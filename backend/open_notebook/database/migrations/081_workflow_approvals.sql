-- Migration 081: Workflow Approvals
-- Add workflow_approvals table for human-in-the-loop approvals

CREATE TABLE workflow_approvals (
    id TEXT PRIMARY KEY,
    workflow_id TEXT,
    execution_id TEXT,
    node_id TEXT NOT NULL,
    approval_prompt TEXT NOT NULL,
    approval_options TEXT NOT NULL,
    required_approvers TEXT,
    input_data TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    response TEXT,
    comment TEXT,
    approved_by TEXT,
    timeout_seconds INTEGER,
    timeout_action TEXT,
    timeout_at TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    responded_at TEXT
);

CREATE INDEX idx_workflow_approvals_status ON workflow_approvals(status);
CREATE INDEX idx_workflow_approvals_execution ON workflow_approvals(execution_id);
CREATE INDEX idx_workflow_approvals_timeout ON workflow_approvals(timeout_at);
