"""
Authentication Dependencies

FastAPI dependency injection for authentication and authorization.
"""

import os
from typing import Optional

from fastapi import Depends, HTTPException, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from open_notebook.constants import USER_STATUS_ACTIVE
from open_notebook.domain.user import User
from api.services.permission_service import PermissionService

# Security scheme
security = HTTPBearer()

# JWT Configuration (will be set by auth router)
SECRET_KEY = None
ALGORITHM = "HS256"

# XSUAA Configuration
XSUAA_ENABLED = os.getenv("XSUAA_ENABLED", "false").lower() == "true"


def set_jwt_config(secret_key: str, algorithm: str = "HS256"):
    """Set JWT configuration"""
    global SECRET_KEY, ALGORITHM
    SECRET_KEY = secret_key
    ALGORITHM = algorithm


async def get_current_user_from_token(token: str) -> User:
    """
    Extract and validate user from JWT token.

    Args:
        token: JWT token string

    Returns:
        User object

    Raises:
        HTTPException: 401 if token invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Load user from database
    user = await User.get(user_id)
    if user is None:
        raise credentials_exception

    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """
    Get current authenticated user from Bearer token.

    Supports both:
    - Local JWT tokens (username/password login)
    - XSUAA tokens (from AppRouter)

    Dependency for FastAPI routes requiring authentication.

    Returns:
        User object

    Raises:
        HTTPException: 401 if not authenticated
    """
    token = credentials.credentials

    # If XSUAA is enabled, handle XSUAA tokens
    if XSUAA_ENABLED:
        from api.services.xsuaa_auth_service import get_current_user_from_xsuaa_token
        return await get_current_user_from_xsuaa_token(token)

    # Otherwise, use standard JWT validation
    return await get_current_user_from_token(token)


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current user and verify status is active.

    Dependency for FastAPI routes requiring active user.

    Returns:
        User object

    Raises:
        HTTPException: 400 if user account is suspended
    """
    if current_user.status != USER_STATUS_ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is suspended or deleted",
        )

    return current_user


def require_permission(resource_type: str, action: str):
    """
    Dependency factory for permission-protected routes.

    Usage:
        @router.post("/workspaces")
        async def create_workspace(
            data: WorkspaceCreate,
            current_user: User = Depends(require_permission("workspace", "create"))
        ):
            ...

    Args:
        resource_type: Type of resource (workspace, agent, tool, etc.)
        action: Action to perform (create, read, update, delete, execute)

    Returns:
        Dependency function that checks permission
    """

    async def permission_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        await PermissionService.require_permission(
            user=current_user,
            resource_type=resource_type,
            action=action,
        )
        return current_user

    return permission_checker


def require_admin():
    """
    Dependency for admin-only routes.

    Usage:
        @router.post("/users")
        async def create_user(
            data: UserCreate,
            current_user: User = Depends(require_admin())
        ):
            ...

    Returns:
        Dependency function that checks superadmin status
    """

    async def admin_checker(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if not current_user.is_superadmin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator access required",
            )
        return current_user

    return admin_checker


# Backward compatibility: X-User-ID header support (for gradual migration)
async def get_user_id_from_header(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
) -> Optional[str]:
    """
    Get user ID from X-User-ID header (legacy support).

    This is for backward compatibility during migration.
    New code should use Bearer tokens via get_current_user.
    """
    return x_user_id
