-- Migration 021: User Query Prompts
-- Create table for user-specific saved query prompts

CREATE TABLE IF NOT EXISTS user_query_prompts (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    query_text TEXT NOT NULL,
    description TEXT,
    category VARCHAR(100),
    team_id VARCHAR(36),  -- Optional: associate with specific team
    prompt_role VARCHAR(50),  -- Optional: remember which system prompt was used
    tags TEXT,  -- JSON array of tags
    use_count INTEGER DEFAULT 0,
    last_used TEXT,
    is_favorite INTEGER DEFAULT 0,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_user_query_prompts_user ON user_query_prompts(user_id);
CREATE INDEX IF NOT EXISTS idx_user_query_prompts_team ON user_query_prompts(team_id);
CREATE INDEX IF NOT EXISTS idx_user_query_prompts_favorite ON user_query_prompts(is_favorite);
CREATE INDEX IF NOT EXISTS idx_user_query_prompts_last_used ON user_query_prompts(last_used);

-- HANA version will be created separately in hana/ directory
