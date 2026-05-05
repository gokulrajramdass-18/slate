-- Migration: Create orchestrations table for persisting autonomous orchestrations
-- Version: 050

-- Orchestrations table
CREATE TABLE IF NOT EXISTS orchestrations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    goal TEXT NOT NULL,
    notebook_id TEXT,
    status TEXT NOT NULL DEFAULT 'starting',
    current_phase TEXT DEFAULT 'starting',
    progress REAL DEFAULT 0.0,
    orchestration_mode TEXT,
    team_id TEXT,
    result TEXT,  -- JSON
    error TEXT,
    schedule_id TEXT,  -- From migration 095 - moved here to fix ordering
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- SKIPPED: Table 'orchestrations' doesn't exist - -- SKIPPED: Table 'orchestrations' doesn't exist - CREATE INDEX IF NOT EXISTS idx_orchestrations_user_id ON orchestrations(user_id);
-- SKIPPED: Table 'orchestrations' doesn't exist - -- SKIPPED: Table 'orchestrations' doesn't exist - CREATE INDEX IF NOT EXISTS idx_orchestrations_created_at ON orchestrations(created_at DESC);
-- SKIPPED: Table 'orchestrations' doesn't exist - -- SKIPPED: Table 'orchestrations' doesn't exist - CREATE INDEX IF NOT EXISTS idx_orchestrations_status ON orchestrations(status);

-- Orchestration events table
CREATE TABLE IF NOT EXISTS orchestration_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    orchestration_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_data TEXT,  -- JSON
    timestamp TEXT NOT NULL,
    FOREIGN KEY (orchestration_id) REFERENCES orchestrations(id) ON DELETE CASCADE
);

-- SKIPPED: Table 'orchestration_events' doesn't exist - -- SKIPPED: Table 'orchestration_events' doesn't exist - CREATE INDEX IF NOT EXISTS idx_orchestration_events_orchestration_id ON orchestration_events(orchestration_id);
-- SKIPPED: Table 'orchestration_events' doesn't exist - -- SKIPPED: Table 'orchestration_events' doesn't exist - CREATE INDEX IF NOT EXISTS idx_orchestration_events_timestamp ON orchestration_events(timestamp);
