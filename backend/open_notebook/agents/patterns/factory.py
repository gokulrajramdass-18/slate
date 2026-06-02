"""
Pattern executor registry / factory.

Maps an orchestration_pattern string (as stored on agent_teams) to a
PatternExecutor instance. New patterns just register here.
"""

from __future__ import annotations

from typing import Dict

from .base import PatternExecutor
from .group_chat import GroupChatExecutor
from .orchestrator_worker import OrchestratorWorkerExecutor
from .parallel import ParallelExecutor
from .review_critique import ReviewCritiqueExecutor
from .router import RouterExecutor
from .sequential import SequentialExecutor


_REGISTRY: Dict[str, PatternExecutor] = {
    OrchestratorWorkerExecutor.pattern_key: OrchestratorWorkerExecutor(),
    SequentialExecutor.pattern_key:         SequentialExecutor(),
    ParallelExecutor.pattern_key:           ParallelExecutor(),
    ReviewCritiqueExecutor.pattern_key:     ReviewCritiqueExecutor(),
    RouterExecutor.pattern_key:             RouterExecutor(),
    GroupChatExecutor.pattern_key:          GroupChatExecutor(),
}


def get_executor(pattern: str) -> PatternExecutor | None:
    """Look up the executor for a given pattern. Returns None if unknown."""
    return _REGISTRY.get(pattern)


def supported_patterns() -> list[str]:
    return list(_REGISTRY.keys())
