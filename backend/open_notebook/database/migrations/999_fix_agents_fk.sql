-- Fix foreign key references from 'agents' (non-existent) to 'agent_instances'
-- This fixes the "no such table: main.agents" error when deleting agent teams

-- SQLite doesn't support modifying foreign keys directly, so we need to recreate tables

PRAGMA foreign_keys=OFF;

-- Backup and recreate execution_messages
CREATE TABLE execution_messages_new (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    from_agent_id TEXT NOT NULL,
    to_agent_id TEXT,
    message_type TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT,
    created TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (execution_id) REFERENCES agent_executions(id) ON DELETE CASCADE,
    FOREIGN KEY (from_agent_id) REFERENCES agent_instances(id) ON DELETE CASCADE,
    FOREIGN KEY (to_agent_id) REFERENCES agent_instances(id) ON DELETE CASCADE
);

INSERT INTO execution_messages_new SELECT * FROM execution_messages;
DROP TABLE execution_messages;
ALTER TABLE execution_messages_new RENAME TO execution_messages;

-- Backup and recreate workflow_steps
CREATE TABLE workflow_steps_new (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    step_number INTEGER NOT NULL,
    agent_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    result TEXT,
    started_at TEXT,
    completed_at TEXT,
    created TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (execution_id) REFERENCES agent_executions(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES agent_instances(id) ON DELETE CASCADE
);

INSERT INTO workflow_steps_new SELECT * FROM workflow_steps;
DROP TABLE workflow_steps;
ALTER TABLE workflow_steps_new RENAME TO workflow_steps;

-- Backup and recreate agent_skill_bindings
CREATE TABLE agent_skill_bindings_new (
    id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL,
    agent_id TEXT,
    standalone_agent_id TEXT,
    role TEXT,
    team_id TEXT,
    binding_type TEXT NOT NULL,
    priority INTEGER DEFAULT 0,
    config TEXT,
    enabled INTEGER DEFAULT 1,
    created TEXT NOT NULL DEFAULT (datetime('now')),
    created_by TEXT,

    FOREIGN KEY (skill_id) REFERENCES agent_skills(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES agent_instances(id) ON DELETE CASCADE,
    FOREIGN KEY (standalone_agent_id) REFERENCES standalone_agents(id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE,

    CHECK (
        (binding_type = 'agent' AND agent_id IS NOT NULL AND standalone_agent_id IS NULL AND role IS NULL AND team_id IS NULL) OR
        (binding_type = 'standalone_agent' AND standalone_agent_id IS NOT NULL AND agent_id IS NULL AND role IS NULL AND team_id IS NULL) OR
        (binding_type = 'role' AND role IS NOT NULL AND agent_id IS NULL AND standalone_agent_id IS NULL AND team_id IS NULL) OR
        (binding_type = 'team' AND team_id IS NOT NULL AND agent_id IS NULL AND standalone_agent_id IS NULL AND role IS NULL)
    )
);

INSERT INTO agent_skill_bindings_new SELECT * FROM agent_skill_bindings;
DROP TABLE agent_skill_bindings;
ALTER TABLE agent_skill_bindings_new RENAME TO agent_skill_bindings;

-- Backup and recreate agent_skill_executions
CREATE TABLE agent_skill_executions_new (
    id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL,
    execution_id TEXT NOT NULL,
    agent_id TEXT,
    team_id TEXT,
    input_data TEXT,
    output_data TEXT,
    success INTEGER NOT NULL,
    result TEXT,
    error TEXT,
    duration_ms REAL,
    trace_id TEXT,
    steps TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    created TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (skill_id) REFERENCES agent_skills(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES agent_instances(id) ON DELETE SET NULL,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE SET NULL
);

INSERT INTO agent_skill_executions_new SELECT * FROM agent_skill_executions;
DROP TABLE agent_skill_executions;
ALTER TABLE agent_skill_executions_new RENAME TO agent_skill_executions;

PRAGMA foreign_keys=ON;
