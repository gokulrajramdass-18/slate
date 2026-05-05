"""
Tests for WorkflowOrchestrator and SynthesizerAgent.

Covers:
- Single agent execution
- Team mode with parallel agents
- Planned mode with dependency resolution
- Streaming event format
- Error handling and fallback
- SynthesizerAgent result merging
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, List, Any

from open_notebook.agents.orchestrator import (
    WorkflowOrchestrator,
    OrchestrationMode,
    WorkflowPhase,
    AgentRole,
    AGENT_SYSTEM_PROMPTS,
)
from open_notebook.agents.synthesizer_agent import SynthesizerAgent


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_tool():
    """Create a minimal mock LangChain tool."""
    tool = MagicMock()
    tool.name = "test_query_hana"
    tool.description = "Query a HANA table"
    return tool


@pytest.fixture
def orchestrator(mock_tool):
    """Create an orchestrator with mocked internals."""
    return WorkflowOrchestrator(
        model_name="gpt-4",
        notebook_id="test-notebook-123",
        tools=[mock_tool],
        session_id="test-session-456",
        system_message="You are a helpful assistant.",
    )


# ============================================================================
# StreamEvent helpers
# ============================================================================

def collect_events_sync(events: list) -> Dict[str, list]:
    """Group collected events by event type."""
    grouped: Dict[str, list] = {}
    for e in events:
        etype = e.get("event", "unknown")
        grouped.setdefault(etype, []).append(json.loads(e.get("data", "{}")))
    return grouped


# ============================================================================
# WorkflowOrchestrator Tests
# ============================================================================

class TestWorkflowOrchestratorInit:
    """Tests for orchestrator initialization."""

    def test_init_stores_params(self, mock_tool):
        o = WorkflowOrchestrator(
            model_name="claude-3-5-sonnet-20241022",
            notebook_id="nb1",
            tools=[mock_tool],
            session_id="sess1",
            system_message="context",
        )
        assert o.model_name == "claude-3-5-sonnet-20241022"
        assert o.notebook_id == "nb1"
        assert len(o.tools) == 1
        assert o.session_id == "sess1"
        assert o.system_message == "context"
        assert o.agent_steps == []
        assert o.tool_results == []
        assert o.final_content == ""

    def test_init_optional_params(self, mock_tool):
        o = WorkflowOrchestrator(
            model_name="gpt-4",
            notebook_id="nb2",
            tools=[mock_tool],
        )
        assert o.session_id is None
        assert o.system_message is None


class TestStreamEvent:
    """Tests for the _event helper."""

    def test_event_format(self):
        e = WorkflowOrchestrator._event("test_type", {"key": "value"})
        assert e["event"] == "test_type"
        data = json.loads(e["data"])
        assert data["key"] == "value"

    def test_event_serializes_nested(self):
        e = WorkflowOrchestrator._event("complex", {
            "list": [1, 2, 3],
            "nested": {"a": True},
        })
        data = json.loads(e["data"])
        assert data["list"] == [1, 2, 3]
        assert data["nested"]["a"] is True


class TestSingleMode:
    """Tests for single agent execution."""

    @pytest.mark.asyncio
    async def test_single_mode_emits_workflow_events(self, orchestrator):
        """Single mode should emit workflow_started, agent_spawned, workflow_complete."""
        # Mock the DataQueryAgent.stream_response to yield a simple response
        mock_message = MagicMock()
        mock_message.content = "test response"
        mock_message.tool_calls = []

        fake_events = [
            {"agent": {"messages": [mock_message]}},
        ]

        with patch(
            "open_notebook.agents.orchestrator.DataQueryAgent"
        ) as MockAgent:
            instance = MockAgent.return_value
            instance.agent_steps = []
            instance.get_captured_tool_results.return_value = []

            async def fake_stream(*args, **kwargs):
                for e in fake_events:
                    yield e

            instance.stream_response = fake_stream

            events = []
            async for event in orchestrator.run("test query", mode=OrchestrationMode.SINGLE):
                events.append(event)

        grouped = collect_events_sync(events)

        assert "workflow_started" in grouped
        assert grouped["workflow_started"][0]["mode"] == "single"
        assert "agent_spawned" in grouped
        assert "workflow_complete" in grouped

    @pytest.mark.asyncio
    async def test_single_mode_streams_chunks(self, orchestrator):
        """Single mode should forward text chunks from the agent."""
        mock_msg1 = MagicMock()
        mock_msg1.content = "Hello "
        mock_msg1.tool_calls = []

        mock_msg2 = MagicMock()
        mock_msg2.content = "World"
        mock_msg2.tool_calls = []

        fake_events = [
            {"agent": {"messages": [mock_msg1]}},
            {"agent": {"messages": [mock_msg2]}},
        ]

        with patch(
            "open_notebook.agents.orchestrator.DataQueryAgent"
        ) as MockAgent:
            instance = MockAgent.return_value
            instance.agent_steps = []
            instance.get_captured_tool_results.return_value = []

            async def fake_stream(*args, **kwargs):
                for e in fake_events:
                    yield e

            instance.stream_response = fake_stream

            events = []
            async for event in orchestrator.run("test", mode=OrchestrationMode.SINGLE):
                events.append(event)

        grouped = collect_events_sync(events)
        chunks = grouped.get("chunk", [])
        combined = "".join(c["content"] for c in chunks)
        assert combined == "Hello World"
        assert orchestrator.final_content == "Hello World"

    @pytest.mark.asyncio
    async def test_single_mode_tool_call_events(self, orchestrator):
        """Single mode should emit agent_step for tool calls."""
        mock_msg_tool = MagicMock()
        mock_msg_tool.content = ""
        mock_msg_tool.tool_calls = [{"name": "test_query_hana"}]

        mock_msg_response = MagicMock()
        mock_msg_response.content = "Result: 42 rows"
        mock_msg_response.tool_calls = []

        fake_events = [
            {"agent": {"messages": [mock_msg_tool]}},
            {"tools": {"event": "on_tool_end", "data": {}}},
            {"agent": {"messages": [mock_msg_response]}},
        ]

        with patch(
            "open_notebook.agents.orchestrator.DataQueryAgent"
        ) as MockAgent:
            instance = MockAgent.return_value
            instance.agent_steps = []
            instance.get_captured_tool_results.return_value = []

            async def fake_stream(*args, **kwargs):
                for e in fake_events:
                    yield e

            instance.stream_response = fake_stream

            events = []
            async for event in orchestrator.run("test", mode=OrchestrationMode.SINGLE):
                events.append(event)

        grouped = collect_events_sync(events)
        steps = grouped.get("agent_step", [])
        tool_calls = [s for s in steps if s.get("step_type") == "tool_call"]
        tool_results = [s for s in steps if s.get("step_type") == "tool_result"]
        assert len(tool_calls) >= 1
        assert len(tool_results) >= 1


class TestTeamMode:
    """Tests for team mode execution."""

    @pytest.mark.asyncio
    async def test_team_mode_spawns_two_agents(self, orchestrator):
        """Team mode should spawn researcher and analyst."""
        with patch(
            "open_notebook.agents.orchestrator.DataQueryAgent"
        ) as MockAgent:
            instance = MockAgent.return_value
            instance.agent_steps = []
            instance.get_captured_tool_results.return_value = []

            async def fake_stream(*args, **kwargs):
                mock_msg = MagicMock()
                mock_msg.content = "agent response"
                mock_msg.tool_calls = []
                yield {"agent": {"messages": [mock_msg]}}

            instance.stream_response = fake_stream

            with patch(
                "open_notebook.agents.orchestrator.SynthesizerAgent"
            ) as MockSynth:
                synth_instance = MockSynth.return_value
                synth_instance.synthesize = AsyncMock(return_value={
                    "content": "Synthesized result",
                    "tool_results": [],
                    "agent_steps": [],
                    "citations": [],
                })

                events = []
                async for event in orchestrator.run("test", mode=OrchestrationMode.TEAM):
                    events.append(event)

        grouped = collect_events_sync(events)

        assert "team_created" in grouped
        assert set(grouped["team_created"][0]["agents"]) == {"researcher", "analyst"}

        spawned = grouped.get("agent_spawned", [])
        spawned_names = {s["agent_name"] for s in spawned}
        assert "researcher" in spawned_names
        assert "analyst" in spawned_names

    @pytest.mark.asyncio
    async def test_team_mode_synthesizes_results(self, orchestrator):
        """Team mode should call SynthesizerAgent and stream the synthesis."""
        with patch(
            "open_notebook.agents.orchestrator.DataQueryAgent"
        ) as MockAgent:
            instance = MockAgent.return_value
            instance.agent_steps = []
            instance.get_captured_tool_results.return_value = []

            async def fake_stream(*args, **kwargs):
                mock_msg = MagicMock()
                mock_msg.content = "data found"
                mock_msg.tool_calls = []
                yield {"agent": {"messages": [mock_msg]}}

            instance.stream_response = fake_stream

            with patch(
                "open_notebook.agents.orchestrator.SynthesizerAgent"
            ) as MockSynth:
                synth_instance = MockSynth.return_value
                synth_instance.synthesize = AsyncMock(return_value={
                    "content": "Combined analysis",
                    "tool_results": [{"tool_name": "t1"}],
                    "agent_steps": [],
                    "citations": [{"agent_name": "researcher"}],
                })

                events = []
                async for event in orchestrator.run("test", mode=OrchestrationMode.TEAM):
                    events.append(event)

        grouped = collect_events_sync(events)
        chunks = grouped.get("chunk", [])
        combined = "".join(c["content"] for c in chunks)
        assert "Combined analysis" in combined
        assert orchestrator.final_content == "Combined analysis"
        assert len(orchestrator.tool_results) == 1


class TestPlannedMode:
    """Tests for planned mode execution."""

    @pytest.mark.asyncio
    async def test_planned_mode_creates_tasks(self, orchestrator):
        """Planned mode should generate a plan and emit task_created events."""
        mock_plan = [
            {"task": "Gather data", "role": "researcher", "depends_on": []},
            {"task": "Analyze data", "role": "analyst", "depends_on": [0]},
        ]

        with patch.object(orchestrator, "_generate_plan", new=AsyncMock(return_value=[
            {"id": "a1", "task": "Gather data", "role": "researcher", "depends_on": [], "status": "pending", "result": None},
            {"id": "a2", "task": "Analyze data", "role": "analyst", "depends_on": [0], "status": "pending", "result": None},
        ])):
            with patch(
                "open_notebook.agents.orchestrator.DataQueryAgent"
            ) as MockAgent:
                instance = MockAgent.return_value
                instance.agent_steps = []
                instance.get_captured_tool_results.return_value = []
                instance.invoke = AsyncMock(return_value="task result")

                with patch(
                    "open_notebook.agents.orchestrator.SynthesizerAgent"
                ) as MockSynth:
                    synth_instance = MockSynth.return_value
                    synth_instance.synthesize = AsyncMock(return_value={
                        "content": "Final planned result",
                        "tool_results": [],
                        "agent_steps": [],
                        "citations": [],
                    })

                    events = []
                    async for event in orchestrator.run("complex query", mode=OrchestrationMode.PLANNED):
                        events.append(event)

        grouped = collect_events_sync(events)

        assert "task_created" in grouped
        assert len(grouped["task_created"]) == 2

        assert "task_started" in grouped
        assert "task_completed" in grouped

        # Second task depends on first
        task0 = grouped["task_created"][0]
        task1 = grouped["task_created"][1]
        assert task0["depends_on"] == []
        assert task1["depends_on"] == [0]

    @pytest.mark.asyncio
    async def test_planned_mode_fallback_on_plan_failure(self, orchestrator):
        """If planning fails, should fall back to team mode."""
        with patch.object(orchestrator, "_generate_plan", new=AsyncMock(return_value=None)):
            with patch.object(orchestrator, "_run_team") as mock_team:
                team_events = [
                    {"event": "team_created", "data": json.dumps({"agents": ["researcher", "analyst"]})},
                ]

                async def fake_team(*args, **kwargs):
                    for e in team_events:
                        yield e

                mock_team.return_value = fake_team()

                events = []
                async for event in orchestrator.run("complex", mode=OrchestrationMode.PLANNED):
                    events.append(event)

        grouped = collect_events_sync(events)
        # Should have a planning error step
        steps = grouped.get("agent_step", [])
        error_steps = [s for s in steps if "failed" in s.get("content", "").lower() or s.get("status") == "error"]
        assert len(error_steps) >= 1


class TestErrorHandling:
    """Tests for error handling in orchestration."""

    @pytest.mark.asyncio
    async def test_workflow_error_event(self, orchestrator):
        """If execution raises, should emit workflow_error."""
        with patch.object(orchestrator, "_run_single", side_effect=RuntimeError("boom")):
            events = []
            async for event in orchestrator.run("test", mode=OrchestrationMode.SINGLE):
                events.append(event)

        grouped = collect_events_sync(events)
        assert "workflow_error" in grouped
        assert "boom" in grouped["workflow_error"][0]["error"]

    @pytest.mark.asyncio
    async def test_team_mode_handles_agent_failure(self, orchestrator):
        """If one agent fails in team mode, the other should still work."""
        call_count = 0

        with patch(
            "open_notebook.agents.orchestrator.DataQueryAgent"
        ) as MockAgent:
            def create_agent(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                instance = MagicMock()
                instance.agent_steps = []
                instance.get_captured_tool_results.return_value = []

                if call_count == 1:
                    # First agent fails
                    async def fail_stream(*a, **kw):
                        raise RuntimeError("agent 1 failed")
                        yield  # make it a generator # noqa: E501
                    instance.stream_response = fail_stream
                else:
                    # Second agent succeeds
                    async def ok_stream(*a, **kw):
                        msg = MagicMock()
                        msg.content = "success from agent 2"
                        msg.tool_calls = []
                        yield {"agent": {"messages": [msg]}}
                    instance.stream_response = ok_stream

                return instance

            MockAgent.side_effect = create_agent

            with patch(
                "open_notebook.agents.orchestrator.SynthesizerAgent"
            ) as MockSynth:
                synth_instance = MockSynth.return_value
                synth_instance.synthesize = AsyncMock(return_value={
                    "content": "partial result",
                    "tool_results": [],
                    "agent_steps": [],
                    "citations": [],
                })

                events = []
                async for event in orchestrator.run("test", mode=OrchestrationMode.TEAM):
                    events.append(event)

        # Should still complete (not crash)
        grouped = collect_events_sync(events)
        assert "workflow_complete" in grouped


# ============================================================================
# SynthesizerAgent Tests
# ============================================================================

class TestSynthesizerAgent:
    """Tests for the SynthesizerAgent."""

    def test_init(self):
        with patch("open_notebook.agents.synthesizer_agent.ChatOpenAI"):
            s = SynthesizerAgent(model_name="gpt-4")
            assert s.model_name == "gpt-4"
            assert s.model is not None

    def test_init_anthropic(self):
        with patch("open_notebook.agents.synthesizer_agent.ChatAnthropic"):
            s = SynthesizerAgent(model_name="claude-3-5-sonnet-20241022")
            assert s.model is not None

    @pytest.mark.asyncio
    async def test_synthesize_calls_llm(self):
        """Synthesize should invoke the LLM and return structured output."""
        with patch("open_notebook.agents.synthesizer_agent.ChatOpenAI"):
            s = SynthesizerAgent(model_name="gpt-4")

        mock_response = MagicMock()
        mock_response.content = "Synthesized: Agent A found X, Agent B found Y."

        s.model = MagicMock()
        s.model.ainvoke = AsyncMock(return_value=mock_response)

        result = await s.synthesize(
            original_query="What is the data?",
            agent_results=[
                {
                    "agent_name": "researcher",
                    "agent_role": "researcher",
                    "response_text": "Found X in the database",
                    "tool_results": [{"tool_name": "hana_query", "result_type": "table"}],
                    "agent_steps": [{"step_type": "tool_call", "content": "query"}],
                },
                {
                    "agent_name": "analyst",
                    "agent_role": "analyst",
                    "response_text": "The data shows Y trend",
                    "tool_results": [],
                    "agent_steps": [],
                },
            ],
        )

        assert "Synthesized" in result["content"]
        assert len(result["tool_results"]) == 1
        assert result["tool_results"][0]["source_agent"] == "researcher"
        assert len(result["citations"]) == 2

    @pytest.mark.asyncio
    async def test_synthesize_fallback_on_llm_error(self):
        """If the LLM fails, synthesize should return concatenated agent outputs."""
        with patch("open_notebook.agents.synthesizer_agent.ChatOpenAI"):
            s = SynthesizerAgent(model_name="gpt-4")

        s.model = MagicMock()
        s.model.ainvoke = AsyncMock(side_effect=RuntimeError("LLM down"))

        result = await s.synthesize(
            original_query="test",
            agent_results=[
                {
                    "agent_name": "agent_a",
                    "agent_role": "researcher",
                    "response_text": "Result A",
                },
                {
                    "agent_name": "agent_b",
                    "agent_role": "analyst",
                    "response_text": "Result B",
                },
            ],
        )

        assert "Result A" in result["content"]
        assert "Result B" in result["content"]

    @pytest.mark.asyncio
    async def test_synthesize_emits_steps(self):
        """Synthesize should call the step callback."""
        steps_received = []

        def step_cb(step):
            steps_received.append(step)

        with patch("open_notebook.agents.synthesizer_agent.ChatOpenAI"):
            s = SynthesizerAgent(model_name="gpt-4", agent_steps_callback=step_cb)

        mock_response = MagicMock()
        mock_response.content = "Done"

        s.model = MagicMock()
        s.model.ainvoke = AsyncMock(return_value=mock_response)

        await s.synthesize("test", [
            {"agent_name": "a", "agent_role": "r", "response_text": "x"},
        ])

        assert len(steps_received) >= 1
        assert steps_received[0]["step_type"] == "synthesizing"

    @pytest.mark.asyncio
    async def test_synthesize_merges_tool_results_with_source(self):
        """Tool results should be tagged with source_agent."""
        with patch("open_notebook.agents.synthesizer_agent.ChatOpenAI"):
            s = SynthesizerAgent(model_name="gpt-4")

        mock_response = MagicMock()
        mock_response.content = "merged"

        s.model = MagicMock()
        s.model.ainvoke = AsyncMock(return_value=mock_response)

        result = await s.synthesize("q", [
            {
                "agent_name": "a1",
                "agent_role": "researcher",
                "response_text": "r1",
                "tool_results": [
                    {"tool_name": "hana", "result": {"rows": []}},
                    {"tool_name": "api", "result": {"data": []}},
                ],
            },
            {
                "agent_name": "a2",
                "agent_role": "analyst",
                "response_text": "r2",
                "tool_results": [
                    {"tool_name": "analysis", "result": {}},
                ],
            },
        ])

        assert len(result["tool_results"]) == 3
        assert result["tool_results"][0]["source_agent"] == "a1"
        assert result["tool_results"][1]["source_agent"] == "a1"
        assert result["tool_results"][2]["source_agent"] == "a2"


# ============================================================================
# Agent Role Prompts Tests
# ============================================================================

class TestAgentRoles:
    """Verify that all roles have system prompts."""

    def test_all_roles_have_prompts(self):
        for role in AgentRole:
            assert role in AGENT_SYSTEM_PROMPTS
            assert len(AGENT_SYSTEM_PROMPTS[role]) > 20

    def test_researcher_prompt_mentions_tools(self):
        assert "tools" in AGENT_SYSTEM_PROMPTS[AgentRole.RESEARCHER].lower()

    def test_analyst_prompt_mentions_analysis(self):
        prompt = AGENT_SYSTEM_PROMPTS[AgentRole.ANALYST].lower()
        assert "analy" in prompt

    def test_planner_prompt_mentions_json(self):
        assert "JSON" in AGENT_SYSTEM_PROMPTS[AgentRole.PLANNER]


# ============================================================================
# Plan Generation Tests
# ============================================================================

class TestPlanGeneration:
    """Tests for the _generate_plan method."""

    @pytest.mark.asyncio
    async def test_generate_plan_parses_json(self, orchestrator):
        """Plan generation should parse LLM JSON output."""
        mock_response = MagicMock()
        mock_response.content = json.dumps([
            {"task": "Get data", "role": "researcher", "depends_on": []},
            {"task": "Analyze", "role": "analyst", "depends_on": [0]},
        ])

        with patch(
            "open_notebook.agents.orchestrator.ChatOpenAI"
        ) as MockLLM:
            instance = MockLLM.return_value
            instance.ainvoke = AsyncMock(return_value=mock_response)

            plan = await orchestrator._generate_plan("complex query")

        assert plan is not None
        assert len(plan) == 2
        assert plan[0]["role"] == "researcher"
        assert plan[1]["depends_on"] == [0]
        assert plan[0]["status"] == "pending"
        assert "id" in plan[0]

    @pytest.mark.asyncio
    async def test_generate_plan_handles_code_fences(self, orchestrator):
        """Should strip markdown code fences from LLM output."""
        mock_response = MagicMock()
        mock_response.content = '```json\n[{"task": "Do X", "role": "researcher", "depends_on": []}]\n```'

        with patch(
            "open_notebook.agents.orchestrator.ChatOpenAI"
        ) as MockLLM:
            instance = MockLLM.return_value
            instance.ainvoke = AsyncMock(return_value=mock_response)

            plan = await orchestrator._generate_plan("query")

        assert plan is not None
        assert len(plan) == 1

    @pytest.mark.asyncio
    async def test_generate_plan_returns_none_on_invalid_json(self, orchestrator):
        """Should return None if LLM output is not valid JSON."""
        mock_response = MagicMock()
        mock_response.content = "This is not JSON"

        with patch(
            "open_notebook.agents.orchestrator.ChatOpenAI"
        ) as MockLLM:
            instance = MockLLM.return_value
            instance.ainvoke = AsyncMock(return_value=mock_response)

            plan = await orchestrator._generate_plan("query")

        assert plan is None

    @pytest.mark.asyncio
    async def test_generate_plan_returns_none_on_exception(self, orchestrator):
        """Should return None if LLM call raises."""
        with patch(
            "open_notebook.agents.orchestrator.ChatOpenAI"
        ) as MockLLM:
            instance = MockLLM.return_value
            instance.ainvoke = AsyncMock(side_effect=RuntimeError("LLM error"))

            plan = await orchestrator._generate_plan("query")

        assert plan is None
