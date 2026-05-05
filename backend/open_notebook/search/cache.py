"""
Embedding Cache

LRU cache with TTL for embedding vectors to avoid redundant API calls.
"""

import hashlib
import time
from collections import OrderedDict
from threading import Lock
from typing import List, Optional, Tuple


class EmbeddingCache:
    """
    Thread-safe LRU cache with TTL for embedding vectors.

    Caches embedding results keyed by (text, model_id) to avoid
    repeated API calls for the same input.
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        """
        Args:
            max_size: Maximum number of cached embeddings
            ttl_seconds: Time-to-live in seconds (default: 1 hour)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, Tuple[List[float], float]] = OrderedDict()
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    def _make_key(self, text: str, model_id: str) -> str:
        """Create a deterministic cache key from text and model_id."""
        raw = f"{model_id}:{text}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, text: str, model_id: str) -> Optional[List[float]]:
        """
        Retrieve a cached embedding if it exists and hasn't expired.

        Args:
            text: The input text
            model_id: The embedding model identifier

        Returns:
            Cached embedding vector, or None on miss/expiry
        """
        key = self._make_key(text, model_id)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None

            embedding, timestamp = entry
            if time.monotonic() - timestamp > self.ttl_seconds:
                # Expired - remove it
                del self._cache[key]
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return embedding

    def set(self, text: str, model_id: str, embedding: List[float]) -> None:
        """
        Store an embedding in the cache.

        Evicts the least-recently-used entry if at capacity.

        Args:
            text: The input text
            model_id: The embedding model identifier
            embedding: The embedding vector to cache
        """
        key = self._make_key(text, model_id)
        with self._lock:
            if key in self._cache:
                # Update existing entry and move to end
                self._cache[key] = (embedding, time.monotonic())
                self._cache.move_to_end(key)
            else:
                # Evict LRU if at capacity
                while len(self._cache) >= self.max_size:
                    self._cache.popitem(last=False)
                self._cache[key] = (embedding, time.monotonic())

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    @property
    def stats(self) -> dict:
        """Return cache hit/miss statistics."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / total, 3) if total > 0 else 0.0,
            }


# Module-level singleton
_embedding_cache = EmbeddingCache(max_size=1000, ttl_seconds=3600)


def get_embedding_cache() -> EmbeddingCache:
    """Return the global embedding cache instance."""
    return _embedding_cache
