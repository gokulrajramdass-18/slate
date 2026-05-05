"""
Community Detection Service for LightRAG.

Implements Louvain algorithm for entity clustering and LLM-based community summarization.
"""

import json
import uuid
from typing import List, Dict, Any, Optional
import asyncio
from datetime import datetime
import logging

try:
    import networkx as nx
    from networkx.algorithms import community as nx_community
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    logging.warning("NetworkX not available - community detection disabled")

try:
    from langchain_community.chat_models import ChatLiteLLM
    from langchain_core.messages import HumanMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

from open_notebook.config import get_database
from open_notebook.domain.entity import Entity, EntityRelationship, Community

logger = logging.getLogger(__name__)


COMMUNITY_SUMMARY_PROMPT = """Summarize the following community of entities and their relationships.

Entities in this community:
{entity_list}

Relationships between them:
{relationship_list}

Provide:
1. A concise name for this community (2-5 words describing the theme)
2. A brief description of what connects these entities (1-2 sentences)
3. The 3 most important/central entities in this community

Output JSON format (strict JSON only):
{{
  "name": "...",
  "description": "...",
  "central_entities": ["...", "...", "..."]
}}
"""


class CommunityDetectionService:
    """Service for detecting and managing entity communities using Louvain algorithm."""

    def __init__(
        self,
        model: Optional[str] = None,
        resolution: float = 1.0,
        min_community_size: int = 3
    ):
        """
        Initialize community detection service.

        Args:
            model: LLM model for summary generation
            resolution: Louvain resolution parameter (higher = more communities)
            min_community_size: Minimum entities per community
        """
        self.model = model
        self.resolution = resolution
        self.min_community_size = min_community_size

        if not NETWORKX_AVAILABLE:
            logger.error("NetworkX required for community detection. Install: pip install networkx")

    async def detect_communities(
        self,
        source_id: Optional[str] = None,
        notebook_id: Optional[str] = None,
        level: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Run Louvain community detection on entity graph.

        Args:
            source_id: Optional filter to specific source
            notebook_id: Optional filter to specific notebook
            level: Hierarchy level (0 = base level)

        Returns:
            List of detected communities with entity IDs
        """
        if not NETWORKX_AVAILABLE:
            raise RuntimeError("NetworkX not installed")

        db = get_database()

        # Build entity graph
        graph = await self._build_entity_graph(source_id, notebook_id)

        if graph.number_of_nodes() < self.min_community_size:
            logger.warning(f"Too few entities ({graph.number_of_nodes()}) for community detection")
            return []

        # Run Louvain algorithm
        try:
            communities = nx_community.louvain_communities(
                graph,
                resolution=self.resolution,
                seed=42  # For reproducibility
            )
        except Exception as e:
            logger.error(f"Louvain algorithm failed: {e}")
            return []

        # Filter by minimum size
        communities = [c for c in communities if len(c) >= self.min_community_size]

        # Calculate modularity
        modularity = nx_community.modularity(graph, communities)

        logger.info(
            f"Detected {len(communities)} communities with modularity {modularity:.3f}"
        )

        # Convert to community dicts
        community_results = []
        for i, entity_set in enumerate(communities):
            community_id = str(uuid.uuid4())
            entity_ids = list(entity_set)

            # Calculate community metadata
            subgraph = graph.subgraph(entity_ids)
            density = nx.density(subgraph)

            # Get central entities (by degree centrality)
            centrality = nx.degree_centrality(subgraph)
            central_entities = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:3]
            central_entity_ids = [e[0] for e in central_entities]

            community_data = {
                "id": community_id,
                "name": None,  # Will be set by LLM
                "description": None,  # Will be set by LLM
                "level": level,
                "parent_community_id": None,
                "entity_ids": json.dumps(entity_ids),
                "metadata": json.dumps({
                    "size": len(entity_ids),
                    "density": density,
                    "central_entities": central_entity_ids,
                    "modularity": modularity
                })
            }

            community_results.append(community_data)

        return community_results

    async def generate_community_summary(
        self,
        community_id: str
    ) -> Dict[str, str]:
        """
        Generate LLM-based summary for a community.

        Args:
            community_id: Community ID

        Returns:
            Dict with name, description, central_entities
        """
        # Get community
        community = await Community.get(community_id)
        if not community:
            raise ValueError(f"Community {community_id} not found")

        # Get entities
        entity_ids = json.loads(community.entity_ids)
        entities = []
        for entity_id in entity_ids:
            entity = await Entity.get(entity_id)
            if entity:
                entities.append(entity)

        if not entities:
            return {
                "name": "Empty Community",
                "description": "No entities in this community",
                "central_entities": []
            }

        # Get relationships between entities
        db = get_database()
        placeholders = ','.join('?' * len(entity_ids))
        relationships = await db.query(
            f"""
            SELECT er.*, e1.name as source_name, e2.name as target_name
            FROM entity_relationships er
            JOIN entities e1 ON er.source_entity_id = e1.id
            JOIN entities e2 ON er.target_entity_id = e2.id
            WHERE er.source_entity_id IN ({placeholders})
              AND er.target_entity_id IN ({placeholders})
            ORDER BY er.strength DESC
            LIMIT 20
            """,
            entity_ids + entity_ids
        )

        # Format entity list
        entity_list = "\n".join([
            f"- {e.name} ({e.entity_type}): {e.description or 'No description'}"
            for e in entities[:15]  # Limit to 15 for context
        ])

        # Format relationship list
        relationship_list = "\n".join([
            f"- {r['source_name']} {r['relationship_type']} {r['target_name']}"
            for r in relationships[:15]  # Limit to 15
        ])

        # Generate summary with LLM
        if LANGCHAIN_AVAILABLE and self.model:
            prompt = COMMUNITY_SUMMARY_PROMPT.format(
                entity_list=entity_list,
                relationship_list=relationship_list
            )

            try:
                llm = ChatLiteLLM(model=self.model, temperature=0.3)
                response = await llm.ainvoke([HumanMessage(content=prompt)])
                content = response.content

                # Parse JSON
                if content.startswith("```json"):
                    content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                summary = json.loads(content)

                return {
                    "name": summary.get("name", f"Community {community_id[:8]}"),
                    "description": summary.get("description", ""),
                    "central_entities": summary.get("central_entities", [])[:3]
                }

            except Exception as e:
                logger.error(f"Failed to generate community summary: {e}")

        # Fallback: Generate basic summary
        entity_types = {}
        for entity in entities:
            entity_types[entity.entity_type] = entity_types.get(entity.entity_type, 0) + 1

        dominant_type = max(entity_types.items(), key=lambda x: x[1])[0] if entity_types else "mixed"

        return {
            "name": f"{dominant_type.title()} Community",
            "description": f"A community of {len(entities)} entities, primarily {dominant_type}s",
            "central_entities": [e.name for e in entities[:3]]
        }

    async def save_communities(
        self,
        communities: List[Dict[str, Any]],
        generate_summaries: bool = True
    ) -> List[str]:
        """
        Save detected communities to database.

        Args:
            communities: List of community dicts from detect_communities()
            generate_summaries: Whether to generate LLM summaries

        Returns:
            List of saved community IDs
        """
        db = get_database()
        saved_ids = []

        for community_data in communities:
            # Generate summary if requested
            if generate_summaries:
                # Save placeholder first
                await db.query(
                    """
                    INSERT INTO entity_communities (id, name, description, level, parent_community_id, entity_ids, metadata, created, updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    [
                        community_data["id"],
                        community_data["name"],
                        community_data["description"],
                        community_data["level"],
                        community_data["parent_community_id"],
                        community_data["entity_ids"],
                        community_data["metadata"]
                    ]
                )

                # Generate summary
                try:
                    summary = await self.generate_community_summary(community_data["id"])

                    # Update with summary
                    await db.query(
                        """
                        UPDATE entity_communities
                        SET name = ?, description = ?, updated = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        [summary["name"], summary["description"], community_data["id"]]
                    )

                    # Update central entities in metadata
                    metadata = json.loads(community_data["metadata"])
                    metadata["central_entity_names"] = summary["central_entities"]
                    await db.query(
                        "UPDATE entity_communities SET metadata = ? WHERE id = ?",
                        [json.dumps(metadata), community_data["id"]]
                    )

                except Exception as e:
                    logger.error(f"Failed to generate summary for community {community_data['id']}: {e}")

            else:
                # Save without summary
                await db.query(
                    """
                    INSERT INTO entity_communities (id, name, description, level, parent_community_id, entity_ids, metadata, created, updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    [
                        community_data["id"],
                        community_data["name"] or f"Community {len(saved_ids) + 1}",
                        community_data["description"],
                        community_data["level"],
                        community_data["parent_community_id"],
                        community_data["entity_ids"],
                        community_data["metadata"]
                    ]
                )

            saved_ids.append(community_data["id"])

        logger.info(f"Saved {len(saved_ids)} communities to database")

        return saved_ids

    async def get_hierarchical_communities(
        self,
        max_levels: int = 3
    ) -> Dict[int, List[Dict[str, Any]]]:
        """
        Detect multi-level hierarchical communities.

        Args:
            max_levels: Maximum hierarchy depth

        Returns:
            Dict mapping level to list of communities
        """
        if not NETWORKX_AVAILABLE:
            raise RuntimeError("NetworkX not installed")

        hierarchy = {}

        # Level 0: Base communities with high resolution
        level_0_communities = await self.detect_communities(level=0)
        hierarchy[0] = level_0_communities

        # Build parent-child relationships for higher levels
        # For simplicity, we'll group communities at each level
        # In production, this would use more sophisticated hierarchical clustering

        for level in range(1, max_levels):
            # Decrease resolution to get larger communities
            self.resolution = self.resolution * 0.5
            level_communities = await self.detect_communities(level=level)

            if not level_communities:
                break

            hierarchy[level] = level_communities

        return hierarchy

    async def update_communities_incremental(
        self,
        new_entity_ids: List[str]
    ) -> None:
        """
        Update communities after new entities are added.

        For simplicity, this re-runs community detection.
        In production, implement true incremental updates.

        Args:
            new_entity_ids: List of newly added entity IDs
        """
        logger.info(f"Updating communities for {len(new_entity_ids)} new entities")

        # For now, re-detect communities
        # TODO: Implement incremental Louvain updates
        communities = await self.detect_communities()
        await self.save_communities(communities, generate_summaries=True)

    async def _build_entity_graph(
        self,
        source_id: Optional[str] = None,
        notebook_id: Optional[str] = None
    ) -> 'nx.Graph':
        """
        Build NetworkX graph from entity relationships.

        Args:
            source_id: Optional filter to specific source
            notebook_id: Optional filter to specific notebook

        Returns:
            NetworkX Graph
        """
        db = get_database()

        # Get entities
        if source_id:
            entities = await Entity.get_by_source(source_id)
        elif notebook_id:
            sources = await db.query(
                "SELECT source_id FROM notebook_source WHERE notebook_id = ?",
                [notebook_id]
            )
            source_ids = [s['source_id'] for s in sources]

            entities = []
            for sid in source_ids:
                entities.extend(await Entity.get_by_source(sid))
        else:
            entities = await Entity.get_all()

        entity_ids = [e.id for e in entities]

        if not entity_ids:
            return nx.Graph()

        # Get relationships
        placeholders = ','.join('?' * len(entity_ids))
        relationships = await db.query(
            f"""
            SELECT * FROM entity_relationships
            WHERE source_entity_id IN ({placeholders})
              AND target_entity_id IN ({placeholders})
            """,
            entity_ids + entity_ids
        )

        # Build graph
        graph = nx.Graph()

        # Add nodes
        for entity in entities:
            graph.add_node(entity.id, name=entity.name, type=entity.entity_type)

        # Add edges (undirected, weighted by strength)
        for rel in relationships:
            graph.add_edge(
                rel['source_entity_id'],
                rel['target_entity_id'],
                weight=rel['strength'],
                type=rel['relationship_type']
            )

        logger.info(f"Built graph with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges")

        return graph
