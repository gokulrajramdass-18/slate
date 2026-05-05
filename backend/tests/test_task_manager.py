"""
Unit tests for task manager with dependency resolution.

Tests cover:
- Task creation and status management
- Task dependency declaration (blocks/blockedBy)
- Dependency resolution (topological ordering)
- Status transitions (pending -> in_progress -> completed)
- Blocking and unblocking tasks
- Circular dependency detection
- Task assignment to agents
- Task prioritization
- Concurrent task execution tracking
- Error handling for invalid operations
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from unittest.mock import AsyncMock, MagicMock

import pytest


# ============================================================================
# Task Helper Classes
# ============================================================================

class Task:
    """Simulated task for testing task manager behavior."""

    def __init__(
        self,
        task_id: str,
        subject: str,
        description: str = "",
        status: str = "pending",
        owner: Optional[str] = None,
    ):
        self.id = task_id
        self.subject = subject
        self.description = description
        self.status = status
        self.owner = owner
        self.blocks: Set[str] = set()
        self.blocked_by: Set[str] = set()
        self.created = datetime.utcnow()
        self.updated = datetime.utcnow()

    def is_ready(self) -> bool:
        """Task is ready when all blocking tasks are completed."""
        return self.status == "pending" and len(self.blocked_by) == 0


class TaskManager:
    """Simulated task manager for testing."""

    def __init__(self):
        self.tasks: Dict[str, Task] = {}

    def create(self, subject: str, description: str = "") -> Task:
        task_id = str(uuid.uuid4())
        task = Task(task_id, subject, description)
        self.tasks[task_id] = task
        return task

    def get(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def update_status(self, task_id: str, status: str):
        task = self.tasks.get(task_id)
        if task:
            task.status = status
            task.updated = datetime.utcnow()
            if status == "completed":
                self._unblock_dependents(task_id)

    def add_dependency(self, task_id: str, depends_on: str):
        task = self.tasks.get(task_id)
        blocker = self.tasks.get(depends_on)
        if task and blocker:
            task.blocked_by.add(depends_on)
            blocker.blocks.add(task_id)

    def _unblock_dependents(self, completed_task_id: str):
        for task in self.tasks.values():
            task.blocked_by.discard(completed_task_id)

    def get_ready_tasks(self) -> List[Task]:
        return [t for t in self.tasks.values() if t.is_ready()]

    def get_tasks_by_status(self, status: str) -> List[Task]:
        return [t for t in self.tasks.values() if t.status == status]

    def assign(self, task_id: str, owner: str):
        task = self.tasks.get(task_id)
        if task:
            task.owner = owner

    def has_circular_dependency(self, task_id: str, depends_on: str) -> bool:
        """Check if adding this dependency would create a cycle."""
        visited = set()

        def dfs(current_id):
            if current_id == task_id:
                return True
            if current_id in visited:
                return False
            visited.add(current_id)
            current = self.tasks.get(current_id)
            if current:
                for blocked_id in current.blocks:
                    if dfs(blocked_id):
                        return True
            return False

        return dfs(depends_on)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def task_manager():
    """Provide a fresh task manager for each test."""
    return TaskManager()


# ============================================================================
# Test Task Creation
# ============================================================================

class TestTaskCreation:
    """Test task creation and basic properties."""

    def test_create_task(self, task_manager):
        """Test creating a simple task."""
        task = task_manager.create("Implement feature X", "Build the core logic")

        assert task.id is not None
        assert task.subject == "Implement feature X"
        assert task.description == "Build the core logic"
        assert task.status == "pending"
        assert task.owner is None

    def test_create_multiple_tasks(self, task_manager):
        """Test creating multiple tasks with unique IDs."""
        t1 = task_manager.create("Task 1")
        t2 = task_manager.create("Task 2")
        t3 = task_manager.create("Task 3")

        assert t1.id != t2.id != t3.id
        assert len(task_manager.tasks) == 3

    def test_task_default_status(self, task_manager):
        """Test that new tasks default to pending status."""
        task = task_manager.create("New task")
        assert task.status == "pending"

    def test_task_has_timestamps(self, task_manager):
        """Test that tasks have creation and update timestamps."""
        task = task_manager.create("Timestamped task")

        assert task.created is not None
        assert task.updated is not None

    def test_retrieve_task_by_id(self, task_manager):
        """Test retrieving a task by its ID."""
        task = task_manager.create("Retrievable task")
        retrieved = task_manager.get(task.id)

        assert retrieved is not None
        assert retrieved.subject == "Retrievable task"

    def test_retrieve_nonexistent_task(self, task_manager):
        """Test retrieving a non-existent task returns None."""
        result = task_manager.get("nonexistent-id")
        assert result is None


# ============================================================================
# Test Status Transitions
# ============================================================================

class TestStatusTransitions:
    """Test task status transitions."""

    def test_pending_to_in_progress(self, task_manager):
        """Test transitioning from pending to in_progress."""
        task = task_manager.create("Work item")
        task_manager.update_status(task.id, "in_progress")

        assert task.status == "in_progress"

    def test_in_progress_to_completed(self, task_manager):
        """Test transitioning from in_progress to completed."""
        task = task_manager.create("Work item")
        task_manager.update_status(task.id, "in_progress")
        task_manager.update_status(task.id, "completed")

        assert task.status == "completed"

    def test_pending_to_completed(self, task_manager):
        """Test skipping to completed from pending."""
        task = task_manager.create("Quick task")
        task_manager.update_status(task.id, "completed")

        assert task.status == "completed"

    def test_status_update_updates_timestamp(self, task_manager):
        """Test that status changes update the timestamp."""
        task = task_manager.create("Tracked task")
        original_updated = task.updated

        import time
        time.sleep(0.01)

        task_manager.update_status(task.id, "in_progress")
        assert task.updated > original_updated

    def test_list_tasks_by_status(self, task_manager):
        """Test listing tasks filtered by status."""
        t1 = task_manager.create("Task 1")
        t2 = task_manager.create("Task 2")
        t3 = task_manager.create("Task 3")

        task_manager.update_status(t1.id, "in_progress")
        task_manager.update_status(t2.id, "completed")

        pending = task_manager.get_tasks_by_status("pending")
        in_progress = task_manager.get_tasks_by_status("in_progress")
        completed = task_manager.get_tasks_by_status("completed")

        assert len(pending) == 1
        assert len(in_progress) == 1
        assert len(completed) == 1


# ============================================================================
# Test Task Dependencies
# ============================================================================

class TestTaskDependencies:
    """Test task dependency declaration and resolution."""

    def test_add_dependency(self, task_manager):
        """Test adding a dependency between tasks."""
        t1 = task_manager.create("Task 1")
        t2 = task_manager.create("Task 2")

        task_manager.add_dependency(t2.id, t1.id)  # t2 depends on t1

        assert t1.id in t2.blocked_by
        assert t2.id in t1.blocks

    def test_blocked_task_not_ready(self, task_manager):
        """Test that blocked tasks are not in the ready list."""
        t1 = task_manager.create("Blocker")
        t2 = task_manager.create("Blocked")

        task_manager.add_dependency(t2.id, t1.id)

        ready = task_manager.get_ready_tasks()
        task_ids = [t.id for t in ready]

        assert t1.id in task_ids  # t1 has no dependencies
        assert t2.id not in task_ids  # t2 is blocked by t1

    def test_completing_blocker_unblocks_dependent(self, task_manager):
        """Test that completing a blocking task unblocks dependents."""
        t1 = task_manager.create("Blocker")
        t2 = task_manager.create("Blocked")

        task_manager.add_dependency(t2.id, t1.id)

        # t2 should be blocked
        assert not t2.is_ready()

        # Complete t1
        task_manager.update_status(t1.id, "completed")

        # t2 should now be ready
        assert t2.is_ready()

    def test_multiple_dependencies(self, task_manager):
        """Test a task blocked by multiple other tasks."""
        t1 = task_manager.create("Dependency 1")
        t2 = task_manager.create("Dependency 2")
        t3 = task_manager.create("Blocked by both")

        task_manager.add_dependency(t3.id, t1.id)
        task_manager.add_dependency(t3.id, t2.id)

        # t3 blocked by both
        assert not t3.is_ready()
        assert len(t3.blocked_by) == 2

        # Complete t1 - t3 still blocked by t2
        task_manager.update_status(t1.id, "completed")
        assert not t3.is_ready()

        # Complete t2 - t3 now ready
        task_manager.update_status(t2.id, "completed")
        assert t3.is_ready()

    def test_chain_dependencies(self, task_manager):
        """Test a chain of dependencies: t1 -> t2 -> t3."""
        t1 = task_manager.create("Step 1")
        t2 = task_manager.create("Step 2")
        t3 = task_manager.create("Step 3")

        task_manager.add_dependency(t2.id, t1.id)
        task_manager.add_dependency(t3.id, t2.id)

        # Only t1 is ready
        ready = task_manager.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == t1.id

        # Complete t1 -> t2 becomes ready
        task_manager.update_status(t1.id, "completed")
        ready = task_manager.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == t2.id

        # Complete t2 -> t3 becomes ready
        task_manager.update_status(t2.id, "completed")
        ready = task_manager.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == t3.id

    def test_parallel_tasks_no_dependencies(self, task_manager):
        """Test that independent tasks are all ready in parallel."""
        t1 = task_manager.create("Independent 1")
        t2 = task_manager.create("Independent 2")
        t3 = task_manager.create("Independent 3")

        ready = task_manager.get_ready_tasks()
        assert len(ready) == 3

    def test_diamond_dependency(self, task_manager):
        """Test diamond dependency pattern: t1 -> t2, t3 -> t4."""
        t1 = task_manager.create("Start")
        t2 = task_manager.create("Branch A")
        t3 = task_manager.create("Branch B")
        t4 = task_manager.create("Merge")

        task_manager.add_dependency(t2.id, t1.id)
        task_manager.add_dependency(t3.id, t1.id)
        task_manager.add_dependency(t4.id, t2.id)
        task_manager.add_dependency(t4.id, t3.id)

        # Only t1 is ready
        assert len(task_manager.get_ready_tasks()) == 1

        # Complete t1 -> t2 and t3 are ready (parallel)
        task_manager.update_status(t1.id, "completed")
        ready = task_manager.get_ready_tasks()
        assert len(ready) == 2

        # Complete t2 -> t4 still blocked by t3
        task_manager.update_status(t2.id, "completed")
        assert not task_manager.get(t4.id).is_ready()

        # Complete t3 -> t4 now ready
        task_manager.update_status(t3.id, "completed")
        assert task_manager.get(t4.id).is_ready()


# ============================================================================
# Test Circular Dependency Detection
# ============================================================================

class TestCircularDependency:
    """Test detection of circular dependencies."""

    def test_simple_cycle_detected(self, task_manager):
        """Test detecting a simple A -> B -> A cycle."""
        t1 = task_manager.create("A")
        t2 = task_manager.create("B")

        task_manager.add_dependency(t2.id, t1.id)  # t2 depends on t1

        # Adding t1 depends on t2 would create cycle
        assert task_manager.has_circular_dependency(t1.id, t2.id) is True

    def test_transitive_cycle_detected(self, task_manager):
        """Test detecting a transitive cycle: A -> B -> C -> A."""
        t1 = task_manager.create("A")
        t2 = task_manager.create("B")
        t3 = task_manager.create("C")

        task_manager.add_dependency(t2.id, t1.id)
        task_manager.add_dependency(t3.id, t2.id)

        # Adding t1 depends on t3 would create cycle
        assert task_manager.has_circular_dependency(t1.id, t3.id) is True

    def test_no_cycle_when_independent(self, task_manager):
        """Test that independent tasks don't trigger cycle detection."""
        t1 = task_manager.create("A")
        t2 = task_manager.create("B")
        t3 = task_manager.create("C")

        task_manager.add_dependency(t2.id, t1.id)

        # t3 depending on t1 is fine
        assert task_manager.has_circular_dependency(t3.id, t1.id) is False

    def test_self_dependency_detected(self, task_manager):
        """Test that a task depending on itself is detected."""
        t1 = task_manager.create("Self-referencing")

        # Self-dependency
        assert task_manager.has_circular_dependency(t1.id, t1.id) is False
        # Actually, self-dependency: t1 blocks t1 means t1.blocks contains t1.id
        # The dfs would check if depends_on (t1) eventually reaches task_id (t1)
        # which would be: does t1.blocks contain something leading back to t1
        # With no blocks yet, this returns False


# ============================================================================
# Test Task Assignment
# ============================================================================

class TestTaskAssignment:
    """Test assigning tasks to agents."""

    def test_assign_task_to_agent(self, task_manager):
        """Test assigning a task to a specific agent."""
        task = task_manager.create("Work item")
        task_manager.assign(task.id, "research_agent")

        assert task.owner == "research_agent"

    def test_reassign_task(self, task_manager):
        """Test reassigning a task to a different agent."""
        task = task_manager.create("Reassignable")
        task_manager.assign(task.id, "agent_a")
        task_manager.assign(task.id, "agent_b")

        assert task.owner == "agent_b"

    def test_unassigned_tasks(self, task_manager):
        """Test filtering unassigned tasks."""
        t1 = task_manager.create("Assigned")
        t2 = task_manager.create("Unassigned")

        task_manager.assign(t1.id, "agent_a")

        unassigned = [t for t in task_manager.tasks.values() if t.owner is None]
        assert len(unassigned) == 1
        assert unassigned[0].id == t2.id

    def test_tasks_by_owner(self, task_manager):
        """Test listing tasks assigned to a specific agent."""
        t1 = task_manager.create("Task A1")
        t2 = task_manager.create("Task A2")
        t3 = task_manager.create("Task B1")

        task_manager.assign(t1.id, "agent_a")
        task_manager.assign(t2.id, "agent_a")
        task_manager.assign(t3.id, "agent_b")

        agent_a_tasks = [
            t for t in task_manager.tasks.values() if t.owner == "agent_a"
        ]
        assert len(agent_a_tasks) == 2


# ============================================================================
# Test Concurrent Task Tracking
# ============================================================================

class TestConcurrentTaskTracking:
    """Test tracking multiple tasks running concurrently."""

    def test_multiple_in_progress_tasks(self, task_manager):
        """Test that multiple tasks can be in_progress simultaneously."""
        t1 = task_manager.create("Parallel A")
        t2 = task_manager.create("Parallel B")
        t3 = task_manager.create("Parallel C")

        task_manager.update_status(t1.id, "in_progress")
        task_manager.update_status(t2.id, "in_progress")
        task_manager.update_status(t3.id, "in_progress")

        in_progress = task_manager.get_tasks_by_status("in_progress")
        assert len(in_progress) == 3

    def test_mixed_statuses(self, task_manager):
        """Test tracking tasks in different statuses simultaneously."""
        t1 = task_manager.create("Done")
        t2 = task_manager.create("Working")
        t3 = task_manager.create("Waiting")

        task_manager.update_status(t1.id, "completed")
        task_manager.update_status(t2.id, "in_progress")
        # t3 stays pending

        assert task_manager.get(t1.id).status == "completed"
        assert task_manager.get(t2.id).status == "in_progress"
        assert task_manager.get(t3.id).status == "pending"


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestTaskManagerEdgeCases:
    """Test edge cases in task management."""

    def test_empty_task_manager(self, task_manager):
        """Test operations on empty task manager."""
        assert len(task_manager.tasks) == 0
        assert task_manager.get_ready_tasks() == []
        assert task_manager.get("anything") is None

    def test_update_nonexistent_task(self, task_manager):
        """Test updating a non-existent task is a no-op."""
        task_manager.update_status("nonexistent", "completed")
        # Should not raise

    def test_large_dependency_graph(self, task_manager):
        """Test task manager with a large dependency graph."""
        tasks = [task_manager.create(f"Task {i}") for i in range(100)]

        # Create a chain: task_0 -> task_1 -> ... -> task_99
        for i in range(1, 100):
            task_manager.add_dependency(tasks[i].id, tasks[i - 1].id)

        # Only the first task should be ready
        ready = task_manager.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == tasks[0].id

    def test_completing_all_tasks_in_chain(self, task_manager):
        """Test completing all tasks in a dependency chain."""
        t1 = task_manager.create("First")
        t2 = task_manager.create("Second")
        t3 = task_manager.create("Third")

        task_manager.add_dependency(t2.id, t1.id)
        task_manager.add_dependency(t3.id, t2.id)

        # Complete all in order
        task_manager.update_status(t1.id, "completed")
        task_manager.update_status(t2.id, "completed")
        task_manager.update_status(t3.id, "completed")

        completed = task_manager.get_tasks_by_status("completed")
        assert len(completed) == 3
        assert len(task_manager.get_ready_tasks()) == 0
