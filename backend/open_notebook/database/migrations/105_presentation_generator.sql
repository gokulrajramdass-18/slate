-- Migration: 105_presentation_generator
-- Description: Add tables for PowerPoint presentation generation feature
-- Author: AI Assistant
-- Date: 2026-05-05

-- Table: presentations
-- Stores main presentation entities
CREATE TABLE IF NOT EXISTS presentations (
    id TEXT PRIMARY KEY,
    notebook_id TEXT,
    template_id TEXT,
    title TEXT NOT NULL DEFAULT 'Untitled Presentation',
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE SET NULL,
    FOREIGN KEY (template_id) REFERENCES presentation_templates(id) ON DELETE SET NULL
);

-- Table: presentation_templates
-- Defines slide layouts and visual themes
CREATE TABLE IF NOT EXISTS presentation_templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    theme_json TEXT NOT NULL,  -- JSON: {colors, fonts, layouts}
    slide_layouts TEXT,         -- JSON array of available layouts
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table: presentation_content
-- Individual slide content within presentations
CREATE TABLE IF NOT EXISTS presentation_content (
    id TEXT PRIMARY KEY,
    presentation_id TEXT NOT NULL,
    slide_number INTEGER NOT NULL,
    slide_type TEXT NOT NULL,  -- title, bullets, two_column, content, image_text, chart
    content_html TEXT,          -- HTML for preview rendering
    content_json TEXT NOT NULL, -- JSON: {title, elements: [{type, content, position, style}]}
    speaker_notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (presentation_id) REFERENCES presentations(id) ON DELETE CASCADE,
    UNIQUE(presentation_id, slide_number)
);

-- Table: presentation_versions
-- Version snapshots for rollback capability
CREATE TABLE IF NOT EXISTS presentation_versions (
    id TEXT PRIMARY KEY,
    presentation_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    slides_snapshot TEXT NOT NULL,  -- JSON array of all slides
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    FOREIGN KEY (presentation_id) REFERENCES presentations(id) ON DELETE CASCADE,
    UNIQUE(presentation_id, version_number)
);

-- Table: presentation_sources
-- Links presentations to their source materials
CREATE TABLE IF NOT EXISTS presentation_sources (
    presentation_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (presentation_id, source_id),
    FOREIGN KEY (presentation_id) REFERENCES presentations(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_presentations_notebook_id ON presentations(notebook_id);
CREATE INDEX IF NOT EXISTS idx_presentations_template_id ON presentations(template_id);
CREATE INDEX IF NOT EXISTS idx_presentations_created_at ON presentations(created_at);

CREATE INDEX IF NOT EXISTS idx_presentation_content_presentation_id ON presentation_content(presentation_id);
CREATE INDEX IF NOT EXISTS idx_presentation_content_slide_number ON presentation_content(presentation_id, slide_number);

CREATE INDEX IF NOT EXISTS idx_presentation_versions_presentation_id ON presentation_versions(presentation_id);
CREATE INDEX IF NOT EXISTS idx_presentation_versions_version_number ON presentation_versions(presentation_id, version_number);

CREATE INDEX IF NOT EXISTS idx_presentation_sources_presentation_id ON presentation_sources(presentation_id);
CREATE INDEX IF NOT EXISTS idx_presentation_sources_source_id ON presentation_sources(source_id);

CREATE INDEX IF NOT EXISTS idx_presentation_templates_category ON presentation_templates(category);
CREATE INDEX IF NOT EXISTS idx_presentation_templates_active ON presentation_templates(is_active);
