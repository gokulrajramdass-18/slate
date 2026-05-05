"""
Comprehensive Tests for Entity Extraction Service

Tests entity and relationship extraction, deduplication, and merging.
"""

import pytest
import json
from unittest.mock import AsyncMock, Mock, patch

from api.services.entity_extraction_service import EntityExtractionService
from open_notebook.domain.entity import Entity


@pytest.mark.asyncio
class TestEntityExtractionService:
    """Test suite for EntityExtractionService"""

    async def test_extract_entities_from_chunk_success(self):
        """Test successful entity extraction from text chunk"""
        service = EntityExtractionService(model="gpt-4o-mini")

        mock_response = Mock()
        mock_response.content = """{
  "entities": [
    {"name": "John Smith", "type": "person", "description": "Research scientist at MIT"},
    {"name": "MIT", "type": "organization", "description": "Massachusetts Institute of Technology"},
    {"name": "Boston", "type": "location", "description": "City in Massachusetts"}
  ],
  "relationships": [
    {"source": "John Smith", "target": "MIT", "type": "works_for", "context": "John Smith works at MIT"},
    {"source": "MIT", "target": "Boston", "type": "located_in", "context": "MIT is located in Boston"}
  ]
}"""

        with patch('api.services.entity_extraction_service.ChatLiteLLM') as mock_chat:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_chat.return_value = mock_llm

            result = await service.extract_entities_from_chunk(
                chunk_id="test-chunk-1",
                chunk_text="John Smith works at MIT in Boston.",
                source_id="test-source-1"
            )

        assert len(result["entities"]) == 3
        assert len(result["relationships"]) == 2

        # Check entity names are normalized
        entity_names = [e["name"] for e in result["entities"]]
        assert "John Smith" in entity_names
        assert "Mit" in entity_names
        assert "Boston" in entity_names

        # Check relationships
        rel_types = [r["relationship_type"] for r in result["relationships"]]
        assert "works_for" in rel_types
        assert "located_in" in rel_types

    async def test_extract_entities_no_llm_available(self):
        """Test extraction when LLM is not available"""
        service = EntityExtractionService(model=None)

        with patch('api.services.entity_extraction_service.LANGCHAIN_AVAILABLE', False):
            result = await service.extract_entities_from_chunk(
                chunk_id="test-chunk-1",
                chunk_text="Test text",
                source_id="test-source-1"
            )

        assert result["entities"] == []
        assert result["relationships"] == []

    async def test_deduplication_merges_identical_names(self):
        """Test entity deduplication merges entities with identical names"""
        service = EntityExtractionService()

        entities = [
            {"id": "1", "name": "John Smith", "entity_type": "person", "metadata": '{"mentions": 1}'},
            {"id": "2", "name": "John Smith", "entity_type": "person", "metadata": '{"mentions": 1}'},
            {"id": "3", "name": "MIT", "entity_type": "organization", "metadata": '{"mentions": 1}'}
        ]

        result = await service._deduplicate_entities(entities)

        assert len(result["entities"]) == 2
        assert "2" in result["mapping"]
        assert result["mapping"]["2"] == "1"

        # Check mentions count updated
        john_smith = next(e for e in result["entities"] if e["name"] == "John Smith")
        metadata = json.loads(john_smith["metadata"])
        assert metadata["mentions"] == 2

    async def test_name_normalization(self):
        """Test entity name normalization to title case"""
        service = EntityExtractionService()

        assert service._normalize_entity_name("john smith") == "John Smith"
        assert service._normalize_entity_name("JOHN SMITH") == "John Smith"
        assert service._normalize_entity_name("  john   smith  ") == "John Smith"
        assert service._normalize_entity_name("mIt") == "Mit"

    async def test_extract_from_chunk_handles_invalid_json(self):
        """Test extraction handles invalid JSON response from LLM"""
        service = EntityExtractionService(model="gpt-4o-mini")

        mock_response = Mock()
        mock_response.content = "This is not valid JSON"

        with patch('api.services.entity_extraction_service.ChatLiteLLM') as mock_chat:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_chat.return_value = mock_llm

            result = await service.extract_entities_from_chunk(
                chunk_id="test-chunk-1",
                chunk_text="Test text",
                source_id="test-source-1"
            )

        assert result["entities"] == []
        assert result["relationships"] == []

    async def test_extract_from_chunk_strips_markdown(self):
        """Test extraction strips markdown code blocks from LLM response"""
        service = EntityExtractionService(model="gpt-4o-mini")

        mock_response = Mock()
        mock_response.content = """```json
{
  "entities": [{"name": "Test", "type": "person", "description": "Test entity"}],
  "relationships": []
}
```"""

        with patch('api.services.entity_extraction_service.ChatLiteLLM') as mock_chat:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_chat.return_value = mock_llm

            result = await service.extract_entities_from_chunk(
                chunk_id="test-chunk-1",
                chunk_text="Test text",
                source_id="test-source-1"
            )

        assert len(result["entities"]) == 1
        assert result["entities"][0]["name"] == "Test"

    async def test_max_entities_per_chunk_limit(self):
        """Test extraction respects max entities per chunk limit"""
        service = EntityExtractionService(model="gpt-4o-mini", max_entities_per_chunk=2)

        # Create response with 5 entities
        entities = [
            {"name": f"Entity{i}", "type": "person", "description": f"Entity {i}"}
            for i in range(5)
        ]

        mock_response = Mock()
        mock_response.content = json.dumps({
            "entities": entities,
            "relationships": []
        })

        with patch('api.services.entity_extraction_service.ChatLiteLLM') as mock_chat:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_chat.return_value = mock_llm

            result = await service.extract_entities_from_chunk(
                chunk_id="test-chunk-1",
                chunk_text="Test text",
                source_id="test-source-1"
            )

        # Should only return first 2 entities
        assert len(result["entities"]) == 2

    async def test_relationships_only_created_for_existing_entities(self):
        """Test relationships only created when both entities exist in result"""
        service = EntityExtractionService(model="gpt-4o-mini")

        mock_response = Mock()
        mock_response.content = json.dumps({
            "entities": [
                {"name": "Entity A", "type": "person", "description": "Test"}
            ],
            "relationships": [
                {"source": "Entity A", "target": "Entity B", "type": "knows", "context": "test"}
            ]
        })

        with patch('api.services.entity_extraction_service.ChatLiteLLM') as mock_chat:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_chat.return_value = mock_llm

            result = await service.extract_entities_from_chunk(
                chunk_id="test-chunk-1",
                chunk_text="Test text",
                source_id="test-source-1"
            )

        # Relationship should be skipped since Entity B doesn't exist
        assert len(result["relationships"]) == 0

    async def test_entity_metadata_includes_required_fields(self):
        """Test extracted entities include required metadata fields"""
        service = EntityExtractionService(model="gpt-4o-mini")

        mock_response = Mock()
        mock_response.content = json.dumps({
            "entities": [{"name": "Test", "type": "person", "description": "Test entity"}],
            "relationships": []
        })

        with patch('api.services.entity_extraction_service.ChatLiteLLM') as mock_chat:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_chat.return_value = mock_llm

            result = await service.extract_entities_from_chunk(
                chunk_id="test-chunk-1",
                chunk_text="Test text",
                source_id="test-source-1"
            )

        entity = result["entities"][0]
        assert entity["id"] is not None
        assert entity["source_id"] == "test-source-1"
        assert entity["chunk_id"] == "test-chunk-1"

        metadata = json.loads(entity["metadata"])
        assert "mentions" in metadata
        assert "first_seen" in metadata
        assert "confidence" in metadata

    async def test_relationship_metadata_includes_required_fields(self):
        """Test extracted relationships include required metadata fields"""
        service = EntityExtractionService(model="gpt-4o-mini")

        mock_response = Mock()
        mock_response.content = json.dumps({
            "entities": [
                {"name": "A", "type": "person", "description": "Test"},
                {"name": "B", "type": "person", "description": "Test"}
            ],
            "relationships": [
                {"source": "A", "target": "B", "type": "knows", "context": "test"}
            ]
        })

        with patch('api.services.entity_extraction_service.ChatLiteLLM') as mock_chat:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_chat.return_value = mock_llm

            result = await service.extract_entities_from_chunk(
                chunk_id="test-chunk-1",
                chunk_text="Test text",
                source_id="test-source-1"
            )

        rel = result["relationships"][0]
        assert rel["id"] is not None
        assert rel["chunk_id"] == "test-chunk-1"
        assert rel["strength"] == 0.5  # Default strength

        metadata = json.loads(rel["metadata"])
        assert "co_occurrence_count" in metadata
        assert "confidence" in metadata


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
