"""
Orchestration Decision Engine

Determines the optimal orchestration strategy (single, team, or swarm)
based on goal complexity, intent, and required capabilities.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models import BaseChatModel

from open_notebook.config import get_default_model

logger = logging.getLogger(__name__)


@dataclass
class OrchestrationDecision:
    """
    Decision on how to orchestrate a goal.

    Attributes:
        mode: Orchestration mode (single, team, swarm)
        team_size: Number of agents to spawn (1 for single)
        roles: List of agent roles needed
        parallel_capable: Whether parallel execution is possible
        estimated_duration: Estimated execution time in seconds
        confidence: Decision confidence (0.0-1.0)
        reasoning: Explanation of the decision
    """
    mode: str
    team_size: int
    roles: List[str]
    parallel_capable: bool
    estimated_duration: float
    confidence: float
    reasoning: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class OrchestrationDecisionEngine:
    """
    Engine that determines orchestration strategy.

    Uses both heuristic rules and LLM-based reasoning to decide
    whether to use single agent, team, or swarm orchestration.
    """

    def __init__(self, llm: Optional[BaseChatModel] = None):
        """
        Initialize decision engine.

        Args:
            llm: Language model for decision making (optional, uses default if not provided)
        """
        self.llm = llm

    async def decide(
        self,
        goal: str,
        complexity: str,
        intent: str,
        capabilities: List[str],
        resources: Optional[Dict[str, Any]] = None
    ) -> OrchestrationDecision:
        """
        Make orchestration decision.

        Args:
            goal: User's goal statement
            complexity: Complexity level (simple, moderate, complex)
            intent: Goal intent (research, analysis, automation, etc.)
            capabilities: Required capabilities/tools
            resources: Available resources (sources, tools, agents)

        Returns:
            OrchestrationDecision with mode and configuration
        """
        resources = resources or {}

        # 1. Apply heuristic rules first
        heuristic_decision = self._apply_heuristics(
            goal, complexity, intent, capabilities, resources
        )

        # 2. If confidence is low, use LLM for decision
        if heuristic_decision.confidence < 0.7:
            logger.info("Heuristic confidence low, using LLM for decision")
            try:
                llm_decision = await self._llm_decide(
                    goal, complexity, intent, capabilities, resources
                )
                # Use LLM decision if confidence is higher
                if llm_decision.confidence > heuristic_decision.confidence:
                    return llm_decision
            except Exception as e:
                logger.warning(f"LLM decision failed, using heuristic: {e}")

        return heuristic_decision

    def _apply_heuristics(
        self,
        goal: str,
        complexity: str,
        intent: str,
        capabilities: List[str],
        resources: Dict[str, Any]
    ) -> OrchestrationDecision:
        """
        Apply heuristic rules to determine orchestration mode.

        Decision Rules:
        1. SINGLE if complexity=simple AND capabilities<=2
        2. TEAM if complexity=moderate AND 2<=capabilities<=4
        3. SWARM if complexity=complex OR capabilities>4
        """
        num_capabilities = len(capabilities)
        num_sources = len(resources.get("sources", []))
        num_tools = len(resources.get("tools", []))

        # Calculate complexity score
        complexity_score = {
            "simple": 1,
            "moderate": 2,
            "complex": 3
        }.get(complexity, 2)

        # Adjust for resources
        if num_sources > 3 or num_tools > 5:
            complexity_score += 1

        # Decision logic
        if complexity_score == 1 and num_capabilities <= 2:
            return self._create_single_decision(goal, intent, capabilities, resources)
        elif complexity_score == 2 or (complexity_score == 3 and num_capabilities <= 4):
            return self._create_team_decision(goal, intent, capabilities, resources)
        else:
            return self._create_swarm_decision(goal, intent, capabilities, resources)

    def _create_single_decision(
        self,
        goal: str,
        intent: str,
        capabilities: List[str],
        resources: Dict[str, Any]
    ) -> OrchestrationDecision:
        """Create SINGLE mode decision."""
        # Determine appropriate single agent role
        role = self._determine_single_role(intent, capabilities)

        return OrchestrationDecision(
            mode="single",
            team_size=1,
            roles=[role],
            parallel_capable=False,
            estimated_duration=30.0,  # 30 seconds baseline
            confidence=0.9,
            reasoning=(
                f"Simple goal with {len(capabilities)} capabilities. "
                f"Single {role} agent can handle this efficiently."
            ),
            metadata={
                "intent": intent,
                "capabilities": capabilities,
                "selected_role": role
            }
        )

    def _create_team_decision(
        self,
        goal: str,
        intent: str,
        capabilities: List[str],
        resources: Dict[str, Any]
    ) -> OrchestrationDecision:
        """Create TEAM mode decision."""
        # Determine team roles based on intent and capabilities
        roles = self._determine_team_roles(intent, capabilities, resources)

        # Check if parallel execution is possible
        parallel_capable = len(roles) >= 2 and self._has_parallel_potential(capabilities)

        # Estimate duration (base + per-agent overhead)
        estimated_duration = 60.0 + (len(roles) * 10.0)
        if parallel_capable:
            estimated_duration *= 0.7  # 30% speedup from parallelization

        return OrchestrationDecision(
            mode="team",
            team_size=len(roles),
            roles=roles,
            parallel_capable=parallel_capable,
            estimated_duration=estimated_duration,
            confidence=0.85,
            reasoning=(
                f"Moderate complexity with {len(capabilities)} capabilities. "
                f"Team of {len(roles)} agents ({', '.join(roles)}) "
                f"{'with parallel execution ' if parallel_capable else ''}will coordinate efficiently."
            ),
            metadata={
                "intent": intent,
                "capabilities": capabilities,
                "parallel_capable": parallel_capable
            }
        )

    def _create_swarm_decision(
        self,
        goal: str,
        intent: str,
        capabilities: List[str],
        resources: Dict[str, Any]
    ) -> OrchestrationDecision:
        """Create SWARM mode decision."""
        # Determine specialized roles for swarm
        roles = self._determine_swarm_roles(intent, capabilities, resources)

        # Swarms always have parallel potential
        parallel_capable = True

        # Estimate duration (higher base due to coordination overhead)
        estimated_duration = 120.0 + (len(roles) * 15.0)
        estimated_duration *= 0.6  # 40% speedup from aggressive parallelization

        return OrchestrationDecision(
            mode="swarm",
            team_size=len(roles),
            roles=roles,
            parallel_capable=parallel_capable,
            estimated_duration=estimated_duration,
            confidence=0.75,
            reasoning=(
                f"Complex goal requiring {len(capabilities)} capabilities. "
                f"Swarm of {len(roles)} specialized agents will collaborate "
                f"with parallel execution streams for optimal results."
            ),
            metadata={
                "intent": intent,
                "capabilities": capabilities,
                "coordination_complexity": "high"
            }
        )

    def _determine_single_role(self, intent: str, capabilities: List[str]) -> str:
        """Determine best single agent role for the goal."""
        # Intent-based role mapping
        intent_role_map = {
            "research": "researcher",
            "analysis": "analyst",
            "data_query": "analyst",
            "automation": "planner",
            "monitoring": "analyst",
            "reporting": "synthesizer"
        }

        # Capability-based role mapping
        if any(cap in ["hana_query", "database", "sql"] for cap in capabilities):
            return "analyst"
        elif any(cap in ["web_search", "retrieval", "scraping"] for cap in capabilities):
            return "researcher"

        # Default based on intent
        return intent_role_map.get(intent, "analyst")

    def _determine_team_roles(
        self,
        intent: str,
        capabilities: List[str],
        resources: Dict[str, Any]
    ) -> List[str]:
        """Determine team roles based on requirements."""
        roles = []

        # Always include a coordinator for multi-agent teams
        roles.append("planner")

        # Add data/research roles based on capabilities
        if any(cap in ["hana_query", "database", "sql", "api_call"] for cap in capabilities):
            roles.append("analyst")

        if any(cap in ["web_search", "retrieval", "scraping"] for cap in capabilities):
            roles.append("researcher")

        # Add synthesizer for final aggregation
        if intent in ["analysis", "reporting", "research"]:
            roles.append("synthesizer")

        # Ensure at least 2 agents for a team
        if len(roles) < 2:
            roles.append("synthesizer")

        return roles

    def _determine_swarm_roles(
        self,
        intent: str,
        capabilities: List[str],
        resources: Dict[str, Any]
    ) -> List[str]:
        """Determine specialized roles for swarm."""
        roles = ["planner"]  # Coordinator

        # Add multiple specialists based on capabilities
        capability_roles = {
            "hana_query": "data_analyst",
            "database": "data_analyst",
            "sql": "data_analyst",
            "api_call": "api_specialist",
            "web_search": "web_researcher",
            "retrieval": "information_retriever",
            "scraping": "web_scraper",
            "visualization": "data_visualizer",
            "nlp": "text_analyst",
            "ml": "ml_specialist"
        }

        # Map capabilities to roles
        for cap in capabilities:
            for cap_pattern, role in capability_roles.items():
                if cap_pattern in cap.lower() and role not in roles:
                    roles.append(role)

        # Add domain-specific specialists
        if intent in ["finance", "financial_analysis"]:
            roles.append("financial_analyst")
        elif intent in ["marketing", "market_research"]:
            roles.append("marketing_analyst")

        # Always add synthesizer for final aggregation
        roles.append("synthesizer")

        return roles

    def _has_parallel_potential(self, capabilities: List[str]) -> bool:
        """Check if capabilities suggest parallel execution is beneficial."""
        # Look for independent data sources or orthogonal tasks
        data_sources = sum(
            1 for cap in capabilities
            if any(term in cap.lower() for term in ["database", "api", "web", "file"])
        )

        # If multiple data sources, parallel execution is beneficial
        return data_sources >= 2

    async def _llm_decide(
        self,
        goal: str,
        complexity: str,
        intent: str,
        capabilities: List[str],
        resources: Dict[str, Any]
    ) -> OrchestrationDecision:
        """
        Use LLM to make orchestration decision.

        Falls back to heuristics if LLM fails.
        """
        if not self.llm:
            self.llm = get_default_model()

        # Build decision prompt
        system_prompt = """You are an expert at orchestrating multi-agent systems.
Given a user goal and its analysis, determine the optimal orchestration strategy.

Orchestration Modes:
- SINGLE: One agent handles the entire task (simple, straightforward goals)
- TEAM: 2-4 agents collaborate (moderate complexity, some parallelism)
- SWARM: 5+ agents with specialized roles (complex, highly parallel)

Consider:
1. Task complexity and dependencies
2. Required capabilities and tools
3. Potential for parallel execution
4. Coordination overhead vs benefits

Respond in JSON format:
{
  "mode": "single|team|swarm",
  "team_size": <number>,
  "roles": ["role1", "role2", ...],
  "parallel_capable": true|false,
  "estimated_duration": <seconds>,
  "confidence": <0.0-1.0>,
  "reasoning": "<explanation>"
}"""

        user_prompt = f"""Goal: {goal}

Analysis:
- Complexity: {complexity}
- Intent: {intent}
- Required Capabilities: {', '.join(capabilities)}
- Available Sources: {len(resources.get('sources', []))}
- Available Tools: {len(resources.get('tools', []))}

Determine the optimal orchestration strategy."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        try:
            response = await self.llm.ainvoke(messages)

            # Parse JSON response
            import json
            decision_data = json.loads(response.content)

            return OrchestrationDecision(
                mode=decision_data["mode"],
                team_size=decision_data["team_size"],
                roles=decision_data["roles"],
                parallel_capable=decision_data["parallel_capable"],
                estimated_duration=decision_data["estimated_duration"],
                confidence=decision_data["confidence"],
                reasoning=decision_data["reasoning"],
                metadata={
                    "decision_method": "llm",
                    "model": getattr(self.llm, "model_name", "unknown")
                }
            )
        except Exception as e:
            logger.error(f"LLM decision parsing failed: {e}")
            # Fall back to heuristics
            return self._apply_heuristics(goal, complexity, intent, capabilities, resources)


# Convenience function
async def decide_orchestration(
    goal: str,
    complexity: str,
    intent: str,
    capabilities: List[str],
    resources: Optional[Dict[str, Any]] = None,
    llm: Optional[BaseChatModel] = None
) -> OrchestrationDecision:
    """
    Convenience function to make orchestration decision.

    Args:
        goal: User's goal statement
        complexity: Complexity level (simple, moderate, complex)
        intent: Goal intent
        capabilities: Required capabilities
        resources: Available resources
        llm: Optional language model

    Returns:
        OrchestrationDecision
    """
    engine = OrchestrationDecisionEngine(llm=llm)
    return await engine.decide(goal, complexity, intent, capabilities, resources)
