-- Migration 085: Fix workflow_templates foreign key constraint
-- Change source_workflow_id to SET NULL on delete instead of preventing deletion

-- SQLite doesn't support ALTER TABLE to modify foreign keys
-- So we need to recreate the table

-- Step 1: Create new table with correct constraint
CREATE TABLE workflow_templates_new (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    source_workflow_id TEXT REFERENCES workflows(id) ON DELETE SET NULL,
    graph_json TEXT NOT NULL,
    parameters TEXT,
    version INTEGER DEFAULT 1,
    is_public INTEGER DEFAULT 0,
    tags TEXT,
    usage_count INTEGER DEFAULT 0,
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);

-- Step 2: Copy data from old table
INSERT INTO workflow_templates_new
SELECT * FROM workflow_templates;

-- Step 3: Drop old table
DROP TABLE workflow_templates;

-- Step 4: Rename new table
ALTER TABLE workflow_templates_new RENAME TO workflow_templates;

-- Step 5: Recreate indexes
CREATE INDEX idx_workflow_templates_user ON workflow_templates(user_id);
CREATE INDEX idx_workflow_templates_public ON workflow_templates(is_public);
CREATE INDEX idx_workflow_templates_category ON workflow_templates(category);
CREATE INDEX idx_workflow_templates_usage ON workflow_templates(usage_count DESC);
CREATE INDEX idx_workflow_templates_source ON workflow_templates(source_workflow_id);
