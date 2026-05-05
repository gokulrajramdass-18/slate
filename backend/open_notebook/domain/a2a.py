"""
A2A (Agent-to-Agent) Protocol Domain Models

Provides domain entities for A2A protocol integration:
- A2ARemoteAgent: Remote A2A agent registry
- A2ATask: Task lifecycle tracking
- A2AAgentCredential: Authentication credentials for remote agents
- A2ASkillMapping: Mapping between remote and local skills
- A2AExecutionMetric: Performance and reliability metrics
"""

import json
from datetime import datetime
from typing import Any, ClassVar, Dict, List, Optional

from pydantic import Field

from open_notebook.database.repository import repo_query, repo_execute
from open_notebook.domain.base import ObjectModel

# Import A2A SDK types
try:
    from a2a.types import (
        AgentCard,
        AgentSkill,
        Message,
        TaskStatus,
        Artifact,
    )
    A2A_SDK_AVAILABLE = True
except ImportError:
    # Fallback if A2A SDK not installed
    A2A_SDK_AVAILABLE = False
    AgentCard = dict  # type: ignore
    AgentSkill = dict  # type: ignore
    Message = dict  # type: ignore
    TaskStatus = dict  # type: ignore
    Artifact = dict  # type: ignore


class A2ARemoteAgent(ObjectModel):
    """
    Remote A2A agent that has been discovered and imported.

    Stores the agent's AgentCard and provides methods for syncing and execution.
    """

    _table_name: ClassVar[str] = "a2a_agent_registry"

    name: str
    card_url: str
    agent_card: str  # JSON string
    transport: str = "JSONRPC"
    endpoint_url: str
    security_schemes: Optional[str] = None  # JSON string
    available_skills: Optional[str] = None  # JSON array string
    last_synced: Optional[str] = None
    enabled: bool = True
    metadata: Optional[str] = None  # JSON string

    def get_agent_card(self) -> Dict[str, Any]:
        """Parse AgentCard JSON."""
        if not self.agent_card:
            return {}
        try:
            return json.loads(self.agent_card)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_agent_card(self, card: Dict[str, Any]) -> None:
        """Set AgentCard from dict."""
        self.agent_card = json.dumps(card) if card else "{}"

    def get_security_schemes(self) -> Dict[str, Any]:
        """Parse security schemes JSON."""
        if not self.security_schemes:
            return {}
        try:
            return json.loads(self.security_schemes)
        except (json.JSONDecodeError, TypeError):
            return {}

    def get_available_skills(self) -> List[str]:
        """Parse available skills JSON array."""
        if not self.available_skills:
            return []
        try:
            result = json.loads(self.available_skills)
            return result if isinstance(result, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_available_skills(self, skills: List[str]) -> None:
        """Set available skills from list."""
        self.available_skills = json.dumps(skills) if skills else "[]"

    def get_metadata(self) -> Dict[str, Any]:
        """Parse metadata JSON."""
        if not self.metadata:
            return {}
        try:
            return json.loads(self.metadata)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_metadata(self, metadata: Dict[str, Any]) -> None:
        """Set metadata from dict."""
        self.metadata = json.dumps(metadata) if metadata else None

    async def update_last_synced(self) -> None:
        """Update last_synced timestamp to now."""
        self.last_synced = datetime.utcnow().isoformat()
        await self.save()

    @classmethod
    async def get_by_card_url(cls, card_url: str) -> Optional["A2ARemoteAgent"]:
        """Get agent by card URL."""
        agents = await cls.get_all(filters={"card_url": card_url})
        return agents[0] if agents else None

    @classmethod
    async def get_enabled(cls) -> List["A2ARemoteAgent"]:
        """Get all enabled remote agents."""
        return await cls.get_all(filters={"enabled": True}, order_by="name ASC")


class A2ATask(ObjectModel):
    """
    A2A task execution tracking.

    Tracks both outgoing tasks (calling remote agents) and incoming tasks
    (remote agents calling us).

    Note: This table doesn't have an 'updated' column, only 'created'.
    """

    _table_name: ClassVar[str] = "a2a_task_store"
    _exclude_fields: ClassVar[List[str]] = ["updated"]  # Table doesn't have updated column

    context_id: str
    agent_id: Optional[str] = None
    skill_id: Optional[str] = None
    kind: str = "task"
    direction: str  # 'outgoing' or 'incoming'

    # TaskStatus fields
    state: str  # queued, running, auth-required, completed, canceled, rejected, failed
    progress: Optional[float] = None
    message: Optional[str] = None

    # Content
    history: Optional[str] = None  # JSON
    artifacts: Optional[str] = None  # JSON
    task_metadata: Optional[str] = None  # JSON

    # Timestamps
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def get_history(self) -> List[Dict[str, Any]]:
        """Parse history JSON array."""
        if not self.history:
            return []
        try:
            result = json.loads(self.history)
            return result if isinstance(result, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_history(self, history: List[Dict[str, Any]]) -> None:
        """Set history from list."""
        self.history = json.dumps(history) if history else None

    def get_artifacts(self) -> List[Dict[str, Any]]:
        """Parse artifacts JSON array."""
        if not self.artifacts:
            return []
        try:
            result = json.loads(self.artifacts)
            return result if isinstance(result, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_artifacts(self, artifacts: List[Dict[str, Any]]) -> None:
        """Set artifacts from list."""
        self.artifacts = json.dumps(artifacts) if artifacts else None

    def get_task_metadata(self) -> Dict[str, Any]:
        """Parse task metadata JSON."""
        if not self.task_metadata:
            return {}
        try:
            return json.loads(self.task_metadata)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_task_metadata(self, metadata: Dict[str, Any]) -> None:
        """Set task metadata from dict."""
        self.task_metadata = json.dumps(metadata) if metadata else None

    def is_terminal(self) -> bool:
        """Check if task is in terminal state."""
        return self.state in ["completed", "canceled", "rejected", "failed"]

    def is_success(self) -> bool:
        """Check if task completed successfully."""
        return self.state == "completed"

    async def mark_running(self) -> None:
        """Mark task as running."""
        self.state = "running"
        if not self.started_at:
            self.started_at = datetime.utcnow().isoformat()
        await self.save()

    async def mark_completed(self, artifacts: Optional[List[Dict[str, Any]]] = None) -> None:
        """Mark task as completed."""
        self.state = "completed"
        self.completed_at = datetime.utcnow().isoformat()
        if artifacts:
            self.set_artifacts(artifacts)
        await self.save()

    async def mark_failed(self, error_message: str) -> None:
        """Mark task as failed."""
        self.state = "failed"
        self.message = error_message
        self.completed_at = datetime.utcnow().isoformat()
        await self.save()

    async def update_progress(self, progress: float, message: Optional[str] = None) -> None:
        """Update task progress."""
        self.progress = max(0.0, min(1.0, progress))
        if message:
            self.message = message
        await self.save()

    @classmethod
    async def get_by_context(cls, context_id: str) -> List["A2ATask"]:
        """Get all tasks for a context."""
        return await cls.get_all(
            filters={"context_id": context_id},
            order_by="created ASC"
        )

    @classmethod
    async def get_active(cls) -> List["A2ATask"]:
        """Get all active (non-terminal) tasks."""
        sql = """
            SELECT * FROM a2a_task_store
            WHERE state IN ('queued', 'running', 'auth-required')
            ORDER BY created ASC
        """
        results = await repo_query(sql, {})
        return [cls(**row) for row in results]


class A2AAgentCredential(ObjectModel):
    """
    Authentication credentials for remote A2A agents.

    Stores encrypted credentials for agents requiring authentication.
    """

    _table_name: ClassVar[str] = "a2a_agent_credentials"

    agent_id: str
    credential_type: str  # 'apiKey', 'bearer', 'oauth2', 'basic'
    credential_data: str  # JSON (encrypted)
    expires_at: Optional[str] = None

    def get_credential_data(self) -> Dict[str, Any]:
        """Parse credential data JSON."""
        if not self.credential_data:
            return {}
        try:
            # TODO: Decrypt before parsing
            return json.loads(self.credential_data)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_credential_data(self, data: Dict[str, Any]) -> None:
        """Set credential data from dict."""
        # TODO: Encrypt before storing
        self.credential_data = json.dumps(data) if data else "{}"

    def is_expired(self) -> bool:
        """Check if credential is expired."""
        if not self.expires_at:
            return False
        try:
            expiry = datetime.fromisoformat(self.expires_at)
            return datetime.utcnow() > expiry
        except (ValueError, TypeError):
            return False

    @classmethod
    async def get_by_agent(cls, agent_id: str) -> Optional["A2AAgentCredential"]:
        """Get credential for agent."""
        creds = await cls.get_all(filters={"agent_id": agent_id})
        return creds[0] if creds else None


class A2ASkillMapping(ObjectModel):
    """
    Mapping between remote A2A agent skills and local skills.

    Tracks which local skill IDs correspond to remote agent skills.
    """

    _table_name: ClassVar[str] = "a2a_skill_mappings"

    remote_agent_id: str
    remote_skill_id: str
    local_skill_id: str
    skill_name: str
    skill_description: Optional[str] = None
    skill_tags: Optional[str] = None  # JSON array
    input_modes: Optional[str] = None  # JSON array
    output_modes: Optional[str] = None  # JSON array
    enabled: bool = True

    def get_skill_tags(self) -> List[str]:
        """Parse skill tags JSON array."""
        if not self.skill_tags:
            return []
        try:
            result = json.loads(self.skill_tags)
            return result if isinstance(result, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_skill_tags(self, tags: List[str]) -> None:
        """Set skill tags from list."""
        self.skill_tags = json.dumps(tags) if tags else None

    def get_input_modes(self) -> List[str]:
        """Parse input modes JSON array."""
        if not self.input_modes:
            return []
        try:
            result = json.loads(self.input_modes)
            return result if isinstance(result, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def get_output_modes(self) -> List[str]:
        """Parse output modes JSON array."""
        if not self.output_modes:
            return []
        try:
            result = json.loads(self.output_modes)
            return result if isinstance(result, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    @classmethod
    async def get_by_remote_agent(cls, agent_id: str) -> List["A2ASkillMapping"]:
        """Get all skill mappings for a remote agent."""
        return await cls.get_all(
            filters={"remote_agent_id": agent_id},
            order_by="skill_name ASC"
        )

    @classmethod
    async def get_by_local_skill(cls, skill_id: str) -> Optional["A2ASkillMapping"]:
        """Get mapping for a local skill."""
        mappings = await cls.get_all(filters={"local_skill_id": skill_id})
        return mappings[0] if mappings else None


class A2AExecutionMetric(ObjectModel):
    """
    Performance and reliability metrics for A2A agent executions.

    Tracks latency, success rates, and error patterns.

    Note: This table uses 'timestamp' instead of 'created' and has no 'updated' column.
    """

    _table_name: ClassVar[str] = "a2a_execution_metrics"
    _exclude_fields: ClassVar[List[str]] = ["created", "updated"]  # Table uses timestamp instead

    agent_id: str
    skill_id: Optional[str] = None
    task_id: str

    # Performance
    latency_ms: Optional[float] = None
    network_latency_ms: Optional[float] = None

    # Result
    success: bool
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    # Context
    retry_count: int = 0
    timestamp: Optional[str] = Field(default_factory=lambda: datetime.utcnow().isoformat())

    @classmethod
    async def record_execution(
        cls,
        agent_id: str,
        task_id: str,
        success: bool,
        latency_ms: Optional[float] = None,
        skill_id: Optional[str] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        retry_count: int = 0,
    ) -> "A2AExecutionMetric":
        """Record an execution metric."""
        metric = cls(
            agent_id=agent_id,
            task_id=task_id,
            skill_id=skill_id,
            latency_ms=latency_ms,
            success=success,
            error_type=error_type,
            error_message=error_message,
            retry_count=retry_count,
        )
        await metric.save()
        return metric

    @classmethod
    async def get_agent_stats(cls, agent_id: str, days: int = 7) -> Dict[str, Any]:
        """Get aggregated statistics for an agent."""
        from datetime import timedelta

        since = (datetime.utcnow() - timedelta(days=days)).isoformat()

        sql = """
            SELECT
                COUNT(*) as total_executions,
                SUM(success) as successful_executions,
                AVG(latency_ms) as avg_latency_ms,
                MIN(latency_ms) as min_latency_ms,
                MAX(latency_ms) as max_latency_ms,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed_executions
            FROM a2a_execution_metrics
            WHERE agent_id = :agent_id
                AND timestamp >= :since
        """

        results = await repo_query(sql, {"agent_id": agent_id, "since": since})

        if not results or not results[0]["total_executions"]:
            return {
                "total_executions": 0,
                "success_rate": 0.0,
                "avg_latency_ms": 0.0,
                "min_latency_ms": 0.0,
                "max_latency_ms": 0.0,
            }

        row = results[0]
        total = row["total_executions"]
        successful = row["successful_executions"] or 0

        return {
            "total_executions": total,
            "successful_executions": successful,
            "failed_executions": row["failed_executions"] or 0,
            "success_rate": (successful / total) if total > 0 else 0.0,
            "avg_latency_ms": row["avg_latency_ms"] or 0.0,
            "min_latency_ms": row["min_latency_ms"] or 0.0,
            "max_latency_ms": row["max_latency_ms"] or 0.0,
        }
