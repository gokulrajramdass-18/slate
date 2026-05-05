-- Migration 062: Add Authorization Code Flow Support
-- Add authorization codes table and update oauth_applications

-- Authorization codes table for Authorization Code flow
CREATE TABLE oauth_authorization_codes (
    id TEXT PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    app_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    redirect_uri TEXT NOT NULL,
    scopes TEXT NOT NULL,  -- JSON array
    code_challenge TEXT,  -- PKCE code challenge
    code_challenge_method TEXT,  -- S256 or plain
    expires_at TEXT NOT NULL,
    used INTEGER DEFAULT 0,  -- Boolean: 0 = not used, 1 = used
    created TEXT NOT NULL,
    FOREIGN KEY (app_id) REFERENCES oauth_applications(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_oauth_codes_code ON oauth_authorization_codes(code);
CREATE INDEX idx_oauth_codes_app ON oauth_authorization_codes(app_id);
CREATE INDEX idx_oauth_codes_user ON oauth_authorization_codes(user_id);
CREATE INDEX idx_oauth_codes_expires ON oauth_authorization_codes(expires_at);

-- Add redirect_uris column to oauth_applications (already exists as nullable, make it useful)
-- Update grant_types to include authorization_code
-- Note: redirect_uris is already in schema from migration 061, we just need to use it

-- Add refresh tokens table
CREATE TABLE oauth_refresh_tokens (
    id TEXT PRIMARY KEY,
    token TEXT UNIQUE NOT NULL,
    app_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    scopes TEXT NOT NULL,  -- JSON array
    expires_at TEXT NOT NULL,
    revoked INTEGER DEFAULT 0,  -- Boolean
    created TEXT NOT NULL,
    FOREIGN KEY (app_id) REFERENCES oauth_applications(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_oauth_refresh_token ON oauth_refresh_tokens(token);
CREATE INDEX idx_oauth_refresh_app ON oauth_refresh_tokens(app_id);
CREATE INDEX idx_oauth_refresh_user ON oauth_refresh_tokens(user_id);
