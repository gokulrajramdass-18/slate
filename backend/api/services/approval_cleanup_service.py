"""
Approval Cleanup Service

Background service to periodically clean up orphaned approvals.
"""

import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ApprovalCleanupService:
    """
    Service to clean up orphaned workflow approvals.

    Runs periodically to remove:
    1. Approvals for deleted workflows
    2. Approvals for deleted executions
    3. Pending approvals for completed/failed executions
    """

    def __init__(self, interval_seconds: int = 3600):  # Default: 1 hour
        """
        Initialize cleanup service.

        Args:
            interval_seconds: How often to run cleanup (default: 3600 = 1 hour)
        """
        self.interval_seconds = interval_seconds
        self._running = False
        self._task = None

    async def start(self):
        """Start the cleanup service."""
        if self._running:
            logger.warning("Approval cleanup service already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._cleanup_loop())
        logger.info(f"Approval cleanup service started (interval: {self.interval_seconds}s)")

    async def stop(self):
        """Stop the cleanup service."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Approval cleanup service stopped")

    async def _cleanup_loop(self):
        """Main cleanup loop."""
        while self._running:
            try:
                await self._run_cleanup()
            except Exception as e:
                logger.error(f"Error during approval cleanup: {e}", exc_info=True)

            # Wait for next interval
            await asyncio.sleep(self.interval_seconds)

    async def _run_cleanup(self):
        """Run the cleanup process."""
        from open_notebook.database.repository import repo_query, repo_delete

        logger.info("Starting approval cleanup")

        total_deleted = 0

        # 1. Approvals with non-existent workflows
        orphaned_workflow = await repo_query("""
            SELECT wa.id
            FROM workflow_approvals wa
            LEFT JOIN workflows w ON wa.workflow_id = w.id
            WHERE w.id IS NULL
        """, {})

        for row in orphaned_workflow:
            await repo_delete("workflow_approvals", row["id"])

        if orphaned_workflow:
            logger.info(f"Deleted {len(orphaned_workflow)} approvals with missing workflows")
            total_deleted += len(orphaned_workflow)

        # 2. Approvals with non-existent executions
        orphaned_execution = await repo_query("""
            SELECT wa.id
            FROM workflow_approvals wa
            LEFT JOIN workflow_executions we ON wa.execution_id = we.id
            WHERE wa.execution_id IS NOT NULL AND we.id IS NULL
        """, {})

        for row in orphaned_execution:
            await repo_delete("workflow_approvals", row["id"])

        if orphaned_execution:
            logger.info(f"Deleted {len(orphaned_execution)} approvals with missing executions")
            total_deleted += len(orphaned_execution)

        # 3. Pending approvals for completed/failed executions
        stale_approvals = await repo_query("""
            SELECT wa.id
            FROM workflow_approvals wa
            JOIN workflow_executions we ON wa.execution_id = we.id
            WHERE wa.status = 'pending'
            AND we.status IN ('completed', 'failed', 'cancelled')
        """, {})

        for row in stale_approvals:
            await repo_delete("workflow_approvals", row["id"])

        if stale_approvals:
            logger.info(f"Deleted {len(stale_approvals)} pending approvals for finished executions")
            total_deleted += len(stale_approvals)

        if total_deleted > 0:
            logger.info(f"Approval cleanup complete: removed {total_deleted} orphaned approvals")
        else:
            logger.debug("Approval cleanup complete: no orphaned approvals found")


# Singleton instance
_cleanup_service = None


def get_approval_cleanup_service(interval_seconds: int = 3600):
    """Get the singleton approval cleanup service."""
    global _cleanup_service
    if _cleanup_service is None:
        _cleanup_service = ApprovalCleanupService(interval_seconds)
    return _cleanup_service
