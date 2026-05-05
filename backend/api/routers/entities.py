"""
API router for entity operations.

Provides CRUD endpoints, search, merge, and graph queries for entities.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel

from open_notebook.domain.entity import Entity
from api.services.entity_extraction_service import EntityExtractionService
from api.services.entity_graph_service import EntityGraphService

router = APIRouter(prefix="/api/entities", tags=["entities"])


# Pydantic models
class EntityResponse(BaseModel):
    id: str
    name: str
    entity_type: str
    description: Optional[str]
    source_id: str
    chunk_id: Optional[str]
    metadata: Optional[str]
    created: Optional[str]
    updated: Optional[str]


class EntityUpdate(BaseModel):
    name: Optional[str] = None
    entity_type: Optional[str] = None
    description: Optional[str] = None


class EntityMergeRequest(BaseModel):
    target_entity_id: str


class ExtractionResponse(BaseModel):
    source_id: str
    entities_count: int
    relationships_count: int
    chunks_processed: int


# Endpoints
@router.post("/extract/{source_id}", response_model=ExtractionResponse)
async def extract_entities_from_source(
    source_id: str,
    force: bool = Query(False, description="Re-extract even if entities exist"),
    model: Optional[str] = Query(None, description="LLM model for extraction")
):
    """Extract entities and relationships from a source."""
    service = EntityExtractionService(model=model)

    try:
        result = await service.extract_entities_from_source(source_id, force=force)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.get("/", response_model=List[EntityResponse])
async def list_entities(
    source_id: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0)
):
    """List entities with optional filters."""
    if source_id:
        entities = await Entity.get_by_source(source_id, entity_type=entity_type)
    else:
        entities = await Entity.get_all()
        if entity_type:
            entities = [e for e in entities if e.entity_type == entity_type]

    # Apply pagination
    entities = entities[offset:offset + limit]

    return [EntityResponse(**e.__dict__) for e in entities]


@router.get("/search", response_model=List[EntityResponse])
async def search_entities(
    query: str = Query(..., min_length=1),
    entity_types: Optional[List[str]] = Query(None),
    source_id: Optional[str] = Query(None),
    limit: int = Query(50, le=500)
):
    """Search entities by name and description."""
    entities = await Entity.search(
        query=query,
        entity_types=entity_types,
        source_id=source_id,
        limit=limit
    )

    return [EntityResponse(**e.__dict__) for e in entities]


@router.get("/{entity_id}", response_model=EntityResponse)
async def get_entity(entity_id: str):
    """Get entity by ID."""
    entity = await Entity.get(entity_id)

    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    return EntityResponse(**entity.__dict__)


@router.put("/{entity_id}", response_model=EntityResponse)
async def update_entity(entity_id: str, update: EntityUpdate):
    """Update entity fields."""
    entity = await Entity.get(entity_id)

    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Update fields
    if update.name:
        entity.name = update.name
    if update.entity_type:
        entity.entity_type = update.entity_type
    if update.description is not None:
        entity.description = update.description

    await entity.save()

    return EntityResponse(**entity.__dict__)


@router.delete("/{entity_id}")
async def delete_entity(entity_id: str):
    """Delete entity and its relationships."""
    entity = await Entity.get(entity_id)

    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    await entity.delete()

    return {"status": "deleted", "entity_id": entity_id}


@router.get("/{entity_id}/relationships")
async def get_entity_relationships(
    entity_id: str,
    direction: str = Query("both", regex="^(outgoing|incoming|both)$"),
    min_strength: float = Query(0.0, ge=0.0, le=1.0)
):
    """Get relationships for an entity."""
    from open_notebook.domain.entity import EntityRelationship

    relationships = await EntityRelationship.get_by_entity(
        entity_id,
        direction=direction,
        min_strength=min_strength
    )

    return [
        {
            "id": r.id,
            "source_entity_id": r.source_entity_id,
            "target_entity_id": r.target_entity_id,
            "relationship_type": r.relationship_type,
            "context": r.context,
            "strength": r.strength,
            "metadata": r.metadata
        }
        for r in relationships
    ]


@router.get("/{entity_id}/neighbors")
async def get_entity_neighbors(
    entity_id: str,
    depth: int = Query(1, ge=1, le=3)
):
    """Get entity neighborhood (BFS expansion)."""
    service = EntityGraphService()

    graph = await service.get_entity_neighborhood(
        entity_id=entity_id,
        depth=depth
    )

    return graph


@router.post("/{entity_id}/merge", response_model=EntityResponse)
async def merge_entity(entity_id: str, request: EntityMergeRequest):
    """Merge this entity with another."""
    service = EntityExtractionService()

    try:
        kept_id = await service.merge_duplicate_entities(
            entity_id,
            request.target_entity_id
        )

        entity = await Entity.get(kept_id)
        return EntityResponse(**entity.__dict__)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Merge failed: {str(e)}")
