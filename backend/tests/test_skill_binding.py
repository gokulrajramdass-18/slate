"""
Unit tests for SkillBinding

Tests skill binding to agents, roles, and teams, with priority resolution.
"""

import pytest
import json
from unittest.mock import AsyncMock, patch

from open_notebook.agents.skills.binding import (
    SkillBinding,
    bind_skill_to_agent,
    bind_skill_to_role,
    bind_skill_to_team,
    get_agent_skills,
    get_team_skills,
    unbind_skill,
    update_binding_config,
    toggle_binding
)


@pytest.fixture
async def mock_db():
    """Mock database operations."""
    with patch('open_notebook.agents.skills.binding.repo_execute') as mock_execute, \
         patch('open_notebook.agents.skills.binding.repo_query') as mock_query:
        # Default empty results
        mock_query.return_value = []
        yield {"execute": mock_execute, "query": mock_query}


class TestSkillBinding:
    """Test SkillBinding dataclass."""

    def test_create_binding(self):
        """Test creating a SkillBinding."""
        binding = SkillBinding(
            id="binding-123",
            skill_id="skill-456",
            agent_id="agent-789",
            config={"param": "value"}
        )

        assert binding.id == "binding-123"
        assert binding.skill_id == "skill-456"
        assert binding.agent_id == "agent-789"
        assert binding.config == {"param": "value"}
        assert binding.enabled is True
        assert binding.created is not None

    def test_binding_defaults(self):
        """Test SkillBinding default values."""
        binding = SkillBinding(
            id="binding-123",
            skill_id="skill-456"
        )

        assert binding.config == {}
        assert binding.enabled is True
        assert binding.created is not None
        assert binding.agent_id is None
        assert binding.role is None
        assert binding.team_id is None

    def test_binding_with_role(self):
        """Test creating a binding with role."""
        binding = SkillBinding(
            id="binding-123",
            skill_id="skill-456",
            role="analyst"
        )

        assert binding.role == "analyst"
        assert binding.agent_id is None
        assert binding.team_id is None

    def test_binding_with_team(self):
        """Test creating a binding with team."""
        binding = SkillBinding(
            id="binding-123",
            skill_id="skill-456",
            team_id="team-789"
        )

        assert binding.team_id == "team-789"
        assert binding.agent_id is None
        assert binding.role is None


class TestBindToAgent:
    """Test binding skills to agents."""

    @pytest.mark.asyncio
    async def test_bind_skill_to_agent(self, mock_db):
        """Test binding a skill to an agent."""
        binding = await bind_skill_to_agent(
            skill_id="skill-123",
            agent_id="agent-456",
            config={"limit": 10}
        )

        # Check binding properties
        assert binding.skill_id == "skill-123"
        assert binding.agent_id == "agent-456"
        assert binding.config == {"limit": 10}
        assert binding.enabled is True
        assert binding.id.startswith("binding-")

        # Check database was called
        mock_db["execute"].assert_called_once()
        call_args = mock_db["execute"].call_args
        assert "INSERT INTO agent_skill_bindings" in call_args[0][0]
        assert call_args[0][1]["skill_id"] == "skill-123"
        assert call_args[0][1]["agent_id"] == "agent-456"

    @pytest.mark.asyncio
    async def test_bind_without_config(self, mock_db):
        """Test binding without config uses empty dict."""
        binding = await bind_skill_to_agent(
            skill_id="skill-123",
            agent_id="agent-456"
        )

        assert binding.config == {}

    @pytest.mark.asyncio
    async def test_bind_config_serialized(self, mock_db):
        """Test that config is JSON serialized in database."""
        await bind_skill_to_agent(
            skill_id="skill-123",
            agent_id="agent-456",
            config={"strategy": "hybrid", "limit": 20}
        )

        call_args = mock_db["execute"].call_args
        config_value = call_args[0][1]["config"]
        # Should be JSON string
        assert isinstance(config_value, str)
        # Can be deserialized
        parsed = json.loads(config_value)
        assert parsed == {"strategy": "hybrid", "limit": 20}


class TestBindToRole:
    """Test binding skills to roles."""

    @pytest.mark.asyncio
    async def test_bind_skill_to_role(self, mock_db):
        """Test binding a skill to a role."""
        binding = await bind_skill_to_role(
            skill_id="skill-123",
            role="analyst",
            config={"threshold": 0.8}
        )

        assert binding.skill_id == "skill-123"
        assert binding.role == "analyst"
        assert binding.config == {"threshold": 0.8}
        assert binding.agent_id is None
        assert binding.team_id is None

        # Check database
        mock_db["execute"].assert_called_once()
        call_args = mock_db["execute"].call_args
        assert call_args[0][1]["role"] == "analyst"

    @pytest.mark.asyncio
    async def test_bind_role_without_config(self, mock_db):
        """Test binding role without config."""
        binding = await bind_skill_to_role(
            skill_id="skill-123",
            role="researcher"
        )

        assert binding.config == {}


class TestBindToTeam:
    """Test binding skills to teams."""

    @pytest.mark.asyncio
    async def test_bind_skill_to_team(self, mock_db):
        """Test binding a skill to a team."""
        binding = await bind_skill_to_team(
            skill_id="skill-123",
            team_id="team-456",
            config={"mode": "collaborative"}
        )

        assert binding.skill_id == "skill-123"
        assert binding.team_id == "team-456"
        assert binding.config == {"mode": "collaborative"}
        assert binding.agent_id is None
        assert binding.role is None

        # Check database
        mock_db["execute"].assert_called_once()
        call_args = mock_db["execute"].call_args
        assert call_args[0][1]["team_id"] == "team-456"


class TestGetAgentSkills:
    """Test retrieving skills for an agent."""

    @pytest.mark.asyncio
    async def test_get_agent_skills(self, mock_db):
        """Test getting skills for an agent (direct + role bindings)."""
        # Mock database return
        mock_db["query"].return_value = [
            {
                "id": "binding-1",
                "skill_id": "skill-1",
                "agent_id": "agent-123",
                "role": None,
                "team_id": None,
                "config": '{"limit": 10}',
                "enabled": 1,
                "created": "2026-04-02T10:00:00"
            },
            {
                "id": "binding-2",
                "skill_id": "skill-2",
                "agent_id": None,
                "role": "analyst",
                "team_id": None,
                "config": '{"strategy": "hybrid"}',
                "enabled": 1,
                "created": "2026-04-02T09:00:00"
            }
        ]

        bindings = await get_agent_skills("agent-123", "analyst")

        # Should get 2 bindings: direct + role
        assert len(bindings) == 2

        # Check first binding (direct)
        assert bindings[0].id == "binding-1"
        assert bindings[0].skill_id == "skill-1"
        assert bindings[0].agent_id == "agent-123"
        assert bindings[0].config == {"limit": 10}

        # Check second binding (role)
        assert bindings[1].id == "binding-2"
        assert bindings[1].skill_id == "skill-2"
        assert bindings[1].role == "analyst"
        assert bindings[1].config == {"strategy": "hybrid"}

        # Check query was called correctly
        mock_db["query"].assert_called_once()
        call_args = mock_db["query"].call_args
        assert "agent_id = :agent_id OR role = :role" in call_args[0][0]
        assert call_args[0][1]["agent_id"] == "agent-123"
        assert call_args[0][1]["role"] == "analyst"

    @pytest.mark.asyncio
    async def test_get_agent_skills_empty(self, mock_db):
        """Test getting skills when agent has none."""
        mock_db["query"].return_value = []

        bindings = await get_agent_skills("agent-123", "analyst")

        assert len(bindings) == 0

    @pytest.mark.asyncio
    async def test_get_agent_skills_only_enabled(self, mock_db):
        """Test that only enabled bindings are returned."""
        mock_db["query"].return_value = []  # Would filter at DB level

        await get_agent_skills("agent-123", "analyst")

        # Check query filters by enabled
        call_args = mock_db["query"].call_args
        assert "enabled = 1" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_agent_skills_ordered_by_created(self, mock_db):
        """Test that bindings are ordered by creation time."""
        mock_db["query"].return_value = []

        await get_agent_skills("agent-123", "analyst")

        # Check query orders by created
        call_args = mock_db["query"].call_args
        assert "ORDER BY created DESC" in call_args[0][0]


class TestGetTeamSkills:
    """Test retrieving skills for a team."""

    @pytest.mark.asyncio
    async def test_get_team_skills(self, mock_db):
        """Test getting skills for a team."""
        mock_db["query"].return_value = [
            {
                "id": "binding-1",
                "skill_id": "skill-1",
                "agent_id": None,
                "role": None,
                "team_id": "team-456",
                "config": '{"mode": "team"}',
                "enabled": 1,
                "created": "2026-04-02T10:00:00"
            }
        ]

        bindings = await get_team_skills("team-456")

        assert len(bindings) == 1
        assert bindings[0].team_id == "team-456"
        assert bindings[0].skill_id == "skill-1"

        # Check query
        mock_db["query"].assert_called_once()
        call_args = mock_db["query"].call_args
        assert "team_id = :team_id" in call_args[0][0]
        assert call_args[0][1]["team_id"] == "team-456"

    @pytest.mark.asyncio
    async def test_get_team_skills_empty(self, mock_db):
        """Test getting skills when team has none."""
        mock_db["query"].return_value = []

        bindings = await get_team_skills("team-456")

        assert len(bindings) == 0


class TestUnbindSkill:
    """Test removing skill bindings."""

    @pytest.mark.asyncio
    async def test_unbind_skill(self, mock_db):
        """Test removing a binding."""
        result = await unbind_skill("binding-123")

        assert result is True

        # Check database was called
        mock_db["execute"].assert_called_once()
        call_args = mock_db["execute"].call_args
        assert "DELETE FROM agent_skill_bindings" in call_args[0][0]
        assert call_args[0][1]["id"] == "binding-123"


class TestUpdateBindingConfig:
    """Test updating binding configuration."""

    @pytest.mark.asyncio
    async def test_update_binding_config(self, mock_db):
        """Test updating a binding's config."""
        new_config = {"strategy": "vector", "limit": 50}
        result = await update_binding_config("binding-123", new_config)

        assert result is True

        # Check database was called
        mock_db["execute"].assert_called_once()
        call_args = mock_db["execute"].call_args
        assert "UPDATE agent_skill_bindings" in call_args[0][0]
        assert "SET config = :config" in call_args[0][0]
        assert call_args[0][1]["id"] == "binding-123"

        # Check config is JSON serialized
        config_value = call_args[0][1]["config"]
        assert isinstance(config_value, str)
        parsed = json.loads(config_value)
        assert parsed == new_config


class TestToggleBinding:
    """Test enabling/disabling bindings."""

    @pytest.mark.asyncio
    async def test_enable_binding(self, mock_db):
        """Test enabling a binding."""
        result = await toggle_binding("binding-123", enabled=True)

        assert result is True

        mock_db["execute"].assert_called_once()
        call_args = mock_db["execute"].call_args
        assert "UPDATE agent_skill_bindings" in call_args[0][0]
        assert "SET enabled = :enabled" in call_args[0][0]
        assert call_args[0][1]["enabled"] == 1

    @pytest.mark.asyncio
    async def test_disable_binding(self, mock_db):
        """Test disabling a binding."""
        result = await toggle_binding("binding-123", enabled=False)

        assert result is True

        call_args = mock_db["execute"].call_args
        assert call_args[0][1]["enabled"] == 0


class TestPriorityResolution:
    """Test priority resolution when multiple bindings exist."""

    @pytest.mark.asyncio
    async def test_direct_binding_returned_first(self, mock_db):
        """Test that direct bindings appear before role bindings."""
        # Most recent binding first (direct), then older role binding
        mock_db["query"].return_value = [
            {
                "id": "binding-direct",
                "skill_id": "skill-1",
                "agent_id": "agent-123",
                "role": None,
                "team_id": None,
                "config": '{"source": "direct"}',
                "enabled": 1,
                "created": "2026-04-02T10:00:00"
            },
            {
                "id": "binding-role",
                "skill_id": "skill-1",
                "agent_id": None,
                "role": "analyst",
                "team_id": None,
                "config": '{"source": "role"}',
                "enabled": 1,
                "created": "2026-04-02T09:00:00"
            }
        ]

        bindings = await get_agent_skills("agent-123", "analyst")

        # Direct binding should be first (newer timestamp)
        assert len(bindings) == 2
        assert bindings[0].id == "binding-direct"
        assert bindings[0].config["source"] == "direct"
        assert bindings[1].id == "binding-role"
        assert bindings[1].config["source"] == "role"

    @pytest.mark.asyncio
    async def test_config_override_precedence(self, mock_db):
        """Test that direct bindings can override role config."""
        mock_db["query"].return_value = [
            {
                "id": "binding-direct",
                "skill_id": "skill-1",
                "agent_id": "agent-123",
                "role": None,
                "team_id": None,
                "config": '{"limit": 50}',  # Override
                "enabled": 1,
                "created": "2026-04-02T10:00:00"
            },
            {
                "id": "binding-role",
                "skill_id": "skill-1",
                "agent_id": None,
                "role": "analyst",
                "team_id": None,
                "config": '{"limit": 10}',  # Default
                "enabled": 1,
                "created": "2026-04-02T09:00:00"
            }
        ]

        bindings = await get_agent_skills("agent-123", "analyst")

        # Both bindings exist, but direct one is first
        assert bindings[0].config["limit"] == 50
        assert bindings[1].config["limit"] == 10


class TestConfigSerialization:
    """Test JSON serialization of config."""

    @pytest.mark.asyncio
    async def test_complex_config_serialization(self, mock_db):
        """Test that complex config is properly serialized."""
        complex_config = {
            "strategies": ["hybrid", "vector"],
            "thresholds": {"min": 0.5, "max": 0.9},
            "enabled": True,
            "count": 42
        }

        await bind_skill_to_agent(
            skill_id="skill-123",
            agent_id="agent-456",
            config=complex_config
        )

        call_args = mock_db["execute"].call_args
        config_str = call_args[0][1]["config"]

        # Verify it's a string
        assert isinstance(config_str, str)

        # Verify it can be deserialized back
        parsed = json.loads(config_str)
        assert parsed == complex_config

    @pytest.mark.asyncio
    async def test_config_deserialization_in_get(self, mock_db):
        """Test that config is deserialized when retrieving bindings."""
        mock_db["query"].return_value = [
            {
                "id": "binding-1",
                "skill_id": "skill-1",
                "agent_id": "agent-123",
                "role": None,
                "team_id": None,
                "config": '{"nested": {"key": "value"}, "array": [1, 2, 3]}',
                "enabled": 1,
                "created": "2026-04-02T10:00:00"
            }
        ]

        bindings = await get_agent_skills("agent-123", "analyst")

        # Config should be deserialized dict
        assert isinstance(bindings[0].config, dict)
        assert bindings[0].config["nested"]["key"] == "value"
        assert bindings[0].config["array"] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_empty_config_handling(self, mock_db):
        """Test handling of null/empty config."""
        mock_db["query"].return_value = [
            {
                "id": "binding-1",
                "skill_id": "skill-1",
                "agent_id": "agent-123",
                "role": None,
                "team_id": None,
                "config": None,  # Null in database
                "enabled": 1,
                "created": "2026-04-02T10:00:00"
            }
        ]

        bindings = await get_agent_skills("agent-123", "analyst")

        # Should default to empty dict
        assert bindings[0].config == {}
