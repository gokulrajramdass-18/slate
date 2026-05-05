"""
Tool Registry - Central registry for organizing and distributing tools to agents.

Provides a singleton ToolRegistry that manages tool registration, categorization,
role-based access, and execution tracking.
"""

import time
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
)
from threading import Lock

logger = logging.getLogger(__name__)


class ToolCategory(str, Enum):
    """Categories for organizing tools."""
    FILE_OPS = "file_ops"
    SEARCH = "search"
    DATABASE = "database"
    API = "api"
    WEB = "web"
    ANALYSIS = "analysis"


class AgentRole(str, Enum):
    """Agent roles that can access tools."""
    PLANNER = "planner"
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    WRITER = "writer"
    EXECUTOR = "executor"
    ADMIN = "admin"


@dataclass
class ToolMetadata:
    """Metadata describing a registered tool."""
    name: str
    description: str
    category: ToolCategory
    allowed_roles: Set[AgentRole]
    is_async: bool = False
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)
    input_schema: Optional[Dict[str, Any]] = None
    output_description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "allowed_roles": [r.value for r in self.allowed_roles],
            "is_async": self.is_async,
            "version": self.version,
            "tags": self.tags,
            "input_schema": self.input_schema,
            "output_description": self.output_description,
        }


@dataclass
class ToolExecution:
    """Record of a single tool execution."""
    tool_name: str
    started_at: float
    ended_at: Optional[float] = None
    duration_ms: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None


class ToolRegistry:
    """
    Singleton registry for managing tools available to agents.

    Supports:
    - Registration of tools with metadata and category
    - Role-based tool filtering
    - Execution tracking with timing
    - LangChain BaseTool wrapping
    """

    _instance: Optional["ToolRegistry"] = None
    _lock: Lock = Lock()

    def __new__(cls) -> "ToolRegistry":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._tools: Dict[str, Any] = {}
        self._metadata: Dict[str, ToolMetadata] = {}
        self._executions: List[ToolExecution] = []
        self._max_execution_history: int = 1000
        self._initialized = True

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        tool: Any,
        description: str,
        category: ToolCategory,
        allowed_roles: Optional[Set[AgentRole]] = None,
        is_async: bool = False,
        version: str = "1.0.0",
        tags: Optional[List[str]] = None,
        input_schema: Optional[Dict[str, Any]] = None,
        output_description: str = "",
    ) -> None:
        """Register a tool with metadata."""
        if allowed_roles is None:
            allowed_roles = set(AgentRole)

        metadata = ToolMetadata(
            name=name,
            description=description,
            category=category,
            allowed_roles=allowed_roles,
            is_async=is_async,
            version=version,
            tags=tags or [],
            input_schema=input_schema,
            output_description=output_description,
        )

        self._tools[name] = tool
        self._metadata[name] = metadata
        logger.debug(f"Registered tool: {name} [{category.value}]")

    def register_langchain_tool(
        self,
        tool: Any,
        category: ToolCategory,
        allowed_roles: Optional[Set[AgentRole]] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        """
        Register a LangChain BaseTool instance.

        Extracts name, description, and schema from the tool object.
        """
        name = getattr(tool, "name", str(tool))
        description = getattr(tool, "description", "")
        is_async = hasattr(tool, "_arun")

        input_schema = None
        args_schema = getattr(tool, "args_schema", None)
        if args_schema is not None:
            try:
                input_schema = args_schema.model_json_schema()
            except Exception:
                pass

        self.register(
            name=name,
            tool=tool,
            description=description,
            category=category,
            allowed_roles=allowed_roles,
            is_async=is_async,
            tags=tags or [],
            input_schema=input_schema,
        )

    def unregister(self, name: str) -> bool:
        """Remove a tool from the registry. Returns True if it existed."""
        existed = name in self._tools
        self._tools.pop(name, None)
        self._metadata.pop(name, None)
        return existed

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_tool(self, name: str) -> Optional[Any]:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_metadata(self, name: str) -> Optional[ToolMetadata]:
        """Get metadata for a tool."""
        return self._metadata.get(name)

    def get_tools_by_category(self, category: ToolCategory) -> Dict[str, Any]:
        """Get all tools in a category."""
        return {
            name: tool
            for name, tool in self._tools.items()
            if self._metadata[name].category == category
        }

    def get_tools_for_role(self, role: AgentRole) -> Dict[str, Any]:
        """Get all tools accessible to a given agent role."""
        return {
            name: tool
            for name, tool in self._tools.items()
            if role in self._metadata[name].allowed_roles
        }

    def get_tools_for_role_and_category(
        self, role: AgentRole, category: ToolCategory
    ) -> Dict[str, Any]:
        """Get tools matching both a role and a category."""
        return {
            name: tool
            for name, tool in self._tools.items()
            if role in self._metadata[name].allowed_roles
            and self._metadata[name].category == category
        }

    def search_tools(self, query: str) -> List[ToolMetadata]:
        """Search tools by name, description, or tags."""
        query_lower = query.lower()
        results = []
        for meta in self._metadata.values():
            if (
                query_lower in meta.name.lower()
                or query_lower in meta.description.lower()
                or any(query_lower in tag.lower() for tag in meta.tags)
            ):
                results.append(meta)
        return results

    def list_tools(self) -> List[ToolMetadata]:
        """List metadata for all registered tools."""
        return list(self._metadata.values())

    @property
    def tool_count(self) -> int:
        return len(self._tools)

    @property
    def categories(self) -> Dict[str, int]:
        """Return category names with their tool counts."""
        counts: Dict[str, int] = {}
        for meta in self._metadata.values():
            key = meta.category.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    # ------------------------------------------------------------------
    # Execution tracking
    # ------------------------------------------------------------------

    def track_execution(
        self,
        tool_name: str,
        success: bool = True,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None,
        input_summary: Optional[str] = None,
        output_summary: Optional[str] = None,
    ) -> ToolExecution:
        """Record a tool execution for observability."""
        now = time.time()
        execution = ToolExecution(
            tool_name=tool_name,
            started_at=now - (duration_ms / 1000.0 if duration_ms else 0),
            ended_at=now,
            duration_ms=duration_ms,
            success=success,
            error=error,
            input_summary=input_summary,
            output_summary=output_summary,
        )
        self._executions.append(execution)

        # Trim history
        if len(self._executions) > self._max_execution_history:
            self._executions = self._executions[-self._max_execution_history:]

        return execution

    def get_execution_stats(self) -> Dict[str, Any]:
        """Get aggregate execution statistics."""
        if not self._executions:
            return {"total": 0, "by_tool": {}}

        by_tool: Dict[str, Dict[str, Any]] = {}
        for ex in self._executions:
            if ex.tool_name not in by_tool:
                by_tool[ex.tool_name] = {
                    "count": 0,
                    "successes": 0,
                    "failures": 0,
                    "total_ms": 0.0,
                }
            stats = by_tool[ex.tool_name]
            stats["count"] += 1
            if ex.success:
                stats["successes"] += 1
            else:
                stats["failures"] += 1
            if ex.duration_ms is not None:
                stats["total_ms"] += ex.duration_ms

        # Compute averages
        for stats in by_tool.values():
            if stats["count"] > 0:
                stats["avg_ms"] = round(stats["total_ms"] / stats["count"], 2)

        return {
            "total": len(self._executions),
            "by_tool": by_tool,
        }

    def get_recent_executions(self, limit: int = 20) -> List[ToolExecution]:
        """Return the most recent executions."""
        return self._executions[-limit:]

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all tools, metadata, and execution history. Useful for testing."""
        self._tools.clear()
        self._metadata.clear()
        self._executions.clear()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the registry state."""
        return {
            "tool_count": self.tool_count,
            "categories": self.categories,
            "tools": {name: meta.to_dict() for name, meta in self._metadata.items()},
            "execution_stats": self.get_execution_stats(),
        }


def get_tool_registry() -> ToolRegistry:
    """Get the global ToolRegistry singleton."""
    return ToolRegistry()
