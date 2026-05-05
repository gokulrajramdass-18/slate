-- ============================================================================
-- Open Notebook - HANA Cloud Migration
-- Migration: 013_microsite_status_and_ownership
-- Database: SAP HANA Cloud
-- Description: Add status management (draft/published/blocked), ownership tracking,
--              and active version reference to microsites. Extend microsite_versions
--              with publish metadata.
-- Date: 2026-03-25
-- ============================================================================

-- ============================================================================
-- EXTEND MICROSITES TABLE
-- ============================================================================

-- Status field for content lifecycle (draft -> published -> blocked)
ALTER TABLE microsites ADD (status NVARCHAR(20) DEFAULT 'draft' NOT NULL);

-- Add CHECK constraint for allowed status values
ALTER TABLE microsites ADD CONSTRAINT chk_microsites_status
    CHECK (status IN ('draft', 'published', 'blocked'));

-- Ownership tracking (user ID or email of creator)
ALTER TABLE microsites ADD (created_by NVARCHAR(255));

-- Reference to the currently active/published version
ALTER TABLE microsites ADD (active_version_id VARCHAR(36));

ALTER TABLE microsites ADD CONSTRAINT fk_microsites_active_version
    FOREIGN KEY (active_version_id) REFERENCES microsite_versions(id)
    ON DELETE SET NULL;

-- Indexes for efficient querying by status and creator
CREATE INDEX idx_microsites_status ON microsites(status);
CREATE INDEX idx_microsites_created_by ON microsites(created_by);

-- ============================================================================
-- EXTEND MICROSITE_VERSIONS TABLE
-- ============================================================================

-- Status of the microsite at time of publish (audit trail)
ALTER TABLE microsite_versions ADD (status_at_publish NVARCHAR(20));

ALTER TABLE microsite_versions ADD CONSTRAINT chk_versions_status_at_publish
    CHECK (status_at_publish IN ('draft', 'published', 'blocked'));

-- Timestamp when this version was published (separate from created timestamp)
ALTER TABLE microsite_versions ADD (published_at TIMESTAMP);

-- Note: UNIQUE index on (microsite_id, version_number) already exists from
-- the initial HANA schema, so we do not recreate it here.

-- ============================================================================
-- Insert migration record
-- ============================================================================
INSERT INTO _migrations (id, version, name, applied_at)
VALUES ('hana-013', 13, '013_microsite_status_and_ownership', CURRENT_TIMESTAMP);
