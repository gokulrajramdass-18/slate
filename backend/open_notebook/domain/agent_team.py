"""
Agent Team domain models.

Provides domain entities for agent team coordination:
- AgentTeam: A group of agents collaborating on a goal
- AgentInstance: An individual agent within a team
- AgentMessage: A message exchanged between agents
- AgentTask: A task assigned to an agent with dependency tracking
"""

import json
from datetime import datetime
from typing import Any, ClassVar, Dict, List, Optional

from pydantic import Field

from open_notebook.database.repository import repo_query, repo_execute
from open_notebook.domain.base import ObjectModel


class AgentTeam(ObjectModel):
    """
    An agent team is a coordinated group of agents working toward a shared goal.

    The team lifecycle: pending -> running -> completed | failed | cancelled
    """

    _table_name: ClassVar[str] = "agent_teams"

    name: str
    goal: Optional[str] = None
    status: str = "pending"
    notebook_id: Optional[str] = None
    session_id: Optional[str] = None
    config: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_by: Optional[str] = None

    # Multi-agent collaboration pattern. One of:
    # orchestrator_worker | sequential | parallel | review_critique | router | group_chat
    # See backend/open_notebook/agents/patterns/ for executor implementations.
    orchestration_pattern: Optional[str] = "orchestrator_worker"
    # JSON-encoded per-pattern config (orchestrator_agent_id, max_rounds, ...).
    pattern_config: Optional[str] = None

    def get_pattern_config(self) -> Dict[str, Any]:
        """Parse pattern_config JSON into a dict."""
        if not self.pattern_config:
            return {}
        try:
            return json.loads(self.pattern_config)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_pattern_config(self, config: Optional[Dict[str, Any]]) -> None:
        """Set pattern_config from a dict."""
        self.pattern_config = json.dumps(config) if config else None

    def get_config(self) -> Dict[str, Any]:
        """Parse config JSON into a dict."""
        if not self.config:
            return {}
        try:
            return json.loads(self.config)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_config(self, config: Dict[str, Any]) -> None:
        """Set config from a dict."""
        self.config = json.dumps(config) if config else None

    def get_result(self) -> Any:
        """Parse result JSON."""
        if not self.result:
            return None
        try:
            return json.loads(self.result)
        except (json.JSONDecodeError, TypeError):
            return self.result

    def set_result(self, result: Any) -> None:
        """Set result as JSON."""
        if result is None:
            self.result = None
        elif isinstance(result, str):
            self.result = result
        else:
            self.result = json.dumps(result)

    async def get_agents(self) -> List["AgentInstance"]:
        """Get all agent instances in this team."""
        if self.id is None:
            return []
        return await AgentInstance.get_all(
            filters={"team_id": self.id},
            order_by="created ASC",
        )

    async def get_tasks(self, status: Optional[str] = None) -> List["AgentTask"]:
        """
        Get tasks for this team, optionally filtered by status.

        Args:
            status: Optional status filter (pending, in_progress, completed, etc.)

        Returns:
            List of AgentTask instances
        """
        if self.id is None:
            return []
        filters: Dict[str, Any] = {"team_id": self.id}
        if status:
            filters["status"] = status
        return await AgentTask.get_all(filters=filters, order_by="priority DESC, created ASC")

    async def get_messages(self, limit: int = 100) -> List["AgentMessage"]:
        """Get recent messages in this team."""
        if self.id is None:
            return []
        sql = """
            SELECT * FROM agent_messages
            WHERE team_id = :team_id
            ORDER BY created ASC
            LIMIT :limit
        """
        results = await repo_query(sql, {"team_id": self.id, "limit": limit})
        return [AgentMessage(**row) for row in results]

    async def mark_running(self) -> None:
        """Transition team to running status."""
        self.status = "running"
        self.started_at = datetime.utcnow().isoformat()
        await self.save()

    async def mark_completed(self, result: Any = None) -> None:
        """Transition team to completed status."""
        self.status = "completed"
        self.completed_at = datetime.utcnow().isoformat()
        if result is not None:
            self.set_result(result)
        await self.save()

    async def mark_failed(self, error: str) -> None:
        """Transition team to failed status."""
        self.status = "failed"
        self.completed_at = datetime.utcnow().isoformat()
        self.error = error
        await self.save()

    @classmethod
    async def get_active(cls) -> List["AgentTeam"]:
        """Get all currently running teams."""
        return await cls.get_all(filters={"status": "running"}, order_by="started_at ASC")


class AgentInstance(ObjectModel):
    """
    An individual agent within a team.

    Each agent has a role (planner, researcher, analyst, synthesizer, etc.)
    and runs with a specific LLM model.

    Supports both local and remote agents via A2A protocol:
    - Local agents: is_remote=False, executed directly via LangGraph
    - Remote agents: is_remote=True, executed via A2A protocol
    """

    _table_name: ClassVar[str] = "agent_instances"

    team_id: str
    role: str
    name: str
    status: str = "idle"
    model_name: Optional[str] = None
    model_override: Optional[str] = None
    system_prompt: Optional[str] = None
    config: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    tool_ids: Optional[str] = None
    last_active: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    # A2A protocol support
    is_remote: bool = False
    remote_agent_id: Optional[str] = None
    a2a_endpoint_url: Optional[str] = None

    # Reference to the reusable standalone agent this instance was hydrated from
    # (introduced by migration 119). Nullable for legacy rows.
    standalone_agent_id: Optional[str] = None
    # Position in the team — drives sequential pattern hand-off order.
    order_index: Optional[int] = 0

    def get_config(self) -> Dict[str, Any]:
        """Parse config JSON."""
        if not self.config:
            return {}
        try:
            return json.loads(self.config)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_config(self, config: Dict[str, Any]) -> None:
        """Set config from dict."""
        self.config = json.dumps(config) if config else None

    def get_result(self) -> Any:
        """Parse result JSON."""
        if not self.result:
            return None
        try:
            return json.loads(self.result)
        except (json.JSONDecodeError, TypeError):
            return self.result

    def set_result(self, result: Any) -> None:
        """Set result as JSON."""
        if result is None:
            self.result = None
        elif isinstance(result, str):
            self.result = result
        else:
            self.result = json.dumps(result)

    async def mark_busy(self) -> None:
        """Transition to busy status."""
        self.status = "busy"
        self.started_at = datetime.utcnow().isoformat()
        await self.save()

    async def mark_completed(self, result: Any = None) -> None:
        """Transition to completed status."""
        self.status = "completed"
        self.completed_at = datetime.utcnow().isoformat()
        if result is not None:
            self.set_result(result)
        await self.save()

    async def mark_failed(self, error: str) -> None:
        """Transition to failed status."""
        self.status = "failed"
        self.completed_at = datetime.utcnow().isoformat()
        self.error = error
        await self.save()

    async def send_message(
        self,
        content: str,
        recipient_id: Optional[str] = None,
        message_type: str = "chat",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "AgentMessage":
        """
        Send a message from this agent.

        Args:
            content: Message text
            recipient_id: Target agent ID, or None for broadcast
            message_type: Message type (chat, task_assign, task_result, error, control)
            metadata: Optional extra data

        Returns:
            Created AgentMessage
        """
        msg = AgentMessage(
            team_id=self.team_id,
            sender_id=self.id,
            recipient_id=recipient_id,
            message_type=message_type,
            content=content,
            metadata=json.dumps(metadata) if metadata else None,
        )
        await msg.save()
        return msg

    async def get_inbox(self, since: Optional[str] = None) -> List["AgentMessage"]:
        """
        Get messages directed to this agent (or broadcast).

        Args:
            since: ISO timestamp to fetch only newer messages

        Returns:
            List of AgentMessage instances
        """
        if self.id is None:
            return []
        sql = """
            SELECT * FROM agent_messages
            WHERE team_id = :team_id
              AND (recipient_id = :agent_id OR recipient_id IS NULL)
              AND sender_id != :agent_id
        """
        params: Dict[str, Any] = {"team_id": self.team_id, "agent_id": self.id}
        if since:
            sql += " AND created > :since"
            params["since"] = since
        sql += " ORDER BY created ASC"
        results = await repo_query(sql, params)
        return [AgentMessage(**row) for row in results]


class AgentMessage(ObjectModel):
    """
    A message exchanged between agents in a team.

    Message types:
    - chat: General communication
    - task_assign: Task assignment notification
    - task_result: Result of a completed task
    - error: Error notification
    - control: Control commands (pause, resume, cancel)
    """

    _table_name: ClassVar[str] = "agent_messages"
    _exclude_fields: ClassVar[List[str]] = ["updated"]

    team_id: str
    sender_id: str
    recipient_id: Optional[str] = None
    message_type: str = "chat"
    content: str
    metadata: Optional[str] = None

    def get_metadata(self) -> Dict[str, Any]:
        """Parse metadata JSON."""
        if not self.metadata:
            return {}
        try:
            return json.loads(self.metadata)
        except (json.JSONDecodeError, TypeError):
            return {}


class AgentTask(ObjectModel):
    """
    A task assigned to an agent within a team.

    Supports dependency resolution: a task is blocked until all
    tasks in its depends_on list are completed.
    """

    _table_name: ClassVar[str] = "agent_tasks"

    team_id: str
    assignee_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    status: str = "pending"
    priority: int = 0
    result: Optional[str] = None
    error: Optional[str] = None
    depends_on: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def get_dependency_ids(self) -> List[str]:
        """Get list of task IDs this task depends on."""
        if not self.depends_on:
            return []
        try:
            deps = json.loads(self.depends_on)
            return deps if isinstance(deps, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_dependency_ids(self, task_ids: List[str]) -> None:
        """Set dependency task IDs."""
        self.depends_on = json.dumps(task_ids) if task_ids else None

    def get_result(self) -> Any:
        """Parse result JSON."""
        if not self.result:
            return None
        try:
            return json.loads(self.result)
        except (json.JSONDecodeError, TypeError):
            return self.result

    def set_result(self, result: Any) -> None:
        """Set result as JSON."""
        if result is None:
            self.result = None
        elif isinstance(result, str):
            self.result = result
        else:
            self.result = json.dumps(result)

    async def is_blocked(self) -> bool:
        """
        Check if this task is blocked by incomplete dependencies.

        Returns:
            True if any dependency task is not completed
        """
        dep_ids = self.get_dependency_ids()
        if not dep_ids:
            return False

        placeholders = ", ".join([f":dep_{i}" for i in range(len(dep_ids))])
        params = {f"dep_{i}": dep_id for i, dep_id in enumerate(dep_ids)}
        sql = f"""
            SELECT COUNT(*) as count FROM agent_tasks
            WHERE id IN ({placeholders})
              AND status != 'completed'
        """
        results = await repo_query(sql, params)
        return results[0]["count"] > 0 if results else False

    async def assign(self, agent_id: str) -> None:
        """Assign this task to an agent."""
        self.assignee_id = agent_id
        self.status = "in_progress"
        self.started_at = datetime.utcnow().isoformat()
        await self.save()

    async def mark_completed(self, result: Any = None) -> None:
        """Mark task as completed."""
        self.status = "completed"
        self.completed_at = datetime.utcnow().isoformat()
        if result is not None:
            self.set_result(result)
        await self.save()

    async def mark_failed(self, error: str) -> None:
        """Mark task as failed."""
        self.status = "failed"
        self.completed_at = datetime.utcnow().isoformat()
        self.error = error
        await self.save()

    @classmethod
    async def get_ready_tasks(cls, team_id: str) -> List["AgentTask"]:
        """
        Get tasks that are ready to execute (pending + unblocked).

        This fetches all pending tasks and checks each for unresolved dependencies.

        Args:
            team_id: Team ID

        Returns:
            List of tasks ready to be assigned
        """
        pending = await cls.get_all(
            filters={"team_id": team_id, "status": "pending"},
            order_by="priority DESC, created ASC",
        )
        ready = []
        for task in pending:
            if not await task.is_blocked():
                ready.append(task)
        return ready
