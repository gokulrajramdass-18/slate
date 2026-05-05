"""
Tests for Agent Management API endpoints (/api/agents).

Tests cover:
- Team CRUD (create, list, get, delete)
- Agent spawning and listing within teams
- Agent deletion
- Task listing and retrieval
- Input validation (missing fields, invalid roles)
- 404 handling for missing teams/agents/tasks
- Cascade deletion (team -> agents -> tasks)
- Query parameters (notebook_id filter, status filter)
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


def _fake_notebook_row(notebook_id: str = "nb-123") -> dict:
    """Return a fake notebook row for verify-notebook queries."""
    return {"id": notebook_id}


def _fake_team_row(
    team_id: str = "team-abc",
    notebook_id: str = "nb-123",
    name: str = "Research Team",
) -> dict:
    now = datetime.utcnow().isoformat()
    return {
        "id": team_id,
        "name": name,
        "notebook_id": notebook_id,
        "description": "Test team",
        "status": "idle",
        "config": None,
        "created": now,
        "updated": now,
    }


def _fake_agent_row(
    agent_id: str = "agent-1",
    team_id: str = "team-abc",
    role: str = "researcher",
) -> dict:
    return {
        "id": agent_id,
        "team_id": team_id,
        "role": role,
        "name": f"{role.title()} Agent",
        "status": "idle",
        "system_prompt": None,
        "model_override": None,
        "tool_ids": None,
        "config": None,
        "last_active": None,
        "created": datetime.utcnow().isoformat(),
    }


def _fake_task_row(
    task_id: str = "task-1",
    team_id: str = "team-abc",
) -> dict:
    return {
        "id": task_id,
        "team_id": team_id,
        "assigned_agent_id": "agent-1",
        "task_type": "research",
        "description": "Find relevant sources",
        "status": "pending",
        "input_data": None,
        "output_data": None,
        "dependencies": None,
        "error": None,
        "started_at": None,
        "completed_at": None,
        "created": datetime.utcnow().isoformat(),
    }


# ============================================================================
# Team Endpoints
# ============================================================================

class TestCreateTeam:
    """Tests for POST /api/agents/teams."""

    @patch("api.routers.agents.repo_execute", new_callable=AsyncMock)
    @patch("api.routers.agents.repo_query", new_callable=AsyncMock)
    def test_create_team_success(self, mock_query, mock_execute, client):
        mock_query.return_value = [_fake_notebook_row()]

        response = client.post(
            "/api/agents/teams",
            json={
                "name": "Research Team",
                "notebook_id": "nb-123",
                "description": "A test team",
                "config": {"max_iterations": 10},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Research Team"
        assert data["notebook_id"] == "nb-123"
        assert data["status"] == "idle"
        assert data["agent_count"] == 0
        assert data["config"]["max_iterations"] == 10
        assert "id" in data

    @patch("api.routers.agents.repo_query", new_callable=AsyncMock)
    def test_create_team_notebook_not_found(self, mock_query, client):
        mock_query.return_value = []

        response = client.post(
            "/api/agents/teams",
            json={"name": "Team X", "notebook_id": "nonexistent"},
        )

        assert response.status_code == 404
        assert "Notebook not found" in response.json()["detail"]

    def test_create_team_missing_name(self, client):
        response = client.post(
            "/api/agents/teams",
            json={"notebook_id": "nb-123"},
        )
        assert response.status_code == 422

    def test_create_team_missing_notebook_id(self, client):
        response = client.post(
            "/api/agents/teams",
            json={"name": "Team"},
        )
        assert response.status_code == 422


class TestListTeams:
    """Tests for GET /api/agents/teams."""

    @patch("api.routers.agents.repo_query", new_callable=AsyncMock)
    def test_list_teams(self, mock_query, client):
        team_row = _fake_team_row()
        mock_query.side_effect = [
            [team_row],              # list teams
            [{"count": 2}],         # agent count for team
        ]

        response = client.get("/api/agents/teams")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["teams"][0]["name"] == "Research Team"
        assert data["teams"][0]["agent_count"] == 2

    @patch("api.routers.agents.repo_query", new_callable=AsyncMock)
    def test_list_teams_with_notebook_filter(self, mock_query, client):
        mock_query.side_effect = [
            [_fake_team_row()],      # filtered list
            [{"count": 0}],         # agent count
        ]

        response = client.get("/api/agents/teams?notebook_id=nb-123")
        assert response.status_code == 200

        # Verify the SQL included the WHERE clause
        first_call = mock_query.call_args_list[0]
        sql = first_call[0][0]
        assert "notebook_id" in sql

    @patch("api.routers.agents.repo_query", new_callable=AsyncMock)
    def test_list_teams_empty(self, mock_query, client):
        mock_query.return_value = []

        response = client.get("/api/agents/teams")
        assert response.status_code == 200
        assert response.json() == {"teams": [], "total": 0}


class TestGetTeam:
    """Tests for GET /api/agents/teams/{team_id}."""

    @patch("api.routers.agents.repo_query", new_callable=AsyncMock)
    def test_get_team_success(self, mock_query, client):
        mock_query.side_effect = [
            [_fake_team_row()],      # get team
            [{"count": 3}],         # agent count
        ]

        response = client.get("/api/agents/teams/team-abc")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "team-abc"
        assert data["agent_count"] == 3

    @patch("api.routers.agents.repo_query", new_callable=AsyncMock)
    def test_get_team_not_found(self, mock_query, client):
        mock_query.return_value = []

        response = client.get("/api/agents/teams/nonexistent")
        assert response.status_code == 404
        assert "Agent team not found" in response.json()["detail"]


class TestDeleteTeam:
    """Tests for DELETE /api/agents/teams/{team_id}."""

    @patch("api.routers.agents.repo_delete", new_callable=AsyncMock)
    @patch("api.routers.agents.repo_execute", new_callable=AsyncMock)
    @patch("api.routers.agents.repo_query", new_callable=AsyncMock)
    def test_delete_team_success(self, mock_query, mock_execute, mock_delete, client):
        mock_query.return_value = [_fake_team_row()]

        response = client.delete("/api/agents/teams/team-abc")
        assert response.status_code == 200
        assert "deleted" in response.json()["message"]

        # Should cascade delete tasks and agents first
        assert mock_execute.call_count == 2  # tasks + agents
        mock_delete.assert_called_once_with("agent_teams", "team-abc")

    @patch("api.routers.agents.repo_query", new_callable=AsyncMock)
    def test_delete_team_not_found(self, mock_query, client):
        mock_query.return_value = []

        response = client.delete("/api/agents/teams/nonexistent")
        assert response.status_code == 404


# ============================================================================
# Agent Endpoints
# ============================================================================

class TestSpawnAgent:
    """Tests for POST /api/agents/teams/{team_id}/spawn."""

    @patch("api.routers.agents.repo_update", new_callable=AsyncMock)
    @patch("api.routers.agents.repo_execute", new_callable=AsyncMock)
    @patch("api.routers.agents.repo_query", new_callable=AsyncMock)
    def test_spawn_agent_success(self, mock_query, mock_execute, mock_update, client):
        mock_query.return_value = [_fake_team_row()]

        response = client.post(
            "/api/agents/teams/team-abc/spawn",
            json={
                "role": "researcher",
                "name": "Source Finder",
                "system_prompt": "You find sources.",
                "tool_ids": ["tool-1", "tool-2"],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "researcher"
        assert data["name"] == "Source Finder"
        assert data["status"] == "idle"
        assert data["tool_ids"] == ["tool-1", "tool-2"]
        assert data["team_id"] == "team-abc"

    @patch("api.routers.agents.repo_update", new_callable=AsyncMock)
    @patch("api.routers.agents.repo_execute", new_callable=AsyncMock)
    @patch("api.routers.agents.repo_query", new_callable=AsyncMock)
    def test_spawn_agent_auto_name(self, mock_query, mock_execute, mock_update, client):
        mock_query.return_value = [_fake_team_row()]

        response = client.post(
            "/api/agents/teams/team-abc/spawn",
            json={"role": "analyst"},
        )

        assert response.status_code == 201
        assert response.json()["name"] == "Analyst Agent"

    @patch("api.routers.agents.repo_query", new_callable=AsyncMock)
    def test_spawn_agent_team_not_found(self, mock_query, client):
        mock_query.return_value = []

        response = client.post(
            "/api/agents/teams/nonexistent/spawn",
            json={"role": "researcher"},
        )
        assert response.status_code == 404

    def test_spawn_agent_invalid_role(self, client):
        response = client.post(
            "/api/agents/teams/team-abc/spawn",
            json={"role": "invalid_role"},
        )
        assert response.status_code == 422


class TestListAgents:
    """Tests for GET /api/agents/teams/{team_id}/agents."""

    @patch("api.routers.agents.repo_query", new_callable=AsyncMock)
    def test_list_agents(self, mock_query, client):
        team_row = _fake_team_row()
        agent_rows = [
            _fake_agent_row("a1", role="researcher"),
            _fake_agent_row("a2", role="analyst"),
        ]
        mock_query.side_effect = [
            [team_row],     # team exists
            agent_rows,     # agents list
        ]

        response = client.get("/api/agents/teams/team-abc/agents")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        roles = {a["role"] for a in data["agents"]}
        assert roles == {"researcher", "analyst"}

    @patch("api.routers.agents.repo_query", new_callable=AsyncMock)
    def test_list_agents_team_not_found(self, mock_query, client):
        mock_query.return_value = []

        response = client.get("/api/agents/teams/nonexistent/agents")
        assert response.status_code == 404


class TestDeleteAgent:
    """Tests for DELETE /api/agents/agents/{agent_id}."""

    @patch("api.routers.agents.repo_delete", new_callable=AsyncMock)
    @patch("api.routers.agents.repo_query", new_callable=AsyncMock)
    def test_delete_agent_success(self, mock_query, mock_delete, client):
        mock_query.return_value = [_fake_agent_row()]

        response = client.delete("/api/agents/agents/agent-1")
        assert response.status_code == 200
        assert "deleted" in response.json()["message"]
        mock_delete.assert_called_once_with("agents", "agent-1")

    @patch("api.routers.agents.repo_query", new_callable=AsyncMock)
    def test_delete_agent_not_found(self, mock_query, client):
        mock_query.return_value = []

        response = client.delete("/api/agents/agents/nonexistent")
        assert response.status_code == 404


# ============================================================================
# Task Endpoints
# ============================================================================

class TestListTasks:
    """Tests for GET /api/agents/teams/{team_id}/tasks."""

    @patch("api.routers.agents.repo_query", new_callable=AsyncMock)
    def test_list_tasks(self, mock_query, client):
        mock_query.side_effect = [
            [_fake_team_row()],                    # team exists
            [_fake_task_row("t1"), _fake_task_row("t2")],  # tasks
        ]

        response = client.get("/api/agents/teams/team-abc/tasks")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

    @patch("api.routers.agents.repo_query", new_callable=AsyncMock)
    def test_list_tasks_with_status_filter(self, mock_query, client):
        mock_query.side_effect = [
            [_fake_team_row()],
            [_fake_task_row()],
        ]

        response = client.get("/api/agents/teams/team-abc/tasks?status=pending")
        assert response.status_code == 200

        # Verify the SQL included status filter
        second_call = mock_query.call_args_list[1]
        sql = second_call[0][0]
        assert "status" in sql

    @patch("api.routers.agents.repo_query", new_callable=AsyncMock)
    def test_list_tasks_team_not_found(self, mock_query, client):
        mock_query.return_value = []

        response = client.get("/api/agents/teams/nonexistent/tasks")
        assert response.status_code == 404


class TestGetTask:
    """Tests for GET /api/agents/tasks/{task_id}."""

    @patch("api.routers.agents.repo_query", new_callable=AsyncMock)
    def test_get_task_success(self, mock_query, client):
        mock_query.return_value = [_fake_task_row()]

        response = client.get("/api/agents/tasks/task-1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "task-1"
        assert data["task_type"] == "research"
        assert data["status"] == "pending"

    @patch("api.routers.agents.repo_query", new_callable=AsyncMock)
    def test_get_task_not_found(self, mock_query, client):
        mock_query.return_value = []

        response = client.get("/api/agents/tasks/nonexistent")
        assert response.status_code == 404


# ============================================================================
# JSON Field Parsing
# ============================================================================

class TestJSONFieldParsing:
    """Test that JSON string fields are properly deserialized."""

    @patch("api.routers.agents.repo_query", new_callable=AsyncMock)
    def test_agent_json_fields(self, mock_query, client):
        row = _fake_agent_row()
        row["tool_ids"] = json.dumps(["tool-a", "tool-b"])
        row["config"] = json.dumps({"temperature": 0.7})

        mock_query.side_effect = [
            [_fake_team_row()],
            [row],
        ]

        response = client.get("/api/agents/teams/team-abc/agents")
        assert response.status_code == 200
        agent = response.json()["agents"][0]
        assert agent["tool_ids"] == ["tool-a", "tool-b"]
        assert agent["config"]["temperature"] == 0.7

    @patch("api.routers.agents.repo_query", new_callable=AsyncMock)
    def test_task_json_fields(self, mock_query, client):
        row = _fake_task_row()
        row["input_data"] = json.dumps({"query": "test"})
        row["output_data"] = json.dumps({"results": []})
        row["dependencies"] = json.dumps(["task-0"])

        mock_query.return_value = [row]

        response = client.get("/api/agents/tasks/task-1")
        assert response.status_code == 200
        data = response.json()
        assert data["input_data"]["query"] == "test"
        assert data["output_data"]["results"] == []
        assert data["dependencies"] == ["task-0"]

    @patch("api.routers.agents.repo_query", new_callable=AsyncMock)
    def test_team_config_json_parsing(self, mock_query, client):
        row = _fake_team_row()
        row["config"] = json.dumps({"timeout": 300})

        mock_query.side_effect = [
            [row],           # get team
            [{"count": 0}],  # agent count
        ]

        response = client.get("/api/agents/teams/team-abc")
        assert response.status_code == 200
        assert response.json()["config"]["timeout"] == 300
