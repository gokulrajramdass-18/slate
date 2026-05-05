-- Open Notebook - SQLite Base Schema
-- Migration: 001_initial_schema
-- Database: SQLite
-- Description: Core tables for notebooks, sources, notes, chat, and configuration

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Notebooks (research projects)
CREATE TABLE IF NOT EXISTS notebooks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    folder_id TEXT,
    archived INTEGER DEFAULT 0,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_notebooks_folder ON notebooks(folder_id);
CREATE INDEX IF NOT EXISTS idx_notebooks_archived ON notebooks(archived);
CREATE INDEX IF NOT EXISTS idx_notebooks_created ON notebooks(created);

-- Sources (content from various types)
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    title TEXT,
    source_type TEXT NOT NULL,  -- file, url, text, youtube, hana_table, api
    full_text TEXT,
    topics TEXT,  -- JSON array
    asset_type TEXT,  -- pdf, docx, video, etc.
    asset_data TEXT,  -- JSON object with metadata
    connection_config TEXT,  -- JSON object (encrypted for hana_table, api)
    sync_config TEXT,  -- JSON object {frequency, last_sync, status, error}
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sources_type ON sources(source_type);
CREATE INDEX IF NOT EXISTS idx_sources_created ON sources(created);

-- Full-text search on sources (FTS5)
CREATE VIRTUAL TABLE IF NOT EXISTS sources_fts USING fts5(
    id UNINDEXED,
    title,
    full_text,
    content='sources',
    content_rowid='rowid'
);

-- Triggers to keep FTS index in sync
CREATE TRIGGER IF NOT EXISTS sources_fts_insert AFTER INSERT ON sources BEGIN
    INSERT INTO sources_fts(id, title, full_text)
    VALUES (new.id, new.title, new.full_text);
END;

CREATE TRIGGER IF NOT EXISTS sources_fts_update AFTER UPDATE ON sources BEGIN
    UPDATE sources_fts SET title = new.title, full_text = new.full_text
    WHERE id = old.id;
END;

CREATE TRIGGER IF NOT EXISTS sources_fts_delete AFTER DELETE ON sources BEGIN
    DELETE FROM sources_fts WHERE id = old.id;
END;

-- Source Embeddings (vector search)
CREATE TABLE IF NOT EXISTS source_embeddings (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    order_num INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding TEXT,  -- JSON array of floats (1536 dimensions)
    created TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_embeddings_source ON source_embeddings(source_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_order ON source_embeddings(source_id, order_num);

-- Junction: Notebooks <-> Sources (many-to-many)
CREATE TABLE IF NOT EXISTS notebook_source (
    notebook_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    created TEXT NOT NULL,
    PRIMARY KEY (notebook_id, source_id),
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_notebook_source_notebook ON notebook_source(notebook_id);
CREATE INDEX IF NOT EXISTS idx_notebook_source_source ON notebook_source(source_id);

-- Notes (user-generated or AI-generated insights)
CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    title TEXT,
    summary TEXT,
    content TEXT,
    embedding TEXT,  -- JSON array (optional for semantic search)
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_notes_created ON notes(created);

-- Junction: Notebooks <-> Notes
CREATE TABLE IF NOT EXISTS notebook_note (
    notebook_id TEXT NOT NULL,
    note_id TEXT NOT NULL,
    created TEXT NOT NULL,
    PRIMARY KEY (notebook_id, note_id),
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE,
    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_notebook_note_notebook ON notebook_note(notebook_id);
CREATE INDEX IF NOT EXISTS idx_notebook_note_note ON notebook_note(note_id);

-- ============================================================================
-- CHAT TABLES
-- ============================================================================

-- Chat Sessions
CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    title TEXT,
    notebook_id TEXT NOT NULL,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_notebook ON chat_sessions(notebook_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated ON chat_sessions(updated);

-- Chat Messages
CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,  -- user, assistant, system
    content TEXT NOT NULL,
    created TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created ON chat_messages(created);

-- ============================================================================
-- AI & CONFIGURATION TABLES
-- ============================================================================

-- Credentials (encrypted API keys)
CREATE TABLE IF NOT EXISTS credentials (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    modalities TEXT,  -- JSON array
    api_key_encrypted TEXT,
    base_url TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_credentials_provider ON credentials(provider);

-- AI Models
CREATE TABLE IF NOT EXISTS models (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    type TEXT NOT NULL,  -- language, embedding, speech_to_text, text_to_speech
    credential_id TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (credential_id) REFERENCES credentials(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_models_type ON models(type);
CREATE INDEX IF NOT EXISTS idx_models_provider ON models(provider);

-- Transformations (custom content processing)
CREATE TABLE IF NOT EXISTS transformations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    title TEXT,
    description TEXT,
    prompt TEXT NOT NULL,
    apply_default INTEGER DEFAULT 0,
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_transformations_default ON transformations(apply_default);

-- ============================================================================
-- ORGANIZATION TABLES
-- ============================================================================

-- Folders (notebook organization)
CREATE TABLE IF NOT EXISTS folders (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    parent_id TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (parent_id) REFERENCES folders(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders(parent_id);

-- Tags
CREATE TABLE IF NOT EXISTS tags (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    color TEXT
);

-- Junction: Notebooks <-> Tags
CREATE TABLE IF NOT EXISTS notebook_tags (
    notebook_id TEXT NOT NULL,
    tag_id TEXT NOT NULL,
    PRIMARY KEY (notebook_id, tag_id),
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_notebook_tags_notebook ON notebook_tags(notebook_id);
CREATE INDEX IF NOT EXISTS idx_notebook_tags_tag ON notebook_tags(tag_id);

-- ============================================================================
-- SEARCH CONFIGURATION
-- ============================================================================

-- Search Configuration
CREATE TABLE IF NOT EXISTS search_config (
    id TEXT PRIMARY KEY,
    user_id TEXT,  -- optional, for multi-user support
    default_strategy TEXT,  -- keyword, vector, hybrid, agentic_rag
    config TEXT,  -- JSON object with strategy-specific settings
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);

-- ============================================================================
-- MIGRATIONS TRACKING
-- ============================================================================

-- Migration history
CREATE TABLE IF NOT EXISTS _migrations (
    id TEXT PRIMARY KEY,
    version INTEGER UNIQUE NOT NULL,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
