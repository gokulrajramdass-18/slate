"""
Users API Router

Endpoints for user management with RBAC support.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.models import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserPasswordChange,
    SuccessResponse,
)
from open_notebook.domain.user import User, UserRole
from open_notebook.constants import USER_STATUS_ACTIVE

router = APIRouter(prefix="/api/users", tags=["users"])

# Note: get_current_user and require_admin dependencies will be imported when ready
# For now, using placeholder comments


def get_current_user():
    """Placeholder - will be implemented by auth agent"""
    pass


def require_admin():
    """Placeholder - will be implemented by auth agent"""
    pass


# ============================================================================
# Helper Functions
# ============================================================================


async def enrich_user_with_roles(user_dict: dict) -> UserResponse:
    """Enrich user data with roles"""
    user = User(**user_dict)
    roles = await user.get_roles()

    return UserResponse(
        **user_dict,
        roles=[
            {
                "id": r.id,
                "name": r.name,
                "display_name": r.display_name,
            }
            for r in roles
        ],
    )


# ============================================================================
# Endpoints
# ============================================================================


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    # current_user: User = Depends(require_admin())  # Uncomment when ready
):
    """
    Create a new user (admin only)

    - Hashes password
    - Assigns default 'user' role
    - Returns user with roles
    """
    # Check if username already exists
    existing = await User.get_by_username(user_data.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{user_data.username}' already exists",
        )

    # Check if email already exists
    if user_data.email:
        existing_email = await User.get_by_email(user_data.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Email '{user_data.email}' already exists",
            )

    # Create user with hashed password
    user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=User.hash_password(user_data.password),
        full_name=user_data.full_name,
        avatar_url=user_data.avatar_url,
        status=user_data.status or USER_STATUS_ACTIVE,
        is_superadmin=user_data.is_superadmin,
    )

    user_id = await user.save()

    # Assign default 'user' role
    from open_notebook.domain.user import Role

    default_role = await Role.get_by_name("user")
    if default_role:
        await UserRole.assign_role(
            user_id=user_id,
            role_id=default_role.id,
            # assigned_by=current_user.id  # Uncomment when ready
        )

    # Fetch created user with roles
    created = await User.get(user_id)
    return await enrich_user_with_roles(created.model_dump())


@router.get("", response_model=List[UserResponse])
async def list_users(
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    # current_user: User = Depends(require_admin())  # Uncomment when ready
):
    """
    List all users with pagination (admin only)

    - Supports status filtering
    - Returns users with their roles
    """
    filters = {}
    if status_filter:
        filters["status"] = status_filter

    # Get all users (TODO: Add pagination at database level)
    users = await User.get_all(filters=filters, order_by="created DESC")

    # Apply pagination in memory (temporary solution)
    paginated_users = users[skip : skip + limit]

    # Enrich with roles
    enriched = []
    for user in paginated_users:
        enriched.append(await enrich_user_with_roles(user.model_dump()))

    return enriched


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    # current_user: User = Depends(get_current_user)  # Uncomment when ready
):
    """
    Get user details

    - Users can view their own profile
    - Admins can view any profile
    """
    user = await User.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # TODO: Check permission when auth is ready
    # if not current_user.is_superadmin and current_user.id != user_id:
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return await enrich_user_with_roles(user.model_dump())


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    update_data: UserUpdate,
    # current_user: User = Depends(get_current_user)  # Uncomment when ready
):
    """
    Update user

    - Users can update their own profile
    - Admins can update any profile
    - Status changes require admin
    """
    user = await User.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # TODO: Check permission when auth is ready
    # is_own_profile = current_user.id == user_id
    # if not current_user.is_superadmin and not is_own_profile:
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Only admin can change status
    # if update_data.status and not current_user.is_superadmin:
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can change user status")

    # Update fields
    if update_data.email is not None:
        # Check email uniqueness
        if update_data.email != user.email:
            existing = await User.get_by_email(update_data.email)
            if existing and existing.id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Email '{update_data.email}' already exists",
                )
        user.email = update_data.email

    if update_data.full_name is not None:
        user.full_name = update_data.full_name

    if update_data.avatar_url is not None:
        user.avatar_url = update_data.avatar_url

    if update_data.status is not None:
        user.status = update_data.status

    await user.save()

    return await enrich_user_with_roles(user.model_dump())


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    # current_user: User = Depends(require_admin())  # Uncomment when ready
):
    """
    Delete user (admin only)

    - Soft delete by setting status to 'deleted'
    """
    user = await User.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Soft delete
    user.status = "deleted"
    await user.save()


@router.post("/{user_id}/roles/{role_id}", response_model=SuccessResponse)
async def assign_role(
    user_id: str,
    role_id: str,
    # current_user: User = Depends(require_admin())  # Uncomment when ready
):
    """
    Assign role to user (admin only)
    """
    # Verify user exists
    user = await User.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Verify role exists
    from open_notebook.domain.user import Role

    role = await Role.get(role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
        )

    # Assign role
    await UserRole.assign_role(
        user_id=user_id,
        role_id=role_id,
        # assigned_by=current_user.id  # Uncomment when ready
    )

    return SuccessResponse(message=f"Role '{role.display_name}' assigned to user")


@router.delete("/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_role(
    user_id: str,
    role_id: str,
    # current_user: User = Depends(require_admin())  # Uncomment when ready
):
    """
    Remove role from user (admin only)

    - Prevents removing last role
    """
    # Verify user exists
    user = await User.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Check if user has multiple roles
    roles = await user.get_roles()
    if len(roles) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove last role from user",
        )

    # Remove role
    await UserRole.remove_role(user_id=user_id, role_id=role_id)


@router.put("/{user_id}/password", response_model=SuccessResponse)
async def change_password(
    user_id: str,
    password_data: UserPasswordChange,
    # current_user: User = Depends(get_current_user)  # Uncomment when ready
):
    """
    Change user password

    - Requires old password verification
    - Users can change their own password
    """
    user = await User.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # TODO: Check permission when auth is ready
    # if current_user.id != user_id:
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Can only change your own password")

    # Verify old password
    if not user.verify_password(password_data.old_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect"
        )

    # Update password
    user.password_hash = User.hash_password(password_data.new_password)
    await user.save()

    return SuccessResponse(message="Password changed successfully")
