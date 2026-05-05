"""
Search Tools for Deep Agents

Wraps existing SearchService with all 4 search strategies
as LangChain tools for Deep Agent usage.
"""

from langchain.tools import BaseTool
from pydantic import Field
from typing import List, Dict, Any, Literal, Optional
import json
import logging

logger = logging.getLogger(__name__)


class NotebookSearchTool(BaseTool):
    """
    Search notebook sources using multiple strategies.

    Integrates with existing SearchService to provide keyword, vector,
    hybrid, and agentic RAG search capabilities.

    This tool wraps the existing SearchService without modifying it,
    maintaining full backward compatibility.
    """

    name: str = "search_notebook"
    description: str = """Search across notebook sources using advanced search strategies.

Use this tool when you need to find information in the notebook's sources.

Available strategies:
- keyword: Fast full-text search with BM25 ranking (best for exact matches)
- vector: Semantic similarity search using embeddings (best for conceptual matches)
- hybrid: Combines keyword + vector with RRF fusion (RECOMMENDED - balanced approach)
- agentic_rag: Multi-step LLM-powered search with query decomposition (best for complex queries)

Args:
    query (str): Search query
    strategy (str): Search strategy to use (default: hybrid)
    limit (int): Maximum results to return (default: 10)

Returns:
    JSON string with search results including content, scores, and source metadata.

Example:
    search_notebook(query="What are the main themes?", strategy="hybrid", limit=5)
"""

    notebook_id: str = Field(description="Notebook ID to search within")
    session_id: Optional[str] = Field(default=None, description="Session ID for context")

    class Config:
        arbitrary_types_allowed = True

    def _run(
        self,
        query: str,
        strategy: Literal["keyword", "vector", "hybrid", "agentic_rag"] = "hybrid",
        limit: int = 10
    ) -> str:
        """Sync not supported"""
        raise NotImplementedError("Use async version (_arun)")

    async def _arun(
        self,
        query: str,
        strategy: Literal["keyword", "vector", "hybrid", "agentic_rag"] = "hybrid",
        limit: int = 10
    ) -> str:
        """
        Execute search using specified strategy.

        Args:
            query: Search query
            strategy: Search strategy to use (default: hybrid)
            limit: Maximum results (default: 10)

        Returns:
            JSON string with search results
        """
        try:
            logger.info(
                f"[SearchTool] Searching notebook {self.notebook_id} "
                f"with strategy={strategy}, query='{query[:50]}...'"
            )

            # Get database and create search service
            from open_notebook.config import get_database
            from api.services.search_service import SearchService
            from open_notebook.search.strategies import SearchFilters

            db = get_database()
            await db.connect()

            try:
                # Create search service instance
                search_svc = SearchService(database=db)

                # Get strategy instance
                strategy_impl = await search_svc.get_search_strategy(strategy)

                # Create filters for this notebook
                filters = SearchFilters(notebook_ids=[self.notebook_id])

                # Execute search
                results = await strategy_impl.search(
                    query=query,
                    filters=filters,
                    limit=limit
                )

                # Format results
                formatted_results = []
                for idx, result in enumerate(results, 1):
                    formatted_results.append({
                        "rank": idx,
                        "source_id": result.source_id,
                        "source_name": result.metadata.get("source_name", "Unknown"),
                        "content": result.content[:500],  # Truncate for context
                        "score": round(result.score, 4),
                        "strategy": strategy
                    })

                logger.info(f"[SearchTool] Found {len(formatted_results)} results")

                return json.dumps({
                    "success": True,
                    "query": query,
                    "strategy": strategy,
                    "total_results": len(formatted_results),
                    "results": formatted_results
                }, indent=2)

            finally:
                await db.disconnect()

        except Exception as e:
            logger.error(f"[SearchTool] Search failed: {e}", exc_info=True)
            return json.dumps({
                "success": False,
                "error": str(e),
                "query": query,
                "strategy": strategy
            })
