"""
Skill Binding - Associates skills with agents/roles/teams

Manages the relationship between skills and their targets (agents, roles, teams).
"""

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from open_notebook.database.repository import repo_query, repo_execute

logger = logging.getLogger(__name__)


@dataclass
class SkillBinding:
    """
    Binds a skill to an agent, role, or team.

    Exactly one of agent_id, role, or team_id must be set.
    """
    id: str
    skill_id: str
    agent_id: Optional[str] = None
    role: Optional[str] = None
    team_id: Optional[str] = None
    config: Dict = None
    enabled: bool = True
    created: str = None

    def __post_init__(self):
        """Initialize defaults."""
        if self.config is None:
            self.config = {}
        if self.created is None:
            self.created = datetime.utcnow().isoformat()


async def bind_skill_to_agent(
    skill_id: str,
    agent_id: str,
    config: Optional[Dict] = None
) -> SkillBinding:
    """
    Bind a skill to a specific agent.

    Args:
        skill_id: ID of skill to bind
        agent_id: ID of standalone agent
        config: Optional config overrides

    Returns:
        Created SkillBinding
    """
    binding_id = f"binding-{uuid.uuid4()}"
    binding = SkillBinding(
        id=binding_id,
        skill_id=skill_id,
        agent_id=agent_id,
        config=config or {}
    )

    await repo_execute(
        """
        INSERT INTO agent_skill_bindings
        (id, skill_id, agent_id, config, enabled, created)
        VALUES (:id, :skill_id, :agent_id, :config, :enabled, :created)
        """,
        {
            "id": binding.id,
            "skill_id": binding.skill_id,
            "agent_id": binding.agent_id,
            "config": json.dumps(binding.config),
            "enabled": 1 if binding.enabled else 0,
            "created": binding.created
        }
    )

    logger.info(f"Bound skill {skill_id} to agent {agent_id}")
    return binding


async def bind_skill_to_role(
    skill_id: str,
    role: str,
    config: Optional[Dict] = None
) -> SkillBinding:
    """
    Bind a skill to all agents with a role.

    Args:
        skill_id: ID of skill to bind
        role: Agent role
        config: Optional config overrides

    Returns:
        Created SkillBinding
    """
    binding_id = f"binding-{uuid.uuid4()}"
    binding = SkillBinding(
        id=binding_id,
        skill_id=skill_id,
        role=role,
        config=config or {}
    )

    await repo_execute(
        """
        INSERT INTO agent_skill_bindings
        (id, skill_id, role, config, enabled, created)
        VALUES (:id, :skill_id, :role, :config, :enabled, :created)
        """,
        {
            "id": binding.id,
            "skill_id": binding.skill_id,
            "role": binding.role,
            "config": json.dumps(binding.config),
            "enabled": 1 if binding.enabled else 0,
            "created": binding.created
        }
    )

    logger.info(f"Bound skill {skill_id} to role {role}")
    return binding


async def bind_skill_to_team(
    skill_id: str,
    team_id: str,
    config: Optional[Dict] = None
) -> SkillBinding:
    """
    Bind a skill to a team.

    Args:
        skill_id: ID of skill to bind
        team_id: ID of team
        config: Optional config overrides

    Returns:
        Created SkillBinding
    """
    binding_id = f"binding-{uuid.uuid4()}"
    binding = SkillBinding(
        id=binding_id,
        skill_id=skill_id,
        team_id=team_id,
        config=config or {}
    )

    await repo_execute(
        """
        INSERT INTO agent_skill_bindings
        (id, skill_id, team_id, config, enabled, created)
        VALUES (:id, :skill_id, :team_id, :config, :enabled, :created)
        """,
        {
            "id": binding.id,
            "skill_id": binding.skill_id,
            "team_id": binding.team_id,
            "config": json.dumps(binding.config),
            "enabled": 1 if binding.enabled else 0,
            "created": binding.created
        }
    )

    logger.info(f"Bound skill {skill_id} to team {team_id}")
    return binding


async def get_agent_skills(agent_id: str, role: str) -> List[SkillBinding]:
    """
    Get all skills bound to an agent (direct bindings + role bindings).

    Args:
        agent_id: Standalone agent ID
        role: Agent role

    Returns:
        List of SkillBindings
    """
    rows = await repo_query(
        """
        SELECT * FROM agent_skill_bindings
        WHERE (agent_id = :agent_id OR role = :role)
        AND enabled = 1
        ORDER BY created DESC
        """,
        {"agent_id": agent_id, "role": role}
    )

    return [
        SkillBinding(
            id=row["id"],
            skill_id=row["skill_id"],
            agent_id=row.get("agent_id"),
            role=row.get("role"),
            team_id=row.get("team_id"),
            config=json.loads(row["config"] or "{}"),
            enabled=bool(row["enabled"]),
            created=row["created"]
        )
        for row in rows
    ]


async def get_team_skills(team_id: str) -> List[SkillBinding]:
    """
    Get all skills bound to a team.

    Args:
        team_id: Team ID

    Returns:
        List of SkillBindings
    """
    rows = await repo_query(
        """
        SELECT * FROM agent_skill_bindings
        WHERE team_id = :team_id
        AND enabled = 1
        ORDER BY created DESC
        """,
        {"team_id": team_id}
    )

    return [
        SkillBinding(
            id=row["id"],
            skill_id=row["skill_id"],
            agent_id=row.get("agent_id"),
            role=row.get("role"),
            team_id=row.get("team_id"),
            config=json.loads(row["config"] or "{}"),
            enabled=bool(row["enabled"]),
            created=row["created"]
        )
        for row in rows
    ]


async def unbind_skill(binding_id: str) -> bool:
    """
    Remove a skill binding.

    Args:
        binding_id: Binding ID to remove

    Returns:
        True if binding was removed, False if not found
    """
    result = await repo_execute(
        "DELETE FROM agent_skill_bindings WHERE id = :id",
        {"id": binding_id}
    )

    logger.info(f"Removed skill binding {binding_id}")
    return True


async def update_binding_config(
    binding_id: str,
    config: Dict
) -> bool:
    """
    Update config for a binding.

    Args:
        binding_id: Binding ID to update
        config: New config dictionary

    Returns:
        True if updated
    """
    await repo_execute(
        """
        UPDATE agent_skill_bindings
        SET config = :config
        WHERE id = :id
        """,
        {
            "id": binding_id,
            "config": json.dumps(config)
        }
    )

    logger.info(f"Updated config for binding {binding_id}")
    return True


async def toggle_binding(binding_id: str, enabled: bool) -> bool:
    """
    Enable or disable a binding.

    Args:
        binding_id: Binding ID to toggle
        enabled: New enabled state

    Returns:
        True if updated
    """
    await repo_execute(
        """
        UPDATE agent_skill_bindings
        SET enabled = :enabled
        WHERE id = :id
        """,
        {
            "id": binding_id,
            "enabled": 1 if enabled else 0
        }
    )

    logger.info(f"{'Enabled' if enabled else 'Disabled'} binding {binding_id}")
    return True
