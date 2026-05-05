"""
Workflow Templates API Router

Endpoints for workflow template CRUD operations, instantiation, and gallery discovery.
"""

import json
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Header, status
from pydantic import BaseModel, Field

from open_notebook.domain.workflow_template import WorkflowTemplate, TemplateParameter
from open_notebook.database.repository import repo_query, repo_execute
from api.services.workflow_template_service import get_workflow_template_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflow-templates", tags=["Workflow Templates"])


# ============================================================================
# Request/Response Models
# ============================================================================

class WorkflowTemplateCreateRequest(BaseModel):
    """Request to create workflow template."""
    workflow_id: str = Field(..., description="Workflow to convert to template")
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    parameters: Optional[List[dict]] = Field(default_factory=list, description="Parameter definitions")
    is_public: bool = False
    tags: Optional[List[str]] = Field(default_factory=list)


class WorkflowTemplateUpdateRequest(BaseModel):
    """Request to update workflow template."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    parameters: Optional[List[dict]] = None
    is_public: Optional[bool] = None
    tags: Optional[List[str]] = None


class WorkflowTemplateInstantiateRequest(BaseModel):
    """Request to instantiate workflow template."""
    parameters: dict = Field(default_factory=dict, description="Runtime parameter values")
    workflow_name: Optional[str] = None


class WorkflowTemplateExecuteRequest(BaseModel):
    """Request to execute workflow template."""
    parameters: dict = Field(default_factory=dict, description="Runtime parameter values")
    input_data: Optional[dict] = Field(default_factory=dict, description="Input data for workflow execution")


class WorkflowTemplateResponse(BaseModel):
    """Workflow template response."""
    id: str
    user_id: str
    name: str
    description: Optional[str]
    category: Optional[str]
    source_workflow_id: Optional[str]
    node_count: int
    edge_count: int
    parameter_count: int
    version: int
    is_public: bool
    tags: List[str]
    usage_count: int
    created_at: str
    updated_at: str


class WorkflowTemplateDetailResponse(WorkflowTemplateResponse):
    """Detailed workflow template response with graph and parameters."""
    graph_json: str
    parameters: List[dict]


# ============================================================================
# Helper Functions
# ============================================================================

async def template_to_response(template: WorkflowTemplate, include_details: bool = False) -> WorkflowTemplateResponse:
    """Convert template to response model."""
    parameters = template.get_parameters()
    tags = template.get_tags()

    # Parse graph to count nodes and edges
    graph_data = json.loads(template.graph_json)
    node_count = len(graph_data.get("nodes", []))
    edge_count = len(graph_data.get("edges", []))

    base_data = {
        "id": template.id,
        "user_id": template.user_id,
        "name": template.name,
        "description": template.description,
        "category": template.category,
        "source_workflow_id": template.source_workflow_id,
        "node_count": node_count,
        "edge_count": edge_count,
        "parameter_count": len(parameters),
        "version": template.version,
        "is_public": template.is_public,
        "tags": tags,
        "usage_count": template.usage_count,
        "created_at": template.created.isoformat() if template.created else datetime.utcnow().isoformat(),
        "updated_at": template.updated.isoformat() if template.updated else datetime.utcnow().isoformat(),
    }

    if include_details:
        return WorkflowTemplateDetailResponse(
            **base_data,
            graph_json=template.graph_json,
            parameters=[p.dict() if hasattr(p, 'dict') else p for p in parameters]
        )

    return WorkflowTemplateResponse(**base_data)


# ============================================================================
# Endpoints
# ============================================================================

@router.post("", response_model=WorkflowTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    request: WorkflowTemplateCreateRequest,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """
    Create workflow template from existing workflow.

    Converts a workflow into a reusable template with parameters.
    """
    try:
        service = get_workflow_template_service()

        template_id = await service.create_template_from_workflow(
            workflow_id=request.workflow_id,
            name=request.name,
            description=request.description,
            parameters=request.parameters,
            category=request.category,
            is_public=request.is_public,
            tags=request.tags,
            user_id=x_user_id
        )

        template = await WorkflowTemplate.get(template_id)
        return await template_to_response(template)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create workflow template: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("", response_model=List[WorkflowTemplateResponse])
async def list_templates(
    x_user_id: str = Header(..., alias="X-User-ID"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=100)
):
    """
    List user's workflow templates.

    Returns templates created by the authenticated user.
    """
    try:
        templates = await WorkflowTemplate.get_by_user(x_user_id, limit=limit)

        # Filter by category if specified
        if category:
            templates = [t for t in templates if t.category == category]

        return [await template_to_response(t) for t in templates]

    except Exception as e:
        logger.error(f"Failed to list workflow templates: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/public")
async def list_public_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=100),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
):
    """
    Browse public workflow template gallery.

    No authentication required. Returns templates marked as public.
    If user ID provided, includes flag indicating if user has consumed each template.
    """
    try:
        templates = await WorkflowTemplate.get_public_templates(category=category, limit=limit)

        # Check which templates the user has consumed
        consumed_template_ids = set()
        if x_user_id:
            template_ids = [t.id for t in templates]
            if template_ids:
                placeholders = ','.join([f":tid{i}" for i in range(len(template_ids))])
                params = {f"tid{i}": tid for i, tid in enumerate(template_ids)}
                params["user_id"] = x_user_id

                consumed_rows = await repo_query(f"""
                    SELECT DISTINCT template_id
                    FROM workflow_template_executions
                    WHERE template_id IN ({placeholders})
                    AND user_id = :user_id
                """, params)

                consumed_template_ids = {row['template_id'] for row in consumed_rows}

        # Add consumed flag to response
        result = []
        for t in templates:
            response_obj = await template_to_response(t)
            # Convert Pydantic model to dict
            if hasattr(response_obj, 'dict'):
                template_dict = response_obj.dict()
            else:
                template_dict = dict(response_obj)

            template_dict['consumed_by_user'] = t.id in consumed_template_ids
            result.append(template_dict)

        return result

    except Exception as e:
        logger.error(f"Failed to list public workflow templates: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{template_id}", response_model=WorkflowTemplateDetailResponse)
async def get_template(
    template_id: str,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """
    Get workflow template details.

    Returns full template including graph and parameters.
    """
    try:
        template = await WorkflowTemplate.get(template_id)

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template {template_id} not found"
            )

        # Check access (owner or public)
        if not template.is_public and template.user_id != x_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        return await template_to_response(template, include_details=True)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workflow template: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/{template_id}", response_model=WorkflowTemplateResponse)
async def update_template(
    template_id: str,
    request: WorkflowTemplateUpdateRequest,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """
    Update workflow template.

    Only the template owner can update it.
    """
    try:
        template = await WorkflowTemplate.get(template_id)

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template {template_id} not found"
            )

        if template.user_id != x_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only template owner can update"
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

        template.updated = datetime.utcnow()
        await template.save()

        return await template_to_response(template)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update workflow template: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: str,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """
    Delete workflow template.

    Only the template owner can delete it.
    """
    try:
        template = await WorkflowTemplate.get(template_id)

        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template {template_id} not found"
            )

        if template.user_id != x_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only template owner can delete"
            )

        from open_notebook.database.repository import repo_delete
        await repo_delete("workflow_templates", template_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete workflow template: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{template_id}/instantiate")
async def instantiate_template(
    template_id: str,
    request: WorkflowTemplateInstantiateRequest,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """
    Instantiate workflow from template.

    Creates a new workflow with parameter values substituted.
    """
    try:
        service = get_workflow_template_service()

        workflow_id = await service.instantiate_template(
            template_id=template_id,
            parameters=request.parameters,
            user_id=x_user_id,
            name=request.workflow_name
        )

        return {
            "success": True,
            "workflow_id": workflow_id,
            "message": "Workflow instantiated successfully"
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to instantiate workflow template: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{template_id}/execute")
async def execute_template(
    template_id: str,
    request: WorkflowTemplateExecuteRequest,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """
    Instantiate and execute workflow template.

    Creates a new workflow and executes it immediately.
    """
    try:
        service = get_workflow_template_service()

        result = await service.execute_template(
            template_id=template_id,
            parameters=request.parameters,
            user_id=x_user_id,
            input_data=request.input_data
        )

        return {
            "success": True,
            **result,
            "message": "Workflow template executed successfully"
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to execute workflow template: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{template_id}/executions")
async def list_template_executions(
    template_id: str,
    x_user_id: str = Header(..., alias="X-User-ID"),
    limit: int = Query(50, ge=1, le=100)
):
    """
    List execution history for workflow template.

    Returns recent executions with results.
    """
    try:
        rows = await repo_query(
            """
            SELECT * FROM workflow_template_executions
            WHERE template_id = :template_id
            AND user_id = :user_id
            ORDER BY created DESC
            LIMIT :limit
            """,
            {"template_id": template_id, "user_id": x_user_id, "limit": limit}
        )

        return {
            "success": True,
            "executions": [dict(row) for row in rows],
            "total": len(rows)
        }

    except Exception as e:
        logger.error(f"Failed to list workflow template executions: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
