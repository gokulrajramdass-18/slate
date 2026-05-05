"""
Template Instantiation Service

Clones workspace templates into new workspace instances with parameter substitution.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from open_notebook.domain.workspace_template import WorkspaceTemplate
from open_notebook.domain.guided_workspace import WorkspacePlan, WorkspacePlanTask
from open_notebook.database.repository import repo_create, repo_execute, repo_query, get_timestamp
from api.services.workspace_initialization_service import WorkspaceInitializationService

logger = logging.getLogger(__name__)


class TemplateInstantiationService:
    """
    Service for instantiating workspace templates.

    Handles parameter validation, placeholder resolution, and workspace creation
    from reusable templates.
    """

    def __init__(self):
        """Initialize template instantiation service."""
        self.workspace_init_service = WorkspaceInitializationService()

    async def instantiate_template(
        self,
        template_id: str,
        parameters: Dict[str, Any],
        user_id: str,
        workspace_name: Optional[str] = None
    ) -> str:
        """
        Instantiate a template as a new workspace with parameter substitution.

        Args:
            template_id: Template ID to instantiate.
            parameters: Runtime parameter values.
            user_id: User creating the workspace.
            workspace_name: Optional workspace name (generated if not provided).

        Returns:
            Workspace ID.

        Raises:
            ValueError: If template not found or parameter validation fails.
        """
        logger.info(f"Instantiating template {template_id} for user {user_id}")

        # Load template
        template = await WorkspaceTemplate.get(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        # Validate parameters
        validation = template.validate_parameters(parameters)
        if not validation["valid"]:
            raise ValueError(f"Parameter validation failed: {', '.join(validation['errors'])}")

        # Generate workspace name if not provided
        if not workspace_name:
            workspace_name = f"{template.name} - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"

        # Generate workspace ID
        workspace_id = str(uuid.uuid4())
        context = {"workspace_id": workspace_id, "user_id": user_id}

        # Resolve phases with parameter substitution
        phases = template.get_phases()
        resolved_phases = self._resolve_phases(phases, parameters, context, template)

        # Resolve collaboration graph
        collaboration_graph = template.get_collaboration_graph()
        resolved_collab_graph = self._resolve_dict_placeholders(
            collaboration_graph, parameters, context, template
        )

        # Build plan structure
        plan = {
            "phases": resolved_phases,
            "collaboration_graph": resolved_collab_graph,
        }

        # Create goal string with parameter info
        goal = f"Template: {template.name}"
        if parameters:
            param_str = ", ".join(f"{k}={v}" for k, v in parameters.items())
            goal += f" | Parameters: {param_str}"

        # Create workspace from plan
        workspace_id = await self.workspace_init_service.create_workspace_from_plan(
            plan=plan,
            name=workspace_name,
            user_id=user_id,
            goal=goal
        )

        logger.info(f"Created workspace {workspace_id} from template {template_id}")

        # Link resources from template defaults
        resources = template.get_default_resources()
        if resources:
            await self.workspace_init_service.link_resources(workspace_id, resources)
            logger.info(f"Linked {len(resources.get('source_ids', []))} sources to workspace")

        # Initialize tasks
        await self.workspace_init_service.initialize_tasks(workspace_id, plan)
        logger.info(f"Initialized tasks for workspace {workspace_id}")

        # Increment template usage count
        await template.increment_usage()

        return workspace_id

    def _resolve_phases(
        self,
        phases: list,
        parameters: Dict[str, Any],
        context: Dict[str, Any],
        template: WorkspaceTemplate
    ) -> list:
        """Resolve all placeholders in phases structure.

        Args:
            phases: Phase definitions list.
            parameters: Runtime parameter values.
            context: Context with workspace_id, user_id.
            template: Template instance for placeholder resolution.

        Returns:
            Resolved phases list.
        """
        resolved_phases = []

        for phase in phases:
            resolved_phase = {
                "phase": template.resolve_placeholders(phase.get("name") or phase.get("phase", ""), parameters, context),
                "tasks": []
            }

            for task in phase.get("tasks", []):
                resolved_task = {
                    "name": template.resolve_placeholders(task.get("name", ""), parameters, context),
                    "description": template.resolve_placeholders(task.get("description", ""), parameters, context),
                    "assigned_agent_id": task.get("assigned_agent_id"),
                    "estimated_duration": task.get("estimated_duration"),
                    "dependencies": task.get("dependencies", []),
                    "required_tools": task.get("required_tools", []),
                    "required_sources": task.get("required_sources", []),
                }
                resolved_phase["tasks"].append(resolved_task)

            resolved_phases.append(resolved_phase)

        return resolved_phases

    def _resolve_dict_placeholders(
        self,
        data: Dict,
        parameters: Dict[str, Any],
        context: Dict[str, Any],
        template: WorkspaceTemplate
    ) -> Dict:
        """Recursively resolve placeholders in dictionary.

        Args:
            data: Dictionary to process.
            parameters: Runtime parameter values.
            context: Context with workspace_id, user_id.
            template: Template instance for placeholder resolution.

        Returns:
            Dictionary with resolved placeholders.
        """
        if not data:
            return {}

        resolved = {}
        for key, value in data.items():
            if isinstance(value, str):
                resolved[key] = template.resolve_placeholders(value, parameters, context)
            elif isinstance(value, dict):
                resolved[key] = self._resolve_dict_placeholders(value, parameters, context, template)
            elif isinstance(value, list):
                resolved[key] = [
                    template.resolve_placeholders(item, parameters, context) if isinstance(item, str)
                    else self._resolve_dict_placeholders(item, parameters, context, template) if isinstance(item, dict)
                    else item
                    for item in value
                ]
            else:
                resolved[key] = value

        return resolved

    async def validate_template_parameters(
        self,
        template_id: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate parameters against template definition.

        Args:
            template_id: Template ID.
            parameters: Runtime parameter values.

        Returns:
            Dict with 'valid' bool and 'errors' list.

        Raises:
            ValueError: If template not found.
        """
        template = await WorkspaceTemplate.get(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        return template.validate_parameters(parameters)

    async def preview_instantiation(
        self,
        template_id: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Preview what a template instantiation would look like.

        Args:
            template_id: Template ID.
            parameters: Runtime parameter values.

        Returns:
            Dict with resolved phases, collaboration graph, resource counts.

        Raises:
            ValueError: If template not found or validation fails.
        """
        template = await WorkspaceTemplate.get(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        # Validate parameters
        validation = template.validate_parameters(parameters)
        if not validation["valid"]:
            raise ValueError(f"Parameter validation failed: {', '.join(validation['errors'])}")

        # Mock context for preview
        context = {"workspace_id": "<WORKSPACE_ID>", "user_id": "<USER_ID>"}

        # Resolve phases
        phases = template.get_phases()
        resolved_phases = self._resolve_phases(phases, parameters, context, template)

        # Resolve collaboration graph
        collaboration_graph = template.get_collaboration_graph()
        resolved_collab_graph = self._resolve_dict_placeholders(
            collaboration_graph, parameters, context, template
        )

        # Get resource counts
        resources = template.get_default_resources()

        return {
            "template_name": template.name,
            "phases": resolved_phases,
            "collaboration_graph": resolved_collab_graph,
            "resource_counts": {
                "sources": len(resources.get("source_ids", [])),
                "tools": len(resources.get("tool_ids", [])),
                "agents": len(resources.get("agent_ids", [])),
                "teams": len(resources.get("team_ids", [])),
            },
            "task_count": sum(len(phase.get("tasks", [])) for phase in resolved_phases),
            "phase_count": len(resolved_phases),
        }


# Singleton instance
_template_instantiation_service: Optional[TemplateInstantiationService] = None


def get_template_instantiation_service() -> TemplateInstantiationService:
    """Get or create the template instantiation service singleton."""
    global _template_instantiation_service
    if _template_instantiation_service is None:
        _template_instantiation_service = TemplateInstantiationService()
    return _template_instantiation_service
