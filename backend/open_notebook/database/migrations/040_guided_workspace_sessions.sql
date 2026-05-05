-- Migration: 040_guided_workspace_sessions.sql
-- Description: Create table for temporary guided workspace creation sessions
-- Date: 2026-04-04

CREATE TABLE IF NOT EXISTS guided_workspace_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    goal TEXT NOT NULL,
    analysis TEXT,              -- JSON: goal analysis results
    clarifications TEXT,        -- JSON: user answers to clarification questions
    selected_resources TEXT,    -- JSON: selected data sources, tools, agents, teams
    generated_plan TEXT,        -- JSON: generated task plan
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'completed', 'abandoned')),
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP        -- Auto-cleanup after 24 hours
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_guided_sessions_user_id ON guided_workspace_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_guided_sessions_status ON guided_workspace_sessions(status);
CREATE INDEX IF NOT EXISTS idx_guided_sessions_expires_at ON guided_workspace_sessions(expires_at);

