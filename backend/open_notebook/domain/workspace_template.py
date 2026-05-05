"""
Workspace Template domain model.

Represents reusable workspace configurations with parameterization support
for scheduled orchestration and manual instantiation.
"""

import json
import re
import uuid
from datetime import datetime, timedelta
from typing import Any, ClassVar, Dict, List, Optional

from pydantic import field_validator

from open_notebook.database.repository import (
    repo_create,
    repo_delete,
    repo_query,
    repo_update,
)
from open_notebook.domain.base import ObjectModel


class WorkspaceTemplate(ObjectModel):
    """
    Reusable workspace template with parameterization.

    Templates define workspace structure (phases, tasks, agents, resources)
    that can be instantiated multiple times with different parameters.
    """

    _table_name: ClassVar[str] = "workspace_templates"
    _exclude_fields: ClassVar[List[str]] = ["created", "updated"]  # Exclude base class fields

    user_id: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    source_workspace_id: Optional[str] = None  # NEW: Remember source workspace

    # Template structure
    phases: str  # JSON: array of phase definitions
    collaboration_graph: Optional[str] = None  # JSON: agent coordination
    default_resources: Optional[str] = None  # JSON: {source_ids, tool_ids, agent_ids, team_ids}

    # Parameterization
    parameters: Optional[str] = None  # JSON: parameter definitions

    # Metadata
    version: int = 1
    is_public: bool = False
    tags: Optional[str] = None  # JSON: array of tags
    times_used: int = 0  # Match database column name

    # Override timestamp field names to match table schema
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        """Pydantic configuration."""
        from_attributes = True
        arbitrary_types_allowed = True

    @field_validator("phases", mode="before")
    @classmethod
    def ensure_phases_string(cls, v: Any) -> str:
        """Convert phases list to JSON string."""
        if isinstance(v, (dict, list)):
            return json.dumps(v)
        if v is None:
            return "[]"
        return v

    @field_validator("collaboration_graph", "default_resources", "parameters", "tags", mode="before")
    @classmethod
    def ensure_json_string(cls, v: Any) -> Optional[str]:
        """Convert dicts/lists to JSON strings for storage."""
        if v is None:
            return None
        if isinstance(v, (dict, list)):
            return json.dumps(v)
        return v

    async def save(self) -> str:
        """
        Save the model to the database.

        Override to use created_at/updated_at instead of created/updated.
        """
        if not self._table_name:
            raise ValueError(f"{self.__class__.__name__} must define _table_name")

        now = datetime.utcnow()

        # Build exclude set
        exclude_set = set(self._exclude_fields) if self._exclude_fields else set()

        # Convert model to dict
        data = self.model_dump(exclude_none=True, exclude=exclude_set)

        # Explicitly remove base class timestamp fields
        data.pop('created', None)
        data.pop('updated', None)

        # Ensure JSON fields are strings
        for field in ("phases", "collaboration_graph", "default_resources", "parameters", "tags"):
            if field in data and isinstance(data[field], (dict, list)):
                data[field] = json.dumps(data[field])

        if self.id is None:
            # Create new record
            self.id = str(uuid.uuid4())
            data["id"] = self.id
            self.created_at = now
            self.updated_at = now
            data["created_at"] = self.created_at.isoformat()
            data["updated_at"] = self.updated_at.isoformat()

            await repo_create(self._table_name, data)
        else:
            # Update existing record
            self.updated_at = now
            data["updated_at"] = self.updated_at.isoformat()

            # Remove id from update data
            record_id = data.pop("id")
            # Remove created_at from update
            data.pop("created_at", None)

            await repo_update(self._table_name, record_id, data)

        return self.id

    def get_phases(self) -> List[Dict]:
        """Parse phases JSON.

        Returns:
            List of phase dictionaries with tasks.
        """
        if not self.phases:
            return []
        if isinstance(self.phases, list):
            return self.phases
        try:
            return json.loads(self.phases)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_collaboration_graph(self) -> Dict:
        """Parse collaboration graph JSON.

        Returns:
            Collaboration graph dict or empty dict.
        """
        if not self.collaboration_graph:
            return {}
        if isinstance(self.collaboration_graph, dict):
            return self.collaboration_graph
        try:
            return json.loads(self.collaboration_graph)
        except (json.JSONDecodeError, TypeError):
            return {}

    def get_default_resources(self) -> Dict:
        """Parse default resources JSON.

        Returns:
            Resources dict with source_ids, tool_ids, agent_ids, team_ids.
        """
        if not self.default_resources:
            return {"source_ids": [], "tool_ids": [], "agent_ids": [], "team_ids": []}
        if isinstance(self.default_resources, dict):
            return self.default_resources
        try:
            return json.loads(self.default_resources)
        except (json.JSONDecodeError, TypeError):
            return {"source_ids": [], "tool_ids": [], "agent_ids": [], "team_ids": []}

    def get_parameters(self) -> List[Dict]:
        """Parse parameters JSON.

        Returns:
            List of parameter definitions.
        """
        if not self.parameters:
            return []
        if isinstance(self.parameters, list):
            return self.parameters
        try:
            return json.loads(self.parameters)
        except (json.JSONDecodeError, TypeError):
            return []

    def get_tags(self) -> List[str]:
        """Parse tags JSON.

        Returns:
            List of tag strings.
        """
        if not self.tags:
            return []
        if isinstance(self.tags, list):
            return self.tags
        try:
            return json.loads(self.tags)
        except (json.JSONDecodeError, TypeError):
            return []

    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate runtime parameters against template definition.

        Args:
            parameters: Runtime parameter values.

        Returns:
            Dict with 'valid' bool and 'errors' list.

        Raises:
            ValueError: If validation fails.
        """
        param_defs = self.get_parameters()
        errors = []

        # Check required parameters
        for param_def in param_defs:
            param_name = param_def.get("name")
            required = param_def.get("required", False)

            if required and param_name not in parameters:
                errors.append(f"Required parameter '{param_name}' is missing")

        # Check parameter types and options
        for param_name, param_value in parameters.items():
            # Find definition
            param_def = next((p for p in param_defs if p.get("name") == param_name), None)

            if not param_def:
                errors.append(f"Unknown parameter '{param_name}'")
                continue

            param_type = param_def.get("type", "string")
            options = param_def.get("options")

            # Type validation
            if param_type == "date" and not isinstance(param_value, str):
                errors.append(f"Parameter '{param_name}' must be a date string")
            elif param_type == "number" and not isinstance(param_value, (int, float)):
                errors.append(f"Parameter '{param_name}' must be a number")
            elif param_type == "boolean" and not isinstance(param_value, bool):
                errors.append(f"Parameter '{param_name}' must be a boolean")

            # Options validation
            if options and param_value not in options:
                errors.append(f"Parameter '{param_name}' must be one of: {', '.join(options)}")

        return {"valid": len(errors) == 0, "errors": errors}

    def resolve_placeholders(self, text: str, parameters: Dict[str, Any], context: Optional[Dict] = None) -> str:
        """Replace {{param_name}} placeholders with values.

        Supports:
        - {{param_name}} - user parameters
        - {{TODAY}} - current date (YYYY-MM-DD)
        - {{NOW}} - current datetime (ISO format)
        - {{WORKSPACE_ID}} - workspace ID from context
        - {{USER_ID}} - user ID from context

        Args:
            text: Text with placeholders.
            parameters: Runtime parameter values.
            context: Optional context with workspace_id, user_id.

        Returns:
            Text with placeholders resolved.
        """
        if not text:
            return text

        context = context or {}
        replacements = {**parameters}

        # Built-in placeholders
        replacements["TODAY"] = datetime.utcnow().strftime("%Y-%m-%d")
        replacements["NOW"] = datetime.utcnow().isoformat()
        replacements["WORKSPACE_ID"] = context.get("workspace_id", "")
        replacements["USER_ID"] = context.get("user_id", self.user_id)

        # Replace all {{placeholder}} patterns
        def replace_fn(match):
            key = match.group(1)
            return str(replacements.get(key, match.group(0)))

        return re.sub(r'\{\{(\w+)\}\}', replace_fn, text)

    async def clone_to_workspace(
        self,
        parameters: Dict[str, Any],
        user_id: str,
        workspace_name: str,
        workspace_id: Optional[str] = None
    ) -> str:
        """Instantiate template as new workspace with parameter substitution.

        Args:
            parameters: Runtime parameter values.
            user_id: User creating the workspace.
            workspace_name: Name for the new workspace.
            workspace_id: Optional workspace ID (generated if not provided).

        Returns:
            Workspace ID.

        Raises:
            ValueError: If parameter validation fails.
        """
        # Validate parameters
        validation = self.validate_parameters(parameters)
        if not validation["valid"]:
            raise ValueError(f"Parameter validation failed: {', '.join(validation['errors'])}")

        # Generate workspace ID if not provided
        if not workspace_id:
            workspace_id = str(uuid.uuid4())

        context = {"workspace_id": workspace_id, "user_id": user_id}

        # Clone phases with parameter substitution
        phases = self.get_phases()
        resolved_phases = []

        for phase in phases:
            resolved_phase = {
                "name": self.resolve_placeholders(phase.get("name", ""), parameters, context),
                "tasks": []
            }

            for task in phase.get("tasks", []):
                resolved_task = {
                    "name": self.resolve_placeholders(task.get("name", ""), parameters, context),
                    "description": self.resolve_placeholders(task.get("description", ""), parameters, context),
                    "assigned_agent_id": task.get("assigned_agent_id"),
                    "estimated_duration": task.get("estimated_duration"),
                    "dependencies": task.get("dependencies", []),
                    "required_tools": task.get("required_tools", []),
                    "required_sources": task.get("required_sources", []),
                }
                resolved_phase["tasks"].append(resolved_task)

            resolved_phases.append(resolved_phase)

        # Return cloned data (actual workspace creation handled by service layer)
        return workspace_id

    async def increment_usage(self) -> None:
        """Increment usage count."""
        self.times_used += 1
        await self.save()

    @classmethod
    async def get_public_templates(cls, category: Optional[str] = None, limit: int = 50) -> List["WorkspaceTemplate"]:
        """Get public templates.

        Args:
            category: Optional category filter.
            limit: Max results.

        Returns:
            List of public templates.
        """
        if category:
            sql = """
                SELECT * FROM workspace_templates
                WHERE is_public = 1 AND category = :category
                ORDER BY times_used DESC, created_at DESC
                LIMIT :limit
            """
            results = await repo_query(sql, {"category": category, "limit": limit})
        else:
            sql = """
                SELECT * FROM workspace_templates
                WHERE is_public = 1
                ORDER BY times_used DESC, created_at DESC
                LIMIT :limit
            """
            results = await repo_query(sql, {"limit": limit})

        templates = []
        for row in results:
            templates.append(cls(**dict(row)))
        return templates

    @classmethod
    async def get_by_user(cls, user_id: str, include_public: bool = False) -> List["WorkspaceTemplate"]:
        """Get templates for a user.

        Args:
            user_id: User ID.
            include_public: Include public templates.

        Returns:
            List of templates.
        """
        if include_public:
            sql = """
                SELECT * FROM workspace_templates
                WHERE user_id = :user_id OR is_public = 1
                ORDER BY created_at DESC
            """
        else:
            sql = """
                SELECT * FROM workspace_templates
                WHERE user_id = :user_id
                ORDER BY created_at DESC
            """

        results = await repo_query(sql, {"user_id": user_id})

        templates = []
        for row in results:
            templates.append(cls(**dict(row)))
        return templates

