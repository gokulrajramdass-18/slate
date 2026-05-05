-- Migration 032: Bookmark Embeddings
-- Add embeddings table for semantic search of bookmarks

-- Bookmark Embeddings Table
-- Stores embeddings for natural language search of bookmarks
CREATE TABLE IF NOT EXISTS bookmark_embeddings (
    id VARCHAR(36) PRIMARY KEY,
    bookmark_id VARCHAR(36) NOT NULL,
    content TEXT NOT NULL,  -- The text that was embedded (searchable context)
    embedding BLOB NOT NULL,  -- Serialized embedding vector
    created TEXT NOT NULL,
    FOREIGN KEY (bookmark_id) REFERENCES user_bookmarks(id) ON DELETE CASCADE
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_bookmark_embeddings_bookmark ON bookmark_embeddings(bookmark_id);

-- Record migration
INSERT INTO _migrations (id, version, name, applied_at)
VALUES (
    'migration-032',
    32,
    'bookmark_embeddings',
    datetime('now')
);
