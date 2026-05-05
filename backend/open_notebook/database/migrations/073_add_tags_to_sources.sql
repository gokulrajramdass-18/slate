-- Migration 073: Add tags support to sources
-- Date: 2026-04-24
-- Description: Add tags JSON column to sources table for organization

-- Add tags column to sources (JSON array of strings)
ALTER TABLE sources ADD COLUMN tags TEXT DEFAULT '[]';

-- Create index for better tag-based filtering performance
-- Note: SQLite doesn't support JSON indexing, but HANA does
-- For HANA: CREATE INDEX idx_sources_tags ON sources(tags);
