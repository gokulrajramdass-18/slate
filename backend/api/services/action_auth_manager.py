"""
Action Auth Manager

Wrapper around APIAuthManager for actions authentication.

Handles:
- Bearer tokens
- API keys (header/query)
- Basic auth
- OAuth2 client credentials (with token refresh)

Reuses existing APIAuthManager from api_source.py
"""

import json
import logging
import base64
from typing import Dict, Any, Optional
import httpx

from open_notebook.sources.api_source import APIAuthManager as BaseAPIAuthManager
from open_notebook.config import get_encryption_key
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class ActionAuthManager:
    """
    Authentication manager for actions.

    Wraps APIAuthManager to provide consistent auth across webhooks.
    """

    def __init__(self, action: Dict[str, Any]):
        """
        Initialize auth manager from action config.

        Args:
            action: Action dict with auth_type and auth_config_encrypted
        """
        self.action = action
        self.auth_type = action.get("auth_type", "none")

        # Decrypt auth config
        auth_config = self._decrypt_auth_config(action.get("auth_config_encrypted"))

        # Build config in format expected by APIAuthManager
        self.config = {
            "auth_type": self.auth_type,
            "auth_config": auth_config or {},
        }

        # Create underlying auth manager
        self.auth_manager = BaseAPIAuthManager({"connection_config": self.config})

    async def get_client(self) -> httpx.AsyncClient:
        """
        Get authenticated HTTP client.

        Returns:
            httpx.AsyncClient with authentication configured
        """
        try:
            return await self.auth_manager.get_client()
        except Exception as e:
            logger.error(f"Failed to create authenticated client: {e}")
            # Fall back to unauthenticated client
            return httpx.AsyncClient(timeout=30.0)

    def _decrypt_auth_config(self, encrypted: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Decrypt authentication configuration using Fernet.

        Args:
            encrypted: Base64-encoded encrypted JSON

        Returns:
            Decrypted auth config dict or None
        """
        if not encrypted:
            return None

        key = get_encryption_key()
        if not key:
            logger.warning("Encryption key not configured, cannot decrypt auth config")
            return None

        try:
            fernet = Fernet(key.encode())
            encrypted_bytes = base64.b64decode(encrypted.encode())
            decrypted = fernet.decrypt(encrypted_bytes)
            return json.loads(decrypted.decode())
        except Exception as e:
            logger.error(f"Failed to decrypt auth config: {e}")
            return None

    @staticmethod
    def supports_auth_type(auth_type: str) -> bool:
        """
        Check if auth type is supported.

        Args:
            auth_type: Authentication type

        Returns:
            True if supported, False otherwise
        """
        supported_types = [
            "none",
            "basic",
            "bearer",
            "api_key",
            "oauth2_client",
        ]
        return auth_type in supported_types

    @staticmethod
    def get_supported_auth_types() -> list:
        """
        Get list of supported authentication types.

        Returns:
            List of auth type strings
        """
        return [
            {
                "type": "none",
                "name": "No Authentication",
                "description": "No authentication required",
            },
            {
                "type": "basic",
                "name": "Basic Auth",
                "description": "Username and password authentication",
                "fields": ["username", "password"],
            },
            {
                "type": "bearer",
                "name": "Bearer Token",
                "description": "Bearer token in Authorization header",
                "fields": ["token"],
            },
            {
                "type": "api_key",
                "name": "API Key",
                "description": "API key in header or query parameter",
                "fields": ["key", "value", "location"],
            },
            {
                "type": "oauth2_client",
                "name": "OAuth 2.0 Client Credentials",
                "description": "OAuth 2.0 client credentials flow with automatic token refresh",
                "fields": ["client_id", "client_secret", "token_url", "scope"],
            },
        ]


# ============================================================================
# Convenience Functions
# ============================================================================

async def create_authenticated_client(action: Dict[str, Any]) -> httpx.AsyncClient:
    """
    Create authenticated HTTP client for an action.

    Convenience function for quick client creation.

    Args:
        action: Action dict with auth config

    Returns:
        Authenticated httpx.AsyncClient
    """
    auth_manager = ActionAuthManager(action)
    return await auth_manager.get_client()


def get_auth_config_schema(auth_type: str) -> Optional[Dict[str, Any]]:
    """
    Get JSON schema for auth config based on auth type.

    Useful for frontend form generation.

    Args:
        auth_type: Authentication type

    Returns:
        JSON schema dict or None if unsupported
    """
    schemas = {
        "none": {},
        "basic": {
            "type": "object",
            "required": ["username", "password"],
            "properties": {
                "username": {"type": "string", "description": "Username"},
                "password": {"type": "string", "description": "Password", "format": "password"},
            },
        },
        "bearer": {
            "type": "object",
            "required": ["token"],
            "properties": {
                "token": {"type": "string", "description": "Bearer token", "format": "password"},
            },
        },
        "api_key": {
            "type": "object",
            "required": ["key", "value", "location"],
            "properties": {
                "key": {"type": "string", "description": "API key name (e.g., X-API-Key)"},
                "value": {"type": "string", "description": "API key value", "format": "password"},
                "location": {
                    "type": "string",
                    "enum": ["header", "query"],
                    "description": "Where to include the API key",
                },
            },
        },
        "oauth2_client": {
            "type": "object",
            "required": ["client_id", "client_secret", "token_url"],
            "properties": {
                "client_id": {"type": "string", "description": "OAuth client ID"},
                "client_secret": {"type": "string", "description": "OAuth client secret", "format": "password"},
                "token_url": {"type": "string", "description": "Token endpoint URL", "format": "uri"},
                "scope": {"type": "string", "description": "OAuth scopes (optional)"},
            },
        },
    }

    return schemas.get(auth_type)
