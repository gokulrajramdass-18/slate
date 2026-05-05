"""
Unit tests for tool filtering module.

Tests the two-phase tool discovery system that reduces context window bloat
in plan mode agents.
"""

import pytest
import asyncio
from typing import List
from unittest.mock import Mock, patch, AsyncMock
from langchain.tools import BaseTool

from deep_agents_integration.tool_filtering import (
    PlanModeToolFilter,
    ToolFilterResult,
    PLAN_MODE_SAFE_TOOLS,
    PLAN_MODE_EXCLUDED_TOOLS,
    get_plan_mode_filter,
)


# ============================================================================
# Mock Tools
# ============================================================================

def create_mock_tool(name: str, description: str = "") -> BaseTool:
    """Create a mock LangChain tool"""
    tool = Mock(spec=BaseTool)
    tool.name = name
    tool.description = description
    return tool


@pytest.fixture
def sample_tools() -> List[BaseTool]:
    """Create sample tools for testing"""
    return [
        create_mock_tool("Read", "Read files from filesystem"),
        create_mock_tool("Write", "Write files to filesystem"),
        create_mock_tool("Glob", "Find files matching pattern"),
        create_mock_tool("Grep", "Search file contents"),
        create_mock_tool("Agent", "Spawn subagents"),
        create_mock_tool("Bash", "Run shell commands"),
        create_mock_tool("Edit", "Edit file contents"),
        create_mock_tool("WebFetch", "Fetch web pages"),
        create_mock_tool("WebSearch", "Search the web"),
        create_mock_tool("TaskCreate", "Create new task"),
        create_mock_tool("mcp__pencil__get_screenshot", "Get screenshot from Pencil design"),
        create_mock_tool("mcp__pencil__batch_design", "Create design components"),
        create_mock_tool("hana_query_table", "Query HANA database table"),
        create_mock_tool("api_call_salesforce", "Call Salesforce API"),
    ]


# ============================================================================
# Heuristic Filtering Tests
# ============================================================================

class TestHeuristicFiltering:
    """Test Phase 1: Heuristic filtering"""

    def test_file_exploration_query(self, sample_tools):
        """Test that file exploration queries select appropriate tools"""
        filter_instance = PlanModeToolFilter()
        filter_instance._enabled = True

        query = "Find all Python files in the src directory and read their contents"
        result = filter_instance._heuristic_filter(query, sample_tools)

        assert result.phase_used == "heuristic"
        assert "Read" in result.selected_tool_ids
        assert "Glob" in result.selected_tool_ids
        assert "Grep" in result.selected_tool_ids
        assert "Write" not in result.selected_tool_ids  # Excluded in plan mode
        assert result.confidence > 0.7

    def test_database_query(self, sample_tools):
        """Test that database queries select HANA tools"""
        filter_instance = PlanModeToolFilter()
        filter_instance._enabled = True

        query = "Query the HANA database to find all customers in California"
        result = filter_instance._heuristic_filter(query, sample_tools)

        assert result.phase_used == "heuristic"
        assert "hana_query_table" in result.selected_tool_ids
        assert "Read" in result.selected_tool_ids  # Always included
        assert result.confidence > 0.7

    def test_web_research_query(self, sample_tools):
        """Test that web research queries select web tools"""
        filter_instance = PlanModeToolFilter()
        filter_instance._enabled = True

        query = "Search the web for documentation on FastAPI routing"
        result = filter_instance._heuristic_filter(query, sample_tools)

        assert result.phase_used == "heuristic"
        assert "WebSearch" in result.selected_tool_ids
        assert "WebFetch" in result.selected_tool_ids
        assert result.confidence > 0.7

    def test_design_query(self, sample_tools):
        """Test that design queries select Pencil MCP tools"""
        filter_instance = PlanModeToolFilter()
        filter_instance._enabled = True

        query = "Design a new UI component for the login screen"
        result = filter_instance._heuristic_filter(query, sample_tools)

        assert result.phase_used == "heuristic"
        # Should include Pencil tools
        pencil_tools = [t for t in result.selected_tool_ids if "pencil" in t.lower()]
        assert len(pencil_tools) > 0

    def test_ambiguous_query_low_confidence(self, sample_tools):
        """Test that ambiguous queries return low confidence"""
        filter_instance = PlanModeToolFilter()
        filter_instance._enabled = True

        query = "Help me with this"
        result = filter_instance._heuristic_filter(query, sample_tools)

        assert result.phase_used == "heuristic"
        # Should have low confidence for ambiguous query
        assert result.confidence < 0.85
        # Should at least include base safe tools
        assert "Read" in result.selected_tool_ids
        assert "Glob" in result.selected_tool_ids


# ============================================================================
# Safety Rules Tests
# ============================================================================

class TestSafetyRules:
    """Test safety constraints"""

    def test_always_includes_base_tools(self, sample_tools):
        """Test that base safe tools are always included"""
        filter_instance = PlanModeToolFilter()

        selected = filter_instance._apply_safety_rules([], sample_tools)

        for safe_tool in ["Read", "Glob", "Grep", "Agent"]:
            assert safe_tool in selected

    def test_never_includes_write_tools(self, sample_tools):
        """Test that write tools are never included"""
        filter_instance = PlanModeToolFilter()

        # Try to force include write tools
        selected = filter_instance._apply_safety_rules(
            ["Write", "Edit", "Read", "Glob"],
            sample_tools
        )

        assert "Write" not in selected
        assert "Edit" not in selected
        assert "Read" in selected
        assert "Glob" in selected

    def test_max_tool_limit(self, sample_tools):
        """Test that max tool limit is enforced"""
        filter_instance = PlanModeToolFilter()
        filter_instance._max_tools = 5

        # Try to select all tools
        all_tool_names = [t.name for t in sample_tools]
        selected = filter_instance._apply_safety_rules(all_tool_names, sample_tools)

        assert len(selected) <= 5
        # At least some base tools should be included (order may vary)
        base_tools_included = sum(1 for tool in ["Read", "Glob", "Grep", "Agent"] if tool in selected)
        assert base_tools_included >= 2  # At least 2 base tools

    def test_minimum_tool_count(self, sample_tools):
        """Test that minimum tool count is enforced"""
        filter_instance = PlanModeToolFilter()

        # Try to select no tools
        selected = filter_instance._apply_safety_rules([], sample_tools)

        assert len(selected) >= 4  # At least base safe tools


# ============================================================================
# LLM Filtering Tests
# ============================================================================

class TestLLMFiltering:
    """Test Phase 2: LLM-based filtering"""

    @pytest.mark.asyncio
    async def test_llm_filter_with_mock_response(self, sample_tools):
        """Test LLM filtering with mocked response"""
        filter_instance = PlanModeToolFilter()

        # Mock the ChatAnthropic response
        with patch('langchain_anthropic.ChatAnthropic') as mock_claude:
            mock_response = Mock()
            mock_response.content = '''
            {
                "selected_tool_ids": ["Read", "Glob", "Grep", "hana_query_table"],
                "reasoning": "File exploration and database query needed",
                "confidence": 0.95
            }
            '''
            mock_instance = AsyncMock()
            mock_instance.ainvoke.return_value = mock_response
            mock_claude.return_value = mock_instance

            query = "Find files that query the database"
            result = await filter_instance._llm_filter(query, sample_tools)

            assert result.phase_used == "llm"
            assert "Read" in result.selected_tool_ids
            assert "hana_query_table" in result.selected_tool_ids
            assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_llm_filter_fallback_on_error(self, sample_tools):
        """Test that LLM filtering falls back to safe tools on error"""
        filter_instance = PlanModeToolFilter()

        # Mock ChatAnthropic to raise an exception
        with patch('langchain_anthropic.ChatAnthropic') as mock_claude:
            mock_claude.side_effect = Exception("API error")

            query = "Test query"
            result = await filter_instance._llm_filter(query, sample_tools)

            assert result.phase_used == "llm"
            # Should fall back to safe tools
            assert "Read" in result.selected_tool_ids
            assert "Glob" in result.selected_tool_ids
            assert result.confidence < 1.0


# ============================================================================
# Two-Phase Pipeline Tests
# ============================================================================

class TestTwoPhaseFiltering:
    """Test complete two-phase filtering pipeline"""

    @pytest.mark.asyncio
    async def test_high_confidence_heuristic_skips_llm(self, sample_tools):
        """Test that high confidence heuristic skips LLM phase"""
        filter_instance = PlanModeToolFilter()
        filter_instance._confidence_threshold = 0.85

        query = "Read all Python files in the project"

        with patch.object(filter_instance, '_llm_filter') as mock_llm:
            result = await filter_instance.filter_tools_for_query(query, sample_tools)

            # LLM should not be called
            mock_llm.assert_not_called()
            assert result.phase_used == "heuristic"

    @pytest.mark.asyncio
    async def test_low_confidence_triggers_llm(self, sample_tools):
        """Test that low confidence heuristic triggers LLM phase"""
        filter_instance = PlanModeToolFilter()
        filter_instance._confidence_threshold = 0.85

        query = "Help me"  # Ambiguous query

        # Mock LLM response
        with patch('langchain_anthropic.ChatAnthropic') as mock_claude:
            mock_response = Mock()
            mock_response.content = '{"selected_tool_ids": ["Read", "Glob"], "reasoning": "Basic exploration", "confidence": 0.9}'
            mock_instance = AsyncMock()
            mock_instance.ainvoke.return_value = mock_response
            mock_claude.return_value = mock_instance

            result = await filter_instance.filter_tools_for_query(query, sample_tools)

            assert result.phase_used == "llm"


# ============================================================================
# Caching Tests
# ============================================================================

class TestCaching:
    """Test result caching"""

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_result(self, sample_tools):
        """Test that repeated queries return cached results"""
        filter_instance = PlanModeToolFilter()
        filter_instance._enabled = True

        query = "Read all files"

        # First call
        result1 = await filter_instance.filter_tools_for_query(query, sample_tools)

        # Second call (should hit cache)
        with patch.object(filter_instance, '_run_two_phase_filter') as mock_filter:
            result2 = await filter_instance.filter_tools_for_query(query, sample_tools)

            # Filter should not be called again
            mock_filter.assert_not_called()
            assert result1.selected_tool_ids == result2.selected_tool_ids

    @pytest.mark.asyncio
    async def test_different_queries_different_cache_keys(self, sample_tools):
        """Test that different queries generate different cache keys"""
        filter_instance = PlanModeToolFilter()

        query1 = "Read files"
        query2 = "Query database"

        key1 = filter_instance._cache_key(query1, [t.name for t in sample_tools])
        key2 = filter_instance._cache_key(query2, [t.name for t in sample_tools])

        assert key1 != key2


# ============================================================================
# Configuration Tests
# ============================================================================

class TestConfiguration:
    """Test configuration and environment variables"""

    def test_filtering_can_be_disabled(self, sample_tools):
        """Test that filtering can be disabled via environment variable"""
        with patch.dict('os.environ', {'PLAN_MODE_TOOL_FILTERING_ENABLED': 'false'}):
            filter_instance = PlanModeToolFilter()

            result = asyncio.run(
                filter_instance.filter_tools_for_query("Test query", sample_tools)
            )

            # Should return all tools when disabled
            assert len(result.selected_tool_ids) == len(sample_tools)
            assert result.reasoning == "Filtering disabled via PLAN_MODE_TOOL_FILTERING_ENABLED=false"

    def test_confidence_threshold_configurable(self):
        """Test that confidence threshold is configurable"""
        with patch.dict('os.environ', {'PLAN_MODE_FILTER_CONFIDENCE_THRESHOLD': '0.75'}):
            filter_instance = PlanModeToolFilter()

            assert filter_instance._confidence_threshold == 0.75

    def test_max_tools_configurable(self):
        """Test that max tools limit is configurable"""
        with patch.dict('os.environ', {'PLAN_MODE_MAX_TOOLS': '15'}):
            filter_instance = PlanModeToolFilter()

            assert filter_instance._max_tools == 15


# ============================================================================
# Singleton Tests
# ============================================================================

class TestSingleton:
    """Test singleton pattern"""

    def test_get_plan_mode_filter_returns_singleton(self):
        """Test that get_plan_mode_filter returns the same instance"""
        filter1 = get_plan_mode_filter()
        filter2 = get_plan_mode_filter()

        assert filter1 is filter2


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests with real-world scenarios"""

    @pytest.mark.asyncio
    async def test_realistic_file_exploration_scenario(self, sample_tools):
        """Test realistic file exploration scenario"""
        filter_instance = PlanModeToolFilter()
        filter_instance._enabled = True

        query = "I need to explore the API router files to understand the authentication flow"

        result = await filter_instance.filter_tools_for_query(query, sample_tools)

        # Should include file exploration tools
        assert "Read" in result.selected_tool_ids
        assert "Glob" in result.selected_tool_ids
        assert "Grep" in result.selected_tool_ids

        # Should NOT include write tools
        assert "Write" not in result.selected_tool_ids
        assert "Edit" not in result.selected_tool_ids

        # Should NOT include irrelevant MCP tools
        assert "mcp__pencil__get_screenshot" not in result.selected_tool_ids

    @pytest.mark.asyncio
    async def test_realistic_data_analysis_scenario(self, sample_tools):
        """Test realistic data analysis scenario"""
        filter_instance = PlanModeToolFilter()
        filter_instance._enabled = True

        query = "Analyze customer data from HANA and fetch additional details from Salesforce API"

        result = await filter_instance.filter_tools_for_query(query, sample_tools)

        # Should include data tools
        assert "hana_query_table" in result.selected_tool_ids
        assert "api_call_salesforce" in result.selected_tool_ids

        # Should still include base tools
        assert "Read" in result.selected_tool_ids
        assert "Agent" in result.selected_tool_ids
