"""
Manual Test for Workspace Agent Routing Logic

Tests the smart message routing without pytest dependency.
"""

import asyncio
from unittest.mock import patch, AsyncMock
from api.services.workspace_agent_selector import WorkspaceAgentSelector


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
            assert result is None, f"Greeting '{greeting}' should skip agent but got {result}"


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
            assert result is not None, f"Task '{task}' should use agent but got None"
            assert result["id"] == "agent-1"


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
            assert result is None, f"Message '{msg}' should skip agent but got {result}"


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
            assert result is not None, f"Task '{msg}' should use agent but got None"


async def test_no_agents_returns_none():
    """When no agents are assigned, always return None."""
    selector = WorkspaceAgentSelector()

    with patch.object(selector, 'get_workspace_agents', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = []

        result = await selector.select_agent_for_message(
            workspace_id="test-workspace",
            message="query the database"
        )
        assert result is None, f"No agents should return None but got {result}"


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
        assert result is not None, f"Question should use agent but got None"


async def run_tests():
    """Run all tests."""
    print("Testing workspace agent routing...\n")

    try:
        await test_simple_greetings_skip_agent()
        print("✓ Simple greetings skip agent")
    except AssertionError as e:
        print(f"✗ Simple greetings test failed: {e}")
        return False

    try:
        await test_task_messages_use_agent()
        print("✓ Task messages use agent")
    except AssertionError as e:
        print(f"✗ Task messages test failed: {e}")
        return False

    try:
        await test_short_conversational_messages_skip_agent()
        print("✓ Short conversational messages skip agent")
    except AssertionError as e:
        print(f"✗ Short conversational test failed: {e}")
        return False

    try:
        await test_short_task_messages_use_agent()
        print("✓ Short task messages use agent")
    except AssertionError as e:
        print(f"✗ Short task messages test failed: {e}")
        return False

    try:
        await test_no_agents_returns_none()
        print("✓ No agents returns None")
    except AssertionError as e:
        print(f"✗ No agents test failed: {e}")
        return False

    try:
        await test_question_marks_prefer_agent()
        print("✓ Question marks prefer agent")
    except AssertionError as e:
        print(f"✗ Question marks test failed: {e}")
        return False

    print("\n✅ All tests passed!")
    return True


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    exit(0 if success else 1)
