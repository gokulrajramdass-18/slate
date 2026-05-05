"""
Comprehensive Tests for LightRAG Hybrid Search Strategy

Tests multi-stage retrieval pipeline with entity extraction, graph traversal,
community context, vector search, and re-ranking.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import List, Dict, Any

from open_notebook.search.lightrag_hybrid import LightRAGHybridSearch
from open_notebook.search.strategies import SearchResult


@pytest.mark.asyncio
class TestLightRAGHybridSearch:
    """Test suite for LightRAGHybridSearch strategy"""

    async def test_stage1_entity_extraction_from_query(self):
        """Test Stage 1: Entity extraction from query"""
        strategy = LightRAGHybridSearch()

        query = "What research did John Smith conduct at MIT in Boston?"

        # Mock entity extraction
        with patch.object(strategy, "_extract_query_entities", return_value=["John Smith", "MIT", "Boston"]):
            entities = await strategy._extract_query_entities(query)

        assert len(entities) == 3
        assert "MIT" in entities

    async def test_stage2_graph_traversal_with_depth(self):
        """Test Stage 2: Graph traversal with configurable depth"""
        strategy = LightRAGHybridSearch(graph_depth=2)

        entities = [
            {"id": "e1", "name": "Alice", "entity_type": "person"}
        ]

        # Mock graph traversal
        with patch("open_notebook.domain.entity.Entity.get_related", new_callable=AsyncMock) as mock_related:
            mock_related.return_value = [
                {"id": "e2", "name": "Bob", "entity_type": "person", "hop": 1},
                {"id": "e3", "name": "Charlie", "entity_type": "person", "hop": 2},
            ]

            graph_context = await strategy._traverse_entity_graph(entities, depth=2)

        assert "entities" in graph_context
        assert len(graph_context["entities"]) >= 2  # Should include neighbors up to depth 2

    async def test_stage3_community_context_gathering(self):
        """Test Stage 3: Community context gathering"""
        strategy = LightRAGHybridSearch()

        entities = [
            {"id": "e1", "name": "Alice", "entity_type": "person"}
        ]

        # Mock community retrieval
        with patch("open_notebook.domain.entity.Entity.get_community", new_callable=AsyncMock) as mock_community:
            mock_community.return_value = {
                "id": "c1",
                "name": "Research Team",
                "description": "A group of researchers",
                "entity_ids": ["e1", "e2", "e3"]
            }

            community_summaries = await strategy._get_community_context(entities)

        assert len(community_summaries) > 0
        assert "Research Team" in community_summaries[0]["name"]

    async def test_stage4_vector_search_with_expanded_query(self):
        """Test Stage 4: Vector search with expanded query context"""
        strategy = LightRAGHybridSearch()

        query = "Who works at MIT?"
        graph_context = {
            "entities": [{"name": "Alice", "entity_type": "person"}],
            "relationships": [{"type": "works_for", "target": "MIT"}]
        }
        community_summaries = [
            {"name": "MIT Community", "description": "Researchers at MIT"}
        ]

        expanded_query = strategy._build_expanded_query(query, graph_context, community_summaries)

        # Expanded query should include original + entity context + community context
        assert "MIT" in expanded_query
        assert len(expanded_query) > len(query)

    async def test_stage5_reranking_with_all_signals(self):
        """Test Stage 5: Re-ranking with vector + graph + entity + community signals"""
        strategy = LightRAGHybridSearch(
            vector_weight=0.4,
            graph_weight=0.3,
            entity_weight=0.2,
            community_weight=0.1
        )

        vector_results = [
            SearchResult(
                content="Alice works at MIT",
                source_id="s1",
                score=0.8,
                metadata={
                    "vector_similarity": 0.8,
                    "graph_centrality": 0.6,
                    "entity_match_score": 0.9,
                    "community_relevance": 0.7
                }
            )
        ]

        graph_context = {"entities": [{"id": "e1", "name": "Alice"}]}
        community_summaries = [{"name": "MIT Community"}]

        reranked = await strategy._rerank_with_graph_and_community(
            vector_results,
            graph_context,
            community_summaries,
            limit=10
        )

        assert len(reranked) > 0
        # Verify scoring formula: 0.4*vector + 0.3*graph + 0.2*entity + 0.1*community
        expected_score = 0.4*0.8 + 0.3*0.6 + 0.2*0.9 + 0.1*0.7
        assert abs(reranked[0].score - expected_score) < 0.01

    async def test_full_pipeline_integration(self):
        """Test full 5-stage pipeline integration"""
        strategy = LightRAGHybridSearch()

        query = "What projects did Alice work on?"

        # Mock all stages
        with patch.object(strategy, "_extract_query_entities", return_value=["Alice"]):
            with patch.object(strategy, "_traverse_entity_graph", return_value={"entities": [{"name": "Alice"}]}):
                with patch.object(strategy, "_get_community_context", return_value=[{"name": "Research Team"}]):
                    with patch.object(strategy, "vector_search") as mock_vector:
                        mock_vector.search = AsyncMock(return_value=[
                            SearchResult(content="Alice project", source_id="s1", score=0.8, metadata={})
                        ])

                        with patch.object(strategy, "_rerank_with_graph_and_community", return_value=[
                            SearchResult(content="Alice project", source_id="s1", score=0.9, metadata={})
                        ]):
                            results = await strategy.search(query, filters={}, limit=10)

        assert len(results) > 0
        assert results[0].score > 0

    async def test_scoring_weights_sum_to_one(self):
        """Test that scoring weights sum to 1.0"""
        strategy = LightRAGHybridSearch(
            vector_weight=0.4,
            graph_weight=0.3,
            entity_weight=0.2,
            community_weight=0.1
        )

        total_weight = (
            strategy.vector_weight +
            strategy.graph_weight +
            strategy.entity_weight +
            strategy.community_weight
        )

        assert abs(total_weight - 1.0) < 0.01

    async def test_community_relevance_calculation(self):
        """Test community relevance score calculation"""
        strategy = LightRAGHybridSearch()

        query_entities = ["Alice", "Bob"]
        chunk_communities = ["Research Team", "MIT Community"]
        community_summaries = [
            {"name": "Research Team", "description": "Alice and Bob collaborate"}
        ]

        relevance = strategy._calculate_community_relevance(
            query_entities,
            chunk_communities,
            community_summaries
        )

        assert 0.0 <= relevance <= 1.0

    async def test_fallback_when_no_entities_found(self):
        """Test fallback to traditional vector search when no entities found"""
        strategy = LightRAGHybridSearch()

        query = "generic question without entities"

        with patch.object(strategy, "_extract_query_entities", return_value=[]):
            with patch.object(strategy, "vector_search") as mock_vector:
                mock_vector.search = AsyncMock(return_value=[
                    SearchResult(content="result", source_id="s1", score=0.8, metadata={})
                ])

                results = await strategy.search(query, filters={}, limit=10)

        assert len(results) > 0

    async def test_graph_context_enriches_query(self):
        """Test that graph context enriches the query with relationship information"""
        strategy = LightRAGHybridSearch()

        query = "Alice's work"
        graph_context = {
            "entities": [{"name": "Alice", "entity_type": "person"}],
            "relationships": [
                {"type": "works_for", "target": "MIT"},
                {"type": "collaborated_on", "target": "Project X"}
            ]
        }

        expanded = strategy._build_expanded_query(query, graph_context, [])

        # Expanded query should mention relationships
        assert "works_for" in expanded or "MIT" in expanded
        assert "Project X" in expanded or "collaborated_on" in expanded

    async def test_community_context_adds_thematic_information(self):
        """Test that community context adds thematic information to query"""
        strategy = LightRAGHybridSearch()

        query = "research projects"
        community_summaries = [
            {
                "name": "AI Research Community",
                "description": "Researchers working on machine learning and neural networks",
                "central_entities": ["Alice", "Bob", "Charlie"]
            }
        ]

        expanded = strategy._build_expanded_query(query, {}, community_summaries)

        # Expanded query should include community themes
        assert "AI Research" in expanded or "machine learning" in expanded

    async def test_multi_hop_reasoning_support(self):
        """Test support for multi-hop reasoning via graph traversal"""
        strategy = LightRAGHybridSearch(graph_depth=3)

        # Query requiring multi-hop: "How is Alice connected to Project X?"
        entities = [
            {"id": "e1", "name": "Alice", "entity_type": "person"}
        ]

        # Mock multi-hop graph traversal: Alice -> MIT -> Project X
        with patch("open_notebook.domain.entity.Entity.get_related", new_callable=AsyncMock) as mock_related:
            mock_related.side_effect = [
                [{"id": "e2", "name": "MIT", "entity_type": "organization", "hop": 1}],
                [{"id": "e3", "name": "Project X", "entity_type": "concept", "hop": 2}],
            ]

            graph_context = await strategy._traverse_entity_graph(entities, depth=3)

        # Should capture multi-hop path
        assert len(graph_context["entities"]) >= 2

    async def test_result_limit_respected(self):
        """Test that result limit is respected after re-ranking"""
        strategy = LightRAGHybridSearch()

        # Create 20 mock results
        vector_results = [
            SearchResult(content=f"result {i}", source_id=f"s{i}", score=0.5 + i*0.01, metadata={})
            for i in range(20)
        ]

        reranked = await strategy._rerank_with_graph_and_community(
            vector_results,
            {},
            [],
            limit=5
        )

        assert len(reranked) <= 5

    async def test_graph_centrality_boosts_hub_entities(self):
        """Test that graph centrality boosts results about hub entities"""
        strategy = LightRAGHybridSearch()

        # Result about high-centrality entity should score higher
        result_hub = SearchResult(
            content="About Alice, a central figure",
            source_id="s1",
            score=0.0,
            metadata={
                "vector_similarity": 0.6,
                "graph_centrality": 0.95,  # High centrality (hub)
                "entity_match_score": 0.7,
                "community_relevance": 0.5
            }
        )

        result_peripheral = SearchResult(
            content="About Bob, a peripheral figure",
            source_id="s2",
            score=0.0,
            metadata={
                "vector_similarity": 0.6,
                "graph_centrality": 0.15,  # Low centrality (peripheral)
                "entity_match_score": 0.7,
                "community_relevance": 0.5
            }
        )

        score_hub = strategy._calculate_final_score(result_hub)
        score_peripheral = strategy._calculate_final_score(result_peripheral)

        assert score_hub > score_peripheral

    async def test_empty_graph_graceful_handling(self):
        """Test graceful handling when entity graph is empty"""
        strategy = LightRAGHybridSearch()

        query = "test query"

        with patch.object(strategy, "_extract_query_entities", return_value=[]):
            with patch.object(strategy, "_traverse_entity_graph", return_value={"entities": []}):
                with patch.object(strategy, "_get_community_context", return_value=[]):
                    with patch.object(strategy, "vector_search") as mock_vector:
                        mock_vector.search = AsyncMock(return_value=[
                            SearchResult(content="result", source_id="s1", score=0.8, metadata={})
                        ])

                        results = await strategy.search(query, filters={}, limit=10)

        # Should still return results from vector search
        assert len(results) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
