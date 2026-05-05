"""
Integration tests for Phase 1 - Agent coordination infrastructure.

Tests the actual domain models (AgentTeam, AgentInstance, AgentMessage, AgentTask),
the MessageBus in-memory messaging, and the TaskManager with real SQLite database.

These tests use a real SQLite database (not mocks) to validate the full
domain model lifecycle through the repository layer.
"""

import asyncio
import json
import os
import tempfile
from typing import AsyncGenerator

import pytest

from open_notebook.database.interface import ConnectionConfig
from open_notebook.database.sqlite_impl import SQLiteDatabase
from open_notebook.domain.agent_team import (
    AgentInstance,
    AgentMessage,
    AgentTask,
    AgentTeam,
)
from open_notebook.agents.messaging import MessageBus
from open_notebook.agents.task_manager import DependencyCycleError, TaskManager


# ============================================================================
# Fixtures
# ============================================================================

AGENT_TEAMS_SCHEMA = """
CREATE TABLE IF NOT EXISTS notebooks (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    archived BOOLEAN DEFAULT FALSE,
    folder_id VARCHAR(36),
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id VARCHAR(36) PRIMARY KEY,
    title VARCHAR(255),
    notebook_id VARCHAR(36),
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS agent_teams (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    goal TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    notebook_id TEXT,
    session_id TEXT,
    config TEXT,
    result TEXT,
    error TEXT,
    started_at TEXT,
    completed_at TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE SET NULL,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS agent_instances (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    role TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'idle',
    model_name TEXT,
    system_prompt TEXT,
    config TEXT,
    result TEXT,
    error TEXT,
    started_at TEXT,
    completed_at TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS agent_messages (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    sender_id TEXT NOT NULL,
    recipient_id TEXT,
    message_type TEXT NOT NULL DEFAULT 'chat',
    content TEXT NOT NULL,
    metadata TEXT,
    created TEXT NOT NULL,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS agent_tasks (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    assignee_id TEXT,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    priority INTEGER NOT NULL DEFAULT 0,
    result TEXT,
    error TEXT,
    depends_on TEXT,
    started_at TEXT,
    completed_at TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE,
    FOREIGN KEY (assignee_id) REFERENCES agent_instances(id) ON DELETE SET NULL
);
"""

TEST_DB_DIR = tempfile.mkdtemp()


@pytest.fixture
async def agent_db(monkeypatch):
    """
    Provide a clean SQLite database with agent_teams schema.
    Patches get_database so the repository layer uses this DB instance.
    Also patches db_connection to reuse the same instance without
    connect/disconnect cycling.
    """
    test_db_path = os.path.join(
        TEST_DB_DIR, f"test_phase1_{id(asyncio.current_task())}.db"
    )

    config = ConnectionConfig(db_type="sqlite", db_path=test_db_path)
    db = SQLiteDatabase(config)
    await db.connect()

    # Create schema
    import aiosqlite

    async with aiosqlite.connect(test_db_path) as raw_db:
        await raw_db.executescript(AGENT_TEAMS_SCHEMA)

    # Patch db_connection to yield our pre-connected instance without cycling
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _mock_db_connection():
        yield db

    monkeypatch.setattr(
        "open_notebook.database.repository.db_connection", _mock_db_connection
    )

    yield db

    await db.disconnect()
    if os.path.exists(test_db_path):
        os.remove(test_db_path)


# ============================================================================
# Test AgentTeam Domain Model
# ============================================================================


class TestAgentTeamDomain:
    """Test AgentTeam CRUD and lifecycle methods."""

    @pytest.mark.asyncio
    async def test_create_team(self, agent_db):
        team = AgentTeam(name="Research Team", goal="Analyze data")
        team_id = await team.save()

        assert team_id is not None
        assert team.id == team_id
        assert team.status == "pending"
        assert team.created is not None

    @pytest.mark.asyncio
    async def test_get_team_by_id(self, agent_db):
        team = AgentTeam(name="Lookup Team", goal="Test retrieval")
        await team.save()

        fetched = await AgentTeam.get(team.id)
        assert fetched is not None
        assert fetched.name == "Lookup Team"
        assert fetched.goal == "Test retrieval"

    @pytest.mark.asyncio
    async def test_get_nonexistent_team(self, agent_db):
        fetched = await AgentTeam.get("nonexistent-id")
        assert fetched is None

    @pytest.mark.asyncio
    async def test_team_lifecycle_running(self, agent_db):
        team = AgentTeam(name="Lifecycle Team")
        await team.save()

        await team.mark_running()
        assert team.status == "running"
        assert team.started_at is not None

        refreshed = await AgentTeam.get(team.id)
        assert refreshed.status == "running"

    @pytest.mark.asyncio
    async def test_team_lifecycle_completed(self, agent_db):
        team = AgentTeam(name="Complete Team")
        await team.save()

        await team.mark_running()
        await team.mark_completed(result={"summary": "All done"})

        assert team.status == "completed"
        assert team.completed_at is not None
        assert team.get_result() == {"summary": "All done"}

    @pytest.mark.asyncio
    async def test_team_lifecycle_failed(self, agent_db):
        team = AgentTeam(name="Failing Team")
        await team.save()

        await team.mark_running()
        await team.mark_failed("Something broke")

        assert team.status == "failed"
        assert team.error == "Something broke"
        assert team.completed_at is not None

    @pytest.mark.asyncio
    async def test_team_config_json(self, agent_db):
        team = AgentTeam(name="Config Team")
        team.set_config({"max_iterations": 5, "model": "gpt-4"})
        await team.save()

        fetched = await AgentTeam.get(team.id)
        cfg = fetched.get_config()
        assert cfg["max_iterations"] == 5
        assert cfg["model"] == "gpt-4"

    @pytest.mark.asyncio
    async def test_team_config_empty(self, agent_db):
        team = AgentTeam(name="No Config")
        await team.save()
        assert team.get_config() == {}

    @pytest.mark.asyncio
    async def test_team_result_string(self, agent_db):
        team = AgentTeam(name="String Result")
        team.set_result("plain text result")
        await team.save()

        fetched = await AgentTeam.get(team.id)
        assert fetched.get_result() == "plain text result"

    @pytest.mark.asyncio
    async def test_team_result_none(self, agent_db):
        team = AgentTeam(name="No Result")
        team.set_result(None)
        assert team.result is None
        assert team.get_result() is None

    @pytest.mark.asyncio
    async def test_get_active_teams(self, agent_db):
        t1 = AgentTeam(name="Running 1")
        await t1.save()
        await t1.mark_running()

        t2 = AgentTeam(name="Pending 1")
        await t2.save()

        t3 = AgentTeam(name="Running 2")
        await t3.save()
        await t3.mark_running()

        active = await AgentTeam.get_active()
        assert len(active) == 2
        names = {t.name for t in active}
        assert "Running 1" in names
        assert "Running 2" in names

    @pytest.mark.asyncio
    async def test_team_get_all(self, agent_db):
        for i in range(3):
            t = AgentTeam(name=f"Team {i}")
            await t.save()

        all_teams = await AgentTeam.get_all()
        assert len(all_teams) == 3

    @pytest.mark.asyncio
    async def test_team_delete(self, agent_db):
        team = AgentTeam(name="Deletable")
        await team.save()
        team_id = team.id

        await team.delete()

        deleted = await AgentTeam.get(team_id)
        assert deleted is None

    @pytest.mark.asyncio
    async def test_team_count(self, agent_db):
        for i in range(4):
            t = AgentTeam(name=f"Count {i}")
            await t.save()

        total = await AgentTeam.count()
        assert total == 4


# ============================================================================
# Test AgentInstance Domain Model
# ============================================================================


class TestAgentInstanceDomain:
    """Test AgentInstance CRUD and lifecycle methods."""

    @pytest.fixture
    async def team(self, agent_db):
        team = AgentTeam(name="Instance Team")
        await team.save()
        return team

    @pytest.mark.asyncio
    async def test_create_agent_instance(self, team):
        agent = AgentInstance(
            team_id=team.id,
            role="researcher",
            name="Research Agent",
            model_name="gpt-4",
        )
        await agent.save()

        assert agent.id is not None
        assert agent.status == "idle"

    @pytest.mark.asyncio
    async def test_get_agent_instance(self, team):
        agent = AgentInstance(team_id=team.id, role="analyst", name="Analyst")
        await agent.save()

        fetched = await AgentInstance.get(agent.id)
        assert fetched is not None
        assert fetched.role == "analyst"
        assert fetched.name == "Analyst"

    @pytest.mark.asyncio
    async def test_agent_lifecycle_busy(self, team):
        agent = AgentInstance(team_id=team.id, role="worker", name="Worker")
        await agent.save()

        await agent.mark_busy()
        assert agent.status == "busy"
        assert agent.started_at is not None

    @pytest.mark.asyncio
    async def test_agent_lifecycle_completed(self, team):
        agent = AgentInstance(team_id=team.id, role="worker", name="Worker")
        await agent.save()

        await agent.mark_busy()
        await agent.mark_completed(result={"output": "done"})

        assert agent.status == "completed"
        assert agent.get_result() == {"output": "done"}

    @pytest.mark.asyncio
    async def test_agent_lifecycle_failed(self, team):
        agent = AgentInstance(team_id=team.id, role="worker", name="Worker")
        await agent.save()

        await agent.mark_busy()
        await agent.mark_failed("timeout")

        assert agent.status == "failed"
        assert agent.error == "timeout"

    @pytest.mark.asyncio
    async def test_team_get_agents(self, team):
        for role in ["researcher", "analyst", "synthesizer"]:
            a = AgentInstance(team_id=team.id, role=role, name=f"{role}_agent")
            await a.save()

        agents = await team.get_agents()
        assert len(agents) == 3
        roles = {a.role for a in agents}
        assert roles == {"researcher", "analyst", "synthesizer"}

    @pytest.mark.asyncio
    async def test_agent_config_json(self, team):
        agent = AgentInstance(team_id=team.id, role="custom", name="Custom")
        agent.set_config({"temperature": 0.2, "tools": ["search", "query"]})
        await agent.save()

        fetched = await AgentInstance.get(agent.id)
        cfg = fetched.get_config()
        assert cfg["temperature"] == 0.2
        assert "search" in cfg["tools"]

    @pytest.mark.asyncio
    async def test_agent_system_prompt(self, team):
        agent = AgentInstance(
            team_id=team.id,
            role="researcher",
            name="Researcher",
            system_prompt="You are a research assistant.",
        )
        await agent.save()

        fetched = await AgentInstance.get(agent.id)
        assert fetched.system_prompt == "You are a research assistant."


# ============================================================================
# Test AgentMessage Domain Model
# ============================================================================


class TestAgentMessageDomain:
    """Test AgentMessage CRUD and querying."""

    @pytest.fixture
    async def team_with_agents(self, agent_db):
        team = AgentTeam(name="Msg Team")
        await team.save()

        a1 = AgentInstance(team_id=team.id, role="sender", name="Sender")
        await a1.save()

        a2 = AgentInstance(team_id=team.id, role="receiver", name="Receiver")
        await a2.save()

        return team, a1, a2

    @pytest.mark.asyncio
    async def test_create_message(self, team_with_agents):
        team, sender, receiver = team_with_agents

        msg = AgentMessage(
            team_id=team.id,
            sender_id=sender.id,
            recipient_id=receiver.id,
            content="Hello!",
            message_type="chat",
        )
        await msg.save()

        assert msg.id is not None
        assert msg.created is not None

    @pytest.mark.asyncio
    async def test_send_message_via_agent(self, team_with_agents):
        team, sender, receiver = team_with_agents

        msg = await sender.send_message(
            content="Task update",
            recipient_id=receiver.id,
            message_type="task_result",
            metadata={"task_id": "t-123"},
        )

        assert msg.id is not None
        assert msg.sender_id == sender.id
        assert msg.recipient_id == receiver.id
        assert msg.message_type == "task_result"
        meta = msg.get_metadata()
        assert meta["task_id"] == "t-123"

    @pytest.mark.asyncio
    async def test_broadcast_message(self, team_with_agents):
        team, sender, _ = team_with_agents

        msg = AgentMessage(
            team_id=team.id,
            sender_id=sender.id,
            recipient_id=None,
            content="Broadcast!",
        )
        await msg.save()

        assert msg.recipient_id is None

    @pytest.mark.asyncio
    async def test_get_team_messages(self, team_with_agents):
        team, sender, receiver = team_with_agents

        for i in range(5):
            await sender.send_message(content=f"msg {i}", recipient_id=receiver.id)

        messages = await team.get_messages()
        assert len(messages) == 5
        assert messages[0].content == "msg 0"

    @pytest.mark.asyncio
    async def test_agent_inbox(self, team_with_agents):
        team, sender, receiver = team_with_agents

        await sender.send_message(content="Direct msg", recipient_id=receiver.id)
        await sender.send_message(content="Broadcast", recipient_id=None)

        inbox = await receiver.get_inbox()
        # Should get direct message + broadcast
        assert len(inbox) == 2

    @pytest.mark.asyncio
    async def test_message_metadata_parsing(self, team_with_agents):
        team, sender, receiver = team_with_agents

        msg = AgentMessage(
            team_id=team.id,
            sender_id=sender.id,
            content="with meta",
            metadata=json.dumps({"key": "value", "count": 42}),
        )
        await msg.save()

        fetched = await AgentMessage.get(msg.id)
        meta = fetched.get_metadata()
        assert meta["key"] == "value"
        assert meta["count"] == 42

    @pytest.mark.asyncio
    async def test_message_empty_metadata(self, team_with_agents):
        team, sender, _ = team_with_agents

        msg = AgentMessage(
            team_id=team.id,
            sender_id=sender.id,
            content="no meta",
        )
        await msg.save()
        assert msg.get_metadata() == {}


# ============================================================================
# Test AgentTask Domain Model
# ============================================================================


class TestAgentTaskDomain:
    """Test AgentTask CRUD, dependency tracking, and lifecycle."""

    @pytest.fixture
    async def team(self, agent_db):
        team = AgentTeam(name="Task Team")
        await team.save()
        return team

    @pytest.mark.asyncio
    async def test_create_task(self, team):
        task = AgentTask(
            team_id=team.id,
            title="Research topic",
            description="Find papers on X",
            priority=1,
        )
        await task.save()

        assert task.id is not None
        assert task.status == "pending"
        assert task.priority == 1

    @pytest.mark.asyncio
    async def test_task_dependency_ids(self, team):
        task = AgentTask(team_id=team.id, title="Dep test")
        task.set_dependency_ids(["id-1", "id-2", "id-3"])
        await task.save()

        fetched = await AgentTask.get(task.id)
        deps = fetched.get_dependency_ids()
        assert deps == ["id-1", "id-2", "id-3"]

    @pytest.mark.asyncio
    async def test_task_no_dependencies(self, team):
        task = AgentTask(team_id=team.id, title="No deps")
        await task.save()
        assert task.get_dependency_ids() == []

    @pytest.mark.asyncio
    async def test_task_is_blocked(self, team):
        t1 = AgentTask(team_id=team.id, title="Blocker")
        await t1.save()

        t2 = AgentTask(team_id=team.id, title="Blocked")
        t2.set_dependency_ids([t1.id])
        await t2.save()

        assert await t2.is_blocked() is True

        # Complete the blocker
        await t1.mark_completed()

        assert await t2.is_blocked() is False

    @pytest.mark.asyncio
    async def test_task_assign(self, team):
        agent = AgentInstance(team_id=team.id, role="worker", name="W")
        await agent.save()

        task = AgentTask(team_id=team.id, title="Assignable")
        await task.save()

        await task.assign(agent.id)
        assert task.status == "in_progress"
        assert task.assignee_id == agent.id
        assert task.started_at is not None

    @pytest.mark.asyncio
    async def test_task_mark_completed(self, team):
        task = AgentTask(team_id=team.id, title="Completable")
        await task.save()

        await task.mark_completed(result={"answer": 42})
        assert task.status == "completed"
        assert task.get_result() == {"answer": 42}
        assert task.completed_at is not None

    @pytest.mark.asyncio
    async def test_task_mark_failed(self, team):
        task = AgentTask(team_id=team.id, title="Failable")
        await task.save()

        await task.mark_failed("LLM rate limit")
        assert task.status == "failed"
        assert task.error == "LLM rate limit"

    @pytest.mark.asyncio
    async def test_get_ready_tasks(self, team):
        t1 = AgentTask(team_id=team.id, title="First")
        await t1.save()

        t2 = AgentTask(team_id=team.id, title="Second")
        t2.set_dependency_ids([t1.id])
        await t2.save()

        t3 = AgentTask(team_id=team.id, title="Independent")
        await t3.save()

        ready = await AgentTask.get_ready_tasks(team.id)
        titles = {t.title for t in ready}
        assert "First" in titles
        assert "Independent" in titles
        assert "Second" not in titles

    @pytest.mark.asyncio
    async def test_get_ready_tasks_after_completion(self, team):
        t1 = AgentTask(team_id=team.id, title="Dep")
        await t1.save()

        t2 = AgentTask(team_id=team.id, title="Downstream")
        t2.set_dependency_ids([t1.id])
        await t2.save()

        # Before completion
        ready = await AgentTask.get_ready_tasks(team.id)
        assert len(ready) == 1
        assert ready[0].title == "Dep"

        # After completion
        await t1.mark_completed()
        ready = await AgentTask.get_ready_tasks(team.id)
        titles = {t.title for t in ready}
        assert "Downstream" in titles

    @pytest.mark.asyncio
    async def test_team_get_tasks(self, team):
        for i in range(3):
            t = AgentTask(team_id=team.id, title=f"Task {i}")
            await t.save()

        tasks = await team.get_tasks()
        assert len(tasks) == 3

    @pytest.mark.asyncio
    async def test_team_get_tasks_filtered(self, team):
        t1 = AgentTask(team_id=team.id, title="Pending")
        await t1.save()

        t2 = AgentTask(team_id=team.id, title="Done")
        await t2.save()
        await t2.mark_completed()

        pending = await team.get_tasks(status="pending")
        assert len(pending) == 1
        assert pending[0].title == "Pending"

    @pytest.mark.asyncio
    async def test_task_result_json(self, team):
        task = AgentTask(team_id=team.id, title="JSON result")
        task.set_result({"data": [1, 2, 3], "meta": {"source": "llm"}})
        await task.save()

        fetched = await AgentTask.get(task.id)
        r = fetched.get_result()
        assert r["data"] == [1, 2, 3]
        assert r["meta"]["source"] == "llm"

    @pytest.mark.asyncio
    async def test_task_result_string(self, team):
        task = AgentTask(team_id=team.id, title="String result")
        task.set_result("just a string")
        await task.save()

        fetched = await AgentTask.get(task.id)
        assert fetched.get_result() == "just a string"


# ============================================================================
# Test MessageBus (In-memory, no DB persistence)
# ============================================================================


class TestMessageBusInMemory:
    """Test the MessageBus in-memory pub/sub without database persistence."""

    @pytest.mark.asyncio
    async def test_subscribe_and_send(self, agent_db):
        bus = MessageBus(team_id="test-team")
        bus.subscribe("a")
        bus.subscribe("b")

        await bus.send("a", "b", "Hello B", persist=False)

        msg = await bus.receive("b", timeout=1.0)
        assert msg is not None
        assert msg.content == "Hello B"
        assert msg.sender_id == "a"

    @pytest.mark.asyncio
    async def test_broadcast(self, agent_db):
        bus = MessageBus(team_id="test-team")
        bus.subscribe("a")
        bus.subscribe("b")
        bus.subscribe("c")

        await bus.broadcast("a", "Announcement", persist=False)

        msg_b = await bus.receive("b", timeout=1.0)
        msg_c = await bus.receive("c", timeout=1.0)
        msg_a = await bus.receive("a", timeout=0)

        assert msg_b is not None
        assert msg_b.content == "Announcement"
        assert msg_c is not None
        assert msg_c.content == "Announcement"
        assert msg_a is None  # Sender excluded

    @pytest.mark.asyncio
    async def test_receive_timeout(self, agent_db):
        bus = MessageBus(team_id="test-team")
        bus.subscribe("a")

        msg = await bus.receive("a", timeout=0.05)
        assert msg is None

    @pytest.mark.asyncio
    async def test_receive_nonblocking(self, agent_db):
        bus = MessageBus(team_id="test-team")
        bus.subscribe("a")

        msg = await bus.receive("a", timeout=0)
        assert msg is None

    @pytest.mark.asyncio
    async def test_drain(self, agent_db):
        bus = MessageBus(team_id="test-team")
        bus.subscribe("a")
        bus.subscribe("b")

        await bus.send("a", "b", "msg1", persist=False)
        await bus.send("a", "b", "msg2", persist=False)
        await bus.send("a", "b", "msg3", persist=False)

        messages = await bus.drain("b")
        assert len(messages) == 3
        assert messages[0].content == "msg1"
        assert messages[2].content == "msg3"

    @pytest.mark.asyncio
    async def test_drain_empty(self, agent_db):
        bus = MessageBus(team_id="test-team")
        bus.subscribe("a")

        messages = await bus.drain("a")
        assert messages == []

    @pytest.mark.asyncio
    async def test_pending_count(self, agent_db):
        bus = MessageBus(team_id="test-team")
        bus.subscribe("a")
        bus.subscribe("b")

        await bus.send("a", "b", "one", persist=False)
        await bus.send("a", "b", "two", persist=False)

        assert bus.pending_count("b") == 2
        assert bus.pending_count("a") == 0

    @pytest.mark.asyncio
    async def test_unsubscribe(self, agent_db):
        bus = MessageBus(team_id="test-team")
        bus.subscribe("a")
        bus.subscribe("b")

        bus.unsubscribe("b")

        await bus.send("a", "b", "after unsub", persist=False)
        msg = await bus.receive("b", timeout=0)
        assert msg is None

    @pytest.mark.asyncio
    async def test_on_message_callback(self, agent_db):
        bus = MessageBus(team_id="test-team")
        bus.subscribe("a")
        bus.subscribe("b")

        received = []
        bus.on_message("b", lambda m: received.append(m))

        await bus.send("a", "b", "callback test", persist=False)

        assert len(received) == 1
        assert received[0].content == "callback test"

    @pytest.mark.asyncio
    async def test_on_message_async_callback(self, agent_db):
        bus = MessageBus(team_id="test-team")
        bus.subscribe("a")
        bus.subscribe("b")

        received = []

        async def async_handler(msg):
            received.append(msg.content)

        bus.on_message("b", async_handler)

        await bus.send("a", "b", "async cb", persist=False)

        assert received == ["async cb"]

    @pytest.mark.asyncio
    async def test_clear(self, agent_db):
        bus = MessageBus(team_id="test-team")
        bus.subscribe("a")
        bus.subscribe("b")

        bus.clear()

        assert bus.pending_count("a") == 0
        msg = await bus.receive("a", timeout=0)
        assert msg is None

    @pytest.mark.asyncio
    async def test_unsubscribed_agent_receive(self, agent_db):
        bus = MessageBus(team_id="test-team")
        # No subscription
        msg = await bus.receive("unknown", timeout=0)
        assert msg is None

    @pytest.mark.asyncio
    async def test_drain_unsubscribed(self, agent_db):
        bus = MessageBus(team_id="test-team")
        messages = await bus.drain("nobody")
        assert messages == []


# ============================================================================
# Test TaskManager with Real Database
# ============================================================================


class TestTaskManagerIntegration:
    """Test TaskManager using real SQLite-backed domain models."""

    @pytest.fixture
    async def team_and_mgr(self, agent_db):
        team = AgentTeam(name="TM Team")
        await team.save()
        mgr = TaskManager(team_id=team.id)
        return team, mgr

    @pytest.mark.asyncio
    async def test_create_task(self, team_and_mgr):
        team, mgr = team_and_mgr
        task = await mgr.create_task("Research topic", description="Find papers")

        assert task.id is not None
        assert task.title == "Research topic"
        assert task.status == "pending"
        assert task.team_id == team.id

    @pytest.mark.asyncio
    async def test_create_task_with_priority(self, team_and_mgr):
        _, mgr = team_and_mgr
        task = await mgr.create_task("Critical", priority=2)
        assert task.priority == 2

    @pytest.mark.asyncio
    async def test_ready_tasks_no_deps(self, team_and_mgr):
        _, mgr = team_and_mgr
        t1 = await mgr.create_task("A")
        t2 = await mgr.create_task("B")

        ready = await mgr.get_ready_tasks()
        assert len(ready) == 2

    @pytest.mark.asyncio
    async def test_ready_tasks_with_deps(self, team_and_mgr):
        _, mgr = team_and_mgr
        t1 = await mgr.create_task("First")
        t2 = await mgr.create_task("Second", depends_on=[t1.id])

        ready = await mgr.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == t1.id

    @pytest.mark.asyncio
    async def test_complete_unblocks_downstream(self, team_and_mgr):
        _, mgr = team_and_mgr
        t1 = await mgr.create_task("Blocker")
        t2 = await mgr.create_task("Blocked", depends_on=[t1.id])

        await mgr.complete_task(t1.id, result="done")

        ready = await mgr.get_ready_tasks()
        ids = {t.id for t in ready}
        assert t2.id in ids

    @pytest.mark.asyncio
    async def test_chain_dependencies(self, team_and_mgr):
        _, mgr = team_and_mgr
        t1 = await mgr.create_task("Step 1")
        t2 = await mgr.create_task("Step 2", depends_on=[t1.id])
        t3 = await mgr.create_task("Step 3", depends_on=[t2.id])

        # Only t1 is ready
        ready = await mgr.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == t1.id

        # Complete t1 -> t2 ready
        await mgr.complete_task(t1.id)
        ready = await mgr.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == t2.id

        # Complete t2 -> t3 ready
        await mgr.complete_task(t2.id)
        ready = await mgr.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == t3.id

    @pytest.mark.asyncio
    async def test_diamond_dependencies(self, team_and_mgr):
        _, mgr = team_and_mgr
        t1 = await mgr.create_task("Root")
        t2 = await mgr.create_task("Branch A", depends_on=[t1.id])
        t3 = await mgr.create_task("Branch B", depends_on=[t1.id])
        t4 = await mgr.create_task("Merge", depends_on=[t2.id, t3.id])

        # Only t1 ready
        ready = await mgr.get_ready_tasks()
        assert len(ready) == 1

        # Complete t1 -> t2 and t3 ready
        await mgr.complete_task(t1.id)
        ready = await mgr.get_ready_tasks()
        assert len(ready) == 2

        # Complete t2 -> t4 still blocked by t3
        await mgr.complete_task(t2.id)
        ready = await mgr.get_ready_tasks()
        titles = {t.title for t in ready}
        assert "Branch B" in titles
        assert "Merge" not in titles

        # Complete t3 -> t4 now ready
        await mgr.complete_task(t3.id)
        ready = await mgr.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].title == "Merge"

    @pytest.mark.asyncio
    async def test_assign_task(self, team_and_mgr):
        team, mgr = team_and_mgr

        agent = AgentInstance(team_id=team.id, role="worker", name="W")
        await agent.save()

        task = await mgr.create_task("Assignable")
        assigned = await mgr.assign_task(task.id, agent.id)

        assert assigned.status == "in_progress"
        assert assigned.assignee_id == agent.id

    @pytest.mark.asyncio
    async def test_assign_blocked_task_raises(self, team_and_mgr):
        team, mgr = team_and_mgr

        agent = AgentInstance(team_id=team.id, role="worker", name="W")
        await agent.save()

        t1 = await mgr.create_task("Dep")
        t2 = await mgr.create_task("Blocked", depends_on=[t1.id])

        with pytest.raises(ValueError, match="blocked"):
            await mgr.assign_task(t2.id, agent.id)

    @pytest.mark.asyncio
    async def test_fail_task(self, team_and_mgr):
        _, mgr = team_and_mgr
        task = await mgr.create_task("Will fail")
        failed = await mgr.fail_task(task.id, "LLM error")

        assert failed.status == "failed"
        assert failed.error == "LLM error"

    @pytest.mark.asyncio
    async def test_is_complete(self, team_and_mgr):
        _, mgr = team_and_mgr
        t1 = await mgr.create_task("A")
        t2 = await mgr.create_task("B")

        assert await mgr.is_complete() is False

        await mgr.complete_task(t1.id)
        assert await mgr.is_complete() is False

        await mgr.complete_task(t2.id)
        assert await mgr.is_complete() is True

    @pytest.mark.asyncio
    async def test_summary(self, team_and_mgr):
        _, mgr = team_and_mgr
        t1 = await mgr.create_task("Done")
        t2 = await mgr.create_task("Pending")
        t3 = await mgr.create_task("Failed")

        await mgr.complete_task(t1.id)
        await mgr.fail_task(t3.id, "err")

        s = await mgr.summary()
        assert s["total"] == 3
        assert s["by_status"]["completed"] == 1
        assert s["by_status"]["pending"] == 1
        assert s["by_status"]["failed"] == 1
        assert s["complete"] is False

    @pytest.mark.asyncio
    async def test_execution_order_linear(self, team_and_mgr):
        _, mgr = team_and_mgr
        t1 = await mgr.create_task("First")
        t2 = await mgr.create_task("Second", depends_on=[t1.id])
        t3 = await mgr.create_task("Third", depends_on=[t2.id])

        layers = await mgr.get_execution_order()
        assert len(layers) == 3
        assert layers[0] == [t1.id]
        assert layers[1] == [t2.id]
        assert layers[2] == [t3.id]

    @pytest.mark.asyncio
    async def test_execution_order_parallel(self, team_and_mgr):
        _, mgr = team_and_mgr
        t1 = await mgr.create_task("Root")
        t2 = await mgr.create_task("A", depends_on=[t1.id])
        t3 = await mgr.create_task("B", depends_on=[t1.id])

        layers = await mgr.get_execution_order()
        assert len(layers) == 2
        assert layers[0] == [t1.id]
        assert set(layers[1]) == {t2.id, t3.id}

    @pytest.mark.asyncio
    async def test_auto_assign(self, team_and_mgr):
        team, mgr = team_and_mgr

        a1 = AgentInstance(team_id=team.id, role="worker", name="W1")
        await a1.save()
        a2 = AgentInstance(team_id=team.id, role="worker", name="W2")
        await a2.save()

        t1 = await mgr.create_task("T1")
        t2 = await mgr.create_task("T2")
        t3 = await mgr.create_task("T3")

        assignments = await mgr.auto_assign([a1, a2])
        # Only 2 agents, so only 2 tasks assigned
        assert len(assignments) == 2

        # Check that assigned tasks are in_progress
        for task, agent in assignments:
            refreshed = await AgentTask.get(task.id)
            assert refreshed.status == "in_progress"

    @pytest.mark.asyncio
    async def test_create_task_invalid_dependency(self, team_and_mgr):
        _, mgr = team_and_mgr

        with pytest.raises(ValueError, match="not found"):
            await mgr.create_task("Bad dep", depends_on=["nonexistent-id"])

    @pytest.mark.asyncio
    async def test_complete_nonexistent_task(self, team_and_mgr):
        _, mgr = team_and_mgr

        with pytest.raises(ValueError, match="not found"):
            await mgr.complete_task("nonexistent-id")

    @pytest.mark.asyncio
    async def test_get_all_tasks(self, team_and_mgr):
        _, mgr = team_and_mgr

        for i in range(5):
            await mgr.create_task(f"Task {i}")

        all_tasks = await mgr.get_all_tasks()
        assert len(all_tasks) == 5

    @pytest.mark.asyncio
    async def test_get_all_tasks_filtered(self, team_and_mgr):
        _, mgr = team_and_mgr

        t1 = await mgr.create_task("Pending")
        t2 = await mgr.create_task("Done")
        await mgr.complete_task(t2.id)

        pending = await mgr.get_all_tasks(status="pending")
        assert len(pending) == 1

        completed = await mgr.get_all_tasks(status="completed")
        assert len(completed) == 1
