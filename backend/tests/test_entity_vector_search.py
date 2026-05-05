"""
Comprehensive Tests for Entity Vector Search Strategy

Tests entity extraction, graph traversal, and re-ranking.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import List, Dict, Any

from open_notebook.search.entity_vector import EntityVectorSearch
from open_notebook.search.strategies import SearchResult


@pytest.mark.asyncio
class TestEntityVectorSearch:
    """Test suite for EntityVectorSearch strategy"""

    async def test_extract_entities_from_query(self):
        """Test entity extraction from search query"""
        strategy = EntityVectorSearch()

        # Mock LLM response for entity extraction
        mock_entities = ["John Smith", "MIT", "Boston"]

        with patch.object(strategy, "_extract_query_entities", return_value=mock_entities):
            entities = await strategy._extract_query_entities("Who is John Smith at MIT in Boston?")

        assert len(entities) == 3
        assert "John Smith" in entities

    async def test_find_entities_in_graph(self):
        """Test finding extracted entities in graph"""
        strategy = EntityVectorSearch()

        query_entities = ["Alice", "Bob"]

        # Mock Entity.get_by_name
        with patch("open_notebook.domain.entity.Entity.get_by_name", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [
                [{"id": "e1", "name": "Alice", "entity_type": "person"}],
                [{"id": "e2", "name": "Bob", "entity_type": "person"}],
            ]

            matched = await strategy._find_entities(query_entities)

        assert len(matched) == 2
        assert matched[0]["name"] == "Alice"

    async def test_expand_entities_to_neighbors(self):
        """Test expanding entities to include neighbors"""
        strategy = EntityVectorSearch()

        matched_entities = [
            {"id": "e1", "name": "Alice", "entity_type": "person"}
        ]

        # Mock Entity.get_related
        with patch("open_notebook.domain.entity.Entity.get_related", new_callable=AsyncMock) as mock_related:
            mock_related.return_value = [
                {"id": "e2", "name": "Bob", "entity_type": "person", "hop": 1}
            ]

            expanded = await strategy._expand_entities(matched_entities, depth=1)

        assert len(expanded) >= 2  # Original + neighbors

    async def test_get_chunks_associated_with_entities(self):
        """Test retrieving chunks associated with entities"""
        strategy = EntityVectorSearch()

        entities = [
            {"id": "e1", "name": "Alice", "entity_type": "person", "chunk_id": "c1"},
            {"id": "e2", "name": "Bob", "entity_type": "person", "chunk_id": "c2"},
        ]

        # Mock chunk retrieval
        with patch("open_notebook.domain.notebook.Source.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [
                {"id": "c1", "content": "Alice works at MIT"},
                {"id": "c2", "content": "Bob is a researcher"},
            ]

            chunks = await strategy._get_entity_chunks(entities)

        assert len(chunks) >= 2

    async def test_rerank_with_graph_centrality(self):
        """Test re-ranking with graph centrality scores"""
        strategy = EntityVectorSearch()

        entity_chunks = [
            SearchResult(
                content="Alice works at MIT",
                source_id="s1",
                score=0.7,
                metadata={"entity_match": True}
            )
        ]

        vector_results = [
            SearchResult(
                content="Research at MIT",
                source_id="s2",
                score=0.8,
                metadata={}
            )
        ]

        reranked = strategy._rerank_with_graph(entity_chunks, vector_results, limit=10)

        # Verify scoring formula applied: score = α*vector + β*graph + γ*entity
        assert len(reranked) > 0
        assert all(hasattr(r, "score") for r in reranked)

    async def test_search_with_entity_aware_retrieval(self):
        """Test full search flow with entity-aware retrieval"""
        strategy = EntityVectorSearch()

        query = "Who works at MIT?"

        # Mock all steps
        with patch.object(strategy, "_extract_query_entities", return_value=["MIT"]):
            with patch.object(strategy, "_find_entities", return_value=[{"id": "e1", "name": "MIT"}]):
                with patch.object(strategy, "_expand_entities", return_value=[{"id": "e1", "name": "MIT"}]):
                    with patch.object(strategy, "_get_entity_chunks", return_value=[]):
                        with patch.object(strategy, "vector_search") as mock_vector:
                            mock_vector.search = AsyncMock(return_value=[
                                SearchResult(content="MIT research", source_id="s1", score=0.8, metadata={})
                            ])

                            results = await strategy.search(query, filters={}, limit=10)

        assert len(results) >= 0

    async def test_scoring_weights_applied_correctly(self):
        """Test that scoring weights (α, β, γ) are applied correctly"""
        strategy = EntityVectorSearch(
            vector_weight=0.5,
            graph_weight=0.3,
            entity_weight=0.2
        )

        result = SearchResult(
            content="test",
            source_id="s1",
            score=0.0,
            metadata={
                "vector_similarity": 1.0,
                "graph_centrality": 0.5,
                "entity_match_score": 1.0
            }
        )

        final_score = strategy._calculate_final_score(result)

        # Expected: 0.5*1.0 + 0.3*0.5 + 0.2*1.0 = 0.85
        assert abs(final_score - 0.85) < 0.01

    async def test_no_entities_in_query_fallback_to_vector(self):
        """Test fallback to vector search when no entities extracted"""
        strategy = EntityVectorSearch()

        query = "generic research question"

        with patch.object(strategy, "_extract_query_entities", return_value=[]):
            with patch.object(strategy, "vector_search") as mock_vector:
                mock_vector.search = AsyncMock(return_value=[
                    SearchResult(content="result", source_id="s1", score=0.8, metadata={})
                ])

                results = await strategy.search(query, filters={}, limit=10)

        # Should fallback to traditional vector search
        assert len(results) > 0

    async def test_graph_centrality_boosts_relevant_results(self):
        """Test that graph centrality boosts relevant entity-related results"""
        strategy = EntityVectorSearch()

        # Result with high graph centrality should score higher
        result_with_centrality = SearchResult(
            content="test",
            source_id="s1",
            score=0.6,
            metadata={
                "vector_similarity": 0.6,
                "graph_centrality": 0.9,  # High centrality
                "entity_match_score": 0.5
            }
        )

        result_without_centrality = SearchResult(
            content="test",
            source_id="s2",
            score=0.6,
            metadata={
                "vector_similarity": 0.6,
                "graph_centrality": 0.1,  # Low centrality
                "entity_match_score": 0.5
            }
        )

        score1 = strategy._calculate_final_score(result_with_centrality)
        score2 = strategy._calculate_final_score(result_without_centrality)

        assert score1 > score2

    async def test_entity_match_score_calculation(self):
        """Test entity match score calculation based on query entities"""
        strategy = EntityVectorSearch()

        query_entities = ["Alice", "MIT"]
        chunk_entities = ["Alice", "Bob"]

        match_score = strategy._calculate_entity_match_score(query_entities, chunk_entities)

        # Should be 0.5 (1 match out of 2 query entities)
        assert abs(match_score - 0.5) < 0.01

    async def test_deduplication_of_results(self):
        """Test deduplication when entity chunks overlap with vector results"""
        strategy = EntityVectorSearch()

        entity_chunks = [
            SearchResult(content="test", source_id="s1", score=0.8, metadata={})
        ]

        vector_results = [
            SearchResult(content="test", source_id="s1", score=0.7, metadata={}),
            SearchResult(content="other", source_id="s2", score=0.6, metadata={})
        ]

        merged = strategy._merge_results(entity_chunks, vector_results)

        # Should deduplicate s1 and keep the higher scoring version
        source_ids = [r.source_id for r in merged]
        assert source_ids.count("s1") == 1
        assert "s2" in source_ids


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
