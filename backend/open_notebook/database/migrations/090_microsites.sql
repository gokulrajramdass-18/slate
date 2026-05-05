-- Microsites migration
-- Create tables for sharing notebooks as public microsites with email authentication

CREATE TABLE IF NOT EXISTS microsites (
    id TEXT PRIMARY KEY,
    notebook_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    slug TEXT UNIQUE NOT NULL,
    theme TEXT DEFAULT 'light',
    is_active INTEGER DEFAULT 1,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    -- Columns from migration 011 (moved here to fix ordering)
    template_id TEXT,
    custom_css TEXT,
    custom_js TEXT,
    generation_config TEXT,
    moderation_status TEXT DEFAULT 'pending',
    published_version INTEGER,
    last_generated TEXT,
    -- Columns from migration 013
    status TEXT NOT NULL DEFAULT 'draft',
    created_by TEXT,
    active_version_id TEXT,
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS microsite_access (
    id TEXT PRIMARY KEY,
    microsite_id TEXT NOT NULL,
    email TEXT NOT NULL,
    created TEXT NOT NULL,
    FOREIGN KEY (microsite_id) REFERENCES microsites(id) ON DELETE CASCADE,
    UNIQUE(microsite_id, email)
);

CREATE TABLE IF NOT EXISTS microsite_otp (
    id TEXT PRIMARY KEY,
    microsite_id TEXT NOT NULL,
    email TEXT NOT NULL,
    otp_code TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    verified INTEGER DEFAULT 0,
    created TEXT NOT NULL,
    FOREIGN KEY (microsite_id) REFERENCES microsites(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_microsites_notebook ON microsites(notebook_id);
CREATE INDEX IF NOT EXISTS idx_microsites_slug ON microsites(slug);
CREATE INDEX IF NOT EXISTS idx_microsite_access_email ON microsite_access(email);
CREATE INDEX IF NOT EXISTS idx_microsite_otp_code ON microsite_otp(otp_code);
CREATE INDEX IF NOT EXISTS idx_microsite_otp_expires ON microsite_otp(expires_at);

-- Indexes from migration 011
CREATE INDEX IF NOT EXISTS idx_microsites_template ON microsites(template_id);
CREATE INDEX IF NOT EXISTS idx_microsites_moderation ON microsites(moderation_status);
CREATE INDEX IF NOT EXISTS idx_microsites_published ON microsites(published_version);

-- Indexes from migration 013
CREATE INDEX IF NOT EXISTS idx_microsites_status ON microsites(status);
CREATE INDEX IF NOT EXISTS idx_microsites_created_by ON microsites(created_by);
