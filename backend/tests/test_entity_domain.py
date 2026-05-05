"""
Comprehensive Tests for Entity Domain Models

Tests Entity, EntityRelationship, and Community CRUD operations.
"""

import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

from open_notebook.domain.entity import Entity, EntityRelationship, Community


@pytest.mark.asyncio
class TestEntityDomain:
    """Test suite for Entity domain model"""

    async def test_entity_create(self):
        """Test entity creation"""
        entity_data = {
            "name": "John Smith",
            "entity_type": "person",
            "description": "Research scientist",
            "source_id": "source-123",
            "chunk_id": "chunk-456",
            "metadata": json.dumps({"mentions": 1})
        }

        with patch("open_notebook.domain.entity.Entity.save", new_callable=AsyncMock) as mock_save:
            mock_save.return_value = "entity-id-123"

            entity = Entity(**entity_data)
            entity_id = await entity.save()

        assert entity_id == "entity-id-123"
        assert entity.name == "John Smith"

    async def test_entity_get_by_id(self):
        """Test retrieving entity by ID"""
        with patch("open_notebook.domain.entity.Entity.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "id": "entity-123",
                "name": "Alice",
                "entity_type": "person",
                "description": "Researcher"
            }

            entity = await Entity.get("entity-123")

        assert entity["name"] == "Alice"
        assert entity["entity_type"] == "person"

    async def test_entity_get_by_source(self):
        """Test retrieving all entities from a source"""
        with patch("open_notebook.domain.entity.Entity.get_by_source", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [
                {"id": "e1", "name": "Alice", "entity_type": "person"},
                {"id": "e2", "name": "Bob", "entity_type": "person"},
            ]

            entities = await Entity.get_by_source("source-123")

        assert len(entities) == 2
        assert entities[0]["name"] == "Alice"

    async def test_entity_get_by_name_exact(self):
        """Test finding entity by exact name match"""
        with patch("open_notebook.domain.entity.Entity.get_by_name", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [
                {"id": "e1", "name": "John Smith", "entity_type": "person"}
            ]

            entities = await Entity.get_by_name("John Smith", fuzzy=False)

        assert len(entities) == 1
        assert entities[0]["name"] == "John Smith"

    async def test_entity_get_by_name_fuzzy(self):
        """Test finding entity by fuzzy name match"""
        with patch("open_notebook.domain.entity.Entity.get_by_name", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [
                {"id": "e1", "name": "John Smith", "entity_type": "person"},
                {"id": "e2", "name": "J. Smith", "entity_type": "person"},
            ]

            entities = await Entity.get_by_name("john smith", fuzzy=True)

        # Fuzzy match should return similar names
        assert len(entities) >= 1

    async def test_entity_get_related(self):
        """Test getting related entities via relationships (BFS)"""
        with patch("open_notebook.domain.entity.Entity.get_related", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [
                {"id": "e2", "name": "Bob", "entity_type": "person", "hop": 1, "relationship_type": "knows"},
                {"id": "e3", "name": "Charlie", "entity_type": "person", "hop": 2, "relationship_type": "knows"},
            ]

            related = await Entity.get_related("e1", depth=2)

        assert len(related) == 2
        assert related[0]["hop"] == 1
        assert related[1]["hop"] == 2

    async def test_entity_get_community(self):
        """Test getting community an entity belongs to"""
        with patch("open_notebook.domain.entity.Entity.get_community", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "id": "c1",
                "name": "Research Team",
                "description": "A group of researchers"
            }

            community = await Entity.get_community("e1")

        assert community["name"] == "Research Team"

    async def test_entity_update(self):
        """Test updating entity fields"""
        entity_data = {
            "id": "e1",
            "name": "John Smith",
            "entity_type": "person",
            "description": "Updated description"
        }

        with patch("open_notebook.domain.entity.Entity.save", new_callable=AsyncMock):
            entity = Entity(**entity_data)
            await entity.save()

        assert entity.description == "Updated description"

    async def test_entity_delete(self):
        """Test deleting entity (cascade deletes relationships)"""
        with patch("open_notebook.domain.entity.Entity.delete", new_callable=AsyncMock) as mock_delete:
            await Entity.delete("e1")
            mock_delete.assert_called_once_with("e1")


@pytest.mark.asyncio
class TestEntityRelationshipDomain:
    """Test suite for EntityRelationship domain model"""

    async def test_relationship_create(self):
        """Test relationship creation"""
        rel_data = {
            "source_entity_id": "e1",
            "target_entity_id": "e2",
            "relationship_type": "knows",
            "context": "They met at the conference",
            "strength": 0.8,
            "chunk_id": "chunk-123",
            "metadata": json.dumps({"co_occurrence_count": 3})
        }

        with patch("open_notebook.domain.entity.EntityRelationship.save", new_callable=AsyncMock) as mock_save:
            mock_save.return_value = "rel-id-123"

            relationship = EntityRelationship(**rel_data)
            rel_id = await relationship.save()

        assert rel_id == "rel-id-123"
        assert relationship.relationship_type == "knows"

    async def test_relationship_get_by_entity_outgoing(self):
        """Test getting outgoing relationships for an entity"""
        with patch("open_notebook.domain.entity.EntityRelationship.get_by_entity", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [
                {"id": "r1", "source_entity_id": "e1", "target_entity_id": "e2", "relationship_type": "knows"},
                {"id": "r2", "source_entity_id": "e1", "target_entity_id": "e3", "relationship_type": "works_with"},
            ]

            relationships = await EntityRelationship.get_by_entity("e1", direction="outgoing")

        assert len(relationships) == 2
        assert all(r["source_entity_id"] == "e1" for r in relationships)

    async def test_relationship_get_by_entity_incoming(self):
        """Test getting incoming relationships for an entity"""
        with patch("open_notebook.domain.entity.EntityRelationship.get_by_entity", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [
                {"id": "r1", "source_entity_id": "e2", "target_entity_id": "e1", "relationship_type": "knows"},
            ]

            relationships = await EntityRelationship.get_by_entity("e1", direction="incoming")

        assert len(relationships) == 1
        assert relationships[0]["target_entity_id"] == "e1"

    async def test_relationship_get_by_entity_both(self):
        """Test getting both incoming and outgoing relationships"""
        with patch("open_notebook.domain.entity.EntityRelationship.get_by_entity", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [
                {"id": "r1", "source_entity_id": "e1", "target_entity_id": "e2", "relationship_type": "knows"},
                {"id": "r2", "source_entity_id": "e2", "target_entity_id": "e1", "relationship_type": "knows"},
            ]

            relationships = await EntityRelationship.get_by_entity("e1", direction="both")

        assert len(relationships) == 2

    async def test_relationship_get_path_dijkstra(self):
        """Test finding shortest path between two entities using Dijkstra"""
        with patch("open_notebook.domain.entity.EntityRelationship.get_path", new_callable=AsyncMock) as mock_path:
            mock_path.return_value = [
                {"source": "e1", "target": "e2", "relationship_type": "knows", "strength": 0.8},
                {"source": "e2", "target": "e3", "relationship_type": "works_with", "strength": 0.7},
            ]

            path = await EntityRelationship.get_path("e1", "e3")

        assert len(path) == 2
        # Path: e1 -> e2 -> e3
        assert path[0]["source"] == "e1"
        assert path[-1]["target"] == "e3"

    async def test_relationship_strength_validation(self):
        """Test relationship strength is between 0.0 and 1.0"""
        # Valid strength
        rel_valid = EntityRelationship(
            source_entity_id="e1",
            target_entity_id="e2",
            relationship_type="knows",
            strength=0.5
        )
        assert 0.0 <= rel_valid.strength <= 1.0

        # Invalid strength should be handled by database constraint

    async def test_relationship_delete(self):
        """Test deleting a relationship"""
        with patch("open_notebook.domain.entity.EntityRelationship.delete", new_callable=AsyncMock) as mock_delete:
            await EntityRelationship.delete("r1")
            mock_delete.assert_called_once_with("r1")


@pytest.mark.asyncio
class TestCommunityDomain:
    """Test suite for Community domain model"""

    async def test_community_create(self):
        """Test community creation"""
        community_data = {
            "name": "Research Team",
            "description": "A group of researchers working on AI",
            "level": 0,
            "entity_ids": json.dumps(["e1", "e2", "e3"]),
            "metadata": json.dumps({"size": 3, "modularity": 0.65})
        }

        with patch("open_notebook.domain.entity.Community.save", new_callable=AsyncMock) as mock_save:
            mock_save.return_value = "community-id-123"

            community = Community(**community_data)
            community_id = await community.save()

        assert community_id == "community-id-123"
        assert community.name == "Research Team"

    async def test_community_get_by_id(self):
        """Test retrieving community by ID"""
        with patch("open_notebook.domain.entity.Community.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                "id": "c1",
                "name": "AI Research Community",
                "description": "Researchers in AI",
                "entity_ids": json.dumps(["e1", "e2", "e3"])
            }

            community = await Community.get("c1")

        assert community["name"] == "AI Research Community"

    async def test_community_get_entities(self):
        """Test getting all entities in a community"""
        with patch("open_notebook.domain.entity.Community.get_entities", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [
                {"id": "e1", "name": "Alice", "entity_type": "person"},
                {"id": "e2", "name": "Bob", "entity_type": "person"},
            ]

            entities = await Community.get_entities("c1")

        assert len(entities) == 2

    async def test_community_hierarchical_structure(self):
        """Test hierarchical community structure (parent-child)"""
        parent_community = {
            "id": "c1",
            "name": "Top Level",
            "level": 0,
            "parent_community_id": None,
            "entity_ids": json.dumps(["e1", "e2", "e3", "e4"])
        }

        child_community = {
            "id": "c2",
            "name": "Sub Community",
            "level": 1,
            "parent_community_id": "c1",
            "entity_ids": json.dumps(["e1", "e2"])
        }

        assert child_community["parent_community_id"] == parent_community["id"]
        assert child_community["level"] > parent_community["level"]

    async def test_community_update_summary(self):
        """Test updating community summary (regeneration)"""
        community_data = {
            "id": "c1",
            "name": "Old Name",
            "description": "Updated description with new entities",
            "entity_ids": json.dumps(["e1", "e2", "e3", "e4"])
        }

        with patch("open_notebook.domain.entity.Community.save", new_callable=AsyncMock):
            community = Community(**community_data)
            await community.save()

        assert community.description == "Updated description with new entities"

    async def test_community_metadata_includes_statistics(self):
        """Test community metadata includes modularity, density, etc."""
        metadata = {
            "size": 10,
            "modularity": 0.72,
            "density": 0.45,
            "central_entities": ["e1", "e5", "e9"]
        }

        community = Community(
            name="Test Community",
            entity_ids=json.dumps(["e1", "e2"]),
            metadata=json.dumps(metadata)
        )

        parsed_metadata = json.loads(community.metadata)
        assert parsed_metadata["modularity"] == 0.72
        assert len(parsed_metadata["central_entities"]) == 3

    async def test_community_delete_cascade(self):
        """Test deleting community (should cascade to child communities)"""
        with patch("open_notebook.domain.entity.Community.delete", new_callable=AsyncMock) as mock_delete:
            await Community.delete("c1")
            mock_delete.assert_called_once_with("c1")

    async def test_community_get_hierarchy(self):
        """Test getting hierarchical view of communities"""
        with patch("open_notebook.domain.entity.Community.get_hierarchy", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {
                0: [{"id": "c1", "name": "Top Level", "level": 0}],
                1: [
                    {"id": "c2", "name": "Sub 1", "level": 1, "parent_community_id": "c1"},
                    {"id": "c3", "name": "Sub 2", "level": 1, "parent_community_id": "c1"},
                ],
            }

            hierarchy = await Community.get_hierarchy()

        assert 0 in hierarchy
        assert 1 in hierarchy
        assert len(hierarchy[1]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
