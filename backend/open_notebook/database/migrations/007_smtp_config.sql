-- SMTP configuration migration
-- Store SMTP server settings for email functionality

CREATE TABLE IF NOT EXISTS smtp_config (
    id TEXT PRIMARY KEY DEFAULT 'default',
    smtp_host TEXT NOT NULL,
    smtp_port INTEGER NOT NULL,
    smtp_username TEXT NOT NULL,
    smtp_password TEXT NOT NULL,
    smtp_from_email TEXT NOT NULL,
    smtp_from_name TEXT,
    smtp_use_tls INTEGER DEFAULT 1,
    smtp_use_ssl INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);

-- Only allow one SMTP config
CREATE UNIQUE INDEX IF NOT EXISTS idx_smtp_config_singleton ON smtp_config(id);
