"""
Clarification detection for pattern executors.

After every agent step, we ask: does this output answer the user's request,
or does the agent need more info from the user before continuing?

The detector is a small LLM classifier with a regex fast-path that skips the
LLM call when the output is *obviously* a deliverable (long-form, no
question marks, no second-person interrogative phrases). The LLM call uses a
short JSON-mode prompt and a low token budget so the per-step cost stays
small.

When a question is detected, callers raise `ClarificationPending` with the
question text and a per-pattern checkpoint dict. The dispatcher in
`langgraph_orchestrator._maybe_run_pattern` catches it, persists the
clarification row, marks the execution awaiting_input, and emits an SSE
event so the UI can pop a dialog.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


# Indicators that the agent is *probably* asking the user something. We use
# this list only as a CHEAP first filter — if none match, the output is
# almost certainly a deliverable and we skip the LLM classifier entirely.
_QUESTION_HINTS = re.compile(
    r"(\?\s*$|"                                            # trailing ?
    r"\bwhich\b|\bchoose\b|\bdo you want\b|\bwould you\b|"
    r"\bplease (?:specify|clarify|confirm|provide|tell)\b|"
    r"\blet me know\b|\bcould you\b|\bcan you\b|"
    r"\bmore information\b|\bclarif|\bconfirm)",
    re.IGNORECASE,
)

_DETECT_SYSTEM = (
    "You are a classifier. Decide whether the AGENT_OUTPUT is the agent "
    "ASKING the user a clarifying question, vs. the agent producing a "
    "deliverable. A deliverable can contain rhetorical questions and still "
    "be a deliverable. A clarifying request is when the agent CANNOT "
    "continue without input from the user (asking them to choose between "
    "options, fill in missing info, confirm an interpretation). "
    'Reply with strict JSON: {"is_question": <bool>, "question": "<one-line '
    'paraphrase if true, else empty>"} and nothing else.'
)


class ClarificationPending(Exception):
    """
    Raised by a pattern executor when an agent has asked the user a question
    instead of producing the next-step output. Carries the question text and
    a checkpoint the resume path can use to skip already-completed steps.
    """

    def __init__(
        self,
        *,
        question: str,
        sender_agent_id: Optional[str],
        sender_name: Optional[str] = None,
        sender_role: Optional[str] = None,
        checkpoint: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(question)
        self.question = question
        self.sender_agent_id = sender_agent_id
        self.sender_name = sender_name
        self.sender_role = sender_role
        self.checkpoint = checkpoint or {}


@dataclass
class DetectionResult:
    is_question: bool
    question: str = ""


async def detect_clarification(llm: Any, agent_output: str) -> DetectionResult:
    """
    Decide whether `agent_output` is a clarifying question.

    Returns DetectionResult(is_question, question). Failures (LLM timeout,
    JSON parse error, etc.) are swallowed and treated as "not a question" —
    we'd rather miss a clarification and ship a deliverable than block on a
    flaky detector.
    """
    text = (agent_output or "").strip()
    if not text:
        return DetectionResult(False)

    # Cheap fast path: nothing that looks like a question? skip the LLM.
    if not _QUESTION_HINTS.search(text):
        return DetectionResult(False)

    # If the text is long-form prose with one tail question (common writer
    # pattern), don't pause — the bulk content IS the deliverable.
    word_count = len(text.split())
    if word_count > 250 and text.count("?") <= 2:
        return DetectionResult(False)

    if llm is None:
        # No LLM available (test path, init failed) — fall back to "treat
        # short outputs ending in ? as a question, otherwise no".
        is_q = text.endswith("?") and word_count < 80
        return DetectionResult(is_q, text if is_q else "")

    try:
        resp = await llm.ainvoke([
            SystemMessage(content=_DETECT_SYSTEM),
            HumanMessage(content=f"AGENT_OUTPUT:\n{text[:4000]}"),
        ])
        raw = (getattr(resp, "content", str(resp)) or "").strip()
        # Strip code fences if any.
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        payload = json.loads(m.group(0) if m else raw)
        is_q = bool(payload.get("is_question"))
        q = str(payload.get("question") or "").strip()
        if is_q and not q:
            # Detector said "yes" but didn't paraphrase — fall back to the
            # last 1–2 sentences of the agent output.
            q = _last_sentences(text)
        return DetectionResult(is_q, q if is_q else "")
    except Exception as e:
        logger.warning("clarification detector failed: %s", e)
        return DetectionResult(False)


async def auto_answer_question(
    llm: Any,
    *,
    original_goal: str,
    question: str,
) -> str:
    """
    Synthesize a plausible answer to the agent's question from the original
    user goal — used when the team has `auto_answer=true` in its config.
    """
    if llm is None:
        return "Use your best judgment."
    try:
        resp = await llm.ainvoke([
            SystemMessage(content=(
                "You are answering on behalf of the user. Read the original "
                "request and pick a single reasonable answer to the agent's "
                "follow-up question. Reply with ONLY the answer text, no "
                "preamble."
            )),
            HumanMessage(content=(
                f"ORIGINAL_REQUEST:\n{original_goal}\n\n"
                f"AGENT_QUESTION:\n{question}\n\n"
                "Your answer:"
            )),
        ])
        return (getattr(resp, "content", str(resp)) or "").strip() or "Use your best judgment."
    except Exception as e:
        logger.warning("auto-answer failed: %s", e)
        return "Use your best judgment."


def _last_sentences(text: str, n: int = 2) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[-n:]).strip()
