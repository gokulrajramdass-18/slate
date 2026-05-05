"""
Agent Tools API Router

Tool discovery endpoints for the multi-agent system.
Provides read-only views of tools available to agents, with role-based filtering.
"""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.models import (
    AgentToolInfo,
    AgentToolListResponse,
    ErrorResponse,
)
from open_notebook.database.repository import repo_query


router = APIRouter(
    prefix="/api/agents/tools",
    tags=["agent-tools"],
    responses={404: {"model": ErrorResponse}},
)


# ============================================================================
# Role-to-Tool Mapping
# ============================================================================

# Default mapping of agent roles to recommended tool categories/types.
# This is a soft recommendation; agents can still use any enabled tool.
ROLE_TOOL_MAP = {
    "planner": ["data_query", "web", "computation"],
    "researcher": ["data_query", "web", "file_analysis"],
    "analyst": ["data_query", "computation", "file_analysis"],
    "writer": ["web", "computation"],
    "reviewer": ["web", "computation"],
    "synthesizer": ["data_query", "web", "computation"],
    "query_specialist": ["data_query"],
    "custom": [],
}


def _parse_json(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None
    return value


def _row_to_agent_tool_info(row: dict) -> AgentToolInfo:
    """Convert a tool registry row to AgentToolInfo."""
    category = row.get("category")

    # Determine which roles this tool is recommended for
    roles = []
    for role, categories in ROLE_TOOL_MAP.items():
        if category in categories:
            roles.append(role)

    return AgentToolInfo(
        id=row["id"],
        name=row["name"],
        tool_type=row["tool_type"],
        category=category,
        description=row.get("description"),
        enabled=bool(row.get("enabled", True)),
        roles=roles,
    )


# ============================================================================
# Tool Discovery Endpoints
# ============================================================================

@router.get("/", response_model=AgentToolListResponse)
async def list_agent_tools(
    enabled_only: bool = Query(True, description="Only return enabled tools"),
    category: Optional[str] = Query(None, description="Filter by tool category"),
):
    """
    List all tools available to agents.

    Returns tools from the registry with role recommendations attached.

    Example:
        GET /api/agents/tools?category=data_query
    """
    sql = "SELECT * FROM tool_registry WHERE 1=1"
    params: dict = {}

    if enabled_only:
        sql += " AND enabled = 1"

    if category:
        sql += " AND category = :category"
        params["category"] = category

    sql += " ORDER BY name ASC"

    rows = await repo_query(sql, params)
    tools = [_row_to_agent_tool_info(r) for r in rows]

    return AgentToolListResponse(tools=tools, total=len(tools))


@router.get("/role/{role}", response_model=AgentToolListResponse)
async def list_tools_for_role(role: str):
    """
    List tools recommended for a specific agent role.

    Uses the role-to-category mapping to find relevant tools.
    Only returns enabled tools.

    Example:
        GET /api/agents/tools/role/researcher
    """
    categories = ROLE_TOOL_MAP.get(role)
    if categories is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown role: {role}. Valid roles: {list(ROLE_TOOL_MAP.keys())}",
        )

    if not categories:
        # Custom role or role with no default categories - return all enabled
        rows = await repo_query(
            "SELECT * FROM tool_registry WHERE enabled = 1 ORDER BY name ASC",
        )
    else:
        # Build IN clause for categories
        placeholders = ", ".join(f":cat_{i}" for i in range(len(categories)))
        params = {f"cat_{i}": cat for i, cat in enumerate(categories)}

        rows = await repo_query(
            f"SELECT * FROM tool_registry WHERE enabled = 1 AND category IN ({placeholders}) ORDER BY name ASC",
            params,
        )

    tools = [_row_to_agent_tool_info(r) for r in rows]
    return AgentToolListResponse(tools=tools, total=len(tools))
