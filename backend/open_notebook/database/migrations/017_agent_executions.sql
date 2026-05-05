-- Migration: 017_agent_executions
-- Add tables for tracking team executions, messages, and workflow steps

-- Team executions table
CREATE TABLE IF NOT EXISTS agent_executions (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    query TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running', -- 'running', 'completed', 'failed', 'cancelled'
    context_source_ids TEXT, -- JSON array of source IDs
    max_steps INTEGER DEFAULT 10,
    mode TEXT DEFAULT 'sequential', -- 'sequential', 'parallel', 'planned'
    result TEXT, -- JSON with final results
    started_at TEXT NOT NULL,
    completed_at TEXT,
    created TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_agent_executions_team_id ON agent_executions(team_id);
CREATE INDEX IF NOT EXISTS idx_agent_executions_status ON agent_executions(status);
CREATE INDEX IF NOT EXISTS idx_agent_executions_started_at ON agent_executions(started_at DESC);

-- Agent execution messages table (for execution-specific communication)
CREATE TABLE IF NOT EXISTS execution_messages (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    from_agent_id TEXT NOT NULL,
    to_agent_id TEXT, -- NULL means broadcast to all
    message_type TEXT NOT NULL, -- 'task_request', 'task_response', 'status_update', 'question', 'answer'
    content TEXT NOT NULL,
    metadata TEXT, -- JSON
    created TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (execution_id) REFERENCES agent_executions(id) ON DELETE CASCADE,
    FOREIGN KEY (from_agent_id) REFERENCES agents(id) ON DELETE CASCADE,
    FOREIGN KEY (to_agent_id) REFERENCES agents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_execution_messages_execution_id ON execution_messages(execution_id);
CREATE INDEX IF NOT EXISTS idx_execution_messages_from_agent ON execution_messages(from_agent_id);
CREATE INDEX IF NOT EXISTS idx_execution_messages_to_agent ON execution_messages(to_agent_id);
CREATE INDEX IF NOT EXISTS idx_execution_messages_created ON execution_messages(created DESC);

-- Workflow steps table (tracks each step in execution)
CREATE TABLE IF NOT EXISTS workflow_steps (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    step_number INTEGER NOT NULL,
    agent_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed'
    result TEXT, -- JSON with step results
    started_at TEXT,
    completed_at TEXT,
    created TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (execution_id) REFERENCES agent_executions(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_workflow_steps_execution_id ON workflow_steps(execution_id);
CREATE INDEX IF NOT EXISTS idx_workflow_steps_agent_id ON workflow_steps(agent_id);
CREATE INDEX IF NOT EXISTS idx_workflow_steps_step_number ON workflow_steps(execution_id, step_number);
CREATE INDEX IF NOT EXISTS idx_workflow_steps_status ON workflow_steps(status);
