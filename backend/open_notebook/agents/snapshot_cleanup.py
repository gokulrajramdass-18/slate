"""
Snapshot Cleanup Job

Scheduled background task to delete expired snapshots and free storage space.

Features:
- Deletes snapshots past their expiration date
- Removes associated file/chunked storage
- Configurable cleanup frequency
- Logging and statistics
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from open_notebook.database.repository import repo_query, repo_delete
from open_notebook.domain.workflow_snapshot import StorageType

logger = logging.getLogger(__name__)


async def cleanup_expired_snapshots() -> Dict[str, Any]:
    """
    Clean up expired snapshots.

    Deletes:
    1. Database records past expires_at
    2. Associated file storage
    3. Empty directories

    Returns:
        Statistics dict with counts
    """
    logger.info("[SnapshotCleanup] Starting cleanup job")

    stats = {
        "deleted_count": 0,
        "freed_bytes": 0,
        "errors": 0,
        "storage_cleaned": {
            "inline": 0,
            "file": 0,
            "chunked": 0
        }
    }

    try:
        # Find expired snapshots
        expired = await repo_query(
            """SELECT id, storage_type, storage_path, total_size_bytes
               FROM workflow_snapshots
               WHERE expires_at IS NOT NULL
               AND datetime(expires_at) < datetime('now')""",
            {}
        )

        logger.info(f"[SnapshotCleanup] Found {len(expired)} expired snapshots")

        # Process each expired snapshot
        for snapshot in expired:
            try:
                # Delete storage if not inline
                storage_type = StorageType(snapshot["storage_type"])

                if storage_type in [StorageType.FILE, StorageType.CHUNKED]:
                    await _delete_storage_files(snapshot["storage_path"])

                # Delete database record
                await repo_delete("workflow_snapshots", snapshot["id"])

                # Update stats
                stats["deleted_count"] += 1
                stats["freed_bytes"] += snapshot.get("total_size_bytes", 0)
                stats["storage_cleaned"][storage_type.value] += 1

                logger.debug(f"[SnapshotCleanup] Deleted snapshot {snapshot['id']}")

            except Exception as e:
                logger.error(f"[SnapshotCleanup] Error deleting snapshot {snapshot['id']}: {e}")
                stats["errors"] += 1

        # Clean up empty directories
        await _cleanup_empty_directories()

        logger.info(
            f"[SnapshotCleanup] Cleanup complete: "
            f"deleted {stats['deleted_count']} snapshots, "
            f"freed {stats['freed_bytes'] / 1024 / 1024:.2f} MB"
        )

    except Exception as e:
        logger.error(f"[SnapshotCleanup] Cleanup job failed: {e}", exc_info=True)
        stats["errors"] += 1

    return stats


async def _delete_storage_files(storage_path: str) -> None:
    """
    Delete snapshot storage files.

    Args:
        storage_path: Relative path to storage
    """
    import os
    import shutil

    base_path = Path(os.getenv("SNAPSHOT_STORAGE_PATH", "./data/snapshots"))
    full_path = base_path / storage_path

    if not full_path.exists():
        logger.warning(f"[SnapshotCleanup] Storage path not found: {full_path}")
        return

    try:
        if full_path.is_file():
            # Single file
            full_path.unlink()
            logger.debug(f"[SnapshotCleanup] Deleted file: {full_path}")
        elif full_path.is_dir():
            # Directory (chunked storage)
            shutil.rmtree(full_path)
            logger.debug(f"[SnapshotCleanup] Deleted directory: {full_path}")
    except Exception as e:
        logger.error(f"[SnapshotCleanup] Error deleting storage: {e}")
        raise


async def _cleanup_empty_directories() -> None:
    """Clean up empty directories in snapshot storage."""
    import os

    base_path = Path(os.getenv("SNAPSHOT_STORAGE_PATH", "./data/snapshots"))

    if not base_path.exists():
        return

    # Walk bottom-up to delete empty directories
    for dirpath, dirnames, filenames in os.walk(str(base_path), topdown=False):
        dir_path = Path(dirpath)

        # Skip base directory
        if dir_path == base_path:
            continue

        # Check if empty
        if not any(dir_path.iterdir()):
            try:
                dir_path.rmdir()
                logger.debug(f"[SnapshotCleanup] Removed empty directory: {dir_path}")
            except Exception as e:
                logger.warning(f"[SnapshotCleanup] Could not remove directory {dir_path}: {e}")


# ============================================================================
# Scheduler Integration
# ============================================================================

def schedule_cleanup_job():
    """
    Schedule the cleanup job to run periodically.

    Uses APScheduler to run daily at 2 AM.
    """
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = AsyncIOScheduler()

    # Schedule for 2 AM daily
    scheduler.add_job(
        cleanup_expired_snapshots,
        CronTrigger(hour=2, minute=0),
        id="snapshot_cleanup",
        name="Workflow Snapshot Cleanup",
        replace_existing=True
    )

    scheduler.start()
    logger.info("[SnapshotCleanup] Scheduled daily cleanup job for 2:00 AM")

    return scheduler


# ============================================================================
# Manual Execution
# ============================================================================

if __name__ == "__main__":
    """Run cleanup job manually"""
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Run cleanup
    stats = asyncio.run(cleanup_expired_snapshots())

    print("\n=== Cleanup Complete ===")
    print(f"Deleted: {stats['deleted_count']} snapshots")
    print(f"Freed: {stats['freed_bytes'] / 1024 / 1024:.2f} MB")
    print(f"Storage cleaned:")
    for storage_type, count in stats["storage_cleaned"].items():
        print(f"  - {storage_type}: {count}")
    if stats["errors"] > 0:
        print(f"Errors: {stats['errors']}")
        sys.exit(1)
