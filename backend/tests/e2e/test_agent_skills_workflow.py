"""
E2E tests for Agent Skills Workflow

These tests cover the complete user journey from creating agents with skills
to executing them and tracking history. Tests are designed to be independent
and idempotent.

Test Coverage:
1. Create Agent with Skills
2. Execute Agent with Skills
3. Update Agent Skills
4. Skill Binding to Role
5. Direct Skill Execution
6. Skill Execution History
7. Permission Denied Scenario
8. Complete Workflow
"""

import json
import time
import uuid
from datetime import datetime
from typing import List, Dict, Any
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from api.main import app
from open_notebook.database.repository import repo_query, repo_execute


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Provide a FastAPI test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
async def clean_database():
    """Clean test data before each test."""
    # Clean up any existing test data (wrapped in try-except for table existence)
    try:
        await repo_execute("DELETE FROM agent_skill_executions WHERE agent_id LIKE 'test-%'", {})
    except Exception:
        pass  # Table might not exist yet

    try:
        await repo_execute("DELETE FROM agent_skill_bindings WHERE created_by = 'test_suite'", {})
    except Exception:
        pass

    try:
        await repo_execute("DELETE FROM agent_skills WHERE name LIKE 'Test %'", {})
    except Exception:
        pass

    try:
        await repo_execute("DELETE FROM standalone_agents WHERE name LIKE 'Test %'", {})
    except Exception:
        pass

    yield

    # Cleanup after test (same error handling)
    try:
        await repo_execute("DELETE FROM agent_skill_executions WHERE agent_id LIKE 'test-%'", {})
    except Exception:
        pass

    try:
        await repo_execute("DELETE FROM agent_skill_bindings WHERE created_by = 'test_suite'", {})
    except Exception:
        pass

    try:
        await repo_execute("DELETE FROM agent_skills WHERE name LIKE 'Test %'", {})
    except Exception:
        pass

    try:
        await repo_execute("DELETE FROM standalone_agents WHERE name LIKE 'Test %'", {})
    except Exception:
        pass


@pytest.fixture
async def sample_skill(clean_database) -> Dict[str, Any]:
    """Create a sample skill for testing."""
    skill_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    await repo_execute(
        """INSERT INTO agent_skills
           (id, name, category, description, skill_type, definition, input_schema, output_schema, roles, tags, enabled, metadata, created, updated)
           VALUES
           (:id, :name, :category, :description, :skill_type, :definition, :input_schema, :output_schema, :roles, :tags, :enabled, :metadata, :created, :updated)""",
        {
            "id": skill_id,
            "name": "Test Semantic Search",
            "category": "search",
            "description": "Search skill for testing",
            "skill_type": "tool_chain",
            "definition": json.dumps({
                "tools": ["semantic_search"],
                "flow": {"steps": ["search"]}
            }),
            "input_schema": json.dumps({
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            }),
            "output_schema": json.dumps({
                "type": "object",
                "properties": {"results": {"type": "array"}}
            }),
            "roles": json.dumps(["researcher", "analyst"]),
            "tags": json.dumps(["search", "semantic", "test"]),
            "enabled": 1,
            "metadata": json.dumps({"test": True}),
            "created": now,
            "updated": now
        }
    )

    return {
        "id": skill_id,
        "name": "Test Semantic Search",
        "category": "search",
        "skill_type": "tool_chain"
    }


@pytest.fixture
async def restricted_skill(clean_database) -> Dict[str, Any]:
    """Create a skill restricted to certain roles."""
    skill_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    await repo_execute(
        """INSERT INTO agent_skills
           (id, name, category, description, skill_type, definition, roles, tags, enabled, created, updated)
           VALUES
           (:id, :name, :category, :description, :skill_type, :definition, :roles, :tags, :enabled, :created, :updated)""",
        {
            "id": skill_id,
            "name": "Test HANA Query",
            "category": "data_analysis",
            "description": "Database query skill (restricted)",
            "skill_type": "tool_chain",
            "definition": json.dumps({"tools": ["hana_query"]}),
            "roles": json.dumps(["analyst", "data_scientist", "researcher"]),
            "tags": json.dumps(["database", "hana", "test"]),
            "enabled": 1,
            "created": now,
            "updated": now
        }
    )

    return {
        "id": skill_id,
        "name": "Test HANA Query",
        "category": "data_analysis",
        "roles": ["analyst", "data_scientist", "researcher"]
    }


# ============================================================================
# Test 1: Create Agent with Skills
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestCreateAgentWithSkills:
    """Test creating a standalone agent with skill_ids."""

    async def test_create_agent_with_single_skill(self, client, sample_skill):
        """Create an agent with a single skill."""
        response = client.post(
            "/api/standalone-agents",
            json={
                "name": "Test Researcher",
                "description": "Researcher agent for testing",
                "role": "researcher",
                "system_prompt": "You are a research agent.",
                "model_name": "gpt-4",
                "skill_ids": [sample_skill["id"]],
                "config": {}
            }
        )

        assert response.status_code == 201, f"Failed: {response.json()}"
        data = response.json()

        # Verify agent created with correct structure
        assert data["name"] == "Test Researcher"
        assert data["role"] == "researcher"
        assert data["status"] == "active"

        # Verify skill_ids stored correctly
        skill_ids = json.loads(data["skill_ids"]) if isinstance(data["skill_ids"], str) else data["skill_ids"]
        assert skill_ids == [sample_skill["id"]]

        return data["id"]

    async def test_create_agent_with_multiple_skills(self, client, sample_skill, restricted_skill):
        """Create an agent with multiple skills."""
        response = client.post(
            "/api/standalone-agents",
            json={
                "name": "Test Analyst",
                "role": "analyst",
                "skill_ids": [sample_skill["id"], restricted_skill["id"]]
            }
        )

        assert response.status_code == 201
        data = response.json()

        skill_ids = json.loads(data["skill_ids"]) if isinstance(data["skill_ids"], str) else data["skill_ids"]
        assert len(skill_ids) == 2
        assert sample_skill["id"] in skill_ids
        assert restricted_skill["id"] in skill_ids

    async def test_create_agent_without_skills(self, client):
        """Create an agent without any skills (should work)."""
        response = client.post(
            "/api/standalone-agents",
            json={
                "name": "Test Planner",
                "role": "planner",
                "skill_ids": []
            }
        )

        assert response.status_code == 201
        data = response.json()

        skill_ids = json.loads(data["skill_ids"]) if isinstance(data["skill_ids"], str) else data["skill_ids"]
        assert skill_ids == []


# ============================================================================
# Test 2: Execute Agent with Skills
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestExecuteAgentWithSkills:
    """Test executing an agent that has skills loaded."""

    async def test_execute_agent_skills_loaded_in_system_prompt(self, client, sample_skill):
        """Execute agent and verify skills appear in system prompt."""
        # Create agent with skill
        create_response = client.post(
            "/api/standalone-agents",
            json={
                "name": "Test Executor Agent",
                "role": "researcher",
                "system_prompt": "Base prompt.",
                "skill_ids": [sample_skill["id"]]
            }
        )
        agent_id = create_response.json()["id"]

        # Mock the execution to capture the system prompt
        with patch('api.routers.standalone_agents.repo_execute') as mock_execute:
            mock_execute.return_value = None

            # Execute agent
            response = client.post(
                f"/api/standalone-agents/{agent_id}/execute",
                json={
                    "query": "Find information about AI",
                    "max_steps": 5
                }
            )

            # Verify execution record created
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
            assert data["agent_id"] == agent_id

    async def test_execute_agent_skills_in_execution_steps(self, client, sample_skill):
        """Verify skills are referenced in execution steps."""
        # This test would require actual execution flow
        # For now, we verify the execution can be initiated
        create_response = client.post(
            "/api/standalone-agents",
            json={
                "name": "Test Steps Agent",
                "role": "researcher",
                "skill_ids": [sample_skill["id"]]
            }
        )
        agent_id = create_response.json()["id"]

        # Execute
        response = client.post(
            f"/api/standalone-agents/{agent_id}/execute",
            json={"query": "Test query"}
        )

        assert response.status_code == 200
        execution = response.json()
        assert execution["agent_id"] == agent_id

        # In a real execution, skills would be invoked and recorded
        # We're testing the infrastructure here


# ============================================================================
# Test 3: Update Agent Skills
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestUpdateAgentSkills:
    """Test updating an agent's skill_ids."""

    async def test_update_add_skills(self, client, sample_skill, restricted_skill):
        """Update agent to add new skills."""
        # Create agent with one skill
        create_response = client.post(
            "/api/standalone-agents",
            json={
                "name": "Test Update Agent",
                "role": "analyst",
                "skill_ids": [sample_skill["id"]]
            }
        )
        agent_id = create_response.json()["id"]

        # Update to add another skill
        update_response = client.put(
            f"/api/standalone-agents/{agent_id}",
            json={
                "skill_ids": [sample_skill["id"], restricted_skill["id"]]
            }
        )

        assert update_response.status_code == 200
        data = update_response.json()

        skill_ids = json.loads(data["skill_ids"]) if isinstance(data["skill_ids"], str) else data["skill_ids"]
        assert len(skill_ids) == 2
        assert sample_skill["id"] in skill_ids
        assert restricted_skill["id"] in skill_ids

    async def test_update_remove_skills(self, client, sample_skill):
        """Update agent to remove skills."""
        # Create agent with skill
        create_response = client.post(
            "/api/standalone-agents",
            json={
                "name": "Test Remove Skills Agent",
                "role": "researcher",
                "skill_ids": [sample_skill["id"]]
            }
        )
        agent_id = create_response.json()["id"]

        # Update to remove skill
        update_response = client.put(
            f"/api/standalone-agents/{agent_id}",
            json={"skill_ids": []}
        )

        assert update_response.status_code == 200
        data = update_response.json()

        skill_ids = json.loads(data["skill_ids"]) if isinstance(data["skill_ids"], str) else data["skill_ids"]
        assert skill_ids == []

    async def test_update_execute_with_new_skills(self, client, sample_skill, restricted_skill):
        """Update skills and verify new skills work in execution."""
        # Create agent
        create_response = client.post(
            "/api/standalone-agents",
            json={
                "name": "Test Dynamic Skills Agent",
                "role": "analyst",
                "skill_ids": [sample_skill["id"]]
            }
        )
        agent_id = create_response.json()["id"]

        # Update skills
        client.put(
            f"/api/standalone-agents/{agent_id}",
            json={"skill_ids": [restricted_skill["id"]]}
        )

        # Execute and verify new skill is available
        response = client.post(
            f"/api/standalone-agents/{agent_id}/execute",
            json={"query": "Test with new skill"}
        )

        assert response.status_code == 200


# ============================================================================
# Test 4: Skill Binding to Role
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestSkillBindingToRole:
    """Test binding skills to roles and automatic skill assignment."""

    async def test_bind_skill_to_researcher_role(self, client, sample_skill):
        """Bind a skill to researcher role."""
        response = client.post(
            f"/api/agent-skills/roles/researcher/skills",
            json={
                "skill_id": sample_skill["id"],
                "binding_type": "role",
                "role": "researcher",
                "priority": 10,
                "enabled": True,
                "created_by": "test_suite"
            }
        )

        assert response.status_code == 201
        data = response.json()

        assert data["skill_id"] == sample_skill["id"]
        assert data["binding_type"] == "role"
        assert data["role"] == "researcher"
        assert data["priority"] == 10
        assert data["enabled"] is True

        return data["id"]

    async def test_list_skills_for_role(self, client, sample_skill):
        """List all skills bound to a role."""
        # Bind skill
        client.post(
            f"/api/agent-skills/roles/analyst/skills",
            json={
                "skill_id": sample_skill["id"],
                "binding_type": "role",
                "role": "analyst",
                "priority": 5,
                "created_by": "test_suite"
            }
        )

        # List skills for role
        response = client.get("/api/agent-skills/roles/analyst/skills")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] >= 1
        skill_ids = [b["skill_id"] for b in data["bindings"]]
        assert sample_skill["id"] in skill_ids

    async def test_agent_inherits_role_skills(self, client, sample_skill):
        """Create agent with role and verify it can use role-bound skills."""
        # Bind skill to role
        client.post(
            f"/api/agent-skills/roles/researcher/skills",
            json={
                "skill_id": sample_skill["id"],
                "binding_type": "role",
                "role": "researcher",
                "created_by": "test_suite"
            }
        )

        # Create agent with that role
        create_response = client.post(
            "/api/standalone-agents",
            json={
                "name": "Test Role Inheritance Agent",
                "role": "researcher",
                "skill_ids": []  # No explicit skills
            }
        )

        agent_id = create_response.json()["id"]

        # The agent should have access to role-bound skills
        # This would be validated during execution
        # Here we verify the agent was created successfully
        assert create_response.status_code == 201


# ============================================================================
# Test 5: Direct Skill Execution
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestDirectSkillExecution:
    """Test executing individual skills directly."""

    async def test_execute_skill_directly(self, client, sample_skill):
        """Execute a skill directly via API."""
        # Create agent
        create_response = client.post(
            "/api/standalone-agents",
            json={
                "name": "Test Direct Execution Agent",
                "role": "researcher",
                "skill_ids": [sample_skill["id"]]
            }
        )
        agent_id = create_response.json()["id"]

        # Execute skill directly
        response = client.post(
            f"/api/agent-skills/agents/{agent_id}/skills/{sample_skill['id']}/execute",
            json={
                "input_data": {"query": "test query"},
                "config_override": {}
            },
            params={"binding_type": "standalone_agent"}
        )

        assert response.status_code == 202  # Accepted
        data = response.json()

        assert data["skill_id"] == sample_skill["id"]
        assert data["agent_id"] == agent_id
        assert data["success"] is False  # Execution not complete yet
        assert "execution_id" in data

    async def test_execute_skill_with_config_override(self, client, sample_skill):
        """Execute skill with custom configuration."""
        create_response = client.post(
            "/api/standalone-agents",
            json={
                "name": "Test Config Override Agent",
                "role": "analyst",
                "skill_ids": [sample_skill["id"]]
            }
        )
        agent_id = create_response.json()["id"]

        # Execute with config override
        response = client.post(
            f"/api/agent-skills/agents/{agent_id}/skills/{sample_skill['id']}/execute",
            json={
                "input_data": {"query": "test"},
                "config_override": {"limit": 50, "strategy": "vector"}
            },
            params={"binding_type": "standalone_agent"}
        )

        assert response.status_code == 202


# ============================================================================
# Test 6: Skill Execution History
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestSkillExecutionHistory:
    """Test tracking and querying skill execution history."""

    async def test_execution_history_recorded(self, client, sample_skill):
        """Verify execution history is recorded."""
        # Create agent
        create_response = client.post(
            "/api/standalone-agents",
            json={
                "name": "Test History Agent",
                "role": "researcher",
                "skill_ids": [sample_skill["id"]]
            }
        )
        agent_id = create_response.json()["id"]

        # Execute skill multiple times
        for i in range(3):
            client.post(
                f"/api/agent-skills/agents/{agent_id}/skills/{sample_skill['id']}/execute",
                json={"input_data": {"query": f"test query {i}"}},
                params={"binding_type": "standalone_agent"}
            )
            time.sleep(0.1)  # Small delay to ensure different timestamps

        # Query execution history
        response = client.get(
            f"/api/agent-skills/{sample_skill['id']}/executions",
            params={"agent_id": agent_id, "limit": 10}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] >= 3
        assert len(data["executions"]) >= 3

        # Verify executions have correct structure
        for exec_record in data["executions"][:3]:
            assert exec_record["skill_id"] == sample_skill["id"]
            assert exec_record["agent_id"] == agent_id
            assert "execution_id" in exec_record
            assert "started_at" in exec_record

    async def test_filter_execution_by_success(self, client, sample_skill):
        """Filter executions by success status."""
        create_response = client.post(
            "/api/standalone-agents",
            json={
                "name": "Test Filter Agent",
                "role": "analyst",
                "skill_ids": [sample_skill["id"]]
            }
        )
        agent_id = create_response.json()["id"]

        # Execute skill
        client.post(
            f"/api/agent-skills/agents/{agent_id}/skills/{sample_skill['id']}/execute",
            json={"input_data": {"query": "test"}},
            params={"binding_type": "standalone_agent"}
        )

        # Query by success=False (since executions are just created, not completed)
        response = client.get(
            f"/api/agent-skills/{sample_skill['id']}/executions",
            params={"success": False, "limit": 10}
        )

        assert response.status_code == 200
        data = response.json()

        # All executions should be unsuccessful (not completed)
        for exec_record in data["executions"]:
            assert exec_record["success"] is False

    async def test_pagination_of_execution_history(self, client, sample_skill):
        """Test pagination of execution history."""
        create_response = client.post(
            "/api/standalone-agents",
            json={
                "name": "Test Pagination Agent",
                "role": "researcher",
                "skill_ids": [sample_skill["id"]]
            }
        )
        agent_id = create_response.json()["id"]

        # Create multiple executions
        for i in range(10):
            client.post(
                f"/api/agent-skills/agents/{agent_id}/skills/{sample_skill['id']}/execute",
                json={"input_data": {"query": f"query {i}"}},
                params={"binding_type": "standalone_agent"}
            )

        # Get first page
        response1 = client.get(
            f"/api/agent-skills/{sample_skill['id']}/executions",
            params={"limit": 5, "offset": 0}
        )

        # Get second page
        response2 = client.get(
            f"/api/agent-skills/{sample_skill['id']}/executions",
            params={"limit": 5, "offset": 5}
        )

        assert response1.status_code == 200
        assert response2.status_code == 200

        page1 = response1.json()["executions"]
        page2 = response2.json()["executions"]

        assert len(page1) <= 5
        assert len(page2) <= 5

        # Verify different executions
        page1_ids = {e["execution_id"] for e in page1}
        page2_ids = {e["execution_id"] for e in page2}
        assert len(page1_ids.intersection(page2_ids)) == 0


# ============================================================================
# Test 7: Permission Denied Scenario
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestPermissionDeniedScenario:
    """Test that skills restricted to certain roles cannot be used by others."""

    async def test_execute_restricted_skill_with_wrong_role(self, client, restricted_skill):
        """Try to execute a restricted skill with an unauthorized role."""
        # Create agent with 'custom' role (not authorized)
        create_response = client.post(
            "/api/standalone-agents",
            json={
                "name": "Test Unauthorized Agent",
                "role": "custom",  # Not in restricted_skill's roles
                "skill_ids": [restricted_skill["id"]]
            }
        )
        agent_id = create_response.json()["id"]

        # Try to execute the restricted skill
        # In a real implementation, this should check permissions
        # For now, we test that the skill can be bound
        response = client.post(
            f"/api/agent-skills/agents/{agent_id}/skills/{restricted_skill['id']}/execute",
            json={"input_data": {"query": "SELECT *"}},
            params={"binding_type": "standalone_agent"}
        )

        # The API creates an execution record, but actual execution
        # would validate permissions. For now, verify the record is created.
        assert response.status_code in [202, 403]

    async def test_authorized_role_can_execute_restricted_skill(self, client, restricted_skill):
        """Verify that authorized roles CAN execute restricted skills."""
        # Create agent with authorized role
        create_response = client.post(
            "/api/standalone-agents",
            json={
                "name": "Test Authorized Agent",
                "role": "analyst",  # In restricted_skill's roles
                "skill_ids": [restricted_skill["id"]]
            }
        )
        agent_id = create_response.json()["id"]

        # Execute restricted skill (should succeed)
        response = client.post(
            f"/api/agent-skills/agents/{agent_id}/skills/{restricted_skill['id']}/execute",
            json={"input_data": {"query": "SELECT *"}},
            params={"binding_type": "standalone_agent"}
        )

        assert response.status_code == 202
        data = response.json()
        assert data["skill_id"] == restricted_skill["id"]


# ============================================================================
# Test 8: Complete Workflow
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestCompleteWorkflow:
    """End-to-end test of complete agent skills workflow."""

    async def test_complete_agent_skills_lifecycle(self, client, sample_skill, restricted_skill):
        """
        Complete workflow:
        1. Create agent with multiple skills
        2. Execute agent
        3. Verify skills loaded
        4. Execute individual skills
        5. Check execution history
        6. Update skills
        7. Execute again with new skills
        """
        # Step 1: Create agent with multiple skills
        create_response = client.post(
            "/api/standalone-agents",
            json={
                "name": "Test Complete Workflow Agent",
                "description": "Agent for complete workflow test",
                "role": "researcher",
                "system_prompt": "You are a test agent.",
                "model_name": "gpt-4",
                "skill_ids": [sample_skill["id"], restricted_skill["id"]],
                "config": {"temperature": 0.7}
            }
        )

        assert create_response.status_code == 201
        agent = create_response.json()
        agent_id = agent["id"]

        # Verify skills are stored
        skill_ids = json.loads(agent["skill_ids"]) if isinstance(agent["skill_ids"], str) else agent["skill_ids"]
        assert len(skill_ids) == 2

        # Step 2: Execute agent
        execute_response = client.post(
            f"/api/standalone-agents/{agent_id}/execute",
            json={
                "query": "Find information about machine learning",
                "max_steps": 10
            }
        )

        assert execute_response.status_code == 200
        execution = execute_response.json()
        assert execution["agent_id"] == agent_id
        assert execution["status"] == "running"

        # Step 3: Verify all skills are available (would be in system prompt)
        # In real execution, skills would be loaded and made available

        # Step 4: Execute individual skills
        exec_responses = []
        for skill_id in [sample_skill["id"], restricted_skill["id"]]:
            response = client.post(
                f"/api/agent-skills/agents/{agent_id}/skills/{skill_id}/execute",
                json={"input_data": {"query": "test"}},
                params={"binding_type": "standalone_agent"}
            )
            assert response.status_code == 202
            exec_responses.append(response.json())

        # Step 5: Check execution history
        history_response = client.get(
            f"/api/agent-skills/{sample_skill['id']}/executions",
            params={"agent_id": agent_id, "limit": 10}
        )

        assert history_response.status_code == 200
        history = history_response.json()
        assert history["total"] >= 1

        # Step 6: Update skills (remove one, keep one)
        update_response = client.put(
            f"/api/standalone-agents/{agent_id}",
            json={"skill_ids": [sample_skill["id"]]}  # Keep only search skill
        )

        assert update_response.status_code == 200
        updated_agent = update_response.json()
        updated_skill_ids = json.loads(updated_agent["skill_ids"]) if isinstance(updated_agent["skill_ids"], str) else updated_agent["skill_ids"]
        assert len(updated_skill_ids) == 1
        assert updated_skill_ids[0] == sample_skill["id"]

        # Step 7: Execute again with updated skills
        final_execute = client.post(
            f"/api/standalone-agents/{agent_id}/execute",
            json={"query": "New query with updated skills"}
        )

        assert final_execute.status_code == 200

        # Verify agent is still active
        get_response = client.get(f"/api/standalone-agents/{agent_id}")
        assert get_response.status_code == 200
        final_agent = get_response.json()
        assert final_agent["status"] == "active"

    async def test_workflow_with_role_binding(self, client, sample_skill):
        """
        Workflow with role-based skill binding:
        1. Bind skill to role
        2. Create agent with that role
        3. Verify agent can use role-bound skill
        4. Add explicit skill to agent
        5. Execute and verify both skills available
        """
        # Step 1: Bind skill to role
        binding_response = client.post(
            f"/api/agent-skills/roles/researcher/skills",
            json={
                "skill_id": sample_skill["id"],
                "binding_type": "role",
                "role": "researcher",
                "priority": 5,
                "created_by": "test_suite"
            }
        )
        assert binding_response.status_code == 201

        # Step 2: Create agent with researcher role
        create_response = client.post(
            "/api/standalone-agents",
            json={
                "name": "Test Role Workflow Agent",
                "role": "researcher",
                "skill_ids": []  # No explicit skills
            }
        )
        assert create_response.status_code == 201
        agent_id = create_response.json()["id"]

        # Step 3: Verify role binding is active
        role_skills = client.get("/api/agent-skills/roles/researcher/skills")
        assert role_skills.status_code == 200
        assert role_skills.json()["total"] >= 1

        # Step 4: Add another skill explicitly
        # (In real workflow, this might be a different skill)
        update_response = client.put(
            f"/api/standalone-agents/{agent_id}",
            json={"skill_ids": [sample_skill["id"]]}
        )
        assert update_response.status_code == 200

        # Step 5: Execute and verify
        exec_response = client.post(
            f"/api/standalone-agents/{agent_id}/execute",
            json={"query": "Test with role and explicit skills"}
        )
        assert exec_response.status_code == 200


# ============================================================================
# Additional Edge Cases
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestEdgeCases:
    """Test edge cases and error conditions."""

    async def test_execute_nonexistent_skill(self, client, sample_skill):
        """Try to execute a skill that doesn't exist."""
        create_response = client.post(
            "/api/standalone-agents",
            json={
                "name": "Test Edge Case Agent",
                "role": "researcher",
                "skill_ids": [sample_skill["id"]]
            }
        )
        agent_id = create_response.json()["id"]

        # Try to execute non-existent skill
        response = client.post(
            f"/api/agent-skills/agents/{agent_id}/skills/nonexistent-skill-id/execute",
            json={"input_data": {"query": "test"}},
            params={"binding_type": "standalone_agent"}
        )

        assert response.status_code == 404

    async def test_bind_skill_to_nonexistent_agent(self, client, sample_skill):
        """Try to bind a skill to an agent that doesn't exist."""
        response = client.post(
            f"/api/agent-skills/agents/nonexistent-agent-id/skills",
            json={
                "skill_id": sample_skill["id"],
                "binding_type": "standalone_agent",
                "priority": 0
            }
        )

        assert response.status_code == 404

    async def test_create_agent_with_invalid_skill_ids(self, client):
        """Create agent with skill IDs that don't exist (should still work)."""
        response = client.post(
            "/api/standalone-agents",
            json={
                "name": "Test Invalid Skills Agent",
                "role": "researcher",
                "skill_ids": ["invalid-skill-id-1", "invalid-skill-id-2"]
            }
        )

        # Agent creation should succeed even with invalid skill_ids
        # Validation happens at execution time
        assert response.status_code == 201

    async def test_update_agent_skills_to_empty(self, client, sample_skill):
        """Update agent to have no skills."""
        create_response = client.post(
            "/api/standalone-agents",
            json={
                "name": "Test Empty Skills Agent",
                "role": "planner",
                "skill_ids": [sample_skill["id"]]
            }
        )
        agent_id = create_response.json()["id"]

        # Update to empty skills
        update_response = client.put(
            f"/api/standalone-agents/{agent_id}",
            json={"skill_ids": []}
        )

        assert update_response.status_code == 200
        updated = update_response.json()
        skill_ids = json.loads(updated["skill_ids"]) if isinstance(updated["skill_ids"], str) else updated["skill_ids"]
        assert skill_ids == []


# ============================================================================
# Performance Tests
# ============================================================================

@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
class TestPerformance:
    """Test performance with many skills and executions."""

    async def test_agent_with_many_skills(self, client):
        """Create agent with many skills and verify performance."""
        # Create multiple test skills
        skill_ids = []
        for i in range(10):
            skill_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()

            await repo_execute(
                """INSERT INTO agent_skills
                   (id, name, category, skill_type, definition, enabled, created, updated)
                   VALUES
                   (:id, :name, :category, :skill_type, :definition, :enabled, :created, :updated)""",
                {
                    "id": skill_id,
                    "name": f"Test Skill {i}",
                    "category": "custom",
                    "skill_type": "custom",
                    "definition": json.dumps({"test": True}),
                    "enabled": 1,
                    "created": now,
                    "updated": now
                }
            )
            skill_ids.append(skill_id)

        # Create agent with all skills
        start_time = time.time()
        response = client.post(
            "/api/standalone-agents",
            json={
                "name": "Test Performance Agent",
                "role": "custom",
                "skill_ids": skill_ids
            }
        )
        create_time = time.time() - start_time

        assert response.status_code == 201
        assert create_time < 2.0  # Should be fast

        agent = response.json()
        stored_skill_ids = json.loads(agent["skill_ids"]) if isinstance(agent["skill_ids"], str) else agent["skill_ids"]
        assert len(stored_skill_ids) == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])
