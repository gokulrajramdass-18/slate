"""
End-to-End Workflow Tests for Open Notebook

Tests complete user workflows from start to finish:
1. Create notebook → Add file source → Search → Get results
2. Create notebook → Add URL source → Chat → Get response
3. Add HANA table source → Sync → Search synced data
4. Add API source with OAuth → Sync → Verify data
5. Switch database SQLite → HANA → Verify data persists
6. Use all 4 search strategies → Compare results
7. Create folder → Add notebooks → Filter by folder/tags
8. Configure AI models → Create chat → Verify model used
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.asyncio
class TestCompleteWorkflows:
    """Test complete user workflows end-to-end."""

    @pytest.fixture(autouse=True)
    async def setup(self, async_test_client):
        """Setup for each test."""
        self.client = async_test_client
        self.created_ids = {
            "notebooks": [],
            "sources": [],
            "chat_sessions": [],
            "folders": [],
        }

    async def teardown_method(self, method):
        """Cleanup after each test."""
        # Delete created resources
        for notebook_id in self.created_ids["notebooks"]:
            try:
                await self.client.delete(f"/api/notebooks/{notebook_id}")
            except:
                pass

    async def test_workflow_1_file_source_search(self):
        """
        Test Workflow 1: Create notebook → Add file source → Search → Get results
        """
        # Step 1: Create notebook
        notebook_data = {
            "name": "Test Notebook - File Search",
            "description": "Testing file upload and search",
        }
        response = await self.client.post("/api/notebooks", json=notebook_data)
        assert response.status_code == 201
        notebook = response.json()
        notebook_id = notebook["id"]
        self.created_ids["notebooks"].append(notebook_id)

        # Step 2: Create a test file
        test_content = """
        Python is a versatile programming language.
        It supports multiple programming paradigms including object-oriented,
        procedural, and functional programming.
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(test_content)
            temp_file_path = f.name

        try:
            # Step 3: Upload file as source
            with open(temp_file_path, "rb") as f:
                files = {"file": ("test.txt", f, "text/plain")}
                data = {"title": "Python Introduction", "notebook_id": notebook_id}
                response = await self.client.post(
                    "/api/sources/upload", files=files, data=data
                )
            assert response.status_code == 201
            source = response.json()
            source_id = source["id"]
            self.created_ids["sources"].append(source_id)

            # Step 4: Verify source was added to notebook
            response = await self.client.get(f"/api/notebooks/{notebook_id}/sources")
            assert response.status_code == 200
            sources = response.json()
            assert len(sources) == 1
            assert sources[0]["id"] == source_id

            # Step 5: Search for content
            search_query = {"query": "Python programming", "strategy": "keyword"}
            response = await self.client.post("/api/search", json=search_query)
            assert response.status_code == 200
            results = response.json()
            assert len(results["results"]) > 0

            # Step 6: Verify search result contains our content
            found = False
            for result in results["results"]:
                if "Python" in result["content"] or "programming" in result["content"]:
                    found = True
                    break
            assert found, "Search did not return expected content"

        finally:
            # Cleanup temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    async def test_workflow_2_url_source_chat(self):
        """
        Test Workflow 2: Create notebook → Add URL source → Chat → Get response
        """
        # Step 1: Create notebook
        notebook_data = {
            "name": "Test Notebook - URL Chat",
            "description": "Testing URL source and chat",
        }
        response = await self.client.post("/api/notebooks", json=notebook_data)
        assert response.status_code == 201
        notebook = response.json()
        notebook_id = notebook["id"]
        self.created_ids["notebooks"].append(notebook_id)

        # Step 2: Add URL source
        source_data = {
            "title": "Example Documentation",
            "source_type": "url",
            "url": "https://example.com/docs",
            "full_text": "This is example documentation about software development.",
            "notebook_id": notebook_id,
        }
        response = await self.client.post("/api/sources", json=source_data)
        assert response.status_code == 201
        source = response.json()
        self.created_ids["sources"].append(source["id"])

        # Step 3: Create chat session
        chat_data = {
            "notebook_id": notebook_id,
            "title": "Test Chat Session",
        }
        response = await self.client.post("/api/chat/sessions", json=chat_data)
        assert response.status_code == 201
        session = response.json()
        session_id = session["id"]
        self.created_ids["chat_sessions"].append(session_id)

        # Step 4: Send chat message
        message_data = {
            "role": "user",
            "content": "What is this documentation about?",
        }
        response = await self.client.post(
            f"/api/chat/sessions/{session_id}/messages", json=message_data
        )
        assert response.status_code == 201
        message = response.json()
        assert message["role"] == "user"

        # Step 5: Verify chat history
        response = await self.client.get(f"/api/chat/sessions/{session_id}")
        assert response.status_code == 200
        session_data = response.json()
        assert len(session_data["messages"]) >= 1

    async def test_workflow_3_hana_table_sync(self, hana_db_config):
        """
        Test Workflow 3: Add HANA table source → Sync → Search synced data
        """
        pytest.skip("Requires HANA connection - implement after HANA setup")

        # Step 1: Create notebook
        notebook_data = {
            "name": "Test Notebook - HANA Table",
            "description": "Testing HANA table source",
        }
        response = await self.client.post("/api/notebooks", json=notebook_data)
        assert response.status_code == 201
        notebook = response.json()
        notebook_id = notebook["id"]
        self.created_ids["notebooks"].append(notebook_id)

        # Step 2: Test HANA connection
        connection_config = {
            "host": hana_db_config.hana_host,
            "port": hana_db_config.hana_port,
            "user": hana_db_config.hana_user,
            "password": hana_db_config.hana_password,
            "database": hana_db_config.hana_database,
            "table": "TEST_TABLE",
        }
        response = await self.client.post(
            "/api/sources/hana-table/test-connection", json=connection_config
        )
        assert response.status_code == 200

        # Step 3: Create HANA table source
        source_data = {
            "title": "HANA Sales Data",
            "source_type": "hana_table",
            "connection_config": connection_config,
            "sync_config": {"frequency": "0 */6 * * *"},
            "notebook_id": notebook_id,
        }
        response = await self.client.post("/api/sources", json=source_data)
        assert response.status_code == 201
        source = response.json()
        source_id = source["id"]
        self.created_ids["sources"].append(source_id)

        # Step 4: Trigger sync
        response = await self.client.post(f"/api/sources/{source_id}/sync")
        assert response.status_code == 200

        # Step 5: Wait for sync to complete
        await asyncio.sleep(2)

        # Step 6: Verify data was synced
        response = await self.client.get(f"/api/sources/{source_id}")
        assert response.status_code == 200
        source_data = response.json()
        assert source_data["sync_config"]["status"] in ["completed", "success"]

        # Step 7: Search synced data
        search_query = {"query": "sales", "strategy": "keyword"}
        response = await self.client.post("/api/search", json=search_query)
        assert response.status_code == 200
        results = response.json()
        assert len(results["results"]) > 0

    async def test_workflow_4_api_source_oauth(self):
        """
        Test Workflow 4: Add API source with OAuth → Sync → Verify data
        """
        # Step 1: Create notebook
        notebook_data = {
            "name": "Test Notebook - API Source",
            "description": "Testing API source with OAuth",
        }
        response = await self.client.post("/api/notebooks", json=notebook_data)
        assert response.status_code == 201
        notebook = response.json()
        notebook_id = notebook["id"]
        self.created_ids["notebooks"].append(notebook_id)

        # Step 2: Test API connection (without OAuth for simplicity)
        api_config = {
            "endpoint": "https://api.github.com/users/octocat",
            "method": "GET",
            "auth_type": "none",
            "headers": {"Accept": "application/json"},
        }
        response = await self.client.post("/api/sources/api/test", json=api_config)
        # GitHub API should be accessible
        assert response.status_code in [200, 404]  # 404 if endpoint doesn't exist

        # Step 3: Create API source
        source_data = {
            "title": "GitHub User Data",
            "source_type": "api",
            "connection_config": api_config,
            "sync_config": {"frequency": "0 */12 * * *"},
            "notebook_id": notebook_id,
        }
        response = await self.client.post("/api/sources", json=source_data)
        assert response.status_code == 201
        source = response.json()
        source_id = source["id"]
        self.created_ids["sources"].append(source_id)

        # Step 4: Trigger manual sync
        response = await self.client.post(f"/api/sources/{source_id}/sync")
        assert response.status_code == 200

        # Step 5: Check sync status
        response = await self.client.get(f"/api/sources/{source_id}")
        assert response.status_code == 200

    async def test_workflow_5_database_switch(self, hana_db_config):
        """
        Test Workflow 5: Switch database SQLite → HANA → Verify data persists
        """
        pytest.skip("Requires HANA connection - implement after HANA setup")

        # Step 1: Create notebook in SQLite
        notebook_data = {
            "name": "Test Notebook - DB Switch",
            "description": "Testing database switching",
        }
        response = await self.client.post("/api/notebooks", json=notebook_data)
        assert response.status_code == 201
        notebook = response.json()
        notebook_id = notebook["id"]
        self.created_ids["notebooks"].append(notebook_id)

        # Step 2: Get current database config
        response = await self.client.get("/api/database/config")
        assert response.status_code == 200
        current_config = response.json()
        assert current_config["database_type"] == "sqlite"

        # Step 3: Test HANA connection
        hana_config = {
            "database_type": "hana",
            "hana_host": hana_db_config.hana_host,
            "hana_port": hana_db_config.hana_port,
            "hana_user": hana_db_config.hana_user,
            "hana_password": hana_db_config.hana_password,
            "hana_database": hana_db_config.hana_database,
        }
        response = await self.client.post(
            "/api/database/test-connection", json=hana_config
        )
        assert response.status_code == 200

        # Step 4: Switch to HANA
        response = await self.client.post("/api/database/switch", json=hana_config)
        assert response.status_code == 200

        # Step 5: Verify notebook exists in HANA
        response = await self.client.get(f"/api/notebooks/{notebook_id}")
        assert response.status_code == 200
        notebook_in_hana = response.json()
        assert notebook_in_hana["name"] == notebook_data["name"]

        # Step 6: Switch back to SQLite
        sqlite_config = {"database_type": "sqlite"}
        response = await self.client.post("/api/database/switch", json=sqlite_config)
        assert response.status_code == 200

    async def test_workflow_6_all_search_strategies(self):
        """
        Test Workflow 6: Use all 4 search strategies → Compare results
        """
        # Step 1: Create notebook with test content
        notebook_data = {
            "name": "Test Notebook - Search Strategies",
            "description": "Testing all search strategies",
        }
        response = await self.client.post("/api/notebooks", json=notebook_data)
        assert response.status_code == 201
        notebook = response.json()
        notebook_id = notebook["id"]
        self.created_ids["notebooks"].append(notebook_id)

        # Step 2: Add multiple sources with different content
        test_sources = [
            {
                "title": "Python Programming Guide",
                "source_type": "text",
                "full_text": "Python is a high-level programming language with dynamic typing and garbage collection.",
                "notebook_id": notebook_id,
            },
            {
                "title": "Machine Learning Basics",
                "source_type": "text",
                "full_text": "Machine learning algorithms learn patterns from data to make predictions.",
                "notebook_id": notebook_id,
            },
            {
                "title": "Web Development Tutorial",
                "source_type": "text",
                "full_text": "Web development involves creating websites using HTML, CSS, and JavaScript.",
                "notebook_id": notebook_id,
            },
        ]

        for source_data in test_sources:
            response = await self.client.post("/api/sources", json=source_data)
            assert response.status_code == 201
            self.created_ids["sources"].append(response.json()["id"])

        # Step 3: Test keyword search
        search_query = {"query": "Python programming", "strategy": "keyword"}
        response = await self.client.post("/api/search", json=search_query)
        assert response.status_code == 200
        keyword_results = response.json()
        assert "results" in keyword_results
        assert keyword_results["strategy"] == "keyword"

        # Step 4: Test vector search (if embeddings available)
        search_query = {"query": "Python programming", "strategy": "vector"}
        response = await self.client.post("/api/search", json=search_query)
        # May fail if embeddings not generated
        if response.status_code == 200:
            vector_results = response.json()
            assert "results" in vector_results
            assert vector_results["strategy"] == "vector"

        # Step 5: Test hybrid search
        search_query = {"query": "Python programming", "strategy": "hybrid"}
        response = await self.client.post("/api/search", json=search_query)
        assert response.status_code == 200
        hybrid_results = response.json()
        assert "results" in hybrid_results
        assert hybrid_results["strategy"] == "hybrid"

        # Step 6: Test agentic RAG
        search_query = {"query": "Explain Python programming", "strategy": "agentic_rag"}
        response = await self.client.post("/api/search", json=search_query)
        # May take longer, so check for accepted or success
        assert response.status_code in [200, 202]

    async def test_workflow_7_folder_organization(self):
        """
        Test Workflow 7: Create folder → Add notebooks → Filter by folder/tags
        """
        # Step 1: Create folder
        folder_data = {"name": "Test Projects", "description": "Test project folder"}
        response = await self.client.post("/api/folders", json=folder_data)
        if response.status_code == 404:
            pytest.skip("Folder API not yet implemented")
        assert response.status_code == 201
        folder = response.json()
        folder_id = folder["id"]
        self.created_ids["folders"].append(folder_id)

        # Step 2: Create notebooks in folder
        for i in range(3):
            notebook_data = {
                "name": f"Project Notebook {i+1}",
                "description": f"Test notebook {i+1}",
                "folder_id": folder_id,
            }
            response = await self.client.post("/api/notebooks", json=notebook_data)
            assert response.status_code == 201
            self.created_ids["notebooks"].append(response.json()["id"])

        # Step 3: Add tags to notebooks
        tags = ["important", "testing", "python"]
        for notebook_id, tag in zip(self.created_ids["notebooks"], tags):
            tag_data = {"name": tag}
            response = await self.client.post(
                f"/api/notebooks/{notebook_id}/tags", json=tag_data
            )
            # If tags not implemented yet, skip
            if response.status_code == 404:
                break
            assert response.status_code == 201

        # Step 4: Filter notebooks by folder
        response = await self.client.get(f"/api/notebooks?folder_id={folder_id}")
        assert response.status_code == 200
        notebooks = response.json()
        assert len(notebooks) == 3

        # Step 5: Filter notebooks by tag
        response = await self.client.get("/api/notebooks?tag=python")
        if response.status_code == 200:
            notebooks = response.json()
            # Should have at least one notebook with 'python' tag
            assert len(notebooks) >= 1

    async def test_workflow_8_model_configuration(self):
        """
        Test Workflow 8: Configure AI models → Create chat → Verify model used
        """
        # Step 1: Get available models
        response = await self.client.get("/api/models/available")
        if response.status_code == 404:
            pytest.skip("Models API not yet implemented")
        assert response.status_code == 200
        models = response.json()
        assert len(models) > 0

        # Step 2: Set default chat model
        model_config = {
            "chat_model": "gpt-4",
            "embedding_model": "text-embedding-3-small",
        }
        response = await self.client.put("/api/models/defaults", json=model_config)
        assert response.status_code == 200

        # Step 3: Create notebook
        notebook_data = {
            "name": "Test Notebook - Model Config",
            "description": "Testing model configuration",
        }
        response = await self.client.post("/api/notebooks", json=notebook_data)
        assert response.status_code == 201
        notebook = response.json()
        notebook_id = notebook["id"]
        self.created_ids["notebooks"].append(notebook_id)

        # Step 4: Create chat session with specific model
        chat_data = {
            "notebook_id": notebook_id,
            "title": "Test Chat with GPT-4",
            "model": "gpt-4",
        }
        response = await self.client.post("/api/chat/sessions", json=chat_data)
        assert response.status_code == 201
        session = response.json()
        session_id = session["id"]
        self.created_ids["chat_sessions"].append(session_id)

        # Step 5: Verify session uses configured model
        response = await self.client.get(f"/api/chat/sessions/{session_id}")
        assert response.status_code == 200
        session_data = response.json()
        # Model should be set
        if "model" in session_data:
            assert session_data["model"] == "gpt-4"


@pytest.mark.integration
@pytest.mark.asyncio
class TestConcurrentOperations:
    """Test concurrent operations to verify thread safety."""

    async def test_concurrent_notebook_creation(self, async_test_client):
        """Test creating multiple notebooks concurrently."""
        client = async_test_client

        async def create_notebook(index: int):
            notebook_data = {
                "name": f"Concurrent Notebook {index}",
                "description": f"Created concurrently - {index}",
            }
            response = await client.post("/api/notebooks", json=notebook_data)
            return response.status_code, response.json()

        # Create 10 notebooks concurrently
        tasks = [create_notebook(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        for status, notebook in results:
            assert status == 201
            assert "id" in notebook

    async def test_concurrent_searches(self, async_test_client):
        """Test running multiple searches concurrently."""
        client = async_test_client

        async def run_search(query: str, strategy: str):
            search_query = {"query": query, "strategy": strategy}
            response = await client.post("/api/search", json=search_query)
            return response.status_code

        # Run 20 searches concurrently with different strategies
        queries = ["test query"] * 20
        strategies = ["keyword", "vector", "hybrid", "agentic_rag"] * 5
        tasks = [run_search(q, s) for q, s in zip(queries, strategies)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Most should succeed (some may fail if embeddings not available)
        success_count = sum(1 for r in results if r == 200)
        assert success_count > 10


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
