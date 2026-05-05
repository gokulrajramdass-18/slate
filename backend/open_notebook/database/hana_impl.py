"""
HANA Cloud Database Implementation

This module implements the DatabaseInterface for SAP HANA Cloud, providing:
- Connection pooling via SQLAlchemy
- Native vector search with COSINE_SIMILARITY()
- HANA-specific data types (REAL_VECTOR, NCLOB)
- SSL/encryption support
- Full-text search with CONTAINS()
"""

import json
import uuid
import logging
from typing import List, Dict, Any, Optional, AsyncContextManager
from datetime import datetime
from contextlib import asynccontextmanager

from hdbcli import dbapi
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

from .interface import (
    DatabaseInterface,
    ConnectionConfig,
    DatabaseError,
    ConnectionError as DBConnectionError,
    QueryError,
    TransactionError
)

logger = logging.getLogger(__name__)


class HANADatabase(DatabaseInterface):
    """
    SAP HANA Cloud database implementation.

    Features:
    - Native vector search with COSINE_SIMILARITY()
    - REAL_VECTOR column type for embeddings
    - Full-text search with CONTAINS()
    - Column store optimization
    - SSL/TLS encryption
    - Connection pooling
    """

    def __init__(self, config: ConnectionConfig):
        """
        Initialize HANA database connection.

        Args:
            config: Database connection configuration
        """
        super().__init__(config)
        self.engine: Optional[AsyncEngine] = None
        self._connection = None
        self._transaction = None

    async def connect(self) -> None:
        """
        Establish connection to HANA Cloud.

        Creates connection pool using SQLAlchemy with hdbcli driver.
        Verifies connectivity with a test query.
        """
        try:
            # Build connection string for SQLAlchemy
            # Format: hana+hdbcli://user:password@host:port/?encrypt=true&sslValidateCertificate=false
            connection_params = {
                'encrypt': 'true' if self.config.encrypt else 'false',
                'sslValidateCertificate': 'false'  # For development; set to 'true' in production
            }

            param_string = '&'.join([f"{k}={v}" for k, v in connection_params.items()])

            connection_url = (
                f"hana+hdbcli://{self.config.user}:{self.config.password}"
                f"@{self.config.host}:{self.config.port}/"
                f"?{param_string}"
            )

            # Create async engine with connection pooling
            self.engine = create_async_engine(
                connection_url,
                poolclass=QueuePool,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_timeout=self.config.pool_timeout,
                pool_pre_ping=True,  # Verify connections before using
                echo=False  # Set to True for SQL debugging
            )

            # Test connection
            async with self.engine.connect() as conn:
                result = await conn.execute(text("SELECT 1 FROM DUMMY"))
                await result.fetchone()

            self._connected = True
            logger.info(f"Connected to HANA Cloud at {self.config.host}:{self.config.port}")

        except Exception as e:
            logger.error(f"Failed to connect to HANA Cloud: {str(e)}")
            raise DBConnectionError(f"HANA connection failed: {str(e)}")

    async def disconnect(self) -> None:
        """
        Close HANA database connections and cleanup.
        """
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self._connected = False
            logger.info("Disconnected from HANA Cloud")

    async def query(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        fetch_one: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query on HANA.

        Args:
            sql: SQL query with :param_name placeholders
            params: Dictionary of parameter values
            fetch_one: Return only first row

        Returns:
            List of dictionaries (or single dict if fetch_one=True)
        """
        if not self._connected:
            raise DatabaseError("Not connected to database")

        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(text(sql), params or {})

                if fetch_one:
                    row = await result.fetchone()
                    if row:
                        return dict(row._mapping)
                    return None

                rows = await result.fetchall()
                return [dict(row._mapping) for row in rows]

        except Exception as e:
            logger.error(f"Query failed: {str(e)}\nSQL: {sql}\nParams: {params}")
            raise QueryError(f"Query execution failed: {str(e)}")

    async def execute(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Execute INSERT, UPDATE, or DELETE on HANA.

        Args:
            sql: SQL statement with :param_name placeholders
            params: Dictionary of parameter values

        Returns:
            Number of rows affected
        """
        if not self._connected:
            raise DatabaseError("Not connected to database")

        try:
            async with self.engine.begin() as conn:
                result = await conn.execute(text(sql), params or {})
                return result.rowcount

        except Exception as e:
            logger.error(f"Execute failed: {str(e)}\nSQL: {sql}\nParams: {params}")
            raise QueryError(f"Execution failed: {str(e)}")

    async def create(
        self,
        table: str,
        data: Dict[str, Any]
    ) -> str:
        """
        Insert a new record into HANA table.

        Automatically:
        - Generates UUID for 'id' field if not provided
        - Sets 'created' and 'updated' timestamps
        - Converts Python dicts/lists to JSON for NCLOB columns

        Args:
            table: Table name
            data: Column values

        Returns:
            Record ID (UUID string)
        """
        # Generate ID if not provided
        if 'id' not in data:
            data['id'] = str(uuid.uuid4())

        # Set timestamps
        now = datetime.utcnow().isoformat()
        if 'created' not in data:
            data['created'] = now
        if 'updated' not in data:
            data['updated'] = now

        # Convert JSON fields to strings
        data = self._serialize_json_fields(data)

        # Build INSERT statement
        columns = ', '.join(data.keys())
        placeholders = ', '.join([f":{key}" for key in data.keys()])
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"

        try:
            await self.execute(sql, data)
            return data['id']

        except Exception as e:
            logger.error(f"Create failed on table {table}: {str(e)}")
            raise DatabaseError(f"Failed to create record: {str(e)}")

    async def update(
        self,
        table: str,
        id: str,
        data: Dict[str, Any]
    ) -> None:
        """
        Update an existing record in HANA.

        Automatically:
        - Updates 'updated' timestamp
        - Converts Python dicts/lists to JSON

        Args:
            table: Table name
            id: Record ID
            data: Column values to update
        """
        # Set updated timestamp
        data['updated'] = datetime.utcnow().isoformat()

        # Convert JSON fields
        data = self._serialize_json_fields(data)

        # Build UPDATE statement
        set_clause = ', '.join([f"{key} = :{key}" for key in data.keys()])
        sql = f"UPDATE {table} SET {set_clause} WHERE id = :id"

        params = {**data, 'id': id}

        try:
            rows_affected = await self.execute(sql, params)
            if rows_affected == 0:
                raise DatabaseError(f"Record with id {id} not found in {table}")

        except Exception as e:
            logger.error(f"Update failed on table {table}: {str(e)}")
            raise DatabaseError(f"Failed to update record: {str(e)}")

    async def upsert(
        self,
        table: str,
        data: Dict[str, Any],
        conflict_columns: Optional[List[str]] = None
    ) -> str:
        """
        Insert or update record using HANA's UPSERT statement.

        Args:
            table: Table name
            data: Column values
            conflict_columns: Columns to check for conflict (default: ['id'])

        Returns:
            Record ID
        """
        # Generate ID if not provided
        if 'id' not in data:
            data['id'] = str(uuid.uuid4())

        # Set timestamps
        now = datetime.utcnow().isoformat()
        if 'created' not in data:
            data['created'] = now
        data['updated'] = now

        # Convert JSON fields
        data = self._serialize_json_fields(data)

        # HANA UPSERT syntax
        columns = ', '.join(data.keys())
        placeholders = ', '.join([f":{key}" for key in data.keys()])

        # Build update clause (all columns except id and created)
        update_columns = [k for k in data.keys() if k not in ['id', 'created']]
        update_clause = ', '.join([f"{key} = :{key}" for key in update_columns])

        sql = f"""
        UPSERT {table} ({columns})
        VALUES ({placeholders})
        WITH PRIMARY KEY
        """

        try:
            await self.execute(sql, data)
            return data['id']

        except Exception as e:
            logger.error(f"Upsert failed on table {table}: {str(e)}")
            raise DatabaseError(f"Failed to upsert record: {str(e)}")

    async def delete(
        self,
        table: str,
        id: str
    ) -> None:
        """
        Delete a record from HANA.

        Cascade deletes are handled by foreign key constraints.

        Args:
            table: Table name
            id: Record ID
        """
        sql = f"DELETE FROM {table} WHERE id = :id"

        try:
            rows_affected = await self.execute(sql, {'id': id})
            if rows_affected == 0:
                raise DatabaseError(f"Record with id {id} not found in {table}")

        except Exception as e:
            logger.error(f"Delete failed on table {table}: {str(e)}")
            raise DatabaseError(f"Failed to delete record: {str(e)}")

    async def insert(
        self,
        table: str,
        data: Dict[str, Any]
    ) -> str:
        """Alias for create() for compatibility."""
        return await self.create(table, data)

    async def vector_search(
        self,
        embedding: List[float],
        table: str = "source_embeddings",
        limit: int = 10,
        threshold: float = 0.7,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search using HANA's native COSINE_SIMILARITY().

        HANA Vector Engine provides high-performance vector search with:
        - Native REAL_VECTOR column type
        - Built-in COSINE_SIMILARITY() function
        - Vector indexes for sub-100ms queries on millions of vectors

        Args:
            embedding: Query vector (e.g., 1536 dimensions for OpenAI)
            table: Table with embedding column
            limit: Max results
            threshold: Minimum similarity (0-1)
            filters: Additional WHERE conditions

        Returns:
            List of records with similarity scores (descending)
        """
        try:
            # Convert embedding to HANA REAL_VECTOR format
            # Format: "[0.1, 0.2, 0.3, ...]"
            embedding_str = '[' + ', '.join(map(str, embedding)) + ']'

            # Build WHERE clause
            where_clauses = []
            params = {'embedding': embedding_str, 'threshold': threshold, 'limit': limit}

            if filters:
                for key, value in filters.items():
                    where_clauses.append(f"{key} = :{key}")
                    params[key] = value

            where_clause = ' AND '.join(where_clauses) if where_clauses else '1=1'

            # HANA native vector search query
            sql = f"""
            SELECT
                id,
                source_id,
                content,
                order_num,
                created,
                COSINE_SIMILARITY(embedding, TO_REAL_VECTOR(:embedding)) as similarity
            FROM {table}
            WHERE {where_clause}
                AND COSINE_SIMILARITY(embedding, TO_REAL_VECTOR(:embedding)) >= :threshold
            ORDER BY similarity DESC
            LIMIT :limit
            """

            results = await self.query(sql, params)
            return results

        except Exception as e:
            logger.error(f"Vector search failed: {str(e)}")
            raise QueryError(f"Vector search failed: {str(e)}")

    @asynccontextmanager
    async def begin_transaction(
        self,
        context: Optional[Any] = None
    ) -> AsyncContextManager:
        """
        Begin a HANA transaction.

        Usage:
            async with db.begin_transaction():
                await db.create('notebooks', {...})
                await db.create('sources', {...})
        """
        if not self._connected:
            raise DatabaseError("Not connected to database")

        async with self.engine.begin() as conn:
            try:
                yield conn
            except Exception as e:
                # Rollback is automatic when exiting the context
                logger.error(f"Transaction failed: {str(e)}")
                raise TransactionError(f"Transaction failed: {str(e)}")

    async def execute_many(
        self,
        sql: str,
        params_list: List[Dict[str, Any]]
    ) -> int:
        """
        Execute a statement multiple times for bulk operations.

        More efficient than individual executions.

        Args:
            sql: SQL statement with :param_name placeholders
            params_list: List of parameter dictionaries

        Returns:
            Total rows affected
        """
        if not self._connected:
            raise DatabaseError("Not connected to database")

        try:
            total_affected = 0
            async with self.engine.begin() as conn:
                for params in params_list:
                    result = await conn.execute(text(sql), params)
                    total_affected += result.rowcount

            return total_affected

        except Exception as e:
            logger.error(f"Execute many failed: {str(e)}")
            raise QueryError(f"Bulk execution failed: {str(e)}")

    def _serialize_json_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Python dicts/lists to JSON strings for NCLOB/JSON columns.

        HANA stores JSON as NCLOB, so we need to serialize Python objects.
        """
        serialized = {}
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                serialized[key] = json.dumps(value)
            else:
                serialized[key] = value
        return serialized

    def _deserialize_json_fields(self, data: Dict[str, Any], json_columns: List[str]) -> Dict[str, Any]:
        """
        Convert JSON strings back to Python objects.

        Args:
            data: Row data from database
            json_columns: List of column names that contain JSON
        """
        deserialized = {}
        for key, value in data.items():
            if key in json_columns and isinstance(value, str):
                try:
                    deserialized[key] = json.loads(value)
                except json.JSONDecodeError:
                    deserialized[key] = value
            else:
                deserialized[key] = value
        return deserialized


# Convenience functions for direct hdbcli usage (for special cases)

def get_hdbcli_connection(config: ConnectionConfig) -> dbapi.Connection:
    """
    Get a raw hdbcli connection for special cases.

    Most code should use HANADatabase class, but this is available
    for operations that need direct hdbcli access.
    """
    try:
        conn = dbapi.connect(
            address=config.host,
            port=config.port,
            user=config.user,
            password=config.password,
            encrypt=config.encrypt,
            sslValidateCertificate=False  # Set to True in production
        )
        return conn
    except Exception as e:
        logger.error(f"Failed to create hdbcli connection: {str(e)}")
        raise DBConnectionError(f"HANA connection failed: {str(e)}")


async def test_hana_connection(config: ConnectionConfig) -> bool:
    """
    Test HANA connection without creating a full database instance.

    Args:
        config: HANA connection configuration

    Returns:
        True if connection successful, False otherwise
    """
    try:
        conn = get_hdbcli_connection(config)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM DUMMY")
        cursor.fetchone()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"HANA connection test failed: {str(e)}")
        return False
