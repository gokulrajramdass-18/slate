-- Add chart visualization tool to registry (skip if already exists)
INSERT OR IGNORE INTO tool_registry (id, name, tool_type, category, description, enabled, default_config, metadata, created, updated)
VALUES (
    '550e8400-e29b-41d4-a716-446655440011',  -- Fixed UUID for chart tool
    'Chart Visualization',
    'chart',
    'visualization',  -- category
    'Create interactive charts and visualizations from data. Supports line, bar, pie, scatter, area, and radar charts with automatic type detection.',
    1,  -- enabled
    '{}',  -- default config (no special config needed)
    '{"requires_api_key": false}',
    datetime('now'),
    datetime('now')
);
