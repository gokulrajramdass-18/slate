"""
Web Search Tool

Provides a LangChain-compatible tool for searching the web using DuckDuckGo.
No API key required - uses the ddgs library.
"""

import json
import time
from typing import Type, Optional

from langchain.tools import BaseTool
from pydantic import BaseModel, Field


class WebSearchInput(BaseModel):
    """Input schema for web search tool"""
    query: str = Field(
        description="Search query to find current information on the web"
    )
    max_results: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of search results to return (1-50)"
    )


class WebSearchTool(BaseTool):
    """
    Search the web for current information using DuckDuckGo.

    No API key required - uses DuckDuckGo's free search.
    """

    name: str = "web_search"
    description: str = (
        "Search the web for current information. "
        "Use this when you need up-to-date facts, news, or information "
        "that may not be in the notebook sources. "
        "Returns a list of search results with titles, URLs, and snippets."
    )
    args_schema: Type[BaseModel] = WebSearchInput

    session_id: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True

    async def _arun(self, query: str, max_results: int = 10) -> str:
        """Execute web search via DuckDuckGo."""
        start_time = time.time()

        try:
            # Import ddgs (formerly duckduckgo_search)
            try:
                from ddgs import DDGS
            except ImportError:
                return json.dumps({
                    "success": False,
                    "error": "ddgs not installed. Install with: pip install ddgs",
                    "results": [],
                    "count": 0,
                })

            # Perform search
            results = []
            with DDGS() as ddgs:
                search_results = list(ddgs.text(query, max_results=max_results))

                for item in search_results:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("href", ""),
                        "snippet": item.get("body", ""),
                        "score": 1.0,  # DuckDuckGo doesn't provide scores
                    })

            duration_ms = (time.time() - start_time) * 1000

            return json.dumps({
                "success": True,
                "results": results,
                "count": len(results),
                "duration_ms": round(duration_ms, 2),
            }, default=str)

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
                "results": [],
                "count": 0,
            })

    def _run(self, **kwargs) -> str:
        """Sync version not supported."""
        raise NotImplementedError("WebSearchTool only supports async execution")
