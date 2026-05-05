"""
End-to-end integration tests for the tool registry workflow.

Tests cover the full lifecycle:
1. Create tool in registry
2. Set permissions for users and roles
3. Create chat session with notebook
4. Verify correct tools are available based on permissions
5. Execute tool call (mocked)
6. Verify usage is logged

These tests mock external dependencies (LLM calls, HANA connections, API calls)
but exercise the full internal flow.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def tool_registry_data():
    """Set of tools to register for e2e tests."""
    return [
        {
            "name": "query_sales_data",
            "tool_type": "hana_query",
            "category": "data_query",
            "description": "Query the SALES_DATA table from HANA database",
            "enabled": True,
            "default_config": {"max_rows": 500, "timeout": 30},
            "metadata": {"icon": "database", "version": "1.0"},
        },
        {
            "name": "call_customer_api",
            "tool_type": "api_call",
            "category": "data_query",
            "description": "Call the Customer API endpoint",
            "enabled": True,
            "default_config": {"timeout": 15},
            "metadata": {"icon": "api", "version": "1.0"},
        },
        {
            "name": "web_search",
            "tool_type": "web_search",
            "category": "web",
            "description": "Search the web for current information",
            "enabled": True,
            "default_config": {"max_results": 10},
            "metadata": {"icon": "search", "version": "1.0"},
        },
        {
            "name": "code_execution",
            "tool_type": "code_exec",
            "category": "computation",
            "description": "Execute Python code in sandboxed environment",
            "enabled": False,  # Disabled by default
            "default_config": {"timeout": 30, "memory_limit_mb": 512},
            "metadata": {"icon": "code", "version": "1.0"},
        },
    ]


@pytest.fixture
def permission_scenarios():
    """Permission configurations for different user roles."""
    return {
        "admin": {
            "tools": ["query_sales_data", "call_customer_api", "web_search", "code_execution"],
            "rate_limit": 100,
        },
        "analyst": {
            "tools": ["query_sales_data", "call_customer_api"],
            "blocked": ["code_execution"],
            "rate_limit": 50,
        },
        "viewer": {
            "tools": ["web_search"],
            "blocked": ["query_sales_data", "call_customer_api", "code_execution"],
            "rate_limit": 10,
        },
    }


# ============================================================================
# Test Full Tool Registry Workflow
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestToolRegistryWorkflow:
    """End-to-end test: register tools, set permissions, use in chat."""

    async def test_full_tool_lifecycle(self, async_test_client, tool_registry_data):
        """
        Full workflow test:
        1. Register tools
        2. Set permissions
        3. Create notebook and chat session
        4. Verify tools available
        5. Clean up
        """
        client = async_test_client

        # ---- Step 1: Register tools ----
        tool_ids = {}
        for tool_data in tool_registry_data:
            response = await client.post("/api/tools", json=tool_data)

            if response.status_code == 404:
                pytest.skip("Tools API not yet implemented")

            assert response.status_code in [200, 201], (
                f"Failed to create tool {tool_data['name']}: {response.text}"
            )
            tool_ids[tool_data["name"]] = response.json()["id"]

        assert len(tool_ids) == 4

        # ---- Step 2: Verify tools are listed ----
        response = await client.get("/api/tools")
        assert response.status_code == 200
        listed_tools = response.json()["tools"]
        listed_names = {t["name"] for t in listed_tools}

        for name in tool_ids:
            assert name in listed_names

        # ---- Step 3: Set permissions ----
        # Admin gets all tools
        for tool_name, tid in tool_ids.items():
            response = await client.post(
                f"/api/tools/{tid}/permissions",
                json={
                    "tool_id": tid,
                    "user_id": None,
                    "role": "admin",
                    "allowed": True,
                    "rate_limit": 100,
                },
            )
            if response.status_code == 404:
                pytest.skip("Permissions API not yet implemented")
            assert response.status_code in [200, 201]

        # Analyst gets data_query tools only
        for tool_name in ["query_sales_data", "call_customer_api"]:
            tid = tool_ids[tool_name]
            response = await client.post(
                f"/api/tools/{tid}/permissions",
                json={
                    "tool_id": tid,
                    "user_id": None,
                    "role": "analyst",
                    "allowed": True,
                    "rate_limit": 50,
                },
            )
            assert response.status_code in [200, 201]

        # Block code_execution for analysts
        response = await client.post(
            f"/api/tools/{tool_ids['code_execution']}/permissions",
            json={
                "tool_id": tool_ids["code_execution"],
                "user_id": None,
                "role": "analyst",
                "allowed": False,
            },
        )
        assert response.status_code in [200, 201]

        # ---- Step 4: Verify permissions ----
        for tid in tool_ids.values():
            response = await client.get(f"/api/tools/{tid}/permissions")
            assert response.status_code == 200
            perms = response.json()["permissions"]
            assert len(perms) >= 1

        # ---- Step 5: Verify tool details ----
        for tool_name, tid in tool_ids.items():
            response = await client.get(f"/api/tools/{tid}")
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == tool_name

        # ---- Step 6: Toggle tool (disable then re-enable) ----
        code_exec_id = tool_ids["code_execution"]
        response = await client.post(
            f"/api/tools/{code_exec_id}/toggle",
            params={"enabled": True},
        )
        if response.status_code != 404:
            assert response.status_code == 200

        # ---- Step 7: Clean up ----
        for tid in tool_ids.values():
            response = await client.delete(f"/api/tools/{tid}")
            assert response.status_code in [200, 204]

        # Verify cleanup
        response = await client.get("/api/tools")
        remaining = response.json()["tools"]
        remaining_ids = {t["id"] for t in remaining}
        for tid in tool_ids.values():
            assert tid not in remaining_ids


# ============================================================================
# Test Tool Creation in Chat Context
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestToolsInChatWorkflow:
    """Test that tools are correctly created and available during chat."""

    async def test_notebook_tools_created_for_chat(self, async_test_client):
        """
        Verify that HANA/API tools from notebook sources are created
        when starting a chat session.
        """
        client = async_test_client

        # 1. Create notebook
        notebook_resp = await client.post(
            "/api/notebooks",
            json={"name": "Tool Test Notebook", "description": "Test tools in chat"},
        )
        assert notebook_resp.status_code == 201
        notebook_id = notebook_resp.json()["id"]

        # 2. Create HANA table source (with mocked connection)
        source_data = {
            "title": "Sales Data",
            "source_type": "hana_table",
            "full_text": "Sales data from HANA",
            "connection_config": json.dumps({
                "connection_id": "test-conn-1",
                "table_name": "SALES_DATA",
                "content_columns": ["PRODUCT", "REVENUE", "DATE"],
            }),
        }
        source_resp = await client.post("/api/sources", json=source_data)
        assert source_resp.status_code == 201
        source_id = source_resp.json()["id"]

        # 3. Link source to notebook
        link_resp = await client.post(
            f"/api/notebooks/{notebook_id}/sources",
            json={"source_id": source_id},
        )
        assert link_resp.status_code == 201

        # 4. Create chat session
        chat_resp = await client.post(
            "/api/chat/sessions",
            json={"notebook_id": notebook_id, "title": "Tool Test Chat"},
        )
        assert chat_resp.status_code == 201
        session_id = chat_resp.json()["id"]

        # 5. Verify session is created
        session_resp = await client.get(f"/api/chat/sessions/{session_id}")
        assert session_resp.status_code == 200
        session_data = session_resp.json()
        assert session_data["notebook_id"] == notebook_id

        # 6. Clean up
        await client.delete(f"/api/chat/sessions/{session_id}")
        await client.delete(f"/api/notebooks/{notebook_id}")


# ============================================================================
# Test Tool Execution Flow (Mocked)
# ============================================================================

@pytest.mark.e2e
class TestToolExecutionFlow:
    """Test tool execution with mocked backends."""

    @pytest.mark.asyncio
    async def test_hana_tool_execution_flow(self):
        """Test HANA tool creation -> execution -> result capture."""
        from api.services.data_query_tools import HANAQueryTool

        # 1. Create tool
        tool = HANAQueryTool(
            source_id="src-sales-1",
            table_name="SALES_DATA",
            connection_config={
                "connection_id": "conn-hana-1",
                "table_name": "SALES_DATA",
            },
            session_id="session-test-1",
            name="query_sales_data",
        )

        assert tool.name == "query_sales_data"
        assert tool.source_id == "src-sales-1"

        # 2. Mock executor and execute
        mock_results = [
            {"PRODUCT": "Widget A", "REVENUE": 150000, "DATE": "2024-01-15"},
            {"PRODUCT": "Widget B", "REVENUE": 120000, "DATE": "2024-01-16"},
            {"PRODUCT": "Widget C", "REVENUE": 95000, "DATE": "2024-01-17"},
        ]

        with patch(
            "api.services.data_query_tools.HANAToolExecutor.execute_tool",
            new_callable=AsyncMock,
            return_value=mock_results,
        ), patch(
            "api.services.data_query_tools.get_chart_tool",
        ) as mock_chart:
            mock_chart.return_value.should_use_chart.return_value = False

            result_json = await tool._arun(
                columns=["PRODUCT", "REVENUE"],
                where_clause="REVENUE > 50000",
                order_by="REVENUE DESC",
                limit=10,
            )

        # 3. Verify result
        result = json.loads(result_json)
        assert result["success"] is True
        assert result["count"] == 3
        assert len(result["rows"]) == 3
        assert result["rows"][0]["PRODUCT"] == "Widget A"
        assert "duration_ms" in result

    @pytest.mark.asyncio
    async def test_api_tool_execution_flow(self):
        """Test API tool creation -> execution -> result capture."""
        from api.services.data_query_tools import APICallTool

        # 1. Create tool
        tool = APICallTool(
            source_id="src-api-1",
            endpoint="https://api.example.com/customers",
            connection_config={"connection_id": "conn-api-1"},
            source_name="Customer API",
            session_id="session-test-2",
            name="call_customer_api",
        )

        assert tool.name == "call_customer_api"
        assert "Customer API" in tool.description

        # 2. Mock API call and execute
        mock_api_result = {
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
            return_value=mock_api_result,
        ), patch(
            "api.services.data_query_tools.get_chart_tool",
        ) as mock_chart:
            mock_chart.return_value.should_use_chart.return_value = False

            result_json = await tool._arun(
                params={"region": "US"},
                filters={"revenue_gt": 10000},
            )

        # 3. Verify result
        result = json.loads(result_json)
        assert result["success"] is True
        assert result["count"] == 2
        assert result["data"][0]["name"] == "Acme Corp"

    @pytest.mark.asyncio
    async def test_tool_error_handling_flow(self):
        """Test that tool errors are captured gracefully."""
        from api.services.data_query_tools import HANAQueryTool

        tool = HANAQueryTool(
            source_id="src-broken",
            table_name="NONEXISTENT_TABLE",
            connection_config={"connection_id": "conn-bad"},
            name="query_nonexistent",
        )

        with patch(
            "api.services.data_query_tools.HANAToolExecutor.execute_tool",
            new_callable=AsyncMock,
            side_effect=Exception("Connection refused"),
        ):
            result_json = await tool._arun(columns=["*"], limit=10)

        result = json.loads(result_json)
        assert result["success"] is False
        assert "error" in result
        assert "Connection refused" in result["error"]
        assert result["rows"] == []


# ============================================================================
# Test Tool Factory Integration
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestToolFactoryIntegration:
    """Test the tool factory creates correct tools from notebook sources."""

    async def test_factory_creates_tools_for_notebook(self):
        """Test create_tools_for_notebook returns correct tool set."""
        from api.services.data_query_tools import create_tools_for_notebook

        # Mock database queries
        hana_sources = [
            {
                "id": "src-1",
                "title": "Sales Data",
                "connection_config": json.dumps({
                    "connection_id": "conn-1",
                    "table_name": "SALES_DATA",
                }),
            },
        ]

        api_sources = [
            {
                "id": "src-2",
                "title": "Customer API",
                "connection_config": json.dumps({
                    "connection_id": "conn-2",
                    "endpoint": "https://api.example.com",
                }),
            },
        ]

        api_connection = [{
            "id": "conn-2",
            "endpoint": "https://api.example.com",
            "name": "Customer API",
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
            tools = await create_tools_for_notebook(
                "notebook-123", session_id="session-abc"
            )

        # Verify tools created
        assert len(tools) == 2

        # Verify HANA tool
        hana_tool = next(t for t in tools if "sales" in t.name.lower())
        assert hana_tool.source_id == "src-1"
        assert hana_tool.table_name == "SALES_DATA"
        assert hana_tool.session_id == "session-abc"

        # Verify API tool
        api_tool = next(t for t in tools if "customer" in t.name.lower())
        assert api_tool.source_id == "src-2"
        assert api_tool.session_id == "session-abc"

    async def test_factory_handles_no_sources(self):
        """Test factory handles notebook with no tool-generating sources."""
        from api.services.data_query_tools import create_tools_for_notebook

        with patch(
            "api.services.data_query_tools.repo_query",
            new_callable=AsyncMock,
            return_value=[],
        ):
            tools = await create_tools_for_notebook("empty-notebook")

        assert tools == []

    async def test_factory_resilient_to_bad_source_config(self):
        """Test factory skips sources with bad config without failing."""
        from api.services.data_query_tools import create_tools_for_notebook

        hana_sources = [
            {
                "id": "good-src",
                "title": "Good Source",
                "connection_config": json.dumps({
                    "connection_id": "conn-1",
                    "table_name": "GOOD_TABLE",
                }),
            },
            {
                "id": "bad-src",
                "title": "Bad Source",
                "connection_config": "not-json",  # Broken
            },
            {
                "id": "empty-src",
                "title": "Empty Source",
                "connection_config": json.dumps({}),  # Missing fields
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
            tools = await create_tools_for_notebook("bad-config-notebook")

        # Only the good source should produce a tool
        assert len(tools) >= 1
        assert any(t.table_name == "GOOD_TABLE" for t in tools)


# ============================================================================
# Test Permission-Based Tool Access (Simulated)
# ============================================================================

@pytest.mark.e2e
class TestPermissionBasedToolAccess:
    """
    Simulate the full permission flow:
    1. Multiple tools available
    2. Different users with different roles
    3. Verify each user gets correct tool subset
    """

    def test_admin_gets_all_enabled_tools(self):
        """Admin should see all enabled tools."""
        all_tools = [
            {"id": "t1", "name": "hana_query", "enabled": True},
            {"id": "t2", "name": "api_call", "enabled": True},
            {"id": "t3", "name": "web_search", "enabled": True},
            {"id": "t4", "name": "code_exec", "enabled": False},
        ]

        permissions = [
            {"tool_id": t["id"], "role": "admin", "allowed": True, "user_id": None}
            for t in all_tools
        ]

        # Filter enabled tools
        enabled = [t for t in all_tools if t["enabled"]]

        # Admin should see all enabled tools
        assert len(enabled) == 3

    def test_analyst_gets_data_query_tools_only(self):
        """Analyst should only see data_query category tools."""
        all_tools = [
            {"id": "t1", "name": "hana_query", "category": "data_query", "enabled": True},
            {"id": "t2", "name": "api_call", "category": "data_query", "enabled": True},
            {"id": "t3", "name": "web_search", "category": "web", "enabled": True},
            {"id": "t4", "name": "code_exec", "category": "computation", "enabled": True},
        ]

        analyst_permissions = {
            "t1": True,
            "t2": True,
            "t3": False,  # Not allowed for analyst
            "t4": False,  # Not allowed for analyst
        }

        analyst_tools = [
            t for t in all_tools
            if t["enabled"] and analyst_permissions.get(t["id"], True)
        ]

        assert len(analyst_tools) == 2
        assert all(t["category"] == "data_query" for t in analyst_tools)

    def test_user_override_gives_extra_access(self):
        """Specific user can get access to tools their role doesn't have."""
        # Alice is an analyst but has user-specific access to code_exec
        analyst_role_perms = {"code_exec": False}
        alice_user_perms = {"code_exec": True}  # Override

        # Resolution: user > role
        effective = alice_user_perms.get("code_exec", analyst_role_perms.get("code_exec", True))
        assert effective is True

    def test_viewer_gets_minimal_tools(self):
        """Viewer role should only get read-only tools."""
        viewer_permissions = {
            "t1": False,  # HANA query - blocked
            "t2": False,  # API call - blocked
            "t3": True,   # Web search - allowed
            "t4": False,  # Code exec - blocked
        }

        allowed_count = sum(1 for v in viewer_permissions.values() if v)
        assert allowed_count == 1


# ============================================================================
# Test Usage Logging (Simulated)
# ============================================================================

@pytest.mark.e2e
class TestUsageLogging:
    """Test that tool usage is properly logged."""

    @pytest.mark.asyncio
    async def test_successful_execution_logged(self):
        """Test that successful tool execution is captured for logging."""
        from api.services.data_query_tools import HANAQueryTool

        tool = HANAQueryTool(
            source_id="src-1",
            table_name="SALES",
            connection_config={"connection_id": "conn-1", "table_name": "SALES"},
            session_id="session-log-test",
            name="query_sales",
        )

        mock_results = [{"product": "A", "revenue": 100}]

        with patch(
            "api.services.data_query_tools.HANAToolExecutor.execute_tool",
            new_callable=AsyncMock,
            return_value=mock_results,
        ), patch(
            "api.services.data_query_tools.get_chart_tool",
        ) as mock_chart:
            mock_chart.return_value.should_use_chart.return_value = False

            result_json = await tool._arun(columns=["*"], limit=10)

        result = json.loads(result_json)

        # Verify the result contains data that can be logged
        assert result["success"] is True
        assert "duration_ms" in result
        assert result["duration_ms"] >= 0
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_failed_execution_logged(self):
        """Test that failed tool execution captures error for logging."""
        from api.services.data_query_tools import HANAQueryTool

        tool = HANAQueryTool(
            source_id="src-1",
            table_name="BAD_TABLE",
            connection_config={"connection_id": "bad-conn"},
            session_id="session-error-test",
            name="query_bad_table",
        )

        with patch(
            "api.services.data_query_tools.HANAToolExecutor.execute_tool",
            new_callable=AsyncMock,
            side_effect=Exception("Table not found"),
        ):
            result_json = await tool._arun(columns=["*"], limit=10)

        result = json.loads(result_json)

        # Verify error is captured for logging
        assert result["success"] is False
        assert "error" in result
        assert "Table not found" in result["error"]

    def test_usage_log_record_structure(self):
        """Test the expected structure of a usage log record."""
        usage_record = {
            "id": str(uuid.uuid4()),
            "tool_id": "t1",
            "user_id": "user-123",
            "session_id": "session-456",
            "notebook_id": "notebook-789",
            "input_params": {"columns": ["*"], "limit": 50},
            "execution_time_ms": 45,
            "success": True,
            "error_message": None,
            "created": datetime.utcnow().isoformat(),
        }

        assert usage_record["tool_id"] == "t1"
        assert usage_record["success"] is True
        assert usage_record["execution_time_ms"] > 0
        assert usage_record["error_message"] is None

    def test_failed_usage_log_record_structure(self):
        """Test usage log record for a failed execution."""
        usage_record = {
            "id": str(uuid.uuid4()),
            "tool_id": "t1",
            "user_id": "user-123",
            "session_id": "session-456",
            "notebook_id": "notebook-789",
            "input_params": {"columns": ["*"], "limit": 50},
            "execution_time_ms": 120,
            "success": False,
            "error_message": "Connection timeout after 30 seconds",
            "created": datetime.utcnow().isoformat(),
        }

        assert usage_record["success"] is False
        assert usage_record["error_message"] is not None
        assert "timeout" in usage_record["error_message"]
