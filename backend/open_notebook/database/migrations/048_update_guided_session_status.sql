-- Migration: 048_update_guided_session_status.sql
-- Description: Update status constraint to allow 'draft', 'expired'
-- Date: 2026-04-04

-- SQLite doesn't allow modifying CHECK constraints
-- We need to recreate the table to update the constraint

-- Step 1: Create new table with updated constraint
CREATE TABLE guided_workspace_sessions_new (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    goal TEXT NOT NULL,
    analysis TEXT,
    clarifications TEXT,
    selected_resources TEXT,
    generated_plan TEXT,
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft', 'active', 'completed', 'abandoned', 'expired')),
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    current_step TEXT,
    clarification_answers TEXT,
    discovered_resources TEXT,
    workspace_id TEXT,
    plan TEXT
);

-- Step 2: Copy data, converting 'active' to 'draft'
-- Note: Only copy columns that exist in the original table
-- workspace_id and plan are new columns, will be NULL
INSERT INTO guided_workspace_sessions_new (
    id, user_id, goal, analysis, clarifications, selected_resources, generated_plan,
    status, created, updated, expires_at, current_step, clarification_answers, discovered_resources
)
SELECT
    id, user_id, goal, analysis, clarifications, selected_resources, generated_plan,
    CASE WHEN status = 'active' THEN 'draft' ELSE status END as status,
    created, updated, expires_at, current_step, clarification_answers, discovered_resources
FROM guided_workspace_sessions;

-- Step 3: Drop old table
DROP TABLE guided_workspace_sessions;

-- Step 4: Rename new table
ALTER TABLE guided_workspace_sessions_new RENAME TO guided_workspace_sessions;

-- Step 5: Recreate indexes
CREATE INDEX idx_guided_sessions_user_id ON guided_workspace_sessions(user_id);
CREATE INDEX idx_guided_sessions_status ON guided_workspace_sessions(status);
CREATE INDEX idx_guided_sessions_expires_at ON guided_workspace_sessions(expires_at);
CREATE INDEX idx_guided_sessions_current_step ON guided_workspace_sessions(current_step);


