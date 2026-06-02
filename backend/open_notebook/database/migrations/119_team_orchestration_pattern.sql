-- Migration: 119 - Team Orchestration Pattern
-- Description:
--   Adds orchestration_pattern + pattern_config to agent_teams so teams can
--   declare *how* their agents collaborate (orchestrator-worker, sequential,
--   parallel, review-critique, router, group-chat). Pattern executors in
--   backend/open_notebook/agents/patterns/ dispatch on these fields.
--
--   Also adds standalone_agent_id + order_index to agent_instances so a team
--   row can be a thin reference to a reusable standalone_agent (instead of an
--   inline copy with no link). order_index drives sequential pattern ordering.
-- Date: 2026-05-29

-- 1. Pattern + per-pattern config on the team itself.
--    Default 'orchestrator_worker' is the most common shape; legacy teams keep
--    working because the langgraph_orchestrator falls back to its heuristic
--    path when pattern_config is null.
ALTER TABLE agent_teams
    ADD COLUMN orchestration_pattern TEXT DEFAULT 'orchestrator_worker';

ALTER TABLE agent_teams
    ADD COLUMN pattern_config TEXT;  -- JSON: orchestrator_agent_id, producer_agent_id, reviewer_agent_id, aggregator_agent_id, max_rounds, max_turns

-- 2. Back-reference from a team-membership row to the reusable standalone agent
--    it was instantiated from. Nullable so legacy team rows (created before
--    the redesign) keep working — they just don't have a back-link.
ALTER TABLE agent_instances
    ADD COLUMN standalone_agent_id TEXT;

-- 3. Position in the team. Drives sequential pattern's hand-off order; also
--    used as a stable display order for the other patterns.
ALTER TABLE agent_instances
    ADD COLUMN order_index INTEGER DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_agent_instances_standalone
    ON agent_instances(standalone_agent_id);

CREATE INDEX IF NOT EXISTS idx_agent_teams_pattern
    ON agent_teams(orchestration_pattern);
