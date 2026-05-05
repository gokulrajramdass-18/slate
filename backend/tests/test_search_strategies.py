"""
Test Search Strategies

Unit tests for all search strategies and the search service.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from open_notebook.search.strategies import SearchResult, SearchFilters
from open_notebook.search.keyword import KeywordSearch
from open_notebook.search.vector import VectorSearch
from open_notebook.search.hybrid import HybridSearch
from open_notebook.search.agentic_rag import AgenticRAGSearch
from api.services.search_service import SearchService


# Mock Database for Testing

class MockDatabase:
    """Mock database for testing."""

    def __init__(self, db_type='sqlite'):
        self.db_type = db_type
        self.__class__.__name__ = f"{db_type.upper()}Database"

    async def query(self, sql: str, params: dict):
        """Mock query method."""
        # Return mock results based on query type
        if 'fts_sources' in sql.lower() or 'contains' in sql.lower():
            # Keyword search
            return [
                {
                    'source_id': 'source-1',
                    'title': 'Test Document',
                    'full_text': 'This is a test document with keyword search.',
                    'source_type': 'text',
                    'created': datetime.now().isoformat(),
                    'score': -2.5,
                    'snippet': 'This is a <mark>test</mark> document...'
                }
            ]
        elif 'source_embeddings' in sql.lower():
            # Vector search
            return [
                {
                    'chunk_id': 'chunk-1',
                    'source_id': 'source-1',
                    'content': 'This is a test chunk for vector search.',
                    'embedding': b'\x00\x01\x02' * 512,  # Mock embedding
                    'title': 'Test Document',
                    'source_type': 'text',
                    'created': datetime.now().isoformat()
                }
            ]
        elif 'search_config' in sql.lower():
            # Search config
            return [
                {
                    'config': '{"default_strategy": "hybrid", "strategies": {}}'
                }
            ]
        return []


# Fixtures

@pytest.fixture
def mock_db():
    """Provide mock database."""
    return MockDatabase('sqlite')


@pytest.fixture
def mock_hana_db():
    """Provide mock HANA database."""
    return MockDatabase('hana')


# Test SearchFilters

def test_search_filters_has_filters():
    """Test filters detection."""
    filters = SearchFilters()
    assert not filters.has_filters()

    filters = SearchFilters(notebook_ids=['nb-1'])
    assert filters.has_filters()


# Test KeywordSearch

@pytest.mark.asyncio
async def test_keyword_search_sqlite(mock_db):
    """Test keyword search with SQLite."""
    strategy = KeywordSearch(mock_db, {'title_boost': 2.0})

    assert strategy.name == 'keyword'
    assert 'BM25' in strategy.description

    results = await strategy.search('test query', limit=10)

    assert len(results) > 0
    assert results[0].source_id == 'source-1'
    assert results[0].score > 0


@pytest.mark.asyncio
async def test_keyword_search_empty_query(mock_db):
    """Test keyword search with empty query."""
    strategy = KeywordSearch(mock_db)
    results = await strategy.search('', limit=10)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_keyword_search_with_filters(mock_db):
    """Test keyword search with filters."""
    strategy = KeywordSearch(mock_db)
    filters = SearchFilters(
        notebook_ids=['nb-1'],
        source_types=['text']
    )

    results = await strategy.search('test', filters=filters, limit=10)
    # Should complete without error
    assert isinstance(results, list)


# Test VectorSearch

@pytest.mark.asyncio
async def test_vector_search_sqlite(mock_db):
    """Test vector search with SQLite."""
    # Mock embedding generation
    async def mock_generate_embedding(text, model):
        return [0.1] * 1536

    with patch('open_notebook.search.vector.VectorSearch._generate_embedding',
               new=mock_generate_embedding):
        strategy = VectorSearch(mock_db, {
            'threshold': 0.7,
            'embedding_model': MagicMock()
        })

        assert strategy.name == 'vector'
        assert 'semantic' in strategy.description.lower()

        results = await strategy.search('test query', limit=10)
        assert isinstance(results, list)


@pytest.mark.asyncio
async def test_vector_search_no_model(mock_db):
    """Test vector search without model raises error."""
    strategy = VectorSearch(mock_db, {})

    with pytest.raises(Exception):
        await strategy.search('test query', limit=10)


# Test HybridSearch

@pytest.mark.asyncio
async def test_hybrid_search(mock_db):
    """Test hybrid search."""
    # Mock sub-strategies
    keyword_results = [
        SearchResult(
            source_id='source-1',
            chunk_id=None,
            content='Keyword result',
            score=0.8,
            highlights=['test'],
            metadata={},
            strategy='keyword'
        )
    ]

    vector_results = [
        SearchResult(
            source_id='source-1',
            chunk_id='chunk-1',
            content='Vector result',
            score=0.9,
            highlights=[],
            metadata={},
            strategy='vector'
        ),
        SearchResult(
            source_id='source-2',
            chunk_id='chunk-2',
            content='Another vector result',
            score=0.7,
            highlights=[],
            metadata={},
            strategy='vector'
        )
    ]

    with patch('open_notebook.search.keyword.KeywordSearch.search',
               return_value=keyword_results), \
         patch('open_notebook.search.vector.VectorSearch.search',
               return_value=vector_results):

        strategy = HybridSearch(mock_db, {
            'keyword_weight': 0.4,
            'vector_weight': 0.6,
            'vector_config': {'embedding_model': MagicMock()}
        })

        assert strategy.name == 'hybrid'

        results = await strategy.search('test query', limit=10)

        # Should have merged results
        assert len(results) > 0
        # RRF score should be calculated
        assert all(r.score > 0 for r in results)


# Test AgenticRAGSearch

@pytest.mark.asyncio
async def test_agentic_rag_search():
    """Test agentic RAG search (basic smoke test)."""
    mock_db = MockDatabase('sqlite')

    # Mock LLM
    mock_llm = AsyncMock()
    mock_response = MagicMock()
    mock_response.content = '{"intent": "test", "entities": []}'
    mock_llm.ainvoke.return_value = mock_response

    strategy = AgenticRAGSearch(mock_db, {
        'llm_model': mock_llm,
        'vector_config': {'embedding_model': MagicMock()}
    })

    assert strategy.name == 'agentic_rag'
    assert 'LangGraph' in strategy.description

    # Note: Full test would require mocking the entire LangGraph workflow
    # This is a basic instantiation test


# Test SearchService

@pytest.mark.asyncio
async def test_search_service_get_strategy(mock_db):
    """Test getting a strategy from the service."""
    service = SearchService(mock_db)

    strategy = await service.get_search_strategy('keyword')
    assert isinstance(strategy, KeywordSearch)

    strategy = await service.get_search_strategy('vector')
    assert isinstance(strategy, VectorSearch)

    strategy = await service.get_search_strategy('hybrid')
    assert isinstance(strategy, HybridSearch)


@pytest.mark.asyncio
async def test_search_service_invalid_strategy(mock_db):
    """Test invalid strategy raises error."""
    service = SearchService(mock_db)

    with pytest.raises(ValueError):
        await service.get_search_strategy('invalid_strategy')


@pytest.mark.asyncio
async def test_search_service_list_strategies(mock_db):
    """Test listing available strategies."""
    service = SearchService(mock_db)

    strategies = await service.list_strategies()

    assert len(strategies) == 4
    assert any(s['name'] == 'keyword' for s in strategies)
    assert any(s['name'] == 'vector' for s in strategies)
    assert any(s['name'] == 'hybrid' for s in strategies)
    assert any(s['name'] == 'agentic_rag' for s in strategies)


@pytest.mark.asyncio
async def test_search_service_default_strategy(mock_db):
    """Test getting default strategy."""
    service = SearchService(mock_db)

    default = await service.get_default_strategy()
    assert default in ['keyword', 'vector', 'hybrid', 'agentic_rag']


@pytest.mark.asyncio
async def test_search_service_test_strategy(mock_db):
    """Test strategy testing."""
    service = SearchService(mock_db)

    result = await service.test_strategy('keyword', 'test query')

    assert 'success' in result
    assert result['strategy'] == 'keyword'
    assert result['query'] == 'test query'


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
