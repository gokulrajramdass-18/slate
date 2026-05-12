"""
HANA Tools for Deep Agents

Adapts existing HANAToolGenerator output as LangChain tools
for Deep Agent usage.
"""

from langchain.tools import BaseTool
from pydantic import Field, create_model
from typing import List, Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)


async def create_hana_tools_for_deep_agent(notebook_id: str) -> List[BaseTool]:
    """
    Create HANA tools for Deep Agent from notebook sources.

    Wraps existing HANAToolGenerator output as LangChain BaseTool instances.
    No changes to HANAToolGenerator or HANAToolExecutor required.

    Args:
        notebook_id: Notebook UUID

    Returns:
        List of HANA query tools as BaseTool instances
    """
    try:
        from api.services.hana_tool_generator import HANAToolGenerator

        # Use existing generator
        tool_schemas = await HANAToolGenerator.generate_tools_for_notebook(notebook_id)

        if not tool_schemas:
            logger.info(f"[HANATools] No HANA sources in notebook {notebook_id}")
            return []

        tools = []
        for schema in tool_schemas:
            try:
                tool = _create_hana_tool_from_schema(schema)
                tools.append(tool)
            except Exception as e:
                logger.warning(f"[HANATools] Failed to create tool from schema: {e}")
                continue

        logger.info(f"[HANATools] Created {len(tools)} HANA tools for notebook {notebook_id}")
        return tools

    except ImportError as e:
        logger.warning(f"[HANATools] HANAToolGenerator not available: {e}")
        return []
    except Exception as e:
        logger.error(f"[HANATools] Failed to create HANA tools: {e}", exc_info=True)
        return []


def _create_hana_tool_from_schema(schema: Dict[str, Any]) -> BaseTool:
    """
    Convert HANAToolGenerator schema to LangChain BaseTool.

    Args:
        schema: Tool schema from HANAToolGenerator (with _metadata)

    Returns:
        LangChain BaseTool instance
    """
    tool_name = schema["name"]
    description = schema["description"]
    metadata = schema["_metadata"]

    # Create dynamic Pydantic model for input validation
    input_fields = {}
    properties = schema["input_schema"]["properties"]

    for prop_name, prop_schema in properties.items():
        prop_type = prop_schema["type"]
        prop_desc = prop_schema["description"]

        # Map JSON schema types to Python types
        if prop_type == "string":
            field_type = Optional[str]
        elif prop_type == "integer":
            field_type = Optional[int]
        elif prop_type == "array":
            field_type = Optional[List[str]]
        else:
            field_type = Optional[str]

        input_fields[prop_name] = (field_type, Field(default=None, description=prop_desc))

    # Create dynamic input model
    InputModel = create_model(f"{tool_name}_input", **input_fields)

    # Capture variables in closure for inner class (avoid scope issues)
    _tool_name = tool_name
    _tool_description = description
    _source_id = metadata["source_id"]
    _table_name = metadata["table_name"]
    _content_columns = metadata["content_columns"]
    _connection_config = metadata["connection_config"]

    # Create tool class dynamically
    class DynamicHANATool(BaseTool):
        name: str = _tool_name
        description: str = _tool_description
        args_schema: type = InputModel

        # Store metadata for execution (use class variables to avoid closure issues)
        source_id_value: str = _source_id
        table_name_value: str = _table_name
        content_columns_value: List[str] = _content_columns
        connection_config_value: Dict[str, Any] = _connection_config

        class Config:
            arbitrary_types_allowed = True

        def _run(self, **kwargs) -> str:
            raise NotImplementedError("Use async version (_arun)")

        async def _arun(self, **kwargs) -> str:
            """Execute HANA query via HANAToolExecutor"""
            try:
                from api.services.hana_tool_executor import HANAToolExecutor

                logger.info(f"[HANATool] Executing {_tool_name} with params: {kwargs}")

                # Build tool_call structure matching what HANAToolExecutor expects
                tool_call = {
                    "name": _tool_name,
                    "arguments": {
                        "columns": kwargs.get("columns") or [],
                        "where_clause": kwargs.get("where_clause") or "",
                        "group_by": kwargs.get("group_by") or "",
                        "order_by": kwargs.get("order_by") or "",
                        "limit": kwargs.get("limit", 50)
                    }
                }

                # Build tool_metadata structure matching what HANAToolExecutor expects
                tool_metadata = {
                    "source_id": self.source_id_value,
                    "table_name": self.table_name_value,
                    "content_columns": self.content_columns_value,
                    "connection_config": self.connection_config_value
                }

                # Execute query using the static method
                result = await HANAToolExecutor.execute_tool(tool_call, tool_metadata)

                logger.info(f"[HANATool] Query returned {len(result)} rows")

                # Format result for LangChain (rows + metadata)
                return json.dumps({
                    "rows": result,
                    "count": len(result),
                    "table": self.table_name_value
                }, indent=2)

            except Exception as e:
                logger.error(f"[HANATool] Query failed: {e}", exc_info=True)

                # Extract error details
                error_msg = str(e)
                error_type = "DatabaseError"

                # Check for specific error types
                if "insufficient privilege" in error_msg.lower():
                    error_type = "PermissionError"
                    friendly_msg = "The database user doesn't have permission to access this table."
                elif "connection" in error_msg.lower():
                    error_type = "ConnectionError"
                    friendly_msg = "Unable to connect to the database."
                elif "not found" in error_msg.lower():
                    error_type = "NotFoundError"
                    friendly_msg = "The requested table or resource was not found."
                else:
                    friendly_msg = "An error occurred while querying the database."

                return json.dumps({
                    "success": False,
                    "error": friendly_msg,
                    "error_details": error_msg,
                    "error_type": error_type,
                    "table": self.table_name_value,
                    "rows": [],
                    "count": 0
                })

    return DynamicHANATool()
