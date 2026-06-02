-- Migration: 119 - Evaluation tool-call assertions and target types
-- Description: Adds tool-usage assertions to evaluations and prepares the
--              evaluation tables to also target workflows (target_type column).
-- Date: 2026-05-29

-- ============================================================================
-- Tool-call assertions on test cases & results
-- ============================================================================

ALTER TABLE evaluation_test_cases
    ADD COLUMN expected_tool_calls TEXT;
    -- JSON: [{"tool_name": "search", "args_match": {"q": "..."}, "required": true}]

ALTER TABLE evaluation_results
    ADD COLUMN actual_tool_calls TEXT;
    -- JSON: [{"tool_name": "search", "args": {...}, "result_snippet": "..."}]

ALTER TABLE evaluation_results
    ADD COLUMN tool_calls_passed INTEGER;
    -- 1/0/NULL — NULL when no expectations were defined for the test case.

-- ============================================================================
-- Target-type columns for datasets and runs (sets up workflow eval support)
-- ============================================================================

ALTER TABLE evaluation_datasets
    ADD COLUMN target_type TEXT NOT NULL DEFAULT 'agent';
    -- 'agent' | 'workflow'

ALTER TABLE evaluation_datasets
    ADD COLUMN workflow_id TEXT;

CREATE INDEX IF NOT EXISTS idx_eval_datasets_workflow
    ON evaluation_datasets(workflow_id);

-- evaluation_runs.agent_id is currently NOT NULL with an FK to standalone_agents.
-- Workflow runs need a nullable agent_id, so rebuild the table. SQLite has no
-- "drop NOT NULL" — we have to copy data through a fresh table.
CREATE TABLE evaluation_runs_new (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    agent_id TEXT,
    workflow_id TEXT,
    target_type TEXT NOT NULL DEFAULT 'agent',
    run_name TEXT,
    model_override TEXT,
    config_override TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    total_cases INTEGER DEFAULT 0,
    passed_cases INTEGER DEFAULT 0,
    failed_cases INTEGER DEFAULT 0,
    avg_score REAL,
    avg_latency_ms REAL,
    started_at TEXT,
    completed_at TEXT,
    error_message TEXT,
    created TEXT NOT NULL,
    created_by TEXT,
    FOREIGN KEY (dataset_id) REFERENCES evaluation_datasets(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES standalone_agents(id) ON DELETE CASCADE
);

INSERT INTO evaluation_runs_new (
    id, dataset_id, agent_id, workflow_id, target_type, run_name, model_override,
    config_override, status, progress, total_cases, passed_cases, failed_cases,
    avg_score, avg_latency_ms, started_at, completed_at, error_message, created, created_by
)
SELECT
    id, dataset_id, agent_id, NULL, 'agent', run_name, model_override,
    config_override, status, progress, total_cases, passed_cases, failed_cases,
    avg_score, avg_latency_ms, started_at, completed_at, error_message, created, created_by
FROM evaluation_runs;

DROP TABLE evaluation_runs;
ALTER TABLE evaluation_runs_new RENAME TO evaluation_runs;

CREATE INDEX IF NOT EXISTS idx_eval_runs_dataset ON evaluation_runs(dataset_id);
CREATE INDEX IF NOT EXISTS idx_eval_runs_agent ON evaluation_runs(agent_id);
CREATE INDEX IF NOT EXISTS idx_eval_runs_workflow ON evaluation_runs(workflow_id);
CREATE INDEX IF NOT EXISTS idx_eval_runs_status ON evaluation_runs(status);
CREATE INDEX IF NOT EXISTS idx_eval_runs_created ON evaluation_runs(created DESC);
