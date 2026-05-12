"""
Tests for unified observability manager.

Tests dual-provider mode, provider switching, callback aggregation,
and config loading.
"""

import os
import pytest
from unittest.mock import Mock, patch, AsyncMock
from api.services.observability_service import (
    ObservabilityManager,
    get_observability_manager,
    reset_observability_manager
)


@pytest.fixture(autouse=True)
def reset_manager():
    """Reset singleton before each test."""
    reset_observability_manager()
    yield
    reset_observability_manager()


@pytest.fixture
def mock_langfuse_service():
    """Mock Langfuse service."""
    with patch('api.services.observability_service.get_langfuse_service') as mock:
        service = Mock()
        service.is_enabled.return_value = True
        service.create_trace.return_value = "langfuse-trace-123"
        service.get_langchain_callback_handler.return_value = Mock(name="LangfuseCallback")
        service.flush = Mock()
        service.shutdown = Mock()
        mock.return_value = service
        yield service


@pytest.fixture
def mock_mlflow_service():
    """Mock MLFlow service."""
    with patch('api.services.mlflow_service.get_mlflow_service') as mock:
        service = Mock()
        service.is_enabled.return_value = True
        service.create_run.return_value = "mlflow-run-456"
        service.get_langchain_callback_handler.return_value = Mock(name="MLFlowCallback")
        service.flush = Mock()
        service.shutdown = Mock()
        mock.return_value = service
        yield service


class TestObservabilityManagerInitialization:
    """Test manager initialization."""

    def test_initialization(self, mock_langfuse_service, mock_mlflow_service):
        """Test manager initializes both services."""
        manager = ObservabilityManager()

        assert manager.langfuse == mock_langfuse_service
        assert not manager._config_loaded

    def test_singleton_pattern(self):
        """Test get_observability_manager returns singleton."""
        manager1 = get_observability_manager()
        manager2 = get_observability_manager()
        assert manager1 is manager2


class TestTraceCreation:
    """Test trace creation in multiple providers."""

    def test_create_trace_langfuse_only(self, mock_langfuse_service, mock_mlflow_service):
        """Test trace creation with Langfuse only."""
        mock_mlflow_service.is_enabled.return_value = False

        manager = ObservabilityManager()
        trace_ids = manager.create_trace(
            session_id="sess-1",
            notebook_id="nb-1",
            metadata={"user_message": "test"}
        )

        assert "langfuse_trace_id" in trace_ids
        assert trace_ids["langfuse_trace_id"] == "langfuse-trace-123"
        assert "mlflow_run_id" not in trace_ids

        mock_langfuse_service.create_trace.assert_called_once()
        mock_mlflow_service.create_run.assert_not_called()

    def test_create_trace_mlflow_only(self, mock_langfuse_service, mock_mlflow_service):
        """Test trace creation with MLFlow only."""
        mock_langfuse_service.is_enabled.return_value = False

        manager = ObservabilityManager()
        trace_ids = manager.create_trace(
            session_id="sess-1",
            notebook_id="nb-1",
            metadata={"user_message": "test"}
        )

        assert "mlflow_run_id" in trace_ids
        assert trace_ids["mlflow_run_id"] == "mlflow-run-456"
        assert "langfuse_trace_id" not in trace_ids

        mock_mlflow_service.create_run.assert_called_once()
        mock_langfuse_service.create_trace.assert_not_called()

    def test_create_trace_dual_mode(self, mock_langfuse_service, mock_mlflow_service):
        """Test trace creation with both providers enabled."""
        manager = ObservabilityManager()
        trace_ids = manager.create_trace(
            session_id="sess-1",
            notebook_id="nb-1",
            metadata={"user_message": "test"}
        )

        assert "langfuse_trace_id" in trace_ids
        assert "mlflow_run_id" in trace_ids
        assert trace_ids["langfuse_trace_id"] == "langfuse-trace-123"
        assert trace_ids["mlflow_run_id"] == "mlflow-run-456"

        mock_langfuse_service.create_trace.assert_called_once()
        mock_mlflow_service.create_run.assert_called_once()

    def test_create_trace_both_disabled(self, mock_langfuse_service, mock_mlflow_service):
        """Test trace creation when both providers are disabled."""
        mock_langfuse_service.is_enabled.return_value = False
        mock_mlflow_service.is_enabled.return_value = False

        manager = ObservabilityManager()
        trace_ids = manager.create_trace(
            session_id="sess-1",
            notebook_id="nb-1"
        )

        assert trace_ids == {}
        mock_langfuse_service.create_trace.assert_not_called()
        mock_mlflow_service.create_run.assert_not_called()


class TestCallbackAggregation:
    """Test LangChain callback aggregation."""

    def test_get_callbacks_dual_mode(self, mock_langfuse_service, mock_mlflow_service):
        """Test callback aggregation with both providers."""
        manager = ObservabilityManager()
        trace_ids = {
            "langfuse_trace_id": "trace-123",
            "mlflow_run_id": "run-456"
        }

        callbacks = manager.get_langchain_callbacks(trace_ids)

        assert len(callbacks) == 2
        mock_langfuse_service.get_langchain_callback_handler.assert_called_once_with("trace-123")
        mock_mlflow_service.get_langchain_callback_handler.assert_called_once_with("run-456")

    def test_get_callbacks_langfuse_only(self, mock_langfuse_service, mock_mlflow_service):
        """Test callbacks with Langfuse only."""
        mock_mlflow_service.is_enabled.return_value = False

        manager = ObservabilityManager()
        trace_ids = {"langfuse_trace_id": "trace-123"}

        callbacks = manager.get_langchain_callbacks(trace_ids)

        assert len(callbacks) == 1
        mock_langfuse_service.get_langchain_callback_handler.assert_called_once()

    def test_get_callbacks_empty(self, mock_langfuse_service, mock_mlflow_service):
        """Test callbacks with no trace IDs."""
        mock_langfuse_service.is_enabled.return_value = False
        mock_mlflow_service.is_enabled.return_value = False

        manager = ObservabilityManager()
        callbacks = manager.get_langchain_callbacks({})

        assert len(callbacks) == 0


class TestLifecycleOperations:
    """Test flush and shutdown operations."""

    def test_flush_both_providers(self, mock_langfuse_service, mock_mlflow_service):
        """Test flush calls both providers."""
        manager = ObservabilityManager()
        manager.flush()

        mock_langfuse_service.flush.assert_called_once()
        mock_mlflow_service.flush.assert_called_once()

    def test_flush_with_one_disabled(self, mock_langfuse_service, mock_mlflow_service):
        """Test flush when one provider is disabled."""
        mock_mlflow_service.is_enabled.return_value = False

        manager = ObservabilityManager()
        manager.flush()

        mock_langfuse_service.flush.assert_called_once()
        mock_mlflow_service.flush.assert_called_once()  # Still called, service handles it

    def test_shutdown_both_providers(self, mock_langfuse_service, mock_mlflow_service):
        """Test shutdown calls both providers."""
        manager = ObservabilityManager()
        manager.shutdown()

        mock_langfuse_service.shutdown.assert_called_once()
        mock_mlflow_service.shutdown.assert_called_once()


class TestConfigLoading:
    """Test configuration loading from database."""

    @pytest.mark.asyncio
    async def test_ensure_config_loaded(self, mock_langfuse_service, mock_mlflow_service):
        """Test config loading from database."""
        mock_config = {
            "provider": "both",
            "langfuse": {"enabled": True},
            "mlflow": {"enabled": True},
            "options": {}
        }

        with patch('api.services.observability_service.get_observability_config', new_callable=AsyncMock) as mock_get_config:
            mock_get_config.return_value = mock_config

            manager = ObservabilityManager()
            await manager._ensure_config_loaded()

            assert manager._config_loaded is True
            assert manager.config == mock_config
            mock_get_config.assert_called_once()

    @pytest.mark.asyncio
    async def test_config_loaded_once(self, mock_langfuse_service, mock_mlflow_service):
        """Test config is only loaded once."""
        mock_config = {"provider": "none"}

        with patch('api.services.observability_service.get_observability_config', new_callable=AsyncMock) as mock_get_config:
            mock_get_config.return_value = mock_config

            manager = ObservabilityManager()
            await manager._ensure_config_loaded()
            await manager._ensure_config_loaded()

            # Should only call once
            assert mock_get_config.call_count == 1

    @pytest.mark.asyncio
    async def test_config_load_error_fallback(self, mock_langfuse_service, mock_mlflow_service):
        """Test config loading falls back on error."""
        with patch('api.services.observability_service.get_observability_config', new_callable=AsyncMock) as mock_get_config:
            mock_get_config.side_effect = Exception("Database error")

            manager = ObservabilityManager()
            await manager._ensure_config_loaded()

            # Should fallback to default config
            assert manager._config_loaded is True
            assert manager.config["provider"] == "none"


class TestProviderReload:
    """Test service reloading with database config."""

    @pytest.mark.asyncio
    async def test_reload_services_with_langfuse_config(self, mock_langfuse_service):
        """Test reloading Langfuse service with database config."""
        mock_config = {
            "provider": "langfuse",
            "langfuse": {
                "enabled": True,
                "public_key": "pk-test",
                "secret_key": "sk-test",
                "host": "https://custom.langfuse.com"
            },
            "mlflow": {"enabled": False},
            "options": {}
        }

        with patch('api.services.observability_service.get_observability_config', new_callable=AsyncMock) as mock_get_config:
            mock_get_config.return_value = mock_config

            manager = ObservabilityManager()
            await manager._ensure_config_loaded()

            # Environment should be updated
            assert os.environ.get("LANGFUSE_PUBLIC_KEY") == "pk-test"
            assert os.environ.get("LANGFUSE_SECRET_KEY") == "sk-test"
            assert os.environ.get("LANGFUSE_HOST") == "https://custom.langfuse.com"
