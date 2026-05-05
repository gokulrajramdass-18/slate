-- Open Notebook - Source Classification Schema
-- Migration: 063_source_classification
-- Database: SQLite
-- Description: Hierarchical classification system with approval workflow

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- ============================================================================
-- CLASSIFICATION TABLES
-- ============================================================================

-- Classification types (hierarchical taxonomy)
-- Supports multi-level hierarchy: Category (level 0) -> Topic/Project (level 1) -> Subtopic (level 2)
CREATE TABLE IF NOT EXISTS classification_types (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    classification_type TEXT NOT NULL,  -- 'category', 'topic', 'project', 'subtopic'
    parent_id TEXT,  -- NULL for root categories
    level INTEGER DEFAULT 0,  -- 0=category, 1=topic/project, 2=subtopic
    color TEXT,  -- Hex color for visualization
    icon TEXT,  -- Icon name from lucide-react
    created TEXT NOT NULL,
    updated TEXT,
    FOREIGN KEY (parent_id) REFERENCES classification_types(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_classification_types_parent ON classification_types(parent_id);
CREATE INDEX IF NOT EXISTS idx_classification_types_type ON classification_types(classification_type);
CREATE INDEX IF NOT EXISTS idx_classification_types_level ON classification_types(level);
CREATE INDEX IF NOT EXISTS idx_classification_types_name ON classification_types(name);

-- Source classifications (many-to-many with approval workflow)
-- Links sources to classification nodes with confidence scores and approval status
CREATE TABLE IF NOT EXISTS source_classifications (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    classification_id TEXT NOT NULL,
    confidence REAL,  -- 0.0-1.0 (AI confidence score)
    status TEXT DEFAULT 'pending',  -- 'pending', 'approved', 'rejected'
    approved_by TEXT,  -- User ID who approved/rejected
    approved_at TEXT,  -- ISO timestamp
    metadata TEXT,  -- JSON: {reason, ai_explanation, manual_note}
    created TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE,
    FOREIGN KEY (classification_id) REFERENCES classification_types(id) ON DELETE CASCADE,
    UNIQUE(source_id, classification_id)
);

CREATE INDEX IF NOT EXISTS idx_source_classifications_source ON source_classifications(source_id);
CREATE INDEX IF NOT EXISTS idx_source_classifications_class ON source_classifications(classification_id);
CREATE INDEX IF NOT EXISTS idx_source_classifications_status ON source_classifications(status);
CREATE INDEX IF NOT EXISTS idx_source_classifications_confidence ON source_classifications(confidence);

-- Classification relationships (connections between classification nodes)
-- Represents parent-child hierarchy and related/similar relationships
CREATE TABLE IF NOT EXISTS classification_relationships (
    id TEXT PRIMARY KEY,
    source_classification_id TEXT NOT NULL,
    target_classification_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,  -- 'parent_child', 'related', 'similar'
    strength REAL,  -- 0.0-1.0 (relationship strength)
    created TEXT NOT NULL,
    FOREIGN KEY (source_classification_id) REFERENCES classification_types(id) ON DELETE CASCADE,
    FOREIGN KEY (target_classification_id) REFERENCES classification_types(id) ON DELETE CASCADE,
    UNIQUE(source_classification_id, target_classification_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_classification_relationships_source ON classification_relationships(source_classification_id);
CREATE INDEX IF NOT EXISTS idx_classification_relationships_target ON classification_relationships(target_classification_id);
CREATE INDEX IF NOT EXISTS idx_classification_relationships_type ON classification_relationships(relationship_type);
