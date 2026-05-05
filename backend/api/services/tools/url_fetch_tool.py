"""
URL Fetch Tool

Provides a LangChain-compatible tool for fetching and extracting content from web pages.
"""

import json
from typing import Type, Optional

import httpx
from langchain.tools import BaseTool
from pydantic import BaseModel, Field


CONTENT_LIMIT = 5000


class URLFetchInput(BaseModel):
    """Input schema for URL fetch tool"""
    url: str = Field(
        description="The URL to fetch content from"
    )
    extract_text: bool = Field(
        default=True,
        description="If true, extract visible text only. If false, return raw HTML."
    )


class URLFetchTool(BaseTool):
    """
    Fetch content from a URL and optionally extract readable text.

    Uses httpx for async HTTP requests and BeautifulSoup4 for text extraction.
    Content is truncated to 5000 characters.
    """

    name: str = "url_fetch"
    description: str = (
        "Fetch content from a web URL. "
        "Can return raw HTML or extracted readable text. "
        "Content is truncated to 5000 characters. "
        "Use this to read web pages, articles, or documentation."
    )
    args_schema: Type[BaseModel] = URLFetchInput

    session_id: Optional[str] = None

    async def _arun(self, url: str, extract_text: bool = True) -> str:
        """Fetch the URL and return content."""
        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={"User-Agent": "OpenNotebook/1.0"},
            ) as client:
                response = await client.get(url)

            content = response.text

            if extract_text:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(content, "html.parser")

                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()

                content = soup.get_text(separator="\n", strip=True)

            if len(content) > CONTENT_LIMIT:
                content = content[:CONTENT_LIMIT] + "... [truncated]"

            return json.dumps({
                "success": True,
                "url": url,
                "content": content,
                "status_code": response.status_code,
            })

        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
                "url": url,
            })

    def _run(self, **kwargs) -> str:
        """Sync version not supported."""
        raise NotImplementedError("URLFetchTool only supports async execution")
