-- Migration: 097_daily_brief_settings.sql
-- Description: Add settings for daily brief feature
-- Date: 2026-05-08

-- Add daily brief settings
INSERT INTO settings (key, value, type, description, created, updated) VALUES
  ('daily_brief_enabled', 'true', 'boolean', 'Enable daily brief feature', datetime('now'), datetime('now')),
  ('daily_brief_ai_enabled', 'true', 'boolean', 'Enable AI-powered summaries in daily brief', datetime('now'), datetime('now')),
  ('daily_brief_sources', '["executions","approvals","schedules","notifications","orchestrations"]', 'json', 'Enabled data sources for daily brief generation', datetime('now'), datetime('now')),
  ('daily_brief_max_items', '5', 'integer', 'Maximum items to show per section in daily brief', datetime('now'), datetime('now'));
