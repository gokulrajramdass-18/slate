-- Migration: Add protected flag to notebooks to prevent deletion during critical operations
-- This ensures workspaces are never accidentally deleted during template execution or other operations

ALTER TABLE notebooks ADD COLUMN protected INTEGER DEFAULT 0;

CREATE INDEX idx_notebooks_protected ON notebooks(protected);
