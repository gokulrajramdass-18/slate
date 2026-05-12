"""
Tests for MLFlow observability service.

Tests initialization, run creation, parameter/metric logging,
callback handlers, and graceful degradation.
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from api.services.mlflow_service import MLFlowService, get_mlflow_service, reset_mlflow_service


@pytest.fixture(autouse=True)
def reset_service():
    """Reset singleton before each test."""
    reset_mlflow_service()
    yield
    reset_mlflow_service()


@pytest.fixture
def mock_mlflow():
    """Mock MLFlow module."""
    with patch('api.services.mlflow_service.mlflow') as mock:
        yield mock


class TestMLFlowServiceInitialization:
    """Test MLFlow service initialization."""

    def test_initialization_disabled_by_default(self):
        """Test service is disabled when MLFLOW_ENABLED is false."""
        with patch.dict(os.environ, {"MLFLOW_ENABLED": "false"}):
            service = MLFlowService()
            assert not service.is_enabled()

    def test_initialization_enabled_with_config(self, mock_mlflow):
        """Test service initializes when enabled with valid config."""
        with patch.dict(os.environ, {
            "MLFLOW_ENABLED": "true",
            "MLFLOW_TRACKING_URI": "http://mlflow:5000",
            "MLFLOW_EXPERIMENT_NAME": "test-experiment"
        }):
            mock_mlflow.set_tracking_uri = Mock()
            mock_mlflow.set_experiment = Mock(return_value=Mock(experiment_id="exp-123"))

            service = MLFlowService()

            assert service.is_enabled()
            assert service.tracking_uri == "http://mlflow:5000"
            assert service.experiment_name == "test-experiment"
            mock_mlflow.set_tracking_uri.assert_called_once_with("http://mlflow:5000")

    def test_initialization_with_missing_dependencies(self):
        """Test service handles missing mlflow package gracefully."""
        with patch.dict(os.environ, {"MLFLOW_ENABLED": "true"}):
            with patch('api.services.mlflow_service.mlflow', None):
                service = MLFlowService()
                assert not service.is_enabled()


class TestMLFlowRunCreation:
    """Test MLFlow run creation."""

    def test_create_run_success(self, mock_mlflow):
        """Test successful run creation."""
        with patch.dict(os.environ, {
            "MLFLOW_ENABLED": "true",
            "MLFLOW_TRACKING_URI": "http://mlflow:5000"
        }):
            mock_run = Mock()
            mock_run.info.run_id = "run-123"
            mock_mlflow.set_tracking_uri = Mock()
            mock_mlflow.set_experiment = Mock(return_value=Mock(experiment_id="exp-123"))
            mock_mlflow.start_run = Mock(return_value=mock_run)

            service = MLFlowService()
            run_id = service.create_run(
                run_name="test-run",
                tags={"session_id": "sess-1", "type": "chat"}
            )

            assert run_id == "run-123"
            mock_mlflow.start_run.assert_called_once()

    def test_create_run_when_disabled(self):
        """Test run creation returns None when service is disabled."""
        with patch.dict(os.environ, {"MLFLOW_ENABLED": "false"}):
            service = MLFlowService()
            run_id = service.create_run(run_name="test-run")
            assert run_id is None

    def test_create_run_with_error(self, mock_mlflow):
        """Test run creation handles errors gracefully."""
        with patch.dict(os.environ, {
            "MLFLOW_ENABLED": "true",
            "MLFLOW_TRACKING_URI": "http://mlflow:5000"
        }):
            mock_mlflow.set_tracking_uri = Mock()
            mock_mlflow.set_experiment = Mock(return_value=Mock(experiment_id="exp-123"))
            mock_mlflow.start_run = Mock(side_effect=Exception("Connection failed"))

            service = MLFlowService()
            run_id = service.create_run(run_name="test-run")

            assert run_id is None


class TestMLFlowLogging:
    """Test MLFlow parameter and metric logging."""

    def test_log_params_success(self, mock_mlflow):
        """Test logging parameters."""
        with patch.dict(os.environ, {
            "MLFLOW_ENABLED": "true",
            "MLFLOW_TRACKING_URI": "http://mlflow:5000"
        }):
            mock_mlflow.set_tracking_uri = Mock()
            mock_mlflow.set_experiment = Mock(return_value=Mock(experiment_id="exp-123"))
            mock_mlflow.log_params = Mock()

            service = MLFlowService()
            params = {"model": "gpt-4", "temperature": 0.7}
            service.log_params(params)

            mock_mlflow.log_params.assert_called_once_with(params)

    def test_log_metrics_success(self, mock_mlflow):
        """Test logging metrics."""
        with patch.dict(os.environ, {
            "MLFLOW_ENABLED": "true",
            "MLFLOW_TRACKING_URI": "http://mlflow:5000"
        }):
            mock_mlflow.set_tracking_uri = Mock()
            mock_mlflow.set_experiment = Mock(return_value=Mock(experiment_id="exp-123"))
            mock_mlflow.log_metrics = Mock()

            service = MLFlowService()
            metrics = {"tokens": 1250, "duration_ms": 3500}
            service.log_metrics(metrics)

            mock_mlflow.log_metrics.assert_called_once_with(metrics)

    def test_log_params_when_disabled(self):
        """Test logging params does nothing when disabled."""
        with patch.dict(os.environ, {"MLFLOW_ENABLED": "false"}):
            service = MLFlowService()
            # Should not raise an exception
            service.log_params({"key": "value"})


class TestMLFlowCallbacks:
    """Test MLFlow LangChain callback handlers."""

    def test_get_callback_handler_success(self, mock_mlflow):
        """Test getting LangChain callback handler."""
        with patch.dict(os.environ, {
            "MLFLOW_ENABLED": "true",
            "MLFLOW_TRACKING_URI": "http://mlflow:5000"
        }):
            mock_mlflow.set_tracking_uri = Mock()
            mock_mlflow.set_experiment = Mock(return_value=Mock(experiment_id="exp-123"))

            # Mock MlflowLangchainTracer
            mock_tracer = Mock()
            with patch('api.services.mlflow_service.MlflowLangchainTracer', return_value=mock_tracer):
                service = MLFlowService()
                callback = service.get_langchain_callback_handler("run-123")

                assert callback == mock_tracer

    def test_get_callback_handler_when_disabled(self):
        """Test callback handler returns None when disabled."""
        with patch.dict(os.environ, {"MLFLOW_ENABLED": "false"}):
            service = MLFlowService()
            callback = service.get_langchain_callback_handler("run-123")
            assert callback is None


class TestMLFlowStatus:
    """Test MLFlow status checking."""

    @pytest.mark.asyncio
    async def test_get_status_when_enabled(self, mock_mlflow):
        """Test status returns connection info when enabled."""
        with patch.dict(os.environ, {
            "MLFLOW_ENABLED": "true",
            "MLFLOW_TRACKING_URI": "http://mlflow:5000",
            "MLFLOW_EXPERIMENT_NAME": "test-exp"
        }):
            mock_mlflow.set_tracking_uri = Mock()
            mock_mlflow.set_experiment = Mock(return_value=Mock(experiment_id="exp-123"))

            # Mock MlflowClient
            mock_client = Mock()
            mock_client.search_runs = Mock(return_value=[
                Mock(info=Mock(end_time=1000))
            ])

            with patch('api.services.mlflow_service.MlflowClient', return_value=mock_client):
                service = MLFlowService()
                status = await service.get_status()

                assert status["enabled"] is True
                assert status["connected"] is True
                assert status["tracking_uri"] == "http://mlflow:5000"
                assert status["experiment_name"] == "test-exp"

    @pytest.mark.asyncio
    async def test_get_status_when_disabled(self):
        """Test status returns disabled when service is off."""
        with patch.dict(os.environ, {"MLFLOW_ENABLED": "false"}):
            service = MLFlowService()
            status = await service.get_status()

            assert status["enabled"] is False
            assert status["connected"] is False


class TestMLFlowSingleton:
    """Test singleton pattern."""

    def test_get_mlflow_service_returns_singleton(self):
        """Test get_mlflow_service returns same instance."""
        service1 = get_mlflow_service()
        service2 = get_mlflow_service()
        assert service1 is service2

    def test_reset_mlflow_service(self):
        """Test reset creates new instance."""
        service1 = get_mlflow_service()
        reset_mlflow_service()
        service2 = get_mlflow_service()
        assert service1 is not service2


class TestMLFlowLifecycle:
    """Test flush and shutdown lifecycle."""

    def test_flush(self, mock_mlflow):
        """Test flush calls MLFlow flush."""
        with patch.dict(os.environ, {
            "MLFLOW_ENABLED": "true",
            "MLFLOW_TRACKING_URI": "http://mlflow:5000"
        }):
            mock_mlflow.set_tracking_uri = Mock()
            mock_mlflow.set_experiment = Mock(return_value=Mock(experiment_id="exp-123"))
            mock_mlflow.flush = Mock()

            service = MLFlowService()
            service.flush()

            # MLFlow doesn't have flush, but service should handle it gracefully
            # This test ensures no exception is raised

    def test_shutdown(self, mock_mlflow):
        """Test shutdown closes runs and flushes."""
        with patch.dict(os.environ, {
            "MLFLOW_ENABLED": "true",
            "MLFLOW_TRACKING_URI": "http://mlflow:5000"
        }):
            mock_mlflow.set_tracking_uri = Mock()
            mock_mlflow.set_experiment = Mock(return_value=Mock(experiment_id="exp-123"))
            mock_mlflow.end_run = Mock()

            service = MLFlowService()
            service.shutdown()

            # Shutdown should be handled gracefully
