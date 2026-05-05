"""
Tests for Agent Memory API endpoints (/api/memory).

Tests cover:
- Memory CRUD (create, list, get, update, delete)
- Memory search with keyword matching
- Tag filtering in search
- Pagination (limit, offset)
- Memory type filtering
- Input validation
- 404 handling for missing notebooks/entries
- JSON field parsing (metadata, tags)
"""

import json
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Provide a FastAPI test client."""
    with TestClient(app) as c:
        yield c


NOTEBOOK_ID = "nb-test-123"
ENTRY_ID = "mem-entry-456"


def _fake_notebook_row(notebook_id: str = NOTEBOOK_ID) -> dict:
    return {"id": notebook_id}


def _fake_memory_row(
    entry_id: str = ENTRY_ID,
    notebook_id: str = NOTEBOOK_ID,
    memory_type: str = "fact",
    content: str = "User prefers short answers.",
    metadata: str = None,
    tags: str = None,
) -> dict:
    now = datetime.utcnow().isoformat()
    return {
        "id": entry_id,
        "notebook_id": notebook_id,
        "memory_type": memory_type,
        "content": content,
        "metadata": metadata,
        "tags": tags,
        "created": now,
        "updated": now,
    }


# ============================================================================
# Create Memory
# ============================================================================

class TestCreateMemory:
    """Tests for POST /api/memory/{notebook_id}."""

    @patch("api.routers.agent_memory.repo_execute", new_callable=AsyncMock)
    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    def test_create_memory_success(self, mock_query, mock_execute, client):
        mock_query.return_value = [_fake_notebook_row()]

        response = client.post(
            f"/api/memory/{NOTEBOOK_ID}",
            json={
                "memory_type": "fact",
                "content": "User prefers concise answers.",
                "tags": ["preference", "formatting"],
                "metadata": {"source": "conversation", "confidence": 0.9},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["notebook_id"] == NOTEBOOK_ID
        assert data["memory_type"] == "fact"
        assert data["content"] == "User prefers concise answers."
        assert data["tags"] == ["preference", "formatting"]
        assert data["metadata"]["confidence"] == 0.9
        assert "id" in data
        mock_execute.assert_called_once()

    @patch("api.routers.agent_memory.repo_execute", new_callable=AsyncMock)
    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    def test_create_memory_minimal(self, mock_query, mock_execute, client):
        mock_query.return_value = [_fake_notebook_row()]

        response = client.post(
            f"/api/memory/{NOTEBOOK_ID}",
            json={
                "memory_type": "insight",
                "content": "Important finding.",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["memory_type"] == "insight"

    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    def test_create_memory_notebook_not_found(self, mock_query, client):
        mock_query.return_value = []

        response = client.post(
            "/api/memory/nonexistent",
            json={"memory_type": "fact", "content": "Test"},
        )

        assert response.status_code == 404
        assert "Notebook not found" in response.json()["detail"]

    def test_create_memory_invalid_type(self, client):
        response = client.post(
            f"/api/memory/{NOTEBOOK_ID}",
            json={"memory_type": "invalid_type", "content": "Test"},
        )
        assert response.status_code == 422

    def test_create_memory_missing_content(self, client):
        response = client.post(
            f"/api/memory/{NOTEBOOK_ID}",
            json={"memory_type": "fact"},
        )
        assert response.status_code == 422

    def test_create_memory_empty_content(self, client):
        response = client.post(
            f"/api/memory/{NOTEBOOK_ID}",
            json={"memory_type": "fact", "content": ""},
        )
        assert response.status_code == 422

    @patch("api.routers.agent_memory.repo_execute", new_callable=AsyncMock)
    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    def test_create_all_memory_types(self, mock_query, mock_execute, client):
        """All MemoryType enum values should be accepted."""
        mock_query.return_value = [_fake_notebook_row()]

        for mem_type in ["fact", "preference", "context", "conversation", "insight"]:
            response = client.post(
                f"/api/memory/{NOTEBOOK_ID}",
                json={"memory_type": mem_type, "content": f"Test {mem_type}"},
            )
            assert response.status_code == 201, f"Failed for type: {mem_type}"
            assert response.json()["memory_type"] == mem_type


# ============================================================================
# List Memories
# ============================================================================

class TestListMemories:
    """Tests for GET /api/memory/{notebook_id}."""

    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    def test_list_memories(self, mock_query, client):
        mock_query.side_effect = [
            [_fake_notebook_row()],          # verify notebook
            [{"count": 2}],                  # count query
            [_fake_memory_row("m1"), _fake_memory_row("m2")],  # data query
        ]

        response = client.get(f"/api/memory/{NOTEBOOK_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["entries"]) == 2

    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    def test_list_memories_with_type_filter(self, mock_query, client):
        mock_query.side_effect = [
            [_fake_notebook_row()],
            [{"count": 1}],
            [_fake_memory_row(memory_type="preference")],
        ]

        response = client.get(f"/api/memory/{NOTEBOOK_ID}?memory_type=preference")
        assert response.status_code == 200

        # Verify the SQL included the filter
        count_call = mock_query.call_args_list[1]
        sql = count_call[0][0]
        assert "memory_type" in sql

    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    def test_list_memories_pagination(self, mock_query, client):
        mock_query.side_effect = [
            [_fake_notebook_row()],
            [{"count": 50}],
            [_fake_memory_row()],
        ]

        response = client.get(f"/api/memory/{NOTEBOOK_ID}?limit=10&offset=20")
        assert response.status_code == 200

        # Verify pagination params
        data_call = mock_query.call_args_list[2]
        params = data_call[0][1]
        assert params["limit"] == 10
        assert params["offset"] == 20

    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    def test_list_memories_empty(self, mock_query, client):
        mock_query.side_effect = [
            [_fake_notebook_row()],
            [{"count": 0}],
            [],
        ]

        response = client.get(f"/api/memory/{NOTEBOOK_ID}")
        assert response.status_code == 200
        assert response.json() == {"entries": [], "total": 0}

    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    def test_list_memories_notebook_not_found(self, mock_query, client):
        mock_query.return_value = []

        response = client.get("/api/memory/nonexistent")
        assert response.status_code == 404


# ============================================================================
# Get Memory
# ============================================================================

class TestGetMemory:
    """Tests for GET /api/memory/{notebook_id}/{entry_id}."""

    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    def test_get_memory_success(self, mock_query, client):
        mock_query.return_value = [_fake_memory_row()]

        response = client.get(f"/api/memory/{NOTEBOOK_ID}/{ENTRY_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == ENTRY_ID
        assert data["content"] == "User prefers short answers."

    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    def test_get_memory_not_found(self, mock_query, client):
        mock_query.return_value = []

        response = client.get(f"/api/memory/{NOTEBOOK_ID}/nonexistent")
        assert response.status_code == 404
        assert "Memory entry not found" in response.json()["detail"]


# ============================================================================
# Update Memory
# ============================================================================

class TestUpdateMemory:
    """Tests for PUT /api/memory/{notebook_id}/{entry_id}."""

    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    @patch("api.routers.agent_memory.repo_update", new_callable=AsyncMock)
    def test_update_memory_content(self, mock_update, mock_query, client):
        original = _fake_memory_row()
        updated = {**original, "content": "Updated content"}
        mock_query.side_effect = [
            [original],   # verify exists
            [updated],    # refreshed record
        ]

        response = client.put(
            f"/api/memory/{NOTEBOOK_ID}/{ENTRY_ID}",
            json={"content": "Updated content"},
        )

        assert response.status_code == 200
        assert response.json()["content"] == "Updated content"
        mock_update.assert_called_once()

    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    @patch("api.routers.agent_memory.repo_update", new_callable=AsyncMock)
    def test_update_memory_type(self, mock_update, mock_query, client):
        original = _fake_memory_row()
        updated = {**original, "memory_type": "preference"}
        mock_query.side_effect = [
            [original],
            [updated],
        ]

        response = client.put(
            f"/api/memory/{NOTEBOOK_ID}/{ENTRY_ID}",
            json={"memory_type": "preference"},
        )

        assert response.status_code == 200
        assert response.json()["memory_type"] == "preference"

    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    @patch("api.routers.agent_memory.repo_update", new_callable=AsyncMock)
    def test_update_memory_tags_and_metadata(self, mock_update, mock_query, client):
        original = _fake_memory_row()
        updated = {
            **original,
            "tags": json.dumps(["new-tag"]),
            "metadata": json.dumps({"updated": True}),
        }
        mock_query.side_effect = [
            [original],
            [updated],
        ]

        response = client.put(
            f"/api/memory/{NOTEBOOK_ID}/{ENTRY_ID}",
            json={"tags": ["new-tag"], "metadata": {"updated": True}},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["tags"] == ["new-tag"]
        assert data["metadata"]["updated"] is True

    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    def test_update_memory_not_found(self, mock_query, client):
        mock_query.return_value = []

        response = client.put(
            f"/api/memory/{NOTEBOOK_ID}/nonexistent",
            json={"content": "Updated"},
        )
        assert response.status_code == 404


# ============================================================================
# Delete Memory
# ============================================================================

class TestDeleteMemory:
    """Tests for DELETE /api/memory/{notebook_id}/{entry_id}."""

    @patch("api.routers.agent_memory.repo_delete", new_callable=AsyncMock)
    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    def test_delete_memory_success(self, mock_query, mock_delete, client):
        mock_query.return_value = [{"id": ENTRY_ID}]

        response = client.delete(f"/api/memory/{NOTEBOOK_ID}/{ENTRY_ID}")
        assert response.status_code == 200
        assert "deleted" in response.json()["message"]
        mock_delete.assert_called_once_with("agent_memory", ENTRY_ID)

    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    def test_delete_memory_not_found(self, mock_query, client):
        mock_query.return_value = []

        response = client.delete(f"/api/memory/{NOTEBOOK_ID}/nonexistent")
        assert response.status_code == 404


# ============================================================================
# Search Memory
# ============================================================================

class TestSearchMemory:
    """Tests for POST /api/memory/{notebook_id}/search."""

    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    def test_search_basic(self, mock_query, client):
        mock_query.side_effect = [
            [_fake_notebook_row()],
            [_fake_memory_row(content="User prefers short answers.")],
        ]

        response = client.post(
            f"/api/memory/{NOTEBOOK_ID}/search",
            json={"query": "prefers"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "prefers"
        assert data["total"] == 1
        assert len(data["results"]) == 1

    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    def test_search_with_type_filter(self, mock_query, client):
        mock_query.side_effect = [
            [_fake_notebook_row()],
            [_fake_memory_row(memory_type="preference")],
        ]

        response = client.post(
            f"/api/memory/{NOTEBOOK_ID}/search",
            json={"query": "user", "memory_type": "preference"},
        )

        assert response.status_code == 200

        # Verify type filter was added to SQL
        data_call = mock_query.call_args_list[1]
        sql = data_call[0][0]
        assert "memory_type" in sql

    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    def test_search_with_tags(self, mock_query, client):
        mock_query.side_effect = [
            [_fake_notebook_row()],
            [_fake_memory_row(tags=json.dumps(["formatting"]))],
        ]

        response = client.post(
            f"/api/memory/{NOTEBOOK_ID}/search",
            json={"query": "user", "tags": ["formatting"]},
        )

        assert response.status_code == 200

        # Verify tag conditions were added
        data_call = mock_query.call_args_list[1]
        sql = data_call[0][0]
        assert "tags LIKE" in sql

    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    def test_search_with_multiple_tags(self, mock_query, client):
        mock_query.side_effect = [
            [_fake_notebook_row()],
            [],
        ]

        response = client.post(
            f"/api/memory/{NOTEBOOK_ID}/search",
            json={"query": "test", "tags": ["tag1", "tag2", "tag3"]},
        )

        assert response.status_code == 200

        # Verify OR conditions for tags
        data_call = mock_query.call_args_list[1]
        sql = data_call[0][0]
        assert "tag_0" in sql
        assert "tag_1" in sql
        assert "tag_2" in sql
        assert "OR" in sql

    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    def test_search_with_limit(self, mock_query, client):
        mock_query.side_effect = [
            [_fake_notebook_row()],
            [],
        ]

        response = client.post(
            f"/api/memory/{NOTEBOOK_ID}/search",
            json={"query": "test", "limit": 5},
        )

        assert response.status_code == 200
        data_call = mock_query.call_args_list[1]
        params = data_call[0][1]
        assert params["limit"] == 5

    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    def test_search_no_results(self, mock_query, client):
        mock_query.side_effect = [
            [_fake_notebook_row()],
            [],
        ]

        response = client.post(
            f"/api/memory/{NOTEBOOK_ID}/search",
            json={"query": "nonexistent"},
        )

        assert response.status_code == 200
        assert response.json()["total"] == 0
        assert response.json()["results"] == []

    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    def test_search_notebook_not_found(self, mock_query, client):
        mock_query.return_value = []

        response = client.post(
            "/api/memory/nonexistent/search",
            json={"query": "test"},
        )
        assert response.status_code == 404

    def test_search_missing_query(self, client):
        response = client.post(
            f"/api/memory/{NOTEBOOK_ID}/search",
            json={},
        )
        assert response.status_code == 422

    def test_search_empty_query(self, client):
        response = client.post(
            f"/api/memory/{NOTEBOOK_ID}/search",
            json={"query": ""},
        )
        assert response.status_code == 422


# ============================================================================
# JSON Field Parsing
# ============================================================================

class TestMemoryJSONParsing:
    """Test that JSON string fields are properly deserialized in responses."""

    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    def test_metadata_json_string_parsed(self, mock_query, client):
        row = _fake_memory_row()
        row["metadata"] = json.dumps({"source": "agent", "confidence": 0.95})
        mock_query.return_value = [row]

        response = client.get(f"/api/memory/{NOTEBOOK_ID}/{ENTRY_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["source"] == "agent"
        assert data["metadata"]["confidence"] == 0.95

    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    def test_tags_json_string_parsed(self, mock_query, client):
        row = _fake_memory_row()
        row["tags"] = json.dumps(["important", "verified"])
        mock_query.return_value = [row]

        response = client.get(f"/api/memory/{NOTEBOOK_ID}/{ENTRY_ID}")
        assert response.status_code == 200
        assert response.json()["tags"] == ["important", "verified"]

    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    def test_null_metadata_and_tags(self, mock_query, client):
        row = _fake_memory_row()
        row["metadata"] = None
        row["tags"] = None
        mock_query.return_value = [row]

        response = client.get(f"/api/memory/{NOTEBOOK_ID}/{ENTRY_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["metadata"] is None
        assert data["tags"] is None

    @patch("api.routers.agent_memory.repo_query", new_callable=AsyncMock)
    def test_invalid_json_metadata_returns_none(self, mock_query, client):
        row = _fake_memory_row()
        row["metadata"] = "not-valid-json"
        row["tags"] = "also-not-json"
        mock_query.return_value = [row]

        response = client.get(f"/api/memory/{NOTEBOOK_ID}/{ENTRY_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["metadata"] is None
        assert data["tags"] is None
