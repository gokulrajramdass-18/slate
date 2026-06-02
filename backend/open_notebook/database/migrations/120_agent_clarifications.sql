-- Migration: 120 - Agent Clarifications (Human-in-the-Loop pause/resume)
-- Description:
--   When a pattern executor detects that an agent has asked the user a
--   clarifying question (instead of producing a deliverable), execution is
--   paused: the question is persisted here, the parent agent_executions row
--   is marked status='awaiting_input', and the SSE stream emits an
--   awaiting_user_input event so the UI can show a popup. When the user
--   answers, the resume endpoint runs the pattern again with a checkpoint
--   that replays already-completed agent steps and re-asks the questioner
--   with the user's answer appended.
-- Date: 2026-05-29

-- 1. Per-question record. status walks pending -> answered (or cancelled).
CREATE TABLE IF NOT EXISTS agent_clarifications (
    id              TEXT PRIMARY KEY,
    execution_id    TEXT NOT NULL,
    team_id         TEXT NOT NULL,
    sender_agent_id TEXT,           -- agent that asked, NULL if synthesized
    sender_name     TEXT,
    sender_role     TEXT,
    question        TEXT NOT NULL,
    answer          TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending | answered | cancelled
    -- Snapshot of the executor's progress at the moment of the question.
    -- JSON shaped per-pattern (see backend/open_notebook/agents/patterns/).
    checkpoint      TEXT,
    created         TEXT NOT NULL,
    answered_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_clarifications_exec
    ON agent_clarifications(execution_id);
CREATE INDEX IF NOT EXISTS idx_clarifications_status
    ON agent_clarifications(status);

-- 2. Surface the awaiting state on the parent execution row so listings can
--    show the "needs input" badge without joining.
-- (No column needed — we reuse agent_executions.status with a new value
--  'awaiting_input' which the API layer already accepts as a free string.)
