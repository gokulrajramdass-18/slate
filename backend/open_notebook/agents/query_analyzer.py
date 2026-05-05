"""
Query Complexity Analyzer

Analyzes incoming user queries to classify complexity, detect intent,
estimate resource requirements, and route to the appropriate agent
configuration.

Complexity Levels:
- SIMPLE: Single-fact lookup, basic question -> Single agent
- MODERATE: Multi-source comparison, data analysis -> Two-agent team
- COMPLEX: Multi-step reasoning, synthesis needed -> Full orchestration with planner
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from api.services.prompt_loader import load_prompt


class QueryComplexity(str, Enum):
    """Classification of query complexity levels."""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


class QueryIntent(str, Enum):
    """Classification of the user's primary intent."""
    FACTUAL_LOOKUP = "factual_lookup"       # Single fact retrieval
    SUMMARIZATION = "summarization"          # Summarize content
    COMPARISON = "comparison"                # Compare multiple items
    ANALYSIS = "analysis"                    # Analyze data or trends
    SYNTHESIS = "synthesis"                  # Combine multiple sources into new insight
    CREATIVE = "creative"                    # Generate new content
    DATA_QUERY = "data_query"               # Query structured data (HANA/API)
    DEEP_RESEARCH = "deep_research"          # Multi-step autonomous research
    CONVERSATIONAL = "conversational"        # General chat / follow-up


@dataclass
class ResourceEstimate:
    """Estimated resources needed to fulfill a query."""
    estimated_sources: int = 1
    estimated_search_calls: int = 1
    estimated_llm_calls: int = 1
    recommended_strategies: List[str] = field(default_factory=lambda: ["hybrid"])
    estimated_time_seconds: float = 5.0
    requires_tools: bool = False
    requires_structured_data: bool = False


@dataclass
class QueryAnalysis:
    """Complete analysis result for a query."""
    original_query: str
    complexity: QueryComplexity
    intent: QueryIntent
    confidence: float  # 0.0 to 1.0
    key_topics: List[str] = field(default_factory=list)
    sub_questions: List[str] = field(default_factory=list)
    resource_estimate: ResourceEstimate = field(default_factory=ResourceEstimate)
    reasoning: str = ""
    recommended_agent_count: int = 1
    recommended_agent_roles: List[str] = field(default_factory=lambda: ["researcher"])
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "original_query": self.original_query,
            "complexity": self.complexity.value,
            "intent": self.intent.value,
            "confidence": self.confidence,
            "key_topics": self.key_topics,
            "sub_questions": self.sub_questions,
            "resource_estimate": {
                "estimated_sources": self.resource_estimate.estimated_sources,
                "estimated_search_calls": self.resource_estimate.estimated_search_calls,
                "estimated_llm_calls": self.resource_estimate.estimated_llm_calls,
                "recommended_strategies": self.resource_estimate.recommended_strategies,
                "estimated_time_seconds": self.resource_estimate.estimated_time_seconds,
                "requires_tools": self.resource_estimate.requires_tools,
                "requires_structured_data": self.resource_estimate.requires_structured_data,
            },
            "reasoning": self.reasoning,
            "recommended_agent_count": self.recommended_agent_count,
            "recommended_agent_roles": self.recommended_agent_roles,
            "timestamp": self.timestamp,
        }


# Heuristic patterns for fast classification (before LLM call)
_SIMPLE_PATTERNS = [
    r"^what is\b",
    r"^who is\b",
    r"^when (was|did|is)\b",
    r"^where (is|was|are)\b",
    r"^define\b",
    r"^how many\b",
    r"^(yes|no|true|false)\??\s*$",
]

_COMPLEX_PATTERNS = [
    r"\bcompare\b.*\band\b",
    r"\banalyze\b.*\btrend",
    r"\bsynthesize\b",
    r"\bresearch\b.*\bcomprehensive",
    r"\bmulti[- ]step\b",
    r"\bcross[- ]reference\b",
    r"\bevaluate\b.*\bpros\b.*\bcons\b",
    r"\brelationship\b.*\bbetween\b",
    r"\bimpact\b.*\bon\b.*\band\b",
    r"\bdeep\s*dive\b",
    r"\bthorough(ly)?\b",
    r"\bcomprehensive\b",
]

_DATA_QUERY_PATTERNS = [
    r"\bquery\b.*\b(table|database|hana|sql)\b",
    r"\bselect\b.*\bfrom\b",
    r"\bshow\b.*\b(data|records|rows)\b",
    r"\bfetch\b.*\b(from|api)\b",
    r"\bget\b.*\b(data|records)\b.*\bfrom\b",
]

# Fallback prompt
ANALYSIS_PROMPT = """You are a query complexity analyzer. Analyze the following user query and classify it.

Query: "{query}"

Context (if any): {context}

Respond with a JSON object containing:
{{
    "complexity": "simple" | "moderate" | "complex",
    "intent": "factual_lookup" | "summarization" | "comparison" | "analysis" | "synthesis" | "creative" | "data_query" | "deep_research" | "conversational",
    "confidence": <float 0.0-1.0>,
    "key_topics": [<list of key topics/entities>],
    "sub_questions": [<list of implicit sub-questions that need answering, empty for simple>],
    "reasoning": "<brief explanation of classification>",
    "estimated_sources": <int>,
    "estimated_search_calls": <int>,
    "estimated_llm_calls": <int>,
    "recommended_strategies": [<list from: "keyword", "vector", "hybrid", "agentic_rag">],
    "estimated_time_seconds": <float>,
    "requires_tools": <bool>,
    "requires_structured_data": <bool>
}}

Classification guidelines:
- SIMPLE: Direct fact lookup, definition, single-source answer. 1 agent.
- MODERATE: Needs 2-3 sources, comparison, summarization, or data query. 2 agents.
- COMPLEX: Multi-step reasoning, cross-source synthesis, deep research, or multi-domain analysis. Full orchestration (3+ agents).

Intent guidelines:
- factual_lookup: "What is X?", "When did Y happen?"
- summarization: "Summarize...", "Give me an overview of..."
- comparison: "Compare X and Y", "Differences between..."
- analysis: "Analyze...", "What trends...", "Why did..."
- synthesis: "Based on all sources, what...", "Combine insights from..."
- creative: "Write a...", "Generate...", "Draft..."
- data_query: "Query the database for...", "Show HANA table data..."
- deep_research: "Research comprehensively...", "Deep dive into..."
- conversational: "Thanks", "Can you clarify...", "What do you mean by..."

Be precise. Return only valid JSON."""


class QueryAnalyzer:
    """
    Analyzes user queries to determine complexity, intent, and routing.

    Uses a two-phase approach:
    1. Fast heuristic pre-classification using regex patterns
    2. LLM-based detailed analysis for ambiguous or moderate/complex queries

    The heuristic phase can short-circuit obviously simple queries to
    avoid unnecessary LLM calls.
    """

    def __init__(
        self,
        model_name: str = "gpt-4",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        use_heuristics: bool = True,
        heuristic_confidence_threshold: float = 0.85,
    ):
        """
        Initialize the query analyzer.

        Args:
            model_name: LLM model to use for analysis
            base_url: Optional base URL for API
            api_key: Optional API key
            use_heuristics: Whether to use fast heuristic pre-classification
            heuristic_confidence_threshold: Minimum confidence for heuristic to skip LLM
        """
        self.model_name = model_name
        self.use_heuristics = use_heuristics
        self.heuristic_confidence_threshold = heuristic_confidence_threshold

        llm_kwargs = {
            "model": model_name,
            "temperature": 0.0,  # Deterministic for classification
        }
        if base_url:
            llm_kwargs["base_url"] = base_url
        if api_key:
            llm_kwargs["openai_api_key"] = api_key

        self.llm = ChatOpenAI(**llm_kwargs)

    def _heuristic_classify(self, query: str) -> Optional[QueryAnalysis]:
        """
        Fast heuristic classification using regex patterns.

        Returns QueryAnalysis if confident enough, None otherwise.
        """
        query_lower = query.lower().strip()
        word_count = len(query_lower.split())

        # Very short queries are usually simple
        if word_count <= 5:
            for pattern in _SIMPLE_PATTERNS:
                if re.search(pattern, query_lower):
                    return QueryAnalysis(
                        original_query=query,
                        complexity=QueryComplexity.SIMPLE,
                        intent=QueryIntent.FACTUAL_LOOKUP,
                        confidence=0.90,
                        key_topics=self._extract_topics_heuristic(query),
                        resource_estimate=ResourceEstimate(
                            estimated_sources=1,
                            estimated_search_calls=1,
                            estimated_llm_calls=1,
                            recommended_strategies=["keyword"],
                            estimated_time_seconds=2.0,
                        ),
                        reasoning="Short query matching simple lookup pattern",
                        recommended_agent_count=1,
                        recommended_agent_roles=["researcher"],
                    )

        # Check for data query patterns
        for pattern in _DATA_QUERY_PATTERNS:
            if re.search(pattern, query_lower):
                return QueryAnalysis(
                    original_query=query,
                    complexity=QueryComplexity.MODERATE,
                    intent=QueryIntent.DATA_QUERY,
                    confidence=0.88,
                    key_topics=self._extract_topics_heuristic(query),
                    resource_estimate=ResourceEstimate(
                        estimated_sources=1,
                        estimated_search_calls=1,
                        estimated_llm_calls=2,
                        recommended_strategies=["keyword"],
                        estimated_time_seconds=5.0,
                        requires_tools=True,
                        requires_structured_data=True,
                    ),
                    reasoning="Query matches structured data query pattern",
                    recommended_agent_count=2,
                    recommended_agent_roles=["researcher", "data_analyst"],
                )

        # Check for complex patterns
        complex_matches = sum(
            1 for pattern in _COMPLEX_PATTERNS
            if re.search(pattern, query_lower)
        )
        if complex_matches >= 2 or (complex_matches >= 1 and word_count > 20):
            return QueryAnalysis(
                original_query=query,
                complexity=QueryComplexity.COMPLEX,
                intent=QueryIntent.SYNTHESIS,
                confidence=0.85,
                key_topics=self._extract_topics_heuristic(query),
                resource_estimate=ResourceEstimate(
                    estimated_sources=5,
                    estimated_search_calls=3,
                    estimated_llm_calls=5,
                    recommended_strategies=["hybrid", "agentic_rag"],
                    estimated_time_seconds=30.0,
                ),
                reasoning="Query matches multiple complex analysis patterns",
                recommended_agent_count=3,
                recommended_agent_roles=["researcher", "analyst", "synthesizer"],
            )

        # Conversational / very short
        if word_count <= 3 and not any(
            re.search(p, query_lower) for p in _SIMPLE_PATTERNS
        ):
            return QueryAnalysis(
                original_query=query,
                complexity=QueryComplexity.SIMPLE,
                intent=QueryIntent.CONVERSATIONAL,
                confidence=0.80,
                key_topics=[],
                resource_estimate=ResourceEstimate(
                    estimated_sources=0,
                    estimated_search_calls=0,
                    estimated_llm_calls=1,
                    recommended_strategies=[],
                    estimated_time_seconds=1.0,
                ),
                reasoning="Very short conversational query",
                recommended_agent_count=1,
                recommended_agent_roles=["researcher"],
            )

        # Not confident enough for heuristic classification
        return None

    def _extract_topics_heuristic(self, query: str) -> List[str]:
        """Extract key topics from query using simple heuristics."""
        # Remove common stop words and extract meaningful terms
        stop_words = {
            "what", "is", "the", "a", "an", "of", "in", "to", "for", "and",
            "or", "but", "with", "from", "by", "on", "at", "how", "why",
            "when", "where", "who", "which", "that", "this", "these", "those",
            "are", "was", "were", "be", "been", "being", "have", "has", "had",
            "do", "does", "did", "will", "would", "could", "should", "may",
            "might", "can", "shall", "about", "between", "compare", "analyze",
            "me", "my", "give", "tell", "show", "please", "thank", "thanks",
        }

        words = re.findall(r'\b[a-zA-Z]{3,}\b', query.lower())
        topics = [w for w in words if w not in stop_words]

        # Deduplicate while preserving order
        seen = set()
        unique_topics = []
        for t in topics:
            if t not in seen:
                seen.add(t)
                unique_topics.append(t)

        return unique_topics[:5]

    async def analyze(
        self,
        query: str,
        context: Optional[str] = None,
    ) -> QueryAnalysis:
        """
        Analyze a query to determine complexity, intent, and routing.

        Uses heuristics first for fast classification, then falls back
        to LLM for ambiguous queries.

        Args:
            query: The user's query string
            context: Optional conversation context

        Returns:
            QueryAnalysis with full classification
        """
        # Phase 1: Heuristic classification
        if self.use_heuristics:
            heuristic_result = self._heuristic_classify(query)
            if (
                heuristic_result is not None
                and heuristic_result.confidence >= self.heuristic_confidence_threshold
            ):
                return heuristic_result

        # Phase 2: LLM-based analysis
        return await self._llm_analyze(query, context)

    async def _llm_analyze(
        self,
        query: str,
        context: Optional[str] = None,
    ) -> QueryAnalysis:
        """
        Use LLM to analyze query complexity and intent.

        Args:
            query: The user's query
            context: Optional conversation context

        Returns:
            QueryAnalysis from LLM classification
        """
        # Load prompt from database
        prompt = await load_prompt(
            "agent_query_analysis",
            variables={"query": query, "context": context or "No additional context"},
            fallback=ANALYSIS_PROMPT.format(query=query, context=context or "No additional context")
        )

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])

            # Clean JSON response
            content = response.content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            result = json.loads(content)

            complexity = QueryComplexity(result.get("complexity", "moderate"))
            intent = QueryIntent(result.get("intent", "analysis"))

            # Determine agent configuration based on complexity
            if complexity == QueryComplexity.SIMPLE:
                agent_count = 1
                agent_roles = ["researcher"]
            elif complexity == QueryComplexity.MODERATE:
                agent_count = 2
                if intent == QueryIntent.DATA_QUERY:
                    agent_roles = ["researcher", "data_analyst"]
                elif intent == QueryIntent.COMPARISON:
                    agent_roles = ["researcher", "analyst"]
                else:
                    agent_roles = ["researcher", "analyst"]
            else:  # COMPLEX
                agent_count = 3
                agent_roles = ["researcher", "analyst", "synthesizer"]
                if intent == QueryIntent.DEEP_RESEARCH:
                    agent_roles = ["researcher", "analyst", "synthesizer"]

            return QueryAnalysis(
                original_query=query,
                complexity=complexity,
                intent=intent,
                confidence=result.get("confidence", 0.7),
                key_topics=result.get("key_topics", []),
                sub_questions=result.get("sub_questions", []),
                resource_estimate=ResourceEstimate(
                    estimated_sources=result.get("estimated_sources", 1),
                    estimated_search_calls=result.get("estimated_search_calls", 1),
                    estimated_llm_calls=result.get("estimated_llm_calls", 1),
                    recommended_strategies=result.get(
                        "recommended_strategies", ["hybrid"]
                    ),
                    estimated_time_seconds=result.get("estimated_time_seconds", 5.0),
                    requires_tools=result.get("requires_tools", False),
                    requires_structured_data=result.get(
                        "requires_structured_data", False
                    ),
                ),
                reasoning=result.get("reasoning", ""),
                recommended_agent_count=agent_count,
                recommended_agent_roles=agent_roles,
            )

        except json.JSONDecodeError as e:
            print(f"[QueryAnalyzer] JSON parsing error: {e}")
            # Fall back to moderate classification
            return self._fallback_analysis(query)
        except Exception as e:
            print(f"[QueryAnalyzer] LLM analysis error: {e}")
            return self._fallback_analysis(query)

    def _fallback_analysis(self, query: str) -> QueryAnalysis:
        """
        Fallback analysis when LLM fails.

        Uses word count and basic heuristics to make a best-effort classification.
        """
        word_count = len(query.split())
        topics = self._extract_topics_heuristic(query)

        if word_count <= 8:
            complexity = QueryComplexity.SIMPLE
            intent = QueryIntent.FACTUAL_LOOKUP
            agent_count = 1
            agent_roles = ["researcher"]
        elif word_count <= 25:
            complexity = QueryComplexity.MODERATE
            intent = QueryIntent.ANALYSIS
            agent_count = 2
            agent_roles = ["researcher", "analyst"]
        else:
            complexity = QueryComplexity.COMPLEX
            intent = QueryIntent.SYNTHESIS
            agent_count = 3
            agent_roles = ["researcher", "analyst", "synthesizer"]

        return QueryAnalysis(
            original_query=query,
            complexity=complexity,
            intent=intent,
            confidence=0.5,  # Low confidence for fallback
            key_topics=topics,
            resource_estimate=ResourceEstimate(
                estimated_sources=agent_count,
                estimated_search_calls=agent_count,
                estimated_llm_calls=agent_count + 1,
                recommended_strategies=["hybrid"],
                estimated_time_seconds=5.0 * agent_count,
            ),
            reasoning="Fallback classification due to LLM analysis failure",
            recommended_agent_count=agent_count,
            recommended_agent_roles=agent_roles,
        )
