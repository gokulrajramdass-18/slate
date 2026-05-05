"""
Sync Service - Background job scheduler for source synchronization

Provides cron-based scheduling for HANA tables and API sources with:
- Periodic sync scheduling (cron expressions)
- Manual sync triggering
- Job queue management
- Retry logic with exponential backoff
- Error tracking and status monitoring
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from enum import Enum

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor

from open_notebook.database.repository import repo_query, repo_create, repo_update

# Configure logging
logger = logging.getLogger(__name__)


class SyncStatus(str, Enum):
    """Sync job status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SyncFrequency(str, Enum):
    """Sync frequency mappings to cron expressions"""
    MANUAL = "manual"
    HOURLY = "0 * * * *"  # Every hour at minute 0
    DAILY = "0 2 * * *"   # Every day at 2 AM
    WEEKLY = "0 2 * * 1"  # Every Monday at 2 AM


class SyncService:
    """
    Background sync service for external data sources

    Manages scheduled and on-demand synchronization for:
    - HANA table sources
    - API sources (with OAuth support)
    """

    def __init__(self):
        """Initialize sync service with APScheduler"""
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.active_jobs: Dict[str, str] = {}  # source_id -> job_id mapping
        self._running = False

    async def start(self):
        """Start the sync scheduler"""
        if self._running:
            logger.warning("Sync service already running")
            return

        logger.info("Starting sync service...")

        # Configure scheduler
        jobstores = {
            'default': MemoryJobStore()
        }
        executors = {
            'default': AsyncIOExecutor()
        }
        job_defaults = {
            'coalesce': True,  # Combine missed runs
            'max_instances': 1,  # One instance per job
            'misfire_grace_time': 300  # 5 minutes grace period
        }

        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='UTC'
        )

        # Start scheduler
        self.scheduler.start()
        self._running = True

        # Load existing scheduled syncs from database
        await self._load_scheduled_syncs()

        logger.info("Sync service started successfully")

    async def stop(self):
        """Stop the sync scheduler gracefully"""
        if not self._running:
            return

        logger.info("Stopping sync service...")

        if self.scheduler:
            # Wait for running jobs to complete (with timeout)
            self.scheduler.shutdown(wait=True)

        self._running = False
        self.active_jobs.clear()

        logger.info("Sync service stopped")

    async def schedule_sync(
        self,
        source_id: str,
        frequency: str
    ) -> Dict[str, Any]:
        """
        Schedule periodic sync for a source

        Args:
            source_id: Source UUID
            frequency: Sync frequency (manual, hourly, daily, weekly)

        Returns:
            Dict with scheduling info
        """
        if not self._running:
            raise RuntimeError("Sync service not running")

        # Validate source exists
        source = await self._get_source(source_id)
        if not source:
            raise ValueError(f"Source {source_id} not found")

        # Check if manual
        if frequency == SyncFrequency.MANUAL.value:
            # Cancel any existing schedule
            await self.cancel_sync(source_id)
            return {
                "source_id": source_id,
                "frequency": frequency,
                "scheduled": False,
                "message": "Manual sync - no schedule created"
            }

        # Get cron expression
        cron_expr = self._frequency_to_cron(frequency)
        if not cron_expr:
            raise ValueError(f"Invalid frequency: {frequency}")

        # Cancel existing job if any
        await self.cancel_sync(source_id)

        # Schedule new job
        job = self.scheduler.add_job(
            self._execute_sync_job,
            trigger=CronTrigger.from_crontab(cron_expr),
            args=[source_id],
            id=f"sync_{source_id}",
            name=f"Sync: {source['name']}",
            replace_existing=True
        )

        # Track job
        self.active_jobs[source_id] = job.id

        # Update source sync config
        await repo_update(
            "sources",
            source_id,
            {
                "sync_config": {
                    "frequency": frequency,
                    "cron": cron_expr,
                    "job_id": job.id,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None
                }
            }
        )

        logger.info(f"Scheduled sync for source {source_id} with frequency {frequency}")

        return {
            "source_id": source_id,
            "frequency": frequency,
            "cron": cron_expr,
            "job_id": job.id,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "scheduled": True
        }

    async def execute_sync(
        self,
        source_id: str,
        force: bool = False
    ) -> str:
        """
        Execute sync immediately (manual trigger)

        Args:
            source_id: Source UUID
            force: Force sync even if one is in progress

        Returns:
            Sync history ID
        """
        if not self._running:
            raise RuntimeError("Sync service not running")

        # Validate source
        source = await self._get_source(source_id)
        if not source:
            raise ValueError(f"Source {source_id} not found")

        # Check if already running
        if not force and source.get("sync_status") == SyncStatus.IN_PROGRESS.value:
            raise RuntimeError("Sync already in progress for this source")

        # Create sync history record
        history_id = await repo_create("sync_history", {
            "source_id": source_id,
            "status": SyncStatus.PENDING.value,
            "started_at": datetime.utcnow().isoformat()
        })

        # Execute sync in background
        asyncio.create_task(self._execute_sync_job(source_id, history_id))

        return history_id

    async def cancel_sync(self, source_id: str):
        """
        Cancel scheduled sync for a source

        Args:
            source_id: Source UUID
        """
        if not self._running:
            return

        job_id = self.active_jobs.get(source_id)
        if job_id:
            try:
                self.scheduler.remove_job(job_id)
                logger.info(f"Cancelled sync job {job_id} for source {source_id}")
            except Exception as e:
                logger.warning(f"Failed to cancel job {job_id}: {e}")
            finally:
                self.active_jobs.pop(source_id, None)

    async def get_sync_status(self, source_id: str) -> Optional[Dict[str, Any]]:
        """
        Get sync status for a source

        Args:
            source_id: Source UUID

        Returns:
            Dict with sync status info
        """
        source = await self._get_source(source_id)
        if not source:
            return None

        # Get latest sync history
        history = await repo_query(
            """
            SELECT * FROM sync_history
            WHERE source_id = :source_id
            ORDER BY created DESC
            LIMIT 1
            """,
            {"source_id": source_id}
        )

        latest = history[0] if history else None

        # Get job info
        job_id = self.active_jobs.get(source_id)
        job_info = None
        if job_id:
            try:
                job = self.scheduler.get_job(job_id)
                if job:
                    job_info = {
                        "job_id": job.id,
                        "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                        "trigger": str(job.trigger)
                    }
            except Exception as e:
                logger.warning(f"Failed to get job info: {e}")

        return {
            "source_id": source_id,
            "sync_status": source.get("sync_status"),
            "last_synced": source.get("last_synced"),
            "error_message": source.get("error_message"),
            "latest_sync": latest,
            "scheduled_job": job_info
        }

    async def get_sync_history(
        self,
        source_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get sync history for a source

        Args:
            source_id: Source UUID
            limit: Maximum number of records to return

        Returns:
            List of sync history records
        """
        return await repo_query(
            """
            SELECT * FROM sync_history
            WHERE source_id = :source_id
            ORDER BY created DESC
            LIMIT :limit
            """,
            {"source_id": source_id, "limit": limit}
        )

    # ========================================================================
    # Internal Methods
    # ========================================================================

    async def _execute_sync_job(
        self,
        source_id: str,
        history_id: Optional[str] = None
    ):
        """
        Execute sync job with error handling and retry logic

        Args:
            source_id: Source UUID
            history_id: Sync history record ID (created if not provided)
        """
        source = None
        start_time = datetime.utcnow()

        try:
            # Get source
            source = await self._get_source(source_id)
            if not source:
                raise ValueError(f"Source {source_id} not found")

            # Create history record if not provided
            if not history_id:
                history_id = await repo_create("sync_history", {
                    "source_id": source_id,
                    "status": SyncStatus.PENDING.value,
                    "started_at": start_time.isoformat()
                })

            # Update source status
            await repo_update("sources", source_id, {
                "sync_status": SyncStatus.IN_PROGRESS.value,
                "error_message": None
            })

            # Update history status
            await repo_update("sync_history", history_id, {
                "status": SyncStatus.IN_PROGRESS.value
            })

            logger.info(f"Starting sync for source {source_id} ({source['source_type']})")

            # Execute sync based on source type
            source_type = source["source_type"]
            rows_updated = 0

            if source_type == "hana_table":
                from open_notebook.sources.hana_table import sync_hana_table
                rows_updated = await sync_hana_table(source)
            elif source_type == "api":
                from open_notebook.sources.api_source import sync_api_source
                rows_updated = await sync_api_source(source)
            else:
                raise ValueError(f"Unsupported source type for sync: {source_type}")

            # Calculate duration
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()

            # Update source
            await repo_update("sources", source_id, {
                "sync_status": SyncStatus.COMPLETED.value,
                "last_synced": end_time.isoformat(),
                "error_message": None
            })

            # Update history
            await repo_update("sync_history", history_id, {
                "status": SyncStatus.COMPLETED.value,
                "completed_at": end_time.isoformat(),
                "rows_updated": rows_updated,
                "duration_seconds": duration,
                "error": None
            })

            logger.info(
                f"Sync completed for source {source_id}: "
                f"{rows_updated} rows updated in {duration:.2f}s"
            )

        except Exception as e:
            logger.error(f"Sync failed for source {source_id}: {e}", exc_info=True)

            # Update source
            await repo_update("sources", source_id, {
                "sync_status": SyncStatus.FAILED.value,
                "error_message": str(e)
            })

            # Update history
            if history_id:
                await repo_update("sync_history", history_id, {
                    "status": SyncStatus.FAILED.value,
                    "completed_at": datetime.utcnow().isoformat(),
                    "error": str(e)
                })

    async def _load_scheduled_syncs(self):
        """Load scheduled syncs from database on startup"""
        try:
            # Get all sources with scheduled sync
            sources = await repo_query(
                """
                SELECT id, title, source_type, sync_config
                FROM sources
                WHERE sync_config IS NOT NULL
                AND source_type IN ('hana_table', 'api')
                """
            )

            for source in sources:
                try:
                    # Parse sync_config from JSON string
                    import json
                    sync_config_raw = source.get("sync_config")

                    if sync_config_raw:
                        # Parse JSON string to dict
                        if isinstance(sync_config_raw, str):
                            sync_config = json.loads(sync_config_raw)
                        else:
                            sync_config = sync_config_raw

                        frequency = sync_config.get("frequency")

                        if frequency and frequency != SyncFrequency.MANUAL.value:
                            await self.schedule_sync(source["id"], frequency)
                            logger.info(f"Restored scheduled sync for source {source['id']}")
                except Exception as e:
                    logger.error(
                        f"Failed to restore sync for source {source['id']}: {e}"
                    )

        except Exception as e:
            logger.error(f"Failed to load scheduled syncs: {e}")

    async def _get_source(self, source_id: str) -> Optional[Dict[str, Any]]:
        """Get source by ID"""
        results = await repo_query(
            "SELECT * FROM sources WHERE id = :id",
            {"id": source_id}
        )
        return results[0] if results else None

    def _frequency_to_cron(self, frequency: str) -> Optional[str]:
        """Convert frequency to cron expression"""
        try:
            return SyncFrequency[frequency.upper()].value
        except KeyError:
            return None


# Global sync service instance
_sync_service: Optional[SyncService] = None


def get_sync_service() -> SyncService:
    """Get global sync service instance"""
    global _sync_service
    if _sync_service is None:
        _sync_service = SyncService()
    return _sync_service
