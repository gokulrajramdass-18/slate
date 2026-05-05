"""
Rate Limiter for Tool Execution

Provides a sliding window rate limiter that wraps any LangChain BaseTool
to enforce per-user call limits per minute.
"""

import time
from collections import defaultdict
from typing import Type

from langchain.tools import BaseTool
from pydantic import BaseModel


# Global sliding window tracker: {(user_id, tool_name): [timestamps]}
_call_timestamps: dict = defaultdict(list)


def _cleanup_window(key: tuple, window_seconds: int = 60) -> list:
    """Remove timestamps outside the sliding window."""
    now = time.monotonic()
    cutoff = now - window_seconds
    _call_timestamps[key] = [
        ts for ts in _call_timestamps[key] if ts > cutoff
    ]
    return _call_timestamps[key]


class RateLimitedTool(BaseTool):
    """
    Wraps any BaseTool with sliding window rate limiting per user.

    Tracks calls per user per minute using an in-memory sliding window.
    Raises ValueError when the limit is exceeded.
    """

    name: str = ""
    description: str = ""
    args_schema: Type[BaseModel] = None

    # Internal fields
    _inner_tool: BaseTool = None
    _calls_per_minute: int = 60
    _user_id: str = ""

    class Config:
        arbitrary_types_allowed = True
        underscore_attrs_are_private = True

    def __init__(
        self,
        tool: BaseTool,
        calls_per_minute: int,
        user_id: str = "",
    ):
        # Forward the wrapped tool's public interface
        super().__init__(
            name=tool.name,
            description=tool.description,
            args_schema=tool.args_schema,
        )
        self._inner_tool = tool
        self._calls_per_minute = calls_per_minute
        self._user_id = user_id

    # Expose the inner tool's custom attributes (source_id, table_name, etc.)
    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._inner_tool, name)

    def _check_rate_limit(self) -> None:
        """Check and enforce the sliding window rate limit."""
        key = (self._user_id, self.name)
        recent = _cleanup_window(key)

        if len(recent) >= self._calls_per_minute:
            raise ValueError(
                f"Rate limit exceeded for tool '{self.name}': "
                f"{self._calls_per_minute} calls/minute"
            )

        _call_timestamps[key].append(time.monotonic())

    async def _arun(self, **kwargs) -> str:
        """Async execution with rate limit check."""
        self._check_rate_limit()
        return await self._inner_tool._arun(**kwargs)

    def _run(self, **kwargs) -> str:
        """Sync execution with rate limit check."""
        self._check_rate_limit()
        return self._inner_tool._run(**kwargs)


def reset_rate_limits() -> None:
    """Reset all rate limit counters. Useful for testing."""
    _call_timestamps.clear()


def get_remaining_calls(user_id: str, tool_name: str, calls_per_minute: int) -> int:
    """Get the number of remaining calls within the current window."""
    key = (user_id, tool_name)
    recent = _cleanup_window(key)
    return max(0, calls_per_minute - len(recent))
