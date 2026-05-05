-- Migration 074: Fix workspace template cascading deletion
-- When a workspace is deleted, templates using it as source should be deleted too
-- This ensures no orphaned templates remain

-- SQLite doesn't support ALTER COLUMN for foreign keys, so we need to recreate the table

-- Step 0: Disable foreign key checks temporarily
PRAGMA foreign_keys = OFF;

-- Step 1: Create new table with correct constraint
CREATE TABLE IF NOT EXISTS workspace_templates_new (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    phases TEXT NOT NULL,
    parameters TEXT,
    parameter_schema TEXT,
    is_public INTEGER DEFAULT 0,
    times_used INTEGER DEFAULT 0,
    avg_execution_time_ms INTEGER,
    last_used_at TEXT,
    tags TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    source_workspace_id TEXT REFERENCES notebooks(id) ON DELETE CASCADE,  -- Changed from SET NULL to CASCADE

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Step 2: Copy data from old table
INSERT INTO workspace_templates_new
SELECT * FROM workspace_templates;

-- Step 3: Drop old table
DROP TABLE workspace_templates;

-- Step 4: Rename new table
ALTER TABLE workspace_templates_new RENAME TO workspace_templates;

-- Step 5: Recreate indexes
CREATE INDEX idx_workspace_templates_user_id ON workspace_templates(user_id);
CREATE INDEX idx_workspace_templates_category ON workspace_templates(category);
CREATE INDEX idx_workspace_templates_source_workspace ON workspace_templates(source_workspace_id);
CREATE INDEX idx_workspace_templates_public ON workspace_templates(is_public);
CREATE INDEX idx_workspace_templates_times_used ON workspace_templates(times_used DESC);

-- Step 6: Re-enable foreign key checks
PRAGMA foreign_keys = ON;
