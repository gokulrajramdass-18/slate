// Core Domain Types

export interface Notebook {
  id: string;
  name: string;
  description?: string;
  folder_id?: string;
  tags?: string[];  // Tags for organizing notebooks
  archived: boolean;
  source_count?: number;
  note_count?: number;  // Number of notes in the notebook
  is_bookmarked?: boolean;
  goal?: string;  // Workspace goal (now required for all workspaces)
  has_plan?: boolean;  // Whether workspace has an AI-generated plan (indicates AI-guided)
  is_processing?: boolean;  // Whether workspace has active workflow executions or agent tasks
  created: string;
  updated: string;
}

export interface Source {
  id: string;
  title: string;
  source_type: SourceType;
  full_text?: string;
  topics?: string[];
  tags?: string[];
  asset_type?: string;
  asset_data?: string | AssetData;  // Can be JSON string or parsed object
  connection_config?: ConnectionConfig;
  sync_config?: SyncConfig;
  sync_status?: "idle" | "scheduled" | "syncing" | "embedding" | "completed" | "success" | "error" | "failed";
  chunk_count?: number;
  last_synced?: string;
  error_message?: string;
  is_bookmarked?: boolean;
  created: string;
  updated: string;
}

export interface AssetData {
  // YouTube fields
  video_id?: string;
  channel_id?: string;
  channel_name?: string;
  channel_handle?: string;
  duration_seconds?: number;
  upload_date?: string;
  view_count?: number;
  description?: string;
  transcript_language?: string;
  transcript_auto_generated?: boolean;
  transcript_available?: boolean;
  thumbnail_url?: string;
  keywords?: string[];

  // HANA Table fields
  schema_name?: string;
  table_name?: string;
  record_count?: number;
  columns?: string[];

  // API fields
  endpoint?: string;
  auth_type?: string;
  response_format?: string;

  // Generic
  [key: string]: any;
}

export type SourceType =
  | "file"
  | "url"
  | "text"
  | "youtube"
  | "hana_table"
  | "api";

export interface ConnectionConfig {
  host?: string;
  port?: number;
  database?: string;
  username?: string;
  password?: string; // Encrypted in backend
  table?: string;
  columns?: string[];
  auth_type?: "none" | "basic" | "bearer" | "oauth2_client" | "oauth2_auth_code";
  endpoint?: string;
  headers?: Record<string, string>;
  oauth_config?: OAuth2Config;
}

export interface OAuth2Config {
  client_id: string;
  client_secret?: string;
  auth_url: string;
  token_url: string;
  scope?: string;
  redirect_uri?: string;
}

export interface SyncConfig {
  enabled: boolean;
  frequency: "manual" | "hourly" | "daily" | "weekly";
  last_sync?: string;
  next_sync?: string;
  status: "idle" | "scheduled" | "syncing" | "success" | "failed";
  error_message?: string;
}

export interface Note {
  id: string;
  title?: string;
  summary?: string;
  content: string;
  is_bookmarked?: boolean;
  created: string;
  updated: string;
}

export interface ChatSession {
  id: string;
  title?: string;
  notebook_id?: string;
  workspace_name?: string;
  created: string;
  updated: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created: string;
  sources?: Array<{
    source_id: string;
    source_name: string;
    chunks_included: number;
    tokens: number;
  }>;
  ui_components?: string;  // JSON string of UIComponentData[]
  render_mode?: "markdown" | "generative" | "hybrid";
  tool_results?: string;  // JSON string of ToolResultData[]
  agent_steps?: string;  // JSON string of AgentStep[]
  langfuse_trace_id?: string;
  langfuse_observation_id?: string;
  mlflow_run_id?: string;
  mlflow_experiment_id?: string;
}

// Agent Execution Step Types

export interface AgentStep {
  step_type: 'thinking' | 'tool_call' | 'tool_result' | 'response' | 'step_start' | 'step_complete' | 'llm_call' | 'llm_response' | 'analysis' | 'planning';
  content: string;
  timestamp: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  metadata?: {
    tool_name?: string;
    tool?: string;  // LangGraph tool name
    args?: any;  // Tool arguments
    output?: any;  // Tool/step output
    duration_ms?: number;
    started_at?: string;
    error_message?: string;
    step?: string;  // Step name from LangGraph
    step_number?: number;  // Step number in plan
    plan?: any[];  // Execution plan
    analysis?: any;  // Query analysis
    prompt?: string;  // LLM prompt
    response?: string;  // LLM response
    [key: string]: any;
  };
}

/**
 * Parse agent_steps JSON string from a ChatMessage into AgentStep array
 */
export function parseAgentSteps(message: ChatMessage): AgentStep[] {
  if (!message.agent_steps) return [];
  try {
    return JSON.parse(message.agent_steps);
  } catch (e) {
    console.error('Failed to parse agent steps:', e);
    return [];
  }
}

// Generative UI Types

export interface UIComponentData {
  component_type: string;
  props: Record<string, unknown>;
  layout?: {
    width?: string;
    height?: string;
  };
  children?: UIComponentData[];
}

export interface ToolResultData {
  tool_name: string;
  tool_call_id: string;
  execution_time_ms: number;
  result_type: "table" | "json" | "text" | "metric" | "chart";
  data: unknown;
  visualization_hint?: "line" | "bar" | "pie" | "scatter" | "area" | "radar" | "composed" | "time_series";
}

// Chart-specific types
export interface ChartDataPoint {
  [key: string]: string | number | null;
}

export interface ChartConfig {
  type: "line" | "bar" | "pie" | "scatter" | "area" | "radar" | "composed";
  data: ChartDataPoint[];
  xKey?: string;
  yKeys: string[];
  title?: string;
  description?: string;
  colors?: string[];
  xLabel?: string;
  yLabel?: string;
  legend?: boolean;
  grid?: boolean;
  stacked?: boolean;
}

export interface Model {
  id: string;
  name: string;
  provider: string;
  type: "language" | "embedding" | "speech_to_text" | "text_to_speech";
  credential_id?: string;
  created: string;
  updated: string;
}

export interface Credential {
  id: string;
  name: string;
  provider: string;
  modalities: string[];
  model_name?: string;
  model_type?: string;
  api_key?: string;
  api_key_encrypted?: string;
  base_url?: string;
  is_active?: boolean;
  connection_status?: string;
  last_tested?: string;
  created: string;
  updated: string;
  // SAP AI Core specific fields
  auth_url?: string;
  api_url?: string;
  client_id?: string;
  client_secret?: string;
  client_secret_encrypted?: string;
  deployment_id?: string;
  resource_group?: string;
  identity_zone?: string;
  identityzoneid?: string;
}

export interface Transformation {
  id: string;
  name: string;
  title: string;
  description?: string;
  prompt: string;
  apply_default: boolean;
  created: string;
  updated: string;
}

export interface Folder {
  id: string;
  name: string;
  parent_id?: string;
  created: string;
  updated: string;
  children?: Folder[];
}

export interface Tag {
  id: string;
  name: string;
  color?: string;
}

export interface SearchConfig {
  id: string;
  user_id?: string;
  default_strategy: SearchStrategy;
  config: Record<string, any>;
  created: string;
  updated: string;
}

export type SearchStrategy = "keyword" | "vector" | "hybrid" | "agentic_rag";

export interface SearchResult {
  id: string;
  title: string;
  content: string;
  source_type: SourceType;
  score: number;
  highlights?: string[];
  metadata?: Record<string, any>;
}

export interface AgenticRAGStep {
  step: string;
  description: string;
  result?: any;
}

export interface DatabaseConfig {
  type: "sqlite" | "hana";
  sqlite_path?: string;
  hana_host?: string;
  hana_port?: number;
  hana_database?: string;
  hana_user?: string;
  hana_encrypt?: boolean;
}

export interface DatabaseStatus {
  connected: boolean;
  type: "sqlite" | "hana";
  stats?: {
    notebooks: number;
    sources: number;
    notes: number;
    embeddings: number;
  };
}

// API Request/Response Types

export interface NotebookCreate {
  name: string;
  description?: string;
  folder_id?: string;
  goal: string;
}

export interface SourceCreate {
  title: string;
  source_type: SourceType;
  notebook_id?: string;
  description?: string;
  tags?: string[];
  content?: string;
  full_text?: string;
  url?: string;
  connection_config?: ConnectionConfig;
  sync_config?: SyncConfig;
}

export interface NoteCreate {
  title?: string;
  summary?: string;
  content: string;
}

export interface ChatSessionCreate {
  title?: string;
  notebook_id: string;  // Required field
  model_override?: string;
  selected_source_ids?: string[];
}

export interface ChatMessageCreate {
  message: string;  // Changed from 'content' to match backend
  stream?: boolean;
  include_context?: boolean;
  selected_source_ids?: string[];
  selected_tool_ids?: string[];  // Filter which tools the agent can use
  max_context_tokens?: number;
  enable_generative_ui?: boolean;  // Optional - uses global setting if not provided
  deep_research?: boolean;  // Enable deep research mode for autonomous multi-phase research
}

export interface SearchRequest {
  query: string;
  strategy?: SearchStrategy;
  filters?: {
    notebook_ids?: string[];
    source_types?: SourceType[];
    date_from?: string;
    date_to?: string;
    tags?: string[];
  };
  limit?: number;
  config_override?: Record<string, any>;
}

export interface UnifiedSearchRequest {
  query: string;
  strategy?: SearchStrategy;
  filters?: {
    notebook_ids?: string[];
    source_types?: SourceType[];
    date_from?: string;
    date_to?: string;
    tags?: string[];
  };
  limit?: number;
  include_bookmarks?: boolean;
  bookmark_boost?: number;
  config_override?: Record<string, any>;
}

export interface UnifiedSearchResult {
  id: string;
  entity_type: "source" | "note" | "notebook";
  entity_id: string;
  chunk_id?: string;
  title: string;
  content: string;
  source_type: SourceType;
  score: number;
  highlights: string[];
  metadata: Record<string, any>;
  strategy: string;
  result_source: "main_search" | "bookmarks";
  is_bookmarked: boolean;
  bookmark_id?: string;
  custom_note?: string;
  created?: string;
}

export interface ErrorResponse {
  error: {
    code: string;
    message: string;
    details?: Record<string, any>;
  };
}

// ============================================================================
// BOOKMARK TYPES
// ============================================================================

export type BookmarkEntityType = "source" | "note" | "notebook";

export interface Bookmark {
  id: string;
  user_id: string;
  entity_type: BookmarkEntityType;
  entity_id: string;
  custom_note?: string;
  reason?: string;
  tags?: string[];
  category?: string;
  bookmarked_at: string;
  created: string;
  updated: string;
}

export interface EnrichedBookmark extends Bookmark {
  entity_title: string;
  entity_description?: string;
  entity_updated: string;
  source_type?: SourceType;
  chunk_count?: number;
  source_count?: number;
  note_count?: number;
}

export interface BookmarkCreate {
  entity_type: BookmarkEntityType;
  entity_id: string;
  custom_note?: string;
  reason?: string;
  tags?: string[];
  category?: string;
}

export interface BookmarkUpdate {
  custom_note?: string;
  reason?: string;
  tags?: string[];
  category?: string;
}

export interface ManualBookmarkCreate {
  title: string;
  description?: string;
  tags?: string[];
  category?: string;
  url?: string;
}

export interface BookmarkToggleResponse {
  is_bookmarked: boolean;
  bookmark?: Bookmark;
  message: string;
}

export interface BookmarkListResponse {
  bookmarks: EnrichedBookmark[];
  total: number;
}

export interface BookmarkCheckResponse {
  is_bookmarked: boolean;
  bookmark_id?: string;
}

export interface BookmarkBulkCheckResponse {
  bookmarks: Record<string, boolean>;
}

// ============================================================================
// MICROSITE GENERATOR TYPES
// ============================================================================

export interface MicrositeTemplate {
  id: string;
  name: string;  // blog, documentation, portfolio, landing_page, report
  display_name: string;
  description: string;
  structure: MicrositeTemplateStructure;
  default_styles: Record<string, string>;
  preview_image?: string;
  is_custom: boolean;
  created: string;
}

export interface MicrositeTemplateStructure {
  sections: MicrositeTemplateSectionDef[];
  layout: string;
  styles: {
    primary_color: string;
    font_heading: string;
    font_body: string;
    [key: string]: string;
  };
}

export interface MicrositeTemplateSectionDef {
  id: string;
  type: string;
  prompt_template: string;
  default_content?: Record<string, any>;
}

export interface MicrositeContent {
  id: string;
  microsite_id: string;
  section_id: string;
  section_type: string;
  content_html: string;
  content_json?: string;
  sort_order: number;
  is_visible: boolean;
  created: string;
  updated: string;
}

export type MicrositeStatus = "draft" | "published" | "blocked";

export interface MicrositeVersion {
  id: string;
  microsite_id: string;
  version_number: number;
  full_html: string;
  full_css?: string;
  content_snapshot?: string;
  created_by: string;
  snapshot_metadata?: Record<string, any>;
  status_at_publish?: MicrositeStatus;
  published_at?: string;
  created: string;
}

export interface ModerationIssue {
  type: "ai_filter" | "keyword_blocklist" | "source_validation" | "user_review";
  description: string;
  severity: "high" | "medium" | "low";
  location?: string;
}

export interface ModerationReport {
  status: "passed" | "warning" | "blocked";
  overall_score: number;
  layers: {
    ai_filter?: { score: number; issues: ModerationIssue[] };
    keyword_blocklist?: { score: number; issues: ModerationIssue[] };
    source_validation?: { score: number; issues: ModerationIssue[] };
  };
  issues: ModerationIssue[];
  requires_review: boolean;
}

export interface MicrositeGenerateRequest {
  template_id: string;
  source_ids: string[];
  user_prompt?: string;
}

export interface MicrositeGenerateResponse {
  microsite_id: string;
  version: number;
  sections: MicrositeContent[];
  moderation: ModerationReport;
  preview_url: string;
}

export interface MicrositeContentUpdate {
  sections: ContentSectionUpdate[];
}

export interface ContentSectionUpdate {
  section_id: string;
  content_html?: string;
  content_json?: string;
}

// ============================================================================
// MICROSITE STATUS & VERSION CONTROL TYPES
// ============================================================================

export interface Microsite {
  id: string;
  notebook_id: string;
  title: string;
  description?: string | null;
  slug: string;
  theme?: string;

  // Status and ownership
  status: MicrositeStatus;
  created_by?: string;
  active_version_id?: string;

  // Existing fields
  template_id?: string | null;
  custom_css?: string;
  custom_js?: string;
  generation_config?: string;
  moderation_status?: string | null;
  published_version?: number | null;
  last_generated?: string;
  is_active: boolean;
  access_url?: string;
  allowed_emails?: string[];
  created: string;
  updated: string;
}

export interface PublishRequest {
  version_message?: string;
}

export interface PublishResponse {
  microsite_id: string;
  status: MicrositeStatus;
  active_version_id: string;
  version_number: number;
  published_at: string;
}

export interface AccessCheckResponse {
  has_access: boolean;
  status: MicrositeStatus;
  reason?: string;
}

export interface ActiveVersionResponse {
  microsite_id: string;
  active_version_id?: string;
  version_number?: number;
  published_at?: string;
  full_html?: string;
}

// ============================================================================
// TOOL REGISTRY TYPES
// ============================================================================

export type ToolType =
  | "hana_query"
  | "api_call"
  | "web_search"
  | "code_exec"
  | "file_analysis"
  | "custom";

export type ToolCategory =
  | "data_query"
  | "web"
  | "computation"
  | "file_analysis";

export interface ToolMetadata {
  icon?: string;
  tags?: string[];
  author?: string;
  version?: string;
  documentation_url?: string;
  cost_per_call?: number;
  [key: string]: any;
}

export interface Tool {
  id: string;
  name: string;
  tool_type: ToolType;
  category?: ToolCategory | string;
  description: string;
  enabled: boolean;
  default_config?: Record<string, any>;
  metadata?: ToolMetadata;
  created: string;
  updated: string;
}

export interface ToolCreate {
  name: string;
  tool_type: ToolType;
  category?: string;
  description: string;
  enabled?: boolean;
  default_config?: Record<string, any>;
  metadata?: ToolMetadata;
}

export interface ToolUpdate {
  name?: string;
  description?: string;
  enabled?: boolean;
  default_config?: Record<string, any>;
  metadata?: ToolMetadata;
}

export interface ToolPermission {
  id: string;
  tool_id: string;
  user_id?: string;
  role?: string;
  allowed: boolean;
  rate_limit?: number;
  custom_config?: Record<string, any>;
  created: string;
}

export interface PermissionCreate {
  user_id?: string;
  role?: string;
  allowed?: boolean;
  rate_limit?: number;
  custom_config?: Record<string, any>;
}

export interface PermissionUpdate {
  allowed?: boolean;
  rate_limit?: number;
  custom_config?: Record<string, any>;
}

export interface ToolUsageStat {
  date: string;
  total_calls: number;
  avg_duration: number;
  successful_calls: number;
  failed_calls: number;
}

// ============================================================================
// MULTI-AGENT TYPES
// ============================================================================

export type AgentRole = "planner" | "researcher" | "analyst" | "data_scientist" | "writer" | "developer" | "tester" | "designer" | "reviewer" | "judge" | "coordinator" | "custom";
export type AgentStatus = "idle" | "working" | "waiting" | "completed" | "error";
export type TaskStatus = "pending" | "in_progress" | "completed" | "failed" | "blocked";
export type TeamStatus = "idle" | "planning" | "executing" | "reviewing" | "completed" | "error";

export interface Agent {
  id: string;
  team_id: string;
  name: string;
  role: AgentRole;
  description?: string;  // Keep for backwards compatibility
  system_prompt?: string;
  model?: string;
  model_override?: string;  // Backend field name
  tools?: string[];
  tool_ids?: string[];  // Backend field name
  mcp_server_ids?: string[];  // MCP servers
  data_source_ids?: string[];  // Data sources
  status: AgentStatus;
  capabilities?: string[];
  config?: Record<string, any>;  // Backend stores capabilities here
  standalone_agent_id?: string;  // Back-reference to a reusable standalone agent
  order_index?: number;          // Position in the team (sequential pattern)
  last_active?: string;
  created: string;
  updated?: string;  // Optional since backend doesn't have it
}

export interface AgentTeam {
  id: string;
  name: string;
  description?: string;
  notebook_id?: string;  // Optional - team can be global
  agents: Agent[];
  status: TeamStatus;
  current_task?: string;
  orchestration_pattern?: OrchestrationPattern;
  pattern_config?: PatternConfig;
  created: string;
  updated: string;
}

export interface AgentTask {
  id: string;
  team_id: string;
  title: string;
  description: string;
  status: TaskStatus;
  assigned_agent_id?: string;
  assigned_agent_name?: string;
  depends_on: string[];
  blocked_by: string[];
  result?: string;
  error?: string;
  started_at?: string;
  completed_at?: string;
  created: string;
  updated: string;
}

export interface AgentMessage {
  id: string;
  team_id: string;
  from_agent_id: string;
  from_agent_name: string;
  to_agent_id?: string;
  to_agent_name?: string;
  // Backend (pattern executors) emits sender_id / recipient_id; the frontend
  // SSE layer mirrors them into from_/to_ above for legacy renderers, but
  // keep the raw fields available for components that want them.
  sender_id?: string;
  recipient_id?: string;
  content: string;
  message_type:
    | "task_assignment"
    | "result"
    | "question"
    | "feedback"
    | "status_update"
    | "broadcast"
    // Pattern-executor message kinds:
    | "task_assign"
    | "task_result"
    | "control"
    | "chat"
    | "tool_call"
    | "tool_result";
  timestamp: string;
  // Backend column name; kept alongside `timestamp` for legacy renderers.
  created?: string;
  metadata?: Record<string, any>;
}

export interface WorkflowStep {
  id: string;
  team_id: string;
  step_number: number;
  title: string;
  description: string;
  agent_id?: string;
  agent_name?: string;
  status: TaskStatus;
  started_at?: string;
  completed_at?: string;
  duration_ms?: number;
  output?: string;
}

export interface TeamExecution {
  id: string;
  team_id: string;
  query: string;
  status: TeamStatus;
  steps: WorkflowStep[];
  tasks: AgentTask[];
  messages: AgentMessage[];
  result?: string;
  started_at: string;
  completed_at?: string;
  total_duration_ms?: number;
  evaluations?: AgentEvaluation[];
  has_evaluations?: boolean;
}

export interface TeamCreateRequest {
  name: string;
  description?: string;
  notebook_id?: string;  // Optional - team can be global or tied to a notebook
  // New shape: compose the team from existing standalone agents.
  agent_ids?: string[];
  // How the agents collaborate. See backend/open_notebook/agents/patterns/.
  orchestration_pattern?: OrchestrationPattern;
  pattern_config?: PatternConfig;
  // Legacy inline-agent shape — accepted by the backend for back-compat.
  agent_configs?: AgentConfig[];
  config?: Record<string, any>;
}

export interface AgentConfig {
  name: string;
  role: AgentRole;
  description: string;
  model?: string;
  tools?: string[];
  capabilities?: string[];
}

// ---------------------------------------------------------------------------
// Team architecture patterns
// ---------------------------------------------------------------------------

export type OrchestrationPattern =
  | "orchestrator_worker"
  | "sequential"
  | "parallel"
  | "review_critique"
  | "router"
  | "group_chat";

export interface PatternConfig {
  // orchestrator_worker, router
  orchestrator_agent_id?: string;
  // review_critique
  producer_agent_id?: string;
  reviewer_agent_id?: string;
  max_rounds?: number;
  // parallel (optional aggregator)
  aggregator_agent_id?: string;
  // group_chat
  max_turns?: number;
  // free-form for future patterns / advanced overrides
  [key: string]: any;
}

export interface OrchestrationPatternMeta {
  key: OrchestrationPattern;
  label: string;
  tagline: string;
  description: string;
}

export const ORCHESTRATION_PATTERNS: OrchestrationPatternMeta[] = [
  {
    key: "orchestrator_worker",
    label: "Orchestrator-Worker",
    tagline: "Supervisor / Subagents",
    description:
      "One orchestrator decomposes the goal into subtasks, dispatches each to a worker, then synthesizes results.",
  },
  {
    key: "sequential",
    label: "Sequential",
    tagline: "The Assembly Line",
    description:
      "Agents run in order — each agent's output becomes the next agent's input.",
  },
  {
    key: "parallel",
    label: "Parallel",
    tagline: "Fan-Out / Fan-In",
    description:
      "All agents run concurrently on the same query; an aggregator combines their answers.",
  },
  {
    key: "review_critique",
    label: "Review & Critique",
    tagline: "The Multi-Agent Loop",
    description:
      "Producer drafts → reviewer critiques → producer revises, looping until approved or max rounds reached.",
  },
  {
    key: "router",
    label: "Router",
    tagline: "The Concierge",
    description:
      "A router agent classifies the query and forwards it to one specialist.",
  },
  {
    key: "group_chat",
    label: "Group Chat / Swarm",
    tagline: "Collaborative Networks",
    description:
      "All agents share a turn-based chat for several rounds, then a synthesizer summarizes.",
  },
];

// ============================================================================
// EVALUATION TYPES
// ============================================================================

export interface EvaluationConfig {
  team_id: string;
  enabled: boolean;
  auto_evaluate: boolean;
  scope: "final_only" | "agents_only" | "all";
  scoring_scale: "0-10" | "1-5" | "percentage";
  created?: string;
  updated?: string;
}

export interface CriteriaScores {
  accuracy?: number;
  completeness?: number;
  quality?: number;
  consistency?: number;
}

export interface AgentEvaluation {
  id: string;
  execution_id: string;
  team_id: string;
  judge_agent_id?: string;
  judge_name?: string;
  scope: "final_result" | "agent_output";
  target_agent_id?: string;
  target_agent_name?: string;
  overall_score: number;
  criteria_scores: CriteriaScores;
  feedback: string;
  approval_status: "approved" | "needs_revision" | "requires_rework";
  confidence: number;
  created: string;
}

export interface ExecutionEvaluations {
  execution_id: string;
  evaluations: AgentEvaluation[];
  total: number;
}


export interface TeamExecuteRequest {
  query: string;
  context_source_ids?: string[];
  notebook_id?: string;
  max_steps?: number;
  prompt_role?: string; // Role of prompt template to use for execution
}

// ============================================================================
// MEMORY SYSTEM TYPES
// ============================================================================

export type MemoryType = "episodic" | "semantic" | "procedural" | "working";
export type MemoryPriority = "low" | "medium" | "high" | "critical";

export interface Memory {
  id: string;
  memory_type: MemoryType;
  content: string;
  summary?: string;
  tags: string[];
  priority: MemoryPriority;
  source_agent_id?: string;
  source_agent_name?: string;
  context?: Record<string, any>;
  embedding_id?: string;
  access_count: number;
  last_accessed?: string;
  expires_at?: string;
  created: string;
  updated: string;
}

export interface MemoryCreate {
  memory_type: MemoryType;
  content: string;
  summary?: string;
  tags?: string[];
  priority?: MemoryPriority;
  context?: Record<string, any>;
  expires_at?: string;
}

export interface MemoryUpdate {
  content?: string;
  summary?: string;
  tags?: string[];
  priority?: MemoryPriority;
  context?: Record<string, any>;
  expires_at?: string;
}

export interface MemorySearchRequest {
  query: string;
  memory_types?: MemoryType[];
  tags?: string[];
  limit?: number;
  min_relevance?: number;
}

export interface MemorySearchResult {
  memory: Memory;
  relevance_score: number;
  highlights?: string[];
}

// ============================================================================
// STANDALONE AGENT TYPES
// ============================================================================

export interface StandaloneAgent {
  id: string;
  name: string;
  description?: string;
  role: AgentRole | "custom";
  system_prompt?: string;
  model_name?: string;
  notebook_id?: string;
  tool_ids?: string[];
  mcp_server_ids?: string[];
  data_source_ids?: string[];
  skill_ids?: string[];
  config?: Record<string, any>;
  status: "active" | "inactive" | "archived";
  created: string;
  updated: string;
}

export interface StandaloneAgentCreate {
  name: string;
  description?: string;
  role: AgentRole | "custom";
  system_prompt?: string;
  model_name?: string;
  notebook_id?: string;
  tool_ids?: string[];
  mcp_server_ids?: string[];
  data_source_ids?: string[];
  skill_ids?: string[];
  config?: Record<string, any>;
}

export interface StandaloneAgentUpdate {
  name?: string;
  description?: string;
  role?: AgentRole | "custom";
  system_prompt?: string;
  model_name?: string;
  notebook_id?: string;
  tool_ids?: string[];
  mcp_server_ids?: string[];
  data_source_ids?: string[];
  skill_ids?: string[];
  config?: Record<string, any>;
  status?: "active" | "inactive" | "archived";
}

export interface StandaloneAgentExecuteRequest {
  query: string;
  context_source_ids?: string[];
  session_id?: string;
  max_steps?: number;
  stream?: boolean;
}

export interface StandaloneAgentExecutionStep {
  step_number: number;
  action: string;
  status: string;
  tool_name?: string;
  tool_input?: Record<string, any>;
  result?: string;
  started_at?: string;
  completed_at?: string;
}

export interface StandaloneAgentExecution {
  id: string;
  agent_id: string;
  query: string;
  status: "running" | "completed" | "failed" | "cancelled";
  steps?: StandaloneAgentExecutionStep[];
  result?: string;
  error?: string;
  context?: Record<string, any>;
  tool_calls?: Array<Record<string, any>>;
  started_at: string;
  completed_at?: string;
  duration_ms?: number;
  created: string;
}
