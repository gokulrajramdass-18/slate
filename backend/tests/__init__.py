"""
Open Notebook Test Suite

Comprehensive test suite for the Open Notebook HANA DB Migration Project.

Test Organization:
- test_database_interface.py: Database abstraction layer tests
- test_hana_impl.py: HANA Cloud implementation tests
- test_domain.py: Domain model tests
- test_notebooks_api.py: API endpoint tests
- test_search_strategies.py: Search strategy tests
- test_sync_service.py: Sync service tests
- conftest.py: Shared fixtures and configuration

Usage:
    pytest tests/                          # Run all tests
    pytest tests/test_domain.py            # Run specific file
    pytest -m api tests/                   # Run by marker
    pytest --cov=open_notebook tests/      # With coverage
"""

__version__ = "1.0.0"
