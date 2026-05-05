"""
Agent Skill Executor Service

Helper service for executing agent skills in the context of standalone agents.
Builds SkillContext, invokes skill handlers, and stores execution records.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from open_notebook.agents.skills import (
    SkillContext,
    SkillExecutionResult,
    get_skill_executor,
    get_skill_registry
)
from open_notebook.database.repository import repo_execute

logger = logging.getLogger(__name__)


async def execute_agent_skill(
    skill_id: str,
    agent_id: str,
    agent_role: str,
    input_data: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
    llm: Optional[Any] = None,
    database: Optional[Any] = None,
    team_id: Optional[str] = None
) -> SkillExecutionResult:
    """
    Execute a skill in the context of an agent.

    Args:
        skill_id: ID of skill to execute
        agent_id: ID of standalone agent executing the skill
        agent_role: Agent role (planner, researcher, etc.)
        input_data: Input parameters for the skill
        config: Optional config overrides
        llm: Optional LLM instance
        database: Optional database connection
        team_id: Optional team ID if agent is part of a team

    Returns:
        SkillExecutionResult with success status, result, and timing
    """
    # Validate skill exists
    registry = get_skill_registry()
    skill = registry.get_skill(skill_id)

    if not skill:
        logger.error(f"Skill not found: {skill_id}")
        return SkillExecutionResult(
            skill_id=skill_id,
            execution_id=str(uuid.uuid4()),
            success=False,
            result=None,
            error=f"Skill not found: {skill_id}"
        )

    # Create execution record ID
    execution_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    # Build SkillContext
    context = SkillContext(
        agent_id=agent_id,
        agent_role=agent_role,
        team_id=team_id,
        skill_id=skill_id,
        execution_id=execution_id,
        input_data=input_data,
        config={**skill.default_config, **(config or {})},
        llm=llm,
        database=database
    )

    logger.info(
        f"Executing skill {skill_id} for agent {agent_id} "
        f"(role: {agent_role}, execution: {execution_id})"
    )

    # Execute skill
    executor = get_skill_executor()
    result = await executor.execute(skill_id, context)

    # Store execution in database
    try:
        await repo_execute(
            """
            INSERT INTO agent_skill_executions (
                id, skill_id, agent_id, team_id, execution_id,
                input_data, output_data, success, result, error,
                duration_ms, steps, started_at, ended_at, created
            ) VALUES (
                :id, :skill_id, :agent_id, :team_id, :execution_id,
                :input_data, :output_data, :success, :result, :error,
                :duration_ms, :steps, :started_at, :ended_at, :created
            )
            """,
            {
                "id": str(uuid.uuid4()),
                "skill_id": skill_id,
                "agent_id": agent_id,
                "team_id": team_id,
                "execution_id": execution_id,
                "input_data": json.dumps(input_data),
                "output_data": json.dumps(result.result if result.success else None),
                "success": 1 if result.success else 0,
                "result": json.dumps(result.result) if result.success else None,
                "error": result.error,
                "duration_ms": result.duration_ms,
                "steps": json.dumps(result.steps),
                "started_at": now,
                "ended_at": datetime.utcnow().isoformat(),
                "created": now
            }
        )
        logger.info(f"Stored skill execution record for {execution_id}")
    except Exception as e:
        logger.error(f"Failed to store skill execution record: {e}")
        # Don't fail the skill execution if storage fails

    return result


async def get_skill_execution_history(
    agent_id: str,
    skill_id: Optional[str] = None,
    limit: int = 50
) -> list:
    """
    Get execution history for an agent's skills.

    Args:
        agent_id: ID of standalone agent
        skill_id: Optional skill ID to filter by
        limit: Maximum number of executions to return

    Returns:
        List of execution records
    """
    from open_notebook.database.repository import repo_query

    where_clause = "agent_id = :agent_id"
    params = {"agent_id": agent_id, "limit": limit}

    if skill_id:
        where_clause += " AND skill_id = :skill_id"
        params["skill_id"] = skill_id

    rows = await repo_query(
        f"""
        SELECT * FROM agent_skill_executions
        WHERE {where_clause}
        ORDER BY created DESC
        LIMIT :limit
        """,
        params
    )

    # Parse JSON fields
    results = []
    for row in rows:
        record = dict(row)
        if record.get("input_data"):
            record["input_data"] = json.loads(record["input_data"])
        if record.get("output_data"):
            record["output_data"] = json.loads(record["output_data"])
        if record.get("steps"):
            record["steps"] = json.loads(record["steps"])
        if record.get("result"):
            record["result"] = json.loads(record["result"])
        results.append(record)

    return results
