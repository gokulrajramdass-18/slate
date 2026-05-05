"""
API Endpoint Discovery Service

Discovers API endpoints from OpenAPI/Swagger specifications or manual input.
Stores endpoint metadata in the database for tool generation and API exploration.
"""

import json
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

import httpx
from fastapi import HTTPException, status

from open_notebook.database.repository import repo_query, repo_create, repo_execute
from api.services.http_client import http_client_manager

logger = logging.getLogger(__name__)

# Constants
MAX_SPEC_SIZE = 5 * 1024 * 1024  # 5MB
SPEC_TIMEOUT = 30.0  # seconds
MAX_ENDPOINTS = 100


# ============================================================================
# OpenAPI/Swagger Parsing
# ============================================================================

async def discover_endpoints_from_openapi(
    connection_id: str,
    openapi_url: str,
    auth_config: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Discover endpoints from an OpenAPI 3.x or Swagger 2.x specification.

    Args:
        connection_id: API connection ID
        openapi_url: URL to OpenAPI/Swagger spec (JSON or YAML)
        auth_config: Optional auth config if spec endpoint requires authentication

    Returns:
        List of endpoint dictionaries with metadata

    Raises:
        HTTPException: If spec cannot be fetched or parsed
    """
    logger.info(f"Fetching OpenAPI spec from {openapi_url}")

    # Fetch spec with timeout and size limit
    try:
        headers = {}
        if auth_config:
            # Add authentication if spec endpoint requires it
            if auth_config.get("type") == "bearer" and "token" in auth_config:
                headers["Authorization"] = f"Bearer {auth_config['token']}"
            elif auth_config.get("type") == "api_key":
                if auth_config.get("location") == "header":
                    headers[auth_config.get("key", "X-API-Key")] = auth_config.get("value", "")

        client = http_client_manager.get_client()
        response = await client.get(openapi_url, headers=headers, follow_redirects=True, timeout=SPEC_TIMEOUT)
        response.raise_for_status()

        # Check content size
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > MAX_SPEC_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"OpenAPI spec too large (max {MAX_SPEC_SIZE / 1024 / 1024}MB)"
            )

        # Parse JSON or YAML
        content_type = response.headers.get("content-type", "")
        if "json" in content_type:
            spec = response.json()
        elif "yaml" in content_type or "yml" in content_type:
            # Try to parse as YAML, fall back to JSON
            try:
                import yaml
                spec = yaml.safe_load(response.text)
            except ImportError:
                logger.warning("PyYAML not installed, trying JSON parse")
                spec = response.json()
        else:
            # Try JSON first, then YAML
            try:
                spec = response.json()
            except json.JSONDecodeError:
                try:
                    import yaml
                    spec = yaml.safe_load(response.text)
                except Exception as e:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Could not parse OpenAPI spec: {str(e)}"
                    )

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail=f"Timeout fetching OpenAPI spec (max {SPEC_TIMEOUT}s)"
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch OpenAPI spec: HTTP {e.response.status_code}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error fetching OpenAPI spec: {str(e)}"
        )

    # Parse spec based on version
    if not isinstance(spec, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OpenAPI spec format"
        )

    # Detect version
    openapi_version = spec.get("openapi", "")
    swagger_version = spec.get("swagger", "")

    if openapi_version.startswith("3."):
        logger.info(f"Parsing OpenAPI 3.x spec (version {openapi_version})")
        endpoints = _parse_openapi_3(spec)
    elif swagger_version == "2.0":
        logger.info("Parsing Swagger 2.0 spec")
        endpoints = _parse_swagger_2(spec)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported spec version (OpenAPI: {openapi_version}, Swagger: {swagger_version})"
        )

    # Limit endpoints
    if len(endpoints) > MAX_ENDPOINTS:
        logger.warning(f"Limiting endpoints from {len(endpoints)} to {MAX_ENDPOINTS}")
        endpoints = endpoints[:MAX_ENDPOINTS]

    # Add connection_id to each endpoint
    for endpoint in endpoints:
        endpoint["connection_id"] = connection_id

    logger.info(f"Discovered {len(endpoints)} endpoints from OpenAPI spec")
    return endpoints


def _parse_openapi_3(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse OpenAPI 3.x specification.

    Args:
        spec: OpenAPI 3.x spec dictionary

    Returns:
        List of endpoint dictionaries
    """
    endpoints = []
    paths = spec.get("paths", {})

    for path, path_item in paths.items():
        # Path-level parameters
        path_parameters = path_item.get("parameters", [])

        for method in ["get", "post", "put", "delete", "patch", "options", "head", "trace"]:
            if method not in path_item:
                continue

            operation = path_item[method]

            # Extract endpoint metadata
            endpoint = {
                "endpoint_path": path,
                "method": method.upper(),
                "description": operation.get("summary") or operation.get("description"),
                "parameters": [],
                "request_body_schema": None,
                "response_schema": None,
            }

            # Parameters (combine path-level and operation-level)
            all_parameters = path_parameters + operation.get("parameters", [])
            for param in all_parameters:
                # Dereference $ref if present
                if "$ref" in param:
                    # Skip for simplicity (would need to resolve references)
                    continue

                param_info = {
                    "name": param.get("name"),
                    "type": _get_openapi3_param_type(param),
                    "in": param.get("in"),  # path, query, header, cookie
                    "required": param.get("required", False),
                    "description": param.get("description"),
                }
                endpoint["parameters"].append(param_info)

            # Request body
            request_body = operation.get("requestBody")
            if request_body:
                content = request_body.get("content", {})
                # Get first content type (usually application/json)
                for content_type, media_type in content.items():
                    schema = media_type.get("schema", {})
                    endpoint["request_body_schema"] = json.dumps(schema)
                    break

            # Response schema (use 200 response)
            responses = operation.get("responses", {})
            success_response = responses.get("200") or responses.get("201")
            if success_response:
                content = success_response.get("content", {})
                for content_type, media_type in content.items():
                    schema = media_type.get("schema", {})
                    endpoint["response_schema"] = json.dumps(schema)
                    break

            # Convert parameters to JSON string
            endpoint["parameters"] = json.dumps(endpoint["parameters"])

            endpoints.append(endpoint)

    return endpoints


def _get_openapi3_param_type(param: Dict[str, Any]) -> str:
    """Extract parameter type from OpenAPI 3.x parameter object."""
    schema = param.get("schema", {})
    return schema.get("type", "string")


def _parse_swagger_2(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse Swagger 2.0 specification.

    Args:
        spec: Swagger 2.0 spec dictionary

    Returns:
        List of endpoint dictionaries
    """
    endpoints = []
    paths = spec.get("paths", {})

    for path, path_item in paths.items():
        # Path-level parameters
        path_parameters = path_item.get("parameters", [])

        for method in ["get", "post", "put", "delete", "patch", "options", "head"]:
            if method not in path_item:
                continue

            operation = path_item[method]

            # Extract endpoint metadata
            endpoint = {
                "endpoint_path": path,
                "method": method.upper(),
                "description": operation.get("summary") or operation.get("description"),
                "parameters": [],
                "request_body_schema": None,
                "response_schema": None,
            }

            # Parameters
            all_parameters = path_parameters + operation.get("parameters", [])
            for param in all_parameters:
                # Dereference $ref if present
                if "$ref" in param:
                    continue

                param_info = {
                    "name": param.get("name"),
                    "type": param.get("type", "string"),
                    "in": param.get("in"),  # path, query, header, body, formData
                    "required": param.get("required", False),
                    "description": param.get("description"),
                }

                # Body parameters have schema
                if param.get("in") == "body":
                    schema = param.get("schema", {})
                    endpoint["request_body_schema"] = json.dumps(schema)
                else:
                    endpoint["parameters"].append(param_info)

            # Response schema (use 200 response)
            responses = operation.get("responses", {})
            success_response = responses.get("200") or responses.get("201")
            if success_response:
                schema = success_response.get("schema", {})
                if schema:
                    endpoint["response_schema"] = json.dumps(schema)

            # Convert parameters to JSON string
            endpoint["parameters"] = json.dumps(endpoint["parameters"])

            endpoints.append(endpoint)

    return endpoints


# ============================================================================
# Manual Endpoint Discovery
# ============================================================================

async def discover_endpoints_manual(
    connection_id: str,
    endpoints: List[Dict[str, str]]
) -> List[Dict[str, Any]]:
    """
    Process manually provided endpoint definitions.

    Args:
        connection_id: API connection ID
        endpoints: List of endpoint dicts with path, method, description

    Returns:
        List of formatted endpoint dictionaries

    Example input:
        [
            {
                "path": "/users",
                "method": "GET",
                "description": "List all users"
            },
            {
                "path": "/users/{id}",
                "method": "GET",
                "description": "Get user by ID",
                "parameters": [{"name": "id", "type": "string", "in": "path", "required": true}]
            }
        ]
    """
    logger.info(f"Processing {len(endpoints)} manual endpoints for connection {connection_id}")

    formatted_endpoints = []

    for endpoint in endpoints:
        # Validate required fields
        if "path" not in endpoint or "method" not in endpoint:
            logger.warning(f"Skipping endpoint missing path or method: {endpoint}")
            continue

        formatted = {
            "connection_id": connection_id,
            "endpoint_path": endpoint["path"],
            "method": endpoint["method"].upper(),
            "description": endpoint.get("description"),
            "parameters": json.dumps(endpoint.get("parameters", [])),
            "request_body_schema": json.dumps(endpoint.get("request_body_schema")) if endpoint.get("request_body_schema") else None,
            "response_schema": json.dumps(endpoint.get("response_schema")) if endpoint.get("response_schema") else None,
        }

        formatted_endpoints.append(formatted)

    logger.info(f"Formatted {len(formatted_endpoints)} manual endpoints")
    return formatted_endpoints


# ============================================================================
# Database Operations
# ============================================================================

async def store_discovered_endpoints(
    connection_id: str,
    endpoints: List[Dict[str, Any]]
) -> int:
    """
    Store discovered endpoints in the database.

    Deletes existing endpoints for this connection and inserts new ones.

    Args:
        connection_id: API connection ID
        endpoints: List of endpoint dictionaries

    Returns:
        Number of endpoints stored
    """
    if not endpoints:
        return 0

    logger.info(f"Storing {len(endpoints)} endpoints for connection {connection_id}")

    # Delete existing endpoints for this connection
    delete_sql = "DELETE FROM api_connection_endpoints WHERE connection_id = :connection_id"
    await repo_execute(delete_sql, {"connection_id": connection_id})

    # Insert new endpoints
    now = datetime.utcnow().isoformat()
    stored_count = 0

    for endpoint in endpoints:
        try:
            data = {
                "id": str(uuid.uuid4()),
                "connection_id": connection_id,
                "endpoint_path": endpoint["endpoint_path"],
                "method": endpoint["method"],
                "description": endpoint.get("description"),
                "parameters": endpoint.get("parameters"),
                "request_body_schema": endpoint.get("request_body_schema"),
                "response_schema": endpoint.get("response_schema"),
                "discovered_at": now,
                "discovery_source": endpoint.get("discovery_source", "openapi"),
            }

            await repo_create("api_connection_endpoints", data)
            stored_count += 1

        except Exception as e:
            logger.error(f"Failed to store endpoint {endpoint.get('endpoint_path')}: {e}")
            continue

    logger.info(f"Successfully stored {stored_count} endpoints")
    return stored_count


async def refresh_endpoint_metadata(
    connection_id: str,
    openapi_url: Optional[str] = None,
    auth_config: Optional[Dict[str, Any]] = None
) -> int:
    """
    Refresh endpoint metadata by re-fetching OpenAPI spec.

    Args:
        connection_id: API connection ID
        openapi_url: URL to OpenAPI spec (if None, use stored URL)
        auth_config: Optional auth config for spec endpoint

    Returns:
        Number of endpoints refreshed

    Raises:
        HTTPException: If connection not found or spec cannot be fetched
    """
    logger.info(f"Refreshing endpoint metadata for connection {connection_id}")

    # Get stored openapi_url if not provided
    if not openapi_url:
        sql = "SELECT openapi_url FROM api_connections WHERE id = :id"
        results = await repo_query(sql, {"id": connection_id})

        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"API connection {connection_id} not found"
            )

        openapi_url = results[0].get("openapi_url")
        if not openapi_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No OpenAPI URL configured for this connection"
            )

    # Discover endpoints
    endpoints = await discover_endpoints_from_openapi(connection_id, openapi_url, auth_config)

    # Store in database
    count = await store_discovered_endpoints(connection_id, endpoints)

    logger.info(f"Refreshed {count} endpoints for connection {connection_id}")
    return count


async def get_endpoints_for_connection(connection_id: str) -> List[Dict[str, Any]]:
    """
    Get cached endpoint metadata for a connection.

    Args:
        connection_id: API connection ID

    Returns:
        List of endpoint dictionaries with metadata
    """
    sql = """
        SELECT
            id,
            connection_id,
            endpoint_path,
            method,
            description,
            parameters,
            request_body_schema,
            response_schema,
            discovered_at,
            discovery_source
        FROM api_connection_endpoints
        WHERE connection_id = :connection_id
        ORDER BY endpoint_path, method
    """

    results = await repo_query(sql, {"connection_id": connection_id})

    # Parse JSON fields
    for result in results:
        if result.get("parameters"):
            try:
                result["parameters"] = json.loads(result["parameters"])
            except json.JSONDecodeError:
                result["parameters"] = []

        if result.get("request_body_schema"):
            try:
                result["request_body_schema"] = json.loads(result["request_body_schema"])
            except json.JSONDecodeError:
                result["request_body_schema"] = None

        if result.get("response_schema"):
            try:
                result["response_schema"] = json.loads(result["response_schema"])
            except json.JSONDecodeError:
                result["response_schema"] = None

    return results


async def get_endpoint_by_id(endpoint_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a specific endpoint by ID.

    Args:
        endpoint_id: Endpoint ID

    Returns:
        Endpoint dictionary or None if not found
    """
    sql = """
        SELECT
            id,
            connection_id,
            endpoint_path,
            method,
            description,
            parameters,
            request_body_schema,
            response_schema,
            discovered_at,
            discovery_source
        FROM api_connection_endpoints
        WHERE id = :id
    """

    results = await repo_query(sql, {"id": endpoint_id})

    if not results:
        return None

    endpoint = results[0]

    # Parse JSON fields
    if endpoint.get("parameters"):
        try:
            endpoint["parameters"] = json.loads(endpoint["parameters"])
        except json.JSONDecodeError:
            endpoint["parameters"] = []

    if endpoint.get("request_body_schema"):
        try:
            endpoint["request_body_schema"] = json.loads(endpoint["request_body_schema"])
        except json.JSONDecodeError:
            endpoint["request_body_schema"] = None

    if endpoint.get("response_schema"):
        try:
            endpoint["response_schema"] = json.loads(endpoint["response_schema"])
        except json.JSONDecodeError:
            endpoint["response_schema"] = None

    return endpoint


async def delete_endpoints_for_connection(connection_id: str) -> int:
    """
    Delete all endpoints for a connection.

    Args:
        connection_id: API connection ID

    Returns:
        Number of endpoints deleted
    """
    sql = "DELETE FROM api_connection_endpoints WHERE connection_id = :connection_id"
    return await repo_execute(sql, {"connection_id": connection_id})


# ============================================================================
# Statistics
# ============================================================================

async def get_endpoint_stats(connection_id: str) -> Dict[str, Any]:
    """
    Get endpoint statistics for a connection.

    Args:
        connection_id: API connection ID

    Returns:
        Dictionary with endpoint statistics
    """
    sql = """
        SELECT
            COUNT(*) as total_endpoints,
            COUNT(DISTINCT method) as unique_methods,
            MAX(discovered_at) as last_discovery
        FROM api_connection_endpoints
        WHERE connection_id = :connection_id
    """

    results = await repo_query(sql, {"connection_id": connection_id})

    if not results:
        return {
            "total_endpoints": 0,
            "unique_methods": 0,
            "last_discovery": None,
            "methods": {}
        }

    stats = results[0]

    # Get method breakdown
    method_sql = """
        SELECT method, COUNT(*) as count
        FROM api_connection_endpoints
        WHERE connection_id = :connection_id
        GROUP BY method
    """

    method_results = await repo_query(method_sql, {"connection_id": connection_id})
    methods = {row["method"]: row["count"] for row in method_results}

    return {
        "total_endpoints": stats["total_endpoints"],
        "unique_methods": stats["unique_methods"],
        "last_discovery": stats["last_discovery"],
        "methods": methods
    }
