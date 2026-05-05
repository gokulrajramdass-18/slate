-- Migration: 060 - Agent Judge Evaluations
-- Description: Schema for judge agent evaluations of team execution results
-- Date: 2026-04-22

-- ============================================================================
-- AGENT EVALUATION CONFIGS TABLE
-- ============================================================================
-- Team-level configuration for judge evaluations

CREATE TABLE IF NOT EXISTS agent_evaluation_configs (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL UNIQUE,
    enabled BOOLEAN NOT NULL DEFAULT 1,
    auto_evaluate BOOLEAN NOT NULL DEFAULT 1,
    scope TEXT NOT NULL DEFAULT 'all',  -- 'final_only', 'agents_only', 'all'
    scoring_scale TEXT NOT NULL DEFAULT '0-10',
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_eval_configs_team ON agent_evaluation_configs(team_id);

-- ============================================================================
-- AGENT EXECUTION EVALUATIONS TABLE
-- ============================================================================
-- Individual evaluation results from judge agents

CREATE TABLE IF NOT EXISTS agent_execution_evaluations (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    team_id TEXT NOT NULL,
    judge_agent_id TEXT,
    scope TEXT NOT NULL,  -- 'final_result', 'agent_output'
    target_agent_id TEXT,  -- NULL if evaluating final result
    overall_score REAL,  -- 0-10 score
    criteria_scores TEXT,  -- JSON: {"accuracy": 9, "completeness": 8, "quality": 9, "consistency": 8}
    feedback TEXT,
    approval_status TEXT,  -- 'approved', 'needs_revision', 'requires_rework'
    confidence REAL,  -- 0.0-1.0
    created TEXT NOT NULL,
    FOREIGN KEY (execution_id) REFERENCES agent_executions(id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE,
    FOREIGN KEY (judge_agent_id) REFERENCES agent_instances(id) ON DELETE SET NULL,
    FOREIGN KEY (target_agent_id) REFERENCES agent_instances(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_exec_evals_execution ON agent_execution_evaluations(execution_id);
CREATE INDEX IF NOT EXISTS idx_exec_evals_team ON agent_execution_evaluations(team_id);
CREATE INDEX IF NOT EXISTS idx_exec_evals_judge ON agent_execution_evaluations(judge_agent_id);
CREATE INDEX IF NOT EXISTS idx_exec_evals_target ON agent_execution_evaluations(target_agent_id);

-- ============================================================================
-- NOTES
-- ============================================================================
-- criteria_scores stores JSON-encoded scoring breakdown
-- auto_evaluate: TRUE for orchestrator-created teams, user-controlled for UI teams
-- scope determines what gets evaluated (final only, agents only, or all)
