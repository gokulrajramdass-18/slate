-- Migration: 104_orchestration_lineage.sql
-- Description: Add template and workspace instance tracking to orchestration tables
-- Date: 2026-04-22
-- Note: Uses INSERT OR IGNORE to make migration idempotent (columns may already exist)

-- Indexes for foreign keys and queries (idempotent with IF NOT EXISTS)
CREATE INDEX IF NOT EXISTS idx_orchestration_schedules_template_id ON orchestration_schedules(template_id);
CREATE INDEX IF NOT EXISTS idx_orchestrations_template_id ON orchestrations(template_id);
CREATE INDEX IF NOT EXISTS idx_orchestrations_workspace_instance_id ON orchestrations(workspace_instance_id);
