"""
OAuth 2.0 Dependencies

FastAPI dependency injection for OAuth token validation and authorization.
Supports both OAuth tokens and user JWT tokens via unified get_current_auth() dependency.
"""

import json
from datetime import datetime
from typing import List, Optional, Tuple

from fastapi import Depends, HTTPException, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from open_notebook.domain.user import User
from open_notebook.database.repository import repo_query
from api.dependencies.auth import SECRET_KEY, ALGORITHM, get_current_user_from_token

# Security scheme
security = HTTPBearer()


class OAuthToken:
    """Parsed OAuth access token with scope validation"""

    def __init__(self, app_id: str, client_id: str, user_id: str, scopes: List[str], jti: str):
        self.app_id = app_id
        self.client_id = client_id
        self.user_id = user_id
        self.scopes = scopes
        self.jti = jti

    def has_scope(self, required_scope: str) -> bool:
        """
        Check if token has required scope.

        Supports wildcard admin:all scope.

        Args:
            required_scope: Scope to check (e.g., "execute:teams")

        Returns:
            True if token has the scope or admin:all
        """
        if "admin:all" in self.scopes:
            return True
        return required_scope in self.scopes


async def get_oauth_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> OAuthToken:
    """
    Validate OAuth access token and return parsed token.

    Checks:
    - JWT signature and expiry
    - Token type == "oauth_access"
    - Token not revoked
    - Application status == "active"

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        OAuthToken instance

    Raises:
        HTTPException: 401 if token invalid, expired, revoked, or app suspended
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate OAuth credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Decode JWT token
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Verify token type
        token_type: str = payload.get("type")
        if token_type != "oauth_access":
            raise credentials_exception

        # Extract claims
        app_id: str = payload.get("sub")  # Subject is app_id
        client_id: str = payload.get("client_id")
        user_id: str = payload.get("user_id")
        scopes: List[str] = payload.get("scopes", [])
        jti: str = payload.get("jti")

        if not all([app_id, client_id, user_id, jti]):
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # Check if token is revoked
    revoked_rows = await repo_query(
        "SELECT jti FROM oauth_revoked_tokens WHERE jti = :jti",
        {"jti": jti}
    )
    if revoked_rows:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked"
        )

    # Verify application is active
    app_rows = await repo_query(
        "SELECT id, status FROM oauth_applications WHERE id = :id",
        {"id": app_id}
    )
    if not app_rows:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OAuth application not found"
        )

    if app_rows[0]["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"OAuth application is {app_rows[0]['status']}"
        )

    return OAuthToken(
        app_id=app_id,
        client_id=client_id,
        user_id=user_id,
        scopes=scopes,
        jti=jti
    )


def require_oauth_scope(required_scope: str):
    """
    Dependency factory for scope-specific OAuth protection.

    Usage:
        @router.post("/teams/{id}/execute")
        async def execute_team(
            oauth_token: OAuthToken = Depends(require_oauth_scope("execute:teams"))
        ):
            # Token guaranteed to have execute:teams scope
            ...

    Args:
        required_scope: OAuth scope required for this endpoint

    Returns:
        Dependency function that checks scope
    """
    async def scope_checker(
        oauth_token: OAuthToken = Depends(get_oauth_token),
    ) -> OAuthToken:
        if not oauth_token.has_scope(required_scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient OAuth scope. Required: {required_scope}"
            )
        return oauth_token

    return scope_checker


async def get_current_auth(
    authorization: Optional[str] = Header(None),
) -> Tuple[str, Optional[OAuthToken], Optional[User]]:
    """
    Universal authentication dependency supporting both OAuth and user JWT tokens.

    Detects token type and validates appropriately:
    - OAuth token (type=="oauth_access") → return ("oauth", OAuthToken, None)
    - User JWT (type=="access") → return ("user", None, User)

    This allows agent APIs to accept both external OAuth requests
    and internal user UI requests without breaking existing functionality.

    Returns:
        Tuple of (auth_type, oauth_token, user):
        - ("oauth", OAuthToken, None) for OAuth tokens
        - ("user", None, User) for user JWT tokens

    Raises:
        HTTPException: 401 if no valid token found
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[7:]  # Remove "Bearer " prefix

    try:
        # Decode JWT to check type
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        token_type = payload.get("type")

        if token_type == "oauth_access":
            # OAuth token - validate via get_oauth_token
            # Create fake credentials for dependency
            from fastapi.security import HTTPAuthorizationCredentials
            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials=token
            )
            oauth_token = await get_oauth_token(credentials)
            return ("oauth", oauth_token, None)

        elif token_type == "access":
            # User JWT token - validate via existing user auth
            user = await get_current_user_from_token(token)
            return ("user", None, user)

        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token type: {token_type}"
            )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
