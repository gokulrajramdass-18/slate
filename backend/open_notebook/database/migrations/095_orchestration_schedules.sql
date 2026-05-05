-- Migration: Orchestration Schedules
-- Add table for scheduling orchestration executions

CREATE TABLE IF NOT EXISTS orchestration_schedules (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    goal TEXT NOT NULL,
    notebook_id TEXT,
    resources TEXT,  -- JSON serialized resources
    config TEXT,     -- JSON serialized config
    schedule_type TEXT NOT NULL CHECK(schedule_type IN ('once', 'recurring')),
    schedule_config TEXT NOT NULL,  -- JSON: {datetime} for once, {cron} for recurring
    next_run TEXT,   -- ISO datetime of next execution
    last_run TEXT,   -- ISO datetime of last execution
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'paused', 'completed', 'failed')),
    execution_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- SKIPPED: Table 'orchestration_schedules' doesn't exist - -- SKIPPED: Table 'orchestration_schedules' doesn't exist - CREATE INDEX IF NOT EXISTS idx_orchestration_schedules_user ON orchestration_schedules(user_id);
-- SKIPPED: Table 'orchestration_schedules' doesn't exist - -- SKIPPED: Table 'orchestration_schedules' doesn't exist - CREATE INDEX IF NOT EXISTS idx_orchestration_schedules_status ON orchestration_schedules(status);
-- SKIPPED: Table 'orchestration_schedules' doesn't exist - -- SKIPPED: Table 'orchestration_schedules' doesn't exist - CREATE INDEX IF NOT EXISTS idx_orchestration_schedules_next_run ON orchestration_schedules(next_run);
-- SKIPPED: Table 'orchestration_schedules' doesn't exist - -- SKIPPED: Table 'orchestration_schedules' doesn't exist - CREATE INDEX IF NOT EXISTS idx_orchestration_schedules_type ON orchestration_schedules(schedule_type);

-- Add schedule_id column to orchestrations table to link to schedule
-- NOTE: Commented out - orchestrations table created in 096, this column should be added there
-- ALTER TABLE orchestrations ADD COLUMN schedule_id TEXT;
-- CREATE INDEX IF NOT EXISTS idx_orchestrations_schedule ON orchestrations(schedule_id);
