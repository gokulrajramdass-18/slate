"""
Bookmarks API Router

Endpoints for managing user-specific bookmarks across entity types.
Follows the user_query_prompts.py pattern with X-User-ID header for user isolation.
Includes natural language search using embeddings.
"""

import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Header, BackgroundTasks

from api.models import (
    BookmarkCreate,
    BookmarkUpdate,
    BookmarkResponse,
    EnrichedBookmarkResponse,
    BookmarkListResponse,
    BookmarkToggleResponse,
    BookmarkBulkCheckRequest,
    BookmarkBulkCheckResponse,
    BookmarkSearchRequest,
    BookmarkSearchResult,
    BookmarkSearchResponse,
    BookmarkEmbeddingResponse,
    BookmarkRegenerateResponse,
    ErrorResponse,
    SuccessResponse,
)
from open_notebook.database.repository import repo_query, repo_execute
from open_notebook.domain.bookmark import Bookmark
from api.services.bookmark_embedding_service import get_bookmark_embedding_service


router = APIRouter(
    prefix="/api/bookmarks",
    tags=["bookmarks"],
    responses={404: {"model": ErrorResponse}},
)


# ============================================================================
# Helpers
# ============================================================================

def _get_user_id(x_user_id: Optional[str] = None) -> str:
    """Get user ID from header or use default."""
    return x_user_id or "default_user"


async def _enrich_bookmark(bookmark: dict) -> dict:
    """Add entity details to a bookmark for display."""
    entity_type = bookmark["entity_type"]
    entity_id = bookmark["entity_id"]

    # Defaults
    bookmark["entity_title"] = None
    bookmark["entity_description"] = None
    bookmark["entity_updated"] = None
    bookmark["source_type"] = None
    bookmark["chunk_count"] = None
    bookmark["source_count"] = None
    bookmark["note_count"] = None

    if entity_type == "source":
        rows = await repo_query(
            "SELECT * FROM sources WHERE id = :id", {"id": entity_id}
        )
        if rows:
            source = rows[0]
            bookmark["entity_title"] = source.get("title")
            bookmark["entity_updated"] = source.get("updated")
            bookmark["source_type"] = source.get("source_type")
            # Get chunk count
            chunks = await repo_query(
                "SELECT COUNT(*) as count FROM source_embeddings WHERE source_id = :id",
                {"id": entity_id},
            )
            bookmark["chunk_count"] = chunks[0]["count"] if chunks else 0

    elif entity_type == "note":
        rows = await repo_query(
            "SELECT * FROM notes WHERE id = :id", {"id": entity_id}
        )
        if rows:
            note = rows[0]
            bookmark["entity_title"] = note.get("title")
            bookmark["entity_description"] = note.get("summary") or note.get("content", "")[:200]
            bookmark["entity_updated"] = note.get("updated")

    elif entity_type == "notebook":
        rows = await repo_query(
            "SELECT * FROM notebooks WHERE id = :id", {"id": entity_id}
        )
        if rows:
            notebook = rows[0]
            bookmark["entity_title"] = notebook.get("name")
            bookmark["entity_description"] = notebook.get("description")
            bookmark["entity_updated"] = notebook.get("updated")
            # Get counts
            sources = await repo_query(
                "SELECT COUNT(*) as count FROM notebook_source WHERE notebook_id = :id",
                {"id": entity_id},
            )
            notes = await repo_query(
                "SELECT COUNT(*) as count FROM notebook_note WHERE notebook_id = :id",
                {"id": entity_id},
            )
            bookmark["source_count"] = sources[0]["count"] if sources else 0
            bookmark["note_count"] = notes[0]["count"] if notes else 0

    return bookmark


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/toggle", response_model=BookmarkToggleResponse)
async def toggle_bookmark(
    body: BookmarkCreate,
    x_user_id: Optional[str] = Header(None),
):
    """
    Toggle bookmark on/off for an entity.

    If the entity is bookmarked, it will be un-bookmarked, and vice versa.
    """
    user_id = _get_user_id(x_user_id)

    # Validate entity_type
    if body.entity_type not in ("source", "note", "notebook"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid entity_type: {body.entity_type}. Must be source, note, or notebook.",
        )

    result = await Bookmark.toggle(
        user_id=user_id,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        custom_note=body.custom_note,
        reason=body.reason,
    )

    bookmark_resp = None
    if result["bookmark"]:
        bookmark_resp = BookmarkResponse(**result["bookmark"])

    return BookmarkToggleResponse(
        is_bookmarked=result["is_bookmarked"],
        bookmark=bookmark_resp,
        message=result["message"],
    )


@router.get("", response_model=BookmarkListResponse)
async def list_bookmarks(
    x_user_id: Optional[str] = Header(None),
    entity_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """
    List all bookmarks for the current user.

    Optionally filter by entity type.
    Results are enriched with entity details (title, description, counts).
    """
    user_id = _get_user_id(x_user_id)

    # Get total count
    total = await Bookmark.count_user_bookmarks(user_id, entity_type)

    # Get bookmarks
    rows = await Bookmark.get_user_bookmarks(user_id, entity_type, limit, offset)

    # Enrich each bookmark with entity details
    enriched = []
    for row in rows:
        enriched_row = await _enrich_bookmark(dict(row))
        enriched.append(EnrichedBookmarkResponse(**enriched_row))

    return BookmarkListResponse(bookmarks=enriched, total=total)


@router.get("/check/{entity_type}/{entity_id}")
async def check_bookmark(
    entity_type: str,
    entity_id: str,
    x_user_id: Optional[str] = Header(None),
):
    """Check if a specific entity is bookmarked by the current user."""
    user_id = _get_user_id(x_user_id)

    is_bookmarked = await Bookmark.is_bookmarked(user_id, entity_type, entity_id)

    # Get bookmark_id if bookmarked
    bookmark_id = None
    if is_bookmarked:
        rows = await repo_query(
            """SELECT id FROM user_bookmarks
               WHERE user_id = :user_id AND entity_type = :entity_type AND entity_id = :entity_id""",
            {"user_id": user_id, "entity_type": entity_type, "entity_id": entity_id},
        )
        if rows:
            bookmark_id = rows[0]["id"]

    return {"is_bookmarked": is_bookmarked, "bookmark_id": bookmark_id}


@router.post("/bulk-check", response_model=BookmarkBulkCheckResponse)
async def bulk_check_bookmarks(
    body: BookmarkBulkCheckRequest,
    x_user_id: Optional[str] = Header(None),
):
    """
    Check bookmark status for multiple entities at once.

    Returns a mapping of entity_id -> is_bookmarked.
    """
    user_id = _get_user_id(x_user_id)

    result = await Bookmark.bulk_check(user_id, body.entity_type, body.entity_ids)

    return BookmarkBulkCheckResponse(bookmarks=result)


@router.get("/{bookmark_id}", response_model=BookmarkResponse)
async def get_bookmark(
    bookmark_id: str,
    x_user_id: Optional[str] = Header(None),
):
    """Get a specific bookmark by ID."""
    user_id = _get_user_id(x_user_id)

    bookmark = await Bookmark.get_by_id(bookmark_id, user_id)
    if not bookmark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bookmark not found: {bookmark_id}",
        )

    return BookmarkResponse(**bookmark)


@router.put("/{bookmark_id}", response_model=BookmarkResponse)
async def update_bookmark(
    bookmark_id: str,
    body: BookmarkUpdate,
    x_user_id: Optional[str] = Header(None),
):
    """Update bookmark metadata (custom_note, reason)."""
    user_id = _get_user_id(x_user_id)

    # Verify exists
    existing = await Bookmark.get_by_id(bookmark_id, user_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bookmark not found: {bookmark_id}",
        )

    updated = await Bookmark.update(
        bookmark_id=bookmark_id,
        user_id=user_id,
        custom_note=body.custom_note,
        reason=body.reason,
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update bookmark",
        )

    return BookmarkResponse(**updated)


@router.delete("/{bookmark_id}", response_model=SuccessResponse)
async def delete_bookmark(
    bookmark_id: str,
    x_user_id: Optional[str] = Header(None),
):
    """Delete a bookmark."""
    user_id = _get_user_id(x_user_id)

    deleted = await Bookmark.delete(bookmark_id, user_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bookmark not found: {bookmark_id}",
        )

    return SuccessResponse(message=f"Bookmark deleted: {bookmark_id}")


# ============================================================================
# Semantic Search Endpoints
# ============================================================================

@router.post("/search", response_model=BookmarkSearchResponse)
async def search_bookmarks(
    body: BookmarkSearchRequest,
    x_user_id: Optional[str] = Header(None),
):
    """
    Search bookmarks using natural language.

    Uses embeddings for semantic similarity search across:
    - Entity titles and descriptions
    - Custom notes and reasons
    - Tags and categories
    """
    user_id = _get_user_id(x_user_id)

    try:
        service = get_bookmark_embedding_service()
        results = await service.search_bookmarks(
            query=body.query,
            user_id=user_id,
            limit=body.limit,
            threshold=body.threshold
        )

        # Enrich results with entity details
        enriched_results = []
        for result in results:
            # Create bookmark dict for enrichment
            bookmark = {
                "id": result["bookmark_id"],
                "user_id": user_id,
                "entity_type": result["entity_type"],
                "entity_id": result["entity_id"],
                "custom_note": result["custom_note"],
                "reason": result["reason"],
                "tags": result["tags"],
                "category": result["category"],
                "bookmarked_at": result["bookmarked_at"],
                "created": result["bookmarked_at"],  # Use bookmarked_at as fallback
                "updated": result["bookmarked_at"],
            }

            enriched = await _enrich_bookmark(bookmark)

            # Add similarity and content
            enriched["similarity"] = result["similarity"]
            enriched["content"] = result["content"]

            enriched_results.append(BookmarkSearchResult(**enriched))

        return BookmarkSearchResponse(
            results=enriched_results,
            total=len(enriched_results),
            query=body.query
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.post("/{bookmark_id}/embedding", response_model=BookmarkEmbeddingResponse)
async def generate_bookmark_embedding(
    bookmark_id: str,
    background_tasks: BackgroundTasks,
    x_user_id: Optional[str] = Header(None),
):
    """
    Generate embedding for a specific bookmark.

    This is useful for regenerating embeddings after updates or when adding
    embeddings to existing bookmarks.
    """
    user_id = _get_user_id(x_user_id)

    # Verify bookmark exists and belongs to user
    bookmark = await Bookmark.get_by_id(bookmark_id, user_id)
    if not bookmark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bookmark not found: {bookmark_id}",
        )

    # Generate embedding in background
    service = get_bookmark_embedding_service()
    background_tasks.add_task(service.generate_embedding_for_bookmark, bookmark_id)

    return BookmarkEmbeddingResponse(
        success=True,
        bookmark_id=bookmark_id,
        message="Embedding generation started in background"
    )


@router.post("/embeddings/regenerate", response_model=BookmarkRegenerateResponse)
async def regenerate_all_embeddings(
    x_user_id: Optional[str] = Header(None),
):
    """
    Regenerate embeddings for all bookmarks of the current user.

    This is useful when:
    - Switching embedding models
    - Fixing corrupted embeddings
    - Bulk adding embeddings to existing bookmarks
    """
    user_id = _get_user_id(x_user_id)

    try:
        service = get_bookmark_embedding_service()
        results = await service.regenerate_all_embeddings(user_id)

        return BookmarkRegenerateResponse(**results)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate embeddings: {str(e)}"
        )
