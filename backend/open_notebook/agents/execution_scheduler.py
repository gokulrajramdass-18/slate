"""
Execution Scheduler

Smart scheduler that decides parallel vs sequential execution strategy
based on dependencies, resource constraints, and estimated speedup.
"""

import logging
from typing import Any, Dict, List, Tuple, Optional
from collections import defaultdict, deque

from open_notebook.agents.task_manager import TaskManager
from open_notebook.domain.agent_team import AgentTask, AgentInstance

logger = logging.getLogger(__name__)


class ExecutionScheduler:
    """
    Schedules tasks for parallel or sequential execution.

    Uses dependency analysis, resource constraints, and performance
    heuristics to optimize execution strategy.
    """

    def __init__(
        self,
        max_concurrent_tasks: int = 5,
        max_concurrent_resources: int = 10
    ):
        """
        Initialize execution scheduler.

        Args:
            max_concurrent_tasks: Maximum tasks to run in parallel
            max_concurrent_resources: Maximum concurrent resource usage
        """
        self.max_concurrent_tasks = max_concurrent_tasks
        self.max_concurrent_resources = max_concurrent_resources

    async def schedule_tasks(
        self,
        tasks: List[Dict[str, Any]],
        agents: List[Dict[str, Any]],
        resources: Optional[Dict[str, Any]] = None
    ) -> List[List[str]]:
        """
        Schedule tasks into execution layers (parallel groups).

        Args:
            tasks: List of task dicts with id, dependencies, estimated_duration, etc.
            agents: List of available agent dicts
            resources: Resource constraints

        Returns:
            List of layers where each layer is a list of task IDs that can run in parallel
        """
        resources = resources or {}

        logger.info(f"Scheduling {len(tasks)} tasks with {len(agents)} agents")

        # 1. Build dependency graph and run topological sort
        layers = self._topological_sort(tasks)

        logger.info(f"Topological sort produced {len(layers)} layers")

        # 2. Optimize each layer for parallel vs sequential execution
        optimized_layers = []
        for layer_idx, layer in enumerate(layers):
            optimized = self._optimize_layer(layer, tasks, agents, resources)
            optimized_layers.extend(optimized)

        logger.info(
            f"Optimized to {len(optimized_layers)} execution layers "
            f"(split {len(layers)} original layers)"
        )

        return optimized_layers

    def _topological_sort(self, tasks: List[Dict[str, Any]]) -> List[List[str]]:
        """
        Perform topological sort using Kahn's algorithm.

        Returns layers of task IDs where tasks in same layer have no dependencies on each other.
        """
        # Build adjacency list and in-degree map
        graph = defaultdict(list)
        in_degree = {}
        task_map = {t["id"]: t for t in tasks}

        for task in tasks:
            task_id = task["id"]
            in_degree[task_id] = 0

        for task in tasks:
            task_id = task["id"]
            dependencies = task.get("dependencies", [])

            for dep_id in dependencies:
                if dep_id in task_map:
                    graph[dep_id].append(task_id)
                    in_degree[task_id] += 1

        # Kahn's algorithm with layer tracking
        layers = []
        queue = deque([tid for tid, deg in in_degree.items() if deg == 0])

        while queue:
            # All tasks in queue can run in parallel (same layer)
            layer = list(queue)
            layers.append(layer)

            # Process layer and update in-degrees
            next_queue = deque()
            for task_id in layer:
                for downstream_id in graph[task_id]:
                    in_degree[downstream_id] -= 1
                    if in_degree[downstream_id] == 0:
                        next_queue.append(downstream_id)

            queue = next_queue

        return layers

    def _optimize_layer(
        self,
        layer: List[str],
        tasks: List[Dict[str, Any]],
        agents: List[Dict[str, Any]],
        resources: Dict[str, Any]
    ) -> List[List[str]]:
        """
        Optimize a layer for parallel vs sequential execution.

        May split layer into multiple sequential groups if:
        - Resource constraints prevent full parallelization
        - Agent availability is limited
        - Speedup potential is low
        """
        if len(layer) <= 1:
            return [layer]  # Single task, no optimization needed

        task_map = {t["id"]: t for t in tasks}
        layer_tasks = [task_map[tid] for tid in layer]

        # Calculate resource usage if all run in parallel
        total_resource_cost = sum(
            self._estimate_resource_cost(t, resources)
            for t in layer_tasks
        )

        # Check resource constraints
        if total_resource_cost > self.max_concurrent_resources:
            logger.info(
                f"Layer resource cost ({total_resource_cost}) exceeds limit "
                f"({self.max_concurrent_resources}), splitting layer"
            )
            return self._split_layer_by_resources(layer_tasks, resources)

        # Check agent availability
        if len(layer) > len(agents):
            logger.info(
                f"Layer has {len(layer)} tasks but only {len(agents)} agents, "
                f"splitting layer"
            )
            return self._split_layer_by_agents(layer, len(agents))

        # Check concurrent task limit
        if len(layer) > self.max_concurrent_tasks:
            logger.info(
                f"Layer has {len(layer)} tasks exceeding concurrent limit "
                f"({self.max_concurrent_tasks}), splitting layer"
            )
            return self._split_layer_by_limit(layer, self.max_concurrent_tasks)

        # Estimate speedup from parallelization
        speedup = self._estimate_speedup(layer_tasks)

        if speedup < 0.3:  # Less than 30% speedup
            logger.info(
                f"Layer speedup ({speedup:.1%}) is low, considering sequential execution"
            )
            # Execute sequentially if speedup is minimal
            return [[tid] for tid in layer]

        # Run all in parallel
        logger.info(f"Layer will execute in parallel with estimated {speedup:.1%} speedup")
        return [layer]

    def _estimate_resource_cost(
        self,
        task: Dict[str, Any],
        resources: Dict[str, Any]
    ) -> float:
        """
        Estimate resource cost of a task.

        Returns a cost score (higher = more resources needed).
        """
        cost = 1.0  # Base cost

        # Check if task requires specific resources
        required_tools = task.get("required_tools", [])
        required_sources = task.get("required_sources", [])

        # Database/API calls are expensive
        expensive_patterns = ["database", "api", "hana", "query"]
        for tool in required_tools:
            if any(pattern in tool.lower() for pattern in expensive_patterns):
                cost += 2.0

        # Multiple sources increase cost
        cost += len(required_sources) * 0.5

        # Estimated duration affects cost
        duration = task.get("estimated_duration", 30)
        if duration > 60:
            cost += 1.0

        return cost

    def _estimate_speedup(self, tasks: List[Dict[str, Any]]) -> float:
        """
        Estimate speedup from parallel execution.

        Returns speedup ratio (0.0 = no speedup, 1.0 = perfect speedup).
        """
        if not tasks:
            return 0.0

        # Calculate sequential execution time
        sequential_time = sum(t.get("estimated_duration", 30) for t in tasks)

        # Calculate parallel execution time (max duration)
        parallel_time = max(t.get("estimated_duration", 30) for t in tasks)

        # Add coordination overhead (10% of parallel time)
        coordination_overhead = parallel_time * 0.1
        parallel_time += coordination_overhead

        # Calculate speedup ratio
        if sequential_time == 0:
            return 0.0

        speedup = (sequential_time - parallel_time) / sequential_time
        return max(0.0, min(1.0, speedup))  # Clamp to [0, 1]

    def _split_layer_by_resources(
        self,
        tasks: List[Dict[str, Any]],
        resources: Dict[str, Any]
    ) -> List[List[str]]:
        """Split layer into groups based on resource constraints."""
        # Sort tasks by resource cost (descending)
        sorted_tasks = sorted(
            tasks,
            key=lambda t: self._estimate_resource_cost(t, resources),
            reverse=True
        )

        groups = []
        current_group = []
        current_cost = 0.0

        for task in sorted_tasks:
            task_cost = self._estimate_resource_cost(task, resources)

            if current_cost + task_cost <= self.max_concurrent_resources:
                current_group.append(task["id"])
                current_cost += task_cost
            else:
                # Start new group
                if current_group:
                    groups.append(current_group)
                current_group = [task["id"]]
                current_cost = task_cost

        # Add last group
        if current_group:
            groups.append(current_group)

        return groups

    def _split_layer_by_agents(
        self,
        layer: List[str],
        num_agents: int
    ) -> List[List[str]]:
        """Split layer into groups based on agent availability."""
        groups = []
        for i in range(0, len(layer), num_agents):
            group = layer[i:i+num_agents]
            groups.append(group)
        return groups

    def _split_layer_by_limit(
        self,
        layer: List[str],
        limit: int
    ) -> List[List[str]]:
        """Split layer into groups based on concurrent task limit."""
        groups = []
        for i in range(0, len(layer), limit):
            group = layer[i:i+limit]
            groups.append(group)
        return groups

    async def assign_tasks_to_agents(
        self,
        task_ids: List[str],
        agents: List[Dict[str, Any]],
        task_map: Dict[str, Dict[str, Any]]
    ) -> List[Tuple[str, str]]:
        """
        Assign tasks to agents for execution.

        Args:
            task_ids: List of task IDs to assign
            agents: List of available agents
            task_map: Map of task_id to task dict

        Returns:
            List of (task_id, agent_id) tuples
        """
        assignments = []

        # Filter idle agents
        idle_agents = [a for a in agents if a.get("status") == "idle"]

        if not idle_agents:
            logger.warning("No idle agents available for assignment")
            return assignments

        # Simple round-robin assignment
        for idx, task_id in enumerate(task_ids):
            agent = idle_agents[idx % len(idle_agents)]
            assignments.append((task_id, agent["id"]))

        logger.info(f"Assigned {len(assignments)} tasks to {len(idle_agents)} agents")

        return assignments


# Convenience function
async def schedule_execution(
    tasks: List[Dict[str, Any]],
    agents: List[Dict[str, Any]],
    resources: Optional[Dict[str, Any]] = None,
    max_concurrent: int = 5
) -> List[List[str]]:
    """
    Convenience function to schedule task execution.

    Args:
        tasks: List of tasks
        agents: List of agents
        resources: Resource constraints
        max_concurrent: Max concurrent tasks

    Returns:
        Execution layers (parallel groups)
    """
    scheduler = ExecutionScheduler(max_concurrent_tasks=max_concurrent)
    return await scheduler.schedule_tasks(tasks, agents, resources)
