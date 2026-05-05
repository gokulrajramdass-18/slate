"""
Hybrid Search Strategy

Combines keyword and vector search using Reciprocal Rank Fusion (RRF).
Executes both strategies in parallel and merges results.
"""

import asyncio
from typing import List, Optional, Dict, Any
from collections import defaultdict
from open_notebook.search.strategies import (
    SearchStrategy,
    SearchResult,
    SearchFilters,
    SearchExecutionError
)
from open_notebook.search.keyword import KeywordSearch
from open_notebook.search.vector import VectorSearch


class HybridSearch(SearchStrategy):
    """
    Hybrid search combining keyword and vector strategies.

    Uses Reciprocal Rank Fusion (RRF) algorithm:
        score = sum(1 / (k + rank_i))
    where k=60 (standard constant) and rank_i is the rank in each strategy.

    Configuration options:
        - keyword_weight: Weight for keyword results (default: 0.4)
        - vector_weight: Weight for vector results (default: 0.6)
        - rrf_k: RRF constant k (default: 60)
        - keyword_config: Config passed to KeywordSearch
        - vector_config: Config passed to VectorSearch
    """

    @property
    def name(self) -> str:
        return "hybrid"

    @property
    def description(self) -> str:
        return "Combines keyword and vector search using Reciprocal Rank Fusion"

    async def search(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        limit: int = 10
    ) -> List[SearchResult]:
        """
        Execute hybrid search combining keyword and vector strategies.

        Args:
            query: Search query
            filters: Optional filters
            limit: Maximum results

        Returns:
            List of SearchResult with combined scores
        """
        if not query or not query.strip():
            return []

        # Get weights and constants
        keyword_weight = self.config.get('keyword_weight', 0.4)
        vector_weight = self.config.get('vector_weight', 0.6)
        rrf_k = self.config.get('rrf_k', 60)

        # Initialize sub-strategies
        keyword_config = self.config.get('keyword_config', {})
        vector_config = self.config.get('vector_config', {})

        keyword_search = KeywordSearch(self.database, keyword_config)
        vector_search = VectorSearch(self.database, vector_config)

        # Execute both searches in parallel
        # Request more results from each to have a better pool for merging
        search_limit = limit * 2

        try:
            keyword_results, vector_results = await asyncio.gather(
                keyword_search.search(query, filters, search_limit),
                vector_search.search(query, filters, search_limit),
                return_exceptions=True
            )

            # Handle exceptions
            keyword_error = None
            vector_error = None
            keyword_exception = False
            vector_exception = False

            if isinstance(keyword_results, Exception):
                keyword_exception = True
                keyword_error = str(keyword_results)
                print(f"Keyword search failed: {keyword_results}")
                import traceback
                traceback.print_exception(type(keyword_results), keyword_results, keyword_results.__traceback__)
                keyword_results = []
            if isinstance(vector_results, Exception):
                vector_exception = True
                vector_error = str(vector_results)
                print(f"Vector search failed: {vector_results}")
                import traceback
                traceback.print_exception(type(vector_results), vector_results, vector_results.__traceback__)
                vector_results = []

            # If both raised exceptions (not just empty results), raise error
            if keyword_exception and vector_exception:
                error_msg = f"Both keyword and vector search failed. "
                if keyword_error:
                    error_msg += f"Keyword error: {keyword_error}. "
                if vector_error:
                    error_msg += f"Vector error: {vector_error}."
                raise SearchExecutionError(error_msg)

            # If both returned empty results (but didn't raise exceptions), that's ok
            if not keyword_results and not vector_results:
                print("Warning: Both searches returned empty results, returning empty list")
                return []

            # Apply RRF fusion
            merged_results = self._reciprocal_rank_fusion(
                keyword_results,
                vector_results,
                keyword_weight,
                vector_weight,
                rrf_k
            )

            # Limit results
            return merged_results[:limit]

        except Exception as e:
            raise SearchExecutionError(f"Hybrid search failed: {str(e)}")

    def _reciprocal_rank_fusion(
        self,
        keyword_results: List[SearchResult],
        vector_results: List[SearchResult],
        keyword_weight: float,
        vector_weight: float,
        k: int = 60
    ) -> List[SearchResult]:
        """
        Merge results using Reciprocal Rank Fusion.

        RRF formula: score = Σ(weight_i / (k + rank_i))

        Args:
            keyword_results: Results from keyword search
            vector_results: Results from vector search
            keyword_weight: Weight for keyword scores
            vector_weight: Weight for vector scores
            k: RRF constant (default: 60)

        Returns:
            Merged and deduplicated list of SearchResult
        """
        # Build rank maps: source_id -> rank (1-indexed)
        keyword_ranks = {
            result.source_id: idx + 1
            for idx, result in enumerate(keyword_results)
        }
        vector_ranks = {
            result.source_id: idx + 1
            for idx, result in enumerate(vector_results)
        }

        # Build result maps for easy lookup
        keyword_map = {r.source_id: r for r in keyword_results}
        vector_map = {r.source_id: r for r in vector_results}

        # Calculate RRF scores
        rrf_scores = defaultdict(float)
        all_source_ids = set(keyword_ranks.keys()) | set(vector_ranks.keys())

        for source_id in all_source_ids:
            score = 0.0

            # Add keyword contribution
            if source_id in keyword_ranks:
                score += keyword_weight / (k + keyword_ranks[source_id])

            # Add vector contribution
            if source_id in vector_ranks:
                score += vector_weight / (k + vector_ranks[source_id])

            rrf_scores[source_id] = score

        # Build merged results
        merged = []
        for source_id, rrf_score in rrf_scores.items():
            # Prefer vector result if available (has chunk_id), else keyword
            if source_id in vector_map:
                base_result = vector_map[source_id]
            else:
                base_result = keyword_map[source_id]

            # Create new result with RRF score
            merged_result = SearchResult(
                source_id=base_result.source_id,
                chunk_id=base_result.chunk_id,
                content=base_result.content,
                score=rrf_score,
                highlights=self._merge_highlights(
                    keyword_map.get(source_id),
                    vector_map.get(source_id)
                ),
                metadata={
                    **base_result.metadata,
                    'keyword_rank': keyword_ranks.get(source_id),
                    'vector_rank': vector_ranks.get(source_id),
                    'keyword_score': keyword_map[source_id].score if source_id in keyword_map else None,
                    'vector_score': vector_map[source_id].score if source_id in vector_map else None
                },
                strategy=self.name
            )
            merged.append(merged_result)

        # Sort by RRF score (descending)
        merged.sort(key=lambda x: x.score, reverse=True)

        return merged

    def _merge_highlights(
        self,
        keyword_result: Optional[SearchResult],
        vector_result: Optional[SearchResult]
    ) -> List[str]:
        """
        Merge highlights from keyword and vector results.

        Args:
            keyword_result: Result from keyword search
            vector_result: Result from vector search

        Returns:
            Combined list of highlights
        """
        highlights = []

        if keyword_result and keyword_result.highlights:
            highlights.extend(keyword_result.highlights)

        if vector_result and vector_result.highlights:
            highlights.extend(vector_result.highlights)

        # Deduplicate while preserving order
        seen = set()
        unique_highlights = []
        for h in highlights:
            if h not in seen:
                seen.add(h)
                unique_highlights.append(h)

        return unique_highlights[:10]  # Limit to top 10
