-- Migration: 120 - Agentic Memory Layers
-- Description: Promote agent_memory to a 4-layer model (Short-Term lives in
--              LangGraph state; Episodic + Semantic share the existing
--              agent_memory table via a new `layer` column; Procedural lives
--              in its own table because it tracks tool-sequence success rates
--              rather than text content).
-- Date: 2026-05-29
--
-- Background: migration 019 created agent_memory scoped to notebooks with a
-- `memory_type` discriminator (fact|conversation|insight|preference|skill).
-- We keep that column for backward-compat but layer the canonical taxonomy
-- on top via a new `layer` column ('episodic'|'semantic') and add an agent
-- foreign key so memories can be scoped to a single StandaloneAgent.
-- Procedural memory is decoupled because it stores tool-call patterns and
-- success counters, not free-form text.

-- ============================================================================
-- 1. EXTEND agent_memory
-- ============================================================================
-- SQLite ALTER TABLE only supports ADD COLUMN (no IF NOT EXISTS), so the
-- migration runner is responsible for skipping already-applied migrations.

ALTER TABLE agent_memory ADD COLUMN layer TEXT;
ALTER TABLE agent_memory ADD COLUMN agent_id TEXT;
ALTER TABLE agent_memory ADD COLUMN source_message_id TEXT;
ALTER TABLE agent_memory ADD COLUMN expires_at TEXT;

-- Backfill `layer` from the existing memory_type enum.
-- fact|preference  -> semantic   (durable, embeddable facts)
-- conversation|insight|context -> episodic  (time-anchored events)
-- skill                         -> episodic  (re-derived into procedural by
--                                  the file-memory migration script if the
--                                  skill content matches the tool-sequence
--                                  pattern; otherwise it stays episodic)
UPDATE agent_memory
SET layer = CASE
    WHEN memory_type IN ('fact', 'preference')         THEN 'semantic'
    WHEN memory_type IN ('conversation', 'insight', 'context') THEN 'episodic'
    WHEN memory_type = 'skill'                         THEN 'episodic'
    ELSE 'episodic'
END
WHERE layer IS NULL;

CREATE INDEX IF NOT EXISTS idx_agent_memory_agent_layer
    ON agent_memory(agent_id, layer);
CREATE INDEX IF NOT EXISTS idx_agent_memory_agent_expires
    ON agent_memory(agent_id, expires_at);
CREATE INDEX IF NOT EXISTS idx_agent_memory_layer
    ON agent_memory(layer);

-- ============================================================================
-- 2. NEW TABLE: agent_procedural_memory
-- ============================================================================
-- Tracks "for tasks like X, the sequence [tool_a -> tool_b] succeeded N/M
-- times." Updated automatically from execution outcomes; agents query the
-- top-rated patterns at recall time and the verbatim sequences are surfaced
-- in the system prompt as "Successful approaches".
--
-- success_rate is intentionally NOT stored — it is computed in queries as
-- success_count * 1.0 / NULLIF(success_count + failure_count, 0)
-- to avoid drift between the counters and the rate.

CREATE TABLE IF NOT EXISTS agent_procedural_memory (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    task_pattern TEXT NOT NULL,           -- canonical short phrase (e.g. "revenue_calculation")
    task_pattern_embedding BLOB,          -- vector for semantic match against new tasks
    tool_sequence TEXT NOT NULL,          -- JSON array of tool names in order
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    avg_duration_ms INTEGER,
    example_inputs TEXT,                  -- JSON array of representative inputs (capped)
    last_used TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (agent_id) REFERENCES standalone_agents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_proc_mem_agent_pattern
    ON agent_procedural_memory(agent_id, task_pattern);
CREATE INDEX IF NOT EXISTS idx_proc_mem_last_used
    ON agent_procedural_memory(last_used DESC);

-- ============================================================================
-- NOTES
-- ============================================================================
-- Layer mapping:
--   short_term -> in-memory only (LangGraph state); no DB table
--   episodic   -> agent_memory rows where layer='episodic'
--   semantic   -> agent_memory rows where layer='semantic' (with embedding)
--   procedural -> agent_procedural_memory
--
-- agent_id is nullable on agent_memory so legacy notebook-scoped rows still
-- validate. New writes always set it. notebook_id remains NOT NULL because
-- agents always run in a notebook context in the current product.
--
-- expires_at lets episodic memories age out per the agent's retention_days
-- setting; pruning is lazy (on recall) plus an optional periodic sweep.
