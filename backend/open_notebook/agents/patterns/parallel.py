"""
Parallel pattern (Fan-Out / Fan-In).

The same query is sent to every team agent concurrently via A2A. An
aggregator step then combines the results — either via a designated
aggregator agent (pattern_config.aggregator_agent_id) or, if not set, a
direct LLM synthesis call.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from .base import PatternContext, PatternExecutor, PatternResult, StepEvent


class ParallelExecutor(PatternExecutor):
    pattern_key = "parallel"

    async def execute(self, ctx: PatternContext) -> PatternResult:
        if not ctx.agents:
            return PatternResult(output="(no agents in team)")

        aggregator_id = ctx.pattern_config.get("aggregator_agent_id")
        # Aggregator agent (if any) does NOT participate in the fan-out —
        # it consumes everyone else's output.
        workers = [a for a in ctx.agents if a["id"] != aggregator_id]

        await ctx.emit(StepEvent(
            kind="control",
            sender_id=None,
            recipient_id=None,
            content=f"Parallel pattern: fan-out to {len(workers)} agents.",
            metadata={"pattern": self.pattern_key, "workers": [a["id"] for a in workers]},
        ))

        async def _run_one(agent: Dict[str, Any]) -> Dict[str, Any]:
            try:
                out = await ctx.invoke_agent(agent, ctx.query, sender_id=None)
                return {"agent_id": agent["id"], "agent_name": agent.get("name"),
                        "role": agent.get("role"), "output": out, "ok": True}
            except Exception as e:
                return {"agent_id": agent["id"], "agent_name": agent.get("name"),
                        "role": agent.get("role"), "output": str(e), "ok": False}

        worker_results = await asyncio.gather(*[_run_one(a) for a in workers])

        # Aggregation step.
        formatted = self._format_results(worker_results)
        aggregator = ctx.find_agent(aggregator_id)
        if aggregator is not None:
            agg_prompt = (
                f"Original request:\n{ctx.query}\n\n"
                f"You are the aggregator. The following specialists each "
                f"answered independently. Synthesize one coherent answer that "
                f"reconciles overlaps and surfaces disagreements.\n\n"
                f"{formatted}"
            )
            final = await ctx.invoke_agent(aggregator, agg_prompt, sender_id=None)
        else:
            final = await self._llm_synthesize(ctx, formatted)

        return PatternResult(
            output=final,
            agent_results=worker_results,
            metadata={"pattern": self.pattern_key, "aggregator_agent_id": aggregator_id},
        )

    @staticmethod
    def _format_results(results: List[Dict[str, Any]]) -> str:
        chunks = []
        for r in results:
            label = f"[{r.get('agent_name') or r.get('role') or r['agent_id']}]"
            chunks.append(f"{label}\n{r['output']}\n")
        return "\n".join(chunks)

    async def _llm_synthesize(self, ctx: PatternContext, formatted: str) -> str:
        system = (
            "You are a synthesis assistant. Given several independent agent "
            "answers to the same question, merge them into one well-structured "
            "response that preserves consensus, calls out disagreements, and "
            "removes redundancy."
        )
        user = f"Original question:\n{ctx.query}\n\nAgent answers:\n{formatted}"
        await ctx.emit(StepEvent(
            kind="control",
            sender_id=None,
            recipient_id=None,
            content="Aggregating with synthesis LLM call.",
        ))
        resp = await ctx.llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
        return getattr(resp, "content", str(resp)) or ""
