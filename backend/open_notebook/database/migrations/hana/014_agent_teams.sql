-- Migration: 014 - Agent Teams (HANA)
-- Description: Schema for agent team coordination, inter-agent messaging, and task management
-- Date: 2026-03-25

-- ============================================================================
-- AGENT TEAMS TABLE
-- ============================================================================

CREATE TABLE agent_teams (
    id NVARCHAR(36) PRIMARY KEY,
    name NVARCHAR(255) NOT NULL,
    goal NCLOB,
    status NVARCHAR(20) NOT NULL DEFAULT 'pending',
    notebook_id NVARCHAR(36),
    session_id NVARCHAR(36),
    config NCLOB,
    result NCLOB,
    error NCLOB,
    started_at NVARCHAR(30),
    completed_at NVARCHAR(30),
    created NVARCHAR(30) NOT NULL,
    updated NVARCHAR(30) NOT NULL,
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE SET NULL,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE SET NULL
);

CREATE INDEX idx_agent_teams_status ON agent_teams(status);
CREATE INDEX idx_agent_teams_notebook ON agent_teams(notebook_id);
CREATE INDEX idx_agent_teams_session ON agent_teams(session_id);

-- ============================================================================
-- AGENT INSTANCES TABLE
-- ============================================================================

CREATE TABLE agent_instances (
    id NVARCHAR(36) PRIMARY KEY,
    team_id NVARCHAR(36) NOT NULL,
    role NVARCHAR(50) NOT NULL,
    name NVARCHAR(255) NOT NULL,
    status NVARCHAR(20) NOT NULL DEFAULT 'idle',
    model_name NVARCHAR(255),
    system_prompt NCLOB,
    config NCLOB,
    result NCLOB,
    error NCLOB,
    started_at NVARCHAR(30),
    completed_at NVARCHAR(30),
    created NVARCHAR(30) NOT NULL,
    updated NVARCHAR(30) NOT NULL,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE
);

CREATE INDEX idx_agent_instances_team ON agent_instances(team_id);
CREATE INDEX idx_agent_instances_role ON agent_instances(role);
CREATE INDEX idx_agent_instances_status ON agent_instances(status);

-- ============================================================================
-- AGENT MESSAGES TABLE
-- ============================================================================

CREATE TABLE agent_messages (
    id NVARCHAR(36) PRIMARY KEY,
    team_id NVARCHAR(36) NOT NULL,
    sender_id NVARCHAR(36) NOT NULL,
    recipient_id NVARCHAR(36),
    message_type NVARCHAR(30) NOT NULL DEFAULT 'chat',
    content NCLOB NOT NULL,
    metadata NCLOB,
    created NVARCHAR(30) NOT NULL,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE
);

CREATE INDEX idx_agent_messages_team ON agent_messages(team_id);
CREATE INDEX idx_agent_messages_sender ON agent_messages(sender_id);
CREATE INDEX idx_agent_messages_recipient ON agent_messages(recipient_id);
CREATE INDEX idx_agent_messages_created ON agent_messages(created);

-- ============================================================================
-- AGENT TASKS TABLE
-- ============================================================================

CREATE TABLE agent_tasks (
    id NVARCHAR(36) PRIMARY KEY,
    team_id NVARCHAR(36) NOT NULL,
    assignee_id NVARCHAR(36),
    title NVARCHAR(500) NOT NULL,
    description NCLOB,
    status NVARCHAR(20) NOT NULL DEFAULT 'pending',
    priority INTEGER NOT NULL DEFAULT 0,
    result NCLOB,
    error NCLOB,
    depends_on NCLOB,
    started_at NVARCHAR(30),
    completed_at NVARCHAR(30),
    created NVARCHAR(30) NOT NULL,
    updated NVARCHAR(30) NOT NULL,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE,
    FOREIGN KEY (assignee_id) REFERENCES agent_instances(id) ON DELETE SET NULL
);

CREATE INDEX idx_agent_tasks_team ON agent_tasks(team_id);
CREATE INDEX idx_agent_tasks_assignee ON agent_tasks(assignee_id);
CREATE INDEX idx_agent_tasks_status ON agent_tasks(status);
