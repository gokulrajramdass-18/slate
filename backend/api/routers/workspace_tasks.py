"""
Workspace Tasks API Router

Handles task management for AI-guided workspaces including:
- Listing tasks by workspace
- Starting/completing tasks
- Progress tracking
- Phase management
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from open_notebook.database.repository import repo_execute, repo_query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workspaces", tags=["workspace_tasks"])


# ============================================================================
# Pydantic Models
# ============================================================================

class WorkspaceTask(BaseModel):
    """A task within a workspace plan"""
    id: str
    plan_id: str
    phase_name: str
    name: str
    description: Optional[str] = None
    assigned_agent_id: Optional[str] = None
    status: str  # pending, in_progress, completed, blocked
    estimated_duration: Optional[int] = None  # minutes
    dependencies: List[str] = Field(default_factory=list)
    required_tools: List[str] = Field(default_factory=list)
    required_sources: List[str] = Field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created: str
    updated: str


class UpdateTaskRequest(BaseModel):
    """Request to update a task"""
    status: Optional[str] = Field(None, description="Task status: pending, in_progress, completed, blocked")
    assigned_agent_id: Optional[str] = Field(None, description="Agent assigned to this task")


class PhaseProgress(BaseModel):
    """Progress information for a phase"""
    phase_name: str
    total_tasks: int
    completed_tasks: int
    in_progress_tasks: int
    pending_tasks: int
    estimated_duration: int  # minutes
    completion_percentage: float


class WorkspaceProgress(BaseModel):
    """Overall workspace progress"""
    workspace_id: str
    total_tasks: int
    completed_tasks: int
    in_progress_tasks: int
    pending_tasks: int
    blocked_tasks: int
    overall_completion_percentage: float
    current_phase: Optional[str] = None
    phases: List[PhaseProgress]
    estimated_total_duration: int  # minutes
    estimated_remaining_duration: int  # minutes


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/{workspace_id}/tasks", response_model=List[WorkspaceTask])
async def list_workspace_tasks(
    workspace_id: str,
    phase: Optional[str] = None,
    task_status: Optional[str] = None,
    x_user_id: Optional[str] = Header("default_user"),
):
    """
    List all tasks for a workspace, optionally filtered by phase or status

    Args:
        workspace_id: The workspace ID
        phase: Optional phase name filter
        task_status: Optional status filter (pending, in_progress, completed, blocked)

    Returns:
        List of workspace tasks
    """
    try:
        # First verify the workspace exists and belongs to the user
        workspace_check = await repo_query(
            "SELECT id FROM notebooks WHERE id = :workspace_id",
            {"workspace_id": workspace_id},
            fetch_one=True
        )

        if not workspace_check:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workspace {workspace_id} not found"
            )

        # Get the workspace plan
        plan_result = await repo_query(
            "SELECT id FROM workspace_plans WHERE workspace_id = :workspace_id",
            {"workspace_id": workspace_id},
            fetch_one=True
        )

        if not plan_result:
            # Workspace exists but has no plan (not an AI-guided workspace)
            return []

        plan_id = plan_result["id"]

        # Build query with optional filters
        query = """
            SELECT
                id, plan_id, phase_name, name, description,
                assigned_agent_id, status, estimated_duration,
                dependencies, required_tools, required_sources,
                started_at, completed_at, created, updated
            FROM workspace_plan_tasks
            WHERE plan_id = :plan_id
        """
        params = {"plan_id": plan_id}

        if phase:
            query += " AND phase_name = :phase"
            params["phase"] = phase

        if task_status:
            query += " AND status = :task_status"
            params["task_status"] = task_status

        query += " ORDER BY created ASC"

        tasks = await repo_query(query, params)

        # Parse JSON fields
        import json
        for task in tasks:
            task["dependencies"] = json.loads(task.get("dependencies") or "[]")
            task["required_tools"] = json.loads(task.get("required_tools") or "[]")
            task["required_sources"] = json.loads(task.get("required_sources") or "[]")

        logger.info(f"Retrieved {len(tasks)} tasks for workspace {workspace_id}")
        return tasks

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list workspace tasks: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve tasks: {str(e)}"
        )


@router.get("/{workspace_id}/tasks/{task_id}", response_model=WorkspaceTask)
async def get_workspace_task(
    workspace_id: str,
    task_id: str,
    x_user_id: Optional[str] = Header("default_user"),
):
    """
    Get details for a specific task

    Args:
        workspace_id: The workspace ID
        task_id: The task ID

    Returns:
        Task details
    """
    try:
        # Verify workspace exists
        workspace_check = await repo_query(
            "SELECT id FROM notebooks WHERE id = :workspace_id",
            {"workspace_id": workspace_id},
            fetch_one=True
        )

        if not workspace_check:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workspace {workspace_id} not found"
            )

        # Get task with plan verification
        query = """
            SELECT
                t.id, t.plan_id, t.phase_name, t.name, t.description,
                t.assigned_agent_id, t.status, t.estimated_duration,
                t.dependencies, t.required_tools, t.required_sources,
                t.started_at, t.completed_at, t.created, t.updated
            FROM workspace_plan_tasks t
            JOIN workspace_plans p ON t.plan_id = p.id
            WHERE t.id = :task_id AND p.workspace_id = :workspace_id
        """

        task = await repo_query(
            query,
            {"task_id": task_id, "workspace_id": workspace_id},
            fetch_one=True
        )

        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found in workspace {workspace_id}"
            )

        # Parse JSON fields
        import json
        task["dependencies"] = json.loads(task.get("dependencies") or "[]")
        task["required_tools"] = json.loads(task.get("required_tools") or "[]")
        task["required_sources"] = json.loads(task.get("required_sources") or "[]")

        return task

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve task: {str(e)}"
        )


class CreateTaskRequest(BaseModel):
    """Request to create a new task"""
    phase_name: str = Field(..., description="Phase this task belongs to")
    name: str = Field(..., description="Task name")
    description: Optional[str] = Field(None, description="Task description")
    assigned_agent_id: Optional[str] = Field(None, description="Agent to assign (optional)")
    estimated_duration: Optional[int] = Field(None, description="Estimated duration in minutes")
    dependencies: List[str] = Field(default_factory=list, description="Task IDs this task depends on")


@router.post("/{workspace_id}/tasks", response_model=WorkspaceTask, status_code=status.HTTP_201_CREATED)
async def create_workspace_task(
    workspace_id: str,
    task_data: CreateTaskRequest,
    x_user_id: Optional[str] = Header("default_user"),
):
    """
    Create a new task for a workspace

    This endpoint allows manual task creation for both AI-guided and manually-created workspaces.
    If the workspace doesn't have a plan, one will be created automatically.

    Args:
        workspace_id: The workspace ID
        task_data: Task creation data

    Returns:
        Created task
    """
    try:
        import uuid
        import json

        # Verify workspace exists
        workspace = await repo_query(
            "SELECT id FROM notebooks WHERE id = :workspace_id",
            {"workspace_id": workspace_id},
            fetch_one=True
        )

        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workspace {workspace_id} not found"
            )

        # Get or create workspace plan
        plan = await repo_query(
            "SELECT id FROM workspace_plans WHERE workspace_id = :workspace_id",
            {"workspace_id": workspace_id},
            fetch_one=True
        )

        if not plan:
            # Create a default plan for manually-created workspaces
            plan_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()

            await repo_execute("""
                INSERT INTO workspace_plans (id, workspace_id, goal, phases, status, created, updated)
                VALUES (:id, :workspace_id, :goal, :phases, :status, :created, :updated)
            """, {
                "id": plan_id,
                "workspace_id": workspace_id,
                "goal": "Manual task management",
                "phases": "[]",  # Empty array for manual task management
                "status": "in_progress",
                "created": now,
                "updated": now
            })

            logger.info(f"Created default plan {plan_id} for workspace {workspace_id}")
        else:
            plan_id = plan["id"]

        # Validate dependencies exist
        if task_data.dependencies:
            for dep_id in task_data.dependencies:
                dep_task = await repo_query(
                    "SELECT id FROM workspace_plan_tasks WHERE id = :id AND plan_id = :plan_id",
                    {"id": dep_id, "plan_id": plan_id},
                    fetch_one=True
                )
                if not dep_task:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Dependency task {dep_id} not found in this workspace"
                    )

        # Create task
        task_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        await repo_execute("""
            INSERT INTO workspace_plan_tasks (
                id, plan_id, phase_name, name, description,
                assigned_agent_id, status, estimated_duration,
                dependencies, required_tools, required_sources,
                created, updated
            ) VALUES (
                :id, :plan_id, :phase_name, :name, :description,
                :assigned_agent_id, :status, :estimated_duration,
                :dependencies, :required_tools, :required_sources,
                :created, :updated
            )
        """, {
            "id": task_id,
            "plan_id": plan_id,
            "phase_name": task_data.phase_name,
            "name": task_data.name,
            "description": task_data.description,
            "assigned_agent_id": task_data.assigned_agent_id,
            "status": "pending",
            "estimated_duration": task_data.estimated_duration,
            "dependencies": json.dumps(task_data.dependencies),
            "required_tools": json.dumps([]),
            "required_sources": json.dumps([]),
            "created": now,
            "updated": now
        })

        logger.info(f"Created task {task_id} in workspace {workspace_id}")

        # Return created task
        return await get_workspace_task(workspace_id, task_id, x_user_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create task: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create task: {str(e)}"
        )


@router.put("/{workspace_id}/tasks/{task_id}", response_model=WorkspaceTask)
async def update_workspace_task(
    workspace_id: str,
    task_id: str,
    update: UpdateTaskRequest,
    x_user_id: Optional[str] = Header("default_user"),
):
    """
    Update a task (status, assignment, etc.)

    Args:
        workspace_id: The workspace ID
        task_id: The task ID
        update: Update fields

    Returns:
        Updated task
    """
    try:
        # First verify the task exists and belongs to this workspace
        existing = await get_workspace_task(workspace_id, task_id, x_user_id)

        # Build update data
        update_data = {"updated": datetime.utcnow().isoformat()}

        if update.status is not None:
            # Validate status
            valid_statuses = ["pending", "in_progress", "completed", "blocked"]
            if update.status not in valid_statuses:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
                )

            update_data["status"] = update.status

            # Track timestamps
            if update.status == "in_progress" and not existing.get("started_at"):
                update_data["started_at"] = datetime.utcnow().isoformat()
            elif update.status == "completed" and not existing.get("completed_at"):
                update_data["completed_at"] = datetime.utcnow().isoformat()

        if update.assigned_agent_id is not None:
            update_data["assigned_agent_id"] = update.assigned_agent_id

        # Build SET clause
        set_clause = ", ".join([f"{k} = :{k}" for k in update_data.keys()])
        update_data["task_id"] = task_id

        # Execute update
        await repo_execute(
            f"UPDATE workspace_plan_tasks SET {set_clause} WHERE id = :task_id",
            update_data
        )

        logger.info(f"Updated task {task_id} in workspace {workspace_id}: {update_data}")

        # If manually completing a task, create a note and check workspace completion
        if update.status == "completed":
            await _create_manual_completion_note(workspace_id, task_id, existing)
            # Small delay to ensure note is fully persisted before checking completion
            import asyncio
            await asyncio.sleep(0.5)
            await _check_workspace_completion_and_summary(workspace_id)

        # Return updated task
        return await get_workspace_task(workspace_id, task_id, x_user_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update task: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update task: {str(e)}"
        )


@router.get("/{workspace_id}/progress", response_model=WorkspaceProgress)
async def get_workspace_progress(
    workspace_id: str,
    x_user_id: Optional[str] = Header("default_user"),
):
    """
    Get overall progress and phase-level progress for a workspace

    Args:
        workspace_id: The workspace ID

    Returns:
        Progress information
    """
    try:
        # Get all tasks
        tasks = await list_workspace_tasks(workspace_id, x_user_id=x_user_id)

        if not tasks:
            # No tasks - return empty progress
            return WorkspaceProgress(
                workspace_id=workspace_id,
                total_tasks=0,
                completed_tasks=0,
                in_progress_tasks=0,
                pending_tasks=0,
                blocked_tasks=0,
                overall_completion_percentage=0.0,
                current_phase=None,
                phases=[],
                estimated_total_duration=0,
                estimated_remaining_duration=0
            )

        # Calculate overall stats
        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks if t["status"] == "completed")
        in_progress_tasks = sum(1 for t in tasks if t["status"] == "in_progress")
        pending_tasks = sum(1 for t in tasks if t["status"] == "pending")
        blocked_tasks = sum(1 for t in tasks if t["status"] == "blocked")

        overall_completion = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0.0

        # Calculate phase-level progress
        phase_stats: Dict[str, Dict] = {}
        for task in tasks:
            phase = task["phase_name"]
            if phase not in phase_stats:
                phase_stats[phase] = {
                    "total": 0,
                    "completed": 0,
                    "in_progress": 0,
                    "pending": 0,
                    "duration": 0
                }

            phase_stats[phase]["total"] += 1
            phase_stats[phase]["duration"] += task.get("estimated_duration") or 0

            if task["status"] == "completed":
                phase_stats[phase]["completed"] += 1
            elif task["status"] == "in_progress":
                phase_stats[phase]["in_progress"] += 1
            elif task["status"] == "pending":
                phase_stats[phase]["pending"] += 1

        # Build phase progress list
        phases = []
        for phase_name, stats in phase_stats.items():
            completion = (stats["completed"] / stats["total"] * 100) if stats["total"] > 0 else 0.0
            phases.append(PhaseProgress(
                phase_name=phase_name,
                total_tasks=stats["total"],
                completed_tasks=stats["completed"],
                in_progress_tasks=stats["in_progress"],
                pending_tasks=stats["pending"],
                estimated_duration=stats["duration"],
                completion_percentage=completion
            ))

        # Determine current phase (first phase with incomplete tasks)
        current_phase = None
        for phase in phases:
            if phase.completed_tasks < phase.total_tasks:
                current_phase = phase.phase_name
                break

        # Calculate time estimates
        total_duration = sum(t.get("estimated_duration") or 0 for t in tasks)
        remaining_duration = sum(
            t.get("estimated_duration") or 0
            for t in tasks
            if t["status"] in ["pending", "in_progress", "blocked"]
        )

        return WorkspaceProgress(
            workspace_id=workspace_id,
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            in_progress_tasks=in_progress_tasks,
            pending_tasks=pending_tasks,
            blocked_tasks=blocked_tasks,
            overall_completion_percentage=round(overall_completion, 1),
            current_phase=current_phase,
            phases=phases,
            estimated_total_duration=total_duration,
            estimated_remaining_duration=remaining_duration
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workspace progress: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate progress: {str(e)}"
        )


@router.post("/{workspace_id}/tasks/regenerate")
async def regenerate_workspace_tasks(
    workspace_id: str,
    x_user_id: Optional[str] = Header(None)
):
    """
    Regenerate all tasks for a workspace by resetting their status to pending.

    This allows users to re-run all tasks in an AI-guided workspace.
    Optionally deletes old task notes and the consolidated summary.
    """
    try:
        logger.info(f"Regenerating tasks for workspace {workspace_id}")

        # Verify workspace exists
        workspace = await repo_query(
            "SELECT id, name FROM notebooks WHERE id = :id",
            {"id": workspace_id},
            fetch_one=True
        )

        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found"
            )

        # Get workspace plan
        plan = await repo_query(
            "SELECT id FROM workspace_plans WHERE workspace_id = :workspace_id",
            {"workspace_id": workspace_id},
            fetch_one=True
        )

        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No plan found for this workspace"
            )

        # Get all task notes to delete (notes with task completion indicators or final deliverable)
        task_notes = await repo_query("""
            SELECT n.id FROM notes n
            JOIN notebook_note nn ON n.id = nn.note_id
            WHERE nn.notebook_id = :workspace_id
            AND (
                n.title LIKE '%✅%'
                OR n.title LIKE '%❌%'
                OR n.title LIKE '%Task:%'
                OR n.title LIKE '%Workspace Completion Summary%'
                OR n.title LIKE '%FINAL DELIVERABLE%'
            )
        """, {"workspace_id": workspace_id})

        # Delete task notes (both from notes table and junction table)
        if task_notes:
            note_ids = [note["id"] for note in task_notes]
            placeholders = ",".join([f":note_id_{i}" for i in range(len(note_ids))])
            params = {f"note_id_{i}": nid for i, nid in enumerate(note_ids)}

            # Delete from junction table
            await repo_execute(
                f"DELETE FROM notebook_note WHERE note_id IN ({placeholders})",
                params
            )

            # Delete from notes table
            await repo_execute(
                f"DELETE FROM notes WHERE id IN ({placeholders})",
                params
            )

            logger.info(f"Deleted {len(note_ids)} task notes")

        # Reset all tasks to pending status and clear errors
        await repo_execute("""
            UPDATE workspace_plan_tasks
            SET status = 'pending',
                error = NULL,
                started_at = NULL,
                completed_at = NULL,
                updated = :updated
            WHERE plan_id = :plan_id
        """, {
            "plan_id": plan["id"],
            "updated": datetime.utcnow().isoformat()
        })

        # Reset plan status to in_progress (so executor picks it up)
        await repo_execute("""
            UPDATE workspace_plans
            SET status = 'in_progress',
                updated = :updated
            WHERE id = :plan_id
        """, {
            "plan_id": plan["id"],
            "updated": datetime.utcnow().isoformat()
        })

        # Get updated task count
        updated_tasks = await repo_query("""
            SELECT COUNT(*) as count
            FROM workspace_plan_tasks
            WHERE plan_id = :plan_id
        """, {"plan_id": plan["id"]}, fetch_one=True)

        logger.info(f"Reset {updated_tasks['count']} tasks to pending status")

        return {
            "message": "Tasks regenerated successfully",
            "workspace_id": workspace_id,
            "tasks_reset": updated_tasks["count"],
            "notes_deleted": len(task_notes) if task_notes else 0
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to regenerate tasks: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate tasks: {str(e)}"
        )


@router.post("/{workspace_id}/tasks/{task_id}/start")
async def start_task_manually(
    workspace_id: str,
    task_id: str,
    x_user_id: Optional[str] = Header("default_user"),
):
    """
    Manually start/retry a specific task

    This endpoint:
    - Resets the task to pending status
    - Clears any error messages
    - Triggers the task executor to pick it up

    Use this when:
    - A task is stuck in 'in_progress'
    - A task failed and you want to retry
    - You want to force execution of a pending task
    """
    try:
        # Verify task exists and belongs to workspace
        task = await get_workspace_task(workspace_id, task_id, x_user_id)

        logger.info(f"Manually starting task {task_id} (current status: {task['status']})")

        # Reset task to pending and clear errors
        await repo_execute("""
            UPDATE workspace_plan_tasks
            SET status = 'pending',
                error = NULL,
                started_at = NULL,
                completed_at = NULL,
                updated = :updated
            WHERE id = :task_id
        """, {
            "task_id": task_id,
            "updated": datetime.utcnow().isoformat()
        })

        # Ensure plan is in_progress so executor picks it up
        await repo_execute("""
            UPDATE workspace_plans
            SET status = 'in_progress',
                updated = :updated
            WHERE workspace_id = :workspace_id
        """, {
            "workspace_id": workspace_id,
            "updated": datetime.utcnow().isoformat()
        })

        logger.info(f"Task {task_id} reset to pending and queued for execution")

        return {
            "message": "Task started successfully",
            "task_id": task_id,
            "workspace_id": workspace_id,
            "previous_status": task["status"],
            "new_status": "pending"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start task: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start task: {str(e)}"
        )


@router.post("/{workspace_id}/tasks/cleanup-stuck")
async def cleanup_stuck_tasks(
    workspace_id: str,
    timeout_minutes: int = 30,
    x_user_id: Optional[str] = Header("default_user"),
):
    """
    Find and reset tasks stuck in 'in_progress' for longer than timeout

    Args:
        workspace_id: Workspace ID
        timeout_minutes: Consider tasks stuck if in_progress for this many minutes (default: 30)

    Returns:
        Number of tasks reset
    """
    try:
        # Calculate cutoff time
        from datetime import timedelta
        cutoff_time = (datetime.utcnow() - timedelta(minutes=timeout_minutes)).isoformat()

        # Find stuck tasks
        stuck_tasks = await repo_query("""
            SELECT t.id, t.name, t.started_at, t.status
            FROM workspace_plan_tasks t
            JOIN workspace_plans p ON t.plan_id = p.id
            WHERE p.workspace_id = :workspace_id
            AND t.status = 'in_progress'
            AND t.started_at < :cutoff_time
        """, {
            "workspace_id": workspace_id,
            "cutoff_time": cutoff_time
        })

        if not stuck_tasks:
            return {
                "message": "No stuck tasks found",
                "tasks_reset": 0
            }

        # Reset stuck tasks to pending with error note
        task_ids = [task["id"] for task in stuck_tasks]
        placeholders = ",".join([f":task_id_{i}" for i in range(len(task_ids))])
        params = {f"task_id_{i}": tid for i, tid in enumerate(task_ids)}
        params["updated"] = datetime.utcnow().isoformat()
        params["error"] = f"Task was stuck in 'in_progress' for more than {timeout_minutes} minutes and was automatically reset"

        await repo_execute(f"""
            UPDATE workspace_plan_tasks
            SET status = 'pending',
                error = :error,
                started_at = NULL,
                updated = :updated
            WHERE id IN ({placeholders})
        """, params)

        logger.info(f"Reset {len(stuck_tasks)} stuck tasks in workspace {workspace_id}")

        return {
            "message": f"Reset {len(stuck_tasks)} stuck task(s)",
            "tasks_reset": len(stuck_tasks),
            "task_names": [t["name"] for t in stuck_tasks]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cleanup stuck tasks: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup stuck tasks: {str(e)}"
        )


@router.post("/{workspace_id}/tasks/finalize")
async def finalize_workspace(
    workspace_id: str,
    x_user_id: Optional[str] = Header("default_user"),
):
    """
    Manually trigger workspace finalization and summary generation

    This endpoint:
    - Checks if all tasks are completed
    - Marks workspace as completed
    - Generates the AI-powered consolidated summary (final deliverable)

    Use this when:
    - All tasks are done but summary wasn't generated
    - You want to regenerate the summary
    """
    try:
        # Verify workspace exists
        workspace = await repo_query(
            "SELECT id, name FROM notebooks WHERE id = :id",
            {"id": workspace_id},
            fetch_one=True
        )

        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found"
            )

        # Get workspace plan
        plan = await repo_query(
            "SELECT id, status FROM workspace_plans WHERE workspace_id = :workspace_id",
            {"workspace_id": workspace_id},
            fetch_one=True
        )

        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No plan found for this workspace"
            )

        # Check task status
        task_stats = await repo_query("""
            SELECT
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status IN ('pending', 'in_progress') THEN 1 ELSE 0 END) as active,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                COUNT(*) as total
            FROM workspace_plan_tasks
            WHERE plan_id = :plan_id
        """, {"plan_id": plan["id"]}, fetch_one=True)

        if task_stats["active"] > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot finalize: {task_stats['active']} task(s) still pending or in progress"
            )

        # Mark as completed (even if some tasks failed)
        await repo_execute("""
            UPDATE workspace_plans
            SET status = 'completed',
                updated = :updated
            WHERE id = :plan_id
        """, {
            "plan_id": plan["id"],
            "updated": datetime.utcnow().isoformat()
        })

        # Trigger summary generation
        from api.services.workspace_task_executor import get_task_executor
        executor = get_task_executor()
        await executor._create_ai_consolidated_summary(workspace_id, plan["id"])

        logger.info(f"Manually finalized workspace {workspace_id}")

        return {
            "message": "Workspace finalized and summary generated",
            "workspace_id": workspace_id,
            "tasks_completed": task_stats["completed"],
            "tasks_failed": task_stats["failed"],
            "status": "completed"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to finalize workspace: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to finalize workspace: {str(e)}"
        )


@router.post("/{workspace_id}/tasks/execute")
async def execute_workspace_plan(
    workspace_id: str,
    x_user_id: Optional[str] = Header("default_user"),
):
    """
    Manually execute workspace plan tasks using autonomous orchestrator

    This endpoint:
    - Triggers autonomous execution of all workspace plan tasks
    - Uses the AutonomousOrchestrator to execute tasks with agents
    - Only works for manually created workspaces (not AI-guided)

    Use this when:
    - User wants to execute manually created workspace tasks
    - Tasks have been created but not executed yet
    """
    try:
        # Verify workspace exists
        workspace = await repo_query(
            "SELECT id, name, goal FROM notebooks WHERE id = :id",
            {"id": workspace_id},
            fetch_one=True
        )

        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found"
            )

        # Check if workspace has a plan
        plan = await repo_query(
            "SELECT id, goal, phases FROM workspace_plans WHERE workspace_id = :workspace_id",
            {"workspace_id": workspace_id},
            fetch_one=True
        )

        if not plan:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workspace has no plan to execute"
            )

        # Check if tasks exist
        tasks = await repo_query(
            "SELECT COUNT(*) as count FROM workspace_plan_tasks WHERE plan_id = :plan_id",
            {"plan_id": plan["id"]},
            fetch_one=True
        )

        if not tasks or tasks["count"] == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workspace plan has no tasks to execute"
            )

        # Import and use autonomous orchestrator
        from open_notebook.agents.autonomous_orchestrator import AutonomousOrchestrator

        # Execute plan asynchronously (don't wait for completion)
        import asyncio

        async def execute_in_background():
            try:
                orchestrator = AutonomousOrchestrator()
                await orchestrator.execute_from_plan(
                    workspace_id=workspace_id,
                    plan_id=plan["id"]
                )
                logger.info(f"Workspace plan execution completed for {workspace_id}")
            except Exception as e:
                logger.error(f"Workspace plan execution failed: {e}", exc_info=True)

        # Start execution in background
        asyncio.create_task(execute_in_background())

        return {
            "message": "Workspace plan execution started",
            "workspace_id": workspace_id,
            "plan_id": plan["id"],
            "task_count": tasks["count"],
            "status": "running"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute workspace plan: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute workspace plan: {str(e)}"
        )


@router.get("/{workspace_id}/assignments")
async def get_task_assignments(workspace_id: str):
    """
    Debug endpoint to verify task-to-agent assignments

    Returns task assignment status for a workspace, showing which tasks
    are assigned to which agents. Useful for troubleshooting agent selection issues.
    """
    try:
        tasks = await repo_query("""
            SELECT wpt.id, wpt.name, wpt.assigned_agent_id, sa.name as agent_name
            FROM workspace_plan_tasks wpt
            LEFT JOIN standalone_agents sa ON wpt.assigned_agent_id = sa.id
            WHERE wpt.plan_id IN (SELECT id FROM workspace_plans WHERE workspace_id = :workspace_id)
        """, {"workspace_id": workspace_id})

        return {
            "workspace_id": workspace_id,
            "total_tasks": len(tasks),
            "assigned_tasks": sum(1 for t in tasks if t["assigned_agent_id"]),
            "unassigned_tasks": sum(1 for t in tasks if not t["assigned_agent_id"]),
            "assignments": [
                {
                    "task_id": t["id"],
                    "task_name": t["name"],
                    "agent_id": t["assigned_agent_id"],
                    "agent_name": t["agent_name"],
                }
                for t in tasks
            ]
        }

    except Exception as e:
        logger.error(f"Failed to get task assignments: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task assignments: {str(e)}"
        )


@router.get("/{workspace_id}/charts")
async def get_workspace_chart_data(workspace_id: str):
    """
    Get chart data for workspace visualizations

    Returns data formatted for:
    - Phase completion bar chart
    - Task status pie chart
    - Progress timeline chart
    - Agent workload distribution chart
    """
    try:
        # Get phase completion data
        phases = await repo_query("""
            SELECT
                phase_name,
                COUNT(*) as total,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
            FROM workspace_plan_tasks
            WHERE plan_id IN (SELECT id FROM workspace_plans WHERE workspace_id = :workspace_id)
            GROUP BY phase_name
            ORDER BY MIN(created)
        """, {"workspace_id": workspace_id})

        # Get task status distribution
        status_dist = await repo_query("""
            SELECT
                status,
                COUNT(*) as count
            FROM workspace_plan_tasks
            WHERE plan_id IN (SELECT id FROM workspace_plans WHERE workspace_id = :workspace_id)
            GROUP BY status
        """, {"workspace_id": workspace_id})

        # Get completion timeline (tasks completed over time)
        timeline = await repo_query("""
            SELECT
                DATE(completed_at) as date,
                COUNT(*) as completed
            FROM workspace_plan_tasks
            WHERE plan_id IN (SELECT id FROM workspace_plans WHERE workspace_id = :workspace_id)
            AND status = 'completed'
            AND completed_at IS NOT NULL
            GROUP BY DATE(completed_at)
            ORDER BY date
        """, {"workspace_id": workspace_id})

        # Get agent workload distribution
        agent_workload = await repo_query("""
            SELECT
                COALESCE(sa.name, 'Unassigned') as agent_name,
                COUNT(*) as task_count
            FROM workspace_plan_tasks wpt
            LEFT JOIN standalone_agents sa ON wpt.assigned_agent_id = sa.id
            WHERE wpt.plan_id IN (SELECT id FROM workspace_plans WHERE workspace_id = :workspace_id)
            GROUP BY sa.name
        """, {"workspace_id": workspace_id})

        # Format phase data
        phase_data = [
            {
                "phase": p["phase_name"],
                "completion": round((p["completed"] / p["total"] * 100) if p["total"] > 0 else 0, 1),
                "completed": p["completed"],
                "in_progress": p["in_progress"],
                "pending": p["pending"],
                "total": p["total"]
            }
            for p in phases
        ]

        # Format status data
        status_data = [
            {
                "status": s["status"].replace("_", " ").title(),
                "count": s["count"]
            }
            for s in status_dist
        ]

        # Format timeline data
        timeline_data = [
            {
                "date": t["date"],
                "completed": t["completed"]
            }
            for t in timeline
        ]

        # Format agent workload data
        workload_data = [
            {
                "agent": w["agent_name"],
                "tasks": w["task_count"]
            }
            for w in agent_workload
        ]

        return {
            "workspace_id": workspace_id,
            "phases": phase_data,
            "status_distribution": status_data,
            "timeline": timeline_data,
            "agent_workload": workload_data
        }

    except Exception as e:
        logger.error(f"Failed to get workspace chart data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get workspace chart data: {str(e)}"
        )


# ============================================================================
# Helper Functions for Manual Task Completion
# ============================================================================

async def _create_manual_completion_note(workspace_id: str, task_id: str, task: Dict):
    """Create a note when a task is manually marked as completed"""
    import uuid

    task_name = task.get("name", "Unnamed Task")
    phase_name = task.get("phase_name", "Unknown Phase")
    description = task.get("description", "No description provided")

    note_id = str(uuid.uuid4())
    note_content = f"""<h2>{task_name}</h2>
<p><strong>Status:</strong> ✅ Manually Completed<br>
<strong>Phase:</strong> {phase_name}<br>
<strong>Workspace:</strong> {workspace_id}</p>

<h3>Task Description</h3>
<p>{description}</p>

<hr>
<p><em>Task manually marked as completed on {datetime.utcnow().strftime('%Y-%m-%d at %H:%M UTC')}</em></p>
"""

    try:
        # Create the note
        await repo_execute("""
            INSERT INTO notes (id, title, content, content_html, created, updated)
            VALUES (:id, :title, :content, :content_html, :created, :updated)
        """, {
            "id": note_id,
            "title": f"✅ {task_name}",
            "content": note_content,
            "content_html": note_content,
            "created": datetime.utcnow().isoformat(),
            "updated": datetime.utcnow().isoformat()
        })

        # Link note to workspace
        await repo_execute("""
            INSERT OR IGNORE INTO notebook_note (notebook_id, note_id, created)
            VALUES (:notebook_id, :note_id, :created)
        """, {
            "notebook_id": workspace_id,
            "note_id": note_id,
            "created": datetime.utcnow().isoformat()
        })

        logger.info(f"Created manual completion note for task: {task_name}")
    except Exception as e:
        logger.error(f"Failed to create manual completion note: {e}", exc_info=True)


async def _check_workspace_completion_and_summary(workspace_id: str):
    """Check if all tasks are completed and generate final summary if needed"""
    try:
        logger.info(f"Checking workspace completion for {workspace_id}")

        # Get workspace plan
        plan = await repo_query(
            "SELECT id, status FROM workspace_plans WHERE workspace_id = :workspace_id",
            {"workspace_id": workspace_id},
            fetch_one=True
        )

        if not plan:
            logger.warning(f"No plan found for workspace {workspace_id}")
            return

        # Check if already completed
        if plan["status"] == "completed":
            logger.info(f"Workspace {workspace_id} already marked as completed")
            return

        # Count task statuses
        task_stats = await repo_query("""
            SELECT
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status IN ('pending', 'in_progress') THEN 1 ELSE 0 END) as active,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                COUNT(*) as total
            FROM workspace_plan_tasks
            WHERE plan_id = :plan_id
        """, {"plan_id": plan["id"]}, fetch_one=True)

        logger.info(f"Task stats for workspace {workspace_id}: completed={task_stats['completed']}, active={task_stats['active']}, failed={task_stats['failed']}, total={task_stats['total']}")

        # If all tasks are completed (and no active tasks), mark workspace as complete and generate summary
        if task_stats["active"] == 0 and task_stats["completed"] > 0:
            logger.info(f"All tasks completed for workspace {workspace_id}, generating summary...")

            # Mark workspace plan as completed
            await repo_execute("""
                UPDATE workspace_plans
                SET status = 'completed',
                    updated = :updated
                WHERE id = :plan_id
            """, {
                "plan_id": plan["id"],
                "updated": datetime.utcnow().isoformat()
            })

            logger.info(f"🎉 Workspace {workspace_id} marked as completed - generating summary")

            # Generate final summary
            from api.services.workspace_task_executor import get_task_executor
            executor = get_task_executor()
            await executor._create_ai_consolidated_summary(workspace_id, plan["id"])

            logger.info(f"✅ Summary generation completed for workspace {workspace_id}")
        else:
            logger.info(f"Workspace {workspace_id} not ready for completion: {task_stats['active']} active tasks remaining")

    except Exception as e:
        logger.error(f"Failed to check workspace completion: {e}", exc_info=True)

