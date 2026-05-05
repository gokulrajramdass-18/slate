"""
Search Strategy Interface

This module defines the abstract base class for all search strategies
and common data structures used across search implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class SearchResult:
    """
    Unified search result structure returned by all search strategies.

    Attributes:
        source_id: Unique identifier of the source document
        chunk_id: Unique identifier of the specific chunk (for vector/hybrid)
        content: The matching text content
        score: Relevance score (0.0 to 1.0, higher is better)
        highlights: List of highlighted snippets or keywords
        metadata: Additional metadata (title, source_type, created, etc.)
        strategy: Name of the strategy that produced this result
    """
    source_id: str
    chunk_id: Optional[str]
    content: str
    score: float
    highlights: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    strategy: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'source_id': self.source_id,
            'chunk_id': self.chunk_id,
            'content': self.content,
            'score': self.score,
            'highlights': self.highlights,
            'metadata': self.metadata,
            'strategy': self.strategy
        }


@dataclass
class SearchFilters:
    """
    Common search filters applicable across all strategies.

    Attributes:
        notebook_ids: Filter by specific notebook(s)
        source_types: Filter by source type (file, url, text, youtube, hana_table, api)
        date_from: Filter sources created after this date
        date_to: Filter sources created before this date
        tags: Filter by tags
    """
    notebook_ids: Optional[List[str]] = None
    source_types: Optional[List[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    tags: Optional[List[str]] = None

    def has_filters(self) -> bool:
        """Check if any filters are set."""
        return any([
            self.notebook_ids,
            self.source_types,
            self.date_from,
            self.date_to,
            self.tags
        ])


class SearchStrategy(ABC):
    """
    Abstract base class for all search strategies.

    Each strategy must implement the search method which takes a query,
    optional filters, and a limit, and returns a list of SearchResult objects.
    """

    def __init__(self, database, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the search strategy.

        Args:
            database: Database interface instance (SQLite or HANA)
            config: Strategy-specific configuration
        """
        self.database = database
        self.config = config or {}

    @abstractmethod
    async def search(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        limit: int = 10
    ) -> List[SearchResult]:
        """
        Execute search with the given query and filters.

        Args:
            query: The search query string
            filters: Optional filters to apply
            limit: Maximum number of results to return

        Returns:
            List of SearchResult objects, sorted by relevance (highest score first)
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this strategy."""
        pass

    @property
    def description(self) -> str:
        """Return a description of this strategy."""
        return "Base search strategy"

    def _build_filter_sql(self, filters: Optional[SearchFilters]) -> tuple[str, Dict[str, Any]]:
        """
        Build SQL WHERE clause and parameters from filters.

        Args:
            filters: SearchFilters object

        Returns:
            Tuple of (WHERE clause string, parameters dict)
        """
        if not filters or not filters.has_filters():
            return "", {}

        conditions = []
        params = {}

        if filters.notebook_ids:
            placeholders = ','.join([f':notebook_id_{i}' for i in range(len(filters.notebook_ids))])
            conditions.append(f"s.id IN (SELECT source_id FROM notebook_source WHERE notebook_id IN ({placeholders}))")
            for i, nb_id in enumerate(filters.notebook_ids):
                params[f'notebook_id_{i}'] = nb_id

        if filters.source_types:
            placeholders = ','.join([f':source_type_{i}' for i in range(len(filters.source_types))])
            conditions.append(f"s.source_type IN ({placeholders})")
            for i, st in enumerate(filters.source_types):
                params[f'source_type_{i}'] = st

        if filters.date_from:
            conditions.append("s.created >= :date_from")
            params['date_from'] = filters.date_from.isoformat()

        if filters.date_to:
            conditions.append("s.created <= :date_to")
            params['date_to'] = filters.date_to.isoformat()

        if filters.tags:
            # Join with tags through notebook_source and notebook_tags
            placeholders = ','.join([f':tag_{i}' for i in range(len(filters.tags))])
            conditions.append(f"""
                s.id IN (
                    SELECT ns.source_id
                    FROM notebook_source ns
                    JOIN notebook_tags nt ON ns.notebook_id = nt.notebook_id
                    JOIN tags t ON nt.tag_id = t.id
                    WHERE t.name IN ({placeholders})
                )
            """)
            for i, tag in enumerate(filters.tags):
                params[f'tag_{i}'] = tag

        where_clause = " AND ".join(conditions) if conditions else ""
        return where_clause, params


class SearchStrategyError(Exception):
    """Base exception for search strategy errors."""
    pass


class SearchConfigError(SearchStrategyError):
    """Raised when search configuration is invalid."""
    pass


class SearchExecutionError(SearchStrategyError):
    """Raised when search execution fails."""
    pass
