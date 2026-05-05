-- Migration: Add metadata and notebook_id to notes table
-- For template execution results and notebook association

-- Add metadata column for JSON metadata
ALTER TABLE notes ADD COLUMN metadata TEXT;

-- Add notebook_id column for primary notebook association
ALTER TABLE notes ADD COLUMN notebook_id TEXT REFERENCES notebooks(id) ON DELETE CASCADE;

-- Add index for notebook_id lookups
CREATE INDEX IF NOT EXISTS idx_notes_notebook_id ON notes(notebook_id);
