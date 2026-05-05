-- ============================================================================
-- Open Notebook - HANA Cloud Initial Schema
-- Migration: 001_initial_schema
-- Database: SAP HANA Cloud
-- ============================================================================
--
-- This migration creates the initial database schema for Open Notebook
-- using SAP HANA Cloud specific data types and optimizations.
--
-- Key HANA Features:
-- - REAL_VECTOR for embeddings (native vector engine)
-- - NCLOB for large JSON/text fields
-- - Column store for analytics performance
-- - Full-text indexing with CONTAINS()
-- ============================================================================

-- Core Tables
-- ============================================================================

-- Notebooks: Research projects/collections
CREATE COLUMN TABLE notebooks (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description NCLOB,
    archived BOOLEAN DEFAULT FALSE,
    folder_id VARCHAR(36),
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_notebooks_archived ON notebooks(archived);
CREATE INDEX idx_notebooks_folder ON notebooks(folder_id);
CREATE INDEX idx_notebooks_created ON notebooks(created);

-- Sources: Content from various types
CREATE COLUMN TABLE sources (
    id VARCHAR(36) PRIMARY KEY,
    title VARCHAR(500),
    source_type VARCHAR(50) NOT NULL,  -- file, url, text, youtube, hana_table, api
    full_text NCLOB,
    topics NCLOB,  -- JSON array
    asset_type VARCHAR(50),
    asset_data NCLOB,  -- JSON
    connection_config NCLOB,  -- JSON (encrypted credentials for hana_table, api)
    sync_config NCLOB,  -- JSON (sync frequency, last_sync, status)
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sources_type ON sources(source_type);
CREATE INDEX idx_sources_created ON sources(created);

-- Full-text index for sources
CREATE FULLTEXT INDEX fts_sources ON sources(title, full_text)
    TEXT ANALYSIS ON
    LANGUAGE DETECTION ('EN')
    FAST PREPROCESS ON
    MIME TYPE PLAIN_TEXT;

-- Source Embeddings: Vector search
CREATE COLUMN TABLE source_embeddings (
    id VARCHAR(36) PRIMARY KEY,
    source_id VARCHAR(36) NOT NULL,
    order_num INTEGER,
    content NCLOB,
    embedding REAL_VECTOR(1536),  -- OpenAI ada-002 dimension
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
);

CREATE INDEX idx_embeddings_source ON source_embeddings(source_id);
CREATE INDEX idx_embeddings_order ON source_embeddings(source_id, order_num);

-- Vector index for high-performance similarity search
-- HANA automatically optimizes REAL_VECTOR columns with vector indexes

-- Junction: Notebooks <-> Sources (many-to-many)
CREATE COLUMN TABLE notebook_source (
    notebook_id VARCHAR(36) NOT NULL,
    source_id VARCHAR(36) NOT NULL,
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (notebook_id, source_id),
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
);

CREATE INDEX idx_notebook_source_notebook ON notebook_source(notebook_id);
CREATE INDEX idx_notebook_source_source ON notebook_source(source_id);

-- Notes: User-generated or AI-generated insights
CREATE COLUMN TABLE notes (
    id VARCHAR(36) PRIMARY KEY,
    title VARCHAR(255),
    summary NCLOB,
    content NCLOB,
    embedding REAL_VECTOR(1536),  -- Optional for semantic search
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_notes_created ON notes(created);

-- Junction: Notebooks <-> Notes
CREATE COLUMN TABLE notebook_note (
    notebook_id VARCHAR(36) NOT NULL,
    note_id VARCHAR(36) NOT NULL,
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (notebook_id, note_id),
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE,
    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
);

-- Chat Tables
-- ============================================================================

-- Chat Sessions
CREATE COLUMN TABLE chat_sessions (
    id VARCHAR(36) PRIMARY KEY,
    title VARCHAR(255),
    notebook_id VARCHAR(36),
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE
);

CREATE INDEX idx_chat_sessions_notebook ON chat_sessions(notebook_id);
CREATE INDEX idx_chat_sessions_created ON chat_sessions(created);

-- Chat Messages
CREATE COLUMN TABLE chat_messages (
    id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL,
    role VARCHAR(20) NOT NULL,  -- user, assistant, system
    content NCLOB,
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
);

CREATE INDEX idx_chat_messages_session ON chat_messages(session_id);
CREATE INDEX idx_chat_messages_created ON chat_messages(session_id, created);

-- AI Configuration Tables
-- ============================================================================

-- Credentials: Encrypted API keys and credentials
CREATE COLUMN TABLE credentials (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    modalities NCLOB,  -- JSON array: ["chat", "embedding", etc.]
    api_key_encrypted NCLOB,  -- AES-256-GCM encrypted
    base_url VARCHAR(500),
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_credentials_provider ON credentials(provider);

-- AI Models
CREATE COLUMN TABLE models (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    type VARCHAR(50) NOT NULL,  -- language, embedding, speech_to_text, text_to_speech
    credential_id VARCHAR(36),
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (credential_id) REFERENCES credentials(id) ON DELETE SET NULL
);

CREATE INDEX idx_models_provider ON models(provider);
CREATE INDEX idx_models_type ON models(type);

-- Transformations: Custom content processing
CREATE COLUMN TABLE transformations (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    title VARCHAR(255),
    description NCLOB,
    prompt NCLOB,
    apply_default BOOLEAN DEFAULT FALSE,
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Organization Tables
-- ============================================================================

-- Folders: Notebook organization
CREATE COLUMN TABLE folders (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    parent_id VARCHAR(36),
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES folders(id) ON DELETE CASCADE
);

CREATE INDEX idx_folders_parent ON folders(parent_id);

-- Add foreign key for notebooks.folder_id (after folders table exists)
ALTER TABLE notebooks ADD FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE SET NULL;

-- Tags
CREATE COLUMN TABLE tags (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    color VARCHAR(20)
);

CREATE INDEX idx_tags_name ON tags(name);

-- Junction: Notebooks <-> Tags
CREATE COLUMN TABLE notebook_tags (
    notebook_id VARCHAR(36) NOT NULL,
    tag_id VARCHAR(36) NOT NULL,
    PRIMARY KEY (notebook_id, tag_id),
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

-- Search Configuration
-- ============================================================================

CREATE COLUMN TABLE search_config (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36),  -- Optional for multi-user setups
    default_strategy VARCHAR(50) NOT NULL,  -- keyword, vector, hybrid, agentic_rag
    config NCLOB,  -- JSON: strategy-specific settings
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Migration Tracking
-- ============================================================================

CREATE COLUMN TABLE _migrations (
    id VARCHAR(36) PRIMARY KEY,
    version INTEGER UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert this migration record
INSERT INTO _migrations (id, version, name, applied_at)
VALUES (
    'hana-001',
    1,
    '001_initial_schema',
    CURRENT_TIMESTAMP
);

-- ============================================================================
-- Performance Optimizations
-- ============================================================================

-- HANA automatically creates column store delta merges
-- For high-write tables, consider partitioning:
-- ALTER TABLE source_embeddings PARTITION BY HASH (source_id) PARTITIONS 4;

-- Vector indexes are automatically created for REAL_VECTOR columns
-- No explicit index creation needed for embedding columns

-- ============================================================================
-- Comments for Documentation
-- ============================================================================

COMMENT ON TABLE notebooks IS 'Research projects and collections';
COMMENT ON TABLE sources IS 'Content from files, URLs, HANA tables, APIs, etc.';
COMMENT ON TABLE source_embeddings IS 'Vector embeddings for semantic search';
COMMENT ON TABLE chat_sessions IS 'AI chat conversation sessions';
COMMENT ON TABLE credentials IS 'Encrypted API keys for AI providers';
COMMENT ON TABLE models IS 'AI model configurations (chat, embedding, STT, TTS)';

-- ============================================================================
-- End of Initial Schema Migration
-- ============================================================================
