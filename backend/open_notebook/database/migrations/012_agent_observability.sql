-- Migration: 012 - Agent Observability
-- Description: Add agent steps tracking and Langfuse tracing integration
-- Date: 2026-03-25

-- ============================================================================
-- ALTER CHAT_MESSAGES TABLE
-- ============================================================================
-- Add columns for agent step tracking and Langfuse trace correlation

ALTER TABLE chat_messages ADD COLUMN agent_steps TEXT;
ALTER TABLE chat_messages ADD COLUMN langfuse_trace_id TEXT;
ALTER TABLE chat_messages ADD COLUMN langfuse_observation_id TEXT;

-- Create index for querying messages by trace ID
CREATE INDEX IF NOT EXISTS idx_chat_messages_trace ON chat_messages(langfuse_trace_id);

-- ============================================================================
-- AGENT EXECUTION TRACES TABLE (Analytics)
-- ============================================================================
-- Optional table for storing aggregate trace metadata and analytics

CREATE TABLE IF NOT EXISTS agent_execution_traces (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    langfuse_trace_id TEXT,
    model_used TEXT,
    total_tokens INTEGER,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_cost REAL,
    duration_ms INTEGER,
    tool_calls_count INTEGER,
    error_occurred BOOLEAN DEFAULT 0,
    created TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (message_id) REFERENCES chat_messages(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_traces_session ON agent_execution_traces(session_id);
CREATE INDEX IF NOT EXISTS idx_traces_created ON agent_execution_traces(created);
CREATE INDEX IF NOT EXISTS idx_traces_langfuse ON agent_execution_traces(langfuse_trace_id);
CREATE INDEX IF NOT EXISTS idx_traces_model ON agent_execution_traces(model_used);

-- ============================================================================
-- NOTES
-- ============================================================================
-- agent_steps format: JSON array of step objects
-- Example:
-- [
--   {
--     "step_type": "thinking",
--     "content": "Analyzing query and available tools",
--     "timestamp": "2026-03-25T10:30:00Z",
--     "status": "completed",
--     "metadata": {}
--   },
--   {
--     "step_type": "tool_call",
--     "content": "Executing: query_hana_table",
--     "timestamp": "2026-03-25T10:30:01Z",
--     "status": "completed",
--     "metadata": {
--       "tool_name": "query_hana_table",
--       "duration_ms": 1250
--     }
--   }
-- ]
--
-- langfuse_trace_id: Unique trace ID from Langfuse for correlating with external dashboard
-- langfuse_observation_id: Optional observation ID for specific LLM calls
