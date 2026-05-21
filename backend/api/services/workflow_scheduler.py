"""
Workflow Scheduler Service

Manages scheduled workflow executions using APScheduler.
Supports cron schedules, event triggers, and dependency chains.
"""

import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.job import Job

from open_notebook.domain.workflow import (
    Workflow,
    WorkflowSchedule,
    ScheduleType,
)
from open_notebook.agents.workflow_engine import WorkflowEngine


class WorkflowScheduler:
    """
    Manages scheduled workflow executions.

    Features:
    - Cron-based scheduling
    - Event-driven triggers
    - Dependency chain execution
    - Automatic retry on failure (optional)
    """

    def __init__(self):
        """Initialize workflow scheduler."""
        self.scheduler = AsyncIOScheduler()
        self._running_jobs: Dict[str, Job] = {}  # schedule_id -> Job
        self._started = False

    async def start(self):
        """Start the scheduler."""
        if self._started:
            return

        print("🕐 Starting workflow scheduler...")

        # Start APScheduler
        self.scheduler.start()
        self._started = True

        # Load and schedule all enabled schedules from database
        await self._load_schedules()

        print(f"✅ Workflow scheduler started with {len(self._running_jobs)} active schedules")

    async def stop(self):
        """Stop the scheduler."""
        if not self._started:
            return

        print("🛑 Stopping workflow scheduler...")

        # Shutdown scheduler
        self.scheduler.shutdown(wait=True)
        self._started = False

        print("✅ Workflow scheduler stopped")

    async def _load_schedules(self):
        """Load all enabled schedules from database and add to scheduler."""
        try:
            # Get database and ensure it's connected
            from open_notebook.config import get_database
            db = get_database()

            if not db.is_connected:
                await db.connect()

            # Get all enabled schedules
            schedules = await WorkflowSchedule.get_enabled()

            for schedule in schedules:
                try:
                    await self.schedule_workflow(schedule)
                except Exception as e:
                    print(f"⚠️ Failed to load schedule {schedule.id}: {e}")

        except Exception as e:
            print(f"❌ Failed to load schedules: {e}")

    async def schedule_workflow(self, schedule: WorkflowSchedule):
        """
        Add workflow to scheduler.

        Args:
            schedule: WorkflowSchedule instance
        """
        if not self._started:
            raise RuntimeError("Scheduler not started. Call start() first.")

        # Remove existing job if present
        if schedule.id in self._running_jobs:
            await self.unschedule_workflow(schedule.id)

        # Skip if schedule is disabled
        if not schedule.enabled:
            print(f"⏸️ Skipping disabled schedule {schedule.id}")
            return

        # Add job based on schedule type
        if schedule.schedule_type == ScheduleType.CRON:
            await self._schedule_cron(schedule)

        elif schedule.schedule_type == ScheduleType.EVENT:
            await self._schedule_event(schedule)

        elif schedule.schedule_type == ScheduleType.DEPENDENCY:
            await self._schedule_dependency(schedule)

        print(f"📅 Scheduled workflow {schedule.workflow_id} ({schedule.schedule_type.value})")

    async def _schedule_cron(self, schedule: WorkflowSchedule):
        """Schedule workflow with cron expression."""
        if not schedule.cron_expression:
            raise ValueError(f"Schedule {schedule.id} missing cron_expression")

        # Parse cron expression
        try:
            trigger = CronTrigger.from_crontab(schedule.cron_expression)
        except Exception as e:
            raise ValueError(f"Invalid cron expression: {schedule.cron_expression}") from e

        # Add job to scheduler
        job = self.scheduler.add_job(
            self._execute_workflow,
            trigger=trigger,
            args=[schedule.workflow_id, schedule.id],
            id=f"workflow_{schedule.workflow_id}_{schedule.id}",
            name=f"Workflow {schedule.workflow_id}",
            replace_existing=True,
            max_instances=1,  # Don't run multiple instances simultaneously
        )

        self._running_jobs[schedule.id] = job

        # Update next_run_at in database
        if job.next_run_time:
            schedule.next_run_at = job.next_run_time
            await schedule.save()

    async def _schedule_event(self, schedule: WorkflowSchedule):
        """
        Schedule workflow for event-driven execution.

        Note: This registers the schedule but actual triggering happens
        via the trigger_workflow_by_event() method when events occur.
        """
        # Store schedule ID for event lookup
        # Actual triggering happens when events are published
        print(f"📢 Registered event trigger for workflow {schedule.workflow_id}")

        # Event triggers are passive - they don't create APScheduler jobs
        # They're stored in database and checked when events occur

    async def _schedule_dependency(self, schedule: WorkflowSchedule):
        """
        Schedule workflow to run after another workflow completes.

        Note: This registers the dependency but actual triggering happens
        when the upstream workflow completes successfully.
        """
        if not schedule.upstream_workflow_id:
            raise ValueError(f"Schedule {schedule.id} missing upstream_workflow_id")

        print(f"🔗 Registered dependency chain: {schedule.upstream_workflow_id} → {schedule.workflow_id}")

        # Dependency chains are passive - checked after workflow completion
        # No APScheduler job needed

    async def unschedule_workflow(self, schedule_id: str):
        """
        Remove workflow from scheduler.

        Args:
            schedule_id: Schedule ID to remove
        """
        if schedule_id in self._running_jobs:
            job = self._running_jobs[schedule_id]
            job.remove()
            del self._running_jobs[schedule_id]
            print(f"🗑️ Removed schedule {schedule_id}")

    async def _execute_workflow(self, workflow_id: str, schedule_id: str):
        """
        Execute a scheduled workflow.

        Args:
            workflow_id: Workflow to execute
            schedule_id: Schedule that triggered execution
        """
        print(f"⚡ Executing scheduled workflow: {workflow_id}")

        try:
            # Get workflow
            workflow = await Workflow.get(workflow_id)

            if not workflow:
                print(f"❌ Workflow {workflow_id} not found")
                return

            if not workflow.is_active:
                print(f"⚠️ Workflow {workflow_id} is not active, skipping execution")
                return

            # Load schedule to pull stored user-provided input_data
            schedule = await WorkflowSchedule.get(schedule_id)
            stored_input = (schedule.input_data or {}) if schedule else {}

            # Create engine and execute. User-provided values flow first; trigger
            # metadata is appended (and overrides) so callers can detect it.
            engine = WorkflowEngine(workflow)
            execution = await engine.execute(
                input_data={
                    **stored_input,
                    "triggered_by": "cron",
                    "schedule_id": schedule_id,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

            # Update schedule last_run_at
            if schedule:
                schedule.last_run_at = datetime.utcnow()

                # Update next_run_at if job exists
                if schedule_id in self._running_jobs:
                    job = self._running_jobs[schedule_id]
                    if job.next_run_time:
                        schedule.next_run_at = job.next_run_time

                await schedule.save()

            print(f"✅ Workflow {workflow_id} executed: {execution.status.value}")

            # Check for dependency chains
            await self._trigger_dependent_workflows(workflow_id, execution)

        except Exception as e:
            print(f"❌ Failed to execute workflow {workflow_id}: {e}")

    async def _trigger_dependent_workflows(
        self,
        workflow_id: str,
        execution
    ):
        """
        Trigger workflows that depend on this workflow completing.

        Args:
            workflow_id: Workflow that just completed
            execution: WorkflowExecution instance
        """
        # Only trigger if execution was successful
        if execution.status.value != "completed":
            return

        # Find schedules that depend on this workflow
        schedules = await WorkflowSchedule.get_enabled()
        dependent_schedules = [
            s for s in schedules
            if s.schedule_type == ScheduleType.DEPENDENCY
            and s.upstream_workflow_id == workflow_id
        ]

        for schedule in dependent_schedules:
            print(f"🔗 Triggering dependent workflow: {schedule.workflow_id}")

            # Execute dependent workflow
            try:
                await self._execute_workflow(
                    schedule.workflow_id,
                    schedule.id
                )
            except Exception as e:
                print(f"❌ Failed to trigger dependent workflow {schedule.workflow_id}: {e}")

    async def trigger_workflow_by_event(
        self,
        event_type: str,
        event_data: Optional[Dict[str, Any]] = None
    ):
        """
        Trigger workflows based on event.

        Args:
            event_type: Type of event (e.g., "source_updated", "notebook_created")
            event_data: Optional event data for filtering
        """
        print(f"📢 Event received: {event_type}")

        # Find schedules for this event type
        schedules = await WorkflowSchedule.get_enabled()
        event_schedules = [
            s for s in schedules
            if s.schedule_type == ScheduleType.EVENT
            and s.event_trigger
            and s.event_trigger.event_type == event_type
        ]

        for schedule in event_schedules:
            # Check filters if present
            if schedule.event_trigger.filters and event_data:
                # Simple filter matching (key-value pairs)
                matches = all(
                    event_data.get(key) == value
                    for key, value in schedule.event_trigger.filters.items()
                )
                if not matches:
                    continue

            print(f"⚡ Triggering workflow {schedule.workflow_id} for event {event_type}")

            # Execute workflow
            try:
                await self._execute_workflow(
                    schedule.workflow_id,
                    schedule.id
                )
            except Exception as e:
                print(f"❌ Failed to trigger workflow {schedule.workflow_id}: {e}")

    async def get_job_status(self, schedule_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a scheduled job.

        Args:
            schedule_id: Schedule ID

        Returns:
            Job status dict or None if not found
        """
        if schedule_id not in self._running_jobs:
            return None

        job = self._running_jobs[schedule_id]

        return {
            "schedule_id": schedule_id,
            "job_id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "pending": job.pending,
        }

    async def list_jobs(self) -> list[Dict[str, Any]]:
        """
        List all scheduled jobs.

        Returns:
            List of job status dicts
        """
        jobs = []

        for schedule_id, job in self._running_jobs.items():
            jobs.append({
                "schedule_id": schedule_id,
                "job_id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "pending": job.pending,
            })

        return jobs


# ============================================================================
# Singleton Instance
# ============================================================================

_scheduler_instance: Optional[WorkflowScheduler] = None


def get_workflow_scheduler() -> WorkflowScheduler:
    """
    Get singleton workflow scheduler instance.

    Returns:
        WorkflowScheduler instance
    """
    global _scheduler_instance

    if _scheduler_instance is None:
        _scheduler_instance = WorkflowScheduler()

    return _scheduler_instance
