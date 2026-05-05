-- ============================================================================
-- Open Notebook - HANA Cloud Tool Registry Schema
-- Migration: 018_tool_registry
-- Database: SAP HANA Cloud
-- Description: Create tables for tool management, permissions, and usage tracking
-- Date: 2026-03-25
-- ============================================================================

-- ============================================================================
-- TOOL REGISTRY TABLE
-- ============================================================================
-- Central registry of all available tools (hana_query, api_call, web_search, etc.)

CREATE COLUMN TABLE tool_registry (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    tool_type VARCHAR(50) NOT NULL,       -- hana_query, api_call, web_search, etc.
    category VARCHAR(100) NOT NULL,       -- data_query, web, computation, etc.
    description NCLOB,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    default_config NCLOB,                 -- JSON object with tool-specific defaults
    metadata NCLOB,                       -- JSON: icon, tags, author, version, documentation_url, cost_per_call
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tool_registry_tool_type ON tool_registry(tool_type);
CREATE INDEX idx_tool_registry_enabled ON tool_registry(enabled);
CREATE INDEX idx_tool_registry_category ON tool_registry(category);

-- ============================================================================
-- TOOL PERMISSIONS TABLE
-- ============================================================================
-- Per-user or per-role permission overrides for tools

CREATE COLUMN TABLE tool_permissions (
    id VARCHAR(36) PRIMARY KEY,
    tool_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36),                  -- nullable: applies to specific user
    role VARCHAR(100),                    -- nullable: applies to role
    allowed BOOLEAN NOT NULL DEFAULT TRUE,
    rate_limit INTEGER,                   -- max calls per hour, nullable
    custom_config NCLOB,                  -- JSON: per-user/role config overrides, nullable
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tool_id) REFERENCES tool_registry(id) ON DELETE CASCADE,
    CHECK ((user_id IS NOT NULL AND role IS NULL) OR (user_id IS NULL AND role IS NOT NULL))
);

CREATE INDEX idx_tool_permissions_tool ON tool_permissions(tool_id);
CREATE INDEX idx_tool_permissions_user ON tool_permissions(user_id);
CREATE INDEX idx_tool_permissions_role ON tool_permissions(role);

-- ============================================================================
-- TOOL USAGE LOG TABLE
-- ============================================================================
-- Audit trail of tool executions for analytics and debugging

CREATE COLUMN TABLE tool_usage_log (
    id VARCHAR(36) PRIMARY KEY,
    tool_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    session_id VARCHAR(36) NOT NULL,
    notebook_id VARCHAR(36) NOT NULL,
    input_params NCLOB,                   -- JSON: parameters passed to the tool
    execution_time_ms INTEGER,
    success BOOLEAN NOT NULL DEFAULT TRUE,
    error_message NCLOB,
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tool_id) REFERENCES tool_registry(id) ON DELETE CASCADE
);

CREATE INDEX idx_tool_usage_log_tool ON tool_usage_log(tool_id);
CREATE INDEX idx_tool_usage_log_user ON tool_usage_log(user_id);
CREATE INDEX idx_tool_usage_log_created ON tool_usage_log(created);

-- ============================================================================
-- Comments for Documentation
-- ============================================================================

COMMENT ON TABLE tool_registry IS 'Central registry of available tools (hana_query, api_call, web_search, etc.)';
COMMENT ON TABLE tool_permissions IS 'Per-user or per-role permission overrides for tools';
COMMENT ON TABLE tool_usage_log IS 'Audit trail of tool executions for analytics and debugging';
