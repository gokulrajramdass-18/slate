"""
Unit tests for SkillExecutor

Tests skill execution, error handling, permissions, timing, and observability.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from open_notebook.agents.skills.base import (
    Skill,
    SkillCategory,
    SkillContext,
    SkillExecutionResult
)
from open_notebook.agents.skills.registry import get_skill_registry
from open_notebook.agents.skills.executor import SkillExecutor, get_skill_executor


# Test handlers
async def successful_handler(context: SkillContext):
    """Handler that succeeds."""
    context.record_step("working", "Doing work", status="running")
    context.record_step("done", "Work complete", status="completed")
    return {"result": "success", "data": 42}


async def failing_handler(context: SkillContext):
    """Handler that raises an exception."""
    raise ValueError("Something went wrong")


async def timeout_handler(context: SkillContext):
    """Handler that times out."""
    await asyncio.sleep(10)  # Sleep longer than timeout
    return {"result": "too late"}


async def step_recording_handler(context: SkillContext):
    """Handler that records multiple steps."""
    context.record_step("step1", "First step", status="completed")
    context.record_step("step2", "Second step", status="completed")
    context.record_step("step3", "Third step", status="completed")
    return {"steps_recorded": 3}


@pytest.fixture
def executor():
    """Get executor instance."""
    return get_skill_executor()


@pytest.fixture
def registry():
    """Get registry instance and clear it."""
    reg = get_skill_registry()
    reg.clear()
    return reg


@pytest.fixture
def sample_context():
    """Create a sample skill context."""
    return SkillContext(
        agent_id="agent-123",
        agent_role="analyst",
        skill_id="test_skill",
        input_data={"query": "test"},
        config={"param": "value"}
    )


class TestExecutorBasics:
    """Test basic executor operations."""

    def test_singleton_pattern(self):
        """Test that SkillExecutor is a singleton."""
        exec1 = SkillExecutor()
        exec2 = SkillExecutor()
        assert exec1 is exec2

    def test_get_skill_executor_returns_singleton(self):
        """Test get_skill_executor returns the singleton instance."""
        exec1 = get_skill_executor()
        exec2 = get_skill_executor()
        assert exec1 is exec2


class TestSuccessfulExecution:
    """Test successful skill execution."""

    @pytest.mark.asyncio
    async def test_execute_skill(self, executor, registry, sample_context):
        """Test executing a skill successfully."""
        skill = Skill(
            id="test_skill",
            name="Test Skill",
            description="Test",
            category=SkillCategory.ANALYSIS,
            handler=successful_handler,
            timeout_seconds=5
        )
        registry.register_skill(skill)

        result = await executor.execute("test_skill", sample_context)

        assert result.success is True
        assert result.skill_id == "test_skill"
        assert result.execution_id == sample_context.execution_id
        assert result.error is None
        assert result.result == {"result": "success", "data": 42}
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_execute_records_steps(self, executor, registry, sample_context):
        """Test that execution records steps from handler."""
        skill = Skill(
            id="test_skill",
            name="Test Skill",
            description="Test",
            category=SkillCategory.ANALYSIS,
            handler=successful_handler
        )
        registry.register_skill(skill)

        result = await executor.execute("test_skill", sample_context)

        assert result.success is True
        assert len(result.steps) == 2
        assert result.steps[0]["step_type"] == "working"
        assert result.steps[1]["step_type"] == "done"

    @pytest.mark.asyncio
    async def test_execute_measures_duration(self, executor, registry, sample_context):
        """Test that execution duration is measured."""
        async def slow_handler(context: SkillContext):
            await asyncio.sleep(0.1)  # 100ms
            return {"result": "done"}

        skill = Skill(
            id="test_skill",
            name="Test Skill",
            description="Test",
            category=SkillCategory.ANALYSIS,
            handler=slow_handler
        )
        registry.register_skill(skill)

        result = await executor.execute("test_skill", sample_context)

        assert result.success is True
        # Should take at least 100ms
        assert result.duration_ms >= 100


class TestErrorHandling:
    """Test error handling during execution."""

    @pytest.mark.asyncio
    async def test_skill_not_found(self, executor, sample_context):
        """Test executing a skill that doesn't exist."""
        result = await executor.execute("nonexistent", sample_context)

        assert result.success is False
        assert result.error == "Skill not found: nonexistent"
        assert result.result is None

    @pytest.mark.asyncio
    async def test_disabled_skill(self, executor, registry, sample_context):
        """Test executing a disabled skill."""
        skill = Skill(
            id="test_skill",
            name="Test Skill",
            description="Test",
            category=SkillCategory.ANALYSIS,
            handler=successful_handler,
            enabled=False  # Disabled
        )
        registry.register_skill(skill)

        result = await executor.execute("test_skill", sample_context)

        assert result.success is False
        assert "disabled" in result.error.lower()
        assert result.result is None

    @pytest.mark.asyncio
    async def test_handler_exception(self, executor, registry, sample_context):
        """Test handling exceptions from skill handler."""
        skill = Skill(
            id="test_skill",
            name="Test Skill",
            description="Test",
            category=SkillCategory.ANALYSIS,
            handler=failing_handler
        )
        registry.register_skill(skill)

        result = await executor.execute("test_skill", sample_context)

        assert result.success is False
        assert "Something went wrong" in result.error
        assert result.result is None
        assert result.duration_ms > 0  # Still measures time

    @pytest.mark.asyncio
    async def test_timeout_handling(self, executor, registry, sample_context):
        """Test handling skill timeout."""
        skill = Skill(
            id="test_skill",
            name="Test Skill",
            description="Test",
            category=SkillCategory.ANALYSIS,
            handler=timeout_handler,
            timeout_seconds=1  # 1 second timeout
        )
        registry.register_skill(skill)

        result = await executor.execute("test_skill", sample_context)

        assert result.success is False
        assert "timed out" in result.error.lower()
        assert result.result is None

    @pytest.mark.asyncio
    async def test_no_timeout_when_zero(self, executor, registry, sample_context):
        """Test that timeout_seconds=0 means no timeout."""
        async def quick_handler(context: SkillContext):
            return {"result": "done"}

        skill = Skill(
            id="test_skill",
            name="Test Skill",
            description="Test",
            category=SkillCategory.ANALYSIS,
            handler=quick_handler,
            timeout_seconds=0  # No timeout
        )
        registry.register_skill(skill)

        result = await executor.execute("test_skill", sample_context)

        assert result.success is True
        assert result.result == {"result": "done"}


class TestPermissions:
    """Test role-based access control."""

    @pytest.mark.asyncio
    async def test_role_allowed(self, executor, registry):
        """Test that allowed role can execute skill."""
        skill = Skill(
            id="test_skill",
            name="Test Skill",
            description="Test",
            category=SkillCategory.ANALYSIS,
            handler=successful_handler,
            allowed_roles={"analyst", "data_scientist"}
        )
        registry.register_skill(skill)

        context = SkillContext(
            agent_id="agent-123",
            agent_role="analyst",  # Allowed role
            skill_id="test_skill",
            input_data={}
        )

        result = await executor.execute("test_skill", context)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_role_not_allowed(self, executor, registry):
        """Test that disallowed role cannot execute skill."""
        skill = Skill(
            id="test_skill",
            name="Test Skill",
            description="Test",
            category=SkillCategory.ANALYSIS,
            handler=successful_handler,
            allowed_roles={"analyst", "data_scientist"}
        )
        registry.register_skill(skill)

        context = SkillContext(
            agent_id="agent-123",
            agent_role="researcher",  # Not allowed
            skill_id="test_skill",
            input_data={}
        )

        result = await executor.execute("test_skill", context)

        assert result.success is False
        assert "not allowed" in result.error.lower()
        assert "researcher" in result.error

    @pytest.mark.asyncio
    async def test_empty_allowed_roles_allows_all(self, executor, registry):
        """Test that empty allowed_roles allows any role."""
        skill = Skill(
            id="test_skill",
            name="Test Skill",
            description="Test",
            category=SkillCategory.ANALYSIS,
            handler=successful_handler,
            allowed_roles=set()  # Empty = all roles allowed
        )
        registry.register_skill(skill)

        context = SkillContext(
            agent_id="agent-123",
            agent_role="any_role",  # Any role should work
            skill_id="test_skill",
            input_data={}
        )

        result = await executor.execute("test_skill", context)

        assert result.success is True


class TestObservability:
    """Test observability features."""

    @pytest.mark.asyncio
    async def test_step_recording(self, executor, registry, sample_context):
        """Test that steps are recorded during execution."""
        skill = Skill(
            id="test_skill",
            name="Test Skill",
            description="Test",
            category=SkillCategory.ANALYSIS,
            handler=step_recording_handler
        )
        registry.register_skill(skill)

        result = await executor.execute("test_skill", sample_context)

        assert result.success is True
        assert len(result.steps) == 3
        assert result.steps[0]["step_type"] == "step1"
        assert result.steps[1]["step_type"] == "step2"
        assert result.steps[2]["step_type"] == "step3"

    @pytest.mark.asyncio
    async def test_steps_preserved_on_error(self, executor, registry, sample_context):
        """Test that steps are preserved even when handler fails."""
        async def partial_handler(context: SkillContext):
            context.record_step("step1", "Started", status="completed")
            context.record_step("step2", "Working", status="running")
            raise ValueError("Failed at step 2")

        skill = Skill(
            id="test_skill",
            name="Test Skill",
            description="Test",
            category=SkillCategory.ANALYSIS,
            handler=partial_handler
        )
        registry.register_skill(skill)

        result = await executor.execute("test_skill", sample_context)

        assert result.success is False
        assert len(result.steps) == 2  # Steps recorded before failure
        assert result.steps[0]["step_type"] == "step1"
        assert result.steps[1]["step_type"] == "step2"

    @pytest.mark.asyncio
    async def test_execution_id_propagated(self, executor, registry, sample_context):
        """Test that execution_id is propagated to result."""
        skill = Skill(
            id="test_skill",
            name="Test Skill",
            description="Test",
            category=SkillCategory.ANALYSIS,
            handler=successful_handler
        )
        registry.register_skill(skill)

        result = await executor.execute("test_skill", sample_context)

        assert result.execution_id == sample_context.execution_id


class TestContextInjection:
    """Test that context is properly injected into handlers."""

    @pytest.mark.asyncio
    async def test_input_data_accessible(self, executor, registry):
        """Test that input_data is accessible in handler."""
        async def data_handler(context: SkillContext):
            return {
                "query": context.input_data.get("query"),
                "count": context.input_data.get("count", 0)
            }

        skill = Skill(
            id="test_skill",
            name="Test Skill",
            description="Test",
            category=SkillCategory.ANALYSIS,
            handler=data_handler
        )
        registry.register_skill(skill)

        context = SkillContext(
            agent_id="agent-123",
            agent_role="analyst",
            skill_id="test_skill",
            input_data={"query": "test query", "count": 5}
        )

        result = await executor.execute("test_skill", context)

        assert result.success is True
        assert result.result["query"] == "test query"
        assert result.result["count"] == 5

    @pytest.mark.asyncio
    async def test_config_accessible(self, executor, registry):
        """Test that config is accessible in handler."""
        async def config_handler(context: SkillContext):
            return {
                "strategy": context.config.get("strategy"),
                "limit": context.config.get("limit", 10)
            }

        skill = Skill(
            id="test_skill",
            name="Test Skill",
            description="Test",
            category=SkillCategory.ANALYSIS,
            handler=config_handler
        )
        registry.register_skill(skill)

        context = SkillContext(
            agent_id="agent-123",
            agent_role="analyst",
            skill_id="test_skill",
            input_data={},
            config={"strategy": "hybrid", "limit": 20}
        )

        result = await executor.execute("test_skill", context)

        assert result.success is True
        assert result.result["strategy"] == "hybrid"
        assert result.result["limit"] == 20

    @pytest.mark.asyncio
    async def test_resources_accessible(self, executor, registry):
        """Test that injected resources are accessible in handler."""
        async def resource_handler(context: SkillContext):
            return {
                "has_llm": context.llm is not None,
                "has_database": context.database is not None,
                "agent_id": context.agent_id,
                "agent_role": context.agent_role
            }

        skill = Skill(
            id="test_skill",
            name="Test Skill",
            description="Test",
            category=SkillCategory.ANALYSIS,
            handler=resource_handler
        )
        registry.register_skill(skill)

        context = SkillContext(
            agent_id="agent-123",
            agent_role="analyst",
            skill_id="test_skill",
            input_data={},
            llm=AsyncMock(),
            database=AsyncMock()
        )

        result = await executor.execute("test_skill", context)

        assert result.success is True
        assert result.result["has_llm"] is True
        assert result.result["has_database"] is True
        assert result.result["agent_id"] == "agent-123"
        assert result.result["agent_role"] == "analyst"


class TestConcurrency:
    """Test concurrent execution."""

    @pytest.mark.asyncio
    async def test_concurrent_executions(self, executor, registry):
        """Test that multiple skills can execute concurrently."""
        async def concurrent_handler(context: SkillContext):
            await asyncio.sleep(0.1)
            return {"agent": context.agent_id}

        for i in range(3):
            skill = Skill(
                id=f"skill_{i}",
                name=f"Skill {i}",
                description="Test",
                category=SkillCategory.ANALYSIS,
                handler=concurrent_handler
            )
            registry.register_skill(skill)

        contexts = [
            SkillContext(
                agent_id=f"agent-{i}",
                agent_role="analyst",
                skill_id=f"skill_{i}",
                input_data={}
            )
            for i in range(3)
        ]

        # Execute all concurrently
        results = await asyncio.gather(*[
            executor.execute(f"skill_{i}", contexts[i])
            for i in range(3)
        ])

        # All should succeed
        assert all(r.success for r in results)
        assert results[0].result["agent"] == "agent-0"
        assert results[1].result["agent"] == "agent-1"
        assert results[2].result["agent"] == "agent-2"
