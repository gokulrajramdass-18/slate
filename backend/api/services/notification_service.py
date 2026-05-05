"""
Notification Service

Manages WebSocket connections and broadcasting for real-time notifications
"""

import asyncio
import json
from typing import Dict, List, Set
from fastapi import WebSocket

from open_notebook.domain.notification import Notification


class NotificationService:
    """Service for managing notification WebSocket connections"""

    def __init__(self):
        # Map of user_id -> set of WebSocket connections
        self._connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: str, websocket: WebSocket):
        """Connect a WebSocket for a user"""
        await websocket.accept()

        async with self._lock:
            if user_id not in self._connections:
                self._connections[user_id] = set()
            self._connections[user_id].add(websocket)

        print(f"✓ WebSocket connected for user {user_id}")

    def disconnect(self, user_id: str, websocket: WebSocket):
        """Disconnect a WebSocket for a user"""
        if user_id in self._connections:
            self._connections[user_id].discard(websocket)

            # Clean up empty sets
            if not self._connections[user_id]:
                del self._connections[user_id]

        print(f"✗ WebSocket disconnected for user {user_id}")

    async def broadcast_notification(self, notification: Notification):
        """
        Broadcast a notification to a user's connected WebSocket clients

        Args:
            notification: The notification to broadcast
        """
        user_id = notification.user_id

        if user_id not in self._connections:
            return

        # Get all connections for this user
        connections = list(self._connections[user_id])

        # Prepare notification data
        data = {
            "type": "new_notification",
            "notification": notification.to_dict()
        }

        # Send to all connections
        disconnected = []
        for websocket in connections:
            try:
                await websocket.send_json(data)
            except Exception as e:
                print(f"Error sending to WebSocket: {e}")
                disconnected.append(websocket)

        # Clean up disconnected sockets
        for ws in disconnected:
            self.disconnect(user_id, ws)

    async def broadcast_to_user(self, user_id: str, data: dict):
        """
        Broadcast arbitrary data to a user's connected WebSocket clients

        Args:
            user_id: User ID
            data: Data to send
        """
        if user_id not in self._connections:
            return

        connections = list(self._connections[user_id])

        disconnected = []
        for websocket in connections:
            try:
                await websocket.send_json(data)
            except Exception as e:
                print(f"Error sending to WebSocket: {e}")
                disconnected.append(websocket)

        # Clean up disconnected sockets
        for ws in disconnected:
            self.disconnect(user_id, ws)

    def get_connected_users(self) -> List[str]:
        """Get list of users with active WebSocket connections"""
        return list(self._connections.keys())

    def get_connection_count(self, user_id: str) -> int:
        """Get number of active connections for a user"""
        return len(self._connections.get(user_id, set()))


# Global notification service instance
_notification_service: NotificationService = None


def get_notification_service() -> NotificationService:
    """Get or create the global notification service instance"""
    global _notification_service

    if _notification_service is None:
        _notification_service = NotificationService()

    return _notification_service


# ============================================================================
# Helper functions for creating notifications
# ============================================================================

async def notify_approval_pending(
    user_id: str,
    workflow_name: str,
    execution_id: str,
    approval_id: str,
    node_name: str
):
    """Create a notification for pending approval"""
    from open_notebook.domain.notification import (
        NotificationType,
        NotificationCategory,
        NotificationPriority
    )

    notification = await Notification.create(
        user_id=user_id,
        type=NotificationType.APPROVAL_PENDING,
        title=f"Approval Required: {workflow_name}",
        message=f"Workflow '{workflow_name}' is waiting for your approval at node '{node_name}'.",
        category=NotificationCategory.APPROVAL,
        priority=NotificationPriority.HIGH,
        entity_type="approval",
        entity_id=approval_id,
        action_url=f"/workflows/executions/{execution_id}/approve/{approval_id}",
        action_label="Review Approval",
        metadata={
            "workflow_name": workflow_name,
            "execution_id": execution_id,
            "node_name": node_name
        },
        expires_in_hours=24  # Expire after 24 hours
    )

    service = get_notification_service()
    await service.broadcast_notification(notification)


async def notify_execution_complete(
    user_id: str,
    workflow_name: str,
    execution_id: str,
    status: str
):
    """Create a notification for completed execution"""
    from open_notebook.domain.notification import (
        NotificationType,
        NotificationCategory,
        NotificationPriority
    )

    is_success = status == "completed"
    notification_type = NotificationType.EXECUTION_COMPLETE if is_success else NotificationType.EXECUTION_FAILED
    priority = NotificationPriority.NORMAL if is_success else NotificationPriority.HIGH

    notification = await Notification.create(
        user_id=user_id,
        type=notification_type,
        title=f"Workflow {'Completed' if is_success else 'Failed'}: {workflow_name}",
        message=f"Workflow '{workflow_name}' has {'completed successfully' if is_success else 'failed'}.",
        category=NotificationCategory.WORKFLOW,
        priority=priority,
        entity_type="execution",
        entity_id=execution_id,
        action_url=f"/workflows/executions/{execution_id}",
        action_label="View Details",
        metadata={
            "workflow_name": workflow_name,
            "status": status
        }
    )

    service = get_notification_service()
    await service.broadcast_notification(notification)


async def notify_agent_complete(
    user_id: str,
    agent_name: str,
    execution_id: str,
    status: str
):
    """Create a notification for completed agent execution"""
    from open_notebook.domain.notification import (
        NotificationType,
        NotificationCategory,
        NotificationPriority
    )

    is_success = status == "completed"
    notification_type = NotificationType.AGENT_COMPLETE if is_success else NotificationType.AGENT_FAILED

    notification = await Notification.create(
        user_id=user_id,
        type=notification_type,
        title=f"Agent {'Completed' if is_success else 'Failed'}: {agent_name}",
        message=f"Agent '{agent_name}' has {'completed successfully' if is_success else 'failed'}.",
        category=NotificationCategory.AGENT,
        priority=NotificationPriority.NORMAL,
        entity_type="agent_execution",
        entity_id=execution_id,
        action_url=f"/agents/executions/{execution_id}",
        action_label="View Results",
        metadata={
            "agent_name": agent_name,
            "status": status
        }
    )

    service = get_notification_service()
    await service.broadcast_notification(notification)


async def notify_schedule_triggered(
    user_id: str,
    workflow_name: str,
    schedule_name: str,
    execution_id: str
):
    """Create a notification for scheduled execution"""
    from open_notebook.domain.notification import (
        NotificationType,
        NotificationCategory,
        NotificationPriority
    )

    notification = await Notification.create(
        user_id=user_id,
        type=NotificationType.SCHEDULE_TRIGGERED,
        title=f"Scheduled Workflow Started: {workflow_name}",
        message=f"Workflow '{workflow_name}' was triggered by schedule '{schedule_name}'.",
        category=NotificationCategory.SCHEDULE,
        priority=NotificationPriority.LOW,
        entity_type="execution",
        entity_id=execution_id,
        action_url=f"/workflows/executions/{execution_id}",
        action_label="View Execution",
        metadata={
            "workflow_name": workflow_name,
            "schedule_name": schedule_name
        }
    )

    service = get_notification_service()
    await service.broadcast_notification(notification)
