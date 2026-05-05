"""
Stream Manager Service

Manages SSE streaming connections and handles cleanup on disconnection.
Prevents system hangs when clients disconnect during agent processing.
"""

import asyncio
import logging
from typing import Dict, Set, Optional
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class StreamConnection:
    """Represents an active SSE streaming connection"""

    def __init__(self, session_id: str, connection_id: str):
        self.session_id = session_id
        self.connection_id = connection_id
        self.started_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.is_cancelled = False
        self._cancellation_event = asyncio.Event()

    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.utcnow()

    def cancel(self):
        """Mark connection as cancelled and signal cancellation event"""
        self.is_cancelled = True
        self._cancellation_event.set()
        logger.info(f"Stream {self.connection_id} for session {self.session_id} marked as cancelled")

    async def wait_for_cancellation(self, timeout: float = 0.1):
        """Wait for cancellation signal with timeout"""
        try:
            await asyncio.wait_for(self._cancellation_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    def is_stale(self, max_age_seconds: int = 300) -> bool:
        """Check if connection is stale (no activity for max_age_seconds)"""
        return (datetime.utcnow() - self.last_activity).total_seconds() > max_age_seconds


class StreamManager:
    """
    Manages active SSE streaming connections and provides cleanup on disconnection.

    Features:
    - Track active streaming connections per session
    - Cancel streams when clients disconnect
    - Clean up stale connections
    - Prevent resource leaks
    """

    def __init__(self):
        self._connections: Dict[str, StreamConnection] = {}
        self._session_connections: Dict[str, Set[str]] = {}  # session_id -> set of connection_ids
        self._cleanup_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def start(self):
        """Start background cleanup task"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_stale_connections())
            logger.info("StreamManager: Started background cleanup task")

    async def stop(self):
        """Stop background cleanup task"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("StreamManager: Stopped background cleanup task")

    @asynccontextmanager
    async def create_stream(self, session_id: str, connection_id: Optional[str] = None):
        """
        Context manager for creating and managing a stream connection.

        Usage:
            async with stream_manager.create_stream(session_id) as stream:
                # Check if stream is cancelled periodically
                if stream.is_cancelled:
                    break
                # ... yield events ...
        """
        if connection_id is None:
            connection_id = f"{session_id}_{datetime.utcnow().timestamp()}"

        stream = StreamConnection(session_id, connection_id)

        async with self._lock:
            # Cancel any existing streams for this session (only allow one active stream per session)
            if session_id in self._session_connections:
                for old_conn_id in list(self._session_connections[session_id]):
                    if old_conn_id in self._connections:
                        self._connections[old_conn_id].cancel()
                        logger.info(f"Cancelled old stream {old_conn_id} for session {session_id}")

            # Register new stream
            self._connections[connection_id] = stream
            if session_id not in self._session_connections:
                self._session_connections[session_id] = set()
            self._session_connections[session_id].add(connection_id)

        logger.info(f"Created stream {connection_id} for session {session_id}")

        try:
            yield stream
        finally:
            # Cleanup on exit
            await self._remove_stream(connection_id)
            logger.info(f"Cleaned up stream {connection_id} for session {session_id}")

    async def cancel_session_streams(self, session_id: str):
        """Cancel all streams for a given session"""
        async with self._lock:
            if session_id in self._session_connections:
                for conn_id in list(self._session_connections[session_id]):
                    if conn_id in self._connections:
                        self._connections[conn_id].cancel()
                logger.info(f"Cancelled all streams for session {session_id}")

    async def _remove_stream(self, connection_id: str):
        """Remove stream from tracking"""
        async with self._lock:
            if connection_id in self._connections:
                stream = self._connections[connection_id]
                session_id = stream.session_id

                del self._connections[connection_id]

                if session_id in self._session_connections:
                    self._session_connections[session_id].discard(connection_id)
                    if not self._session_connections[session_id]:
                        del self._session_connections[session_id]

    async def _cleanup_stale_connections(self):
        """Background task to clean up stale connections"""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute

                async with self._lock:
                    stale_connections = [
                        conn_id for conn_id, stream in self._connections.items()
                        if stream.is_stale(max_age_seconds=300)  # 5 minutes
                    ]

                    for conn_id in stale_connections:
                        stream = self._connections[conn_id]
                        stream.cancel()
                        logger.warning(f"Cancelled stale stream {conn_id} for session {stream.session_id}")
                        await self._remove_stream(conn_id)

                    if stale_connections:
                        logger.info(f"Cleaned up {len(stale_connections)} stale connections")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")


# Global stream manager instance
_stream_manager: Optional[StreamManager] = None


def get_stream_manager() -> StreamManager:
    """Get or create the global stream manager instance"""
    global _stream_manager
    if _stream_manager is None:
        _stream_manager = StreamManager()
    return _stream_manager


async def start_stream_manager():
    """Initialize and start the stream manager (call on app startup)"""
    manager = get_stream_manager()
    await manager.start()
    logger.info("Stream manager started")


async def stop_stream_manager():
    """Stop the stream manager (call on app shutdown)"""
    global _stream_manager
    if _stream_manager:
        await _stream_manager.stop()
        _stream_manager = None
        logger.info("Stream manager stopped")
