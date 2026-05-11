-- Migration: Add workspace_documents table for storing presentations and other documents
-- This table tracks documents (presentations, PDFs, etc.) stored in S3

CREATE TABLE IF NOT EXISTS workspace_documents (
    id TEXT PRIMARY KEY,
    notebook_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    document_type TEXT NOT NULL,  -- 'presentation', 'pdf', 'word', 'excel', etc.
    file_url TEXT NOT NULL,        -- S3 URL to the file
    file_size INTEGER,              -- File size in bytes
    s3_key TEXT NOT NULL,           -- S3 object key for deletion
    mime_type TEXT,                 -- MIME type of the file
    metadata TEXT,                  -- JSON metadata (presentation_id, slide_count, etc.)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE
);

-- Index for fast lookups by notebook
CREATE INDEX IF NOT EXISTS idx_workspace_documents_notebook
ON workspace_documents(notebook_id);

-- Index for document type filtering
CREATE INDEX IF NOT EXISTS idx_workspace_documents_type
ON workspace_documents(document_type);

-- Index for created_at ordering
CREATE INDEX IF NOT EXISTS idx_workspace_documents_created
ON workspace_documents(created_at DESC);
