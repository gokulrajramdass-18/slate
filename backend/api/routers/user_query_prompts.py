"""
User Query Prompts API Router

Endpoints for managing user-specific saved query prompts that can be reused.
"""

import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Header

from api.models import (
    ErrorResponse,
    UserQueryPromptCreate,
    UserQueryPromptUpdate,
    UserQueryPromptResponse,
    UserQueryPromptListResponse,
    SuccessResponse,
)
from open_notebook.database.repository import repo_query, repo_execute


router = APIRouter(
    prefix="/api/user-query-prompts",
    tags=["user-query-prompts"],
    responses={404: {"model": ErrorResponse}},
)


# ============================================================================
# Helpers
# ============================================================================

def _get_user_id(x_user_id: Optional[str] = None) -> str:
    """Get user ID from header or use default."""
    return x_user_id or "default_user"


def _row_to_response(row: dict) -> UserQueryPromptResponse:
    """Convert a DB row to UserQueryPromptResponse."""
    tags = []
    if row.get("tags"):
        try:
            tags = json.loads(row["tags"]) if isinstance(row["tags"], str) else row["tags"]
        except (json.JSONDecodeError, TypeError):
            tags = []

    return UserQueryPromptResponse(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        query_text=row["query_text"],
        description=row.get("description"),
        category=row.get("category"),
        team_id=row.get("team_id"),
        prompt_role=row.get("prompt_role"),
        tags=tags,
        use_count=row.get("use_count", 0),
        last_used=row.get("last_used"),
        is_favorite=bool(row.get("is_favorite", 0)),
        created=row["created"],
        updated=row["updated"],
    )


# ============================================================================
# CRUD Endpoints
# ============================================================================

@router.get("", response_model=UserQueryPromptListResponse)
async def list_prompts(
    x_user_id: Optional[str] = Header(None),
    team_id: Optional[str] = None,
    category: Optional[str] = None,
    is_favorite: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0
):
    """
    List saved query prompts for the current user.

    Can filter by team, category, or favorite status.
    Results ordered by last_used (most recent first), then by created.
    """
    user_id = _get_user_id(x_user_id)

    # Build query
    conditions = ["user_id = :user_id"]
    params = {"user_id": user_id, "limit": limit, "offset": offset}

    if team_id:
        conditions.append("team_id = :team_id")
        params["team_id"] = team_id

    if category:
        conditions.append("category = :category")
        params["category"] = category

    if is_favorite is not None:
        conditions.append("is_favorite = :is_favorite")
        params["is_favorite"] = 1 if is_favorite else 0

    where_clause = " AND ".join(conditions)

    # Get total count
    count_rows = await repo_query(
        f"SELECT COUNT(*) as count FROM user_query_prompts WHERE {where_clause}",
        params
    )
    total = count_rows[0]["count"] if count_rows else 0

    # Get prompts
    rows = await repo_query(
        f"""SELECT * FROM user_query_prompts
            WHERE {where_clause}
            ORDER BY
                CASE WHEN last_used IS NULL THEN 1 ELSE 0 END,
                last_used DESC,
                created DESC
            LIMIT :limit OFFSET :offset""",
        params
    )

    prompts = [_row_to_response(r) for r in rows]
    return UserQueryPromptListResponse(prompts=prompts, total=total)


@router.get("/{prompt_id}", response_model=UserQueryPromptResponse)
async def get_prompt(
    prompt_id: str,
    x_user_id: Optional[str] = Header(None)
):
    """Get a specific saved query prompt."""
    user_id = _get_user_id(x_user_id)

    rows = await repo_query(
        "SELECT * FROM user_query_prompts WHERE id = :id AND user_id = :user_id",
        {"id": prompt_id, "user_id": user_id}
    )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt not found: {prompt_id}"
        )

    return _row_to_response(rows[0])


@router.post("", response_model=UserQueryPromptResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt(
    body: UserQueryPromptCreate,
    x_user_id: Optional[str] = Header(None)
):
    """Create a new saved query prompt."""
    user_id = _get_user_id(x_user_id)
    now = datetime.utcnow().isoformat()
    prompt_id = str(uuid.uuid4())

    # Validate team_id if provided
    if body.team_id:
        team_rows = await repo_query(
            "SELECT id FROM agent_teams WHERE id = :id",
            {"id": body.team_id}
        )
        if not team_rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Team not found: {body.team_id}"
            )

    tags_json = json.dumps(body.tags) if body.tags else None

    await repo_execute(
        """INSERT INTO user_query_prompts
           (id, user_id, name, query_text, description, category, team_id, prompt_role,
            tags, use_count, is_favorite, created, updated)
           VALUES (:id, :user_id, :name, :query_text, :description, :category, :team_id,
                   :prompt_role, :tags, 0, :is_favorite, :created, :updated)""",
        {
            "id": prompt_id,
            "user_id": user_id,
            "name": body.name,
            "query_text": body.query_text,
            "description": body.description,
            "category": body.category,
            "team_id": body.team_id,
            "prompt_role": body.prompt_role,
            "tags": tags_json,
            "is_favorite": 1 if body.is_favorite else 0,
            "created": now,
            "updated": now,
        }
    )

    # Return created prompt
    return await get_prompt(prompt_id, x_user_id)


@router.put("/{prompt_id}", response_model=UserQueryPromptResponse)
async def update_prompt(
    prompt_id: str,
    body: UserQueryPromptUpdate,
    x_user_id: Optional[str] = Header(None)
):
    """Update a saved query prompt."""
    user_id = _get_user_id(x_user_id)
    now = datetime.utcnow().isoformat()

    # Verify exists
    existing = await repo_query(
        "SELECT * FROM user_query_prompts WHERE id = :id AND user_id = :user_id",
        {"id": prompt_id, "user_id": user_id}
    )

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt not found: {prompt_id}"
        )

    # Build update
    updates = []
    params = {"id": prompt_id, "user_id": user_id, "updated": now}

    if body.name is not None:
        updates.append("name = :name")
        params["name"] = body.name

    if body.query_text is not None:
        updates.append("query_text = :query_text")
        params["query_text"] = body.query_text

    if body.description is not None:
        updates.append("description = :description")
        params["description"] = body.description

    if body.category is not None:
        updates.append("category = :category")
        params["category"] = body.category

    if body.tags is not None:
        updates.append("tags = :tags")
        params["tags"] = json.dumps(body.tags)

    if body.is_favorite is not None:
        updates.append("is_favorite = :is_favorite")
        params["is_favorite"] = 1 if body.is_favorite else 0

    if updates:
        updates.append("updated = :updated")
        sql = f"UPDATE user_query_prompts SET {', '.join(updates)} WHERE id = :id AND user_id = :user_id"
        await repo_execute(sql, params)

    return await get_prompt(prompt_id, x_user_id)


@router.delete("/{prompt_id}", response_model=SuccessResponse)
async def delete_prompt(
    prompt_id: str,
    x_user_id: Optional[str] = Header(None)
):
    """Delete a saved query prompt."""
    user_id = _get_user_id(x_user_id)

    # Verify exists
    existing = await repo_query(
        "SELECT * FROM user_query_prompts WHERE id = :id AND user_id = :user_id",
        {"id": prompt_id, "user_id": user_id}
    )

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt not found: {prompt_id}"
        )

    await repo_execute(
        "DELETE FROM user_query_prompts WHERE id = :id AND user_id = :user_id",
        {"id": prompt_id, "user_id": user_id}
    )

    return SuccessResponse(message=f"Prompt deleted: {prompt_id}")


# ============================================================================
# Usage Tracking
# ============================================================================

@router.post("/{prompt_id}/use", response_model=UserQueryPromptResponse)
async def mark_prompt_used(
    prompt_id: str,
    x_user_id: Optional[str] = Header(None)
):
    """
    Mark a prompt as used (increments use_count and updates last_used).

    Call this when a user loads a saved prompt into the query input.
    """
    user_id = _get_user_id(x_user_id)
    now = datetime.utcnow().isoformat()

    # Verify exists
    existing = await repo_query(
        "SELECT * FROM user_query_prompts WHERE id = :id AND user_id = :user_id",
        {"id": prompt_id, "user_id": user_id}
    )

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt not found: {prompt_id}"
        )

    # Increment use count and update last_used
    await repo_execute(
        """UPDATE user_query_prompts
           SET use_count = use_count + 1, last_used = :last_used, updated = :updated
           WHERE id = :id AND user_id = :user_id""",
        {"id": prompt_id, "user_id": user_id, "last_used": now, "updated": now}
    )

    return await get_prompt(prompt_id, x_user_id)


@router.post("/{prompt_id}/favorite", response_model=UserQueryPromptResponse)
async def toggle_favorite(
    prompt_id: str,
    x_user_id: Optional[str] = Header(None)
):
    """Toggle favorite status for a prompt."""
    user_id = _get_user_id(x_user_id)
    now = datetime.utcnow().isoformat()

    # Get current status
    existing = await repo_query(
        "SELECT is_favorite FROM user_query_prompts WHERE id = :id AND user_id = :user_id",
        {"id": prompt_id, "user_id": user_id}
    )

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt not found: {prompt_id}"
        )

    # Toggle
    new_favorite = 0 if existing[0]["is_favorite"] else 1

    await repo_execute(
        """UPDATE user_query_prompts
           SET is_favorite = :is_favorite, updated = :updated
           WHERE id = :id AND user_id = :user_id""",
        {"id": prompt_id, "user_id": user_id, "is_favorite": new_favorite, "updated": now}
    )

    return await get_prompt(prompt_id, x_user_id)
