"""
Open Notebook Search Module

Multi-strategy search system for intelligent content retrieval.
"""

from open_notebook.search.strategies import (
    SearchStrategy,
    SearchResult,
    SearchFilters,
    SearchStrategyError,
    SearchConfigError,
    SearchExecutionError
)

from open_notebook.search.keyword import KeywordSearch
from open_notebook.search.vector import VectorSearch
from open_notebook.search.hybrid import HybridSearch
from open_notebook.search.agentic_rag import AgenticRAGSearch
from open_notebook.search.cache import EmbeddingCache, get_embedding_cache

__all__ = [
    # Base classes
    'SearchStrategy',
    'SearchResult',
    'SearchFilters',
    # Exceptions
    'SearchStrategyError',
    'SearchConfigError',
    'SearchExecutionError',
    # Strategies
    'KeywordSearch',
    'VectorSearch',
    'HybridSearch',
    'AgenticRAGSearch',
    # Cache
    'EmbeddingCache',
    'get_embedding_cache',
]
