-- Migration 066: Template Execution Support with Folder Organization
-- Date: 2026-04-23

-- Add source_workspace_id to workspace_templates
ALTER TABLE workspace_templates
ADD COLUMN source_workspace_id TEXT REFERENCES notebooks(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_workspace_templates_source_workspace
ON workspace_templates(source_workspace_id);

-- Enhance folders table for template execution organization
ALTER TABLE folders ADD COLUMN notebook_id TEXT REFERENCES notebooks(id) ON DELETE CASCADE;
ALTER TABLE folders ADD COLUMN folder_type TEXT DEFAULT 'user';  -- 'user', 'system', 'template_executions'
ALTER TABLE folders ADD COLUMN metadata TEXT;  -- JSON: {template_id, execution_count, last_execution}

CREATE INDEX IF NOT EXISTS idx_folders_notebook_id ON folders(notebook_id);
CREATE INDEX IF NOT EXISTS idx_folders_type ON folders(folder_type);

-- Create template_executions table
CREATE TABLE IF NOT EXISTS template_executions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    template_id TEXT NOT NULL,
    target_workspace_id TEXT NOT NULL,
    folder_id TEXT NOT NULL,

    -- Input parameters
    parameters TEXT,  -- JSON: runtime parameter values

    -- Results
    result_note_id TEXT,
    status TEXT NOT NULL,  -- 'pending', 'running', 'completed', 'failed'
    error TEXT,

    -- Execution tracking
    current_phase TEXT,
    progress REAL DEFAULT 0.0,

    -- Timing
    started_at TEXT NOT NULL,
    completed_at TEXT,
    duration_ms INTEGER,

    -- Metadata
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (template_id) REFERENCES workspace_templates(id) ON DELETE CASCADE,
    FOREIGN KEY (target_workspace_id) REFERENCES notebooks(id) ON DELETE CASCADE,
    FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE CASCADE,
    FOREIGN KEY (result_note_id) REFERENCES notes(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_template_executions_template ON template_executions(template_id);
CREATE INDEX IF NOT EXISTS idx_template_executions_workspace ON template_executions(target_workspace_id);
CREATE INDEX IF NOT EXISTS idx_template_executions_folder ON template_executions(folder_id);
CREATE INDEX IF NOT EXISTS idx_template_executions_status ON template_executions(status);
CREATE INDEX IF NOT EXISTS idx_template_executions_created ON template_executions(created_at DESC);

-- Add folder_id to notes table for organization
ALTER TABLE notes ADD COLUMN folder_id TEXT REFERENCES folders(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_notes_folder_id ON notes(folder_id);
