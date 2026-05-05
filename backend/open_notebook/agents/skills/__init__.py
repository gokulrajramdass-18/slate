"""
Agent Skills System

A plugin architecture for equipping agents with reusable, composable capabilities.
Skills extend agents with specialized abilities while maintaining observability,
role-based access control, and team coordination.

Usage:
    from open_notebook.agents.skills import (
        Skill,
        SkillCategory,
        SkillContext,
        SkillRegistry,
        get_skill_registry,
        register_skill,
    )

    # Define a skill
    async def my_skill_handler(context: SkillContext) -> Dict[str, Any]:
        # Implementation
        return {"result": "success"}

    # Register
    skill = Skill(
        id="my_skill",
        name="My Skill",
        description="Does something useful",
        category=SkillCategory.ANALYSIS,
        handler=my_skill_handler
    )

    register_skill(skill)
"""

from open_notebook.agents.skills.base import (
    Skill,
    SkillCategory,
    SkillContext,
    SkillExecutionResult,
    RetryPolicy,
)
from open_notebook.agents.skills.registry import (
    SkillRegistry,
    get_skill_registry,
)
from open_notebook.agents.skills.binding import (
    SkillBinding,
    get_agent_skills,
    get_team_skills,
    bind_skill_to_agent,
    bind_skill_to_team,
    bind_skill_to_role,
)
from open_notebook.agents.skills.executor import (
    SkillExecutor,
    get_skill_executor,
)


def register_skill(skill: Skill) -> None:
    """Convenience function to register a skill."""
    registry = get_skill_registry()
    registry.register_skill(skill)


__all__ = [
    # Base types
    "Skill",
    "SkillCategory",
    "SkillContext",
    "SkillExecutionResult",
    "RetryPolicy",
    # Registry
    "SkillRegistry",
    "get_skill_registry",
    "register_skill",
    # Bindings
    "SkillBinding",
    "get_agent_skills",
    "get_team_skills",
    "bind_skill_to_agent",
    "bind_skill_to_team",
    "bind_skill_to_role",
    # Executor
    "SkillExecutor",
    "get_skill_executor",
]
