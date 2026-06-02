-- Migration: MCP server oauth_mode toggle (user vs system)
-- Version: 118
-- Description:
--   Adds `oauth_mode` to mcp_servers so admins can choose between:
--     - 'user'   (default): each user authenticates separately. Tokens are
--                stored per (server_id, user_id) — current behavior from
--                migration 117.
--     - 'system': one admin completes OAuth once; the resulting token is
--                shared across all users. Stored under the sentinel
--                user_id = '__system__'.
--
--   Also: rebuilds mcp_oauth_tokens to drop the FK on user_id so the
--   '__system__' sentinel can be inserted (the FK on server_id stays).
--   `users.id` is a 36-char UUID, so '__system__' cannot collide.
--
--   Mode is locked at creation; updates to oauth_mode are rejected by the
--   API layer. Existing per-user rows are preserved.

-- 1. Add oauth_mode. Defaults to 'user' so all rows from migration 117
--    keep their current behavior with no operator action required.
ALTER TABLE mcp_servers
    ADD COLUMN oauth_mode TEXT NOT NULL DEFAULT 'user';

-- 2. Rebuild mcp_oauth_tokens without the user_id → users(id) FK.
--    SQLite cannot drop a single FK in place, so we copy → swap.
CREATE TABLE mcp_oauth_tokens__new (
    server_id      TEXT NOT NULL,
    user_id        TEXT NOT NULL,            -- '__system__' for system-mode, else users.id
    access_token   TEXT NOT NULL,
    refresh_token  TEXT,
    token_type     TEXT DEFAULT 'Bearer',
    expires_at     TIMESTAMP NOT NULL,
    scope          TEXT,
    user_info      TEXT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (server_id, user_id),
    FOREIGN KEY (server_id) REFERENCES mcp_servers(id) ON DELETE CASCADE
);

INSERT INTO mcp_oauth_tokens__new (
    server_id, user_id, access_token, refresh_token, token_type,
    expires_at, scope, user_info, created_at, updated_at
)
SELECT
    server_id, user_id, access_token, refresh_token, token_type,
    expires_at, scope, user_info, created_at, updated_at
FROM mcp_oauth_tokens;

DROP TABLE mcp_oauth_tokens;
ALTER TABLE mcp_oauth_tokens__new RENAME TO mcp_oauth_tokens;

CREATE INDEX IF NOT EXISTS idx_mcp_oauth_tokens_user
    ON mcp_oauth_tokens(user_id);

CREATE INDEX IF NOT EXISTS idx_mcp_oauth_tokens_expires
    ON mcp_oauth_tokens(expires_at);
