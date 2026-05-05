"""
Tests for the Version Management Service.

Tests:
- Version snapshot creation
- Version numbering (sequential, unique per microsite)
- Unpublished changes detection
- Content snapshot accuracy
- Edge cases (no content, no previous versions, etc.)
"""

import json
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.version_service import VersionService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_microsite(mid=None, template_id="tpl-1", title="Test Site"):
    """Create a mock microsite record dict."""
    return {
        "id": mid or str(uuid.uuid4()),
        "title": title,
        "template_id": template_id,
        "custom_css": "body { color: red; }",
        "generation_config": json.dumps({
            "site_title": title,
            "nav_items": [{"label": "Home", "url": "#"}],
            "footer_text": "Footer",
            "logo_url": None,
            "primary_color": "#0066cc",
        }),
    }


def _make_section(section_id="hero", order_num=0, html="<h1>Hello</h1>", visible=True):
    """Create a mock content section record dict."""
    return {
        "id": str(uuid.uuid4()),
        "microsite_id": "ms-1",
        "section_id": section_id,
        "order_num": order_num,
        "content_html": html,
        "content_json": None,
        "is_visible": 1 if visible else 0,
        "created": datetime.utcnow().isoformat(),
        "updated": datetime.utcnow().isoformat(),
    }


def _make_template():
    """Create a mock template record dict."""
    return {
        "id": "tpl-1",
        "name": "blog",
        "display_name": "Blog",
        "default_styles": json.dumps({"primary_color": "#333", "css": ""}),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestVersionServiceCreatePublishVersion:
    """Tests for create_publish_version."""

    @pytest.mark.asyncio
    async def test_creates_first_version(self):
        """First publish should create version 1."""
        service = VersionService()
        ms = _make_microsite(mid="ms-1")
        sections = [_make_section()]

        async def mock_query(sql, params=None, fetch_one=False):
            if "FROM microsites WHERE id" in sql:
                return [ms]
            if "FROM microsite_content" in sql:
                return sections
            if "MAX(version_number)" in sql:
                return [{"max_version": None}]
            if "FROM microsite_templates" in sql:
                return [_make_template()]
            if "FROM microsite_versions WHERE id" in sql:
                return [{
                    "id": "v-1",
                    "microsite_id": "ms-1",
                    "version_number": 1,
                    "published_at": datetime.utcnow().isoformat(),
                    "created": datetime.utcnow().isoformat(),
                    "created_by": "user-1",
                    "full_html": "<html></html>",
                    "full_css": "",
                    "content_snapshot": "{}",
                }]
            return []

        async def mock_execute(sql, params=None):
            return 1

        with patch("api.services.version_service.repo_query", side_effect=mock_query), \
             patch("api.services.version_service.repo_execute", side_effect=mock_execute):
            result = await service.create_publish_version("ms-1", created_by="user-1")

        assert result["version_number"] == 1
        assert result["created_by"] == "user-1"

    @pytest.mark.asyncio
    async def test_increments_version_number(self):
        """Subsequent publishes should increment version number."""
        service = VersionService()
        ms = _make_microsite(mid="ms-2")
        sections = [_make_section()]

        async def mock_query(sql, params=None, fetch_one=False):
            if "FROM microsites WHERE id" in sql:
                return [ms]
            if "FROM microsite_content" in sql:
                return sections
            if "MAX(version_number)" in sql:
                return [{"max_version": 3}]
            if "FROM microsite_templates" in sql:
                return [_make_template()]
            if "FROM microsite_versions WHERE id" in sql:
                return [{
                    "id": "v-4",
                    "microsite_id": "ms-2",
                    "version_number": 4,
                    "published_at": datetime.utcnow().isoformat(),
                    "created": datetime.utcnow().isoformat(),
                    "created_by": "user-1",
                    "full_html": "<html></html>",
                    "full_css": "",
                    "content_snapshot": "{}",
                }]
            return []

        async def mock_execute(sql, params=None):
            return 1

        with patch("api.services.version_service.repo_query", side_effect=mock_query), \
             patch("api.services.version_service.repo_execute", side_effect=mock_execute):
            result = await service.create_publish_version("ms-2", created_by="user-1")

        assert result["version_number"] == 4

    @pytest.mark.asyncio
    async def test_raises_for_missing_microsite(self):
        """Should raise ValueError if microsite not found."""
        service = VersionService()

        async def mock_query(sql, params=None, fetch_one=False):
            return []

        with patch("api.services.version_service.repo_query", side_effect=mock_query):
            with pytest.raises(ValueError, match="not found"):
                await service.create_publish_version("nonexistent")

    @pytest.mark.asyncio
    async def test_handles_empty_content(self):
        """Should create version even with no content sections."""
        service = VersionService()
        ms = _make_microsite(mid="ms-empty")

        async def mock_query(sql, params=None, fetch_one=False):
            if "FROM microsites WHERE id" in sql:
                return [ms]
            if "FROM microsite_content" in sql:
                return []  # No content
            if "MAX(version_number)" in sql:
                return [{"max_version": None}]
            if "FROM microsite_templates" in sql:
                return [_make_template()]
            if "FROM microsite_versions WHERE id" in sql:
                return [{
                    "id": "v-empty",
                    "microsite_id": "ms-empty",
                    "version_number": 1,
                    "published_at": datetime.utcnow().isoformat(),
                    "created": datetime.utcnow().isoformat(),
                    "created_by": "system",
                    "full_html": "<html></html>",
                    "full_css": "",
                    "content_snapshot": json.dumps({"sections": []}),
                }]
            return []

        async def mock_execute(sql, params=None):
            return 1

        with patch("api.services.version_service.repo_query", side_effect=mock_query), \
             patch("api.services.version_service.repo_execute", side_effect=mock_execute):
            result = await service.create_publish_version("ms-empty")

        assert result["version_number"] == 1

    @pytest.mark.asyncio
    async def test_stores_version_message_in_snapshot(self):
        """Version message should be stored in content_snapshot metadata."""
        service = VersionService()
        ms = _make_microsite(mid="ms-msg")
        captured_params = {}

        async def mock_query(sql, params=None, fetch_one=False):
            if "FROM microsites WHERE id" in sql:
                return [ms]
            if "FROM microsite_content" in sql:
                return [_make_section()]
            if "MAX(version_number)" in sql:
                return [{"max_version": None}]
            if "FROM microsite_templates" in sql:
                return [_make_template()]
            if "FROM microsite_versions WHERE id" in sql:
                return [{
                    "id": "v-msg",
                    "microsite_id": "ms-msg",
                    "version_number": 1,
                    "published_at": datetime.utcnow().isoformat(),
                    "created": datetime.utcnow().isoformat(),
                    "created_by": "user-1",
                    "full_html": "<html></html>",
                    "full_css": "",
                    "content_snapshot": "{}",
                }]
            return []

        async def mock_execute(sql, params=None):
            if "INSERT INTO microsite_versions" in sql:
                captured_params.update(params or {})
            return 1

        with patch("api.services.version_service.repo_query", side_effect=mock_query), \
             patch("api.services.version_service.repo_execute", side_effect=mock_execute):
            await service.create_publish_version("ms-msg", created_by="user-1", message="Fixed typos")

        snapshot = json.loads(captured_params["content_snapshot"])
        assert snapshot.get("message") == "Fixed typos"


class TestVersionServiceHasUnpublishedChanges:
    """Tests for has_unpublished_changes."""

    @pytest.mark.asyncio
    async def test_returns_true_when_no_microsite(self):
        """No microsite found should return True."""
        service = VersionService()

        async def mock_query(sql, params=None, fetch_one=False):
            return []

        with patch("api.services.version_service.repo_query", side_effect=mock_query):
            result = await service.has_unpublished_changes("nonexistent")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_when_no_versions(self):
        """No published versions should return True."""
        service = VersionService()

        call_count = 0

        async def mock_query(sql, params=None, fetch_one=False):
            nonlocal call_count
            call_count += 1
            if "FROM microsites" in sql:
                return [{"active_version_id": None, "published_version": None}]
            # No versions found
            return []

        with patch("api.services.version_service.repo_query", side_effect=mock_query):
            result = await service.has_unpublished_changes("ms-1")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_content_matches(self):
        """Should return False when current content matches the snapshot."""
        service = VersionService()
        sections = [
            {
                "section_id": "hero",
                "content_html": "<h1>Hello</h1>",
                "content_json": None,
                "order_num": 0,
                "is_visible": 1,
            }
        ]
        snapshot = {
            "sections": [
                {
                    "section_id": "hero",
                    "content_html": "<h1>Hello</h1>",
                    "content_json": None,
                    "order_num": 0,
                    "is_visible": True,
                }
            ]
        }

        async def mock_query(sql, params=None, fetch_one=False):
            if "FROM microsites" in sql:
                return [{"active_version_id": "v-1", "published_version": 1}]
            if "content_snapshot FROM microsite_versions" in sql:
                return [{"content_snapshot": json.dumps(snapshot)}]
            if "FROM microsite_content" in sql:
                return sections
            return []

        with patch("api.services.version_service.repo_query", side_effect=mock_query):
            result = await service.has_unpublished_changes("ms-1")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_content_differs(self):
        """Should return True when current content differs from snapshot."""
        service = VersionService()
        # Current content has been edited
        sections = [
            {
                "section_id": "hero",
                "content_html": "<h1>Updated Title</h1>",
                "content_json": None,
                "order_num": 0,
                "is_visible": 1,
            }
        ]
        # Stored snapshot has old content
        snapshot = {
            "sections": [
                {
                    "section_id": "hero",
                    "content_html": "<h1>Hello</h1>",
                    "content_json": None,
                    "order_num": 0,
                    "is_visible": True,
                }
            ]
        }

        async def mock_query(sql, params=None, fetch_one=False):
            if "FROM microsites" in sql:
                return [{"active_version_id": "v-1", "published_version": 1}]
            if "content_snapshot FROM microsite_versions" in sql:
                return [{"content_snapshot": json.dumps(snapshot)}]
            if "FROM microsite_content" in sql:
                return sections
            return []

        with patch("api.services.version_service.repo_query", side_effect=mock_query):
            result = await service.has_unpublished_changes("ms-1")

        assert result is True

    @pytest.mark.asyncio
    async def test_falls_back_to_latest_version_when_no_active_version(self):
        """When active_version_id is None, should use latest version by number."""
        service = VersionService()
        sections = [
            {
                "section_id": "hero",
                "content_html": "<h1>Hello</h1>",
                "content_json": None,
                "order_num": 0,
                "is_visible": 1,
            }
        ]
        snapshot = {
            "sections": [
                {
                    "section_id": "hero",
                    "content_html": "<h1>Hello</h1>",
                    "content_json": None,
                    "order_num": 0,
                    "is_visible": True,
                }
            ]
        }

        queries_received = []

        async def mock_query(sql, params=None, fetch_one=False):
            queries_received.append(sql)
            if "FROM microsites" in sql:
                return [{"active_version_id": None, "published_version": 2}]
            if "ORDER BY version_number DESC LIMIT 1" in sql:
                return [{"content_snapshot": json.dumps(snapshot)}]
            if "FROM microsite_content" in sql:
                return sections
            return []

        with patch("api.services.version_service.repo_query", side_effect=mock_query):
            result = await service.has_unpublished_changes("ms-1")

        assert result is False
        # Verify the fallback query was used
        assert any("ORDER BY version_number DESC LIMIT 1" in q for q in queries_received)


class TestVersionServiceHelpers:
    """Tests for helper methods."""

    @pytest.mark.asyncio
    async def test_get_version(self):
        """get_version should return a version by ID."""
        service = VersionService()
        version_data = {
            "id": "v-1",
            "microsite_id": "ms-1",
            "version_number": 1,
        }

        async def mock_query(sql, params=None, fetch_one=False):
            if "FROM microsite_versions WHERE id" in sql:
                return [version_data]
            return []

        with patch("api.services.version_service.repo_query", side_effect=mock_query):
            result = await service.get_version("v-1")

        assert result == version_data

    @pytest.mark.asyncio
    async def test_get_version_returns_none_for_missing(self):
        """get_version should return None for non-existent ID."""
        service = VersionService()

        async def mock_query(sql, params=None, fetch_one=False):
            return []

        with patch("api.services.version_service.repo_query", side_effect=mock_query):
            result = await service.get_version("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_latest_version(self):
        """get_latest_version should return the highest version number."""
        service = VersionService()
        version_data = {
            "id": "v-3",
            "microsite_id": "ms-1",
            "version_number": 3,
        }

        async def mock_query(sql, params=None, fetch_one=False):
            return [version_data]

        with patch("api.services.version_service.repo_query", side_effect=mock_query):
            result = await service.get_latest_version("ms-1")

        assert result["version_number"] == 3

    @pytest.mark.asyncio
    async def test_build_full_css_combines_template_and_custom(self):
        """_build_full_css should combine template and custom CSS."""
        service = VersionService()
        ms = {
            "template_id": "tpl-1",
            "custom_css": ".custom { color: blue; }",
        }
        template_styles = json.dumps({"css": ".template { font-size: 16px; }"})

        async def mock_query(sql, params=None, fetch_one=False):
            if "FROM microsite_templates" in sql:
                return [{"default_styles": template_styles}]
            return []

        with patch("api.services.version_service.repo_query", side_effect=mock_query):
            result = await service._build_full_css(ms)

        assert "Template Styles" in result
        assert ".template { font-size: 16px; }" in result
        assert "Custom Styles" in result
        assert ".custom { color: blue; }" in result

    @pytest.mark.asyncio
    async def test_build_full_css_handles_no_template(self):
        """_build_full_css should handle missing template gracefully."""
        service = VersionService()
        ms = {
            "template_id": None,
            "custom_css": ".only-custom { margin: 0; }",
        }

        async def mock_query(sql, params=None, fetch_one=False):
            return []

        with patch("api.services.version_service.repo_query", side_effect=mock_query):
            result = await service._build_full_css(ms)

        assert ".only-custom { margin: 0; }" in result
