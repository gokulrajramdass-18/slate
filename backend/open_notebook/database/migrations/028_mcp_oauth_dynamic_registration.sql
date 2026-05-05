-- Migration: Add MCP OAuth tables for dynamic client registration
-- Version: 028
-- Description: Tables for storing dynamically registered OAuth clients and tokens

-- Table for storing dynamically registered OAuth client credentials
CREATE TABLE IF NOT EXISTS mcp_oauth_clients (
    server_id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    client_secret TEXT,                    -- Optional, some providers don't issue secrets
    registration_data TEXT,                -- JSON of full registration response
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table for storing OAuth tokens
CREATE TABLE IF NOT EXISTS mcp_oauth_tokens (
    server_id TEXT PRIMARY KEY,
    access_token TEXT NOT NULL,           -- Should be encrypted in production
    refresh_token TEXT,                   -- Should be encrypted in production
    token_type TEXT DEFAULT 'Bearer',
    expires_at TIMESTAMP NOT NULL,
    scope TEXT,                           -- Space-separated scopes
    user_info TEXT,                       -- JSON of user information
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (server_id) REFERENCES mcp_servers(id) ON DELETE CASCADE
);

-- Index for token expiration checks
CREATE INDEX IF NOT EXISTS idx_oauth_tokens_expires
ON mcp_oauth_tokens(expires_at);

-- Index for client lookups
CREATE INDEX IF NOT EXISTS idx_oauth_clients_server
ON mcp_oauth_clients(server_id);
