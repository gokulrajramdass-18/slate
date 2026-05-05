"""
Unit tests for Action Executor Service

Tests all core functionality of the ActionExecutor service including:
- Action execution lifecycle
- Condition evaluation
- Template rendering
- Authentication handling
- Retry policies
- Error handling
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from api.services.action_executor import ActionExecutor
from api.models.action_models import ActionExecutionRequest


@pytest.fixture
def executor():
    """Create an ActionExecutor instance for testing."""
    return ActionExecutor()


@pytest.fixture
def sample_action():
    """Sample action configuration for testing."""
    return {
        "id": "test-action-id",
        "name": "test_action",
        "action_type": "webhook",
        "endpoint": "https://api.example.com/webhook",
        "method": "POST",
        "auth_type": "none",
        "auth_config_encrypted": None,
        "headers": {"Content-Type": "application/json"},
        "query_params": {},
        "body_template": {
            "status": "{{status}}",
            "result": "{{result}}",
            "message": "Orchestration {{status}}"
        },
        "condition_expression": "status == 'completed'",
        "retry_policy": {
            "max_retries": 3,
            "backoff": "exponential",
            "initial_delay": 1.0
        },
        "is_active": True
    }


@pytest.fixture
def sample_context():
    """Sample execution context."""
    return {
        "status": "completed",
        "result": "Success",
        "orchestration_id": "orch-123",
        "goal": "Test goal"
    }


class TestActionExecutor:
    """Test suite for ActionExecutor."""

    @pytest.mark.asyncio
    async def test_execute_action_success(self, executor, sample_action, sample_context):
        """Test successful action execution."""
        with patch.object(executor, '_load_action', return_value=sample_action), \
             patch.object(executor, '_record_execution', return_value="exec-123"), \
             patch.object(executor, '_execute_webhook', new_callable=AsyncMock,
                         return_value={"status": "success"}):

            result = await executor.execute_action(
                action_id="test-action-id",
                context=sample_context,
                user_id="user-123",
                trigger_event="test"
            )

            assert result.execution_id == "exec-123"
            assert result.status == "success"
            assert result.condition_met is True

    @pytest.mark.asyncio
    async def test_execute_action_condition_not_met(self, executor, sample_action, sample_context):
        """Test action execution when condition is not met."""
        # Modify context so condition fails
        context = {"status": "failed", "result": "Error"}

        with patch.object(executor, '_load_action', return_value=sample_action), \
             patch.object(executor, '_record_execution', return_value="exec-123"):

            result = await executor.execute_action(
                action_id="test-action-id",
                context=context,
                user_id="user-123",
                trigger_event="test"
            )

            assert result.status == "skipped"
            assert result.condition_met is False

    @pytest.mark.asyncio
    async def test_execute_action_no_condition(self, executor, sample_action, sample_context):
        """Test action execution when no condition is specified."""
        sample_action["condition_expression"] = None

        with patch.object(executor, '_load_action', return_value=sample_action), \
             patch.object(executor, '_record_execution', return_value="exec-123"), \
             patch.object(executor, '_execute_webhook', new_callable=AsyncMock,
                         return_value={"status": "success"}):

            result = await executor.execute_action(
                action_id="test-action-id",
                context=sample_context,
                user_id="user-123",
                trigger_event="test"
            )

            assert result.status == "success"
            assert result.condition_met is None

    @pytest.mark.asyncio
    async def test_execute_action_failure(self, executor, sample_action, sample_context):
        """Test action execution failure."""
        with patch.object(executor, '_load_action', return_value=sample_action), \
             patch.object(executor, '_record_execution', return_value="exec-123"), \
             patch.object(executor, '_execute_webhook', new_callable=AsyncMock,
                         side_effect=Exception("Connection error")):

            result = await executor.execute_action(
                action_id="test-action-id",
                context=sample_context,
                user_id="user-123",
                trigger_event="test"
            )

            assert result.status == "failed"
            assert "Connection error" in result.error_message

    def test_evaluate_condition_true(self, executor):
        """Test condition evaluation that returns True."""
        condition = "status == 'completed' and confidence > 0.8"
        context = {"status": "completed", "confidence": 0.9}

        result, details = executor._evaluate_condition(condition, context)

        assert result is True
        assert details["expression"] == condition
        assert details["result"] is True
        assert details["variables"] == context

    def test_evaluate_condition_false(self, executor):
        """Test condition evaluation that returns False."""
        condition = "status == 'completed'"
        context = {"status": "failed"}

        result, details = executor._evaluate_condition(condition, context)

        assert result is False

    def test_evaluate_condition_complex(self, executor):
        """Test complex condition evaluation."""
        condition = "len(results) > 10 and quality == 'high'"
        context = {"results": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11], "quality": "high"}

        result, details = executor._evaluate_condition(condition, context)

        assert result is True

    def test_evaluate_condition_missing_variable(self, executor):
        """Test condition evaluation with missing variable."""
        condition = "status == 'completed'"
        context = {}  # Missing status

        result, details = executor._evaluate_condition(condition, context)

        assert result is False
        assert "error" in details

    def test_evaluate_condition_invalid_syntax(self, executor):
        """Test condition evaluation with invalid Python syntax."""
        condition = "status == 'completed' and ("  # Invalid syntax
        context = {"status": "completed"}

        result, details = executor._evaluate_condition(condition, context)

        assert result is False
        assert "error" in details

    def test_render_template_simple(self, executor):
        """Test simple template rendering."""
        template = {
            "message": "Status: {{status}}",
            "value": "{{value}}"
        }
        context = {"status": "success", "value": 42}

        rendered = executor._render_template(template, context)

        assert rendered["message"] == "Status: success"
        assert rendered["value"] == "42"

    def test_render_template_nested(self, executor):
        """Test nested template rendering."""
        template = {
            "data": {
                "result": "{{result}}",
                "details": {
                    "status": "{{status}}"
                }
            }
        }
        context = {"result": "Success", "status": "completed"}

        rendered = executor._render_template(template, context)

        assert rendered["data"]["result"] == "Success"
        assert rendered["data"]["details"]["status"] == "completed"

    def test_render_template_missing_variable(self, executor):
        """Test template rendering with missing variable."""
        template = {"message": "Status: {{status}}"}
        context = {}  # Missing status

        rendered = executor._render_template(template, context)

        # Jinja2 renders missing variables as empty string
        assert rendered["message"] == "Status: "

    def test_render_template_with_filters(self, executor):
        """Test template rendering with Jinja2 filters."""
        template = {
            "uppercase": "{{name | upper}}",
            "default": "{{value | default('N/A')}}"
        }
        context = {"name": "test"}

        rendered = executor._render_template(template, context)

        assert rendered["uppercase"] == "TEST"
        assert rendered["default"] == "N/A"

    @pytest.mark.asyncio
    async def test_execute_webhook_success(self, executor):
        """Test successful webhook execution."""
        action = {
            "endpoint": "https://api.example.com/webhook",
            "method": "POST",
            "auth_type": "none",
            "headers": {"Content-Type": "application/json"}
        }
        body = {"message": "Test"}

        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = AsyncMock(return_value={"status": "ok"})
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await executor._execute_webhook(action, body)

            assert result["status_code"] == 200
            assert result["response"] == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_execute_webhook_auth_bearer(self, executor):
        """Test webhook execution with Bearer auth."""
        action = {
            "endpoint": "https://api.example.com/webhook",
            "method": "POST",
            "auth_type": "bearer",
            "auth_config_encrypted": None,
            "headers": {}
        }
        body = {"message": "Test"}

        with patch.object(executor, '_get_authenticated_client', new_callable=AsyncMock) as mock_auth:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = AsyncMock(return_value={})
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_auth.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_auth.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await executor._execute_webhook(action, body)

            assert result["status_code"] == 200
            mock_auth.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_email_success(self, executor):
        """Test successful email execution."""
        action = {
            "endpoint": "user@example.com",
            "body_template": {
                "subject": "Test Subject",
                "body": "Test Body",
                "is_html": False
            }
        }
        rendered_body = {
            "subject": "Test Subject",
            "body": "Test Body",
            "is_html": False
        }

        with patch('api.services.action_executor.SMTPService') as mock_smtp:
            mock_instance = mock_smtp.return_value
            mock_instance.send_email = AsyncMock(return_value=True)

            result = await executor._execute_email(action, rendered_body)

            assert result["sent"] is True
            assert result["recipient"] == "user@example.com"
            mock_instance.send_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_hana_operation_insert(self, executor):
        """Test HANA INSERT operation."""
        action = {
            "endpoint": "test_table"
        }
        rendered_body = {
            "operation": "INSERT",
            "data": {
                "column1": "value1",
                "column2": "value2"
            }
        }

        with patch('api.services.action_executor.repo_create') as mock_create:
            mock_create.return_value = "new-id"

            result = await executor._execute_hana_operation(action, rendered_body)

            assert result["operation"] == "INSERT"
            assert result["table"] == "test_table"
            assert result["id"] == "new-id"
            mock_create.assert_called_once_with("test_table", rendered_body["data"])

    @pytest.mark.asyncio
    async def test_execute_hana_operation_update(self, executor):
        """Test HANA UPDATE operation."""
        action = {
            "endpoint": "test_table"
        }
        rendered_body = {
            "operation": "UPDATE",
            "id": "record-123",
            "data": {
                "column1": "new_value"
            }
        }

        with patch('api.services.action_executor.repo_update') as mock_update:
            mock_update.return_value = None

            result = await executor._execute_hana_operation(action, rendered_body)

            assert result["operation"] == "UPDATE"
            assert result["table"] == "test_table"
            assert result["id"] == "record-123"
            mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_workflow_trigger(self, executor):
        """Test workflow trigger execution."""
        action = {}
        rendered_body = {
            "goal": "Test goal",
            "notebook_id": "notebook-123",
            "resources": {"source_ids": ["source-1"]}
        }

        with patch('api.services.action_executor.executeOrchestration', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"orchestration_id": "new-orch-123"}

            result = await executor._execute_workflow_trigger(action, rendered_body)

            assert result["orchestration_id"] == "new-orch-123"
            mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_with_policy_success_first_try(self, executor):
        """Test retry policy with success on first attempt."""
        mock_func = AsyncMock(return_value="success")
        retry_policy = {"max_retries": 3, "backoff": "exponential", "initial_delay": 0.1}

        result = await executor._retry_with_policy(mock_func, retry_policy)

        assert result == "success"
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_with_policy_success_after_retries(self, executor):
        """Test retry policy with success after failures."""
        mock_func = AsyncMock(side_effect=[
            Exception("Fail 1"),
            Exception("Fail 2"),
            "success"
        ])
        retry_policy = {"max_retries": 3, "backoff": "exponential", "initial_delay": 0.1}

        result = await executor._retry_with_policy(mock_func, retry_policy)

        assert result == "success"
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_with_policy_max_retries_exceeded(self, executor):
        """Test retry policy when max retries is exceeded."""
        mock_func = AsyncMock(side_effect=Exception("Persistent error"))
        retry_policy = {"max_retries": 2, "backoff": "exponential", "initial_delay": 0.1}

        with pytest.raises(Exception, match="Persistent error"):
            await executor._retry_with_policy(mock_func, retry_policy)

        assert mock_func.call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_retry_with_policy_linear_backoff(self, executor):
        """Test retry policy with linear backoff."""
        call_times = []

        async def mock_func():
            call_times.append(datetime.now())
            if len(call_times) < 3:
                raise Exception("Fail")
            return "success"

        retry_policy = {"max_retries": 3, "backoff": "linear", "initial_delay": 0.1}

        result = await executor._retry_with_policy(mock_func, retry_policy)

        assert result == "success"
        assert len(call_times) == 3

        # Check delays increase linearly (with some tolerance)
        delay1 = (call_times[1] - call_times[0]).total_seconds()
        delay2 = (call_times[2] - call_times[1]).total_seconds()

        # Linear backoff should roughly double each time with initial_delay
        assert 0.08 < delay1 < 0.15  # ~0.1s
        assert 0.15 < delay2 < 0.25  # ~0.2s

    @pytest.mark.asyncio
    async def test_record_execution(self, executor):
        """Test execution recording."""
        with patch('api.services.action_executor.repo_create') as mock_create:
            mock_create.return_value = "exec-id-123"

            exec_id = await executor._record_execution(
                action_id="action-123",
                status="success",
                input_data={"test": "data"},
                output_data={"result": "ok"},
                error_message=None,
                condition_met=True,
                condition_details={"expression": "true"},
                execution_time_ms=150,
                retry_count=0,
                user_id="user-123",
                orchestration_id="orch-123",
                chat_session_id=None,
                trigger_event="test"
            )

            assert exec_id == "exec-id-123"
            mock_create.assert_called_once()

            # Verify the data passed to repo_create
            call_args = mock_create.call_args[0]
            assert call_args[0] == "action_executions"
            data = call_args[1]
            assert data["action_id"] == "action-123"
            assert data["status"] == "success"
            assert data["condition_met"] == 1
            assert data["execution_time_ms"] == 150


class TestActionExecutorIntegration:
    """Integration tests for ActionExecutor with real-ish scenarios."""

    @pytest.mark.asyncio
    async def test_full_webhook_flow(self, executor):
        """Test complete webhook execution flow."""
        action = {
            "id": "webhook-action",
            "name": "slack_notification",
            "action_type": "webhook",
            "endpoint": "https://hooks.slack.com/services/TEST",
            "method": "POST",
            "auth_type": "none",
            "headers": {"Content-Type": "application/json"},
            "body_template": {
                "text": "Orchestration {{status}}: {{result}}"
            },
            "condition_expression": "status == 'completed'",
            "retry_policy": {"max_retries": 2, "backoff": "exponential", "initial_delay": 0.1},
            "is_active": True
        }

        context = {
            "status": "completed",
            "result": "All tasks finished successfully",
            "orchestration_id": "orch-456"
        }

        with patch.object(executor, '_load_action', return_value=action), \
             patch.object(executor, '_record_execution', return_value="exec-789"), \
             patch('httpx.AsyncClient') as mock_client_class:

            # Setup mock HTTP client
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json = AsyncMock(return_value={"ok": True})
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await executor.execute_action(
                action_id="webhook-action",
                context=context,
                user_id="user-789",
                orchestration_id="orch-456",
                trigger_event="orchestration.completed"
            )

            assert result.status == "success"
            assert result.condition_met is True
            assert result.execution_id == "exec-789"

    @pytest.mark.asyncio
    async def test_conditional_skip_flow(self, executor):
        """Test action that gets skipped due to condition."""
        action = {
            "id": "conditional-action",
            "name": "failure_alert",
            "action_type": "email",
            "endpoint": "oncall@example.com",
            "body_template": {
                "subject": "Orchestration Failed",
                "body": "Error: {{error}}"
            },
            "condition_expression": "status == 'failed'",
            "is_active": True
        }

        context = {
            "status": "completed",  # Not failed!
            "result": "Success"
        }

        with patch.object(executor, '_load_action', return_value=action), \
             patch.object(executor, '_record_execution', return_value="exec-skip"):

            result = await executor.execute_action(
                action_id="conditional-action",
                context=context,
                user_id="user-123",
                trigger_event="orchestration.completed"
            )

            assert result.status == "skipped"
            assert result.condition_met is False
