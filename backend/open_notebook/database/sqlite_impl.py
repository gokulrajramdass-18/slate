"""
SQLite Database Implementation

Implements DatabaseInterface for SQLite with async operations using aiosqlite.
Uses SQLAlchemy for connection pooling and NumPy for vector search.
"""

import asyncio
import json
import uuid
import numpy as np
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncContextManager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.pool import AsyncAdaptedQueuePool

from .interface import (
    DatabaseInterface,
    ConnectionConfig,
    TransactionContext,
    DatabaseError,
    ConnectionError,
    QueryError,
    TransactionError
)


class SQLiteDatabase(DatabaseInterface):
    """
    SQLite implementation of DatabaseInterface.

    Features:
    - Async operations via aiosqlite
    - Connection pooling via SQLAlchemy async engine
    - Transaction support
    - Vector search using NumPy cosine similarity
    - JSON column support
    - Full-text search (FTS5)
    """

    def __init__(self, config: ConnectionConfig):
        super().__init__(config)
        self.engine: Optional[AsyncEngine] = None
        self._db_path = config.db_path or "./data/database.db"
        self._pool_size = config.pool_size
        self._max_overflow = config.max_overflow

    async def connect(self) -> None:
        """
        Establish connection to SQLite database.

        Creates database file and parent directories if they don't exist.
        Sets up SQLAlchemy async engine with connection pooling.
        """
        try:
            # Ensure parent directory exists
            db_path = Path(self._db_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)

            # Create SQLAlchemy async engine with connection pooling
            database_url = f"sqlite+aiosqlite:///{self._db_path}"

            # Event listener to enable foreign keys on every connection
            from sqlalchemy import event

            self.engine = create_async_engine(
                database_url,
                poolclass=AsyncAdaptedQueuePool,
                pool_size=self._pool_size,
                max_overflow=self._max_overflow,
                pool_timeout=self.config.pool_timeout,
                echo=False,  # Set to True for SQL logging
                connect_args={"check_same_thread": False}
            )

            # Enable foreign keys, WAL mode, and performance settings for ALL connections in the pool
            @event.listens_for(self.engine.sync_engine, "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")  # RE-ENABLED - workspaces should never be deleted
                cursor.execute("PRAGMA busy_timeout=5000")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=-64000")
                cursor.execute("PRAGMA wal_autocheckpoint=1000")
                cursor.close()

            # Test connection
            from sqlalchemy import text
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

            self._connected = True

        except Exception as e:
            raise ConnectionError(f"Failed to connect to SQLite database: {str(e)}")

    async def disconnect(self) -> None:
        """
        Close database connections and cleanup resources.
        """
        if self.engine:
            await self.engine.dispose()
            self._connected = False

    async def query(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        fetch_one: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results as dictionaries.

        Args:
            sql: SQL query with :param_name placeholders
            params: Dictionary of parameter values
            fetch_one: If True, return only first row

        Returns:
            List of dictionaries (or single dict if fetch_one=True)
        """
        if not self._connected:
            raise DatabaseError("Database not connected")

        try:
            from sqlalchemy import text
            async with self.engine.connect() as conn:
                if params:
                    result = await conn.execute(text(sql), params)
                else:
                    result = await conn.execute(text(sql))

                if fetch_one:
                    row = result.mappings().fetchone()
                    return dict(row) if row else None
                else:
                    rows = result.mappings().fetchall()
                    return [dict(row) for row in rows]

        except Exception as e:
            raise QueryError(f"Query failed: {str(e)}\nSQL: {sql}")

    async def execute(
        self,
        sql: str,
        params: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Execute an INSERT, UPDATE, or DELETE statement.

        Returns:
            Number of rows affected
        """
        if not self._connected:
            raise DatabaseError("Database not connected")

        try:
            from sqlalchemy import text
            async with self.engine.begin() as conn:
                if params:
                    result = await conn.execute(text(sql), params)
                else:
                    result = await conn.execute(text(sql))

                return result.rowcount

        except Exception as e:
            raise QueryError(f"Execute failed: {str(e)}\nSQL: {sql}")

    async def create(
        self,
        table: str,
        data: Dict[str, Any]
    ) -> str:
        """
        Insert a new record with auto-generated UUID and timestamps.

        Returns:
            UUID of created record
        """
        if not self._connected:
            raise DatabaseError("Database not connected")

        # Add timestamps (only if not already excluded from data)
        now = datetime.utcnow().isoformat()
        # Tables that use created_at/updated_at instead of created/updated
        tables_with_at_timestamps = [
            'workflows',
            'workflow_schedules',
            'actions',
            'orchestration_action_bindings',
            'workspace_templates',
            'template_executions'  # NEW: Template executions use created_at/updated_at
        ]
        # Tables that don't have id/created/updated columns at all
        # Includes: tables with composite PKs, junction tables, and tables with custom timestamp columns
        tables_without_timestamps = [
            'workflow_executions',
            'chat_messages',
            'agent_messages',
            'microsite_versions',
            'content_moderation_logs',
            'tool_permissions',
            'tool_usage_log',
            'a2a_execution_metrics',
            'action_executions',
            # Junction tables (composite primary keys, no id column)
            'notebook_note',
            'notebook_source',
            'notebook_chat_session'
        ]

        # Generate UUID if not provided (skip for junction tables)
        if 'id' not in data and table not in tables_without_timestamps:
            data['id'] = str(uuid.uuid4())

        if table in tables_with_at_timestamps:
            # Use created_at/updated_at for workflow tables
            if 'created_at' not in data:
                data['created_at'] = now
            if 'updated_at' not in data:
                data['updated_at'] = now
        elif table not in tables_without_timestamps:
            # Use created/updated for regular tables
            if 'created' not in data:
                data['created'] = now
            if 'updated' not in data:
                data['updated'] = now

        # Convert JSON fields to strings
        data = self._serialize_json_fields(data)

        # Build INSERT statement
        columns = list(data.keys())
        placeholders = [f":{col}" for col in columns]
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"

        try:
            await self.execute(sql, data)
            # Junction tables don't have an id column, return empty string
            return data.get('id', '')
        except Exception as e:
            raise DatabaseError(f"Create failed for table {table}: {str(e)}")

    async def update(
        self,
        table: str,
        id: str,
        data: Dict[str, Any]
    ) -> None:
        """
        Update an existing record.

        Automatically updates 'updated' timestamp.
        """
        if not self._connected:
            raise DatabaseError("Database not connected")

        # Update timestamp
        tables_with_at_timestamps = [
            'workflows',
            'workflow_schedules',
            'actions',
            'orchestration_action_bindings',
            'workspace_templates',
            'template_executions'  # NEW: Template executions use created_at/updated_at
        ]
        tables_without_timestamps = ['workflow_executions', 'chat_messages', 'agent_messages', 'microsite_versions', 'content_moderation_logs', 'tool_permissions', 'tool_usage_log', 'a2a_execution_metrics', 'action_executions']

        if table in tables_with_at_timestamps:
            data['updated_at'] = datetime.utcnow().isoformat()
        elif table not in tables_without_timestamps:
            data['updated'] = datetime.utcnow().isoformat()

        # Convert JSON fields to strings
        data = self._serialize_json_fields(data)

        # Build UPDATE statement
        set_clause = ', '.join([f"{col} = :{col}" for col in data.keys()])
        sql = f"UPDATE {table} SET {set_clause} WHERE id = :id"

        params = {**data, 'id': id}

        try:
            rows_affected = await self.execute(sql, params)
            if rows_affected == 0:
                raise DatabaseError(f"Record not found: {table} with id {id}")
        except Exception as e:
            raise DatabaseError(f"Update failed for table {table}: {str(e)}")

    async def upsert(
        self,
        table: str,
        data: Dict[str, Any],
        conflict_columns: Optional[List[str]] = None
    ) -> str:
        """
        Insert or update a record using INSERT ... ON CONFLICT.

        Returns:
            UUID of record
        """
        if not self._connected:
            raise DatabaseError("Database not connected")

        # Generate UUID if not provided
        if 'id' not in data:
            data['id'] = str(uuid.uuid4())

        # Add timestamps
        now = datetime.utcnow().isoformat()
        if 'created' not in data:
            data['created'] = now
        data['updated'] = now

        # Convert JSON fields
        data = self._serialize_json_fields(data)

        # Default conflict column is 'id'
        conflict_cols = conflict_columns or ['id']

        # Build UPSERT statement (SQLite 3.24+)
        columns = list(data.keys())
        placeholders = [f":{col}" for col in columns]

        # Columns to update on conflict (exclude conflict columns)
        update_cols = [col for col in columns if col not in conflict_cols]
        update_clause = ', '.join([f"{col} = excluded.{col}" for col in update_cols])

        sql = f"""
            INSERT INTO {table} ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
            ON CONFLICT({', '.join(conflict_cols)})
            DO UPDATE SET {update_clause}
        """

        try:
            await self.execute(sql, data)
            return data['id']
        except Exception as e:
            raise DatabaseError(f"Upsert failed for table {table}: {str(e)}")

    async def delete(
        self,
        table: str,
        id: str
    ) -> None:
        """
        Delete a record by ID.

        Cascade deletes handled by foreign key constraints.
        """
        if not self._connected:
            raise DatabaseError("Database not connected")

        sql = f"DELETE FROM {table} WHERE id = :id"

        try:
            rows_affected = await self.execute(sql, {'id': id})
            if rows_affected == 0:
                raise DatabaseError(f"Record not found: {table} with id {id}")
        except DatabaseError:
            # Re-raise our own DatabaseErrors
            raise
        except Exception as e:
            # Log the actual error for debugging
            import traceback
            print(f"[Database] Delete error for {table} id={id}:")
            print(f"[Database] SQL: {sql}")
            print(f"[Database] Error type: {type(e).__name__}")
            print(f"[Database] Error message: {str(e)}")
            traceback.print_exc()
            raise DatabaseError(f"Delete failed for table {table}: {str(e)}")

    async def insert(
        self,
        table: str,
        data: Dict[str, Any]
    ) -> str:
        """
        Alias for create() for compatibility.
        """
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
        Perform vector similarity search using NumPy cosine similarity.

        SQLite stores embeddings as JSON arrays in TEXT/BLOB columns.
        This implementation loads all embeddings and computes similarity in Python.

        For production with large datasets, consider using HANA's native vector search.

        Args:
            embedding: Query embedding vector
            table: Table with embeddings (must have 'embedding' column)
            limit: Max results
            threshold: Min similarity score
            filters: Additional filters (e.g., {'source_id': 'uuid'})

        Returns:
            List of results sorted by similarity (descending)
        """
        if not self._connected:
            raise DatabaseError("Database not connected")

        try:
            # Build query to fetch all embeddings
            sql = f"SELECT * FROM {table}"
            where_clauses = []
            params = {}

            if filters:
                for key, value in filters.items():
                    where_clauses.append(f"{key} = :{key}")
                    params[key] = value

            if where_clauses:
                sql += " WHERE " + " AND ".join(where_clauses)

            rows = await self.query(sql, params)

            if not rows:
                return []

            # Convert query embedding to numpy array
            query_vec = np.array(embedding, dtype=np.float32)
            query_norm = np.linalg.norm(query_vec)

            # Compute cosine similarity for each row
            results = []
            for row in rows:
                # Parse embedding (stored as JSON string)
                try:
                    if isinstance(row['embedding'], str):
                        stored_embedding = json.loads(row['embedding'])
                    elif isinstance(row['embedding'], bytes):
                        # If stored as BLOB (numpy array)
                        stored_embedding = np.frombuffer(row['embedding'], dtype=np.float32).tolist()
                    else:
                        stored_embedding = row['embedding']

                    stored_vec = np.array(stored_embedding, dtype=np.float32)
                    stored_norm = np.linalg.norm(stored_vec)

                    # Cosine similarity: dot(A, B) / (norm(A) * norm(B))
                    if query_norm > 0 and stored_norm > 0:
                        similarity = float(np.dot(query_vec, stored_vec) / (query_norm * stored_norm))
                    else:
                        similarity = 0.0

                    # Only include if above threshold
                    if similarity >= threshold:
                        result = dict(row)
                        result['similarity'] = similarity
                        results.append(result)

                except (json.JSONDecodeError, ValueError) as e:
                    # Skip invalid embeddings
                    continue

            # Sort by similarity (descending) and limit
            results.sort(key=lambda x: x['similarity'], reverse=True)
            return results[:limit]

        except Exception as e:
            raise QueryError(f"Vector search failed: {str(e)}")

    @asynccontextmanager
    async def begin_transaction(
        self,
        context: Optional[TransactionContext] = None
    ) -> AsyncContextManager:
        """
        Begin a database transaction.

        Usage:
            async with db.begin_transaction():
                await db.create('table', {...})
                # Transaction commits on successful exit
                # Rolls back on exception
        """
        if not self._connected:
            raise DatabaseError("Database not connected")

        try:
            async with self.engine.begin() as conn:
                try:
                    yield conn
                except Exception:
                    raise

        except Exception as e:
            raise TransactionError(f"Transaction failed: {str(e)}")

    async def execute_many(
        self,
        sql: str,
        params_list: List[Dict[str, Any]]
    ) -> int:
        """
        Execute a statement multiple times with different parameters.

        More efficient than individual executions for bulk operations.
        """
        if not self._connected:
            raise DatabaseError("Database not connected")

        if not params_list:
            return 0

        try:
            from sqlalchemy import text
            async with self.engine.begin() as conn:
                total_rows = 0
                for params in params_list:
                    result = await conn.execute(text(sql), params)
                    total_rows += result.rowcount
                return total_rows

        except Exception as e:
            raise QueryError(f"Execute many failed: {str(e)}")

    def _convert_params(self, sql: str, params: Dict[str, Any]) -> tuple:
        """
        Convert named parameters (:name) to positional (?) for aiosqlite.

        Args:
            sql: SQL with named parameters
            params: Dictionary of parameters

        Returns:
            Tuple of (converted_sql, param_list)
        """
        import re

        # Find all named parameters
        param_names = re.findall(r':(\w+)', sql)

        # Replace named with positional
        converted_sql = sql
        param_list = []

        for name in param_names:
            converted_sql = converted_sql.replace(f':{name}', '?', 1)
            if name in params:
                param_list.append(params[name])
            else:
                raise ValueError(f"Missing parameter: {name}")

        return converted_sql, param_list

    def _serialize_json_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert dict/list values to JSON strings for storage.

        SQLite doesn't have native JSON type (until 3.38 with JSON functions),
        so we store as TEXT.
        """
        serialized = {}
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                serialized[key] = json.dumps(value)
            else:
                serialized[key] = value
        return serialized
