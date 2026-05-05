"""
Database Interface - Abstract base class for database implementations

This module defines the abstract interface that all database implementations
(SQLite, HANA) must conform to, enabling runtime database switching.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncContextManager
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ConnectionConfig:
    """Configuration for database connections"""
    db_type: str  # 'sqlite' or 'hana'
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    encrypt: bool = True
    # SQLite specific
    db_path: Optional[str] = None
    # Connection pool settings
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30


@dataclass
class QueryResult:
    """Result of a database query"""
    rows: List[Dict[str, Any]]
    row_count: int
    execution_time: float  # milliseconds


@dataclass
class TransactionContext:
    """Context for database transactions"""
    isolation_level: Optional[str] = None
    read_only: bool = False


class DatabaseInterface(ABC):
    """
    Abstract base class for database implementations.

    All database backends (SQLite, HANA) must implement this interface
    to ensure consistent behavior across the application.
    """

    def __init__(self, config: ConnectionConfig):
        """
        Initialize database with configuration

        Args:
            config: Database connection configuration
        """
        self.config = config
        self._connected = False

    @abstractmethod
    async def connect(self) -> None:
        """
        Establish connection to the database.

        Should set up connection pooling and verify connectivity.
        Raises DatabaseError if connection fails.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Close database connections and cleanup resources.

        Should gracefully close all pooled connections and release resources.
        """
        pass

    @abstractmethod
    async def query(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        fetch_one: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results.

        Args:
            sql: SQL query string with parameterized placeholders
            params: Dictionary of parameter values
            fetch_one: If True, return only first row (or None)

        Returns:
            List of dictionaries representing rows (keys are column names)
            If fetch_one=True, returns single dict or None

        Raises:
            DatabaseError: If query execution fails
        """
        pass

    @abstractmethod
    async def execute(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Execute an INSERT, UPDATE, or DELETE statement.

        Args:
            sql: SQL statement with parameterized placeholders
            params: Dictionary of parameter values

        Returns:
            Number of rows affected

        Raises:
            DatabaseError: If execution fails
        """
        pass

    @abstractmethod
    async def create(
        self,
        table: str,
        data: Dict[str, Any]
    ) -> str:
        """
        Insert a new record into a table.

        Automatically generates UUID for 'id' field if not provided.
        Sets 'created' and 'updated' timestamps if columns exist.

        Args:
            table: Table name
            data: Dictionary of column names and values

        Returns:
            ID of the created record (UUID string)

        Raises:
            DatabaseError: If insert fails
        """
        pass

    @abstractmethod
    async def update(
        self,
        table: str,
        id: str,
        data: Dict[str, Any]
    ) -> None:
        """
        Update an existing record in a table.

        Automatically updates 'updated' timestamp if column exists.

        Args:
            table: Table name
            id: Record ID (UUID string)
            data: Dictionary of column names and new values

        Raises:
            DatabaseError: If update fails or record not found
        """
        pass

    @abstractmethod
    async def upsert(
        self,
        table: str,
        data: Dict[str, Any],
        conflict_columns: Optional[List[str]] = None
    ) -> str:
        """
        Insert a record or update if it already exists.

        Args:
            table: Table name
            data: Dictionary of column names and values
            conflict_columns: Columns to check for conflict (default: ['id'])

        Returns:
            ID of the record (UUID string)

        Raises:
            DatabaseError: If upsert fails
        """
        pass

    @abstractmethod
    async def delete(
        self,
        table: str,
        id: str
    ) -> None:
        """
        Delete a record from a table.

        Cascade deletes handled by database foreign key constraints.

        Args:
            table: Table name
            id: Record ID (UUID string)

        Raises:
            DatabaseError: If delete fails or record not found
        """
        pass

    @abstractmethod
    async def insert(
        self,
        table: str,
        data: Dict[str, Any]
    ) -> str:
        """
        Insert a new record (alias for create for compatibility).

        Args:
            table: Table name
            data: Dictionary of column names and values

        Returns:
            ID of the created record (UUID string)
        """
        pass

    @abstractmethod
    async def vector_search(
        self,
        embedding: List[float],
        table: str = "source_embeddings",
        limit: int = 10,
        threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search.

        Implementation varies by database:
        - SQLite: Python-based cosine similarity with NumPy
        - HANA: Native COSINE_SIMILARITY() function

        Args:
            embedding: Query embedding vector (1536 dimensions for OpenAI)
            table: Table containing embeddings (default: source_embeddings)
            limit: Maximum number of results
            threshold: Minimum similarity score (0.0 to 1.0)
            filters: Additional WHERE clause filters

        Returns:
            List of dictionaries with 'id', 'source_id', 'content',
            'similarity' (score), and other columns

        Raises:
            DatabaseError: If search fails
        """
        pass

    @abstractmethod
    async def begin_transaction(
        self,
        context: Optional[TransactionContext] = None
    ) -> AsyncContextManager:
        """
        Begin a database transaction.

        Usage:
            async with db.begin_transaction():
                await db.create('notebooks', {...})
                await db.create('sources', {...})

        Args:
            context: Transaction configuration (isolation level, read-only)

        Returns:
            Async context manager for transaction

        Raises:
            DatabaseError: If transaction fails
        """
        pass

    @abstractmethod
    async def execute_many(
        self,
        sql: str,
        params_list: List[Dict[str, Any]]
    ) -> int:
        """
        Execute a statement multiple times with different parameters.

        More efficient than individual executions for bulk operations.

        Args:
            sql: SQL statement with parameterized placeholders
            params_list: List of parameter dictionaries

        Returns:
            Total number of rows affected

        Raises:
            DatabaseError: If execution fails
        """
        pass

    @property
    def is_connected(self) -> bool:
        """Check if database is currently connected"""
        return self._connected

    @property
    def db_type(self) -> str:
        """Get database type (sqlite or hana)"""
        return self.config.db_type


class DatabaseError(Exception):
    """Base exception for database errors"""
    pass


class ConnectionError(DatabaseError):
    """Raised when connection to database fails"""
    pass


class QueryError(DatabaseError):
    """Raised when query execution fails"""
    pass


class TransactionError(DatabaseError):
    """Raised when transaction fails"""
    pass
