"""
Action Executor Service

Executes actions with full lifecycle management:
- Condition evaluation
- Template rendering
- Authentication
- Retry policies
- Result capture
- Audit logging

Supports:
- Webhooks (HTTP requests with auth)
- Email (via SMTP)
- HANA operations (INSERT/UPDATE)
- Workflow triggers (start orchestrations)
"""

import json
import logging
import asyncio
import time
import uuid
from typing import Dict, Any, Optional, Tuple, Callable
from datetime import datetime
from jinja2 import Template, TemplateSyntaxError
import httpx

from open_notebook.database.repository import repo_query, repo_create, repo_update, repo_execute
from api.action_models import ActionExecutionResponse

logger = logging.getLogger(__name__)


class ActionExecutor:
    """Execute actions with authentication, retry, and result capture"""

    async def execute_action(
        self,
        action_id: str,
        context: Dict[str, Any],
        user_id: str,
        orchestration_id: Optional[str] = None,
        chat_session_id: Optional[str] = None,
        trigger_event: Optional[str] = "manual",
    ) -> ActionExecutionResponse:
        """
        Execute an action with full lifecycle management.

        Steps:
        1. Load action config
        2. Evaluate condition (if present)
        3. Render body template with context
        4. Execute action (with retry)
        5. Record execution result
        """
        start_time = time.time()
        execution_id = str(uuid.uuid4())

        try:
            # Load action
            sql = "SELECT * FROM actions WHERE id = :id AND is_active = 1"
            results = await repo_query(sql, {"id": action_id})

            if not results:
                raise ValueError(f"Action {action_id} not found or inactive")

            action = results[0]

            # Execute internally
            result = await self._execute_action_internal(
                action=action,
                context=context,
                user_id=user_id,
                test_mode=False,
            )

            execution_time_ms = int((time.time() - start_time) * 1000)

            # Record execution
            execution_id = await self._record_execution(
                action_id=action_id,
                status=result["status"],
                input_data=result["input_data"],
                output_data=result.get("output_data"),
                error_message=result.get("error_message"),
                condition_met=result.get("condition_met"),
                condition_details=result.get("condition_details"),
                execution_time_ms=execution_time_ms,
                retry_count=result.get("retry_count", 0),
                user_id=user_id,
                orchestration_id=orchestration_id,
                chat_session_id=chat_session_id,
                trigger_event=trigger_event,
            )

            # Update action stats
            await self._update_action_stats(action_id)

            return ActionExecutionResponse(
                execution_id=execution_id,
                action_id=action_id,
                status=result["status"],
                condition_met=result.get("condition_met"),
                output_data=result.get("output_data"),
                error_message=result.get("error_message"),
                execution_time_ms=execution_time_ms,
                created_at=datetime.utcnow().isoformat(),
                completed_at=datetime.utcnow().isoformat(),
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Failed to execute action {action_id}: {e}")

            # Record failed execution
            execution_id = await self._record_execution(
                action_id=action_id,
                status="failed",
                input_data={"context": context},
                output_data=None,
                error_message=str(e),
                condition_met=None,
                condition_details=None,
                execution_time_ms=execution_time_ms,
                retry_count=0,
                user_id=user_id,
                orchestration_id=orchestration_id,
                chat_session_id=chat_session_id,
                trigger_event=trigger_event,
            )

            raise

    async def _execute_action_internal(
        self,
        action: Dict[str, Any],
        context: Dict[str, Any],
        user_id: str,
        test_mode: bool = False,
    ) -> Dict[str, Any]:
        """
        Internal execution logic (without recording).

        Used for both real execution and testing.
        """
        action_type = action["action_type"]
        retry_policy = json.loads(action.get("retry_policy") or "null")

        # Step 1: Evaluate condition
        condition_met = True
        condition_details = None

        if action.get("condition_expression"):
            condition_met, condition_details = await self._evaluate_condition(
                action["condition_expression"],
                context
            )

            if not condition_met:
                return {
                    "status": "skipped",
                    "condition_met": False,
                    "condition_details": condition_details,
                    "input_data": {"context": context},
                    "output_data": {"message": "Condition not met, action skipped"},
                }

        # Step 2: Render template
        rendered_body = None
        if action.get("body_template"):
            try:
                body_template = json.loads(action["body_template"])
                rendered_body = await self._render_template(body_template, context)
            except Exception as e:
                logger.error(f"Failed to render template: {e}")
                return {
                    "status": "failed",
                    "error_message": f"Template rendering failed: {str(e)}",
                    "condition_met": condition_met,
                    "condition_details": condition_details,
                    "input_data": {"context": context},
                }

        # Step 3: Execute action with retry
        try:
            if retry_policy:
                output_data, retry_count = await self._retry_with_policy(
                    lambda: self._execute_by_type(action, rendered_body, context, test_mode),
                    retry_policy
                )
            else:
                output_data = await self._execute_by_type(action, rendered_body, context, test_mode)
                retry_count = 0

            return {
                "status": "success",
                "condition_met": condition_met,
                "condition_details": condition_details,
                "input_data": {"context": context, "rendered_body": rendered_body},
                "output_data": output_data,
                "retry_count": retry_count,
            }

        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return {
                "status": "failed",
                "error_message": str(e),
                "condition_met": condition_met,
                "condition_details": condition_details,
                "input_data": {"context": context, "rendered_body": rendered_body},
            }

    async def _execute_by_type(
        self,
        action: Dict[str, Any],
        rendered_body: Optional[Dict[str, Any]],
        context: Dict[str, Any],
        test_mode: bool = False,
    ) -> Dict[str, Any]:
        """Route execution to type-specific handler"""
        action_type = action["action_type"]

        if action_type == "webhook":
            return await self._execute_webhook(action, rendered_body, test_mode)
        elif action_type == "email":
            return await self._execute_email(action, rendered_body, test_mode)
        elif action_type == "hana_operation":
            return await self._execute_hana_operation(action, rendered_body, context, test_mode)
        elif action_type == "workflow_trigger":
            return await self._execute_workflow_trigger(action, rendered_body, context, test_mode)
        else:
            raise ValueError(f"Unsupported action type: {action_type}")

    # ============================================================================
    # Condition Evaluation
    # ============================================================================

    async def _evaluate_condition(
        self,
        condition: str,
        context: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Evaluate conditional expression using Python eval with safe context.

        Example: "status == 'completed' and result.confidence > 0.8"

        Returns: (condition_met, variables_used)
        """
        try:
            # Build safe evaluation context
            safe_context = {
                "__builtins__": {
                    "True": True,
                    "False": False,
                    "None": None,
                    "len": len,
                    "str": str,
                    "int": int,
                    "float": float,
                    "bool": bool,
                },
                **context  # User variables
            }

            # Evaluate condition
            result = eval(condition, safe_context)

            # Extract variables used in condition
            used_vars = {k: v for k, v in context.items() if k in condition}

            return bool(result), {
                "expression": condition,
                "result": result,
                "variables": used_vars,
            }

        except Exception as e:
            logger.error(f"Condition evaluation failed: {e}")
            # Default to True on evaluation error (don't skip due to bad condition)
            return True, {
                "expression": condition,
                "error": str(e),
                "default_result": True,
            }

    # ============================================================================
    # Template Rendering
    # ============================================================================

    async def _render_template(
        self,
        template: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Render body template with Jinja2-style placeholders.

        Example:
        - Template: {"result": "{{result}}", "status": "{{status}}"}
        - Context: {"result": "Success", "status": "completed"}
        - Output: {"result": "Success", "status": "completed"}
        """
        try:
            rendered = {}

            for key, value in template.items():
                if isinstance(value, str):
                    # Render string with Jinja2
                    jinja_template = Template(value)
                    rendered[key] = jinja_template.render(**context)
                elif isinstance(value, dict):
                    # Recursively render nested dicts
                    rendered[key] = await self._render_template(value, context)
                elif isinstance(value, list):
                    # Render each item in list
                    rendered[key] = [
                        Template(item).render(**context) if isinstance(item, str) else item
                        for item in value
                    ]
                else:
                    # Keep non-string values as-is
                    rendered[key] = value

            return rendered

        except TemplateSyntaxError as e:
            raise ValueError(f"Template syntax error: {str(e)}")
        except Exception as e:
            raise ValueError(f"Template rendering failed: {str(e)}")

    # ============================================================================
    # Type-Specific Executors
    # ============================================================================

    async def _execute_webhook(
        self,
        action: Dict[str, Any],
        rendered_body: Optional[Dict[str, Any]],
        test_mode: bool = False,
    ) -> Dict[str, Any]:
        """Execute HTTP webhook with authentication"""
        from api.services.action_auth_manager import ActionAuthManager

        endpoint = action["endpoint"]
        method = action.get("method", "POST").upper()
        headers = json.loads(action.get("headers") or "{}")
        query_params = json.loads(action.get("query_params") or "{}")

        # Get authenticated HTTP client
        auth_manager = ActionAuthManager(action)
        client = await auth_manager.get_client()

        try:
            # Make request
            if method == "GET":
                response = await client.get(endpoint, headers=headers, params=query_params)
            elif method == "POST":
                response = await client.post(endpoint, headers=headers, params=query_params, json=rendered_body)
            elif method == "PUT":
                response = await client.put(endpoint, headers=headers, params=query_params, json=rendered_body)
            elif method == "DELETE":
                response = await client.delete(endpoint, headers=headers, params=query_params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()

            # Parse response
            try:
                response_data = response.json()
            except:
                response_data = {"text": response.text}

            return {
                "status_code": response.status_code,
                "response": response_data,
                "test_mode": test_mode,
            }

        finally:
            await client.aclose()

    async def _execute_email(
        self,
        action: Dict[str, Any],
        rendered_body: Optional[Dict[str, Any]],
        test_mode: bool = False,
    ) -> Dict[str, Any]:
        """Send email via SMTP"""
        from api.services.smtp_service import SMTPService

        to_email = action["endpoint"]  # Email address in endpoint field
        subject = rendered_body.get("subject", "Notification from Open Notebook")
        body = rendered_body.get("body", "")
        is_html = rendered_body.get("is_html", False)

        if test_mode:
            return {
                "message": "Email would be sent (test mode)",
                "to": to_email,
                "subject": subject,
                "test_mode": True,
            }

        success = await SMTPService.send_email(to_email, subject, body, is_html)

        if not success:
            raise Exception("Failed to send email via SMTP")

        return {
            "message": "Email sent successfully",
            "to": to_email,
            "subject": subject,
        }

    async def _execute_hana_operation(
        self,
        action: Dict[str, Any],
        rendered_body: Optional[Dict[str, Any]],
        context: Dict[str, Any],
        test_mode: bool = False,
    ) -> Dict[str, Any]:
        """Execute HANA INSERT/UPDATE"""
        table_name = action["endpoint"]  # Table name in endpoint field
        operation = rendered_body.get("operation", "INSERT").upper()
        data = rendered_body.get("data", {})

        if test_mode:
            return {
                "message": f"Would execute {operation} on {table_name} (test mode)",
                "table": table_name,
                "operation": operation,
                "data": data,
                "test_mode": True,
            }

        # Get HANA connection from context or default
        # This assumes HANA connection is available
        from open_notebook.config import get_database

        async with get_database() as db:
            if operation == "INSERT":
                # Generate ID if not provided
                if "id" not in data:
                    data["id"] = str(uuid.uuid4())

                # Build INSERT statement
                columns = ", ".join(data.keys())
                placeholders = ", ".join([f":{k}" for k in data.keys()])
                sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"

                await db.execute(sql, data)

                return {
                    "message": f"Inserted record into {table_name}",
                    "table": table_name,
                    "operation": "INSERT",
                    "record_id": data.get("id"),
                }

            elif operation == "UPDATE":
                record_id = data.pop("id", None)
                if not record_id:
                    raise ValueError("ID required for UPDATE operation")

                # Build UPDATE statement
                set_clause = ", ".join([f"{k} = :{k}" for k in data.keys()])
                sql = f"UPDATE {table_name} SET {set_clause} WHERE id = :id"
                data["id"] = record_id

                await db.execute(sql, data)

                return {
                    "message": f"Updated record in {table_name}",
                    "table": table_name,
                    "operation": "UPDATE",
                    "record_id": record_id,
                }

            else:
                raise ValueError(f"Unsupported HANA operation: {operation}")

    async def _execute_workflow_trigger(
        self,
        action: Dict[str, Any],
        rendered_body: Optional[Dict[str, Any]],
        context: Dict[str, Any],
        test_mode: bool = False,
    ) -> Dict[str, Any]:
        """Start new orchestration"""
        goal = rendered_body.get("goal", "Triggered workflow")
        notebook_id = rendered_body.get("notebook_id")
        resources = rendered_body.get("resources", {})

        if test_mode:
            return {
                "message": "Would start orchestration (test mode)",
                "goal": goal,
                "notebook_id": notebook_id,
                "test_mode": True,
            }

        # Create new orchestration
        from open_notebook.agents.autonomous_orchestrator import AutonomousOrchestrator

        orchestrator = AutonomousOrchestrator(
            goal=goal,
            user_id=context.get("user_id"),
            notebook_id=notebook_id,
            resources=resources,
        )

        # Start orchestration asynchronously
        asyncio.create_task(orchestrator.execute())

        return {
            "message": "Orchestration started",
            "goal": goal,
            "orchestration_id": orchestrator.orchestration_id,
        }

    # ============================================================================
    # Retry Logic
    # ============================================================================

    async def _retry_with_policy(
        self,
        func: Callable,
        retry_policy: Dict[str, Any]
    ) -> Tuple[Any, int]:
        """
        Execute function with retry policy (exponential backoff).

        Returns: (result, retry_count)
        """
        max_retries = retry_policy.get("max_retries", 3)
        backoff = retry_policy.get("backoff", "exponential")
        initial_delay = retry_policy.get("initial_delay", 1.0)

        retry_count = 0
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                result = await func()
                return result, retry_count

            except Exception as e:
                last_exception = e
                retry_count += 1

                if attempt < max_retries:
                    # Calculate delay
                    if backoff == "exponential":
                        delay = initial_delay * (2 ** attempt)
                    elif backoff == "linear":
                        delay = initial_delay * (attempt + 1)
                    else:
                        delay = initial_delay

                    logger.warning(f"Action execution failed (attempt {attempt + 1}/{max_retries + 1}), retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Action execution failed after {max_retries + 1} attempts: {e}")
                    raise last_exception

    # ============================================================================
    # Execution Recording
    # ============================================================================

    async def _record_execution(
        self,
        action_id: str,
        status: str,
        input_data: Dict[str, Any],
        output_data: Optional[Dict[str, Any]],
        error_message: Optional[str],
        condition_met: Optional[bool],
        condition_details: Optional[Dict[str, Any]],
        execution_time_ms: int,
        retry_count: int,
        user_id: str,
        orchestration_id: Optional[str],
        chat_session_id: Optional[str],
        trigger_event: str,
    ) -> str:
        """Record execution to action_executions table"""
        execution_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        data = {
            "id": execution_id,
            "action_id": action_id,
            "orchestration_id": orchestration_id,
            "chat_session_id": chat_session_id,
            "user_id": user_id,
            "status": status,
            "trigger_event": trigger_event,
            "input_data": json.dumps(input_data),
            "output_data": json.dumps(output_data) if output_data else None,
            "error_message": error_message,
            "condition_met": 1 if condition_met else 0 if condition_met is False else None,
            "condition_details": json.dumps(condition_details) if condition_details else None,
            "execution_time_ms": execution_time_ms,
            "retry_count": retry_count,
            "created_at": now,
            "completed_at": now,
        }

        await repo_create("action_executions", data)
        logger.info(f"Recorded execution {execution_id} for action {action_id}: {status}")

        return execution_id

    async def _update_action_stats(self, action_id: str):
        """Update action execution stats"""
        now = datetime.utcnow().isoformat()

        # Increment execution count
        sql = """
            UPDATE actions
            SET execution_count = execution_count + 1,
                last_executed_at = :last_executed_at
            WHERE id = :id
        """
        await repo_execute(sql, {"id": action_id, "last_executed_at": now})
