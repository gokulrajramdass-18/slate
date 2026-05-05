"""
API Key Domain Model

Manages API keys for external application authentication.
"""

import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from open_notebook.database.repository import repo_execute, repo_query


@dataclass
class APIKey:
    """API Key domain model"""
    id: str
    name: str
    description: Optional[str]
    key_hash: str
    key_prefix: str
    scopes: List[str]
    owner_id: str
    application_name: Optional[str]
    last_used_at: Optional[datetime]
    usage_count: int
    is_active: bool
    expires_at: Optional[datetime]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    @staticmethod
    def _hash_key(api_key: str) -> str:
        """Hash an API key using SHA-256"""
        return hashlib.sha256(api_key.encode()).hexdigest()

    @staticmethod
    def _generate_key() -> tuple[str, str, str]:
        """
        Generate a new API key

        Returns:
            tuple: (full_key, key_hash, key_prefix)
        """
        # Generate a secure random key (32 bytes = 64 hex chars)
        full_key = f"sk_{secrets.token_urlsafe(32)}"
        key_hash = APIKey._hash_key(full_key)
        key_prefix = full_key[:12]  # First 12 chars for identification

        return full_key, key_hash, key_prefix

    @staticmethod
    async def create(
        name: str,
        owner_id: str,
        scopes: List[str],
        description: Optional[str] = None,
        application_name: Optional[str] = None,
        expires_in_days: Optional[int] = None
    ) -> tuple["APIKey", str]:
        """
        Create a new API key

        Args:
            name: Friendly name for the key
            owner_id: User who owns this key
            scopes: List of allowed scopes (e.g., ['notifications:write'])
            description: Optional description
            application_name: Name of the external application
            expires_in_days: Optional expiration in days

        Returns:
            tuple: (APIKey object, plain_text_key)
                   Note: plain_text_key is only returned once and not stored
        """
        api_key_id = str(uuid.uuid4())
        now = datetime.utcnow()
        expires_at = now + timedelta(days=expires_in_days) if expires_in_days else None

        # Generate key
        plain_key, key_hash, key_prefix = APIKey._generate_key()

        await repo_execute(
            """
            INSERT INTO api_keys (
                id, name, description, key_hash, key_prefix, scopes,
                owner_id, application_name, expires_at, created_at, updated_at
            ) VALUES (
                :id, :name, :description, :key_hash, :key_prefix, :scopes,
                :owner_id, :application_name, :expires_at, :created_at, :updated_at
            )
            """,
            {
                "id": api_key_id,
                "name": name,
                "description": description,
                "key_hash": key_hash,
                "key_prefix": key_prefix,
                "scopes": json.dumps(scopes),
                "owner_id": owner_id,
                "application_name": application_name,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            }
        )

        api_key = await APIKey.get(api_key_id)
        return api_key, plain_key

    @staticmethod
    async def get(api_key_id: str) -> Optional["APIKey"]:
        """Get an API key by ID"""
        rows = await repo_query(
            "SELECT * FROM api_keys WHERE id = :id",
            {"id": api_key_id}
        )

        if not rows:
            return None

        return APIKey._from_row(rows[0])

    @staticmethod
    async def get_by_key_hash(key_hash: str) -> Optional["APIKey"]:
        """Get an API key by its hash"""
        rows = await repo_query(
            "SELECT * FROM api_keys WHERE key_hash = :key_hash",
            {"key_hash": key_hash}
        )

        if not rows:
            return None

        return APIKey._from_row(rows[0])

    @staticmethod
    async def verify_key(plain_key: str) -> Optional["APIKey"]:
        """
        Verify an API key and return the APIKey object if valid

        Args:
            plain_key: The plain text API key to verify

        Returns:
            APIKey object if valid, None otherwise
        """
        key_hash = APIKey._hash_key(plain_key)
        api_key = await APIKey.get_by_key_hash(key_hash)

        if not api_key:
            return None

        # Check if active
        if not api_key.is_active:
            return None

        # Check if expired
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            return None

        # Update last used timestamp
        await api_key.record_usage()

        return api_key

    @staticmethod
    async def list_by_owner(owner_id: str, include_inactive: bool = False) -> List["APIKey"]:
        """Get all API keys for an owner"""
        query = "SELECT * FROM api_keys WHERE owner_id = :owner_id"
        params: Dict[str, Any] = {"owner_id": owner_id}

        if not include_inactive:
            query += " AND is_active = 1"

        query += " ORDER BY created_at DESC"

        rows = await repo_query(query, params)
        return [APIKey._from_row(row) for row in rows]

    async def record_usage(self) -> None:
        """Record API key usage (updates last_used_at and usage_count)"""
        await repo_execute(
            """
            UPDATE api_keys
            SET last_used_at = :now, usage_count = usage_count + 1
            WHERE id = :id
            """,
            {"id": self.id, "now": datetime.utcnow().isoformat()}
        )
        self.last_used_at = datetime.utcnow()
        self.usage_count += 1

    async def log_usage(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_body: Optional[Dict] = None,
        response_body: Optional[Dict] = None,
        error: Optional[str] = None
    ) -> None:
        """Log API key usage for audit trail"""
        await repo_execute(
            """
            INSERT INTO api_key_usage_logs (
                id, api_key_id, endpoint, method, status_code,
                ip_address, user_agent, request_body, response_body, error
            ) VALUES (
                :id, :api_key_id, :endpoint, :method, :status_code,
                :ip_address, :user_agent, :request_body, :response_body, :error
            )
            """,
            {
                "id": str(uuid.uuid4()),
                "api_key_id": self.id,
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "request_body": json.dumps(request_body) if request_body else None,
                "response_body": json.dumps(response_body) if response_body else None,
                "error": error
            }
        )

    async def revoke(self) -> None:
        """Revoke (deactivate) the API key"""
        await repo_execute(
            "UPDATE api_keys SET is_active = 0, updated_at = :now WHERE id = :id",
            {"id": self.id, "now": datetime.utcnow().isoformat()}
        )
        self.is_active = False

    async def delete(self) -> None:
        """Delete the API key"""
        await repo_execute(
            "DELETE FROM api_keys WHERE id = :id",
            {"id": self.id}
        )

    def has_scope(self, required_scope: str) -> bool:
        """Check if API key has a required scope"""
        return required_scope in self.scopes

    @staticmethod
    def _from_row(row: Dict[str, Any]) -> "APIKey":
        """Convert database row to APIKey object"""
        scopes = []
        if row.get("scopes"):
            try:
                scopes = json.loads(row["scopes"])
            except json.JSONDecodeError:
                scopes = []

        return APIKey(
            id=row["id"],
            name=row["name"],
            description=row.get("description"),
            key_hash=row["key_hash"],
            key_prefix=row["key_prefix"],
            scopes=scopes,
            owner_id=row["owner_id"],
            application_name=row.get("application_name"),
            last_used_at=datetime.fromisoformat(row["last_used_at"]) if row.get("last_used_at") else None,
            usage_count=row.get("usage_count", 0),
            is_active=bool(row.get("is_active", 1)),
            expires_at=datetime.fromisoformat(row["expires_at"]) if row.get("expires_at") else None,
            created_at=datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else None
        )

    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "key_prefix": self.key_prefix,
            "scopes": self.scopes,
            "owner_id": self.owner_id,
            "application_name": self.application_name,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "usage_count": self.usage_count,
            "is_active": self.is_active,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

        if include_sensitive:
            result["key_hash"] = self.key_hash

        return result
