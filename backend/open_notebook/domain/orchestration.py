"""
Domain Models for Autonomous Orchestration

Models for orchestration executions, events, resources, metrics, and configs.
"""

import json
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass

from open_notebook.domain.base import ObjectModel


class OrchestrationExecution(ObjectModel):
    """Orchestration execution record."""

    _table_name = "orchestration_executions"

    def __init__(
        self,
        id: str,
        user_id: str,
        goal: str,
        status: str,
        notebook_id: Optional[str] = None,
        orchestration_mode: Optional[str] = None,
        team_id: Optional[str] = None,
        complexity: Optional[str] = None,
        intent: Optional[str] = None,
        required_capabilities: Optional[List[str]] = None,
        execution_plan: Optional[Dict[str, Any]] = None,
        parallel_groups: Optional[List[List[str]]] = None,
        current_phase: Optional[str] = None,
        progress: float = 0.0,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        started_at: Optional[str] = None,
        completed_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        **kwargs
    ):
        """Initialize orchestration execution."""
        self.id = id
        self.user_id = user_id
        self.notebook_id = notebook_id
        self.goal = goal
        self.status = status
        self.orchestration_mode = orchestration_mode
        self.team_id = team_id
        self.complexity = complexity
        self.intent = intent
        self.required_capabilities = required_capabilities or []
        self.execution_plan = execution_plan
        self.parallel_groups = parallel_groups or []
        self.current_phase = current_phase
        self.progress = progress
        self.result = result
        self.error = error
        self.started_at = started_at or datetime.utcnow().isoformat()
        self.completed_at = completed_at
        self.updated_at = updated_at or datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "notebook_id": self.notebook_id,
            "goal": self.goal,
            "status": self.status,
            "orchestration_mode": self.orchestration_mode,
            "team_id": self.team_id,
            "complexity": self.complexity,
            "intent": self.intent,
            "required_capabilities": json.dumps(self.required_capabilities),
            "execution_plan": json.dumps(self.execution_plan) if self.execution_plan else None,
            "parallel_groups": json.dumps(self.parallel_groups),
            "current_phase": self.current_phase,
            "progress": self.progress,
            "result": json.dumps(self.result) if self.result else None,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrchestrationExecution":
        """Create from dictionary."""
        # Parse JSON fields
        if isinstance(data.get("required_capabilities"), str):
            data["required_capabilities"] = json.loads(data["required_capabilities"])

        if isinstance(data.get("execution_plan"), str):
            data["execution_plan"] = json.loads(data["execution_plan"])

        if isinstance(data.get("parallel_groups"), str):
            data["parallel_groups"] = json.loads(data["parallel_groups"])

        if isinstance(data.get("result"), str):
            data["result"] = json.loads(data["result"])

        return cls(**data)

    @classmethod
    async def get_by_user(cls, user_id: str, limit: int = 50) -> List["OrchestrationExecution"]:
        """Get orchestrations for user."""
        from open_notebook.database.repository import repo_query

        rows = await repo_query(
            f"""
            SELECT * FROM {cls._table_name}
            WHERE user_id = :user_id
            ORDER BY started_at DESC
            LIMIT :limit
            """,
            {"user_id": user_id, "limit": limit}
        )

        return [cls.from_dict(row) for row in rows]

    @classmethod
    async def get_by_status(cls, status: str, user_id: Optional[str] = None) -> List["OrchestrationExecution"]:
        """Get orchestrations by status."""
        from open_notebook.database.repository import repo_query

        if user_id:
            rows = await repo_query(
                f"""
                SELECT * FROM {cls._table_name}
                WHERE status = :status AND user_id = :user_id
                ORDER BY started_at DESC
                """,
                {"status": status, "user_id": user_id}
            )
        else:
            rows = await repo_query(
                f"""
                SELECT * FROM {cls._table_name}
                WHERE status = :status
                ORDER BY started_at DESC
                """,
                {"status": status}
            )

        return [cls.from_dict(row) for row in rows]


class OrchestrationEvent(ObjectModel):
    """Orchestration event record."""

    _table_name = "orchestration_events"

    def __init__(
        self,
        orchestration_id: str,
        event_type: str,
        event_data: Dict[str, Any],
        id: Optional[int] = None,
        timestamp: Optional[str] = None,
        **kwargs
    ):
        """Initialize orchestration event."""
        self.id = id
        self.orchestration_id = orchestration_id
        self.event_type = event_type
        self.event_data = event_data
        self.timestamp = timestamp or datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "orchestration_id": self.orchestration_id,
            "event_type": self.event_type,
            "event_data": json.dumps(self.event_data),
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrchestrationEvent":
        """Create from dictionary."""
        # Parse JSON field
        if isinstance(data.get("event_data"), str):
            data["event_data"] = json.loads(data["event_data"])

        return cls(**data)

    @classmethod
    async def get_by_orchestration(
        cls,
        orchestration_id: str,
        after_timestamp: Optional[str] = None
    ) -> List["OrchestrationEvent"]:
        """Get events for orchestration."""
        from open_notebook.database.repository import repo_query

        if after_timestamp:
            rows = await repo_query(
                f"""
                SELECT * FROM {cls._table_name}
                WHERE orchestration_id = :orchestration_id
                  AND timestamp > :after_timestamp
                ORDER BY timestamp ASC
                """,
                {"orchestration_id": orchestration_id, "after_timestamp": after_timestamp}
            )
        else:
            rows = await repo_query(
                f"""
                SELECT * FROM {cls._table_name}
                WHERE orchestration_id = :orchestration_id
                ORDER BY timestamp ASC
                """,
                {"orchestration_id": orchestration_id}
            )

        return [cls.from_dict(row) for row in rows]


class OrchestrationResource(ObjectModel):
    """Orchestration resource usage record."""

    _table_name = "orchestration_resources"

    def __init__(
        self,
        orchestration_id: str,
        resource_type: str,
        resource_id: str,
        resource_name: Optional[str] = None,
        usage_count: int = 0,
        id: Optional[int] = None,
        **kwargs
    ):
        """Initialize orchestration resource."""
        self.id = id
        self.orchestration_id = orchestration_id
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.resource_name = resource_name
        self.usage_count = usage_count

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "orchestration_id": self.orchestration_id,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "usage_count": self.usage_count
        }

    @classmethod
    async def get_by_orchestration(cls, orchestration_id: str) -> List["OrchestrationResource"]:
        """Get resources for orchestration."""
        from open_notebook.database.repository import repo_query

        rows = await repo_query(
            f"""
            SELECT * FROM {cls._table_name}
            WHERE orchestration_id = :orchestration_id
            ORDER BY usage_count DESC
            """,
            {"orchestration_id": orchestration_id}
        )

        return [cls.from_dict(row) for row in rows]


@dataclass
class OrchestrationMetrics:
    """Orchestration performance metrics."""
    orchestration_id: str
    analysis_duration_ms: Optional[int] = None
    decision_duration_ms: Optional[int] = None
    spawning_duration_ms: Optional[int] = None
    planning_duration_ms: Optional[int] = None
    execution_duration_ms: Optional[int] = None
    synthesis_duration_ms: Optional[int] = None
    total_duration_ms: Optional[int] = None
    task_count: int = 0
    parallel_task_count: int = 0
    sequential_task_count: int = 0
    handover_count: int = 0
    agent_count: int = 0
    tool_call_count: int = 0
    llm_token_usage: int = 0
    speedup_ratio: Optional[float] = None
    resource_utilization: Optional[float] = None
    created_at: Optional[str] = None

    async def save(self) -> None:
        """Save metrics to database."""
        from open_notebook.database.repository import repo_execute

        await repo_execute(
            """
            INSERT INTO orchestration_metrics
            (orchestration_id, analysis_duration_ms, decision_duration_ms,
             spawning_duration_ms, planning_duration_ms, execution_duration_ms,
             synthesis_duration_ms, total_duration_ms, task_count,
             parallel_task_count, sequential_task_count, handover_count,
             agent_count, tool_call_count, llm_token_usage, speedup_ratio,
             resource_utilization, created_at)
            VALUES (:orchestration_id, :analysis_duration_ms, :decision_duration_ms,
                    :spawning_duration_ms, :planning_duration_ms, :execution_duration_ms,
                    :synthesis_duration_ms, :total_duration_ms, :task_count,
                    :parallel_task_count, :sequential_task_count, :handover_count,
                    :agent_count, :tool_call_count, :llm_token_usage, :speedup_ratio,
                    :resource_utilization, :created_at)
            """,
            {
                "orchestration_id": self.orchestration_id,
                "analysis_duration_ms": self.analysis_duration_ms,
                "decision_duration_ms": self.decision_duration_ms,
                "spawning_duration_ms": self.spawning_duration_ms,
                "planning_duration_ms": self.planning_duration_ms,
                "execution_duration_ms": self.execution_duration_ms,
                "synthesis_duration_ms": self.synthesis_duration_ms,
                "total_duration_ms": self.total_duration_ms,
                "task_count": self.task_count,
                "parallel_task_count": self.parallel_task_count,
                "sequential_task_count": self.sequential_task_count,
                "handover_count": self.handover_count,
                "agent_count": self.agent_count,
                "tool_call_count": self.tool_call_count,
                "llm_token_usage": self.llm_token_usage,
                "speedup_ratio": self.speedup_ratio,
                "resource_utilization": self.resource_utilization,
                "created_at": self.created_at or datetime.utcnow().isoformat()
            }
        )

    @classmethod
    async def get_by_orchestration(cls, orchestration_id: str) -> Optional["OrchestrationMetrics"]:
        """Get metrics for orchestration."""
        from open_notebook.database.repository import repo_query

        rows = await repo_query(
            """
            SELECT * FROM orchestration_metrics
            WHERE orchestration_id = :orchestration_id
            """,
            {"orchestration_id": orchestration_id}
        )

        if rows:
            return cls(**rows[0])
        return None


class OrchestrationConfig(ObjectModel):
    """User orchestration configuration."""

    _table_name = "orchestration_configs"

    def __init__(
        self,
        id: str,
        user_id: str,
        prefer_team_over_single: bool = False,
        prefer_swarm_over_team: bool = False,
        max_team_size: int = 10,
        max_concurrent_tasks: int = 5,
        enable_parallel_execution: bool = True,
        max_execution_duration_seconds: int = 600,
        max_llm_tokens_per_orchestration: int = 100000,
        decision_model: Optional[str] = None,
        planner_model: Optional[str] = None,
        synthesizer_model: Optional[str] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        **kwargs
    ):
        """Initialize orchestration config."""
        self.id = id
        self.user_id = user_id
        self.prefer_team_over_single = prefer_team_over_single
        self.prefer_swarm_over_team = prefer_swarm_over_team
        self.max_team_size = max_team_size
        self.max_concurrent_tasks = max_concurrent_tasks
        self.enable_parallel_execution = enable_parallel_execution
        self.max_execution_duration_seconds = max_execution_duration_seconds
        self.max_llm_tokens_per_orchestration = max_llm_tokens_per_orchestration
        self.decision_model = decision_model
        self.planner_model = planner_model
        self.synthesizer_model = synthesizer_model
        self.created_at = created_at or datetime.utcnow().isoformat()
        self.updated_at = updated_at or datetime.utcnow().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "prefer_team_over_single": self.prefer_team_over_single,
            "prefer_swarm_over_team": self.prefer_swarm_over_team,
            "max_team_size": self.max_team_size,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "enable_parallel_execution": self.enable_parallel_execution,
            "max_execution_duration_seconds": self.max_execution_duration_seconds,
            "max_llm_tokens_per_orchestration": self.max_llm_tokens_per_orchestration,
            "decision_model": self.decision_model,
            "planner_model": self.planner_model,
            "synthesizer_model": self.synthesizer_model,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    @classmethod
    async def get_by_user(cls, user_id: str) -> Optional["OrchestrationConfig"]:
        """Get config for user."""
        from open_notebook.database.repository import repo_query

        rows = await repo_query(
            f"""
            SELECT * FROM {cls._table_name}
            WHERE user_id = :user_id
            """,
            {"user_id": user_id}
        )

        if rows:
            return cls.from_dict(rows[0])
        return None

    @classmethod
    async def get_or_create_for_user(cls, user_id: str) -> "OrchestrationConfig":
        """Get or create default config for user."""
        config = await cls.get_by_user(user_id)
        if config:
            return config

        # Create default config
        import uuid
        config = cls(id=str(uuid.uuid4()), user_id=user_id)
        await config.save()
        return config
