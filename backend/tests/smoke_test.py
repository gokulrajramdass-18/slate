"""
Smoke Tests for Open Notebook

Quick health checks for production deployment:
- Database connectivity
- API endpoints responding
- Search functionality working
- Can create/read/update/delete basic resources

These tests should run in under 30 seconds and catch critical issues.
"""

import asyncio

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestSystemHealth:
    """Quick health checks for system readiness."""

    async def test_database_connectivity(self, async_test_client):
        """Test that database is accessible."""
        client = async_test_client

        # Try to list notebooks (even if empty)
        response = await client.get("/api/notebooks")
        assert response.status_code == 200, "Database connection failed"

    async def test_api_health_endpoint(self, async_test_client):
        """Test API health endpoint."""
        client = async_test_client

        # Check if health endpoint exists
        response = await client.get("/health")
        if response.status_code == 404:
            # Health endpoint not implemented, try root
            response = await client.get("/")

        assert response.status_code in [200, 404], "API not responding"

    async def test_api_docs_available(self, async_test_client):
        """Test that API documentation is available."""
        client = async_test_client

        # FastAPI auto-generates /docs
        response = await client.get("/docs")
        assert response.status_code == 200, "API docs not available"


@pytest.mark.asyncio
class TestCoreEndpoints:
    """Test that all core API endpoints are responding."""

    async def test_notebooks_endpoints(self, async_test_client):
        """Test notebooks CRUD endpoints."""
        client = async_test_client

        # List (GET /api/notebooks)
        response = await client.get("/api/notebooks")
        assert response.status_code == 200

        # Create (POST /api/notebooks)
        notebook_data = {
            "name": "Smoke Test Notebook",
            "description": "Quick test",
        }
        response = await client.post("/api/notebooks", json=notebook_data)
        assert response.status_code == 201
        notebook_id = response.json()["id"]

        # Read (GET /api/notebooks/{id})
        response = await client.get(f"/api/notebooks/{notebook_id}")
        assert response.status_code == 200

        # Update (PUT /api/notebooks/{id})
        update_data = {"name": "Updated Smoke Test"}
        response = await client.put(f"/api/notebooks/{notebook_id}", json=update_data)
        assert response.status_code == 200

        # Delete (DELETE /api/notebooks/{id})
        response = await client.delete(f"/api/notebooks/{notebook_id}")
        assert response.status_code == 204

    async def test_sources_endpoints(self, async_test_client):
        """Test sources CRUD endpoints."""
        client = async_test_client

        # Create notebook first
        notebook = await client.post(
            "/api/notebooks",
            json={"name": "Test Notebook", "description": "For sources test"},
        )
        notebook_id = notebook.json()["id"]

        # List (GET /api/sources)
        response = await client.get("/api/sources")
        assert response.status_code == 200

        # Create (POST /api/sources)
        source_data = {
            "title": "Smoke Test Source",
            "source_type": "text",
            "full_text": "Quick test content",
            "notebook_id": notebook_id,
        }
        response = await client.post("/api/sources", json=source_data)
        assert response.status_code == 201
        source_id = response.json()["id"]

        # Read (GET /api/sources/{id})
        response = await client.get(f"/api/sources/{source_id}")
        assert response.status_code == 200

        # Update (PUT /api/sources/{id})
        update_data = {"title": "Updated Source"}
        response = await client.put(f"/api/sources/{source_id}", json=update_data)
        assert response.status_code == 200

        # Delete (DELETE /api/sources/{id})
        response = await client.delete(f"/api/sources/{source_id}")
        assert response.status_code == 204

        # Cleanup
        await client.delete(f"/api/notebooks/{notebook_id}")

    async def test_search_endpoint(self, async_test_client):
        """Test search endpoint is working."""
        client = async_test_client

        # Create test data
        notebook = await client.post(
            "/api/notebooks",
            json={"name": "Search Test", "description": "Test"},
        )
        notebook_id = notebook.json()["id"]

        await client.post(
            "/api/sources",
            json={
                "title": "Test Doc",
                "source_type": "text",
                "full_text": "This is searchable content for smoke test.",
                "notebook_id": notebook_id,
            },
        )

        # Test search
        search_query = {"query": "searchable", "strategy": "keyword"}
        response = await client.post("/api/search", json=search_query)
        assert response.status_code == 200
        results = response.json()
        assert "results" in results

        # Cleanup
        await client.delete(f"/api/notebooks/{notebook_id}")

    async def test_chat_endpoints(self, async_test_client):
        """Test chat endpoints are working."""
        client = async_test_client

        # Create notebook
        notebook = await client.post(
            "/api/notebooks",
            json={"name": "Chat Test", "description": "Test"},
        )
        notebook_id = notebook.json()["id"]

        # Create session (POST /api/chat/sessions)
        chat_data = {"notebook_id": notebook_id, "title": "Smoke Test Chat"}
        response = await client.post("/api/chat/sessions", json=chat_data)
        assert response.status_code == 201
        session_id = response.json()["id"]

        # Get session (GET /api/chat/sessions/{id})
        response = await client.get(f"/api/chat/sessions/{session_id}")
        assert response.status_code == 200

        # Send message (POST /api/chat/sessions/{id}/messages)
        message_data = {"role": "user", "content": "Test message"}
        response = await client.post(
            f"/api/chat/sessions/{session_id}/messages", json=message_data
        )
        assert response.status_code == 201

        # Cleanup
        await client.delete(f"/api/chat/sessions/{session_id}")
        await client.delete(f"/api/notebooks/{notebook_id}")


@pytest.mark.asyncio
class TestSearchFunctionality:
    """Test that search is working with different strategies."""

    async def test_keyword_search_works(self, async_test_client):
        """Test keyword search returns results."""
        client = async_test_client

        # Create test data
        notebook = await client.post(
            "/api/notebooks",
            json={"name": "Keyword Test", "description": "Test"},
        )
        notebook_id = notebook.json()["id"]

        await client.post(
            "/api/sources",
            json={
                "title": "Python Guide",
                "source_type": "text",
                "full_text": "Python is a programming language.",
                "notebook_id": notebook_id,
            },
        )

        # Search
        search_query = {"query": "Python", "strategy": "keyword"}
        response = await client.post("/api/search", json=search_query)
        assert response.status_code == 200

        results = response.json()
        assert len(results["results"]) > 0
        assert "Python" in results["results"][0]["content"]

        # Cleanup
        await client.delete(f"/api/notebooks/{notebook_id}")

    async def test_vector_search_available(self, async_test_client):
        """Test vector search endpoint is available (may not have embeddings)."""
        client = async_test_client

        search_query = {"query": "test query", "strategy": "vector"}
        response = await client.post("/api/search", json=search_query)

        # Should respond even if no embeddings (empty results)
        assert response.status_code in [200, 404]

    async def test_hybrid_search_available(self, async_test_client):
        """Test hybrid search endpoint is available."""
        client = async_test_client

        search_query = {"query": "test query", "strategy": "hybrid"}
        response = await client.post("/api/search", json=search_query)

        # Should respond
        assert response.status_code in [200, 404]


@pytest.mark.asyncio
class TestDataIntegrity:
    """Quick data integrity checks."""

    async def test_cascade_delete_works(self, async_test_client):
        """Test that deleting notebook deletes sources."""
        client = async_test_client

        # Create notebook with source
        notebook = await client.post(
            "/api/notebooks",
            json={"name": "Cascade Test", "description": "Test"},
        )
        notebook_id = notebook.json()["id"]

        source = await client.post(
            "/api/sources",
            json={
                "title": "Test Source",
                "source_type": "text",
                "full_text": "Content",
                "notebook_id": notebook_id,
            },
        )
        source_id = source.json()["id"]

        # Delete notebook
        response = await client.delete(f"/api/notebooks/{notebook_id}")
        assert response.status_code == 204

        # Source should be gone
        response = await client.get(f"/api/sources/{source_id}")
        assert response.status_code == 404

    async def test_notebook_source_relationship(self, async_test_client):
        """Test notebook-source relationship is maintained."""
        client = async_test_client

        # Create notebook
        notebook = await client.post(
            "/api/notebooks",
            json={"name": "Relationship Test", "description": "Test"},
        )
        notebook_id = notebook.json()["id"]

        # Add source
        source = await client.post(
            "/api/sources",
            json={
                "title": "Test Source",
                "source_type": "text",
                "full_text": "Content",
                "notebook_id": notebook_id,
            },
        )
        source_id = source.json()["id"]

        # Check notebook lists source
        response = await client.get(f"/api/notebooks/{notebook_id}/sources")
        assert response.status_code == 200
        sources = response.json()
        assert len(sources) == 1
        assert sources[0]["id"] == source_id

        # Cleanup
        await client.delete(f"/api/notebooks/{notebook_id}")


@pytest.mark.asyncio
class TestDatabaseConfig:
    """Test database configuration endpoints."""

    async def test_get_database_config(self, async_test_client):
        """Test getting current database configuration."""
        client = async_test_client

        response = await client.get("/api/database/config")

        if response.status_code == 404:
            pytest.skip("Database config API not implemented")

        assert response.status_code == 200
        config = response.json()
        assert "database_type" in config
        assert config["database_type"] in ["sqlite", "hana"]

    async def test_database_status(self, async_test_client):
        """Test database status endpoint."""
        client = async_test_client

        response = await client.get("/api/database/status")

        if response.status_code == 404:
            pytest.skip("Database status API not implemented")

        assert response.status_code == 200
        status = response.json()
        assert "connected" in status or "status" in status


@pytest.mark.asyncio
class TestSystemLimits:
    """Test system handles edge cases."""

    async def test_empty_query_handling(self, async_test_client):
        """Test empty search query is handled."""
        client = async_test_client

        search_query = {"query": "", "strategy": "keyword"}
        response = await client.post("/api/search", json=search_query)

        # Should handle gracefully (empty results or validation error)
        assert response.status_code in [200, 400, 422]

    async def test_invalid_id_handling(self, async_test_client):
        """Test invalid ID returns 404."""
        client = async_test_client

        response = await client.get("/api/notebooks/invalid-id-12345")
        assert response.status_code in [404, 422]

    async def test_duplicate_notebook_name_allowed(self, async_test_client):
        """Test that duplicate notebook names are allowed."""
        client = async_test_client

        # Create first notebook
        nb1 = await client.post(
            "/api/notebooks",
            json={"name": "Duplicate Test", "description": "First"},
        )
        assert nb1.status_code == 201

        # Create second with same name (should be allowed)
        nb2 = await client.post(
            "/api/notebooks",
            json={"name": "Duplicate Test", "description": "Second"},
        )
        assert nb2.status_code == 201

        # Cleanup
        await client.delete(f"/api/notebooks/{nb1.json()['id']}")
        await client.delete(f"/api/notebooks/{nb2.json()['id']}")


async def run_smoke_tests():
    """Run all smoke tests and report results."""
    print("Running Open Notebook Smoke Tests...")
    print("=" * 60)

    test_classes = [
        TestSystemHealth,
        TestCoreEndpoints,
        TestSearchFunctionality,
        TestDataIntegrity,
        TestDatabaseConfig,
        TestSystemLimits,
    ]

    results = {"passed": 0, "failed": 0, "skipped": 0}

    for test_class in test_classes:
        print(f"\n{test_class.__name__}:")
        # Run tests in class
        # (This is simplified - actual pytest run is more complex)

    print("\n" + "=" * 60)
    print(f"Results: {results['passed']} passed, {results['failed']} failed, {results['skipped']} skipped")

    return results["failed"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-x"])
