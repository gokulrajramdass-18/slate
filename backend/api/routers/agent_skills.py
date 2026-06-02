"""
Agent Skills Management API Router

CRUD endpoints for agent skills, skill bindings (agents/roles), and execution tracking.
"""

import json
import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse

from api.models import (
    AgentSkillCreate,
    AgentSkillUpdate,
    AgentSkillResponse,
    AgentSkillListResponse,
    SkillBindingCreate,
    SkillBindingUpdate,
    SkillBindingResponse,
    SkillBindingListResponse,
    SkillExecuteRequest,
    SkillExecutionResponse,
    SkillExecutionListResponse,
    SuccessResponse,
    ErrorResponse,
)
from open_notebook.database.repository import repo_query, repo_execute


router = APIRouter(prefix="/api/agent-skills", tags=["agent-skills"])


# ============================================================================
# Helper Functions
# ============================================================================

def _parse_json(value) -> Optional[dict]:
    """Parse a JSON string field if needed."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None
    return value


def _parse_json_list(value) -> Optional[List]:
    """Parse a JSON array string field if needed."""
    if isinstance(value, str):
        try:
            result = json.loads(value)
            return result if isinstance(result, list) else None
        except (json.JSONDecodeError, TypeError):
            return None
    return value if isinstance(value, list) else None


async def _get_skill_or_404(skill_id: str) -> dict:
    """Fetch a skill by ID or raise 404."""
    rows = await repo_query(
        "SELECT * FROM agent_skills WHERE id = :id",
        {"id": skill_id},
    )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill not found: {skill_id}",
        )
    return rows[0]


async def _get_binding_or_404(binding_id: str) -> dict:
    """Fetch a skill binding by ID or raise 404."""
    rows = await repo_query(
        "SELECT * FROM agent_skill_bindings WHERE id = :id",
        {"id": binding_id},
    )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Binding not found: {binding_id}",
        )
    return rows[0]


def _row_to_skill_response(row: dict) -> AgentSkillResponse:
    """Convert a DB row to AgentSkillResponse."""
    return AgentSkillResponse(
        id=row["id"],
        name=row["name"],
        category=row["category"],
        description=row.get("description"),
        skill_type=row["skill_type"],
        definition=_parse_json(row["definition"]) or {},
        input_schema=_parse_json(row.get("input_schema")),
        output_schema=_parse_json(row.get("output_schema")),
        roles=_parse_json_list(row.get("roles")) or [],
        tags=_parse_json_list(row.get("tags")) or [],
        enabled=bool(row.get("enabled", True)),
        metadata=_parse_json(row.get("metadata")) or {},
        created=row.get("created", ""),
        updated=row.get("updated", ""),
    )


def _row_to_binding_response(row: dict) -> SkillBindingResponse:
    """Convert a DB row to SkillBindingResponse."""
    return SkillBindingResponse(
        id=row["id"],
        skill_id=row["skill_id"],
        skill_name=row.get("skill_name"),  # From JOIN
        binding_type=row["binding_type"],
        agent_id=row.get("agent_id"),
        standalone_agent_id=row.get("standalone_agent_id"),
        role=row.get("role"),
        team_id=row.get("team_id"),
        priority=row.get("priority", 0),
        config=_parse_json(row.get("config")) or {},
        enabled=bool(row.get("enabled", True)),
        created=row.get("created", ""),
        created_by=row.get("created_by"),
    )


def _row_to_execution_response(row: dict) -> SkillExecutionResponse:
    """Convert a DB row to SkillExecutionResponse."""
    return SkillExecutionResponse(
        id=row["id"],
        skill_id=row["skill_id"],
        skill_name=row.get("skill_name"),  # From JOIN
        execution_id=row["execution_id"],
        agent_id=row.get("agent_id"),
        team_id=row.get("team_id"),
        input_data=_parse_json(row.get("input_data")) or {},
        output_data=_parse_json(row.get("output_data")) or {},
        success=bool(row["success"]),
        result=_parse_json(row.get("result")),
        error=row.get("error"),
        duration_ms=row.get("duration_ms"),
        trace_id=row.get("trace_id"),
        steps=_parse_json_list(row.get("steps")) or [],
        started_at=row["started_at"],
        ended_at=row.get("ended_at"),
        created=row.get("created", ""),
    )


# ============================================================================
# 1. Discovery Endpoints
# ============================================================================

@router.get("/", response_model=AgentSkillListResponse)
async def list_skills(
    category: Optional[str] = Query(None, description="Filter by category"),
    role: Optional[str] = Query(None, description="Filter by recommended role"),
    skill_type: Optional[str] = Query(None, description="Filter by skill type"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    tags: Optional[str] = Query(None, description="Comma-separated tags to filter by"),
    search: Optional[str] = Query(None, description="Search in name and description"),
):
    """
    List all agent skills with optional filtering.

    Supports filtering by:
    - category: data_analysis, web_research, code_generation, communication, planning, custom
    - role: planner, researcher, analyst, writer, etc.
    - skill_type: tool_chain, prompt_template, workflow, custom
    - enabled: true/false
    - tags: comma-separated list
    - search: text search in name and description

    Example:
        GET /api/agent-skills?category=data_analysis&enabled=true
    """
    sql = "SELECT * FROM agent_skills WHERE 1=1"
    params = {}

    if category:
        sql += " AND category = :category"
        params["category"] = category

    if skill_type:
        sql += " AND skill_type = :skill_type"
        params["skill_type"] = skill_type

    if enabled is not None:
        sql += " AND enabled = :enabled"
        params["enabled"] = 1 if enabled else 0

    if role:
        # Search in JSON roles array
        sql += " AND roles LIKE :role"
        params["role"] = f'%"{role}"%'

    if tags:
        # Search for any of the provided tags
        tag_list = [t.strip() for t in tags.split(",")]
        tag_conditions = []
        for i, tag in enumerate(tag_list):
            tag_key = f"tag_{i}"
            tag_conditions.append(f"tags LIKE :{tag_key}")
            params[tag_key] = f'%"{tag}"%'
        if tag_conditions:
            sql += f" AND ({' OR '.join(tag_conditions)})"

    if search:
        sql += " AND (name LIKE :search OR description LIKE :search)"
        params["search"] = f"%{search}%"

    sql += " ORDER BY name ASC"

    rows = await repo_query(sql, params)
    skills = [_row_to_skill_response(r) for r in rows]

    return AgentSkillListResponse(skills=skills, total=len(skills))


@router.get("/{skill_id}", response_model=AgentSkillResponse)
async def get_skill(skill_id: str):
    """
    Get detailed information about a specific skill.

    Example:
        GET /api/agent-skills/skill-uuid-123
    """
    row = await _get_skill_or_404(skill_id)
    return _row_to_skill_response(row)


@router.get("/search", response_model=AgentSkillListResponse)
async def search_skills(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Search skills by name, description, or tags.

    Example:
        GET /api/agent-skills/search?q=data+analysis&limit=10
    """
    sql = """
        SELECT * FROM agent_skills
        WHERE enabled = 1
        AND (
            name LIKE :query
            OR description LIKE :query
            OR tags LIKE :query
        )
        ORDER BY name ASC
        LIMIT :limit
    """
    params = {"query": f"%{q}%", "limit": limit}

    rows = await repo_query(sql, params)
    skills = [_row_to_skill_response(r) for r in rows]

    return AgentSkillListResponse(skills=skills, total=len(skills))


# ============================================================================
# 2. Skill CRUD Endpoints
# ============================================================================

@router.post("/", response_model=AgentSkillResponse, status_code=status.HTTP_201_CREATED)
async def create_skill(body: AgentSkillCreate):
    """
    Create a new agent skill.

    Example:
        POST /api/agent-skills
        {
            "name": "Data Analysis Pipeline",
            "category": "data_analysis",
            "skill_type": "tool_chain",
            "definition": {
                "tools": ["hana_query", "python_analyze"],
                "flow": {"steps": [...]}
            },
            "roles": ["analyst", "researcher"],
            "tags": ["data", "analysis", "sql"]
        }
    """
    # Check for duplicate name
    existing = await repo_query(
        "SELECT id FROM agent_skills WHERE name = :name",
        {"name": body.name},
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Skill with name '{body.name}' already exists",
        )

    now = datetime.utcnow().isoformat()
    skill_id = str(uuid.uuid4())

    data = {
        "id": skill_id,
        "name": body.name,
        "category": body.category.value,
        "description": body.description,
        "skill_type": body.skill_type.value,
        "definition": json.dumps(body.definition),
        "input_schema": json.dumps(body.input_schema) if body.input_schema else None,
        "output_schema": json.dumps(body.output_schema) if body.output_schema else None,
        "roles": json.dumps(body.roles) if body.roles else "[]",
        "tags": json.dumps(body.tags) if body.tags else "[]",
        "enabled": 1 if body.enabled else 0,
        "metadata": json.dumps(body.metadata) if body.metadata else "{}",
        "created": now,
        "updated": now,
    }

    await repo_execute(
        """INSERT INTO agent_skills
           (id, name, category, description, skill_type, definition, input_schema, output_schema, roles, tags, enabled, metadata, created, updated)
           VALUES
           (:id, :name, :category, :description, :skill_type, :definition, :input_schema, :output_schema, :roles, :tags, :enabled, :metadata, :created, :updated)""",
        data,
    )

    return AgentSkillResponse(
        id=skill_id,
        name=body.name,
        category=body.category.value,
        description=body.description,
        skill_type=body.skill_type.value,
        definition=body.definition,
        input_schema=body.input_schema,
        output_schema=body.output_schema,
        roles=body.roles or [],
        tags=body.tags or [],
        enabled=body.enabled,
        metadata=body.metadata or {},
        created=now,
        updated=now,
    )


@router.put("/{skill_id}", response_model=AgentSkillResponse)
async def update_skill(skill_id: str, body: AgentSkillUpdate):
    """
    Update an existing skill.

    Example:
        PUT /api/agent-skills/skill-uuid-123
        {
            "description": "Updated description",
            "enabled": false
        }
    """
    # Verify skill exists
    skill_row = await _get_skill_or_404(skill_id)

    # Built-in skills are backed by a Python function in the in-process
    # registry (see SkillExecutor._execute_code_skill). Their `skill_type`
    # and `definition` columns are essentially decorative — the registry
    # is authoritative — so editing those fields in the DB only creates
    # drift between what the UI shows and what actually runs. Allow
    # metadata edits (name, description, category, tags, roles, enabled,
    # input/output schema, metadata) but lock the two fields whose
    # backing implementation lives in code.
    if skill_row.get("skill_type") == "builtin":
        if body.skill_type is not None and body.skill_type.value != "builtin":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Built-in skills are backed by code in the registry; "
                    "their type cannot be changed from the UI."
                ),
            )
        if body.definition is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Built-in skills' definition is provided by the "
                    "registry and cannot be edited from the UI. Edit "
                    "the metadata (name, description, tags, roles, etc.) "
                    "instead."
                ),
            )

    # Check for name conflict if updating name
    if body.name and body.name != skill_row["name"]:
        existing = await repo_query(
            "SELECT id FROM agent_skills WHERE name = :name AND id != :id",
            {"name": body.name, "id": skill_id},
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Skill with name '{body.name}' already exists",
            )

    now = datetime.utcnow().isoformat()
    updates = []
    params = {"id": skill_id, "updated": now}

    if body.name is not None:
        updates.append("name = :name")
        params["name"] = body.name

    if body.category is not None:
        updates.append("category = :category")
        params["category"] = body.category.value

    if body.description is not None:
        updates.append("description = :description")
        params["description"] = body.description

    if body.skill_type is not None:
        updates.append("skill_type = :skill_type")
        params["skill_type"] = body.skill_type.value

    if body.definition is not None:
        updates.append("definition = :definition")
        params["definition"] = json.dumps(body.definition)

    if body.input_schema is not None:
        updates.append("input_schema = :input_schema")
        params["input_schema"] = json.dumps(body.input_schema)

    if body.output_schema is not None:
        updates.append("output_schema = :output_schema")
        params["output_schema"] = json.dumps(body.output_schema)

    if body.roles is not None:
        updates.append("roles = :roles")
        params["roles"] = json.dumps(body.roles)

    if body.tags is not None:
        updates.append("tags = :tags")
        params["tags"] = json.dumps(body.tags)

    if body.enabled is not None:
        updates.append("enabled = :enabled")
        params["enabled"] = 1 if body.enabled else 0

    if body.metadata is not None:
        updates.append("metadata = :metadata")
        params["metadata"] = json.dumps(body.metadata)

    if updates:
        updates.append("updated = :updated")
        sql = f"UPDATE agent_skills SET {', '.join(updates)} WHERE id = :id"
        await repo_execute(sql, params)

    # Fetch updated skill
    updated_row = await _get_skill_or_404(skill_id)
    return _row_to_skill_response(updated_row)


@router.delete("/{skill_id}", response_model=SuccessResponse)
async def delete_skill(skill_id: str):
    """
    Delete a skill and all its bindings.

    Example:
        DELETE /api/agent-skills/skill-uuid-123
    """
    # Verify skill exists
    await _get_skill_or_404(skill_id)

    # Delete skill (bindings cascade)
    await repo_execute(
        "DELETE FROM agent_skills WHERE id = :id",
        {"id": skill_id},
    )

    return SuccessResponse(
        success=True,
        message=f"Skill {skill_id} deleted successfully",
    )


# ============================================================================
# 3. Bindings - Agents
# ============================================================================

@router.post("/agents/{agent_id}/skills", response_model=SkillBindingResponse, status_code=status.HTTP_201_CREATED)
async def bind_skill_to_agent(agent_id: str, body: SkillBindingCreate):
    """
    Bind a skill to a specific agent.

    The binding_type should be 'agent' or 'standalone_agent'.

    Example:
        POST /api/agent-skills/agents/agent-uuid-123/skills
        {
            "skill_id": "skill-uuid-456",
            "binding_type": "agent",
            "agent_id": "agent-uuid-123",
            "priority": 5,
            "config": {"custom_param": "value"}
        }
    """
    # Validate binding type
    if body.binding_type not in ["agent", "standalone_agent"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="binding_type must be 'agent' or 'standalone_agent' for this endpoint",
        )

    # Verify skill exists
    await _get_skill_or_404(body.skill_id)

    # Verify agent exists
    if body.binding_type == "agent":
        agent_rows = await repo_query(
            "SELECT id FROM agents WHERE id = :id",
            {"id": agent_id},
        )
        if not agent_rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent not found: {agent_id}",
            )
    else:  # standalone_agent
        agent_rows = await repo_query(
            "SELECT id FROM standalone_agents WHERE id = :id",
            {"id": agent_id},
        )
        if not agent_rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Standalone agent not found: {agent_id}",
            )

    # Check for duplicate binding
    check_sql = "SELECT id FROM agent_skill_bindings WHERE skill_id = :skill_id"
    check_params = {"skill_id": body.skill_id}

    if body.binding_type == "agent":
        check_sql += " AND agent_id = :agent_id"
        check_params["agent_id"] = agent_id
    else:
        check_sql += " AND standalone_agent_id = :standalone_agent_id"
        check_params["standalone_agent_id"] = agent_id

    existing = await repo_query(check_sql, check_params)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This skill is already bound to this agent",
        )

    # Create binding
    now = datetime.utcnow().isoformat()
    binding_id = str(uuid.uuid4())

    data = {
        "id": binding_id,
        "skill_id": body.skill_id,
        "binding_type": body.binding_type,
        "agent_id": agent_id if body.binding_type == "agent" else None,
        "standalone_agent_id": agent_id if body.binding_type == "standalone_agent" else None,
        "role": None,
        "team_id": None,
        "priority": body.priority,
        "config": json.dumps(body.config) if body.config else "{}",
        "enabled": 1 if body.enabled else 0,
        "created": now,
        "created_by": body.created_by if hasattr(body, "created_by") else None,
    }

    await repo_execute(
        """INSERT INTO agent_skill_bindings
           (id, skill_id, binding_type, agent_id, standalone_agent_id, role, team_id, priority, config, enabled, created, created_by)
           VALUES
           (:id, :skill_id, :binding_type, :agent_id, :standalone_agent_id, :role, :team_id, :priority, :config, :enabled, :created, :created_by)""",
        data,
    )

    # Fetch skill name for response
    skill_row = await _get_skill_or_404(body.skill_id)

    return SkillBindingResponse(
        id=binding_id,
        skill_id=body.skill_id,
        skill_name=skill_row["name"],
        binding_type=body.binding_type,
        agent_id=agent_id if body.binding_type == "agent" else None,
        standalone_agent_id=agent_id if body.binding_type == "standalone_agent" else None,
        role=None,
        team_id=None,
        priority=body.priority,
        config=body.config or {},
        enabled=body.enabled,
        created=now,
        created_by=data["created_by"],
    )


@router.get("/agents/{agent_id}/skills", response_model=SkillBindingListResponse)
async def list_agent_skills(
    agent_id: str,
    binding_type: str = Query("agent", description="'agent' or 'standalone_agent'"),
    enabled_only: bool = Query(True, description="Only return enabled bindings"),
):
    """
    List all skills bound to a specific agent.

    Example:
        GET /api/agent-skills/agents/agent-uuid-123/skills?binding_type=agent
    """
    sql = """
        SELECT b.*, s.name as skill_name
        FROM agent_skill_bindings b
        JOIN agent_skills s ON b.skill_id = s.id
        WHERE 1=1
    """
    params = {}

    if binding_type == "agent":
        sql += " AND b.agent_id = :agent_id AND b.binding_type = 'agent'"
        params["agent_id"] = agent_id
    elif binding_type == "standalone_agent":
        sql += " AND b.standalone_agent_id = :agent_id AND b.binding_type = 'standalone_agent'"
        params["agent_id"] = agent_id
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="binding_type must be 'agent' or 'standalone_agent'",
        )

    if enabled_only:
        sql += " AND b.enabled = 1"

    sql += " ORDER BY b.priority DESC, s.name ASC"

    rows = await repo_query(sql, params)
    bindings = [_row_to_binding_response(r) for r in rows]

    return SkillBindingListResponse(bindings=bindings, total=len(bindings))


@router.delete("/agents/{agent_id}/skills/{skill_id}", response_model=SuccessResponse)
async def unbind_skill_from_agent(
    agent_id: str,
    skill_id: str,
    binding_type: str = Query("agent", description="'agent' or 'standalone_agent'"),
):
    """
    Remove a skill binding from an agent.

    Example:
        DELETE /api/agent-skills/agents/agent-uuid-123/skills/skill-uuid-456?binding_type=agent
    """
    # Find the binding
    sql = "SELECT id FROM agent_skill_bindings WHERE skill_id = :skill_id"
    params = {"skill_id": skill_id}

    if binding_type == "agent":
        sql += " AND agent_id = :agent_id AND binding_type = 'agent'"
        params["agent_id"] = agent_id
    elif binding_type == "standalone_agent":
        sql += " AND standalone_agent_id = :agent_id AND binding_type = 'standalone_agent'"
        params["agent_id"] = agent_id
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="binding_type must be 'agent' or 'standalone_agent'",
        )

    rows = await repo_query(sql, params)
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Binding not found",
        )

    binding_id = rows[0]["id"]

    # Delete binding
    await repo_execute(
        "DELETE FROM agent_skill_bindings WHERE id = :id",
        {"id": binding_id},
    )

    return SuccessResponse(
        success=True,
        message=f"Skill unbound from agent successfully",
    )


# ============================================================================
# 4. Bindings - Roles
# ============================================================================

@router.post("/roles/{role}/skills", response_model=SkillBindingResponse, status_code=status.HTTP_201_CREATED)
async def bind_skill_to_role(role: str, body: SkillBindingCreate):
    """
    Bind a skill to all agents with a specific role.

    Example:
        POST /api/agent-skills/roles/analyst/skills
        {
            "skill_id": "skill-uuid-456",
            "binding_type": "role",
            "role": "analyst",
            "priority": 10
        }
    """
    # Validate binding type
    if body.binding_type != "role":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="binding_type must be 'role' for this endpoint",
        )

    # Verify skill exists
    await _get_skill_or_404(body.skill_id)

    # Check for duplicate binding
    existing = await repo_query(
        "SELECT id FROM agent_skill_bindings WHERE skill_id = :skill_id AND role = :role",
        {"skill_id": body.skill_id, "role": role},
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This skill is already bound to role '{role}'",
        )

    # Create binding
    now = datetime.utcnow().isoformat()
    binding_id = str(uuid.uuid4())

    data = {
        "id": binding_id,
        "skill_id": body.skill_id,
        "binding_type": "role",
        "agent_id": None,
        "standalone_agent_id": None,
        "role": role,
        "team_id": None,
        "priority": body.priority,
        "config": json.dumps(body.config) if body.config else "{}",
        "enabled": 1 if body.enabled else 0,
        "created": now,
        "created_by": body.created_by if hasattr(body, "created_by") else None,
    }

    await repo_execute(
        """INSERT INTO agent_skill_bindings
           (id, skill_id, binding_type, agent_id, standalone_agent_id, role, team_id, priority, config, enabled, created, created_by)
           VALUES
           (:id, :skill_id, :binding_type, :agent_id, :standalone_agent_id, :role, :team_id, :priority, :config, :enabled, :created, :created_by)""",
        data,
    )

    # Fetch skill name for response
    skill_row = await _get_skill_or_404(body.skill_id)

    return SkillBindingResponse(
        id=binding_id,
        skill_id=body.skill_id,
        skill_name=skill_row["name"],
        binding_type="role",
        agent_id=None,
        standalone_agent_id=None,
        role=role,
        team_id=None,
        priority=body.priority,
        config=body.config or {},
        enabled=body.enabled,
        created=now,
        created_by=data["created_by"],
    )


@router.get("/roles/{role}/skills", response_model=SkillBindingListResponse)
async def list_role_skills(
    role: str,
    enabled_only: bool = Query(True, description="Only return enabled bindings"),
):
    """
    List all skills bound to a specific role.

    Example:
        GET /api/agent-skills/roles/analyst/skills
    """
    sql = """
        SELECT b.*, s.name as skill_name
        FROM agent_skill_bindings b
        JOIN agent_skills s ON b.skill_id = s.id
        WHERE b.role = :role AND b.binding_type = 'role'
    """
    params = {"role": role}

    if enabled_only:
        sql += " AND b.enabled = 1"

    sql += " ORDER BY b.priority DESC, s.name ASC"

    rows = await repo_query(sql, params)
    bindings = [_row_to_binding_response(r) for r in rows]

    return SkillBindingListResponse(bindings=bindings, total=len(bindings))


@router.delete("/roles/{role}/skills/{skill_id}", response_model=SuccessResponse)
async def unbind_skill_from_role(role: str, skill_id: str):
    """
    Remove a skill binding from a role.

    Example:
        DELETE /api/agent-skills/roles/analyst/skills/skill-uuid-456
    """
    # Find the binding
    rows = await repo_query(
        "SELECT id FROM agent_skill_bindings WHERE skill_id = :skill_id AND role = :role AND binding_type = 'role'",
        {"skill_id": skill_id, "role": role},
    )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Binding not found",
        )

    binding_id = rows[0]["id"]

    # Delete binding
    await repo_execute(
        "DELETE FROM agent_skill_bindings WHERE id = :id",
        {"id": binding_id},
    )

    return SuccessResponse(
        success=True,
        message=f"Skill unbound from role '{role}' successfully",
    )


# ============================================================================
# 5. Execution
# ============================================================================

@router.post("/agents/{agent_id}/skills/{skill_id}/execute", response_model=SkillExecutionResponse, status_code=status.HTTP_202_ACCEPTED)
async def execute_skill(
    agent_id: str,
    skill_id: str,
    body: SkillExecuteRequest,
    binding_type: str = Query("agent", description="'agent' or 'standalone_agent'"),
):
    """
    Execute a skill for a specific agent.

    This is a placeholder endpoint that creates an execution record.
    Actual skill execution would be handled by a background worker or agent runtime.

    Example:
        POST /api/agent-skills/agents/agent-uuid-123/skills/skill-uuid-456/execute
        {
            "input_data": {"query": "SELECT * FROM users"},
            "config_override": {"timeout": 30}
        }
    """
    # Verify skill exists
    skill_row = await _get_skill_or_404(skill_id)

    # Verify agent exists
    if binding_type == "agent":
        agent_rows = await repo_query(
            "SELECT id FROM agents WHERE id = :id",
            {"id": agent_id},
        )
    else:
        agent_rows = await repo_query(
            "SELECT id FROM standalone_agents WHERE id = :id",
            {"id": agent_id},
        )

    if not agent_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found: {agent_id}",
        )

    # Create execution record
    now = datetime.utcnow().isoformat()
    execution_id = str(uuid.uuid4())
    unique_exec_id = str(uuid.uuid4())

    data = {
        "id": execution_id,
        "skill_id": skill_id,
        "execution_id": unique_exec_id,
        "agent_id": agent_id,
        "team_id": None,
        "input_data": json.dumps(body.input_data),
        "output_data": None,
        "success": 0,
        "result": None,
        "error": None,
        "duration_ms": None,
        "trace_id": str(uuid.uuid4()),
        "steps": json.dumps([]),
        "started_at": now,
        "ended_at": None,
        "created": now,
    }

    await repo_execute(
        """INSERT INTO agent_skill_executions
           (id, skill_id, execution_id, agent_id, team_id, input_data, output_data, success, result, error, duration_ms, trace_id, steps, started_at, ended_at, created)
           VALUES
           (:id, :skill_id, :execution_id, :agent_id, :team_id, :input_data, :output_data, :success, :result, :error, :duration_ms, :trace_id, :steps, :started_at, :ended_at, :created)""",
        data,
    )

    return SkillExecutionResponse(
        id=execution_id,
        skill_id=skill_id,
        skill_name=skill_row["name"],
        execution_id=unique_exec_id,
        agent_id=agent_id,
        team_id=None,
        input_data=body.input_data,
        output_data={},
        success=False,
        result=None,
        error=None,
        duration_ms=None,
        trace_id=data["trace_id"],
        steps=[],
        started_at=now,
        ended_at=None,
        created=now,
    )


@router.get("/{skill_id}/executions", response_model=SkillExecutionListResponse)
async def list_skill_executions(
    skill_id: str,
    agent_id: Optional[str] = Query(None, description="Filter by agent"),
    success: Optional[bool] = Query(None, description="Filter by success status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    List execution history for a specific skill.

    Example:
        GET /api/agent-skills/skill-uuid-123/executions?limit=20
    """
    sql = """
        SELECT e.*, s.name as skill_name
        FROM agent_skill_executions e
        JOIN agent_skills s ON e.skill_id = s.id
        WHERE e.skill_id = :skill_id
    """
    params = {"skill_id": skill_id, "limit": limit, "offset": offset}

    if agent_id:
        sql += " AND e.agent_id = :agent_id"
        params["agent_id"] = agent_id

    if success is not None:
        sql += " AND e.success = :success"
        params["success"] = 1 if success else 0

    sql += " ORDER BY e.started_at DESC LIMIT :limit OFFSET :offset"

    rows = await repo_query(sql, params)
    executions = [_row_to_execution_response(r) for r in rows]

    # Get total count
    count_sql = "SELECT COUNT(*) as total FROM agent_skill_executions WHERE skill_id = :skill_id"
    count_params = {"skill_id": skill_id}
    if agent_id:
        count_sql += " AND agent_id = :agent_id"
        count_params["agent_id"] = agent_id
    if success is not None:
        count_sql += " AND success = :success"
        count_params["success"] = 1 if success else 0

    count_rows = await repo_query(count_sql, count_params)
    total = count_rows[0]["total"] if count_rows else 0

    return SkillExecutionListResponse(executions=executions, total=total)


# ============================================================================
# 6. Bindings Management
# ============================================================================

@router.get("/bindings", response_model=SkillBindingListResponse)
async def list_all_bindings(
    skill_id: Optional[str] = Query(None, description="Filter by skill"),
    binding_type: Optional[str] = Query(None, description="Filter by binding type"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    List all skill bindings across agents, roles, and teams.

    Example:
        GET /api/agent-skills/bindings?binding_type=role&enabled=true
    """
    sql = """
        SELECT b.*, s.name as skill_name
        FROM agent_skill_bindings b
        JOIN agent_skills s ON b.skill_id = s.id
        WHERE 1=1
    """
    params = {"limit": limit, "offset": offset}

    if skill_id:
        sql += " AND b.skill_id = :skill_id"
        params["skill_id"] = skill_id

    if binding_type:
        sql += " AND b.binding_type = :binding_type"
        params["binding_type"] = binding_type

    if enabled is not None:
        sql += " AND b.enabled = :enabled"
        params["enabled"] = 1 if enabled else 0

    sql += " ORDER BY b.created DESC LIMIT :limit OFFSET :offset"

    rows = await repo_query(sql, params)
    bindings = [_row_to_binding_response(r) for r in rows]

    return SkillBindingListResponse(bindings=bindings, total=len(bindings))


@router.patch("/bindings/{binding_id}", response_model=SkillBindingResponse)
async def update_binding(binding_id: str, body: SkillBindingUpdate):
    """
    Update a skill binding's priority, config, or enabled status.

    Example:
        PATCH /api/agent-skills/bindings/binding-uuid-123
        {
            "priority": 15,
            "enabled": false
        }
    """
    # Verify binding exists
    binding_row = await _get_binding_or_404(binding_id)

    updates = []
    params = {"id": binding_id}

    if body.priority is not None:
        updates.append("priority = :priority")
        params["priority"] = body.priority

    if body.config is not None:
        updates.append("config = :config")
        params["config"] = json.dumps(body.config)

    if body.enabled is not None:
        updates.append("enabled = :enabled")
        params["enabled"] = 1 if body.enabled else 0

    if updates:
        sql = f"UPDATE agent_skill_bindings SET {', '.join(updates)} WHERE id = :id"
        await repo_execute(sql, params)

    # Fetch updated binding with skill name
    updated_rows = await repo_query(
        """SELECT b.*, s.name as skill_name
           FROM agent_skill_bindings b
           JOIN agent_skills s ON b.skill_id = s.id
           WHERE b.id = :id""",
        {"id": binding_id},
    )

    return _row_to_binding_response(updated_rows[0])


@router.delete("/bindings/{binding_id}", response_model=SuccessResponse)
async def delete_binding(binding_id: str):
    """
    Delete a specific skill binding.

    Example:
        DELETE /api/agent-skills/bindings/binding-uuid-123
    """
    # Verify binding exists
    await _get_binding_or_404(binding_id)

    # Delete binding
    await repo_execute(
        "DELETE FROM agent_skill_bindings WHERE id = :id",
        {"id": binding_id},
    )

    return SuccessResponse(
        success=True,
        message=f"Binding {binding_id} deleted successfully",
    )
