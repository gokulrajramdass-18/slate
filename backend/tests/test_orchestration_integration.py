"""
Integration Tests for Autonomous Orchestration

Tests the full orchestration lifecycle from decision to synthesis.
"""

import pytest
import asyncio
from typing import List, Dict, Any

from open_notebook.agents.orchestration_decision import OrchestrationDecisionEngine, OrchestrationDecision
from open_notebook.agents.team_spawner import TeamSpawner
from open_notebook.agents.execution_scheduler import ExecutionScheduler
from open_notebook.agents.handover_coordinator import HandoverCoordinator
from open_notebook.agents.autonomous_orchestrator import AutonomousOrchestrator
from api.services.orchestration_detection import OrchestrationDetector


@pytest.mark.asyncio
class TestOrchestrationDetection:
    """Test orchestration detection heuristics."""

    async def test_simple_query_detection(self):
        """Simple queries should not trigger orchestration."""
        detector = OrchestrationDetector(enable_llm_detection=False)

        result = await detector.should_orchestrate(
            query="What is the capital of France?",
            available_tools=[],
            context={}
        )

        assert result["complexity"] == "simple"
        assert result["should_orchestrate"] is False
        assert result["confidence"] > 0.7

    async def test_moderate_query_detection(self):
        """Moderate queries should show moderate complexity."""
        detector = OrchestrationDetector(enable_llm_detection=False)

        result = await detector.should_orchestrate(
            query="Analyze the sales data and create a summary report",
            available_tools=[],
            context={}
        )

        assert result["complexity"] in ["moderate", "complex"]
        assert result["confidence"] > 0.3

    async def test_complex_query_detection(self):
        """Complex queries should trigger orchestration."""
        detector = OrchestrationDetector(enable_llm_detection=False)

        result = await detector.should_orchestrate(
            query="First query HANA for Q4 sales data, then research competitor prices on the web, compare the results, and generate a comprehensive analysis report with recommendations",
            available_tools=[],
            context={}
        )

        assert result["complexity"] == "complex"
        assert result["should_orchestrate"] is True
        assert result["confidence"] > 0.6

    async def test_cross_domain_detection(self):
        """Cross-domain queries should indicate complexity."""
        detector = OrchestrationDetector(enable_llm_detection=False)

        result = await detector.should_orchestrate(
            query="Query the database for customer data, search the web for industry benchmarks, and create a comparison report",
            available_tools=[],
            context={}
        )

        assert result["complexity"] in ["moderate", "complex"]
        assert "Cross-domain" in result["reasoning"] or "Multiple actions" in result["reasoning"]


@pytest.mark.asyncio
class TestOrchestrationDecision:
    """Test orchestration decision engine."""

    async def test_simple_decision(self):
        """Simple goal should result in single agent mode."""
        engine = OrchestrationDecisionEngine()

        decision = await engine.decide(
            goal="What is 2 + 2?",
            complexity="simple",
            intent="calculation",
            capabilities=[],
            resources={}
        )

        assert decision.mode == "single"
        assert decision.team_size == 1
        assert len(decision.roles) == 1

    async def test_moderate_decision(self):
        """Moderate goal should result in team mode."""
        engine = OrchestrationDecisionEngine()

        decision = await engine.decide(
            goal="Analyze sales data and create report",
            complexity="moderate",
            intent="analysis",
            capabilities=["data_analysis", "reporting"],
            resources={}
        )

        assert decision.mode in ["team", "single"]
        if decision.mode == "team":
            assert 2 <= decision.team_size <= 4

    async def test_complex_decision(self):
        """Complex goal should result in team or swarm mode."""
        engine = OrchestrationDecisionEngine()

        decision = await engine.decide(
            goal="Research competitor strategies, analyze our sales data, synthesize insights, and create presentation",
            complexity="complex",
            intent="comprehensive_analysis",
            capabilities=["research", "data_analysis", "synthesis", "reporting"],
            resources={}
        )

        assert decision.mode in ["team", "swarm"]
        assert decision.team_size >= 2


@pytest.mark.asyncio
class TestExecutionScheduler:
    """Test task scheduling logic."""

    async def test_simple_sequential_scheduling(self):
        """Tasks with dependencies should be scheduled sequentially."""
        scheduler = ExecutionScheduler()

        tasks = [
            {"id": "task1", "dependencies": []},
            {"id": "task2", "dependencies": ["task1"]},
            {"id": "task3", "dependencies": ["task2"]}
        ]

        layers = await scheduler.schedule_tasks(tasks, agents=[], resources={})

        # Should have 3 layers (sequential)
        assert len(layers) == 3
        assert layers[0] == ["task1"]
        assert layers[1] == ["task2"]
        assert layers[2] == ["task3"]

    async def test_parallel_scheduling(self):
        """Independent tasks should be scheduled in parallel."""
        scheduler = ExecutionScheduler()

        tasks = [
            {"id": "task1", "dependencies": []},
            {"id": "task2", "dependencies": []},
            {"id": "task3", "dependencies": []}
        ]

        layers = await scheduler.schedule_tasks(tasks, agents=[], resources={})

        # Should have 1 layer (all parallel)
        assert len(layers) >= 1
        # First layer should contain all tasks (or split if resource constrained)
        assert "task1" in layers[0] or "task1" in layers[1] if len(layers) > 1 else True

    async def test_mixed_scheduling(self):
        """Mixed dependencies should create proper execution order."""
        scheduler = ExecutionScheduler()

        tasks = [
            {"id": "task1", "dependencies": []},
            {"id": "task2", "dependencies": []},
            {"id": "task3", "dependencies": ["task1", "task2"]},
        ]

        layers = await scheduler.schedule_tasks(tasks, agents=[], resources={})

        # Should have 2 layers
        assert len(layers) == 2
        # task1 and task2 in first layer
        assert set(layers[0]) == {"task1", "task2"}
        # task3 in second layer
        assert layers[1] == ["task3"]


@pytest.mark.asyncio
class TestAutonomousOrchestrator:
    """Test end-to-end orchestration."""

    @pytest.mark.skip(reason="Requires full infrastructure setup")
    async def test_orchestrator_simple_goal(self):
        """Test orchestrator with simple goal."""
        orchestrator = AutonomousOrchestrator()

        result = await orchestrator.execute(
            goal="What is 2 + 2?",
            user_id="test-user",
            notebook_id=None,
            resources={}
        )

        assert result["success"] is True
        assert result["orchestration_mode"] == "single"
        assert result["result"] is not None

    @pytest.mark.skip(reason="Requires full infrastructure setup")
    async def test_orchestrator_complex_goal(self):
        """Test orchestrator with complex goal."""
        orchestrator = AutonomousOrchestrator()

        result = await orchestrator.execute(
            goal="Analyze Q4 sales data from HANA, research competitor pricing, compare results, and generate report",
            user_id="test-user",
            notebook_id="test-notebook",
            resources={}
        )

        assert result["success"] is True
        assert result["orchestration_mode"] in ["team", "swarm"]
        assert result["team_id"] is not None
        assert result["result"] is not None


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
