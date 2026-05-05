"""
API Key Management Router

Endpoints for creating and managing API keys for external integrations.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Header, status
from pydantic import BaseModel, Field

from open_notebook.domain.api_key import APIKey


router = APIRouter(prefix="/api/api-keys", tags=["API Keys"])


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateAPIKeyRequest(BaseModel):
    """Request model for creating an API key"""
    name: str = Field(..., max_length=100, description="Friendly name for the key")
    description: Optional[str] = Field(None, max_length=500, description="Purpose/usage description")
    scopes: List[str] = Field(
        ...,
        min_items=1,
        description="List of scopes (e.g., ['notifications:write', 'workflows:execute'])"
    )
    application_name: Optional[str] = Field(None, max_length=100, description="External application name")
    expires_in_days: Optional[int] = Field(
        None,
        ge=1,
        le=365,
        description="Expiration time in days (max 365)"
    )


class APIKeyResponse(BaseModel):
    """Response model for API key (without sensitive data)"""
    id: str
    name: str
    description: Optional[str]
    key_prefix: str
    scopes: List[str]
    owner_id: str
    application_name: Optional[str]
    last_used_at: Optional[str]
    usage_count: int
    is_active: bool
    expires_at: Optional[str]
    created_at: Optional[str]


class CreateAPIKeyResponse(BaseModel):
    """Response model for newly created API key (includes plain key)"""
    id: str
    name: str
    api_key: str  # Plain text key - only shown once!
    key_prefix: str
    scopes: List[str]
    application_name: Optional[str]
    expires_at: Optional[str]
    warning: str = "Store this API key securely. It will not be shown again."


class UsageLogResponse(BaseModel):
    """Response model for usage log"""
    id: str
    endpoint: str
    method: str
    status_code: int
    ip_address: Optional[str]
    timestamp: str
    error: Optional[str]


# ============================================================================
# Available Scopes
# ============================================================================

AVAILABLE_SCOPES = {
    "notifications:write": "Send notifications to users",
    "notifications:read": "Read user notifications",
    "workflows:execute": "Execute workflows",
    "workflows:read": "Read workflow definitions",
    "agents:execute": "Execute agents",
    "agents:read": "Read agent configurations",
}


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/scopes")
async def get_available_scopes():
    """
    Get list of available API scopes

    Returns all available scopes and their descriptions.
    """
    return {
        "scopes": [
            {"scope": scope, "description": desc}
            for scope, desc in AVAILABLE_SCOPES.items()
        ]
    }


@router.post("", response_model=CreateAPIKeyResponse, status_code=201)
async def create_api_key(
    request: CreateAPIKeyRequest,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """
    Create a new API key

    **Important:** The API key will only be shown once. Store it securely.

    **Available Scopes:**
    - `notifications:write` - Send notifications to users
    - `notifications:read` - Read user notifications
    - `workflows:execute` - Execute workflows
    - `workflows:read` - Read workflow definitions
    - `agents:execute` - Execute agents
    - `agents:read` - Read agent configurations
    """
    try:
        # Validate scopes
        invalid_scopes = [s for s in request.scopes if s not in AVAILABLE_SCOPES]
        if invalid_scopes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid scopes: {', '.join(invalid_scopes)}"
            )

        # Create API key
        api_key, plain_key = await APIKey.create(
            name=request.name,
            owner_id=x_user_id,
            scopes=request.scopes,
            description=request.description,
            application_name=request.application_name,
            expires_in_days=request.expires_in_days
        )

        return CreateAPIKeyResponse(
            id=api_key.id,
            name=api_key.name,
            api_key=plain_key,
            key_prefix=api_key.key_prefix,
            scopes=api_key.scopes,
            application_name=api_key.application_name,
            expires_at=api_key.expires_at.isoformat() if api_key.expires_at else None
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("", response_model=List[APIKeyResponse])
async def list_api_keys(
    x_user_id: str = Header(..., alias="X-User-ID"),
    include_inactive: bool = Query(False, description="Include revoked/inactive keys")
):
    """
    List all API keys for the current user

    Returns a list of API keys (without the actual key values).
    """
    try:
        api_keys = await APIKey.list_by_owner(x_user_id, include_inactive)
        return [APIKeyResponse(**key.to_dict()) for key in api_keys]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{api_key_id}", response_model=APIKeyResponse)
async def get_api_key(
    api_key_id: str,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """
    Get details of a specific API key

    Returns API key information without the actual key value.
    """
    try:
        api_key = await APIKey.get(api_key_id)

        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )

        # Verify ownership
        if api_key.owner_id != x_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this API key"
            )

        return APIKeyResponse(**api_key.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{api_key_id}/revoke")
async def revoke_api_key(
    api_key_id: str,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """
    Revoke (deactivate) an API key

    The key will no longer be able to authenticate API requests.
    """
    try:
        api_key = await APIKey.get(api_key_id)

        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )

        # Verify ownership
        if api_key.owner_id != x_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to revoke this API key"
            )

        await api_key.revoke()

        return {
            "message": "API key revoked successfully",
            "api_key_id": api_key_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{api_key_id}")
async def delete_api_key(
    api_key_id: str,
    x_user_id: str = Header(..., alias="X-User-ID")
):
    """
    Delete an API key permanently

    This action cannot be undone. All usage logs will also be deleted.
    """
    try:
        api_key = await APIKey.get(api_key_id)

        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )

        # Verify ownership
        if api_key.owner_id != x_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this API key"
            )

        await api_key.delete()

        return {
            "message": "API key deleted successfully",
            "api_key_id": api_key_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{api_key_id}/usage", response_model=List[UsageLogResponse])
async def get_api_key_usage(
    api_key_id: str,
    x_user_id: str = Header(..., alias="X-User-ID"),
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get usage logs for an API key

    Returns recent API calls made with this key.
    """
    try:
        api_key = await APIKey.get(api_key_id)

        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )

        # Verify ownership
        if api_key.owner_id != x_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this API key's usage"
            )

        # Get usage logs
        from open_notebook.database.repository import repo_query

        rows = await repo_query(
            """
            SELECT id, endpoint, method, status_code, ip_address, timestamp, error
            FROM api_key_usage_logs
            WHERE api_key_id = :api_key_id
            ORDER BY timestamp DESC
            LIMIT :limit
            """,
            {"api_key_id": api_key_id, "limit": limit}
        )

        return [
            UsageLogResponse(
                id=row["id"],
                endpoint=row["endpoint"],
                method=row["method"],
                status_code=row["status_code"],
                ip_address=row.get("ip_address"),
                timestamp=row["timestamp"],
                error=row.get("error")
            )
            for row in rows
        ]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
