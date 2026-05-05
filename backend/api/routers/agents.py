"""
Agent Management API Router

Endpoints for managing agent teams, individual agents, and task tracking
within the multi-agent orchestration system.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status, Depends
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

from api.dependencies.auth import get_current_active_user
from open_notebook.domain.user import User
from api.models import (
    AgentTeamCreate,
    AgentTeamResponse,
    AgentTeamListResponse,
    AgentSpawnRequest,
    AgentResponse,
    AgentListResponse,
    AgentTaskResponse,
    AgentTaskListResponse,
    TeamExecuteRequest,
    TeamExecutionResponse,
    TeamExecutionListResponse,
    SuccessResponse,
    ErrorResponse,
)
from open_notebook.database.repository import repo_query, repo_execute, repo_update, repo_delete


router = APIRouter(
    prefix="/api/agents",
    tags=["agents"],
    responses={404: {"model": ErrorResponse}},
)


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


async def _get_team_or_404(team_id: str) -> dict:
    """Fetch a team by ID or raise 404."""
    rows = await repo_query(
        "SELECT * FROM agent_teams WHERE id = :id",
        {"id": team_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Agent team not found: {team_id}")
    return rows[0]


async def _get_agent_count(team_id: str) -> int:
    """Get number of agents in a team."""
    rows = await repo_query(
        "SELECT COUNT(*) as count FROM agent_instances WHERE team_id = :team_id",
        {"team_id": team_id},
    )
    return rows[0]["count"] if rows else 0


def _row_to_team_response(row: dict, agent_count: int = 0) -> AgentTeamResponse:
    """Convert a DB row to AgentTeamResponse."""
    return AgentTeamResponse(
        id=row["id"],
        name=row["name"],
        notebook_id=row.get("notebook_id"),
        description=row.get("goal"),  # Map 'goal' column to 'description' field
        status=row.get("status", "idle"),
        config=_parse_json(row.get("config")),
        agent_count=agent_count,
        created=row.get("created"),
        updated=row.get("updated"),
    )


def _row_to_agent_response(row: dict) -> AgentResponse:
    """Convert a DB row to AgentResponse."""
    return AgentResponse(
        id=row["id"],
        team_id=row["team_id"],
        role=row["role"],
        name=row["name"],
        status=row.get("status", "idle"),
        system_prompt=row.get("system_prompt"),
        model_override=row.get("model_override"),
        tool_ids=_parse_json(row.get("tool_ids")),
        config=_parse_json(row.get("config")),
        last_active=row.get("last_active"),
        created=row.get("created"),
    )


def _row_to_task_response(row: dict) -> AgentTaskResponse:
    """Convert a DB row to AgentTaskResponse."""
    return AgentTaskResponse(
        id=row["id"],
        team_id=row["team_id"],
        assigned_agent_id=row.get("assigned_agent_id"),
        task_type=row["task_type"],
        description=row["description"],
        status=row.get("status", "pending"),
        input_data=_parse_json(row.get("input_data")),
        output_data=_parse_json(row.get("output_data")),
        dependencies=_parse_json(row.get("dependencies")),
        error=row.get("error"),
        started_at=row.get("started_at"),
        completed_at=row.get("completed_at"),
        created=row.get("created"),
    )


# ============================================================================
# Team Endpoints
# ============================================================================

@router.post("/teams", response_model=AgentTeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    body: AgentTeamCreate,
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new agent team, optionally for a notebook.

    An agent team is a group of specialized agents that collaborate
    to answer complex queries using orchestrated workflows.

    Requires JWT authentication. Teams are owned by the creating user.

    Example:
        POST /api/agents/teams
        {
            "name": "Research Team",
            "notebook_id": "nb-123",  # Optional
            "description": "Multi-agent team for deep research",
            "config": {"max_iterations": 10, "timeout_seconds": 300}
        }
    """
    # Verify notebook exists if provided
    if body.notebook_id:
        nb_rows = await repo_query(
            "SELECT id FROM notebooks WHERE id = :id",
            {"id": body.notebook_id},
        )
        if not nb_rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notebook not found: {body.notebook_id}",
            )

    now = datetime.utcnow().isoformat()
    team_id = str(uuid.uuid4())

    data = {
        "id": team_id,
        "name": body.name,
        "notebook_id": body.notebook_id,
        "goal": body.description,  # Map 'description' field to 'goal' column
        "status": "idle",
        "config": json.dumps(body.config) if body.config else None,
        "created_by": current_user.id,  # Track ownership
        "created": now,
        "updated": now,
    }

    await repo_execute(
        """INSERT INTO agent_teams (id, name, notebook_id, goal, status, config, created_by, created, updated)
           VALUES (:id, :name, :notebook_id, :goal, :status, :config, :created_by, :created, :updated)""",
        data,
    )

    # Spawn agents if provided in agent_configs
    agent_count = 0
    spawned_agents = []
    if body.agent_configs:
        for agent_config in body.agent_configs:
            agent_id = str(uuid.uuid4())
            agent_name = agent_config.get("name", f"{agent_config.get('role', 'agent').title()} Agent")

            # Map frontend agent_config fields to backend schema
            agent_data = {
                "id": agent_id,
                "team_id": team_id,
                "role": agent_config.get("role", "custom"),
                "name": agent_name,
                "status": "idle",
                "system_prompt": agent_config.get("description"),  # Use description as system prompt
                "model_override": agent_config.get("model"),
                "tool_ids": json.dumps(agent_config.get("tools", [])) if agent_config.get("tools") else None,
                "config": json.dumps({"capabilities": agent_config.get("capabilities", [])}) if agent_config.get("capabilities") else None,
                "last_active": None,
                "created": now,
            }

            await repo_execute(
                """INSERT INTO agent_instances (id, team_id, role, name, status, system_prompt, model_override, tool_ids, config, last_active, created)
                   VALUES (:id, :team_id, :role, :name, :status, :system_prompt, :model_override, :tool_ids, :config, :last_active, :created)""",
                agent_data,
            )

            # Create response for this agent
            spawned_agents.append(AgentResponse(
                id=agent_id,
                team_id=team_id,
                role=agent_config.get("role", "custom"),
                name=agent_name,
                status="idle",
                system_prompt=agent_config.get("description"),
                model_override=agent_config.get("model"),
                tool_ids=agent_config.get("tools", []),
                config={"capabilities": agent_config.get("capabilities", [])},
                last_active=None,
                created=now,
            ))
            agent_count += 1

    return AgentTeamResponse(
        id=team_id,
        name=body.name,
        notebook_id=body.notebook_id,
        description=body.description,
        status="idle",
        config=body.config,
        agent_count=agent_count,
        agents=spawned_agents,
        created=now,
        updated=now,
    )


@router.get("/teams", response_model=AgentTeamListResponse)
async def list_teams(
    notebook_id: Optional[str] = Query(None, description="Filter by notebook ID"),
    current_user: User = Depends(get_current_active_user)
):
    """
    List agent teams, optionally filtered by notebook.

    Returns teams owned by the current user (or all if superadmin).

    Example:
        GET /api/agents/teams?notebook_id=nb-123
    """
    sql = "SELECT * FROM agent_teams WHERE created_by = :created_by"
    params: dict = {"created_by": current_user.id}

    # Superadmins can see all teams
    if current_user.is_superadmin:
        sql = "SELECT * FROM agent_teams"
        params = {}

    if notebook_id:
        if current_user.is_superadmin:
            sql += " WHERE notebook_id = :notebook_id"
        else:
            sql += " AND notebook_id = :notebook_id"
        params["notebook_id"] = notebook_id

    sql += " ORDER BY created DESC"

    rows = await repo_query(sql, params)

    teams = []
    for row in rows:
        count = await _get_agent_count(row["id"])

        # Fetch agents for this team
        agent_rows = await repo_query(
            "SELECT * FROM agent_instances WHERE team_id = :team_id ORDER BY created ASC",
            {"team_id": row["id"]},
        )
        agents = [_row_to_agent_response(r) for r in agent_rows]

        team_response = _row_to_team_response(row, count)
        team_response.agents = agents
        teams.append(team_response)

    return AgentTeamListResponse(teams=teams, total=len(teams))


@router.get("/teams/{team_id}", response_model=AgentTeamResponse)
async def get_team(
    team_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get details of a specific agent team.

    Example:
        GET /api/agents/teams/abc-123
    """
    row = await _get_team_or_404(team_id)

    # Verify ownership
    if row["created_by"] != current_user.id and not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own teams"
        )
    count = await _get_agent_count(team_id)

    # Fetch agents for this team
    agent_rows = await repo_query(
        "SELECT * FROM agent_instances WHERE team_id = :team_id ORDER BY created ASC",
        {"team_id": team_id},
    )
    agents = [_row_to_agent_response(r) for r in agent_rows]

    team_response = _row_to_team_response(row, count)
    team_response.agents = agents
    return team_response


@router.put("/teams/{team_id}", response_model=AgentTeamResponse)
async def update_team(
    team_id: str,
    body: AgentTeamCreate,
    current_user: User = Depends(get_current_active_user)
):
    """
    Update an agent team's configuration and agents.

    This allows editing the team name, description, config, and the full
    list of agents. Existing agents not in agent_configs will be removed,
    and new agents will be spawned.

    Example:
        PUT /api/agents/teams/abc-123
        {
            "name": "Updated Research Team",
            "description": "Enhanced multi-agent team",
            "config": {"max_iterations": 15},
            "agent_configs": [
                {
                    "role": "researcher",
                    "name": "Enhanced Researcher",
                    "description": "Searches for information",
                    "model": "gpt-4",
                    "tools": ["search_tool"],
                    "capabilities": ["search", "analysis"]
                }
            ]
        }
    """
    # Verify team exists
    team_row = await _get_team_or_404(team_id)

    # Verify ownership
    if team_row["owner_user_id"] != current_user.id and not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own teams"
        )

    # Verify notebook exists if changed
    if body.notebook_id and body.notebook_id != team_row.get("notebook_id"):
        nb_rows = await repo_query(
            "SELECT id FROM notebooks WHERE id = :id",
            {"id": body.notebook_id},
        )
        if not nb_rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notebook not found: {body.notebook_id}",
            )

    now = datetime.utcnow().isoformat()

    # Update team
    update_data = {
        "id": team_id,
        "name": body.name,
        "notebook_id": body.notebook_id,
        "goal": body.description,
        "config": json.dumps(body.config) if body.config else None,
        "updated": now,
    }

    await repo_execute(
        """UPDATE agent_teams
           SET name = :name, notebook_id = :notebook_id, goal = :goal,
               config = :config, updated = :updated
           WHERE id = :id""",
        update_data,
    )

    # Delete existing agents
    await repo_execute(
        "DELETE FROM agent_instances WHERE team_id = :team_id",
        {"team_id": team_id},
    )

    # Spawn new agents if provided
    agent_count = 0
    spawned_agents = []

    if body.agent_configs:
        for agent_config in body.agent_configs:
            agent_id = str(uuid.uuid4())
            agent_name = agent_config.get("name", f"{agent_config.get('role', 'agent').title()} Agent")

            agent_data = {
                "id": agent_id,
                "team_id": team_id,
                "role": agent_config.get("role", "custom"),
                "name": agent_name,
                "status": "idle",
                "system_prompt": agent_config.get("description"),
                "model_override": agent_config.get("model"),
                "tool_ids": json.dumps(agent_config.get("tools", [])) if agent_config.get("tools") else None,
                "config": json.dumps({"capabilities": agent_config.get("capabilities", [])}) if agent_config.get("capabilities") else None,
                "last_active": None,
                "created": now,
            }

            await repo_execute(
                """INSERT INTO agent_instances (id, team_id, role, name, status, system_prompt, model_override, tool_ids, config, last_active, created)
                   VALUES (:id, :team_id, :role, :name, :status, :system_prompt, :model_override, :tool_ids, :config, :last_active, :created)""",
                agent_data,
            )

            spawned_agents.append(
                AgentResponse(
                    id=agent_id,
                    team_id=team_id,
                    role=agent_config.get("role", "custom"),
                    name=agent_name,
                    status="idle",
                    system_prompt=agent_config.get("description"),
                    model_override=agent_config.get("model"),
                    tool_ids=agent_config.get("tools", []),
                    config={"capabilities": agent_config.get("capabilities", [])} if agent_config.get("capabilities") else None,
                    created=now,
                )
            )
            agent_count += 1

    return AgentTeamResponse(
        id=team_id,
        name=body.name,
        notebook_id=body.notebook_id,
        description=body.description,
        status=team_row.get("status", "idle"),
        config=body.config,
        agent_count=agent_count,
        agents=spawned_agents,
        created=team_row.get("created"),
        updated=now,
    )


@router.delete("/teams/{team_id}", response_model=SuccessResponse)
async def delete_team(
    team_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete an agent team and all its agents and tasks.

    Example:
        DELETE /api/agents/teams/abc-123
    """
    team = await _get_team_or_404(team_id)

    # Verify ownership
    if team["created_by"] != current_user.id and not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own teams"
        )

    # Cascade deletes agents and tasks via FK constraints,
    # but do it explicitly for safety
    await repo_execute(
        "DELETE FROM agent_tasks WHERE team_id = :team_id",
        {"team_id": team_id},
    )
    await repo_execute(
        "DELETE FROM agent_instances WHERE team_id = :team_id",
        {"team_id": team_id},
    )
    await repo_delete("agent_teams", team_id)

    return SuccessResponse(message=f"Agent team {team_id} deleted")


# ============================================================================
# Evaluation Configuration Endpoints
# ============================================================================

@router.post("/teams/{team_id}/evaluation/config", response_model=SuccessResponse)
async def create_evaluation_config(
    team_id: str,
    enabled: bool = True,
    auto_evaluate: bool = True,
    scope: str = "all",
    scoring_scale: str = "0-10",
    current_user: User = Depends(get_current_active_user)
):
    """Create or update evaluation configuration for a team."""
    from api.services.evaluation_service import get_evaluation_service

    team = await _get_team_or_404(team_id)
    if team["created_by"] != current_user.id and not current_user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    service = await get_evaluation_service()
    existing_config = await service.get_evaluation_config(team_id)

    if existing_config:
        await service.update_evaluation_config(
            team_id=team_id,
            enabled=enabled,
            auto_evaluate=auto_evaluate,
            scope=scope,
            scoring_scale=scoring_scale
        )
    else:
        await service.create_evaluation_config(
            team_id=team_id,
            enabled=enabled,
            auto_evaluate=auto_evaluate,
            scope=scope,
            scoring_scale=scoring_scale
        )

    return SuccessResponse(message=f"Evaluation config saved for team {team_id}")


@router.get("/teams/{team_id}/evaluation/config")
async def get_evaluation_config(
    team_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get evaluation configuration for a team."""
    from api.services.evaluation_service import get_evaluation_service

    team = await _get_team_or_404(team_id)
    if team["created_by"] != current_user.id and not current_user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    service = await get_evaluation_service()
    config = await service.get_evaluation_config(team_id)

    if not config:
        return {
            "team_id": team_id,
            "enabled": False,
            "auto_evaluate": False,
            "scope": "all",
            "scoring_scale": "0-10"
        }

    return config


@router.post("/executions/{execution_id}/evaluate", response_model=SuccessResponse)
async def trigger_evaluation(
    execution_id: str,
    scope: Optional[str] = None,
    current_user: User = Depends(get_current_active_user)
):
    """Manually trigger judge evaluation."""
    from api.services.evaluation_service import get_evaluation_service
    from api.services.context import get_llm_for_credential
    from api.services.settings import get_setting
    from api.routers.credentials import _credentials_store

    exec_rows = await repo_query(
        "SELECT * FROM agent_executions WHERE id = :id",
        {"id": execution_id}
    )
    if not exec_rows:
        raise HTTPException(status_code=404, detail=f"Execution not found")

    execution = exec_rows[0]
    team = await _get_team_or_404(execution["team_id"])
    if team["created_by"] != current_user.id and not current_user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    # Get LLM
    language_model_id = await get_setting("language_model_id", "")
    if not language_model_id:
        for cred_id, cred in _credentials_store.items():
            if cred.get("is_active") and cred.get("model_type") == "language":
                language_model_id = cred_id
                break

    if not language_model_id:
        raise HTTPException(status_code=400, detail="No language model configured")

    llm = await get_llm_for_credential(language_model_id)

    # Trigger evaluation
    service = await get_evaluation_service()
    evaluation_ids = await service.trigger_evaluation(
        execution_id=execution_id,
        team_id=execution["team_id"],
        llm=llm,
        force_scope=scope
    )

    return SuccessResponse(message=f"Created {len(evaluation_ids)} evaluations")


@router.get("/executions/{execution_id}/evaluations")
async def get_execution_evaluations(
    execution_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get all evaluations for an execution."""
    from api.services.evaluation_service import get_evaluation_service

    exec_rows = await repo_query(
        "SELECT * FROM agent_executions WHERE id = :id",
        {"id": execution_id}
    )
    if not exec_rows:
        raise HTTPException(status_code=404, detail=f"Execution not found")

    execution = exec_rows[0]
    team = await _get_team_or_404(execution["team_id"])
    if team["created_by"] != current_user.id and not current_user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    service = await get_evaluation_service()
    evaluations = await service.get_evaluations_for_execution(execution_id)

    return {
        "execution_id": execution_id,
        "evaluations": evaluations,
        "total": len(evaluations)
    }


# ============================================================================
# Agent Endpoints
# ============================================================================

@router.post(
    "/teams/{team_id}/spawn",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def spawn_agent(
    team_id: str,
    body: AgentSpawnRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Spawn a new agent within a team.

    Agents are specialized workers with assigned roles (planner, researcher,
    analyst, etc.) that collaborate within a team.

    Example:
        POST /api/agents/teams/abc-123/spawn
        {
            "role": "researcher",
            "name": "Source Researcher",
            "tool_ids": ["tool-uuid-1", "tool-uuid-2"]
        }
    """
    team = await _get_team_or_404(team_id)

    # Verify ownership
    if team["created_by"] != current_user.id and not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only spawn agents in your own teams"
        )

    now = datetime.utcnow().isoformat()
    agent_id = str(uuid.uuid4())
    agent_name = body.name or f"{body.role.value.title()} Agent"

    data = {
        "id": agent_id,
        "team_id": team_id,
        "role": body.role.value,
        "name": agent_name,
        "status": "idle",
        "system_prompt": body.system_prompt,
        "model_override": body.model_override,
        "tool_ids": json.dumps(body.tool_ids) if body.tool_ids else None,
        "config": json.dumps(body.config) if body.config else None,
        "last_active": None,
        "created": now,
        "updated": now,
    }

    await repo_execute(
        """INSERT INTO agent_instances (id, team_id, role, name, status, system_prompt, model_override, tool_ids, config, last_active, created, updated)
           VALUES (:id, :team_id, :role, :name, :status, :system_prompt, :model_override, :tool_ids, :config, :last_active, :created, :updated)""",
        data,
    )

    # Update team's updated timestamp
    await repo_update("agent_teams", team_id, {"updated": now})

    return AgentResponse(
        id=agent_id,
        team_id=team_id,
        role=body.role.value,
        name=agent_name,
        status="idle",
        system_prompt=body.system_prompt,
        model_override=body.model_override,
        tool_ids=body.tool_ids,
        config=body.config,
        last_active=None,
        created=now,
    )


@router.get("/teams/{team_id}/agents", response_model=AgentListResponse)
async def list_agents(
    team_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    List all agents in a team.

    Example:
        GET /api/agents/teams/abc-123/agents
    """
    team = await _get_team_or_404(team_id)

    # Verify ownership
    if team["created_by"] != current_user.id and not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only list agents in your own teams"
        )

    rows = await repo_query(
        "SELECT * FROM agent_instances WHERE team_id = :team_id ORDER BY created ASC",
        {"team_id": team_id},
    )

    agents = [_row_to_agent_response(r) for r in rows]
    return AgentListResponse(agents=agents, total=len(agents))


@router.delete("/agents/{agent_id}", response_model=SuccessResponse)
async def delete_agent(
    agent_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Remove an agent from its team.

    Example:
        DELETE /api/agents/agents/agent-uuid
    """
    rows = await repo_query(
        "SELECT ai.*, at.created_by FROM agent_instances ai JOIN agent_teams at ON ai.team_id = at.id WHERE ai.id = :id",
        {"id": agent_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    # Verify ownership
    if rows[0]["created_by"] != current_user.id and not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete agents in your own teams"
        )

    await repo_delete("agents", agent_id)
    return SuccessResponse(message=f"Agent {agent_id} deleted")


# ============================================================================
# Task Endpoints
# ============================================================================

@router.get("/teams/{team_id}/tasks", response_model=AgentTaskListResponse)
async def list_tasks(
    team_id: str,
    task_status: Optional[str] = Query(None, alias="status", description="Filter by status"),
):
    """
    List all tasks for a team, optionally filtered by status.

    Example:
        GET /api/agents/teams/abc-123/tasks?status=in_progress
    """
    await _get_team_or_404(team_id)

    sql = "SELECT * FROM agent_tasks WHERE team_id = :team_id"
    params: dict = {"team_id": team_id}

    if task_status:
        sql += " AND status = :status"
        params["status"] = task_status

    sql += " ORDER BY created ASC"

    rows = await repo_query(sql, params)
    tasks = [_row_to_task_response(r) for r in rows]
    return AgentTaskListResponse(tasks=tasks, total=len(tasks))


@router.get("/tasks/{task_id}", response_model=AgentTaskResponse)
async def get_task(task_id: str):
    """
    Get details of a specific task.

    Example:
        GET /api/agents/tasks/task-uuid
    """
    rows = await repo_query(
        "SELECT * FROM agent_tasks WHERE id = :id",
        {"id": task_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    return _row_to_task_response(rows[0])


# ============================================================================
# Team Execution Endpoints
# ============================================================================

@router.post("/teams/{team_id}/execute", response_model=TeamExecutionResponse)
async def execute_team(
    team_id: str,
    body: TeamExecuteRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Execute team using LangGraph dynamic orchestrator.

    Features:
    - AI-driven task decomposition
    - Dynamic execution planning
    - Full observability (returns complete execution trace)
    - Result aggregation

    Example:
        POST /api/agents/teams/abc-123/execute
        {
            "query": "Analyze customer data and create report",
            "context_source_ids": ["source1", "source2"]
        }
    """
    from api.services.langgraph_orchestrator import LangGraphOrchestrator
    from api.services.settings import get_setting
    from api.routers.credentials import _credentials_store

    # Get team and verify ownership
    team = await _get_team_or_404(team_id)

    if team["created_by"] != current_user.id and not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only execute your own teams"
        )

    # Get LLM
    language_model_id = await get_setting("language_model_id", "")
    if not language_model_id or language_model_id not in _credentials_store:
        # Find first available
        for cred_id, cred in _credentials_store.items():
            if (cred.get("is_active") and
                cred.get("model_type") == "language" and
                cred.get("connection_status") in ["connected", "untested", None]):
                language_model_id = cred_id
                break

    if not language_model_id:
        raise HTTPException(
            status_code=400,
            detail="No language model configured. Please add a credential in Settings → API Keys"
        )

    # Get LLM instance
    from api.services.context import get_llm_for_credential
    llm = await get_llm_for_credential(language_model_id)

    # Get tools for team
    from api.services.tool_factory import create_tools_for_team
    tools = await create_tools_for_team(team_id, body.context_source_ids or [])

    # Create orchestrator
    execution_id = str(uuid.uuid4())
    orchestrator = LangGraphOrchestrator(
        team_id=team_id,
        execution_id=execution_id,
        llm=llm,
        tools=tools
    )

    # Execute
    result = await orchestrator.execute(
        query=body.query,
        role=team.get("goal", "researcher"),
        context_source_ids=body.context_source_ids,
        notebook_id=body.notebook_id
    )

    # Transform step_results to match WorkflowStep schema
    transformed_steps = []
    for idx, step in enumerate(result.get("steps", [])):
        transformed_steps.append({
            "step_number": idx + 1,
            "agent_id": None,
            "agent_name": None,
            "action": step.get("step", "unknown"),
            "status": "completed",
            "result": json.dumps(step.get("output")) if isinstance(step.get("output"), (dict, list)) else str(step.get("output", "")),
            "started_at": step.get("timestamp"),
            "completed_at": step.get("timestamp")
        })

    # Replace steps with transformed version
    result["steps"] = transformed_steps

    # Ensure tasks and messages exist
    result.setdefault("tasks", [])
    result.setdefault("messages", [])

    # AUTO-EVALUATION: Trigger judge evaluation if configured
    from api.services.evaluation_service import get_evaluation_service

    try:
        eval_service = await get_evaluation_service()
        should_eval = await eval_service.should_evaluate(team_id, execution_id)

        if should_eval:
            logger.info(f"Triggering auto-evaluation for execution {execution_id}")
            evaluation_ids = await eval_service.trigger_evaluation(
                execution_id=execution_id,
                team_id=team_id,
                llm=llm
            )
            logger.info(f"Auto-evaluation complete: {len(evaluation_ids)} evaluations created")
    except Exception as e:
        logger.error(f"Auto-evaluation failed: {e}")
        # Don't fail the entire execution if evaluation fails

    return TeamExecutionResponse(**result)


@router.post("/teams/{team_id}/execute/stream")
async def execute_team_stream(
    team_id: str,
    body: TeamExecuteRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Execute team using LangGraph with real-time streaming.

    Streams Server-Sent Events (SSE) for:
    - Step start/complete
    - Tool invocations
    - LLM reasoning
    - Results
    - Errors

    Example:
        POST /api/agents/teams/abc-123/execute/stream
        {
            "query": "Analyze customer data",
            "context_source_ids": ["source1"]
        }

    Returns:
        SSE stream with events:
        - event: metadata - Execution info
        - event: step_start - Step begins
        - event: step_complete - Step finishes
        - event: tool_call - Tool invocation
        - event: tool_result - Tool result
        - event: llm_call - LLM request
        - event: llm_response - LLM response
        - event: done - Execution complete
        - event: error - Error occurred
    """
    from api.services.langgraph_orchestrator import LangGraphOrchestrator
    from api.services.settings import get_setting
    from api.routers.credentials import _credentials_store

    # Get team and verify ownership
    team = await _get_team_or_404(team_id)

    if team["created_by"] != current_user.id and not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only execute your own teams"
        )

    # Get LLM
    language_model_id = await get_setting("language_model_id", "")
    if not language_model_id or language_model_id not in _credentials_store:
        # Find first available
        for cred_id, cred in _credentials_store.items():
            if (cred.get("is_active") and
                cred.get("model_type") == "language" and
                cred.get("connection_status") in ["connected", "untested", None]):
                language_model_id = cred_id
                break

    if not language_model_id:
        raise HTTPException(
            status_code=400,
            detail="No language model configured"
        )

    # Get LLM instance
    from api.services.context import get_llm_for_credential
    llm = await get_llm_for_credential(language_model_id)

    # Fetch system prompt template if specified
    system_prompt = None
    if body.prompt_role:
        prompt_rows = await repo_query(
            "SELECT prompt_text FROM agent_prompt_templates WHERE role = :role",
            {"role": body.prompt_role}
        )
        if prompt_rows:
            system_prompt = prompt_rows[0]["prompt_text"]
            print(f"[Router] Using custom system prompt from role: {body.prompt_role}")
        else:
            print(f"[Router] Warning: Prompt role '{body.prompt_role}' not found, using default")

    # Extract source IDs from agent configurations if not provided
    context_source_ids = body.context_source_ids or []
    if not context_source_ids:
        # Get agents for this team and extract source IDs from their tool_ids
        agent_rows = await repo_query(
            "SELECT id, tool_ids FROM agent_instances WHERE team_id = :team_id",
            {"team_id": team_id}
        )

        for agent in agent_rows:
            if agent.get("tool_ids"):
                try:
                    import json
                    ids = json.loads(agent["tool_ids"]) if isinstance(agent["tool_ids"], str) else agent["tool_ids"]
                    for id_val in ids:
                        if isinstance(id_val, str) and id_val.startswith("source:"):
                            source_id = id_val.replace("source:", "")
                            if source_id not in context_source_ids:
                                context_source_ids.append(source_id)
                except Exception as e:
                    print(f"Warning: Failed to parse agent tool_ids: {e}")

    print(f"[Router] Context source IDs for execution: {context_source_ids}")

    # Get tools for team
    from api.services.tool_factory import create_tools_for_team
    tools = await create_tools_for_team(team_id, context_source_ids)

    # Create orchestrator
    execution_id = str(uuid.uuid4())
    orchestrator = LangGraphOrchestrator(
        team_id=team_id,
        execution_id=execution_id,
        llm=llm,
        tools=tools,
        system_prompt=system_prompt  # Pass custom prompt if specified
    )

    async def event_generator():
        """Generate SSE events from LangGraph execution."""
        try:
            print(f"[Router] Starting event generator...")
            async for event in orchestrator.stream_execution(
                query=body.query,
                role=team.get("goal", "researcher"),
                context_source_ids=context_source_ids,
                notebook_id=body.notebook_id
            ):
                # Format as SSE
                event_type = event.get("event", "message")
                event_data = event.get("data", {})

                print(f"[Router] Yielding event: {event_type}")
                yield f"event: {event_type}\n"
                yield f"data: {json.dumps(event_data)}\n\n"

            print(f"[Router] Stream completed")

        except Exception as e:
            # Send error event
            print(f"[Router] Stream error: {e}")
            import traceback
            traceback.print_exc()
            yield f"event: error\n"
            yield f"data: {json.dumps({'error': str(e), 'type': type(e).__name__})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/teams/{team_id}/executions", response_model=TeamExecutionListResponse)
async def list_team_executions(
    team_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    List execution history for a team.

    Example:
        GET /api/agents/teams/abc-123/executions?limit=10
    """
    await _get_team_or_404(team_id)

    rows = await repo_query(
        """SELECT * FROM agent_executions
           WHERE team_id = :team_id
           ORDER BY started_at DESC
           LIMIT :limit OFFSET :offset""",
        {"team_id": team_id, "limit": limit, "offset": offset}
    )

    executions = []
    for row in rows:
        # Get steps for this execution
        step_rows = await repo_query(
            "SELECT * FROM workflow_steps WHERE execution_id = :execution_id ORDER BY step_number",
            {"execution_id": row["id"]}
        )

        # Get tasks for this execution
        task_rows = await repo_query(
            "SELECT * FROM agent_tasks WHERE execution_id = :execution_id ORDER BY created",
            {"execution_id": row["id"]}
        )

        # Get messages for this execution with agent names
        message_rows = await repo_query(
            """SELECT
                m.*,
                sender.name as sender_name,
                recipient.name as recipient_name
            FROM agent_messages m
            LEFT JOIN agent_instances sender ON m.sender_id = sender.id
            LEFT JOIN agent_instances recipient ON m.recipient_id = recipient.id
            WHERE m.execution_id = :execution_id
            ORDER BY m.created""",
            {"execution_id": row["id"]}
        )

        # If no workflow steps but we have tasks, map tasks to steps format
        if not step_rows and task_rows:
            mapped_steps = []
            for i, task in enumerate(task_rows, 1):
                mapped_steps.append({
                    "id": task["id"],
                    "step_number": i,
                    "title": task.get("description", "Untitled Task"),
                    "action": task.get("task_type", "task"),
                    "status": task["status"],
                    "output": task.get("output_data"),
                    "result": task.get("output_data"),
                    "started_at": task.get("started_at") or task.get("created"),  # Fallback to created if started_at is None
                    "completed_at": task.get("completed_at"),
                })
            step_rows = mapped_steps

        # Parse result if it's JSON with an "output" field
        result_value = row.get("result")
        if result_value and isinstance(result_value, str):
            try:
                parsed = json.loads(result_value)
                if isinstance(parsed, dict) and "output" in parsed:
                    result_value = parsed["output"]
            except (json.JSONDecodeError, TypeError):
                pass  # Keep as-is if not valid JSON

        # Transform message field names to match Pydantic model
        transformed_messages = []
        for m in message_rows:
            transformed_msg = {
                "id": m["id"],
                "team_id": m["team_id"],
                "execution_id": m.get("execution_id") or row["id"],
                "from_agent_id": m["sender_id"],
                "from_agent_name": m.get("sender_name") or ("System" if m["sender_id"] == "system" else m["sender_id"]),
                "to_agent_id": m.get("recipient_id"),
                "to_agent_name": m.get("recipient_name"),
                "message_type": m["message_type"],
                "content": m["content"],
                "created": m["created"],  # For backend Pydantic validation
                "timestamp": m["created"],  # For frontend display
                "metadata": json.loads(m["metadata"]) if m.get("metadata") and isinstance(m["metadata"], str) else m.get("metadata"),
            }
            transformed_messages.append(transformed_msg)

        execution = TeamExecutionResponse(
            id=row["id"],
            team_id=row["team_id"],
            query=row["query"],
            status=row["status"],
            steps=[dict(s) if not isinstance(s, dict) else s for s in step_rows],
            tasks=[dict(t) for t in task_rows],
            messages=transformed_messages,
            result=result_value,
            started_at=row["started_at"],
            completed_at=row.get("completed_at")
        )
        executions.append(execution)

    # Get total count
    count_rows = await repo_query(
        "SELECT COUNT(*) as count FROM agent_executions WHERE team_id = :team_id",
        {"team_id": team_id}
    )
    total = count_rows[0]["count"] if count_rows else 0

    return TeamExecutionListResponse(executions=executions, total=total)


@router.get("/executions/{execution_id}", response_model=TeamExecutionResponse)
async def get_execution(execution_id: str):
    """
    Get details of a specific execution.

    Example:
        GET /api/agents/executions/exec-uuid
    """
    rows = await repo_query(
        "SELECT * FROM agent_executions WHERE id = :id",
        {"id": execution_id}
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Execution not found: {execution_id}")

    row = rows[0]

    # Get steps
    step_rows = await repo_query(
        "SELECT * FROM workflow_steps WHERE execution_id = :execution_id ORDER BY step_number",
        {"execution_id": execution_id}
    )

    # Get tasks
    task_rows = await repo_query(
        "SELECT * FROM agent_tasks WHERE execution_id = :execution_id ORDER BY created",
        {"execution_id": execution_id}
    )

    # Get messages with agent names
    message_rows = await repo_query(
        """SELECT
            m.*,
            sender.name as sender_name,
            recipient.name as recipient_name
        FROM agent_messages m
        LEFT JOIN agent_instances sender ON m.sender_id = sender.id
        LEFT JOIN agent_instances recipient ON m.recipient_id = recipient.id
        WHERE m.execution_id = :execution_id
        ORDER BY m.created""",
        {"execution_id": execution_id}
    )
    with open("/tmp/agent_debug.log", "a") as f:
        f.write(f"[GET_EXECUTION] Found {len(message_rows)} messages for execution {execution_id}\n")

    # If no workflow steps but we have tasks, map tasks to steps format
    if not step_rows and task_rows:
        mapped_steps = []
        for i, task in enumerate(task_rows, 1):
            mapped_steps.append({
                "id": task["id"],
                "step_number": i,
                "title": task.get("description", "Untitled Task"),
                "action": task.get("task_type", "task"),
                "status": task["status"],
                "output": task.get("output_data"),
                "result": task.get("output_data"),
                "started_at": task.get("started_at") or task.get("created"),  # Fallback to created if started_at is None
                "completed_at": task.get("completed_at"),
            })
        step_rows = mapped_steps

    # Parse result if it's JSON with an "output" field
    result_value = row.get("result")
    logger.info(f"[RESULT PARSING] Raw result type: {type(result_value)}, length: {len(result_value) if result_value else 0}")

    if result_value and isinstance(result_value, str):
        try:
            parsed = json.loads(result_value)
            logger.info(f"[RESULT PARSING] Parsed JSON successfully, type: {type(parsed)}")
            if isinstance(parsed, dict) and "output" in parsed:
                result_value = parsed["output"]
                logger.info(f"[RESULT PARSING] Extracted 'output' field, new length: {len(result_value)}")
            else:
                logger.warning(f"[RESULT PARSING] JSON is dict but no 'output' field. Keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'N/A'}")
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"[RESULT PARSING] JSON parse error: {e}")
            pass  # Keep as-is if not valid JSON

    # Transform message field names to match Pydantic model
    transformed_messages = []
    for m in message_rows:
        transformed_msg = {
            "id": m["id"],
            "team_id": m["team_id"],
            "execution_id": m.get("execution_id") or row["id"],
            "from_agent_id": m["sender_id"],
            "from_agent_name": m.get("sender_name") or ("System" if m["sender_id"] == "system" else m["sender_id"]),
            "to_agent_id": m.get("recipient_id"),
            "to_agent_name": m.get("recipient_name"),
            "message_type": m["message_type"],
            "content": m["content"],
            "created": m["created"],  # For backend Pydantic validation
            "timestamp": m["created"],  # For frontend display
            "metadata": json.loads(m["metadata"]) if m.get("metadata") and isinstance(m["metadata"], str) else m.get("metadata"),
        }
        transformed_messages.append(transformed_msg)

    return TeamExecutionResponse(
        id=row["id"],
        team_id=row["team_id"],
        query=row["query"],
        status=row["status"],
        steps=[dict(s) if not isinstance(s, dict) else s for s in step_rows],
        tasks=[dict(t) for t in task_rows],
        messages=transformed_messages,
        result=result_value,
        started_at=row["started_at"],
        completed_at=row.get("completed_at")
    )


@router.delete("/executions/{execution_id}", response_model=SuccessResponse)
async def delete_execution(execution_id: str):
    """
    Delete an execution and all its associated data.

    Example:
        DELETE /api/agents/executions/exec-uuid
    """
    rows = await repo_query(
        "SELECT id FROM agent_executions WHERE id = :id",
        {"id": execution_id}
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Execution not found: {execution_id}")

    # Delete (cascades to steps, tasks, messages via FK)
    await repo_execute(
        "DELETE FROM agent_executions WHERE id = :id",
        {"id": execution_id}
    )

    return SuccessResponse(message=f"Execution {execution_id} deleted")


@router.post("/executions/{execution_id}/cancel", response_model=SuccessResponse)
async def cancel_execution(execution_id: str):
    """
    Cancel a running execution.

    Example:
        POST /api/agents/executions/exec-uuid/cancel
    """
    rows = await repo_query(
        "SELECT id, status FROM agent_executions WHERE id = :id",
        {"id": execution_id}
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Execution not found: {execution_id}")

    if rows[0]["status"] not in ["running", "pending"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel execution with status: {rows[0]['status']}"
        )

    # Update status
    await repo_execute(
        """UPDATE agent_executions
           SET status = :status, completed_at = :completed_at
           WHERE id = :id""",
        {
            "id": execution_id,
            "status": "cancelled",
            "completed_at": datetime.utcnow().isoformat()
        }
    )

    return SuccessResponse(message=f"Execution {execution_id} cancelled")


