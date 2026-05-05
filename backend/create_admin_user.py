#!/usr/bin/env python3
"""Create default admin user in database"""

import asyncio
import aiosqlite

async def create_admin_user():
    """Create admin user with username: admin, password: admin"""

    sql = """
    -- Create default admin user
    INSERT OR IGNORE INTO users (
        id,
        username,
        email,
        password_hash,
        full_name,
        status,
        is_superadmin,
        created,
        updated,
        last_login
    ) VALUES (
        '00000000-0000-0000-0000-000000000001',
        'admin',
        'admin@localhost',
        '$2b$12$492IqJ92IoDzTeXRuP3dHOg/VAZlvkszODp3QhZ0l3bMqDrTOiLFO',
        'System Administrator',
        'active',
        1,
        datetime('now'),
        datetime('now'),
        NULL
    );
    """

    role_sql = """
    -- Assign admin role to admin user
    INSERT OR IGNORE INTO user_roles (
        id,
        user_id,
        role_id,
        assigned_by,
        assigned_at
    )
    SELECT
        '00000000-0000-0000-0000-000000000002',
        '00000000-0000-0000-0000-000000000001',
        r.id,
        '00000000-0000-0000-0000-000000000001',
        datetime('now')
    FROM roles r
    WHERE r.name = 'admin';
    """

    verify_sql = "SELECT id, username, email, full_name, is_superadmin FROM users WHERE username = 'admin'"

    async with aiosqlite.connect('/app/data/database.db') as db:
        # Create user
        await db.execute(sql)
        await db.commit()
        print("✓ Admin user created")

        # Assign admin role
        await db.execute(role_sql)
        await db.commit()
        print("✓ Admin role assigned")

        # Verify
        async with db.execute(verify_sql) as cursor:
            row = await cursor.fetchone()
            if row:
                print(f"\n✅ Admin user created successfully!")
                print(f"   ID: {row[0]}")
                print(f"   Username: {row[1]}")
                print(f"   Email: {row[2]}")
                print(f"   Full Name: {row[3]}")
                print(f"   Is Superadmin: {row[4]}")
                print(f"\n   Login with:")
                print(f"   Username: admin")
                print(f"   Password: admin")
            else:
                print("❌ Failed to create admin user")

if __name__ == '__main__':
    asyncio.run(create_admin_user())
