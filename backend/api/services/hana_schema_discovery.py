"""
HANA Schema Discovery Service

Discovers tables and columns from HANA databases and caches them locally.
Used for building tools and understanding HANA data structures.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from hdbcli import dbapi

from open_notebook.database.repository import repo_query, repo_create, repo_execute
from api.services.hana_connection_utils import decrypt_password, get_connection_by_id


logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

MAX_TABLES = 500
QUERY_TIMEOUT = 120  # 2 minutes in seconds

# System schemas to exclude
EXCLUDED_SCHEMAS = [
    'SYS',
    '_SYS_AFL',
    '_SYS_BI',
    '_SYS_BIC',
    '_SYS_EPM',
    '_SYS_REPO',
    '_SYS_RT',
    '_SYS_STATISTICS',
    '_SYS_TASK',
    '_SYS_XS',
]


# ============================================================================
# Discovery Functions
# ============================================================================

async def discover_tables(connection_id: str) -> List[Dict[str, Any]]:
    """
    Discover tables from HANA database

    Queries SYS.TABLES and SYS.TABLE_COLUMNS to get comprehensive table metadata.
    Excludes system schemas and limits to MAX_TABLES.

    Args:
        connection_id: ID of the HANA connection

    Returns:
        List of table metadata dictionaries with:
        - schema_name: Schema name
        - table_name: Table name
        - table_type: Type (TABLE, VIEW, etc.)
        - columns: List of column metadata dicts
        - row_count: Approximate row count

    Raises:
        ValueError: If connection not found
        Exception: If discovery fails
    """
    logger.info(f"🔍 Starting table discovery for connection {connection_id}")

    # Get connection details
    connection = await get_connection_by_id(connection_id)
    if not connection:
        raise ValueError(f"Connection {connection_id} not found")

    # Decrypt password
    password = decrypt_password(connection["password_encrypted"])

    # Connect to HANA
    db_connection = None
    cursor = None

    try:
        # Connection parameters
        conn_params = {
            'address': connection["host"],
            'port': connection["port"],
            'user': connection["user"],
            'password': password,
            'encrypt': bool(connection["encrypt"]),
            'sslValidateCertificate': False  # For development
        }

        logger.info(f"Connecting to HANA at {connection['host']}:{connection['port']}")
        db_connection = dbapi.connect(**conn_params)
        cursor = db_connection.cursor()

        # Build schema exclusion filter
        schema_placeholders = ', '.join(['?' for _ in EXCLUDED_SCHEMAS])

        # Query tables (excluding system schemas)
        tables_sql = f"""
            SELECT
                SCHEMA_NAME,
                TABLE_NAME,
                TABLE_TYPE,
                RECORD_COUNT
            FROM SYS.M_TABLES
            WHERE SCHEMA_NAME NOT IN ({schema_placeholders})
            AND IS_TEMPORARY = 'FALSE'
            ORDER BY SCHEMA_NAME, TABLE_NAME
            LIMIT {MAX_TABLES}
        """

        logger.info("Querying HANA tables...")
        cursor.execute(tables_sql, EXCLUDED_SCHEMAS)
        table_rows = cursor.fetchall()

        logger.info(f"Found {len(table_rows)} tables. Fetching column metadata...")

        # Prepare results
        tables = []

        # For each table, get columns
        for idx, table_row in enumerate(table_rows, 1):
            schema_name = table_row[0]
            table_name = table_row[1]
            table_type = table_row[2]
            row_count = table_row[3] or 0

            # Query columns for this table
            columns_sql = """
                SELECT
                    COLUMN_NAME,
                    DATA_TYPE_NAME,
                    LENGTH,
                    SCALE,
                    IS_NULLABLE,
                    POSITION
                FROM SYS.TABLE_COLUMNS
                WHERE SCHEMA_NAME = ?
                AND TABLE_NAME = ?
                ORDER BY POSITION
            """

            cursor.execute(columns_sql, (schema_name, table_name))
            column_rows = cursor.fetchall()

            # Build column metadata
            columns = []
            for col_row in column_rows:
                column_meta = {
                    'name': col_row[0],
                    'type': col_row[1],
                    'length': col_row[2],
                    'scale': col_row[3],
                    'nullable': col_row[4] == 'TRUE',
                    'position': col_row[5]
                }
                columns.append(column_meta)

            # Add table metadata
            table_meta = {
                'schema_name': schema_name,
                'table_name': table_name,
                'table_type': table_type,
                'columns': columns,
                'row_count': row_count
            }
            tables.append(table_meta)

            # Log progress every 50 tables
            if idx % 50 == 0:
                logger.info(f"Progress: {idx}/{len(table_rows)} tables processed")

        logger.info(f"✅ Discovery complete. Found {len(tables)} tables with column metadata")
        return tables

    except Exception as e:
        logger.error(f"❌ Table discovery failed: {str(e)}")
        raise Exception(f"Failed to discover tables: {str(e)}")

    finally:
        # Close connection
        if cursor:
            try:
                cursor.close()
            except:
                pass

        if db_connection:
            try:
                db_connection.close()
            except:
                pass


async def store_discovered_tables(connection_id: str, tables: List[Dict[str, Any]]) -> int:
    """
    Store discovered tables in local database

    Deletes existing records for this connection and inserts new ones.

    Args:
        connection_id: ID of the HANA connection
        tables: List of table metadata from discover_tables()

    Returns:
        Count of tables stored

    Raises:
        Exception: If storage fails
    """
    logger.info(f"💾 Storing {len(tables)} discovered tables for connection {connection_id}")

    try:
        # Delete existing records for this connection
        delete_sql = "DELETE FROM hana_connection_tables WHERE connection_id = :connection_id"
        await repo_execute(delete_sql, {"connection_id": connection_id})

        # Insert new records
        now = datetime.utcnow().isoformat()
        stored_count = 0

        for table in tables:
            # Serialize column metadata to JSON
            column_metadata_json = json.dumps(table['columns'])

            # Create record
            data = {
                'id': str(uuid.uuid4()),
                'connection_id': connection_id,
                'schema_name': table['schema_name'],
                'table_name': table['table_name'],
                'table_type': table['table_type'],
                'column_metadata': column_metadata_json,
                'row_count': table['row_count'],
                'discovered_at': now
            }

            await repo_create('hana_connection_tables', data)
            stored_count += 1

        logger.info(f"✅ Stored {stored_count} tables successfully")
        return stored_count

    except Exception as e:
        logger.error(f"❌ Failed to store discovered tables: {str(e)}")
        raise Exception(f"Failed to store tables: {str(e)}")


async def refresh_table_metadata(connection_id: str) -> int:
    """
    Refresh table metadata for a connection

    Discovers tables from HANA and stores them locally.
    This is the main entry point for schema discovery.

    Args:
        connection_id: ID of the HANA connection

    Returns:
        Count of tables refreshed

    Raises:
        ValueError: If connection not found
        Exception: If refresh fails
    """
    logger.info(f"🔄 Refreshing table metadata for connection {connection_id}")

    try:
        # Discover tables
        tables = await discover_tables(connection_id)

        # Store in database
        count = await store_discovered_tables(connection_id, tables)

        logger.info(f"✅ Successfully refreshed {count} tables")
        return count

    except ValueError:
        # Connection not found - re-raise
        raise

    except Exception as e:
        logger.error(f"❌ Refresh failed: {str(e)}")
        # Log but don't fail completely - return 0
        return 0


async def get_tables_for_connection(connection_id: str) -> List[Dict[str, Any]]:
    """
    Get cached table metadata for a connection

    Returns tables that were previously discovered and stored.

    Args:
        connection_id: ID of the HANA connection

    Returns:
        List of table metadata dictionaries with:
        - id: Record ID
        - connection_id: Connection ID
        - schema_name: Schema name
        - table_name: Table name
        - table_type: Type (TABLE, VIEW, etc.)
        - columns: List of column metadata (parsed from JSON)
        - row_count: Approximate row count
        - discovered_at: Timestamp of discovery

    Raises:
        Exception: If query fails
    """
    logger.info(f"📖 Retrieving cached tables for connection {connection_id}")

    try:
        sql = """
            SELECT
                id,
                connection_id,
                schema_name,
                table_name,
                table_type,
                column_metadata,
                row_count,
                discovered_at
            FROM hana_connection_tables
            WHERE connection_id = :connection_id
            ORDER BY schema_name, table_name
        """

        results = await repo_query(sql, {"connection_id": connection_id})

        # Parse column metadata from JSON
        tables = []
        for row in results:
            table = {
                'id': row['id'],
                'connection_id': row['connection_id'],
                'schema_name': row['schema_name'],
                'table_name': row['table_name'],
                'table_type': row['table_type'],
                'columns': json.loads(row['column_metadata']) if row['column_metadata'] else [],
                'row_count': row['row_count'],
                'discovered_at': row['discovered_at']
            }
            tables.append(table)

        logger.info(f"✅ Retrieved {len(tables)} cached tables")
        return tables

    except Exception as e:
        logger.error(f"❌ Failed to retrieve cached tables: {str(e)}")
        raise Exception(f"Failed to get tables: {str(e)}")


async def get_table_details(connection_id: str, schema_name: str, table_name: str) -> Optional[Dict[str, Any]]:
    """
    Get details for a specific table

    Args:
        connection_id: ID of the HANA connection
        schema_name: Schema name
        table_name: Table name

    Returns:
        Table metadata dict or None if not found

    Raises:
        Exception: If query fails
    """
    logger.info(f"📖 Retrieving table details: {schema_name}.{table_name}")

    try:
        sql = """
            SELECT
                id,
                connection_id,
                schema_name,
                table_name,
                table_type,
                column_metadata,
                row_count,
                discovered_at
            FROM hana_connection_tables
            WHERE connection_id = :connection_id
            AND schema_name = :schema_name
            AND table_name = :table_name
        """

        results = await repo_query(sql, {
            "connection_id": connection_id,
            "schema_name": schema_name,
            "table_name": table_name
        })

        if not results:
            return None

        row = results[0]
        table = {
            'id': row['id'],
            'connection_id': row['connection_id'],
            'schema_name': row['schema_name'],
            'table_name': row['table_name'],
            'table_type': row['table_type'],
            'columns': json.loads(row['column_metadata']) if row['column_metadata'] else [],
            'row_count': row['row_count'],
            'discovered_at': row['discovered_at']
        }

        return table

    except Exception as e:
        logger.error(f"❌ Failed to retrieve table details: {str(e)}")
        raise Exception(f"Failed to get table details: {str(e)}")
