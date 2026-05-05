-- Migration 029: Add OAuth auth types to MCP servers
-- Adds 'auto' and 'oauth' to the auth_type CHECK constraint

-- SQLite doesn't support ALTER TABLE ... ALTER COLUMN
-- So we need to recreate the table with the new constraint

-- Step 1: Create temporary table with new constraint
CREATE TABLE mcp_servers_new (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    protocol TEXT NOT NULL,

    -- stdio configuration
    command TEXT,
    args TEXT,
    env_vars TEXT,

    -- HTTP configuration
    url TEXT,
    headers TEXT,
    auth_type TEXT,          -- 'none', 'bearer', 'api_key', 'auto', 'oauth'
    auth_config_encrypted TEXT,

    -- Connection status
    status TEXT DEFAULT 'untested',
    last_test_at TEXT,
    last_test_message TEXT,

    -- Capabilities cache
    capabilities TEXT,

    -- Timestamps
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    -- Constraints
    CHECK (protocol IN ('stdio', 'http')),
    CHECK (status IN ('untested', 'connected', 'error', 'disconnected')),
    CHECK (auth_type IS NULL OR auth_type IN ('none', 'bearer', 'api_key', 'auto', 'oauth'))
);

-- Step 2: Copy data from old table
INSERT INTO mcp_servers_new
SELECT * FROM mcp_servers;

-- Step 3: Drop old table
DROP TABLE mcp_servers;

-- Step 4: Rename new table
ALTER TABLE mcp_servers_new RENAME TO mcp_servers;

-- Step 5: Recreate indexes
CREATE INDEX idx_mcp_servers_status ON mcp_servers(status);
CREATE INDEX idx_mcp_servers_protocol ON mcp_servers(protocol);
CREATE INDEX idx_mcp_servers_name ON mcp_servers(name);
