"""
LLM Client Pool - Singleton cache for LangChain LLM client instances.

Avoids recreating ChatOpenAI/ChatAnthropic instances for the same
model+parameters combination. Thread-safe via a module-level lock.
"""

import threading
from typing import Any, Dict, Optional

from langchain_openai import ChatOpenAI


class LLMClientPool:
    """
    Singleton cache of LangChain LLM clients keyed by
    (model_name, temperature, base_url, api_key, streaming).

    Usage::

        llm = LLMClientPool.get_llm("gpt-4", temperature=0.7)
        llm2 = LLMClientPool.get_llm("gpt-4", temperature=0.7)
        assert llm is llm2  # same instance
    """

    _instance: Optional["LLMClientPool"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._cache: Dict[str, Any] = {}

    @classmethod
    def _get_instance(cls) -> "LLMClientPool":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @staticmethod
    def _cache_key(
        model_name: str,
        temperature: float,
        base_url: Optional[str],
        api_key: Optional[str],
        streaming: bool,
    ) -> str:
        # Hash the api_key to avoid storing it as plain text in the key
        key_hash = hash(api_key) if api_key else "none"
        return f"{model_name}|{temperature}|{base_url or ''}|{key_hash}|{streaming}"

    @classmethod
    def get_llm(
        cls,
        model_name: str,
        temperature: float = 0.7,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        streaming: bool = True,
        **kwargs: Any,
    ) -> ChatOpenAI:
        """
        Return a cached ChatOpenAI instance or create one.

        Extra ``kwargs`` (e.g. ``max_tokens``, ``callbacks``) are forwarded
        to the constructor on first creation but are **not** part of the
        cache key.  If you need different ``kwargs`` for the same model,
        create the client directly.

        Args:
            model_name: Model identifier (e.g. "gpt-4", "claude-3-opus")
            temperature: Sampling temperature
            base_url: Optional API base URL (e.g. LiteLLM proxy)
            api_key: Optional API key
            streaming: Enable streaming responses
            **kwargs: Extra keyword arguments forwarded to ChatOpenAI

        Returns:
            A (possibly cached) ChatOpenAI instance
        """
        pool = cls._get_instance()
        key = cls._cache_key(model_name, temperature, base_url, api_key, streaming)

        with cls._lock:
            if key in pool._cache:
                return pool._cache[key]

        # Build outside the lock to avoid holding it during network calls
        llm_kwargs: Dict[str, Any] = {
            "model": model_name,
            "temperature": temperature,
            "streaming": streaming,
        }
        if base_url:
            llm_kwargs["base_url"] = base_url
        if api_key:
            # Use "api_key" for LiteLLM compatibility (it gets mapped to the right param)
            llm_kwargs["api_key"] = api_key
        llm_kwargs.update(kwargs)

        llm = ChatOpenAI(**llm_kwargs)

        with cls._lock:
            # Double-check: another thread may have populated it
            if key not in pool._cache:
                pool._cache[key] = llm
            return pool._cache[key]

    @classmethod
    def clear(cls) -> None:
        """Drop all cached clients (useful in tests)."""
        pool = cls._get_instance()
        with cls._lock:
            pool._cache.clear()

    @classmethod
    def size(cls) -> int:
        """Return the number of cached clients."""
        pool = cls._get_instance()
        with cls._lock:
            return len(pool._cache)
