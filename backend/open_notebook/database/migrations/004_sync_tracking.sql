-- Migration 004: Sync Tracking
-- Add support for background sync job tracking and history

-- Create sync_history table for tracking sync operations
CREATE TABLE IF NOT EXISTS sync_history (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    status TEXT NOT NULL,  -- pending, in_progress, completed, failed, cancelled
    started_at TEXT NOT NULL,
    completed_at TEXT,
    rows_updated INTEGER DEFAULT 0,
    duration_seconds REAL,
    error TEXT,
    created TEXT NOT NULL DEFAULT (datetime('now')),
    updated TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
);

-- Add indexes for sync_history
CREATE INDEX IF NOT EXISTS idx_sync_history_source ON sync_history(source_id);
CREATE INDEX IF NOT EXISTS idx_sync_history_status ON sync_history(status);
CREATE INDEX IF NOT EXISTS idx_sync_history_created ON sync_history(created DESC);

-- Add content_hash column to source_embeddings for change detection
-- (SQLite doesn't support ADD COLUMN IF NOT EXISTS, so we check first)
-- This will be handled by the migration runner

-- Update sources table to add sync tracking columns if they don't exist
-- ALTER TABLE sources ADD COLUMN last_synced TEXT;
-- ALTER TABLE sources ADD COLUMN sync_status TEXT;
-- ALTER TABLE sources ADD COLUMN error_message TEXT;

-- Note: For SQLite, we need to check if columns exist before adding them
-- This is handled programmatically in the migration runner
