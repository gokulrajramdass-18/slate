"""
HTTP Client Pool

Singleton manager for shared httpx.AsyncClient instances with connection pooling.
Avoids creating a new TCP connection for every outbound HTTP request.
"""

import httpx
from typing import Optional


class HTTPClientManager:
    """
    Manages a shared httpx.AsyncClient with sensible connection limits.

    Usage:
        from api.services.http_client import http_client_manager

        client = http_client_manager.get_client()
        response = await client.get("https://example.com")

    The client is lazily created on first access and reused across the
    application lifetime. Call close() during shutdown.
    """

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    def get_client(self, timeout: float = 30.0) -> httpx.AsyncClient:
        """
        Return the shared AsyncClient, creating it lazily if needed.

        Note: The default timeout on the shared client is 30s.
        For individual requests that need a different timeout, pass
        `timeout=` directly to the request method (get/post/etc.).

        Args:
            timeout: Default timeout for the client if it needs to be created.

        Returns:
            Shared httpx.AsyncClient
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=timeout,
                limits=httpx.Limits(
                    max_connections=100,
                    max_keepalive_connections=20,
                    keepalive_expiry=30,
                ),
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Close the shared client. Safe to call multiple times."""
        if self._client is not None and not self._client.is_closed:
            await self._client.close()
            self._client = None


# Module-level singleton
http_client_manager = HTTPClientManager()
