"""
Guided Workspace domain models.

Includes GuidedWorkspaceSession, WorkspacePlan, and WorkspacePlanTask entities
for the AI-powered workspace creation wizard.
"""

import json
import uuid
from datetime import datetime
from typing import Any, ClassVar, Dict, List, Optional, Union

from pydantic import Field, field_validator

from open_notebook.database.repository import (
    repo_create,
    repo_delete,
    repo_query,
    repo_update,
)
from open_notebook.domain.base import ObjectModel


class GuidedWorkspaceSession(ObjectModel):
    """
    Temporary session for the guided workspace creation wizard.

    Tracks the user's progress through goal analysis, clarification questions,
    resource selection, and plan generation. Sessions expire after 24 hours.
    """

    _table_name: ClassVar[str] = "guided_workspace_sessions"

    user_id: str
    goal: str
    current_step: Optional[str] = None
    analysis: Optional[str] = None
    clarifications: Optional[str] = None
    selected_resources: Optional[str] = None
    generated_plan: Optional[str] = None
    status: str = "active"
    expires_at: Optional[datetime] = None

    @field_validator("analysis", "clarifications", "selected_resources", "generated_plan", mode="before")
    @classmethod
    def ensure_json_string(cls, v: Any) -> Optional[str]:
        """Convert dicts/lists to JSON strings for storage."""
        if v is None:
            return None
        if isinstance(v, (dict, list)):
            return json.dumps(v)
        return v

    def parse_analysis(self) -> Dict:
        """Parse the analysis JSON string to a dictionary.

        Returns:
            Parsed analysis dict, or empty dict if not set or invalid.
        """
        if not self.analysis:
            return {}
        if isinstance(self.analysis, dict):
            return self.analysis
        try:
            return json.loads(self.analysis)
        except (json.JSONDecodeError, TypeError):
            return {}

    def get_selected_resources(self) -> Dict:
        """Parse the selected_resources JSON string to a dictionary.

        Returns:
            Parsed resources dict, or empty dict if not set or invalid.
        """
        if not self.selected_resources:
            return {}
        if isinstance(self.selected_resources, dict):
            return self.selected_resources
        try:
            return json.loads(self.selected_resources)
        except (json.JSONDecodeError, TypeError):
            return {}

    def get_clarifications(self) -> Dict:
        """Parse the clarifications JSON string to a dictionary.

        Returns:
            Parsed clarifications dict, or empty dict if not set or invalid.
        """
        if not self.clarifications:
            return {}
        if isinstance(self.clarifications, dict):
            return self.clarifications
        try:
            return json.loads(self.clarifications)
        except (json.JSONDecodeError, TypeError):
            return {}

    def get_generated_plan(self) -> Dict:
        """Parse the generated_plan JSON string to a dictionary.

        Returns:
            Parsed plan dict, or empty dict if not set or invalid.
        """
        if not self.generated_plan:
            return {}
        if isinstance(self.generated_plan, dict):
            return self.generated_plan
        try:
            return json.loads(self.generated_plan)
        except (json.JSONDecodeError, TypeError):
            return {}

    def is_expired(self) -> bool:
        """Check if this session has expired.

        Returns:
            True if the session has passed its expiration time.
        """
        if self.expires_at is None:
            return False
        now = datetime.utcnow()
        if isinstance(self.expires_at, str):
            try:
                expires = datetime.fromisoformat(self.expires_at)
            except ValueError:
                return False
        else:
            expires = self.expires_at
        return now > expires

    @classmethod
    async def cleanup_expired(cls) -> int:
        """Delete all expired sessions.

        Returns:
            Number of sessions deleted.
        """
        now = datetime.utcnow().isoformat()
        # Get expired session IDs first
        sql = """
            SELECT id FROM guided_workspace_sessions
            WHERE expires_at IS NOT NULL AND expires_at < :now
        """
        results = await repo_query(sql, {"now": now})

        for row in results:
            await repo_delete("guided_workspace_sessions", row["id"])

        return len(results)

    async def save(self) -> str:
        """Save the session, serializing JSON fields."""
        now = datetime.utcnow()
        data = self.model_dump(exclude_none=True)

        # Ensure JSON fields are strings
        for field in ("analysis", "clarifications", "selected_resources", "generated_plan"):
            if field in data and isinstance(data[field], (dict, list)):
                data[field] = json.dumps(data[field])

        if self.id is None:
            self.id = str(uuid.uuid4())
            self.created = now
            self.updated = now
            data["id"] = self.id
            data["created"] = self.created
            data["updated"] = self.updated
            await repo_create(self._table_name, data)
        else:
            self.updated = now
            data["updated"] = self.updated
            record_id = data.pop("id")
            await repo_update(self._table_name, record_id, data)

        return self.id


class WorkspacePlanTask(ObjectModel):
    """
    Individual task within a workspace plan.

    Represents a single unit of work assigned to an agent, with dependencies,
    required tools/sources, and result tracking.
    """

    _table_name: ClassVar[str] = "workspace_plan_tasks"

    plan_id: str
    phase_name: str
    name: str
    description: Optional[str] = None
    assigned_agent_id: Optional[str] = None
    status: str = "pending"
    estimated_duration: Optional[int] = None
    actual_duration: Optional[int] = None
    dependencies: Optional[str] = None
    required_tools: Optional[str] = None
    required_sources: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @field_validator("dependencies", "required_tools", "required_sources", "result", mode="before")
    @classmethod
    def ensure_json_string_task(cls, v: Any) -> Optional[str]:
        """Convert dicts/lists to JSON strings for storage."""
        if v is None:
            return None
        if isinstance(v, (dict, list)):
            return json.dumps(v)
        return v

    def _parse_json_field(self, value: Optional[str], default: Any = None) -> Any:
        """Parse a JSON string field safely."""
        if value is None:
            return default if default is not None else []
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default if default is not None else []

    def get_dependency_ids(self) -> List[str]:
        """Get the list of task IDs this task depends on.

        Returns:
            List of task ID strings.
        """
        return self._parse_json_field(self.dependencies, [])

    def get_required_tools(self) -> List[str]:
        """Get the list of required tool IDs.

        Returns:
            List of tool ID strings.
        """
        return self._parse_json_field(self.required_tools, [])

    def get_required_sources(self) -> List[str]:
        """Get the list of required source IDs.

        Returns:
            List of source ID strings.
        """
        return self._parse_json_field(self.required_sources, [])

    def get_result(self) -> Dict:
        """Parse the result JSON.

        Returns:
            Parsed result dict, or empty dict if not set.
        """
        return self._parse_json_field(self.result, {})

    async def can_start(self) -> bool:
        """Check if all dependencies are met (completed).

        Returns:
            True if all dependency tasks are completed.
        """
        dep_ids = self.get_dependency_ids()
        if not dep_ids:
            return True

        placeholders = ", ".join(f":dep_{i}" for i in range(len(dep_ids)))
        params = {f"dep_{i}": dep_id for i, dep_id in enumerate(dep_ids)}

        sql = f"""
            SELECT COUNT(*) as count FROM workspace_plan_tasks
            WHERE id IN ({placeholders}) AND status != 'completed'
        """
        results = await repo_query(sql, params)
        return results[0]["count"] == 0 if results else True

    async def start(self) -> None:
        """Mark this task as in_progress and record the start time."""
        self.status = "in_progress"
        self.started_at = datetime.utcnow()
        await self.save()

    async def complete(self, result: Dict) -> None:
        """Mark this task as completed with the given result.

        Args:
            result: Dictionary containing the task output.
        """
        self.status = "completed"
        self.result = json.dumps(result)
        self.completed_at = datetime.utcnow()
        if self.started_at:
            started = self.started_at
            if isinstance(started, str):
                started = datetime.fromisoformat(started)
            delta = self.completed_at - started
            self.actual_duration = int(delta.total_seconds() / 60)
        await self.save()

    async def fail(self, error: str) -> None:
        """Mark this task as failed with an error message.

        Args:
            error: Description of what went wrong.
        """
        self.status = "failed"
        self.error = error
        self.completed_at = datetime.utcnow()
        await self.save()

    async def get_dependencies(self) -> List["WorkspacePlanTask"]:
        """Get the actual WorkspacePlanTask objects this task depends on.

        Returns:
            List of WorkspacePlanTask instances.
        """
        dep_ids = self.get_dependency_ids()
        if not dep_ids:
            return []

        tasks = []
        for dep_id in dep_ids:
            task = await WorkspacePlanTask.get(dep_id)
            if task is not None:
                tasks.append(task)
        return tasks

    async def save(self) -> str:
        """Save the task, serializing JSON fields."""
        now = datetime.utcnow()
        data = self.model_dump(exclude_none=True)

        # Ensure JSON fields are strings
        for field in ("dependencies", "required_tools", "required_sources", "result"):
            if field in data and isinstance(data[field], (dict, list)):
                data[field] = json.dumps(data[field])

        if self.id is None:
            self.id = str(uuid.uuid4())
            self.created = now
            self.updated = now
            data["id"] = self.id
            data["created"] = self.created
            data["updated"] = self.updated
            await repo_create(self._table_name, data)
        else:
            self.updated = now
            data["updated"] = self.updated
            record_id = data.pop("id")
            await repo_update(self._table_name, record_id, data)

        return self.id


class WorkspacePlan(ObjectModel):
    """
    Persisted workspace plan with phases, tasks, and collaboration graph.

    Links to a workspace (notebook) and tracks overall execution progress
    across multiple phases and tasks.
    """

    _table_name: ClassVar[str] = "workspace_plans"

    workspace_id: str
    goal: str
    phases: str  # JSON: array of phases
    collaboration_graph: Optional[str] = None
    status: str = "pending"
    progress: Optional[str] = None

    @field_validator("phases", mode="before")
    @classmethod
    def ensure_phases_string(cls, v: Any) -> str:
        """Convert phases list/dict to JSON string."""
        if isinstance(v, (dict, list)):
            return json.dumps(v)
        if v is None:
            return "[]"
        return v

    @field_validator("collaboration_graph", "progress", mode="before")
    @classmethod
    def ensure_json_string_plan(cls, v: Any) -> Optional[str]:
        """Convert dicts/lists to JSON strings for storage."""
        if v is None:
            return None
        if isinstance(v, (dict, list)):
            return json.dumps(v)
        return v

    def get_phases(self) -> List[Dict]:
        """Parse the phases JSON string.

        Returns:
            List of phase dictionaries.
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
        """Parse the collaboration_graph JSON string.

        Returns:
            Collaboration graph dict, or empty dict if not set.
        """
        if not self.collaboration_graph:
            return {}
        if isinstance(self.collaboration_graph, dict):
            return self.collaboration_graph
        try:
            return json.loads(self.collaboration_graph)
        except (json.JSONDecodeError, TypeError):
            return {}

    def get_progress(self) -> Dict:
        """Parse the progress JSON string.

        Returns:
            Progress dict, or empty dict if not set.
        """
        if not self.progress:
            return {}
        if isinstance(self.progress, dict):
            return self.progress
        try:
            return json.loads(self.progress)
        except (json.JSONDecodeError, TypeError):
            return {}

    async def get_tasks(self) -> List[WorkspacePlanTask]:
        """Get all tasks belonging to this plan.

        Returns:
            List of WorkspacePlanTask instances ordered by phase and creation time.
        """
        if self.id is None:
            return []

        sql = """
            SELECT * FROM workspace_plan_tasks
            WHERE plan_id = :plan_id
            ORDER BY phase_name, created
        """
        results = await repo_query(sql, {"plan_id": self.id})

        tasks = []
        for row in results:
            row_dict = dict(row)
            tasks.append(WorkspacePlanTask(**row_dict))
        return tasks

    async def get_phase_progress(self, phase_name: str) -> Dict:
        """Get progress statistics for a specific phase.

        Args:
            phase_name: Name of the phase to check.

        Returns:
            Dict with keys: total, pending, in_progress, completed, failed, skipped.
        """
        if self.id is None:
            return {"total": 0, "pending": 0, "in_progress": 0, "completed": 0, "failed": 0, "skipped": 0}

        sql = """
            SELECT status, COUNT(*) as count
            FROM workspace_plan_tasks
            WHERE plan_id = :plan_id AND phase_name = :phase_name
            GROUP BY status
        """
        results = await repo_query(sql, {"plan_id": self.id, "phase_name": phase_name})

        progress = {"total": 0, "pending": 0, "in_progress": 0, "completed": 0, "failed": 0, "skipped": 0}
        for row in results:
            status = row["status"]
            count = row["count"]
            if status in progress:
                progress[status] = count
            progress["total"] += count

        return progress

    async def get_overall_progress(self) -> Dict:
        """Get overall completion statistics across all phases.

        Returns:
            Dict with keys: total, pending, in_progress, completed, failed, skipped,
            completion_percentage.
        """
        if self.id is None:
            return {
                "total": 0, "pending": 0, "in_progress": 0, "completed": 0,
                "failed": 0, "skipped": 0, "completion_percentage": 0.0,
            }

        sql = """
            SELECT status, COUNT(*) as count
            FROM workspace_plan_tasks
            WHERE plan_id = :plan_id
            GROUP BY status
        """
        results = await repo_query(sql, {"plan_id": self.id})

        progress = {
            "total": 0, "pending": 0, "in_progress": 0, "completed": 0,
            "failed": 0, "skipped": 0, "completion_percentage": 0.0,
        }
        for row in results:
            status = row["status"]
            count = row["count"]
            if status in progress:
                progress[status] = count
            progress["total"] += count

        if progress["total"] > 0:
            progress["completion_percentage"] = round(
                (progress["completed"] / progress["total"]) * 100, 1
            )

        return progress

    async def save(self) -> str:
        """Save the plan, serializing JSON fields."""
        now = datetime.utcnow()
        data = self.model_dump(exclude_none=True)

        # Ensure JSON fields are strings
        for field in ("phases", "collaboration_graph", "progress"):
            if field in data and isinstance(data[field], (dict, list)):
                data[field] = json.dumps(data[field])

        if self.id is None:
            self.id = str(uuid.uuid4())
            self.created = now
            self.updated = now
            data["id"] = self.id
            data["created"] = self.created
            data["updated"] = self.updated
            await repo_create(self._table_name, data)
        else:
            self.updated = now
            data["updated"] = self.updated
            record_id = data.pop("id")
            await repo_update(self._table_name, record_id, data)

        return self.id
