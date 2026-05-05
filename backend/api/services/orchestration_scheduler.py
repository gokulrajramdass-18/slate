"""
Orchestration Scheduler Service

Monitors and executes scheduled orchestrations using APScheduler.
Handles both one-time and recurring orchestration schedules.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.job import Job

from open_notebook.config import get_database
from open_notebook.database.repository import repo_execute, repo_query
from open_notebook.agents.autonomous_orchestrator import AutonomousOrchestrator

logger = logging.getLogger(__name__)


class OrchestrationScheduler:
    """
    Manages scheduled orchestration executions.

    Features:
    - One-time scheduled executions
    - Recurring cron-based executions
    - Automatic schedule management
    - Execution tracking and history
    """

    def __init__(self):
        """Initialize orchestration scheduler."""
        self.scheduler = AsyncIOScheduler()
        self._running_jobs: Dict[str, Job] = {}  # schedule_id -> Job
        self._started = False

    async def start(self):
        """Start the scheduler."""
        if self._started:
            return

        logger.info("🕐 Starting orchestration scheduler...")

        # Start APScheduler
        self.scheduler.start()
        self._started = True

        # Load and schedule all active schedules from database
        await self._load_schedules()

        logger.info(f"✅ Orchestration scheduler started with {len(self._running_jobs)} active schedules")

    async def stop(self):
        """Stop the scheduler."""
        if not self._started:
            return

        logger.info("🛑 Stopping orchestration scheduler...")

        # Shutdown scheduler
        self.scheduler.shutdown(wait=True)
        self._started = False

        logger.info("✅ Orchestration scheduler stopped")

    async def _load_schedules(self):
        """Load all active schedules from database and add to scheduler."""
        try:
            # Get all active schedules
            schedules = await repo_query(
                """
                SELECT id, user_id, goal, notebook_id, resources, config,
                       schedule_type, schedule_config, next_run
                FROM orchestration_schedules
                WHERE status = 'active'
                """,
                {}
            )

            logger.info(f"📋 Loading {len(schedules)} active orchestration schedules")

            for schedule in schedules:
                try:
                    await self._schedule_orchestration(schedule)
                except Exception as e:
                    logger.error(f"Failed to schedule {schedule['id']}: {e}", exc_info=True)

            logger.info(f"✅ Loaded {len(self._running_jobs)} orchestration schedules")

        except Exception as e:
            logger.error(f"Failed to load schedules: {e}", exc_info=True)

    async def _schedule_orchestration(self, schedule: Dict[str, Any]):
        """
        Schedule an orchestration execution.

        Args:
            schedule: Schedule record from database
        """
        schedule_id = schedule["id"]
        schedule_type = schedule["schedule_type"]
        schedule_config = json.loads(schedule["schedule_config"])

        logger.info(f"📅 Scheduling orchestration {schedule_id} (type: {schedule_type})")

        # Parse schedule configuration
        if schedule_type == "once":
            # One-time execution
            scheduled_datetime_str = schedule_config.get("datetime")
            if not scheduled_datetime_str:
                logger.error(f"Missing datetime for once schedule {schedule_id}")
                return

            # Parse datetime and ensure it's timezone-aware
            scheduled_datetime = datetime.fromisoformat(scheduled_datetime_str.replace('Z', '+00:00'))
            # If naive (no timezone), assume UTC
            if scheduled_datetime.tzinfo is None:
                scheduled_datetime = scheduled_datetime.replace(tzinfo=timezone.utc)

            # Check if already past
            if scheduled_datetime <= datetime.now(timezone.utc):
                logger.warning(f"Schedule {schedule_id} is in the past, marking as completed")
                await self._mark_schedule_completed(schedule_id)
                return

            # Create date trigger
            trigger = DateTrigger(run_date=scheduled_datetime)

            # Add job
            job = self.scheduler.add_job(
                self._execute_scheduled_orchestration,
                trigger=trigger,
                args=[schedule],
                id=schedule_id,
                name=f"Orchestration: {schedule['goal'][:50]}",
                replace_existing=True
            )

            self._running_jobs[schedule_id] = job
            logger.info(f"✅ Scheduled one-time orchestration {schedule_id} for {scheduled_datetime}")

        elif schedule_type == "recurring":
            # Recurring execution with cron
            cron_expression = schedule_config.get("cron")
            if not cron_expression:
                logger.error(f"Missing cron for recurring schedule {schedule_id}")
                return

            # Create cron trigger
            try:
                trigger = CronTrigger.from_crontab(cron_expression)
            except Exception as e:
                logger.error(f"Invalid cron expression for {schedule_id}: {e}")
                return

            # Add job
            job = self.scheduler.add_job(
                self._execute_scheduled_orchestration,
                trigger=trigger,
                args=[schedule],
                id=schedule_id,
                name=f"Orchestration: {schedule['goal'][:50]}",
                replace_existing=True
            )

            self._running_jobs[schedule_id] = job

            # Get next run time
            next_run = job.next_run_time
            logger.info(f"✅ Scheduled recurring orchestration {schedule_id} with cron '{cron_expression}', next run: {next_run}")

            # Update next_run in database
            if next_run:
                await repo_execute(
                    "UPDATE orchestration_schedules SET next_run = :next_run, updated_at = :updated_at WHERE id = :id",
                    {
                        "id": schedule_id,
                        "next_run": next_run.isoformat(),
                        "updated_at": datetime.utcnow().isoformat()
                    }
                )

    async def _execute_scheduled_orchestration(self, schedule: Dict[str, Any]):
        """
        Execute a scheduled orchestration.

        Supports two modes:
        1. Goal-based: Execute with goal string (existing behavior)
        2. Template-based: Instantiate template → execute with plan (new)

        Args:
            schedule: Schedule record from database
        """
        schedule_id = schedule["id"]
        schedule_type = schedule["schedule_type"]
        template_id = schedule.get("template_id")

        logger.info(f"🚀 Executing scheduled orchestration {schedule_id} (template_id: {template_id})")

        try:
            # Parse resources and config
            resources = json.loads(schedule["resources"]) if schedule["resources"] else None
            config = json.loads(schedule["config"]) if schedule["config"] else {}

            # Get model configuration from database if not in config
            model_name = config.get("model_name")
            api_key = config.get("api_key")
            base_url = config.get("base_url")

            logger.info(f"Initial config: model_name={model_name}, api_key={'<set>' if api_key else None}, base_url={base_url}")

            if not model_name or not api_key:
                # Get default language model from settings
                from api.services.settings import get_model_defaults
                from api.services.credential_manager import get_credential_manager
                from api.services.hana_connection_utils import decrypt_password

                logger.info("Fetching default model from settings...")
                model_defaults = await get_model_defaults()
                language_model_id = model_defaults.get("language_model_id")
                logger.info(f"Default language model ID: {language_model_id}")

                if language_model_id:
                    # Get credential for the default model
                    credential_manager = get_credential_manager()
                    credential = credential_manager.get(language_model_id)
                    logger.info(f"Credential found: {credential is not None}")

                    if credential:
                        model_name = model_name or credential.get("name") or language_model_id
                        logger.info(f"Using model: {model_name}")

                        # Decrypt API key
                        api_key_encrypted = credential.get("api_key_encrypted")
                        logger.info(f"Encrypted API key present: {api_key_encrypted is not None}")
                        if api_key_encrypted and not api_key:
                            api_key = decrypt_password(api_key_encrypted)
                            logger.info(f"API key decrypted: {api_key is not None and len(api_key) > 0}")

                        # Get base URL
                        base_url = base_url or credential.get("base_url")
                        logger.info(f"Base URL: {base_url}")

                        logger.info(f"Using default model from database: {model_name}")
                    else:
                        logger.warning(f"Default language model credential not found: {language_model_id}")
                else:
                    logger.warning("No default language model configured in settings")

            logger.info(f"Final config: model_name={model_name}, api_key={'<set>' if api_key else None}, base_url={base_url}")

            # Create orchestrator
            orchestrator = AutonomousOrchestrator(
                model_name=model_name or "gpt-4",
                api_key=api_key,
                base_url=base_url
            )

            # Determine execution mode: template-based or goal-based
            workspace_instance_id = None

            if template_id:
                # Template-based execution
                from api.services.template_instantiation_service import get_template_instantiation_service
                from open_notebook.domain.workspace_template import WorkspaceTemplate

                logger.info(f"Template-based execution for template {template_id}")

                # Parse parameters from schedule
                parameters = json.loads(schedule.get("parameters", "{}"))
                logger.info(f"Template parameters: {parameters}")

                # Load template to get name
                template = await WorkspaceTemplate.get(template_id)
                template_name = template.name if template else "Template"

                # Instantiate template as workspace
                instantiation_service = get_template_instantiation_service()
                workspace_name = f"{template_name} - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"

                workspace_instance_id = await instantiation_service.instantiate_template(
                    template_id=template_id,
                    parameters=parameters,
                    user_id=schedule["user_id"],
                    workspace_name=workspace_name
                )

                logger.info(f"Instantiated workspace {workspace_instance_id} from template {template_id}")

                # Execute from plan
                result = await orchestrator.execute_from_plan(
                    workspace_id=workspace_instance_id,
                    user_id=schedule["user_id"]
                )

            else:
                # Goal-based execution (existing behavior)
                logger.info("Goal-based execution")

                result = await orchestrator.execute(
                    goal=schedule["goal"],
                    user_id=schedule["user_id"],
                    notebook_id=schedule["notebook_id"],
                    resources=resources
                )

            # Save orchestration result to database
            orchestration_id = result.get("orchestration_id")
            if orchestration_id:
                # Link orchestration to schedule, template, and workspace instance
                await repo_execute(
                    """
                    UPDATE orchestrations
                    SET schedule_id = :schedule_id,
                        template_id = :template_id,
                        workspace_instance_id = :workspace_instance_id
                    WHERE id = :id
                    """,
                    {
                        "id": orchestration_id,
                        "schedule_id": schedule_id,
                        "template_id": template_id,
                        "workspace_instance_id": workspace_instance_id
                    }
                )

            # Execute bound actions after orchestration completes
            if orchestration_id:
                await self._execute_bound_actions(
                    schedule_id=schedule_id,
                    orchestration_id=orchestration_id,
                    context={
                        "status": result.get("status", "completed"),
                        "result": result.get("result"),
                        "error": result.get("error"),
                        "orchestration_id": orchestration_id,
                        "schedule_id": schedule_id,
                        "goal": schedule["goal"],
                        "notebook_id": schedule["notebook_id"],
                        "execution_count": schedule.get("execution_count", 0) + 1,
                    },
                    trigger_event="orchestration.completed",
                    user_id=schedule["user_id"]
                )

            # Update schedule execution tracking
            execution_count = schedule.get("execution_count", 0) + 1
            now = datetime.utcnow().isoformat()

            update_data = {
                "id": schedule_id,
                "last_run": now,
                "execution_count": execution_count,
                "updated_at": now
            }

            # For one-time schedules, mark as completed
            if schedule_type == "once":
                update_data["status"] = "completed"
                update_data["next_run"] = None

                await repo_execute(
                    """
                    UPDATE orchestration_schedules
                    SET last_run = :last_run, execution_count = :execution_count,
                        status = :status, next_run = :next_run, updated_at = :updated_at
                    WHERE id = :id
                    """,
                    update_data
                )

                # Remove from running jobs
                if schedule_id in self._running_jobs:
                    del self._running_jobs[schedule_id]

                logger.info(f"✅ Completed one-time schedule {schedule_id}")

            else:
                # For recurring schedules, calculate next run
                job = self._running_jobs.get(schedule_id)
                if job:
                    next_run = job.next_run_time
                    update_data["next_run"] = next_run.isoformat() if next_run else None

                await repo_execute(
                    """
                    UPDATE orchestration_schedules
                    SET last_run = :last_run, execution_count = :execution_count,
                        next_run = :next_run, updated_at = :updated_at
                    WHERE id = :id
                    """,
                    update_data
                )

                logger.info(f"✅ Executed recurring schedule {schedule_id}, next run: {update_data.get('next_run')}")

        except Exception as e:
            logger.error(f"Failed to execute scheduled orchestration {schedule_id}: {e}", exc_info=True)

            # Update schedule with error status
            await repo_execute(
                """
                UPDATE orchestration_schedules
                SET status = 'failed', updated_at = :updated_at
                WHERE id = :id
                """,
                {
                    "id": schedule_id,
                    "updated_at": datetime.utcnow().isoformat()
                }
            )

            # Remove from running jobs
            if schedule_id in self._running_jobs:
                del self._running_jobs[schedule_id]

    async def _mark_schedule_completed(self, schedule_id: str):
        """Mark a schedule as completed."""
        await repo_execute(
            """
            UPDATE orchestration_schedules
            SET status = 'completed', next_run = NULL, updated_at = :updated_at
            WHERE id = :id
            """,
            {
                "id": schedule_id,
                "updated_at": datetime.utcnow().isoformat()
            }
        )

    async def add_schedule(self, schedule: Dict[str, Any]):
        """
        Add a new schedule dynamically.

        Args:
            schedule: Schedule record from database
        """
        if not self._started:
            logger.warning("Scheduler not started, cannot add schedule")
            return

        await self._schedule_orchestration(schedule)

    async def remove_schedule(self, schedule_id: str):
        """
        Remove a schedule.

        Args:
            schedule_id: Schedule ID to remove
        """
        if schedule_id in self._running_jobs:
            job = self._running_jobs[schedule_id]
            job.remove()
            del self._running_jobs[schedule_id]
            logger.info(f"Removed schedule {schedule_id}")

    async def pause_schedule(self, schedule_id: str):
        """
        Pause a schedule.

        Args:
            schedule_id: Schedule ID to pause
        """
        if schedule_id in self._running_jobs:
            job = self._running_jobs[schedule_id]
            job.pause()
            logger.info(f"Paused schedule {schedule_id}")

            # Update database
            await repo_execute(
                "UPDATE orchestration_schedules SET status = 'paused', updated_at = :updated_at WHERE id = :id",
                {
                    "id": schedule_id,
                    "updated_at": datetime.utcnow().isoformat()
                }
            )

    async def resume_schedule(self, schedule_id: str):
        """
        Resume a paused schedule.

        Args:
            schedule_id: Schedule ID to resume
        """
        if schedule_id in self._running_jobs:
            job = self._running_jobs[schedule_id]
            job.resume()
            logger.info(f"Resumed schedule {schedule_id}")

            # Update database
            await repo_execute(
                "UPDATE orchestration_schedules SET status = 'active', updated_at = :updated_at WHERE id = :id",
                {
                    "id": schedule_id,
                    "updated_at": datetime.utcnow().isoformat()
                }
            )

    async def _execute_bound_actions(
        self,
        schedule_id: str,
        orchestration_id: str,
        context: Dict[str, Any],
        trigger_event: str,
        user_id: str
    ):
        """
        Execute actions bound to this schedule.

        Args:
            schedule_id: Schedule ID
            orchestration_id: Orchestration ID
            context: Context variables for action execution
            trigger_event: Event that triggered this execution
            user_id: User ID
        """
        try:
            from api.services.action_executor import ActionExecutor

            # Get active bindings for this schedule
            sql = """
                SELECT ab.*, a.name as action_name
                FROM orchestration_action_bindings ab
                JOIN actions a ON ab.action_id = a.id
                WHERE ab.schedule_id = :schedule_id
                  AND ab.is_active = 1
                  AND a.is_active = 1
                ORDER BY ab.execution_order ASC
            """
            bindings = await repo_query(sql, {"schedule_id": schedule_id})

            if not bindings:
                logger.debug(f"No action bindings found for schedule {schedule_id}")
                return

            logger.info(f"Executing {len(bindings)} bound actions for schedule {schedule_id}")

            executor = ActionExecutor()

            for binding in bindings:
                try:
                    logger.info(f"Executing action {binding['action_name']} (order {binding['execution_order']})")

                    result = await executor.execute_action(
                        action_id=binding["action_id"],
                        context=context,
                        user_id=user_id,
                        orchestration_id=orchestration_id,
                        trigger_event=trigger_event
                    )

                    logger.info(f"Action {binding['action_name']} executed: {result.status}")

                except Exception as e:
                    logger.error(f"Failed to execute action {binding['action_name']}: {e}", exc_info=True)
                    # Continue with other actions even if one fails

        except Exception as e:
            logger.error(f"Failed to execute bound actions for schedule {schedule_id}: {e}", exc_info=True)


# Global scheduler instance
_scheduler: Optional[OrchestrationScheduler] = None


async def get_orchestration_scheduler() -> OrchestrationScheduler:
    """Get or create the global orchestration scheduler."""
    global _scheduler

    if _scheduler is None:
        _scheduler = OrchestrationScheduler()
        await _scheduler.start()

    return _scheduler


async def shutdown_orchestration_scheduler():
    """Shutdown the global orchestration scheduler."""
    global _scheduler

    if _scheduler is not None:
        await _scheduler.stop()
        _scheduler = None
