"""
Standalone-agent runtime — shared between the HTTP streaming endpoint and
the agent-team pattern executors.

The streaming endpoint at `/api/standalone-agents/{id}/execute/stream` used
to inline the entire LLM tool-calling loop. That made it impossible for any
other caller (most importantly the team pattern executors) to invoke a
standalone agent and observe its per-step events.

This module hosts the loop as `run_standalone_agent_events()` — an async
generator that yields dicts of shape:

    {"kind": "metadata"      , "execution_id": ..., "agent_id": ..., "query": ...}
    {"kind": "agent_step"    , "step_number": ..., "action": ..., "status": ..., "result": ...}
    {"kind": "chunk"         , "content": ...}
    {"kind": "tool_call"     , "tool": ..., "arguments": {...}}
    {"kind": "tool_result"   , "tool": ..., "result": ...}
    {"kind": "done"          , "execution_id": ..., "response": ..., "tool_count": ...}
    {"kind": "error"         , "error": ...}

The HTTP endpoint reformats these to SSE frames; pattern executors translate
them into team-level agent_messages rows so the team timeline sees every
tool call and step the agent made.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from api.services.tool_factory import ToolFactory
from api.services.llm_client import _normalize_openai_base, call_llm_chat_message
from api.services.memory_service import derive_task_pattern, get_memory_manager
from open_notebook.database.repository import repo_execute, repo_query


# Hard ceiling on tool-calling rounds per single agent invocation. Mirrors
# the limit the inline endpoint used; raising it doesn't help quality but
# does multiply LLM cost on a runaway model.
_MAX_TOOL_ITERATIONS = 5


async def run_standalone_agent_events(
    *,
    agent_data: Dict[str, Any],
    query: str,
    credential: Dict[str, Any],
    context_source_ids: Optional[List[str]] = None,
    notebook_id: Optional[str] = None,
    session_id: Optional[str] = None,
    record_execution: bool = True,
) -> AsyncIterator[Dict[str, Any]]:
    """
    Run a single standalone-agent turn and yield a stream of structured
    events.

    Parameters
    ----------
    agent_data:
        Row from `standalone_agents` (dict-like). Required keys: id, role,
        system_prompt, tool_ids, skill_ids, model_name, data_source_ids,
        notebook_id, config.
    query:
        The user (or upstream agent) prompt.
    credential:
        Resolved credential dict from `_credentials_store` — caller is
        responsible for picking the right one (agent's `model_name` override
        or the global default).
    context_source_ids:
        Optional override of the agent's configured `data_source_ids`. When
        None, falls back to whatever the agent was configured with.
    record_execution:
        When True (HTTP path) we INSERT a `standalone_agent_executions` row
        and emit memory side-effects. When False (team path) the team
        already owns its own execution row, and writing one here would
        clutter the standalone-agent history with team invocations — we
        skip both.
    """
    agent_id = agent_data["id"]
    execution_id = str(uuid.uuid4())
    start_time = datetime.utcnow()
    now = start_time.isoformat()

    if record_execution:
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
                "query": query,
                "status": "running",
                "session_id": session_id,
                "notebook_id": notebook_id or agent_data.get("notebook_id"),
                "context": json.dumps({
                    "source_ids": context_source_ids or json.loads(agent_data.get("data_source_ids") or "[]"),
                }),
                "started_at": now,
                "created": now,
                "updated": now,
            },
        )

    yield {
        "kind": "metadata",
        "execution_id": execution_id,
        "agent_id": agent_id,
        "query": query,
    }

    # --- Step 1: data sources ----------------------------------------------------
    source_ids = context_source_ids
    if source_ids is None:
        try:
            source_ids = json.loads(agent_data.get("data_source_ids") or "[]")
        except (json.JSONDecodeError, TypeError):
            source_ids = []

    context_content = ""
    if source_ids:
        yield {"kind": "agent_step", "step_number": 1,
               "action": f"Loading {len(source_ids)} data sources", "status": "running"}
        param_names = [f":source_{i}" for i in range(len(source_ids))]
        placeholders = ",".join(param_names)
        sql = f"SELECT id, title, full_text, source_type FROM sources WHERE id IN ({placeholders})"
        params = {f"source_{i}": sid for i, sid in enumerate(source_ids)}
        sources_rows = await repo_query(sql, params)
        if sources_rows:
            parts = []
            titles = []
            for s in sources_rows:
                titles.append(s.get("title") or "Untitled")
                parts.append(
                    f"Source: {s.get('title')} (Type: {s.get('source_type')})\n{s.get('full_text') or ''}\n"
                )
            context_content = "\n\n---\n\n".join(parts)
            yield {"kind": "agent_step", "step_number": 1,
                   "action": f"Loaded {len(sources_rows)} data sources",
                   "status": "completed", "result": f"Sources: {titles}"}
        else:
            yield {"kind": "agent_step", "step_number": 1,
                   "action": "No matching sources found", "status": "completed"}
    else:
        yield {"kind": "agent_step", "step_number": 1,
               "action": "No data sources configured", "status": "completed",
               "result": "Agent will respond without additional context"}

    # --- Step 2: tools -----------------------------------------------------------
    try:
        tool_ids = json.loads(agent_data.get("tool_ids") or "[]")
    except (json.JSONDecodeError, TypeError):
        tool_ids = []

    tools: List[Any] = []
    if tool_ids:
        yield {"kind": "agent_step", "step_number": 2,
               "action": "Loading tools", "status": "running"}
        tool_factory = ToolFactory()
        all_registry_tools = await tool_factory._get_registry_tools()
        for tool in all_registry_tools:
            tool_registry_id = None
            if hasattr(tool, "metadata") and isinstance(tool.metadata, dict):
                tool_registry_id = tool.metadata.get("_registry_id")
            elif hasattr(tool, "config") and isinstance(tool.config, dict):
                tool_registry_id = tool.config.get("_registry_id")
            elif hasattr(tool, "_tool_meta"):
                tool_registry_id = tool.__dict__.get("_tool_meta", {}).get("registry_id")
            if tool_registry_id in tool_ids:
                tools.append(tool)
        yield {"kind": "agent_step", "step_number": 2,
               "action": f"Loaded {len(tools)} tools", "status": "completed",
               "result": f"Tools: {[t.name for t in tools]}" if tools else "No matching tools found"}
    else:
        yield {"kind": "agent_step", "step_number": 2,
               "action": "No tools configured", "status": "completed",
               "result": "Agent will respond without tool access"}

    # --- Step 3: skills ----------------------------------------------------------
    try:
        skill_ids = json.loads(agent_data.get("skill_ids") or "[]")
    except (json.JSONDecodeError, TypeError):
        skill_ids = []

    skills: List[Any] = []
    if skill_ids:
        yield {"kind": "agent_step", "step_number": 3,
               "action": f"Loading {len(skill_ids)} skills", "status": "running"}
        from open_notebook.agents.skills import get_skill_registry
        registry = get_skill_registry()
        skill_names = []
        for sid in skill_ids:
            sk = registry.get_skill(sid)
            if sk and sk.enabled:
                skills.append(sk)
                skill_names.append(sk.name)
        yield {"kind": "agent_step", "step_number": 3,
               "action": f"Loaded {len(skills)} skills", "status": "completed",
               "result": f"Skills: {skill_names}" if skill_names else "No skills found"}
    else:
        yield {"kind": "agent_step", "step_number": 3,
               "action": "No skills configured", "status": "completed"}

    # --- Build system prompt -----------------------------------------------------
    system_prompt = agent_data.get("system_prompt") or f"You are a helpful {agent_data.get('role', 'agent')} assistant."
    try:
        cfg_raw = agent_data.get("config")
        cfg = json.loads(cfg_raw) if isinstance(cfg_raw, str) else (cfg_raw or {})
        role_template_key = cfg.get("role_template_key")
        if role_template_key:
            from api.services.prompt_loader import load_prompt
            template_text = await load_prompt(role_template_key, fallback=system_prompt)
            if template_text:
                system_prompt = template_text
    except Exception:
        pass

    if skills:
        system_prompt += "\n\nYou have access to the following skills:\n" + "\n".join(
            f"- {s.name}: {s.description}" for s in skills
        )
    if context_content:
        system_prompt += f"\n\nYou have access to the following data sources:\n\n{context_content}"

    # --- Memory recall -----------------------------------------------------------
    try:
        memory_manager = get_memory_manager()
        memory_bundle = await memory_manager.recall_for_agent(
            agent_id, query,
            state={"session_id": session_id,
                   "notebook_id": notebook_id or agent_data.get("notebook_id"),
                   "task": query},
        )
        memory_block = memory_manager.format_for_prompt(memory_bundle)
        if memory_block:
            system_prompt = memory_block + "\n" + system_prompt
            yield {"kind": "agent_step", "step_number": 3,
                   "action": "Recalled agent memory", "status": "completed",
                   "result": f"Episodic={len(memory_bundle.episodic)} Semantic={len(memory_bundle.semantic)} Procedural={len(memory_bundle.procedural)}"}
    except Exception:
        memory_bundle = None

    # --- LLM tool-calling loop ---------------------------------------------------
    yield {"kind": "agent_step", "step_number": 4,
           "action": "Executing query with LLM", "status": "running"}

    llm_messages: List[Dict[str, Any]] = []
    if system_prompt:
        llm_messages.append({"role": "system", "content": system_prompt})
    llm_messages.append({"role": "user", "content": query})

    full_response = ""
    tool_call_count = 0
    executed_tool_sequence: List[str] = []
    is_sap_ai_core = credential.get("provider") == "sap_ai_core"

    for iteration in range(_MAX_TOOL_ITERATIONS):
        request_payload: Dict[str, Any] = {
            "model": credential["model_name"],
            "messages": llm_messages,
            "max_tokens": 2000,
            "temperature": 0.7,
            "stream": True,
        }
        if tools:
            request_payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": getattr(t, "args_schema", {}).schema() if hasattr(t, "args_schema") else {},
                    },
                }
                for t in tools
            ]

        api_base = _normalize_openai_base(credential.get("base_url"))
        endpoint_url = f"{api_base}/chat/completions"

        try:
            current_content = ""
            current_tool_calls: List[Dict[str, Any]] = []

            if is_sap_ai_core:
                extra: dict = {}
                if request_payload.get("tools"):
                    extra["tools"] = request_payload["tools"]
                try:
                    assistant_msg = await call_llm_chat_message(
                        credential, llm_messages,
                        temperature=request_payload["temperature"],
                        max_tokens=request_payload["max_tokens"],
                        timeout=300.0,
                        extra_payload=extra or None,
                    )
                except RuntimeError as sap_err:
                    err = f"LLM API error: {sap_err}"
                    if record_execution:
                        await _mark_failed(execution_id, err)
                    yield {"kind": "error", "error": err}
                    return

                current_content = assistant_msg.get("content") or ""
                if current_content:
                    yield {"kind": "chunk", "content": current_content}
                for tc in assistant_msg.get("tool_calls") or []:
                    fn = tc.get("function") or {}
                    args = fn.get("arguments")
                    if isinstance(args, dict):
                        args = json.dumps(args)
                    current_tool_calls.append({
                        "id": tc.get("id") or "",
                        "function": {"name": fn.get("name") or "", "arguments": args or ""},
                    })
            else:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    async with client.stream(
                        "POST", endpoint_url,
                        headers={
                            "Authorization": f"Bearer {credential['api_key']}",
                            "Content-Type": "application/json",
                        },
                        json=request_payload,
                    ) as response:
                        if response.status_code != 200:
                            error_text = await response.aread()
                            err = f"LLM API error {response.status_code}: {error_text.decode()}"
                            if record_execution:
                                await _mark_failed(execution_id, err)
                            yield {"kind": "error", "error": err}
                            return
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
                                        if "choices" in chunk_data and chunk_data["choices"]:
                                            choice = chunk_data["choices"][0]
                                            finish_reason = choice.get("finish_reason")
                                            if finish_reason:
                                                break
                                            delta = choice.get("delta", {})
                                            content = delta.get("content", "")
                                            if content:
                                                current_content += content
                                                yield {"kind": "chunk", "content": content}
                                            if "tool_calls" in delta:
                                                for tc in delta["tool_calls"]:
                                                    tc_index = tc.get("index", 0)
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
                        except Exception:
                            if not current_content and not current_tool_calls:
                                raise

            if current_tool_calls:
                tool_call_count += len(current_tool_calls)
                llm_messages.append({
                    "role": "assistant",
                    "content": current_content or None,
                    "tool_calls": [
                        {"id": tc["id"], "type": "function", "function": tc["function"]}
                        for tc in current_tool_calls
                    ],
                })
                for tc in current_tool_calls:
                    tool_name = tc["function"]["name"]
                    tool_args_str = tc["function"]["arguments"]
                    executed_tool_sequence.append(tool_name)
                    try:
                        tool_args = json.loads(tool_args_str)
                    except json.JSONDecodeError:
                        tool_args = {}
                    yield {"kind": "tool_call", "tool": tool_name, "arguments": tool_args}

                    tool_result: Any = None
                    for t in tools:
                        if t.name == tool_name:
                            try:
                                tool_result = await t.ainvoke(tool_args)
                            except Exception as e:
                                tool_result = f"Error executing tool: {e}"
                            break
                    if tool_result is None:
                        tool_result = f"Tool {tool_name} not found"

                    llm_messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": str(tool_result),
                    })
                    yield {"kind": "tool_result", "tool": tool_name,
                           "result": str(tool_result)[:2000]}
                continue  # next loop iteration to let the LLM react

            full_response = current_content
            break
        except httpx.TimeoutException:
            err = "LLM request timed out"
            if record_execution:
                await _mark_failed(execution_id, err)
            yield {"kind": "error", "error": err}
            return
        except Exception as e:
            err = f"LLM call failed: {e}"
            if record_execution:
                await _mark_failed(execution_id, err)
            yield {"kind": "error", "error": err}
            return

    yield {"kind": "agent_step", "step_number": 4,
           "action": "Query execution completed", "status": "completed"}

    # --- Persist + memory + done ------------------------------------------------
    duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
    if record_execution:
        await repo_execute(
            """
            UPDATE standalone_agent_executions
            SET status = :status, result = :result, completed_at = :completed_at,
                updated = :updated, duration_ms = :duration_ms
            WHERE id = :id
            """,
            {
                "id": execution_id, "status": "completed",
                "result": json.dumps({"response": full_response}),
                "completed_at": datetime.utcnow().isoformat(),
                "updated": datetime.utcnow().isoformat(),
                "duration_ms": duration_ms,
            },
        )
        try:
            mm = get_memory_manager()
            summary = " ".join((full_response or "").strip().splitlines()[0:2])[:500] or "(no textual response)"
            await mm.record_episode(
                agent_id, agent_data.get("notebook_id") or "",
                f"Q: {query}\nA: {summary}",
                metadata={"execution_id": execution_id, "tool_count": tool_call_count, "duration_ms": duration_ms},
                importance=0.6 if tool_call_count else 0.4,
            )
            if executed_tool_sequence:
                await mm.record_tool_outcome(
                    agent_id, derive_task_pattern(query),
                    executed_tool_sequence, success=True,
                    duration_ms=duration_ms, example_input=query[:200],
                )
        except Exception:
            pass

    yield {
        "kind": "done",
        "execution_id": execution_id,
        "response": full_response,
        "tool_count": tool_call_count,
        "duration_ms": duration_ms,
    }


async def _mark_failed(execution_id: str, error: str) -> None:
    """Mark a standalone_agent_executions row as failed (best-effort)."""
    try:
        await repo_execute(
            "UPDATE standalone_agent_executions SET status = :s, error = :e, completed_at = :c, updated = :c WHERE id = :id",
            {"id": execution_id, "s": "failed", "e": error, "c": datetime.utcnow().isoformat()},
        )
    except Exception:
        pass


async def resolve_credential_for_agent(
    agent_data: Dict[str, Any],
    *,
    fallback_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Pick the credential a standalone agent should use. Honours the agent's
    `model_name` override; falls back to the global `language_model_id`
    setting (or `fallback_id` if the caller passes one).
    """
    from api.services.settings import get_setting
    from api.routers.credentials import _credentials_store

    model_id = agent_data.get("model_name") or fallback_id or await get_setting("language_model_id", "")
    cred = _credentials_store.get(model_id) if model_id else None
    if cred:
        return cred
    # Last resort: first active language credential.
    for cid, c in _credentials_store.items():
        if c.get("is_active") and c.get("model_type") == "language":
            return c
    return None
