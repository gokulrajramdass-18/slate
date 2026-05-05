-- Migration 002: Embeddings and Search Configuration
-- Adds support for vector search and search strategy configuration

-- Source Embeddings Table
-- Stores chunked embeddings for semantic search
CREATE TABLE IF NOT EXISTS source_embeddings (
    id VARCHAR(36) PRIMARY KEY,
    source_id VARCHAR(36) NOT NULL,
    order_num INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding BLOB NOT NULL,  -- Serialized NumPy array for SQLite, REAL_VECTOR for HANA
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_embeddings_source ON source_embeddings(source_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_order ON source_embeddings(source_id, order_num);

-- Search Configuration Table
-- Stores user preferences for search strategies
CREATE TABLE IF NOT EXISTS search_config (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36),  -- NULL for global config, specific for per-user
    default_strategy VARCHAR(50) NOT NULL DEFAULT 'hybrid',
    config TEXT NOT NULL,  -- JSON configuration
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id)  -- One config per user (NULL counts as one)
);

-- Default search configuration
INSERT INTO search_config (id, user_id, default_strategy, config, created, updated)
VALUES (
    'default-search-config',
    NULL,
    'hybrid',
    '{
        "default_strategy": "hybrid",
        "strategies": {
            "keyword": {
                "title_boost": 2.0,
                "min_score": 0.0,
                "snippet_length": 200
            },
            "vector": {
                "threshold": 0.7,
                "rerank": false
            },
            "hybrid": {
                "keyword_weight": 0.4,
                "vector_weight": 0.6,
                "rrf_k": 60,
                "keyword_config": {
                    "title_boost": 2.0,
                    "min_score": 0.0
                },
                "vector_config": {
                    "threshold": 0.7
                }
            },
            "agentic_rag": {
                "max_iterations": 5,
                "relevance_threshold": 0.6,
                "max_sub_queries": 5,
                "keyword_config": {},
                "vector_config": {},
                "hybrid_config": {}
            }
        }
    }',
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

-- Record migration
INSERT INTO _migrations (id, version, name, applied_at)
VALUES (
    'migration-002',
    2,
    'embeddings_and_search_config',
    CURRENT_TIMESTAMP
);
