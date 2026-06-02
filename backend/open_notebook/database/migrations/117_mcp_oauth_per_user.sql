-- Migration: Per-user MCP OAuth tokens
-- Version: 117
-- Description:
--   Each user authenticates MCP OAuth servers with their own identity.
--   Tokens are now scoped per (server_id, user_id) instead of per server.
--   The OAuth client registration (mcp_oauth_clients) stays shared per server.
--
--   Existing tokens are wiped: every user must re-authenticate. OAuth-typed
--   servers are reset to status='needs_auth' and their auth_config_encrypted
--   is cleared so it cannot shadow per-user tokens.

-- Drop existing per-server token table; everyone re-authenticates.
DROP TABLE IF EXISTS mcp_oauth_tokens;

CREATE TABLE mcp_oauth_tokens (
    server_id      TEXT NOT NULL,
    user_id        TEXT NOT NULL,
    access_token   TEXT NOT NULL,           -- Encrypted at rest
    refresh_token  TEXT,                    -- Encrypted at rest
    token_type     TEXT DEFAULT 'Bearer',
    expires_at     TIMESTAMP NOT NULL,
    scope          TEXT,                    -- Space-separated scopes
    user_info      TEXT,                    -- JSON of provider user info
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (server_id, user_id),
    FOREIGN KEY (server_id) REFERENCES mcp_servers(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id)   REFERENCES users(id)       ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mcp_oauth_tokens_user
    ON mcp_oauth_tokens(user_id);

CREATE INDEX IF NOT EXISTS idx_mcp_oauth_tokens_expires
    ON mcp_oauth_tokens(expires_at);

-- For OAuth servers, blank out the legacy server-level token so it cannot
-- shadow a user-scoped token if the loader ever falls back to it.
UPDATE mcp_servers
SET auth_config_encrypted = NULL
WHERE auth_type = 'oauth';

-- Reset OAuth servers so each user is prompted to authenticate themselves.
UPDATE mcp_servers
SET status = 'needs_auth',
    last_test_message = 'Per-user OAuth migration: please authenticate.'
WHERE auth_type = 'oauth';
