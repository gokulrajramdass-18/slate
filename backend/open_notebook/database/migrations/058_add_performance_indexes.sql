-- Performance indexes for frequently queried columns
-- Improves JOIN performance on junction tables and filtered queries

CREATE INDEX IF NOT EXISTS idx_notebook_source_notebook ON notebook_source(notebook_id);
CREATE INDEX IF NOT EXISTS idx_notebook_source_source ON notebook_source(source_id);
CREATE INDEX IF NOT EXISTS idx_source_embeddings_source ON source_embeddings(source_id);
CREATE INDEX IF NOT EXISTS idx_notebooks_created_by ON notebooks(created_by);
CREATE INDEX IF NOT EXISTS idx_sources_created_by ON sources(created_by);
-- Note: bookmarks table index will be added when bookmarks feature is fully migrated
