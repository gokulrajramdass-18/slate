"""
API endpoint tests for Graph Router.

Tests cover:
- GET /api/graph/sources (global graph)
- GET /api/graph/sources/notebook/{id} (notebook graph)
- GET /api/graph/sources/{id}/neighbors (neighborhood)
- POST /api/graph/sources/similarities (recompute)
- GET /api/graph/layouts (list)
- GET /api/graph/layouts/{id} (get)
- POST /api/graph/layouts (save)
- PUT /api/graph/layouts/{id} (update)
- DELETE /api/graph/layouts/{id} (delete)
"""

import json
from unittest.mock import AsyncMock, patch

import pytest


# ============================================================================
# Shared mock helpers
# ============================================================================

MOCK_GRAPH_DATA = {
    "nodes": [
        {
            "id": "s1",
            "type": "text",
            "label": "Source 1",
            "data": {
                "title": "Source 1",
                "description": "",
                "source_type": "text",
                "created": "2026-01-01T00:00:00",
                "updated": "2026-01-01T00:00:00",
                "chunk_count": 5,
                "topics": ["python"],
                "connection_count": 1,
                "notebooks": [],
            },
        }
    ],
    "edges": [
        {
            "id": "semantic-s1-s2",
            "source": "s1",
            "target": "s2",
            "type": "semantic",
            "label": "85%",
            "data": {"strength": 0.85, "metadata": {}},
        }
    ],
    "metadata": {
        "total_sources": 1,
        "date_range": {"min": "2026-01-01", "max": "2026-01-01"},
        "source_type_counts": {"text": 1},
        "edge_type_counts": {"semantic": 1},
    },
}

MOCK_LAYOUT = {
    "id": "layout-1",
    "name": "My Layout",
    "description": "Test layout",
    "scope": "global",
    "scope_id": None,
    "layout_data": {"s1": {"x": 100, "y": 200}},
    "created": "2026-01-01T00:00:00",
    "updated": "2026-01-01T00:00:00",
}


# ============================================================================
# Global graph endpoint
# ============================================================================


@pytest.mark.api
class TestGetGlobalGraph:
    """Test GET /api/graph/sources."""

    def test_returns_graph_data(self, test_client):
        with patch("api.routers.graph.graph_service.get_graph_data", new_callable=AsyncMock) as mock:
            mock.return_value = MOCK_GRAPH_DATA
            response = test_client.get("/api/graph/sources")

        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert "metadata" in data

    def test_with_source_type_filter(self, test_client):
        with patch("api.routers.graph.graph_service.get_graph_data", new_callable=AsyncMock) as mock:
            mock.return_value = MOCK_GRAPH_DATA
            response = test_client.get("/api/graph/sources?source_types=text&source_types=file")

        assert response.status_code == 200
        call_args = mock.call_args
        filters = call_args[0][2]  # third positional arg
        assert "source_types" in filters

    def test_with_semantic_threshold(self, test_client):
        with patch("api.routers.graph.graph_service.get_graph_data", new_callable=AsyncMock) as mock:
            mock.return_value = MOCK_GRAPH_DATA
            response = test_client.get("/api/graph/sources?semantic_threshold=0.9")

        assert response.status_code == 200

    def test_with_show_isolated_false(self, test_client):
        with patch("api.routers.graph.graph_service.get_graph_data", new_callable=AsyncMock) as mock:
            mock.return_value = MOCK_GRAPH_DATA
            response = test_client.get("/api/graph/sources?show_isolated=false")

        assert response.status_code == 200

    def test_invalid_threshold(self, test_client):
        response = test_client.get("/api/graph/sources?semantic_threshold=2.0")
        assert response.status_code == 422

    def test_service_error(self, test_client):
        with patch("api.routers.graph.graph_service.get_graph_data", new_callable=AsyncMock) as mock:
            mock.side_effect = Exception("DB error")
            response = test_client.get("/api/graph/sources")

        assert response.status_code == 500


# ============================================================================
# Notebook graph endpoint
# ============================================================================


@pytest.mark.api
class TestGetNotebookGraph:
    """Test GET /api/graph/sources/notebook/{notebook_id}."""

    def test_returns_notebook_graph(self, test_client):
        with patch("api.routers.graph.graph_service.get_graph_data", new_callable=AsyncMock) as mock:
            mock.return_value = MOCK_GRAPH_DATA
            response = test_client.get("/api/graph/sources/notebook/nb-123")

        assert response.status_code == 200
        mock.assert_called_once()
        call_args = mock.call_args
        assert call_args[0][0] == "notebook"
        assert call_args[0][1] == "nb-123"

    def test_with_filters(self, test_client):
        with patch("api.routers.graph.graph_service.get_graph_data", new_callable=AsyncMock) as mock:
            mock.return_value = MOCK_GRAPH_DATA
            response = test_client.get(
                "/api/graph/sources/notebook/nb-123"
                "?source_types=file&semantic_threshold=0.8&show_isolated=false"
            )

        assert response.status_code == 200


# ============================================================================
# Neighborhood endpoint
# ============================================================================


@pytest.mark.api
class TestGetNeighborhood:
    """Test GET /api/graph/sources/{source_id}/neighbors."""

    def test_returns_neighborhood(self, test_client):
        with patch("api.routers.graph.graph_service.get_neighborhood", new_callable=AsyncMock) as mock:
            mock.return_value = MOCK_GRAPH_DATA
            response = test_client.get("/api/graph/sources/s1/neighbors?depth=2")

        assert response.status_code == 200
        mock.assert_called_once()
        call_args = mock.call_args
        assert call_args[0][0] == "s1"  # source_id
        assert call_args[0][1] == 2  # depth

    def test_default_depth(self, test_client):
        with patch("api.routers.graph.graph_service.get_neighborhood", new_callable=AsyncMock) as mock:
            mock.return_value = MOCK_GRAPH_DATA
            response = test_client.get("/api/graph/sources/s1/neighbors")

        assert response.status_code == 200
        call_args = mock.call_args
        assert call_args[0][1] == 1  # default depth

    def test_depth_exceeds_max(self, test_client):
        response = test_client.get("/api/graph/sources/s1/neighbors?depth=5")
        assert response.status_code == 422


# ============================================================================
# Similarities endpoint
# ============================================================================


@pytest.mark.api
class TestRecomputeSimilarities:
    """Test POST /api/graph/sources/similarities."""

    def test_recompute_specific_sources(self, test_client):
        with patch("api.routers.graph.graph_service.compute_source_similarities", new_callable=AsyncMock):
            response = test_client.post(
                "/api/graph/sources/similarities?threshold=0.8&top_k=10",
                json=["s1", "s2"],
            )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2

    def test_recompute_all(self, test_client):
        with patch("api.routers.graph.graph_service.compute_source_similarities", new_callable=AsyncMock), \
             patch("api.routers.graph.repo_query", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [
                {"source_id": "s1"},
                {"source_id": "s2"},
                {"source_id": "s3"},
            ]
            response = test_client.post("/api/graph/sources/similarities")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3


# ============================================================================
# Layout endpoints
# ============================================================================


@pytest.mark.api
class TestLayoutEndpoints:
    """Test layout CRUD endpoints."""

    def test_list_layouts(self, test_client):
        with patch("api.routers.graph.graph_service.list_layouts", new_callable=AsyncMock) as mock:
            mock.return_value = [MOCK_LAYOUT]
            response = test_client.get("/api/graph/layouts?scope=global")

        assert response.status_code == 200
        data = response.json()
        assert "layouts" in data
        assert data["total"] == 1

    def test_list_layouts_notebook_scope_requires_id(self, test_client):
        with patch("api.routers.graph.graph_service.list_layouts", new_callable=AsyncMock):
            response = test_client.get("/api/graph/layouts?scope=notebook")

        assert response.status_code == 400

    def test_list_layouts_invalid_scope(self, test_client):
        response = test_client.get("/api/graph/layouts?scope=invalid")
        assert response.status_code == 422

    def test_get_layout(self, test_client):
        with patch("api.routers.graph.graph_service.load_layout", new_callable=AsyncMock) as mock:
            mock.return_value = MOCK_LAYOUT
            response = test_client.get("/api/graph/layouts/layout-1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "layout-1"
        assert data["name"] == "My Layout"

    def test_get_layout_not_found(self, test_client):
        with patch("api.routers.graph.graph_service.load_layout", new_callable=AsyncMock) as mock:
            mock.return_value = None
            response = test_client.get("/api/graph/layouts/nonexistent")

        assert response.status_code == 404

    def test_save_layout(self, test_client):
        with patch("api.routers.graph.graph_service.save_layout", new_callable=AsyncMock) as mock_save, \
             patch("api.routers.graph.graph_service.load_layout", new_callable=AsyncMock) as mock_load:
            mock_save.return_value = "layout-new"
            mock_load.return_value = {**MOCK_LAYOUT, "id": "layout-new"}
            response = test_client.post(
                "/api/graph/layouts",
                json={
                    "name": "New Layout",
                    "scope": "global",
                    "layout_data": {"s1": {"x": 10, "y": 20}},
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "layout-new"

    def test_save_layout_notebook_scope_requires_id(self, test_client):
        response = test_client.post(
            "/api/graph/layouts",
            json={
                "name": "Layout",
                "scope": "notebook",
                "layout_data": {},
            },
        )
        assert response.status_code == 400

    def test_update_layout(self, test_client):
        updated = {**MOCK_LAYOUT, "layout_data": {"s1": {"x": 50, "y": 60}}}
        with patch("api.routers.graph.graph_service.load_layout", new_callable=AsyncMock) as mock_load, \
             patch("api.routers.graph.graph_service.update_layout", new_callable=AsyncMock):
            mock_load.side_effect = [MOCK_LAYOUT, updated]
            response = test_client.put(
                "/api/graph/layouts/layout-1",
                json={"s1": {"x": 50, "y": 60}},
            )

        assert response.status_code == 200

    def test_update_layout_not_found(self, test_client):
        with patch("api.routers.graph.graph_service.load_layout", new_callable=AsyncMock) as mock:
            mock.return_value = None
            response = test_client.put(
                "/api/graph/layouts/nonexistent",
                json={"s1": {"x": 50, "y": 60}},
            )

        assert response.status_code == 404

    def test_delete_layout(self, test_client):
        with patch("api.routers.graph.graph_service.load_layout", new_callable=AsyncMock) as mock_load, \
             patch("api.routers.graph.graph_service.delete_layout", new_callable=AsyncMock):
            mock_load.return_value = MOCK_LAYOUT
            response = test_client.delete("/api/graph/layouts/layout-1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "layout-1"

    def test_delete_layout_not_found(self, test_client):
        with patch("api.routers.graph.graph_service.load_layout", new_callable=AsyncMock) as mock:
            mock.return_value = None
            response = test_client.delete("/api/graph/layouts/nonexistent")

        assert response.status_code == 404
