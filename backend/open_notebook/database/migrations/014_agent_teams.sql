-- Migration: 014 - Agent Teams
-- Description: Schema for agent team coordination, inter-agent messaging, and task management
-- Date: 2026-03-25

-- ============================================================================
-- AGENT TEAMS TABLE
-- ============================================================================
-- An agent team is a group of agents collaborating on a goal

CREATE TABLE IF NOT EXISTS agent_teams (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    goal TEXT,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, running, completed, failed, cancelled
    notebook_id TEXT,
    session_id TEXT,
    config TEXT,        -- JSON: model overrides, max_iterations, etc.
    result TEXT,        -- JSON: final output / summary
    error TEXT,
    started_at TEXT,
    completed_at TEXT,
    created_by VARCHAR(36),  -- From migration 056 - moved here to fix ordering
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE SET NULL,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_teams_status ON agent_teams(status);
CREATE INDEX IF NOT EXISTS idx_agent_teams_notebook ON agent_teams(notebook_id);
CREATE INDEX IF NOT EXISTS idx_agent_teams_session ON agent_teams(session_id);

-- ============================================================================
-- AGENT INSTANCES TABLE
-- ============================================================================
-- Individual agent instances within a team

CREATE TABLE IF NOT EXISTS agent_instances (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    role TEXT NOT NULL,           -- planner, researcher, analyst, synthesizer, custom
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'idle',  -- idle, busy, completed, failed
    model_name TEXT,
    system_prompt TEXT,
    config TEXT,                  -- JSON: role-specific config
    result TEXT,                  -- JSON: agent output
    error TEXT,
    started_at TEXT,
    completed_at TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_agent_instances_team ON agent_instances(team_id);
CREATE INDEX IF NOT EXISTS idx_agent_instances_role ON agent_instances(role);
CREATE INDEX IF NOT EXISTS idx_agent_instances_status ON agent_instances(status);

-- ============================================================================
-- AGENT MESSAGES TABLE
-- ============================================================================
-- Messages exchanged between agents in a team

CREATE TABLE IF NOT EXISTS agent_messages (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    sender_id TEXT NOT NULL,      -- agent_instance id or 'system'
    recipient_id TEXT,            -- agent_instance id, NULL = broadcast
    message_type TEXT NOT NULL DEFAULT 'chat',  -- chat, task_assign, task_result, error, control
    content TEXT NOT NULL,
    metadata TEXT,                -- JSON: extra data (tool results, references, etc.)
    created TEXT NOT NULL,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_agent_messages_team ON agent_messages(team_id);
CREATE INDEX IF NOT EXISTS idx_agent_messages_sender ON agent_messages(sender_id);
CREATE INDEX IF NOT EXISTS idx_agent_messages_recipient ON agent_messages(recipient_id);
CREATE INDEX IF NOT EXISTS idx_agent_messages_created ON agent_messages(created);

-- ============================================================================
-- AGENT TASKS TABLE
-- ============================================================================
-- Tasks assigned to agents within a team

CREATE TABLE IF NOT EXISTS agent_tasks (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    assignee_id TEXT,             -- agent_instance id, NULL = unassigned
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, blocked, in_progress, completed, failed, cancelled
    priority INTEGER NOT NULL DEFAULT 0,     -- 0=normal, 1=high, 2=critical
    result TEXT,                  -- JSON: task output
    error TEXT,
    depends_on TEXT,              -- JSON array of task IDs this depends on
    started_at TEXT,
    completed_at TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE,
    FOREIGN KEY (assignee_id) REFERENCES agent_instances(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_tasks_team ON agent_tasks(team_id);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_assignee ON agent_tasks(assignee_id);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_status ON agent_tasks(status);

-- ============================================================================
-- NOTES
-- ============================================================================
-- config/result/metadata columns store JSON-encoded data.
-- depends_on stores a JSON array of agent_tasks.id values, e.g. ["task-uuid-1","task-uuid-2"].
-- Dependency resolution is handled in application code (see task_manager.py).

CREATE INDEX IF NOT EXISTS idx_agent_teams_created_by ON agent_teams(created_by);
