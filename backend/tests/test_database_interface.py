"""
Unit tests for database abstraction interface and SQLite implementation.

Tests cover:
- Abstract interface contract
- SQLite implementation (all methods)
- Connection pooling
- Transaction support
- Error handling
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import List

import pytest
import numpy as np

from open_notebook.database.interface import DatabaseInterface
from open_notebook.database.sqlite_impl import SQLiteDatabase
from open_notebook.database.models import ConnectionConfig, QueryResult, TransactionContext


class TestDatabaseInterface:
    """Test abstract database interface contract."""

    def test_interface_is_abstract(self):
        """DatabaseInterface should not be instantiable."""
        with pytest.raises(TypeError):
            DatabaseInterface()

    def test_interface_defines_required_methods(self):
        """Interface should define all required abstract methods."""
        required_methods = [
            'connect',
            'disconnect',
            'query',
            'create',
            'update',
            'delete',
            'upsert',
            'vector_search',
            'execute',
            'begin_transaction',
        ]

        for method in required_methods:
            assert hasattr(DatabaseInterface, method), f"Missing method: {method}"


@pytest.mark.asyncio
class TestSQLiteDatabase:
    """Test SQLite database implementation."""

    async def test_connection_lifecycle(self, sqlite_db):
        """Test database connection and disconnection."""
        assert sqlite_db.is_connected()

        await sqlite_db.disconnect()
        assert not sqlite_db.is_connected()

        # Reconnect
        await sqlite_db.connect()
        assert sqlite_db.is_connected()

    async def test_create_record(self, sqlite_db):
        """Test creating a new record."""
        data = {
            "name": "My Research Notebook",
            "description": "Testing notebook creation",
            "archived": False
        }

        record_id = await sqlite_db.create("notebooks", data)

        assert record_id is not None
        assert len(record_id) == 36  # UUID format

        # Verify record was created
        results = await sqlite_db.query(
            "SELECT * FROM notebooks WHERE id = ?",
            [record_id]
        )

        assert len(results) == 1
        assert results[0]["name"] == data["name"]
        assert results[0]["description"] == data["description"]

    async def test_create_with_id(self, sqlite_db):
        """Test creating a record with specified ID."""
        notebook_id = str(uuid.uuid4())
        data = {
            "id": notebook_id,
            "name": "Test Notebook",
            "description": "Test",
            "archived": False
        }

        record_id = await sqlite_db.create("notebooks", data)
        assert record_id == notebook_id

    async def test_query_with_parameters(self, sqlite_db):
        """Test parameterized queries."""
        # Create test data
        await sqlite_db.create("notebooks", {
            "name": "Notebook 1",
            "archived": False
        })
        await sqlite_db.create("notebooks", {
            "name": "Notebook 2",
            "archived": True
        })
        await sqlite_db.create("notebooks", {
            "name": "Notebook 3",
            "archived": False
        })

        # Query with parameter
        results = await sqlite_db.query(
            "SELECT * FROM notebooks WHERE archived = ?",
            [False]
        )

        assert len(results) == 2
        assert all(r["archived"] == False for r in results)

    async def test_query_multiple_parameters(self, sqlite_db):
        """Test query with multiple parameters."""
        # Create test data
        await sqlite_db.create("sources", {
            "title": "Document 1",
            "source_type": "text",
            "full_text": "Content 1"
        })
        await sqlite_db.create("sources", {
            "title": "Document 2",
            "source_type": "file",
            "full_text": "Content 2"
        })

        # Query with multiple parameters
        results = await sqlite_db.query(
            "SELECT * FROM sources WHERE source_type = ? AND title LIKE ?",
            ["text", "Document%"]
        )

        assert len(results) == 1
        assert results[0]["title"] == "Document 1"

    async def test_update_record(self, sqlite_db):
        """Test updating an existing record."""
        # Create record
        record_id = await sqlite_db.create("notebooks", {
            "name": "Original Name",
            "description": "Original description",
            "archived": False
        })

        # Update record
        await sqlite_db.update("notebooks", record_id, {
            "name": "Updated Name",
            "description": "Updated description"
        })

        # Verify update
        results = await sqlite_db.query(
            "SELECT * FROM notebooks WHERE id = ?",
            [record_id]
        )

        assert results[0]["name"] == "Updated Name"
        assert results[0]["description"] == "Updated description"
        assert results[0]["archived"] == False  # Unchanged field

    async def test_update_nonexistent_record(self, sqlite_db):
        """Test updating a record that doesn't exist."""
        fake_id = str(uuid.uuid4())

        with pytest.raises(Exception):  # Should raise error
            await sqlite_db.update("notebooks", fake_id, {
                "name": "Updated Name"
            })

    async def test_delete_record(self, sqlite_db):
        """Test deleting a record."""
        # Create record
        record_id = await sqlite_db.create("notebooks", {
            "name": "To Be Deleted",
            "archived": False
        })

        # Verify it exists
        results = await sqlite_db.query(
            "SELECT * FROM notebooks WHERE id = ?",
            [record_id]
        )
        assert len(results) == 1

        # Delete record
        await sqlite_db.delete("notebooks", record_id)

        # Verify deletion
        results = await sqlite_db.query(
            "SELECT * FROM notebooks WHERE id = ?",
            [record_id]
        )
        assert len(results) == 0

    async def test_delete_cascade(self, sqlite_db):
        """Test cascade delete with foreign key relationships."""
        # Create notebook
        notebook_id = await sqlite_db.create("notebooks", {
            "name": "Parent Notebook",
            "archived": False
        })

        # Create source
        source_id = await sqlite_db.create("sources", {
            "title": "Child Source",
            "source_type": "text",
            "full_text": "Content"
        })

        # Link them
        await sqlite_db.execute(
            "INSERT INTO notebook_source (notebook_id, source_id) VALUES (?, ?)",
            [notebook_id, source_id]
        )

        # Verify link exists
        links = await sqlite_db.query(
            "SELECT * FROM notebook_source WHERE notebook_id = ?",
            [notebook_id]
        )
        assert len(links) == 1

        # Delete notebook
        await sqlite_db.delete("notebooks", notebook_id)

        # Verify cascade delete removed link
        links = await sqlite_db.query(
            "SELECT * FROM notebook_source WHERE notebook_id = ?",
            [notebook_id]
        )
        assert len(links) == 0

    async def test_upsert_insert(self, sqlite_db):
        """Test upsert when record doesn't exist (insert)."""
        record_id = str(uuid.uuid4())

        await sqlite_db.upsert("notebooks", record_id, {
            "id": record_id,
            "name": "New Notebook",
            "archived": False
        })

        # Verify inserted
        results = await sqlite_db.query(
            "SELECT * FROM notebooks WHERE id = ?",
            [record_id]
        )
        assert len(results) == 1
        assert results[0]["name"] == "New Notebook"

    async def test_upsert_update(self, sqlite_db):
        """Test upsert when record exists (update)."""
        # Create initial record
        record_id = await sqlite_db.create("notebooks", {
            "name": "Original",
            "archived": False
        })

        # Upsert with same ID
        await sqlite_db.upsert("notebooks", record_id, {
            "id": record_id,
            "name": "Updated via Upsert",
            "archived": True
        })

        # Verify updated
        results = await sqlite_db.query(
            "SELECT * FROM notebooks WHERE id = ?",
            [record_id]
        )
        assert len(results) == 1
        assert results[0]["name"] == "Updated via Upsert"
        assert results[0]["archived"] == True

    async def test_vector_search_cosine_similarity(self, sqlite_db, sample_embeddings):
        """Test vector search using cosine similarity."""
        # Create source with embeddings
        source_id = await sqlite_db.create("sources", {
            "title": "Test Document",
            "source_type": "text",
            "full_text": "Sample content for vector search"
        })

        # Add embeddings
        for i, embedding in enumerate(sample_embeddings):
            embedding_blob = embedding.tobytes()
            await sqlite_db.create("source_embeddings", {
                "source_id": source_id,
                "order_num": i,
                "content": f"Chunk {i}",
                "embedding": embedding_blob
            })

        # Search with query embedding (similar to first embedding)
        query_embedding = sample_embeddings[0] + np.random.randn(1536) * 0.1
        query_embedding = query_embedding / np.linalg.norm(query_embedding)

        results = await sqlite_db.vector_search(
            embedding=query_embedding.tolist(),
            limit=3,
            threshold=0.5
        )

        assert len(results) > 0
        assert len(results) <= 3
        assert all("similarity" in r for r in results)
        assert all("content" in r for r in results)

        # Results should be ordered by similarity (descending)
        similarities = [r["similarity"] for r in results]
        assert similarities == sorted(similarities, reverse=True)

    async def test_vector_search_with_threshold(self, sqlite_db, sample_embeddings):
        """Test vector search with similarity threshold."""
        source_id = await sqlite_db.create("sources", {
            "title": "Test Document",
            "source_type": "text",
            "full_text": "Sample content"
        })

        # Add one embedding
        await sqlite_db.create("source_embeddings", {
            "source_id": source_id,
            "order_num": 0,
            "content": "Test chunk",
            "embedding": sample_embeddings[0].tobytes()
        })

        # Search with very dissimilar embedding
        dissimilar_embedding = -sample_embeddings[0]  # Opposite direction
        dissimilar_embedding = dissimilar_embedding / np.linalg.norm(dissimilar_embedding)

        results = await sqlite_db.vector_search(
            embedding=dissimilar_embedding.tolist(),
            limit=10,
            threshold=0.9  # High threshold
        )

        # Should return no results due to low similarity
        assert len(results) == 0

    async def test_transaction_commit(self, sqlite_db):
        """Test transaction commit."""
        async with sqlite_db.begin_transaction() as tx:
            # Create records within transaction
            await sqlite_db.create("notebooks", {
                "name": "Transactional Notebook 1",
                "archived": False
            })
            await sqlite_db.create("notebooks", {
                "name": "Transactional Notebook 2",
                "archived": False
            })
            # Transaction commits on exit

        # Verify records were committed
        results = await sqlite_db.query(
            "SELECT * FROM notebooks WHERE name LIKE ?",
            ["Transactional%"]
        )
        assert len(results) == 2

    async def test_transaction_rollback(self, sqlite_db):
        """Test transaction rollback on error."""
        try:
            async with sqlite_db.begin_transaction() as tx:
                # Create a record
                await sqlite_db.create("notebooks", {
                    "name": "Should Be Rolled Back",
                    "archived": False
                })

                # Raise an error to trigger rollback
                raise Exception("Intentional error for rollback test")

        except Exception:
            pass  # Expected

        # Verify record was not committed
        results = await sqlite_db.query(
            "SELECT * FROM notebooks WHERE name = ?",
            ["Should Be Rolled Back"]
        )
        assert len(results) == 0

    async def test_concurrent_queries(self, sqlite_db):
        """Test handling concurrent queries with connection pooling."""
        # Create test data
        for i in range(10):
            await sqlite_db.create("notebooks", {
                "name": f"Notebook {i}",
                "archived": False
            })

        # Execute multiple queries concurrently
        async def query_notebooks():
            return await sqlite_db.query(
                "SELECT * FROM notebooks WHERE archived = ?",
                [False]
            )

        tasks = [query_notebooks() for _ in range(10)]
        results_list = await asyncio.gather(*tasks)

        # All queries should return the same results
        assert all(len(results) == 10 for results in results_list)

    async def test_json_field_storage(self, sqlite_db):
        """Test storing and retrieving JSON fields."""
        topics = ["machine learning", "neural networks", "AI"]
        connection_config = {
            "host": "example.com",
            "port": 443,
            "credentials": "encrypted"
        }

        source_id = await sqlite_db.create("sources", {
            "title": "Test Source",
            "source_type": "api",
            "full_text": "Content",
            "topics": json.dumps(topics),
            "connection_config": json.dumps(connection_config)
        })

        # Retrieve and verify
        results = await sqlite_db.query(
            "SELECT * FROM sources WHERE id = ?",
            [source_id]
        )

        assert len(results) == 1
        assert json.loads(results[0]["topics"]) == topics
        assert json.loads(results[0]["connection_config"]) == connection_config

    async def test_timestamp_handling(self, sqlite_db):
        """Test automatic timestamp creation and updates."""
        # Create record
        record_id = await sqlite_db.create("notebooks", {
            "name": "Timestamp Test",
            "archived": False
        })

        # Get initial timestamps
        results = await sqlite_db.query(
            "SELECT created, updated FROM notebooks WHERE id = ?",
            [record_id]
        )
        initial_created = results[0]["created"]
        initial_updated = results[0]["updated"]

        assert initial_created is not None
        assert initial_updated is not None

        # Wait a moment and update
        await asyncio.sleep(0.1)

        await sqlite_db.update("notebooks", record_id, {
            "name": "Updated Name"
        })

        # Get new timestamps
        results = await sqlite_db.query(
            "SELECT created, updated FROM notebooks WHERE id = ?",
            [record_id]
        )
        new_created = results[0]["created"]
        new_updated = results[0]["updated"]

        # Created should not change, updated should change
        assert new_created == initial_created
        assert new_updated > initial_updated

    async def test_null_handling(self, sqlite_db):
        """Test handling of NULL values."""
        record_id = await sqlite_db.create("notebooks", {
            "name": "Null Test",
            "description": None,  # Explicitly NULL
            "archived": False,
            "folder_id": None
        })

        results = await sqlite_db.query(
            "SELECT * FROM notebooks WHERE id = ?",
            [record_id]
        )

        assert results[0]["description"] is None
        assert results[0]["folder_id"] is None

    async def test_error_handling_invalid_table(self, sqlite_db):
        """Test error handling for invalid table name."""
        with pytest.raises(Exception):
            await sqlite_db.create("nonexistent_table", {
                "field": "value"
            })

    async def test_error_handling_invalid_column(self, sqlite_db):
        """Test error handling for invalid column name."""
        with pytest.raises(Exception):
            await sqlite_db.create("notebooks", {
                "name": "Test",
                "nonexistent_column": "value"
            })

    async def test_sql_injection_prevention(self, sqlite_db):
        """Test SQL injection prevention via parameterized queries."""
        # Create test data
        await sqlite_db.create("notebooks", {
            "name": "Legitimate Notebook",
            "archived": False
        })

        # Attempt SQL injection
        malicious_input = "' OR '1'='1"

        results = await sqlite_db.query(
            "SELECT * FROM notebooks WHERE name = ?",
            [malicious_input]
        )

        # Should return no results (not all records)
        assert len(results) == 0

    async def test_batch_insert(self, sqlite_db):
        """Test batch insertion of multiple records."""
        records = [
            {"name": f"Batch Notebook {i}", "archived": False}
            for i in range(100)
        ]

        # Insert all records
        record_ids = []
        for record in records:
            record_id = await sqlite_db.create("notebooks", record)
            record_ids.append(record_id)

        # Verify all inserted
        results = await sqlite_db.query(
            "SELECT * FROM notebooks WHERE name LIKE ?",
            ["Batch Notebook%"]
        )

        assert len(results) == 100
        assert len(record_ids) == 100
        assert len(set(record_ids)) == 100  # All unique


@pytest.mark.asyncio
class TestConnectionPooling:
    """Test connection pooling behavior."""

    async def test_connection_reuse(self, sqlite_db):
        """Test that connections are reused from pool."""
        # Execute multiple queries
        for i in range(10):
            await sqlite_db.query("SELECT 1", [])

        # Connection should still be alive
        assert sqlite_db.is_connected()

    async def test_connection_pool_size(self):
        """Test connection pool configuration."""
        from open_notebook.database.models import ConnectionConfig
        from open_notebook.database.sqlite_impl import SQLiteDatabase
        import tempfile

        config = ConnectionConfig(
            database_type="sqlite",
            sqlite_path=tempfile.mktemp(suffix=".db"),
            pool_size=5,
            max_overflow=10
        )

        db = SQLiteDatabase(config)
        await db.connect()

        # Should be able to handle concurrent connections
        async def concurrent_query():
            return await db.query("SELECT 1", [])

        tasks = [concurrent_query() for _ in range(20)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 20

        await db.disconnect()
