-- Migration 033: LightRAG Entity Knowledge Graph
-- Creates tables for entity extraction, relationships, communities, and embeddings
-- Enables fine-grained knowledge graph construction from source content

-- Entities extracted from source content
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('person', 'organization', 'location', 'event', 'concept', 'other')),
    description TEXT,
    source_id TEXT NOT NULL,
    chunk_id TEXT,  -- Which chunk was it extracted from
    metadata TEXT,  -- JSON: {mentions: int, first_seen: timestamp, aliases: [], confidence: float}
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE,
    FOREIGN KEY (chunk_id) REFERENCES source_embeddings(id) ON DELETE CASCADE
);

-- Entity relationships (directed edges in knowledge graph)
CREATE TABLE IF NOT EXISTS entity_relationships (
    id TEXT PRIMARY KEY,
    source_entity_id TEXT NOT NULL,
    target_entity_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,  -- "mentions", "works_for", "located_in", "collaborated_on", etc.
    context TEXT,  -- Sentence/paragraph where relationship was found
    chunk_id TEXT,  -- Source chunk reference
    strength REAL DEFAULT 0.5 CHECK (strength BETWEEN 0.0 AND 1.0),
    metadata TEXT,  -- JSON: {co_occurrence_count: int, bidirectional: bool, confidence: float}
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (target_entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (chunk_id) REFERENCES source_embeddings(id) ON DELETE SET NULL,
    UNIQUE(source_entity_id, target_entity_id, relationship_type)
);

-- Entity embeddings for semantic entity search
CREATE TABLE IF NOT EXISTS entity_embeddings (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    embedding BLOB NOT NULL,  -- JSON array for SQLite, REAL_VECTOR for HANA
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE
);

-- Entity communities (clustering results from Louvain algorithm)
CREATE TABLE IF NOT EXISTS entity_communities (
    id TEXT PRIMARY KEY,
    name TEXT,
    description TEXT,  -- LLM-generated summary of community theme
    level INTEGER DEFAULT 0,  -- Hierarchy level (Louvain multi-resolution)
    parent_community_id TEXT,  -- For hierarchical communities
    entity_ids TEXT NOT NULL,  -- JSON array of entity IDs in this community
    metadata TEXT,  -- JSON: {size: int, density: float, central_entities: [], modularity: float}
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_community_id) REFERENCES entity_communities(id) ON DELETE CASCADE
);

-- Indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_entities_source ON entities(source_id);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
CREATE INDEX IF NOT EXISTS idx_entities_source_type ON entities(source_id, entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_created ON entities(created DESC);

CREATE INDEX IF NOT EXISTS idx_entity_rels_source ON entity_relationships(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_rels_target ON entity_relationships(target_entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_rels_type ON entity_relationships(relationship_type);
CREATE INDEX IF NOT EXISTS idx_entity_rels_source_target ON entity_relationships(source_entity_id, target_entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_rels_type_strength ON entity_relationships(relationship_type, strength DESC);
CREATE INDEX IF NOT EXISTS idx_entity_rels_strength ON entity_relationships(strength DESC);

CREATE INDEX IF NOT EXISTS idx_entity_embeddings_entity ON entity_embeddings(entity_id);

CREATE INDEX IF NOT EXISTS idx_communities_level ON entity_communities(level);
CREATE INDEX IF NOT EXISTS idx_communities_parent ON entity_communities(parent_community_id);
CREATE INDEX IF NOT EXISTS idx_communities_created ON entity_communities(created DESC);
