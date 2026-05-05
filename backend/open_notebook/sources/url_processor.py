"""
URL Source Processor

Handles web page scraping and metadata extraction using httpx + BeautifulSoup.
Extracts text content and basic metadata from web pages.
"""

import os
import json
from typing import Dict, Any, Optional
from datetime import datetime
import httpx
from bs4 import BeautifulSoup


async def extract_url_data(url: str) -> Dict[str, Any]:
    """
    Extract content and metadata from a URL using basic httpx + BeautifulSoup scraping.

    Args:
        url: Web page URL to scrape

    Returns:
        Dictionary with:
        - full_text: Extracted content (plain text)
        - metadata: Dict with title, description, author, published_date
        - asset_type: "webpage"
        - scraping_method: "basic"

    Raises:
        Exception: If scraping fails
    """
    return await _scrape_with_httpx(url)


async def _scrape_with_httpx(url: str) -> Dict[str, Any]:
    """
    Basic scraping with httpx + BeautifulSoup.

    Args:
        url: Web page URL

    Returns:
        Dictionary with scraped content and metadata

    Raises:
        Exception: If scraping fails
    """
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract title
        title_tag = soup.find('title')
        title = title_tag.get_text().strip() if title_tag else ''

        # Extract meta description
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        if not desc_tag:
            desc_tag = soup.find('meta', attrs={'property': 'og:description'})
        description = desc_tag.get('content', '').strip() if desc_tag else ''

        # Extract author
        author_tag = soup.find('meta', attrs={'name': 'author'})
        if not author_tag:
            author_tag = soup.find('meta', attrs={'property': 'article:author'})
        author = author_tag.get('content', '').strip() if author_tag else None

        # Extract published date
        date_tag = soup.find('meta', attrs={'property': 'article:published_time'})
        if not date_tag:
            date_tag = soup.find('time', attrs={'datetime': True})
        published_date = None
        if date_tag:
            published_date = date_tag.get('content') or date_tag.get('datetime')

        # Remove unwanted elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        # Extract text
        text = soup.get_text()

        # Clean whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)

        # Build metadata dictionary
        metadata = {
            "title": title,
            "description": description,
            "author": author,
            "published_date": published_date,
            "url": url,
            "extracted_at": datetime.utcnow().isoformat(),
            "content_type": "text",
        }

        return {
            "full_text": text[:50000],  # Keep 50k limit for basic scraping
            "metadata": metadata,
            "asset_type": "webpage",
            "scraping_method": "basic",
        }
