-- Migration: 018 - Tool Registry
-- Description: Create tables for tool management, permissions, and usage tracking
-- Date: 2026-03-25

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- ============================================================================
-- TOOL REGISTRY TABLE
-- ============================================================================
-- Central registry of all available tools (hana_query, api_call, web_search, etc.)

CREATE TABLE IF NOT EXISTS tool_registry (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    tool_type TEXT NOT NULL,        -- hana_query, api_call, web_search, etc.
    category TEXT NOT NULL,         -- data_query, web, computation, etc.
    description TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    default_config TEXT,            -- JSON object with tool-specific defaults
    metadata TEXT,                  -- JSON: icon, tags, author, version, documentation_url, cost_per_call
    created_by VARCHAR(36),         -- From migration 056 - moved here to fix ordering
    created TEXT NOT NULL DEFAULT (datetime('now')),
    updated TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tool_registry_tool_type ON tool_registry(tool_type);
CREATE INDEX IF NOT EXISTS idx_tool_registry_enabled ON tool_registry(enabled);
CREATE INDEX IF NOT EXISTS idx_tool_registry_category ON tool_registry(category);

-- ============================================================================
-- TOOL PERMISSIONS TABLE
-- ============================================================================
-- Per-user or per-role permission overrides for tools

CREATE TABLE IF NOT EXISTS tool_permissions (
    id TEXT PRIMARY KEY,
    tool_id TEXT NOT NULL,
    user_id TEXT,                   -- nullable: applies to specific user
    role TEXT,                      -- nullable: applies to role
    allowed INTEGER NOT NULL DEFAULT 1,
    rate_limit INTEGER,            -- max calls per hour, nullable
    custom_config TEXT,            -- JSON: per-user/role config overrides, nullable
    created TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (tool_id) REFERENCES tool_registry(id) ON DELETE CASCADE,
    -- Exactly one of user_id or role must be set
    CHECK ((user_id IS NOT NULL AND role IS NULL) OR (user_id IS NULL AND role IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS idx_tool_permissions_tool ON tool_permissions(tool_id);
CREATE INDEX IF NOT EXISTS idx_tool_permissions_user ON tool_permissions(user_id);
CREATE INDEX IF NOT EXISTS idx_tool_permissions_role ON tool_permissions(role);

-- ============================================================================
-- TOOL USAGE LOG TABLE
-- ============================================================================
-- Audit trail of tool executions for analytics and debugging

CREATE TABLE IF NOT EXISTS tool_usage_log (
    id TEXT PRIMARY KEY,
    tool_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    notebook_id TEXT NOT NULL,
    input_params TEXT,             -- JSON: parameters passed to the tool
    execution_time_ms INTEGER,
    success INTEGER NOT NULL DEFAULT 1,
    error_message TEXT,
    created TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (tool_id) REFERENCES tool_registry(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tool_usage_log_tool ON tool_usage_log(tool_id);
CREATE INDEX IF NOT EXISTS idx_tool_usage_log_user ON tool_usage_log(user_id);
CREATE INDEX IF NOT EXISTS idx_tool_usage_log_created ON tool_usage_log(created);

CREATE INDEX IF NOT EXISTS idx_tool_registry_created_by ON tool_registry(created_by);
