"""
MCP Tool Wrapper for LangChain

Provides a LangChain tool implementation that wraps MCP server tools,
making them available to LangGraph agents.
"""

import json
import logging
from typing import Any, Dict, Optional
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

from api.services.mcp_client import mcp_pool, effective_token_user_id

logger = logging.getLogger(__name__)


async def execute_mcp_tool(
    server_id: str,
    server_config: Dict[str, Any],
    tool_name: str,
    user_id: Optional[str] = None,
    **kwargs,
) -> str:
    """
    Execute an MCP tool on behalf of `user_id`.

    For user-mode OAuth servers, `user_id` selects the calling user's
    access token. For system-mode servers it's collapsed to the shared
    `__system__` sentinel so all callers hit the same pooled client and
    the same token row — keeping the per-instance refresh lock effective.

    Args:
        server_id: MCP server ID
        server_config: Server configuration (must contain `oauth_mode`)
        tool_name: Name of the tool to execute
        user_id: Authenticated user calling the tool (required for OAuth)
        **kwargs: Tool arguments
    """
    server_name = server_config.get("name", "Unknown Server")

    # Substitute user_id once at the boundary: from here down, the pool,
    # the client, and the refresh path all see the same value.
    pool_user_id = effective_token_user_id(server_config, user_id)

    try:
        # Pooled client keyed on (server_id, pool_user_id). Non-OAuth
        # servers ignore user_id; system-mode servers collapse to one
        # entry; user-mode servers stay isolated per user.
        client = await mcp_pool.get_client(
            server_id, server_config, user_id=pool_user_id
        )

        # Filter out None values to avoid "None is not of type 'integer'" errors
        # Many APIs require optional parameters to be omitted entirely, not sent as null
        filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}

        # Call tool on MCP server with filtered arguments
        result = await client.call_tool(tool_name, filtered_kwargs)

        # Format result
        if isinstance(result, list):
            # MCP returns list of content items
            return format_mcp_content(result)
        elif isinstance(result, dict):
            return json.dumps(result, indent=2)
        else:
            return str(result)

    except PermissionError:
        # Raised by the pool when no per-user OAuth token exists.
        return (
            f"You haven't authenticated with '{server_name}' yet. "
            "Please connect this MCP server in Settings → MCP Servers."
        )

    except ConnectionError as e:
        # OAuth or connection error
        error_msg = str(e)
        if "Authentication failed" in error_msg:
            return f"Authentication failed for MCP server '{server_name}'. Please reconnect the server in Settings."
        return f"MCP server '{server_name}' is currently unavailable. Please check the connection status in Settings."

    except RuntimeError as e:
        # Client not connected
        if "not connected" in str(e).lower():
            return f"MCP server '{server_name}' is not connected. Please check the server status in Settings."
        error_msg = f"Error executing tool '{tool_name}' on '{server_name}': {str(e)}"
        logger.error(error_msg)
        return error_msg

    except Exception as e:
        # Generic error
        error_msg = f"Error executing tool '{tool_name}' on MCP server '{server_name}': {str(e)}"
        logger.error(error_msg, exc_info=True)
        return error_msg


def format_mcp_content(content_list: list) -> str:
    """
    Format MCP content response.

    MCP servers return content as a list of typed items (text, image, resource).
    This method formats them as a human-readable string.

    Args:
        content_list: List of content items from MCP server

    Returns:
        Formatted string representation
    """
    parts = []

    for item in content_list:
        content_type = item.get("type", "")

        if content_type == "text":
            # Plain text content
            text = item.get("text", "")
            parts.append(text)

        elif content_type == "image":
            # Image content (base64 or URL)
            image_data = item.get("data", "")
            image_mime = item.get("mimeType", "image/png")
            # Truncate for readability
            preview = image_data[:50] + "..." if len(image_data) > 50 else image_data
            parts.append(f"[Image ({image_mime}): {preview}]")

        elif content_type == "resource":
            # Resource reference
            uri = item.get("uri", "")
            resource_text = item.get("text", "")
            if resource_text:
                parts.append(f"[Resource: {uri}]\n{resource_text}")
            else:
                parts.append(f"[Resource: {uri}]")

        else:
            # Unknown content type - dump as JSON
            parts.append(json.dumps(item))

    return "\n\n".join(parts) if parts else ""


def create_mcp_tool(
    server_id: str,
    server_config: Dict[str, Any],
    tool_data: Dict[str, Any],
    user_id: Optional[str] = None,
) -> StructuredTool:
    """
    Factory function to create LangChain StructuredTool from MCP tool data.

    The tool is bound to a specific user via closure: when the agent invokes
    the tool, the call routes to that user's connection pool entry (and
    therefore that user's OAuth token). Building separate tool instances per
    user is what keeps two simultaneous agent runs from sharing an identity.

    Args:
        server_id: MCP server identifier
        server_config: Server configuration dict
        tool_data: Tool data from mcp_tools table
        user_id: Authenticated user the tool will run as (required for OAuth)

    Returns:
        StructuredTool instance
    """
    tool_name = tool_data["tool_name"]
    server_name = server_config.get("name", "Unknown")

    # Sanitize server name for tool ID
    server_name_sanitized = server_name.lower().replace(" ", "_").replace("-", "_")
    server_name_sanitized = "".join(c for c in server_name_sanitized if c.isalnum() or c == "_")

    # Create unique tool name
    full_tool_name = f"mcp_{server_name_sanitized}_{tool_name}"

    # Get description
    description = tool_data.get("description", f"Execute {tool_name}")
    description_with_source = f"{description} (from MCP server: {server_name})"

    # Parse input schema
    input_schema_dict = json.loads(tool_data.get("input_schema") or "{}")

    # Create Pydantic model from input schema
    # Extract properties and required fields from the MCP tool schema
    properties = input_schema_dict.get("properties", {})
    required_fields = input_schema_dict.get("required", [])

    # Build field definitions for create_model
    # create_model expects: field_name=(type, default_value)
    field_definitions = {}

    for field_name, field_info in properties.items():
        field_type = Any  # Default to Any for flexibility
        field_description = field_info.get("description", "")
        is_required = field_name in required_fields

        # Create Field with description
        if is_required:
            field_definitions[field_name] = (field_type, Field(..., description=field_description))
        else:
            field_definitions[field_name] = (field_type, Field(None, description=field_description))

    # Create dynamic Pydantic model with proper fields
    if field_definitions:
        # Use create_model with field definitions
        MCPToolArgs = create_model(
            "MCPToolArgs",
            **field_definitions
        )
        # Don't set extra='allow' - it causes LangChain tool binding to fail
        # LangChain expects 'extra_data' field which Pydantic v2 doesn't create
    else:
        # No fields defined, create simple model with no extra fields allowed
        # This is safer and avoids LangChain/Pydantic compatibility issues
        class MCPToolArgs(BaseModel):
            pass

    # Create the async function that will be wrapped. Capture user_id in
    # the closure so the tool, no matter where it's executed downstream,
    # invokes the MCP server as the user it was minted for.
    async def mcp_tool_func(**kwargs) -> str:
        """Execute MCP tool with provided arguments"""
        return await execute_mcp_tool(
            server_id=server_id,
            server_config=server_config,
            tool_name=tool_name,
            user_id=user_id,
            **kwargs,
        )

    # Create StructuredTool using from_function
    # This avoids the BaseTool inheritance that causes recursion
    tool = StructuredTool.from_function(
        name=full_tool_name,
        description=description_with_source,
        func=None,  # No sync version
        coroutine=mcp_tool_func,  # Async version
        args_schema=MCPToolArgs,  # Simple schema
        return_direct=False,
    )

    # Add metadata for identification
    tool.metadata = {
        "server_id": server_id,
        "server_name": server_name,
        "tool_name": tool_name,
        "server_status": server_config.get("status", "unknown"),
        "source": "mcp"
    }

    return tool

