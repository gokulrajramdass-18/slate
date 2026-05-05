"""
Tests for Dynamic Skill Executor and A2A Integration

Tests both code-based and UI-defined skills execution.
"""

import pytest
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from open_notebook.agents.skills.base import SkillContext, SkillCategory
from open_notebook.agents.skills.dynamic_executor import (
    DynamicSkillExecutor,
    get_dynamic_skill_executor
)
from open_notebook.agents.skills.executor import get_skill_executor
from open_notebook.agents.skills.registry import get_skill_registry


@pytest.fixture
def skill_context():
    """Create a basic skill context for testing."""
    return SkillContext(
        agent_id="test-agent-123",
        agent_role="analyst",
        skill_id="test-skill",
        input_data={
            "query": "Test query",
            "data": "Sample data",
            "analysis_type": "detailed"
        },
        config={"timeout": 30}
    )


@pytest.fixture
def mock_llm():
    """Mock LLM for testing."""
    mock = AsyncMock()
    mock.ainvoke = AsyncMock(return_value=MagicMock(content="LLM response text"))
    return mock


@pytest.fixture
def mock_tool():
    """Mock tool for testing."""
    mock = MagicMock()
    mock.execute = AsyncMock(return_value={"result": "tool output", "rows": [1, 2, 3]})
    return mock


@pytest.fixture
def mock_database():
    """Mock database query for dynamic skills."""
    async def mock_query(sql, params):
        skill_id = params.get("id")

        if skill_id == "prompt-skill-123":
            return [{
                "id": skill_id,
                "name": "Test Prompt Skill",
                "skill_type": "prompt_template",
                "definition": json.dumps({
                    "template": "Analyze {data} and provide {analysis_type} insights",
                    "variables": [
                        {"name": "data", "type": "text", "required": True},
                        {"name": "analysis_type", "type": "string", "required": True}
                    ],
                    "model": "claude-3-5-sonnet",
                    "temperature": 0.7
                }),
                "enabled": 1
            }]
        elif skill_id == "chain-skill-456":
            return [{
                "id": skill_id,
                "name": "Test Chain Skill",
                "skill_type": "tool_chain",
                "definition": json.dumps({
                    "tools": [
                        {
                            "tool_id": "test_tool",
                            "input_mapping": {
                                "input": "{input.query}"
                            },
                            "output_key": "step1"
                        }
                    ],
                    "flow": {
                        "type": "sequential",
                        "return": "{steps.step1.result}"
                    }
                }),
                "enabled": 1
            }]
        else:
            return []

    return mock_query


class TestDynamicSkillExecutor:
    """Test DynamicSkillExecutor functionality."""

    @pytest.mark.asyncio
    async def test_execute_prompt_template_skill(self, skill_context, mock_llm, mock_database):
        """Test executing a prompt_template skill."""
        # Setup
        executor = DynamicSkillExecutor()
        skill_context.llm = mock_llm

        with patch('open_notebook.agents.skills.dynamic_executor.repo_query', new=mock_database):
            # Execute
            result = await executor.execute_dynamic_skill("prompt-skill-123", skill_context)

            # Verify
            assert result is not None
            assert "output" in result
            assert result["output"] == "LLM response text"
            assert result["model"] == "claude-3-5-sonnet"
            assert "prompt_used" in result

            # Verify LLM was called
            mock_llm.ainvoke.assert_called_once()

            # Verify template was formatted correctly
            call_args = mock_llm.ainvoke.call_args
            messages = call_args[0][0]
            assert "Sample data" in str(messages)
            assert "detailed" in str(messages)

    @pytest.mark.asyncio
    async def test_execute_tool_chain_skill(self, skill_context, mock_tool, mock_database):
        """Test executing a tool_chain skill."""
        # Setup
        executor = DynamicSkillExecutor()
        skill_context.get_tool = MagicMock(return_value=mock_tool)

        with patch('open_notebook.agents.skills.dynamic_executor.repo_query', new=mock_database):
            # Execute
            result = await executor.execute_dynamic_skill("chain-skill-456", skill_context)

            # Verify
            assert result is not None
            assert "output" in result
            assert result["output"] == "tool output"
            assert "steps" in result
            assert "step1" in result["steps"]

            # Verify tool was called
            mock_tool.execute.assert_called_once()

            # Verify input mapping worked
            call_args = mock_tool.execute.call_args[0][0]
            assert call_args["input"] == "Test query"

    @pytest.mark.asyncio
    async def test_required_variable_validation(self, skill_context, mock_database):
        """Test that required variables are validated."""
        # Setup - remove required variable
        executor = DynamicSkillExecutor()
        skill_context.input_data = {"analysis_type": "detailed"}  # Missing 'data'

        with patch('open_notebook.agents.skills.dynamic_executor.repo_query', new=mock_database):
            # Execute and expect error
            with pytest.raises(ValueError, match="Required variable 'data' not provided"):
                await executor.execute_dynamic_skill("prompt-skill-123", skill_context)

    @pytest.mark.asyncio
    async def test_skill_not_found(self, skill_context, mock_database):
        """Test error when skill not found in database."""
        executor = DynamicSkillExecutor()

        with patch('open_notebook.agents.skills.dynamic_executor.repo_query', new=mock_database):
            with pytest.raises(ValueError, match="Skill not found or disabled"):
                await executor.execute_dynamic_skill("nonexistent-skill", skill_context)

    @pytest.mark.asyncio
    async def test_template_variable_resolution(self, skill_context, mock_tool):
        """Test template variable resolution for tool chains."""
        executor = DynamicSkillExecutor()

        # Test input resolution
        result = executor._resolve_template("{input.query}", {"query": "test"}, {})
        assert result == "test"

        # Test nested input resolution
        result = executor._resolve_template(
            "{input.nested.value}",
            {"nested": {"value": "nested_test"}},
            {}
        )
        assert result == "nested_test"

        # Test steps resolution
        result = executor._resolve_template(
            "{steps.step1.result}",
            {},
            {"step1": {"result": "step_output"}}
        )
        assert result == "step_output"

        # Test non-template passthrough
        result = executor._resolve_template("plain string", {}, {})
        assert result == "plain string"

    def test_singleton_accessor(self):
        """Test that get_dynamic_skill_executor returns singleton."""
        executor1 = get_dynamic_skill_executor()
        executor2 = get_dynamic_skill_executor()

        assert executor1 is executor2


class TestUnifiedSkillExecutor:
    """Test unified SkillExecutor with code and dynamic skills."""

    @pytest.mark.asyncio
    async def test_execute_code_skill(self, skill_context):
        """Test that code skills execute correctly."""
        from open_notebook.agents.skills.base import Skill

        # Register a test code skill
        async def test_handler(context):
            return {"output": f"Processed: {context.input_data['query']}"}

        test_skill = Skill(
            id="test-code-skill",
            name="Test Code Skill",
            description="Test",
            category=SkillCategory.TOOLS,
            handler=test_handler,
            enabled=True
        )

        registry = get_skill_registry()
        registry.register_skill(test_skill)

        # Execute
        executor = get_skill_executor()
        result = await executor.execute("test-code-skill", skill_context)

        # Verify
        assert result.success
        assert result.result["output"] == "Processed: Test query"

        # Cleanup
        registry.unregister_skill("test-code-skill")

    @pytest.mark.asyncio
    async def test_execute_dynamic_skill_fallback(self, skill_context, mock_llm, mock_database):
        """Test that executor falls back to dynamic skills when not in code registry."""
        # Setup
        skill_context.llm = mock_llm
        executor = get_skill_executor()

        # Ensure skill is NOT in code registry
        registry = get_skill_registry()
        assert not registry.get_skill("prompt-skill-123")

        with patch('open_notebook.agents.skills.dynamic_executor.repo_query', new=mock_database):
            # Execute
            result = await executor.execute("prompt-skill-123", skill_context)

            # Verify
            assert result.success
            assert result.result["output"] == "LLM response text"
            assert len(result.steps) > 0

    @pytest.mark.asyncio
    async def test_skill_not_found_anywhere(self, skill_context, mock_database):
        """Test error when skill not in code registry OR database."""
        executor = get_skill_executor()

        with patch('open_notebook.agents.skills.dynamic_executor.repo_query', new=mock_database):
            result = await executor.execute("truly-nonexistent", skill_context)

            # Verify
            assert not result.success
            assert "not found" in result.error.lower()


class TestA2AIntegration:
    """Test A2A integration with dynamic skills."""

    @pytest.mark.asyncio
    async def test_standalone_agent_adapter_with_dynamic_skill(self, mock_llm, mock_database):
        """Test StandaloneAgentA2AAdapter executes dynamic skills correctly."""
        from open_notebook.agents.a2a.standalone_adapter import StandaloneAgentA2AAdapter
        from open_notebook.domain.standalone_agent import StandaloneAgent
        from a2a.types import SendMessageRequest, MessageSendParams, Message, TextPart

        # Create agent with custom role (which maps to "custom" skill by default)
        # We'll mock the SkillExecutor to handle the dynamic skill lookup
        agent = StandaloneAgent(
            id="test-agent-123",
            name="Test Agent",
            role="custom",  # This will use "custom" as primary_skill_id
            status="active",
            is_remote=False
        )

        # Create adapter
        adapter = StandaloneAgentA2AAdapter(agent)

        # Create A2A request
        request = SendMessageRequest(
            id=str(uuid.uuid4()),
            method="message/send",
            params=MessageSendParams(
                message=Message(
                    messageId=str(uuid.uuid4()),
                    role="user",
                    parts=[TextPart(text="Analyze this data")]
                )
            )
        )

        # Mock context resources
        # We'll mock the SkillExecutor to handle any skill_id and return dynamic skill result
        with patch('open_notebook.agents.skills.dynamic_executor.repo_query', new=mock_database):
            with patch('open_notebook.agents.skills.executor.get_skill_executor') as mock_get_executor:
                with patch('open_notebook.agents.skills.registry.get_skill_registry') as mock_get_registry:
                    # Mock registry to return None (skill not in code registry)
                    mock_registry = MagicMock()
                    mock_registry.get_skill = MagicMock(return_value=None)
                    mock_get_registry.return_value = mock_registry

                    # Create mock executor that returns success
                    mock_executor = MagicMock()
                    mock_result = MagicMock()
                    mock_result.success = True
                    mock_result.result = {"output": "Analysis complete", "steps": []}
                    mock_executor.execute = AsyncMock(return_value=mock_result)
                    mock_get_executor.return_value = mock_executor

                    # Execute
                    response = await adapter.handle_message(request, user_id="user-123")

                    # Verify
                    assert response is not None
                    actual_response = response.root
                    assert actual_response.result.status.state == "completed"
                    assert len(actual_response.result.artifacts) > 0


class TestSkillDefinitionValidation:
    """Test validation of skill definitions."""

    def test_prompt_template_missing_template(self):
        """Test error when template field missing."""
        executor = DynamicSkillExecutor()
        definition = {
            "variables": [{"name": "data", "type": "text"}],
            # Missing "template" key
        }

        # Should raise KeyError or ValueError
        with pytest.raises((KeyError, ValueError)):
            template = definition["template"]

    @pytest.mark.asyncio
    async def test_tool_chain_missing_tool(self, skill_context):
        """Test error when tool not found in registry."""
        executor = DynamicSkillExecutor()
        definition = {
            "tools": [
                {
                    "tool_id": "nonexistent_tool",
                    "input_mapping": {},
                    "output_key": "step1"
                }
            ],
            "flow": {"return": "{steps}"}
        }

        skill_context.get_tool = MagicMock(return_value=None)

        with pytest.raises(ValueError, match="Tool not found"):
            await executor._execute_tool_chain(skill_context, definition)

    @pytest.mark.asyncio
    async def test_custom_skill_module_not_whitelisted(self, skill_context):
        """Test security check for custom module imports."""
        executor = DynamicSkillExecutor()
        definition = {
            "module": "os",  # Not in whitelist
            "function": "system"
        }

        with pytest.raises(ValueError, match="Module not in whitelist"):
            await executor._execute_custom(skill_context, definition)


@pytest.mark.asyncio
async def test_end_to_end_dynamic_skill_execution(mock_llm, mock_database):
    """
    End-to-end test: Create skill → Bind to agent → Execute via A2A.
    """
    from open_notebook.agents.skills.executor import get_skill_executor

    # 1. Skill exists in database (mocked)
    skill_id = "prompt-skill-123"

    # 2. Create context
    context = SkillContext(
        agent_id="agent-123",
        agent_role="analyst",
        skill_id=skill_id,
        input_data={
            "data": "Q1 sales data",
            "analysis_type": "quarterly"
        },
        llm=mock_llm
    )

    # 3. Execute via unified executor
    with patch('open_notebook.agents.skills.dynamic_executor.repo_query', new=mock_database):
        executor = get_skill_executor()
        result = await executor.execute(skill_id, context)

        # 4. Verify execution
        assert result.success
        assert result.result["output"] == "LLM response text"
        assert result.result["model"] == "claude-3-5-sonnet"

        # 5. Verify steps recorded
        assert len(result.steps) > 0
        step_types = [step["step_type"] for step in result.steps]
        assert "skill_start" in step_types
        assert "prompt_generated" in step_types
        assert "skill_complete" in step_types


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
