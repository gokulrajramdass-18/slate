-- Migration 012: Source Graph Visualization Tables
-- Creates tables for relational graph visualization with source similarities and saved layouts

-- Source similarities table - Pre-computed semantic relationships
CREATE TABLE IF NOT EXISTS source_similarities (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    related_source_id TEXT NOT NULL,
    similarity_score REAL NOT NULL CHECK (similarity_score >= 0.0 AND similarity_score <= 1.0),
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, related_source_id),
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE,
    FOREIGN KEY (related_source_id) REFERENCES sources(id) ON DELETE CASCADE
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_similarities_source ON source_similarities(source_id, similarity_score DESC);
CREATE INDEX IF NOT EXISTS idx_similarities_related ON source_similarities(related_source_id, similarity_score DESC);
CREATE INDEX IF NOT EXISTS idx_similarities_score ON source_similarities(similarity_score DESC);

-- Graph layouts table - Saved node positions for custom layouts
CREATE TABLE IF NOT EXISTS graph_layouts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    scope TEXT NOT NULL CHECK (scope IN ('global', 'notebook')),
    scope_id TEXT,  -- notebook_id if scope='notebook', NULL if global
    layout_data TEXT NOT NULL,  -- JSON: { nodes: { [source_id]: { x: number, y: number } } }
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scope_id) REFERENCES notebooks(id) ON DELETE CASCADE
);

-- Index for filtering by scope
CREATE INDEX IF NOT EXISTS idx_layouts_scope ON graph_layouts(scope, scope_id);
CREATE INDEX IF NOT EXISTS idx_layouts_created ON graph_layouts(created DESC);
