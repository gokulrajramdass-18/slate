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

    # Create tool class dynamically
    class DynamicHANATool(BaseTool):
        name: str = tool_name
        description: str = description
        args_schema: type = InputModel

        # Store metadata for execution
        _source_id: str = metadata["source_id"]
        _table_name: str = metadata["table_name"]
        _content_columns: List[str] = metadata["content_columns"]
        _connection_config: Dict[str, Any] = metadata["connection_config"]

        class Config:
            arbitrary_types_allowed = True

        def _run(self, **kwargs) -> str:
            raise NotImplementedError("Use async version (_arun)")

        async def _arun(self, **kwargs) -> str:
            """Execute HANA query via HANAToolExecutor"""
            try:
                from api.services.hana_tool_executor import HANAToolExecutor

                logger.info(f"[HANATool] Executing {tool_name} with params: {kwargs}")

                # Build SQL query from parameters
                executor = HANAToolExecutor(
                    source_id=self._source_id,
                    connection_config=self._connection_config
                )

                # Extract parameters
                columns = kwargs.get("columns") or self._content_columns
                where_clause = kwargs.get("where_clause")
                group_by = kwargs.get("group_by")
                order_by = kwargs.get("order_by")
                limit = kwargs.get("limit", 50)

                # Execute query
                result = await executor.execute_query(
                    table_name=self._table_name,
                    columns=columns,
                    where_clause=where_clause,
                    group_by=group_by,
                    order_by=order_by,
                    limit=limit
                )

                logger.info(f"[HANATool] Query returned {len(result.get('rows', []))} rows")

                return json.dumps(result, indent=2)

            except Exception as e:
                logger.error(f"[HANATool] Query failed: {e}", exc_info=True)
                return json.dumps({
                    "success": False,
                    "error": str(e),
                    "table": self._table_name
                })

    return DynamicHANATool()
