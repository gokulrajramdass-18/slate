"""
Orchestration Schedules API Router

Endpoints for creating and managing orchestration schedules with template support.
"""

import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Header, status
from pydantic import BaseModel, Field, field_validator

from open_notebook.database.repository import repo_query, repo_create, repo_execute, repo_update
from api.services.orchestration_scheduler import get_orchestration_scheduler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orchestration-schedules", tags=["Orchestration Schedules"])


# ============================================================================
# Request/Response Models
# ============================================================================

class ScheduleCreateRequest(BaseModel):
    """Request to create orchestration schedule."""
    # Mode 1: Goal-based (existing)
    goal: Optional[str] = Field(None, min_length=10, max_length=2000)

    # Mode 2: Template-based (new)
    template_id: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict)

    # Common fields
    notebook_id: Optional[str] = None
    resources: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = Field(default_factory=dict)

    # Schedule configuration
    schedule_type: str = Field(..., description="'once' or 'recurring'")
    schedule_config: Dict[str, Any] = Field(..., description="{datetime} for once, {cron} for recurring")

    @field_validator("schedule_type")
    def validate_schedule_type(cls, v):
        if v not in ["once", "recurring"]:
            raise ValueError("schedule_type must be 'once' or 'recurring'")
        return v

    def model_post_init(self, __context):
        """Validate that either goal XOR template_id is provided."""
        has_goal = self.goal is not None
        has_template = self.template_id is not None

        if has_goal == has_template:  # Both or neither
            raise ValueError("Must provide either 'goal' OR 'template_id', not both or neither")


class ScheduleUpdateRequest(BaseModel):
    """Request to update schedule."""
    goal: Optional[str] = None
    template_id: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    notebook_id: Optional[str] = None
    resources: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    schedule_type: Optional[str] = None
    schedule_config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class ScheduleResponse(BaseModel):
    """Schedule response."""
    id: str
    user_id: str
    goal: Optional[str]
    template_id: Optional[str]
    template_name: Optional[str]
    parameters: Optional[Dict[str, Any]]
    notebook_id: Optional[str]
    schedule_type: str
    schedule_config: Dict[str, Any]
    next_run: Optional[str]
    last_run: Optional[str]
    status: str
    execution_count: int
    created_at: str
    updated_at: str


# ============================================================================
# Helper Functions
# ============================================================================

async def schedule_to_response(schedule_dict: dict) -> ScheduleResponse:
    """Convert schedule dict to response model."""
    # Parse JSON fields
    parameters = json.loads(schedule_dict.get("parameters") or "{}")
    schedule_config = json.loads(schedule_dict.get("schedule_config") or "{}")

    # Get template name if template_id exists
    template_name = None
    if schedule_dict.get("template_id"):
        from open_notebook.domain.workspace_template import WorkspaceTemplate
        template = await WorkspaceTemplate.get(schedule_dict["template_id"])
        if template:
            template_name = template.name

    return ScheduleResponse(
        id=schedule_dict["id"],
        user_id=schedule_dict["user_id"],
        goal=schedule_dict.get("goal"),
        template_id=schedule_dict.get("template_id"),
        template_name=template_name,
        parameters=parameters if parameters else None,
        notebook_id=schedule_dict.get("notebook_id"),
        schedule_type=schedule_dict["schedule_type"],
        schedule_config=schedule_config,
        next_run=schedule_dict.get("next_run"),
        last_run=schedule_dict.get("last_run"),
        status=schedule_dict["status"],
        execution_count=schedule_dict.get("execution_count", 0),
        created_at=schedule_dict["created_at"],
        updated_at=schedule_dict["updated_at"],
    )


# ============================================================================
# Endpoints
# ============================================================================

@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    request: ScheduleCreateRequest,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """
    Create orchestration schedule.

    Supports two modes:
    1. **Goal-based**: Provide `goal` for autonomous orchestration
    2. **Template-based**: Provide `template_id` + `parameters` for template instantiation

    Schedule types:
    - **once**: Execute at specific datetime (`schedule_config: {datetime: "2026-04-23T10:00:00Z"}`)
    - **recurring**: Execute on cron schedule (`schedule_config: {cron: "0 9 * * *"}`)
    """
    try:
        import uuid

        schedule_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        # Prepare schedule data
        schedule_data = {
            "id": schedule_id,
            "user_id": x_user_id,
            "goal": request.goal,
            "template_id": request.template_id,
            "parameters": json.dumps(request.parameters) if request.parameters else None,
            "notebook_id": request.notebook_id,
            "resources": json.dumps(request.resources) if request.resources else None,
            "config": json.dumps(request.config) if request.config else None,
            "schedule_type": request.schedule_type,
            "schedule_config": json.dumps(request.schedule_config),
            "status": "active",
            "execution_count": 0,
            "created_at": now,
            "updated_at": now,
        }

        # Insert into database
        await repo_create("orchestration_schedules", schedule_data)

        logger.info(f"Created schedule {schedule_id} (type: {request.schedule_type}, template: {request.template_id})")

        # Add to scheduler
        scheduler = await get_orchestration_scheduler()
        await scheduler.add_schedule(schedule_data)

        # Return response
        schedule_dict = await repo_query(
            "SELECT * FROM orchestration_schedules WHERE id = :id",
            {"id": schedule_id},
            fetch_one=True
        )

        return await schedule_to_response(dict(schedule_dict))

    except Exception as e:
        logger.error(f"Failed to create schedule: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("", response_model=List[ScheduleResponse])
async def list_schedules(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    template_id: Optional[str] = Query(None, description="Filter by template"),
    limit: int = Query(50, ge=1, le=100),
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """List user's orchestration schedules."""
    try:
        where_clauses = ["user_id = :user_id"]
        params = {"user_id": x_user_id, "limit": limit}

        if status_filter:
            where_clauses.append("status = :status")
            params["status"] = status_filter

        if template_id:
            where_clauses.append("template_id = :template_id")
            params["template_id"] = template_id

        where_sql = " AND ".join(where_clauses)

        sql = f"""
            SELECT * FROM orchestration_schedules
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT :limit
        """

        results = await repo_query(sql, params)

        schedules = []
        for row in results:
            schedules.append(await schedule_to_response(dict(row)))

        return schedules

    except Exception as e:
        logger.error(f"Failed to list schedules: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: str,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """Get schedule details."""
    try:
        sql = """
            SELECT * FROM orchestration_schedules
            WHERE id = :id AND user_id = :user_id
        """

        result = await repo_query(sql, {"id": schedule_id, "user_id": x_user_id}, fetch_one=True)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schedule {schedule_id} not found"
            )

        return await schedule_to_response(dict(result))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get schedule: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: str,
    request: ScheduleUpdateRequest,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """Update schedule."""
    try:
        # Check existence and ownership
        existing = await repo_query(
            "SELECT * FROM orchestration_schedules WHERE id = :id AND user_id = :user_id",
            {"id": schedule_id, "user_id": x_user_id},
            fetch_one=True
        )

        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schedule {schedule_id} not found"
            )

        # Build update data
        update_data = {"updated_at": datetime.utcnow().isoformat()}

        if request.goal is not None:
            update_data["goal"] = request.goal
        if request.template_id is not None:
            update_data["template_id"] = request.template_id
        if request.parameters is not None:
            update_data["parameters"] = json.dumps(request.parameters)
        if request.notebook_id is not None:
            update_data["notebook_id"] = request.notebook_id
        if request.resources is not None:
            update_data["resources"] = json.dumps(request.resources)
        if request.config is not None:
            update_data["config"] = json.dumps(request.config)
        if request.schedule_type is not None:
            update_data["schedule_type"] = request.schedule_type
        if request.schedule_config is not None:
            update_data["schedule_config"] = json.dumps(request.schedule_config)
        if request.status is not None:
            update_data["status"] = request.status

        await repo_update("orchestration_schedules", schedule_id, update_data)

        logger.info(f"Updated schedule {schedule_id}")

        # Reload and return
        result = await repo_query(
            "SELECT * FROM orchestration_schedules WHERE id = :id",
            {"id": schedule_id},
            fetch_one=True
        )

        return await schedule_to_response(dict(result))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update schedule: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: str,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """Delete schedule."""
    try:
        # Check existence and ownership
        existing = await repo_query(
            "SELECT * FROM orchestration_schedules WHERE id = :id AND user_id = :user_id",
            {"id": schedule_id, "user_id": x_user_id},
            fetch_one=True
        )

        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schedule {schedule_id} not found"
            )

        # Remove from scheduler
        scheduler = await get_orchestration_scheduler()
        await scheduler.remove_schedule(schedule_id)

        # Delete from database
        await repo_execute(
            "DELETE FROM orchestration_schedules WHERE id = :id",
            {"id": schedule_id}
        )

        logger.info(f"Deleted schedule {schedule_id}")

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete schedule: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{schedule_id}/pause", response_model=ScheduleResponse)
async def pause_schedule(
    schedule_id: str,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """Pause schedule."""
    try:
        # Check existence and ownership
        existing = await repo_query(
            "SELECT * FROM orchestration_schedules WHERE id = :id AND user_id = :user_id",
            {"id": schedule_id, "user_id": x_user_id},
            fetch_one=True
        )

        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schedule {schedule_id} not found"
            )

        # Pause in scheduler
        scheduler = await get_orchestration_scheduler()
        await scheduler.pause_schedule(schedule_id)

        logger.info(f"Paused schedule {schedule_id}")

        # Return updated schedule
        result = await repo_query(
            "SELECT * FROM orchestration_schedules WHERE id = :id",
            {"id": schedule_id},
            fetch_one=True
        )

        return await schedule_to_response(dict(result))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to pause schedule: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{schedule_id}/resume", response_model=ScheduleResponse)
async def resume_schedule(
    schedule_id: str,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """Resume paused schedule."""
    try:
        # Check existence and ownership
        existing = await repo_query(
            "SELECT * FROM orchestration_schedules WHERE id = :id AND user_id = :user_id",
            {"id": schedule_id, "user_id": x_user_id},
            fetch_one=True
        )

        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schedule {schedule_id} not found"
            )

        # Resume in scheduler
        scheduler = await get_orchestration_scheduler()
        await scheduler.resume_schedule(schedule_id)

        logger.info(f"Resumed schedule {schedule_id}")

        # Return updated schedule
        result = await repo_query(
            "SELECT * FROM orchestration_schedules WHERE id = :id",
            {"id": schedule_id},
            fetch_one=True
        )

        return await schedule_to_response(dict(result))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume schedule: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{schedule_id}/executions", response_model=List[dict])
async def get_schedule_executions(
    schedule_id: str,
    limit: int = Query(50, ge=1, le=100),
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """Get execution history for schedule."""
    try:
        # Check ownership
        existing = await repo_query(
            "SELECT * FROM orchestration_schedules WHERE id = :id AND user_id = :user_id",
            {"id": schedule_id, "user_id": x_user_id},
            fetch_one=True
        )

        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schedule {schedule_id} not found"
            )

        # Get orchestrations for this schedule
        sql = """
            SELECT o.*, n.name as workspace_name
            FROM orchestrations o
            LEFT JOIN notebooks n ON o.workspace_instance_id = n.id
            WHERE o.schedule_id = :schedule_id
            ORDER BY o.created_at DESC
            LIMIT :limit
        """

        results = await repo_query(sql, {"schedule_id": schedule_id, "limit": limit})

        executions = []
        for row in results:
            row_dict = dict(row)
            executions.append({
                "orchestration_id": row_dict["id"],
                "workspace_instance_id": row_dict.get("workspace_instance_id"),
                "workspace_name": row_dict.get("workspace_name"),
                "template_id": row_dict.get("template_id"),
                "status": row_dict["status"],
                "created_at": row_dict["created_at"],
                "updated_at": row_dict["updated_at"],
            })

        return executions

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get schedule executions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
