-- Migration: 021 - Add execution_id to agent_messages
-- Description: Add execution_id column to agent_messages for tracking message-execution relationship
-- Date: 2026-03-27

-- Add execution_id column to agent_messages table
ALTER TABLE agent_messages ADD COLUMN execution_id TEXT;

-- Create index for efficient execution-based message queries
CREATE INDEX IF NOT EXISTS idx_agent_messages_execution ON agent_messages(execution_id);
