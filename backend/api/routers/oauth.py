"""
OAuth 2.0 Management API Router

Endpoints for OAuth application management and OAuth 2.0 protocol implementation.
Supports Client Credentials flow (RFC 6749) with token revocation and introspection.
"""

import json
import secrets
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, status, Form
from pydantic import BaseModel, Field
from jose import jwt
import base64

from api.dependencies.auth import get_current_active_user, SECRET_KEY, ALGORITHM
from open_notebook.domain.user import User
from open_notebook.database.repository import repo_query, repo_execute, repo_update, repo_delete
from open_notebook.config import get_encryption_key
from cryptography.fernet import Fernet

router = APIRouter(
    prefix="/api/oauth",
    tags=["oauth"],
)

# OAuth 2.0 protocol router (no /api prefix for standard endpoints)
oauth_protocol_router = APIRouter(
    prefix="/oauth",
    tags=["oauth-protocol"],
)


# ============================================================================
# Pydantic Models
# ============================================================================

class OAuthAppCreate(BaseModel):
    """Create OAuth application"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    scopes: List[str] = Field(..., min_items=1)
    redirect_uris: Optional[List[str]] = Field(None, description="Redirect URIs for Authorization Code flow")
    grant_types: Optional[List[str]] = Field(["client_credentials"], description="OAuth grant types: client_credentials, authorization_code")
    rate_limit_per_hour: int = Field(1000, ge=1, le=10000)
    rate_limit_per_day: int = Field(10000, ge=1, le=100000)
    token_expiry_seconds: int = Field(3600, ge=300, le=86400)


class OAuthAppUpdate(BaseModel):
    """Update OAuth application"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    scopes: Optional[List[str]] = None
    redirect_uris: Optional[List[str]] = None
    grant_types: Optional[List[str]] = None
    rate_limit_per_hour: Optional[int] = Field(None, ge=1, le=10000)
    rate_limit_per_day: Optional[int] = Field(None, ge=1, le=100000)
    token_expiry_seconds: Optional[int] = Field(None, ge=300, le=86400)


class OAuthAppResponse(BaseModel):
    """OAuth application response (without secret)"""
    id: str
    name: str
    description: Optional[str]
    client_id: str
    scopes: List[str]
    redirect_uris: Optional[List[str]] = None
    grant_types: Optional[List[str]] = None
    status: str
    rate_limit_per_hour: int
    rate_limit_per_day: int
    token_expiry_seconds: int
    last_used_at: Optional[str]
    created: str
    updated: str


class OAuthAppWithSecret(OAuthAppResponse):
    """OAuth application with client secret (only returned on creation)"""
    client_secret: str


class TokenRequest(BaseModel):
    """OAuth 2.0 token request"""
    grant_type: str = "client_credentials"
    client_id: str
    client_secret: str
    scope: Optional[str] = None  # Space-separated scopes


class TokenResponse(BaseModel):
    """OAuth 2.0 token response"""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    scope: str
    refresh_token: Optional[str] = None  # For authorization_code grant


class TokenRevocationRequest(BaseModel):
    """Token revocation request (RFC 7009)"""
    token: str
    token_type_hint: Optional[str] = "access_token"


class TokenIntrospectionRequest(BaseModel):
    """Token introspection request (RFC 7662)"""
    token: str


class TokenIntrospectionResponse(BaseModel):
    """Token introspection response (RFC 7662)"""
    active: bool
    scope: Optional[str] = None
    client_id: Optional[str] = None
    exp: Optional[int] = None
    iat: Optional[int] = None


class OAuthScopeResponse(BaseModel):
    """OAuth scope information"""
    scope: str
    resource_type: str
    action: str
    description: Optional[str]


class OAuthAppUsageStats(BaseModel):
    """Usage statistics for OAuth app"""
    total_requests: int
    requests_last_hour: int
    requests_last_day: int
    avg_response_time_ms: float
    error_rate: float


# ============================================================================
# Helper Functions
# ============================================================================

def _encrypt_secret(secret: str) -> str:
    """Encrypt client secret using Fernet"""
    key = get_encryption_key()
    if not key:
        raise HTTPException(
            status_code=500,
            detail="Encryption key not configured"
        )
    fernet = Fernet(key.encode())
    encrypted = fernet.encrypt(secret.encode())
    return base64.b64encode(encrypted).decode()


def _decrypt_secret(encrypted: str) -> str:
    """Decrypt client secret"""
    key = get_encryption_key()
    if not key:
        raise HTTPException(
            status_code=500,
            detail="Encryption key not configured"
        )
    try:
        fernet = Fernet(key.encode())
        encrypted_bytes = base64.b64decode(encrypted.encode())
        decrypted = fernet.decrypt(encrypted_bytes)
        return decrypted.decode()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to decrypt secret: {str(e)}"
        )


def _generate_client_id() -> str:
    """Generate random client ID"""
    return secrets.token_urlsafe(16)


def _generate_client_secret() -> str:
    """Generate random client secret"""
    return secrets.token_urlsafe(32)


async def _get_app_or_404(app_id: str, user_id: str) -> dict:
    """Get OAuth app by ID, verify ownership"""
    rows = await repo_query(
        "SELECT * FROM oauth_applications WHERE id = :id",
        {"id": app_id}
    )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"OAuth application not found: {app_id}"
        )

    app = rows[0]
    if app["owner_user_id"] != user_id:
        raise HTTPException(
            status_code=403,
            detail="You can only access your own OAuth applications"
        )

    return app


def _format_app_response(row: dict) -> OAuthAppResponse:
    """Convert database row to response model"""
    # Parse scopes
    scopes = json.loads(row["scopes"]) if isinstance(row["scopes"], str) else row["scopes"]

    # Parse redirect_uris
    redirect_uris = None
    if row.get("redirect_uris"):
        redirect_uris = json.loads(row["redirect_uris"]) if isinstance(row["redirect_uris"], str) else row["redirect_uris"]

    # Parse grant_types with fallback
    grant_types = ["client_credentials"]  # Default
    if row.get("grant_types"):
        if isinstance(row["grant_types"], str):
            try:
                grant_types = json.loads(row["grant_types"])
            except (json.JSONDecodeError, ValueError):
                # If it's a plain string like "client_credentials", wrap it
                grant_types = [row["grant_types"]] if row["grant_types"] else ["client_credentials"]
        elif isinstance(row["grant_types"], list):
            grant_types = row["grant_types"]

    return OAuthAppResponse(
        id=row["id"],
        name=row["name"],
        description=row.get("description"),
        client_id=row["client_id"],
        scopes=scopes,
        redirect_uris=redirect_uris,
        grant_types=grant_types,
        status=row["status"],
        rate_limit_per_hour=row["rate_limit_per_hour"],
        rate_limit_per_day=row["rate_limit_per_day"],
        token_expiry_seconds=row["token_expiry_seconds"],
        last_used_at=row.get("last_used_at"),
        created=row["created"],
        updated=row["updated"]
    )


# ============================================================================
# OAuth Application Management Endpoints
# ============================================================================

@router.post("/apps", response_model=OAuthAppWithSecret, status_code=status.HTTP_201_CREATED)
async def create_oauth_app(
    body: OAuthAppCreate,
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new OAuth application.

    Returns client_id and client_secret. **Save the client_secret immediately** -
    it cannot be retrieved again (only regenerated).

    Example:
        POST /api/oauth/apps
        {
            "name": "My External App",
            "description": "External system integration",
            "scopes": ["read:agents", "execute:teams"],
            "rate_limit_per_hour": 1000,
            "rate_limit_per_day": 10000,
            "token_expiry_seconds": 3600
        }
    """
    # Validate scopes exist
    scope_rows = await repo_query(
        "SELECT scope FROM oauth_scopes WHERE scope IN ({})".format(
            ",".join([f"'{s}'" for s in body.scopes])
        ),
        {}
    )
    valid_scopes = {row["scope"] for row in scope_rows}
    invalid_scopes = set(body.scopes) - valid_scopes
    if invalid_scopes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scopes: {', '.join(invalid_scopes)}"
        )

    # Generate credentials
    app_id = str(uuid.uuid4())
    client_id = _generate_client_id()
    client_secret = _generate_client_secret()
    client_secret_encrypted = _encrypt_secret(client_secret)

    now = datetime.utcnow().isoformat()

    data = {
        "id": app_id,
        "name": body.name,
        "description": body.description,
        "owner_user_id": current_user.id,
        "client_id": client_id,
        "client_secret_encrypted": client_secret_encrypted,
        "scopes": json.dumps(body.scopes),
        "redirect_uris": json.dumps(body.redirect_uris) if body.redirect_uris else None,
        "grant_types": json.dumps(body.grant_types) if body.grant_types else json.dumps(["client_credentials"]),
        "status": "active",
        "rate_limit_per_hour": body.rate_limit_per_hour,
        "rate_limit_per_day": body.rate_limit_per_day,
        "token_expiry_seconds": body.token_expiry_seconds,
        "last_used_at": None,
        "created": now,
        "updated": now
    }

    await repo_execute(
        """INSERT INTO oauth_applications
           (id, name, description, owner_user_id, client_id, client_secret_encrypted,
            scopes, redirect_uris, grant_types, status, rate_limit_per_hour,
            rate_limit_per_day, token_expiry_seconds, last_used_at, created, updated)
           VALUES (:id, :name, :description, :owner_user_id, :client_id, :client_secret_encrypted,
                   :scopes, :redirect_uris, :grant_types, :status, :rate_limit_per_hour,
                   :rate_limit_per_day, :token_expiry_seconds, :last_used_at, :created, :updated)""",
        data
    )

    return OAuthAppWithSecret(
        id=app_id,
        name=body.name,
        description=body.description,
        client_id=client_id,
        client_secret=client_secret,  # Only time this is returned!
        scopes=body.scopes,
        redirect_uris=body.redirect_uris,
        grant_types=body.grant_types or ["client_credentials"],
        status="active",
        rate_limit_per_hour=body.rate_limit_per_hour,
        rate_limit_per_day=body.rate_limit_per_day,
        token_expiry_seconds=body.token_expiry_seconds,
        last_used_at=None,
        created=now,
        updated=now
    )


@router.get("/apps", response_model=List[OAuthAppResponse])
async def list_oauth_apps(
    current_user: User = Depends(get_current_active_user)
):
    """
    List all OAuth applications owned by current user.

    Example:
        GET /api/oauth/apps
    """
    rows = await repo_query(
        "SELECT * FROM oauth_applications WHERE owner_user_id = :owner_user_id ORDER BY created DESC",
        {"owner_user_id": current_user.id}
    )

    return [_format_app_response(row) for row in rows]


@router.get("/apps/{app_id}", response_model=OAuthAppResponse)
async def get_oauth_app(
    app_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get OAuth application details.

    Example:
        GET /api/oauth/apps/abc-123
    """
    app = await _get_app_or_404(app_id, current_user.id)
    return _format_app_response(app)


@router.put("/apps/{app_id}", response_model=OAuthAppResponse)
async def update_oauth_app(
    app_id: str,
    body: OAuthAppUpdate,
    current_user: User = Depends(get_current_active_user)
):
    """
    Update OAuth application settings.

    Cannot update client_id or client_secret (use regenerate-secret endpoint).

    Example:
        PUT /api/oauth/apps/abc-123
        {
            "name": "Updated App Name",
            "scopes": ["read:agents", "write:teams", "execute:teams"]
        }
    """
    app = await _get_app_or_404(app_id, current_user.id)

    # Build update data
    update_data = {"updated": datetime.utcnow().isoformat()}

    if body.name is not None:
        update_data["name"] = body.name
    if body.description is not None:
        update_data["description"] = body.description
    if body.scopes is not None:
        # Validate scopes
        scope_rows = await repo_query(
            "SELECT scope FROM oauth_scopes WHERE scope IN ({})".format(
                ",".join([f"'{s}'" for s in body.scopes])
            ),
            {}
        )
        valid_scopes = {row["scope"] for row in scope_rows}
        invalid_scopes = set(body.scopes) - valid_scopes
        if invalid_scopes:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid scopes: {', '.join(invalid_scopes)}"
            )
        update_data["scopes"] = json.dumps(body.scopes)

    if body.rate_limit_per_hour is not None:
        update_data["rate_limit_per_hour"] = body.rate_limit_per_hour
    if body.rate_limit_per_day is not None:
        update_data["rate_limit_per_day"] = body.rate_limit_per_day
    if body.token_expiry_seconds is not None:
        update_data["token_expiry_seconds"] = body.token_expiry_seconds

    await repo_update("oauth_applications", app_id, update_data)

    # Fetch updated app
    updated_app = await _get_app_or_404(app_id, current_user.id)
    return _format_app_response(updated_app)


@router.delete("/apps/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_oauth_app(
    app_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete OAuth application.

    This will invalidate all tokens issued by this application.

    Example:
        DELETE /api/oauth/apps/abc-123
    """
    await _get_app_or_404(app_id, current_user.id)
    await repo_delete("oauth_applications", app_id)


@router.post("/apps/{app_id}/regenerate-secret", response_model=OAuthAppWithSecret)
async def regenerate_client_secret(
    app_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Regenerate client secret for OAuth application.

    **Warning:** This will invalidate the old secret. All external systems
    using the old secret will need to update their credentials.

    Example:
        POST /api/oauth/apps/abc-123/regenerate-secret
    """
    app = await _get_app_or_404(app_id, current_user.id)

    # Generate new secret
    new_secret = _generate_client_secret()
    new_secret_encrypted = _encrypt_secret(new_secret)

    await repo_update("oauth_applications", app_id, {
        "client_secret_encrypted": new_secret_encrypted,
        "updated": datetime.utcnow().isoformat()
    })

    # Fetch updated app
    updated_app = await _get_app_or_404(app_id, current_user.id)

    return OAuthAppWithSecret(
        **_format_app_response(updated_app).dict(),
        client_secret=new_secret  # Only time new secret is returned!
    )


@router.get("/apps/{app_id}/usage", response_model=OAuthAppUsageStats)
async def get_oauth_app_usage(
    app_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get usage statistics for OAuth application.

    Example:
        GET /api/oauth/apps/abc-123/usage
    """
    app = await _get_app_or_404(app_id, current_user.id)

    # Total requests
    total_rows = await repo_query(
        "SELECT COUNT(*) as count FROM oauth_audit_log WHERE app_id = :app_id",
        {"app_id": app_id}
    )
    total_requests = total_rows[0]["count"] if total_rows else 0

    # Requests in last hour
    hour_ago = (datetime.utcnow() - timedelta(hours=1)).isoformat()
    hour_rows = await repo_query(
        "SELECT COUNT(*) as count FROM oauth_audit_log WHERE app_id = :app_id AND created >= :hour_ago",
        {"app_id": app_id, "hour_ago": hour_ago}
    )
    requests_last_hour = hour_rows[0]["count"] if hour_rows else 0

    # Requests in last day
    day_ago = (datetime.utcnow() - timedelta(days=1)).isoformat()
    day_rows = await repo_query(
        "SELECT COUNT(*) as count FROM oauth_audit_log WHERE app_id = :app_id AND created >= :day_ago",
        {"app_id": app_id, "day_ago": day_ago}
    )
    requests_last_day = day_rows[0]["count"] if day_rows else 0

    # Average response time
    avg_rows = await repo_query(
        "SELECT AVG(response_time_ms) as avg_time FROM oauth_audit_log WHERE app_id = :app_id",
        {"app_id": app_id}
    )
    avg_response_time_ms = float(avg_rows[0]["avg_time"]) if avg_rows and avg_rows[0]["avg_time"] else 0.0

    # Error rate
    error_rows = await repo_query(
        "SELECT COUNT(*) as count FROM oauth_audit_log WHERE app_id = :app_id AND status_code >= 400",
        {"app_id": app_id}
    )
    error_count = error_rows[0]["count"] if error_rows else 0
    error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0.0

    return OAuthAppUsageStats(
        total_requests=total_requests,
        requests_last_hour=requests_last_hour,
        requests_last_day=requests_last_day,
        avg_response_time_ms=avg_response_time_ms,
        error_rate=error_rate
    )


@router.get("/scopes", response_model=List[OAuthScopeResponse])
async def list_oauth_scopes():
    """
    List all available OAuth scopes.

    Example:
        GET /api/oauth/scopes
    """
    rows = await repo_query(
        "SELECT scope, resource_type, action, description FROM oauth_scopes WHERE is_system_only = 0 ORDER BY resource_type, action",
        {}
    )

    return [
        OAuthScopeResponse(
            scope=row["scope"],
            resource_type=row["resource_type"],
            action=row["action"],
            description=row.get("description")
        )
        for row in rows
    ]


# ============================================================================
# OAuth 2.0 Protocol Endpoints
# ============================================================================

@oauth_protocol_router.post("/token", response_model=TokenResponse)
async def issue_token(body: TokenRequest):
    """
    OAuth 2.0 Token Endpoint (Client Credentials Flow - RFC 6749).

    Exchange client credentials for an access token.

    Example:
        POST /oauth/token
        {
            "grant_type": "client_credentials",
            "client_id": "abc123...",
            "client_secret": "xyz789...",
            "scope": "read:agents execute:teams"
        }
    """
    # Validate grant type
    if body.grant_type != "client_credentials":
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported grant type: {body.grant_type}"
        )

    # Find application by client_id
    app_rows = await repo_query(
        "SELECT * FROM oauth_applications WHERE client_id = :client_id",
        {"client_id": body.client_id}
    )
    if not app_rows:
        raise HTTPException(
            status_code=401,
            detail="Invalid client credentials"
        )

    app = app_rows[0]

    # Verify client_secret (constant-time comparison)
    try:
        stored_secret = _decrypt_secret(app["client_secret_encrypted"])
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to verify credentials"
        )

    if not secrets.compare_digest(body.client_secret, stored_secret):
        raise HTTPException(
            status_code=401,
            detail="Invalid client credentials"
        )

    # Verify application status
    if app["status"] != "active":
        raise HTTPException(
            status_code=401,
            detail=f"OAuth application is {app['status']}"
        )

    # Parse and validate requested scopes
    app_scopes = json.loads(app["scopes"]) if isinstance(app["scopes"], str) else app["scopes"]
    requested_scopes = body.scope.split() if body.scope else app_scopes

    # Check all requested scopes are allowed
    invalid_scopes = set(requested_scopes) - set(app_scopes)
    if invalid_scopes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scopes requested: {', '.join(invalid_scopes)}"
        )

    # Create JWT access token
    now = datetime.utcnow()
    exp = now + timedelta(seconds=app["token_expiry_seconds"])
    jti = str(uuid.uuid4())

    token_claims = {
        "sub": app["id"],  # Subject is app_id
        "client_id": app["client_id"],
        "user_id": app["owner_user_id"],
        "scopes": requested_scopes,
        "type": "oauth_access",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": jti
    }

    access_token = jwt.encode(token_claims, SECRET_KEY, algorithm=ALGORITHM)

    return TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=app["token_expiry_seconds"],
        scope=" ".join(requested_scopes)
    )


@oauth_protocol_router.post("/revoke", status_code=status.HTTP_200_OK)
async def revoke_token(body: TokenRevocationRequest):
    """
    Token Revocation Endpoint (RFC 7009).

    Revoke an access token before its natural expiry.

    Example:
        POST /oauth/revoke
        {
            "token": "eyJ...",
            "token_type_hint": "access_token"
        }
    """
    try:
        # Decode token to get jti
        payload = jwt.decode(body.token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        exp_timestamp = payload.get("exp")

        if not jti or not exp_timestamp:
            raise HTTPException(
                status_code=400,
                detail="Invalid token"
            )

        exp_dt = datetime.fromtimestamp(exp_timestamp)

        # Add to revocation list
        await repo_execute(
            """INSERT INTO oauth_revoked_tokens (jti, revoked_at, expires_at, reason)
               VALUES (:jti, :revoked_at, :expires_at, :reason)""",
            {
                "jti": jti,
                "revoked_at": datetime.utcnow().isoformat(),
                "expires_at": exp_dt.isoformat(),
                "reason": "Revoked by client"
            }
        )

        return {"message": "Token revoked successfully"}

    except jwt.JWTError:
        # RFC 7009: The authorization server responds with HTTP status code 200
        # even if the token is invalid (no information disclosure)
        return {"message": "Token revoked successfully"}


@oauth_protocol_router.post("/introspect", response_model=TokenIntrospectionResponse)
async def introspect_token(body: TokenIntrospectionRequest):
    """
    Token Introspection Endpoint (RFC 7662).

    Check if a token is active and get its metadata.

    Example:
        POST /oauth/introspect
        {
            "token": "eyJ..."
        }
    """
    try:
        # Decode token
        payload = jwt.decode(body.token, SECRET_KEY, algorithms=[ALGORITHM])

        # Check token type
        if payload.get("type") != "oauth_access":
            return TokenIntrospectionResponse(active=False)

        # Check if revoked
        jti = payload.get("jti")
        if jti:
            revoked_rows = await repo_query(
                "SELECT jti FROM oauth_revoked_tokens WHERE jti = :jti",
                {"jti": jti}
            )
            if revoked_rows:
                return TokenIntrospectionResponse(active=False)

        # Check application status
        app_id = payload.get("sub")
        if app_id:
            app_rows = await repo_query(
                "SELECT status FROM oauth_applications WHERE id = :id",
                {"id": app_id}
            )
            if not app_rows or app_rows[0]["status"] != "active":
                return TokenIntrospectionResponse(active=False)

        # Token is active
        scopes = payload.get("scopes", [])
        return TokenIntrospectionResponse(
            active=True,
            scope=" ".join(scopes) if scopes else None,
            client_id=payload.get("client_id"),
            exp=payload.get("exp"),
            iat=payload.get("iat")
        )

    except jwt.JWTError:
        return TokenIntrospectionResponse(active=False)


# ============================================================================
# Authorization Code Flow Endpoints (RFC 6749 + PKCE RFC 7636)
# ============================================================================

@oauth_protocol_router.get("/authorize")
async def authorize(
    response_type: str,
    client_id: str,
    redirect_uri: str,
    scope: str,
    state: Optional[str] = None,
    code_challenge: Optional[str] = None,
    code_challenge_method: Optional[str] = "S256",
    current_user: User = Depends(get_current_active_user)
):
    """
    Authorization Endpoint for Authorization Code flow.

    User is redirected here from external application. After authentication,
    shows consent screen. On approval, redirects back with authorization code.

    Supports PKCE (RFC 7636) for enhanced security.

    Example:
        GET /oauth/authorize?response_type=code&client_id=xxx&redirect_uri=https://app.com/callback&scope=read:agents&state=random&code_challenge=xxx&code_challenge_method=S256
    """
    # Validate response_type
    if response_type != "code":
        raise HTTPException(
            status_code=400,
            detail="Unsupported response_type. Only 'code' is supported."
        )

    # Validate application
    app_rows = await repo_query(
        "SELECT * FROM oauth_applications WHERE client_id = :client_id AND status = 'active'",
        {"client_id": client_id}
    )
    if not app_rows:
        raise HTTPException(
            status_code=400,
            detail="Invalid client_id or application is not active"
        )

    app = app_rows[0]

    # Check if application supports authorization_code grant
    grant_types = json.loads(app["grant_types"]) if app["grant_types"] else []
    if "authorization_code" not in grant_types:
        raise HTTPException(
            status_code=400,
            detail="Application does not support authorization_code grant type"
        )

    # Validate redirect_uri
    registered_uris = json.loads(app["redirect_uris"]) if app["redirect_uris"] else []
    if redirect_uri not in registered_uris:
        raise HTTPException(
            status_code=400,
            detail="Invalid redirect_uri. Must be registered with the application."
        )

    # Validate requested scopes
    requested_scopes = scope.split(" ") if scope else []
    app_scopes = json.loads(app["scopes"])
    invalid_scopes = set(requested_scopes) - set(app_scopes)
    if invalid_scopes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scopes requested: {', '.join(invalid_scopes)}"
        )

    # Validate PKCE if provided
    if code_challenge:
        if code_challenge_method not in ["S256", "plain"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid code_challenge_method. Must be 'S256' or 'plain'."
            )

    # Generate authorization code
    code = secrets.token_urlsafe(32)
    code_id = str(uuid.uuid4())
    expires_at = (datetime.utcnow() + timedelta(minutes=10)).isoformat()

    # Store authorization code
    await repo_execute(
        """INSERT INTO oauth_authorization_codes
           (id, code, app_id, user_id, redirect_uri, scopes, code_challenge,
            code_challenge_method, expires_at, used, created)
           VALUES (:id, :code, :app_id, :user_id, :redirect_uri, :scopes,
                   :code_challenge, :code_challenge_method, :expires_at, :used, :created)""",
        {
            "id": code_id,
            "code": code,
            "app_id": app["id"],
            "user_id": current_user.id,
            "redirect_uri": redirect_uri,
            "scopes": json.dumps(requested_scopes),
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
            "expires_at": expires_at,
            "used": 0,
            "created": datetime.utcnow().isoformat()
        }
    )

    # Redirect back to application with code
    from urllib.parse import urlencode
    from fastapi.responses import RedirectResponse

    params = {
        "code": code,
    }
    if state:
        params["state"] = state

    redirect_url = f"{redirect_uri}?{urlencode(params)}"
    return RedirectResponse(url=redirect_url)


@oauth_protocol_router.post("/token")
async def token_endpoint_extended(
    grant_type: str = Form(...),
    client_id: str = Form(...),
    client_secret: Optional[str] = Form(None),
    code: Optional[str] = Form(None),
    redirect_uri: Optional[str] = Form(None),
    code_verifier: Optional[str] = Form(None),
    refresh_token: Optional[str] = Form(None),
    scope: Optional[str] = Form(None)
):
    """
    Token Endpoint supporting multiple grant types:
    - client_credentials: Server-to-server authentication
    - authorization_code: User-authorized access with PKCE
    - refresh_token: Refresh access token

    Examples:
        # Client Credentials
        POST /oauth/token
        grant_type=client_credentials&client_id=xxx&client_secret=xxx&scope=read:agents

        # Authorization Code with PKCE
        POST /oauth/token
        grant_type=authorization_code&code=xxx&client_id=xxx&redirect_uri=xxx&code_verifier=xxx

        # Refresh Token
        POST /oauth/token
        grant_type=refresh_token&refresh_token=xxx&client_id=xxx
    """
    if grant_type == "client_credentials":
        # Original client credentials flow (keep existing logic)
        return await issue_token(TokenRequest(
            grant_type=grant_type,
            client_id=client_id,
            client_secret=client_secret or "",
            scope=scope
        ))

    elif grant_type == "authorization_code":
        # Authorization Code flow
        if not code or not redirect_uri:
            raise HTTPException(
                status_code=400,
                detail="code and redirect_uri are required for authorization_code grant"
            )

        # Fetch authorization code
        code_rows = await repo_query(
            "SELECT * FROM oauth_authorization_codes WHERE code = :code AND used = 0",
            {"code": code}
        )
        if not code_rows:
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired authorization code"
            )

        auth_code = code_rows[0]

        # Check expiration
        if datetime.fromisoformat(auth_code["expires_at"]) < datetime.utcnow():
            raise HTTPException(
                status_code=400,
                detail="Authorization code has expired"
            )

        # Validate client_id
        if auth_code["app_id"] != client_id:
            # Need to get app_id from client_id
            app_rows = await repo_query(
                "SELECT id FROM oauth_applications WHERE client_id = :client_id",
                {"client_id": client_id}
            )
            if not app_rows or app_rows[0]["id"] != auth_code["app_id"]:
                raise HTTPException(
                    status_code=400,
                    detail="client_id does not match authorization code"
                )

        # Validate redirect_uri
        if auth_code["redirect_uri"] != redirect_uri:
            raise HTTPException(
                status_code=400,
                detail="redirect_uri does not match"
            )

        # Validate PKCE if code_challenge was provided
        if auth_code["code_challenge"]:
            if not code_verifier:
                raise HTTPException(
                    status_code=400,
                    detail="code_verifier required for PKCE flow"
                )

            # Verify code_verifier against code_challenge
            import hashlib
            import base64

            if auth_code["code_challenge_method"] == "S256":
                # SHA256 hash of verifier
                verifier_hash = hashlib.sha256(code_verifier.encode()).digest()
                computed_challenge = base64.urlsafe_b64encode(verifier_hash).decode().rstrip("=")
            else:  # plain
                computed_challenge = code_verifier

            if computed_challenge != auth_code["code_challenge"]:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid code_verifier"
                )

        # Mark code as used
        await repo_execute(
            "UPDATE oauth_authorization_codes SET used = 1 WHERE id = :id",
            {"id": auth_code["id"]}
        )

        # Get application details
        app_rows = await repo_query(
            "SELECT * FROM oauth_applications WHERE id = :id",
            {"id": auth_code["app_id"]}
        )
        if not app_rows:
            raise HTTPException(status_code=400, detail="Application not found")

        app = app_rows[0]

        # Generate access token
        scopes = json.loads(auth_code["scopes"])
        jti = str(uuid.uuid4())
        exp = datetime.utcnow() + timedelta(seconds=app["token_expiry_seconds"])

        token_payload = {
            "sub": app["id"],
            "client_id": client_id,
            "user_id": auth_code["user_id"],
            "scopes": scopes,
            "type": "oauth_access",
            "exp": int(exp.timestamp()),
            "iat": int(datetime.utcnow().timestamp()),
            "jti": jti
        }

        access_token = jwt.encode(token_payload, SECRET_KEY, algorithm=ALGORITHM)

        # Generate refresh token
        refresh_token_value = secrets.token_urlsafe(32)
        refresh_token_id = str(uuid.uuid4())
        refresh_expires_at = (datetime.utcnow() + timedelta(days=30)).isoformat()

        await repo_execute(
            """INSERT INTO oauth_refresh_tokens
               (id, token, app_id, user_id, scopes, expires_at, revoked, created)
               VALUES (:id, :token, :app_id, :user_id, :scopes, :expires_at, :revoked, :created)""",
            {
                "id": refresh_token_id,
                "token": refresh_token_value,
                "app_id": app["id"],
                "user_id": auth_code["user_id"],
                "scopes": json.dumps(scopes),
                "expires_at": refresh_expires_at,
                "revoked": 0,
                "created": datetime.utcnow().isoformat()
            }
        )

        return TokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=app["token_expiry_seconds"],
            refresh_token=refresh_token_value,
            scope=" ".join(scopes)
        )

    elif grant_type == "refresh_token":
        # Refresh Token flow
        if not refresh_token:
            raise HTTPException(
                status_code=400,
                detail="refresh_token is required"
            )

        # Fetch refresh token
        rt_rows = await repo_query(
            "SELECT * FROM oauth_refresh_tokens WHERE token = :token AND revoked = 0",
            {"token": refresh_token}
        )
        if not rt_rows:
            raise HTTPException(
                status_code=400,
                detail="Invalid or revoked refresh token"
            )

        rt = rt_rows[0]

        # Check expiration
        if datetime.fromisoformat(rt["expires_at"]) < datetime.utcnow():
            raise HTTPException(
                status_code=400,
                detail="Refresh token has expired"
            )

        # Get application
        app_rows = await repo_query(
            "SELECT * FROM oauth_applications WHERE id = :id",
            {"id": rt["app_id"]}
        )
        if not app_rows:
            raise HTTPException(status_code=400, detail="Application not found")

        app = app_rows[0]

        # Generate new access token
        scopes = json.loads(rt["scopes"])
        jti = str(uuid.uuid4())
        exp = datetime.utcnow() + timedelta(seconds=app["token_expiry_seconds"])

        token_payload = {
            "sub": app["id"],
            "client_id": app["client_id"],
            "user_id": rt["user_id"],
            "scopes": scopes,
            "type": "oauth_access",
            "exp": int(exp.timestamp()),
            "iat": int(datetime.utcnow().timestamp()),
            "jti": jti
        }

        access_token = jwt.encode(token_payload, SECRET_KEY, algorithm=ALGORITHM)

        return TokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=app["token_expiry_seconds"],
            scope=" ".join(scopes)
        )

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported grant_type: {grant_type}"
        )
