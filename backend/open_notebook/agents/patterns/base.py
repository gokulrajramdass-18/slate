"""
Base types for pattern executors.

A PatternExecutor is the single abstraction every architecture pattern
implements. It receives a PatternContext (team + agents + LLM + A2A bus +
config + step sink) and returns a PatternResult.

The executor is responsible for the *coordination*; agent invocation goes
through PatternContext.invoke_agent() so every pattern uses the same A2A-or-
fallback transport. This keeps "via A2A" honest without forcing every legacy
team (which doesn't link standalone agents) to break.
"""

from __future__ import annotations

import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from open_notebook.agents.a2a.team_message_bus import A2ATeamMessageBus
from open_notebook.agents.patterns.clarification import (
    ClarificationPending,
    auto_answer_question,
    detect_clarification,
)
from open_notebook.database.repository import repo_execute

logger = logging.getLogger(__name__)


# A small event type emitted at every meaningful step so the team viewer can
# render a live timeline. Mirrors the message_type values already used by the
# agent_messages table (chat / task_assign / task_result / control).
@dataclass
class StepEvent:
    kind: str                       # "task_assign" | "task_result" | "chat" | "control"
    sender_id: Optional[str]        # agent id or None for "system"
    recipient_id: Optional[str]     # agent id or None for broadcast
    content: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PatternResult:
    """What an executor returns to the orchestrator."""
    output: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    agent_results: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PatternContext:
    """
    Everything a pattern executor needs to do its job.

    `agents` is a list of dicts shaped like agent_instances rows (id, role,
    name, system_prompt, model_override, standalone_agent_id, order_index).
    Using dicts (not the AgentInstance domain model) keeps this layer
    decoupled from pydantic validation quirks on extra columns.
    """
    team_id: str
    user_id: str
    query: str
    team: Dict[str, Any]
    agents: List[Dict[str, Any]]
    pattern_config: Dict[str, Any]
    llm: Any                                          # langchain BaseChatModel
    bus: Optional[A2ATeamMessageBus] = None           # may be None for legacy teams
    notebook_id: Optional[str] = None
    context_source_ids: Optional[List[str]] = None
    on_step: Optional[Callable[[StepEvent], Awaitable[None]]] = None
    # Used to tag every persisted agent_messages row so historical reloads
    # via GET /agents/executions/{id} only see this run's events.
    execution_id: Optional[str] = None

    # ---- human-in-the-loop ----------------------------------------------
    # When True, instead of pausing on a detected clarifying question we
    # synthesize an answer from the original goal and feed it back to the
    # asking agent. Read from team.config.auto_answer.
    auto_answer: bool = False
    # Skip clarification detection entirely. Used for the orchestrator/
    # router/synth-LLM calls where the LLM is reasoning about *what* to do
    # next and may produce a "which option?" framing that is NOT a question
    # to the human.
    detect_questions: bool = True
    # Map of {agent_id: user_reply}. On resume, when an executor invokes the
    # agent that originally asked, we splice the reply into the prompt so
    # the agent gets to "see" the user's answer and produce a deliverable.
    pending_answers: Dict[str, str] = field(default_factory=dict)
    # Per-pattern checkpoint the executor refreshes as it makes progress.
    # On a ClarificationPending raise, the dispatcher snapshots this for
    # the resume path.
    checkpoint_state: Dict[str, Any] = field(default_factory=dict)
    # On resume, the dispatcher pre-fills this with the prior checkpoint so
    # the executor can fast-forward instead of redoing finished work.
    resumed_from: Optional[Dict[str, Any]] = None

    # ---- helpers ---------------------------------------------------------

    def agents_by_id(self) -> Dict[str, Dict[str, Any]]:
        return {a["id"]: a for a in self.agents}

    def find_agent(self, agent_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not agent_id:
            return None
        return self.agents_by_id().get(agent_id)

    async def emit(self, event: StepEvent) -> None:
        """Persist the event as an agent_messages row and notify the listener."""
        msg_id = str(uuid.uuid4())
        await repo_execute(
            """INSERT INTO agent_messages
               (id, team_id, execution_id, sender_id, recipient_id, message_type, content, metadata, created)
               VALUES (:id, :team_id, :execution_id, :sender_id, :recipient_id, :message_type, :content, :metadata, :created)""",
            {
                "id": msg_id,
                "team_id": self.team_id,
                "execution_id": self.execution_id,
                "sender_id": event.sender_id or "system",
                "recipient_id": event.recipient_id,
                "message_type": event.kind,
                "content": event.content,
                "metadata": json.dumps(event.metadata) if event.metadata else None,
                "created": datetime.utcnow().isoformat(),
            },
        )
        if self.on_step is not None:
            try:
                await self.on_step(event)
            except Exception:  # pragma: no cover - listener errors must not kill the run
                logger.exception("on_step listener raised; continuing")

    async def invoke_agent(
        self,
        agent: Dict[str, Any],
        prompt: str,
        sender_id: Optional[str] = None,
        *,
        detect: Optional[bool] = None,
    ) -> str:
        """
        Ask one team agent to respond to `prompt`.

        Talks to the agent via the A2A bus when available. If the bus call
        fails (the installed `a2a-sdk` in this image has a protobuf-shaped
        `Message` that the existing `team_message_bus.py` was written
        against in pydantic shape — see context note in repo memory), we
        transparently fall back to a direct LLM call using the agent's
        system_prompt. Either way the call is bracketed by task_assign +
        task_result events so the UI sees a uniform handoff log.

        After the agent responds, we run the clarification detector. If the
        agent is asking the user a question:
        - With ``auto_answer=True`` we synthesize a plausible answer and
          re-invoke the same agent once, returning that response.
        - Otherwise we raise ``ClarificationPending``; the executor lets it
          bubble to the dispatcher, which pauses execution and signals the
          UI.

        Pass ``detect=False`` to skip detection (e.g. for orchestrator/
        synth/router LLM calls whose output isn't a candidate deliverable).
        """
        agent_id = agent["id"]
        agent_name = agent.get("name") or agent.get("role") or "agent"

        # On resume, splice the user's prior answer into this agent's prompt
        # so the agent sees it and produces a real deliverable this time.
        prior_answer = self.pending_answers.pop(agent_id, None)
        if prior_answer:
            prompt = (
                f"{prompt}\n\n"
                f"You previously asked the user a clarifying question. They "
                f"replied:\n\"\"\"\n{prior_answer}\n\"\"\"\n"
                f"Now produce the deliverable — do not ask another question."
            )

        await self.emit(StepEvent(
            kind="task_assign",
            sender_id=sender_id,
            recipient_id=agent_id,
            content=prompt,
            metadata={"agent_name": agent_name, "role": agent.get("role")},
        ))

        output = await self._run_agent_call(agent, prompt, sender_id, agent_name)

        # Clarification detection. Skip if the caller said so, if we just
        # spliced in an answer (the agent was told not to ask again), or if
        # the executor disabled it globally.
        do_detect = self.detect_questions if detect is None else detect
        if do_detect and not prior_answer:
            det = await detect_clarification(self.llm, output)
            if det.is_question:
                if self.auto_answer:
                    # Synthesize an answer and re-invoke ONCE. We don't
                    # recurse the detector — auto-answered runs trust the
                    # second response.
                    synth = await auto_answer_question(
                        self.llm,
                        original_goal=self.query,
                        question=det.question,
                    )
                    await self.emit(StepEvent(
                        kind="control",
                        sender_id=None,
                        recipient_id=agent_id,
                        content=f"Auto-answered: {synth}",
                        metadata={"auto_answer": True, "question": det.question},
                    ))
                    self.pending_answers[agent_id] = synth
                    return await self.invoke_agent(
                        agent, prompt, sender_id=sender_id, detect=False
                    )
                # Pause: persist the timeline event then bubble the typed
                # exception. Dispatcher snapshots checkpoint_state.
                await self.emit(StepEvent(
                    kind="task_result",
                    sender_id=agent_id,
                    recipient_id=sender_id,
                    content=output,
                    metadata={
                        "agent_name": agent_name,
                        "role": agent.get("role"),
                        "is_clarification": True,
                        "question": det.question,
                    },
                ))
                raise ClarificationPending(
                    question=det.question or output,
                    sender_agent_id=agent_id,
                    sender_name=agent_name,
                    sender_role=agent.get("role"),
                    checkpoint=dict(self.checkpoint_state),
                )

        await self.emit(StepEvent(
            kind="task_result",
            sender_id=agent_id,
            recipient_id=sender_id,
            content=output,
            metadata={"agent_name": agent_name, "role": agent.get("role")},
        ))
        return output

    async def _run_agent_call(
        self,
        agent: Dict[str, Any],
        prompt: str,
        sender_id: Optional[str],
        agent_name: str,
    ) -> str:
        """
        Run an agent and return its final text response.

        Resolution order:
        1) If the team-instance has a `standalone_agent_id` link, drive the
           shared standalone-agent runner. Every agent_step / tool_call /
           tool_result event the agent emits is translated into a team-
           level agent_messages row so the team timeline shows the same
           audit trail you'd see on the standalone agent's page — including
           which tools the agent used, with what arguments, and what they
           returned.
        2) Else, A2A bus path (currently dead-on-arrival in this image — see
           [[a2a-sdk-shape-mismatch]]).
        3) Else, direct llm.ainvoke fallback (legacy teams without a
           standalone link).
        """
        agent_id = agent["id"]
        sa_id = agent.get("standalone_agent_id")
        try:
            # ---- Path 1: standalone-agent runner --------------------------
            if sa_id:
                output = await self._run_via_standalone_runner(
                    agent, sa_id, prompt, sender_id,
                )
                return output

            # ---- Path 2: A2A bus (best-effort) ---------------------------
            output = ""
            if self.bus is not None and self.bus.is_local_agent(agent_id):
                try:
                    result = await self.bus.send_message(
                        sender_id=sender_id or "system",
                        recipient_id=agent_id,
                        content=prompt,
                    )
                    output = (result or {}).get("output") or ""
                    if not output:
                        artifacts = (result or {}).get("artifacts") or []
                        output = "\n".join(a.get("content", "") for a in artifacts).strip()
                except Exception as bus_err:
                    logger.warning(
                        "A2A bus failed for %s (%s); falling back to direct LLM",
                        agent_id, bus_err,
                    )
                    output = ""

            # ---- Path 3: direct LLM call --------------------------------
            if not output:
                output = await self._direct_llm_call(agent, prompt)
            return output
        except Exception as e:
            logger.exception("invoke_agent transport failed for %s", agent_id)
            await self.emit(StepEvent(
                kind="task_result",
                sender_id=agent_id,
                recipient_id=sender_id,
                content=f"[error] {e}",
                metadata={"agent_name": agent_name, "error": True},
            ))
            raise

    async def _run_via_standalone_runner(
        self,
        agent: Dict[str, Any],
        standalone_agent_id: str,
        prompt: str,
        sender_id: Optional[str],
    ) -> str:
        """
        Drive the shared standalone-agent runner for a team-member agent.

        Streams its dict events; for the ones that carry user-visible work
        (tool calls, agent steps with results) we write a team-level
        agent_messages row tagged with the agent's id so the team timeline
        renders them under the right card. Returns the final text response.
        """
        from open_notebook.database.repository import repo_query
        from api.services.standalone_agent_runner import (
            run_standalone_agent_events,
            resolve_credential_for_agent,
        )

        agent_id = agent["id"]
        agent_name = agent.get("name") or agent.get("role") or "agent"

        # Load the live standalone_agents row each time. It carries the
        # tool/skill/source IDs the runner needs.
        rows = await repo_query(
            "SELECT * FROM standalone_agents WHERE id = :id",
            {"id": standalone_agent_id},
        )
        if not rows:
            logger.warning("standalone_agent_id %s not found; falling back to direct LLM",
                           standalone_agent_id)
            return await self._direct_llm_call(agent, prompt)

        sa_data = rows[0]
        credential = await resolve_credential_for_agent(sa_data)
        if credential is None:
            logger.warning("No credential resolved for standalone agent %s; falling back",
                           standalone_agent_id)
            return await self._direct_llm_call(agent, prompt)

        accumulated = ""
        final_response = ""

        async for ev in run_standalone_agent_events(
            agent_data=sa_data,
            query=prompt,
            credential=credential,
            notebook_id=self.notebook_id,
            session_id=None,
            # Team invocations don't get their own row in the standalone
            # agent's execution history — that history is for direct chats
            # with the agent. The team owns its own execution row.
            record_execution=False,
        ):
            kind = ev.get("kind")
            if kind == "agent_step":
                # Surface meaningful steps as control-kind messages in the
                # team timeline; suppress the no-op "no X configured" lines
                # to keep noise down.
                action = ev.get("action") or ""
                status = ev.get("status") or ""
                result = ev.get("result")
                if status == "completed" and not result and action.startswith("No "):
                    continue
                content = action
                if result:
                    content = f"{action}\n{result}" if action else str(result)
                await self.emit(StepEvent(
                    kind="control",
                    sender_id=agent_id,
                    recipient_id=sender_id,
                    content=content,
                    metadata={
                        "agent_name": agent_name,
                        "role": agent.get("role"),
                        "step_number": ev.get("step_number"),
                        "status": status,
                    },
                ))
            elif kind == "tool_call":
                await self.emit(StepEvent(
                    kind="tool_call",
                    sender_id=agent_id,
                    recipient_id=sender_id,
                    content=f"Calling tool: {ev.get('tool')}",
                    metadata={
                        "agent_name": agent_name,
                        "role": agent.get("role"),
                        "tool_name": ev.get("tool"),
                        "tool_input": ev.get("arguments"),
                    },
                ))
            elif kind == "tool_result":
                await self.emit(StepEvent(
                    kind="tool_result",
                    sender_id=agent_id,
                    recipient_id=sender_id,
                    content=f"Tool {ev.get('tool')} returned",
                    metadata={
                        "agent_name": agent_name,
                        "role": agent.get("role"),
                        "tool_name": ev.get("tool"),
                        "tool_output": ev.get("result"),
                    },
                ))
            elif kind == "chunk":
                accumulated += ev.get("content") or ""
            elif kind == "done":
                final_response = ev.get("response") or accumulated
            elif kind == "error":
                # Surface the error and abort with a raise so the executor's
                # try/except records it the same way it would any other
                # transport failure.
                raise RuntimeError(ev.get("error") or "Standalone runner failed")
            # metadata kind: ignore — the team already has its own metadata.

        return final_response or accumulated

    async def _direct_llm_call(self, agent: Dict[str, Any], prompt: str) -> str:
        """Fallback path: direct LLM call using the agent's system prompt."""
        system_prompt = (
            agent.get("system_prompt")
            or f"You are a {agent.get('role', 'helpful')} agent named {agent.get('name', 'Assistant')}."
        )
        msgs = [SystemMessage(content=system_prompt), HumanMessage(content=prompt)]
        response = await self.llm.ainvoke(msgs)
        return getattr(response, "content", str(response)) or ""


class PatternExecutor(ABC):
    """One concrete collaboration pattern."""

    pattern_key: str = ""

    @abstractmethod
    async def execute(self, ctx: PatternContext) -> PatternResult:
        ...

    # Common helpers shared by multiple patterns.

    @staticmethod
    def _format_agent_list(agents: List[Dict[str, Any]]) -> str:
        lines = []
        for a in agents:
            lines.append(
                f"- id={a['id']} name={a.get('name')} role={a.get('role')}: "
                f"{(a.get('system_prompt') or '').strip().splitlines()[0:1] or ['(no description)']}"
            )
        return "\n".join(
            f"- id={a['id']} name={a.get('name')} role={a.get('role')}"
            for a in agents
        )
