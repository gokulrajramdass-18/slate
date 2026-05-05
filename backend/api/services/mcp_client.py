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

    def __init__(self, url: str, headers: Dict[str, str], auth_config: Dict, server_id: str = None):
        """
        Initialize HTTP MCP client.

        Args:
            url: Base URL of MCP server
            headers: Additional HTTP headers
            auth_config: Authentication configuration
            server_id: MCP server identifier (for OAuth token refresh)
        """
        self.url = url.rstrip("/")
        self.headers = headers or {}
        self.auth_config = auth_config or {}
        # Store server_id for OAuth token refresh
        if server_id:
            self.auth_config["server_id"] = server_id
        self.client: Optional[httpx.AsyncClient] = None
        self._connected = False
        self._needs_oauth = False  # Track if OAuth is required
        self.server_capabilities: Dict[str, Any] = {}
        self.server_info: Dict[str, Any] = {}
        self._request_id = 1  # For JSON-RPC request IDs

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

        Returns True if refresh successful, False otherwise.
        """
        refresh_token = self.auth_config.get("refresh_token")
        if not refresh_token:
            logger.warning("No refresh token available for OAuth refresh")
            return False

        try:
            # Get OAuth client credentials from database
            from open_notebook.database.repository import repo_query

            server_id = self.auth_config.get("server_id")
            if not server_id:
                logger.error("No server_id in auth_config for OAuth refresh")
                return False

            # Get OAuth client credentials
            client_data_list = await repo_query(
                "SELECT client_id, client_secret, registration_data FROM mcp_oauth_clients WHERE server_id = :server_id",
                {"server_id": server_id}
            )

            if not client_data_list:
                logger.error(f"No OAuth client found for server {server_id}")
                return False

            client_data = client_data_list[0]  # Get first result

            # Parse registration data to get token endpoint
            registration_info = json.loads(client_data["registration_data"]) if client_data["registration_data"] else {}
            token_url = registration_info.get("token_endpoint")

            # Fallback to constructing from server URL if not in registration data
            if not token_url:
                # Ensure self.url exists and has protocol
                if not self.url:
                    logger.error("Server URL is not set, cannot construct token endpoint")
                    return False

                base_url = self.url if self.url.startswith(('http://', 'https://')) else f"https://{self.url}"
                token_url = f"{base_url}/oauth/token"
                logger.info(f"No token_endpoint in registration, constructing: {token_url}")

            # Validate token_url has protocol
            if not token_url or not token_url.startswith(('http://', 'https://')):
                logger.error(f"Invalid token URL (missing protocol or empty): '{token_url}'")
                return False

            # Call token refresh endpoint
            # OAuth 2.0 requires client credentials via HTTP Basic Auth
            import base64

            client_id = client_data["client_id"]
            client_secret = client_data["client_secret"] or ""

            # Create Basic Auth header
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
                        "Authorization": f"Basic {encoded_credentials}"
                    }
                )

                if response.status_code == 200:
                    token_data = response.json()

                    # Update auth_config with new tokens
                    self.auth_config["token"] = token_data["access_token"]
                    self.auth_config["access_token"] = token_data["access_token"]

                    if "refresh_token" in token_data:
                        self.auth_config["refresh_token"] = token_data["refresh_token"]

                    # Calculate expiry
                    expires_in = token_data.get("expires_in", 3600)
                    expires_at = datetime.now() + timedelta(seconds=expires_in)
                    self.auth_config["expires_at"] = expires_at.isoformat()

                    # Save to database
                    await self._save_auth_config(server_id, token_data, expires_at)

                    logger.info(f"OAuth token refreshed successfully for server {server_id}")
                    return True
                else:
                    logger.error(f"OAuth refresh failed with status {response.status_code}: {response.text}")
                    return False

            finally:
                await client.aclose()

        except Exception as e:
            logger.error(f"Error refreshing OAuth token: {e}", exc_info=True)
            return False

    async def _save_auth_config(self, server_id: str, token_data: dict, expires_at: datetime):
        """
        Save updated OAuth tokens to database.

        Args:
            server_id: MCP server ID
            token_data: Token response from OAuth server
            expires_at: Token expiration time
        """
        from open_notebook.database.repository import repo_execute

        await repo_execute("""
            INSERT OR REPLACE INTO mcp_oauth_tokens
            (server_id, access_token, refresh_token, expires_at, user_info, updated_at)
            VALUES (:server_id, :access_token, :refresh_token, :expires_at, :user_info, :updated_at)
        """, {
            "server_id": server_id,
            "access_token": token_data["access_token"],
            "refresh_token": token_data.get("refresh_token", self.auth_config.get("refresh_token")),
            "expires_at": expires_at.isoformat(),
            "user_info": json.dumps(token_data.get("user_info", {})),
            "updated_at": datetime.now().isoformat()
        })

        # Also update the server's auth_config_encrypted field
        from api.services.encryption import encrypt_data

        encrypted_auth = encrypt_data(json.dumps(self.auth_config))
        await repo_execute("""
            UPDATE mcp_servers
            SET auth_config_encrypted = :auth_config
            WHERE id = :server_id
        """, {
            "server_id": server_id,
            "auth_config": encrypted_auth
        })

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
    async def create_client(server_config: Dict[str, Any]) -> MCPClient:
        """
        Create MCP client instance based on server configuration.

        Args:
            server_config: Server configuration dict from database

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

            # For OAuth servers, load tokens from mcp_oauth_tokens table
            server_id = server_config.get("id")
            auth_type = server_config.get("auth_type")
            if auth_type == "oauth" and server_id:
                try:
                    from open_notebook.database.repository import repo_query

                    oauth_tokens_list = await repo_query(
                        "SELECT access_token, refresh_token, expires_at FROM mcp_oauth_tokens WHERE server_id = :server_id",
                        {"server_id": server_id}
                    )

                    if oauth_tokens_list:
                        oauth_tokens = oauth_tokens_list[0]  # Get first result
                        # Merge OAuth tokens into auth_config
                        auth_config["access_token"] = oauth_tokens["access_token"]
                        auth_config["token"] = oauth_tokens["access_token"]  # For compatibility
                        auth_config["refresh_token"] = oauth_tokens["refresh_token"]
                        auth_config["expires_at"] = oauth_tokens["expires_at"]
                        auth_config["server_id"] = server_id  # For refresh
                        logger.info(f"Loaded OAuth tokens for server {server_id}, expires: {oauth_tokens['expires_at']}")
                except Exception as e:
                    logger.error(f"Failed to load OAuth tokens: {e}", exc_info=True)

            return MCPHttpClient(
                url=server_config["url"],
                headers=json.loads(server_config.get("headers") or "{}"),
                auth_config=auth_config,
                server_id=server_id  # Pass server_id for OAuth refresh
            )

        else:
            raise ValueError(f"Unsupported MCP protocol: {protocol}")


class MCPConnectionPool:
    """
    Manages active MCP client connections.

    Provides connection pooling to avoid repeatedly spawning/connecting
    to MCP servers for each tool call.
    """

    def __init__(self):
        self._clients: Dict[str, MCPClient] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    async def get_client(self, server_id: str, server_config: Dict) -> MCPClient:
        """
        Get or create MCP client for server.

        Args:
            server_id: Unique server identifier
            server_config: Server configuration from database

        Returns:
            Connected MCPClient instance
        """
        # Check if already connected
        if server_id in self._clients:
            return self._clients[server_id]

        # Acquire lock for this server
        async with self._get_lock(server_id):
            # Double-check after acquiring lock
            if server_id in self._clients:
                return self._clients[server_id]

            # Create and connect new client (factory is now async)
            client = await MCPClientFactory.create_client(server_config)
            connected = await client.connect()

            if not connected:
                raise ConnectionError(f"Failed to connect to MCP server {server_id}")

            self._clients[server_id] = client
            return client

    async def disconnect(self, server_id: str) -> None:
        """
        Disconnect and remove client from pool.

        Args:
            server_id: Server identifier to disconnect
        """
        if server_id in self._clients:
            async with self._get_lock(server_id):
                client = self._clients.pop(server_id, None)
                if client:
                    await client.disconnect()

    async def disconnect_all(self) -> None:
        """Disconnect all clients in the pool"""
        server_ids = list(self._clients.keys())
        for server_id in server_ids:
            await self.disconnect(server_id)

    def _get_lock(self, server_id: str) -> asyncio.Lock:
        """Get or create lock for server"""
        if server_id not in self._locks:
            self._locks[server_id] = asyncio.Lock()
        return self._locks[server_id]


# Global connection pool instance
mcp_pool = MCPConnectionPool()
