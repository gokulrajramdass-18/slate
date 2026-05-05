-- Migration: 061_workspace_templates.sql
-- Description: Create table for reusable workspace templates with parameterization
-- Date: 2026-04-22

CREATE TABLE IF NOT EXISTS workspace_templates (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT CHECK(category IN ('data_pipeline', 'research', 'reporting', 'monitoring', 'analysis', 'automation', 'other')),

    -- Template structure (cloneable)
    phases TEXT NOT NULL,              -- JSON: array of phase definitions with tasks
    collaboration_graph TEXT,          -- JSON: agent coordination patterns
    default_resources TEXT,            -- JSON: default tools/sources/agents {source_ids: [], tool_ids: [], agent_ids: [], team_ids: []}

    -- Parameterization
    parameters TEXT,                   -- JSON: [{name, type, description, default_value, required, options}]

    -- Metadata
    version INTEGER DEFAULT 1,
    is_public INTEGER DEFAULT 0,       -- 0 = private, 1 = public (shareable)
    tags TEXT,                         -- JSON: array of searchable tags
    usage_count INTEGER DEFAULT 0,     -- Track popularity

    -- Timestamps
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_workspace_templates_user_id ON workspace_templates(user_id);
CREATE INDEX IF NOT EXISTS idx_workspace_templates_category ON workspace_templates(category);
CREATE INDEX IF NOT EXISTS idx_workspace_templates_is_public ON workspace_templates(is_public);
CREATE INDEX IF NOT EXISTS idx_workspace_templates_created_at ON workspace_templates(created_at);
CREATE INDEX IF NOT EXISTS idx_workspace_templates_usage_count ON workspace_templates(usage_count);
