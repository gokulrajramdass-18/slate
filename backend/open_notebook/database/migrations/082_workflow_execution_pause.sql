-- Migration 082: Workflow Execution Pause Support
-- Add fields to support pausing and resuming workflow executions

ALTER TABLE workflow_executions ADD COLUMN current_node_id TEXT;
ALTER TABLE workflow_executions ADD COLUMN paused_at TEXT;
ALTER TABLE workflow_executions ADD COLUMN paused_reason TEXT;
ALTER TABLE workflow_executions ADD COLUMN resume_data TEXT;
