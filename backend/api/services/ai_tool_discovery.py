"""
AI-Powered Tool Discovery

Uses LLM to intelligently recommend tools based on workspace goal analysis.
"""

import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


async def discover_tools_with_ai(
    all_tools: List[Dict[str, Any]],
    analysis: Dict[str, Any],
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Use AI to discover and recommend relevant tools based on goal analysis.

    Args:
        all_tools: List of all available tools with name, description
        analysis: Goal analysis with intent, domain, requirements
        limit: Maximum number of tools to recommend

    Returns:
        List of tools with relevance_score and relevance_reason added
    """
    try:
        import os
        from litellm import acompletion

        # Get model from environment or use default
        model_name = os.getenv("DEFAULT_CHAT_MODEL", "gpt-4")

        # Check if we have any API keys configured
        # LiteLLM supports many providers, check common ones
        has_api_key = any([
            os.getenv("OPENAI_API_KEY"),
            os.getenv("ANTHROPIC_API_KEY"),
            os.getenv("GOOGLE_API_KEY"),
            os.getenv("GROQ_API_KEY"),
            os.getenv("COHERE_API_KEY"),
        ])

        if not has_api_key:
            logger.info("No AI API keys configured, skipping AI-powered tool discovery")
            return []

        # Use LiteLLM for universal model support (works with OpenAI, Anthropic, Google, etc.)

        # Extract analysis details
        intent = analysis.get("intent", "")
        domain = analysis.get("domain", "")
        requirements = analysis.get("requirements", [])
        keywords = analysis.get("keywords", [])

        # Create tool descriptions (limit to avoid token overflow)
        tools_list = []
        for i, tool in enumerate(all_tools[:50], 1):
            desc = tool.get("description", "")[:200]  # Truncate long descriptions
            tools_list.append(f"{i}. {tool['name']}: {desc}")

        tools_description = "\n".join(tools_list)

        # Create AI prompt
        prompt = f"""You are an expert at recommending tools for workspace creation.

WORKSPACE GOAL ANALYSIS:
- Intent: {intent}
- Domain: {domain}
- Requirements: {', '.join(requirements)}
- Keywords: {', '.join(keywords)}

AVAILABLE TOOLS:
{tools_description}

Task: Select the {limit} most relevant tools that would help achieve this workspace goal.

For each recommended tool:
1. Use the EXACT tool name from the list above
2. Assign a relevance score (0.0-1.0, where 1.0 is perfect match)
3. Explain in ONE sentence why it's relevant to THIS specific goal

Rules:
- Be selective - only recommend tools that are truly useful for THIS goal
- Prioritize tools that match the intent and requirements
- Consider the domain when making recommendations
- A score of 0.7+ means highly relevant
- A score of 0.5-0.7 means moderately relevant
- Scores below 0.5 should not be included

Return ONLY a valid JSON array (no markdown, no explanation):
[
  {{"name": "Exact Tool Name", "score": 0.95, "reason": "Specific reason for this goal"}},
  ...
]"""

        # Call LLM using LiteLLM
        response = await acompletion(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = response.choices[0].message.content

        # Parse response
        # Extract JSON from markdown code blocks if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        recommendations = json.loads(content.strip())

        # Match recommendations with actual tools and add scores
        results = []
        for rec in recommendations:
            tool_name = rec.get("name", "")
            score = float(rec.get("score", 0.0))
            reason = rec.get("reason", "Relevant to your workspace goal")

            # Find matching tool (case-insensitive)
            matching_tool = next(
                (t for t in all_tools if t["name"].lower() == tool_name.lower()),
                None
            )

            if matching_tool and score >= 0.5:  # Only include relevant tools
                tool_copy = matching_tool.copy()
                tool_copy["relevance_score"] = round(score, 3)
                tool_copy["relevance_reason"] = reason
                results.append(tool_copy)

        logger.info(f"AI recommended {len(results)} tools for goal analysis")
        return results[:limit]

    except Exception as e:
        logger.error(f"AI tool discovery failed: {e}", exc_info=True)
        return []
