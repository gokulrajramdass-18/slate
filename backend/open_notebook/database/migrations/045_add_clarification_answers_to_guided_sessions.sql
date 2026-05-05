-- Migration: 045_add_clarification_answers_to_guided_sessions.sql
-- Description: Add clarification_answers column to guided_workspace_sessions table
-- Date: 2026-04-04

ALTER TABLE guided_workspace_sessions ADD COLUMN clarification_answers TEXT;
