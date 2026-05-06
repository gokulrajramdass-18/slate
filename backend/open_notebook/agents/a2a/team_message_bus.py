"""
A2A Team Message Bus

A2A-compliant message bus for agent teams.
Handles both local and remote agents using A2A protocol.
"""

import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

from a2a.types import (
    SendMessageRequest,
    SendMessageResponse,
    MessageSendConfiguration,
    Message,
    Part,
)

from open_notebook.agents.a2a.task_manager import A2ATaskManager
from open_notebook.agents.a2a.standalone_adapter import StandaloneAgentA2AAdapter
from open_notebook.agents.a2a.client import OpenNotebookA2AClient
from open_notebook.domain.a2a import A2ARemoteAgent
from open_notebook.domain.standalone_agent import StandaloneAgent


class A2ATeamMessageBus:
    """
    A2A-compliant message bus for agent teams.

    Handles both local and remote agents using A2A protocol for all communication.
    Provides location transparency - coordinator doesn't know/care if agents are local or remote.

    Features:
    - Unified A2A protocol for all agents
    - Local agent execution via StandaloneAgentA2AAdapter
    - Remote agent execution via OpenNotebookA2AClient
    - Task lifecycle tracking
    - Broadcast support
    - Metrics collection
    """

    def __init__(self, team_id: str, user_id: str):
        """
        Initialize A2A team message bus.

        Args:
            team_id: Team ID (used as context ID)
            user_id: User ID for agent execution context
        """
        self.team_id = team_id
        self.user_id = user_id
        self._local_agents: Dict[str, StandaloneAgentA2AAdapter] = {}
        self._remote_agents: Dict[str, OpenNotebookA2AClient] = {}
        self._task_manager = A2ATaskManager()

    async def register_local_agent(
        self,
        agent_id: str,
        standalone_agent: StandaloneAgent,
    ) -> None:
        """
        Register a local agent with A2A adapter.

        Args:
            agent_id: Agent instance ID
            standalone_agent: StandaloneAgent domain model
        """
        adapter = StandaloneAgentA2AAdapter(
            standalone_agent=standalone_agent,
            task_manager=self._task_manager,
        )
        self._local_agents[agent_id] = adapter

    async def register_remote_agent(
        self,
        agent_id: str,
        remote_agent: A2ARemoteAgent,
    ) -> None:
        """
        Register a remote A2A agent.

        Args:
            agent_id: Agent instance ID
            remote_agent: A2ARemoteAgent domain model
        """
        client = OpenNotebookA2AClient(remote_agent)
        self._remote_agents[agent_id] = client

    def unregister_agent(self, agent_id: str) -> None:
        """
        Unregister an agent from the bus.

        Args:
            agent_id: Agent instance ID
        """
        if agent_id in self._local_agents:
            del self._local_agents[agent_id]
        if agent_id in self._remote_agents:
            del self._remote_agents[agent_id]

    async def send_message(
        self,
        sender_id: str,
        recipient_id: str,
        content: str,
        skill_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send A2A message to local or remote agent.

        Automatically routes to correct handler based on agent registration.
        Provides location transparency.

        Args:
            sender_id: Sender agent ID
            recipient_id: Recipient agent ID
            content: Message content
            skill_id: Optional skill ID to execute
            metadata: Optional metadata

        Returns:
            Execution result dictionary

        Raises:
            ValueError: If recipient agent not found
        """
        # Create A2A message
        message = Message(
            messageId=str(uuid.uuid4()),
            role="agent",
            parts=[Part(text=content)],
        )

        # Build metadata
        msg_metadata = {
            "contextId": self.team_id,
            "senderId": sender_id,
            "recipientId": recipient_id,
            "userId": self.user_id,
        }
        if skill_id:
            msg_metadata["skillId"] = skill_id
        if metadata:
            msg_metadata.update(metadata)

        # Build request
        request = SendMessageRequest(
            message=message,
            metadata=msg_metadata,
        )

        # Route to local or remote
        if recipient_id in self._local_agents:
            response = await self._local_agents[recipient_id].handle_message(
                request=request,
                user_id=self.user_id,
                notebook_id=self.team_id,  # Use team_id as notebook context
            )
        elif recipient_id in self._remote_agents:
            response = await self._remote_agents[recipient_id].send_message_raw(request)
        else:
            raise ValueError(f"Agent not found: {recipient_id}")

        # Extract result from A2A response
        return self._extract_result(response)

    async def broadcast(
        self,
        sender_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Broadcast message to all agents in team (except sender).

        Args:
            sender_id: Sender agent ID
            content: Message content
            metadata: Optional metadata

        Returns:
            List of results from all agents
        """
        results = []

        # Get all agent IDs
        all_agents = set(self._local_agents.keys()) | set(self._remote_agents.keys())

        # Send to all except sender
        for agent_id in all_agents:
            if agent_id != sender_id:
                try:
                    result = await self.send_message(
                        sender_id=sender_id,
                        recipient_id=agent_id,
                        content=content,
                        metadata=metadata,
                    )
                    results.append({
                        "agent_id": agent_id,
                        "success": True,
                        "result": result,
                    })
                except Exception as e:
                    results.append({
                        "agent_id": agent_id,
                        "success": False,
                        "error": str(e),
                    })

        return results

    def _extract_result(self, response: SendMessageResponse) -> Dict[str, Any]:
        """
        Extract result from A2A response.

        Args:
            response: SendMessageResponse

        Returns:
            Result dictionary with output, artifacts, status
        """
        # Extract actual response from union
        actual_response = response.root

        # Get task
        task = actual_response.result

        # Extract artifacts
        artifacts = []
        for artifact in task.artifacts:
            content_parts = []
            for part in artifact.parts:
                if hasattr(part, "text") and part.text:
                    content_parts.append(part.text)

            artifacts.append({
                "artifact_id": artifact.artifactId,
                "content": "\n".join(content_parts),
            })

        # Extract main output (first artifact)
        output = artifacts[0]["content"] if artifacts else ""

        return {
            "task_id": task.id,
            "status": task.status.state,
            "output": output,
            "artifacts": artifacts,
            "context_id": task.contextId,
        }

    def get_agent_count(self) -> Dict[str, int]:
        """
        Get count of registered agents by type.

        Returns:
            Dictionary with local and remote counts
        """
        return {
            "local": len(self._local_agents),
            "remote": len(self._remote_agents),
            "total": len(self._local_agents) + len(self._remote_agents),
        }

    def list_agents(self) -> Dict[str, List[str]]:
        """
        List all registered agents by type.

        Returns:
            Dictionary with local and remote agent IDs
        """
        return {
            "local": list(self._local_agents.keys()),
            "remote": list(self._remote_agents.keys()),
        }

    def is_local_agent(self, agent_id: str) -> bool:
        """
        Check if agent is local.

        Args:
            agent_id: Agent ID

        Returns:
            True if agent is local, False if remote or not found
        """
        return agent_id in self._local_agents

    def is_remote_agent(self, agent_id: str) -> bool:
        """
        Check if agent is remote.

        Args:
            agent_id: Agent ID

        Returns:
            True if agent is remote, False if local or not found
        """
        return agent_id in self._remote_agents

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of A2A task.

        Args:
            task_id: Task ID

        Returns:
            Task status dictionary or None if not found
        """
        from open_notebook.domain.a2a import A2ATask

        task = await A2ATask.get(task_id)
        if not task:
            return None

        return {
            "id": task.id,
            "status": task.status,
            "direction": task.direction,
            "agent_id": task.agent_id,
            "skill_id": task.skill_id,
            "context_id": task.context_id,
            "created_at": task.created_at.isoformat(),
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        }

    async def get_team_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent tasks for this team.

        Args:
            limit: Maximum number of tasks to return

        Returns:
            List of task dictionaries
        """
        from open_notebook.domain.a2a import A2ATask

        tasks = await A2ATask.get_all(
            order_by=("created_at", "DESC"),
            limit=limit,
        )

        # Filter by team context
        team_tasks = [
            task for task in tasks
            if task.context_id == self.team_id
        ]

        return [
            {
                "id": task.id,
                "status": task.status,
                "direction": task.direction,
                "agent_id": task.agent_id,
                "skill_id": task.skill_id,
                "created_at": task.created_at.isoformat(),
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            }
            for task in team_tasks[:limit]
        ]


class A2ATeamMessageBusFactory:
    """
    Factory for creating A2ATeamMessageBus instances.

    Maintains a registry of buses by team ID for reuse.
    """

    def __init__(self):
        self._buses: Dict[str, A2ATeamMessageBus] = {}

    def create_bus(self, team_id: str, user_id: str) -> A2ATeamMessageBus:
        """
        Create or get existing message bus for team.

        Args:
            team_id: Team ID
            user_id: User ID

        Returns:
            A2ATeamMessageBus instance
        """
        if team_id not in self._buses:
            self._buses[team_id] = A2ATeamMessageBus(team_id, user_id)
        return self._buses[team_id]

    def get_bus(self, team_id: str) -> Optional[A2ATeamMessageBus]:
        """
        Get existing bus for team.

        Args:
            team_id: Team ID

        Returns:
            Bus if found, None otherwise
        """
        return self._buses.get(team_id)

    def remove_bus(self, team_id: str) -> None:
        """
        Remove bus for team.

        Args:
            team_id: Team ID
        """
        if team_id in self._buses:
            del self._buses[team_id]

    def list_teams(self) -> List[str]:
        """
        List all active team IDs.

        Returns:
            List of team IDs
        """
        return list(self._buses.keys())


# Global factory instance
_factory: Optional[A2ATeamMessageBusFactory] = None


def get_team_message_bus_factory() -> A2ATeamMessageBusFactory:
    """
    Get global team message bus factory.

    Returns:
        Global factory instance
    """
    global _factory
    if _factory is None:
        _factory = A2ATeamMessageBusFactory()
    return _factory
