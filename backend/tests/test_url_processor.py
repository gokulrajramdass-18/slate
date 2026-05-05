"""
Tests for URL Processor

Tests basic URL scraping functionality with httpx + BeautifulSoup.
"""

import os
import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


@pytest.mark.asyncio
class TestURLProcessor:
    """Test URL processor functionality."""

    @pytest.fixture
    def mock_html_content(self):
        """Sample HTML content for basic scraping."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Page Title</title>
            <meta name="description" content="Test page description">
            <meta name="author" content="Jane Smith">
            <meta property="article:published_time" content="2026-04-01T10:00:00Z">
        </head>
        <body>
            <nav>Navigation content to be removed</nav>
            <header>Header to be removed</header>
            <main>
                <h1>Main Content</h1>
                <p>This is the main article content.</p>
                <p>Multiple paragraphs with useful information.</p>
            </main>
            <footer>Footer to be removed</footer>
            <script>console.log('script to be removed');</script>
        </body>
        </html>
        """

    async def test_extract_url_basic_scraping(self, mock_html_content):
        """Test basic URL extraction."""
        from open_notebook.sources.url_processor import extract_url_data

        mock_response = MagicMock()
        mock_response.text = mock_html_content
        mock_response.raise_for_status = MagicMock()

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await extract_url_data("https://example.com/page")

            assert result["scraping_method"] == "basic"
            assert result["asset_type"] == "webpage"
            assert "Main Content" in result["full_text"]
            assert "Navigation content" not in result["full_text"]
            assert "script to be removed" not in result["full_text"]

            # Check metadata
            metadata = result["metadata"]
            assert metadata["title"] == "Test Page Title"
            assert metadata["description"] == "Test page description"
            assert metadata["author"] == "Jane Smith"
            assert metadata["content_type"] == "text"

    async def test_metadata_extraction(self, mock_html_content):
        """Test metadata extraction."""
        from open_notebook.sources.url_processor import extract_url_data

        mock_response = MagicMock()
        mock_response.text = mock_html_content
        mock_response.raise_for_status = MagicMock()

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await extract_url_data("https://example.com")

            metadata = result["metadata"]

            assert metadata["title"] == "Test Page Title"
            assert metadata["description"] == "Test page description"
            assert metadata["author"] == "Jane Smith"
            assert metadata["published_date"] == "2026-04-01T10:00:00Z"
            assert metadata["url"] == "https://example.com"

    async def test_50k_character_limit(self):
        """Test that basic scraping maintains 50k character limit."""
        from open_notebook.sources.url_processor import extract_url_data

        # Create large HTML content
        large_html = "<html><body><main>"
        large_html += "<p>This is a paragraph. </p>" * 10000
        large_html += "</main></body></html>"

        mock_response = MagicMock()
        mock_response.text = large_html
        mock_response.raise_for_status = MagicMock()

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await extract_url_data("https://example.com")

            # Should be limited to 50k
            assert len(result["full_text"]) == 50000

    async def test_error_handling_network_failure(self):
        """Test error handling when network request fails."""
        from open_notebook.sources.url_processor import extract_url_data

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.side_effect = Exception("Network error")
            mock_client_class.return_value = mock_client

            with pytest.raises(Exception) as exc_info:
                await extract_url_data("https://example.com")

            assert "Network error" in str(exc_info.value)

    async def test_html_cleanup(self):
        """Test that unwanted HTML elements are removed."""
        from open_notebook.sources.url_processor import extract_url_data

        html_with_unwanted = """
        <html>
        <head><title>Test</title></head>
        <body>
            <nav>Nav content</nav>
            <header>Header content</header>
            <script>alert('bad');</script>
            <style>body { color: red; }</style>
            <main>Good content</main>
            <footer>Footer content</footer>
        </body>
        </html>
        """

        mock_response = MagicMock()
        mock_response.text = html_with_unwanted
        mock_response.raise_for_status = MagicMock()

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await extract_url_data("https://example.com")

            content = result["full_text"]

            # Good content should be present
            assert "Good content" in content

            # Bad content should be removed
            assert "Nav content" not in content
            assert "Header content" not in content
            assert "Footer content" not in content
            assert "alert('bad')" not in content
            assert "color: red" not in content

    async def test_og_description_fallback(self):
        """Test that og:description is used as fallback."""
        from open_notebook.sources.url_processor import extract_url_data

        html_with_og = """
        <html>
        <head>
            <title>Test</title>
            <meta property="og:description" content="OG description">
        </head>
        <body><main>Content</main></body>
        </html>
        """

        mock_response = MagicMock()
        mock_response.text = html_with_og
        mock_response.raise_for_status = MagicMock()

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            result = await extract_url_data("https://example.com")

            assert result["metadata"]["description"] == "OG description"
