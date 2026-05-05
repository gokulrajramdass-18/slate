"""
Unit tests for multi-agent task-based orchestration system.

Tests the LangGraph-based multi-agent orchestration including:
- Routing logic (single vs multi-agent)
- Agent identification and matching
- Task record creation
- Parallel execution
- Dependency-aware execution
- Error handling and fallback scenarios
"""

import pytest
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from api.services.langgraph_orchestrator import (
    LangGraphOrchestrator,
    DynamicAgentState
)
from open_notebook.database.repository import repo_query, repo_execute


class TestRoutingLogic:
    """Test conditional routing between single and multi-agent modes."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance for testing."""
        team_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())
        llm = Mock()
        tools = []
        return LangGraphOrchestrator(team_id, execution_id, llm, tools)

    def test_route_single_agent_simple_query(self, orchestrator):
        """Verify simple queries route to single-agent mode."""
        state: DynamicAgentState = {
            "query": "What is 2+2?",
            "role": "researcher",
            "team_id": orchestrator.team_id,
            "execution_id": orchestrator.execution_id,
            "available_sources": [],
            "available_tools": [],
            "source_context": "",
            "analysis": {
                "complexity": "simple",
                "estimated_steps": 1,
                "recommended_agent_count": 1
            },
            "plan": [],
            "current_step": 0,
            "step_results": [],
            "tool_calls": [],
            "errors": [],
            "final_answer": None,
            "status": "planning",
            "orchestration_mode": "single",
            "assigned_agents": [],
            "task_records": [],
            "agent_results": [],
            "messages": []
        }

        route = orchestrator._route_orchestration(state)
        assert route == "single"

    def test_route_single_agent_moderate_two_steps(self, orchestrator):
        """Verify moderate queries with 2 steps route to single-agent mode."""
        state: DynamicAgentState = {
            "query": "Search for data and summarize",
            "role": "researcher",
            "team_id": orchestrator.team_id,
            "execution_id": orchestrator.execution_id,
            "available_sources": [],
            "available_tools": [],
            "source_context": "",
            "analysis": {
                "complexity": "moderate",
                "estimated_steps": 2,
                "recommended_agent_count": 1
            },
            "plan": [],
            "current_step": 0,
            "step_results": [],
            "tool_calls": [],
            "errors": [],
            "final_answer": None,
            "status": "planning",
            "orchestration_mode": "single",
            "assigned_agents": [],
            "task_records": [],
            "agent_results": [],
            "messages": []
        }

        route = orchestrator._route_orchestration(state)
        assert route == "single"

    def test_route_multi_agent_complex_query(self, orchestrator):
        """Verify complex queries route to multi-agent mode."""
        state: DynamicAgentState = {
            "query": "Analyze sales data, create visualizations, and write report",
            "role": "researcher",
            "team_id": orchestrator.team_id,
            "execution_id": orchestrator.execution_id,
            "available_sources": [],
            "available_tools": [],
            "source_context": "",
            "analysis": {
                "complexity": "complex",
                "estimated_steps": 4,
                "recommended_agent_count": 3
            },
            "plan": [],
            "current_step": 0,
            "step_results": [],
            "tool_calls": [],
            "errors": [],
            "final_answer": None,
            "status": "planning",
            "orchestration_mode": "single",
            "assigned_agents": [],
            "task_records": [],
            "agent_results": [],
            "messages": []
        }

        route = orchestrator._route_orchestration(state)
        assert route == "multi"

    def test_route_multi_agent_many_steps(self, orchestrator):
        """Verify queries with >2 steps route to multi-agent mode."""
        state: DynamicAgentState = {
            "query": "Multi-step analysis",
            "role": "researcher",
            "team_id": orchestrator.team_id,
            "execution_id": orchestrator.execution_id,
            "available_sources": [],
            "available_tools": [],
            "source_context": "",
            "analysis": {
                "complexity": "moderate",
                "estimated_steps": 3,
                "recommended_agent_count": 1
            },
            "plan": [],
            "current_step": 0,
            "step_results": [],
            "tool_calls": [],
            "errors": [],
            "final_answer": None,
            "status": "planning",
            "orchestration_mode": "single",
            "assigned_agents": [],
            "task_records": [],
            "agent_results": [],
            "messages": []
        }

        route = orchestrator._route_orchestration(state)
        assert route == "multi"

    def test_route_multi_agent_multiple_agents_recommended(self, orchestrator):
        """Verify queries recommending multiple agents route to multi-agent mode."""
        state: DynamicAgentState = {
            "query": "Collaborative analysis",
            "role": "researcher",
            "team_id": orchestrator.team_id,
            "execution_id": orchestrator.execution_id,
            "available_sources": [],
            "available_tools": [],
            "source_context": "",
            "analysis": {
                "complexity": "moderate",
                "estimated_steps": 2,
                "recommended_agent_count": 2
            },
            "plan": [],
            "current_step": 0,
            "step_results": [],
            "tool_calls": [],
            "errors": [],
            "final_answer": None,
            "status": "planning",
            "orchestration_mode": "single",
            "assigned_agents": [],
            "task_records": [],
            "agent_results": [],
            "messages": []
        }

        route = orchestrator._route_orchestration(state)
        assert route == "multi"


class TestAgentMatching:
    """Test agent identification and matching logic."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance for testing."""
        team_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())
        llm = Mock()
        tools = []
        return LangGraphOrchestrator(team_id, execution_id, llm, tools)

    def test_match_agent_by_tool(self, orchestrator):
        """Verify agent matching by required tool."""
        step = {
            "step_name": "Query HANA",
            "tool_name": "hana_query_tool"
        }

        agents = [
            {
                "id": "agent-1",
                "name": "Data Analyst",
                "role": "analyst",
                "tool_ids": ["hana_query_tool", "calculator"]
            },
            {
                "id": "agent-2",
                "name": "Researcher",
                "role": "researcher",
                "tool_ids": ["web_search", "wikipedia"]
            }
        ]

        matched = orchestrator._match_agent_to_step(step, agents)
        assert matched is not None
        assert matched["id"] == "agent-1"
        assert matched["name"] == "Data Analyst"

    def test_match_agent_by_tool_comma_separated(self, orchestrator):
        """Verify agent matching with comma-separated tool_ids string."""
        step = {
            "step_name": "Search web",
            "tool_name": "web_search"
        }

        agents = [
            {
                "id": "agent-1",
                "name": "Researcher",
                "role": "researcher",
                "tool_ids": "web_search, wikipedia, url_fetch"  # String format
            }
        ]

        matched = orchestrator._match_agent_to_step(step, agents)
        assert matched is not None
        assert matched["id"] == "agent-1"

    def test_match_agent_by_role_fallback(self, orchestrator):
        """Verify agent matching by role when tool not found."""
        step = {
            "step_name": "Analyze data",
            "step_type": "data_query"
        }

        agents = [
            {
                "id": "agent-1",
                "name": "Data Analyst",
                "role": "data_analyst",
                "tool_ids": []
            },
            {
                "id": "agent-2",
                "name": "Researcher",
                "role": "researcher",
                "tool_ids": []
            }
        ]

        matched = orchestrator._match_agent_to_step(step, agents)
        assert matched is not None
        assert matched["id"] == "agent-1"
        assert matched["role"] == "data_analyst"

    def test_match_agent_fallback_to_first(self, orchestrator):
        """Verify fallback to first agent when no matches."""
        step = {
            "step_name": "Unknown task",
            "tool_name": "nonexistent_tool"
        }

        agents = [
            {
                "id": "agent-1",
                "name": "Generic Agent",
                "role": "generic",
                "tool_ids": ["other_tool"]
            }
        ]

        matched = orchestrator._match_agent_to_step(step, agents)
        assert matched is not None
        assert matched["id"] == "agent-1"

    def test_match_agent_no_agents_available(self, orchestrator):
        """Verify None returned when no agents available."""
        step = {
            "step_name": "Some task",
            "tool_name": "some_tool"
        }

        agents = []

        matched = orchestrator._match_agent_to_step(step, agents)
        assert matched is None


class TestTaskCreation:
    """Test task record creation and database operations."""

    @pytest.mark.asyncio
    async def test_create_tasks_from_plan(self):
        """Verify task records are created from execution plan."""
        team_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())
        llm = Mock()
        tools = []

        orchestrator = LangGraphOrchestrator(team_id, execution_id, llm, tools)

        state: DynamicAgentState = {
            "query": "Analyze and report",
            "role": "researcher",
            "team_id": team_id,
            "execution_id": execution_id,
            "available_sources": [],
            "available_tools": [],
            "source_context": "",
            "analysis": None,
            "plan": [
                {
                    "step_name": "Query HANA",
                    "tool_name": "hana_query",
                    "step_type": "data_query"
                },
                {
                    "step_name": "Generate summary",
                    "tool_name": "text_gen",
                    "step_type": "synthesis"
                }
            ],
            "current_step": 0,
            "step_results": [],
            "tool_calls": [],
            "errors": [],
            "final_answer": None,
            "status": "planning",
            "orchestration_mode": "multi",
            "assigned_agents": [
                {
                    "id": "agent-1",
                    "name": "Data Analyst",
                    "role": "data_analyst",
                    "tool_ids": ["hana_query"]
                },
                {
                    "id": "agent-2",
                    "name": "Writer",
                    "role": "writer",
                    "tool_ids": ["text_gen"]
                }
            ],
            "task_records": [],
            "agent_results": [],
            "messages": []
        }

        with patch('api.services.langgraph_orchestrator.repo_execute') as mock_execute:
            mock_execute.return_value = None

            result = await orchestrator._create_tasks_node(state)

            # Verify task records created
            assert "task_records" in result
            assert len(result["task_records"]) == 2

            # Verify first task
            task1 = result["task_records"][0]
            assert task1["title"] == "Query HANA"
            assert task1["agent_id"] == "agent-1"
            assert task1["status"] == "pending"
            assert task1["priority"] == 0

            # Verify second task
            task2 = result["task_records"][1]
            assert task2["title"] == "Generate summary"
            assert task2["agent_id"] == "agent-2"
            assert task2["status"] == "pending"
            assert task2["priority"] == 1

            # Verify database calls
            assert mock_execute.call_count >= 2  # At least 2 task inserts

    @pytest.mark.asyncio
    async def test_create_tasks_logs_messages(self):
        """Verify task creation logs assignment messages."""
        team_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())
        llm = Mock()
        tools = []

        orchestrator = LangGraphOrchestrator(team_id, execution_id, llm, tools)

        state: DynamicAgentState = {
            "query": "Test query",
            "role": "researcher",
            "team_id": team_id,
            "execution_id": execution_id,
            "available_sources": [],
            "available_tools": [],
            "source_context": "",
            "analysis": None,
            "plan": [
                {"step_name": "Task 1", "tool_name": "tool1"}
            ],
            "current_step": 0,
            "step_results": [],
            "tool_calls": [],
            "errors": [],
            "final_answer": None,
            "status": "planning",
            "orchestration_mode": "multi",
            "assigned_agents": [
                {
                    "id": "agent-1",
                    "name": "Agent A",
                    "role": "generic",
                    "tool_ids": ["tool1"]
                }
            ],
            "task_records": [],
            "agent_results": [],
            "messages": []
        }

        with patch('api.services.langgraph_orchestrator.repo_execute') as mock_execute:
            mock_execute.return_value = None

            result = await orchestrator._create_tasks_node(state)

            # Verify messages created
            assert "messages" in result
            assert len(result["messages"]) >= 1

            # Verify message content
            message = result["messages"][0]
            assert message["sender_id"] == "system"
            assert message["recipient_id"] == "agent-1"
            assert "Task 1" in message["content"]


class TestAgentIdentification:
    """Test agent identification and database queries."""

    @pytest.mark.asyncio
    async def test_identify_agents_matches_roles(self):
        """Verify agents are identified based on recommended roles."""
        team_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())
        llm = Mock()
        tools = []

        orchestrator = LangGraphOrchestrator(team_id, execution_id, llm, tools)

        state: DynamicAgentState = {
            "query": "Research and analyze",
            "role": "researcher",
            "team_id": team_id,
            "execution_id": execution_id,
            "available_sources": [],
            "available_tools": [],
            "source_context": "",
            "analysis": {
                "complexity": "complex",
                "recommended_agent_roles": ["researcher", "analyst"]
            },
            "plan": [],
            "current_step": 0,
            "step_results": [],
            "tool_calls": [],
            "errors": [],
            "final_answer": None,
            "status": "planning",
            "orchestration_mode": "multi",
            "assigned_agents": [],
            "task_records": [],
            "agent_results": [],
            "messages": []
        }

        mock_agents = [
            {
                "id": "agent-1",
                "name": "Researcher",
                "role": "researcher",
                "tool_ids": ["web_search"],
                "capabilities": [],
                "config": {},
                "status": "active"
            },
            {
                "id": "agent-2",
                "name": "Data Analyst",
                "role": "analyst",
                "tool_ids": ["data_tool"],
                "capabilities": [],
                "config": {},
                "status": "active"
            },
            {
                "id": "agent-3",
                "name": "Writer",
                "role": "writer",
                "tool_ids": ["text_gen"],
                "capabilities": [],
                "config": {},
                "status": "active"
            }
        ]

        with patch('api.services.langgraph_orchestrator.repo_query') as mock_query, \
             patch('api.services.langgraph_orchestrator.repo_execute') as mock_execute:

            mock_query.return_value = mock_agents
            mock_execute.return_value = None

            result = await orchestrator._identify_agents_node(state)

            # Verify agents identified
            assert "assigned_agents" in result
            assert len(result["assigned_agents"]) == 2  # Only researcher and analyst

            # Verify correct agents matched
            agent_roles = [a["role"] for a in result["assigned_agents"]]
            assert "researcher" in agent_roles
            assert "analyst" in agent_roles
            assert "writer" not in agent_roles

    @pytest.mark.asyncio
    async def test_identify_agents_fallback_all_agents(self):
        """Verify all agents used when no role matches."""
        team_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())
        llm = Mock()
        tools = []

        orchestrator = LangGraphOrchestrator(team_id, execution_id, llm, tools)

        state: DynamicAgentState = {
            "query": "Generic task",
            "role": "researcher",
            "team_id": team_id,
            "execution_id": execution_id,
            "available_sources": [],
            "available_tools": [],
            "source_context": "",
            "analysis": {
                "complexity": "complex",
                "recommended_agent_roles": ["nonexistent_role"]
            },
            "plan": [],
            "current_step": 0,
            "step_results": [],
            "tool_calls": [],
            "errors": [],
            "final_answer": None,
            "status": "planning",
            "orchestration_mode": "multi",
            "assigned_agents": [],
            "task_records": [],
            "agent_results": [],
            "messages": []
        }

        mock_agents = [
            {"id": "agent-1", "name": "Agent 1", "role": "generic", "tool_ids": [], "status": "active"},
            {"id": "agent-2", "name": "Agent 2", "role": "generic", "tool_ids": [], "status": "active"}
        ]

        with patch('api.services.langgraph_orchestrator.repo_query') as mock_query, \
             patch('api.services.langgraph_orchestrator.repo_execute') as mock_execute:

            mock_query.return_value = mock_agents
            mock_execute.return_value = None

            result = await orchestrator._identify_agents_node(state)

            # Verify all agents used as fallback
            assert len(result["assigned_agents"]) == 2

    @pytest.mark.asyncio
    async def test_identify_agents_no_agents_available(self):
        """Verify fallback to single-agent mode when no agents found."""
        team_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())
        llm = Mock()
        tools = []

        orchestrator = LangGraphOrchestrator(team_id, execution_id, llm, tools)

        state: DynamicAgentState = {
            "query": "Test query",
            "role": "researcher",
            "team_id": team_id,
            "execution_id": execution_id,
            "available_sources": [],
            "available_tools": [],
            "source_context": "",
            "analysis": {"complexity": "complex"},
            "plan": [],
            "current_step": 0,
            "step_results": [],
            "tool_calls": [],
            "errors": [],
            "final_answer": None,
            "status": "planning",
            "orchestration_mode": "multi",
            "assigned_agents": [],
            "task_records": [],
            "agent_results": [],
            "messages": []
        }

        with patch('api.services.langgraph_orchestrator.repo_query') as mock_query, \
             patch('api.services.langgraph_orchestrator.repo_execute') as mock_execute:

            mock_query.return_value = []  # No agents
            mock_execute.return_value = None

            result = await orchestrator._identify_agents_node(state)

            # Verify fallback
            assert result["orchestration_mode"] == "single"
            assert len(result["assigned_agents"]) == 0


class TestParallelExecution:
    """Test parallel task execution."""

    @pytest.mark.asyncio
    async def test_execute_tasks_in_parallel(self):
        """Verify independent tasks execute in parallel."""
        team_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())
        llm = Mock()
        tools = []

        orchestrator = LangGraphOrchestrator(team_id, execution_id, llm, tools)

        # Mock tasks
        task1_id = str(uuid.uuid4())
        task2_id = str(uuid.uuid4())

        mock_tasks = [
            {
                "id": task1_id,
                "title": "Task 1",
                "assignee_id": "agent-1",
                "description": json.dumps({"step_name": "Task 1"}),
                "status": "pending",
                "depends_on": "[]"
            },
            {
                "id": task2_id,
                "title": "Task 2",
                "assignee_id": "agent-2",
                "description": json.dumps({"step_name": "Task 2"}),
                "status": "pending",
                "depends_on": "[]"
            }
        ]

        state: DynamicAgentState = {
            "query": "Test",
            "role": "researcher",
            "team_id": team_id,
            "execution_id": execution_id,
            "available_sources": [],
            "available_tools": [],
            "source_context": "",
            "analysis": None,
            "plan": [],
            "current_step": 0,
            "step_results": [],
            "tool_calls": [],
            "errors": [],
            "final_answer": None,
            "status": "executing",
            "orchestration_mode": "multi",
            "assigned_agents": [],
            "task_records": [],
            "agent_results": [],
            "messages": []
        }

        with patch('api.services.langgraph_orchestrator.repo_query') as mock_query, \
             patch('api.services.langgraph_orchestrator.repo_execute') as mock_execute, \
             patch.object(orchestrator, '_execute_agent_task') as mock_exec_task:

            mock_query.return_value = mock_tasks
            mock_execute.return_value = None

            # Mock task execution results
            mock_exec_task.side_effect = [
                {"success": True, "output": "Result 1", "timestamp": datetime.utcnow().isoformat()},
                {"success": True, "output": "Result 2", "timestamp": datetime.utcnow().isoformat()}
            ]

            # Mock TaskManager (imported inside the function)
            with patch('open_notebook.agents.task_manager.TaskManager') as mock_tm_class:
                mock_tm = Mock()
                mock_tm.get_execution_order = AsyncMock(return_value=[[task1_id, task2_id]])  # Both in same layer
                mock_tm_class.return_value = mock_tm

                result = await orchestrator._execute_multi_agent_node(state)

                # Verify both tasks executed
                assert "agent_results" in result
                assert len(result["agent_results"]) == 2

                # Verify both succeeded
                assert all(r["status"] == "completed" for r in result["agent_results"])


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_task_execution_failure_continues(self):
        """Verify execution continues when one task fails."""
        team_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())
        llm = Mock()
        tools = []

        orchestrator = LangGraphOrchestrator(team_id, execution_id, llm, tools)

        task1_id = str(uuid.uuid4())
        task2_id = str(uuid.uuid4())

        mock_tasks = [
            {
                "id": task1_id,
                "title": "Task 1",
                "assignee_id": "agent-1",
                "description": json.dumps({"step_name": "Task 1"}),
                "status": "pending"
            },
            {
                "id": task2_id,
                "title": "Task 2",
                "assignee_id": "agent-2",
                "description": json.dumps({"step_name": "Task 2"}),
                "status": "pending"
            }
        ]

        state: DynamicAgentState = {
            "query": "Test",
            "role": "researcher",
            "team_id": team_id,
            "execution_id": execution_id,
            "available_sources": [],
            "available_tools": [],
            "source_context": "",
            "analysis": None,
            "plan": [],
            "current_step": 0,
            "step_results": [],
            "tool_calls": [],
            "errors": [],
            "final_answer": None,
            "status": "executing",
            "orchestration_mode": "multi",
            "assigned_agents": [],
            "task_records": [],
            "agent_results": [],
            "messages": []
        }

        with patch('api.services.langgraph_orchestrator.repo_query') as mock_query, \
             patch('api.services.langgraph_orchestrator.repo_execute') as mock_execute, \
             patch.object(orchestrator, '_execute_agent_task') as mock_exec_task:

            mock_query.return_value = mock_tasks
            mock_execute.return_value = None

            # First task fails, second succeeds
            mock_exec_task.side_effect = [
                Exception("Task 1 failed"),
                {"success": True, "output": "Result 2", "timestamp": datetime.utcnow().isoformat()}
            ]

            with patch('open_notebook.agents.task_manager.TaskManager') as mock_tm_class:
                mock_tm = Mock()
                mock_tm.get_execution_order = AsyncMock(return_value=[[task1_id, task2_id]])
                mock_tm_class.return_value = mock_tm

                result = await orchestrator._execute_multi_agent_node(state)

                # Verify both tasks processed
                assert len(result["agent_results"]) == 2

                # Verify one failed, one succeeded
                statuses = [r["status"] for r in result["agent_results"]]
                assert "failed" in statuses
                assert "completed" in statuses

    @pytest.mark.asyncio
    async def test_consolidation_llm_failure_fallback(self):
        """Verify fallback when LLM consolidation fails."""
        team_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())

        # Mock LLM that raises exception
        llm = Mock()
        llm.ainvoke = AsyncMock(side_effect=Exception("LLM error"))
        tools = []

        orchestrator = LangGraphOrchestrator(team_id, execution_id, llm, tools)

        state: DynamicAgentState = {
            "query": "Test query",
            "role": "researcher",
            "team_id": team_id,
            "execution_id": execution_id,
            "available_sources": [],
            "available_tools": [],
            "source_context": "",
            "analysis": None,
            "plan": [],
            "current_step": 0,
            "step_results": [],
            "tool_calls": [],
            "errors": [],
            "final_answer": None,
            "status": "aggregating",
            "orchestration_mode": "multi",
            "assigned_agents": [],
            "task_records": [],
            "agent_results": [
                {"task_id": "t1", "agent_id": "a1", "status": "completed", "result": "Result 1"},
                {"task_id": "t2", "agent_id": "a2", "status": "completed", "result": "Result 2"}
            ],
            "messages": []
        }

        result = await orchestrator._consolidate_multi_results_node(state)

        # Verify fallback answer provided
        assert "final_answer" in result
        assert result["final_answer"] is not None
        assert "Result 1" in result["final_answer"] or "Result 2" in result["final_answer"]

        # Verify error logged
        assert "errors" in result
        assert len(result["errors"]) > 0


class TestMessageLogging:
    """Test coordination message logging."""

    @pytest.mark.asyncio
    async def test_log_message_creates_database_record(self):
        """Verify message logging creates database record."""
        team_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())
        llm = Mock()
        tools = []

        orchestrator = LangGraphOrchestrator(team_id, execution_id, llm, tools)

        with patch('api.services.langgraph_orchestrator.repo_execute') as mock_execute:
            mock_execute.return_value = None

            message_id = await orchestrator._log_message(
                team_id=team_id,
                execution_id=execution_id,
                sender_id="system",
                recipient_id="agent-1",
                message_type="task_assignment",
                content="Assigned task to agent",
                metadata={"task_id": "task-123"}
            )

            # Verify message ID returned
            assert message_id is not None

            # Verify database insert called
            mock_execute.assert_called_once()
            call_args = mock_execute.call_args

            # Verify SQL contains INSERT INTO agent_messages
            assert "agent_messages" in call_args[0][0]

            # Verify parameters
            params = call_args[0][1]
            assert params["team"] == team_id
            assert params["sender"] == "system"
            assert params["recipient"] == "agent-1"
            assert params["type"] == "task_assignment"
            assert params["content"] == "Assigned task to agent"

    @pytest.mark.asyncio
    async def test_log_broadcast_message(self):
        """Verify broadcast messages (recipient_id = None) work."""
        team_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())
        llm = Mock()
        tools = []

        orchestrator = LangGraphOrchestrator(team_id, execution_id, llm, tools)

        with patch('api.services.langgraph_orchestrator.repo_execute') as mock_execute:
            mock_execute.return_value = None

            message_id = await orchestrator._log_message(
                team_id=team_id,
                execution_id=execution_id,
                sender_id="system",
                recipient_id=None,  # Broadcast
                message_type="system_broadcast",
                content="System message to all agents"
            )

            # Verify message created
            assert message_id is not None

            # Verify recipient_id is None in params
            params = mock_execute.call_args[0][1]
            assert params["recipient"] is None


class TestIntegration:
    """Integration tests for full workflow."""

    @pytest.mark.asyncio
    async def test_full_multi_agent_flow_simulation(self):
        """Simulate complete multi-agent execution flow."""
        team_id = str(uuid.uuid4())
        execution_id = str(uuid.uuid4())

        # Mock LLM
        llm = Mock()
        llm.ainvoke = AsyncMock(return_value=Mock(content="Consolidated answer"))
        tools = []

        orchestrator = LangGraphOrchestrator(team_id, execution_id, llm, tools)

        # 1. Test routing
        analysis_state: DynamicAgentState = {
            "query": "Complex multi-agent query",
            "role": "researcher",
            "team_id": team_id,
            "execution_id": execution_id,
            "available_sources": [],
            "available_tools": [],
            "source_context": "",
            "analysis": {
                "complexity": "complex",
                "estimated_steps": 3,
                "recommended_agent_count": 2,
                "recommended_agent_roles": ["researcher", "analyst"]
            },
            "plan": [],
            "current_step": 0,
            "step_results": [],
            "tool_calls": [],
            "errors": [],
            "final_answer": None,
            "status": "planning",
            "orchestration_mode": "single",
            "assigned_agents": [],
            "task_records": [],
            "agent_results": [],
            "messages": []
        }

        route = orchestrator._route_orchestration(analysis_state)
        assert route == "multi", "Should route to multi-agent mode"

        # 2. Test agent identification
        mock_agents = [
            {"id": "agent-1", "name": "Researcher", "role": "researcher", "tool_ids": ["web_search"], "status": "active"},
            {"id": "agent-2", "name": "Analyst", "role": "analyst", "tool_ids": ["data_tool"], "status": "active"}
        ]

        with patch('api.services.langgraph_orchestrator.repo_query') as mock_query, \
             patch('api.services.langgraph_orchestrator.repo_execute') as mock_execute:

            mock_query.return_value = mock_agents
            mock_execute.return_value = None

            identify_result = await orchestrator._identify_agents_node(analysis_state)

            assert len(identify_result["assigned_agents"]) == 2
            assert identify_result["orchestration_mode"] == "multi"

        # 3. Test task creation
        task_state = {**analysis_state, **identify_result}
        task_state["plan"] = [
            {"step_name": "Research", "tool_name": "web_search"},
            {"step_name": "Analyze", "tool_name": "data_tool"}
        ]

        with patch('api.services.langgraph_orchestrator.repo_execute') as mock_execute:
            mock_execute.return_value = None

            create_result = await orchestrator._create_tasks_node(task_state)

            assert len(create_result["task_records"]) == 2
            assert len(create_result["messages"]) >= 2

        print("\n✅ Full multi-agent flow simulation passed!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
