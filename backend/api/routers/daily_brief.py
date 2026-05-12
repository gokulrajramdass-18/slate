"""
Daily Brief Router

API endpoints for retrieving personalized daily briefs and managing settings.
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from open_notebook.domain.user import User
from api.dependencies.auth import get_current_active_user
from api.services.daily_brief_service import get_daily_brief_data
from api.services.daily_brief_ai import generate_summary
from api.services.settings import get_daily_brief_config, set_daily_brief_config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["daily-brief"])


# ============================================================================
# Pydantic Models
# ============================================================================

class ExecutionItem(BaseModel):
    """Individual workflow execution item"""
    id: str
    workflow_id: str
    workflow_name: Optional[str]
    status: str
    started_at: str
    completed_at: Optional[str]
    triggered_by: str


class ExecutionsSummary(BaseModel):
    """Summary of workflow executions"""
    total: int = 0
    completed: int = 0
    failed: int = 0
    success_rate: float = 0.0
    recent_items: List[ExecutionItem] = []


class ApprovalItem(BaseModel):
    """Individual approval item requiring user action"""
    id: str
    workflow_name: str
    approval_prompt: str
    created_at: str
    timeout_at: Optional[str]
    action_url: str


class ScheduleItem(BaseModel):
    """Upcoming scheduled workflow"""
    id: str
    workflow_name: str
    next_run_at: str
    schedule_type: str
    cron_expression: Optional[str]


class NotificationItem(BaseModel):
    """Individual notification"""
    id: str
    type: str
    title: str
    message: str
    category: str
    priority: str
    created_at: str
    action_url: Optional[str]


class NotificationsSummary(BaseModel):
    """Summary of notifications"""
    total: int = 0
    unread: int = 0
    by_category: Dict[str, int] = {}
    recent_items: List[NotificationItem] = []


class OrchestrationItem(BaseModel):
    """Individual orchestration run"""
    id: str
    goal: str
    status: str
    current_phase: Optional[str]
    progress: float
    created_at: str
    updated_at: str


class OrchestrationsSummary(BaseModel):
    """Summary of orchestration runs"""
    total: int = 0
    completed: int = 0
    failed: int = 0
    recent_items: List[OrchestrationItem] = []


class DailyBriefData(BaseModel):
    """Daily brief data for user"""
    user_name: str
    last_login: Optional[str]
    current_time: str
    time_since_login: str
    executions_since_login: Optional[ExecutionsSummary] = None
    pending_approvals: Optional[List[ApprovalItem]] = None
    upcoming_schedules: Optional[List[ScheduleItem]] = None
    notifications: Optional[NotificationsSummary] = None
    orchestrations: Optional[OrchestrationsSummary] = None
    ai_summary: Optional[str] = None


class DailyBriefConfig(BaseModel):
    """Daily brief configuration"""
    enabled: bool = True
    ai_enabled: bool = True
    sources: List[str] = ["executions", "approvals", "schedules", "notifications", "orchestrations"]
    max_items: int = Field(5, ge=1, le=20)


class DailyBriefConfigUpdate(BaseModel):
    """Update daily brief configuration"""
    enabled: Optional[bool] = None
    ai_enabled: Optional[bool] = None
    sources: Optional[List[str]] = None
    max_items: Optional[int] = Field(None, ge=1, le=20)


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/api/daily-brief", response_model=DailyBriefData)
async def get_daily_brief(current_user: User = Depends(get_current_active_user)):
    """
    Get personalized daily brief for current user.

    Returns summary of activity since last login:
    - Workflow executions
    - Pending approvals
    - Upcoming schedules
    - Notifications
    - Orchestration runs
    - AI-generated summary (optional)

    Respects admin configuration for enabled data sources.
    """
    try:
        # Check if feature is enabled
        config = await get_daily_brief_config()
        if not config["enabled"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Daily brief feature is disabled"
            )

        # Get data since last login (or past 7 days if never logged in)
        since_dt = current_user.last_login
        brief_data_dict = await get_daily_brief_data(current_user.id, since_dt)

        # Generate AI summary if enabled
        if config["ai_enabled"]:
            try:
                ai_summary = await generate_summary(brief_data_dict)
                brief_data_dict["ai_summary"] = ai_summary
            except Exception as e:
                logger.error(f"AI summary generation failed: {e}")
                brief_data_dict["ai_summary"] = None

        # Convert to Pydantic model
        brief_data = DailyBriefData(**brief_data_dict)

        return brief_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting daily brief: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate daily brief: {str(e)}"
        )


@router.get("/api/admin/daily-brief/settings", response_model=DailyBriefConfig)
async def get_daily_brief_settings(current_user: User = Depends(get_current_active_user)):
    """
    Get daily brief configuration (admin only).

    Returns:
    - enabled: Whether daily brief is enabled
    - ai_enabled: Whether AI summaries are enabled
    - sources: List of enabled data sources
    - max_items: Maximum items per section
    """
    # Check admin access
    if not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:
        config = await get_daily_brief_config()
        return DailyBriefConfig(**config)
    except Exception as e:
        logger.error(f"Error getting daily brief settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get settings: {str(e)}"
        )


@router.put("/api/admin/daily-brief/settings", response_model=DailyBriefConfig)
async def update_daily_brief_settings(
    updates: DailyBriefConfigUpdate,
    current_user: User = Depends(get_current_active_user)
):
    """
    Update daily brief configuration (admin only).

    Allows admins to:
    - Enable/disable daily brief feature
    - Enable/disable AI summaries
    - Configure which data sources are included
    - Set max items per section
    """
    # Check admin access
    if not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    try:
        # Update settings
        await set_daily_brief_config(
            enabled=updates.enabled,
            ai_enabled=updates.ai_enabled,
            sources=updates.sources,
            max_items=updates.max_items
        )

        # Return updated config
        config = await get_daily_brief_config()
        return DailyBriefConfig(**config)
    except Exception as e:
        logger.error(f"Error updating daily brief settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update settings: {str(e)}"
        )
