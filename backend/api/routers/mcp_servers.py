"""
MCP Servers API Router

Provides REST API endpoints for managing MCP (Model Context Protocol) server
connections, including CRUD operations, connection testing, and capability discovery.

Per-user OAuth: OAuth-typed servers expose a per-user `current_user_status`
field on every response so the UI can render a separate Connect/Connected
state for each logged-in user even though the server config itself is shared.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from open_notebook.config import get_encryption_key
from open_notebook.database.repository import repo_query, repo_execute
from api.services.mcp_client import (
    MCPClientFactory,
    mcp_pool,
    SYSTEM_OAUTH_USER_ID,
    effective_token_user_id,
)
from api.dependencies.auth import get_current_active_user
from open_notebook.domain.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp-servers", tags=["MCP Servers"])


# ============================================================================
# Encryption Helpers
# ============================================================================

def encrypt_password(password: str) -> str:
    """Encrypt password using Fernet encryption"""
    from cryptography.fernet import Fernet
    import base64

    key = get_encryption_key()
    if not key:
        # If no encryption key set, store as-is (not recommended for production)
        return password

    fernet = Fernet(key.encode())
    encrypted = fernet.encrypt(password.encode())
    return base64.b64encode(encrypted).decode()


def decrypt_password(encrypted_password: str) -> str:
    """Decrypt password using Fernet encryption"""
    from cryptography.fernet import Fernet
    import base64

    key = get_encryption_key()
    if not key:
        # If no encryption key set, assume password is plain text
        return encrypted_password

    try:
        fernet = Fernet(key.encode())

        # Fix base64 padding if needed
        # Base64 strings must be a multiple of 4 characters
        padded = encrypted_password
        padding_needed = len(padded) % 4
        if padding_needed:
            padded += '=' * (4 - padding_needed)

        decrypted = fernet.decrypt(base64.b64decode(padded))
        return decrypted.decode()
    except Exception as e:
        logger.error(f"Failed to decrypt password: {e}")
        # Return as-is if decryption fails (could be plain text or corrupted)
        return encrypted_password


# ============================================================================
# Pydantic Models
# ============================================================================

class MCPServerCreate(BaseModel):
    """Request model for creating MCP server"""
    name: str = Field(..., min_length=1, max_length=255, description="Server name")
    description: Optional[str] = Field(None, description="Optional server description")
    protocol: Literal["stdio", "http"] = Field(..., description="Protocol type")

    # stdio fields
    command: Optional[str] = Field(None, description="Command to execute (stdio only)")
    args: Optional[List[str]] = Field(None, description="Command arguments (stdio only)")
    env_vars: Optional[dict] = Field(None, description="Environment variables (stdio only)")

    # HTTP fields
    url: Optional[str] = Field(None, description="Base URL (HTTP only)")
    headers: Optional[dict] = Field(None, description="HTTP headers (HTTP only)")
    auth_type: Optional[Literal["none", "bearer", "api_key", "auto", "oauth"]] = Field(
        "none", description="Authentication type (HTTP only)"
    )
    auth_config: Optional[dict] = Field(
        None,
        description="Authentication config (HTTP only). For bearer: {token: '...'}, for api_key: {key_name: '...', key: '...'}"
    )

    # OAuth scope mode. 'user' (default) → each user authenticates and
    # has their own token. 'system' → one admin completes OAuth once and
    # all users share that token. Locked at creation; ignored by updates.
    # Only superadmins may create servers with oauth_mode='system'.
    oauth_mode: Optional[Literal["user", "system"]] = Field(
        "user",
        description="OAuth scope mode. 'user' (default) or 'system' (admin-only).",
    )


class MCPServerUpdate(BaseModel):
    """Request model for updating MCP server (all fields optional)"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    protocol: Optional[Literal["stdio", "http"]] = None

    # stdio fields
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env_vars: Optional[dict] = None

    # HTTP fields
    url: Optional[str] = None
    headers: Optional[dict] = None
    auth_type: Optional[Literal["none", "bearer", "api_key", "auto", "oauth"]] = None
    auth_config: Optional[dict] = None


class MCPServerResponse(BaseModel):
    """Response model for MCP server"""
    id: str
    name: str
    description: Optional[str]
    protocol: str

    # stdio fields
    command: Optional[str]
    args: Optional[List[str]]
    env_vars: Optional[dict]

    # HTTP fields
    url: Optional[str]
    headers: Optional[dict]
    auth_type: Optional[str]

    # OAuth scope mode: 'user' (per-user tokens) or 'system' (one shared
    # token across all users). Always present, defaults to 'user' for
    # rows created before migration 118.
    oauth_mode: Optional[str] = None

    # Status
    status: str
    last_test_at: Optional[str]
    last_test_message: Optional[str]
    capabilities: Optional[dict]

    # Per-user view of authentication state. For OAuth servers this is
    # 'connected' iff the calling user has a row in mcp_oauth_tokens, else
    # 'needs_auth'. For non-OAuth servers it mirrors `status`.
    current_user_status: Optional[str] = None

    # Timestamps
    created_at: str
    updated_at: str


class MCPServerTestResponse(BaseModel):
    """Response model for server connection test"""
    success: bool
    message: str
    capabilities: Optional[dict] = None


class MCPToolResponse(BaseModel):
    """Response model for MCP tool"""
    id: str
    server_id: str
    tool_name: str
    description: Optional[str]
    input_schema: dict
    discovered_at: str


# ============================================================================
# Helper Functions
# ============================================================================

def format_server(
    row: dict,
    has_user_token: Optional[bool] = None,
) -> MCPServerResponse:
    """
    Format database row as response model.

    `has_user_token` is the result of looking up the *effective* token
    row for this server (True/False), or None when the caller is not in
    a per-user context. The lookup uses `effective_token_user_id`, so
    for system-mode servers it reflects whether the shared `__system__`
    row exists (same value for every caller); for user-mode servers it
    reflects whether *this user* has authenticated.
    """
    auth_type = row.get("auth_type")
    server_status = row.get("status", "untested")
    oauth_mode = row.get("oauth_mode") or "user"

    if auth_type == "oauth":
        if has_user_token is None:
            current_user_status = None
        elif has_user_token:
            current_user_status = "connected"
        else:
            current_user_status = "needs_auth"
    else:
        # Non-OAuth servers: per-user status equals the global status.
        current_user_status = server_status

    return MCPServerResponse(
        id=row["id"],
        name=row["name"],
        description=row.get("description"),
        protocol=row["protocol"],
        command=row.get("command"),
        args=json.loads(row["args"]) if row.get("args") else None,
        env_vars=json.loads(row["env_vars"]) if row.get("env_vars") else None,
        url=row.get("url"),
        headers=json.loads(row["headers"]) if row.get("headers") else None,
        auth_type=auth_type,
        oauth_mode=oauth_mode,
        status=server_status,
        last_test_at=row.get("last_test_at"),
        last_test_message=row.get("last_test_message"),
        capabilities=json.loads(row["capabilities"]) if row.get("capabilities") else None,
        current_user_status=current_user_status,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def _user_has_token(server_row: dict, user_id: str) -> bool:
    """
    True iff the *effective* token row for this server exists.

    For user-mode servers this is the calling user's row. For system-mode
    servers it's the shared `__system__` row — the same value for every
    caller. The substitution lives in `effective_token_user_id`.
    """
    token_user_id = effective_token_user_id(server_row, user_id)
    if not token_user_id:
        return False
    rows = await repo_query(
        "SELECT 1 FROM mcp_oauth_tokens "
        "WHERE server_id = :server_id AND user_id = :user_id LIMIT 1",
        {"server_id": server_row["id"], "user_id": token_user_id},
    )
    return bool(rows)


async def get_server_by_id(server_id: str) -> Optional[dict]:
    """Fetch server from database by ID"""
    rows = await repo_query("SELECT * FROM mcp_servers WHERE id = :id", {"id": server_id})
    return dict(rows[0]) if rows else None


def validate_server_config(server: MCPServerCreate) -> None:
    """Validate server configuration based on protocol"""
    if server.protocol == "stdio":
        if not server.command:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="command is required for stdio protocol"
            )
    elif server.protocol == "http":
        if not server.url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="url is required for http protocol"
            )


# ============================================================================
# CRUD Endpoints
# ============================================================================

@router.post("", status_code=status.HTTP_201_CREATED, response_model=MCPServerResponse)
async def create_server(
    server: MCPServerCreate,
    current_user: User = Depends(get_current_active_user),
):
    """Create new MCP server connection.

    Creating a server with `oauth_mode='system'` is admin-only — that mode
    grants every user access to a single shared OAuth identity, so it
    needs the same trust level as managing any other shared credential.
    `oauth_mode='user'` (the default) is open to all authenticated users.
    """

    # Admin gate: system mode shares one token across everyone, so only
    # superadmins may create such servers.
    oauth_mode = server.oauth_mode or "user"
    if oauth_mode == "system" and not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create system-mode MCP servers.",
        )

    # Validate protocol-specific fields
    validate_server_config(server)

    server_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    # Encrypt auth config if present
    auth_encrypted = None
    if server.auth_config:
        try:
            auth_encrypted = encrypt_password(json.dumps(server.auth_config))
        except Exception as e:
            logger.error(f"Failed to encrypt auth config: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to encrypt authentication configuration"
            )

    # Check for duplicate name
    existing = await repo_query(
        "SELECT id FROM mcp_servers WHERE name = :name",
        {"name": server.name}
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Server with name '{server.name}' already exists"
        )

    # Insert server
    await repo_execute("""
        INSERT INTO mcp_servers (
            id, name, description, protocol,
            command, args, env_vars,
            url, headers, auth_type, auth_config_encrypted,
            oauth_mode,
            status, created_at, updated_at
        ) VALUES (
            :id, :name, :description, :protocol,
            :command, :args, :env_vars,
            :url, :headers, :auth_type, :auth_config,
            :oauth_mode,
            :status, :created_at, :updated_at
        )
    """, {
        "id": server_id,
        "name": server.name,
        "description": server.description,
        "protocol": server.protocol,
        "command": server.command,
        "args": json.dumps(server.args) if server.args else None,
        "env_vars": json.dumps(server.env_vars) if server.env_vars else None,
        "url": server.url,
        "headers": json.dumps(server.headers) if server.headers else None,
        "auth_type": server.auth_type,
        "auth_config": auth_encrypted,
        "oauth_mode": oauth_mode,
        "status": "untested",
        "created_at": now,
        "updated_at": now
    })

    # Fetch and return created server. The creator hasn't yet authenticated
    # an OAuth flow even on their own behalf, so has_user_token is False.
    server_data = await get_server_by_id(server_id)
    has_token = False if server.auth_type == "oauth" else None
    return format_server(server_data, has_user_token=has_token)


@router.get("", response_model=List[MCPServerResponse])
async def list_servers(
    current_user: User = Depends(get_current_active_user),
):
    """List all MCP servers, with `current_user_status` reflecting the
    *effective* token row for each server:
      - user-mode: the calling user's row.
      - system-mode: the shared `__system__` row (same value for everyone).
    """
    rows = await repo_query(
        """
        SELECT s.*,
               (CASE WHEN t.access_token IS NOT NULL THEN 1 ELSE 0 END) AS _has_user_token
        FROM mcp_servers s
        LEFT JOIN mcp_oauth_tokens t
            ON t.server_id = s.id
           AND t.user_id   = CASE
                                 WHEN COALESCE(s.oauth_mode, 'user') = 'system'
                                     THEN :system_user_id
                                 ELSE :user_id
                             END
        ORDER BY s.name
        """,
        {"user_id": current_user.id, "system_user_id": SYSTEM_OAUTH_USER_ID},
    )
    return [
        format_server(
            dict(row),
            has_user_token=bool(row.get("_has_user_token"))
                if row.get("auth_type") == "oauth"
                else None,
        )
        for row in rows
    ]


@router.get("/{server_id}", response_model=MCPServerResponse)
async def get_server(
    server_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Get single MCP server by ID"""
    server_data = await get_server_by_id(server_id)

    if not server_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP server not found"
        )

    has_token = (
        await _user_has_token(server_data, current_user.id)
        if server_data.get("auth_type") == "oauth"
        else None
    )
    return format_server(server_data, has_user_token=has_token)


@router.put("/{server_id}", response_model=MCPServerResponse)
async def update_server(
    server_id: str,
    update: MCPServerUpdate,
    current_user: User = Depends(get_current_active_user),
):
    """Update MCP server"""

    # Check if server exists
    existing = await get_server_by_id(server_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP server not found"
        )

    # Build update fields
    update_fields = []
    update_params = {}

    # Simple fields
    if update.name is not None:
        # Check for duplicate name
        duplicate = await repo_query(
            "SELECT id FROM mcp_servers WHERE name = :name AND id != :id",
            {"name": update.name, "id": server_id}
        )
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Server with name '{update.name}' already exists"
            )
        update_fields.append("name = :name")
        update_params["name"] = update.name

    if update.description is not None:
        update_fields.append("description = :description")
        update_params["description"] = update.description

    if update.protocol is not None:
        update_fields.append("protocol = :protocol")
        update_params["protocol"] = update.protocol

    # stdio fields
    if update.command is not None:
        update_fields.append("command = :command")
        update_params["command"] = update.command

    if update.args is not None:
        update_fields.append("args = :args")
        update_params["args"] = json.dumps(update.args)

    if update.env_vars is not None:
        update_fields.append("env_vars = :env_vars")
        update_params["env_vars"] = json.dumps(update.env_vars)

    # HTTP fields
    if update.url is not None:
        update_fields.append("url = :url")
        update_params["url"] = update.url

    if update.headers is not None:
        update_fields.append("headers = :headers")
        update_params["headers"] = json.dumps(update.headers)

    if update.auth_type is not None:
        update_fields.append("auth_type = :auth_type")
        update_params["auth_type"] = update.auth_type

    if update.auth_config is not None:
        try:
            auth_encrypted = encrypt_password(json.dumps(update.auth_config))
            update_fields.append("auth_config_encrypted = :auth_config")
            update_params["auth_config"] = auth_encrypted
        except Exception as e:
            logger.error(f"Failed to encrypt auth config: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to encrypt authentication configuration"
            )

    # Always update updated_at
    now = datetime.utcnow().isoformat()
    update_fields.append("updated_at = :updated_at")
    update_params["updated_at"] = now

    # Perform update if there are fields to update
    if update_fields:
        update_params["id"] = server_id  # For WHERE clause
        sql = f"UPDATE mcp_servers SET {', '.join(update_fields)} WHERE id = :id"
        await repo_execute(sql, update_params)

        # Disconnect every cached client for this server so all users
        # reconnect with the new config on next use.
        await mcp_pool.disconnect(server_id, user_id=None)

    # Fetch and return updated server (per-user state)
    server_data = await get_server_by_id(server_id)
    has_token = (
        await _user_has_token(server_data, current_user.id)
        if server_data.get("auth_type") == "oauth"
        else None
    )
    return format_server(server_data, has_user_token=has_token)


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(
    server_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Delete MCP server"""

    # Check if server exists
    existing = await get_server_by_id(server_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP server not found"
        )

    # Drop every cached client for this server (any user). user_id=None
    # signals "all users" to the pool.
    await mcp_pool.disconnect(server_id, user_id=None)

    # Delete from database (CASCADE will delete mcp_tools and mcp_oauth_tokens)
    await repo_execute("DELETE FROM mcp_servers WHERE id = :id", {"id": server_id})


# ============================================================================
# Testing and Discovery Endpoints
# ============================================================================

@router.post("/{server_id}/test", response_model=MCPServerTestResponse)
async def test_server(
    server_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    """
    Test the MCP server connection on behalf of the calling user.

    For OAuth servers this checks whether *this user* has a valid token.
    A 200 with `success=False` and `needs_oauth=True` means the user must
    visit `/oauth/start` to authenticate themselves — even if another user
    has already authenticated against the same server.
    """

    # Fetch server config
    server_config = await get_server_by_id(server_id)
    if not server_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP server not found"
        )
    logger.info(
        f"Testing server {server_config.get('name')} ({server_id}) for user={current_user.id}"
    )

    now = datetime.utcnow().isoformat()

    try:
        # Per-user client. PermissionError surfaces when no OAuth token row
        # exists for this user (vs. ConnectionError for transport failures).
        client = await MCPClientFactory.create_client(server_config, user_id=current_user.id)
        connected = await client.connect()
        logger.info(f"Connection result: connected={connected}")

        # Check if OAuth is required (401 response or no token loaded)
        if not connected and hasattr(client, '_needs_oauth') and client._needs_oauth:
            logger.info(f"MCP server {server_id} requires OAuth - triggering discovery")

            # Import OAuth discovery functions
            from api.routers.mcp_oauth import (
                discover_oauth_configuration,
                register_oauth_client_dynamically,
                store_client_credentials,
                get_stored_client_credentials,
                _public_base_url,
            )

            # Step 1: Make sure dynamic registration has happened (shared
            # across users). If we already have a client_id we skip this.
            try:
                existing_client = await get_stored_client_credentials(server_id)
                if not existing_client:
                    oauth_config = await discover_oauth_configuration(server_config["url"])

                    if not oauth_config:
                        # OAuth required but auto-discovery failed
                        await repo_execute("""
                            UPDATE mcp_servers
                            SET status = :status, last_test_at = :last_test_at,
                                last_test_message = :last_test_message, updated_at = :updated_at,
                                auth_type = :auth_type
                            WHERE id = :id
                        """, {
                            "status": "needs_auth",
                            "last_test_at": now,
                            "last_test_message": "OAuth required. Please configure OAuth credentials manually.",
                            "updated_at": now,
                            "auth_type": "oauth",
                            "id": server_id
                        })

                        return MCPServerTestResponse(
                            success=False,
                            message="OAuth required but automatic discovery not supported. Please configure OAuth manually.",
                            capabilities={
                                "needs_oauth": True,
                                "manual_setup_required": True,
                            }
                        )

                    if oauth_config.get('registration_endpoint'):
                        # Use the public origin (AppRouter when deployed,
                        # bare backend in local dev) — must match the
                        # redirect_uri the user's browser actually sees.
                        base_url = _public_base_url(request)
                        registered_client = await register_oauth_client_dynamically(
                            registration_endpoint=oauth_config['registration_endpoint'],
                            server_id=server_id,
                            base_url=base_url
                        )
                        await store_client_credentials(
                            server_id=server_id,
                            client_id=registered_client['client_id'],
                            client_secret=registered_client.get('client_secret'),
                            registration_response=registered_client
                        )
                    else:
                        raise Exception("OAuth required but dynamic client registration not supported")

                # Mark the server as needing auth at the global level (it stays
                # "connected" once anyone has authenticated; here we reflect
                # that *this* user still needs to log in).
                await repo_execute("""
                    UPDATE mcp_servers
                    SET auth_type = :auth_type,
                        last_test_at = :last_test_at,
                        last_test_message = :last_test_message,
                        updated_at = :updated_at
                    WHERE id = :id
                """, {
                    "auth_type": "oauth",
                    "last_test_at": now,
                    "last_test_message": "OAuth authentication required for this user.",
                    "updated_at": now,
                    "id": server_id
                })

                # Authorization URL: the frontend should call POST
                # /oauth/start with its JWT to get the per-user signed URL.
                # We return the relative path so the frontend can hit it
                # with credentials attached.
                start_url = f"/api/mcp-servers/{server_id}/oauth/start"

                return MCPServerTestResponse(
                    success=False,
                    message="OAuth required for this user. POST to oauth/start to begin.",
                    capabilities={
                        "needs_oauth": True,
                        "oauth_start_url": start_url,
                        "current_user_status": "needs_auth",
                    }
                )

            except Exception as oauth_error:
                logger.error(f"OAuth discovery failed: {oauth_error}")
                raise Exception(f"OAuth required but setup failed: {str(oauth_error)}")

        if not connected:
            raise Exception("Failed to establish connection")

        # We've proven the connection works; now do the canonical
        # discover-and-cache pass via the shared helper so /test and the
        # OAuth-callback path stay in lock-step (same SQL, same field
        # semantics, same error handling).
        await client.disconnect()
        from api.services.mcp_client import (
            discover_and_cache_capabilities,
            effective_token_user_id as _eff,
        )
        capabilities = await discover_and_cache_capabilities(
            server_config, user_id=_eff(server_config, current_user.id)
        )

        return MCPServerTestResponse(
            success=True,
            message=(
                f"Connected successfully. Found "
                f"{len(capabilities['tools'])} tools, "
                f"{len(capabilities['resources'])} resources, "
                f"{len(capabilities['prompts'])} prompts."
            ),
            capabilities=capabilities
        )

    except Exception as e:
        error_message = str(e)
        logger.error(f"Failed to test MCP server {server_id}: {error_message}", exc_info=True)

        # Update database with error status
        await repo_execute("""
            UPDATE mcp_servers
            SET status = :status, last_test_at = :last_test_at, last_test_message = :last_test_message, updated_at = :updated_at
            WHERE id = :id
        """, {
            "status": "error",
            "last_test_at": now,
            "last_test_message": error_message[:500],  # Truncate long error messages
            "updated_at": now,
            "id": server_id
        })

        return MCPServerTestResponse(
            success=False,
            message=f"Connection failed: {error_message}"
        )


@router.get("/{server_id}/tools", response_model=List[MCPToolResponse])
async def list_server_tools(
    server_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """List tools from MCP server (cached, shared across users)."""

    # Check if server exists
    server_config = await get_server_by_id(server_id)
    if not server_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP server not found"
        )

    # Fetch cached tools
    rows = await repo_query("""
        SELECT * FROM mcp_tools
        WHERE server_id = :server_id
        ORDER BY tool_name
    """, {"server_id": server_id})

    return [
        MCPToolResponse(
            id=row["id"],
            server_id=row["server_id"],
            tool_name=row["tool_name"],
            description=row.get("description"),
            input_schema=json.loads(row.get("input_schema") or "{}"),
            discovered_at=row["discovered_at"]
        )
        for row in rows
    ]


@router.get("/{server_id}/resources", response_model=dict)
async def list_server_resources(
    server_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """List resources from MCP server (from cached capabilities)"""

    server_config = await get_server_by_id(server_id)
    if not server_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP server not found"
        )

    capabilities = server_config.get("capabilities")
    if capabilities:
        capabilities = json.loads(capabilities)
        return {"resources": capabilities.get("resources", [])}

    return {"resources": []}


@router.get("/{server_id}/prompts", response_model=dict)
async def list_server_prompts(
    server_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """List prompts from MCP server (from cached capabilities)"""

    server_config = await get_server_by_id(server_id)
    if not server_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP server not found"
        )

    capabilities = server_config.get("capabilities")
    if capabilities:
        capabilities = json.loads(capabilities)
        return {"prompts": capabilities.get("prompts", [])}

    return {"prompts": []}


@router.post("/{server_id}/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_server(
    server_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """
    Logout from this OAuth-authenticated MCP server.

    For user-mode servers (the default) this deletes only the calling
    user's token; other users' sessions are untouched.

    For system-mode servers there is exactly one shared token. Logging
    out signs *every* user out of this server, so we require admin.
    """

    # Check if server exists
    server_config = await get_server_by_id(server_id)
    if not server_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP server not found"
        )

    is_system_mode = (server_config.get("oauth_mode") or "user") == "system"
    if is_system_mode and not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Only administrators can sign out a system-mode MCP server "
                "(this would sign all users out)."
            ),
        )

    # Resolve the row to delete via the same helper used everywhere else.
    token_user_id = effective_token_user_id(server_config, current_user.id)
    if not token_user_id:
        return  # nothing to revoke

    await repo_execute(
        "DELETE FROM mcp_oauth_tokens "
        "WHERE server_id = :server_id AND user_id = :user_id",
        {"server_id": server_id, "user_id": token_user_id},
    )

    # Evict the matching pool entry. For user-mode this is just the
    # caller's client; for system-mode it's the single shared client
    # that was being used by everyone.
    await mcp_pool.disconnect(server_id, user_id=token_user_id)

    logger.info(
        f"Logout: server={server_id} token_user={token_user_id} "
        f"by user={current_user.id}"
    )


# ============================================================================
# Sessions Endpoints (per-user OAuth tokens)
# ============================================================================
#
# These endpoints expose the rows in `mcp_oauth_tokens` so users can see
# who is authenticated against an MCP server and revoke a specific session.
#
# Visibility:
#   - Non-admins:   see only their own session for the server (a single row,
#                   if they've authenticated).
#   - Superadmins:  see every authenticated user, plus the shared
#                   `__system__` row for system-mode servers.
#
# Revoke:
#   - A non-admin may only revoke their own session.
#   - A superadmin may revoke any session, including `__system__` (which
#     signs every user out of a system-mode server).


class MCPServerSessionResponse(BaseModel):
    """One authenticated user's session for an MCP server."""

    server_id: str
    # The token row's user_id. For user-mode servers this is a real user
    # UUID; for system-mode servers it's the sentinel `__system__`.
    user_id: str
    # Resolved profile fields. Null for the `__system__` row (which has no
    # corresponding users-table entry).
    username: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    is_system: bool = False
    # Provider-side identity captured at OAuth time (e.g. Outreach email).
    # Falls back to the local user when not present.
    provider_email: Optional[str] = None
    provider_name: Optional[str] = None
    expires_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    # Convenience flag — true iff this row belongs to the calling user
    # (i.e. their own session). Lets the UI label "(You)" without an
    # extra round-trip.
    is_current_user: bool = False


@router.get(
    "/{server_id}/sessions",
    response_model=List[MCPServerSessionResponse],
)
async def list_server_sessions(
    server_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """List authenticated user sessions for this MCP server.

    Non-admins see only their own session. Admins see every row in
    `mcp_oauth_tokens` for this server, including the shared `__system__`
    row for system-mode servers.
    """
    server_config = await get_server_by_id(server_id)
    if not server_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP server not found",
        )

    # Build the query. We LEFT JOIN users so the `__system__` row (which
    # has no users-table entry) still appears for admins.
    if current_user.is_superadmin:
        sql = """
            SELECT t.server_id, t.user_id, t.user_info, t.expires_at,
                   t.created_at, t.updated_at,
                   u.username, u.email, u.full_name
            FROM mcp_oauth_tokens t
            LEFT JOIN users u ON u.id = t.user_id
            WHERE t.server_id = :server_id
            ORDER BY t.updated_at DESC
        """
        params = {"server_id": server_id}
    else:
        # Non-admin: only the calling user's row. For system-mode servers
        # the row lives under `__system__`, which a non-admin shouldn't
        # see — `effective_token_user_id` would resolve them there, but
        # they don't own that row and can't revoke it. So we restrict to
        # the literal user id.
        sql = """
            SELECT t.server_id, t.user_id, t.user_info, t.expires_at,
                   t.created_at, t.updated_at,
                   u.username, u.email, u.full_name
            FROM mcp_oauth_tokens t
            LEFT JOIN users u ON u.id = t.user_id
            WHERE t.server_id = :server_id AND t.user_id = :user_id
            ORDER BY t.updated_at DESC
        """
        params = {"server_id": server_id, "user_id": current_user.id}

    rows = await repo_query(sql, params)

    sessions: list[MCPServerSessionResponse] = []
    for row in rows:
        row = dict(row)
        is_system = row["user_id"] == SYSTEM_OAUTH_USER_ID

        provider_email = None
        provider_name = None
        if row.get("user_info"):
            try:
                info = json.loads(row["user_info"])
                provider_email = info.get("email")
                provider_name = info.get("name")
            except (json.JSONDecodeError, TypeError):
                # Corrupt user_info shouldn't break the listing.
                pass

        sessions.append(
            MCPServerSessionResponse(
                server_id=row["server_id"],
                user_id=row["user_id"],
                username=row.get("username"),
                email=row.get("email"),
                full_name=row.get("full_name"),
                is_system=is_system,
                provider_email=provider_email,
                provider_name=provider_name,
                expires_at=row.get("expires_at"),
                created_at=row.get("created_at"),
                updated_at=row.get("updated_at"),
                is_current_user=(row["user_id"] == current_user.id),
            )
        )

    return sessions


@router.delete(
    "/{server_id}/sessions/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_server_session(
    server_id: str,
    user_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Revoke an authenticated user's session for this MCP server.

    A non-admin may only revoke their own session. A superadmin may
    revoke any session, including the shared `__system__` row that
    backs system-mode servers (this signs every user out at once).
    """
    server_config = await get_server_by_id(server_id)
    if not server_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP server not found",
        )

    # Authorization: non-admins can only delete their own row.
    if user_id != current_user.id and not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can revoke other users' sessions.",
        )

    # Confirm the row exists so we can return a clean 404 instead of a
    # silent no-op (and so the UI can refresh confidently on success).
    existing = await repo_query(
        "SELECT 1 FROM mcp_oauth_tokens "
        "WHERE server_id = :server_id AND user_id = :user_id LIMIT 1",
        {"server_id": server_id, "user_id": user_id},
    )
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found for this user.",
        )

    await repo_execute(
        "DELETE FROM mcp_oauth_tokens "
        "WHERE server_id = :server_id AND user_id = :user_id",
        {"server_id": server_id, "user_id": user_id},
    )

    # Evict the matching cached client so the next request reconnects
    # (or fails with needs_auth, which is what we want).
    await mcp_pool.disconnect(server_id, user_id=user_id)

    logger.info(
        f"Session revoked: server={server_id} target_user={user_id} "
        f"by user={current_user.id}"
    )
