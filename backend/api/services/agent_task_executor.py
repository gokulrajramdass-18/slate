"""
Agent Task Executor Service

Routes workspace tasks to their assigned agents or teams for execution.
Bridges the guided workspace wizard agent selection with actual agent execution.
"""

import logging
from typing import Dict, List, Optional

from open_notebook.database.repository import repo_query

logger = logging.getLogger(__name__)


class AgentTaskExecutor:
    """
    Executes workspace tasks using their assigned agents or teams.

    This service bridges the gap between:
    1. Agents/teams selected in guided workspace wizard
    2. Actual agent execution for tasks
    """

    async def execute_task_with_agent(
        self,
        task: Dict,
        workspace_id: str,
        agent_id: Optional[str] = None
    ) -> Dict:
        """
        Execute a task using its assigned agent or team.

        Args:
            task: Task dict with id, name, description, assigned_agent_id
            workspace_id: Workspace/notebook ID
            agent_id: Optional override agent ID (uses task.assigned_agent_id if None)

        Returns:
            Dict with execution result
        """
        # Get agent ID (from parameter or task assignment)
        target_agent_id = agent_id or task.get("assigned_agent_id")

        if not target_agent_id:
            logger.warning(f"No agent assigned to task {task['id']}, using default execution")
            return await self._execute_with_default_llm(task, workspace_id)

        # Get agent details
        agent = await self._get_agent_or_team(target_agent_id)

        if not agent:
            logger.error(f"Agent {target_agent_id} not found, falling back to default")
            return await self._execute_with_default_llm(task, workspace_id)

        # Route to appropriate execution method
        if agent["type"] == "team":
            return await self._execute_with_team(task, workspace_id, agent)
        else:
            return await self._execute_with_standalone_agent(task, workspace_id, agent)

    async def _get_agent_or_team(self, agent_id: str) -> Optional[Dict]:
        """
        Fetch agent or team details by ID.

        Returns:
            Dict with type='agent' or type='team' plus details, or None if not found
        """
        # Try standalone agents first
        agent = await repo_query(
            """
            SELECT id, name, description, role, system_prompt, model_name,
                   tool_ids, skill_ids, mcp_server_ids, data_source_ids, config
            FROM standalone_agents
            WHERE id = :agent_id AND status = 'active'
            """,
            {"agent_id": agent_id},
            fetch_one=True
        )

        if agent:
            return {
                "type": "agent",
                "id": agent["id"],
                "name": agent["name"],
                "description": agent.get("description"),
                "role": agent.get("role"),
                "system_prompt": agent.get("system_prompt"),
                "model_name": agent.get("model_name"),
                "tool_ids": agent.get("tool_ids", "[]"),
                "skill_ids": agent.get("skill_ids", "[]"),
                "mcp_server_ids": agent.get("mcp_server_ids", "[]"),
                "data_source_ids": agent.get("data_source_ids", "[]"),
                "config": agent.get("config", "{}")
            }

        # Try agent teams
        team = await repo_query(
            """
            SELECT id, name, description, config
            FROM agent_teams
            WHERE id = :agent_id AND status = 'active'
            """,
            {"agent_id": agent_id},
            fetch_one=True
        )

        if team:
            # Get team members
            members = await repo_query(
                """
                SELECT sa.id, sa.name, sa.role, sa.system_prompt, sa.model_name,
                       sa.tool_ids, sa.skill_ids, sa.mcp_server_ids, sa.data_source_ids
                FROM standalone_agents sa
                JOIN agent_team_members atm ON sa.id = atm.agent_id
                WHERE atm.team_id = :team_id AND sa.status = 'active'
                ORDER BY atm.sequence
                """,
                {"team_id": team["id"]}
            )

            return {
                "type": "team",
                "id": team["id"],
                "name": team["name"],
                "description": team.get("description"),
                "config": team.get("config", "{}"),
                "members": list(members)
            }

        return None

    async def _execute_with_standalone_agent(
        self,
        task: Dict,
        workspace_id: str,
        agent: Dict
    ) -> Dict:
        """
        Execute task using a standalone agent.

        This creates a DataQueryAgent with the agent's configuration.
        """
        import json
        from open_notebook.agents.data_query_agent import DataQueryAgent
        from api.services.tool_factory import get_tool_factory
        from api.services.settings import get_setting
        from api.services.credential_manager import get_credential_manager

        logger.info(f"Executing task '{task['name']}' with agent '{agent['name']}'")

        # Get agent's model configuration
        model_name = agent.get("model_name")
        if not model_name:
            # Fall back to workspace default
            model_name = await get_setting("language_model_id", "")

        if not model_name:
            raise Exception("No model configured for agent")

        # Get credentials using unified credential manager
        # This supports lookup by ID (UUID) or name (model name)
        credential_manager = get_credential_manager()
        credential = credential_manager.get(model_name)

        # Fallback to legacy store if not found
        if not credential:
            from api.routers.credentials import _credentials_store
            credential = _credentials_store.get(model_name)
            if credential:
                logger.info(f"Found credential in legacy store: {model_name}")
                # Register it in the manager for future use
                credential_manager.register_in_memory_credential(model_name, credential)

        if not credential:
            raise Exception(f"Model credential not found: {model_name}")

        # Create tools for the agent based on its configuration
        factory = get_tool_factory()

        # Parse agent's tool/skill/mcp/source IDs
        tool_ids = json.loads(agent.get("tool_ids", "[]"))
        skill_ids = json.loads(agent.get("skill_ids", "[]"))
        mcp_server_ids = json.loads(agent.get("mcp_server_ids", "[]"))
        data_source_ids = json.loads(agent.get("data_source_ids", "[]"))

        # Create tools (filtered by agent's configuration)
        tools = await factory.create_tools_for_session(
            notebook_id=workspace_id,
            user_id="workspace_executor",
            session_id=f"task_{task['id']}",
            selected_tool_ids=tool_ids,
            selected_mcp_server_ids=mcp_server_ids
        )

        logger.info(f"Created {len(tools)} tools for agent")

        # Build system prompt
        system_prompt = agent.get("system_prompt") or f"""You are {agent['name']}, a {agent.get('role', 'assistant')} agent.

{agent.get('description', '')}

Your current task:
{task['description']}

Focus on completing this specific task and providing detailed, actionable results."""

        # Create DataQueryAgent with agent configuration
        data_agent = DataQueryAgent(
            model_name=credential["model_name"],
            notebook_id=workspace_id,
            tools=tools,
            session_id=f"task_{task['id']}",
            system_message=system_prompt,
            capture_tool_results=True,
            api_key=credential.get("api_key"),
            base_url=credential.get("base_url"),
            enable_tool_filtering=True,
            task_description=task['description']
        )

        # Execute the task
        task_query = f"""Execute this task:

**Task**: {task['name']}
**Description**: {task['description']}
**Phase**: {task.get('phase_name', 'Unknown')}

Provide a detailed analysis and results for this task. Use available tools to gather data and insights."""

        result_text = await data_agent.invoke(task_query, [])

        logger.info(f"Agent '{agent['name']}' completed task '{task['name']}'")

        return {
            "success": True,
            "result": result_text,
            "agent_name": agent["name"],
            "agent_id": agent["id"],
            "agent_type": "standalone",
            "tool_results": data_agent.get_captured_tool_results(),
            "agent_steps": data_agent.agent_steps
        }

    async def _execute_with_team(
        self,
        task: Dict,
        workspace_id: str,
        team: Dict
    ) -> Dict:
        """
        Execute task using an agent team.

        For now, uses the first team member. Future: implement team orchestration.
        """
        import json

        logger.info(f"Executing task '{task['name']}' with team '{team['name']}'")

        members = team.get("members", [])
        if not members:
            raise Exception(f"Team '{team['name']}' has no active members")

        # For now, use the first member (team lead)
        # TODO: Implement proper team orchestration
        lead_agent = members[0]

        # Convert team member to agent dict format
        agent_dict = {
            "type": "agent",
            "id": lead_agent["id"],
            "name": lead_agent["name"],
            "role": lead_agent.get("role"),
            "system_prompt": lead_agent.get("system_prompt"),
            "model_name": lead_agent.get("model_name"),
            "tool_ids": lead_agent.get("tool_ids", "[]"),
            "skill_ids": lead_agent.get("skill_ids", "[]"),
            "mcp_server_ids": lead_agent.get("mcp_server_ids", "[]"),
            "data_source_ids": lead_agent.get("data_source_ids", "[]")
        }

        # Execute with team lead
        result = await self._execute_with_standalone_agent(task, workspace_id, agent_dict)

        # Update result to indicate team execution
        result["agent_type"] = "team"
        result["team_name"] = team["name"]
        result["team_id"] = team["id"]
        result["team_member_used"] = lead_agent["name"]

        logger.info(f"Team '{team['name']}' (via {lead_agent['name']}) completed task '{task['name']}'")

        return result

    async def _execute_with_default_llm(
        self,
        task: Dict,
        workspace_id: str
    ) -> Dict:
        """
        Fallback: Execute task with default LLM (no specific agent).

        This is the original behavior from workspace_task_executor.py
        """
        from api.services.settings import get_setting
        from api.services.credential_manager import get_credential_manager
        import httpx
        from open_notebook.database.repository import repo_query

        logger.info(f"Executing task '{task['name']}' with default LLM (no agent assigned)")

        # Get workspace info
        workspace = await repo_query(
            "SELECT name, goal FROM notebooks WHERE id = :id",
            {"id": workspace_id},
            fetch_one=True
        )

        # Get workspace sources for context
        sources = await repo_query(
            """
            SELECT s.id, s.title, s.source_type, s.full_text
            FROM sources s
            JOIN notebook_source ns ON s.id = ns.source_id
            WHERE ns.notebook_id = :workspace_id
            """,
            {"workspace_id": workspace_id}
        )

        # Build context
        sources_context = []
        for source in sources[:5]:  # Limit to 5 sources
            content = source.get('full_text', '')[:1000] if source.get('full_text') else "No content"
            sources_context.append(f"**{source['title']}** ({source['source_type']})\n{content}")

        sources_text = "\n\n---\n\n".join(sources_context) if sources_context else "No sources available"

        # Build prompt
        prompt = f"""Execute this workspace task and provide detailed analysis.

**Workspace**: {workspace.get('name', 'Unknown')}
**Goal**: {workspace.get('goal', 'N/A')}

**Task**: {task['name']}
**Description**: {task['description']}
**Phase**: {task.get('phase_name', 'Unknown')}

**Available Data**:
{sources_text}

**Your Task**:
Analyze the available data and provide a comprehensive analysis for this task.
Include specific insights, data points, and actionable recommendations.

Generate your analysis in clean HTML format (use <h3>, <h4>, <p>, <ul>, <li> tags).
"""

        # Get LLM configuration using credential manager
        model_id = await get_setting("language_model_id", "")
        if not model_id:
            raise Exception("No language model configured")

        credential_manager = get_credential_manager()
        credential = credential_manager.get(model_id)

        # Fallback to legacy store
        if not credential:
            from api.routers.credentials import _credentials_store
            credential = _credentials_store.get(model_id)
            if credential:
                logger.info(f"Found credential in legacy store for default LLM: {model_id}")
                credential_manager.register_in_memory_credential(model_id, credential)

        if not credential:
            raise Exception("Language model credential not found")

        # Call LLM
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{credential['base_url']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {credential['api_key']}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": credential.get("model_name", "gpt-4"),
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert analyst. Provide detailed, data-driven analysis."
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000,
                },
            )

            if response.status_code != 200:
                raise Exception(f"LLM API error: {response.status_code}")

            result = response.json()
            result_text = result["choices"][0]["message"]["content"]

        logger.info(f"Default LLM completed task '{task['name']}'")

        return {
            "success": True,
            "result": result_text,
            "agent_name": "Default LLM",
            "agent_id": None,
            "agent_type": "default",
            "tool_results": None,
            "agent_steps": []
        }


# Singleton
_agent_task_executor: Optional[AgentTaskExecutor] = None


def get_agent_task_executor() -> AgentTaskExecutor:
    """Get or create the AgentTaskExecutor singleton."""
    global _agent_task_executor
    if _agent_task_executor is None:
        _agent_task_executor = AgentTaskExecutor()
    return _agent_task_executor
