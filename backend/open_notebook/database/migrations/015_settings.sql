-- Settings table for application configuration
-- Stores key-value pairs for persistent settings

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'string',  -- string, json, integer, boolean
    description TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);

-- Insert default model settings
INSERT OR IGNORE INTO settings (key, value, type, description, created, updated)
VALUES
    ('language_model_id', '', 'string', 'Default language model for chat', datetime('now'), datetime('now')),
    ('embedding_model_id', '', 'string', 'Default embedding model for search', datetime('now'), datetime('now')),
    ('tts_model_id', '', 'string', 'Default text-to-speech model', datetime('now'), datetime('now')),
    ('stt_model_id', '', 'string', 'Default speech-to-text model', datetime('now'), datetime('now'));
