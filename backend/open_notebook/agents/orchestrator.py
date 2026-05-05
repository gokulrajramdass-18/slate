"""
Workflow Orchestrator - Coordinates single and multi-agent execution with streaming.

Provides three orchestration modes:
1. Single Agent: Routes simple queries to DataQueryAgent
2. Team Mode: Spawns researcher + analyst agents for moderate queries
3. Planned Mode: Uses a planner step to decompose complex queries, then executes a full agent team

All modes emit SSE-compatible streaming events for real-time frontend updates.
"""

import asyncio
import json
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

from open_notebook.agents.data_query_agent import DataQueryAgent
from open_notebook.agents.synthesizer_agent import SynthesizerAgent
from api.services.prompt_loader import load_prompt


# ============================================================================
# Types and Enums
# ============================================================================

class OrchestrationMode(str, Enum):
    """How the orchestrator runs agents."""
    SINGLE = "single"
    TEAM = "team"
    PLANNED = "planned"


class WorkflowPhase(str, Enum):
    """High-level phases of an orchestrated workflow."""
    INITIALIZING = "initializing"
    PLANNING = "planning"
    EXECUTING = "executing"
    SYNTHESIZING = "synthesizing"
    COMPLETE = "complete"
    ERROR = "error"


class AgentRole(str, Enum):
    """Predefined roles for team agents."""
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    PLANNER = "planner"


# Fallback prompts (kept for offline/fallback scenarios)
AGENT_SYSTEM_PROMPTS = {
    AgentRole.RESEARCHER: (
        "You are a research agent. Your job is to find relevant information by "
        "querying data sources, searching content, and gathering facts. "
        "Focus on completeness and accuracy. Use all available tools to retrieve data."
    ),
    AgentRole.ANALYST: (
        "You are an analysis agent. Your job is to interpret data, identify patterns, "
        "draw conclusions, and provide insights. When you receive data from tools, "
        "analyze it thoroughly and explain what it means in context."
    ),
    AgentRole.PLANNER: (
        "You are a planning agent. Decompose the user's complex query into a set of "
        "concrete sub-tasks that can be executed by researcher and analyst agents. "
        "Return a JSON array of task objects, each with keys: "
        '"task" (description), "role" (researcher or analyst), "depends_on" (list of task indices, 0-based).'
    ),
}


class AgentTask(TypedDict, total=False):
    """A task produced by the planner for a team agent."""
    id: str
    task: str
    role: str
    depends_on: List[int]
    status: str  # pending, running, completed, error
    result: Optional[Dict[str, Any]]


class StreamEvent(TypedDict, total=False):
    """An SSE event emitted by the orchestrator."""
    event: str
    data: str  # JSON-encoded payload


# ============================================================================
# WorkflowOrchestrator
# ============================================================================

class WorkflowOrchestrator:
    """
    Coordinates multi-agent workflows with real-time streaming.

    Usage:
        orchestrator = WorkflowOrchestrator(
            model_name="claude-3-5-sonnet-20241022",
            notebook_id="abc",
            tools=langchain_tools,
        )
        async for event in orchestrator.run(query, mode=OrchestrationMode.TEAM):
            # event is a StreamEvent dict: {"event": "...", "data": "..."}
            yield event
    """

    def __init__(
        self,
        model_name: str,
        notebook_id: str,
        tools: list,
        session_id: Optional[str] = None,
        system_message: Optional[str] = None,
    ):
        """
        Args:
            model_name: LLM model name (e.g., "claude-3-5-sonnet-20241022")
            notebook_id: Notebook UUID for scoping queries
            tools: List of LangChain tools available to agents
            session_id: Optional chat session ID
            system_message: Optional base system message with notebook context
        """
        self.model_name = model_name
        self.notebook_id = notebook_id
        self.tools = tools
        self.session_id = session_id
        self.system_message = system_message

        # Accumulated results for post-run access
        self.agent_steps: List[Dict[str, Any]] = []
        self.tool_results: List[Dict[str, Any]] = []
        self.final_content: str = ""

    # ------------------------------------------------------------------
    # Helper: Load role-specific prompts from database
    # ------------------------------------------------------------------

    async def _get_role_prompt(self, role: AgentRole) -> str:
        """Load role-specific system prompt from database with fallback."""
        role_key_map = {
            AgentRole.RESEARCHER: "agent_role_researcher",
            AgentRole.ANALYST: "agent_role_analyst",
            AgentRole.PLANNER: "agent_role_planner",
        }

        template_key = role_key_map.get(role)
        if not template_key:
            return AGENT_SYSTEM_PROMPTS.get(role, "")

        try:
            return await load_prompt(
                template_key,
                variables={},
                fallback=AGENT_SYSTEM_PROMPTS[role]
            )
        except Exception:
            # If load fails, use fallback
            return AGENT_SYSTEM_PROMPTS[role]

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        query: str,
        mode: OrchestrationMode = OrchestrationMode.SINGLE,
        chat_history: Optional[List[Dict]] = None,
    ) -> AsyncIterator[StreamEvent]:
        """
        Execute the workflow and stream events.

        Args:
            query: User's query
            mode: Orchestration mode
            chat_history: Optional prior chat messages

        Yields:
            StreamEvent dicts compatible with sse_starlette
        """
        workflow_id = str(uuid.uuid4())[:8]

        yield self._event("workflow_started", {
            "workflow_id": workflow_id,
            "mode": mode.value,
            "query": query[:200],
            "timestamp": datetime.utcnow().isoformat(),
        })

        try:
            if mode == OrchestrationMode.SINGLE:
                async for event in self._run_single(query, chat_history):
                    yield event
            elif mode == OrchestrationMode.TEAM:
                async for event in self._run_team(query, chat_history):
                    yield event
            elif mode == OrchestrationMode.PLANNED:
                async for event in self._run_planned(query, chat_history):
                    yield event
            else:
                raise ValueError(f"Unknown orchestration mode: {mode}")

            yield self._event("workflow_complete", {
                "workflow_id": workflow_id,
                "mode": mode.value,
                "content_length": len(self.final_content),
                "timestamp": datetime.utcnow().isoformat(),
            })

        except Exception as e:
            yield self._event("workflow_error", {
                "workflow_id": workflow_id,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            })

    # ------------------------------------------------------------------
    # Mode 1: Single Agent
    # ------------------------------------------------------------------

    async def _run_single(
        self, query: str, chat_history: Optional[List[Dict]]
    ) -> AsyncIterator[StreamEvent]:
        """Route a simple query to a single DataQueryAgent."""
        yield self._event("agent_spawned", {
            "agent_name": "data_query",
            "agent_role": "single",
        })

        agent = DataQueryAgent(
            model_name=self.model_name,
            notebook_id=self.notebook_id,
            tools=self.tools,
            session_id=self.session_id,
            system_message=self.system_message,
            capture_tool_results=True,
        )

        accumulated = ""
        async for event in agent.stream_response(query, chat_history):
            if "agent" in event:
                messages = event["agent"].get("messages", [])
                if messages:
                    last = messages[-1]
                    if hasattr(last, "tool_calls") and last.tool_calls:
                        for tc in last.tool_calls:
                            yield self._event("agent_step", {
                                "step_type": "tool_call",
                                "content": f"Executing: {tc.get('name', 'unknown')}",
                                "status": "running",
                                "agent_name": "data_query",
                            })
                    elif hasattr(last, "content") and last.content:
                        text = last.content if isinstance(last.content, str) else ""
                        if text:
                            accumulated += text
                            yield self._event("chunk", {"content": text})

            elif "tools" in event:
                tool_evt = event["tools"].get("event", "")
                if tool_evt == "on_tool_end":
                    yield self._event("agent_step", {
                        "step_type": "tool_result",
                        "content": "Tool completed",
                        "status": "completed",
                        "agent_name": "data_query",
                    })

        self.final_content = accumulated
        self.agent_steps = agent.agent_steps
        self.tool_results = agent.get_captured_tool_results()

    # ------------------------------------------------------------------
    # Mode 2: Team Mode (parallel researcher + analyst)
    # ------------------------------------------------------------------

    async def _run_team(
        self, query: str, chat_history: Optional[List[Dict]]
    ) -> AsyncIterator[StreamEvent]:
        """Spawn researcher and analyst agents in parallel."""
        yield self._event("team_created", {
            "agents": ["researcher", "analyst"],
        })

        # Run both agents concurrently
        researcher_result: Dict[str, Any] = {}
        analyst_result: Dict[str, Any] = {}
        events_queue: asyncio.Queue[StreamEvent] = asyncio.Queue()

        async def run_agent(role: AgentRole, target: Dict):
            """Execute a single agent and push events to the shared queue."""
            role_prompt = await self._get_role_prompt(role)
            combined_system = f"{role_prompt}\n\n{self.system_message or ''}"

            agent = DataQueryAgent(
                model_name=self.model_name,
                notebook_id=self.notebook_id,
                tools=self.tools,
                session_id=self.session_id,
                system_message=combined_system,
                capture_tool_results=True,
            )

            await events_queue.put(self._event("agent_spawned", {
                "agent_name": role.value,
                "agent_role": role.value,
            }))

            accumulated = ""
            try:
                async for event in agent.stream_response(query, chat_history):
                    if "agent" in event:
                        messages = event["agent"].get("messages", [])
                        if messages:
                            last = messages[-1]
                            if hasattr(last, "content") and isinstance(last.content, str) and last.content:
                                accumulated += last.content
                                await events_queue.put(self._event("agent_message", {
                                    "agent_name": role.value,
                                    "content": last.content,
                                }))
                    elif "tools" in event:
                        tool_evt = event["tools"].get("event", "")
                        if tool_evt == "on_tool_start":
                            await events_queue.put(self._event("agent_step", {
                                "step_type": "tool_call",
                                "content": "Querying data source",
                                "status": "running",
                                "agent_name": role.value,
                            }))
                        elif tool_evt == "on_tool_end":
                            await events_queue.put(self._event("agent_step", {
                                "step_type": "tool_result",
                                "content": "Tool completed",
                                "status": "completed",
                                "agent_name": role.value,
                            }))

                target["agent_name"] = role.value
                target["agent_role"] = role.value
                target["response_text"] = accumulated
                target["tool_results"] = agent.get_captured_tool_results()
                target["agent_steps"] = agent.agent_steps

            except Exception as e:
                target["agent_name"] = role.value
                target["agent_role"] = role.value
                target["response_text"] = f"Agent {role.value} failed: {e}"
                target["tool_results"] = []
                target["agent_steps"] = []

                await events_queue.put(self._event("agent_step", {
                    "step_type": "error",
                    "content": f"Agent {role.value} failed: {e}",
                    "status": "error",
                    "agent_name": role.value,
                }))

        # Launch both agents
        tasks = [
            asyncio.create_task(run_agent(AgentRole.RESEARCHER, researcher_result)),
            asyncio.create_task(run_agent(AgentRole.ANALYST, analyst_result)),
        ]

        # Drain the event queue while agents are running
        done_count = 0
        while done_count < len(tasks):
            # Check if any tasks completed
            for t in tasks:
                if t.done() and not getattr(t, "_counted", False):
                    t._counted = True  # type: ignore[attr-defined]
                    done_count += 1

            # Drain available events
            while not events_queue.empty():
                yield events_queue.get_nowait()

            if done_count < len(tasks):
                await asyncio.sleep(0.05)

        # Drain any remaining events
        while not events_queue.empty():
            yield events_queue.get_nowait()

        # Await tasks to propagate any exceptions
        for t in tasks:
            if not t.done():
                await t

        # Synthesize
        yield self._event("agent_step", {
            "step_type": "synthesizing",
            "content": "Combining agent results",
            "status": "running",
        })

        synthesizer = SynthesizerAgent(
            model_name=self.model_name,
        )

        agent_results = [r for r in [researcher_result, analyst_result] if r.get("response_text")]
        synthesis = await synthesizer.synthesize(query, agent_results)

        self.final_content = synthesis["content"]
        self.tool_results = synthesis["tool_results"]
        self.agent_steps = synthesis["agent_steps"]

        # Stream synthesized content as chunks
        chunk_size = 120
        text = synthesis["content"]
        for i in range(0, len(text), chunk_size):
            yield self._event("chunk", {"content": text[i:i + chunk_size]})

    # ------------------------------------------------------------------
    # Mode 3: Planned Mode (planner + dynamic team)
    # ------------------------------------------------------------------

    async def _run_planned(
        self, query: str, chat_history: Optional[List[Dict]]
    ) -> AsyncIterator[StreamEvent]:
        """Use a planner to decompose the query, then execute tasks."""
        # Step 1: Plan
        yield self._event("agent_step", {
            "step_type": "planning",
            "content": "Decomposing query into sub-tasks",
            "status": "running",
        })

        plan = await self._generate_plan(query)

        if not plan:
            # Fallback to team mode if planning fails
            yield self._event("agent_step", {
                "step_type": "planning",
                "content": "Planning failed, falling back to team mode",
                "status": "error",
            })
            async for event in self._run_team(query, chat_history):
                yield event
            return

        yield self._event("agent_step", {
            "step_type": "planning",
            "content": f"Created {len(plan)} tasks",
            "status": "completed",
            "metadata": {"task_count": len(plan)},
        })

        for idx, task in enumerate(plan):
            yield self._event("task_created", {
                "task_index": idx,
                "task": task.get("task", ""),
                "role": task.get("role", "researcher"),
                "depends_on": task.get("depends_on", []),
            })

        # Step 2: Execute tasks respecting dependencies
        results_by_index: Dict[int, Dict[str, Any]] = {}

        # Group tasks by dependency level for parallel execution
        remaining = set(range(len(plan)))

        while remaining:
            # Find tasks whose dependencies are all satisfied
            ready = []
            for idx in remaining:
                deps = plan[idx].get("depends_on", [])
                if all(d in results_by_index for d in deps):
                    ready.append(idx)

            if not ready:
                # Circular dependency or bug - execute remaining sequentially
                ready = [min(remaining)]

            # Execute ready tasks in parallel
            task_futures = []
            for idx in ready:
                task_desc = plan[idx].get("task", "")
                role_str = plan[idx].get("role", "researcher")
                role = AgentRole.RESEARCHER if role_str == "researcher" else AgentRole.ANALYST

                # Enrich task with results from dependencies
                dep_context = ""
                for dep_idx in plan[idx].get("depends_on", []):
                    dep_result = results_by_index.get(dep_idx, {})
                    dep_text = dep_result.get("response_text", "")
                    if dep_text:
                        dep_context += f"\n\nPrior finding (task {dep_idx}): {dep_text[:500]}"

                enriched_query = f"{task_desc}\n\nOriginal user query: {query}{dep_context}"

                yield self._event("task_started", {
                    "task_index": idx,
                    "role": role.value,
                })

                task_futures.append((idx, role, enriched_query))

            # Run all ready tasks concurrently
            async def execute_task(idx: int, role: AgentRole, eq: str) -> Dict[str, Any]:
                role_prompt = await self._get_role_prompt(role)
                combined_system = f"{role_prompt}\n\n{self.system_message or ''}"

                agent = DataQueryAgent(
                    model_name=self.model_name,
                    notebook_id=self.notebook_id,
                    tools=self.tools,
                    session_id=self.session_id,
                    system_message=combined_system,
                    capture_tool_results=True,
                )

                try:
                    text = await agent.invoke(eq, chat_history)
                    return {
                        "agent_name": f"{role.value}_{idx}",
                        "agent_role": role.value,
                        "response_text": text,
                        "tool_results": agent.get_captured_tool_results(),
                        "agent_steps": agent.agent_steps,
                    }
                except Exception as e:
                    return {
                        "agent_name": f"{role.value}_{idx}",
                        "agent_role": role.value,
                        "response_text": f"Task failed: {e}",
                        "tool_results": [],
                        "agent_steps": [],
                    }

            coros = [execute_task(idx, role, eq) for idx, role, eq in task_futures]
            task_results = await asyncio.gather(*coros, return_exceptions=True)

            for (idx, _, _), result in zip(task_futures, task_results):
                if isinstance(result, Exception):
                    results_by_index[idx] = {
                        "agent_name": f"task_{idx}",
                        "agent_role": "unknown",
                        "response_text": f"Task {idx} raised: {result}",
                        "tool_results": [],
                        "agent_steps": [],
                    }
                else:
                    results_by_index[idx] = result

                yield self._event("task_completed", {
                    "task_index": idx,
                    "status": "error" if isinstance(result, Exception) else "completed",
                })

                remaining.discard(idx)

        # Step 3: Synthesize all task results
        yield self._event("agent_step", {
            "step_type": "synthesizing",
            "content": f"Synthesizing results from {len(results_by_index)} tasks",
            "status": "running",
        })

        synthesizer = SynthesizerAgent(model_name=self.model_name)
        all_results = [results_by_index[i] for i in sorted(results_by_index)]
        synthesis = await synthesizer.synthesize(query, all_results)

        self.final_content = synthesis["content"]
        self.tool_results = synthesis["tool_results"]
        self.agent_steps = synthesis["agent_steps"]

        # Stream synthesized content
        chunk_size = 120
        text = synthesis["content"]
        for i in range(0, len(text), chunk_size):
            yield self._event("chunk", {"content": text[i:i + chunk_size]})

    # ------------------------------------------------------------------
    # Planner helper
    # ------------------------------------------------------------------

    async def _generate_plan(self, query: str) -> Optional[List[AgentTask]]:
        """
        Use the LLM to decompose a query into sub-tasks.

        Returns:
            List of AgentTask dicts, or None on failure.
        """
        is_anthropic = any(x in self.model_name.lower() for x in ["claude", "anthropic"])

        if is_anthropic:
            llm = ChatAnthropic(model=self.model_name, temperature=0.2, max_tokens=2048)
        else:
            llm = ChatOpenAI(model=self.model_name, temperature=0.2, max_tokens=2048)

        prompt = f"""Decompose this user query into 2-5 concrete sub-tasks.

User Query: {query}

Return a JSON array. Each element must have:
- "task": a clear description of what the agent should do
- "role": either "researcher" (for data gathering) or "analyst" (for interpretation)
- "depends_on": array of 0-based task indices this task depends on (empty if independent)

Example:
[
  {{"task": "Retrieve sales data for Q4", "role": "researcher", "depends_on": []}},
  {{"task": "Analyze trends in the Q4 sales data", "role": "analyst", "depends_on": [0]}}
]

Return ONLY the JSON array, no other text."""

        try:
            planner_prompt = await self._get_role_prompt(AgentRole.PLANNER)
            response = await llm.ainvoke([
                SystemMessage(content=planner_prompt),
                HumanMessage(content=prompt),
            ])

            content = response.content.strip()
            # Strip markdown code fences
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            tasks = json.loads(content)
            if not isinstance(tasks, list):
                return None

            # Validate and assign IDs
            validated: List[AgentTask] = []
            for i, t in enumerate(tasks):
                validated.append({
                    "id": str(uuid.uuid4())[:8],
                    "task": t.get("task", f"Task {i}"),
                    "role": t.get("role", "researcher"),
                    "depends_on": t.get("depends_on", []),
                    "status": "pending",
                    "result": None,
                })

            return validated

        except Exception as e:
            print(f"[Orchestrator] Planning failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Event helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _event(event_type: str, data: Dict[str, Any]) -> StreamEvent:
        """Create a StreamEvent dict."""
        return {
            "event": event_type,
            "data": json.dumps(data),
        }
