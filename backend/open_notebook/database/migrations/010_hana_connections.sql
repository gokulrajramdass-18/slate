-- Migration: Create HANA connections table
-- Purpose: Store reusable HANA database connections for sources

CREATE TABLE IF NOT EXISTS hana_connections (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    host TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 443,
    database TEXT NOT NULL,
    user TEXT NOT NULL,
    password_encrypted TEXT NOT NULL,  -- Encrypted with ENCRYPTION_KEY
    encrypt INTEGER NOT NULL DEFAULT 1,  -- Boolean: use SSL/TLS
    schema TEXT,  -- Optional default schema
    description TEXT,  -- Optional description
    created_by VARCHAR(36),  -- From migration 056 - moved here to fix ordering
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_hana_connections_name ON hana_connections(name);

CREATE INDEX IF NOT EXISTS idx_hana_connections_created_by ON hana_connections(created_by);
