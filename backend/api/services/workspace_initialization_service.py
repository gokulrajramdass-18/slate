"""
Workspace Initialization Service

Creates workspaces from generated plans, links resources, initializes tasks,
and configures agents. Used by the Guided Workspace Creation wizard after
a plan has been approved by the user.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from open_notebook.database.repository import (
    add_relationship,
    get_timestamp,
    repo_create,
    repo_execute,
    repo_query,
    repo_update,
    transaction,
)

logger = logging.getLogger(__name__)


class WorkspaceInitializationService:
    """
    Orchestrates workspace creation from a generated plan.

    Handles notebook creation, resource linking, task initialization,
    and agent configuration as a cohesive operation.
    """

    async def create_workspace_from_plan(
        self, plan: Dict, name: str, user_id: str, goal: str
    ) -> str:
        """Create a notebook and workspace plan from a generated plan.

        Args:
            plan: Generated plan dict with 'phases', 'collaboration_graph', etc.
            name: Workspace/notebook display name.
            user_id: ID of the user creating the workspace.
            goal: The user's original goal text.

        Returns:
            The workspace (notebook) ID.

        Raises:
            Exception: If notebook or plan creation fails.
        """
        now = get_timestamp()
        workspace_id = str(uuid.uuid4())

        # Create the notebook
        notebook_data = {
            "id": workspace_id,
            "name": name,
            "description": f"Workspace for: {goal[:200]}",
            "goal": goal,
            "created": now,
            "updated": now,
        }

        try:
            await repo_create("notebooks", notebook_data)
            logger.info("Created notebook %s for workspace '%s'", workspace_id, name)
        except Exception:
            logger.exception("Failed to create notebook for workspace '%s'", name)
            raise

        # Create the workspace plan record
        plan_id = str(uuid.uuid4())
        plan_data = {
            "id": plan_id,
            "workspace_id": workspace_id,
            "goal": goal,
            "phases": json.dumps(plan.get("phases", [])),
            "collaboration_graph": json.dumps(plan.get("collaboration_graph", {})),
            "status": "pending",
            "progress": json.dumps({}),
            "created": now,
            "updated": now,
        }

        try:
            await repo_create("workspace_plans", plan_data)
            logger.info("Created workspace plan %s for workspace %s", plan_id, workspace_id)
        except Exception:
            logger.exception("Failed to create workspace plan for workspace %s", workspace_id)
            raise

        return workspace_id

    async def link_resources(self, workspace_id: str, resources: Dict) -> None:
        """Link selected resources (sources, tools, agents) to the workspace.

        Args:
            workspace_id: The notebook/workspace ID to link resources to.
            resources: Dict with optional keys:
                - source_ids: List of source IDs to link.
                - tool_ids: List of tool IDs (stored as config).
                - agent_ids: List of standalone agent IDs to associate.
                - team_ids: List of agent team IDs to associate.

        Raises:
            Exception: If any linking operation fails (non-fatal per item).
        """
        logger.info(f"=== link_resources called: workspace_id={workspace_id}, resources={resources} ===")
        source_ids: List[str] = resources.get("source_ids", [])
        logger.info(f"=== Extracted source_ids: {source_ids} ===")
        tool_ids: List[str] = resources.get("tool_ids", [])
        agent_ids: List[str] = resources.get("agent_ids", [])
        team_ids: List[str] = resources.get("team_ids", [])

        # Link sources via notebook_source junction table
        for source_id in source_ids:
            try:
                await add_relationship("notebook_source", workspace_id, source_id)
                logger.debug("Linked source %s to workspace %s", source_id, workspace_id)
            except Exception:
                logger.warning(
                    "Failed to link source %s to workspace %s",
                    source_id, workspace_id,
                    exc_info=True,
                )

        # Associate standalone agents with the notebook
        for agent_id in agent_ids:
            try:
                await repo_update("standalone_agents", agent_id, {
                    "notebook_id": workspace_id,
                    "updated": get_timestamp(),
                })
                logger.debug("Associated agent %s with workspace %s", agent_id, workspace_id)
            except Exception:
                logger.warning(
                    "Failed to associate agent %s with workspace %s",
                    agent_id, workspace_id,
                    exc_info=True,
                )

        # Associate agent teams with the notebook
        for team_id in team_ids:
            try:
                await repo_update("agent_teams", team_id, {
                    "notebook_id": workspace_id,
                    "updated": get_timestamp(),
                })
                logger.debug("Associated team %s with workspace %s", team_id, workspace_id)
            except Exception:
                logger.warning(
                    "Failed to associate team %s with workspace %s",
                    team_id, workspace_id,
                    exc_info=True,
                )

        # Store tool associations as workspace config if any
        if tool_ids:
            try:
                config = json.dumps({"tool_ids": tool_ids})
                await repo_execute(
                    """
                    UPDATE notebooks SET config = :config, updated = :updated
                    WHERE id = :id
                    """,
                    {"config": config, "updated": get_timestamp(), "id": workspace_id},
                )
                logger.debug("Stored %d tool IDs in workspace %s config", len(tool_ids), workspace_id)
            except Exception:
                logger.warning(
                    "Failed to store tool config for workspace %s",
                    workspace_id,
                    exc_info=True,
                )

        logger.info(
            "Linked resources to workspace %s: %d sources, %d tools, %d agents, %d teams",
            workspace_id, len(source_ids), len(tool_ids), len(agent_ids), len(team_ids),
        )

    async def initialize_tasks(self, workspace_id: str, plan: Dict) -> None:
        """Create workspace_plan_tasks entries for all tasks in all phases.

        Extracts tasks from plan['phases'], creates a database record for each,
        and sets initial status to 'pending'.

        Args:
            workspace_id: The notebook/workspace ID.
            plan: Generated plan dict containing 'phases' with nested tasks.

        Raises:
            Exception: If plan lookup or task creation fails.
        """
        # Find the workspace plan record
        results = await repo_query(
            "SELECT id FROM workspace_plans WHERE workspace_id = :workspace_id",
            {"workspace_id": workspace_id},
            fetch_one=True,
        )

        if not results:
            logger.error("No workspace plan found for workspace %s", workspace_id)
            raise ValueError(f"No workspace plan found for workspace {workspace_id}")

        plan_id = results["id"]
        phases = plan.get("phases", [])
        now = get_timestamp()
        task_count = 0

        for phase in phases:
            # Support both "name" and "phase" keys (plan generation uses "phase")
            phase_name = phase.get("name") or phase.get("phase", "Unnamed Phase")
            tasks = phase.get("tasks", [])

            for task in tasks:
                task_id = str(uuid.uuid4())
                task_data = {
                    "id": task_id,
                    "plan_id": plan_id,
                    "phase_name": phase_name,
                    "name": task.get("name", "Unnamed Task"),
                    "description": task.get("description", ""),
                    "assigned_agent_id": task.get("assigned_agent_id"),
                    "status": "pending",
                    "estimated_duration": task.get("estimated_duration"),
                    "dependencies": json.dumps(task.get("dependencies", [])),
                    "required_tools": json.dumps(task.get("required_tools", [])),
                    "required_sources": json.dumps(task.get("required_sources", [])),
                    "created": now,
                    "updated": now,
                }

                try:
                    await repo_create("workspace_plan_tasks", task_data)
                    task_count += 1

                    # Log agent assignment for debugging
                    if task_data.get("assigned_agent_id"):
                        logger.info(f"  ✓ Task '{task.get('name')}' assigned to agent {task_data['assigned_agent_id']}")
                    else:
                        logger.warning(f"  ⚠ Task '{task.get('name')}' has NO assigned agent")

                except Exception:
                    logger.warning(
                        "Failed to create task '%s' in phase '%s'",
                        task.get("name", "?"), phase_name,
                        exc_info=True,
                    )

        logger.info(
            "Initialized %d tasks across %d phases for workspace %s",
            task_count, len(phases), workspace_id,
        )

    async def configure_agents(self, workspace_id: str, assignments: Dict) -> None:
        """Configure agent-to-task assignments for the workspace.

        Updates standalone agents with notebook associations and records
        which tasks each agent is responsible for.

        Args:
            workspace_id: The notebook/workspace ID.
            assignments: Dict mapping agent_id -> list of task_ids.
                Example: {"agent-uuid-1": ["task-uuid-a", "task-uuid-b"]}

        Raises:
            Exception: If agent update or task assignment fails (non-fatal per item).
        """
        if not assignments:
            logger.debug("No agent assignments to configure for workspace %s", workspace_id)
            return

        for agent_id, task_ids in assignments.items():
            # Associate agent with the workspace notebook
            try:
                await repo_update("standalone_agents", agent_id, {
                    "notebook_id": workspace_id,
                    "updated": get_timestamp(),
                })
            except Exception:
                logger.warning(
                    "Failed to associate agent %s with workspace %s",
                    agent_id, workspace_id,
                    exc_info=True,
                )
                continue

            # Assign agent to each task
            for task_id in task_ids:
                try:
                    await repo_update("workspace_plan_tasks", task_id, {
                        "assigned_agent_id": agent_id,
                        "updated": get_timestamp(),
                    })
                except Exception:
                    logger.warning(
                        "Failed to assign agent %s to task %s",
                        agent_id, task_id,
                        exc_info=True,
                    )

        logger.info(
            "Configured %d agent assignments for workspace %s",
            len(assignments), workspace_id,
        )


# Singleton instance
_workspace_init_service: Optional[WorkspaceInitializationService] = None


def get_workspace_initialization_service() -> WorkspaceInitializationService:
    """Get or create the workspace initialization service singleton."""
    global _workspace_init_service
    if _workspace_init_service is None:
        _workspace_init_service = WorkspaceInitializationService()
    return _workspace_init_service
