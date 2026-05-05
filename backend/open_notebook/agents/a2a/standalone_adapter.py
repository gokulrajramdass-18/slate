"""
Standalone Agent A2A Adapter

Wraps standalone LangGraph agents to handle A2A protocol messages.
Converts A2A SendMessageRequest → Agent execution → A2A SendMessageResponse.
"""

import uuid
from typing import Any, Dict, Optional, List
from datetime import datetime

from a2a.types import (
    SendMessageRequest,
    SendMessageResponse,
    Task,
    TaskStatus,
    Artifact,
    Part,
    Message,
)

from open_notebook.agents.a2a.task_manager import A2ATaskManager
from open_notebook.agents.a2a.agent_card import AgentCardGenerator
from open_notebook.agents.skills.base import SkillContext
from open_notebook.domain.standalone_agent import StandaloneAgent


class StandaloneAgentA2AAdapter:
    """
    Wraps a standalone agent to handle A2A messages.

    Provides the bridge between A2A protocol and native LangGraph agents:
    - Receives A2A SendMessageRequest
    - Executes underlying agent (DataQueryAgent, DeepResearchAgent, etc.)
    - Converts result to A2A SendMessageResponse with artifacts
    - Tracks execution via A2ATaskManager

    This enables standalone agents to be used interchangeably with remote A2A agents.
    """

    def __init__(
        self,
        standalone_agent: StandaloneAgent,
        task_manager: Optional[A2ATaskManager] = None,
    ):
        """
        Initialize adapter for a standalone agent.

        Args:
            standalone_agent: StandaloneAgent domain model
            task_manager: Optional A2ATaskManager for task tracking
        """
        self.standalone_agent = standalone_agent
        self.task_manager = task_manager or A2ATaskManager()
        self.card_generator = AgentCardGenerator()

    async def handle_message(
        self,
        request: SendMessageRequest,
        user_id: str,
        notebook_id: Optional[str] = None,
    ) -> SendMessageResponse:
        """
        Handle incoming A2A message and execute agent.

        Workflow:
        1. Create A2A task for tracking
        2. Extract message content from A2A request
        3. Build skill context
        4. Execute agent via skill
        5. Convert result to A2A artifacts
        6. Mark task as completed
        7. Return A2A response

        Args:
            request: A2A SendMessageRequest
            user_id: User ID for context
            notebook_id: Optional notebook ID for workspace context

        Returns:
            SendMessageResponse with task and artifacts
        """
        # Extract context ID from metadata
        context_id = request.params.metadata.get("contextId") if request.params.metadata else None
        # Use request ID as fallback if no context ID provided
        if not context_id:
            context_id = request.id

        # Create A2A task
        task = await self.task_manager.create_task(
            context_id=context_id,
            direction="incoming",
            agent_id=self.standalone_agent.id,
            skill_id=self.standalone_agent.primary_skill_id,
        )

        try:
            # Mark task as running
            await self.task_manager.mark_task_running(task.id)

            # Extract message content
            message = request.params.message
            content = self._extract_content(message)

            # Build skill context
            skill_context = SkillContext(
                agent_id=self.standalone_agent.id,
                agent_role=self.standalone_agent.role or "agent",
                skill_id=self.standalone_agent.primary_skill_id,
                input_data={
                    "query": content,
                    "user_id": user_id,
                    "notebook_id": notebook_id,
                    "context_id": context_id,
                    "config": self.standalone_agent.config,
                },
                metadata={
                    "request_id": request.id,
                    "task_id": task.id,
                    "agent_name": self.standalone_agent.name,
                },
            )

            # Execute agent via skill (handles both code and dynamic skills)
            from open_notebook.agents.skills.executor import get_skill_executor
            executor = get_skill_executor()

            # Execute skill (executor will check registry first, then database)
            skill_result = await executor.execute(
                self.standalone_agent.primary_skill_id,
                skill_context
            )

            if not skill_result.success:
                raise ValueError(skill_result.error or "Skill execution failed")

            result = skill_result.result

            # Convert result to A2A artifacts
            artifacts = self._create_artifacts(result, task.id)

            # Mark task as completed with artifacts
            await self.task_manager.mark_task_completed(
                task_id=task.id,
                artifacts=[artifact.model_dump() for artifact in artifacts],
            )

            # Create A2A task response
            a2a_task = Task(
                id=task.id,
                contextId=context_id,
                status=TaskStatus(state="completed"),
                artifacts=artifacts,
            )

            # Return success response
            return SendMessageResponse(
                root=SendMessageSuccessResponse(
                    id=request.id,
                    result=a2a_task,
                )
            )

        except Exception as e:
            # Mark task as failed
            await self.task_manager.mark_task_failed(
                task_id=task.id,
                error=str(e),
            )

            # Create error task
            a2a_task = Task(
                id=task.id,
                contextId=context_id,
                status=TaskStatus(
                    state="failed",
                    message=str(e),
                ),
                artifacts=[],
            )

            # Return success response with failed task
            # (A2A protocol uses success response even for task failures)
            return SendMessageResponse(
                root=SendMessageSuccessResponse(
                    id=request.id,
                    result=a2a_task,
                )
            )

    def _extract_content(self, message: Message) -> str:
        """
        Extract text content from A2A message.

        Args:
            message: A2A Message with parts

        Returns:
            Concatenated text content
        """
        parts = []
        for part in message.parts:
            if hasattr(part, "text") and part.text:
                parts.append(part.text)
        return "\n".join(parts)

    def _create_artifacts(self, result: Dict[str, Any], task_id: str) -> List[Artifact]:
        """
        Convert agent result to A2A artifacts.

        Args:
            result: Agent execution result
            task_id: Task ID for artifact ID generation

        Returns:
            List of A2A artifacts
        """
        artifacts = []

        # Main result artifact (text)
        if "output" in result:
            artifact = Artifact(
                artifactId=f"{task_id}-output",
                parts=[Part(text=str(result["output"]))],
            )
            artifacts.append(artifact)

        # Additional artifacts (steps, metadata, etc.)
        if "steps" in result:
            steps_text = self._format_steps(result["steps"])
            artifact = Artifact(
                artifactId=f"{task_id}-steps",
                parts=[TextPart(text=steps_text)],
            )
            artifacts.append(artifact)

        if "metadata" in result:
            import json
            metadata_text = json.dumps(result["metadata"], indent=2)
            artifact = Artifact(
                artifactId=f"{task_id}-metadata",
                parts=[TextPart(text=metadata_text)],
            )
            artifacts.append(artifact)

        return artifacts

    def _format_steps(self, steps: List[Dict[str, Any]]) -> str:
        """
        Format agent steps as text.

        Args:
            steps: List of step dictionaries

        Returns:
            Formatted text
        """
        lines = ["Agent Execution Steps:", ""]
        for i, step in enumerate(steps, 1):
            lines.append(f"Step {i}: {step.get('name', 'Unknown')}")
            if "description" in step:
                lines.append(f"  {step['description']}")
            if "result" in step:
                lines.append(f"  Result: {step['result']}")
            lines.append("")
        return "\n".join(lines)

    async def get_agent_card(self) -> Dict[str, Any]:
        """
        Generate AgentCard for this standalone agent.

        Returns:
            AgentCard as dictionary
        """
        # Get skill from registry
        from open_notebook.agents.skills.registry import get_skill_registry
        registry = get_skill_registry()
        skill = registry.get_skill(self.standalone_agent.primary_skill_id)

        if not skill:
            raise ValueError(f"Skill not found: {self.standalone_agent.primary_skill_id}")

        # Generate AgentCard from skills
        card = await self.card_generator.generate_agent_card(
            agent_skills=[skill],
            agent_name=self.standalone_agent.name,
            agent_description=self.standalone_agent.description,
        )

        return card.model_dump()


class StandaloneAgentA2ARegistry:
    """
    Registry for managing StandaloneAgentA2AAdapters.

    Maintains a mapping of standalone agent IDs to their A2A adapters,
    enabling location transparency (local vs remote agents).
    """

    def __init__(self):
        self._adapters: Dict[str, StandaloneAgentA2AAdapter] = {}
        self._task_manager = A2ATaskManager()

    async def register_agent(self, standalone_agent: StandaloneAgent) -> StandaloneAgentA2AAdapter:
        """
        Register a standalone agent with A2A adapter.

        Args:
            standalone_agent: StandaloneAgent to register

        Returns:
            Created adapter
        """
        adapter = StandaloneAgentA2AAdapter(
            standalone_agent=standalone_agent,
            task_manager=self._task_manager,
        )
        self._adapters[standalone_agent.id] = adapter
        return adapter

    def get_adapter(self, agent_id: str) -> Optional[StandaloneAgentA2AAdapter]:
        """
        Get adapter for agent ID.

        Args:
            agent_id: Agent ID

        Returns:
            Adapter if found, None otherwise
        """
        return self._adapters.get(agent_id)

    def unregister_agent(self, agent_id: str) -> None:
        """
        Unregister agent adapter.

        Args:
            agent_id: Agent ID to unregister
        """
        if agent_id in self._adapters:
            del self._adapters[agent_id]

    def list_agents(self) -> List[str]:
        """
        List all registered agent IDs.

        Returns:
            List of agent IDs
        """
        return list(self._adapters.keys())

    async def send_message(
        self,
        agent_id: str,
        request: SendMessageRequest,
        user_id: str,
        notebook_id: Optional[str] = None,
    ) -> SendMessageResponse:
        """
        Send A2A message to registered agent.

        Args:
            agent_id: Target agent ID
            request: A2A SendMessageRequest
            user_id: User ID for context
            notebook_id: Optional notebook ID

        Returns:
            SendMessageResponse from agent

        Raises:
            ValueError: If agent not found
        """
        adapter = self.get_adapter(agent_id)
        if not adapter:
            raise ValueError(f"Agent not found: {agent_id}")

        return await adapter.handle_message(request, user_id, notebook_id)


# Global registry instance
_registry: Optional[StandaloneAgentA2ARegistry] = None


def get_standalone_agent_registry() -> StandaloneAgentA2ARegistry:
    """
    Get global standalone agent A2A registry.

    Returns:
        Global registry instance
    """
    global _registry
    if _registry is None:
        _registry = StandaloneAgentA2ARegistry()
    return _registry
