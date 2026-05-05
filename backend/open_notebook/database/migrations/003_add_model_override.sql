-- Migration: Add model_override to chat_sessions
-- Date: 2026-03-21
-- Description: Add optional model override field to chat sessions

-- Add model_override column to chat_sessions
ALTER TABLE chat_sessions ADD COLUMN model_override TEXT;

-- Add index for performance
CREATE INDEX IF NOT EXISTS idx_chat_sessions_model ON chat_sessions(model_override);
