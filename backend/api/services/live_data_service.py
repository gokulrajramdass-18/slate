"""
Live Data Service - Fetch real-time data from API and HANA sources

This service handles dynamic data fetching during chat sessions to provide
LLMs with up-to-date information from API endpoints and HANA tables.
"""
from typing import List, Dict, Any, Optional
import httpx
import json
import base64
import re
from cryptography.fernet import Fernet

from open_notebook.database.repository import repo_query
from open_notebook.config import get_encryption_key
from api.services.http_client import http_client_manager


async def decrypt_auth_config(encrypted: Optional[str]) -> Optional[Dict[str, Any]]:
    """Decrypt authentication configuration"""
    if not encrypted:
        return None

    key = get_encryption_key()
    if not key:
        return None

    try:
        fernet = Fernet(key.encode())
        encrypted_bytes = base64.b64decode(encrypted.encode())
        decrypted = fernet.decrypt(encrypted_bytes)
        return json.loads(decrypted.decode())
    except Exception:
        return None


async def fetch_api_source_data(source_id: str) -> Dict[str, Any]:
    """
    Fetch live data from an API source

    Returns:
        Dict with 'success', 'data', 'error', 'source_name', 'record_count'
    """
    try:
        # Get source and its connection
        source_sql = """
            SELECT s.*, s.title as source_name
            FROM sources s
            WHERE s.id = :source_id AND s.source_type = 'api'
        """
        source_results = await repo_query(source_sql, {"source_id": source_id})

        if not source_results:
            return {
                "success": False,
                "error": "API source not found",
                "source_name": "Unknown",
                "data": None,
                "record_count": 0
            }

        source = source_results[0]

        # Get connection config (stored in connection_config field)
        connection_config = json.loads(source.get("connection_config", "{}"))
        connection_id = connection_config.get("connection_id")

        if not connection_id:
            return {
                "success": False,
                "error": "No connection ID found for API source",
                "source_name": source["source_name"],
                "data": None,
                "record_count": 0
            }

        # Fetch connection details
        conn_sql = "SELECT * FROM api_connections WHERE id = :id"
        conn_results = await repo_query(conn_sql, {"id": connection_id})

        if not conn_results:
            return {
                "success": False,
                "error": "API connection not found",
                "source_name": source["source_name"],
                "data": None,
                "record_count": 0
            }

        conn = conn_results[0]

        # Decrypt auth config
        auth_config = await decrypt_auth_config(conn.get("auth_config_encrypted"))

        # Build request
        headers = json.loads(conn.get("headers") or "{}")
        query_params = json.loads(conn.get("query_params") or "{}")
        request_body = json.loads(conn["request_body"]) if conn.get("request_body") else None

        # Add authentication
        if conn["auth_type"] == "bearer" and auth_config and "token" in auth_config:
            headers["Authorization"] = f"Bearer {auth_config['token']}"
        elif conn["auth_type"] == "api_key" and auth_config:
            if auth_config.get("location") == "header":
                headers[auth_config.get("key", "X-API-Key")] = auth_config.get("value", "")
            elif auth_config.get("location") == "query":
                query_params[auth_config.get("key", "api_key")] = auth_config.get("value", "")
        elif conn["auth_type"] == "basic" and auth_config:
            import base64
            credentials = f"{auth_config.get('username', '')}:{auth_config.get('password', '')}"
            encoded = base64.b64encode(credentials.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"

        # Execute request
        client = http_client_manager.get_client()
        if conn.get("method", "GET") == "GET":
            response = await client.get(
                conn["endpoint"],
                headers=headers,
                params=query_params,
                timeout=30.0
            )
        else:
            response = await client.post(
                conn["endpoint"],
                headers=headers,
                params=query_params,
                json=request_body,
                timeout=30.0
            )

        response.raise_for_status()

        # Parse response
        data = response.json()

        # Extract data using data_path if specified
        if conn.get("data_path"):
            parts = conn["data_path"].split(".")
            for part in parts:
                if isinstance(data, dict):
                    data = data.get(part, [])
                else:
                    break

        record_count = len(data) if isinstance(data, list) else 1

        return {
            "success": True,
            "data": data,
            "error": None,
            "source_name": source["source_name"],
            "record_count": record_count,
            "endpoint": conn["endpoint"]
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "source_name": source.get("source_name", "Unknown") if 'source' in locals() else "Unknown",
            "data": None,
            "record_count": 0
        }


async def fetch_hana_source_data(source_id: str) -> Dict[str, Any]:
    """
    Fetch live data from a HANA table source

    Returns:
        Dict with 'success', 'data', 'error', 'source_name', 'record_count'
    """
    try:
        # Get source details
        source_sql = """
            SELECT s.*, s.title as source_name
            FROM sources s
            WHERE s.id = :source_id AND s.source_type = 'hana_table'
        """
        source_results = await repo_query(source_sql, {"source_id": source_id})

        if not source_results:
            return {
                "success": False,
                "error": "HANA source not found",
                "source_name": "Unknown",
                "data": None,
                "record_count": 0
            }

        source = source_results[0]

        # Get connection config (stored in connection_config field)
        connection_config = json.loads(source.get("connection_config", "{}"))
        connection_id = connection_config.get("connection_id")
        table_name = connection_config.get("table_name")
        content_columns = connection_config.get("content_columns", [])
        query = connection_config.get("query")

        if not connection_id or not table_name:
            return {
                "success": False,
                "error": "Missing connection ID or table name",
                "source_name": source["source_name"],
                "data": None,
                "record_count": 0
            }

        # Fetch HANA connection details
        conn_sql = "SELECT * FROM hana_connections WHERE id = :id"
        conn_results = await repo_query(conn_sql, {"id": connection_id})

        if not conn_results:
            return {
                "success": False,
                "error": "HANA connection not found",
                "source_name": source["source_name"],
                "data": None,
                "record_count": 0
            }

        conn = conn_results[0]

        # Import HANA driver
        try:
            from hdbcli import dbapi
        except ImportError:
            return {
                "success": False,
                "error": "HANA client library not installed (pip install hdbcli)",
                "source_name": source["source_name"],
                "data": None,
                "record_count": 0
            }

        # Decrypt password using the utility function
        from api.services.hana_connection_utils import decrypt_password

        encrypted_password = conn.get("password_encrypted")
        if not encrypted_password:
            return {
                "success": False,
                "error": "No password stored for connection",
                "source_name": source["source_name"],
                "data": None,
                "record_count": 0
            }

        password = decrypt_password(encrypted_password)

        # Connect to HANA
        connection = dbapi.connect(
            address=conn["host"],
            port=conn["port"],
            user=conn["user"],
            password=password,
            encrypt=conn.get("encrypt", True),
            sslValidateCertificate=False
        )

        cursor = connection.cursor()

        # Build query
        if query:
            # Use custom query
            sql_query = query
        else:
            # Build default query
            columns_str = ", ".join(content_columns) if content_columns else "*"
            sql_query = f"SELECT {columns_str} FROM {table_name} LIMIT 100"

        # Execute query
        cursor.execute(sql_query)

        # Fetch results
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        # Convert to list of dicts
        data = []
        for row in rows:
            data.append(dict(zip(columns, row)))

        cursor.close()
        connection.close()

        return {
            "success": True,
            "data": data,
            "error": None,
            "source_name": source["source_name"],
            "record_count": len(data),
            "table_name": table_name
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "source_name": source.get("source_name", "Unknown") if 'source' in locals() else "Unknown",
            "data": None,
            "record_count": 0
        }


async def fetch_all_live_sources(notebook_id: str) -> List[Dict[str, Any]]:
    """
    Fetch live data from all API and HANA sources in a notebook

    Returns:
        List of result dicts from fetch_api_source_data and fetch_hana_source_data
    """
    # Get all API and HANA sources for this notebook
    sql = """
        SELECT s.id, s.source_type
        FROM sources s
        INNER JOIN notebook_source ns ON s.id = ns.source_id
        WHERE ns.notebook_id = :notebook_id
        AND s.source_type IN ('api', 'hana_table')
    """

    sources = await repo_query(sql, {"notebook_id": notebook_id})

    results = []

    for source in sources:
        if source["source_type"] == "api":
            result = await fetch_api_source_data(source["id"])
            results.append(result)
        elif source["source_type"] == "hana_table":
            result = await fetch_hana_source_data(source["id"])
            results.append(result)

    return results


def format_live_data_for_context(live_results: List[Dict[str, Any]]) -> str:
    """
    Format live data results into a string for LLM context

    Args:
        live_results: List of results from fetch_all_live_sources

    Returns:
        Formatted string with live data
    """
    if not live_results:
        return ""

    context_parts = ["\n\n=== LIVE DATA FROM SOURCES ===\n"]

    for result in live_results:
        if not result["success"]:
            context_parts.append(
                f"\n[{result['source_name']}]\n"
                f"Status: Failed to fetch\n"
                f"Error: {result['error']}\n"
            )
            continue

        context_parts.append(
            f"\n[{result['source_name']}]\n"
            f"Status: Success\n"
            f"Records: {result['record_count']}\n"
        )

        if "endpoint" in result:
            context_parts.append(f"Endpoint: {result['endpoint']}\n")
        if "table_name" in result:
            context_parts.append(f"Table: {result['table_name']}\n")

        # Format data (limit to avoid context overflow)
        data = result["data"]
        if isinstance(data, list):
            # Show first 50 records
            limited_data = data[:50]
            context_parts.append(f"\nData (showing {len(limited_data)} of {len(data)} records):\n")
            context_parts.append(json.dumps(limited_data, indent=2, default=str))
            if len(data) > 50:
                context_parts.append(f"\n... and {len(data) - 50} more records")
        else:
            context_parts.append("\nData:\n")
            context_parts.append(json.dumps(data, indent=2, default=str))

        context_parts.append("\n")

    context_parts.append("\n=== END LIVE DATA ===\n")

    return "".join(context_parts)


# ============================================================================
# Parameterized API Execution (for Agent Tools)
# ============================================================================

async def execute_api_call_with_params(
    source_id: str,
    params: Optional[Dict[str, Any]] = None,
    filters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Execute API call with dynamic parameters (for LangChain tools)

    Args:
        source_id: API source UUID
        params: Query parameters to override/add to default params
        filters: Filtering criteria for response data

    Returns:
        Dict with 'success', 'data', 'error', 'record_count'
    """
    try:
        # Get source and its connection
        source_sql = """
            SELECT s.*, s.title as source_name
            FROM sources s
            WHERE s.id = :source_id AND s.source_type = 'api'
        """
        source_results = await repo_query(source_sql, {"source_id": source_id})

        if not source_results:
            return {
                "success": False,
                "error": "API source not found",
                "data": None,
                "record_count": 0
            }

        source = source_results[0]

        # Get connection config
        connection_config = json.loads(source.get("connection_config", "{}"))
        connection_id = connection_config.get("connection_id")

        if not connection_id:
            return {
                "success": False,
                "error": "No connection ID found for API source",
                "data": None,
                "record_count": 0
            }

        # Fetch connection details
        conn_sql = "SELECT * FROM api_connections WHERE id = :id"
        conn_results = await repo_query(conn_sql, {"id": connection_id})

        if not conn_results:
            return {
                "success": False,
                "error": "API connection not found",
                "data": None,
                "record_count": 0
            }

        conn = conn_results[0]

        # Decrypt auth config
        auth_config = await decrypt_auth_config(conn.get("auth_config_encrypted"))

        # Build request
        headers = json.loads(conn.get("headers") or "{}")

        # Merge query parameters (agent params override defaults)
        default_params = json.loads(conn.get("query_params") or "{}")
        query_params = {**default_params, **(params or {})}

        request_body = json.loads(conn["request_body"]) if conn.get("request_body") else None

        # Add authentication
        if conn["auth_type"] == "bearer" and auth_config and "token" in auth_config:
            headers["Authorization"] = f"Bearer {auth_config['token']}"
        elif conn["auth_type"] == "api_key" and auth_config:
            if auth_config.get("location") == "header":
                headers[auth_config.get("key", "X-API-Key")] = auth_config.get("value", "")
            elif auth_config.get("location") == "query":
                query_params[auth_config.get("key", "api_key")] = auth_config.get("value", "")
        elif conn["auth_type"] == "basic" and auth_config:
            credentials = f"{auth_config.get('username', '')}:{auth_config.get('password', '')}"
            encoded = base64.b64encode(credentials.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"

        # Execute request
        client = http_client_manager.get_client()
        if conn.get("method", "GET") == "GET":
            response = await client.get(
                conn["endpoint"],
                headers=headers,
                params=query_params,
                timeout=30.0
            )
        else:
            response = await client.post(
                conn["endpoint"],
                headers=headers,
                params=query_params,
                json=request_body,
                timeout=30.0
            )

        response.raise_for_status()

        # Parse response
        data = response.json()

        # Extract data using data_path if specified
        if conn.get("data_path"):
            data = extract_jsonpath(data, conn["data_path"])

        # Apply filters if specified
        if filters and isinstance(data, list):
            data = apply_filters(data, filters)

        record_count = len(data) if isinstance(data, list) else 1

        return {
            "success": True,
            "data": data,
            "error": None,
            "record_count": record_count
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": None,
            "record_count": 0
        }


def extract_jsonpath(data: Any, path: str) -> Any:
    """
    Extract data using JSONPath (simple dot notation)

    Args:
        data: JSON data (dict or list)
        path: Dot-separated path (e.g., "data.items" or "users.0.profile")

    Returns:
        Extracted data
    """
    if not path:
        return data

    parts = path.split(".")
    current = data

    for part in parts:
        if isinstance(current, dict):
            current = current.get(part, None)
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            current = current[index] if index < len(current) else None
        else:
            return None

        if current is None:
            return []

    return current


def apply_filters(data: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Apply filters to list of dictionaries

    Args:
        data: List of records (dicts)
        filters: Dict of field: value pairs to filter by

    Returns:
        Filtered list
    """
    if not filters:
        return data

    filtered = []
    for record in data:
        matches = True
        for key, value in filters.items():
            # Support nested keys with dot notation
            record_value = record
            for part in key.split("."):
                if isinstance(record_value, dict):
                    record_value = record_value.get(part)
                else:
                    record_value = None
                    break

            # Compare values
            if record_value != value:
                # Try regex matching for strings
                if isinstance(record_value, str) and isinstance(value, str):
                    if not re.search(value, record_value, re.IGNORECASE):
                        matches = False
                        break
                else:
                    matches = False
                    break

        if matches:
            filtered.append(record)

    return filtered
