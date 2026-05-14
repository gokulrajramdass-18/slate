"""
Authentication Router

JWT-based authentication for RBAC system.
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from jose import jwt
from pydantic import BaseModel, Field

from open_notebook.constants import USER_STATUS_ACTIVE
from open_notebook.domain.user import User, Role, UserRole
from api.dependencies.auth import (
    get_current_user,
    get_current_active_user,
    set_jwt_config,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production-please")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Initialize JWT config in dependencies
set_jwt_config(SECRET_KEY, ALGORITHM)


# ============================================================================
# Pydantic Models
# ============================================================================


class LoginRequest(BaseModel):
    """Login credentials"""

    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """JWT token response"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: dict


class RefreshRequest(BaseModel):
    """Refresh token request"""

    refresh_token: str


class RegisterRequest(BaseModel):
    """User registration"""

    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = None
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None


# ============================================================================
# Helper Functions
# ============================================================================


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_user_response_data(user: User) -> dict:
    """Get user data for response"""
    roles = await user.get_roles()

    return {
        "id": user.username,  # Use username as the primary ID for frontend
        "uuid": user.id,  # Keep UUID for reference if needed
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "avatar_url": user.avatar_url,
        "is_superadmin": user.is_superadmin,
        "status": user.status,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "roles": [
            {"id": r.id, "name": r.name, "display_name": r.display_name}
            for r in roles
        ],
    }


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """
    Authenticate user and return JWT tokens.

    - Verifies username/password
    - Returns access token (30 min) + refresh token (7 days)
    - Updates last_login timestamp
    """
    # Get user by username
    user = await User.get_by_username(request.username)

    # Verify user exists and password is correct
    if not user or not user.verify_password(request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check user is not suspended/deleted
    if user.status != USER_STATUS_ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"User account is {user.status}",
        )

    # Update last login
    await user.update_last_login()

    # Create tokens
    token_data = {"user_id": user.id, "username": user.username}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Get user data
    user_data = await get_user_response_data(user)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user_data,
    )


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest):
    """
    Register new user.

    - Creates user with hashed password
    - Assigns default 'user' role
    - Returns JWT tokens for immediate login
    """
    # Check if username already exists
    existing = await User.get_by_username(request.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{request.username}' already exists",
        )

    # Check if email already exists
    if request.email:
        existing_email = await User.get_by_email(request.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Email '{request.email}' already exists",
            )

    # Create user
    user = User(
        username=request.username,
        email=request.email,
        password_hash=User.hash_password(request.password),
        full_name=request.full_name,
        status=USER_STATUS_ACTIVE,
        is_superadmin=False,
    )

    user_id = await user.save()

    # Assign default 'user' role
    default_role = await Role.get_by_name("user")
    if default_role:
        await UserRole.assign_role(
            user_id=user_id, role_id=default_role.id, assigned_by=user_id
        )

    # Reload user to get roles
    user = await User.get(user_id)

    # Create tokens
    token_data = {"user_id": user.id, "username": user.username}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Get user data
    user_data = await get_user_response_data(user)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user_data,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(request: RefreshRequest):
    """
    Get new access token using refresh token.

    - Verifies refresh token
    - Returns new access token
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode refresh token
        payload = jwt.decode(request.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("user_id")
        token_type: str = payload.get("type")

        if user_id is None or token_type != "refresh":
            raise credentials_exception

    except Exception:
        raise credentials_exception

    # Load user
    user = await User.get(user_id)
    if not user or user.status != USER_STATUS_ACTIVE:
        raise credentials_exception

    # Create new access token
    token_data = {"user_id": user.id, "username": user.username}
    access_token = create_access_token(token_data)

    # Get user data
    user_data = await get_user_response_data(user)

    return TokenResponse(
        access_token=access_token,
        refresh_token=request.refresh_token,  # Return same refresh token
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user_data,
    )


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout (client-side token deletion mainly).

    JWT tokens are stateless, so logout is handled client-side
    by deleting the tokens. This endpoint exists for consistency.
    """
    return {"message": "Logged out successfully"}


@router.get("/me")
async def get_current_user_info(request: Request):
    """
    Get current authenticated user info.

    Returns user with roles and permissions.

    Supports both:
    - JWT Bearer token (Authorization header)
    - XSUAA session via AppRouter (cookie-based, JWT in Authorization header from AppRouter)
    """
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

    # Check for Authorization header (works for both JWT and XSUAA)
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract token from Bearer header
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header[7:]  # Remove "Bearer " prefix

    # Use get_current_user_from_token which handles both JWT and XSUAA
    from api.dependencies.auth import get_current_user_from_token

    # Check if XSUAA is enabled
    xsuaa_enabled = os.getenv("XSUAA_ENABLED", "false").lower() == "true"

    if xsuaa_enabled:
        from api.services.xsuaa_auth_service import get_current_user_from_xsuaa_token
        current_user = await get_current_user_from_xsuaa_token(token)
    else:
        current_user = await get_current_user_from_token(token)

    user_data = await get_user_response_data(current_user)
    return user_data


@router.get("/me/permissions")
async def get_current_user_permissions(current_user: User = Depends(get_current_active_user)):
    """
    Get all permissions for current user (aggregated from all roles).

    Returns a list of permissions with resource_type, action, and scope.
    Superadmins get a special flag.
    """
    from open_notebook.domain.user import RolePermission

    # Superadmins have all permissions
    if current_user.is_superadmin:
        return {
            "is_superadmin": True,
            "permissions": []  # No need to list all, frontend checks is_superadmin
        }

    # Get all permissions from user's roles
    permissions = await RolePermission.get_for_user(current_user.id)

    return {
        "is_superadmin": False,
        "permissions": [
            {
                "resource_type": p.resource_type,
                "action": p.action,
                "scope": p.scope,
            }
            for p in permissions
        ]
    }


@router.get("/status")
async def get_auth_status():
    """
    Get authentication system status.

    Returns configuration info (no secrets).
    """
    return {
        "auth_type": "JWT",
        "token_type": "Bearer",
        "access_token_expires_minutes": ACCESS_TOKEN_EXPIRE_MINUTES,
        "refresh_token_expires_days": REFRESH_TOKEN_EXPIRE_DAYS,
    }
