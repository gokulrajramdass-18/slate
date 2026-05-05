-- Migration: 046_seed_tool_registry.sql
-- Description: Seed tool_registry with prebuilt tools
-- Date: 2026-04-04

-- Web Search Tool
INSERT OR IGNORE INTO tool_registry (id, name, tool_type, category, description, enabled, metadata)
VALUES (
    'web-search-tool',
    'Web Search',
    'web_search',
    'web',
    'Search the web using Tavily API for up-to-date information',
    1,
    '{"icon": "search", "tags": ["web", "search", "research"]}'
);

-- Calculator Tool
INSERT OR IGNORE INTO tool_registry (id, name, tool_type, category, description, enabled, metadata)
VALUES (
    'calculator-tool',
    'Calculator',
    'calculator',
    'computation',
    'Perform mathematical calculations and evaluate expressions',
    1,
    '{"icon": "calculator", "tags": ["math", "calculation", "compute"]}'
);

-- DateTime Tool
INSERT OR IGNORE INTO tool_registry (id, name, tool_type, category, description, enabled, metadata)
VALUES (
    'datetime-tool',
    'Date & Time',
    'datetime',
    'utility',
    'Get current date/time, format dates, calculate date differences',
    1,
    '{"icon": "calendar", "tags": ["date", "time", "calendar"]}'
);

-- URL Fetch Tool
INSERT OR IGNORE INTO tool_registry (id, name, tool_type, category, description, enabled, metadata)
VALUES (
    'url-fetch-tool',
    'URL Fetch',
    'url_fetch',
    'web',
    'Fetch and extract content from web pages',
    1,
    '{"icon": "globe", "tags": ["web", "fetch", "scrape"]}'
);

-- JSON Parser Tool
INSERT OR IGNORE INTO tool_registry (id, name, tool_type, category, description, enabled, metadata)
VALUES (
    'json-parser-tool',
    'JSON Parser',
    'json_parser',
    'data',
    'Parse, validate, and query JSON data structures',
    1,
    '{"icon": "braces", "tags": ["json", "parse", "data"]}'
);

-- Text Analyzer Tool
INSERT OR IGNORE INTO tool_registry (id, name, tool_type, category, description, enabled, metadata)
VALUES (
    'text-analyzer-tool',
    'Text Analyzer',
    'text_analyzer',
    'analysis',
    'Analyze text for statistics, sentiment, and patterns',
    1,
    '{"icon": "file-text", "tags": ["text", "analysis", "nlp"]}'
);

-- Wikipedia Tool
INSERT OR IGNORE INTO tool_registry (id, name, tool_type, category, description, enabled, metadata)
VALUES (
    'wikipedia-tool',
    'Wikipedia',
    'wikipedia',
    'knowledge',
    'Search and retrieve information from Wikipedia',
    1,
    '{"icon": "book-open", "tags": ["wikipedia", "knowledge", "research"]}'
);
