"""
Messaging - Async message bus for inter-agent communication.

Provides an in-memory pub/sub message bus that agents use to communicate
within a team. Messages are also persisted via the AgentMessage domain model.

Key concepts:
- Each agent subscribes by its ID
- Broadcast messages (recipient_id=None) go to all subscribers except sender
- The bus supports async iteration so agents can poll their inbox
"""

import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from open_notebook.domain.agent_team import AgentMessage


class MessageBus:
    """
    In-memory async message bus for a single agent team.

    Messages are delivered through asyncio.Queue per subscriber.
    For persistence, callers should also save messages via AgentMessage.save().

    Usage::

        bus = MessageBus(team_id="team-123")
        bus.subscribe("agent-a")
        bus.subscribe("agent-b")

        # Send to specific agent
        await bus.send("agent-a", "agent-b", "Hello B", message_type="chat")

        # Broadcast
        await bus.broadcast("agent-a", "Status update", message_type="chat")

        # Receive
        msg = await bus.receive("agent-b", timeout=5.0)
    """

    def __init__(self, team_id: str):
        self.team_id = team_id
        self._queues: Dict[str, asyncio.Queue] = {}
        self._listeners: Dict[str, List[Callable]] = defaultdict(list)

    def subscribe(self, agent_id: str) -> None:
        """Register an agent to receive messages."""
        if agent_id not in self._queues:
            self._queues[agent_id] = asyncio.Queue()

    def unsubscribe(self, agent_id: str) -> None:
        """Remove an agent's subscription."""
        self._queues.pop(agent_id, None)
        self._listeners.pop(agent_id, None)

    def on_message(self, agent_id: str, callback: Callable) -> None:
        """
        Register a callback for incoming messages to an agent.

        The callback receives an AgentMessage and is awaited if async.
        """
        self._listeners[agent_id].append(callback)

    async def send(
        self,
        sender_id: str,
        recipient_id: str,
        content: str,
        message_type: str = "chat",
        metadata: Optional[Dict[str, Any]] = None,
        persist: bool = True,
    ) -> AgentMessage:
        """
        Send a message from one agent to another.

        Args:
            sender_id: Sending agent ID
            recipient_id: Receiving agent ID
            content: Message text
            message_type: Type of message
            metadata: Optional extra data
            persist: If True, save to database

        Returns:
            The created AgentMessage
        """
        import json

        msg = AgentMessage(
            team_id=self.team_id,
            sender_id=sender_id,
            recipient_id=recipient_id,
            message_type=message_type,
            content=content,
            metadata=json.dumps(metadata) if metadata else None,
        )

        if persist:
            await msg.save()

        # Deliver to recipient queue
        queue = self._queues.get(recipient_id)
        if queue is not None:
            await queue.put(msg)

        # Fire listeners
        for cb in self._listeners.get(recipient_id, []):
            if asyncio.iscoroutinefunction(cb):
                await cb(msg)
            else:
                cb(msg)

        return msg

    async def broadcast(
        self,
        sender_id: str,
        content: str,
        message_type: str = "chat",
        metadata: Optional[Dict[str, Any]] = None,
        persist: bool = True,
    ) -> AgentMessage:
        """
        Broadcast a message to all agents except the sender.

        Args:
            sender_id: Sending agent ID
            content: Message text
            message_type: Type of message
            metadata: Optional extra data
            persist: If True, save to database

        Returns:
            The created AgentMessage (recipient_id=None)
        """
        import json

        msg = AgentMessage(
            team_id=self.team_id,
            sender_id=sender_id,
            recipient_id=None,
            message_type=message_type,
            content=content,
            metadata=json.dumps(metadata) if metadata else None,
        )

        if persist:
            await msg.save()

        # Deliver to all queues except sender
        for agent_id, queue in self._queues.items():
            if agent_id != sender_id:
                await queue.put(msg)

        # Fire listeners for all except sender
        for agent_id, callbacks in self._listeners.items():
            if agent_id != sender_id:
                for cb in callbacks:
                    if asyncio.iscoroutinefunction(cb):
                        await cb(msg)
                    else:
                        cb(msg)

        return msg

    async def receive(
        self,
        agent_id: str,
        timeout: Optional[float] = None,
    ) -> Optional[AgentMessage]:
        """
        Receive the next message for an agent.

        Args:
            agent_id: Agent ID to receive for
            timeout: Max seconds to wait. None = wait forever, 0 = non-blocking.

        Returns:
            AgentMessage or None if timeout reached
        """
        queue = self._queues.get(agent_id)
        if queue is None:
            return None

        try:
            if timeout == 0:
                return queue.get_nowait()
            return await asyncio.wait_for(queue.get(), timeout=timeout)
        except (asyncio.TimeoutError, asyncio.QueueEmpty):
            return None

    async def drain(self, agent_id: str) -> List[AgentMessage]:
        """
        Receive all currently queued messages for an agent (non-blocking).

        Args:
            agent_id: Agent ID

        Returns:
            List of messages (may be empty)
        """
        messages = []
        queue = self._queues.get(agent_id)
        if queue is None:
            return messages
        while not queue.empty():
            try:
                messages.append(queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return messages

    def pending_count(self, agent_id: str) -> int:
        """Number of unread messages for an agent."""
        queue = self._queues.get(agent_id)
        return queue.qsize() if queue else 0

    def clear(self) -> None:
        """Clear all queues and listeners."""
        self._queues.clear()
        self._listeners.clear()
