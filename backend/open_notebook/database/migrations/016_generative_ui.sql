-- Generative UI migration
-- Migration: 016_generative_ui
-- Database: SQLite
-- Description: Add nullable fields to chat_messages for generative UI support.
--              Enables assistant messages to carry structured UI component specs,
--              render mode hints, and raw tool execution results.

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- ============================================================================
-- EXTEND CHAT_MESSAGES TABLE
-- ============================================================================

-- JSON array of UIComponentData objects (component type, props, layout hints)
ALTER TABLE chat_messages ADD COLUMN ui_components TEXT;

-- Render mode hint for the frontend: 'markdown', 'generative_ui', 'hybrid'
ALTER TABLE chat_messages ADD COLUMN render_mode TEXT DEFAULT 'markdown';

-- JSON array of ToolResultData objects captured during agent execution
ALTER TABLE chat_messages ADD COLUMN tool_results TEXT;

-- Index on render_mode for efficient filtering of generative UI messages
CREATE INDEX IF NOT EXISTS idx_chat_messages_render_mode ON chat_messages(render_mode);
