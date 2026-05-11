"""
Settings Service

Handles persistent application settings stored in the database.
"""

import json
from typing import Optional, Any
from open_notebook.database.repository import repo_query


async def get_setting(key: str, default: Any = None) -> Any:
    """
    Get a setting value from the database.

    Args:
        key: Setting key
        default: Default value if not found

    Returns:
        Setting value (parsed based on type) or default
    """
    result = await repo_query(
        "SELECT value, type FROM settings WHERE key = :key",
        {"key": key}
    )

    if not result:
        return default

    value = result[0]["value"]
    value_type = result[0]["type"]

    # Parse based on type
    if value_type == "json":
        return json.loads(value) if value else default
    elif value_type == "integer":
        return int(value) if value else default
    elif value_type == "boolean":
        return value.lower() == "true" if value else default
    else:  # string
        return value if value else default


async def set_setting(key: str, value: Any, value_type: str = "string", description: Optional[str] = None) -> None:
    """
    Set a setting value in the database.

    Args:
        key: Setting key
        value: Setting value
        value_type: Type of value (string, json, integer, boolean)
        description: Optional description
    """
    import aiosqlite
    import os

    # Convert value to string based on type
    if value_type == "json":
        str_value = json.dumps(value)
    elif value_type == "boolean":
        str_value = "true" if value else "false"
    else:
        str_value = str(value) if value is not None else ""

    # Get database path from environment or default
    db_path = os.getenv("SQLITE_DB_PATH", "./data/database.db")

    # Direct SQLite connection for UPDATE/INSERT with commit
    async with aiosqlite.connect(db_path) as db:
        # Check if exists
        cursor = await db.execute(
            "SELECT key FROM settings WHERE key = ?",
            (key,)
        )
        existing = await cursor.fetchone()

        if existing:
            # Update
            await db.execute(
                """
                UPDATE settings
                SET value = ?, type = ?, updated = datetime('now')
                WHERE key = ?
                """,
                (str_value, value_type, key)
            )
        else:
            # Insert
            await db.execute(
                """
                INSERT INTO settings (key, value, type, description, created, updated)
                VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                (key, str_value, value_type, description or "")
            )

        await db.commit()


async def get_model_defaults() -> dict:
    """
    Get default model selections from database.

    Returns:
        Dictionary with model IDs
    """
    return {
        "language_model_id": await get_setting("language_model_id", ""),
        "embedding_model_id": await get_setting("embedding_model_id", ""),
        "tts_model_id": await get_setting("tts_model_id", ""),
        "stt_model_id": await get_setting("stt_model_id", ""),
    }


async def set_model_defaults(
    language_model_id: Optional[str] = None,
    embedding_model_id: Optional[str] = None,
    tts_model_id: Optional[str] = None,
    stt_model_id: Optional[str] = None
) -> None:
    """
    Set default model selections in database.

    Args:
        language_model_id: Language model ID
        embedding_model_id: Embedding model ID
        tts_model_id: TTS model ID
        stt_model_id: STT model ID
    """
    if language_model_id is not None:
        await set_setting("language_model_id", language_model_id, "string", "Default language model for chat")
    if embedding_model_id is not None:
        await set_setting("embedding_model_id", embedding_model_id, "string", "Default embedding model for search")
    if tts_model_id is not None:
        await set_setting("tts_model_id", tts_model_id, "string", "Default text-to-speech model")
    if stt_model_id is not None:
        await set_setting("stt_model_id", stt_model_id, "string", "Default speech-to-text model")


async def get_chat_preferences() -> dict:
    """
    Get chat preferences from database.

    Returns:
        Dictionary with chat preferences
    """
    return {
        "enable_generative_ui": await get_setting("enable_generative_ui", False),
        "stream_responses": await get_setting("stream_responses", True),
        "include_context_by_default": await get_setting("include_context_by_default", True),
    }


async def set_chat_preferences(
    enable_generative_ui: Optional[bool] = None,
    stream_responses: Optional[bool] = None,
    include_context_by_default: Optional[bool] = None
) -> None:
    """
    Set chat preferences in database.

    Args:
        enable_generative_ui: Enable generative UI components in chat
        stream_responses: Enable streaming responses
        include_context_by_default: Include context from sources by default
    """
    if enable_generative_ui is not None:
        await set_setting(
            "enable_generative_ui",
            enable_generative_ui,
            "boolean",
            "Enable generative UI components (data tables, charts, etc.) in chat responses"
        )
    if stream_responses is not None:
        await set_setting(
            "stream_responses",
            stream_responses,
            "boolean",
            "Enable streaming for chat responses"
        )
    if include_context_by_default is not None:
        await set_setting(
            "include_context_by_default",
            include_context_by_default,
            "boolean",
            "Include context from notebook sources by default"
        )


async def get_daily_brief_config() -> dict:
    """
    Get daily brief configuration from database.

    Returns:
        Dictionary with daily brief settings
    """
    return {
        "enabled": await get_setting("daily_brief_enabled", True),
        "ai_enabled": await get_setting("daily_brief_ai_enabled", True),
        "sources": await get_setting(
            "daily_brief_sources",
            ["executions", "approvals", "schedules", "notifications", "orchestrations"]
        ),
        "max_items": await get_setting("daily_brief_max_items", 5),
    }


async def set_daily_brief_config(
    enabled: Optional[bool] = None,
    ai_enabled: Optional[bool] = None,
    sources: Optional[list] = None,
    max_items: Optional[int] = None
) -> None:
    """
    Set daily brief configuration in database.

    Args:
        enabled: Enable daily brief feature
        ai_enabled: Enable AI-powered summaries
        sources: List of enabled data sources
        max_items: Maximum items to show per section
    """
    if enabled is not None:
        await set_setting(
            "daily_brief_enabled",
            enabled,
            "boolean",
            "Enable daily brief feature"
        )
    if ai_enabled is not None:
        await set_setting(
            "daily_brief_ai_enabled",
            ai_enabled,
            "boolean",
            "Enable AI-powered summaries in daily brief"
        )
    if sources is not None:
        await set_setting(
            "daily_brief_sources",
            sources,
            "json",
            "Enabled data sources for daily brief generation"
        )
    if max_items is not None:
        await set_setting(
            "daily_brief_max_items",
            max_items,
            "integer",
            "Maximum items to show per section in daily brief"
        )
