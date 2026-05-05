"""
Built-in skills auto-registration

This module registers all built-in skills on import.
Call register_builtin_skills() on application startup.
"""

import logging

logger = logging.getLogger(__name__)


def register_builtin_skills():
    """
    Register all built-in skills.

    This should be called once during application startup to make
    all built-in skills available to agents.
    """
    from open_notebook.agents.skills import register_skill
    from open_notebook.agents.skills.builtin.search_skill import create_search_skill
    from open_notebook.agents.skills.builtin.data_query_skill import hana_query_skill
    from open_notebook.agents.skills.builtin.memory_skill import (
        memory_store_skill,
        memory_recall_skill
    )
    from open_notebook.agents.skills.builtin.synthesis_skill import summarize_skill

    skills = [
        create_search_skill(),
        hana_query_skill,
        memory_store_skill,
        memory_recall_skill,
        summarize_skill,
    ]

    registered_count = 0
    for skill in skills:
        try:
            register_skill(skill)
            registered_count += 1
            logger.info(f"Registered built-in skill: {skill.id} ({skill.name})")
        except Exception as e:
            logger.error(f"Failed to register skill {skill.id}: {e}")

    logger.info(f"Successfully registered {registered_count}/{len(skills)} built-in skills")
    print(f"✓ Registered {registered_count} built-in agent skills")

    return registered_count


__all__ = [
    "register_builtin_skills",
]
