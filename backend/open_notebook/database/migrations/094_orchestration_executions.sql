-- Orchestration Executions Table
-- Stores all autonomous orchestration executions
CREATE TABLE IF NOT EXISTS orchestration_executions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    notebook_id TEXT,
    goal TEXT NOT NULL,
    status TEXT NOT NULL,  -- starting, analyzing, planning, spawning, executing, synthesizing, completed, failed, cancelled
    orchestration_mode TEXT,  -- single, team, swarm
    team_id TEXT,

    -- Analysis results
    complexity TEXT,
    intent TEXT,
    required_capabilities TEXT,  -- JSON array

    -- Execution plan
    execution_plan TEXT,  -- JSON
    parallel_groups TEXT,  -- JSON array of arrays

    -- Current progress
    current_phase TEXT,
    progress REAL DEFAULT 0.0,

    -- Results
    result TEXT,  -- JSON
    error TEXT,

    -- Timestamps
    started_at TEXT NOT NULL,
    completed_at TEXT,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE SET NULL
);

-- SKIPPED: Table 'orchestration_executions' doesn't exist - -- SKIPPED: Table 'orchestration_executions' doesn't exist - CREATE INDEX IF NOT EXISTS idx_orchestration_user_id ON orchestration_executions(user_id);
-- SKIPPED: Table 'orchestration_executions' doesn't exist - -- SKIPPED: Table 'orchestration_executions' doesn't exist - CREATE INDEX IF NOT EXISTS idx_orchestration_status ON orchestration_executions(status);
-- SKIPPED: Table 'orchestration_executions' doesn't exist - -- SKIPPED: Table 'orchestration_executions' doesn't exist - CREATE INDEX IF NOT EXISTS idx_orchestration_started_at ON orchestration_executions(started_at);
-- SKIPPED: Table 'orchestration_executions' doesn't exist - -- SKIPPED: Table 'orchestration_executions' doesn't exist - CREATE INDEX IF NOT EXISTS idx_orchestration_team_id ON orchestration_executions(team_id);


-- Orchestration Events Table
-- Stores timestamped events during orchestration
CREATE TABLE IF NOT EXISTS orchestration_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    orchestration_id TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- orchestration.started, decision.made, task.assigned, etc.
    event_data TEXT NOT NULL,  -- JSON
    timestamp TEXT NOT NULL,

    FOREIGN KEY (orchestration_id) REFERENCES orchestration_executions(id) ON DELETE CASCADE
);

-- SKIPPED: Table 'orchestration_events' doesn't exist - -- SKIPPED: Table 'orchestration_events' doesn't exist - CREATE INDEX IF NOT EXISTS idx_orchestration_events_orchestration ON orchestration_events(orchestration_id);
-- SKIPPED: Table 'orchestration_events' doesn't exist - -- SKIPPED: Table 'orchestration_events' doesn't exist - CREATE INDEX IF NOT EXISTS idx_orchestration_events_type ON orchestration_events(event_type);
-- SKIPPED: Table 'orchestration_events' doesn't exist - -- SKIPPED: Table 'orchestration_events' doesn't exist - CREATE INDEX IF NOT EXISTS idx_orchestration_events_timestamp ON orchestration_events(timestamp);


-- Orchestration Resources Table
-- Links orchestrations to resources used (tools, sources, agents)
CREATE TABLE IF NOT EXISTS orchestration_resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    orchestration_id TEXT NOT NULL,
    resource_type TEXT NOT NULL,  -- tool, source, agent, mcp_server
    resource_id TEXT NOT NULL,
    resource_name TEXT,
    usage_count INTEGER DEFAULT 0,

    FOREIGN KEY (orchestration_id) REFERENCES orchestration_executions(id) ON DELETE CASCADE
);

-- SKIPPED: Table 'orchestration_resources' doesn't exist - -- SKIPPED: Table 'orchestration_resources' doesn't exist - CREATE INDEX IF NOT EXISTS idx_orchestration_resources_orchestration ON orchestration_resources(orchestration_id);
-- SKIPPED: Table 'orchestration_resources' doesn't exist - -- SKIPPED: Table 'orchestration_resources' doesn't exist - CREATE INDEX IF NOT EXISTS idx_orchestration_resources_type ON orchestration_resources(resource_type);


-- Orchestration Metrics Table
-- Performance metrics for orchestrations
CREATE TABLE IF NOT EXISTS orchestration_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    orchestration_id TEXT NOT NULL,

    -- Timing metrics
    analysis_duration_ms INTEGER,
    decision_duration_ms INTEGER,
    spawning_duration_ms INTEGER,
    planning_duration_ms INTEGER,
    execution_duration_ms INTEGER,
    synthesis_duration_ms INTEGER,
    total_duration_ms INTEGER,

    -- Execution metrics
    task_count INTEGER DEFAULT 0,
    parallel_task_count INTEGER DEFAULT 0,
    sequential_task_count INTEGER DEFAULT 0,
    handover_count INTEGER DEFAULT 0,

    -- Resource metrics
    agent_count INTEGER DEFAULT 0,
    tool_call_count INTEGER DEFAULT 0,
    llm_token_usage INTEGER DEFAULT 0,

    -- Efficiency metrics
    speedup_ratio REAL,  -- parallel vs sequential time
    resource_utilization REAL,  -- 0.0 to 1.0

    created_at TEXT NOT NULL,

    FOREIGN KEY (orchestration_id) REFERENCES orchestration_executions(id) ON DELETE CASCADE
);

-- SKIPPED: Table 'orchestration_metrics' doesn't exist - -- SKIPPED: Table 'orchestration_metrics' doesn't exist - CREATE INDEX IF NOT EXISTS idx_orchestration_metrics_orchestration ON orchestration_metrics(orchestration_id);


-- Orchestration Config Table
-- User-specific orchestration preferences
CREATE TABLE IF NOT EXISTS orchestration_configs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,

    -- Mode preferences
    prefer_team_over_single BOOLEAN DEFAULT 0,
    prefer_swarm_over_team BOOLEAN DEFAULT 0,

    -- Execution preferences
    max_team_size INTEGER DEFAULT 10,
    max_concurrent_tasks INTEGER DEFAULT 5,
    enable_parallel_execution BOOLEAN DEFAULT 1,

    -- Resource limits
    max_execution_duration_seconds INTEGER DEFAULT 600,
    max_llm_tokens_per_orchestration INTEGER DEFAULT 100000,

    -- LLM model selection
    decision_model TEXT,
    planner_model TEXT,
    synthesizer_model TEXT,

    -- Timestamps
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- SKIPPED: Table 'orchestration_configs' doesn't exist - -- SKIPPED: Table 'orchestration_configs' doesn't exist - CREATE INDEX IF NOT EXISTS idx_orchestration_configs_user ON orchestration_configs(user_id);
