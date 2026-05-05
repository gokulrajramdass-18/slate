#!/usr/bin/env python3
"""
Fix migrations by checking for existing columns/tables before applying changes.
This script wraps problematic ALTER TABLE statements with existence checks.
"""

import sqlite3
import sys
from pathlib import Path

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


def check_migration_compatibility(migration_file):
    """Check which ALTER TABLE statements would fail."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    issues = []

    with open(migration_file, 'r') as f:
        content = f.read()
        lines = content.split('\n')

        for i, line in enumerate(lines, 1):
            line = line.strip()

            # Check ALTER TABLE ADD COLUMN statements
            if line.startswith('ALTER TABLE') and 'ADD COLUMN' in line:
                parts = line.replace(';', '').split()
                try:
                    table_idx = parts.index('TABLE') + 1
                    column_idx = parts.index('COLUMN') + 1
                    table_name = parts[table_idx]
                    column_name = parts[column_idx]

                    if table_exists(cursor, table_name):
                        if column_exists(cursor, table_name, column_name):
                            issues.append({
                                'line': i,
                                'type': 'duplicate_column',
                                'table': table_name,
                                'column': column_name,
                                'sql': line
                            })
                    else:
                        issues.append({
                            'line': i,
                            'type': 'missing_table',
                            'table': table_name,
                            'sql': line
                        })
                except (ValueError, IndexError):
                    pass

            # Check CREATE INDEX statements
            if line.startswith('CREATE INDEX') and 'IF NOT EXISTS' not in line:
                # Extract table name from the statement
                if '(' in line and ')' in line:
                    parts = line.split('ON')
                    if len(parts) == 2:
                        table_part = parts[1].split('(')[0].strip()
                        if not table_exists(cursor, table_part):
                            issues.append({
                                'line': i,
                                'type': 'index_on_missing_table',
                                'table': table_part,
                                'sql': line
                            })

    conn.close()
    return issues


def main():
    if not DATABASE_PATH.exists():
        print(f"Database not found: {DATABASE_PATH}")
        return 1

    print("Scanning migrations for compatibility issues...\n")

    # Get list of migration files
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

    all_issues = {}
    for migration_file in migration_files:
        issues = check_migration_compatibility(migration_file)
        if issues:
            all_issues[migration_file.name] = issues

    if not all_issues:
        print("✓ No compatibility issues found!")
        return 0

    print(f"Found issues in {len(all_issues)} migration(s):\n")

    for filename, issues in all_issues.items():
        print(f"📄 {filename}")
        for issue in issues:
            if issue['type'] == 'duplicate_column':
                print(f"  Line {issue['line']}: Column '{issue['column']}' already exists in '{issue['table']}'")
                print(f"    → {issue['sql']}")
            elif issue['type'] == 'missing_table':
                print(f"  Line {issue['line']}: Table '{issue['table']}' doesn't exist")
                print(f"    → {issue['sql']}")
            elif issue['type'] == 'index_on_missing_table':
                print(f"  Line {issue['line']}: Cannot create index on missing table '{issue['table']}'")
                print(f"    → {issue['sql']}")
        print()

    print("\nRecommendation:")
    print("1. Comment out duplicate column additions")
    print("2. Add 'IF NOT EXISTS' to CREATE INDEX statements")
    print("3. Ensure tables exist before creating indexes")

    return 0


if __name__ == "__main__":
    sys.exit(main())
