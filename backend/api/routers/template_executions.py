"""
Template Executions Endpoint

Standalone endpoint for listing all workflow template executions for a user
"""

from fastapi import APIRouter, Header, Query
from open_notebook.database.repository import repo_query

router = APIRouter(prefix="/api/template-executions", tags=["Template Executions"])


@router.get("")
async def list_user_template_executions(
    user_id: str = Header(..., alias="X-User-ID"),
    status_filter: str = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100)
):
    """
    List all workflow template executions for a user.

    Returns executions across all templates with workflow and execution details.
    """
    query = """
        SELECT
            wte.id,
            wte.template_id,
            wte.template_name,
            wte.workflow_id,
            wte.execution_id,
            wte.parameters,
            wte.status,
            wte.trigger_type,
            wte.schedule_type,
            wte.started_at,
            wte.completed_at,
            wte.duration_ms,
            wte.created_at,
            we.status as execution_status
        FROM workflow_template_executions wte
        LEFT JOIN workflow_executions we ON wte.execution_id = we.id
        WHERE wte.user_id = :user_id
    """

    params = {"user_id": user_id, "limit": limit}

    if status_filter:
        query += " AND wte.status = :status"
        params["status"] = status_filter

    query += " ORDER BY wte.created_at DESC LIMIT :limit"

    rows = await repo_query(query, params)

    return [dict(row) for row in rows]
