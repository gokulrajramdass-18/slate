-- Migration 017: MCP (Model Context Protocol) Server Integration
-- Creates tables for managing MCP server connections and discovered tools

-- MCP server connections table
CREATE TABLE IF NOT EXISTS mcp_servers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    protocol TEXT NOT NULL,  -- 'stdio' or 'http'

    -- stdio configuration (subprocess-based MCP servers)
    command TEXT,            -- e.g., 'npx', 'python', '/path/to/server'
    args TEXT,               -- JSON array of command arguments
    env_vars TEXT,           -- JSON object of environment variables

    -- HTTP configuration (HTTP/SSE-based MCP servers)
    url TEXT,                -- HTTP endpoint base URL
    headers TEXT,            -- JSON object of HTTP headers
    auth_type TEXT,          -- 'none', 'bearer', 'api_key'
    auth_config_encrypted TEXT,  -- Encrypted auth credentials (AES-256-GCM)

    -- Connection status and testing
    status TEXT DEFAULT 'untested',  -- 'untested', 'connected', 'error', 'disconnected'
    last_test_at TEXT,
    last_test_message TEXT,

    -- Capabilities cache (from discovery)
    capabilities TEXT,       -- JSON: {tools: [...], resources: [...], prompts: [...]}

    -- Timestamps
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    -- Constraints
    CHECK (protocol IN ('stdio', 'http')),
    CHECK (status IN ('untested', 'connected', 'error', 'disconnected')),
    CHECK (auth_type IS NULL OR auth_type IN ('none', 'bearer', 'api_key'))
);

-- Indexes for quick lookups
CREATE INDEX IF NOT EXISTS idx_mcp_servers_status ON mcp_servers(status);
CREATE INDEX IF NOT EXISTS idx_mcp_servers_protocol ON mcp_servers(protocol);
CREATE INDEX IF NOT EXISTS idx_mcp_servers_name ON mcp_servers(name);

-- MCP tool discovery cache
-- Stores tools discovered from MCP servers for UI display and permission management
CREATE TABLE IF NOT EXISTS mcp_tools (
    id TEXT PRIMARY KEY,
    server_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    description TEXT,
    input_schema TEXT,       -- JSON schema for tool parameters
    discovered_at TEXT NOT NULL,

    FOREIGN KEY (server_id) REFERENCES mcp_servers(id) ON DELETE CASCADE,
    UNIQUE(server_id, tool_name)
);

CREATE INDEX IF NOT EXISTS idx_mcp_tools_server ON mcp_tools(server_id);
CREATE INDEX IF NOT EXISTS idx_mcp_tools_name ON mcp_tools(tool_name);

-- Comments for documentation
--
-- Table: mcp_servers
-- Purpose: Store MCP server connection configurations and status
--
-- Protocol types:
--   - stdio: Subprocess-based communication via JSON-RPC over stdin/stdout
--   - http: HTTP REST API with optional SSE streaming
--
-- Authentication types (for HTTP):
--   - none: No authentication
--   - bearer: Bearer token in Authorization header
--   - api_key: Custom API key header
--
-- Status values:
--   - untested: Server created but not yet tested
--   - connected: Successfully connected and capabilities discovered
--   - error: Connection failed (see last_test_message for details)
--   - disconnected: Previously connected but currently offline
--
-- Table: mcp_tools
-- Purpose: Cache discovered tools from MCP servers
-- Note: Tools are auto-discovered during server testing and refreshed on each test
