"""
Performance Tests for Open Notebook

Tests system performance under various loads:
- Load 10k documents → Measure ingestion time
- Vector search with 10k embeddings → Measure query time
- Concurrent API requests (100 users) → Measure response time
- Large file upload (100MB) → Measure upload time
- Database switch time measurement
"""

import asyncio
import random
import tempfile
import time
from pathlib import Path
from typing import List

import pytest
from httpx import AsyncClient


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.asyncio
class TestIngestionPerformance:
    """Test document ingestion performance."""

    async def test_bulk_document_ingestion(self, async_test_client):
        """Test ingesting 1000 documents and measure time."""
        client = async_test_client

        # Create notebook
        notebook = await client.post(
            "/api/notebooks",
            json={"name": "Bulk Ingestion Test", "description": "Performance test"},
        )
        notebook_id = notebook.json()["id"]

        # Prepare test documents
        num_docs = 1000
        documents = [
            {
                "title": f"Test Document {i}",
                "source_type": "text",
                "full_text": f"This is test document number {i}. " * 50,  # ~50 words
                "notebook_id": notebook_id,
            }
            for i in range(num_docs)
        ]

        # Measure ingestion time
        start_time = time.time()

        # Ingest in batches of 100 for better performance
        batch_size = 100
        for i in range(0, num_docs, batch_size):
            batch = documents[i : i + batch_size]
            tasks = [client.post("/api/sources", json=doc) for doc in batch]
            responses = await asyncio.gather(*tasks)

            # Verify all succeeded
            for response in responses:
                assert response.status_code == 201

        end_time = time.time()
        elapsed = end_time - start_time

        # Calculate metrics
        docs_per_second = num_docs / elapsed
        print(f"\nIngestion Performance:")
        print(f"  Documents: {num_docs}")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Throughput: {docs_per_second:.2f} docs/sec")

        # Performance target: At least 50 docs/sec
        assert docs_per_second > 50, f"Ingestion too slow: {docs_per_second:.2f} docs/sec"

    async def test_embedding_generation_performance(
        self, async_test_client, mock_embedding_model
    ):
        """Test embedding generation for 100 documents."""
        pytest.skip("Embedding generation API not yet implemented")

        client = async_test_client

        # Create notebook with sources
        notebook = await client.post(
            "/api/notebooks",
            json={"name": "Embedding Test", "description": "Test embeddings"},
        )
        notebook_id = notebook.json()["id"]

        # Create 100 sources
        num_sources = 100
        source_ids = []
        for i in range(num_sources):
            source = await client.post(
                "/api/sources",
                json={
                    "title": f"Doc {i}",
                    "source_type": "text",
                    "full_text": f"Document content {i}. " * 100,
                    "notebook_id": notebook_id,
                },
            )
            source_ids.append(source.json()["id"])

        # Measure embedding generation time
        start_time = time.time()

        # Trigger embedding generation
        response = await client.post("/api/embeddings/generate", json={"source_ids": source_ids})
        assert response.status_code in [200, 202]

        # Wait for completion
        await asyncio.sleep(5)

        end_time = time.time()
        elapsed = end_time - start_time

        print(f"\nEmbedding Generation Performance:")
        print(f"  Sources: {num_sources}")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Throughput: {num_sources / elapsed:.2f} sources/sec")


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.asyncio
class TestSearchPerformance:
    """Test search performance with large datasets."""

    async def test_vector_search_performance(self, async_test_client):
        """Test vector search with 1000 documents."""
        pytest.skip("Vector search with embeddings not yet fully implemented")

        client = async_test_client

        # Create notebook with many sources
        notebook = await client.post(
            "/api/notebooks",
            json={"name": "Vector Search Test", "description": "Performance test"},
        )
        notebook_id = notebook.json()["id"]

        # Create 1000 sources
        num_sources = 1000
        for i in range(num_sources):
            await client.post(
                "/api/sources",
                json={
                    "title": f"Document {i}",
                    "source_type": "text",
                    "full_text": f"Content for document {i}. " * 50,
                    "notebook_id": notebook_id,
                },
            )

        # Run vector searches and measure time
        queries = [
            "machine learning",
            "database design",
            "web development",
            "python programming",
            "artificial intelligence",
        ]

        times = []
        for query in queries:
            start_time = time.time()

            search_query = {"query": query, "strategy": "vector", "limit": 10}
            response = await client.post("/api/search", json=search_query)
            assert response.status_code == 200

            elapsed = time.time() - start_time
            times.append(elapsed)

        avg_time = sum(times) / len(times)
        print(f"\nVector Search Performance:")
        print(f"  Dataset size: {num_sources} documents")
        print(f"  Queries: {len(queries)}")
        print(f"  Average query time: {avg_time*1000:.2f}ms")
        print(f"  Min/Max: {min(times)*1000:.2f}ms / {max(times)*1000:.2f}ms")

        # Performance target: Average query under 500ms
        assert avg_time < 0.5, f"Search too slow: {avg_time*1000:.2f}ms"

    async def test_keyword_search_performance(self, async_test_client):
        """Test keyword search performance with 1000 documents."""
        client = async_test_client

        # Create notebook
        notebook = await client.post(
            "/api/notebooks",
            json={"name": "Keyword Search Test", "description": "Performance test"},
        )
        notebook_id = notebook.json()["id"]

        # Create 1000 sources with varied content
        num_sources = 1000
        keywords = ["python", "database", "machine learning", "web", "API"]

        for i in range(num_sources):
            keyword = random.choice(keywords)
            await client.post(
                "/api/sources",
                json={
                    "title": f"Document {i}",
                    "source_type": "text",
                    "full_text": f"This document is about {keyword}. " * 50,
                    "notebook_id": notebook_id,
                },
            )

        # Run keyword searches
        times = []
        for keyword in keywords:
            start_time = time.time()

            search_query = {"query": keyword, "strategy": "keyword", "limit": 10}
            response = await client.post("/api/search", json=search_query)
            assert response.status_code == 200

            elapsed = time.time() - start_time
            times.append(elapsed)

        avg_time = sum(times) / len(times)
        print(f"\nKeyword Search Performance:")
        print(f"  Dataset size: {num_sources} documents")
        print(f"  Queries: {len(keywords)}")
        print(f"  Average query time: {avg_time*1000:.2f}ms")

        # Performance target: Under 200ms
        assert avg_time < 0.2, f"Keyword search too slow: {avg_time*1000:.2f}ms"

    async def test_hybrid_search_performance(self, async_test_client):
        """Test hybrid search performance."""
        client = async_test_client

        # Create test data
        notebook = await client.post(
            "/api/notebooks",
            json={"name": "Hybrid Search Test", "description": "Performance test"},
        )
        notebook_id = notebook.json()["id"]

        # Create 500 sources
        for i in range(500):
            await client.post(
                "/api/sources",
                json={
                    "title": f"Doc {i}",
                    "source_type": "text",
                    "full_text": f"Document {i} content. " * 50,
                    "notebook_id": notebook_id,
                },
            )

        # Measure hybrid search time
        start_time = time.time()

        search_query = {"query": "document content", "strategy": "hybrid", "limit": 10}
        response = await client.post("/api/search", json=search_query)

        elapsed = time.time() - start_time
        print(f"\nHybrid Search Performance:")
        print(f"  Dataset size: 500 documents")
        print(f"  Query time: {elapsed*1000:.2f}ms")

        # Hybrid should be reasonable even with both strategies
        assert elapsed < 1.0, f"Hybrid search too slow: {elapsed*1000:.2f}ms"


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.asyncio
class TestConcurrentLoadPerformance:
    """Test system performance under concurrent load."""

    async def test_concurrent_read_performance(self, async_test_client):
        """Test 100 concurrent read requests."""
        client = async_test_client

        # Create test notebook
        notebook = await client.post(
            "/api/notebooks",
            json={"name": "Concurrent Test", "description": "Load test"},
        )
        notebook_id = notebook.json()["id"]

        # Simulate 100 concurrent users reading
        num_requests = 100

        async def read_notebook():
            start = time.time()
            response = await client.get(f"/api/notebooks/{notebook_id}")
            elapsed = time.time() - start
            return response.status_code, elapsed

        start_time = time.time()
        results = await asyncio.gather(*[read_notebook() for _ in range(num_requests)])
        total_time = time.time() - start_time

        # Analyze results
        success_count = sum(1 for status, _ in results if status == 200)
        times = [elapsed for _, elapsed in results]
        avg_time = sum(times) / len(times)
        p95_time = sorted(times)[int(len(times) * 0.95)]

        print(f"\nConcurrent Read Performance:")
        print(f"  Requests: {num_requests}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Success rate: {success_count / num_requests * 100:.1f}%")
        print(f"  Avg response time: {avg_time*1000:.2f}ms")
        print(f"  P95 response time: {p95_time*1000:.2f}ms")
        print(f"  Throughput: {num_requests / total_time:.2f} req/sec")

        # Performance targets
        assert success_count == num_requests, "Some requests failed"
        assert avg_time < 0.1, f"Average response too slow: {avg_time*1000:.2f}ms"
        assert p95_time < 0.2, f"P95 response too slow: {p95_time*1000:.2f}ms"

    async def test_concurrent_write_performance(self, async_test_client):
        """Test 50 concurrent write requests."""
        client = async_test_client

        num_requests = 50

        async def create_notebook(index: int):
            start = time.time()
            notebook_data = {
                "name": f"Load Test Notebook {index}",
                "description": f"Created for load test {index}",
            }
            response = await client.post("/api/notebooks", json=notebook_data)
            elapsed = time.time() - start
            return response.status_code, elapsed

        start_time = time.time()
        results = await asyncio.gather(*[create_notebook(i) for i in range(num_requests)])
        total_time = time.time() - start_time

        # Analyze results
        success_count = sum(1 for status, _ in results if status == 201)
        times = [elapsed for _, elapsed in results]
        avg_time = sum(times) / len(times)

        print(f"\nConcurrent Write Performance:")
        print(f"  Requests: {num_requests}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Success rate: {success_count / num_requests * 100:.1f}%")
        print(f"  Avg response time: {avg_time*1000:.2f}ms")
        print(f"  Throughput: {num_requests / total_time:.2f} req/sec")

        # Performance targets
        assert success_count == num_requests, "Some requests failed"
        assert avg_time < 0.2, f"Average write too slow: {avg_time*1000:.2f}ms"

    async def test_mixed_workload_performance(self, async_test_client):
        """Test mixed read/write/search workload."""
        client = async_test_client

        # Create test data
        notebook = await client.post(
            "/api/notebooks",
            json={"name": "Mixed Workload Test", "description": "Performance test"},
        )
        notebook_id = notebook.json()["id"]

        # Add some sources
        for i in range(10):
            await client.post(
                "/api/sources",
                json={
                    "title": f"Source {i}",
                    "source_type": "text",
                    "full_text": f"Content {i}",
                    "notebook_id": notebook_id,
                },
            )

        # Mix of operations
        async def read_op():
            start = time.time()
            await client.get(f"/api/notebooks/{notebook_id}")
            return "read", time.time() - start

        async def write_op(index: int):
            start = time.time()
            await client.post(
                "/api/sources",
                json={
                    "title": f"New Source {index}",
                    "source_type": "text",
                    "full_text": "New content",
                    "notebook_id": notebook_id,
                },
            )
            return "write", time.time() - start

        async def search_op():
            start = time.time()
            await client.post(
                "/api/search", json={"query": "content", "strategy": "keyword"}
            )
            return "search", time.time() - start

        # Mix of 60 reads, 20 writes, 20 searches
        operations = (
            [read_op() for _ in range(60)]
            + [write_op(i) for i in range(20)]
            + [search_op() for _ in range(20)]
        )
        random.shuffle(operations)

        # Execute all operations
        start_time = time.time()
        results = await asyncio.gather(*operations)
        total_time = time.time() - start_time

        # Analyze by operation type
        by_type = {}
        for op_type, elapsed in results:
            if op_type not in by_type:
                by_type[op_type] = []
            by_type[op_type].append(elapsed)

        print(f"\nMixed Workload Performance:")
        print(f"  Total operations: {len(operations)}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Throughput: {len(operations) / total_time:.2f} ops/sec")

        for op_type, times in by_type.items():
            avg = sum(times) / len(times)
            print(f"  {op_type.capitalize()} avg: {avg*1000:.2f}ms ({len(times)} ops)")


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.asyncio
class TestFileUploadPerformance:
    """Test file upload performance."""

    async def test_small_file_upload(self, async_test_client):
        """Test uploading 1MB file."""
        client = async_test_client

        # Create notebook
        notebook = await client.post(
            "/api/notebooks", json={"name": "File Upload Test", "description": "Test"}
        )
        notebook_id = notebook.json()["id"]

        # Create 1MB test file
        file_size = 1 * 1024 * 1024  # 1MB
        content = b"x" * file_size

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            # Measure upload time
            start_time = time.time()

            with open(temp_path, "rb") as f:
                files = {"file": ("test.txt", f, "text/plain")}
                data = {"title": "Large File", "notebook_id": notebook_id}
                response = await client.post("/api/sources/upload", files=files, data=data)

            elapsed = time.time() - start_time

            print(f"\nFile Upload Performance (1MB):")
            print(f"  Upload time: {elapsed:.2f}s")
            print(f"  Throughput: {file_size / elapsed / 1024 / 1024:.2f} MB/s")

            assert response.status_code == 201
            assert elapsed < 2.0, f"Upload too slow: {elapsed:.2f}s"

        finally:
            Path(temp_path).unlink()

    async def test_large_file_upload(self, async_test_client):
        """Test uploading 10MB file."""
        client = async_test_client

        # Create notebook
        notebook = await client.post(
            "/api/notebooks", json={"name": "Large File Test", "description": "Test"}
        )
        notebook_id = notebook.json()["id"]

        # Create 10MB test file
        file_size = 10 * 1024 * 1024  # 10MB
        content = b"x" * file_size

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            # Measure upload time
            start_time = time.time()

            with open(temp_path, "rb") as f:
                files = {"file": ("large_test.txt", f, "text/plain")}
                data = {"title": "Very Large File", "notebook_id": notebook_id}
                response = await client.post("/api/sources/upload", files=files, data=data)

            elapsed = time.time() - start_time

            print(f"\nFile Upload Performance (10MB):")
            print(f"  Upload time: {elapsed:.2f}s")
            print(f"  Throughput: {file_size / elapsed / 1024 / 1024:.2f} MB/s")

            assert response.status_code == 201
            assert elapsed < 10.0, f"Upload too slow: {elapsed:.2f}s"

        finally:
            Path(temp_path).unlink()


@pytest.mark.slow
@pytest.mark.hana
@pytest.mark.asyncio
class TestDatabaseSwitchPerformance:
    """Test database switching performance."""

    async def test_database_switch_time(self, async_test_client, hana_db_config):
        """Measure time to switch between databases."""
        pytest.skip("Requires HANA connection")

        client = async_test_client

        # Measure switch to HANA
        hana_config = {
            "database_type": "hana",
            "hana_host": hana_db_config.hana_host,
            "hana_port": hana_db_config.hana_port,
            "hana_user": hana_db_config.hana_user,
            "hana_password": hana_db_config.hana_password,
            "hana_database": hana_db_config.hana_database,
        }

        start_time = time.time()
        response = await client.post("/api/database/switch", json=hana_config)
        elapsed_to_hana = time.time() - start_time

        assert response.status_code == 200

        # Measure switch back to SQLite
        sqlite_config = {"database_type": "sqlite"}

        start_time = time.time()
        response = await client.post("/api/database/switch", json=sqlite_config)
        elapsed_to_sqlite = time.time() - start_time

        assert response.status_code == 200

        print(f"\nDatabase Switch Performance:")
        print(f"  SQLite → HANA: {elapsed_to_hana:.2f}s")
        print(f"  HANA → SQLite: {elapsed_to_sqlite:.2f}s")

        # Should be reasonably fast
        assert elapsed_to_hana < 5.0
        assert elapsed_to_sqlite < 5.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "--tb=short"])
