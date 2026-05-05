#!/usr/bin/env python3
"""
Test script to verify API structure and imports

Run this to check if all API components are properly set up.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_imports():
    """Test that all API modules can be imported"""
    print("Testing API imports...")

    try:
        # Test models
        print("  ✓ Importing api.models...")
        from api import models
        print(f"    - Found {len([x for x in dir(models) if not x.startswith('_')])} exports")

        # Test services
        print("  ✓ Importing api.services.database_service...")
        from api.services import database_service
        print(f"    - Found DatabaseService class")

        # Test routers
        print("  ✓ Importing api.routers.notebooks...")
        from api.routers import notebooks
        print(f"    - Router prefix: {notebooks.router.prefix}")

        print("  ✓ Importing api.routers.sources...")
        from api.routers import sources
        print(f"    - Router prefix: {sources.router.prefix}")

        print("  ✓ Importing api.routers.database...")
        from api.routers import database
        print(f"    - Router prefix: {database.router.prefix}")

        # Test main app
        print("  ✓ Importing api.main...")
        from api import main
        print(f"    - FastAPI app: {main.app.title}")

        print("\n✅ All imports successful!")
        return True

    except Exception as e:
        print(f"\n❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_models():
    """Test that Pydantic models are valid"""
    print("\nTesting Pydantic models...")

    try:
        from api.models import (
            NotebookCreate,
            NotebookResponse,
            SourceCreate,
            HANATableSourceCreate,
            APISourceCreate,
            DatabaseConfig,
            DatabaseType,
        )

        # Test notebook model
        notebook = NotebookCreate(
            name="Test Notebook",
            description="Test description",
            tags=["test"],
        )
        print(f"  ✓ NotebookCreate: {notebook.name}")

        # Test database config
        config = DatabaseConfig(
            db_type=DatabaseType.SQLITE,
            sqlite_config={"db_path": "./test.db"},
        )
        print(f"  ✓ DatabaseConfig: {config.db_type}")

        print("\n✅ All models valid!")
        return True

    except Exception as e:
        print(f"\n❌ Model validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_routes():
    """Test that routes are properly configured"""
    print("\nTesting route configuration...")

    try:
        from api import main

        # Get all routes
        routes = [route for route in main.app.routes if hasattr(route, 'methods')]
        print(f"  Found {len(routes)} routes:")

        # Group by prefix
        notebooks = [r for r in routes if r.path.startswith('/api/notebooks')]
        sources = [r for r in routes if r.path.startswith('/api/sources')]
        database = [r for r in routes if r.path.startswith('/api/database')]

        print(f"    - Notebooks: {len(notebooks)} endpoints")
        print(f"    - Sources: {len(sources)} endpoints")
        print(f"    - Database: {len(database)} endpoints")

        # Check key endpoints
        paths = [r.path for r in routes]
        required_endpoints = [
            '/api/notebooks',
            '/api/sources',
            '/api/database/config',
            '/api/database/switch',
            '/api/health',
        ]

        missing = [ep for ep in required_endpoints if ep not in paths]
        if missing:
            print(f"\n  ⚠️  Missing endpoints: {missing}")
        else:
            print(f"\n  ✓ All required endpoints present")

        print("\n✅ Route configuration valid!")
        return True

    except Exception as e:
        print(f"\n❌ Route configuration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 60)
    print("Open Notebook API - Structure Test")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Models", test_models()))
    results.append(("Routes", test_routes()))

    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n🎉 All tests passed! API structure is ready.")
        print("\nNext steps:")
        print("  1. Start the API server: python -m api.main")
        print("  2. Visit http://localhost:5055/api/docs")
        print("  3. Test endpoints using the Swagger UI")
        return 0
    else:
        print("\n❌ Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
