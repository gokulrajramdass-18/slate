"""
Notification API Router

Provides endpoints for notification management and WebSocket support for real-time updates
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends, Query
from pydantic import BaseModel, Field

from open_notebook.domain.notification import (
    Notification,
    NotificationType,
    NotificationCategory,
    NotificationPriority
)
from api.services.notification_service import NotificationService, get_notification_service


router = APIRouter(prefix="/api/notifications", tags=["notifications"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateNotificationRequest(BaseModel):
    """Request model for creating a notification"""
    user_id: str
    type: NotificationType
    title: str = Field(..., max_length=200)
    message: str = Field(..., max_length=1000)
    category: Optional[NotificationCategory] = None
    priority: NotificationPriority = NotificationPriority.NORMAL
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    action_url: Optional[str] = None
    action_label: Optional[str] = None
    metadata: Optional[dict] = None
    expires_in_hours: Optional[int] = None


class NotificationResponse(BaseModel):
    """Response model for a notification"""
    id: str
    user_id: str
    type: str
    title: str
    message: str
    category: Optional[str] = None
    priority: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    action_url: Optional[str] = None
    action_label: Optional[str] = None
    metadata: Optional[dict] = None
    is_read: bool
    is_archived: bool
    read_at: Optional[str] = None
    created_at: Optional[str] = None
    expires_at: Optional[str] = None


class NotificationListResponse(BaseModel):
    """Response model for notification list"""
    notifications: List[NotificationResponse]
    total: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    """Response model for unread count"""
    count: int


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("", response_model=NotificationResponse, status_code=201)
async def create_notification(
    request: CreateNotificationRequest,
    service: NotificationService = Depends(get_notification_service)
):
    """
    Create a new notification

    This endpoint is typically called by internal services, but can also be used
    to create system notifications manually.
    """
    try:
        notification = await Notification.create(
            user_id=request.user_id,
            type=request.type,
            title=request.title,
            message=request.message,
            category=request.category,
            priority=request.priority,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            action_url=request.action_url,
            action_label=request.action_label,
            metadata=request.metadata,
            expires_in_hours=request.expires_in_hours
        )

        # Broadcast to connected WebSocket clients
        await service.broadcast_notification(notification)

        return NotificationResponse(**notification.to_dict())

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=NotificationListResponse)
async def get_notifications(
    user_id: str = Query(..., description="User ID"),
    unread_only: bool = Query(False, description="Show only unread notifications"),
    category: Optional[NotificationCategory] = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset")
):
    """
    Get notifications for a user

    Returns a paginated list of notifications with filtering options.
    """
    try:
        notifications = await Notification.get_user_notifications(
            user_id=user_id,
            unread_only=unread_only,
            category=category,
            limit=limit,
            offset=offset
        )

        unread_count = await Notification.get_unread_count(user_id)

        return NotificationListResponse(
            notifications=[NotificationResponse(**n.to_dict()) for n in notifications],
            total=len(notifications),
            unread_count=unread_count
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(user_id: str = Query(..., description="User ID")):
    """Get count of unread notifications for a user"""
    try:
        count = await Notification.get_unread_count(user_id)
        return UnreadCountResponse(count=count)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(notification_id: str):
    """Get a specific notification by ID"""
    notification = await Notification.get(notification_id)

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    return NotificationResponse(**notification.to_dict())


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_as_read(
    notification_id: str,
    service: NotificationService = Depends(get_notification_service)
):
    """Mark a notification as read"""
    notification = await Notification.get(notification_id)

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    await notification.mark_as_read()

    # Broadcast update to WebSocket clients
    await service.broadcast_notification(notification)

    return NotificationResponse(**notification.to_dict())


@router.post("/{notification_id}/unread", response_model=NotificationResponse)
async def mark_notification_as_unread(
    notification_id: str,
    service: NotificationService = Depends(get_notification_service)
):
    """Mark a notification as unread"""
    notification = await Notification.get(notification_id)

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    await notification.mark_as_unread()

    # Broadcast update to WebSocket clients
    await service.broadcast_notification(notification)

    return NotificationResponse(**notification.to_dict())


@router.post("/mark-all-read")
async def mark_all_as_read(
    user_id: str = Query(..., description="User ID"),
    service: NotificationService = Depends(get_notification_service)
):
    """Mark all notifications as read for a user"""
    try:
        count = await Notification.mark_all_as_read(user_id)

        # Broadcast update to WebSocket clients
        await service.broadcast_to_user(user_id, {
            "type": "all_marked_read",
            "count": count
        })

        return {"message": f"Marked {count} notifications as read"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{notification_id}")
async def delete_notification(notification_id: str):
    """Delete a notification"""
    notification = await Notification.get(notification_id)

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    await notification.delete()

    return {"message": "Notification deleted"}


@router.post("/{notification_id}/archive")
async def archive_notification(notification_id: str):
    """Archive a notification"""
    notification = await Notification.get(notification_id)

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    await notification.archive()

    return {"message": "Notification archived"}


# ============================================================================
# WebSocket Endpoint for Real-time Notifications
# ============================================================================

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    service: NotificationService = Depends(get_notification_service)
):
    """
    WebSocket endpoint for real-time notifications

    Clients connect to this endpoint to receive real-time notification updates.
    The connection sends a heartbeat ping every 30 seconds to keep the connection alive.
    """
    await service.connect(user_id, websocket)

    try:
        # Send initial unread count
        unread_count = await Notification.get_unread_count(user_id)
        await websocket.send_json({
            "type": "unread_count",
            "count": unread_count
        })

        # Keep connection alive and handle incoming messages
        while True:
            # Wait for client messages (e.g., ping/pong)
            data = await websocket.receive_text()

            # Echo back for keep-alive
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        service.disconnect(user_id, websocket)
    except Exception as e:
        print(f"WebSocket error for user {user_id}: {e}")
        service.disconnect(user_id, websocket)
