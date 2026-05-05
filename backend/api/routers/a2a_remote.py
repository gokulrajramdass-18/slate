"""
A2A Remote Agent Management API

Endpoints for discovering, importing, and managing remote A2A agents.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from open_notebook.agents.a2a.discovery import A2ADiscoveryClient
from open_notebook.domain.a2a import A2ARemoteAgent, A2ASkillMapping, A2AExecutionMetric

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/a2a/remote-agents", tags=["a2a-remote"])


# ============================================================================
# Request/Response Models
# ============================================================================

class DiscoverAgentRequest(BaseModel):
    """Request to discover remote agent."""
    card_url: str


class DiscoverAgentResponse(BaseModel):
    """Response with AgentCard."""
    card: dict
    name: str
    skills_count: int


class ImportAgentRequest(BaseModel):
    """Request to import remote agent."""
    card_url: str
    name: Optional[str] = None
    enabled: bool = True


class ImportAgentResponse(BaseModel):
    """Response after importing agent."""
    agent_id: str
    agent_name: str
    skills_imported: int


class RemoteAgentSummary(BaseModel):
    """Summary of remote agent."""
    id: str
    name: str
    card_url: str
    endpoint_url: str
    transport: str
    skills_count: int
    enabled: bool
    last_synced: Optional[str]
    created: str


class RemoteAgentDetail(RemoteAgentSummary):
    """Detailed remote agent info."""
    agent_card: dict
    security_schemes: Optional[dict]
    available_skills: List[str]
    metadata: dict


class RemoteAgentStats(BaseModel):
    """Agent performance statistics."""
    total_executions: int
    successful_executions: int
    failed_executions: int
    success_rate: float
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float


# ============================================================================
# Discovery Endpoints
# ============================================================================

@router.post("/discover", response_model=DiscoverAgentResponse)
async def discover_remote_agent(request: DiscoverAgentRequest):
    """
    Discover remote A2A agent by card URL.

    Fetches AgentCard without importing the agent.
    """
    try:
        client = A2ADiscoveryClient()
        card = await client.discover_agent(request.card_url)

        return DiscoverAgentResponse(
            card=card.model_dump(mode="json", exclude_none=True),
            name=card.name,
            skills_count=len(card.skills or []),
        )

    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/import", response_model=ImportAgentResponse)
async def import_remote_agent(request: ImportAgentRequest):
    """
    Import remote A2A agent as local skills.

    Creates agent record and registers all skills.
    """
    try:
        client = A2ADiscoveryClient()
        agent = await client.import_agent(
            card_url=request.card_url,
            name=request.name,
            enabled=request.enabled,
        )

        skills_count = len(agent.get_available_skills())

        return ImportAgentResponse(
            agent_id=agent.id,
            agent_name=agent.name,
            skills_imported=skills_count,
        )

    except Exception as e:
        logger.error(f"Import failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Agent Management
# ============================================================================

@router.get("", response_model=List[RemoteAgentSummary])
async def list_remote_agents(
    enabled_only: bool = Query(False, description="Only return enabled agents"),
):
    """List all imported remote agents."""
    try:
        client = A2ADiscoveryClient()
        agents = await client.list_agents(enabled_only=enabled_only)

        return [
            RemoteAgentSummary(
                id=agent.id,
                name=agent.name,
                card_url=agent.card_url,
                endpoint_url=agent.endpoint_url,
                transport=agent.transport,
                skills_count=len(agent.get_available_skills()),
                enabled=agent.enabled,
                last_synced=agent.last_synced,
                created=agent.created,
            )
            for agent in agents
        ]

    except Exception as e:
        logger.error(f"List agents failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{agent_id}", response_model=RemoteAgentDetail)
async def get_remote_agent(agent_id: str):
    """Get detailed information about a remote agent."""
    agent = await A2ARemoteAgent.get(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return RemoteAgentDetail(
        id=agent.id,
        name=agent.name,
        card_url=agent.card_url,
        endpoint_url=agent.endpoint_url,
        transport=agent.transport,
        skills_count=len(agent.get_available_skills()),
        enabled=agent.enabled,
        last_synced=agent.last_synced,
        created=agent.created,
        agent_card=agent.get_agent_card(),
        security_schemes=agent.get_security_schemes(),
        available_skills=agent.get_available_skills(),
        metadata=agent.get_metadata(),
    )


@router.put("/{agent_id}/enable")
async def enable_remote_agent(agent_id: str):
    """Enable a remote agent."""
    agent = await A2ARemoteAgent.get(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.enabled = True
    await agent.save()

    return JSONResponse(content={"status": "enabled", "agent_id": agent_id})


@router.put("/{agent_id}/disable")
async def disable_remote_agent(agent_id: str):
    """Disable a remote agent."""
    agent = await A2ARemoteAgent.get(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.enabled = False
    await agent.save()

    return JSONResponse(content={"status": "disabled", "agent_id": agent_id})


@router.delete("/{agent_id}")
async def remove_remote_agent(agent_id: str):
    """Remove remote agent and its skill bindings."""
    try:
        client = A2ADiscoveryClient()
        success = await client.remove_agent(agent_id)

        if not success:
            raise HTTPException(status_code=404, detail="Agent not found")

        return JSONResponse(content={"status": "deleted", "agent_id": agent_id})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Remove agent failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_id}/sync")
async def sync_remote_agent(agent_id: str):
    """Re-fetch AgentCard and update skills."""
    try:
        client = A2ADiscoveryClient()
        agent = await client.sync_agent(agent_id)

        skills_count = len(agent.get_available_skills())

        return JSONResponse(content={
            "status": "synced",
            "agent_id": agent_id,
            "skills_count": skills_count,
            "last_synced": agent.last_synced,
        })

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Sync agent failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Skills Endpoints
# ============================================================================

@router.get("/{agent_id}/skills")
async def get_agent_skills(agent_id: str):
    """Get skills for a remote agent."""
    agent = await A2ARemoteAgent.get(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Get skill mappings
    mappings = await A2ASkillMapping.get_by_remote_agent(agent_id)

    return JSONResponse(content={
        "agent_id": agent_id,
        "agent_name": agent.name,
        "skills": [
            {
                "id": mapping.local_skill_id,
                "remote_id": mapping.remote_skill_id,
                "name": mapping.skill_name,
                "description": mapping.skill_description,
                "tags": mapping.get_skill_tags(),
                "enabled": mapping.enabled,
            }
            for mapping in mappings
        ],
    })


# ============================================================================
# Statistics Endpoints
# ============================================================================

@router.get("/{agent_id}/stats", response_model=RemoteAgentStats)
async def get_agent_stats(
    agent_id: str,
    days: int = Query(7, description="Number of days to include", ge=1, le=90),
):
    """Get performance statistics for a remote agent."""
    agent = await A2ARemoteAgent.get(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    stats = await A2AExecutionMetric.get_agent_stats(agent_id, days=days)

    return RemoteAgentStats(**stats)


# ============================================================================
# Health Check
# ============================================================================

@router.get("/health")
async def remote_agents_health():
    """Health check for remote agents system."""
    try:
        # Count agents
        agents = await A2ARemoteAgent.get_all()
        enabled_agents = [a for a in agents if a.enabled]

        return JSONResponse(content={
            "status": "healthy",
            "total_agents": len(agents),
            "enabled_agents": len(enabled_agents),
        })

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "unhealthy", "error": str(e)},
        )
