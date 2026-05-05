-- Migration: 043_add_goal_to_notebooks.sql
-- Description: Add goal field to notebooks table for guided workspace creation
-- Date: 2026-04-04

-- Add goal column to notebooks
ALTER TABLE notebooks ADD COLUMN goal TEXT;

-- Create index for searching by goal
CREATE INDEX IF NOT EXISTS idx_notebooks_goal ON notebooks(goal);

