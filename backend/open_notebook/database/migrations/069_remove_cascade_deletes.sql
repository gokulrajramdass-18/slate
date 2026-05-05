-- Migration: Remove CASCADE DELETE constraints that cause workspace deletion chain reactions
-- This prevents workspaces from being deleted during template execution

-- Step 1: Recreate folders table without CASCADE DELETE on notebook_id
-- (Keep CASCADE on parent_id for folder hierarchy)
CREATE TABLE folders_new (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    parent_id TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    notebook_id TEXT REFERENCES notebooks(id) ON DELETE SET NULL,
    folder_type TEXT DEFAULT 'user',
    metadata TEXT,
    FOREIGN KEY (parent_id) REFERENCES folders(id) ON DELETE CASCADE
);

-- Copy data
INSERT INTO folders_new SELECT * FROM folders;

-- Drop old table
DROP TABLE folders;

-- Rename new table
ALTER TABLE folders_new RENAME TO folders;

-- Recreate indexes
CREATE INDEX idx_folders_parent ON folders(parent_id);
CREATE INDEX idx_folders_parent_id ON folders(parent_id);
CREATE INDEX idx_folders_notebook_id ON folders(notebook_id);
CREATE INDEX idx_folders_type ON folders(folder_type);

-- Step 2: Recreate template_executions table with SET NULL on workspace and folder deletion
CREATE TABLE template_executions_new (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    template_id TEXT NOT NULL,
    target_workspace_id TEXT NOT NULL,
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

-- Step 3: Recreate notes table with SET NULL on notebook deletion (not CASCADE)
CREATE TABLE notes_new (
    id TEXT PRIMARY KEY,
    title TEXT,
    summary TEXT,
    content TEXT,
    embedding TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    content_html TEXT,
    folder_id TEXT,
    metadata TEXT,
    notebook_id TEXT REFERENCES notebooks(id) ON DELETE SET NULL
);

-- Copy data
INSERT INTO notes_new SELECT * FROM notes;

-- Drop old table
DROP TABLE notes;

-- Rename new table
ALTER TABLE notes_new RENAME TO notes;

-- Recreate indexes
CREATE INDEX idx_notes_notebook_id ON notes(notebook_id);
