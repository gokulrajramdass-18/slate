"""
Pydantic models for API request/response validation

Defines schemas for:
- Notebooks
- Sources (including HANA tables and API sources)
- Database configuration
- Common response models
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Literal, Union
from enum import Enum
import json

from pydantic import BaseModel, Field, HttpUrl, field_validator, ConfigDict


# ============================================================================
# Enums
# ============================================================================

class MicrositeStatus(str, Enum):
    """Status states for microsites"""
    DRAFT = "draft"
    PUBLISHED = "published"
    BLOCKED = "blocked"


class SourceType(str, Enum):
    """Source types supported by the system"""
    FILE = "file"
    URL = "url"
    TEXT = "text"
    YOUTUBE = "youtube"
    HANA_TABLE = "hana_table"
    API = "api"


class DatabaseType(str, Enum):
    """Supported database types"""
    SQLITE = "sqlite"
    HANA = "hana"


class AuthType(str, Enum):
    """Authentication types for API sources"""
    NONE = "none"
    BASIC = "basic"
    BEARER = "bearer"
    OAUTH2_CLIENT = "oauth2_client"
    OAUTH2_AUTH_CODE = "oauth2_auth_code"
    API_KEY = "api_key"


class SyncFrequency(str, Enum):
    """Sync frequency options"""
    MANUAL = "manual"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


# ============================================================================
# Notebook Models
# ============================================================================

class NotebookBase(BaseModel):
    """Base notebook model with common fields"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    folder_id: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list)
    goal: Optional[str] = None  # Workspace goal (optional in responses for backward compatibility)

    @field_validator('tags', mode='before')
    @classmethod
    def parse_tags(cls, v: Union[str, List[str], None]) -> List[str]:
        """Parse tags from JSON string if needed"""
        if v is None:
            return []
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            if not v or v == '[]':
                return []
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except (json.JSONDecodeError, TypeError):
                return []
        return []


class NotebookCreate(NotebookBase):
    """Model for creating a new notebook"""
    goal: str = Field(..., min_length=1, description="Workspace goal")  # Required for new workspaces


class NotebookUpdate(BaseModel):
    """Model for updating an existing notebook"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    folder_id: Optional[str] = None
    tags: Optional[List[str]] = None
    goal: Optional[str] = None


class NotebookResponse(NotebookBase):
    """Model for notebook responses"""
    id: str
    created: datetime
    updated: datetime
    source_count: Optional[int] = 0
    note_count: Optional[int] = 0
    is_bookmarked: Optional[bool] = None
    has_plan: Optional[bool] = False  # Whether workspace has an AI-generated plan

    class Config:
        from_attributes = True


# ============================================================================
# Source Models - Base
# ============================================================================

class SourceBase(BaseModel):
    """Base source model"""
    title: str = Field(..., min_length=1, max_length=255)
    source_type: SourceType
    description: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list)


class SourceCreate(SourceBase):
    """Model for creating a source (base fields)"""
    notebook_id: Optional[str] = None  # Optional - source can exist standalone or in a notebook
    # Additional fields depend on source_type
    connection_config: Optional[Dict[str, Any]] = None
    sync_config: Optional[Dict[str, Any]] = None
    content: Optional[str] = None  # For text sources
    url: Optional[str] = None  # For URL/YouTube sources


class SourceUpdate(BaseModel):
    """Model for updating a source"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    connection_config: Optional[Dict[str, Any]] = None
    sync_config: Optional[Dict[str, Any]] = None


class SourceResponse(SourceBase):
    """Model for source responses"""
    id: str
    created: datetime
    updated: datetime
    last_synced: Optional[datetime] = None
    sync_status: Optional[str] = None
    error_message: Optional[str] = None
    chunk_count: Optional[int] = 0
    notebooks: Optional[List[Dict[str, str]]] = []  # List of {id, name} dicts
    is_bookmarked: Optional[bool] = None

    # Include content fields for full source data
    full_text: Optional[str] = None
    asset_data: Optional[str] = None  # JSON string
    asset_type: Optional[str] = None

    class Config:
        from_attributes = True

    @property
    def youtube_metadata(self) -> Optional[Dict[str, Any]]:
        """Return parsed YouTube metadata if source is YouTube type."""
        if self.source_type == SourceType.YOUTUBE and self.asset_data:
            try:
                if isinstance(self.asset_data, str):
                    return json.loads(self.asset_data)
                return self.asset_data
            except:
                return None
        return None


# ============================================================================
# HANA Table Source Models
# ============================================================================

class HANAConnectionConfig(BaseModel):
    """HANA database connection configuration"""
    model_config = ConfigDict(protected_namespaces=())  # Allow 'schema' field

    host: str = Field(..., description="HANA server hostname or IP")
    port: int = Field(default=443, ge=1, le=65535)
    database: str = Field(..., description="Database/schema name")
    user: str = Field(..., description="Database username")
    password: str = Field(..., description="Database password")
    encrypt: bool = Field(default=True, description="Use encrypted connection")
    schema: Optional[str] = Field(None, description="Schema name (if different from database)")


class HANATableConfig(BaseModel):
    """Configuration for HANA table source"""
    connection_id: Optional[str] = Field(None, description="ID of saved HANA connection")
    connection: Optional[HANAConnectionConfig] = Field(None, description="Direct connection config (legacy)")
    table_name: str = Field(..., description="Name of the table to sync")
    query: Optional[str] = Field(None, description="Optional SQL query to filter data")
    key_column: str = Field(default="id", description="Column to use as unique identifier")
    content_columns: List[str] = Field(..., description="Columns to include in content")


class HANATableSourceCreate(BaseModel):
    """Create HANA table source"""
    name: str = Field(..., min_length=1, max_length=255)
    notebook_id: Optional[str] = None  # Optional - source can exist standalone or in a notebook
    description: Optional[str] = None
    config: HANATableConfig
    sync_frequency: SyncFrequency = SyncFrequency.MANUAL


class HANATestConnectionRequest(BaseModel):
    """Request to test HANA connection"""
    connection: HANAConnectionConfig


class HANATestConnectionResponse(BaseModel):
    """Response from HANA connection test"""
    success: bool
    message: str
    server_version: Optional[str] = None
    latency_ms: Optional[float] = None


class HANATableInfo(BaseModel):
    """Information about a HANA table"""
    schema_name: str
    table_name: str
    table_type: str  # TABLE, VIEW, etc.
    record_count: Optional[int] = None
    columns: Optional[List[str]] = None


class HANAListTablesRequest(BaseModel):
    """Request to list HANA tables"""
    connection: HANAConnectionConfig
    schema_filter: Optional[str] = Field(None, description="Filter by schema name")


class HANAListTablesResponse(BaseModel):
    """Response for listing HANA tables"""
    success: bool
    message: str
    tables: Optional[List[HANATableInfo]] = Field(default_factory=list)
    total_count: Optional[int] = 0


# ============================================================================
# API Source Models
# ============================================================================

class BasicAuthConfig(BaseModel):
    """Basic authentication configuration"""
    username: str
    password: str


class BearerTokenConfig(BaseModel):
    """Bearer token authentication"""
    token: str


class APIKeyConfig(BaseModel):
    """API key authentication"""
    key: str
    header_name: str = Field(default="X-API-Key")
    prefix: Optional[str] = Field(None, description="Optional prefix (e.g., 'Bearer')")


class OAuth2ClientConfig(BaseModel):
    """OAuth 2.0 Client Credentials Flow"""
    client_id: str
    client_secret: str
    token_url: str
    scope: Optional[str] = None


class OAuth2AuthCodeConfig(BaseModel):
    """OAuth 2.0 Authorization Code Flow"""
    client_id: str
    client_secret: str
    authorization_url: str
    token_url: str
    redirect_uri: str
    scope: Optional[str] = None
    state: Optional[str] = None


class APISourceConfig(BaseModel):
    """Configuration for API source"""
    connection_id: Optional[str] = Field(None, description="ID of saved API connection")
    url: Optional[str] = Field(None, description="API endpoint URL (legacy, use connection_id)")
    method: Literal["GET", "POST"] = Field(default="GET")
    auth_type: AuthType = AuthType.NONE
    auth_config: Optional[Dict[str, Any]] = Field(None, description="Auth configuration based on auth_type")
    headers: Optional[Dict[str, str]] = Field(default_factory=dict)
    query_params: Optional[Dict[str, str]] = Field(default_factory=dict)
    body: Optional[Dict[str, Any]] = None
    json_path: Optional[str] = Field(None, description="JSONPath to extract data from response")
    pagination_config: Optional[Dict[str, Any]] = None

    @field_validator('auth_config')
    @classmethod
    def validate_auth_config(cls, v, info):
        """Validate auth_config matches auth_type"""
        values = info.data
        if 'auth_type' not in values:
            return v

        auth_type = values['auth_type']
        if auth_type == AuthType.NONE and v is not None:
            raise ValueError("auth_config should be None when auth_type is 'none'")
        elif auth_type != AuthType.NONE and v is None:
            raise ValueError(f"auth_config is required for auth_type '{auth_type}'")

        return v


class APISourceCreate(BaseModel):
    """Create API source"""
    name: str = Field(..., min_length=1, max_length=255)
    notebook_id: Optional[str] = None  # Optional - can be standalone
    description: Optional[str] = None
    config: APISourceConfig
    sync_frequency: SyncFrequency = SyncFrequency.MANUAL


class APITestRequest(BaseModel):
    """Request to test API connection"""
    config: APISourceConfig


class APITestResponse(BaseModel):
    """Response from API connection test"""
    success: bool
    message: str
    status_code: Optional[int] = None
    response_size: Optional[int] = None
    latency_ms: Optional[float] = None
    sample_data: Optional[Dict[str, Any]] = None


# ============================================================================
# Source Sync Models
# ============================================================================

class SyncTriggerRequest(BaseModel):
    """Request to trigger a source sync"""
    force: bool = Field(default=False, description="Force sync even if recently synced")


class SyncTriggerResponse(BaseModel):
    """Response from sync trigger"""
    success: bool
    message: str
    job_id: Optional[str] = None
    estimated_time: Optional[int] = None  # seconds


class SyncStatusResponse(BaseModel):
    """Response with sync status for a source"""
    source_id: str
    sync_status: Optional[str] = None
    last_synced: Optional[datetime] = None
    error_message: Optional[str] = None
    latest_sync: Optional[Dict[str, Any]] = None
    scheduled_job: Optional[Dict[str, Any]] = None


class SyncHistoryRecord(BaseModel):
    """Single sync history record"""
    id: str
    source_id: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    rows_updated: int = 0
    duration_seconds: Optional[float] = None
    error: Optional[str] = None
    created: datetime


class SyncHistoryResponse(BaseModel):
    """Response with sync history"""
    source_id: str
    history: List[SyncHistoryRecord]
    total: int


class SyncConfigUpdateRequest(BaseModel):
    """Request to update sync configuration"""
    frequency: SyncFrequency = Field(..., description="Sync frequency")


class SyncConfigUpdateResponse(BaseModel):
    """Response from sync config update"""
    success: bool
    message: str
    source_id: str
    frequency: str
    cron: Optional[str] = None
    next_run: Optional[str] = None
    scheduled: bool


# ============================================================================
# Database Configuration Models
# ============================================================================

class SQLiteConfig(BaseModel):
    """SQLite database configuration"""
    db_path: str = Field(default="./data/database.db")
    pool_size: int = Field(default=20, ge=1, le=50)
    timeout: int = Field(default=30, ge=5, le=300)


class HANAConfig(BaseModel):
    """HANA Cloud database configuration"""
    host: str
    port: int = Field(default=443, ge=1, le=65535)
    database: str
    user: str
    password: str
    encrypt: bool = True
    pool_size: int = Field(default=10, ge=1, le=50)
    max_overflow: int = Field(default=20, ge=0, le=100)
    pool_timeout: int = Field(default=30, ge=5, le=300)


class DatabaseConfig(BaseModel):
    """Database configuration wrapper"""
    db_type: DatabaseType
    sqlite_config: Optional[SQLiteConfig] = None
    hana_config: Optional[HANAConfig] = None

    @field_validator('sqlite_config', 'hana_config')
    @classmethod
    def validate_config(cls, v, info):
        """Ensure correct config is provided for db_type"""
        values = info.data
        field_name = info.field_name

        if 'db_type' not in values:
            return v

        db_type = values['db_type']
        if db_type == DatabaseType.SQLITE and field_name == 'sqlite_config' and v is None:
            raise ValueError("sqlite_config is required when db_type is 'sqlite'")
        if db_type == DatabaseType.HANA and field_name == 'hana_config' and v is None:
            raise ValueError("hana_config is required when db_type is 'hana'")

        return v


class DatabaseConfigResponse(DatabaseConfig):
    """Response model for database configuration (masks passwords)"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "current_type": "sqlite",
                "sqlite_config": {"db_path": "./data/database.db"},
                "hana_config": {
                    "host": "example.hanacloud.ondemand.com",
                    "port": 443,
                    "database": "mydb",
                    "user": "myuser",
                    "password": "********",
                    "encrypt": True
                }
            }
        }
    )


class DatabaseTestConnectionRequest(BaseModel):
    """Request to test database connection"""
    config: DatabaseConfig


class DatabaseTestConnectionResponse(BaseModel):
    """Response from database connection test"""
    success: bool
    message: str
    db_type: DatabaseType
    server_version: Optional[str] = None
    latency_ms: Optional[float] = None


class DatabaseSwitchRequest(BaseModel):
    """Request to switch database"""
    target_type: DatabaseType
    config: DatabaseConfig
    migrate_data: bool = Field(default=False, description="Migrate existing data to new database")


class DatabaseSwitchResponse(BaseModel):
    """Response from database switch"""
    success: bool
    message: str
    previous_type: DatabaseType
    current_type: DatabaseType
    migration_status: Optional[str] = None


class DatabaseStatus(BaseModel):
    """Current database status"""
    db_type: DatabaseType
    connected: bool
    connection_pool_size: Optional[int] = None
    active_connections: Optional[int] = None
    total_records: Optional[int] = None
    notebooks_count: Optional[int] = None
    sources_count: Optional[int] = None
    notes_count: Optional[int] = None
    last_backup: Optional[datetime] = None
    uptime_seconds: Optional[int] = None


# ============================================================================
# Common Response Models
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


class SuccessResponse(BaseModel):
    """Generic success response"""
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None


class PaginatedResponse(BaseModel):
    """Paginated response wrapper"""
    items: List[Any]
    total: int
    page: int = 1
    page_size: int = 50
    has_next: bool
    has_prev: bool


class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str  # "healthy", "degraded", "unhealthy"
    database: str  # "connected", "disconnected"
    version: str
    uptime_seconds: int


# ============================================================================
# Chat Models
# ============================================================================

class ChatSessionBase(BaseModel):
    """Base chat session model"""
    model_config = {"protected_namespaces": ()}

    title: Optional[str] = "New Chat"
    notebook_id: Optional[str] = None  # Made optional, will auto-create default notebook if None


class ChatSessionCreate(ChatSessionBase):
    """Model for creating a chat session"""
    model_override: Optional[str] = Field(None, description="Optional AI model override for this session")
    selected_source_ids: Optional[List[str]] = Field(None, description="Optional list of source IDs to include in context")


class ChatSessionUpdate(BaseModel):
    """Model for updating a chat session"""
    model_config = {"protected_namespaces": ()}

    title: Optional[str] = None
    model_override: Optional[str] = None


class ChatSessionResponse(ChatSessionBase):
    """Model for chat session responses"""
    id: str
    created: datetime
    updated: datetime
    message_count: Optional[int] = 0
    workspace_name: Optional[str] = None

    class Config:
        from_attributes = True


class ChatMessageBase(BaseModel):
    """Base chat message model"""
    role: str = Field(..., description="Message role: user, assistant, or system")
    content: str = Field(..., min_length=1)


class ChatMessageCreate(ChatMessageBase):
    """Model for creating a chat message"""
    pass


class ChatMessageResponse(ChatMessageBase):
    """Model for chat message responses"""
    id: str
    session_id: str
    created: datetime
    sources: Optional[List[Dict[str, Any]]] = Field(
        None, description="Sources used for context in this response (notebook sources + tool results)"
    )
    ui_components: Optional[List[Dict[str, Any]]] = Field(
        None, description="UI component specs for generative UI rendering"
    )
    render_mode: Optional[str] = Field(
        "markdown", description="Render mode: markdown, generative_ui, hybrid"
    )
    tool_results: Optional[List[Dict[str, Any]]] = Field(
        None, description="Raw tool execution results"
    )
    agent_steps: Optional[str] = Field(
        None, description="JSON string of agent execution steps"
    )
    langfuse_trace_id: Optional[str] = Field(
        None, description="Langfuse trace ID for observability"
    )
    langfuse_observation_id: Optional[str] = Field(
        None, description="Langfuse observation ID for observability"
    )

    class Config:
        from_attributes = True

    @field_validator("ui_components", "tool_results", "sources", mode="before")
    @classmethod
    def parse_json_fields(cls, v):
        """Deserialize JSON strings stored in the database."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return v


class ChatRequest(BaseModel):
    """Request model for sending a chat message"""
    message: str = Field(..., min_length=1, description="User message")
    stream: bool = Field(default=False, description="Whether to stream the response")
    include_context: bool = Field(default=True, description="Whether to include notebook context")
    selected_source_ids: Optional[List[str]] = Field(None, description="Optional source IDs for context")
    selected_tool_ids: Optional[List[str]] = Field(None, description="Optional tool IDs to enable (filters available tools)")
    max_context_tokens: Optional[int] = Field(12000, ge=100, le=32000, description="Maximum tokens for context")
    enable_generative_ui: bool = Field(default=False, description="Enable generative UI component generation from tool results")
    deep_research: bool = Field(default=False, description="Enable deep research mode for comprehensive autonomous research")


class ChatResponse(BaseModel):
    """Response model for chat message"""
    session_id: str
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
    context_info: Optional[Dict[str, Any]] = Field(None, description="Information about context used")


# ============================================================================
# Generative UI Models
# ============================================================================

class RenderMode(str, Enum):
    """Render mode for chat messages"""
    MARKDOWN = "markdown"
    GENERATIVE_UI = "generative_ui"
    HYBRID = "hybrid"


class UIComponentData(BaseModel):
    """
    Specification for a single UI component to be rendered by the frontend.

    The frontend component registry uses `component_type` to resolve the
    React component, and passes `props` as component properties.
    """
    component_type: str = Field(
        ...,
        description="Component type key (e.g., 'hana_data_table', 'metric_card', 'bar_chart')"
    )
    props: Dict[str, Any] = Field(
        default_factory=dict,
        description="Properties passed to the React component"
    )
    layout: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional layout hints (width, height, priority, position)"
    )


class ToolResultData(BaseModel):
    """
    Captured result from a tool execution during agent processing.

    Used as input to the ComponentGenerator to decide which UI components
    to render for a given tool call.
    """
    tool_name: str = Field(..., description="Name of the executed tool")
    tool_input: Dict[str, Any] = Field(
        default_factory=dict,
        description="Input arguments passed to the tool"
    )
    result: Any = Field(..., description="Raw result returned by the tool")
    result_type: str = Field(
        "unknown",
        description="Inferred type: 'tabular', 'scalar', 'list', 'chart', 'error', 'empty'"
    )
    suggested_component: Optional[str] = Field(
        None,
        description="Suggested component type for rendering this result"
    )
    visualization_hint: Optional[str] = Field(
        None,
        description="Specific visualization type hint: 'line', 'bar', 'pie', 'scatter', 'area', 'radar', 'composed'"
    )
    execution_time_ms: Optional[float] = Field(
        None, description="Tool execution duration in milliseconds"
    )


# ============================================================================
# Deep Research Models
# ============================================================================

class ResearchPhase(str, Enum):
    """Phases of deep research"""
    INITIALIZING = "initializing"
    ANALYZING_QUERY = "analyzing_query"
    DECOMPOSING = "decomposing"
    SEARCHING = "searching"
    SYNTHESIZING = "synthesizing"
    FINALIZING = "finalizing"
    COMPLETE = "complete"
    ERROR = "error"


class DeepResearchRequest(BaseModel):
    """Request model for deep research mode"""
    message: str = Field(..., min_length=1, description="Research query from user")
    max_iterations: int = Field(default=5, ge=1, le=10, description="Maximum research iterations")
    search_strategies: Optional[List[str]] = Field(
        default=["hybrid", "vector"],
        description="Search strategies to use (hybrid, vector, keyword, agentic_rag)"
    )


class DeepResearchJobResponse(BaseModel):
    """Response when starting a deep research job"""
    job_id: str = Field(..., description="Unique job ID for tracking")
    status: str = Field(default="queued", description="Initial job status")
    estimated_time: int = Field(default=120, description="Estimated time in seconds")
    message: str = Field(default="Deep research job queued")


class DeepResearchProgressUpdate(BaseModel):
    """Progress update during deep research"""
    job_id: str
    phase: ResearchPhase
    progress: int = Field(..., ge=0, le=100, description="Progress percentage")
    message: Optional[str] = None
    intermediate_results: Optional[List[Dict[str, Any]]] = None


class DeepResearchResult(BaseModel):
    """Final result from deep research"""
    job_id: str
    status: str = Field(default="complete")
    phase: ResearchPhase
    final_report: str = Field(..., description="Comprehensive research report in Markdown")
    key_findings: List[Dict[str, Any]] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    search_results_count: int = Field(default=0)
    sub_questions_count: int = Field(default=0)
    duration_seconds: Optional[float] = None
    created_at: Optional[datetime] = None


class DeepResearchStatusResponse(BaseModel):
    """Response for checking deep research job status"""
    job_id: str
    status: str = Field(..., description="queued, running, complete, failed")
    phase: Optional[ResearchPhase] = None
    progress: int = Field(default=0, ge=0, le=100)
    message: Optional[str] = None
    result: Optional[DeepResearchResult] = None
    error: Optional[str] = None


# ============================================================================
# Microsite Generator Models
# ============================================================================

class MicrositeGenerateRequest(BaseModel):
    """Request to trigger microsite generation from template + sources"""
    template_id: str = Field(..., description="ID of the template to use")
    source_ids: List[str] = Field(..., min_length=1, description="Source IDs to include in generation")
    user_prompt: Optional[str] = Field(None, max_length=2000, description="Optional user prompt for AI guidance")


class ContentSectionUpdate(BaseModel):
    """Update for a single content section"""
    section_id: str = Field(..., description="ID of the section to update")
    content_html: Optional[str] = Field(None, description="Updated HTML content")
    content_json: Optional[str] = Field(None, description="Updated TipTap JSON content")


class MicrositeContentUpdate(BaseModel):
    """Request to update microsite content sections"""
    sections: List[ContentSectionUpdate] = Field(..., min_length=1, description="Sections to update")
    custom_css: Optional[str] = Field(None, description="Custom CSS to apply to the microsite")


class ModerationIssueSeverity(str, Enum):
    """Severity levels for moderation issues"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ModerationIssue(BaseModel):
    """A single issue found during content moderation"""
    type: str = Field(..., description="Issue type: ai_filter, keyword_blocklist, source_validation")
    description: str = Field(..., description="Human-readable description of the issue")
    severity: ModerationIssueSeverity = Field(..., description="Issue severity")
    location: Optional[str] = Field(None, description="Section or location where issue was found")


class ModerationLayerResult(BaseModel):
    """Result from a single moderation layer"""
    layer: str = Field(..., description="Layer name: ai_filter, keyword_blocklist, source_validation, user_review")
    status: str = Field(..., description="Layer status: passed, warning, blocked, error")
    score: float = Field(..., ge=0.0, le=1.0, description="Layer score (0.0 = worst, 1.0 = best)")
    issues: List[ModerationIssue] = Field(default_factory=list)
    message: Optional[str] = None


class ModerationReport(BaseModel):
    """Comprehensive moderation report from guardrails pipeline"""
    status: str = Field(..., description="Overall status: passed, warning, blocked")
    overall_score: float = Field(..., ge=0.0, le=1.0, description="Weighted overall score")
    layers: List[ModerationLayerResult] = Field(default_factory=list, description="Results from each moderation layer")
    issues: List[ModerationIssue] = Field(default_factory=list, description="All issues across all layers")
    requires_review: bool = Field(default=False, description="Whether manual review is required")


class MicrositeContentSection(BaseModel):
    """A content section within a microsite"""
    id: str
    microsite_id: str
    section_id: str = Field(..., description="Section ID matching template structure: hero, summary, insights, sources_list, conclusion, etc.")
    order_num: int = Field(default=0, description="Display order")
    content_html: Optional[str] = None
    content_json: Optional[str] = None
    is_visible: bool = True
    created: Optional[datetime] = None
    updated: Optional[datetime] = None


class MicrositeGenerateResponse(BaseModel):
    """Response from microsite generation"""
    microsite_id: str
    version: int = Field(..., description="Version number of the generated content")
    sections: List[MicrositeContentSection] = Field(default_factory=list)
    moderation: ModerationReport
    preview_url: str = Field(..., description="URL to preview the generated microsite")


class MicrositeContentResponse(BaseModel):
    """Response containing microsite content sections"""
    microsite_id: str
    template_id: Optional[str] = None
    custom_css: Optional[str] = None
    sections: List[MicrositeContentSection] = Field(default_factory=list)


class MicrositeContentUpdateResponse(BaseModel):
    """Response from content update"""
    updated_sections: List[MicrositeContentSection] = Field(default_factory=list)
    new_version: int = Field(..., description="New version number after update")


class ModerationRequest(BaseModel):
    """Request to run moderation on specific sections or all"""
    section_ids: Optional[List[str]] = Field(None, description="Specific section IDs to moderate (None = all)")


class ModerationLogEntry(BaseModel):
    """A single moderation log entry"""
    id: str
    microsite_id: str
    content_section: Optional[str] = Field(None, description="Section ID or 'full' for whole-site moderation")
    moderation_type: str = Field(..., description="ai_filter, keyword_blocklist, source_validation, user_review")
    status: str
    score: float
    issues_found: Optional[str] = Field(None, description="JSON array of issue objects")
    metadata: Optional[str] = Field(None, description="JSON: additional context")
    created: Optional[datetime] = None


class ModerationHistoryResponse(BaseModel):
    """Response containing moderation history"""
    microsite_id: str
    logs: List[ModerationLogEntry] = Field(default_factory=list)
    summary: Optional[Dict[str, Any]] = None


class MicrositeTemplateSection(BaseModel):
    """A section definition within a template"""
    id: str
    type: str = Field(..., description="Section type: hero, summary, insights, etc.")
    prompt_template: str = Field(..., description="AI prompt template for content generation")
    default_content: Optional[Dict[str, Any]] = None


class MicrositeTemplateResponse(BaseModel):
    """Response for a microsite template"""
    id: str
    name: str
    display_name: str = Field(..., description="Human-readable template name")
    description: Optional[str] = None
    structure: Optional[str] = Field(None, description="Template structure as JSON string (sections, layout, prompts)")
    default_styles: Optional[str] = Field(None, description="Default styles as JSON string (CSS variables, fonts, colors)")
    preview_image: Optional[str] = Field(None, description="Base64-encoded preview image or URL")
    is_custom: bool = False
    created: Optional[datetime] = None


class MicrositeTemplateListResponse(BaseModel):
    """Response for listing templates"""
    templates: List[MicrositeTemplateResponse] = Field(default_factory=list)


class MicrositeVersionResponse(BaseModel):
    """Response for a microsite version snapshot"""
    id: str
    microsite_id: str
    version_number: int
    full_html: Optional[str] = None
    full_css: Optional[str] = None
    content_snapshot: Optional[str] = Field(None, description="JSON snapshot of all content sections")
    created_by: Optional[str] = Field(None, description="User or 'system' for auto-generated")
    created: Optional[datetime] = None


class MicrositeVersionListResponse(BaseModel):
    """Response for listing microsite versions"""
    microsite_id: str
    versions: List[MicrositeVersionResponse] = Field(default_factory=list)


class MicrositeRollbackRequest(BaseModel):
    """Request to rollback to a specific version"""
    version_number: int = Field(..., ge=1, description="Version number to rollback to")


class MicrositeRollbackResponse(BaseModel):
    """Response from version rollback"""
    microsite_id: str
    restored_version: int
    new_version: int = Field(..., description="New version number created from rollback")
    sections: List[MicrositeContentSection] = Field(default_factory=list)


# ============================================================================
# Microsite Status Management Models
# ============================================================================

class MicrositePublishRequest(BaseModel):
    """Request to publish a microsite"""
    version_message: Optional[str] = Field(None, description="Optional message for this version")


class MicrositePublishResponse(BaseModel):
    """Response after publishing"""
    microsite_id: str
    status: MicrositeStatus
    active_version_id: str
    version_number: int
    published_at: str


class MicrositeBlockRequest(BaseModel):
    """Request to block a microsite"""
    reason: str = Field(..., description="Reason for blocking")


class MicrositeAccessCheckResponse(BaseModel):
    """Response for access check"""
    has_access: bool
    status: MicrositeStatus
    reason: Optional[str] = None


class MicrositeActiveVersionResponse(BaseModel):
    """Response for active version query"""
    microsite_id: str
    active_version_id: Optional[str] = None
    version_number: Optional[int] = None
    published_at: Optional[str] = None
    full_html: Optional[str] = None


# ============================================================================
# Tool Registry Models
# ============================================================================

class ToolType(str, Enum):
    """Supported tool types in the registry"""
    HANA_QUERY = "hana_query"
    API_CALL = "api_call"
    WEB_SEARCH = "web_search"
    CODE_EXEC = "code_exec"
    FILE_ANALYSIS = "file_analysis"
    CALCULATOR = "calculator"
    DATETIME = "datetime"
    URL_FETCH = "url_fetch"
    DATA_PARSER = "data_parser"
    TEXT_ANALYSIS = "text_analysis"
    WIKIPEDIA = "wikipedia"
    UNIT_CONVERTER = "unit_converter"
    CUSTOM = "custom"


class ToolCategory(str, Enum):
    """Tool categories"""
    DATA_QUERY = "data_query"
    WEB = "web"
    COMPUTATION = "computation"
    FILE_ANALYSIS = "file_analysis"


class ToolRegistryCreate(BaseModel):
    """Request model for registering a new tool"""
    name: str = Field(..., min_length=1, max_length=255)
    tool_type: ToolType
    category: Optional[ToolCategory] = None
    description: str = Field(..., min_length=1)
    enabled: bool = True
    default_config: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class ToolRegistryUpdate(BaseModel):
    """Request model for updating a tool"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    enabled: Optional[bool] = None
    category: Optional[ToolCategory] = None
    default_config: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class ToolRegistryResponse(BaseModel):
    """Response model for a tool registry entry"""
    id: str
    name: str
    tool_type: str
    category: Optional[str] = None
    description: Optional[str] = None
    enabled: bool = True
    default_config: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    created: Optional[datetime] = None
    updated: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_validator("default_config", "metadata", mode="before")
    @classmethod
    def parse_json(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return v


class ToolRegistryListResponse(BaseModel):
    """Response model for listing tools"""
    tools: List[ToolRegistryResponse] = Field(default_factory=list)
    total: int = 0


class ToolPermissionCreate(BaseModel):
    """Request model for creating a tool permission"""
    user_id: Optional[str] = None
    role: Optional[str] = None
    allowed: bool = True
    rate_limit: Optional[int] = Field(None, ge=1, le=10000, description="Max calls per minute")
    custom_config: Optional[Dict[str, Any]] = None

    @field_validator("role")
    @classmethod
    def validate_user_or_role(cls, v, info):
        """Ensure either user_id or role is set, not both."""
        user_id = info.data.get("user_id")
        if user_id and v:
            raise ValueError("Set either user_id or role, not both")
        if not user_id and not v:
            raise ValueError("Either user_id or role is required")
        return v


class ToolPermissionUpdate(BaseModel):
    """Request model for updating a tool permission"""
    allowed: Optional[bool] = None
    rate_limit: Optional[int] = Field(None, ge=1, le=10000)
    custom_config: Optional[Dict[str, Any]] = None


class ToolPermissionResponse(BaseModel):
    """Response model for a tool permission entry"""
    id: str
    tool_id: str
    user_id: Optional[str] = None
    role: Optional[str] = None
    allowed: bool = True
    rate_limit: Optional[int] = None
    custom_config: Optional[Dict[str, Any]] = None
    created: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_validator("custom_config", mode="before")
    @classmethod
    def parse_json_config(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return v


class ToolPermissionListResponse(BaseModel):
    """Response model for listing permissions"""
    permissions: List[ToolPermissionResponse] = Field(default_factory=list)


class ToolUsageStat(BaseModel):
    """Single day usage statistic"""
    date: str
    total_calls: int = 0
    avg_duration: Optional[float] = None
    successful_calls: int = 0
    failed_calls: int = 0


class ToolUsageResponse(BaseModel):
    """Response model for tool usage statistics"""
    tool_id: str
    usage: List[ToolUsageStat] = Field(default_factory=list)


class ToolUsageReportEntry(BaseModel):
    """Single tool entry in the usage report"""
    name: str
    category: Optional[str] = None
    total_calls: int = 0
    avg_duration: Optional[float] = None
    unique_users: int = 0


class ToolUsageReportResponse(BaseModel):
    """Response model for overall usage report"""
    report: List[ToolUsageReportEntry] = Field(default_factory=list)


# ============================================================================
# Agent Role Enum
# ============================================================================

class AgentRole(str, Enum):
    """Roles that agents can assume in a multi-agent team"""
    PLANNER = "planner"
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    WRITER = "writer"
    REVIEWER = "reviewer"
    SYNTHESIZER = "synthesizer"
    QUERY_SPECIALIST = "query_specialist"
    CUSTOM = "custom"


class AgentStatus(str, Enum):
    """Status of an agent within a team"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING = "waiting"


class TaskStatus(str, Enum):
    """Status of a task in the orchestration pipeline"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MemoryType(str, Enum):
    """Types of agent memory entries"""
    FACT = "fact"
    PREFERENCE = "preference"
    CONTEXT = "context"
    CONVERSATION = "conversation"
    INSIGHT = "insight"


# ============================================================================
# Agent Team Models
# ============================================================================

class AgentTeamCreate(BaseModel):
    """Request model for creating an agent team"""
    name: str = Field(..., min_length=1, max_length=255, description="Team name")
    notebook_id: Optional[str] = Field(None, description="Notebook this team operates on (optional)")
    description: Optional[str] = Field(None, description="Team purpose description")

    # New (preferred) shape: compose the team from existing standalone agents.
    # When agent_ids is provided, the backend hydrates one agent_instances row
    # per id (copying role/system_prompt/tools) and assigns order_index by
    # position in this list — which drives the sequential pattern's order.
    agent_ids: Optional[List[str]] = Field(
        default=None,
        description="IDs of standalone agents to add to this team (in order)",
    )

    # Architecture pattern that drives execution. See
    # backend/open_notebook/agents/patterns/factory.py for the registry.
    orchestration_pattern: Optional[str] = Field(
        default="orchestrator_worker",
        description="One of: orchestrator_worker | sequential | parallel | review_critique | router | group_chat",
    )
    pattern_config: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description=(
            "Per-pattern config. Keys: orchestrator_agent_id (orchestrator_worker, router), "
            "producer_agent_id + reviewer_agent_id + max_rounds (review_critique), "
            "aggregator_agent_id (parallel), max_turns (group_chat)."
        ),
    )

    # Legacy shape — inline agent definitions. Still accepted for back-compat
    # with older clients; new UI uses agent_ids instead.
    agent_configs: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        description="DEPRECATED: inline agent configs. Prefer agent_ids."
    )
    config: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Team-level configuration (max_iterations, timeout_seconds, etc.)"
    )


class AgentTeamResponse(BaseModel):
    """Response model for an agent team"""
    id: str
    name: str
    notebook_id: Optional[str] = None
    description: Optional[str] = None
    status: str = "idle"
    config: Optional[Dict[str, Any]] = None
    orchestration_pattern: Optional[str] = "orchestrator_worker"
    pattern_config: Optional[Dict[str, Any]] = None
    agent_count: int = 0
    agents: Optional[List["AgentResponse"]] = Field(default_factory=list, description="Optional list of agents in the team")
    created: Optional[datetime] = None
    updated: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_validator("config", "pattern_config", mode="before")
    @classmethod
    def parse_config_json(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return v


class AgentTeamListResponse(BaseModel):
    """Response model for listing agent teams"""
    teams: List[AgentTeamResponse] = Field(default_factory=list)
    total: int = 0


# ============================================================================
# Agent Models
# ============================================================================

class AgentSpawnRequest(BaseModel):
    """Request model for spawning an agent in a team"""
    role: AgentRole = Field(..., description="Agent role")
    name: Optional[str] = Field(None, description="Agent display name (auto-generated if omitted)")
    system_prompt: Optional[str] = Field(None, description="Custom system prompt override")
    model_override: Optional[str] = Field(None, description="LLM model override for this agent")
    tool_ids: Optional[List[str]] = Field(
        default_factory=list,
        description="Tool IDs from registry this agent can use"
    )
    config: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Agent-specific configuration"
    )


class AgentResponse(BaseModel):
    """Response model for a single agent"""
    id: str
    team_id: str
    role: str
    name: str
    status: str = "idle"
    system_prompt: Optional[str] = None
    model_override: Optional[str] = None
    tool_ids: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None
    standalone_agent_id: Optional[str] = None
    order_index: Optional[int] = 0
    last_active: Optional[datetime] = None
    created: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_validator("tool_ids", "config", mode="before")
    @classmethod
    def parse_json_fields_agent(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return v


class AgentListResponse(BaseModel):
    """Response model for listing agents in a team"""
    agents: List[AgentResponse] = Field(default_factory=list)
    total: int = 0


# ============================================================================
# Agent Task Models
# ============================================================================

class AgentTaskResponse(BaseModel):
    """Response model for an agent task"""
    id: str
    team_id: str
    assigned_agent_id: Optional[str] = None
    task_type: Optional[str] = None
    description: str
    status: str = "pending"
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    dependencies: Optional[List[str]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_validator("input_data", "output_data", "dependencies", mode="before")
    @classmethod
    def parse_json_fields_task(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return v


class AgentTaskListResponse(BaseModel):
    """Response model for listing tasks in a team"""
    tasks: List[AgentTaskResponse] = Field(default_factory=list)
    total: int = 0


# ============================================================================
# Team Execution Models
# ============================================================================

class TeamExecuteRequest(BaseModel):
    """Request model for executing an agent team"""
    query: str = Field(..., min_length=1, description="Query or task for the team to execute")
    context_source_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional source IDs to use as context"
    )
    notebook_id: Optional[str] = Field(None, description="Optional notebook for context")
    max_steps: Optional[int] = Field(10, ge=1, le=50, description="Maximum execution steps")
    stream: bool = Field(False, description="Whether to stream progress via SSE")
    prompt_role: Optional[str] = Field(None, description="Role of prompt template to use for execution")


class WorkflowStep(BaseModel):
    """A step in the workflow execution"""
    step_number: int
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    action: str
    status: str
    result: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class AgentMessage(BaseModel):
    """Message sent between agents or from agent to orchestrator"""
    id: str
    team_id: Optional[str] = None
    execution_id: str
    from_agent_id: str
    from_agent_name: Optional[str] = None
    to_agent_id: Optional[str] = None  # None = broadcast
    to_agent_name: Optional[str] = None
    message_type: str  # "task_request", "task_response", "status_update", "question", "answer"
    content: str
    metadata: Optional[Dict[str, Any]] = None
    created: str
    timestamp: Optional[str] = None  # For frontend compatibility


class TeamExecutionResponse(BaseModel):
    """Response model for team execution"""
    id: str
    team_id: str
    query: str
    status: str  # "running", "completed", "failed", "cancelled"
    steps: List[WorkflowStep] = Field(default_factory=list)
    tasks: List[AgentTaskResponse] = Field(default_factory=list)
    messages: List[AgentMessage] = Field(default_factory=list)
    result: Optional[str] = None
    started_at: str
    completed_at: Optional[str] = None


class TeamExecutionListResponse(BaseModel):
    """Response model for listing team executions"""
    executions: List[TeamExecutionResponse] = Field(default_factory=list)
    total: int = 0


# ============================================================================
# Agent Memory Models
# ============================================================================

class MemoryEntryCreate(BaseModel):
    """Request model for creating a memory entry"""
    memory_type: MemoryType = Field(..., description="Type of memory entry")
    content: str = Field(..., min_length=1, description="Memory content text")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional metadata (source, confidence, agent_id, etc.)"
    )
    tags: Optional[List[str]] = Field(
        default_factory=list,
        description="Tags for categorization"
    )


class MemoryEntryUpdate(BaseModel):
    """Request model for updating a memory entry"""
    content: Optional[str] = Field(None, min_length=1)
    memory_type: Optional[MemoryType] = None
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class MemoryEntryResponse(BaseModel):
    """Response model for a memory entry"""
    id: str
    notebook_id: str
    memory_type: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    created: Optional[datetime] = None
    updated: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_validator("metadata", "tags", mode="before")
    @classmethod
    def parse_json_fields_memory(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return v


class MemoryListResponse(BaseModel):
    """Response model for listing memory entries"""
    entries: List[MemoryEntryResponse] = Field(default_factory=list)
    total: int = 0


class MemorySearchRequest(BaseModel):
    """Request model for searching memory"""
    query: str = Field(..., min_length=1, description="Search query")
    memory_type: Optional[MemoryType] = Field(None, description="Filter by memory type")
    limit: int = Field(10, ge=1, le=100, description="Maximum results")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")


class MemorySearchResponse(BaseModel):
    """Response model for memory search results"""
    results: List[MemoryEntryResponse] = Field(default_factory=list)
    total: int = 0
    query: str


# ============================================================================
# Agentic Memory Layers (4-layer model)
# ============================================================================

class MemoryLayerEnum(str, Enum):
    """Canonical 4-layer agentic memory taxonomy.

    Short-term lives only in LangGraph state — it has no API surface; it's
    included here for completeness so the frontend can render a row for it.
    """
    SHORT_TERM = "short_term"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


class MemoryConfigModel(BaseModel):
    """Per-agent memory configuration. Persisted under StandaloneAgent.config['memory']."""
    short_term_enabled: bool = True

    episodic_enabled: bool = True
    episodic_retention_days: int = Field(90, ge=1, le=3650)
    episodic_max_entries: int = Field(500, ge=10, le=10_000)

    semantic_enabled: bool = True
    semantic_max_facts: int = Field(200, ge=10, le=10_000)

    procedural_enabled: bool = False
    procedural_min_attempts: int = Field(3, ge=1, le=100)
    procedural_min_success_rate: float = Field(0.6, ge=0.0, le=1.0)


class EpisodicEntryCreate(BaseModel):
    """Manual insert of an episodic memory (admin/debug use)."""
    content: str = Field(..., min_length=1)
    notebook_id: str = Field(..., description="Notebook context for this episode")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    tags: Optional[List[str]] = Field(default_factory=list)
    importance: float = Field(0.5, ge=0.0, le=1.0)
    source_message_id: Optional[str] = None


class SemanticEntryCreate(BaseModel):
    """Manual insert of a semantic fact (with embedding when available)."""
    content: str = Field(..., min_length=1)
    notebook_id: str = Field(..., description="Notebook context for this fact")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    tags: Optional[List[str]] = Field(default_factory=list)
    importance: float = Field(0.5, ge=0.0, le=1.0)


class EpisodicEntryResponse(BaseModel):
    id: str
    agent_id: Optional[str] = None
    notebook_id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    importance: float = 0.5
    source_message_id: Optional[str] = None
    expires_at: Optional[str] = None
    created: Optional[str] = None
    updated: Optional[str] = None


class SemanticEntryResponse(BaseModel):
    id: str
    agent_id: Optional[str] = None
    notebook_id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    importance: float = 0.5
    access_count: int = 0
    last_accessed: Optional[str] = None
    has_embedding: bool = False
    similarity: Optional[float] = None
    created: Optional[str] = None
    updated: Optional[str] = None


class ProceduralEntryResponse(BaseModel):
    id: str
    agent_id: str
    task_pattern: str
    tool_sequence: List[str] = Field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 0.0
    total_attempts: int = 0
    avg_duration_ms: Optional[int] = None
    example_inputs: List[Any] = Field(default_factory=list)
    last_used: Optional[str] = None
    has_embedding: bool = False
    similarity: Optional[float] = None
    created: Optional[str] = None
    updated: Optional[str] = None


class EpisodicListResponse(BaseModel):
    entries: List[EpisodicEntryResponse] = Field(default_factory=list)
    total: int = 0


class SemanticListResponse(BaseModel):
    entries: List[SemanticEntryResponse] = Field(default_factory=list)
    total: int = 0


class ProceduralListResponse(BaseModel):
    entries: List[ProceduralEntryResponse] = Field(default_factory=list)
    total: int = 0


class RecallBundleResponse(BaseModel):
    """Result of GET /api/memory/agents/{id}/recall — debug endpoint output."""
    short_term: Dict[str, Any] = Field(default_factory=dict)
    episodic: List[EpisodicEntryResponse] = Field(default_factory=list)
    semantic: List[SemanticEntryResponse] = Field(default_factory=list)
    procedural: List[ProceduralEntryResponse] = Field(default_factory=list)
    formatted_prompt: str = ""


class MemoryStatsResponse(BaseModel):
    """Lightweight counts per layer — populates UI badges."""
    agent_id: str
    episodic: int = 0
    semantic: int = 0
    procedural: int = 0


# ============================================================================
# Orchestrated Chat Models
# ============================================================================

class OrchestratedChatRequest(BaseModel):
    """Request model for multi-agent orchestrated chat"""
    message: str = Field(..., min_length=1, description="User message")
    stream: bool = Field(default=True, description="Stream responses via SSE")
    agent_roles: Optional[List[AgentRole]] = Field(
        None,
        description="Specific agent roles to activate (None = auto-select)"
    )
    max_iterations: int = Field(
        default=5, ge=1, le=20,
        description="Maximum orchestration iterations"
    )
    include_context: bool = Field(default=True, description="Include notebook context")
    selected_source_ids: Optional[List[str]] = Field(
        None, description="Source IDs for context"
    )
    config: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional orchestration config"
    )


class OrchestratedChatEvent(BaseModel):
    """A single event in an orchestrated chat stream"""
    event_type: str = Field(..., description="Event type: agent_start, agent_step, agent_done, chunk, error, done")
    agent_id: Optional[str] = None
    agent_role: Optional[str] = None
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None


# ============================================================================
# Agent Tool Discovery Models
# ============================================================================

class AgentToolInfo(BaseModel):
    """Tool information for agent use"""
    id: str
    name: str
    tool_type: str
    category: Optional[str] = None
    description: Optional[str] = None
    enabled: bool = True
    roles: Optional[List[str]] = Field(
        default_factory=list,
        description="Roles this tool is recommended for"
    )


class AgentToolListResponse(BaseModel):
    """Response for listing tools available to agents"""
    tools: List[AgentToolInfo] = Field(default_factory=list)
    total: int = 0


# ============================================================================
# Prompt Template Models
# ============================================================================

class PromptTemplateResponse(BaseModel):
    """Response model for a prompt template"""
    id: str
    role: str = Field(..., description="Agent role this template applies to (e.g., planner, researcher, analyst)")
    name: str = Field(..., description="Human-readable template name")
    template: str = Field(..., description="The active prompt template text")
    description: Optional[str] = None
    is_default: bool = Field(default=True, description="Whether this is the built-in default template")
    created: Optional[datetime] = None
    updated: Optional[datetime] = None

    class Config:
        from_attributes = True


class PromptTemplateUpdate(BaseModel):
    """Request model for updating or creating a prompt template"""
    template: str = Field(..., min_length=1, description="The new prompt template text")
    role: Optional[str] = Field(None, description="Agent role name (required for CREATE, optional for UPDATE)")
    name: Optional[str] = Field(None, description="Optional new name for the template")
    description: Optional[str] = Field(None, description="Optional new description")


class PromptTemplateListResponse(BaseModel):
    """Response model for listing prompt templates"""
    templates: List[PromptTemplateResponse] = Field(default_factory=list)
    total: int = 0


class AgentPromptResponse(BaseModel):
    """Response model for an agent's effective prompt"""
    agent_id: str
    role: str
    effective_prompt: str = Field(..., description="The resolved prompt text for this agent")
    source: str = Field(..., description="Where the prompt comes from: 'custom', 'template', 'default'")
    template_id: Optional[str] = Field(None, description="ID of the template used, if any")
    custom_prompt: Optional[str] = Field(None, description="Custom prompt override, if set")


class AgentPromptUpdate(BaseModel):
    """Request model for setting a custom prompt on an agent"""
    custom_prompt: Optional[str] = Field(
        None,
        description="Custom prompt override. Set to null to clear and revert to template/default."
    )


# ============================================================================
# User Query Prompt Models
# ============================================================================

class UserQueryPromptCreate(BaseModel):
    """Request to create a saved query prompt"""
    name: str = Field(..., min_length=1, max_length=255, description="Name for the saved prompt")
    query_text: str = Field(..., min_length=1, description="The query text to save")
    description: Optional[str] = Field(None, description="Optional description")
    category: Optional[str] = Field(None, max_length=100, description="Category for organization")
    team_id: Optional[str] = Field(None, description="Associate with specific team")
    prompt_role: Optional[str] = Field(None, description="Remember which system prompt was used")
    tags: Optional[List[str]] = Field(default_factory=list, description="Tags for organization")
    is_favorite: bool = Field(False, description="Mark as favorite")


class UserQueryPromptUpdate(BaseModel):
    """Request to update a saved query prompt"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    query_text: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)
    tags: Optional[List[str]] = None
    is_favorite: Optional[bool] = None


class UserQueryPromptResponse(BaseModel):
    """Response model for a saved query prompt"""
    id: str
    user_id: str
    name: str
    query_text: str
    description: Optional[str] = None
    category: Optional[str] = None
    team_id: Optional[str] = None
    prompt_role: Optional[str] = None
    tags: List[str] = []
    use_count: int = 0
    last_used: Optional[str] = None
    is_favorite: bool = False
    created: str
    updated: str


class UserQueryPromptListResponse(BaseModel):
    """Response model for listing saved query prompts"""
    prompts: List[UserQueryPromptResponse]
    total: int


# ============================================================================
# Standalone Agent Models
# ============================================================================

class StandaloneAgentCreate(BaseModel):
    """Request model for creating a standalone agent"""
    name: str = Field(..., min_length=1, max_length=255, description="Agent name")
    description: Optional[str] = Field(None, description="Agent description")
    role: str = Field(..., description="Agent role (planner, researcher, analyst, synthesizer, custom)")
    system_prompt: Optional[str] = Field(None, description="Custom system prompt")
    model_name: Optional[str] = Field(None, description="LLM model override")
    notebook_id: Optional[str] = Field(None, description="Optional linked notebook")
    tool_ids: Optional[List[str]] = Field(
        default_factory=list,
        description="Tool IDs from registry"
    )
    skill_ids: List[str] = Field(
        default_factory=list,
        description="Skill IDs from skill registry"
    )
    mcp_server_ids: Optional[List[str]] = Field(
        default_factory=list,
        description="MCP server IDs"
    )
    data_source_ids: Optional[List[str]] = Field(
        default_factory=list,
        description="Source IDs for data access"
    )
    config: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Agent-specific configuration"
    )


class StandaloneAgentUpdate(BaseModel):
    """Request model for updating a standalone agent"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    role: Optional[str] = None
    system_prompt: Optional[str] = None
    model_name: Optional[str] = None
    notebook_id: Optional[str] = None
    tool_ids: Optional[List[str]] = None
    skill_ids: Optional[List[str]] = None
    mcp_server_ids: Optional[List[str]] = None
    data_source_ids: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None  # active, inactive, archived


class StandaloneAgentResponse(BaseModel):
    """Response model for a standalone agent"""
    id: str
    name: str
    description: Optional[str] = None
    role: str
    system_prompt: Optional[str] = None
    model_name: Optional[str] = None
    notebook_id: Optional[str] = None
    tool_ids: Optional[List[str]] = None
    skill_ids: List[str] = []
    mcp_server_ids: Optional[List[str]] = None
    data_source_ids: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None
    status: str = "active"
    created: Optional[datetime] = None
    updated: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_validator("tool_ids", "skill_ids", "mcp_server_ids", "data_source_ids", "config", mode="before")
    @classmethod
    def parse_json_fields_standalone(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v) if v else None
            except (json.JSONDecodeError, TypeError):
                return None
        return v


class StandaloneAgentListResponse(BaseModel):
    """Response model for listing standalone agents"""
    agents: List[StandaloneAgentResponse] = Field(default_factory=list)
    total: int = 0


# ============================================================================
# Standalone Agent Execution Models
# ============================================================================

class StandaloneAgentExecuteRequest(BaseModel):
    """Request model for executing a standalone agent"""
    query: str = Field(..., min_length=1, description="Query or task for the agent")
    context_source_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional source IDs to use as context (overrides agent's data_source_ids)"
    )
    session_id: Optional[str] = Field(None, description="Optional chat session link")
    max_steps: Optional[int] = Field(10, ge=1, le=50, description="Maximum execution steps")
    stream: bool = Field(False, description="Whether to stream progress via SSE")


class StandaloneAgentExecutionStep(BaseModel):
    """A step in the standalone agent execution"""
    step_number: int
    action: str
    status: str
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    result: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class StandaloneAgentExecutionResponse(BaseModel):
    """Response model for standalone agent execution"""
    id: str
    agent_id: str
    query: str
    status: str  # "running", "completed", "failed", "cancelled"
    steps: List[StandaloneAgentExecutionStep] = Field(default_factory=list)
    result: Optional[str] = None
    error: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    started_at: str
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None
    created: Optional[datetime] = None

    class Config:
        from_attributes = True

    @field_validator("steps", mode="before")
    @classmethod
    def parse_steps_field(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            try:
                return json.loads(v) if v else []
            except (json.JSONDecodeError, TypeError):
                return []
        return v

    @field_validator("context", "tool_calls", mode="before")
    @classmethod
    def parse_json_fields_execution(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v) if v else None
            except (json.JSONDecodeError, TypeError):
                return None
        return v

    @field_validator("result", mode="before")
    @classmethod
    def parse_result_field(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            try:
                # Try to parse as JSON
                parsed = json.loads(v)
                # If it's a dict with 'response' key, extract it
                if isinstance(parsed, dict) and 'response' in parsed:
                    return parsed['response']
                # Otherwise return as-is
                return v
            except (json.JSONDecodeError, TypeError):
                return v
        if isinstance(v, dict):
            # If already a dict with 'response', extract it
            if 'response' in v:
                return v['response']
            # Otherwise stringify it
            return json.dumps(v)
        return str(v)


class StandaloneAgentExecutionListResponse(BaseModel):
    """Response model for listing standalone agent executions"""
    executions: List[StandaloneAgentExecutionResponse] = Field(default_factory=list)
    total: int = 0


# ============================================================================
# Bookmark Models
# ============================================================================

class EntityTypeEnum(str, Enum):
    """Entity types that can be bookmarked"""
    SOURCE = "source"
    NOTE = "note"
    NOTEBOOK = "notebook"


class BookmarkCreate(BaseModel):
    """Request to create/toggle a bookmark"""
    entity_type: str = Field(..., description="Entity type: source, note, or notebook")
    entity_id: str = Field(..., description="ID of the entity to bookmark")
    custom_note: Optional[str] = Field(None, description="User's optional note about this bookmark")
    reason: Optional[str] = Field(None, description="Why this was bookmarked")


class BookmarkUpdate(BaseModel):
    """Request to update bookmark metadata"""
    custom_note: Optional[str] = None
    reason: Optional[str] = None


class BookmarkResponse(BaseModel):
    """Response model for a single bookmark"""
    id: str
    user_id: str
    entity_type: str
    entity_id: str
    custom_note: Optional[str] = None
    reason: Optional[str] = None
    bookmarked_at: str
    created: str
    updated: str


class EnrichedBookmarkResponse(BookmarkResponse):
    """Response model for a bookmark enriched with entity details"""
    entity_title: Optional[str] = None
    entity_description: Optional[str] = None
    entity_updated: Optional[str] = None

    # Type-specific fields
    source_type: Optional[str] = None
    chunk_count: Optional[int] = None
    source_count: Optional[int] = None  # For notebooks
    note_count: Optional[int] = None    # For notebooks


class BookmarkListResponse(BaseModel):
    """Response model for listing bookmarks"""
    bookmarks: List[EnrichedBookmarkResponse] = Field(default_factory=list)
    total: int = 0


class BookmarkToggleResponse(BaseModel):
    """Response model for toggle operation"""
    is_bookmarked: bool
    bookmark: Optional[BookmarkResponse] = None
    message: str


class BookmarkBulkCheckRequest(BaseModel):
    """Request to check bookmark status for multiple entities"""
    entity_type: str = Field(..., description="Entity type: source, note, or notebook")
    entity_ids: List[str] = Field(..., description="List of entity IDs to check")


class BookmarkBulkCheckResponse(BaseModel):
    """Response model for bulk check"""
    bookmarks: Dict[str, bool] = Field(default_factory=dict)


class BookmarkSearchRequest(BaseModel):
    """Request to search bookmarks using natural language"""
    query: str = Field(..., min_length=1, description="Natural language search query")
    limit: int = Field(10, ge=1, le=100, description="Maximum results to return")
    threshold: float = Field(0.7, ge=0.0, le=1.0, description="Minimum similarity threshold")


class BookmarkSearchResult(EnrichedBookmarkResponse):
    """Search result with similarity score"""
    similarity: float = Field(..., description="Similarity score (0.0-1.0)")
    content: str = Field(..., description="The searchable context that was matched")


class BookmarkSearchResponse(BaseModel):
    """Response model for bookmark search"""
    results: List[BookmarkSearchResult] = Field(default_factory=list)
    total: int = 0
    query: str


class BookmarkEmbeddingResponse(BaseModel):
    """Response for embedding generation"""
    success: bool
    bookmark_id: Optional[str] = None
    context_length: Optional[int] = None
    message: str
    error: Optional[str] = None


class BookmarkRegenerateResponse(BaseModel):
    """Response for bulk regeneration of embeddings"""
    total: int
    success: int
    failed: int
    errors: List[Dict[str, Any]] = Field(default_factory=list)


# ============================================================================
# Graph Visualization Models
# ============================================================================

class EdgeType(str, Enum):
    """Edge types for graph visualization"""
    SEMANTIC = "semantic"
    NOTEBOOK = "notebook"
    TOPIC = "topic"
    NOTE_LINK = "note_link"
    HANA_SCHEMA = "hana_schema"
    API_RELATION = "api_relation"
    CLASSIFIED_AS = "classified_as"
    PARENT_CHILD = "parent_child"
    RELATED = "related"


class GraphNodeData(BaseModel):
    """Data payload for graph nodes"""
    title: str
    description: Optional[str] = None
    source_type: SourceType
    created: str
    updated: str
    chunk_count: int = 0
    topics: List[str] = Field(default_factory=list)
    connection_count: int = 0
    notebooks: List[Dict[str, str]] = Field(default_factory=list)

    # Type-specific metadata
    hana_metadata: Optional[Dict[str, Any]] = None
    api_metadata: Optional[Dict[str, Any]] = None
    youtube_metadata: Optional[Dict[str, Any]] = None
    file_metadata: Optional[Dict[str, Any]] = None

    # Classification-specific fields (for classification nodes)
    classification_type: Optional[str] = None
    level: Optional[int] = None
    sourceCount: Optional[int] = None
    childCount: Optional[int] = None
    pendingCount: Optional[int] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    name: Optional[str] = None


class GraphNode(BaseModel):
    """Graph node representing a source"""
    id: str
    type: str = "source"  # React Flow node type (always "source")
    label: str
    data: GraphNodeData
    position: Optional[Dict[str, float]] = None


class GraphEdgeData(BaseModel):
    """Data payload for graph edges"""
    relationship_type: EdgeType  # Actual edge type (semantic, notebook, etc.)
    strength: float = Field(..., ge=0.0, le=1.0, description="Edge strength (0.0-1.0)")
    api_variant: Optional[str] = None  # For API edges: solid, dashed, dotted
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """Graph edge representing a relationship"""
    id: str
    source: str
    target: str
    type: str = "relationship"  # React Flow edge type (always "relationship")
    label: Optional[str] = None
    data: GraphEdgeData


class GraphMetadata(BaseModel):
    """Metadata about the graph"""
    total_sources: int
    date_range: Optional[Dict[str, str]] = None  # { min, max }
    source_type_counts: Dict[str, int] = Field(default_factory=dict)
    edge_type_counts: Dict[str, int] = Field(default_factory=dict)


class GraphResponse(BaseModel):
    """Response for graph data queries"""
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    metadata: GraphMetadata


class GraphFilters(BaseModel):
    """Filters for graph queries"""
    source_types: Optional[List[SourceType]] = None
    notebook_ids: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    semantic_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    min_topic_overlap: int = Field(default=2, ge=1)
    show_isolated: bool = True
    edge_types: List[EdgeType] = Field(default_factory=lambda: [
        EdgeType.SEMANTIC, EdgeType.NOTEBOOK, EdgeType.TOPIC,
        EdgeType.NOTE_LINK, EdgeType.HANA_SCHEMA, EdgeType.API_RELATION
    ])


class LayoutSaveRequest(BaseModel):
    """Request to save a custom layout"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    scope: Literal["global", "notebook"]
    scope_id: Optional[str] = None
    layout_data: Dict[str, Dict[str, float]]  # { node_id: { x, y } }


class LayoutResponse(BaseModel):
    """Response for layout operations"""
    id: str
    name: str
    description: Optional[str] = None
    scope: str
    scope_id: Optional[str] = None
    layout_data: Optional[Dict[str, Dict[str, float]]] = None
    created: str
    updated: str


class LayoutListResponse(BaseModel):
    """Response for listing layouts"""
    layouts: List[LayoutResponse]
    total: int


# ============================================================================
# Graph Visualization Models
# ============================================================================

class EdgeType(str, Enum):
    """Edge types for graph visualization"""
    SEMANTIC = "semantic"
    NOTEBOOK = "notebook"
    TOPIC = "topic"
    NOTE_LINK = "note_link"
    HANA_SCHEMA = "hana_schema"
    API_RELATION = "api_relation"
    CLASSIFIED_AS = "classified_as"
    PARENT_CHILD = "parent_child"
    RELATED = "related"




class GraphMetadata(BaseModel):
    """Metadata about the graph"""
    total_sources: int
    date_range: Optional[Dict[str, str]] = None  # { min, max }
    source_type_counts: Dict[str, int] = Field(default_factory=dict)
    edge_type_counts: Dict[str, int] = Field(default_factory=dict)


class GraphResponse(BaseModel):
    """Response for graph data queries"""
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    metadata: GraphMetadata


class GraphFilters(BaseModel):
    """Filters for graph queries"""
    source_types: Optional[List[SourceType]] = None
    notebook_ids: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    semantic_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    min_topic_overlap: int = Field(default=2, ge=1)
    show_isolated: bool = True
    edge_types: List[EdgeType] = Field(default_factory=lambda: [
        EdgeType.SEMANTIC, EdgeType.NOTEBOOK, EdgeType.TOPIC,
        EdgeType.NOTE_LINK, EdgeType.HANA_SCHEMA, EdgeType.API_RELATION
    ])


class LayoutSaveRequest(BaseModel):
    """Request to save a custom layout"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    scope: Literal["global", "notebook"]
    scope_id: Optional[str] = None
    layout_data: Dict[str, Dict[str, float]]  # { node_id: { x, y } }


class LayoutResponse(BaseModel):
    """Response for layout operations"""
    id: str
    name: str
    description: Optional[str] = None
    scope: str
    scope_id: Optional[str] = None
    layout_data: Optional[Dict[str, Dict[str, float]]] = None
    created: str
    updated: str


class LayoutListResponse(BaseModel):
    """Response for listing layouts"""
    layouts: List[LayoutResponse]
    total: int



# ============================================================================
# Agent Skills Models
# ============================================================================

class SkillType(str, Enum):
    """Types of agent skills"""
    TOOL_CHAIN = "tool_chain"
    PROMPT_TEMPLATE = "prompt_template"
    WORKFLOW = "workflow"
    CUSTOM = "custom"


class SkillCategory(str, Enum):
    """Categories for organizing skills"""
    DATA_ANALYSIS = "data_analysis"
    WEB_RESEARCH = "web_research"
    CODE_GENERATION = "code_generation"
    COMMUNICATION = "communication"
    PLANNING = "planning"
    CUSTOM = "custom"


class BindingType(str, Enum):
    """Types of skill bindings"""
    AGENT = "agent"
    STANDALONE_AGENT = "standalone_agent"
    ROLE = "role"
    TEAM = "team"


class AgentSkillCreate(BaseModel):
    """Request model for creating a skill"""
    name: str = Field(..., min_length=1, max_length=255)
    category: SkillCategory
    description: Optional[str] = None
    skill_type: SkillType
    definition: Dict[str, Any] = Field(..., description="Skill implementation as JSON")
    input_schema: Optional[Dict[str, Any]] = Field(None, description="JSON schema for input parameters")
    output_schema: Optional[Dict[str, Any]] = Field(None, description="JSON schema for output format")
    roles: Optional[List[str]] = Field(default_factory=list, description="Recommended roles")
    tags: Optional[List[str]] = Field(default_factory=list, description="Searchable tags")
    enabled: bool = True
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Version, author, etc.")


class AgentSkillUpdate(BaseModel):
    """Request model for updating a skill"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[SkillCategory] = None
    description: Optional[str] = None
    skill_type: Optional[SkillType] = None
    definition: Optional[Dict[str, Any]] = None
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    roles: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    enabled: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


class AgentSkillResponse(BaseModel):
    """Response model for a skill"""
    id: str
    name: str
    category: str
    description: Optional[str] = None
    skill_type: str
    definition: Dict[str, Any]
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    roles: Optional[List[str]] = Field(default_factory=list)
    tags: Optional[List[str]] = Field(default_factory=list)
    enabled: bool
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    created: str
    updated: str


class AgentSkillListResponse(BaseModel):
    """Response model for listing skills"""
    skills: List[AgentSkillResponse] = Field(default_factory=list)
    total: int = 0


class SkillBindingCreate(BaseModel):
    """Request model for creating a skill binding"""
    skill_id: str
    binding_type: BindingType
    agent_id: Optional[str] = None
    standalone_agent_id: Optional[str] = None
    role: Optional[str] = None
    team_id: Optional[str] = None
    priority: int = Field(default=0, description="Higher priority skills are suggested first")
    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Config overrides")
    enabled: bool = True


class SkillBindingUpdate(BaseModel):
    """Request model for updating a skill binding"""
    priority: Optional[int] = None
    config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


class SkillBindingResponse(BaseModel):
    """Response model for a skill binding"""
    id: str
    skill_id: str
    skill_name: Optional[str] = None  # Joined from agent_skills
    binding_type: str
    agent_id: Optional[str] = None
    standalone_agent_id: Optional[str] = None
    role: Optional[str] = None
    team_id: Optional[str] = None
    priority: int
    config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    enabled: bool
    created: str
    created_by: Optional[str] = None


class SkillBindingListResponse(BaseModel):
    """Response model for listing skill bindings"""
    bindings: List[SkillBindingResponse] = Field(default_factory=list)
    total: int = 0


class SkillExecuteRequest(BaseModel):
    """Request model for executing a skill"""
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Input parameters for skill execution")
    config_override: Optional[Dict[str, Any]] = Field(None, description="Override skill configuration for this execution")


class SkillExecutionResponse(BaseModel):
    """Response model for a skill execution"""
    id: str
    skill_id: str
    skill_name: Optional[str] = None  # Joined from agent_skills
    execution_id: str
    agent_id: Optional[str] = None
    team_id: Optional[str] = None
    input_data: Optional[Dict[str, Any]] = Field(default_factory=dict)
    output_data: Optional[Dict[str, Any]] = Field(default_factory=dict)
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None
    trace_id: Optional[str] = None
    steps: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    started_at: str
    ended_at: Optional[str] = None
    created: str


class SkillExecutionListResponse(BaseModel):
    """Response model for listing skill executions"""
    executions: List[SkillExecutionResponse] = Field(default_factory=list)
    total: int = 0


# ============================================================================
# System Prompt Template Models
# ============================================================================

class SystemPromptVariable(BaseModel):
    """Variable metadata for system prompt templates"""
    name: str
    type: str  # string, integer, boolean, etc.
    required: bool = True
    description: Optional[str] = None
    example: Optional[str] = None


class SystemPromptMetadata(BaseModel):
    """Metadata for system prompt templates"""
    output_format: str = "text"  # text, json, markdown
    composition: str = "base"  # base, addon
    conditions: Optional[List[str]] = None  # When to include (e.g., ["tools_available"])
    max_length: Optional[int] = None
    output_schema: Optional[Dict[str, Any]] = None
    note: Optional[str] = None


class SystemPromptTemplateResponse(BaseModel):
    """Response model for system prompt template"""
    id: str
    category: str  # chat, research, orchestration, microsite
    template_key: str
    name: str
    description: Optional[str] = None
    template: str  # The prompt_text field (renamed for consistency with agent_prompts)
    variables: Optional[List[SystemPromptVariable]] = None
    metadata: Optional[SystemPromptMetadata] = None
    is_default: bool = True
    is_active: bool = True
    created: Optional[str] = None
    updated: Optional[str] = None

    class Config:
        from_attributes = True

    @field_validator("variables", mode="before")
    @classmethod
    def parse_variables(cls, v):
        if isinstance(v, str):
            try:
                data = json.loads(v) if v else {"variables": []}
                # Handle both {variables: [...]} and [...] formats
                if isinstance(data, dict) and "variables" in data:
                    return [SystemPromptVariable(**var) for var in data["variables"]]
                elif isinstance(data, list):
                    return [SystemPromptVariable(**var) for var in data]
                return []
            except (json.JSONDecodeError, TypeError, ValueError):
                return []
        return v

    @field_validator("metadata", mode="before")
    @classmethod
    def parse_metadata(cls, v):
        if isinstance(v, str):
            try:
                data = json.loads(v) if v else {}
                return SystemPromptMetadata(**data)
            except (json.JSONDecodeError, TypeError, ValueError):
                return SystemPromptMetadata()
        return v


class SystemPromptTemplateUpdate(BaseModel):
    """Request model for updating system prompt template"""
    template: str = Field(..., min_length=1, description="The prompt template text")
    name: Optional[str] = Field(None, description="Optional name update")
    description: Optional[str] = Field(None, description="Optional description update")


class SystemPromptTemplateListResponse(BaseModel):
    """Response model for listing system prompt templates"""
    templates: List[SystemPromptTemplateResponse] = Field(default_factory=list)
    total: int = 0

# ============================================================================
# Guided Workspace Creation Models
# ============================================================================

class GoalAnalysisRequest(BaseModel):
    """Request to analyze a workspace goal"""
    goal: str = Field(..., min_length=20, max_length=5000, description="User's workspace goal")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class GoalAnalysisResponse(BaseModel):
    """Response from goal analysis"""
    session_id: str = Field(..., description="Unique session ID for this guided creation")
    analysis: Dict[str, Any] = Field(..., description="Parsed goal analysis (intent, domain, keywords, etc.)")
    needs_clarification: bool = Field(..., description="Whether clarification questions are needed")
    questions: Optional[List[Dict[str, Any]]] = Field(None, description="Clarification questions if needed")


class ClarificationRequest(BaseModel):
    """Request to submit clarification answers"""
    session_id: str = Field(..., description="Session ID from goal analysis")
    goal: str = Field(..., description="Original goal")
    answers: Dict[str, Any] = Field(..., description="User's answers to clarification questions")


class ClarificationResponse(BaseModel):
    """Response from clarification"""
    updated_analysis: Dict[str, Any] = Field(..., description="Refined analysis with answers incorporated")
    ready_for_discovery: bool = Field(..., description="Whether ready to discover resources")


class ResourceDiscoveryRequest(BaseModel):
    """Request to discover relevant resources"""
    session_id: str = Field(..., description="Session ID")
    goal: str = Field(..., description="User's goal")
    analysis: Dict[str, Any] = Field(..., description="Goal analysis")


class DiscoveredResourcesResponse(BaseModel):
    """Response with discovered resources"""
    data_sources: List[Dict[str, Any]] = Field(default_factory=list, description="Relevant data sources")
    tools: List[Dict[str, Any]] = Field(default_factory=list, description="Relevant tools")
    agents: List[Dict[str, Any]] = Field(default_factory=list, description="Relevant agents")
    teams: List[Dict[str, Any]] = Field(default_factory=list, description="Relevant teams")


class PlanGenerationRequest(BaseModel):
    """Request to generate task plan"""
    session_id: str = Field(..., description="Session ID")
    goal: str = Field(..., description="User's goal")
    selected_resources: Dict[str, List[str]] = Field(..., description="Selected resource IDs by type")


class WorkspacePlanResponse(BaseModel):
    """Response with generated plan"""
    phases: List[Dict[str, Any]] = Field(..., description="Phased tasks")
    total_duration: int = Field(..., description="Total estimated duration in minutes")
    collaboration_graph: Dict[str, Any] = Field(..., description="Agent collaboration structure")


class CreateWorkspaceRequest(BaseModel):
    """Request to create workspace from plan"""
    session_id: str = Field(..., description="Session ID")
    name: str = Field(..., min_length=1, max_length=255, description="Workspace name")
    goal: str = Field(..., description="User's goal")
    selected_resources: Dict[str, List[str]] = Field(..., description="Selected resource IDs")
    plan: Dict[str, Any] = Field(..., description="Generated plan")
    auto_start: bool = Field(default=False, description="Whether to auto-start execution")


class WorkspaceCreatedResponse(BaseModel):
    """Response after workspace creation"""
    workspace_id: str = Field(..., description="Created workspace ID")
    status: str = Field(..., description="Creation status")
    initialization_tasks: List[str] = Field(default_factory=list, description="Initialization tasks completed")
    next_steps: List[str] = Field(default_factory=list, description="Recommended next steps")


class GuidedWorkspaceSessionResponse(BaseModel):
    """Response with session details"""
    id: str
    user_id: str
    goal: str
    analysis: Optional[Dict[str, Any]] = None
    clarifications: Optional[Dict[str, Any]] = None
    selected_resources: Optional[Dict[str, Any]] = None
    generated_plan: Optional[Dict[str, Any]] = None
    status: str
    created: datetime
    updated: datetime
    expires_at: Optional[datetime] = None


# ============================================================================
# RBAC Models (User, Role, Permission, Resource Sharing)
# ============================================================================

class UserCreate(BaseModel):
    """Model for creating a new user"""
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    email: Optional[str] = Field(None, pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$', description="Email address")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")
    full_name: Optional[str] = Field(None, max_length=255, description="Full name")
    avatar_url: Optional[str] = None
    status: Optional[str] = "active"
    is_superadmin: bool = False


class UserUpdate(BaseModel):
    """Model for updating a user"""
    email: Optional[str] = Field(None, pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    status: Optional[str] = None  # admin only


class UserPasswordChange(BaseModel):
    """Model for changing user password"""
    old_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")


class RoleInfo(BaseModel):
    """Basic role information"""
    id: str
    name: str
    display_name: str


class UserResponse(BaseModel):
    """Response model for user data"""
    id: str
    username: str
    email: Optional[str]
    full_name: Optional[str]
    avatar_url: Optional[str]
    status: str
    is_superadmin: bool
    last_login: Optional[datetime]
    created: datetime
    updated: datetime
    roles: List[RoleInfo] = Field(default_factory=list)


class RoleCreate(BaseModel):
    """Model for creating a new role"""
    name: str = Field(..., min_length=2, max_length=50, pattern=r'^[a-z_]+$', description="Unique role identifier (lowercase, underscores)")
    display_name: str = Field(..., min_length=2, max_length=100, description="Human-readable name")
    description: Optional[str] = None


class RoleUpdate(BaseModel):
    """Model for updating a role"""
    display_name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None


class RolePermissionCreate(BaseModel):
    """Model for creating a role permission"""
    resource_type: str = Field(..., description="Resource type (workspace, agent, tool, etc.)")
    action: str = Field(..., description="Action (create, read, update, delete, execute, share)")
    scope: str = Field(default="own", description="Scope (own, team, all)")
    conditions: Optional[dict] = None


class RolePermissionUpdate(BaseModel):
    """Model for updating a role permission"""
    scope: Optional[str] = None
    conditions: Optional[dict] = None


class RolePermissionResponse(BaseModel):
    """Response model for role permission"""
    id: str
    role_id: str
    resource_type: str
    action: str
    scope: str
    conditions: Optional[dict]
    created: datetime
    updated: datetime


class RoleResponse(BaseModel):
    """Response model for role data"""
    id: str
    name: str
    display_name: str
    description: Optional[str]
    is_system_role: bool
    created_by: Optional[str]
    created: datetime
    updated: datetime
    permissions: List[RolePermissionResponse] = Field(default_factory=list)


class ResourceShareCreate(BaseModel):
    """Model for creating a resource share"""
    resource_type: str = Field(..., description="Resource type to share")
    resource_id: str = Field(..., description="Resource ID to share")
    shared_with_user: Optional[str] = Field(None, description="User ID to share with")
    shared_with_role: Optional[str] = Field(None, description="Role ID to share with")
    permission_level: str = Field(default="read", description="Permission level (read, write, admin)")
    expires_at: Optional[datetime] = None


class ResourceShareResponse(BaseModel):
    """Response model for resource share"""
    id: str
    resource_type: str
    resource_id: str
    shared_by: str
    shared_with_user: Optional[str]
    shared_with_role: Optional[str]
    permission_level: str
    expires_at: Optional[datetime]
    created: datetime
    updated: datetime


# ============================================================================
# Agent Evaluation Models
# ============================================================================

class EvaluationDatasetCreate(BaseModel):
    """Request model for creating an evaluation dataset"""
    name: str = Field(..., min_length=1, max_length=255, description="Dataset name")
    description: Optional[str] = Field(None, description="Dataset description")
    agent_id: Optional[str] = Field(None, description="Optional linked agent")
    workflow_id: Optional[str] = Field(None, description="Optional linked workflow")
    target_type: str = Field(default="agent", description="Eval target: 'agent' or 'workflow'")
    criteria: Optional[List[str]] = Field(
        default=["accuracy", "relevance", "completeness"],
        description="Evaluation criteria"
    )
    scoring_method: str = Field(
        default="llm_judge",
        description="Scoring method: llm_judge, exact_match, semantic_similarity"
    )


class ExpectedToolCall(BaseModel):
    """Assertion about a tool the agent should invoke during a test case."""
    tool_name: str = Field(..., description="Name of the tool the agent must call")
    args_match: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional subset of args that must match (recursive subset)"
    )
    required: bool = Field(
        default=True,
        description="If False, the call is observed but absence is not a failure"
    )


class EvaluationTestCaseUpload(BaseModel):
    """Model for uploading test cases"""
    dataset_id: str = Field(..., description="Dataset ID to add test cases to")
    test_cases: List[Dict[str, Any]] = Field(..., description="Test cases to upload")


class EvaluationDatasetResponse(BaseModel):
    """Response model for evaluation dataset"""
    id: str
    name: str
    description: Optional[str]
    agent_id: Optional[str]
    workflow_id: Optional[str] = None
    target_type: str = "agent"
    test_case_count: int
    file_name: Optional[str]
    file_format: Optional[str]
    criteria: List[str]
    scoring_method: str
    created: str
    updated: str
    created_by: Optional[str]


class EvaluationRunCreate(BaseModel):
    """Request model for creating an evaluation run"""
    dataset_id: str = Field(..., description="Dataset to evaluate against")
    agent_id: Optional[str] = Field(None, description="Agent to evaluate (required for target_type='agent')")
    workflow_id: Optional[str] = Field(None, description="Workflow to evaluate (required for target_type='workflow')")
    target_type: str = Field(default="agent", description="Eval target: 'agent' or 'workflow'")
    run_name: Optional[str] = Field(None, description="Optional run name")
    model_override: Optional[str] = Field(None, description="Override agent's model")
    config_override: Optional[Dict[str, Any]] = Field(None, description="Override agent config")


class EvaluationRunResponse(BaseModel):
    """Response model for evaluation run"""
    id: str
    dataset_id: str
    agent_id: Optional[str] = None
    workflow_id: Optional[str] = None
    target_type: str = "agent"
    dataset_name: Optional[str]
    agent_name: Optional[str]
    run_name: Optional[str]
    model_override: Optional[str]
    status: str  # pending, running, completed, failed
    progress: int  # 0-100
    total_cases: int
    passed_cases: int
    failed_cases: int
    avg_score: Optional[float]
    avg_latency_ms: Optional[float]
    started_at: Optional[str]
    completed_at: Optional[str]
    error_message: Optional[str]
    created: str
    created_by: Optional[str]


class EvaluationResultResponse(BaseModel):
    """Response model for individual evaluation result"""
    id: str
    run_id: str
    test_case_id: str
    input_prompt: str
    expected_output: Optional[str]
    expected_tool_calls: Optional[List[Dict[str, Any]]] = None
    agent_output: str
    execution_time_ms: float
    passed: bool
    overall_score: Optional[float]
    criteria_scores: Optional[Dict[str, float]]
    similarity_score: Optional[float]
    exact_match: Optional[bool]
    feedback: Optional[str]
    judge_reasoning: Optional[str]
    actual_tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_calls_passed: Optional[bool] = None
    error_occurred: bool
    error_message: Optional[str]
    category: Optional[str]
    tags: Optional[List[str]]
    created: str


class EvaluationRunListResponse(BaseModel):
    """Response model for list of evaluation runs"""
    runs: List[EvaluationRunResponse]
    total: int = 0
