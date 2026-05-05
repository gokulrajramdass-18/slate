"""
Unit tests for HANA database implementation.

Tests cover:
- HANA connection (using .env credentials)
- HANA-specific methods
- Vector search with COSINE_SIMILARITY
- Native text search
- Skip if HANA not available (pytest.mark.skipif)
"""

import json
import uuid
from datetime import datetime

import pytest
import numpy as np

from open_notebook.database.hana_impl import HANADatabase
from open_notebook.database.models import ConnectionConfig


@pytest.mark.hana
@pytest.mark.asyncio
class TestHANAConnection:
    """Test HANA database connection."""

    async def test_hana_connect(self, hana_db):
        """Test connecting to HANA database."""
        assert hana_db.is_connected()
        assert hana_db.connection is not None

    async def test_hana_connection_params(self, hana_db_config):
        """Test HANA connection with SSL encryption."""
        db = HANADatabase(hana_db_config)

        # Should connect with SSL enabled
        await db.connect()
        assert db.is_connected()

        await db.disconnect()
        assert not db.is_connected()

    async def test_hana_connection_error_handling(self):
        """Test error handling for invalid HANA credentials."""
        config = ConnectionConfig(
            database_type="hana",
            hana_host="invalid.host.com",
            hana_port=443,
            hana_user="invalid_user",
            hana_password="invalid_password",
            hana_database="invalid_db",
            hana_encrypt=True
        )

        db = HANADatabase(config)

        with pytest.raises(Exception):  # Connection should fail
            await db.connect()

    async def test_hana_connection_pool(self, hana_db):
        """Test HANA connection pooling."""
        # Execute multiple queries to test pooling
        for i in range(10):
            result = await hana_db.query("SELECT 1 FROM DUMMY", [])
            assert len(result) == 1

        # Connection should still be active
        assert hana_db.is_connected()


@pytest.mark.hana
@pytest.mark.asyncio
class TestHANAOperations:
    """Test HANA-specific CRUD operations."""

    async def test_hana_create_table(self, hana_db):
        """Test creating tables in HANA."""
        table_name = f"test_notebooks_{uuid.uuid4().hex[:8]}"

        # Create test table
        await hana_db.execute(f"""
            CREATE COLUMN TABLE {table_name} (
                id VARCHAR(36) PRIMARY KEY,
                name NVARCHAR(255) NOT NULL,
                description NCLOB,
                archived BOOLEAN DEFAULT FALSE,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """, [])

        # Verify table exists
        result = await hana_db.query(f"""
            SELECT TABLE_NAME FROM TABLES
            WHERE SCHEMA_NAME = CURRENT_SCHEMA
            AND TABLE_NAME = ?
        """, [table_name])

        assert len(result) == 1

        # Cleanup
        await hana_db.execute(f"DROP TABLE {table_name}", [])

    async def test_hana_create_record(self, hana_db):
        """Test creating a record in HANA."""
        table_name = f"test_notebooks_{uuid.uuid4().hex[:8]}"

        # Create test table
        await hana_db.execute(f"""
            CREATE COLUMN TABLE {table_name} (
                id VARCHAR(36) PRIMARY KEY,
                name NVARCHAR(255) NOT NULL,
                archived BOOLEAN DEFAULT FALSE
            )
        """, [])

        # Create record
        record_id = await hana_db.create(table_name, {
            "name": "Test HANA Notebook",
            "archived": False
        })

        assert record_id is not None
        assert len(record_id) == 36

        # Verify record
        results = await hana_db.query(
            f"SELECT * FROM {table_name} WHERE id = ?",
            [record_id]
        )

        assert len(results) == 1
        assert results[0]["NAME"] == "Test HANA Notebook"  # HANA returns uppercase column names

        # Cleanup
        await hana_db.execute(f"DROP TABLE {table_name}", [])

    async def test_hana_nclob_storage(self, hana_db):
        """Test storing large text in NCLOB fields."""
        table_name = f"test_sources_{uuid.uuid4().hex[:8]}"

        # Create test table with NCLOB
        await hana_db.execute(f"""
            CREATE COLUMN TABLE {table_name} (
                id VARCHAR(36) PRIMARY KEY,
                title NVARCHAR(500),
                full_text NCLOB
            )
        """, [])

        # Create record with large text
        large_text = "A" * 100000  # 100K characters

        record_id = await hana_db.create(table_name, {
            "title": "Large Document",
            "full_text": large_text
        })

        # Verify storage
        results = await hana_db.query(
            f"SELECT full_text FROM {table_name} WHERE id = ?",
            [record_id]
        )

        assert len(results[0]["FULL_TEXT"]) == 100000

        # Cleanup
        await hana_db.execute(f"DROP TABLE {table_name}", [])


@pytest.mark.hana
@pytest.mark.asyncio
class TestHANAVectorSearch:
    """Test HANA native vector search with COSINE_SIMILARITY."""

    async def test_hana_vector_column_creation(self, hana_db):
        """Test creating table with REAL_VECTOR column."""
        table_name = f"test_embeddings_{uuid.uuid4().hex[:8]}"

        # Create table with vector column
        await hana_db.execute(f"""
            CREATE COLUMN TABLE {table_name} (
                id VARCHAR(36) PRIMARY KEY,
                content NVARCHAR(5000),
                embedding REAL_VECTOR(1536)
            )
        """, [])

        # Verify table structure
        result = await hana_db.query(f"""
            SELECT COLUMN_NAME, DATA_TYPE_NAME
            FROM TABLE_COLUMNS
            WHERE SCHEMA_NAME = CURRENT_SCHEMA
            AND TABLE_NAME = ?
            AND COLUMN_NAME = 'EMBEDDING'
        """, [table_name])

        assert len(result) == 1
        assert result[0]["DATA_TYPE_NAME"] == "REAL_VECTOR"

        # Cleanup
        await hana_db.execute(f"DROP TABLE {table_name}", [])

    async def test_hana_vector_index_creation(self, hana_db):
        """Test creating vector index on embedding column."""
        table_name = f"test_embeddings_{uuid.uuid4().hex[:8]}"
        index_name = f"idx_{table_name}_vec"

        # Create table with vector column
        await hana_db.execute(f"""
            CREATE COLUMN TABLE {table_name} (
                id VARCHAR(36) PRIMARY KEY,
                content NVARCHAR(5000),
                embedding REAL_VECTOR(1536)
            )
        """, [])

        # Create vector index
        await hana_db.execute(f"""
            CREATE VECTOR INDEX {index_name}
            ON {table_name}(embedding)
        """, [])

        # Verify index exists
        result = await hana_db.query(f"""
            SELECT INDEX_NAME FROM INDEXES
            WHERE SCHEMA_NAME = CURRENT_SCHEMA
            AND TABLE_NAME = ?
            AND INDEX_NAME = ?
        """, [table_name, index_name])

        assert len(result) == 1

        # Cleanup
        await hana_db.execute(f"DROP TABLE {table_name} CASCADE", [])

    async def test_hana_vector_insert_and_search(self, hana_db, sample_embeddings):
        """Test inserting vectors and searching with COSINE_SIMILARITY."""
        table_name = f"test_embeddings_{uuid.uuid4().hex[:8]}"

        # Create table with vector column
        await hana_db.execute(f"""
            CREATE COLUMN TABLE {table_name} (
                id VARCHAR(36) PRIMARY KEY,
                content NVARCHAR(5000),
                embedding REAL_VECTOR(1536)
            )
        """, [])

        # Insert embeddings
        record_ids = []
        for i, embedding in enumerate(sample_embeddings):
            # Convert numpy array to list for HANA
            embedding_list = embedding.tolist()

            record_id = str(uuid.uuid4())
            await hana_db.execute(f"""
                INSERT INTO {table_name} (id, content, embedding)
                VALUES (?, ?, TO_REAL_VECTOR(?))
            """, [record_id, f"Chunk {i}", str(embedding_list)])

            record_ids.append(record_id)

        # Search with query embedding
        query_embedding = sample_embeddings[0] + np.random.randn(1536) * 0.1
        query_embedding = query_embedding / np.linalg.norm(query_embedding)
        query_embedding_list = query_embedding.tolist()

        # Use native COSINE_SIMILARITY function
        results = await hana_db.query(f"""
            SELECT
                id,
                content,
                COSINE_SIMILARITY(embedding, TO_REAL_VECTOR(?)) AS similarity
            FROM {table_name}
            ORDER BY similarity DESC
            LIMIT 3
        """, [str(query_embedding_list)])

        assert len(results) > 0
        assert len(results) <= 3

        # Results should be ordered by similarity (descending)
        similarities = [r["SIMILARITY"] for r in results]
        assert similarities == sorted(similarities, reverse=True)

        # All similarities should be between -1 and 1
        assert all(-1 <= s <= 1 for s in similarities)

        # Cleanup
        await hana_db.execute(f"DROP TABLE {table_name}", [])

    async def test_hana_vector_search_with_filter(self, hana_db, sample_embeddings):
        """Test vector search with additional filters."""
        table_name = f"test_embeddings_{uuid.uuid4().hex[:8]}"

        # Create table with additional metadata
        await hana_db.execute(f"""
            CREATE COLUMN TABLE {table_name} (
                id VARCHAR(36) PRIMARY KEY,
                source_id VARCHAR(36),
                content NVARCHAR(5000),
                embedding REAL_VECTOR(1536)
            )
        """, [])

        # Insert embeddings with different source_ids
        source_id_1 = str(uuid.uuid4())
        source_id_2 = str(uuid.uuid4())

        for i, embedding in enumerate(sample_embeddings[:3]):
            await hana_db.execute(f"""
                INSERT INTO {table_name} (id, source_id, content, embedding)
                VALUES (?, ?, ?, TO_REAL_VECTOR(?))
            """, [str(uuid.uuid4()), source_id_1, f"Chunk {i}", str(embedding.tolist())])

        for i, embedding in enumerate(sample_embeddings[3:]):
            await hana_db.execute(f"""
                INSERT INTO {table_name} (id, source_id, content, embedding)
                VALUES (?, ?, ?, TO_REAL_VECTOR(?))
            """, [str(uuid.uuid4()), source_id_2, f"Chunk {i+3}", str(embedding.tolist())])

        # Search with filter
        query_embedding = sample_embeddings[0]
        query_embedding_list = query_embedding.tolist()

        results = await hana_db.query(f"""
            SELECT
                id,
                content,
                COSINE_SIMILARITY(embedding, TO_REAL_VECTOR(?)) AS similarity
            FROM {table_name}
            WHERE source_id = ?
            ORDER BY similarity DESC
            LIMIT 5
        """, [str(query_embedding_list), source_id_1])

        assert len(results) == 3  # Only 3 records with source_id_1

        # Cleanup
        await hana_db.execute(f"DROP TABLE {table_name}", [])

    async def test_hana_vector_search_threshold(self, hana_db, sample_embeddings):
        """Test vector search with similarity threshold."""
        table_name = f"test_embeddings_{uuid.uuid4().hex[:8]}"

        # Create table
        await hana_db.execute(f"""
            CREATE COLUMN TABLE {table_name} (
                id VARCHAR(36) PRIMARY KEY,
                content NVARCHAR(5000),
                embedding REAL_VECTOR(1536)
            )
        """, [])

        # Insert one embedding
        await hana_db.execute(f"""
            INSERT INTO {table_name} (id, content, embedding)
            VALUES (?, ?, TO_REAL_VECTOR(?))
        """, [str(uuid.uuid4()), "Test content", str(sample_embeddings[0].tolist())])

        # Search with very dissimilar embedding
        dissimilar_embedding = -sample_embeddings[0]  # Opposite direction
        dissimilar_embedding = dissimilar_embedding / np.linalg.norm(dissimilar_embedding)

        results = await hana_db.query(f"""
            SELECT
                id,
                content,
                COSINE_SIMILARITY(embedding, TO_REAL_VECTOR(?)) AS similarity
            FROM {table_name}
            WHERE COSINE_SIMILARITY(embedding, TO_REAL_VECTOR(?)) >= ?
            ORDER BY similarity DESC
        """, [str(dissimilar_embedding.tolist()), str(dissimilar_embedding.tolist()), 0.9])

        # Should return no results due to low similarity
        assert len(results) == 0

        # Cleanup
        await hana_db.execute(f"DROP TABLE {table_name}", [])


@pytest.mark.hana
@pytest.mark.asyncio
class TestHANATextSearch:
    """Test HANA native full-text search."""

    async def test_hana_fulltext_index_creation(self, hana_db):
        """Test creating full-text index in HANA."""
        table_name = f"test_sources_{uuid.uuid4().hex[:8]}"

        # Create table
        await hana_db.execute(f"""
            CREATE COLUMN TABLE {table_name} (
                id VARCHAR(36) PRIMARY KEY,
                title NVARCHAR(500),
                full_text NCLOB
            )
        """, [])

        # Create full-text index
        await hana_db.execute(f"""
            CREATE FULLTEXT INDEX fts_{table_name}
            ON {table_name}(title, full_text)
        """, [])

        # Verify index exists
        result = await hana_db.query(f"""
            SELECT INDEX_NAME FROM FULLTEXT_INDEXES
            WHERE SCHEMA_NAME = CURRENT_SCHEMA
            AND TABLE_NAME = ?
        """, [table_name])

        assert len(result) == 1

        # Cleanup
        await hana_db.execute(f"DROP TABLE {table_name} CASCADE", [])

    async def test_hana_contains_search(self, hana_db):
        """Test CONTAINS function for full-text search."""
        table_name = f"test_sources_{uuid.uuid4().hex[:8]}"

        # Create table with full-text index
        await hana_db.execute(f"""
            CREATE COLUMN TABLE {table_name} (
                id VARCHAR(36) PRIMARY KEY,
                title NVARCHAR(500),
                full_text NCLOB
            )
        """, [])

        await hana_db.execute(f"""
            CREATE FULLTEXT INDEX fts_{table_name}
            ON {table_name}(title, full_text)
        """, [])

        # Insert test data
        await hana_db.execute(f"""
            INSERT INTO {table_name} (id, title, full_text)
            VALUES (?, ?, ?)
        """, [str(uuid.uuid4()), "Machine Learning Basics",
               "Machine learning is a subset of artificial intelligence..."])

        await hana_db.execute(f"""
            INSERT INTO {table_name} (id, title, full_text)
            VALUES (?, ?, ?)
        """, [str(uuid.uuid4()), "Neural Networks",
               "Neural networks are computing systems inspired by biological neural networks..."])

        await hana_db.execute(f"""
            INSERT INTO {table_name} (id, title, full_text)
            VALUES (?, ?, ?)
        """, [str(uuid.uuid4()), "Deep Learning",
               "Deep learning is part of machine learning methods based on artificial neural networks..."])

        # Search using CONTAINS
        results = await hana_db.query(f"""
            SELECT title, SCORE() as relevance
            FROM {table_name}
            WHERE CONTAINS((title, full_text), 'machine learning')
            ORDER BY relevance DESC
        """, [])

        assert len(results) >= 2
        # Results should include relevance score
        assert all("RELEVANCE" in r for r in results)

        # Cleanup
        await hana_db.execute(f"DROP TABLE {table_name} CASCADE", [])

    async def test_hana_fuzzy_search(self, hana_db):
        """Test fuzzy text search in HANA."""
        table_name = f"test_sources_{uuid.uuid4().hex[:8]}"

        # Create table
        await hana_db.execute(f"""
            CREATE COLUMN TABLE {table_name} (
                id VARCHAR(36) PRIMARY KEY,
                title NVARCHAR(500)
            )
        """, [])

        # Insert test data
        await hana_db.execute(f"""
            INSERT INTO {table_name} (id, title)
            VALUES (?, ?)
        """, [str(uuid.uuid4()), "Python Programming"])

        # Fuzzy search (with typo)
        results = await hana_db.query(f"""
            SELECT title
            FROM {table_name}
            WHERE CONTAINS(title, 'Pyton', FUZZY(0.8))
        """, [])

        # Should find "Python" despite typo
        assert len(results) >= 1

        # Cleanup
        await hana_db.execute(f"DROP TABLE {table_name} CASCADE", [])


@pytest.mark.hana
@pytest.mark.asyncio
class TestHANAPerformance:
    """Test HANA performance features."""

    async def test_hana_column_store(self, hana_db):
        """Test column store table creation."""
        table_name = f"test_columnar_{uuid.uuid4().hex[:8]}"

        # Create column store table
        await hana_db.execute(f"""
            CREATE COLUMN TABLE {table_name} (
                id VARCHAR(36) PRIMARY KEY,
                data NVARCHAR(1000)
            )
        """, [])

        # Verify it's a column store table
        result = await hana_db.query(f"""
            SELECT TABLE_TYPE FROM TABLES
            WHERE SCHEMA_NAME = CURRENT_SCHEMA
            AND TABLE_NAME = ?
        """, [table_name])

        assert result[0]["TABLE_TYPE"] == "COLUMN"

        # Cleanup
        await hana_db.execute(f"DROP TABLE {table_name}", [])

    async def test_hana_batch_insert_performance(self, hana_db):
        """Test batch insert performance."""
        table_name = f"test_batch_{uuid.uuid4().hex[:8]}"

        # Create table
        await hana_db.execute(f"""
            CREATE COLUMN TABLE {table_name} (
                id VARCHAR(36) PRIMARY KEY,
                name NVARCHAR(255),
                value INTEGER
            )
        """, [])

        # Batch insert 1000 records
        import time
        start_time = time.time()

        for i in range(1000):
            await hana_db.execute(f"""
                INSERT INTO {table_name} (id, name, value)
                VALUES (?, ?, ?)
            """, [str(uuid.uuid4()), f"Record {i}", i])

        elapsed_time = time.time() - start_time

        # Should complete in reasonable time
        assert elapsed_time < 30  # 30 seconds for 1000 inserts

        # Verify count
        result = await hana_db.query(f"SELECT COUNT(*) as cnt FROM {table_name}", [])
        assert result[0]["CNT"] == 1000

        # Cleanup
        await hana_db.execute(f"DROP TABLE {table_name}", [])


@pytest.mark.hana
@pytest.mark.asyncio
class TestHANATransactions:
    """Test HANA transaction support."""

    async def test_hana_transaction_commit(self, hana_db):
        """Test transaction commit in HANA."""
        table_name = f"test_tx_{uuid.uuid4().hex[:8]}"

        # Create table
        await hana_db.execute(f"""
            CREATE COLUMN TABLE {table_name} (
                id VARCHAR(36) PRIMARY KEY,
                name NVARCHAR(255)
            )
        """, [])

        # Transaction
        async with hana_db.begin_transaction():
            await hana_db.execute(f"""
                INSERT INTO {table_name} (id, name) VALUES (?, ?)
            """, [str(uuid.uuid4()), "Record 1"])

            await hana_db.execute(f"""
                INSERT INTO {table_name} (id, name) VALUES (?, ?)
            """, [str(uuid.uuid4()), "Record 2"])

        # Verify commit
        result = await hana_db.query(f"SELECT COUNT(*) as cnt FROM {table_name}", [])
        assert result[0]["CNT"] == 2

        # Cleanup
        await hana_db.execute(f"DROP TABLE {table_name}", [])

    async def test_hana_transaction_rollback(self, hana_db):
        """Test transaction rollback in HANA."""
        table_name = f"test_tx_{uuid.uuid4().hex[:8]}"

        # Create table
        await hana_db.execute(f"""
            CREATE COLUMN TABLE {table_name} (
                id VARCHAR(36) PRIMARY KEY,
                name NVARCHAR(255)
            )
        """, [])

        # Transaction with error
        try:
            async with hana_db.begin_transaction():
                await hana_db.execute(f"""
                    INSERT INTO {table_name} (id, name) VALUES (?, ?)
                """, [str(uuid.uuid4()), "Record 1"])

                # Intentional error
                raise Exception("Rollback test")
        except Exception:
            pass

        # Verify rollback
        result = await hana_db.query(f"SELECT COUNT(*) as cnt FROM {table_name}", [])
        assert result[0]["CNT"] == 0

        # Cleanup
        await hana_db.execute(f"DROP TABLE {table_name}", [])
