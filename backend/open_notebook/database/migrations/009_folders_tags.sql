-- Migration 009: Add folders and tags support
-- Date: 2026-03-22

-- Add tags column to notebooks (JSON array of strings)
ALTER TABLE notebooks ADD COLUMN tags TEXT DEFAULT '[]';

-- Add folders table (if not exists for idempotency)
CREATE TABLE IF NOT EXISTS folders (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    parent_id TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (parent_id) REFERENCES folders(id) ON DELETE CASCADE
);

-- Add tags table (if not exists for idempotency)
CREATE TABLE IF NOT EXISTS tags (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    created TEXT NOT NULL
);

-- Add notebook_tags junction table (if not exists for idempotency)
CREATE TABLE IF NOT EXISTS notebook_tags (
    notebook_id TEXT NOT NULL,
    tag_id TEXT NOT NULL,
    PRIMARY KEY (notebook_id, tag_id),
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_folders_parent_id ON folders(parent_id);
CREATE INDEX IF NOT EXISTS idx_notebook_tags_notebook_id ON notebook_tags(notebook_id);
CREATE INDEX IF NOT EXISTS idx_notebook_tags_tag_id ON notebook_tags(tag_id);
