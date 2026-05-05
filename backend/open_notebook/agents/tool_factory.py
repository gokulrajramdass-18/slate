"""
Tool Factory - Registers existing and new tools into the central ToolRegistry.

Call ``initialize_tools()`` at application startup to populate the registry
with all built-in tools.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Set

from langchain.tools import BaseTool, tool as langchain_tool
from pydantic import BaseModel, Field

from open_notebook.agents.tool_registry import (
    AgentRole,
    ToolCategory,
    get_tool_registry,
)

logger = logging.getLogger(__name__)

ALL_ROLES: Set[AgentRole] = set(AgentRole)
RESEARCH_ROLES: Set[AgentRole] = {
    AgentRole.RESEARCHER,
    AgentRole.ANALYST,
    AgentRole.PLANNER,
    AgentRole.ADMIN,
}
EXEC_ROLES: Set[AgentRole] = {
    AgentRole.EXECUTOR,
    AgentRole.ADMIN,
}


# ============================================================================
# Utility tool input schemas
# ============================================================================

class NotebookSearchInput(BaseModel):
    """Input for searching within notebooks."""
    query: str = Field(description="Search query string")
    notebook_id: Optional[str] = Field(default=None, description="Limit to a specific notebook")
    strategy: str = Field(default="hybrid", description="Search strategy: keyword, vector, hybrid, agentic_rag")
    limit: int = Field(default=10, ge=1, le=100, description="Max results")


class FileReadInput(BaseModel):
    """Input for reading an uploaded source file."""
    source_id: str = Field(description="UUID of the source to read")
    max_chars: int = Field(default=5000, ge=100, le=50000, description="Maximum characters to return")


class SourceListInput(BaseModel):
    """Input for listing sources in a notebook."""
    notebook_id: str = Field(description="UUID of the notebook")
    source_type: Optional[str] = Field(default=None, description="Filter by type: file, url, text, youtube, hana_table, api")


class DataSummaryInput(BaseModel):
    """Input for summarising tabular data."""
    data: str = Field(description="JSON string of row data (list of dicts)")
    columns: Optional[List[str]] = Field(default=None, description="Columns to include in summary")


# ============================================================================
# Utility tools (new standalone LangChain tools)
# ============================================================================

class NotebookSearchTool(BaseTool):
    """Search across notebook sources using configured strategies."""

    name: str = "notebook_search"
    description: str = (
        "Search across notebook sources using keyword, vector, hybrid, or agentic RAG strategies. "
        "Returns ranked results with relevance scores and highlights."
    )
    args_schema: type = NotebookSearchInput

    async def _arun(self, query: str, notebook_id: Optional[str] = None, strategy: str = "hybrid", limit: int = 10) -> str:
        from open_notebook.search.strategies import SearchFilters
        from api.services.search_service import SearchService
        from open_notebook.database.repository import get_repo_database

        db = await get_repo_database()
        service = SearchService(db)
        strat = await service.get_search_strategy(strategy)

        filters = None
        if notebook_id:
            filters = SearchFilters(notebook_ids=[notebook_id])

        results = await strat.search(query, filters=filters, limit=limit)
        return json.dumps(
            [
                {
                    "source_id": r.source_id,
                    "score": round(r.score, 4),
                    "content": r.content[:500],
                    "highlights": r.highlights[:5],
                    "metadata": r.metadata,
                }
                for r in results
            ],
            default=str,
        )

    def _run(self, **kwargs: Any) -> str:
        raise NotImplementedError("Use async")


class FileReadTool(BaseTool):
    """Read the text content of an uploaded source."""

    name: str = "read_source_file"
    description: str = (
        "Read the extracted text content of an uploaded source by its ID. "
        "Useful for retrieving full document text for analysis."
    )
    args_schema: type = FileReadInput

    async def _arun(self, source_id: str, max_chars: int = 5000) -> str:
        from open_notebook.database.repository import repo_query

        rows = await repo_query(
            "SELECT title, full_text, source_type FROM sources WHERE id = :id",
            {"id": source_id},
        )
        if not rows:
            return json.dumps({"error": f"Source {source_id} not found"})

        row = rows[0]
        text = (row.get("full_text") or "")[:max_chars]
        return json.dumps(
            {
                "source_id": source_id,
                "title": row.get("title", ""),
                "source_type": row.get("source_type", ""),
                "content": text,
                "truncated": len(row.get("full_text") or "") > max_chars,
            },
            default=str,
        )

    def _run(self, **kwargs: Any) -> str:
        raise NotImplementedError("Use async")


class SourceListTool(BaseTool):
    """List sources belonging to a notebook."""

    name: str = "list_notebook_sources"
    description: str = (
        "List all sources in a notebook. Optionally filter by source type "
        "(file, url, text, youtube, hana_table, api)."
    )
    args_schema: type = SourceListInput

    async def _arun(self, notebook_id: str, source_type: Optional[str] = None) -> str:
        from open_notebook.database.repository import repo_query

        sql = """
            SELECT s.id, s.title, s.source_type, s.created
            FROM sources s
            JOIN notebook_source ns ON s.id = ns.source_id
            WHERE ns.notebook_id = :notebook_id
        """
        params: Dict[str, Any] = {"notebook_id": notebook_id}

        if source_type:
            sql += " AND s.source_type = :source_type"
            params["source_type"] = source_type

        sql += " ORDER BY s.created DESC"
        rows = await repo_query(sql, params)

        return json.dumps(
            [
                {
                    "id": r["id"],
                    "title": r.get("title", ""),
                    "source_type": r.get("source_type", ""),
                    "created": r.get("created", ""),
                }
                for r in rows
            ],
            default=str,
        )

    def _run(self, **kwargs: Any) -> str:
        raise NotImplementedError("Use async")


class DataSummaryTool(BaseTool):
    """Produce descriptive statistics for tabular JSON data."""

    name: str = "summarize_data"
    description: str = (
        "Given tabular data as a JSON string (list of dicts), return descriptive "
        "statistics: row count, column types, min/max/mean for numerics."
    )
    args_schema: type = DataSummaryInput

    async def _arun(self, data: str, columns: Optional[List[str]] = None) -> str:
        rows = json.loads(data)
        if not rows:
            return json.dumps({"error": "No data provided"})

        all_cols = list(rows[0].keys())
        cols = columns or all_cols

        summary: Dict[str, Any] = {"row_count": len(rows), "columns": {}}
        for col in cols:
            values = [r.get(col) for r in rows if r.get(col) is not None]
            numerics = [v for v in values if isinstance(v, (int, float))]
            col_info: Dict[str, Any] = {
                "non_null_count": len(values),
                "type": "numeric" if numerics else "text",
            }
            if numerics:
                col_info["min"] = min(numerics)
                col_info["max"] = max(numerics)
                col_info["mean"] = round(sum(numerics) / len(numerics), 4)
            else:
                unique = set(str(v) for v in values)
                col_info["unique_count"] = len(unique)
                if len(unique) <= 10:
                    col_info["sample_values"] = sorted(unique)[:10]
            summary["columns"][col] = col_info

        return json.dumps(summary, default=str)

    def _run(self, **kwargs: Any) -> str:
        raise NotImplementedError("Use async")


# ============================================================================
# Registration helpers
# ============================================================================

def _register_search_tools() -> int:
    """Register search-strategy tools."""
    registry = get_tool_registry()
    count = 0

    search_tool = NotebookSearchTool()
    registry.register_langchain_tool(
        search_tool,
        category=ToolCategory.SEARCH,
        allowed_roles=RESEARCH_ROLES | {AgentRole.WRITER},
        tags=["search", "rag", "hybrid", "keyword", "vector"],
    )
    count += 1
    return count


def _register_file_tools() -> int:
    """Register file operation tools."""
    registry = get_tool_registry()
    count = 0

    registry.register_langchain_tool(
        FileReadTool(),
        category=ToolCategory.FILE_OPS,
        allowed_roles=ALL_ROLES,
        tags=["file", "read", "source", "document"],
    )
    count += 1

    registry.register_langchain_tool(
        SourceListTool(),
        category=ToolCategory.FILE_OPS,
        allowed_roles=ALL_ROLES,
        tags=["list", "sources", "notebook"],
    )
    count += 1
    return count


def _register_database_tools() -> int:
    """Register database/HANA tools from data_query_tools."""
    registry = get_tool_registry()
    count = 0

    try:
        from api.services.data_query_tools import HANAQueryTool, APICallTool

        # Register the HANA tool class as a factory-style entry.
        # Actual instances are created per-notebook via create_tools_for_notebook,
        # but we register a prototype so the registry knows about the capability.
        registry.register(
            name="query_hana_table",
            tool=HANAQueryTool,
            description=(
                "Query HANA database tables with column selection, filtering, "
                "grouping, and ordering. Returns JSON results."
            ),
            category=ToolCategory.DATABASE,
            allowed_roles={AgentRole.ANALYST, AgentRole.RESEARCHER, AgentRole.EXECUTOR, AgentRole.ADMIN},
            is_async=True,
            tags=["hana", "database", "sql", "query"],
            input_schema={"ref": "HANAQueryInput"},
        )
        count += 1

        registry.register(
            name="call_api",
            tool=APICallTool,
            description=(
                "Call external REST APIs with parameters and filters. "
                "Supports OAuth 2.0 and Bearer token authentication."
            ),
            category=ToolCategory.API,
            allowed_roles={AgentRole.ANALYST, AgentRole.RESEARCHER, AgentRole.EXECUTOR, AgentRole.ADMIN},
            is_async=True,
            tags=["api", "rest", "http", "oauth"],
            input_schema={"ref": "APICallInput"},
        )
        count += 1
    except ImportError:
        logger.warning("data_query_tools not available; HANA/API tools not registered")

    return count


def _register_analysis_tools() -> int:
    """Register data analysis tools."""
    registry = get_tool_registry()
    count = 0

    registry.register_langchain_tool(
        DataSummaryTool(),
        category=ToolCategory.ANALYSIS,
        allowed_roles={AgentRole.ANALYST, AgentRole.RESEARCHER, AgentRole.ADMIN},
        tags=["analysis", "statistics", "summary", "data"],
    )
    count += 1

    # Register chart tool
    try:
        from api.services.tools.chart_tool import ChartTool

        registry.register(
            name="create_chart",
            tool=ChartTool,
            description=(
                "Create charts (line, bar, pie, scatter, area, radar) from tabular data "
                "with auto-detection of chart type and axis configuration."
            ),
            category=ToolCategory.ANALYSIS,
            allowed_roles={AgentRole.ANALYST, AgentRole.WRITER, AgentRole.ADMIN},
            is_async=True,
            tags=["chart", "visualization", "graph", "plot"],
        )
        count += 1
    except ImportError:
        logger.warning("chart_tool not available; chart tool not registered")

    return count


def _register_web_tools() -> int:
    """Register web search / fetch tools."""
    registry = get_tool_registry()
    count = 0

    # Try to import and register DuckDuckGo search
    try:
        from langchain_community.tools import DuckDuckGoSearchRun

        # Create DuckDuckGo search tool
        ddg_tool = DuckDuckGoSearchRun(
            name="web_search",
            description="Search the web using DuckDuckGo for current information, news, and research. Returns relevant results with summaries."
        )

        registry.register(
            name="web_search",
            tool=ddg_tool,
            description="Search the web using DuckDuckGo for current information, news, and research. Returns relevant results with summaries.",
            category=ToolCategory.WEB,
            allowed_roles={AgentRole.RESEARCHER, AgentRole.ADMIN},
            is_async=True,
            tags=["web", "search", "internet", "duckduckgo"],
        )
        count += 1
        logger.info("DuckDuckGo web search tool registered successfully")
    except ImportError as e:
        logger.warning(f"DuckDuckGo search not available: {e}")
        # Register placeholder
        registry.register(
            name="web_search",
            tool=None,
            description="Web search (DuckDuckGo not installed - run: pip install duckduckgo-search).",
            category=ToolCategory.WEB,
            allowed_roles={AgentRole.RESEARCHER, AgentRole.ADMIN},
            is_async=True,
            tags=["web", "search", "disabled"],
        )
        count += 1

    return count


# ============================================================================
# Public API
# ============================================================================

def initialize_tools() -> Dict[str, int]:
    """
    Initialize the tool registry with all built-in tools.

    Returns a dict mapping category to number of tools registered.
    Call this once at application startup.
    """
    results: Dict[str, int] = {}
    results["search"] = _register_search_tools()
    results["file_ops"] = _register_file_tools()
    results["database"] = _register_database_tools()
    results["analysis"] = _register_analysis_tools()
    results["web"] = _register_web_tools()

    registry = get_tool_registry()
    total = registry.tool_count
    logger.info(f"Tool registry initialized with {total} tools: {results}")
    return results


def get_tools_for_agent(role: AgentRole, categories: Optional[List[ToolCategory]] = None) -> List[Any]:
    """
    Convenience: get a flat list of tool objects for an agent with a given role.

    Args:
        role: The agent's role.
        categories: Optional category filter.

    Returns:
        List of tool objects (LangChain BaseTool instances or classes).
    """
    registry = get_tool_registry()
    if categories:
        tools: Dict[str, Any] = {}
        for cat in categories:
            tools.update(registry.get_tools_for_role_and_category(role, cat))
        return list(tools.values())
    return list(registry.get_tools_for_role(role).values())
