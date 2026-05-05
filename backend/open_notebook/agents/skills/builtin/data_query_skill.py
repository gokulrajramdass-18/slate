"""
Data Query Skill - Query HANA tables and APIs

Provides capability to execute SQL queries on HANA database sources.
Restricted to analyst, data_scientist, and researcher roles.
"""

from typing import Any, Dict

from open_notebook.agents.skills.base import Skill, SkillCategory, SkillContext


async def hana_query_handler(context: SkillContext) -> Dict[str, Any]:
    """
    Execute HANA query.

    Args:
        context: SkillContext with input_data containing:
            - source_id: HANA source ID
            - query: SQL query string
            - params: Optional query parameters

    Returns:
        Dict with rows, count, and source_id
    """
    source_id = context.input_data.get("source_id")
    query = context.input_data.get("query")
    params = context.input_data.get("params", [])
    limit = context.config.get("limit", 100)

    if not source_id:
        raise ValueError("source_id is required")

    if not query:
        raise ValueError("query is required")

    context.record_step(
        "querying",
        f"Executing query on source {source_id}",
        status="running",
        metadata={"source_id": source_id}
    )

    # Import data query tools
    from api.services.data_query_tools import execute_hana_query

    # Execute query
    try:
        results = await execute_hana_query(
            source_id=source_id,
            query=query,
            params=params,
            limit=limit
        )

        context.record_step(
            "completed",
            f"Retrieved {len(results)} rows",
            status="completed",
            metadata={"row_count": len(results)}
        )

        return {
            "rows": results,
            "count": len(results),
            "source_id": source_id,
            "query": query
        }

    except Exception as e:
        context.record_step(
            "error",
            f"Query failed: {str(e)}",
            status="error"
        )
        raise


# Define skill
hana_query_skill = Skill(
    id="hana_query",
    name="HANA Table Query",
    description="Query SAP HANA tables with SQL. Restricted to analyst, data scientist, and researcher roles.",
    category=SkillCategory.DATA_QUERY,
    handler=hana_query_handler,
    allowed_roles={"analyst", "data_scientist", "researcher"},
    config_schema={
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "default": 100,
                "minimum": 1,
                "maximum": 10000,
                "description": "Maximum number of rows to return"
            }
        }
    },
    default_config={"limit": 100},
    tags=["data", "sql", "hana", "query"],
    timeout_seconds=60,
    author="Open Notebook",
    version="1.0.0"
)
