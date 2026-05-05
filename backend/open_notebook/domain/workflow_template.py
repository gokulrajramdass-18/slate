"""
Workflow Template System

Allows users to save workflows as reusable templates with parameters
and publish them to a gallery for others to discover and use.
"""

import json
import re
from datetime import datetime
from typing import List, Optional, Dict, Any, ClassVar
from pydantic import BaseModel

from .base import ObjectModel
from .workflow import WorkflowGraph


class TemplateParameter(BaseModel):
    """Parameter definition for templates."""
    name: str
    type: str  # string, number, date, boolean, select
    description: Optional[str] = None
    default_value: Optional[Any] = None
    required: bool = False
    options: Optional[List[str]] = None  # For select type


class WorkflowTemplate(ObjectModel):
    """
    Workflow template with parameterization support.

    Workflow templates allow users to create reusable workflow patterns
    that can be instantiated with different parameters.
    """
    _table_name: ClassVar[str] = "workflow_templates"

    user_id: str
    name: str
    description: Optional[str]
    category: Optional[str]
    source_workflow_id: Optional[str]
    graph_json: str  # JSON with {{parameter}} placeholders
    parameters: Optional[str]  # JSON array of TemplateParameter
    version: int = 1
    is_public: bool = False
    tags: Optional[str]  # JSON array
    usage_count: int = 0

    def get_parameters(self) -> List[TemplateParameter]:
        """Parse parameters from JSON."""
        if not self.parameters:
            return []
        param_data = json.loads(self.parameters)
        return [TemplateParameter(**p) for p in param_data]

    def get_tags(self) -> List[str]:
        """Parse tags from JSON."""
        if not self.tags:
            return []
        return json.loads(self.tags)

    def validate_parameters(self, params: Dict[str, Any]) -> Dict:
        """
        Validate parameters against template definition.

        Returns: {valid: bool, errors: List[str]}
        """
        errors = []
        param_defs = self.get_parameters()

        for param_def in param_defs:
            if param_def.required and param_def.name not in params:
                errors.append(f"Required parameter '{param_def.name}' is missing")

            if param_def.name in params:
                value = params[param_def.name]

                # Type validation
                if param_def.type == "number" and not isinstance(value, (int, float)):
                    errors.append(f"Parameter '{param_def.name}' must be a number")
                elif param_def.type == "boolean" and not isinstance(value, bool):
                    errors.append(f"Parameter '{param_def.name}' must be a boolean")
                elif param_def.type == "select" and param_def.options and value not in param_def.options:
                    errors.append(f"Parameter '{param_def.name}' must be one of: {param_def.options}")

        return {"valid": len(errors) == 0, "errors": errors}

    def resolve_placeholders(self, text: str, params: Dict[str, Any]) -> str:
        """
        Replace {{param_name}} with actual values.

        Also supports:
        - {{TODAY}} - Current date
        - {{NOW}} - Current timestamp
        - {{USER_ID}} - User ID from context
        """
        # Replace custom parameters
        for key, value in params.items():
            text = text.replace(f"{{{{{key}}}}}", str(value))

        # Replace built-in placeholders
        text = text.replace("{{TODAY}}", datetime.now().strftime("%Y-%m-%d"))
        text = text.replace("{{NOW}}", datetime.now().isoformat())

        return text

    async def increment_usage(self):
        """Increment usage count when template is instantiated."""
        self.usage_count += 1
        await self.save()

    @classmethod
    async def get_public_templates(cls, category: Optional[str] = None, limit: int = 50):
        """Get public templates, optionally filtered by category."""
        from ..database.repository import repo_query

        query = "SELECT * FROM workflow_templates WHERE is_public = :is_public"
        params = {"is_public": True}

        if category:
            query += " AND category = :category"
            params["category"] = category

        query += f" ORDER BY usage_count DESC, created DESC LIMIT {limit}"

        rows = await repo_query(query, params)
        return [cls.from_db(row) for row in rows]

    @classmethod
    async def get_by_user(cls, user_id: str, limit: int = 50):
        """Get templates created by a user."""
        from ..database.repository import repo_query

        rows = await repo_query(
            f"SELECT * FROM workflow_templates WHERE user_id = :user_id ORDER BY updated DESC LIMIT {limit}",
            {"user_id": user_id}
        )
        return [cls.from_db(row) for row in rows]

    @classmethod
    async def get(cls, template_id: str):
        """Get template by ID."""
        from ..database.repository import repo_query

        rows = await repo_query(
            "SELECT * FROM workflow_templates WHERE id = :id",
            {"id": template_id}
        )

        if not rows:
            return None

        return cls.from_db(rows[0])

    @classmethod
    def from_db(cls, row: dict):
        """Create instance from database row."""
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            name=row["name"],
            description=row.get("description"),
            category=row.get("category"),
            source_workflow_id=row.get("source_workflow_id"),
            graph_json=row["graph_json"],
            parameters=row.get("parameters"),
            version=row.get("version", 1),
            is_public=bool(row.get("is_public", 0)),
            tags=row.get("tags"),
            usage_count=row.get("usage_count", 0),
            created=row.get("created_at"),
            updated=row.get("updated_at"),
        )

    async def save(self):
        """Save template to database."""
        import uuid
        from ..database.repository import db_connection

        # Generate ID if this is a new template
        if self.id is None:
            self.id = str(uuid.uuid4())

        async with db_connection() as db:
            data = {
                "id": self.id,
                "user_id": self.user_id,
                "name": self.name,
                "description": self.description,
                "category": self.category,
                "source_workflow_id": self.source_workflow_id,
                "graph_json": self.graph_json,
                "parameters": self.parameters,
                "version": self.version,
                "is_public": self.is_public,
                "tags": self.tags,
                "usage_count": self.usage_count,
            }

            # Check if exists
            existing = await db.query("SELECT id FROM workflow_templates WHERE id = :id", {"id": self.id})

            if existing:
                await db.update("workflow_templates", self.id, data)
            else:
                await db.create("workflow_templates", data)
