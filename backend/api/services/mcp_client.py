"""
MCP (Model Context Protocol) Client Service

Provides client implementations for communicating with MCP servers using both:
- stdio protocol (subprocess-based JSON-RPC over stdin/stdout)
- HTTP protocol (REST API with optional SSE streaming)

Includes connection pooling for efficient resource management.
"""

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)


# Sentinel user_id used to key the single shared OAuth token row for
# system-mode MCP servers (oauth_mode='system'). users.id is a 36-char
# UUID, so this string cannot collide with a real user.
SYSTEM_OAUTH_USER_ID = "__system__"


def effective_token_user_id(
    server_row: Dict[str, Any],
    caller_user_id: Optional[str],
) -> Optional[str]:
    """
    Resolve which user_id to use for token storage/lookup for `server_row`.

    For system-mode servers (`oauth_mode='system'`), the OAuth token is
    shared across all users and stored under `SYSTEM_OAUTH_USER_ID`. For
    user-mode servers (the default), each user has their own token and we
    use `caller_user_id` verbatim.

    Centralized here so every read/write path makes the same choice; if
    one site forgot to substitute, two users could end up reading
    different tokens for the same supposedly-shared server.
    """
    if (server_row.get("oauth_mode") or "user") == "system":
        return SYSTEM_OAUTH_USER_ID
    return caller_user_id


class MCPClient(ABC):
    """Abstract base class for MCP protocol clients"""

    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to MCP server.

        Returns:
            bool: True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        Discover available tools from MCP server.

        Returns:
            List of tool definitions with name, description, and inputSchema
        """
        pass

    @abstractmethod
    async def list_resources(self) -> List[Dict[str, Any]]:
        """
        Discover available resources from MCP server.

        Returns:
            List of resource definitions
        """
        pass

    @abstractmethod
    async def list_prompts(self) -> List[Dict[str, Any]]:
        """
        Discover available prompts from MCP server.

        Returns:
            List of prompt definitions
        """
        pass

    @abstractmethod
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """
        Execute a tool on the MCP server.

        Args:
            name: Tool name
            arguments: Tool arguments as dict

        Returns:
            Tool execution result
        """
        pass

    @abstractmethod
    async def read_resource(self, uri: str) -> Any:
        """
        Read a resource from the MCP server.

        Args:
            uri: Resource URI

        Returns:
            Resource content
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to MCP server"""
        pass


class MCPStdioClient(MCPClient):
    """
    MCP client using stdio protocol (subprocess communication via JSON-RPC).

    Communicates with MCP servers running as child processes using JSON-RPC
    messages over stdin/stdout.
    """

    def __init__(self, command: str, args: List[str], env: Dict[str, str]):
        """
        Initialize stdio MCP client.

        Args:
            command: Command to execute (e.g., 'npx', 'python', '/path/to/server')
            args: List of command arguments
            env: Environment variables to set
        """
        self.command = command
        self.args = args
        self.env = env
        self.process: Optional[asyncio.subprocess.Process] = None
        self.request_id = 0
        self.pending_requests: Dict[int, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None
        self._connected = False

    async def connect(self) -> bool:
        """Start subprocess and establish JSON-RPC communication"""
        try:
            # Build environment (merge with current environment)
            full_env = {**os.environ, **self.env}

            # Start subprocess
            self.process = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=full_env,
            )

            # Start reader task for responses
            self._reader_task = asyncio.create_task(self._read_responses())

            # Send initialize request
            response = await self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {}
                },
                "clientInfo": {
                    "name": "open-notebook",
                    "version": "1.0.0"
                }
            })

            self._connected = response.get("protocolVersion") is not None
            return self._connected

        except Exception as e:
            logger.error(f"Failed to connect to MCP stdio server: {e}")
            return False

    async def _send_request(self, method: str, params: Dict) -> Dict:
        """Send JSON-RPC request over stdin and wait for response"""
        if not self.process or not self.process.stdin:
            raise RuntimeError("MCP client not connected")

        self.request_id += 1
        request_id = self.request_id

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }

        # Create future for response
        future = asyncio.Future()
        self.pending_requests[request_id] = future

        # Write to stdin
        message = json.dumps(request) + "\n"
        self.process.stdin.write(message.encode())
        await self.process.stdin.drain()

        # Wait for response (with timeout)
        try:
            return await asyncio.wait_for(future, timeout=30.0)
        except asyncio.TimeoutError:
            self.pending_requests.pop(request_id, None)
            raise TimeoutError(f"MCP request timeout: {method}")

    async def _read_responses(self):
        """Read JSON-RPC responses from stdout"""
        if not self.process or not self.process.stdout:
            return

        try:
            while self.process.returncode is None:
                line = await self.process.stdout.readline()
                if not line:
                    break

                try:
                    response = json.loads(line.decode().strip())
                    request_id = response.get("id")

                    if request_id in self.pending_requests:
                        future = self.pending_requests.pop(request_id)
                        if "error" in response:
                            error_data = response["error"]
                            future.set_exception(
                                Exception(f"MCP error: {error_data.get('message', 'Unknown error')}")
                            )
                        else:
                            future.set_result(response.get("result", {}))

                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON from MCP server: {line} ({e})")
                except Exception as e:
                    logger.error(f"Error processing MCP response: {e}")

        except Exception as e:
            logger.error(f"Error reading MCP responses: {e}")
        finally:
            # Cancel any pending requests
            for future in self.pending_requests.values():
                if not future.done():
                    future.set_exception(Exception("Connection closed"))
            self.pending_requests.clear()

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from MCP server"""
        try:
            response = await self._send_request("tools/list", {})
            return response.get("tools", [])
        except Exception as e:
            logger.error(f"Failed to list MCP tools: {e}")
            return []

    async def list_resources(self) -> List[Dict[str, Any]]:
        """List available resources from MCP server"""
        try:
            response = await self._send_request("resources/list", {})
            return response.get("resources", [])
        except Exception as e:
            logger.error(f"Failed to list MCP resources: {e}")
            return []

    async def list_prompts(self) -> List[Dict[str, Any]]:
        """List available prompts from MCP server"""
        try:
            response = await self._send_request("prompts/list", {})
            return response.get("prompts", [])
        except Exception as e:
            logger.error(f"Failed to list MCP prompts: {e}")
            return []

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool on the MCP server"""
        response = await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })
        return response.get("content", [])

    async def read_resource(self, uri: str) -> Any:
        """Read a resource from the MCP server"""
        response = await self._send_request("resources/read", {
            "uri": uri
        })
        return response.get("contents", [])

    async def disconnect(self) -> None:
        """Terminate subprocess and cleanup"""
        if self.process:
            try:
                # Cancel reader task
                if self._reader_task and not self._reader_task.done():
                    self._reader_task.cancel()
                    try:
                        await self._reader_task
                    except asyncio.CancelledError:
                        pass

                # Terminate process
                self.process.terminate()
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    self.process.kill()
                    await self.process.wait()

            except Exception as e:
                logger.error(f"Error disconnecting MCP stdio client: {e}")
            finally:
                self.process = None
                self._connected = False


class MCPHttpClient(MCPClient):
    """
    MCP client using HTTP/SSE protocol.

    Communicates with MCP servers over HTTP REST APIs with optional
    Server-Sent Events for streaming responses.
    """

    def __init__(
        self,
        url: str,
        headers: Dict[str, str],
        auth_config: Dict,
        server_id: str = None,
        user_id: str = None,
    ):
        """
        Initialize HTTP MCP client.

        Args:
            url: Base URL of MCP server
            headers: Additional HTTP headers
            auth_config: Authentication configuration
            server_id: MCP server identifier (for OAuth token refresh)
            user_id: Authenticated user identifier (for per-user OAuth tokens).
                Required for OAuth servers; ignored for non-OAuth auth.
        """
        self.url = url.rstrip("/")
        self.headers = headers or {}
        self.auth_config = auth_config or {}
        self.user_id = user_id
        # Store server_id (and user_id) for OAuth token refresh
        if server_id:
            self.auth_config["server_id"] = server_id
        if user_id:
            self.auth_config["user_id"] = user_id
        self.client: Optional[httpx.AsyncClient] = None
        self._connected = False
        self._needs_oauth = False  # Track if OAuth is required
        self.server_capabilities: Dict[str, Any] = {}
        self.server_info: Dict[str, Any] = {}
        self._request_id = 1  # For JSON-RPC request IDs
        # Per-instance refresh lock so two concurrent tool calls from the
        # same user don't trigger duplicate refresh requests.
        self._refresh_lock = asyncio.Lock()

    async def connect(self) -> bool:
        """
        Test HTTP connection to MCP server.
        Performs MCP initialize handshake via JSON-RPC.
        """
        try:
            # Check if OAuth token is expired and refresh if needed
            # OAuth can be stored as type "oauth" or "bearer" with refresh_token present
            has_oauth = (
                self.auth_config.get("type") in ("oauth", "bearer") and
                self.auth_config.get("refresh_token")
            )

            if has_oauth and self._is_token_expired():
                logger.info("OAuth token expired, attempting refresh...")
                refreshed = await self._refresh_oauth_token()
                if not refreshed:
                    logger.warning("OAuth token refresh failed")
                    self._needs_oauth = True
                    return False

            logger.info(f"Connecting to MCP server: {self.url}")
            logger.info(f"Auth config type: {self.auth_config.get('type')}")

            self.client = httpx.AsyncClient(
                base_url=self.url,
                headers=self._build_headers(),
                timeout=30.0,
            )

            # Log headers (mask token)
            headers = self._build_headers()
            auth_header = headers.get('Authorization', 'None')
            if auth_header and auth_header.startswith('Bearer '):
                masked = f"Bearer {auth_header[7:20]}..."
                logger.info(f"Authorization header: {masked}")

            # MCP initialize handshake (JSON-RPC)
            logger.info(f"Sending MCP initialize request")
            initialize_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "roots": {"listChanged": True},
                        "sampling": {}
                    },
                    "clientInfo": {
                        "name": "open-notebook",
                        "version": "1.0.0"
                    }
                }
            }

            # Send initialize via POST (MCP JSON-RPC)
            response = await self.client.post(
                "/",
                json=initialize_request,
                headers={
                    **self._build_headers(),
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream"
                }
            )

            logger.info(f"Initialize response status: {response.status_code}")

            # Check for 401 Unauthorized - triggers OAuth flow
            if response.status_code == 401:
                logger.info(f"MCP server returned 401 - OAuth required: {self.url}")
                self._connected = False
                self._needs_oauth = True
                return False

            if response.status_code == 200:
                # Parse response based on content type
                content_type = response.headers.get('content-type', '')

                if 'text/event-stream' in content_type:
                    # SSE response - parse SSE format
                    init_response = self._parse_sse_response(response.text)
                else:
                    # Regular JSON response
                    init_response = response.json()

                if init_response.get("result"):
                    self.server_capabilities = init_response["result"].get("capabilities", {})
                    self.server_info = init_response["result"].get("serverInfo", {})
                    logger.info(f"✅ MCP server initialized: {self.server_info.get('name')}")
                    logger.info(f"   Capabilities: {list(self.server_capabilities.keys())}")
                    self._connected = True
                    self._needs_oauth = False
                    return True

            self._connected = False
            self._needs_oauth = False
            return False

        except Exception as e:
            logger.error(f"Failed to connect to MCP HTTP server {self.url}: {e}", exc_info=True)
            self._needs_oauth = False
            return False

    def _build_headers(self) -> Dict[str, str]:
        """Build HTTP headers including authentication"""
        headers = self.headers.copy()

        # Add authentication
        auth_type = self.auth_config.get("type")

        # For OAuth or bearer tokens
        if auth_type in ("bearer", "oauth"):
            # Try both 'token' and 'access_token' keys
            token = self.auth_config.get("token") or self.auth_config.get("access_token", "")
            if token:
                headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "api_key":
            key_name = self.auth_config.get("key_name", "X-API-Key")
            key_value = self.auth_config.get("key", "")
            headers[key_name] = key_value

        return headers

    def _is_token_expired(self) -> bool:
        """
        Check if OAuth token is expired or expiring soon.

        Returns True if token expires within 5 minutes.
        """
        expires_at_str = self.auth_config.get("expires_at")
        if not expires_at_str:
            return False

        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            # Consider expired if within 5 minutes of expiry
            return datetime.now() + timedelta(minutes=5) >= expires_at
        except (ValueError, TypeError):
            logger.warning(f"Invalid expires_at format: {expires_at_str}")
            return False

    async def _refresh_oauth_token(self) -> bool:
        """
        Refresh OAuth token using refresh token.

        Each user has their own refresh token; this method only updates the
        row for `(server_id, user_id)`. A per-instance lock prevents two
        concurrent tool calls from issuing duplicate refresh requests.

        Returns True if refresh successful, False otherwise.
        """
        async with self._refresh_lock:
            # Re-check expiry after acquiring the lock — another coroutine
            # may have already refreshed.
            if not self._is_token_expired():
                return True

            refresh_token = self.auth_config.get("refresh_token")
            if not refresh_token:
                logger.warning("No refresh token available for OAuth refresh")
                return False

            try:
                from open_notebook.database.repository import repo_query

                server_id = self.auth_config.get("server_id")
                user_id = self.auth_config.get("user_id") or self.user_id
                if not server_id:
                    logger.error("No server_id in auth_config for OAuth refresh")
                    return False
                if not user_id:
                    logger.error("No user_id in auth_config for OAuth refresh")
                    return False

                # OAuth client credentials are shared per server (RFC 7591).
                client_data_list = await repo_query(
                    "SELECT client_id, client_secret, registration_data "
                    "FROM mcp_oauth_clients WHERE server_id = :server_id",
                    {"server_id": server_id},
                )
                if not client_data_list:
                    logger.error(f"No OAuth client found for server {server_id}")
                    return False
                client_data = client_data_list[0]

                registration_info = (
                    json.loads(client_data["registration_data"])
                    if client_data["registration_data"]
                    else {}
                )
                token_url = registration_info.get("token_endpoint")
                if not token_url:
                    if not self.url:
                        logger.error("Server URL is not set, cannot construct token endpoint")
                        return False
                    base_url = (
                        self.url
                        if self.url.startswith(("http://", "https://"))
                        else f"https://{self.url}"
                    )
                    token_url = f"{base_url}/oauth/token"
                    logger.info(f"No token_endpoint in registration, constructing: {token_url}")

                if not token_url or not token_url.startswith(("http://", "https://")):
                    logger.error(f"Invalid token URL: '{token_url}'")
                    return False

                import base64

                client_id = client_data["client_id"]
                client_secret = client_data["client_secret"] or ""
                credentials = f"{client_id}:{client_secret}"
                encoded_credentials = base64.b64encode(credentials.encode()).decode()

                client = httpx.AsyncClient(timeout=30.0)
                try:
                    response = await client.post(
                        token_url,
                        data={
                            "grant_type": "refresh_token",
                            "refresh_token": refresh_token,
                        },
                        headers={
                            "Content-Type": "application/x-www-form-urlencoded",
                            "Authorization": f"Basic {encoded_credentials}",
                        },
                    )

                    if response.status_code == 200:
                        token_data = response.json()

                        # Update in-memory auth_config
                        self.auth_config["token"] = token_data["access_token"]
                        self.auth_config["access_token"] = token_data["access_token"]
                        if "refresh_token" in token_data:
                            self.auth_config["refresh_token"] = token_data["refresh_token"]
                        expires_in = token_data.get("expires_in", 3600)
                        expires_at = datetime.now() + timedelta(seconds=expires_in)
                        self.auth_config["expires_at"] = expires_at.isoformat()

                        # Persist for this (server_id, user_id) only
                        await self._save_auth_config(
                            server_id=server_id,
                            user_id=user_id,
                            token_data=token_data,
                            expires_at=expires_at,
                        )

                        logger.info(
                            f"OAuth token refreshed: server={server_id} user={user_id}"
                        )
                        return True
                    else:
                        logger.error(
                            f"OAuth refresh failed ({response.status_code}): {response.text}"
                        )
                        return False
                finally:
                    await client.aclose()

            except Exception as e:
                logger.error(f"Error refreshing OAuth token: {e}", exc_info=True)
                return False

    async def _save_auth_config(
        self,
        server_id: str,
        user_id: str,
        token_data: dict,
        expires_at: datetime,
    ):
        """
        Save refreshed OAuth tokens to the per-user row in mcp_oauth_tokens.

        Tokens are encrypted with the same Fernet helper that
        `mcp_servers.auth_config_encrypted` uses (`encrypt_password`), so
        `MCPClientFactory.create_client` can decrypt them on the next load.
        Only the (server_id, user_id) row is touched — other users sharing
        this server are unaffected.
        """
        from open_notebook.database.repository import repo_execute
        from api.routers.mcp_servers import encrypt_password

        new_access = token_data["access_token"]
        new_refresh = token_data.get(
            "refresh_token", self.auth_config.get("refresh_token")
        )

        encrypted_access = encrypt_password(new_access) if new_access else None
        encrypted_refresh = encrypt_password(new_refresh) if new_refresh else None

        await repo_execute(
            """
            INSERT OR REPLACE INTO mcp_oauth_tokens
            (server_id, user_id, access_token, refresh_token, expires_at, user_info, updated_at)
            VALUES (:server_id, :user_id, :access_token, :refresh_token, :expires_at, :user_info, :updated_at)
            """,
            {
                "server_id": server_id,
                "user_id": user_id,
                "access_token": encrypted_access,
                "refresh_token": encrypted_refresh,
                "expires_at": expires_at.isoformat(),
                "user_info": json.dumps(token_data.get("user_info", {})),
                "updated_at": datetime.now().isoformat(),
            },
        )

    def _parse_sse_response(self, sse_text: str) -> Dict[str, Any]:
        """
        Parse Server-Sent Events (SSE) response format.

        SSE format:
        event: message
        data: {"jsonrpc":"2.0","id":1,"result":{...}}

        Returns the parsed JSON from the data field.
        """
        lines = sse_text.strip().split('\n')
        data_line = None

        for line in lines:
            if line.startswith('data: '):
                data_line = line[6:]  # Remove 'data: ' prefix
                break

        if data_line:
            return json.loads(data_line)

        # If no data line found, try parsing the whole thing as JSON
        return json.loads(sse_text)

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        List available tools from MCP server via JSON-RPC.
        Sends tools/list request as per MCP protocol.
        """
        if not self.client:
            raise RuntimeError("MCP client not connected")

        try:
            # Check if server supports tools
            if "tools" not in self.server_capabilities:
                logger.info("Server does not support tools capability")
                return []

            # MCP tools/list request (JSON-RPC)
            self._request_id += 1
            request = {
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": "tools/list",
                "params": {}
            }

            response = await self.client.post(
                "/",
                json=request,
                headers={
                    **self._build_headers(),
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream"
                }
            )

            response.raise_for_status()

            # Parse response based on content type
            content_type = response.headers.get('content-type', '')
            if 'text/event-stream' in content_type:
                data = self._parse_sse_response(response.text)
            else:
                data = response.json()

            if data.get("result") and "tools" in data["result"]:
                tools = data["result"]["tools"]
                logger.info(f"Discovered {len(tools)} tools from MCP server")
                return tools

            return []
        except Exception as e:
            logger.error(f"Failed to list MCP tools: {e}")
            return []

    async def list_resources(self) -> List[Dict[str, Any]]:
        """
        List available resources from MCP server via JSON-RPC.
        Sends resources/list request as per MCP protocol.
        """
        if not self.client:
            raise RuntimeError("MCP client not connected")

        try:
            # Check if server supports resources
            if "resources" not in self.server_capabilities:
                logger.info("Server does not support resources capability")
                return []

            # MCP resources/list request (JSON-RPC)
            self._request_id += 1
            request = {
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": "resources/list",
                "params": {}
            }

            response = await self.client.post(
                "/",
                json=request,
                headers={
                    **self._build_headers(),
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream"
                }
            )

            response.raise_for_status()

            # Parse response based on content type
            content_type = response.headers.get('content-type', '')
            if 'text/event-stream' in content_type:
                data = self._parse_sse_response(response.text)
            else:
                data = response.json()

            if data.get("result") and "resources" in data["result"]:
                resources = data["result"]["resources"]
                logger.info(f"Discovered {len(resources)} resources from MCP server")
                return resources

            return []
        except Exception as e:
            logger.error(f"Failed to list MCP resources: {e}")
            return []

    async def list_prompts(self) -> List[Dict[str, Any]]:
        """
        List available prompts from MCP server via JSON-RPC.
        Sends prompts/list request as per MCP protocol.
        """
        if not self.client:
            raise RuntimeError("MCP client not connected")

        try:
            # Check if server supports prompts
            if "prompts" not in self.server_capabilities:
                logger.info("Server does not support prompts capability")
                return []

            # MCP prompts/list request (JSON-RPC)
            self._request_id += 1
            request = {
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": "prompts/list",
                "params": {}
            }

            response = await self.client.post(
                "/",
                json=request,
                headers={
                    **self._build_headers(),
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream"
                }
            )

            response.raise_for_status()

            # Parse response based on content type
            content_type = response.headers.get('content-type', '')
            if 'text/event-stream' in content_type:
                data = self._parse_sse_response(response.text)
            else:
                data = response.json()

            if data.get("result") and "prompts" in data["result"]:
                prompts = data["result"]["prompts"]
                logger.info(f"Discovered {len(prompts)} prompts from MCP server")
                return prompts

            return []
        except Exception as e:
            logger.error(f"Failed to list MCP prompts: {e}")
            return []
            response.raise_for_status()
            data = response.json()
            return data.get("prompts", [])
        except Exception as e:
            logger.error(f"Failed to list MCP prompts: {e}")
            return []

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """
        Execute a tool on the MCP server.

        Handles OAuth token refresh automatically on 401 response.
        """
        if not self.client:
            raise RuntimeError("MCP client not connected")

        # Check if OAuth token is expired and refresh if needed
        # OAuth can be stored as type "oauth" or "bearer" with refresh_token present
        has_oauth = (
            self.auth_config.get("type") in ("oauth", "bearer") and
            self.auth_config.get("refresh_token")
        )

        if has_oauth and self._is_token_expired():
            logger.info(f"OAuth token expired before tool call, refreshing...")
            await self._refresh_oauth_token()

        try:
            # MCP uses JSON-RPC format for tool calls
            request_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": name,
                    "arguments": arguments
                }
            }

            response = await self.client.post(
                "/",  # MCP HTTP uses root endpoint for JSON-RPC
                json=request_payload,
                headers={
                    **self._build_headers(),
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream"
                }
            )

            # Handle 401 - try refreshing token once if we have OAuth
            if response.status_code == 401 and has_oauth:
                logger.info(f"Received 401 during tool call, attempting token refresh...")
                refreshed = await self._refresh_oauth_token()

                if refreshed:
                    # Retry with new token
                    self.client = httpx.AsyncClient(
                        base_url=self.url,
                        headers=self._build_headers(),
                        timeout=30.0,
                    )
                    response = await self.client.post(
                        "/",
                        json=request_payload,
                        headers={
                            **self._build_headers(),
                            "Content-Type": "application/json",
                            "Accept": "application/json, text/event-stream"
                        }
                    )

            response.raise_for_status()

            # Check if response is SSE format
            content_type = response.headers.get('content-type', '')
            if 'text/event-stream' in content_type:
                # Parse SSE response
                result = self._parse_sse_response(response.text)
            else:
                # Regular JSON response
                result = response.json()

            # Extract result from JSON-RPC response
            if "result" in result:
                return result["result"].get("content", [])
            elif "error" in result:
                error = result["error"]
                raise RuntimeError(f"MCP error: {error.get('message', 'Unknown error')}")

            return result

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ConnectionError(f"Authentication failed for MCP server. Please reconnect.")
            elif e.response.status_code == 406:
                raise ConnectionError(f"Request not acceptable (406). The MCP server may require additional headers or authentication.")
            raise

    async def read_resource(self, uri: str) -> Any:
        """Read a resource from the MCP server"""
        if not self.client:
            raise RuntimeError("MCP client not connected")

        response = await self.client.post("/resources/read", json={"uri": uri})
        response.raise_for_status()
        return response.json()

    async def disconnect(self) -> None:
        """Close HTTP client connection"""
        if self.client:
            try:
                await self.client.aclose()
            except Exception as e:
                logger.error(f"Error disconnecting MCP HTTP client: {e}")
            finally:
                self.client = None
                self._connected = False


class MCPClientFactory:
    """Factory for creating appropriate MCP client based on protocol"""

    @staticmethod
    async def create_client(
        server_config: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> MCPClient:
        """
        Create MCP client instance based on server configuration.

        Args:
            server_config: Server configuration dict from database
            user_id: Authenticated user ID (the caller). For user-mode OAuth
                servers this selects which user's token row is loaded.
                For system-mode OAuth servers (`oauth_mode='system'`) the
                caller's id is replaced with `SYSTEM_OAUTH_USER_ID` so all
                users share a single token row and a single pooled client.
                For non-OAuth auth this is ignored.

        Returns:
            MCPClient instance (MCPStdioClient or MCPHttpClient)

        Raises:
            ValueError: If protocol is unsupported
        """
        protocol = server_config.get("protocol")

        if protocol == "stdio":
            return MCPStdioClient(
                command=server_config["command"],
                args=json.loads(server_config.get("args") or "[]"),
                env=json.loads(server_config.get("env_vars") or "{}")
            )

        elif protocol == "http":
            # Decrypt auth config if present
            from api.routers.mcp_servers import decrypt_password

            auth_encrypted = server_config.get("auth_config_encrypted")
            auth_config = {}
            if auth_encrypted:
                try:
                    auth_config = json.loads(decrypt_password(auth_encrypted))
                    logger.info(f"Decrypted auth config type: {auth_config.get('type')}")
                except Exception as e:
                    logger.error(f"Failed to decrypt auth config: {e}", exc_info=True)

            # For OAuth servers, load this user's tokens from mcp_oauth_tokens.
            # System-mode servers (`oauth_mode='system'`) collapse every
            # caller to a single shared row keyed on SYSTEM_OAUTH_USER_ID,
            # so all users share the same access token AND the same pooled
            # client (the per-instance refresh lock only works if there's
            # one instance).
            server_id = server_config.get("id")
            auth_type = server_config.get("auth_type")
            if auth_type == "oauth" and server_id:
                token_user_id = effective_token_user_id(server_config, user_id)
                if not token_user_id:
                    logger.warning(
                        f"OAuth server {server_id} requested without user_id; "
                        "client will report _needs_oauth=True"
                    )
                else:
                    try:
                        from open_notebook.database.repository import repo_query

                        oauth_tokens_list = await repo_query(
                            "SELECT access_token, refresh_token, expires_at "
                            "FROM mcp_oauth_tokens "
                            "WHERE server_id = :server_id AND user_id = :user_id",
                            {"server_id": server_id, "user_id": token_user_id},
                        )

                        if oauth_tokens_list:
                            oauth_tokens = oauth_tokens_list[0]
                            # Tokens are encrypted at rest; decrypt for use.
                            try:
                                access_plain = decrypt_password(oauth_tokens["access_token"]) if oauth_tokens["access_token"] else None
                                refresh_plain = (
                                    decrypt_password(oauth_tokens["refresh_token"])
                                    if oauth_tokens["refresh_token"]
                                    else None
                                )
                            except Exception as dec_err:
                                # Backwards compat: rows from before per-user
                                # migration may be plaintext. Fall back.
                                logger.warning(
                                    f"Token decrypt failed, treating as plaintext: {dec_err}"
                                )
                                access_plain = oauth_tokens["access_token"]
                                refresh_plain = oauth_tokens["refresh_token"]

                            auth_config["type"] = "oauth"
                            auth_config["access_token"] = access_plain
                            auth_config["token"] = access_plain  # For compatibility
                            auth_config["refresh_token"] = refresh_plain
                            auth_config["expires_at"] = oauth_tokens["expires_at"]
                            auth_config["server_id"] = server_id
                            # Stamp the *effective* user_id (the same value
                            # used for the SELECT) so refresh writes back
                            # to the correct row — '__system__' for system
                            # mode, the caller's UUID otherwise.
                            auth_config["user_id"] = token_user_id
                            logger.info(
                                f"Loaded OAuth tokens: server={server_id} user={token_user_id} "
                                f"expires={oauth_tokens['expires_at']}"
                            )
                        else:
                            logger.info(
                                f"No OAuth token for server={server_id} user={token_user_id}; "
                                "client will report _needs_oauth=True"
                            )
                    except Exception as e:
                        logger.error(f"Failed to load OAuth tokens: {e}", exc_info=True)

            # The MCPHttpClient also receives the *effective* user_id so
            # its refresh writeback path keys on the same row.
            return MCPHttpClient(
                url=server_config["url"],
                headers=json.loads(server_config.get("headers") or "{}"),
                auth_config=auth_config,
                server_id=server_id,
                user_id=(
                    effective_token_user_id(server_config, user_id)
                    if auth_type == "oauth"
                    else user_id
                ),
            )

        else:
            raise ValueError(f"Unsupported MCP protocol: {protocol}")


class MCPConnectionPool:
    """
    Manages active MCP client connections.

    Provides connection pooling to avoid repeatedly spawning/connecting
    to MCP servers for each tool call.

    Cache key shape: `f"{server_id}:{user_id}"` for OAuth servers (so two
    users using the same MCP server get isolated clients with their own
    bearer tokens), and `server_id` alone for non-OAuth servers (where the
    auth is shared and a single connection is fine).
    """

    def __init__(self):
        self._clients: Dict[str, MCPClient] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    @staticmethod
    def _cache_key(server_id: str, user_id: Optional[str]) -> str:
        """Compute the pool key. user_id is folded in only when present."""
        return f"{server_id}:{user_id}" if user_id else server_id

    async def get_client(
        self,
        server_id: str,
        server_config: Dict,
        user_id: Optional[str] = None,
    ) -> MCPClient:
        """
        Get or create MCP client for (server, user).

        For OAuth servers, pass `user_id` so each user gets their own
        client with their own access token. Omit `user_id` for non-OAuth
        servers (the cache then collapses to per-server).

        Returns:
            Connected MCPClient instance
        """
        key = self._cache_key(server_id, user_id)

        # Fast path
        if key in self._clients:
            return self._clients[key]

        async with self._get_lock(key):
            # Double-check after acquiring lock
            if key in self._clients:
                return self._clients[key]

            client = await MCPClientFactory.create_client(server_config, user_id=user_id)
            connected = await client.connect()

            if not connected:
                # Surface OAuth-needed as a distinct, recoverable error so
                # callers (e.g. the test endpoint) can route the user to
                # the authorize flow instead of a generic failure.
                if getattr(client, "_needs_oauth", False):
                    raise PermissionError(
                        f"OAuth required for MCP server {server_id} (user={user_id})"
                    )
                raise ConnectionError(f"Failed to connect to MCP server {server_id}")

            self._clients[key] = client
            return client

    async def disconnect(
        self,
        server_id: str,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Disconnect and remove client(s) from the pool.

        - With `user_id`: disconnects only that user's client for this server.
        - Without `user_id`: disconnects every cached client for this server
          (used when the server is deleted/edited).
        """
        if user_id is not None:
            key = self._cache_key(server_id, user_id)
            if key in self._clients:
                async with self._get_lock(key):
                    client = self._clients.pop(key, None)
                    if client:
                        await client.disconnect()
            return

        # No user_id: drop every entry whose key starts with server_id
        prefix = f"{server_id}:"
        keys_to_drop = [
            k for k in list(self._clients.keys())
            if k == server_id or k.startswith(prefix)
        ]
        for key in keys_to_drop:
            async with self._get_lock(key):
                client = self._clients.pop(key, None)
                if client:
                    await client.disconnect()

    async def disconnect_all(self) -> None:
        """Disconnect all clients in the pool"""
        keys = list(self._clients.keys())
        for key in keys:
            async with self._get_lock(key):
                client = self._clients.pop(key, None)
                if client:
                    await client.disconnect()

    def _get_lock(self, key: str) -> asyncio.Lock:
        """Get or create lock for a pool key."""
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]


# Global connection pool instance
mcp_pool = MCPConnectionPool()


async def discover_and_cache_capabilities(
    server_config: Dict[str, Any],
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Connect to an MCP server, list its tools / resources / prompts, and
    persist the result to `mcp_servers.capabilities` + `mcp_tools`.

    Used in two places:
      1. The `/test` endpoint (manual user click).
      2. The OAuth callback, immediately after a successful sign-in, so
         the server card lands showing real tool counts instead of
         requiring the user to press Test.

    The caller is responsible for permission gating; this function trusts
    the inputs. `user_id` selects which OAuth identity to use (per-user
    or `__system__`).

    Returns the capabilities dict. Raises ConnectionError / PermissionError
    if the connection fails — callers should map those to friendly
    messages.
    """
    from open_notebook.database.repository import repo_execute

    server_id = server_config["id"]
    now = datetime.now().isoformat()

    # Build a fresh client so we don't pin a stale pool entry to a
    # potentially-revoked token. The factory handles per-user vs system-
    # mode substitution internally.
    client = await MCPClientFactory.create_client(server_config, user_id=user_id)
    connected = await client.connect()
    if not connected:
        if getattr(client, "_needs_oauth", False):
            raise PermissionError(
                f"OAuth required for MCP server {server_id} (user={user_id})"
            )
        raise ConnectionError(f"Failed to connect to MCP server {server_id}")

    try:
        tools = await client.list_tools()
        resources = await client.list_resources()
        prompts = await client.list_prompts()
    finally:
        # We use a one-shot client here, not the pool, so close it.
        try:
            await client.disconnect()
        except Exception:
            pass

    capabilities = {"tools": tools, "resources": resources, "prompts": prompts}

    # Persist server-level capabilities cache.
    await repo_execute(
        """
        UPDATE mcp_servers
        SET status = :status,
            last_test_at = :last_test_at,
            last_test_message = :last_test_message,
            capabilities = :capabilities,
            updated_at = :updated_at
        WHERE id = :id
        """,
        {
            "status": "connected",
            "last_test_at": now,
            "last_test_message": (
                f"Discovered {len(tools)} tools, {len(resources)} resources, "
                f"{len(prompts)} prompts."
            ),
            "capabilities": json.dumps(capabilities),
            "updated_at": now,
            "id": server_id,
        },
    )

    # Replace the per-tool cache wholesale — schemas can change between
    # discoveries, and stale rows would confuse the tool factory.
    await repo_execute(
        "DELETE FROM mcp_tools WHERE server_id = :server_id",
        {"server_id": server_id},
    )
    for tool in tools:
        await repo_execute(
            """
            INSERT INTO mcp_tools (id, server_id, tool_name, description, input_schema, discovered_at)
            VALUES (:id, :server_id, :tool_name, :description, :input_schema, :discovered_at)
            """,
            {
                "id": f"{server_id}:{tool['name']}",
                "server_id": server_id,
                "tool_name": tool["name"],
                "description": tool.get("description", ""),
                "input_schema": json.dumps(tool.get("inputSchema", {})),
                "discovered_at": now,
            },
        )

    logger.info(
        f"Discovered MCP capabilities: server={server_id} user={user_id} "
        f"tools={len(tools)} resources={len(resources)} prompts={len(prompts)}"
    )
    return capabilities
