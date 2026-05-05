-- Migration 027: Add tags and categories to bookmarks
-- Add tags and categories fields for better bookmark organization

-- Add tags column (JSON array of strings)
ALTER TABLE user_bookmarks ADD COLUMN tags TEXT;

-- Add category column (single category string)
ALTER TABLE user_bookmarks ADD COLUMN category TEXT;

-- Create index for category filtering
CREATE INDEX IF NOT EXISTS idx_user_bookmarks_category ON user_bookmarks(category);
