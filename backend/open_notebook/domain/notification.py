"""
Notification Domain Model

Handles user notifications for approvals, executions, agent activity, etc.
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum

from open_notebook.database.repository import repo_execute, repo_query


class NotificationType(str, Enum):
    """Notification type enumeration"""
    APPROVAL_PENDING = "approval_pending"
    EXECUTION_COMPLETE = "execution_complete"
    EXECUTION_FAILED = "execution_failed"
    AGENT_COMPLETE = "agent_complete"
    AGENT_FAILED = "agent_failed"
    SCHEDULE_TRIGGERED = "schedule_triggered"
    WORKFLOW_PAUSED = "workflow_paused"
    TEMPLATE_EXECUTED = "template_executed"
    SYSTEM = "system"


class NotificationCategory(str, Enum):
    """Notification category for grouping"""
    WORKFLOW = "workflow"
    AGENT = "agent"
    APPROVAL = "approval"
    SCHEDULE = "schedule"
    SYSTEM = "system"


class NotificationPriority(str, Enum):
    """Notification priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Notification:
    """Notification domain model"""
    id: str
    user_id: str
    type: str
    title: str
    message: str
    category: Optional[str] = None
    priority: str = "normal"
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    action_url: Optional[str] = None
    action_label: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    is_read: bool = False
    is_archived: bool = False
    read_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    @staticmethod
    async def create(
        user_id: str,
        type: NotificationType,
        title: str,
        message: str,
        category: Optional[NotificationCategory] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        action_url: Optional[str] = None,
        action_label: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        expires_in_hours: Optional[int] = None,
    ) -> "Notification":
        """
        Create a new notification

        Args:
            user_id: ID of the user to notify
            type: Type of notification
            title: Short notification title
            message: Detailed notification message
            category: Notification category
            priority: Priority level
            entity_type: Type of entity (workflow, agent, etc.)
            entity_id: ID of the entity
            action_url: URL for action button
            action_label: Label for action button
            metadata: Additional context data
            expires_in_hours: Optional expiry time in hours
        """
        notification_id = str(uuid.uuid4())
        now = datetime.utcnow()
        expires_at = now + timedelta(hours=expires_in_hours) if expires_in_hours else None

        await repo_execute(
            """
            INSERT INTO notifications (
                id, user_id, type, title, message, category, priority,
                entity_type, entity_id, action_url, action_label,
                metadata, created_at, expires_at
            ) VALUES (
                :id, :user_id, :type, :title, :message, :category, :priority,
                :entity_type, :entity_id, :action_url, :action_label,
                :metadata, :created_at, :expires_at
            )
            """,
            {
                "id": notification_id,
                "user_id": user_id,
                "type": type.value,
                "title": title,
                "message": message,
                "category": category.value if category else None,
                "priority": priority.value,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "action_url": action_url,
                "action_label": action_label,
                "metadata": json.dumps(metadata) if metadata else None,
                "created_at": now.isoformat(),
                "expires_at": expires_at.isoformat() if expires_at else None,
            }
        )

        return await Notification.get(notification_id)

    @staticmethod
    async def get(notification_id: str) -> Optional["Notification"]:
        """Get a notification by ID"""
        rows = await repo_query(
            "SELECT * FROM notifications WHERE id = :id",
            {"id": notification_id}
        )

        if not rows:
            return None

        return Notification._from_row(rows[0])

    @staticmethod
    async def get_user_notifications(
        user_id: str,
        unread_only: bool = False,
        category: Optional[NotificationCategory] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List["Notification"]:
        """
        Get notifications for a user

        Args:
            user_id: User ID
            unread_only: Only return unread notifications
            category: Filter by category
            limit: Maximum number of results
            offset: Pagination offset
        """
        conditions = ["user_id = :user_id", "is_archived = 0"]
        params: Dict[str, Any] = {"user_id": user_id, "limit": limit, "offset": offset}

        if unread_only:
            conditions.append("is_read = 0")

        if category:
            conditions.append("category = :category")
            params["category"] = category.value

        # Exclude expired notifications
        conditions.append("(expires_at IS NULL OR expires_at > :now)")
        params["now"] = datetime.utcnow().isoformat()

        where_clause = " AND ".join(conditions)

        rows = await repo_query(
            f"""
            SELECT * FROM notifications
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
            """,
            params
        )

        return [Notification._from_row(row) for row in rows]

    @staticmethod
    async def get_unread_count(user_id: str) -> int:
        """Get count of unread notifications for a user"""
        rows = await repo_query(
            """
            SELECT COUNT(*) as count FROM notifications
            WHERE user_id = :user_id
            AND is_read = 0
            AND is_archived = 0
            AND (expires_at IS NULL OR expires_at > :now)
            """,
            {"user_id": user_id, "now": datetime.utcnow().isoformat()}
        )

        return rows[0]["count"] if rows else 0

    async def mark_as_read(self) -> None:
        """Mark notification as read"""
        await repo_execute(
            """
            UPDATE notifications
            SET is_read = 1, read_at = :read_at
            WHERE id = :id
            """,
            {"id": self.id, "read_at": datetime.utcnow().isoformat()}
        )
        self.is_read = True
        self.read_at = datetime.utcnow()

    async def mark_as_unread(self) -> None:
        """Mark notification as unread"""
        await repo_execute(
            "UPDATE notifications SET is_read = 0, read_at = NULL WHERE id = :id",
            {"id": self.id}
        )
        self.is_read = False
        self.read_at = None

    async def archive(self) -> None:
        """Archive notification"""
        await repo_execute(
            "UPDATE notifications SET is_archived = 1 WHERE id = :id",
            {"id": self.id}
        )
        self.is_archived = True

    async def delete(self) -> None:
        """Delete notification"""
        await repo_execute(
            "DELETE FROM notifications WHERE id = :id",
            {"id": self.id}
        )

    @staticmethod
    async def mark_all_as_read(user_id: str) -> int:
        """Mark all notifications as read for a user"""
        result = await repo_execute(
            """
            UPDATE notifications
            SET is_read = 1, read_at = :read_at
            WHERE user_id = :user_id AND is_read = 0
            """,
            {"user_id": user_id, "read_at": datetime.utcnow().isoformat()}
        )
        # repo_execute returns an int for SQLite
        return result if isinstance(result, int) else result.get("rows_affected", 0)

    @staticmethod
    async def cleanup_expired(days: int = 30) -> int:
        """
        Clean up old notifications

        Args:
            days: Delete notifications older than this many days
        """
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        result = await repo_execute(
            """
            DELETE FROM notifications
            WHERE (expires_at IS NOT NULL AND expires_at < :now)
            OR (created_at < :cutoff AND is_read = 1)
            """,
            {"now": datetime.utcnow().isoformat(), "cutoff": cutoff}
        )

        return result if isinstance(result, int) else result.get("rows_affected", 0)

    @staticmethod
    def _from_row(row: Dict[str, Any]) -> "Notification":
        """Convert database row to Notification object"""
        metadata = None
        if row.get("metadata"):
            try:
                metadata = json.loads(row["metadata"])
            except json.JSONDecodeError:
                metadata = None

        return Notification(
            id=row["id"],
            user_id=row["user_id"],
            type=row["type"],
            title=row["title"],
            message=row["message"],
            category=row.get("category"),
            priority=row.get("priority", "normal"),
            entity_type=row.get("entity_type"),
            entity_id=row.get("entity_id"),
            action_url=row.get("action_url"),
            action_label=row.get("action_label"),
            metadata=metadata,
            is_read=bool(row.get("is_read", 0)),
            is_archived=bool(row.get("is_archived", 0)),
            read_at=datetime.fromisoformat(row["read_at"]) if row.get("read_at") else None,
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
            expires_at=datetime.fromisoformat(row["expires_at"]) if row.get("expires_at") else None,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        result = asdict(self)

        # Convert datetime objects to ISO strings
        if self.created_at:
            result["created_at"] = self.created_at.isoformat()
        if self.read_at:
            result["read_at"] = self.read_at.isoformat()
        if self.expires_at:
            result["expires_at"] = self.expires_at.isoformat()

        return result
