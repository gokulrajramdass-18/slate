-- Migration: 047_add_discovered_resources_to_guided_sessions.sql
-- Description: Add discovered_resources column to guided_workspace_sessions table
-- Date: 2026-04-04

ALTER TABLE guided_workspace_sessions ADD COLUMN discovered_resources TEXT;
