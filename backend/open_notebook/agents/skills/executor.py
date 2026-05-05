"""
Skill Executor - Execute skills with observability

Handles skill execution with timing, error handling, and observability.
"""

import asyncio
import logging
import time
from typing import Any, Optional

from open_notebook.agents.skills.base import (
    SkillContext,
    SkillExecutionResult
)
from open_notebook.agents.skills.registry import get_skill_registry

logger = logging.getLogger(__name__)


class SkillExecutor:
    """
    Singleton executor for running skills with observability.

    Validates permissions, measures execution time, captures errors,
    and records execution steps.
    """
    _instance: Optional["SkillExecutor"] = None

    def __new__(cls):
        """Singleton instantiation."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def execute(
        self,
        skill_id: str,
        context: SkillContext
    ) -> SkillExecutionResult:
        """
        Execute a skill with observability.

        Handles both code-based skills (in registry) and dynamic skills (in database).

        Args:
            skill_id: ID of skill to execute
            context: Execution context with input data and resources

        Returns:
            SkillExecutionResult with success status, result, timing, and steps
        """
        registry = get_skill_registry()
        skill = registry.get_skill(skill_id)

        # If skill found in registry, execute as code-based skill
        if skill:
            return await self._execute_code_skill(skill_id, skill, context)

        # Skill not in registry - check if it's a dynamic skill in database
        logger.info(f"Skill {skill_id} not in code registry, checking database for dynamic skill")

        try:
            return await self._execute_dynamic_skill(skill_id, context)
        except ValueError as e:
            # Not found in database either
            error_msg = f"Skill not found in code registry or database: {skill_id}"
            logger.error(error_msg)
            return SkillExecutionResult(
                skill_id=skill_id,
                execution_id=context.execution_id,
                success=False,
                result=None,
                error=error_msg
            )

    async def _execute_code_skill(
        self,
        skill_id: str,
        skill: Any,
        context: SkillContext
    ) -> SkillExecutionResult:
        """
        Execute a code-based skill from the registry.

        Args:
            skill_id: Skill ID
            skill: Skill object from registry
            context: Execution context

        Returns:
            SkillExecutionResult
        """
        # Check if skill is enabled
        if not skill.enabled:
            error_msg = f"Skill is disabled: {skill_id}"
            logger.warning(error_msg)
            return SkillExecutionResult(
                skill_id=skill_id,
                execution_id=context.execution_id,
                success=False,
                result=None,
                error=error_msg
            )

        # Check access control
        if skill.allowed_roles and context.agent_role not in skill.allowed_roles:
            error_msg = (
                f"Agent role '{context.agent_role}' not allowed for skill {skill_id}. "
                f"Allowed roles: {list(skill.allowed_roles)}"
            )
            logger.warning(error_msg)
            return SkillExecutionResult(
                skill_id=skill_id,
                execution_id=context.execution_id,
                success=False,
                result=None,
                error=error_msg
            )

        # Execute with timing and timeout
        start_time = time.time()
        try:
            logger.info(
                f"Executing code skill {skill_id} for agent {context.agent_id} "
                f"(role: {context.agent_role})"
            )

            # Apply timeout if configured
            if skill.timeout_seconds > 0:
                result = await asyncio.wait_for(
                    skill.handler(context),
                    timeout=skill.timeout_seconds
                )
            else:
                result = await skill.handler(context)

            duration_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Skill {skill_id} completed successfully in {duration_ms:.2f}ms"
            )

            return SkillExecutionResult(
                skill_id=skill_id,
                execution_id=context.execution_id,
                success=True,
                result=result,
                duration_ms=duration_ms,
                steps=context.steps
            )

        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            error_msg = f"Skill execution timed out after {skill.timeout_seconds}s"
            logger.error(error_msg)
            return SkillExecutionResult(
                skill_id=skill_id,
                execution_id=context.execution_id,
                success=False,
                result=None,
                error=error_msg,
                duration_ms=duration_ms,
                steps=context.steps
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            error_msg = f"Skill execution failed: {str(e)}"
            logger.exception(f"Error executing skill {skill_id}: {e}")
            return SkillExecutionResult(
                skill_id=skill_id,
                execution_id=context.execution_id,
                success=False,
                result=None,
                error=error_msg,
                duration_ms=duration_ms,
                steps=context.steps
            )

    async def _execute_dynamic_skill(
        self,
        skill_id: str,
        context: SkillContext
    ) -> SkillExecutionResult:
        """
        Execute a dynamic skill from the database.

        Args:
            skill_id: Skill ID
            context: Execution context

        Returns:
            SkillExecutionResult
        """
        from open_notebook.agents.skills.dynamic_executor import get_dynamic_skill_executor

        start_time = time.time()

        try:
            logger.info(
                f"Executing dynamic skill {skill_id} for agent {context.agent_id}"
            )

            # Execute via dynamic executor
            executor = get_dynamic_skill_executor()
            result = await executor.execute_dynamic_skill(skill_id, context)

            duration_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Dynamic skill {skill_id} completed successfully in {duration_ms:.2f}ms"
            )

            return SkillExecutionResult(
                skill_id=skill_id,
                execution_id=context.execution_id,
                success=True,
                result=result,
                duration_ms=duration_ms,
                steps=context.steps
            )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            error_msg = f"Dynamic skill execution failed: {str(e)}"
            logger.exception(f"Error executing dynamic skill {skill_id}: {e}")
            return SkillExecutionResult(
                skill_id=skill_id,
                execution_id=context.execution_id,
                success=False,
                result=None,
                error=error_msg,
                duration_ms=duration_ms,
                steps=context.steps
            )


# Singleton accessor
def get_skill_executor() -> SkillExecutor:
    """
    Get the global skill executor instance.

    Returns:
        Singleton SkillExecutor instance
    """
    return SkillExecutor()
