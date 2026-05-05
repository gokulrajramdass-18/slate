"""
Tool Management API Router

CRUD endpoints for the tool registry, permissions, and usage analytics.
"""

import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse

from api.models import (
    ToolRegistryCreate,
    ToolRegistryUpdate,
    ToolRegistryResponse,
    ToolRegistryListResponse,
    ToolPermissionCreate,
    ToolPermissionUpdate,
    ToolPermissionResponse,
    ToolPermissionListResponse,
    ToolUsageResponse,
    ToolUsageStat,
    ToolUsageReportResponse,
    ToolUsageReportEntry,
    SuccessResponse,
)
from open_notebook.database.repository import repo_query, repo_create, repo_update, repo_delete, repo_execute


router = APIRouter(prefix="/api/tools", tags=["tools"])


# ============================================================================
# Simplified Tool Listing for Resource Discovery
# ============================================================================

@router.get("/registry")
async def list_registry_tools_simple():
    """
    List enabled tools from the tool registry for resource selection.

    Returns simplified tool info for use in guided workspace creation modal.
    """
    sql = """
        SELECT id, name, tool_type, category, description
        FROM tool_registry
        WHERE enabled = 1
        ORDER BY name ASC
    """
    rows = await repo_query(sql, {})

    tools = [
        {
            "id": row["id"],
            "name": row["name"],
            "tool_type": row["tool_type"],
            "category": row.get("category", ""),
            "description": row.get("description", ""),
            "source": "registry",
        }
        for row in rows
    ]
    return {"tools": tools}


@router.get("/mcp")
async def list_mcp_tools_simple():
    """
    List tools from connected MCP servers for resource selection.

    Returns simplified tool info for use in guided workspace creation modal.
    """
    try:
        sql = """
            SELECT t.id, t.tool_name as name, t.description,
                   s.name AS server_name, s.status AS server_status
            FROM mcp_tools t
            JOIN mcp_servers s ON t.server_id = s.id
            WHERE s.status = 'connected'
            ORDER BY t.tool_name ASC
        """
        rows = await repo_query(sql, {})

        tools = [
            {
                "id": row["id"],
                "name": row["name"],
                "tool_type": "mcp",
                "description": row.get("description", ""),
                "server_name": row.get("server_name", ""),
                "source": "mcp",
            }
            for row in rows
        ]
        return {"tools": tools}
    except Exception:
        # Return empty if MCP tables don't exist yet
        return {"tools": []}


# ============================================================================
# Helper Functions
# ============================================================================

async def _get_tool_or_404(tool_id: str) -> dict:
    """Fetch a tool by ID or raise 404."""
    sql = "SELECT * FROM tool_registry WHERE id = :id"
    rows = await repo_query(sql, {"id": tool_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Tool not found")
    return rows[0]


def _parse_json_field(value) -> Optional[dict]:
    """Parse a JSON string field if needed."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None
    return value


def _row_to_tool_response(row: dict) -> ToolRegistryResponse:
    """Convert a DB row to ToolRegistryResponse."""
    return ToolRegistryResponse(
        id=row["id"],
        name=row["name"],
        tool_type=row["tool_type"],
        category=row.get("category"),
        description=row.get("description"),
        enabled=bool(row.get("enabled", True)),
        default_config=_parse_json_field(row.get("default_config")),
        metadata=_parse_json_field(row.get("metadata")),
        created=row.get("created"),
        updated=row.get("updated"),
    )


# ============================================================================
# Tool CRUD Endpoints
# ============================================================================

@router.get("/", response_model=ToolRegistryListResponse)
async def list_tools(
    category: Optional[str] = Query(None, description="Filter by category"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    tool_type: Optional[str] = Query(None, description="Filter by tool type"),
):
    """List all tools in the registry."""
    sql = "SELECT * FROM tool_registry WHERE 1=1"
    params: dict = {}

    if category:
        sql += " AND category = :category"
        params["category"] = category

    if enabled is not None:
        sql += " AND enabled = :enabled"
        params["enabled"] = 1 if enabled else 0

    if tool_type:
        sql += " AND tool_type = :tool_type"
        params["tool_type"] = tool_type

    sql += " ORDER BY name ASC"

    rows = await repo_query(sql, params)
    tools = [_row_to_tool_response(r) for r in rows]
    return ToolRegistryListResponse(tools=tools, total=len(tools))


@router.get("/{tool_id}", response_model=ToolRegistryResponse)
async def get_tool(tool_id: str):
    """Get a single tool by ID."""
    row = await _get_tool_or_404(tool_id)
    return _row_to_tool_response(row)


@router.post("/", response_model=ToolRegistryResponse, status_code=status.HTTP_201_CREATED)
async def create_tool(body: ToolRegistryCreate):
    """Register a new tool."""
    # Check uniqueness
    existing = await repo_query(
        "SELECT id FROM tool_registry WHERE name = :name",
        {"name": body.name},
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tool with name '{body.name}' already exists",
        )

    now = datetime.utcnow().isoformat()
    tool_id = str(uuid.uuid4())
    data = {
        "id": tool_id,
        "name": body.name,
        "tool_type": body.tool_type.value,
        "category": body.category.value if body.category else None,
        "description": body.description,
        "enabled": 1 if body.enabled else 0,
        "default_config": json.dumps(body.default_config) if body.default_config else None,
        "metadata": json.dumps(body.metadata) if body.metadata else None,
        "created": now,
        "updated": now,
    }

    await repo_execute(
        """INSERT INTO tool_registry (id, name, tool_type, category, description, enabled, default_config, metadata, created, updated)
           VALUES (:id, :name, :tool_type, :category, :description, :enabled, :default_config, :metadata, :created, :updated)""",
        data,
    )

    return ToolRegistryResponse(**{
        **data,
        "enabled": body.enabled,
        "default_config": body.default_config,
        "metadata": body.metadata,
    })


@router.put("/{tool_id}", response_model=ToolRegistryResponse)
async def update_tool(tool_id: str, body: ToolRegistryUpdate):
    """Update a tool."""
    await _get_tool_or_404(tool_id)

    update_data: dict = {}
    if body.name is not None:
        update_data["name"] = body.name
    if body.description is not None:
        update_data["description"] = body.description
    if body.enabled is not None:
        update_data["enabled"] = 1 if body.enabled else 0
    if body.category is not None:
        update_data["category"] = body.category.value
    if body.default_config is not None:
        update_data["default_config"] = json.dumps(body.default_config)
    if body.metadata is not None:
        update_data["metadata"] = json.dumps(body.metadata)

    if update_data:
        update_data["updated"] = datetime.utcnow().isoformat()
        await repo_update("tool_registry", tool_id, update_data)

    # Return refreshed record
    row = await _get_tool_or_404(tool_id)
    return _row_to_tool_response(row)


@router.delete("/{tool_id}", response_model=SuccessResponse)
async def delete_tool(tool_id: str):
    """Delete a tool and its permissions."""
    await _get_tool_or_404(tool_id)

    # Delete permissions first (cascade may not be set up)
    await repo_execute(
        "DELETE FROM tool_permissions WHERE tool_id = :tool_id",
        {"tool_id": tool_id},
    )
    await repo_delete("tool_registry", tool_id)

    return SuccessResponse(message=f"Tool {tool_id} deleted")


@router.post("/{tool_id}/toggle", response_model=SuccessResponse)
async def toggle_tool(tool_id: str, enabled: bool = Query(...)):
    """Enable or disable a tool."""
    await _get_tool_or_404(tool_id)
    await repo_update("tool_registry", tool_id, {
        "enabled": 1 if enabled else 0,
        "updated": datetime.utcnow().isoformat(),
    })
    state = "enabled" if enabled else "disabled"
    return SuccessResponse(message=f"Tool {state}")


# ============================================================================
# Permission Endpoints
# ============================================================================

@router.get("/{tool_id}/permissions", response_model=ToolPermissionListResponse)
async def list_permissions(tool_id: str):
    """List permissions for a tool."""
    await _get_tool_or_404(tool_id)

    sql = "SELECT * FROM tool_permissions WHERE tool_id = :tool_id ORDER BY created DESC"
    rows = await repo_query(sql, {"tool_id": tool_id})

    perms = [
        ToolPermissionResponse(
            id=r["id"],
            tool_id=r["tool_id"],
            user_id=r.get("user_id"),
            role=r.get("role"),
            allowed=bool(r.get("allowed", True)),
            rate_limit=r.get("rate_limit"),
            custom_config=_parse_json_field(r.get("custom_config")),
            created=r.get("created"),
        )
        for r in rows
    ]
    return ToolPermissionListResponse(permissions=perms)


@router.post("/{tool_id}/permissions", response_model=ToolPermissionResponse, status_code=status.HTTP_201_CREATED)
async def create_permission(tool_id: str, body: ToolPermissionCreate):
    """Add a permission rule for a tool."""
    await _get_tool_or_404(tool_id)

    now = datetime.utcnow().isoformat()
    perm_id = str(uuid.uuid4())
    data = {
        "id": perm_id,
        "tool_id": tool_id,
        "user_id": body.user_id,
        "role": body.role,
        "allowed": 1 if body.allowed else 0,
        "rate_limit": body.rate_limit,
        "custom_config": json.dumps(body.custom_config) if body.custom_config else None,
        "created": now,
    }

    await repo_execute(
        """INSERT INTO tool_permissions (id, tool_id, user_id, role, allowed, rate_limit, custom_config, created)
           VALUES (:id, :tool_id, :user_id, :role, :allowed, :rate_limit, :custom_config, :created)""",
        data,
    )

    return ToolPermissionResponse(
        id=perm_id,
        tool_id=tool_id,
        user_id=body.user_id,
        role=body.role,
        allowed=body.allowed,
        rate_limit=body.rate_limit,
        custom_config=body.custom_config,
        created=now,
    )


@router.put("/permissions/{perm_id}", response_model=SuccessResponse)
async def update_permission(perm_id: str, body: ToolPermissionUpdate):
    """Update a permission rule."""
    rows = await repo_query("SELECT id FROM tool_permissions WHERE id = :id", {"id": perm_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Permission not found")

    update_data: dict = {}
    if body.allowed is not None:
        update_data["allowed"] = 1 if body.allowed else 0
    if body.rate_limit is not None:
        update_data["rate_limit"] = body.rate_limit
    if body.custom_config is not None:
        update_data["custom_config"] = json.dumps(body.custom_config)

    if update_data:
        await repo_update("tool_permissions", perm_id, update_data)

    return SuccessResponse(message="Permission updated")


@router.delete("/permissions/{perm_id}", response_model=SuccessResponse)
async def delete_permission(perm_id: str):
    """Remove a permission rule."""
    rows = await repo_query("SELECT id FROM tool_permissions WHERE id = :id", {"id": perm_id})
    if not rows:
        raise HTTPException(status_code=404, detail="Permission not found")

    await repo_delete("tool_permissions", perm_id)
    return SuccessResponse(message="Permission deleted")


# ============================================================================
# Usage Analytics Endpoints
# ============================================================================

@router.get("/{tool_id}/usage", response_model=ToolUsageResponse)
async def get_tool_usage(
    tool_id: str,
    days: int = Query(7, ge=1, le=90, description="Number of days to look back"),
):
    """Get usage statistics for a specific tool."""
    await _get_tool_or_404(tool_id)

    sql = """
        SELECT
            DATE(created) as date,
            COUNT(*) as total_calls,
            AVG(execution_time_ms) as avg_duration,
            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_calls,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_calls
        FROM tool_usage_log
        WHERE tool_id = :tool_id
        AND created >= DATE('now', '-' || :days || ' days')
        GROUP BY DATE(created)
        ORDER BY date DESC
    """
    rows = await repo_query(sql, {"tool_id": tool_id, "days": days})

    stats = [
        ToolUsageStat(
            date=r["date"],
            total_calls=r["total_calls"],
            avg_duration=r.get("avg_duration"),
            successful_calls=r.get("successful_calls", 0),
            failed_calls=r.get("failed_calls", 0),
        )
        for r in rows
    ]
    return ToolUsageResponse(tool_id=tool_id, usage=stats)


@router.get("/usage/report", response_model=ToolUsageReportResponse)
async def get_usage_report(
    days: int = Query(7, ge=1, le=90, description="Number of days to look back"),
):
    """Get overall tool usage report across all tools."""
    sql = """
        SELECT
            t.name,
            t.category,
            COUNT(l.id) as total_calls,
            AVG(l.execution_time_ms) as avg_duration,
            COUNT(DISTINCT l.user_id) as unique_users
        FROM tool_registry t
        LEFT JOIN tool_usage_log l ON t.id = l.tool_id
            AND l.created >= DATE('now', '-' || :days || ' days')
        GROUP BY t.id, t.name, t.category
        ORDER BY total_calls DESC
    """
    rows = await repo_query(sql, {"days": days})

    report = [
        ToolUsageReportEntry(
            name=r["name"],
            category=r.get("category"),
            total_calls=r.get("total_calls", 0),
            avg_duration=r.get("avg_duration"),
            unique_users=r.get("unique_users", 0),
        )
        for r in rows
    ]
    return ToolUsageReportResponse(report=report)
