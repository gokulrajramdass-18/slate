"""
LangGraph-based dynamic agent orchestrator.

Provides:
- AI-driven task decomposition
- Dynamic execution planning
- Full streaming observability (every step, every tool call)
- Automatic result aggregation
- Real-time progress updates to UI
"""
import asyncio
import json
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Any, Annotated, Literal, TypedDict
import operator

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import BaseTool

from open_notebook.database.repository import repo_query, repo_execute


class DynamicAgentState(TypedDict):
    """State for dynamic agent execution."""

    # Input
    query: str
    role: str
    team_id: str
    execution_id: str

    # Context
    available_sources: List[Dict[str, Any]]
    available_tools: List[str]
    source_context: str

    # Planning
    analysis: Optional[Dict[str, Any]]
    plan: List[Dict[str, Any]]  # [{"step": "...", "tool": "...", "args": {...}}]
    current_step: int

    # Execution
    step_results: Annotated[List[Dict[str, Any]], operator.add]  # Accumulate results
    tool_calls: Annotated[List[Dict[str, Any]], operator.add]  # Track all tool invocations
    errors: Annotated[List[str], operator.add]  # Track errors

    # Output
    final_answer: Optional[str]
    status: str  # "planning", "executing", "aggregating", "completed", "failed"

    # Multi-Agent Orchestration
    orchestration_mode: str  # "single" | "multi"
    assigned_agents: List[Dict[str, Any]]  # List of agent records from database
    task_records: List[Dict[str, Any]]  # Created agent_tasks records
    agent_results: Annotated[List[Dict[str, Any]], operator.add]  # Results from each agent
    messages: Annotated[List[Dict[str, Any]], operator.add]  # Coordination messages


class LangGraphOrchestrator:
    """
    Dynamic agent orchestrator using LangGraph.

    Features:
    - AI analyzes query and creates execution plan
    - Dynamic tool selection based on available tools and data sources
    - Streams every action (steps, tool calls, LLM reasoning) to UI
    - Handles errors gracefully with retries
    - Aggregates all results into final answer
    """

    def __init__(
        self,
        team_id: str,
        execution_id: str,
        llm: Any,
        tools: List[BaseTool],
        system_prompt: Optional[str] = None
    ):
        """
        Initialize orchestrator.

        Args:
            team_id: Agent team ID
            execution_id: Execution ID for tracking
            llm: Language model instance
            tools: List of available tools
            system_prompt: Optional custom system prompt to use for execution
                          If None, uses hardcoded default (can be loaded from DB via
                          load_prompt("orchestration_base_system") in calling code)
        """
        self.team_id = team_id
        self.execution_id = execution_id
        self.llm = llm
        self.tools = tools
        # Default fallback - callers can load from DB and pass as parameter
        self.system_prompt = system_prompt or "You are a helpful AI assistant with expertise in research and analysis."
        # Bind tools to LLM for tool calling
        if tools:
            self.llm_with_tools = self.llm.bind_tools(tools)
        else:
            self.llm_with_tools = self.llm
        self.graph = None
        self.step_counter = 0  # Track step numbers for saving to DB
        self.system_agent_id = None  # Will be set to first agent in team for FK constraint

    async def _maybe_run_pattern(
        self,
        query: str,
        context_source_ids: Optional[List[str]],
        notebook_id: Optional[str],
        *,
        resume: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        If this team has an orchestration_pattern set, run the matching
        PatternExecutor and return its result in the same shape execute()
        normally returns. Returns None to mean "no pattern — fall through to
        the legacy LangGraph path".

        ``resume`` is set by the resume-after-clarification endpoint:
            { "checkpoint": <prior pattern checkpoint>,
              "pending_answers": {agent_id: user_answer} }
        """
        # Local imports keep the module load order safe — patterns/ pulls in
        # the A2A bus which has its own deps.
        from open_notebook.agents.patterns import (
            PatternContext,
            StepEvent,
            get_executor,
        )
        from open_notebook.agents.patterns.clarification import ClarificationPending
        from open_notebook.agents.a2a.team_message_bus import A2ATeamMessageBus

        team_rows = await repo_query(
            "SELECT * FROM agent_teams WHERE id = :id",
            {"id": self.team_id},
        )
        if not team_rows:
            return None
        team = team_rows[0]
        pattern = team.get("orchestration_pattern")
        if not pattern:
            return None
        executor = get_executor(pattern)
        if executor is None:
            print(f"[LangGraph] Unknown orchestration_pattern={pattern}; "
                  f"falling back to legacy path.")
            return None

        agents = await repo_query(
            "SELECT * FROM agent_instances WHERE team_id = :team_id "
            "ORDER BY order_index ASC, created ASC",
            {"team_id": self.team_id},
        )
        if not agents:
            # Pattern executors require at least one agent. Fall through so
            # the legacy single-agent path kicks in.
            return None

        # Parse pattern_config JSON.
        pcfg_raw = team.get("pattern_config")
        try:
            pattern_config = json.loads(pcfg_raw) if pcfg_raw else {}
        except (json.JSONDecodeError, TypeError):
            pattern_config = {}

        # Team-level config carries auto_answer and other run-time toggles.
        try:
            team_config = json.loads(team.get("config")) if team.get("config") else {}
        except (json.JSONDecodeError, TypeError):
            team_config = {}
        auto_answer = bool(team_config.get("auto_answer"))

        user_id = team.get("created_by") or "system"

        # Build A2A bus and register every agent that has a standalone-agent
        # link. Agents without a link will be invoked via the direct-LLM
        # fallback in PatternContext.invoke_agent (still fully functional;
        # just not over the A2A wire).
        bus = A2ATeamMessageBus(team_id=self.team_id, user_id=user_id)
        try:
            from open_notebook.domain.standalone_agent import StandaloneAgent

            for a in agents:
                sa_id = a.get("standalone_agent_id")
                if not sa_id:
                    continue
                try:
                    sa = await StandaloneAgent.get(sa_id)
                    if sa is not None:
                        await bus.register_local_agent(agent_id=a["id"], standalone_agent=sa)
                except Exception as reg_err:  # registration failures are non-fatal
                    print(f"[LangGraph] Bus register failed for {a['id']}: {reg_err}")
        except Exception as imp_err:
            print(f"[LangGraph] StandaloneAgent import failed; bus disabled: {imp_err}")
            bus = None

        # Record execution. On the first run we INSERT; on resume the row
        # already exists (the resume endpoint reuses the same execution_id),
        # so we INSERT-OR-IGNORE and then bump the row back to running.
        # Without OR IGNORE, the second pass would 500 with "UNIQUE
        # constraint failed: agent_executions.id".
        now = datetime.utcnow().isoformat()
        await repo_execute(
            """INSERT OR IGNORE INTO agent_executions
               (id, team_id, query, status, started_at)
               VALUES (:id, :team_id, :query, :status, :started_at)""",
            {
                "id": self.execution_id,
                "team_id": self.team_id,
                "query": query,
                "status": "running",
                "started_at": now,
            },
        )
        if resume:
            await repo_execute(
                "UPDATE agent_executions SET status = 'running', completed_at = NULL WHERE id = :id",
                {"id": self.execution_id},
            )

        ctx = PatternContext(
            team_id=self.team_id,
            user_id=user_id,
            query=query,
            team=team,
            agents=list(agents),
            pattern_config=pattern_config,
            llm=self.llm,
            bus=bus,
            notebook_id=notebook_id,
            context_source_ids=context_source_ids,
            execution_id=self.execution_id,
            auto_answer=auto_answer,
            pending_answers=dict((resume or {}).get("pending_answers") or {}),
            resumed_from=(resume or {}).get("checkpoint"),
        )

        try:
            result = await executor.execute(ctx)
        except ClarificationPending as cp:
            # Pause the run. Persist the question + checkpoint so the resume
            # endpoint has everything it needs to continue. The executor
            # already emitted a task_result event flagged is_clarification.
            now2 = datetime.utcnow().isoformat()
            clarif_id = str(uuid.uuid4())
            await repo_execute(
                """INSERT INTO agent_clarifications
                   (id, execution_id, team_id, sender_agent_id, sender_name,
                    sender_role, question, status, checkpoint, created)
                   VALUES (:id, :exec, :team, :sa, :sn, :sr, :q, 'pending',
                           :ck, :c)""",
                {
                    "id": clarif_id,
                    "exec": self.execution_id,
                    "team": self.team_id,
                    "sa": cp.sender_agent_id,
                    "sn": cp.sender_name,
                    "sr": cp.sender_role,
                    "q": cp.question,
                    "ck": json.dumps({
                        "pattern": pattern,
                        "state": cp.checkpoint,
                        "query": query,
                    }),
                    "c": now2,
                },
            )
            await repo_execute(
                """UPDATE agent_executions
                   SET status = :status
                   WHERE id = :id""",
                {"id": self.execution_id, "status": "awaiting_input"},
            )
            messages = await repo_query(
                """SELECT id, sender_id, recipient_id, message_type, content, metadata, created
                   FROM agent_messages
                   WHERE team_id = :team_id AND created >= :since
                   ORDER BY created ASC""",
                {"team_id": self.team_id, "since": now},
            )
            return {
                "id": self.execution_id,
                "team_id": self.team_id,
                "query": query,
                "status": "awaiting_input",
                "result": None,
                "steps": [],
                "tasks": [],
                "messages": messages,
                "tool_calls": [],
                "errors": [],
                "pattern": pattern,
                "clarification": {
                    "id": clarif_id,
                    "question": cp.question,
                    "sender_agent_id": cp.sender_agent_id,
                    "sender_name": cp.sender_name,
                    "sender_role": cp.sender_role,
                },
                "started_at": now,
                "completed_at": None,
            }
        except Exception as e:
            print(f"[LangGraph] Pattern '{pattern}' failed: {e}")
            await repo_execute(
                """UPDATE agent_executions
                   SET status = :status, result = :result, completed_at = :completed_at
                   WHERE id = :id""",
                {
                    "id": self.execution_id,
                    "status": "failed",
                    "result": json.dumps({"error": str(e), "pattern": pattern}),
                    "completed_at": datetime.utcnow().isoformat(),
                },
            )
            raise

        completed_at = datetime.utcnow().isoformat()
        await repo_execute(
            """UPDATE agent_executions
               SET status = :status, result = :result, completed_at = :completed_at
               WHERE id = :id""",
            {
                "id": self.execution_id,
                "status": "completed",
                "result": json.dumps({
                    "output": result.output,
                    "pattern": pattern,
                    "agent_results": result.agent_results,
                    "metadata": result.metadata,
                }),
                "completed_at": completed_at,
            },
        )

        # Pull the timeline for the UI from agent_messages — every executor
        # writes there via PatternContext.emit().
        messages = await repo_query(
            """SELECT id, sender_id, recipient_id, message_type, content, metadata, created
               FROM agent_messages
               WHERE team_id = :team_id AND created >= :since
               ORDER BY created ASC""",
            {"team_id": self.team_id, "since": now},
        )

        return {
            "id": self.execution_id,
            "team_id": self.team_id,
            "query": query,
            "status": "completed",
            "result": result.output,
            "steps": result.agent_results,
            "tasks": [],
            "messages": messages,
            "tool_calls": [],
            "errors": [],
            "pattern": pattern,
            "pattern_metadata": result.metadata,
            "started_at": now,
            "completed_at": completed_at,
        }

    async def _maybe_stream_pattern(
        self,
        query: str,
        context_source_ids: Optional[List[str]],
        notebook_id: Optional[str],
        *,
        resume: Optional[Dict[str, Any]] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Streaming counterpart to _maybe_run_pattern. Runs the pattern
        executor and returns a list of SSE events to yield. Returns None when
        the team has no pattern (legacy fallback) or no agents.
        """
        # Pattern execution isn't a true generator — the executor runs to
        # completion. We collect events in-flight via the on_step callback,
        # then yield the metadata + step events + final answer in order.
        result_obj = await self._maybe_run_pattern(
            query=query,
            context_source_ids=context_source_ids,
            notebook_id=notebook_id,
            resume=resume,
        )
        if result_obj is None:
            return None

        # Resolve agent IDs → display names so the UI can render the timeline
        # without a second round-trip. The same dict also drives the
        # message-event payload below.
        agent_rows = await repo_query(
            "SELECT id, name, role FROM agent_instances WHERE team_id = :t",
            {"t": self.team_id},
        )
        name_by_id = {a["id"]: a.get("name") for a in agent_rows}
        role_by_id = {a["id"]: a.get("role") for a in agent_rows}

        def _name(aid: Optional[str]) -> Optional[str]:
            if not aid or aid == "system":
                return "System"
            return name_by_id.get(aid) or aid[:8]

        events: List[Dict[str, Any]] = []
        events.append({
            "event": "metadata",
            "data": {
                "execution_id": self.execution_id,
                "team_id": self.team_id,
                "query": query,
                "pattern": result_obj.get("pattern"),
                "pattern_metadata": result_obj.get("pattern_metadata") or {},
            },
        })
        for msg in result_obj.get("messages", []):
            sender = msg.get("sender_id")
            recipient = msg.get("recipient_id")
            # The metadata column stores JSON-encoded text (PatternContext.emit
            # writes json.dumps(...)). Decode it before shipping so the
            # frontend gets a real object — the Message Details dialog reads
            # individual keys (role, agent_name, is_clarification, ...) and
            # would otherwise see a string.
            raw_meta = msg.get("metadata")
            if isinstance(raw_meta, str):
                try:
                    raw_meta = json.loads(raw_meta) if raw_meta else None
                except (json.JSONDecodeError, TypeError):
                    pass
            # Frontend's AgentMessage type uses from_/to_ + timestamp; emit
            # both shapes so the existing MessageTimeline renders correctly
            # without changing the wire contract for legacy consumers.
            payload = {
                "id": msg.get("id"),
                "sender_id": sender,
                "recipient_id": recipient,
                "from_agent_id": sender,
                "to_agent_id": recipient,
                "from_agent_name": _name(sender),
                "to_agent_name": _name(recipient) if recipient else None,
                "message_type": msg.get("message_type"),
                "content": msg.get("content"),
                "metadata": raw_meta,
                "created": msg.get("created"),
                "timestamp": msg.get("created"),
            }
            events.append({"event": "message", "data": payload})

        # Paused-for-clarification path: emit a dedicated event so the UI can
        # pop a dialog. We do NOT emit `done` — the execution is awaiting
        # input, not finished.
        if result_obj.get("status") == "awaiting_input":
            cl = result_obj.get("clarification") or {}
            events.append({
                "event": "awaiting_user_input",
                "data": {
                    "execution_id": self.execution_id,
                    "team_id": self.team_id,
                    "clarification_id": cl.get("id"),
                    "question": cl.get("question"),
                    "sender_agent_id": cl.get("sender_agent_id"),
                    "sender_name": cl.get("sender_name"),
                    "sender_role": cl.get("sender_role"),
                    "pattern": result_obj.get("pattern"),
                },
            })
            return events
        # `done` is the event the existing frontend SSE client already maps
        # to onComplete, which sets currentExecution and unlocks the Result
        # tab. We pass the synthesized final answer here so the user lands
        # on a clear deliverable.
        events.append({
            "event": "done",
            "data": {
                "id": self.execution_id,
                "team_id": self.team_id,
                "query": query,
                "status": "completed",
                "result": result_obj.get("result"),
                "pattern": result_obj.get("pattern"),
                "pattern_metadata": result_obj.get("pattern_metadata") or {},
                "messages": [],   # already streamed individually above
                "tasks": [],
                "steps": [
                    {
                        **(s if isinstance(s, dict) else {}),
                        "agent_name": _name((s or {}).get("agent_id")) if isinstance(s, dict) else None,
                    }
                    for s in (result_obj.get("steps") or [])
                ],
                "started_at": result_obj.get("started_at"),
                "completed_at": result_obj.get("completed_at"),
            },
        })
        events.append({
            "event": "complete",
            "data": {
                "status": "completed",
                "completed_at": result_obj.get("completed_at"),
            },
        })
        return events

    async def _save_workflow_step(self, step_name: str, output: Any, status: str = "completed", error: Optional[str] = None):
        """
        Save a workflow step to the database.

        Args:
            step_name: Name of the step
            output: Step output (dict or string)
            status: Step status (completed, failed, in_progress)
            error: Optional error message if failed
        """
        self.step_counter += 1
        now = datetime.utcnow().isoformat()

        # Convert output to string if it's a dict
        output_str = json.dumps(output) if isinstance(output, dict) else str(output)

        # If there's an error, include it in the result
        if error:
            result_str = f"ERROR: {error}\n\nOutput: {output_str}"
        else:
            result_str = output_str

        # Get an agent_id from the team (required by FK constraint)
        if not self.system_agent_id:
            try:
                agent_rows = await repo_query(
                    "SELECT id FROM agent_instances WHERE team_id = :team_id LIMIT 1",
                    {"team_id": self.team_id}
                )
                if agent_rows:
                    self.system_agent_id = agent_rows[0]["id"]
                else:
                    # No agents in team, skip saving (shouldn't happen but handle gracefully)
                    print(f"[LangGraph] Warning: No agents found for team {self.team_id}, cannot save steps")
                    return
            except Exception as e:
                print(f"[LangGraph] Warning: Could not fetch agent_id: {e}")
                return

        try:
            # Execute with FK checks disabled in a single transaction
            # (repo_execute creates new connections, so PRAGMA doesn't persist)
            from open_notebook.database.repository import db_connection

            async with db_connection() as db:
                # Disable FK checks
                await db.execute("PRAGMA foreign_keys = OFF", {})

                # Insert step
                await db.execute(
                    """INSERT INTO workflow_steps
                       (id, execution_id, step_number, agent_id, agent_name, action, status, started_at, completed_at, result)
                       VALUES (:id, :execution_id, :step_number, :agent_id, :agent_name, :action, :status, :started_at, :completed_at, :result)""",
                    {
                        "id": str(uuid.uuid4()),
                        "execution_id": self.execution_id,
                        "step_number": self.step_counter,
                        "agent_id": self.system_agent_id,  # Use team's agent for FK constraint
                        "agent_name": "Orchestrator",
                        "action": step_name,
                        "status": status,
                        "started_at": now,
                        "completed_at": now if status == "completed" else None,
                        "result": result_str
                    }
                )

                # Re-enable FK checks
                await db.execute("PRAGMA foreign_keys = ON", {})

            print(f"[LangGraph] ✓ Saved step {self.step_counter}: {step_name} ({status})")
        except Exception as e:
            print(f"[LangGraph] Warning: Failed to save step to database: {e}")

    async def _save_task(self, task_data: Dict[str, Any]):
        """
        Save a task to the database.

        Args:
            task_data: Task information from SSE event
        """
        now = datetime.utcnow().isoformat()

        try:
            from open_notebook.database.repository import db_connection

            async with db_connection() as db:
                await db.execute("PRAGMA foreign_keys = OFF", {})

                await db.execute(
                    """INSERT INTO agent_tasks
                       (id, team_id, execution_id, assignee_id, title, description, status, priority, started_at, created, updated)
                       VALUES (:id, :team_id, :execution_id, :assignee_id, :title, :description, :status, :priority, :started_at, :created, :updated)""",
                    {
                        "id": task_data.get("id") or task_data.get("task_id") or str(uuid.uuid4()),
                        "team_id": self.team_id,
                        "execution_id": self.execution_id,
                        "assignee_id": task_data.get("agent_id") or task_data.get("assigned_agent_id"),
                        "title": task_data.get("title") or "Untitled Task",
                        "description": task_data.get("description") or task_data.get("task_description") or "",
                        "status": task_data.get("status", "pending"),
                        "priority": task_data.get("priority", 0),
                        "started_at": task_data.get("started_at") or task_data.get("created_at") or now,
                        "created": now,
                        "updated": now
                    }
                )

                await db.execute("PRAGMA foreign_keys = ON", {})

            print(f"[LangGraph] ✓ Saved task: {task_data.get('title', 'Untitled')}")
        except Exception as e:
            print(f"[LangGraph] Warning: Failed to save task to database: {e}")

    async def _save_message(self, message_data: Dict[str, Any]):
        """
        Save a message to the database.

        Args:
            message_data: Message information from SSE event
        """
        now = datetime.utcnow().isoformat()

        try:
            from open_notebook.database.repository import db_connection

            async with db_connection() as db:
                await db.execute("PRAGMA foreign_keys = OFF", {})

                # Convert metadata to JSON string if it's a dict
                metadata_str = None
                if message_data.get("metadata"):
                    metadata_str = json.dumps(message_data["metadata"]) if isinstance(message_data["metadata"], dict) else message_data["metadata"]

                await db.execute(
                    """INSERT INTO agent_messages
                       (id, team_id, execution_id, sender_id, recipient_id, message_type, content, metadata, created)
                       VALUES (:id, :team_id, :execution_id, :sender_id, :recipient_id, :message_type, :content, :metadata, :created)""",
                    {
                        "id": message_data.get("id") or str(uuid.uuid4()),
                        "team_id": self.team_id,
                        "execution_id": self.execution_id,
                        "sender_id": message_data.get("from_agent_id") or message_data.get("sender_id") or "system",
                        "recipient_id": message_data.get("to_agent_id") or message_data.get("recipient_id"),
                        "message_type": message_data.get("message_type", "chat"),
                        "content": message_data.get("content") or message_data.get("message") or "",
                        "metadata": metadata_str,
                        "created": message_data.get("created") or message_data.get("timestamp") or now
                    }
                )

                await db.execute("PRAGMA foreign_keys = ON", {})

            print(f"[LangGraph] ✓ Saved message: {message_data.get('message_type', 'chat')}")
        except Exception as e:
            print(f"[LangGraph] Warning: Failed to save message to database: {e}")

    def _build_graph(self) -> StateGraph:
        """Build the dynamic execution graph with multi-agent support."""

        workflow = StateGraph(DynamicAgentState)

        # ====== EXISTING SINGLE-AGENT NODES ======
        workflow.add_node("analyze_query", self._analyze_query_node)
        workflow.add_node("create_plan", self._create_plan_node)
        workflow.add_node("execute_step", self._execute_step_node)
        workflow.add_node("aggregate_results", self._aggregate_node)
        workflow.add_node("handle_error", self._handle_error_node)

        # ====== NEW MULTI-AGENT NODES ======
        workflow.add_node("identify_agents", self._identify_agents_node)
        workflow.add_node("create_tasks", self._create_tasks_node)
        workflow.add_node("execute_multi_agent", self._execute_multi_agent_node)
        workflow.add_node("consolidate_multi_results", self._consolidate_multi_results_node)

        # Set entry point
        workflow.set_entry_point("analyze_query")

        # ====== CONDITIONAL ROUTING AFTER ANALYSIS ======
        # Route to single-agent or multi-agent based on query complexity
        workflow.add_conditional_edges(
            "analyze_query",
            self._route_orchestration,
            {
                "single": "create_plan",  # Existing single-agent path
                "multi": "identify_agents"  # New multi-agent path
            }
        )

        # ====== SINGLE-AGENT PATH (EXISTING) ======
        workflow.add_edge("create_plan", "execute_step")

        # Conditional routing after execution
        workflow.add_conditional_edges(
            "execute_step",
            self._should_continue,
            {
                "continue": "execute_step",  # Loop back for next step
                "aggregate": "aggregate_results",  # Done, synthesize
                "error": "handle_error"  # Handle error
            }
        )

        workflow.add_edge("handle_error", "aggregate_results")
        workflow.add_edge("aggregate_results", END)

        # ====== MULTI-AGENT PATH (NEW) ======
        # Conditional routing after identify_agents
        # If no agents found (orchestration_mode = "single"), route to create_plan → execute_step
        # Otherwise continue with create_plan → create_tasks (multi-agent needs plan too!)
        def route_after_identify_agents(state: DynamicAgentState) -> str:
            """Route based on whether agents were found."""
            mode = state.get("orchestration_mode", "multi")
            if mode == "single":
                print(f"[LangGraph] No agents found, falling back to single-agent path")
                return "single"
            else:
                return "multi"

        workflow.add_conditional_edges(
            "identify_agents",
            route_after_identify_agents,
            {
                "single": "create_plan",  # Fallback: create_plan → execute_step → aggregate
                "multi": "create_plan"    # Multi-agent: create_plan → create_tasks → ...
            }
        )

        # After create_plan, route based on orchestration_mode
        def route_after_create_plan(state: DynamicAgentState) -> str:
            """Route to either single-agent execution or multi-agent task creation."""
            mode = state.get("orchestration_mode", "single")
            if mode == "multi":
                return "create_tasks"
            else:
                return "execute_step"

        workflow.add_conditional_edges(
            "create_plan",
            route_after_create_plan,
            {
                "execute_step": "execute_step",  # Single-agent path
                "create_tasks": "create_tasks"   # Multi-agent path
            }
        )

        workflow.add_edge("create_tasks", "execute_multi_agent")
        workflow.add_edge("execute_multi_agent", "consolidate_multi_results")
        workflow.add_edge("consolidate_multi_results", END)

        return workflow.compile()

    async def _analyze_query_node(self, state: DynamicAgentState) -> Dict[str, Any]:
        """
        Analyze query complexity and requirements.

        AI determines:
        - What data sources are needed
        - What tools should be used
        - Query complexity level
        - Estimated number of steps
        """

        print(f"[LangGraph] Analyzing query: {state['query'][:100]}...")

        # Build context about available resources
        tools_description = "\n".join([
            f"- {tool}: {self._get_tool_description(tool)}"
            for tool in state["available_tools"]
        ])

        sources_description = "\n".join([
            f"- {src['title']} ({src['source_type']})"
            for src in state["available_sources"]
        ])

        analysis_prompt = f"""{self.system_prompt}

You are analyzing a user query to plan its execution.

Query: {state["query"]}
Role: {state["role"]}

Available Tools:
{tools_description if tools_description else "None"}

Available Data Sources:
{sources_description if sources_description else "None"}

Context from sources:
{state.get("source_context", "")[:500]}...

Analyze the query and determine:
1. **Complexity**: Simple (single step), Medium (2-3 steps), Complex (4+ steps)
2. **Required Tools**: Which tools are needed and why
3. **Required Sources**: Which data sources should be consulted
4. **Approach**: How to break down the task
5. **Estimated Steps**: How many execution steps will be needed

IMPORTANT: Return ONLY valid JSON, no markdown, no explanation. Just the raw JSON object.

JSON format:
{{
    "complexity": "simple",
    "required_tools": ["tool_name"],
    "required_sources": ["source_name"],
    "approach": "Brief description",
    "estimated_steps": 1,
    "reasoning": "Why this approach"
}}
"""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="You are an expert task planner. Return responses in pure JSON format only, no markdown or code blocks."),
                HumanMessage(content=analysis_prompt)
            ])

            # Parse response - handle potential markdown code blocks
            content = response.content.strip()

            # Remove markdown code blocks if present
            if content.startswith("```"):
                # Find the JSON content between ```json and ```
                lines = content.split("\n")
                json_lines = []
                in_code_block = False
                for line in lines:
                    if line.startswith("```"):
                        in_code_block = not in_code_block
                        continue
                    if in_code_block:
                        json_lines.append(line)
                content = "\n".join(json_lines)

            analysis = json.loads(content)

            print(f"[LangGraph] Query analysis: {analysis['complexity']} complexity, {analysis['estimated_steps']} steps")

            return {
                "analysis": analysis,
                "status": "planning",
                "step_results": [{
                    "step": "analyze_query",
                    "output": analysis,
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }

        except Exception as e:
            print(f"[LangGraph] Analysis error: {e}")
            return {
                "analysis": {
                    "complexity": "simple",
                    "required_tools": [],
                    "required_sources": [],
                    "approach": "Direct answer",
                    "estimated_steps": 1,
                    "error": str(e)
                },
                "status": "planning",
                "errors": [f"Analysis error: {str(e)}"]
            }

    async def _create_plan_node(self, state: DynamicAgentState) -> Dict[str, Any]:
        """
        Create step-by-step execution plan.

        AI generates detailed plan with:
        - Step descriptions
        - Tool selection for each step
        - Tool arguments
        - Dependencies between steps
        """

        print(f"[LangGraph] Creating execution plan...")

        analysis = state.get("analysis", {})

        # Build tools description with parameters
        tools_with_params = self._get_tools_with_parameters()

        planning_prompt = f"""Create a detailed execution plan for this query.

Query: {state["query"]}
Role: {state["role"]}
Analysis: {json.dumps(analysis, indent=2)}

Available Tools (with parameters):
{tools_with_params}

Source Context Available:
{state.get("source_context", "None")[:300]}

Create a step-by-step plan. Each step should:
1. Have a clear objective
2. Use the most appropriate tool
3. Include specific tool arguments
4. Build on results from previous steps (if applicable)

IMPORTANT: Return ONLY valid JSON array, no markdown, no explanation. Just the raw JSON array.

JSON format:
[
    {{
        "step_number": 1,
        "step_name": "Search for information",
        "tool_name": "web_search",
        "tool_args": {{"query": "specific search query"}},
        "expected_output": "What this step should produce",
        "depends_on": []
    }}
]

Keep it efficient: {analysis.get('estimated_steps', 3)} steps maximum.
"""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="You are an expert execution planner. Return responses in pure JSON format only, no markdown or code blocks."),
                HumanMessage(content=planning_prompt)
            ])

            # Parse response - handle potential markdown code blocks
            content = response.content.strip()

            # Remove markdown code blocks if present
            if content.startswith("```"):
                lines = content.split("\n")
                json_lines = []
                in_code_block = False
                for line in lines:
                    if line.startswith("```"):
                        in_code_block = not in_code_block
                        continue
                    if in_code_block:
                        json_lines.append(line)
                content = "\n".join(json_lines)

            # Parse plan
            plan = json.loads(content)

            if not isinstance(plan, list):
                plan = [plan]

            print(f"[LangGraph] Created plan with {len(plan)} steps")
            for i, step in enumerate(plan):
                print(f"  Step {i+1}: {step.get('step_name')} using {step.get('tool_name')}")

            return {
                "plan": plan,
                "current_step": 0,
                "status": "executing",
                "step_results": [{
                    "step": "create_plan",
                    "output": f"Created {len(plan)}-step execution plan",
                    "plan": plan,
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }

        except Exception as e:
            print(f"[LangGraph] Planning error: {e}")
            # Fallback: create simple single-step plan
            fallback_plan = [{
                "step_number": 1,
                "step_name": "Answer query directly",
                "tool_name": None,
                "tool_args": {},
                "expected_output": "Direct answer to query"
            }]

            return {
                "plan": fallback_plan,
                "current_step": 0,
                "status": "executing",
                "errors": [f"Planning error: {str(e)}, using fallback plan"]
            }

    async def _execute_step_node(self, state: DynamicAgentState) -> Dict[str, Any]:
        """
        Execute current step of the plan.

        - Invokes specified tool with arguments
        - Handles errors with retries
        - Stores result for next steps
        - Tracks all tool calls for UI visibility
        """

        current_idx = state["current_step"]
        plan = state["plan"]

        if current_idx >= len(plan):
            return {"status": "aggregating"}

        step = plan[current_idx]
        step_name = step.get("step_name", f"Step {current_idx + 1}")
        tool_name = step.get("tool_name")
        tool_args = step.get("tool_args", {})

        print(f"\n[LangGraph] Executing step {current_idx + 1}/{len(plan)}: {step_name}")
        print(f"  Tool: {tool_name}")
        print(f"  Args: {tool_args}")

        # If no tool specified, use LLM directly
        if not tool_name or tool_name == "None":
            return await self._execute_llm_step(state, step, current_idx)

        # Check if tool exists
        tool = next((t for t in self.tools if t.name == tool_name), None)

        if not tool:
            print(f"[LangGraph] Tool not found: {tool_name}")
            return {
                "current_step": current_idx + 1,
                "errors": [f"Tool not found: {tool_name}"],
                "step_results": [{
                    "step": step_name,
                    "step_number": current_idx + 1,
                    "tool": tool_name,
                    "status": "failed",
                    "error": f"Tool not found: {tool_name}",
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }

        # Execute tool
        try:
            # Record tool call start
            tool_call_record = {
                "tool": tool_name,
                "args": tool_args,
                "step": step_name,
                "step_number": current_idx + 1,
                "status": "running",
                "timestamp": datetime.utcnow().isoformat()
            }

            # Invoke tool
            result = await tool.ainvoke(tool_args)

            # Record success
            tool_call_record["status"] = "success"
            tool_call_record["result"] = result

            print(f"[LangGraph] Step {current_idx + 1} completed successfully")
            print(f"  Result preview: {str(result)[:200]}...")

            return {
                "current_step": current_idx + 1,
                "tool_calls": [tool_call_record],
                "step_results": [{
                    "step": step_name,
                    "step_number": current_idx + 1,
                    "tool": tool_name,
                    "args": tool_args,
                    "output": result,
                    "status": "success",
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }

        except Exception as e:
            print(f"[LangGraph] Step {current_idx + 1} failed: {e}")

            return {
                "current_step": current_idx + 1,
                "errors": [f"Step '{step_name}' failed: {str(e)}"],
                "tool_calls": [{
                    "tool": tool_name,
                    "args": tool_args,
                    "step": step_name,
                    "step_number": current_idx + 1,
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }],
                "step_results": [{
                    "step": step_name,
                    "step_number": current_idx + 1,
                    "tool": tool_name,
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }

    async def _execute_llm_step(
        self,
        state: DynamicAgentState,
        step: Dict[str, Any],
        step_idx: int
    ) -> Dict[str, Any]:
        """Execute step using LLM directly (no tool)."""

        step_name = step.get("step_name", f"Step {step_idx + 1}")

        # Build context from previous results
        previous_results = "\n".join([
            f"Step {r.get('step_number', '?')}: {r.get('output', 'No output')}"
            for r in state.get("step_results", [])
            if r.get("step") != "analyze_query" and r.get("step") != "create_plan"
        ])

        prompt = f"""Execute this step: {step_name}

Original Query: {state["query"]}
Role: {state["role"]}

Previous Results:
{previous_results if previous_results else "None yet"}

Source Context:
{state.get("source_context", "None")[:500]}

Provide a detailed response for this step.
"""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=f"You are a {state['role']} agent."),
                HumanMessage(content=prompt)
            ])

            return {
                "current_step": step_idx + 1,
                "step_results": [{
                    "step": step_name,
                    "step_number": step_idx + 1,
                    "tool": "llm",
                    "output": response.content,
                    "status": "success",
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }

        except Exception as e:
            return {
                "current_step": step_idx + 1,
                "errors": [f"LLM step failed: {str(e)}"],
                "step_results": [{
                    "step": step_name,
                    "step_number": step_idx + 1,
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }

    def _should_continue(self, state: DynamicAgentState) -> Literal["continue", "aggregate", "error"]:
        """Determine next step in execution."""

        # Check if done
        if state["current_step"] >= len(state["plan"]):
            return "aggregate"

        # Check if too many errors
        if len(state.get("errors", [])) > 3:
            print(f"[LangGraph] Too many errors ({len(state['errors'])}), stopping execution")
            return "error"

        # Continue to next step
        return "continue"

    async def _handle_error_node(self, state: DynamicAgentState) -> Dict[str, Any]:
        """Handle execution errors gracefully."""

        print(f"[LangGraph] Handling {len(state.get('errors', []))} errors")

        return {
            "status": "aggregating",
            "step_results": [{
                "step": "error_handling",
                "output": f"Execution stopped due to errors: {'; '.join(state.get('errors', []))}",
                "timestamp": datetime.utcnow().isoformat()
            }]
        }

    async def _aggregate_node(self, state: DynamicAgentState) -> Dict[str, Any]:
        """
        Aggregate all step results into final answer.

        Synthesizes:
        - All successful step outputs
        - Tool call results
        - Error information (if any)
        - Comprehensive final answer
        """

        print(f"\n[LangGraph] Aggregating results from {len(state.get('step_results', []))} steps...")

        # Filter out planning steps
        execution_results = [
            r for r in state.get("step_results", [])
            if r.get("step") not in ["analyze_query", "create_plan", "error_handling"]
        ]

        # Format results
        results_summary = "\n\n".join([
            f"""**Step {r.get('step_number', '?')}: {r.get('step', 'Unknown')}**
Tool: {r.get('tool', 'None')}
Status: {r.get('status', 'unknown')}
Output: {r.get('output', r.get('error', 'No output'))}"""
            for r in execution_results
        ])

        # Get errors if any
        errors_summary = "\n".join(state.get("errors", []))

        synthesis_prompt = f"""Synthesize the final answer for this query.

Original Query: {state["query"]}
Role: {state["role"]}

Execution Summary:
- Total steps executed: {len(execution_results)}
- Successful steps: {len([r for r in execution_results if r.get('status') == 'success'])}
- Failed steps: {len([r for r in execution_results if r.get('status') == 'error'])}
{"- Errors encountered: " + errors_summary if errors_summary else ""}

Step Results:
{results_summary}

Synthesize a comprehensive, well-structured final answer that:
1. Directly addresses the original query
2. Incorporates findings from all successful steps
3. Presents information clearly and professionally
4. Acknowledges any limitations due to errors
5. Provides actionable insights based on the {state["role"]} role

Format as markdown for readability.
"""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=f"{self.system_prompt}\n\nYou are a {state['role']} agent synthesizing research findings."),
                HumanMessage(content=synthesis_prompt)
            ])

            final_answer = response.content

            print(f"[LangGraph] Synthesis complete: {len(final_answer)} chars")

            return {
                "final_answer": final_answer,
                "status": "completed",
                "step_results": [{
                    "step": "aggregate_results",
                    "output": final_answer,
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }

        except Exception as e:
            print(f"[LangGraph] Synthesis error: {e}")

            # Fallback: just combine outputs
            errors_section = f"## Errors\n{errors_summary}" if errors_summary else ""
            fallback_answer = f"""# Results Summary

Query: {state["query"]}

{results_summary}

{errors_section}
"""

            return {
                "final_answer": fallback_answer,
                "status": "completed",
                "errors": [f"Synthesis error: {str(e)}"]
            }

    # ========================================================================
    # MULTI-AGENT ORCHESTRATION NODES
    # ========================================================================

    def _route_orchestration(self, state: DynamicAgentState) -> Literal["single", "multi"]:
        """
        Conditional router: Decide between single-agent and multi-agent execution.

        Routes to:
        - "single": Simple/moderate queries with ≤2 steps
        - "multi": Complex queries OR queries with >2 steps (works with 1+ agents)

        Note: Multi-agent mode works with any number of agents (1+).
        The name refers to the task-based orchestration approach, not agent count.

        Returns:
            "single" or "multi"
        """
        analysis = state.get("analysis", {})
        complexity = analysis.get("complexity", "simple").lower()
        estimated_steps = analysis.get("estimated_steps", 1)

        # Route to multi-agent task orchestration if:
        # 1. Complexity is complex
        # 2. More than 2 steps
        # This works with any number of agents (1+)
        if complexity == "complex" or estimated_steps > 2:
            print(f"[LangGraph] Routing to TASK-BASED orchestration (complexity: {complexity}, steps: {estimated_steps})")
            return "multi"

        print(f"[LangGraph] Routing to DIRECT execution (complexity: {complexity}, steps: {estimated_steps})")
        return "single"

    async def _identify_agents_node(self, state: DynamicAgentState) -> Dict[str, Any]:
        """
        Identify team agents matching the query requirements.

        Intelligently analyzes requirements and creates new agents only when:
        1. No existing agents match required roles/capabilities
        2. Existing agents lack tools needed for the query

        Queries the agents table for team members and matches them
        to recommended roles from analysis.

        Returns:
            Updates assigned_agents field with matching agents (existing + newly created)
        """
        print(f"[LangGraph] Identifying agents for team {state['team_id']}...")

        analysis = state.get("analysis", {})
        recommended_roles = analysis.get("recommended_agent_roles", [])
        required_tools = analysis.get("required_tools", [])

        # Query active agents from team
        agents = await repo_query(
            """SELECT id, name, role, tool_ids, config, status
               FROM agent_instances
               WHERE team_id = :team_id AND (status = 'active' OR status = 'idle')
               ORDER BY created DESC""",
            {"team_id": state["team_id"]}
        )

        print(f"[LangGraph] Found {len(agents)} existing agent(s) for team")

        # Analyze capability gaps
        capability_gaps = await self._analyze_capability_gaps(
            existing_agents=agents,
            recommended_roles=recommended_roles,
            required_tools=required_tools,
            state=state
        )

        # Create new agents to fill gaps (if needed)
        newly_created_agents = []
        if capability_gaps:
            print(f"[LangGraph] Identified {len(capability_gaps)} capability gap(s), creating agents...")
            newly_created_agents = await self._create_missing_agents(
                capability_gaps=capability_gaps,
                team_id=state["team_id"],
                state=state
            )

            # Log agent creation
            if newly_created_agents:
                await self._log_message(
                    team_id=state["team_id"],
                    execution_id=state["execution_id"],
                    sender_id="system",
                    recipient_id=None,
                    message_type="system_info",
                    content=f"Created {len(newly_created_agents)} new agent(s) to fulfill query requirements",
                    metadata={"new_agents": [{"id": a["id"], "name": a["name"], "role": a["role"]} for a in newly_created_agents]}
                )

        # Combine existing and newly created agents
        all_agents = agents + newly_created_agents

        if not all_agents:
            print(f"[LangGraph] No agents available (none existing, none created)")
            await self._log_message(
                team_id=state["team_id"],
                execution_id=state["execution_id"],
                sender_id="system",
                recipient_id=None,
                message_type="warning",
                content="No agents available. Falling back to single-agent mode.",
                metadata={"recommended_roles": recommended_roles}
            )

            return {
                "orchestration_mode": "single",
                "assigned_agents": [],
                "messages": [{
                    "sender_id": "system",
                    "message_type": "warning",
                    "content": "No agents available, using single-agent fallback",
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }

        # Filter agents by recommended roles if specified
        if recommended_roles:
            matched_agents = [
                agent for agent in all_agents
                if agent.get("role", "").lower() in [r.lower() for r in recommended_roles]
            ]
            # If no matches, use all agents
            assigned_agents = matched_agents if matched_agents else all_agents
        else:
            assigned_agents = all_agents

        print(f"[LangGraph] Final agent assignment: {len(assigned_agents)} agent(s)")
        print(f"  - Existing: {len([a for a in assigned_agents if a not in newly_created_agents])}")
        print(f"  - Newly created: {len([a for a in assigned_agents if a in newly_created_agents])}")
        print(f"  - Agent names: {[a.get('name') for a in assigned_agents]}")

        # Log agent assignment message
        agent_word = "agent" if len(assigned_agents) == 1 else "agents"
        created_note = f" ({len(newly_created_agents)} newly created)" if newly_created_agents else ""
        await self._log_message(
            team_id=state["team_id"],
            execution_id=state["execution_id"],
            sender_id="system",
            recipient_id=None,
            message_type="system_broadcast",
            content=f"Task-based orchestration with {len(assigned_agents)} {agent_word}{created_note}",
            metadata={"agent_ids": [a["id"] for a in assigned_agents]}
        )

        return {
            "orchestration_mode": "multi",
            "assigned_agents": assigned_agents,
            "messages": [{
                "sender_id": "system",
                "message_type": "system_broadcast",
                "content": f"Task-based orchestration with {len(assigned_agents)} {agent_word}{created_note}",
                "timestamp": datetime.utcnow().isoformat()
            }]
        }

    async def _create_tasks_node(self, state: DynamicAgentState) -> Dict[str, Any]:
        """
        Create task records from execution plan.

        Creates agent_tasks records and assigns them to agents
        based on tool requirements and roles.

        Returns:
            Updates task_records field with created tasks
        """
        print(f"[LangGraph] Creating tasks from plan with {len(state.get('plan', []))} steps...")

        plan = state.get("plan", [])
        assigned_agents = state.get("assigned_agents", [])
        task_records = []
        messages = []

        for step_num, step in enumerate(plan):
            # Match step to agent
            agent = self._match_agent_to_step(step, assigned_agents)

            if not agent:
                print(f"[LangGraph] Warning: No agent found for step {step_num + 1}")
                continue

            # Create task record
            task_id = str(uuid.uuid4())
            task_title = step.get("step_name", f"Step {step_num + 1}")

            await repo_execute(
                """INSERT INTO agent_tasks
                   (id, team_id, execution_id, assignee_id, title, description,
                    status, priority, depends_on, created, updated)
                   VALUES (:id, :team_id, :exec_id, :agent_id, :title, :desc,
                           'pending', :priority, :depends, :now, :now)""",
                {
                    "id": task_id,
                    "team_id": state["team_id"],
                    "exec_id": state["execution_id"],
                    "agent_id": agent["id"],
                    "title": task_title,
                    "desc": json.dumps(step),
                    "priority": step_num,
                    "depends": json.dumps(step.get("depends_on", [])),
                    "now": datetime.utcnow().isoformat(),
                }
            )

            task_record = {
                "id": task_id,
                "title": task_title,
                "agent_id": agent["id"],
                "agent_name": agent.get("name"),
                "status": "pending",
                "priority": step_num,
                "description": json.dumps(step)
            }
            task_records.append(task_record)

            # Log assignment message
            await self._log_message(
                team_id=state["team_id"],
                execution_id=state["execution_id"],
                sender_id="system",
                recipient_id=agent["id"],
                message_type="task_assignment",
                content=f"Assigned task: {task_title}",
                metadata={"task_id": task_id, "step_number": step_num + 1}
            )

            messages.append({
                "sender_id": "system",
                "recipient_id": agent["id"],
                "message_type": "task_assignment",
                "content": f"Assigned {task_title} to {agent.get('name')}",
                "timestamp": datetime.utcnow().isoformat()
            })

            print(f"[LangGraph] Created task {task_id}: '{task_title}' → Agent {agent.get('name')}")

        return {
            "task_records": task_records,
            "messages": messages
        }

    async def _execute_multi_agent_node(self, state: DynamicAgentState) -> Dict[str, Any]:
        """
        Execute tasks with multiple agents in parallel when possible, sequential when dependencies exist.

        Uses dependency graph analysis to determine which tasks can run in parallel.
        Tasks without dependencies or with satisfied dependencies run concurrently.

        Returns:
            Updates agent_results field with execution results
        """
        print(f"[LangGraph] Executing multi-agent tasks with parallel execution...")

        # Load all tasks for this execution
        all_tasks_in_db = await repo_query(
            """SELECT * FROM agent_tasks
               WHERE team_id = :team_id AND execution_id = :exec_id
               ORDER BY priority ASC""",
            {"team_id": state["team_id"], "exec_id": state["execution_id"]}
        )

        if not all_tasks_in_db:
            print(f"[LangGraph] No tasks found for execution {state['execution_id']}")
            return {
                "agent_results": [],
                "status": "completed"
            }

        print(f"[LangGraph] Found {len(all_tasks_in_db)} tasks to execute")

        # Execute tasks with dependency-aware parallelization
        agent_results = await self._execute_tasks_parallel(all_tasks_in_db, state)

        print(f"[LangGraph] All tasks completed. Total results: {len(agent_results)}")

        return {
            "agent_results": agent_results,
            "status": "completed"
        }

    async def _execute_tasks_parallel(
        self,
        tasks: List[Dict[str, Any]],
        state: DynamicAgentState
    ) -> List[Dict[str, Any]]:
        """
        Execute tasks in parallel waves based on dependencies.

        Algorithm:
        1. Build dependency graph
        2. Execute tasks in waves:
           - Wave 1: All tasks with no dependencies (parallel)
           - Wave 2: Tasks depending only on Wave 1 (parallel)
           - Wave N: Tasks depending on previous waves (parallel)

        Args:
            tasks: List of task records from database
            state: Current execution state

        Returns:
            List of agent results
        """
        # Build task dependency graph
        task_map = {task["id"]: task for task in tasks}
        completed_tasks = set()
        failed_tasks = set()
        agent_results = []

        # Parse dependencies
        task_dependencies = {}
        for task in tasks:
            depends_on = []
            depends_json = task.get("depends_on")
            if depends_json:
                try:
                    depends_on = json.loads(depends_json) if isinstance(depends_json, str) else depends_on
                except Exception:
                    depends_on = []
            task_dependencies[task["id"]] = depends_on

        print(f"[LangGraph] Task dependencies: {task_dependencies}")

        wave_number = 0
        while len(completed_tasks) + len(failed_tasks) < len(tasks):
            wave_number += 1

            # Find tasks ready to execute (dependencies satisfied)
            ready_tasks = []
            for task in tasks:
                task_id = task["id"]

                # Skip if already completed or failed
                if task_id in completed_tasks or task_id in failed_tasks:
                    continue

                # Check if dependencies are satisfied
                dependencies = task_dependencies.get(task_id, [])
                if all(dep in completed_tasks for dep in dependencies):
                    ready_tasks.append(task)

            if not ready_tasks:
                # Check if we have tasks blocked by failed dependencies
                remaining_tasks = [
                    task for task in tasks
                    if task["id"] not in completed_tasks and task["id"] not in failed_tasks
                ]
                if remaining_tasks:
                    print(f"[LangGraph] Warning: {len(remaining_tasks)} tasks blocked by failed dependencies")
                    for task in remaining_tasks:
                        print(f"  - {task['title']} blocked by: {task_dependencies.get(task['id'], [])}")
                break

            print(f"[LangGraph] Wave {wave_number}: Executing {len(ready_tasks)} task(s) in parallel")
            for task in ready_tasks:
                print(f"  - {task['title']} (agent: {task.get('assignee_id')})")

            # Execute ready tasks in parallel
            wave_results = await asyncio.gather(*[
                self._execute_single_task_with_error_handling(task, state)
                for task in ready_tasks
            ], return_exceptions=True)

            # Process results
            for task, result in zip(ready_tasks, wave_results):
                task_id = task["id"]

                if isinstance(result, Exception):
                    # Exception during execution
                    error_msg = str(result)
                    print(f"[LangGraph] Task {task_id} raised exception: {error_msg}")
                    failed_tasks.add(task_id)

                    agent_results.append({
                        "task_id": task_id,
                        "agent_id": task["assignee_id"],
                        "title": task["title"],
                        "description": task.get("description"),
                        "status": "failed",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    })

                elif result.get("success"):
                    # Task succeeded
                    print(f"[LangGraph] ✓ Task '{task['title']}' completed")
                    completed_tasks.add(task_id)

                    agent_results.append({
                        "task_id": task_id,
                        "agent_id": task["assignee_id"],
                        "title": task["title"],
                        "description": task.get("description"),
                        "status": "completed",
                        "result": result.get("output"),
                        "timestamp": datetime.utcnow().isoformat()
                    })

                else:
                    # Task failed
                    error_msg = result.get("error", "Unknown error")
                    print(f"[LangGraph] ✗ Task '{task['title']}' failed: {error_msg}")
                    failed_tasks.add(task_id)

                    agent_results.append({
                        "task_id": task_id,
                        "agent_id": task["assignee_id"],
                        "title": task["title"],
                        "description": task.get("description"),
                        "status": "failed",
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat()
                    })

        print(f"[LangGraph] Parallel execution complete:")
        print(f"  - Waves executed: {wave_number}")
        print(f"  - Successful: {len(completed_tasks)}")
        print(f"  - Failed: {len(failed_tasks)}")

        return agent_results

    async def _execute_single_task_with_error_handling(
        self,
        task: Dict[str, Any],
        state: DynamicAgentState
    ) -> Dict[str, Any]:
        """
        Execute a single task with full error handling and database updates.

        Args:
            task: Task record from database
            state: Current execution state

        Returns:
            Result dict with success, output, or error
        """
        task_id = task["id"]
        print(f"[LangGraph] Executing task {task_id}: {task['title']}")

        try:
            result = await self._execute_agent_task(task, state)

            if result.get("success"):
                # Task succeeded - update database
                await repo_execute(
                    """UPDATE agent_tasks
                       SET status = 'completed', result = :result,
                           completed_at = :completed, updated = :updated
                       WHERE id = :id""",
                    {
                        "id": task_id,
                        "result": result.get("output"),
                        "completed": datetime.utcnow().isoformat(),
                        "updated": datetime.utcnow().isoformat(),
                    }
                )

                # Log completion message
                await self._log_message(
                    team_id=state["team_id"],
                    execution_id=state["execution_id"],
                    sender_id=task["assignee_id"],
                    recipient_id=None,
                    message_type="task_complete",
                    content=f"Task '{task['title']}' completed",
                    metadata={"task_id": task_id, "result_length": len(str(result.get("output", "")))}
                )
            else:
                # Task failed - update database
                error_msg = result.get("error", "Unknown error")
                await repo_execute(
                    """UPDATE agent_tasks
                       SET status = 'failed', error = :error,
                           completed_at = :completed, updated = :updated
                       WHERE id = :id""",
                    {
                        "id": task_id,
                        "error": error_msg,
                        "completed": datetime.utcnow().isoformat(),
                        "updated": datetime.utcnow().isoformat(),
                    }
                )

                # Log error message
                await self._log_message(
                    team_id=state["team_id"],
                    execution_id=state["execution_id"],
                    sender_id=task["assignee_id"],
                    recipient_id=None,
                    message_type="error",
                    content=f"Task '{task['title']}' failed: {error_msg}",
                    metadata={"task_id": task_id}
                )

            return result

        except Exception as e:
            # Unexpected exception during execution
            error_msg = str(e)
            print(f"[LangGraph] Exception executing task {task_id}: {error_msg}")
            import traceback
            traceback.print_exc()

            # Update database
            await repo_execute(
                """UPDATE agent_tasks
                   SET status = 'failed', error = :error,
                       completed_at = :completed, updated = :updated
                   WHERE id = :id""",
                {
                    "id": task_id,
                    "error": error_msg,
                    "completed": datetime.utcnow().isoformat(),
                    "updated": datetime.utcnow().isoformat(),
                }
            )

            # Return failure result
            return {
                "success": False,
                "error": error_msg
            }

    async def _consolidate_multi_results_node(self, state: DynamicAgentState) -> Dict[str, Any]:
        """
        Consolidate results from multiple agents into final answer.

        Synthesizes outputs from all agents using LLM.

        Returns:
            Updates final_answer field
        """
        print(f"[LangGraph] Consolidating results from {len(state.get('agent_results', []))} agents...")

        agent_results = state.get("agent_results", [])

        # Format agent results
        results_text = "\n\n".join([
            f"""### Agent Result {i + 1}
Task: {result.get('task_id')}
Agent: {result.get('agent_id')}
Status: {result.get('status')}
Output: {result.get('result', result.get('error', 'No output'))}"""
            for i, result in enumerate(agent_results)
        ])

        consolidation_prompt = f"""Consolidate the following results from multiple agents into a comprehensive final answer.

Original Query: {state["query"]}
Role: {state["role"]}

Agent Results:
{results_text}

Source Context:
{state.get("source_context", "")[:1000]}

Synthesize a comprehensive, well-structured final answer that:
1. Directly addresses the original query
2. Integrates findings from all agents
3. Presents information clearly and professionally
4. Provides actionable insights based on the {state["role"]} role

Format as markdown for readability."""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=f"You are a {state['role']} agent consolidating multi-agent findings."),
                HumanMessage(content=consolidation_prompt)
            ])

            final_answer = response.content

            print(f"[LangGraph] Consolidation complete: {len(final_answer)} chars")

            return {
                "final_answer": final_answer,
                "status": "completed"
            }

        except Exception as e:
            print(f"[LangGraph] Consolidation error: {e}")

            # Fallback: just combine outputs
            fallback_answer = f"""# Multi-Agent Results

Query: {state["query"]}

{results_text}

## Summary
Consolidated outputs from {len(agent_results)} agents.
"""

            return {
                "final_answer": fallback_answer,
                "status": "completed",
                "errors": [f"Consolidation error: {str(e)}"]
            }

    async def execute(
        self,
        query: str,
        role: str = "researcher",
        context_source_ids: Optional[List[str]] = None,
        notebook_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute agent with query.

        Args:
            query: User query
            role: Agent role (researcher, analyst, etc.)
            context_source_ids: Optional source IDs for context
            notebook_id: Optional notebook ID to fetch sources from

        Returns:
            Execution result with final answer
        """
        # ------------------------------------------------------------------
        # Pattern dispatch.
        #
        # When the team carries an orchestration_pattern (set by the redesigned
        # CreateTeamDialog), execution is driven by the matching PatternExecutor
        # — a deterministic, user-chosen flow that talks to agents via the A2A
        # bus. Teams without a pattern fall through to the legacy LangGraph
        # heuristic path below.
        # ------------------------------------------------------------------
        try:
            patterned = await self._maybe_run_pattern(
                query=query,
                context_source_ids=context_source_ids,
                notebook_id=notebook_id,
            )
        except Exception:
            # Don't let a pattern-dispatch error mask the legacy fallback
            # behavior — surface the error if the pattern ran, but log + drop
            # it if the dispatcher itself blew up before invoking the executor.
            patterned = None

        if patterned is not None:
            return patterned

        print(f"\n{'='*70}")
        print(f"[LangGraph] Starting execution")
        print(f"  Team: {self.team_id}")
        print(f"  Execution: {self.execution_id}")
        print(f"  Query: {query[:100]}...")
        print(f"{'='*70}\n")

        # Build source context
        source_context, available_sources = await self._build_source_context(
            context_source_ids,
            notebook_id
        )

        # Get available tools
        available_tools = [tool.name for tool in self.tools]

        # Build graph
        self.graph = self._build_graph()

        # Initial state
        initial_state: DynamicAgentState = {
            "query": query,
            "role": role,
            "team_id": self.team_id,
            "execution_id": self.execution_id,
            "available_sources": available_sources,
            "available_tools": available_tools,
            "source_context": source_context,
            "analysis": None,
            "plan": [],
            "current_step": 0,
            "step_results": [],
            "tool_calls": [],
            "errors": [],
            "final_answer": None,
            "status": "initializing",
            # Multi-agent orchestration fields
            "orchestration_mode": "single",  # Will be set by routing logic
            "assigned_agents": [],
            "task_records": [],
            "agent_results": [],
            "messages": []
        }

        # Create execution record
        now = datetime.utcnow().isoformat()
        await repo_execute(
            """INSERT INTO agent_executions
               (id, team_id, query, status, started_at)
               VALUES (:id, :team_id, :query, :status, :started_at)""",
            {
                "id": self.execution_id,
                "team_id": self.team_id,
                "query": query,
                "status": "running",
                "started_at": now
            }
        )

        try:
            # Execute graph
            final_state = await self.graph.ainvoke(initial_state)

            # Save result
            completed_at = datetime.utcnow().isoformat()
            await repo_execute(
                """UPDATE agent_executions
                   SET status = :status, result = :result, completed_at = :completed_at
                   WHERE id = :id""",
                {
                    "id": self.execution_id,
                    "status": "completed",
                    "result": json.dumps({
                        "output": final_state.get("final_answer"),
                        "steps": len(final_state.get("step_results", [])),
                        "tool_calls": len(final_state.get("tool_calls", [])),
                        "errors": final_state.get("errors", [])
                    }),
                    "completed_at": completed_at
                }
            )

            print(f"\n[LangGraph] Execution completed successfully")
            print(f"  Steps: {len(final_state.get('step_results', []))}")
            print(f"  Tool calls: {len(final_state.get('tool_calls', []))}")
            print(f"  Errors: {len(final_state.get('errors', []))}")

            # Fetch messages from database
            messages = await repo_query(
                """SELECT id, sender_id, recipient_id, message_type, content, metadata, created
                   FROM agent_messages
                   WHERE execution_id = :exec_id
                   ORDER BY created ASC""",
                {"exec_id": self.execution_id}
            )

            # Fetch tasks from database
            tasks = await repo_query(
                """SELECT id, assignee_id, title, description, status, priority,
                          result, error, depends_on, started_at, completed_at, created, updated
                   FROM agent_tasks
                   WHERE execution_id = :exec_id
                   ORDER BY created ASC""",
                {"exec_id": self.execution_id}
            )

            return {
                "id": self.execution_id,
                "team_id": self.team_id,
                "query": query,
                "status": "completed",
                "result": final_state.get("final_answer"),
                "steps": final_state.get("step_results", []),
                "tasks": tasks,
                "messages": messages,
                "tool_calls": final_state.get("tool_calls", []),
                "errors": final_state.get("errors", []),
                "started_at": now,
                "completed_at": completed_at
            }

        except Exception as e:
            print(f"\n[LangGraph] Execution failed: {e}")

            # Update execution record
            await repo_execute(
                """UPDATE agent_executions
                   SET status = :status, result = :result, completed_at = :completed_at
                   WHERE id = :id""",
                {
                    "id": self.execution_id,
                    "status": "failed",
                    "result": json.dumps({"error": str(e)}),
                    "completed_at": datetime.utcnow().isoformat()
                }
            )

            raise

    async def stream_execution(
        self,
        query: str,
        role: str = "researcher",
        context_source_ids: Optional[List[str]] = None,
        notebook_id: Optional[str] = None,
        *,
        resume: Optional[Dict[str, Any]] = None,
    ):
        """
        Execute agent and stream all events to UI.

        Yields SSE events for:
        - Step start/complete
        - Tool calls
        - LLM reasoning
        - Results
        - Errors

        Args:
            query: User query
            role: Agent role
            context_source_ids: Optional source IDs
            notebook_id: Optional notebook ID

        Yields:
            Dict events for SSE streaming
        """

        print(f"\n[LangGraph] Starting streaming execution...")
        print(f"[LangGraph] Query: {query}")
        print(f"[LangGraph] Role: {role}")
        print(f"[LangGraph] Tools available: {len(self.tools)}")

        # Pattern dispatch — same logic as execute(). When the team has an
        # orchestration_pattern, we forward to the pattern executor and yield
        # a small set of SSE events shaped like the legacy stream so existing
        # UI handlers keep rendering. The executor's PatternContext.emit
        # writes durable rows to agent_messages; we surface them as we go via
        # the on_step callback.
        try:
            patterned = await self._maybe_stream_pattern(
                query=query,
                context_source_ids=context_source_ids,
                notebook_id=notebook_id,
                resume=resume,
            )
        except Exception as pat_err:
            yield {"event": "error", "data": {"error": str(pat_err)}}
            return

        if patterned is not None:
            for ev in patterned:
                yield ev
            return

        try:
            # Build source context
            print(f"[LangGraph] Building source context...")
            source_context, available_sources = await self._build_source_context(
                context_source_ids,
                notebook_id
            )
            print(f"[LangGraph] Source context built. Available sources: {len(available_sources)}")

            # Get available tools
            available_tools = [tool.name for tool in self.tools]
            print(f"[LangGraph] Available tools: {available_tools}")

            # Send initial metadata
            yield {
                "event": "metadata",
                "data": {
                    "execution_id": self.execution_id,
                    "team_id": self.team_id,
                    "query": query,
                    "role": role,
                    "available_tools": available_tools,
                    "available_sources": len(available_sources)
                }
            }

            # Build graph
            print(f"[LangGraph] Building execution graph...")
            self.graph = self._build_graph()
            print(f"[LangGraph] Graph built successfully")

            # Initial state
            initial_state: DynamicAgentState = {
                "query": query,
                "role": role,
                "team_id": self.team_id,
                "execution_id": self.execution_id,
                "available_sources": available_sources,
                "available_tools": available_tools,
                "source_context": source_context,
                "analysis": None,
                "plan": [],
                "current_step": 0,
                "step_results": [],
                "tool_calls": [],
                "errors": [],
                "final_answer": None,
                "status": "initializing",
                # Multi-agent orchestration fields
                "orchestration_mode": "single",
                "assigned_agents": [],
                "task_records": [],
                "agent_results": [],
                "messages": []
            }
            print(f"[LangGraph] Initial state created")

            # Create execution record
            now = datetime.utcnow().isoformat()
            print(f"[LangGraph] Creating execution record...")
            await repo_execute(
                """INSERT INTO agent_executions
                   (id, team_id, query, status, started_at)
                   VALUES (:id, :team_id, :query, :status, :started_at)""",
                {
                    "id": self.execution_id,
                    "team_id": self.team_id,
                    "query": query,
                    "status": "running",
                    "started_at": now
                }
            )
            print(f"[LangGraph] Execution record created")

        except Exception as e:
            print(f"[LangGraph] ❌ Setup error: {e}")
            import traceback
            traceback.print_exc()
            yield {
                "event": "error",
                "data": {
                    "error": str(e),
                    "type": "setup_error",
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            return

        print(f"[LangGraph] Setup complete, moving to execution phase...")

        try:
            # Stream execution state updates
            print(f"[LangGraph] Starting graph execution stream...")

            final_state = None
            async for state_update in self.graph.astream(initial_state, stream_mode="updates"):
                print(f"[LangGraph] Received state update: {list(state_update.keys())}")

                # state_update contains the updates from the last node
                for node_name, node_output in state_update.items():
                    print(f"[LangGraph] Node '{node_name}' output keys: {list(node_output.keys()) if isinstance(node_output, dict) else type(node_output)}")

                    # Send node-specific events based on which node executed
                    if node_name == "analyze_query" and isinstance(node_output, dict):
                        if node_output.get("analysis"):
                            step_data = {
                                "step": "analyze_query",
                                "output": node_output.get("analysis"),
                                "timestamp": datetime.utcnow().isoformat()
                            }
                            yield {
                                "event": "step_complete",
                                "data": step_data
                            }
                            # Save to database
                            await self._save_workflow_step("analyze_query", node_output.get("analysis"))

                    elif node_name == "create_plan" and isinstance(node_output, dict):
                        if node_output.get("plan"):
                            step_data = {
                                "step": "create_plan",
                                "output": {"plan": node_output.get("plan")},
                                "timestamp": datetime.utcnow().isoformat()
                            }
                            yield {
                                "event": "step_complete",
                                "data": step_data
                            }
                            # Save to database
                            await self._save_workflow_step("create_plan", {"plan": node_output.get("plan")})

                    elif node_name == "execute_step" and isinstance(node_output, dict):
                        # Send tool call events
                        if node_output.get("tool_calls"):
                            for tool_call in node_output.get("tool_calls", []):
                                yield {
                                    "event": "tool_call" if tool_call.get("status") == "running" else "tool_result",
                                    "data": tool_call
                                }

                        # Send step result events
                        if node_output.get("step_results"):
                            for step_result in node_output.get("step_results", []):
                                yield {
                                    "event": "step_complete",
                                    "data": step_result
                                }
                                # Save each step result to database
                                await self._save_workflow_step(
                                    step_result.get("step", "unknown"),
                                    step_result.get("output"),
                                    status=step_result.get("status", "completed"),
                                    error=step_result.get("error")
                                )

                    elif node_name == "aggregate_results" and isinstance(node_output, dict):
                        final_state = node_output
                        if node_output.get("final_answer"):
                            step_data = {
                                "step": "aggregate_results",
                                "output": node_output.get("final_answer"),
                                "timestamp": datetime.utcnow().isoformat()
                            }
                            yield {
                                "event": "step_complete",
                                "data": step_data
                            }
                            # Save to database
                            await self._save_workflow_step("aggregate_results", node_output.get("final_answer"))

                    # ====== NEW MULTI-AGENT NODE EVENTS ======
                    elif node_name == "identify_agents" and isinstance(node_output, dict):
                        if node_output.get("assigned_agents"):
                            yield {
                                "event": "step_complete",
                                "data": {
                                    "step": "identify_agents",
                                    "output": {
                                        "agent_count": len(node_output.get("assigned_agents", [])),
                                        "agents": [a.get("name") for a in node_output.get("assigned_agents", [])]
                                    },
                                    "timestamp": datetime.utcnow().isoformat()
                                }
                            }

                        # Emit messages from this node
                        if node_output.get("messages"):
                            for message in node_output.get("messages", []):
                                message_data = message
                                yield {
                                    "event": "message",
                                    "data": message_data
                                }
                                # Save to database
                                await self._save_message(message_data)

                    elif node_name == "create_tasks" and isinstance(node_output, dict):
                        # Emit task_created events for each task
                        if node_output.get("task_records"):
                            for task in node_output.get("task_records", []):
                                task_data = {
                                    "id": task.get("id"),  # Frontend expects 'id'
                                    "task_id": task.get("id"),  # Keep for backward compat
                                    "agent_id": task.get("agent_id"),
                                    "agent_name": task.get("agent_name"),
                                    "assigned_agent_name": task.get("agent_name"),  # Frontend field
                                    "title": task.get("title"),
                                    "description": task.get("description"),
                                    "status": task.get("status", "pending"),
                                    "priority": task.get("priority"),
                                    "created_at": datetime.utcnow().isoformat()
                                }
                                yield {
                                    "event": "task_update",
                                    "data": task_data
                                }
                                # Save to database
                                await self._save_task(task_data)

                        # Emit assignment messages
                        if node_output.get("messages"):
                            for message in node_output.get("messages", []):
                                message_data = message
                                yield {
                                    "event": "message",
                                    "data": message_data
                                }
                                # Save to database
                                await self._save_message(message_data)

                        # Also emit a summary step_complete
                        if node_output.get("task_records"):
                            yield {
                                "event": "step_complete",
                                "data": {
                                    "step": "create_tasks",
                                    "output": {
                                        "task_count": len(node_output.get("task_records", [])),
                                        "tasks": [t.get("title") for t in node_output.get("task_records", [])]
                                    },
                                    "timestamp": datetime.utcnow().isoformat()
                                }
                            }

                    elif node_name == "execute_multi_agent" and isinstance(node_output, dict):
                        # Emit task_update events for each completed task
                        if node_output.get("agent_results"):
                            for result in node_output.get("agent_results", []):
                                task_data = {
                                    "id": result.get("task_id"),  # Frontend expects 'id'
                                    "task_id": result.get("task_id"),  # Keep for backward compat
                                    "agent_id": result.get("agent_id"),
                                    "title": result.get("title"),  # Task title
                                    "description": result.get("description"),  # Task description
                                    "status": result.get("status"),
                                    "result": result.get("result", result.get("error")),
                                    "error": result.get("error"),  # Explicit error field
                                    "completed_at": result.get("timestamp")
                                }
                                yield {
                                    "event": "task_update",
                                    "data": task_data
                                }
                                # Save/update task in database
                                await self._save_task(task_data)

                        # Also emit summary
                        if node_output.get("agent_results"):
                            yield {
                                "event": "step_complete",
                                "data": {
                                    "step": "execute_multi_agent",
                                    "output": {
                                        "completed_tasks": len([r for r in node_output.get("agent_results", []) if r.get("status") == "completed"]),
                                        "failed_tasks": len([r for r in node_output.get("agent_results", []) if r.get("status") == "failed"])
                                    },
                                    "timestamp": datetime.utcnow().isoformat()
                                }
                            }

                    elif node_name == "consolidate_multi_results" and isinstance(node_output, dict):
                        final_state = node_output
                        if node_output.get("final_answer"):
                            yield {
                                "event": "step_complete",
                                "data": {
                                    "step": "consolidate_multi_results",
                                    "output": node_output.get("final_answer"),
                                    "timestamp": datetime.utcnow().isoformat()
                                }
                            }

            # If we didn't get final_state from stream, invoke to get it
            if not final_state:
                print("[LangGraph] Getting final state...")
                final_state = await self.graph.ainvoke(initial_state)

            print(f"[LangGraph] Execution complete. Final status: {final_state.get('status')}")

            # Save result
            completed_at = datetime.utcnow().isoformat()
            await repo_execute(
                """UPDATE agent_executions
                   SET status = :status, result = :result, completed_at = :completed_at
                   WHERE id = :id""",
                {
                    "id": self.execution_id,
                    "status": "completed",
                    "result": json.dumps({
                        "output": final_state.get("final_answer"),
                        "steps": len(final_state.get("step_results", [])),
                        "tool_calls": len(final_state.get("tool_calls", []))
                    }),
                    "completed_at": completed_at
                }
            )

            # Send final result
            yield {
                "event": "done",
                "data": {
                    "execution_id": self.execution_id,
                    "status": "completed",
                    "result": final_state.get("final_answer")
                }
            }

        except Exception as e:
            print(f"[LangGraph] ❌ Streaming error: {e}")
            import traceback
            traceback.print_exc()

            # Update execution record
            await repo_execute(
                """UPDATE agent_executions
                   SET status = :status, result = :result, completed_at = :completed_at
                   WHERE id = :id""",
                {
                    "id": self.execution_id,
                    "status": "failed",
                    "result": json.dumps({"error": str(e)}),
                    "completed_at": datetime.utcnow().isoformat()
                }
            )

            # Send error event
            yield {
                "event": "error",
                "data": {
                    "error": str(e),
                    "type": type(e).__name__,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }

    def _format_event_for_ui(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Convert LangGraph event to UI-friendly format.

        LangGraph events we capture:
        - on_chain_start/end: Node execution
        - on_tool_start/end: Tool invocation
        - on_llm_start/end: LLM calls
        """

        event_type = event.get("event")

        if event_type == "on_chain_start":
            return {
                "event": "step_start",
                "data": {
                    "step": event.get("name"),
                    "input": event.get("data", {}).get("input"),
                    "timestamp": datetime.utcnow().isoformat()
                }
            }

        elif event_type == "on_chain_end":
            return {
                "event": "step_complete",
                "data": {
                    "step": event.get("name"),
                    "output": event.get("data", {}).get("output"),
                    "timestamp": datetime.utcnow().isoformat()
                }
            }

        elif event_type == "on_tool_start":
            return {
                "event": "tool_call",
                "data": {
                    "tool": event.get("name"),
                    "args": event.get("data", {}).get("input"),
                    "timestamp": datetime.utcnow().isoformat()
                }
            }

        elif event_type == "on_tool_end":
            return {
                "event": "tool_result",
                "data": {
                    "tool": event.get("name"),
                    "output": event.get("data", {}).get("output"),
                    "timestamp": datetime.utcnow().isoformat()
                }
            }

        elif event_type == "on_llm_start":
            messages = event.get("data", {}).get("input", {}).get("messages", [])
            last_message = messages[-1] if messages else None

            return {
                "event": "llm_call",
                "data": {
                    "prompt": last_message.content if last_message else None,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }

        elif event_type == "on_llm_end":
            return {
                "event": "llm_response",
                "data": {
                    "response": event.get("data", {}).get("output"),
                    "timestamp": datetime.utcnow().isoformat()
                }
            }

        return None

    async def _build_source_context(
        self,
        context_source_ids: Optional[List[str]],
        notebook_id: Optional[str]
    ) -> tuple[str, List[Dict[str, Any]]]:
        """Build context from sources."""

        if not context_source_ids and not notebook_id:
            return "", []

        source_ids = context_source_ids or []

        # If notebook_id provided, fetch all sources
        if notebook_id and not source_ids:
            notebook_sources = await repo_query(
                """SELECT source_id FROM notebook_source
                   WHERE notebook_id = :notebook_id""",
                {"notebook_id": notebook_id}
            )
            source_ids = [row["source_id"] for row in notebook_sources]

        if not source_ids:
            return "", []

        # Fetch sources
        placeholders = ",".join([f":id{i}" for i in range(len(source_ids))])
        params = {f"id{i}": sid for i, sid in enumerate(source_ids)}

        sources = await repo_query(
            f"""SELECT id, title, source_type, full_text
                FROM sources
                WHERE id IN ({placeholders})
                LIMIT 10""",
            params
        )

        if not sources:
            return "", []

        # Format context
        context_parts = []
        available_sources = []

        for source in sources:
            title = source.get("title", "Untitled")
            source_type = source.get("source_type", "unknown")
            full_text = source.get("full_text", "")

            context_parts.append(f"\n## {title} ({source_type})\n{full_text[:1000]}")

            available_sources.append({
                "id": source.get("id"),
                "title": title,
                "source_type": source_type
            })

        context_str = "\n".join(context_parts)

        print(f"[LangGraph] Built context from {len(sources)} sources ({len(context_str)} chars)")

        return context_str, available_sources

    def _get_tool_description(self, tool_name: str) -> str:
        """Get tool description."""
        tool = next((t for t in self.tools if t.name == tool_name), None)
        return tool.description if tool else "No description"

    def _get_tools_with_parameters(self) -> str:
        """Format tools with their parameters."""
        if not self.tools:
            return "No tools available"

        lines = []
        for tool in self.tools:
            lines.append(f"\n### {tool.name}")
            lines.append(f"Description: {tool.description}")

            # Get parameters from tool schema
            if hasattr(tool, "args_schema"):
                schema = tool.args_schema.schema()
                properties = schema.get("properties", {})
                required = schema.get("required", [])

                lines.append("Parameters:")
                for param_name, param_info in properties.items():
                    param_type = param_info.get("type", "any")
                    param_desc = param_info.get("description", "No description")
                    is_required = " (required)" if param_name in required else " (optional)"
                    lines.append(f"  - {param_name} ({param_type}){is_required}: {param_desc}")

        return "\n".join(lines)

    # ========================================================================
    # MULTI-AGENT ORCHESTRATION HELPERS
    # ========================================================================

    async def _log_message(
        self,
        team_id: str,
        execution_id: str,
        sender_id: str,
        recipient_id: Optional[str],
        message_type: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log coordination message to database.

        Args:
            team_id: Team ID
            execution_id: Execution ID
            sender_id: Sender agent ID or 'system'
            recipient_id: Recipient agent ID (None = broadcast)
            message_type: Message type (task_assignment, task_complete, coordination, etc.)
            content: Message content
            metadata: Optional metadata dict

        Returns:
            Message ID
        """
        message_id = str(uuid.uuid4())

        await repo_execute(
            """INSERT INTO agent_messages
               (id, team_id, execution_id, sender_id, recipient_id,
                message_type, content, metadata, created)
               VALUES (:id, :team, :exec, :sender, :recipient,
                       :type, :content, :meta, :now)""",
            {
                "id": message_id,
                "team": team_id,
                "exec": execution_id,
                "sender": sender_id,
                "recipient": recipient_id,
                "type": message_type,
                "content": content,
                "meta": json.dumps(metadata) if metadata else None,
                "now": datetime.utcnow().isoformat(),
            }
        )

        return message_id

    async def _analyze_capability_gaps(
        self,
        existing_agents: List[Dict[str, Any]],
        recommended_roles: List[str],
        required_tools: List[str],
        state: DynamicAgentState
    ) -> List[Dict[str, Any]]:
        """
        Analyze capability gaps between requirements and existing agents.

        Identifies missing roles and tools that existing agents cannot fulfill.

        Args:
            existing_agents: Current team agents
            recommended_roles: Roles from query analysis
            required_tools: Tools from query analysis
            state: Current execution state

        Returns:
            List of capability gap descriptions (each gap is a dict with role, tools, reason)
        """
        gaps = []

        # Extract existing capabilities
        existing_roles = {agent.get("role", "").lower() for agent in existing_agents}
        existing_tools = set()
        for agent in existing_agents:
            tool_ids = agent.get("tool_ids", [])
            if isinstance(tool_ids, str):
                tool_ids = [t.strip() for t in tool_ids.split(",") if t.strip()]
            existing_tools.update(tool_ids)

        print(f"[LangGraph] Existing capabilities: roles={existing_roles}, tools={existing_tools}")
        print(f"[LangGraph] Required: roles={recommended_roles}, tools={required_tools}")

        # Check for missing roles
        for role in recommended_roles:
            role_lower = role.lower()
            if role_lower not in existing_roles:
                # Find tools needed for this role
                role_tools = self._get_default_tools_for_role(role_lower)
                gaps.append({
                    "gap_type": "missing_role",
                    "role": role_lower,
                    "tools": role_tools,
                    "reason": f"No agent with role '{role}' exists"
                })
                print(f"[LangGraph] Gap identified: Missing role '{role}'")

        # Check for missing tools (even if roles exist)
        missing_tools = [tool for tool in required_tools if tool not in existing_tools]
        if missing_tools:
            # Group missing tools by role affinity
            for tool in missing_tools:
                suggested_role = self._get_role_for_tool(tool)
                # Check if any existing agent with that role could get this tool
                has_role_agent = any(
                    agent.get("role", "").lower() == suggested_role
                    for agent in existing_agents
                )

                if not has_role_agent:
                    gaps.append({
                        "gap_type": "missing_tool",
                        "role": suggested_role,
                        "tools": [tool],
                        "reason": f"Tool '{tool}' needed but no agent has it"
                    })
                    print(f"[LangGraph] Gap identified: Missing tool '{tool}', need role '{suggested_role}'")

        return gaps

    def _get_default_tools_for_role(self, role: str) -> List[str]:
        """
        Get default tools for a given role.

        Args:
            role: Agent role (lowercase)

        Returns:
            List of tool IDs appropriate for this role
        """
        role_tool_mapping = {
            "researcher": ["web_search", "semantic_search"],
            "data_analyst": ["hana_query", "python_repl"],
            "analyst": ["hana_query", "python_repl"],
            "synthesizer": ["semantic_search"],
            "writer": ["semantic_search"],
            "query_agent": ["hana_query"],
            "search_agent": ["web_search", "semantic_search"],
        }

        # Get tools from mapping, filter to only available tools
        suggested_tools = role_tool_mapping.get(role, ["semantic_search"])
        available_tool_names = [tool.name for tool in self.tools]

        return [tool for tool in suggested_tools if tool in available_tool_names]

    def _get_role_for_tool(self, tool_name: str) -> str:
        """
        Determine best role for a given tool.

        Args:
            tool_name: Tool identifier

        Returns:
            Recommended role for this tool
        """
        tool_role_mapping = {
            "web_search": "researcher",
            "semantic_search": "researcher",
            "hana_query": "data_analyst",
            "python_repl": "data_analyst",
            "api_call": "data_analyst",
        }

        return tool_role_mapping.get(tool_name, "researcher")

    async def _create_missing_agents(
        self,
        capability_gaps: List[Dict[str, Any]],
        team_id: str,
        state: DynamicAgentState
    ) -> List[Dict[str, Any]]:
        """
        Create new agents to fill capability gaps.

        Only creates agents when necessary to fulfill unmet requirements.

        Args:
            capability_gaps: List of identified gaps
            team_id: Team ID to add agents to
            state: Current execution state

        Returns:
            List of newly created agent records
        """
        newly_created = []

        for gap in capability_gaps:
            role = gap["role"]
            tools = gap["tools"]
            reason = gap["reason"]

            # Generate agent name
            agent_name = self._generate_agent_name(role, team_id)

            # Create agent record
            agent_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()

            try:
                await repo_execute(
                    """INSERT INTO agent_instances
                       (id, team_id, name, role, tool_ids, config, status, created, updated)
                       VALUES (:id, :team_id, :name, :role, :tool_ids, :config, :status, :created, :updated)""",
                    {
                        "id": agent_id,
                        "team_id": team_id,
                        "name": agent_name,
                        "role": role,
                        "tool_ids": json.dumps(tools),
                        "config": json.dumps({"auto_created": True, "reason": reason}),
                        "status": "active",
                        "created": now,
                        "updated": now
                    }
                )

                agent_record = {
                    "id": agent_id,
                    "team_id": team_id,
                    "name": agent_name,
                    "role": role,
                    "tool_ids": tools,
                    "config": {"auto_created": True, "reason": reason},
                    "status": "active",
                    "created": now,
                    "updated": now
                }
                newly_created.append(agent_record)

                print(f"[LangGraph] ✓ Created agent: {agent_name} (role={role}, tools={tools})")

                # Log creation message
                await self._log_message(
                    team_id=team_id,
                    execution_id=state["execution_id"],
                    sender_id="system",
                    recipient_id=agent_id,
                    message_type="agent_created",
                    content=f"Created agent '{agent_name}' with role '{role}' to fulfill: {reason}",
                    metadata={"agent_id": agent_id, "tools": tools}
                )

            except Exception as e:
                print(f"[LangGraph] Failed to create agent for role '{role}': {e}")
                continue

        return newly_created

    def _generate_agent_name(self, role: str, team_id: str) -> str:
        """
        Generate a unique agent name based on role.

        Args:
            role: Agent role
            team_id: Team ID

        Returns:
            Generated agent name
        """
        # Role-specific name templates
        role_names = {
            "researcher": "Research Specialist",
            "data_analyst": "Data Analyst",
            "analyst": "Analysis Agent",
            "synthesizer": "Report Synthesizer",
            "writer": "Content Writer",
            "query_agent": "Query Executor",
            "search_agent": "Search Specialist",
        }

        base_name = role_names.get(role, f"{role.title()} Agent")

        # Add suffix to make unique (simple counter approach)
        import random
        suffix = random.randint(1000, 9999)

        return f"{base_name} #{suffix}"

    def _match_agent_to_step(
        self,
        step: Dict[str, Any],
        agents: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Match a plan step to the best agent based on tools and role.

        Args:
            step: Plan step dict with tool_name and step_type
            agents: List of agent records from database

        Returns:
            Best matching agent or None
        """
        if not agents:
            return None

        # 1. Get required tool from step
        required_tool = step.get("tool_name")

        # 2. Filter agents that have the required tool
        if required_tool:
            for agent in agents:
                tool_ids = agent.get("tool_ids", [])
                # Handle both list and comma-separated string formats
                if isinstance(tool_ids, str):
                    tool_ids = [t.strip() for t in tool_ids.split(",") if t.strip()]
                if required_tool in tool_ids:
                    return agent

        # 3. Fallback: Match by role based on step type
        step_type = step.get("step_type", "")
        role_mapping = {
            "data_query": ["data_analyst", "query_agent", "analyst"],
            "web_search": ["researcher", "search_agent", "researcher"],
            "synthesis": ["synthesizer", "writer", "writer"],
            "analysis": ["analyst", "data_analyst"],
        }

        preferred_roles = role_mapping.get(step_type, [])
        for role in preferred_roles:
            for agent in agents:
                if agent.get("role", "").lower() == role.lower():
                    return agent

        # 4. Last resort: Return first available agent
        return agents[0]

    async def _execute_agent_task(
        self,
        task: Dict[str, Any],
        state: DynamicAgentState
    ) -> Dict[str, Any]:
        """
        Execute a single agent task.

        Args:
            task: Task record from agent_tasks table
            state: Current execution state

        Returns:
            Result dict with success, output, error
        """
        try:
            # Mark task as in_progress
            await repo_execute(
                """UPDATE agent_tasks
                   SET status = 'in_progress', started_at = :started, updated = :updated
                   WHERE id = :id""",
                {
                    "id": task["id"],
                    "started": datetime.utcnow().isoformat(),
                    "updated": datetime.utcnow().isoformat(),
                }
            )

            # Parse task description to get step info
            step = json.loads(task.get("description", "{}"))

            # Execute step using existing execution logic
            # Get the tool if specified
            tool_name = step.get("tool_name")
            if tool_name:
                # Execute tool
                tool = next((t for t in self.tools if t.name == tool_name), None)
                if tool:
                    tool_args = step.get("tool_args", {})
                    result = await tool.ainvoke(tool_args)
                    output = str(result)
                else:
                    output = f"Tool '{tool_name}' not found"
            else:
                # LLM-based step
                prompt = f"""Task: {task.get('title')}

                Query: {state['query']}

                Context from previous steps:
                {json.dumps(state.get('step_results', []), indent=2)}

                Source context:
                {state.get('source_context', '')[:1000]}

                Provide a response for this task."""

                response = await self.llm.ainvoke([HumanMessage(content=prompt)])
                output = response.content

            return {
                "success": True,
                "output": output,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            print(f"[Task Execution] Error executing task {task['id']}: {e}")
            return {
                "success": False,
                "output": None,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
