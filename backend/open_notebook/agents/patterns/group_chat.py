"""
Group Chat / Swarm pattern.

All agents share a turn-based chat. Each turn, the next agent in round-robin
order sees the running transcript and contributes one message. The chat
stops when an agent emits the sentinel `<<DONE>>` (case-insensitive) or
max_turns is reached. A final synthesis LLM call summarizes the transcript
into one user-facing answer.

Total messages = up to max_turns × len(agents). max_turns defaults to 5.
"""

from __future__ import annotations

import re
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage

from .base import PatternContext, PatternExecutor, PatternResult, StepEvent


_DONE_RE = re.compile(r"<<\s*DONE\s*>>", re.IGNORECASE)


class GroupChatExecutor(PatternExecutor):
    pattern_key = "group_chat"

    async def execute(self, ctx: PatternContext) -> PatternResult:
        if not ctx.agents:
            return PatternResult(output="(no agents in team)")

        max_turns = int(ctx.pattern_config.get("max_turns") or 5)
        max_turns = max(1, min(max_turns, 50))

        roster = "\n".join(
            f"- {a.get('name')} ({a.get('role')})"
            for a in ctx.agents
        )

        await ctx.emit(StepEvent(
            kind="control",
            sender_id=None,
            recipient_id=None,
            content=f"Group Chat: {len(ctx.agents)} agents, max_turns={max_turns}.",
            metadata={"pattern": self.pattern_key, "max_turns": max_turns},
        ))

        transcript: List[str] = []
        agent_results: List[dict] = []
        done = False

        for round_num in range(1, max_turns + 1):
            for agent in ctx.agents:
                prompt = self._render_prompt(ctx, agent, transcript, round_num, roster)
                msg = await ctx.invoke_agent(agent, prompt, sender_id=None)
                line = f"{agent.get('name') or agent['id']}: {msg}"
                transcript.append(line)
                agent_results.append({
                    "round": round_num,
                    "agent_id": agent["id"],
                    "agent_name": agent.get("name"),
                    "output": msg,
                })
                if _DONE_RE.search(msg or ""):
                    done = True
                    break
            if done:
                break

        final = await self._synthesize(ctx, transcript)

        return PatternResult(
            output=final,
            agent_results=agent_results,
            metadata={
                "pattern": self.pattern_key,
                "rounds_used": (round_num if done else max_turns),
                "messages": len(agent_results),
                "stopped_on_done": done,
            },
        )

    @staticmethod
    def _render_prompt(ctx, agent, transcript, round_num, roster) -> str:
        history = "\n".join(transcript) if transcript else "(no messages yet)"
        return (
            f"You are {agent.get('name')} ({agent.get('role')}). You are part "
            f"of a multi-agent group chat working on this request:\n\n"
            f"{ctx.query}\n\n"
            f"Roster:\n{roster}\n\n"
            f"Conversation so far:\n{history}\n\n"
            f"Round {round_num}. Add your single next message. If the team has "
            f"reached a complete answer, end your message with <<DONE>>."
        )

    async def _synthesize(self, ctx: PatternContext, transcript: List[str]) -> str:
        await ctx.emit(StepEvent(
            kind="control",
            sender_id=None,
            recipient_id=None,
            content="Synthesizing final answer from group chat transcript.",
        ))
        joined = "\n".join(transcript) if transcript else "(empty)"
        sys = (
            "You are a synthesis assistant. Given a multi-agent chat transcript, "
            "produce one well-structured final answer for the user. Reflect "
            "agreed conclusions; surface unresolved points succinctly."
        )
        user = f"Original request:\n{ctx.query}\n\nTranscript:\n{joined}"
        resp = await ctx.llm.ainvoke([SystemMessage(content=sys), HumanMessage(content=user)])
        return getattr(resp, "content", str(resp)) or ""
