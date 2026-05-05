"""
Entity domain models for LightRAG knowledge graph.

Provides Entity, EntityRelationship, and Community models with graph query capabilities.
"""

from typing import List, Optional, Dict, Any, ClassVar
import json
from open_notebook.domain.base import ObjectModel
from open_notebook.config import get_database


class Entity(ObjectModel):
    """
    Entity extracted from source content.

    Represents people, organizations, locations, events, concepts, etc.
    """

    _table_name: ClassVar[str] = "entities"

    # Model fields
    name: str
    entity_type: str
    description: Optional[str] = None
    source_id: str
    chunk_id: Optional[str] = None
    metadata: Optional[str] = None

    @classmethod
    async def get_by_source(cls, source_id: str, entity_type: Optional[str] = None) -> List['Entity']:
        """Get all entities extracted from a source, optionally filtered by type."""
        db = get_database()

        if entity_type:
            query = f"SELECT * FROM {cls._table_name} WHERE source_id = ? AND entity_type = ? ORDER BY created DESC"
            params = [source_id, entity_type]
        else:
            query = f"SELECT * FROM {cls._table_name} WHERE source_id = ? ORDER BY created DESC"
            params = [source_id]

        results = await db.query(query, params)
        return [cls(**row) for row in results]

    @classmethod
    async def get_by_name(cls, name: str, fuzzy: bool = False) -> List['Entity']:
        """
        Find entities by name.

        Args:
            name: Entity name to search for
            fuzzy: If True, use case-insensitive LIKE search; if False, exact match
        """
        db = get_database()

        if fuzzy:
            query = f"SELECT * FROM {cls.table_name} WHERE LOWER(name) LIKE LOWER(?) ORDER BY name"
            params = [f"%{name}%"]
        else:
            query = f"SELECT * FROM {cls.table_name} WHERE name = ? ORDER BY created DESC"
            params = [name]

        results = await db.query(query, params)
        return [cls(**row) for row in results]

    @classmethod
    async def get_related(
        cls,
        entity_id: str,
        depth: int = 1,
        relationship_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get related entities via relationship graph using BFS.

        Args:
            entity_id: Starting entity ID
            depth: How many hops to traverse (default: 1)
            relationship_types: Optional filter for relationship types

        Returns:
            List of dicts with entity, relationship, and distance information
        """
        db = get_database()

        # BFS traversal
        visited = set()
        queue = [(entity_id, 0)]  # (entity_id, distance)
        related_entities = []

        while queue:
            current_entity_id, current_depth = queue.pop(0)

            if current_entity_id in visited or current_depth > depth:
                continue

            visited.add(current_entity_id)

            # Get all relationships where this entity is source or target
            if relationship_types:
                placeholders = ','.join('?' * len(relationship_types))
                query = f"""
                    SELECT er.*,
                           e1.name as source_name,
                           e2.name as target_name
                    FROM entity_relationships er
                    JOIN entities e1 ON er.source_entity_id = e1.id
                    JOIN entities e2 ON er.target_entity_id = e2.id
                    WHERE (er.source_entity_id = ? OR er.target_entity_id = ?)
                      AND er.relationship_type IN ({placeholders})
                    ORDER BY er.strength DESC
                """
                params = [current_entity_id, current_entity_id] + relationship_types
            else:
                query = """
                    SELECT er.*,
                           e1.name as source_name,
                           e2.name as target_name
                    FROM entity_relationships er
                    JOIN entities e1 ON er.source_entity_id = e1.id
                    JOIN entities e2 ON er.target_entity_id = e2.id
                    WHERE er.source_entity_id = ? OR er.target_entity_id = ?
                    ORDER BY er.strength DESC
                """
                params = [current_entity_id, current_entity_id]

            relationships = await db.query(query, params)

            for rel in relationships:
                # Determine the other entity in the relationship
                other_entity_id = (
                    rel['target_entity_id']
                    if rel['source_entity_id'] == current_entity_id
                    else rel['source_entity_id']
                )

                # Add to results if not starting entity
                if current_entity_id != entity_id:
                    related_entities.append({
                        'entity_id': current_entity_id,
                        'relationship': rel,
                        'distance': current_depth
                    })

                # Add to queue for next level
                if current_depth < depth:
                    queue.append((other_entity_id, current_depth + 1))

        return related_entities

    @classmethod
    async def get_community(cls, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the community this entity belongs to.

        Returns the lowest-level (most specific) community containing this entity.
        """
        db = get_database()

        query = """
            SELECT * FROM entity_communities
            WHERE entity_ids LIKE ?
            ORDER BY level DESC, created DESC
            LIMIT 1
        """
        params = [f'%"{entity_id}"%']

        results = await db.query(query, params)

        if not results:
            return None

        community = results[0]
        community['entity_ids'] = json.loads(community['entity_ids'])
        if community['metadata']:
            community['metadata'] = json.loads(community['metadata'])

        return community

    @classmethod
    async def search(
        cls,
        query: str,
        entity_types: Optional[List[str]] = None,
        source_id: Optional[str] = None,
        limit: int = 50
    ) -> List['Entity']:
        """
        Search entities by name and description.

        Args:
            query: Search query (fuzzy match on name and description)
            entity_types: Optional filter by entity types
            source_id: Optional filter by source
            limit: Maximum results to return
        """
        db = get_database()

        conditions = ["(LOWER(name) LIKE LOWER(?) OR LOWER(description) LIKE LOWER(?))"]
        params = [f"%{query}%", f"%{query}%"]

        if entity_types:
            placeholders = ','.join('?' * len(entity_types))
            conditions.append(f"entity_type IN ({placeholders})")
            params.extend(entity_types)

        if source_id:
            conditions.append("source_id = ?")
            params.append(source_id)

        where_clause = " AND ".join(conditions)
        sql = f"""
            SELECT * FROM {cls.table_name}
            WHERE {where_clause}
            ORDER BY
                CASE WHEN LOWER(name) = LOWER(?) THEN 0 ELSE 1 END,
                name
            LIMIT ?
        """
        params.append(query)
        params.append(limit)

        results = await db.query(sql, params)
        return [cls(**row) for row in results]

    @classmethod
    async def merge_entities(cls, entity_ids: List[str], keep_entity_id: str) -> str:
        """
        Merge multiple entities into one.

        Updates all relationships to point to the kept entity and deletes the others.

        Args:
            entity_ids: List of entity IDs to merge
            keep_entity_id: The entity ID to keep

        Returns:
            The kept entity ID
        """
        db = get_database()

        # Update relationships to use kept entity
        for entity_id in entity_ids:
            if entity_id == keep_entity_id:
                continue

            # Update source entity references
            await db.query(
                "UPDATE entity_relationships SET source_entity_id = ? WHERE source_entity_id = ?",
                [keep_entity_id, entity_id]
            )

            # Update target entity references
            await db.query(
                "UPDATE entity_relationships SET target_entity_id = ? WHERE target_entity_id = ?",
                [keep_entity_id, entity_id]
            )

            # Delete the merged entity
            await db.query(f"DELETE FROM {cls.table_name} WHERE id = ?", [entity_id])

        # Update kept entity's metadata to include merge info
        kept_entity = await cls.get(keep_entity_id)
        if kept_entity:
            metadata = json.loads(kept_entity.metadata) if kept_entity.metadata else {}
            metadata['merged_from'] = [eid for eid in entity_ids if eid != keep_entity_id]
            metadata['merge_count'] = len(metadata['merged_from'])

            await db.query(
                f"UPDATE {cls.table_name} SET metadata = ?, updated = CURRENT_TIMESTAMP WHERE id = ?",
                [json.dumps(metadata), keep_entity_id]
            )

        return keep_entity_id


class EntityRelationship(ObjectModel):
    """
    Directed relationship between two entities.

    Represents edges in the entity knowledge graph.
    """

    _table_name: ClassVar[str] = "entity_relationships"

    # Model fields
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    context: Optional[str] = None
    chunk_id: Optional[str] = None
    strength: float = 0.5
    metadata: Optional[str] = None

    @classmethod
    async def get_by_entity(
        cls,
        entity_id: str,
        direction: str = "both",
        relationship_types: Optional[List[str]] = None,
        min_strength: float = 0.0
    ) -> List['EntityRelationship']:
        """
        Get relationships for an entity.

        Args:
            entity_id: Entity ID
            direction: "outgoing", "incoming", or "both"
            relationship_types: Optional filter for relationship types
            min_strength: Minimum relationship strength (0.0-1.0)
        """
        db = get_database()

        conditions = []
        params = []

        if direction == "outgoing":
            conditions.append("source_entity_id = ?")
            params.append(entity_id)
        elif direction == "incoming":
            conditions.append("target_entity_id = ?")
            params.append(entity_id)
        else:  # both
            conditions.append("(source_entity_id = ? OR target_entity_id = ?)")
            params.extend([entity_id, entity_id])

        if relationship_types:
            placeholders = ','.join('?' * len(relationship_types))
            conditions.append(f"relationship_type IN ({placeholders})")
            params.extend(relationship_types)

        conditions.append("strength >= ?")
        params.append(min_strength)

        where_clause = " AND ".join(conditions)
        query = f"""
            SELECT * FROM {cls.table_name}
            WHERE {where_clause}
            ORDER BY strength DESC, created DESC
        """

        results = await db.query(query, params)
        return [cls(**row) for row in results]

    @classmethod
    async def get_path(
        cls,
        source_entity_id: str,
        target_entity_id: str,
        max_depth: int = 5
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Find shortest path between two entities using Dijkstra's algorithm.

        Args:
            source_entity_id: Starting entity ID
            target_entity_id: Destination entity ID
            max_depth: Maximum path length to search

        Returns:
            List of edges forming the shortest path, or None if no path exists
        """
        db = get_database()

        # Get all relationships (we'll use them as graph edges)
        query = "SELECT * FROM entity_relationships"
        relationships = await db.query(query, [])

        # Build adjacency list (undirected graph)
        graph = {}
        for rel in relationships:
            source = rel['source_entity_id']
            target = rel['target_entity_id']
            weight = 1.0 / (rel['strength'] + 0.01)  # Inverse of strength (lower is better)

            if source not in graph:
                graph[source] = []
            if target not in graph:
                graph[target] = []

            graph[source].append({'entity': target, 'weight': weight, 'relationship': rel})
            graph[target].append({'entity': source, 'weight': weight, 'relationship': rel})

        # Dijkstra's algorithm
        import heapq

        distances = {source_entity_id: 0}
        previous = {source_entity_id: None}
        pq = [(0, source_entity_id)]
        visited = set()

        while pq:
            current_dist, current_entity = heapq.heappop(pq)

            if current_entity in visited:
                continue

            visited.add(current_entity)

            if current_entity == target_entity_id:
                # Reconstruct path
                path = []
                entity = target_entity_id
                while previous[entity] is not None:
                    prev_entity, relationship = previous[entity]
                    path.insert(0, relationship)
                    entity = prev_entity
                return path if len(path) <= max_depth else None

            if current_entity not in graph:
                continue

            for neighbor in graph[current_entity]:
                neighbor_entity = neighbor['entity']
                new_dist = current_dist + neighbor['weight']

                if neighbor_entity not in distances or new_dist < distances[neighbor_entity]:
                    distances[neighbor_entity] = new_dist
                    previous[neighbor_entity] = (current_entity, neighbor['relationship'])
                    heapq.heappush(pq, (new_dist, neighbor_entity))

        return None  # No path found

    @classmethod
    async def get_all_types(cls) -> List[str]:
        """Get all unique relationship types in the database."""
        db = get_database()

        query = f"SELECT DISTINCT relationship_type FROM {cls.table_name} ORDER BY relationship_type"
        results = await db.query(query, [])

        return [row['relationship_type'] for row in results]


class Community(ObjectModel):
    """
    Community of related entities detected via clustering algorithms.

    Represents thematic clusters in the entity knowledge graph.
    """

    _table_name: ClassVar[str] = "entity_communities"

    # Model fields
    name: Optional[str] = None
    description: Optional[str] = None
    level: int = 0
    parent_community_id: Optional[str] = None
    entity_ids: str  # JSON array
    metadata: Optional[str] = None

    @classmethod
    async def get_hierarchical(cls, max_level: Optional[int] = None) -> Dict[int, List['Community']]:
        """
        Get communities organized by hierarchy level.

        Args:
            max_level: Optional maximum level to retrieve

        Returns:
            Dictionary mapping level -> list of communities
        """
        db = get_database()

        if max_level is not None:
            query = f"SELECT * FROM {cls.table_name} WHERE level <= ? ORDER BY level, created DESC"
            params = [max_level]
        else:
            query = f"SELECT * FROM {cls.table_name} ORDER BY level, created DESC"
            params = []

        results = await db.query(query, params)
        communities = [cls(**row) for row in results]

        # Organize by level
        hierarchy = {}
        for community in communities:
            level = community.level
            if level not in hierarchy:
                hierarchy[level] = []
            hierarchy[level].append(community)

        return hierarchy

    @classmethod
    async def get_by_entity(cls, entity_id: str) -> List['Community']:
        """Get all communities containing a specific entity."""
        db = get_database()

        query = f"""
            SELECT * FROM {cls.table_name}
            WHERE entity_ids LIKE ?
            ORDER BY level DESC, created DESC
        """
        params = [f'%"{entity_id}"%']

        results = await db.query(query, params)
        return [cls(**row) for row in results]

    @classmethod
    async def get_entities(cls, community_id: str) -> List[Entity]:
        """Get all entities in a community."""
        community = await cls.get(community_id)
        if not community:
            return []

        entity_ids = json.loads(community.entity_ids)

        if not entity_ids:
            return []

        db = get_database()
        placeholders = ','.join('?' * len(entity_ids))
        query = f"SELECT * FROM entities WHERE id IN ({placeholders})"

        results = await db.query(query, entity_ids)
        return [Entity(**row) for row in results]
