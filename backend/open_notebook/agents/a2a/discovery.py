"""
A2A Discovery Client

Discovers remote A2A agents by fetching AgentCards.
"""

import logging
import uuid
from typing import Dict, List, Optional
from urllib.parse import urljoin

import httpx
from a2a.types import AgentCard, AgentSkill

from open_notebook.agents.skills.base import Skill, SkillCategory
from open_notebook.agents.skills.registry import get_skill_registry
from open_notebook.domain.a2a import A2ARemoteAgent, A2ASkillMapping

logger = logging.getLogger(__name__)


class A2ADiscoveryClient:
    """
    Discover remote A2A agents by fetching AgentCards.

    Handles:
    - Well-known URL resolution
    - AgentCard fetching and validation
    - Agent import and skill mapping
    - Credential management
    """

    def __init__(self, timeout: int = 30):
        """
        Initialize discovery client.

        Args:
            timeout: HTTP request timeout in seconds
        """
        self.timeout = timeout
        self.skill_registry = get_skill_registry()

    async def discover_agent(self, card_url: str) -> AgentCard:
        """
        Fetch AgentCard from remote agent.

        Args:
            card_url: URL to AgentCard or base URL

        Returns:
            Parsed AgentCard

        Raises:
            httpx.HTTPError: If fetch fails
            ValueError: If card is invalid
        """
        # Try well-known URL first if not explicit card URL
        if not card_url.endswith("agent-card.json"):
            # Ensure base URL has protocol
            if not card_url.startswith(("http://", "https://")):
                card_url = f"https://{card_url}"

            card_url = urljoin(card_url, "/.well-known/agent-card.json")

        logger.info(f"Fetching AgentCard from {card_url}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(card_url)
                response.raise_for_status()
            except httpx.HTTPError as e:
                logger.error(f"Failed to fetch AgentCard: {e}")
                raise

        # Parse and validate AgentCard
        try:
            card_data = response.json()
            card = AgentCard.model_validate(card_data)
            logger.info(f"Successfully fetched AgentCard for {card.name}")
            return card
        except Exception as e:
            logger.error(f"Failed to parse AgentCard: {e}")
            raise ValueError(f"Invalid AgentCard: {e}")

    async def import_agent(
        self,
        card_url: str,
        name: Optional[str] = None,
        enabled: bool = True,
    ) -> A2ARemoteAgent:
        """
        Import remote agent into local registry.

        Creates A2ARemoteAgent record and registers skills as local skills.

        Args:
            card_url: URL to AgentCard
            name: Override agent name (default: from card)
            enabled: Whether agent is enabled

        Returns:
            Created A2ARemoteAgent

        Raises:
            ValueError: If agent already exists or import fails
        """
        # Check if already imported
        existing = await A2ARemoteAgent.get_by_card_url(card_url)
        if existing:
            logger.warning(f"Agent already imported: {existing.name} ({existing.id})")
            return existing

        # Fetch AgentCard
        card = await self.discover_agent(card_url)

        # Create remote agent record (let ObjectModel generate ID)
        agent = A2ARemoteAgent(
            name=name or card.name,
            card_url=card_url,
            agent_card=card.model_dump_json(),
            transport=card.preferred_transport or "JSONRPC",
            endpoint_url=card.url,
            enabled=enabled,
        )

        # Set security schemes
        if card.security_schemes:
            agent.security_schemes = card.model_dump_json(include={"security_schemes"})

        # Set available skills
        skill_ids = [s.id for s in (card.skills or [])]
        agent.set_available_skills(skill_ids)

        # Save agent
        await agent.save()
        await agent.update_last_synced()

        logger.info(f"Imported remote agent: {agent.name} ({agent.id}) with {len(skill_ids)} skills")

        # Import skills
        imported_count = 0
        for a2a_skill in (card.skills or []):
            try:
                await self._import_skill_as_local(agent.id, a2a_skill)
                imported_count += 1
            except Exception as e:
                logger.error(f"Failed to import skill {a2a_skill.id}: {e}")

        logger.info(f"Successfully imported {imported_count}/{len(card.skills or [])} skills")

        return agent

    async def _import_skill_as_local(
        self,
        agent_id: str,
        a2a_skill: AgentSkill,
    ) -> None:
        """
        Create local skill record pointing to remote A2A agent.

        Args:
            agent_id: Remote agent ID
            a2a_skill: A2A AgentSkill from remote card

        Raises:
            ValueError: If skill already exists
        """
        # Generate local skill ID
        local_skill_id = f"a2a:{agent_id}:{a2a_skill.id}"

        # Check if skill already exists
        if self.skill_registry.get_skill(local_skill_id):
            logger.warning(f"Skill already registered: {local_skill_id}")
            return

        # Create skill mapping record (let ObjectModel generate ID)
        mapping = A2ASkillMapping(
            remote_agent_id=agent_id,
            remote_skill_id=a2a_skill.id,
            local_skill_id=local_skill_id,
            skill_name=a2a_skill.name,
            skill_description=a2a_skill.description,
            enabled=True,
        )

        # Set tags
        if a2a_skill.tags:
            mapping.set_skill_tags(a2a_skill.tags)

        # Save mapping
        await mapping.save()

        # Register skill in local registry
        # Import here to avoid circular dependency
        from open_notebook.agents.a2a.skill_adapter import RemoteSkillAdapter

        handler = RemoteSkillAdapter.create_handler(agent_id, a2a_skill.id)

        # Determine category from tags
        category = self._infer_category_from_tags(a2a_skill.tags or [])

        skill = Skill(
            id=local_skill_id,
            name=f"{a2a_skill.name} (Remote)",
            description=a2a_skill.description or "Remote A2A agent skill",
            category=category,
            handler=handler,
            tags=(a2a_skill.tags or []) + ["a2a", "remote"],
            version="1.0.0",
        )

        self.skill_registry.register_skill(skill)

        logger.info(f"Registered remote skill: {skill.name} ({local_skill_id})")

    def _infer_category_from_tags(self, tags: List[str]) -> SkillCategory:
        """
        Infer skill category from tags.

        Args:
            tags: List of tags

        Returns:
            SkillCategory
        """
        tag_str = " ".join(tags).lower()

        if any(word in tag_str for word in ["search", "find", "lookup"]):
            return SkillCategory.SEARCH
        elif any(word in tag_str for word in ["data", "query", "database"]):
            return SkillCategory.DATA_QUERY
        elif any(word in tag_str for word in ["analyze", "analysis"]):
            return SkillCategory.ANALYSIS
        elif any(word in tag_str for word in ["synthesis", "summarize", "combine"]):
            return SkillCategory.SYNTHESIS
        elif any(word in tag_str for word in ["coordinate", "manage", "orchestrate"]):
            return SkillCategory.COORDINATION
        elif any(word in tag_str for word in ["memory", "remember", "recall"]):
            return SkillCategory.MEMORY
        else:
            return SkillCategory.TOOLS

    async def sync_agent(self, agent_id: str) -> A2ARemoteAgent:
        """
        Re-fetch AgentCard and update skills.

        Args:
            agent_id: Remote agent ID

        Returns:
            Updated A2ARemoteAgent

        Raises:
            ValueError: If agent not found or sync fails
        """
        agent = await A2ARemoteAgent.get(agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")

        logger.info(f"Syncing agent: {agent.name} ({agent_id})")

        # Fetch latest AgentCard
        card = await self.discover_agent(agent.card_url)

        # Update agent record
        agent.set_agent_card(card.model_dump())
        agent.transport = card.preferred_transport or "JSONRPC"
        agent.endpoint_url = card.url

        # Update available skills
        new_skill_ids = [s.id for s in (card.skills or [])]
        old_skill_ids = agent.get_available_skills()
        agent.set_available_skills(new_skill_ids)

        await agent.save()
        await agent.update_last_synced()

        # Find removed skills
        removed_skills = set(old_skill_ids) - set(new_skill_ids)
        for skill_id in removed_skills:
            local_id = f"a2a:{agent_id}:{skill_id}"
            self.skill_registry.unregister_skill(local_id)
            logger.info(f"Unregistered removed skill: {local_id}")

        # Find added skills
        added_skills = set(new_skill_ids) - set(old_skill_ids)
        for a2a_skill in (card.skills or []):
            if a2a_skill.id in added_skills:
                await self._import_skill_as_local(agent_id, a2a_skill)

        logger.info(
            f"Synced agent {agent.name}: "
            f"+{len(added_skills)} skills, -{len(removed_skills)} skills"
        )

        return agent

    async def remove_agent(self, agent_id: str) -> bool:
        """
        Remove remote agent and its skills.

        Args:
            agent_id: Remote agent ID

        Returns:
            True if removed, False if not found
        """
        agent = await A2ARemoteAgent.get(agent_id)
        if not agent:
            return False

        logger.info(f"Removing agent: {agent.name} ({agent_id})")

        # Unregister all skills
        skill_ids = agent.get_available_skills()
        for skill_id in skill_ids:
            local_id = f"a2a:{agent_id}:{skill_id}"
            self.skill_registry.unregister_skill(local_id)

        # Delete agent (cascades to credentials and mappings)
        await agent.delete()

        logger.info(f"Removed agent {agent.name} and {len(skill_ids)} skills")
        return True

    async def list_agents(self, enabled_only: bool = False) -> List[A2ARemoteAgent]:
        """
        List all imported remote agents.

        Args:
            enabled_only: Only return enabled agents

        Returns:
            List of A2ARemoteAgents
        """
        if enabled_only:
            return await A2ARemoteAgent.get_enabled()
        else:
            return await A2ARemoteAgent.get_all(order_by="name ASC")

    async def get_agent(self, agent_id: str) -> Optional[A2ARemoteAgent]:
        """
        Get remote agent by ID.

        Args:
            agent_id: Remote agent ID

        Returns:
            A2ARemoteAgent or None
        """
        return await A2ARemoteAgent.get(agent_id)
