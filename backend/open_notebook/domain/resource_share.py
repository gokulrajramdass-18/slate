"""
Resource sharing domain model.

Provides ResourceShare model for collaborative access to resources.
"""

from datetime import datetime
from typing import ClassVar, List, Optional

from open_notebook.constants import PERMISSION_ADMIN, PERMISSION_READ, PERMISSION_WRITE
from open_notebook.database.repository import repo_execute, repo_query
from open_notebook.domain.base import ObjectModel


class ResourceShare(ObjectModel):
    """
    Resource sharing model for collaborative access.

    Allows users to share resources (workspaces, agents, tools, etc.) with other users
    or roles with specific permission levels.

    Attributes:
        resource_type: Type of resource being shared (workspace, agent, tool, etc.)
        resource_id: ID of the resource being shared
        shared_by: User ID who owns and is sharing the resource
        shared_with_user: User ID to share with (if user-based sharing)
        shared_with_role: Role ID to share with (if role-based sharing)
        permission_level: Level of access (read, write, admin)
        expires_at: Optional expiration timestamp
    """

    _table_name: ClassVar[str] = "resource_shares"
    _exclude_fields: ClassVar[List[str]] = []

    resource_type: str
    resource_id: str
    shared_by: str
    shared_with_user: Optional[str] = None
    shared_with_role: Optional[str] = None
    permission_level: str = PERMISSION_READ
    expires_at: Optional[datetime] = None

    @classmethod
    async def get_for_resource(
        cls, resource_type: str, resource_id: str
    ) -> List["ResourceShare"]:
        """Get all shares for a specific resource."""
        sql = """
            SELECT * FROM resource_shares
            WHERE resource_type = :resource_type AND resource_id = :resource_id
            ORDER BY created DESC
        """
        results = await repo_query(
            sql, {"resource_type": resource_type, "resource_id": resource_id}
        )
        return [cls(**row) for row in results]

    @classmethod
    async def get_for_user(cls, user_id: str) -> List["ResourceShare"]:
        """Get all resources shared with a specific user."""
        sql = """
            SELECT * FROM resource_shares
            WHERE shared_with_user = :user_id
            AND (expires_at IS NULL OR expires_at > :now)
            ORDER BY created DESC
        """
        results = await repo_query(sql, {"user_id": user_id, "now": datetime.utcnow()})
        return [cls(**row) for row in results]

    @classmethod
    async def get_shared_by_user(cls, user_id: str) -> List["ResourceShare"]:
        """Get all resources shared by a specific user."""
        sql = """
            SELECT * FROM resource_shares
            WHERE shared_by = :user_id
            ORDER BY created DESC
        """
        results = await repo_query(sql, {"user_id": user_id})
        return [cls(**row) for row in results]

    @classmethod
    async def check_access(
        cls,
        user_id: str,
        resource_type: str,
        resource_id: str,
        required_permission: str = PERMISSION_READ,
    ) -> bool:
        """
        Check if a user has access to a resource via sharing.

        Args:
            user_id: User ID to check access for
            resource_type: Type of resource
            resource_id: ID of the resource
            required_permission: Minimum permission level required (read, write, admin)

        Returns:
            True if user has access at the required level or higher
        """
        # Permission hierarchy: admin > write > read
        permission_hierarchy = {
            PERMISSION_READ: 1,
            PERMISSION_WRITE: 2,
            PERMISSION_ADMIN: 3,
        }

        required_level = permission_hierarchy.get(required_permission, 1)

        # Check direct user shares
        sql = """
            SELECT permission_level FROM resource_shares
            WHERE resource_type = :resource_type
            AND resource_id = :resource_id
            AND shared_with_user = :user_id
            AND (expires_at IS NULL OR expires_at > :now)
        """
        results = await repo_query(
            sql,
            {
                "resource_type": resource_type,
                "resource_id": resource_id,
                "user_id": user_id,
                "now": datetime.utcnow(),
            },
        )

        for row in results:
            granted_level = permission_hierarchy.get(row["permission_level"], 0)
            if granted_level >= required_level:
                return True

        # Check role-based shares
        sql = """
            SELECT rs.permission_level FROM resource_shares rs
            INNER JOIN user_roles ur ON rs.shared_with_role = ur.role_id
            WHERE rs.resource_type = :resource_type
            AND rs.resource_id = :resource_id
            AND ur.user_id = :user_id
            AND (rs.expires_at IS NULL OR rs.expires_at > :now)
        """
        results = await repo_query(
            sql,
            {
                "resource_type": resource_type,
                "resource_id": resource_id,
                "user_id": user_id,
                "now": datetime.utcnow(),
            },
        )

        for row in results:
            granted_level = permission_hierarchy.get(row["permission_level"], 0)
            if granted_level >= required_level:
                return True

        return False

    @classmethod
    async def share_resource(
        cls,
        resource_type: str,
        resource_id: str,
        shared_by: str,
        shared_with_user: Optional[str] = None,
        shared_with_role: Optional[str] = None,
        permission_level: str = PERMISSION_READ,
        expires_at: Optional[datetime] = None,
    ) -> str:
        """
        Share a resource with a user or role.

        Args:
            resource_type: Type of resource to share
            resource_id: ID of the resource
            shared_by: User ID who is sharing
            shared_with_user: User ID to share with (optional)
            shared_with_role: Role ID to share with (optional)
            permission_level: Permission level to grant (read, write, admin)
            expires_at: Optional expiration timestamp

        Returns:
            Share ID

        Raises:
            ValueError: If neither shared_with_user nor shared_with_role is provided
        """
        if not shared_with_user and not shared_with_role:
            raise ValueError("Must specify either shared_with_user or shared_with_role")

        # Check if share already exists
        where_clauses = [
            "resource_type = :resource_type",
            "resource_id = :resource_id",
            "shared_by = :shared_by",
        ]
        params = {
            "resource_type": resource_type,
            "resource_id": resource_id,
            "shared_by": shared_by,
        }

        if shared_with_user:
            where_clauses.append("shared_with_user = :shared_with_user")
            params["shared_with_user"] = shared_with_user

        if shared_with_role:
            where_clauses.append("shared_with_role = :shared_with_role")
            params["shared_with_role"] = shared_with_role

        sql = f"SELECT * FROM resource_shares WHERE {' AND '.join(where_clauses)}"
        existing = await repo_query(sql, params)

        if existing:
            # Update existing share
            share_id = existing[0]["id"]
            update_sql = """
                UPDATE resource_shares
                SET permission_level = :permission_level,
                    expires_at = :expires_at,
                    updated = :updated
                WHERE id = :id
            """
            await repo_execute(
                update_sql,
                {
                    "id": share_id,
                    "permission_level": permission_level,
                    "expires_at": expires_at,
                    "updated": datetime.utcnow(),
                },
            )
            return share_id

        # Create new share
        share = cls(
            resource_type=resource_type,
            resource_id=resource_id,
            shared_by=shared_by,
            shared_with_user=shared_with_user,
            shared_with_role=shared_with_role,
            permission_level=permission_level,
            expires_at=expires_at,
        )
        return await share.save()

    @classmethod
    async def revoke_share(cls, share_id: str) -> None:
        """Revoke a resource share."""
        sql = "DELETE FROM resource_shares WHERE id = :id"
        await repo_execute(sql, {"id": share_id})

    @classmethod
    async def cleanup_expired(cls) -> int:
        """Remove expired shares and return count removed."""
        sql = "DELETE FROM resource_shares WHERE expires_at IS NOT NULL AND expires_at <= :now"
        return await repo_execute(sql, {"now": datetime.utcnow()})
