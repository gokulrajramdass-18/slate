"""
Roles API Router

Endpoints for role and permission management with RBAC support.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from api.models import (
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    RolePermissionCreate,
    RolePermissionUpdate,
    RolePermissionResponse,
    SuccessResponse,
)
from open_notebook.domain.user import Role, RolePermission
from open_notebook.constants import (
    RESOURCE_WORKSPACE,
    ACTION_CREATE,
    SCOPE_OWN,
)

router = APIRouter(prefix="/api/roles", tags=["roles"])


# Placeholder dependencies (will be replaced when auth agent completes)
def get_current_user():
    pass


def require_admin():
    pass


# ============================================================================
# Helper Functions
# ============================================================================


async def enrich_role_with_permissions(role_dict: dict) -> RoleResponse:
    """Enrich role data with permissions"""
    role = Role(**role_dict)
    permissions = await role.get_permissions()

    return RoleResponse(
        **role_dict,
        permissions=[
            RolePermissionResponse(
                id=p.id,
                role_id=p.role_id,
                resource_type=p.resource_type,
                action=p.action,
                scope=p.scope,
                conditions=p.conditions,
                created=p.created,
                updated=p.updated,
            )
            for p in permissions
        ],
    )


# ============================================================================
# Role Endpoints
# ============================================================================


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    # current_user: User = Depends(require_admin())  # Uncomment when ready
):
    """
    Create a new role (admin only)

    - Prevents duplicate names
    - Creates as non-system role
    """
    # Check for duplicate name
    existing = await Role.get_by_name(role_data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Role '{role_data.name}' already exists",
        )

    # Create role
    role = Role(
        name=role_data.name,
        display_name=role_data.display_name,
        description=role_data.description,
        is_system_role=False,
        # created_by=current_user.id  # Uncomment when ready
    )

    role_id = await role.save()

    # Fetch created role
    created = await Role.get(role_id)
    return await enrich_role_with_permissions(created.model_dump())


@router.get("", response_model=List[RoleResponse])
async def list_roles(
    # current_user: User = Depends(get_current_user)  # Uncomment when ready
):
    """
    List all roles (authenticated users)

    - Returns all roles for selection
    """
    roles = await Role.get_all(order_by="name ASC")

    enriched = []
    for role in roles:
        enriched.append(await enrich_role_with_permissions(role.model_dump()))

    return enriched


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: str,
    # current_user: User = Depends(get_current_user)  # Uncomment when ready
):
    """
    Get role with permissions
    """
    role = await Role.get(role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
        )

    return await enrich_role_with_permissions(role.model_dump())


@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: str,
    update_data: RoleUpdate,
    # current_user: User = Depends(require_admin())  # Uncomment when ready
):
    """
    Update role (admin only)

    - Cannot update system roles
    """
    role = await Role.get(role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
        )

    # Prevent updating system roles
    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify system roles",
        )

    # Update fields
    if update_data.display_name is not None:
        role.display_name = update_data.display_name

    if update_data.description is not None:
        role.description = update_data.description

    await role.save()

    return await enrich_role_with_permissions(role.model_dump())


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: str,
    # current_user: User = Depends(require_admin())  # Uncomment when ready
):
    """
    Delete role (admin only)

    - Cannot delete system roles
    - Warns if users have this role
    """
    role = await Role.get(role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
        )

    # Prevent deleting system roles
    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete system roles",
        )

    # Check if users have this role
    users = await role.get_users()
    if users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete role: {len(users)} user(s) have this role",
        )

    await role.delete()


# ============================================================================
# Permission Endpoints
# ============================================================================


@router.get("/{role_id}/permissions", response_model=List[RolePermissionResponse])
async def get_role_permissions(
    role_id: str,
    # current_user: User = Depends(get_current_user)  # Uncomment when ready
):
    """
    Get all permissions for a role
    """
    role = await Role.get(role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
        )

    permissions = await role.get_permissions()

    return [
        RolePermissionResponse(
            id=p.id,
            role_id=p.role_id,
            resource_type=p.resource_type,
            action=p.action,
            scope=p.scope,
            conditions=p.conditions,
            created=p.created,
            updated=p.updated,
        )
        for p in permissions
    ]


@router.post(
    "/{role_id}/permissions",
    response_model=RolePermissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_permission(
    role_id: str,
    permission_data: RolePermissionCreate,
    # current_user: User = Depends(require_admin())  # Uncomment when ready
):
    """
    Add permission to role (admin only)

    - Validates resource_type, action, scope
    """
    role = await Role.get(role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
        )

    # Check for duplicate permission
    existing_perms = await role.get_permissions()
    for perm in existing_perms:
        if (
            perm.resource_type == permission_data.resource_type
            and perm.action == permission_data.action
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Permission already exists: {permission_data.resource_type}.{permission_data.action}",
            )

    # Create permission
    permission = RolePermission(
        role_id=role_id,
        resource_type=permission_data.resource_type,
        action=permission_data.action,
        scope=permission_data.scope or SCOPE_OWN,
        conditions=permission_data.conditions,
    )

    perm_id = await permission.save()

    # Fetch created permission
    created = await RolePermission.get(perm_id)
    return RolePermissionResponse(
        id=created.id,
        role_id=created.role_id,
        resource_type=created.resource_type,
        action=created.action,
        scope=created.scope,
        conditions=created.conditions,
        created=created.created,
        updated=created.updated,
    )


@router.put("/{role_id}/permissions/{permission_id}", response_model=RolePermissionResponse)
async def update_permission(
    role_id: str,
    permission_id: str,
    update_data: RolePermissionUpdate,
    # current_user: User = Depends(require_admin())  # Uncomment when ready
):
    """
    Update permission (admin only)

    - Updates scope or conditions
    """
    permission = await RolePermission.get(permission_id)
    if not permission or permission.role_id != role_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found"
        )

    # Update fields
    if update_data.scope is not None:
        permission.scope = update_data.scope

    if update_data.conditions is not None:
        permission.conditions = update_data.conditions

    await permission.save()

    return RolePermissionResponse(
        id=permission.id,
        role_id=permission.role_id,
        resource_type=permission.resource_type,
        action=permission.action,
        scope=permission.scope,
        conditions=permission.conditions,
        created=permission.created,
        updated=permission.updated,
    )


@router.delete("/{role_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_permission(
    role_id: str,
    permission_id: str,
    # current_user: User = Depends(require_admin())  # Uncomment when ready
):
    """
    Remove permission from role (admin only)
    """
    permission = await RolePermission.get(permission_id)
    if not permission or permission.role_id != role_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found"
        )

    await permission.delete()
