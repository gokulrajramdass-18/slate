"""
Quick test for LightRAG entity extraction functionality.

Tests entity extraction, deduplication, and relationship mapping.
"""

import asyncio
import pytest
from api.services.entity_extraction_service import EntityExtractionService
from open_notebook.domain.entity import Entity, EntityRelationship
from unittest.mock import AsyncMock, Mock, patch


@pytest.mark.asyncio
async def test_entity_extraction_basic():
    """Test basic entity extraction from text."""

    service = EntityExtractionService(model="gpt-4o-mini")

    # Mock the LLM response
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

    # Patch ChatLiteLLM to return mock
    with patch('api.services.entity_extraction_service.ChatLiteLLM') as mock_chat_class:
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)
        mock_chat_class.return_value = mock_llm

        # Extract entities
        result = await service.extract_entities_from_chunk(
            chunk_id="test-chunk-1",
            chunk_text="John Smith works at MIT in Boston. He is a research scientist.",
            source_id="test-source-1"
        )

    # Verify results
    assert len(result["entities"]) == 3
    assert len(result["relationships"]) == 2

    # Check entity names are normalized
    entity_names = [e["name"] for e in result["entities"]]
    assert "John Smith" in entity_names
    assert "Mit" in entity_names  # Normalized to title case
    assert "Boston" in entity_names

    # Check relationships
    rel_types = [r["relationship_type"] for r in result["relationships"]]
    assert "works_for" in rel_types
    assert "located_in" in rel_types

    print("✅ Basic entity extraction test passed")


@pytest.mark.asyncio
async def test_entity_deduplication():
    """Test entity deduplication within same source."""

    service = EntityExtractionService()

    entities = [
        {"id": "1", "name": "John Smith", "entity_type": "person", "metadata": '{"mentions": 1}'},
        {"id": "2", "name": "John Smith", "entity_type": "person", "metadata": '{"mentions": 1}'},
        {"id": "3", "name": "MIT", "entity_type": "organization", "metadata": '{"mentions": 1}'}
    ]

    result = await service._deduplicate_entities(entities)

    # Should deduplicate John Smith
    assert len(result["entities"]) == 2

    # Check ID mapping
    assert "2" in result["mapping"]
    assert result["mapping"]["2"] == "1"  # Entity 2 mapped to entity 1

    # Check mentions count updated
    john_smith_entity = next(e for e in result["entities"] if e["name"] == "John Smith")
    metadata = json.loads(john_smith_entity["metadata"])
    assert metadata["mentions"] == 2

    print("✅ Entity deduplication test passed")


@pytest.mark.asyncio
async def test_entity_name_normalization():
    """Test entity name normalization."""

    service = EntityExtractionService()

    # Test various name formats
    assert service._normalize_entity_name("john smith") == "John Smith"
    assert service._normalize_entity_name("JOHN SMITH") == "John Smith"
    assert service._normalize_entity_name("  john   smith  ") == "John Smith"
    assert service._normalize_entity_name("mIt") == "Mit"

    print("✅ Entity name normalization test passed")


async def main():
    """Run all tests."""
    print("\n🧪 Running LightRAG Entity Extraction Tests\n")

    await test_entity_extraction_basic()
    await test_entity_deduplication()
    await test_entity_name_normalization()

    print("\n✅ All tests passed!\n")


if __name__ == "__main__":
    import json
    asyncio.run(main())
