"""
Tool Filtering for Plan Mode

Two-phase tool discovery system that reduces context window bloat:
1. Fast heuristic filtering (pattern matching, no LLM cost)
2. LLM-based selection (only when confidence < threshold)

Used by Explore and Plan agents to intelligently filter tools before bind_tools().
"""

import os
import re
import hashlib
import logging
from typing import List, Dict, Optional, Literal, Set
from pydantic import BaseModel, Field
from langchain.tools import BaseTool

logger = logging.getLogger(__name__)

# Configuration defaults
DEFAULT_CONFIDENCE_THRESHOLD = 0.85
DEFAULT_MAX_TOOLS = 10
DEFAULT_FILTER_MODEL = "claude-3-5-haiku-20241022"  # Valid Haiku model name


class ToolFilterResult(BaseModel):
    """Result of tool filtering operation"""
    selected_tool_ids: List[str] = Field(
        description="Tool IDs selected for this query"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence in selection (0.0-1.0)"
    )
    reasoning: str = Field(
        description="Explanation of why these tools were selected"
    )
    phase_used: Literal["heuristic", "llm"] = Field(
        description="Which phase made the selection"
    )


# Plan mode safe tools (always include for read-only operations)
PLAN_MODE_SAFE_TOOLS = {
    "Read", "Glob", "Grep",  # File operations
    "Agent",  # Spawn subagents
    "TaskCreate", "TaskList", "TaskGet", "TaskUpdate",  # Task management
    "AskUserQuestion",  # User interaction
    "WebFetch", "WebSearch",  # Research
}

# Tools to NEVER include in plan mode
PLAN_MODE_EXCLUDED_TOOLS = {
    "Write", "Edit", "NotebookEdit",  # Write operations
    "ExitPlanMode",  # Plan completion (agent decides)
    "Bash",  # Potentially destructive
    "TeamCreate", "TeamDelete",  # Team management
    "ExitWorktree", "EnterWorktree",  # Worktree management
}

# Pattern matching for query classification
FILE_EXPLORATION_PATTERNS = [
    r'\b(file|code|search|find|explore|read|locate|discover)\b',
    r'\b(structure|architecture|codebase|repository)\b',
    r'\b(implementation|function|class|module|package)\b',
]

DATABASE_PATTERNS = [
    r'\b(database|query|table|hana|sql|data)\b',
    r'\b(select|insert|update|schema|column)\b',
    r'\b(migration|record|row)\b',
]

WEB_PATTERNS = [
    r'\b(web|url|fetch|http|api|endpoint)\b',
    r'\b(website|page|html|json|rest)\b',
]

DESIGN_PATTERNS = [
    r'\b(design|ui|component|layout|interface)\b',
    r'\b(frontend|screen|page|view)\b',
    r'\b(pencil|figma|mockup|wireframe)\b',
]

PLAN_MODE_PATTERNS = [
    r'\b(plan|design|architecture|approach|strategy)\b',
    r'\b(implement|build|create|add|develop)\b',
    r'\b(how to|should we|what if)\b',
]


class PlanModeToolFilter:
    """
    Two-phase tool filtering for plan mode.

    Phase 1: Fast heuristic matching (pattern-based, no LLM cost)
    Phase 2: LLM-based selection (only when confidence < threshold)
    """

    def __init__(self):
        self._cache: Dict[str, ToolFilterResult] = {}
        self._enabled = os.getenv("PLAN_MODE_TOOL_FILTERING_ENABLED", "true").lower() == "true"
        self._confidence_threshold = float(
            os.getenv("PLAN_MODE_FILTER_CONFIDENCE_THRESHOLD", str(DEFAULT_CONFIDENCE_THRESHOLD))
        )
        self._max_tools = int(os.getenv("PLAN_MODE_MAX_TOOLS", str(DEFAULT_MAX_TOOLS)))
        self._filter_model = os.getenv("PLAN_MODE_FILTER_MODEL", DEFAULT_FILTER_MODEL)

    async def filter_tools_for_query(
        self, query: str, available_tools: List[BaseTool]
    ) -> ToolFilterResult:
        """
        Filter tools based on query and available tools.

        Args:
            query: User query or task description
            available_tools: All tools available to agent

        Returns:
            ToolFilterResult with selected tools
        """
        # Check if filtering is enabled
        if not self._enabled:
            logger.info("[ToolFilter] Filtering disabled, returning all tools")
            return ToolFilterResult(
                selected_tool_ids=[t.name for t in available_tools],
                confidence=1.0,
                reasoning="Filtering disabled via PLAN_MODE_TOOL_FILTERING_ENABLED=false",
                phase_used="heuristic"
            )

        # Check cache
        cache_key = self._cache_key(query, [t.name for t in available_tools])
        if cache_key in self._cache:
            logger.debug(f"[ToolFilter] Cache hit for query: {query[:50]}...")
            return self._cache[cache_key]

        # Run two-phase filtering
        result = await self._run_two_phase_filter(query, available_tools)

        # Cache result
        if len(self._cache) >= 100:  # Simple LRU: clear oldest entries
            logger.debug("[ToolFilter] Cache full, clearing oldest entries")
            self._cache.clear()
        self._cache[cache_key] = result

        # Log result
        logger.info(
            "[ToolFilter] Complete",
            extra={
                "query_preview": query[:100],
                "total_tools": len(available_tools),
                "selected_tools": len(result.selected_tool_ids),
                "confidence": result.confidence,
                "phase": result.phase_used,
                "tool_ids": result.selected_tool_ids,
            }
        )

        return result

    async def _run_two_phase_filter(
        self, query: str, available_tools: List[BaseTool]
    ) -> ToolFilterResult:
        """Run two-phase filtering pipeline"""
        # Phase 1: Heuristic filtering
        heuristic_result = self._heuristic_filter(query, available_tools)

        # Check confidence threshold
        if heuristic_result.confidence >= self._confidence_threshold:
            logger.info(
                f"[ToolFilter] Phase 1 (heuristic) sufficient "
                f"(confidence={heuristic_result.confidence:.2f})"
            )
            return heuristic_result

        # Phase 2: LLM-based selection (fallback)
        logger.info(
            f"[ToolFilter] Phase 1 confidence low ({heuristic_result.confidence:.2f}), "
            f"falling back to Phase 2 (LLM)"
        )
        llm_result = await self._llm_filter(query, available_tools)
        return llm_result

    def _heuristic_filter(
        self, query: str, available_tools: List[BaseTool]
    ) -> ToolFilterResult:
        """
        Phase 1: Fast heuristic filtering using pattern matching.

        Returns:
            ToolFilterResult with confidence score
        """
        query_lower = query.lower()
        selected_tools: Set[str] = set()
        confidence_scores = []

        # 1. Always include base safe tools
        for tool in available_tools:
            if tool.name in PLAN_MODE_SAFE_TOOLS:
                selected_tools.add(tool.name)

        # 2. Pattern matching for specific domains
        pattern_matches = {
            "file_exploration": self._matches_any_pattern(query_lower, FILE_EXPLORATION_PATTERNS),
            "database": self._matches_any_pattern(query_lower, DATABASE_PATTERNS),
            "web": self._matches_any_pattern(query_lower, WEB_PATTERNS),
            "design": self._matches_any_pattern(query_lower, DESIGN_PATTERNS),
            "plan_mode": self._matches_any_pattern(query_lower, PLAN_MODE_PATTERNS),
        }

        # 3. Select tools based on pattern matches
        for tool in available_tools:
            tool_name_lower = tool.name.lower()
            tool_desc_lower = getattr(tool, 'description', '').lower()

            # File exploration tools
            if pattern_matches["file_exploration"]:
                if any(kw in tool_name_lower for kw in ["read", "glob", "grep", "file", "search"]):
                    selected_tools.add(tool.name)
                    confidence_scores.append(0.9)

            # Database tools
            if pattern_matches["database"]:
                if any(kw in tool_name_lower for kw in ["hana", "query", "table", "database", "sql"]):
                    selected_tools.add(tool.name)
                    confidence_scores.append(0.85)

            # Web tools
            if pattern_matches["web"]:
                if any(kw in tool_name_lower for kw in ["web", "fetch", "http", "api"]):
                    selected_tools.add(tool.name)
                    confidence_scores.append(0.85)

            # Design tools (MCP Pencil)
            if pattern_matches["design"]:
                if any(kw in tool_name_lower for kw in ["pencil", "design", "ui", "mcp"]):
                    selected_tools.add(tool.name)
                    confidence_scores.append(0.8)

        # 4. Apply safety rules
        selected_tools = self._apply_safety_rules(list(selected_tools), available_tools)

        # 5. Calculate confidence
        if confidence_scores:
            avg_confidence = sum(confidence_scores) / len(confidence_scores)
        elif len(selected_tools) == len(PLAN_MODE_SAFE_TOOLS):
            # Only base tools selected, uncertain
            avg_confidence = 0.5
        else:
            # Some tools selected beyond base tools
            avg_confidence = 0.75

        # Higher confidence if clear pattern match
        total_pattern_matches = sum(1 for v in pattern_matches.values() if v)
        if total_pattern_matches >= 2:
            avg_confidence = min(avg_confidence + 0.15, 1.0)
        elif total_pattern_matches == 1:
            avg_confidence = min(avg_confidence + 0.05, 1.0)

        reasoning = self._build_heuristic_reasoning(pattern_matches, selected_tools)

        return ToolFilterResult(
            selected_tool_ids=selected_tools,
            confidence=avg_confidence,
            reasoning=reasoning,
            phase_used="heuristic"
        )

    async def _llm_filter(
        self, query: str, available_tools: List[BaseTool]
    ) -> ToolFilterResult:
        """
        Phase 2: LLM-based tool selection.

        Uses a lightweight model (Haiku) to semantically understand query
        and select minimal tool set.

        Returns:
            ToolFilterResult with selected tools
        """
        try:
            from langchain_anthropic import ChatAnthropic
            import json

            # Build tool list summary
            tool_summary = self._build_tool_summary(available_tools)

            # Build LLM prompt
            prompt = f"""You are a tool selection assistant for Claude Code's plan mode.

Plan mode is a READ-ONLY exploration phase where the agent:
- Reads code files
- Searches for patterns
- Analyzes architecture
- Designs implementation plans
- Does NOT write/edit files or execute code

Given the following query and available tools, select the MINIMAL set of tools needed for this planning task.

Query: {query}

Available Tools:
{tool_summary}

Return ONLY a JSON object (no markdown, no explanation):
{{
    "selected_tool_ids": ["tool1", "tool2", ...],
    "reasoning": "Brief explanation of why these tools are needed",
    "confidence": 0.9
}}

Guidelines:
- Prefer Read, Glob, Grep for file exploration
- Include Agent for complex multi-step exploration
- Exclude Write, Edit, Bash (write operations)
- Exclude MCP tools unless directly relevant to query
- Aim for 5-10 tools maximum
- Always include at least: Read, Glob, Grep, Agent"""

            # Call LLM
            model = ChatAnthropic(model=self._filter_model, temperature=0)
            response = await model.ainvoke(prompt)
            content = response.content

            # Parse JSON response
            # Remove markdown code blocks if present
            content = re.sub(r'^```json?\s*', '', content, flags=re.MULTILINE)
            content = re.sub(r'\s*```$', '', content, flags=re.MULTILINE)

            result_data = json.loads(content)

            # Apply safety rules
            selected_tools = self._apply_safety_rules(
                result_data["selected_tool_ids"],
                available_tools
            )

            return ToolFilterResult(
                selected_tool_ids=selected_tools,
                confidence=result_data.get("confidence", 0.9),
                reasoning=result_data["reasoning"],
                phase_used="llm"
            )

        except Exception as e:
            logger.error(f"[ToolFilter] LLM selection failed: {e}", exc_info=True)
            # Fallback to all available tools (don't filter when LLM unavailable)
            # This is safer than returning empty list which breaks the agent
            all_tool_ids = [t.name for t in available_tools]
            return ToolFilterResult(
                selected_tool_ids=all_tool_ids,
                confidence=0.6,
                reasoning=f"LLM selection failed, using all {len(all_tool_ids)} available tools. Error: {str(e)[:200]}",
                phase_used="llm"
            )

    def _apply_safety_rules(
        self, selected_tools: List[str], available_tools: List[BaseTool]
    ) -> List[str]:
        """
        Apply hard safety constraints to tool selection.

        Rules:
        1. Always include base safe tools (Read, Glob, Grep, Agent)
        2. Never include write tools (Write, Edit, etc.)
        3. Enforce min/max tool count
        """
        selected_set = set(selected_tools)
        available_names = {t.name for t in available_tools}

        # Rule 1: Always include base safe tools (if available)
        for safe_tool in PLAN_MODE_SAFE_TOOLS:
            if safe_tool in available_names:
                selected_set.add(safe_tool)

        # Rule 2: Remove excluded tools
        selected_set -= PLAN_MODE_EXCLUDED_TOOLS

        # Rule 3: Enforce max tool count
        if len(selected_set) > self._max_tools:
            # Prioritize: base tools > user-selected > alphabetical
            prioritized = [t for t in PLAN_MODE_SAFE_TOOLS if t in selected_set]
            prioritized += [t for t in selected_tools if t not in PLAN_MODE_SAFE_TOOLS and t in selected_set]
            selected_set = set(prioritized[:self._max_tools])

        # Rule 4: Enforce minimum (at least base safe tools)
        min_tools = min(4, len(available_tools))
        if len(selected_set) < min_tools:
            # Add more safe tools
            for tool in available_tools:
                if tool.name in PLAN_MODE_SAFE_TOOLS and tool.name not in selected_set:
                    selected_set.add(tool.name)
                    if len(selected_set) >= min_tools:
                        break

        return list(selected_set)

    def _matches_any_pattern(self, text: str, patterns: List[str]) -> bool:
        """Check if text matches any regex pattern"""
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _build_heuristic_reasoning(
        self, pattern_matches: Dict[str, bool], selected_tools: Set[str]
    ) -> str:
        """Build human-readable reasoning for heuristic selection"""
        matched_domains = [k for k, v in pattern_matches.items() if v]

        if not matched_domains:
            return "Query unclear, using base safe tools only"

        domain_str = ", ".join(matched_domains)
        return (
            f"Detected domains: {domain_str}. "
            f"Selected {len(selected_tools)} tools including base safe tools "
            f"(Read, Glob, Grep, Agent) and domain-specific tools."
        )

    def _build_tool_summary(self, tools: List[BaseTool]) -> str:
        """Build abbreviated tool summary for LLM prompt"""
        lines = []
        for tool in tools:
            # Get first line of description
            desc = getattr(tool, 'description', 'No description')
            first_line = desc.split('\n')[0].strip()
            if len(first_line) > 100:
                first_line = first_line[:100] + "..."
            lines.append(f"- {tool.name}: {first_line}")
        return "\n".join(lines)

    def _cache_key(self, query: str, tool_names: List[str]) -> str:
        """Generate cache key from query + available tools"""
        tool_sig = ",".join(sorted(tool_names))
        combined = f"{query}|{tool_sig}"
        return hashlib.md5(combined.encode()).hexdigest()


# Singleton instance
_filter_instance: Optional[PlanModeToolFilter] = None


def get_plan_mode_filter() -> PlanModeToolFilter:
    """Get or create singleton filter instance"""
    global _filter_instance
    if _filter_instance is None:
        _filter_instance = PlanModeToolFilter()
    return _filter_instance
