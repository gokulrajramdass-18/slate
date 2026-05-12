"""
XSUAA Authentication Handler

Handles XSUAA JWT tokens from AppRouter and auto-creates users.
"""

import os
from typing import Optional
from jose import jwt, JWTError
from fastapi import HTTPException, status

from open_notebook.constants import USER_STATUS_ACTIVE
from open_notebook.domain.user import User, Role, UserRole


XSUAA_ENABLED = os.getenv("XSUAA_ENABLED", "false").lower() == "true"


async def get_or_create_user_from_xsuaa(token: str) -> User:
    """
    Extract user info from XSUAA JWT token and get or create user.

    XSUAA tokens contain:
    - user_name: email/username
    - email: user email
    - user_id: SAP user ID (P-number)
    - scope: list of scopes including slate.User, slate.Admin

    Args:
        token: XSUAA JWT token

    Returns:
        User object (existing or newly created)
    """
    try:
        # Decode without verification first to inspect claims
        # AppRouter already verified the token with XSUAA
        payload = jwt.get_unverified_claims(token)

        # Extract XSUAA user info
        xsuaa_user_id = payload.get("user_id") or payload.get("sub")
        username = payload.get("user_name") or payload.get("email")
        email = payload.get("email") or username
        scopes = payload.get("scope", [])

        if not username:
            raise ValueError("No username in XSUAA token")

        # Check if user already exists (by email)
        user = await User.get_by_email(email) if email else None

        if not user:
            # User doesn't exist - create new user
            print(f"Creating new user from XSUAA token: {username} ({email})")

            # Determine if user should be admin based on scopes
            is_admin = any("Admin" in scope for scope in scopes)

            # Make specific users superadmin by email
            is_superadmin = email in ["gokulraj.ramdass@sap.com"]

            # Create user
            user = User(
                username=username.split("@")[0],  # Use email prefix as username
                email=email,
                password_hash="",  # No password for XSUAA users
                full_name=username,
                status=USER_STATUS_ACTIVE,
                is_superadmin=is_superadmin,
            )

            user_id = await user.save()

            # Assign role based on XSUAA scopes
            if is_admin:
                admin_role = await Role.get_by_name("admin")
                if admin_role:
                    await UserRole.assign_role(
                        user_id=user_id,
                        role_id=admin_role.id,
                        assigned_by=user_id
                    )
                    print(f"Assigned admin role to user {username}")
            else:
                user_role = await Role.get_by_name("user")
                if user_role:
                    await UserRole.assign_role(
                        user_id=user_id,
                        role_id=user_role.id,
                        assigned_by=user_id
                    )
                    print(f"Assigned user role to user {username}")

            # Reload user to get roles
            user = await User.get(user_id)
            print(f"Created new user: {user.username} (ID: {user.id})")

        return user

    except Exception as e:
        print(f"Error extracting user from XSUAA token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid XSUAA token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_from_xsuaa_token(token: str) -> User:
    """
    Get or create user from XSUAA JWT token.

    This is called when XSUAA_ENABLED=true and we receive a token
    from AppRouter that has already been verified by XSUAA.

    Args:
        token: XSUAA JWT token (already verified by AppRouter/XSUAA)

    Returns:
        User object
    """
    return await get_or_create_user_from_xsuaa(token)
