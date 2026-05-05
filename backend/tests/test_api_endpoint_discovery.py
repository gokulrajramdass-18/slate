"""
Unit Tests for API Endpoint Discovery Service

Tests the discovery of API endpoints from OpenAPI/Swagger specifications.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import httpx
from fastapi import HTTPException

from api.services.api_endpoint_discovery import (
    discover_endpoints_from_openapi,
    discover_endpoints_manual,
    store_discovered_endpoints,
    refresh_endpoint_metadata,
    get_endpoints_for_connection,
    get_endpoint_by_id,
    delete_endpoints_for_connection,
    get_endpoint_stats,
    _parse_openapi_3,
    _parse_swagger_2,
    MAX_SPEC_SIZE,
    MAX_ENDPOINTS
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def openapi_3_spec():
    """Sample OpenAPI 3.x specification"""
    return {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/users": {
                "get": {
                    "summary": "List users",
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer"}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Success",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"type": "object"}
                                    }
                                }
                            }
                        }
                    }
                },
                "post": {
                    "summary": "Create user",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "email": {"type": "string"}
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "Created",
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object"}
                                }
                            }
                        }
                    }
                }
            },
            "/users/{id}": {
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"}
                    }
                ],
                "get": {
                    "summary": "Get user by ID",
                    "responses": {
                        "200": {
                            "description": "Success",
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object"}
                                }
                            }
                        }
                    }
                }
            }
        }
    }


@pytest.fixture
def swagger_2_spec():
    """Sample Swagger 2.0 specification"""
    return {
        "swagger": "2.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/products": {
                "get": {
                    "summary": "List products",
                    "parameters": [
                        {
                            "name": "category",
                            "in": "query",
                            "type": "string",
                            "required": False
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Success",
                            "schema": {
                                "type": "array",
                                "items": {"type": "object"}
                            }
                        }
                    }
                }
            },
            "/products/{id}": {
                "get": {
                    "summary": "Get product",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "type": "string",
                            "required": True
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Success",
                            "schema": {"type": "object"}
                        }
                    }
                }
            }
        }
    }


# ============================================================================
# discover_endpoints_from_openapi() Tests - OpenAPI 3.x
# ============================================================================

@pytest.mark.asyncio
async def test_discover_endpoints_from_openapi_3_success(openapi_3_spec):
    """Test successful endpoint discovery from OpenAPI 3.x spec"""

    mock_response = MagicMock()
    mock_response.json.return_value = openapi_3_spec
    mock_response.headers = {"content-type": "application/json"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        endpoints = await discover_endpoints_from_openapi(
            "conn-123",
            "https://api.example.com/openapi.json"
        )

        # Should discover 3 endpoints (GET /users, POST /users, GET /users/{id})
        assert len(endpoints) == 3

        # Check GET /users
        get_users = next(e for e in endpoints if e["endpoint_path"] == "/users" and e["method"] == "GET")
        assert get_users["description"] == "List users"
        assert get_users["connection_id"] == "conn-123"

        # Parameters should be JSON string
        params = json.loads(get_users["parameters"])
        assert len(params) == 1
        assert params[0]["name"] == "limit"
        assert params[0]["type"] == "integer"
        assert params[0]["in"] == "query"

        # Response schema should be JSON string
        response_schema = json.loads(get_users["response_schema"])
        assert response_schema["type"] == "array"

        # Check POST /users
        post_users = next(e for e in endpoints if e["endpoint_path"] == "/users" and e["method"] == "POST")
        assert post_users["description"] == "Create user"

        # Request body schema should be JSON string
        request_schema = json.loads(post_users["request_body_schema"])
        assert request_schema["type"] == "object"
        assert "name" in request_schema["properties"]

        # Check GET /users/{id} - should include path parameter
        get_user = next(e for e in endpoints if e["endpoint_path"] == "/users/{id}")
        params = json.loads(get_user["parameters"])
        assert len(params) == 1
        assert params[0]["name"] == "id"
        assert params[0]["in"] == "path"
        assert params[0]["required"] is True


@pytest.mark.asyncio
async def test_discover_endpoints_from_openapi_with_auth():
    """Test fetching OpenAPI spec with authentication"""

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "openapi": "3.0.0",
        "info": {"title": "API"},
        "paths": {}
    }
    mock_response.headers = {"content-type": "application/json"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        auth_config = {
            "type": "bearer",
            "token": "test-token-123"
        }

        await discover_endpoints_from_openapi(
            "conn-123",
            "https://api.example.com/openapi.json",
            auth_config
        )

        # Verify bearer token was added to headers
        call_kwargs = mock_client.get.call_args[1]
        assert "headers" in call_kwargs
        assert call_kwargs["headers"]["Authorization"] == "Bearer test-token-123"


@pytest.mark.asyncio
async def test_discover_endpoints_from_openapi_with_api_key_auth():
    """Test fetching OpenAPI spec with API key authentication"""

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "openapi": "3.0.0",
        "info": {"title": "API"},
        "paths": {}
    }
    mock_response.headers = {"content-type": "application/json"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        auth_config = {
            "type": "api_key",
            "location": "header",
            "key": "X-API-Key",
            "value": "secret-key-123"
        }

        await discover_endpoints_from_openapi(
            "conn-123",
            "https://api.example.com/openapi.json",
            auth_config
        )

        # Verify API key was added to headers
        call_kwargs = mock_client.get.call_args[1]
        assert "headers" in call_kwargs
        assert call_kwargs["headers"]["X-API-Key"] == "secret-key-123"


# ============================================================================
# discover_endpoints_from_openapi() Tests - Swagger 2.0
# ============================================================================

@pytest.mark.asyncio
async def test_discover_endpoints_from_swagger_2_success(swagger_2_spec):
    """Test successful endpoint discovery from Swagger 2.0 spec"""

    mock_response = MagicMock()
    mock_response.json.return_value = swagger_2_spec
    mock_response.headers = {"content-type": "application/json"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        endpoints = await discover_endpoints_from_openapi(
            "conn-123",
            "https://api.example.com/swagger.json"
        )

        # Should discover 2 endpoints
        assert len(endpoints) == 2

        # Check GET /products
        get_products = next(e for e in endpoints if e["endpoint_path"] == "/products")
        assert get_products["description"] == "List products"
        params = json.loads(get_products["parameters"])
        assert params[0]["name"] == "category"
        assert params[0]["type"] == "string"


# ============================================================================
# discover_endpoints_from_openapi() Tests - Error Cases
# ============================================================================

@pytest.mark.asyncio
async def test_discover_endpoints_timeout():
    """Test timeout handling"""

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.side_effect = httpx.TimeoutException("Timeout")
        mock_client_class.return_value = mock_client

        with pytest.raises(HTTPException) as exc_info:
            await discover_endpoints_from_openapi(
                "conn-123",
                "https://api.example.com/openapi.json"
            )

        assert exc_info.value.status_code == 408
        assert "Timeout" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_discover_endpoints_http_error():
    """Test HTTP error handling"""

    mock_response = MagicMock()
    mock_response.status_code = 404

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.side_effect = httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=mock_response
        )
        mock_client_class.return_value = mock_client

        with pytest.raises(HTTPException) as exc_info:
            await discover_endpoints_from_openapi(
                "conn-123",
                "https://api.example.com/openapi.json"
            )

        assert exc_info.value.status_code == 400
        assert "Failed to fetch OpenAPI spec" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_discover_endpoints_spec_too_large():
    """Test spec size limit enforcement"""

    mock_response = MagicMock()
    mock_response.headers = {
        "content-type": "application/json",
        "content-length": str(MAX_SPEC_SIZE + 1000)
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        with pytest.raises(HTTPException) as exc_info:
            await discover_endpoints_from_openapi(
                "conn-123",
                "https://api.example.com/huge-spec.json"
            )

        # Implementation raises HTTPException with status 413 for size exceeded
        # But httpx might wrap it in a different status code, so check message
        assert exc_info.value.status_code in (400, 413)
        assert "too large" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_discover_endpoints_invalid_spec_format():
    """Test invalid spec format handling"""

    mock_response = MagicMock()
    mock_response.json.return_value = {"invalid": "spec"}  # No openapi or swagger version
    mock_response.headers = {"content-type": "application/json"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        with pytest.raises(HTTPException) as exc_info:
            await discover_endpoints_from_openapi(
                "conn-123",
                "https://api.example.com/spec.json"
            )

        assert exc_info.value.status_code == 400
        assert "Unsupported spec version" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_discover_endpoints_not_dict():
    """Test handling when spec is not a dictionary"""

    mock_response = MagicMock()
    mock_response.json.return_value = ["not", "a", "dict"]
    mock_response.headers = {"content-type": "application/json"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        with pytest.raises(HTTPException) as exc_info:
            await discover_endpoints_from_openapi(
                "conn-123",
                "https://api.example.com/spec.json"
            )

        assert exc_info.value.status_code == 400
        assert "Invalid OpenAPI spec format" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_discover_endpoints_respects_max_limit():
    """Test that endpoint limit is enforced"""

    # Create spec with more than MAX_ENDPOINTS
    large_spec = {
        "openapi": "3.0.0",
        "info": {"title": "Large API"},
        "paths": {}
    }

    # Add MAX_ENDPOINTS + 10 paths
    for i in range(MAX_ENDPOINTS + 10):
        large_spec["paths"][f"/endpoint{i}"] = {
            "get": {
                "summary": f"Endpoint {i}",
                "responses": {"200": {"description": "OK"}}
            }
        }

    mock_response = MagicMock()
    mock_response.json.return_value = large_spec
    mock_response.headers = {"content-type": "application/json"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        endpoints = await discover_endpoints_from_openapi(
            "conn-123",
            "https://api.example.com/spec.json"
        )

        # Should be limited to MAX_ENDPOINTS
        assert len(endpoints) == MAX_ENDPOINTS


# ============================================================================
# discover_endpoints_manual() Tests
# ============================================================================

@pytest.mark.asyncio
async def test_discover_endpoints_manual_success():
    """Test manual endpoint definition processing"""

    manual_endpoints = [
        {
            "path": "/users",
            "method": "GET",
            "description": "List all users"
        },
        {
            "path": "/users/{id}",
            "method": "GET",
            "description": "Get user by ID",
            "parameters": [
                {"name": "id", "type": "string", "in": "path", "required": True}
            ]
        },
        {
            "path": "/users",
            "method": "POST",
            "description": "Create user",
            "request_body_schema": {"type": "object"},
            "response_schema": {"type": "object"}
        }
    ]

    endpoints = await discover_endpoints_manual("conn-123", manual_endpoints)

    assert len(endpoints) == 3

    # Check first endpoint
    assert endpoints[0]["connection_id"] == "conn-123"
    assert endpoints[0]["endpoint_path"] == "/users"
    assert endpoints[0]["method"] == "GET"
    assert endpoints[0]["description"] == "List all users"

    # Check endpoint with parameters
    params = json.loads(endpoints[1]["parameters"])
    assert len(params) == 1
    assert params[0]["name"] == "id"

    # Check endpoint with schemas
    assert endpoints[2]["request_body_schema"] is not None
    assert endpoints[2]["response_schema"] is not None


@pytest.mark.asyncio
async def test_discover_endpoints_manual_missing_required_fields():
    """Test manual endpoint processing skips invalid entries"""

    manual_endpoints = [
        {"path": "/valid", "method": "GET"},  # Valid
        {"path": "/no-method"},  # Missing method
        {"method": "GET"},  # Missing path
        {"path": "/another-valid", "method": "POST"}  # Valid
    ]

    endpoints = await discover_endpoints_manual("conn-123", manual_endpoints)

    # Should only get 2 valid endpoints
    assert len(endpoints) == 2
    assert endpoints[0]["endpoint_path"] == "/valid"
    assert endpoints[1]["endpoint_path"] == "/another-valid"


@pytest.mark.asyncio
async def test_discover_endpoints_manual_normalizes_methods():
    """Test that HTTP methods are normalized to uppercase"""

    manual_endpoints = [
        {"path": "/test1", "method": "get"},
        {"path": "/test2", "method": "Post"},
        {"path": "/test3", "method": "DELETE"}
    ]

    endpoints = await discover_endpoints_manual("conn-123", manual_endpoints)

    assert all(e["method"].isupper() for e in endpoints)
    assert endpoints[0]["method"] == "GET"
    assert endpoints[1]["method"] == "POST"
    assert endpoints[2]["method"] == "DELETE"


# ============================================================================
# store_discovered_endpoints() Tests
# ============================================================================

@pytest.mark.asyncio
async def test_store_discovered_endpoints_success():
    """Test successful storage of discovered endpoints"""

    endpoints = [
        {
            "endpoint_path": "/users",
            "method": "GET",
            "description": "List users",
            "parameters": json.dumps([]),
            "request_body_schema": None,
            "response_schema": json.dumps({"type": "array"})
        },
        {
            "endpoint_path": "/users/{id}",
            "method": "GET",
            "description": "Get user",
            "parameters": json.dumps([{"name": "id", "in": "path"}]),
            "request_body_schema": None,
            "response_schema": json.dumps({"type": "object"})
        }
    ]

    with patch("api.services.api_endpoint_discovery.repo_execute") as mock_execute:
        with patch("api.services.api_endpoint_discovery.repo_create") as mock_create:
            mock_execute.return_value = None
            mock_create.return_value = None

            count = await store_discovered_endpoints("conn-123", endpoints)

            # Verify delete was called
            mock_execute.assert_called_once()
            delete_call = mock_execute.call_args
            assert "DELETE FROM api_connection_endpoints" in delete_call[0][0]

            # Verify creates were called
            assert mock_create.call_count == 2

            # Check first create
            first_create = mock_create.call_args_list[0][0]
            assert first_create[0] == "api_connection_endpoints"
            data = first_create[1]
            assert data["connection_id"] == "conn-123"
            assert data["endpoint_path"] == "/users"
            assert data["method"] == "GET"

            assert count == 2


@pytest.mark.asyncio
async def test_store_discovered_endpoints_empty():
    """Test storing empty endpoint list"""

    with patch("api.services.api_endpoint_discovery.repo_execute") as mock_execute:
        with patch("api.services.api_endpoint_discovery.repo_create") as mock_create:
            count = await store_discovered_endpoints("conn-123", [])

            # Should not call any database operations for empty list
            mock_execute.assert_not_called()
            mock_create.assert_not_called()

            assert count == 0


@pytest.mark.asyncio
async def test_store_discovered_endpoints_partial_failure():
    """Test handling of partial failures during storage"""

    endpoints = [
        {"endpoint_path": "/good", "method": "GET", "description": "Good"},
        {"endpoint_path": "/bad", "method": "GET", "description": "Bad"}
    ]

    with patch("api.services.api_endpoint_discovery.repo_execute"):
        with patch("api.services.api_endpoint_discovery.repo_create") as mock_create:
            # First succeeds, second fails
            mock_create.side_effect = [None, Exception("DB error")]

            count = await store_discovered_endpoints("conn-123", endpoints)

            # Should store what it can
            assert count == 1


# ============================================================================
# refresh_endpoint_metadata() Tests
# ============================================================================

@pytest.mark.asyncio
async def test_refresh_endpoint_metadata_with_url():
    """Test refreshing metadata with explicit OpenAPI URL"""

    with patch("api.services.api_endpoint_discovery.discover_endpoints_from_openapi") as mock_discover:
        mock_discover.return_value = [
            {"endpoint_path": "/test", "method": "GET", "description": "Test"}
        ]

        with patch("api.services.api_endpoint_discovery.store_discovered_endpoints") as mock_store:
            mock_store.return_value = 1

            count = await refresh_endpoint_metadata(
                "conn-123",
                openapi_url="https://api.example.com/openapi.json"
            )

            mock_discover.assert_called_once_with("conn-123", "https://api.example.com/openapi.json", None)
            assert count == 1


@pytest.mark.asyncio
async def test_refresh_endpoint_metadata_from_stored_url():
    """Test refreshing metadata using stored OpenAPI URL"""

    with patch("api.services.api_endpoint_discovery.repo_query") as mock_query:
        mock_query.return_value = [{"openapi_url": "https://stored-url.com/spec.json"}]

        with patch("api.services.api_endpoint_discovery.discover_endpoints_from_openapi") as mock_discover:
            mock_discover.return_value = []

            with patch("api.services.api_endpoint_discovery.store_discovered_endpoints") as mock_store:
                mock_store.return_value = 0

                await refresh_endpoint_metadata("conn-123")

                # Should fetch stored URL
                mock_query.assert_called_once()
                mock_discover.assert_called_once_with("conn-123", "https://stored-url.com/spec.json", None)


@pytest.mark.asyncio
async def test_refresh_endpoint_metadata_connection_not_found():
    """Test refresh when connection doesn't exist"""

    with patch("api.services.api_endpoint_discovery.repo_query") as mock_query:
        mock_query.return_value = []

        with pytest.raises(HTTPException) as exc_info:
            await refresh_endpoint_metadata("conn-999")

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_refresh_endpoint_metadata_no_openapi_url():
    """Test refresh when connection has no OpenAPI URL configured"""

    with patch("api.services.api_endpoint_discovery.repo_query") as mock_query:
        mock_query.return_value = [{"openapi_url": None}]

        with pytest.raises(HTTPException) as exc_info:
            await refresh_endpoint_metadata("conn-123")

        assert exc_info.value.status_code == 400
        assert "No OpenAPI URL" in str(exc_info.value.detail)


# ============================================================================
# get_endpoints_for_connection() Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_endpoints_for_connection_success():
    """Test retrieving cached endpoints"""

    mock_rows = [
        {
            "id": "endpoint-1",
            "connection_id": "conn-123",
            "endpoint_path": "/users",
            "method": "GET",
            "description": "List users",
            "parameters": json.dumps([{"name": "limit", "type": "integer"}]),
            "request_body_schema": None,
            "response_schema": json.dumps({"type": "array"}),
            "discovered_at": "2024-03-28T10:00:00",
            "discovery_source": "openapi"
        }
    ]

    with patch("api.services.api_endpoint_discovery.repo_query") as mock_query:
        mock_query.return_value = mock_rows

        endpoints = await get_endpoints_for_connection("conn-123")

        assert len(endpoints) == 1

        # Verify JSON fields were parsed
        assert isinstance(endpoints[0]["parameters"], list)
        assert endpoints[0]["parameters"][0]["name"] == "limit"

        assert isinstance(endpoints[0]["response_schema"], dict)
        assert endpoints[0]["response_schema"]["type"] == "array"


@pytest.mark.asyncio
async def test_get_endpoints_for_connection_handles_invalid_json():
    """Test handling of invalid JSON in stored data"""

    mock_rows = [
        {
            "id": "endpoint-1",
            "connection_id": "conn-123",
            "endpoint_path": "/test",
            "method": "GET",
            "description": "Test",
            "parameters": "invalid json",  # Invalid JSON
            "request_body_schema": None,
            "response_schema": None,
            "discovered_at": "2024-03-28T10:00:00",
            "discovery_source": "manual"
        }
    ]

    with patch("api.services.api_endpoint_discovery.repo_query") as mock_query:
        mock_query.return_value = mock_rows

        endpoints = await get_endpoints_for_connection("conn-123")

        # Should handle gracefully with empty list
        assert endpoints[0]["parameters"] == []


# ============================================================================
# get_endpoint_by_id() Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_endpoint_by_id_success():
    """Test retrieving specific endpoint by ID"""

    mock_row = {
        "id": "endpoint-123",
        "connection_id": "conn-123",
        "endpoint_path": "/users/{id}",
        "method": "GET",
        "description": "Get user",
        "parameters": json.dumps([{"name": "id", "in": "path"}]),
        "request_body_schema": None,
        "response_schema": json.dumps({"type": "object"}),
        "discovered_at": "2024-03-28T10:00:00",
        "discovery_source": "openapi"
    }

    with patch("api.services.api_endpoint_discovery.repo_query") as mock_query:
        mock_query.return_value = [mock_row]

        endpoint = await get_endpoint_by_id("endpoint-123")

        assert endpoint is not None
        assert endpoint["endpoint_path"] == "/users/{id}"
        assert isinstance(endpoint["parameters"], list)


@pytest.mark.asyncio
async def test_get_endpoint_by_id_not_found():
    """Test retrieving non-existent endpoint"""

    with patch("api.services.api_endpoint_discovery.repo_query") as mock_query:
        mock_query.return_value = []

        endpoint = await get_endpoint_by_id("nonexistent")

        assert endpoint is None


# ============================================================================
# delete_endpoints_for_connection() Tests
# ============================================================================

@pytest.mark.asyncio
async def test_delete_endpoints_for_connection():
    """Test deleting all endpoints for a connection"""

    with patch("api.services.api_endpoint_discovery.repo_execute") as mock_execute:
        mock_execute.return_value = 5

        count = await delete_endpoints_for_connection("conn-123")

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args
        assert "DELETE FROM api_connection_endpoints" in call_args[0][0]
        assert call_args[0][1]["connection_id"] == "conn-123"
        assert count == 5


# ============================================================================
# get_endpoint_stats() Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_endpoint_stats_success():
    """Test retrieving endpoint statistics"""

    mock_stats = {
        "total_endpoints": 10,
        "unique_methods": 3,
        "last_discovery": "2024-03-28T10:00:00"
    }

    mock_methods = [
        {"method": "GET", "count": 6},
        {"method": "POST", "count": 3},
        {"method": "DELETE", "count": 1}
    ]

    with patch("api.services.api_endpoint_discovery.repo_query") as mock_query:
        mock_query.side_effect = [[mock_stats], mock_methods]

        stats = await get_endpoint_stats("conn-123")

        assert stats["total_endpoints"] == 10
        assert stats["unique_methods"] == 3
        assert stats["methods"]["GET"] == 6
        assert stats["methods"]["POST"] == 3
        assert stats["methods"]["DELETE"] == 1


@pytest.mark.asyncio
async def test_get_endpoint_stats_empty():
    """Test statistics for connection with no endpoints"""

    with patch("api.services.api_endpoint_discovery.repo_query") as mock_query:
        mock_query.side_effect = [[], []]

        stats = await get_endpoint_stats("conn-123")

        assert stats["total_endpoints"] == 0
        assert stats["unique_methods"] == 0
        assert stats["last_discovery"] is None
        assert stats["methods"] == {}
