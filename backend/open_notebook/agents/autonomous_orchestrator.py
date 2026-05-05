"""
Autonomous Orchestrator

LangGraph-based supervisor agent that orchestrates dynamic agent team spawning and coordination.
Automatically decides single/team/swarm mode and manages the full orchestration lifecycle.
"""

import logging
import operator
import asyncio
from typing import Any, Dict, List, Optional, TypedDict, Annotated
from datetime import datetime

from langgraph.graph import StateGraph, END
from langchain_core.language_models import BaseChatModel

from open_notebook.agents.orchestration_decision import OrchestrationDecisionEngine
from open_notebook.agents.team_spawner import TeamSpawner
from open_notebook.agents.execution_scheduler import ExecutionScheduler
from open_notebook.agents.handover_coordinator import HandoverCoordinator
from open_notebook.agents.agent_manager import AgentManager
from open_notebook.agents.a2a.team_message_bus import A2ATeamMessageBusFactory
from open_notebook.agents.task_manager import TaskManager
from open_notebook.config import get_default_model
from api.services.goal_analysis_service import GoalAnalysisService
from api.services.plan_generation_service import PlanGenerationService

logger = logging.getLogger(__name__)


def merge_dicts(a: Dict, b: Dict) -> Dict:
    """Merge two dicts (for use in Annotated reducer)."""
    result = {**a}
    result.update(b)
    return result


class OrchestratorState(TypedDict):
    """State for autonomous orchestrator."""
    # Input
    goal: str
    user_id: str
    notebook_id: Optional[str]
    resources: Optional[Dict[str, Any]]  # Available resources (tools, sources, etc.)

    # Analysis
    complexity: str  # simple, moderate, complex
    intent: str
    required_capabilities: List[str]

    # Planning
    orchestration_mode: str  # single, team, swarm
    execution_plan: Optional[Dict[str, Any]]
    parallel_groups: List[List[str]]

    # Team Management
    team_id: Optional[str]
    team_name: Optional[str]
    message_bus_id: Optional[str]
    spawned_agents: List[Dict[str, Any]]
    _temp_notebook_id: Optional[str]  # Temporary notebook for ad-hoc sources
    is_template_execution: bool  # Flag to prevent workspace cleanup during template execution

    # Execution
    current_phase: str
    completed_tasks: Annotated[List[str], operator.add]
    task_results: Annotated[Dict[str, Any], merge_dicts]
    agent_messages: Annotated[List[Dict], operator.add]
    combined_output: Optional[str]

    # Output
    final_result: Optional[Dict[str, Any]]
    status: str  # analyzing, planning, spawning, executing, synthesizing, completed
    error: Optional[str]


class AutonomousOrchestrator:
    """
    LangGraph-based autonomous orchestrator.

    Coordinates the full lifecycle:
    1. Analyze goal (complexity, intent, capabilities)
    2. Decide orchestration mode (single, team, swarm)
    3. Spawn team (if needed)
    4. Plan execution (task decomposition, dependencies)
    5. Execute tasks (parallel/sequential with handovers)
    6. Synthesize results
    """

    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        agent_manager: Optional[AgentManager] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        event_callback: Optional[callable] = None,
        model_name: Optional[str] = None
    ):
        """
        Initialize autonomous orchestrator.

        Args:
            llm: Language model for decisions
            agent_manager: Agent manager instance
            base_url: LLM API base URL
            api_key: LLM API key
            event_callback: Optional async callback for emitting events (event_type, data)
            model_name: Optional model name override
        """
        self.llm = llm or get_default_model()
        self.agent_manager = agent_manager or AgentManager(
            base_url=base_url,
            api_key=api_key
        )
        self.base_url = base_url
        self.api_key = api_key
        self.event_callback = event_callback
        self.model_name = model_name or (self.llm.model_name if hasattr(self.llm, 'model_name') else "gpt-4")

        # Initialize services
        # Note: GoalAnalysisService and PlanGenerationService get their own LLM config
        # OrchestrationDecisionEngine accepts llm parameter
        self.goal_analysis_service = GoalAnalysisService()
        self.decision_engine = OrchestrationDecisionEngine(llm=self.llm)
        self.plan_generation_service = PlanGenerationService()
        self.team_spawner = TeamSpawner(agent_manager=self.agent_manager)
        self.execution_scheduler = ExecutionScheduler()

        # Build LangGraph
        self.graph = self._build_graph()

    async def _emit_event(self, event_type: str, data: Dict[str, Any]):
        """Emit an event if callback is configured."""
        if self.event_callback:
            try:
                await self.event_callback(event_type, data)
            except Exception as e:
                logger.error(f"Event emission failed for {event_type}: {e}")

        # Execute event-triggered actions
        if hasattr(self, 'orchestration_id') and self.orchestration_id:
            await self._trigger_event_actions(
                orchestration_id=self.orchestration_id,
                event_type=event_type,
                event_data=data
            )

    def _build_graph(self) -> StateGraph:
        """Build LangGraph orchestration workflow."""
        workflow = StateGraph(OrchestratorState)

        # Add nodes
        workflow.add_node("analyze_goal", self._analyze_goal)
        workflow.add_node("decide_orchestration", self._decide_orchestration)
        workflow.add_node("execute_single", self._execute_single)
        workflow.add_node("spawn_team", self._spawn_team)
        workflow.add_node("plan_execution", self._plan_execution)
        workflow.add_node("execute_team", self._execute_team)
        workflow.add_node("synthesize_results", self._synthesize_results)

        # Set entry point
        workflow.set_entry_point("analyze_goal")

        # Add edges
        workflow.add_edge("analyze_goal", "decide_orchestration")

        # Add conditional routing from decision
        workflow.add_conditional_edges(
            "decide_orchestration",
            self._route_orchestration,
            {
                "single": "execute_single",
                "team": "spawn_team",
                "swarm": "spawn_team",  # Same path as team, just larger
            }
        )

        # Single agent path
        workflow.add_edge("execute_single", "synthesize_results")

        # Team/swarm path
        workflow.add_edge("spawn_team", "plan_execution")
        workflow.add_edge("plan_execution", "execute_team")
        workflow.add_edge("execute_team", "synthesize_results")

        # Exit
        workflow.add_edge("synthesize_results", END)

        return workflow.compile()

    async def execute(
        self,
        goal: str,
        user_id: str,
        notebook_id: Optional[str] = None,
        resources: Optional[Dict[str, Any]] = None,
        is_template_execution: bool = False  # NEW: Flag to prevent workspace cleanup
    ) -> Dict[str, Any]:
        """
        Execute autonomous orchestration.

        Args:
            goal: User's goal
            user_id: User ID
            notebook_id: Notebook ID (optional)
            resources: Available resources (tools, sources, etc.)
            is_template_execution: If True, treat notebook_id as existing workspace (don't cleanup)

        Returns:
            Orchestration result
        """
        logger.info(f"Starting autonomous orchestration for goal: {goal}")
        print(f"\n{'='*80}")
        print(f"🎬 ORCHESTRATOR.execute() CALLED")
        print(f"{'='*80}")
        print(f"  goal: {goal[:50]}...")
        print(f"  user_id: {user_id}")
        print(f"  notebook_id: {notebook_id}")
        print(f"  resources PARAMETER: {resources}")
        print(f"  resources type: {type(resources)}")
        print(f"{'='*80}\n")
        logger.info(f"Orchestration context - notebook_id: {notebook_id}, resources: {resources}")

        # Initialize state
        initial_state = {
            "goal": goal,
            "user_id": user_id,
            "notebook_id": notebook_id,
            "resources": resources or {},  # Add resources to state!
            "complexity": "",
            "intent": "",
            "required_capabilities": [],
            "orchestration_mode": "",
            "execution_plan": None,
            "parallel_groups": [],
            "team_id": None,
            "spawned_agents": [],
            "current_phase": "initializing",
            "completed_tasks": [],
            "task_results": {},
            "agent_messages": [],
            "final_result": None,
            "status": "started",
            "error": None,
            "is_template_execution": is_template_execution  # NEW: Track if this is template execution
        }

        # Execute graph
        final_state = None
        try:
            final_state = await self.graph.ainvoke(initial_state)

            # Cleanup temporary notebook if created (ONLY if not template execution)
            if not is_template_execution:
                temp_notebook_id = final_state.get("_temp_notebook_id")
                if temp_notebook_id:
                    logger.warning(f"⚠️  CLEANUP TRIGGERED: temp_notebook_id={temp_notebook_id}, is_template_execution={is_template_execution}")
                    logger.warning(f"⚠️  This workspace WILL BE DELETED: {temp_notebook_id}")
                    try:
                        from open_notebook.domain.notebook import Notebook
                        logger.info(f"Cleaning up temporary notebook: {temp_notebook_id}")
                        temp_notebook = await Notebook.get(temp_notebook_id)
                        if temp_notebook:
                            logger.warning(f"🗑️  DELETING WORKSPACE: {temp_notebook.name} (ID: {temp_notebook.id})")
                            await temp_notebook.delete()
                            logger.info(f"Deleted temporary notebook: {temp_notebook_id}")
                    except Exception as cleanup_error:
                        logger.warning(f"Failed to cleanup temporary notebook {temp_notebook_id}: {cleanup_error}")
            else:
                logger.info(f"✅ Template execution mode: SKIPPING workspace cleanup (notebook_id={notebook_id})")
                if "_temp_notebook_id" in final_state:
                    logger.warning(f"⚠️  Note: _temp_notebook_id was set to {final_state['_temp_notebook_id']} but NOT cleaning up due to template execution flag")

            return {
                "success": True,
                "result": final_state.get("final_result"),
                "orchestration_mode": final_state.get("orchestration_mode"),
                "team_id": final_state.get("team_id"),
                "task_results": final_state.get("task_results"),
                "status": final_state.get("status")
            }
        except Exception as e:
            logger.error(f"Orchestration failed: {e}")

            # Cleanup temporary notebook even on failure (ONLY if not template execution)
            if not is_template_execution:
                # Try to get temp_notebook_id from final_state if it exists, otherwise from initial_state
                temp_notebook_id = None
                if final_state and "_temp_notebook_id" in final_state:
                    temp_notebook_id = final_state.get("_temp_notebook_id")
                elif "_temp_notebook_id" in initial_state:
                    temp_notebook_id = initial_state.get("_temp_notebook_id")

                if temp_notebook_id:
                    try:
                        from open_notebook.domain.notebook import Notebook
                        logger.info(f"Cleaning up temporary notebook after error: {temp_notebook_id}")
                        temp_notebook = await Notebook.get(temp_notebook_id)
                        if temp_notebook:
                            await temp_notebook.delete()
                    except Exception as cleanup_error:
                        logger.warning(f"Failed to cleanup temporary notebook: {cleanup_error}")

            return {
                "success": False,
                "error": str(e),
                "status": "failed"
            }

    async def execute_from_plan(
        self,
        workspace_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Execute workspace with existing plan (skip goal analysis).

        This method is used for template-based orchestration where the workspace
        and plan already exist. It skips the analyze_goal, decide_orchestration,
        and plan_execution nodes, going directly to team spawning and execution.

        Args:
            workspace_id: Workspace (notebook) ID with existing plan.
            user_id: User ID.

        Returns:
            Orchestration result.

        Raises:
            ValueError: If workspace or plan not found.
        """
        from open_notebook.domain.guided_workspace import WorkspacePlan
        from open_notebook.database.repository import repo_query

        logger.info(f"Executing from existing plan for workspace {workspace_id}")

        # Load workspace plan
        results = await repo_query(
            "SELECT * FROM workspace_plans WHERE workspace_id = :workspace_id",
            {"workspace_id": workspace_id},
            fetch_one=True
        )

        if not results:
            raise ValueError(f"No workspace plan found for workspace {workspace_id}")

        plan_record = dict(results)
        workspace_plan = WorkspacePlan(**plan_record)

        # Get plan phases and collaboration graph
        phases = workspace_plan.get_phases()
        collaboration_graph = workspace_plan.get_collaboration_graph()

        logger.info(f"Loaded plan with {len(phases)} phases")

        # Build initial state with plan pre-loaded
        initial_state = {
            "goal": workspace_plan.goal,
            "user_id": user_id,
            "notebook_id": workspace_id,
            "resources": {},
            "complexity": "moderate",  # Assume moderate since plan exists
            "intent": "execute_plan",
            "required_capabilities": [],
            "orchestration_mode": "team",  # Use team mode for plan execution
            "execution_plan": {"phases": phases},
            "parallel_groups": [],
            "team_id": None,
            "spawned_agents": [],
            "current_phase": "executing",
            "completed_tasks": [],
            "task_results": {},
            "agent_messages": [],
            "combined_output": None,
            "final_result": None,
            "status": "started",
            "error": None
        }

        # Execute directly: spawn_team → execute_team → synthesize_results
        try:
            # Spawn team
            logger.info("Spawning team from plan...")
            state = await self._spawn_team(initial_state)
            initial_state.update(state)

            # Skip plan_execution (already have plan)
            logger.info("Executing team...")
            state = await self._execute_team(initial_state)
            initial_state.update(state)

            # Synthesize results
            logger.info("Synthesizing results...")
            state = await self._synthesize_results(initial_state)
            initial_state.update(state)

            # Cleanup temporary notebook if created
            temp_notebook_id = initial_state.get("_temp_notebook_id")
            if temp_notebook_id:
                try:
                    from open_notebook.domain.notebook import Notebook
                    logger.info(f"Cleaning up temporary notebook: {temp_notebook_id}")
                    temp_notebook = await Notebook.get(temp_notebook_id)
                    if temp_notebook:
                        await temp_notebook.delete()
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup temporary notebook: {cleanup_error}")

            return {
                "success": True,
                "result": initial_state.get("final_result"),
                "orchestration_mode": initial_state.get("orchestration_mode"),
                "team_id": initial_state.get("team_id"),
                "task_results": initial_state.get("task_results"),
                "status": initial_state.get("status"),
                "workspace_id": workspace_id
            }

        except Exception as e:
            logger.error(f"Execution from plan failed: {e}", exc_info=True)

            # Cleanup temporary notebook on failure
            temp_notebook_id = initial_state.get("_temp_notebook_id")
            if temp_notebook_id:
                try:
                    from open_notebook.domain.notebook import Notebook
                    temp_notebook = await Notebook.get(temp_notebook_id)
                    if temp_notebook:
                        await temp_notebook.delete()
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup temporary notebook: {cleanup_error}")

            return {
                "success": False,
                "error": str(e),
                "status": "failed",
                "workspace_id": workspace_id
            }

    async def _analyze_goal(self, state: OrchestratorState) -> Dict[str, Any]:
        """Analyze goal to determine complexity and requirements."""
        print(f"\n{'='*80}\n📊 NODE: _analyze_goal CALLED\n{'='*80}")
        print(f"  State at entry - resources: {state.get('resources')}")
        logger.info("Analyzing goal...")

        try:
            analysis = await self.goal_analysis_service.analyze_goal(
                goal=state["goal"],
                context={"notebook_id": state.get("notebook_id")}
            )

            return {
                "complexity": analysis.get("complexity", "moderate"),
                "intent": analysis.get("intent", "general"),
                "required_capabilities": analysis.get("requirements", []),
                "status": "analyzing_complete"
            }
        except Exception as e:
            logger.error(f"Goal analysis failed: {e}")
            # Fallback to moderate complexity
            return {
                "complexity": "moderate",
                "intent": "general",
                "required_capabilities": [],
                "status": "analyzing_failed",
                "error": str(e)
            }

    async def _decide_orchestration(self, state: OrchestratorState) -> Dict[str, Any]:
        """Decide orchestration mode."""
        print(f"\n{'='*80}\n🎯 NODE: _decide_orchestration CALLED\n{'='*80}")
        print(f"  State at entry - resources: {state.get('resources')}")
        logger.info("Deciding orchestration mode...")

        try:
            decision = await self.decision_engine.decide(
                goal=state["goal"],
                complexity=state["complexity"],
                intent=state["intent"],
                capabilities=state["required_capabilities"],
                resources={}
            )

            logger.info(f"Decision: {decision.mode} with {decision.team_size} agents")

            return {
                "orchestration_mode": decision.mode,
                "spawned_agents": [{"role": role} for role in decision.roles],
                "status": "decision_made"
            }
        except Exception as e:
            logger.error(f"Decision failed: {e}")
            # Fallback to single agent
            return {
                "orchestration_mode": "single",
                "spawned_agents": [{"role": "analyst"}],
                "status": "decision_failed",
                "error": str(e)
            }

    def _route_orchestration(self, state: OrchestratorState) -> str:
        """Route to appropriate execution path."""
        mode = state.get("orchestration_mode", "single")
        logger.info(f"Routing to {mode} execution path")
        return mode

    async def _execute_single(self, state: OrchestratorState) -> Dict[str, Any]:
        """Execute single agent using DataQueryAgent."""
        print(f"\n{'='*80}\n🚀 _execute_single CALLED\n{'='*80}")
        logger.info("Executing single agent with DataQueryAgent...")

        # Emit start event
        await self._emit_event("orchestration.executing", {
            "mode": "single",
            "timestamp": datetime.utcnow().isoformat()
        })

        try:
            from open_notebook.agents.data_query_agent import DataQueryAgent
            from api.services.tool_factory import get_tool_factory
            from open_notebook.domain.notebook import Notebook

            # Get notebook for tool creation
            notebook_id = state.get("notebook_id")
            resources = state.get("resources", {})
            user_id = state.get("user_id", "default")

            print(f"\n🔍 DEBUG _execute_single:")
            print(f"  notebook_id: {notebook_id}")
            print(f"  user_id: {user_id}")
            print(f"  resources: {resources}")
            print(f"  resources type: {type(resources)}")

            notebook = None
            if notebook_id:
                try:
                    notebook = await Notebook.get(notebook_id)
                except:
                    logger.warning(f"Could not load notebook {notebook_id}")

            # Create tools for this execution
            factory = get_tool_factory()

            tools = []
            temp_notebook_id = None

            # Option 1: Load tools from notebook
            if notebook_id:
                print(f"✅ Taking Option 1: notebook_id path")
                tools = await factory.create_tools_for_session(
                    notebook_id=notebook_id,
                    user_id=user_id,
                    session_id=None
                )
            # Option 2: Load tools for directly attached sources
            elif resources and "source_ids" in resources and resources["source_ids"]:
                # CRITICAL: Don't create temp notebooks during template execution
                if state.get("is_template_execution"):
                    logger.warning("Template execution: skipping temp notebook creation for source_ids")
                    print(f"⚠️  Template execution mode: NOT creating temp notebook for sources")
                    tools = []  # No tools for template execution with source_ids
                else:
                    print(f"✅ Taking Option 2: resources.source_ids path")
                import uuid
                from open_notebook.database.repository import repo_execute

                source_ids = resources["source_ids"]
                print(f"  source_ids: {source_ids}")
                print(f"  source_ids count: {len(source_ids)}")
                logger.info(f"Creating temporary notebook for {len(source_ids)} directly attached sources")

                try:
                    # Create a temporary notebook to hold the sources
                    print(f"  Creating temporary notebook...")
                    temp_notebook = Notebook(
                        name="Orchestration Temporary Context",
                        description="Temporary notebook for orchestration with attached sources",
                        user_id=user_id,
                        archived=False
                    )
                    print(f"  Created Notebook object, calling save()...")
                    await temp_notebook.save()
                    temp_notebook_id = temp_notebook.id  # Get the generated ID
                    print(f"  ✅ Notebook saved with ID: {temp_notebook_id}")

                    # Link sources to temporary notebook
                    for source_id in source_ids:
                        print(f"  Linking source {source_id} to temp notebook...")
                        await repo_execute(
                            "INSERT OR IGNORE INTO notebook_source (notebook_id, source_id) VALUES (:notebook_id, :source_id)",
                            {"notebook_id": temp_notebook_id, "source_id": source_id}
                        )
                        print(f"  ✅ Source linked!")

                    # Now create tools using the temporary notebook
                    print(f"  Calling create_tools_for_session with temp notebook...")
                    tools = await factory.create_tools_for_session(
                        notebook_id=temp_notebook_id,
                        user_id=user_id,
                        session_id=None
                    )
                    print(f"  ✅ Got {len(tools)} tools back!")

                    # Store temp notebook ID in state for cleanup
                    state["_temp_notebook_id"] = temp_notebook_id

                    logger.info(f"Created {len(tools)} tools from {len(source_ids)} attached sources")

                except Exception as e:
                    print(f"  ❌ EXCEPTION in temp notebook creation: {e}")
                    print(f"  Exception type: {type(e)}")
                    import traceback
                    traceback.print_exc()
                    logger.error(f"Failed to create tools from attached sources: {e}", exc_info=True)
            else:
                print(f"❌ No option matched!")
                print(f"  notebook_id is None: {notebook_id is None}")
                print(f"  resources is truthy: {bool(resources)}")
                print(f"  'source_ids' in resources: {'source_ids' in resources if resources else 'N/A'}")
                print(f"  resources.get('source_ids'): {resources.get('source_ids') if resources else 'N/A'}")

            logger.info(f"Created {len(tools)} tools for execution")

            # Emit tools loaded event
            await self._emit_event("tools.loaded", {
                "tools_count": len(tools),
                "tool_names": [t.name for t in tools] if tools else [],
                "timestamp": datetime.utcnow().isoformat()
            })

            # Create agent with goal as system message
            system_message = f"""You are an autonomous AI agent executing the following goal:

Goal: {state['goal']}

Use the available tools to accomplish this goal. Be thorough and provide detailed results."""

            agent = DataQueryAgent(
                model_name=self.model_name,
                notebook_id=notebook_id or "autonomous",
                tools=tools,
                session_id=None,
                system_message=system_message,
                capture_tool_results=True,
                api_key=self.api_key,
                base_url=self.base_url,
            )

            # Emit agent created event
            await self._emit_event("agent.ready", {
                "agent_type": "single",
                "model": self.llm.model_name if hasattr(self.llm, 'model_name') else "gpt-4",
                "timestamp": datetime.utcnow().isoformat()
            })

            # Execute the goal
            logger.info(f"Invoking agent with goal: {state['goal']}")
            response = await agent.invoke(
                user_message=state['goal'],
                chat_history=[]
            )

            logger.info(f"Agent execution complete. Response length: {len(response)}")

            # Extract tool results if available
            tool_data = []
            if hasattr(agent, 'tool_results') and agent.tool_results:
                tool_data = agent.tool_results
                logger.info(f"Captured {len(tool_data)} tool results")

            # Emit completion event
            await self._emit_event("task.completed", {
                "task_id": "single_agent",
                "output_length": len(response),
                "tools_used": len(tool_data),
                "timestamp": datetime.utcnow().isoformat()
            })

            result = {
                "output": response,
                "tool_results": tool_data,
                "tools_used": len(tools),
                "status": "completed"
            }

            return {
                "task_results": {"single_agent": result},
                "final_result": result,
                "status": "completed"
            }
        except Exception as e:
            logger.error(f"Single execution failed: {e}", exc_info=True)

            # Emit error event
            await self._emit_event("orchestration.error", {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })

            return {
                "status": "failed",
                "error": str(e),
                "task_results": {}
            }

    async def _spawn_team(self, state: OrchestratorState) -> Dict[str, Any]:
        """Spawn agent team using TeamSpawner."""
        print(f"\n{'='*80}\n👥 NODE: _spawn_team CALLED\n{'='*80}")
        print(f"  State at entry - resources: {state.get('resources')}")
        logger.info(f"Spawning agent team...")

        try:
            from open_notebook.agents.team_spawner import TeamSpawner
            from api.services.tool_factory import get_tool_factory

            mode = state.get("orchestration_mode", "team")
            spawned_agents_config = state.get("spawned_agents", [])

            # Extract roles from spawned_agents config
            roles = [agent.get("role") for agent in spawned_agents_config if agent.get("role")]

            if not roles:
                # Fallback roles based on mode
                if mode == "swarm":
                    roles = ["planner", "researcher", "analyst", "data_specialist", "synthesizer"]
                elif mode == "team":
                    roles = ["planner", "researcher", "analyst"]
                else:
                    roles = ["analyst"]

            logger.info(f"Spawning {len(roles)} agents with roles: {roles}")

            # Prepare resources for team
            notebook_id = state.get("notebook_id")
            user_id = state.get("user_id", "default")
            resources_param = state.get("resources", {})

            # Get available tools
            factory = get_tool_factory()
            tools = []

            if notebook_id:
                tools = await factory.create_tools_for_session(
                    notebook_id=notebook_id,
                    user_id=user_id,
                    session_id=None
                )
            elif resources_param and "source_ids" in resources_param:
                # CRITICAL: Don't create temp notebooks during template execution
                if state.get("is_template_execution"):
                    logger.warning("Template execution: skipping temp notebook creation in _plan_execution")
                    tools = []  # No tools for template execution
                else:
                    # Create temp notebook for direct sources (same as _execute_team)
                    from open_notebook.domain.notebook import Notebook
                    from open_notebook.database.repository import repo_execute

                    source_ids = resources_param["source_ids"]
                    temp_notebook = Notebook(
                        name="Orchestration Temporary Context",
                        description="Temporary notebook for orchestration with attached sources",
                        user_id=user_id,
                        archived=False
                    )
                    await temp_notebook.save()
                    temp_notebook_id = temp_notebook.id

                    for source_id in source_ids:
                        await repo_execute(
                            "INSERT INTO notebook_source (notebook_id, source_id, created) VALUES (:notebook_id, :source_id, :created)",
                            {
                                "notebook_id": temp_notebook_id,
                                "source_id": source_id,
                                "created": datetime.utcnow().isoformat()
                            }
                        )

                    tools = await factory.create_tools_for_session(
                        notebook_id=temp_notebook_id,
                        user_id=user_id,
                        session_id=None
                    )

                    # Store temp notebook for cleanup
                    state["_temp_notebook_id"] = temp_notebook_id
                    notebook_id = temp_notebook_id

            # Prepare resources dict for TeamSpawner
            team_resources = {
                "tools": [{"id": t.name, "name": t.name} for t in tools],
                "notebook_id": notebook_id,
            }

            # Spawn team
            spawner = TeamSpawner(
                base_url=self.base_url,
                api_key=self.api_key
            )

            team_info = await spawner.spawn_team(
                goal=state["goal"],
                roles=roles,
                resources=team_resources,
                config={"default_model": self.model_name},
                user_id=user_id,
                notebook_id=notebook_id
            )

            logger.info(f"Team spawned successfully: {team_info['team_id']} with {len(team_info['agents'])} agents")

            # Emit agent spawned events for each real agent
            for agent in team_info["agents"]:
                await self._emit_event("agent.spawned", {
                    "agent_id": agent["id"],
                    "agent_name": agent["name"],
                    "agent_role": agent["role"],
                    "model": agent["model"],
                    "tools_count": len(agent.get("tools", [])),
                    "timestamp": datetime.utcnow().isoformat()
                })

            # Store temp notebook in state for _execute_team
            temp_notebook_for_execution = state.get("_temp_notebook_id", notebook_id)

            return {
                "team_id": team_info["team_id"],
                "team_name": team_info["team_name"],
                "spawned_agents": team_info["agents"],
                "message_bus_id": team_info["message_bus_id"],
                "_temp_notebook_id": temp_notebook_for_execution,  # Pass to execute_team
                "status": "team_ready"
            }

        except Exception as e:
            logger.error(f"Team spawning failed: {e}", exc_info=True)

            # Fallback to simple team ID
            import uuid
            team_id = str(uuid.uuid4())[:8]

            return {
                "team_id": team_id,
                "status": "team_fallback",
                "error": str(e)
            }

    async def _plan_execution(self, state: OrchestratorState) -> Dict[str, Any]:
        """Plan task execution - simplified."""
        print(f"\n{'='*80}\n📋 NODE: _plan_execution CALLED\n{'='*80}")
        print(f"  State at entry - resources: {state.get('resources')}")
        logger.info("Planning execution...")

        # Create a simple execution plan based on the goal
        # For now, just create one main task
        plan = {
            "phases": [{
                "name": "Execute",
                "tasks": [{
                    "id": "main_task",
                    "description": state["goal"]
                }]
            }]
        }

        logger.info(f"Created simple plan with 1 task")

        return {
            "execution_plan": plan,
            "status": "plan_generated"
        }

    async def _execute_team(self, state: OrchestratorState) -> Dict[str, Any]:
        """Execute team with spawned agents - use DataQueryAgent with tools."""
        print("=" * 80)
        print("🚀 _execute_team CALLED!")
        print("=" * 80)
        logger.info("Executing team with spawned agents...")

        # Emit start event
        await self._emit_event("orchestration.executing", {
            "mode": state.get("orchestration_mode", "team"),
            "timestamp": datetime.utcnow().isoformat()
        })

        try:
            from open_notebook.agents.data_query_agent import DataQueryAgent
            from api.services.tool_factory import get_tool_factory
            import asyncio

            # Get execution plan
            execution_plan = state.get("execution_plan", {})
            phases = execution_plan.get("phases", [])

            if not phases:
                # Fallback: Create a simple plan by decomposing the goal
                logger.warning("No execution plan found, creating simple decomposition")
                phases = [{
                    "name": "Execute",
                    "tasks": [{"id": "main_task", "description": state["goal"]}]
                }]

            # Get spawned agents from state
            spawned_agents = state.get("spawned_agents", [])
            team_id = state.get("team_id")

            if not spawned_agents or not team_id:
                logger.warning("No agents spawned, falling back to single agent execution")
                return await self._execute_single(state)

            # Get tools (either from notebook or directly attached sources)
            notebook_id = state.get("_temp_notebook_id") or state.get("notebook_id")
            user_id = state.get("user_id", "default")

            # Get tools for the notebook
            factory = get_tool_factory()
            tools = []

            if notebook_id:
                tools = await factory.create_tools_for_session(
                    notebook_id=notebook_id,
                    user_id=user_id,
                    session_id=None
                )

            logger.info(f"Team execution with {len(spawned_agents)} agents and {len(tools)} tools")

            # Execute tasks (for simplicity, assign tasks round-robin to agents)
            task_results = {}
            all_outputs = []
            agent_idx = 0

            for phase_idx, phase in enumerate(phases):
                phase_name = phase.get("name", f"Phase {phase_idx + 1}")
                tasks = phase.get("tasks", [])

                logger.info(f"Executing phase: {phase_name} with {len(tasks)} tasks")

                # Emit phase start event
                await self._emit_event("phase.started", {
                    "phase_name": phase_name,
                    "phase_index": phase_idx,
                    "task_count": len(tasks),
                    "timestamp": datetime.utcnow().isoformat()
                })

                for task in tasks:
                    task_id = task.get("id", f"task_{len(task_results)}")
                    task_desc = task.get("description", "")

                    # Select agent (round-robin)
                    agent_info = spawned_agents[agent_idx % len(spawned_agents)]
                    agent_idx += 1

                    logger.info(f"Assigning task {task_id} to agent {agent_info['name']} ({agent_info['role']})")

                    # Emit task start event
                    await self._emit_event("task.assigned", {
                        "task_id": task_id,
                        "task_description": task_desc[:200],
                        "agent_id": agent_info["id"],
                        "agent_name": agent_info["name"],
                        "agent_role": agent_info["role"],
                        "phase": phase_name,
                        "timestamp": datetime.utcnow().isoformat()
                    })

                    await self._emit_event("task.started", {
                        "task_id": task_id,
                        "agent_id": agent_info["id"],
                        "timestamp": datetime.utcnow().isoformat()
                    })

                    # Execute task with DataQueryAgent (has tool support)
                    try:
                        # Create system message for this agent role
                        system_message = f"""You are a {agent_info['role']} agent in a multi-agent team working on: {state['goal']}

Your specific role: {agent_info['role']}
Your task: {task_desc}

Use the available tools to complete this task. DO NOT just describe what you would do - actually execute the tools and provide results.

CRITICAL: Format your response in clean HTML using these tags:
- <h3>, <h4> for headings
- <p> for paragraphs
- <ul>, <ol>, <li> for lists
- <table>, <tr>, <th>, <td> for tables (with proper styling)
- <strong> for emphasis, <em> for italics
- Use proper line breaks with <br> instead of \\n

Your entire response must be valid HTML that can be rendered directly in a browser."""

                        # Create DataQueryAgent with tools
                        agent = DataQueryAgent(
                            model_name=self.model_name,
                            notebook_id=notebook_id or "autonomous",
                            tools=tools,
                            session_id=None,
                            system_message=system_message,
                            capture_tool_results=True,
                            api_key=self.api_key,
                            base_url=self.base_url,
                        )

                        # Execute task
                        response = await agent.invoke(
                            user_message=task_desc,
                            chat_history=[]
                        )

                        tool_data = []
                        if hasattr(agent, 'tool_results') and agent.tool_results:
                            tool_data = agent.tool_results

                        task_results[task_id] = {
                            "output": response,
                            "tool_results": tool_data,
                            "status": "completed",
                            "phase": phase_name,
                            "agent_id": agent_info["id"],
                            "agent_name": agent_info["name"]
                        }

                        all_outputs.append(f"**{phase_name} - {agent_info['name']}:**\n{response}\n")

                        logger.info(f"Task {task_id} completed by {agent_info['name']}")

                        # Save task result as note in execution folder (if folder_id provided)
                        execution_folder_id = state.get("resources", {}).get("execution_folder_id")
                        if execution_folder_id and notebook_id:
                            try:
                                from open_notebook.domain.notebook import Note, Notebook
                                import uuid
                                import markdown

                                task_name = task.get("name", task.get("description", "Task"))
                                note_id = str(uuid.uuid4())

                                # Process response - convert to proper HTML
                                cleaned_response = response

                                # If response looks like it has markdown or plain text, convert it
                                if not cleaned_response.strip().startswith('<html') and not '<table' in cleaned_response[:100]:
                                    # Try to parse as markdown
                                    try:
                                        cleaned_response = markdown.markdown(
                                            cleaned_response,
                                            extensions=['tables', 'fenced_code', 'nl2br']
                                        )
                                    except Exception as md_error:
                                        logger.warning(f"Markdown conversion failed: {md_error}")
                                        # Fallback: just wrap in <pre> for plain text
                                        cleaned_response = f'<pre style="white-space: pre-wrap; word-wrap: break-word;">{cleaned_response}</pre>'

                                # Format task result as HTML
                                note_content = f"""<h2>{task_name}</h2>
<p><strong>Status:</strong> ✅ Completed<br>
<strong>Phase:</strong> {phase_name}<br>
<strong>Executed By:</strong> {agent_info['name']} ({agent_info['role']})</p>

{cleaned_response}

<hr>
<p><em>Completed by {agent_info['name']} on {datetime.utcnow().strftime('%Y-%m-%d at %H:%M UTC')}</em></p>
"""

                                note = Note(
                                    notebook_id=notebook_id,
                                    folder_id=execution_folder_id,
                                    title=f"✅ {task_name}",
                                    content=note_content,
                                    content_html=note_content,
                                    metadata=""
                                )
                                await note.save()

                                # Link note to workspace
                                workspace = await Notebook.get(notebook_id)
                                if workspace:
                                    await workspace.add_note(note.id)
                                    logger.info(f"Saved task result note {note_id} in execution folder {execution_folder_id}")

                            except Exception as note_error:
                                logger.error(f"Failed to save task result as note: {note_error}")
                                # Continue execution even if note save fails

                        # Emit task completed event
                        await self._emit_event("task.completed", {
                            "task_id": task_id,
                            "agent_id": agent_info["id"],
                            "output_length": len(response),
                            "tools_used": len(tool_data),
                            "status": "completed",
                            "timestamp": datetime.utcnow().isoformat()
                        })

                    except Exception as e:
                        logger.error(f"Task {task_id} failed: {e}", exc_info=True)

                        task_results[task_id] = {
                            "output": f"Error: {str(e)}",
                            "status": "failed",
                            "phase": phase_name,
                            "error": str(e)
                        }

                        # Emit task error event
                        await self._emit_event("task.error", {
                            "task_id": task_id,
                            "error": str(e),
                            "timestamp": datetime.utcnow().isoformat()
                        })

                # Emit phase completed event
                await self._emit_event("phase.completed", {
                    "phase_name": phase_name,
                    "phase_index": phase_idx,
                    "timestamp": datetime.utcnow().isoformat()
                })

            # Combine outputs
            combined_output = "\n".join(all_outputs)

            result = {
                "output": combined_output,
                "task_results": task_results,
                "status": "completed",
                "agents_used": len(set(r.get("agent_id") for r in task_results.values() if r.get("agent_id"))),
                "tools_used": len(tools)
            }

            return {
                "task_results": task_results,
                "final_result": result,
                "status": "completed"
            }

        except Exception as e:
            logger.error(f"Team execution failed: {e}", exc_info=True)

            # Emit error event
            await self._emit_event("orchestration.error", {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })

            return {
                "status": "failed",
                "error": str(e),
                "task_results": {}
            }

    async def _synthesize_results(self, state: OrchestratorState) -> Dict[str, Any]:
        """Synthesize final results."""
        print(f"\n{'='*80}\n🔬 NODE: _synthesize_results CALLED\n{'='*80}")
        print(f"Task results keys: {list(state.get('task_results', {}).keys())}")
        print(f"Task results: {state.get('task_results', {})}")
        logger.info("Synthesizing results...")

        try:
            task_results = state.get("task_results", {})
            combined_output = state.get("combined_output", "")

            # Format results for synthesis
            formatted_results = []
            total_tool_results = 0

            for task_id, result in task_results.items():
                output = result.get("output", "")
                tool_results = result.get("tool_results", [])
                total_tool_results += len(tool_results)

                formatted_results.append({
                    "task_id": task_id,
                    "output": output,
                    "tools_used": len(tool_results),
                    "status": result.get("status", "unknown"),
                    "phase": result.get("phase", "unknown")
                })

            # Create final synthesis
            synthesis = {
                "goal": state["goal"],
                "orchestration_mode": state["orchestration_mode"],
                "task_count": len(task_results),
                "results": formatted_results,
                "combined_output": combined_output or self._combine_task_outputs(task_results),
                "total_tools_used": total_tool_results,
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat()
            }

            logger.info(f"Synthesis complete: {len(task_results)} tasks, {total_tool_results} tool calls")

            return {
                "final_result": synthesis,
                "status": "completed"
            }
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            return {
                "status": "synthesis_failed",
                "error": str(e)
            }

    def _combine_task_outputs(self, task_results: Dict[str, Any]) -> str:
        """Combine outputs from multiple tasks into a coherent result."""
        outputs = []
        for task_id, result in task_results.items():
            output = result.get("output", "")
            if output:
                phase = result.get("phase", "Task")
                outputs.append(f"**{phase} ({task_id}):**\n{output}\n")

        return "\n\n".join(outputs) if outputs else "No output generated"

    async def _trigger_event_actions(
        self,
        orchestration_id: str,
        event_type: str,
        event_data: Dict[str, Any]
    ):
        """
        Execute actions bound to this orchestration for specific events.

        Args:
            orchestration_id: Orchestration ID
            event_type: Event type that triggered this
            event_data: Event data
        """
        try:
            from open_notebook.database.repository import repo_query
            from api.services.action_executor import ActionExecutor

            # Map event types to trigger conditions
            trigger_map = {
                "orchestration.started": "on_start",
                "orchestration.completed": "on_completion",
                "orchestration.error": "on_failure",
                "analysis.completed": "on_phase_change",
                "decision.made": "on_phase_change",
                "team.spawned": "on_phase_change",
                "plan.generated": "on_phase_change",
                "execution.started": "on_phase_change",
                "synthesis.started": "on_phase_change",
            }

            trigger_condition = trigger_map.get(event_type)
            if not trigger_condition:
                return

            # Get active bindings for this orchestration
            sql = """
                SELECT ab.*, a.id as action_id
                FROM orchestration_action_bindings ab
                JOIN actions a ON ab.action_id = a.id
                WHERE ab.orchestration_id = :orchestration_id
                  AND ab.trigger_condition IN ('always', :trigger_condition)
                  AND ab.is_active = 1
                  AND a.is_active = 1
                ORDER BY ab.execution_order ASC
            """
            bindings = await repo_query(sql, {
                "orchestration_id": orchestration_id,
                "trigger_condition": trigger_condition
            })

            if not bindings:
                return

            logger.info(f"Executing {len(bindings)} bound actions for orchestration {orchestration_id}, event {event_type}")

            executor = ActionExecutor()

            for binding in bindings:
                try:
                    # Build context from orchestration state + event data
                    context = {
                        "event_type": event_type,
                        "event_data": event_data,
                        "orchestration_id": orchestration_id,
                        "goal": self.state.get("goal") if hasattr(self, 'state') else None,
                        "current_phase": self.state.get("current_phase") if hasattr(self, 'state') else None,
                        "progress": self.state.get("progress") if hasattr(self, 'state') else None,
                        "orchestration_mode": self.state.get("orchestration_mode") if hasattr(self, 'state') else None,
                    }

                    await executor.execute_action(
                        action_id=binding["action_id"],
                        context=context,
                        user_id=self.state.get("user_id") if hasattr(self, 'state') else "system",
                        orchestration_id=orchestration_id,
                        trigger_event=event_type
                    )

                except Exception as e:
                    logger.error(f"Failed to execute action {binding['action_id']}: {e}", exc_info=True)
                    # Continue with other actions even if one fails

        except Exception as e:
            logger.error(f"Failed to trigger event actions for {event_type}: {e}", exc_info=True)

    async def execute_template_phases(
        self,
        phases: List[Dict],
        workspace_id: str,
        user_id: str,
        parameters: Dict[str, Any],
        template: Any,
        execution_folder_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute resolved template phases within workspace context.

        Args:
            phases: Resolved phase definitions with parameter substitution
            workspace_id: Target workspace ID
            user_id: User ID
            parameters: Runtime parameter values
            template: WorkspaceTemplate instance

        Returns:
            {
                "status": "completed",
                "summary": str,
                "summary_html": str,
                "phases_completed": int,
                "phase_results": List[Dict]
            }
        """
        try:
            from open_notebook.domain.notebook import Notebook

            # Load workspace for context
            workspace = await Notebook.get(workspace_id)
            if not workspace:
                raise ValueError(f"Workspace {workspace_id} not found")

            # Resolve phases with parameter substitution
            resolved_phases = []
            context = {"workspace_id": workspace_id, "user_id": user_id}

            for phase in phases:
                resolved_phase = {
                    "name": template.resolve_placeholders(phase.get("name", ""), parameters, context),
                    "tasks": []
                }

                for task in phase.get("tasks", []):
                    resolved_task = {
                        "name": template.resolve_placeholders(task.get("name", ""), parameters, context),
                        "description": template.resolve_placeholders(task.get("description", ""), parameters, context),
                        "assigned_agent_id": task.get("assigned_agent_id"),
                        "estimated_duration": task.get("estimated_duration"),
                        "dependencies": task.get("dependencies", []),
                        "required_tools": task.get("required_tools", []),
                        "required_sources": task.get("required_sources", []),
                    }
                    resolved_phase["tasks"].append(resolved_task)

                resolved_phases.append(resolved_phase)

            # Build goal from phases
            goal = f"Execute template: {', '.join([p['name'] for p in resolved_phases])}"

            # Execute using orchestrator
            # IMPORTANT: Do NOT set _temp_notebook_id - this is an existing workspace, not temporary
            result = await self.execute(
                goal=goal,
                user_id=user_id,
                notebook_id=workspace_id,
                resources={
                    "sources": [],  # Sources from workspace
                    "notes": [],
                    "phases": resolved_phases,
                    "execution_folder_id": execution_folder_id  # Pass folder_id for task result organization
                },
                is_template_execution=True  # Flag to prevent workspace cleanup
            )

            # Generate summary
            if result.get("success"):
                summary = self._generate_execution_summary(resolved_phases, result)
                summary_html = self._generate_execution_summary_html(resolved_phases, result)

                return {
                    "status": "completed",
                    "summary": summary,
                    "summary_html": summary_html,
                    "phases_completed": len(resolved_phases),
                    "phase_results": result.get("task_results", {})
                }
            else:
                raise ValueError(f"Execution failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            logger.error(f"Template phase execution failed: {e}", exc_info=True)
            raise

    def _generate_execution_summary(self, phases: List[Dict], result: Dict) -> str:
        """Generate comprehensive text summary of execution with actual results."""
        lines = [f"# Template Execution Summary\n"]
        lines.append(f"**Execution Date**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append(f"**Phases Completed**: {len(phases)}\n")
        lines.append(f"**Orchestration Mode**: {result.get('orchestration_mode', 'N/A')}\n\n")

        # Include task results with actual outputs
        task_results = result.get("task_results", {})

        if task_results:
            lines.append("## Execution Results\n\n")

            for task_key, task_result in task_results.items():
                lines.append(f"### {task_key.replace('_', ' ').title()}\n\n")

                # Extract output from task result
                if isinstance(task_result, dict):
                    # Check for output field (from agent responses)
                    if "output" in task_result:
                        output = task_result["output"]
                        if isinstance(output, list):
                            # Handle list of output chunks (from streaming)
                            for chunk in output:
                                if isinstance(chunk, dict) and "text" in chunk:
                                    lines.append(f"{chunk['text']}\n\n")
                                else:
                                    lines.append(f"{chunk}\n\n")
                        else:
                            lines.append(f"{output}\n\n")

                    # Include tool results if available
                    if "tool_results" in task_result:
                        tool_results = task_result["tool_results"]
                        if tool_results:
                            lines.append("**Tools Used:**\n\n")
                            for tool_result in tool_results[:5]:  # Limit to first 5 tools
                                tool_name = tool_result.get("tool_name", "Unknown")
                                result_data = tool_result.get("result", {})

                                # Format result based on type
                                if isinstance(result_data, dict):
                                    if "result" in result_data:
                                        lines.append(f"- **{tool_name}**: {result_data['result']}\n")
                                    elif "success" in result_data:
                                        status = "✓" if result_data["success"] else "✗"
                                        lines.append(f"- **{tool_name}** {status}\n")
                                else:
                                    lines.append(f"- **{tool_name}**: {str(result_data)[:200]}\n")
                            lines.append("\n")
                else:
                    # Simple string result
                    lines.append(f"{task_result}\n\n")

        # Original phase breakdown
        lines.append("## Phase Breakdown\n\n")
        for i, phase in enumerate(phases, 1):
            lines.append(f"### Phase {i}: {phase['name']}\n")
            lines.append(f"- Tasks: {len(phase['tasks'])}\n")
            for task in phase['tasks']:
                lines.append(f"  - {task.get('name', 'Unnamed task')}\n")

        # Include final result if available
        if result.get("final_result"):
            final_output = result['final_result'].get('combined_output', '')
            if final_output:
                lines.append(f"\n## Summary\n\n{final_output}\n")

        return "\n".join(lines)

    def _generate_execution_summary_html(self, phases: List[Dict], result: Dict) -> str:
        """Generate comprehensive HTML summary of execution with actual results."""
        html = [
            "<h1>Template Execution Summary</h1>",
            f"<p><strong>Execution Date:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}</p>",
            f"<p><strong>Phases Completed:</strong> {len(phases)}</p>",
            f"<p><strong>Orchestration Mode:</strong> {result.get('orchestration_mode', 'N/A')}</p>"
        ]

        # Include task results with actual outputs
        task_results = result.get("task_results", {})

        if task_results:
            html.append("<h2>Execution Results</h2>")

            for task_key, task_result in task_results.items():
                html.append(f"<h3>{task_key.replace('_', ' ').title()}</h3>")

                # Extract output from task result
                if isinstance(task_result, dict):
                    # Check for output field
                    if "output" in task_result:
                        output = task_result["output"]
                        if isinstance(output, list):
                            html.append("<div class='execution-output'>")
                            for chunk in output:
                                if isinstance(chunk, dict) and "text" in chunk:
                                    # Convert markdown to HTML if needed
                                    text = chunk['text'].replace('\n', '<br>')
                                    html.append(f"<p>{text}</p>")
                                else:
                                    html.append(f"<p>{chunk}</p>")
                            html.append("</div>")
                        else:
                            html.append(f"<p>{output}</p>")

                    # Include tool results
                    if "tool_results" in task_result and task_result["tool_results"]:
                        html.append("<h4>Tools Used:</h4>")
                        html.append("<ul>")
                        for tool_result in task_result["tool_results"][:5]:
                            tool_name = tool_result.get("tool_name", "Unknown")
                            result_data = tool_result.get("result", {})

                            if isinstance(result_data, dict):
                                if "result" in result_data:
                                    html.append(f"<li><strong>{tool_name}:</strong> {result_data['result']}</li>")
                                elif "success" in result_data:
                                    status = "✓" if result_data["success"] else "✗"
                                    html.append(f"<li><strong>{tool_name}</strong> {status}</li>")
                            else:
                                html.append(f"<li><strong>{tool_name}:</strong> {str(result_data)[:200]}</li>")
                        html.append("</ul>")
                else:
                    html.append(f"<p>{task_result}</p>")

        # Phase breakdown
        html.append("<h2>Phase Breakdown</h2>")
        for i, phase in enumerate(phases, 1):
            html.append(f"<h3>Phase {i}: {phase['name']}</h3>")
            html.append(f"<ul><li>Tasks: {len(phase['tasks'])}</li></ul>")
            if phase['tasks']:
                html.append("<ul>")
                for task in phase['tasks']:
                    html.append(f"<li>{task.get('name', 'Unnamed task')}</li>")
                html.append("</ul>")

        # Include final result
        if result.get("final_result"):
            final_output = result['final_result'].get('combined_output', '')
            if final_output:
                html.append("<h2>Summary</h2>")
                html.append(f"<p>{final_output.replace(chr(10), '<br>')}</p>")

        return "\n".join(html)


# Convenience function
async def orchestrate(
    goal: str,
    user_id: str,
    notebook_id: Optional[str] = None,
    resources: Optional[Dict[str, Any]] = None,
    llm: Optional[BaseChatModel] = None
) -> Dict[str, Any]:
    """
    Convenience function for autonomous orchestration.

    Args:
        goal: User's goal
        user_id: User ID
        notebook_id: Notebook ID
        resources: Available resources
        llm: Language model

    Returns:
        Orchestration result
    """
    orchestrator = AutonomousOrchestrator(llm=llm)
    return await orchestrator.execute(goal, user_id, notebook_id, resources)
