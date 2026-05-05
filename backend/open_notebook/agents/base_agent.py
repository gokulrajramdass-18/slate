"""
Base Agent - Abstract base class for team agents.

Provides:
- BaseAgent abstract class that all team agents extend
- AgentStatus enum for runtime lifecycle tracking
- Common step-recording and LLM invocation utilities
"""

import json
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from open_notebook.agents.llm_pool import LLMClientPool
from open_notebook.domain.agent_team import AgentInstance, AgentMessage


class AgentStatus(str, Enum):
    """Runtime status of an agent."""

    IDLE = "idle"
    BUSY = "busy"
    COMPLETED = "completed"
    FAILED = "failed"


class BaseAgent(ABC):
    """
    Abstract base class for all agents in a team.

    Subclasses must implement `execute` which contains the agent's
    core logic. The base class provides:
    - LLM creation and invocation helpers
    - Step recording for observability
    - Message send/receive through the domain layer
    - Structured output parsing

    Usage::

        class ResearcherAgent(BaseAgent):
            async def execute(self, input_data):
                result = await self.invoke_llm("Summarize this: ...")
                return {"summary": result}
    """

    def __init__(
        self,
        instance: AgentInstance,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize agent from a persisted AgentInstance.

        Args:
            instance: The database-backed AgentInstance record
            model_name: Override model (falls back to instance.model_name)
            base_url: Optional LLM API base URL
            api_key: Optional LLM API key
        """
        self.instance = instance
        self.model_name = model_name or instance.model_name or "gpt-4"
        self.steps: List[Dict[str, Any]] = []

        self.llm = LLMClientPool.get_llm(
            model_name=self.model_name,
            temperature=0.7,
            base_url=base_url,
            api_key=api_key,
            streaming=True,
        )

    @property
    def agent_id(self) -> Optional[str]:
        return self.instance.id

    @property
    def role(self) -> str:
        return self.instance.role

    @property
    def name(self) -> str:
        return self.instance.name

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the agent's core logic.

        Args:
            input_data: Arbitrary input provided by the orchestrator.

        Returns:
            Dict with the agent's output / result.
        """
        ...

    # ------------------------------------------------------------------
    # LLM helpers
    # ------------------------------------------------------------------

    async def invoke_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Call the LLM with a prompt and return the text response.

        Args:
            prompt: User/task prompt
            system_prompt: Optional system message (defaults to instance.system_prompt)
            history: Optional prior messages [{"role": "user"|"assistant", "content": "..."}]

        Returns:
            LLM response text
        """
        messages = []
        sys_msg = system_prompt or self.instance.system_prompt
        if sys_msg:
            messages.append(SystemMessage(content=sys_msg))

        if history:
            for msg in history:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))

        messages.append(HumanMessage(content=prompt))
        response = await self.llm.ainvoke(messages)
        return response.content

    async def invoke_llm_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> Any:
        """
        Call the LLM and parse the response as JSON.

        Handles markdown code fences around JSON.

        Args:
            prompt: User/task prompt
            system_prompt: Optional system message

        Returns:
            Parsed JSON (dict or list)

        Raises:
            json.JSONDecodeError: If response is not valid JSON
        """
        raw = await self.invoke_llm(prompt, system_prompt)
        content = raw.strip()
        # Strip markdown code fences
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        return json.loads(content.strip())

    # ------------------------------------------------------------------
    # Step recording (mirrors DeepResearchAgent pattern)
    # ------------------------------------------------------------------

    def record_step(
        self,
        step_type: str,
        content: str,
        status: str = "completed",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record an execution step for observability.

        Args:
            step_type: Category (thinking, searching, analyzing, tool_call, etc.)
            content: Human-readable description
            status: pending | running | completed | error
            metadata: Extra data

        Returns:
            The step dict
        """
        step = {
            "step_type": step_type,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "status": status,
            "metadata": metadata or {},
        }
        self.steps.append(step)
        return step

    def update_last_step(
        self,
        status: str = "completed",
        content: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update the most recently recorded step."""
        if not self.steps:
            return
        last = self.steps[-1]
        last["status"] = status
        if content:
            last["content"] = content
        if metadata:
            last["metadata"].update(metadata)

    # ------------------------------------------------------------------
    # Messaging helpers (delegate to domain model)
    # ------------------------------------------------------------------

    async def send_message(
        self,
        content: str,
        recipient_id: Optional[str] = None,
        message_type: str = "chat",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentMessage:
        """Send a message from this agent via the domain layer."""
        return await self.instance.send_message(
            content=content,
            recipient_id=recipient_id,
            message_type=message_type,
            metadata=metadata,
        )

    async def get_inbox(self, since: Optional[str] = None) -> List[AgentMessage]:
        """Fetch messages directed at (or broadcast to) this agent."""
        return await self.instance.get_inbox(since=since)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Full lifecycle wrapper: mark busy -> execute -> mark completed/failed.

        Args:
            input_data: Input for the agent

        Returns:
            Agent output dict
        """
        await self.instance.mark_busy()
        try:
            result = await self.execute(input_data)
            await self.instance.mark_completed(result)
            return result
        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            await self.instance.mark_failed(error_msg)
            raise
