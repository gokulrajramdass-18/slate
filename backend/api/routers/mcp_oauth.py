"""
MCP Server OAuth Endpoints
Provides OAuth authorization and callback handling for MCP servers.
"""

from fastapi import APIRouter, Request, Query, HTTPException, Response
from fastapi.responses import RedirectResponse, HTMLResponse
import secrets
import httpx
import hashlib
import base64
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp-servers", tags=["mcp-oauth"])

# In-memory session storage (use Redis in production)
oauth_sessions = {}

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


@router.get("/{server_id}/oauth/authorize")
async def mcp_oauth_authorize(
    server_id: str,
    request: Request
):
    """
    PUBLIC ENDPOINT - No authentication required

    Automatically discovers OAuth configuration and uses Dynamic Client
    Registration (RFC 7591) if supported. No manual configuration needed!
    """
    try:
        # Get MCP server configuration from database
        server = await get_mcp_server(server_id)
        if not server:
            raise HTTPException(status_code=404, detail="Server not found")

        # Step 1: Discover OAuth configuration
        oauth_config = await discover_oauth_configuration(server["url"])
        if not oauth_config:
            return error_html("OAuth not supported by this server")

        # Step 2: Check if we have existing client credentials
        existing_client = await get_stored_client_credentials(server_id)

        if existing_client:
            # Use existing credentials
            client_id = existing_client['client_id']
            client_secret = existing_client.get('client_secret')
        elif oauth_config.get('registration_endpoint'):
            # Step 3: Use Dynamic Client Registration (RFC 7591)
            try:
                registered_client = await register_oauth_client_dynamically(
                    registration_endpoint=oauth_config['registration_endpoint'],
                    server_id=server_id,
                    base_url=str(request.base_url).rstrip('/')
                )
                client_id = registered_client['client_id']
                client_secret = registered_client.get('client_secret')

                # Store credentials for future use
                await store_client_credentials(
                    server_id=server_id,
                    client_id=client_id,
                    client_secret=client_secret,
                    registration_response=registered_client
                )
            except Exception as e:
                logger.error(f"Dynamic client registration failed: {e}")
                return error_html(f"Could not register OAuth client: {str(e)}")
        else:
            return error_html(
                "OAuth provider does not support Dynamic Client Registration. "
                "Manual configuration required."
            )

        # Generate CSRF protection state
        state = secrets.token_urlsafe(32)

        # Generate PKCE parameters
        code_verifier = secrets.token_urlsafe(32)
        code_challenge = generate_pkce_challenge(code_verifier)

        # Create session ID
        session_id = secrets.token_urlsafe(32)

        # Store session data
        oauth_sessions[session_id] = {
            'server_id': server_id,
            'state': state,
            'code_verifier': code_verifier,
            'created_at': datetime.now(),
            'oauth_config': oauth_config,
            'client_id': client_id,
            'client_secret': client_secret,
        }

        # Build OAuth authorization URL
        base_url = str(request.base_url).rstrip('/')
        redirect_uri = f"{base_url}/api/mcp-servers/{server_id}/oauth/callback"

        # Build scopes - use what the server supports
        scopes = oauth_config.get('scopes_supported', [])
        scope_string = ' '.join(scopes) if scopes else ''

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

        logger.info(f"Redirecting to OAuth provider for server {server_id} (Dynamic Registration)")

        # Set session cookie
        response = RedirectResponse(url=authorization_url, status_code=302)
        response.set_cookie(
            key="oauth_session",
            value=session_id,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=600  # 10 minutes
        )

        return response

    except Exception as e:
        logger.error(f"OAuth authorization error: {e}")
        return error_html(f"Failed to initiate OAuth: {str(e)}")


@router.get("/{server_id}/oauth/callback")
async def mcp_oauth_callback(
    server_id: str,
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
):
    """
    Handle OAuth callback from provider.
    Exchange authorization code for access token.
    """
    import json

    try:
        # Get session from cookie
        session_id = request.cookies.get("oauth_session")
        if not session_id or session_id not in oauth_sessions:
            return error_html("Invalid or expired session")

        session = oauth_sessions[session_id]

        # Validate state (CSRF protection)
        if state != session['state']:
            return error_html("State mismatch - possible CSRF attack")

        # Validate server_id matches
        if server_id != session['server_id']:
            return error_html("Server ID mismatch")

        provider_config = session['oauth_config']

        # Get client credentials from session
        client_id = session['client_id']
        client_secret = session.get('client_secret')

        # Build redirect URI
        base_url = str(request.base_url).rstrip('/')
        redirect_uri = f"{base_url}/api/mcp-servers/{server_id}/oauth/callback"

        # Exchange authorization code for access token
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                provider_config['token_endpoint'],
                data={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': redirect_uri,
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'code_verifier': session['code_verifier'],
                },
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Accept': 'application/json',
                }
            )

        if token_response.status_code != 200:
            logger.error(f"Token exchange failed: {token_response.text}")
            return error_html(f"Token exchange failed: {token_response.text}")

        token_data = token_response.json()
        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token')
        expires_in = token_data.get('expires_in', 3600)

        if not access_token:
            return error_html("No access token received")

        # Get user info (optional, depends on provider)
        user_info = None
        try:
            async with httpx.AsyncClient() as client:
                user_response = await client.get(
                    "https://api.outreach.io/api/v2/users/me",
                    headers={
                        'Authorization': f"Bearer {access_token}",
                        'Content-Type': 'application/vnd.api+json',
                    }
                )

            if user_response.status_code == 200:
                user_data = user_response.json()
                user_info = {
                    'id': user_data['data']['id'],
                    'email': user_data['data']['attributes'].get('email'),
                    'name': user_data['data']['attributes'].get('name'),
                }
        except Exception as e:
            logger.warning(f"Failed to get user info: {e}")

        # Store tokens in database
        await store_oauth_tokens(
            server_id=server_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            user_info=user_info
        )

        # Update server auth config with token and mark as connected
        from open_notebook.database.repository import repo_execute
        from api.routers.mcp_servers import encrypt_password

        auth_config = {
            "type": "bearer",
            "token": access_token
        }

        auth_encrypted = encrypt_password(json.dumps(auth_config))

        now = datetime.now().isoformat()
        await repo_execute("""
            UPDATE mcp_servers
            SET auth_config_encrypted = :auth_config,
                auth_type = :auth_type,
                status = :status,
                last_test_at = :last_test_at,
                last_test_message = :last_test_message,
                updated_at = :updated_at
            WHERE id = :id
        """, {
            "auth_config": auth_encrypted,
            "auth_type": "oauth",
            "status": "connected",
            "last_test_at": now,
            "last_test_message": "OAuth authentication successful. Connection ready to use.",
            "updated_at": now,
            "id": server_id
        })

        logger.info(f"✅ OAuth successful for server {server_id} - marked as connected")

        # TODO: Queue background job to discover capabilities
        # For now, capabilities will be discovered on first use

        # Clean up session
        del oauth_sessions[session_id]

        logger.info(f"OAuth complete for server {server_id}")

        # Return success HTML with postMessage
        return success_html(user_info)

    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
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
    access_token: str,
    refresh_token: str,
    expires_in: int,
    user_info: dict = None
):
    """Store OAuth tokens in database (encrypted)"""
    # TODO: Implement encrypted token storage
    from open_notebook.database.repository import repo_execute
    import json

    expires_at = datetime.now() + timedelta(seconds=expires_in)

    # Encrypt tokens before storing
    # encrypted_access = encrypt_token(access_token)
    # encrypted_refresh = encrypt_token(refresh_token)

    await repo_execute("""
        INSERT OR REPLACE INTO mcp_oauth_tokens
        (server_id, access_token, refresh_token, expires_at, user_info, updated_at)
        VALUES (:server_id, :access_token, :refresh_token, :expires_at, :user_info, :updated_at)
    """, {
        "server_id": server_id,
        "access_token": access_token,  # Should be encrypted
        "refresh_token": refresh_token,  # Should be encrypted
        "expires_at": expires_at.isoformat(),
        "user_info": json.dumps(user_info) if user_info else None,
        "updated_at": datetime.now().isoformat()
    })

    logger.info(f"Stored OAuth tokens for server {server_id}")
