"""
HANA Tool Executor Service

Executes HANA SQL queries when LLM calls function tools.
Includes safety validation, connection management, and result formatting.
"""

from typing import Dict, Any, List
import json
import signal
from hdbcli import dbapi
from api.routers.hana_connections import decrypt_password


class HANAToolExecutor:
    """Execute HANA SQL queries triggered by LLM function calls"""

    # Safety limits
    MAX_ROWS = 500
    MAX_RESPONSE_SIZE = 1_000_000  # 1MB
    QUERY_TIMEOUT = 30  # seconds

    @staticmethod
    def _validate_sql_safety(sql: str) -> None:
        """
        Validate SQL is safe (SELECT only, no dangerous operations)

        Args:
            sql: SQL query string

        Raises:
            ValueError: If SQL contains dangerous operations
        """
        sql_upper = sql.upper().strip()

        # Must start with SELECT
        if not sql_upper.startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed")

        # Block dangerous keywords
        dangerous_keywords = [
            "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE",
            "TRUNCATE", "EXEC", "EXECUTE", "CALL", "GRANT", "REVOKE"
        ]
        for keyword in dangerous_keywords:
            if f" {keyword} " in f" {sql_upper} " or sql_upper.endswith(keyword):
                raise ValueError(f"Dangerous SQL keyword detected: {keyword}")

        # Block semicolons (prevent multiple statements)
        if ";" in sql:
            raise ValueError("Multiple SQL statements not allowed (semicolon detected)")

        # Block comments that could hide malicious code
        if "--" in sql or "/*" in sql or "*/" in sql:
            raise ValueError("SQL comments not allowed")

    @staticmethod
    async def _get_connection_credentials(connection_config: Dict[str, Any]) -> Dict[str, str]:
        """
        Get HANA connection credentials from config

        Args:
            connection_config: Connection configuration from source

        Returns:
            Dict with host, port, user, password, database
        """
        from open_notebook.database.repository import repo_query

        # Check if using connection_id (saved connection)
        if "connection_id" in connection_config and connection_config["connection_id"]:
            conn_id = connection_config["connection_id"]
            conn_sql = "SELECT * FROM hana_connections WHERE id = :id"
            conn_results = await repo_query(conn_sql, {"id": conn_id})

            if not conn_results:
                raise ValueError(f"HANA connection {conn_id} not found")

            conn = conn_results[0]

            # Decrypt password (column name is password_encrypted)
            encrypted_password = conn.get("password_encrypted")
            if not encrypted_password:
                raise ValueError(f"No password stored for connection {conn_id}")

            decrypted_password = decrypt_password(encrypted_password)

            return {
                "host": conn["host"],
                "port": conn["port"],
                "user": conn["user"],
                "password": decrypted_password,
                "database": conn["database"]
            }

        # Fallback: Direct connection config (legacy)
        elif "connection" in connection_config:
            conn_cfg = connection_config["connection"]
            return {
                "host": conn_cfg["host"],
                "port": conn_cfg["port"],
                "user": conn_cfg["user"],
                "password": conn_cfg["password"],  # Already decrypted
                "database": conn_cfg.get("database", conn_cfg.get("databaseName", ""))
            }

        else:
            raise ValueError("Invalid connection configuration: missing connection_id or connection")

    @staticmethod
    def _build_sql_query(
        table_name: str,
        columns: List[str],
        content_columns: List[str],
        where_clause: str = "",
        group_by: str = "",
        order_by: str = "",
        limit: int = 50
    ) -> str:
        """
        Build safe SQL query from parameters

        Args:
            table_name: Table to query
            columns: Columns to SELECT (empty for default)
            content_columns: Default columns from source config
            where_clause: WHERE condition (without WHERE keyword)
            group_by: GROUP BY clause (without GROUP BY keyword)
            order_by: ORDER BY clause (without ORDER BY keyword)
            limit: Maximum rows to return

        Returns:
            Complete SQL query string
        """
        # Use provided columns or fall back to content_columns
        if columns:
            columns_str = ", ".join(columns)
        elif content_columns:
            columns_str = ", ".join(content_columns)
        else:
            columns_str = "*"

        # Build query
        sql = f"SELECT {columns_str} FROM {table_name}"

        if where_clause:
            sql += f" WHERE {where_clause}"

        if group_by:
            sql += f" GROUP BY {group_by}"

        if order_by:
            sql += f" ORDER BY {order_by}"

        # Cap limit at MAX_ROWS
        limit = min(limit, HANAToolExecutor.MAX_ROWS)
        sql += f" LIMIT {limit}"

        return sql

    @staticmethod
    async def execute_tool(
        tool_call: Dict[str, Any],
        tool_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Execute HANA query based on LLM tool call

        Args:
            tool_call: LLM function call with name and arguments
            tool_metadata: Metadata from tool schema (source_id, table_name, etc.)

        Returns:
            Query results as list of dicts

        Raises:
            ValueError: If SQL validation fails
            TimeoutError: If query exceeds timeout
            Exception: If query execution fails
        """
        # Parse arguments from tool call
        try:
            if "arguments" in tool_call:
                # Handle both dict (Anthropic) and string (OpenAI) formats
                if isinstance(tool_call["arguments"], dict):
                    args = tool_call["arguments"]
                elif isinstance(tool_call["arguments"], str):
                    args = json.loads(tool_call["arguments"])
                else:
                    args = {}
            else:
                args = {}
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid tool call arguments: {str(e)}")

        # Extract parameters
        columns = args.get("columns", [])
        where_clause = args.get("where_clause", "")
        group_by = args.get("group_by", "")
        order_by = args.get("order_by", "")
        limit = args.get("limit", 50)

        # Get metadata
        table_name = tool_metadata["table_name"]
        content_columns = tool_metadata["content_columns"]
        connection_config = tool_metadata["connection_config"]

        # Build SQL
        sql = HANAToolExecutor._build_sql_query(
            table_name=table_name,
            columns=columns,
            content_columns=content_columns,
            where_clause=where_clause,
            group_by=group_by,
            order_by=order_by,
            limit=limit
        )

        # Validate SQL safety
        HANAToolExecutor._validate_sql_safety(sql)

        print(f"🔍 Executing HANA query: {sql}")

        # Get connection credentials
        creds = await HANAToolExecutor._get_connection_credentials(connection_config)

        # Execute query with timeout
        connection = None
        cursor = None

        def timeout_handler(signum, frame):
            raise TimeoutError(f"Query exceeded maximum execution time ({HANAToolExecutor.QUERY_TIMEOUT}s)")

        # Set timeout (Unix-only, won't work on Windows)
        try:
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(HANAToolExecutor.QUERY_TIMEOUT)
        except (AttributeError, ValueError):
            # SIGALRM not available (Windows) - skip timeout
            pass

        try:
            # Connect to HANA
            # Note: For HANA Cloud, databaseName parameter is usually not needed
            # and can cause connection errors. Omit it for best compatibility.
            connection_params = {
                "address": creds["host"],
                "port": creds["port"],
                "user": creds["user"],
                "password": creds["password"],
                "encrypt": True
            }

            # Do NOT include databaseName for HANA Cloud connections
            # (it's auto-determined from the connection)

            connection = dbapi.connect(**connection_params)

            cursor = connection.cursor()
            cursor.execute(sql)

            # Fetch results
            column_names = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            # Convert to list of dicts
            results = [
                {column_names[i]: HANAToolExecutor._convert_value(row[i]) for i in range(len(column_names))}
                for row in rows
            ]

            # Check result size
            results_json = json.dumps(results, default=str)
            if len(results_json) > HANAToolExecutor.MAX_RESPONSE_SIZE:
                raise ValueError(
                    f"Query result too large ({len(results_json)} bytes). "
                    f"Try reducing LIMIT or selecting fewer columns."
                )

            print(f"✅ Query returned {len(results)} rows")
            return results

        except TimeoutError:
            print(f"❌ Query timeout: {sql}")
            raise

        except Exception as e:
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "sql_query": sql,
                "table_name": table_name,
                "connection_host": creds.get("host", "unknown")
            }
            print(f"❌ HANA query execution failed: {json.dumps(error_details, indent=2)}")
            raise Exception(f"Failed to query HANA table '{table_name}': {str(e)}. SQL: {sql}")

        finally:
            # Cancel timeout alarm
            try:
                signal.alarm(0)
            except (AttributeError, ValueError):
                pass

            # Close connection
            if cursor:
                try:
                    cursor.close()
                except:
                    pass

            if connection:
                try:
                    connection.close()
                except:
                    pass

    @staticmethod
    def _convert_value(value: Any) -> Any:
        """
        Convert HANA value to JSON-serializable format

        Args:
            value: Raw value from HANA query result

        Returns:
            JSON-serializable value
        """
        # Handle None
        if value is None:
            return None

        # Handle dates/times - convert to ISO string
        if hasattr(value, 'isoformat'):
            return value.isoformat()

        # Handle bytes - convert to string
        if isinstance(value, bytes):
            return value.decode('utf-8', errors='replace')

        # Handle decimals - convert to float
        if hasattr(value, '__float__'):
            return float(value)

        # Return as-is
        return value
