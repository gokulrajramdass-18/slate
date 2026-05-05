"""
Resource Shares API Router

Endpoints for sharing resources with users and roles.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from api.models import ResourceShareCreate, ResourceShareResponse, SuccessResponse
from open_notebook.domain.resource_share import ResourceShare
from open_notebook.domain.user import User

router = APIRouter(prefix="/api/resource-shares", tags=["resource_shares"])


# Placeholder dependencies
def get_current_user():
    pass


# ============================================================================
# Endpoints
# ============================================================================


@router.post("", response_model=ResourceShareResponse, status_code=status.HTTP_201_CREATED)
async def create_share(
    share_data: ResourceShareCreate,
    # current_user: User = Depends(get_current_user)  # Uncomment when ready
):
    """
    Share a resource with a user or role

    - Verifies ownership or admin access
    - Creates or updates existing share
    """
    # TODO: Verify ownership when auth is ready
    # Load resource and verify current_user owns it or is admin

    # Validate share target
    if not share_data.shared_with_user and not share_data.shared_with_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must specify either shared_with_user or shared_with_role",
        )

    # Create share
    share_id = await ResourceShare.share_resource(
        resource_type=share_data.resource_type,
        resource_id=share_data.resource_id,
        # shared_by=current_user.id,  # Uncomment when ready
        shared_by="default_user",  # Temporary
        shared_with_user=share_data.shared_with_user,
        shared_with_role=share_data.shared_with_role,
        permission_level=share_data.permission_level,
        expires_at=share_data.expires_at,
    )

    # Fetch created share
    share = await ResourceShare.get(share_id)
    return ResourceShareResponse(**share.model_dump())


@router.get(
    "/resource/{resource_type}/{resource_id}", response_model=List[ResourceShareResponse]
)
async def list_shares_for_resource(
    resource_type: str,
    resource_id: str,
    # current_user: User = Depends(get_current_user)  # Uncomment when ready
):
    """
    List all shares for a resource (owner or admin only)
    """
    # TODO: Verify ownership when auth is ready

    shares = await ResourceShare.get_for_resource(resource_type, resource_id)

    return [ResourceShareResponse(**s.model_dump()) for s in shares]


@router.get("/my-shares", response_model=List[ResourceShareResponse])
async def list_my_shares(
    # current_user: User = Depends(get_current_user)  # Uncomment when ready
):
    """
    List all resources shared with current user
    """
    # shares = await ResourceShare.get_for_user(current_user.id)  # Uncomment when ready
    shares = await ResourceShare.get_for_user("default_user")  # Temporary

    return [ResourceShareResponse(**s.model_dump()) for s in shares]


@router.get("/shared-by-me", response_model=List[ResourceShareResponse])
async def list_shared_by_me(
    # current_user: User = Depends(get_current_user)  # Uncomment when ready
):
    """
    List all resources shared by current user
    """
    # shares = await ResourceShare.get_shared_by_user(current_user.id)  # Uncomment when ready
    shares = await ResourceShare.get_shared_by_user("default_user")  # Temporary

    return [ResourceShareResponse(**s.model_dump()) for s in shares]


@router.delete("/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_share(
    share_id: str,
    # current_user: User = Depends(get_current_user)  # Uncomment when ready
):
    """
    Delete a share (owner or admin only)
    """
    share = await ResourceShare.get(share_id)
    if not share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Share not found"
        )

    # TODO: Verify ownership when auth is ready
    # if share.shared_by != current_user.id and not current_user.is_superadmin:
    #     raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    await ResourceShare.revoke_share(share_id)
