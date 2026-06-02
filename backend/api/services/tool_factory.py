"""
Unified Tool Factory

Creates LangChain tools for chat sessions by combining:
1. Source-based tools (HANA tables, APIs from notebook sources)
2. Registry tools (globally registered tools like web search)

Applies user/role permissions and rate limits.
"""

import json
import logging
from typing import List, Optional, Dict, Any

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from open_notebook.database.repository import repo_query
from api.services.rate_limiter import RateLimitedTool

logger = logging.getLogger(__name__)


class ToolFactory:
    """Unified tool creation with registry and permissions."""

    async def create_tools_for_session(
        self,
        notebook_id: str,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> List[BaseTool]:
        """
        Create tools for a chat session.

        Merges source-based tools with registry tools, filters by
        user permissions, and wraps with rate limits.

        Args:
            notebook_id: Notebook UUID whose sources provide tools
            user_id: User UUID for permission and rate limit checks
            session_id: Optional chat session ID for observability

        Returns:
            List of ready-to-use LangChain BaseTool instances
        """
        # 1. Source-based tools (HANA tables, APIs)
        source_tools = await self._get_source_tools(notebook_id, session_id)

        # 2. Registry tools (globally enabled)
        registry_tools = await self._get_registry_tools()

        # 3. MCP server tools (connected servers, scoped to this user)
        mcp_tools = await self._get_mcp_tools(user_id)

        # 4. Action tools (globally configured actions)
        action_tools = await self._get_action_tools(user_id, session_id)

        all_tools = source_tools + registry_tools + mcp_tools + action_tools

        # 5. Permission filtering
        allowed_tools = await self._filter_by_permissions(all_tools, user_id)

        # 6. Rate limiting
        limited_tools = self._apply_rate_limits(allowed_tools, user_id)

        logger.info(
            "ToolFactory: %d tools for session (source=%d, registry=%d, mcp=%d, actions=%d, after perms=%d)",
            len(limited_tools),
            len(source_tools),
            len(registry_tools),
            len(mcp_tools),
            len(action_tools),
            len(allowed_tools),
        )

        return limited_tools

    # ------------------------------------------------------------------
    # Source tools
    # ------------------------------------------------------------------

    async def _get_source_tools(
        self,
        notebook_id: str,
        session_id: Optional[str] = None,
    ) -> List[BaseTool]:
        """Delegate to existing create_tools_for_notebook."""
        from api.services.data_query_tools import create_tools_for_notebook

        try:
            return await create_tools_for_notebook(notebook_id, session_id)
        except Exception as exc:
            logger.warning("Failed to get source tools for notebook %s: %s", notebook_id, exc)
            return []

    # ------------------------------------------------------------------
    # MCP server tools
    # ------------------------------------------------------------------

    async def _get_mcp_tools(self, user_id: str) -> List[BaseTool]:
        """
        Instantiate MCP tools that `user_id` is authorized to use.

        The LEFT JOIN against `mcp_oauth_tokens` resolves to:
          - the user's own row for user-mode servers, OR
          - the shared `__system__` row for system-mode servers.

        If the resolved row is missing, the OAuth server contributes no
        tools to this user's agent. Non-OAuth servers always contribute.

        Returns:
            List of MCPTool instances bound to this user (the closure
            captures the *effective* token user_id, so system-mode tools
            invoke the pool with `__system__`).
        """
        from api.services.mcp_tools import create_mcp_tool
        from api.services.mcp_client import SYSTEM_OAUTH_USER_ID

        tools: List[BaseTool] = []

        try:
            # CASE on s.oauth_mode collapses system-mode rows to the
            # shared sentinel; user-mode rows still match the caller.
            sql = """
                SELECT s.*
                FROM mcp_servers s
                LEFT JOIN mcp_oauth_tokens t
                    ON t.server_id = s.id
                   AND t.user_id   = CASE
                                         WHEN COALESCE(s.oauth_mode, 'user') = 'system'
                                             THEN :system_user_id
                                         ELSE :user_id
                                     END
                WHERE s.status = 'connected'
                  AND (
                        s.auth_type IS NULL
                     OR s.auth_type != 'oauth'
                     OR t.access_token IS NOT NULL
                  )
                ORDER BY s.name
            """
            servers = await repo_query(
                sql,
                {"user_id": user_id, "system_user_id": SYSTEM_OAUTH_USER_ID},
            )

            for server in servers:
                server_id = server["id"]
                server_config = dict(server)

                # Get cached tools from discovery
                tools_sql = """
                    SELECT * FROM mcp_tools
                    WHERE server_id = :server_id
                    ORDER BY tool_name
                """
                tool_rows = await repo_query(tools_sql, {"server_id": server_id})

                # Create MCPTool instances bound to this user. For
                # system-mode servers, `create_mcp_tool` will substitute
                # the user_id with `__system__` internally so the closure
                # routes to the shared pooled client.
                for tool_data in tool_rows:
                    try:
                        tool = create_mcp_tool(
                            server_id=server_id,
                            server_config=server_config,
                            tool_data=dict(tool_data),
                            user_id=user_id,
                        )
                        tools.append(tool)
                    except Exception as exc:
                        logger.error(
                            "Failed to create MCP tool %s from server %s: %s",
                            tool_data.get("tool_name"),
                            server.get("name"),
                            exc,
                            exc_info=True  # This will log the full traceback
                        )

        except Exception as exc:
            # Tables may not exist yet during migration
            logger.warning("MCP servers or tools table not available yet: %s", exc)

        return tools

    # ------------------------------------------------------------------
    # Registry tools
    # ------------------------------------------------------------------

    async def _get_registry_tools(self) -> List[BaseTool]:
        """
        Instantiate tools from the tool_registry table.

        Only returns tools where enabled = TRUE.  Each row's tool_type
        drives which concrete BaseTool subclass is created.
        """
        try:
            sql = """
                SELECT id, name, tool_type, description, default_config, metadata
                FROM tool_registry
                WHERE enabled = 1
            """
            rows = await repo_query(sql)
        except Exception:
            # Table may not exist yet during migration
            logger.debug("tool_registry table not available yet")
            return []

        tools: List[BaseTool] = []
        for row in rows:
            tool = self._instantiate_registry_tool(row)
            if tool is not None:
                # Store registry id in tool metadata/config instead of as attribute
                # This avoids Pydantic validation errors
                if hasattr(tool, 'metadata') and isinstance(tool.metadata, dict):
                    tool.metadata['_registry_id'] = row["id"]
                elif hasattr(tool, 'config') and isinstance(tool.config, dict):
                    tool.config['_registry_id'] = row["id"]
                else:
                    # Fallback: store in a private dict attribute that we manage
                    if not hasattr(tool, '_tool_meta'):
                        tool.__dict__['_tool_meta'] = {}
                    tool.__dict__['_tool_meta']['registry_id'] = row["id"]
                tools.append(tool)

        return tools

    def _instantiate_registry_tool(self, row: Dict[str, Any]) -> Optional[BaseTool]:
        """Create a BaseTool from a registry row based on tool_type."""
        tool_type = row.get("tool_type", "")
        default_config = row.get("default_config")
        if isinstance(default_config, str):
            try:
                default_config = json.loads(default_config)
            except (json.JSONDecodeError, TypeError):
                default_config = {}
        default_config = default_config or {}

        try:
            if tool_type == "web_search":
                return self._create_web_search_tool(row, default_config)
            elif tool_type == "code_exec":
                return self._create_code_exec_tool(row, default_config)
            elif tool_type == "file_analysis":
                return self._create_file_analysis_tool(row, default_config)
            elif tool_type == "calculator":
                return self._create_calculator_tool(row, default_config)
            elif tool_type == "datetime":
                return self._create_datetime_tool(row, default_config)
            elif tool_type == "url_fetch":
                return self._create_url_fetch_tool(row, default_config)
            elif tool_type == "json_parser":
                return self._create_json_parser_tool(row, default_config)
            elif tool_type == "text_analyzer":
                return self._create_text_analyzer_tool(row, default_config)
            elif tool_type == "wikipedia":
                return self._create_wikipedia_tool(row, default_config)
            elif tool_type == "chart":
                return self._create_chart_tool(row, default_config)
            else:
                logger.debug("Unknown registry tool_type: %s", tool_type)
                return None
        except Exception as exc:
            logger.warning("Failed to instantiate registry tool %s: %s", row.get("name"), exc)
            return None

    # --- Concrete tool creators (stubs – implement when tools are added) ---

    def _create_web_search_tool(self, row: dict, config: dict) -> Optional[BaseTool]:
        """Create web search tool if available.

        The tool itself handles missing API keys gracefully by returning
        an informative error, so we always create it when registered.
        """
        try:
            from api.services.tools.web_search_tool import WebSearchTool
            import os

            api_key = config.get("api_key") or os.getenv("TAVILY_API_KEY")
            return WebSearchTool(api_key=api_key)
        except ImportError:
            return None

    def _create_code_exec_tool(self, row: dict, config: dict) -> Optional[BaseTool]:
        """Create code execution tool if available."""
        try:
            from api.services.tools.code_exec_tool import CodeExecutionTool
            return CodeExecutionTool(**config)
        except ImportError:
            return None

    def _create_file_analysis_tool(self, row: dict, config: dict) -> Optional[BaseTool]:
        """Create file analysis tool if available."""
        try:
            from api.services.tools.file_analysis_tool import FileAnalysisTool
            return FileAnalysisTool(**config)
        except ImportError:
            return None

    def _create_calculator_tool(self, row: dict, config: dict) -> Optional[BaseTool]:
        """Create calculator tool for math expressions."""
        try:
            from api.services.tools.calculator_tool import CalculatorTool
            return CalculatorTool()
        except ImportError:
            return None

    def _create_datetime_tool(self, row: dict, config: dict) -> Optional[BaseTool]:
        """Create datetime tool for date/time operations."""
        try:
            from api.services.tools.datetime_tool import DateTimeTool
            return DateTimeTool()
        except ImportError:
            return None

    def _create_url_fetch_tool(self, row: dict, config: dict) -> Optional[BaseTool]:
        """Create URL fetch tool for retrieving web content."""
        try:
            from api.services.tools.url_fetch_tool import URLFetchTool
            return URLFetchTool()
        except ImportError:
            return None

    def _create_json_parser_tool(self, row: dict, config: dict) -> Optional[BaseTool]:
        """Create JSON parser tool for structured data extraction."""
        try:
            from api.services.tools.json_parser_tool import JSONParserTool
            return JSONParserTool()
        except ImportError:
            return None

    def _create_text_analyzer_tool(self, row: dict, config: dict) -> Optional[BaseTool]:
        """Create text analyzer tool for text statistics and analysis."""
        try:
            from api.services.tools.text_analyzer_tool import TextAnalyzerTool
            return TextAnalyzerTool()
        except ImportError:
            return None

    def _create_wikipedia_tool(self, row: dict, config: dict) -> Optional[BaseTool]:
        """Create Wikipedia tool for encyclopedia lookups."""
        try:
            from api.services.tools.wikipedia_tool import WikipediaTool
            return WikipediaTool()
        except ImportError:
            return None

    def _create_chart_tool(self, row: dict, config: dict) -> Optional[BaseTool]:
        """Create chart visualization tool."""
        try:
            from api.services.tools.chart_langchain_tool import ChartVisualizationTool
            return ChartVisualizationTool()
        except ImportError:
            return None

    # ------------------------------------------------------------------
    # Action tools
    # ------------------------------------------------------------------

    async def _get_action_tools(self, user_id: str, session_id: Optional[str] = None) -> List[BaseTool]:
        """
        Create tools from active actions.

        Each action becomes a tool that the agent can invoke.

        Args:
            user_id: User ID for context
            session_id: Chat session ID for context

        Returns:
            List of action tools
        """
        try:
            sql = """
                SELECT id, name, description, action_type, body_template
                FROM actions
                WHERE is_active = 1
                ORDER BY name
            """
            actions = await repo_query(sql, {})
        except Exception as exc:
            logger.warning("Failed to load actions: %s", exc)
            return []

        tools: List[BaseTool] = []
        for action in actions:
            try:
                tool = self._create_action_tool(action, user_id, session_id)
                if tool:
                    tools.append(tool)
            except Exception as exc:
                logger.error(
                    "Failed to create action tool %s: %s",
                    action.get("name"),
                    exc,
                    exc_info=True
                )

        return tools

    def _create_action_tool(
        self,
        action: Dict[str, Any],
        user_id: str,
        session_id: Optional[str] = None
    ) -> Optional[BaseTool]:
        """
        Create a LangChain tool from an action.

        Example:
        - Action name: "send_slack_notification"
        - Tool name: "execute_send_slack_notification"
        - Description: "Send a notification to Slack channel"

        Args:
            action: Action record from database
            user_id: User ID for context
            session_id: Chat session ID for context

        Returns:
            StructuredTool or None if creation fails
        """
        from langchain_core.tools import StructuredTool
        from pydantic import BaseModel, Field, create_model
        from api.services.action_executor import ActionExecutor
        import re

        action_id = action["id"]
        action_name = action["name"]
        action_type = action["action_type"]
        description = action.get("description") or f"Execute {action_name} action"

        # Create executor
        executor = ActionExecutor()

        # Create async runner function
        async def action_runner(**kwargs):
            """Execute action with provided context."""
            try:
                result = await executor.execute_action(
                    action_id=action_id,
                    context=kwargs,
                    user_id=user_id,
                    chat_session_id=session_id,
                    trigger_event="chat.command"
                )

                # Return formatted result
                return json.dumps({
                    "success": result.status == "success",
                    "status": result.status,
                    "output": result.output_data,
                    "error": result.error_message,
                    "execution_time_ms": result.execution_time_ms,
                }, indent=2)

            except Exception as e:
                return json.dumps({
                    "success": False,
                    "error": str(e)
                }, indent=2)

        # Generate dynamic args schema from body template
        args_schema = self._generate_action_tool_schema(action)

        try:
            return StructuredTool.from_function(
                coroutine=action_runner,  # Use coroutine parameter for async functions
                name=f"execute_{action_name}",
                description=description,
                args_schema=args_schema,
            )
        except Exception as e:
            logger.error(f"Failed to create tool for action {action_name}: {e}")
            return None

    def _generate_action_tool_schema(self, action: Dict[str, Any]) -> type[BaseModel]:
        """
        Generate Pydantic schema for action tool args based on body template.

        Extracts placeholder variables from body_template and creates a schema.

        Args:
            action: Action record with body_template

        Returns:
            Pydantic BaseModel class for tool args
        """
        from pydantic import BaseModel, Field, create_model
        import re

        # Default schema with generic context field
        default_schema = create_model(
            "ActionInput",
            **{
                "context": (str, Field(default="{}", description="JSON context for action execution"))
            }
        )

        # Extract placeholders from body template
        body_template_str = action.get("body_template")
        if not body_template_str:
            return default_schema

        try:
            # Parse body template
            body_template = json.loads(body_template_str) if isinstance(body_template_str, str) else body_template_str

            # Extract all {{variable}} placeholders
            template_str = json.dumps(body_template)
            placeholders = re.findall(r'\{\{(\w+)\}\}', template_str)

            if not placeholders:
                return default_schema

            # Create schema with one field per placeholder
            fields = {}
            for placeholder in set(placeholders):  # Deduplicate
                fields[placeholder] = (
                    str,
                    Field(default="", description=f"Value for {placeholder}")
                )

            return create_model("ActionInput", **fields)

        except Exception as e:
            logger.warning(f"Failed to generate action tool schema: {e}")
            return default_schema

    # ------------------------------------------------------------------
    # Permissions
    # ------------------------------------------------------------------

    async def _filter_by_permissions(
        self,
        tools: List[BaseTool],
        user_id: str,
    ) -> List[BaseTool]:
        """
        Filter tools based on tool_permissions table.

        Resolution order:
        1. User-specific permission (highest priority)
        2. Role-based permission
        3. No entry => allowed by default
        """
        # Build permission map from DB
        perm_map = await self._load_permission_map(user_id)
        if not perm_map:
            # No permissions defined at all – everything allowed
            return tools

        allowed: List[BaseTool] = []
        for tool in tools:
            # Get registry ID from metadata/config/_tool_meta
            tool_id = None
            if hasattr(tool, 'metadata') and isinstance(tool.metadata, dict):
                tool_id = tool.metadata.get('_registry_id')
            elif hasattr(tool, 'config') and isinstance(tool.config, dict):
                tool_id = tool.config.get('_registry_id')
            elif hasattr(tool, '_tool_meta'):
                tool_id = tool.__dict__.get('_tool_meta', {}).get('registry_id')

            if tool_id and tool_id in perm_map:
                perm = perm_map[tool_id]
                if not perm.get("allowed", True):
                    continue
                # Attach rate limit from permission for later wrapping
                rate_limit = perm.get("rate_limit")
                if rate_limit:
                    tool.__dict__['_perm_rate_limit'] = rate_limit
            # No permission entry or source tool without registry id => allowed
            allowed.append(tool)

        return allowed

    async def _load_permission_map(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        """Load permission entries for user + their roles."""
        try:
            # Get user roles
            roles_sql = "SELECT role FROM user_roles WHERE user_id = :user_id"
            role_rows = await repo_query(roles_sql, {"user_id": user_id})
        except Exception:
            # user_roles table may not exist
            role_rows = []

        role_list = [r["role"] for r in role_rows] if role_rows else []

        try:
            # Build dynamic query for user + roles
            if role_list:
                placeholders = ", ".join(f":role_{i}" for i in range(len(role_list)))
                perm_sql = f"""
                    SELECT tool_id, allowed, rate_limit, custom_config
                    FROM tool_permissions
                    WHERE user_id = :user_id OR role IN ({placeholders})
                    ORDER BY
                        CASE WHEN user_id IS NOT NULL THEN 1 ELSE 2 END
                """
                params: Dict[str, Any] = {"user_id": user_id}
                for i, role in enumerate(role_list):
                    params[f"role_{i}"] = role
            else:
                perm_sql = """
                    SELECT tool_id, allowed, rate_limit, custom_config
                    FROM tool_permissions
                    WHERE user_id = :user_id
                    ORDER BY
                        CASE WHEN user_id IS NOT NULL THEN 1 ELSE 2 END
                """
                params = {"user_id": user_id}

            rows = await repo_query(perm_sql, params)
        except Exception:
            return {}

        perm_map: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            tid = row["tool_id"]
            if tid not in perm_map:  # First match wins (user > role)
                perm_map[tid] = row

        return perm_map

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _apply_rate_limits(
        self,
        tools: List[BaseTool],
        user_id: str,
    ) -> List[BaseTool]:
        """Wrap tools that have a rate limit with RateLimitedTool."""
        result: List[BaseTool] = []
        for tool in tools:
            rate_limit = getattr(tool, "_perm_rate_limit", None)
            if rate_limit:
                tool = RateLimitedTool(tool, calls_per_minute=rate_limit, user_id=user_id)
            result.append(tool)
        return result


# ============================================================================
# Singleton accessor
# ============================================================================

_tool_factory: Optional[ToolFactory] = None


def get_tool_factory() -> ToolFactory:
    """Get or create the singleton ToolFactory instance."""
    global _tool_factory
    if _tool_factory is None:
        _tool_factory = ToolFactory()
    return _tool_factory


async def create_tools_for_team(
    team_id: str,
    source_ids: Optional[List[str]] = None
) -> List[BaseTool]:
    """
    Create tools for an agent team.

    Args:
        team_id: Team ID
        source_ids: Optional list of source IDs to create tools from

    Returns:
        List of LangChain tools
    """
    tools: List[BaseTool] = []
    tool_ids_seen = set()

    # Get team's agents and their tool configurations
    try:
        agent_rows = await repo_query(
            "SELECT id, tool_ids FROM agent_instances WHERE team_id = :team_id",
            {"team_id": team_id}
        )

        logger.info(f"Found {len(agent_rows)} agents for team {team_id}")

        # Collect all tool IDs and source IDs from agents
        agent_tool_ids = []
        agent_source_ids = []

        for agent in agent_rows:
            if agent.get("tool_ids"):
                try:
                    ids = json.loads(agent["tool_ids"]) if isinstance(agent["tool_ids"], str) else agent["tool_ids"]
                    for id_val in ids:
                        if isinstance(id_val, str):
                            if id_val.startswith("source:"):
                                # Extract source ID
                                source_id = id_val.replace("source:", "")
                                agent_source_ids.append(source_id)
                                logger.info(f"Agent has source: {source_id}")
                            else:
                                # Regular tool ID
                                agent_tool_ids.append(id_val)
                                logger.info(f"Agent has tool: {id_val}")
                except Exception as e:
                    logger.warning(f"Failed to parse agent tool_ids: {e}")

        logger.info(f"Agent tools: {agent_tool_ids}, Agent sources: {agent_source_ids}")

    except Exception as e:
        logger.warning(f"Failed to get agents for team {team_id}: {e}")
        agent_tool_ids = []
        agent_source_ids = []

    # Get registry tools (globally enabled)
    factory = get_tool_factory()
    registry_tools = await factory._get_registry_tools()

    # Filter registry tools to only those configured for agents
    if agent_tool_ids:
        for tool in registry_tools:
            # Get registry ID from tool metadata
            tool_id = None
            if hasattr(tool, 'metadata') and isinstance(tool.metadata, dict):
                tool_id = tool.metadata.get('_registry_id')
            elif hasattr(tool, 'config') and isinstance(tool.config, dict):
                tool_id = tool.config.get('_registry_id')
            elif hasattr(tool, '_tool_meta'):
                tool_id = tool.__dict__.get('_tool_meta', {}).get('registry_id')

            if tool_id and tool_id in agent_tool_ids:
                tools.append(tool)
                tool_ids_seen.add(tool_id)
                logger.info(f"Added registry tool: {tool.name} (id={tool_id})")
    else:
        # No specific tools configured - add all registry tools
        tools.extend(registry_tools)
        logger.info(f"No agent tools configured, added all {len(registry_tools)} registry tools")

    # Get MCP tools — scoped to the team's owner so per-user OAuth tokens
    # are honored. Falls back to "system" for legacy teams without a created_by.
    team_owner_rows = await repo_query(
        "SELECT created_by FROM agent_teams WHERE id = :team_id",
        {"team_id": team_id},
    )
    user_id = (team_owner_rows[0].get("created_by") if team_owner_rows else None) or "system"
    mcp_tools = await factory._get_mcp_tools(user_id)
    tools.extend(mcp_tools)

    # Get source-based tools from agent-configured sources
    if agent_source_ids:
        try:
            from api.services.data_query_tools import create_tools_for_sources
            source_tools = await create_tools_for_sources(agent_source_ids, None)
            tools.extend(source_tools)
            logger.info(f"Added {len(source_tools)} source-based tools from agent sources")
        except Exception as e:
            logger.warning(f"Failed to create source tools from agent sources: {e}")

    # Also get source-based tools from team's notebook if available
    try:
        # Get team's notebook_id
        team_rows = await repo_query(
            "SELECT notebook_id FROM agent_teams WHERE id = :id",
            {"id": team_id}
        )

        if team_rows and team_rows[0].get("notebook_id"):
            notebook_id = team_rows[0]["notebook_id"]
            from api.services.data_query_tools import create_tools_for_notebook
            source_tools = await create_tools_for_notebook(notebook_id, None)
            tools.extend(source_tools)
            logger.info(f"Added {len(source_tools)} source tools from notebook {notebook_id}")

    except Exception as e:
        logger.warning(f"Failed to create source tools for team notebook: {e}")

    logger.info(f"Created {len(tools)} total tools for team {team_id}")

    return tools
