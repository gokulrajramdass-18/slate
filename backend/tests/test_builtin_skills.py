"""
Unit tests for built-in skills

Tests each built-in skill handler for input validation, execution, and error handling.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from open_notebook.agents.skills.base import SkillContext, SkillCategory
from open_notebook.agents.skills.builtin.search_skill import (
    semantic_search_handler,
    create_search_skill
)


@pytest.fixture
def sample_context():
    """Create a sample skill context."""
    return SkillContext(
        agent_id="agent-123",
        agent_role="analyst",
        skill_id="test_skill",
        input_data={"query": "test query"},
        config={"strategy": "hybrid", "limit": 10}
    )


class TestSearchSkill:
    """Test semantic search skill."""

    def test_create_search_skill(self):
        """Test skill creation."""
        skill = create_search_skill()

        assert skill.id == "semantic_search"
        assert skill.name == "Semantic Search"
        assert skill.category == SkillCategory.SEARCH
        assert skill.handler == semantic_search_handler
        assert "search" in skill.tags
        assert skill.timeout_seconds == 30
        assert skill.enabled is True

    def test_search_skill_config_schema(self):
        """Test that skill has proper config schema."""
        skill = create_search_skill()

        assert skill.config_schema is not None
        assert "properties" in skill.config_schema
        assert "strategy" in skill.config_schema["properties"]
        assert "limit" in skill.config_schema["properties"]

        # Check strategy options
        strategy = skill.config_schema["properties"]["strategy"]
        assert strategy["enum"] == ["vector", "keyword", "hybrid", "agentic_rag"]
        assert strategy["default"] == "hybrid"

        # Check limit constraints
        limit_prop = skill.config_schema["properties"]["limit"]
        assert limit_prop["default"] == 10
        assert limit_prop["minimum"] == 1
        assert limit_prop["maximum"] == 100

    def test_search_skill_default_config(self):
        """Test default configuration."""
        skill = create_search_skill()

        assert skill.default_config == {"strategy": "hybrid", "limit": 10}

    @pytest.mark.asyncio
    async def test_search_handler_missing_query(self, sample_context):
        """Test that handler raises error when query is missing."""
        sample_context.input_data = {}  # No query

        with pytest.raises(ValueError, match="Query parameter is required"):
            await semantic_search_handler(sample_context)

    @pytest.mark.asyncio
    async def test_search_handler_records_steps(self, sample_context):
        """Test that handler records execution steps."""
        mock_results = []

        with patch('open_notebook.agents.skills.builtin.search_skill.get_search_strategy') as mock_strategy:
            mock_strategy_instance = AsyncMock()
            mock_strategy_instance.search = AsyncMock(return_value=mock_results)
            mock_strategy.return_value = mock_strategy_instance

            result = await semantic_search_handler(sample_context)

            # Check steps were recorded
            assert len(sample_context.steps) == 2
            assert sample_context.steps[0]["step_type"] == "searching"
            assert "hybrid" in sample_context.steps[0]["content"]
            assert sample_context.steps[1]["step_type"] == "completed"
            assert "0 results" in sample_context.steps[1]["content"]

    @pytest.mark.asyncio
    async def test_search_handler_uses_config_strategy(self, sample_context):
        """Test that handler uses strategy from config."""
        sample_context.config = {"strategy": "vector", "limit": 20}

        with patch('open_notebook.agents.skills.builtin.search_skill.get_search_strategy') as mock_strategy:
            mock_strategy_instance = AsyncMock()
            mock_strategy_instance.search = AsyncMock(return_value=[])
            mock_strategy.return_value = mock_strategy_instance

            await semantic_search_handler(sample_context)

            # Should call get_search_strategy with "vector"
            mock_strategy.assert_called_once_with("vector")

    @pytest.mark.asyncio
    async def test_search_handler_uses_config_limit(self, sample_context):
        """Test that handler uses limit from config."""
        sample_context.config = {"strategy": "hybrid", "limit": 50}

        with patch('open_notebook.agents.skills.builtin.search_skill.get_search_strategy') as mock_strategy:
            mock_strategy_instance = AsyncMock()
            mock_strategy_instance.search = AsyncMock(return_value=[])
            mock_strategy.return_value = mock_strategy_instance

            await semantic_search_handler(sample_context)

            # Check limit was passed to search
            call_kwargs = mock_strategy_instance.search.call_args[1]
            assert call_kwargs["limit"] == 50

    @pytest.mark.asyncio
    async def test_search_handler_with_notebook_filter(self, sample_context):
        """Test that handler adds notebook_id to filters."""
        sample_context.input_data = {
            "query": "test",
            "notebook_id": "notebook-123"
        }

        with patch('open_notebook.agents.skills.builtin.search_skill.get_search_strategy') as mock_strategy:
            mock_strategy_instance = AsyncMock()
            mock_strategy_instance.search = AsyncMock(return_value=[])
            mock_strategy.return_value = mock_strategy_instance

            await semantic_search_handler(sample_context)

            # Check notebook filter was added
            call_kwargs = mock_strategy_instance.search.call_args[1]
            assert call_kwargs["filters"]["notebook_id"] == "notebook-123"

    @pytest.mark.asyncio
    async def test_search_handler_with_additional_filters(self, sample_context):
        """Test that handler preserves additional filters."""
        sample_context.input_data = {
            "query": "test",
            "filters": {"source_type": "pdf", "archived": False}
        }

        with patch('open_notebook.agents.skills.builtin.search_skill.get_search_strategy') as mock_strategy:
            mock_strategy_instance = AsyncMock()
            mock_strategy_instance.search = AsyncMock(return_value=[])
            mock_strategy.return_value = mock_strategy_instance

            await semantic_search_handler(sample_context)

            # Check filters were passed
            call_kwargs = mock_strategy_instance.search.call_args[1]
            assert call_kwargs["filters"]["source_type"] == "pdf"
            assert call_kwargs["filters"]["archived"] is False

    @pytest.mark.asyncio
    async def test_search_handler_returns_results(self, sample_context):
        """Test that handler returns properly formatted results."""
        # Create mock results with to_dict method
        mock_result1 = MagicMock()
        mock_result1.to_dict.return_value = {"id": "1", "title": "Result 1", "score": 0.9}
        mock_result2 = MagicMock()
        mock_result2.to_dict.return_value = {"id": "2", "title": "Result 2", "score": 0.8}

        with patch('open_notebook.agents.skills.builtin.search_skill.get_search_strategy') as mock_strategy:
            mock_strategy_instance = AsyncMock()
            mock_strategy_instance.search = AsyncMock(return_value=[mock_result1, mock_result2])
            mock_strategy.return_value = mock_strategy_instance

            result = await semantic_search_handler(sample_context)

            # Check result structure
            assert "results" in result
            assert "count" in result
            assert "strategy" in result
            assert "query" in result

            assert result["count"] == 2
            assert result["strategy"] == "hybrid"
            assert result["query"] == "test query"
            assert len(result["results"]) == 2
            assert result["results"][0]["title"] == "Result 1"

    @pytest.mark.asyncio
    async def test_search_handler_with_dict_results(self, sample_context):
        """Test handler with results that have __dict__ but no to_dict."""
        # Create object with __dict__ attribute
        class SimpleResult:
            def __init__(self, id, title):
                self.id = id
                self.title = title

        mock_results = [
            SimpleResult("1", "Result 1"),
            SimpleResult("2", "Result 2")
        ]

        with patch('open_notebook.agents.skills.builtin.search_skill.get_search_strategy') as mock_strategy:
            mock_strategy_instance = AsyncMock()
            mock_strategy_instance.search = AsyncMock(return_value=mock_results)
            mock_strategy.return_value = mock_strategy_instance

            result = await semantic_search_handler(sample_context)

            assert result["count"] == 2
            assert result["results"][0]["id"] == "1"
            assert result["results"][1]["title"] == "Result 2"

    @pytest.mark.asyncio
    async def test_search_handler_with_string_results(self, sample_context):
        """Test handler with results that are simple strings."""
        mock_results = ["result1", "result2", "result3"]

        with patch('open_notebook.agents.skills.builtin.search_skill.get_search_strategy') as mock_strategy:
            mock_strategy_instance = AsyncMock()
            mock_strategy_instance.search = AsyncMock(return_value=mock_results)
            mock_strategy.return_value = mock_strategy_instance

            result = await semantic_search_handler(sample_context)

            assert result["count"] == 3
            assert result["results"] == ["result1", "result2", "result3"]

    @pytest.mark.asyncio
    async def test_search_handler_default_strategy(self):
        """Test that handler uses default strategy when not configured."""
        context = SkillContext(
            agent_id="agent-123",
            agent_role="analyst",
            skill_id="test_skill",
            input_data={"query": "test"},
            config={}  # No strategy configured
        )

        with patch('open_notebook.agents.skills.builtin.search_skill.get_search_strategy') as mock_strategy:
            mock_strategy_instance = AsyncMock()
            mock_strategy_instance.search = AsyncMock(return_value=[])
            mock_strategy.return_value = mock_strategy_instance

            await semantic_search_handler(context)

            # Should use default "hybrid"
            mock_strategy.assert_called_once_with("hybrid")

    @pytest.mark.asyncio
    async def test_search_handler_default_limit(self):
        """Test that handler uses default limit when not configured."""
        context = SkillContext(
            agent_id="agent-123",
            agent_role="analyst",
            skill_id="test_skill",
            input_data={"query": "test"},
            config={}  # No limit configured
        )

        with patch('open_notebook.agents.skills.builtin.search_skill.get_search_strategy') as mock_strategy:
            mock_strategy_instance = AsyncMock()
            mock_strategy_instance.search = AsyncMock(return_value=[])
            mock_strategy.return_value = mock_strategy_instance

            await semantic_search_handler(context)

            # Should use default 10
            call_kwargs = mock_strategy_instance.search.call_args[1]
            assert call_kwargs["limit"] == 10

    @pytest.mark.asyncio
    async def test_search_handler_step_metadata(self, sample_context):
        """Test that completion step includes metadata."""
        mock_results = [MagicMock(), MagicMock(), MagicMock()]
        for r in mock_results:
            r.to_dict.return_value = {}

        with patch('open_notebook.agents.skills.builtin.search_skill.get_search_strategy') as mock_strategy:
            mock_strategy_instance = AsyncMock()
            mock_strategy_instance.search = AsyncMock(return_value=mock_results)
            mock_strategy.return_value = mock_strategy_instance

            await semantic_search_handler(sample_context)

            # Check completion step metadata
            completion_step = sample_context.steps[1]
            assert completion_step["metadata"]["result_count"] == 3
            assert completion_step["metadata"]["strategy"] == "hybrid"


class TestBuiltinSkillsRegistration:
    """Test builtin skills registration."""

    @pytest.mark.asyncio
    async def test_register_builtin_skills(self):
        """Test registering all builtin skills."""
        from open_notebook.agents.skills import get_skill_registry
        from open_notebook.agents.skills.builtin import register_builtin_skills

        registry = get_skill_registry()
        registry.clear()

        # Register builtin skills
        register_builtin_skills()

        # Check that skills were registered
        skills = registry.list_skills()
        assert len(skills) >= 1  # At least search skill

        # Check search skill exists
        search_skill = registry.get_skill("semantic_search")
        assert search_skill is not None
        assert search_skill.name == "Semantic Search"

    @pytest.mark.asyncio
    async def test_builtin_skills_have_metadata(self):
        """Test that builtin skills have proper metadata."""
        from open_notebook.agents.skills import get_skill_registry
        from open_notebook.agents.skills.builtin import register_builtin_skills

        registry = get_skill_registry()
        registry.clear()
        register_builtin_skills()

        for skill in registry.list_skills():
            # All should have required fields
            assert skill.id
            assert skill.name
            assert skill.description
            assert skill.category
            assert skill.handler is not None
            assert skill.version
            assert isinstance(skill.tags, list)
            assert skill.timeout_seconds > 0

    @pytest.mark.asyncio
    async def test_builtin_skills_registration_errors_logged(self):
        """Test that registration errors are logged but don't crash."""
        from open_notebook.agents.skills.builtin import register_builtin_skills

        # This should not raise even if one skill fails
        # (The function catches exceptions internally)
        register_builtin_skills()  # Should complete without raising


class TestSkillComposition:
    """Test skill composition (skills calling other skills)."""

    @pytest.mark.asyncio
    async def test_context_can_call_other_skills(self):
        """Test that context.call_skill works for composition."""
        from open_notebook.agents.skills import (
            get_skill_registry,
            Skill,
            SkillCategory
        )

        # Create two skills
        async def skill1_handler(context: SkillContext):
            return {"result": "skill1"}

        async def skill2_handler(context: SkillContext):
            # Call skill1 from skill2
            result = await context.call_skill(
                "skill1",
                {"data": "test"},
                {"config": "value"}
            )
            return {"skill1_result": result, "skill2_data": "processed"}

        registry = get_skill_registry()
        registry.clear()

        skill1 = Skill(
            id="skill1",
            name="Skill 1",
            description="First skill",
            category=SkillCategory.TOOLS,
            handler=skill1_handler
        )

        skill2 = Skill(
            id="skill2",
            name="Skill 2",
            description="Second skill that calls first",
            category=SkillCategory.TOOLS,
            handler=skill2_handler
        )

        registry.register_skill(skill1)
        registry.register_skill(skill2)

        # Execute skill2 (which will call skill1)
        from open_notebook.agents.skills import get_skill_executor

        context = SkillContext(
            agent_id="agent-123",
            agent_role="analyst",
            skill_id="skill2",
            input_data={}
        )

        executor = get_skill_executor()
        result = await executor.execute("skill2", context)

        assert result.success is True
        # Result should contain data from both skills
        assert "skill1_result" in result.result
        assert "skill2_data" in result.result
