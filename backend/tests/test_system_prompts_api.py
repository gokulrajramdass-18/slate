"""
Integration tests for system_prompts API router

Tests all REST endpoints: list, get, update, reset, toggle, cache operations.
"""

import pytest
from httpx import AsyncClient
from api.main import app


@pytest.fixture
async def client():
    """Create async test client"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
class TestListTemplates:
    """Test GET /api/system-prompts/templates"""

    async def test_list_all_templates(self, client):
        """Test listing all templates"""
        response = await client.get("/api/system-prompts/templates")

        assert response.status_code == 200
        data = response.json()

        assert "templates" in data
        assert "total" in data
        assert data["total"] == 28
        assert len(data["templates"]) == 28

    async def test_list_by_category_chat(self, client):
        """Test listing chat templates"""
        response = await client.get("/api/system-prompts/templates?category=chat")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] >= 3  # At least 3 chat prompts
        assert all(t["category"] == "chat" for t in data["templates"])

    async def test_list_by_category_research(self, client):
        """Test listing research templates"""
        response = await client.get("/api/system-prompts/templates?category=research")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 4
        assert all(t["category"] == "research" for t in data["templates"])

    async def test_list_by_category_orchestration(self, client):
        """Test listing orchestration templates"""
        response = await client.get("/api/system-prompts/templates?category=orchestration")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 5
        assert all(t["category"] == "orchestration" for t in data["templates"])

    async def test_list_by_category_microsite(self, client):
        """Test listing microsite templates"""
        response = await client.get("/api/system-prompts/templates?category=microsite")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 15
        assert all(t["category"] == "microsite" for t in data["templates"])

    async def test_list_invalid_category(self, client):
        """Test listing with invalid category returns empty"""
        response = await client.get("/api/system-prompts/templates?category=invalid")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0


@pytest.mark.asyncio
class TestGetTemplate:
    """Test GET /api/system-prompts/templates/{template_key}"""

    async def test_get_chat_base_system(self, client):
        """Test getting chat_base_system template"""
        response = await client.get("/api/system-prompts/templates/chat_base_system")

        assert response.status_code == 200
        data = response.json()

        assert data["template_key"] == "chat_base_system"
        assert data["category"] == "chat"
        assert data["name"] == "Chat Base System"
        assert "notebook_name" in data["template"]
        assert len(data["variables"]) == 5
        assert data["metadata"]["output_format"] == "text"
        assert data["is_default"] is True
        assert data["is_active"] is True

    async def test_get_research_phase1(self, client):
        """Test getting research phase 1 template"""
        response = await client.get("/api/system-prompts/templates/research_phase1_query_analysis")

        assert response.status_code == 200
        data = response.json()

        assert data["template_key"] == "research_phase1_query_analysis"
        assert data["category"] == "research"
        assert data["metadata"]["output_format"] == "json"

    async def test_get_nonexistent_template(self, client):
        """Test getting non-existent template returns 404"""
        response = await client.get("/api/system-prompts/templates/nonexistent_key")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    async def test_template_structure(self, client):
        """Test template response has correct structure"""
        response = await client.get("/api/system-prompts/templates/chat_base_system")

        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert "id" in data
        assert "category" in data
        assert "template_key" in data
        assert "name" in data
        assert "template" in data
        assert "variables" in data
        assert "metadata" in data
        assert "is_default" in data
        assert "is_active" in data
        assert "created" in data
        assert "updated" in data

        # Variables structure
        for var in data["variables"]:
            assert "name" in var
            assert "type" in var
            assert "required" in var

        # Metadata structure
        assert "output_format" in data["metadata"]
        assert "composition" in data["metadata"]


@pytest.mark.asyncio
class TestUpdateTemplate:
    """Test PUT /api/system-prompts/templates/{template_key}"""

    async def test_update_template_text(self, client):
        """Test updating template text"""
        new_template = "Custom prompt text for testing"

        response = await client.put(
            "/api/system-prompts/templates/chat_base_system",
            json={"template": new_template}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["template"] == new_template
        assert data["is_default"] is False  # Marked as custom

        # Reset after test
        await client.post("/api/system-prompts/templates/chat_base_system/reset")

    async def test_update_template_name_and_description(self, client):
        """Test updating name and description"""
        response = await client.put(
            "/api/system-prompts/templates/chat_base_system",
            json={
                "template": "Test prompt",
                "name": "Custom Chat Name",
                "description": "Custom description"
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "Custom Chat Name"
        assert data["description"] == "Custom description"

        # Reset after test
        await client.post("/api/system-prompts/templates/chat_base_system/reset")

    async def test_update_nonexistent_template(self, client):
        """Test updating non-existent template returns 404"""
        response = await client.put(
            "/api/system-prompts/templates/nonexistent",
            json={"template": "Test"}
        )

        assert response.status_code == 404

    async def test_update_invalid_json(self, client):
        """Test updating with invalid JSON returns 422"""
        response = await client.put(
            "/api/system-prompts/templates/chat_base_system",
            json={}  # Missing required 'template' field
        )

        assert response.status_code == 422


@pytest.mark.asyncio
class TestResetTemplate:
    """Test POST /api/system-prompts/templates/{template_key}/reset"""

    async def test_reset_customized_template(self, client):
        """Test resetting a customized template"""
        # First, customize the template
        await client.put(
            "/api/system-prompts/templates/chat_base_system",
            json={"template": "Custom text"}
        )

        # Verify it's customized
        response = await client.get("/api/system-prompts/templates/chat_base_system")
        assert response.json()["is_default"] is False

        # Reset
        response = await client.post("/api/system-prompts/templates/chat_base_system/reset")

        assert response.status_code == 200
        data = response.json()

        assert data["is_default"] is True
        assert "Custom text" not in data["template"]

    async def test_reset_default_template(self, client):
        """Test resetting already-default template (idempotent)"""
        response = await client.post("/api/system-prompts/templates/chat_base_system/reset")

        assert response.status_code == 200
        data = response.json()
        assert data["is_default"] is True

    async def test_reset_nonexistent_template(self, client):
        """Test resetting non-existent template returns 404"""
        response = await client.post("/api/system-prompts/templates/nonexistent/reset")

        assert response.status_code == 404


@pytest.mark.asyncio
class TestToggleTemplate:
    """Test POST /api/system-prompts/templates/{template_key}/toggle"""

    async def test_toggle_to_inactive(self, client):
        """Test disabling an active template"""
        # Ensure it's active
        await client.post("/api/system-prompts/templates/chat_base_system/toggle")
        response = await client.get("/api/system-prompts/templates/chat_base_system")
        initial_state = response.json()["is_active"]

        # Toggle
        response = await client.post("/api/system-prompts/templates/chat_base_system/toggle")

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] != initial_state

        # Toggle back
        await client.post("/api/system-prompts/templates/chat_base_system/toggle")

    async def test_toggle_idempotence(self, client):
        """Test toggling twice returns to original state"""
        # Get initial state
        response = await client.get("/api/system-prompts/templates/chat_base_system")
        initial_active = response.json()["is_active"]

        # Toggle twice
        await client.post("/api/system-prompts/templates/chat_base_system/toggle")
        await client.post("/api/system-prompts/templates/chat_base_system/toggle")

        # Should be back to initial state
        response = await client.get("/api/system-prompts/templates/chat_base_system")
        assert response.json()["is_active"] == initial_active

    async def test_toggle_nonexistent_template(self, client):
        """Test toggling non-existent template returns 404"""
        response = await client.post("/api/system-prompts/templates/nonexistent/toggle")

        assert response.status_code == 404


@pytest.mark.asyncio
class TestCacheOperations:
    """Test cache management endpoints"""

    async def test_get_cache_stats(self, client):
        """Test getting cache statistics"""
        response = await client.get("/api/system-prompts/cache/stats")

        assert response.status_code == 200
        data = response.json()

        assert "cache_size" in data
        assert "cache_ttl_minutes" in data
        assert "cached_keys" in data

        assert isinstance(data["cache_size"], int)
        assert isinstance(data["cache_ttl_minutes"], float)
        assert isinstance(data["cached_keys"], list)
        assert data["cache_ttl_minutes"] == 5.0

    async def test_clear_cache(self, client):
        """Test clearing cache"""
        response = await client.post("/api/system-prompts/cache/clear")

        assert response.status_code == 200
        data = response.json()

        assert "message" in data
        assert "cleared" in data["message"].lower()

        # Verify cache is empty
        stats_response = await client.get("/api/system-prompts/cache/stats")
        stats = stats_response.json()
        assert stats["cache_size"] == 0


@pytest.mark.asyncio
class TestDataIntegrity:
    """Test data integrity and consistency"""

    async def test_all_templates_have_required_fields(self, client):
        """Test all templates have required fields"""
        response = await client.get("/api/system-prompts/templates")
        templates = response.json()["templates"]

        for template in templates:
            assert template["id"]
            assert template["category"]
            assert template["template_key"]
            assert template["name"]
            assert template["template"]
            assert isinstance(template["variables"], list)
            assert isinstance(template["metadata"], dict)
            assert isinstance(template["is_default"], bool)
            assert isinstance(template["is_active"], bool)

    async def test_unique_template_keys(self, client):
        """Test all template keys are unique"""
        response = await client.get("/api/system-prompts/templates")
        templates = response.json()["templates"]

        keys = [t["template_key"] for t in templates]
        assert len(keys) == len(set(keys))  # No duplicates

    async def test_category_counts(self, client):
        """Test correct counts per category"""
        expected_counts = {
            "chat": 4,
            "research": 4,
            "orchestration": 5,
            "microsite": 15
        }

        for category, expected_count in expected_counts.items():
            response = await client.get(f"/api/system-prompts/templates?category={category}")
            actual_count = response.json()["total"]
            assert actual_count == expected_count, f"Category {category}: expected {expected_count}, got {actual_count}"


@pytest.mark.asyncio
class TestConcurrency:
    """Test concurrent operations"""

    async def test_concurrent_reads(self, client):
        """Test concurrent reads don't cause issues"""
        import asyncio

        # Read same template concurrently
        tasks = [
            client.get("/api/system-prompts/templates/chat_base_system")
            for _ in range(10)
        ]

        responses = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r.status_code == 200 for r in responses)

        # All should return same data
        first_data = responses[0].json()
        assert all(r.json() == first_data for r in responses)

    async def test_concurrent_updates(self, client):
        """Test concurrent updates are handled correctly"""
        import asyncio

        # Update same template concurrently with different values
        tasks = [
            client.put(
                "/api/system-prompts/templates/chat_base_system",
                json={"template": f"Test {i}"}
            )
            for i in range(5)
        ]

        responses = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r.status_code == 200 for r in responses)

        # Reset after test
        await client.post("/api/system-prompts/templates/chat_base_system/reset")
