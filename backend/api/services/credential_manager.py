"""
Credential Manager Service

Provides a unified interface for credential storage with automatic
synchronization between in-memory store and database.

This fixes the issue where agents can't find credentials configured
via the UI because they're stored in memory but not synced to database.
"""

import json
import logging
from typing import Dict, Optional, Any
from datetime import datetime

from open_notebook.database.repository import repo_query, repo_execute, repo_create, repo_update

logger = logging.getLogger(__name__)


class CredentialManager:
    """
    Manages credential storage with automatic sync between memory and database.

    This class ensures that:
    1. Credentials can be looked up by ID (UUID) or name (model name)
    2. In-memory store is synced with database
    3. Agents can find credentials regardless of how they query
    """

    def __init__(self):
        self._memory_store: Dict[str, Dict[str, Any]] = {}
        self._name_to_id_map: Dict[str, str] = {}

    async def initialize(self):
        """Load all credentials from database into memory on startup."""
        logger.info("🔄 Initializing CredentialManager - loading from database...")

        try:
            # Load credentials from database
            credentials = await repo_query("SELECT * FROM credentials")

            for cred in credentials:
                cred_dict = dict(cred)
                cred_id = cred_dict["id"]
                cred_name = cred_dict["name"]

                # Store in memory by ID
                self._memory_store[cred_id] = cred_dict

                # Store name-to-ID mapping
                self._name_to_id_map[cred_name] = cred_id

                logger.debug(f"  Loaded credential: {cred_name} (ID: {cred_id})")

            logger.info(f"✅ Loaded {len(credentials)} credential(s) from database")

        except Exception as e:
            logger.warning(f"Could not load credentials from database: {e}")
            # Continue with empty store - will sync when credentials are added

    def register_in_memory_credential(
        self,
        cred_id: str,
        credential: Dict[str, Any]
    ):
        """
        Register a credential from the in-memory _credentials_store.

        This is called to sync existing in-memory credentials to the manager.

        Args:
            cred_id: Credential ID (UUID)
            credential: Credential data dict
        """
        self._memory_store[cred_id] = credential

        # Store name-to-ID mapping
        if "model_name" in credential:
            self._name_to_id_map[credential["model_name"]] = cred_id
        if "name" in credential:
            self._name_to_id_map[credential["name"]] = cred_id

    async def sync_to_database(self, cred_id: str):
        """
        Sync a credential from memory to database.

        Args:
            cred_id: Credential ID to sync
        """
        if cred_id not in self._memory_store:
            logger.warning(f"Credential {cred_id} not in memory, cannot sync")
            return

        credential = self._memory_store[cred_id]

        try:
            # Check if credential exists in database
            existing = await repo_query(
                "SELECT id FROM credentials WHERE id = :id",
                {"id": cred_id},
                fetch_one=True
            )

            data = {
                "id": cred_id,
                "name": credential.get("name") or credential.get("model_name", "Unknown"),
                "provider": credential.get("provider", "openai"),
                "modalities": json.dumps(credential.get("modalities", [])),
                "api_key_encrypted": credential.get("api_key_encrypted"),
                "base_url": credential.get("base_url"),
                "created": credential.get("created", datetime.utcnow().isoformat()),
                "updated": datetime.utcnow().isoformat()
            }

            if existing:
                # Update existing
                await repo_update("credentials", cred_id, data)
                logger.debug(f"✅ Updated credential in database: {cred_id}")
            else:
                # Create new
                await repo_create("credentials", data)
                logger.debug(f"✅ Created credential in database: {cred_id}")

        except Exception as e:
            logger.error(f"Failed to sync credential {cred_id} to database: {e}")

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get a credential by ID or name.

        Args:
            key: Credential ID (UUID) or model name

        Returns:
            Credential dict or None if not found
        """
        # Try direct ID lookup first
        if key in self._memory_store:
            return self._memory_store[key]

        # Try name-to-ID mapping
        if key in self._name_to_id_map:
            cred_id = self._name_to_id_map[key]
            return self._memory_store.get(cred_id)

        # Not found
        logger.debug(f"Credential not found: {key}")
        return None

    def get_by_id(self, cred_id: str) -> Optional[Dict[str, Any]]:
        """Get credential by ID only."""
        return self._memory_store.get(cred_id)

    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get credential by name only."""
        cred_id = self._name_to_id_map.get(name)
        if cred_id:
            return self._memory_store.get(cred_id)
        return None

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """Get all credentials."""
        return self._memory_store.copy()

    async def import_from_legacy_store(self, legacy_store: Dict[str, Dict[str, Any]]):
        """
        Import credentials from legacy _credentials_store.

        Args:
            legacy_store: The existing _credentials_store dict
        """
        logger.info(f"🔄 Importing {len(legacy_store)} credential(s) from legacy store...")

        for cred_id, credential in legacy_store.items():
            # Register in memory
            self.register_in_memory_credential(cred_id, credential)

            # Sync to database
            await self.sync_to_database(cred_id)

        logger.info(f"✅ Imported {len(legacy_store)} credential(s)")


# Global instance
_credential_manager: Optional[CredentialManager] = None


def get_credential_manager() -> CredentialManager:
    """Get or create the CredentialManager singleton."""
    global _credential_manager
    if _credential_manager is None:
        _credential_manager = CredentialManager()
    return _credential_manager


async def initialize_credential_manager():
    """Initialize the credential manager and load credentials."""
    manager = get_credential_manager()
    await manager.initialize()
    return manager
