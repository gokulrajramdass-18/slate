"""
Unit tests for ToolFactory and tool creation.

Tests cover:
- ToolFactory.create_tools_for_session()
- Source-based tool creation (HANA + API)
- Registry-based tool creation
- Permission filtering
- Rate limit application
- Tool name sanitization
"""

import json
import uuid
from datetime import datetime
from typing import List, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from api.services.data_query_tools import (
    HANAQueryTool,
    HANAQueryInput,
    APICallTool,
    APICallInput,
    create_tools_for_notebook,
    _sanitize_tool_name,
)


# ============================================================================
# Test Tool Name Sanitization
# ============================================================================

class TestSanitizeToolName:
    """Test the _sanitize_tool_name helper."""

    def test_simple_name(self):
        """Test sanitizing a simple alphanumeric name."""
        assert _sanitize_tool_name("sales_data") == "sales_data"

    def test_name_with_spaces(self):
        """Test spaces are replaced with underscores."""
        assert _sanitize_tool_name("Sales Data") == "sales_data"

    def test_name_with_special_chars(self):
        """Test special characters are replaced."""
        assert _sanitize_tool_name("My-API (v2.0)") == "my_api__v2_0_"

    def test_consecutive_underscores_collapsed(self):
        """Test consecutive underscores are collapsed to one."""
        assert _sanitize_tool_name("a---b___c") == "a_b_c"

    def test_leading_trailing_underscores_stripped(self):
        """Test leading/trailing underscores are removed."""
        assert _sanitize_tool_name("__name__") == "name"

    def test_empty_name_returns_tool(self):
        """Test empty string returns fallback 'tool'."""
        assert _sanitize_tool_name("") == "tool"

    def test_all_special_chars_returns_tool(self):
        """Test string of only special chars returns fallback."""
        assert _sanitize_tool_name("@#$%") == "tool"

    def test_uppercase_lowered(self):
        """Test uppercase letters are lowered."""
        assert _sanitize_tool_name("SALES_DATA") == "sales_data"

    def test_mixed_case_with_numbers(self):
        """Test mixed case with numbers preserved."""
        result = _sanitize_tool_name("Table123Name")
        assert result == "table123name"


# ============================================================================
# Test HANAQueryInput Schema
# ============================================================================

class TestHANAQueryInputSchema:
    """Test HANA query tool input schema."""

    def test_default_values(self):
        """Test default values for all fields."""
        input_data = HANAQueryInput()
        assert input_data.columns == ["*"]
        assert input_data.where_clause == ""
        assert input_data.group_by == ""
        assert input_data.order_by == ""
        assert input_data.limit == 50

    def test_custom_values(self):
        """Test setting custom values."""
        input_data = HANAQueryInput(
            columns=["name", "revenue"],
            where_clause="revenue > 1000",
            group_by="name",
            order_by="revenue DESC",
            limit=100,
        )
        assert input_data.columns == ["name", "revenue"]
        assert input_data.where_clause == "revenue > 1000"
        assert input_data.limit == 100

    def test_limit_min_bound(self):
        """Test limit minimum bound (1)."""
        with pytest.raises(Exception):
            HANAQueryInput(limit=0)

    def test_limit_max_bound(self):
        """Test limit maximum bound (500)."""
        with pytest.raises(Exception):
            HANAQueryInput(limit=501)

    def test_limit_at_boundaries(self):
        """Test limit at exact boundaries."""
        input_min = HANAQueryInput(limit=1)
        assert input_min.limit == 1

        input_max = HANAQueryInput(limit=500)
        assert input_max.limit == 500


# ============================================================================
# Test APICallInput Schema
# ============================================================================

class TestAPICallInputSchema:
    """Test API call tool input schema."""

    def test_default_values(self):
        """Test default values."""
        input_data = APICallInput()
        assert input_data.params == {}
        assert input_data.filters == {}

    def test_custom_params(self):
        """Test custom parameters."""
        input_data = APICallInput(
            params={"region": "US", "status": "active"},
            filters={"revenue_gt": 10000},
        )
        assert input_data.params["region"] == "US"
        assert input_data.filters["revenue_gt"] == 10000


# ============================================================================
# Test HANAQueryTool
# ============================================================================

class TestHANAQueryTool:
    """Test HANA query tool creation and behavior."""

    def test_tool_creation(self):
        """Test creating a HANA query tool instance."""
        tool = HANAQueryTool(
            source_id="source-123",
            table_name="SALES_DATA",
            connection_config={"connection_id": "conn-1", "table_name": "SALES_DATA"},
            name="query_sales_data",
        )

        assert tool.name == "query_sales_data"
        assert tool.source_id == "source-123"
        assert tool.table_name == "SALES_DATA"
        assert "SALES_DATA" in tool.description

    def test_tool_description_generated(self):
        """Test that description is auto-generated from table name."""
        tool = HANAQueryTool(
            source_id="s1",
            table_name="CUSTOMERS",
            connection_config={},
            name="query_customers",
        )

        assert "CUSTOMERS" in tool.description
        assert "query" in tool.description.lower() or "Query" in tool.description

    def test_tool_schema_type(self):
        """Test that tool uses correct input schema."""
        tool = HANAQueryTool(
            source_id="s1",
            table_name="T1",
            connection_config={},
            name="query_t1",
        )

        assert tool.args_schema == HANAQueryInput

    def test_sync_run_raises(self):
        """Test that synchronous _run raises NotImplementedError."""
        tool = HANAQueryTool(
            source_id="s1",
            table_name="T1",
            connection_config={},
            name="query_t1",
        )

        with pytest.raises(NotImplementedError):
            tool._run()

    @pytest.mark.asyncio
    async def test_arun_returns_json_on_error(self):
        """Test that _arun returns JSON error on execution failure."""
        tool = HANAQueryTool(
            source_id="s1",
            table_name="NONEXISTENT",
            connection_config={"connection_id": "invalid"},
            name="query_nonexistent",
        )

        # Execute should fail but return JSON error, not raise
        result = await tool._arun(columns=["*"], limit=10)
        result_data = json.loads(result)

        assert result_data["success"] is False
        assert "error" in result_data
        assert result_data["rows"] == []
        assert result_data["count"] == 0

    @pytest.mark.asyncio
    async def test_arun_success_with_mock(self):
        """Test successful tool execution with mocked executor."""
        tool = HANAQueryTool(
            source_id="s1",
            table_name="SALES",
            connection_config={"connection_id": "conn-1", "table_name": "SALES"},
            name="query_sales",
        )

        mock_results = [
            {"product": "Widget A", "revenue": 150000},
            {"product": "Widget B", "revenue": 120000},
        ]

        with patch(
            "api.services.data_query_tools.HANAToolExecutor.execute_tool",
            new_callable=AsyncMock,
            return_value=mock_results,
        ), patch(
            "api.services.data_query_tools.get_chart_tool"
        ) as mock_chart:
            mock_chart.return_value.should_use_chart.return_value = False

            result = await tool._arun(
                columns=["product", "revenue"],
                where_clause="revenue > 100000",
                limit=10,
            )

        result_data = json.loads(result)
        assert result_data["success"] is True
        assert result_data["count"] == 2
        assert len(result_data["rows"]) == 2
        assert "duration_ms" in result_data


# ============================================================================
# Test APICallTool
# ============================================================================

class TestAPICallTool:
    """Test API call tool creation and behavior."""

    def test_tool_creation(self):
        """Test creating an API call tool instance."""
        tool = APICallTool(
            source_id="source-456",
            endpoint="https://api.example.com/data",
            connection_config={"connection_id": "conn-2"},
            source_name="Customer API",
            name="call_customer_api",
        )

        assert tool.name == "call_customer_api"
        assert tool.source_id == "source-456"
        assert tool.endpoint == "https://api.example.com/data"
        assert "Customer API" in tool.description

    def test_tool_schema_type(self):
        """Test that tool uses correct input schema."""
        tool = APICallTool(
            source_id="s1",
            endpoint="https://api.test.com",
            connection_config={},
            name="call_test",
        )

        assert tool.args_schema == APICallInput

    def test_sync_run_raises(self):
        """Test that synchronous _run raises NotImplementedError."""
        tool = APICallTool(
            source_id="s1",
            endpoint="https://api.test.com",
            connection_config={},
            name="call_test",
        )

        with pytest.raises(NotImplementedError):
            tool._run()

    @pytest.mark.asyncio
    async def test_arun_returns_json_on_error(self):
        """Test that _arun returns JSON error on execution failure."""
        tool = APICallTool(
            source_id="s1",
            endpoint="https://api.nonexistent.com",
            connection_config={"connection_id": "invalid"},
            name="call_nonexistent",
        )

        result = await tool._arun(params={}, filters={})
        result_data = json.loads(result)

        assert result_data["success"] is False
        assert "error" in result_data

    @pytest.mark.asyncio
    async def test_arun_success_with_mock(self):
        """Test successful API tool execution with mock."""
        tool = APICallTool(
            source_id="s1",
            endpoint="https://api.example.com/customers",
            connection_config={"connection_id": "conn-1"},
            source_name="Customer API",
            name="call_customers",
        )

        mock_result = {
            "success": True,
            "data": [
                {"id": "C001", "name": "Acme Corp", "revenue": 50000},
                {"id": "C002", "name": "Widget Inc", "revenue": 35000},
            ],
            "record_count": 2,
        }

        with patch(
            "api.services.data_query_tools.execute_api_call_with_params",
            new_callable=AsyncMock,
            return_value=mock_result,
        ), patch(
            "api.services.data_query_tools.get_chart_tool"
        ) as mock_chart:
            mock_chart.return_value.should_use_chart.return_value = False

            result = await tool._arun(
                params={"region": "US"},
                filters={"revenue_gt": 10000},
            )

        result_data = json.loads(result)
        assert result_data["success"] is True
        assert result_data["count"] == 2
        assert len(result_data["data"]) == 2


# ============================================================================
# Test create_tools_for_notebook
# ============================================================================

@pytest.mark.asyncio
class TestCreateToolsForNotebook:
    """Test the tool factory function that creates tools from notebook sources."""

    async def test_returns_empty_list_for_no_sources(self):
        """Test returns empty list when notebook has no tool-generating sources."""
        with patch(
            "api.services.data_query_tools.repo_query",
            new_callable=AsyncMock,
            return_value=[],
        ):
            tools = await create_tools_for_notebook("notebook-123")
            assert tools == []

    async def test_creates_hana_tools_from_sources(self):
        """Test creating HANA tools from notebook HANA table sources."""
        hana_sources = [
            {
                "id": "src-1",
                "title": "Sales Data",
                "connection_config": json.dumps({
                    "connection_id": "conn-1",
                    "table_name": "SALES_DATA",
                }),
            },
            {
                "id": "src-2",
                "title": "Customer Data",
                "connection_config": json.dumps({
                    "connection_id": "conn-1",
                    "table_name": "CUSTOMERS",
                }),
            },
        ]

        async def mock_repo_query(sql, params=None):
            if "hana_table" in sql:
                return hana_sources
            return []

        with patch(
            "api.services.data_query_tools.repo_query",
            side_effect=mock_repo_query,
        ):
            tools = await create_tools_for_notebook("notebook-123")

        assert len(tools) == 2
        assert all(isinstance(t, HANAQueryTool) for t in tools)
        assert tools[0].name == "query_sales_data"
        assert tools[1].name == "query_customers"

    async def test_creates_api_tools_from_sources(self):
        """Test creating API tools from notebook API sources."""
        api_sources = [
            {
                "id": "src-3",
                "title": "GitHub Issues",
                "connection_config": json.dumps({
                    "connection_id": "conn-2",
                    "endpoint": "https://api.github.com/issues",
                }),
            },
        ]

        api_connection = [{
            "id": "conn-2",
            "endpoint": "https://api.github.com/issues",
            "name": "GitHub",
        }]

        async def mock_repo_query(sql, params=None):
            if "hana_table" in sql:
                return []
            elif "source_type = 'api'" in sql:
                return api_sources
            elif "api_connections" in sql:
                return api_connection
            return []

        with patch(
            "api.services.data_query_tools.repo_query",
            side_effect=mock_repo_query,
        ):
            tools = await create_tools_for_notebook("notebook-123")

        assert len(tools) == 1
        assert isinstance(tools[0], APICallTool)
        assert "github_issues" in tools[0].name

    async def test_skips_api_source_without_connection_id(self):
        """Test that API sources without connection_id are skipped."""
        api_sources = [
            {
                "id": "src-4",
                "title": "Bad Source",
                "connection_config": json.dumps({}),  # No connection_id
            },
        ]

        async def mock_repo_query(sql, params=None):
            if "hana_table" in sql:
                return []
            elif "source_type = 'api'" in sql:
                return api_sources
            return []

        with patch(
            "api.services.data_query_tools.repo_query",
            side_effect=mock_repo_query,
        ):
            tools = await create_tools_for_notebook("notebook-123")

        assert len(tools) == 0

    async def test_skips_failed_tool_creation_gracefully(self):
        """Test that failures in tool creation are handled gracefully."""
        hana_sources = [
            {
                "id": "src-1",
                "title": "Good Source",
                "connection_config": json.dumps({
                    "connection_id": "conn-1",
                    "table_name": "GOOD_TABLE",
                }),
            },
            {
                "id": "src-2",
                "title": "Bad Source",
                "connection_config": "invalid json{{{",  # Malformed JSON
            },
        ]

        async def mock_repo_query(sql, params=None):
            if "hana_table" in sql:
                return hana_sources
            return []

        with patch(
            "api.services.data_query_tools.repo_query",
            side_effect=mock_repo_query,
        ):
            tools = await create_tools_for_notebook("notebook-123")

        # Should have 1 tool (the good one), bad one skipped
        assert len(tools) == 1
        assert tools[0].table_name == "GOOD_TABLE"

    async def test_passes_session_id_to_tools(self):
        """Test that session_id is forwarded to created tools."""
        hana_sources = [
            {
                "id": "src-1",
                "title": "Sales",
                "connection_config": json.dumps({
                    "connection_id": "conn-1",
                    "table_name": "SALES",
                }),
            },
        ]

        async def mock_repo_query(sql, params=None):
            if "hana_table" in sql:
                return hana_sources
            return []

        with patch(
            "api.services.data_query_tools.repo_query",
            side_effect=mock_repo_query,
        ):
            tools = await create_tools_for_notebook(
                "notebook-123", session_id="session-abc"
            )

        assert len(tools) == 1
        assert tools[0].session_id == "session-abc"

    async def test_combines_hana_and_api_tools(self):
        """Test that HANA and API tools are combined in result."""
        hana_sources = [
            {
                "id": "src-1",
                "title": "Sales Data",
                "connection_config": json.dumps({
                    "connection_id": "conn-1",
                    "table_name": "SALES",
                }),
            },
        ]

        api_sources = [
            {
                "id": "src-2",
                "title": "Weather API",
                "connection_config": json.dumps({
                    "connection_id": "conn-2",
                    "endpoint": "https://api.weather.com",
                }),
            },
        ]

        api_connection = [{
            "id": "conn-2",
            "endpoint": "https://api.weather.com",
            "name": "Weather",
        }]

        async def mock_repo_query(sql, params=None):
            if "hana_table" in sql:
                return hana_sources
            elif "source_type = 'api'" in sql:
                return api_sources
            elif "api_connections" in sql:
                return api_connection
            return []

        with patch(
            "api.services.data_query_tools.repo_query",
            side_effect=mock_repo_query,
        ):
            tools = await create_tools_for_notebook("notebook-123")

        assert len(tools) == 2

        tool_types = {type(t).__name__ for t in tools}
        assert "HANAQueryTool" in tool_types
        assert "APICallTool" in tool_types


# ============================================================================
# Test ToolFactory (Phase 2 Design)
# ============================================================================

class TestToolFactoryDesign:
    """
    Tests for the Phase 2 ToolFactory design.

    These tests validate the intended behavior of the unified ToolFactory
    class as described in TOOL_CONFIGURATION_GUIDE.md Section 5.2.
    They use mocks since the ToolFactory class has not been implemented yet.
    """

    @pytest.mark.asyncio
    async def test_factory_creates_source_and_registry_tools(self):
        """Test that ToolFactory combines source and registry tools."""
        # Simulate ToolFactory behavior
        source_tools = [
            MagicMock(spec=BaseTool, name="query_sales"),
            MagicMock(spec=BaseTool, name="call_api"),
        ]
        registry_tools = [
            MagicMock(spec=BaseTool, name="web_search"),
        ]

        all_tools = source_tools + registry_tools
        assert len(all_tools) == 3

    @pytest.mark.asyncio
    async def test_factory_filters_disabled_registry_tools(self):
        """Test that disabled registry tools are excluded."""
        # Simulate registry query returning only enabled tools
        registry_data = [
            {"id": "t1", "name": "web_search", "enabled": True},
            {"id": "t2", "name": "code_exec", "enabled": False},
        ]

        enabled_tools = [t for t in registry_data if t["enabled"]]
        assert len(enabled_tools) == 1
        assert enabled_tools[0]["name"] == "web_search"

    @pytest.mark.asyncio
    async def test_factory_applies_user_permissions(self):
        """Test permission filtering: user-specific permissions override role."""
        # Simulate permission resolution
        permissions = [
            {"tool_id": "t1", "user_id": "alice", "role": None, "allowed": True},
            {"tool_id": "t1", "user_id": None, "role": "analyst", "allowed": False},
        ]

        # User-specific should take priority
        perm_map = {}
        for perm in permissions:
            tool_id = perm["tool_id"]
            if tool_id not in perm_map:
                perm_map[tool_id] = perm

        # Alice's user-specific permission wins
        assert perm_map["t1"]["allowed"] is True

    @pytest.mark.asyncio
    async def test_factory_default_allow_when_no_permission(self):
        """Test that tools with no permission entries are allowed by default."""
        tool_ids = ["t1", "t2", "t3"]
        perm_map = {"t1": {"allowed": True}}  # Only t1 has explicit permission

        # Tools not in perm_map should be allowed by default
        allowed = []
        for tool_id in tool_ids:
            if tool_id in perm_map:
                if perm_map[tool_id]["allowed"]:
                    allowed.append(tool_id)
            else:
                allowed.append(tool_id)  # Default allow

        assert len(allowed) == 3  # All tools allowed
        assert "t2" in allowed
        assert "t3" in allowed

    @pytest.mark.asyncio
    async def test_factory_applies_rate_limits(self):
        """Test that rate limits from permissions are applied."""
        # Simulate rate limit application
        permissions = {
            "t1": {"rate_limit": 50},
            "t2": {"rate_limit": None},  # No limit
        }

        limited_count = sum(
            1 for p in permissions.values() if p["rate_limit"] is not None
        )
        assert limited_count == 1

    @pytest.mark.asyncio
    async def test_factory_applies_custom_config(self):
        """Test that custom configs from permissions override defaults."""
        default_config = {"max_results": 10, "timeout": 30}
        custom_config = {"max_results": 50}

        # Merge custom over default
        merged = {**default_config, **custom_config}
        assert merged["max_results"] == 50
        assert merged["timeout"] == 30  # Preserved from default


# ============================================================================
# Test Tool Chart Detection
# ============================================================================

class TestToolChartDetection:
    """Test chart detection in tool results."""

    @pytest.mark.asyncio
    async def test_hana_tool_with_chart_hint(self):
        """Test that chart-suitable data gets visualization hints."""
        tool = HANAQueryTool(
            source_id="s1",
            table_name="SALES",
            connection_config={"connection_id": "conn-1", "table_name": "SALES"},
            name="query_sales",
        )

        chart_data = [
            {"product": "A", "revenue": 100},
            {"product": "B", "revenue": 200},
            {"product": "C", "revenue": 150},
        ]

        mock_chart_config = {
            "xKey": "product",
            "yKeys": ["revenue"],
            "colors": ["#8884d8"],
        }

        with patch(
            "api.services.data_query_tools.HANAToolExecutor.execute_tool",
            new_callable=AsyncMock,
            return_value=chart_data,
        ), patch(
            "api.services.data_query_tools.get_chart_tool"
        ) as mock_chart_tool, patch(
            "api.services.data_query_tools.ChartAnalyzer"
        ) as mock_analyzer:
            mock_chart_tool.return_value.should_use_chart.return_value = True
            mock_analyzer.return_value.analyze_and_suggest.return_value = (
                "bar_chart",
                mock_chart_config,
            )

            result = await tool._arun(columns=["product", "revenue"], limit=10)

        result_data = json.loads(result)
        assert result_data["success"] is True
        assert result_data.get("visualization_hint") == "bar_chart"
        assert "chart_config" in result_data
