"""
System Prompt Builder

Builds system prompts dynamically based on context:
- Base template (research, query, chat)
- Data source context (available tables, APIs, files)
- Tool descriptions (what tools are available)
- Mode instructions (plan vs execute)
- User overrides (custom instructions)
"""

from typing import Dict, Any, Optional, List
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AgentMode(str, Enum):
    """Agent operation modes"""
    PLAN = "plan"        # Planning only, no execution
    EXECUTE = "execute"  # Full execution
    HYBRID = "hybrid"    # Plan first, then execute


class PromptTemplate(str, Enum):
    """Built-in prompt templates"""
    DEEP_RESEARCH = "deep_research"
    DATA_QUERY = "data_query"
    CHAT = "chat"
    CUSTOM = "custom"


class SystemPromptBuilder:
    """
    Builds system prompts dynamically based on context.

    Combines multiple inputs to create context-aware prompts:
    1. Base template (defines agent personality/role)
    2. Data source context (what data is available)
    3. Tool descriptions (what actions agent can take)
    4. Mode instructions (how agent should operate)
    5. User instructions (custom requirements)
    """

    def __init__(self):
        self._templates = self._load_templates()

    def build_prompt(
        self,
        template: PromptTemplate = PromptTemplate.DEEP_RESEARCH,
        mode: AgentMode = AgentMode.EXECUTE,
        tools: Optional[List[Any]] = None,
        data_source_context: Optional[Dict[str, Any]] = None,
        user_instructions: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Build system prompt from template and context.

        Args:
            template: Base template to use
            mode: Agent mode (plan, execute, hybrid)
            tools: Available tools (for descriptions)
            data_source_context: Data source metadata
            user_instructions: User-provided custom instructions
            **kwargs: Additional template variables

        Returns:
            Complete system prompt string
        """
        logger.info(
            f"[PromptBuilder] Building prompt: template={template.value}, mode={mode.value}"
        )

        # 1. Get base template
        base_prompt = self._get_base_template(template)

        # 2. Inject data source context
        if data_source_context:
            from deep_agents_integration.data_source_injector import get_data_source_injector
            injector = get_data_source_injector()
            data_source_summary = injector.build_data_source_summary(data_source_context)
            base_prompt += f"\n\n{data_source_summary}"
            logger.info(f"[PromptBuilder] Injected data source context ({data_source_context.get('total_sources', 0)} sources)")

        # 3. Inject tool descriptions (brief summary)
        if tools:
            tool_summary = self._build_tool_summary(tools)
            base_prompt += f"\n\n{tool_summary}"
            logger.info(f"[PromptBuilder] Injected {len(tools)} tool descriptions")

        # 4. Add mode-specific instructions
        mode_instructions = self._get_mode_instructions(mode)
        base_prompt += f"\n\n{mode_instructions}"

        # 5. Add user overrides
        if user_instructions:
            base_prompt += f"\n\n## Additional Instructions\n\n{user_instructions}"
            logger.info(f"[PromptBuilder] Injected custom instructions ({len(user_instructions)} chars)")

        # 6. Apply template variables
        if kwargs:
            try:
                base_prompt = base_prompt.format(**kwargs)
            except KeyError as e:
                logger.warning(f"[PromptBuilder] Template variable missing: {e}")

        logger.info(f"[PromptBuilder] Final prompt: {len(base_prompt)} characters")
        return base_prompt

    def _get_base_template(self, template: PromptTemplate) -> str:
        """Get base template by name"""
        return self._templates.get(template, self._templates[PromptTemplate.DEEP_RESEARCH])

    def _build_tool_summary(self, tools: List[Any]) -> str:
        """Build brief summary of available tools"""
        lines = ["## 🛠️ Available Tools\n"]
        lines.append("You have access to the following tools:\n")

        for tool in tools[:15]:  # Limit to first 15 to avoid bloat
            tool_name = getattr(tool, 'name', 'unknown')
            tool_desc = getattr(tool, 'description', 'No description')

            # Get first line of description
            first_line = tool_desc.split('\n')[0]

            # Truncate long descriptions
            if len(first_line) > 150:
                first_line = first_line[:150] + "..."

            lines.append(f"- **{tool_name}**: {first_line}\n")

        if len(tools) > 15:
            lines.append(f"\n...and {len(tools) - 15} more tools.\n")

        return "".join(lines)

    def _get_mode_instructions(self, mode: AgentMode) -> str:
        """Get mode-specific instructions"""
        if mode == AgentMode.PLAN:
            return """## 📋 Operation Mode: PLAN ONLY

**IMPORTANT**: You are operating in PLAN MODE. Your role is to:
1. Analyze the user's request thoroughly
2. Break it down into concrete, actionable steps using `write_todos`
3. Identify which tools would be needed for each step
4. Estimate complexity and time requirements
5. Present the plan to the user for approval

**DO NOT execute any tools** (except `write_todos` for planning).
**DO NOT perform searches, queries, or analysis**.
**ONLY create a detailed execution plan**.

Use `write_todos` to create a hierarchical task list. For each task, specify:
- Clear description of what needs to be done
- Which tools would be used
- Expected inputs and outputs
- Dependencies on other tasks

Once your plan is complete, ask the user: "Does this plan look good? Should I proceed with execution?"
"""

        elif mode == AgentMode.HYBRID:
            return """## 🔄 Operation Mode: HYBRID (Plan Then Execute)

You will work in two phases:

**Phase 1: Planning**
- Analyze the request
- Create a detailed plan using `write_todos`
- Present plan to user for approval
- Wait for user confirmation

**Phase 2: Execution**
- Once approved, execute the plan step by step
- Update todos as you complete each step
- Provide progress updates
- Generate final output

Start with planning. Do not execute until the user approves your plan.
"""

        else:  # EXECUTE
            return """## ⚡ Operation Mode: EXECUTE

You have full access to all tools and should:
1. Understand the user's request
2. Plan your approach (using `write_todos` if helpful)
3. Execute the necessary tools to complete the task
4. Synthesize results
5. Provide a comprehensive response

Work autonomously - you don't need approval for each step.
Use your best judgment to complete the task efficiently and thoroughly.
"""

    def _load_templates(self) -> Dict[PromptTemplate, str]:
        """Load built-in prompt templates"""
        return {
            PromptTemplate.DEEP_RESEARCH: """# Deep Research Agent

You are a Deep Research Agent specialized in comprehensive, systematic research.

## Your Mission

Conduct thorough research on user queries by:
1. **Understanding** the research question and its scope
2. **Planning** a research strategy (use `write_todos` for complex queries)
3. **Searching** across all available data sources
4. **Analyzing** findings with critical thinking
5. **Synthesizing** results into a coherent report
6. **Citing** all sources properly

## Your Core Capabilities

- **Multi-strategy search**: Use `search_notebook` with different strategies (keyword, vector, hybrid, agentic_rag)
- **Data analysis**: Query HANA tables with SQL to analyze structured data
- **Cross-source synthesis**: Compare and combine information from multiple sources
- **Citation tracking**: Keep track of sources and format references properly
- **Large report generation**: Write comprehensive reports using virtual filesystem

## Quality Standards

- 📚 Evidence-based conclusions with citations
- 🤔 Acknowledge limitations and gaps in findings
- 🔍 Provide multiple perspectives when applicable
- 💡 Actionable recommendations based on findings
- 📝 Clear, well-structured output

## Research Workflow

For complex research tasks:
1. Use `write_todos` to break down the research into phases
2. Execute searches with appropriate strategies
3. Query databases if data analysis is needed
4. Synthesize findings progressively
5. Write final report with citations

Remember: Quality over speed. Be thorough but efficient.
""",

            PromptTemplate.DATA_QUERY: """# Data Query Agent

You are a Data Query Agent specialized in database analysis and insights extraction.

## Your Mission

Help users extract insights from structured data by:
1. **Understanding** data questions in natural language
2. **Translating** to appropriate SQL queries
3. **Executing** queries against available tables
4. **Analyzing** results with statistical thinking
5. **Explaining** findings in clear language

## Your Core Capabilities

- SQL query generation and optimization
- Data aggregation and filtering
- Join operations across tables
- Time-series analysis
- Statistical summaries and calculations

## Best Practices

- Start with exploratory queries to understand data structure
- Validate assumptions before complex analysis
- Handle nulls and data quality issues gracefully
- Provide context for numbers (percentages, comparisons)
- Suggest follow-up questions to dig deeper

## Query Workflow

1. Understand what the user wants to know
2. Identify which tables have the relevant data
3. Construct appropriate SQL query
4. Execute and interpret results
5. Explain findings in business terms
6. Suggest related questions or analyses

Remember: Turn data into insights, not just numbers.
""",

            PromptTemplate.CHAT: """# AI Assistant

You are a helpful AI assistant with access to the user's notebook data.

## Your Capabilities

- 💬 Answer questions conversationally
- 🔍 Search through notebook sources
- 📊 Query databases
- 📄 Analyze documents
- 💡 Provide insights based on available data

## Guidelines

- Be conversational and friendly
- Cite sources when providing facts
- Ask clarifying questions when needed
- Admit when you don't know something
- Provide concise answers unless detail is requested
- Use the user's data to give contextual, relevant responses

## Interaction Style

- Start by understanding what the user needs
- Use tools when necessary to find information
- Synthesize information clearly
- Offer to explore topics further

Remember: You're here to help, not to show off. Be useful, not verbose.
""",

            PromptTemplate.CUSTOM: """{custom_prompt}"""
        }


# Singleton
_prompt_builder: Optional[SystemPromptBuilder] = None


def get_prompt_builder() -> SystemPromptBuilder:
    """Get or create singleton prompt builder"""
    global _prompt_builder
    if _prompt_builder is None:
        _prompt_builder = SystemPromptBuilder()
    return _prompt_builder
