"""
Agent Team Spawner

Automatically creates agent teams with appropriate roles, tools, and resources.
Integrates with A2A message bus for location-transparent communication.
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from open_notebook.agents.agent_manager import AgentManager, get_agent_class
from open_notebook.agents.a2a.team_message_bus import (
    A2ATeamMessageBus,
    A2ATeamMessageBusFactory
)
from open_notebook.domain.agent_team import AgentTeam, AgentInstance

logger = logging.getLogger(__name__)


class TeamSpawner:
    """
    Spawns agent teams based on requirements.

    Automatically:
    1. Creates AgentTeam
    2. Spawns agents with appropriate roles
    3. Configures agents with tools and resources
    4. Sets up A2A message bus for communication
    """

    def __init__(
        self,
        agent_manager: Optional[AgentManager] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        Initialize team spawner.

        Args:
            agent_manager: AgentManager instance (creates new if not provided)
            base_url: Base URL for LLM API
            api_key: API key for LLM
        """
        self.agent_manager = agent_manager or AgentManager(
            base_url=base_url,
            api_key=api_key
        )
        self.base_url = base_url
        self.api_key = api_key

    async def spawn_team(
        self,
        goal: str,
        roles: List[str],
        resources: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        notebook_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Spawn agent team with specified roles.

        Args:
            goal: Team goal/objective
            roles: List of agent roles to spawn
            resources: Available resources (tools, sources, etc.)
            config: Team configuration
            user_id: User ID for context
            notebook_id: Notebook ID for context

        Returns:
            Dict with team_id, agent_ids, message_bus_id, and spawned agent details
        """
        resources = resources or {}
        config = config or {}

        logger.info(f"Spawning team for goal: {goal}")
        logger.info(f"Roles: {roles}")

        # 1. Create agent team
        team_name = self._generate_team_name(goal, roles)
        team = await self.agent_manager.create_team(
            name=team_name,
            goal=goal,
            notebook_id=notebook_id,
            config=config
        )

        logger.info(f"Created team {team.id}: {team_name}")

        # 2. Spawn agents for each role
        spawned_agents = []
        for role in roles:
            agent = await self._spawn_agent(
                team_id=team.id,
                role=role,
                resources=resources,
                config=config
            )
            spawned_agents.append(agent)

        # 3. Create A2A message bus for team
        bus_factory = A2ATeamMessageBusFactory()
        message_bus = bus_factory.create_bus(
            team_id=team.id,
            user_id=user_id or "system"
        )

        # 4. Register local agents with message bus
        for agent in spawned_agents:
            # Get agent instance
            agent_instance = await AgentInstance.get(agent["id"])
            if agent_instance:
                # Register with A2A (using agent manager's adapters)
                await self._register_agent_with_bus(
                    message_bus=message_bus,
                    agent_instance=agent_instance
                )

        logger.info(
            f"Team {team.id} spawned successfully with {len(spawned_agents)} agents"
        )

        return {
            "team_id": team.id,
            "team_name": team_name,
            "goal": goal,
            "agent_ids": [a["id"] for a in spawned_agents],
            "agents": spawned_agents,
            "message_bus_id": team.id,
            "status": "ready"
        }

        # Create evaluation config for orchestrator-created teams
        has_judge = any(agent["role"] == "judge" for agent in spawned_agents)

        if has_judge:
            try:
                from api.services.evaluation_service import get_evaluation_service
                eval_service = await get_evaluation_service()

                await eval_service.create_evaluation_config(
                    team_id=team.id,
                    enabled=True,
                    auto_evaluate=True,  # AUTO-ENABLE for orchestrator
                    scope="all",
                    scoring_scale="0-10"
                )

                logger.info(f"Auto-evaluation enabled for orchestrator team {team.id}")
            except Exception as e:
                logger.warning(f"Failed to create evaluation config: {e}")

        return {
            "team_id": team.id,
            "team_name": team_name,
            "goal": goal,
            "agent_ids": [a["id"] for a in spawned_agents],
            "agents": spawned_agents,
            "message_bus_id": team.id,
            "status": "ready"
        }

    async def _spawn_agent(
        self,
        team_id: str,
        role: str,
        resources: Dict[str, Any],
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Spawn individual agent with role and configuration.

        Args:
            team_id: Team ID
            role: Agent role
            resources: Available resources
            config: Configuration

        Returns:
            Dict with agent details
        """
        # Generate agent name
        agent_name = self._generate_agent_name(role)

        # Select tools for role
        tool_ids = self._select_tools_for_role(role, resources)

        # Select model for role
        model_name = self._select_model_for_role(role, config)

        # Generate system prompt for role
        system_prompt = self._generate_system_prompt(role, resources)

        # Create agent configuration
        agent_config = {
            "role": role,
            "tools": tool_ids,
            "model": model_name,
            **(config.get("agent_config", {}))
        }

        # Add agent to team
        agent = await self.agent_manager.add_agent(
            team_id=team_id,
            role=role,
            name=agent_name,
            model_name=model_name,
            system_prompt=system_prompt,
            config=agent_config
        )

        logger.info(f"Spawned {role} agent: {agent_name} ({agent.id})")

        return {
            "id": agent.id,
            "name": agent_name,
            "role": role,
            "model": model_name,
            "tools": tool_ids,
            "status": "idle"
        }

    def _generate_team_name(self, goal: str, roles: List[str]) -> str:
        """Generate descriptive team name."""
        # Extract key words from goal
        goal_words = goal.split()[:3]
        goal_snippet = " ".join(goal_words)

        # Create name
        role_count = len(roles)
        return f"{goal_snippet} Team ({role_count} agents)"

    def _generate_agent_name(self, role: str) -> str:
        """Generate unique agent name for role."""
        role_names = {
            "planner": "Planner",
            "researcher": "Researcher",
            "analyst": "Data Analyst",
            "data_analyst": "Data Specialist",
            "synthesizer": "Synthesizer",
            "reporter": "Reporter",
            "api_specialist": "API Specialist",
            "web_researcher": "Web Researcher",
            "information_retriever": "Info Retriever",
            "web_scraper": "Web Scraper",
            "data_visualizer": "Visualizer",
            "text_analyst": "Text Analyst",
            "ml_specialist": "ML Specialist",
            "financial_analyst": "Financial Analyst",
            "marketing_analyst": "Marketing Analyst",
            "judge": "Judge"
        }

        base_name = role_names.get(role, role.replace("_", " ").title())
        # Add UUID suffix to ensure uniqueness
        suffix = str(uuid.uuid4())[:8]
        return f"{base_name}-{suffix}"

    def _select_tools_for_role(
        self,
        role: str,
        resources: Dict[str, Any]
    ) -> List[str]:
        """Select appropriate tools for agent role."""
        all_tools = resources.get("tools", [])

        # Role-to-tool mapping
        role_tool_patterns = {
            "researcher": ["web_search", "retrieval", "scraping"],
            "analyst": ["hana_query", "database", "sql", "data_analysis"],
            "data_analyst": ["hana_query", "database", "sql", "data_analysis"],
            "planner": ["task_decomposition", "scheduling"],
            "synthesizer": ["aggregation", "summarization"],
            "reporter": ["report_generation", "visualization"],
            "api_specialist": ["api_call", "rest", "http"],
            "web_researcher": ["web_search", "scraping"],
            "web_scraper": ["scraping", "crawling"],
            "data_visualizer": ["visualization", "charting"],
            "text_analyst": ["nlp", "sentiment", "text_processing"],
            "ml_specialist": ["ml", "prediction", "classification"],
            "judge": ["evaluation", "scoring", "quality_check"]
        }

        patterns = role_tool_patterns.get(role, [])

        # Filter tools matching patterns
        selected_tools = []
        for tool in all_tools:
            tool_id = tool.get("id", "")
            tool_name = tool.get("name", "").lower()

            for pattern in patterns:
                if pattern in tool_id.lower() or pattern in tool_name:
                    selected_tools.append(tool_id)
                    break

        return selected_tools

    def _select_model_for_role(
        self,
        role: str,
        config: Dict[str, Any]
    ) -> str:
        """Select appropriate LLM model for role."""
        # Check if role-specific model is configured
        role_models = config.get("role_models", {})
        if role in role_models:
            return role_models[role]

        # Default model based on role complexity
        complex_roles = [
            "planner",
            "synthesizer",
            "financial_analyst",
            "ml_specialist"
        ]

        if role in complex_roles:
            return config.get("default_model", "gpt-4")
        else:
            return config.get("default_model", "gpt-3.5-turbo")

    def _generate_system_prompt(
        self,
        role: str,
        resources: Dict[str, Any]
    ) -> str:
        """Generate system prompt for agent role."""
        role_prompts = {
            "planner": """You are a Planner Agent responsible for task decomposition and coordination.

Your responsibilities:
- Break down complex goals into manageable subtasks
- Identify dependencies between tasks
- Assign tasks to appropriate team members
- Monitor progress and adjust plans as needed

Always think step-by-step and ensure tasks are clearly defined.""",

            "researcher": """You are a Researcher Agent specialized in information gathering.

Your responsibilities:
- Search for relevant information from web and documents
- Retrieve and synthesize research findings
- Provide comprehensive summaries of findings
- Cite sources and maintain accuracy

Focus on finding high-quality, relevant information.""",

            "analyst": """You are a Data Analyst Agent specialized in data analysis.

Your responsibilities:
- Query databases and APIs for data
- Analyze data to extract insights
- Identify trends, patterns, and anomalies
- Provide data-driven recommendations

Use statistical methods and be precise in your analysis.""",

            "synthesizer": """You are a Synthesizer Agent responsible for aggregating results.

Your responsibilities:
- Aggregate outputs from multiple agents
- Resolve conflicts in information
- Create coherent final outputs
- Ensure completeness and accuracy

Focus on creating well-structured, comprehensive responses.""",

            "reporter": """You are a Reporter Agent specialized in report generation.

Your responsibilities:
- Create professional reports from analysis results
- Structure information clearly
- Include visualizations where appropriate
- Ensure readability and actionability

Focus on clear communication of insights.""",

            "judge": """You are a Judge Agent responsible for quality evaluation.

Your responsibilities:
- Evaluate outputs for accuracy, completeness, quality, and consistency
- Score outputs on a 0-10 scale across defined criteria
- Provide constructive feedback for improvement
- Make approval recommendations (approved/needs_revision/requires_rework)

Use this evaluation framework:
1. Accuracy & Correctness (0-10): Factual accuracy, no errors
2. Completeness & Coverage (0-10): Addresses all requirements
3. Quality & Clarity (0-10): Well-written, clear, professional
4. Consistency & Coherence (0-10): Logical flow, no contradictions

Provide structured evaluations with specific feedback."""
        }

        # Get role-specific prompt or generic prompt
        prompt = role_prompts.get(role, f"""You are a {role.replace('_', ' ').title()} Agent.

Perform tasks assigned to you efficiently and communicate results clearly to your team.""")

        # Add available tools context
        tools = resources.get("tools", [])
        if tools:
            tool_names = [t.get("name", t.get("id", "")) for t in tools[:5]]
            prompt += f"\n\nAvailable tools: {', '.join(tool_names)}"

        return prompt

    async def _register_agent_with_bus(
        self,
        message_bus: A2ATeamMessageBus,
        agent_instance: AgentInstance
    ) -> None:
        """
        Register agent with A2A message bus.

        Args:
            message_bus: A2A message bus
            agent_instance: Agent instance to register
        """
        # Check if agent is remote or local
        if agent_instance.is_remote and agent_instance.a2a_endpoint_url:
            # Register as remote agent
            from open_notebook.domain.a2a import A2ARemoteAgent

            remote_agent = await A2ARemoteAgent.get(agent_instance.remote_agent_id)
            if remote_agent:
                await message_bus.register_remote_agent(
                    agent_id=agent_instance.id,
                    remote_agent=remote_agent
                )
        else:
            # Register as local agent
            # Create A2A adapter for local agent
            from open_notebook.agents.a2a.standalone_adapter import (
                StandaloneAgentA2AAdapter
            )
            from open_notebook.domain.standalone_agent import StandaloneAgent

            # Convert AgentInstance to StandaloneAgent for adapter
            # (This is a simplified conversion - in production, may need more sophisticated mapping)
            standalone = StandaloneAgent(
                id=agent_instance.id,
                name=agent_instance.name,
                role=agent_instance.role,
                status="active"
            )

            await message_bus.register_local_agent(
                agent_id=agent_instance.id,
                standalone_agent=standalone
            )

        logger.debug(f"Registered agent {agent_instance.id} with message bus")


# Convenience function
async def spawn_team(
    goal: str,
    roles: List[str],
    resources: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
    notebook_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to spawn an agent team.

    Args:
        goal: Team goal/objective
        roles: List of agent roles
        resources: Available resources
        config: Team configuration
        user_id: User ID
        notebook_id: Notebook ID

    Returns:
        Dict with team and agent details
    """
    spawner = TeamSpawner()
    return await spawner.spawn_team(
        goal=goal,
        roles=roles,
        resources=resources,
        config=config,
        user_id=user_id,
        notebook_id=notebook_id
    )
