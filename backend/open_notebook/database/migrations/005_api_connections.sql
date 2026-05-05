-- Migration: API Connections Management
-- Description: Create table to store reusable API connection configurations
-- Date: 2026-03-23

CREATE TABLE IF NOT EXISTS api_connections (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,

    -- Connection details
    endpoint TEXT NOT NULL,
    auth_type TEXT NOT NULL, -- 'none', 'basic', 'bearer', 'api_key', 'oauth2_client_credentials', 'oauth2_authorization_code'

    -- Authentication config (encrypted JSON)
    auth_config_encrypted TEXT,

    -- Headers (stored as JSON)
    headers TEXT,

    -- Request configuration
    method TEXT DEFAULT 'GET',
    query_params TEXT, -- JSON
    request_body TEXT, -- JSON

    -- Response parsing
    data_path TEXT, -- JSONPath to extract data array
    id_field TEXT DEFAULT 'id',
    content_fields TEXT, -- JSON array of field names

    -- Metadata
    created_by TEXT,  -- From migration 056 - moved here to fix ordering
    created TEXT,
    updated TEXT,
    last_tested TEXT,
    test_status TEXT, -- 'success', 'failed', 'pending'
    test_message TEXT,

    -- Constraints
    UNIQUE(name)
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_api_connections_created ON api_connections(created DESC);
CREATE INDEX IF NOT EXISTS idx_api_connections_test_status ON api_connections(test_status);

CREATE INDEX IF NOT EXISTS idx_api_connections_created_by ON api_connections(created_by);
