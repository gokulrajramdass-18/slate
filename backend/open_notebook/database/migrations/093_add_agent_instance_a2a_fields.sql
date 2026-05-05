-- Add A2A protocol fields to agent_instances table

-- Add is_remote column (default False for existing agents)
-- SKIPPED: Column already exists - ALTER TABLE agent_instances ADD COLUMN is_remote INTEGER DEFAULT 0 NOT NULL;

-- Add remote_agent_id column (NULL for local agents)
-- SKIPPED: Column already exists - ALTER TABLE agent_instances ADD COLUMN remote_agent_id TEXT;

-- Add a2a_endpoint_url column (NULL for local agents)
-- SKIPPED: Column already exists - ALTER TABLE agent_instances ADD COLUMN a2a_endpoint_url TEXT;

-- Create index for remote agents
-- SKIPPED: Column 'is_remote' doesn't exist in 'agent_instances' - CREATE INDEX IF NOT EXISTS idx_agent_instances_remote ON agent_instances(is_remote) WHERE is_remote = 1;
