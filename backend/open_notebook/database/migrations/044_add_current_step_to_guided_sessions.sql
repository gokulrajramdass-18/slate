-- Migration: 044_add_current_step_to_guided_sessions.sql
-- Description: Add current_step column to guided_workspace_sessions table
-- Date: 2026-04-04

ALTER TABLE guided_workspace_sessions ADD COLUMN current_step TEXT;

CREATE INDEX IF NOT EXISTS idx_guided_sessions_current_step ON guided_workspace_sessions(current_step);
