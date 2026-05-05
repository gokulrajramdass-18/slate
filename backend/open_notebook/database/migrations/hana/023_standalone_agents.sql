-- Migration: 023 - Standalone Agents (HANA version)
-- Description: Schema for standalone agent configurations (individual agents not part of a team)
-- Date: 2026-03-27

-- ============================================================================
-- STANDALONE AGENTS TABLE
-- ============================================================================
-- Individual agent configurations with their own tools, MCP servers, and data sources

CREATE TABLE standalone_agents (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description NCLOB,
    role VARCHAR(50) NOT NULL,           -- planner, researcher, analyst, synthesizer, custom
    system_prompt NCLOB,
    model_name VARCHAR(100),             -- LLM model override
    notebook_id VARCHAR(36),             -- Optional linked notebook

    -- Configuration
    config NCLOB,                        -- JSON: agent-specific settings

    -- Tools and capabilities
    tool_ids NCLOB,                      -- JSON array of tool IDs from tool registry
    mcp_server_ids NCLOB,                -- JSON array of MCP server IDs
    data_source_ids NCLOB,               -- JSON array of source IDs (from sources table)

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'active',  -- active, inactive, archived

    -- Metadata
    created TIMESTAMP NOT NULL,
    updated TIMESTAMP NOT NULL,
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE SET NULL
);

CREATE INDEX idx_standalone_agents_role ON standalone_agents(role);
CREATE INDEX idx_standalone_agents_status ON standalone_agents(status);
CREATE INDEX idx_standalone_agents_notebook ON standalone_agents(notebook_id);

-- ============================================================================
-- STANDALONE AGENT EXECUTIONS TABLE
-- ============================================================================
-- Execution history for standalone agents

CREATE TABLE standalone_agent_executions (
    id VARCHAR(36) PRIMARY KEY,
    agent_id VARCHAR(36) NOT NULL,
    query NCLOB NOT NULL,                -- User query/prompt
    status VARCHAR(20) NOT NULL DEFAULT 'running',  -- running, completed, failed, cancelled

    -- Execution context
    session_id VARCHAR(36),              -- Optional chat session link
    notebook_id VARCHAR(36),             -- Snapshot of notebook at execution time
    context NCLOB,                       -- JSON: execution context (sources used, etc.)

    -- Results
    result NCLOB,                        -- JSON: agent output
    error NCLOB,
    steps NCLOB,                         -- JSON array: execution steps for visibility
    tool_calls NCLOB,                    -- JSON array: tools invoked during execution

    -- Timing
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INTEGER,

    -- Metadata
    created TIMESTAMP NOT NULL,
    updated TIMESTAMP NOT NULL,
    FOREIGN KEY (agent_id) REFERENCES standalone_agents(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE SET NULL,
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE SET NULL
);

CREATE INDEX idx_standalone_executions_agent ON standalone_agent_executions(agent_id);
CREATE INDEX idx_standalone_executions_status ON standalone_agent_executions(status);
CREATE INDEX idx_standalone_executions_session ON standalone_agent_executions(session_id);
CREATE INDEX idx_standalone_executions_created ON standalone_agent_executions(created);

-- ============================================================================
-- NOTES
-- ============================================================================
-- tool_ids, mcp_server_ids, data_source_ids store JSON arrays of UUIDs
-- config stores JSON-encoded configuration
-- steps and tool_calls store JSON arrays for execution tracing
