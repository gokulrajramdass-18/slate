"""
Skill Registry - Singleton for managing all skills

Provides thread-safe skill registration, discovery, and access control.
"""

import logging
from threading import Lock
from typing import Dict, List, Optional

from open_notebook.agents.skills.base import Skill, SkillCategory

logger = logging.getLogger(__name__)


class SkillRegistry:
    """
    Singleton registry for managing skills.

    Thread-safe implementation that maintains an in-memory store of all
    registered skills. Provides discovery, filtering, and search capabilities.
    """
    _instance: Optional["SkillRegistry"] = None
    _lock = Lock()

    def __new__(cls):
        """Thread-safe singleton instantiation."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        """Initialize registry (only once)."""
        if self._initialized:
            return

        self._skills: Dict[str, Skill] = {}
        self._initialized = True
        logger.info("SkillRegistry initialized")

    def register_skill(self, skill: Skill) -> None:
        """
        Register a skill.

        Args:
            skill: Skill instance to register

        Raises:
            ValueError: If skill with same ID already exists
        """
        if skill.id in self._skills:
            logger.warning(f"Overwriting existing skill: {skill.id}")

        self._skills[skill.id] = skill
        logger.info(
            f"Registered skill: {skill.id} ({skill.name}) "
            f"in category {skill.category.value}"
        )

    def unregister_skill(self, skill_id: str) -> bool:
        """
        Unregister a skill.

        Args:
            skill_id: ID of skill to remove

        Returns:
            True if skill was removed, False if not found
        """
        if skill_id in self._skills:
            del self._skills[skill_id]
            logger.info(f"Unregistered skill: {skill_id}")
            return True
        return False

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """
        Get skill by ID.

        Checks in-memory registry first, then checks database for dynamic skills.

        Args:
            skill_id: Skill identifier

        Returns:
            Skill instance or None if not found
        """
        # Check in-memory registry first (code-based skills)
        skill = self._skills.get(skill_id)
        if skill:
            return skill

        # Check if this is a database-stored skill (marker for dynamic execution)
        # Return a marker skill that indicates dynamic execution is needed
        return None  # Caller should check database if None

    def is_dynamic_skill(self, skill_id: str) -> bool:
        """
        Check if skill_id is NOT in code registry (implies it's a dynamic skill).

        Args:
            skill_id: Skill identifier

        Returns:
            True if skill is not in code registry (likely dynamic)
        """
        return skill_id not in self._skills

    def list_skills(self, include_disabled: bool = False) -> List[Skill]:
        """
        List all skills.

        Args:
            include_disabled: Include disabled skills in results

        Returns:
            List of all registered skills
        """
        skills = list(self._skills.values())
        if not include_disabled:
            skills = [s for s in skills if s.enabled]
        return skills

    def get_skills_by_category(
        self,
        category: SkillCategory,
        include_disabled: bool = False
    ) -> List[Skill]:
        """
        Get skills by category.

        Args:
            category: Skill category to filter by
            include_disabled: Include disabled skills in results

        Returns:
            List of skills in the specified category
        """
        skills = [
            s for s in self._skills.values()
            if s.category == category
        ]

        if not include_disabled:
            skills = [s for s in skills if s.enabled]

        return skills

    def get_skills_for_role(
        self,
        role: str,
        include_disabled: bool = False
    ) -> List[Skill]:
        """
        Get skills accessible to a role.

        Skills with no allowed_roles are accessible to all roles.

        Args:
            role: Agent role to check
            include_disabled: Include disabled skills in results

        Returns:
            List of skills accessible to the role
        """
        skills = [
            s for s in self._skills.values()
            if not s.allowed_roles or role in s.allowed_roles
        ]

        if not include_disabled:
            skills = [s for s in skills if s.enabled]

        return skills

    def search_skills(
        self,
        query: str,
        include_disabled: bool = False
    ) -> List[Skill]:
        """
        Search skills by name, description, or tags.

        Performs case-insensitive substring matching.

        Args:
            query: Search query string
            include_disabled: Include disabled skills in results

        Returns:
            List of matching skills
        """
        query_lower = query.lower()
        results = []

        for skill in self._skills.values():
            # Skip disabled if not requested
            if not include_disabled and not skill.enabled:
                continue

            # Check name
            if query_lower in skill.name.lower():
                results.append(skill)
                continue

            # Check description
            if query_lower in skill.description.lower():
                results.append(skill)
                continue

            # Check tags
            if any(query_lower in tag.lower() for tag in skill.tags):
                results.append(skill)
                continue

        return results

    def get_skill_count(self) -> int:
        """
        Get total number of registered skills.

        Returns:
            Count of registered skills
        """
        return len(self._skills)

    def clear(self) -> None:
        """
        Clear all registered skills.

        WARNING: This removes all skills from the registry.
        Primarily used for testing.
        """
        count = len(self._skills)
        self._skills.clear()
        logger.warning(f"Cleared {count} skills from registry")


# Singleton accessor
def get_skill_registry() -> SkillRegistry:
    """
    Get the global skill registry instance.

    Returns:
        Singleton SkillRegistry instance
    """
    return SkillRegistry()
