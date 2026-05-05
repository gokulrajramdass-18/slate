"""
Standalone Agent domain model.

Provides domain entity for standalone agents - individual agents not part of a team.
"""

import json
from typing import Any, ClassVar, Dict, List, Optional

from open_notebook.domain.base import ObjectModel


class StandaloneAgent(ObjectModel):
    """
    A standalone agent is an individual agent configuration with its own tools,
    MCP servers, and data sources.

    Unlike team agents, standalone agents operate independently and can be
    executed directly by users without coordination with other agents.

    Supports both local and remote agents via A2A protocol:
    - Local agents: is_remote=False, executed directly via LangGraph
    - Remote agents: is_remote=True, executed via A2A protocol
    """

    _table_name: ClassVar[str] = "standalone_agents"

    name: str
    description: Optional[str] = None
    role: str
    system_prompt: Optional[str] = None
    model_name: Optional[str] = None
    notebook_id: Optional[str] = None

    # Configuration
    config: Optional[str] = None
    tool_ids: Optional[str] = None
    mcp_server_ids: Optional[str] = None
    data_source_ids: Optional[str] = None

    # Status
    status: str = "active"

    # A2A protocol support
    is_remote: bool = False
    remote_agent_id: Optional[str] = None
    a2a_endpoint_url: Optional[str] = None

    # Primary skill ID (for A2A adapter)
    @property
    def primary_skill_id(self) -> str:
        """
        Get primary skill ID for this agent.

        For remote agents, this returns the remote skill mapping ID.
        For local agents, this returns the role-based skill ID.
        """
        if self.is_remote and self.remote_agent_id:
            # For remote agents, use the remote agent's primary skill
            # This will be determined from A2A AgentCard
            return f"a2a:{self.remote_agent_id}:primary"
        else:
            # For local agents, map role to skill ID
            role_to_skill = {
                "planner": "planner",
                "researcher": "researcher",
                "analyst": "data_query",
                "synthesizer": "synthesizer",
                "custom": "custom",
            }
            return role_to_skill.get(self.role, "custom")

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

    def get_tool_ids(self) -> List[str]:
        """Get list of tool IDs."""
        if not self.tool_ids:
            return []
        try:
            tools = json.loads(self.tool_ids)
            return tools if isinstance(tools, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_tool_ids(self, tool_ids: List[str]) -> None:
        """Set tool IDs from list."""
        self.tool_ids = json.dumps(tool_ids) if tool_ids else None

    def get_mcp_server_ids(self) -> List[str]:
        """Get list of MCP server IDs."""
        if not self.mcp_server_ids:
            return []
        try:
            servers = json.loads(self.mcp_server_ids)
            return servers if isinstance(servers, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_mcp_server_ids(self, server_ids: List[str]) -> None:
        """Set MCP server IDs from list."""
        self.mcp_server_ids = json.dumps(server_ids) if server_ids else None

    def get_data_source_ids(self) -> List[str]:
        """Get list of data source IDs."""
        if not self.data_source_ids:
            return []
        try:
            sources = json.loads(self.data_source_ids)
            return sources if isinstance(sources, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_data_source_ids(self, source_ids: List[str]) -> None:
        """Set data source IDs from list."""
        self.data_source_ids = json.dumps(source_ids) if source_ids else None

    async def get_executions(
        self,
        limit: int = 50,
        status: Optional[str] = None
    ) -> List["StandaloneAgentExecution"]:
        """
        Get execution history for this agent.

        Args:
            limit: Maximum number of executions to return
            status: Optional status filter

        Returns:
            List of StandaloneAgentExecution instances
        """
        if self.id is None:
            return []

        filters: Dict[str, Any] = {"agent_id": self.id}
        if status:
            filters["status"] = status

        return await StandaloneAgentExecution.get_all(
            filters=filters,
            order_by=("created", "DESC"),
            limit=limit,
        )

    @classmethod
    async def get_by_role(cls, role: str) -> List["StandaloneAgent"]:
        """
        Get all agents with a specific role.

        Args:
            role: Agent role

        Returns:
            List of StandaloneAgent instances
        """
        return await cls.get_all(
            filters={"role": role, "status": "active"},
            order_by=("created", "DESC"),
        )

    @classmethod
    async def get_remote_agents(cls) -> List["StandaloneAgent"]:
        """
        Get all remote A2A agents.

        Returns:
            List of remote StandaloneAgent instances
        """
        return await cls.get_all(
            filters={"is_remote": True, "status": "active"},
            order_by=("created", "DESC"),
        )

    @classmethod
    async def get_local_agents(cls) -> List["StandaloneAgent"]:
        """
        Get all local agents.

        Returns:
            List of local StandaloneAgent instances
        """
        return await cls.get_all(
            filters={"is_remote": False, "status": "active"},
            order_by=("created", "DESC"),
        )


class StandaloneAgentExecution(ObjectModel):
    """
    Execution record for a standalone agent.

    Tracks the execution history, results, and performance metrics
    for standalone agent invocations.
    """

    _table_name: ClassVar[str] = "standalone_agent_executions"

    agent_id: str
    query: str
    status: str = "running"

    # Execution context
    session_id: Optional[str] = None
    notebook_id: Optional[str] = None
    context: Optional[str] = None

    # Results
    result: Optional[str] = None
    error: Optional[str] = None
    steps: Optional[str] = None
    tool_calls: Optional[str] = None

    # Timing
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None

    def get_context(self) -> Dict[str, Any]:
        """Parse context JSON."""
        if not self.context:
            return {}
        try:
            return json.loads(self.context)
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_context(self, context: Dict[str, Any]) -> None:
        """Set context from dict."""
        self.context = json.dumps(context) if context else None

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

    def get_steps(self) -> List[Dict[str, Any]]:
        """Parse steps JSON."""
        if not self.steps:
            return []
        try:
            steps = json.loads(self.steps)
            return steps if isinstance(steps, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_steps(self, steps: List[Dict[str, Any]]) -> None:
        """Set steps from list."""
        self.steps = json.dumps(steps) if steps else None

    def get_tool_calls(self) -> List[Dict[str, Any]]:
        """Parse tool_calls JSON."""
        if not self.tool_calls:
            return []
        try:
            calls = json.loads(self.tool_calls)
            return calls if isinstance(calls, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> None:
        """Set tool_calls from list."""
        self.tool_calls = json.dumps(tool_calls) if tool_calls else None
