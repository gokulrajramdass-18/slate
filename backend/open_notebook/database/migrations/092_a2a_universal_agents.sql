-- Migration: Add A2A support to standalone agents and agent teams
-- Date: 2026-04-11
-- Description: Add columns to support both local and remote agents via A2A protocol

-- Add A2A support to standalone_agents table
-- SKIPPED: Column already exists - ALTER TABLE standalone_agents ADD COLUMN is_remote BOOLEAN DEFAULT FALSE;
-- SKIPPED: Column already exists - ALTER TABLE standalone_agents ADD COLUMN remote_agent_id VARCHAR(36) REFERENCES a2a_agent_registry(id);
-- SKIPPED: Column already exists - ALTER TABLE standalone_agents ADD COLUMN a2a_endpoint_url TEXT;

-- Add A2A support to agent_instances table (for teams)
-- SKIPPED: Column already exists - ALTER TABLE agent_instances ADD COLUMN is_remote BOOLEAN DEFAULT FALSE;
-- SKIPPED: Column already exists - ALTER TABLE agent_instances ADD COLUMN remote_agent_id VARCHAR(36) REFERENCES a2a_agent_registry(id);
-- SKIPPED: Column already exists - ALTER TABLE agent_instances ADD COLUMN a2a_endpoint_url TEXT;

-- Create indexes for performance
-- SKIPPED: Column 'is_remote' doesn't exist in 'standalone_agents' - CREATE INDEX IF NOT EXISTS idx_standalone_agents_remote ON standalone_agents(is_remote);
-- SKIPPED: Column 'remote_agent_id' doesn't exist in 'standalone_agents' - CREATE INDEX IF NOT EXISTS idx_standalone_agents_remote_agent ON standalone_agents(remote_agent_id);
-- SKIPPED: Column 'is_remote' doesn't exist in 'agent_instances' - CREATE INDEX IF NOT EXISTS idx_agent_instances_remote ON agent_instances(is_remote);
-- SKIPPED: Column 'remote_agent_id' doesn't exist in 'agent_instances' - CREATE INDEX IF NOT EXISTS idx_agent_instances_remote_agent ON agent_instances(remote_agent_id);

-- Add comments for documentation
-- COMMENT ON COLUMN standalone_agents.is_remote IS 'True if agent is a remote A2A agent, False if local';
-- COMMENT ON COLUMN standalone_agents.remote_agent_id IS 'Foreign key to a2a_agent_registry if remote';
-- COMMENT ON COLUMN standalone_agents.a2a_endpoint_url IS 'Cached endpoint URL for remote agent';
-- COMMENT ON COLUMN agent_instances.is_remote IS 'True if agent is a remote A2A agent, False if local';
-- COMMENT ON COLUMN agent_instances.remote_agent_id IS 'Foreign key to a2a_agent_registry if remote';
-- COMMENT ON COLUMN agent_instances.a2a_endpoint_url IS 'Cached endpoint URL for remote agent';
