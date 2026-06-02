"""
Domain models for Visual Workflow Graph System.

Workflows are visual graphs with nodes (LLM, Tool, Conditional) and edges
that define execution flow. They can be scheduled via cron, events, or dependencies.
"""

import json
from datetime import datetime
from typing import List, Optional, Dict, Any, Literal, ClassVar
from enum import Enum
from pydantic import BaseModel, Field

from .base import ObjectModel


# ============================================================================
# Enums
# ============================================================================

class NodeType(str, Enum):
    """Types of workflow nodes."""
    LLM = "llm"
    TOOL = "tool"
    CONDITIONAL = "conditional"
    AGENT = "agent"
    INPUT = "input"
    OUTPUT = "output"
    NOTEBOOK_GENERATOR = "notebook_generator"
    MICROSITE_GENERATOR = "microsite_generator"
    PRESENTATION_GENERATOR = "presentation_generator"
    HUMAN_APPROVAL = "human_approval"
    WORKSPACE = "workspace"
    TEMPLATE = "template"
    DELAY = "delay"
    WEBHOOK = "webhook"
    EMAIL = "email"             # Send email via configured SMTP
    SNAPSHOT = "snapshot"       # Store data snapshot
    COMPARE = "compare"         # Compare two snapshots
    HANA_TABLE = "hana_table"   # HANA table data source
    API = "api"                 # REST API endpoint with snapshots
    FOREACH = "foreach"         # Iterate over a list, run a body node per item
    JQ = "jq"                   # Process / transform JSON with a jq expression
    NOTIFY = "notify"           # Fire-and-forget user notification (inbox + toast)


class ExecutionStatus(str, Enum):
    """Status of workflow execution."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduleType(str, Enum):
    """Types of workflow schedules."""
    CRON = "cron"
    EVENT = "event"
    DEPENDENCY = "dependency"
    MANUAL = "manual"


# ============================================================================
# Graph Structure Models
# ============================================================================

class Position(BaseModel):
    """Node position in visual canvas."""
    x: float
    y: float


class InputFieldDefinition(BaseModel):
    """Definition for a single input field in input nodes."""
    name: str = Field(description="Field name (e.g., 'query', 'user_id')")
    type: Literal["string", "number", "boolean", "array", "object", "dropdown"] = Field(default="string")
    required: bool = Field(default=False)
    default_value: Optional[Any] = None
    description: Optional[str] = Field(default=None, description="Help text for users")
    validation: Optional[Dict[str, Any]] = Field(
        default=None,
        description="JSON schema validation rules (e.g., {'minLength': 5})"
    )
    # For type=='dropdown': either a list of strings (simple) or a list of {label, value} pairs.
    # When the user selects an option, only `value` (or the bare string) flows downstream.
    options: Optional[List[Any]] = Field(
        default=None,
        description="Dropdown choices: list of strings, or list of {label, value} objects"
    )


class NodeConfig(BaseModel):
    """
    Configuration for workflow nodes.

    Different node types use different fields:
    - LLM nodes: model_name, system_prompt, temperature
    - Tool nodes: tool_name, tool_args
    - Conditional nodes: condition_type, field_path, comparison_value, true_edge_id, false_edge_id
    - Agent nodes: agent_type, agent_id, agent_name
    - Input nodes: input_fields, input_schema_json
    """
    # LLM node config
    model_name: Optional[str] = None
    system_prompt: Optional[str] = None
    temperature: Optional[float] = 0.3
    max_tokens: Optional[int] = 4096

    # Tool node config
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    enable_snapshots: Optional[bool] = False  # Enable automatic snapshots for tool nodes

    # Conditional node config
    condition_type: Optional[Literal["equals", "contains", "greater_than", "less_than"]] = None
    field_path: Optional[str] = None  # JSONPath to field in data
    comparison_value: Optional[Any] = None
    true_edge_id: Optional[str] = None  # Edge to follow if condition is true
    false_edge_id: Optional[str] = None  # Edge to follow if condition is false

    # Agent node config
    agent_type: Optional[Literal["standalone", "team"]] = None
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    prompt: Optional[str] = Field(
        default=None,
        description="Prompt template for agent execution. Supports {{variable}} substitution from input fields."
    )

    # Input node config
    input_fields: Optional[List[InputFieldDefinition]] = Field(
        default=None,
        description="Field definitions for input nodes"
    )
    input_schema_json: Optional[str] = Field(
        default=None,
        description="Alternative: JSON Schema string for advanced users"
    )

    # Notebook Generator node config
    notebook_name: Optional[str] = None
    notebook_description: Optional[str] = None
    folder_id: Optional[str] = None
    tags: Optional[List[str]] = None
    source_mode: Optional[Literal["create_from_content", "use_existing", "both"]] = None
    content_source_node_id: Optional[str] = None
    content_extraction_mode: Optional[Literal["full_output", "smart_parse", "json_path"]] = None
    content_extraction_path: Optional[str] = None  # JSONPath expression for json_path mode
    source_title_template: Optional[str] = None
    source_type: Optional[Literal["text", "file", "url"]] = None
    existing_source_ids: Optional[List[str]] = None
    output_format: Optional[Literal["id_only", "full_object", "summary"]] = None

    # Microsite Generator node config
    microsite_title: Optional[str] = None
    microsite_description: Optional[str] = None
    notebook_id_template: Optional[str] = None
    template_id: Optional[str] = None
    microsite_source_mode: Optional[Literal["from_notebook", "explicit_ids", "from_node"]] = None
    microsite_source_ids: Optional[List[str]] = None
    source_node_id: Optional[str] = None
    user_prompt: Optional[str] = None
    auto_publish: Optional[bool] = None
    microsite_output_format: Optional[Literal["preview_url", "full_response", "summary"]] = None
    auto_create_notebook: Optional[bool] = None
    auto_notebook_description: Optional[str] = None
    fail_on_moderation_block: Optional[bool] = None

    # Human Approval node config
    approval_type: Optional[Literal["manual", "auto_timeout"]] = None
    approval_prompt: Optional[str] = None
    approval_options: Optional[List[str]] = Field(default_factory=lambda: ["approve", "reject"])
    timeout_seconds: Optional[int] = None
    timeout_action: Optional[Literal["approve", "reject", "fail"]] = "fail"
    required_approvers: Optional[List[str]] = None  # User IDs

    # Workspace node config
    workspace_template_id: Optional[str] = None
    workspace_parameters: Optional[Dict[str, Any]] = None
    wait_for_completion: Optional[bool] = True

    # Template node config (workflow template)
    template_id: Optional[str] = None
    template_parameters: Optional[Dict[str, Any]] = None

    # Delay node config
    delay_seconds: Optional[int] = None
    delay_expression: Optional[str] = None  # JSONPath to extract delay from data

    # Webhook node config
    webhook_url: Optional[str] = None
    webhook_method: Optional[Literal["GET", "POST", "PUT"]] = "POST"
    webhook_headers: Optional[Dict[str, str]] = None
    webhook_body_template: Optional[str] = None
    webhook_auth_type: Optional[Literal["none", "bearer", "basic"]] = None
    webhook_auth_token: Optional[str] = None

    # Email node config (uses SMTP settings configured in Settings → SMTP)
    email_to: Optional[List[str]] = None        # Recipient emails; supports {{var}} per entry
    email_cc: Optional[List[str]] = None
    email_bcc: Optional[List[str]] = None
    email_subject: Optional[str] = None
    email_body: Optional[str] = None            # HTML body produced by the rich-text editor
    email_is_html: Optional[bool] = True

    # Notify node config — fire-and-forget user notification (inbox + toast).
    # Recipient defaults to the workflow's running user; supports {{var}} substitution
    # in title/message/action_url. Workflow continues immediately — does NOT pause.
    notify_title: Optional[str] = None
    notify_message: Optional[str] = None
    notify_priority: Optional[Literal["low", "normal", "high", "urgent"]] = "normal"
    notify_action_url: Optional[str] = None
    notify_action_label: Optional[str] = None
    notify_user_ids: Optional[List[str]] = None  # Override recipients; defaults to workflow user

    # Snapshot node config
    snapshot_mode: Optional[Literal["store", "compare"]] = "store"
    snapshot_label: Optional[str] = None  # 'yesterday', 'today', 'baseline'
    source_node_id: Optional[str] = None  # Node to snapshot
    retention_days: Optional[int] = 30    # Auto-cleanup old snapshots

    # Compare mode config
    compare_snapshot_1: Optional[str] = None  # e.g., 'yesterday'
    compare_snapshot_2: Optional[str] = None  # e.g., 'today'
    comparison_strategy: Optional[Literal["fast", "medium", "full"]] = "fast"
    change_threshold: Optional[float] = 0.0  # Minimum % change to trigger
    watch_columns: Optional[List[Dict[str, Any]]] = None  # Columns to watch: [{column: str, watch_value: Optional[str]}]

    # HANA Table node config
    hana_connection_id: Optional[str] = None  # Reference to hana_connections table
    hana_table_name: Optional[str] = None  # Fully qualified table name (SCHEMA.TABLE)
    hana_query: Optional[str] = None  # Optional custom SQL query (SELECT only)
    hana_where_clause: Optional[str] = None  # WHERE clause filter
    hana_limit: Optional[int] = 10000  # Row limit
    hana_columns: Optional[List[str]] = None  # Specific columns to select
    conditions: Optional[List[Dict[str, Any]]] = None  # Filter conditions: [{column: str, operator: str, value: str}]
    hana_fail_on_empty: Optional[bool] = False  # Raise if query returns 0 rows

    # API node config
    api_endpoint: Optional[str] = None  # Full URL
    api_method: Optional[Literal["GET", "POST", "PUT", "DELETE"]] = "GET"
    api_headers: Optional[Dict[str, str]] = None  # HTTP headers
    api_query_params: Optional[Dict[str, Any]] = None  # URL query parameters
    api_request_body: Optional[Dict[str, Any]] = None  # Request body (JSON)
    api_auth_type: Optional[Literal["none", "bearer", "api_key", "basic"]] = "none"
    api_auth_token: Optional[str] = None  # Auth token/key
    api_response_data_path: Optional[str] = None  # JSONPath to extract array (e.g., "$.data")
    api_timeout: Optional[int] = 30  # Request timeout in seconds
    api_connection_id: Optional[str] = None  # Reference to api_connections table (optional)
    api_path: Optional[str] = None  # Path to append to connection endpoint (e.g., "/users", "/todos")
    api_fail_on_empty: Optional[bool] = False  # Raise if extracted data is empty
    api_empty_check_path: Optional[str] = None  # JSONPath to check for emptiness; falls back to api_response_data_path
    api_expected_status_codes: Optional[List[int]] = None  # If set, only these status codes are accepted

    # API node batching — split a single query param's list value into N parallel
    # requests to avoid HTTP 414 (URI too long) on large ID lists. Only activates
    # when api_batch_param is set; the rest are tunables.
    api_batch_param: Optional[str] = None  # Query param name to split (e.g., "filter[customId]")
    api_batch_size: Optional[int] = 50  # Items per batch
    api_batch_separator: Optional[str] = ","  # Separator joining items in each batch's value
    api_batch_concurrency: Optional[int] = 4  # Max in-flight requests during fan-out

    # ForEach node config
    foreach_source: Optional[str] = None  # Template like "{{hana-NODE-ID.rows}}" pointing to a list
    foreach_body_node_id: Optional[str] = None  # ID of the node to execute once per item
    foreach_on_error: Optional[Literal["continue", "fail"]] = "continue"
    foreach_max_items: Optional[int] = 1000  # Cap on rows iterated

    # JQ node config
    jq_expression: Optional[str] = Field(
        default=None,
        description="jq expression applied to the input JSON (e.g., '.users | map(.name)')"
    )
    jq_input_source: Optional[str] = Field(
        default=None,
        description=(
            "Optional template selecting the input JSON. Supports {{node-id.field}}; "
            "if omitted, the most recent upstream node output is used."
        )
    )
    jq_output_mode: Optional[Literal["first", "all"]] = Field(
        default="first",
        description="'first' returns a single value; 'all' returns the full list of jq results"
    )
    jq_on_error: Optional[Literal["fail", "null"]] = Field(
        default="fail",
        description="'fail' raises on jq errors; 'null' returns null and continues"
    )


class WorkflowNode(BaseModel):
    """A node in the workflow graph."""
    id: str
    type: NodeType
    label: str
    position: Position
    config: NodeConfig


class WorkflowEdge(BaseModel):
    """An edge connecting two nodes in the workflow graph."""
    id: str
    source: str  # source node_id
    target: str  # target node_id
    sourceHandle: Optional[str] = None  # Source handle ID (for conditional nodes)
    targetHandle: Optional[str] = None  # Target handle ID
    label: Optional[str] = None
    condition_result: Optional[bool] = None  # For conditional edges


class WorkflowGraph(BaseModel):
    """The complete workflow graph structure."""
    nodes: List[WorkflowNode]
    edges: List[WorkflowEdge]
    entry_node_id: str  # Starting point for execution


# ============================================================================
# Execution Models
# ============================================================================

class NodeExecutionState(BaseModel):
    """State of a node during workflow execution."""
    node_id: str
    status: ExecutionStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    input_data: Optional[Any] = None
    output_data: Optional[Any] = None
    error: Optional[str] = None


class WorkflowExecution(ObjectModel):
    """
    Represents a single execution instance of a workflow.

    Tracks the execution state of each node and the overall workflow status.
    """
    _table_name: ClassVar[str] = "workflow_executions"

    workflow_id: str
    status: ExecutionStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    node_states: Dict[str, NodeExecutionState] = Field(default_factory=dict)
    final_output: Optional[Any] = None
    error: Optional[str] = None
    triggered_by: Optional[str] = "manual"  # manual, cron, event, dependency

    # Pause/resume support
    current_node_id: Optional[str] = None
    paused_at: Optional[datetime] = None
    paused_reason: Optional[str] = None
    resume_data: Optional[str] = None  # JSON string

    @classmethod
    async def get_all(cls, order_by: str = "started_at DESC", limit: Optional[int] = None):
        """Get all workflow executions."""
        from ..database.repository import repo_query

        query = f"SELECT * FROM workflow_executions ORDER BY {order_by}"
        if limit:
            query += f" LIMIT {limit}"

        rows = await repo_query(query, {})
        return [cls.from_db(row) for row in rows]

    @classmethod
    async def get(cls, execution_id: str):
        """Get execution by ID."""
        from ..database.repository import repo_query

        rows = await repo_query(
            "SELECT * FROM workflow_executions WHERE id = :id",
            {"id": execution_id}
        )

        if not rows:
            return None

        return cls.from_db(rows[0])

    @classmethod
    async def get_by_workflow(cls, workflow_id: str, limit: int = 50):
        """Get executions for a specific workflow."""
        from ..database.repository import repo_query

        rows = await repo_query(
            "SELECT * FROM workflow_executions WHERE workflow_id = :workflow_id ORDER BY started_at DESC LIMIT :limit",
            {"workflow_id": workflow_id, "limit": limit}
        )
        return [cls.from_db(row) for row in rows]

    @classmethod
    def from_db(cls, row: dict):
        """Create instance from database row."""
        # Parse JSON fields
        node_states = {}
        if row.get("node_states") and row["node_states"] != "{}":
            try:
                node_states_data = json.loads(row["node_states"]) if isinstance(row["node_states"], str) else row["node_states"]
                if node_states_data:  # Only process if not empty
                    node_states = {}
                    for node_id, state_data in node_states_data.items():
                        # Convert ISO string timestamps back to datetime objects
                        if state_data.get('started_at') and isinstance(state_data['started_at'], str):
                            state_data['started_at'] = datetime.fromisoformat(state_data['started_at'])
                        if state_data.get('completed_at') and isinstance(state_data['completed_at'], str):
                            state_data['completed_at'] = datetime.fromisoformat(state_data['completed_at'])

                        node_states[node_id] = NodeExecutionState(**state_data)
            except Exception as e:
                print(f"Error parsing node_states: {e}")
                node_states = {}

        final_output = None
        if row.get("final_output"):
            try:
                final_output = json.loads(row["final_output"]) if isinstance(row["final_output"], str) else row["final_output"]
            except Exception:
                final_output = None

        # Parse timestamps
        started_at = row["started_at"]
        if isinstance(started_at, str):
            started_at = datetime.fromisoformat(started_at)

        completed_at = row.get("completed_at")
        if completed_at and isinstance(completed_at, str):
            completed_at = datetime.fromisoformat(completed_at)

        paused_at = row.get("paused_at")
        if paused_at and isinstance(paused_at, str):
            paused_at = datetime.fromisoformat(paused_at)

        return cls(
            id=row["id"],
            workflow_id=row["workflow_id"],
            status=ExecutionStatus(row["status"]),
            started_at=started_at,
            completed_at=completed_at,
            node_states=node_states,
            final_output=final_output,
            error=row.get("error"),
            triggered_by=row.get("triggered_by", "manual"),
            current_node_id=row.get("current_node_id"),
            paused_at=paused_at,
            paused_reason=row.get("paused_reason"),
            resume_data=row.get("resume_data"),
        )

    async def save(self):
        """Save execution to database."""
        import uuid
        from ..database.repository import db_connection

        # Generate ID if this is a new execution
        if self.id is None:
            self.id = str(uuid.uuid4())

        async with db_connection() as db:
            # Serialize node_states and final_output
            # Convert NodeExecutionState to dict with ISO timestamps
            node_states_dict = {}
            for node_id, state in self.node_states.items():
                state_data = state.dict()
                # Convert datetime fields to ISO strings
                if state_data.get('started_at'):
                    state_data['started_at'] = state_data['started_at'].isoformat()
                if state_data.get('completed_at'):
                    state_data['completed_at'] = state_data['completed_at'].isoformat()
                node_states_dict[node_id] = state_data

            node_states_json = json.dumps(node_states_dict)
            final_output_json = json.dumps(self.final_output) if self.final_output else None

            data = {
                "id": self.id,
                "workflow_id": self.workflow_id,
                "status": self.status.value,
                "started_at": self.started_at.isoformat(),
                "completed_at": self.completed_at.isoformat() if self.completed_at else None,
                "node_states": node_states_json,
                "final_output": final_output_json,
                "error": self.error,
                "triggered_by": self.triggered_by,
                "current_node_id": self.current_node_id,
                "paused_at": self.paused_at.isoformat() if self.paused_at else None,
                "paused_reason": self.paused_reason,
                "resume_data": self.resume_data,
            }

            # Check if exists
            existing = await db.query("SELECT id FROM workflow_executions WHERE id = :id", {"id": self.id})

            if existing:
                await db.update("workflow_executions", self.id, data)
            else:
                await db.create("workflow_executions", data)


# ============================================================================
# Schedule Models
# ============================================================================

class EventTrigger(BaseModel):
    """Configuration for event-driven workflow triggers."""
    event_type: str  # "source_updated", "notebook_created", "chat_completed", etc.
    filters: Optional[Dict[str, Any]] = None


class WorkflowSchedule(ObjectModel):
    """
    Defines when and how a workflow should be executed.

    Supports:
    - Cron schedules (time-based)
    - Event triggers (reactive)
    - Dependency chains (sequential workflows)
    """
    _table_name: ClassVar[str] = "workflow_schedules"

    workflow_id: str
    schedule_type: ScheduleType
    cron_expression: Optional[str] = None
    event_trigger: Optional[EventTrigger] = None
    upstream_workflow_id: Optional[str] = None
    enabled: bool = True
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    input_data: Optional[Dict[str, Any]] = None

    @classmethod
    async def get_by_workflow(cls, workflow_id: str):
        """Get schedules for a specific workflow."""
        from ..database.repository import repo_query

        rows = await repo_query(
            "SELECT * FROM workflow_schedules WHERE workflow_id = :workflow_id ORDER BY created_at DESC",
            {"workflow_id": workflow_id}
        )
        return [cls.from_db(row) for row in rows]

    @classmethod
    async def get_enabled(cls):
        """Get all enabled schedules."""
        from ..database.repository import repo_query

        rows = await repo_query(
            "SELECT * FROM workflow_schedules WHERE enabled = :enabled",
            {"enabled": True}
        )
        return [cls.from_db(row) for row in rows]

    @classmethod
    def from_db(cls, row: dict):
        """Create instance from database row."""
        event_trigger = None
        if row.get("event_trigger"):
            event_trigger = EventTrigger(**json.loads(row["event_trigger"]))

        input_data = None
        if row.get("input_data"):
            try:
                input_data = json.loads(row["input_data"])
            except (TypeError, json.JSONDecodeError):
                input_data = None

        return cls(
            id=row["id"],
            workflow_id=row["workflow_id"],
            schedule_type=ScheduleType(row["schedule_type"]),
            cron_expression=row.get("cron_expression"),
            event_trigger=event_trigger,
            upstream_workflow_id=row.get("upstream_workflow_id"),
            enabled=bool(row["enabled"]),
            last_run_at=row.get("last_run_at"),
            next_run_at=row.get("next_run_at"),
            input_data=input_data,
            created=row.get("created_at"),
            updated=row.get("updated_at"),
        )

    async def save(self):
        """Save schedule to database."""
        import uuid
        from ..database.repository import db_connection

        # Generate ID if this is a new schedule
        if self.id is None:
            self.id = str(uuid.uuid4())

        async with db_connection() as db:
            data = {
                "id": self.id,
                "workflow_id": self.workflow_id,
                "schedule_type": self.schedule_type.value,
                "cron_expression": self.cron_expression,
                "event_trigger": json.dumps(self.event_trigger.dict()) if self.event_trigger else None,
                "upstream_workflow_id": self.upstream_workflow_id,
                "enabled": self.enabled,
                "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
                "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
                "input_data": json.dumps(self.input_data) if self.input_data else None,
            }

            # Check if exists
            existing = await db.query("SELECT id FROM workflow_schedules WHERE id = :id", {"id": self.id})

            if existing:
                await db.update("workflow_schedules", self.id, data)
            else:
                await db.create("workflow_schedules", data)


# ============================================================================
# Workflow Model
# ============================================================================

class Workflow(ObjectModel):
    """
    A visual workflow graph definition.

    Contains nodes (LLM, Tool, Conditional) and edges that define execution flow.
    Can be scheduled via cron, events, or dependency chains.
    """
    _table_name: ClassVar[str] = "workflows"

    name: str
    description: Optional[str] = None
    graph: WorkflowGraph
    created_by: str
    is_active: bool = True
    tags: List[str] = Field(default_factory=list)

    @classmethod
    async def get_all(cls, order_by: str = "updated_at DESC", limit: Optional[int] = None):
        """Get all workflows."""
        from ..database.repository import repo_query

        query = f"SELECT * FROM workflows ORDER BY {order_by}"
        if limit:
            query += f" LIMIT {limit}"

        rows = await repo_query(query, {})
        return [cls.from_db(row) for row in rows]

    @classmethod
    async def get_by_user(cls, user_id: str, limit: int = 50):
        """Get workflows created by a specific user."""
        from ..database.repository import repo_query

        rows = await repo_query(
            "SELECT * FROM workflows WHERE created_by = :user_id ORDER BY updated_at DESC LIMIT :limit",
            {"user_id": user_id, "limit": limit}
        )
        return [cls.from_db(row) for row in rows]

    @classmethod
    async def get(cls, workflow_id: str):
        """Get workflow by ID."""
        from ..database.repository import repo_query

        rows = await repo_query(
            "SELECT * FROM workflows WHERE id = :id",
            {"id": workflow_id}
        )

        if not rows:
            return None

        return cls.from_db(rows[0])

    @classmethod
    def from_db(cls, row: dict):
        """Create instance from database row."""
        # Parse graph JSON
        graph_data = json.loads(row["graph_json"])
        graph = WorkflowGraph(**graph_data)

        # Parse tags
        tags = json.loads(row.get("tags", "[]"))

        return cls(
            id=row["id"],
            name=row["name"],
            description=row.get("description"),
            graph=graph,
            created_by=row["created_by"],
            is_active=bool(row["is_active"]),
            tags=tags,
            created=row.get("created_at"),
            updated=row.get("updated_at"),
        )

    async def save(self):
        """Save workflow to database."""
        import uuid
        from ..database.repository import db_connection

        # Generate ID if this is a new workflow
        if self.id is None:
            self.id = str(uuid.uuid4())

        async with db_connection() as db:
            data = {
                "id": self.id,
                "name": self.name,
                "description": self.description,
                "graph_json": json.dumps(self.graph.dict()),
                "created_by": self.created_by,
                "is_active": self.is_active,
                "tags": json.dumps(self.tags),
            }

            # Check if exists
            existing = await db.query("SELECT id FROM workflows WHERE id = :id", {"id": self.id})

            if existing:
                await db.update("workflows", self.id, data)
            else:
                await db.create("workflows", data)

    async def get_executions(self, limit: int = 50):
        """Get execution history for this workflow."""
        return await WorkflowExecution.get_by_workflow(self.workflow_id, limit)

    async def get_schedules(self):
        """Get schedules for this workflow."""
        return await WorkflowSchedule.get_by_workflow(self.id)
