"""
Tool Discovery Pipeline

Discovers and assembles tools from multiple sources at runtime:
- Tool Registry (globally enabled tools)
- Notebook Sources (HANA tables, APIs, files)
- MCP Servers (external tool providers)
- Custom Tools (user-defined tools)
"""

from typing import List, Dict, Any, Optional
from langchain.tools import BaseTool
import logging

logger = logging.getLogger(__name__)


class ToolDiscoveryPipeline:
    """
    Discovers and assembles tools from multiple sources at runtime.

    This allows tools to be dynamically configured based on:
    - Notebook context (what data sources are available)
    - User permissions (what tools user is allowed to use)
    - Session configuration (tool whitelist/blacklist)
    """

    def __init__(self):
        self._tool_factory = None

    async def discover_tools(
        self,
        notebook_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        enabled_tool_ids: Optional[List[str]] = None,
        disabled_tool_ids: Optional[List[str]] = None,
    ) -> List[BaseTool]:
        """
        Discover and assemble tools from all sources.

        Args:
            notebook_id: Notebook ID for context (determines data sources)
            user_id: User ID for permissions
            session_id: Session ID for observability
            enabled_tool_ids: Explicitly enable these tool IDs (whitelist)
            disabled_tool_ids: Explicitly disable these tool IDs (blacklist)

        Returns:
            List of BaseTool instances ready for Deep Agent
        """
        all_tools = []

        # 1. Discover from Tool Registry (web search, calculator, etc.)
        registry_tools = await self._discover_registry_tools(
            user_id=user_id,
            enabled_tool_ids=enabled_tool_ids,
            disabled_tool_ids=disabled_tool_ids
        )
        all_tools.extend(registry_tools)
        logger.info(f"[ToolDiscovery] Discovered {len(registry_tools)} registry tools")

        # 2. Discover from Notebook Sources (HANA tables, APIs, search)
        if notebook_id:
            source_tools = await self._discover_source_tools(
                notebook_id=notebook_id,
                session_id=session_id,
                enabled_tool_ids=enabled_tool_ids,
                disabled_tool_ids=disabled_tool_ids
            )
            all_tools.extend(source_tools)
            logger.info(f"[ToolDiscovery] Discovered {len(source_tools)} source-based tools")

        # 3. Discover from MCP Servers (per-user — only servers this user
        #    has authenticated against will yield tools)
        mcp_tools = await self._discover_mcp_tools(
            user_id=user_id,
            enabled_tool_ids=enabled_tool_ids,
            disabled_tool_ids=disabled_tool_ids
        )
        all_tools.extend(mcp_tools)
        logger.info(f"[ToolDiscovery] Discovered {len(mcp_tools)} MCP tools")

        # 4. Apply filters
        filtered_tools = await self._apply_filters(
            tools=all_tools,
            user_id=user_id,
            enabled_tool_ids=enabled_tool_ids,
            disabled_tool_ids=disabled_tool_ids
        )

        logger.info(
            f"[ToolDiscovery] Complete: {len(filtered_tools)} tools available "
            f"(from {len(all_tools)} discovered)"
        )

        return filtered_tools

    async def _discover_registry_tools(
        self,
        user_id: Optional[str] = None,
        enabled_tool_ids: Optional[List[str]] = None,
        disabled_tool_ids: Optional[List[str]] = None
    ) -> List[BaseTool]:
        """Discover tools from tool_registry table"""
        try:
            from api.services.tool_factory import get_tool_factory

            if not self._tool_factory:
                self._tool_factory = get_tool_factory()

            # Get all enabled registry tools
            registry_tools = await self._tool_factory._get_registry_tools()
            return registry_tools

        except Exception as e:
            logger.warning(f"[ToolDiscovery] Failed to discover registry tools: {e}")
            return []

    async def _discover_source_tools(
        self,
        notebook_id: str,
        session_id: Optional[str] = None,
        enabled_tool_ids: Optional[List[str]] = None,
        disabled_tool_ids: Optional[List[str]] = None
    ) -> List[BaseTool]:
        """Discover tools from notebook sources (HANA, APIs, search)"""
        tools = []

        try:
            # Import tool wrappers
            from deep_agents_integration.deep_agents_tools.search_tools import NotebookSearchTool

            # Add search tool (always available if notebook exists)
            search_tool = NotebookSearchTool(
                notebook_id=notebook_id,
                session_id=session_id
            )
            tools.append(search_tool)
            logger.info(f"[ToolDiscovery] Added search tool for notebook {notebook_id}")

        except ImportError as e:
            logger.warning(f"[ToolDiscovery] Search tools not available: {e}")

        try:
            # Add HANA table tools
            from deep_agents_integration.deep_agents_tools.hana_tools import create_hana_tools_for_deep_agent

            hana_tools = await create_hana_tools_for_deep_agent(notebook_id)
            tools.extend(hana_tools)
            logger.info(f"[ToolDiscovery] Added {len(hana_tools)} HANA tools")

        except ImportError as e:
            logger.warning(f"[ToolDiscovery] HANA tools not available: {e}")
        except Exception as e:
            logger.warning(f"[ToolDiscovery] Failed to discover HANA tools: {e}")

        return tools

    async def _discover_mcp_tools(
        self,
        user_id: Optional[str] = None,
        enabled_tool_ids: Optional[List[str]] = None,
        disabled_tool_ids: Optional[List[str]] = None
    ) -> List[BaseTool]:
        """Discover tools from MCP servers, scoped to this user's auth state."""
        try:
            if not self._tool_factory:
                from api.services.tool_factory import get_tool_factory
                self._tool_factory = get_tool_factory()

            # Without a user_id we can't load OAuth tokens, so MCP tools are
            # silently empty. This is the correct behavior for unauthenticated
            # contexts (e.g. system jobs that don't have a calling user).
            if not user_id:
                return []

            return await self._tool_factory._get_mcp_tools(user_id)

        except Exception as e:
            logger.warning(f"[ToolDiscovery] Failed to discover MCP tools: {e}")
            return []

    async def _apply_filters(
        self,
        tools: List[BaseTool],
        user_id: Optional[str] = None,
        enabled_tool_ids: Optional[List[str]] = None,
        disabled_tool_ids: Optional[List[str]] = None
    ) -> List[BaseTool]:
        """Apply whitelist/blacklist filters"""
        filtered = []

        for tool in tools:
            tool_id = self._get_tool_id(tool)

            # Apply blacklist
            if disabled_tool_ids and tool_id in disabled_tool_ids:
                logger.debug(f"[ToolDiscovery] Tool {tool_id} disabled by blacklist")
                continue

            # Apply whitelist (if specified)
            if enabled_tool_ids:
                # Support wildcards (e.g., "hana_*")
                matches = False
                for pattern in enabled_tool_ids:
                    if pattern.endswith("*"):
                        prefix = pattern[:-1]
                        if tool_id.startswith(prefix):
                            matches = True
                            break
                    elif pattern == tool_id:
                        matches = True
                        break

                if not matches:
                    logger.debug(f"[ToolDiscovery] Tool {tool_id} not in whitelist")
                    continue

            filtered.append(tool)

        return filtered

    def _get_tool_id(self, tool: BaseTool) -> str:
        """Get tool ID from metadata"""
        # Try to get registry ID
        if hasattr(tool, 'metadata') and isinstance(tool.metadata, dict):
            return tool.metadata.get('_registry_id', tool.name)
        elif hasattr(tool, 'config') and isinstance(tool.config, dict):
            return tool.config.get('_registry_id', tool.name)
        elif hasattr(tool, '_tool_meta'):
            return tool.__dict__.get('_tool_meta', {}).get('registry_id', tool.name)

        # Fallback to tool name
        return tool.name


# Singleton
_discovery_pipeline: Optional[ToolDiscoveryPipeline] = None


def get_tool_discovery_pipeline() -> ToolDiscoveryPipeline:
    """Get or create singleton discovery pipeline"""
    global _discovery_pipeline
    if _discovery_pipeline is None:
        _discovery_pipeline = ToolDiscoveryPipeline()
    return _discovery_pipeline
