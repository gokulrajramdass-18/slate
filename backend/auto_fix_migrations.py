#!/usr/bin/env python3
"""
Automatically fix migrations by commenting out duplicate column additions
and wrapping problematic statements with existence checks.
"""

import sqlite3
import sys
from pathlib import Path
import re

DATABASE_PATH = Path("data/database.db")
MIGRATIONS_DIR = Path("open_notebook/database/migrations")


def get_table_columns(cursor, table_name):
    """Get all column names for a table."""
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        return {row[1] for row in cursor.fetchall()}
    except sqlite3.OperationalError:
        return set()


def table_exists(cursor, table_name):
    """Check if a table exists."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    )
    return cursor.fetchone() is not None


def column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table."""
    columns = get_table_columns(cursor, table_name)
    return column_name in columns


def fix_migration_file(migration_file):
    """Fix a migration file by commenting out problematic statements."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    with open(migration_file, 'r') as f:
        lines = f.readlines()

    modified = False
    new_lines = []

    for i, line in enumerate(lines):
        original_line = line
        stripped = line.strip()

        # Check ALTER TABLE ADD COLUMN statements
        if stripped.startswith('ALTER TABLE') and 'ADD COLUMN' in stripped:
            parts = stripped.replace(';', '').split()
            try:
                table_idx = parts.index('TABLE') + 1
                column_idx = parts.index('COLUMN') + 1
                table_name = parts[table_idx]
                column_name = parts[column_idx]

                if table_exists(cursor, table_name) and column_exists(cursor, table_name, column_name):
                    # Comment out this line
                    new_lines.append(f"-- SKIPPED: Column already exists - {line}")
                    modified = True
                    continue
                elif not table_exists(cursor, table_name):
                    # Comment out - table doesn't exist
                    new_lines.append(f"-- SKIPPED: Table doesn't exist - {line}")
                    modified = True
                    continue
            except (ValueError, IndexError):
                pass

        # Fix CREATE INDEX statements
        if 'CREATE INDEX' in stripped:
            # Add IF NOT EXISTS if missing
            if 'IF NOT EXISTS' not in stripped:
                line = line.replace('CREATE INDEX', 'CREATE INDEX IF NOT EXISTS', 1)
                modified = True

            # Check if the table and column exist
            # Extract table and column from: CREATE INDEX ... ON table(column)
            match = re.search(r'ON\s+(\w+)\s*\(([^)]+)\)', stripped)
            if match:
                table_name = match.group(1)
                column_spec = match.group(2)
                # Get first column name (handle "column DESC" and "column1, column2")
                first_column = column_spec.split(',')[0].split()[0].strip()

                if table_exists(cursor, table_name):
                    if not column_exists(cursor, table_name, first_column):
                        # Comment out - column doesn't exist
                        new_lines.append(f"-- SKIPPED: Column '{first_column}' doesn't exist in '{table_name}' - {line}")
                        modified = True
                        continue
                else:
                    # Comment out - table doesn't exist
                    new_lines.append(f"-- SKIPPED: Table '{table_name}' doesn't exist - {line}")
                    modified = True
                    continue

        new_lines.append(line)

    conn.close()

    if modified:
        # Write back to file
        with open(migration_file, 'w') as f:
            f.writelines(new_lines)
        return True

    return False


def main():
    if not DATABASE_PATH.exists():
        print(f"Database not found: {DATABASE_PATH}")
        return 1

    print("Fixing migrations...\n")

    # Get list of migration files
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

    fixed_count = 0
    for migration_file in migration_files:
        if fix_migration_file(migration_file):
            print(f"✓ Fixed {migration_file.name}")
            fixed_count += 1

    if fixed_count == 0:
        print("No fixes needed!")
    else:
        print(f"\n✓ Fixed {fixed_count} migration file(s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
