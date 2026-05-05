"""
Repository Layer - Data Access Layer

Provides high-level data access functions using the database abstraction layer.
Replaces direct SurrealDB calls with database interface methods.
"""

import uuid
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from datetime import datetime

from open_notebook.config import get_database
from open_notebook.database.interface import DatabaseInterface, DatabaseError


@asynccontextmanager
async def db_connection():
    """
    Context manager for database connections.

    Automatically connects and disconnects from the database.

    Usage:
        async with db_connection() as db:
            results = await db.query("SELECT * FROM notebooks")

    Yields:
        DatabaseInterface instance
    """
    db = get_database()
    try:
        await db.connect()
        yield db
    finally:
        await db.disconnect()


async def repo_query(
    sql: str,
    params: Optional[Dict[str, Any]] = None,
    fetch_one: bool = False
) -> List[Dict[str, Any]]:
    """
    Execute a SELECT query and return results.

    Args:
        sql: SQL query with named parameters
        params: Dictionary of parameter values
        fetch_one: If True, return single record or None

    Returns:
        List of dictionaries or single dict if fetch_one=True

    Example:
        notebooks = await repo_query(
            "SELECT * FROM notebooks WHERE archived = :archived",
            {"archived": False}
        )
    """
    async with db_connection() as db:
        return await db.query(sql, params, fetch_one)


async def repo_execute(
    sql: str,
    params: Optional[Dict[str, Any]] = None
) -> int:
    """
    Execute an INSERT, UPDATE, or DELETE statement.

    Args:
        sql: SQL statement with named parameters
        params: Dictionary of parameter values

    Returns:
        Number of rows affected

    Example:
        rows_affected = await repo_execute(
            "INSERT INTO notebook_source (notebook_id, source_id, created) VALUES (:notebook_id, :source_id, :created)",
            {"notebook_id": "uuid1", "source_id": "uuid2", "created": "2024-01-01T00:00:00"}
        )
    """
    async with db_connection() as db:
        return await db.execute(sql, params)


async def repo_create(
    table: str,
    data: Dict[str, Any]
) -> str:
    """
    Create a new record in a table.

    Automatically generates UUID and timestamps.

    Args:
        table: Table name
        data: Dictionary of column values

    Returns:
        UUID of created record

    Example:
        notebook_id = await repo_create('notebooks', {
            'name': 'My Research',
            'description': 'Project description'
        })
    """
    async with db_connection() as db:
        return await db.create(table, data)


async def repo_update(
    table: str,
    id: str,
    data: Dict[str, Any]
) -> None:
    """
    Update an existing record.

    Automatically updates 'updated' timestamp.

    Args:
        table: Table name
        id: Record UUID
        data: Dictionary of column values to update

    Example:
        await repo_update('notebooks', notebook_id, {
            'name': 'Updated Name',
            'archived': True
        })
    """
    async with db_connection() as db:
        await db.update(table, id, data)


async def repo_upsert(
    table: str,
    data: Dict[str, Any],
    conflict_columns: Optional[List[str]] = None
) -> str:
    """
    Insert or update a record.

    Args:
        table: Table name
        data: Dictionary of column values
        conflict_columns: Columns to check for conflict (default: ['id'])

    Returns:
        UUID of record

    Example:
        tag_id = await repo_upsert('tags', {
            'name': 'Important',
            'color': '#FF0000'
        }, conflict_columns=['name'])
    """
    async with db_connection() as db:
        return await db.upsert(table, data, conflict_columns)


async def repo_delete(
    table: str,
    id: str
) -> None:
    """
    Delete a record by ID.

    Cascade deletes handled by foreign key constraints.

    Args:
        table: Table name
        id: Record UUID

    Example:
        await repo_delete('notebooks', notebook_id)
    """
    async with db_connection() as db:
        await db.delete(table, id)


async def repo_insert(
    table: str,
    data: Dict[str, Any]
) -> str:
    """
    Alias for repo_create for compatibility.
    """
    return await repo_create(table, data)


# ============================================================================
# RECORD ID UTILITIES
# ============================================================================

def generate_id() -> str:
    """
    Generate a new UUID for record IDs.

    Replaces SurrealDB's table:id format with standard UUIDs.

    Returns:
        UUID string (e.g., "550e8400-e29b-41d4-a716-446655440000")
    """
    return str(uuid.uuid4())


def parse_record_id(record_id: str) -> str:
    """
    Parse record ID to extract UUID.

    For migration compatibility: handles both UUID and SurrealDB table:id format.

    Args:
        record_id: Either UUID or table:id format

    Returns:
        UUID string

    Example:
        # UUID format
        parse_record_id("550e8400-e29b-41d4-a716-446655440000")
        # Returns: "550e8400-e29b-41d4-a716-446655440000"

        # SurrealDB format (backward compatibility)
        parse_record_id("notebooks:550e8400-e29b-41d4-a716-446655440000")
        # Returns: "550e8400-e29b-41d4-a716-446655440000"
    """
    if ':' in record_id:
        # SurrealDB format: table:id
        return record_id.split(':', 1)[1]
    return record_id


def format_record_id(table: str, id: str) -> str:
    """
    Format record ID for compatibility.

    For SQLite/HANA: returns just the UUID.
    For SurrealDB compatibility: would return table:id.

    Args:
        table: Table name
        id: UUID string

    Returns:
        Formatted ID (currently just UUID)
    """
    # For SQL databases, we just use UUID
    # For SurrealDB compatibility, would return f"{table}:{id}"
    return id


# ============================================================================
# WORKFLOW REPOSITORY METHODS
# ============================================================================

async def create_workflow(
    name: str,
    graph_json: str,
    created_by: str,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> str:
    """
    Create a new workflow definition.

    Args:
        name: Workflow name
        graph_json: JSON serialized WorkflowGraph
        created_by: User ID
        description: Optional description
        tags: Optional list of tags

    Returns:
        Workflow UUID
    """
    import json

    workflow_id = generate_id()
    data = {
        "id": workflow_id,
        "name": name,
        "description": description,
        "graph_json": graph_json,
        "created_by": created_by,
        "created_at": get_timestamp(),
        "updated_at": get_timestamp(),
        "is_active": True,
        "tags": json.dumps(tags or []),
    }
    await repo_create("workflows", data)
    return workflow_id


async def get_workflow(workflow_id: str) -> Optional[Dict[str, Any]]:
    """Get workflow by ID."""
    return await repo_query(
        "SELECT * FROM workflows WHERE id = :id",
        {"id": workflow_id},
        fetch_one=True
    )


async def list_workflows(
    user_id: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    List workflows with optional filters.

    Args:
        user_id: Filter by creator
        is_active: Filter by active status
        limit: Max results
        offset: Skip results

    Returns:
        List of workflows
    """
    conditions = []
    params = {"limit": limit, "offset": offset}

    if user_id:
        conditions.append("created_by = :user_id")
        params["user_id"] = user_id

    if is_active is not None:
        conditions.append("is_active = :is_active")
        params["is_active"] = is_active

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    query = f"""
        SELECT * FROM workflows
        WHERE {where_clause}
        ORDER BY updated_at DESC
        LIMIT :limit OFFSET :offset
    """

    return await repo_query(query, params)


async def update_workflow(
    workflow_id: str,
    updates: Dict[str, Any]
) -> None:
    """
    Update workflow fields.

    Args:
        workflow_id: Workflow UUID
        updates: Dictionary of fields to update
    """
    updates["updated_at"] = get_timestamp()
    await repo_update("workflows", workflow_id, updates)


async def delete_workflow(workflow_id: str) -> None:
    """Delete workflow (cascade deletes executions and schedules)."""
    await repo_delete("workflows", workflow_id)


async def create_workflow_execution(
    workflow_id: str,
    status: str = "pending",
    triggered_by: str = "manual"
) -> str:
    """
    Create a new workflow execution record.

    Args:
        workflow_id: Workflow UUID
        status: Initial status
        triggered_by: Trigger source (manual, cron, event, dependency)

    Returns:
        Execution UUID
    """
    execution_id = generate_id()
    data = {
        "id": execution_id,
        "workflow_id": workflow_id,
        "status": status,
        "started_at": get_timestamp(),
        "triggered_by": triggered_by,
    }
    await repo_create("workflow_executions", data)
    return execution_id


async def get_workflow_execution(execution_id: str) -> Optional[Dict[str, Any]]:
    """Get execution by ID."""
    return await repo_query(
        "SELECT * FROM workflow_executions WHERE id = :id",
        {"id": execution_id},
        fetch_one=True
    )


async def list_workflow_executions(
    workflow_id: str,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    List executions for a workflow.

    Args:
        workflow_id: Workflow UUID
        status: Filter by status
        limit: Max results
        offset: Skip results

    Returns:
        List of executions
    """
    conditions = ["workflow_id = :workflow_id"]
    params = {"workflow_id": workflow_id, "limit": limit, "offset": offset}

    if status:
        conditions.append("status = :status")
        params["status"] = status

    where_clause = " AND ".join(conditions)
    query = f"""
        SELECT * FROM workflow_executions
        WHERE {where_clause}
        ORDER BY started_at DESC
        LIMIT :limit OFFSET :offset
    """

    return await repo_query(query, params)


async def update_workflow_execution(
    execution_id: str,
    updates: Dict[str, Any]
) -> None:
    """Update execution fields."""
    await repo_update("workflow_executions", execution_id, updates)


async def create_workflow_schedule(
    workflow_id: str,
    schedule_type: str,
    cron_expression: Optional[str] = None,
    event_trigger: Optional[str] = None,
    upstream_workflow_id: Optional[str] = None,
    enabled: bool = True
) -> str:
    """
    Create a workflow schedule.

    Args:
        workflow_id: Workflow UUID
        schedule_type: cron, event, dependency, manual
        cron_expression: Cron expression for cron schedules
        event_trigger: JSON serialized EventTrigger for event schedules
        upstream_workflow_id: Upstream workflow for dependency schedules
        enabled: Initial enabled state

    Returns:
        Schedule UUID
    """
    schedule_id = generate_id()
    data = {
        "id": schedule_id,
        "workflow_id": workflow_id,
        "schedule_type": schedule_type,
        "cron_expression": cron_expression,
        "event_trigger": event_trigger,
        "upstream_workflow_id": upstream_workflow_id,
        "enabled": enabled,
        "created_at": get_timestamp(),
        "updated_at": get_timestamp(),
    }
    await repo_create("workflow_schedules", data)
    return schedule_id


async def get_workflow_schedule(schedule_id: str) -> Optional[Dict[str, Any]]:
    """Get schedule by ID."""
    return await repo_query(
        "SELECT * FROM workflow_schedules WHERE id = :id",
        {"id": schedule_id},
        fetch_one=True
    )


async def list_workflow_schedules(
    workflow_id: Optional[str] = None,
    enabled: Optional[bool] = None,
    schedule_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List workflow schedules with optional filters.

    Args:
        workflow_id: Filter by workflow
        enabled: Filter by enabled status
        schedule_type: Filter by type

    Returns:
        List of schedules
    """
    conditions = []
    params = {}

    if workflow_id:
        conditions.append("workflow_id = :workflow_id")
        params["workflow_id"] = workflow_id

    if enabled is not None:
        conditions.append("enabled = :enabled")
        params["enabled"] = enabled

    if schedule_type:
        conditions.append("schedule_type = :schedule_type")
        params["schedule_type"] = schedule_type

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    query = f"""
        SELECT * FROM workflow_schedules
        WHERE {where_clause}
        ORDER BY created_at DESC
    """

    return await repo_query(query, params)


async def update_workflow_schedule(
    schedule_id: str,
    updates: Dict[str, Any]
) -> None:
    """Update schedule fields."""
    updates["updated_at"] = get_timestamp()
    await repo_update("workflow_schedules", schedule_id, updates)


async def delete_workflow_schedule(schedule_id: str) -> None:
    """Delete workflow schedule."""
    await repo_delete("workflow_schedules", schedule_id)


# ============================================================================
# TIMESTAMP UTILITIES
# ============================================================================

def get_timestamp() -> str:
    """
    Get current timestamp in ISO 8601 format.

    Returns:
        ISO 8601 timestamp string
    """
    return datetime.utcnow().isoformat()


# ============================================================================
# RELATIONSHIP HELPERS
# ============================================================================

async def add_relationship(
    junction_table: str,
    parent_id: str,
    child_id: str,
    parent_column: str = None,
    child_column: str = None
) -> None:
    """
    Add a many-to-many relationship.

    Args:
        junction_table: Junction table name (e.g., 'notebook_source')
        parent_id: Parent record UUID
        child_id: Child record UUID
        parent_column: Parent column name (default: inferred from table name)
        child_column: Child column name (default: inferred from table name)

    Example:
        # Add source to notebook
        await add_relationship('notebook_source', notebook_id, source_id)
    """
    # Infer column names if not provided
    if not parent_column:
        parent_column = junction_table.split('_')[0] + '_id'
    if not child_column:
        child_column = junction_table.split('_')[1] + '_id'

    data = {
        parent_column: parent_id,
        child_column: child_id,
        'created': get_timestamp()
    }

    # Use direct SQL INSERT OR IGNORE instead of upsert to avoid adding id/updated columns
    sql = f"""
        INSERT OR IGNORE INTO {junction_table} ({', '.join(data.keys())})
        VALUES ({', '.join([f':{k}' for k in data.keys()])})
    """
    await repo_execute(sql, data)


async def remove_relationship(
    junction_table: str,
    parent_id: str,
    child_id: str,
    parent_column: str = None,
    child_column: str = None
) -> None:
    """
    Remove a many-to-many relationship.

    Args:
        junction_table: Junction table name
        parent_id: Parent record UUID
        child_id: Child record UUID
        parent_column: Parent column name (default: inferred)
        child_column: Child column name (default: inferred)

    Example:
        # Remove source from notebook
        await remove_relationship('notebook_source', notebook_id, source_id)
    """
    # Infer column names if not provided
    if not parent_column:
        parent_column = junction_table.split('_')[0] + '_id'
    if not child_column:
        child_column = junction_table.split('_')[1] + '_id'

    sql = f"""
        DELETE FROM {junction_table}
        WHERE {parent_column} = :parent_id
        AND {child_column} = :child_id
    """

    async with db_connection() as db:
        await db.execute(sql, {
            'parent_id': parent_id,
            'child_id': child_id
        })


async def get_related_ids(
    junction_table: str,
    parent_id: str,
    parent_column: str = None,
    child_column: str = None
) -> List[str]:
    """
    Get IDs of related records in a many-to-many relationship.

    Args:
        junction_table: Junction table name
        parent_id: Parent record UUID
        parent_column: Parent column name (default: inferred)
        child_column: Child column name (default: inferred)

    Returns:
        List of child record UUIDs

    Example:
        # Get all source IDs for a notebook
        source_ids = await get_related_ids('notebook_source', notebook_id)
    """
    # Infer column names if not provided
    if not parent_column:
        parent_column = junction_table.split('_')[0] + '_id'
    if not child_column:
        child_column = junction_table.split('_')[1] + '_id'

    sql = f"""
        SELECT {child_column} as id
        FROM {junction_table}
        WHERE {parent_column} = :parent_id
    """

    results = await repo_query(sql, {'parent_id': parent_id})
    return [row['id'] for row in results]


# ============================================================================
# BULK OPERATIONS
# ============================================================================

async def bulk_create(
    table: str,
    records: List[Dict[str, Any]]
) -> List[str]:
    """
    Create multiple records efficiently.

    Args:
        table: Table name
        records: List of dictionaries with column values

    Returns:
        List of created record UUIDs

    Example:
        ids = await bulk_create('tags', [
            {'name': 'Important', 'color': '#FF0000'},
            {'name': 'Work', 'color': '#0000FF'}
        ])
    """
    if not records:
        return []

    # Add IDs and timestamps to all records
    now = get_timestamp()
    for record in records:
        if 'id' not in record:
            record['id'] = generate_id()
        if 'created' not in record:
            record['created'] = now
        if 'updated' not in record:
            record['updated'] = now

    # Build INSERT statement
    columns = list(records[0].keys())
    placeholders = [f":{col}" for col in columns]
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"

    async with db_connection() as db:
        await db.execute_many(sql, records)

    return [record['id'] for record in records]


# ============================================================================
# TRANSACTION SUPPORT
# ============================================================================

@asynccontextmanager
async def transaction():
    """
    Context manager for database transactions.

    Usage:
        async with transaction() as db:
            await db.create('notebooks', {...})
            await db.create('sources', {...})
            # Commits on success, rolls back on exception

    Yields:
        DatabaseInterface instance with transaction support
    """
    db = get_database()
    await db.connect()

    try:
        async with db.begin_transaction():
            yield db
    finally:
        await db.disconnect()


# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

# Global database instance
_db_instance: Optional[DatabaseInterface] = None


async def init_database() -> DatabaseInterface:
    """
    Initialize the database connection.

    Should be called on application startup.
    Creates and caches a database instance.

    Returns:
        DatabaseInterface instance

    Example:
        # In FastAPI startup
        @app.on_event("startup")
        async def startup():
            await init_database()
    """
    global _db_instance

    if _db_instance is not None:
        return _db_instance

    # Get database from config
    _db_instance = get_database()
    await _db_instance.connect()

    return _db_instance


async def close_database() -> None:
    """
    Close the database connection.

    Should be called on application shutdown.

    Example:
        # In FastAPI shutdown
        @app.on_event("shutdown")
        async def shutdown():
            await close_database()
    """
    global _db_instance

    if _db_instance is not None:
        await _db_instance.disconnect()
        _db_instance = None


def get_database_instance() -> Optional[DatabaseInterface]:
    """
    Get the cached database instance.

    Returns:
        DatabaseInterface instance or None if not initialized
    """
    return _db_instance
