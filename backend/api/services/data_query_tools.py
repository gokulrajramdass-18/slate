"""
LangChain Tool Wrappers for HANA and API Sources

Provides LangChain-compatible tool wrappers that delegate to existing
tool executors while maintaining observability and error handling.
"""

import json
import time
from typing import Type, Dict, Any, List, Optional
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from open_notebook.database.repository import repo_query
from api.services.tools.chart_tool import get_chart_tool


# ============================================================================
# Tool Input Schemas
# ============================================================================

class HANAQueryInput(BaseModel):
    """Input schema for HANA query tool"""
    columns: List[str] = Field(
        default=["*"],
        description="Columns to select (e.g., ['id', 'name', 'total']). Use ['*'] for all columns."
    )
    where_clause: str = Field(
        default="",
        description="WHERE condition without the WHERE keyword (e.g., 'amount > 1000 AND status = \"active\"')"
    )
    group_by: str = Field(
        default="",
        description="GROUP BY clause (e.g., 'category')"
    )
    order_by: str = Field(
        default="",
        description="ORDER BY clause (e.g., 'created DESC')"
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of rows to return (1-500)"
    )


class APICallInput(BaseModel):
    """Input schema for API call tool"""
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Query parameters to send with the API request"
    )
    filters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Filters to apply to the response data (e.g., {'status': 'active'})"
    )


class FileDataQueryInput(BaseModel):
    """Input schema for file data query tool"""
    query: str = Field(
        description="Natural language query about the file data (e.g., 'Show me accounts with revenue > 1000')"
    )


# ============================================================================
# HANA Query Tool
# ============================================================================

class HANAQueryTool(BaseTool):
    """Tool for querying HANA database tables via natural language"""

    name: str = "query_hana_table"
    description: str = ""  # Will be set dynamically per instance
    args_schema: Type[BaseModel] = HANAQueryInput

    # Custom attributes (not passed to LLM)
    source_id: str
    table_name: str
    connection_config: Dict[str, Any]
    session_id: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data):
        # Build description with table info
        table_name = data.get("table_name", "table")
        data["description"] = (
            f"Query the {table_name} table from HANA database. "
            f"Use this to retrieve, filter, aggregate, and analyze data. "
            f"Returns results as JSON array of objects."
        )
        super().__init__(**data)

    async def _arun(self, **kwargs) -> str:
        """Execute HANA query"""
        start_time = time.time()

        try:
            # Import executor
            from api.services.hana_tool_executor import HANAToolExecutor

            # Build tool call format expected by executor
            tool_call = {
                "id": f"call_{int(time.time())}",
                "function": {"name": self.name},
                "arguments": kwargs
            }

            # Build metadata format expected by executor
            tool_metadata = {
                "source_id": self.source_id,
                "table_name": self.table_name,
                "content_columns": kwargs.get("columns", ["*"]),
                "connection_config": self.connection_config
            }

            # Execute query
            results = await HANAToolExecutor.execute_tool(tool_call, tool_metadata)

            # Log execution time
            duration_ms = (time.time() - start_time) * 1000

            # Build response - only add visualization if query succeeded
            response = {
                "success": True,
                "rows": results,
                "count": len(results),
                "duration_ms": round(duration_ms, 2)
            }

            # Only check for charting if we have results
            if results and len(results) > 0:
                # Check if results should be visualized as chart
                chart_tool = get_chart_tool()
                should_chart = chart_tool.should_use_chart(results, max_rows=100)

                # Add chart metadata if suitable for visualization
                if should_chart:
                    from api.services.chart_analyzer import ChartAnalyzer
                    analyzer = ChartAnalyzer()
                    chart_type, chart_config = analyzer.analyze_and_suggest(results)

                    response["visualization_hint"] = chart_type
                    response["chart_config"] = {
                        "xKey": chart_config["xKey"],
                        "yKeys": chart_config["yKeys"],
                        "colors": chart_config["colors"],
                        "legend": chart_config.get("legend", True),
                        "grid": chart_config.get("grid", True),
                    }

            # Log to LangFuse if available
            try:
                from api.services.langfuse_observer import langfuse_observer
                if self.session_id:
                    langfuse_observer.log_tool_execution(
                        tool_name=self.name,
                        input_params=kwargs,
                        output=response,
                        duration_ms=duration_ms,
                        session_id=self.session_id
                    )
            except ImportError:
                pass  # LangFuse not available yet

            # Return as JSON string
            return json.dumps(response, default=str)

        except Exception as e:
            error_msg = str(e)
            print(f"❌ HANAQueryTool error: {error_msg}")

            # Extract more details from the error
            error_details = {
                "success": False,
                "error": error_msg,
                "error_type": type(e).__name__,
                "rows": [],
                "count": 0,
                "table_name": self.table_name,
                "query_params": {
                    "columns": kwargs.get("columns", []),
                    "where_clause": kwargs.get("where_clause", ""),
                    "limit": kwargs.get("limit", 50)
                }
            }

            # Log to console for debugging
            print(f"❌ Query failed for table '{self.table_name}': {error_msg}")

            # Return detailed error as JSON
            return json.dumps(error_details, default=str)

    def _run(self, **kwargs) -> str:
        """Sync version not supported"""
        raise NotImplementedError("HANAQueryTool only supports async execution")


# ============================================================================
# API Call Tool
# ============================================================================

class APICallTool(BaseTool):
    """Tool for calling external REST APIs"""

    name: str = "call_api"
    description: str = ""  # Will be set dynamically per instance
    args_schema: Type[BaseModel] = APICallInput

    # Custom attributes
    source_id: str
    endpoint: str
    connection_config: Dict[str, Any]
    session_id: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data):
        # Build description with API info
        source_name = data.get("source_name", "API")
        endpoint = data.get("endpoint", "")
        data["description"] = (
            f"Call the {source_name} API endpoint: {endpoint}. "
            f"Use this to fetch real-time data from the external API. "
            f"Returns JSON response data."
        )
        super().__init__(**data)

    async def _arun(self, **kwargs) -> str:
        """Execute API call"""
        start_time = time.time()

        try:
            # Import live data service
            from api.services.live_data_service import execute_api_call_with_params

            # Extract parameters
            params = kwargs.get("params", {})
            filters = kwargs.get("filters", {})

            # Execute API call
            result = await execute_api_call_with_params(
                source_id=self.source_id,
                params=params,
                filters=filters
            )

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Check if API result data should be charted
            if result["success"] and result.get("data"):
                data = result["data"]
                chart_tool = get_chart_tool()

                # Check if data is list of dicts (chartable)
                if isinstance(data, list) and data and isinstance(data[0], dict):
                    should_chart = chart_tool.should_use_chart(data, max_rows=100)

                    if should_chart:
                        from api.services.chart_analyzer import ChartAnalyzer
                        analyzer = ChartAnalyzer()
                        chart_type, chart_config = analyzer.analyze_and_suggest(data)

                        result["visualization_hint"] = chart_type
                        result["chart_config"] = {
                            "xKey": chart_config["xKey"],
                            "yKeys": chart_config["yKeys"],
                            "colors": chart_config["colors"],
                            "legend": chart_config.get("legend", True),
                            "grid": chart_config.get("grid", True),
                        }

            # Log to LangFuse if available
            try:
                from api.services.langfuse_observer import langfuse_observer
                if self.session_id:
                    langfuse_observer.log_tool_execution(
                        tool_name=self.name,
                        input_params=kwargs,
                        output=result,
                        duration_ms=duration_ms,
                        session_id=self.session_id
                    )
            except ImportError:
                pass

            # Return result as JSON
            if result["success"]:
                response = {
                    "success": True,
                    "data": result["data"],
                    "count": result["record_count"],
                    "duration_ms": round(duration_ms, 2)
                }

                # Include chart metadata if present
                if "visualization_hint" in result:
                    response["visualization_hint"] = result["visualization_hint"]
                    response["chart_config"] = result["chart_config"]

                return json.dumps(response, default=str)
            else:
                return json.dumps({
                    "success": False,
                    "error": result["error"],
                    "data": None,
                    "count": 0
                })

        except Exception as e:
            error_msg = str(e)
            print(f"❌ APICallTool error: {error_msg}")

            return json.dumps({
                "success": False,
                "error": error_msg,
                "data": None,
                "count": 0
            })

    def _run(self, **kwargs) -> str:
        """Sync version not supported"""
        raise NotImplementedError("APICallTool only supports async execution")


# ============================================================================
# File Data Query Tool
# ============================================================================

class FileDataTool(BaseTool):
    """Tool for querying data from uploaded files (Excel, CSV, etc.)"""

    name: str = "query_file_data"
    description: str = ""  # Will be set dynamically per instance
    args_schema: Type[BaseModel] = FileDataQueryInput

    # Custom attributes
    source_id: str
    file_name: str
    content: str
    session_id: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data):
        # Build description with file info
        file_name = data.get("file_name", "file")
        data["description"] = (
            f"Query data from the {file_name} file. "
            f"Use this to answer questions about the data in this file. "
            f"Returns relevant information based on the query."
        )
        super().__init__(**data)

    async def _arun(self, query: str) -> str:
        """Execute file data query"""
        try:
            # Return the first part of file content with the query context
            response = {
                "success": True,
                "file_name": self.file_name,
                "query": query,
                "content_preview": self.content,
                "message": f"Here is data from {self.file_name}. Analyze this content to answer the query: {query}"
            }

            return json.dumps(response, default=str)

        except Exception as e:
            error_msg = str(e)
            print(f"❌ FileDataTool error: {error_msg}")

            return json.dumps({
                "success": False,
                "error": error_msg,
                "file_name": self.file_name
            })

    def _run(self, query: str) -> str:
        """Sync version not supported"""
        raise NotImplementedError("FileDataTool only supports async execution")


# ============================================================================
# Connection-Level Tool Generation (Auto-Discovered Tables/Endpoints)
# ============================================================================

async def _get_hana_connection_level_tools(
    notebook_id: str,
    session_id: Optional[str] = None
) -> List[BaseTool]:
    """
    Generate tools for auto-discovered HANA tables from connections used by notebook sources

    Args:
        notebook_id: Notebook UUID
        session_id: Optional chat session ID for observability

    Returns:
        List of HANAQueryTool instances for discovered tables
    """
    tools = []

    # Find all HANA connections used by sources in this notebook
    connections_sql = """
        SELECT DISTINCT hc.id, hc.name, hc.host, hc.port, hc.database, hc.schema
        FROM hana_connections hc
        INNER JOIN sources s ON json_extract(s.connection_config, '$.connection_id') = hc.id
        INNER JOIN notebook_source ns ON s.id = ns.source_id
        WHERE ns.notebook_id = :notebook_id
        AND s.source_type = 'hana_table'
    """

    connections = await repo_query(connections_sql, {"notebook_id": notebook_id})

    for conn in connections:
        try:
            # Get discovered tables for this connection
            tables_sql = """
                SELECT id, schema_name, table_name, table_type, column_metadata, row_count
                FROM hana_connection_tables
                WHERE connection_id = :connection_id
                ORDER BY table_name
            """

            discovered_tables = await repo_query(tables_sql, {"connection_id": conn["id"]})

            for table in discovered_tables:
                try:
                    # Build connection config for tool
                    connection_config = {
                        "connection_id": conn["id"],
                        "table_name": table["table_name"],
                        "schema_name": table.get("schema_name") or conn.get("schema"),
                        "host": conn["host"],
                        "port": conn["port"],
                        "database": conn["database"]
                    }

                    # Use connection_id as source_id (marker for auto-discovered)
                    tool = HANAQueryTool(
                        source_id=conn["id"],  # Using connection_id as marker
                        table_name=table["table_name"],
                        connection_config=connection_config,
                        session_id=session_id,
                        name=f"query_{_sanitize_tool_name(table['table_name'])}"
                    )
                    tools.append(tool)

                except Exception as e:
                    print(f"⚠️ Failed to create tool for discovered table {table['table_name']}: {e}")
                    continue

            if discovered_tables:
                print(f"✅ Created {len(discovered_tables)} auto-discovered HANA tools from connection {conn['name']}")

        except Exception as e:
            print(f"⚠️ Failed to get discovered tables for connection {conn['id']}: {e}")
            continue

    return tools


async def _get_api_connection_level_tools(
    notebook_id: str,
    session_id: Optional[str] = None
) -> List[BaseTool]:
    """
    Generate tools for auto-discovered API endpoints from connections used by notebook sources

    Args:
        notebook_id: Notebook UUID
        session_id: Optional chat session ID for observability

    Returns:
        List of APICallTool instances for discovered endpoints
    """
    tools = []

    # Find all API connections used by sources in this notebook
    connections_sql = """
        SELECT DISTINCT ac.id, ac.name, ac.endpoint
        FROM api_connections ac
        INNER JOIN sources s ON json_extract(s.connection_config, '$.connection_id') = ac.id
        INNER JOIN notebook_source ns ON s.id = ns.source_id
        WHERE ns.notebook_id = :notebook_id
        AND s.source_type = 'api'
    """

    connections = await repo_query(connections_sql, {"notebook_id": notebook_id})

    for conn in connections:
        try:
            # Get discovered endpoints for this connection
            endpoints_sql = """
                SELECT id, endpoint_path, method, description, parameters, response_schema
                FROM api_connection_endpoints
                WHERE connection_id = :connection_id
                AND method = 'GET'
                ORDER BY endpoint_path
            """

            discovered_endpoints = await repo_query(endpoints_sql, {"connection_id": conn["id"]})

            # Skip if no endpoints discovered (fallback to current behavior)
            if not discovered_endpoints:
                continue

            for endpoint in discovered_endpoints:
                try:
                    # Build full endpoint path
                    full_endpoint = endpoint["endpoint_path"]
                    if not full_endpoint.startswith("/"):
                        full_endpoint = "/" + full_endpoint

                    # Build connection config for tool
                    connection_config = {
                        "connection_id": conn["id"],
                        "endpoint": full_endpoint,
                        "method": endpoint["method"],
                        "base_url": conn["base_url"]
                    }

                    # Create descriptive name
                    endpoint_name = endpoint.get("description") or endpoint["endpoint_path"]

                    # Use connection_id as source_id (marker for auto-discovered)
                    tool = APICallTool(
                        source_id=conn["id"],  # Using connection_id as marker
                        endpoint=full_endpoint,
                        connection_config=connection_config,
                        session_id=session_id,
                        source_name=f"{conn['name']} - {endpoint_name}",
                        name=f"call_{_sanitize_tool_name(endpoint_name)}"
                    )
                    tools.append(tool)

                except Exception as e:
                    print(f"⚠️ Failed to create tool for discovered endpoint {endpoint['endpoint_path']}: {e}")
                    continue

            if discovered_endpoints:
                print(f"✅ Created {len(discovered_endpoints)} auto-discovered API tools from connection {conn['name']}")

        except Exception as e:
            print(f"⚠️ Failed to get discovered endpoints for connection {conn['id']}: {e}")
            continue

    return tools


def _deduplicate_tools(tools: List[BaseTool]) -> List[BaseTool]:
    """
    Remove duplicate tools by tool name, preferring explicit sources over auto-discovered

    Auto-discovered tools have source_id == connection_id
    Explicit source tools have source_id != connection_id

    Args:
        tools: List of tools to deduplicate

    Returns:
        Deduplicated list of tools
    """
    tools_by_name = {}

    for tool in tools:
        tool_name = tool.name

        if tool_name not in tools_by_name:
            # First occurrence, add it
            tools_by_name[tool_name] = tool
        else:
            # Duplicate found - prefer explicit source over auto-discovered
            existing_tool = tools_by_name[tool_name]

            # Check if existing tool is auto-discovered
            # Auto-discovered tools have source_id that matches a connection_id pattern
            # For simplicity, we'll assume tools added from explicit sources come first
            # and only replace if the new tool is explicit (different logic needed)

            # Actually, let's prefer whichever was added first (explicit sources come first)
            # So we keep the existing tool and skip the new one
            continue

    deduplicated = list(tools_by_name.values())

    duplicates_removed = len(tools) - len(deduplicated)
    if duplicates_removed > 0:
        print(f"🔄 Removed {duplicates_removed} duplicate tools")

    return deduplicated


# ============================================================================
# Tool Factory
# ============================================================================

async def create_tools_for_notebook(
    notebook_id: str,
    session_id: Optional[str] = None
) -> List[BaseTool]:
    """
    Generate LangChain tools from notebook sources (explicit + auto-discovered)

    Args:
        notebook_id: Notebook UUID
        session_id: Optional chat session ID for observability

    Returns:
        List of LangChain BaseTool instances (HANA + API tools)
    """
    tools = []

    # ========================================================================
    # PART 1: Create tools for explicit HANA table sources
    # ========================================================================
    hana_sql = """
        SELECT s.id, s.title, s.connection_config
        FROM sources s
        INNER JOIN notebook_source ns ON s.id = ns.source_id
        WHERE ns.notebook_id = :notebook_id
        AND s.source_type = 'hana_table'
    """

    hana_sources = await repo_query(hana_sql, {"notebook_id": notebook_id})

    for source in hana_sources:
        try:
            # Parse connection config
            config = json.loads(source.get("connection_config", "{}"))

            # Create HANA tool
            tool = HANAQueryTool(
                source_id=source["id"],
                table_name=config.get("table_name", "table"),
                connection_config=config,
                session_id=session_id,
                name=f"query_{_sanitize_tool_name(config.get('table_name', 'table'))}"
            )
            tools.append(tool)

            print(f"✅ Created HANA tool: {tool.name}")

        except Exception as e:
            print(f"⚠️ Failed to create HANA tool for source {source['id']}: {e}")
            continue

    # ========================================================================
    # PART 2: Create tools for explicit API sources
    # ========================================================================
    api_sql = """
        SELECT s.id, s.title, s.connection_config
        FROM sources s
        INNER JOIN notebook_source ns ON s.id = ns.source_id
        WHERE ns.notebook_id = :notebook_id
        AND s.source_type = 'api'
    """

    api_sources = await repo_query(api_sql, {"notebook_id": notebook_id})

    for source in api_sources:
        try:
            # Parse connection config
            config = json.loads(source.get("connection_config", "{}"))

            # Get connection details
            connection_id = config.get("connection_id")
            if not connection_id:
                print(f"⚠️ API source {source['id']} has no connection_id")
                continue

            # Fetch connection
            conn_sql = "SELECT * FROM api_connections WHERE id = :id"
            conn_results = await repo_query(conn_sql, {"id": connection_id})

            if not conn_results:
                print(f"⚠️ API connection {connection_id} not found")
                continue

            conn = conn_results[0]

            # Create API tool
            tool = APICallTool(
                source_id=source["id"],
                endpoint=conn["endpoint"],
                connection_config=config,
                session_id=session_id,
                source_name=source["title"],
                name=f"call_{_sanitize_tool_name(source['title'])}"
            )
            tools.append(tool)

            print(f"✅ Created API tool: {tool.name}")

        except Exception as e:
            print(f"⚠️ Failed to create API tool for source {source['id']}: {e}")
            continue

    # ========================================================================
    # PART 2.5: Create tools for file sources (Excel, PDF, etc.)
    # ========================================================================
    file_sql = """
        SELECT s.id, s.title, s.full_text
        FROM sources s
        INNER JOIN notebook_source ns ON s.id = ns.source_id
        WHERE ns.notebook_id = :notebook_id
        AND s.source_type = 'file'
    """

    file_sources = await repo_query(file_sql, {"notebook_id": notebook_id})

    for source in file_sources:
        try:
            # Get file content from sources table (full_text column)
            content = source.get("full_text", "")

            if content:
                # Create FileDataTool with file content
                tool = FileDataTool(
                    source_id=source["id"],
                    file_name=source["title"],
                    content=content[:10000],  # First 10k chars
                    session_id=session_id,
                    name=f"query_{_sanitize_tool_name(source['title'])}"
                )
                tools.append(tool)
                print(f"✅ Created file data tool: {tool.name}")
            else:
                print(f"⚠️ File source {source['id']} has no content (full_text is empty)")

        except Exception as e:
            print(f"⚠️ Failed to create file tool for source {source['id']}: {e}")
            continue

    # ========================================================================
    # PART 3: Add auto-discovered HANA tables from connections
    # ========================================================================
    auto_hana_tools = await _get_hana_connection_level_tools(notebook_id, session_id)
    tools.extend(auto_hana_tools)

    # ========================================================================
    # PART 4: Add auto-discovered API endpoints from connections
    # ========================================================================
    auto_api_tools = await _get_api_connection_level_tools(notebook_id, session_id)
    tools.extend(auto_api_tools)

    # ========================================================================
    # PART 5: Deduplicate tools (prefer explicit sources over auto-discovered)
    # ========================================================================
    tools = _deduplicate_tools(tools)

    print(f"📦 Created {len(tools)} tools for notebook {notebook_id}")
    return tools


async def create_tools_for_sources(
    source_ids: List[str],
    session_id: Optional[str] = None
) -> List[BaseTool]:
    """
    Generate LangChain tools from specific source IDs

    Args:
        source_ids: List of source UUIDs
        session_id: Optional chat session ID for observability

    Returns:
        List of LangChain BaseTool instances (HANA + API + File tools)
    """
    tools = []

    if not source_ids:
        return tools

    # Build placeholders for SQL IN clause
    placeholders = ", ".join([f":id{i}" for i in range(len(source_ids))])
    params = {f"id{i}": source_id for i, source_id in enumerate(source_ids)}

    # Get all specified sources
    sources_sql = f"""
        SELECT id, title, source_type, connection_config, full_text
        FROM sources
        WHERE id IN ({placeholders})
    """

    sources = await repo_query(sources_sql, params)

    for source in sources:
        source_type = source.get("source_type")

        try:
            # HANA table sources
            if source_type == "hana_table":
                config = json.loads(source.get("connection_config", "{}"))
                tool = HANAQueryTool(
                    source_id=source["id"],
                    table_name=config.get("table_name", "table"),
                    connection_config=config,
                    session_id=session_id,
                    name=f"query_{_sanitize_tool_name(config.get('table_name', 'table'))}"
                )
                tools.append(tool)
                print(f"✅ Created HANA tool: {tool.name}")

            # API sources
            elif source_type == "api":
                config = json.loads(source.get("connection_config", "{}"))
                connection_id = config.get("connection_id")

                if connection_id:
                    conn_sql = "SELECT * FROM api_connections WHERE id = :id"
                    conn_results = await repo_query(conn_sql, {"id": connection_id})

                    if conn_results:
                        conn = conn_results[0]
                        tool = APICallTool(
                            source_id=source["id"],
                            endpoint=conn["endpoint"],
                            connection_config=config,
                            session_id=session_id,
                            source_name=source["title"],
                            name=f"call_{_sanitize_tool_name(source['title'])}"
                        )
                        tools.append(tool)
                        print(f"✅ Created API tool: {tool.name}")

            # File sources (Excel, CSV, etc.) - read content
            elif source_type == "file":
                # Get file content from sources table (full_text column)
                content = source.get("full_text", "")

                if content:
                    # Create FileDataTool with file content
                    tool = FileDataTool(
                        source_id=source["id"],
                        file_name=source["title"],
                        content=content[:10000],  # First 10k chars
                        session_id=session_id,
                        name=f"query_{_sanitize_tool_name(source['title'])}"
                    )
                    tools.append(tool)
                    print(f"✅ Created file data tool: {tool.name}")

        except Exception as e:
            print(f"⚠️ Failed to create tool for source {source['id']}: {e}")
            continue

    print(f"📊 Total tools created from sources: {len(tools)}")
    return tools


def _sanitize_tool_name(name: str) -> str:
    """Sanitize name for use in tool names"""
    # Replace spaces and special chars with underscore
    import re
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', name.lower())
    # Remove consecutive underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    return sanitized or "tool"
