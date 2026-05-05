"""
Base types for the Agent Skills System.

Defines core data structures: Skill, SkillContext, SkillCategory, etc.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


class SkillCategory(str, Enum):
    """Categories for organizing skills."""
    SEARCH = "search"
    DATA_QUERY = "data_query"
    ANALYSIS = "analysis"
    SYNTHESIS = "synthesis"
    COORDINATION = "coordination"
    MEMORY = "memory"
    TOOLS = "tools"
    COMMUNICATION = "communication"
    VALIDATION = "validation"
    TRANSFORMATION = "transformation"


@dataclass
class RetryPolicy:
    """Configuration for skill retry behavior."""
    max_attempts: int = 3
    initial_delay_ms: int = 1000
    backoff_multiplier: float = 2.0
    max_delay_ms: int = 10000
    retry_on_errors: List[str] = field(default_factory=lambda: ["timeout", "network"])


@dataclass
class SkillContext:
    """
    Execution context provided to skill handlers.

    Contains all resources and state needed for skill execution.
    """
    # Identity
    agent_id: str
    agent_role: str
    skill_id: str
    team_id: Optional[str] = None

    # Execution
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    input_data: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)

    # Resources (injected at runtime)
    llm: Optional[Any] = None
    database: Optional[Any] = None
    message_bus: Optional[Any] = None
    task_manager: Optional[Any] = None
    tool_registry: Optional[Any] = None

    # Observability
    parent_span_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # State
    agent_state: Dict[str, Any] = field(default_factory=dict)
    team_state: Dict[str, Any] = field(default_factory=dict)

    # Steps tracking (for observability)
    steps: List[Dict[str, Any]] = field(default_factory=list)

    def record_step(
        self,
        step_type: str,
        content: str,
        status: str = "completed",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record an execution step for observability.

        Args:
            step_type: Step category (thinking, searching, tool_call, etc.)
            content: Human-readable description
            status: pending | running | completed | error
            metadata: Extra data

        Returns:
            The created step dict
        """
        step = {
            "step_type": step_type,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "status": status,
            "metadata": metadata or {},
        }
        self.steps.append(step)
        return step

    def get_tool(self, tool_name: str) -> Optional[Any]:
        """
        Access a tool from the registry.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool instance or None if not found
        """
        if self.tool_registry is None:
            return None
        return self.tool_registry.get_tool(tool_name)

    async def call_skill(
        self,
        skill_id: str,
        input_data: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Call another skill (for composition).

        Args:
            skill_id: ID of skill to call
            input_data: Input for the skill
            config: Optional config override

        Returns:
            Skill execution result
        """
        # Import here to avoid circular dependency
        from open_notebook.agents.skills.executor import get_skill_executor

        executor = get_skill_executor()

        # Create child context
        child_context = SkillContext(
            agent_id=self.agent_id,
            agent_role=self.agent_role,
            team_id=self.team_id,
            skill_id=skill_id,
            execution_id=str(uuid.uuid4()),
            input_data=input_data,
            config=config or {},
            llm=self.llm,
            database=self.database,
            message_bus=self.message_bus,
            task_manager=self.task_manager,
            tool_registry=self.tool_registry,
            parent_span_id=self.execution_id,
            metadata=self.metadata.copy(),
            agent_state=self.agent_state,
            team_state=self.team_state,
        )

        return await executor.execute(skill_id, child_context)


@dataclass
class Skill:
    """
    A reusable capability that can be attached to agents.

    Skills are composable, observable, and can be configured per-binding.
    """
    id: str
    name: str
    description: str
    category: SkillCategory
    handler: Callable  # async def handler(context: SkillContext) -> Any
    version: str = "1.0.0"

    # Access control
    allowed_roles: Set[str] = field(default_factory=set)
    required_permissions: List[str] = field(default_factory=list)

    # Configuration
    config_schema: Optional[Dict[str, Any]] = None
    default_config: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    tags: List[str] = field(default_factory=list)
    author: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)  # Other skill IDs

    # Runtime behavior
    timeout_seconds: int = 30
    retry_policy: Optional[RetryPolicy] = None
    cache_ttl_seconds: int = 0  # 0 = no caching

    # Status
    enabled: bool = True
    deprecated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize skill metadata (excludes handler)."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "version": self.version,
            "allowed_roles": list(self.allowed_roles),
            "required_permissions": self.required_permissions,
            "config_schema": self.config_schema,
            "default_config": self.default_config,
            "tags": self.tags,
            "author": self.author,
            "dependencies": self.dependencies,
            "timeout_seconds": self.timeout_seconds,
            "retry_policy": self.retry_policy.__dict__ if self.retry_policy else None,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "enabled": self.enabled,
            "deprecated": self.deprecated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], handler: Callable) -> "Skill":
        """Deserialize skill metadata and attach handler."""
        retry_dict = data.get("retry_policy")
        retry_policy = RetryPolicy(**retry_dict) if retry_dict else None

        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            category=SkillCategory(data["category"]),
            version=data.get("version", "1.0.0"),
            handler=handler,
            allowed_roles=set(data.get("allowed_roles", [])),
            required_permissions=data.get("required_permissions", []),
            config_schema=data.get("config_schema"),
            default_config=data.get("default_config", {}),
            tags=data.get("tags", []),
            author=data.get("author"),
            dependencies=data.get("dependencies", []),
            timeout_seconds=data.get("timeout_seconds", 30),
            retry_policy=retry_policy,
            cache_ttl_seconds=data.get("cache_ttl_seconds", 0),
            enabled=data.get("enabled", True),
            deprecated=data.get("deprecated", False),
        )


@dataclass
class SkillExecutionResult:
    """Result of skill execution."""
    skill_id: str
    execution_id: str
    success: bool
    result: Any
    error: Optional[str] = None
    duration_ms: float = 0
    steps: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize result."""
        return {
            "skill_id": self.skill_id,
            "execution_id": self.execution_id,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "steps": self.steps,
            "metadata": self.metadata,
        }
