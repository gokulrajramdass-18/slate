"""
Pydantic models for Actions system

Three-model pattern:
- Create models: Include secrets (auth_config)
- Update models: Optional secrets
- Response models: Exclude secrets (never return credentials)
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


# ============================================================================
# Action Models
# ============================================================================

class ActionCreate(BaseModel):
    """Create a new action (includes secrets)"""
    name: str = Field(..., min_length=1, max_length=255, description="Unique action name")
    description: Optional[str] = Field(None, description="Human-readable description")
    action_type: str = Field(
        ...,
        description="Action type: webhook, email, hana_operation, workflow_trigger"
    )
    endpoint: Optional[str] = Field(None, description="URL, table name, or workflow ID")
    method: str = Field(default="POST", description="HTTP method for webhooks")

    # Authentication (secrets included for creation)
    auth_type: Optional[str] = Field(
        default="none",
        description="Authentication type: none, basic, bearer, api_key, oauth2_client"
    )
    auth_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Authentication configuration (will be encrypted)"
    )

    # Request configuration
    headers: Optional[Dict[str, str]] = Field(default_factory=dict, description="HTTP headers")
    query_params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Query parameters")
    body_template: Optional[Dict[str, Any]] = Field(
        None,
        description="Body template with Jinja2 placeholders, e.g., {'result': '{{result}}'}"
    )

    # Conditional execution
    condition_expression: Optional[str] = Field(
        None,
        description="Python expression for conditional execution, e.g., \"status == 'completed'\""
    )

    # Retry configuration
    retry_policy: Optional[Dict[str, Any]] = Field(
        None,
        description="Retry policy: {'max_retries': 3, 'backoff': 'exponential'}"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "send_slack_notification",
                "description": "Send notification to Slack channel",
                "action_type": "webhook",
                "endpoint": "https://hooks.slack.com/services/...",
                "method": "POST",
                "auth_type": "bearer",
                "auth_config": {"token": "xoxb-..."},
                "body_template": {
                    "text": "Orchestration completed: {{result}}",
                    "channel": "#notifications"
                },
                "condition_expression": "status == 'completed'",
                "retry_policy": {"max_retries": 3, "backoff": "exponential"}
            }
        }


class ActionUpdate(BaseModel):
    """Update an existing action (optional secrets)"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    action_type: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    auth_type: Optional[str] = None
    auth_config: Optional[Dict[str, Any]] = None  # Optional: only update if provided
    headers: Optional[Dict[str, str]] = None
    query_params: Optional[Dict[str, Any]] = None
    body_template: Optional[Dict[str, Any]] = None
    condition_expression: Optional[str] = None
    retry_policy: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ActionResponse(BaseModel):
    """Action response (excludes secrets)"""
    id: str
    name: str
    description: Optional[str]
    action_type: str
    endpoint: Optional[str]
    method: str
    auth_type: Optional[str]
    # NO auth_config field - never return secrets
    headers: Dict[str, str]
    query_params: Dict[str, Any]
    body_template: Optional[Dict[str, Any]]
    condition_expression: Optional[str]
    retry_policy: Optional[Dict[str, Any]]
    is_active: bool
    created_at: str
    updated_at: str
    last_executed_at: Optional[str]
    execution_count: int

    class Config:
        from_attributes = True


# ============================================================================
# Action Execution Models
# ============================================================================

class ActionExecutionRequest(BaseModel):
    """Request to execute an action"""
    context: Dict[str, Any] = Field(
        ...,
        description="Variables for template rendering and condition evaluation"
    )
    user_id: str = Field(..., description="User ID executing the action")
    orchestration_id: Optional[str] = Field(None, description="Orchestration ID if triggered by orchestration")
    chat_session_id: Optional[str] = Field(None, description="Chat session ID if triggered by chat")
    trigger_event: Optional[str] = Field(
        default="manual",
        description="Event that triggered execution: manual, orchestration.completed, etc."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "context": {
                    "status": "completed",
                    "result": "Analysis complete",
                    "confidence": 0.95
                },
                "user_id": "user-123",
                "orchestration_id": "orch-456",
                "trigger_event": "orchestration.completed"
            }
        }


class ActionExecutionResponse(BaseModel):
    """Response from action execution"""
    execution_id: str
    action_id: str
    status: str  # pending, running, success, failed, skipped
    condition_met: Optional[bool]
    output_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    execution_time_ms: Optional[int]
    created_at: str
    completed_at: Optional[str]

    class Config:
        from_attributes = True


class ActionExecutionDetail(BaseModel):
    """Detailed execution information including input"""
    id: str
    action_id: str
    action_name: str  # Denormalized for UI
    orchestration_id: Optional[str]
    chat_session_id: Optional[str]
    user_id: str
    status: str
    trigger_event: str
    input_data: Optional[Dict[str, Any]]
    output_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    condition_met: Optional[bool]
    condition_details: Optional[Dict[str, Any]]
    execution_time_ms: Optional[int]
    retry_count: int
    created_at: str
    completed_at: Optional[str]


class ActionStats(BaseModel):
    """Statistics for an action"""
    action_id: str
    total_executions: int
    successful_executions: int
    failed_executions: int
    skipped_executions: int
    success_rate: float
    average_execution_time_ms: Optional[float]
    last_execution: Optional[str]
    last_execution_status: Optional[str]


# ============================================================================
# Action Binding Models
# ============================================================================

class ActionBindingCreate(BaseModel):
    """Create an action binding to an orchestration"""
    action_id: str = Field(..., description="Action ID to bind")
    trigger_condition: str = Field(
        ...,
        description="Trigger condition: on_start, on_completion, on_failure, on_phase_change, always"
    )
    phase_filter: Optional[List[str]] = Field(
        None,
        description="Phases to trigger on (for on_phase_change), e.g., ['planning', 'execution']"
    )
    execution_order: int = Field(
        default=0,
        description="Order of execution if multiple actions are bound"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "action_id": "action-123",
                "trigger_condition": "on_completion",
                "phase_filter": None,
                "execution_order": 0
            }
        }


class ActionBindingUpdate(BaseModel):
    """Update an action binding"""
    trigger_condition: Optional[str] = None
    phase_filter: Optional[List[str]] = None
    execution_order: Optional[int] = None
    is_active: Optional[bool] = None


class ActionBindingResponse(BaseModel):
    """Action binding response"""
    id: str
    schedule_id: Optional[str]
    orchestration_id: Optional[str]
    action_id: str
    action_name: str  # Denormalized for UI
    action_type: str  # Denormalized for UI
    trigger_condition: str
    phase_filter: Optional[List[str]]
    execution_order: int
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


# ============================================================================
# Test Models
# ============================================================================

class ActionTestResponse(BaseModel):
    """Response from testing an action"""
    success: bool
    message: str
    execution_time_ms: Optional[int] = None
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    condition_met: Optional[bool] = None
    condition_details: Optional[Dict[str, Any]] = None
