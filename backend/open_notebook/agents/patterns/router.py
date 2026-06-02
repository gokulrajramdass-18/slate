"""
Router pattern (Concierge).

A designated router agent classifies the user's query and forwards it to one
specialist agent. The router's response is parsed for the chosen agent_id;
falls back to the first non-router agent if parsing fails.
"""

from __future__ import annotations

import re
from typing import Dict

from .base import PatternContext, PatternExecutor, PatternResult, StepEvent


_ID_RE = re.compile(r"agent[_\s\-]?id\s*[:=]\s*[\"']?([\w\-]+)", re.IGNORECASE)


class RouterExecutor(PatternExecutor):
    pattern_key = "router"

    async def execute(self, ctx: PatternContext) -> PatternResult:
        if not ctx.agents:
            return PatternResult(output="(no agents in team)")

        router = self._pick_router(ctx)
        specialists = [a for a in ctx.agents if a["id"] != router["id"]]
        if not specialists:
            out = await ctx.invoke_agent(router, ctx.query, sender_id=None)
            return PatternResult(
                output=out,
                agent_results=[{"agent_id": router["id"], "output": out}],
                metadata={"pattern": self.pattern_key, "degenerate": True},
            )

        await ctx.emit(StepEvent(
            kind="control",
            sender_id=None,
            recipient_id=router["id"],
            content=f"Router pattern: router={router.get('name')}, "
                    f"specialists={len(specialists)}.",
            metadata={"pattern": self.pattern_key, "router_id": router["id"]},
        ))

        # 1. Routing decision.
        spec_list = "\n".join(
            f"- agent_id={a['id']}, name={a.get('name')}, role={a.get('role')}: "
            f"{(a.get('system_prompt') or '').strip().splitlines()[0] if a.get('system_prompt') else ''}"
            for a in specialists
        )
        route_prompt = (
            f"User query:\n{ctx.query}\n\n"
            f"Available specialists:\n{spec_list}\n\n"
            f"Choose exactly one specialist for this query. "
            f"Reply with: agent_id: <the_id> followed by a one-line reason."
        )
        decision = await ctx.invoke_agent(router, route_prompt, sender_id=None, detect=False)

        chosen = self._parse_choice(decision, specialists)

        # 2. Forward to the specialist.
        out = await ctx.invoke_agent(chosen, ctx.query, sender_id=router["id"])

        return PatternResult(
            output=out,
            agent_results=[
                {"agent_id": router["id"], "agent_name": router.get("name"),
                 "role": "router", "output": decision},
                {"agent_id": chosen["id"], "agent_name": chosen.get("name"),
                 "role": chosen.get("role"), "output": out},
            ],
            metadata={
                "pattern": self.pattern_key,
                "router_id": router["id"],
                "chosen_id": chosen["id"],
            },
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _pick_router(ctx: PatternContext) -> Dict:
        chosen = ctx.find_agent(ctx.pattern_config.get("orchestrator_agent_id"))
        if chosen is not None:
            return chosen
        for role in ("planner", "coordinator", "router"):
            for a in ctx.agents:
                if (a.get("role") or "").lower() == role:
                    return a
        return ctx.agents[0]

    @staticmethod
    def _parse_choice(raw: str, specialists: list) -> Dict:
        ids = {a["id"] for a in specialists}
        # Direct ID match anywhere in the response.
        for sid in ids:
            if sid in (raw or ""):
                for a in specialists:
                    if a["id"] == sid:
                        return a
        m = _ID_RE.search(raw or "")
        if m:
            cand = m.group(1)
            for a in specialists:
                if a["id"].startswith(cand) or a.get("name") == cand or a.get("role") == cand:
                    return a
        # Match by name or role mentioned.
        lower = (raw or "").lower()
        for a in specialists:
            n = (a.get("name") or "").lower()
            r = (a.get("role") or "").lower()
            if (n and n in lower) or (r and r in lower):
                return a
        return specialists[0]
