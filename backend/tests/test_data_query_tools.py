"""
Unit Tests for Data Query Tools

Tests LangChain tool wrappers for HANA and API sources.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from api.services.data_query_tools import (
    HANAQueryTool,
    APICallTool,
    create_tools_for_notebook,
    _sanitize_tool_name
)


# ============================================================================
# Tool Name Sanitization Tests
# ============================================================================

def test_sanitize_tool_name():
    """Test tool name sanitization"""
    assert _sanitize_tool_name("Sales Data") == "sales_data"
    assert _sanitize_tool_name("My-API-2024") == "my_api_2024"
    assert _sanitize_tool_name("  spaced  ") == "spaced"
    assert _sanitize_tool_name("special!@#$%chars") == "special_chars"
    assert _sanitize_tool_name("___multiple___underscores___") == "multiple_underscores"
    assert _sanitize_tool_name("") == "tool"


# ============================================================================
# HANAQueryTool Tests
# ============================================================================

@pytest.mark.asyncio
async def test_hana_query_tool_success():
    """Test successful HANA query execution"""
    # Mock HANAToolExecutor
    mock_results = [
        {"id": 1, "name": "Product A", "price": 100},
        {"id": 2, "name": "Product B", "price": 200}
    ]

    with patch("api.services.data_query_tools.HANAToolExecutor") as mock_executor:
        mock_executor.execute_tool = AsyncMock(return_value=mock_results)

        # Create tool
        tool = HANAQueryTool(
            source_id="test-source-id",
            table_name="PRODUCTS",
            connection_config={"connection_id": "test-conn"}
        )

        # Execute tool
        result = await tool._arun(
            columns=["id", "name", "price"],
            where_clause="price > 50",
            limit=10
        )

        # Parse result
        result_data = json.loads(result)

        # Assertions
        assert result_data["success"] is True
        assert result_data["count"] == 2
        assert len(result_data["rows"]) == 2
        assert result_data["rows"][0]["name"] == "Product A"
        assert "duration_ms" in result_data


@pytest.mark.asyncio
async def test_hana_query_tool_error():
    """Test HANA query tool error handling"""
    with patch("api.services.data_query_tools.HANAToolExecutor") as mock_executor:
        mock_executor.execute_tool = AsyncMock(side_effect=Exception("Connection failed"))

        tool = HANAQueryTool(
            source_id="test-source-id",
            table_name="PRODUCTS",
            connection_config={"connection_id": "test-conn"}
        )

        result = await tool._arun(columns=["*"], limit=10)
        result_data = json.loads(result)

        assert result_data["success"] is False
        assert "Connection failed" in result_data["error"]
        assert result_data["count"] == 0


@pytest.mark.asyncio
async def test_hana_query_tool_with_langfuse():
    """Test HANA tool with LangFuse logging"""
    mock_results = [{"id": 1}]

    with patch("api.services.data_query_tools.HANAToolExecutor") as mock_executor:
        mock_executor.execute_tool = AsyncMock(return_value=mock_results)

        with patch("api.services.data_query_tools.langfuse_observer") as mock_observer:
            mock_observer.log_tool_execution = MagicMock()

            tool = HANAQueryTool(
                source_id="test-source",
                table_name="TEST_TABLE",
                connection_config={},
                session_id="test-session-123"
            )

            await tool._arun(columns=["*"], limit=5)

            # Verify LangFuse was called
            mock_observer.log_tool_execution.assert_called_once()


def test_hana_query_tool_sync_not_supported():
    """Test that sync execution raises NotImplementedError"""
    tool = HANAQueryTool(
        source_id="test",
        table_name="TEST",
        connection_config={}
    )

    with pytest.raises(NotImplementedError):
        tool._run(columns=["*"])


# ============================================================================
# APICallTool Tests
# ============================================================================

@pytest.mark.asyncio
async def test_api_call_tool_success():
    """Test successful API call execution"""
    mock_response = {
        "success": True,
        "data": [{"id": 1, "title": "Item 1"}, {"id": 2, "title": "Item 2"}],
        "record_count": 2
    }

    with patch("api.services.data_query_tools.execute_api_call_with_params") as mock_exec:
        mock_exec.return_value = mock_response

        tool = APICallTool(
            source_id="api-source-id",
            endpoint="https://api.example.com/data",
            connection_config={"connection_id": "test-api-conn"},
            source_name="Example API"
        )

        result = await tool._arun(
            params={"limit": 10, "status": "active"},
            filters={"category": "electronics"}
        )

        result_data = json.loads(result)

        assert result_data["success"] is True
        assert result_data["count"] == 2
        assert len(result_data["data"]) == 2
        assert "duration_ms" in result_data


@pytest.mark.asyncio
async def test_api_call_tool_error():
    """Test API call tool error handling"""
    mock_response = {
        "success": False,
        "error": "API rate limit exceeded",
        "data": None,
        "record_count": 0
    }

    with patch("api.services.data_query_tools.execute_api_call_with_params") as mock_exec:
        mock_exec.return_value = mock_response

        tool = APICallTool(
            source_id="api-source",
            endpoint="https://api.example.com/data",
            connection_config={},
            source_name="Test API"
        )

        result = await tool._arun(params={})
        result_data = json.loads(result)

        assert result_data["success"] is False
        assert "rate limit" in result_data["error"]


@pytest.mark.asyncio
async def test_api_call_tool_exception():
    """Test API call tool exception handling"""
    with patch("api.services.data_query_tools.execute_api_call_with_params") as mock_exec:
        mock_exec.side_effect = Exception("Network error")

        tool = APICallTool(
            source_id="api-source",
            endpoint="https://api.example.com/data",
            connection_config={},
            source_name="Test API"
        )

        result = await tool._arun(params={})
        result_data = json.loads(result)

        assert result_data["success"] is False
        assert "Network error" in result_data["error"]


def test_api_call_tool_sync_not_supported():
    """Test that sync execution raises NotImplementedError"""
    tool = APICallTool(
        source_id="test",
        endpoint="https://api.test.com",
        connection_config={},
        source_name="Test"
    )

    with pytest.raises(NotImplementedError):
        tool._run(params={})


# ============================================================================
# Tool Factory Tests
# ============================================================================

@pytest.mark.asyncio
async def test_create_tools_for_notebook_empty():
    """Test tool creation for notebook with no sources"""
    with patch("api.services.data_query_tools.repo_query") as mock_query:
        # No sources: explicit HANA, explicit API, connection-level HANA, connection-level API
        mock_query.side_effect = [[], [], [], []]

        tools = await create_tools_for_notebook("test-notebook-id")

        assert len(tools) == 0


@pytest.mark.asyncio
async def test_create_tools_for_notebook_hana_only():
    """Test tool creation with HANA sources only"""
    mock_hana_sources = [
        {
            "id": "hana-source-1",
            "title": "Sales Data",
            "connection_config": json.dumps({
                "table_name": "SALES",
                "connection_id": "conn-1"
            })
        },
        {
            "id": "hana-source-2",
            "title": "Products",
            "connection_config": json.dumps({
                "table_name": "PRODUCTS",
                "connection_id": "conn-2"
            })
        }
    ]

    with patch("api.services.data_query_tools.repo_query") as mock_query:
        mock_query.side_effect = [
            mock_hana_sources,  # Explicit HANA sources
            [],  # No explicit API sources
            [],  # No connection-level HANA
            []   # No connection-level API
        ]

        tools = await create_tools_for_notebook("notebook-id", session_id="session-123")

        assert len(tools) == 2
        assert all(isinstance(tool, HANAQueryTool) for tool in tools)
        assert tools[0].name == "query_sales"
        assert tools[1].name == "query_products"
        assert tools[0].session_id == "session-123"


@pytest.mark.asyncio
async def test_create_tools_for_notebook_api_only():
    """Test tool creation with API sources only"""
    mock_api_sources = [
        {
            "id": "api-source-1",
            "title": "Weather API",
            "connection_config": json.dumps({
                "connection_id": "api-conn-1"
            })
        }
    ]

    mock_api_connection = {
        "id": "api-conn-1",
        "endpoint": "https://api.weather.com/v1/current",
        "method": "GET"
    }

    with patch("api.services.data_query_tools.repo_query") as mock_query:
        mock_query.side_effect = [
            [],  # No explicit HANA sources
            mock_api_sources,  # Explicit API sources
            [mock_api_connection],  # API connection details
            [],  # No connection-level HANA
            []   # No connection-level API
        ]

        tools = await create_tools_for_notebook("notebook-id")

        assert len(tools) == 1
        assert isinstance(tools[0], APICallTool)
        assert tools[0].name == "call_weather_api"
        assert tools[0].endpoint == "https://api.weather.com/v1/current"


@pytest.mark.asyncio
async def test_create_tools_for_notebook_mixed():
    """Test tool creation with both HANA and API sources"""
    mock_hana_sources = [
        {
            "id": "hana-1",
            "title": "Customers",
            "connection_config": json.dumps({
                "table_name": "CUSTOMERS",
                "connection_id": "hana-conn"
            })
        }
    ]

    mock_api_sources = [
        {
            "id": "api-1",
            "title": "CRM API",
            "connection_config": json.dumps({
                "connection_id": "api-conn"
            })
        }
    ]

    mock_api_connection = {
        "id": "api-conn",
        "endpoint": "https://crm.example.com/api/v1/leads"
    }

    with patch("api.services.data_query_tools.repo_query") as mock_query:
        mock_query.side_effect = [
            mock_hana_sources,      # Explicit HANA
            mock_api_sources,       # Explicit API
            [mock_api_connection],  # API connection details
            [],  # No connection-level HANA
            []   # No connection-level API
        ]

        tools = await create_tools_for_notebook("notebook-id")

        assert len(tools) == 2
        assert isinstance(tools[0], HANAQueryTool)
        assert isinstance(tools[1], APICallTool)


@pytest.mark.asyncio
async def test_create_tools_skips_invalid_sources():
    """Test that tool factory skips sources with errors"""
    mock_hana_sources = [
        {
            "id": "good-source",
            "title": "Valid Table",
            "connection_config": json.dumps({
                "table_name": "VALID",
                "connection_id": "conn-1"
            })
        },
        {
            "id": "bad-source",
            "title": "Invalid",
            "connection_config": "invalid-json"  # Will fail parsing
        }
    ]

    with patch("api.services.data_query_tools.repo_query") as mock_query:
        mock_query.side_effect = [
            mock_hana_sources,  # Explicit HANA
            [],  # No explicit API sources
            [],  # No connection-level HANA
            []   # No connection-level API
        ]

        tools = await create_tools_for_notebook("notebook-id")

        # Should only get 1 tool (bad source skipped)
        assert len(tools) == 1
        assert tools[0].source_id == "good-source"


@pytest.mark.asyncio
async def test_create_tools_skips_api_without_connection():
    """Test that API sources without valid connections are skipped"""
    mock_api_sources = [
        {
            "id": "api-no-conn",
            "title": "Bad API",
            "connection_config": json.dumps({})  # No connection_id
        }
    ]

    with patch("api.services.data_query_tools.repo_query") as mock_query:
        mock_query.side_effect = [
            [],  # No HANA
            mock_api_sources,
            [],  # No HANA connection-level tools
            []  # No API connection-level tools
        ]

        tools = await create_tools_for_notebook("notebook-id")

        assert len(tools) == 0  # API source skipped


# ============================================================================
# Connection-Level Tool Generation Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_hana_connection_level_tools():
    """Test generation of tools from auto-discovered HANA tables"""
    from api.services.data_query_tools import _get_hana_connection_level_tools

    # Mock HANA connections used by notebook
    mock_connections = [
        {
            "id": "hana-conn-1",
            "connection_name": "Test HANA",
            "host": "test.hana.com",
            "port": 443,
            "database_name": "TEST_DB",
            "schema_name": "TEST_SCHEMA"
        }
    ]

    # Mock discovered tables for connection
    mock_discovered_tables = [
        {
            "id": "table-1",
            "schema_name": "TEST_SCHEMA",
            "table_name": "CUSTOMERS",
            "table_type": "TABLE",
            "column_metadata": json.dumps([
                {"name": "ID", "type": "INTEGER"},
                {"name": "NAME", "type": "NVARCHAR"}
            ]),
            "row_count": 1000
        },
        {
            "id": "table-2",
            "schema_name": "TEST_SCHEMA",
            "table_name": "ORDERS",
            "table_type": "TABLE",
            "column_metadata": json.dumps([
                {"name": "ORDER_ID", "type": "INTEGER"}
            ]),
            "row_count": 5000
        }
    ]

    with patch("api.services.data_query_tools.repo_query") as mock_query:
        mock_query.side_effect = [
            mock_connections,  # Connections query
            mock_discovered_tables  # Tables for first connection
        ]

        tools = await _get_hana_connection_level_tools("notebook-123")

        # Should create 2 tools (one per discovered table)
        assert len(tools) == 2

        # Check first tool
        assert tools[0].name == "query_customers"
        assert tools[0].source_id == "hana-conn-1"  # Uses connection_id as marker
        assert tools[0].table_name == "CUSTOMERS"

        # Check second tool
        assert tools[1].name == "query_orders"
        assert tools[1].table_name == "ORDERS"


@pytest.mark.asyncio
async def test_get_hana_connection_level_tools_no_connections():
    """Test when notebook has no HANA connections"""
    from api.services.data_query_tools import _get_hana_connection_level_tools

    with patch("api.services.data_query_tools.repo_query") as mock_query:
        mock_query.return_value = []  # No connections

        tools = await _get_hana_connection_level_tools("notebook-123")

        assert len(tools) == 0


@pytest.mark.asyncio
async def test_get_hana_connection_level_tools_no_discovered_tables():
    """Test when connection has no discovered tables"""
    from api.services.data_query_tools import _get_hana_connection_level_tools

    mock_connections = [
        {
            "id": "hana-conn-1",
            "connection_name": "Test HANA",
            "host": "test.hana.com",
            "port": 443,
            "database_name": "TEST_DB",
            "schema_name": "TEST_SCHEMA"
        }
    ]

    with patch("api.services.data_query_tools.repo_query") as mock_query:
        mock_query.side_effect = [
            mock_connections,
            []  # No discovered tables
        ]

        tools = await _get_hana_connection_level_tools("notebook-123")

        assert len(tools) == 0


@pytest.mark.asyncio
async def test_get_api_connection_level_tools():
    """Test generation of tools from auto-discovered API endpoints"""
    from api.services.data_query_tools import _get_api_connection_level_tools

    # Mock API connections used by notebook
    mock_connections = [
        {
            "id": "api-conn-1",
            "name": "Test API",
            "base_url": "https://api.example.com",
            "endpoint": "/v1/data"
        }
    ]

    # Mock discovered endpoints for connection
    mock_discovered_endpoints = [
        {
            "id": "endpoint-1",
            "endpoint_path": "/users",
            "method": "GET",
            "description": "List users",
            "parameters": json.dumps([]),
            "response_schema": json.dumps({"type": "array"})
        },
        {
            "id": "endpoint-2",
            "endpoint_path": "/products",
            "method": "GET",
            "description": "List products",
            "parameters": json.dumps([]),
            "response_schema": json.dumps({"type": "array"})
        }
    ]

    with patch("api.services.data_query_tools.repo_query") as mock_query:
        mock_query.side_effect = [
            mock_connections,  # Connections query
            mock_discovered_endpoints  # Endpoints for first connection
        ]

        tools = await _get_api_connection_level_tools("notebook-123")

        # Should create 2 tools (one per discovered endpoint)
        assert len(tools) == 2

        # Check first tool
        assert tools[0].name == "call_list_users"
        assert tools[0].source_id == "api-conn-1"  # Uses connection_id as marker
        assert tools[0].endpoint == "/users"

        # Check second tool
        assert tools[1].name == "call_list_products"
        assert tools[1].endpoint == "/products"


@pytest.mark.asyncio
async def test_get_api_connection_level_tools_no_endpoints():
    """Test when connection has no discovered endpoints"""
    from api.services.data_query_tools import _get_api_connection_level_tools

    mock_connections = [
        {
            "id": "api-conn-1",
            "name": "Test API",
            "base_url": "https://api.example.com",
            "endpoint": "/v1/data"
        }
    ]

    with patch("api.services.data_query_tools.repo_query") as mock_query:
        mock_query.side_effect = [
            mock_connections,
            []  # No discovered endpoints
        ]

        tools = await _get_api_connection_level_tools("notebook-123")

        # Should skip connection when no endpoints discovered
        assert len(tools) == 0


@pytest.mark.asyncio
async def test_deduplicate_tools_removes_duplicates():
    """Test tool deduplication by name"""
    from api.services.data_query_tools import _deduplicate_tools

    # Create mock tools with duplicate names
    tool1 = HANAQueryTool(
        source_id="explicit-source-1",
        table_name="CUSTOMERS",
        connection_config={},
        name="query_customers"
    )

    tool2 = HANAQueryTool(
        source_id="connection-id",  # Auto-discovered (connection_id as source_id)
        table_name="CUSTOMERS",
        connection_config={},
        name="query_customers"  # Same name as tool1
    )

    tool3 = HANAQueryTool(
        source_id="explicit-source-2",
        table_name="ORDERS",
        connection_config={},
        name="query_orders"
    )

    tools = [tool1, tool2, tool3]

    deduplicated = _deduplicate_tools(tools)

    # Should keep only 2 tools (duplicate removed)
    assert len(deduplicated) == 2

    # Should keep first occurrence (tool1) and skip duplicate (tool2)
    tool_names = [t.name for t in deduplicated]
    assert "query_customers" in tool_names
    assert "query_orders" in tool_names

    # Verify we kept the first one (explicit source)
    customers_tool = next(t for t in deduplicated if t.name == "query_customers")
    assert customers_tool.source_id == "explicit-source-1"


@pytest.mark.asyncio
async def test_deduplicate_tools_no_duplicates():
    """Test deduplication when no duplicates exist"""
    from api.services.data_query_tools import _deduplicate_tools

    tool1 = HANAQueryTool(
        source_id="source-1",
        table_name="CUSTOMERS",
        connection_config={},
        name="query_customers"
    )

    tool2 = HANAQueryTool(
        source_id="source-2",
        table_name="ORDERS",
        connection_config={},
        name="query_orders"
    )

    tools = [tool1, tool2]

    deduplicated = _deduplicate_tools(tools)

    # Should keep all tools
    assert len(deduplicated) == 2


@pytest.mark.asyncio
async def test_create_tools_for_notebook_with_auto_discovery():
    """Test tool creation includes both explicit and auto-discovered sources"""

    # Mock explicit HANA source
    mock_hana_sources = [
        {
            "id": "explicit-hana-1",
            "title": "Explicit Table",
            "connection_config": json.dumps({
                "table_name": "EXPLICIT_TABLE",
                "connection_id": "hana-conn-1"
            })
        }
    ]

    # Mock explicit API source
    mock_api_sources = [
        {
            "id": "explicit-api-1",
            "title": "Explicit API",
            "connection_config": json.dumps({
                "connection_id": "api-conn-1"
            })
        }
    ]

    mock_api_connection = {
        "id": "api-conn-1",
        "endpoint": "/v1/explicit"
    }

    # Mock HANA connections for auto-discovery
    mock_hana_connections = [
        {
            "id": "hana-conn-1",
            "connection_name": "Test HANA",
            "host": "test.hana.com",
            "port": 443,
            "database_name": "TEST_DB",
            "schema_name": "TEST_SCHEMA"
        }
    ]

    # Mock auto-discovered HANA tables
    mock_discovered_tables = [
        {
            "id": "discovered-1",
            "schema_name": "TEST_SCHEMA",
            "table_name": "AUTO_TABLE",
            "table_type": "TABLE",
            "column_metadata": json.dumps([]),
            "row_count": 100
        }
    ]

    # Mock API connections for auto-discovery
    mock_api_connections = [
        {
            "id": "api-conn-1",
            "name": "Test API",
            "base_url": "https://api.example.com",
            "endpoint": "/v1/data"
        }
    ]

    # Mock auto-discovered API endpoints
    mock_discovered_endpoints = [
        {
            "id": "endpoint-1",
            "endpoint_path": "/auto",
            "method": "GET",
            "description": "Auto endpoint",
            "parameters": json.dumps([]),
            "response_schema": None
        }
    ]

    with patch("api.services.data_query_tools.repo_query") as mock_query:
        mock_query.side_effect = [
            mock_hana_sources,  # Explicit HANA sources
            mock_api_sources,  # Explicit API sources
            [mock_api_connection],  # API connection for explicit source
            mock_hana_connections,  # HANA connections for auto-discovery
            mock_discovered_tables,  # Auto-discovered tables
            mock_api_connections,  # API connections for auto-discovery
            mock_discovered_endpoints  # Auto-discovered endpoints
        ]

        tools = await create_tools_for_notebook("notebook-123")

        # Should have:
        # - 1 explicit HANA tool
        # - 1 explicit API tool
        # - 1 auto-discovered HANA tool
        # - 1 auto-discovered API tool
        # Total: 4 tools
        assert len(tools) == 4

        tool_names = [t.name for t in tools]
        assert "query_explicit_table" in tool_names
        assert "call_explicit_api" in tool_names
        assert "query_auto_table" in tool_names
        assert "call_auto_endpoint" in tool_names


@pytest.mark.asyncio
async def test_create_tools_for_notebook_deduplicates():
    """Test that duplicate tools are removed, preferring explicit sources"""

    # Mock explicit HANA source for CUSTOMERS table
    mock_hana_sources = [
        {
            "id": "explicit-source-1",
            "title": "Customers",
            "connection_config": json.dumps({
                "table_name": "CUSTOMERS",
                "connection_id": "hana-conn-1"
            })
        }
    ]

    # Mock HANA connection
    mock_hana_connections = [
        {
            "id": "hana-conn-1",
            "connection_name": "Test HANA",
            "host": "test.hana.com",
            "port": 443,
            "database_name": "TEST_DB",
            "schema_name": "TEST_SCHEMA"
        }
    ]

    # Mock auto-discovered table (same table as explicit source)
    mock_discovered_tables = [
        {
            "id": "discovered-1",
            "schema_name": "TEST_SCHEMA",
            "table_name": "CUSTOMERS",  # Same as explicit
            "table_type": "TABLE",
            "column_metadata": json.dumps([]),
            "row_count": 1000
        }
    ]

    with patch("api.services.data_query_tools.repo_query") as mock_query:
        mock_query.side_effect = [
            mock_hana_sources,  # Explicit sources
            [],  # No explicit API sources
            mock_hana_connections,  # Connections for auto-discovery
            mock_discovered_tables,  # Auto-discovered tables (duplicate)
            [],  # No API connections
        ]

        tools = await create_tools_for_notebook("notebook-123")

        # Should only have 1 tool (duplicate removed)
        assert len(tools) == 1

        # Should keep the explicit source version
        assert tools[0].source_id == "explicit-source-1"
        assert tools[0].name == "query_customers"
