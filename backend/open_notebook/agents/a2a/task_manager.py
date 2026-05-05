"""
A2A Task Manager

Manages A2A task lifecycle and persistence.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from open_notebook.domain.a2a import A2ATask

logger = logging.getLogger(__name__)


class A2ATaskManager:
    """
    Manage A2A task lifecycle and persistence.

    Handles task creation, updates, cancellation, and retrieval.
    """

    async def create_task(
        self,
        context_id: str,
        direction: str,
        agent_id: Optional[str] = None,
        skill_id: Optional[str] = None,
        kind: str = "task",
        task_id: Optional[str] = None,
    ) -> A2ATask:
        """
        Create and persist A2A task.

        Args:
            context_id: Session/conversation context
            direction: 'outgoing' or 'incoming'
            agent_id: Remote agent ID (for outgoing) or None (for incoming)
            skill_id: Skill being executed
            kind: Task kind (default: 'task')
            task_id: Optional custom task ID (default: generated UUID)

        Returns:
            Created A2ATask
        """
        task = A2ATask(
            id=task_id,  # Only set if provided, otherwise ObjectModel.save() will generate
            context_id=context_id,
            agent_id=agent_id,
            skill_id=skill_id,
            kind=kind,
            direction=direction,
            state="queued",
            progress=0.0,
        )
        await task.save()

        logger.info(
            f"Created A2A task {task.id} ({direction}) "
            f"for context {context_id}"
        )

        return task

    async def get_task(self, task_id: str) -> Optional[A2ATask]:
        """
        Retrieve task by ID.

        Args:
            task_id: Task identifier

        Returns:
            A2ATask or None if not found
        """
        return await A2ATask.get(task_id)

    async def update_task_status(
        self,
        task_id: str,
        state: str,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        artifacts: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Update task status.

        Args:
            task_id: Task identifier
            state: New state
            progress: Progress (0.0-1.0)
            message: Status message
            artifacts: Optional artifacts to attach
        """
        task = await self.get_task(task_id)
        if not task:
            logger.warning(f"Task {task_id} not found for update")
            return

        task.state = state
        if progress is not None:
            task.progress = max(0.0, min(1.0, progress))
        if message:
            task.message = message
        if artifacts:
            task.set_artifacts(artifacts)

        # Update timestamps
        if state == "running" and not task.started_at:
            task.started_at = datetime.utcnow().isoformat()
        if task.is_terminal():
            task.completed_at = datetime.utcnow().isoformat()

        await task.save()

        logger.debug(f"Updated task {task_id} to state {state}")

    async def mark_task_running(self, task_id: str) -> None:
        """Mark task as running."""
        await self.update_task_status(task_id, "running", progress=0.0)

    async def mark_task_completed(
        self,
        task_id: str,
        artifacts: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Mark task as completed."""
        await self.update_task_status(
            task_id,
            "completed",
            progress=1.0,
            artifacts=artifacts,
        )

    async def mark_task_failed(
        self,
        task_id: str,
        error_message: str,
    ) -> None:
        """Mark task as failed."""
        await self.update_task_status(
            task_id,
            "failed",
            message=error_message,
        )

    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel running task.

        Args:
            task_id: Task identifier

        Returns:
            True if canceled, False if not found or already terminal
        """
        task = await self.get_task(task_id)
        if not task:
            return False

        if task.is_terminal():
            logger.warning(f"Cannot cancel task {task_id} in terminal state {task.state}")
            return False

        task.state = "canceled"
        task.completed_at = datetime.utcnow().isoformat()
        await task.save()

        logger.info(f"Canceled task {task_id}")
        return True

    async def append_to_history(
        self,
        task_id: str,
        message: Dict[str, Any],
    ) -> None:
        """
        Append message to task history.

        Args:
            task_id: Task identifier
            message: A2A Message dict
        """
        task = await self.get_task(task_id)
        if not task:
            return

        history = task.get_history()
        history.append(message)
        task.set_history(history)
        await task.save()

    async def get_context_tasks(
        self,
        context_id: str,
        direction: Optional[str] = None,
    ) -> List[A2ATask]:
        """
        Get all tasks for a context.

        Args:
            context_id: Context identifier
            direction: Optional direction filter

        Returns:
            List of A2ATasks
        """
        tasks = await A2ATask.get_by_context(context_id)
        if direction:
            tasks = [t for t in tasks if t.direction == direction]
        return tasks

    async def get_active_tasks(self) -> List[A2ATask]:
        """
        Get all active (non-terminal) tasks.

        Returns:
            List of active A2ATasks
        """
        return await A2ATask.get_active()

    async def cleanup_old_tasks(self, days: int = 30) -> int:
        """
        Delete tasks older than specified days.

        Args:
            days: Age threshold in days

        Returns:
            Number of tasks deleted
        """
        from datetime import timedelta
        from open_notebook.database.repository import repo_execute, repo_query

        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        # Count tasks to delete
        count_sql = """
            SELECT COUNT(*) as count FROM a2a_task_store
            WHERE created < :cutoff AND state IN ('completed', 'canceled', 'failed')
        """
        result = await repo_query(count_sql, {"cutoff": cutoff})
        count = result[0]["count"] if result else 0

        if count == 0:
            logger.info("No old tasks to cleanup")
            return 0

        # Delete old tasks
        delete_sql = """
            DELETE FROM a2a_task_store
            WHERE created < :cutoff AND state IN ('completed', 'canceled', 'failed')
        """
        await repo_execute(delete_sql, {"cutoff": cutoff})

        logger.info(f"Cleaned up {count} old A2A tasks")
        return count
