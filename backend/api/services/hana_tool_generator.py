"""
HANA Tool Generator Service

Dynamically generates OpenAI function calling tool schemas from HANA source configuration.
Tools are generated on-the-fly for each chat session based on current source settings.
"""

from typing import Dict, Any, List
import json
import re


class HANAToolGenerator:
    """Generate dynamic function calling tools for HANA table sources"""

    @staticmethod
    def _sanitize_function_name(table_name: str) -> str:
        """
        Sanitize table name to create valid function name

        Args:
            table_name: Raw table name (e.g., "SCHEMA.SALES_DATA")

        Returns:
            Sanitized function name (e.g., "query_schema_sales_data")
        """
        # Replace dots, spaces, and special chars with underscores
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', table_name.lower())
        # Remove consecutive underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')
        return f"query_{sanitized}"

    @staticmethod
    async def generate_tool_schema(source_id: str, source: dict) -> Dict[str, Any]:
        """
        Generate Anthropic tool schema for a HANA source

        Args:
            source_id: Source UUID
            source: Source dict with connection_config containing HANATableConfig

        Returns:
            Anthropic tool schema dict with _metadata for execution
        """
        # Parse connection config
        try:
            if isinstance(source["connection_config"], str):
                config_json = json.loads(source["connection_config"])
            else:
                config_json = source["connection_config"]
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"Invalid connection_config for source {source_id}: {str(e)}")

        # Extract table configuration
        table_name = config_json.get("table_name")
        if not table_name:
            raise ValueError(f"Missing table_name in connection_config for source {source_id}")

        content_columns = config_json.get("content_columns", [])
        if not content_columns:
            # Fallback to all columns if not specified
            content_columns = ["*"]

        # Generate function name (sanitize table name)
        func_name = HANAToolGenerator._sanitize_function_name(table_name)

        # Build description with column info
        columns_desc = ", ".join(content_columns)
        source_title = source.get("title", table_name)

        description = (
            f"Query the {table_name} table from HANA database ({source_title}). "
            f"Available columns: {columns_desc}. "
            f"Use this tool when the user asks questions about data in this table. "
            f"You can filter, aggregate, and sort the results."
        )

        # Tool schema (Anthropic format)
        tool_schema = {
            "name": func_name,
            "description": description,
            "input_schema": {
                "type": "object",
                "properties": {
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            f"Columns to SELECT. Available: {columns_desc}. "
                            f"Can use SQL expressions like 'SUM(quantity)', 'COUNT(*)', etc. "
                            f"Leave empty to select all configured columns."
                        )
                    },
                    "where_clause": {
                        "type": "string",
                        "description": (
                            "SQL WHERE condition (without 'WHERE' keyword). "
                            "Example: \"price > 100 AND order_date >= '2024-01-01'\". "
                            "Leave empty for no filtering."
                        )
                    },
                    "group_by": {
                        "type": "string",
                        "description": (
                            "SQL GROUP BY clause (without 'GROUP BY' keyword). "
                            "Example: \"product_name, category\". "
                            "Use when aggregating data."
                        )
                    },
                    "order_by": {
                        "type": "string",
                        "description": (
                            "SQL ORDER BY clause (without 'ORDER BY' keyword). "
                            "Example: \"order_date DESC\" or \"revenue DESC\". "
                            "Leave empty for default order."
                        )
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum rows to return (default: 50, max: 500)"
                    }
                },
                "required": []
            },
            "_metadata": {
                "source_id": source_id,
                "table_name": table_name,
                "content_columns": content_columns,
                "connection_config": config_json
            }
        }

        return tool_schema

    @staticmethod
    async def generate_tools_for_notebook(notebook_id: str) -> List[Dict[str, Any]]:
        """
        Generate all HANA tools for sources in a notebook

        Called at the start of each chat session to create function tools
        dynamically based on current notebook sources.

        Args:
            notebook_id: Notebook UUID

        Returns:
            List of tool schemas (one per HANA source)
        """
        from open_notebook.database.repository import repo_query

        # Get HANA sources in notebook
        sql = """
            SELECT s.*
            FROM sources s
            INNER JOIN notebook_source ns ON s.id = ns.source_id
            WHERE ns.notebook_id = :notebook_id
            AND s.source_type = 'hana_table'
        """
        sources = await repo_query(sql, {"notebook_id": notebook_id})

        if not sources:
            # No HANA sources in this notebook
            return []

        # Generate tool for each source
        tools = []
        for source in sources:
            try:
                tool = await HANAToolGenerator.generate_tool_schema(source["id"], source)
                tools.append(tool)
            except Exception as e:
                # Log error but don't fail entire generation
                print(f"⚠️ Failed to generate tool for source {source.get('id')}: {str(e)}")
                continue

        return tools

    @staticmethod
    def extract_metadata(tool: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract and remove metadata from tool schema

        Metadata is needed for execution but should not be sent to LLM.

        Args:
            tool: Tool schema with _metadata field

        Returns:
            Extracted metadata dict
        """
        return tool.pop("_metadata", {})
