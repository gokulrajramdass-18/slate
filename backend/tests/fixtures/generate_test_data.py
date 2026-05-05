"""
Test Data Generator for Open Notebook E2E Tests

Generates realistic test data including:
- Multiple notebooks with sources
- Sample embeddings
- Chat histories
- Search queries and expected results
"""

import asyncio
import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import numpy as np


class TestDataGenerator:
    """Generate realistic test data for E2E tests."""

    def __init__(self, seed: int = 42):
        """Initialize with a seed for reproducibility."""
        random.seed(seed)
        np.random.seed(seed)

    # Sample content for documents
    SAMPLE_DOCUMENTS = [
        {
            "title": "Python Best Practices",
            "content": "Python is a versatile programming language. Best practices include using virtual environments, writing docstrings, and following PEP 8 style guide. Type hints improve code readability.",
            "topics": ["python", "programming", "best practices"],
        },
        {
            "title": "Machine Learning Introduction",
            "content": "Machine learning enables computers to learn from data without explicit programming. Common algorithms include linear regression, decision trees, and neural networks. Feature engineering is crucial for model performance.",
            "topics": ["machine learning", "AI", "data science"],
        },
        {
            "title": "Database Design Principles",
            "content": "Effective database design involves normalization, indexing, and choosing appropriate data types. ACID properties ensure data integrity. Consider denormalization for read-heavy workloads.",
            "topics": ["database", "design", "SQL"],
        },
        {
            "title": "REST API Design",
            "content": "RESTful APIs use HTTP methods correctly: GET for retrieval, POST for creation, PUT for updates, DELETE for removal. Use proper status codes and consistent resource naming conventions.",
            "topics": ["API", "REST", "web development"],
        },
        {
            "title": "SAP HANA Overview",
            "content": "SAP HANA is an in-memory database platform that enables real-time analytics. It combines row and column-based storage. Vector embeddings can be stored for similarity search using COSINE_SIMILARITY function.",
            "topics": ["HANA", "database", "analytics", "SAP"],
        },
        {
            "title": "Vector Search Explained",
            "content": "Vector search enables semantic similarity queries by representing text as high-dimensional embeddings. Cosine similarity measures the angle between vectors. ANN algorithms like HNSW improve search speed.",
            "topics": ["vector search", "embeddings", "semantic search"],
        },
        {
            "title": "FastAPI Framework",
            "content": "FastAPI is a modern Python web framework based on type hints. It provides automatic API documentation, request validation, and async support. Built on Starlette and Pydantic.",
            "topics": ["FastAPI", "Python", "web framework"],
        },
        {
            "title": "Pytest Testing Guide",
            "content": "Pytest is a testing framework for Python. Features include fixtures for setup, parametrized tests, and plugins for async and coverage. Use markers to organize tests.",
            "topics": ["pytest", "testing", "Python"],
        },
        {
            "title": "CI/CD Best Practices",
            "content": "Continuous integration and deployment automate software delivery. Run tests on every commit, use staging environments, and implement gradual rollouts. Monitor deployments carefully.",
            "topics": ["CI/CD", "DevOps", "automation"],
        },
        {
            "title": "Docker Containerization",
            "content": "Docker packages applications with their dependencies into containers. Use multi-stage builds to reduce image size. Docker Compose orchestrates multi-container applications.",
            "topics": ["Docker", "containers", "DevOps"],
        },
    ]

    SAMPLE_CHAT_MESSAGES = [
        "What are the main features of this system?",
        "How do I create a new notebook?",
        "Can you explain vector search?",
        "What databases are supported?",
        "How does the sync feature work?",
        "Tell me about search strategies",
        "What is agentic RAG?",
        "How do I configure HANA connection?",
    ]

    def generate_notebooks(self, count: int = 5) -> List[Dict[str, Any]]:
        """Generate sample notebooks."""
        notebooks = []
        for i in range(count):
            notebook = {
                "id": str(uuid.uuid4()),
                "name": f"Test Notebook {i+1}",
                "description": f"A test notebook for E2E testing - {i+1}",
                "archived": random.choice([True, False]) if i > 2 else False,
                "folder_id": None,
                "created": (datetime.now() - timedelta(days=random.randint(1, 30))).isoformat(),
                "updated": (datetime.now() - timedelta(days=random.randint(0, 5))).isoformat(),
            }
            notebooks.append(notebook)
        return notebooks

    def generate_sources(self, count: int = 10) -> List[Dict[str, Any]]:
        """Generate sample sources with realistic content."""
        sources = []
        for i in range(count):
            doc = random.choice(self.SAMPLE_DOCUMENTS)
            source_type = random.choice(["file", "url", "text", "hana_table", "api"])

            source = {
                "id": str(uuid.uuid4()),
                "title": doc["title"],
                "source_type": source_type,
                "full_text": doc["content"],
                "topics": json.dumps(doc["topics"]),
                "asset_type": self._get_asset_type(source_type),
                "asset_data": None,
                "connection_config": self._get_connection_config(source_type),
                "sync_config": self._get_sync_config(source_type),
                "created": (datetime.now() - timedelta(days=random.randint(1, 30))).isoformat(),
                "updated": (datetime.now() - timedelta(days=random.randint(0, 5))).isoformat(),
            }
            sources.append(source)
        return sources

    def _get_asset_type(self, source_type: str) -> str:
        """Get appropriate asset type for source type."""
        if source_type == "file":
            return random.choice(["pdf", "docx", "txt"])
        elif source_type == "url":
            return "url"
        return None

    def _get_connection_config(self, source_type: str) -> str:
        """Generate connection config for source type."""
        if source_type == "hana_table":
            config = {
                "host": "test.hanacloud.ondemand.com",
                "port": 443,
                "table": "TEST_TABLE",
                "columns": ["TITLE", "CONTENT", "CATEGORY"],
            }
            return json.dumps(config)
        elif source_type == "api":
            config = {
                "endpoint": "https://api.example.com/data",
                "method": "GET",
                "auth_type": "bearer",
                "headers": {"Accept": "application/json"},
            }
            return json.dumps(config)
        return None

    def _get_sync_config(self, source_type: str) -> str:
        """Generate sync config for source type."""
        if source_type in ["hana_table", "api"]:
            config = {
                "frequency": random.choice(["0 */6 * * *", "0 */12 * * *", "0 0 * * *"]),
                "last_sync": None,
                "status": "idle",
            }
            return json.dumps(config)
        return None

    def generate_embeddings(
        self, source_id: str, chunks: int = 5, dimension: int = 1536
    ) -> List[Dict[str, Any]]:
        """Generate sample embeddings for a source."""
        embeddings = []
        for i in range(chunks):
            # Generate normalized random embedding
            embedding_vec = np.random.randn(dimension).astype(np.float32)
            embedding_vec = embedding_vec / np.linalg.norm(embedding_vec)

            embedding = {
                "id": str(uuid.uuid4()),
                "source_id": source_id,
                "order_num": i,
                "content": f"Chunk {i+1} of the source content",
                "embedding": embedding_vec.tobytes(),
                "created": datetime.now().isoformat(),
            }
            embeddings.append(embedding)
        return embeddings

    def generate_chat_sessions(
        self, notebook_id: str, count: int = 3
    ) -> List[Dict[str, Any]]:
        """Generate sample chat sessions with messages."""
        sessions = []
        for i in range(count):
            session_id = str(uuid.uuid4())
            session = {
                "id": session_id,
                "title": f"Chat Session {i+1}",
                "notebook_id": notebook_id,
                "created": (datetime.now() - timedelta(hours=random.randint(1, 48))).isoformat(),
                "updated": datetime.now().isoformat(),
                "messages": self.generate_chat_messages(session_id, random.randint(2, 6)),
            }
            sessions.append(session)
        return sessions

    def generate_chat_messages(
        self, session_id: str, count: int = 4
    ) -> List[Dict[str, Any]]:
        """Generate chat messages for a session."""
        messages = []
        for i in range(count):
            role = "user" if i % 2 == 0 else "assistant"
            if role == "user":
                content = random.choice(self.SAMPLE_CHAT_MESSAGES)
            else:
                content = "Based on the notebook content, here's what I found..."

            message = {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "role": role,
                "content": content,
                "created": (datetime.now() - timedelta(minutes=random.randint(1, 60))).isoformat(),
            }
            messages.append(message)
        return messages

    def generate_search_queries(self) -> List[Dict[str, Any]]:
        """Generate sample search queries with expected results."""
        queries = [
            {
                "query": "Python programming",
                "strategy": "keyword",
                "filters": {},
                "expected_keywords": ["Python", "programming", "PEP 8"],
            },
            {
                "query": "machine learning algorithms",
                "strategy": "vector",
                "filters": {},
                "expected_keywords": ["machine learning", "algorithms", "neural networks"],
            },
            {
                "query": "database design best practices",
                "strategy": "hybrid",
                "filters": {},
                "expected_keywords": ["database", "design", "normalization"],
            },
            {
                "query": "How to build REST APIs?",
                "strategy": "agentic_rag",
                "filters": {},
                "expected_keywords": ["REST", "API", "HTTP"],
            },
        ]
        return queries

    def generate_notebook_source_relationships(
        self, notebooks: List[Dict], sources: List[Dict]
    ) -> List[Dict[str, str]]:
        """Generate notebook-source relationships."""
        relationships = []
        for notebook in notebooks:
            # Assign 2-4 sources to each notebook
            num_sources = random.randint(2, min(4, len(sources)))
            selected_sources = random.sample(sources, num_sources)

            for source in selected_sources:
                relationships.append(
                    {
                        "notebook_id": notebook["id"],
                        "source_id": source["id"],
                        "created": datetime.now().isoformat(),
                    }
                )
        return relationships

    def save_to_file(self, data: Dict[str, Any], filename: str):
        """Save generated data to JSON file."""
        output_path = Path(__file__).parent / filename
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print(f"Saved test data to {output_path}")

    def generate_complete_dataset(self) -> Dict[str, Any]:
        """Generate a complete test dataset with all entities."""
        print("Generating complete test dataset...")

        notebooks = self.generate_notebooks(5)
        sources = self.generate_sources(10)
        relationships = self.generate_notebook_source_relationships(notebooks, sources)

        # Generate embeddings for first 5 sources
        all_embeddings = []
        for source in sources[:5]:
            embeddings = self.generate_embeddings(source["id"], chunks=5)
            all_embeddings.extend(embeddings)

        # Generate chat sessions for first notebook
        chat_sessions = self.generate_chat_sessions(notebooks[0]["id"], 3)

        search_queries = self.generate_search_queries()

        dataset = {
            "notebooks": notebooks,
            "sources": sources,
            "notebook_source": relationships,
            "embeddings": all_embeddings,
            "chat_sessions": chat_sessions,
            "search_queries": search_queries,
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "seed": 42,
                "version": "1.0",
            },
        }

        return dataset


async def main():
    """Generate and save test data."""
    generator = TestDataGenerator(seed=42)
    dataset = generator.generate_complete_dataset()

    # Save to file
    generator.save_to_file(dataset, "test_data.json")

    # Print summary
    print("\nTest Data Summary:")
    print(f"  Notebooks: {len(dataset['notebooks'])}")
    print(f"  Sources: {len(dataset['sources'])}")
    print(f"  Relationships: {len(dataset['notebook_source'])}")
    print(f"  Embeddings: {len(dataset['embeddings'])}")
    print(f"  Chat Sessions: {len(dataset['chat_sessions'])}")
    print(f"  Search Queries: {len(dataset['search_queries'])}")


if __name__ == "__main__":
    asyncio.run(main())
