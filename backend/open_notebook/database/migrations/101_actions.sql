-- Actions system migration
-- Description: Create tables for configurable actions with authentication, templates, and orchestration bindings
-- Date: 2026-04-16

-- ============================================================================
-- Main actions table - Global registry of reusable actions
-- ============================================================================
CREATE TABLE IF NOT EXISTS actions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,

    -- Action type
    action_type TEXT NOT NULL,  -- 'webhook', 'email', 'hana_operation', 'workflow_trigger'

    -- Connection details
    endpoint TEXT,  -- URL or table name or workflow ID
    method TEXT DEFAULT 'POST',  -- For webhooks

    -- Authentication (encrypted)
    auth_type TEXT,  -- 'none', 'basic', 'bearer', 'api_key', 'oauth2_client'
    auth_config_encrypted TEXT,  -- Encrypted JSON

    -- Headers and params (JSON)
    headers TEXT,
    query_params TEXT,

    -- Body template with placeholders (JSON)
    body_template TEXT,  -- e.g., {"result": "{{result}}", "status": "{{status}}"}

    -- Conditional execution
    condition_expression TEXT,  -- e.g., "status == 'completed' and result.confidence > 0.8"

    -- Retry policy (JSON)
    retry_policy TEXT,  -- e.g., {"max_retries": 3, "backoff": "exponential"}

    -- Status
    is_active INTEGER DEFAULT 1,

    -- Metadata
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_executed_at TEXT,
    execution_count INTEGER DEFAULT 0
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_actions_type ON actions(action_type);
CREATE INDEX IF NOT EXISTS idx_actions_active ON actions(is_active);
CREATE INDEX IF NOT EXISTS idx_actions_created_at ON actions(created_at DESC);

-- ============================================================================
-- Action executions table - Audit trail for all action executions
-- ============================================================================
CREATE TABLE IF NOT EXISTS action_executions (
    id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL,

    -- Context - what triggered this execution
    orchestration_id TEXT,  -- If triggered by orchestration
    chat_session_id TEXT,  -- If triggered by chat
    user_id TEXT NOT NULL,

    -- Execution details
    status TEXT NOT NULL,  -- 'pending', 'running', 'success', 'failed', 'skipped'
    trigger_event TEXT,  -- 'orchestration.completed', 'manual', 'chat.command', etc.

    -- Data
    input_data TEXT,  -- JSON: what was sent
    output_data TEXT,  -- JSON: response received
    error_message TEXT,

    -- Condition evaluation
    condition_met INTEGER,  -- 1 if condition passed, 0 if failed, NULL if no condition
    condition_details TEXT,  -- JSON: variables used in evaluation

    -- Performance metrics
    execution_time_ms INTEGER,
    retry_count INTEGER DEFAULT 0,

    -- Timestamps
    created_at TEXT NOT NULL,
    completed_at TEXT,

    -- Foreign keys
    FOREIGN KEY (action_id) REFERENCES actions(id) ON DELETE CASCADE,
    FOREIGN KEY (orchestration_id) REFERENCES orchestrations(id) ON DELETE SET NULL,
    FOREIGN KEY (chat_session_id) REFERENCES chat_sessions(id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_action_executions_action_id ON action_executions(action_id);
CREATE INDEX IF NOT EXISTS idx_action_executions_orchestration_id ON action_executions(orchestration_id);
CREATE INDEX IF NOT EXISTS idx_action_executions_chat_session_id ON action_executions(chat_session_id);
CREATE INDEX IF NOT EXISTS idx_action_executions_user_id ON action_executions(user_id);
CREATE INDEX IF NOT EXISTS idx_action_executions_status ON action_executions(status);
CREATE INDEX IF NOT EXISTS idx_action_executions_created_at ON action_executions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_action_executions_trigger_event ON action_executions(trigger_event);

-- ============================================================================
-- Orchestration action bindings - Link actions to orchestrations
-- ============================================================================
CREATE TABLE IF NOT EXISTS orchestration_action_bindings (
    id TEXT PRIMARY KEY,

    -- Either schedule_id (recurring) or orchestration_id (one-time)
    schedule_id TEXT,  -- For recurring scheduled orchestrations
    orchestration_id TEXT,  -- For one-time orchestration bindings

    action_id TEXT NOT NULL,

    -- Trigger configuration
    trigger_condition TEXT NOT NULL,  -- 'on_start', 'on_completion', 'on_failure', 'on_phase_change', 'always'
    phase_filter TEXT,  -- JSON array: ["planning", "execution"] or NULL for all phases

    -- Order of execution (if multiple actions bound)
    execution_order INTEGER DEFAULT 0,

    -- Status
    is_active INTEGER DEFAULT 1,

    -- Metadata
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    -- Foreign keys
    FOREIGN KEY (schedule_id) REFERENCES orchestration_schedules(id) ON DELETE CASCADE,
    FOREIGN KEY (orchestration_id) REFERENCES orchestrations(id) ON DELETE CASCADE,
    FOREIGN KEY (action_id) REFERENCES actions(id) ON DELETE CASCADE,

    -- Constraint: must have either schedule_id or orchestration_id, not both
    CHECK (
        (schedule_id IS NOT NULL AND orchestration_id IS NULL) OR
        (schedule_id IS NULL AND orchestration_id IS NOT NULL)
    )
);

-- Indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_orchestration_action_bindings_schedule ON orchestration_action_bindings(schedule_id);
CREATE INDEX IF NOT EXISTS idx_orchestration_action_bindings_orchestration ON orchestration_action_bindings(orchestration_id);
CREATE INDEX IF NOT EXISTS idx_orchestration_action_bindings_action ON orchestration_action_bindings(action_id);
CREATE INDEX IF NOT EXISTS idx_orchestration_action_bindings_trigger ON orchestration_action_bindings(trigger_condition);
CREATE INDEX IF NOT EXISTS idx_orchestration_action_bindings_active ON orchestration_action_bindings(is_active);
