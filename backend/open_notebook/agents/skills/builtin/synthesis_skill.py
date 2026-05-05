"""
Synthesis Skill - Content generation and summarization

Provides LLM-powered content summarization and synthesis capabilities.
Requires LLM to be configured in the execution context.
"""

from typing import Any, Dict

from open_notebook.agents.skills.base import Skill, SkillCategory, SkillContext


async def summarize_handler(context: SkillContext) -> Dict[str, Any]:
    """
    Summarize content using LLM.

    Args:
        context: SkillContext with input_data containing:
            - content: Text content to summarize

    Returns:
        Dict with summary, word_count, and style
    """
    content = context.input_data.get("content", "")
    max_words = context.config.get("max_words", 100)
    style = context.config.get("style", "concise")

    if not content:
        raise ValueError("content is required")

    if not context.llm:
        raise ValueError("No LLM configured in context. LLM is required for summarization.")

    context.record_step(
        "analyzing",
        f"Processing content for {style} summary (max {max_words} words)",
        status="running",
        metadata={"content_length": len(content), "max_words": max_words}
    )

    # Build prompt based on style
    style_instructions = {
        "concise": "Be extremely concise and focus only on the most important points.",
        "detailed": "Provide a comprehensive summary covering all major points and key details.",
        "technical": "Use technical language and focus on specific details, methodologies, and technical aspects."
    }

    instruction = style_instructions.get(style, style_instructions["concise"])

    prompt = f"""{instruction}

Summarize the following content in approximately {max_words} words:

{content}

Provide only the summary, without any preamble or meta-commentary."""

    try:
        # Invoke LLM
        response = await context.llm.ainvoke(prompt)

        # Extract content from response
        if hasattr(response, 'content'):
            summary = response.content
        elif hasattr(response, 'text'):
            summary = response.text
        else:
            summary = str(response)

        # Count words
        word_count = len(summary.split())

        context.record_step(
            "completed",
            f"Generated {word_count}-word {style} summary",
            status="completed",
            metadata={"word_count": word_count, "style": style}
        )

        return {
            "summary": summary,
            "word_count": word_count,
            "style": style,
            "original_length": len(content)
        }

    except Exception as e:
        context.record_step(
            "error",
            f"Summarization failed: {str(e)}",
            status="error"
        )
        raise


# Define skill
summarize_skill = Skill(
    id="summarize_content",
    name="Content Summarization",
    description="Summarize text using LLM. Supports concise, detailed, and technical summary styles.",
    category=SkillCategory.SYNTHESIS,
    handler=summarize_handler,
    config_schema={
        "type": "object",
        "properties": {
            "max_words": {
                "type": "integer",
                "default": 100,
                "minimum": 10,
                "maximum": 1000,
                "description": "Maximum words in summary (approximate)"
            },
            "style": {
                "type": "string",
                "enum": ["concise", "detailed", "technical"],
                "default": "concise",
                "description": "Summary style: concise (brief), detailed (comprehensive), or technical (technical focus)"
            }
        }
    },
    default_config={"max_words": 100, "style": "concise"},
    tags=["nlp", "summarization", "llm", "synthesis"],
    timeout_seconds=60,
    author="Open Notebook",
    version="1.0.0"
)
