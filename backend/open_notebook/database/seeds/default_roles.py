"""
Seed default roles and admin user for RBAC system.

Creates 4 system roles with full permission sets and a default admin user.
"""

import asyncio
from datetime import datetime

from open_notebook.constants import *
from open_notebook.domain.user import User, Role, RolePermission, UserRole


async def seed_default_roles():
    """
    Create 4 default system roles with full permission sets.

    Roles:
    1. admin - Full access to everything (scope=all)
    2. power_user - Read/execute all, manage own
    3. user - Manage own resources only
    4. viewer - Read-only access

    Returns:
        dict: Created role IDs by name
    """
    print("Seeding default roles...")

    role_ids = {}

    # Define roles
    roles_to_create = [
        {
            "name": "admin",
            "display_name": "Administrator",
            "description": "Full system access with all permissions",
            "is_system_role": True,
        },
        {
            "name": "power_user",
            "display_name": "Power User",
            "description": "Can read/execute all resources and manage own resources",
            "is_system_role": True,
        },
        {
            "name": "user",
            "display_name": "Standard User",
            "description": "Can manage own resources only",
            "is_system_role": True,
        },
        {
            "name": "viewer",
            "display_name": "Viewer",
            "description": "Read-only access to resources",
            "is_system_role": True,
        },
    ]

    # Create roles
    for role_data in roles_to_create:
        existing = await Role.get_by_name(role_data["name"])
        if existing:
            print(f"  ✓ Role '{role_data['name']}' already exists")
            role_ids[role_data["name"]] = existing.id
            continue

        role = Role(**role_data)
        role_id = await role.save()
        role_ids[role_data["name"]] = role_id
        print(f"  ✓ Created role: {role_data['display_name']}")

    # Define resource types
    resource_types = [
        RESOURCE_WORKSPACE,
        RESOURCE_SOURCE,
        RESOURCE_CHAT_SESSION,
        RESOURCE_AGENT,
        RESOURCE_AGENT_TEAM,
        RESOURCE_TOOL,
        RESOURCE_MCP_SERVER,
        RESOURCE_HANA_CONNECTION,
        RESOURCE_API_CONNECTION,
        RESOURCE_MICROSITE,
        RESOURCE_WORKFLOW,
        RESOURCE_BOOKMARK,
        RESOURCE_QUERY_PROMPT,
    ]

    # Admin permissions: ALL scope for everything
    print("\n  Creating admin permissions...")
    admin_actions = [
        ACTION_CREATE,
        ACTION_READ,
        ACTION_UPDATE,
        ACTION_DELETE,
        ACTION_EXECUTE,
        ACTION_SHARE,
    ]

    for resource_type in resource_types:
        for action in admin_actions:
            # Check if permission exists
            existing_perms = await RolePermission.get_for_role(role_ids["admin"])
            exists = any(
                p.resource_type == resource_type and p.action == action
                for p in existing_perms
            )
            if not exists:
                perm = RolePermission(
                    role_id=role_ids["admin"],
                    resource_type=resource_type,
                    action=action,
                    scope=SCOPE_ALL,
                )
                await perm.save()

    # Add admin permissions for user and role management
    for resource_type in [RESOURCE_USER, RESOURCE_ROLE]:
        for action in [
            ACTION_CREATE,
            ACTION_READ,
            ACTION_UPDATE,
            ACTION_DELETE,
        ]:
            existing_perms = await RolePermission.get_for_role(role_ids["admin"])
            exists = any(
                p.resource_type == resource_type and p.action == action
                for p in existing_perms
            )
            if not exists:
                perm = RolePermission(
                    role_id=role_ids["admin"],
                    resource_type=resource_type,
                    action=action,
                    scope=SCOPE_ALL,
                )
                await perm.save()

    print("  ✓ Admin permissions created")

    # Power User permissions: Read/Execute ALL, others OWN
    print("\n  Creating power_user permissions...")
    for resource_type in resource_types:
        # Read and Execute: ALL scope
        for action in [ACTION_READ, ACTION_EXECUTE]:
            existing_perms = await RolePermission.get_for_role(role_ids["power_user"])
            exists = any(
                p.resource_type == resource_type and p.action == action
                for p in existing_perms
            )
            if not exists:
                perm = RolePermission(
                    role_id=role_ids["power_user"],
                    resource_type=resource_type,
                    action=action,
                    scope=SCOPE_ALL,
                )
                await perm.save()

        # Create, Update, Delete, Share: OWN scope
        for action in [ACTION_CREATE, ACTION_UPDATE, ACTION_DELETE, ACTION_SHARE]:
            existing_perms = await RolePermission.get_for_role(role_ids["power_user"])
            exists = any(
                p.resource_type == resource_type and p.action == action
                for p in existing_perms
            )
            if not exists:
                perm = RolePermission(
                    role_id=role_ids["power_user"],
                    resource_type=resource_type,
                    action=action,
                    scope=SCOPE_OWN,
                )
                await perm.save()

    print("  ✓ Power user permissions created")

    # Standard User permissions: All actions with OWN scope
    print("\n  Creating user permissions...")
    for resource_type in resource_types:
        for action in [
            ACTION_CREATE,
            ACTION_READ,
            ACTION_UPDATE,
            ACTION_DELETE,
            ACTION_EXECUTE,
            ACTION_SHARE,
        ]:
            existing_perms = await RolePermission.get_for_role(role_ids["user"])
            exists = any(
                p.resource_type == resource_type and p.action == action
                for p in existing_perms
            )
            if not exists:
                perm = RolePermission(
                    role_id=role_ids["user"],
                    resource_type=resource_type,
                    action=action,
                    scope=SCOPE_OWN,
                )
                await perm.save()

    print("  ✓ User permissions created")

    # Viewer permissions: Read-only with OWN scope
    print("\n  Creating viewer permissions...")
    for resource_type in resource_types:
        existing_perms = await RolePermission.get_for_role(role_ids["viewer"])
        exists = any(
            p.resource_type == resource_type and p.action == ACTION_READ
            for p in existing_perms
        )
        if not exists:
            perm = RolePermission(
                role_id=role_ids["viewer"],
                resource_type=resource_type,
                action=ACTION_READ,
                scope=SCOPE_OWN,
            )
            await perm.save()

    print("  ✓ Viewer permissions created")

    print("\n✅ Default roles seeded successfully!")
    return role_ids


async def seed_default_admin_user():
    """
    Create default admin user for initial setup.

    Credentials:
    - Username: admin
    - Password: admin (should be changed after first login!)
    - Status: active
    - is_superadmin: True

    Returns:
        str: Admin user ID
    """
    print("\nSeeding default admin user...")

    # Check if admin user exists
    existing = await User.get_by_username("admin")
    if existing:
        print("  ✓ Admin user already exists")
        return existing.id

    # Create admin user
    admin_user = User(
        username="admin",
        email="admin@localhost",
        password_hash=User.hash_password("admin"),
        full_name="System Administrator",
        status=USER_STATUS_ACTIVE,
        is_superadmin=True,
    )

    user_id = await admin_user.save()
    print("  ✓ Created admin user (username: admin, password: admin)")

    # Assign admin role
    admin_role = await Role.get_by_name("admin")
    if admin_role:
        await UserRole.assign_role(
            user_id=user_id, role_id=admin_role.id, assigned_by=user_id
        )
        print("  ✓ Assigned admin role")

    print("\n✅ Default admin user seeded successfully!")
    print("\n⚠️  IMPORTANT: Change the default password immediately!")
    return user_id


async def seed_all():
    """Seed both default roles and admin user"""
    print("="*60)
    print("SEEDING RBAC SYSTEM")
    print("="*60)

    role_ids = await seed_default_roles()
    admin_id = await seed_default_admin_user()

    print("\n" + "="*60)
    print("SEEDING COMPLETE")
    print("="*60)
    print(f"\nRoles created: {len(role_ids)}")
    print(f"Admin user ID: {admin_id}")
    print("\nDefault credentials:")
    print("  Username: admin")
    print("  Password: admin")
    print("\n⚠️  Change the admin password immediately in production!")
    print("="*60)


if __name__ == "__main__":
    # Run seeding
    asyncio.run(seed_all())
