-- Migration: 035 - A2A Protocol Integration
-- Description: Enable Agent-to-Agent (A2A) protocol support for local and remote agents
-- Date: 2026-04-11

-- ============================================================================
-- A2A REMOTE AGENT REGISTRY
-- ============================================================================
-- Stores remote A2A agents that have been discovered and imported

CREATE TABLE IF NOT EXISTS a2a_agent_registry (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    card_url TEXT NOT NULL UNIQUE,
    agent_card TEXT NOT NULL,          -- JSON: Full AgentCard from A2A protocol
    transport TEXT DEFAULT 'JSONRPC',  -- JSONRPC, GRPC, HTTP+JSON
    endpoint_url TEXT NOT NULL,
    security_schemes TEXT,             -- JSON: Authentication requirements
    available_skills TEXT,             -- JSON array: List of skill IDs from remote agent
    last_synced TEXT,                  -- Last time AgentCard was refreshed
    enabled INTEGER NOT NULL DEFAULT 1,
    metadata TEXT,                     -- JSON: Stats like latency, success_rate, version
    created TEXT NOT NULL DEFAULT (datetime('now')),
    updated TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_a2a_agents_enabled ON a2a_agent_registry(enabled);
CREATE INDEX IF NOT EXISTS idx_a2a_agents_last_synced ON a2a_agent_registry(last_synced);
CREATE INDEX IF NOT EXISTS idx_a2a_agents_card_url ON a2a_agent_registry(card_url);

-- ============================================================================
-- A2A TASK STORE
-- ============================================================================
-- Tracks A2A task executions (both outgoing to remote agents and incoming from clients)

CREATE TABLE IF NOT EXISTS a2a_task_store (
    id TEXT PRIMARY KEY,               -- A2A task ID (UUID)
    context_id TEXT NOT NULL,          -- Conversation/session context ID
    agent_id TEXT,                     -- Remote agent ID (if outgoing) or NULL (if incoming)
    skill_id TEXT,                     -- Skill being executed
    kind TEXT DEFAULT 'task',          -- task, session, etc.
    direction TEXT NOT NULL,           -- 'outgoing' (to remote) or 'incoming' (from remote)

    -- A2A TaskStatus fields
    state TEXT NOT NULL,               -- queued, running, auth-required, completed, canceled, rejected, failed
    progress REAL,                     -- 0.0 to 1.0
    message TEXT,                      -- Status message

    -- Content
    history TEXT,                      -- JSON: Array of Message objects (A2A format)
    artifacts TEXT,                    -- JSON: Array of Artifact objects (A2A format)
    task_metadata TEXT,                -- JSON: Task-specific metadata

    -- Tracking
    started_at TEXT,
    completed_at TEXT,
    created TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_a2a_tasks_context ON a2a_task_store(context_id);
CREATE INDEX IF NOT EXISTS idx_a2a_tasks_agent ON a2a_task_store(agent_id);
CREATE INDEX IF NOT EXISTS idx_a2a_tasks_skill ON a2a_task_store(skill_id);
CREATE INDEX IF NOT EXISTS idx_a2a_tasks_state ON a2a_task_store(state);
CREATE INDEX IF NOT EXISTS idx_a2a_tasks_direction ON a2a_task_store(direction);
CREATE INDEX IF NOT EXISTS idx_a2a_tasks_started ON a2a_task_store(started_at DESC);

-- ============================================================================
-- A2A AGENT CREDENTIALS
-- ============================================================================
-- Stores encrypted credentials for authenticated remote A2A agents

CREATE TABLE IF NOT EXISTS a2a_agent_credentials (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL UNIQUE,
    credential_type TEXT NOT NULL,     -- 'apiKey', 'bearer', 'oauth2', 'basic'
    credential_data TEXT NOT NULL,     -- JSON: Encrypted credential details
    expires_at TEXT,                   -- For OAuth tokens with expiry
    created TEXT NOT NULL DEFAULT (datetime('now')),
    updated TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (agent_id) REFERENCES a2a_agent_registry(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_a2a_creds_agent ON a2a_agent_credentials(agent_id);
CREATE INDEX IF NOT EXISTS idx_a2a_creds_type ON a2a_agent_credentials(credential_type);

-- ============================================================================
-- A2A SKILL MAPPINGS
-- ============================================================================
-- Maps remote A2A agent skills to local agent_skills registry

CREATE TABLE IF NOT EXISTS a2a_skill_mappings (
    id TEXT PRIMARY KEY,
    remote_agent_id TEXT NOT NULL,
    remote_skill_id TEXT NOT NULL,     -- Skill ID from remote AgentCard
    local_skill_id TEXT NOT NULL,      -- Generated local skill ID (a2a:{agent_id}:{skill_id})
    skill_name TEXT NOT NULL,
    skill_description TEXT,
    skill_tags TEXT,                   -- JSON array
    input_modes TEXT,                  -- JSON array of MIME types
    output_modes TEXT,                 -- JSON array of MIME types
    enabled INTEGER NOT NULL DEFAULT 1,
    created TEXT NOT NULL DEFAULT (datetime('now')),
    updated TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (remote_agent_id) REFERENCES a2a_agent_registry(id) ON DELETE CASCADE,
    FOREIGN KEY (local_skill_id) REFERENCES agent_skills(id) ON DELETE CASCADE,

    UNIQUE(remote_agent_id, remote_skill_id)
);

CREATE INDEX IF NOT EXISTS idx_a2a_mappings_remote_agent ON a2a_skill_mappings(remote_agent_id);
CREATE INDEX IF NOT EXISTS idx_a2a_mappings_local_skill ON a2a_skill_mappings(local_skill_id);
CREATE INDEX IF NOT EXISTS idx_a2a_mappings_enabled ON a2a_skill_mappings(enabled);

-- ============================================================================
-- A2A EXECUTION METRICS
-- ============================================================================
-- Tracks performance and reliability metrics for remote A2A agents

CREATE TABLE IF NOT EXISTS a2a_execution_metrics (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    skill_id TEXT,
    task_id TEXT NOT NULL,

    -- Performance
    latency_ms REAL,                   -- Total execution time
    network_latency_ms REAL,           -- Network round-trip time

    -- Result
    success INTEGER NOT NULL,
    error_type TEXT,                   -- timeout, network, auth, validation, server_error
    error_message TEXT,

    -- Context
    retry_count INTEGER DEFAULT 0,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (agent_id) REFERENCES a2a_agent_registry(id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES a2a_task_store(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_a2a_metrics_agent ON a2a_execution_metrics(agent_id);
CREATE INDEX IF NOT EXISTS idx_a2a_metrics_timestamp ON a2a_execution_metrics(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_a2a_metrics_success ON a2a_execution_metrics(success);

-- ============================================================================
-- NOTES
-- ============================================================================
-- Transport Types:
--   - JSONRPC: JSON-RPC 2.0 over HTTP (default, most common)
--   - GRPC: gRPC protocol (high performance)
--   - HTTP+JSON: RESTful HTTP with JSON (streaming via SSE)
--
-- Task States (from A2A spec):
--   - queued: Task created, waiting to start
--   - running: Task is executing
--   - auth-required: Waiting for user authentication
--   - completed: Task finished successfully
--   - canceled: Task was canceled by user/system
--   - rejected: Task was rejected by agent
--   - failed: Task failed with error
--
-- Direction:
--   - outgoing: This system calling remote A2A agent
--   - incoming: Remote system calling this system via A2A
--
-- Credential Types:
--   - apiKey: API key in header/query/cookie
--   - bearer: Bearer token in Authorization header
--   - oauth2: OAuth 2.0 flow (stores access/refresh tokens)
--   - basic: HTTP Basic authentication
