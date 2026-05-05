"""
Semantic Search Skill - Search notebook sources

Provides semantic, keyword, hybrid, and agentic RAG search capabilities
for notebook content.
"""

from typing import Any, Dict

from open_notebook.agents.skills.base import Skill, SkillCategory, SkillContext


async def semantic_search_handler(context: SkillContext) -> Dict[str, Any]:
    """
    Search using configured strategy.

    Args:
        context: SkillContext with input_data containing:
            - query: Search query string
            - notebook_id: Optional notebook to limit search to
            - filters: Optional additional filters

    Returns:
        Dict with results, count, and strategy used
    """
    query = context.input_data.get("query", "")
    strategy_name = context.config.get("strategy", "hybrid")
    limit = context.config.get("limit", 10)
    notebook_id = context.input_data.get("notebook_id")
    filters = context.input_data.get("filters", {})

    if not query:
        raise ValueError("Query parameter is required")

    context.record_step(
        "searching",
        f"Using {strategy_name} strategy to search for: {query}",
        status="running"
    )

    # Import search service
    from api.services.search_service import get_search_strategy

    # Add notebook filter if specified
    if notebook_id:
        filters["notebook_id"] = notebook_id

    # Get search strategy
    strategy = get_search_strategy(strategy_name)
    results = await strategy.search(
        query=query,
        filters=filters,
        limit=limit
    )

    context.record_step(
        "completed",
        f"Found {len(results)} results",
        status="completed",
        metadata={"result_count": len(results), "strategy": strategy_name}
    )

    # Convert results to dict
    result_dicts = []
    for r in results:
        if hasattr(r, 'to_dict'):
            result_dicts.append(r.to_dict())
        elif hasattr(r, '__dict__'):
            result_dicts.append(r.__dict__)
        else:
            result_dicts.append(str(r))

    return {
        "results": result_dicts,
        "count": len(results),
        "strategy": strategy_name,
        "query": query
    }


def create_search_skill() -> Skill:
    """Create and return the semantic search skill."""
    return Skill(
        id="semantic_search",
        name="Semantic Search",
        description="Search notebook sources using vector, keyword, hybrid, or agentic RAG search strategies",
        category=SkillCategory.SEARCH,
        handler=semantic_search_handler,
        config_schema={
            "type": "object",
            "properties": {
                "strategy": {
                    "type": "string",
                    "enum": ["vector", "keyword", "hybrid", "agentic_rag"],
                    "default": "hybrid",
                    "description": "Search strategy to use"
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Maximum number of results to return"
                }
            }
        },
        default_config={"strategy": "hybrid", "limit": 10},
        tags=["search", "retrieval", "rag", "semantic"],
        timeout_seconds=30,
        author="Open Notebook",
        version="1.0.0"
    )
