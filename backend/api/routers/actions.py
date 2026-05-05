"""
Actions Router - Manage reusable action configurations

Provides CRUD operations, testing, execution, and history for actions.
Follows the three-model pattern: Create (with secrets), Update (optional secrets), Response (no secrets).
"""

from fastapi import APIRouter, HTTPException, status, Header
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import uuid
import logging

from api.action_models import (
    ActionCreate,
    ActionUpdate,
    ActionResponse,
    ActionExecutionRequest,
    ActionExecutionResponse,
    ActionExecutionDetail,
    ActionStats,
    ActionTestResponse,
)
from open_notebook.database.repository import (
    repo_query,
    repo_create,
    repo_update,
    repo_delete,
)
from open_notebook.config import get_encryption_key
from cryptography.fernet import Fernet
import base64

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/actions", tags=["Actions"])


# ============================================================================
# Helper Functions - Encryption/Decryption
# ============================================================================

def encrypt_auth_config(auth_config: Optional[Dict[str, Any]]) -> Optional[str]:
    """Encrypt authentication configuration using Fernet"""
    if not auth_config:
        return None

    key = get_encryption_key()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Encryption key not configured. Set OPEN_NOTEBOOK_ENCRYPTION_KEY environment variable."
        )

    try:
        fernet = Fernet(key.encode())
        json_str = json.dumps(auth_config)
        encrypted = fernet.encrypt(json_str.encode())
        return base64.b64encode(encrypted).decode()
    except Exception as e:
        logger.error(f"Failed to encrypt auth config: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to encrypt authentication configuration: {str(e)}"
        )


def decrypt_auth_config(encrypted: Optional[str]) -> Optional[Dict[str, Any]]:
    """Decrypt authentication configuration using Fernet"""
    if not encrypted:
        return None

    key = get_encryption_key()
    if not key:
        logger.warning("Encryption key not configured, cannot decrypt auth config")
        return None

    try:
        fernet = Fernet(key.encode())
        encrypted_bytes = base64.b64decode(encrypted.encode())
        decrypted = fernet.decrypt(encrypted_bytes)
        return json.loads(decrypted.decode())
    except Exception as e:
        logger.error(f"Failed to decrypt auth config: {e}")
        return None


def format_action(row: dict) -> ActionResponse:
    """Format database row to ActionResponse model"""
    return ActionResponse(
        id=row["id"],
        name=row["name"],
        description=row.get("description"),
        action_type=row["action_type"],
        endpoint=row.get("endpoint"),
        method=row.get("method", "POST"),
        auth_type=row.get("auth_type"),
        # NO auth_config - never return secrets
        headers=json.loads(row.get("headers") or "{}"),
        query_params=json.loads(row.get("query_params") or "{}"),
        body_template=json.loads(row["body_template"]) if row.get("body_template") else None,
        condition_expression=row.get("condition_expression"),
        retry_policy=json.loads(row["retry_policy"]) if row.get("retry_policy") else None,
        is_active=bool(row.get("is_active", 1)),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        last_executed_at=row.get("last_executed_at"),
        execution_count=row.get("execution_count", 0),
    )


# ============================================================================
# CRUD Endpoints
# ============================================================================

@router.get("", response_model=List[ActionResponse])
async def list_actions(
    action_type: Optional[str] = None,
    is_active: Optional[bool] = None,
):
    """
    List all actions with optional filtering.

    - **action_type**: Filter by action type (webhook, email, hana_operation, workflow_trigger)
    - **is_active**: Filter by active status
    """
    sql = "SELECT * FROM actions WHERE 1=1"
    params = {}

    if action_type:
        sql += " AND action_type = :action_type"
        params["action_type"] = action_type

    if is_active is not None:
        sql += " AND is_active = :is_active"
        params["is_active"] = 1 if is_active else 0

    sql += " ORDER BY created_at DESC"

    results = await repo_query(sql, params)
    return [format_action(row) for row in results]


@router.get("/{action_id}", response_model=ActionResponse)
async def get_action(action_id: str):
    """Get a specific action by ID"""
    sql = "SELECT * FROM actions WHERE id = :id"
    results = await repo_query(sql, {"id": action_id})

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action {action_id} not found"
        )

    return format_action(results[0])


@router.post("", response_model=ActionResponse, status_code=status.HTTP_201_CREATED)
async def create_action(action: ActionCreate):
    """
    Create a new action.

    Authentication config will be encrypted before storage.
    """
    action_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    # Encrypt auth config
    auth_encrypted = encrypt_auth_config(action.auth_config)

    data = {
        "id": action_id,
        "name": action.name,
        "description": action.description,
        "action_type": action.action_type,
        "endpoint": action.endpoint,
        "method": action.method,
        "auth_type": action.auth_type,
        "auth_config_encrypted": auth_encrypted,
        "headers": json.dumps(action.headers),
        "query_params": json.dumps(action.query_params),
        "body_template": json.dumps(action.body_template) if action.body_template else None,
        "condition_expression": action.condition_expression,
        "retry_policy": json.dumps(action.retry_policy) if action.retry_policy else None,
        "is_active": 1,
        "created_at": now,
        "updated_at": now,
        "execution_count": 0,
    }

    try:
        await repo_create("actions", data)
        logger.info(f"Created action {action_id}: {action.name}")
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Action with name '{action.name}' already exists"
            )
        raise

    return await get_action(action_id)


@router.put("/{action_id}", response_model=ActionResponse)
async def update_action(action_id: str, action: ActionUpdate):
    """
    Update an existing action.

    Only provided fields will be updated. Authentication config will be re-encrypted if provided.
    """
    # Verify action exists
    existing = await get_action(action_id)

    # Build update data
    data = {}
    if action.name is not None:
        data["name"] = action.name
    if action.description is not None:
        data["description"] = action.description
    if action.action_type is not None:
        data["action_type"] = action.action_type
    if action.endpoint is not None:
        data["endpoint"] = action.endpoint
    if action.method is not None:
        data["method"] = action.method
    if action.auth_type is not None:
        data["auth_type"] = action.auth_type
    if action.auth_config is not None:
        data["auth_config_encrypted"] = encrypt_auth_config(action.auth_config)
    if action.headers is not None:
        data["headers"] = json.dumps(action.headers)
    if action.query_params is not None:
        data["query_params"] = json.dumps(action.query_params)
    if action.body_template is not None:
        data["body_template"] = json.dumps(action.body_template)
    if action.condition_expression is not None:
        data["condition_expression"] = action.condition_expression
    if action.retry_policy is not None:
        data["retry_policy"] = json.dumps(action.retry_policy)
    if action.is_active is not None:
        data["is_active"] = 1 if action.is_active else 0

    data["updated_at"] = datetime.utcnow().isoformat()

    try:
        await repo_update("actions", action_id, data)
        logger.info(f"Updated action {action_id}")
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Action with name '{action.name}' already exists"
            )
        raise

    return await get_action(action_id)


@router.delete("/{action_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_action(action_id: str):
    """
    Delete an action.

    This will also cascade delete all bindings and executions.
    """
    # Verify action exists
    await get_action(action_id)

    await repo_delete("actions", action_id)
    logger.info(f"Deleted action {action_id}")


# ============================================================================
# Testing Endpoints
# ============================================================================

@router.post("/test", response_model=ActionTestResponse)
async def test_action_config(action: ActionCreate, x_user_id: str = Header(..., alias="X-User-ID")):
    """
    Test an action configuration without saving it.

    Useful for validating configuration before creation.
    """
    from api.services.action_executor import ActionExecutor

    # Create temporary action dict
    temp_action = {
        "id": "test",
        "name": action.name,
        "action_type": action.action_type,
        "endpoint": action.endpoint,
        "method": action.method,
        "auth_type": action.auth_type,
        "auth_config_encrypted": encrypt_auth_config(action.auth_config),
        "headers": json.dumps(action.headers),
        "query_params": json.dumps(action.query_params),
        "body_template": json.dumps(action.body_template) if action.body_template else None,
        "condition_expression": action.condition_expression,
        "retry_policy": json.dumps(action.retry_policy) if action.retry_policy else None,
    }

    # Test context
    test_context = {
        "status": "completed",
        "result": "Test result",
        "test_mode": True,
    }

    executor = ActionExecutor()
    start_time = datetime.utcnow()

    try:
        result = await executor._execute_action_internal(
            action=temp_action,
            context=test_context,
            user_id=x_user_id,
            test_mode=True
        )

        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        return ActionTestResponse(
            success=True,
            message="Action test successful",
            execution_time_ms=execution_time_ms,
            output_data=result.get("output_data"),
            condition_met=result.get("condition_met"),
            condition_details=result.get("condition_details"),
        )

    except Exception as e:
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        logger.error(f"Action test failed: {e}")

        return ActionTestResponse(
            success=False,
            message=f"Action test failed: {str(e)}",
            execution_time_ms=execution_time_ms,
            error_message=str(e),
        )


@router.post("/{action_id}/test", response_model=ActionTestResponse)
async def test_saved_action(action_id: str, x_user_id: str = Header(..., alias="X-User-ID")):
    """
    Test a saved action.

    Uses a test context to verify the action works as expected.
    """
    # Get action
    sql = "SELECT * FROM actions WHERE id = :id"
    results = await repo_query(sql, {"id": action_id})

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action {action_id} not found"
        )

    action = results[0]

    # Test context
    test_context = {
        "status": "completed",
        "result": "Test result",
        "test_mode": True,
    }

    from api.services.action_executor import ActionExecutor

    executor = ActionExecutor()
    start_time = datetime.utcnow()

    try:
        result = await executor._execute_action_internal(
            action=action,
            context=test_context,
            user_id=x_user_id,
            test_mode=True
        )

        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        return ActionTestResponse(
            success=True,
            message="Action test successful",
            execution_time_ms=execution_time_ms,
            output_data=result.get("output_data"),
            condition_met=result.get("condition_met"),
            condition_details=result.get("condition_details"),
        )

    except Exception as e:
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        logger.error(f"Action test failed: {e}")

        return ActionTestResponse(
            success=False,
            message=f"Action test failed: {str(e)}",
            execution_time_ms=execution_time_ms,
            error_message=str(e),
        )


# ============================================================================
# Execution Endpoints
# ============================================================================

@router.post("/{action_id}/execute", response_model=ActionExecutionResponse)
async def execute_action(action_id: str, request: ActionExecutionRequest):
    """
    Manually execute an action with provided context.

    This creates an execution record and returns the result.
    """
    from api.services.action_executor import ActionExecutor

    executor = ActionExecutor()

    try:
        result = await executor.execute_action(
            action_id=action_id,
            context=request.context,
            user_id=request.user_id,
            orchestration_id=request.orchestration_id,
            chat_session_id=request.chat_session_id,
            trigger_event=request.trigger_event,
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute action {action_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute action: {str(e)}"
        )


@router.get("/{action_id}/executions", response_model=List[ActionExecutionDetail])
async def get_action_executions(
    action_id: str,
    limit: int = 50,
    offset: int = 0,
    status_filter: Optional[str] = None,
):
    """
    Get execution history for an action.

    - **limit**: Maximum number of executions to return (default 50)
    - **offset**: Number of executions to skip (default 0)
    - **status_filter**: Filter by status (pending, running, success, failed, skipped)
    """
    # Verify action exists
    await get_action(action_id)

    sql = """
        SELECT
            ae.*,
            a.name as action_name
        FROM action_executions ae
        JOIN actions a ON ae.action_id = a.id
        WHERE ae.action_id = :action_id
    """
    params = {"action_id": action_id, "limit": limit, "offset": offset}

    if status_filter:
        sql += " AND ae.status = :status"
        params["status"] = status_filter

    sql += " ORDER BY ae.created_at DESC LIMIT :limit OFFSET :offset"

    results = await repo_query(sql, params)

    return [
        ActionExecutionDetail(
            id=row["id"],
            action_id=row["action_id"],
            action_name=row["action_name"],
            orchestration_id=row.get("orchestration_id"),
            chat_session_id=row.get("chat_session_id"),
            user_id=row["user_id"],
            status=row["status"],
            trigger_event=row["trigger_event"],
            input_data=json.loads(row["input_data"]) if row.get("input_data") else None,
            output_data=json.loads(row["output_data"]) if row.get("output_data") else None,
            error_message=row.get("error_message"),
            condition_met=bool(row["condition_met"]) if row.get("condition_met") is not None else None,
            condition_details=json.loads(row["condition_details"]) if row.get("condition_details") else None,
            execution_time_ms=row.get("execution_time_ms"),
            retry_count=row.get("retry_count", 0),
            created_at=row["created_at"],
            completed_at=row.get("completed_at"),
        )
        for row in results
    ]


@router.get("/{action_id}/executions/{execution_id}", response_model=ActionExecutionDetail)
async def get_action_execution(action_id: str, execution_id: str):
    """Get details of a specific execution"""
    sql = """
        SELECT
            ae.*,
            a.name as action_name
        FROM action_executions ae
        JOIN actions a ON ae.action_id = a.id
        WHERE ae.id = :execution_id AND ae.action_id = :action_id
    """

    results = await repo_query(sql, {"execution_id": execution_id, "action_id": action_id})

    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution {execution_id} not found for action {action_id}"
        )

    row = results[0]
    return ActionExecutionDetail(
        id=row["id"],
        action_id=row["action_id"],
        action_name=row["action_name"],
        orchestration_id=row.get("orchestration_id"),
        chat_session_id=row.get("chat_session_id"),
        user_id=row["user_id"],
        status=row["status"],
        trigger_event=row["trigger_event"],
        input_data=json.loads(row["input_data"]) if row.get("input_data") else None,
        output_data=json.loads(row["output_data"]) if row.get("output_data") else None,
        error_message=row.get("error_message"),
        condition_met=bool(row["condition_met"]) if row.get("condition_met") is not None else None,
        condition_details=json.loads(row["condition_details"]) if row.get("condition_details") else None,
        execution_time_ms=row.get("execution_time_ms"),
        retry_count=row.get("retry_count", 0),
        created_at=row["created_at"],
        completed_at=row.get("completed_at"),
    )


# ============================================================================
# Statistics Endpoints
# ============================================================================

@router.get("/{action_id}/stats", response_model=ActionStats)
async def get_action_stats(action_id: str):
    """
    Get execution statistics for an action.

    Returns success rate, execution counts, and performance metrics.
    """
    # Verify action exists
    await get_action(action_id)

    sql = """
        SELECT
            COUNT(*) as total_executions,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_executions,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_executions,
            SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped_executions,
            AVG(CASE WHEN execution_time_ms IS NOT NULL THEN execution_time_ms ELSE NULL END) as avg_execution_time_ms,
            MAX(created_at) as last_execution,
            (SELECT status FROM action_executions WHERE action_id = :action_id ORDER BY created_at DESC LIMIT 1) as last_execution_status
        FROM action_executions
        WHERE action_id = :action_id
    """

    results = await repo_query(sql, {"action_id": action_id})
    row = results[0]

    total = row["total_executions"]
    successful = row["successful_executions"]
    success_rate = (successful / total * 100) if total > 0 else 0.0

    return ActionStats(
        action_id=action_id,
        total_executions=total,
        successful_executions=successful,
        failed_executions=row["failed_executions"],
        skipped_executions=row["skipped_executions"],
        success_rate=round(success_rate, 2),
        average_execution_time_ms=round(row["avg_execution_time_ms"], 2) if row["avg_execution_time_ms"] else None,
        last_execution=row["last_execution"],
        last_execution_status=row["last_execution_status"],
    )
