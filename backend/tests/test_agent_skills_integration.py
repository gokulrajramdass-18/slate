"""
Integration tests for Agent Skills

Tests skills integration with standalone agents, including execution flow,
step recording, and result handling.
"""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock

from open_notebook.agents.skills import (
    Skill,
    SkillCategory,
    SkillContext,
    get_skill_registry,
    get_skill_executor
)


@pytest.fixture
def registry():
    """Get clean registry."""
    reg = get_skill_registry()
    reg.clear()
    return reg


@pytest.fixture
def executor():
    """Get executor instance."""
    return get_skill_executor()


# Sample skill handlers for testing
async def analysis_skill_handler(context: SkillContext):
    """Analyze some data."""
    context.record_step("analyzing", "Analyzing data", status="running")

    data = context.input_data.get("data", "")
    result = {
        "analysis": f"Analyzed: {data}",
        "word_count": len(data.split()),
        "agent": context.agent_id
    }

    context.record_step("completed", "Analysis complete", status="completed")
    return result


async def search_skill_handler(context: SkillContext):
    """Search for information."""
    query = context.input_data.get("query", "")
    limit = context.config.get("limit", 5)

    context.record_step("searching", f"Searching for: {query}", status="running")

    # Simulate search results
    results = [
        {"id": i, "title": f"Result {i}", "query": query}
        for i in range(limit)
    ]

    context.record_step("completed", f"Found {len(results)} results", status="completed")

    return {
        "results": results,
        "count": len(results),
        "query": query
    }


async def memory_skill_handler(context: SkillContext):
    """Store agent memory."""
    key = context.input_data.get("key")
    value = context.input_data.get("value")

    # Store in agent state
    context.agent_state[key] = value

    context.record_step("stored", f"Stored memory: {key}", status="completed")

    return {"stored": True, "key": key}


class TestSkillIntegrationBasics:
    """Test basic skill integration with agents."""

    @pytest.mark.asyncio
    async def test_execute_skill_for_agent(self, registry, executor):
        """Test executing a skill for an agent."""
        # Register skill
        skill = Skill(
            id="analysis_skill",
            name="Analysis",
            description="Analyze data",
            category=SkillCategory.ANALYSIS,
            handler=analysis_skill_handler
        )
        registry.register_skill(skill)

        # Create context
        context = SkillContext(
            agent_id="agent-123",
            agent_role="analyst",
            skill_id="analysis_skill",
            input_data={"data": "hello world test data"}
        )

        # Execute
        result = await executor.execute("analysis_skill", context)

        assert result.success is True
        assert result.result["analysis"] == "Analyzed: hello world test data"
        assert result.result["word_count"] == 4
        assert result.result["agent"] == "agent-123"

    @pytest.mark.asyncio
    async def test_skill_step_recording(self, registry, executor):
        """Test that skill steps are recorded."""
        skill = Skill(
            id="analysis_skill",
            name="Analysis",
            description="Analyze data",
            category=SkillCategory.ANALYSIS,
            handler=analysis_skill_handler
        )
        registry.register_skill(skill)

        context = SkillContext(
            agent_id="agent-123",
            agent_role="analyst",
            skill_id="analysis_skill",
            input_data={"data": "test"}
        )

        result = await executor.execute("analysis_skill", context)

        # Check steps were recorded
        assert len(result.steps) == 2
        assert result.steps[0]["step_type"] == "analyzing"
        assert result.steps[0]["status"] == "running"
        assert result.steps[1]["step_type"] == "completed"
        assert result.steps[1]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_skill_with_config(self, registry, executor):
        """Test skill execution with configuration."""
        skill = Skill(
            id="search_skill",
            name="Search",
            description="Search data",
            category=SkillCategory.SEARCH,
            handler=search_skill_handler,
            default_config={"limit": 5}
        )
        registry.register_skill(skill)

        context = SkillContext(
            agent_id="agent-123",
            agent_role="researcher",
            skill_id="search_skill",
            input_data={"query": "machine learning"},
            config={"limit": 3}  # Override default
        )

        result = await executor.execute("search_skill", context)

        assert result.success is True
        assert result.result["count"] == 3  # Used configured limit
        assert result.result["query"] == "machine learning"


class TestSkillStateManagement:
    """Test agent state management in skills."""

    @pytest.mark.asyncio
    async def test_skill_modifies_agent_state(self, registry, executor):
        """Test that skills can modify agent state."""
        skill = Skill(
            id="memory_skill",
            name="Memory",
            description="Store memory",
            category=SkillCategory.MEMORY,
            handler=memory_skill_handler
        )
        registry.register_skill(skill)

        # Create context with empty agent state
        agent_state = {}
        context = SkillContext(
            agent_id="agent-123",
            agent_role="analyst",
            skill_id="memory_skill",
            input_data={"key": "last_query", "value": "test query"},
            agent_state=agent_state
        )

        result = await executor.execute("memory_skill", context)

        assert result.success is True
        assert result.result["stored"] is True
        # Agent state should be updated
        assert agent_state["last_query"] == "test query"

    @pytest.mark.asyncio
    async def test_skill_shares_agent_state(self, registry, executor):
        """Test that multiple skill executions share agent state."""
        skill = Skill(
            id="memory_skill",
            name="Memory",
            description="Store memory",
            category=SkillCategory.MEMORY,
            handler=memory_skill_handler
        )
        registry.register_skill(skill)

        # Shared agent state
        agent_state = {"existing": "data"}

        # First execution
        context1 = SkillContext(
            agent_id="agent-123",
            agent_role="analyst",
            skill_id="memory_skill",
            input_data={"key": "key1", "value": "value1"},
            agent_state=agent_state
        )
        await executor.execute("memory_skill", context1)

        # Second execution (same agent state)
        context2 = SkillContext(
            agent_id="agent-123",
            agent_role="analyst",
            skill_id="memory_skill",
            input_data={"key": "key2", "value": "value2"},
            agent_state=agent_state
        )
        await executor.execute("memory_skill", context2)

        # Both should be in shared state
        assert agent_state["existing"] == "data"
        assert agent_state["key1"] == "value1"
        assert agent_state["key2"] == "value2"


class TestMultipleSkillExecution:
    """Test executing multiple skills in sequence."""

    @pytest.mark.asyncio
    async def test_execute_multiple_skills_sequentially(self, registry, executor):
        """Test executing multiple skills in sequence."""
        # Register skills
        analysis_skill = Skill(
            id="analysis_skill",
            name="Analysis",
            description="Analyze data",
            category=SkillCategory.ANALYSIS,
            handler=analysis_skill_handler
        )

        search_skill = Skill(
            id="search_skill",
            name="Search",
            description="Search data",
            category=SkillCategory.SEARCH,
            handler=search_skill_handler
        )

        registry.register_skill(analysis_skill)
        registry.register_skill(search_skill)

        # Execute first skill
        context1 = SkillContext(
            agent_id="agent-123",
            agent_role="analyst",
            skill_id="analysis_skill",
            input_data={"data": "test data"}
        )
        result1 = await executor.execute("analysis_skill", context1)

        # Execute second skill
        context2 = SkillContext(
            agent_id="agent-123",
            agent_role="analyst",
            skill_id="search_skill",
            input_data={"query": "test"},
            config={"limit": 2}
        )
        result2 = await executor.execute("search_skill", context2)

        # Both should succeed
        assert result1.success is True
        assert result2.success is True
        assert "analysis" in result1.result
        assert "results" in result2.result


class TestSkillResourceInjection:
    """Test resource injection into skill context."""

    @pytest.mark.asyncio
    async def test_llm_injection(self, registry, executor):
        """Test that LLM is injected into context."""
        async def llm_skill_handler(context: SkillContext):
            if context.llm is None:
                return {"has_llm": False}

            # Use LLM
            response = await context.llm.ainvoke("test prompt")
            return {"has_llm": True, "response": response}

        skill = Skill(
            id="llm_skill",
            name="LLM Skill",
            description="Uses LLM",
            category=SkillCategory.SYNTHESIS,
            handler=llm_skill_handler
        )
        registry.register_skill(skill)

        # Mock LLM
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value="LLM response")

        context = SkillContext(
            agent_id="agent-123",
            agent_role="analyst",
            skill_id="llm_skill",
            input_data={},
            llm=mock_llm
        )

        result = await executor.execute("llm_skill", context)

        assert result.success is True
        assert result.result["has_llm"] is True
        assert result.result["response"] == "LLM response"

    @pytest.mark.asyncio
    async def test_database_injection(self, registry, executor):
        """Test that database is injected into context."""
        async def db_skill_handler(context: SkillContext):
            if context.database is None:
                return {"has_database": False}

            # Use database
            data = await context.database.query("SELECT * FROM test")
            return {"has_database": True, "data": data}

        skill = Skill(
            id="db_skill",
            name="Database Skill",
            description="Uses database",
            category=SkillCategory.DATA_QUERY,
            handler=db_skill_handler
        )
        registry.register_skill(skill)

        # Mock database
        mock_db = AsyncMock()
        mock_db.query = AsyncMock(return_value=[{"id": 1, "name": "test"}])

        context = SkillContext(
            agent_id="agent-123",
            agent_role="analyst",
            skill_id="db_skill",
            input_data={},
            database=mock_db
        )

        result = await executor.execute("db_skill", context)

        assert result.success is True
        assert result.result["has_database"] is True
        assert len(result.result["data"]) == 1

    @pytest.mark.asyncio
    async def test_tool_registry_access(self, registry, executor):
        """Test that tools can be accessed from context."""
        async def tool_skill_handler(context: SkillContext):
            tool = context.get_tool("test_tool")
            if tool is None:
                return {"has_tool": False}
            return {"has_tool": True, "tool_name": tool.name}

        skill = Skill(
            id="tool_skill",
            name="Tool Skill",
            description="Uses tools",
            category=SkillCategory.TOOLS,
            handler=tool_skill_handler
        )
        registry.register_skill(skill)

        # Mock tool registry
        mock_tool = MagicMock()
        mock_tool.name = "Test Tool"

        mock_tool_registry = MagicMock()
        mock_tool_registry.get_tool = MagicMock(return_value=mock_tool)

        context = SkillContext(
            agent_id="agent-123",
            agent_role="analyst",
            skill_id="tool_skill",
            input_data={},
            tool_registry=mock_tool_registry
        )

        result = await executor.execute("tool_skill", context)

        assert result.success is True
        assert result.result["has_tool"] is True
        assert result.result["tool_name"] == "Test Tool"


class TestSkillComposition:
    """Test skills calling other skills."""

    @pytest.mark.asyncio
    async def test_skill_calls_another_skill(self, registry, executor):
        """Test that one skill can call another."""
        # First skill - does basic work
        async def base_skill_handler(context: SkillContext):
            value = context.input_data.get("value", 0)
            return {"result": value * 2}

        # Second skill - calls first skill
        async def composite_skill_handler(context: SkillContext):
            # Call base skill
            base_result = await context.call_skill(
                "base_skill",
                {"value": 5}
            )

            # Do additional work
            return {
                "base_result": base_result.result,
                "final_result": base_result.result["result"] + 10
            }

        base_skill = Skill(
            id="base_skill",
            name="Base",
            description="Base skill",
            category=SkillCategory.TOOLS,
            handler=base_skill_handler
        )

        composite_skill = Skill(
            id="composite_skill",
            name="Composite",
            description="Composite skill",
            category=SkillCategory.TOOLS,
            handler=composite_skill_handler
        )

        registry.register_skill(base_skill)
        registry.register_skill(composite_skill)

        context = SkillContext(
            agent_id="agent-123",
            agent_role="analyst",
            skill_id="composite_skill",
            input_data={}
        )

        result = await executor.execute("composite_skill", context)

        assert result.success is True
        assert result.result["base_result"]["result"] == 10  # 5 * 2
        assert result.result["final_result"] == 20  # 10 + 10


class TestErrorPropagation:
    """Test error propagation in skill execution."""

    @pytest.mark.asyncio
    async def test_skill_error_captured(self, registry, executor):
        """Test that skill errors are properly captured."""
        async def failing_skill_handler(context: SkillContext):
            context.record_step("starting", "Starting work")
            raise ValueError("Something went wrong")

        skill = Skill(
            id="failing_skill",
            name="Failing",
            description="Fails",
            category=SkillCategory.TOOLS,
            handler=failing_skill_handler
        )
        registry.register_skill(skill)

        context = SkillContext(
            agent_id="agent-123",
            agent_role="analyst",
            skill_id="failing_skill",
            input_data={}
        )

        result = await executor.execute("failing_skill", context)

        assert result.success is False
        assert "Something went wrong" in result.error
        # Steps before error should be preserved
        assert len(result.steps) == 1
        assert result.steps[0]["step_type"] == "starting"
