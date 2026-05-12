#!/usr/bin/env python3
"""
Clean database initialization - bypasses migration system entirely
Uses static schema.sql file
"""
import aiosqlite
import asyncio
import os

async def init_db():
    db_path = os.getenv("SQLITE_DB_PATH", "/app/data/database.db")

    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    print(f"Initializing database at {db_path}")

    # Remove existing database to start fresh
    if os.path.exists(db_path):
        print("Removing existing database for clean init...")
        os.remove(db_path)
        print("✅ Old database removed")

    # Read schema file
    schema_file = os.path.join(os.path.dirname(__file__), "schema_clean.sql")
    if not os.path.exists(schema_file):
        print(f"❌ ERROR: Schema file not found at {schema_file}")
        raise FileNotFoundError(f"Schema file not found: {schema_file}")

    print(f"Loading schema from {schema_file}...")

    with open(schema_file, 'r') as f:
        schema_sql = f.read()

    async with aiosqlite.connect(db_path) as db:
        # Execute schema
        await db.executescript(schema_sql)
        await db.commit()
        print("✅ Schema created successfully")

    print("✅ Database initialized successfully - SKIPPING MIGRATIONS")

if __name__ == "__main__":
    asyncio.run(init_db())
