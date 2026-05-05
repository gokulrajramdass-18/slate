-- Migration: 013 - Microsite Status and Ownership
-- Description: Add status management (draft/published/blocked), ownership tracking,
--              and active version reference to microsites. Extend microsite_versions
--              with publish metadata.
-- Date: 2026-03-25
-- NOTE: Most columns already exist from other migrations, so this is now mostly indexes

-- ============================================================================
-- EXTEND MICROSITES TABLE
-- ============================================================================

-- NOTE: These columns are now created in migration 090 to fix ordering issues
-- Status field
-- ALTER TABLE microsites ADD COLUMN status TEXT NOT NULL DEFAULT 'draft';

-- Ownership tracking
-- ALTER TABLE microsites ADD COLUMN created_by TEXT;

-- Reference to the currently active/published version
-- ALTER TABLE microsites ADD COLUMN active_version_id TEXT;

-- Indexes for efficient querying by status and creator (now in migration 090)
-- CREATE INDEX IF NOT EXISTS idx_microsites_status ON microsites(status);
-- CREATE INDEX IF NOT EXISTS idx_microsites_created_by ON microsites(created_by);

-- ============================================================================
-- EXTEND MICROSITE_VERSIONS TABLE
-- ============================================================================

-- NOTE: These columns are now created in migration 011 to fix ordering issues
-- Status of the microsite at time of publish (audit trail)
-- ALTER TABLE microsite_versions ADD COLUMN status_at_publish TEXT;

-- Timestamp when this version was published
-- ALTER TABLE microsite_versions ADD COLUMN published_at TEXT;
