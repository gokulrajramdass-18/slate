"""
Sequential pattern (Assembly Line).

Agents run in user-defined order (`order_index` from agent_instances). Each
agent's output becomes the next agent's input — the `query` for the first
agent is the user's original request; for every later agent it's the output
of the previous one, framed as a hand-off.
"""

from __future__ import annotations

from .base import PatternContext, PatternExecutor, PatternResult, StepEvent


class SequentialExecutor(PatternExecutor):
    pattern_key = "sequential"

    async def execute(self, ctx: PatternContext) -> PatternResult:
        if not ctx.agents:
            return PatternResult(output="(no agents in team)", agent_results=[])

        ordered = sorted(
            ctx.agents,
            key=lambda a: (a.get("order_index") or 0, a.get("name") or ""),
        )

        await ctx.emit(StepEvent(
            kind="control",
            sender_id=None,
            recipient_id=None,
            content=f"Sequential pattern: {len(ordered)} agents.",
            metadata={"pattern": self.pattern_key, "order": [a["id"] for a in ordered]},
        ))

        # Resume support: replay completed steps from the prior checkpoint
        # instead of re-running them. The checkpoint is shaped:
        #   { "completed": [ {agent_id, output} ], "current": str|None }
        prior = (ctx.resumed_from or {}).get("completed") or []
        completed_ids = {p["agent_id"] for p in prior}
        results: list = list(prior)
        current = (results[-1]["output"] if results else ctx.query)

        for i, agent in enumerate(ordered):
            if agent["id"] in completed_ids:
                continue  # already done in a prior run
            prompt = (
                f"Original user request:\n{ctx.query}\n\n"
                f"Previous step output:\n{current}\n\n"
                f"Continue the work — your contribution as the "
                f"{agent.get('role') or agent.get('name')}."
            ) if i > 0 else ctx.query

            # Refresh the checkpoint BEFORE invoking. If the agent asks a
            # question, the dispatcher snapshots this as-is so resume picks
            # up at the same spot.
            ctx.checkpoint_state.clear()
            ctx.checkpoint_state.update({
                "completed": list(results),
                "current_index": i,
                "current_agent_id": agent["id"],
            })

            output = await ctx.invoke_agent(agent, prompt, sender_id=None)
            results.append({
                "agent_id": agent["id"],
                "agent_name": agent.get("name"),
                "role": agent.get("role"),
                "output": output,
            })
            current = output

        return PatternResult(
            output=current,
            agent_results=results,
            metadata={"pattern": self.pattern_key, "resumed": bool(prior)},
        )
