-- Migration 086: Extend Workflow Template Executions for Scheduling
-- Add fields for tracking trigger type, schedule, and timing

ALTER TABLE workflow_template_executions ADD COLUMN trigger_type TEXT DEFAULT 'immediate';
ALTER TABLE workflow_template_executions ADD COLUMN schedule_type TEXT;
ALTER TABLE workflow_template_executions ADD COLUMN cron_expression TEXT;
ALTER TABLE workflow_template_executions ADD COLUMN started_at TEXT;
ALTER TABLE workflow_template_executions ADD COLUMN duration_ms INTEGER;
ALTER TABLE workflow_template_executions ADD COLUMN template_name TEXT;
ALTER TABLE workflow_template_executions ADD COLUMN error TEXT;

CREATE INDEX IF NOT EXISTS idx_workflow_template_exec_trigger ON workflow_template_executions(trigger_type);
CREATE INDEX IF NOT EXISTS idx_workflow_template_exec_started ON workflow_template_executions(started_at);


