"""
Workflow Snapshots API Endpoints

Provides REST API for managing workflow snapshots:
- List user's snapshots
- View snapshot details
- Compare snapshots
- Delete snapshots
"""

from datetime import date, datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from open_notebook.domain.workflow_snapshot import WorkflowSnapshot, SnapshotContext
from open_notebook.agents.snapshot_comparator import SnapshotComparator
from api.dependencies.auth import get_current_user
from open_notebook.domain.user import User

router = APIRouter(prefix="/api/snapshots", tags=["snapshots"])


# ============================================================================
# Request/Response Models
# ============================================================================

class SnapshotSummary(BaseModel):
    """Snapshot summary for list view"""
    id: str
    workflow_id: str
    node_id: str
    snapshot_date: datetime  # Changed from date to datetime
    snapshot_label: Optional[str]
    storage_type: str
    row_count: int
    total_size_bytes: int
    context_hash: str
    created_at: str


class SnapshotDetail(BaseModel):
    """Detailed snapshot information"""
    id: str
    workflow_id: str
    node_id: str
    user_id: str
    snapshot_date: datetime  # Changed from date to datetime
    snapshot_label: Optional[str]
    storage_type: str
    row_count: int
    total_size_bytes: int
    column_count: int
    context_hash: str
    stats_summary: Optional[str]
    sample_data: Optional[str]
    created_at: str
    expires_at: Optional[str]


class CompareRequest(BaseModel):
    """Request to compare two snapshots"""
    snapshot1_id: str
    snapshot2_id: str
    strategy: str = Field(default="fast", description="fast, medium, or full")


class CompareResponse(BaseModel):
    """Comparison result"""
    status: str
    strategy: str
    has_changes: bool
    change_percentage: float
    comparison_time_ms: float
    snapshot1_date: str
    snapshot2_date: str
    delta: Optional[dict] = None
    stats_changes: Optional[dict] = None


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/", response_model=List[SnapshotSummary])
async def list_snapshots(
    workflow_id: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
):
    """
    List snapshots.

    Args:
        workflow_id: Optional workflow filter (required for listing)
        limit: Max results (default 50, max 100)

    Returns:
        List of snapshot summaries
    """
    # Require workflow_id for listing snapshots
    if not workflow_id:
        raise HTTPException(
            status_code=400,
            detail="workflow_id is required"
        )

    snapshots = await WorkflowSnapshot.list_for_workflow(
        workflow_id=workflow_id,
        limit=limit
    )

    return [
        SnapshotSummary(
            id=s.id,
            workflow_id=s.workflow_id,
            node_id=s.node_id,
            snapshot_date=s.snapshot_date,
            snapshot_label=s.snapshot_label,
            storage_type=s.storage_type.value,
            row_count=s.row_count,
            total_size_bytes=s.total_size_bytes,
            context_hash=s.context_hash,
            created_at=s.created.isoformat() if s.created else ""
        )
        for s in snapshots
    ]


@router.get("/{snapshot_id}", response_model=SnapshotDetail)
async def get_snapshot(
    snapshot_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get snapshot details.

    Args:
        snapshot_id: Snapshot ID
        current_user: Authenticated user

    Returns:
        Snapshot details

    Raises:
        HTTPException: 404 if not found or 403 if unauthorized
    """
    snapshot = await WorkflowSnapshot.get(snapshot_id)

    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    # Check ownership
    if snapshot.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return SnapshotDetail(
        id=snapshot.id,
        workflow_id=snapshot.workflow_id,
        node_id=snapshot.node_id,
        user_id=snapshot.user_id,
        snapshot_date=snapshot.snapshot_date,
        snapshot_label=snapshot.snapshot_label,
        storage_type=snapshot.storage_type.value,
        row_count=snapshot.row_count,
        total_size_bytes=snapshot.total_size_bytes,
        column_count=snapshot.column_count,
        context_hash=snapshot.context_hash,
        stats_summary=snapshot.stats_summary,
        sample_data=snapshot.sample_data,
        created_at=snapshot.created.isoformat() if snapshot.created else "",
        expires_at=snapshot.expires_at.isoformat() if snapshot.expires_at else None
    )


@router.post("/compare", response_model=CompareResponse)
async def compare_snapshots(
    request: CompareRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Compare two snapshots.

    Args:
        request: Compare request with snapshot IDs
        current_user: Authenticated user

    Returns:
        Comparison result

    Raises:
        HTTPException: 404 if snapshots not found, 403 if unauthorized, 400 if incompatible
    """
    # Load snapshots
    snapshot1 = await WorkflowSnapshot.get(request.snapshot1_id)
    snapshot2 = await WorkflowSnapshot.get(request.snapshot2_id)

    if not snapshot1 or not snapshot2:
        raise HTTPException(status_code=404, detail="One or both snapshots not found")

    # Check ownership
    user_id = current_user.id
    if snapshot1.user_id != user_id or snapshot2.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Compare
    try:
        import os
        comparator = SnapshotComparator({
            "snapshot_storage_path": os.getenv("SNAPSHOT_STORAGE_PATH", "./data/snapshots")
        })

        result = await comparator.compare_snapshots(
            snapshot1.model_dump(),
            snapshot2.model_dump(),
            strategy=request.strategy
        )

        return CompareResponse(**result)

    except ValueError as e:
        # Context mismatch
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{snapshot_id}")
async def delete_snapshot(
    snapshot_id: str,
):
    """
    Delete a snapshot.

    Args:
        snapshot_id: Snapshot ID

    Returns:
        Success message

    Raises:
        HTTPException: 404 if not found
    """
    snapshot = await WorkflowSnapshot.get(snapshot_id)

    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    # Delete snapshot
    from open_notebook.database.repository import repo_delete
    await repo_delete("workflow_snapshots", snapshot_id)

    # TODO: Also delete file storage if not inline

    return {"message": "Snapshot deleted successfully"}


@router.get("/stats/storage")
async def get_storage_stats(current_user: User = Depends(get_current_user)):
    """
    Get storage statistics for current user.

    Args:
        current_user: Authenticated user

    Returns:
        Storage statistics
    """
    from open_notebook.database.repository import repo_query

    user_id = current_user.id

    # Get user's storage stats
    stats = await repo_query(
        """SELECT
            storage_type,
            COUNT(*) as count,
            SUM(total_size_bytes) as total_bytes,
            AVG(total_size_bytes) as avg_bytes
        FROM workflow_snapshots
        WHERE user_id = :user_id
        GROUP BY storage_type""",
        {"user_id": user_id}
    )

    return {
        "by_storage_type": [
            {
                "storage_type": row["storage_type"],
                "count": row["count"],
                "total_mb": round(row["total_bytes"] / 1024 / 1024, 2),
                "avg_mb": round(row["avg_bytes"] / 1024 / 1024, 2)
            }
            for row in stats
        ]
    }
