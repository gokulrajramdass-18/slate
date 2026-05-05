-- Migration: 019 - Agent Memory
-- Description: Long-term memory storage for agents scoped to notebooks
-- Date: 2026-03-26

-- ============================================================================
-- AGENT MEMORY TABLE
-- ============================================================================
-- Stores persistent memory entries that agents can recall during conversations
-- Scoped to notebooks to maintain context isolation

CREATE TABLE IF NOT EXISTS agent_memory (
    id TEXT PRIMARY KEY,
    notebook_id TEXT NOT NULL,
    memory_type TEXT NOT NULL,  -- 'fact', 'conversation', 'insight', 'preference', 'skill'
    content TEXT NOT NULL,       -- The memory content/text
    metadata TEXT,               -- JSON: additional structured data
    tags TEXT,                   -- JSON array: searchable tags
    embedding BLOB,              -- Vector embedding for semantic search
    importance REAL DEFAULT 0.5, -- 0.0-1.0 importance score for prioritization
    access_count INTEGER DEFAULT 0,  -- Track usage frequency
    last_accessed TEXT,          -- ISO timestamp of last access
    created TEXT NOT NULL,       -- ISO timestamp
    updated TEXT NOT NULL,       -- ISO timestamp
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_agent_memory_notebook ON agent_memory(notebook_id);
CREATE INDEX IF NOT EXISTS idx_agent_memory_type ON agent_memory(memory_type);
CREATE INDEX IF NOT EXISTS idx_agent_memory_created ON agent_memory(created DESC);
CREATE INDEX IF NOT EXISTS idx_agent_memory_importance ON agent_memory(importance DESC);
CREATE INDEX IF NOT EXISTS idx_agent_memory_last_accessed ON agent_memory(last_accessed DESC);

-- ============================================================================
-- NOTES
-- ============================================================================
-- Memory Types:
--   - fact: Factual information learned during conversations
--   - conversation: Important conversation snippets worth remembering
--   - insight: Derived insights or patterns noticed by agents
--   - preference: User preferences and interaction patterns
--   - skill: Learned procedures or approaches that worked well
--
-- The embedding column stores vector embeddings for semantic search
-- The importance score helps with memory prioritization and pruning
-- Access count and last_accessed enable usage-based memory management
