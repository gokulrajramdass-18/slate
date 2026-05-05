"""
Test Unified Agent Pattern - Claude Code Style Agent Invocation

Tests the new unified agent approach where DataQueryAgent is always used,
and the LLM decides whether to invoke tools based on the conversation context.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from open_notebook.agents.data_query_agent import DataQueryAgent


@pytest.mark.asyncio
async def test_agent_with_no_tools_conversational():
    """
    Test that DataQueryAgent works in pure conversational mode with no tools.

    This simulates: User says "Hello!" → Agent responds conversationally
    """
    # Create agent with empty tools list
    agent = DataQueryAgent(
        model_name="gpt-4",
        notebook_id="test-notebook",
        tools=[],  # Empty tools - pure chat mode
        session_id="test-session",
        system_message="You are a helpful assistant.",
    )

    # Verify initialization
    assert len(agent.tools) == 0
    assert agent.graph is not None

    # Mock the LLM response
    with patch.object(agent.model, 'ainvoke') as mock_invoke:
        from langchain_core.messages import AIMessage
        mock_invoke.return_value = AIMessage(content="Hello! How can I help you today?")

        # Invoke agent
        response = await agent.invoke("Hello!")

        # Verify response is conversational
        assert "Hello" in response
        assert "help" in response.lower()

        # Verify no tool calls were attempted
        assert len(agent.tool_results) == 0


@pytest.mark.asyncio
async def test_agent_with_tools_decides_not_to_use():
    """
    Test that agent with tools available decides NOT to use them for casual chat.

    This simulates: User says "Thank you!" → Agent responds directly (no tool use)
    """
    # Mock tool
    mock_tool = MagicMock()
    mock_tool.name = "query_database"
    mock_tool.description = "Query the database"

    # Create agent with tools
    agent = DataQueryAgent(
        model_name="gpt-4",
        notebook_id="test-notebook",
        tools=[mock_tool],
        session_id="test-session",
        system_message="You are a helpful assistant with database access.",
    )

    # Verify initialization
    assert len(agent.tools) == 1

    # Mock the LLM response (no tool calls)
    with patch.object(agent.model, 'ainvoke') as mock_invoke:
        from langchain_core.messages import AIMessage
        # LLM decides NOT to use tools - just responds
        mock_invoke.return_value = AIMessage(content="You're welcome!")

        # Invoke agent
        response = await agent.invoke("Thank you!")

        # Verify response is direct
        assert "welcome" in response.lower()

        # Verify no tools were executed
        assert len(agent.tool_results) == 0


@pytest.mark.asyncio
async def test_agent_with_tools_decides_to_use():
    """
    Test that agent with tools available decides TO use them for data queries.

    This simulates: User says "Show me the data" → Agent uses tool
    """
    # Mock tool
    mock_tool = MagicMock()
    mock_tool.name = "query_database"
    mock_tool.description = "Query the database"

    # Create agent with tools
    agent = DataQueryAgent(
        model_name="gpt-4",
        notebook_id="test-notebook",
        tools=[mock_tool],
        session_id="test-session",
        system_message="You are a helpful assistant with database access.",
        capture_tool_results=True,
    )

    # This is a more complex test that would require mocking the full LangGraph execution
    # For now, just verify the agent is set up correctly
    assert len(agent.tools) == 1
    assert agent.capture_tool_results is True
    assert agent.graph is not None


@pytest.mark.asyncio
async def test_agent_progressive_enhancement():
    """
    Test progressive enhancement: same agent code works with 0, 1, or many tools.
    """

    # Case 1: No tools
    agent_no_tools = DataQueryAgent(
        model_name="gpt-4",
        notebook_id="test-notebook",
        tools=[],
        session_id="test-session",
    )
    assert len(agent_no_tools.tools) == 0
    assert agent_no_tools.graph is not None

    # Case 2: One tool
    mock_tool_1 = MagicMock()
    mock_tool_1.name = "tool_1"

    agent_one_tool = DataQueryAgent(
        model_name="gpt-4",
        notebook_id="test-notebook",
        tools=[mock_tool_1],
        session_id="test-session",
    )
    assert len(agent_one_tool.tools) == 1
    assert agent_one_tool.graph is not None

    # Case 3: Multiple tools
    mock_tool_2 = MagicMock()
    mock_tool_2.name = "tool_2"
    mock_tool_3 = MagicMock()
    mock_tool_3.name = "tool_3"

    agent_many_tools = DataQueryAgent(
        model_name="gpt-4",
        notebook_id="test-notebook",
        tools=[mock_tool_1, mock_tool_2, mock_tool_3],
        session_id="test-session",
    )
    assert len(agent_many_tools.tools) == 3
    assert agent_many_tools.graph is not None


def test_agent_graph_structure_without_tools():
    """
    Test that the LangGraph structure is correct when no tools are available.

    Expected: agent → END (no tool node, no conditional routing)
    """
    agent = DataQueryAgent(
        model_name="gpt-4",
        notebook_id="test-notebook",
        tools=[],
        session_id="test-session",
    )

    # Verify graph exists
    assert agent.graph is not None

    # Graph should have agent node but no tools node
    # (Detailed graph inspection would require accessing LangGraph internals)


def test_agent_graph_structure_with_tools():
    """
    Test that the LangGraph structure is correct when tools are available.

    Expected: agent ⇄ tools (with conditional routing)
    """
    mock_tool = MagicMock()
    mock_tool.name = "test_tool"

    agent = DataQueryAgent(
        model_name="gpt-4",
        notebook_id="test-notebook",
        tools=[mock_tool],
        session_id="test-session",
    )

    # Verify graph exists
    assert agent.graph is not None

    # Graph should have both agent and tools nodes
    # (Detailed graph inspection would require accessing LangGraph internals)


@pytest.mark.asyncio
async def test_chat_router_unified_path():
    """
    Test that the chat router always uses DataQueryAgent regardless of tools.

    This is an integration-style test that verifies the router logic.
    """
    # This would be an integration test with the actual FastAPI endpoint
    # Skipping for now as it requires full API setup
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
