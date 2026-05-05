"""
Permission Service

Centralized permission checking for RBAC system.
"""

from typing import Optional

from fastapi import HTTPException, status

from open_notebook.constants import PERMISSION_ADMIN, PERMISSION_READ, PERMISSION_WRITE
from open_notebook.domain.user import User


class PermissionService:
    """Centralized service for checking user permissions"""

    @staticmethod
    async def check_permission(
        user: User,
        resource_type: str,
        action: str,
        resource_id: Optional[str] = None,
        resource_owner: Optional[str] = None,
    ) -> bool:
        """
        Check if user has permission for action on resource type.

        Args:
            user: User object to check permissions for
            resource_type: Type of resource (workspace, agent, tool, etc.)
            action: Action to perform (create, read, update, delete, execute, share)
            resource_id: Optional specific resource ID (for share checks)
            resource_owner: Optional resource owner ID (for scope=own checks)

        Returns:
            True if user has permission, False otherwise
        """
        # Use domain model's has_permission method
        return await user.has_permission(
            resource_type=resource_type,
            action=action,
            resource_owner=resource_owner,
            resource_id=resource_id,
        )

    @staticmethod
    async def require_permission(
        user: User,
        resource_type: str,
        action: str,
        resource_id: Optional[str] = None,
        resource_owner: Optional[str] = None,
    ) -> None:
        """
        Require permission or raise HTTPException(403).

        Args:
            user: User object to check permissions for
            resource_type: Type of resource
            action: Action to perform
            resource_id: Optional specific resource ID
            resource_owner: Optional resource owner ID

        Raises:
            HTTPException: 403 Forbidden if permission denied
        """
        has_permission = await PermissionService.check_permission(
            user=user,
            resource_type=resource_type,
            action=action,
            resource_id=resource_id,
            resource_owner=resource_owner,
        )

        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {action} on {resource_type}",
            )

    @staticmethod
    def permission_hierarchy_check(
        granted_level: str, required_level: str
    ) -> bool:
        """
        Check if granted permission level satisfies required level.

        Hierarchy: admin > write > read

        Args:
            granted_level: Permission level granted (read, write, admin)
            required_level: Permission level required (read, write, admin)

        Returns:
            True if granted >= required
        """
        hierarchy = {
            PERMISSION_READ: 1,
            PERMISSION_WRITE: 2,
            PERMISSION_ADMIN: 3,
        }

        granted = hierarchy.get(granted_level, 0)
        required = hierarchy.get(required_level, 0)

        return granted >= required
