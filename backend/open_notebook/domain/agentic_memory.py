"""
Agentic Memory domain models.

Defines the canonical 4-layer memory taxonomy used by the MemoryManager:

    Short-Term  - lives only in LangGraph state (no DB row)
    Episodic    - past interactions, stored in agent_memory.layer='episodic'
    Semantic    - agent-curated facts, stored in agent_memory.layer='semantic'
    Procedural  - tool-success patterns, stored in agent_procedural_memory

These dataclasses are intentionally plain (not ObjectModel-derived) because
the MemoryManager needs to issue compound SQL — JOINs, embedding similarity,
UPSERT-with-counter-increment — that the generic CRUD repository cannot
express. Each class still provides ``from_row`` and ``to_dict`` so the API
router can move data across the boundary uniformly.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# ============================================================================
# Layer enum
# ============================================================================

class MemoryLayer(str, Enum):
    """Canonical 4-layer agentic memory taxonomy."""

    SHORT_TERM = "short_term"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


# ============================================================================
# MemoryConfig — per-agent layer configuration
# ============================================================================

@dataclass
class MemoryConfig:
    """
    Per-agent configuration for the 4 memory layers.

    Stored under ``StandaloneAgent.config["memory"]``. ``default()`` returns a
    sensible starter config: short-term/episodic/semantic on, procedural off
    (procedural needs a few attempts of history before it becomes useful).
    """

    short_term_enabled: bool = True

    episodic_enabled: bool = True
    episodic_retention_days: int = 90
    episodic_max_entries: int = 500

    semantic_enabled: bool = True
    semantic_max_facts: int = 200

    procedural_enabled: bool = False
    procedural_min_attempts: int = 3
    procedural_min_success_rate: float = 0.6

    @classmethod
    def default(cls) -> "MemoryConfig":
        return cls()

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "MemoryConfig":
        """Build from a dict, falling back to defaults for missing keys.

        Tolerates ``None`` and unknown keys so we can round-trip safely as
        the schema grows.
        """
        if not data:
            return cls.default()
        defaults = asdict(cls.default())
        # Drop keys we don't recognise — keeps forward-compat clean.
        merged = {k: data.get(k, defaults[k]) for k in defaults}
        return cls(**merged)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
# Episodic — past interactions
# ============================================================================

@dataclass
class EpisodicMemory:
    """
    A single episodic memory: a distilled lesson from a past interaction.

    Wraps a row of ``agent_memory`` where ``layer='episodic'``. The optional
    ``source_message_id`` provides provenance back to the chat message that
    generated this episode.
    """

    id: str
    agent_id: Optional[str]
    notebook_id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    importance: float = 0.5
    source_message_id: Optional[str] = None
    expires_at: Optional[str] = None
    created: Optional[str] = None
    updated: Optional[str] = None

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "EpisodicMemory":
        return cls(
            id=row["id"],
            agent_id=row.get("agent_id"),
            notebook_id=row["notebook_id"],
            content=row["content"],
            metadata=_parse_json(row.get("metadata")) or {},
            tags=_parse_json(row.get("tags")) or [],
            importance=row.get("importance") or 0.5,
            source_message_id=row.get("source_message_id"),
            expires_at=row.get("expires_at"),
            created=row.get("created"),
            updated=row.get("updated"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
# Semantic — agent-curated facts (with embeddings)
# ============================================================================

@dataclass
class SemanticMemory:
    """
    A durable fact the agent has chosen to remember.

    Wraps a row of ``agent_memory`` where ``layer='semantic'``. Facts have an
    embedding so recall can match by meaning, not just keywords. The raw
    embedding bytes are not exposed via ``to_dict`` — they're a storage
    detail and far too large to send over the API.
    """

    id: str
    agent_id: Optional[str]
    notebook_id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    importance: float = 0.5
    access_count: int = 0
    last_accessed: Optional[str] = None
    has_embedding: bool = False
    similarity: Optional[float] = None  # Populated on recall, not on raw fetch
    created: Optional[str] = None
    updated: Optional[str] = None

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "SemanticMemory":
        return cls(
            id=row["id"],
            agent_id=row.get("agent_id"),
            notebook_id=row["notebook_id"],
            content=row["content"],
            metadata=_parse_json(row.get("metadata")) or {},
            tags=_parse_json(row.get("tags")) or [],
            importance=row.get("importance") or 0.5,
            access_count=row.get("access_count") or 0,
            last_accessed=row.get("last_accessed"),
            has_embedding=row.get("embedding") is not None,
            similarity=row.get("_similarity"),  # injected by ranking step
            created=row.get("created"),
            updated=row.get("updated"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
# Procedural — tool-sequence success patterns
# ============================================================================

@dataclass
class ProceduralMemory:
    """
    A learned tool-call pattern: "for tasks like X, sequence [a -> b] worked
    N out of M times."

    success_rate is computed (not stored) from the counters to avoid drift.
    """

    id: str
    agent_id: str
    task_pattern: str
    tool_sequence: List[str]
    success_count: int = 0
    failure_count: int = 0
    avg_duration_ms: Optional[int] = None
    example_inputs: List[Any] = field(default_factory=list)
    last_used: Optional[str] = None
    has_embedding: bool = False
    similarity: Optional[float] = None  # Populated on recall
    created: Optional[str] = None
    updated: Optional[str] = None

    @property
    def total_attempts(self) -> int:
        return self.success_count + self.failure_count

    @property
    def success_rate(self) -> float:
        total = self.total_attempts
        return (self.success_count / total) if total else 0.0

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "ProceduralMemory":
        return cls(
            id=row["id"],
            agent_id=row["agent_id"],
            task_pattern=row["task_pattern"],
            tool_sequence=_parse_json(row.get("tool_sequence")) or [],
            success_count=row.get("success_count") or 0,
            failure_count=row.get("failure_count") or 0,
            avg_duration_ms=row.get("avg_duration_ms"),
            example_inputs=_parse_json(row.get("example_inputs")) or [],
            last_used=row.get("last_used"),
            has_embedding=row.get("task_pattern_embedding") is not None,
            similarity=row.get("_similarity"),
            created=row.get("created"),
            updated=row.get("updated"),
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["success_rate"] = self.success_rate
        d["total_attempts"] = self.total_attempts
        return d


# ============================================================================
# RecallBundle — what MemoryManager.recall_for_agent returns
# ============================================================================

@dataclass
class RecallBundle:
    """The full recall result that gets formatted into a system prompt."""

    short_term: Dict[str, Any] = field(default_factory=dict)
    episodic: List[EpisodicMemory] = field(default_factory=list)
    semantic: List[SemanticMemory] = field(default_factory=list)
    procedural: List[ProceduralMemory] = field(default_factory=list)

    def is_empty(self) -> bool:
        return (
            not self.short_term
            and not self.episodic
            and not self.semantic
            and not self.procedural
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "short_term": self.short_term,
            "episodic": [m.to_dict() for m in self.episodic],
            "semantic": [m.to_dict() for m in self.semantic],
            "procedural": [m.to_dict() for m in self.procedural],
        }


# ============================================================================
# Helpers
# ============================================================================

def _parse_json(value: Any) -> Any:
    """Best-effort JSON parse: strings -> python objects, everything else passes through."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def utcnow_iso() -> str:
    """Single source of truth for ISO-8601 UTC timestamps used by this module."""
    return datetime.utcnow().isoformat()
