"""
Migration runner for sync tracking

Handles adding sync tracking columns and tables to existing database.
"""

import asyncio
import logging
from open_notebook.database.repository import repo_query, repo_create, db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_sync_migration():
    """Run sync tracking migration"""

    try:
        async with db_connection() as db:
            logger.info("Running sync tracking migration...")

            # Check if migration already applied
            existing = await repo_query(
                "SELECT * FROM _migrations WHERE name = :name",
                {"name": "sync_tracking"}
            )

            if existing:
                logger.info("Sync tracking migration already applied, skipping")
                return

            # Create sync_history table
            logger.info("Creating sync_history table...")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sync_history (
                    id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    rows_updated INTEGER DEFAULT 0,
                    duration_seconds REAL,
                    error TEXT,
                    created TEXT NOT NULL DEFAULT (datetime('now')),
                    updated TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
                )
            """)

            # Create indexes
            logger.info("Creating indexes...")
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_sync_history_source ON sync_history(source_id)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_sync_history_status ON sync_history(status)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_sync_history_created ON sync_history(created DESC)"
            )

            # Check if source_embeddings needs content_hash column
            logger.info("Checking source_embeddings table...")
            try:
                # Try to query content_hash column
                await db.query("SELECT content_hash FROM source_embeddings LIMIT 1")
                logger.info("content_hash column already exists")
            except:
                # Column doesn't exist, add it
                logger.info("Adding content_hash column to source_embeddings...")
                await db.execute(
                    "ALTER TABLE source_embeddings ADD COLUMN content_hash TEXT"
                )

            # Check if sources table needs sync columns
            logger.info("Checking sources table...")
            columns_to_add = [
                ("last_synced", "TEXT"),
                ("sync_status", "TEXT"),
                ("error_message", "TEXT")
            ]

            for col_name, col_type in columns_to_add:
                try:
                    # Try to query column
                    await db.query(f"SELECT {col_name} FROM sources LIMIT 1")
                    logger.info(f"{col_name} column already exists")
                except:
                    # Column doesn't exist, add it
                    logger.info(f"Adding {col_name} column to sources...")
                    await db.execute(
                        f"ALTER TABLE sources ADD COLUMN {col_name} {col_type}"
                    )

            # Record migration
            logger.info("Recording migration...")
            await repo_create("_migrations", {
                "version": 4,
                "name": "sync_tracking",
            })

            logger.info("✅ Sync tracking migration completed successfully")

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(run_sync_migration())
