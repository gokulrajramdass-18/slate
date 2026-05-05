-- Migration 080: Workflow Templates
-- Add workflow_templates table for reusable workflow patterns

CREATE TABLE workflow_templates (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    source_workflow_id TEXT REFERENCES workflows(id),
    graph_json TEXT NOT NULL,
    parameters TEXT,
    version INTEGER DEFAULT 1,
    is_public INTEGER DEFAULT 0,
    tags TEXT,
    usage_count INTEGER DEFAULT 0,
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);

CREATE INDEX idx_workflow_templates_user ON workflow_templates(user_id);
CREATE INDEX idx_workflow_templates_public ON workflow_templates(is_public);
CREATE INDEX idx_workflow_templates_category ON workflow_templates(category);
CREATE INDEX idx_workflow_templates_usage ON workflow_templates(usage_count DESC);
