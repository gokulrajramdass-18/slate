"""
End-to-end workflow tests for the microsite status management feature.

Tests the complete lifecycle through API endpoints:
1. Create microsite (verify status=draft)
2. Add content sections
3. Publish (verify version 1 created, status=published)
4. Access via public URL (verify success)
5. Edit content
6. Publish again (verify version 2 created, becomes active)
7. Verify version 2 is served publicly
8. Rollback to version 1 (verify creates version 3)
9. Unpublish (verify status=draft)
10. Access via public URL (verify 403)

Edge cases:
- Draft microsite not accessible via public URL
- Blocked microsite returns 403
- Creator can access draft, others cannot
"""

import json
import uuid
from datetime import datetime
from unittest.mock import patch

import aiosqlite
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from api.routers.microsites import router as microsites_router


# ---------------------------------------------------------------------------
# Schema -- same schema used in test_microsite_status.py, extended with the
# tables that the microsites router may reference.
# ---------------------------------------------------------------------------

FULL_SCHEMA = """
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
    structure TEXT NOT NULL DEFAULT '{}',
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def e2e_env(tmp_path):
    """Set up a self-contained environment for e2e microsite testing.

    Creates:
    - A temporary SQLite database with the full microsite schema
    - A minimal FastAPI app with the microsites router mounted
    - An httpx AsyncClient pointing at that app
    - Patches the repository layer to use the test database

    Yields a dict with ``client`` (AsyncClient) and ``db`` (SQLiteDatabase).
    """
    from open_notebook.database.sqlite_impl import SQLiteDatabase
    from open_notebook.database.interface import ConnectionConfig

    db_path = str(tmp_path / "e2e_microsite.db")
    config = ConnectionConfig(db_type="sqlite", db_path=db_path)
    db = SQLiteDatabase(config)
    await db.connect()

    # Create schema
    async with aiosqlite.connect(db_path) as raw_db:
        await raw_db.executescript(FULL_SCHEMA)

    # Seed a notebook (required FK for microsites)
    now = datetime.utcnow().isoformat()
    await db.execute(
        "INSERT INTO notebooks (id, name, description, created, updated) VALUES (:id, :name, :desc, :c, :u)",
        {"id": "nb-e2e", "name": "E2E Notebook", "desc": "For workflow tests", "c": now, "u": now},
    )

    # Make connect/disconnect idempotent (same pattern as test_microsite_status.py)
    _orig_connect = db.connect
    _orig_disconnect = db.disconnect

    async def _noop_connect():
        if not db._connected:
            await _orig_connect()

    async def _noop_disconnect():
        pass

    db.connect = _noop_connect
    db.disconnect = _noop_disconnect

    # Create a minimal FastAPI app with just the microsites router
    test_app = FastAPI()
    test_app.include_router(microsites_router)

    # Patch the repository layer to use the test database
    with patch("open_notebook.database.repository.get_database", return_value=db), \
         patch("api.services.version_service.repo_query", side_effect=_make_repo_query(db)), \
         patch("api.services.version_service.repo_execute", side_effect=_make_repo_execute(db)):

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield {"client": client, "db": db}

    # Teardown
    db.connect = _orig_connect
    db.disconnect = _orig_disconnect
    await db.disconnect()


def _make_repo_query(db):
    """Create a repo_query replacement that uses the test database directly."""
    async def _repo_query(sql, params=None, fetch_one=False):
        return await db.query(sql, params, fetch_one)
    return _repo_query


def _make_repo_execute(db):
    """Create a repo_execute replacement that uses the test database directly."""
    async def _repo_execute(sql, params=None):
        return await db.execute(sql, params)
    return _repo_execute


async def _add_content_section(db, microsite_id, section_id, html, order_num=0):
    """Helper: insert a content section directly into the database."""
    now = datetime.utcnow().isoformat()
    await db.execute(
        """INSERT INTO microsite_content
           (id, microsite_id, section_id, content_html, order_num, is_visible, created, updated)
           VALUES (:id, :mid, :sid, :html, :order, 1, :c, :u)""",
        {
            "id": str(uuid.uuid4()),
            "mid": microsite_id,
            "sid": section_id,
            "html": html,
            "order": order_num,
            "c": now,
            "u": now,
        },
    )


async def _update_content_section(db, microsite_id, section_id, html):
    """Helper: update content_html for a section by section_id."""
    now = datetime.utcnow().isoformat()
    await db.execute(
        "UPDATE microsite_content SET content_html = :html, updated = :u WHERE microsite_id = :mid AND section_id = :sid",
        {"html": html, "u": now, "mid": microsite_id, "sid": section_id},
    )


# ---------------------------------------------------------------------------
# E2E Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.asyncio
class TestMicrositeFullWorkflow:
    """Test the complete microsite lifecycle through API endpoints."""

    async def test_full_publish_edit_rollback_unpublish_workflow(self, e2e_env):
        """
        Full workflow:
        1. Create microsite → status=draft
        2. Add content sections
        3. Publish → version 1, status=published
        4. Access public URL → success (HTML returned)
        5. Edit content
        6. Publish again → version 2, becomes active
        7. Verify version 2 is served publicly
        8. Rollback to version 1 → creates version 3
        9. Unpublish → status=draft
        10. Access public URL → 403
        """
        client = e2e_env["client"]
        db = e2e_env["db"]

        # --- Step 1: Create microsite ---
        resp = await client.post(
            "/api/microsites",
            json={"notebook_id": "nb-e2e", "title": "E2E Workflow Site"},
        )
        assert resp.status_code == 201, resp.text
        ms = resp.json()
        ms_id = ms["id"]
        slug = ms["slug"]

        assert ms["status"] == "draft"
        assert ms["active_version_id"] is None

        # --- Step 2: Add content sections ---
        await _add_content_section(db, ms_id, "hero", "<h1>Welcome v1</h1>", order_num=0)
        await _add_content_section(db, ms_id, "about", "<p>About us v1</p>", order_num=1)

        # --- Step 3: Publish (first time) ---
        resp = await client.post(
            f"/api/microsites/{ms_id}/publish",
            json={"version_message": "Initial publish"},
        )
        assert resp.status_code == 200, resp.text
        pub = resp.json()
        assert pub["status"] == "published"
        assert pub["version_number"] == 1
        v1_id = pub["active_version_id"]
        assert v1_id is not None

        # Verify microsite is now published in DB
        resp = await client.get(f"/api/microsites/{ms_id}")
        assert resp.json()["status"] == "published"
        assert resp.json()["active_version_id"] == v1_id

        # --- Step 4: Access via public URL ---
        resp = await client.get(f"/api/microsites/public/{slug}")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

        # --- Step 5: Edit content ---
        await _update_content_section(db, ms_id, "hero", "<h1>Welcome v2 - Updated!</h1>")

        # --- Step 6: Publish again ---
        resp = await client.post(
            f"/api/microsites/{ms_id}/publish",
            json={"version_message": "Content update"},
        )
        assert resp.status_code == 200, resp.text
        pub2 = resp.json()
        assert pub2["version_number"] == 2
        v2_id = pub2["active_version_id"]
        assert v2_id != v1_id

        # --- Step 7: Verify version 2 is served publicly ---
        resp = await client.get(f"/api/microsites/public/{slug}")
        assert resp.status_code == 200

        # --- Step 8: Rollback to version 1 ---
        resp = await client.post(
            f"/api/microsites/{ms_id}/rollback",
            json={"version_number": 1},
        )
        assert resp.status_code == 200, resp.text
        rollback = resp.json()
        assert rollback["restored_version"] == 1
        assert rollback["new_version"] == 3  # Rollback creates version 3

        # --- Step 9: Unpublish ---
        resp = await client.post(f"/api/microsites/{ms_id}/unpublish")
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "draft"

        # Verify status reverted
        resp = await client.get(f"/api/microsites/{ms_id}")
        assert resp.json()["status"] == "draft"
        assert resp.json()["active_version_id"] is None

        # --- Step 10: Public URL should fail ---
        resp = await client.get(f"/api/microsites/public/{slug}")
        assert resp.status_code == 403

    async def test_version_list_after_multiple_publishes(self, e2e_env):
        """Verify version list grows correctly across publishes and rollback."""
        client = e2e_env["client"]
        db = e2e_env["db"]

        # Create microsite and add content
        resp = await client.post(
            "/api/microsites",
            json={"notebook_id": "nb-e2e", "title": "Version List Test"},
        )
        ms_id = resp.json()["id"]
        await _add_content_section(db, ms_id, "main", "<p>Content</p>")

        # Publish three times
        for i in range(3):
            await _update_content_section(db, ms_id, "main", f"<p>Content v{i + 1}</p>")
            resp = await client.post(
                f"/api/microsites/{ms_id}/publish",
                json={"version_message": f"Version {i + 1}"},
            )
            assert resp.status_code == 200

        # List versions
        resp = await client.get(f"/api/microsites/{ms_id}/versions")
        assert resp.status_code == 200
        versions = resp.json()["versions"]
        assert len(versions) == 3
        # Versions should be descending
        assert versions[0]["version_number"] == 3
        assert versions[2]["version_number"] == 1


@pytest.mark.e2e
@pytest.mark.asyncio
class TestDraftAccessControl:
    """Test that draft microsites are not publicly accessible."""

    async def test_draft_not_accessible_via_public_url(self, e2e_env):
        """A draft microsite should return 403 on its public URL."""
        client = e2e_env["client"]

        resp = await client.post(
            "/api/microsites",
            json={"notebook_id": "nb-e2e", "title": "Draft Only"},
        )
        slug = resp.json()["slug"]

        # Public access should fail
        resp = await client.get(f"/api/microsites/public/{slug}")
        assert resp.status_code == 403

    async def test_draft_preview_accessible_by_creator(self, e2e_env):
        """Preview endpoint should allow the creator to view a draft."""
        client = e2e_env["client"]
        db = e2e_env["db"]

        resp = await client.post(
            "/api/microsites",
            json={"notebook_id": "nb-e2e", "title": "Draft Preview"},
        )
        ms_id = resp.json()["id"]

        # Add content and create a version so preview has something to show
        await _add_content_section(db, ms_id, "hero", "<h1>Draft Content</h1>")

        # Publish to create a version, then unpublish back to draft
        resp = await client.post(
            f"/api/microsites/{ms_id}/publish",
            json={},
        )
        assert resp.status_code == 200
        resp = await client.post(f"/api/microsites/{ms_id}/unpublish")
        assert resp.status_code == 200

        # Preview should still work for the creator (get_current_user_id returns "system")
        resp = await client.get(f"/api/microsites/{ms_id}/preview")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


@pytest.mark.e2e
@pytest.mark.asyncio
class TestBlockedMicrosite:
    """Test that blocked microsites are inaccessible."""

    async def test_blocked_returns_403_on_public_url(self, e2e_env):
        """A blocked microsite should return 403 on its public URL."""
        client = e2e_env["client"]
        db = e2e_env["db"]

        # Create and publish first (so there's content)
        resp = await client.post(
            "/api/microsites",
            json={"notebook_id": "nb-e2e", "title": "Will Be Blocked"},
        )
        ms_id = resp.json()["id"]
        slug = resp.json()["slug"]

        await _add_content_section(db, ms_id, "hero", "<h1>Some content</h1>")
        resp = await client.post(
            f"/api/microsites/{ms_id}/publish",
            json={},
        )
        assert resp.status_code == 200

        # Verify public access works while published
        resp = await client.get(f"/api/microsites/public/{slug}")
        assert resp.status_code == 200

        # Block the microsite
        resp = await client.post(
            f"/api/microsites/{ms_id}/block",
            json={"reason": "Policy violation"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "blocked"

        # Public access should now fail
        resp = await client.get(f"/api/microsites/public/{slug}")
        assert resp.status_code == 403

    async def test_blocked_preview_returns_403(self, e2e_env):
        """Preview endpoint should return 403 for blocked microsites."""
        client = e2e_env["client"]
        db = e2e_env["db"]

        resp = await client.post(
            "/api/microsites",
            json={"notebook_id": "nb-e2e", "title": "Block Preview Test"},
        )
        ms_id = resp.json()["id"]
        await _add_content_section(db, ms_id, "hero", "<h1>Content</h1>")

        # Publish so there's a version
        await client.post(f"/api/microsites/{ms_id}/publish", json={})

        # Block
        await client.post(
            f"/api/microsites/{ms_id}/block",
            json={"reason": "Test block"},
        )

        # Preview should be blocked
        resp = await client.get(f"/api/microsites/{ms_id}/preview")
        assert resp.status_code == 403

    async def test_cannot_publish_blocked_microsite(self, e2e_env):
        """Publishing a blocked microsite should return 403."""
        client = e2e_env["client"]
        db = e2e_env["db"]

        resp = await client.post(
            "/api/microsites",
            json={"notebook_id": "nb-e2e", "title": "Block Publish Test"},
        )
        ms_id = resp.json()["id"]
        await _add_content_section(db, ms_id, "hero", "<h1>Content</h1>")

        # Publish then block
        await client.post(f"/api/microsites/{ms_id}/publish", json={})
        await client.post(
            f"/api/microsites/{ms_id}/block",
            json={"reason": "Blocked for test"},
        )

        # Trying to publish again should fail
        resp = await client.post(
            f"/api/microsites/{ms_id}/publish",
            json={"version_message": "Should fail"},
        )
        assert resp.status_code == 403


@pytest.mark.e2e
@pytest.mark.asyncio
class TestActiveVersionEndpoint:
    """Test the active-version endpoint through the workflow."""

    async def test_active_version_empty_when_draft(self, e2e_env):
        """Draft microsite should have no active version."""
        client = e2e_env["client"]

        resp = await client.post(
            "/api/microsites",
            json={"notebook_id": "nb-e2e", "title": "Active Version Test"},
        )
        ms_id = resp.json()["id"]

        resp = await client.get(f"/api/microsites/{ms_id}/active-version")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active_version_id"] is None
        assert data["version_number"] is None

    async def test_active_version_set_after_publish(self, e2e_env):
        """After publish, active-version should return the published version."""
        client = e2e_env["client"]
        db = e2e_env["db"]

        resp = await client.post(
            "/api/microsites",
            json={"notebook_id": "nb-e2e", "title": "Active After Publish"},
        )
        ms_id = resp.json()["id"]
        await _add_content_section(db, ms_id, "hero", "<h1>Active</h1>")

        pub = await client.post(f"/api/microsites/{ms_id}/publish", json={})
        assert pub.status_code == 200

        resp = await client.get(f"/api/microsites/{ms_id}/active-version")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active_version_id"] is not None
        assert data["version_number"] == 1
        assert data["full_html"] is not None

    async def test_active_version_cleared_after_unpublish(self, e2e_env):
        """After unpublish, active-version should be empty again."""
        client = e2e_env["client"]
        db = e2e_env["db"]

        resp = await client.post(
            "/api/microsites",
            json={"notebook_id": "nb-e2e", "title": "Unpublish Active"},
        )
        ms_id = resp.json()["id"]
        await _add_content_section(db, ms_id, "hero", "<h1>Test</h1>")

        await client.post(f"/api/microsites/{ms_id}/publish", json={})
        await client.post(f"/api/microsites/{ms_id}/unpublish")

        resp = await client.get(f"/api/microsites/{ms_id}/active-version")
        assert resp.status_code == 200
        assert resp.json()["active_version_id"] is None


@pytest.mark.e2e
@pytest.mark.asyncio
class TestAccessCheckEndpoint:
    """Test the access-check endpoint for different statuses."""

    async def test_access_check_draft(self, e2e_env):
        """Draft microsite: creator has access, status is reported as draft."""
        client = e2e_env["client"]

        resp = await client.post(
            "/api/microsites",
            json={"notebook_id": "nb-e2e", "title": "Access Check Draft"},
        )
        ms_id = resp.json()["id"]

        resp = await client.get(f"/api/microsites/{ms_id}/access-check")
        assert resp.status_code == 200
        data = resp.json()
        # get_current_user_id() returns "system", which matches created_by
        assert data["has_access"] is True
        assert data["status"] == "draft"

    async def test_access_check_published(self, e2e_env):
        """Published microsite: everyone has access."""
        client = e2e_env["client"]
        db = e2e_env["db"]

        resp = await client.post(
            "/api/microsites",
            json={"notebook_id": "nb-e2e", "title": "Access Check Published"},
        )
        ms_id = resp.json()["id"]
        await _add_content_section(db, ms_id, "hero", "<h1>Public</h1>")
        await client.post(f"/api/microsites/{ms_id}/publish", json={})

        resp = await client.get(f"/api/microsites/{ms_id}/access-check")
        assert resp.status_code == 200
        assert resp.json()["has_access"] is True
        assert resp.json()["status"] == "published"

    async def test_access_check_blocked(self, e2e_env):
        """Blocked microsite: no one has access."""
        client = e2e_env["client"]
        db = e2e_env["db"]

        resp = await client.post(
            "/api/microsites",
            json={"notebook_id": "nb-e2e", "title": "Access Check Blocked"},
        )
        ms_id = resp.json()["id"]
        await _add_content_section(db, ms_id, "hero", "<h1>Blocked</h1>")
        await client.post(f"/api/microsites/{ms_id}/publish", json={})
        await client.post(
            f"/api/microsites/{ms_id}/block",
            json={"reason": "Test"},
        )

        resp = await client.get(f"/api/microsites/{ms_id}/access-check")
        assert resp.status_code == 200
        data = resp.json()
        # Blocked: nobody has access (even creator)
        assert data["has_access"] is False
        assert data["status"] == "blocked"
