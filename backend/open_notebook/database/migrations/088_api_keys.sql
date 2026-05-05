-- API Keys for external application authentication
-- Allows external apps to send notifications via REST API

CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,  -- Friendly name for the API key
    description TEXT,  -- Purpose/usage description
    key_hash TEXT NOT NULL UNIQUE,  -- Hashed API key
    key_prefix TEXT NOT NULL,  -- First 8 chars for identification

    -- Permissions
    scopes TEXT NOT NULL,  -- JSON array of allowed scopes: ['notifications:write']

    -- Associated user/application
    owner_id TEXT NOT NULL,  -- User who created this key
    application_name TEXT,  -- External application name

    -- Usage tracking
    last_used_at TIMESTAMP,
    usage_count INTEGER DEFAULT 0,

    -- Status
    is_active INTEGER DEFAULT 1,
    expires_at TIMESTAMP,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_owner_id ON api_keys(owner_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_is_active ON api_keys(is_active);

-- API Key usage logs for audit trail
CREATE TABLE IF NOT EXISTS api_key_usage_logs (
    id TEXT PRIMARY KEY,
    api_key_id TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    status_code INTEGER,
    ip_address TEXT,
    user_agent TEXT,
    request_body TEXT,  -- JSON of request for audit
    response_body TEXT,  -- JSON of response for audit
    error TEXT,  -- Error message if failed
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (api_key_id) REFERENCES api_keys(id) ON DELETE CASCADE
);

-- Indexes for usage logs
CREATE INDEX IF NOT EXISTS idx_api_key_usage_logs_api_key_id ON api_key_usage_logs(api_key_id);
CREATE INDEX IF NOT EXISTS idx_api_key_usage_logs_timestamp ON api_key_usage_logs(timestamp DESC);
