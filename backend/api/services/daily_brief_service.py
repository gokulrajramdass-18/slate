"""
Daily Brief Service

Aggregates data for personalized daily brief shown to users on login.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from open_notebook.database.repository import repo_query
from api.services.settings import get_daily_brief_config


async def get_daily_brief_data(user_id: str, since_datetime: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Get daily brief data for a user since their last login.

    Args:
        user_id: User ID
        since_datetime: Start datetime for data aggregation (defaults to 7 days ago if None)

    Returns:
        Dictionary with daily brief data
    """
    # Get configuration
    config = await get_daily_brief_config()
    enabled_sources = config.get("sources", [])
    max_items = config.get("max_items", 5)

    # Default to 7 days ago if no since_datetime provided
    if since_datetime is None:
        since_datetime = datetime.now() - timedelta(days=7)

    # Calculate time since login
    time_diff = datetime.now() - since_datetime
    if time_diff.days > 0:
        time_since_login = f"{time_diff.days} day{'s' if time_diff.days != 1 else ''} ago"
    elif time_diff.seconds >= 3600:
        hours = time_diff.seconds // 3600
        time_since_login = f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif time_diff.seconds >= 60:
        minutes = time_diff.seconds // 60
        time_since_login = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        time_since_login = "just now"

    # Get user info
    user_result = await repo_query(
        "SELECT username, full_name FROM users WHERE id = :user_id",
        {"user_id": user_id}
    )
    user_name = (
        user_result[0]["full_name"] or user_result[0]["username"]
        if user_result else "User"
    )

    # Initialize result
    result = {
        "user_name": user_name,
        "last_login": since_datetime.isoformat() if since_datetime else None,
        "current_time": datetime.now().isoformat(),
        "time_since_login": time_since_login,
    }

    # Aggregate data based on enabled sources
    if "executions" in enabled_sources:
        result["executions_since_login"] = await _get_executions_since(user_id, since_datetime, max_items)

    if "approvals" in enabled_sources:
        result["pending_approvals"] = await _get_pending_approvals(user_id, max_items)

    if "schedules" in enabled_sources:
        result["upcoming_schedules"] = await _get_upcoming_schedules(user_id, max_items)

    if "notifications" in enabled_sources:
        result["notifications"] = await _get_notifications_since(user_id, since_datetime, max_items)

    if "orchestrations" in enabled_sources:
        result["orchestrations"] = await _get_orchestrations_since(user_id, since_datetime, max_items)

    return result


async def _get_executions_since(user_id: str, since_dt: datetime, max_items: int = 5) -> Dict[str, Any]:
    """Get workflow execution summary since datetime"""
    try:
        since_str = since_dt.isoformat()

        # Get user's workflows
        user_workflows = await repo_query(
            "SELECT id FROM workflows WHERE created_by = :user_id",
            {"user_id": user_id}
        )
        workflow_ids = [w["id"] for w in user_workflows]

        if not workflow_ids:
            return {
                "total": 0,
                "completed": 0,
                "failed": 0,
                "success_rate": 0.0,
                "recent_items": []
            }

        # Build WHERE clause for user's workflows
        workflow_filter = " AND workflow_id IN ({})".format(
            ",".join(f"'{wid}'" for wid in workflow_ids)
        )

        # Total executions since last login
        total = await repo_query(
            f"""
            SELECT COUNT(*) as count FROM workflow_executions
            WHERE started_at >= :since_dt {workflow_filter}
            """,
            {"since_dt": since_str}
        )
        total_count = total[0]["count"] if total else 0

        # Completed and failed counts
        stats = await repo_query(
            f"""
            SELECT
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed
            FROM workflow_executions
            WHERE started_at >= :since_dt {workflow_filter}
            """,
            {"since_dt": since_str}
        )
        completed_count = stats[0]["completed"] if stats else 0
        failed_count = stats[0]["failed"] if stats else 0

        # Success rate
        success_rate = (completed_count / total_count * 100) if total_count > 0 else 0.0

        # Recent executions
        recent = await repo_query(
            f"""
            SELECT
                e.id, e.workflow_id, w.name as workflow_name, e.status,
                e.started_at, e.completed_at, e.triggered_by
            FROM workflow_executions e
            LEFT JOIN workflows w ON e.workflow_id = w.id
            WHERE e.started_at >= :since_dt {workflow_filter}
            ORDER BY e.started_at DESC
            LIMIT :max_items
            """,
            {"since_dt": since_str, "max_items": max_items}
        )
        recent_items = [dict(row) for row in recent]

        return {
            "total": total_count,
            "completed": completed_count,
            "failed": failed_count,
            "success_rate": round(success_rate, 1),
            "recent_items": recent_items
        }
    except Exception as e:
        print(f"Error getting executions: {e}")
        return {
            "total": 0,
            "completed": 0,
            "failed": 0,
            "success_rate": 0.0,
            "recent_items": []
        }


async def _get_pending_approvals(user_id: str, max_items: int = 5) -> List[Dict[str, Any]]:
    """Get pending approvals for user"""
    try:
        # Get approvals where user is required approver or no specific approver is set
        approvals = await repo_query(
            """
            SELECT
                a.id, a.workflow_id, a.approval_prompt, a.created,
                a.timeout_at, w.name as workflow_name
            FROM workflow_approvals a
            LEFT JOIN workflows w ON a.workflow_id = w.id
            WHERE a.status = 'pending'
            AND (a.required_approvers IS NULL OR a.required_approvers LIKE :user_pattern)
            ORDER BY a.created DESC
            LIMIT :max_items
            """,
            {"user_pattern": f"%{user_id}%", "max_items": max_items}
        )

        result = []
        for approval in approvals:
            result.append({
                "id": approval["id"],
                "workflow_name": approval["workflow_name"] or "Unnamed Workflow",
                "approval_prompt": approval["approval_prompt"],
                "created_at": approval["created"],
                "timeout_at": approval["timeout_at"],
                "action_url": f"/workflows/{approval['workflow_id']}/approvals/{approval['id']}"
            })

        return result
    except Exception as e:
        print(f"Error getting pending approvals: {e}")
        return []


async def _get_upcoming_schedules(user_id: str, max_items: int = 5) -> List[Dict[str, Any]]:
    """Get upcoming scheduled workflows for user"""
    try:
        # Get user's workflows that have schedules
        schedules = await repo_query(
            """
            SELECT
                s.id, s.workflow_id, s.schedule_type, s.cron_expression,
                s.next_run_at, w.name as workflow_name
            FROM workflow_schedules s
            LEFT JOIN workflows w ON s.workflow_id = w.id
            WHERE s.enabled = 1
            AND s.next_run_at IS NOT NULL
            AND w.created_by = :user_id
            ORDER BY s.next_run_at ASC
            LIMIT :max_items
            """,
            {"user_id": user_id, "max_items": max_items}
        )

        result = []
        for schedule in schedules:
            result.append({
                "id": schedule["id"],
                "workflow_name": schedule["workflow_name"] or "Unnamed Workflow",
                "next_run_at": schedule["next_run_at"],
                "schedule_type": schedule["schedule_type"],
                "cron_expression": schedule["cron_expression"]
            })

        return result
    except Exception as e:
        print(f"Error getting upcoming schedules: {e}")
        return []


async def _get_notifications_since(user_id: str, since_dt: datetime, max_items: int = 5) -> Dict[str, Any]:
    """Get notifications summary since datetime"""
    try:
        since_str = since_dt.isoformat()

        # Total notifications since last login
        total = await repo_query(
            """
            SELECT COUNT(*) as count FROM notifications
            WHERE user_id = :user_id
            AND created_at >= :since_dt
            AND is_archived = 0
            """,
            {"user_id": user_id, "since_dt": since_str}
        )
        total_count = total[0]["count"] if total else 0

        # Unread count
        unread = await repo_query(
            """
            SELECT COUNT(*) as count FROM notifications
            WHERE user_id = :user_id
            AND is_read = 0
            AND is_archived = 0
            """,
            {"user_id": user_id}
        )
        unread_count = unread[0]["count"] if unread else 0

        # By category
        by_category = await repo_query(
            """
            SELECT category, COUNT(*) as count FROM notifications
            WHERE user_id = :user_id
            AND created_at >= :since_dt
            AND is_archived = 0
            GROUP BY category
            """,
            {"user_id": user_id, "since_dt": since_str}
        )
        category_dict = {row["category"]: row["count"] for row in by_category}

        # Recent notifications
        recent = await repo_query(
            """
            SELECT id, type, title, message, category, priority, created_at, action_url
            FROM notifications
            WHERE user_id = :user_id
            AND created_at >= :since_dt
            AND is_archived = 0
            ORDER BY created_at DESC
            LIMIT :max_items
            """,
            {"user_id": user_id, "since_dt": since_str, "max_items": max_items}
        )
        recent_items = [dict(row) for row in recent]

        return {
            "total": total_count,
            "unread": unread_count,
            "by_category": category_dict,
            "recent_items": recent_items
        }
    except Exception as e:
        print(f"Error getting notifications: {e}")
        return {
            "total": 0,
            "unread": 0,
            "by_category": {},
            "recent_items": []
        }


async def _get_orchestrations_since(user_id: str, since_dt: datetime, max_items: int = 5) -> Dict[str, Any]:
    """Get orchestration runs since datetime"""
    try:
        since_str = since_dt.isoformat()

        # Total orchestrations since last login
        total = await repo_query(
            """
            SELECT COUNT(*) as count FROM orchestrations
            WHERE user_id = :user_id
            AND created_at >= :since_dt
            """,
            {"user_id": user_id, "since_dt": since_str}
        )
        total_count = total[0]["count"] if total else 0

        # Completed and failed counts
        stats = await repo_query(
            """
            SELECT
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed
            FROM orchestrations
            WHERE user_id = :user_id
            AND created_at >= :since_dt
            """,
            {"user_id": user_id, "since_dt": since_str}
        )
        completed_count = stats[0]["completed"] if stats else 0
        failed_count = stats[0]["failed"] if stats else 0

        # Recent orchestrations
        recent = await repo_query(
            """
            SELECT
                id, goal, status, current_phase, progress, created_at, updated_at
            FROM orchestrations
            WHERE user_id = :user_id
            AND created_at >= :since_dt
            ORDER BY created_at DESC
            LIMIT :max_items
            """,
            {"user_id": user_id, "since_dt": since_str, "max_items": max_items}
        )
        recent_items = [dict(row) for row in recent]

        return {
            "total": total_count,
            "completed": completed_count,
            "failed": failed_count,
            "recent_items": recent_items
        }
    except Exception as e:
        print(f"Error getting orchestrations: {e}")
        return {
            "total": 0,
            "completed": 0,
            "failed": 0,
            "recent_items": []
        }
