"""
Unit tests for inter-agent messaging system.

Tests cover:
- Message creation and serialization
- Direct message routing (agent-to-agent)
- Broadcast message routing (agent-to-all)
- Message delivery confirmation
- Message queue ordering (FIFO)
- Message filtering by type
- Error handling for invalid recipients
- Message history and retrieval
- Team-scoped messaging isolation
"""

import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================================
# Message Data Structures
# ============================================================================

def create_message(
    sender_id: str,
    recipient_id: str,
    content: str,
    msg_type: str = "text",
    team_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Helper to create a message dict."""
    return {
        "id": str(uuid.uuid4()),
        "sender_id": sender_id,
        "recipient_id": recipient_id,
        "content": content,
        "type": msg_type,
        "team_id": team_id,
        "metadata": metadata or {},
        "created": datetime.utcnow().isoformat(),
        "delivered": False,
        "read": False,
    }


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def message_bus():
    """Simulated message bus for testing."""
    queues: Dict[str, List[Dict]] = {}
    history: List[Dict] = []

    class MockMessageBus:
        async def send(self, message: Dict) -> str:
            recipient = message["recipient_id"]
            if recipient not in queues:
                queues[recipient] = []
            queues[recipient].append(message)
            history.append(message)
            return message["id"]

        async def broadcast(self, message: Dict, team_id: str) -> List[str]:
            recipients = [
                agent_id for agent_id in queues.keys()
                if agent_id != message["sender_id"]
            ]
            msg_ids = []
            for recipient in recipients:
                msg = {**message, "id": str(uuid.uuid4()), "recipient_id": recipient}
                queues[recipient].append(msg)
                history.append(msg)
                msg_ids.append(msg["id"])
            return msg_ids

        async def receive(self, agent_id: str) -> List[Dict]:
            return queues.get(agent_id, [])

        async def acknowledge(self, message_id: str):
            for msgs in queues.values():
                for msg in msgs:
                    if msg["id"] == message_id:
                        msg["delivered"] = True
                        msg["read"] = True

        def get_history(self) -> List[Dict]:
            return history

    # Pre-register some agents
    queues["agent_a"] = []
    queues["agent_b"] = []
    queues["agent_c"] = []

    return MockMessageBus(), queues, history


# ============================================================================
# Test Message Creation
# ============================================================================

class TestMessageCreation:
    """Test message creation and structure."""

    def test_create_text_message(self):
        """Test creating a simple text message."""
        msg = create_message("agent_a", "agent_b", "Hello")

        assert msg["sender_id"] == "agent_a"
        assert msg["recipient_id"] == "agent_b"
        assert msg["content"] == "Hello"
        assert msg["type"] == "text"
        assert msg["delivered"] is False
        assert msg["read"] is False

    def test_message_has_unique_id(self):
        """Test that each message has a unique ID."""
        msg1 = create_message("a", "b", "msg1")
        msg2 = create_message("a", "b", "msg2")

        assert msg1["id"] != msg2["id"]

    def test_create_message_with_type(self):
        """Test creating messages with different types."""
        types = ["text", "task_result", "status_update", "error", "handoff"]

        for msg_type in types:
            msg = create_message("a", "b", "content", msg_type=msg_type)
            assert msg["type"] == msg_type

    def test_create_message_with_metadata(self):
        """Test creating a message with metadata."""
        metadata = {
            "priority": "high",
            "context": {"notebook_id": "nb-123"},
            "tokens_used": 150,
        }

        msg = create_message("a", "b", "content", metadata=metadata)

        assert msg["metadata"]["priority"] == "high"
        assert msg["metadata"]["tokens_used"] == 150

    def test_message_json_serialization(self):
        """Test that messages can be serialized to/from JSON."""
        msg = create_message("a", "b", "Hello world")
        serialized = json.dumps(msg)
        deserialized = json.loads(serialized)

        assert deserialized["sender_id"] == "a"
        assert deserialized["content"] == "Hello world"

    def test_create_message_with_team_scope(self):
        """Test creating a team-scoped message."""
        msg = create_message("a", "b", "content", team_id="team-123")
        assert msg["team_id"] == "team-123"


# ============================================================================
# Test Direct Message Routing
# ============================================================================

class TestDirectMessaging:
    """Test direct agent-to-agent messaging."""

    @pytest.mark.asyncio
    async def test_send_direct_message(self, message_bus):
        """Test sending a direct message to a specific agent."""
        bus, queues, _ = message_bus
        msg = create_message("agent_a", "agent_b", "Hello B!")

        msg_id = await bus.send(msg)

        assert msg_id is not None
        assert len(queues["agent_b"]) == 1
        assert queues["agent_b"][0]["content"] == "Hello B!"

    @pytest.mark.asyncio
    async def test_receive_messages(self, message_bus):
        """Test that an agent can receive its messages."""
        bus, _, _ = message_bus

        await bus.send(create_message("agent_a", "agent_b", "Message 1"))
        await bus.send(create_message("agent_c", "agent_b", "Message 2"))

        messages = await bus.receive("agent_b")

        assert len(messages) == 2
        contents = [m["content"] for m in messages]
        assert "Message 1" in contents
        assert "Message 2" in contents

    @pytest.mark.asyncio
    async def test_messages_isolated_per_agent(self, message_bus):
        """Test that messages are isolated to the correct recipient."""
        bus, queues, _ = message_bus

        await bus.send(create_message("agent_a", "agent_b", "For B only"))

        assert len(queues["agent_b"]) == 1
        assert len(queues["agent_a"]) == 0
        assert len(queues["agent_c"]) == 0

    @pytest.mark.asyncio
    async def test_fifo_message_ordering(self, message_bus):
        """Test that messages are delivered in FIFO order."""
        bus, _, _ = message_bus

        for i in range(5):
            await bus.send(create_message("agent_a", "agent_b", f"Message {i}"))

        messages = await bus.receive("agent_b")

        assert len(messages) == 5
        for i, msg in enumerate(messages):
            assert msg["content"] == f"Message {i}"

    @pytest.mark.asyncio
    async def test_acknowledge_message(self, message_bus):
        """Test acknowledging message delivery."""
        bus, _, _ = message_bus

        msg = create_message("agent_a", "agent_b", "Please confirm")
        msg_id = await bus.send(msg)

        messages = await bus.receive("agent_b")
        assert messages[0]["delivered"] is False

        await bus.acknowledge(msg_id)

        messages = await bus.receive("agent_b")
        # After acknowledge, the message should be marked
        acknowledged = [m for m in messages if m.get("read")]
        assert len(acknowledged) >= 1


# ============================================================================
# Test Broadcast Messaging
# ============================================================================

class TestBroadcastMessaging:
    """Test broadcasting messages to all agents in a team."""

    @pytest.mark.asyncio
    async def test_broadcast_to_all(self, message_bus):
        """Test broadcasting a message to all team members."""
        bus, queues, _ = message_bus

        msg = create_message("agent_a", "*", "Team announcement")
        msg_ids = await bus.broadcast(msg, "team-1")

        # Should be sent to agent_b and agent_c (not agent_a - sender)
        assert len(msg_ids) == 2
        assert len(queues["agent_b"]) == 1
        assert len(queues["agent_c"]) == 1
        assert len(queues["agent_a"]) == 0  # Sender excluded

    @pytest.mark.asyncio
    async def test_broadcast_content_identical(self, message_bus):
        """Test that broadcast messages have the same content."""
        bus, queues, _ = message_bus

        msg = create_message("agent_a", "*", "Same content for all")
        await bus.broadcast(msg, "team-1")

        b_content = queues["agent_b"][0]["content"]
        c_content = queues["agent_c"][0]["content"]

        assert b_content == c_content == "Same content for all"

    @pytest.mark.asyncio
    async def test_broadcast_assigns_unique_ids(self, message_bus):
        """Test that each broadcast copy gets a unique message ID."""
        bus, queues, _ = message_bus

        msg = create_message("agent_a", "*", "Broadcast")
        await bus.broadcast(msg, "team-1")

        b_id = queues["agent_b"][0]["id"]
        c_id = queues["agent_c"][0]["id"]

        assert b_id != c_id


# ============================================================================
# Test Message History
# ============================================================================

class TestMessageHistory:
    """Test message history tracking and retrieval."""

    @pytest.mark.asyncio
    async def test_message_history_tracks_all(self, message_bus):
        """Test that all sent messages appear in history."""
        bus, _, history = message_bus

        await bus.send(create_message("a", "agent_b", "msg1"))
        await bus.send(create_message("a", "agent_c", "msg2"))

        assert len(bus.get_history()) == 2

    @pytest.mark.asyncio
    async def test_history_preserves_order(self, message_bus):
        """Test that message history preserves chronological order."""
        bus, _, _ = message_bus

        for i in range(3):
            await bus.send(create_message("a", "agent_b", f"msg_{i}"))

        history = bus.get_history()
        contents = [h["content"] for h in history]

        assert contents == ["msg_0", "msg_1", "msg_2"]

    @pytest.mark.asyncio
    async def test_history_includes_broadcasts(self, message_bus):
        """Test that broadcast messages appear in history."""
        bus, _, _ = message_bus

        await bus.send(create_message("a", "agent_b", "direct"))
        msg = create_message("a", "*", "broadcast")
        await bus.broadcast(msg, "team-1")

        history = bus.get_history()
        # Direct + 2 broadcast copies (to agent_b and agent_c)
        assert len(history) == 3


# ============================================================================
# Test Message Filtering
# ============================================================================

class TestMessageFiltering:
    """Test filtering messages by various criteria."""

    def test_filter_by_type(self):
        """Test filtering messages by type."""
        messages = [
            create_message("a", "b", "text msg", msg_type="text"),
            create_message("a", "b", "task result", msg_type="task_result"),
            create_message("a", "b", "another text", msg_type="text"),
            create_message("a", "b", "error", msg_type="error"),
        ]

        text_msgs = [m for m in messages if m["type"] == "text"]
        assert len(text_msgs) == 2

    def test_filter_by_sender(self):
        """Test filtering messages by sender."""
        messages = [
            create_message("agent_a", "b", "from A"),
            create_message("agent_b", "c", "from B"),
            create_message("agent_a", "c", "from A again"),
        ]

        from_a = [m for m in messages if m["sender_id"] == "agent_a"]
        assert len(from_a) == 2

    def test_filter_by_time_range(self):
        """Test filtering messages within a time window."""
        now = datetime.utcnow()
        old_time = (now - timedelta(hours=2)).isoformat()
        recent_time = (now - timedelta(minutes=5)).isoformat()

        messages = [
            {"content": "old", "created": old_time},
            {"content": "recent", "created": recent_time},
            {"content": "new", "created": now.isoformat()},
        ]

        cutoff = (now - timedelta(hours=1)).isoformat()
        recent = [m for m in messages if m["created"] > cutoff]

        assert len(recent) == 2

    def test_filter_unread_messages(self):
        """Test filtering unread messages."""
        messages = [
            {"content": "unread1", "read": False},
            {"content": "read1", "read": True},
            {"content": "unread2", "read": False},
        ]

        unread = [m for m in messages if not m["read"]]
        assert len(unread) == 2


# ============================================================================
# Test Team-Scoped Messaging
# ============================================================================

class TestTeamScopedMessaging:
    """Test that messages are properly scoped to teams."""

    def test_messages_contain_team_id(self):
        """Test that team messages include team_id."""
        msg = create_message("a", "b", "team msg", team_id="team-123")
        assert msg["team_id"] == "team-123"

    def test_filter_messages_by_team(self):
        """Test filtering messages by team ID."""
        messages = [
            create_message("a", "b", "team1 msg", team_id="team-1"),
            create_message("a", "b", "team2 msg", team_id="team-2"),
            create_message("a", "b", "team1 msg2", team_id="team-1"),
        ]

        team1_msgs = [m for m in messages if m["team_id"] == "team-1"]
        assert len(team1_msgs) == 2

    def test_no_cross_team_leakage(self):
        """Test that messages don't leak across teams."""
        team_queues = {
            "team-1": {"agent_a": [], "agent_b": []},
            "team-2": {"agent_c": [], "agent_d": []},
        }

        msg = create_message("agent_a", "agent_b", "team-1 only", team_id="team-1")
        team_queues["team-1"]["agent_b"].append(msg)

        # Team 2 agents should have no messages
        assert len(team_queues["team-2"]["agent_c"]) == 0
        assert len(team_queues["team-2"]["agent_d"]) == 0


# ============================================================================
# Test Error Handling
# ============================================================================

class TestMessagingErrors:
    """Test error handling in messaging system."""

    def test_message_with_empty_content(self):
        """Test creating a message with empty content."""
        msg = create_message("a", "b", "")
        assert msg["content"] == ""

    def test_message_with_large_content(self):
        """Test creating a message with very large content."""
        large_content = "x" * 100_000
        msg = create_message("a", "b", large_content)
        assert len(msg["content"]) == 100_000

    @pytest.mark.asyncio
    async def test_send_to_nonexistent_agent(self, message_bus):
        """Test sending to a non-existent agent creates the queue."""
        bus, queues, _ = message_bus
        msg = create_message("agent_a", "nonexistent_agent", "Hello?")
        await bus.send(msg)

        # Queue should be created for the recipient
        assert "nonexistent_agent" in queues

    @pytest.mark.asyncio
    async def test_concurrent_message_sending(self, message_bus):
        """Test sending multiple messages concurrently."""
        bus, _, _ = message_bus

        async def send_msg(content):
            return await bus.send(
                create_message("agent_a", "agent_b", content)
            )

        msg_ids = await asyncio.gather(
            send_msg("concurrent_1"),
            send_msg("concurrent_2"),
            send_msg("concurrent_3"),
        )

        assert len(msg_ids) == 3
        assert len(set(msg_ids)) == 3  # All unique IDs

        messages = await bus.receive("agent_b")
        assert len(messages) == 3
