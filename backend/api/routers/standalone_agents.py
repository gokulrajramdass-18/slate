"""
Standalone Agents Router

Endpoints for managing individual agents (not part of teams) with their own:
- Tools and MCP servers
- Data sources
- Execution history
"""

import json
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from api.models import (
    StandaloneAgentCreate,
    StandaloneAgentUpdate,
    StandaloneAgentResponse,
    StandaloneAgentListResponse,
    StandaloneAgentExecuteRequest,
    StandaloneAgentExecutionResponse,
    StandaloneAgentExecutionListResponse,
    StandaloneAgentExecutionStep,
)
from open_notebook.config import get_database
from open_notebook.database.repository import repo_query, repo_execute
from api.services.tool_factory import ToolFactory
from api.services.llm_client import (
    _normalize_openai_base,
    call_llm_chat_message,
)
from api.services.memory_service import derive_task_pattern, get_memory_manager

router = APIRouter(prefix="/api/standalone-agents", tags=["standalone-agents"])


# ============================================================================
# Agent CRUD Operations
# ============================================================================

@router.post("", response_model=StandaloneAgentResponse, status_code=201)
async def create_standalone_agent(agent: StandaloneAgentCreate):
    """Create a new standalone agent"""
    agent_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    # Validate role
    valid_roles = [
        "planner", "researcher", "analyst", "synthesizer",
        "writer", "strategist", "editor",
        "custom",
    ]
    if agent.role not in valid_roles:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}"
        )

    # Validate notebook_id if provided
    if agent.notebook_id:
        notebook_check = await repo_query(
            "SELECT id FROM notebooks WHERE id = :notebook_id",
            {"notebook_id": agent.notebook_id}
        )
        if not notebook_check:
            raise HTTPException(status_code=404, detail="Notebook not found")

    # Insert agent
    await repo_execute(
        """
        INSERT INTO standalone_agents (
            id, name, description, role, system_prompt, model_name, notebook_id,
            config, tool_ids, skill_ids, mcp_server_ids, data_source_ids, status, created, updated
        ) VALUES (
            :id, :name, :description, :role, :system_prompt, :model_name, :notebook_id,
            :config, :tool_ids, :skill_ids, :mcp_server_ids, :data_source_ids, :status, :created, :updated
        )
        """,
        {
            "id": agent_id,
            "name": agent.name,
            "description": agent.description,
            "role": agent.role,
            "system_prompt": agent.system_prompt,
            "model_name": agent.model_name,
            "notebook_id": agent.notebook_id,
            "config": json.dumps(agent.config or {}),
            "tool_ids": json.dumps(agent.tool_ids or []),
            "skill_ids": json.dumps(agent.skill_ids or []),
            "mcp_server_ids": json.dumps(agent.mcp_server_ids or []),
            "data_source_ids": json.dumps(agent.data_source_ids or []),
            "status": "active",
            "created": now,
            "updated": now,
        }
    )

    return await get_standalone_agent(agent_id)


@router.get("", response_model=StandaloneAgentListResponse)
async def list_standalone_agents(
    notebook_id: Optional[str] = Query(None, description="Filter by notebook"),
    status: Optional[str] = Query(None, description="Filter by status (active, inactive, archived)"),
    role: Optional[str] = Query(None, description="Filter by role"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List all standalone agents with optional filters"""

    # Build query with filters
    where_clauses = []
    params = {"limit": limit, "offset": offset}

    if notebook_id:
        where_clauses.append("notebook_id = :notebook_id")
        params["notebook_id"] = notebook_id

    if status:
        where_clauses.append("status = :status")
        params["status"] = status

    if role:
        where_clauses.append("role = :role")
        params["role"] = role

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Get total count
    count_result = await repo_query(
        f"SELECT COUNT(*) as count FROM standalone_agents WHERE {where_sql}",
        params
    )
    total = count_result[0]["count"] if count_result else 0

    # Get agents
    agents_rows = await repo_query(
        f"""
        SELECT * FROM standalone_agents
        WHERE {where_sql}
        ORDER BY created DESC
        LIMIT :limit OFFSET :offset
        """,
        params
    )

    agents = [StandaloneAgentResponse(**row) for row in agents_rows]

    return StandaloneAgentListResponse(agents=agents, total=total)


@router.get("/{agent_id}", response_model=StandaloneAgentResponse)
async def get_standalone_agent(agent_id: str):
    """Get a standalone agent by ID"""
    rows = await repo_query(
        "SELECT * FROM standalone_agents WHERE id = :id",
        {"id": agent_id}
    )

    if not rows:
        raise HTTPException(status_code=404, detail="Agent not found")

    return StandaloneAgentResponse(**rows[0])


@router.put("/{agent_id}", response_model=StandaloneAgentResponse)
async def update_standalone_agent(agent_id: str, update: StandaloneAgentUpdate):
    """Update a standalone agent"""

    # Check if agent exists
    existing = await repo_query(
        "SELECT id FROM standalone_agents WHERE id = :id",
        {"id": agent_id}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Build update query
    update_fields = []
    params = {"id": agent_id, "updated": datetime.utcnow().isoformat()}

    update_data = update.model_dump(exclude_unset=True)

    # Handle model_name: if explicitly set to None or empty string, use default from settings
    if "model_name" in update_data:
        if update_data["model_name"] is None or update_data["model_name"] == "":
            # Get default language model from settings
            from api.services.settings import get_setting
            default_model_id = await get_setting("language_model_id", "")
            update_data["model_name"] = default_model_id if default_model_id else None

    for field, value in update_data.items():
        if field in ["tool_ids", "skill_ids", "mcp_server_ids", "data_source_ids", "config"]:
            # JSON fields
            update_fields.append(f"{field} = :{field}")
            params[field] = json.dumps(value) if value is not None else None
        else:
            # Regular fields
            update_fields.append(f"{field} = :{field}")
            params[field] = value

    if update_fields:
        update_fields.append("updated = :updated")
        sql = f"""
            UPDATE standalone_agents
            SET {', '.join(update_fields)}
            WHERE id = :id
        """
        await repo_execute(sql, params)

    return await get_standalone_agent(agent_id)


@router.delete("/{agent_id}", status_code=204)
async def delete_standalone_agent(agent_id: str):
    """Delete a standalone agent (also deletes execution history)"""
    result = await repo_execute(
        "DELETE FROM standalone_agents WHERE id = :id",
        {"id": agent_id}
    )

    if result == 0:
        raise HTTPException(status_code=404, detail="Agent not found")


# ============================================================================
# Agent Execution
# ============================================================================

@router.post("/{agent_id}/execute", response_model=StandaloneAgentExecutionResponse)
async def execute_standalone_agent(
    agent_id: str,
    request: StandaloneAgentExecuteRequest
):
    """
    Execute a standalone agent with a query.

    This is the non-streaming version. For streaming, use /execute/stream endpoint.
    """
    # Get agent
    agent_rows = await repo_query(
        "SELECT * FROM standalone_agents WHERE id = :id AND status = 'active'",
        {"id": agent_id}
    )
    if not agent_rows:
        raise HTTPException(status_code=404, detail="Agent not found or inactive")

    agent_data = agent_rows[0]

    # Create execution record
    execution_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    await repo_execute(
        """
        INSERT INTO standalone_agent_executions (
            id, agent_id, query, status, session_id, notebook_id,
            context, started_at, created, updated
        ) VALUES (
            :id, :agent_id, :query, :status, :session_id, :notebook_id,
            :context, :started_at, :created, :updated
        )
        """,
        {
            "id": execution_id,
            "agent_id": agent_id,
            "query": request.query,
            "status": "running",
            "session_id": request.session_id,
            "notebook_id": agent_data["notebook_id"],
            "context": json.dumps({
                "source_ids": request.context_source_ids or json.loads(agent_data.get("data_source_ids") or "[]"),
                "max_steps": request.max_steps
            }),
            "started_at": now,
            "created": now,
            "updated": now,
        }
    )

    return await get_standalone_agent_execution(execution_id)


@router.post("/{agent_id}/execute/stream")
async def execute_standalone_agent_stream(
    agent_id: str,
    request: StandaloneAgentExecuteRequest
):
    """
    Execute a standalone agent with streaming progress via SSE.

    Streams events:
    - metadata: execution metadata (id, agent_id, etc.)
    - agent_step: execution step progress
    - chunk: response text chunks
    - ui_component: generative UI components
    - done: execution complete
    - error: execution failed
    """
    # Get agent
    agent_rows = await repo_query(
        "SELECT * FROM standalone_agents WHERE id = :id AND status = 'active'",
        {"id": agent_id}
    )
    if not agent_rows:
        raise HTTPException(status_code=404, detail="Agent not found or inactive")

    agent_data = agent_rows[0]

    # Create execution record
    execution_id = str(uuid.uuid4())
    start_time = datetime.utcnow()
    now = start_time.isoformat()

    await repo_execute(
        """
        INSERT INTO standalone_agent_executions (
            id, agent_id, query, status, session_id, notebook_id,
            context, started_at, created, updated
        ) VALUES (
            :id, :agent_id, :query, :status, :session_id, :notebook_id,
            :context, :started_at, :created, :updated
        )
        """,
        {
            "id": execution_id,
            "agent_id": agent_id,
            "query": request.query,
            "status": "running",
            "session_id": request.session_id,
            "notebook_id": agent_data["notebook_id"],
            "context": json.dumps({
                "source_ids": request.context_source_ids or json.loads(agent_data.get("data_source_ids") or "[]"),
                "max_steps": request.max_steps
            }),
            "started_at": now,
            "created": now,
            "updated": now,
        }
    )

    async def event_generator():
        """Adapter: drive the shared standalone-agent runner and reformat its
        dict events into the legacy SSE-string shape this endpoint emitted."""
        from api.services.standalone_agent_runner import (
            run_standalone_agent_events,
            resolve_credential_for_agent,
        )

        # Resolve credential up-front so we can fail with a clear SSE error
        # rather than letting the runner blow up on a missing key.
        credential = await resolve_credential_for_agent(agent_data)
        if not credential:
            yield f"event: error\ndata: {json.dumps({'error': 'No AI model configured. Please add a model in Settings → Models.'})}\n\n"
            return

        try:
            async for ev in run_standalone_agent_events(
                agent_data=agent_data,
                query=request.query,
                credential=credential,
                context_source_ids=request.context_source_ids,
                notebook_id=agent_data.get("notebook_id"),
                session_id=request.session_id,
                # The HTTP endpoint already INSERTed an executions row above
                # with the same execution_id we want to keep — pass it
                # through and skip the runner's own insert by setting
                # record_execution=False, then update the row at the end.
                record_execution=False,
            ):
                kind = ev.pop("kind", "message")
                # Replace the runner's generated execution_id with the one
                # we already wrote so the existing /executions/{id} link
                # works for clients that captured it.
                if kind in ("metadata", "done"):
                    ev["execution_id"] = execution_id
                yield f"event: {kind}\ndata: {json.dumps(ev)}\n\n"
                if kind == "done":
                    # Finalize the row this endpoint inserted up-front.
                    duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                    await repo_execute(
                        """
                        UPDATE standalone_agent_executions
                        SET status = :status, result = :result, completed_at = :completed_at,
                            updated = :updated, duration_ms = :duration_ms
                        WHERE id = :id
                        """,
                        {
                            "id": execution_id, "status": "completed",
                            "result": json.dumps({"response": ev.get("response", "")}),
                            "completed_at": datetime.utcnow().isoformat(),
                            "updated": datetime.utcnow().isoformat(),
                            "duration_ms": duration_ms,
                        },
                    )
                elif kind == "error":
                    await repo_execute(
                        "UPDATE standalone_agent_executions SET status = 'failed', error = :e, completed_at = :c, updated = :c WHERE id = :id",
                        {"id": execution_id, "e": ev.get("error", "Unknown error"), "c": datetime.utcnow().isoformat()},
                    )
        except Exception as e:
            import traceback
            traceback.print_exc()
            await repo_execute(
                "UPDATE standalone_agent_executions SET status = 'failed', error = :e, completed_at = :c, updated = :c WHERE id = :id",
                {"id": execution_id, "e": str(e), "c": datetime.utcnow().isoformat()},
            )
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"


    # Adapt the existing string-yielding generator to the dict shape
    # EventSourceResponse expects: {"event": "<type>", "data": "<json>"}.
    # We keep `event_generator` emitting raw SSE strings (lots of yield
    # sites — switching them all would be churn for no behavioural gain)
    # and translate here. Anything that doesn't match the
    # "event:…\ndata:…\n\n" frame is forwarded as a comment so we never
    # silently drop output.
    async def sse_events():
        async for chunk in event_generator():
            if not isinstance(chunk, str):
                continue
            text = chunk.strip()
            if not text:
                continue
            event_type = "message"
            data_str = text
            if text.startswith("event:"):
                # Format: "event: <type>\ndata: <json>"
                first_nl = text.find("\n")
                if first_nl != -1:
                    event_type = text[len("event:"):first_nl].strip()
                    rest = text[first_nl + 1 :]
                    if rest.startswith("data:"):
                        data_str = rest[len("data:"):].strip()
                    else:
                        data_str = rest
            elif text.startswith("data:"):
                data_str = text[len("data:"):].strip()
            yield {"event": event_type, "data": data_str}

    # EventSourceResponse from sse_starlette flushes per yield (no buffer
    # between Python and the AppRouter), sets Cache-Control: no-cache
    # plus no-transform so the AppRouter / nginx don't gzip-buffer the
    # stream, and emits a periodic ping to keep the connection alive.
    # Same pattern chat.py uses successfully — replaces the earlier
    # StreamingResponse where steps only arrived once the run finished.
    return EventSourceResponse(
        sse_events(),
        ping=5,
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ============================================================================
# Execution History
# ============================================================================

@router.get("/{agent_id}/executions", response_model=StandaloneAgentExecutionListResponse)
async def list_standalone_agent_executions(
    agent_id: str,
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List execution history for a standalone agent"""

    # Verify agent exists
    agent_check = await repo_query(
        "SELECT id FROM standalone_agents WHERE id = :id",
        {"id": agent_id}
    )
    if not agent_check:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Build query
    where_clause = "agent_id = :agent_id"
    params = {"agent_id": agent_id, "limit": limit, "offset": offset}

    if status:
        where_clause += " AND status = :status"
        params["status"] = status

    # Get total count
    count_result = await repo_query(
        f"SELECT COUNT(*) as count FROM standalone_agent_executions WHERE {where_clause}",
        params
    )
    total = count_result[0]["count"] if count_result else 0

    # Get executions
    executions_rows = await repo_query(
        f"""
        SELECT * FROM standalone_agent_executions
        WHERE {where_clause}
        ORDER BY created DESC
        LIMIT :limit OFFSET :offset
        """,
        params
    )

    executions = [StandaloneAgentExecutionResponse(**row) for row in executions_rows]

    return StandaloneAgentExecutionListResponse(executions=executions, total=total)


@router.get("/executions/{execution_id}", response_model=StandaloneAgentExecutionResponse)
async def get_standalone_agent_execution(execution_id: str):
    """Get details of a specific execution"""
    rows = await repo_query(
        "SELECT * FROM standalone_agent_executions WHERE id = :id",
        {"id": execution_id}
    )

    if not rows:
        raise HTTPException(status_code=404, detail="Execution not found")

    return StandaloneAgentExecutionResponse(**rows[0])


@router.delete("/executions/{execution_id}", status_code=204)
async def delete_standalone_agent_execution(execution_id: str):
    """Delete an execution record"""
    result = await repo_execute(
        "DELETE FROM standalone_agent_executions WHERE id = :id",
        {"id": execution_id}
    )

    if result == 0:
        raise HTTPException(status_code=404, detail="Execution not found")


@router.post("/executions/{execution_id}/cancel")
async def cancel_standalone_agent_execution(execution_id: str):
    """Cancel a running execution"""
    # Get execution
    execution = await repo_query(
        "SELECT * FROM standalone_agent_executions WHERE id = :id",
        {"id": execution_id},
        fetch_one=True
    )

    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    if execution["status"] not in ["running", "pending"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel execution with status: {execution['status']}"
        )

    # Update status to cancelled
    await repo_execute(
        """
        UPDATE standalone_agent_executions
        SET status = 'cancelled',
            completed_at = CURRENT_TIMESTAMP,
            error = 'Cancelled by user',
            updated = CURRENT_TIMESTAMP
        WHERE id = :id
        """,
        {"id": execution_id}
    )

    return {"message": "Execution cancelled successfully"}


@router.post("/executions/cleanup")
async def cleanup_abandoned_executions(
    timeout_minutes: int = Query(30, ge=1, le=1440, description="Mark executions older than N minutes as timeout")
):
    """
    Mark abandoned executions as timeout.

    This is useful for cleaning up executions that got stuck due to:
    - Network disconnections
    - Browser tab closures
    - Server restarts
    - Unhandled errors
    """
    # Calculate cutoff time
    from datetime import timedelta
    cutoff_time = (datetime.utcnow() - timedelta(minutes=timeout_minutes)).isoformat()

    # Mark old running executions as timeout
    result = await repo_execute(
        """
        UPDATE standalone_agent_executions
        SET status = 'timeout',
            completed_at = CURRENT_TIMESTAMP,
            error = 'Execution abandoned (exceeded timeout)',
            updated = CURRENT_TIMESTAMP
        WHERE status = 'running'
          AND created < :cutoff_time
        """,
        {"cutoff_time": cutoff_time}
    )

    return {
        "message": f"Cleanup complete",
        "timeout_minutes": timeout_minutes,
        "cleaned_up": result if result else 0
    }

