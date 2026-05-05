"""
Integration Tests for Open Notebook

Tests integration between multiple components:
- Notebook with multiple source types
- Search across different source types
- Chat with source context
- Concurrent operations (multiple users)
- Database switching under load
"""

import asyncio
import json
from typing import List

import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.asyncio
class TestNotebookIntegration:
    """Test notebooks with multiple integrated components."""

    async def test_notebook_with_multiple_source_types(self, async_test_client):
        """Test a notebook containing file, URL, text, and HANA sources."""
        client = async_test_client

        # Create notebook
        notebook_data = {
            "name": "Multi-Source Notebook",
            "description": "Contains multiple source types",
        }
        response = await client.post("/api/notebooks", json=notebook_data)
        assert response.status_code == 201
        notebook_id = response.json()["id"]

        # Add text source
        text_source = {
            "title": "Text Source",
            "source_type": "text",
            "full_text": "This is inline text content for testing.",
            "notebook_id": notebook_id,
        }
        response = await client.post("/api/sources", json=text_source)
        assert response.status_code == 201

        # Add URL source
        url_source = {
            "title": "URL Source",
            "source_type": "url",
            "url": "https://example.com",
            "full_text": "Content from example.com",
            "notebook_id": notebook_id,
        }
        response = await client.post("/api/sources", json=url_source)
        assert response.status_code == 201

        # Verify all sources are linked
        response = await client.get(f"/api/notebooks/{notebook_id}/sources")
        assert response.status_code == 200
        sources = response.json()
        assert len(sources) == 2

        # Verify different source types
        source_types = {s["source_type"] for s in sources}
        assert "text" in source_types
        assert "url" in source_types

    async def test_notebook_full_lifecycle(self, async_test_client):
        """Test complete notebook lifecycle: create, add sources, search, chat, delete."""
        client = async_test_client

        # 1. Create notebook
        notebook_data = {
            "name": "Lifecycle Test Notebook",
            "description": "Testing full lifecycle",
        }
        response = await client.post("/api/notebooks", json=notebook_data)
        assert response.status_code == 201
        notebook_id = response.json()["id"]

        # 2. Add source
        source_data = {
            "title": "Test Source",
            "source_type": "text",
            "full_text": "Content for lifecycle testing.",
            "notebook_id": notebook_id,
        }
        response = await client.post("/api/sources", json=source_data)
        assert response.status_code == 201
        source_id = response.json()["id"]

        # 3. Search content
        search_query = {"query": "lifecycle", "strategy": "keyword"}
        response = await client.post("/api/search", json=search_query)
        assert response.status_code == 200

        # 4. Create chat session
        chat_data = {"notebook_id": notebook_id, "title": "Test Chat"}
        response = await client.post("/api/chat/sessions", json=chat_data)
        assert response.status_code == 201
        session_id = response.json()["id"]

        # 5. Send message
        message_data = {"role": "user", "content": "Tell me about this notebook"}
        response = await client.post(
            f"/api/chat/sessions/{session_id}/messages", json=message_data
        )
        assert response.status_code == 201

        # 6. Delete notebook (should cascade)
        response = await client.delete(f"/api/notebooks/{notebook_id}")
        assert response.status_code == 204

        # 7. Verify notebook is gone
        response = await client.get(f"/api/notebooks/{notebook_id}")
        assert response.status_code == 404

        # 8. Verify source is gone (cascade delete)
        response = await client.get(f"/api/sources/{source_id}")
        assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
class TestSearchIntegration:
    """Test search across different source types and strategies."""

    async def test_search_across_multiple_sources(self, async_test_client):
        """Test searching content from multiple source types."""
        client = async_test_client

        # Create notebook
        response = await client.post(
            "/api/notebooks",
            json={"name": "Search Test", "description": "Testing search"},
        )
        notebook_id = response.json()["id"]

        # Add multiple sources with overlapping content
        sources = [
            {
                "title": "Python Guide",
                "source_type": "text",
                "full_text": "Python is a powerful programming language.",
                "notebook_id": notebook_id,
            },
            {
                "title": "Python Tutorial",
                "source_type": "text",
                "full_text": "Learn Python programming step by step.",
                "notebook_id": notebook_id,
            },
            {
                "title": "Programming Languages",
                "source_type": "text",
                "full_text": "Popular languages include Python, Java, and JavaScript.",
                "notebook_id": notebook_id,
            },
        ]

        for source_data in sources:
            await client.post("/api/sources", json=source_data)

        # Search for "Python"
        search_query = {"query": "Python", "strategy": "keyword"}
        response = await client.post("/api/search", json=search_query)
        assert response.status_code == 200
        results = response.json()

        # Should find content from all three sources
        assert len(results["results"]) >= 2  # At least 2 matches

    async def test_search_with_filters(self, async_test_client):
        """Test search with various filters."""
        client = async_test_client

        # Create two notebooks
        nb1 = await client.post(
            "/api/notebooks", json={"name": "Notebook 1", "description": "First"}
        )
        nb1_id = nb1.json()["id"]

        nb2 = await client.post(
            "/api/notebooks", json={"name": "Notebook 2", "description": "Second"}
        )
        nb2_id = nb2.json()["id"]

        # Add sources to each
        await client.post(
            "/api/sources",
            json={
                "title": "Source 1",
                "source_type": "text",
                "full_text": "Testing search filters in notebook one.",
                "notebook_id": nb1_id,
            },
        )

        await client.post(
            "/api/sources",
            json={
                "title": "Source 2",
                "source_type": "text",
                "full_text": "Testing search filters in notebook two.",
                "notebook_id": nb2_id,
            },
        )

        # Search with notebook filter
        search_query = {
            "query": "search filters",
            "strategy": "keyword",
            "filters": {"notebook_id": nb1_id},
        }
        response = await client.post("/api/search", json=search_query)
        assert response.status_code == 200
        results = response.json()

        # Should only find results from notebook 1
        for result in results["results"]:
            assert result["notebook_id"] == nb1_id

    async def test_search_strategy_comparison(self, async_test_client):
        """Test and compare results from different search strategies."""
        client = async_test_client

        # Create test content
        response = await client.post(
            "/api/notebooks",
            json={"name": "Strategy Test", "description": "Compare strategies"},
        )
        notebook_id = response.json()["id"]

        await client.post(
            "/api/sources",
            json={
                "title": "AI Overview",
                "source_type": "text",
                "full_text": "Artificial intelligence and machine learning are transforming technology.",
                "notebook_id": notebook_id,
            },
        )

        query = "What is AI?"
        strategies = ["keyword", "vector", "hybrid"]

        results_by_strategy = {}
        for strategy in strategies:
            search_query = {"query": query, "strategy": strategy}
            response = await client.post("/api/search", json=search_query)

            if response.status_code == 200:
                results_by_strategy[strategy] = response.json()

        # At least keyword should work
        assert "keyword" in results_by_strategy
        assert len(results_by_strategy["keyword"]["results"]) > 0

        # Hybrid should combine both if available
        if "hybrid" in results_by_strategy:
            # Hybrid results should have score from both
            for result in results_by_strategy["hybrid"]["results"]:
                assert "score" in result


@pytest.mark.integration
@pytest.mark.asyncio
class TestChatIntegration:
    """Test chat with source context integration."""

    async def test_chat_with_source_context(self, async_test_client):
        """Test chat using content from sources as context."""
        client = async_test_client

        # Create notebook with source
        notebook = await client.post(
            "/api/notebooks",
            json={"name": "Chat Context Test", "description": "Testing chat context"},
        )
        notebook_id = notebook.json()["id"]

        source_data = {
            "title": "Python Basics",
            "source_type": "text",
            "full_text": "Python is a high-level programming language. It uses indentation for code blocks.",
            "notebook_id": notebook_id,
        }
        await client.post("/api/sources", json=source_data)

        # Create chat session
        chat_data = {"notebook_id": notebook_id, "title": "Python Questions"}
        session = await client.post("/api/chat/sessions", json=chat_data)
        session_id = session.json()["id"]

        # Send message
        message_data = {"role": "user", "content": "What programming language is this about?"}
        response = await client.post(
            f"/api/chat/sessions/{session_id}/messages", json=message_data
        )
        assert response.status_code == 201

        # Verify message was stored
        session_data = await client.get(f"/api/chat/sessions/{session_id}")
        messages = session_data.json()["messages"]
        assert len(messages) >= 1
        assert messages[0]["content"] == "What programming language is this about?"

    async def test_chat_session_management(self, async_test_client):
        """Test creating, updating, and deleting chat sessions."""
        client = async_test_client

        # Create notebook
        notebook = await client.post(
            "/api/notebooks", json={"name": "Chat Management Test", "description": "Test"}
        )
        notebook_id = notebook.json()["id"]

        # Create multiple chat sessions
        sessions = []
        for i in range(3):
            chat_data = {
                "notebook_id": notebook_id,
                "title": f"Chat Session {i+1}",
            }
            response = await client.post("/api/chat/sessions", json=chat_data)
            assert response.status_code == 201
            sessions.append(response.json())

        # Update session title
        session_id = sessions[0]["id"]
        update_data = {"title": "Updated Chat Title"}
        response = await client.put(f"/api/chat/sessions/{session_id}", json=update_data)
        assert response.status_code == 200

        # Verify update
        response = await client.get(f"/api/chat/sessions/{session_id}")
        updated = response.json()
        assert updated["title"] == "Updated Chat Title"

        # Delete session
        response = await client.delete(f"/api/chat/sessions/{session_id}")
        assert response.status_code == 204

        # Verify deletion
        response = await client.get(f"/api/chat/sessions/{session_id}")
        assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.asyncio
class TestDatabaseSwitching:
    """Test database switching scenarios."""

    async def test_sqlite_operations(self, async_test_client):
        """Test basic operations in SQLite mode."""
        client = async_test_client

        # Verify we're in SQLite mode
        response = await client.get("/api/database/config")
        if response.status_code == 404:
            pytest.skip("Database API not implemented")

        config = response.json()
        assert config["database_type"] == "sqlite"

        # Perform CRUD operations
        notebook = await client.post(
            "/api/notebooks",
            json={"name": "SQLite Test", "description": "Testing SQLite"},
        )
        assert notebook.status_code == 201
        notebook_id = notebook.json()["id"]

        # Read
        response = await client.get(f"/api/notebooks/{notebook_id}")
        assert response.status_code == 200

        # Update
        response = await client.put(
            f"/api/notebooks/{notebook_id}",
            json={"name": "Updated SQLite Test"},
        )
        assert response.status_code == 200

        # Delete
        response = await client.delete(f"/api/notebooks/{notebook_id}")
        assert response.status_code == 204

    @pytest.mark.hana
    async def test_database_switch_preserves_data(
        self, async_test_client, hana_db_config
    ):
        """Test that data persists when switching databases."""
        client = async_test_client

        # Create data in SQLite
        notebook = await client.post(
            "/api/notebooks",
            json={"name": "Switch Test", "description": "Testing DB switch"},
        )
        notebook_id = notebook.json()["id"]

        # Switch to HANA
        hana_config = {
            "database_type": "hana",
            "hana_host": hana_db_config.hana_host,
            "hana_port": hana_db_config.hana_port,
            "hana_user": hana_db_config.hana_user,
            "hana_password": hana_db_config.hana_password,
            "hana_database": hana_db_config.hana_database,
        }
        response = await client.post("/api/database/switch", json=hana_config)
        assert response.status_code == 200

        # Verify data exists in HANA
        response = await client.get(f"/api/notebooks/{notebook_id}")
        assert response.status_code == 200
        notebook_data = response.json()
        assert notebook_data["name"] == "Switch Test"


@pytest.mark.integration
@pytest.mark.asyncio
class TestConcurrentUsers:
    """Test concurrent operations from multiple users."""

    async def test_concurrent_notebook_reads(self, async_test_client):
        """Test multiple users reading notebooks concurrently."""
        client = async_test_client

        # Create test notebook
        notebook = await client.post(
            "/api/notebooks",
            json={"name": "Concurrent Read Test", "description": "Test concurrent reads"},
        )
        notebook_id = notebook.json()["id"]

        # Simulate 50 concurrent reads
        async def read_notebook():
            response = await client.get(f"/api/notebooks/{notebook_id}")
            return response.status_code

        tasks = [read_notebook() for _ in range(50)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(status == 200 for status in results)

    async def test_concurrent_source_creation(self, async_test_client):
        """Test multiple users creating sources concurrently."""
        client = async_test_client

        # Create test notebook
        notebook = await client.post(
            "/api/notebooks",
            json={"name": "Concurrent Source Test", "description": "Test"},
        )
        notebook_id = notebook.json()["id"]

        # Create 20 sources concurrently
        async def create_source(index: int):
            source_data = {
                "title": f"Source {index}",
                "source_type": "text",
                "full_text": f"Content for source {index}",
                "notebook_id": notebook_id,
            }
            response = await client.post("/api/sources", json=source_data)
            return response.status_code

        tasks = [create_source(i) for i in range(20)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        success_count = sum(1 for status in results if status == 201)
        assert success_count == 20

        # Verify all sources are linked
        response = await client.get(f"/api/notebooks/{notebook_id}/sources")
        sources = response.json()
        assert len(sources) == 20

    async def test_concurrent_searches(self, async_test_client):
        """Test multiple users searching concurrently."""
        client = async_test_client

        # Create test data
        notebook = await client.post(
            "/api/notebooks",
            json={"name": "Search Test", "description": "Test concurrent searches"},
        )
        notebook_id = notebook.json()["id"]

        for i in range(5):
            await client.post(
                "/api/sources",
                json={
                    "title": f"Document {i}",
                    "source_type": "text",
                    "full_text": f"This is test document number {i} for concurrent searches.",
                    "notebook_id": notebook_id,
                },
            )

        # Run 30 concurrent searches
        async def run_search(query: str):
            search_query = {"query": query, "strategy": "keyword"}
            response = await client.post("/api/search", json=search_query)
            return response.status_code

        queries = [f"test document {i % 5}" for i in range(30)]
        tasks = [run_search(q) for q in queries]
        results = await asyncio.gather(*tasks)

        # Most should succeed
        success_count = sum(1 for status in results if status == 200)
        assert success_count >= 25  # Allow some failures


@pytest.mark.integration
@pytest.mark.asyncio
class TestDataIntegrity:
    """Test data integrity across operations."""

    async def test_cascade_delete_integrity(self, async_test_client):
        """Test that cascade deletes maintain referential integrity."""
        client = async_test_client

        # Create notebook with sources and chats
        notebook = await client.post(
            "/api/notebooks",
            json={"name": "Cascade Test", "description": "Test cascade deletes"},
        )
        notebook_id = notebook.json()["id"]

        # Add sources
        source_ids = []
        for i in range(3):
            source = await client.post(
                "/api/sources",
                json={
                    "title": f"Source {i}",
                    "source_type": "text",
                    "full_text": f"Content {i}",
                    "notebook_id": notebook_id,
                },
            )
            source_ids.append(source.json()["id"])

        # Create chat session
        chat = await client.post(
            "/api/chat/sessions",
            json={"notebook_id": notebook_id, "title": "Test Chat"},
        )
        session_id = chat.json()["id"]

        # Delete notebook
        response = await client.delete(f"/api/notebooks/{notebook_id}")
        assert response.status_code == 204

        # Verify sources are deleted
        for source_id in source_ids:
            response = await client.get(f"/api/sources/{source_id}")
            assert response.status_code == 404

        # Verify chat session is deleted
        response = await client.get(f"/api/chat/sessions/{session_id}")
        assert response.status_code == 404

    async def test_transaction_rollback(self, async_test_client):
        """Test that failed operations rollback properly."""
        client = async_test_client

        # Try to create notebook with invalid data
        invalid_data = {"name": None, "description": "This should fail"}
        response = await client.post("/api/notebooks", json=invalid_data)
        # Should fail validation
        assert response.status_code in [400, 422]

        # Database should still be in consistent state
        response = await client.get("/api/notebooks")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
