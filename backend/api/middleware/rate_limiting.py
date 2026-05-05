"""
OAuth Rate Limiting Middleware

Enforces per-application hourly and daily request quotas for OAuth API calls.
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, Tuple

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt

from api.dependencies.auth import SECRET_KEY, ALGORITHM
from open_notebook.database.repository import repo_query


class OAuthRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware for OAuth API calls.

    Only applies to /api/agents/* endpoints with OAuth tokens.
    Enforces per-application hourly and daily limits.
    """

    def __init__(self, app):
        super().__init__(app)
        # In-memory rate limit counters: {client_id: {"hourly": (count, reset_time), "daily": (count, reset_time)}}
        self.hourly_counts: Dict[str, Tuple[int, float]] = {}
        self.daily_counts: Dict[str, Tuple[int, float]] = {}
        # Cache rate limits: {app_id: (hourly_limit, daily_limit, cached_at)}
        self.rate_limit_cache: Dict[str, Tuple[int, int, float]] = {}
        self.cache_ttl = 300  # 5 minutes

    async def dispatch(self, request: Request, call_next):
        # Only apply to /api/agents/* paths
        if not request.url.path.startswith("/api/agents"):
            return await call_next(request)

        # Extract OAuth token from Authorization header
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            # Not an OAuth request, skip rate limiting
            return await call_next(request)

        try:
            # Decode token (lightweight, no validation)
            token = auth_header[7:]
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_signature": False})

            # Check if OAuth token
            if payload.get("type") != "oauth_access":
                # User JWT token, skip rate limiting
                return await call_next(request)

            client_id = payload.get("client_id")
            app_id = payload.get("sub")

            if not client_id or not app_id:
                return await call_next(request)

            # Get rate limits (cached)
            hourly_limit, daily_limit = await self._get_rate_limits(app_id)

            # Check hourly limit
            now = time.time()
            hour_start = now - (now % 3600)  # Start of current hour

            if client_id in self.hourly_counts:
                count, reset_time = self.hourly_counts[client_id]
                if reset_time > now:
                    # Within same hour
                    if count >= hourly_limit:
                        return self._rate_limit_response(
                            hourly_limit,
                            0,
                            int(reset_time - now),
                            "hourly"
                        )
                    self.hourly_counts[client_id] = (count + 1, reset_time)
                else:
                    # New hour
                    self.hourly_counts[client_id] = (1, hour_start + 3600)
            else:
                # First request this hour
                self.hourly_counts[client_id] = (1, hour_start + 3600)

            # Check daily limit
            day_start = now - (now % 86400)  # Start of current day

            if client_id in self.daily_counts:
                count, reset_time = self.daily_counts[client_id]
                if reset_time > now:
                    # Within same day
                    if count >= daily_limit:
                        return self._rate_limit_response(
                            daily_limit,
                            0,
                            int(reset_time - now),
                            "daily"
                        )
                    self.daily_counts[client_id] = (count + 1, reset_time)
                else:
                    # New day
                    self.daily_counts[client_id] = (1, day_start + 86400)
            else:
                # First request today
                self.daily_counts[client_id] = (1, day_start + 86400)

            # Process request
            response = await call_next(request)

            # Add rate limit headers
            hourly_count, hourly_reset = self.hourly_counts[client_id]
            daily_count, daily_reset = self.daily_counts[client_id]

            response.headers["X-RateLimit-Limit-Hour"] = str(hourly_limit)
            response.headers["X-RateLimit-Remaining-Hour"] = str(max(0, hourly_limit - hourly_count))
            response.headers["X-RateLimit-Reset-Hour"] = str(int(hourly_reset))

            response.headers["X-RateLimit-Limit-Day"] = str(daily_limit)
            response.headers["X-RateLimit-Remaining-Day"] = str(max(0, daily_limit - daily_count))
            response.headers["X-RateLimit-Reset-Day"] = str(int(daily_reset))

            return response

        except Exception as e:
            # Fail open - don't block requests if rate limiting fails
            print(f"Rate limiting error: {e}")
            return await call_next(request)

    async def _get_rate_limits(self, app_id: str) -> Tuple[int, int]:
        """Get rate limits for app (cached)"""
        now = time.time()

        # Check cache
        if app_id in self.rate_limit_cache:
            hourly, daily, cached_at = self.rate_limit_cache[app_id]
            if now - cached_at < self.cache_ttl:
                return (hourly, daily)

        # Query database
        try:
            rows = await repo_query(
                "SELECT rate_limit_per_hour, rate_limit_per_day FROM oauth_applications WHERE id = :id",
                {"id": app_id}
            )
            if rows:
                hourly = rows[0]["rate_limit_per_hour"]
                daily = rows[0]["rate_limit_per_day"]
                self.rate_limit_cache[app_id] = (hourly, daily, now)
                return (hourly, daily)
        except Exception as e:
            print(f"Failed to fetch rate limits: {e}")

        # Default limits if query fails
        return (1000, 10000)

    def _rate_limit_response(self, limit: int, remaining: int, retry_after: int, period: str):
        """Return 429 Too Many Requests response"""
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate Limit Exceeded",
                "detail": f"You have exceeded the {period} rate limit of {limit} requests",
                "retry_after": retry_after
            },
            headers={
                "Retry-After": str(retry_after),
                f"X-RateLimit-Limit-{period.title()}": str(limit),
                f"X-RateLimit-Remaining-{period.title()}": str(remaining)
            }
        )
