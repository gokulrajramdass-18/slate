"""
Pattern executors — pluggable team architectures.

Each executor implements one collaboration pattern (orchestrator-worker,
sequential, parallel, review/critique, router, group chat). They are picked
by orchestration_pattern on the agent_teams row and wired in by
api.services.langgraph_orchestrator at the top of execute().

All executors share a single shape:

    executor = get_executor(pattern)
    result   = await executor.execute(ctx)

where ctx is a PatternContext carrying everything an executor might need —
team, agents, the LLM, the A2A bus, the per-pattern config, and a sink for
emitting steps that the team viewer renders as a timeline.
"""

from .base import PatternContext, PatternExecutor, PatternResult, StepEvent
from .factory import get_executor

__all__ = [
    "PatternContext",
    "PatternExecutor",
    "PatternResult",
    "StepEvent",
    "get_executor",
]
