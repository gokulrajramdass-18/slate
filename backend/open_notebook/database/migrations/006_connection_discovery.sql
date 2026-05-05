-- Migration: Connection Discovery Tables
-- Description: Create tables to store discovered HANA tables and API endpoints
-- Date: 2026-03-28

-- ============================================================================
-- HANA Connection Tables Discovery
-- ============================================================================

CREATE TABLE IF NOT EXISTS hana_connection_tables (
    id TEXT PRIMARY KEY,
    connection_id TEXT NOT NULL,
    schema_name TEXT,
    table_name TEXT NOT NULL,
    table_type TEXT,  -- 'TABLE', 'VIEW', 'COLUMN TABLE', 'ROW TABLE'
    column_metadata TEXT,  -- JSON array of {name, type, length, nullable, is_primary_key}
    row_count INTEGER,
    discovered_at TEXT NOT NULL,

    FOREIGN KEY (connection_id) REFERENCES hana_connections(id) ON DELETE CASCADE,
    UNIQUE(connection_id, schema_name, table_name)
);

-- Indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_hana_conn_tables_conn ON hana_connection_tables(connection_id);
CREATE INDEX IF NOT EXISTS idx_hana_conn_tables_name ON hana_connection_tables(table_name);
CREATE INDEX IF NOT EXISTS idx_hana_conn_tables_discovered ON hana_connection_tables(discovered_at DESC);

-- ============================================================================
-- API Connection Endpoints Discovery
-- ============================================================================

CREATE TABLE IF NOT EXISTS api_connection_endpoints (
    id TEXT PRIMARY KEY,
    connection_id TEXT NOT NULL,
    endpoint_path TEXT NOT NULL,  -- e.g., /users, /orders/{id}
    method TEXT NOT NULL,  -- GET, POST, PUT, DELETE, PATCH
    description TEXT,
    parameters TEXT,  -- JSON array of {name, type, in, required, description}
    request_body_schema TEXT,  -- JSON schema for request body
    response_schema TEXT,  -- JSON schema for response
    discovered_at TEXT NOT NULL,
    discovery_source TEXT,  -- 'openapi', 'swagger', 'manual'

    FOREIGN KEY (connection_id) REFERENCES api_connections(id) ON DELETE CASCADE,
    UNIQUE(connection_id, endpoint_path, method)
);

-- Indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_api_conn_endpoints_conn ON api_connection_endpoints(connection_id);
CREATE INDEX IF NOT EXISTS idx_api_conn_endpoints_method ON api_connection_endpoints(method);
CREATE INDEX IF NOT EXISTS idx_api_conn_endpoints_discovered ON api_connection_endpoints(discovered_at DESC);
