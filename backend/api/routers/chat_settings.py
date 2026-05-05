"""
Chat Settings Router

Handles chat preferences and configuration.
"""

from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(
    prefix="/api/chat/settings",
    tags=["chat-settings"],
)


# ============================================================================
# Request/Response Models
# ============================================================================

class ChatPreferences(BaseModel):
    """Chat preferences configuration"""
    enable_generative_ui: bool = False
    stream_responses: bool = True
    include_context_by_default: bool = True


class ChatPreferencesUpdate(BaseModel):
    """Update chat preferences"""
    enable_generative_ui: Optional[bool] = None
    stream_responses: Optional[bool] = None
    include_context_by_default: Optional[bool] = None


# ============================================================================
# Endpoints
# ============================================================================

@router.get("", response_model=ChatPreferences)
async def get_chat_settings():
    """
    Get current chat preferences from database.

    Returns:
        Chat preferences configuration
    """
    from api.services.settings import get_chat_preferences
    prefs = await get_chat_preferences()
    return ChatPreferences(**prefs)


@router.put("", response_model=ChatPreferences)
async def update_chat_settings(updates: ChatPreferencesUpdate):
    """
    Update chat preferences in database.

    Args:
        updates: Chat preferences to update

    Returns:
        Updated chat preferences
    """
    from api.services.settings import set_chat_preferences, get_chat_preferences

    # Save to database
    await set_chat_preferences(
        enable_generative_ui=updates.enable_generative_ui,
        stream_responses=updates.stream_responses,
        include_context_by_default=updates.include_context_by_default
    )

    # Return updated preferences
    prefs = await get_chat_preferences()
    return ChatPreferences(**prefs)
