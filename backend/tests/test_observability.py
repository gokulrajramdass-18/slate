"""
Tests for Langfuse Observability Service

Tests the observability service integration including:
- Service initialization
- Trace creation
- Graceful degradation when disabled
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from api.services.observability_service import LangfuseService, get_langfuse_service, reset_langfuse_service


class TestLangfuseService:
    """Test suite for LangfuseService"""

    def setup_method(self):
        """Reset service before each test"""
        reset_langfuse_service()

    def teardown_method(self):
        """Clean up after each test"""
        reset_langfuse_service()

    def test_service_initialization_disabled(self):
        """Test that service initializes correctly when disabled"""
        with patch.dict(os.environ, {"LANGFUSE_ENABLED": "false"}):
            service = LangfuseService()
            assert service.enabled is False
            assert service.langfuse_client is None
            assert service.is_enabled() is False

    def test_service_initialization_no_keys(self):
        """Test that service disables when keys are missing"""
        with patch.dict(os.environ, {
            "LANGFUSE_ENABLED": "true",
            "LANGFUSE_PUBLIC_KEY": "",
            "LANGFUSE_SECRET_KEY": ""
        }, clear=True):
            service = LangfuseService()
            assert service.enabled is False
            assert service.is_enabled() is False

    @patch('api.services.observability_service.Langfuse')
    def test_service_initialization_with_keys(self, mock_langfuse):
        """Test that service initializes correctly with valid keys"""
        mock_client = MagicMock()
        mock_langfuse.return_value = mock_client

        with patch.dict(os.environ, {
            "LANGFUSE_ENABLED": "true",
            "LANGFUSE_PUBLIC_KEY": "pk-test",
            "LANGFUSE_SECRET_KEY": "sk-test",
            "LANGFUSE_HOST": "https://test.langfuse.com"
        }):
            service = LangfuseService()
            assert service.is_enabled() is True
            assert service.langfuse_client == mock_client
            mock_langfuse.assert_called_once()

    def test_create_trace_when_disabled(self):
        """Test that create_trace returns None when disabled"""
        with patch.dict(os.environ, {"LANGFUSE_ENABLED": "false"}):
            service = LangfuseService()
            trace_id = service.create_trace(
                session_id="test-session",
                notebook_id="test-notebook",
                metadata={"test": True}
            )
            assert trace_id is None

    @patch('api.services.observability_service.Langfuse')
    def test_create_trace_when_enabled(self, mock_langfuse):
        """Test that create_trace returns trace_id when enabled"""
        mock_client = MagicMock()
        mock_trace = MagicMock()
        mock_trace.id = "trace-123"
        mock_client.trace.return_value = mock_trace
        mock_langfuse.return_value = mock_client

        with patch.dict(os.environ, {
            "LANGFUSE_ENABLED": "true",
            "LANGFUSE_PUBLIC_KEY": "pk-test",
            "LANGFUSE_SECRET_KEY": "sk-test"
        }):
            service = LangfuseService()
            trace_id = service.create_trace(
                session_id="test-session",
                notebook_id="test-notebook",
                metadata={"user_message": "test"}
            )
            assert trace_id == "trace-123"
            mock_client.trace.assert_called_once()

    @patch('api.services.observability_service.Langfuse')
    def test_create_trace_handles_exceptions(self, mock_langfuse):
        """Test that create_trace handles exceptions gracefully"""
        mock_client = MagicMock()
        mock_client.trace.side_effect = Exception("Test error")
        mock_langfuse.return_value = mock_client

        with patch.dict(os.environ, {
            "LANGFUSE_ENABLED": "true",
            "LANGFUSE_PUBLIC_KEY": "pk-test",
            "LANGFUSE_SECRET_KEY": "sk-test"
        }):
            service = LangfuseService()
            # Should not raise exception
            trace_id = service.create_trace(
                session_id="test-session",
                notebook_id="test-notebook",
                metadata={}
            )
            assert trace_id is None

    def test_create_span_when_disabled(self):
        """Test that create_span returns None when disabled"""
        with patch.dict(os.environ, {"LANGFUSE_ENABLED": "false"}):
            service = LangfuseService()
            span_id = service.create_span(
                trace_id="trace-123",
                name="test_operation",
                input_data={"test": "data"},
                metadata={}
            )
            assert span_id is None

    @patch('api.services.observability_service.Langfuse')
    def test_get_langchain_callback_when_disabled(self, mock_langfuse):
        """Test that callback handler returns None when disabled"""
        with patch.dict(os.environ, {"LANGFUSE_ENABLED": "false"}):
            service = LangfuseService()
            callback = service.get_langchain_callback_handler()
            assert callback is None

    @patch('api.services.observability_service.CallbackHandler')
    @patch('api.services.observability_service.Langfuse')
    def test_get_langchain_callback_when_enabled(self, mock_langfuse, mock_callback_handler):
        """Test that callback handler is created when enabled"""
        mock_client = MagicMock()
        mock_langfuse.return_value = mock_client
        mock_handler = MagicMock()
        mock_callback_handler.return_value = mock_handler

        with patch.dict(os.environ, {
            "LANGFUSE_ENABLED": "true",
            "LANGFUSE_PUBLIC_KEY": "pk-test",
            "LANGFUSE_SECRET_KEY": "sk-test"
        }):
            service = LangfuseService()
            callback = service.get_langchain_callback_handler("trace-123")
            assert callback == mock_handler
            mock_callback_handler.assert_called_once()

    @patch('api.services.observability_service.Langfuse')
    def test_flush_when_enabled(self, mock_langfuse):
        """Test that flush is called when enabled"""
        mock_client = MagicMock()
        mock_langfuse.return_value = mock_client

        with patch.dict(os.environ, {
            "LANGFUSE_ENABLED": "true",
            "LANGFUSE_PUBLIC_KEY": "pk-test",
            "LANGFUSE_SECRET_KEY": "sk-test"
        }):
            service = LangfuseService()
            service.flush()
            mock_client.flush.assert_called_once()

    def test_flush_when_disabled(self):
        """Test that flush does nothing when disabled"""
        with patch.dict(os.environ, {"LANGFUSE_ENABLED": "false"}):
            service = LangfuseService()
            # Should not raise exception
            service.flush()

    def test_singleton_pattern(self):
        """Test that get_langfuse_service returns singleton instance"""
        with patch.dict(os.environ, {"LANGFUSE_ENABLED": "false"}):
            service1 = get_langfuse_service()
            service2 = get_langfuse_service()
            assert service1 is service2

    def test_verbose_mode(self):
        """Test that verbose mode is correctly parsed"""
        with patch.dict(os.environ, {
            "LANGFUSE_ENABLED": "false",
            "LANGFUSE_VERBOSE": "true"
        }):
            service = LangfuseService()
            assert service.verbose is True

        reset_langfuse_service()

        with patch.dict(os.environ, {
            "LANGFUSE_ENABLED": "false",
            "LANGFUSE_VERBOSE": "false"
        }):
            service = LangfuseService()
            assert service.verbose is False


class TestObservabilityIntegration:
    """Integration tests for observability in chat flow"""

    def setup_method(self):
        """Reset service before each test"""
        reset_langfuse_service()

    def teardown_method(self):
        """Clean up after each test"""
        reset_langfuse_service()

    def test_service_works_without_langfuse_package(self):
        """Test that service gracefully handles missing langfuse package"""
        with patch.dict(os.environ, {"LANGFUSE_ENABLED": "true"}):
            with patch('builtins.__import__', side_effect=ImportError("No module named 'langfuse'")):
                # Should not raise exception during initialization
                service = LangfuseService()
                assert service.enabled is False

    @patch('api.services.observability_service.Langfuse')
    def test_trace_metadata_includes_session_info(self, mock_langfuse):
        """Test that trace metadata includes session information"""
        mock_client = MagicMock()
        mock_trace = MagicMock()
        mock_trace.id = "trace-123"
        mock_client.trace.return_value = mock_trace
        mock_langfuse.return_value = mock_client

        with patch.dict(os.environ, {
            "LANGFUSE_ENABLED": "true",
            "LANGFUSE_PUBLIC_KEY": "pk-test",
            "LANGFUSE_SECRET_KEY": "sk-test"
        }):
            service = LangfuseService()
            trace_id = service.create_trace(
                session_id="session-123",
                notebook_id="notebook-456",
                metadata={
                    "user_message": "test question",
                    "model": "gpt-4",
                    "tools_available": 5
                }
            )

            # Verify trace was created with correct metadata
            assert trace_id == "trace-123"
            call_kwargs = mock_client.trace.call_args.kwargs
            assert call_kwargs["session_id"] == "session-123"
            assert "user_message" in call_kwargs["metadata"]
            assert "model" in call_kwargs["metadata"]
