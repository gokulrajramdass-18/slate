"""
Orchestration Actions Router

Manage action bindings to orchestration schedules and one-time orchestrations.

Endpoints:
- Bind actions to schedules (recurring orchestrations)
- Bind actions to one-time orchestrations
- Configure trigger conditions and execution order
"""

from fastapi import APIRouter, HTTPException, status
from typing import List, Optional
from datetime import datetime
import json
import uuid
import logging

from api.action_models import (
    ActionBindingCreate,
    ActionBindingUpdate,
    ActionBindingResponse,
)
from open_notebook.database.repository import (
    repo_query,
    repo_create,
    repo_update,
    repo_delete,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orchestration", tags=["Orchestration Actions"])


# ============================================================================
# Helper Functions
# ============================================================================

def format_binding(row: dict) -> ActionBindingResponse:
    """Format database row to ActionBindingResponse model"""
    return ActionBindingResponse(
        id=row["id"],
        schedule_id=row.get("schedule_id"),
        orchestration_id=row.get("orchestration_id"),
        action_id=row["action_id"],
        action_name=row["action_name"],
        action_type=row["action_type"],
        trigger_condition=row["trigger_condition"],
        phase_filter=json.loads(row["phase_filter"]) if row.get("phase_filter") else None,
        execution_order=row.get("execution_order", 0),
        is_active=bool(row.get("is_active", 1)),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def verify_schedule_exists(schedule_id: str):
    """Verify orchestration schedule exists"""
    sql = "SELECT id FROM orchestration_schedules WHERE id = :id"
    results = await repo_query(sql, {"id": schedule_id})

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Orchestration schedule {schedule_id} not found"
        )


async def verify_orchestration_exists(orchestration_id: str):
    """Verify orchestration exists"""
    sql = "SELECT id FROM orchestrations WHERE id = :id"
    results = await repo_query(sql, {"id": orchestration_id})

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Orchestration {orchestration_id} not found"
        )


async def verify_action_exists(action_id: str):
    """Verify action exists"""
    sql = "SELECT id FROM actions WHERE id = :id"
    results = await repo_query(sql, {"id": action_id})

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action {action_id} not found"
        )


# ============================================================================
# Schedule Action Bindings
# ============================================================================

@router.post("/schedules/{schedule_id}/actions", response_model=ActionBindingResponse, status_code=status.HTTP_201_CREATED)
async def add_schedule_action(schedule_id: str, binding: ActionBindingCreate):
    """
    Bind an action to an orchestration schedule.

    The action will execute based on the trigger condition when the schedule runs.
    """
    # Verify schedule and action exist
    await verify_schedule_exists(schedule_id)
    await verify_action_exists(binding.action_id)

    binding_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    data = {
        "id": binding_id,
        "schedule_id": schedule_id,
        "orchestration_id": None,
        "action_id": binding.action_id,
        "trigger_condition": binding.trigger_condition,
        "phase_filter": json.dumps(binding.phase_filter) if binding.phase_filter else None,
        "execution_order": binding.execution_order,
        "is_active": 1,
        "created_at": now,
        "updated_at": now,
    }

    await repo_create("orchestration_action_bindings", data)
    logger.info(f"Created action binding {binding_id} for schedule {schedule_id}")

    return await get_schedule_action_binding(schedule_id, binding_id)


@router.get("/schedules/{schedule_id}/actions", response_model=List[ActionBindingResponse])
async def list_schedule_actions(schedule_id: str, is_active: Optional[bool] = None):
    """
    List all actions bound to an orchestration schedule.

    - **is_active**: Filter by active status
    """
    await verify_schedule_exists(schedule_id)

    sql = """
        SELECT
            oab.*,
            a.name as action_name,
            a.action_type
        FROM orchestration_action_bindings oab
        JOIN actions a ON oab.action_id = a.id
        WHERE oab.schedule_id = :schedule_id
    """
    params = {"schedule_id": schedule_id}

    if is_active is not None:
        sql += " AND oab.is_active = :is_active"
        params["is_active"] = 1 if is_active else 0

    sql += " ORDER BY oab.execution_order ASC, oab.created_at ASC"

    results = await repo_query(sql, params)
    return [format_binding(row) for row in results]


@router.get("/schedules/{schedule_id}/actions/{binding_id}", response_model=ActionBindingResponse)
async def get_schedule_action_binding(schedule_id: str, binding_id: str):
    """Get a specific action binding"""
    sql = """
        SELECT
            oab.*,
            a.name as action_name,
            a.action_type
        FROM orchestration_action_bindings oab
        JOIN actions a ON oab.action_id = a.id
        WHERE oab.id = :binding_id AND oab.schedule_id = :schedule_id
    """

    results = await repo_query(sql, {"binding_id": binding_id, "schedule_id": schedule_id})

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action binding {binding_id} not found for schedule {schedule_id}"
        )

    return format_binding(results[0])


@router.put("/schedules/{schedule_id}/actions/{binding_id}", response_model=ActionBindingResponse)
async def update_schedule_action(schedule_id: str, binding_id: str, binding: ActionBindingUpdate):
    """Update an action binding"""
    # Verify binding exists
    await get_schedule_action_binding(schedule_id, binding_id)

    # Build update data
    data = {}
    if binding.trigger_condition is not None:
        data["trigger_condition"] = binding.trigger_condition
    if binding.phase_filter is not None:
        data["phase_filter"] = json.dumps(binding.phase_filter)
    if binding.execution_order is not None:
        data["execution_order"] = binding.execution_order
    if binding.is_active is not None:
        data["is_active"] = 1 if binding.is_active else 0

    data["updated_at"] = datetime.utcnow().isoformat()

    await repo_update("orchestration_action_bindings", binding_id, data)
    logger.info(f"Updated action binding {binding_id} for schedule {schedule_id}")

    return await get_schedule_action_binding(schedule_id, binding_id)


@router.delete("/schedules/{schedule_id}/actions/{binding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule_action(schedule_id: str, binding_id: str):
    """Remove an action binding from a schedule"""
    # Verify binding exists
    await get_schedule_action_binding(schedule_id, binding_id)

    await repo_delete("orchestration_action_bindings", binding_id)
    logger.info(f"Deleted action binding {binding_id} for schedule {schedule_id}")


# ============================================================================
# One-Time Orchestration Action Bindings
# ============================================================================

@router.post("/orchestrations/{orchestration_id}/actions", response_model=ActionBindingResponse, status_code=status.HTTP_201_CREATED)
async def add_orchestration_action(orchestration_id: str, binding: ActionBindingCreate):
    """
    Bind an action to a one-time orchestration.

    The action will execute based on the trigger condition during orchestration execution.
    """
    # Verify orchestration and action exist
    await verify_orchestration_exists(orchestration_id)
    await verify_action_exists(binding.action_id)

    binding_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    data = {
        "id": binding_id,
        "schedule_id": None,
        "orchestration_id": orchestration_id,
        "action_id": binding.action_id,
        "trigger_condition": binding.trigger_condition,
        "phase_filter": json.dumps(binding.phase_filter) if binding.phase_filter else None,
        "execution_order": binding.execution_order,
        "is_active": 1,
        "created_at": now,
        "updated_at": now,
    }

    await repo_create("orchestration_action_bindings", data)
    logger.info(f"Created action binding {binding_id} for orchestration {orchestration_id}")

    return await get_orchestration_action_binding(orchestration_id, binding_id)


@router.get("/orchestrations/{orchestration_id}/actions", response_model=List[ActionBindingResponse])
async def list_orchestration_actions(orchestration_id: str, is_active: Optional[bool] = None):
    """
    List all actions bound to an orchestration.

    - **is_active**: Filter by active status
    """
    await verify_orchestration_exists(orchestration_id)

    sql = """
        SELECT
            oab.*,
            a.name as action_name,
            a.action_type
        FROM orchestration_action_bindings oab
        JOIN actions a ON oab.action_id = a.id
        WHERE oab.orchestration_id = :orchestration_id
    """
    params = {"orchestration_id": orchestration_id}

    if is_active is not None:
        sql += " AND oab.is_active = :is_active"
        params["is_active"] = 1 if is_active else 0

    sql += " ORDER BY oab.execution_order ASC, oab.created_at ASC"

    results = await repo_query(sql, params)
    return [format_binding(row) for row in results]


@router.get("/orchestrations/{orchestration_id}/actions/{binding_id}", response_model=ActionBindingResponse)
async def get_orchestration_action_binding(orchestration_id: str, binding_id: str):
    """Get a specific action binding for an orchestration"""
    sql = """
        SELECT
            oab.*,
            a.name as action_name,
            a.action_type
        FROM orchestration_action_bindings oab
        JOIN actions a ON oab.action_id = a.id
        WHERE oab.id = :binding_id AND oab.orchestration_id = :orchestration_id
    """

    results = await repo_query(sql, {"binding_id": binding_id, "orchestration_id": orchestration_id})

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action binding {binding_id} not found for orchestration {orchestration_id}"
        )

    return format_binding(results[0])


# ============================================================================
# Utility Endpoints
# ============================================================================

@router.get("/actions/bindings", response_model=List[ActionBindingResponse])
async def list_all_bindings(
    action_id: Optional[str] = None,
    trigger_condition: Optional[str] = None,
    is_active: Optional[bool] = None,
):
    """
    List all action bindings with optional filtering.

    Useful for getting an overview of all action bindings across schedules and orchestrations.

    - **action_id**: Filter by specific action
    - **trigger_condition**: Filter by trigger condition
    - **is_active**: Filter by active status
    """
    sql = """
        SELECT
            oab.*,
            a.name as action_name,
            a.action_type
        FROM orchestration_action_bindings oab
        JOIN actions a ON oab.action_id = a.id
        WHERE 1=1
    """
    params = {}

    if action_id:
        sql += " AND oab.action_id = :action_id"
        params["action_id"] = action_id

    if trigger_condition:
        sql += " AND oab.trigger_condition = :trigger_condition"
        params["trigger_condition"] = trigger_condition

    if is_active is not None:
        sql += " AND oab.is_active = :is_active"
        params["is_active"] = 1 if is_active else 0

    sql += " ORDER BY oab.created_at DESC"

    results = await repo_query(sql, params)
    return [format_binding(row) for row in results]
