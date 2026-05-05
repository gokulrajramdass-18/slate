"""
Entity Graph Service for LightRAG.

Builds graph representations from entity relationships for visualization and querying.
"""

import json
from typing import List, Dict, Any, Optional
import logging

from open_notebook.config import get_database
from open_notebook.domain.entity import Entity, EntityRelationship

logger = logging.getLogger(__name__)


class EntityGraphService:
    """Service for building and querying entity knowledge graphs."""

    async def get_entity_graph(
        self,
        source_id: Optional[str] = None,
        notebook_id: Optional[str] = None,
        entity_types: Optional[List[str]] = None,
        relationship_types: Optional[List[str]] = None,
        community_id: Optional[str] = None,
        min_strength: float = 0.3
    ) -> Dict[str, Any]:
        """
        Build entity graph with optional filters.

        Args:
            source_id: Filter to specific source
            notebook_id: Filter to specific notebook
            entity_types: Filter entity types (e.g., ['person', 'organization'])
            relationship_types: Filter relationship types
            community_id: Filter to specific community
            min_strength: Minimum relationship strength

        Returns:
            Dict with 'nodes' and 'edges' for graph visualization
        """
        db = get_database()

        # Get entities based on filters
        if community_id:
            from open_notebook.domain.entity import Community
            community = await Community.get(community_id)
            if not community:
                return {"nodes": [], "edges": [], "metadata": {}}

            entity_ids = json.loads(community.entity_ids)
            entities = []
            for eid in entity_ids:
                entity = await Entity.get(eid)
                if entity:
                    entities.append(entity)

        elif source_id:
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

        # Apply entity type filter
        if entity_types:
            entities = [e for e in entities if e.entity_type in entity_types]

        if not entities:
            return {"nodes": [], "edges": [], "metadata": {}}

        entity_ids = [e.id for e in entities]

        # Get relationships
        placeholders = ','.join('?' * len(entity_ids))
        query_conditions = [
            f"source_entity_id IN ({placeholders})",
            f"target_entity_id IN ({placeholders})",
            "strength >= ?"
        ]
        query_params = entity_ids + entity_ids + [min_strength]

        if relationship_types:
            rel_placeholders = ','.join('?' * len(relationship_types))
            query_conditions.append(f"relationship_type IN ({rel_placeholders})")
            query_params.extend(relationship_types)

        relationships = await db.query(
            f"""
            SELECT er.*,
                   e1.name as source_name,
                   e1.entity_type as source_type,
                   e2.name as target_name,
                   e2.entity_type as target_type
            FROM entity_relationships er
            JOIN entities e1 ON er.source_entity_id = e1.id
            JOIN entities e2 ON er.target_entity_id = e2.id
            WHERE {' AND '.join(query_conditions)}
            """,
            query_params
        )

        # Build nodes
        nodes = []
        for entity in entities:
            metadata = json.loads(entity.metadata) if entity.metadata else {}

            node = {
                "id": entity.id,
                "type": "entity",  # React Flow node type
                "label": entity.name,
                "data": {
                    "name": entity.name,
                    "entity_type": entity.entity_type,
                    "description": entity.description,
                    "source_id": entity.source_id,
                    "mentions": metadata.get("mentions", 1),
                    "confidence": metadata.get("confidence", 0.8)
                }
            }
            nodes.append(node)

        # Build edges
        edges = []
        for rel in relationships:
            metadata = json.loads(rel['metadata']) if rel['metadata'] else {}

            edge = {
                "id": rel['id'],
                "source": rel['source_entity_id'],
                "target": rel['target_entity_id'],
                "type": "relationship",  # React Flow edge type
                "label": rel['relationship_type'],
                "data": {
                    "relationship_type": rel['relationship_type'],
                    "strength": rel['strength'],
                    "context": rel['context'],
                    "co_occurrence_count": metadata.get("co_occurrence_count", 1),
                    "source_name": rel['source_name'],
                    "target_name": rel['target_name']
                }
            }
            edges.append(edge)

        # Calculate metadata
        metadata = {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "entity_type_distribution": {},
            "relationship_type_distribution": {},
            "avg_strength": sum(e['data']['strength'] for e in edges) / len(edges) if edges else 0
        }

        # Count entity types
        for entity in entities:
            metadata["entity_type_distribution"][entity.entity_type] = \
                metadata["entity_type_distribution"].get(entity.entity_type, 0) + 1

        # Count relationship types
        for rel in relationships:
            metadata["relationship_type_distribution"][rel['relationship_type']] = \
                metadata["relationship_type_distribution"].get(rel['relationship_type'], 0) + 1

        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": metadata
        }

    async def get_entity_neighborhood(
        self,
        entity_id: str,
        depth: int = 1,
        min_strength: float = 0.3
    ) -> Dict[str, Any]:
        """
        Get entity and its neighbors up to specified depth (BFS expansion).

        Args:
            entity_id: Starting entity ID
            depth: How many hops to traverse
            min_strength: Minimum relationship strength

        Returns:
            Graph dict with nodes and edges
        """
        db = get_database()

        # Get starting entity
        entity = await Entity.get(entity_id)
        if not entity:
            return {"nodes": [], "edges": [], "metadata": {}}

        # BFS to collect entity IDs
        visited = set()
        queue = [(entity_id, 0)]  # (entity_id, current_depth)
        entity_ids_to_fetch = set([entity_id])

        while queue:
            current_id, current_depth = queue.pop(0)

            if current_id in visited or current_depth > depth:
                continue

            visited.add(current_id)

            # Get neighbors
            relationships = await EntityRelationship.get_by_entity(
                current_id,
                direction="both",
                min_strength=min_strength
            )

            for rel in relationships:
                neighbor_id = (
                    rel.target_entity_id
                    if rel.source_entity_id == current_id
                    else rel.source_entity_id
                )

                entity_ids_to_fetch.add(neighbor_id)

                if current_depth < depth:
                    queue.append((neighbor_id, current_depth + 1))

        # Fetch all entities
        entities = []
        for eid in entity_ids_to_fetch:
            e = await Entity.get(eid)
            if e:
                entities.append(e)

        # Get relationships between these entities
        entity_id_list = list(entity_ids_to_fetch)
        placeholders = ','.join('?' * len(entity_id_list))

        relationships = await db.query(
            f"""
            SELECT er.*,
                   e1.name as source_name,
                   e2.name as target_name
            FROM entity_relationships er
            JOIN entities e1 ON er.source_entity_id = e1.id
            JOIN entities e2 ON er.target_entity_id = e2.id
            WHERE er.source_entity_id IN ({placeholders})
              AND er.target_entity_id IN ({placeholders})
              AND er.strength >= ?
            """,
            entity_id_list + entity_id_list + [min_strength]
        )

        # Build graph (reuse logic from get_entity_graph)
        nodes = []
        for e in entities:
            metadata = json.loads(e.metadata) if e.metadata else {}
            nodes.append({
                "id": e.id,
                "type": "entity",
                "label": e.name,
                "data": {
                    "name": e.name,
                    "entity_type": e.entity_type,
                    "description": e.description,
                    "is_center": e.id == entity_id,  # Mark center node
                    "mentions": metadata.get("mentions", 1)
                }
            })

        edges = []
        for rel in relationships:
            metadata = json.loads(rel['metadata']) if rel['metadata'] else {}
            edges.append({
                "id": rel['id'],
                "source": rel['source_entity_id'],
                "target": rel['target_entity_id'],
                "type": "relationship",
                "label": rel['relationship_type'],
                "data": {
                    "relationship_type": rel['relationship_type'],
                    "strength": rel['strength'],
                    "context": rel['context']
                }
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "center_entity_id": entity_id,
                "depth": depth,
                "total_nodes": len(nodes),
                "total_edges": len(edges)
            }
        }

    async def get_entity_path(
        self,
        source_entity_id: str,
        target_entity_id: str,
        max_depth: int = 5
    ) -> Dict[str, Any]:
        """
        Find shortest path between two entities and return as subgraph.

        Args:
            source_entity_id: Starting entity
            target_entity_id: Destination entity
            max_depth: Maximum path length

        Returns:
            Graph dict with path nodes and edges
        """
        # Use domain model's path finding
        path = await EntityRelationship.get_path(
            source_entity_id,
            target_entity_id,
            max_depth
        )

        if not path:
            return {
                "nodes": [],
                "edges": [],
                "metadata": {"path_found": False}
            }

        # Extract entity IDs from path
        entity_ids = set([source_entity_id, target_entity_id])
        for rel in path:
            entity_ids.add(rel['source_entity_id'])
            entity_ids.add(rel['target_entity_id'])

        # Fetch entities
        entities = []
        for eid in entity_ids:
            entity = await Entity.get(eid)
            if entity:
                entities.append(entity)

        # Build nodes
        nodes = []
        for entity in entities:
            nodes.append({
                "id": entity.id,
                "type": "entity",
                "label": entity.name,
                "data": {
                    "name": entity.name,
                    "entity_type": entity.entity_type,
                    "description": entity.description,
                    "is_source": entity.id == source_entity_id,
                    "is_target": entity.id == target_entity_id,
                    "on_path": True
                }
            })

        # Build edges
        edges = []
        for rel in path:
            metadata = json.loads(rel['metadata']) if rel['metadata'] else {}
            edges.append({
                "id": rel['id'],
                "source": rel['source_entity_id'],
                "target": rel['target_entity_id'],
                "type": "relationship",
                "label": rel['relationship_type'],
                "data": {
                    "relationship_type": rel['relationship_type'],
                    "strength": rel['strength'],
                    "context": rel['context'],
                    "on_path": True
                }
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "path_found": True,
                "path_length": len(path),
                "source_entity_id": source_entity_id,
                "target_entity_id": target_entity_id
            }
        }

    async def export_graph(
        self,
        format: str = "json",
        **graph_params
    ) -> Any:
        """
        Export entity graph in various formats.

        Args:
            format: Export format ('json', 'gexf', 'graphml')
            **graph_params: Parameters passed to get_entity_graph()

        Returns:
            Exported graph data
        """
        graph = await self.get_entity_graph(**graph_params)

        if format == "json":
            return graph

        elif format == "gexf":
            # GEXF format for Gephi
            try:
                import networkx as nx
                G = nx.DiGraph()

                for node in graph['nodes']:
                    G.add_node(
                        node['id'],
                        label=node['label'],
                        entity_type=node['data']['entity_type']
                    )

                for edge in graph['edges']:
                    G.add_edge(
                        edge['source'],
                        edge['target'],
                        label=edge['label'],
                        weight=edge['data']['strength']
                    )

                from io import BytesIO
                buffer = BytesIO()
                nx.write_gexf(G, buffer)
                return buffer.getvalue()

            except ImportError:
                logger.error("NetworkX required for GEXF export")
                return None

        elif format == "graphml":
            # GraphML format
            try:
                import networkx as nx
                G = nx.DiGraph()

                for node in graph['nodes']:
                    G.add_node(node['id'], **node['data'])

                for edge in graph['edges']:
                    G.add_edge(
                        edge['source'],
                        edge['target'],
                        **edge['data']
                    )

                from io import BytesIO
                buffer = BytesIO()
                nx.write_graphml(G, buffer)
                return buffer.getvalue()

            except ImportError:
                logger.error("NetworkX required for GraphML export")
                return None

        else:
            raise ValueError(f"Unsupported export format: {format}")
