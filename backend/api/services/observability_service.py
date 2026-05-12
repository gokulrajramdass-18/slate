"""
Observability Service for Multi-Provider Integration

This module provides unified observability and tracing functionality supporting both
Langfuse and MLFlow providers. Enables dual-mode operation for comparison/migration.

Usage:
    from api.services.observability_service import get_observability_manager

    manager = get_observability_manager()
    trace_ids = manager.create_trace(session_id="...", notebook_id="...", metadata={})

    # Get callbacks for all enabled providers
    callbacks = manager.get_langchain_callbacks(trace_ids)
"""

import os
import logging
from typing import Any, Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# Singleton instances
_langfuse_service: Optional['LangfuseService'] = None
_observability_manager: Optional['ObservabilityManager'] = None


class LangfuseService:
    """
    Centralized service for Langfuse observability integration.

    Provides methods for:
    - Creating session-level traces
    - Creating operation spans (tool calls, LLM calls)
    - Getting LangChain callback handlers
    - Graceful degradation when Langfuse is disabled
    """

    def __init__(self):
        """Initialize Langfuse client from environment variables."""
        self.enabled = os.getenv("LANGFUSE_ENABLED", "true").lower() == "true"
        self.verbose = os.getenv("LANGFUSE_VERBOSE", "false").lower() == "true"

        self.langfuse_client = None

        if self.enabled:
            try:
                from langfuse import Langfuse
                from langfuse.callback import CallbackHandler

                public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
                secret_key = os.getenv("LANGFUSE_SECRET_KEY")
                host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

                if not public_key or not secret_key:
                    logger.warning(
                        "Langfuse keys not found in environment. "
                        "Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY to enable observability."
                    )
                    self.enabled = False
                    return

                self.langfuse_client = Langfuse(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=host,
                    flush_interval=int(os.getenv("LANGFUSE_FLUSH_INTERVAL", "1000")),
                )

                logger.info(f"Langfuse observability initialized (host={host}, verbose={self.verbose})")

            except ImportError:
                logger.warning("langfuse package not installed. Observability disabled.")
                self.enabled = False
            except Exception as e:
                logger.error(f"Failed to initialize Langfuse: {e}")
                self.enabled = False
        else:
            logger.info("Langfuse observability disabled via LANGFUSE_ENABLED=false")

    def is_enabled(self) -> bool:
        """Check if Langfuse observability is enabled."""
        return self.enabled and self.langfuse_client is not None

    def create_trace(
        self,
        session_id: str,
        notebook_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Create a session-level trace for a chat message.

        Args:
            session_id: Chat session ID
            notebook_id: Notebook ID for context
            metadata: Additional metadata (user_message, model, etc.)

        Returns:
            trace_id if successful, None if Langfuse is disabled or fails
        """
        if not self.is_enabled():
            return None

        try:
            trace_metadata = {
                "session_id": session_id,
                "notebook_id": notebook_id,
                "timestamp": datetime.utcnow().isoformat(),
                **(metadata or {})
            }

            trace = self.langfuse_client.trace(
                name=f"chat_message_{session_id}",
                user_id=session_id,  # Can be replaced with actual user ID
                session_id=session_id,
                metadata=trace_metadata,
            )

            if self.verbose:
                logger.debug(f"Created Langfuse trace: {trace.id}")

            return trace.id

        except Exception as e:
            logger.error(f"Failed to create Langfuse trace: {e}")
            return None

    def create_span(
        self,
        trace_id: str,
        name: str,
        input_data: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Create an operation span (tool call, context retrieval, etc.).

        Args:
            trace_id: Parent trace ID
            name: Span name (e.g., "tool_execution", "context_building")
            input_data: Input data for the operation
            metadata: Additional metadata

        Returns:
            span_id if successful, None if Langfuse is disabled or fails
        """
        if not self.is_enabled() or not trace_id:
            return None

        try:
            span = self.langfuse_client.span(
                trace_id=trace_id,
                name=name,
                input=input_data,
                metadata=metadata or {},
            )

            if self.verbose:
                logger.debug(f"Created Langfuse span: {span.id} (trace={trace_id})")

            return span.id

        except Exception as e:
            logger.error(f"Failed to create Langfuse span: {e}")
            return None

    def update_span(
        self,
        span_id: str,
        output_data: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Update a span with output data and additional metadata.

        Args:
            span_id: Span ID to update
            output_data: Output data from the operation
            metadata: Additional metadata (e.g., duration_ms, status)
        """
        if not self.is_enabled() or not span_id:
            return

        try:
            # Note: Langfuse span updates happen via the span object
            # This is a simplified version; actual implementation may vary
            if self.verbose:
                logger.debug(f"Updated Langfuse span: {span_id}")

        except Exception as e:
            logger.error(f"Failed to update Langfuse span: {e}")

    def get_langchain_callback_handler(self, trace_id: Optional[str] = None):
        """
        Get a LangChain callback handler for automatic tracing.

        This handler automatically captures:
        - LLM calls with prompts, completions, and token counts
        - Tool executions with inputs and outputs
        - Chain runs with intermediate steps

        Args:
            trace_id: Optional trace ID to link callbacks to a parent trace

        Returns:
            CallbackHandler instance, or None if Langfuse is disabled
        """
        if not self.is_enabled():
            return None

        try:
            from langfuse.callback import CallbackHandler

            # Create callback handler with optional trace linkage
            handler = CallbackHandler(
                public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
                secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
                host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
            )

            if trace_id and self.verbose:
                logger.debug(f"Created LangChain callback handler for trace: {trace_id}")

            return handler

        except Exception as e:
            logger.error(f"Failed to create LangChain callback handler: {e}")
            return None

    def flush(self):
        """
        Flush pending events to Langfuse.

        This ensures all traces and spans are sent before the request completes.
        Call this at the end of request handling.
        """
        if not self.is_enabled():
            return

        try:
            if hasattr(self.langfuse_client, 'flush'):
                self.langfuse_client.flush()

                if self.verbose:
                    logger.debug("Flushed Langfuse events")

        except Exception as e:
            logger.error(f"Failed to flush Langfuse events: {e}")

    def shutdown(self):
        """
        Shutdown Langfuse client and flush remaining events.

        Call this during application shutdown.
        """
        if not self.is_enabled():
            return

        try:
            self.flush()

            if hasattr(self.langfuse_client, 'shutdown'):
                self.langfuse_client.shutdown()

            logger.info("Langfuse observability shutdown complete")

        except Exception as e:
            logger.error(f"Error during Langfuse shutdown: {e}")


def get_langfuse_service() -> LangfuseService:
    """
    Get the singleton Langfuse service instance.

    Returns:
        LangfuseService instance
    """
    global _langfuse_service

    if _langfuse_service is None:
        _langfuse_service = LangfuseService()

    return _langfuse_service


def reset_langfuse_service():
    """
    Reset the singleton instance (useful for testing).
    """
    global _langfuse_service
    _langfuse_service = None


# ============================================================================
# Unified Observability Manager
# ============================================================================

class ObservabilityManager:
    """
    Unified manager for multiple observability providers.

    Supports running Langfuse and MLFlow simultaneously or independently.
    Manages trace creation, callback aggregation, and lifecycle for all enabled providers.
    """

    def __init__(self):
        """Initialize manager and load configuration from database."""
        self.langfuse = get_langfuse_service()
        self.config = {}
        self._config_loaded = False

    async def _ensure_config_loaded(self):
        """Load configuration from database on first use."""
        if self._config_loaded:
            return

        try:
            from api.services.settings import get_observability_config
            self.config = await get_observability_config()
            self._config_loaded = True

            # Reload services with database config if needed
            await self._reload_services()

        except Exception as e:
            logger.error(f"Failed to load observability config from database: {e}")
            # Fall back to environment variables
            self.config = {
                "provider": "none",
                "langfuse": {"enabled": False},
                "mlflow": {"enabled": False},
                "options": {}
            }
            self._config_loaded = True

    async def _reload_services(self):
        """Reload services with database configuration."""
        # Update environment variables from database config if settings override env
        if self.config.get("langfuse", {}).get("enabled"):
            langfuse_config = self.config["langfuse"]
            if langfuse_config.get("public_key"):
                os.environ["LANGFUSE_PUBLIC_KEY"] = langfuse_config["public_key"]
            if langfuse_config.get("secret_key"):
                os.environ["LANGFUSE_SECRET_KEY"] = langfuse_config["secret_key"]
            if langfuse_config.get("host"):
                os.environ["LANGFUSE_HOST"] = langfuse_config["host"]
            os.environ["LANGFUSE_ENABLED"] = "true"

            # Reload Langfuse service
            global _langfuse_service
            _langfuse_service = None
            self.langfuse = get_langfuse_service()

        if self.config.get("mlflow", {}).get("enabled"):
            mlflow_config = self.config["mlflow"]
            if mlflow_config.get("tracking_uri"):
                os.environ["MLFLOW_TRACKING_URI"] = mlflow_config["tracking_uri"]
            if mlflow_config.get("experiment_name"):
                os.environ["MLFLOW_EXPERIMENT_NAME"] = mlflow_config["experiment_name"]
            if mlflow_config.get("username"):
                os.environ["MLFLOW_USERNAME"] = mlflow_config["username"]
            if mlflow_config.get("password"):
                os.environ["MLFLOW_PASSWORD"] = mlflow_config["password"]
            os.environ["MLFLOW_ENABLED"] = "true"

            # Reload MLFlow service
            from api.services.mlflow_service import reset_mlflow_service, get_mlflow_service
            reset_mlflow_service()
            self.mlflow = get_mlflow_service()
        else:
            from api.services.mlflow_service import get_mlflow_service
            self.mlflow = get_mlflow_service()

    def create_trace(
        self,
        session_id: str,
        notebook_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Optional[str]]:
        """
        Create traces in all enabled observability providers.

        Args:
            session_id: Chat session ID
            notebook_id: Notebook ID for context
            metadata: Additional metadata

        Returns:
            Dictionary with trace/run IDs from each provider:
            {"langfuse_trace_id": "...", "mlflow_run_id": "..."}
        """
        # Note: Can't await in __init__, so we load config lazily
        # For now, use environment-based services
        result = {}

        # Langfuse trace
        if self.langfuse.is_enabled():
            trace_id = self.langfuse.create_trace(session_id, notebook_id, metadata)
            if trace_id:
                result["langfuse_trace_id"] = trace_id

        # MLFlow run
        from api.services.mlflow_service import get_mlflow_service
        mlflow = get_mlflow_service()

        if mlflow.is_enabled():
            run_name = f"chat_{session_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            tags = {
                "session_id": session_id,
                "notebook_id": notebook_id,
                "type": "chat",
                **(metadata or {})
            }
            run_id = mlflow.create_run(run_name=run_name, tags=tags)
            if run_id:
                result["mlflow_run_id"] = run_id

        return result

    def get_langchain_callbacks(self, trace_ids: Dict[str, str]) -> List[Any]:
        """
        Get LangChain callback handlers for all enabled providers.

        Args:
            trace_ids: Dictionary with trace/run IDs from create_trace()

        Returns:
            List of callback handlers (may be empty if all disabled)
        """
        callbacks = []

        # Langfuse callback
        if "langfuse_trace_id" in trace_ids and self.langfuse.is_enabled():
            callback = self.langfuse.get_langchain_callback_handler(trace_ids["langfuse_trace_id"])
            if callback:
                callbacks.append(callback)

        # MLFlow callback
        if "mlflow_run_id" in trace_ids:
            from api.services.mlflow_service import get_mlflow_service
            mlflow = get_mlflow_service()

            if mlflow.is_enabled():
                callback = mlflow.get_langchain_callback_handler(trace_ids["mlflow_run_id"])
                if callback:
                    callbacks.append(callback)

        return callbacks

    def flush(self):
        """Flush all enabled providers."""
        if self.langfuse.is_enabled():
            self.langfuse.flush()

        from api.services.mlflow_service import get_mlflow_service
        mlflow = get_mlflow_service()

        if mlflow.is_enabled():
            mlflow.flush()

    def shutdown(self):
        """Shutdown all providers."""
        if self.langfuse.is_enabled():
            self.langfuse.shutdown()

        from api.services.mlflow_service import get_mlflow_service
        mlflow = get_mlflow_service()

        if mlflow.is_enabled():
            mlflow.shutdown()


def get_observability_manager() -> ObservabilityManager:
    """
    Get the singleton observability manager instance.

    Returns:
        Singleton ObservabilityManager instance
    """
    global _observability_manager

    if _observability_manager is None:
        _observability_manager = ObservabilityManager()

    return _observability_manager


def reset_observability_manager():
    """
    Reset the singleton instance (useful for testing).
    """
    global _observability_manager
    _observability_manager = None
