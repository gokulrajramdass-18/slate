-- Migration 061: OAuth 2.0 Application Registration System
-- Creates tables for OAuth app management, scopes, token revocation, and audit logging

-- Table 1: OAuth Applications
CREATE TABLE oauth_applications (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    owner_user_id TEXT NOT NULL,
    client_id TEXT UNIQUE NOT NULL,
    client_secret_encrypted TEXT NOT NULL,
    scopes TEXT NOT NULL,  -- JSON array of scope strings
    redirect_uris TEXT,  -- JSON array (for future Authorization Code flow)
    grant_types TEXT DEFAULT 'client_credentials',
    status TEXT DEFAULT 'active',  -- active, suspended, revoked
    rate_limit_per_hour INTEGER DEFAULT 1000,
    rate_limit_per_day INTEGER DEFAULT 10000,
    token_expiry_seconds INTEGER DEFAULT 3600,
    last_used_at TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_oauth_apps_owner ON oauth_applications(owner_user_id);
CREATE INDEX idx_oauth_apps_client_id ON oauth_applications(client_id);
CREATE INDEX idx_oauth_apps_status ON oauth_applications(status);

-- Table 2: OAuth Scopes (Reference table with seed data)
CREATE TABLE oauth_scopes (
    id TEXT PRIMARY KEY,
    scope TEXT UNIQUE NOT NULL,
    resource_type TEXT NOT NULL,
    action TEXT NOT NULL,
    description TEXT,
    is_system_only INTEGER DEFAULT 0,
    created TEXT NOT NULL
);

-- Seed OAuth scopes
INSERT INTO oauth_scopes (id, scope, resource_type, action, description, is_system_only, created) VALUES
    ('scope-1', 'read:agents', 'agent', 'read', 'View agent information', 0, datetime('now')),
    ('scope-2', 'write:agents', 'agent', 'write', 'Create and modify agents', 0, datetime('now')),
    ('scope-3', 'delete:agents', 'agent', 'delete', 'Delete agents', 0, datetime('now')),
    ('scope-4', 'read:teams', 'team', 'read', 'View team information', 0, datetime('now')),
    ('scope-5', 'write:teams', 'team', 'write', 'Create and modify teams', 0, datetime('now')),
    ('scope-6', 'delete:teams', 'team', 'delete', 'Delete teams', 0, datetime('now')),
    ('scope-7', 'execute:teams', 'team', 'execute', 'Execute team workflows', 0, datetime('now')),
    ('scope-8', 'read:tasks', 'task', 'read', 'View task information', 0, datetime('now')),
    ('scope-9', 'read:executions', 'execution', 'read', 'View execution details', 0, datetime('now')),
    ('scope-10', 'write:executions', 'execution', 'write', 'Manage executions (cancel, delete)', 0, datetime('now')),
    ('scope-11', 'admin:all', 'all', 'all', 'Full administrative access', 1, datetime('now'));

-- Table 3: OAuth Revoked Tokens (Token blacklist)
CREATE TABLE oauth_revoked_tokens (
    jti TEXT PRIMARY KEY,  -- JWT ID claim
    revoked_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    reason TEXT
);

CREATE INDEX idx_oauth_revoked_jti ON oauth_revoked_tokens(jti);
CREATE INDEX idx_oauth_revoked_expires ON oauth_revoked_tokens(expires_at);

-- Table 4: OAuth Audit Log (API call tracking)
CREATE TABLE oauth_audit_log (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    app_id TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    status_code INTEGER,
    scopes_used TEXT,  -- JSON array
    ip_address TEXT,
    user_agent TEXT,
    response_time_ms INTEGER,
    created TEXT NOT NULL,
    FOREIGN KEY (app_id) REFERENCES oauth_applications(id) ON DELETE CASCADE
);

CREATE INDEX idx_oauth_audit_client ON oauth_audit_log(client_id);
CREATE INDEX idx_oauth_audit_app ON oauth_audit_log(app_id);
CREATE INDEX idx_oauth_audit_created ON oauth_audit_log(created);
CREATE INDEX idx_oauth_audit_status ON oauth_audit_log(status_code);
