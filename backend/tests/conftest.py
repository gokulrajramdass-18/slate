"""
Pytest configuration and shared fixtures for Open Notebook tests.

This module provides fixtures for:
- Database setup (SQLite and HANA)
- Test client (FastAPI TestClient)
- Sample data fixtures
- Cleanup after tests
"""

import asyncio
import os
import pytest
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import Mock, patch

import numpy as np
from fastapi.testclient import TestClient
from httpx import AsyncClient


# Test database paths
TEST_DB_DIR = tempfile.mkdtemp()
TEST_SQLITE_PATH = os.path.join(TEST_DB_DIR, "test.db")


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def sqlite_db():
    """
    Provide a clean SQLite database for each test.
    Automatically creates schema and cleans up after test.
    """
    from open_notebook.database.sqlite_impl import SQLiteDatabase
    from open_notebook.database.interface import ConnectionConfig

    # Create unique DB for this test
    test_db_path = f"{TEST_SQLITE_PATH}_{id(asyncio.current_task())}"

    config = ConnectionConfig(
        db_type="sqlite",
        db_path=test_db_path
    )

    db = SQLiteDatabase(config)
    await db.connect()

    # Run schema creation using aiosqlite directly (SQLiteDatabase has no executescript)
    import aiosqlite
    async with aiosqlite.connect(test_db_path) as raw_db:
        await raw_db.executescript("""
            CREATE TABLE IF NOT EXISTS notebooks (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                archived BOOLEAN DEFAULT FALSE,
                folder_id VARCHAR(36),
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS sources (
                id VARCHAR(36) PRIMARY KEY,
                title VARCHAR(500),
                source_type VARCHAR(50),
                full_text TEXT,
                topics TEXT,
                asset_type VARCHAR(50),
                asset_data TEXT,
                connection_config TEXT,
                sync_config TEXT,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS notebook_source (
                notebook_id VARCHAR(36) NOT NULL,
                source_id VARCHAR(36) NOT NULL,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (notebook_id, source_id),
                FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE,
                FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS notes (
                id VARCHAR(36) PRIMARY KEY,
                title VARCHAR(255),
                summary TEXT,
                content TEXT,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS notebook_note (
                notebook_id VARCHAR(36) NOT NULL,
                note_id VARCHAR(36) NOT NULL,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (notebook_id, note_id),
                FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE,
                FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS source_embeddings (
                id VARCHAR(36) PRIMARY KEY,
                source_id VARCHAR(36) NOT NULL,
                order_num INTEGER,
                content TEXT,
                embedding BLOB,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS chat_sessions (
                id VARCHAR(36) PRIMARY KEY,
                title VARCHAR(255),
                notebook_id VARCHAR(36),
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id VARCHAR(36) PRIMARY KEY,
                session_id VARCHAR(36) NOT NULL,
                role VARCHAR(20),
                content TEXT,
                ui_components TEXT,
                render_mode TEXT DEFAULT 'markdown',
                tool_results TEXT,
                created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_chat_messages_render_mode ON chat_messages(render_mode);

            CREATE VIRTUAL TABLE IF NOT EXISTS sources_fts USING fts5(
                source_id UNINDEXED,
                title,
                full_text,
                content='sources',
                content_rowid='rowid'
            );
        """)

    yield db

    # Cleanup
    await db.disconnect()
    if os.path.exists(test_db_path):
        os.remove(test_db_path)


@pytest.fixture(scope="function")
def hana_db_config():
    """
    Provide HANA database configuration from environment variables.
    Skip test if HANA credentials not available.
    """
    hana_host = os.getenv("HANA_HOST")
    hana_port = os.getenv("HANA_PORT", "443")
    hana_user = os.getenv("HANA_USER")
    hana_password = os.getenv("HANA_PASSWORD")
    hana_database = os.getenv("HANA_DATABASE")

    if not all([hana_host, hana_user, hana_password, hana_database]):
        pytest.skip("HANA credentials not available in environment")

    from open_notebook.database.models import ConnectionConfig

    return ConnectionConfig(
        database_type="hana",
        hana_host=hana_host,
        hana_port=int(hana_port),
        hana_user=hana_user,
        hana_password=hana_password,
        hana_database=hana_database,
        hana_encrypt=True
    )


@pytest.fixture(scope="function")
async def hana_db(hana_db_config):
    """
    Provide a HANA database connection.
    Skip if credentials not available.
    """
    from open_notebook.database.hana_impl import HANADatabase

    db = HANADatabase(hana_db_config)
    await db.connect()

    yield db

    # Cleanup - drop test tables
    await db.disconnect()


@pytest.fixture
def test_client():
    """
    Provide FastAPI test client with in-memory SQLite database.
    """
    # Override database config for tests
    os.environ["DATABASE_TYPE"] = "sqlite"
    os.environ["SQLITE_DB_PATH"] = TEST_SQLITE_PATH

    from api.main import app

    with TestClient(app) as client:
        yield client


@pytest.fixture
async def async_test_client():
    """
    Provide async FastAPI test client.
    """
    os.environ["DATABASE_TYPE"] = "sqlite"
    os.environ["SQLITE_DB_PATH"] = TEST_SQLITE_PATH

    from api.main import app

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def sample_notebook_data():
    """Sample notebook data for testing."""
    return {
        "name": "Test Notebook",
        "description": "A test notebook for unit tests",
        "archived": False,
        "folder_id": None
    }


@pytest.fixture
def sample_source_data():
    """Sample source data for testing."""
    return {
        "title": "Test Document",
        "source_type": "text",
        "full_text": "This is a test document with some sample content.",
        "topics": ["testing", "documentation"],
        "asset_type": None,
        "asset_data": None,
        "connection_config": None,
        "sync_config": None
    }


@pytest.fixture
def sample_hana_table_source():
    """Sample HANA table source configuration."""
    return {
        "title": "Sales Data",
        "source_type": "hana_table",
        "connection_config": {
            "host": "test.hanacloud.ondemand.com",
            "port": 443,
            "user": "test_user",
            "password": "encrypted_password",
            "database": "test_db",
            "table": "SALES_DATA",
            "columns": ["PRODUCT_NAME", "DESCRIPTION", "CATEGORY"]
        },
        "sync_config": {
            "frequency": "0 */6 * * *",  # Every 6 hours
            "last_sync": None,
            "status": "idle"
        }
    }


@pytest.fixture
def sample_api_source():
    """Sample API source configuration."""
    return {
        "title": "GitHub Issues",
        "source_type": "api",
        "connection_config": {
            "endpoint": "https://api.github.com/repos/test/repo/issues",
            "method": "GET",
            "auth_type": "bearer",
            "bearer_token": "encrypted_token",
            "headers": {"Accept": "application/json"},
            "params": {"state": "open"},
            "response_path": "$.items[*]",
            "text_fields": ["title", "body"]
        },
        "sync_config": {
            "frequency": "0 */12 * * *",  # Every 12 hours
            "last_sync": None,
            "status": "idle"
        }
    }


@pytest.fixture
def sample_embeddings():
    """Generate sample embeddings for vector search tests."""
    # Generate 5 sample 1536-dimensional embeddings
    np.random.seed(42)
    embeddings = []

    for i in range(5):
        embedding = np.random.randn(1536).astype(np.float32)
        # Normalize to unit length
        embedding = embedding / np.linalg.norm(embedding)
        embeddings.append(embedding)

    return embeddings


@pytest.fixture
def mock_embedding_model():
    """Mock embedding model for testing without API calls."""
    def generate_embedding(text: str):
        # Generate deterministic embedding based on text hash
        np.random.seed(hash(text) % (2**32))
        embedding = np.random.randn(1536).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        return embedding.tolist()

    mock = Mock()
    mock.embed_query = Mock(side_effect=generate_embedding)
    mock.embed_documents = Mock(side_effect=lambda texts: [generate_embedding(t) for t in texts])

    return mock


@pytest.fixture
def mock_llm_model():
    """Mock LLM model for testing without API calls."""
    mock = Mock()
    mock.invoke = Mock(return_value="This is a mocked LLM response.")
    mock.astream = Mock(return_value=iter(["This ", "is ", "a ", "mocked ", "response."]))

    return mock


@pytest.fixture(autouse=True)
def reset_database_factory():
    """Reset the database factory singleton between tests."""
    # This ensures each test gets a fresh database connection
    from open_notebook import config
    if hasattr(config, '_db_instance'):
        delattr(config, '_db_instance')

    yield

    # Cleanup after test
    if hasattr(config, '_db_instance'):
        delattr(config, '_db_instance')


@pytest.fixture
def temp_upload_dir():
    """Provide temporary directory for file uploads."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_pdf_file(temp_upload_dir):
    """Create a sample PDF file for upload tests."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    pdf_path = os.path.join(temp_upload_dir, "test.pdf")

    c = canvas.Canvas(pdf_path, pagesize=letter)
    c.drawString(100, 750, "Test PDF Document")
    c.drawString(100, 700, "This is a test document for upload testing.")
    c.save()

    return pdf_path


# Markers for conditional test execution
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "hana: mark test as requiring HANA database connection"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "api: mark test as API endpoint test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end integration test"
    )


def pytest_collection_modifyitems(config, items):
    """Automatically skip HANA tests if credentials not available."""
    hana_available = all([
        os.getenv("HANA_HOST"),
        os.getenv("HANA_USER"),
        os.getenv("HANA_PASSWORD"),
        os.getenv("HANA_DATABASE")
    ])

    skip_hana = pytest.mark.skip(reason="HANA credentials not available")

    for item in items:
        if "hana" in item.keywords and not hana_available:
            item.add_marker(skip_hana)
