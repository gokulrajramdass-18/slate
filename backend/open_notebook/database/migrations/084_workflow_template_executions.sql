-- Migration 084: Workflow Template Executions
-- Track template instantiations and executions

CREATE TABLE workflow_template_executions (
    id TEXT PRIMARY KEY,
    template_id TEXT NOT NULL REFERENCES workflow_templates(id) ON DELETE CASCADE,
    workflow_id TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    execution_id TEXT REFERENCES workflow_executions(id) ON DELETE CASCADE,
    parameters TEXT,
    status TEXT NOT NULL,
    user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE INDEX idx_wf_template_executions_template ON workflow_template_executions(template_id);
CREATE INDEX idx_wf_template_executions_user ON workflow_template_executions(user_id);
