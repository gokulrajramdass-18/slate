"""
Workspace Templates API Router

Endpoints for template CRUD operations, instantiation, and discovery.
"""

import json
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Header, status
from pydantic import BaseModel, Field

from open_notebook.domain.workspace_template import WorkspaceTemplate
from open_notebook.database.repository import repo_query, repo_execute
from api.services.template_instantiation_service import get_template_instantiation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workspace-templates", tags=["Workspace Templates"])


# ============================================================================
# Request/Response Models
# ============================================================================

class TemplateCreateRequest(BaseModel):
    """Request to create template from workspace."""
    workspace_id: str = Field(..., description="Workspace to convert to template")
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    parameters: Optional[List[dict]] = Field(default_factory=list, description="Parameter definitions")
    is_public: bool = False
    tags: Optional[List[str]] = Field(default_factory=list)


class TemplateUpdateRequest(BaseModel):
    """Request to update template."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    parameters: Optional[List[dict]] = None
    is_public: Optional[bool] = None
    tags: Optional[List[str]] = None


class TemplateInstantiateRequest(BaseModel):
    """Request to instantiate template."""
    parameters: dict = Field(default_factory=dict, description="Runtime parameter values")
    workspace_name: Optional[str] = None


class TemplateExecuteRequest(BaseModel):
    """Request to execute template."""
    parameters: dict = Field(default_factory=dict, description="Runtime parameter values")
    target_workspace_id: Optional[str] = Field(
        None,
        description="Workspace to store results. Defaults to template's source workspace."
    )


class TemplateExecuteResponse(BaseModel):
    """Template execution response."""
    execution_id: str
    result_note_id: str
    folder_id: str
    target_workspace_id: str
    note_title: str
    message: str


class TemplateResponse(BaseModel):
    """Template response."""
    id: str
    user_id: str
    name: str
    description: Optional[str]
    category: Optional[str]
    source_workspace_id: Optional[str]
    phase_count: int
    task_count: int
    parameter_count: int
    version: int
    is_public: bool
    tags: List[str]
    usage_count: int  # Mapped from times_used in DB
    created_at: str
    updated_at: str


# ============================================================================
# Helper Functions
# ============================================================================

async def template_to_response(template: WorkspaceTemplate) -> TemplateResponse:
    """Convert template to response model."""
    phases = template.get_phases()
    parameters = template.get_parameters()
    tags = template.get_tags()

    task_count = sum(len(phase.get("tasks", [])) for phase in phases)

    return TemplateResponse(
        id=template.id,
        user_id=template.user_id,
        name=template.name,
        description=template.description,
        category=template.category,
        source_workspace_id=template.source_workspace_id,
        phase_count=len(phases),
        task_count=task_count,
        parameter_count=len(parameters),
        version=template.version,
        is_public=template.is_public,
        tags=tags,
        usage_count=template.times_used,
        created_at=template.created_at.isoformat() if isinstance(template.created_at, datetime) else template.created_at,
        updated_at=template.updated_at.isoformat() if isinstance(template.updated_at, datetime) else template.updated_at,
    )


# ============================================================================
# Endpoints
# ============================================================================

@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    request: TemplateCreateRequest,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """
    Create template from existing workspace.

    Converts a workspace with plan into a reusable template.
    """
    try:
        # Load workspace plan
        sql = """
            SELECT wp.*, n.name as workspace_name
            FROM workspace_plans wp
            JOIN notebooks n ON wp.workspace_id = n.id
            WHERE wp.workspace_id = :workspace_id
        """
        results = await repo_query(sql, {"workspace_id": request.workspace_id}, fetch_one=True)

        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workspace plan not found for workspace {request.workspace_id}"
            )

        plan_data = dict(results)

        # Load tasks from workspace_plan_tasks table and build phases
        tasks_sql = """
            SELECT * FROM workspace_plan_tasks
            WHERE plan_id = :plan_id
            ORDER BY phase_name, created
        """
        task_results = await repo_query(tasks_sql, {"plan_id": plan_data["id"]})

        # Group tasks by phase
        phases_dict = {}
        for task_row in task_results:
            task = dict(task_row)
            phase_name = task["phase_name"]

            if phase_name not in phases_dict:
                phases_dict[phase_name] = {
                    "name": phase_name,
                    "tasks": []
                }

            phases_dict[phase_name]["tasks"].append({
                "name": task["name"],
                "description": task.get("description", ""),
                "assigned_agent_id": task.get("assigned_agent_id"),
                "estimated_duration": task.get("estimated_duration"),
                "dependencies": json.loads(task["dependencies"]) if task.get("dependencies") else [],
                "required_tools": json.loads(task["required_tools"]) if task.get("required_tools") else [],
                "required_sources": json.loads(task["required_sources"]) if task.get("required_sources") else [],
            })

        # Convert to phases list
        phases_list = list(phases_dict.values())

        # If no tasks found, use phases from plan_data (if any)
        if not phases_list:
            phases_json = plan_data.get("phases", "[]")
            if isinstance(phases_json, str):
                phases_list = json.loads(phases_json) if phases_json else []
            else:
                phases_list = phases_json or []

        # Create template
        template = WorkspaceTemplate(
            user_id=x_user_id,
            name=request.name,
            description=request.description,
            category=request.category,
            source_workspace_id=request.workspace_id,  # NEW: Remember source workspace
            phases=json.dumps(phases_list),
            collaboration_graph=plan_data.get("collaboration_graph"),
            default_resources=None,  # TODO: Extract from workspace
            parameters=json.dumps(request.parameters) if request.parameters else None,
            is_public=request.is_public,
            tags=json.dumps(request.tags) if request.tags else None,
        )

        await template.save()

        logger.info(f"Created template {template.id} from workspace {request.workspace_id}")

        return await template_to_response(template)

    except Exception as e:
        logger.error(f"Failed to create template: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("", response_model=List[TemplateResponse])
async def list_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    is_public: Optional[bool] = Query(None, description="Filter by public status"),
    limit: int = Query(50, ge=1, le=100),
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """
    List templates accessible to user.

    Returns user's own templates and public templates.
    """
    try:
        where_clauses = []
        params = {"user_id": x_user_id, "limit": limit}

        # Filter by user or public
        where_clauses.append("(user_id = :user_id OR is_public = 1)")

        if category:
            where_clauses.append("category = :category")
            params["category"] = category

        if is_public is not None:
            where_clauses.append("is_public = :is_public")
            params["is_public"] = 1 if is_public else 0

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        sql = f"""
            SELECT * FROM workspace_templates
            WHERE {where_sql}
            ORDER BY times_used DESC, created_at DESC
            LIMIT :limit
        """

        results = await repo_query(sql, params)

        templates = []
        for row in results:
            template = WorkspaceTemplate(**dict(row))
            templates.append(await template_to_response(template))

        return templates

    except Exception as e:
        logger.error(f"Failed to list templates: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/public", response_model=List[TemplateResponse])
async def list_public_templates(
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100)
):
    """List public templates (no authentication required)."""
    try:
        templates = await WorkspaceTemplate.get_public_templates(category=category, limit=limit)
        return [await template_to_response(t) for t in templates]

    except Exception as e:
        logger.error(f"Failed to list public templates: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{template_id}", response_model=dict)
async def get_template(
    template_id: str,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """Get template details including full structure."""
    try:
        template = await WorkspaceTemplate.get(template_id)

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template {template_id} not found"
            )

        # Check access
        if not template.is_public and template.user_id != x_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to private template"
            )

        # Return full template with structure
        response_data = (await template_to_response(template)).model_dump()
        response_data.update({
            "phases": template.get_phases(),
            "collaboration_graph": template.get_collaboration_graph(),
            "default_resources": template.get_default_resources(),
            "parameters": template.get_parameters(),
        })

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get template: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    request: TemplateUpdateRequest,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """Update template."""
    try:
        template = await WorkspaceTemplate.get(template_id)

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template {template_id} not found"
            )

        # Check ownership
        if template.user_id != x_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only update own templates"
            )

        # Update fields
        if request.name is not None:
            template.name = request.name
        if request.description is not None:
            template.description = request.description
        if request.category is not None:
            template.category = request.category
        if request.parameters is not None:
            template.parameters = json.dumps(request.parameters)
        if request.is_public is not None:
            template.is_public = request.is_public
        if request.tags is not None:
            template.tags = json.dumps(request.tags)

        await template.save()

        logger.info(f"Updated template {template_id}")

        return await template_to_response(template)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update template: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: str,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """Delete template."""
    try:
        template = await WorkspaceTemplate.get(template_id)

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template {template_id} not found"
            )

        # Check ownership
        if template.user_id != x_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only delete own templates"
            )

        await template.delete()

        logger.info(f"Deleted template {template_id}")

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete template: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{template_id}/clone", response_model=dict)
async def instantiate_template(
    template_id: str,
    request: TemplateInstantiateRequest,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """Manually instantiate template as new workspace."""
    try:
        service = get_template_instantiation_service()

        workspace_id = await service.instantiate_template(
            template_id=template_id,
            parameters=request.parameters,
            user_id=x_user_id,
            workspace_name=request.workspace_name
        )

        logger.info(f"Instantiated template {template_id} as workspace {workspace_id}")

        return {
            "workspace_id": workspace_id,
            "template_id": template_id,
            "message": "Workspace created from template"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to instantiate template: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{template_id}/execute", response_model=TemplateExecuteResponse)
async def execute_template(
    template_id: str,
    request: TemplateExecuteRequest,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """
    Execute template and store results in workspace.

    Results are stored as a note in the target workspace (defaults to source workspace).
    Each execution creates a new note with parameters in the title, organized in folder structure:
      /Template Executions/{Template Name}/{Execution Note}
    """
    try:
        from api.services.template_execution_service import TemplateExecutionService

        service = TemplateExecutionService()
        result = await service.execute_template(
            template_id=template_id,
            parameters=request.parameters,
            user_id=x_user_id,
            target_workspace_id=request.target_workspace_id
        )

        return TemplateExecuteResponse(
            **result,
            message=f"Results stored in workspace folder: Template Executions/{result['note_title']}"
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to execute template: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{template_id}/executions", response_model=List[dict])
async def get_template_executions(
    template_id: str,
    limit: int = Query(50, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status: pending, running, completed, failed"),
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """Get execution history for template."""
    try:
        from open_notebook.domain.template_execution import TemplateExecution

        executions = await TemplateExecution.get_by_template(
            template_id=template_id,
            limit=limit,
            status=status
        )

        # Enrich with workspace names
        result = []
        for exec in executions:
            # Fetch workspace name
            workspace_name = None
            if exec.target_workspace_id:
                ws_query = await repo_query(
                    "SELECT name FROM notebooks WHERE id = :id",
                    {"id": exec.target_workspace_id},
                    fetch_one=True
                )
                if ws_query:
                    workspace_name = ws_query.get("name")

            result.append({
                "execution_id": exec.id,
                "orchestration_id": exec.id,  # For backward compatibility
                "target_workspace_id": exec.target_workspace_id,
                "workspace_id": exec.target_workspace_id,  # For backward compatibility
                "workspace_name": workspace_name,
                "folder_id": exec.folder_id,
                "parameters": exec.get_parameters(),
                "result_note_id": exec.result_note_id,
                "status": exec.status,
                "error": exec.error,
                "current_phase": exec.current_phase,
                "progress": exec.progress,
                "started_at": exec.started_at.isoformat() if exec.started_at else None,
                "executed_at": exec.completed_at.isoformat() if exec.completed_at else (exec.started_at.isoformat() if exec.started_at else None),  # For display
                "completed_at": exec.completed_at.isoformat() if exec.completed_at else None,
                "duration_ms": exec.duration_ms
            })

        return result

    except Exception as e:
        logger.error(f"Failed to get template executions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{template_id}/executions/{execution_id}")
async def delete_template_execution(
    template_id: str,
    execution_id: str,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """
    Delete a template execution and all associated resources.

    This will:
    1. Delete the execution record
    2. Delete the execution folder and all notes inside it
    3. Clean up any workspace_plan_tasks records
    """
    try:
        from open_notebook.domain.template_execution import TemplateExecution
        from open_notebook.domain.notebook import Notebook

        # Get execution
        execution = await TemplateExecution.get(execution_id)
        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Execution {execution_id} not found"
            )

        # Verify it belongs to this template
        if execution.template_id != template_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Execution does not belong to this template"
            )

        # Don't allow deleting running executions
        if execution.status == "running":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete a running execution. Please wait for it to complete or fail."
            )

        logger.info(f"Deleting execution {execution_id} for template {template_id}")

        # 1. Get all notes in the execution folder
        if execution.folder_id:
            notes_in_folder = await repo_query(
                "SELECT id FROM notes WHERE folder_id = :folder_id",
                {"folder_id": execution.folder_id}
            )

            note_ids = [note["id"] for note in notes_in_folder]

            # Delete notes and their junction table entries
            for note_id in note_ids:
                await repo_execute(
                    "DELETE FROM notebook_note WHERE note_id = :note_id",
                    {"note_id": note_id}
                )
                await repo_execute(
                    "DELETE FROM notes WHERE id = :note_id",
                    {"note_id": note_id}
                )

            logger.info(f"Deleted {len(note_ids)} notes from execution folder")

            # 2. Delete the execution folder
            await repo_execute(
                "DELETE FROM folders WHERE id = :folder_id",
                {"folder_id": execution.folder_id}
            )
            logger.info(f"Deleted execution folder {execution.folder_id}")

        # 3. Delete workspace_plan_tasks if any (for backward compatibility)
        await repo_execute(
            """DELETE FROM workspace_plan_tasks
               WHERE plan_id IN (
                   SELECT id FROM workspace_plans
                   WHERE workspace_id = :workspace_id
               )""",
            {"workspace_id": execution.target_workspace_id}
        )

        # 4. Delete workspace_plans if any
        await repo_execute(
            "DELETE FROM workspace_plans WHERE workspace_id = :workspace_id",
            {"workspace_id": execution.target_workspace_id}
        )

        # 5. Delete the execution record
        await execution.delete()
        logger.info(f"Deleted execution record {execution_id}")

        return {"message": "Execution deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete execution: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/executions/cleanup-stuck")
async def cleanup_stuck_executions(
    timeout_minutes: int = Query(30, ge=5, le=1440, description="Timeout in minutes"),
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """
    Clean up stuck template executions that have been running too long.

    Marks executions as 'failed' if they've been running for longer than the timeout period.
    """
    try:
        from open_notebook.domain.template_execution import TemplateExecution

        cleaned_count = await TemplateExecution.cleanup_stuck_executions(timeout_minutes)

        return {
            "success": True,
            "message": f"Cleaned up {cleaned_count} stuck execution(s)",
            "cleaned_count": cleaned_count,
            "timeout_minutes": timeout_minutes
        }

    except Exception as e:
        logger.error(f"Failed to cleanup stuck executions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
