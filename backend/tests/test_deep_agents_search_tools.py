"""
Tests for Deep Agents Search Tool

Tests integration with existing SearchService.
"""

import pytest
import json
from deep_agents_integration.deep_agents_tools.search_tools import NotebookSearchTool


@pytest.mark.asyncio
async def test_search_tool_basic(test_notebook_with_sources):
    """Test basic search functionality"""
    tool = NotebookSearchTool(
        notebook_id=test_notebook_with_sources.id,
        session_id="test-session"
    )

    result = await tool._arun(
        query="test query",
        strategy="hybrid",
        limit=5
    )

    # Parse result
    data = json.loads(result)

    # Should return success
    assert data["success"] == True
    assert "results" in data
    assert data["strategy"] == "hybrid"


@pytest.mark.asyncio
async def test_search_tool_strategies(test_notebook_with_sources):
    """Test different search strategies"""
    tool = NotebookSearchTool(notebook_id=test_notebook_with_sources.id)

    strategies = ["keyword", "vector", "hybrid"]

    for strategy in strategies:
        result = await tool._arun(
            query="test query",
            strategy=strategy,
            limit=3
        )

        data = json.loads(result)
        assert data["success"] == True
        assert data["strategy"] == strategy


@pytest.mark.asyncio
async def test_search_tool_error_handling():
    """Test error handling for invalid notebook"""
    tool = NotebookSearchTool(notebook_id="nonexistent-notebook")

    result = await tool._arun(
        query="test query",
        strategy="hybrid"
    )

    data = json.loads(result)

    # Should return error gracefully
    assert data["success"] == False
    assert "error" in data


@pytest.mark.asyncio
async def test_search_tool_result_format(test_notebook_with_sources):
    """Test result format consistency"""
    tool = NotebookSearchTool(notebook_id=test_notebook_with_sources.id)

    result = await tool._arun(query="test", limit=2)
    data = json.loads(result)

    if data["success"] and data["results"]:
        # Check result structure
        first_result = data["results"][0]
        assert "rank" in first_result
        assert "source_id" in first_result
        assert "source_name" in first_result
        assert "content" in first_result
        assert "score" in first_result
        assert "strategy" in first_result
