"""
Tool registry domain models.

Includes ToolRegistry, ToolPermission, and ToolUsageLog entities
for managing tool configuration, access control, and usage tracking.
"""

import json
from datetime import datetime, timedelta
from typing import Any, ClassVar, Dict, List, Optional

from open_notebook.database.repository import repo_query
from open_notebook.domain.base import ObjectModel


class ToolRegistry(ObjectModel):
    """
    ToolRegistry represents a registered tool that AI agents can invoke.

    Tool types include hana_query, api_call, web_search, code_exec, and custom.
    Each tool has a type, category, and optional default configuration.
    """

    _table_name: ClassVar[str] = "tool_registry"

    name: str
    tool_type: str  # hana_query, api_call, web_search, code_exec, custom
    category: Optional[str] = None  # data_query, web, computation, file_analysis
    description: Optional[str] = None
    enabled: bool = True
    default_config: Optional[str] = None  # JSON string
    metadata: Optional[str] = None  # JSON string: {icon, tags, author, version, ...}

    def get_default_config(self) -> Optional[Dict[str, Any]]:
        """Parse default_config JSON string into a dict."""
        if not self.default_config:
            return None
        try:
            return json.loads(self.default_config)
        except (json.JSONDecodeError, TypeError):
            return None

    def set_default_config(self, config: Dict[str, Any]) -> None:
        """Set default_config from a dict."""
        if config:
            self.default_config = json.dumps(config)
        else:
            self.default_config = None

    def get_metadata(self) -> Optional[Dict[str, Any]]:
        """Parse metadata JSON string into a dict."""
        if not self.metadata:
            return None
        try:
            return json.loads(self.metadata)
        except (json.JSONDecodeError, TypeError):
            return None

    def set_metadata(self, meta: Dict[str, Any]) -> None:
        """Set metadata from a dict."""
        if meta:
            self.metadata = json.dumps(meta)
        else:
            self.metadata = None

    async def toggle_enabled(self) -> bool:
        """
        Toggle the enabled state of this tool.

        Returns:
            The new enabled state.
        """
        self.enabled = not self.enabled
        await self.save()
        return self.enabled

    @classmethod
    async def get_by_type(cls, tool_type: str) -> List["ToolRegistry"]:
        """
        Get all tools of a specific type.

        Args:
            tool_type: Tool type (e.g., 'hana_query', 'api_call')

        Returns:
            List of ToolRegistry instances
        """
        sql = """
            SELECT * FROM tool_registry
            WHERE tool_type = :tool_type
            ORDER BY name ASC
        """
        results = await repo_query(sql, {"tool_type": tool_type})
        return [cls(**row) for row in results]

    @classmethod
    async def get_by_category(cls, category: str) -> List["ToolRegistry"]:
        """
        Get all tools in a specific category.

        Args:
            category: Tool category (e.g., 'data_query', 'web')

        Returns:
            List of ToolRegistry instances
        """
        sql = """
            SELECT * FROM tool_registry
            WHERE category = :category
            ORDER BY name ASC
        """
        results = await repo_query(sql, {"category": category})
        return [cls(**row) for row in results]

    @classmethod
    async def get_enabled(cls) -> List["ToolRegistry"]:
        """
        Get all enabled tools.

        Returns:
            List of enabled ToolRegistry instances
        """
        return await cls.get_all(
            order_by="name ASC",
            filters={"enabled": True},
        )


class ToolPermission(ObjectModel):
    """
    ToolPermission controls access to a tool for a user or role.

    Either user_id or role must be set, but not both.
    When user_id is set, the permission applies to that specific user.
    When role is set, the permission applies to all users with that role.
    """

    _table_name: ClassVar[str] = "tool_permissions"
    _exclude_fields: ClassVar[List[str]] = ["updated"]

    tool_id: str
    user_id: Optional[str] = None
    role: Optional[str] = None  # admin, analyst, viewer, etc.
    allowed: bool = True
    rate_limit: Optional[int] = None  # Calls per minute, None = no limit
    custom_config: Optional[str] = None  # JSON string for user-specific overrides

    def get_custom_config(self) -> Optional[Dict[str, Any]]:
        """Parse custom_config JSON string into a dict."""
        if not self.custom_config:
            return None
        try:
            return json.loads(self.custom_config)
        except (json.JSONDecodeError, TypeError):
            return None

    def set_custom_config(self, config: Dict[str, Any]) -> None:
        """Set custom_config from a dict."""
        if config:
            self.custom_config = json.dumps(config)
        else:
            self.custom_config = None

    @classmethod
    async def get_for_user(cls, user_id: str) -> List["ToolPermission"]:
        """
        Get all permissions for a specific user.

        Args:
            user_id: User ID

        Returns:
            List of ToolPermission instances for the user
        """
        sql = """
            SELECT * FROM tool_permissions
            WHERE user_id = :user_id
            ORDER BY created ASC
        """
        results = await repo_query(sql, {"user_id": user_id})
        return [cls(**row) for row in results]

    @classmethod
    async def get_for_role(cls, role: str) -> List["ToolPermission"]:
        """
        Get all permissions for a specific role.

        Args:
            role: Role name (e.g., 'admin', 'analyst')

        Returns:
            List of ToolPermission instances for the role
        """
        sql = """
            SELECT * FROM tool_permissions
            WHERE role = :role
            ORDER BY created ASC
        """
        results = await repo_query(sql, {"role": role})
        return [cls(**row) for row in results]

    @classmethod
    async def get_for_tool(cls, tool_id: str) -> List["ToolPermission"]:
        """
        Get all permissions for a specific tool.

        Args:
            tool_id: Tool registry ID

        Returns:
            List of ToolPermission instances for the tool
        """
        sql = """
            SELECT * FROM tool_permissions
            WHERE tool_id = :tool_id
            ORDER BY created ASC
        """
        results = await repo_query(sql, {"tool_id": tool_id})
        return [cls(**row) for row in results]


class ToolUsageLog(ObjectModel):
    """
    ToolUsageLog records each invocation of a tool for observability.

    Tracks which tool was called, by whom, in what context,
    how long it took, and whether it succeeded.
    """

    _table_name: ClassVar[str] = "tool_usage_log"
    _exclude_fields: ClassVar[List[str]] = ["updated"]

    tool_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    notebook_id: Optional[str] = None
    input_params: Optional[str] = None  # JSON string
    execution_time_ms: Optional[int] = None
    success: Optional[bool] = None
    error_message: Optional[str] = None

    def get_input_params(self) -> Optional[Dict[str, Any]]:
        """Parse input_params JSON string into a dict."""
        if not self.input_params:
            return None
        try:
            return json.loads(self.input_params)
        except (json.JSONDecodeError, TypeError):
            return None

    def set_input_params(self, params: Dict[str, Any]) -> None:
        """Set input_params from a dict."""
        if params:
            self.input_params = json.dumps(params)
        else:
            self.input_params = None

    @classmethod
    async def get_by_tool(
        cls, tool_id: str, limit: int = 100
    ) -> List["ToolUsageLog"]:
        """
        Get usage logs for a specific tool.

        Args:
            tool_id: Tool registry ID
            limit: Maximum number of records to return

        Returns:
            List of ToolUsageLog instances, most recent first
        """
        sql = f"""
            SELECT * FROM tool_usage_log
            WHERE tool_id = :tool_id
            ORDER BY created DESC
            LIMIT {limit}
        """
        results = await repo_query(sql, {"tool_id": tool_id})
        return [cls(**row) for row in results]

    @classmethod
    async def get_by_user(
        cls, user_id: str, limit: int = 100
    ) -> List["ToolUsageLog"]:
        """
        Get usage logs for a specific user.

        Args:
            user_id: User ID
            limit: Maximum number of records to return

        Returns:
            List of ToolUsageLog instances, most recent first
        """
        sql = f"""
            SELECT * FROM tool_usage_log
            WHERE user_id = :user_id
            ORDER BY created DESC
            LIMIT {limit}
        """
        results = await repo_query(sql, {"user_id": user_id})
        return [cls(**row) for row in results]

    @classmethod
    async def get_by_session(
        cls, session_id: str
    ) -> List["ToolUsageLog"]:
        """
        Get usage logs for a specific chat session.

        Args:
            session_id: Chat session ID

        Returns:
            List of ToolUsageLog instances, chronologically ordered
        """
        sql = """
            SELECT * FROM tool_usage_log
            WHERE session_id = :session_id
            ORDER BY created ASC
        """
        results = await repo_query(sql, {"session_id": session_id})
        return [cls(**row) for row in results]

    @classmethod
    async def get_stats(
        cls, tool_id: str, days: int = 30
    ) -> Dict[str, Any]:
        """
        Get usage statistics for a tool over a time period.

        Args:
            tool_id: Tool registry ID
            days: Number of days to look back

        Returns:
            Dict with total_calls, success_count, error_count,
            avg_execution_time_ms, and error_rate
        """
        since = datetime.utcnow() - timedelta(days=days)

        sql = """
            SELECT
                COUNT(*) as total_calls,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as error_count,
                AVG(execution_time_ms) as avg_execution_time_ms
            FROM tool_usage_log
            WHERE tool_id = :tool_id
              AND created >= :since
        """
        results = await repo_query(sql, {"tool_id": tool_id, "since": since})

        if not results or results[0]["total_calls"] == 0:
            return {
                "total_calls": 0,
                "success_count": 0,
                "error_count": 0,
                "avg_execution_time_ms": 0,
                "error_rate": 0.0,
            }

        row = results[0]
        total = row["total_calls"]
        errors = row["error_count"] or 0

        return {
            "total_calls": total,
            "success_count": row["success_count"] or 0,
            "error_count": errors,
            "avg_execution_time_ms": round(row["avg_execution_time_ms"] or 0),
            "error_rate": round(errors / total, 4) if total > 0 else 0.0,
        }
