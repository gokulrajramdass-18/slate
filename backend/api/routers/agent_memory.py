"""
Agent Memory API Router

CRUD and search endpoints for agent memory entries.

Two surfaces live here:

1. Legacy notebook-scoped endpoints (``/api/memory/{notebook_id}``) — kept for
   backward compatibility with the original migration-019 model. They use the
   ``MemoryType`` enum (fact|preference|context|conversation|insight).

2. Agent-scoped endpoints (``/api/memory/agents/{agent_id}/...``) — the
   canonical 4-layer model (Short-Term, Episodic, Semantic, Procedural).
   Backed by ``MemoryManager`` in ``api.services.memory_service``.
"""

import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from api.models import (
    EpisodicEntryCreate,
    EpisodicEntryResponse,
    EpisodicListResponse,
    ErrorResponse,
    MemoryConfigModel,
    MemoryEntryCreate,
    MemoryEntryResponse,
    MemoryEntryUpdate,
    MemoryListResponse,
    MemorySearchRequest,
    MemorySearchResponse,
    MemoryStatsResponse,
    ProceduralEntryResponse,
    ProceduralListResponse,
    RecallBundleResponse,
    SemanticEntryCreate,
    SemanticEntryResponse,
    SemanticListResponse,
    SuccessResponse,
)
from api.services.memory_service import get_memory_manager
from open_notebook.database.repository import (
    repo_delete,
    repo_execute,
    repo_query,
    repo_update,
)
from open_notebook.domain.agentic_memory import (
    EpisodicMemory,
    MemoryConfig,
    MemoryLayer,
    ProceduralMemory,
    SemanticMemory,
)
from open_notebook.domain.standalone_agent import StandaloneAgent


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


# ============================================================================
# Agent-Scoped Memory Endpoints (4-layer model)
# ============================================================================
#
# All routes below operate on a single StandaloneAgent. They're prefixed with
# /agents to keep them disambiguated from the legacy notebook-scoped routes.

async def _verify_agent(agent_id: str) -> StandaloneAgent:
    agent = await StandaloneAgent.get(agent_id)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}",
        )
    return agent


def _episodic_to_response(mem: EpisodicMemory) -> EpisodicEntryResponse:
    return EpisodicEntryResponse(
        id=mem.id,
        agent_id=mem.agent_id,
        notebook_id=mem.notebook_id,
        content=mem.content,
        metadata=mem.metadata or {},
        tags=mem.tags or [],
        importance=mem.importance,
        source_message_id=mem.source_message_id,
        expires_at=mem.expires_at,
        created=mem.created,
        updated=mem.updated,
    )


def _semantic_to_response(mem: SemanticMemory) -> SemanticEntryResponse:
    return SemanticEntryResponse(
        id=mem.id,
        agent_id=mem.agent_id,
        notebook_id=mem.notebook_id,
        content=mem.content,
        metadata=mem.metadata or {},
        tags=mem.tags or [],
        importance=mem.importance,
        access_count=mem.access_count,
        last_accessed=mem.last_accessed,
        has_embedding=mem.has_embedding,
        similarity=mem.similarity,
        created=mem.created,
        updated=mem.updated,
    )


def _procedural_to_response(mem: ProceduralMemory) -> ProceduralEntryResponse:
    return ProceduralEntryResponse(
        id=mem.id,
        agent_id=mem.agent_id,
        task_pattern=mem.task_pattern,
        tool_sequence=mem.tool_sequence,
        success_count=mem.success_count,
        failure_count=mem.failure_count,
        success_rate=mem.success_rate,
        total_attempts=mem.total_attempts,
        avg_duration_ms=mem.avg_duration_ms,
        example_inputs=mem.example_inputs,
        last_used=mem.last_used,
        has_embedding=mem.has_embedding,
        similarity=mem.similarity,
        created=mem.created,
        updated=mem.updated,
    )


# ----------------------------------------------------------------------------
# Memory configuration (per-agent)
# ----------------------------------------------------------------------------

@router.get("/agents/{agent_id}/config", response_model=MemoryConfigModel)
async def get_agent_memory_config(agent_id: str):
    """Read the memory configuration for a single agent."""
    agent = await _verify_agent(agent_id)
    cfg = agent.get_memory_config()
    return MemoryConfigModel(**cfg.to_dict())


@router.put("/agents/{agent_id}/config", response_model=MemoryConfigModel)
async def update_agent_memory_config(agent_id: str, body: MemoryConfigModel):
    """
    Replace the memory configuration for a single agent.

    Persists into ``standalone_agents.config`` under the ``memory`` key.

    We update the ``config`` column directly rather than going through
    ``StandaloneAgent.save()`` because the legacy XSUAA schema is missing
    a few of ObjectModel's auto-tracked columns (``is_remote`` etc.) and a
    full row UPDATE blows up. Targeted UPDATE is also faster.
    """
    agent = await _verify_agent(agent_id)
    new_cfg = MemoryConfig.from_dict(body.model_dump())
    cfg = agent.get_config()
    cfg["memory"] = new_cfg.to_dict()
    now = datetime.utcnow().isoformat()
    await repo_execute(
        "UPDATE standalone_agents SET config = :config, updated = :updated WHERE id = :id",
        {"id": agent_id, "config": json.dumps(cfg), "updated": now},
    )
    return MemoryConfigModel(**new_cfg.to_dict())


# ----------------------------------------------------------------------------
# Stats (counts per layer) — used by the Memory tab badge
# ----------------------------------------------------------------------------

@router.get("/agents/{agent_id}/stats", response_model=MemoryStatsResponse)
async def get_agent_memory_stats(agent_id: str):
    await _verify_agent(agent_id)
    mgr = get_memory_manager()
    return MemoryStatsResponse(
        agent_id=agent_id,
        episodic=await mgr.count_layer(agent_id, MemoryLayer.EPISODIC),
        semantic=await mgr.count_layer(agent_id, MemoryLayer.SEMANTIC),
        procedural=await mgr.count_layer(agent_id, MemoryLayer.PROCEDURAL),
    )


# ----------------------------------------------------------------------------
# Recall (debug)
# ----------------------------------------------------------------------------

@router.get("/agents/{agent_id}/recall", response_model=RecallBundleResponse)
async def recall_for_agent(
    agent_id: str,
    query: str = Query(..., min_length=1, description="Probe query for recall ranking"),
    k_episodic: int = Query(5, ge=0, le=50),
    k_semantic: int = Query(5, ge=0, le=50),
    k_procedural: int = Query(3, ge=0, le=50),
):
    """
    Build a RecallBundle for the given query, exactly as the agent would see
    it before generating a response. Returns the bundle plus the formatted
    markdown that would get prepended to the system prompt.
    """
    await _verify_agent(agent_id)
    mgr = get_memory_manager()
    bundle = await mgr.recall_for_agent(
        agent_id,
        query,
        state=None,
        k_episodic=k_episodic,
        k_semantic=k_semantic,
        k_procedural=k_procedural,
    )
    return RecallBundleResponse(
        short_term=bundle.short_term or {},
        episodic=[_episodic_to_response(m) for m in bundle.episodic],
        semantic=[_semantic_to_response(m) for m in bundle.semantic],
        procedural=[_procedural_to_response(m) for m in bundle.procedural],
        formatted_prompt=mgr.format_for_prompt(bundle),
    )


# ----------------------------------------------------------------------------
# Episodic
# ----------------------------------------------------------------------------

@router.get("/agents/{agent_id}/episodic", response_model=EpisodicListResponse)
async def list_episodic(
    agent_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    await _verify_agent(agent_id)
    mgr = get_memory_manager()
    entries = await mgr.list_episodic(agent_id, limit=limit, offset=offset)
    total = await mgr.count_layer(agent_id, MemoryLayer.EPISODIC)
    return EpisodicListResponse(
        entries=[_episodic_to_response(e) for e in entries],
        total=total,
    )


@router.post(
    "/agents/{agent_id}/episodic",
    response_model=EpisodicEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_episodic(agent_id: str, body: EpisodicEntryCreate):
    await _verify_agent(agent_id)
    mgr = get_memory_manager()
    entry = await mgr.record_episode(
        agent_id,
        body.notebook_id,
        body.content,
        metadata=body.metadata,
        tags=body.tags,
        importance=body.importance,
        source_message_id=body.source_message_id,
    )
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Episodic memory is disabled for this agent.",
        )
    return _episodic_to_response(entry)


@router.delete("/agents/{agent_id}/episodic/{entry_id}", response_model=SuccessResponse)
async def delete_episodic(agent_id: str, entry_id: str):
    await _verify_agent(agent_id)
    mgr = get_memory_manager()
    ok = await mgr.delete_entry(entry_id, layer=MemoryLayer.EPISODIC)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Episodic entry not found: {entry_id}",
        )
    return SuccessResponse(message=f"Episodic entry {entry_id} deleted")


# ----------------------------------------------------------------------------
# Semantic
# ----------------------------------------------------------------------------

@router.get("/agents/{agent_id}/semantic", response_model=SemanticListResponse)
async def list_semantic(
    agent_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    await _verify_agent(agent_id)
    mgr = get_memory_manager()
    entries = await mgr.list_semantic(agent_id, limit=limit, offset=offset)
    total = await mgr.count_layer(agent_id, MemoryLayer.SEMANTIC)
    return SemanticListResponse(
        entries=[_semantic_to_response(e) for e in entries],
        total=total,
    )


@router.post(
    "/agents/{agent_id}/semantic",
    response_model=SemanticEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_semantic(agent_id: str, body: SemanticEntryCreate):
    await _verify_agent(agent_id)
    mgr = get_memory_manager()
    entry = await mgr.record_fact(
        agent_id,
        body.notebook_id,
        body.content,
        metadata=body.metadata,
        tags=body.tags,
        importance=body.importance,
    )
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Semantic memory is disabled for this agent.",
        )
    return _semantic_to_response(entry)


@router.delete("/agents/{agent_id}/semantic/{entry_id}", response_model=SuccessResponse)
async def delete_semantic(agent_id: str, entry_id: str):
    await _verify_agent(agent_id)
    mgr = get_memory_manager()
    ok = await mgr.delete_entry(entry_id, layer=MemoryLayer.SEMANTIC)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Semantic entry not found: {entry_id}",
        )
    return SuccessResponse(message=f"Semantic entry {entry_id} deleted")


# ----------------------------------------------------------------------------
# Procedural (read + delete only — captured automatically from executions)
# ----------------------------------------------------------------------------

@router.get("/agents/{agent_id}/procedural", response_model=ProceduralListResponse)
async def list_procedural(
    agent_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    await _verify_agent(agent_id)
    mgr = get_memory_manager()
    entries = await mgr.list_procedural(agent_id, limit=limit, offset=offset)
    total = await mgr.count_layer(agent_id, MemoryLayer.PROCEDURAL)
    return ProceduralListResponse(
        entries=[_procedural_to_response(e) for e in entries],
        total=total,
    )


@router.delete(
    "/agents/{agent_id}/procedural/{entry_id}", response_model=SuccessResponse
)
async def delete_procedural(agent_id: str, entry_id: str):
    await _verify_agent(agent_id)
    mgr = get_memory_manager()
    ok = await mgr.delete_entry(entry_id, layer=MemoryLayer.PROCEDURAL)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Procedural entry not found: {entry_id}",
        )
    return SuccessResponse(message=f"Procedural entry {entry_id} deleted")


@router.post(
    "/agents/{agent_id}/procedural/prune-expired", response_model=SuccessResponse
)
async def prune_expired_episodic(agent_id: str):
    """
    Manually trigger expiry pruning for an agent.

    Episodic rows whose ``expires_at`` is in the past are deleted. Recall does
    this lazily on every call, but exposing it for the inspector page is handy.
    """
    await _verify_agent(agent_id)
    mgr = get_memory_manager()
    deleted = await mgr.prune_expired(agent_id)
    return SuccessResponse(message=f"Pruned {deleted} expired episodic entries")
