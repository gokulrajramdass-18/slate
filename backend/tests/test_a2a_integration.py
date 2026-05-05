"""
A2A Integration Tests

Tests for A2A protocol integration with agent skills system.
"""

import pytest
import uuid
import json
from unittest.mock import AsyncMock, MagicMock, patch

from open_notebook.agents.a2a.agent_card import AgentCardGenerator
from open_notebook.agents.a2a.discovery import A2ADiscoveryClient
from open_notebook.agents.a2a.skill_adapter import RemoteSkillAdapter, RemoteSkillRegistry
from open_notebook.agents.a2a.task_manager import A2ATaskManager
from open_notebook.agents.skills.base import Skill, SkillCategory, SkillContext
from open_notebook.agents.skills.registry import get_skill_registry
from open_notebook.domain.a2a import A2ARemoteAgent, A2ATask


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_agent_card():
    """Mock AgentCard from remote agent."""
    return {
        "url": "https://example.com/a2a/message/send",
        "name": "Test Remote Agent",
        "description": "A test remote agent",
        "version": "1.0.0",
        "preferred_transport": "JSONRPC",  # snake_case for Pydantic
        "capabilities": {
            "streaming": True,
        },
        "default_input_modes": ["text/plain", "application/json"],
        "default_output_modes": ["text/plain", "application/json"],
        "skills": [
            {
                "id": "test-skill-1",
                "name": "Test Skill 1",
                "description": "A test skill",
                "tags": ["test", "data"],
            },
            {
                "id": "test-skill-2",
                "name": "Test Skill 2",
                "description": "Another test skill",
                "tags": ["test", "analysis"],
            },
        ],
    }


@pytest.fixture
def test_skill():
    """Create a test skill."""
    async def test_handler(context: SkillContext):
        return {"result": "test success", "input": context.input_data}

    return Skill(
        id="test-local-skill",
        name="Test Local Skill",
        description="A local skill for testing",
        category=SkillCategory.TOOLS,
        handler=test_handler,
        tags=["test", "local"],
    )


# ============================================================================
# AgentCard Generation Tests
# ============================================================================

@pytest.mark.asyncio
async def test_agent_card_generation(test_skill):
    """Test AgentCard generation from local skills."""
    # Register skill
    registry = get_skill_registry()
    registry.register_skill(test_skill)

    try:
        # Generate AgentCard
        generator = AgentCardGenerator(
            base_url="http://localhost:5055",
            agent_name="Test Agent",
        )
        card = generator.generate_card()

        # Verify card structure
        assert card.name == "Test Agent"
        assert card.url == "http://localhost:5055/api/a2a/message/send"
        assert card.preferred_transport == "JSONRPC"

        # Verify skills included
        skills = card.skills or []
        skill_ids = [s.id for s in skills]
        assert "test-local-skill" in skill_ids

        # Verify skill details
        test_skill_card = next(s for s in skills if s.id == "test-local-skill")
        assert test_skill_card.name == "Test Local Skill"
        assert "test" in test_skill_card.tags

    finally:
        # Cleanup
        registry.unregister_skill(test_skill.id)


# ============================================================================
# A2A Task Manager Tests
# ============================================================================

@pytest.mark.asyncio
async def test_task_creation():
    """Test A2A task creation and persistence."""
    task_mgr = A2ATaskManager()

    # Create task
    task = await task_mgr.create_task(
        context_id="test-context",
        direction="outgoing",
        agent_id="test-agent",
        skill_id="test-skill",
    )

    assert task is not None
    assert task.context_id == "test-context"
    assert task.direction == "outgoing"
    assert task.state == "queued"
    assert task.progress == 0.0

    # Cleanup
    await task.delete()


@pytest.mark.asyncio
async def test_task_lifecycle():
    """Test complete task lifecycle."""
    task_mgr = A2ATaskManager()

    # Create task
    task = await task_mgr.create_task(
        context_id="test-context",
        direction="incoming",
    )

    # Mark running
    await task_mgr.mark_task_running(task.id)
    updated = await task_mgr.get_task(task.id)
    assert updated.state == "running"

    # Update progress
    await task_mgr.update_task_status(
        task.id,
        "running",
        progress=0.5,
        message="Processing",
    )
    updated = await task_mgr.get_task(task.id)
    assert updated.progress == 0.5
    assert updated.message == "Processing"

    # Mark completed
    await task_mgr.mark_task_completed(task.id)
    updated = await task_mgr.get_task(task.id)
    assert updated.state == "completed"
    assert updated.progress == 1.0
    assert updated.is_terminal()
    assert updated.is_success()

    # Cleanup
    await task.delete()


@pytest.mark.asyncio
async def test_task_cancellation():
    """Test task cancellation."""
    task_mgr = A2ATaskManager()

    task = await task_mgr.create_task(
        context_id="test-context",
        direction="outgoing",
    )

    await task_mgr.mark_task_running(task.id)

    # Cancel task
    success = await task_mgr.cancel_task(task.id)
    assert success

    updated = await task_mgr.get_task(task.id)
    assert updated.state == "canceled"
    assert updated.is_terminal()

    # Cannot cancel again
    success = await task_mgr.cancel_task(task.id)
    assert not success

    # Cleanup
    await task.delete()


# ============================================================================
# A2A Discovery Tests
# ============================================================================

@pytest.mark.asyncio
async def test_agent_discovery(mock_agent_card):
    """Test remote agent discovery."""
    with patch("httpx.AsyncClient.get") as mock_get:
        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.json = MagicMock(return_value=mock_agent_card)  # json() is NOT async in httpx
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        client = A2ADiscoveryClient()
        card = await client.discover_agent("https://example.com")

        # Verify AgentCard parsed
        assert card.name == "Test Remote Agent"
        assert len(card.skills or []) == 2


@pytest.mark.asyncio
async def test_agent_import(mock_agent_card):
    """Test importing remote agent and skills."""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.json = MagicMock(return_value=mock_agent_card)  # json() is NOT async in httpx
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        client = A2ADiscoveryClient()
        agent = await client.import_agent("https://example.com")

        try:
            # Verify agent created
            assert agent.name == "Test Remote Agent"
            assert agent.endpoint_url == "https://example.com/a2a/message/send"

            # Verify skills imported
            skills = agent.get_available_skills()
            assert len(skills) == 2
            assert "test-skill-1" in skills
            assert "test-skill-2" in skills

            # Verify skills registered locally
            registry = get_skill_registry()
            local_skill_1 = registry.get_skill(f"a2a:{agent.id}:test-skill-1")
            assert local_skill_1 is not None
            assert "remote" in local_skill_1.tags

        finally:
            # Cleanup
            await client.remove_agent(agent.id)


# ============================================================================
# Remote Skill Adapter Tests
# ============================================================================

@pytest.mark.asyncio
async def test_remote_skill_handler():
    """Test remote skill handler execution."""
    # Create mock remote agent with minimal valid AgentCard
    minimal_card = {
        "url": "https://example.com/a2a",
        "name": "Test Agent",
        "description": "Test",
        "version": "1.0.0",
        "capabilities": {"streaming": False},
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
        "skills": []
    }
    agent = A2ARemoteAgent(
        name="Test Agent",
        card_url="https://example.com",
        agent_card=json.dumps(minimal_card),
        transport="JSONRPC",
        endpoint_url="https://example.com/a2a",
        enabled=True,
    )
    await agent.save()
    agent_id = agent.id

    try:
        # Create handler
        handler = RemoteSkillAdapter.create_handler(agent_id, "test-skill")

        # Mock the A2A client
        with patch("open_notebook.agents.a2a.client.OpenNotebookA2AClient.send_message") as mock_send:
            mock_send.return_value = {"result": "remote success"}

            # Create context
            context = SkillContext(
                agent_id="test-agent",
                agent_role="test",
                skill_id=f"a2a:{agent_id}:test-skill",
                input_data={"query": "test"},
            )

            # Execute handler
            result = await handler(context)

            # Verify result
            assert result["result"] == "remote success"

            # Verify steps recorded
            assert len(context.steps) > 0
            assert any("remote" in s["step_type"] for s in context.steps)

    finally:
        # Cleanup
        await agent.delete()


def test_remote_skill_id_parsing():
    """Test remote skill ID parsing."""
    skill_id = "a2a:agent-123:skill-456"

    # Check if remote
    assert RemoteSkillRegistry.is_remote_skill(skill_id)

    # Parse ID
    agent_id, remote_skill_id = RemoteSkillRegistry.parse_remote_skill_id(skill_id)
    assert agent_id == "agent-123"
    assert remote_skill_id == "skill-456"

    # Test invalid ID
    with pytest.raises(ValueError):
        RemoteSkillRegistry.parse_remote_skill_id("not-a-remote-skill")


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_full_import_and_execution_flow(mock_agent_card):
    """Test complete flow: discover → import → execute remote skill."""
    with patch("httpx.AsyncClient.get") as mock_get, \
         patch("httpx.AsyncClient.post") as mock_post:

        # Mock discovery
        mock_get_response = AsyncMock()
        mock_get_response.json = MagicMock(return_value=mock_agent_card)  # json() is NOT async in httpx
        mock_get_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_get_response

        # Mock execution
        mock_post_response = AsyncMock()
        mock_post_response.json = MagicMock(return_value={
            "jsonrpc": "2.0",
            "id": "test-id",
            "result": {
                "id": "task-123",
                "contextId": "test-context",
                "status": {"state": "completed"},
                "artifacts": [
                    {
                        "artifactId": "artifact-1",
                        "mimeType": "application/json",
                        "parts": [{"type": "text", "text": '{"result": "success"}'}]
                    }
                ],
            },
        })
        mock_post_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_post_response

        client = A2ADiscoveryClient()

        # Import agent
        agent = await client.import_agent("https://example.com")

        try:
            # Get local skill
            registry = get_skill_registry()
            skill = registry.get_skill(f"a2a:{agent.id}:test-skill-1")
            assert skill is not None

            # Execute skill
            context = SkillContext(
                agent_id="test-agent",
                agent_role="test",
                skill_id=skill.id,
                input_data={"query": "test"},
            )

            result = await skill.handler(context)

            # Verify result
            assert result is not None
            # Note: Result structure depends on client implementation

        finally:
            # Cleanup
            await client.remove_agent(agent.id)


# ============================================================================
# API Tests
# ============================================================================

@pytest.mark.asyncio
async def test_agent_card_endpoint():
    """Test AgentCard endpoint returns valid card."""
    from api.routers.a2a import get_agent_card

    response = await get_agent_card()

    # Verify response
    assert response.status_code == 200
    card_data = response.body

    # Parse as JSON
    import json
    card = json.loads(card_data)

    assert "name" in card
    assert "url" in card
    assert "preferredTransport" in card


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
