"""
Visual Workflows API

Endpoints for creating, managing, and executing visual workflow graphs.

Workflows are drag-and-drop graphs with nodes (LLM, Tool, Conditional)
that can be scheduled via cron, events, or dependencies.
"""

import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from open_notebook.domain.workflow import (
    Workflow,
    WorkflowGraph,
    WorkflowNode,
    WorkflowEdge,
    WorkflowExecution,
    WorkflowSchedule,
    NodeType,
    ScheduleType,
    EventTrigger,
    Position,
    NodeConfig,
)
from open_notebook.agents.workflow_engine import WorkflowEngine


router = APIRouter(prefix="/api/workflows", tags=["workflows"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateWorkflowRequest(BaseModel):
    """Request to create a workflow."""
    name: str = Field(..., description="Workflow name")
    description: Optional[str] = Field(None, description="Workflow description")
    graph: WorkflowGraph = Field(..., description="Visual graph structure")
    tags: Optional[List[str]] = Field(default_factory=list, description="Tags")


class UpdateWorkflowRequest(BaseModel):
    """Request to update a workflow."""
    name: Optional[str] = None
    description: Optional[str] = None
    graph: Optional[WorkflowGraph] = None
    is_active: Optional[bool] = None
    tags: Optional[List[str]] = None


class ExecuteWorkflowRequest(BaseModel):
    """Request to execute a workflow."""
    input_data: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Initial input data for workflow"
    )
    stream: bool = Field(default=False, description="Stream execution events via SSE")


class CreateScheduleRequest(BaseModel):
    """Request to create a workflow schedule."""
    schedule_type: ScheduleType = Field(..., description="Schedule type")
    cron_expression: Optional[str] = Field(None, description="Cron expression for cron schedules")
    event_trigger: Optional[EventTrigger] = Field(None, description="Event trigger config")
    upstream_workflow_id: Optional[str] = Field(None, description="Upstream workflow for dependency chains")
    enabled: bool = Field(default=True, description="Enable schedule immediately")


class UpdateScheduleRequest(BaseModel):
    """Request to update a workflow schedule."""
    cron_expression: Optional[str] = None
    event_trigger: Optional[EventTrigger] = None
    enabled: Optional[bool] = None


# ============================================================================
# Workflow CRUD Endpoints
# ============================================================================

@router.post("")
async def create_workflow(request: CreateWorkflowRequest):
    """
    Create a new workflow definition.

    Validates:
    - Graph has valid entry node
    - All edges connect existing nodes
    - No cycles (prevents infinite loops)
    - Valid node configurations
    """
    try:
        # Get user from auth (placeholder)
        user_id = "default-user"  # TODO: Get from auth context

        # Validate graph structure
        _validate_workflow_graph(request.graph)

        # Create workflow
        workflow = Workflow(
            id=None,  # Will be generated
            name=request.name,
            description=request.description,
            graph=request.graph,
            created_by=user_id,
            tags=request.tags or [],
        )

        await workflow.save()

        return {
            "success": True,
            "workflow_id": workflow.id,
            "name": workflow.name,
            "node_count": len(workflow.graph.nodes),
            "edge_count": len(workflow.graph.edges),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create workflow: {str(e)}")


@router.get("")
async def list_workflows(
    limit: int = 50,
    offset: int = 0,
    is_active: Optional[bool] = None,
):
    """
    List all workflows.

    Filters:
    - is_active: Filter by active status
    """
    try:
        from open_notebook.database.repository import repo_query

        workflows = await Workflow.get_all(order_by="updated_at DESC", limit=limit)

        # Filter by is_active if specified
        if is_active is not None:
            workflows = [w for w in workflows if w.is_active == is_active]

        # Get template information for each workflow
        workflow_ids = [w.id for w in workflows]
        template_info = {}

        if workflow_ids:
            placeholders = ','.join([f":wid{i}" for i in range(len(workflow_ids))])
            params = {f"wid{i}": wid for i, wid in enumerate(workflow_ids)}

            template_rows = await repo_query(f"""
                SELECT
                    wte.workflow_id,
                    wte.template_id,
                    wt.name as template_name,
                    wt.is_public as template_is_public
                FROM workflow_template_executions wte
                JOIN workflow_templates wt ON wte.template_id = wt.id
                WHERE wte.workflow_id IN ({placeholders})
            """, params)

            for row in template_rows:
                template_info[row['workflow_id']] = {
                    'template_id': row['template_id'],
                    'template_name': row['template_name'],
                    'template_is_public': bool(row['template_is_public'])
                }

        return {
            "success": True,
            "workflows": [
                {
                    "id": w.id,
                    "name": w.name,
                    "description": w.description,
                    "node_count": len(w.graph.nodes),
                    "edge_count": len(w.graph.edges),
                    "is_active": w.is_active,
                    "tags": w.tags,
                    "created_by": w.created_by,
                    "updated_at": w.updated.isoformat() if w.updated else None,
                    "source_template": template_info.get(w.id),
                }
                for w in workflows
            ],
            "total": len(workflows),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list workflows: {str(e)}")


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str):
    """Get workflow by ID with full graph definition."""
    try:
        workflow = await Workflow.get(workflow_id)

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        return {
            "success": True,
            "workflow": {
                "id": workflow.id,
                "name": workflow.name,
                "description": workflow.description,
                "graph": workflow.graph.dict(),
                "is_active": workflow.is_active,
                "tags": workflow.tags,
                "created_by": workflow.created_by,
                "created_at": workflow.created.isoformat() if workflow.created else None,
                "updated_at": workflow.updated.isoformat() if workflow.updated else None,
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get workflow: {str(e)}")


@router.put("/{workflow_id}")
async def update_workflow(workflow_id: str, request: UpdateWorkflowRequest):
    """Update workflow definition."""
    try:
        workflow = await Workflow.get(workflow_id)

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Update fields
        if request.name is not None:
            workflow.name = request.name
        if request.description is not None:
            workflow.description = request.description
        if request.graph is not None:
            _validate_workflow_graph(request.graph)
            workflow.graph = request.graph
        if request.is_active is not None:
            workflow.is_active = request.is_active
        if request.tags is not None:
            workflow.tags = request.tags

        await workflow.save()

        return {
            "success": True,
            "workflow_id": workflow.id,
            "updated_at": workflow.updated.isoformat() if workflow.updated else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update workflow: {str(e)}")


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """Delete workflow (cascade deletes executions and schedules)."""
    try:
        workflow = await Workflow.get(workflow_id)

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Delete all pending approvals for this workflow
        from open_notebook.database.repository import repo_query, repo_delete

        try:
            approval_rows = await repo_query(
                "SELECT id FROM workflow_approvals WHERE workflow_id = :workflow_id AND status = 'pending'",
                {"workflow_id": workflow_id}
            )

            for row in approval_rows:
                await repo_delete("workflow_approvals", row["id"])

            print(f"[WorkflowAPI] Deleted {len(approval_rows)} pending approvals for workflow {workflow_id}")

        except Exception as e:
            # Log but don't fail deletion if approval cleanup fails
            print(f"[WorkflowAPI] Warning: Failed to delete approvals: {e}")

        # Delete will cascade to executions and schedules
        await repo_delete("workflows", workflow_id)

        return {
            "success": True,
            "message": "Workflow deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete workflow: {str(e)}")


# ============================================================================
# Execution Endpoints
# ============================================================================

@router.post("/{workflow_id}/execute")
async def execute_workflow(
    workflow_id: str,
    request: ExecuteWorkflowRequest,
):
    """
    Execute a workflow.

    If stream=True, returns SSE stream with node execution updates.
    If stream=False, returns final execution result.

    SSE Events:
    - workflow_started: Execution began
    - node_executed: Node completed
    - workflow_completed: Execution finished
    - workflow_error: Execution failed
    """
    try:
        # Get workflow
        workflow = await Workflow.get(workflow_id)

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        if not workflow.is_active:
            raise HTTPException(status_code=400, detail="Workflow is not active")

        # Validate input data against input node schema
        input_node = next(
            (node for node in workflow.graph.nodes if node.type == NodeType.INPUT),
            None
        )

        if input_node and input_node.config.input_fields:
            validation_errors = []
            input_fields = input_node.config.input_fields
            input_data = request.input_data or {}

            for field_def in input_fields:
                if field_def.required and field_def.name not in input_data:
                    if field_def.default_value is None:
                        validation_errors.append(f"Required field '{field_def.name}' is missing")

            if validation_errors:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "message": "Input validation failed",
                        "errors": validation_errors
                    }
                )

        # Create engine
        engine = WorkflowEngine(workflow)

        # Execute
        if request.stream:
            # Stream execution
            return EventSourceResponse(
                _stream_execution(engine, request.input_data)
            )
        else:
            # Non-streaming execution
            execution = await engine.execute(input_data=request.input_data)

            return {
                "success": True,
                "execution_id": execution.id,
                "workflow_id": workflow_id,
                "status": execution.status.value,
                "started_at": execution.started_at.isoformat(),
                "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                "final_output": execution.final_output,
                "node_states": {
                    node_id: {
                        "status": state.status.value,
                        "output": state.output_data,
                        "error": state.error,
                    }
                    for node_id, state in execution.node_states.items()
                },
                "error": execution.error,
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")


async def _stream_execution(engine: WorkflowEngine, input_data: Dict[str, Any]):
    """Stream execution events via SSE."""
    try:
        async for event in engine.execute_streaming(input_data):
            yield {
                "event": event["type"],
                "data": json.dumps(event)
            }
    except Exception as e:
        yield {
            "event": "error",
            "data": json.dumps({"error": str(e)})
        }


@router.get("/{workflow_id}/executions")
async def list_executions(
    workflow_id: str,
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
):
    """List execution history for workflow."""
    try:
        executions = await WorkflowExecution.get_by_workflow(workflow_id, limit=limit)

        # Filter by status if specified
        if status:
            executions = [e for e in executions if e.status.value == status]

        return {
            "success": True,
            "executions": [
                {
                    "id": e.id,
                    "workflow_id": e.workflow_id,
                    "status": e.status.value,
                    "started_at": e.started_at.isoformat(),
                    "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                    "triggered_by": e.triggered_by,
                    "error": e.error,
                    "node_states": {
                        node_id: {
                            "status": state.status.value,
                            "started_at": state.started_at.isoformat() if state.started_at else None,
                            "completed_at": state.completed_at.isoformat() if state.completed_at else None,
                        }
                        for node_id, state in e.node_states.items()
                    },
                }
                for e in executions
            ],
            "total": len(executions),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list executions: {str(e)}")


@router.get("/{workflow_id}/executions/{execution_id}")
async def get_execution(workflow_id: str, execution_id: str):
    """Get execution details with node states."""
    try:
        execution = await WorkflowExecution.get(execution_id)

        if not execution or execution.workflow_id != workflow_id:
            raise HTTPException(status_code=404, detail="Execution not found")

        return {
            "success": True,
            "execution": {
                "id": execution.id,
                "workflow_id": execution.workflow_id,
                "status": execution.status.value,
                "started_at": execution.started_at.isoformat(),
                "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                "final_output": execution.final_output,
                "triggered_by": execution.triggered_by,
                "error": execution.error,
                "node_states": {
                    node_id: {
                        "status": state.status.value,
                        "started_at": state.started_at.isoformat() if state.started_at else None,
                        "completed_at": state.completed_at.isoformat() if state.completed_at else None,
                        "output_data": state.output_data,
                        "error": state.error,
                    }
                    for node_id, state in execution.node_states.items()
                },
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get execution: {str(e)}")


# ============================================================================
# Schedule Endpoints
# ============================================================================

@router.post("/{workflow_id}/schedules")
async def create_schedule(workflow_id: str, request: CreateScheduleRequest):
    """
    Create schedule for workflow.

    Types:
    - cron: Time-based with cron expression
    - event: Event-driven trigger
    - dependency: Chain after another workflow
    """
    try:
        # Verify workflow exists
        workflow = await Workflow.get(workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Validate schedule
        if request.schedule_type == ScheduleType.CRON and not request.cron_expression:
            raise HTTPException(status_code=400, detail="cron_expression required for cron schedules")

        if request.schedule_type == ScheduleType.EVENT and not request.event_trigger:
            raise HTTPException(status_code=400, detail="event_trigger required for event schedules")

        if request.schedule_type == ScheduleType.DEPENDENCY and not request.upstream_workflow_id:
            raise HTTPException(status_code=400, detail="upstream_workflow_id required for dependency schedules")

        # Create schedule
        schedule = WorkflowSchedule(
            id=None,  # Will be generated
            workflow_id=workflow_id,
            schedule_type=request.schedule_type,
            cron_expression=request.cron_expression,
            event_trigger=request.event_trigger,
            upstream_workflow_id=request.upstream_workflow_id,
            enabled=request.enabled,
        )

        await schedule.save()

        # Add to APScheduler
        from api.services.workflow_scheduler import get_workflow_scheduler
        scheduler = get_workflow_scheduler()
        await scheduler.schedule_workflow(schedule)

        return {
            "success": True,
            "schedule_id": schedule.id,
            "workflow_id": workflow_id,
            "schedule_type": schedule.schedule_type.value,
            "cron_expression": schedule.cron_expression,
            "event_trigger": schedule.event_trigger.dict() if schedule.event_trigger else None,
            "upstream_workflow_id": schedule.upstream_workflow_id,
            "enabled": schedule.enabled,
            "next_run_at": schedule.next_run_at.isoformat() if schedule.next_run_at else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create schedule: {str(e)}")


@router.get("/{workflow_id}/schedules")
async def list_schedules(workflow_id: str):
    """List schedules for workflow."""
    try:
        schedules = await WorkflowSchedule.get_by_workflow(workflow_id)

        return {
            "success": True,
            "schedules": [
                {
                    "id": s.id,
                    "workflow_id": s.workflow_id,
                    "schedule_type": s.schedule_type.value,
                    "cron_expression": s.cron_expression,
                    "event_trigger": s.event_trigger.dict() if s.event_trigger else None,
                    "upstream_workflow_id": s.upstream_workflow_id,
                    "enabled": s.enabled,
                    "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
                    "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None,
                }
                for s in schedules
            ],
            "total": len(schedules),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list schedules: {str(e)}")


@router.put("/{workflow_id}/schedules/{schedule_id}")
async def update_schedule(
    workflow_id: str,
    schedule_id: str,
    request: UpdateScheduleRequest,
):
    """Update schedule configuration."""
    try:
        schedule = await WorkflowSchedule.get(schedule_id)

        if not schedule or schedule.workflow_id != workflow_id:
            raise HTTPException(status_code=404, detail="Schedule not found")

        # Update fields
        if request.cron_expression is not None:
            schedule.cron_expression = request.cron_expression
        if request.event_trigger is not None:
            schedule.event_trigger = request.event_trigger
        if request.enabled is not None:
            schedule.enabled = request.enabled

        await schedule.save()

        # Update APScheduler
        from api.services.workflow_scheduler import get_workflow_scheduler
        scheduler = get_workflow_scheduler()
        await scheduler.schedule_workflow(schedule)

        return {
            "success": True,
            "schedule_id": schedule.id,
            "enabled": schedule.enabled,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update schedule: {str(e)}")


@router.delete("/{workflow_id}/schedules/{schedule_id}")
async def delete_schedule(workflow_id: str, schedule_id: str):
    """Delete workflow schedule."""
    try:
        schedule = await WorkflowSchedule.get(schedule_id)

        if not schedule or schedule.workflow_id != workflow_id:
            raise HTTPException(status_code=404, detail="Schedule not found")

        from open_notebook.database.repository import repo_delete
        await repo_delete("workflow_schedules", schedule_id)

        # Remove from APScheduler
        from api.services.workflow_scheduler import get_workflow_scheduler
        scheduler = get_workflow_scheduler()
        await scheduler.unschedule_workflow(schedule_id)

        return {
            "success": True,
            "message": "Schedule deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete schedule: {str(e)}")


# ============================================================================
# Scheduler Status Endpoints
# ============================================================================

@router.get("/scheduler/jobs")
async def list_scheduler_jobs():
    """
    List all scheduled jobs in APScheduler.

    Returns active cron jobs with next run times.
    """
    try:
        from api.services.workflow_scheduler import get_workflow_scheduler
        scheduler = get_workflow_scheduler()

        jobs = await scheduler.list_jobs()

        return {
            "success": True,
            "jobs": jobs,
            "total": len(jobs),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {str(e)}")


@router.get("/scheduler/jobs/{schedule_id}")
async def get_scheduler_job(schedule_id: str):
    """Get status of a specific scheduled job."""
    try:
        from api.services.workflow_scheduler import get_workflow_scheduler
        scheduler = get_workflow_scheduler()

        job_status = await scheduler.get_job_status(schedule_id)

        if not job_status:
            raise HTTPException(status_code=404, detail="Job not found")

        return {
            "success": True,
            "job": job_status,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}")


@router.post("/{workflow_id}/trigger")
async def trigger_workflow_manually(workflow_id: str, input_data: Optional[Dict[str, Any]] = None):
    """
    Manually trigger a workflow execution (bypass schedule).

    This executes the workflow immediately, regardless of its schedule.
    """
    try:
        # Get workflow
        workflow = await Workflow.get(workflow_id)

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        if not workflow.is_active:
            raise HTTPException(status_code=400, detail="Workflow is not active")

        # Create engine and execute
        engine = WorkflowEngine(workflow)
        execution = await engine.execute(
            input_data={
                **(input_data or {}),
                "triggered_by": "manual",
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        return {
            "success": True,
            "execution_id": execution.id,
            "workflow_id": workflow_id,
            "status": execution.status.value,
            "started_at": execution.started_at.isoformat(),
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to trigger workflow: {str(e)}")


@router.post("/events/{event_type}")
async def trigger_workflows_by_event(
    event_type: str,
    event_data: Optional[Dict[str, Any]] = None
):
    """
    Trigger workflows based on event.

    This publishes an event that triggers all workflows with matching event schedules.

    Example:
        POST /api/workflows/events/source_updated
        {
            "source_id": "abc-123",
            "source_type": "hana_table"
        }
    """
    try:
        from api.services.workflow_scheduler import get_workflow_scheduler
        scheduler = get_workflow_scheduler()

        await scheduler.trigger_workflow_by_event(event_type, event_data)

        return {
            "success": True,
            "event_type": event_type,
            "message": "Event published, workflows triggered",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to publish event: {str(e)}")


# ============================================================================
# Tool Schema Discovery Endpoints
# ============================================================================

@router.get("/tools")
async def list_available_tools():
    """
    List all available tools with basic info.

    Used by frontend to discover what tools are available for workflows.
    """
    try:
        from api.services.tool_factory import ToolFactory

        tools = []
        for tool_type in ToolFactory.get_available_tools():
            tool = ToolFactory.get_tool(tool_type)
            if tool:
                tools.append({
                    "tool_name": tool.name,
                    "description": tool.description,
                    "has_schema": hasattr(tool, 'args_schema')
                })

        return {"tools": tools}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list tools: {str(e)}")


@router.get("/tools/{tool_name}/schema")
async def get_tool_schema(tool_name: str):
    """
    Get the input schema for a specific tool.

    Returns field definitions that can be used for connection-based
    inference in input nodes.

    Args:
        tool_name: Name of the tool (e.g., 'web_search', 'calculator')

    Returns:
        Tool schema with field definitions
    """
    try:
        from api.services.tool_factory import ToolFactory

        # Get tool instance
        tool = ToolFactory.get_tool(tool_name)

        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

        # Get Pydantic schema
        if hasattr(tool, 'args_schema'):
            schema = tool.args_schema.model_json_schema()

            # Extract field definitions
            properties = schema.get("properties", {})
            required = schema.get("required", [])

            fields = []
            for field_name, field_info in properties.items():
                fields.append({
                    "name": field_name,
                    "type": _map_json_type_to_input_type(field_info.get("type", "string")),
                    "required": field_name in required,
                    "description": field_info.get("description"),
                    "default_value": field_info.get("default"),
                })

            return {
                "tool_name": tool_name,
                "tool_description": tool.description,
                "fields": fields,
                "raw_schema": schema
            }
        else:
            return {
                "tool_name": tool_name,
                "fields": [],
                "message": "Tool has no defined schema"
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _map_json_type_to_input_type(json_type: str) -> str:
    """Map JSON schema types to input field types."""
    mapping = {
        "string": "string",
        "integer": "number",
        "number": "number",
        "boolean": "boolean",
        "array": "array",
        "object": "object"
    }
    return mapping.get(json_type, "string")


# ============================================================================
# Helper Functions
# ============================================================================

def _validate_workflow_graph(graph: WorkflowGraph) -> None:
    """
    Validate workflow graph structure.

    Checks:
    - Entry node exists
    - All edges connect existing nodes
    - No cycles (prevents infinite loops)

    Raises:
        ValueError: If validation fails
    """
    # Check entry node exists
    node_ids = {node.id for node in graph.nodes}

    if graph.entry_node_id not in node_ids:
        raise ValueError(f"Entry node {graph.entry_node_id} not found in graph")

    # Check all edges connect existing nodes
    for edge in graph.edges:
        if edge.source not in node_ids:
            raise ValueError(f"Edge source {edge.source} not found in graph")
        if edge.target not in node_ids:
            raise ValueError(f"Edge target {edge.target} not found in graph")

    # Check for cycles (simplified - just check for self-loops)
    for edge in graph.edges:
        if edge.source == edge.target:
            raise ValueError(f"Self-loop detected: {edge.source} -> {edge.target}")

    # TODO: More sophisticated cycle detection (Phase 8+)


# ============================================================================
# Template and Pause/Resume Endpoints
# ============================================================================

@router.post("/{workflow_id}/save-as-template")
async def save_workflow_as_template(
    workflow_id: str,
    name: str,
    description: Optional[str] = None,
    category: Optional[str] = None,
    parameters: Optional[List[dict]] = None,
    is_public: bool = False,
    tags: Optional[List[str]] = None
):
    """
    Save workflow as a reusable template.

    Creates a template from the workflow that can be instantiated with parameters.
    """
    try:
        from api.services.workflow_template_service import get_workflow_template_service

        service = get_workflow_template_service()

        # Get user from header (placeholder)
        user_id = "default-user"  # TODO: Get from auth context

        template_id = await service.create_template_from_workflow(
            workflow_id=workflow_id,
            name=name,
            description=description,
            parameters=parameters or [],
            category=category,
            is_public=is_public,
            tags=tags,
            user_id=user_id
        )

        return {
            "success": True,
            "template_id": template_id,
            "message": "Workflow saved as template successfully"
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save workflow as template: {str(e)}")


@router.post("/executions/{execution_id}/pause")
async def pause_execution(execution_id: str, reason: Optional[str] = "manual_pause"):
    """
    Manually pause a workflow execution.

    Useful for debugging or manual intervention.
    """
    try:
        from api.services.workflow_resume_service import pause_workflow_execution

        await pause_workflow_execution(
            execution_id=execution_id,
            reason=reason
        )

        return {
            "success": True,
            "message": "Execution paused successfully"
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to pause execution: {str(e)}")


@router.post("/executions/{execution_id}/resume")
async def resume_execution(
    execution_id: str,
    resume_data: Optional[Dict[str, Any]] = None
):
    """
    Manually resume a paused workflow execution.

    Optionally inject data to continue execution.
    """
    try:
        from api.services.workflow_resume_service import resume_workflow_execution

        await resume_workflow_execution(
            execution_id=execution_id,
            resume_data=resume_data
        )

        return {
            "success": True,
            "message": "Execution resumed successfully"
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resume execution: {str(e)}")
