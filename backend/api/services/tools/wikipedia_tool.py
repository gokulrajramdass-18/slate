"""
Wikipedia Tool

Provides a LangChain-compatible tool for searching Wikipedia via its REST API.
"""

import json
from typing import Type, Optional

import httpx
from langchain.tools import BaseTool
from pydantic import BaseModel, Field


WIKIPEDIA_API = "https://en.wikipedia.org/api/rest_v1"
WIKIPEDIA_SEARCH = "https://en.wikipedia.org/w/api.php"


class WikipediaInput(BaseModel):
    """Input schema for Wikipedia tool"""
    query: str = Field(
        description="Search query for Wikipedia"
    )
    sentences: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of sentences to return in the summary (1-10)"
    )


class WikipediaTool(BaseTool):
    """
    Search Wikipedia and return a summary of the top matching article.
    """

    name: str = "wikipedia"
    description: str = (
        "Search Wikipedia for an article and return a short summary. "
        "Use this when the user needs encyclopedic or factual background information."
    )
    args_schema: Type[BaseModel] = WikipediaInput

    session_id: Optional[str] = None

    async def _arun(self, query: str, sentences: int = 3) -> str:
        """Search Wikipedia and return a summary."""
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                headers={"User-Agent": "OpenNotebook/1.0"},
            ) as client:
                search_resp = await client.get(
                    WIKIPEDIA_SEARCH,
                    params={
                        "action": "query",
                        "list": "search",
                        "srsearch": query,
                        "srlimit": 1,
                        "format": "json",
                    },
                )

                if search_resp.status_code != 200:
                    return json.dumps({
                        "success": False,
                        "error": f"Wikipedia search failed: {search_resp.status_code}",
                    })

                search_data = search_resp.json()
                results = search_data.get("query", {}).get("search", [])

                if not results:
                    return json.dumps({
                        "success": False,
                        "error": f"No Wikipedia articles found for '{query}'",
                    })

                title = results[0]["title"]

                summary_resp = await client.get(
                    f"{WIKIPEDIA_API}/page/summary/{title}",
                )

                if summary_resp.status_code != 200:
                    return json.dumps({
                        "success": False,
                        "error": f"Failed to fetch summary for '{title}'",
                    })

                summary_data = summary_resp.json()
                full_summary = summary_data.get("extract", "")

                # Truncate to requested number of sentences
                parts = full_summary.split(". ")
                if len(parts) > sentences:
                    summary = ". ".join(parts[:sentences]) + "."
                else:
                    summary = full_summary

                page_url = summary_data.get(
                    "content_urls", {}
                ).get("desktop", {}).get("page", f"https://en.wikipedia.org/wiki/{title}")

            return json.dumps({
                "success": True,
                "title": title,
                "summary": summary,
                "url": page_url,
            })

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
            })

    def _run(self, **kwargs) -> str:
        """Sync version not supported."""
        raise NotImplementedError("WikipediaTool only supports async execution")
