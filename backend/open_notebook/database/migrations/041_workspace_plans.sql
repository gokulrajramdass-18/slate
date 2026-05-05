-- Migration: 041_workspace_plans.sql
-- Description: Create table for persisted workspace plans with tasks and collaboration
-- Date: 2026-04-04

CREATE TABLE IF NOT EXISTS workspace_plans (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    goal TEXT NOT NULL,
    phases TEXT NOT NULL,          -- JSON: array of phases with tasks
    collaboration_graph TEXT,      -- JSON: agent collaboration structure
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'in_progress', 'completed', 'failed', 'cancelled')),
    progress TEXT,                 -- JSON: task completion tracking
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_workspace_plans_workspace_id ON workspace_plans(workspace_id);
CREATE INDEX IF NOT EXISTS idx_workspace_plans_status ON workspace_plans(status);

