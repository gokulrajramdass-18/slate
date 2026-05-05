"""
Tool Schema Converter

Converts LangChain StructuredTool (with Pydantic schemas) to Anthropic tool format
for native Claude tool use.
"""

import logging
from typing import Dict, Any, List, Optional
from langchain.tools import BaseTool
from pydantic import BaseModel

logger = logging.getLogger(__name__)


def langchain_tool_to_anthropic_schema(tool: BaseTool) -> Dict[str, Any]:
    """
    Convert LangChain tool to Anthropic tool schema.

    Args:
        tool: LangChain BaseTool with optional args_schema (Pydantic model)

    Returns:
        Dictionary with Anthropic tool format:
        {
            "name": str,
            "description": str,
            "input_schema": {
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }

    Example:
        >>> from langchain.tools import BaseTool
        >>> from pydantic import BaseModel, Field
        >>>
        >>> class QueryInput(BaseModel):
        >>>     table_name: str = Field(description="HANA table name")
        >>>     query: str = Field(description="SQL query")
        >>>
        >>> class HANAQueryTool(BaseTool):
        >>>     name = "query_hana"
        >>>     description = "Query HANA database"
        >>>     args_schema = QueryInput
        >>>
        >>> tool = HANAQueryTool()
        >>> schema = langchain_tool_to_anthropic_schema(tool)
        >>> # Returns:
        >>> # {
        >>> #     "name": "query_hana",
        >>> #     "description": "Query HANA database",
        >>> #     "input_schema": {
        >>> #         "type": "object",
        >>> #         "properties": {
        >>> #             "table_name": {"type": "string", "description": "HANA table name"},
        >>> #             "query": {"type": "string", "description": "SQL query"}
        >>> #         },
        >>> #         "required": ["table_name", "query"]
        >>> #     }
        >>> # }
    """
    schema = {
        "name": tool.name,
        "description": tool.description or "No description provided"
    }

    # Extract input schema from Pydantic model
    if hasattr(tool, "args_schema") and tool.args_schema:
        try:
            # Get JSON schema from Pydantic model
            json_schema = tool.args_schema.model_json_schema()

            # Convert to Anthropic format
            input_schema = {
                "type": "object",
                "properties": _clean_properties(json_schema.get("properties", {})),
                "required": json_schema.get("required", [])
            }

            # Add schema-level description if present
            if "description" in json_schema:
                input_schema["description"] = json_schema["description"]

            schema["input_schema"] = input_schema

        except Exception as e:
            logger.warning(
                f"Failed to convert schema for tool '{tool.name}': {e}. "
                "Using empty schema."
            )
            schema["input_schema"] = {"type": "object", "properties": {}}
    else:
        # No args_schema - tool takes no parameters
        schema["input_schema"] = {"type": "object", "properties": {}}

    return schema


def _clean_properties(properties: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean and simplify property definitions for Anthropic.

    Removes Pydantic-specific fields and simplifies types.

    Args:
        properties: Property definitions from Pydantic schema

    Returns:
        Cleaned property definitions
    """
    cleaned = {}

    for prop_name, prop_def in properties.items():
        clean_prop = {}

        # Copy basic fields
        if "type" in prop_def:
            clean_prop["type"] = _map_type(prop_def["type"])

        if "description" in prop_def:
            clean_prop["description"] = prop_def["description"]

        # Handle enum values
        if "enum" in prop_def:
            clean_prop["enum"] = prop_def["enum"]

        # Handle default values
        if "default" in prop_def:
            clean_prop["default"] = prop_def["default"]

        # Handle array items
        if prop_def.get("type") == "array" and "items" in prop_def:
            clean_prop["items"] = _clean_nested_schema(prop_def["items"])

        # Handle object properties (nested schemas)
        if prop_def.get("type") == "object" and "properties" in prop_def:
            clean_prop["properties"] = _clean_properties(prop_def["properties"])
            if "required" in prop_def:
                clean_prop["required"] = prop_def["required"]

        # Handle anyOf/oneOf (union types)
        if "anyOf" in prop_def:
            # Simplify union types - take first non-null type
            types = [t for t in prop_def["anyOf"] if t.get("type") != "null"]
            if types:
                clean_prop.update(_clean_nested_schema(types[0]))

        if "oneOf" in prop_def:
            # Similar to anyOf
            types = [t for t in prop_def["oneOf"] if t.get("type") != "null"]
            if types:
                clean_prop.update(_clean_nested_schema(types[0]))

        cleaned[prop_name] = clean_prop

    return cleaned


def _clean_nested_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean nested schema definition.

    Args:
        schema: Nested schema dict

    Returns:
        Cleaned schema
    """
    clean = {}

    if "type" in schema:
        clean["type"] = _map_type(schema["type"])

    if "description" in schema:
        clean["description"] = schema["description"]

    if "enum" in schema:
        clean["enum"] = schema["enum"]

    # Handle nested properties
    if schema.get("type") == "object" and "properties" in schema:
        clean["properties"] = _clean_properties(schema["properties"])
        if "required" in schema:
            clean["required"] = schema["required"]

    # Handle array items
    if schema.get("type") == "array" and "items" in schema:
        clean["items"] = _clean_nested_schema(schema["items"])

    return clean


def _map_type(pydantic_type: str) -> str:
    """
    Map Pydantic types to JSON Schema types.

    Args:
        pydantic_type: Pydantic type string

    Returns:
        JSON Schema type string
    """
    type_mapping = {
        "string": "string",
        "integer": "integer",
        "number": "number",
        "boolean": "boolean",
        "array": "array",
        "object": "object",
        "null": "null",
    }

    return type_mapping.get(pydantic_type, "string")


def batch_convert_tools(tools: List[BaseTool]) -> List[Dict[str, Any]]:
    """
    Convert multiple LangChain tools to Anthropic format.

    Args:
        tools: List of LangChain BaseTool instances

    Returns:
        List of Anthropic tool schemas

    Example:
        >>> tools = [hana_tool, api_tool, web_search_tool]
        >>> anthropic_tools = batch_convert_tools(tools)
        >>> # Pass to Claude:
        >>> client.messages.create(
        >>>     model="claude-3-5-sonnet-20241022",
        >>>     tools=anthropic_tools,
        >>>     ...
        >>> )
    """
    converted = []

    for tool in tools:
        try:
            schema = langchain_tool_to_anthropic_schema(tool)
            converted.append(schema)
        except Exception as e:
            logger.error(f"Failed to convert tool '{tool.name}': {e}")
            # Continue with other tools

    logger.info(f"Converted {len(converted)}/{len(tools)} tools to Anthropic format")
    return converted


def validate_anthropic_schema(schema: Dict[str, Any]) -> bool:
    """
    Validate that a schema conforms to Anthropic tool format.

    Args:
        schema: Tool schema to validate

    Returns:
        True if valid, False otherwise
    """
    required_fields = ["name", "input_schema"]

    # Check required fields
    for field in required_fields:
        if field not in schema:
            logger.warning(f"Schema missing required field: {field}")
            return False

    # Validate input_schema structure
    input_schema = schema["input_schema"]
    if not isinstance(input_schema, dict):
        logger.warning("input_schema must be a dictionary")
        return False

    if input_schema.get("type") != "object":
        logger.warning("input_schema type must be 'object'")
        return False

    if "properties" not in input_schema:
        logger.warning("input_schema missing 'properties'")
        return False

    return True
