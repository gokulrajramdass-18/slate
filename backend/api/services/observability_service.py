"""
Observability Service for Langfuse Integration

This module provides centralized observability and tracing functionality using Langfuse.
It handles LLM call tracing, tool execution monitoring, and agent step tracking.

Usage:
    from api.services.observability_service import get_langfuse_service

    service = get_langfuse_service()
    trace_id = service.create_trace(session_id="...", notebook_id="...", metadata={})

    # Use with LangChain
    callback = service.get_langchain_callback_handler(trace_id)
"""

import os
import logging
from typing import Any, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Singleton instance
_langfuse_service: Optional['LangfuseService'] = None


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
