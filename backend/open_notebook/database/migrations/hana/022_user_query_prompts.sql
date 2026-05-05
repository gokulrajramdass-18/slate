-- Migration 021: User Query Prompts (HANA Version)
-- Create table for user-specific saved query prompts

CREATE TABLE user_query_prompts (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    query_text NCLOB NOT NULL,
    description NCLOB,
    category VARCHAR(100),
    team_id VARCHAR(36),
    prompt_role VARCHAR(50),
    tags NCLOB,
    use_count INTEGER DEFAULT 0,
    last_used TIMESTAMP,
    is_favorite SMALLINT DEFAULT 0,
    created TIMESTAMP NOT NULL,
    updated TIMESTAMP NOT NULL,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE SET NULL
);

CREATE INDEX idx_user_query_prompts_user ON user_query_prompts(user_id);
CREATE INDEX idx_user_query_prompts_team ON user_query_prompts(team_id);
CREATE INDEX idx_user_query_prompts_favorite ON user_query_prompts(is_favorite);
CREATE INDEX idx_user_query_prompts_last_used ON user_query_prompts(last_used);
