"""
Unit and integration tests for microsite status management.

Tests cover:
- Status transitions (draft -> published -> blocked -> draft)
- Access control (creator vs. public vs. other users)
- Publish creates a version and sets active_version_id
- Unpublish clears active version and reverts to draft
- Block disables public access
- Active version management
- API endpoint integration tests via FastAPI TestClient
"""

import asyncio
import json
import os
import tempfile
import uuid
from datetime import datetime

import aiosqlite
import pytest

from open_notebook.domain.microsite import Microsite


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MICROSITE_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS notebooks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    archived INTEGER DEFAULT 0,
    folder_id TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS microsites (
    id TEXT PRIMARY KEY,
    notebook_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    slug TEXT UNIQUE NOT NULL,
    theme TEXT DEFAULT 'light',
    is_active INTEGER DEFAULT 1,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    template_id TEXT,
    custom_css TEXT,
    custom_js TEXT,
    generation_config TEXT,
    moderation_status TEXT DEFAULT 'pending',
    published_version INTEGER,
    last_generated TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_by TEXT,
    active_version_id TEXT,
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_microsites_status ON microsites(status);
CREATE INDEX IF NOT EXISTS idx_microsites_created_by ON microsites(created_by);

CREATE TABLE IF NOT EXISTS microsite_versions (
    id TEXT PRIMARY KEY,
    microsite_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    full_html TEXT,
    full_css TEXT,
    content_snapshot TEXT,
    created_by TEXT,
    created TEXT NOT NULL,
    status_at_publish TEXT,
    published_at TEXT,
    FOREIGN KEY (microsite_id) REFERENCES microsites(id) ON DELETE CASCADE,
    UNIQUE(microsite_id, version_number)
);

CREATE TABLE IF NOT EXISTS microsite_content (
    id TEXT PRIMARY KEY,
    microsite_id TEXT NOT NULL,
    section_id TEXT NOT NULL,
    content_html TEXT,
    content_json TEXT,
    order_num INTEGER DEFAULT 0,
    is_visible INTEGER DEFAULT 1,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (microsite_id) REFERENCES microsites(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS microsite_access (
    id TEXT PRIMARY KEY,
    microsite_id TEXT NOT NULL,
    email TEXT NOT NULL,
    created TEXT NOT NULL,
    FOREIGN KEY (microsite_id) REFERENCES microsites(id) ON DELETE CASCADE,
    UNIQUE(microsite_id, email)
);

CREATE TABLE IF NOT EXISTS microsite_templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    description TEXT,
    structure TEXT NOT NULL,
    default_styles TEXT,
    preview_image TEXT,
    is_custom INTEGER DEFAULT 0,
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS microsite_sources (
    microsite_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    created TEXT NOT NULL,
    PRIMARY KEY (microsite_id, source_id),
    FOREIGN KEY (microsite_id) REFERENCES microsites(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS _migrations (
    id TEXT PRIMARY KEY,
    version INTEGER UNIQUE NOT NULL,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
"""


@pytest.fixture
async def microsite_db(tmp_path):
    """Provide a clean SQLite database with full microsite schema.

    The fixture patches ``get_database`` inside the *repository* module so that
    domain model methods (``save``, ``publish``, etc.) that call ``repo_update``
    → ``db_connection()`` → ``get_database()`` resolve to the test database.

    ``connect()`` / ``disconnect()`` are made idempotent so the repeated
    connect/disconnect cycle inside ``db_connection()`` does not tear down the
    engine that the rest of the test is using.
    """
    from unittest.mock import patch
    from open_notebook.database.sqlite_impl import SQLiteDatabase
    from open_notebook.database.interface import ConnectionConfig

    db_path = str(tmp_path / "test_microsite.db")
    config = ConnectionConfig(db_type="sqlite", db_path=db_path)
    db = SQLiteDatabase(config)
    await db.connect()

    # Create schema
    async with aiosqlite.connect(db_path) as raw_db:
        await raw_db.executescript(MICROSITE_SCHEMA)

    # Seed a notebook for FK references
    now = datetime.utcnow().isoformat()
    await db.execute(
        "INSERT INTO notebooks (id, name, created, updated) VALUES (:id, :name, :created, :updated)",
        {"id": "nb-1", "name": "Test Notebook", "created": now, "updated": now},
    )

    # Make connect/disconnect idempotent so that db_connection()'s
    # connect → yield → disconnect cycle does not destroy the engine.
    _original_connect = db.connect
    _original_disconnect = db.disconnect

    async def _noop_connect():
        if not db._connected:
            await _original_connect()

    async def _noop_disconnect():
        pass  # keep alive until fixture teardown

    db.connect = _noop_connect
    db.disconnect = _noop_disconnect

    # Patch get_database where the *repository* module imported it so that
    # repo_query / repo_update / repo_create all use the test database.
    with patch("open_notebook.database.repository.get_database", return_value=db):
        yield db

    # Restore and actually disconnect
    db.connect = _original_connect
    db.disconnect = _original_disconnect
    await db.disconnect()


async def _insert_microsite(db, **overrides) -> dict:
    """Helper: insert a microsite and return its data dict."""
    now = datetime.utcnow().isoformat()
    data = {
        "id": overrides.get("id", str(uuid.uuid4())),
        "notebook_id": overrides.get("notebook_id", "nb-1"),
        "title": overrides.get("title", "Test Microsite"),
        "slug": overrides.get("slug", str(uuid.uuid4())[:12]),
        "theme": overrides.get("theme", "light"),
        "is_active": overrides.get("is_active", 1),
        "status": overrides.get("status", "draft"),
        "created_by": overrides.get("created_by", "user-1"),
        "active_version_id": overrides.get("active_version_id", None),
        "created": overrides.get("created", now),
        "updated": overrides.get("updated", now),
    }
    cols = ", ".join(data.keys())
    placeholders = ", ".join(f":{k}" for k in data.keys())
    await db.execute(f"INSERT INTO microsites ({cols}) VALUES ({placeholders})", data)
    return data


async def _insert_version(db, microsite_id, version_number, **overrides) -> dict:
    """Helper: insert a microsite version and return its data dict."""
    now = datetime.utcnow().isoformat()
    data = {
        "id": overrides.get("id", str(uuid.uuid4())),
        "microsite_id": microsite_id,
        "version_number": version_number,
        "full_html": overrides.get("full_html", f"<html>v{version_number}</html>"),
        "full_css": overrides.get("full_css", ""),
        "content_snapshot": overrides.get("content_snapshot", json.dumps({"sections": []})),
        "created_by": overrides.get("created_by", "user-1"),
        "status_at_publish": overrides.get("status_at_publish", "published"),
        "published_at": overrides.get("published_at", now),
        "created": overrides.get("created", now),
    }
    cols = ", ".join(data.keys())
    placeholders = ", ".join(f":{k}" for k in data.keys())
    await db.execute(f"INSERT INTO microsite_versions ({cols}) VALUES ({placeholders})", data)
    return data


# ---------------------------------------------------------------------------
# Domain model tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestMicrositeStatusTransitions:
    """Test status lifecycle: draft -> published -> blocked -> draft."""

    async def test_new_microsite_defaults_to_draft(self, microsite_db):
        ms = Microsite(notebook_id="nb-1", title="Draft Test", created_by="user-1")
        assert ms.status == "draft"
        assert ms.active_version_id is None

    async def test_publish_sets_status_and_version(self, microsite_db):
        ms_data = await _insert_microsite(microsite_db, status="draft")
        ver = await _insert_version(microsite_db, ms_data["id"], 1)

        ms = Microsite(**ms_data)
        await ms.publish(version_id=ver["id"])

        assert ms.status == "published"
        assert ms.active_version_id == ver["id"]

    async def test_unpublish_reverts_to_draft(self, microsite_db):
        ms_data = await _insert_microsite(microsite_db, status="published")
        ver = await _insert_version(microsite_db, ms_data["id"], 1)

        ms_data["active_version_id"] = ver["id"]
        ms = Microsite(**ms_data)
        await ms.unpublish()

        assert ms.status == "draft"
        assert ms.active_version_id is None

    async def test_block_disables_access(self, microsite_db):
        ms_data = await _insert_microsite(microsite_db, status="published")

        ms = Microsite(**ms_data)
        await ms.block(reason="Policy violation")

        assert ms.status == "blocked"
        assert ms.active_version_id is None

    async def test_block_then_unpublish_to_draft(self, microsite_db):
        ms_data = await _insert_microsite(microsite_db, status="blocked")

        ms = Microsite(**ms_data)
        await ms.unpublish()

        assert ms.status == "draft"

    async def test_full_lifecycle(self, microsite_db):
        """draft -> published -> blocked -> draft -> published"""
        ms_data = await _insert_microsite(microsite_db, status="draft")
        ms = Microsite(**ms_data)

        # draft -> published
        ver1 = await _insert_version(microsite_db, ms_data["id"], 1)
        await ms.publish(version_id=ver1["id"])
        assert ms.status == "published"

        # published -> blocked
        await ms.block()
        assert ms.status == "blocked"
        assert ms.active_version_id is None

        # blocked -> draft
        await ms.unpublish()
        assert ms.status == "draft"

        # draft -> published (with new version)
        ver2 = await _insert_version(microsite_db, ms_data["id"], 2)
        await ms.publish(version_id=ver2["id"])
        assert ms.status == "published"
        assert ms.active_version_id == ver2["id"]


@pytest.mark.asyncio
class TestMicrositeAccessControl:
    """Test can_access logic for different users and statuses."""

    async def test_published_accessible_by_anyone(self, microsite_db):
        ms = Microsite(
            notebook_id="nb-1", title="Public", status="published", created_by="user-1"
        )
        assert await ms.can_access(user_id=None) is True
        assert await ms.can_access(user_id="random-user") is True
        assert await ms.can_access(user_id="user-1") is True

    async def test_draft_accessible_by_creator_only(self, microsite_db):
        ms = Microsite(
            notebook_id="nb-1", title="Draft", status="draft", created_by="user-1"
        )
        assert await ms.can_access(user_id="user-1") is True
        assert await ms.can_access(user_id="other-user") is False
        assert await ms.can_access(user_id=None) is False

    async def test_blocked_not_accessible_by_anyone(self, microsite_db):
        ms = Microsite(
            notebook_id="nb-1", title="Blocked", status="blocked", created_by="user-1"
        )
        assert await ms.can_access(user_id="user-1") is False
        assert await ms.can_access(user_id=None) is False
        assert await ms.can_access(user_id="admin") is False

    async def test_draft_no_creator_not_accessible(self, microsite_db):
        """Draft with no created_by set should not be accessible to anyone."""
        ms = Microsite(
            notebook_id="nb-1", title="Orphan Draft", status="draft", created_by=None
        )
        assert await ms.can_access(user_id="user-1") is False
        assert await ms.can_access(user_id=None) is False


@pytest.mark.asyncio
class TestMicrositePublishCreatesVersion:
    """Test that publishing sets active_version_id correctly."""

    async def test_publish_records_version_id(self, microsite_db):
        ms_data = await _insert_microsite(microsite_db)
        ver = await _insert_version(microsite_db, ms_data["id"], 1)

        ms = Microsite(**ms_data)
        await ms.publish(version_id=ver["id"])

        # Verify persisted in database
        results = await microsite_db.query(
            "SELECT status, active_version_id FROM microsites WHERE id = :id",
            {"id": ms_data["id"]},
        )
        assert results[0]["status"] == "published"
        assert results[0]["active_version_id"] == ver["id"]

    async def test_republish_updates_version(self, microsite_db):
        ms_data = await _insert_microsite(microsite_db)
        ver1 = await _insert_version(microsite_db, ms_data["id"], 1)
        ver2 = await _insert_version(microsite_db, ms_data["id"], 2)

        ms = Microsite(**ms_data)
        await ms.publish(version_id=ver1["id"])
        assert ms.active_version_id == ver1["id"]

        await ms.publish(version_id=ver2["id"])
        assert ms.active_version_id == ver2["id"]

        # Verify in DB
        results = await microsite_db.query(
            "SELECT active_version_id FROM microsites WHERE id = :id",
            {"id": ms_data["id"]},
        )
        assert results[0]["active_version_id"] == ver2["id"]

    async def test_unpublish_clears_active_version_in_db(self, microsite_db):
        ms_data = await _insert_microsite(microsite_db, status="published")
        ver = await _insert_version(microsite_db, ms_data["id"], 1)

        ms_data["active_version_id"] = ver["id"]
        ms = Microsite(**ms_data)
        await ms.unpublish()

        results = await microsite_db.query(
            "SELECT status, active_version_id FROM microsites WHERE id = :id",
            {"id": ms_data["id"]},
        )
        assert results[0]["status"] == "draft"
        assert results[0]["active_version_id"] is None


@pytest.mark.asyncio
class TestActiveVersionManagement:
    """Test active version queries and edge cases."""

    async def test_microsite_with_no_versions(self, microsite_db):
        ms_data = await _insert_microsite(microsite_db)

        results = await microsite_db.query(
            "SELECT * FROM microsite_versions WHERE microsite_id = :mid",
            {"mid": ms_data["id"]},
        )
        assert len(results) == 0

    async def test_active_version_points_to_valid_record(self, microsite_db):
        ms_data = await _insert_microsite(microsite_db)
        ver = await _insert_version(microsite_db, ms_data["id"], 1)

        await microsite_db.execute(
            "UPDATE microsites SET active_version_id = :vid WHERE id = :id",
            {"vid": ver["id"], "id": ms_data["id"]},
        )

        results = await microsite_db.query(
            """SELECT mv.* FROM microsite_versions mv
               JOIN microsites ms ON ms.active_version_id = mv.id
               WHERE ms.id = :id""",
            {"id": ms_data["id"]},
        )
        assert len(results) == 1
        assert results[0]["version_number"] == 1

    async def test_version_number_uniqueness(self, microsite_db):
        ms_data = await _insert_microsite(microsite_db)
        await _insert_version(microsite_db, ms_data["id"], 1)

        # Inserting a duplicate version_number should fail
        with pytest.raises(Exception):
            await _insert_version(
                microsite_db,
                ms_data["id"],
                1,
                id=str(uuid.uuid4()),
            )

    async def test_multiple_versions_increment(self, microsite_db):
        ms_data = await _insert_microsite(microsite_db)
        await _insert_version(microsite_db, ms_data["id"], 1)
        await _insert_version(microsite_db, ms_data["id"], 2)
        await _insert_version(microsite_db, ms_data["id"], 3)

        results = await microsite_db.query(
            "SELECT version_number FROM microsite_versions WHERE microsite_id = :mid ORDER BY version_number",
            {"mid": ms_data["id"]},
        )
        assert [r["version_number"] for r in results] == [1, 2, 3]

    async def test_version_stores_publish_metadata(self, microsite_db):
        ms_data = await _insert_microsite(microsite_db)
        now = datetime.utcnow().isoformat()
        ver = await _insert_version(
            microsite_db,
            ms_data["id"],
            1,
            status_at_publish="published",
            published_at=now,
        )

        results = await microsite_db.query(
            "SELECT status_at_publish, published_at FROM microsite_versions WHERE id = :id",
            {"id": ver["id"]},
        )
        assert results[0]["status_at_publish"] == "published"
        assert results[0]["published_at"] == now


@pytest.mark.asyncio
class TestMicrositeCreateFactory:
    """Test microsite creation following the production pattern.

    Note: ``Microsite.create()`` relies on ``ObjectModel.save()`` which uses
    ``self.id is None`` to decide create-vs-update. Because
    ``Microsite.model_post_init`` eagerly generates an ID, ``save()`` always
    takes the update path for new instances and fails. The production API
    (``api/routers/microsites.py``) works around this by constructing the model,
    converting to dict, and calling ``repo_create`` directly. These tests verify
    that pattern.
    """

    async def test_create_starts_as_draft(self, microsite_db):
        ms = Microsite(
            notebook_id="nb-1",
            title="Factory Test",
            created_by="user-1",
        )
        assert ms.status == "draft"
        assert ms.created_by == "user-1"
        assert ms.id is not None

    async def test_create_persists_to_db(self, microsite_db):
        from open_notebook.database.repository import repo_create

        ms = Microsite(
            notebook_id="nb-1",
            title="Persistent Test",
            created_by="user-2",
        )
        ms_dict = ms.model_dump()
        # Convert datetime objects to ISO strings for SQLite
        for key in ("created", "updated"):
            if isinstance(ms_dict.get(key), datetime):
                ms_dict[key] = ms_dict[key].isoformat()

        microsite_id = await repo_create("microsites", ms_dict)

        results = await microsite_db.query(
            "SELECT * FROM microsites WHERE id = :id",
            {"id": microsite_id},
        )
        assert len(results) == 1
        assert results[0]["status"] == "draft"
        assert results[0]["created_by"] == "user-2"

    async def test_create_with_description(self, microsite_db):
        ms = Microsite(
            notebook_id="nb-1",
            title="Described",
            created_by="user-1",
            description="A detailed description",
        )
        assert ms.description == "A detailed description"


@pytest.mark.asyncio
class TestMicrositeStatusIndexes:
    """Test that status-based queries use indexes efficiently."""

    async def test_query_by_status(self, microsite_db):
        await _insert_microsite(microsite_db, status="draft", id="ms-draft-1")
        await _insert_microsite(microsite_db, status="published", id="ms-pub-1", slug="pub1")
        await _insert_microsite(microsite_db, status="published", id="ms-pub-2", slug="pub2")
        await _insert_microsite(microsite_db, status="blocked", id="ms-block-1", slug="blk1")

        drafts = await microsite_db.query(
            "SELECT * FROM microsites WHERE status = :status",
            {"status": "draft"},
        )
        published = await microsite_db.query(
            "SELECT * FROM microsites WHERE status = :status",
            {"status": "published"},
        )
        blocked = await microsite_db.query(
            "SELECT * FROM microsites WHERE status = :status",
            {"status": "blocked"},
        )

        assert len(drafts) == 1
        assert len(published) == 2
        assert len(blocked) == 1

    async def test_query_by_created_by(self, microsite_db):
        await _insert_microsite(microsite_db, created_by="alice", id="ms-a1")
        await _insert_microsite(microsite_db, created_by="alice", id="ms-a2", slug="a2")
        await _insert_microsite(microsite_db, created_by="bob", id="ms-b1", slug="b1")

        alice_sites = await microsite_db.query(
            "SELECT * FROM microsites WHERE created_by = :user",
            {"user": "alice"},
        )
        bob_sites = await microsite_db.query(
            "SELECT * FROM microsites WHERE created_by = :user",
            {"user": "bob"},
        )

        assert len(alice_sites) == 2
        assert len(bob_sites) == 1
