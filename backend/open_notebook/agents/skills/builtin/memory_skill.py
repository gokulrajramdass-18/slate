"""
Memory Skills - Persistent agent memory

Provides storage and retrieval of persistent memories for agents.
Supports agent-scoped, team-scoped, and global memories.
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict

from open_notebook.agents.skills.base import Skill, SkillCategory, SkillContext
from open_notebook.database.repository import repo_execute, repo_query


async def store_memory_handler(context: SkillContext) -> Dict[str, Any]:
    """
    Store a memory.

    Args:
        context: SkillContext with input_data containing:
            - key: Memory key
            - value: Memory value (any JSON-serializable type)

    Returns:
        Dict with stored status, key, and scope
    """
    key = context.input_data.get("key")
    value = context.input_data.get("value")
    scope = context.config.get("scope", "agent")  # agent, team, global

    if not key:
        raise ValueError("key is required")

    if value is None:
        raise ValueError("value is required")

    # Determine scope ID
    if scope == "agent":
        scope_id = context.agent_id
    elif scope == "team":
        if not context.team_id:
            raise ValueError("team_id not available in context for team scope")
        scope_id = context.team_id
    else:  # global
        scope_id = "global"

    context.record_step(
        "storing",
        f"Saving memory: {key} (scope: {scope})",
        status="running"
    )

    # Check if agent_memory table exists
    try:
        await repo_execute(
            """
            CREATE TABLE IF NOT EXISTS agent_memory (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                scope TEXT NOT NULL,
                created TEXT NOT NULL,
                updated TEXT NOT NULL,
                UNIQUE(agent_id, key, scope)
            )
            """,
            {}
        )

        # Create index
        await repo_execute(
            """
            CREATE INDEX IF NOT EXISTS idx_agent_memory_lookup
            ON agent_memory(agent_id, key, scope)
            """,
            {}
        )

    except Exception as e:
        # Table might already exist
        pass

    # Insert or replace memory
    memory_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    await repo_execute(
        """
        INSERT OR REPLACE INTO agent_memory
        (id, agent_id, key, value, scope, created, updated)
        VALUES (:id, :agent_id, :key, :value, :scope, :created, :updated)
        """,
        {
            "id": memory_id,
            "agent_id": scope_id,
            "key": key,
            "value": json.dumps(value),
            "scope": scope,
            "created": now,
            "updated": now
        }
    )

    context.record_step(
        "completed",
        f"Memory stored: {key}",
        status="completed",
        metadata={"key": key, "scope": scope}
    )

    return {
        "stored": True,
        "key": key,
        "scope": scope,
        "scope_id": scope_id
    }


async def recall_memory_handler(context: SkillContext) -> Dict[str, Any]:
    """
    Recall a memory.

    Args:
        context: SkillContext with input_data containing:
            - key: Memory key to retrieve

    Returns:
        Dict with found status and value (if found)
    """
    key = context.input_data.get("key")
    scope = context.config.get("scope", "agent")

    if not key:
        raise ValueError("key is required")

    # Determine scope ID
    if scope == "agent":
        scope_id = context.agent_id
    elif scope == "team":
        if not context.team_id:
            raise ValueError("team_id not available in context for team scope")
        scope_id = context.team_id
    else:  # global
        scope_id = "global"

    context.record_step(
        "recalling",
        f"Retrieving memory: {key} (scope: {scope})",
        status="running"
    )

    # Query memory
    try:
        rows = await repo_query(
            """
            SELECT value, updated FROM agent_memory
            WHERE agent_id = :agent_id AND key = :key AND scope = :scope
            """,
            {"agent_id": scope_id, "key": key, "scope": scope}
        )

        if rows:
            value = json.loads(rows[0]["value"])
            updated = rows[0]["updated"]

            context.record_step(
                "completed",
                f"Memory found: {key}",
                status="completed",
                metadata={"key": key, "found": True}
            )

            return {
                "found": True,
                "key": key,
                "value": value,
                "scope": scope,
                "updated": updated
            }
        else:
            context.record_step(
                "completed",
                f"Memory not found: {key}",
                status="completed",
                metadata={"key": key, "found": False}
            )

            return {
                "found": False,
                "key": key,
                "value": None,
                "scope": scope
            }

    except Exception as e:
        # Table might not exist yet
        context.record_step(
            "completed",
            f"Memory not found: {key} (table might not exist)",
            status="completed",
            metadata={"key": key, "found": False}
        )

        return {
            "found": False,
            "key": key,
            "value": None,
            "scope": scope
        }


# Define skills
memory_store_skill = Skill(
    id="memory_store",
    name="Store Memory",
    description="Store persistent agent memory that survives across sessions. Supports agent, team, and global scopes.",
    category=SkillCategory.MEMORY,
    handler=store_memory_handler,
    config_schema={
        "type": "object",
        "properties": {
            "scope": {
                "type": "string",
                "enum": ["agent", "team", "global"],
                "default": "agent",
                "description": "Memory scope: agent (private), team (shared with team), or global (shared across all agents)"
            }
        }
    },
    default_config={"scope": "agent"},
    tags=["memory", "storage", "persistence"],
    timeout_seconds=10,
    author="Open Notebook",
    version="1.0.0"
)

memory_recall_skill = Skill(
    id="memory_recall",
    name="Recall Memory",
    description="Retrieve stored agent memory by key. Returns value if found, or null if not found.",
    category=SkillCategory.MEMORY,
    handler=recall_memory_handler,
    config_schema={
        "type": "object",
        "properties": {
            "scope": {
                "type": "string",
                "enum": ["agent", "team", "global"],
                "default": "agent",
                "description": "Memory scope to search in"
            }
        }
    },
    default_config={"scope": "agent"},
    tags=["memory", "retrieval", "persistence"],
    timeout_seconds=10,
    author="Open Notebook",
    version="1.0.0"
)
