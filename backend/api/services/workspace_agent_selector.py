"""
Workspace Agent Selector

Determines which agent should handle chat messages in workspaces
based on agent assignments from the guided workspace wizard.
"""

import json
import logging
from typing import Dict, List, Optional

from open_notebook.database.repository import repo_query

logger = logging.getLogger(__name__)


class WorkspaceAgentSelector:
    """
    Selects the appropriate agent for handling workspace chat messages
    based on guided workspace agent assignments.
    """

    async def get_workspace_agents(self, workspace_id: str) -> List[Dict]:
        """
        Get all agents assigned to a workspace.

        Returns:
            List of agent dicts with type, id, name, role, etc.
        """
        # Get standalone agents associated with this workspace
        agents = await repo_query(
            """
            SELECT id, name, description, role, system_prompt, model_name,
                   tool_ids, skill_ids, mcp_server_ids, data_source_ids, config
            FROM standalone_agents
            WHERE notebook_id = :workspace_id AND status = 'active'
            ORDER BY created ASC
            """,
            {"workspace_id": workspace_id}
        )

        # Get teams associated with this workspace
        teams = await repo_query(
            """
            SELECT id, name, description, config
            FROM agent_teams
            WHERE notebook_id = :workspace_id AND status = 'active'
            ORDER BY created ASC
            """,
            {"workspace_id": workspace_id}
        )

        result = []

        # Add standalone agents
        for agent in agents:
            result.append({
                "type": "agent",
                "id": agent["id"],
                "name": agent["name"],
                "description": agent.get("description"),
                "role": agent.get("role"),
                "system_prompt": agent.get("system_prompt"),
                "model_name": agent.get("model_name"),
                "tool_ids": agent.get("tool_ids", "[]"),
                "skill_ids": agent.get("skill_ids", "[]"),
                "mcp_server_ids": agent.get("mcp_server_ids", "[]"),
                "data_source_ids": agent.get("data_source_ids", "[]"),
                "config": agent.get("config", "{}")
            })

        # Add teams
        for team in teams:
            # Get team members
            members = await repo_query(
                """
                SELECT sa.id, sa.name, sa.role
                FROM standalone_agents sa
                JOIN agent_team_members atm ON sa.id = atm.agent_id
                WHERE atm.team_id = :team_id AND sa.status = 'active'
                ORDER BY atm.sequence
                """,
                {"team_id": team["id"]}
            )

            result.append({
                "type": "team",
                "id": team["id"],
                "name": team["name"],
                "description": team.get("description"),
                "config": team.get("config", "{}"),
                "members": [
                    {"id": m["id"], "name": m["name"], "role": m.get("role")}
                    for m in members
                ]
            })

        return result

    async def select_agent_for_message(
        self,
        workspace_id: str,
        message: str,
        context: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Select the best agent to handle a chat message.

        For now, this returns the first assigned agent.
        Future: Implement intelligent routing based on message content and agent roles.

        Args:
            workspace_id: Workspace/notebook ID
            message: User's message
            context: Optional context information

        Returns:
            Selected agent dict or None if no agents assigned
        """
        agents = await self.get_workspace_agents(workspace_id)

        if not agents:
            logger.info(f"No agents assigned to workspace {workspace_id}")
            return None

        # For now, return the first agent
        # TODO: Implement intelligent routing based on:
        #  - Message content analysis
        #  - Agent role matching
        #  - Agent skills/tools
        #  - Current task context
        selected = agents[0]

        logger.info(
            f"Selected agent '{selected['name']}' ({selected['type']}) for workspace {workspace_id}"
        )

        return selected

    async def get_primary_workspace_agent(self, workspace_id: str) -> Optional[Dict]:
        """
        Get the primary agent for a workspace (typically the first/lead agent).

        Returns:
            Primary agent dict or None if no agents assigned
        """
        agents = await self.get_workspace_agents(workspace_id)
        return agents[0] if agents else None


# Singleton
_workspace_agent_selector: Optional[WorkspaceAgentSelector] = None


def get_workspace_agent_selector() -> WorkspaceAgentSelector:
    """Get or create the WorkspaceAgentSelector singleton."""
    global _workspace_agent_selector
    if _workspace_agent_selector is None:
        _workspace_agent_selector = WorkspaceAgentSelector()
    return _workspace_agent_selector
