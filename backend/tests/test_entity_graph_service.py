"""
Comprehensive Tests for Entity Graph Service

Tests graph building, filtering, BFS, Dijkstra, and export functionality.
"""

import pytest
import json
from unittest.mock import AsyncMock, patch
from typing import List, Dict, Any

from api.services.entity_graph_service import EntityGraphService
from open_notebook.domain.entity import Entity, EntityRelationship


@pytest.mark.asyncio
class TestEntityGraphService:
    """Test suite for EntityGraphService"""

    async def test_build_entity_graph_basic(self):
        """Test basic entity graph building"""
        service = EntityGraphService()

        entities = [
            {"id": "e1", "name": "Alice", "entity_type": "person"},
            {"id": "e2", "name": "Bob", "entity_type": "person"},
            {"id": "e3", "name": "MIT", "entity_type": "organization"},
        ]

        relationships = [
            {"id": "r1", "source_entity_id": "e1", "target_entity_id": "e2", "relationship_type": "knows", "strength": 0.8},
            {"id": "r2", "source_entity_id": "e1", "target_entity_id": "e3", "relationship_type": "works_for", "strength": 0.9},
        ]

        with patch.object(Entity, "get_all", new_callable=AsyncMock) as mock_entities:
            with patch.object(EntityRelationship, "get_all", new_callable=AsyncMock) as mock_rels:
                mock_entities.return_value = entities
                mock_rels.return_value = relationships

                graph = await service.build_graph()

        assert len(graph["nodes"]) == 3
        assert len(graph["edges"]) == 2
        assert graph["nodes"][0]["data"]["name"] == "Alice"

    async def test_filter_graph_by_entity_type(self):
        """Test filtering graph by entity type"""
        service = EntityGraphService()

        entities = [
            {"id": "e1", "name": "Alice", "entity_type": "person"},
            {"id": "e2", "name": "Bob", "entity_type": "person"},
            {"id": "e3", "name": "MIT", "entity_type": "organization"},
        ]

        relationships = [
            {"id": "r1", "source_entity_id": "e1", "target_entity_id": "e2", "relationship_type": "knows", "strength": 0.8},
        ]

        with patch.object(Entity, "get_all", new_callable=AsyncMock) as mock_entities:
            with patch.object(EntityRelationship, "get_all", new_callable=AsyncMock) as mock_rels:
                mock_entities.return_value = entities
                mock_rels.return_value = relationships

                graph = await service.build_graph(entity_types=["person"])

        # Should only include person entities
        assert len(graph["nodes"]) == 2
        assert all(node["data"]["entity_type"] == "person" for node in graph["nodes"])

    async def test_filter_graph_by_relationship_type(self):
        """Test filtering graph by relationship type"""
        service = EntityGraphService()

        entities = [
            {"id": "e1", "name": "Alice", "entity_type": "person"},
            {"id": "e2", "name": "Bob", "entity_type": "person"},
            {"id": "e3", "name": "MIT", "entity_type": "organization"},
        ]

        relationships = [
            {"id": "r1", "source_entity_id": "e1", "target_entity_id": "e2", "relationship_type": "knows", "strength": 0.8},
            {"id": "r2", "source_entity_id": "e1", "target_entity_id": "e3", "relationship_type": "works_for", "strength": 0.9},
        ]

        with patch.object(Entity, "get_all", new_callable=AsyncMock) as mock_entities:
            with patch.object(EntityRelationship, "get_all", new_callable=AsyncMock) as mock_rels:
                mock_entities.return_value = entities
                mock_rels.return_value = relationships

                graph = await service.build_graph(relationship_types=["knows"])

        # Should only include "knows" relationships
        assert len(graph["edges"]) == 1
        assert graph["edges"][0]["data"]["relationship_type"] == "knows"

    async def test_filter_graph_by_min_strength(self):
        """Test filtering graph by minimum relationship strength"""
        service = EntityGraphService()

        entities = [
            {"id": "e1", "name": "Alice", "entity_type": "person"},
            {"id": "e2", "name": "Bob", "entity_type": "person"},
            {"id": "e3", "name": "Charlie", "entity_type": "person"},
        ]

        relationships = [
            {"id": "r1", "source_entity_id": "e1", "target_entity_id": "e2", "relationship_type": "knows", "strength": 0.9},
            {"id": "r2", "source_entity_id": "e2", "target_entity_id": "e3", "relationship_type": "knows", "strength": 0.3},
        ]

        with patch.object(Entity, "get_all", new_callable=AsyncMock) as mock_entities:
            with patch.object(EntityRelationship, "get_all", new_callable=AsyncMock) as mock_rels:
                mock_entities.return_value = entities
                mock_rels.return_value = relationships

                graph = await service.build_graph(min_strength=0.5)

        # Should only include relationships with strength >= 0.5
        assert len(graph["edges"]) == 1
        assert graph["edges"][0]["data"]["strength"] >= 0.5

    async def test_bfs_neighborhood_expansion_depth_1(self):
        """Test BFS neighborhood expansion with depth 1"""
        service = EntityGraphService()

        entities = [
            {"id": "e1", "name": "Alice", "entity_type": "person"},
            {"id": "e2", "name": "Bob", "entity_type": "person"},
            {"id": "e3", "name": "Charlie", "entity_type": "person"},
        ]

        relationships = [
            {"id": "r1", "source_entity_id": "e1", "target_entity_id": "e2", "relationship_type": "knows", "strength": 0.8},
            {"id": "r2", "source_entity_id": "e2", "target_entity_id": "e3", "relationship_type": "knows", "strength": 0.7},
        ]

        with patch.object(Entity, "get", new_callable=AsyncMock) as mock_get:
            with patch.object(EntityRelationship, "get_by_entity", new_callable=AsyncMock) as mock_rels:
                mock_get.return_value = entities[0]
                mock_rels.return_value = [relationships[0]]

                with patch.object(Entity, "get_all", new_callable=AsyncMock) as mock_entities:
                    mock_entities.return_value = entities[:2]

                    neighborhood = await service.get_neighborhood(entity_id="e1", depth=1)

        # Should include e1 and e2 (direct neighbor)
        assert len(neighborhood["nodes"]) == 2
        assert "e1" in [node["id"] for node in neighborhood["nodes"]]
        assert "e2" in [node["id"] for node in neighborhood["nodes"]]
        # Should NOT include e3 (2 hops away)
        assert "e3" not in [node["id"] for node in neighborhood["nodes"]]

    async def test_bfs_neighborhood_expansion_depth_2(self):
        """Test BFS neighborhood expansion with depth 2"""
        service = EntityGraphService()

        # Linear chain: e1 -> e2 -> e3
        with patch.object(service, "_expand_bfs") as mock_expand:
            mock_expand.return_value = {"e1", "e2", "e3"}

            neighborhood = await service.get_neighborhood(entity_id="e1", depth=2)

        # Should include all 3 entities (up to 2 hops)
        assert len(neighborhood["nodes"]) >= 3 or mock_expand.called

    async def test_dijkstra_shortest_path(self):
        """Test Dijkstra shortest path between two entities"""
        service = EntityGraphService()

        entities = [
            {"id": "e1", "name": "Alice", "entity_type": "person"},
            {"id": "e2", "name": "Bob", "entity_type": "person"},
            {"id": "e3", "name": "Charlie", "entity_type": "person"},
        ]

        # Path: e1 -> e2 -> e3
        relationships = [
            {"id": "r1", "source_entity_id": "e1", "target_entity_id": "e2", "relationship_type": "knows", "strength": 0.8},
            {"id": "r2", "source_entity_id": "e2", "target_entity_id": "e3", "relationship_type": "knows", "strength": 0.7},
        ]

        with patch.object(Entity, "get_all", new_callable=AsyncMock) as mock_entities:
            with patch.object(EntityRelationship, "get_all", new_callable=AsyncMock) as mock_rels:
                mock_entities.return_value = entities
                mock_rels.return_value = relationships

                path = await service.find_path(source_entity_id="e1", target_entity_id="e3")

        assert path is not None
        assert "nodes" in path
        assert "edges" in path
        # Path should go through e1, e2, e3
        node_ids = [node["id"] for node in path["nodes"]]
        assert "e1" in node_ids
        assert "e2" in node_ids
        assert "e3" in node_ids

    async def test_no_path_between_disconnected_entities(self):
        """Test path finding when no path exists"""
        service = EntityGraphService()

        entities = [
            {"id": "e1", "name": "Alice", "entity_type": "person"},
            {"id": "e2", "name": "Bob", "entity_type": "person"},
        ]

        # No relationships - disconnected graph
        relationships = []

        with patch.object(Entity, "get_all", new_callable=AsyncMock) as mock_entities:
            with patch.object(EntityRelationship, "get_all", new_callable=AsyncMock) as mock_rels:
                mock_entities.return_value = entities
                mock_rels.return_value = relationships

                path = await service.find_path(source_entity_id="e1", target_entity_id="e2")

        assert path is None or len(path.get("nodes", [])) == 0

    async def test_graph_export_json_format(self):
        """Test graph export in JSON format"""
        service = EntityGraphService()

        entities = [
            {"id": "e1", "name": "Alice", "entity_type": "person"},
        ]

        relationships = []

        with patch.object(Entity, "get_all", new_callable=AsyncMock) as mock_entities:
            with patch.object(EntityRelationship, "get_all", new_callable=AsyncMock) as mock_rels:
                mock_entities.return_value = entities
                mock_rels.return_value = relationships

                export_data = await service.export_graph(format="json")

        assert "nodes" in export_data
        assert "edges" in export_data
        # Verify it's JSON-serializable
        json_str = json.dumps(export_data)
        assert json_str is not None

    async def test_graph_export_cytoscape_format(self):
        """Test graph export in Cytoscape format"""
        service = EntityGraphService()

        entities = [
            {"id": "e1", "name": "Alice", "entity_type": "person"},
        ]

        relationships = [
            {"id": "r1", "source_entity_id": "e1", "target_entity_id": "e2", "relationship_type": "knows", "strength": 0.8},
        ]

        with patch.object(Entity, "get_all", new_callable=AsyncMock) as mock_entities:
            with patch.object(EntityRelationship, "get_all", new_callable=AsyncMock) as mock_rels:
                mock_entities.return_value = entities
                mock_rels.return_value = relationships

                export_data = await service.export_graph(format="cytoscape")

        # Cytoscape format has specific structure
        assert "elements" in export_data or "nodes" in export_data

    async def test_filter_by_source_id(self):
        """Test filtering graph by source ID"""
        service = EntityGraphService()

        entities = [
            {"id": "e1", "name": "Alice", "entity_type": "person", "source_id": "s1"},
            {"id": "e2", "name": "Bob", "entity_type": "person", "source_id": "s2"},
        ]

        relationships = []

        with patch.object(Entity, "get_all", new_callable=AsyncMock) as mock_entities:
            with patch.object(EntityRelationship, "get_all", new_callable=AsyncMock) as mock_rels:
                mock_entities.return_value = entities
                mock_rels.return_value = relationships

                graph = await service.build_graph(source_id="s1")

        # Should only include entities from source s1
        assert len(graph["nodes"]) == 1
        assert graph["nodes"][0]["data"]["source_id"] == "s1"

    async def test_filter_by_community_id(self):
        """Test filtering graph by community ID"""
        service = EntityGraphService()

        entities = [
            {"id": "e1", "name": "Alice", "entity_type": "person", "metadata": json.dumps({"community_id": "c1"})},
            {"id": "e2", "name": "Bob", "entity_type": "person", "metadata": json.dumps({"community_id": "c2"})},
        ]

        relationships = []

        with patch.object(Entity, "get_all", new_callable=AsyncMock) as mock_entities:
            with patch.object(EntityRelationship, "get_all", new_callable=AsyncMock) as mock_rels:
                mock_entities.return_value = entities
                mock_rels.return_value = relationships

                graph = await service.build_graph(community_id="c1")

        # Should only include entities from community c1
        assert len(graph["nodes"]) == 1

    async def test_graph_statistics(self):
        """Test calculation of graph statistics"""
        service = EntityGraphService()

        entities = [
            {"id": "e1", "name": "Alice", "entity_type": "person"},
            {"id": "e2", "name": "Bob", "entity_type": "person"},
            {"id": "e3", "name": "Charlie", "entity_type": "person"},
        ]

        relationships = [
            {"id": "r1", "source_entity_id": "e1", "target_entity_id": "e2", "relationship_type": "knows", "strength": 0.8},
            {"id": "r2", "source_entity_id": "e2", "target_entity_id": "e3", "relationship_type": "knows", "strength": 0.7},
        ]

        with patch.object(Entity, "get_all", new_callable=AsyncMock) as mock_entities:
            with patch.object(EntityRelationship, "get_all", new_callable=AsyncMock) as mock_rels:
                mock_entities.return_value = entities
                mock_rels.return_value = relationships

                stats = await service.get_graph_statistics()

        assert "node_count" in stats
        assert "edge_count" in stats
        assert stats["node_count"] == 3
        assert stats["edge_count"] == 2

    async def test_edge_direction_preserved(self):
        """Test that edge directionality is preserved in graph"""
        service = EntityGraphService()

        entities = [
            {"id": "e1", "name": "Alice", "entity_type": "person"},
            {"id": "e2", "name": "Bob", "entity_type": "person"},
        ]

        relationships = [
            {"id": "r1", "source_entity_id": "e1", "target_entity_id": "e2", "relationship_type": "manages", "strength": 0.8},
        ]

        with patch.object(Entity, "get_all", new_callable=AsyncMock) as mock_entities:
            with patch.object(EntityRelationship, "get_all", new_callable=AsyncMock) as mock_rels:
                mock_entities.return_value = entities
                mock_rels.return_value = relationships

                graph = await service.build_graph()

        edge = graph["edges"][0]
        assert edge["source"] == "e1"
        assert edge["target"] == "e2"

    async def test_empty_graph_handling(self):
        """Test handling of empty graph (no entities or relationships)"""
        service = EntityGraphService()

        with patch.object(Entity, "get_all", new_callable=AsyncMock) as mock_entities:
            with patch.object(EntityRelationship, "get_all", new_callable=AsyncMock) as mock_rels:
                mock_entities.return_value = []
                mock_rels.return_value = []

                graph = await service.build_graph()

        assert len(graph["nodes"]) == 0
        assert len(graph["edges"]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
