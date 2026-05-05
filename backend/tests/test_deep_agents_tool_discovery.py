"""
Tests for Deep Agents Tool Discovery Pipeline

Tests dynamic tool discovery from multiple sources with fallback behavior.
"""

import pytest
from deep_agents_integration.tool_discovery import get_tool_discovery_pipeline


@pytest.mark.asyncio
async def test_tool_discovery_basic():
    """Test basic tool discovery without notebook"""
    pipeline = get_tool_discovery_pipeline()

    tools = await pipeline.discover_tools()

    # Should discover at least registry tools
    assert isinstance(tools, list)
    # May be empty if registry not seeded, but should not error


@pytest.mark.asyncio
async def test_tool_discovery_with_notebook(test_notebook):
    """Test tool discovery with notebook context"""
    pipeline = get_tool_discovery_pipeline()

    tools = await pipeline.discover_tools(
        notebook_id=test_notebook.id
    )

    # Should include search tool
    tool_names = [t.name for t in tools]
    assert "search_notebook" in tool_names


@pytest.mark.asyncio
async def test_tool_discovery_whitelist():
    """Test tool whitelisting"""
    pipeline = get_tool_discovery_pipeline()

    # Enable only specific tools
    tools = await pipeline.discover_tools(
        enabled_tool_ids=["search_notebook", "calculator"]
    )

    tool_names = [t.name for t in tools]

    # Should only have whitelisted tools (if they exist)
    for name in tool_names:
        assert name in ["search_notebook", "calculator"] or name.startswith("query_")


@pytest.mark.asyncio
async def test_tool_discovery_blacklist():
    """Test tool blacklisting"""
    pipeline = get_tool_discovery_pipeline()

    # Disable specific tools
    tools = await pipeline.discover_tools(
        disabled_tool_ids=["web_search"]
    )

    tool_names = [t.name for t in tools]

    # Should not have blacklisted tool
    assert "web_search" not in tool_names


@pytest.mark.asyncio
async def test_tool_discovery_wildcard():
    """Test wildcard pattern in whitelist"""
    pipeline = get_tool_discovery_pipeline()

    # Enable all HANA tools
    tools = await pipeline.discover_tools(
        notebook_id="test-nb",
        enabled_tool_ids=["search_*", "query_*"]
    )

    tool_names = [t.name for t in tools]

    # All tools should match pattern
    for name in tool_names:
        assert name.startswith("search_") or name.startswith("query_")
