"""
Agent Manager - AgentTeam orchestrator for coordinating multi-agent workflows.

Provides:
- AgentTeam creation and lifecycle management
- Agent registration and instantiation
- Coordinated execution loop (plan -> assign -> execute -> collect)
- Progress streaming via async iterators
- Integration with TaskManager and MessageBus
"""

import asyncio
import json
from datetime import datetime
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Type

from open_notebook.agents.base_agent import BaseAgent
from open_notebook.agents.messaging import MessageBus
from open_notebook.agents.task_manager import TaskManager
from open_notebook.domain.agent_team import AgentInstance, AgentTask, AgentTeam


# Registry mapping role names to BaseAgent subclasses
_AGENT_REGISTRY: Dict[str, Type[BaseAgent]] = {}


def register_agent(role: str, agent_cls: Type[BaseAgent]) -> None:
    """
    Register a BaseAgent subclass for a role.

    Args:
        role: Role name (e.g. "researcher", "analyst")
        agent_cls: Class implementing BaseAgent
    """
    _AGENT_REGISTRY[role] = agent_cls


def get_agent_class(role: str) -> Optional[Type[BaseAgent]]:
    """Look up the registered agent class for a role."""
    return _AGENT_REGISTRY.get(role)


class AgentManager:
    """
    Orchestrator that creates and runs an agent team.

    Lifecycle::

        mgr = AgentManager()

        # 1. Create a team
        team = await mgr.create_team("Research Project", goal="Analyze quarterly data")

        # 2. Add agents
        await mgr.add_agent(team.id, role="researcher", name="Researcher-1")
        await mgr.add_agent(team.id, role="analyst", name="Analyst-1")

        # 3. Add tasks
        t1 = await mgr.add_task(team.id, "Gather data")
        t2 = await mgr.add_task(team.id, "Analyze data", depends_on=[t1.id])

        # 4. Run
        result = await mgr.run_team(team.id)

    The manager coordinates:
    - Task scheduling (via TaskManager)
    - Inter-agent messaging (via MessageBus)
    - Agent lifecycle (idle -> busy -> completed/failed)
    - Team lifecycle (pending -> running -> completed/failed)
    """

    def __init__(
        self,
        model_name: str = "gpt-4",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        max_iterations: int = 50,
        progress_callback: Optional[Callable] = None,
    ):
        """
        Args:
            model_name: Default LLM model for agents
            base_url: Optional LLM API base URL
            api_key: Optional LLM API key
            max_iterations: Safety limit on scheduling iterations
            progress_callback: Optional callback(team_id, phase, progress, message)
        """
        self.model_name = model_name
        self.base_url = base_url
        self.api_key = api_key
        self.max_iterations = max_iterations
        self.progress_callback = progress_callback

        # Active state per team
        self._buses: Dict[str, MessageBus] = {}
        self._task_managers: Dict[str, TaskManager] = {}
        self._agents: Dict[str, Dict[str, BaseAgent]] = {}  # team_id -> {agent_id -> agent}

    # ------------------------------------------------------------------
    # Team lifecycle
    # ------------------------------------------------------------------

    async def create_team(
        self,
        name: str,
        goal: Optional[str] = None,
        notebook_id: Optional[str] = None,
        session_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> AgentTeam:
        """
        Create a new agent team.

        Args:
            name: Team name
            goal: High-level goal description
            notebook_id: Optional notebook context
            session_id: Optional chat session context
            config: Optional configuration overrides

        Returns:
            Persisted AgentTeam
        """
        team = AgentTeam(
            name=name,
            goal=goal,
            notebook_id=notebook_id,
            session_id=session_id,
        )
        if config:
            team.set_config(config)
        await team.save()

        # Initialize in-memory structures
        self._buses[team.id] = MessageBus(team_id=team.id)
        self._task_managers[team.id] = TaskManager(team_id=team.id)
        self._agents[team.id] = {}

        return team

    async def add_agent(
        self,
        team_id: str,
        role: str,
        name: str,
        model_name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> AgentInstance:
        """
        Add an agent to a team.

        If a BaseAgent subclass is registered for the role, it will be
        instantiated when the team runs.

        Args:
            team_id: Team to add to
            role: Agent role
            name: Human-readable agent name
            model_name: LLM model override
            system_prompt: System prompt override
            config: Role-specific configuration

        Returns:
            Persisted AgentInstance
        """
        instance = AgentInstance(
            team_id=team_id,
            role=role,
            name=name,
            model_name=model_name or self.model_name,
            system_prompt=system_prompt,
        )
        if config:
            instance.set_config(config)
        await instance.save()

        # Subscribe to message bus
        bus = self._buses.get(team_id)
        if bus:
            bus.subscribe(instance.id)

        return instance

    async def add_task(
        self,
        team_id: str,
        title: str,
        description: Optional[str] = None,
        depends_on: Optional[List[str]] = None,
        priority: int = 0,
        assignee_id: Optional[str] = None,
    ) -> AgentTask:
        """
        Add a task to a team.

        Args:
            team_id: Team to add to
            title: Task title
            description: Task description
            depends_on: List of prerequisite task IDs
            priority: 0=normal, 1=high, 2=critical
            assignee_id: Optional pre-assigned agent

        Returns:
            Persisted AgentTask
        """
        mgr = self._task_managers.get(team_id)
        if mgr is None:
            mgr = TaskManager(team_id=team_id)
            self._task_managers[team_id] = mgr

        return await mgr.create_task(
            title=title,
            description=description,
            depends_on=depends_on,
            priority=priority,
            assignee_id=assignee_id,
        )

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def run_team(
        self,
        team_id: str,
        input_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute the team's task plan to completion.

        Runs an iterative loop:
        1. Find ready tasks
        2. Match to idle agents
        3. Execute tasks concurrently
        4. Repeat until all tasks done or max iterations reached

        Args:
            team_id: Team to run
            input_data: Optional initial input shared with all agents

        Returns:
            Dict with team result and task summaries
        """
        team = await AgentTeam.get(team_id)
        if team is None:
            raise ValueError(f"Team {team_id} not found")

        task_mgr = self._task_managers.get(team_id) or TaskManager(team_id=team_id)
        self._task_managers[team_id] = task_mgr

        bus = self._buses.get(team_id) or MessageBus(team_id=team_id)
        self._buses[team_id] = bus

        await team.mark_running()
        self._notify_progress(team_id, "running", 0, "Team started")

        input_data = input_data or {}
        iteration = 0

        try:
            while iteration < self.max_iterations:
                iteration += 1

                # Check if all tasks are done
                if await task_mgr.is_complete():
                    break

                # Get ready tasks
                ready = await task_mgr.get_ready_tasks()
                if not ready:
                    # No ready tasks but not complete -> tasks may be in_progress
                    in_progress = await task_mgr.get_all_tasks(status="in_progress")
                    if not in_progress:
                        # Deadlock or all failed
                        break
                    # Wait briefly for in-progress tasks
                    await asyncio.sleep(0.1)
                    continue

                # Get team agents
                agents_db = await team.get_agents()
                agent_objects = await self._ensure_agents(team_id, agents_db)

                # Assign and execute ready tasks
                progress = int((iteration / self.max_iterations) * 100)
                self._notify_progress(
                    team_id, "executing", min(progress, 95),
                    f"Iteration {iteration}: {len(ready)} tasks ready"
                )

                await self._execute_round(task_mgr, agent_objects, ready, input_data)

            # Collect results
            summary = await task_mgr.summary()
            all_tasks = await task_mgr.get_all_tasks()
            task_results = {}
            for t in all_tasks:
                task_results[t.id] = {
                    "title": t.title,
                    "status": t.status,
                    "result": t.get_result(),
                    "error": t.error,
                }

            result = {
                "summary": summary,
                "tasks": task_results,
                "iterations": iteration,
            }

            if summary.get("complete"):
                await team.mark_completed(result)
                self._notify_progress(team_id, "completed", 100, "All tasks completed")
            else:
                failed_count = summary.get("by_status", {}).get("failed", 0)
                if failed_count > 0:
                    await team.mark_failed(f"{failed_count} task(s) failed")
                else:
                    await team.mark_completed(result)
                self._notify_progress(team_id, "completed", 100, "Team finished")

            return result

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            await team.mark_failed(error_msg)
            self._notify_progress(team_id, "failed", 0, error_msg)
            raise

    async def run_team_streaming(
        self,
        team_id: str,
        input_data: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Execute the team and stream progress events.

        Yields dicts with keys: phase, progress, message, data.
        """
        team = await AgentTeam.get(team_id)
        if team is None:
            raise ValueError(f"Team {team_id} not found")

        task_mgr = self._task_managers.get(team_id) or TaskManager(team_id=team_id)
        self._task_managers[team_id] = task_mgr

        bus = self._buses.get(team_id) or MessageBus(team_id=team_id)
        self._buses[team_id] = bus

        await team.mark_running()
        yield {"phase": "running", "progress": 0, "message": "Team started"}

        input_data = input_data or {}
        iteration = 0

        try:
            while iteration < self.max_iterations:
                iteration += 1

                if await task_mgr.is_complete():
                    break

                ready = await task_mgr.get_ready_tasks()
                if not ready:
                    in_progress = await task_mgr.get_all_tasks(status="in_progress")
                    if not in_progress:
                        break
                    await asyncio.sleep(0.1)
                    continue

                agents_db = await team.get_agents()
                agent_objects = await self._ensure_agents(team_id, agents_db)

                progress = int((iteration / self.max_iterations) * 100)
                yield {
                    "phase": "executing",
                    "progress": min(progress, 95),
                    "message": f"Iteration {iteration}: {len(ready)} tasks ready",
                    "ready_tasks": [t.title for t in ready],
                }

                completed_tasks = await self._execute_round(task_mgr, agent_objects, ready, input_data)
                for task, result in completed_tasks:
                    yield {
                        "phase": "task_completed",
                        "progress": min(progress, 95),
                        "message": f"Completed: {task.title}",
                        "task_id": task.id,
                        "task_result": result,
                    }

            summary = await task_mgr.summary()
            await team.mark_completed({"summary": summary})
            yield {"phase": "completed", "progress": 100, "message": "All tasks done", "summary": summary}

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            await team.mark_failed(error_msg)
            yield {"phase": "failed", "progress": 0, "message": error_msg}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _ensure_agents(
        self,
        team_id: str,
        instances: List[AgentInstance],
    ) -> Dict[str, BaseAgent]:
        """
        Ensure BaseAgent objects exist for all instances.

        Creates them on first access using the agent registry.
        """
        if team_id not in self._agents:
            self._agents[team_id] = {}

        team_agents = self._agents[team_id]

        for inst in instances:
            if inst.id not in team_agents:
                cls = get_agent_class(inst.role) or _DefaultAgent
                team_agents[inst.id] = cls(
                    instance=inst,
                    model_name=inst.model_name or self.model_name,
                    base_url=self.base_url,
                    api_key=self.api_key,
                )

        return team_agents

    async def _execute_round(
        self,
        task_mgr: TaskManager,
        agents: Dict[str, BaseAgent],
        ready_tasks: List[AgentTask],
        input_data: Dict[str, Any],
    ) -> List[tuple]:
        """
        Execute one round of task assignments and return results.

        Returns list of (task, result) tuples for completed tasks.
        """
        # Find idle agents
        idle_agents = [
            agent for agent in agents.values()
            if agent.instance.status in ("idle", "completed")
        ]

        completed = []
        coros = []

        for task in ready_tasks:
            if not idle_agents:
                break

            # If task has a pre-assigned agent, use that
            if task.assignee_id and task.assignee_id in agents:
                agent = agents[task.assignee_id]
            else:
                agent = idle_agents.pop(0)

            await task_mgr.assign_task(task.id, agent.instance.id)

            async def _run_task(t: AgentTask, a: BaseAgent) -> tuple:
                task_input = {
                    **input_data,
                    "task_id": t.id,
                    "task_title": t.title,
                    "task_description": t.description,
                }
                try:
                    result = await a.run(task_input)
                    await task_mgr.complete_task(t.id, result)
                    return (t, result)
                except Exception as e:
                    await task_mgr.fail_task(t.id, str(e))
                    return (t, {"error": str(e)})

            coros.append(_run_task(task, agent))

        if coros:
            results = await asyncio.gather(*coros, return_exceptions=True)
            for r in results:
                if isinstance(r, tuple):
                    completed.append(r)

        return completed

    def _notify_progress(
        self, team_id: str, phase: str, progress: int, message: str
    ) -> None:
        """Fire the progress callback if configured."""
        if self.progress_callback:
            try:
                self.progress_callback(team_id, phase, progress, message)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def cancel_team(self, team_id: str) -> None:
        """Cancel a running team."""
        team = await AgentTeam.get(team_id)
        if team:
            team.status = "cancelled"
            team.completed_at = datetime.utcnow().isoformat()
            await team.save()

        bus = self._buses.pop(team_id, None)
        if bus:
            bus.clear()
        self._task_managers.pop(team_id, None)
        self._agents.pop(team_id, None)

    def get_message_bus(self, team_id: str) -> Optional[MessageBus]:
        """Get the message bus for a team."""
        return self._buses.get(team_id)

    def get_task_manager(self, team_id: str) -> Optional[TaskManager]:
        """Get the task manager for a team."""
        return self._task_managers.get(team_id)


class _DefaultAgent(BaseAgent):
    """
    Fallback agent used when no specific class is registered for a role.

    Uses the LLM directly with the task description as the prompt.
    """

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        title = input_data.get("task_title", "Unknown task")
        description = input_data.get("task_description", "")

        self.record_step("thinking", f"Working on: {title}", status="running")

        prompt = f"""You are a {self.role} agent. Complete this task:

Title: {title}
Description: {description}

Provide your result as a JSON object."""

        try:
            result = await self.invoke_llm_json(prompt)
            self.update_last_step(status="completed", content=f"Completed: {title}")
            return result if isinstance(result, dict) else {"output": result}
        except Exception:
            # Fall back to raw text if JSON parsing fails
            raw = await self.invoke_llm(prompt)
            self.update_last_step(status="completed", content=f"Completed: {title}")
            return {"output": raw}
