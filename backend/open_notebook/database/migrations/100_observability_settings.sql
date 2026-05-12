-- Migration: 100 - Observability Settings
-- Description: Add settings for MLFlow and Langfuse observability configuration
-- Date: 2026-05-11

-- Add observability settings to settings table
-- Note: secret_key and password fields will be ENCRYPTED before storage
INSERT OR IGNORE INTO settings (key, value, type, description, created, updated) VALUES
  ('observability_provider', 'none', 'string', 'Observability provider: none, langfuse, mlflow, both', datetime('now'), datetime('now')),

  -- Langfuse settings (secret_key is ENCRYPTED before storage)
  ('langfuse_enabled', 'false', 'boolean', 'Enable Langfuse observability', datetime('now'), datetime('now')),
  ('langfuse_public_key', '', 'string', 'Langfuse public API key', datetime('now'), datetime('now')),
  ('langfuse_secret_key', '', 'string', 'Langfuse secret API key (ENCRYPTED)', datetime('now'), datetime('now')),
  ('langfuse_host', 'https://cloud.langfuse.com', 'string', 'Langfuse host URL', datetime('now'), datetime('now')),

  -- MLFlow settings (basic auth credentials ENCRYPTED if provided)
  ('mlflow_enabled', 'false', 'boolean', 'Enable MLFlow observability', datetime('now'), datetime('now')),
  ('mlflow_tracking_uri', 'http://mlflow:5000', 'string', 'MLFlow tracking server URL', datetime('now'), datetime('now')),
  ('mlflow_experiment_name', 'slate-agents', 'string', 'MLFlow experiment name', datetime('now'), datetime('now')),
  ('mlflow_username', '', 'string', 'MLFlow basic auth username (optional)', datetime('now'), datetime('now')),
  ('mlflow_password', '', 'string', 'MLFlow basic auth password (ENCRYPTED, optional)', datetime('now'), datetime('now')),

  -- Common settings
  ('observability_trace_level', 'info', 'string', 'Trace level: debug, info, warn, error', datetime('now'), datetime('now')),
  ('observability_log_llm_calls', 'true', 'boolean', 'Log all LLM calls', datetime('now'), datetime('now')),
  ('observability_log_tool_calls', 'true', 'boolean', 'Log all tool executions', datetime('now'), datetime('now')),
  ('observability_log_agent_steps', 'true', 'boolean', 'Log agent execution steps', datetime('now'), datetime('now'));
