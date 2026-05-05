"""
OAuth Audit Logging Middleware

Logs all OAuth API calls to the audit log table for security monitoring and usage analytics.
"""

import asyncio
import json
import time
import uuid
from datetime import datetime

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt

from api.dependencies.auth import SECRET_KEY, ALGORITHM
from open_notebook.database.repository import repo_execute, repo_update


class OAuthAuditMiddleware(BaseHTTPMiddleware):
    """
    Audit logging middleware for OAuth API calls.

    Logs all OAuth requests to oauth_audit_log table and updates last_used_at.
    Fire-and-forget async logging (non-blocking).
    """

    async def dispatch(self, request: Request, call_next):
        # Only log OAuth requests to /api/agents/*
        if not request.url.path.startswith("/api/agents"):
            return await call_next(request)

        # Extract OAuth token
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return await call_next(request)

        try:
            # Decode token (lightweight, no validation)
            token = auth_header[7:]
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_signature": False})

            # Check if OAuth token
            if payload.get("type") != "oauth_access":
                # User JWT token, skip audit logging
                return await call_next(request)

            client_id = payload.get("client_id")
            app_id = payload.get("sub")
            scopes = payload.get("scopes", [])

            if not client_id or not app_id:
                return await call_next(request)

            # Record start time
            start_time = time.time()

            # Process request
            response = await call_next(request)

            # Calculate response time
            response_time_ms = int((time.time() - start_time) * 1000)

            # Get client IP and user agent
            client_ip = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")

            # Fire-and-forget async logging
            asyncio.create_task(
                self._log_request(
                    client_id=client_id,
                    app_id=app_id,
                    endpoint=request.url.path,
                    method=request.method,
                    status_code=response.status_code,
                    scopes_used=scopes,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    response_time_ms=response_time_ms
                )
            )

            return response

        except Exception as e:
            # Don't block requests if audit logging fails
            print(f"Audit logging error: {e}")
            return await call_next(request)

    async def _log_request(
        self,
        client_id: str,
        app_id: str,
        endpoint: str,
        method: str,
        status_code: int,
        scopes_used: list,
        ip_address: str,
        user_agent: str,
        response_time_ms: int
    ):
        """Log request to audit table (fire-and-forget)"""
        try:
            log_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()

            # Insert audit log
            await repo_execute(
                """INSERT INTO oauth_audit_log
                   (id, client_id, app_id, endpoint, method, status_code, scopes_used,
                    ip_address, user_agent, response_time_ms, created)
                   VALUES (:id, :client_id, :app_id, :endpoint, :method, :status_code,
                           :scopes_used, :ip_address, :user_agent, :response_time_ms, :created)""",
                {
                    "id": log_id,
                    "client_id": client_id,
                    "app_id": app_id,
                    "endpoint": endpoint,
                    "method": method,
                    "status_code": status_code,
                    "scopes_used": json.dumps(scopes_used),
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                    "response_time_ms": response_time_ms,
                    "created": now
                }
            )

            # Update last_used_at on application
            await repo_update("oauth_applications", app_id, {
                "last_used_at": now
            })

        except Exception as e:
            # Log error but don't raise
            print(f"Failed to write audit log: {e}")
