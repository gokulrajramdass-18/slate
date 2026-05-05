-- Migration 021: Visual Workflow Graphs System
-- Creates tables for visual workflow definitions, executions, and schedules

-- Workflows table - Stores workflow definitions with visual graph structure
CREATE TABLE IF NOT EXISTS workflows (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    graph_json TEXT NOT NULL,  -- JSON serialized WorkflowGraph (nodes, edges, entry_node_id)
    created_by VARCHAR(36),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    tags TEXT  -- JSON array of tags
);

-- Index for faster workflow lookups
CREATE INDEX IF NOT EXISTS idx_workflows_created_by ON workflows(created_by);
CREATE INDEX IF NOT EXISTS idx_workflows_is_active ON workflows(is_active);
CREATE INDEX IF NOT EXISTS idx_workflows_updated_at ON workflows(updated_at DESC);

-- Workflow executions table - Tracks workflow execution instances
CREATE TABLE IF NOT EXISTS workflow_executions (
    id VARCHAR(36) PRIMARY KEY,
    workflow_id VARCHAR(36) NOT NULL,
    status VARCHAR(20) NOT NULL,  -- pending, running, completed, failed, cancelled
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    node_states TEXT,  -- JSON serialized Dict[node_id, NodeExecutionState]
    final_output TEXT,  -- JSON serialized final result
    error TEXT,  -- Error message if failed
    triggered_by VARCHAR(20),  -- manual, cron, event, dependency
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
);

-- Indexes for execution queries
CREATE INDEX IF NOT EXISTS idx_workflow_executions_workflow_id ON workflow_executions(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_status ON workflow_executions(status);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_started_at ON workflow_executions(started_at DESC);

-- Workflow schedules table - Defines when workflows should run
CREATE TABLE IF NOT EXISTS workflow_schedules (
    id VARCHAR(36) PRIMARY KEY,
    workflow_id VARCHAR(36) NOT NULL,
    schedule_type VARCHAR(20) NOT NULL,  -- cron, event, dependency, manual
    cron_expression VARCHAR(100),  -- For cron schedules
    event_trigger TEXT,  -- JSON serialized EventTrigger for event-driven schedules
    upstream_workflow_id VARCHAR(36),  -- For dependency chain schedules
    enabled BOOLEAN DEFAULT TRUE,
    last_run_at TIMESTAMP,
    next_run_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE,
    FOREIGN KEY (upstream_workflow_id) REFERENCES workflows(id) ON DELETE SET NULL
);

-- Indexes for schedule queries
CREATE INDEX IF NOT EXISTS idx_workflow_schedules_workflow_id ON workflow_schedules(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_schedules_enabled ON workflow_schedules(enabled);
CREATE INDEX IF NOT EXISTS idx_workflow_schedules_next_run_at ON workflow_schedules(next_run_at);
CREATE INDEX IF NOT EXISTS idx_workflow_schedules_type ON workflow_schedules(schedule_type);
