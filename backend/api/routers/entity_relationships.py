"""
API router for entity relationship operations.

Provides CRUD endpoints and path-finding for relationships.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel

from open_notebook.domain.entity import EntityRelationship

router = APIRouter(prefix="/api/entity-relationships", tags=["entity-relationships"])


# Pydantic models
class RelationshipResponse(BaseModel):
    id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    context: Optional[str]
    chunk_id: Optional[str]
    strength: float
    metadata: Optional[str]
    created: Optional[str]


class RelationshipCreate(BaseModel):
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    context: Optional[str] = None
    strength: float = 0.5


class RelationshipUpdate(BaseModel):
    relationship_type: Optional[str] = None
    context: Optional[str] = None
    strength: Optional[float] = None


# Endpoints
@router.get("/", response_model=List[RelationshipResponse])
async def list_relationships(
    entity_id: Optional[str] = Query(None),
    relationship_type: Optional[str] = Query(None),
    min_strength: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0)
):
    """List relationships with optional filters."""
    if entity_id:
        relationships = await EntityRelationship.get_by_entity(
            entity_id,
            direction="both",
            relationship_types=[relationship_type] if relationship_type else None,
            min_strength=min_strength
        )
    else:
        relationships = await EntityRelationship.get_all()

        if relationship_type:
            relationships = [r for r in relationships if r.relationship_type == relationship_type]
        if min_strength > 0:
            relationships = [r for r in relationships if r.strength >= min_strength]

    # Apply pagination
    relationships = relationships[offset:offset + limit]

    return [RelationshipResponse(**r.__dict__) for r in relationships]


@router.get("/types")
async def get_relationship_types():
    """Get all unique relationship types."""
    types = await EntityRelationship.get_all_types()
    return {"relationship_types": types}


@router.get("/{relationship_id}", response_model=RelationshipResponse)
async def get_relationship(relationship_id: str):
    """Get relationship by ID."""
    relationship = await EntityRelationship.get(relationship_id)

    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")

    return RelationshipResponse(**relationship.__dict__)


@router.post("/", response_model=RelationshipResponse)
async def create_relationship(relationship: RelationshipCreate):
    """Create a new relationship (manual)."""
    import uuid
    from open_notebook.config import get_database

    db = get_database()

    relationship_id = str(uuid.uuid4())

    try:
        await db.query(
            """
            INSERT INTO entity_relationships (id, source_entity_id, target_entity_id, relationship_type, context, strength, created)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            [
                relationship_id,
                relationship.source_entity_id,
                relationship.target_entity_id,
                relationship.relationship_type,
                relationship.context,
                relationship.strength
            ]
        )

        created = await EntityRelationship.get(relationship_id)
        return RelationshipResponse(**created.__dict__)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create relationship: {str(e)}")


@router.put("/{relationship_id}", response_model=RelationshipResponse)
async def update_relationship(relationship_id: str, update: RelationshipUpdate):
    """Update relationship fields."""
    relationship = await EntityRelationship.get(relationship_id)

    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")

    # Update fields
    if update.relationship_type:
        relationship.relationship_type = update.relationship_type
    if update.context is not None:
        relationship.context = update.context
    if update.strength is not None:
        relationship.strength = update.strength

    await relationship.save()

    return RelationshipResponse(**relationship.__dict__)


@router.delete("/{relationship_id}")
async def delete_relationship(relationship_id: str):
    """Delete relationship."""
    relationship = await EntityRelationship.get(relationship_id)

    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")

    await relationship.delete()

    return {"status": "deleted", "relationship_id": relationship_id}


@router.get("/path/find")
async def find_path(
    source_entity_id: str = Query(...),
    target_entity_id: str = Query(...),
    max_depth: int = Query(5, ge=1, le=10)
):
    """Find shortest path between two entities."""
    from api.services.entity_graph_service import EntityGraphService

    service = EntityGraphService()

    graph = await service.get_entity_path(
        source_entity_id=source_entity_id,
        target_entity_id=target_entity_id,
        max_depth=max_depth
    )

    if not graph['metadata']['path_found']:
        raise HTTPException(status_code=404, detail="No path found between entities")

    return graph
