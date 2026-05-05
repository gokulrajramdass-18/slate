"""
External Notifications API Router

Public API endpoints for external applications to send notifications.
Requires API key authentication.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request, status
from pydantic import BaseModel, Field

from open_notebook.domain.notification import (
    Notification,
    NotificationType,
    NotificationCategory,
    NotificationPriority
)
from open_notebook.domain.api_key import APIKey
from api.middleware.api_key_auth import verify_notifications_write
from api.services.notification_service import get_notification_service


router = APIRouter(prefix="/api/external/notifications", tags=["External Notifications"])


# ============================================================================
# Request/Response Models
# ============================================================================

class ExternalNotificationRequest(BaseModel):
    """Request model for creating a notification from external application"""
    user_id: str = Field(..., description="Target user ID to notify")
    title: str = Field(..., max_length=200, description="Notification title")
    message: str = Field(..., max_length=1000, description="Notification message")
    type: NotificationType = Field(
        NotificationType.SYSTEM,
        description="Notification type (defaults to 'system')"
    )
    category: Optional[NotificationCategory] = Field(
        None,
        description="Notification category for grouping"
    )
    priority: NotificationPriority = Field(
        NotificationPriority.NORMAL,
        description="Priority level (low, normal, high, urgent)"
    )
    action_url: Optional[str] = Field(
        None,
        description="URL for the action button"
    )
    action_label: Optional[str] = Field(
        None,
        description="Label for the action button"
    )
    metadata: Optional[dict] = Field(
        None,
        description="Additional metadata (JSON object)"
    )
    expires_in_hours: Optional[int] = Field(
        None,
        ge=1,
        le=8760,  # Max 1 year
        description="Expiration time in hours"
    )


class ExternalNotificationResponse(BaseModel):
    """Response model for external notification creation"""
    id: str
    user_id: str
    title: str
    message: str
    type: str
    category: Optional[str]
    priority: str
    action_url: Optional[str]
    action_label: Optional[str]
    created_at: str
    expires_at: Optional[str]
    success: bool = True


class BatchNotificationRequest(BaseModel):
    """Request model for sending notifications to multiple users"""
    user_ids: list[str] = Field(..., min_items=1, max_items=100, description="List of user IDs (max 100)")
    title: str = Field(..., max_length=200)
    message: str = Field(..., max_length=1000)
    type: NotificationType = NotificationType.SYSTEM
    category: Optional[NotificationCategory] = None
    priority: NotificationPriority = NotificationPriority.NORMAL
    action_url: Optional[str] = None
    action_label: Optional[str] = None
    metadata: Optional[dict] = None
    expires_in_hours: Optional[int] = None


class BatchNotificationResponse(BaseModel):
    """Response for batch notification"""
    total: int
    successful: int
    failed: int
    notification_ids: list[str]
    errors: Optional[list[dict]] = None


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/send", response_model=ExternalNotificationResponse, status_code=201)
async def send_notification(
    request_data: ExternalNotificationRequest,
    request: Request,
    api_key: APIKey = Depends(verify_notifications_write)
):
    """
    Send a notification to a user (External API)

    Requires API key authentication with 'notifications:write' scope.

    **Authentication:**
    ```
    Authorization: Bearer sk_your_api_key_here
    ```

    **Example Request:**
    ```json
    {
        "user_id": "user-123",
        "title": "New Order Received",
        "message": "You have a new order #12345 from external system",
        "type": "system",
        "priority": "high",
        "action_url": "/orders/12345",
        "action_label": "View Order",
        "metadata": {
            "order_id": "12345",
            "source": "ecommerce-platform"
        }
    }
    ```

    **Rate Limits:**
    - 100 requests per minute per API key
    - 1000 requests per hour per API key
    """
    try:
        # Create the notification
        notification = await Notification.create(
            user_id=request_data.user_id,
            type=request_data.type,
            title=request_data.title,
            message=request_data.message,
            category=request_data.category,
            priority=request_data.priority,
            entity_type="external_api",
            entity_id=api_key.id,
            action_url=request_data.action_url,
            action_label=request_data.action_label,
            metadata={
                **(request_data.metadata or {}),
                "api_key_id": api_key.id,
                "api_key_name": api_key.name,
                "application_name": api_key.application_name
            },
            expires_in_hours=request_data.expires_in_hours
        )

        # Broadcast to connected WebSocket clients
        service = get_notification_service()
        await service.broadcast_notification(notification)

        # Log API key usage
        await api_key.log_usage(
            endpoint="/api/external/notifications/send",
            method="POST",
            status_code=201,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            request_body=request_data.dict(),
            response_body={"notification_id": notification.id}
        )

        return ExternalNotificationResponse(
            **notification.to_dict(),
            success=True
        )

    except Exception as e:
        # Log error
        await api_key.log_usage(
            endpoint="/api/external/notifications/send",
            method="POST",
            status_code=500,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            request_body=request_data.dict(),
            error=str(e)
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create notification: {str(e)}"
        )


@router.post("/send-batch", response_model=BatchNotificationResponse)
async def send_batch_notifications(
    request_data: BatchNotificationRequest,
    request: Request,
    api_key: APIKey = Depends(verify_notifications_write)
):
    """
    Send notifications to multiple users at once (External API)

    Requires API key authentication with 'notifications:write' scope.
    Maximum 100 users per request.

    **Example Request:**
    ```json
    {
        "user_ids": ["user-1", "user-2", "user-3"],
        "title": "System Maintenance",
        "message": "System will be down for maintenance tonight at 11 PM",
        "type": "system",
        "priority": "high",
        "action_url": "/system/status",
        "action_label": "View Status"
    }
    ```
    """
    notification_ids = []
    errors = []
    successful = 0
    service = get_notification_service()

    for user_id in request_data.user_ids:
        try:
            notification = await Notification.create(
                user_id=user_id,
                type=request_data.type,
                title=request_data.title,
                message=request_data.message,
                category=request_data.category,
                priority=request_data.priority,
                entity_type="external_api",
                entity_id=api_key.id,
                action_url=request_data.action_url,
                action_label=request_data.action_label,
                metadata={
                    **(request_data.metadata or {}),
                    "api_key_id": api_key.id,
                    "api_key_name": api_key.name,
                    "application_name": api_key.application_name,
                    "batch": True
                },
                expires_in_hours=request_data.expires_in_hours
            )

            notification_ids.append(notification.id)
            successful += 1

            # Broadcast to user
            await service.broadcast_notification(notification)

        except Exception as e:
            errors.append({
                "user_id": user_id,
                "error": str(e)
            })

    # Log batch usage
    await api_key.log_usage(
        endpoint="/api/external/notifications/send-batch",
        method="POST",
        status_code=200,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        request_body=request_data.dict(),
        response_body={
            "total": len(request_data.user_ids),
            "successful": successful,
            "failed": len(errors)
        }
    )

    return BatchNotificationResponse(
        total=len(request_data.user_ids),
        successful=successful,
        failed=len(errors),
        notification_ids=notification_ids,
        errors=errors if errors else None
    )


@router.get("/health")
async def health_check(api_key: APIKey = Depends(verify_notifications_write)):
    """
    Health check endpoint for external API

    Verifies that your API key is valid and the service is operational.
    """
    return {
        "status": "healthy",
        "api_key_name": api_key.name,
        "application": api_key.application_name,
        "scopes": api_key.scopes
    }
