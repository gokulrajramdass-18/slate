"""
Test script for database abstraction layer

Tests basic database operations with SQLite implementation.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from open_notebook.config import get_database, DatabaseType
from open_notebook.database.repository import (
    repo_create,
    repo_query,
    repo_update,
    repo_delete,
    generate_id
)


async def test_database_connection():
    """Test basic database connection"""
    print("\n" + "=" * 60)
    print("Testing Database Connection")
    print("=" * 60)

    db = get_database()
    print(f"Database type: {db.db_type}")

    try:
        await db.connect()
        print("✓ Database connected successfully")

        # Test simple query
        result = await db.query("SELECT 1 as test")
        print(f"✓ Query test passed: {result}")

        await db.disconnect()
        print("✓ Database disconnected")

        return True
    except Exception as e:
        print(f"✗ Connection test failed: {str(e)}")
        return False


async def test_crud_operations():
    """Test CRUD operations"""
    print("\n" + "=" * 60)
    print("Testing CRUD Operations")
    print("=" * 60)

    db = get_database()
    await db.connect()

    try:
        # Create
        print("\n1. Testing CREATE...")
        notebook_data = {
            'name': 'Test Notebook',
            'description': 'A test notebook for database verification',
            'archived': 0
        }
        notebook_id = await db.create('notebooks', notebook_data)
        print(f"✓ Created notebook with ID: {notebook_id}")

        # Read
        print("\n2. Testing READ...")
        result = await db.query(
            "SELECT * FROM notebooks WHERE id = :id",
            {'id': notebook_id},
            fetch_one=True
        )
        print(f"✓ Read notebook: {result['name']}")

        # Update
        print("\n3. Testing UPDATE...")
        await db.update('notebooks', notebook_id, {
            'name': 'Updated Test Notebook',
            'archived': 1
        })
        result = await db.query(
            "SELECT * FROM notebooks WHERE id = :id",
            {'id': notebook_id},
            fetch_one=True
        )
        print(f"✓ Updated notebook: {result['name']}, archived={result['archived']}")

        # Delete
        print("\n4. Testing DELETE...")
        await db.delete('notebooks', notebook_id)
        result = await db.query(
            "SELECT * FROM notebooks WHERE id = :id",
            {'id': notebook_id}
        )
        print(f"✓ Deleted notebook (result count: {len(result)})")

        print("\n✓ All CRUD operations passed!")
        return True

    except Exception as e:
        print(f"\n✗ CRUD test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await db.disconnect()


async def test_repository_layer():
    """Test repository layer functions"""
    print("\n" + "=" * 60)
    print("Testing Repository Layer")
    print("=" * 60)

    try:
        # Create using repository
        print("\n1. Testing repo_create...")
        notebook_id = await repo_create('notebooks', {
            'name': 'Repository Test',
            'description': 'Testing repository layer'
        })
        print(f"✓ Created notebook via repository: {notebook_id}")

        # Query using repository
        print("\n2. Testing repo_query...")
        notebooks = await repo_query("SELECT * FROM notebooks WHERE id = :id", {'id': notebook_id})
        print(f"✓ Queried notebook: {notebooks[0]['name']}")

        # Update using repository
        print("\n3. Testing repo_update...")
        await repo_update('notebooks', notebook_id, {
            'name': 'Updated via Repository'
        })
        notebooks = await repo_query("SELECT * FROM notebooks WHERE id = :id", {'id': notebook_id})
        print(f"✓ Updated notebook: {notebooks[0]['name']}")

        # Delete using repository
        print("\n4. Testing repo_delete...")
        await repo_delete('notebooks', notebook_id)
        notebooks = await repo_query("SELECT * FROM notebooks WHERE id = :id", {'id': notebook_id})
        print(f"✓ Deleted notebook (result count: {len(notebooks)})")

        print("\n✓ All repository operations passed!")
        return True

    except Exception as e:
        print(f"\n✗ Repository test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_vector_search():
    """Test vector search functionality"""
    print("\n" + "=" * 60)
    print("Testing Vector Search")
    print("=" * 60)

    db = get_database()
    await db.connect()

    try:
        # Create a test source
        print("\n1. Creating test source...")
        source_id = await db.create('sources', {
            'title': 'Test Source',
            'source_type': 'text',
            'full_text': 'This is a test document about machine learning and AI.'
        })
        print(f"✓ Created source: {source_id}")

        # Create test embeddings
        print("\n2. Creating test embeddings...")
        import numpy as np
        import json

        # Generate random embeddings (simulating real embeddings)
        embedding1 = np.random.rand(128).tolist()  # Smaller dimension for testing
        embedding2 = np.random.rand(128).tolist()

        await db.create('source_embeddings', {
            'source_id': source_id,
            'order_num': 0,
            'content': 'Machine learning is a subset of AI',
            'embedding': json.dumps(embedding1)
        })

        await db.create('source_embeddings', {
            'source_id': source_id,
            'order_num': 1,
            'content': 'Neural networks are powerful models',
            'embedding': json.dumps(embedding2)
        })
        print("✓ Created 2 test embeddings")

        # Perform vector search
        print("\n3. Testing vector search...")
        query_embedding = np.random.rand(128).tolist()
        results = await db.vector_search(
            embedding=query_embedding,
            limit=5,
            threshold=0.0  # Low threshold for testing
        )
        print(f"✓ Vector search returned {len(results)} results")

        if results:
            print(f"  Top result similarity: {results[0]['similarity']:.4f}")
            print(f"  Content: {results[0]['content'][:50]}...")

        # Cleanup
        await db.delete('sources', source_id)
        print("\n✓ Vector search test passed!")
        return True

    except Exception as e:
        print(f"\n✗ Vector search test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await db.disconnect()


async def run_all_tests():
    """Run all tests"""
    print("\n")
    print("=" * 60)
    print("Open Notebook - Database Abstraction Layer Tests")
    print("=" * 60)

    # Set DATABASE_TYPE to sqlite for testing
    os.environ['DATABASE_TYPE'] = 'sqlite'
    os.environ['SQLITE_DB_PATH'] = './data/test_database.db'

    results = []

    # Run tests
    results.append(await test_database_connection())
    results.append(await test_crud_operations())
    results.append(await test_repository_layer())
    results.append(await test_vector_search())

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("\n✓ All tests passed!")
    else:
        print(f"\n✗ {total - passed} test(s) failed")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
