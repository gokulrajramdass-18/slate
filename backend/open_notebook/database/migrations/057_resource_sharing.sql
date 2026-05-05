-- Migration: Resource Sharing
-- Created: 2026-04-11
-- Description: Generic resource sharing system for collaborative access

-- Generic Resource Sharing
CREATE TABLE IF NOT EXISTS resource_shares (
    id VARCHAR(36) PRIMARY KEY,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(36) NOT NULL,
    shared_by VARCHAR(36) NOT NULL,
    shared_with_user VARCHAR(36),
    shared_with_role VARCHAR(36),
    permission_level VARCHAR(20) NOT NULL CHECK (permission_level IN ('read', 'write', 'admin')),
    expires_at TEXT,
    created TEXT NOT NULL,
    FOREIGN KEY (shared_by) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (shared_with_user) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (shared_with_role) REFERENCES roles(id) ON DELETE CASCADE,
    CHECK (shared_with_user IS NOT NULL OR shared_with_role IS NOT NULL)
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_resource_shares_resource ON resource_shares(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_resource_shares_user ON resource_shares(shared_with_user);
CREATE INDEX IF NOT EXISTS idx_resource_shares_role ON resource_shares(shared_with_role);
CREATE INDEX IF NOT EXISTS idx_resource_shares_shared_by ON resource_shares(shared_by);
