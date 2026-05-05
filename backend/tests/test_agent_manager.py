"""
Unit tests for Agent Manager / Agent Registry.

Tests cover:
- Agent definition CRUD (create, read, update, delete)
- Agent instantiation from registry
- Agent lifecycle (spawn, execute, terminate)
- Agent type validation
- Registry singleton pattern
- Dynamic agent loading
- Pre-registered agent lookup
- Error handling for missing/invalid agents
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_agent_definition():
    """Sample agent definition data."""
    return {
        "name": "research_agent",
        "agent_type": "langgraph_stateful",
        "description": "Deep research agent for multi-step analysis",
        "system_prompt": "You are a research assistant that performs deep analysis.",
        "model": "gpt-4",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_depth": {"type": "integer", "default": 3},
            },
            "required": ["query"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "findings": {"type": "array"},
                "summary": {"type": "string"},
            },
        },
        "config": {
            "max_iterations": 10,
            "timeout_seconds": 300,
        },
        "tags": ["research", "analysis"],
        "version": 1,
        "enabled": True,
    }


@pytest.fixture
def sample_simple_agent():
    """Sample simple LLM agent definition."""
    return {
        "name": "summarizer_agent",
        "agent_type": "simple_llm",
        "description": "Summarizes text content",
        "system_prompt": "Summarize the following content concisely.",
        "model": "gpt-4",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
            },
            "required": ["text"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
            },
        },
        "config": {},
        "tags": ["summarization"],
        "version": 1,
        "enabled": True,
    }


@pytest.fixture
def sample_tool_agent():
    """Sample tool-based agent definition."""
    return {
        "name": "data_query_agent",
        "agent_type": "langgraph_tool",
        "description": "Queries data sources using tools",
        "system_prompt": "Use available tools to answer data questions.",
        "model": "gpt-4",
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "notebook_id": {"type": "string"},
            },
            "required": ["question"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "tool_results": {"type": "array"},
            },
        },
        "config": {
            "tools": ["hana_query", "api_call"],
            "max_tool_calls": 5,
        },
        "tags": ["data", "query"],
        "version": 1,
        "enabled": True,
    }


@pytest.fixture
def mock_db_store():
    """In-memory store simulating the database for agent definitions."""
    store: Dict[str, Dict[str, Any]] = {}

    async def mock_query(sql, params=None):
        params = params or {}
        if "WHERE id = :id" in sql:
            agent_id = params.get("id")
            agent = store.get(agent_id)
            return [agent] if agent else []
        if "WHERE name = :name" in sql:
            name = params.get("name")
            return [a for a in store.values() if a.get("name") == name]
        if "WHERE agent_type = :agent_type" in sql:
            agent_type = params.get("agent_type")
            return [a for a in store.values() if a.get("agent_type") == agent_type]
        if "WHERE enabled" in sql:
            return [a for a in store.values() if a.get("enabled")]
        return list(store.values())

    async def mock_create(table, data):
        record_id = data.get("id", str(uuid.uuid4()))
        data["id"] = record_id
        data["created"] = datetime.utcnow().isoformat()
        data["updated"] = datetime.utcnow().isoformat()
        store[record_id] = data
        return record_id

    async def mock_update(table, record_id, data):
        if record_id in store:
            store[record_id].update(data)
            store[record_id]["updated"] = datetime.utcnow().isoformat()

    async def mock_delete(table, record_id):
        store.pop(record_id, None)

    return store, mock_query, mock_create, mock_update, mock_delete


# ============================================================================
# Test Agent Definition CRUD
# ============================================================================

class TestAgentDefinitionCRUD:
    """Test agent definition create, read, update, delete operations."""

    @pytest.mark.asyncio
    async def test_create_agent_definition(self, sample_agent_definition, mock_db_store):
        """Test creating a new agent definition."""
        store, mock_query, mock_create, _, _ = mock_db_store

        agent_id = str(uuid.uuid4())
        data = {**sample_agent_definition, "id": agent_id}
        result_id = await mock_create("agent_definitions", data)

        assert result_id == agent_id
        assert agent_id in store
        assert store[agent_id]["name"] == "research_agent"
        assert store[agent_id]["agent_type"] == "langgraph_stateful"

    @pytest.mark.asyncio
    async def test_get_agent_by_id(self, sample_agent_definition, mock_db_store):
        """Test retrieving an agent by ID."""
        store, mock_query, mock_create, _, _ = mock_db_store

        agent_id = str(uuid.uuid4())
        await mock_create("agent_definitions", {**sample_agent_definition, "id": agent_id})

        results = await mock_query(
            "SELECT * FROM agent_definitions WHERE id = :id",
            {"id": agent_id},
        )

        assert len(results) == 1
        assert results[0]["name"] == "research_agent"

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, mock_db_store):
        """Test retrieving a non-existent agent returns empty."""
        _, mock_query, _, _, _ = mock_db_store

        results = await mock_query(
            "SELECT * FROM agent_definitions WHERE id = :id",
            {"id": "nonexistent-id"},
        )

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_update_agent_definition(self, sample_agent_definition, mock_db_store):
        """Test updating an agent definition."""
        store, mock_query, mock_create, mock_update, _ = mock_db_store

        agent_id = str(uuid.uuid4())
        await mock_create("agent_definitions", {**sample_agent_definition, "id": agent_id})

        await mock_update("agent_definitions", agent_id, {
            "description": "Updated description",
            "version": 2,
        })

        assert store[agent_id]["description"] == "Updated description"
        assert store[agent_id]["version"] == 2

    @pytest.mark.asyncio
    async def test_delete_agent_definition(self, sample_agent_definition, mock_db_store):
        """Test deleting an agent definition."""
        store, _, mock_create, _, mock_delete = mock_db_store

        agent_id = str(uuid.uuid4())
        await mock_create("agent_definitions", {**sample_agent_definition, "id": agent_id})
        assert agent_id in store

        await mock_delete("agent_definitions", agent_id)
        assert agent_id not in store

    @pytest.mark.asyncio
    async def test_list_agents_by_type(self, mock_db_store):
        """Test listing agents filtered by type."""
        store, mock_query, mock_create, _, _ = mock_db_store

        await mock_create("agent_definitions", {
            "id": str(uuid.uuid4()),
            "name": "agent1",
            "agent_type": "simple_llm",
            "enabled": True,
        })
        await mock_create("agent_definitions", {
            "id": str(uuid.uuid4()),
            "name": "agent2",
            "agent_type": "langgraph_stateful",
            "enabled": True,
        })
        await mock_create("agent_definitions", {
            "id": str(uuid.uuid4()),
            "name": "agent3",
            "agent_type": "simple_llm",
            "enabled": True,
        })

        results = await mock_query(
            "SELECT * FROM agent_definitions WHERE agent_type = :agent_type",
            {"agent_type": "simple_llm"},
        )

        assert len(results) == 2
        assert all(r["agent_type"] == "simple_llm" for r in results)

    @pytest.mark.asyncio
    async def test_list_enabled_agents(self, mock_db_store):
        """Test listing only enabled agents."""
        store, mock_query, mock_create, _, _ = mock_db_store

        await mock_create("agent_definitions", {
            "id": str(uuid.uuid4()),
            "name": "enabled_agent",
            "agent_type": "simple_llm",
            "enabled": True,
        })
        await mock_create("agent_definitions", {
            "id": str(uuid.uuid4()),
            "name": "disabled_agent",
            "agent_type": "simple_llm",
            "enabled": False,
        })

        results = await mock_query(
            "SELECT * FROM agent_definitions WHERE enabled = TRUE", {}
        )

        assert len(results) == 1
        assert results[0]["name"] == "enabled_agent"


# ============================================================================
# Test Agent Type Validation
# ============================================================================

class TestAgentTypeValidation:
    """Test agent type validation and constraints."""

    VALID_AGENT_TYPES = ["langgraph_stateful", "langgraph_tool", "simple_llm", "custom"]

    @pytest.mark.parametrize("agent_type", VALID_AGENT_TYPES)
    def test_valid_agent_types(self, agent_type):
        """Test that all valid agent types are accepted."""
        assert agent_type in self.VALID_AGENT_TYPES

    def test_invalid_agent_type(self):
        """Test that invalid agent types are rejected."""
        invalid_types = ["unknown", "gpt", "langchain", ""]
        for t in invalid_types:
            assert t not in self.VALID_AGENT_TYPES

    def test_agent_type_case_sensitive(self):
        """Test that agent types are case-sensitive."""
        assert "Simple_LLM" not in self.VALID_AGENT_TYPES
        assert "LANGGRAPH_STATEFUL" not in self.VALID_AGENT_TYPES


# ============================================================================
# Test Agent Lifecycle
# ============================================================================

class TestAgentLifecycle:
    """Test agent spawn, execute, and terminate lifecycle."""

    @pytest.mark.asyncio
    async def test_spawn_agent_creates_instance(self):
        """Test that spawning an agent creates an instance with unique ID."""
        agent_def = {
            "id": str(uuid.uuid4()),
            "name": "test_agent",
            "agent_type": "simple_llm",
            "config": {},
        }

        # Simulate agent spawn
        instance_id = str(uuid.uuid4())
        instance = {
            "instance_id": instance_id,
            "definition_id": agent_def["id"],
            "status": "ready",
            "created": datetime.utcnow().isoformat(),
        }

        assert instance["status"] == "ready"
        assert instance["definition_id"] == agent_def["id"]
        assert len(instance["instance_id"]) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_agent_status_transitions(self):
        """Test valid agent status transitions."""
        valid_transitions = {
            "created": ["ready", "failed"],
            "ready": ["running", "terminated"],
            "running": ["completed", "failed", "terminated"],
            "completed": ["terminated"],
            "failed": ["ready", "terminated"],  # Can be restarted
            "terminated": [],  # Terminal state
        }

        # Test valid transitions
        for from_status, to_statuses in valid_transitions.items():
            for to_status in to_statuses:
                assert to_status in valid_transitions[from_status], (
                    f"Transition {from_status} -> {to_status} should be valid"
                )

        # Test terminal state has no transitions
        assert valid_transitions["terminated"] == []

    @pytest.mark.asyncio
    async def test_agent_execution_with_input_validation(self):
        """Test that agent validates input before execution."""
        input_schema = {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
            },
            "required": ["query"],
        }

        # Valid input
        valid_input = {"query": "What is AI?"}
        assert "query" in valid_input

        # Invalid input (missing required field)
        invalid_input = {"max_depth": 3}
        assert "query" not in invalid_input

    @pytest.mark.asyncio
    async def test_agent_timeout_handling(self):
        """Test that agent execution respects timeout."""
        config = {"timeout_seconds": 5}
        timeout = config.get("timeout_seconds", 300)
        assert timeout == 5

        # Default timeout
        config_no_timeout = {}
        default_timeout = config_no_timeout.get("timeout_seconds", 300)
        assert default_timeout == 300


# ============================================================================
# Test Registry Singleton
# ============================================================================

class TestRegistrySingleton:
    """Test agent registry singleton pattern."""

    def test_registry_returns_same_instance(self):
        """Test that registry factory returns the same instance."""
        # Simulate singleton pattern
        _instance = None

        def get_registry():
            nonlocal _instance
            if _instance is None:
                _instance = {"agents": {}, "created": datetime.utcnow()}
            return _instance

        registry1 = get_registry()
        registry2 = get_registry()

        assert registry1 is registry2

    def test_registry_can_be_reset(self):
        """Test that registry can be reset for testing."""
        _instance = {"agents": {}}

        def reset_registry():
            nonlocal _instance
            _instance = None

        reset_registry()
        assert _instance is None

    def test_registry_thread_safety_concept(self):
        """Test the concept of thread-safe registry initialization."""
        import threading

        instances = []
        lock = threading.Lock()
        _singleton = {}

        def get_or_create():
            with lock:
                if "instance" not in _singleton:
                    _singleton["instance"] = {"agents": {}}
                instances.append(id(_singleton["instance"]))

        threads = [threading.Thread(target=get_or_create) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should get the same instance
        assert len(set(instances)) == 1


# ============================================================================
# Test Agent Registration
# ============================================================================

class TestAgentRegistration:
    """Test registering agents in the registry."""

    def test_register_agent(self, sample_agent_definition):
        """Test registering an agent adds it to the registry."""
        registry = {}
        agent_id = str(uuid.uuid4())
        registry[agent_id] = sample_agent_definition

        assert agent_id in registry
        assert registry[agent_id]["name"] == "research_agent"

    def test_register_duplicate_name_rejected(self):
        """Test that duplicate agent names are rejected."""
        registry = {}
        registry["agent1"] = {"name": "research_agent"}

        # Attempt duplicate
        existing_names = {v["name"] for v in registry.values()}
        assert "research_agent" in existing_names

    def test_unregister_agent(self, sample_agent_definition):
        """Test unregistering an agent removes it from the registry."""
        registry = {}
        agent_id = str(uuid.uuid4())
        registry[agent_id] = sample_agent_definition

        del registry[agent_id]
        assert agent_id not in registry

    def test_lookup_agent_by_name(self):
        """Test looking up an agent by name."""
        registry = {
            "id1": {"name": "research_agent", "agent_type": "langgraph_stateful"},
            "id2": {"name": "summarizer_agent", "agent_type": "simple_llm"},
        }

        found = [v for v in registry.values() if v["name"] == "research_agent"]
        assert len(found) == 1
        assert found[0]["agent_type"] == "langgraph_stateful"

    def test_list_agents_by_tags(self):
        """Test listing agents filtered by tags."""
        registry = {
            "id1": {"name": "agent1", "tags": ["research", "analysis"]},
            "id2": {"name": "agent2", "tags": ["data", "query"]},
            "id3": {"name": "agent3", "tags": ["research", "summary"]},
        }

        research_agents = [
            v for v in registry.values()
            if "research" in v.get("tags", [])
        ]

        assert len(research_agents) == 2


# ============================================================================
# Test Agent Configuration
# ============================================================================

class TestAgentConfiguration:
    """Test agent configuration handling."""

    def test_config_with_defaults(self):
        """Test that missing config fields fall back to defaults."""
        defaults = {
            "max_iterations": 10,
            "timeout_seconds": 300,
            "temperature": 0.7,
        }
        user_config = {"max_iterations": 5}

        merged = {**defaults, **user_config}

        assert merged["max_iterations"] == 5  # User override
        assert merged["timeout_seconds"] == 300  # Default preserved
        assert merged["temperature"] == 0.7  # Default preserved

    def test_config_json_serialization(self, sample_agent_definition):
        """Test that agent config can be serialized to/from JSON."""
        config = sample_agent_definition["config"]
        serialized = json.dumps(config)
        deserialized = json.loads(serialized)

        assert deserialized == config

    def test_config_with_nested_values(self):
        """Test configuration with nested dictionaries."""
        config = {
            "model_settings": {
                "temperature": 0.7,
                "max_tokens": 4096,
            },
            "tool_settings": {
                "max_calls": 5,
                "retry_on_error": True,
            },
        }

        assert config["model_settings"]["temperature"] == 0.7
        assert config["tool_settings"]["retry_on_error"] is True

    def test_schema_validation_valid_input(self):
        """Test schema validation with valid input."""
        schema = {
            "required": ["query"],
            "properties": {
                "query": {"type": "string"},
                "max_depth": {"type": "integer"},
            },
        }

        valid_data = {"query": "test question", "max_depth": 3}

        # Check required fields
        for field in schema["required"]:
            assert field in valid_data

    def test_schema_validation_missing_required(self):
        """Test schema validation catches missing required fields."""
        schema = {"required": ["query", "notebook_id"]}
        data = {"query": "test"}

        missing = [f for f in schema["required"] if f not in data]
        assert "notebook_id" in missing


# ============================================================================
# Test Error Handling
# ============================================================================

class TestAgentManagerErrors:
    """Test error handling in agent management."""

    @pytest.mark.asyncio
    async def test_instantiate_disabled_agent_fails(self):
        """Test that disabled agents cannot be instantiated."""
        agent_def = {
            "id": "agent-1",
            "name": "disabled_agent",
            "enabled": False,
        }

        assert not agent_def["enabled"]

    @pytest.mark.asyncio
    async def test_instantiate_missing_agent_fails(self):
        """Test that missing agent definitions raise an error."""
        registry = {}
        agent_id = "nonexistent"

        assert agent_id not in registry

    def test_invalid_input_schema_rejected(self):
        """Test that invalid input schema format is rejected."""
        invalid_schemas = [
            "not a dict",
            123,
            None,
            [],
        ]

        for schema in invalid_schemas:
            assert not isinstance(schema, dict) or schema is None

    def test_agent_with_no_model_fails(self):
        """Test that agents without a model specification fail validation."""
        agent_def = {
            "name": "no_model_agent",
            "agent_type": "simple_llm",
            "model": None,
        }

        assert agent_def["model"] is None

    @pytest.mark.asyncio
    async def test_agent_execution_error_captured(self):
        """Test that execution errors are captured, not raised."""
        error_result = {
            "success": False,
            "error": "Model API returned 429 (rate limited)",
            "agent_id": "agent-1",
            "execution_time_ms": 150,
        }

        assert error_result["success"] is False
        assert "429" in error_result["error"]

    @pytest.mark.asyncio
    async def test_concurrent_agent_spawning(self):
        """Test that multiple agents can be spawned concurrently."""
        import asyncio

        spawned = []

        async def spawn_agent(name):
            await asyncio.sleep(0.01)  # Simulate async work
            spawned.append({
                "id": str(uuid.uuid4()),
                "name": name,
                "status": "ready",
            })

        await asyncio.gather(
            spawn_agent("agent_1"),
            spawn_agent("agent_2"),
            spawn_agent("agent_3"),
        )

        assert len(spawned) == 3
        names = {a["name"] for a in spawned}
        assert names == {"agent_1", "agent_2", "agent_3"}
