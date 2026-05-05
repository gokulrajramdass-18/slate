"""
Unified Search Service

Combines main search (sources) with bookmark search for comprehensive results.
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

from open_notebook.search.strategies import SearchFilters
from api.services.search_service import SearchService
from api.services.bookmark_embedding_service import get_bookmark_embedding_service


class UnifiedSearchService:
    """
    Unified search service that combines:
    1. Main search across all sources (keyword, vector, hybrid, agentic_rag)
    2. Bookmark search across user's bookmarked items

    Results are merged, deduplicated, and ranked by relevance.
    """

    def __init__(self, database, user_id: Optional[str] = None):
        """
        Initialize unified search service.

        Args:
            database: Database interface instance
            user_id: User ID for bookmark search (optional)
        """
        self.database = database
        self.user_id = user_id or "default_user"
        self.search_service = SearchService(database)

    async def search(
        self,
        query: str,
        strategy: str = "hybrid",
        filters: Optional[SearchFilters] = None,
        limit: int = 20,
        include_bookmarks: bool = True,
        bookmark_boost: float = 1.5,
        config_override: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute unified search combining main search and bookmarks.

        Args:
            query: Search query
            strategy: Main search strategy (keyword, vector, hybrid, agentic_rag)
            filters: Optional filters for main search
            limit: Maximum total results
            include_bookmarks: Whether to include bookmark search results
            bookmark_boost: Score multiplier for bookmarked items (default: 1.5x)
            config_override: Strategy config override

        Returns:
            Dict with:
                - results: List of unified search results
                - total_results: Total count
                - sources: Dict with counts by source (main_search, bookmarks)
                - metadata: Additional metadata
        """
        if not query or not query.strip():
            return {
                "results": [],
                "total_results": 0,
                "sources": {"main_search": 0, "bookmarks": 0},
                "metadata": {"query": query, "strategy": strategy}
            }

        # Execute searches in parallel
        tasks = []

        # 1. Main search
        main_search_task = self._execute_main_search(
            query, strategy, filters, limit * 2, config_override
        )
        tasks.append(main_search_task)

        # 2. Bookmark search (if enabled)
        if include_bookmarks:
            bookmark_search_task = self._execute_bookmark_search(
                query, limit
            )
            tasks.append(bookmark_search_task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle results
        main_results = results[0] if not isinstance(results[0], Exception) else []
        bookmark_results = results[1] if len(results) > 1 and not isinstance(results[1], Exception) else []

        # Log any errors
        if isinstance(results[0], Exception):
            print(f"Main search error: {results[0]}")
        if len(results) > 1 and isinstance(results[1], Exception):
            print(f"Bookmark search error: {results[1]}")

        # Merge and deduplicate results
        merged_results = self._merge_results(
            main_results,
            bookmark_results,
            bookmark_boost
        )

        # Limit final results
        final_results = merged_results[:limit]

        return {
            "results": final_results,
            "total_results": len(final_results),
            "sources": {
                "main_search": len(main_results),
                "bookmarks": len(bookmark_results)
            },
            "metadata": {
                "query": query,
                "strategy": strategy,
                "include_bookmarks": include_bookmarks,
                "bookmark_boost": bookmark_boost,
                "filters_applied": filters is not None if filters else False
            }
        }

    async def _execute_main_search(
        self,
        query: str,
        strategy: str,
        filters: Optional[SearchFilters],
        limit: int,
        config_override: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Execute main search across sources."""
        try:
            search_strategy = await self.search_service.get_search_strategy(
                strategy, config_override
            )

            results = await search_strategy.search(query, filters, limit)

            # Convert SearchResult objects to dicts with standardized format
            return [
                {
                    "id": r.source_id,
                    "entity_type": "source",
                    "entity_id": r.source_id,
                    "chunk_id": r.chunk_id,
                    "title": r.metadata.get("title", "Untitled"),
                    "content": r.content,
                    "source_type": r.metadata.get("source_type", "text"),
                    "score": r.score,
                    "highlights": r.highlights,
                    "metadata": r.metadata,
                    "strategy": r.strategy,
                    "result_source": "main_search",
                    "is_bookmarked": False,
                    "bookmark_id": None,
                    "custom_note": None,
                    "created": r.metadata.get("created")
                }
                for r in results
            ]
        except Exception as e:
            print(f"Main search failed: {e}")
            return []

    async def _execute_bookmark_search(
        self,
        query: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Execute bookmark search."""
        try:
            service = get_bookmark_embedding_service()
            results = await service.search_bookmarks(
                query=query,
                user_id=self.user_id,
                limit=limit,
                threshold=0.6  # Lower threshold for bookmarks
            )

            # Enrich and standardize bookmark results
            enriched_results = []
            for result in results:
                # Get entity details based on type
                entity_title = None
                entity_description = None
                source_type = None

                if result["entity_type"] == "source":
                    from open_notebook.database.repository import repo_query
                    rows = await repo_query(
                        "SELECT title, full_text, source_type FROM sources WHERE id = :id",
                        {"id": result["entity_id"]}
                    )
                    if rows:
                        entity_title = rows[0].get("title")
                        entity_description = rows[0].get("full_text", "")[:500]
                        source_type = rows[0].get("source_type")

                elif result["entity_type"] == "note":
                    from open_notebook.database.repository import repo_query
                    rows = await repo_query(
                        "SELECT title, content FROM notes WHERE id = :id",
                        {"id": result["entity_id"]}
                    )
                    if rows:
                        entity_title = rows[0].get("title")
                        entity_description = rows[0].get("content", "")[:500]
                        source_type = "note"

                elif result["entity_type"] == "notebook":
                    from open_notebook.database.repository import repo_query
                    rows = await repo_query(
                        "SELECT name, description FROM notebooks WHERE id = :id",
                        {"id": result["entity_id"]}
                    )
                    if rows:
                        entity_title = rows[0].get("name")
                        entity_description = rows[0].get("description")
                        source_type = "notebook"

                enriched_results.append({
                    "id": result["bookmark_id"],
                    "entity_type": result["entity_type"],
                    "entity_id": result["entity_id"],
                    "chunk_id": None,
                    "title": entity_title or "Untitled",
                    "content": result.get("content", "") or entity_description or "",
                    "source_type": source_type or result["entity_type"],
                    "score": result["similarity"],
                    "highlights": [],
                    "metadata": {
                        "title": entity_title,
                        "source_type": source_type,
                        "tags": result.get("tags"),
                        "category": result.get("category"),
                        "custom_note": result.get("custom_note"),
                        "reason": result.get("reason")
                    },
                    "strategy": "bookmark_semantic",
                    "result_source": "bookmarks",
                    "is_bookmarked": True,
                    "bookmark_id": result["bookmark_id"],
                    "custom_note": result.get("custom_note"),
                    "created": result.get("bookmarked_at")
                })

            return enriched_results

        except Exception as e:
            print(f"Bookmark search failed: {e}")
            return []

    def _merge_results(
        self,
        main_results: List[Dict[str, Any]],
        bookmark_results: List[Dict[str, Any]],
        bookmark_boost: float
    ) -> List[Dict[str, Any]]:
        """
        Merge and deduplicate results from both searches.

        Strategy:
        1. Boost bookmark scores by bookmark_boost factor
        2. Deduplicate by entity_id (prefer bookmark version if duplicate)
        3. Sort by final score (descending)

        Args:
            main_results: Results from main search
            bookmark_results: Results from bookmark search
            bookmark_boost: Score multiplier for bookmarks

        Returns:
            Merged and sorted list of results
        """
        # Build result map: entity_id -> result
        result_map: Dict[str, Dict[str, Any]] = {}

        # Add main search results
        for result in main_results:
            entity_id = result["entity_id"]
            result_map[entity_id] = result

        # Add bookmark results with boost and override main search
        for result in bookmark_results:
            entity_id = result["entity_id"]

            # Apply bookmark boost
            result["score"] = result["score"] * bookmark_boost
            result["metadata"]["bookmark_boosted"] = True
            result["metadata"]["original_score"] = result["score"] / bookmark_boost

            # Override if exists (prefer bookmark version)
            if entity_id in result_map:
                # Merge metadata from main search
                main_result = result_map[entity_id]
                result["metadata"]["also_in_main_search"] = True
                result["metadata"]["main_search_score"] = main_result["score"]
                result["metadata"]["main_search_strategy"] = main_result.get("strategy")

            result_map[entity_id] = result

        # Convert to list and sort by score
        merged = list(result_map.values())
        merged.sort(key=lambda x: x["score"], reverse=True)

        return merged


def get_unified_search_service(database, user_id: Optional[str] = None) -> UnifiedSearchService:
    """
    Factory function to get UnifiedSearchService instance.

    Args:
        database: Database interface
        user_id: User ID for bookmark search

    Returns:
        UnifiedSearchService instance
    """
    return UnifiedSearchService(database, user_id)
