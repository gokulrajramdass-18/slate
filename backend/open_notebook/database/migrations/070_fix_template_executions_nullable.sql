-- Migration: Make target_workspace_id nullable in template_executions
-- This allows workspace deletion to SET NULL instead of failing

-- Recreate template_executions with nullable target_workspace_id
CREATE TABLE template_executions_new (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    template_id TEXT NOT NULL,
    target_workspace_id TEXT,  -- Changed from NOT NULL to nullable
    folder_id TEXT,


    parameters TEXT,


    result_note_id TEXT,
    status TEXT NOT NULL,
    error TEXT,


    current_phase TEXT,
    progress REAL DEFAULT 0.0,


    started_at TEXT NOT NULL,
    completed_at TEXT,
    duration_ms INTEGER,


    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (template_id) REFERENCES workspace_templates(id) ON DELETE CASCADE,
    FOREIGN KEY (target_workspace_id) REFERENCES notebooks(id) ON DELETE SET NULL,
    FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE SET NULL,
    FOREIGN KEY (result_note_id) REFERENCES notes(id) ON DELETE SET NULL
);

-- Copy data
INSERT INTO template_executions_new SELECT * FROM template_executions;

-- Drop old table
DROP TABLE template_executions;

-- Rename new table
ALTER TABLE template_executions_new RENAME TO template_executions;

-- Recreate indexes
CREATE INDEX idx_template_executions_template ON template_executions(template_id);
CREATE INDEX idx_template_executions_workspace ON template_executions(target_workspace_id);
CREATE INDEX idx_template_executions_folder ON template_executions(folder_id);
CREATE INDEX idx_template_executions_status ON template_executions(status);
CREATE INDEX idx_template_executions_created ON template_executions(created_at DESC);
