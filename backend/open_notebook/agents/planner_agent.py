"""
Planner Agent

LangGraph-based agent that decomposes complex queries into executable plans.
Takes a QueryAnalysis from the QueryAnalyzer and produces an ExecutionPlan
with ordered subtasks, agent assignments, and dependency tracking.

For SIMPLE queries, the planner short-circuits with a single-task plan.
For MODERATE/COMPLEX queries, it uses the LLM to decompose and schedule.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from api.services.prompt_loader import load_prompt

from open_notebook.agents.query_analyzer import (
    QueryAnalysis,
    QueryComplexity,
    QueryIntent,
)


class TaskStatus(str, Enum):
    """Status of an individual subtask in the execution plan."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AgentRole(str, Enum):
    """Available agent roles for task assignment."""
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    DATA_ANALYST = "data_analyst"
    SYNTHESIZER = "synthesizer"
    WRITER = "writer"


@dataclass
class SubTask:
    """A single subtask within an execution plan."""
    id: str
    description: str
    agent_role: str
    dependencies: List[str] = field(default_factory=list)
    search_strategy: Optional[str] = None
    expected_output: str = ""
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    priority: int = 1  # 1 = highest

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "agent_role": self.agent_role,
            "dependencies": self.dependencies,
            "search_strategy": self.search_strategy,
            "expected_output": self.expected_output,
            "status": self.status.value,
            "result": self.result,
            "priority": self.priority,
        }


@dataclass
class ExecutionPlan:
    """
    Complete execution plan for a query.

    Contains ordered subtasks with dependencies, agent assignments,
    and resource estimates.
    """
    query: str
    complexity: QueryComplexity
    intent: QueryIntent
    subtasks: List[SubTask] = field(default_factory=list)
    parallel_groups: List[List[str]] = field(default_factory=list)
    estimated_total_time_seconds: float = 5.0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "complexity": self.complexity.value,
            "intent": self.intent.value,
            "subtasks": [t.to_dict() for t in self.subtasks],
            "parallel_groups": self.parallel_groups,
            "estimated_total_time_seconds": self.estimated_total_time_seconds,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    def get_ready_tasks(self) -> List[SubTask]:
        """Return tasks whose dependencies are all completed."""
        completed_ids = {
            t.id for t in self.subtasks if t.status == TaskStatus.COMPLETED
        }
        return [
            t
            for t in self.subtasks
            if t.status == TaskStatus.PENDING
            and all(dep in completed_ids for dep in t.dependencies)
        ]

    def mark_completed(self, task_id: str, result: Optional[str] = None) -> None:
        """Mark a subtask as completed."""
        for t in self.subtasks:
            if t.id == task_id:
                t.status = TaskStatus.COMPLETED
                t.result = result
                return

    def mark_failed(self, task_id: str, error: Optional[str] = None) -> None:
        """Mark a subtask as failed."""
        for t in self.subtasks:
            if t.id == task_id:
                t.status = TaskStatus.FAILED
                t.result = error
                return

    @property
    def is_complete(self) -> bool:
        """Check if all tasks are completed or failed."""
        return all(
            t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED)
            for t in self.subtasks
        )

    @property
    def progress_pct(self) -> float:
        """Return completion percentage."""
        if not self.subtasks:
            return 100.0
        done = sum(
            1
            for t in self.subtasks
            if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED)
        )
        return round((done / len(self.subtasks)) * 100, 1)


# ============================================================================
# LangGraph State
# ============================================================================

class PlannerState(TypedDict, total=False):
    """State for the planner workflow."""
    query_analysis: Dict[str, Any]
    plan: Dict[str, Any]
    phase: str
    error: Optional[str]


# ============================================================================
# Planning Prompt
# ============================================================================

# Fallback prompt
PLANNING_PROMPT = """You are a task planner for a multi-agent research system.

Given the following query analysis, create an execution plan that decomposes the work into subtasks.

Query Analysis:
{analysis_json}

Create a JSON plan with the following structure:
{{
    "subtasks": [
        {{
            "id": "task_1",
            "description": "<what this task does>",
            "agent_role": "researcher" | "analyst" | "data_analyst" | "synthesizer" | "writer",
            "dependencies": [<list of task IDs this depends on>],
            "search_strategy": "keyword" | "vector" | "hybrid" | "agentic_rag" | null,
            "expected_output": "<what this task produces>",
            "priority": <1-5, 1=highest>
        }}
    ],
    "parallel_groups": [[<task IDs that can run in parallel>], ...],
    "estimated_total_time_seconds": <float>
}}

Planning rules:
1. For SIMPLE queries: Create 1-2 subtasks (search + respond).
2. For MODERATE queries: Create 2-4 subtasks with some parallelism.
3. For COMPLEX queries: Create 3-6 subtasks with clear dependency chains.
4. The final subtask should always be a synthesis/response task.
5. Independent search tasks should be grouped in parallel_groups.
6. Use appropriate search strategies based on the query intent.
7. Data queries should use the data_analyst role.
8. Assign exactly one agent_role per task.

Available agent roles:
- researcher: Searches and retrieves information from sources
- analyst: Analyzes data, identifies patterns, draws conclusions
- data_analyst: Queries structured data (HANA tables, APIs)
- synthesizer: Combines findings from multiple tasks into a coherent answer
- writer: Generates formatted output (reports, summaries)

Return only valid JSON."""


# ============================================================================
# Planner Agent
# ============================================================================

class PlannerAgent:
    """
    LangGraph-based agent that creates execution plans from query analyses.

    For simple queries, generates plans without LLM calls.
    For moderate/complex queries, uses LLM to decompose and schedule.
    """

    def __init__(
        self,
        model_name: str = "gpt-4",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize the planner agent.

        Args:
            model_name: LLM model for planning
            base_url: Optional base URL for API
            api_key: Optional API key
        """
        self.model_name = model_name

        llm_kwargs = {
            "model": model_name,
            "temperature": 0.0,
        }
        if base_url:
            llm_kwargs["base_url"] = base_url
        if api_key:
            llm_kwargs["openai_api_key"] = api_key

        self.llm = ChatOpenAI(**llm_kwargs)

        # Build LangGraph workflow
        self.workflow = self._build_workflow()
        self.memory = MemorySaver()
        self.app = self.workflow.compile(checkpointer=self.memory)

    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph planner workflow."""
        workflow = StateGraph(PlannerState)

        workflow.add_node("classify", self._classify_node)
        workflow.add_node("plan_simple", self._plan_simple_node)
        workflow.add_node("plan_with_llm", self._plan_with_llm_node)
        workflow.add_node("validate", self._validate_node)

        workflow.set_entry_point("classify")

        workflow.add_conditional_edges(
            "classify",
            self._route_by_complexity,
            {
                "simple": "plan_simple",
                "needs_llm": "plan_with_llm",
            },
        )

        workflow.add_edge("plan_simple", "validate")
        workflow.add_edge("plan_with_llm", "validate")
        workflow.add_edge("validate", END)

        return workflow

    def _route_by_complexity(self, state: PlannerState) -> str:
        """Route to simple or LLM-based planning."""
        analysis = state.get("query_analysis", {})
        complexity = analysis.get("complexity", "moderate")
        if complexity == "simple":
            return "simple"
        return "needs_llm"

    async def _classify_node(self, state: PlannerState) -> Dict[str, Any]:
        """Classify and prepare for planning."""
        state["phase"] = "classifying"
        return state

    async def _plan_simple_node(self, state: PlannerState) -> Dict[str, Any]:
        """Generate a simple plan without LLM."""
        analysis = state.get("query_analysis", {})
        intent = analysis.get("intent", "factual_lookup")

        subtasks = []
        parallel_groups = []

        if intent == "conversational":
            subtasks.append({
                "id": "task_1",
                "description": "Generate conversational response",
                "agent_role": "researcher",
                "dependencies": [],
                "search_strategy": None,
                "expected_output": "Direct response to user",
                "priority": 1,
            })
        else:
            subtasks.append({
                "id": "task_1",
                "description": f"Search for information about: {analysis.get('original_query', '')}",
                "agent_role": "researcher",
                "dependencies": [],
                "search_strategy": "hybrid",
                "expected_output": "Relevant search results",
                "priority": 1,
            })
            subtasks.append({
                "id": "task_2",
                "description": "Formulate response from search results",
                "agent_role": "researcher",
                "dependencies": ["task_1"],
                "search_strategy": None,
                "expected_output": "Final answer to user query",
                "priority": 1,
            })
            parallel_groups.append(["task_1"])

        state["plan"] = {
            "subtasks": subtasks,
            "parallel_groups": parallel_groups,
            "estimated_total_time_seconds": 3.0,
        }
        state["phase"] = "planned"
        return state

    async def _plan_with_llm_node(self, state: PlannerState) -> Dict[str, Any]:
        """Generate a plan using LLM for moderate/complex queries."""
        analysis = state.get("query_analysis", {})

        # Load prompt from database
        prompt = await load_prompt(
            "agent_planning",
            variables={"analysis_json": json.dumps(analysis, indent=2, default=str)},
            fallback=PLANNING_PROMPT.format(analysis_json=json.dumps(analysis, indent=2, default=str))
        )

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])

            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            plan_data = json.loads(content)
            state["plan"] = plan_data
            state["phase"] = "planned"

        except json.JSONDecodeError as e:
            print(f"[PlannerAgent] JSON parsing error: {e}")
            state["plan"] = self._fallback_plan(analysis)
            state["phase"] = "planned_fallback"
        except Exception as e:
            print(f"[PlannerAgent] LLM planning error: {e}")
            state["plan"] = self._fallback_plan(analysis)
            state["phase"] = "planned_fallback"

        return state

    async def _validate_node(self, state: PlannerState) -> Dict[str, Any]:
        """Validate and fix the execution plan."""
        plan = state.get("plan", {})
        subtasks = plan.get("subtasks", [])

        # Ensure all task IDs are unique
        seen_ids = set()
        for task in subtasks:
            if task["id"] in seen_ids:
                task["id"] = f"{task['id']}_{len(seen_ids)}"
            seen_ids.add(task["id"])

        # Ensure all dependencies reference valid task IDs
        valid_ids = {t["id"] for t in subtasks}
        for task in subtasks:
            task["dependencies"] = [
                d for d in task.get("dependencies", []) if d in valid_ids
            ]

        # Ensure no circular dependencies
        self._remove_circular_deps(subtasks)

        # Ensure there is a final synthesis/response task
        if subtasks and subtasks[-1].get("agent_role") not in (
            "synthesizer",
            "writer",
            "researcher",
        ):
            subtasks.append({
                "id": f"task_{len(subtasks) + 1}",
                "description": "Synthesize results into final response",
                "agent_role": "synthesizer",
                "dependencies": [t["id"] for t in subtasks],
                "search_strategy": None,
                "expected_output": "Final synthesized response",
                "priority": 1,
            })

        plan["subtasks"] = subtasks
        state["plan"] = plan
        state["phase"] = "validated"
        return state

    def _remove_circular_deps(self, subtasks: List[Dict]) -> None:
        """Remove circular dependencies from subtask list in-place."""
        task_map = {t["id"]: t for t in subtasks}

        def has_cycle(task_id: str, visited: set, path: set) -> bool:
            visited.add(task_id)
            path.add(task_id)
            task = task_map.get(task_id)
            if not task:
                return False
            for dep in task.get("dependencies", []):
                if dep in path:
                    return True
                if dep not in visited and has_cycle(dep, visited, path):
                    return True
            path.discard(task_id)
            return False

        # Check each task and remove offending dependencies
        for task in subtasks:
            safe_deps = []
            for dep in task.get("dependencies", []):
                # Temporarily add dep, check for cycle
                task["dependencies"] = safe_deps + [dep]
                visited = set()
                path = set()
                if not has_cycle(task["id"], visited, path):
                    safe_deps.append(dep)
            task["dependencies"] = safe_deps

    def _fallback_plan(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a fallback plan when LLM fails."""
        complexity = analysis.get("complexity", "moderate")
        query = analysis.get("original_query", "")

        if complexity == "moderate":
            return {
                "subtasks": [
                    {
                        "id": "task_1",
                        "description": f"Search sources for: {query}",
                        "agent_role": "researcher",
                        "dependencies": [],
                        "search_strategy": "hybrid",
                        "expected_output": "Search results",
                        "priority": 1,
                    },
                    {
                        "id": "task_2",
                        "description": "Analyze and respond",
                        "agent_role": "analyst",
                        "dependencies": ["task_1"],
                        "search_strategy": None,
                        "expected_output": "Analysis and response",
                        "priority": 1,
                    },
                ],
                "parallel_groups": [["task_1"]],
                "estimated_total_time_seconds": 10.0,
            }
        else:  # complex
            return {
                "subtasks": [
                    {
                        "id": "task_1",
                        "description": f"Research: {query}",
                        "agent_role": "researcher",
                        "dependencies": [],
                        "search_strategy": "hybrid",
                        "expected_output": "Research results",
                        "priority": 1,
                    },
                    {
                        "id": "task_2",
                        "description": "Deep analysis of findings",
                        "agent_role": "analyst",
                        "dependencies": ["task_1"],
                        "search_strategy": "agentic_rag",
                        "expected_output": "Detailed analysis",
                        "priority": 2,
                    },
                    {
                        "id": "task_3",
                        "description": "Synthesize into comprehensive response",
                        "agent_role": "synthesizer",
                        "dependencies": ["task_1", "task_2"],
                        "search_strategy": None,
                        "expected_output": "Synthesized response",
                        "priority": 1,
                    },
                ],
                "parallel_groups": [["task_1"]],
                "estimated_total_time_seconds": 30.0,
            }

    async def create_plan(self, analysis: QueryAnalysis) -> ExecutionPlan:
        """
        Create an execution plan from a query analysis.

        Args:
            analysis: QueryAnalysis from the QueryAnalyzer

        Returns:
            ExecutionPlan with subtasks, dependencies, and scheduling
        """
        config = {
            "configurable": {
                "thread_id": f"planner_{datetime.utcnow().timestamp()}"
            }
        }

        initial_state: PlannerState = {
            "query_analysis": analysis.to_dict(),
            "plan": {},
            "phase": "initial",
            "error": None,
        }

        try:
            final_state = await self.app.ainvoke(initial_state, config)
            plan_data = final_state.get("plan", {})

            subtasks = [
                SubTask(
                    id=t["id"],
                    description=t["description"],
                    agent_role=t["agent_role"],
                    dependencies=t.get("dependencies", []),
                    search_strategy=t.get("search_strategy"),
                    expected_output=t.get("expected_output", ""),
                    priority=t.get("priority", 1),
                )
                for t in plan_data.get("subtasks", [])
            ]

            return ExecutionPlan(
                query=analysis.original_query,
                complexity=analysis.complexity,
                intent=analysis.intent,
                subtasks=subtasks,
                parallel_groups=plan_data.get("parallel_groups", []),
                estimated_total_time_seconds=plan_data.get(
                    "estimated_total_time_seconds", 5.0
                ),
                metadata={
                    "confidence": analysis.confidence,
                    "key_topics": analysis.key_topics,
                    "recommended_agent_roles": analysis.recommended_agent_roles,
                },
            )

        except Exception as e:
            print(f"[PlannerAgent] Planning failed: {e}")
            # Return minimal single-task plan
            return ExecutionPlan(
                query=analysis.original_query,
                complexity=analysis.complexity,
                intent=analysis.intent,
                subtasks=[
                    SubTask(
                        id="task_1",
                        description=f"Answer: {analysis.original_query}",
                        agent_role="researcher",
                        search_strategy="hybrid",
                        expected_output="Response to user query",
                    )
                ],
                parallel_groups=[["task_1"]],
                estimated_total_time_seconds=5.0,
                metadata={"error": str(e)},
            )
