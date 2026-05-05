-- Migration 033: Add Skills Support to Standalone Agents
-- Description: Add skill_ids column to standalone_agents table

-- Add skills support to standalone agents
ALTER TABLE standalone_agents ADD COLUMN skill_ids TEXT DEFAULT '[]';

-- Create index for skills queries
CREATE INDEX IF NOT EXISTS idx_standalone_agents_skills ON standalone_agents(skill_ids);
