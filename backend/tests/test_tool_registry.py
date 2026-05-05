"""
Tests for the Tool Registry and Tool Factory.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from open_notebook.agents.tool_registry import (
    AgentRole,
    ToolCategory,
    ToolMetadata,
    ToolRegistry,
    get_tool_registry,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_registry():
    """Reset the singleton registry before each test."""
    registry = get_tool_registry()
    registry.reset()
    yield registry
    registry.reset()


class _DummyInput(BaseModel):
    query: str = Field(description="A test query")


class _DummyTool(BaseTool):
    name: str = "dummy_tool"
    description: str = "A dummy tool for testing"
    args_schema: type = _DummyInput

    def _run(self, query: str) -> str:
        return f"result:{query}"

    async def _arun(self, query: str) -> str:
        return f"async_result:{query}"


# ---------------------------------------------------------------------------
# Singleton behaviour
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_returns_same_instance(self):
        a = ToolRegistry()
        b = ToolRegistry()
        assert a is b

    def test_get_tool_registry_returns_singleton(self):
        a = get_tool_registry()
        b = get_tool_registry()
        assert a is b


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_register_tool(self, clean_registry):
        reg = clean_registry
        reg.register(
            name="test",
            tool=lambda x: x,
            description="desc",
            category=ToolCategory.SEARCH,
        )
        assert reg.tool_count == 1
        assert reg.get_tool("test") is not None

    def test_register_langchain_tool(self, clean_registry):
        reg = clean_registry
        tool = _DummyTool()
        reg.register_langchain_tool(tool, category=ToolCategory.FILE_OPS)
        assert reg.tool_count == 1
        meta = reg.get_metadata("dummy_tool")
        assert meta is not None
        assert meta.category == ToolCategory.FILE_OPS
        assert meta.is_async is True  # has _arun

    def test_register_with_roles(self, clean_registry):
        reg = clean_registry
        roles = {AgentRole.ANALYST, AgentRole.ADMIN}
        reg.register(
            name="restricted",
            tool="t",
            description="d",
            category=ToolCategory.DATABASE,
            allowed_roles=roles,
        )
        meta = reg.get_metadata("restricted")
        assert meta.allowed_roles == roles

    def test_unregister(self, clean_registry):
        reg = clean_registry
        reg.register(name="x", tool="t", description="d", category=ToolCategory.WEB)
        assert reg.unregister("x") is True
        assert reg.get_tool("x") is None
        assert reg.tool_count == 0

    def test_unregister_nonexistent(self, clean_registry):
        assert clean_registry.unregister("nope") is False

    def test_overwrite_registration(self, clean_registry):
        reg = clean_registry
        reg.register(name="a", tool="v1", description="d1", category=ToolCategory.API)
        reg.register(name="a", tool="v2", description="d2", category=ToolCategory.WEB)
        assert reg.tool_count == 1
        assert reg.get_tool("a") == "v2"
        assert reg.get_metadata("a").category == ToolCategory.WEB


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

class TestRetrieval:
    def _seed(self, reg):
        reg.register(
            name="search1", tool="s1", description="kw search",
            category=ToolCategory.SEARCH,
            allowed_roles={AgentRole.RESEARCHER, AgentRole.ADMIN},
            tags=["keyword"],
        )
        reg.register(
            name="db1", tool="d1", description="hana query",
            category=ToolCategory.DATABASE,
            allowed_roles={AgentRole.ANALYST, AgentRole.ADMIN},
            tags=["hana"],
        )
        reg.register(
            name="file1", tool="f1", description="read file",
            category=ToolCategory.FILE_OPS,
            allowed_roles=set(AgentRole),
            tags=["file", "read"],
        )

    def test_get_by_category(self, clean_registry):
        self._seed(clean_registry)
        tools = clean_registry.get_tools_by_category(ToolCategory.SEARCH)
        assert "search1" in tools
        assert "db1" not in tools

    def test_get_for_role(self, clean_registry):
        self._seed(clean_registry)
        tools = clean_registry.get_tools_for_role(AgentRole.RESEARCHER)
        assert "search1" in tools
        assert "file1" in tools
        assert "db1" not in tools  # researcher not in analyst-only

    def test_get_for_role_and_category(self, clean_registry):
        self._seed(clean_registry)
        tools = clean_registry.get_tools_for_role_and_category(
            AgentRole.ADMIN, ToolCategory.DATABASE
        )
        assert "db1" in tools
        assert len(tools) == 1

    def test_search_by_name(self, clean_registry):
        self._seed(clean_registry)
        results = clean_registry.search_tools("search")
        assert any(m.name == "search1" for m in results)

    def test_search_by_tag(self, clean_registry):
        self._seed(clean_registry)
        results = clean_registry.search_tools("hana")
        assert any(m.name == "db1" for m in results)

    def test_list_tools(self, clean_registry):
        self._seed(clean_registry)
        all_tools = clean_registry.list_tools()
        assert len(all_tools) == 3

    def test_categories_property(self, clean_registry):
        self._seed(clean_registry)
        cats = clean_registry.categories
        assert cats["search"] == 1
        assert cats["database"] == 1
        assert cats["file_ops"] == 1


# ---------------------------------------------------------------------------
# Execution tracking
# ---------------------------------------------------------------------------

class TestExecutionTracking:
    def test_track_success(self, clean_registry):
        ex = clean_registry.track_execution(
            tool_name="my_tool", success=True, duration_ms=42.5
        )
        assert ex.success is True
        assert ex.duration_ms == 42.5

    def test_track_failure(self, clean_registry):
        ex = clean_registry.track_execution(
            tool_name="my_tool", success=False, error="boom", duration_ms=10
        )
        assert ex.success is False
        assert ex.error == "boom"

    def test_stats_aggregation(self, clean_registry):
        reg = clean_registry
        reg.track_execution("a", success=True, duration_ms=10)
        reg.track_execution("a", success=True, duration_ms=20)
        reg.track_execution("a", success=False, duration_ms=5, error="err")
        reg.track_execution("b", success=True, duration_ms=100)

        stats = reg.get_execution_stats()
        assert stats["total"] == 4
        assert stats["by_tool"]["a"]["count"] == 3
        assert stats["by_tool"]["a"]["successes"] == 2
        assert stats["by_tool"]["a"]["failures"] == 1
        assert stats["by_tool"]["a"]["avg_ms"] == pytest.approx(11.67, abs=0.01)
        assert stats["by_tool"]["b"]["count"] == 1

    def test_recent_executions(self, clean_registry):
        reg = clean_registry
        for i in range(5):
            reg.track_execution(f"t{i}", success=True, duration_ms=float(i))
        recent = reg.get_recent_executions(limit=3)
        assert len(recent) == 3
        assert recent[-1].tool_name == "t4"

    def test_history_trim(self, clean_registry):
        reg = clean_registry
        reg._max_execution_history = 5
        for i in range(10):
            reg.track_execution(f"t{i}", success=True, duration_ms=1)
        assert len(reg._executions) == 5


# ---------------------------------------------------------------------------
# ToolMetadata serialization
# ---------------------------------------------------------------------------

class TestMetadataSerialization:
    def test_to_dict(self):
        meta = ToolMetadata(
            name="x",
            description="desc",
            category=ToolCategory.API,
            allowed_roles={AgentRole.ADMIN},
            tags=["a", "b"],
        )
        d = meta.to_dict()
        assert d["name"] == "x"
        assert d["category"] == "api"
        assert "admin" in d["allowed_roles"]

    def test_registry_to_dict(self, clean_registry):
        reg = clean_registry
        reg.register(name="t", tool="v", description="d", category=ToolCategory.WEB)
        d = reg.to_dict()
        assert d["tool_count"] == 1
        assert "t" in d["tools"]


# ---------------------------------------------------------------------------
# Tool Factory integration
# ---------------------------------------------------------------------------

class TestToolFactory:
    def test_initialize_tools_registers_expected_categories(self, clean_registry):
        """initialize_tools should register tools in multiple categories."""
        from open_notebook.agents.tool_factory import initialize_tools

        results = initialize_tools()
        reg = clean_registry

        assert reg.tool_count > 0
        # At minimum search, file_ops, analysis, and web should be present
        assert results.get("search", 0) >= 1
        assert results.get("file_ops", 0) >= 1
        assert results.get("analysis", 0) >= 1

    def test_get_tools_for_agent(self, clean_registry):
        from open_notebook.agents.tool_factory import initialize_tools, get_tools_for_agent

        initialize_tools()
        tools = get_tools_for_agent(AgentRole.ADMIN)
        assert len(tools) > 0

    def test_get_tools_for_agent_with_category_filter(self, clean_registry):
        from open_notebook.agents.tool_factory import initialize_tools, get_tools_for_agent

        initialize_tools()
        tools = get_tools_for_agent(AgentRole.ADMIN, categories=[ToolCategory.SEARCH])
        assert all(
            clean_registry.get_metadata(getattr(t, "name", "")).category == ToolCategory.SEARCH
            for t in tools
            if clean_registry.get_metadata(getattr(t, "name", "")) is not None
        )

    def test_notebook_search_tool_is_langchain_compatible(self, clean_registry):
        from open_notebook.agents.tool_factory import NotebookSearchTool

        tool = NotebookSearchTool()
        assert isinstance(tool, BaseTool)
        assert tool.name == "notebook_search"

    def test_data_summary_tool_runs_sync_raises(self, clean_registry):
        from open_notebook.agents.tool_factory import DataSummaryTool

        tool = DataSummaryTool()
        with pytest.raises(NotImplementedError):
            tool._run(data="[]")

    @pytest.mark.asyncio
    async def test_data_summary_tool_async(self, clean_registry):
        from open_notebook.agents.tool_factory import DataSummaryTool

        tool = DataSummaryTool()
        data = json.dumps([
            {"name": "Alice", "age": 30, "score": 85.5},
            {"name": "Bob", "age": 25, "score": 92.0},
            {"name": "Carol", "age": 35, "score": 78.0},
        ])
        result = await tool._arun(data=data)
        parsed = json.loads(result)
        assert parsed["row_count"] == 3
        assert "age" in parsed["columns"]
        assert parsed["columns"]["age"]["type"] == "numeric"
        assert parsed["columns"]["age"]["min"] == 25
        assert parsed["columns"]["age"]["max"] == 35
        assert parsed["columns"]["name"]["type"] == "text"
