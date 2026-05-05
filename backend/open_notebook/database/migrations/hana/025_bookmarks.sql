-- Migration 025: User Bookmarks (HANA version)
-- Create table for user-specific bookmarks across entity types (sources, notes, notebooks)

CREATE TABLE user_bookmarks (
    id NVARCHAR(36) PRIMARY KEY,
    user_id NVARCHAR(255) NOT NULL,
    entity_type NVARCHAR(50) NOT NULL,              -- 'source', 'note', 'notebook'
    entity_id NVARCHAR(36) NOT NULL,
    custom_note NCLOB,
    reason NCLOB,
    bookmarked_at NVARCHAR(50) NOT NULL,
    created NVARCHAR(50) NOT NULL,
    updated NVARCHAR(50) NOT NULL,
    UNIQUE(user_id, entity_type, entity_id)
);

CREATE INDEX idx_user_bookmarks_user ON user_bookmarks(user_id);
CREATE INDEX idx_user_bookmarks_entity ON user_bookmarks(entity_type, entity_id);
CREATE INDEX idx_user_bookmarks_user_type ON user_bookmarks(user_id, entity_type);
CREATE INDEX idx_user_bookmarks_bookmarked_at ON user_bookmarks(bookmarked_at);
