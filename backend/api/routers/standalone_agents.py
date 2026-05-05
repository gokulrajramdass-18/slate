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
    valid_roles = ["planner", "researcher", "analyst", "synthesizer", "custom"]
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
        """Generate SSE events for execution progress"""
        try:
            print(f"DEBUG: Starting execution for agent {agent_id}")
            # Send metadata
            metadata_event = f"event: metadata\ndata: {json.dumps({'execution_id': execution_id, 'agent_id': agent_id, 'query': request.query})}\n\n"
            print(f"DEBUG: Sending metadata event: {metadata_event[:100]}...")
            yield metadata_event

            # Get LLM from configured models (same approach as agent teams)
            print(f"DEBUG: Getting LLM configuration...")
            from api.services.settings import get_setting
            from api.routers.credentials import _credentials_store

            # Get configured model from database
            language_model_id = await get_setting("language_model_id", "")
            model_id = agent_data.get("model_name") or language_model_id

            # Validate model exists in credentials store, fallback to default if not found
            credential = _credentials_store.get(model_id) if model_id else None

            if not credential and model_id:
                # Model not found, try using default
                print(f"DEBUG: Model {model_id} not found in credentials, falling back to default")
                model_id = language_model_id
                credential = _credentials_store.get(model_id) if model_id else None

            if not model_id or not credential:
                error_msg = "No AI model configured. Please add a model in Settings → Models."
                print(f"DEBUG: {error_msg}")
                yield f"event: error\ndata: {json.dumps({'error': error_msg})}\n\n"
                return

            print(f"DEBUG: Using model: {credential['model_name']} via {credential['base_url']}")

            # Build context from data sources - load actual content
            source_ids = json.loads(agent_data.get("data_source_ids") or "[]")
            context_content = ""

            print(f"DEBUG: source_ids type: {type(source_ids)}, value: {source_ids}, length: {len(source_ids) if source_ids else 0}")

            if source_ids and len(source_ids) > 0:
                print(f"DEBUG: Loading {len(source_ids)} data sources")
                yield f"event: agent_step\ndata: {json.dumps({'step_number': 1, 'action': f'Loading {len(source_ids)} data sources', 'status': 'running'})}\n\n"

                # Build query with named parameters for each source ID
                param_names = [f":source_{i}" for i in range(len(source_ids))]
                placeholders = ','.join(param_names)
                sql = f"SELECT id, title, full_text, source_type FROM sources WHERE id IN ({placeholders})"

                # Create params dict with named parameters
                params = {f"source_{i}": source_id for i, source_id in enumerate(source_ids)}

                print(f"DEBUG: SQL: {sql}")
                print(f"DEBUG: Params: {params}")

                sources_rows = await repo_query(sql, params)
                print(f"DEBUG: Got {len(sources_rows) if sources_rows else 0} sources")

                if sources_rows:
                    context_parts = []
                    source_titles = []
                    for source in sources_rows:
                        source_type = source.get("source_type", "unknown")
                        title = source.get("title", "Untitled")
                        full_text = source.get("full_text", "")
                        source_titles.append(title)

                        context_parts.append(f"Source: {title} (Type: {source_type})\n{full_text}\n")

                    context_content = "\n\n---\n\n".join(context_parts)

                yield f"event: agent_step\ndata: {json.dumps({'step_number': 1, 'action': f'Loaded {len(sources_rows)} data sources', 'status': 'completed', 'result': f'Sources: {source_titles}'})}\n\n"
            else:
                print(f"DEBUG: No data sources, showing step 1 as empty")
                # No data sources - still show step 1
                yield f"event: agent_step\ndata: {json.dumps({'step_number': 1, 'action': 'No data sources configured', 'status': 'completed', 'result': 'Agent will respond without additional context'})}\n\n"

            # Get tools - always show step 2
            tool_ids = json.loads(agent_data.get("tool_ids") or "[]")
            tools = []

            if tool_ids:
                yield f"event: agent_step\ndata: {json.dumps({'step_number': 2, 'action': 'Loading tools', 'status': 'running'})}\n\n"

                # Get all registry tools and filter by selected tool_ids
                tool_factory = ToolFactory()
                all_registry_tools = await tool_factory._get_registry_tools()

                # Filter to only selected tools by matching registry_id in metadata
                for tool in all_registry_tools:
                    tool_registry_id = None
                    if hasattr(tool, 'metadata') and isinstance(tool.metadata, dict):
                        tool_registry_id = tool.metadata.get('_registry_id')
                    elif hasattr(tool, 'config') and isinstance(tool.config, dict):
                        tool_registry_id = tool.config.get('_registry_id')
                    elif hasattr(tool, '_tool_meta'):
                        tool_registry_id = tool.__dict__['_tool_meta'].get('registry_id')

                    if tool_registry_id in tool_ids:
                        tools.append(tool)

                tool_names = [t.name for t in tools]
                yield f"event: agent_step\ndata: {json.dumps({'step_number': 2, 'action': f'Loaded {len(tools)} tools', 'status': 'completed', 'result': f'Tools: {tool_names}' if tool_names else 'No matching tools found'})}\n\n"
            else:
                # No tools - still show step 2
                yield f"event: agent_step\ndata: {json.dumps({'step_number': 2, 'action': 'No tools configured', 'status': 'completed', 'result': 'Agent will respond without tool access'})}\n\n"

            # Get skills - always show step 3
            skill_ids = json.loads(agent_data.get("skill_ids") or "[]")
            skills = []

            if skill_ids:
                yield f"event: agent_step\ndata: {json.dumps({'step_number': 3, 'action': f'Loading {len(skill_ids)} skills', 'status': 'running'})}\n\n"

                # Get skills from registry
                from open_notebook.agents.skills import get_skill_registry
                registry = get_skill_registry()

                skill_names = []
                for skill_id in skill_ids:
                    skill = registry.get_skill(skill_id)
                    if skill and skill.enabled:
                        skills.append(skill)
                        skill_names.append(skill.name)

                yield f"event: agent_step\ndata: {json.dumps({'step_number': 3, 'action': f'Loaded {len(skills)} skills', 'status': 'completed', 'result': f'Skills: {skill_names}' if skill_names else 'No skills found'})}\n\n"
            else:
                # No skills - still show step 3
                yield f"event: agent_step\ndata: {json.dumps({'step_number': 3, 'action': 'No skills configured', 'status': 'completed', 'result': 'Agent will respond without skills'})}\n\n"

            # Build system prompt
            system_prompt = agent_data.get("system_prompt") or f"You are a helpful {agent_data['role']} assistant."

            # Add skills to system prompt if available
            if skills:
                skill_descriptions = []
                for skill in skills:
                    skill_descriptions.append(f"- {skill.name}: {skill.description}")

                skills_text = "\n".join(skill_descriptions)
                system_prompt += f"\n\nYou have access to the following skills:\n{skills_text}\n\nYou can reference these skills in your responses when appropriate."

            # Add context from data sources if available
            if context_content:
                system_prompt += f"\n\nYou have access to the following data sources:\n\n{context_content}"

            # Execute query with tool calling loop
            execute_step = f"event: agent_step\ndata: {json.dumps({'step_number': 4, 'action': 'Executing query with LLM', 'status': 'running'})}\n\n"
            print(f"DEBUG: Sending execute step")
            yield execute_step

            # Prepare messages
            llm_messages = []
            if system_prompt:
                llm_messages.append({"role": "system", "content": system_prompt})
            llm_messages.append({"role": "user", "content": request.query})

            full_response = ""
            tool_call_count = 0
            max_tool_iterations = 5  # Prevent infinite loops

            print(f"DEBUG: Starting LLM call with tool loop...")

            # Use httpx to call LiteLLM proxy
            import httpx

            # Tool calling loop - continue until we get a final text response
            for iteration in range(max_tool_iterations):
                request_payload = {
                    "model": credential["model_name"],
                    "messages": llm_messages,
                    "max_tokens": 2000,
                    "temperature": 0.7,
                    "stream": True
                }

                # Add tools if available
                if tools:
                    tool_schemas = []
                    for tool in tools:
                        tool_schemas.append({
                            "type": "function",
                            "function": {
                                "name": tool.name,
                                "description": tool.description,
                                "parameters": getattr(tool, "args_schema", {}).schema() if hasattr(tool, "args_schema") else {}
                            }
                        })
                    request_payload["tools"] = tool_schemas
                    print(f"DEBUG: Including {len(tool_schemas)} tools in request (iteration {iteration})")

                endpoint_url = f"{credential['base_url']}/chat/completions"

                try:
                    current_content = ""
                    current_tool_calls = []

                    async with httpx.AsyncClient(timeout=120.0) as client:  # Increased timeout
                        async with client.stream(
                            "POST",
                            endpoint_url,
                            headers={
                                "Authorization": f"Bearer {credential['api_key']}",
                                "Content-Type": "application/json"
                            },
                            json=request_payload
                        ) as response:
                            if response.status_code != 200:
                                error_text = await response.aread()
                                error_msg = f"LLM API error {response.status_code}: {error_text.decode()}"
                                print(f"DEBUG: {error_msg}")
                                yield f"event: error\ndata: {json.dumps({'error': error_msg})}\n\n"
                                await repo_execute(
                                    "UPDATE standalone_agent_executions SET status = :status, error = :error, completed_at = :completed_at, updated = :updated WHERE id = :id",
                                    {"id": execution_id, "status": "failed", "error": error_msg, "completed_at": datetime.utcnow().isoformat(), "updated": datetime.utcnow().isoformat()}
                                )
                                return

                            # Stream response chunks with better error handling
                            try:
                                async for line in response.aiter_lines():
                                    if not line:
                                        continue

                                    if line.startswith("data: "):
                                        data_str = line[6:]
                                        if data_str == "[DONE]":
                                            break

                                        try:
                                            chunk_data = json.loads(data_str)
                                            if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                                                choice = chunk_data["choices"][0]

                                                # Check for finish_reason to properly end the stream
                                                finish_reason = choice.get("finish_reason")
                                                if finish_reason:
                                                    print(f"DEBUG: Stream finished with reason: {finish_reason}")
                                                    break

                                                delta = choice.get("delta", {})

                                                # Handle text content
                                                content = delta.get("content", "")
                                                if content:
                                                    current_content += content
                                                    chunk_event = f"event: chunk\ndata: {json.dumps({'content': content})}\n\n"
                                                    yield chunk_event

                                                # Handle tool calls
                                                if "tool_calls" in delta:
                                                    for tc in delta["tool_calls"]:
                                                        tc_index = tc.get("index", 0)
                                                        # Extend list if needed
                                                        while len(current_tool_calls) <= tc_index:
                                                            current_tool_calls.append({"id": "", "function": {"name": "", "arguments": ""}})

                                                        if "id" in tc:
                                                            current_tool_calls[tc_index]["id"] = tc["id"]
                                                        if "function" in tc:
                                                            if "name" in tc["function"]:
                                                                current_tool_calls[tc_index]["function"]["name"] = tc["function"]["name"]
                                                            if "arguments" in tc["function"]:
                                                                current_tool_calls[tc_index]["function"]["arguments"] += tc["function"]["arguments"]
                                        except json.JSONDecodeError:
                                            continue
                            except Exception as stream_err:
                                print(f"DEBUG: Stream read error: {stream_err}")
                                # If we got partial content, continue with it
                                if not current_content and not current_tool_calls:
                                    raise

                    # Check if we got tool calls
                    if current_tool_calls:
                        tool_call_count += len(current_tool_calls)
                        print(f"DEBUG: LLM requested {len(current_tool_calls)} tool calls")

                        # Add assistant message with tool calls
                        llm_messages.append({
                            "role": "assistant",
                            "content": current_content or None,
                            "tool_calls": [
                                {
                                    "id": tc["id"],
                                    "type": "function",
                                    "function": tc["function"]
                                }
                                for tc in current_tool_calls
                            ]
                        })

                        # Execute each tool call
                        for tc in current_tool_calls:
                            tool_name = tc["function"]["name"]
                            tool_args_str = tc["function"]["arguments"]

                            try:
                                tool_args = json.loads(tool_args_str)
                            except json.JSONDecodeError:
                                tool_args = {}

                            print(f"DEBUG: Executing tool: {tool_name} with args: {tool_args}")
                            yield f"event: tool_call\ndata: {json.dumps({'tool': tool_name, 'arguments': tool_args})}\n\n"

                            # Find and execute the tool
                            tool_result = None
                            for tool in tools:
                                if tool.name == tool_name:
                                    try:
                                        tool_result = await tool.arun(**tool_args)
                                        print(f"DEBUG: Tool {tool_name} result: {str(tool_result)[:200]}")
                                    except Exception as e:
                                        tool_result = f"Error executing tool: {str(e)}"
                                        print(f"DEBUG: Tool {tool_name} error: {e}")
                                    break

                            if tool_result is None:
                                tool_result = f"Tool {tool_name} not found"

                            # Add tool result to messages
                            llm_messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": str(tool_result)
                            })

                            yield f"event: tool_result\ndata: {json.dumps({'tool': tool_name, 'result': str(tool_result)[:500]})}\n\n"

                        # Continue loop to get final response
                        continue

                    # No tool calls, we have the final response
                    full_response = current_content
                    break

                except httpx.TimeoutException:
                    error_msg = "LLM request timed out"
                    print(f"DEBUG: {error_msg}")
                    await repo_execute(
                        "UPDATE standalone_agent_executions SET status = :status, error = :error, completed_at = :completed_at, updated = :updated WHERE id = :id",
                        {"id": execution_id, "status": "failed", "error": error_msg, "completed_at": datetime.utcnow().isoformat(), "updated": datetime.utcnow().isoformat()}
                    )
                    yield f"event: error\ndata: {json.dumps({'error': error_msg})}\n\n"
                    return
                except Exception as e:
                    error_msg = f"LLM call failed: {str(e)}"
                    print(f"DEBUG: {error_msg}")
                    await repo_execute(
                        "UPDATE standalone_agent_executions SET status = :status, error = :error, completed_at = :completed_at, updated = :updated WHERE id = :id",
                        {"id": execution_id, "status": "failed", "error": error_msg, "completed_at": datetime.utcnow().isoformat(), "updated": datetime.utcnow().isoformat()}
                    )
                    yield f"event: error\ndata: {json.dumps({'error': error_msg})}\n\n"
                    return

            print(f"DEBUG: Streaming complete, response length: {len(full_response)}")
            yield f"event: agent_step\ndata: {json.dumps({'step_number': 4, 'action': 'Query execution completed', 'status': 'completed'})}\n\n"

            # Calculate duration
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Store result
            await repo_execute(
                """
                UPDATE standalone_agent_executions
                SET status = :status, result = :result, completed_at = :completed_at,
                    updated = :updated, duration_ms = :duration_ms
                WHERE id = :id
                """,
                {
                    "id": execution_id,
                    "status": "completed",
                    "result": json.dumps({"response": full_response}),
                    "completed_at": datetime.utcnow().isoformat(),
                    "updated": datetime.utcnow().isoformat(),
                    "duration_ms": duration_ms,
                }
            )

            yield f"event: done\ndata: {json.dumps({'execution_id': execution_id})}\n\n"
            print(f"DEBUG: Execution complete for {execution_id}")

        except Exception as e:
            print(f"DEBUG: Error during execution: {str(e)}")
            import traceback
            traceback.print_exc()
            # Mark as failed
            await repo_execute(
                """
                UPDATE standalone_agent_executions
                SET status = :status, error = :error, completed_at = :completed_at, updated = :updated
                WHERE id = :id
                """,
                {
                    "id": execution_id,
                    "status": "failed",
                    "error": str(e),
                    "completed_at": datetime.utcnow().isoformat(),
                    "updated": datetime.utcnow().isoformat(),
                }
            )

            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
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

