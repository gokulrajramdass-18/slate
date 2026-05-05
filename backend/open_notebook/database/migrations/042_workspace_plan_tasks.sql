-- Migration: 042_workspace_plan_tasks.sql
-- Description: Create table for individual tasks within workspace plans
-- Date: 2026-04-04

CREATE TABLE IF NOT EXISTS workspace_plan_tasks (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES workspace_plans(id) ON DELETE CASCADE,
    phase_name TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    assigned_agent_id TEXT,     -- References standalone_agents or agent teams
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'in_progress', 'completed', 'failed', 'skipped')),
    estimated_duration INTEGER, -- Minutes
    actual_duration INTEGER,    -- Minutes
    dependencies TEXT,          -- JSON: array of task IDs that must complete first
    required_tools TEXT,        -- JSON: array of tool IDs needed
    required_sources TEXT,      -- JSON: array of source IDs needed
    result TEXT,                -- JSON: task output/result
    error TEXT,                 -- Error message if failed
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_plan_tasks_plan_id ON workspace_plan_tasks(plan_id);
CREATE INDEX IF NOT EXISTS idx_plan_tasks_status ON workspace_plan_tasks(status);
CREATE INDEX IF NOT EXISTS idx_plan_tasks_assigned_agent ON workspace_plan_tasks(assigned_agent_id);
CREATE INDEX IF NOT EXISTS idx_plan_tasks_phase ON workspace_plan_tasks(phase_name);

