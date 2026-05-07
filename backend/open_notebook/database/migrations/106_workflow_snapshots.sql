-- Migration 030: Workflow Snapshots with Context-Aware Multi-Tenant Support
-- Creates table for storing workflow node output snapshots with:
-- - User-scoped access (multi-tenant isolation)
-- - Query context tracking (for proper comparison)
-- - Tiered storage (inline/file/chunked)
-- - Fast comparison via hashes and statistics

-- Main snapshots table
CREATE TABLE IF NOT EXISTS workflow_snapshots (
    -- Identity
    id TEXT PRIMARY KEY,

    -- Ownership & Scope (Multi-tenant)
    workflow_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    execution_id TEXT,
    user_id TEXT NOT NULL,

    -- Temporal
    snapshot_date TEXT NOT NULL,  -- ISO date format
    snapshot_label TEXT,          -- 'yesterday', 'today', 'baseline', etc.
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT,              -- Auto-cleanup date

    -- Storage Strategy
    storage_type TEXT NOT NULL CHECK(storage_type IN ('inline', 'file', 'chunked')),
    storage_path TEXT,            -- Path to external storage (for file/chunked)
    inline_data TEXT,             -- Compressed data (for inline storage)

    -- Data Characteristics
    data_hash TEXT NOT NULL,      -- SHA256 of full data
    row_count INTEGER NOT NULL DEFAULT 0,
    total_size_bytes INTEGER NOT NULL DEFAULT 0,
    column_count INTEGER DEFAULT 0,

    -- Context Tracking (Critical for proper comparison)
    query_context TEXT NOT NULL,  -- JSON: {user_id, query_params, input_data, source_config}
    context_hash TEXT NOT NULL,   -- SHA256 of query_context for fast matching

    -- Metadata for Fast Comparison (without loading full data)
    stats_summary TEXT,           -- JSON: {column: {min, max, avg, stddev}}
    sample_data TEXT,             -- JSON: First 100 rows for preview
    bloom_filter BLOB,            -- Optional: For membership testing

    -- Constraints
    UNIQUE(workflow_id, node_id, user_id, context_hash, snapshot_date),
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE,
    FOREIGN KEY (execution_id) REFERENCES workflow_executions(id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Performance Indexes

-- User's snapshots (for dashboard view)
CREATE INDEX IF NOT EXISTS idx_snapshots_user_date
    ON workflow_snapshots(user_id, snapshot_date DESC);

-- Workflow-specific snapshots
CREATE INDEX IF NOT EXISTS idx_snapshots_workflow_user
    ON workflow_snapshots(workflow_id, user_id, snapshot_date DESC);

-- Context-based lookup (for finding comparable snapshots)
CREATE INDEX IF NOT EXISTS idx_snapshots_context
    ON workflow_snapshots(context_hash, snapshot_date DESC);

-- Cleanup job efficiency
CREATE INDEX IF NOT EXISTS idx_snapshots_cleanup
    ON workflow_snapshots(expires_at)
    WHERE expires_at IS NOT NULL;

-- Execution tracking
CREATE INDEX IF NOT EXISTS idx_snapshots_execution
    ON workflow_snapshots(execution_id)
    WHERE execution_id IS NOT NULL;

-- Node-specific snapshots
CREATE INDEX IF NOT EXISTS idx_snapshots_node
    ON workflow_snapshots(workflow_id, node_id, snapshot_date DESC);

-- Helpful Views

-- User snapshot summary (for UI)
CREATE VIEW IF NOT EXISTS user_snapshot_summary AS
SELECT
    s.id,
    s.workflow_id,
    w.name as workflow_name,
    s.node_id,
    s.user_id,
    u.username,
    s.snapshot_date,
    s.snapshot_label,
    s.storage_type,
    s.row_count,
    s.total_size_bytes,
    ROUND(s.total_size_bytes / 1024.0 / 1024.0, 2) as size_mb,
    json_extract(s.query_context, '$.query_params') as query_params,
    s.created_at,
    s.expires_at,
    CASE
        WHEN s.expires_at IS NULL THEN 'permanent'
        WHEN datetime(s.expires_at) < datetime('now') THEN 'expired'
        ELSE 'active'
    END as status
FROM workflow_snapshots s
JOIN workflows w ON s.workflow_id = w.id
JOIN users u ON s.user_id = u.id
ORDER BY s.created_at DESC;

-- Storage statistics (for monitoring)
CREATE VIEW IF NOT EXISTS snapshot_storage_stats AS
SELECT
    storage_type,
    COUNT(*) as snapshot_count,
    SUM(total_size_bytes) as total_bytes,
    ROUND(SUM(total_size_bytes) / 1024.0 / 1024.0 / 1024.0, 2) as total_gb,
    AVG(total_size_bytes) as avg_bytes,
    MIN(total_size_bytes) as min_bytes,
    MAX(total_size_bytes) as max_bytes
FROM workflow_snapshots
GROUP BY storage_type;
