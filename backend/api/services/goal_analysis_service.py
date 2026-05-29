"""
Goal Analysis Service

Analyzes user workspace goals using LLMs to extract intent, domain,
keywords, and requirements. Supports clarification question generation
and iterative refinement based on user answers.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from api.services.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt templates (kept as fallbacks for robustness)
# ---------------------------------------------------------------------------

GOAL_ANALYSIS_PROMPT = """You are analyzing a user's workspace goal.

USER GOAL: {goal}

Analyze and extract:
1. Intent: What is the user trying to achieve? (research, analysis, automation, learning, monitoring, reporting)
2. Domain: What domain/industry? (business, finance, technology, healthcare, education, marketing, legal, science, general)
3. Complexity: simple, moderate, or complex?
4. Keywords: 5-10 relevant keywords
5. Requirements: What capabilities/resources are needed?

Return ONLY valid JSON:
{{
  "intent": "...",
  "domain": "...",
  "complexity": "simple|moderate|complex",
  "keywords": ["...", "..."],
  "requirements": ["...", "..."]
}}"""

CLARIFICATION_PROMPT = """Based on the following analysis of a user's workspace goal, determine if clarification is needed.

ANALYSIS:
{analysis_json}

If the analysis is ambiguous or could benefit from clarification, generate 1-3 questions.
Each question should help narrow down the user's intent, preferred data sources, or scope.

Return ONLY valid JSON:
{{
  "needs_clarification": true,
  "questions": [
    {{
      "question": "What specific aspect are you most interested in?",
      "type": "multiple_choice",
      "options": ["Option A", "Option B", "Option C"],
      "help_text": "This helps us tailor your workspace."
    }}
  ]
}}

Question types: multiple_choice (include options), text (free-form), date_range (for time-bound goals).
If no clarification is needed, return: {{"needs_clarification": false, "questions": []}}"""

REFINEMENT_PROMPT = """You previously analyzed a user's workspace goal. The user has now answered clarification questions.

ORIGINAL ANALYSIS:
{analysis_json}

USER ANSWERS:
{answers_json}

Update the analysis incorporating the user's answers. Refine keywords and requirements accordingly.

Return ONLY valid JSON:
{{
  "intent": "...",
  "domain": "...",
  "complexity": "simple|moderate|complex",
  "keywords": ["...", "..."],
  "requirements": ["...", "..."]
}}"""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class GoalAnalysisService:
    """
    Analyzes user goals via LLM to extract structured intent, domain,
    keywords, and requirements. Provides clarification question generation
    and iterative refinement.
    """

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def analyze_goal(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze a user goal and extract structured information.

        Args:
            goal: The user's stated workspace goal.
            context: Optional extra context (e.g. notebook info).

        Returns:
            Dict with keys: intent, domain, complexity, keywords, requirements.
        """
        # Check cache
        cache_key = goal.strip().lower()
        if cache_key in self._cache:
            logger.debug("Returning cached analysis for goal: %s", goal[:60])
            return self._cache[cache_key]

        # Load prompt from database with fallback
        prompt_template = await load_prompt(
            "guided_goal_analysis",
            variables={"goal": goal, "context": json.dumps(context) if context else ""},
            fallback=GOAL_ANALYSIS_PROMPT
        )

        # Format with variables (fallback already formatted, template uses {goal})
        if "{goal}" in prompt_template:
            prompt = prompt_template.format(goal=goal)
            if context:
                prompt += f"\n\nADDITIONAL CONTEXT: {json.dumps(context)}"
        else:
            # Already formatted by load_prompt
            prompt = prompt_template

        raw = await self._call_llm(prompt)
        analysis = self._parse_json_response(raw)

        # Validate / fill defaults
        analysis.setdefault("intent", "research")
        analysis.setdefault("domain", "general")
        analysis.setdefault("complexity", "moderate")
        analysis.setdefault("keywords", [])
        analysis.setdefault("requirements", [])

        self._cache[cache_key] = analysis
        logger.info(
            "Goal analyzed: intent=%s domain=%s complexity=%s",
            analysis["intent"],
            analysis["domain"],
            analysis["complexity"],
        )
        return analysis

    async def generate_clarification_questions(
        self,
        analysis: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Generate clarifying questions when the goal is ambiguous.

        Args:
            analysis: Output from analyze_goal.

        Returns:
            List of question dicts with: question, type, options, help_text.
            Empty list when no clarification is needed.
        """
        # Load prompt from database with fallback
        prompt = await load_prompt(
            "guided_clarification",
            variables={"analysis_json": json.dumps(analysis, indent=2)},
            fallback=CLARIFICATION_PROMPT.format(analysis_json=json.dumps(analysis, indent=2))
        )

        raw = await self._call_llm(prompt)
        parsed = self._parse_json_response(raw)

        if not parsed.get("needs_clarification", False):
            return []

        questions: List[Dict[str, Any]] = []
        for q in parsed.get("questions", []):
            questions.append({
                "question": q.get("question", ""),
                "type": q.get("type", "text"),
                "options": q.get("options", []),
                "help_text": q.get("help_text", ""),
            })

        logger.info("Generated %d clarification question(s)", len(questions))
        return questions

    async def refine_analysis(
        self,
        analysis: Dict[str, Any],
        answers: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Refine an existing analysis using user-provided answers.

        Args:
            analysis: Original analysis from analyze_goal.
            answers: Dict mapping question text to user answer.

        Returns:
            Updated analysis dict.
        """
        # Load prompt from database with fallback
        prompt = await load_prompt(
            "guided_refinement",
            variables={
                "analysis_json": json.dumps(analysis, indent=2),
                "answers_json": json.dumps(answers, indent=2)
            },
            fallback=REFINEMENT_PROMPT.format(
                analysis_json=json.dumps(analysis, indent=2),
                answers_json=json.dumps(answers, indent=2)
            )
        )

        raw = await self._call_llm(prompt)
        refined = self._parse_json_response(raw)

        # Carry forward any missing fields from the original analysis
        for key in ("intent", "domain", "complexity", "keywords", "requirements"):
            refined.setdefault(key, analysis.get(key))

        logger.info(
            "Analysis refined: intent=%s domain=%s complexity=%s",
            refined["intent"],
            refined["domain"],
            refined["complexity"],
        )
        return refined

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _call_llm(self, prompt: str) -> str:
        """
        Call the configured LLM with a prompt and return the raw text response.

        Args:
            prompt: The full prompt to send.

        Returns:
            Raw assistant message content.
        """
        from api.services.llm_client import resolve_llm_credential, call_llm_chat

        credential = await resolve_llm_credential()
        return await call_llm_chat(
            credential,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a goal analysis assistant. "
                        "Always respond with valid JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=1500,
        )

    @staticmethod
    def _parse_json_response(text: str) -> Dict[str, Any]:
        """
        Extract and parse JSON from an LLM response that may contain
        markdown fences or surrounding prose.
        """
        cleaned = text.strip()

        # Strip markdown code fences
        json_match = re.search(
            r"```(?:json)?\s*\n?(.*?)\n?```", cleaned, re.DOTALL
        )
        if json_match:
            cleaned = json_match.group(1).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Fall back: find first JSON object in text
            brace_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if brace_match:
                try:
                    return json.loads(brace_match.group(0))
                except json.JSONDecodeError:
                    pass

        logger.warning("Could not parse LLM JSON response: %s", cleaned[:200])
        return {}


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_goal_analysis_service: Optional[GoalAnalysisService] = None


def get_goal_analysis_service() -> GoalAnalysisService:
    """Get or create the GoalAnalysisService singleton."""
    global _goal_analysis_service
    if _goal_analysis_service is None:
        _goal_analysis_service = GoalAnalysisService()
    return _goal_analysis_service
