"""
Plan Generation Service

Generates phased task plans with agent assignments and collaboration graphs
using LLMs. Takes a user goal, available resources, and goal analysis to
produce actionable execution plans.
"""

import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional

import httpx

from api.services.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt templates (kept as fallbacks for robustness)
# ---------------------------------------------------------------------------

PLAN_GENERATION_PROMPT = """Generate a task plan to achieve this goal.

GOAL: {goal}

ANALYSIS:
- Intent: {intent}
- Domain: {domain}
- Complexity: {complexity}

AVAILABLE RESOURCES:
- Data Sources: {sources}
- Tools: {tools}
- Agents: {agents}

IMPORTANT: Create ONLY user-actionable tasks. Do NOT include:
- System/infrastructure tasks (embeddings, indexing, database operations)
- UI navigation tasks (opening interfaces, clicking buttons)
- Setup/configuration tasks (these happen automatically)

Focus on:
- Analysis and research tasks the user must perform
- Decision-making tasks requiring human judgment
- Creative tasks (writing, designing, planning)
- Review and validation tasks

Create a phased plan with:
- 2-4 phases (logical groupings of related work)
- 2-5 meaningful tasks per phase
- Clear task descriptions focused on outcomes
- Realistic time estimates for each task

Return ONLY valid JSON:
{{
  "phases": [
    {{
      "name": "Phase Name",
      "description": "What this phase achieves",
      "tasks": [
        {{
          "name": "Task name",
          "description": "What to do",
          "success_criteria": "How to verify completion",
          "required_tools": ["tool_id"],
          "required_sources": ["source_id"],
          "dependencies": []
        }}
      ]
    }}
  ]
}}"""

AGENT_ASSIGNMENT_PROMPT = """Assign agents to tasks based on their capabilities.

TASKS:
{tasks_json}

AVAILABLE AGENTS:
{agents_json}

For each task, pick the best agent based on skill match and workload balance.
Related tasks should go to the same agent when possible.

Return ONLY valid JSON:
{{
  "assignments": [
    {{
      "task_id": "task_1_1",
      "agent_id": "agent-uuid",
      "reason": "Brief justification"
    }}
  ]
}}"""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class PlanGenerationService:
    """
    Generates phased task plans, assigns agents, estimates durations,
    and builds collaboration graphs using LLM-powered analysis.
    """

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_task_plan(
        self,
        goal: str,
        resources: Dict[str, Any],
        analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Use LLM to generate a phased plan for the given goal.

        Args:
            goal: The user's workspace goal.
            resources: Available resources (sources, tools, agents).
            analysis: Goal analysis output (intent, domain, complexity, etc.).

        Returns:
            Plan dict with phases, each containing tasks with unique IDs.
        """
        sources_summary = self._summarize_resources(
            resources.get("sources", []), key="title"
        )
        tools_summary = self._summarize_resources(
            resources.get("tools", []), key="name"
        )
        agents_summary = self._summarize_resources(
            resources.get("agents", []), key="name"
        )

        # Load prompt from database with fallback
        prompt = await load_prompt(
            "guided_plan_generation",
            variables={
                "goal": goal,
                "analysis": json.dumps(analysis, indent=2),
                "resources": json.dumps({
                    "sources": sources_summary,
                    "tools": tools_summary,
                    "agents": agents_summary
                }, indent=2)
            },
            fallback=PLAN_GENERATION_PROMPT.format(
                goal=goal,
                intent=analysis.get("intent", "research"),
                domain=analysis.get("domain", "general"),
                complexity=analysis.get("complexity", "moderate"),
                sources=sources_summary,
                tools=tools_summary,
                agents=agents_summary,
            )
        )

        raw = await self._call_llm(prompt)
        plan = self._parse_json_response(raw)

        # Assign unique IDs to every task
        plan = self._assign_task_ids(plan)

        logger.info(
            "Generated plan with %d phase(s) and %d total task(s)",
            len(plan.get("phases", [])),
            sum(
                len(p.get("tasks", []))
                for p in plan.get("phases", [])
            ),
        )
        return plan

    async def assign_agents_to_tasks(
        self,
        plan: Dict[str, Any],
        agents: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Match agent capabilities to task requirements.

        Assigns an agent_id to each task based on skills match,
        workload distribution, and task dependencies.

        Args:
            plan: Plan dict from generate_task_plan.
            agents: List of available agent dicts (id, name, skills, ...).

        Returns:
            Updated plan with assigned_agent_id per task.
        """
        if not agents:
            logger.warning("No agents available for assignment")
            return plan

        # Flatten tasks for the LLM prompt
        flat_tasks = []
        for phase in plan.get("phases", []):
            for task in phase.get("tasks", []):
                flat_tasks.append({
                    "id": task.get("id", ""),
                    "name": task.get("name", ""),
                    "description": task.get("description", ""),
                    "required_tools": task.get("required_tools", []),
                    "dependencies": task.get("dependencies", []),
                })

        agents_info = [
            {
                "id": a.get("id", ""),
                "name": a.get("name", ""),
                "skills": a.get("skills", []),
                "role": a.get("role", "general"),
            }
            for a in agents
        ]

        # Load prompt from database with fallback
        prompt = await load_prompt(
            "guided_agent_assignment",
            variables={
                "tasks_json": json.dumps(flat_tasks, indent=2),
                "available_agents": json.dumps(agents_info, indent=2)
            },
            fallback=AGENT_ASSIGNMENT_PROMPT.format(
                tasks_json=json.dumps(flat_tasks, indent=2),
                agents_json=json.dumps(agents_info, indent=2),
            )
        )

        raw = await self._call_llm(prompt)
        result = self._parse_json_response(raw)

        # Build lookup: task_id -> agent_id
        assignment_map: Dict[str, str] = {}
        for entry in result.get("assignments", []):
            assignment_map[entry["task_id"]] = entry["agent_id"]

        # Apply assignments into the plan
        for phase in plan.get("phases", []):
            for task in phase.get("tasks", []):
                tid = task.get("id", "")
                if tid in assignment_map:
                    task["assigned_agent_id"] = assignment_map[tid]
                else:
                    # Round-robin fallback
                    task["assigned_agent_id"] = self._fallback_agent(
                        agents, flat_tasks, tid
                    )

        logger.info(
            "Assigned agents to %d task(s) across %d agent(s)",
            len(flat_tasks),
            len(agents),
        )
        return plan

    def estimate_durations(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Estimate duration for each task based on complexity heuristics.

        Complexity buckets:
        - simple:   5-15 min
        - moderate: 15-30 min
        - complex:  30-60 min

        Adds a buffer for tasks that have dependencies.

        Args:
            plan: Plan dict with phases and tasks.

        Returns:
            Updated plan with estimated_duration (minutes) per task.
        """
        complexity_ranges = {
            "simple": (5, 15),
            "moderate": (15, 30),
            "complex": (30, 60),
        }

        for phase in plan.get("phases", []):
            for task in phase.get("tasks", []):
                complexity = self._infer_task_complexity(task)
                lo, hi = complexity_ranges.get(complexity, (15, 30))
                base = (lo + hi) // 2

                # Add buffer for tasks with dependencies
                deps = task.get("dependencies", [])
                buffer = 5 * len(deps) if deps else 0

                task["estimated_duration"] = base + buffer
                task["complexity"] = complexity

        total = sum(
            t.get("estimated_duration", 0)
            for p in plan.get("phases", [])
            for t in p.get("tasks", [])
        )
        logger.info("Estimated total duration: %d minutes", total)
        return plan

    def build_collaboration_graph(
        self,
        plan: Dict[str, Any],
        agents: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Analyze task assignments and dependencies to build a collaboration graph.

        Args:
            plan: Plan dict with agent assignments.
            agents: List of agent dicts.

        Returns:
            Graph dict with nodes (agents) and edges (collaboration links).
            Format matches frontend expectations:
            - nodes: {id, type, name, tasks: [task_names]}
            - edges: {from, to, relationship: 'depends_on'|'collaborates_with'|'shares_data'}
        """
        agent_lookup = {a.get("id", ""): a for a in agents}

        # Count tasks per agent and collect task names
        agent_task_names: Dict[str, List[str]] = {}
        task_agent_map: Dict[str, str] = {}

        for phase in plan.get("phases", []):
            for task in phase.get("tasks", []):
                aid = task.get("assigned_agent_id", "")
                tid = task.get("id", "")
                task_name = task.get("name", "Untitled Task")
                if aid:
                    agent_task_names.setdefault(aid, []).append(task_name)
                    task_agent_map[tid] = aid

        # Build nodes - format: {id, type, name, tasks}
        nodes = []
        for aid, task_names in agent_task_names.items():
            agent_info = agent_lookup.get(aid, {})
            nodes.append({
                "id": aid,
                "type": agent_info.get("type", "agent"),  # 'agent' or 'team'
                "name": agent_info.get("name", "Unknown"),
                "tasks": task_names,
            })

        # Build edges from task dependencies
        edges = []
        seen_edges = set()

        for phase in plan.get("phases", []):
            for task in phase.get("tasks", []):
                tid = task.get("id", "")
                current_agent = task_agent_map.get(tid, "")

                for dep_id in task.get("dependencies", []):
                    dep_agent = task_agent_map.get(dep_id, "")
                    if dep_agent and dep_agent != current_agent:
                        edge_key = (dep_agent, current_agent)
                        if edge_key not in seen_edges:
                            seen_edges.add(edge_key)
                            edges.append({
                                "from": dep_agent,
                                "to": current_agent,
                                "relationship": "depends_on",  # Sequential execution
                            })

        # Check for shared resources (sources/tools) - indicates data sharing
        task_resources: Dict[str, set] = {}
        for phase in plan.get("phases", []):
            for task in phase.get("tasks", []):
                tid = task.get("id", "")
                resources = set(task.get("required_sources", []) + task.get("required_tools", []))
                task_resources[tid] = resources

        # Find agents sharing resources
        for i, (aid1, _) in enumerate(agent_task_names.items()):
            for aid2, _ in list(agent_task_names.items())[i + 1:]:
                # Get all resources for this agent pair
                resources1 = set()
                resources2 = set()
                for tid, agent_id in task_agent_map.items():
                    if agent_id == aid1:
                        resources1.update(task_resources.get(tid, set()))
                    elif agent_id == aid2:
                        resources2.update(task_resources.get(tid, set()))

                # If they share resources, add shares_data edge
                shared = resources1 & resources2
                if shared:
                    edge_key = (aid1, aid2)
                    if edge_key not in seen_edges:
                        seen_edges.add(edge_key)
                        edges.append({
                            "from": aid1,
                            "to": aid2,
                            "relationship": "shares_data",  # Data exchange
                        })

        # Add co-assignment edges (agents working in parallel in same phase)
        for phase in plan.get("phases", []):
            phase_agents = set()
            for task in phase.get("tasks", []):
                aid = task.get("assigned_agent_id", "")
                if aid:
                    phase_agents.add(aid)

            phase_agents_list = sorted(phase_agents)
            for i in range(len(phase_agents_list)):
                for j in range(i + 1, len(phase_agents_list)):
                    edge_key = (phase_agents_list[i], phase_agents_list[j])
                    if edge_key not in seen_edges:
                        seen_edges.add(edge_key)
                        edges.append({
                            "from": phase_agents_list[i],
                            "to": phase_agents_list[j],
                            "relationship": "collaborates_with",  # Parallel work
                        })

        logger.info(
            "Built collaboration graph: %d node(s), %d edge(s)",
            len(nodes),
            len(edges),
        )
        return {"nodes": nodes, "edges": edges}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _assign_task_ids(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Assign unique IDs to every task in the plan."""
        for phase_idx, phase in enumerate(plan.get("phases", []), start=1):
            for task_idx, task in enumerate(phase.get("tasks", []), start=1):
                if not task.get("id"):
                    task["id"] = f"task_{phase_idx}_{task_idx}"
        return plan

    @staticmethod
    def _infer_task_complexity(task: Dict[str, Any]) -> str:
        """Heuristic complexity inference based on task properties."""
        desc = (task.get("description", "") + " " + task.get("name", "")).lower()
        tools = task.get("required_tools", [])
        deps = task.get("dependencies", [])

        complex_signals = [
            "analyze", "integrate", "orchestrate", "optimize",
            "synthesize", "transform", "aggregate", "correlate",
        ]
        simple_signals = [
            "connect", "list", "fetch", "load", "check", "verify",
            "configure", "setup", "set up",
        ]

        if len(tools) >= 3 or len(deps) >= 2:
            return "complex"
        if any(s in desc for s in complex_signals):
            return "complex"
        if any(s in desc for s in simple_signals) and len(tools) <= 1:
            return "simple"
        return "moderate"

    @staticmethod
    def _fallback_agent(
        agents: List[Dict[str, Any]],
        all_tasks: List[Dict[str, Any]],
        task_id: str,
    ) -> str:
        """Simple round-robin fallback when LLM doesn't assign an agent."""
        if not agents:
            return ""
        # Use task_id hash to deterministically pick an agent
        idx = hash(task_id) % len(agents)
        return agents[idx].get("id", "")

    @staticmethod
    def _summarize_resources(
        items: List[Dict[str, Any]],
        key: str = "name",
    ) -> str:
        """Produce a concise summary string for LLM prompts."""
        if not items:
            return "None"
        names = [item.get(key, item.get("id", "unknown")) for item in items]
        return ", ".join(names[:20])

    async def _get_llm_config(self) -> Dict[str, str]:
        """
        Resolve LLM credentials from the settings / credentials store.

        Returns:
            Dict with base_url, api_key, model_name.

        Raises:
            RuntimeError: When no language model is configured.
        """
        from api.routers.credentials import _credentials_store
        from api.services.settings import get_setting

        model_id = await get_setting("language_model_id", "")
        if not model_id:
            raise RuntimeError(
                "No language model configured. "
                "Please select a model in Settings -> Models."
            )

        credential = _credentials_store.get(model_id)
        if not credential:
            raise RuntimeError(
                f"Language model '{model_id}' not found in credentials."
            )

        return {
            "base_url": credential["base_url"],
            "api_key": credential["api_key"],
            "model_name": credential.get(
                "model_name", credential.get("name", "gpt-4")
            ),
        }

    async def _call_llm(self, prompt: str) -> str:
        """
        Call the configured LLM with a prompt and return raw text.

        Args:
            prompt: The full prompt to send.

        Returns:
            Raw assistant message content.
        """
        config = await self._get_llm_config()

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{config['base_url']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {config['api_key']}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config["model_name"],
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a task planning assistant. "
                                "Always respond with valid JSON only."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.4,
                    "max_tokens": 3000,
                },
            )

            if response.status_code != 200:
                logger.error(
                    "LLM API error %d: %s",
                    response.status_code,
                    response.text[:500],
                )
                raise RuntimeError(
                    f"LLM API error: {response.status_code}"
                )

            result = response.json()
            return result["choices"][0]["message"]["content"]

    @staticmethod
    def _parse_json_response(text: str) -> Dict[str, Any]:
        """
        Extract and parse JSON from an LLM response that may contain
        markdown fences or surrounding prose.
        """
        cleaned = text.strip()

        # Strip markdown code fences
        json_match = re.search(
            r"```(?:json)?\s*\n?(.*?)\n?```", cleaned, re.DOTALL
        )
        if json_match:
            cleaned = json_match.group(1).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Fall back: find first JSON object in text
            brace_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if brace_match:
                try:
                    return json.loads(brace_match.group(0))
                except json.JSONDecodeError:
                    pass

        logger.warning("Could not parse LLM JSON response: %s", cleaned[:200])
        return {"phases": []}


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_plan_generation_service: Optional[PlanGenerationService] = None


def get_plan_generation_service() -> PlanGenerationService:
    """Get or create the PlanGenerationService singleton."""
    global _plan_generation_service
    if _plan_generation_service is None:
        _plan_generation_service = PlanGenerationService()
    return _plan_generation_service
