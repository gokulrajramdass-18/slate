-- Migration 025: User Bookmarks
-- Create table for user-specific bookmarks across entity types (sources, notes, notebooks)

CREATE TABLE IF NOT EXISTS user_bookmarks (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,              -- 'source', 'note', 'notebook'
    entity_id VARCHAR(36) NOT NULL,
    custom_note TEXT,
    reason TEXT,
    bookmarked_at TEXT NOT NULL,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    UNIQUE(user_id, entity_type, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_user_bookmarks_user ON user_bookmarks(user_id);
CREATE INDEX IF NOT EXISTS idx_user_bookmarks_entity ON user_bookmarks(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_user_bookmarks_user_type ON user_bookmarks(user_id, entity_type);
CREATE INDEX IF NOT EXISTS idx_user_bookmarks_bookmarked_at ON user_bookmarks(bookmarked_at DESC);
