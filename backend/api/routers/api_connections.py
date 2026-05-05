"""
API Connections Router - Manage reusable API connection configurations
"""
from fastapi import APIRouter, HTTPException, status
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import json
import uuid

from open_notebook.database.repository import (
    repo_query,
    repo_create,
    repo_update,
    repo_delete,
)
from open_notebook.config import get_encryption_key
from cryptography.fernet import Fernet
import base64
from api.services.api_endpoint_discovery import (
    discover_endpoints_from_openapi,
    discover_endpoints_manual,
    store_discovered_endpoints,
    get_endpoints_for_connection,
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/api-connections", tags=["API Connections"])


# ============================================================================
# Models
# ============================================================================

class APIConnectionCreate(BaseModel):
    """Create API connection"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    endpoint: str = Field(..., description="API endpoint URL")
    auth_type: str = Field(..., description="Authentication type")
    auth_config: Optional[Dict[str, Any]] = Field(None, description="Authentication configuration")
    headers: Optional[Dict[str, str]] = Field(default_factory=dict)
    method: str = Field(default="GET")
    query_params: Optional[Dict[str, Any]] = Field(default_factory=dict)
    request_body: Optional[Dict[str, Any]] = None
    data_path: Optional[str] = Field(None, description="JSONPath to data array")
    id_field: str = Field(default="id")
    content_fields: List[str] = Field(default_factory=list)
    openapi_url: Optional[str] = Field(None, description="OpenAPI specification URL")
    endpoints: Optional[List[Dict[str, str]]] = Field(None, description="Manual endpoint list")


class APIConnectionUpdate(BaseModel):
    """Update API connection"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    endpoint: Optional[str] = None
    auth_type: Optional[str] = None
    auth_config: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None
    method: Optional[str] = None
    query_params: Optional[Dict[str, Any]] = None
    request_body: Optional[Dict[str, Any]] = None
    data_path: Optional[str] = None
    id_field: Optional[str] = None
    content_fields: Optional[List[str]] = None


class APIConnectionResponse(BaseModel):
    """API connection response"""
    id: str
    name: str
    description: Optional[str]
    endpoint: str
    auth_type: str
    headers: Dict[str, str]
    method: str
    query_params: Dict[str, Any]
    request_body: Optional[Dict[str, Any]]
    data_path: Optional[str]
    id_field: str
    content_fields: List[str]
    created: str
    updated: str
    last_tested: Optional[str]
    test_status: Optional[str]
    test_message: Optional[str]

    class Config:
        from_attributes = True


class APIConnectionTestResponse(BaseModel):
    """Test connection response"""
    success: bool
    message: str
    preview: Optional[Any] = None  # Can be list or dict
    record_count: Optional[int] = None


# ============================================================================
# Helper Functions
# ============================================================================

def encrypt_auth_config(auth_config: Optional[Dict[str, Any]]) -> Optional[str]:
    """Encrypt authentication configuration"""
    if not auth_config:
        return None

    key = get_encryption_key()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Encryption key not configured"
        )

    fernet = Fernet(key.encode())
    json_str = json.dumps(auth_config)
    encrypted = fernet.encrypt(json_str.encode())
    return base64.b64encode(encrypted).decode()


def decrypt_auth_config(encrypted: Optional[str]) -> Optional[Dict[str, Any]]:
    """Decrypt authentication configuration"""
    if not encrypted:
        return None

    key = get_encryption_key()
    if not key:
        return None

    try:
        fernet = Fernet(key.encode())
        encrypted_bytes = base64.b64decode(encrypted.encode())
        decrypted = fernet.decrypt(encrypted_bytes)
        return json.loads(decrypted.decode())
    except Exception:
        return None


def format_connection(row: dict) -> APIConnectionResponse:
    """Format database row to response model"""
    return APIConnectionResponse(
        id=row["id"],
        name=row["name"],
        description=row.get("description"),
        endpoint=row["endpoint"],
        auth_type=row["auth_type"],
        headers=json.loads(row.get("headers") or "{}"),
        method=row.get("method", "GET"),
        query_params=json.loads(row.get("query_params") or "{}"),
        request_body=json.loads(row["request_body"]) if row.get("request_body") else None,
        data_path=row.get("data_path"),
        id_field=row.get("id_field", "id"),
        content_fields=json.loads(row.get("content_fields") or "[]"),
        created=row["created"],
        updated=row["updated"],
        last_tested=row.get("last_tested"),
        test_status=row.get("test_status"),
        test_message=row.get("test_message"),
    )


# ============================================================================
# Endpoints
# ============================================================================

@router.get("", response_model=List[APIConnectionResponse])
async def list_connections():
    """List all API connections"""
    sql = """
        SELECT * FROM api_connections
        ORDER BY created DESC
    """
    results = await repo_query(sql, {})
    return [format_connection(row) for row in results]


@router.get("/{connection_id}", response_model=APIConnectionResponse)
async def get_connection(connection_id: str):
    """Get a specific API connection"""
    sql = "SELECT * FROM api_connections WHERE id = :id"
    results = await repo_query(sql, {"id": connection_id})

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API connection {connection_id} not found"
        )

    return format_connection(results[0])


@router.post("", response_model=APIConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_connection(conn: APIConnectionCreate):
    """Create a new API connection"""
    connection_id = str(uuid.uuid4())

    # Encrypt auth config
    auth_encrypted = encrypt_auth_config(conn.auth_config)

    data = {
        "id": connection_id,
        "name": conn.name,
        "description": conn.description,
        "endpoint": conn.endpoint,
        "auth_type": conn.auth_type,
        "auth_config_encrypted": auth_encrypted,
        "headers": json.dumps(conn.headers),
        "method": conn.method,
        "query_params": json.dumps(conn.query_params),
        "request_body": json.dumps(conn.request_body) if conn.request_body else None,
        "data_path": conn.data_path,
        "id_field": conn.id_field,
        "content_fields": json.dumps(conn.content_fields),
    }

    await repo_create("api_connections", data)

    # Attempt endpoint discovery if provided
    if conn.openapi_url or conn.endpoints:
        try:
            logger.info(f"Attempting endpoint discovery for connection {connection_id}")

            discovered = None
            if conn.openapi_url:
                logger.info(f"Discovering endpoints from OpenAPI spec: {conn.openapi_url}")
                discovered = await discover_endpoints_from_openapi(conn.openapi_url)
            elif conn.endpoints:
                logger.info(f"Discovering endpoints from manual list: {len(conn.endpoints)} endpoints")
                discovered = await discover_endpoints_manual(conn.endpoints)

            if discovered:
                await store_discovered_endpoints(connection_id, discovered)
                logger.info(f"Successfully discovered and stored {len(discovered)} endpoints for connection {connection_id}")
            else:
                logger.warning(f"No endpoints discovered for connection {connection_id}")

        except Exception as e:
            logger.warning(f"Endpoint discovery failed for connection {connection_id}: {str(e)}")
            # Don't fail connection creation if discovery fails

    # Fetch created connection
    return await get_connection(connection_id)


@router.put("/{connection_id}", response_model=APIConnectionResponse)
async def update_connection(connection_id: str, conn: APIConnectionUpdate):
    """Update an API connection"""
    # Verify connection exists
    existing = await get_connection(connection_id)

    # Build update data
    data = {}
    if conn.name is not None:
        data["name"] = conn.name
    if conn.description is not None:
        data["description"] = conn.description
    if conn.endpoint is not None:
        data["endpoint"] = conn.endpoint
    if conn.auth_type is not None:
        data["auth_type"] = conn.auth_type
    if conn.auth_config is not None:
        data["auth_config_encrypted"] = encrypt_auth_config(conn.auth_config)
    if conn.headers is not None:
        data["headers"] = json.dumps(conn.headers)
    if conn.method is not None:
        data["method"] = conn.method
    if conn.query_params is not None:
        data["query_params"] = json.dumps(conn.query_params)
    if conn.request_body is not None:
        data["request_body"] = json.dumps(conn.request_body)
    if conn.data_path is not None:
        data["data_path"] = conn.data_path
    if conn.id_field is not None:
        data["id_field"] = conn.id_field
    if conn.content_fields is not None:
        data["content_fields"] = json.dumps(conn.content_fields)

    data["updated"] = datetime.utcnow().isoformat()

    await repo_update("api_connections", connection_id, data)

    return await get_connection(connection_id)


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(connection_id: str):
    """Delete an API connection"""
    # Verify connection exists
    await get_connection(connection_id)

    await repo_delete("api_connections", connection_id)


@router.post("/{connection_id}/test", response_model=APIConnectionTestResponse)
async def test_connection(connection_id: str):
    """Test an API connection"""
    # Fetch connection
    sql = "SELECT * FROM api_connections WHERE id = :id"
    results = await repo_query(sql, {"id": connection_id})

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API connection {connection_id} not found"
        )

    conn = results[0]

    # Decrypt auth config
    auth_config = decrypt_auth_config(conn.get("auth_config_encrypted"))

    # Build test request
    import httpx

    headers = json.loads(conn.get("headers") or "{}")
    query_params = json.loads(conn.get("query_params") or "{}")
    request_body = json.loads(conn["request_body"]) if conn.get("request_body") else None

    # Add authentication
    if conn["auth_type"] == "bearer" and auth_config and "token" in auth_config:
        headers["Authorization"] = f"Bearer {auth_config['token']}"
    elif conn["auth_type"] == "api_key" and auth_config:
        if auth_config.get("location") == "header":
            headers[auth_config.get("key", "X-API-Key")] = auth_config.get("value", "")
        elif auth_config.get("location") == "query":
            query_params[auth_config.get("key", "api_key")] = auth_config.get("value", "")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if conn.get("method", "GET") == "GET":
                response = await client.get(
                    conn["endpoint"],
                    headers=headers,
                    params=query_params
                )
            else:
                response = await client.post(
                    conn["endpoint"],
                    headers=headers,
                    params=query_params,
                    json=request_body
                )

        response.raise_for_status()

        # Parse response
        data = response.json()

        # Extract data using data_path if specified
        if conn.get("data_path"):
            # Simple dot notation support (e.g., "data.items")
            parts = conn["data_path"].split(".")
            for part in parts:
                data = data.get(part, [])

        record_count = len(data) if isinstance(data, list) else 1

        # Update test status
        await repo_update("api_connections", connection_id, {
            "last_tested": datetime.utcnow().isoformat(),
            "test_status": "success",
            "test_message": f"Successfully connected. Found {record_count} records.",
        })

        # Return preview (first 5 items)
        preview = data[:5] if isinstance(data, list) else data

        return APIConnectionTestResponse(
            success=True,
            message=f"Successfully connected. Found {record_count} records.",
            preview=preview,
            record_count=record_count
        )

    except Exception as e:
        # Update test status
        await repo_update("api_connections", connection_id, {
            "last_tested": datetime.utcnow().isoformat(),
            "test_status": "failed",
            "test_message": str(e),
        })

        return APIConnectionTestResponse(
            success=False,
            message=f"Connection test failed: {str(e)}"
        )


@router.post("/test", response_model=APIConnectionTestResponse)
async def test_config(config: APIConnectionCreate):
    """Test an API connection config without saving"""
    # Similar to test_connection but without saving to database
    import httpx

    headers = config.headers or {}
    query_params = config.query_params or {}
    request_body = config.request_body

    # Add authentication
    if config.auth_type == "bearer" and config.auth_config and "token" in config.auth_config:
        headers["Authorization"] = f"Bearer {config.auth_config['token']}"
    elif config.auth_type == "api_key" and config.auth_config:
        if config.auth_config.get("location") == "header":
            headers[config.auth_config.get("key", "X-API-Key")] = config.auth_config.get("value", "")
        elif config.auth_config.get("location") == "query":
            query_params[config.auth_config.get("key", "api_key")] = config.auth_config.get("value", "")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if config.method == "GET":
                response = await client.get(
                    config.endpoint,
                    headers=headers,
                    params=query_params
                )
            else:
                response = await client.post(
                    config.endpoint,
                    headers=headers,
                    params=query_params,
                    json=request_body
                )

        response.raise_for_status()

        # Parse response
        data = response.json()

        # Extract data using data_path if specified
        if config.data_path:
            parts = config.data_path.split(".")
            for part in parts:
                data = data.get(part, [])

        record_count = len(data) if isinstance(data, list) else 1
        preview = data[:5] if isinstance(data, list) else data

        return APIConnectionTestResponse(
            success=True,
            message=f"Successfully connected. Found {record_count} records.",
            preview=preview,
            record_count=record_count
        )

    except Exception as e:
        return APIConnectionTestResponse(
            success=False,
            message=f"Connection test failed: {str(e)}"
        )


@router.get("/{connection_id}/preview", response_model=Dict[str, Any])
async def get_preview(connection_id: str):
    """Get a preview of data from the API connection"""
    test_result = await test_connection(connection_id)

    if not test_result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=test_result.message
        )

    return {
        "success": True,
        "data": test_result.preview,
        "record_count": test_result.record_count
    }


@router.post("/{connection_id}/discover-endpoints")
async def discover_endpoints(
    connection_id: str,
    discovery_config: Optional[Dict[str, Any]] = None
):
    """Manually trigger endpoint discovery for a connection"""
    # Verify connection exists
    await get_connection(connection_id)

    if not discovery_config:
        discovery_config = {}

    openapi_url = discovery_config.get("openapi_url")
    endpoints = discovery_config.get("endpoints")

    if not openapi_url and not endpoints:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'openapi_url' or 'endpoints' must be provided"
        )

    try:
        discovered = None
        if openapi_url:
            logger.info(f"Discovering endpoints from OpenAPI spec: {openapi_url}")
            discovered = await discover_endpoints_from_openapi(openapi_url)
        elif endpoints:
            logger.info(f"Discovering endpoints from manual list: {len(endpoints)} endpoints")
            discovered = await discover_endpoints_manual(endpoints)

        if discovered:
            await store_discovered_endpoints(connection_id, discovered)
            discovered_at = datetime.utcnow().isoformat()
            logger.info(f"Successfully discovered and stored {len(discovered)} endpoints for connection {connection_id}")

            return {
                "success": True,
                "connection_id": connection_id,
                "endpoints_discovered": len(discovered),
                "discovered_at": discovered_at
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No endpoints discovered from the provided source"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Endpoint discovery failed for connection {connection_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Endpoint discovery failed: {str(e)}"
        )


@router.get("/{connection_id}/endpoints")
async def get_connection_endpoints(connection_id: str):
    """List all discovered endpoints for a connection"""
    # Verify connection exists
    await get_connection(connection_id)

    try:
        endpoints = await get_endpoints_for_connection(connection_id)

        return {
            "connection_id": connection_id,
            "endpoints": endpoints,
            "count": len(endpoints)
        }

    except Exception as e:
        logger.error(f"Failed to retrieve endpoints for connection {connection_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve endpoints: {str(e)}"
        )

