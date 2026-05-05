"""
Entity Extraction Service for LightRAG.

Extracts entities and relationships from source content using LLM-based analysis.
Supports multiple AI providers via LangChain integration.
"""

import json
import uuid
from typing import List, Dict, Any, Optional, Tuple
import asyncio
from datetime import datetime

from open_notebook.config import get_database
from open_notebook.domain.entity import Entity, EntityRelationship
import logging

# Try to import LangChain, fall back to placeholder if not available
try:
    from langchain_community.chat_models import ChatLiteLLM
    from langchain.prompts import ChatPromptTemplate
    from langchain_core.messages import HumanMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

logger = logging.getLogger(__name__)


# LLM Prompt Templates
ENTITY_EXTRACTION_PROMPT = """Extract entities and relationships from the following text chunk.

Text:
{chunk_text}

Instructions:
1. Identify all entities: people, organizations, locations, events, and concepts
2. For each entity, provide:
   - Name (canonical form, use title case for consistency)
   - Type (person/organization/location/event/concept/other)
   - Brief description (1-2 sentences explaining what/who this entity is)
3. Identify relationships between entities mentioned in this chunk
4. For each relationship:
   - Source entity name
   - Target entity name
   - Relationship type (verb phrase like "works_for", "located_in", "collaborated_on", "mentions", "founded", "part_of")
   - Context (the sentence or phrase where this relationship is mentioned)
5. Be precise and avoid duplicates

Output JSON format (strict JSON only, no markdown):
{{
  "entities": [
    {{"name": "...", "type": "person|organization|location|event|concept|other", "description": "..."}},
    ...
  ],
  "relationships": [
    {{"source": "...", "target": "...", "type": "...", "context": "..."}},
    ...
  ]
}}
"""

ENTITY_MERGE_PROMPT = """Determine if these entities refer to the same real-world entity.

Entity 1: {entity1_name}
Description: {entity1_description}

Entity 2: {entity2_name}
Description: {entity2_description}

Output JSON format (strict JSON only):
{{
  "same_entity": true|false,
  "confidence": 0.0-1.0,
  "reason": "brief explanation"
}}
"""


class EntityExtractionService:
    """Service for extracting entities and relationships from text using LLM."""

    def __init__(
        self,
        model: Optional[str] = None,
        max_entities_per_chunk: int = 20,
        min_confidence: float = 0.7,
        batch_size: int = 10
    ):
        """
        Initialize entity extraction service.

        Args:
            model: LLM model to use (defaults to configured model)
            max_entities_per_chunk: Maximum entities to extract per chunk
            min_confidence: Minimum confidence threshold for extraction
            batch_size: Number of chunks to process in parallel
        """
        self.model = model
        self.max_entities_per_chunk = max_entities_per_chunk
        self.min_confidence = min_confidence
        self.batch_size = batch_size

    async def extract_entities_from_chunk(
        self,
        chunk_id: str,
        chunk_text: str,
        source_id: str
    ) -> Dict[str, Any]:
        """
        Extract entities and relationships from a single chunk.

        Args:
            chunk_id: Chunk ID reference
            chunk_text: Text content to analyze
            source_id: Source ID this chunk belongs to

        Returns:
            Dict with 'entities' and 'relationships' lists
        """
        try:
            # Prepare prompt
            prompt = ENTITY_EXTRACTION_PROMPT.format(chunk_text=chunk_text)

            # Call LLM (use LangChain if available)
            if LANGCHAIN_AVAILABLE and self.model:
                llm = ChatLiteLLM(model=self.model, temperature=0)
                response = await llm.ainvoke([HumanMessage(content=prompt)])
                content = response.content
            else:
                # Placeholder for when LLM is not available
                logger.warning("LLM not available - returning empty extraction results")
                return {"entities": [], "relationships": []}

            # Parse response
            try:
                # Try to extract JSON from response
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                extraction_result = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {e}")
                logger.error(f"Response: {content}")
                return {"entities": [], "relationships": []}

            # Validate and normalize entities
            entities = []
            for entity_data in extraction_result.get("entities", [])[:self.max_entities_per_chunk]:
                if not entity_data.get("name") or not entity_data.get("type"):
                    continue

                # Normalize entity name (title case)
                name = self._normalize_entity_name(entity_data["name"])

                entity = {
                    "id": str(uuid.uuid4()),
                    "name": name,
                    "entity_type": entity_data["type"].lower(),
                    "description": entity_data.get("description", ""),
                    "source_id": source_id,
                    "chunk_id": chunk_id,
                    "metadata": json.dumps({
                        "mentions": 1,
                        "first_seen": datetime.utcnow().isoformat(),
                        "confidence": 0.8  # Default confidence
                    })
                }
                entities.append(entity)

            # Validate and normalize relationships
            relationships = []
            entity_name_to_id = {e["name"]: e["id"] for e in entities}

            for rel_data in extraction_result.get("relationships", []):
                source_name = self._normalize_entity_name(rel_data.get("source", ""))
                target_name = self._normalize_entity_name(rel_data.get("target", ""))

                # Check if both entities exist
                if source_name not in entity_name_to_id or target_name not in entity_name_to_id:
                    continue

                relationship = {
                    "id": str(uuid.uuid4()),
                    "source_entity_id": entity_name_to_id[source_name],
                    "target_entity_id": entity_name_to_id[target_name],
                    "relationship_type": rel_data.get("type", "mentions").lower().replace(" ", "_"),
                    "context": rel_data.get("context", ""),
                    "chunk_id": chunk_id,
                    "strength": 0.5,  # Default strength
                    "metadata": json.dumps({
                        "co_occurrence_count": 1,
                        "confidence": 0.8
                    })
                }
                relationships.append(relationship)

            return {
                "entities": entities,
                "relationships": relationships
            }

        except Exception as e:
            logger.error(f"Error extracting entities from chunk {chunk_id}: {e}")
            return {"entities": [], "relationships": []}

    async def extract_entities_from_source(
        self,
        source_id: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Extract entities from all chunks in a source.

        Args:
            source_id: Source ID to process
            force: If True, re-extract even if entities already exist

        Returns:
            Dict with extraction statistics
        """
        db = get_database()

        # Check if already extracted
        if not force:
            existing = await db.query(
                "SELECT COUNT(*) as count FROM entities WHERE source_id = ?",
                [source_id]
            )
            if existing[0]['count'] > 0:
                logger.info(f"Source {source_id} already has entities. Use force=True to re-extract.")
                return {
                    "source_id": source_id,
                    "entities_count": existing[0]['count'],
                    "skipped": True
                }

        # Get all chunks for this source
        chunks = await db.query(
            "SELECT id, content FROM source_embeddings WHERE source_id = ? ORDER BY order_num",
            [source_id]
        )

        if not chunks:
            logger.warning(f"No chunks found for source {source_id}")
            return {
                "source_id": source_id,
                "entities_count": 0,
                "relationships_count": 0,
                "chunks_processed": 0
            }

        # Process chunks in batches
        all_entities = []
        all_relationships = []

        for i in range(0, len(chunks), self.batch_size):
            batch = chunks[i:i + self.batch_size]

            # Extract entities from batch in parallel
            tasks = [
                self.extract_entities_from_chunk(chunk['id'], chunk['content'], source_id)
                for chunk in batch
            ]
            results = await asyncio.gather(*tasks)

            for result in results:
                all_entities.extend(result["entities"])
                all_relationships.extend(result["relationships"])

        # Deduplicate entities by name
        deduplicated = await self._deduplicate_entities(all_entities)
        all_entities = deduplicated["entities"]
        entity_id_mapping = deduplicated["mapping"]

        # Update relationship entity IDs based on deduplication
        for rel in all_relationships:
            if rel["source_entity_id"] in entity_id_mapping:
                rel["source_entity_id"] = entity_id_mapping[rel["source_entity_id"]]
            if rel["target_entity_id"] in entity_id_mapping:
                rel["target_entity_id"] = entity_id_mapping[rel["target_entity_id"]]

        # Save to database
        for entity in all_entities:
            await db.query(
                """
                INSERT INTO entities (id, name, entity_type, description, source_id, chunk_id, metadata, created, updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                [
                    entity["id"],
                    entity["name"],
                    entity["entity_type"],
                    entity["description"],
                    entity["source_id"],
                    entity["chunk_id"],
                    entity["metadata"]
                ]
            )

        for rel in all_relationships:
            try:
                await db.query(
                    """
                    INSERT INTO entity_relationships (id, source_entity_id, target_entity_id, relationship_type, context, chunk_id, strength, metadata, created)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    [
                        rel["id"],
                        rel["source_entity_id"],
                        rel["target_entity_id"],
                        rel["relationship_type"],
                        rel["context"],
                        rel["chunk_id"],
                        rel["strength"],
                        rel["metadata"]
                    ]
                )
            except Exception as e:
                # Likely a duplicate relationship
                logger.debug(f"Skipping duplicate relationship: {e}")

        logger.info(
            f"Extracted {len(all_entities)} entities and {len(all_relationships)} relationships "
            f"from {len(chunks)} chunks in source {source_id}"
        )

        return {
            "source_id": source_id,
            "entities_count": len(all_entities),
            "relationships_count": len(all_relationships),
            "chunks_processed": len(chunks)
        }

    async def batch_extract_from_notebook(self, notebook_id: str) -> Dict[str, Any]:
        """
        Extract entities from all sources in a notebook.

        Args:
            notebook_id: Notebook ID

        Returns:
            Dict with aggregated statistics
        """
        db = get_database()

        # Get all sources in notebook
        sources = await db.query(
            """
            SELECT s.id FROM sources s
            JOIN notebook_source ns ON s.id = ns.source_id
            WHERE ns.notebook_id = ?
            """,
            [notebook_id]
        )

        if not sources:
            return {
                "notebook_id": notebook_id,
                "sources_processed": 0,
                "total_entities": 0,
                "total_relationships": 0
            }

        # Process each source
        results = []
        for source in sources:
            result = await self.extract_entities_from_source(source['id'])
            results.append(result)

        # Aggregate statistics
        total_entities = sum(r['entities_count'] for r in results)
        total_relationships = sum(r['relationships_count'] for r in results)

        return {
            "notebook_id": notebook_id,
            "sources_processed": len(sources),
            "total_entities": total_entities,
            "total_relationships": total_relationships,
            "per_source": results
        }

    async def merge_duplicate_entities(
        self,
        entity_id_1: str,
        entity_id_2: str
    ) -> str:
        """
        Merge two entities that refer to the same real-world entity.

        Uses LLM to verify if entities should be merged.

        Args:
            entity_id_1: First entity ID
            entity_id_2: Second entity ID

        Returns:
            The kept entity ID
        """
        # Get entities
        entity1 = await Entity.get(entity_id_1)
        entity2 = await Entity.get(entity_id_2)

        if not entity1 or not entity2:
            raise ValueError("One or both entities not found")

        if not merge_decision.get("same_entity", False):
            logger.info(f"LLM determined entities are not the same: {merge_decision.get('reason')}")
            return entity_id_1  # No merge

        # Use LLM to verify merge
        prompt = ENTITY_MERGE_PROMPT.format(
            entity1_name=entity1.name,
            entity1_description=entity1.description or "",
            entity2_name=entity2.name,
            entity2_description=entity2.description or ""
        )

        if LANGCHAIN_AVAILABLE and self.model:
            llm = ChatLiteLLM(model=self.model, temperature=0)
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content
        else:
            # Without LLM, default to not merging
            logger.warning("LLM not available - skipping entity merge")
            return entity_id_1

        # Parse response
        try:
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            merge_decision = json.loads(content)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse merge decision: {content}")
            raise ValueError("Failed to parse LLM merge decision")

        # Merge entities (keep entity1)
        kept_id = await Entity.merge_entities([entity_id_1, entity_id_2], entity_id_1)

        logger.info(f"Merged entities {entity_id_1} and {entity_id_2} into {kept_id}")

        return kept_id

    async def recompute_entity_graph(self, source_id: str) -> None:
        """
        Recompute entity graph for a source.

        Deletes existing entities and re-extracts from chunks.

        Args:
            source_id: Source ID to recompute
        """
        db = get_database()

        # Delete existing entities (CASCADE will delete relationships)
        await db.query("DELETE FROM entities WHERE source_id = ?", [source_id])

        # Re-extract
        await self.extract_entities_from_source(source_id, force=True)

    async def _deduplicate_entities(
        self,
        entities: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Deduplicate entities by name within the same source.

        Args:
            entities: List of entity dicts

        Returns:
            Dict with deduplicated entities and ID mapping
        """
        # Group by name
        entities_by_name = {}
        for entity in entities:
            name = entity["name"]
            if name not in entities_by_name:
                entities_by_name[name] = []
            entities_by_name[name].append(entity)

        # For each name group, keep first and merge metadata
        deduplicated = []
        id_mapping = {}  # old_id -> new_id

        for name, entity_group in entities_by_name.items():
            if len(entity_group) == 1:
                deduplicated.append(entity_group[0])
                continue

            # Keep first entity
            kept_entity = entity_group[0]

            # Update metadata (sum mentions)
            metadata = json.loads(kept_entity["metadata"])
            metadata["mentions"] = len(entity_group)
            metadata["aliases"] = list(set([e["name"] for e in entity_group[1:]]))
            kept_entity["metadata"] = json.dumps(metadata)

            deduplicated.append(kept_entity)

            # Map all old IDs to kept ID
            for entity in entity_group:
                id_mapping[entity["id"]] = kept_entity["id"]

        return {
            "entities": deduplicated,
            "mapping": id_mapping
        }

    def _normalize_entity_name(self, name: str) -> str:
        """Normalize entity name to title case for consistency."""
        # Remove extra whitespace
        name = " ".join(name.split())

        # Title case for consistency
        return name.title()
