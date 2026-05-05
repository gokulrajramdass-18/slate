"""
HANA Table Source Sync

Handles periodic synchronization of data from HANA database tables:
- Connects to HANA using connection config
- Executes queries or SELECT * from table
- Extracts text from configured columns
- Detects changes using hash-based comparison
- Updates full_text and triggers embedding regeneration
"""

import hashlib
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from open_notebook.database.interface import ConnectionConfig
from open_notebook.database.hana_impl import HANADatabase
from open_notebook.database.repository import repo_query, repo_create, repo_update, repo_delete

logger = logging.getLogger(__name__)


async def sync_hana_table(source: Dict[str, Any]) -> int:
    """
    Sync HANA table source

    Args:
        source: Source record with connection_config and sync_config

    Returns:
        Number of rows updated

    Process:
        1. Connect to HANA database
        2. Execute query or SELECT * FROM table
        3. Extract text from configured columns
        4. Compare with existing data (hash-based)
        5. Update changed records
        6. Trigger embedding regeneration for changes
    """
    rows_updated = 0
    db = None

    try:
        # Parse connection config
        conn_config_data = source.get("connection_config", {})
        if isinstance(conn_config_data, str):
            conn_config_data = json.loads(conn_config_data)

        # Get connection details
        connection = conn_config_data.get("connection", {})
        table_name = conn_config_data.get("table_name")
        query = conn_config_data.get("query")
        key_column = conn_config_data.get("key_column", "id")
        content_columns = conn_config_data.get("content_columns", [])

        if not table_name:
            raise ValueError("table_name is required in connection_config")

        if not content_columns:
            raise ValueError("content_columns is required in connection_config")

        logger.info(f"Syncing HANA table: {table_name}")

        # Create HANA connection
        conn_config = ConnectionConfig(
            db_type="hana",
            host=connection.get("host"),
            port=connection.get("port", 443),
            database=connection.get("database"),
            user=connection.get("user"),
            password=connection.get("password"),
            encrypt=connection.get("encrypt", True)
        )

        db = HANADatabase(conn_config)
        await db.connect()

        # Build and execute query
        if query:
            # Use custom query
            sql = query
            params = {}
        else:
            # Default: SELECT * FROM table
            sql = f"SELECT * FROM {table_name}"
            params = {}

        logger.info(f"Executing query: {sql}")
        rows = await db.query(sql, params)

        logger.info(f"Retrieved {len(rows)} rows from HANA table")

        # Process each row
        for row in rows:
            try:
                # Extract key value
                key_value = row.get(key_column)
                if not key_value:
                    logger.warning(f"Row missing key column '{key_column}', skipping")
                    continue

                # Extract text from configured columns
                text_parts = []
                for col in content_columns:
                    value = row.get(col)
                    if value is not None:
                        text_parts.append(f"{col}: {value}")

                full_text = "\n".join(text_parts)

                # Calculate content hash
                content_hash = hashlib.sha256(full_text.encode()).hexdigest()

                # Create metadata
                metadata = {
                    "source_id": source["id"],
                    "source_type": "hana_table",
                    "table_name": table_name,
                    "key_column": key_column,
                    "key_value": str(key_value),
                    "synced_at": datetime.utcnow().isoformat(),
                    "row_data": {k: str(v) for k, v in row.items()}  # Store all columns
                }

                # Check if embedding exists
                existing = await repo_query(
                    """
                    SELECT id, content_hash, full_text
                    FROM source_embeddings
                    WHERE source_id = :source_id
                    AND metadata LIKE :key_filter
                    """,
                    {
                        "source_id": source["id"],
                        "key_filter": f'%"key_value":"{key_value}"%'
                    }
                )

                if existing:
                    # Check if content changed
                    existing_record = existing[0]
                    if existing_record.get("content_hash") != content_hash:
                        # Update existing record
                        await repo_update(
                            "source_embeddings",
                            existing_record["id"],
                            {
                                "full_text": full_text,
                                "content_hash": content_hash,
                                "metadata": json.dumps(metadata),
                                "embedding": None,  # Clear embedding to trigger regeneration
                                "updated": datetime.utcnow().isoformat()
                            }
                        )
                        rows_updated += 1
                        logger.debug(f"Updated record for key {key_value}")
                else:
                    # Create new record
                    await repo_create(
                        "source_embeddings",
                        {
                            "source_id": source["id"],
                            "chunk_index": 0,
                            "full_text": full_text,
                            "content_hash": content_hash,
                            "metadata": json.dumps(metadata),
                            "embedding": None  # Will be generated by embedding service
                        }
                    )
                    rows_updated += 1
                    logger.debug(f"Created new record for key {key_value}")

            except Exception as e:
                logger.error(f"Failed to process row: {e}")
                continue

        # Clean up deleted rows (rows that exist in embeddings but not in source)
        # Get all embedding keys
        all_embeddings = await repo_query(
            """
            SELECT id, metadata
            FROM source_embeddings
            WHERE source_id = :source_id
            """,
            {"source_id": source["id"]}
        )

        # Get keys from current sync
        synced_keys = {str(row.get(key_column)) for row in rows}

        for emb in all_embeddings:
            try:
                emb_metadata = json.loads(emb["metadata"]) if isinstance(emb["metadata"], str) else emb["metadata"]
                emb_key = emb_metadata.get("key_value")

                if emb_key and emb_key not in synced_keys:
                    # This record no longer exists in source, delete it
                    await repo_delete("source_embeddings", emb["id"])
                    logger.debug(f"Deleted stale record for key {emb_key}")
            except Exception as e:
                logger.error(f"Failed to check stale record: {e}")

        logger.info(f"HANA table sync completed: {rows_updated} rows updated")

    except Exception as e:
        logger.error(f"HANA table sync failed: {e}", exc_info=True)
        raise

    finally:
        if db:
            await db.disconnect()

    return rows_updated


async def test_hana_connection(
    connection: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Test HANA database connection

    Args:
        connection: Connection configuration dict

    Returns:
        Dict with success status and details
    """
    db = None

    try:
        # Create connection config
        conn_config = ConnectionConfig(
            db_type="hana",
            host=connection.get("host"),
            port=connection.get("port", 443),
            database=connection.get("database"),
            user=connection.get("user"),
            password=connection.get("password"),
            encrypt=connection.get("encrypt", True)
        )

        # Test connection
        db = HANADatabase(conn_config)
        start_time = datetime.utcnow()

        await db.connect()

        # Get version
        result = await db.query("SELECT VERSION FROM SYS.M_DATABASE", fetch_one=True)
        version = result.get("VERSION") if result else None

        # Calculate latency
        latency = (datetime.utcnow() - start_time).total_seconds() * 1000

        return {
            "success": True,
            "message": "Successfully connected to HANA database",
            "server_version": version,
            "latency_ms": round(latency, 2)
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Connection failed: {str(e)}",
            "error": str(e)
        }

    finally:
        if db:
            await db.disconnect()


async def get_hana_tables(
    connection: Dict[str, Any],
    schema: Optional[str] = None
) -> List[str]:
    """
    Get list of tables from HANA database

    Args:
        connection: Connection configuration
        schema: Optional schema name

    Returns:
        List of table names
    """
    db = None

    try:
        # Create connection config
        conn_config = ConnectionConfig(
            db_type="hana",
            host=connection.get("host"),
            port=connection.get("port", 443),
            database=connection.get("database"),
            user=connection.get("user"),
            password=connection.get("password"),
            encrypt=connection.get("encrypt", True)
        )

        # Connect
        db = HANADatabase(conn_config)
        await db.connect()

        # Query tables
        if schema:
            sql = """
                SELECT TABLE_NAME
                FROM SYS.TABLES
                WHERE SCHEMA_NAME = :schema
                ORDER BY TABLE_NAME
            """
            params = {"schema": schema}
        else:
            sql = """
                SELECT TABLE_NAME
                FROM SYS.TABLES
                WHERE SCHEMA_NAME = CURRENT_SCHEMA
                ORDER BY TABLE_NAME
            """
            params = {}

        results = await db.query(sql, params)
        return [row["TABLE_NAME"] for row in results]

    except Exception as e:
        logger.error(f"Failed to get HANA tables: {e}")
        raise

    finally:
        if db:
            await db.disconnect()


async def get_hana_table_columns(
    connection: Dict[str, Any],
    table_name: str,
    schema: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get columns for a HANA table

    Args:
        connection: Connection configuration
        table_name: Table name
        schema: Optional schema name

    Returns:
        List of column definitions
    """
    db = None

    try:
        # Create connection config
        conn_config = ConnectionConfig(
            db_type="hana",
            host=connection.get("host"),
            port=connection.get("port", 443),
            database=connection.get("database"),
            user=connection.get("user"),
            password=connection.get("password"),
            encrypt=connection.get("encrypt", True)
        )

        # Connect
        db = HANADatabase(conn_config)
        await db.connect()

        # Query columns
        if schema:
            sql = """
                SELECT COLUMN_NAME, DATA_TYPE_NAME, LENGTH, IS_NULLABLE
                FROM SYS.TABLE_COLUMNS
                WHERE SCHEMA_NAME = :schema AND TABLE_NAME = :table
                ORDER BY POSITION
            """
            params = {"schema": schema, "table": table_name}
        else:
            sql = """
                SELECT COLUMN_NAME, DATA_TYPE_NAME, LENGTH, IS_NULLABLE
                FROM SYS.TABLE_COLUMNS
                WHERE SCHEMA_NAME = CURRENT_SCHEMA AND TABLE_NAME = :table
                ORDER BY POSITION
            """
            params = {"table": table_name}

        results = await db.query(sql, params)
        return [
            {
                "name": row["COLUMN_NAME"],
                "type": row["DATA_TYPE_NAME"],
                "length": row.get("LENGTH"),
                "nullable": row.get("IS_NULLABLE") == "TRUE"
            }
            for row in results
        ]

    except Exception as e:
        logger.error(f"Failed to get table columns: {e}")
        raise

    finally:
        if db:
            await db.disconnect()
