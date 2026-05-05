"""
Approval Timeout Handler

Background service that checks for timed-out approvals and takes configured actions.
"""

import asyncio
from datetime import datetime
from typing import Optional


class ApprovalTimeoutHandler:
    """
    Monitors approvals for timeouts and executes configured actions.

    Runs every 30 seconds to check for timed-out approvals.
    """

    def __init__(self):
        self._running = False
        self._task = None

    async def start(self):
        """Start the timeout handler."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._check_loop())
        print("[ApprovalTimeoutHandler] Started")

    async def stop(self):
        """Stop the timeout handler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        print("[ApprovalTimeoutHandler] Stopped")

    async def _check_loop(self):
        """Main loop that checks for timeouts."""
        while self._running:
            try:
                await self._check_timeouts()
            except Exception as e:
                print(f"[ApprovalTimeoutHandler] Error: {e}")
                import traceback
                traceback.print_exc()

            await asyncio.sleep(30)  # Check every 30 seconds

    async def _check_timeouts(self):
        """Check for timed-out approvals and execute actions."""
        from open_notebook.database.repository import repo_query

        # Get timed-out approvals
        now = datetime.utcnow().isoformat()
        rows = await repo_query(
            """
            SELECT * FROM workflow_approvals
            WHERE status = 'pending'
            AND timeout_at IS NOT NULL
            AND timeout_at <= :now
            """,
            {"now": now}
        )

        if rows:
            print(f"[ApprovalTimeoutHandler] Found {len(rows)} timed-out approvals")

        for row in rows:
            await self._handle_timeout(row)

    async def _handle_timeout(self, approval_row: dict):
        """Handle a single timed-out approval."""
        from open_notebook.domain.workflow_approval import WorkflowApproval

        approval = WorkflowApproval.from_db(approval_row)
        timeout_action = approval.timeout_action or "fail"

        print(f"[ApprovalTimeoutHandler] Timeout: {approval.id}, action: {timeout_action}")

        if timeout_action == "approve":
            await self._respond_to_approval(
                approval,
                response="approve",
                comment="Auto-approved due to timeout"
            )
        elif timeout_action == "reject":
            await self._respond_to_approval(
                approval,
                response="reject",
                comment="Auto-rejected due to timeout"
            )
        else:  # fail
            # Mark approval as timed_out and fail execution
            approval.status = "timed_out"
            approval.responded_at = datetime.utcnow()
            await approval.save()

            # Fail the execution and update node state
            from open_notebook.domain.workflow import WorkflowExecution, ExecutionStatus
            try:
                execution = await WorkflowExecution.get(approval.execution_id)
                if execution:
                    execution.status = ExecutionStatus.FAILED
                    execution.error = f"Approval {approval.id} timed out"
                    execution.completed_at = datetime.utcnow()

                    # Update node state to show it failed due to timeout
                    node_state = execution.node_states.get(approval.node_id, {})
                    node_state["status"] = "failed"
                    node_state["error"] = f"Approval timed out after {approval.timeout_seconds} seconds"
                    node_state["completed_at"] = datetime.utcnow().isoformat()
                    execution.node_states[approval.node_id] = node_state

                    await execution.save()
            except Exception as e:
                print(f"[ApprovalTimeoutHandler] Failed to fail execution: {e}")

    async def _respond_to_approval(
        self,
        approval: "WorkflowApproval",
        response: str,
        comment: str
    ):
        """
        Respond to an approval and resume workflow.

        This is a simplified version that doesn't resume the workflow.
        The full implementation would use the ApprovalAPI's respond_to_approval.
        """
        approval.status = "approved" if response == "approve" else "rejected"
        approval.response = response
        approval.comment = comment
        approval.approved_by = "system"
        approval.responded_at = datetime.utcnow()
        await approval.save()

        # Resume workflow
        try:
            from api.services.workflow_resume_service import resume_workflow_execution
            await resume_workflow_execution(
                execution_id=approval.execution_id,
                resume_data={
                    "approval_id": approval.id,
                    "approval_response": response,
                    "approval_comment": comment
                }
            )
        except Exception as e:
            print(f"[ApprovalTimeoutHandler] Failed to resume workflow: {e}")


# Singleton instance
_timeout_handler: Optional[ApprovalTimeoutHandler] = None


def get_approval_timeout_handler() -> ApprovalTimeoutHandler:
    """Get the singleton approval timeout handler."""
    global _timeout_handler
    if _timeout_handler is None:
        _timeout_handler = ApprovalTimeoutHandler()
    return _timeout_handler
