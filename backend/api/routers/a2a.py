"""
A2A Protocol API Router

Exposes A2A-compliant endpoints for agent-to-agent communication.
"""

import logging
import os
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from open_notebook.agents.a2a.agent_card import generate_agent_card_json
from open_notebook.agents.a2a.message_handler import A2AMessageHandler
from open_notebook.agents.a2a.task_manager import A2ATaskManager

# Import A2A types
try:
    from a2a.types import MessageSendRequest, MessageStreamRequest
    A2A_SDK_AVAILABLE = True
except ImportError:
    A2A_SDK_AVAILABLE = False
    MessageSendRequest = dict  # type: ignore
    MessageStreamRequest = dict  # type: ignore


logger = logging.getLogger(__name__)

router = APIRouter(tags=["a2a"])


# ============================================================================
# Well-Known AgentCard Endpoint
# ============================================================================

@router.get("/.well-known/agent-card.json")
async def get_agent_card():
    """
    Serve AgentCard at well-known URL for A2A discovery.

    Returns system-level agent card. For multi-agent discovery,
    see /.well-known/agent-directory.json
    """
    try:
        from open_notebook.database.repository import repo_query

        card_json = generate_agent_card_json()

        # Add link to agent directory
        base_url = os.getenv("API_BASE_URL") or "http://localhost:5055"
        card_json["agentDirectory"] = f"{base_url}/.well-known/agent-directory.json"

        # Add agents array for multi-agent discovery (custom extension)
        try:
            agents_rows = await repo_query(
                """
                SELECT id, name, description, role, status
                FROM standalone_agents
                WHERE status = :status
                ORDER BY created DESC
                """,
                {"status": "active"}
            )

            card_json["agents"] = [
                {
                    "id": agent["id"],
                    "name": agent["name"],
                    "role": agent["role"],
                    "description": agent["description"],
                    "agentCardUrl": f"{base_url}/.well-known/agents/{agent['id']}/agent-card.json",
                }
                for agent in agents_rows
            ]
        except Exception as e:
            logger.warning(f"Could not add agents array: {e}")
            card_json["agents"] = []

        return JSONResponse(content=card_json)
    except Exception as e:
        logger.error(f"Error generating AgentCard: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate AgentCard")


@router.get("/.well-known/agent-directory.json")
async def get_agent_directory():
    """
    Serve agent directory for multi-agent discovery.

    Returns list of all available agents with links to their cards.
    """
    try:
        from open_notebook.database.repository import repo_query

        # Get all active standalone agents directly from database
        agents_rows = await repo_query(
            """
            SELECT id, name, description, role, status
            FROM standalone_agents
            WHERE status = :status
            ORDER BY created DESC
            """,
            {"status": "active"}
        )

        base_url = os.getenv("API_BASE_URL") or "http://localhost:5055"

        # Build directory
        directory = {
            "name": "Open Notebook Agent System",
            "version": "1.0.0",
            "description": "Multi-agent system with specialized agents",
            "agents": [
                {
                    "id": agent["id"],
                    "name": agent["name"],
                    "role": agent["role"],
                    "description": agent["description"],
                    "status": agent["status"],
                    "agentCardUrl": f"{base_url}/.well-known/agents/{agent['id']}/agent-card.json",
                }
                for agent in agents_rows
            ],
            "systemAgentUrl": f"{base_url}/.well-known/agent-card.json",
        }

        return JSONResponse(content=directory)

    except Exception as e:
        logger.error(f"Error generating agent directory: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate directory")


@router.get("/.well-known/agents/{agent_id}/agent-card.json")
async def get_standalone_agent_card(agent_id: str):
    """
    Serve A2A agent card for a specific standalone agent.

    Each agent gets its own A2A-compliant agent card with:
    - Agent-specific identity (name, role, description)
    - Skills filtered by agent role
    - Dedicated message endpoints
    """
    try:
        from api.routers.standalone_agents import get_standalone_agent

        # Get agent details
        try:
            agent = await get_standalone_agent(agent_id)
        except HTTPException:
            raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

        # Generate agent-specific card
        card_json = generate_agent_card_json(
            agent_id=agent_id,
            agent_name=agent.name,
            role=agent.role,
        )

        # Customize endpoints for this agent
        base_url = os.getenv("API_BASE_URL") or "http://localhost:5055"
        card_json["url"] = f"{base_url}/api/a2a/agents/{agent_id}/message/send"

        # Update streaming interface
        if "additionalInterfaces" in card_json:
            card_json["additionalInterfaces"][0]["url"] = \
                f"{base_url}/api/a2a/agents/{agent_id}/message/stream"

        # Add agent metadata
        card_json["agentId"] = agent_id
        card_json["role"] = agent.role
        card_json["description"] = agent.description or card_json.get("description")

        return JSONResponse(content=card_json)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating agent card for {agent_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate agent card")


# ============================================================================
# A2A Message Endpoints
# ============================================================================

@router.post("/api/a2a/message/send")
async def message_send(request: Dict[str, Any]):
    """
    Synchronous message endpoint (A2A protocol).

    Accepts an A2A MessageSendRequest and returns a MessageSendResponse.
    """
    if not A2A_SDK_AVAILABLE:
        raise HTTPException(
            status_code=500,
            detail="A2A SDK not available. Install with: pip install a2a-sdk[http-server]"
        )

    try:
        # Parse request
        a2a_request = MessageSendRequest.model_validate(request)

        # Handle message
        handler = A2AMessageHandler()
        response = await handler.handle_message_send(a2a_request)

        # Return response
        return JSONResponse(content=response.model_dump(mode="json", exclude_none=True))

    except Exception as e:
        logger.error(f"Error in message/send: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/a2a/message/stream")
async def message_stream(request: Dict[str, Any]):
    """
    Streaming message endpoint (A2A protocol with SSE).

    Accepts an A2A MessageStreamRequest and returns Server-Sent Events.
    """
    if not A2A_SDK_AVAILABLE:
        raise HTTPException(
            status_code=500,
            detail="A2A SDK not available"
        )

    try:
        # Parse request
        a2a_request = MessageStreamRequest.model_validate(request)

        # Handle message with streaming
        handler = A2AMessageHandler()
        event_stream = handler.handle_message_stream(a2a_request)

        # Return SSE stream
        return StreamingResponse(
            event_stream,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            }
        )

    except Exception as e:
        logger.error(f"Error in message/stream: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Per-Agent Message Endpoints
# ============================================================================

@router.post("/api/a2a/agents/{agent_id}/message/send")
async def agent_message_send(agent_id: str, request: Dict[str, Any]):
    """
    Message endpoint for specific standalone agent.

    Routes messages to the specified agent with its context.
    """
    if not A2A_SDK_AVAILABLE:
        raise HTTPException(status_code=500, detail="A2A SDK not available")

    try:
        # Verify agent exists
        from api.routers.standalone_agents import get_standalone_agent
        agent = await get_standalone_agent(agent_id)

        # Parse A2A request
        a2a_request = MessageSendRequest.model_validate(request)

        # Add agent context
        if not a2a_request.metadata:
            a2a_request.metadata = {}
        a2a_request.metadata["agent_id"] = agent_id
        a2a_request.metadata["agent_name"] = agent.name
        a2a_request.metadata["agent_role"] = agent.role

        # Handle message with agent-specific handler
        handler = A2AMessageHandler()
        response = await handler.handle_message_send(a2a_request)

        return JSONResponse(content=response.model_dump(mode="json", exclude_none=True))

    except Exception as e:
        logger.error(f"Error in agent message/send for {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/a2a/agents/{agent_id}/message/stream")
async def agent_message_stream(agent_id: str, request: Dict[str, Any]):
    """
    Streaming message endpoint for specific standalone agent.
    """
    if not A2A_SDK_AVAILABLE:
        raise HTTPException(status_code=500, detail="A2A SDK not available")

    try:
        # Verify agent exists
        from api.routers.standalone_agents import get_standalone_agent
        agent = await get_standalone_agent(agent_id)

        # Parse A2A request
        a2a_request = MessageStreamRequest.model_validate(request)

        # Add agent context
        if not a2a_request.metadata:
            a2a_request.metadata = {}
        a2a_request.metadata["agent_id"] = agent_id
        a2a_request.metadata["agent_name"] = agent.name
        a2a_request.metadata["agent_role"] = agent.role

        # Handle message with streaming
        handler = A2AMessageHandler()
        event_stream = handler.handle_message_stream(a2a_request)

        return StreamingResponse(
            event_stream,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            }
        )

    except Exception as e:
        logger.error(f"Error in agent message/stream for {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Task Status Endpoints
# ============================================================================

@router.get("/api/a2a/task/{task_id}")
async def get_task(task_id: str):
    """
    Get task status (A2A protocol).

    Returns the current status and results of a task.
    """
    task_manager = A2ATaskManager()
    task = await task_manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return JSONResponse(content={
        "taskId": task.id,
        "contextId": task.context_id,
        "status": {
            "state": task.state,
            "progress": task.progress,
            "message": task.message,
        },
        "artifacts": task.get_artifacts(),
        "history": task.get_history(),
        "startedAt": task.started_at,
        "completedAt": task.completed_at,
    })


@router.post("/api/a2a/task/{task_id}/cancel")
async def cancel_task(task_id: str):
    """
    Cancel a running task.

    Returns success if task was canceled.
    """
    task_manager = A2ATaskManager()
    success = await task_manager.cancel_task(task_id)

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Task not found or already completed"
        )

    return JSONResponse(content={"status": "canceled", "taskId": task_id})


# ============================================================================
# Health Check
# ============================================================================

@router.get("/api/a2a/health")
async def health_check():
    """Health check endpoint for A2A server."""
    return JSONResponse(content={
        "status": "healthy",
        "a2a_version": "0.3",
        "sdk_available": A2A_SDK_AVAILABLE,
    })
