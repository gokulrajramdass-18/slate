"""
Orchestration Detection Service

Analyzes chat queries to determine if they warrant autonomous orchestration.
Uses heuristics and optional LLM analysis to detect complex multi-step tasks.
"""

import logging
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)


class OrchestrationDetector:
    """
    Detects queries that should trigger autonomous orchestration.

    Uses both heuristics and LLM analysis to identify:
    - Multi-step tasks
    - Cross-domain queries (e.g., data analysis + web research)
    - Parallelizable subtasks
    - Complex reasoning requirements
    """

    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        enable_llm_detection: bool = True
    ):
        """
        Initialize orchestration detector.

        Args:
            llm: Language model for advanced detection
            enable_llm_detection: Use LLM for detection (vs heuristics only)
        """
        self.llm = llm
        self.enable_llm_detection = enable_llm_detection

    async def should_orchestrate(
        self,
        query: str,
        available_tools: List[Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Determine if query should trigger orchestration.

        Args:
            query: User query
            available_tools: Available tools in session
            context: Additional context (notebook, sources, etc.)

        Returns:
            Dict with:
                - should_orchestrate: bool
                - confidence: float (0.0-1.0)
                - reasoning: str
                - complexity: str (simple, moderate, complex)
                - detected_subtasks: List[str]
        """
        context = context or {}

        # Quick heuristic checks
        heuristic_result = self._heuristic_detection(query, available_tools, context)

        # If heuristics strongly indicate orchestration and LLM is disabled, return
        if not self.enable_llm_detection:
            return heuristic_result

        # If heuristics indicate low complexity, skip LLM check
        if heuristic_result["complexity"] == "simple" and heuristic_result["confidence"] > 0.8:
            return heuristic_result

        # Use LLM for sophisticated detection
        if self.llm:
            try:
                llm_result = await self._llm_detection(query, available_tools, context)

                # Combine heuristic and LLM results (LLM gets higher weight)
                combined = self._combine_results(heuristic_result, llm_result)
                return combined

            except Exception as e:
                logger.warning(f"LLM detection failed: {e}, falling back to heuristics")
                return heuristic_result

        return heuristic_result

    def _heuristic_detection(
        self,
        query: str,
        available_tools: List[Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Heuristic-based detection using patterns and keywords.

        Indicators of complex queries:
        - Multiple action verbs (analyze, compare, research, create)
        - Cross-domain keywords (data + research, API + database)
        - Coordination keywords (then, after, before, first, next)
        - Multiple tool types needed
        - Report generation keywords
        """
        query_lower = query.lower()

        # Complexity indicators
        complexity_score = 0.0
        detected_subtasks = []
        reasoning_parts = []

        # 1. Multiple action verbs
        action_verbs = [
            "analyze", "compare", "research", "create", "generate",
            "summarize", "extract", "query", "fetch", "compile",
            "investigate", "explore", "evaluate", "assess"
        ]

        action_count = sum(1 for verb in action_verbs if verb in query_lower)
        if action_count >= 2:
            complexity_score += 0.3
            reasoning_parts.append(f"Multiple actions detected: {action_count}")

        # 2. Coordination keywords (sequential steps)
        coordination_words = ["then", "after", "before", "first", "next", "finally", "once"]
        has_coordination = any(word in query_lower for word in coordination_words)
        if has_coordination:
            complexity_score += 0.2
            reasoning_parts.append("Sequential coordination detected")

        # 3. Cross-domain keywords
        data_keywords = ["database", "table", "query", "data", "hana", "sql"]
        research_keywords = ["research", "search", "web", "find", "investigate", "competitor"]
        reporting_keywords = ["report", "presentation", "summary", "analysis", "visualization"]

        has_data = any(word in query_lower for word in data_keywords)
        has_research = any(word in query_lower for word in research_keywords)
        has_reporting = any(word in query_lower for word in reporting_keywords)

        domain_count = sum([has_data, has_research, has_reporting])
        if domain_count >= 2:
            complexity_score += 0.3
            reasoning_parts.append(f"Cross-domain query: {domain_count} domains")

        # 4. Multiple tool types available
        tool_types = set()
        for tool in available_tools:
            tool_name = getattr(tool, 'name', '').lower()
            if 'hana' in tool_name or 'database' in tool_name:
                tool_types.add('data')
            elif 'search' in tool_name or 'web' in tool_name:
                tool_types.add('research')
            elif 'api' in tool_name:
                tool_types.add('api')

        if len(tool_types) >= 2:
            complexity_score += 0.1
            reasoning_parts.append(f"Multiple tool types available: {len(tool_types)}")

        # 5. Report generation indicators
        if has_reporting and (has_data or has_research):
            complexity_score += 0.2
            detected_subtasks.append("Generate final report")
            reasoning_parts.append("Report generation detected")

        # 6. Comparison tasks (usually need parallel data gathering)
        comparison_words = ["compare", "versus", "vs", "difference between", "contrast"]
        has_comparison = any(word in query_lower for word in comparison_words)
        if has_comparison:
            complexity_score += 0.15
            reasoning_parts.append("Comparison task detected")

        # 7. Long queries (more likely to be complex)
        word_count = len(query.split())
        if word_count > 20:
            complexity_score += 0.1
            reasoning_parts.append(f"Long query: {word_count} words")

        # Determine complexity level
        if complexity_score >= 0.6:
            complexity = "complex"
            should_orchestrate = True
            confidence = min(complexity_score, 1.0)
        elif complexity_score >= 0.3:
            complexity = "moderate"
            should_orchestrate = False  # Could use orchestration, but single agent likely sufficient
            confidence = 0.5
        else:
            complexity = "simple"
            should_orchestrate = False
            confidence = 0.8

        reasoning = "; ".join(reasoning_parts) if reasoning_parts else "Simple query"

        return {
            "should_orchestrate": should_orchestrate,
            "confidence": confidence,
            "reasoning": reasoning,
            "complexity": complexity,
            "detected_subtasks": detected_subtasks
        }

    async def _llm_detection(
        self,
        query: str,
        available_tools: List[Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        LLM-based detection for sophisticated analysis.
        """
        # Build tool descriptions
        tool_descriptions = []
        for tool in available_tools[:10]:  # Limit to avoid token explosion
            tool_descriptions.append(f"- {tool.name}: {tool.description[:100]}")
        tools_text = "\n".join(tool_descriptions) if tool_descriptions else "No tools available"

        system_prompt = """You are an expert at analyzing user queries to determine their complexity.

Your task is to decide if a query should trigger multi-agent orchestration or can be handled by a single agent.

Multi-agent orchestration should be used when:
1. The query has multiple distinct subtasks that could run in parallel
2. The query requires cross-domain expertise (e.g., data analysis + web research + reporting)
3. The query involves sequential steps with handovers
4. The query would benefit from specialized agents working together

Single agent is sufficient when:
1. The query is a simple question with one answer
2. The query uses only one tool or data source
3. The query doesn't require coordination between multiple steps

Respond in JSON format with:
{
  "should_orchestrate": true/false,
  "confidence": 0.0-1.0,
  "complexity": "simple"/"moderate"/"complex",
  "reasoning": "brief explanation",
  "detected_subtasks": ["subtask1", "subtask2", ...]
}"""

        user_prompt = f"""Query: "{query}"

Available tools:
{tools_text}

Should this query trigger multi-agent orchestration?"""

        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]

            response = await self.llm.ainvoke(messages)
            content = response.content

            # Parse JSON response
            import json
            result = json.loads(content)

            return {
                "should_orchestrate": result.get("should_orchestrate", False),
                "confidence": float(result.get("confidence", 0.5)),
                "reasoning": result.get("reasoning", "LLM analysis"),
                "complexity": result.get("complexity", "moderate"),
                "detected_subtasks": result.get("detected_subtasks", [])
            }

        except Exception as e:
            logger.error(f"LLM detection parsing failed: {e}")
            # Return neutral result
            return {
                "should_orchestrate": False,
                "confidence": 0.5,
                "reasoning": f"LLM analysis error: {e}",
                "complexity": "moderate",
                "detected_subtasks": []
            }

    def _combine_results(
        self,
        heuristic_result: Dict[str, Any],
        llm_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Combine heuristic and LLM results.

        Gives LLM result 70% weight, heuristics 30%.
        """
        # Weighted average for should_orchestrate
        h_score = 1.0 if heuristic_result["should_orchestrate"] else 0.0
        l_score = 1.0 if llm_result["should_orchestrate"] else 0.0
        combined_score = (h_score * 0.3) + (l_score * 0.7)

        should_orchestrate = combined_score >= 0.5

        # Weighted average for confidence
        combined_confidence = (
            heuristic_result["confidence"] * 0.3 +
            llm_result["confidence"] * 0.7
        )

        # Take LLM complexity if confident, else heuristic
        complexity = llm_result["complexity"] if llm_result["confidence"] > 0.6 else heuristic_result["complexity"]

        # Merge subtasks
        detected_subtasks = list(set(
            heuristic_result["detected_subtasks"] +
            llm_result["detected_subtasks"]
        ))

        # Combine reasoning
        reasoning = f"Heuristic: {heuristic_result['reasoning']}; LLM: {llm_result['reasoning']}"

        return {
            "should_orchestrate": should_orchestrate,
            "confidence": combined_confidence,
            "reasoning": reasoning,
            "complexity": complexity,
            "detected_subtasks": detected_subtasks
        }


# Singleton instance
_orchestration_detector = None


def get_orchestration_detector(
    llm: Optional[ChatOpenAI] = None,
    enable_llm_detection: bool = False  # Disabled by default for performance
) -> OrchestrationDetector:
    """Get or create orchestration detector singleton."""
    global _orchestration_detector

    if _orchestration_detector is None:
        _orchestration_detector = OrchestrationDetector(
            llm=llm,
            enable_llm_detection=enable_llm_detection
        )

    return _orchestration_detector
