"""
MCP Servers API Router

Provides REST API endpoints for managing MCP (Model Context Protocol) server
connections, including CRUD operations, connection testing, and capability discovery.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from open_notebook.config import get_encryption_key
from open_notebook.database.repository import repo_query, repo_execute
from api.services.mcp_client import MCPClientFactory, mcp_pool

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

    # Status
    status: str
    last_test_at: Optional[str]
    last_test_message: Optional[str]
    capabilities: Optional[dict]

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

def format_server(row: dict) -> MCPServerResponse:
    """Format database row as response model"""
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
        auth_type=row.get("auth_type"),
        status=row.get("status", "untested"),
        last_test_at=row.get("last_test_at"),
        last_test_message=row.get("last_test_message"),
        capabilities=json.loads(row["capabilities"]) if row.get("capabilities") else None,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


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
async def create_server(server: MCPServerCreate):
    """Create new MCP server connection"""

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
            status, created_at, updated_at
        ) VALUES (
            :id, :name, :description, :protocol,
            :command, :args, :env_vars,
            :url, :headers, :auth_type, :auth_config,
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
        "status": "untested",
        "created_at": now,
        "updated_at": now
    })

    # Fetch and return created server
    server_data = await get_server_by_id(server_id)
    return format_server(server_data)


@router.get("", response_model=List[MCPServerResponse])
async def list_servers():
    """List all MCP servers"""
    rows = await repo_query("SELECT * FROM mcp_servers ORDER BY name")
    return [format_server(dict(row)) for row in rows]


@router.get("/{server_id}", response_model=MCPServerResponse)
async def get_server(server_id: str):
    """Get single MCP server by ID"""
    server_data = await get_server_by_id(server_id)

    if not server_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP server not found"
        )

    return format_server(server_data)


@router.put("/{server_id}", response_model=MCPServerResponse)
async def update_server(server_id: str, update: MCPServerUpdate):
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

        # Disconnect from pool to force reconnect with new config
        await mcp_pool.disconnect(server_id)

    # Fetch and return updated server
    server_data = await get_server_by_id(server_id)
    return format_server(server_data)


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(server_id: str):
    """Delete MCP server"""

    # Check if server exists
    existing = await get_server_by_id(server_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP server not found"
        )

    # Disconnect from pool
    await mcp_pool.disconnect(server_id)

    # Delete from database (CASCADE will delete mcp_tools)
    await repo_execute("DELETE FROM mcp_servers WHERE id = :id", {"id": server_id})


# ============================================================================
# Testing and Discovery Endpoints
# ============================================================================

@router.post("/{server_id}/test", response_model=MCPServerTestResponse)
async def test_server(server_id: str):
    """Test MCP server connection and discover capabilities"""

    # Fetch server config
    server_config = await get_server_by_id(server_id)
    if not server_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP server not found"
        )
    logger.info(f"Testing server {server_config.get('name')} ({server_id})")

    now = datetime.utcnow().isoformat()

    try:
        # Create and connect client
        client = await MCPClientFactory.create_client(server_config)
        connected = await client.connect()
        logger.info(f"Connection result: connected={connected}")

        # Check if OAuth is required (401 response)
        if not connected and hasattr(client, '_needs_oauth') and client._needs_oauth:
            logger.info(f"MCP server {server_id} requires OAuth - triggering discovery")

            # Import OAuth discovery functions
            from api.routers.mcp_oauth import discover_oauth_configuration, register_oauth_client_dynamically, store_client_credentials

            # Step 1: Discover OAuth configuration
            try:
                oauth_config = await discover_oauth_configuration(server_config["url"])

                if not oauth_config:
                    # OAuth required but auto-discovery failed
                    # Update database to indicate manual OAuth setup needed
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
                            "instructions": "This server requires OAuth but doesn't support automatic discovery. Please obtain OAuth credentials from the provider and configure them manually."
                        }
                    )

                # Step 2: Check for dynamic client registration
                if oauth_config.get('registration_endpoint'):
                    # Get base URL for redirect URI
                    # TODO: Get actual base URL from request context
                    base_url = "http://localhost:5055"

                    # Register client dynamically
                    registered_client = await register_oauth_client_dynamically(
                        registration_endpoint=oauth_config['registration_endpoint'],
                        server_id=server_id,
                        base_url=base_url
                    )

                    # Store credentials
                    await store_client_credentials(
                        server_id=server_id,
                        client_id=registered_client['client_id'],
                        client_secret=registered_client.get('client_secret'),
                        registration_response=registered_client
                    )

                    # Update database to indicate OAuth is needed
                    await repo_execute("""
                        UPDATE mcp_servers
                        SET status = :status, last_test_at = :last_test_at,
                            last_test_message = :last_test_message, updated_at = :updated_at,
                            auth_type = :auth_type
                        WHERE id = :id
                    """, {
                        "status": "needs_auth",
                        "last_test_at": now,
                        "last_test_message": "OAuth authentication required. Please complete authorization.",
                        "updated_at": now,
                        "auth_type": "oauth",
                        "id": server_id
                    })

                    # Return special response with authorization URL
                    authorization_url = f"{base_url}/api/mcp-servers/{server_id}/oauth/authorize"

                    return MCPServerTestResponse(
                        success=False,
                        message=f"OAuth required. Authorization URL: {authorization_url}",
                        capabilities={"authorization_url": authorization_url, "needs_oauth": True}
                    )
                else:
                    raise Exception("OAuth required but dynamic client registration not supported")

            except Exception as oauth_error:
                logger.error(f"OAuth discovery failed: {oauth_error}")
                raise Exception(f"OAuth required but setup failed: {str(oauth_error)}")

        if not connected:
            raise Exception("Failed to establish connection")

        # Discover capabilities
        tools = await client.list_tools()
        resources = await client.list_resources()
        prompts = await client.list_prompts()

        capabilities = {
            "tools": tools,
            "resources": resources,
            "prompts": prompts
        }

        # Update database with success status
        await repo_execute("""
            UPDATE mcp_servers
            SET status = :status, last_test_at = :last_test_at, last_test_message = :last_test_message,
                capabilities = :capabilities, updated_at = :updated_at
            WHERE id = :id
        """, {
            "status": "connected",
            "last_test_at": now,
            "last_test_message": "Successfully connected",
            "capabilities": json.dumps(capabilities),
            "updated_at": now,
            "id": server_id
        })

        # Cache discovered tools
        # First, delete existing tools for this server
        await repo_execute("DELETE FROM mcp_tools WHERE server_id = :server_id", {"server_id": server_id})

        # Insert new tools
        for tool in tools:
            tool_id = f"{server_id}:{tool['name']}"
            await repo_execute("""
                INSERT INTO mcp_tools (id, server_id, tool_name, description, input_schema, discovered_at)
                VALUES (:id, :server_id, :tool_name, :description, :input_schema, :discovered_at)
            """, {
                "id": tool_id,
                "server_id": server_id,
                "tool_name": tool["name"],
                "description": tool.get("description", ""),
                "input_schema": json.dumps(tool.get("inputSchema", {})),
                "discovered_at": now
            })

        # Disconnect (will reconnect via pool when needed)
        await client.disconnect()

        return MCPServerTestResponse(
            success=True,
            message=f"Connected successfully. Found {len(tools)} tools, {len(resources)} resources, {len(prompts)} prompts.",
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
async def list_server_tools(server_id: str):
    """List tools from MCP server"""

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
async def list_server_resources(server_id: str):
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
async def list_server_prompts(server_id: str):
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
async def logout_server(server_id: str):
    """
    Logout from OAuth-authenticated MCP server.
    Clears stored tokens and resets auth configuration.
    """

    # Check if server exists
    server_config = await get_server_by_id(server_id)
    if not server_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCP server not found"
        )

    # Delete OAuth tokens
    await repo_execute("DELETE FROM mcp_oauth_tokens WHERE server_id = :server_id", {"server_id": server_id})

    # Clear auth config and reset status
    now = datetime.utcnow().isoformat()
    await repo_execute("""
        UPDATE mcp_servers
        SET auth_config_encrypted = NULL,
            status = :status,
            last_test_message = :message,
            updated_at = :updated_at
        WHERE id = :id
    """, {
        "status": "needs_auth",
        "message": "Logged out. Please re-authenticate.",
        "updated_at": now,
        "id": server_id
    })

    # Disconnect from pool
    await mcp_pool.disconnect(server_id)

    logger.info(f"User logged out from MCP server {server_id}")
