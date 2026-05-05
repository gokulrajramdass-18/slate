"""
Deep Research Router

Handles deep research mode for comprehensive autonomous research.
Uses background jobs with status tracking and notifications.
"""

import uuid
import asyncio
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from sse_starlette.sse import EventSourceResponse
import json

from api.models import (
    DeepResearchRequest,
    DeepResearchJobResponse,
    DeepResearchProgressUpdate,
    DeepResearchResult,
    DeepResearchStatusResponse,
    ResearchPhase,
    ErrorResponse
)
from open_notebook.agents.deep_research_agent import DeepResearchAgent
from open_notebook.domain.chat import ChatSession


router = APIRouter(
    prefix="/api/chat/deep-research",
    tags=["deep-research"],
    responses={404: {"model": ErrorResponse}},
)


# In-memory job storage (in production, use Redis or database)
_research_jobs: Dict[str, Dict[str, Any]] = {}


# ============================================================================
# Deep Research Endpoints
# ============================================================================

@router.post("/sessions/{session_id}/start", response_model=DeepResearchJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_deep_research(
    session_id: str,
    request: DeepResearchRequest,
    background_tasks: BackgroundTasks
):
    """
    Start a deep research job in the background.

    This endpoint:
    1. Creates a unique job ID
    2. Validates the session exists
    3. Queues the research job
    4. Returns immediately with job ID for tracking

    The user can:
    - Poll status with GET /api/chat/deep-research/jobs/{job_id}
    - Stream progress with GET /api/chat/deep-research/jobs/{job_id}/stream

    Args:
        session_id: Chat session ID
        request: Deep research request with query and options
        background_tasks: FastAPI background tasks

    Returns:
        Job information with ID for tracking
    """
    # Validate session exists
    session = await ChatSession.get(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session not found: {session_id}"
        )

    # Create job ID
    job_id = str(uuid.uuid4())

    # Initialize job tracking
    _research_jobs[job_id] = {
        "job_id": job_id,
        "session_id": session_id,
        "notebook_id": session.notebook_id,
        "query": request.message,
        "status": "queued",
        "phase": ResearchPhase.INITIALIZING,
        "progress": 0,
        "result": None,
        "error": None,
        "created_at": datetime.utcnow(),
        "started_at": None,
        "completed_at": None
    }

    # Queue background research job
    background_tasks.add_task(
        _execute_deep_research,
        job_id=job_id,
        session_id=session_id,
        notebook_id=session.notebook_id,
        query=request.message,
        max_iterations=request.max_iterations,
        search_strategies=request.search_strategies
    )

    print(f"[Deep Research] Job {job_id} queued for session {session_id}")

    return DeepResearchJobResponse(
        job_id=job_id,
        status="queued",
        estimated_time=120,  # 2 minutes estimate
        message=f"Deep research started. Track progress with job ID: {job_id}"
    )


@router.get("/jobs/{job_id}", response_model=DeepResearchStatusResponse)
async def get_research_status(job_id: str):
    """
    Get the current status of a deep research job.

    Args:
        job_id: Job ID returned from start endpoint

    Returns:
        Current job status with progress and result (if complete)
    """
    if job_id not in _research_jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research job not found: {job_id}"
        )

    job = _research_jobs[job_id]

    # Build response
    response = DeepResearchStatusResponse(
        job_id=job_id,
        status=job["status"],
        phase=job["phase"],
        progress=job["progress"],
        message=job.get("message"),
        error=job.get("error")
    )

    # If complete, include result
    if job["status"] == "complete" and job["result"]:
        response.result = DeepResearchResult(**job["result"])

    return response


@router.get("/jobs/{job_id}/stream")
async def stream_research_progress(job_id: str):
    """
    Stream real-time progress updates for a deep research job.

    Returns:
        Server-Sent Events (SSE) stream with progress updates
    """
    if job_id not in _research_jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research job not found: {job_id}"
        )

    return EventSourceResponse(_stream_progress(job_id))


async def _stream_progress(job_id: str):
    """
    Generator that streams progress updates for a research job.

    Yields:
        SSE events with progress data
    """
    job = _research_jobs.get(job_id)
    if not job:
        yield {
            "event": "error",
            "data": json.dumps({"error": "Job not found"})
        }
        return

    print(f"[Deep Research SSE] Client connected for job {job_id}")
    last_progress = -1

    # Send initial status
    yield {
        "event": "status",
        "data": json.dumps({
            "job_id": job_id,
            "status": job["status"],
            "phase": job["phase"],
            "progress": job["progress"]
        })
    }

    # Poll for updates until complete
    poll_count = 0
    while True:
        poll_count += 1
        job = _research_jobs.get(job_id)
        if not job:
            print(f"[Deep Research SSE] Job {job_id} disappeared, closing stream")
            yield {
                "event": "error",
                "data": json.dumps({"error": "Job not found"})
            }
            break

        # Send update if progress changed
        if job["progress"] != last_progress:
            print(f"[Deep Research SSE] Progress update: {job['progress']}% (phase: {job['phase']})")

            # Get agent steps if available
            agent_steps = []
            if job.get("agent"):
                agent_steps = job["agent"].agent_steps if hasattr(job["agent"], "agent_steps") else []

            yield {
                "event": "progress",
                "data": json.dumps({
                    "phase": job["phase"],
                    "progress": job["progress"],
                    "message": job.get("message", ""),
                    "agent_steps": agent_steps  # Include agent steps in progress
                })
            }
            last_progress = job["progress"]

        # Check if complete
        if job["status"] in ["complete", "failed"]:
            print(f"[Deep Research SSE] Job {job_id} finished with status: {job['status']}")
            if job["status"] == "complete":
                yield {
                    "event": "complete",
                    "data": json.dumps({
                        "job_id": job_id,
                        "final_report": job["result"]["final_report"],
                        "key_findings": job["result"]["key_findings"],
                        "citations": job["result"]["citations"],
                        "search_results_count": job["result"].get("search_results_count", 0),
                        "duration_seconds": job["result"].get("duration_seconds", 0)
                    })
                }
            else:
                yield {
                    "event": "error",
                    "data": json.dumps({"error": job["error"]})
                }
            break

        # Wait before next poll
        await asyncio.sleep(1)

        # Safety timeout after 10 minutes
        if poll_count > 600:
            print(f"[Deep Research SSE] Timeout for job {job_id}")
            yield {
                "event": "error",
                "data": json.dumps({"error": "Research timeout"})
            }
            break

    print(f"[Deep Research SSE] Stream closed for job {job_id}")


@router.delete("/jobs/{job_id}")
async def cancel_research_job(job_id: str):
    """
    Cancel a running deep research job.

    Args:
        job_id: Job ID to cancel

    Returns:
        Success response
    """
    if job_id not in _research_jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research job not found: {job_id}"
        )

    job = _research_jobs[job_id]

    if job["status"] in ["complete", "failed", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status: {job['status']}"
        )

    # Mark as cancelled
    job["status"] = "cancelled"
    job["completed_at"] = datetime.utcnow()

    print(f"[Deep Research] Job {job_id} cancelled")

    return {"success": True, "message": f"Job {job_id} cancelled"}


# ============================================================================
# Background Job Execution
# ============================================================================

async def _execute_deep_research(
    job_id: str,
    session_id: str,
    notebook_id: str,
    query: str,
    max_iterations: int,
    search_strategies: list
):
    """
    Execute deep research in the background.

    Updates job status as it progresses.

    Args:
        job_id: Unique job ID
        session_id: Chat session ID
        notebook_id: Notebook ID for context
        query: Research query
        max_iterations: Max research iterations
        search_strategies: List of search strategies to use
    """
    job = _research_jobs[job_id]
    agent = None  # Store agent reference for SSE access

    try:
        # Update status
        job["status"] = "running"
        job["started_at"] = datetime.utcnow()

        print(f"[Deep Research] Starting job {job_id}: {query}")

        # Get model from session or settings (same as regular chat)
        from api.services.settings import get_setting
        from api.routers.credentials import _credentials_store

        session = await ChatSession.get(session_id)
        language_model_id = await get_setting("language_model_id", "")
        model_id = session.model_override if session and session.model_override else language_model_id

        if not model_id:
            raise ValueError(
                "No AI model configured. Please:\n"
                "1. Go to Settings → Models in the UI\n"
                "2. Configure a language model (OpenAI, Anthropic, or localhost proxy)\n"
                "3. Try deep research again"
            )

        credential = _credentials_store.get(model_id)
        if not credential:
            raise ValueError(f"Model credential not found: {model_id}")

        model_name = credential["model_name"]
        base_url = credential.get("base_url", "https://api.openai.com/v1")
        api_key = credential["api_key"]

        print(f"[Deep Research] Using model: {model_name} via {base_url}")

        # Create progress callback to update job state
        def update_progress(phase, progress, message=""):
            job["phase"] = phase
            job["progress"] = progress
            job["message"] = message
            print(f"[Deep Research] Progress: {progress}% - {phase} - {message}")

        # Create agent with credentials and progress callback
        agent = DeepResearchAgent(
            model_name=model_name,
            notebook_id=notebook_id,
            session_id=session_id,
            max_iterations=max_iterations,
            search_strategies=search_strategies,
            base_url=base_url,
            api_key=api_key,
            progress_callback=update_progress
        )

        # Store agent reference in job for SSE access to agent_steps
        job["agent"] = agent

        print(f"[Deep Research] Agent created, starting research...")

        # Execute research with progress updates to job
        try:
            final_state = await agent.research_non_streaming(query)
        except Exception as research_error:
            print(f"[Deep Research] Research execution failed: {research_error}")
            raise

        print(f"[Deep Research] Research complete, final phase: {final_state.get('phase')}")

        # Update job with progress during research
        job["phase"] = final_state.get("phase", ResearchPhase.COMPLETE)
        job["progress"] = final_state.get("progress", 100)

        # Check for errors
        if final_state.get("phase") == ResearchPhase.ERROR:
            raise Exception(final_state.get("error", "Unknown error"))

        # Store result
        duration = (datetime.utcnow() - job["started_at"]).total_seconds()

        job["result"] = {
            "job_id": job_id,
            "status": "complete",
            "phase": final_state.get("phase"),
            "final_report": final_state.get("final_report", ""),
            "key_findings": final_state.get("key_findings", []),
            "citations": final_state.get("citations", []),
            "search_results_count": sum(len(v) for v in final_state.get("search_results", {}).values()),
            "sub_questions_count": len(final_state.get("sub_questions", [])),
            "duration_seconds": duration,
            "created_at": job["created_at"],
            "agent_steps": agent.agent_steps  # Include agent steps
        }

        job["status"] = "complete"
        job["phase"] = ResearchPhase.COMPLETE
        job["progress"] = 100
        job["completed_at"] = datetime.utcnow()

        # Save research report as assistant message with agent steps
        if session:
            await session.add_message(
                "assistant",
                f"# Deep Research Complete\n\n{final_state.get('final_report', '')}",
                agent_steps=agent.agent_steps  # Include agent steps in message
            )

        print(f"[Deep Research] ✓ Job {job_id} complete ({duration:.1f}s)")

    except Exception as e:
        print(f"[Deep Research] ✗ Job {job_id} failed: {e}")
        import traceback
        traceback.print_exc()

        job["status"] = "failed"
        job["phase"] = ResearchPhase.ERROR
        job["error"] = str(e)
        job["completed_at"] = datetime.utcnow()


# ============================================================================
# Job Cleanup (optional)
# ============================================================================

@router.post("/jobs/cleanup")
async def cleanup_old_jobs(max_age_hours: int = 24):
    """
    Clean up old completed/failed research jobs.

    Args:
        max_age_hours: Delete jobs older than this many hours

    Returns:
        Number of jobs deleted
    """
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    deleted = 0

    jobs_to_delete = []
    for job_id, job in _research_jobs.items():
        completed_at = job.get("completed_at")
        if completed_at and completed_at < cutoff:
            if job["status"] in ["complete", "failed", "cancelled"]:
                jobs_to_delete.append(job_id)

    for job_id in jobs_to_delete:
        del _research_jobs[job_id]
        deleted += 1

    print(f"[Deep Research] Cleaned up {deleted} old jobs")

    return {
        "success": True,
        "message": f"Deleted {deleted} old jobs",
        "deleted_count": deleted
    }
