"""
Integration tests for API endpoints.

Tests cover:
- All notebook endpoints
- Source creation (all types)
- Database switching endpoint
- Error handling and validation
"""

import json
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient


@pytest.mark.api
class TestNotebooksAPI:
    """Test notebook API endpoints."""

    def test_create_notebook(self, test_client):
        """Test POST /api/notebooks - create notebook."""
        response = test_client.post(
            "/api/notebooks",
            json={
                "name": "Test Notebook",
                "description": "Test description",
                "archived": False
            }
        )

        assert response.status_code == 201
        data = response.json()

        assert "id" in data
        assert data["name"] == "Test Notebook"
        assert data["description"] == "Test description"
        assert data["archived"] == False

    def test_create_notebook_minimal(self, test_client):
        """Test creating notebook with minimal required fields."""
        response = test_client.post(
            "/api/notebooks",
            json={"name": "Minimal Notebook"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal Notebook"

    def test_create_notebook_validation_error(self, test_client):
        """Test validation error when name is missing."""
        response = test_client.post(
            "/api/notebooks",
            json={"description": "Missing name"}
        )

        assert response.status_code == 422

    def test_list_notebooks(self, test_client):
        """Test GET /api/notebooks - list all notebooks."""
        # Create test notebooks
        for i in range(3):
            test_client.post(
                "/api/notebooks",
                json={"name": f"Notebook {i}"}
            )

        response = test_client.get("/api/notebooks")

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) >= 3

    def test_list_notebooks_with_filter(self, test_client):
        """Test listing notebooks with archived filter."""
        # Create active and archived notebooks
        test_client.post("/api/notebooks", json={"name": "Active 1", "archived": False})
        test_client.post("/api/notebooks", json={"name": "Active 2", "archived": False})
        test_client.post("/api/notebooks", json={"name": "Archived 1", "archived": True})

        # Filter active only
        response = test_client.get("/api/notebooks?archived=false")

        assert response.status_code == 200
        data = response.json()

        assert all(nb["archived"] == False for nb in data)

    def test_get_notebook_by_id(self, test_client):
        """Test GET /api/notebooks/{id} - get single notebook."""
        # Create notebook
        create_response = test_client.post(
            "/api/notebooks",
            json={"name": "Test Notebook"}
        )
        notebook_id = create_response.json()["id"]

        # Get notebook
        response = test_client.get(f"/api/notebooks/{notebook_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == notebook_id
        assert data["name"] == "Test Notebook"

    def test_get_notebook_not_found(self, test_client):
        """Test 404 for non-existent notebook."""
        fake_id = str(uuid.uuid4())

        response = test_client.get(f"/api/notebooks/{fake_id}")

        assert response.status_code == 404

    def test_update_notebook(self, test_client):
        """Test PUT /api/notebooks/{id} - update notebook."""
        # Create notebook
        create_response = test_client.post(
            "/api/notebooks",
            json={"name": "Original Name", "description": "Original"}
        )
        notebook_id = create_response.json()["id"]

        # Update notebook
        response = test_client.put(
            f"/api/notebooks/{notebook_id}",
            json={
                "name": "Updated Name",
                "description": "Updated description",
                "archived": True
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "Updated Name"
        assert data["description"] == "Updated description"
        assert data["archived"] == True

    def test_update_partial_fields(self, test_client):
        """Test partial update of notebook."""
        # Create notebook
        create_response = test_client.post(
            "/api/notebooks",
            json={"name": "Test", "description": "Description", "archived": False}
        )
        notebook_id = create_response.json()["id"]

        # Update only name
        response = test_client.put(
            f"/api/notebooks/{notebook_id}",
            json={"name": "New Name"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "New Name"
        assert data["description"] == "Description"  # Unchanged
        assert data["archived"] == False  # Unchanged

    def test_delete_notebook(self, test_client):
        """Test DELETE /api/notebooks/{id} - delete notebook."""
        # Create notebook
        create_response = test_client.post(
            "/api/notebooks",
            json={"name": "To Delete"}
        )
        notebook_id = create_response.json()["id"]

        # Delete notebook
        response = test_client.delete(f"/api/notebooks/{notebook_id}")

        assert response.status_code == 204

        # Verify deletion
        get_response = test_client.get(f"/api/notebooks/{notebook_id}")
        assert get_response.status_code == 404

    def test_get_notebook_sources(self, test_client):
        """Test GET /api/notebooks/{id}/sources - list sources in notebook."""
        # Create notebook
        notebook_response = test_client.post(
            "/api/notebooks",
            json={"name": "Test Notebook"}
        )
        notebook_id = notebook_response.json()["id"]

        # Create and add sources
        for i in range(3):
            source_response = test_client.post(
                "/api/sources",
                json={
                    "title": f"Source {i}",
                    "source_type": "text",
                    "full_text": f"Content {i}"
                }
            )
            source_id = source_response.json()["id"]

            test_client.post(
                f"/api/notebooks/{notebook_id}/sources",
                json={"source_id": source_id}
            )

        # Get sources
        response = test_client.get(f"/api/notebooks/{notebook_id}/sources")

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 3

    def test_add_source_to_notebook(self, test_client):
        """Test POST /api/notebooks/{id}/sources - add source to notebook."""
        # Create notebook and source
        notebook_response = test_client.post(
            "/api/notebooks",
            json={"name": "Test Notebook"}
        )
        notebook_id = notebook_response.json()["id"]

        source_response = test_client.post(
            "/api/sources",
            json={
                "title": "Test Source",
                "source_type": "text",
                "full_text": "Content"
            }
        )
        source_id = source_response.json()["id"]

        # Add source to notebook
        response = test_client.post(
            f"/api/notebooks/{notebook_id}/sources",
            json={"source_id": source_id}
        )

        assert response.status_code == 201

    def test_remove_source_from_notebook(self, test_client):
        """Test DELETE /api/notebooks/{id}/sources/{source_id} - remove source."""
        # Create notebook and source
        notebook_response = test_client.post(
            "/api/notebooks",
            json={"name": "Test Notebook"}
        )
        notebook_id = notebook_response.json()["id"]

        source_response = test_client.post(
            "/api/sources",
            json={
                "title": "Test Source",
                "source_type": "text",
                "full_text": "Content"
            }
        )
        source_id = source_response.json()["id"]

        # Add source
        test_client.post(
            f"/api/notebooks/{notebook_id}/sources",
            json={"source_id": source_id}
        )

        # Remove source
        response = test_client.delete(
            f"/api/notebooks/{notebook_id}/sources/{source_id}"
        )

        assert response.status_code == 204

        # Verify removal
        sources_response = test_client.get(f"/api/notebooks/{notebook_id}/sources")
        assert len(sources_response.json()) == 0


@pytest.mark.api
class TestSourcesAPI:
    """Test source API endpoints for all source types."""

    def test_create_text_source(self, test_client):
        """Test creating a text source."""
        response = test_client.post(
            "/api/sources",
            json={
                "title": "Text Document",
                "source_type": "text",
                "full_text": "This is plain text content.",
                "topics": ["testing", "documentation"]
            }
        )

        assert response.status_code == 201
        data = response.json()

        assert data["source_type"] == "text"
        assert data["title"] == "Text Document"
        assert data["topics"] == ["testing", "documentation"]

    def test_create_url_source(self, test_client):
        """Test creating a URL source."""
        response = test_client.post(
            "/api/sources",
            json={
                "title": "Web Page",
                "source_type": "url",
                "full_text": "Scraped content",
                "asset_data": "https://example.com/article"
            }
        )

        assert response.status_code == 201
        data = response.json()

        assert data["source_type"] == "url"
        assert data["asset_data"] == "https://example.com/article"

    def test_create_youtube_source(self, test_client):
        """Test creating a YouTube source."""
        response = test_client.post(
            "/api/sources",
            json={
                "title": "YouTube Video",
                "source_type": "youtube",
                "full_text": "Video transcript",
                "asset_data": "https://youtube.com/watch?v=abc123"
            }
        )

        assert response.status_code == 201
        data = response.json()

        assert data["source_type"] == "youtube"

    def test_create_hana_table_source(self, test_client, sample_hana_table_source):
        """Test creating a HANA table source."""
        response = test_client.post(
            "/api/sources/hana-table",
            json=sample_hana_table_source
        )

        assert response.status_code == 201
        data = response.json()

        assert data["source_type"] == "hana_table"
        assert data["connection_config"]["table"] == "SALES_DATA"
        assert data["sync_config"]["frequency"] == "0 */6 * * *"

    def test_create_api_source(self, test_client, sample_api_source):
        """Test creating an API source."""
        response = test_client.post(
            "/api/sources/api",
            json=sample_api_source
        )

        assert response.status_code == 201
        data = response.json()

        assert data["source_type"] == "api"
        assert data["connection_config"]["endpoint"] is not None

    def test_list_sources(self, test_client):
        """Test GET /api/sources - list all sources."""
        # Create test sources
        for i in range(3):
            test_client.post(
                "/api/sources",
                json={
                    "title": f"Source {i}",
                    "source_type": "text",
                    "full_text": f"Content {i}"
                }
            )

        response = test_client.get("/api/sources")

        assert response.status_code == 200
        data = response.json()

        assert isinstance(data, list)
        assert len(data) >= 3

    def test_list_sources_by_type(self, test_client):
        """Test filtering sources by type."""
        # Create different types
        test_client.post("/api/sources", json={
            "title": "Text 1",
            "source_type": "text",
            "full_text": "Content"
        })

        test_client.post("/api/sources", json={
            "title": "URL 1",
            "source_type": "url",
            "full_text": "Content",
            "asset_data": "https://example.com"
        })

        # Filter by type
        response = test_client.get("/api/sources?source_type=text")

        assert response.status_code == 200
        data = response.json()

        assert all(s["source_type"] == "text" for s in data)

    def test_get_source_by_id(self, test_client):
        """Test GET /api/sources/{id} - get single source."""
        create_response = test_client.post(
            "/api/sources",
            json={
                "title": "Test Source",
                "source_type": "text",
                "full_text": "Content"
            }
        )
        source_id = create_response.json()["id"]

        response = test_client.get(f"/api/sources/{source_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == source_id

    def test_update_source(self, test_client):
        """Test PUT /api/sources/{id} - update source."""
        create_response = test_client.post(
            "/api/sources",
            json={
                "title": "Original",
                "source_type": "text",
                "full_text": "Original content"
            }
        )
        source_id = create_response.json()["id"]

        response = test_client.put(
            f"/api/sources/{source_id}",
            json={
                "title": "Updated",
                "full_text": "Updated content"
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["title"] == "Updated"
        assert data["full_text"] == "Updated content"

    def test_delete_source(self, test_client):
        """Test DELETE /api/sources/{id} - delete source."""
        create_response = test_client.post(
            "/api/sources",
            json={
                "title": "To Delete",
                "source_type": "text",
                "full_text": "Content"
            }
        )
        source_id = create_response.json()["id"]

        response = test_client.delete(f"/api/sources/{source_id}")

        assert response.status_code == 204

    def test_trigger_source_sync(self, test_client, sample_api_source):
        """Test POST /api/sources/{id}/sync - trigger manual sync."""
        create_response = test_client.post(
            "/api/sources/api",
            json=sample_api_source
        )
        source_id = create_response.json()["id"]

        response = test_client.post(f"/api/sources/{source_id}/sync")

        assert response.status_code == 202  # Accepted
        data = response.json()

        assert "status" in data
        assert data["status"] in ["scheduled", "syncing"]

    def test_file_upload_source(self, test_client, sample_pdf_file):
        """Test file upload for source creation."""
        with open(sample_pdf_file, "rb") as f:
            response = test_client.post(
                "/api/sources/upload",
                files={"file": ("test.pdf", f, "application/pdf")},
                data={"title": "Uploaded PDF"}
            )

        assert response.status_code == 201
        data = response.json()

        assert data["source_type"] == "file"
        assert data["asset_type"] == "pdf"


@pytest.mark.api
class TestDatabaseAPI:
    """Test database configuration and switching endpoints."""

    def test_get_database_config(self, test_client):
        """Test GET /api/database/config - get current database config."""
        response = test_client.get("/api/database/config")

        assert response.status_code == 200
        data = response.json()

        assert "database_type" in data
        assert data["database_type"] in ["sqlite", "hana"]

    def test_get_database_status(self, test_client):
        """Test GET /api/database/status - get connection status."""
        response = test_client.get("/api/database/status")

        assert response.status_code == 200
        data = response.json()

        assert "connected" in data
        assert "database_type" in data

    def test_test_hana_connection(self, test_client):
        """Test POST /api/database/test-connection - test HANA connection."""
        response = test_client.post(
            "/api/database/test-connection",
            json={
                "database_type": "hana",
                "hana_host": "test.hanacloud.ondemand.com",
                "hana_port": 443,
                "hana_user": "test_user",
                "hana_password": "test_password",
                "hana_database": "test_db"
            }
        )

        # May fail if credentials invalid, but should return proper response
        assert response.status_code in [200, 422, 502]

        if response.status_code == 200:
            data = response.json()
            assert "success" in data

    def test_update_database_config(self, test_client):
        """Test PUT /api/database/config - update database configuration."""
        response = test_client.put(
            "/api/database/config",
            json={
                "database_type": "sqlite",
                "sqlite_path": "/tmp/test.db"
            }
        )

        assert response.status_code == 200

    def test_switch_database(self, test_client):
        """Test POST /api/database/switch - switch between databases."""
        response = test_client.post(
            "/api/database/switch",
            json={"target_type": "sqlite"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["database_type"] == "sqlite"
        assert "message" in data


@pytest.mark.api
class TestSearchAPI:
    """Test search API endpoints."""

    def test_keyword_search(self, test_client):
        """Test POST /api/search - keyword search."""
        # Create test sources
        test_client.post("/api/sources", json={
            "title": "Machine Learning Basics",
            "source_type": "text",
            "full_text": "Introduction to machine learning algorithms"
        })

        test_client.post("/api/sources", json={
            "title": "Neural Networks",
            "source_type": "text",
            "full_text": "Deep learning with neural networks"
        })

        # Search
        response = test_client.post(
            "/api/search",
            json={
                "query": "machine learning",
                "strategy": "keyword",
                "limit": 10
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert "results" in data
        assert "strategy" in data
        assert data["strategy"] == "keyword"

    def test_vector_search(self, test_client, mock_embedding_model):
        """Test POST /api/search - vector search."""
        # Mock embedding model
        with pytest.mock.patch("open_notebook.ai.embeddings.get_embedding_model") as mock:
            mock.return_value = mock_embedding_model

            response = test_client.post(
                "/api/search",
                json={
                    "query": "artificial intelligence",
                    "strategy": "vector",
                    "limit": 5
                }
            )

        assert response.status_code == 200
        data = response.json()

        assert data["strategy"] == "vector"

    def test_hybrid_search(self, test_client):
        """Test POST /api/search - hybrid search."""
        response = test_client.post(
            "/api/search",
            json={
                "query": "test query",
                "strategy": "hybrid",
                "limit": 10
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["strategy"] == "hybrid"

    def test_search_with_filters(self, test_client):
        """Test search with filters."""
        # Create notebook
        notebook_response = test_client.post(
            "/api/notebooks",
            json={"name": "Test Notebook"}
        )
        notebook_id = notebook_response.json()["id"]

        # Search with notebook filter
        response = test_client.post(
            "/api/search",
            json={
                "query": "test",
                "strategy": "keyword",
                "filters": {
                    "notebook_id": notebook_id
                }
            }
        )

        assert response.status_code == 200


@pytest.mark.api
class TestErrorHandling:
    """Test API error handling."""

    def test_invalid_json(self, test_client):
        """Test handling of invalid JSON."""
        response = test_client.post(
            "/api/notebooks",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    def test_missing_required_field(self, test_client):
        """Test validation error for missing required field."""
        response = test_client.post(
            "/api/sources",
            json={
                "source_type": "text"
                # Missing title and full_text
            }
        )

        assert response.status_code == 422

    def test_invalid_uuid(self, test_client):
        """Test error for invalid UUID format."""
        response = test_client.get("/api/notebooks/invalid-uuid")

        assert response.status_code in [400, 422]

    def test_database_error_handling(self, test_client):
        """Test handling of database errors."""
        # Try to add source to non-existent notebook
        response = test_client.post(
            f"/api/notebooks/{uuid.uuid4()}/sources",
            json={"source_id": str(uuid.uuid4())}
        )

        assert response.status_code == 404

    def test_concurrent_requests(self, test_client):
        """Test handling of concurrent API requests."""
        import concurrent.futures

        def create_notebook(i):
            return test_client.post(
                "/api/notebooks",
                json={"name": f"Concurrent {i}"}
            )

        # Execute 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_notebook, i) for i in range(10)]
            results = [f.result() for f in futures]

        # All should succeed
        assert all(r.status_code == 201 for r in results)

        # All should have unique IDs
        ids = [r.json()["id"] for r in results]
        assert len(set(ids)) == 10


@pytest.mark.api
@pytest.mark.asyncio
class TestAsyncEndpoints:
    """Test async endpoint behavior."""

    async def test_async_notebook_creation(self, async_test_client):
        """Test async notebook creation."""
        response = await async_test_client.post(
            "/api/notebooks",
            json={"name": "Async Notebook"}
        )

        assert response.status_code == 201

    async def test_async_concurrent_requests(self, async_test_client):
        """Test async concurrent requests."""
        import asyncio

        async def create_notebook(i):
            return await async_test_client.post(
                "/api/notebooks",
                json={"name": f"Async {i}"}
            )

        # Create 20 notebooks concurrently
        results = await asyncio.gather(
            *[create_notebook(i) for i in range(20)]
        )

        assert all(r.status_code == 201 for r in results)
