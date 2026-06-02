"""
Review & Critique pattern (Multi-Agent Loop).

Producer drafts → reviewer critiques → producer revises, looping up to
max_rounds (default 3) or until the reviewer signals approval. The producer
and reviewer are picked from pattern_config; if absent, defaults are the
first agent (producer) and the first reviewer/judge agent (reviewer), else
the second agent.
"""

from __future__ import annotations

import re
from typing import Dict

from .base import PatternContext, PatternExecutor, PatternResult, StepEvent


_APPROVED_RE = re.compile(r"\b(approved|ship\s*it|looks\s*good|lgtm)\b", re.IGNORECASE)


class ReviewCritiqueExecutor(PatternExecutor):
    pattern_key = "review_critique"

    async def execute(self, ctx: PatternContext) -> PatternResult:
        if len(ctx.agents) < 2:
            # Need at least two agents for a producer/reviewer split.
            agent = ctx.agents[0] if ctx.agents else None
            if agent is None:
                return PatternResult(output="(no agents in team)")
            out = await ctx.invoke_agent(agent, ctx.query, sender_id=None)
            return PatternResult(
                output=out,
                agent_results=[{"agent_id": agent["id"], "output": out}],
                metadata={"pattern": self.pattern_key, "degenerate": True},
            )

        producer = self._pick(ctx, "producer_agent_id", default_role=None, fallback_index=0)
        reviewer = self._pick(
            ctx, "reviewer_agent_id",
            default_role="reviewer",
            fallback_index=1,
            avoid_id=producer["id"],
        )
        max_rounds = int(ctx.pattern_config.get("max_rounds") or 3)
        max_rounds = max(1, min(max_rounds, 20))

        await ctx.emit(StepEvent(
            kind="control",
            sender_id=None,
            recipient_id=None,
            content=f"Review & Critique: producer={producer.get('name')}, "
                    f"reviewer={reviewer.get('name')}, max_rounds={max_rounds}.",
            metadata={
                "pattern": self.pattern_key,
                "producer_id": producer["id"],
                "reviewer_id": reviewer["id"],
                "max_rounds": max_rounds,
            },
        ))

        history = []
        last_critique = ""
        last_draft = ""
        approved = False

        for round_num in range(1, max_rounds + 1):
            # 1. Producer drafts (or revises).
            if round_num == 1:
                draft_prompt = ctx.query
            else:
                draft_prompt = (
                    f"Original request:\n{ctx.query}\n\n"
                    f"Your previous draft:\n{last_draft}\n\n"
                    f"Reviewer's critique:\n{last_critique}\n\n"
                    f"Revise. Address each critique point."
                )
            last_draft = await ctx.invoke_agent(producer, draft_prompt, sender_id=reviewer["id"] if round_num > 1 else None)

            # 2. Reviewer critiques.
            review_prompt = (
                f"Request:\n{ctx.query}\n\n"
                f"Draft (round {round_num}):\n{last_draft}\n\n"
                f"Critique the draft. If it fully meets the request, reply with "
                f"the single word APPROVED on its own line. Otherwise list "
                f"specific, actionable fixes."
            )
            last_critique = await ctx.invoke_agent(reviewer, review_prompt, sender_id=producer["id"])

            history.append({
                "round": round_num,
                "draft": last_draft,
                "critique": last_critique,
            })

            if _APPROVED_RE.search(last_critique or ""):
                approved = True
                break

        return PatternResult(
            output=last_draft,
            agent_results=history,
            metadata={
                "pattern": self.pattern_key,
                "producer_id": producer["id"],
                "reviewer_id": reviewer["id"],
                "rounds_used": len(history),
                "approved": approved,
            },
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _pick(
        ctx: PatternContext,
        config_key: str,
        default_role: str | None,
        fallback_index: int,
        avoid_id: str | None = None,
    ) -> Dict:
        chosen = ctx.find_agent(ctx.pattern_config.get(config_key))
        if chosen is not None:
            return chosen
        if default_role:
            for a in ctx.agents:
                if (a.get("role") or "").lower() == default_role and a["id"] != avoid_id:
                    return a
        # Last resort: pick by index, skipping `avoid_id`.
        candidates = [a for a in ctx.agents if a["id"] != avoid_id]
        return candidates[min(fallback_index, len(candidates) - 1)] if candidates else ctx.agents[0]
