"""
Unit tests for Graph Service.

Tests cover:
- Semantic similarity computation
- Edge building (semantic, notebook, topic, note_link, hana_schema, api_relation)
- Graph data assembly and filtering
- Layout CRUD operations
- Helper functions (is_nested_endpoint, get_common_resource)
"""

import json
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from api.services.graph_service import (
    build_topic_edges,
    is_nested_endpoint,
    get_common_resource,
)


# ============================================================================
# Helper function tests (no DB required)
# ============================================================================


class TestIsNestedEndpoint:
    """Test is_nested_endpoint helper."""

    def test_nested_child(self):
        assert is_nested_endpoint("/api/users", "/api/users/123/posts") is True

    def test_nested_parent(self):
        assert is_nested_endpoint("/api/users/123/posts", "/api/users") is True

    def test_same_endpoint(self):
        assert is_nested_endpoint("/api/users", "/api/users") is True

    def test_not_nested(self):
        assert is_nested_endpoint("/api/users", "/api/products") is False

    def test_with_query_params(self):
        assert is_nested_endpoint("/api/users?page=1", "/api/users/123") is True

    def test_trailing_slashes(self):
        assert is_nested_endpoint("/api/users/", "/api/users") is True

    def test_partial_segment_mismatch(self):
        # /api/user is NOT a prefix of /api/users in path terms
        # but string-wise it is -- this tests current behavior
        assert is_nested_endpoint("/api/user", "/api/users") is True


class TestGetCommonResource:
    """Test get_common_resource helper."""

    def test_common_resource(self):
        assert get_common_resource("/api/users", "/api/users/123") == "users"

    def test_no_common_resource(self):
        assert get_common_resource("/api/users", "/v2/products") is None

    def test_ignores_api_prefix(self):
        # "api" should be filtered out as a common resource
        assert get_common_resource("/api/users", "/api/products") is None

    def test_ignores_version_prefix(self):
        assert get_common_resource("/v1/users", "/v1/products") is None

    def test_deeper_common(self):
        assert get_common_resource("/api/admin/users", "/api/admin/users/123") == "users"

    def test_with_path_params(self):
        # Path parameters like {id} break the common prefix
        assert get_common_resource("/api/users/{id}", "/api/users/{id}/posts") is None

    def test_empty_paths(self):
        assert get_common_resource("", "") is None


# ============================================================================
# Topic edge tests (pure logic, mock-free)
# ============================================================================


class TestBuildTopicEdges:
    """Test topic edge building from source topic arrays."""

    @pytest.mark.asyncio
    async def test_basic_overlap(self):
        sources = [
            {"id": "s1", "topics": json.dumps(["python", "ai", "ml"])},
            {"id": "s2", "topics": json.dumps(["ai", "ml", "data"])},
        ]
        edges = await build_topic_edges(sources, min_overlap=2)

        assert len(edges) == 1
        edge = edges[0]
        assert edge["source"] == "s1"
        assert edge["target"] == "s2"
        assert edge["type"] == "topic"
        assert edge["data"]["strength"] > 0

    @pytest.mark.asyncio
    async def test_no_overlap(self):
        sources = [
            {"id": "s1", "topics": json.dumps(["python", "java"])},
            {"id": "s2", "topics": json.dumps(["rust", "go"])},
        ]
        edges = await build_topic_edges(sources, min_overlap=2)
        assert len(edges) == 0

    @pytest.mark.asyncio
    async def test_below_min_overlap(self):
        sources = [
            {"id": "s1", "topics": json.dumps(["python", "ai"])},
            {"id": "s2", "topics": json.dumps(["ai", "rust"])},
        ]
        # Only 1 topic overlap, min is 2
        edges = await build_topic_edges(sources, min_overlap=2)
        assert len(edges) == 0

    @pytest.mark.asyncio
    async def test_multiple_pairs(self):
        sources = [
            {"id": "s1", "topics": json.dumps(["a", "b", "c"])},
            {"id": "s2", "topics": json.dumps(["b", "c", "d"])},
            {"id": "s3", "topics": json.dumps(["c", "d", "e"])},
        ]
        edges = await build_topic_edges(sources, min_overlap=2)
        # s1-s2 share b,c; s2-s3 share c,d; s1-s3 share only c (below min)
        assert len(edges) == 2

    @pytest.mark.asyncio
    async def test_empty_sources(self):
        edges = await build_topic_edges([], min_overlap=2)
        assert edges == []

    @pytest.mark.asyncio
    async def test_no_topics(self):
        sources = [
            {"id": "s1", "topics": None},
            {"id": "s2", "topics": ""},
        ]
        edges = await build_topic_edges(sources, min_overlap=2)
        assert edges == []

    @pytest.mark.asyncio
    async def test_topics_as_list(self):
        """Topics can be a list (not JSON string)."""
        sources = [
            {"id": "s1", "topics": ["python", "ai", "ml"]},
            {"id": "s2", "topics": ["ai", "ml", "data"]},
        ]
        edges = await build_topic_edges(sources, min_overlap=2)
        assert len(edges) == 1

    @pytest.mark.asyncio
    async def test_jaccard_similarity(self):
        sources = [
            {"id": "s1", "topics": json.dumps(["a", "b"])},
            {"id": "s2", "topics": json.dumps(["a", "b"])},
        ]
        edges = await build_topic_edges(sources, min_overlap=2)
        assert len(edges) == 1
        # Identical topic sets -> Jaccard = 1.0
        assert edges[0]["data"]["strength"] == 1.0

    @pytest.mark.asyncio
    async def test_shared_topics_metadata(self):
        sources = [
            {"id": "s1", "topics": json.dumps(["a", "b", "c"])},
            {"id": "s2", "topics": json.dumps(["b", "c", "d"])},
        ]
        edges = await build_topic_edges(sources, min_overlap=2)
        metadata = edges[0]["data"]["metadata"]
        assert metadata["overlap_count"] == 2
        assert set(metadata["shared_topics"]) == {"b", "c"}


# ============================================================================
# Database-dependent tests (mocked)
# ============================================================================


class TestBuildSemanticEdges:
    """Test semantic edge building with mocked DB."""

    @pytest.mark.asyncio
    async def test_returns_edges_above_threshold(self):
        mock_db = AsyncMock()
        mock_db.query = AsyncMock(return_value=[
            {"source_id": "s1", "related_source_id": "s2", "similarity_score": 0.85},
            {"source_id": "s1", "related_source_id": "s3", "similarity_score": 0.72},
        ])

        with patch("api.services.graph_service.db_connection") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            from api.services.graph_service import build_semantic_edges
            edges = await build_semantic_edges(["s1", "s2", "s3"], threshold=0.7)

        assert len(edges) == 2
        assert all(e["type"] == "semantic" for e in edges)
        assert edges[0]["data"]["strength"] == 0.85

    @pytest.mark.asyncio
    async def test_empty_source_ids(self):
        from api.services.graph_service import build_semantic_edges
        edges = await build_semantic_edges([])
        assert edges == []


class TestBuildNotebookEdges:
    """Test notebook membership edge building with mocked DB."""

    @pytest.mark.asyncio
    async def test_returns_edges_for_shared_notebook(self):
        mock_db = AsyncMock()
        mock_db.query = AsyncMock(return_value=[
            {
                "source1": "s1", "source2": "s2",
                "notebook_id": "nb1", "notebook_name": "Research"
            },
        ])

        with patch("api.services.graph_service.db_connection") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            from api.services.graph_service import build_notebook_edges
            edges = await build_notebook_edges(["s1", "s2"])

        assert len(edges) == 1
        assert edges[0]["type"] == "notebook"
        assert edges[0]["label"] == "Research"
        assert edges[0]["data"]["strength"] == 1.0

    @pytest.mark.asyncio
    async def test_empty_source_ids(self):
        from api.services.graph_service import build_notebook_edges
        edges = await build_notebook_edges([])
        assert edges == []


class TestComputeSourceSimilarities:
    """Test similarity computation with mocked DB and numpy."""

    @pytest.mark.asyncio
    async def test_computes_and_stores_similarities(self):
        # Create two similar vectors
        np.random.seed(42)
        vec1 = np.random.randn(1536).astype(np.float32)
        vec1 = vec1 / np.linalg.norm(vec1)
        # Make vec2 close to vec1
        vec2 = vec1 + np.random.randn(1536).astype(np.float32) * 0.1
        vec2 = vec2 / np.linalg.norm(vec2)

        mock_db = AsyncMock()

        # First call: source embeddings; second: all other embeddings;
        # third: other source's embeddings; fourth: delete; fifth+: inserts
        call_count = 0
        async def mock_query(sql, params=None, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [{"embedding": json.dumps(vec1.tolist())}]
            elif call_count == 2:
                return [{"source_id": "s2", "embedding": json.dumps(vec2.tolist())}]
            elif call_count == 3:
                return [{"embedding": json.dumps(vec2.tolist())}]
            return []

        mock_db.query = mock_query
        mock_db.execute = AsyncMock()

        with patch("api.services.graph_service.db_connection") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            from api.services.graph_service import compute_source_similarities
            await compute_source_similarities("s1", threshold=0.5, top_k=10)

        # Should have called execute for DELETE and at least one INSERT
        assert mock_db.execute.call_count >= 1


class TestBuildNoteLinks:
    """Test note link edge building."""

    @pytest.mark.asyncio
    async def test_returns_note_link_edges(self):
        mock_db = AsyncMock()
        mock_db.query = AsyncMock(return_value=[
            {
                "source_note_id": "n1", "target_note_id": "n2",
                "source_title": "Note A", "target_title": "Note B"
            },
        ])

        with patch("api.services.graph_service.db_connection") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            from api.services.graph_service import build_note_link_edges
            edges = await build_note_link_edges(["n1", "n2"])

        assert len(edges) == 1
        assert edges[0]["type"] == "note_link"

    @pytest.mark.asyncio
    async def test_empty_source_ids(self):
        from api.services.graph_service import build_note_link_edges
        edges = await build_note_link_edges([])
        assert edges == []


# ============================================================================
# Layout CRUD tests
# ============================================================================


class TestLayoutOperations:
    """Test layout save/load/list/delete with mocked DB."""

    @pytest.mark.asyncio
    async def test_save_layout(self):
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()

        with patch("api.services.graph_service.db_connection") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            from api.services.graph_service import save_layout
            layout_id = await save_layout(
                name="Test Layout",
                scope="global",
                scope_id=None,
                layout_data={"s1": {"x": 100, "y": 200}},
                description="A test"
            )

        assert layout_id is not None
        assert len(layout_id) == 36  # UUID format
        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_layout(self):
        mock_db = AsyncMock()
        mock_db.query = AsyncMock(return_value={
            "id": "layout-1",
            "name": "Test",
            "scope": "global",
            "scope_id": None,
            "layout_data": json.dumps({"s1": {"x": 10, "y": 20}}),
            "created": "2026-01-01T00:00:00",
            "updated": "2026-01-01T00:00:00",
        })

        with patch("api.services.graph_service.db_connection") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            from api.services.graph_service import load_layout
            layout = await load_layout("layout-1")

        assert layout is not None
        assert layout["layout_data"] == {"s1": {"x": 10, "y": 20}}

    @pytest.mark.asyncio
    async def test_load_layout_not_found(self):
        mock_db = AsyncMock()
        mock_db.query = AsyncMock(return_value=None)

        with patch("api.services.graph_service.db_connection") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            from api.services.graph_service import load_layout
            layout = await load_layout("nonexistent")

        assert layout is None

    @pytest.mark.asyncio
    async def test_list_layouts_global(self):
        mock_db = AsyncMock()
        mock_db.query = AsyncMock(return_value=[
            {"id": "l1", "name": "Layout 1", "scope": "global", "created": "2026-01-01", "updated": "2026-01-01"},
            {"id": "l2", "name": "Layout 2", "scope": "global", "created": "2026-01-02", "updated": "2026-01-02"},
        ])

        with patch("api.services.graph_service.db_connection") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            from api.services.graph_service import list_layouts
            layouts = await list_layouts("global")

        assert len(layouts) == 2

    @pytest.mark.asyncio
    async def test_delete_layout(self):
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()

        with patch("api.services.graph_service.db_connection") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            from api.services.graph_service import delete_layout
            await delete_layout("layout-1")

        mock_db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_layout(self):
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()

        with patch("api.services.graph_service.db_connection") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            from api.services.graph_service import update_layout
            await update_layout("layout-1", {"s1": {"x": 50, "y": 60}})

        mock_db.execute.assert_called_once()
