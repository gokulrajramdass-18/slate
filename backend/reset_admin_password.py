#!/usr/bin/env python3
"""
Reset admin user password to 'admin'
"""
import asyncio
import sys
from passlib.context import CryptContext

# Add parent directory to path
sys.path.insert(0, '.')

from open_notebook.domain.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def reset_password():
    """Reset admin password to 'admin'"""
    try:
        # Get admin user
        user = await User.get_by_username("admin")

        if not user:
            print("❌ Admin user not found!")
            return False

        # Hash new password
        new_password = "admin"
        password_hash = pwd_context.hash(new_password)

        # Update password
        user.password_hash = password_hash
        await user.save()

        print(f"✅ Admin password reset successfully!")
        print(f"   Username: admin")
        print(f"   Password: admin")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(reset_password())
    sys.exit(0 if success else 1)
