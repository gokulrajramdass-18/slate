"""
Orchestrator-Worker pattern (Supervisor / Subagents).

A designated orchestrator agent decomposes the user's goal into subtasks
expressed as a small JSON plan, dispatches each subtask to a worker via A2A,
collects results, then asks the orchestrator to synthesize a final answer.

If the orchestrator's plan can't be parsed (LLMs occasionally wander), we
fall back to a fan-out: every worker gets the original query, and the
orchestrator synthesizes from those.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from .base import PatternContext, PatternExecutor, PatternResult, StepEvent


_PLAN_SYSTEM = (
    "You are an orchestrator. Decompose the user's goal into a small set of "
    "subtasks (1–5) and assign each to one of the available workers by id. "
    "Respond ONLY with JSON of the form: "
    '{"subtasks":[{"agent_id":"...","task":"..."}]}'
)


class OrchestratorWorkerExecutor(PatternExecutor):
    pattern_key = "orchestrator_worker"

    async def execute(self, ctx: PatternContext) -> PatternResult:
        if not ctx.agents:
            return PatternResult(output="(no agents in team)")

        orchestrator = self._pick_orchestrator(ctx)
        workers = [a for a in ctx.agents if a["id"] != orchestrator["id"]]
        if not workers:
            # Single-agent team — degenerate to a direct call on the orchestrator.
            out = await ctx.invoke_agent(orchestrator, ctx.query, sender_id=None)
            return PatternResult(
                output=out, agent_results=[{"agent_id": orchestrator["id"], "output": out}],
                metadata={"pattern": self.pattern_key, "orchestrator_id": orchestrator["id"], "degenerate": True},
            )

        await ctx.emit(StepEvent(
            kind="control",
            sender_id=None,
            recipient_id=orchestrator["id"],
            content=f"Orchestrator-Worker pattern: orchestrator={orchestrator.get('name')}, "
                    f"workers={len(workers)}.",
            metadata={"pattern": self.pattern_key, "orchestrator_id": orchestrator["id"]},
        ))

        # 1. Plan
        plan_prompt = (
            f"User goal:\n{ctx.query}\n\n"
            f"Available workers:\n"
            + "\n".join(
                f"- agent_id={a['id']}, name={a.get('name')}, role={a.get('role')}"
                for a in workers
            )
            + "\n\n" + _PLAN_SYSTEM
        )
        # Orchestrator's plan output is structured JSON, not a question to
        # the user — skip detection.
        plan_raw = await ctx.invoke_agent(
            orchestrator, plan_prompt, sender_id=None, detect=False,
        )
        subtasks = self._parse_plan(plan_raw, workers)

        # 2. Dispatch
        worker_outputs: List[Dict[str, Any]] = []
        if subtasks:
            for st in subtasks:
                worker = ctx.find_agent(st["agent_id"]) or workers[0]
                out = await ctx.invoke_agent(worker, st["task"], sender_id=orchestrator["id"])
                worker_outputs.append({
                    "agent_id": worker["id"],
                    "agent_name": worker.get("name"),
                    "task": st["task"],
                    "output": out,
                })
        else:
            # Fallback: fan-out the original query to all workers.
            await ctx.emit(StepEvent(
                kind="control",
                sender_id=orchestrator["id"],
                recipient_id=None,
                content="Plan unparseable; falling back to fan-out.",
            ))
            for worker in workers:
                out = await ctx.invoke_agent(worker, ctx.query, sender_id=orchestrator["id"])
                worker_outputs.append({
                    "agent_id": worker["id"],
                    "agent_name": worker.get("name"),
                    "task": ctx.query,
                    "output": out,
                })

        # 3. Synthesize
        formatted = "\n\n".join(
            f"[{w.get('agent_name') or w['agent_id']}] task: {w['task']}\n{w['output']}"
            for w in worker_outputs
        )
        synth_prompt = (
            f"Original goal:\n{ctx.query}\n\n"
            f"Worker outputs:\n{formatted}\n\n"
            f"Synthesize the final answer for the user."
        )
        # The synthesis prompt explicitly asks for a final answer, not a
        # follow-up — skip detection.
        final = await ctx.invoke_agent(
            orchestrator, synth_prompt, sender_id=None, detect=False,
        )

        return PatternResult(
            output=final,
            agent_results=worker_outputs,
            metadata={
                "pattern": self.pattern_key,
                "orchestrator_id": orchestrator["id"],
                "subtask_count": len(worker_outputs),
            },
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _pick_orchestrator(ctx: PatternContext) -> Dict[str, Any]:
        chosen = ctx.find_agent(ctx.pattern_config.get("orchestrator_agent_id"))
        if chosen is not None:
            return chosen
        # Default: first planner/coordinator, else first agent.
        for role in ("planner", "coordinator"):
            for a in ctx.agents:
                if (a.get("role") or "").lower() == role:
                    return a
        return ctx.agents[0]

    @staticmethod
    def _parse_plan(raw: str, workers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract a JSON plan from the orchestrator response, tolerantly."""
        if not raw:
            return []
        # Try direct json, then a fenced block, then a regex object.
        candidates: List[str] = [raw]
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if m:
            candidates.insert(0, m.group(1))
        m2 = re.search(r"(\{.*\})", raw, re.DOTALL)
        if m2:
            candidates.append(m2.group(1))

        worker_ids = {w["id"] for w in workers}
        for c in candidates:
            try:
                data = json.loads(c)
                subs = data.get("subtasks") if isinstance(data, dict) else None
                if not isinstance(subs, list):
                    continue
                cleaned = []
                for s in subs:
                    if not isinstance(s, dict):
                        continue
                    aid = s.get("agent_id")
                    task = s.get("task") or s.get("description")
                    if not task:
                        continue
                    if aid not in worker_ids:
                        # Map by name as a fallback.
                        for w in workers:
                            if w.get("name") == aid or w.get("role") == aid:
                                aid = w["id"]
                                break
                        else:
                            aid = workers[0]["id"]
                    cleaned.append({"agent_id": aid, "task": str(task)})
                if cleaned:
                    return cleaned
            except (json.JSONDecodeError, TypeError):
                continue
        return []
