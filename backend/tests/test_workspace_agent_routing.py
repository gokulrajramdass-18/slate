"""
Test Workspace Agent Routing Logic

Tests the smart message routing that determines whether to use agents
for chat messages based on message content.
"""

import pytest
from unittest.mock import patch, AsyncMock
from api.services.workspace_agent_selector import WorkspaceAgentSelector


@pytest.mark.asyncio
async def test_simple_greetings_skip_agent():
    """Simple greetings should not trigger agent execution."""
    mock_agents = [
        {"id": "agent-1", "name": "Test Agent", "type": "agent"}
    ]

    selector = WorkspaceAgentSelector()

    # Test various greeting formats
    greetings = ["hi", "hello", "Hey", "HELLO!", "thanks", "okay", "bye"]

    for greeting in greetings:
        with patch.object(selector, 'get_workspace_agents', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_agents

            result = await selector.select_agent_for_message(
                workspace_id="test-workspace",
                message=greeting
            )
            assert result is None, f"Greeting '{greeting}' should skip agent"


@pytest.mark.asyncio
async def test_task_messages_use_agent():
    """Task-oriented messages should trigger agent execution."""
    mock_agents = [
        {"id": "agent-1", "name": "Test Agent", "type": "agent"}
    ]

    selector = WorkspaceAgentSelector()

    # Test various task messages
    tasks = [
        "query the database",
        "show me the orders",
        "analyze the sales data",
        "fetch customer information",
        "what is the total revenue?",
        "Can you search for orders?"
    ]

    for task in tasks:
        with patch.object(selector, 'get_workspace_agents', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_agents

            result = await selector.select_agent_for_message(
                workspace_id="test-workspace",
                message=task
            )
            assert result is not None, f"Task '{task}' should use agent"
            assert result["id"] == "agent-1"


@pytest.mark.asyncio
async def test_short_conversational_messages_skip_agent():
    """Short conversational messages without task keywords should skip agent."""
    mock_agents = [
        {"id": "agent-1", "name": "Test Agent", "type": "agent"}
    ]

    selector = WorkspaceAgentSelector()

    # Short messages without task intent
    messages = ["cool", "nice", "I see", "got it"]

    for msg in messages:
        with patch.object(selector, 'get_workspace_agents', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_agents

            result = await selector.select_agent_for_message(
                workspace_id="test-workspace",
                message=msg
            )
            assert result is None, f"Message '{msg}' should skip agent"


@pytest.mark.asyncio
async def test_short_task_messages_use_agent():
    """Short messages with task keywords should use agent."""
    mock_agents = [
        {"id": "agent-1", "name": "Test Agent", "type": "agent"}
    ]

    selector = WorkspaceAgentSelector()

    # Short but task-oriented messages
    messages = ["find orders", "query db", "get data", "show list"]

    for msg in messages:
        with patch.object(selector, 'get_workspace_agents', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_agents

            result = await selector.select_agent_for_message(
                workspace_id="test-workspace",
                message=msg
            )
            assert result is not None, f"Task '{msg}' should use agent"


@pytest.mark.asyncio
async def test_no_agents_returns_none():
    """When no agents are assigned, always return None."""
    selector = WorkspaceAgentSelector()

    with patch.object(selector, 'get_workspace_agents', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = []

        result = await selector.select_agent_for_message(
            workspace_id="test-workspace",
            message="query the database"
        )
        assert result is None


@pytest.mark.asyncio
async def test_question_marks_prefer_agent():
    """Messages with question marks should use agent (queries)."""
    mock_agents = [
        {"id": "agent-1", "name": "Test Agent", "type": "agent"}
    ]

    selector = WorkspaceAgentSelector()

    with patch.object(selector, 'get_workspace_agents', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_agents

        result = await selector.select_agent_for_message(
            workspace_id="test-workspace",
            message="what time is it?"
        )
        assert result is not None


if __name__ == "__main__":
    import asyncio

    async def run_tests():
        """Run all tests."""
        print("Testing workspace agent routing...")

        await test_simple_greetings_skip_agent()
        print("✓ Simple greetings skip agent")

        await test_task_messages_use_agent()
        print("✓ Task messages use agent")

        await test_short_conversational_messages_skip_agent()
        print("✓ Short conversational messages skip agent")

        await test_short_task_messages_use_agent()
        print("✓ Short task messages use agent")

        await test_no_agents_returns_none()
        print("✓ No agents returns None")

        await test_question_marks_prefer_agent()
        print("✓ Question marks prefer agent")

        print("\n✅ All tests passed!")

    asyncio.run(run_tests())
