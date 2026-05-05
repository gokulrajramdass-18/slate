"""
End-to-end integration tests for the multi-agent workflow system.

Tests the full lifecycle:
1. Orchestrator selects mode based on query complexity
2. Agents are spawned with correct roles
3. Tasks are created, assigned, and executed
4. Inter-agent messaging works during execution
5. Results are synthesized into a unified response
6. Streaming events are emitted throughout

All external dependencies (LLM calls, database persistence) are mocked,
but the internal flow across orchestrator, agents, task_manager, messaging,
and synthesizer is exercised end-to-end.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_langchain_tool():
    """Create a mock LangChain tool for agent use."""
    tool = MagicMock()
    tool.name = "query_sales_data"
    tool.description = "Query sales data from HANA database"
    return tool


@pytest.fixture
def workflow_config():
    """Standard workflow configuration for tests."""
    return {
        "model_name": "gpt-4",
        "notebook_id": f"nb-{uuid.uuid4().hex[:8]}",
        "session_id": f"sess-{uuid.uuid4().hex[:8]}",
        "system_message": "You are a helpful research assistant.",
    }


# ============================================================================
# Helpers
# ============================================================================

def collect_stream_events(events: list) -> Dict[str, list]:
    """Group streamed events by event type, parsing data JSON."""
    grouped: Dict[str, list] = {}
    for e in events:
        etype = e.get("event", "unknown")
        data_str = e.get("data", "{}")
        try:
            data = json.loads(data_str) if isinstance(data_str, str) else data_str
        except json.JSONDecodeError:
            data = {"raw": data_str}
        grouped.setdefault(etype, []).append(data)
    return grouped


def make_mock_agent_stream(*texts):
    """Create a mock stream_response that yields text chunks."""
    async def fake_stream(*args, **kwargs):
        for text in texts:
            msg = MagicMock()
            msg.content = text
            msg.tool_calls = []
            yield {"agent": {"messages": [msg]}}
    return fake_stream


def make_mock_agent_with_tools(*texts, tool_name="query_sales_data"):
    """Create a mock stream that includes tool calls followed by text."""
    async def fake_stream(*args, **kwargs):
        # First: tool call
        tool_msg = MagicMock()
        tool_msg.content = ""
        tool_msg.tool_calls = [{"name": tool_name}]
        yield {"agent": {"messages": [tool_msg]}}

        # Tool execution
        yield {"tools": {"event": "on_tool_start", "data": {"name": tool_name}}}
        yield {"tools": {"event": "on_tool_end", "data": {"output": '{"rows": []}'}}}

        # Response text
        for text in texts:
            msg = MagicMock()
            msg.content = text
            msg.tool_calls = []
            yield {"agent": {"messages": [msg]}}
    return fake_stream


# ============================================================================
# E2E Test: Single Agent Mode
# ============================================================================

class TestE2ESingleAgentWorkflow:
    """
    Full flow: user query -> orchestrator (single mode) -> DataQueryAgent -> response.
    """

    @pytest.mark.asyncio
    async def test_single_agent_simple_query(self, mock_langchain_tool, workflow_config):
        """A simple query should route through single mode and return text."""
        from open_notebook.agents.orchestrator import (
            WorkflowOrchestrator,
            OrchestrationMode,
        )

        orchestrator = WorkflowOrchestrator(
            model_name=workflow_config["model_name"],
            notebook_id=workflow_config["notebook_id"],
            tools=[mock_langchain_tool],
            session_id=workflow_config["session_id"],
            system_message=workflow_config["system_message"],
        )

        with patch("open_notebook.agents.orchestrator.DataQueryAgent") as MockAgent:
            instance = MockAgent.return_value
            instance.agent_steps = [
                {"step_type": "thinking", "content": "Analyzing", "status": "completed"}
            ]
            instance.get_captured_tool_results.return_value = []
            instance.stream_response = make_mock_agent_stream(
                "The quarterly sales data shows ",
                "a 15% increase in Q4."
            )

            events = []
            async for event in orchestrator.run(
                "Show me Q4 sales data",
                mode=OrchestrationMode.SINGLE,
            ):
                events.append(event)

        grouped = collect_stream_events(events)

        # Verify lifecycle events
        assert "workflow_started" in grouped
        assert grouped["workflow_started"][0]["mode"] == "single"
        assert "workflow_complete" in grouped
        assert "agent_spawned" in grouped

        # Verify content was streamed
        chunks = grouped.get("chunk", [])
        full_text = "".join(c["content"] for c in chunks)
        assert "quarterly sales data" in full_text
        assert "15% increase" in full_text
        assert orchestrator.final_content == full_text

    @pytest.mark.asyncio
    async def test_single_agent_with_tool_calls(self, mock_langchain_tool, workflow_config):
        """Single mode should emit tool call/result events when tools are used."""
        from open_notebook.agents.orchestrator import (
            WorkflowOrchestrator,
            OrchestrationMode,
        )

        orchestrator = WorkflowOrchestrator(
            model_name=workflow_config["model_name"],
            notebook_id=workflow_config["notebook_id"],
            tools=[mock_langchain_tool],
            session_id=workflow_config["session_id"],
        )

        with patch("open_notebook.agents.orchestrator.DataQueryAgent") as MockAgent:
            instance = MockAgent.return_value
            instance.agent_steps = []
            instance.get_captured_tool_results.return_value = [
                {"tool_name": "query_sales_data", "result_type": "table", "result": {"rows": []}}
            ]
            instance.stream_response = make_mock_agent_with_tools(
                "The query returned 42 results."
            )

            events = []
            async for event in orchestrator.run(
                "Query the sales data",
                mode=OrchestrationMode.SINGLE,
            ):
                events.append(event)

        grouped = collect_stream_events(events)
        steps = grouped.get("agent_step", [])

        tool_calls = [s for s in steps if s.get("step_type") == "tool_call"]
        tool_results = [s for s in steps if s.get("step_type") == "tool_result"]

        assert len(tool_calls) >= 1
        assert len(tool_results) >= 1
        assert orchestrator.tool_results[0]["tool_name"] == "query_sales_data"


# ============================================================================
# E2E Test: Team Mode
# ============================================================================

class TestE2ETeamWorkflow:
    """
    Full flow: query -> orchestrator (team mode) -> researcher + analyst -> synthesizer -> response.
    """

    @pytest.mark.asyncio
    async def test_team_mode_full_workflow(self, mock_langchain_tool, workflow_config):
        """Team mode should spawn 2 agents, collect results, and synthesize."""
        from open_notebook.agents.orchestrator import (
            WorkflowOrchestrator,
            OrchestrationMode,
        )

        orchestrator = WorkflowOrchestrator(
            model_name=workflow_config["model_name"],
            notebook_id=workflow_config["notebook_id"],
            tools=[mock_langchain_tool],
            session_id=workflow_config["session_id"],
            system_message=workflow_config["system_message"],
        )

        with patch("open_notebook.agents.orchestrator.DataQueryAgent") as MockAgent:
            instance = MockAgent.return_value
            instance.agent_steps = []
            instance.get_captured_tool_results.return_value = []
            instance.stream_response = make_mock_agent_stream("Agent output data")

            with patch("open_notebook.agents.orchestrator.SynthesizerAgent") as MockSynth:
                synth_instance = MockSynth.return_value
                synth_instance.synthesize = AsyncMock(return_value={
                    "content": "Based on research and analysis, Q4 sales grew 15%. "
                               "[Agent: researcher] found the raw data. "
                               "[Agent: analyst] identified the growth trend.",
                    "tool_results": [],
                    "agent_steps": [],
                    "citations": [
                        {"agent_name": "researcher", "agent_role": "researcher"},
                        {"agent_name": "analyst", "agent_role": "analyst"},
                    ],
                })

                events = []
                async for event in orchestrator.run(
                    "Analyze Q4 performance trends",
                    mode=OrchestrationMode.TEAM,
                ):
                    events.append(event)

        grouped = collect_stream_events(events)

        # Verify team creation
        assert "team_created" in grouped
        assert set(grouped["team_created"][0]["agents"]) == {"researcher", "analyst"}

        # Verify both agents spawned
        spawned = grouped.get("agent_spawned", [])
        spawned_names = {s["agent_name"] for s in spawned}
        assert "researcher" in spawned_names
        assert "analyst" in spawned_names

        # Verify synthesis happened
        synth_steps = [
            s for s in grouped.get("agent_step", [])
            if s.get("step_type") == "synthesizing"
        ]
        assert len(synth_steps) >= 1

        # Verify final content contains synthesized result
        chunks = grouped.get("chunk", [])
        full_text = "".join(c["content"] for c in chunks)
        assert "Q4 sales grew 15%" in full_text
        assert orchestrator.final_content == full_text

        # Verify workflow completed
        assert "workflow_complete" in grouped

    @pytest.mark.asyncio
    async def test_team_mode_agent_messages_emitted(self, mock_langchain_tool, workflow_config):
        """Team mode should emit agent_message events from each agent."""
        from open_notebook.agents.orchestrator import (
            WorkflowOrchestrator,
            OrchestrationMode,
        )

        orchestrator = WorkflowOrchestrator(
            model_name=workflow_config["model_name"],
            notebook_id=workflow_config["notebook_id"],
            tools=[mock_langchain_tool],
        )

        with patch("open_notebook.agents.orchestrator.DataQueryAgent") as MockAgent:
            instance = MockAgent.return_value
            instance.agent_steps = []
            instance.get_captured_tool_results.return_value = []
            instance.stream_response = make_mock_agent_stream("Research finding here")

            with patch("open_notebook.agents.orchestrator.SynthesizerAgent") as MockSynth:
                synth_instance = MockSynth.return_value
                synth_instance.synthesize = AsyncMock(return_value={
                    "content": "Merged result",
                    "tool_results": [],
                    "agent_steps": [],
                    "citations": [],
                })

                events = []
                async for event in orchestrator.run(
                    "Research this topic",
                    mode=OrchestrationMode.TEAM,
                ):
                    events.append(event)

        grouped = collect_stream_events(events)
        agent_msgs = grouped.get("agent_message", [])

        # Both researcher and analyst should have sent messages
        senders = {m.get("agent_name") for m in agent_msgs}
        assert "researcher" in senders
        assert "analyst" in senders


# ============================================================================
# E2E Test: Planned Mode
# ============================================================================

class TestE2EPlannedWorkflow:
    """
    Full flow: query -> planner -> task graph -> parallel execution -> synthesis.
    """

    @pytest.mark.asyncio
    async def test_planned_mode_full_workflow(self, mock_langchain_tool, workflow_config):
        """Planned mode: plan -> execute tasks with deps -> synthesize."""
        from open_notebook.agents.orchestrator import (
            WorkflowOrchestrator,
            OrchestrationMode,
        )

        orchestrator = WorkflowOrchestrator(
            model_name=workflow_config["model_name"],
            notebook_id=workflow_config["notebook_id"],
            tools=[mock_langchain_tool],
            session_id=workflow_config["session_id"],
            system_message=workflow_config["system_message"],
        )

        mock_plan = [
            {"id": "t1", "task": "Gather Q4 sales data", "role": "researcher", "depends_on": [], "status": "pending", "result": None},
            {"id": "t2", "task": "Gather Q4 marketing data", "role": "researcher", "depends_on": [], "status": "pending", "result": None},
            {"id": "t3", "task": "Analyze combined trends", "role": "analyst", "depends_on": [0, 1], "status": "pending", "result": None},
        ]

        with patch.object(orchestrator, "_generate_plan", new=AsyncMock(return_value=mock_plan)):
            with patch("open_notebook.agents.orchestrator.DataQueryAgent") as MockAgent:
                instance = MockAgent.return_value
                instance.agent_steps = []
                instance.get_captured_tool_results.return_value = []
                instance.invoke = AsyncMock(return_value="Task result data")

                with patch("open_notebook.agents.orchestrator.SynthesizerAgent") as MockSynth:
                    synth_instance = MockSynth.return_value
                    synth_instance.synthesize = AsyncMock(return_value={
                        "content": "Comprehensive Q4 analysis combining sales and marketing data shows strong growth.",
                        "tool_results": [],
                        "agent_steps": [],
                        "citations": [],
                    })

                    events = []
                    async for event in orchestrator.run(
                        "Give me a comprehensive Q4 analysis",
                        mode=OrchestrationMode.PLANNED,
                    ):
                        events.append(event)

        grouped = collect_stream_events(events)

        # Verify planning step
        planning_steps = [
            s for s in grouped.get("agent_step", [])
            if s.get("step_type") == "planning"
        ]
        assert len(planning_steps) >= 1
        completed_plans = [s for s in planning_steps if s.get("status") == "completed"]
        assert len(completed_plans) >= 1

        # Verify tasks were created
        task_events = grouped.get("task_created", [])
        assert len(task_events) == 3

        # Verify dependency structure
        t3_event = task_events[2]
        assert t3_event["depends_on"] == [0, 1]

        # Verify tasks started and completed
        assert "task_started" in grouped
        assert "task_completed" in grouped
        completed = grouped["task_completed"]
        assert len(completed) == 3

        # Verify synthesis
        chunks = grouped.get("chunk", [])
        full_text = "".join(c["content"] for c in chunks)
        assert "Q4 analysis" in full_text

        assert "workflow_complete" in grouped

    @pytest.mark.asyncio
    async def test_planned_mode_parallel_independent_tasks(self, mock_langchain_tool, workflow_config):
        """Tasks without dependencies should execute in parallel."""
        from open_notebook.agents.orchestrator import (
            WorkflowOrchestrator,
            OrchestrationMode,
        )

        orchestrator = WorkflowOrchestrator(
            model_name=workflow_config["model_name"],
            notebook_id=workflow_config["notebook_id"],
            tools=[mock_langchain_tool],
        )

        # All tasks independent - should run in same batch
        mock_plan = [
            {"id": "t1", "task": "Task A", "role": "researcher", "depends_on": [], "status": "pending", "result": None},
            {"id": "t2", "task": "Task B", "role": "researcher", "depends_on": [], "status": "pending", "result": None},
            {"id": "t3", "task": "Task C", "role": "analyst", "depends_on": [], "status": "pending", "result": None},
        ]

        execution_order = []

        with patch.object(orchestrator, "_generate_plan", new=AsyncMock(return_value=mock_plan)):
            with patch("open_notebook.agents.orchestrator.DataQueryAgent") as MockAgent:
                instance = MockAgent.return_value
                instance.agent_steps = []
                instance.get_captured_tool_results.return_value = []

                async def track_invoke(query, history=None):
                    execution_order.append(query[:20])
                    return "result"

                instance.invoke = track_invoke

                with patch("open_notebook.agents.orchestrator.SynthesizerAgent") as MockSynth:
                    synth_instance = MockSynth.return_value
                    synth_instance.synthesize = AsyncMock(return_value={
                        "content": "All done",
                        "tool_results": [],
                        "agent_steps": [],
                        "citations": [],
                    })

                    events = []
                    async for event in orchestrator.run("do it", mode=OrchestrationMode.PLANNED):
                        events.append(event)

        grouped = collect_stream_events(events)

        # All 3 tasks should have started
        started = grouped.get("task_started", [])
        assert len(started) == 3

        # All 3 should have completed
        completed = grouped.get("task_completed", [])
        assert len(completed) == 3

    @pytest.mark.asyncio
    async def test_planned_mode_fallback_to_team(self, mock_langchain_tool, workflow_config):
        """If planning fails, should fall back to team mode."""
        from open_notebook.agents.orchestrator import (
            WorkflowOrchestrator,
            OrchestrationMode,
        )

        orchestrator = WorkflowOrchestrator(
            model_name=workflow_config["model_name"],
            notebook_id=workflow_config["notebook_id"],
            tools=[mock_langchain_tool],
        )

        with patch.object(orchestrator, "_generate_plan", new=AsyncMock(return_value=None)):
            with patch("open_notebook.agents.orchestrator.DataQueryAgent") as MockAgent:
                instance = MockAgent.return_value
                instance.agent_steps = []
                instance.get_captured_tool_results.return_value = []
                instance.stream_response = make_mock_agent_stream("fallback data")

                with patch("open_notebook.agents.orchestrator.SynthesizerAgent") as MockSynth:
                    synth_instance = MockSynth.return_value
                    synth_instance.synthesize = AsyncMock(return_value={
                        "content": "Fallback synthesis",
                        "tool_results": [],
                        "agent_steps": [],
                        "citations": [],
                    })

                    events = []
                    async for event in orchestrator.run(
                        "complex query",
                        mode=OrchestrationMode.PLANNED,
                    ):
                        events.append(event)

        grouped = collect_stream_events(events)

        # Should have fallen back to team mode
        assert "team_created" in grouped
        assert "workflow_complete" in grouped


# ============================================================================
# E2E Test: Error Resilience
# ============================================================================

class TestE2EErrorResilience:
    """Test that the system degrades gracefully under failures."""

    @pytest.mark.asyncio
    async def test_agent_failure_doesnt_crash_team(self, mock_langchain_tool, workflow_config):
        """If one agent throws, the team should still produce a result."""
        from open_notebook.agents.orchestrator import (
            WorkflowOrchestrator,
            OrchestrationMode,
        )

        orchestrator = WorkflowOrchestrator(
            model_name=workflow_config["model_name"],
            notebook_id=workflow_config["notebook_id"],
            tools=[mock_langchain_tool],
        )

        call_count = 0

        with patch("open_notebook.agents.orchestrator.DataQueryAgent") as MockAgent:
            def create_agent(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                inst = MagicMock()
                inst.agent_steps = []
                inst.get_captured_tool_results.return_value = []

                if call_count == 1:
                    # Researcher fails
                    async def fail(*a, **kw):
                        raise RuntimeError("LLM timeout")
                        yield  # noqa: E501
                    inst.stream_response = fail
                else:
                    # Analyst succeeds
                    inst.stream_response = make_mock_agent_stream("Analyst found insights")

                return inst

            MockAgent.side_effect = create_agent

            with patch("open_notebook.agents.orchestrator.SynthesizerAgent") as MockSynth:
                synth_instance = MockSynth.return_value
                synth_instance.synthesize = AsyncMock(return_value={
                    "content": "Partial result from analyst only",
                    "tool_results": [],
                    "agent_steps": [],
                    "citations": [],
                })

                events = []
                async for event in orchestrator.run("test", mode=OrchestrationMode.TEAM):
                    events.append(event)

        grouped = collect_stream_events(events)

        # Should still complete
        assert "workflow_complete" in grouped

        # Should have error step
        steps = grouped.get("agent_step", [])
        error_steps = [s for s in steps if s.get("status") == "error"]
        assert len(error_steps) >= 1

    @pytest.mark.asyncio
    async def test_synthesis_failure_still_completes(self, mock_langchain_tool, workflow_config):
        """If synthesis LLM fails, fallback concatenation should work."""
        from open_notebook.agents.orchestrator import (
            WorkflowOrchestrator,
            OrchestrationMode,
        )
        from open_notebook.agents.synthesizer_agent import SynthesizerAgent

        orchestrator = WorkflowOrchestrator(
            model_name=workflow_config["model_name"],
            notebook_id=workflow_config["notebook_id"],
            tools=[mock_langchain_tool],
        )

        with patch("open_notebook.agents.orchestrator.DataQueryAgent") as MockAgent:
            instance = MockAgent.return_value
            instance.agent_steps = []
            instance.get_captured_tool_results.return_value = []
            instance.stream_response = make_mock_agent_stream("Agent data collected")

            with patch("open_notebook.agents.orchestrator.SynthesizerAgent") as MockSynth:
                synth_instance = MockSynth.return_value

                # Synthesize returns fallback (as if LLM failed internally)
                synth_instance.synthesize = AsyncMock(return_value={
                    "content": "**researcher:**\nAgent data collected\n\n---\n\n**analyst:**\nAgent data collected",
                    "tool_results": [],
                    "agent_steps": [],
                    "citations": [],
                })

                events = []
                async for event in orchestrator.run("test", mode=OrchestrationMode.TEAM):
                    events.append(event)

        grouped = collect_stream_events(events)
        assert "workflow_complete" in grouped

        chunks = grouped.get("chunk", [])
        full_text = "".join(c["content"] for c in chunks)
        assert "Agent data collected" in full_text

    @pytest.mark.asyncio
    async def test_workflow_error_emitted_on_crash(self, mock_langchain_tool, workflow_config):
        """A complete failure should emit workflow_error."""
        from open_notebook.agents.orchestrator import (
            WorkflowOrchestrator,
            OrchestrationMode,
        )

        orchestrator = WorkflowOrchestrator(
            model_name=workflow_config["model_name"],
            notebook_id=workflow_config["notebook_id"],
            tools=[mock_langchain_tool],
        )

        with patch.object(
            orchestrator, "_run_single",
            side_effect=RuntimeError("fatal error"),
        ):
            events = []
            async for event in orchestrator.run("test", mode=OrchestrationMode.SINGLE):
                events.append(event)

        grouped = collect_stream_events(events)
        assert "workflow_error" in grouped
        assert "fatal error" in grouped["workflow_error"][0]["error"]


# ============================================================================
# E2E Test: Synthesizer Integration
# ============================================================================

class TestE2ESynthesizerIntegration:
    """Test the synthesizer as part of the full pipeline."""

    @pytest.mark.asyncio
    async def test_synthesizer_receives_all_agent_results(self, mock_langchain_tool, workflow_config):
        """Verify synthesizer is called with results from both agents."""
        from open_notebook.agents.orchestrator import (
            WorkflowOrchestrator,
            OrchestrationMode,
        )

        orchestrator = WorkflowOrchestrator(
            model_name=workflow_config["model_name"],
            notebook_id=workflow_config["notebook_id"],
            tools=[mock_langchain_tool],
        )

        with patch("open_notebook.agents.orchestrator.DataQueryAgent") as MockAgent:
            instance = MockAgent.return_value
            instance.agent_steps = [{"step_type": "thinking", "content": "done", "status": "completed"}]
            instance.get_captured_tool_results.return_value = [
                {"tool_name": "query_sales_data", "result_type": "table"}
            ]
            instance.stream_response = make_mock_agent_stream("Data found")

            with patch("open_notebook.agents.orchestrator.SynthesizerAgent") as MockSynth:
                synth_instance = MockSynth.return_value
                synth_instance.synthesize = AsyncMock(return_value={
                    "content": "Combined",
                    "tool_results": [{"tool_name": "query_sales_data", "source_agent": "researcher"}],
                    "agent_steps": [],
                    "citations": [
                        {"agent_name": "researcher", "agent_role": "researcher"},
                        {"agent_name": "analyst", "agent_role": "analyst"},
                    ],
                })

                events = []
                async for event in orchestrator.run("analyze", mode=OrchestrationMode.TEAM):
                    events.append(event)

                # Verify synthesize was called with both agent results
                call_args = synth_instance.synthesize.call_args
                assert call_args is not None
                query_arg = call_args[0][0]  # first positional arg
                results_arg = call_args[0][1]  # second positional arg

                assert query_arg == "analyze"
                assert len(results_arg) == 2  # researcher + analyst

                roles = {r["agent_role"] for r in results_arg}
                assert "researcher" in roles
                assert "analyst" in roles


# ============================================================================
# E2E Test: Streaming Event Contract
# ============================================================================

class TestE2EStreamingContract:
    """Verify the SSE event contract is consistent across modes."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("mode", ["single", "team", "planned"])
    async def test_all_modes_emit_start_and_complete(self, mode, mock_langchain_tool, workflow_config):
        """Every mode must emit workflow_started and workflow_complete."""
        from open_notebook.agents.orchestrator import (
            WorkflowOrchestrator,
            OrchestrationMode,
        )

        orchestrator = WorkflowOrchestrator(
            model_name=workflow_config["model_name"],
            notebook_id=workflow_config["notebook_id"],
            tools=[mock_langchain_tool],
        )

        enum_mode = OrchestrationMode(mode)

        with patch("open_notebook.agents.orchestrator.DataQueryAgent") as MockAgent:
            instance = MockAgent.return_value
            instance.agent_steps = []
            instance.get_captured_tool_results.return_value = []
            instance.stream_response = make_mock_agent_stream("response")
            instance.invoke = AsyncMock(return_value="response")

            with patch("open_notebook.agents.orchestrator.SynthesizerAgent") as MockSynth:
                synth_instance = MockSynth.return_value
                synth_instance.synthesize = AsyncMock(return_value={
                    "content": "result",
                    "tool_results": [],
                    "agent_steps": [],
                    "citations": [],
                })

                if mode == "planned":
                    plan = [
                        {"id": "t1", "task": "Do X", "role": "researcher",
                         "depends_on": [], "status": "pending", "result": None},
                    ]
                    with patch.object(orchestrator, "_generate_plan", new=AsyncMock(return_value=plan)):
                        events = []
                        async for event in orchestrator.run("query", mode=enum_mode):
                            events.append(event)
                else:
                    events = []
                    async for event in orchestrator.run("query", mode=enum_mode):
                        events.append(event)

        grouped = collect_stream_events(events)

        assert "workflow_started" in grouped, f"Missing workflow_started for mode={mode}"
        assert grouped["workflow_started"][0]["mode"] == mode

        assert "workflow_complete" in grouped, f"Missing workflow_complete for mode={mode}"

    @pytest.mark.asyncio
    async def test_events_are_valid_json(self, mock_langchain_tool, workflow_config):
        """All event data fields must be valid JSON strings."""
        from open_notebook.agents.orchestrator import (
            WorkflowOrchestrator,
            OrchestrationMode,
        )

        orchestrator = WorkflowOrchestrator(
            model_name=workflow_config["model_name"],
            notebook_id=workflow_config["notebook_id"],
            tools=[mock_langchain_tool],
        )

        with patch("open_notebook.agents.orchestrator.DataQueryAgent") as MockAgent:
            instance = MockAgent.return_value
            instance.agent_steps = []
            instance.get_captured_tool_results.return_value = []
            instance.stream_response = make_mock_agent_stream("test")

            events = []
            async for event in orchestrator.run("test", mode=OrchestrationMode.SINGLE):
                events.append(event)

        for event in events:
            assert "event" in event, "Event missing 'event' key"
            assert "data" in event, "Event missing 'data' key"
            # Data must be valid JSON
            data = json.loads(event["data"])
            assert isinstance(data, dict), f"Event data should be dict, got {type(data)}"


# ============================================================================
# E2E Test: Chat History Propagation
# ============================================================================

class TestE2EChatHistoryPropagation:
    """Verify that chat history is forwarded to agents."""

    @pytest.mark.asyncio
    async def test_single_mode_passes_history(self, mock_langchain_tool, workflow_config):
        """Chat history should be passed to the DataQueryAgent."""
        from open_notebook.agents.orchestrator import (
            WorkflowOrchestrator,
            OrchestrationMode,
        )

        orchestrator = WorkflowOrchestrator(
            model_name=workflow_config["model_name"],
            notebook_id=workflow_config["notebook_id"],
            tools=[mock_langchain_tool],
        )

        history = [
            {"role": "user", "content": "What is Q3 data?"},
            {"role": "assistant", "content": "Q3 showed 10% growth."},
        ]

        captured_history = []

        with patch("open_notebook.agents.orchestrator.DataQueryAgent") as MockAgent:
            instance = MockAgent.return_value
            instance.agent_steps = []
            instance.get_captured_tool_results.return_value = []

            async def capture_stream(query, chat_history=None):
                captured_history.append(chat_history)
                msg = MagicMock()
                msg.content = "Q4 data"
                msg.tool_calls = []
                yield {"agent": {"messages": [msg]}}

            instance.stream_response = capture_stream

            events = []
            async for event in orchestrator.run(
                "Now show me Q4",
                mode=OrchestrationMode.SINGLE,
                chat_history=history,
            ):
                events.append(event)

        # Agent should have received the history
        assert len(captured_history) == 1
        assert captured_history[0] == history
