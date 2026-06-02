CREATE TABLE _migrations (
    id TEXT PRIMARY KEY,
    version INTEGER UNIQUE NOT NULL,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
CREATE TABLE a2a_agent_credentials (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL UNIQUE,
    credential_type TEXT NOT NULL,     -- 'apiKey', 'bearer', 'oauth2', 'basic'
    credential_data TEXT NOT NULL,     -- JSON: Encrypted credential details
    expires_at TEXT,                   -- For OAuth tokens with expiry
    created TEXT NOT NULL DEFAULT (datetime('now')),
    updated TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (agent_id) REFERENCES a2a_agent_registry(id) ON DELETE CASCADE
);
CREATE TABLE a2a_agent_registry (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    card_url TEXT NOT NULL UNIQUE,
    agent_card TEXT NOT NULL,          -- JSON: Full AgentCard from A2A protocol
    transport TEXT DEFAULT 'JSONRPC',  -- JSONRPC, GRPC, HTTP+JSON
    endpoint_url TEXT NOT NULL,
    security_schemes TEXT,             -- JSON: Authentication requirements
    available_skills TEXT,             -- JSON array: List of skill IDs from remote agent
    last_synced TEXT,                  -- Last time AgentCard was refreshed
    enabled INTEGER NOT NULL DEFAULT 1,
    metadata TEXT,                     -- JSON: Stats like latency, success_rate, version
    created TEXT NOT NULL DEFAULT (datetime('now')),
    updated TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE a2a_execution_metrics (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    skill_id TEXT,
    task_id TEXT NOT NULL,

    -- Performance
    latency_ms REAL,                   -- Total execution time
    network_latency_ms REAL,           -- Network round-trip time

    -- Result
    success INTEGER NOT NULL,
    error_type TEXT,                   -- timeout, network, auth, validation, server_error
    error_message TEXT,

    -- Context
    retry_count INTEGER DEFAULT 0,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (agent_id) REFERENCES a2a_agent_registry(id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES a2a_task_store(id) ON DELETE CASCADE
);
CREATE TABLE a2a_skill_mappings (
    id TEXT PRIMARY KEY,
    remote_agent_id TEXT NOT NULL,
    remote_skill_id TEXT NOT NULL,     -- Skill ID from remote AgentCard
    local_skill_id TEXT NOT NULL,      -- Generated local skill ID (a2a:{agent_id}:{skill_id})
    skill_name TEXT NOT NULL,
    skill_description TEXT,
    skill_tags TEXT,                   -- JSON array
    input_modes TEXT,                  -- JSON array of MIME types
    output_modes TEXT,                 -- JSON array of MIME types
    enabled INTEGER NOT NULL DEFAULT 1,
    created TEXT NOT NULL DEFAULT (datetime('now')),
    updated TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (remote_agent_id) REFERENCES a2a_agent_registry(id) ON DELETE CASCADE,
    FOREIGN KEY (local_skill_id) REFERENCES agent_skills(id) ON DELETE CASCADE,

    UNIQUE(remote_agent_id, remote_skill_id)
);
CREATE TABLE a2a_task_store (
    id TEXT PRIMARY KEY,               -- A2A task ID (UUID)
    context_id TEXT NOT NULL,          -- Conversation/session context ID
    agent_id TEXT,                     -- Remote agent ID (if outgoing) or NULL (if incoming)
    skill_id TEXT,                     -- Skill being executed
    kind TEXT DEFAULT 'task',          -- task, session, etc.
    direction TEXT NOT NULL,           -- 'outgoing' (to remote) or 'incoming' (from remote)

    -- A2A TaskStatus fields
    state TEXT NOT NULL,               -- queued, running, auth-required, completed, canceled, rejected, failed
    progress REAL,                     -- 0.0 to 1.0
    message TEXT,                      -- Status message

    -- Content
    history TEXT,                      -- JSON: Array of Message objects (A2A format)
    artifacts TEXT,                    -- JSON: Array of Artifact objects (A2A format)
    task_metadata TEXT,                -- JSON: Task-specific metadata

    -- Tracking
    started_at TEXT,
    completed_at TEXT,
    created TEXT NOT NULL DEFAULT (datetime('now'))
, updated TEXT);
CREATE TABLE IF NOT EXISTS "action_executions" (
    id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL,
    orchestration_id TEXT,
    chat_session_id TEXT,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL,
    trigger_event TEXT,
    input_data TEXT,
    output_data TEXT,
    error_message TEXT,
    condition_met INTEGER,
    condition_details TEXT,
    execution_time_ms INTEGER,
    retry_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (action_id) REFERENCES actions(id) ON DELETE CASCADE
);
CREATE TABLE actions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,

    
    action_type TEXT NOT NULL,  

    
    endpoint TEXT,  
    method TEXT DEFAULT 'POST',  

    
    auth_type TEXT,  
    auth_config_encrypted TEXT,  

    
    headers TEXT,
    query_params TEXT,

    
    body_template TEXT,  

    
    condition_expression TEXT,  

    
    retry_policy TEXT,  

    
    is_active INTEGER DEFAULT 1,

    
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_executed_at TEXT,
    execution_count INTEGER DEFAULT 0
);
CREATE TABLE agent_evaluation_configs (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL UNIQUE,
    enabled BOOLEAN NOT NULL DEFAULT 1,
    auto_evaluate BOOLEAN NOT NULL DEFAULT 1,
    scope TEXT NOT NULL DEFAULT 'all',  
    scoring_scale TEXT NOT NULL DEFAULT '0-10',
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE
);
CREATE TABLE agent_execution_evaluations (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    team_id TEXT NOT NULL,
    judge_agent_id TEXT,
    scope TEXT NOT NULL,  
    target_agent_id TEXT,  
    overall_score REAL,  
    criteria_scores TEXT,  
    feedback TEXT,
    approval_status TEXT,  
    confidence REAL,  
    created TEXT NOT NULL,
    FOREIGN KEY (execution_id) REFERENCES agent_executions(id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE,
    FOREIGN KEY (judge_agent_id) REFERENCES agent_instances(id) ON DELETE SET NULL,
    FOREIGN KEY (target_agent_id) REFERENCES agent_instances(id) ON DELETE SET NULL
);
CREATE TABLE agent_execution_traces (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    langfuse_trace_id TEXT,
    model_used TEXT,
    total_tokens INTEGER,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_cost REAL,
    duration_ms INTEGER,
    tool_calls_count INTEGER,
    error_occurred BOOLEAN DEFAULT 0,
    created TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (message_id) REFERENCES chat_messages(id) ON DELETE CASCADE
);
CREATE TABLE agent_executions (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    query TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running', 
    context_source_ids TEXT, 
    max_steps INTEGER DEFAULT 10,
    mode TEXT DEFAULT 'sequential', 
    result TEXT, 
    started_at TEXT NOT NULL,
    completed_at TEXT,
    created TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE
);
CREATE TABLE agent_instances (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    role TEXT NOT NULL,           
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'idle',  
    model_name TEXT,
    system_prompt TEXT,
    config TEXT,                  
    result TEXT,                  
    error TEXT,
    started_at TEXT,
    completed_at TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL, model_override TEXT, tool_ids TEXT, last_active TEXT, is_remote INTEGER DEFAULT 0 NOT NULL, remote_agent_id TEXT, a2a_endpoint_url TEXT, standalone_agent_id TEXT, order_index INTEGER DEFAULT 0,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE
);
CREATE TABLE agent_memory (
    id TEXT PRIMARY KEY,
    notebook_id TEXT NOT NULL,
    memory_type TEXT NOT NULL,  
    content TEXT NOT NULL,       
    metadata TEXT,               
    tags TEXT,                   
    embedding BLOB,              
    importance REAL DEFAULT 0.5, 
    access_count INTEGER DEFAULT 0,  
    last_accessed TEXT,          
    created TEXT NOT NULL,       
    updated TEXT NOT NULL, layer TEXT, agent_id TEXT, source_message_id TEXT, expires_at TEXT,       
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE
);
CREATE TABLE agent_messages (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    sender_id TEXT NOT NULL,      
    recipient_id TEXT,            
    message_type TEXT NOT NULL DEFAULT 'chat',  
    content TEXT NOT NULL,
    metadata TEXT,                
    created TEXT NOT NULL, execution_id TEXT,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE
);
CREATE TABLE agent_prompt_templates (
    id TEXT PRIMARY KEY,
    role TEXT NOT NULL UNIQUE,            
    name TEXT NOT NULL,                   
    description TEXT,                     
    prompt_text TEXT NOT NULL,            
    default_prompt_text TEXT NOT NULL,    
    is_default INTEGER NOT NULL DEFAULT 1, 
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS "agent_skill_bindings" (
    id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL,
    agent_id TEXT,
    standalone_agent_id TEXT,
    role TEXT,
    team_id TEXT,
    binding_type TEXT NOT NULL,
    priority INTEGER DEFAULT 0,
    config TEXT,
    enabled INTEGER DEFAULT 1,
    created TEXT NOT NULL DEFAULT (datetime('now')),
    created_by TEXT,

    FOREIGN KEY (skill_id) REFERENCES agent_skills(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES agent_instances(id) ON DELETE CASCADE,
    FOREIGN KEY (standalone_agent_id) REFERENCES standalone_agents(id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE,

    CHECK (
        (binding_type = 'agent' AND agent_id IS NOT NULL AND standalone_agent_id IS NULL AND role IS NULL AND team_id IS NULL) OR
        (binding_type = 'standalone_agent' AND standalone_agent_id IS NOT NULL AND agent_id IS NULL AND role IS NULL AND team_id IS NULL) OR
        (binding_type = 'role' AND role IS NOT NULL AND agent_id IS NULL AND standalone_agent_id IS NULL AND team_id IS NULL) OR
        (binding_type = 'team' AND team_id IS NOT NULL AND agent_id IS NULL AND standalone_agent_id IS NULL AND role IS NULL)
    )
);
CREATE TABLE IF NOT EXISTS "agent_skill_executions" (
    id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL,
    execution_id TEXT NOT NULL,
    agent_id TEXT,
    team_id TEXT,
    input_data TEXT,
    output_data TEXT,
    success INTEGER NOT NULL,
    result TEXT,
    error TEXT,
    duration_ms REAL,
    trace_id TEXT,
    steps TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    created TEXT NOT NULL DEFAULT (datetime('now')),

    FOREIGN KEY (skill_id) REFERENCES agent_skills(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES agent_instances(id) ON DELETE SET NULL,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE SET NULL
);
CREATE TABLE agent_skills (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,         
    description TEXT,
    skill_type TEXT NOT NULL,       
    definition TEXT NOT NULL,       
    input_schema TEXT,              
    output_schema TEXT,             
    roles TEXT,                     
    tags TEXT,                      
    enabled INTEGER NOT NULL DEFAULT 1,
    metadata TEXT,                  
    created TEXT NOT NULL DEFAULT (datetime('now')),
    updated TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE agent_tasks (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    assignee_id TEXT,             
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'pending',  
    priority INTEGER NOT NULL DEFAULT 0,     
    result TEXT,                  
    error TEXT,
    depends_on TEXT,              
    started_at TEXT,
    completed_at TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL, execution_id TEXT,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE CASCADE,
    FOREIGN KEY (assignee_id) REFERENCES agent_instances(id) ON DELETE SET NULL
);
CREATE TABLE agent_teams (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    goal TEXT,
    status TEXT NOT NULL DEFAULT 'pending',  
    notebook_id TEXT,
    session_id TEXT,
    config TEXT,        
    result TEXT,        
    error TEXT,
    started_at TEXT,
    completed_at TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL, created_by VARCHAR(36), orchestration_pattern TEXT DEFAULT 'orchestrator_worker', pattern_config TEXT,
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE SET NULL,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE SET NULL
);
CREATE TABLE api_connection_endpoints (
    id TEXT PRIMARY KEY,
    connection_id TEXT NOT NULL,
    endpoint_path TEXT NOT NULL,  
    method TEXT NOT NULL,  
    description TEXT,
    parameters TEXT,  
    request_body_schema TEXT,  
    response_schema TEXT,  
    discovered_at TEXT NOT NULL,
    discovery_source TEXT,  

    FOREIGN KEY (connection_id) REFERENCES api_connections(id) ON DELETE CASCADE,
    UNIQUE(connection_id, endpoint_path, method)
);
CREATE TABLE api_connections (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,

    
    endpoint TEXT NOT NULL,
    auth_type TEXT NOT NULL, 

    
    auth_config_encrypted TEXT,

    
    headers TEXT,

    
    method TEXT DEFAULT 'GET',
    query_params TEXT, 
    request_body TEXT, 

    
    data_path TEXT, 
    id_field TEXT DEFAULT 'id',
    content_fields TEXT, 

    
    created TEXT,
    updated TEXT,
    last_tested TEXT,
    test_status TEXT, 
    test_message TEXT, created_by VARCHAR(36),

    
    UNIQUE(name)
);
CREATE TABLE api_key_usage_logs (
    id TEXT PRIMARY KEY,
    api_key_id TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    status_code INTEGER,
    ip_address TEXT,
    user_agent TEXT,
    request_body TEXT,  
    response_body TEXT,  
    error TEXT,  
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (api_key_id) REFERENCES api_keys(id) ON DELETE CASCADE
);
CREATE TABLE api_keys (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,  
    description TEXT,  
    key_hash TEXT NOT NULL UNIQUE,  
    key_prefix TEXT NOT NULL,  

    
    scopes TEXT NOT NULL,  

    
    owner_id TEXT NOT NULL,  
    application_name TEXT,  

    
    last_used_at TIMESTAMP,
    usage_count INTEGER DEFAULT 0,

    
    is_active INTEGER DEFAULT 1,
    expires_at TIMESTAMP,

    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE bookmark_embeddings (
    id VARCHAR(36) PRIMARY KEY,
    bookmark_id VARCHAR(36) NOT NULL,
    content TEXT NOT NULL,  
    embedding BLOB NOT NULL,  
    created TEXT NOT NULL,
    FOREIGN KEY (bookmark_id) REFERENCES user_bookmarks(id) ON DELETE CASCADE
);
CREATE TABLE chat_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,  
    content TEXT NOT NULL,
    created TEXT NOT NULL, agent_steps TEXT, langfuse_trace_id TEXT, langfuse_observation_id TEXT, ui_components TEXT, render_mode TEXT DEFAULT 'markdown', tool_results TEXT, sources TEXT,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
);
CREATE TABLE chat_sessions (
    id TEXT PRIMARY KEY,
    title TEXT,
    notebook_id TEXT NOT NULL,
    created TEXT NOT NULL,
    updated TEXT NOT NULL, model_override TEXT, created_by VARCHAR(36),
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE
);
CREATE TABLE classification_relationships (
    id TEXT PRIMARY KEY,
    source_classification_id TEXT NOT NULL,
    target_classification_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,  
    strength REAL,  
    created TEXT NOT NULL,
    FOREIGN KEY (source_classification_id) REFERENCES classification_types(id) ON DELETE CASCADE,
    FOREIGN KEY (target_classification_id) REFERENCES classification_types(id) ON DELETE CASCADE,
    UNIQUE(source_classification_id, target_classification_id, relationship_type)
);
CREATE TABLE classification_types (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    classification_type TEXT NOT NULL,  
    parent_id TEXT,  
    level INTEGER DEFAULT 0,  
    color TEXT,  
    icon TEXT,  
    created TEXT NOT NULL,
    updated TEXT,
    FOREIGN KEY (parent_id) REFERENCES classification_types(id) ON DELETE CASCADE
);
CREATE TABLE content_blocklist (
    id TEXT PRIMARY KEY,
    keyword TEXT NOT NULL,
    category TEXT DEFAULT 'custom',  
    severity TEXT DEFAULT 'warning', 
    is_regex INTEGER DEFAULT 0,      
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);
CREATE TABLE content_moderation_logs (
    id TEXT PRIMARY KEY,
    microsite_id TEXT NOT NULL,
    content_section TEXT,            
    moderation_type TEXT NOT NULL,   
    status TEXT NOT NULL,            
    score REAL,                      
    issues_found TEXT,               
    metadata TEXT,                   
    created TEXT NOT NULL,
    FOREIGN KEY (microsite_id) REFERENCES microsites(id) ON DELETE CASCADE
);
CREATE TABLE credentials (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    modalities TEXT,  
    api_key_encrypted TEXT,
    base_url TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL
, source TEXT DEFAULT 'litellm', auth_url TEXT, api_url TEXT, client_id TEXT, client_secret_encrypted TEXT, resource_group TEXT DEFAULT 'default', deployment_id TEXT, identity_zone TEXT, identityzoneid TEXT, model_name TEXT, model_type TEXT, is_active INTEGER DEFAULT 1, connection_status TEXT, last_tested TEXT);
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('person', 'organization', 'location', 'event', 'concept', 'other')),
    description TEXT,
    source_id TEXT NOT NULL,
    chunk_id TEXT,  
    metadata TEXT,  
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE,
    FOREIGN KEY (chunk_id) REFERENCES source_embeddings(id) ON DELETE CASCADE
);
CREATE TABLE entity_communities (
    id TEXT PRIMARY KEY,
    name TEXT,
    description TEXT,  
    level INTEGER DEFAULT 0,  
    parent_community_id TEXT,  
    entity_ids TEXT NOT NULL,  
    metadata TEXT,  
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_community_id) REFERENCES entity_communities(id) ON DELETE CASCADE
);
CREATE TABLE entity_embeddings (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    embedding BLOB NOT NULL,  
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE
);
CREATE TABLE entity_relationships (
    id TEXT PRIMARY KEY,
    source_entity_id TEXT NOT NULL,
    target_entity_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,  
    context TEXT,  
    chunk_id TEXT,  
    strength REAL DEFAULT 0.5 CHECK (strength BETWEEN 0.0 AND 1.0),
    metadata TEXT,  
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (target_entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (chunk_id) REFERENCES source_embeddings(id) ON DELETE SET NULL,
    UNIQUE(source_entity_id, target_entity_id, relationship_type)
);
CREATE TABLE evaluation_datasets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    agent_id TEXT,  
    created_by TEXT,

    
    test_case_count INTEGER DEFAULT 0,
    file_name TEXT,  
    file_format TEXT,  

    
    criteria TEXT,  
    scoring_method TEXT DEFAULT 'llm_judge',  

    created TEXT NOT NULL,
    updated TEXT NOT NULL, target_type TEXT NOT NULL DEFAULT 'agent', workflow_id TEXT,

    FOREIGN KEY (agent_id) REFERENCES standalone_agents(id) ON DELETE SET NULL
);
CREATE TABLE evaluation_results (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    test_case_id TEXT NOT NULL,

    
    agent_output TEXT NOT NULL,
    execution_time_ms REAL,

    
    passed BOOLEAN NOT NULL DEFAULT 0,
    overall_score REAL,  
    criteria_scores TEXT,  

    
    similarity_score REAL,  
    exact_match BOOLEAN,

    
    feedback TEXT,  
    judge_reasoning TEXT,  

    
    error_occurred BOOLEAN DEFAULT 0,
    error_message TEXT,

    created TEXT NOT NULL, actual_tool_calls TEXT, tool_calls_passed INTEGER,

    FOREIGN KEY (run_id) REFERENCES evaluation_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (test_case_id) REFERENCES evaluation_test_cases(id) ON DELETE CASCADE
);
CREATE TABLE evaluation_test_cases (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,

    
    input_prompt TEXT NOT NULL,
    expected_output TEXT,  
    context TEXT,  
    metadata TEXT,  

    
    tags TEXT,  
    category TEXT,  

    created TEXT NOT NULL, expected_tool_calls TEXT,

    FOREIGN KEY (dataset_id) REFERENCES evaluation_datasets(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "execution_messages" (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    from_agent_id TEXT NOT NULL,
    to_agent_id TEXT,
    message_type TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT,
    created TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (execution_id) REFERENCES agent_executions(id) ON DELETE CASCADE,
    FOREIGN KEY (from_agent_id) REFERENCES agent_instances(id) ON DELETE CASCADE,
    FOREIGN KEY (to_agent_id) REFERENCES agent_instances(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "folders" (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    parent_id TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    notebook_id TEXT REFERENCES notebooks(id) ON DELETE SET NULL,
    folder_type TEXT DEFAULT 'user',
    metadata TEXT,
    FOREIGN KEY (parent_id) REFERENCES folders(id) ON DELETE CASCADE
);
CREATE TABLE graph_layouts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    scope TEXT NOT NULL CHECK (scope IN ('global', 'notebook')),
    scope_id TEXT,  
    layout_data TEXT NOT NULL,  
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scope_id) REFERENCES notebooks(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "guided_workspace_sessions" (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    goal TEXT NOT NULL,
    analysis TEXT,
    clarifications TEXT,
    selected_resources TEXT,
    generated_plan TEXT,
    status TEXT DEFAULT 'draft' CHECK(status IN ('draft', 'active', 'completed', 'abandoned', 'expired')),
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    current_step TEXT,
    clarification_answers TEXT,
    discovered_resources TEXT,
    workspace_id TEXT,
    plan TEXT
);
CREATE TABLE hana_connection_tables (
    id TEXT PRIMARY KEY,
    connection_id TEXT NOT NULL,
    schema_name TEXT,
    table_name TEXT NOT NULL,
    table_type TEXT,  
    column_metadata TEXT,  
    row_count INTEGER,
    discovered_at TEXT NOT NULL,

    FOREIGN KEY (connection_id) REFERENCES hana_connections(id) ON DELETE CASCADE,
    UNIQUE(connection_id, schema_name, table_name)
);
CREATE TABLE hana_connections (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    host TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 443,
    database TEXT NOT NULL,
    user TEXT NOT NULL,
    password_encrypted TEXT NOT NULL,  
    encrypt INTEGER NOT NULL DEFAULT 1,  
    schema TEXT,  
    description TEXT,  
    created TEXT NOT NULL,
    updated TEXT NOT NULL
, created_by VARCHAR(36));
CREATE TABLE mcp_oauth_clients (
    server_id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    client_secret TEXT,                    
    registration_data TEXT,                
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS "mcp_servers" (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    protocol TEXT NOT NULL,

    
    command TEXT,
    args TEXT,
    env_vars TEXT,

    
    url TEXT,
    headers TEXT,
    auth_type TEXT,
    auth_config_encrypted TEXT,

    
    status TEXT DEFAULT 'untested',
    last_test_at TEXT,
    last_test_message TEXT,

    
    capabilities TEXT,

    
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL, oauth_mode TEXT NOT NULL DEFAULT 'user',

    
    CHECK (protocol IN ('stdio', 'http')),
    CHECK (status IN ('untested', 'connected', 'error', 'disconnected', 'needs_auth')),
    CHECK (auth_type IS NULL OR auth_type IN ('none', 'bearer', 'api_key', 'auto', 'oauth'))
);
CREATE TABLE mcp_tools (
    id TEXT PRIMARY KEY,
    server_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    description TEXT,
    input_schema TEXT,       
    discovered_at TEXT NOT NULL,

    FOREIGN KEY (server_id) REFERENCES mcp_servers(id) ON DELETE CASCADE,
    UNIQUE(server_id, tool_name)
);
CREATE TABLE microsite_access (
    id TEXT PRIMARY KEY,
    microsite_id TEXT NOT NULL,
    email TEXT NOT NULL,
    created TEXT NOT NULL,
    FOREIGN KEY (microsite_id) REFERENCES microsites(id) ON DELETE CASCADE,
    UNIQUE(microsite_id, email)
);
CREATE TABLE microsite_content (
    id TEXT PRIMARY KEY,
    microsite_id TEXT NOT NULL,
    section_id TEXT NOT NULL,       
    content_html TEXT,              
    content_json TEXT,              
    order_num INTEGER DEFAULT 0,   
    is_visible INTEGER DEFAULT 1,  
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (microsite_id) REFERENCES microsites(id) ON DELETE CASCADE
);
CREATE TABLE microsite_otp (
    id TEXT PRIMARY KEY,
    microsite_id TEXT NOT NULL,
    email TEXT NOT NULL,
    otp_code TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    verified INTEGER DEFAULT 0,
    created TEXT NOT NULL,
    FOREIGN KEY (microsite_id) REFERENCES microsites(id) ON DELETE CASCADE
);
CREATE TABLE microsite_sources (
    microsite_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    created TEXT NOT NULL,
    PRIMARY KEY (microsite_id, source_id),
    FOREIGN KEY (microsite_id) REFERENCES microsites(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
);
CREATE TABLE microsite_templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    description TEXT,
    structure TEXT NOT NULL,       
    default_styles TEXT,           
    preview_image TEXT,            
    is_custom INTEGER DEFAULT 0,  
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);
CREATE TABLE microsite_versions (
    id TEXT PRIMARY KEY,
    microsite_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    full_html TEXT,                  
    full_css TEXT,                   
    content_snapshot TEXT,           
    created_by TEXT,                 
    created TEXT NOT NULL, status_at_publish TEXT, published_at TEXT,
    FOREIGN KEY (microsite_id) REFERENCES microsites(id) ON DELETE CASCADE,
    UNIQUE(microsite_id, version_number)
);
CREATE TABLE microsites (
    id TEXT PRIMARY KEY,
    notebook_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    slug TEXT UNIQUE NOT NULL,
    theme TEXT DEFAULT 'light',
    is_active INTEGER DEFAULT 1,
    created TEXT NOT NULL,
    updated TEXT NOT NULL, created_by VARCHAR(36), template_id TEXT REFERENCES microsite_templates(id) ON DELETE SET NULL, custom_css TEXT, custom_js TEXT, generation_config TEXT, moderation_status TEXT DEFAULT 'pending', published_version INTEGER, last_generated TEXT, status TEXT NOT NULL DEFAULT 'draft', active_version_id TEXT,
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE
);
CREATE TABLE models (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    provider TEXT NOT NULL,
    type TEXT NOT NULL,  
    credential_id TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (credential_id) REFERENCES credentials(id) ON DELETE SET NULL
);
CREATE TABLE note_links (
    id TEXT PRIMARY KEY,
    source_note_id TEXT NOT NULL,
    target_note_id TEXT NOT NULL,
    created TEXT NOT NULL,
    FOREIGN KEY (source_note_id) REFERENCES notes(id) ON DELETE CASCADE,
    FOREIGN KEY (target_note_id) REFERENCES notes(id) ON DELETE CASCADE,
    UNIQUE(source_note_id, target_note_id)
);
CREATE TABLE note_tags (
    note_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
    PRIMARY KEY (note_id, tag)
);
CREATE TABLE notebook_note (
    notebook_id TEXT NOT NULL,
    note_id TEXT NOT NULL,
    created TEXT NOT NULL,
    PRIMARY KEY (notebook_id, note_id),
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE,
    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
);
CREATE TABLE notebook_source (
    notebook_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    created TEXT NOT NULL,
    PRIMARY KEY (notebook_id, source_id),
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
);
CREATE TABLE notebook_tags (
    notebook_id TEXT NOT NULL,
    tag_id TEXT NOT NULL,
    PRIMARY KEY (notebook_id, tag_id),
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);
CREATE TABLE notebooks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    folder_id TEXT,
    archived INTEGER DEFAULT 0,
    created TEXT NOT NULL,
    updated TEXT NOT NULL, created_by VARCHAR(36), tags TEXT DEFAULT '[]', goal TEXT, protected INTEGER DEFAULT 0,
    FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS "notes" (
    id TEXT PRIMARY KEY,
    title TEXT,
    summary TEXT,
    content TEXT,
    embedding TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    content_html TEXT,
    folder_id TEXT,
    metadata TEXT,
    notebook_id TEXT REFERENCES notebooks(id) ON DELETE SET NULL
);
CREATE TABLE notifications (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    type TEXT NOT NULL,  
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    category TEXT,  
    priority TEXT DEFAULT 'normal',  

    
    entity_type TEXT,  
    entity_id TEXT,

    
    action_url TEXT,
    action_label TEXT,

    
    metadata TEXT,  

    
    is_read INTEGER DEFAULT 0,
    is_archived INTEGER DEFAULT 0,
    read_at TIMESTAMP,

    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,  

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE oauth_applications (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    owner_user_id TEXT NOT NULL,
    client_id TEXT UNIQUE NOT NULL,
    client_secret_encrypted TEXT NOT NULL,
    scopes TEXT NOT NULL,  
    redirect_uris TEXT,  
    grant_types TEXT DEFAULT 'client_credentials',
    status TEXT DEFAULT 'active',  
    rate_limit_per_hour INTEGER DEFAULT 1000,
    rate_limit_per_day INTEGER DEFAULT 10000,
    token_expiry_seconds INTEGER DEFAULT 3600,
    last_used_at TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (owner_user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE oauth_audit_log (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    app_id TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    status_code INTEGER,
    scopes_used TEXT,  
    ip_address TEXT,
    user_agent TEXT,
    response_time_ms INTEGER,
    created TEXT NOT NULL,
    FOREIGN KEY (app_id) REFERENCES oauth_applications(id) ON DELETE CASCADE
);
CREATE TABLE oauth_authorization_codes (
    id TEXT PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    app_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    redirect_uri TEXT NOT NULL,
    scopes TEXT NOT NULL,  
    code_challenge TEXT,  
    code_challenge_method TEXT,  
    expires_at TEXT NOT NULL,
    used INTEGER DEFAULT 0,  
    created TEXT NOT NULL,
    FOREIGN KEY (app_id) REFERENCES oauth_applications(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE oauth_refresh_tokens (
    id TEXT PRIMARY KEY,
    token TEXT UNIQUE NOT NULL,
    app_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    scopes TEXT NOT NULL,  
    expires_at TEXT NOT NULL,
    revoked INTEGER DEFAULT 0,  
    created TEXT NOT NULL,
    FOREIGN KEY (app_id) REFERENCES oauth_applications(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE oauth_revoked_tokens (
    jti TEXT PRIMARY KEY,  
    revoked_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    reason TEXT
);
CREATE TABLE oauth_scopes (
    id TEXT PRIMARY KEY,
    scope TEXT UNIQUE NOT NULL,
    resource_type TEXT NOT NULL,
    action TEXT NOT NULL,
    description TEXT,
    is_system_only INTEGER DEFAULT 0,
    created TEXT NOT NULL
);
CREATE TABLE orchestration_action_bindings (
    id TEXT PRIMARY KEY,

    
    schedule_id TEXT,  
    orchestration_id TEXT,  

    action_id TEXT NOT NULL,

    
    trigger_condition TEXT NOT NULL,  
    phase_filter TEXT,  

    
    execution_order INTEGER DEFAULT 0,

    
    is_active INTEGER DEFAULT 1,

    
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    
    FOREIGN KEY (schedule_id) REFERENCES orchestration_schedules(id) ON DELETE CASCADE,
    FOREIGN KEY (orchestration_id) REFERENCES orchestrations(id) ON DELETE CASCADE,
    FOREIGN KEY (action_id) REFERENCES actions(id) ON DELETE CASCADE,

    
    CHECK (
        (schedule_id IS NOT NULL AND orchestration_id IS NULL) OR
        (schedule_id IS NULL AND orchestration_id IS NOT NULL)
    )
);
CREATE TABLE orchestration_configs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,

    
    prefer_team_over_single BOOLEAN DEFAULT 0,
    prefer_swarm_over_team BOOLEAN DEFAULT 0,

    
    max_team_size INTEGER DEFAULT 10,
    max_concurrent_tasks INTEGER DEFAULT 5,
    enable_parallel_execution BOOLEAN DEFAULT 1,

    
    max_execution_duration_seconds INTEGER DEFAULT 600,
    max_llm_tokens_per_orchestration INTEGER DEFAULT 100000,

    
    decision_model TEXT,
    planner_model TEXT,
    synthesizer_model TEXT,

    
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE orchestration_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    orchestration_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_data TEXT,  
    timestamp TEXT NOT NULL,
    FOREIGN KEY (orchestration_id) REFERENCES orchestrations(id) ON DELETE CASCADE
);
CREATE TABLE orchestration_executions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    notebook_id TEXT,
    goal TEXT NOT NULL,
    status TEXT NOT NULL,  
    orchestration_mode TEXT,  
    team_id TEXT,

    
    complexity TEXT,
    intent TEXT,
    required_capabilities TEXT,  

    
    execution_plan TEXT,  
    parallel_groups TEXT,  

    
    current_phase TEXT,
    progress REAL DEFAULT 0.0,

    
    result TEXT,  
    error TEXT,

    
    started_at TEXT NOT NULL,
    completed_at TEXT,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE SET NULL
);
CREATE TABLE orchestration_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    orchestration_id TEXT NOT NULL,

    
    analysis_duration_ms INTEGER,
    decision_duration_ms INTEGER,
    spawning_duration_ms INTEGER,
    planning_duration_ms INTEGER,
    execution_duration_ms INTEGER,
    synthesis_duration_ms INTEGER,
    total_duration_ms INTEGER,

    
    task_count INTEGER DEFAULT 0,
    parallel_task_count INTEGER DEFAULT 0,
    sequential_task_count INTEGER DEFAULT 0,
    handover_count INTEGER DEFAULT 0,

    
    agent_count INTEGER DEFAULT 0,
    tool_call_count INTEGER DEFAULT 0,
    llm_token_usage INTEGER DEFAULT 0,

    
    speedup_ratio REAL,  
    resource_utilization REAL,  

    created_at TEXT NOT NULL,

    FOREIGN KEY (orchestration_id) REFERENCES orchestration_executions(id) ON DELETE CASCADE
);
CREATE TABLE orchestration_resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    orchestration_id TEXT NOT NULL,
    resource_type TEXT NOT NULL,  
    resource_id TEXT NOT NULL,
    resource_name TEXT,
    usage_count INTEGER DEFAULT 0,

    FOREIGN KEY (orchestration_id) REFERENCES orchestration_executions(id) ON DELETE CASCADE
);
CREATE TABLE orchestration_schedules (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    goal TEXT NOT NULL,
    notebook_id TEXT,
    resources TEXT,  -- JSON serialized resources
    config TEXT,     -- JSON serialized config
    schedule_type TEXT NOT NULL CHECK(schedule_type IN ('once', 'recurring')),
    schedule_config TEXT NOT NULL,  -- JSON: {datetime} for once, {cron} for recurring
    next_run TEXT,   -- ISO datetime of next execution
    last_run TEXT,   -- ISO datetime of last execution
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'paused', 'completed', 'failed')),
    execution_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL, template_id TEXT REFERENCES workspace_templates(id) ON DELETE SET NULL, parameters TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE orchestrations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    goal TEXT NOT NULL,
    notebook_id TEXT,
    status TEXT NOT NULL DEFAULT 'starting',
    current_phase TEXT DEFAULT 'starting',
    progress REAL DEFAULT 0.0,
    orchestration_mode TEXT,
    team_id TEXT,
    result TEXT,  
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
, schedule_id TEXT, template_id TEXT REFERENCES workspace_templates(id) ON DELETE SET NULL, workspace_instance_id TEXT REFERENCES notebooks(id) ON DELETE SET NULL);
CREATE TABLE presentation_content (
    id TEXT PRIMARY KEY,
    presentation_id TEXT NOT NULL,
    slide_number INTEGER NOT NULL,
    slide_type TEXT NOT NULL,  
    content_html TEXT,          
    content_json TEXT NOT NULL, 
    speaker_notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (presentation_id) REFERENCES presentations(id) ON DELETE CASCADE,
    UNIQUE(presentation_id, slide_number)
);
CREATE TABLE presentation_sources (
    presentation_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (presentation_id, source_id),
    FOREIGN KEY (presentation_id) REFERENCES presentations(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
);
CREATE TABLE presentation_templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    theme_json TEXT NOT NULL,  
    slide_layouts TEXT,         
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE presentation_versions (
    id TEXT PRIMARY KEY,
    presentation_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    slides_snapshot TEXT NOT NULL,  
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    FOREIGN KEY (presentation_id) REFERENCES presentations(id) ON DELETE CASCADE,
    UNIQUE(presentation_id, version_number)
);
CREATE TABLE presentations (
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
CREATE TABLE resource_shares (
    id VARCHAR(36) PRIMARY KEY,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(36) NOT NULL,
    shared_by VARCHAR(36) NOT NULL,
    shared_with_user VARCHAR(36),
    shared_with_role VARCHAR(36),
    permission_level VARCHAR(20) NOT NULL CHECK (permission_level IN ('read', 'write', 'admin')),
    expires_at TEXT,
    created TEXT NOT NULL,
    FOREIGN KEY (shared_by) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (shared_with_user) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (shared_with_role) REFERENCES roles(id) ON DELETE CASCADE,
    CHECK (shared_with_user IS NOT NULL OR shared_with_role IS NOT NULL)
);
CREATE TABLE role_permissions (
    id VARCHAR(36) PRIMARY KEY,
    role_id VARCHAR(36) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    scope VARCHAR(20) DEFAULT 'own' CHECK (scope IN ('own', 'team', 'all')),
    conditions TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
    UNIQUE(role_id, resource_type, action)
);
CREATE TABLE roles (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,
    is_system_role INTEGER DEFAULT 0,
    created_by VARCHAR(36),
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE search_config (
    id TEXT PRIMARY KEY,
    user_id TEXT,  
    default_strategy TEXT,  
    config TEXT,  
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'string',  
    description TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);
CREATE TABLE smtp_config (
    id TEXT PRIMARY KEY DEFAULT 'default',
    smtp_host TEXT NOT NULL,
    smtp_port INTEGER NOT NULL,
    smtp_username TEXT NOT NULL,
    smtp_password TEXT NOT NULL,
    smtp_from_email TEXT NOT NULL,
    smtp_from_name TEXT,
    smtp_use_tls INTEGER DEFAULT 1,
    smtp_use_ssl INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);
CREATE TABLE source_classifications (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    classification_id TEXT NOT NULL,
    confidence REAL,  
    status TEXT DEFAULT 'pending',  
    approved_by TEXT,  
    approved_at TEXT,  
    metadata TEXT,  
    created TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE,
    FOREIGN KEY (classification_id) REFERENCES classification_types(id) ON DELETE CASCADE,
    UNIQUE(source_id, classification_id)
);
CREATE TABLE source_embeddings (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    order_num INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding TEXT,  
    created TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
);
CREATE TABLE source_similarities (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    related_source_id TEXT NOT NULL,
    similarity_score REAL NOT NULL CHECK (similarity_score >= 0.0 AND similarity_score <= 1.0),
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, related_source_id),
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE,
    FOREIGN KEY (related_source_id) REFERENCES sources(id) ON DELETE CASCADE
);
CREATE TABLE sources (
    id TEXT PRIMARY KEY,
    title TEXT,
    source_type TEXT NOT NULL,  
    full_text TEXT,
    topics TEXT,  
    asset_type TEXT,  
    asset_data TEXT,  
    connection_config TEXT,  
    sync_config TEXT,  
    created TEXT NOT NULL,
    updated TEXT NOT NULL
, created_by VARCHAR(36), tags TEXT DEFAULT '[]');
CREATE VIRTUAL TABLE sources_fts USING fts5(
    id UNINDEXED,
    title,
    full_text,
    content='sources',
    content_rowid='rowid'
)
/* sources_fts(id,title,full_text) */;
CREATE TABLE IF NOT EXISTS 'sources_fts_data'(id INTEGER PRIMARY KEY, block BLOB);
CREATE TABLE IF NOT EXISTS 'sources_fts_idx'(segid, term, pgno, PRIMARY KEY(segid, term)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS 'sources_fts_docsize'(id INTEGER PRIMARY KEY, sz BLOB);
CREATE TABLE IF NOT EXISTS 'sources_fts_config'(k PRIMARY KEY, v) WITHOUT ROWID;
CREATE TABLE standalone_agent_executions (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    query TEXT NOT NULL,          
    status TEXT NOT NULL DEFAULT 'running',  

    
    session_id TEXT,              
    notebook_id TEXT,             
    context TEXT,                 

    
    result TEXT,                  
    error TEXT,
    steps TEXT,                   
    tool_calls TEXT,              

    
    started_at TEXT,
    completed_at TEXT,
    duration_ms INTEGER,

    
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (agent_id) REFERENCES standalone_agents(id) ON DELETE CASCADE,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE SET NULL,
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE SET NULL
);
CREATE TABLE standalone_agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    role TEXT NOT NULL,           
    system_prompt TEXT,
    model_name TEXT,              
    notebook_id TEXT,             

    
    config TEXT,                  

    
    tool_ids TEXT,                
    mcp_server_ids TEXT,          
    data_source_ids TEXT,         

    
    status TEXT NOT NULL DEFAULT 'active',  

    
    created TEXT NOT NULL,
    updated TEXT NOT NULL, skill_ids TEXT DEFAULT '[]', created_by VARCHAR(36),
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE SET NULL
);
CREATE TABLE sync_history (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    status TEXT NOT NULL,  
    started_at TEXT NOT NULL,
    completed_at TEXT,
    rows_updated INTEGER DEFAULT 0,
    duration_seconds REAL,
    error TEXT,
    created TEXT NOT NULL DEFAULT (datetime('now')),
    updated TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
);
CREATE TABLE system_prompt_templates (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,                       
    template_key TEXT NOT NULL UNIQUE,            
    name TEXT NOT NULL,                           
    description TEXT,                             
    prompt_text TEXT NOT NULL,                    
    default_prompt_text TEXT NOT NULL,            
    variables TEXT,                               
    metadata TEXT,                                
    is_default INTEGER NOT NULL DEFAULT 1,        
    is_active INTEGER NOT NULL DEFAULT 1,         
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);
CREATE TABLE tags (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    color TEXT
);
CREATE TABLE IF NOT EXISTS "template_executions" (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    template_id TEXT NOT NULL,
    target_workspace_id TEXT,  
    folder_id TEXT,


    parameters TEXT,


    result_note_id TEXT,
    status TEXT NOT NULL,
    error TEXT,


    current_phase TEXT,
    progress REAL DEFAULT 0.0,


    started_at TEXT NOT NULL,
    completed_at TEXT,
    duration_ms INTEGER,


    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (template_id) REFERENCES workspace_templates(id) ON DELETE CASCADE,
    FOREIGN KEY (target_workspace_id) REFERENCES notebooks(id) ON DELETE SET NULL,
    FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE SET NULL,
    FOREIGN KEY (result_note_id) REFERENCES notes(id) ON DELETE SET NULL
);
CREATE TABLE tool_permissions (
    id TEXT PRIMARY KEY,
    tool_id TEXT NOT NULL,
    user_id TEXT,                   
    role TEXT,                      
    allowed INTEGER NOT NULL DEFAULT 1,
    rate_limit INTEGER,            
    custom_config TEXT,            
    created TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (tool_id) REFERENCES tool_registry(id) ON DELETE CASCADE,
    
    CHECK ((user_id IS NOT NULL AND role IS NULL) OR (user_id IS NULL AND role IS NOT NULL))
);
CREATE TABLE tool_registry (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    tool_type TEXT NOT NULL,        
    category TEXT NOT NULL,         
    description TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    default_config TEXT,            
    metadata TEXT,                  
    created TEXT NOT NULL DEFAULT (datetime('now')),
    updated TEXT NOT NULL DEFAULT (datetime('now'))
, created_by VARCHAR(36));
CREATE TABLE tool_usage_log (
    id TEXT PRIMARY KEY,
    tool_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    notebook_id TEXT NOT NULL,
    input_params TEXT,             
    execution_time_ms INTEGER,
    success INTEGER NOT NULL DEFAULT 1,
    error_message TEXT,
    created TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (tool_id) REFERENCES tool_registry(id) ON DELETE CASCADE
);
CREATE TABLE transformations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    title TEXT,
    description TEXT,
    prompt TEXT NOT NULL,
    apply_default INTEGER DEFAULT 0,
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);
CREATE TABLE user_bookmarks (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,              
    entity_id VARCHAR(36) NOT NULL,
    custom_note TEXT,
    reason TEXT,
    bookmarked_at TEXT NOT NULL,
    created TEXT NOT NULL,
    updated TEXT NOT NULL, tags TEXT, category TEXT,
    UNIQUE(user_id, entity_type, entity_id)
);
CREATE TABLE user_query_prompts (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    query_text TEXT NOT NULL,
    description TEXT,
    category VARCHAR(100),
    team_id VARCHAR(36),  
    prompt_role VARCHAR(50),  
    tags TEXT,  
    use_count INTEGER DEFAULT 0,
    last_used TEXT,
    is_favorite INTEGER DEFAULT 0,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (team_id) REFERENCES agent_teams(id) ON DELETE SET NULL
);
CREATE TABLE user_roles (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL,
    role_id VARCHAR(36) NOT NULL,
    assigned_by VARCHAR(36),
    assigned_at TEXT NOT NULL, created TEXT DEFAULT (datetime('now')), updated TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, role_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE users (
    id VARCHAR(36) PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    password_hash TEXT NOT NULL,
    full_name VARCHAR(255),
    avatar_url TEXT,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'deleted')),
    is_superadmin INTEGER DEFAULT 0,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    last_login TEXT
);
CREATE TABLE workflow_approvals (
    id TEXT PRIMARY KEY,
    workflow_id TEXT,
    execution_id TEXT,
    node_id TEXT NOT NULL,
    approval_prompt TEXT NOT NULL,
    approval_options TEXT NOT NULL,
    required_approvers TEXT,
    input_data TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    response TEXT,
    comment TEXT,
    approved_by TEXT,
    timeout_seconds INTEGER,
    timeout_action TEXT,
    timeout_at TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    responded_at TEXT
);
CREATE TABLE workflow_executions (
    id VARCHAR(36) PRIMARY KEY,
    workflow_id VARCHAR(36) NOT NULL,
    status VARCHAR(20) NOT NULL,  
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    node_states TEXT,  
    final_output TEXT,  
    error TEXT,  
    triggered_by VARCHAR(20), current_node_id TEXT, paused_at TEXT, paused_reason TEXT, resume_data TEXT,  
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
);
CREATE TABLE workflow_schedules (
    id VARCHAR(36) PRIMARY KEY,
    workflow_id VARCHAR(36) NOT NULL,
    schedule_type VARCHAR(20) NOT NULL,  
    cron_expression VARCHAR(100),  
    event_trigger TEXT,  
    upstream_workflow_id VARCHAR(36),  
    enabled BOOLEAN DEFAULT TRUE,
    last_run_at TIMESTAMP,
    next_run_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, webhook_secret TEXT, template_id TEXT REFERENCES workflow_templates(id), template_parameters TEXT, input_data TEXT,
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE,
    FOREIGN KEY (upstream_workflow_id) REFERENCES workflows(id) ON DELETE SET NULL
);
CREATE TABLE workflow_snapshots (
    
    id TEXT PRIMARY KEY,

    
    workflow_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    execution_id TEXT,
    user_id TEXT NOT NULL,

    
    snapshot_date TEXT NOT NULL,  
    snapshot_label TEXT,          
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT,              

    
    storage_type TEXT NOT NULL CHECK(storage_type IN ('inline', 'file', 'chunked')),
    storage_path TEXT,            
    inline_data TEXT,             

    
    data_hash TEXT NOT NULL,      
    row_count INTEGER NOT NULL DEFAULT 0,
    total_size_bytes INTEGER NOT NULL DEFAULT 0,
    column_count INTEGER DEFAULT 0,

    
    query_context TEXT NOT NULL,  
    context_hash TEXT NOT NULL,   

    
    stats_summary TEXT,           
    sample_data TEXT,             
    bloom_filter BLOB,            

    
    UNIQUE(workflow_id, node_id, user_id, context_hash, snapshot_date),
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE,
    FOREIGN KEY (execution_id) REFERENCES workflow_executions(id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "workflow_steps" (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    step_number INTEGER NOT NULL,
    agent_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    result TEXT,
    started_at TEXT,
    completed_at TEXT,
    created TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (execution_id) REFERENCES agent_executions(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES agent_instances(id) ON DELETE CASCADE
);
CREATE TABLE workflow_template_executions (
    id TEXT PRIMARY KEY,
    template_id TEXT NOT NULL REFERENCES workflow_templates(id) ON DELETE CASCADE,
    workflow_id TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    execution_id TEXT REFERENCES workflow_executions(id) ON DELETE CASCADE,
    parameters TEXT,
    status TEXT NOT NULL,
    user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT
, trigger_type TEXT DEFAULT 'immediate', schedule_type TEXT, cron_expression TEXT, started_at TEXT, duration_ms INTEGER, template_name TEXT, error TEXT);
CREATE TABLE IF NOT EXISTS "workflow_templates" (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    source_workflow_id TEXT REFERENCES workflows(id) ON DELETE SET NULL,
    graph_json TEXT NOT NULL,
    parameters TEXT,
    version INTEGER DEFAULT 1,
    is_public INTEGER DEFAULT 0,
    tags TEXT,
    usage_count INTEGER DEFAULT 0,
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);
CREATE TABLE workflows (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    graph_json TEXT NOT NULL,  
    created_by VARCHAR(36),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    tags TEXT  
);
CREATE TABLE workspace_documents (
    id TEXT PRIMARY KEY,
    notebook_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    document_type TEXT NOT NULL,  
    file_url TEXT NOT NULL,        
    file_size INTEGER,              
    s3_key TEXT NOT NULL,           
    mime_type TEXT,                 
    metadata TEXT,                  
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    FOREIGN KEY (notebook_id) REFERENCES notebooks(id) ON DELETE CASCADE
);
CREATE TABLE workspace_plan_tasks (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES workspace_plans(id) ON DELETE CASCADE,
    phase_name TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    assigned_agent_id TEXT,     
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'in_progress', 'completed', 'failed', 'skipped')),
    estimated_duration INTEGER, 
    actual_duration INTEGER,    
    dependencies TEXT,          
    required_tools TEXT,        
    required_sources TEXT,      
    result TEXT,                
    error TEXT,                 
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE workspace_plans (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    goal TEXT NOT NULL,
    phases TEXT NOT NULL,          
    collaboration_graph TEXT,      
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'in_progress', 'completed', 'failed', 'cancelled')),
    progress TEXT,                 
    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
, execution_folder_id TEXT);
CREATE TABLE IF NOT EXISTS "workspace_templates" (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    phases TEXT NOT NULL,
    parameters TEXT,
    parameter_schema TEXT,
    is_public INTEGER DEFAULT 0,
    times_used INTEGER DEFAULT 0,
    avg_execution_time_ms INTEGER,
    last_used_at TEXT,
    tags TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    source_workspace_id TEXT REFERENCES notebooks(id) ON DELETE CASCADE,  

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX idx_a2a_agents_card_url ON a2a_agent_registry(card_url);
CREATE INDEX idx_a2a_agents_enabled ON a2a_agent_registry(enabled);
CREATE INDEX idx_a2a_agents_last_synced ON a2a_agent_registry(last_synced);
CREATE INDEX idx_a2a_creds_agent ON a2a_agent_credentials(agent_id);
CREATE INDEX idx_a2a_creds_type ON a2a_agent_credentials(credential_type);
CREATE INDEX idx_a2a_mappings_enabled ON a2a_skill_mappings(enabled);
CREATE INDEX idx_a2a_mappings_local_skill ON a2a_skill_mappings(local_skill_id);
CREATE INDEX idx_a2a_mappings_remote_agent ON a2a_skill_mappings(remote_agent_id);
CREATE INDEX idx_a2a_metrics_agent ON a2a_execution_metrics(agent_id);
CREATE INDEX idx_a2a_metrics_success ON a2a_execution_metrics(success);
CREATE INDEX idx_a2a_metrics_timestamp ON a2a_execution_metrics(timestamp DESC);
CREATE INDEX idx_a2a_tasks_agent ON a2a_task_store(agent_id);
CREATE INDEX idx_a2a_tasks_context ON a2a_task_store(context_id);
CREATE INDEX idx_a2a_tasks_direction ON a2a_task_store(direction);
CREATE INDEX idx_a2a_tasks_skill ON a2a_task_store(skill_id);
CREATE INDEX idx_a2a_tasks_started ON a2a_task_store(started_at DESC);
CREATE INDEX idx_a2a_tasks_state ON a2a_task_store(state);
CREATE INDEX idx_action_executions_action_id ON action_executions(action_id);
CREATE INDEX idx_action_executions_chat_session_id ON action_executions(chat_session_id);
CREATE INDEX idx_action_executions_created_at ON action_executions(created_at DESC);
CREATE INDEX idx_action_executions_orchestration_id ON action_executions(orchestration_id);
CREATE INDEX idx_action_executions_status ON action_executions(status);
CREATE INDEX idx_action_executions_trigger_event ON action_executions(trigger_event);
CREATE INDEX idx_action_executions_user_id ON action_executions(user_id);
CREATE INDEX idx_actions_active ON actions(is_active);
CREATE INDEX idx_actions_created_at ON actions(created_at DESC);
CREATE INDEX idx_actions_type ON actions(action_type);
CREATE INDEX idx_agent_executions_started_at ON agent_executions(started_at DESC);
CREATE INDEX idx_agent_executions_status ON agent_executions(status);
CREATE INDEX idx_agent_executions_team_id ON agent_executions(team_id);
CREATE INDEX idx_agent_instances_remote ON agent_instances(is_remote) WHERE is_remote = 1;
CREATE INDEX idx_agent_instances_role ON agent_instances(role);
CREATE INDEX idx_agent_instances_status ON agent_instances(status);
CREATE INDEX idx_agent_instances_team ON agent_instances(team_id);
CREATE INDEX idx_agent_memory_created ON agent_memory(created DESC);
CREATE INDEX idx_agent_memory_importance ON agent_memory(importance DESC);
CREATE INDEX idx_agent_memory_last_accessed ON agent_memory(last_accessed DESC);
CREATE INDEX idx_agent_memory_notebook ON agent_memory(notebook_id);
CREATE INDEX idx_agent_memory_type ON agent_memory(memory_type);
CREATE INDEX idx_agent_messages_created ON agent_messages(created);
CREATE INDEX idx_agent_messages_execution ON agent_messages(execution_id);
CREATE INDEX idx_agent_messages_recipient ON agent_messages(recipient_id);
CREATE INDEX idx_agent_messages_sender ON agent_messages(sender_id);
CREATE INDEX idx_agent_messages_team ON agent_messages(team_id);
CREATE INDEX idx_agent_skills_category ON agent_skills(category);
CREATE INDEX idx_agent_skills_enabled ON agent_skills(enabled);
CREATE INDEX idx_agent_skills_skill_type ON agent_skills(skill_type);
CREATE INDEX idx_agent_tasks_assignee ON agent_tasks(assignee_id);
CREATE INDEX idx_agent_tasks_status ON agent_tasks(status);
CREATE INDEX idx_agent_tasks_team ON agent_tasks(team_id);
CREATE INDEX idx_agent_teams_created_by ON agent_teams(created_by);
CREATE INDEX idx_agent_teams_notebook ON agent_teams(notebook_id);
CREATE INDEX idx_agent_teams_session ON agent_teams(session_id);
CREATE INDEX idx_agent_teams_status ON agent_teams(status);
CREATE INDEX idx_api_conn_endpoints_conn ON api_connection_endpoints(connection_id);
CREATE INDEX idx_api_conn_endpoints_discovered ON api_connection_endpoints(discovered_at DESC);
CREATE INDEX idx_api_conn_endpoints_method ON api_connection_endpoints(method);
CREATE INDEX idx_api_connections_created ON api_connections(created DESC);
CREATE INDEX idx_api_connections_created_by ON api_connections(created_by);
CREATE INDEX idx_api_connections_test_status ON api_connections(test_status);
CREATE INDEX idx_api_key_usage_logs_api_key_id ON api_key_usage_logs(api_key_id);
CREATE INDEX idx_api_key_usage_logs_timestamp ON api_key_usage_logs(timestamp DESC);
CREATE INDEX idx_api_keys_is_active ON api_keys(is_active);
CREATE INDEX idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_owner_id ON api_keys(owner_id);
CREATE INDEX idx_blocklist_category ON content_blocklist(category);
CREATE INDEX idx_blocklist_severity ON content_blocklist(severity);
CREATE INDEX idx_bookmark_embeddings_bookmark ON bookmark_embeddings(bookmark_id);
CREATE INDEX idx_chat_messages_created ON chat_messages(created);
CREATE INDEX idx_chat_messages_render_mode ON chat_messages(render_mode);
CREATE INDEX idx_chat_messages_session ON chat_messages(session_id);
CREATE INDEX idx_chat_messages_trace ON chat_messages(langfuse_trace_id);
CREATE INDEX idx_chat_sessions_created_by ON chat_sessions(created_by);
CREATE INDEX idx_chat_sessions_model ON chat_sessions(model_override);
CREATE INDEX idx_chat_sessions_notebook ON chat_sessions(notebook_id);
CREATE INDEX idx_chat_sessions_updated ON chat_sessions(updated);
CREATE INDEX idx_classification_relationships_source ON classification_relationships(source_classification_id);
CREATE INDEX idx_classification_relationships_target ON classification_relationships(target_classification_id);
CREATE INDEX idx_classification_relationships_type ON classification_relationships(relationship_type);
CREATE INDEX idx_classification_types_level ON classification_types(level);
CREATE INDEX idx_classification_types_name ON classification_types(name);
CREATE INDEX idx_classification_types_parent ON classification_types(parent_id);
CREATE INDEX idx_classification_types_type ON classification_types(classification_type);
CREATE INDEX idx_communities_created ON entity_communities(created DESC);
CREATE INDEX idx_communities_level ON entity_communities(level);
CREATE INDEX idx_communities_parent ON entity_communities(parent_community_id);
CREATE INDEX idx_credentials_deployment ON credentials(deployment_id);
CREATE INDEX idx_credentials_provider ON credentials(provider);
CREATE INDEX idx_credentials_source ON credentials(source);
CREATE INDEX idx_embeddings_order ON source_embeddings(source_id, order_num);
CREATE INDEX idx_embeddings_source ON source_embeddings(source_id);
CREATE INDEX idx_entities_created ON entities(created DESC);
CREATE INDEX idx_entities_name ON entities(name);
CREATE INDEX idx_entities_source ON entities(source_id);
CREATE INDEX idx_entities_source_type ON entities(source_id, entity_type);
CREATE INDEX idx_entities_type ON entities(entity_type);
CREATE INDEX idx_entity_embeddings_entity ON entity_embeddings(entity_id);
CREATE INDEX idx_entity_rels_source ON entity_relationships(source_entity_id);
CREATE INDEX idx_entity_rels_source_target ON entity_relationships(source_entity_id, target_entity_id);
CREATE INDEX idx_entity_rels_strength ON entity_relationships(strength DESC);
CREATE INDEX idx_entity_rels_target ON entity_relationships(target_entity_id);
CREATE INDEX idx_entity_rels_type ON entity_relationships(relationship_type);
CREATE INDEX idx_entity_rels_type_strength ON entity_relationships(relationship_type, strength DESC);
CREATE INDEX idx_eval_cases_category ON evaluation_test_cases(category);
CREATE INDEX idx_eval_cases_dataset ON evaluation_test_cases(dataset_id);
CREATE INDEX idx_eval_datasets_agent ON evaluation_datasets(agent_id);
CREATE INDEX idx_eval_datasets_created ON evaluation_datasets(created DESC);
CREATE INDEX idx_eval_results_case ON evaluation_results(test_case_id);
CREATE INDEX idx_eval_results_passed ON evaluation_results(passed);
CREATE INDEX idx_eval_results_run ON evaluation_results(run_id);
CREATE INDEX idx_folders_notebook_id ON folders(notebook_id);
CREATE INDEX idx_folders_parent ON folders(parent_id);
CREATE INDEX idx_folders_parent_id ON folders(parent_id);
CREATE INDEX idx_folders_type ON folders(folder_type);
CREATE INDEX idx_guided_sessions_current_step ON guided_workspace_sessions(current_step);
CREATE INDEX idx_guided_sessions_expires_at ON guided_workspace_sessions(expires_at);
CREATE INDEX idx_guided_sessions_status ON guided_workspace_sessions(status);
CREATE INDEX idx_guided_sessions_user_id ON guided_workspace_sessions(user_id);
CREATE INDEX idx_hana_conn_tables_conn ON hana_connection_tables(connection_id);
CREATE INDEX idx_hana_conn_tables_discovered ON hana_connection_tables(discovered_at DESC);
CREATE INDEX idx_hana_conn_tables_name ON hana_connection_tables(table_name);
CREATE INDEX idx_hana_connections_created_by ON hana_connections(created_by);
CREATE INDEX idx_hana_connections_name ON hana_connections(name);
CREATE INDEX idx_layouts_created ON graph_layouts(created DESC);
CREATE INDEX idx_layouts_scope ON graph_layouts(scope, scope_id);
CREATE INDEX idx_mcp_servers_name ON mcp_servers(name);
CREATE INDEX idx_mcp_servers_protocol ON mcp_servers(protocol);
CREATE INDEX idx_mcp_servers_status ON mcp_servers(status);
CREATE INDEX idx_mcp_tools_name ON mcp_tools(tool_name);
CREATE INDEX idx_mcp_tools_server ON mcp_tools(server_id);
CREATE INDEX idx_microsite_access_email ON microsite_access(email);
CREATE INDEX idx_microsite_content_microsite ON microsite_content(microsite_id);
CREATE INDEX idx_microsite_content_order ON microsite_content(microsite_id, order_num);
CREATE INDEX idx_microsite_content_section ON microsite_content(microsite_id, section_id);
CREATE INDEX idx_microsite_otp_code ON microsite_otp(otp_code);
CREATE INDEX idx_microsite_otp_expires ON microsite_otp(expires_at);
CREATE INDEX idx_microsite_sources_microsite ON microsite_sources(microsite_id);
CREATE INDEX idx_microsite_sources_source ON microsite_sources(source_id);
CREATE INDEX idx_microsite_templates_custom ON microsite_templates(is_custom);
CREATE INDEX idx_microsite_templates_name ON microsite_templates(name);
CREATE INDEX idx_microsite_versions_created ON microsite_versions(created);
CREATE INDEX idx_microsite_versions_microsite ON microsite_versions(microsite_id);
CREATE INDEX idx_microsite_versions_number ON microsite_versions(microsite_id, version_number);
CREATE INDEX idx_microsites_created_by ON microsites(created_by);
CREATE INDEX idx_microsites_moderation ON microsites(moderation_status);
CREATE INDEX idx_microsites_notebook ON microsites(notebook_id);
CREATE INDEX idx_microsites_published ON microsites(published_version);
CREATE INDEX idx_microsites_slug ON microsites(slug);
CREATE INDEX idx_microsites_status ON microsites(status);
CREATE INDEX idx_microsites_template ON microsites(template_id);
CREATE INDEX idx_models_provider ON models(provider);
CREATE INDEX idx_models_type ON models(type);
CREATE INDEX idx_moderation_logs_created ON content_moderation_logs(created);
CREATE INDEX idx_moderation_logs_microsite ON content_moderation_logs(microsite_id);
CREATE INDEX idx_moderation_logs_status ON content_moderation_logs(status);
CREATE INDEX idx_moderation_logs_type ON content_moderation_logs(moderation_type);
CREATE INDEX idx_note_links_source ON note_links(source_note_id);
CREATE INDEX idx_note_links_target ON note_links(target_note_id);
CREATE INDEX idx_note_tags_note ON note_tags(note_id);
CREATE INDEX idx_note_tags_tag ON note_tags(tag);
CREATE INDEX idx_notebook_note_note ON notebook_note(note_id);
CREATE INDEX idx_notebook_note_notebook ON notebook_note(notebook_id);
CREATE INDEX idx_notebook_source_notebook ON notebook_source(notebook_id);
CREATE INDEX idx_notebook_source_source ON notebook_source(source_id);
CREATE INDEX idx_notebook_tags_notebook ON notebook_tags(notebook_id);
CREATE INDEX idx_notebook_tags_notebook_id ON notebook_tags(notebook_id);
CREATE INDEX idx_notebook_tags_tag ON notebook_tags(tag_id);
CREATE INDEX idx_notebook_tags_tag_id ON notebook_tags(tag_id);
CREATE INDEX idx_notebooks_archived ON notebooks(archived);
CREATE INDEX idx_notebooks_created ON notebooks(created);
CREATE INDEX idx_notebooks_created_by ON notebooks(created_by);
CREATE INDEX idx_notebooks_folder ON notebooks(folder_id);
CREATE INDEX idx_notebooks_goal ON notebooks(goal);
CREATE INDEX idx_notebooks_protected ON notebooks(protected);
CREATE INDEX idx_notes_notebook_id ON notes(notebook_id);
CREATE INDEX idx_notifications_category ON notifications(category);
CREATE INDEX idx_notifications_created_at ON notifications(created_at DESC);
CREATE INDEX idx_notifications_entity ON notifications(entity_type, entity_id);
CREATE INDEX idx_notifications_is_read ON notifications(is_read);
CREATE INDEX idx_notifications_type ON notifications(type);
CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_user_unread ON notifications(user_id, is_read, created_at DESC);
CREATE INDEX idx_oauth_apps_client_id ON oauth_applications(client_id);
CREATE INDEX idx_oauth_apps_owner ON oauth_applications(owner_user_id);
CREATE INDEX idx_oauth_apps_status ON oauth_applications(status);
CREATE INDEX idx_oauth_audit_app ON oauth_audit_log(app_id);
CREATE INDEX idx_oauth_audit_client ON oauth_audit_log(client_id);
CREATE INDEX idx_oauth_audit_created ON oauth_audit_log(created);
CREATE INDEX idx_oauth_audit_status ON oauth_audit_log(status_code);
CREATE INDEX idx_oauth_clients_server
ON mcp_oauth_clients(server_id);
CREATE INDEX idx_oauth_codes_app ON oauth_authorization_codes(app_id);
CREATE INDEX idx_oauth_codes_code ON oauth_authorization_codes(code);
CREATE INDEX idx_oauth_codes_expires ON oauth_authorization_codes(expires_at);
CREATE INDEX idx_oauth_codes_user ON oauth_authorization_codes(user_id);
CREATE INDEX idx_oauth_refresh_app ON oauth_refresh_tokens(app_id);
CREATE INDEX idx_oauth_refresh_token ON oauth_refresh_tokens(token);
CREATE INDEX idx_oauth_refresh_user ON oauth_refresh_tokens(user_id);
CREATE INDEX idx_oauth_revoked_expires ON oauth_revoked_tokens(expires_at);
CREATE INDEX idx_oauth_revoked_jti ON oauth_revoked_tokens(jti);
CREATE INDEX idx_orchestration_action_bindings_action ON orchestration_action_bindings(action_id);
CREATE INDEX idx_orchestration_action_bindings_active ON orchestration_action_bindings(is_active);
CREATE INDEX idx_orchestration_action_bindings_orchestration ON orchestration_action_bindings(orchestration_id);
CREATE INDEX idx_orchestration_action_bindings_schedule ON orchestration_action_bindings(schedule_id);
CREATE INDEX idx_orchestration_action_bindings_trigger ON orchestration_action_bindings(trigger_condition);
CREATE INDEX idx_orchestration_events_orchestration_id ON orchestration_events(orchestration_id);
CREATE INDEX idx_orchestration_events_timestamp ON orchestration_events(timestamp);
CREATE INDEX idx_orchestration_schedules_next_run ON orchestration_schedules(next_run);
CREATE INDEX idx_orchestration_schedules_status ON orchestration_schedules(status);
CREATE INDEX idx_orchestration_schedules_template_id ON orchestration_schedules(template_id);
CREATE INDEX idx_orchestration_schedules_type ON orchestration_schedules(schedule_type);
CREATE INDEX idx_orchestration_schedules_user ON orchestration_schedules(user_id);
CREATE INDEX idx_orchestrations_created_at ON orchestrations(created_at DESC);
CREATE INDEX idx_orchestrations_schedule ON orchestrations(schedule_id);
CREATE INDEX idx_orchestrations_status ON orchestrations(status);
CREATE INDEX idx_orchestrations_template_id ON orchestrations(template_id);
CREATE INDEX idx_orchestrations_user_id ON orchestrations(user_id);
CREATE INDEX idx_orchestrations_workspace_instance_id ON orchestrations(workspace_instance_id);
CREATE INDEX idx_plan_tasks_assigned_agent ON workspace_plan_tasks(assigned_agent_id);
CREATE INDEX idx_plan_tasks_phase ON workspace_plan_tasks(phase_name);
CREATE INDEX idx_plan_tasks_plan_id ON workspace_plan_tasks(plan_id);
CREATE INDEX idx_plan_tasks_status ON workspace_plan_tasks(status);
CREATE INDEX idx_presentation_content_presentation_id ON presentation_content(presentation_id);
CREATE INDEX idx_presentation_content_slide_number ON presentation_content(presentation_id, slide_number);
CREATE INDEX idx_presentation_sources_presentation_id ON presentation_sources(presentation_id);
CREATE INDEX idx_presentation_sources_source_id ON presentation_sources(source_id);
CREATE INDEX idx_presentation_templates_active ON presentation_templates(is_active);
CREATE INDEX idx_presentation_templates_category ON presentation_templates(category);
CREATE INDEX idx_presentation_versions_presentation_id ON presentation_versions(presentation_id);
CREATE INDEX idx_presentation_versions_version_number ON presentation_versions(presentation_id, version_number);
CREATE INDEX idx_presentations_created_at ON presentations(created_at);
CREATE INDEX idx_presentations_notebook_id ON presentations(notebook_id);
CREATE INDEX idx_presentations_template_id ON presentations(template_id);
CREATE INDEX idx_prompt_templates_role ON agent_prompt_templates(role);
CREATE INDEX idx_resource_shares_resource ON resource_shares(resource_type, resource_id);
CREATE INDEX idx_resource_shares_role ON resource_shares(shared_with_role);
CREATE INDEX idx_resource_shares_shared_by ON resource_shares(shared_by);
CREATE INDEX idx_resource_shares_user ON resource_shares(shared_with_user);
CREATE INDEX idx_role_permissions_resource ON role_permissions(resource_type, action);
CREATE INDEX idx_role_permissions_role ON role_permissions(role_id);
CREATE INDEX idx_similarities_related ON source_similarities(related_source_id, similarity_score DESC);
CREATE INDEX idx_similarities_score ON source_similarities(similarity_score DESC);
CREATE INDEX idx_similarities_source ON source_similarities(source_id, similarity_score DESC);
CREATE UNIQUE INDEX idx_smtp_config_singleton ON smtp_config(id);
CREATE INDEX idx_snapshots_cleanup
    ON workflow_snapshots(expires_at)
    WHERE expires_at IS NOT NULL;
CREATE INDEX idx_snapshots_context
    ON workflow_snapshots(context_hash, snapshot_date DESC);
CREATE INDEX idx_snapshots_execution
    ON workflow_snapshots(execution_id)
    WHERE execution_id IS NOT NULL;
CREATE INDEX idx_snapshots_node
    ON workflow_snapshots(workflow_id, node_id, snapshot_date DESC);
CREATE INDEX idx_snapshots_user_date
    ON workflow_snapshots(user_id, snapshot_date DESC);
CREATE INDEX idx_snapshots_workflow_user
    ON workflow_snapshots(workflow_id, user_id, snapshot_date DESC);
CREATE INDEX idx_source_classifications_class ON source_classifications(classification_id);
CREATE INDEX idx_source_classifications_confidence ON source_classifications(confidence);
CREATE INDEX idx_source_classifications_source ON source_classifications(source_id);
CREATE INDEX idx_source_classifications_status ON source_classifications(status);
CREATE INDEX idx_source_embeddings_source ON source_embeddings(source_id);
CREATE INDEX idx_sources_created ON sources(created);
CREATE INDEX idx_sources_created_by ON sources(created_by);
CREATE INDEX idx_sources_type ON sources(source_type);
CREATE INDEX idx_standalone_agents_created_by ON standalone_agents(created_by);
CREATE INDEX idx_standalone_agents_notebook ON standalone_agents(notebook_id);
CREATE INDEX idx_standalone_agents_role ON standalone_agents(role);
CREATE INDEX idx_standalone_agents_skills ON standalone_agents(skill_ids);
CREATE INDEX idx_standalone_agents_status ON standalone_agents(status);
CREATE INDEX idx_standalone_executions_agent ON standalone_agent_executions(agent_id);
CREATE INDEX idx_standalone_executions_created ON standalone_agent_executions(created);
CREATE INDEX idx_standalone_executions_session ON standalone_agent_executions(session_id);
CREATE INDEX idx_standalone_executions_status ON standalone_agent_executions(status);
CREATE INDEX idx_sync_history_created ON sync_history(created DESC);
CREATE INDEX idx_sync_history_source ON sync_history(source_id);
CREATE INDEX idx_sync_history_status ON sync_history(status);
CREATE INDEX idx_system_prompts_active ON system_prompt_templates(is_active);
CREATE INDEX idx_system_prompts_category ON system_prompt_templates(category);
CREATE INDEX idx_system_prompts_key ON system_prompt_templates(template_key);
CREATE INDEX idx_template_executions_created ON template_executions(created_at DESC);
CREATE INDEX idx_template_executions_folder ON template_executions(folder_id);
CREATE INDEX idx_template_executions_status ON template_executions(status);
CREATE INDEX idx_template_executions_template ON template_executions(template_id);
CREATE INDEX idx_template_executions_user ON template_executions(user_id);
CREATE INDEX idx_template_executions_workspace ON template_executions(target_workspace_id);
CREATE INDEX idx_tool_permissions_role ON tool_permissions(role);
CREATE INDEX idx_tool_permissions_tool ON tool_permissions(tool_id);
CREATE INDEX idx_tool_permissions_user ON tool_permissions(user_id);
CREATE INDEX idx_tool_registry_category ON tool_registry(category);
CREATE INDEX idx_tool_registry_created_by ON tool_registry(created_by);
CREATE INDEX idx_tool_registry_enabled ON tool_registry(enabled);
CREATE INDEX idx_tool_registry_tool_type ON tool_registry(tool_type);
CREATE INDEX idx_tool_usage_log_created ON tool_usage_log(created);
CREATE INDEX idx_tool_usage_log_tool ON tool_usage_log(tool_id);
CREATE INDEX idx_tool_usage_log_user ON tool_usage_log(user_id);
CREATE INDEX idx_traces_created ON agent_execution_traces(created);
CREATE INDEX idx_traces_langfuse ON agent_execution_traces(langfuse_trace_id);
CREATE INDEX idx_traces_model ON agent_execution_traces(model_used);
CREATE INDEX idx_traces_session ON agent_execution_traces(session_id);
CREATE INDEX idx_transformations_default ON transformations(apply_default);
CREATE INDEX idx_user_bookmarks_bookmarked_at ON user_bookmarks(bookmarked_at DESC);
CREATE INDEX idx_user_bookmarks_category ON user_bookmarks(category);
CREATE INDEX idx_user_bookmarks_entity ON user_bookmarks(entity_type, entity_id);
CREATE INDEX idx_user_bookmarks_user ON user_bookmarks(user_id);
CREATE INDEX idx_user_bookmarks_user_type ON user_bookmarks(user_id, entity_type);
CREATE INDEX idx_user_query_prompts_favorite ON user_query_prompts(is_favorite);
CREATE INDEX idx_user_query_prompts_last_used ON user_query_prompts(last_used);
CREATE INDEX idx_user_query_prompts_team ON user_query_prompts(team_id);
CREATE INDEX idx_user_query_prompts_user ON user_query_prompts(user_id);
CREATE INDEX idx_user_roles_role ON user_roles(role_id);
CREATE INDEX idx_user_roles_user ON user_roles(user_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_wf_template_executions_template ON workflow_template_executions(template_id);
CREATE INDEX idx_wf_template_executions_user ON workflow_template_executions(user_id);
CREATE INDEX idx_workflow_approvals_execution ON workflow_approvals(execution_id);
CREATE INDEX idx_workflow_approvals_status ON workflow_approvals(status);
CREATE INDEX idx_workflow_approvals_timeout ON workflow_approvals(timeout_at);
CREATE INDEX idx_workflow_executions_started_at ON workflow_executions(started_at DESC);
CREATE INDEX idx_workflow_executions_status ON workflow_executions(status);
CREATE INDEX idx_workflow_executions_workflow_id ON workflow_executions(workflow_id);
CREATE INDEX idx_workflow_schedules_enabled ON workflow_schedules(enabled);
CREATE INDEX idx_workflow_schedules_next_run_at ON workflow_schedules(next_run_at);
CREATE INDEX idx_workflow_schedules_type ON workflow_schedules(schedule_type);
CREATE INDEX idx_workflow_schedules_workflow_id ON workflow_schedules(workflow_id);
CREATE INDEX idx_workflow_template_exec_started ON workflow_template_executions(started_at);
CREATE INDEX idx_workflow_template_exec_trigger ON workflow_template_executions(trigger_type);
CREATE INDEX idx_workflow_templates_category ON workflow_templates(category);
CREATE INDEX idx_workflow_templates_public ON workflow_templates(is_public);
CREATE INDEX idx_workflow_templates_source ON workflow_templates(source_workflow_id);
CREATE INDEX idx_workflow_templates_usage ON workflow_templates(usage_count DESC);
CREATE INDEX idx_workflow_templates_user ON workflow_templates(user_id);
CREATE INDEX idx_workflows_created_by ON workflows(created_by);
CREATE INDEX idx_workflows_is_active ON workflows(is_active);
CREATE INDEX idx_workflows_updated_at ON workflows(updated_at DESC);
CREATE INDEX idx_workspace_documents_created
ON workspace_documents(created_at DESC);
CREATE INDEX idx_workspace_documents_notebook
ON workspace_documents(notebook_id);
CREATE INDEX idx_workspace_documents_type
ON workspace_documents(document_type);
CREATE INDEX idx_workspace_plans_status ON workspace_plans(status);
CREATE INDEX idx_workspace_plans_workspace_id ON workspace_plans(workspace_id);
CREATE INDEX idx_workspace_templates_category ON workspace_templates(category);
CREATE INDEX idx_workspace_templates_public ON workspace_templates(is_public);
CREATE INDEX idx_workspace_templates_source_workspace ON workspace_templates(source_workspace_id);
CREATE INDEX idx_workspace_templates_times_used ON workspace_templates(times_used DESC);
CREATE INDEX idx_workspace_templates_user_id ON workspace_templates(user_id);
CREATE VIEW snapshot_storage_stats AS
SELECT
    storage_type,
    COUNT(*) as snapshot_count,
    SUM(total_size_bytes) as total_bytes,
    ROUND(SUM(total_size_bytes) / 1024.0 / 1024.0 / 1024.0, 2) as total_gb,
    AVG(total_size_bytes) as avg_bytes,
    MIN(total_size_bytes) as min_bytes,
    MAX(total_size_bytes) as max_bytes
FROM workflow_snapshots
GROUP BY storage_type
/* snapshot_storage_stats(storage_type,snapshot_count,total_bytes,total_gb,avg_bytes,min_bytes,max_bytes) */;
CREATE TRIGGER sources_fts_delete AFTER DELETE ON sources BEGIN
    DELETE FROM sources_fts WHERE id = old.id;
END;
CREATE TRIGGER sources_fts_insert AFTER INSERT ON sources BEGIN
    INSERT INTO sources_fts(id, title, full_text)
    VALUES (new.id, new.title, new.full_text);
END;
CREATE TRIGGER sources_fts_update AFTER UPDATE ON sources BEGIN
    UPDATE sources_fts SET title = new.title, full_text = new.full_text
    WHERE id = old.id;
END;
CREATE VIEW user_snapshot_summary AS
SELECT
    s.id,
    s.workflow_id,
    w.name as workflow_name,
    s.node_id,
    s.user_id,
    u.username,
    s.snapshot_date,
    s.snapshot_label,
    s.storage_type,
    s.row_count,
    s.total_size_bytes,
    ROUND(s.total_size_bytes / 1024.0 / 1024.0, 2) as size_mb,
    json_extract(s.query_context, '$.query_params') as query_params,
    s.created_at,
    s.expires_at,
    CASE
        WHEN s.expires_at IS NULL THEN 'permanent'
        WHEN datetime(s.expires_at) < datetime('now') THEN 'expired'
        ELSE 'active'
    END as status
FROM workflow_snapshots s
JOIN workflows w ON s.workflow_id = w.id
JOIN users u ON s.user_id = u.id
ORDER BY s.created_at DESC
/* user_snapshot_summary(id,workflow_id,workflow_name,node_id,user_id,username,snapshot_date,snapshot_label,storage_type,row_count,total_size_bytes,size_mb,query_params,created_at,expires_at,status) */;
CREATE INDEX idx_notes_created ON notes(created);
CREATE TABLE IF NOT EXISTS "mcp_oauth_tokens" (
    server_id      TEXT NOT NULL,
    user_id        TEXT NOT NULL,            -- '__system__' for system-mode, else users.id
    access_token   TEXT NOT NULL,
    refresh_token  TEXT,
    token_type     TEXT DEFAULT 'Bearer',
    expires_at     TIMESTAMP NOT NULL,
    scope          TEXT,
    user_info      TEXT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (server_id, user_id),
    FOREIGN KEY (server_id) REFERENCES mcp_servers(id) ON DELETE CASCADE
);
CREATE INDEX idx_mcp_oauth_tokens_user
    ON mcp_oauth_tokens(user_id);
CREATE INDEX idx_mcp_oauth_tokens_expires
    ON mcp_oauth_tokens(expires_at);
CREATE INDEX idx_agent_instances_standalone ON agent_instances(standalone_agent_id);
CREATE INDEX idx_agent_teams_pattern ON agent_teams(orchestration_pattern);
CREATE TABLE IF NOT EXISTS "evaluation_runs" (
            id TEXT PRIMARY KEY,
            dataset_id TEXT NOT NULL,
            agent_id TEXT,
            workflow_id TEXT,
            target_type TEXT NOT NULL DEFAULT 'agent',
            run_name TEXT,
            model_override TEXT,
            config_override TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            progress INTEGER DEFAULT 0,
            total_cases INTEGER DEFAULT 0,
            passed_cases INTEGER DEFAULT 0,
            failed_cases INTEGER DEFAULT 0,
            avg_score REAL,
            avg_latency_ms REAL,
            started_at TEXT,
            completed_at TEXT,
            error_message TEXT,
            created TEXT NOT NULL,
            created_by TEXT,
            FOREIGN KEY (dataset_id) REFERENCES evaluation_datasets(id) ON DELETE CASCADE,
            FOREIGN KEY (agent_id) REFERENCES standalone_agents(id) ON DELETE CASCADE
        );
CREATE INDEX idx_eval_runs_dataset ON evaluation_runs(dataset_id);
CREATE INDEX idx_eval_runs_agent ON evaluation_runs(agent_id);
CREATE INDEX idx_eval_runs_workflow ON evaluation_runs(workflow_id);
CREATE INDEX idx_eval_runs_status ON evaluation_runs(status);
CREATE INDEX idx_eval_runs_created ON evaluation_runs(created DESC);
CREATE TABLE agent_procedural_memory (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    task_pattern TEXT NOT NULL,
    task_pattern_embedding BLOB,
    tool_sequence TEXT NOT NULL,
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    avg_duration_ms INTEGER,
    example_inputs TEXT,
    last_used TEXT,
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    FOREIGN KEY (agent_id) REFERENCES standalone_agents(id) ON DELETE CASCADE
);
CREATE INDEX idx_agent_memory_agent_layer ON agent_memory(agent_id, layer);
CREATE INDEX idx_agent_memory_agent_expires ON agent_memory(agent_id, expires_at);
CREATE INDEX idx_agent_memory_layer ON agent_memory(layer);
CREATE INDEX idx_proc_mem_agent_pattern ON agent_procedural_memory(agent_id, task_pattern);
CREATE INDEX idx_proc_mem_last_used ON agent_procedural_memory(last_used DESC);
CREATE TABLE agent_clarifications (
            id              TEXT PRIMARY KEY,
            execution_id    TEXT NOT NULL,
            team_id         TEXT NOT NULL,
            sender_agent_id TEXT,
            sender_name     TEXT,
            sender_role     TEXT,
            question        TEXT NOT NULL,
            answer          TEXT,
            status          TEXT NOT NULL DEFAULT 'pending',
            checkpoint      TEXT,
            created         TEXT NOT NULL,
            answered_at     TEXT
        );
CREATE INDEX idx_clarifications_exec ON agent_clarifications(execution_id);
CREATE INDEX idx_clarifications_status ON agent_clarifications(status);
