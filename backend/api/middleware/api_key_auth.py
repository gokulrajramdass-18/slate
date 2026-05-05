"""
API Key Authentication Middleware

FastAPI dependency for validating API keys on external endpoints.
"""

from typing import Optional
from fastapi import Header, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from open_notebook.domain.api_key import APIKey


# Security scheme for Swagger UI
api_key_scheme = HTTPBearer(
    scheme_name="API Key",
    description="Enter your API key in the format: Bearer sk_..."
)


async def verify_api_key(
    authorization: Optional[str] = Header(None),
    request: Request = None
) -> APIKey:
    """
    Verify API key from Authorization header

    Usage:
        @router.post("/endpoint")
        async def my_endpoint(api_key: APIKey = Depends(verify_api_key)):
            # api_key is now validated and available
            pass

    Args:
        authorization: Authorization header value (Bearer token)
        request: FastAPI request object

    Returns:
        APIKey: Validated API key object

    Raises:
        HTTPException: If API key is invalid or missing
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Include 'Authorization: Bearer <your-api-key>' header.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Extract token from "Bearer <token>" format
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Use 'Authorization: Bearer <your-api-key>'",
            headers={"WWW-Authenticate": "Bearer"}
        )

    api_key_string = parts[1]

    # Verify the key
    api_key = await APIKey.verify_key(api_key_string)

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return api_key


def verify_api_key_with_scope(required_scope: str):
    """
    Create a dependency that verifies API key and checks for specific scope

    Usage:
        verify_notifications = verify_api_key_with_scope("notifications:write")

        @router.post("/endpoint")
        async def my_endpoint(api_key: APIKey = Depends(verify_notifications)):
            pass

    Args:
        required_scope: The scope required for this endpoint

    Returns:
        Dependency function
    """
    async def verify(
        authorization: Optional[str] = Header(None),
        request: Request = None
    ) -> APIKey:
        api_key = await verify_api_key(authorization, request)

        if not api_key.has_scope(required_scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key does not have required scope: {required_scope}"
            )

        return api_key

    return verify


# Common scope validators
verify_notifications_write = verify_api_key_with_scope("notifications:write")
verify_workflows_execute = verify_api_key_with_scope("workflows:execute")
verify_agents_execute = verify_api_key_with_scope("agents:execute")
