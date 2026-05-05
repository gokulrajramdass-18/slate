"""
System Prompt Template API Router

Endpoints for managing system prompt templates by category.
Mirrors agent_prompts.py pattern for consistency.
"""

import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Query

from api.models import (
    ErrorResponse,
    SystemPromptTemplateResponse,
    SystemPromptTemplateUpdate,
    SystemPromptTemplateListResponse,
    SuccessResponse
)
from api.services.prompt_loader import PromptLoader
from open_notebook.database.repository import repo_query, repo_execute


router = APIRouter(
    prefix="/api/system-prompts",
    tags=["system-prompts"],
    responses={404: {"model": ErrorResponse}},
)


# ============================================================================
# Helpers
# ============================================================================

def _row_to_response(row: dict) -> SystemPromptTemplateResponse:
    """Convert a DB row from system_prompt_templates to SystemPromptTemplateResponse."""
    return SystemPromptTemplateResponse(
        id=row["id"],
        category=row["category"],
        template_key=row["template_key"],
        name=row["name"],
        description=row.get("description"),
        template=row["prompt_text"],  # Map prompt_text to template field
        variables=row.get("variables"),  # Will be parsed by Pydantic validator
        metadata=row.get("metadata"),  # Will be parsed by Pydantic validator
        is_default=bool(row.get("is_default", 1)),
        is_active=bool(row.get("is_active", 1)),
        created=row.get("created"),
        updated=row.get("updated"),
    )


# ============================================================================
# Template CRUD Endpoints
# ============================================================================

@router.get("/templates", response_model=SystemPromptTemplateListResponse)
async def list_templates(category: Optional[str] = Query(None, description="Filter by category")):
    """
    List all system prompt templates, optionally filtered by category.

    Categories: chat, research, orchestration, microsite
    """
    if category:
        rows = await repo_query(
            "SELECT * FROM system_prompt_templates WHERE category = :category ORDER BY template_key ASC",
            {"category": category}
        )
    else:
        rows = await repo_query(
            "SELECT * FROM system_prompt_templates ORDER BY category ASC, template_key ASC"
        )

    templates = [_row_to_response(r) for r in rows]
    return SystemPromptTemplateListResponse(templates=templates, total=len(templates))


@router.get("/templates/{template_key}", response_model=SystemPromptTemplateResponse)
async def get_template(template_key: str):
    """
    Get a specific system prompt template by key.
    """
    rows = await repo_query(
        "SELECT * FROM system_prompt_templates WHERE template_key = :key",
        {"key": template_key},
    )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {template_key}",
        )

    return _row_to_response(rows[0])


@router.put("/templates/{template_key}", response_model=SystemPromptTemplateResponse)
async def update_template(template_key: str, body: SystemPromptTemplateUpdate):
    """
    Update a system prompt template.

    This marks the template as non-default (is_default=0).
    The original default text is preserved in default_prompt_text for reset.
    """
    now = datetime.utcnow().isoformat()

    # Verify template exists
    rows = await repo_query(
        "SELECT * FROM system_prompt_templates WHERE template_key = :key",
        {"key": template_key},
    )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {template_key}",
        )

    update_fields = {"key": template_key, "updated": now, "prompt_text": body.template}

    # Build dynamic SET clause
    set_parts = ["prompt_text = :prompt_text", "is_default = 0", "updated = :updated"]

    if body.name is not None:
        set_parts.append("name = :name")
        update_fields["name"] = body.name

    if body.description is not None:
        set_parts.append("description = :description")
        update_fields["description"] = body.description

    sql = f"UPDATE system_prompt_templates SET {', '.join(set_parts)} WHERE template_key = :key"
    await repo_execute(sql, update_fields)

    # Invalidate cache for this template
    PromptLoader.invalidate_cache(template_key)

    # Return updated template
    updated_rows = await repo_query(
        "SELECT * FROM system_prompt_templates WHERE template_key = :key",
        {"key": template_key},
    )
    return _row_to_response(updated_rows[0])


@router.post("/templates/{template_key}/reset", response_model=SystemPromptTemplateResponse)
async def reset_template(template_key: str):
    """
    Reset a system prompt template to its built-in default.

    Copies default_prompt_text back into prompt_text and sets is_default=1.
    """
    rows = await repo_query(
        "SELECT * FROM system_prompt_templates WHERE template_key = :key",
        {"key": template_key},
    )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {template_key}",
        )

    now = datetime.utcnow().isoformat()

    await repo_execute(
        """UPDATE system_prompt_templates
           SET prompt_text = default_prompt_text, is_default = 1, updated = :updated
           WHERE template_key = :key""",
        {"updated": now, "key": template_key},
    )

    # Invalidate cache
    PromptLoader.invalidate_cache(template_key)

    updated_rows = await repo_query(
        "SELECT * FROM system_prompt_templates WHERE template_key = :key",
        {"key": template_key},
    )
    return _row_to_response(updated_rows[0])


@router.post("/templates/{template_key}/toggle", response_model=SystemPromptTemplateResponse)
async def toggle_template(template_key: str):
    """
    Toggle a template between active and inactive.

    When inactive (is_active=0), the system will use hardcoded fallback prompts.
    """
    rows = await repo_query(
        "SELECT * FROM system_prompt_templates WHERE template_key = :key",
        {"key": template_key},
    )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {template_key}",
        )

    current_active = bool(rows[0]["is_active"])
    new_active = 0 if current_active else 1
    now = datetime.utcnow().isoformat()

    await repo_execute(
        """UPDATE system_prompt_templates
           SET is_active = :active, updated = :updated
           WHERE template_key = :key""",
        {"active": new_active, "updated": now, "key": template_key},
    )

    # Invalidate cache
    PromptLoader.invalidate_cache(template_key)

    updated_rows = await repo_query(
        "SELECT * FROM system_prompt_templates WHERE template_key = :key",
        {"key": template_key},
    )
    return _row_to_response(updated_rows[0])


@router.post("/cache/clear", response_model=SuccessResponse)
async def clear_cache():
    """
    Clear the prompt loader cache.

    Useful after bulk updates or for debugging.
    """
    stats_before = PromptLoader.get_cache_stats()
    PromptLoader.invalidate_cache()  # Clear all
    stats_after = PromptLoader.get_cache_stats()

    return SuccessResponse(
        message=f"Cache cleared. {stats_before['cache_size']} entries removed.",
        data={"before": stats_before, "after": stats_after}
    )


@router.get("/cache/stats")
async def get_cache_stats():
    """
    Get prompt loader cache statistics.
    """
    return PromptLoader.get_cache_stats()
