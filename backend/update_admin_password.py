#!/usr/bin/env python3
"""Update admin user password hash"""

import asyncio
import aiosqlite

async def update_admin_password():
    """Update admin user password hash to bcrypt 4.x compatible version"""

    sql = """
    UPDATE users
    SET password_hash = '$2b$12$r8mzS/i6VItrR1sKOdKS5OcELualeCLOxbDg4X88g7CGL16eNJ2dy',
        updated = datetime('now')
    WHERE username = 'admin';
    """

    verify_sql = "SELECT username, password_hash FROM users WHERE username = 'admin'"

    async with aiosqlite.connect('/app/data/database.db') as db:
        # Update password
        await db.execute(sql)
        await db.commit()
        print("✓ Admin password hash updated")

        # Verify
        async with db.execute(verify_sql) as cursor:
            row = await cursor.fetchone()
            if row:
                print(f"\n✅ Password updated successfully!")
                print(f"   Username: {row[0]}")
                print(f"   New hash: {row[1][:50]}...")
            else:
                print("❌ Admin user not found")

if __name__ == '__main__':
    asyncio.run(update_admin_password())
