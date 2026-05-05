"""
Analysis Skill - Analyze and extract insights from data

Provides data analysis, summarization, and insight extraction.
"""

from typing import Any, Dict

from open_notebook.agents.skills.base import Skill, SkillCategory, SkillContext


async def analysis_handler(context: SkillContext) -> Dict[str, Any]:
    """
    Analyze data and extract insights.

    Args:
        context: SkillContext with input_data containing:
            - data: Data to analyze (text, JSON, or structured)
            - analysis_type: Type of analysis (summarize, extract_key_points, sentiment)

    Returns:
        Dict with analysis results
    """
    data = context.input_data.get("data", "")
    analysis_type = context.config.get("analysis_type", "summarize")

    if not data:
        raise ValueError("Data parameter is required")

    context.record_step(
        "analyzing",
        f"Analyzing data using {analysis_type} method",
        status="running"
    )

    # Placeholder for actual analysis logic
    # In real implementation, this would use LLM or other analysis tools
    result = {
        "analysis_type": analysis_type,
        "input_length": len(str(data)),
        "summary": f"Analysis of {len(str(data))} characters completed",
        "insights": [
            "Data processed successfully",
            "Ready for further analysis"
        ]
    }

    context.record_step(
        "completed",
        f"Analysis complete: {analysis_type}",
        status="completed",
        metadata={"analysis_type": analysis_type}
    )

    return result


def create_analysis_skill() -> Skill:
    """Create and return the analysis skill."""
    return Skill(
        id="data_analysis",
        name="Data Analysis",
        description="Analyze data and extract insights using various methods",
        category=SkillCategory.ANALYSIS,
        handler=analysis_handler,
        config_schema={
            "type": "object",
            "properties": {
                "analysis_type": {
                    "type": "string",
                    "enum": ["summarize", "extract_key_points", "sentiment", "trends"],
                    "default": "summarize",
                    "description": "Type of analysis to perform"
                }
            }
        },
        default_config={"analysis_type": "summarize"},
        tags=["analysis", "insights", "summarization"],
        timeout_seconds=45,
        author="Open Notebook",
        version="1.0.0"
    )
