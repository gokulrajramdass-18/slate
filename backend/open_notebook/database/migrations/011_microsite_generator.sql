-- Microsite Generator migration
-- Migration: 011_microsite_generator
-- Database: SQLite
-- Description: Tables for microsite generation with AI enhancement, dual edit modes,
--              content moderation, versioning, and template-based structure.

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- ============================================================================
-- NEW TABLES
-- ============================================================================

-- Microsite Templates (pre-built themes: blog, docs, portfolio, landing, report)
CREATE TABLE IF NOT EXISTS microsite_templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    description TEXT,
    structure TEXT NOT NULL,       -- JSON: sections, layout, prompt templates
    default_styles TEXT,           -- JSON: CSS variables, fonts, colors
    preview_image TEXT,            -- Base64 or URL for template preview
    is_custom INTEGER DEFAULT 0,  -- 0 = built-in, 1 = user-created
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_microsite_templates_name ON microsite_templates(name);
CREATE INDEX IF NOT EXISTS idx_microsite_templates_custom ON microsite_templates(is_custom);

-- Microsite Content (individual editable sections with HTML + TipTap JSON)
CREATE TABLE IF NOT EXISTS microsite_content (
    id TEXT PRIMARY KEY,
    microsite_id TEXT NOT NULL,
    section_id TEXT NOT NULL,       -- Matches section id in template structure
    content_html TEXT,              -- Rendered HTML for display
    content_json TEXT,              -- TipTap JSON for WYSIWYG editing
    order_num INTEGER DEFAULT 0,   -- Display order
    is_visible INTEGER DEFAULT 1,  -- Toggle section visibility
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (microsite_id) REFERENCES microsites(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_microsite_content_microsite ON microsite_content(microsite_id);
CREATE INDEX IF NOT EXISTS idx_microsite_content_section ON microsite_content(microsite_id, section_id);
CREATE INDEX IF NOT EXISTS idx_microsite_content_order ON microsite_content(microsite_id, order_num);

-- Microsite Versions (full snapshots for rollback)
CREATE TABLE IF NOT EXISTS microsite_versions (
    id TEXT PRIMARY KEY,
    microsite_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    full_html TEXT,                  -- Complete rendered HTML document
    full_css TEXT,                   -- Complete CSS (template + custom)
    content_snapshot TEXT,           -- JSON: snapshot of all content sections
    created_by TEXT,                 -- User or 'system' for auto-generated
    created TEXT NOT NULL,
    -- Columns from migration 013 (moved here to fix ordering)
    status_at_publish TEXT,          -- Status of the microsite at time of publish (audit trail)
    published_at TEXT,               -- Timestamp when this version was published
    FOREIGN KEY (microsite_id) REFERENCES microsites(id) ON DELETE CASCADE,
    UNIQUE(microsite_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_microsite_versions_microsite ON microsite_versions(microsite_id);
CREATE INDEX IF NOT EXISTS idx_microsite_versions_number ON microsite_versions(microsite_id, version_number);
CREATE INDEX IF NOT EXISTS idx_microsite_versions_created ON microsite_versions(created);

-- Microsite Sources (track which sources were used in generation)
CREATE TABLE IF NOT EXISTS microsite_sources (
    microsite_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    created TEXT NOT NULL,
    PRIMARY KEY (microsite_id, source_id),
    FOREIGN KEY (microsite_id) REFERENCES microsites(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_microsite_sources_microsite ON microsite_sources(microsite_id);
CREATE INDEX IF NOT EXISTS idx_microsite_sources_source ON microsite_sources(source_id);

-- Content Moderation Logs (audit trail for all guardrail strategies)
CREATE TABLE IF NOT EXISTS content_moderation_logs (
    id TEXT PRIMARY KEY,
    microsite_id TEXT NOT NULL,
    content_section TEXT,            -- Section ID or 'full' for whole-site moderation
    moderation_type TEXT NOT NULL,   -- ai_filter, keyword_blocklist, source_validation, user_review
    status TEXT NOT NULL,            -- passed, warning, blocked
    score REAL,                      -- 0.0 to 1.0 safety/quality score
    issues_found TEXT,               -- JSON array of issue objects
    metadata TEXT,                   -- JSON: additional context (model used, processing time, etc.)
    created TEXT NOT NULL,
    FOREIGN KEY (microsite_id) REFERENCES microsites(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_moderation_logs_microsite ON content_moderation_logs(microsite_id);
CREATE INDEX IF NOT EXISTS idx_moderation_logs_type ON content_moderation_logs(moderation_type);
CREATE INDEX IF NOT EXISTS idx_moderation_logs_status ON content_moderation_logs(status);
CREATE INDEX IF NOT EXISTS idx_moderation_logs_created ON content_moderation_logs(created);

-- Content Blocklist (user-configurable keyword/pattern blocklist)
CREATE TABLE IF NOT EXISTS content_blocklist (
    id TEXT PRIMARY KEY,
    keyword TEXT NOT NULL,
    category TEXT DEFAULT 'custom',  -- profanity, sensitive, custom
    severity TEXT DEFAULT 'warning', -- block, warning
    is_regex INTEGER DEFAULT 0,      -- 0 = literal match, 1 = regex pattern
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_blocklist_category ON content_blocklist(category);
CREATE INDEX IF NOT EXISTS idx_blocklist_severity ON content_blocklist(severity);

-- ============================================================================
-- EXTEND MICROSITES TABLE
-- ============================================================================

-- NOTE: These columns are now created in migration 090 to fix ordering issues
-- Add new columns to existing microsites table for generator integration
-- ALTER TABLE microsites ADD COLUMN template_id TEXT REFERENCES microsite_templates(id) ON DELETE SET NULL;
-- ALTER TABLE microsites ADD COLUMN custom_css TEXT;
-- ALTER TABLE microsites ADD COLUMN custom_js TEXT;
-- ALTER TABLE microsites ADD COLUMN generation_config TEXT;        -- JSON: AI prompts, settings, parameters
-- ALTER TABLE microsites ADD COLUMN moderation_status TEXT DEFAULT 'pending';  -- pending, passed, needs_review, blocked
-- ALTER TABLE microsites ADD COLUMN published_version INTEGER;
-- ALTER TABLE microsites ADD COLUMN last_generated TEXT;           -- ISO timestamp of last AI generation

-- Indexes on new columns (now in migration 090)
-- CREATE INDEX IF NOT EXISTS idx_microsites_template ON microsites(template_id);
-- CREATE INDEX IF NOT EXISTS idx_microsites_moderation ON microsites(moderation_status);
-- CREATE INDEX IF NOT EXISTS idx_microsites_published ON microsites(published_version);
