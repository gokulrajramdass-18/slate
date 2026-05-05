"""
Template Execution domain model.
"""

import json
import uuid
from datetime import datetime
from typing import ClassVar, List, Optional, Dict, Any

from open_notebook.database.repository import repo_create, repo_query, repo_update
from open_notebook.domain.base import ObjectModel


class TemplateExecution(ObjectModel):
    """
    Track template execution with results stored in workspace folders.
    """

    _table_name: ClassVar[str] = "template_executions"
    _exclude_fields: ClassVar[List[str]] = ["created", "updated"]  # Exclude base class fields

    user_id: str
    template_id: str
    target_workspace_id: Optional[str] = None  # Nullable to allow workspace deletion
    folder_id: Optional[str] = None
    parameters: Optional[str] = None  # JSON
    result_note_id: Optional[str] = None
    status: str = "pending"  # pending, running, completed, failed
    error: Optional[str] = None
    current_phase: Optional[str] = None
    progress: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None

    # Override timestamp field names to match table schema
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        """Pydantic configuration."""
        from_attributes = True
        arbitrary_types_allowed = True

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

        # Convert datetime objects to ISO strings for storage
        for field in ['started_at', 'completed_at', 'created_at', 'updated_at']:
            if field in data and isinstance(data[field], datetime):
                data[field] = data[field].isoformat()

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
            # Remove created_at from update (shouldn't be changed)
            data.pop("created_at", None)

            # Double-check: remove base class fields again
            data.pop('created', None)
            data.pop('updated', None)

            await repo_update(self._table_name, record_id, data)

        return self.id

    def get_parameters(self) -> Dict[str, Any]:
        """Parse parameters JSON."""
        if not self.parameters:
            return {}
        try:
            return json.loads(self.parameters)
        except (json.JSONDecodeError, TypeError):
            return {}

    async def update_progress(self, phase: str, progress: float):
        """Update execution progress."""
        self.current_phase = phase
        self.progress = progress
        await self.save()

    @classmethod
    async def get_by_template(
        cls,
        template_id: str,
        limit: int = 50,
        status: Optional[str] = None
    ) -> List["TemplateExecution"]:
        """Get execution history for a template."""
        if status:
            sql = """
                SELECT * FROM template_executions
                WHERE template_id = :template_id AND status = :status
                ORDER BY created_at DESC
                LIMIT :limit
            """
            results = await repo_query(sql, {
                "template_id": template_id,
                "status": status,
                "limit": limit
            })
        else:
            sql = """
                SELECT * FROM template_executions
                WHERE template_id = :template_id
                ORDER BY created_at DESC
                LIMIT :limit
            """
            results = await repo_query(sql, {"template_id": template_id, "limit": limit})

        return [cls(**dict(row)) for row in results]

    @classmethod
    async def cleanup_stuck_executions(cls, timeout_minutes: int = 30) -> int:
        """
        Mark executions that have been running for too long as failed.

        Args:
            timeout_minutes: Maximum time an execution can run before being marked as stuck

        Returns:
            Number of executions cleaned up
        """
        from open_notebook.database.repository import repo_execute

        sql = """
            UPDATE template_executions
            SET status = 'failed',
                error = 'Execution timed out after ' || :timeout || ' minutes',
                completed_at = CURRENT_TIMESTAMP,
                duration_ms = CAST((julianday(CURRENT_TIMESTAMP) - julianday(started_at)) * 86400000 AS INTEGER),
                updated_at = CURRENT_TIMESTAMP
            WHERE status = 'running'
              AND started_at IS NOT NULL
              AND (julianday(CURRENT_TIMESTAMP) - julianday(started_at)) * 1440 > :timeout
        """

        result = await repo_execute(sql, {"timeout": timeout_minutes})

        # Return number of rows affected (if available)
        return result if isinstance(result, int) else 0

    @classmethod
    async def get_by_workspace(
        cls,
        workspace_id: str,
        limit: int = 50
    ) -> List["TemplateExecution"]:
        """Get all executions for a workspace."""
        sql = """
            SELECT * FROM template_executions
            WHERE target_workspace_id = :workspace_id
            ORDER BY created_at DESC
            LIMIT :limit
        """
        results = await repo_query(sql, {"workspace_id": workspace_id, "limit": limit})
        return [cls(**dict(row)) for row in results]
