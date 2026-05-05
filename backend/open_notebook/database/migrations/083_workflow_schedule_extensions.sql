-- Migration 083: Workflow Schedule Extensions
-- Add webhook and template support to workflow schedules

ALTER TABLE workflow_schedules ADD COLUMN webhook_secret TEXT;
ALTER TABLE workflow_schedules ADD COLUMN template_id TEXT REFERENCES workflow_templates(id);
ALTER TABLE workflow_schedules ADD COLUMN template_parameters TEXT;
