-- Migration: 023 - Standalone Agents
-- Description: Schema for standalone agent configurations (individual agents not part of a team)
-- Date: 2026-03-27

-- ============================================================================
-- STANDALONE AGENTS TABLE
-- ============================================================================
-- Individual agent configurations with their own tools, MCP servers, and data sources

CREATE TABLE IF NOT EXISTS standalone_agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    role TEXT NOT NULL,           -- planner, researcher, analyst, synthesizer, custom
    system_prompt TEXT,
    model_name TEXT,              -- LLM model override
    notebook_id TEXT,             -- Optional linked notebook

    -- Configuration
    config TEXT,                  -- JSON: agent-specific settings

    -- Tools and capabilities
    tool_ids TEXT,                -- JSON array of tool IDs from tool registry
    mcp_server_ids TEXT,          -- JSON array of MCP server IDs
    data_source_ids TEXT,         -- JSON array of source IDs (from sources table)

    -- Status
    status TEXT NOT NULL DEFAULT 'active',  -- active, inactive, archived

    -- Ownership (from migration 056 - moved here to fix ordering)
    created_by VARCHAR(36),
    updated_by VARCHAR(36),

    -- Metadata
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_standalone_agents_role ON standalone_agents(role);
CREATE INDEX IF NOT EXISTS idx_standalone_agents_status ON standalone_agents(status);
CREATE INDEX IF NOT EXISTS idx_standalone_agents_notebook ON standalone_agents(notebook_id);

-- ============================================================================
-- STANDALONE AGENT EXECUTIONS TABLE
-- ============================================================================
-- Execution history for standalone agents

CREATE TABLE IF NOT EXISTS standalone_agent_executions (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    query TEXT NOT NULL,          -- User query/prompt
    status TEXT NOT NULL DEFAULT 'running',  -- running, completed, failed, cancelled

    -- Execution context
    session_id TEXT,              -- Optional chat session link
    notebook_id TEXT,             -- Snapshot of notebook at execution time
    context TEXT,                 -- JSON: execution context (sources used, etc.)

    -- Results
    result TEXT,                  -- JSON: agent output
    error TEXT,
    steps TEXT,                   -- JSON array: execution steps for visibility
    tool_calls TEXT,              -- JSON array: tools invoked during execution

    -- Timing
    started_at TEXT,
    completed_at TEXT,
    duration_ms INTEGER,

    -- Metadata
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (agent_id) REFERENCES standalone_agents(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE SET NULL,
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_standalone_executions_agent ON standalone_agent_executions(agent_id);
CREATE INDEX IF NOT EXISTS idx_standalone_executions_status ON standalone_agent_executions(status);
CREATE INDEX IF NOT EXISTS idx_standalone_executions_session ON standalone_agent_executions(session_id);
CREATE INDEX IF NOT EXISTS idx_standalone_executions_created ON standalone_agent_executions(created);

-- ============================================================================
-- NOTES
-- ============================================================================
-- tool_ids, mcp_server_ids, data_source_ids store JSON arrays of UUIDs
-- config stores JSON-encoded configuration
-- steps and tool_calls store JSON arrays for execution tracing

CREATE INDEX IF NOT EXISTS idx_standalone_agents_created_by ON standalone_agents(created_by);
