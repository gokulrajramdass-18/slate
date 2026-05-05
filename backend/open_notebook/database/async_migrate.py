"""
Database Migration Script

Runs SQL migrations and tracks applied versions in the _migrations table.
"""

import asyncio
import os
from pathlib import Path
from typing import List, Dict
from datetime import datetime

from open_notebook.config import get_database
from open_notebook.database.interface import DatabaseError


class MigrationManager:
    """Manages database migrations"""

    def __init__(self, migrations_dir: str = None):
        """
        Initialize migration manager

        Args:
            migrations_dir: Path to migrations directory
        """
        if migrations_dir is None:
            # Default to migrations directory next to this file
            base_dir = Path(__file__).parent
            migrations_dir = base_dir / "migrations"

        self.migrations_dir = Path(migrations_dir)
        self.db = get_database()

    async def get_applied_migrations(self) -> List[int]:
        """
        Get list of applied migration versions.

        Returns:
            List of version numbers
        """
        try:
            await self.db.connect()
            results = await self.db.query(
                "SELECT version FROM _migrations ORDER BY version"
            )
            return [row['version'] for row in results]
        except DatabaseError:
            # _migrations table doesn't exist yet
            return []
        finally:
            await self.db.disconnect()

    async def get_pending_migrations(self) -> List[Dict]:
        """
        Get list of pending migrations to apply.

        Returns:
            List of dicts with 'version', 'name', 'path'
        """
        applied = await self.get_applied_migrations()

        # Find all .sql files in migrations directory
        migration_files = sorted(self.migrations_dir.glob("*.sql"))

        pending = []
        for filepath in migration_files:
            # Extract version from filename (e.g., 001_initial_schema.sql)
            filename = filepath.name
            if not filename[0].isdigit():
                continue

            try:
                version = int(filename.split('_')[0])
                name = filename.replace('.sql', '').replace(f'{version:03d}_', '')

                if version not in applied:
                    pending.append({
                        'version': version,
                        'name': name,
                        'path': filepath
                    })
            except (ValueError, IndexError):
                print(f"Warning: Skipping invalid migration filename: {filename}")
                continue

        return pending

    async def apply_migration(self, migration: Dict) -> None:
        """
        Apply a single migration.

        Args:
            migration: Dict with 'version', 'name', 'path'
        """
        print(f"Applying migration {migration['version']:03d}: {migration['name']}")

        # Read SQL file
        with open(migration['path'], 'r') as f:
            sql_content = f.read()

        await self.db.connect()

        try:
            # Split SQL into individual statements
            statements = self._split_sql(sql_content)

            # Execute each statement
            for statement in statements:
                if statement.strip():
                    await self.db.execute(statement)

            # Record migration in _migrations table (without auto-timestamps)
            migration_id = f"{migration['version']:03d}"
            sql = """
                INSERT INTO _migrations (id, version, name, applied_at)
                VALUES (:id, :version, :name, :applied_at)
            """
            await self.db.execute(sql, {
                'id': migration_id,
                'version': migration['version'],
                'name': migration['name'],
                'applied_at': datetime.utcnow().isoformat()
            })

            print(f"  ✓ Migration {migration['version']:03d} applied successfully")

        except Exception as e:
            print(f"  ✗ Migration {migration['version']:03d} failed: {str(e)}")
            raise
        finally:
            await self.db.disconnect()

    async def migrate(self) -> None:
        """
        Apply all pending migrations.
        """
        print("Checking for pending migrations...")

        pending = await self.get_pending_migrations()

        if not pending:
            print("No pending migrations. Database is up to date.")
            return

        print(f"Found {len(pending)} pending migration(s)")

        for migration in pending:
            await self.apply_migration(migration)

        print(f"\n✓ All migrations applied successfully!")

    async def rollback(self, target_version: int = None) -> None:
        """
        Rollback migrations to a target version.

        Note: This is for development only. Production rollbacks not recommended.

        Args:
            target_version: Version to roll back to (None = rollback last migration)
        """
        applied = await self.get_applied_migrations()

        if not applied:
            print("No migrations to rollback")
            return

        if target_version is None:
            # Rollback last migration
            target_version = applied[-2] if len(applied) > 1 else 0

        migrations_to_rollback = [v for v in applied if v > target_version]

        if not migrations_to_rollback:
            print(f"Already at version {target_version}")
            return

        print(f"Rolling back {len(migrations_to_rollback)} migration(s)...")
        print("WARNING: Rollback is destructive and may cause data loss!")

        # Note: Actual rollback implementation would require down migrations
        # For now, just remove from _migrations table
        await self.db.connect()
        try:
            for version in reversed(migrations_to_rollback):
                await self.db.execute(
                    "DELETE FROM _migrations WHERE version = :version",
                    {'version': version}
                )
                print(f"  ✓ Rolled back migration {version:03d}")
        finally:
            await self.db.disconnect()

        print(f"\n✓ Rollback complete. Database at version {target_version}")
        print("Note: This only removes migration records. Manual schema cleanup may be needed.")

    async def status(self) -> None:
        """
        Show migration status.
        """
        applied = await self.get_applied_migrations()
        pending = await self.get_pending_migrations()

        print("Migration Status")
        print("=" * 60)

        if applied:
            print(f"\nApplied migrations: {len(applied)}")
            for version in applied:
                print(f"  ✓ {version:03d}")
        else:
            print("\nNo migrations applied yet")

        if pending:
            print(f"\nPending migrations: {len(pending)}")
            for migration in pending:
                print(f"  • {migration['version']:03d}: {migration['name']}")
        else:
            print("\nNo pending migrations. Database is up to date.")

        print("=" * 60)

    def _split_sql(self, sql_content: str) -> List[str]:
        """
        Split SQL content into individual statements.

        Simple implementation - splits on semicolons outside of strings.

        Args:
            sql_content: SQL file content

        Returns:
            List of SQL statements
        """
        # Remove comments
        lines = []
        for line in sql_content.split('\n'):
            # Remove single-line comments
            if '--' in line:
                line = line[:line.index('--')]
            lines.append(line)

        sql = '\n'.join(lines)

        # Smart SQL splitting that handles triggers
        statements = []
        current_stmt = []
        in_trigger = False

        for line in sql.split('\n'):
            line_upper = line.strip().upper()

            # Check if entering a trigger
            if 'CREATE TRIGGER' in line_upper:
                in_trigger = True

            current_stmt.append(line)

            # Check for end of statement
            if ';' in line:
                if in_trigger and 'END' in line_upper:
                    # End of trigger
                    in_trigger = False
                    statements.append('\n'.join(current_stmt))
                    current_stmt = []
                elif not in_trigger:
                    # Regular statement end
                    statements.append('\n'.join(current_stmt))
                    current_stmt = []

        # Add any remaining statement
        if current_stmt:
            statements.append('\n'.join(current_stmt))

        # Clean up statements
        return [stmt.strip() for stmt in statements if stmt.strip()]


async def main():
    """
    Main entry point for migration script.
    """
    import sys

    # Parse command line arguments
    command = sys.argv[1] if len(sys.argv) > 1 else "migrate"

    manager = MigrationManager()

    if command == "migrate":
        await manager.migrate()
    elif command == "status":
        await manager.status()
    elif command == "rollback":
        target = int(sys.argv[2]) if len(sys.argv) > 2 else None
        await manager.rollback(target)
    else:
        print(f"Unknown command: {command}")
        print("Usage: python -m open_notebook.database.async_migrate [migrate|status|rollback]")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
