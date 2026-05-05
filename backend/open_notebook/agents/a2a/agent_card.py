"""
AgentCard Generation

Generates A2A-compliant AgentCards from local skill registry.
"""

import logging
import os
from typing import Dict, List, Optional

from a2a.types import AgentCard, AgentInterface, AgentSkill, AgentCapabilities

from open_notebook.agents.skills.base import Skill, SkillCategory
from open_notebook.agents.skills.registry import get_skill_registry

logger = logging.getLogger(__name__)


class AgentCardGenerator:
    """
    Generate A2A AgentCard from local skill registry.

    Maps local Skills to A2A AgentSkill format and creates a compliant
    AgentCard for discovery and invocation.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        agent_name: Optional[str] = None,
        agent_description: Optional[str] = None,
    ):
        """
        Initialize AgentCard generator.

        Args:
            base_url: Base URL for A2A endpoints (default: from env or localhost)
            agent_name: Agent name (default: "Open Notebook Agent")
            agent_description: Agent description
        """
        # Get base URL from env or use default
        default_url = os.getenv("API_BASE_URL") or "http://localhost:5055"
        self.base_url = base_url or default_url
        self.agent_name = agent_name or "Open Notebook Agent"
        self.agent_description = agent_description or (
            "AI-powered research and data analysis agent with advanced skills "
            "for querying data sources, web research, synthesis, and more."
        )
        self.skill_registry = get_skill_registry()

    def generate_card(
        self,
        agent_id: Optional[str] = None,
        role: Optional[str] = None,
        include_disabled: bool = False,
    ) -> AgentCard:
        """
        Generate AgentCard for entire system or specific agent/role.

        Args:
            agent_id: Optional agent ID to filter skills
            role: Optional role to filter skills
            include_disabled: Include disabled skills

        Returns:
            A2A-compliant AgentCard
        """
        # Get skills for agent/role
        skills = self._get_skills(agent_id=agent_id, role=role, include_disabled=include_disabled)

        # Convert to A2A AgentSkill format
        agent_skills = [self._skill_to_a2a_skill(s) for s in skills]

        # Build AgentCard
        card = AgentCard(
            url=f"{self.base_url}/api/a2a/message/send",
            name=self.agent_name,
            description=self.agent_description,
            version="1.0.0",
            preferredTransport="JSONRPC",
            capabilities=AgentCapabilities(
                streaming=True,
            ),
            defaultInputModes=["text/plain", "application/json"],
            defaultOutputModes=["text/plain", "application/json"],
            additionalInterfaces=[
                AgentInterface(
                    url=f"{self.base_url}/api/a2a/message/stream",
                    transport="HTTP+JSON",
                )
            ],
            skills=agent_skills if agent_skills else [],  # Empty list, not None
            # TODO: Add security schemes if authentication enabled
            securitySchemes=None,
        )

        logger.info(
            f"Generated AgentCard with {len(agent_skills)} skills "
            f"for {self.agent_name}"
        )

        return card

    def _get_skills(
        self,
        agent_id: Optional[str] = None,
        role: Optional[str] = None,
        include_disabled: bool = False,
    ) -> List[Skill]:
        """
        Get skills to include in AgentCard.

        Args:
            agent_id: Filter by agent ID (from skill bindings)
            role: Filter by role
            include_disabled: Include disabled skills

        Returns:
            List of Skills
        """
        if role:
            # Get skills for role
            skills = self.skill_registry.get_skills_for_role(role, include_disabled)
        elif agent_id:
            # TODO: Get skills bound to specific agent
            # For now, return all skills
            skills = self.skill_registry.list_skills(include_disabled)
        else:
            # All skills
            skills = self.skill_registry.list_skills(include_disabled)

        # Filter out A2A remote skills (don't re-expose them)
        skills = [s for s in skills if not s.id.startswith("a2a:")]

        return skills

    def _skill_to_a2a_skill(self, skill: Skill) -> AgentSkill:
        """
        Convert local Skill to A2A AgentSkill.

        Args:
            skill: Local Skill instance

        Returns:
            A2A AgentSkill
        """
        # Extract examples from metadata or description
        examples = []
        if skill.tags:
            # Create example from tags
            examples = [f"I need help with {', '.join(skill.tags[:3])}"]

        return AgentSkill(
            id=skill.id,
            name=skill.name,
            description=skill.description,
            tags=skill.tags,
            examples=examples if examples else None,
            # Use agent-level input/output modes (don't override)
            inputModes=None,
            outputModes=None,
            # TODO: Add security requirements if skill needs specific permissions
            security=None,
        )

    def get_skill_by_id(self, skill_id: str) -> Optional[Skill]:
        """
        Get skill from registry by ID.

        Args:
            skill_id: Skill identifier

        Returns:
            Skill instance or None
        """
        return self.skill_registry.get_skill(skill_id)

    def to_dict(self, card: AgentCard) -> Dict:
        """
        Convert AgentCard to dict for JSON serialization.

        Args:
            card: AgentCard instance

        Returns:
            Dictionary representation
        """
        return card.model_dump(mode="json", exclude_none=True)


def generate_agent_card_json(
    base_url: Optional[str] = None,
    agent_name: Optional[str] = None,
    agent_id: Optional[str] = None,
    role: Optional[str] = None,
) -> Dict:
    """
    Convenience function to generate AgentCard as JSON dict.

    Args:
        base_url: Base URL for endpoints
        agent_name: Agent name
        agent_id: Filter by agent ID
        role: Filter by role

    Returns:
        AgentCard as dict
    """
    generator = AgentCardGenerator(base_url=base_url, agent_name=agent_name)
    card = generator.generate_card(agent_id=agent_id, role=role)
    return generator.to_dict(card)
