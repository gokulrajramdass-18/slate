"""
MCP Server OAuth Endpoints
Provides OAuth authorization and callback handling for MCP servers.

Per-user OAuth model:
  - Each logged-in user authenticates MCP servers with their own identity.
  - Tokens are stored in mcp_oauth_tokens keyed on (server_id, user_id).
  - OAuth client_id/secret (RFC 7591 dynamic registration) stays shared per
    server.
  - The user_id travels through the IdP round-trip inside a signed `state`
    parameter so the public /callback endpoint can resolve it without trusting
    cookies.
"""

import os
from fastapi import APIRouter, Depends, Request, Query, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
import secrets
import httpx
import hashlib
import base64
from datetime import datetime, timedelta
import logging

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from api.dependencies.auth import get_current_active_user
from open_notebook.domain.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp-servers", tags=["mcp-oauth"])

# In-memory session storage (use Redis in production)
# Key: session_id -> {server_id, user_id, csrf, code_verifier, oauth_config,
#                     client_id, client_secret, created_at}
oauth_sessions = {}

# Signed state lifetime. The IdP redirect typically completes in seconds; we
# allow 10 minutes to absorb slow logins, MFA prompts, etc.
OAUTH_STATE_MAX_AGE_SECONDS = 600

# Serializer used to sign the OAuth `state` parameter so the public /callback
# endpoint can recover {server_id, user_id, csrf} without trusting cookies.
# We salt with a constant so the same secret can be reused for other signed
# tokens elsewhere in the codebase without collision.
_state_serializer: URLSafeTimedSerializer | None = None


def _get_state_serializer() -> URLSafeTimedSerializer:
    """Lazy-init the state serializer using OPEN_NOTEBOOK_ENCRYPTION_KEY."""
    global _state_serializer
    if _state_serializer is None:
        secret = os.getenv("OPEN_NOTEBOOK_ENCRYPTION_KEY")
        if not secret:
            # Fall back to JWT secret if available — never let this be empty.
            from api.dependencies import auth as _auth
            secret = _auth.SECRET_KEY or "mcp-oauth-state-fallback-do-not-use-in-prod"
        _state_serializer = URLSafeTimedSerializer(
            secret_key=secret,
            salt="mcp-oauth-state",
        )
    return _state_serializer


def _sign_state(payload: dict) -> str:
    """Sign an opaque state payload for the OAuth round-trip."""
    return _get_state_serializer().dumps(payload)


def _verify_state(token: str) -> dict:
    """Verify and decode a signed state token. Raises HTTPException on failure."""
    try:
        return _get_state_serializer().loads(
            token, max_age=OAUTH_STATE_MAX_AGE_SECONDS
        )
    except SignatureExpired:
        raise HTTPException(status_code=400, detail="OAuth state expired")
    except BadSignature:
        raise HTTPException(status_code=400, detail="OAuth state invalid")

# OAuth provider configuration (should be in environment variables or database)
OAUTH_PROVIDERS = {
    "outreach": {
        "authorization_url": "https://accounts.outreach.io/oauth/authorize",
        "token_url": "https://api.outreach.io/oauth/token",
        "scopes": ["prospects.read", "prospects.write", "users.read"],
        "client_id": None,  # Set from environment or database
        "client_secret": None,
    }
}


def generate_pkce_challenge(verifier: str) -> str:
    """Generate PKCE code challenge from verifier"""
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip('=')


def _public_base_url(request: Request) -> str:
    """
    Resolve the public-facing base URL for building OAuth redirect URIs.

    Behind AppRouter (XSUAA mode) `request.base_url` is the *internal*
    backend URL (e.g. http://localhost:5055/) — the address the AppRouter
    talks to. OAuth providers strict-match the `redirect_uri` against
    what was registered, and the user's browser hits the public AppRouter
    origin (e.g. http://localhost:5001/), so the internal URL never works.

    Set `PUBLIC_BASE_URL` (no trailing slash) to the AppRouter's origin
    in production / XSUAA mode. We fall back to `request.base_url` for
    local dev where the backend is reached directly.
    """
    public = os.getenv("PUBLIC_BASE_URL", "").strip()
    if public:
        return public.rstrip("/")
    return str(request.base_url).rstrip("/")


@router.post("/{server_id}/oauth/start")
async def mcp_oauth_start(
    server_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    """
    Begin an OAuth flow for this server.

    The frontend calls this with the user's JWT, then opens the returned
    `authorization_url` in a popup. The `state` parameter is signed and
    contains `{server_id, user_id, csrf}` so the public `/callback`
    endpoint can recover the user's identity without trusting cookies.

    For system-mode servers, only admins may initiate the flow — see
    `_build_authorization_url` for the gate.
    """
    auth_url, _session_id = await _build_authorization_url(
        server_id=server_id,
        current_user=current_user,
        request=request,
    )
    return {"authorization_url": auth_url}


@router.get("/{server_id}/oauth/authorize")
async def mcp_oauth_authorize(
    server_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    """
    Authenticated convenience redirect. Same as /oauth/start but returns a
    302 to the IdP. Used when the frontend prefers a top-level navigation.
    """
    auth_url, _session_id = await _build_authorization_url(
        server_id=server_id,
        current_user=current_user,
        request=request,
    )
    response = RedirectResponse(url=auth_url, status_code=302)
    return response


async def _build_authorization_url(
    server_id: str,
    current_user: User,
    request: Request,
) -> tuple[str, str]:
    """
    Discover OAuth config, register a client if needed, and return the
    provider authorization URL with a signed state. The state encodes the
    initiating user's id so the public callback can route the resulting
    tokens to the correct row — for user-mode that's `current_user.id`;
    for system-mode the substitution to `__system__` happens at storage
    time (in the callback) via `effective_token_user_id`.

    Returns:
        (authorization_url, session_id)
    """
    # Look up the server first so we can apply the system-mode admin gate
    # *before* doing any expensive discovery / registration work and
    # before leaking the provider URL to non-admin callers.
    server = await get_mcp_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    if (server.get("oauth_mode") or "user") == "system" and not current_user.is_superadmin:
        raise HTTPException(
            status_code=403,
            detail=(
                "Only administrators can authenticate a system-mode MCP "
                "server (its tokens are shared across all users)."
            ),
        )

    user_id = current_user.id

    # Step 1: Discover OAuth configuration
    oauth_config = await discover_oauth_configuration(server["url"])
    if not oauth_config:
        raise HTTPException(
            status_code=400, detail="OAuth not supported by this server"
        )

    # Step 2: Reuse the shared client registration if we already have one
    existing_client = await get_stored_client_credentials(server_id)
    if existing_client:
        client_id = existing_client["client_id"]
        client_secret = existing_client.get("client_secret")
    elif oauth_config.get("registration_endpoint"):
        # Step 3: Use Dynamic Client Registration (RFC 7591)
        try:
            registered_client = await register_oauth_client_dynamically(
                registration_endpoint=oauth_config["registration_endpoint"],
                server_id=server_id,
                base_url=_public_base_url(request),
            )
            client_id = registered_client["client_id"]
            client_secret = registered_client.get("client_secret")
            await store_client_credentials(
                server_id=server_id,
                client_id=client_id,
                client_secret=client_secret,
                registration_response=registered_client,
            )
        except Exception as e:
            logger.error(f"Dynamic client registration failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Could not register OAuth client: {str(e)}",
            )
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                "OAuth provider does not support Dynamic Client Registration. "
                "Manual configuration required."
            ),
        )

    # CSRF nonce + PKCE
    csrf = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(32)
    code_challenge = generate_pkce_challenge(code_verifier)

    # Sign state so the public /callback can trust it
    state = _sign_state({
        "server_id": server_id,
        "user_id": user_id,
        "csrf": csrf,
    })

    # Cache verifier + client creds for the callback (server-side only)
    session_id = secrets.token_urlsafe(32)
    oauth_sessions[session_id] = {
        "server_id": server_id,
        "user_id": user_id,
        "csrf": csrf,
        "code_verifier": code_verifier,
        "created_at": datetime.now(),
        "oauth_config": oauth_config,
        "client_id": client_id,
        "client_secret": client_secret,
    }

    # Build redirect_uri off the *public* origin so it matches what was
    # registered with the IdP (and what the user's browser actually sees).
    base_url = _public_base_url(request)
    redirect_uri = f"{base_url}/api/mcp-servers/{server_id}/oauth/callback"

    scopes = oauth_config.get("scopes_supported", [])
    scope_string = " ".join(scopes) if scopes else ""

    # Index the verifier by csrf as well so the callback can find it without
    # cookies (popup cross-origin returns can drop SameSite=Lax cookies).
    oauth_sessions[f"csrf:{csrf}"] = session_id

    authorization_url = (
        f"{oauth_config['authorization_endpoint']}"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&state={state}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
    )
    if scope_string:
        authorization_url += f"&scope={scope_string}"

    logger.info(
        f"Built OAuth URL for server={server_id} user={user_id} "
        f"(dynamic registration)"
    )
    return authorization_url, session_id


@router.get("/{server_id}/oauth/callback")
async def mcp_oauth_callback(
    server_id: str,
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
):
    """
    Handle OAuth callback from provider.

    Public endpoint (the IdP redirects here unauthenticated). The user's
    identity is recovered from the signed `state` parameter, which was
    generated server-side in /oauth/start with `current_user.id` baked in.
    """
    import json

    try:
        # Recover {server_id, user_id, csrf} from the signed state. This
        # raises HTTPException on tampering or expiry.
        decoded = _verify_state(state)
        if decoded.get("server_id") != server_id:
            return error_html("Server ID mismatch in state")
        user_id = decoded.get("user_id")
        csrf = decoded.get("csrf")
        if not user_id or not csrf:
            return error_html("Malformed OAuth state")

        # Resolve the server row up-front so we know whether to store
        # under '__system__' (system-mode) or under user_id (user-mode).
        # The IdP-initiated callback is unauthenticated by definition,
        # but the signed state already proved a server-side /start call
        # was made by an admin (the gate fires before the state is
        # signed), so we trust the mode flag here.
        server_row = await get_mcp_server(server_id)
        if not server_row:
            return error_html("Server no longer exists")

        # Find the cached session via the csrf index. This carries the
        # PKCE verifier + client credentials but NOT the user identity —
        # the signed state is authoritative for user_id.
        session_id = oauth_sessions.get(f"csrf:{csrf}")
        if not session_id or session_id not in oauth_sessions:
            return error_html("Invalid or expired session")
        session = oauth_sessions[session_id]

        # Defense in depth: the cached session must agree with the state.
        if session.get("user_id") != user_id or session.get("server_id") != server_id:
            return error_html("Session does not match signed state")

        provider_config = session["oauth_config"]
        client_id = session["client_id"]
        client_secret = session.get("client_secret")

        # Build the same redirect_uri we registered with — IdP token
        # exchange strict-matches it against the authorize call.
        base_url = _public_base_url(request)
        redirect_uri = f"{base_url}/api/mcp-servers/{server_id}/oauth/callback"

        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                provider_config["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code_verifier": session["code_verifier"],
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
            )

        if token_response.status_code != 200:
            logger.error(f"Token exchange failed: {token_response.text}")
            return error_html(f"Token exchange failed: {token_response.text}")

        token_data = token_response.json()
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)

        if not access_token:
            return error_html("No access token received")

        # Provider-specific user info (Outreach). Best-effort.
        user_info = None
        try:
            async with httpx.AsyncClient() as client:
                user_response = await client.get(
                    "https://api.outreach.io/api/v2/users/me",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/vnd.api+json",
                    },
                )
            if user_response.status_code == 200:
                user_data = user_response.json()
                user_info = {
                    "id": user_data["data"]["id"],
                    "email": user_data["data"]["attributes"].get("email"),
                    "name": user_data["data"]["attributes"].get("name"),
                }
        except Exception as e:
            logger.warning(f"Failed to get user info: {e}")

        # Persist tokens. For user-mode servers we key on the admin/user
        # who completed the flow (`user_id`); for system-mode servers the
        # helper redirects storage to the shared `__system__` row, which
        # all users will read from going forward. The signed `state`
        # still records who actually authenticated — that's the audit
        # trail; the row itself is intentionally shared.
        from api.services.mcp_client import effective_token_user_id

        token_user_id = effective_token_user_id(server_row, user_id)
        await store_oauth_tokens(
            server_id=server_id,
            user_id=token_user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            user_info=user_info,
        )

        # For OAuth servers we no longer mirror the access token into
        # mcp_servers.auth_config_encrypted — that field was a single
        # shared bucket. We only update the global metadata so the
        # admin-facing list shows that *some* user has authenticated.
        from open_notebook.database.repository import repo_execute

        now = datetime.now().isoformat()
        await repo_execute(
            """
            UPDATE mcp_servers
            SET auth_type = :auth_type,
                status = :status,
                last_test_at = :last_test_at,
                last_test_message = :last_test_message,
                updated_at = :updated_at
            WHERE id = :id
            """,
            {
                "auth_type": "oauth",
                "status": "connected",
                "last_test_at": now,
                "last_test_message": (
                    "OAuth authentication successful (per-user tokens)."
                ),
                "updated_at": now,
                "id": server_id,
            },
        )

        logger.info(
            f"✅ OAuth successful: server={server_id} user={user_id}"
        )

        # Eagerly discover tools / resources / prompts so the UI lands on
        # a "connected" card with real tool counts instead of zeros. This
        # also seeds `mcp_tools`, which the agent toolset queries on every
        # session start. Failures here are non-fatal — the user can still
        # press the Test button to retry, and the next agent session
        # would also surface the issue.
        try:
            from api.services.mcp_client import (
                discover_and_cache_capabilities,
                effective_token_user_id as _eff,
            )

            # Re-fetch the server row to pick up the newly persisted
            # auth_type / status fields the UPDATE above just wrote.
            fresh_row = await get_mcp_server(server_id)
            if fresh_row:
                pool_user_id = _eff(fresh_row, user_id)
                await discover_and_cache_capabilities(
                    fresh_row, user_id=pool_user_id
                )
        except Exception as discover_err:
            logger.warning(
                f"Post-OAuth capability discovery failed for {server_id}: "
                f"{discover_err}"
            )

        # Clean up session entries
        oauth_sessions.pop(session_id, None)
        oauth_sessions.pop(f"csrf:{csrf}", None)

        return success_html(user_info)

    except HTTPException:
        # Already a clean error response — re-raise so FastAPI handles it.
        raise
    except Exception as e:
        logger.error(f"OAuth callback error: {e}", exc_info=True)
        return error_html(f"Authentication failed: {str(e)}")


def success_html(user_info: dict = None) -> HTMLResponse:
    """Generate success page that sends tokens to parent window"""
    import json

    user_info_json = json.dumps(user_info) if user_info else 'null'
    user_display = user_info.get('email') or user_info.get('name') if user_info else 'User'

    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Successfully Connected</title>
        <style>
          * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
          }}
          body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          }}
          .container {{
            background: white;
            padding: 3rem;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align: center;
            max-width: 400px;
            animation: slideUp 0.5s ease-out;
          }}
          @keyframes slideUp {{
            from {{
              opacity: 0;
              transform: translateY(20px);
            }}
            to {{
              opacity: 1;
              transform: translateY(0);
            }}
          }}
          .success-icon {{
            width: 80px;
            height: 80px;
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 1.5rem;
            font-size: 48px;
            color: white;
            animation: scaleIn 0.5s ease-out 0.2s backwards;
          }}
          @keyframes scaleIn {{
            from {{
              transform: scale(0);
            }}
            to {{
              transform: scale(1);
            }}
          }}
          h1 {{
            color: #1f2937;
            margin: 0 0 0.5rem;
            font-size: 1.75rem;
            font-weight: 600;
          }}
          .subtitle {{
            color: #6b7280;
            margin: 0 0 1.5rem;
            font-size: 0.95rem;
          }}
          .user-info {{
            background: linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%);
            padding: 1rem;
            border-radius: 12px;
            margin-bottom: 1.5rem;
          }}
          .user-info strong {{
            display: block;
            color: #374151;
            font-size: 0.95rem;
            margin-bottom: 0.25rem;
          }}
          .user-info span {{
            color: #6b7280;
            font-size: 0.875rem;
          }}
          .spinner {{
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
          }}
          @keyframes spin {{
            0% {{ transform: rotate(0deg); }}
            100% {{ transform: rotate(360deg); }}
          }}
          .closing-message {{
            color: #9ca3af;
            font-size: 0.875rem;
            margin-top: 1rem;
          }}
        </style>
      </head>
      <body>
        <div class="container">
          <div class="success-icon">✓</div>
          <h1>Successfully Connected!</h1>
          <p class="subtitle">Authentication completed</p>

          {f'''
          <div class="user-info">
            <strong>Connected Account</strong>
            <span>{user_display}</span>
          </div>
          ''' if user_info else ''}

          <div class="spinner"></div>
          <p class="closing-message">Completing setup...</p>
        </div>
        <script>
          (function() {{
            try {{
              // Send success message to parent window
              if (window.opener) {{
                window.opener.postMessage({{
                  type: 'mcp_oauth_success',
                  access_token: 'stored_securely',  // Don't send actual token to frontend
                  connected: true,
                  user_info: {user_info_json}
                }}, '*');

                // Close window after brief delay
                setTimeout(function() {{
                  window.close();
                }}, 1500);
              }} else {{
                document.querySelector('.closing-message').textContent = 'You can close this window.';
                document.querySelector('.spinner').style.display = 'none';
              }}
            }} catch (error) {{
              console.error('PostMessage error:', error);
            }}
          }})();
        </script>
      </body>
    </html>
    """)


def error_html(error_message: str) -> HTMLResponse:
    """Generate error page"""
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Authentication Error</title>
        <style>
          * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
          }}
          body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            background: #f3f4f6;
          }}
          .container {{
            background: white;
            padding: 3rem;
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            text-align: center;
            max-width: 400px;
          }}
          .error-icon {{
            width: 80px;
            height: 80px;
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 1.5rem;
            font-size: 48px;
            color: white;
          }}
          h1 {{
            color: #dc2626;
            margin: 0 0 0.5rem;
            font-size: 1.75rem;
            font-weight: 600;
          }}
          p {{
            color: #6b7280;
            line-height: 1.6;
          }}
          .error-details {{
            background: #fef2f2;
            border: 1px solid #fecaca;
            padding: 1rem;
            border-radius: 8px;
            margin-top: 1.5rem;
            text-align: left;
          }}
          .error-details code {{
            color: #dc2626;
            font-size: 0.875rem;
            word-break: break-word;
          }}
        </style>
      </head>
      <body>
        <div class="container">
          <div class="error-icon">✕</div>
          <h1>Authentication Failed</h1>
          <p>We couldn't complete the authentication process.</p>
          <div class="error-details">
            <code>{error_message}</code>
          </div>
        </div>
        <script>
          if (window.opener) {{
            window.opener.postMessage({{
              type: 'mcp_oauth_error',
              error: 'authentication_failed',
              error_description: '{error_message}'
            }}, '*');

            setTimeout(function() {{
              window.close();
            }}, 5000);
          }}
        </script>
      </body>
    </html>
    """)


# Helper functions (implement these based on your database)

async def discover_oauth_configuration(server_url: str) -> dict | None:
    """
    Automatically discover OAuth configuration from server.
    Tries multiple discovery methods:
    1. RFC 8414: OAuth 2.0 Authorization Server Metadata
    2. OpenID Connect Discovery
    3. Well-known endpoints
    """
    # Extract base URL (remove path after domain)
    from urllib.parse import urlparse
    parsed = urlparse(server_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    logger.info(f"Attempting OAuth discovery for server: {server_url}")
    logger.info(f"Base URL for discovery: {base_url}")

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        # Try RFC 8414 at base URL first (most common)
        discovery_urls = [
            f"{base_url}/.well-known/oauth-authorization-server",
            f"{server_url}/.well-known/oauth-authorization-server",
            f"{base_url}/.well-known/openid-configuration",
            f"{server_url}/.well-known/openid-configuration",
            f"{base_url}/.well-known/oauth-config",
            f"{server_url}/.well-known/oauth-config",
        ]

        for discovery_url in discovery_urls:
            try:
                logger.debug(f"Trying discovery at: {discovery_url}")
                response = await client.get(discovery_url)
                if response.status_code == 200:
                    config = response.json()
                    logger.info(f"✅ Discovered OAuth config at: {discovery_url}")
                    return config
            except Exception as e:
                logger.debug(f"Discovery failed at {discovery_url}: {e}")
                continue

    logger.warning(f"❌ Could not discover OAuth configuration for {server_url}")
    logger.warning(f"Tried URLs: {discovery_urls}")
    return None


async def register_oauth_client_dynamically(
    registration_endpoint: str,
    server_id: str,
    base_url: str
) -> dict:
    """
    Register OAuth client dynamically using RFC 7591.
    No manual configuration needed!
    """
    redirect_uri = f"{base_url}/api/mcp-servers/{server_id}/oauth/callback"

    registration_data = {
        "client_name": "Open Notebook",
        "client_uri": base_url,
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "client_secret_post",
        "application_type": "web",
        "software_id": "open-notebook",
        "software_version": "1.0.0",
    }

    logger.info(f"Attempting dynamic client registration at {registration_endpoint}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            registration_endpoint,
            json=registration_data,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        )

    if response.status_code in [200, 201]:
        result = response.json()
        logger.info(f"Successfully registered OAuth client: {result.get('client_id')}")
        return result

    raise Exception(f"Client registration failed ({response.status_code}): {response.text}")


async def get_mcp_server(server_id: str):
    """Get MCP server from database"""
    from open_notebook.database.repository import repo_query

    result = await repo_query(
        "SELECT * FROM mcp_servers WHERE id = :id",
        {"id": server_id}
    )
    if result:
        return dict(result[0])
    return None


async def get_stored_client_credentials(server_id: str) -> dict | None:
    """Get stored OAuth client credentials for server"""
    from open_notebook.database.repository import repo_query

    result = await repo_query(
        "SELECT * FROM mcp_oauth_clients WHERE server_id = :server_id",
        {"server_id": server_id}
    )
    if result:
        return dict(result[0])
    return None


async def store_client_credentials(
    server_id: str,
    client_id: str,
    client_secret: str,
    registration_response: dict
):
    """Store OAuth client credentials from dynamic registration"""
    from open_notebook.database.repository import repo_execute
    import json

    await repo_execute("""
        INSERT OR REPLACE INTO mcp_oauth_clients
        (server_id, client_id, client_secret, registration_data, created_at)
        VALUES (:server_id, :client_id, :client_secret, :registration_data, :created_at)
    """, {
        "server_id": server_id,
        "client_id": client_id,
        "client_secret": client_secret,  # Should be encrypted in production
        "registration_data": json.dumps(registration_response),
        "created_at": datetime.now().isoformat()
    })

    logger.info(f"Stored OAuth client credentials for server {server_id}")


def get_oauth_client_id(server_id: str) -> str:
    """Get OAuth client ID for server from environment or database"""
    # Fallback to environment variable (legacy)
    import os
    return os.getenv("OUTREACH_CLIENT_ID", "")


def get_oauth_client_secret(server_id: str) -> str:
    """Get OAuth client secret for server from environment or database"""
    # Fallback to environment variable (legacy)
    import os
    return os.getenv("OUTREACH_CLIENT_SECRET", "")


async def store_oauth_tokens(
    server_id: str,
    user_id: str,
    access_token: str,
    refresh_token: str,
    expires_in: int,
    user_info: dict = None,
):
    """
    Store OAuth tokens in the database, encrypted at rest.

    Tokens are scoped to (server_id, user_id) — each user has their own
    pair, refreshed independently. Tokens are encrypted using the same
    Fernet helper that `mcp_servers.auth_config_encrypted` uses, so they
    can be decrypted by `MCPClientFactory.create_client()`.
    """
    from open_notebook.database.repository import repo_execute
    from api.routers.mcp_servers import encrypt_password
    import json

    expires_at = datetime.now() + timedelta(seconds=expires_in)

    encrypted_access = encrypt_password(access_token) if access_token else None
    encrypted_refresh = encrypt_password(refresh_token) if refresh_token else None

    await repo_execute(
        """
        INSERT OR REPLACE INTO mcp_oauth_tokens
        (server_id, user_id, access_token, refresh_token, expires_at, user_info, updated_at)
        VALUES (:server_id, :user_id, :access_token, :refresh_token, :expires_at, :user_info, :updated_at)
        """,
        {
            "server_id": server_id,
            "user_id": user_id,
            "access_token": encrypted_access,
            "refresh_token": encrypted_refresh,
            "expires_at": expires_at.isoformat(),
            "user_info": json.dumps(user_info) if user_info else None,
            "updated_at": datetime.now().isoformat(),
        },
    )

    logger.info(f"Stored OAuth tokens: server={server_id} user={user_id}")
