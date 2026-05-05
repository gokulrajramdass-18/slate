"""
Tests for Query Analyzer and Planner Agent

Tests cover:
- Heuristic classification for simple/complex/data queries
- LLM-based analysis with mocked responses
- Fallback behavior when LLM fails
- ExecutionPlan lifecycle (ready tasks, completion, progress)
- PlannerAgent plan generation for all complexity levels
- Edge cases (empty queries, very long queries, ambiguous queries)
- Circular dependency detection and removal
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from open_notebook.agents.query_analyzer import (
    QueryAnalyzer,
    QueryAnalysis,
    QueryComplexity,
    QueryIntent,
    ResourceEstimate,
    _SIMPLE_PATTERNS,
    _COMPLEX_PATTERNS,
    _DATA_QUERY_PATTERNS,
)
from open_notebook.agents.planner_agent import (
    PlannerAgent,
    ExecutionPlan,
    SubTask,
    TaskStatus,
    AgentRole,
)


# ============================================================================
# QueryAnalyzer - Heuristic Tests
# ============================================================================


class TestHeuristicClassification:
    """Test the fast regex-based pre-classification."""

    def setup_method(self):
        """Create analyzer with heuristics enabled, LLM not needed."""
        self.analyzer = QueryAnalyzer.__new__(QueryAnalyzer)
        self.analyzer.use_heuristics = True
        self.analyzer.heuristic_confidence_threshold = 0.85

    def test_simple_what_is_query(self):
        result = self.analyzer._heuristic_classify("What is machine learning?")
        assert result is not None
        assert result.complexity == QueryComplexity.SIMPLE
        assert result.intent == QueryIntent.FACTUAL_LOOKUP
        assert result.confidence >= 0.85

    def test_simple_who_is_query(self):
        result = self.analyzer._heuristic_classify("Who is Alan Turing?")
        assert result is not None
        assert result.complexity == QueryComplexity.SIMPLE

    def test_simple_when_query(self):
        result = self.analyzer._heuristic_classify("When was Python created?")
        assert result is not None
        assert result.complexity == QueryComplexity.SIMPLE

    def test_simple_where_query(self):
        result = self.analyzer._heuristic_classify("Where is SAP headquartered?")
        assert result is not None
        assert result.complexity == QueryComplexity.SIMPLE

    def test_simple_define_query(self):
        result = self.analyzer._heuristic_classify("Define recursion")
        assert result is not None
        assert result.complexity == QueryComplexity.SIMPLE

    def test_data_query_hana(self):
        result = self.analyzer._heuristic_classify(
            "Query the HANA table for sales data"
        )
        assert result is not None
        assert result.complexity == QueryComplexity.MODERATE
        assert result.intent == QueryIntent.DATA_QUERY
        assert result.resource_estimate.requires_tools is True
        assert result.resource_estimate.requires_structured_data is True

    def test_data_query_sql(self):
        result = self.analyzer._heuristic_classify(
            "Select all records from the database"
        )
        assert result is not None
        assert result.intent == QueryIntent.DATA_QUERY

    def test_data_query_fetch_api(self):
        result = self.analyzer._heuristic_classify(
            "Fetch data from the API endpoint"
        )
        assert result is not None
        assert result.intent == QueryIntent.DATA_QUERY

    def test_complex_compare_and_analyze(self):
        result = self.analyzer._heuristic_classify(
            "Compare the impact of renewable energy and fossil fuels on climate change, "
            "and analyze the trend in adoption rates across different regions comprehensively"
        )
        assert result is not None
        assert result.complexity == QueryComplexity.COMPLEX
        assert result.recommended_agent_count >= 3

    def test_complex_deep_dive(self):
        result = self.analyzer._heuristic_classify(
            "Do a deep dive into the relationship between AI adoption and "
            "productivity gains, cross-reference with industry reports and evaluate "
            "the pros and cons comprehensively"
        )
        assert result is not None
        assert result.complexity == QueryComplexity.COMPLEX

    def test_conversational_short(self):
        result = self.analyzer._heuristic_classify("thanks")
        assert result is not None
        assert result.complexity == QueryComplexity.SIMPLE
        assert result.intent == QueryIntent.CONVERSATIONAL
        assert result.resource_estimate.estimated_search_calls == 0

    def test_conversational_ok(self):
        result = self.analyzer._heuristic_classify("ok")
        assert result is not None
        assert result.intent == QueryIntent.CONVERSATIONAL

    def test_ambiguous_returns_none(self):
        """Ambiguous queries should return None so LLM handles them."""
        result = self.analyzer._heuristic_classify(
            "Tell me about the current state of the project and what we should focus on next"
        )
        # This is moderate-length without strong pattern matches,
        # so heuristic should return None
        assert result is None


class TestTopicExtraction:
    """Test heuristic topic extraction."""

    def setup_method(self):
        self.analyzer = QueryAnalyzer.__new__(QueryAnalyzer)

    def test_extracts_meaningful_words(self):
        topics = self.analyzer._extract_topics_heuristic(
            "What is the impact of machine learning on healthcare?"
        )
        assert "impact" in topics
        assert "machine" in topics
        assert "learning" in topics
        assert "healthcare" in topics
        # Stop words should be excluded
        assert "what" not in topics
        assert "the" not in topics
        assert "is" not in topics

    def test_deduplicates_topics(self):
        topics = self.analyzer._extract_topics_heuristic(
            "machine learning and machine learning applications"
        )
        assert topics.count("machine") == 1

    def test_limits_to_five(self):
        topics = self.analyzer._extract_topics_heuristic(
            "climate change renewable energy solar wind nuclear hydrogen geothermal biomass"
        )
        assert len(topics) <= 5

    def test_empty_query(self):
        topics = self.analyzer._extract_topics_heuristic("")
        assert topics == []


# ============================================================================
# QueryAnalyzer - LLM Analysis Tests (mocked)
# ============================================================================


class TestLLMAnalysis:
    """Test LLM-based query analysis with mocked LLM."""

    @pytest.fixture
    def mock_llm_response(self):
        """Create a mock LLM response."""
        def _make_response(data: dict):
            mock_msg = MagicMock()
            mock_msg.content = json.dumps(data)
            return mock_msg
        return _make_response

    @pytest.mark.asyncio
    async def test_llm_moderate_analysis(self, mock_llm_response):
        analyzer = QueryAnalyzer.__new__(QueryAnalyzer)
        analyzer.use_heuristics = True
        analyzer.heuristic_confidence_threshold = 0.85

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=mock_llm_response(
                {
                    "complexity": "moderate",
                    "intent": "comparison",
                    "confidence": 0.88,
                    "key_topics": ["Python", "JavaScript", "performance"],
                    "sub_questions": [
                        "What are the performance characteristics of Python?",
                        "What are the performance characteristics of JavaScript?",
                    ],
                    "reasoning": "Query asks for comparison between two languages",
                    "estimated_sources": 3,
                    "estimated_search_calls": 2,
                    "estimated_llm_calls": 3,
                    "recommended_strategies": ["hybrid", "keyword"],
                    "estimated_time_seconds": 8.0,
                    "requires_tools": False,
                    "requires_structured_data": False,
                }
            )
        )
        analyzer.llm = mock_llm

        result = await analyzer._llm_analyze(
            "Compare Python and JavaScript performance characteristics"
        )

        assert result.complexity == QueryComplexity.MODERATE
        assert result.intent == QueryIntent.COMPARISON
        assert result.confidence == 0.88
        assert result.recommended_agent_count == 2
        assert "researcher" in result.recommended_agent_roles
        assert "analyst" in result.recommended_agent_roles

    @pytest.mark.asyncio
    async def test_llm_complex_analysis(self, mock_llm_response):
        analyzer = QueryAnalyzer.__new__(QueryAnalyzer)
        analyzer.use_heuristics = True
        analyzer.heuristic_confidence_threshold = 0.85

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=mock_llm_response(
                {
                    "complexity": "complex",
                    "intent": "deep_research",
                    "confidence": 0.92,
                    "key_topics": ["AI", "healthcare", "regulation", "ethics"],
                    "sub_questions": [
                        "What AI applications exist in healthcare?",
                        "What regulations govern AI in healthcare?",
                        "What ethical concerns exist?",
                    ],
                    "reasoning": "Multi-faceted research question",
                    "estimated_sources": 8,
                    "estimated_search_calls": 4,
                    "estimated_llm_calls": 6,
                    "recommended_strategies": ["hybrid", "agentic_rag"],
                    "estimated_time_seconds": 45.0,
                    "requires_tools": False,
                    "requires_structured_data": False,
                }
            )
        )
        analyzer.llm = mock_llm

        result = await analyzer._llm_analyze(
            "Research the impact of AI on healthcare, including current regulations and ethical concerns"
        )

        assert result.complexity == QueryComplexity.COMPLEX
        assert result.intent == QueryIntent.DEEP_RESEARCH
        assert result.recommended_agent_count == 3
        assert "synthesizer" in result.recommended_agent_roles

    @pytest.mark.asyncio
    async def test_llm_json_error_fallback(self):
        analyzer = QueryAnalyzer.__new__(QueryAnalyzer)
        analyzer.use_heuristics = True
        analyzer.heuristic_confidence_threshold = 0.85

        mock_llm = AsyncMock()
        mock_msg = MagicMock()
        mock_msg.content = "This is not valid JSON"
        mock_llm.ainvoke = AsyncMock(return_value=mock_msg)
        analyzer.llm = mock_llm

        result = await analyzer._llm_analyze("Some query that fails parsing")

        assert result.confidence == 0.5  # Fallback confidence
        assert "Fallback" in result.reasoning

    @pytest.mark.asyncio
    async def test_llm_exception_fallback(self):
        analyzer = QueryAnalyzer.__new__(QueryAnalyzer)
        analyzer.use_heuristics = True
        analyzer.heuristic_confidence_threshold = 0.85

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("API error"))
        analyzer.llm = mock_llm

        result = await analyzer._llm_analyze("Some query that raises exception")

        assert result.confidence == 0.5
        assert "Fallback" in result.reasoning

    @pytest.mark.asyncio
    async def test_llm_response_with_code_blocks(self, mock_llm_response):
        """Test that code block markers are properly stripped."""
        analyzer = QueryAnalyzer.__new__(QueryAnalyzer)
        analyzer.use_heuristics = True
        analyzer.heuristic_confidence_threshold = 0.85

        mock_llm = AsyncMock()
        mock_msg = MagicMock()
        mock_msg.content = '```json\n{"complexity": "simple", "intent": "factual_lookup", "confidence": 0.95, "key_topics": ["test"], "sub_questions": [], "reasoning": "test", "estimated_sources": 1, "estimated_search_calls": 1, "estimated_llm_calls": 1, "recommended_strategies": ["keyword"], "estimated_time_seconds": 2.0, "requires_tools": false, "requires_structured_data": false}\n```'
        mock_llm.ainvoke = AsyncMock(return_value=mock_msg)
        analyzer.llm = mock_llm

        result = await analyzer._llm_analyze("What is Python?")
        assert result.complexity == QueryComplexity.SIMPLE


class TestFallbackAnalysis:
    """Test the word-count based fallback."""

    def setup_method(self):
        self.analyzer = QueryAnalyzer.__new__(QueryAnalyzer)

    def test_short_query_fallback(self):
        result = self.analyzer._fallback_analysis("What is AI?")
        assert result.complexity == QueryComplexity.SIMPLE
        assert result.recommended_agent_count == 1

    def test_medium_query_fallback(self):
        result = self.analyzer._fallback_analysis(
            "Explain the differences between supervised and unsupervised learning approaches"
        )
        assert result.complexity == QueryComplexity.MODERATE
        assert result.recommended_agent_count == 2

    def test_long_query_fallback(self):
        long_query = " ".join(["word"] * 30)
        result = self.analyzer._fallback_analysis(long_query)
        assert result.complexity == QueryComplexity.COMPLEX
        assert result.recommended_agent_count == 3


class TestAnalyzeIntegration:
    """Test the full analyze() method combining heuristics + LLM."""

    @pytest.mark.asyncio
    async def test_simple_query_skips_llm(self):
        """Simple queries should use heuristics without calling LLM."""
        analyzer = QueryAnalyzer.__new__(QueryAnalyzer)
        analyzer.use_heuristics = True
        analyzer.heuristic_confidence_threshold = 0.85

        mock_llm = AsyncMock()
        analyzer.llm = mock_llm

        result = await analyzer.analyze("What is Python?")

        assert result.complexity == QueryComplexity.SIMPLE
        mock_llm.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_ambiguous_query_calls_llm(self):
        """Ambiguous queries should fall through to LLM."""
        analyzer = QueryAnalyzer.__new__(QueryAnalyzer)
        analyzer.use_heuristics = True
        analyzer.heuristic_confidence_threshold = 0.85

        mock_llm = AsyncMock()
        mock_msg = MagicMock()
        mock_msg.content = json.dumps(
            {
                "complexity": "moderate",
                "intent": "analysis",
                "confidence": 0.82,
                "key_topics": ["project"],
                "sub_questions": [],
                "reasoning": "Moderate analysis needed",
                "estimated_sources": 2,
                "estimated_search_calls": 2,
                "estimated_llm_calls": 2,
                "recommended_strategies": ["hybrid"],
                "estimated_time_seconds": 8.0,
                "requires_tools": False,
                "requires_structured_data": False,
            }
        )
        mock_llm.ainvoke = AsyncMock(return_value=mock_msg)
        analyzer.llm = mock_llm

        result = await analyzer.analyze(
            "Explain the main architectural decisions in our project and their trade-offs"
        )

        assert result.complexity == QueryComplexity.MODERATE
        mock_llm.ainvoke.assert_called_once()


# ============================================================================
# QueryAnalysis - Serialization Tests
# ============================================================================


class TestQueryAnalysisSerialization:
    """Test QueryAnalysis dataclass serialization."""

    def test_to_dict(self):
        analysis = QueryAnalysis(
            original_query="Test query",
            complexity=QueryComplexity.MODERATE,
            intent=QueryIntent.COMPARISON,
            confidence=0.88,
            key_topics=["a", "b"],
            sub_questions=["Q1?", "Q2?"],
            resource_estimate=ResourceEstimate(
                estimated_sources=3,
                requires_tools=True,
            ),
            reasoning="Test",
            recommended_agent_count=2,
            recommended_agent_roles=["researcher", "analyst"],
        )

        d = analysis.to_dict()
        assert d["complexity"] == "moderate"
        assert d["intent"] == "comparison"
        assert d["confidence"] == 0.88
        assert d["resource_estimate"]["requires_tools"] is True
        assert len(d["key_topics"]) == 2


# ============================================================================
# ExecutionPlan Tests
# ============================================================================


class TestExecutionPlan:
    """Test ExecutionPlan lifecycle methods."""

    def _make_plan(self) -> ExecutionPlan:
        return ExecutionPlan(
            query="test",
            complexity=QueryComplexity.MODERATE,
            intent=QueryIntent.COMPARISON,
            subtasks=[
                SubTask(
                    id="task_1",
                    description="Search",
                    agent_role="researcher",
                    dependencies=[],
                    search_strategy="hybrid",
                ),
                SubTask(
                    id="task_2",
                    description="Analyze",
                    agent_role="analyst",
                    dependencies=["task_1"],
                ),
                SubTask(
                    id="task_3",
                    description="Synthesize",
                    agent_role="synthesizer",
                    dependencies=["task_1", "task_2"],
                ),
            ],
            parallel_groups=[["task_1"]],
        )

    def test_get_ready_tasks_initial(self):
        plan = self._make_plan()
        ready = plan.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "task_1"

    def test_get_ready_tasks_after_first_completion(self):
        plan = self._make_plan()
        plan.mark_completed("task_1", "search results")
        ready = plan.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "task_2"

    def test_get_ready_tasks_after_two_completions(self):
        plan = self._make_plan()
        plan.mark_completed("task_1")
        plan.mark_completed("task_2")
        ready = plan.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "task_3"

    def test_is_complete(self):
        plan = self._make_plan()
        assert plan.is_complete is False
        plan.mark_completed("task_1")
        plan.mark_completed("task_2")
        assert plan.is_complete is False
        plan.mark_completed("task_3")
        assert plan.is_complete is True

    def test_is_complete_with_failure(self):
        plan = self._make_plan()
        plan.mark_completed("task_1")
        plan.mark_failed("task_2", "error")
        plan.mark_completed("task_3")
        assert plan.is_complete is True

    def test_progress_pct(self):
        plan = self._make_plan()
        assert plan.progress_pct == 0.0
        plan.mark_completed("task_1")
        assert plan.progress_pct == pytest.approx(33.3, abs=0.1)
        plan.mark_completed("task_2")
        assert plan.progress_pct == pytest.approx(66.7, abs=0.1)
        plan.mark_completed("task_3")
        assert plan.progress_pct == 100.0

    def test_progress_empty_plan(self):
        plan = ExecutionPlan(
            query="test",
            complexity=QueryComplexity.SIMPLE,
            intent=QueryIntent.FACTUAL_LOOKUP,
        )
        assert plan.progress_pct == 100.0

    def test_to_dict(self):
        plan = self._make_plan()
        d = plan.to_dict()
        assert d["complexity"] == "moderate"
        assert len(d["subtasks"]) == 3
        assert d["subtasks"][0]["id"] == "task_1"
        assert d["subtasks"][1]["dependencies"] == ["task_1"]

    def test_mark_failed(self):
        plan = self._make_plan()
        plan.mark_failed("task_1", "timeout")
        assert plan.subtasks[0].status == TaskStatus.FAILED
        assert plan.subtasks[0].result == "timeout"


class TestSubTask:
    """Test SubTask dataclass."""

    def test_to_dict(self):
        task = SubTask(
            id="t1",
            description="Do something",
            agent_role="researcher",
            dependencies=["t0"],
            search_strategy="hybrid",
            expected_output="Results",
            priority=2,
        )
        d = task.to_dict()
        assert d["id"] == "t1"
        assert d["status"] == "pending"
        assert d["dependencies"] == ["t0"]


# ============================================================================
# PlannerAgent Tests (mocked LLM)
# ============================================================================


class TestPlannerAgentSimple:
    """Test PlannerAgent with simple queries (no LLM needed)."""

    @pytest.mark.asyncio
    async def test_simple_factual_plan(self):
        """Simple queries should produce 2-task plans without LLM."""
        planner = PlannerAgent.__new__(PlannerAgent)
        planner.model_name = "gpt-4"

        # Build just the simple planner node to test
        analysis = QueryAnalysis(
            original_query="What is Python?",
            complexity=QueryComplexity.SIMPLE,
            intent=QueryIntent.FACTUAL_LOOKUP,
            confidence=0.90,
        )

        state: dict = {
            "query_analysis": analysis.to_dict(),
            "plan": {},
            "phase": "initial",
            "error": None,
        }

        result = await planner._plan_simple_node(state)
        plan = result["plan"]

        assert len(plan["subtasks"]) == 2
        assert plan["subtasks"][0]["agent_role"] == "researcher"
        assert plan["subtasks"][1]["dependencies"] == ["task_1"]

    @pytest.mark.asyncio
    async def test_conversational_plan(self):
        """Conversational queries should produce a single task."""
        planner = PlannerAgent.__new__(PlannerAgent)

        analysis = QueryAnalysis(
            original_query="thanks",
            complexity=QueryComplexity.SIMPLE,
            intent=QueryIntent.CONVERSATIONAL,
            confidence=0.80,
        )

        state: dict = {
            "query_analysis": analysis.to_dict(),
            "plan": {},
            "phase": "initial",
            "error": None,
        }

        result = await planner._plan_simple_node(state)
        plan = result["plan"]

        assert len(plan["subtasks"]) == 1
        assert plan["subtasks"][0]["search_strategy"] is None


class TestPlannerAgentLLM:
    """Test PlannerAgent LLM-based planning with mocked LLM."""

    @pytest.mark.asyncio
    async def test_moderate_plan_generation(self):
        planner = PlannerAgent.__new__(PlannerAgent)

        mock_llm = AsyncMock()
        mock_msg = MagicMock()
        mock_msg.content = json.dumps(
            {
                "subtasks": [
                    {
                        "id": "task_1",
                        "description": "Search for Python performance data",
                        "agent_role": "researcher",
                        "dependencies": [],
                        "search_strategy": "hybrid",
                        "expected_output": "Performance benchmarks",
                        "priority": 1,
                    },
                    {
                        "id": "task_2",
                        "description": "Search for JavaScript performance data",
                        "agent_role": "researcher",
                        "dependencies": [],
                        "search_strategy": "hybrid",
                        "expected_output": "Performance benchmarks",
                        "priority": 1,
                    },
                    {
                        "id": "task_3",
                        "description": "Compare and synthesize findings",
                        "agent_role": "analyst",
                        "dependencies": ["task_1", "task_2"],
                        "search_strategy": None,
                        "expected_output": "Comparison analysis",
                        "priority": 1,
                    },
                ],
                "parallel_groups": [["task_1", "task_2"]],
                "estimated_total_time_seconds": 12.0,
            }
        )
        mock_llm.ainvoke = AsyncMock(return_value=mock_msg)
        planner.llm = mock_llm

        analysis = QueryAnalysis(
            original_query="Compare Python and JavaScript",
            complexity=QueryComplexity.MODERATE,
            intent=QueryIntent.COMPARISON,
            confidence=0.88,
        )

        state: dict = {
            "query_analysis": analysis.to_dict(),
            "plan": {},
            "phase": "initial",
            "error": None,
        }

        result = await planner._plan_with_llm_node(state)
        plan = result["plan"]

        assert len(plan["subtasks"]) == 3
        assert plan["parallel_groups"] == [["task_1", "task_2"]]

    @pytest.mark.asyncio
    async def test_llm_failure_fallback(self):
        planner = PlannerAgent.__new__(PlannerAgent)

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        planner.llm = mock_llm

        analysis = QueryAnalysis(
            original_query="Analyze trends",
            complexity=QueryComplexity.MODERATE,
            intent=QueryIntent.ANALYSIS,
            confidence=0.75,
        )

        state: dict = {
            "query_analysis": analysis.to_dict(),
            "plan": {},
            "phase": "initial",
            "error": None,
        }

        result = await planner._plan_with_llm_node(state)
        plan = result["plan"]

        # Should get a fallback plan
        assert len(plan["subtasks"]) >= 2
        assert result["phase"] == "planned_fallback"


class TestPlannerValidation:
    """Test plan validation and circular dependency removal."""

    @pytest.mark.asyncio
    async def test_removes_invalid_dependencies(self):
        planner = PlannerAgent.__new__(PlannerAgent)

        state: dict = {
            "query_analysis": {},
            "plan": {
                "subtasks": [
                    {
                        "id": "task_1",
                        "description": "First",
                        "agent_role": "researcher",
                        "dependencies": ["nonexistent_task"],
                    },
                    {
                        "id": "task_2",
                        "description": "Second",
                        "agent_role": "analyst",
                        "dependencies": ["task_1"],
                    },
                ],
            },
            "phase": "planned",
            "error": None,
        }

        result = await planner._validate_node(state)
        plan = result["plan"]

        # Invalid dependency should be removed
        assert plan["subtasks"][0]["dependencies"] == []
        assert plan["subtasks"][1]["dependencies"] == ["task_1"]

    @pytest.mark.asyncio
    async def test_deduplicates_task_ids(self):
        planner = PlannerAgent.__new__(PlannerAgent)

        state: dict = {
            "query_analysis": {},
            "plan": {
                "subtasks": [
                    {
                        "id": "task_1",
                        "description": "First",
                        "agent_role": "researcher",
                        "dependencies": [],
                    },
                    {
                        "id": "task_1",
                        "description": "Duplicate",
                        "agent_role": "analyst",
                        "dependencies": [],
                    },
                ],
            },
            "phase": "planned",
            "error": None,
        }

        result = await planner._validate_node(state)
        plan = result["plan"]

        ids = [t["id"] for t in plan["subtasks"]]
        assert len(ids) == len(set(ids))  # All unique

    def test_circular_dependency_removal(self):
        planner = PlannerAgent.__new__(PlannerAgent)

        subtasks = [
            {
                "id": "task_1",
                "description": "A",
                "agent_role": "researcher",
                "dependencies": ["task_2"],
            },
            {
                "id": "task_2",
                "description": "B",
                "agent_role": "analyst",
                "dependencies": ["task_1"],
            },
        ]

        planner._remove_circular_deps(subtasks)

        # At least one of the circular deps should be removed
        deps_1 = subtasks[0]["dependencies"]
        deps_2 = subtasks[1]["dependencies"]
        # Can't both depend on each other
        assert not (("task_2" in deps_1) and ("task_1" in deps_2))


class TestPlannerFallbackPlans:
    """Test fallback plan generation."""

    def test_moderate_fallback(self):
        planner = PlannerAgent.__new__(PlannerAgent)
        plan = planner._fallback_plan(
            {"complexity": "moderate", "original_query": "test query"}
        )
        assert len(plan["subtasks"]) == 2
        assert plan["subtasks"][1]["dependencies"] == ["task_1"]

    def test_complex_fallback(self):
        planner = PlannerAgent.__new__(PlannerAgent)
        plan = planner._fallback_plan(
            {"complexity": "complex", "original_query": "test query"}
        )
        assert len(plan["subtasks"]) == 3
        assert "task_1" in plan["subtasks"][2]["dependencies"]
        assert "task_2" in plan["subtasks"][2]["dependencies"]


class TestPlannerRouting:
    """Test the routing logic in the planner workflow."""

    def test_route_simple(self):
        planner = PlannerAgent.__new__(PlannerAgent)
        state = {"query_analysis": {"complexity": "simple"}}
        assert planner._route_by_complexity(state) == "simple"

    def test_route_moderate(self):
        planner = PlannerAgent.__new__(PlannerAgent)
        state = {"query_analysis": {"complexity": "moderate"}}
        assert planner._route_by_complexity(state) == "needs_llm"

    def test_route_complex(self):
        planner = PlannerAgent.__new__(PlannerAgent)
        state = {"query_analysis": {"complexity": "complex"}}
        assert planner._route_by_complexity(state) == "needs_llm"

    def test_route_missing_defaults_to_llm(self):
        planner = PlannerAgent.__new__(PlannerAgent)
        state = {"query_analysis": {}}
        assert planner._route_by_complexity(state) == "needs_llm"


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_query_heuristic(self):
        analyzer = QueryAnalyzer.__new__(QueryAnalyzer)
        analyzer.use_heuristics = True
        analyzer.heuristic_confidence_threshold = 0.85

        result = analyzer._heuristic_classify("")
        # Empty string has 1 word (empty), should match conversational
        assert result is not None
        assert result.intent == QueryIntent.CONVERSATIONAL

    def test_very_long_query_heuristic(self):
        analyzer = QueryAnalyzer.__new__(QueryAnalyzer)
        analyzer.use_heuristics = True
        analyzer.heuristic_confidence_threshold = 0.85

        long_query = (
            "compare the relationship between " + " and ".join(
                [f"factor_{i}" for i in range(20)]
            ) + " and thoroughly evaluate the impact on productivity"
        )
        result = analyzer._heuristic_classify(long_query)
        # Long query with "compare", "relationship between", "thoroughly" should be complex
        assert result is not None
        assert result.complexity == QueryComplexity.COMPLEX

    def test_resource_estimate_defaults(self):
        estimate = ResourceEstimate()
        assert estimate.estimated_sources == 1
        assert estimate.estimated_search_calls == 1
        assert estimate.estimated_llm_calls == 1
        assert estimate.recommended_strategies == ["hybrid"]
        assert estimate.requires_tools is False

    def test_agent_role_enum_values(self):
        assert AgentRole.RESEARCHER.value == "researcher"
        assert AgentRole.ANALYST.value == "analyst"
        assert AgentRole.DATA_ANALYST.value == "data_analyst"
        assert AgentRole.SYNTHESIZER.value == "synthesizer"
        assert AgentRole.WRITER.value == "writer"

    def test_task_status_enum_values(self):
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.SKIPPED.value == "skipped"
