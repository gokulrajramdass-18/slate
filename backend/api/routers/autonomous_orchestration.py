"""
Autonomous Orchestration API Router

REST API endpoints for autonomous agent orchestration with Server-Sent Events (SSE) streaming.
"""

import logging
import asyncio
import json
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Header, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from open_notebook.agents.autonomous_orchestrator import AutonomousOrchestrator
from open_notebook.config import get_default_model, get_database
from open_notebook.database.repository import repo_query, repo_execute

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orchestration", tags=["Autonomous Orchestration"])


# Request/Response Models
class OrchestrationRequest(BaseModel):
    """Request to start autonomous orchestration."""
    goal: str = Field(..., min_length=10, max_length=2000, description="User's goal")
    notebook_id: Optional[str] = Field(None, description="Notebook context")
    resources: Optional[Dict[str, Any]] = Field(None, description="Available resources")
    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Orchestration config")


class OrchestrationResponse(BaseModel):
    """Response from orchestration execution."""
    orchestration_id: str
    status: str
    orchestration_mode: Optional[str] = None
    team_id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str


class OrchestrationStatus(BaseModel):
    """Status of an orchestration."""
    orchestration_id: str
    status: str
    current_phase: str
    progress: float  # 0.0 to 1.0
    team_id: Optional[str] = None
    orchestration_mode: Optional[str] = None
    started_at: str
    updated_at: str


class OrchestrationListItem(BaseModel):
    """List item for orchestrations."""
    orchestration_id: str
    goal: str
    status: str
    orchestration_mode: Optional[str] = None
    team_id: Optional[str] = None
    created_at: str


def _generate_orchestration_id() -> str:
    """Generate unique orchestration ID."""
    import uuid
    return str(uuid.uuid4())


async def _save_orchestration(orchestration_data: Dict[str, Any]) -> None:
    """Save orchestration to database."""
    db = get_database()
    await db.connect()
    try:
        await db.execute(
            """
            INSERT OR REPLACE INTO orchestrations
            (id, user_id, goal, notebook_id, status, current_phase, progress,
             orchestration_mode, team_id, result, error, created_at, updated_at)
            VALUES (:id, :user_id, :goal, :notebook_id, :status, :current_phase, :progress,
                    :orchestration_mode, :team_id, :result, :error, :created_at, :updated_at)
            """,
            {
                "id": orchestration_data["id"],
                "user_id": orchestration_data["user_id"],
                "goal": orchestration_data["goal"],
                "notebook_id": orchestration_data.get("notebook_id"),
                "status": orchestration_data["status"],
                "current_phase": orchestration_data.get("current_phase", "starting"),
                "progress": orchestration_data.get("progress", 0.0),
                "orchestration_mode": orchestration_data.get("orchestration_mode"),
                "team_id": orchestration_data.get("team_id"),
                "result": json.dumps(orchestration_data.get("result")) if orchestration_data.get("result") else None,
                "error": orchestration_data.get("error"),
                "created_at": orchestration_data["created_at"],
                "updated_at": orchestration_data["updated_at"]
            }
        )
    finally:
        await db.disconnect()


async def _get_orchestration(orchestration_id: str) -> Optional[Dict[str, Any]]:
    """Get orchestration from database."""
    db = get_database()
    await db.connect()
    try:
        result = await db.query(
            "SELECT * FROM orchestrations WHERE id = :id",
            {"id": orchestration_id}
        )
        if result:
            row = result[0]
            return {
                "id": row["id"],
                "user_id": row["user_id"],
                "goal": row["goal"],
                "notebook_id": row["notebook_id"],
                "status": row["status"],
                "current_phase": row["current_phase"],
                "progress": row["progress"],
                "orchestration_mode": row["orchestration_mode"],
                "team_id": row["team_id"],
                "result": json.loads(row["result"]) if row["result"] else None,
                "error": row["error"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }
        return None
    finally:
        await db.disconnect()


async def _save_event(orchestration_id: str, event_type: str, event_data: Dict[str, Any]) -> None:
    """Save event to database."""
    db = get_database()
    await db.connect()
    try:
        await db.execute(
            """
            INSERT INTO orchestration_events
            (orchestration_id, event_type, event_data, timestamp)
            VALUES (:orchestration_id, :event_type, :event_data, :timestamp)
            """,
            {
                "orchestration_id": orchestration_id,
                "event_type": event_type,
                "event_data": json.dumps(event_data),
                "timestamp": event_data.get("timestamp", datetime.utcnow().isoformat())
            }
        )
    except Exception as e:
        logger.error(f"Failed to save event {event_type} for {orchestration_id}: {e}")
        # Don't raise - we don't want to break streaming if event save fails
    finally:
        await db.disconnect()


async def _get_events(orchestration_id: str, after_timestamp: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get events from database."""
    db = get_database()
    await db.connect()
    try:
        if after_timestamp:
            results = await db.query(
                """
                SELECT event_type, event_data, timestamp
                FROM orchestration_events
                WHERE orchestration_id = :orchestration_id AND timestamp > :after
                ORDER BY timestamp ASC
                """,
                {"orchestration_id": orchestration_id, "after": after_timestamp}
            )
        else:
            results = await db.query(
                """
                SELECT event_type, event_data, timestamp
                FROM orchestration_events
                WHERE orchestration_id = :orchestration_id
                ORDER BY timestamp ASC
                """,
                {"orchestration_id": orchestration_id}
            )

        return [
            {
                "type": row["event_type"],
                "data": json.loads(row["event_data"]),
                "timestamp": row["timestamp"]
            }
            for row in results
        ]
    finally:
        await db.disconnect()


async def _emit_event(orchestration_id: str, event_type: str, event_data: Dict[str, Any]):
    """Store orchestration event in database."""
    try:
        await _save_event(orchestration_id, event_type, event_data)
    except Exception as e:
        logger.error(f"Failed to save event {event_type} for orchestration {orchestration_id}: {e}")


def _format_sse(event: str, data: Dict[str, Any]) -> str:
    """Format Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/execute", response_model=OrchestrationResponse)
async def execute_orchestration(
    request: OrchestrationRequest,
    user_id: str = Header(alias="X-User-ID", default="default-user")
) -> OrchestrationResponse:
    """
    Execute autonomous orchestration (non-streaming).

    Returns final result after completion.
    """
    logger.info(f"Starting orchestration for user {user_id}: {request.goal[:50]}...")

    try:
        # Create orchestration ID
        orchestration_id = _generate_orchestration_id()

        # Store orchestration state in database
        await _save_orchestration({
            "id": orchestration_id,
            "goal": request.goal,
            "user_id": user_id,
            "notebook_id": request.notebook_id,
            "status": "starting",
            "current_phase": "starting",
            "progress": 0.0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        })

        # Get LLM from credential store (same as agent teams)
        from api.services.settings import get_setting
        from api.routers.credentials import _credentials_store
        from api.services.context import get_llm_for_credential

        language_model_id = await get_setting("language_model_id", "")
        if not language_model_id or language_model_id not in _credentials_store:
            # Find first available language model
            for cred_id, cred in _credentials_store.items():
                if (cred.get("is_active") and
                    cred.get("model_type") == "language" and
                    cred.get("connection_status") in ["connected", "untested", None]):
                    language_model_id = cred_id
                    break

        if not language_model_id:
            raise HTTPException(
                status_code=400,
                detail="No language model configured. Please configure a model in Settings → Models."
            )

        # Get LLM instance
        llm = await get_llm_for_credential(language_model_id)
        logger.info(f"Using language model: {language_model_id}")

        # Create orchestrator with LLM
        orchestrator = AutonomousOrchestrator(llm=llm)

        # Execute orchestration
        result = await orchestrator.execute(
            goal=request.goal,
            user_id=user_id,
            notebook_id=request.notebook_id,
            resources=request.resources
        )

        # Update orchestration state in database
        await _save_orchestration({
            "id": orchestration_id,
            "user_id": user_id,
            "goal": request.goal,
            "notebook_id": request.notebook_id,
            "status": result.get("status", "completed"),
            "current_phase": result.get("status", "completed"),
            "progress": 1.0 if result.get("status") == "completed" else 0.0,
            "orchestration_mode": result.get("orchestration_mode"),
            "team_id": result.get("team_id"),
            "result": result.get("result"),
            "error": result.get("error"),
            "created_at": (await _get_orchestration(orchestration_id))["created_at"],
            "updated_at": datetime.utcnow().isoformat()
        })

        return OrchestrationResponse(
            orchestration_id=orchestration_id,
            status=result.get("status", "completed"),
            orchestration_mode=result.get("orchestration_mode"),
            team_id=result.get("team_id"),
            result=result.get("result"),
            error=result.get("error"),
            timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Orchestration failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute/stream")
async def execute_orchestration_stream(
    request: OrchestrationRequest,
    user_id: str = Header(alias="X-User-ID", default="default-user")
):
    """
    Execute autonomous orchestration with SSE streaming.

    Streams real-time events during execution.

    SSE Events:
    - orchestration.started
    - analysis.completed
    - decision.made
    - agent.spawned (real agent instances created by TeamSpawner)
    - tools.loaded
    - agent.ready
    - task.assigned
    - task.started
    - task.progress
    - task.completed
    - synthesis.started
    - orchestration.completed
    - orchestration.error

    For team/swarm modes, real agent instances are spawned using TeamSpawner
    with A2A message bus for inter-agent communication.
    """
    logger.info(f"Starting streaming orchestration for user {user_id}: {request.goal[:50]}...")
    print(f"\n{'='*80}")
    print(f"📥 ROUTER RECEIVED REQUEST")
    print(f"{'='*80}")
    print(f"  goal: {request.goal[:50]}...")
    print(f"  notebook_id: {request.notebook_id}")
    print(f"  request.resources: {request.resources}")
    print(f"  request.resources type: {type(request.resources)}")
    print(f"  request dict: {request.model_dump()}")
    print(f"{'='*80}\n")
    logger.info(f"Request details - notebook_id: {request.notebook_id}, resources: {request.resources}")

    async def event_generator():
        orchestration_id = _generate_orchestration_id()

        try:
            # Initialize orchestration state in database
            await _save_orchestration({
                "id": orchestration_id,
                "goal": request.goal,
                "user_id": user_id,
                "notebook_id": request.notebook_id,
                "status": "starting",
                "current_phase": "starting",
                "progress": 0.0,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            })

            # Emit started event
            started_event = {
                "orchestration_id": orchestration_id,
                "goal": request.goal,
                "timestamp": datetime.utcnow().isoformat()
            }
            await _save_event(orchestration_id, "orchestration.started", started_event)
            yield _format_sse("orchestration.started", started_event)

            # Get LLM from credential store (same as agent teams)
            from api.services.settings import get_setting
            from api.routers.credentials import _credentials_store
            from api.services.context import get_llm_for_credential

            language_model_id = await get_setting("language_model_id", "")
            if not language_model_id or language_model_id not in _credentials_store:
                # Find first available language model
                for cred_id, cred in _credentials_store.items():
                    if (cred.get("is_active") and
                        cred.get("model_type") == "language" and
                        cred.get("connection_status") in ["connected", "untested", None]):
                        language_model_id = cred_id
                        break

            if not language_model_id:
                yield _format_sse("orchestration.error", {
                    "orchestration_id": orchestration_id,
                    "error": "No language model configured. Please configure a model in Settings → Models.",
                    "timestamp": datetime.utcnow().isoformat()
                })
                return

            # Get LLM instance
            llm = await get_llm_for_credential(language_model_id)
            logger.info(f"Using language model: {language_model_id}")

            # Get credential details for agent creation
            credential = _credentials_store.get(language_model_id, {})
            actual_model_name = credential.get("model_name", "gpt-4")
            base_url = credential.get("base_url")
            api_key = credential.get("api_key")

            logger.info(f"Model: {actual_model_name}, Base URL: {base_url}")

            # Create orchestrator with event callback
            events_queue = asyncio.Queue()

            async def event_callback(event_type: str, data: Dict[str, Any]):
                """Callback to capture orchestration events."""
                await events_queue.put((event_type, data))

            orchestrator = AutonomousOrchestrator(
                llm=llm,
                event_callback=event_callback,
                base_url=base_url,
                api_key=api_key,
                model_name=actual_model_name
            )

            # Start orchestration in background
            orchestration_task = asyncio.create_task(
                orchestrator.execute(
                    goal=request.goal,
                    user_id=user_id,
                    notebook_id=request.notebook_id,
                    resources=request.resources
                )
            )

            # Stream events as they occur
            while not orchestration_task.done():
                try:
                    # Wait for event with timeout
                    event_type, event_data = await asyncio.wait_for(
                        events_queue.get(),
                        timeout=0.5
                    )

                    # Store event
                    await _emit_event(orchestration_id, event_type, event_data)

                    # Send SSE event
                    yield _format_sse(event_type, {
                        "orchestration_id": orchestration_id,
                        **event_data
                    })

                except asyncio.TimeoutError:
                    # No event, continue waiting
                    continue

            # Get final result
            result = await orchestration_task

            # Get initial orchestration data
            orchestration_data = await _get_orchestration(orchestration_id)

            # Update orchestration state in database
            await _save_orchestration({
                "id": orchestration_id,
                "user_id": user_id,
                "goal": request.goal,
                "notebook_id": request.notebook_id,
                "status": result.get("status", "completed"),
                "current_phase": result.get("status", "completed"),
                "progress": 1.0 if result.get("success") else 0.0,
                "orchestration_mode": result.get("orchestration_mode"),
                "team_id": result.get("team_id"),
                "result": result.get("result"),
                "error": result.get("error"),
                "created_at": orchestration_data["created_at"],
                "updated_at": datetime.utcnow().isoformat()
            })

            # Emit synthetic events based on result (for rich UI display)
            # These help the frontend show agent details, task assignments, etc.
            orchestration_mode = result.get("orchestration_mode")
            team_id = result.get("team_id")
            final_result = result.get("result")

            # Emit decision event
            if orchestration_mode:
                team_size = 1
                if orchestration_mode == "team":
                    team_size = 3
                elif orchestration_mode == "swarm":
                    team_size = 5

                decision_event = {
                    "orchestration_id": orchestration_id,
                    "orchestration_mode": orchestration_mode,
                    "team_size": team_size,
                    "reasoning": f"Based on goal complexity, selected {orchestration_mode} mode with {team_size} agent(s)",
                    "timestamp": datetime.utcnow().isoformat()
                }
                await _save_event(orchestration_id, "decision.made", decision_event)
                yield _format_sse("decision.made", decision_event)

            # Emit task events (based on final result)
            if final_result and isinstance(final_result, dict):
                task_results = final_result.get("results", [])
                for idx, task_result in enumerate(task_results):
                    task_id = task_result.get("task_id", f"task-{idx}")
                    output = task_result.get("output", "Task completed")

                    # Task assigned
                    task_assigned_event = {
                        "orchestration_id": orchestration_id,
                        "task_id": task_id,
                        "task_description": output[:100] if output else "Processing task",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    await _save_event(orchestration_id, "task.assigned", task_assigned_event)
                    yield _format_sse("task.assigned", task_assigned_event)

                    # Task completed
                    task_completed_event = {
                        "orchestration_id": orchestration_id,
                        "task_id": task_id,
                        "output": output,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    await _save_event(orchestration_id, "task.completed", task_completed_event)
                    yield _format_sse("task.completed", task_completed_event)

            # Emit completion event
            if result.get("success"):
                completion_event = {
                    "orchestration_id": orchestration_id,
                    "orchestration_mode": result.get("orchestration_mode"),
                    "team_id": result.get("team_id"),
                    "result": result.get("result"),
                    "timestamp": datetime.utcnow().isoformat()
                }
                await _save_event(orchestration_id, "orchestration.completed", completion_event)
                yield _format_sse("orchestration.completed", completion_event)
            else:
                error_event = {
                    "orchestration_id": orchestration_id,
                    "error": result.get("error"),
                    "timestamp": datetime.utcnow().isoformat()
                }
                await _save_event(orchestration_id, "orchestration.error", error_event)
                yield _format_sse("orchestration.error", error_event)

        except Exception as e:
            logger.error(f"Streaming orchestration failed: {e}", exc_info=True)

            # Update state in database
            orchestration_data = await _get_orchestration(orchestration_id)
            if orchestration_data:
                await _save_orchestration({
                    **orchestration_data,
                    "status": "failed",
                    "current_phase": "failed",
                    "error": str(e),
                    "updated_at": datetime.utcnow().isoformat()
                })

            # Emit error event
            error_event = {
                "orchestration_id": orchestration_id,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
            await _save_event(orchestration_id, "orchestration.error", error_event)
            yield _format_sse("orchestration.error", error_event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )


@router.get("/{orchestration_id}/status", response_model=OrchestrationStatus)
async def get_orchestration_status(
    orchestration_id: str,
    user_id: str = Header(alias="X-User-ID", default="default-user")
) -> OrchestrationStatus:
    """Get current status of an orchestration."""
    logger.info(f"Status request for {orchestration_id} with user_id: {user_id}")

    orchestration = await _get_orchestration(orchestration_id)

    if not orchestration:
        raise HTTPException(status_code=404, detail="Orchestration not found")

    logger.info(f"Orchestration owner: {orchestration.get('user_id')}")

    # Check ownership
    if orchestration.get("user_id") != user_id:
        logger.warning(f"Access denied: {user_id} trying to access {orchestration.get('user_id')}'s orchestration")
        raise HTTPException(status_code=403, detail="Access denied")

    return OrchestrationStatus(
        orchestration_id=orchestration_id,
        status=orchestration.get("status", "starting"),
        current_phase=orchestration.get("current_phase", "starting"),
        progress=orchestration.get("progress", 0.0),
        team_id=orchestration.get("team_id"),
        orchestration_mode=orchestration.get("orchestration_mode"),
        started_at=orchestration.get("created_at"),
        updated_at=orchestration.get("updated_at")
    )


@router.get("/{orchestration_id}/events")
async def get_orchestration_events(
    orchestration_id: str,
    user_id: str = Header(alias="X-User-ID", default="default-user"),
    after: Optional[str] = Query(None, description="Get events after this timestamp")
) -> List[Dict[str, Any]]:
    """Get events for an orchestration."""
    orchestration = await _get_orchestration(orchestration_id)

    if not orchestration:
        raise HTTPException(status_code=404, detail="Orchestration not found")

    # Check ownership
    if orchestration.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get events from database
    events = await _get_events(orchestration_id, after)
    return events


@router.get("/", response_model=List[OrchestrationListItem])
async def list_orchestrations(
    user_id: str = Header(alias="X-User-ID", default="default-user"),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status")
) -> List[OrchestrationListItem]:
    """List orchestrations for user."""
    db = get_database()
    await db.connect()
    try:
        # Build query with filters
        if status:
            query = """
                SELECT * FROM orchestrations
                WHERE user_id = :user_id AND status = :status
                ORDER BY created_at DESC
                LIMIT :limit
            """
            params = {"user_id": user_id, "status": status, "limit": limit}
        else:
            query = """
                SELECT * FROM orchestrations
                WHERE user_id = :user_id
                ORDER BY created_at DESC
                LIMIT :limit
            """
            params = {"user_id": user_id, "limit": limit}

        results = await db.query(query, params)

        # Format response
        return [
            OrchestrationListItem(
                orchestration_id=row["id"],
                goal=row["goal"],
                status=row["status"],
                orchestration_mode=row["orchestration_mode"],
                team_id=row["team_id"],
                created_at=row["created_at"]
            )
            for row in results
        ]
    finally:
        await db.disconnect()


@router.delete("/{orchestration_id}")
async def delete_orchestration(
    orchestration_id: str,
    user_id: str = Header(alias="X-User-ID", default="default-user")
) -> Dict[str, str]:
    """Delete an orchestration and its events."""
    orchestration = await _get_orchestration(orchestration_id)

    if not orchestration:
        raise HTTPException(status_code=404, detail="Orchestration not found")

    # Check ownership
    if orchestration.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Delete from database (CASCADE will delete events)
    db = get_database()
    await db.connect()
    try:
        await db.execute(
            "DELETE FROM orchestrations WHERE id = :id",
            {"id": orchestration_id}
        )
    finally:
        await db.disconnect()

    return {"message": "Orchestration deleted"}


@router.post("/{orchestration_id}/cancel")
async def cancel_orchestration(
    orchestration_id: str,
    user_id: str = Header(alias="X-User-ID", default="default-user")
) -> Dict[str, str]:
    """
    Cancel a running orchestration.

    Note: This is a placeholder. Full cancellation requires task cancellation support.
    """
    orchestration = await _get_orchestration(orchestration_id)

    if not orchestration:
        raise HTTPException(status_code=404, detail="Orchestration not found")

    # Check ownership
    if orchestration.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Check if cancellable
    if orchestration.get("status") in ["completed", "failed"]:
        raise HTTPException(status_code=400, detail="Cannot cancel completed orchestration")

    # Update status in database
    await _save_orchestration({
        **orchestration,
        "status": "cancelled",
        "current_phase": "cancelled",
        "updated_at": datetime.utcnow().isoformat()
    })

    # TODO: Implement actual task cancellation
    logger.warning(f"Cancellation requested for {orchestration_id} but not fully implemented")

    return {"message": "Orchestration cancelled (best effort)"}


@router.get("/health")
async def health() -> Dict[str, str]:
    """Health check for orchestration service."""
    return {
        "status": "healthy",
        "service": "autonomous_orchestration",
        "active_orchestrations": str(len(_orchestrations))
    }


# Scheduling Models
class ScheduleOnce(BaseModel):
    """One-time schedule."""
    type: str = Field("once", description="Schedule type")
    datetime: str = Field(..., description="ISO datetime for execution")


class ScheduleRecurring(BaseModel):
    """Recurring schedule with cron."""
    type: str = Field("recurring", description="Schedule type")
    cron: str = Field(..., description="Cron expression")


class OrchestrationScheduleRequest(BaseModel):
    """Request to schedule orchestration."""
    goal: str = Field(..., min_length=10, max_length=2000, description="User's goal")
    notebook_id: Optional[str] = Field(None, description="Notebook context")
    resources: Optional[Dict[str, Any]] = Field(None, description="Available resources")
    schedule: Dict[str, Any] = Field(..., description="Schedule configuration (once or recurring)")
    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Orchestration config")


class ScheduledOrchestrationResponse(BaseModel):
    """Response from scheduling orchestration."""
    schedule_id: str
    orchestration_config: Dict[str, Any]
    schedule_type: str
    next_run: Optional[str] = None
    cron_expression: Optional[str] = None
    status: str
    created_at: str


@router.post("/schedule", response_model=ScheduledOrchestrationResponse)
async def schedule_orchestration(
    request: OrchestrationScheduleRequest,
    x_user_id: str = Header("default", alias="X-User-ID")
) -> ScheduledOrchestrationResponse:
    """
    Schedule orchestration for future execution.

    Supports:
    - One-time execution at specific datetime
    - Recurring execution with cron expression
    """
    import uuid
    from datetime import datetime, timezone
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.date import DateTrigger

    schedule_id = str(uuid.uuid4())
    schedule_type = request.schedule.get("type")

    logger.info(f"Scheduling orchestration: {schedule_id}, type: {schedule_type}")

    # Prepare orchestration config
    orchestration_config = {
        "goal": request.goal,
        "notebook_id": request.notebook_id,
        "resources": request.resources,
        "user_id": x_user_id,
        "config": request.config or {},
    }

    # Get or create scheduler instance
    # TODO: This should be a singleton scheduler service
    # For now, we'll store schedule info in database and rely on workflow_scheduler
    from api.services.workflow_scheduler import WorkflowScheduler
    from open_notebook.database.repository import repo_execute

    try:
        # Validate and parse schedule
        if schedule_type == "once":
            scheduled_datetime_str = request.schedule.get("datetime")
            if not scheduled_datetime_str:
                raise HTTPException(status_code=400, detail="datetime required for once schedule")

            # Parse datetime and make timezone-aware (assume UTC if no timezone)
            try:
                if 'T' in scheduled_datetime_str:
                    # ISO format
                    if '+' in scheduled_datetime_str or scheduled_datetime_str.endswith('Z'):
                        # Already has timezone
                        scheduled_datetime = datetime.fromisoformat(scheduled_datetime_str.replace('Z', '+00:00'))
                    else:
                        # No timezone, assume UTC
                        scheduled_datetime = datetime.fromisoformat(scheduled_datetime_str).replace(tzinfo=timezone.utc)
                else:
                    # Just date, assume midnight UTC
                    scheduled_datetime = datetime.fromisoformat(scheduled_datetime_str).replace(tzinfo=timezone.utc)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Invalid datetime format: {str(e)}")

            # Check if in future
            if scheduled_datetime <= datetime.now(timezone.utc):
                raise HTTPException(status_code=400, detail="Scheduled time must be in the future")

            next_run = scheduled_datetime.isoformat()
            cron_expression = None

        elif schedule_type == "recurring":
            cron_expression = request.schedule.get("cron")
            if not cron_expression:
                raise HTTPException(status_code=400, detail="cron required for recurring schedule")

            # Validate cron expression
            try:
                # Parse cron to calculate next run
                parts = cron_expression.split()
                if len(parts) != 5:
                    raise ValueError("Cron must have 5 fields: minute hour day month day_of_week")

                # Create trigger to validate and get next run time
                trigger = CronTrigger.from_crontab(cron_expression)
                next_run_time = trigger.get_next_fire_time(None, datetime.now(timezone.utc))
                next_run = next_run_time.isoformat() if next_run_time else None

            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid cron expression: {str(e)}")

        else:
            raise HTTPException(status_code=400, detail=f"Invalid schedule type: {schedule_type}")

        # Save schedule to database
        await repo_execute(
            """
            INSERT INTO orchestration_schedules
            (id, user_id, goal, notebook_id, resources, config, schedule_type, schedule_config,
             next_run, status, created_at, updated_at)
            VALUES (:id, :user_id, :goal, :notebook_id, :resources, :config, :schedule_type,
                    :schedule_config, :next_run, :status, :created_at, :updated_at)
            """,
            {
                "id": schedule_id,
                "user_id": x_user_id,
                "goal": request.goal,
                "notebook_id": request.notebook_id,
                "resources": json.dumps(request.resources) if request.resources else None,
                "config": json.dumps(request.config) if request.config else None,
                "schedule_type": schedule_type,
                "schedule_config": json.dumps(request.schedule),
                "next_run": next_run,
                "status": "active",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
        )

        logger.info(f"✅ Orchestration scheduled: {schedule_id}")

        # Notify scheduler to add this schedule
        try:
            from api.services.orchestration_scheduler import get_orchestration_scheduler
            scheduler = await get_orchestration_scheduler()

            # Prepare schedule data for scheduler
            schedule_data = {
                "id": schedule_id,
                "user_id": x_user_id,
                "goal": request.goal,
                "notebook_id": request.notebook_id,
                "resources": json.dumps(request.resources) if request.resources else None,
                "config": json.dumps(request.config) if request.config else None,
                "schedule_type": schedule_type,
                "schedule_config": json.dumps(request.schedule),
                "next_run": next_run,
                "execution_count": 0
            }

            await scheduler.add_schedule(schedule_data)
            logger.info(f"🔔 Notified scheduler about new schedule {schedule_id}")
        except Exception as notify_error:
            logger.warning(f"Failed to notify scheduler: {notify_error}")
            # Don't fail the request if scheduler notification fails

        return ScheduledOrchestrationResponse(
            schedule_id=schedule_id,
            orchestration_config=orchestration_config,
            schedule_type=schedule_type,
            next_run=next_run,
            cron_expression=cron_expression if schedule_type == "recurring" else None,
            status="active",
            created_at=datetime.utcnow().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to schedule orchestration: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to schedule orchestration: {str(e)}")


@router.get("/schedules", response_model=List[Dict[str, Any]])
async def list_schedules(
    x_user_id: str = Header("default", alias="X-User-ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200)
) -> List[Dict[str, Any]]:
    """
    List orchestration schedules.

    Args:
        status: Filter by status (active, paused, completed, failed)
        limit: Maximum number of schedules to return
    """
    try:
        query = """
            SELECT id, user_id, goal, notebook_id, schedule_type, schedule_config,
                   next_run, last_run, status, execution_count, created_at, updated_at
            FROM orchestration_schedules
            WHERE user_id = :user_id
        """
        params: Dict[str, Any] = {"user_id": x_user_id}

        if status:
            query += " AND status = :status"
            params["status"] = status

        query += " ORDER BY created_at DESC LIMIT :limit"
        params["limit"] = limit

        schedules = await repo_query(query, params)

        # Parse JSON fields
        for schedule in schedules:
            if schedule.get("schedule_config"):
                schedule["schedule_config"] = json.loads(schedule["schedule_config"])
            if schedule.get("resources"):
                schedule["resources"] = json.loads(schedule["resources"])
            if schedule.get("config"):
                schedule["config"] = json.loads(schedule["config"])

        return schedules

    except Exception as e:
        logger.error(f"Failed to list schedules: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list schedules: {str(e)}")


@router.get("/schedules/{schedule_id}")
async def get_schedule(
    schedule_id: str,
    x_user_id: str = Header("default", alias="X-User-ID")
) -> Dict[str, Any]:
    """Get schedule details."""
    try:
        schedules = await repo_query(
            """
            SELECT id, user_id, goal, notebook_id, resources, config,
                   schedule_type, schedule_config, next_run, last_run,
                   status, execution_count, created_at, updated_at
            FROM orchestration_schedules
            WHERE id = :id AND user_id = :user_id
            """,
            {"id": schedule_id, "user_id": x_user_id}
        )

        if not schedules:
            raise HTTPException(status_code=404, detail="Schedule not found")

        schedule = schedules[0]

        # Parse JSON fields
        if schedule.get("schedule_config"):
            schedule["schedule_config"] = json.loads(schedule["schedule_config"])
        if schedule.get("resources"):
            schedule["resources"] = json.loads(schedule["resources"])
        if schedule.get("config"):
            schedule["config"] = json.loads(schedule["config"])

        return schedule

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get schedule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get schedule: {str(e)}")


@router.post("/schedules/{schedule_id}/pause")
async def pause_schedule(
    schedule_id: str,
    x_user_id: str = Header("default", alias="X-User-ID")
) -> Dict[str, str]:
    """Pause a recurring schedule."""
    try:
        # Verify ownership
        schedules = await repo_query(
            "SELECT user_id, status FROM orchestration_schedules WHERE id = :id",
            {"id": schedule_id}
        )

        if not schedules:
            raise HTTPException(status_code=404, detail="Schedule not found")

        if schedules[0]["user_id"] != x_user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        if schedules[0]["status"] != "active":
            raise HTTPException(status_code=400, detail="Can only pause active schedules")

        # Pause in scheduler
        from api.services.orchestration_scheduler import get_orchestration_scheduler
        scheduler = await get_orchestration_scheduler()
        await scheduler.pause_schedule(schedule_id)

        return {"message": f"Schedule {schedule_id} paused"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to pause schedule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to pause schedule: {str(e)}")


@router.post("/schedules/{schedule_id}/resume")
async def resume_schedule(
    schedule_id: str,
    x_user_id: str = Header("default", alias="X-User-ID")
) -> Dict[str, str]:
    """Resume a paused schedule."""
    try:
        # Verify ownership
        schedules = await repo_query(
            "SELECT user_id, status FROM orchestration_schedules WHERE id = :id",
            {"id": schedule_id}
        )

        if not schedules:
            raise HTTPException(status_code=404, detail="Schedule not found")

        if schedules[0]["user_id"] != x_user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        if schedules[0]["status"] != "paused":
            raise HTTPException(status_code=400, detail="Can only resume paused schedules")

        # Resume in scheduler
        from api.services.orchestration_scheduler import get_orchestration_scheduler
        scheduler = await get_orchestration_scheduler()
        await scheduler.resume_schedule(schedule_id)

        return {"message": f"Schedule {schedule_id} resumed"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume schedule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to resume schedule: {str(e)}")


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: str,
    x_user_id: str = Header("default", alias="X-User-ID")
) -> Dict[str, str]:
    """Delete a schedule."""
    try:
        # Verify ownership
        schedules = await repo_query(
            "SELECT user_id FROM orchestration_schedules WHERE id = :id",
            {"id": schedule_id}
        )

        if not schedules:
            raise HTTPException(status_code=404, detail="Schedule not found")

        if schedules[0]["user_id"] != x_user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Remove from scheduler
        from api.services.orchestration_scheduler import get_orchestration_scheduler
        scheduler = await get_orchestration_scheduler()
        await scheduler.remove_schedule(schedule_id)

        # Delete from database
        await repo_execute(
            "DELETE FROM orchestration_schedules WHERE id = :id",
            {"id": schedule_id}
        )

        return {"message": f"Schedule {schedule_id} deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete schedule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete schedule: {str(e)}")

