"""
Agent Memory API Router

CRUD and search endpoints for agent memory entries scoped to notebooks.
Supports semantic search (keyword-based fallback when embeddings unavailable).
"""

import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from api.models import (
    MemoryEntryCreate,
    MemoryEntryUpdate,
    MemoryEntryResponse,
    MemoryListResponse,
    MemorySearchRequest,
    MemorySearchResponse,
    SuccessResponse,
    ErrorResponse,
)
from open_notebook.database.repository import repo_query, repo_execute, repo_update, repo_delete


router = APIRouter(
    prefix="/api/memory",
    tags=["agent-memory"],
    responses={404: {"model": ErrorResponse}},
)


# ============================================================================
# Helper Functions
# ============================================================================

def _parse_json(value):
    """Parse a JSON string field if needed."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None
    return value


def _row_to_memory_response(row: dict) -> MemoryEntryResponse:
    """Convert a DB row to MemoryEntryResponse."""
    return MemoryEntryResponse(
        id=row["id"],
        notebook_id=row["notebook_id"],
        memory_type=row["memory_type"],
        content=row["content"],
        metadata=_parse_json(row.get("metadata")),
        tags=_parse_json(row.get("tags")),
        created=row.get("created"),
        updated=row.get("updated"),
    )


async def _verify_notebook(notebook_id: str):
    """Verify a notebook exists or raise 404."""
    rows = await repo_query(
        "SELECT id FROM notebooks WHERE id = :id",
        {"id": notebook_id},
    )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notebook not found: {notebook_id}",
        )


# ============================================================================
# Memory CRUD Endpoints
# ============================================================================

@router.post(
    "/{notebook_id}",
    response_model=MemoryEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_memory(notebook_id: str, body: MemoryEntryCreate):
    """
    Create a new memory entry for a notebook.

    Memory entries represent facts, preferences, context, conversation history,
    or insights that agents can recall during future interactions.

    Example:
        POST /api/memory/nb-123
        {
            "memory_type": "fact",
            "content": "User prefers concise answers with code examples.",
            "tags": ["preference", "formatting"]
        }
    """
    await _verify_notebook(notebook_id)

    now = datetime.utcnow().isoformat()
    entry_id = str(uuid.uuid4())

    data = {
        "id": entry_id,
        "notebook_id": notebook_id,
        "memory_type": body.memory_type.value,
        "content": body.content,
        "metadata": json.dumps(body.metadata) if body.metadata else None,
        "tags": json.dumps(body.tags) if body.tags else None,
        "created": now,
        "updated": now,
    }

    await repo_execute(
        """INSERT INTO agent_memory (id, notebook_id, memory_type, content, metadata, tags, created, updated)
           VALUES (:id, :notebook_id, :memory_type, :content, :metadata, :tags, :created, :updated)""",
        data,
    )

    return MemoryEntryResponse(
        id=entry_id,
        notebook_id=notebook_id,
        memory_type=body.memory_type.value,
        content=body.content,
        metadata=body.metadata,
        tags=body.tags,
        created=now,
        updated=now,
    )


@router.get("/{notebook_id}", response_model=MemoryListResponse)
async def list_memories(
    notebook_id: str,
    memory_type: Optional[str] = Query(None, description="Filter by memory type"),
    limit: int = Query(50, ge=1, le=200, description="Maximum entries to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    List memory entries for a notebook.

    Example:
        GET /api/memory/nb-123?memory_type=fact&limit=20
    """
    await _verify_notebook(notebook_id)

    sql = "SELECT * FROM agent_memory WHERE notebook_id = :notebook_id"
    params: dict = {"notebook_id": notebook_id}

    if memory_type:
        sql += " AND memory_type = :memory_type"
        params["memory_type"] = memory_type

    # Get total count
    count_sql = sql.replace("SELECT *", "SELECT COUNT(*) as count")
    count_rows = await repo_query(count_sql, params)
    total = count_rows[0]["count"] if count_rows else 0

    sql += " ORDER BY updated DESC LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset

    rows = await repo_query(sql, params)
    entries = [_row_to_memory_response(r) for r in rows]

    return MemoryListResponse(entries=entries, total=total)


@router.get("/{notebook_id}/{entry_id}", response_model=MemoryEntryResponse)
async def get_memory(notebook_id: str, entry_id: str):
    """
    Get a specific memory entry.

    Example:
        GET /api/memory/nb-123/entry-456
    """
    rows = await repo_query(
        "SELECT * FROM agent_memory WHERE id = :id AND notebook_id = :notebook_id",
        {"id": entry_id, "notebook_id": notebook_id},
    )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory entry not found: {entry_id}",
        )

    return _row_to_memory_response(rows[0])


@router.put("/{notebook_id}/{entry_id}", response_model=MemoryEntryResponse)
async def update_memory(notebook_id: str, entry_id: str, body: MemoryEntryUpdate):
    """
    Update a memory entry.

    Example:
        PUT /api/memory/nb-123/entry-456
        {"content": "Updated fact about the user."}
    """
    rows = await repo_query(
        "SELECT * FROM agent_memory WHERE id = :id AND notebook_id = :notebook_id",
        {"id": entry_id, "notebook_id": notebook_id},
    )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory entry not found: {entry_id}",
        )

    update_data: dict = {"updated": datetime.utcnow().isoformat()}

    if body.content is not None:
        update_data["content"] = body.content
    if body.memory_type is not None:
        update_data["memory_type"] = body.memory_type.value
    if body.metadata is not None:
        update_data["metadata"] = json.dumps(body.metadata)
    if body.tags is not None:
        update_data["tags"] = json.dumps(body.tags)

    await repo_update("agent_memory", entry_id, update_data)

    # Return refreshed record
    refreshed = await repo_query(
        "SELECT * FROM agent_memory WHERE id = :id",
        {"id": entry_id},
    )
    return _row_to_memory_response(refreshed[0])


@router.delete("/{notebook_id}/{entry_id}", response_model=SuccessResponse)
async def delete_memory(notebook_id: str, entry_id: str):
    """
    Delete a memory entry.

    Example:
        DELETE /api/memory/nb-123/entry-456
    """
    rows = await repo_query(
        "SELECT id FROM agent_memory WHERE id = :id AND notebook_id = :notebook_id",
        {"id": entry_id, "notebook_id": notebook_id},
    )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory entry not found: {entry_id}",
        )

    await repo_delete("agent_memory", entry_id)
    return SuccessResponse(message=f"Memory entry {entry_id} deleted")


# ============================================================================
# Memory Search Endpoint
# ============================================================================

@router.post("/{notebook_id}/search", response_model=MemorySearchResponse)
async def search_memory(notebook_id: str, body: MemorySearchRequest):
    """
    Search memory entries for a notebook using keyword matching.

    Searches the content field using SQL LIKE. When vector embeddings are
    available (future), this will also support semantic similarity search.

    Example:
        POST /api/memory/nb-123/search
        {
            "query": "user preferences",
            "memory_type": "preference",
            "limit": 10
        }
    """
    await _verify_notebook(notebook_id)

    # Build keyword search query
    sql = """
        SELECT * FROM agent_memory
        WHERE notebook_id = :notebook_id
        AND content LIKE :query_pattern
    """
    params: dict = {
        "notebook_id": notebook_id,
        "query_pattern": f"%{body.query}%",
    }

    if body.memory_type:
        sql += " AND memory_type = :memory_type"
        params["memory_type"] = body.memory_type.value

    if body.tags:
        # Filter entries that contain any of the requested tags
        # SQLite doesn't have native JSON array containment, so use LIKE
        tag_conditions = []
        for i, tag in enumerate(body.tags):
            param_name = f"tag_{i}"
            tag_conditions.append(f"tags LIKE :{param_name}")
            params[param_name] = f'%"{tag}"%'
        if tag_conditions:
            sql += f" AND ({' OR '.join(tag_conditions)})"

    sql += " ORDER BY updated DESC LIMIT :limit"
    params["limit"] = body.limit

    rows = await repo_query(sql, params)
    results = [_row_to_memory_response(r) for r in rows]

    return MemorySearchResponse(
        results=results,
        total=len(results),
        query=body.query,
    )
