"""
Workflow Approval System

Manages human-in-the-loop approvals that pause workflow execution
until a user responds.
"""

import json
from datetime import datetime
from typing import List, Optional, Dict, Any, ClassVar
from pydantic import BaseModel

from .base import ObjectModel


class WorkflowApproval(ObjectModel):
    """
    Approval request that pauses workflow execution.

    When a workflow reaches a HumanApproval node, an approval is created
    and the workflow pauses until a user responds.
    """
    _table_name: ClassVar[str] = "workflow_approvals"

    workflow_id: Optional[str] = None
    execution_id: Optional[str] = None
    node_id: str
    approval_prompt: str
    approval_options: str  # JSON array
    required_approvers: Optional[str] = None  # JSON array of user IDs
    input_data: Optional[str] = None  # JSON context for decision
    status: str = "pending"  # pending, approved, rejected, timed_out
    response: Optional[str] = None  # User's choice
    comment: Optional[str] = None  # User's comment
    approved_by: Optional[str] = None
    timeout_seconds: Optional[int] = None
    timeout_action: Optional[str] = None  # approve, reject, fail
    timeout_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None

    def get_approval_options(self) -> List[str]:
        """Parse approval options from JSON."""
        return json.loads(self.approval_options)

    def get_required_approvers(self) -> List[str]:
        """Parse required approvers from JSON."""
        if not self.required_approvers:
            return []
        return json.loads(self.required_approvers)

    def get_input_data(self) -> Dict[str, Any]:
        """Parse input data from JSON."""
        if not self.input_data:
            return {}
        return json.loads(self.input_data)

    def is_timed_out(self) -> bool:
        """Check if approval has timed out."""
        if not self.timeout_at:
            return False
        return datetime.utcnow() > self.timeout_at

    @classmethod
    async def get_pending_for_user(cls, user_id: str, limit: int = 50):
        """Get pending approvals for a user."""
        from ..database.repository import repo_query

        # Get approvals where user is in required_approvers or no specific approvers
        rows = await repo_query(
            """
            SELECT * FROM workflow_approvals
            WHERE status = 'pending'
            AND (required_approvers IS NULL OR required_approvers LIKE :user_pattern)
            ORDER BY created DESC
            LIMIT :limit
            """,
            {"user_pattern": f"%{user_id}%", "limit": limit}
        )
        return [cls.from_db(row) for row in rows]

    @classmethod
    async def get_by_execution(cls, execution_id: str):
        """Get all approvals for a workflow execution."""
        from ..database.repository import repo_query

        rows = await repo_query(
            "SELECT * FROM workflow_approvals WHERE execution_id = :execution_id ORDER BY created ASC",
            {"execution_id": execution_id}
        )
        return [cls.from_db(row) for row in rows]

    @classmethod
    async def get(cls, approval_id: str):
        """Get approval by ID."""
        from ..database.repository import repo_query

        rows = await repo_query(
            "SELECT * FROM workflow_approvals WHERE id = :id",
            {"id": approval_id}
        )

        if not rows:
            return None

        return cls.from_db(rows[0])

    @classmethod
    def from_db(cls, row: dict):
        """Create instance from database row."""
        # Parse timestamps
        timeout_at = row.get("timeout_at")
        if timeout_at and isinstance(timeout_at, str):
            timeout_at = datetime.fromisoformat(timeout_at)

        responded_at = row.get("responded_at")
        if responded_at and isinstance(responded_at, str):
            responded_at = datetime.fromisoformat(responded_at)

        created = row.get("created")
        if created and isinstance(created, str):
            created = datetime.fromisoformat(created)

        updated = row.get("updated")
        if updated and isinstance(updated, str):
            updated = datetime.fromisoformat(updated)

        return cls(
            id=row["id"],
            workflow_id=row["workflow_id"],
            execution_id=row["execution_id"],
            node_id=row["node_id"],
            approval_prompt=row["approval_prompt"],
            approval_options=row["approval_options"],
            required_approvers=row.get("required_approvers"),
            input_data=row.get("input_data"),
            status=row.get("status", "pending"),
            response=row.get("response"),
            comment=row.get("comment"),
            approved_by=row.get("approved_by"),
            timeout_seconds=row.get("timeout_seconds"),
            timeout_action=row.get("timeout_action"),
            timeout_at=timeout_at,
            responded_at=responded_at,
            created=created,
            updated=updated,
        )

    async def save(self):
        """Save approval to database."""
        import uuid
        from ..database.repository import db_connection

        # Generate ID if this is a new approval
        if self.id is None:
            self.id = str(uuid.uuid4())

        async with db_connection() as db:
            data = {
                "id": self.id,
                "workflow_id": self.workflow_id,
                "execution_id": self.execution_id,
                "node_id": self.node_id,
                "approval_prompt": self.approval_prompt,
                "approval_options": self.approval_options,
                "required_approvers": self.required_approvers,
                "input_data": self.input_data,
                "status": self.status,
                "response": self.response,
                "comment": self.comment,
                "approved_by": self.approved_by,
                "timeout_seconds": self.timeout_seconds,
                "timeout_action": self.timeout_action,
                "timeout_at": self.timeout_at.isoformat() if self.timeout_at else None,
                "responded_at": self.responded_at.isoformat() if self.responded_at else None,
            }

            # Check if exists
            existing = await db.query("SELECT id FROM workflow_approvals WHERE id = :id", {"id": self.id})

            if existing:
                await db.update("workflow_approvals", self.id, data)
            else:
                await db.create("workflow_approvals", data)
