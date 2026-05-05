"""
Unit Tests for HANA Schema Discovery Service

Tests the discovery of tables and columns from HANA databases.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime
import sys

# Mock the circular import before importing the module
sys.modules['api.routers.hana_connections'] = MagicMock()

from api.services.hana_schema_discovery import (
    discover_tables,
    store_discovered_tables,
    refresh_table_metadata,
    get_tables_for_connection,
    get_table_details,
    EXCLUDED_SCHEMAS,
    MAX_TABLES
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_hana_connection():
    """Mock HANA connection configuration"""
    return {
        "id": "conn-123",
        "connection_name": "Test HANA",
        "host": "test.hanacloud.ondemand.com",
        "port": 443,
        "user": "TEST_USER",
        "database_name": "TEST_DB",
        "schema_name": "TEST_SCHEMA",
        "password_encrypted": "encrypted_password_here",
        "encrypt": True
    }


@pytest.fixture
def mock_table_rows():
    """Mock table rows returned from HANA system tables"""
    return [
        ("SCHEMA_A", "CUSTOMERS", "TABLE", 1000),
        ("SCHEMA_A", "ORDERS", "TABLE", 5000),
        ("SCHEMA_B", "PRODUCTS", "VIEW", 200)
    ]


@pytest.fixture
def mock_column_rows():
    """Mock column rows for a specific table"""
    return {
        "CUSTOMERS": [
            ("ID", "INTEGER", 10, 0, "FALSE", 1),
            ("NAME", "NVARCHAR", 100, 0, "TRUE", 2),
            ("EMAIL", "NVARCHAR", 255, 0, "TRUE", 3),
            ("CREATED_AT", "TIMESTAMP", 0, 0, "FALSE", 4)
        ],
        "ORDERS": [
            ("ORDER_ID", "INTEGER", 10, 0, "FALSE", 1),
            ("CUSTOMER_ID", "INTEGER", 10, 0, "FALSE", 2),
            ("AMOUNT", "DECIMAL", 15, 2, "FALSE", 3),
            ("STATUS", "NVARCHAR", 50, 0, "TRUE", 4)
        ],
        "PRODUCTS": [
            ("PRODUCT_ID", "INTEGER", 10, 0, "FALSE", 1),
            ("PRODUCT_NAME", "NVARCHAR", 200, 0, "FALSE", 2),
            ("PRICE", "DECIMAL", 10, 2, "FALSE", 3)
        ]
    }


# ============================================================================
# discover_tables() Tests
# ============================================================================

@pytest.mark.asyncio
async def test_discover_tables_success(mock_hana_connection, mock_table_rows, mock_column_rows):
    """Test successful table discovery from HANA"""

    # Mock get_connection_by_id
    async def mock_get_conn(conn_id):
        return mock_hana_connection

    with patch("api.services.hana_schema_discovery.get_connection_by_id", new=mock_get_conn):
        # Mock decrypt_password
                with patch("api.services.hana_schema_discovery.decrypt_password") as mock_decrypt:
                    mock_decrypt.return_value = "decrypted_password"

                    # Mock HANA connection
                    with patch("api.services.hana_schema_discovery.dbapi.connect") as mock_connect:
                        # Create mock cursor
                        mock_cursor = MagicMock()

                        # Mock execute calls
                        def execute_side_effect(sql, params=None):
                            if "FROM SYS.M_TABLES" in sql:
                                # Return table rows
                                mock_cursor.fetchall.return_value = mock_table_rows
                            elif "FROM SYS.TABLE_COLUMNS" in sql:
                                # Return column rows based on table name
                                table_name = params[1] if params else None
                                mock_cursor.fetchall.return_value = mock_column_rows.get(table_name, [])

                        mock_cursor.execute.side_effect = execute_side_effect
                        mock_cursor.fetchall.return_value = mock_table_rows

                        # Mock connection
                        mock_db_conn = MagicMock()
                        mock_db_conn.cursor.return_value = mock_cursor
                        mock_connect.return_value = mock_db_conn

                        # Execute discovery
                        result = await discover_tables("conn-123")

                        # Assertions
                        assert len(result) == 3

                        # Check first table
                        assert result[0]["schema_name"] == "SCHEMA_A"
                        assert result[0]["table_name"] == "CUSTOMERS"
                        assert result[0]["table_type"] == "TABLE"
                        assert result[0]["row_count"] == 1000
                        assert len(result[0]["columns"]) == 4

                        # Check column details
                        first_col = result[0]["columns"][0]
                        assert first_col["name"] == "ID"
                        assert first_col["type"] == "INTEGER"
                        assert first_col["nullable"] is False
                        assert first_col["position"] == 1

                        # Verify connection was made correctly
                        mock_connect.assert_called_once()
                        conn_params = mock_connect.call_args[1]
                        assert conn_params["address"] == "test.hanacloud.ondemand.com"
                        assert conn_params["port"] == 443
                        assert conn_params["user"] == "TEST_USER"
                        assert conn_params["password"] == "decrypted_password"
                        assert conn_params["encrypt"] is True


@pytest.mark.asyncio
async def test_discover_tables_connection_not_found():
    """Test discovery when connection doesn't exist"""

    async def mock_get_conn_async(conn_id):
            return None
    with patch("api.services.hana_schema_discovery.get_connection_by_id", new=mock_get_conn_async):

        with pytest.raises(ValueError, match="Connection conn-999 not found"):
            await discover_tables("conn-999")


@pytest.mark.asyncio
async def test_discover_tables_connection_error(mock_hana_connection):
    """Test discovery when HANA connection fails"""

    async def mock_get_conn_async(conn_id):
            return mock_hana_connection
    with patch("api.services.hana_schema_discovery.get_connection_by_id", new=mock_get_conn_async):

        with patch("api.services.hana_schema_discovery.decrypt_password") as mock_decrypt:
            mock_decrypt.return_value = "password"

            with patch("api.services.hana_schema_discovery.dbapi.connect") as mock_connect:
                mock_connect.side_effect = Exception("Authentication failed")

                with pytest.raises(Exception, match="Failed to discover tables"):
                    await discover_tables("conn-123")


@pytest.mark.asyncio
async def test_discover_tables_query_error(mock_hana_connection):
    """Test discovery when query execution fails"""

    async def mock_get_conn_async(conn_id):
            return mock_hana_connection
    with patch("api.services.hana_schema_discovery.get_connection_by_id", new=mock_get_conn_async):

        with patch("api.services.hana_schema_discovery.decrypt_password") as mock_decrypt:
            mock_decrypt.return_value = "password"

            with patch("api.services.hana_schema_discovery.dbapi.connect") as mock_connect:
                mock_cursor = MagicMock()
                mock_cursor.execute.side_effect = Exception("SQL execution error")

                mock_db_conn = MagicMock()
                mock_db_conn.cursor.return_value = mock_cursor
                mock_connect.return_value = mock_db_conn

                with pytest.raises(Exception, match="Failed to discover tables"):
                    await discover_tables("conn-123")


@pytest.mark.asyncio
async def test_discover_tables_excludes_system_schemas(mock_hana_connection):
    """Test that system schemas are excluded from discovery"""

    # Include system schemas in mock data
    mock_tables = [
        ("USER_SCHEMA", "USER_TABLE", "TABLE", 100),
        ("SYS", "SYSTEM_TABLE", "TABLE", 1000),
        ("_SYS_BIC", "BIC_VIEW", "VIEW", 500)
    ]

    async def mock_get_conn_async(conn_id):
            return mock_hana_connection
    with patch("api.services.hana_schema_discovery.get_connection_by_id", new=mock_get_conn_async):

        with patch("api.services.hana_schema_discovery.decrypt_password"):
            with patch("api.services.hana_schema_discovery.dbapi.connect") as mock_connect:
                mock_cursor = MagicMock()

                # Capture SQL to verify exclusion
                executed_sql = None
                executed_params = None

                def capture_execute(sql, params=None):
                    nonlocal executed_sql, executed_params
                    executed_sql = sql
                    executed_params = params
                    if "FROM SYS.M_TABLES" in sql:
                        mock_cursor.fetchall.return_value = mock_tables
                    else:
                        mock_cursor.fetchall.return_value = []

                mock_cursor.execute.side_effect = capture_execute
                mock_db_conn = MagicMock()
                mock_db_conn.cursor.return_value = mock_cursor
                mock_connect.return_value = mock_db_conn

                await discover_tables("conn-123")

                # Verify that EXCLUDED_SCHEMAS were used in WHERE clause
                assert executed_params is not None
                assert all(schema in executed_params for schema in EXCLUDED_SCHEMAS)


@pytest.mark.asyncio
async def test_discover_tables_respects_max_limit(mock_hana_connection):
    """Test that discovery respects MAX_TABLES limit"""

    async def mock_get_conn_async(conn_id):
            return mock_hana_connection
    with patch("api.services.hana_schema_discovery.get_connection_by_id", new=mock_get_conn_async):

        with patch("api.services.hana_schema_discovery.decrypt_password"):
            with patch("api.services.hana_schema_discovery.dbapi.connect") as mock_connect:
                mock_cursor = MagicMock()

                # Capture SQL
                executed_sql = None

                def capture_sql(sql, params=None):
                    nonlocal executed_sql
                    executed_sql = sql
                    mock_cursor.fetchall.return_value = []

                mock_cursor.execute.side_effect = capture_sql
                mock_db_conn = MagicMock()
                mock_db_conn.cursor.return_value = mock_cursor
                mock_connect.return_value = mock_db_conn

                await discover_tables("conn-123")

                # Verify LIMIT clause
                assert f"LIMIT {MAX_TABLES}" in executed_sql


# ============================================================================
# store_discovered_tables() Tests
# ============================================================================

@pytest.mark.asyncio
async def test_store_discovered_tables_success():
    """Test successful storage of discovered tables"""

    tables = [
        {
            "schema_name": "SCHEMA_A",
            "table_name": "CUSTOMERS",
            "table_type": "TABLE",
            "columns": [
                {"name": "ID", "type": "INTEGER", "nullable": False, "position": 1}
            ],
            "row_count": 1000
        },
        {
            "schema_name": "SCHEMA_A",
            "table_name": "ORDERS",
            "table_type": "TABLE",
            "columns": [
                {"name": "ORDER_ID", "type": "INTEGER", "nullable": False, "position": 1}
            ],
            "row_count": 5000
        }
    ]

    with patch("api.services.hana_schema_discovery.repo_execute") as mock_execute:
        with patch("api.services.hana_schema_discovery.repo_create") as mock_create:
            mock_execute.return_value = None
            mock_create.return_value = None

            count = await store_discovered_tables("conn-123", tables)

            # Verify delete was called
            mock_execute.assert_called_once()
            delete_call = mock_execute.call_args
            assert "DELETE FROM hana_connection_tables" in delete_call[0][0]
            assert delete_call[0][1]["connection_id"] == "conn-123"

            # Verify creates were called
            assert mock_create.call_count == 2

            # Check first create call
            first_create = mock_create.call_args_list[0][0]
            assert first_create[0] == "hana_connection_tables"
            data = first_create[1]
            assert data["connection_id"] == "conn-123"
            assert data["schema_name"] == "SCHEMA_A"
            assert data["table_name"] == "CUSTOMERS"
            assert data["table_type"] == "TABLE"
            assert data["row_count"] == 1000

            # Verify column metadata was serialized to JSON
            column_metadata = json.loads(data["column_metadata"])
            assert len(column_metadata) == 1
            assert column_metadata[0]["name"] == "ID"

            # Verify count
            assert count == 2


@pytest.mark.asyncio
async def test_store_discovered_tables_empty():
    """Test storing empty list of tables"""

    with patch("api.services.hana_schema_discovery.repo_execute") as mock_execute:
        with patch("api.services.hana_schema_discovery.repo_create") as mock_create:
            count = await store_discovered_tables("conn-123", [])

            # Should still delete existing
            mock_execute.assert_called_once()

            # Should not create any
            mock_create.assert_not_called()

            assert count == 0


@pytest.mark.asyncio
async def test_store_discovered_tables_error():
    """Test storage error handling"""

    tables = [
        {
            "schema_name": "SCHEMA_A",
            "table_name": "CUSTOMERS",
            "table_type": "TABLE",
            "columns": [],
            "row_count": 1000
        }
    ]

    with patch("api.services.hana_schema_discovery.repo_execute"):
        with patch("api.services.hana_schema_discovery.repo_create") as mock_create:
            mock_create.side_effect = Exception("Database write error")

            with pytest.raises(Exception, match="Failed to store tables"):
                await store_discovered_tables("conn-123", tables)


# ============================================================================
# refresh_table_metadata() Tests
# ============================================================================

@pytest.mark.asyncio
async def test_refresh_table_metadata_success(mock_hana_connection):
    """Test successful end-to-end metadata refresh"""

    with patch("api.services.hana_schema_discovery.discover_tables") as mock_discover:
        mock_discover.return_value = [
            {
                "schema_name": "SCHEMA_A",
                "table_name": "CUSTOMERS",
                "table_type": "TABLE",
                "columns": [],
                "row_count": 1000
            }
        ]

        with patch("api.services.hana_schema_discovery.store_discovered_tables") as mock_store:
            mock_store.return_value = 1

            count = await refresh_table_metadata("conn-123")

            # Verify calls
            mock_discover.assert_called_once_with("conn-123")
            mock_store.assert_called_once()

            # Verify count
            assert count == 1


@pytest.mark.asyncio
async def test_refresh_table_metadata_connection_not_found():
    """Test refresh when connection doesn't exist"""

    with patch("api.services.hana_schema_discovery.discover_tables") as mock_discover:
        mock_discover.side_effect = ValueError("Connection not found")

        with pytest.raises(ValueError, match="Connection not found"):
            await refresh_table_metadata("conn-999")


@pytest.mark.asyncio
async def test_refresh_table_metadata_discovery_error():
    """Test refresh when discovery fails"""

    with patch("api.services.hana_schema_discovery.discover_tables") as mock_discover:
        mock_discover.side_effect = Exception("Discovery failed")

        # Should not raise, but return 0
        count = await refresh_table_metadata("conn-123")
        assert count == 0


@pytest.mark.asyncio
async def test_refresh_table_metadata_storage_error():
    """Test refresh when storage fails"""

    with patch("api.services.hana_schema_discovery.discover_tables") as mock_discover:
        mock_discover.return_value = [{"schema_name": "TEST", "table_name": "TABLE", "columns": []}]

        with patch("api.services.hana_schema_discovery.store_discovered_tables") as mock_store:
            mock_store.side_effect = Exception("Storage failed")

            # Should not raise, but return 0
            count = await refresh_table_metadata("conn-123")
            assert count == 0


# ============================================================================
# get_tables_for_connection() Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_tables_for_connection_success():
    """Test retrieving cached tables from database"""

    mock_rows = [
        {
            "id": "table-1",
            "connection_id": "conn-123",
            "schema_name": "SCHEMA_A",
            "table_name": "CUSTOMERS",
            "table_type": "TABLE",
            "column_metadata": json.dumps([
                {"name": "ID", "type": "INTEGER", "nullable": False, "position": 1}
            ]),
            "row_count": 1000,
            "discovered_at": "2024-03-28T10:00:00"
        },
        {
            "id": "table-2",
            "connection_id": "conn-123",
            "schema_name": "SCHEMA_A",
            "table_name": "ORDERS",
            "table_type": "TABLE",
            "column_metadata": json.dumps([
                {"name": "ORDER_ID", "type": "INTEGER", "nullable": False, "position": 1}
            ]),
            "row_count": 5000,
            "discovered_at": "2024-03-28T10:00:00"
        }
    ]

    with patch("api.services.hana_schema_discovery.repo_query") as mock_query:
        mock_query.return_value = mock_rows

        tables = await get_tables_for_connection("conn-123")

        # Verify query was called correctly
        mock_query.assert_called_once()
        call_args = mock_query.call_args
        assert "FROM hana_connection_tables" in call_args[0][0]
        assert call_args[0][1]["connection_id"] == "conn-123"

        # Verify results
        assert len(tables) == 2
        assert tables[0]["table_name"] == "CUSTOMERS"
        assert tables[0]["row_count"] == 1000

        # Verify column metadata was parsed from JSON
        assert isinstance(tables[0]["columns"], list)
        assert len(tables[0]["columns"]) == 1
        assert tables[0]["columns"][0]["name"] == "ID"


@pytest.mark.asyncio
async def test_get_tables_for_connection_empty():
    """Test retrieving tables when none exist"""

    with patch("api.services.hana_schema_discovery.repo_query") as mock_query:
        mock_query.return_value = []

        tables = await get_tables_for_connection("conn-123")

        assert len(tables) == 0


@pytest.mark.asyncio
async def test_get_tables_for_connection_null_column_metadata():
    """Test handling of null column metadata"""

    mock_rows = [
        {
            "id": "table-1",
            "connection_id": "conn-123",
            "schema_name": "SCHEMA_A",
            "table_name": "CUSTOMERS",
            "table_type": "TABLE",
            "column_metadata": None,  # Null metadata
            "row_count": 1000,
            "discovered_at": "2024-03-28T10:00:00"
        }
    ]

    with patch("api.services.hana_schema_discovery.repo_query") as mock_query:
        mock_query.return_value = mock_rows

        tables = await get_tables_for_connection("conn-123")

        assert len(tables) == 1
        assert tables[0]["columns"] == []  # Should default to empty list


@pytest.mark.asyncio
async def test_get_tables_for_connection_error():
    """Test error handling when query fails"""

    with patch("api.services.hana_schema_discovery.repo_query") as mock_query:
        mock_query.side_effect = Exception("Database query error")

        with pytest.raises(Exception, match="Failed to get tables"):
            await get_tables_for_connection("conn-123")


# ============================================================================
# get_table_details() Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_table_details_success():
    """Test retrieving specific table details"""

    mock_row = {
        "id": "table-1",
        "connection_id": "conn-123",
        "schema_name": "SCHEMA_A",
        "table_name": "CUSTOMERS",
        "table_type": "TABLE",
        "column_metadata": json.dumps([
            {"name": "ID", "type": "INTEGER", "nullable": False, "position": 1},
            {"name": "NAME", "type": "NVARCHAR", "nullable": True, "position": 2}
        ]),
        "row_count": 1000,
        "discovered_at": "2024-03-28T10:00:00"
    }

    with patch("api.services.hana_schema_discovery.repo_query") as mock_query:
        mock_query.return_value = [mock_row]

        table = await get_table_details("conn-123", "SCHEMA_A", "CUSTOMERS")

        # Verify query parameters
        call_args = mock_query.call_args
        params = call_args[0][1]
        assert params["connection_id"] == "conn-123"
        assert params["schema_name"] == "SCHEMA_A"
        assert params["table_name"] == "CUSTOMERS"

        # Verify result
        assert table is not None
        assert table["table_name"] == "CUSTOMERS"
        assert len(table["columns"]) == 2
        assert table["columns"][0]["name"] == "ID"


@pytest.mark.asyncio
async def test_get_table_details_not_found():
    """Test retrieving non-existent table"""

    with patch("api.services.hana_schema_discovery.repo_query") as mock_query:
        mock_query.return_value = []

        table = await get_table_details("conn-123", "SCHEMA_A", "NONEXISTENT")

        assert table is None


@pytest.mark.asyncio
async def test_get_table_details_error():
    """Test error handling when query fails"""

    with patch("api.services.hana_schema_discovery.repo_query") as mock_query:
        mock_query.side_effect = Exception("Database error")

        with pytest.raises(Exception, match="Failed to get table details"):
            await get_table_details("conn-123", "SCHEMA_A", "CUSTOMERS")
