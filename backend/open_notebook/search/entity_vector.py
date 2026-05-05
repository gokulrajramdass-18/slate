"""
Entity-Aware Vector Search Strategy for LightRAG.

Enhances traditional vector search with entity graph traversal and re-ranking.
"""

import json
from typing import List, Dict, Any, Optional
import logging

from open_notebook.search.strategies import SearchStrategy, SearchResult, SearchFilters
from open_notebook.search.vector import VectorSearch
from open_notebook.domain.entity import Entity, EntityRelationship
from open_notebook.config import get_database

logger = logging.getLogger(__name__)


class EntityVectorSearch(SearchStrategy):
    """
    Entity-aware vector search with graph-based re-ranking.

    Process:
    1. Extract potential entities from query
    2. Find matching entities in graph
    3. Expand to related entities (1-hop neighbors)
    4. Retrieve chunks associated with entities
    5. Combine with traditional vector search
    6. Re-rank using: score = α * vector_sim + β * graph_centrality + γ * entity_match
    """

    def __init__(
        self,
        vector_weight: float = 0.5,
        graph_weight: float = 0.3,
        entity_match_weight: float = 0.2,
        expansion_depth: int = 1
    ):
        """
        Initialize entity vector search.

        Args:
            vector_weight: Weight for vector similarity score (α)
            graph_weight: Weight for graph centrality score (β)
            entity_match_weight: Weight for entity match score (γ)
            expansion_depth: How many hops to traverse in entity graph
        """
        self.vector_search = VectorSearch()
        self.vector_weight = vector_weight
        self.graph_weight = graph_weight
        self.entity_match_weight = entity_match_weight
        self.expansion_depth = expansion_depth

    async def search(
        self,
        query: str,
        filters: SearchFilters,
        limit: int = 10
    ) -> List[SearchResult]:
        """
        Perform entity-aware vector search.

        Args:
            query: Search query
            filters: Search filters
            limit: Maximum results

        Returns:
            List of search results with entity-aware scores
        """
        # Step 1: Extract entities from query (simple keyword extraction)
        query_entities = await self._extract_query_entities(query)

        if not query_entities:
            # No entities found, fall back to traditional vector search
            logger.debug("No entities found in query, using traditional vector search")
            return await self.vector_search.search(query, filters, limit)

        # Step 2: Find matching entities in graph
        matched_entities = await self._find_entities(query_entities, filters)

        if not matched_entities:
            logger.debug("No matching entities in graph, using traditional vector search")
            return await self.vector_search.search(query, filters, limit)

        # Step 3: Expand to related entities
        expanded_entities = await self._expand_entities(
            [e.id for e in matched_entities],
            depth=self.expansion_depth
        )

        # Step 4: Get chunks associated with entities
        entity_chunks = await self._get_entity_chunks(expanded_entities, filters)

        # Step 5: Traditional vector search
        vector_results = await self.vector_search.search(query, filters, limit * 3)

        # Step 6: Combine and re-rank
        final_results = await self._rerank_with_graph(
            entity_chunks,
            vector_results,
            matched_entities,
            limit
        )

        return final_results

    async def _extract_query_entities(self, query: str) -> List[str]:
        """
        Extract potential entity names from query.

        Simple implementation: Extract capitalized words and phrases.
        In production, use NER (spaCy, Hugging Face) for better extraction.
        """
        words = query.split()

        # Extract capitalized words (potential entity names)
        entities = []
        current_entity = []

        for word in words:
            # Remove punctuation
            clean_word = word.strip('.,?!;:')

            if clean_word and clean_word[0].isupper():
                current_entity.append(clean_word)
            else:
                if current_entity:
                    entities.append(' '.join(current_entity))
                    current_entity = []

        if current_entity:
            entities.append(' '.join(current_entity))

        logger.debug(f"Extracted entities from query: {entities}")
        return entities

    async def _find_entities(
        self,
        query_entities: List[str],
        filters: SearchFilters
    ) -> List[Entity]:
        """Find entities in graph matching query entity names."""
        matched = []

        for entity_name in query_entities:
            # Fuzzy search by name
            results = await Entity.search(
                query=entity_name,
                source_id=None,
                limit=5
            )

            if results:
                matched.extend(results)

        # Deduplicate by ID
        seen = set()
        unique_matched = []
        for entity in matched:
            if entity.id not in seen:
                seen.add(entity.id)
                unique_matched.append(entity)

        logger.debug(f"Found {len(unique_matched)} matching entities in graph")
        return unique_matched

    async def _expand_entities(
        self,
        entity_ids: List[str],
        depth: int = 1
    ) -> List[str]:
        """Expand entity IDs to include related entities via graph traversal."""
        all_entity_ids = set(entity_ids)

        for entity_id in entity_ids:
            related = await Entity.get_related(entity_id, depth=depth)

            for rel_info in related:
                all_entity_ids.add(rel_info['entity_id'])

        logger.debug(f"Expanded {len(entity_ids)} entities to {len(all_entity_ids)} entities")
        return list(all_entity_ids)

    async def _get_entity_chunks(
        self,
        entity_ids: List[str],
        filters: SearchFilters
    ) -> List[Dict[str, Any]]:
        """Get chunks associated with entities."""
        if not entity_ids:
            return []

        db = get_database()

        # Get chunk IDs from entities
        placeholders = ','.join('?' * len(entity_ids))
        entities_data = await db.query(
            f"SELECT DISTINCT chunk_id, source_id FROM entities WHERE id IN ({placeholders}) AND chunk_id IS NOT NULL",
            entity_ids
        )

        chunk_ids = [e['chunk_id'] for e in entities_data if e['chunk_id']]

        if not chunk_ids:
            return []

        # Fetch chunks
        chunk_placeholders = ','.join('?' * len(chunk_ids))
        chunks = await db.query(
            f"""
            SELECT id, source_id, content, order_num
            FROM source_embeddings
            WHERE id IN ({chunk_placeholders})
            """,
            chunk_ids
        )

        # Convert to result format
        entity_chunk_results = []
        for chunk in chunks:
            entity_chunk_results.append({
                'chunk_id': chunk['id'],
                'source_id': chunk['source_id'],
                'content': chunk['content'],
                'from_entity': True  # Mark as entity-derived
            })

        logger.debug(f"Retrieved {len(entity_chunk_results)} chunks from entities")
        return entity_chunk_results

    async def _rerank_with_graph(
        self,
        entity_chunks: List[Dict[str, Any]],
        vector_results: List[SearchResult],
        matched_entities: List[Entity],
        limit: int
    ) -> List[SearchResult]:
        """
        Re-rank combined results using entity graph information.

        Score = α * vector_similarity + β * graph_centrality + γ * entity_match_score
        """
        # Build combined results map
        combined = {}

        # Add vector results
        for result in vector_results:
            key = (result.source_id, result.chunk_id)
            combined[key] = {
                'result': result,
                'vector_score': result.score,
                'graph_centrality': 0.0,
                'entity_match': 0.0,
                'from_entity': False
            }

        # Add entity chunks
        entity_source_ids = set()
        for chunk in entity_chunks:
            key = (chunk['source_id'], chunk['chunk_id'])
            entity_source_ids.add(chunk['source_id'])

            if key not in combined:
                # Create new result for entity chunk
                result = SearchResult(
                    source_id=chunk['source_id'],
                    chunk_id=chunk['chunk_id'],
                    content=chunk['content'],
                    score=0.5,  # Default score
                    highlights=[],
                    metadata={}
                )
                combined[key] = {
                    'result': result,
                    'vector_score': 0.5,
                    'graph_centrality': 0.0,
                    'entity_match': 1.0,  # Full match since from entity
                    'from_entity': True
                }
            else:
                # Boost existing result
                combined[key]['entity_match'] = 1.0
                combined[key]['from_entity'] = True

        # Calculate graph centrality scores
        # For simplicity, use entity relationship count as centrality measure
        db = get_database()
        matched_entity_ids = [e.id for e in matched_entities]

        if matched_entity_ids:
            placeholders = ','.join('?' * len(matched_entity_ids))
            centrality_data = await db.query(
                f"""
                SELECT e.source_id, COUNT(er.id) as relationship_count
                FROM entities e
                LEFT JOIN entity_relationships er ON e.id = er.source_entity_id OR e.id = er.target_entity_id
                WHERE e.id IN ({placeholders})
                GROUP BY e.source_id
                """,
                matched_entity_ids
            )

            max_centrality = max([c['relationship_count'] for c in centrality_data], default=1)

            for c in centrality_data:
                # Normalize centrality
                normalized_centrality = c['relationship_count'] / max_centrality if max_centrality > 0 else 0

                # Apply to all chunks from this source
                for key, data in combined.items():
                    if data['result'].source_id == c['source_id']:
                        data['graph_centrality'] = normalized_centrality

        # Calculate final scores
        for key, data in combined.items():
            final_score = (
                self.vector_weight * data['vector_score'] +
                self.graph_weight * data['graph_centrality'] +
                self.entity_match_weight * data['entity_match']
            )
            data['result'].score = final_score

        # Sort and return top results
        sorted_results = sorted(
            [data['result'] for data in combined.values()],
            key=lambda r: r.score,
            reverse=True
        )

        return sorted_results[:limit]
