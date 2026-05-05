"""
HANA Connection Utilities

Shared utilities for HANA connection management.
Avoids circular imports by providing encryption and query functions.
"""

from typing import Optional
import base64
from cryptography.fernet import Fernet

from open_notebook.config import get_encryption_key
from open_notebook.database.repository import repo_query


# ============================================================================
# Encryption Functions
# ============================================================================

def encrypt_password(password: str) -> str:
    """Encrypt password using Fernet encryption"""
    key = get_encryption_key()
    if not key:
        # If no encryption key set, store as-is (not recommended for production)
        return password

    fernet = Fernet(key.encode())
    encrypted = fernet.encrypt(password.encode())
    return base64.b64encode(encrypted).decode()


def decrypt_password(encrypted_password: str) -> str:
    """Decrypt password"""
    key = get_encryption_key()
    if not key:
        # If no encryption key set, assume unencrypted
        return encrypted_password

    try:
        fernet = Fernet(key.encode())
        encrypted_bytes = base64.b64decode(encrypted_password.encode())
        decrypted = fernet.decrypt(encrypted_bytes)
        return decrypted.decode()
    except:
        # Fallback: return as-is if decryption fails
        return encrypted_password


# ============================================================================
# Database Query Functions
# ============================================================================

async def get_connection_by_id(connection_id: str) -> Optional[dict]:
    """Get connection by ID"""
    sql = "SELECT * FROM hana_connections WHERE id = :id"
    results = await repo_query(sql, {"id": connection_id})
    return results[0] if results else None
