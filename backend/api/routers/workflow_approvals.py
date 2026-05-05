"""
Workflow Approvals API Router

Endpoints for human-in-the-loop approval management and inbox.
"""

import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Header, status
from pydantic import BaseModel, Field

from open_notebook.domain.workflow_approval import WorkflowApproval
from api.services.workflow_resume_service import resume_workflow_execution

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflow-approvals", tags=["Workflow Approvals"])


# ============================================================================
# Request/Response Models
# ============================================================================

class ApprovalRespondRequest(BaseModel):
    """Request to respond to an approval."""
    response: str = Field(..., description="User's choice (e.g., 'approve', 'reject')")
    comment: Optional[str] = Field(None, description="Optional comment")


class ApprovalResponse(BaseModel):
    """Approval response."""
    id: str
    workflow_id: Optional[str]
    execution_id: Optional[str]
    node_id: str
    approval_prompt: str
    approval_options: List[str]
    required_approvers: List[str]
    input_data: dict
    status: str
    response: Optional[str]
    comment: Optional[str]
    approved_by: Optional[str]
    timeout_seconds: Optional[int]
    timeout_action: Optional[str]
    timeout_at: Optional[str]
    created_at: str
    responded_at: Optional[str]


# ============================================================================
# Helper Functions
# ============================================================================

def approval_to_response(approval: WorkflowApproval) -> ApprovalResponse:
    """Convert approval to response model."""
    return ApprovalResponse(
        id=approval.id,
        workflow_id=approval.workflow_id,
        execution_id=approval.execution_id,
        node_id=approval.node_id,
        approval_prompt=approval.approval_prompt,
        approval_options=approval.get_approval_options(),
        required_approvers=approval.get_required_approvers(),
        input_data=approval.get_input_data(),
        status=approval.status,
        response=approval.response,
        comment=approval.comment,
        approved_by=approval.approved_by,
        timeout_seconds=approval.timeout_seconds,
        timeout_action=approval.timeout_action,
        timeout_at=approval.timeout_at.isoformat() if approval.timeout_at else None,
        created_at=approval.created.isoformat() if approval.created else datetime.utcnow().isoformat(),
        responded_at=approval.responded_at.isoformat() if approval.responded_at else None,
    )


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/inbox", response_model=List[ApprovalResponse])
async def get_approval_inbox(
    x_user_id: str = Header(..., alias="X-User-ID"),
    status_filter: Optional[str] = Query(None, description="Filter by status (pending, approved, rejected, timed_out)"),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get user's approval inbox.

    Returns approvals that require the user's attention, plus history.
    """
    try:
        if status_filter == "pending":
            approvals = await WorkflowApproval.get_pending_for_user(x_user_id, limit=limit)
        else:
            # Get all approvals for user (pending + history)
            from open_notebook.database.repository import repo_query

            query = """
                SELECT * FROM workflow_approvals
                WHERE (required_approvers IS NULL OR required_approvers LIKE :user_pattern)
            """

            params = {"user_pattern": f"%{x_user_id}%", "limit": limit}

            if status_filter:
                query += " AND status = :status"
                params["status"] = status_filter

            query += " ORDER BY created DESC LIMIT :limit"

            rows = await repo_query(query, params)
            approvals = [WorkflowApproval.from_db(row) for row in rows]

        return [approval_to_response(a) for a in approvals]

    except Exception as e:
        logger.error(f"Failed to get approval inbox: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: str,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """
    Get approval details.

    Returns full approval information including context data.
    """
    try:
        approval = await WorkflowApproval.get(approval_id)

        if not approval:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approval {approval_id} not found"
            )

        # Check access
        required_approvers = approval.get_required_approvers()
        if required_approvers and x_user_id not in required_approvers:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to view this approval"
            )

        return approval_to_response(approval)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get approval: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{approval_id}/respond", response_model=ApprovalResponse)
async def respond_to_approval(
    approval_id: str,
    request: ApprovalRespondRequest,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """
    Respond to an approval.

    Approves or rejects the approval and resumes the workflow execution.
    """
    try:
        approval = await WorkflowApproval.get(approval_id)

        if not approval:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approval {approval_id} not found"
            )

        # Check if already responded
        if approval.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Approval already {approval.status}"
            )

        # Check access
        required_approvers = approval.get_required_approvers()
        if required_approvers and x_user_id not in required_approvers:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to respond to this approval"
            )

        # Validate response is one of the allowed options
        options = approval.get_approval_options()
        if request.response not in options:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid response. Must be one of: {options}"
            )

        # Update approval
        approval.status = "approved" if request.response == "approve" else "rejected"
        approval.response = request.response
        approval.comment = request.comment
        approval.approved_by = x_user_id
        approval.responded_at = datetime.utcnow()
        await approval.save()

        # Resume workflow with approval data
        try:
            await resume_workflow_execution(
                execution_id=approval.execution_id,
                resume_data={
                    "approval_id": approval_id,
                    "approval_response": request.response,
                    "approval_comment": request.comment,
                    "approved_by": x_user_id
                }
            )
        except Exception as e:
            logger.error(f"Failed to resume workflow after approval: {e}")
            # Don't fail the approval response, just log it
            # The approval is saved, workflow can be resumed manually if needed

        return approval_to_response(approval)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to respond to approval: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/executions/{execution_id}", response_model=List[ApprovalResponse])
async def list_execution_approvals(
    execution_id: str,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """
    List all approvals for a workflow execution.

    Returns approval history for the execution.
    """
    try:
        approvals = await WorkflowApproval.get_by_execution(execution_id)
        return [approval_to_response(a) for a in approvals]

    except Exception as e:
        logger.error(f"Failed to list execution approvals: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/workflows/{workflow_id}", response_model=List[ApprovalResponse])
async def list_workflow_approvals(
    workflow_id: str,
    x_user_id: str = Header(..., alias="X-User-ID"),
    limit: int = Query(50, ge=1, le=100)
):
    """
    List all approvals for a workflow.

    Returns approval history across all executions of the workflow.
    """
    try:
        from open_notebook.database.repository import repo_query

        rows = await repo_query(
            """
            SELECT * FROM workflow_approvals
            WHERE workflow_id = :workflow_id
            ORDER BY created DESC
            LIMIT :limit
            """,
            {"workflow_id": workflow_id, "limit": limit}
        )

        approvals = [WorkflowApproval.from_db(row) for row in rows]
        return [approval_to_response(a) for a in approvals]

    except Exception as e:
        logger.error(f"Failed to list workflow approvals: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/cleanup-orphaned", response_model=dict)
async def cleanup_orphaned_approvals(
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """
    Manually trigger cleanup of orphaned approvals.

    Removes:
    - Approvals for deleted workflows
    - Approvals for deleted executions
    - Pending approvals for completed/failed executions

    Requires user authentication.
    """
    try:
        from open_notebook.database.repository import repo_query, repo_delete

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
        total_deleted += len(stale_approvals)

        logger.info(f"Manual cleanup: removed {total_deleted} orphaned approvals (user: {x_user_id})")

        return {
            "success": True,
            "deleted_count": total_deleted,
            "breakdown": {
                "missing_workflows": len(orphaned_workflow),
                "missing_executions": len(orphaned_execution),
                "stale_pending": len(stale_approvals)
            }
        }

    except Exception as e:
        logger.error(f"Failed to cleanup orphaned approvals: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
