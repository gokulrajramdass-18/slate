-- Migration: 034 - Agent Skills System
-- Description: Create tables for agent skills management and bindings
-- Date: 2026-04-02

-- ============================================================================
-- AGENT SKILLS TABLE
-- ============================================================================
-- Registry of reusable skills that agents can learn and execute

CREATE TABLE IF NOT EXISTS agent_skills (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,         -- 'data_analysis', 'web_research', 'code_generation', 'communication', 'planning', 'custom'
    description TEXT,
    skill_type TEXT NOT NULL,       -- 'tool_chain', 'prompt_template', 'workflow', 'custom'
    definition TEXT NOT NULL,       -- JSON: skill implementation (tool sequence, prompt, workflow graph, etc.)
    input_schema TEXT,              -- JSON: expected input parameters schema
    output_schema TEXT,             -- JSON: expected output format
    roles TEXT,                     -- JSON array: recommended roles for this skill
    tags TEXT,                      -- JSON array: searchable tags
    enabled INTEGER NOT NULL DEFAULT 1,
    metadata TEXT,                  -- JSON: version, author, cost_estimate, etc.
    created TEXT NOT NULL DEFAULT (datetime('now')),
    updated TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_agent_skills_category ON agent_skills(category);
CREATE INDEX IF NOT EXISTS idx_agent_skills_skill_type ON agent_skills(skill_type);
CREATE INDEX IF NOT EXISTS idx_agent_skills_enabled ON agent_skills(enabled);

-- ============================================================================
-- AGENT SKILL BINDINGS TABLE
-- ============================================================================
-- Maps skills to specific agents (from agents or standalone_agents) or agent roles

CREATE TABLE IF NOT EXISTS agent_skill_bindings (
    id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL,

    -- Target (exactly one must be set)
    agent_id TEXT,                  -- Can reference agents or standalone_agents
    standalone_agent_id TEXT,       -- Specific standalone agent
    role TEXT,                      -- Agent role (applies to all agents with this role)
    team_id TEXT,                   -- Team-level skill binding

    -- Binding type
    binding_type TEXT NOT NULL,     -- 'agent', 'standalone_agent', 'role', 'team'
    priority INTEGER DEFAULT 0,     -- Higher priority skills are suggested first

    -- Configuration
    config TEXT,                    -- JSON object for skill config overrides
    enabled INTEGER DEFAULT 1,

    -- Metadata
    created TEXT NOT NULL DEFAULT (datetime('now')),
    created_by TEXT,

    FOREIGN KEY (skill_id) REFERENCES agent_skills(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE,
    FOREIGN KEY (standalone_agent_id) REFERENCES standalone_agents(id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE,

    -- Constraint: exactly one target
    CHECK (
        (binding_type = 'agent' AND agent_id IS NOT NULL AND standalone_agent_id IS NULL AND role IS NULL AND team_id IS NULL) OR
        (binding_type = 'standalone_agent' AND standalone_agent_id IS NOT NULL AND agent_id IS NULL AND role IS NULL AND team_id IS NULL) OR
        (binding_type = 'role' AND role IS NOT NULL AND agent_id IS NULL AND standalone_agent_id IS NULL AND team_id IS NULL) OR
        (binding_type = 'team' AND team_id IS NOT NULL AND agent_id IS NULL AND standalone_agent_id IS NULL AND role IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_skill_bindings_agent ON agent_skill_bindings(agent_id);
CREATE INDEX IF NOT EXISTS idx_skill_bindings_standalone_agent ON agent_skill_bindings(standalone_agent_id);
CREATE INDEX IF NOT EXISTS idx_skill_bindings_role ON agent_skill_bindings(role);
CREATE INDEX IF NOT EXISTS idx_skill_bindings_team ON agent_skill_bindings(team_id);
CREATE INDEX IF NOT EXISTS idx_skill_bindings_skill ON agent_skill_bindings(skill_id);
CREATE INDEX IF NOT EXISTS idx_skill_bindings_enabled ON agent_skill_bindings(enabled);

-- ============================================================================
-- SKILL EXECUTIONS TABLE
-- ============================================================================
-- Tracks skill execution history for analytics and learning

CREATE TABLE IF NOT EXISTS agent_skill_executions (
    id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL,
    execution_id TEXT NOT NULL,     -- Unique ID for this execution

    -- Context
    agent_id TEXT,                  -- Which agent executed the skill
    team_id TEXT,                   -- Optional: if part of team execution

    -- Execution details
    input_data TEXT,                -- JSON: input parameters
    output_data TEXT,               -- JSON: execution results

    -- Result
    success INTEGER NOT NULL,
    result TEXT,                    -- JSON: structured result
    error TEXT,                     -- Error message if failed
    duration_ms REAL,               -- Execution duration in milliseconds

    -- Observability
    trace_id TEXT,                  -- For distributed tracing
    steps TEXT,                     -- JSON array: step-by-step execution log

    -- Timestamps
    started_at TEXT NOT NULL,
    ended_at TEXT,
    created TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (skill_id) REFERENCES agent_skills(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE SET NULL,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_skill_executions_skill ON agent_skill_executions(skill_id);
CREATE INDEX IF NOT EXISTS idx_skill_executions_agent ON agent_skill_executions(agent_id);
CREATE INDEX IF NOT EXISTS idx_skill_executions_team ON agent_skill_executions(team_id);
CREATE INDEX IF NOT EXISTS idx_skill_executions_started ON agent_skill_executions(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_skill_executions_success ON agent_skill_executions(success);

-- ============================================================================
-- NOTES
-- ============================================================================
-- Skill Types:
--   - tool_chain: Sequence of tool calls with data flow
--   - prompt_template: Reusable prompt with variable interpolation
--   - workflow: Multi-step workflow graph
--   - custom: Custom Python code or external integration
--
-- Binding Types:
--   - agent: Skill bound to specific agent instance (team agent)
--   - standalone_agent: Skill bound to standalone agent
--   - role: Skill bound to all agents with a specific role
--   - team: Skill bound to all agents in a specific team
--
-- The definition column stores the skill implementation as JSON:
--   - tool_chain: {"tools": [...], "flow": {...}}
--   - prompt_template: {"template": "...", "variables": [...]}
--   - workflow: {"nodes": [...], "edges": [...]}
--   - custom: {"module": "...", "function": "...", "config": {...}}
