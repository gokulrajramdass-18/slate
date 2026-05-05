"""
Agent Prompt Template API Router

Endpoints for managing prompt templates by agent role
and per-agent custom prompt overrides.
"""

import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, status

from api.models import (
    ErrorResponse,
    PromptTemplateResponse,
    PromptTemplateUpdate,
    PromptTemplateListResponse,
    AgentPromptResponse,
    AgentPromptUpdate,
    SuccessResponse,
)
from open_notebook.database.repository import repo_query, repo_execute


router = APIRouter(
    prefix="/api/agents/prompts",
    tags=["agent-prompts"],
    responses={404: {"model": ErrorResponse}},
)


# ============================================================================
# Helpers
# ============================================================================

def _row_to_response(row: dict) -> PromptTemplateResponse:
    """Convert a DB row from agent_prompt_templates to PromptTemplateResponse."""
    return PromptTemplateResponse(
        id=row["id"],
        role=row["role"],
        name=row["name"],
        template=row["prompt_text"],
        description=row.get("description"),
        is_default=bool(row.get("is_default", 1)),
        variables=None,  # Not stored in DB; could be extracted at runtime
        created=row.get("created"),
        updated=row.get("updated"),
    )


# ============================================================================
# Template CRUD Endpoints
# ============================================================================

@router.get("/templates", response_model=PromptTemplateListResponse)
async def list_templates():
    """
    List all prompt templates.

    Returns one template per agent role.
    """
    rows = await repo_query(
        "SELECT * FROM agent_prompt_templates ORDER BY role ASC"
    )

    templates = [_row_to_response(r) for r in rows]
    return PromptTemplateListResponse(templates=templates, total=len(templates))


@router.get("/templates/{role}", response_model=PromptTemplateResponse)
async def get_template(role: str):
    """
    Get the prompt template for a specific agent role.
    """
    rows = await repo_query(
        "SELECT * FROM agent_prompt_templates WHERE role = :role",
        {"role": role},
    )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No template found for role: {role}",
        )

    return _row_to_response(rows[0])


@router.put("/templates/{role}", response_model=PromptTemplateResponse)
async def update_template(role: str, body: PromptTemplateUpdate):
    """
    Update the prompt template for an agent role.

    This marks the template as non-default (is_default=0).
    The original default text is preserved in default_prompt_text for reset.
    """
    now = datetime.utcnow().isoformat()

    # Verify template exists
    rows = await repo_query(
        "SELECT * FROM agent_prompt_templates WHERE role = :role",
        {"role": role},
    )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No template found for role: {role}",
        )

    update_fields = {"role": role, "updated": now, "prompt_text": body.template}

    # Build dynamic SET clause
    set_parts = ["prompt_text = :prompt_text", "is_default = 0", "updated = :updated"]

    if body.name is not None:
        set_parts.append("name = :name")
        update_fields["name"] = body.name

    if body.description is not None:
        set_parts.append("description = :description")
        update_fields["description"] = body.description

    sql = f"UPDATE agent_prompt_templates SET {', '.join(set_parts)} WHERE role = :role"
    await repo_execute(sql, update_fields)

    # Return updated template
    updated_rows = await repo_query(
        "SELECT * FROM agent_prompt_templates WHERE role = :role",
        {"role": role},
    )
    return _row_to_response(updated_rows[0])


@router.post("/templates", response_model=PromptTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(body: PromptTemplateUpdate):
    """
    Create a new agent role template with a custom system prompt.

    The role name must be unique and not already exist.
    Both prompt_text and default_prompt_text are set to the provided template.
    """
    if not body.role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role name is required",
        )

    # Check if role already exists
    existing = await repo_query(
        "SELECT * FROM agent_prompt_templates WHERE role = :role",
        {"role": body.role},
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Role '{body.role}' already exists. Use PUT to update it.",
        )

    now = datetime.utcnow().isoformat()
    template_id = f"prompt-tpl-{str(uuid.uuid4())[:8]}"

    # Create new template
    await repo_execute(
        """INSERT INTO agent_prompt_templates
           (id, role, name, description, prompt_text, default_prompt_text, is_default, created, updated)
           VALUES (:id, :role, :name, :description, :prompt_text, :default_prompt_text, 0, :created, :updated)""",
        {
            "id": template_id,
            "role": body.role,
            "name": body.name or body.role.replace("_", " ").title(),
            "description": body.description or f"Custom {body.role} agent role",
            "prompt_text": body.template,
            "default_prompt_text": body.template,  # Same as prompt_text initially
            "created": now,
            "updated": now,
        },
    )

    # Return created template
    rows = await repo_query(
        "SELECT * FROM agent_prompt_templates WHERE id = :id",
        {"id": template_id},
    )
    return _row_to_response(rows[0])


@router.post("/templates/{role}/reset", response_model=PromptTemplateResponse)
async def reset_template(role: str):
    """
    Reset a prompt template to its built-in default.

    Copies default_prompt_text back into prompt_text and sets is_default=1.
    """
    rows = await repo_query(
        "SELECT * FROM agent_prompt_templates WHERE role = :role",
        {"role": role},
    )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No template found for role: {role}",
        )

    now = datetime.utcnow().isoformat()

    await repo_execute(
        """UPDATE agent_prompt_templates
           SET prompt_text = default_prompt_text, is_default = 1, updated = :updated
           WHERE role = :role""",
        {"updated": now, "role": role},
    )

    updated_rows = await repo_query(
        "SELECT * FROM agent_prompt_templates WHERE role = :role",
        {"role": role},
    )
    return _row_to_response(updated_rows[0])


@router.delete("/templates/{role}", response_model=SuccessResponse)
async def delete_template(role: str):
    """
    Delete a custom agent role template.

    Only custom roles (is_default=0) can be deleted.
    Built-in roles (is_default=1) cannot be deleted.
    """
    rows = await repo_query(
        "SELECT * FROM agent_prompt_templates WHERE role = :role",
        {"role": role},
    )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No template found for role: {role}",
        )

    # Prevent deletion of built-in roles
    if rows[0].get("is_default", 1):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cannot delete built-in role: {role}. Only custom roles can be deleted.",
        )

    await repo_execute(
        "DELETE FROM agent_prompt_templates WHERE role = :role",
        {"role": role},
    )

    return SuccessResponse(message=f"Template '{role}' deleted successfully")


# ============================================================================
# Per-Agent Prompt Endpoints
# ============================================================================

@router.get("/agents/{agent_id}/prompt", response_model=AgentPromptResponse)
async def get_agent_prompt(agent_id: str):
    """
    Get the effective prompt for a specific agent.

    Resolution order:
    1. Agent's system_prompt field (custom override on the agent row)
    2. Role-level template from agent_prompt_templates
    3. Fallback generic prompt
    """
    # Fetch agent
    agent_rows = await repo_query(
        "SELECT * FROM agents WHERE id = :id",
        {"id": agent_id},
    )
    if not agent_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}",
        )

    agent = agent_rows[0]
    role = agent.get("role", "custom")

    # Check for custom prompt on the agent itself
    custom_prompt = agent.get("system_prompt")
    if custom_prompt:
        return AgentPromptResponse(
            agent_id=agent_id,
            role=role,
            effective_prompt=custom_prompt,
            source="custom",
            custom_prompt=custom_prompt,
        )

    # Check for role-level template
    template_rows = await repo_query(
        "SELECT * FROM agent_prompt_templates WHERE role = :role",
        {"role": role},
    )

    if template_rows:
        return AgentPromptResponse(
            agent_id=agent_id,
            role=role,
            effective_prompt=template_rows[0]["prompt_text"],
            source="template",
            template_id=template_rows[0]["id"],
        )

    # Ultimate fallback
    return AgentPromptResponse(
        agent_id=agent_id,
        role=role,
        effective_prompt="You are a helpful AI assistant.",
        source="default",
    )


@router.put("/agents/{agent_id}/prompt", response_model=AgentPromptResponse)
async def set_agent_prompt(agent_id: str, body: AgentPromptUpdate):
    """
    Set or clear a custom prompt override for a specific agent.

    Pass custom_prompt=null to remove the override and revert to the role template.
    This updates the agent's system_prompt field.
    """
    # Verify agent exists
    agent_rows = await repo_query(
        "SELECT * FROM agents WHERE id = :id",
        {"id": agent_id},
    )
    if not agent_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}",
        )

    now = datetime.utcnow().isoformat()

    await repo_execute(
        "UPDATE agents SET system_prompt = :system_prompt WHERE id = :id",
        {
            "system_prompt": body.custom_prompt,  # None clears the override
            "id": agent_id,
        },
    )

    # Return the effective prompt
    return await get_agent_prompt(agent_id)
