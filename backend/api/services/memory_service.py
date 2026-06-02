"""
MemoryManager — orchestrates the 4 agentic memory layers.

    Short-Term  : LangGraph state passed through ``state`` (no DB)
    Episodic    : agent_memory rows where layer='episodic'
    Semantic    : agent_memory rows where layer='semantic' + embedding BLOB
    Procedural  : agent_procedural_memory rows + embedding BLOB

The manager exposes:

    recall_for_agent(...)    -> RecallBundle to inject into the system prompt
    format_for_prompt(...)   -> markdown string ready to prepend
    record_episode(...)      -> capture a turn
    record_fact(...)         -> capture a durable fact (with embedding)
    record_tool_outcome(...) -> upsert procedural success/failure counters
    prune_expired(...)       -> sweep TTL'd episodic rows

Embeddings: re-uses the same configured provider as source/bookmark embeddings
(see api.services.embedding_service). The embedding cache from
open_notebook.search.cache is used to avoid duplicate API calls.

Storage of vectors as BLOBs follows the same convention as source_embeddings:
np.float32 bytes via ``np.array(...).tobytes()`` and ``np.frombuffer`` on read.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional

import numpy as np

from open_notebook.database.repository import (
    repo_delete,
    repo_execute,
    repo_query,
    repo_update,
)
from open_notebook.domain.agentic_memory import (
    EpisodicMemory,
    MemoryConfig,
    MemoryLayer,
    ProceduralMemory,
    RecallBundle,
    SemanticMemory,
    utcnow_iso,
)
from open_notebook.domain.standalone_agent import StandaloneAgent
from open_notebook.search.cache import get_embedding_cache

logger = logging.getLogger(__name__)

# Soft cap on example_inputs per procedural row — tiny enough to keep the row
# small, large enough to be useful for "what did this work on before?".
PROCEDURAL_EXAMPLE_CAP = 5


# ============================================================================
# MemoryManager
# ============================================================================

class MemoryManager:
    """Stateless orchestrator over the 4 memory layers.

    All methods are async because every layer eventually touches the DB or an
    embedding provider. The class itself holds no per-request state; it's safe
    to instantiate at module load (see ``get_memory_manager`` below).
    """

    # ------------------------------------------------------------------
    # Recall
    # ------------------------------------------------------------------

    async def recall_for_agent(
        self,
        agent_id: str,
        query: str,
        state: Optional[Dict[str, Any]] = None,
        *,
        k_episodic: int = 5,
        k_semantic: int = 5,
        k_procedural: int = 3,
    ) -> RecallBundle:
        """
        Build a RecallBundle for one turn of agent execution.

        ``state`` is the LangGraph state snapshot whose interesting bits get
        surfaced as short-term memory; it's optional so this method can also
        be hit from the API for debugging.
        """
        agent = await self._load_agent(agent_id)
        if agent is None:
            return RecallBundle()

        config = agent.get_memory_config()
        bundle = RecallBundle()

        # Lazy expiry sweep — small, cheap, keeps the table tidy without a cron.
        if config.episodic_enabled:
            try:
                await self.prune_expired(agent_id)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("prune_expired failed for agent %s: %s", agent_id, exc)

        # 1. Short-term — pull whatever the caller wired in.
        if config.short_term_enabled and state:
            bundle.short_term = self._snapshot_state(state)

        # 2. Episodic — recency + keyword overlap.
        if config.episodic_enabled:
            bundle.episodic = await self._recall_episodic(agent_id, query, k_episodic)

        # 3. Semantic — embedding cosine similarity, keyword fallback.
        if config.semantic_enabled:
            bundle.semantic = await self._recall_semantic(agent_id, query, k_semantic)

        # 4. Procedural — embedding match against task_pattern + filters.
        if config.procedural_enabled:
            bundle.procedural = await self._recall_procedural(
                agent_id,
                query,
                k_procedural,
                min_attempts=config.procedural_min_attempts,
                min_success_rate=config.procedural_min_success_rate,
            )

        return bundle

    # ------------------------------------------------------------------
    # Prompt formatting
    # ------------------------------------------------------------------

    @staticmethod
    def format_for_prompt(bundle: RecallBundle) -> str:
        """Render the bundle as a markdown block for prepending to a prompt.

        Returns an empty string when nothing relevant was recalled, so the
        caller can safely concatenate without producing a stray header.
        """
        if bundle.is_empty():
            return ""

        sections: List[str] = ["## Agent Memory"]

        if bundle.short_term:
            sections.append("### Active context (short-term)")
            for k, v in bundle.short_term.items():
                sections.append(f"- **{k}**: {v}")

        if bundle.semantic:
            sections.append("### Remembered facts")
            for fact in bundle.semantic:
                tag_str = ""
                if fact.tags:
                    tag_str = " _" + ", ".join(fact.tags) + "_"
                sections.append(f"- {fact.content}{tag_str}")

        if bundle.episodic:
            sections.append("### Past episodes")
            for ep in bundle.episodic:
                sections.append(f"- {ep.content}")

        if bundle.procedural:
            sections.append("### Successful approaches")
            for proc in bundle.procedural:
                seq = " → ".join(proc.tool_sequence) or "(empty)"
                sections.append(
                    f"- For tasks like _{proc.task_pattern}_, the sequence "
                    f"[{seq}] succeeded {proc.success_count}/{proc.total_attempts} times."
                )

        sections.append("")  # trailing blank line
        return "\n".join(sections)

    # ------------------------------------------------------------------
    # Capture: episodic
    # ------------------------------------------------------------------

    async def record_episode(
        self,
        agent_id: str,
        notebook_id: str,
        content: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        importance: float = 0.5,
        source_message_id: Optional[str] = None,
    ) -> Optional[EpisodicMemory]:
        """
        Insert a new episodic memory row.

        Returns None if the agent has episodic memory disabled — callers can
        safely fire-and-forget.
        """
        agent = await self._load_agent(agent_id)
        if agent is None:
            return None
        config = agent.get_memory_config()
        if not config.episodic_enabled:
            return None

        now = utcnow_iso()
        expires_at = self._compute_expiry(config.episodic_retention_days)
        entry_id = str(uuid.uuid4())

        await repo_execute(
            """
            INSERT INTO agent_memory (
                id, notebook_id, agent_id, memory_type, layer,
                content, metadata, tags, importance,
                source_message_id, expires_at,
                created, updated
            ) VALUES (
                :id, :notebook_id, :agent_id, :memory_type, :layer,
                :content, :metadata, :tags, :importance,
                :source_message_id, :expires_at,
                :created, :updated
            )
            """,
            {
                "id": entry_id,
                "notebook_id": notebook_id,
                "agent_id": agent_id,
                "memory_type": "conversation",  # legacy column — keep populated
                "layer": MemoryLayer.EPISODIC.value,
                "content": content,
                "metadata": json.dumps(metadata) if metadata else None,
                "tags": json.dumps(tags) if tags else None,
                "importance": importance,
                "source_message_id": source_message_id,
                "expires_at": expires_at,
                "created": now,
                "updated": now,
            },
        )

        # Trim to max_entries — drop oldest by created.
        await self._trim_layer(agent_id, MemoryLayer.EPISODIC, config.episodic_max_entries)

        rows = await repo_query(
            "SELECT * FROM agent_memory WHERE id = :id", {"id": entry_id}
        )
        return EpisodicMemory.from_row(rows[0]) if rows else None

    # ------------------------------------------------------------------
    # Capture: semantic
    # ------------------------------------------------------------------

    async def record_fact(
        self,
        agent_id: str,
        notebook_id: str,
        content: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        importance: float = 0.5,
    ) -> Optional[SemanticMemory]:
        """Insert a durable fact, with embedding when an embedding provider is configured."""
        agent = await self._load_agent(agent_id)
        if agent is None:
            return None
        config = agent.get_memory_config()
        if not config.semantic_enabled:
            return None

        embedding_blob = await self._embed_to_blob(content)
        now = utcnow_iso()
        entry_id = str(uuid.uuid4())

        await repo_execute(
            """
            INSERT INTO agent_memory (
                id, notebook_id, agent_id, memory_type, layer,
                content, metadata, tags, embedding, importance,
                created, updated
            ) VALUES (
                :id, :notebook_id, :agent_id, :memory_type, :layer,
                :content, :metadata, :tags, :embedding, :importance,
                :created, :updated
            )
            """,
            {
                "id": entry_id,
                "notebook_id": notebook_id,
                "agent_id": agent_id,
                "memory_type": "fact",
                "layer": MemoryLayer.SEMANTIC.value,
                "content": content,
                "metadata": json.dumps(metadata) if metadata else None,
                "tags": json.dumps(tags) if tags else None,
                "embedding": embedding_blob,
                "importance": importance,
                "created": now,
                "updated": now,
            },
        )

        await self._trim_layer(agent_id, MemoryLayer.SEMANTIC, config.semantic_max_facts)

        rows = await repo_query(
            "SELECT * FROM agent_memory WHERE id = :id", {"id": entry_id}
        )
        return SemanticMemory.from_row(rows[0]) if rows else None

    # ------------------------------------------------------------------
    # Capture: procedural
    # ------------------------------------------------------------------

    async def record_tool_outcome(
        self,
        agent_id: str,
        task_pattern: str,
        tool_sequence: List[str],
        *,
        success: bool,
        duration_ms: Optional[int] = None,
        example_input: Optional[Any] = None,
    ) -> Optional[ProceduralMemory]:
        """
        UPSERT a procedural memory row.

        Keyed on (agent_id, task_pattern, tool_sequence). On hit, increments
        success_count or failure_count and rolls avg_duration_ms; on miss,
        inserts a fresh row and embeds the task_pattern for future recall.
        """
        agent = await self._load_agent(agent_id)
        if agent is None:
            return None
        config = agent.get_memory_config()
        if not config.procedural_enabled:
            return None
        if not task_pattern.strip() or not tool_sequence:
            return None

        seq_json = json.dumps(tool_sequence)
        now = utcnow_iso()

        rows = await repo_query(
            """
            SELECT * FROM agent_procedural_memory
            WHERE agent_id = :agent_id
              AND task_pattern = :task_pattern
              AND tool_sequence = :tool_sequence
            LIMIT 1
            """,
            {
                "agent_id": agent_id,
                "task_pattern": task_pattern,
                "tool_sequence": seq_json,
            },
        )

        if rows:
            existing = rows[0]
            new_success = (existing["success_count"] or 0) + (1 if success else 0)
            new_failure = (existing["failure_count"] or 0) + (0 if success else 1)
            total_before = (existing["success_count"] or 0) + (existing["failure_count"] or 0)
            new_avg = self._roll_avg(
                existing.get("avg_duration_ms"), total_before, duration_ms
            )

            examples = _safe_load_list(existing.get("example_inputs"))
            if example_input is not None and len(examples) < PROCEDURAL_EXAMPLE_CAP:
                examples.append(example_input)

            await repo_update(
                "agent_procedural_memory",
                existing["id"],
                {
                    "success_count": new_success,
                    "failure_count": new_failure,
                    "avg_duration_ms": new_avg,
                    "example_inputs": json.dumps(examples),
                    "last_used": now,
                    "updated": now,
                },
            )
            refreshed = await repo_query(
                "SELECT * FROM agent_procedural_memory WHERE id = :id",
                {"id": existing["id"]},
            )
            return ProceduralMemory.from_row(refreshed[0])

        # Miss — insert a new row.
        embedding_blob = await self._embed_to_blob(task_pattern)
        new_id = str(uuid.uuid4())
        examples = [example_input] if example_input is not None else []

        await repo_execute(
            """
            INSERT INTO agent_procedural_memory (
                id, agent_id, task_pattern, task_pattern_embedding,
                tool_sequence, success_count, failure_count,
                avg_duration_ms, example_inputs, last_used,
                created, updated
            ) VALUES (
                :id, :agent_id, :task_pattern, :task_pattern_embedding,
                :tool_sequence, :success_count, :failure_count,
                :avg_duration_ms, :example_inputs, :last_used,
                :created, :updated
            )
            """,
            {
                "id": new_id,
                "agent_id": agent_id,
                "task_pattern": task_pattern,
                "task_pattern_embedding": embedding_blob,
                "tool_sequence": seq_json,
                "success_count": 1 if success else 0,
                "failure_count": 0 if success else 1,
                "avg_duration_ms": duration_ms,
                "example_inputs": json.dumps(examples),
                "last_used": now,
                "created": now,
                "updated": now,
            },
        )
        rows = await repo_query(
            "SELECT * FROM agent_procedural_memory WHERE id = :id", {"id": new_id}
        )
        return ProceduralMemory.from_row(rows[0]) if rows else None

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    async def prune_expired(self, agent_id: str) -> int:
        """Delete episodic rows whose expires_at is in the past."""
        now = utcnow_iso()
        return await repo_execute(
            """
            DELETE FROM agent_memory
            WHERE agent_id = :agent_id
              AND layer = 'episodic'
              AND expires_at IS NOT NULL
              AND expires_at < :now
            """,
            {"agent_id": agent_id, "now": now},
        )

    async def delete_entry(self, entry_id: str, *, layer: MemoryLayer) -> bool:
        """Delete a single memory row by id, dispatched by layer."""
        if layer == MemoryLayer.PROCEDURAL:
            rows = await repo_query(
                "SELECT id FROM agent_procedural_memory WHERE id = :id", {"id": entry_id}
            )
            if not rows:
                return False
            await repo_delete("agent_procedural_memory", entry_id)
            return True
        rows = await repo_query(
            "SELECT id FROM agent_memory WHERE id = :id AND layer = :layer",
            {"id": entry_id, "layer": layer.value},
        )
        if not rows:
            return False
        await repo_delete("agent_memory", entry_id)
        return True

    # ------------------------------------------------------------------
    # Public list helpers used by the API router
    # ------------------------------------------------------------------

    async def list_episodic(
        self, agent_id: str, *, limit: int = 50, offset: int = 0
    ) -> List[EpisodicMemory]:
        rows = await repo_query(
            """
            SELECT * FROM agent_memory
            WHERE agent_id = :agent_id AND layer = 'episodic'
            ORDER BY created DESC
            LIMIT :limit OFFSET :offset
            """,
            {"agent_id": agent_id, "limit": limit, "offset": offset},
        )
        return [EpisodicMemory.from_row(r) for r in rows]

    async def list_semantic(
        self, agent_id: str, *, limit: int = 50, offset: int = 0
    ) -> List[SemanticMemory]:
        rows = await repo_query(
            """
            SELECT * FROM agent_memory
            WHERE agent_id = :agent_id AND layer = 'semantic'
            ORDER BY importance DESC, updated DESC
            LIMIT :limit OFFSET :offset
            """,
            {"agent_id": agent_id, "limit": limit, "offset": offset},
        )
        return [SemanticMemory.from_row(r) for r in rows]

    async def list_procedural(
        self, agent_id: str, *, limit: int = 50, offset: int = 0
    ) -> List[ProceduralMemory]:
        rows = await repo_query(
            """
            SELECT * FROM agent_procedural_memory
            WHERE agent_id = :agent_id
            ORDER BY
                CAST(success_count AS REAL) /
                    NULLIF(success_count + failure_count, 0) DESC,
                last_used DESC
            LIMIT :limit OFFSET :offset
            """,
            {"agent_id": agent_id, "limit": limit, "offset": offset},
        )
        return [ProceduralMemory.from_row(r) for r in rows]

    async def count_layer(self, agent_id: str, layer: MemoryLayer) -> int:
        """Total entries (across all pages) for a layer — for UI badges."""
        if layer == MemoryLayer.PROCEDURAL:
            rows = await repo_query(
                "SELECT COUNT(*) AS c FROM agent_procedural_memory WHERE agent_id = :agent_id",
                {"agent_id": agent_id},
            )
        else:
            rows = await repo_query(
                "SELECT COUNT(*) AS c FROM agent_memory WHERE agent_id = :agent_id AND layer = :layer",
                {"agent_id": agent_id, "layer": layer.value},
            )
        return int(rows[0]["c"]) if rows else 0

    # ==================================================================
    # Internal helpers
    # ==================================================================

    @staticmethod
    async def _load_agent(agent_id: str) -> Optional[StandaloneAgent]:
        try:
            return await StandaloneAgent.get(agent_id)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("StandaloneAgent.get(%s) failed: %s", agent_id, exc)
            return None

    @staticmethod
    def _snapshot_state(state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pluck the cheap, useful keys out of a LangGraph state dict.

        We deliberately ignore ``messages`` (way too big for a prompt block)
        and pick scalar/JSON-friendly keys the agent might want to reference.
        """
        if not isinstance(state, dict):
            return {}

        keep_keys = (
            "session_id",
            "notebook_id",
            "user_id",
            "iteration",
            "current_node_id",
            "task",
            "goal",
        )
        snapshot: Dict[str, Any] = {}
        for k in keep_keys:
            if k in state and state[k] is not None:
                v = state[k]
                # Only keep small primitives — avoid leaking giant payloads.
                if isinstance(v, (str, int, float, bool)):
                    snapshot[k] = v
        return snapshot

    @staticmethod
    def _compute_expiry(retention_days: int) -> Optional[str]:
        if retention_days is None or retention_days <= 0:
            return None
        from datetime import datetime, timedelta

        return (datetime.utcnow() + timedelta(days=retention_days)).isoformat()

    @staticmethod
    def _roll_avg(prev_avg: Optional[int], n: int, new_value: Optional[int]) -> Optional[int]:
        """Online running mean: avg' = (avg*n + x) / (n+1)."""
        if new_value is None:
            return prev_avg
        if prev_avg is None or n <= 0:
            return int(new_value)
        return int((prev_avg * n + new_value) / (n + 1))

    async def _trim_layer(
        self, agent_id: str, layer: MemoryLayer, max_entries: int
    ) -> None:
        """Delete the oldest rows in a layer when over the cap. Best-effort."""
        if max_entries is None or max_entries <= 0:
            return
        # SQLite supports DELETE ... WHERE id IN (SELECT ...).
        await repo_execute(
            """
            DELETE FROM agent_memory
            WHERE id IN (
                SELECT id FROM agent_memory
                WHERE agent_id = :agent_id AND layer = :layer
                ORDER BY importance ASC, created ASC
                LIMIT MAX(0, (
                    SELECT COUNT(*) FROM agent_memory
                    WHERE agent_id = :agent_id AND layer = :layer
                ) - :max_entries)
            )
            """,
            {
                "agent_id": agent_id,
                "layer": layer.value,
                "max_entries": max_entries,
            },
        )

    # ------------------------------------------------------------------
    # Recall helpers per layer
    # ------------------------------------------------------------------

    async def _recall_episodic(
        self, agent_id: str, query: str, k: int
    ) -> List[EpisodicMemory]:
        # Pull a generous candidate set, then re-rank in Python by recency
        # × keyword overlap. Avoids needing per-row embeddings on episodic.
        candidates = await repo_query(
            """
            SELECT * FROM agent_memory
            WHERE agent_id = :agent_id AND layer = 'episodic'
              AND (expires_at IS NULL OR expires_at > :now)
            ORDER BY created DESC
            LIMIT 50
            """,
            {"agent_id": agent_id, "now": utcnow_iso()},
        )
        if not candidates:
            return []

        terms = _tokenize(query)
        scored: List[tuple] = []
        for row in candidates:
            content = (row.get("content") or "").lower()
            tag_blob = (row.get("tags") or "").lower()
            score = (row.get("importance") or 0.5)
            if terms:
                hits = sum(1 for t in terms if t in content or t in tag_blob)
                score += hits * 0.5
            scored.append((score, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [EpisodicMemory.from_row(r) for _, r in scored[:k]]

    async def _recall_semantic(
        self, agent_id: str, query: str, k: int
    ) -> List[SemanticMemory]:
        rows = await repo_query(
            "SELECT * FROM agent_memory WHERE agent_id = :agent_id AND layer = 'semantic'",
            {"agent_id": agent_id},
        )
        if not rows:
            return []

        # Try semantic ranking; fall back to keyword if no embeddings.
        query_vec = await self._embed(query)
        if query_vec is not None:
            ranked = self._rank_by_similarity(rows, query_vec, "embedding", k)
        else:
            ranked = self._rank_by_keyword(rows, query, k)

        # Touch access counters for what we surfaced.
        if ranked:
            ids = [r["id"] for r in ranked]
            placeholders = ",".join(f":id{i}" for i in range(len(ids)))
            params: Dict[str, Any] = {f"id{i}": v for i, v in enumerate(ids)}
            params["now"] = utcnow_iso()
            await repo_execute(
                f"""
                UPDATE agent_memory
                SET access_count = COALESCE(access_count, 0) + 1,
                    last_accessed = :now
                WHERE id IN ({placeholders})
                """,
                params,
            )
        return [SemanticMemory.from_row(r) for r in ranked]

    async def _recall_procedural(
        self,
        agent_id: str,
        query: str,
        k: int,
        *,
        min_attempts: int,
        min_success_rate: float,
    ) -> List[ProceduralMemory]:
        rows = await repo_query(
            """
            SELECT * FROM agent_procedural_memory
            WHERE agent_id = :agent_id
              AND (success_count + failure_count) >= :min_attempts
              AND CAST(success_count AS REAL) /
                    NULLIF(success_count + failure_count, 0) >= :min_rate
            """,
            {
                "agent_id": agent_id,
                "min_attempts": min_attempts,
                "min_rate": min_success_rate,
            },
        )
        if not rows:
            return []

        query_vec = await self._embed(query)
        if query_vec is not None:
            ranked = self._rank_by_similarity(rows, query_vec, "task_pattern_embedding", k)
        else:
            # Substring fallback — match query terms against task_pattern.
            terms = _tokenize(query)
            scored: List[tuple] = []
            for row in rows:
                pattern = (row.get("task_pattern") or "").lower()
                hits = sum(1 for t in terms if t in pattern) if terms else 0
                # Tie-break by overall success rate.
                total = (row.get("success_count") or 0) + (row.get("failure_count") or 0)
                rate = (row.get("success_count") or 0) / total if total else 0.0
                scored.append((hits + rate, row))
            scored.sort(key=lambda x: x[0], reverse=True)
            ranked = [r for _, r in scored[:k]]

        return [ProceduralMemory.from_row(r) for r in ranked]

    # ------------------------------------------------------------------
    # Embedding helpers
    # ------------------------------------------------------------------

    async def _embed(self, text: str) -> Optional[List[float]]:
        """
        Generate an embedding via the configured provider. Returns None if
        embeddings are unavailable — callers should fall back to keyword.

        Routes through the embedding cache for de-duplication.
        """
        if not text or not text.strip():
            return None
        try:
            from api.routers.credentials import _credentials_store
            from api.services.settings import get_setting
        except Exception:
            return None

        try:
            embedding_model_id = await get_setting("embedding_model_id", "")
            if not embedding_model_id:
                return None
            credential = _credentials_store.get(embedding_model_id)
            if not credential:
                return None

            cache = get_embedding_cache()
            cached = cache.get(text, embedding_model_id)
            if cached is not None:
                return cached

            provider = credential.get("provider", "")
            if provider == "sap_ai_core":
                api_url = "http://slate-sap-ai-core-api:5056"
                api_key = ""
                model_name = (
                    credential.get("deployment_model_name")
                    or credential.get("model_name", "text-embedding-3-large")
                )
            else:
                api_url = credential.get("base_url")
                api_key = credential.get("api_key", "")
                model_name = (
                    credential.get("deployment_model_name")
                    or credential.get("model_name")
                    or credential.get("name", "text-embedding-ada-002")
                )

            if not api_url:
                return None

            from api.services.http_client import http_client_manager

            client = http_client_manager.get_client()
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            response = await client.post(
                f"{api_url}/embeddings",
                headers=headers,
                json={"model": model_name, "input": text},
                timeout=30.0,
            )
            if response.status_code != 200:
                logger.warning(
                    "Embedding API returned %s for memory recall: %s",
                    response.status_code,
                    response.text[:200],
                )
                return None

            data = response.json()
            embedding = data["data"][0]["embedding"]
            cache.set(text, embedding_model_id, embedding)
            return embedding
        except Exception as exc:
            logger.warning("Memory embedding failed; falling back to keyword: %s", exc)
            return None

    async def _embed_to_blob(self, text: str) -> Optional[bytes]:
        vec = await self._embed(text)
        if vec is None:
            return None
        return np.array(vec, dtype=np.float32).tobytes()

    @staticmethod
    def _rank_by_similarity(
        rows: List[Dict[str, Any]],
        query_vec: List[float],
        embedding_col: str,
        k: int,
    ) -> List[Dict[str, Any]]:
        """Cosine-similarity rank rows whose ``embedding_col`` is a float32 BLOB.

        Rows without an embedding fall back to similarity = -1 so they sort
        last; we still return them rather than dropping silently because the
        agent may have written facts before embeddings were configured.
        """
        q = np.array(query_vec, dtype=np.float32)
        q_norm = float(np.linalg.norm(q))
        if q_norm == 0:
            return rows[:k]

        scored: List[tuple] = []
        for row in rows:
            blob = row.get(embedding_col)
            if not blob:
                scored.append((-1.0, row))
                continue
            try:
                if isinstance(blob, bytes):
                    v = np.frombuffer(blob, dtype=np.float32)
                else:
                    v = np.array(blob, dtype=np.float32)
                v_norm = float(np.linalg.norm(v))
                if v_norm == 0:
                    scored.append((-1.0, row))
                    continue
                sim = float(np.dot(q, v) / (q_norm * v_norm))
                row["_similarity"] = sim
                scored.append((sim, row))
            except Exception:
                scored.append((-1.0, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:k]]

    @staticmethod
    def _rank_by_keyword(
        rows: List[Dict[str, Any]], query: str, k: int
    ) -> List[Dict[str, Any]]:
        terms = _tokenize(query)
        if not terms:
            return rows[:k]
        scored: List[tuple] = []
        for row in rows:
            content = (row.get("content") or "").lower()
            score = sum(1 for t in terms if t in content)
            if score:
                scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:k]]


# ============================================================================
# Helpers and singleton
# ============================================================================

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]{3,}")


def _tokenize(text: str) -> List[str]:
    """Bag-of-words tokenizer — drops common stop-ish noise and short tokens."""
    if not text:
        return []
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _safe_load_list(raw: Any) -> List[Any]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Module-level singleton — MemoryManager itself is stateless."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager


# ----------------------------------------------------------------------------
# Convenience: extract a "task pattern" from a free-form user query.
# Cheap heuristic — first verb-ish + first noun-ish word, joined by underscore.
# Used by LangGraph hooks so they can capture procedural memory without
# requiring callers to invent a label by hand.
# ----------------------------------------------------------------------------

_VERBISH = {
    "calculate", "compute", "summarize", "summarise", "search", "find",
    "explain", "analyze", "analyse", "extract", "translate", "compare",
    "list", "show", "describe", "review", "fetch", "lookup", "get",
    "build", "generate", "draft", "write", "rewrite", "rephrase",
}


def derive_task_pattern(query: str, *, max_words: int = 4) -> str:
    """
    Distil a query into a short canonical phrase usable as a procedural key.

    Strategy: first recognised verb + the next ``max_words-1`` content words.
    Falls back to the first ``max_words`` content words. Always lowercase,
    underscore-joined, never empty (returns "task" if the query is unparseable).
    """
    tokens = _tokenize(query)
    if not tokens:
        return "task"
    verb_idx = next((i for i, t in enumerate(tokens) if t in _VERBISH), None)
    if verb_idx is not None:
        chunk = tokens[verb_idx : verb_idx + max_words]
    else:
        chunk = tokens[:max_words]
    return "_".join(chunk) or "task"
