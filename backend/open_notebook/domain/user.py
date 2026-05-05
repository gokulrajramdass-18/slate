"""
User domain models for authentication and authorization.

Provides User, Role, RolePermission models with full CRUD and permission checking.
"""

import json
from datetime import datetime
from typing import ClassVar, List, Optional

from passlib.context import CryptContext

from open_notebook.constants import (
    PERMISSION_READ,
    PERMISSION_WRITE,
    SCOPE_ALL,
    SCOPE_OWN,
    USER_STATUS_ACTIVE,
)
from open_notebook.database.repository import repo_create, repo_query
from open_notebook.domain.base import ObjectModel

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User(ObjectModel):
    """
    User model representing system users.

    Attributes:
        username: Unique username for login
        email: Email address (optional, unique)
        password_hash: Bcrypt hashed password
        full_name: Display name
        avatar_url: Profile picture URL
        status: active | suspended | deleted
        is_superadmin: Bypass all permission checks
        last_login: Timestamp of last successful login
    """

    _table_name: ClassVar[str] = "users"
    _exclude_fields: ClassVar[List[str]] = []

    username: str
    email: Optional[str] = None
    password_hash: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    status: str = USER_STATUS_ACTIVE
    is_superadmin: bool = False
    last_login: Optional[datetime] = None

    @classmethod
    async def get_by_username(cls, username: str) -> Optional["User"]:
        """Get user by username."""
        sql = "SELECT * FROM users WHERE username = :username"
        results = await repo_query(sql, {"username": username})

        if not results:
            return None

        return cls(**results[0])

    @classmethod
    async def get_by_email(cls, email: str) -> Optional["User"]:
        """Get user by email."""
        sql = "SELECT * FROM users WHERE email = :email"
        results = await repo_query(sql, {"email": email})

        if not results:
            return None

        return cls(**results[0])

    async def get_roles(self) -> List["Role"]:
        """Get all roles assigned to this user."""
        sql = """
            SELECT r.* FROM roles r
            INNER JOIN user_roles ur ON r.id = ur.role_id
            WHERE ur.user_id = :user_id
        """
        results = await repo_query(sql, {"user_id": self.id})
        return [Role(**row) for row in results]

    async def has_permission(
        self,
        resource_type: str,
        action: str,
        resource_owner: Optional[str] = None,
        resource_id: Optional[str] = None,
    ) -> bool:
        """
        Check if user has permission for action on resource type.

        Args:
            resource_type: Type of resource (workspace, agent, tool, etc.)
            action: Action to perform (create, read, update, delete, execute, share)
            resource_owner: Owner user ID of the resource (for scope=own checks)
            resource_id: Specific resource ID (for share checks)

        Returns:
            True if user has permission, False otherwise
        """
        # Superadmin bypass
        if self.is_superadmin:
            return True

        # Suspended users have no permissions
        if self.status != USER_STATUS_ACTIVE:
            return False

        # Get user's roles
        roles = await self.get_roles()

        # Check each role's permissions
        for role in roles:
            permissions = await role.get_permissions()
            for perm in permissions:
                if perm.resource_type == resource_type and perm.action == action:
                    # Check scope
                    if perm.scope == SCOPE_ALL:
                        return True
                    elif perm.scope == SCOPE_OWN and resource_owner == self.id:
                        return True
                    elif perm.scope == "team":
                        # TODO: Implement team membership check
                        pass

        # Check explicit resource shares
        if resource_id:
            from open_notebook.domain.resource_share import ResourceShare

            has_access = await ResourceShare.check_access(
                user_id=self.id,
                resource_type=resource_type,
                resource_id=resource_id,
                required_permission=action,
            )
            if has_access:
                return True

        return False

    def verify_password(self, password: str) -> bool:
        """Verify password against hash."""
        return pwd_context.verify(password, self.password_hash)

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        return pwd_context.hash(password)

    async def update_last_login(self) -> None:
        """Update last_login timestamp."""
        self.last_login = datetime.utcnow()
        await self.save()


class Role(ObjectModel):
    """
    Role model representing user roles.

    Attributes:
        name: Unique role identifier (e.g., 'admin', 'user')
        display_name: Human-readable name
        description: Role description
        is_system_role: Cannot be deleted if True
        created_by: User who created the role
    """

    _table_name: ClassVar[str] = "roles"
    _exclude_fields: ClassVar[List[str]] = []

    name: str
    display_name: str
    description: Optional[str] = None
    is_system_role: bool = False
    created_by: Optional[str] = None

    @classmethod
    async def get_by_name(cls, name: str) -> Optional["Role"]:
        """Get role by name."""
        sql = "SELECT * FROM roles WHERE name = :name"
        results = await repo_query(sql, {"name": name})

        if not results:
            return None

        return cls(**results[0])

    async def get_permissions(self) -> List["RolePermission"]:
        """Get all permissions for this role."""
        return await RolePermission.get_for_role(self.id)

    async def get_users(self) -> List[User]:
        """Get all users with this role."""
        sql = """
            SELECT u.* FROM users u
            INNER JOIN user_roles ur ON u.id = ur.user_id
            WHERE ur.role_id = :role_id
        """
        results = await repo_query(sql, {"role_id": self.id})
        return [User(**row) for row in results]


class RolePermission(ObjectModel):
    """
    Role permission model defining what actions roles can perform.

    Attributes:
        role_id: Role this permission belongs to
        resource_type: Type of resource (workspace, agent, tool, etc.)
        action: Action allowed (create, read, update, delete, execute, share)
        scope: Scope of access (own, team, all)
        conditions: Optional JSON conditions for advanced rules
    """

    _table_name: ClassVar[str] = "role_permissions"
    _exclude_fields: ClassVar[List[str]] = []

    role_id: str
    resource_type: str
    action: str
    scope: str = SCOPE_OWN
    conditions: Optional[dict] = None

    @classmethod
    async def get_for_role(cls, role_id: str) -> List["RolePermission"]:
        """Get all permissions for a role."""
        sql = "SELECT * FROM role_permissions WHERE role_id = :role_id"
        results = await repo_query(sql, {"role_id": role_id})
        return [cls(**row) for row in results]

    @classmethod
    async def get_for_user(cls, user_id: str) -> List["RolePermission"]:
        """Get all permissions for a user (via their roles)."""
        sql = """
            SELECT DISTINCT rp.* FROM role_permissions rp
            INNER JOIN user_roles ur ON rp.role_id = ur.role_id
            WHERE ur.user_id = :user_id
        """
        results = await repo_query(sql, {"user_id": user_id})
        return [cls(**row) for row in results]

    def to_dict(self) -> dict:
        """Convert to dictionary, parsing conditions if present."""
        data = self.model_dump()
        if isinstance(data.get("conditions"), str):
            try:
                data["conditions"] = json.loads(data["conditions"])
            except (json.JSONDecodeError, TypeError):
                data["conditions"] = None
        return data


class UserRole(ObjectModel):
    """
    User-Role assignment linking users to roles.

    Attributes:
        user_id: User ID
        role_id: Role ID
        assigned_by: User who made the assignment
        assigned_at: Timestamp of assignment
    """

    _table_name: ClassVar[str] = "user_roles"
    _exclude_fields: ClassVar[List[str]] = []

    user_id: str
    role_id: str
    assigned_by: Optional[str] = None
    assigned_at: Optional[datetime] = None

    @classmethod
    async def assign_role(
        cls, user_id: str, role_id: str, assigned_by: Optional[str] = None
    ) -> str:
        """Assign a role to a user."""
        # Check if already assigned
        sql = "SELECT * FROM user_roles WHERE user_id = :user_id AND role_id = :role_id"
        existing = await repo_query(sql, {"user_id": user_id, "role_id": role_id})

        if existing:
            return existing[0]["id"]

        # Create new assignment
        assignment = cls(
            user_id=user_id,
            role_id=role_id,
            assigned_by=assigned_by,
            assigned_at=datetime.utcnow(),
        )
        return await assignment.save()

    @classmethod
    async def remove_role(cls, user_id: str, role_id: str) -> None:
        """Remove a role from a user."""
        sql = "DELETE FROM user_roles WHERE user_id = :user_id AND role_id = :role_id"
        from open_notebook.database.repository import repo_execute

        await repo_execute(sql, {"user_id": user_id, "role_id": role_id})
