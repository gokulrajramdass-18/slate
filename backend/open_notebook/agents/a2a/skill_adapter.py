"""
Remote Skill Adapter

Adapts remote A2A agent skills to work as local skills.
"""

import logging
from typing import Any, Callable

from open_notebook.agents.a2a.client import OpenNotebookA2AClient
from open_notebook.agents.skills.base import SkillContext
from open_notebook.domain.a2a import A2ARemoteAgent

logger = logging.getLogger(__name__)


class RemoteSkillAdapter:
    """
    Adapter to execute remote A2A skills as local skills.

    Creates skill handlers that:
    - Connect to remote A2A agents
    - Execute via A2A protocol
    - Handle errors and retries
    - Track execution steps
    """

    @staticmethod
    def create_handler(
        agent_id: str,
        remote_skill_id: str,
    ) -> Callable:
        """
        Create async handler for remote skill execution.

        Args:
            agent_id: Remote agent ID
            remote_skill_id: Skill ID on remote agent

        Returns:
            Async handler function compatible with Skill.handler
        """

        async def remote_skill_handler(context: SkillContext) -> Any:
            """
            Execute remote A2A skill.

            Args:
                context: Skill execution context

            Returns:
                Skill result

            Raises:
                ValueError: If agent not found
                Exception: If remote execution fails
            """
            # Get remote agent
            agent = await A2ARemoteAgent.get(agent_id)
            if not agent:
                error = f"Remote agent not found: {agent_id}"
                context.record_step("error", error, status="error")
                raise ValueError(error)

            if not agent.enabled:
                error = f"Remote agent is disabled: {agent.name}"
                context.record_step("error", error, status="error")
                raise ValueError(error)

            # Record start
            context.record_step(
                "remote_call",
                f"Calling remote skill '{remote_skill_id}' on {agent.name}",
                status="running",
            )

            # Create client
            async with OpenNotebookA2AClient(agent) as client:
                try:
                    # Check if streaming requested
                    if context.config.get("stream", False):
                        # Streaming execution
                        result = None
                        async for event in client.stream_message(
                            skill_id=remote_skill_id,
                            input_data=context.input_data,
                            context_id=context.execution_id,
                        ):
                            # Record progress
                            event_type = event.get("event_type")
                            data = event.get("data", {})

                            if event_type == "task.updated":
                                progress = data.get("status", {}).get("progress", 0.0)
                                message = data.get("status", {}).get("message", "Processing")
                                context.record_step(
                                    "remote_progress",
                                    f"{message} ({progress * 100:.0f}%)",
                                    status="running",
                                    metadata={"progress": progress},
                                )
                            elif event_type == "task.completed":
                                result = data.get("artifacts", [])

                        # Extract result from artifacts
                        if isinstance(result, list) and result:
                            # Get first artifact content
                            result = result[0].get("content") if result[0] else {}

                    else:
                        # Synchronous execution
                        result = await client.send_message(
                            skill_id=remote_skill_id,
                            input_data=context.input_data,
                            context_id=context.execution_id,
                        )

                    # Record completion
                    context.record_step(
                        "remote_call",
                        f"Completed remote skill '{remote_skill_id}'",
                        status="completed",
                        metadata={"agent": agent.name},
                    )

                    return result

                except Exception as e:
                    # Record error
                    error_msg = f"Remote skill execution failed: {e}"
                    context.record_step("error", error_msg, status="error")

                    logger.error(
                        f"Remote skill {remote_skill_id} on {agent.name} failed: {e}"
                    )
                    raise

        # Set metadata on handler for introspection
        remote_skill_handler.__name__ = f"remote_{agent_id}_{remote_skill_id}"
        remote_skill_handler.__doc__ = f"Remote A2A skill: {remote_skill_id} on agent {agent_id}"

        return remote_skill_handler


class RemoteSkillRegistry:
    """
    Registry for tracking remote skill handlers.

    Provides utilities for:
    - Looking up remote skills
    - Checking agent availability
    - Managing skill lifecycle
    """

    @staticmethod
    def is_remote_skill(skill_id: str) -> bool:
        """
        Check if skill ID represents a remote A2A skill.

        Args:
            skill_id: Skill identifier

        Returns:
            True if remote skill
        """
        return skill_id.startswith("a2a:")

    @staticmethod
    def parse_remote_skill_id(skill_id: str) -> tuple[str, str]:
        """
        Parse remote skill ID into agent ID and remote skill ID.

        Args:
            skill_id: Local skill ID in format "a2a:{agent_id}:{remote_skill_id}"

        Returns:
            Tuple of (agent_id, remote_skill_id)

        Raises:
            ValueError: If skill ID format is invalid
        """
        if not RemoteSkillRegistry.is_remote_skill(skill_id):
            raise ValueError(f"Not a remote skill ID: {skill_id}")

        parts = skill_id.split(":", 2)
        if len(parts) != 3:
            raise ValueError(f"Invalid remote skill ID format: {skill_id}")

        return parts[1], parts[2]

    @staticmethod
    async def get_remote_agent_for_skill(skill_id: str) -> A2ARemoteAgent:
        """
        Get remote agent for a skill.

        Args:
            skill_id: Local skill ID

        Returns:
            A2ARemoteAgent

        Raises:
            ValueError: If not a remote skill or agent not found
        """
        agent_id, _ = RemoteSkillRegistry.parse_remote_skill_id(skill_id)
        agent = await A2ARemoteAgent.get(agent_id)

        if not agent:
            raise ValueError(f"Remote agent not found: {agent_id}")

        return agent
