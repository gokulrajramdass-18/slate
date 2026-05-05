"""
Task Manager - Task lifecycle and dependency resolution for agent teams.

Provides:
- Task creation with dependency chains
- Topological dependency resolution
- Automatic unblocking when upstream tasks complete
- Cycle detection in dependency graphs
- Assignment of ready tasks to idle agents
"""

import json
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from open_notebook.domain.agent_team import AgentInstance, AgentTask, AgentTeam


class DependencyCycleError(Exception):
    """Raised when a circular dependency is detected in the task graph."""
    pass


class TaskManager:
    """
    Manages the task lifecycle for a single agent team.

    Responsibilities:
    - Create tasks with dependencies
    - Resolve which tasks are ready to run
    - Assign tasks to agents
    - Handle task completion and cascade unblocking
    - Detect dependency cycles

    Usage::

        mgr = TaskManager(team_id="team-123")

        t1 = await mgr.create_task("Gather data", description="...")
        t2 = await mgr.create_task("Analyze", depends_on=[t1.id])
        t3 = await mgr.create_task("Report", depends_on=[t2.id])

        ready = await mgr.get_ready_tasks()
        # -> [t1] (t2 and t3 are blocked)

        await mgr.complete_task(t1.id, result={"data": [...]})
        ready = await mgr.get_ready_tasks()
        # -> [t2]
    """

    def __init__(self, team_id: str):
        self.team_id = team_id

    async def create_task(
        self,
        title: str,
        description: Optional[str] = None,
        depends_on: Optional[List[str]] = None,
        priority: int = 0,
        assignee_id: Optional[str] = None,
    ) -> AgentTask:
        """
        Create a new task in this team.

        Args:
            title: Short task title
            description: Detailed description
            depends_on: List of task IDs this task depends on
            priority: 0=normal, 1=high, 2=critical
            assignee_id: Optional agent to pre-assign

        Returns:
            Created AgentTask

        Raises:
            DependencyCycleError: If adding this dependency would create a cycle
        """
        task = AgentTask(
            team_id=self.team_id,
            title=title,
            description=description,
            priority=priority,
            assignee_id=assignee_id,
            status="pending",
        )

        if depends_on:
            # Validate that dependency tasks exist and belong to this team
            for dep_id in depends_on:
                dep = await AgentTask.get(dep_id)
                if dep is None or dep.team_id != self.team_id:
                    raise ValueError(f"Dependency task {dep_id} not found in team {self.team_id}")
            task.set_dependency_ids(depends_on)

        await task.save()

        # Validate no cycles after insertion
        if depends_on:
            try:
                await self._check_cycles()
            except DependencyCycleError:
                # Roll back: delete the task
                await task.delete()
                raise

        return task

    async def get_ready_tasks(self) -> List[AgentTask]:
        """
        Get all tasks that are pending and have no unresolved dependencies.

        Returns:
            List of tasks ready to be assigned, ordered by priority (desc) then creation time
        """
        return await AgentTask.get_ready_tasks(self.team_id)

    async def get_all_tasks(self, status: Optional[str] = None) -> List[AgentTask]:
        """
        Get all tasks in this team, optionally filtered by status.

        Args:
            status: Optional status filter

        Returns:
            List of AgentTask
        """
        filters: Dict[str, Any] = {"team_id": self.team_id}
        if status:
            filters["status"] = status
        return await AgentTask.get_all(filters=filters, order_by="priority DESC, created ASC")

    async def assign_task(self, task_id: str, agent_id: str) -> AgentTask:
        """
        Assign a task to an agent and mark it in_progress.

        Args:
            task_id: Task to assign
            agent_id: Agent to assign to

        Returns:
            Updated AgentTask

        Raises:
            ValueError: If task is blocked or already in_progress/completed
        """
        task = await AgentTask.get(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")
        if task.status not in ("pending",):
            raise ValueError(f"Task {task_id} is {task.status}, cannot assign")
        if await task.is_blocked():
            raise ValueError(f"Task {task_id} is blocked by dependencies")

        await task.assign(agent_id)
        return task

    async def complete_task(self, task_id: str, result: Any = None) -> AgentTask:
        """
        Mark a task as completed and return it.

        After completion, downstream tasks may become unblocked.

        Args:
            task_id: Task to complete
            result: Optional result data

        Returns:
            Updated AgentTask
        """
        task = await AgentTask.get(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")

        await task.mark_completed(result)
        return task

    async def fail_task(self, task_id: str, error: str) -> AgentTask:
        """
        Mark a task as failed.

        Args:
            task_id: Task ID
            error: Error description

        Returns:
            Updated AgentTask
        """
        task = await AgentTask.get(task_id)
        if task is None:
            raise ValueError(f"Task {task_id} not found")

        await task.mark_failed(error)
        return task

    async def get_execution_order(self) -> List[List[str]]:
        """
        Compute a topological execution plan grouped into parallel layers.

        Returns a list of layers. Tasks in the same layer can run in parallel.

        Returns:
            List of layers, each layer is a list of task IDs

        Raises:
            DependencyCycleError: If a cycle is detected
        """
        all_tasks = await self.get_all_tasks()
        if not all_tasks:
            return []

        # Build adjacency and in-degree maps
        graph: Dict[str, List[str]] = defaultdict(list)
        in_degree: Dict[str, int] = {}
        task_map: Dict[str, AgentTask] = {}

        for task in all_tasks:
            task_map[task.id] = task
            in_degree.setdefault(task.id, 0)
            for dep_id in task.get_dependency_ids():
                graph[dep_id].append(task.id)
                in_degree[task.id] = in_degree.get(task.id, 0) + 1

        # Kahn's algorithm for topological sort with layers
        layers: List[List[str]] = []
        queue = deque([tid for tid, deg in in_degree.items() if deg == 0])
        visited = 0

        while queue:
            layer = list(queue)
            layers.append(layer)
            next_queue: deque = deque()
            for tid in layer:
                visited += 1
                for downstream in graph[tid]:
                    in_degree[downstream] -= 1
                    if in_degree[downstream] == 0:
                        next_queue.append(downstream)
            queue = next_queue

        if visited != len(task_map):
            raise DependencyCycleError(
                f"Cycle detected: processed {visited}/{len(task_map)} tasks"
            )

        return layers

    async def auto_assign(self, agents: List[AgentInstance]) -> List[Tuple[AgentTask, AgentInstance]]:
        """
        Automatically assign ready tasks to idle agents.

        Matches tasks to agents by priority. Does not consider role
        matching (callers should filter agents by role if needed).

        Args:
            agents: Available agent instances

        Returns:
            List of (task, agent) pairs that were assigned
        """
        idle_agents = [a for a in agents if a.status == "idle"]
        ready_tasks = await self.get_ready_tasks()

        assignments: List[Tuple[AgentTask, AgentInstance]] = []
        for task, agent in zip(ready_tasks, idle_agents):
            await self.assign_task(task.id, agent.id)
            assignments.append((task, agent))

        return assignments

    async def is_complete(self) -> bool:
        """
        Check if all tasks in the team are completed.

        Returns:
            True if no pending/blocked/in_progress tasks remain
        """
        remaining = await self.get_all_tasks()
        return all(t.status in ("completed", "cancelled") for t in remaining)

    async def summary(self) -> Dict[str, Any]:
        """
        Get a summary of task statuses.

        Returns:
            Dict with counts per status
        """
        all_tasks = await self.get_all_tasks()
        counts: Dict[str, int] = defaultdict(int)
        for task in all_tasks:
            counts[task.status] += 1
        return {
            "total": len(all_tasks),
            "by_status": dict(counts),
            "complete": await self.is_complete(),
        }

    async def _check_cycles(self) -> None:
        """
        Verify no cycles exist in the task dependency graph.

        Raises:
            DependencyCycleError: If a cycle is found
        """
        # get_execution_order uses Kahn's algorithm which detects cycles
        await self.get_execution_order()
