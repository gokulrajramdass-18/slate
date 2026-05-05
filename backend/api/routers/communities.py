"""
API router for community operations.

Provides community detection, management, and hierarchical queries.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from open_notebook.domain.entity import Community
from api.services.community_detection_service import CommunityDetectionService

router = APIRouter(prefix="/api/communities", tags=["communities"])


# Pydantic models
class CommunityResponse(BaseModel):
    id: str
    name: Optional[str]
    description: Optional[str]
    level: int
    parent_community_id: Optional[str]
    entity_ids: str  # JSON array
    metadata: Optional[str]
    created: Optional[str]
    updated: Optional[str]


class CommunityUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class DetectCommunitiesRequest(BaseModel):
    source_id: Optional[str] = None
    notebook_id: Optional[str] = None
    generate_summaries: bool = True
    resolution: float = 1.0
    min_community_size: int = 3


class DetectCommunitiesResponse(BaseModel):
    communities_count: int
    community_ids: List[str]


# Endpoints
@router.post("/detect", response_model=DetectCommunitiesResponse)
async def detect_communities(request: DetectCommunitiesRequest):
    """Run community detection on entity graph."""
    service = CommunityDetectionService(
        resolution=request.resolution,
        min_community_size=request.min_community_size
    )

    try:
        # Detect communities
        communities = await service.detect_communities(
            source_id=request.source_id,
            notebook_id=request.notebook_id
        )

        # Save to database
        community_ids = await service.save_communities(
            communities,
            generate_summaries=request.generate_summaries
        )

        return DetectCommunitiesResponse(
            communities_count=len(community_ids),
            community_ids=community_ids
        )

    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Community detection failed: {str(e)}")


@router.get("/", response_model=List[CommunityResponse])
async def list_communities(
    level: Optional[int] = Query(None, ge=0),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0)
):
    """List communities with optional filters."""
    communities = await Community.get_all()

    if level is not None:
        communities = [c for c in communities if c.level == level]

    # Apply pagination
    communities = communities[offset:offset + limit]

    return [CommunityResponse(**c.__dict__) for c in communities]


@router.get("/hierarchy")
async def get_hierarchy(max_level: Optional[int] = Query(None, ge=0)):
    """Get hierarchical community structure."""
    hierarchy = await Community.get_hierarchical(max_level=max_level)

    result = {}
    for level, communities in hierarchy.items():
        result[str(level)] = [
            {
                "id": c.id,
                "name": c.name,
                "entity_count": len(json.loads(c.entity_ids)) if c.entity_ids else 0
            }
            for c in communities
        ]

    return result


@router.get("/{community_id}", response_model=CommunityResponse)
async def get_community(community_id: str):
    """Get community by ID."""
    community = await Community.get(community_id)

    if not community:
        raise HTTPException(status_code=404, detail="Community not found")

    return CommunityResponse(**community.__dict__)


@router.put("/{community_id}", response_model=CommunityResponse)
async def update_community(community_id: str, update: CommunityUpdate):
    """Update community fields."""
    community = await Community.get(community_id)

    if not community:
        raise HTTPException(status_code=404, detail="Community not found")

    # Update fields
    if update.name:
        community.name = update.name
    if update.description is not None:
        community.description = update.description

    await community.save()

    return CommunityResponse(**community.__dict__)


@router.delete("/{community_id}")
async def delete_community(community_id: str):
    """Delete community."""
    community = await Community.get(community_id)

    if not community:
        raise HTTPException(status_code=404, detail="Community not found")

    await community.delete()

    return {"status": "deleted", "community_id": community_id}


@router.get("/{community_id}/entities")
async def get_community_entities(community_id: str):
    """Get all entities in a community."""
    entities = await Community.get_entities(community_id)

    return [
        {
            "id": e.id,
            "name": e.name,
            "entity_type": e.entity_type,
            "description": e.description
        }
        for e in entities
    ]


@router.post("/{community_id}/regenerate-summary")
async def regenerate_community_summary(community_id: str, model: Optional[str] = Query(None)):
    """Regenerate LLM summary for a community."""
    service = CommunityDetectionService(model=model)

    try:
        summary = await service.generate_community_summary(community_id)

        # Update community
        community = await Community.get(community_id)
        if not community:
            raise HTTPException(status_code=404, detail="Community not found")

        community.name = summary["name"]
        community.description = summary["description"]
        await community.save()

        return {
            "community_id": community_id,
            "name": summary["name"],
            "description": summary["description"],
            "central_entities": summary["central_entities"]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summary generation failed: {str(e)}")


import json
