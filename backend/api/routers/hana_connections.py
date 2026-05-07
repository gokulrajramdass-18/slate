"""
HANA Connections Router

Manages saved HANA database connections that can be reused across multiple sources.
"""

import json
from typing import List, Optional
from datetime import datetime
import uuid
import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict

from open_notebook.database.repository import repo_query, repo_create, repo_update, repo_delete
from api.services.hana_connection_utils import encrypt_password, decrypt_password, get_connection_by_id
from api.services.hana_schema_discovery import refresh_table_metadata, get_tables_for_connection

router = APIRouter(prefix="/api/hana-connections", tags=["hana-connections"])

logger = logging.getLogger(__name__)


# ============================================================================
# Models
# ============================================================================

class HANAConnectionBase(BaseModel):
    """Base HANA connection model"""
    model_config = ConfigDict(protected_namespaces=())  # Allow 'schema' field

    name: str = Field(..., min_length=1, max_length=255, description="Connection name")
    host: str = Field(..., description="HANA server hostname or IP")
    port: int = Field(default=443, ge=1, le=65535, description="Port number")
    database: str = Field(..., description="Database name")
    user: str = Field(..., description="Database username")
    password: str = Field(..., description="Database password (will be encrypted)")
    encrypt: bool = Field(default=True, description="Use encrypted connection (SSL/TLS)")
    schema: Optional[str] = Field(None, description="Default schema")
    description: Optional[str] = Field(None, description="Connection description")


class HANAConnectionCreate(HANAConnectionBase):
    """Model for creating a HANA connection"""
    pass


class HANAConnectionUpdate(BaseModel):
    """Model for updating a HANA connection (all fields optional)"""
    model_config = ConfigDict(protected_namespaces=())  # Allow 'schema' field

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    host: Optional[str] = None
    port: Optional[int] = Field(None, ge=1, le=65535)
    database: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None  # Only update if provided
    encrypt: Optional[bool] = None
    schema: Optional[str] = None
    description: Optional[str] = None


class HANAConnectionResponse(BaseModel):
    """Model for HANA connection responses (password hidden)"""
    model_config = ConfigDict(protected_namespaces=())  # Allow 'schema' field

    id: str
    name: str
    host: str
    port: int
    database: str
    user: str
    encrypt: bool
    schema: Optional[str] = None
    description: Optional[str] = None
    created: str
    updated: str


class HANAConnectionTestRequest(BaseModel):
    """Request to test a HANA connection"""
    connection_id: str


class HANAConnectionTestResponse(BaseModel):
    """Response from connection test"""
    success: bool
    message: str
    server_version: Optional[str] = None
    latency_ms: Optional[float] = None


class HANADiscoverTablesResponse(BaseModel):
    """Response from table discovery"""
    success: bool
    connection_id: str
    tables_discovered: int
    discovered_at: str


class HANAListTablesResponse(BaseModel):
    """Response from listing discovered tables"""
    connection_id: str
    tables: List[dict]
    count: int


# ============================================================================
# Endpoints
# ============================================================================

@router.post("", response_model=HANAConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_connection(connection: HANAConnectionCreate):
    """
    Create a new HANA connection

    Password will be encrypted before storage.
    """
    try:
        # Check if name already exists
        existing = await repo_query(
            "SELECT id FROM hana_connections WHERE name = :name",
            {"name": connection.name}
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Connection with name '{connection.name}' already exists"
            )

        # Encrypt password
        encrypted_password = encrypt_password(connection.password)

        # Create connection
        connection_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        data = {
            "id": connection_id,
            "name": connection.name,
            "host": connection.host,
            "port": connection.port,
            "database": connection.database,
            "user": connection.user,
            "password_encrypted": encrypted_password,
            "encrypt": 1 if connection.encrypt else 0,
            "schema": connection.schema,
            "description": connection.description,
            "created": now,
            "updated": now,
        }

        await repo_create("hana_connections", data)

        # Trigger table discovery (don't fail if it errors)
        try:
            logger.info(f"🔍 Triggering table discovery for connection {connection_id}")
            tables_count = await refresh_table_metadata(connection_id)
            logger.info(f"✅ Discovered {tables_count} tables for connection {connection_id}")
        except Exception as e:
            logger.warning(f"⚠️ Table discovery failed for connection {connection_id}: {str(e)}")
            # Don't fail connection creation if discovery fails

        # Return response (without password)
        return HANAConnectionResponse(
            id=connection_id,
            name=connection.name,
            host=connection.host,
            port=connection.port,
            database=connection.database,
            user=connection.user,
            encrypt=connection.encrypt,
            schema=connection.schema,
            description=connection.description,
            created=now,
            updated=now,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create connection: {str(e)}",
        )


@router.get("", response_model=List[HANAConnectionResponse])
async def list_connections():
    """
    List all HANA connections

    Passwords are not included in responses.
    """
    try:
        sql = """
            SELECT id, name, host, port, database, user, encrypt, schema, description, created, updated
            FROM hana_connections
            ORDER BY name
        """
        connections = await repo_query(sql, {})

        return [
            HANAConnectionResponse(
                id=conn["id"],
                name=conn["name"],
                host=conn["host"],
                port=conn["port"],
                database=conn["database"],
                user=conn["user"],
                encrypt=bool(conn["encrypt"]),
                schema=conn.get("schema"),
                description=conn.get("description"),
                created=conn["created"],
                updated=conn["updated"],
            )
            for conn in connections
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list connections: {str(e)}",
        )


@router.get("/{connection_id}", response_model=HANAConnectionResponse)
async def get_connection(connection_id: str):
    """
    Get a specific HANA connection by ID

    Password is not included in response.
    """
    try:
        connection = await get_connection_by_id(connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection {connection_id} not found"
            )

        return HANAConnectionResponse(
            id=connection["id"],
            name=connection["name"],
            host=connection["host"],
            port=connection["port"],
            database=connection["database"],
            user=connection["user"],
            encrypt=bool(connection["encrypt"]),
            schema=connection.get("schema"),
            description=connection.get("description"),
            created=connection["created"],
            updated=connection["updated"],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get connection: {str(e)}",
        )


@router.put("/{connection_id}", response_model=HANAConnectionResponse)
async def update_connection(connection_id: str, update: HANAConnectionUpdate):
    """
    Update a HANA connection

    Only provided fields will be updated. Password will be re-encrypted if changed.
    """
    try:
        # Check if connection exists
        existing = await get_connection_by_id(connection_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection {connection_id} not found"
            )

        # Build update data
        update_data = {}
        if update.name is not None:
            # Check if new name conflicts with existing
            name_check = await repo_query(
                "SELECT id FROM hana_connections WHERE name = :name AND id != :id",
                {"name": update.name, "id": connection_id}
            )
            if name_check:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Connection with name '{update.name}' already exists"
                )
            update_data["name"] = update.name

        if update.host is not None:
            update_data["host"] = update.host
        if update.port is not None:
            update_data["port"] = update.port
        if update.database is not None:
            update_data["database"] = update.database
        if update.user is not None:
            update_data["user"] = update.user
        if update.password is not None:
            update_data["password_encrypted"] = encrypt_password(update.password)
        if update.encrypt is not None:
            update_data["encrypt"] = 1 if update.encrypt else 0
        if update.schema is not None:
            update_data["schema"] = update.schema
        if update.description is not None:
            update_data["description"] = update.description

        update_data["updated"] = datetime.utcnow().isoformat()

        # Update connection
        await repo_update("hana_connections", connection_id, update_data)

        # Get updated connection
        updated_conn = await get_connection_by_id(connection_id)

        return HANAConnectionResponse(
            id=updated_conn["id"],
            name=updated_conn["name"],
            host=updated_conn["host"],
            port=updated_conn["port"],
            database=updated_conn["database"],
            user=updated_conn["user"],
            encrypt=bool(updated_conn["encrypt"]),
            schema=updated_conn.get("schema"),
            description=updated_conn.get("description"),
            created=updated_conn["created"],
            updated=updated_conn["updated"],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update connection: {str(e)}",
        )


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(connection_id: str):
    """
    Delete a HANA connection

    Warning: This will not affect existing sources using this connection,
    as they store a copy of the connection config.
    """
    try:
        # Check if connection exists
        existing = await get_connection_by_id(connection_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection {connection_id} not found"
            )

        # Delete connection
        await repo_delete("hana_connections", connection_id)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete connection: {str(e)}",
        )


@router.post("/test", response_model=HANAConnectionTestResponse)
async def test_connection(request: HANAConnectionTestRequest):
    """
    Test a saved HANA connection

    Attempts to connect and retrieve server version.
    """
    try:
        # Get connection
        connection = await get_connection_by_id(request.connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection {request.connection_id} not found"
            )

        # Decrypt password
        password = decrypt_password(connection["password_encrypted"])

        # Test connection
        import time
        from hdbcli import dbapi

        conn_params = {
            'address': connection["host"],
            'port': connection["port"],
            'user': connection["user"],
            'password': password,
            'encrypt': bool(connection["encrypt"]),
            'sslValidateCertificate': False  # For development
        }

        start_time = time.time()
        db_connection = dbapi.connect(**conn_params)
        cursor = db_connection.cursor()
        latency_ms = (time.time() - start_time) * 1000

        # Get version
        cursor.execute("SELECT VERSION FROM SYS.M_DATABASE")
        result = cursor.fetchone()
        server_version = result[0] if result else None

        cursor.close()
        db_connection.close()

        return HANAConnectionTestResponse(
            success=True,
            message="Connection successful",
            server_version=server_version,
            latency_ms=round(latency_ms, 2)
        )

    except HTTPException:
        raise
    except Exception as e:
        return HANAConnectionTestResponse(
            success=False,
            message=f"Connection failed: {str(e)}",
            server_version=None,
            latency_ms=None
        )


@router.post("/{connection_id}/discover-tables", response_model=HANADiscoverTablesResponse)
async def discover_tables(connection_id: str):
    """
    Manually trigger table discovery for a HANA connection

    Discovers all tables and columns from the HANA database and caches them locally.
    This can take some time for large databases.
    """
    try:
        # Check if connection exists
        connection = await get_connection_by_id(connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection {connection_id} not found"
            )

        # Trigger discovery
        logger.info(f"🔍 Starting table discovery for connection {connection_id}")
        tables_count = await refresh_table_metadata(connection_id)
        discovered_at = datetime.utcnow().isoformat()

        logger.info(f"✅ Discovered {tables_count} tables for connection {connection_id}")

        return HANADiscoverTablesResponse(
            success=True,
            connection_id=connection_id,
            tables_discovered=tables_count,
            discovered_at=discovered_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Table discovery failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to discover tables: {str(e)}",
        )


@router.get("/{connection_id}/discovered-tables", response_model=HANAListTablesResponse)
async def get_discovered_tables(connection_id: str):
    """
    List all discovered tables for a HANA connection

    Returns tables that were previously discovered and cached locally.
    If no tables are found, you may need to trigger discovery first.
    """
    try:
        # Check if connection exists
        connection = await get_connection_by_id(connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection {connection_id} not found"
            )

        # Get cached tables
        tables = await get_tables_for_connection(connection_id)

        return HANAListTablesResponse(
            connection_id=connection_id,
            tables=tables,
            count=len(tables)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to retrieve discovered tables: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve discovered tables: {str(e)}",
        )


@router.get("/{connection_id}/tables")
async def list_tables(connection_id: str, schema: Optional[str] = None):
    """
    List tables available in a HANA connection

    Returns table names and basic metadata.
    If no schema specified, uses CURRENT_SCHEMA or lists all accessible tables.
    """
    import sys
    print(f"[HANA] ========== list_tables ENTRY POINT ==========", file=sys.stderr, flush=True)
    print(f"[HANA] list_tables called for connection {connection_id}, schema={schema}", flush=True)
    try:
        # Get connection
        connection = await get_connection_by_id(connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection {connection_id} not found"
            )

        print(f"[HANA] Connection found, decrypting password...")
        # Decrypt password
        password = decrypt_password(connection["password_encrypted"])

        # Connect and list tables
        from hdbcli import dbapi

        conn_params = {
            'address': connection["host"],
            'port': connection["port"],
            'user': connection["user"],
            'password': password,
            'encrypt': bool(connection["encrypt"]),
            'sslValidateCertificate': False
        }

        db_connection = dbapi.connect(**conn_params)
        cursor = db_connection.cursor()

        # Debug: Show current user and available schemas
        try:
            cursor.execute("SELECT CURRENT_USER FROM DUMMY")
            current_user = cursor.fetchone()[0]
            print(f"[HANA] Connected as user: {current_user}")

            cursor.execute("SELECT DISTINCT SCHEMA_NAME FROM SYS.M_TABLES ORDER BY SCHEMA_NAME LIMIT 20")
            all_schemas = [row[0] for row in cursor.fetchall()]
            print(f"[HANA] Available schemas (first 20): {all_schemas}")
        except Exception as e:
            print(f"[HANA] Debug query failed: {e}")

        # Determine schema to use (from parameter, connection config, or current schema)
        schema_filter = schema or connection.get("schema")

        # If no schema specified, try to get the user's current schema
        if not schema_filter:
            try:
                cursor.execute("SELECT CURRENT_SCHEMA FROM DUMMY")
                result = cursor.fetchone()
                if result and result[0]:
                    schema_filter = result[0]
            except Exception:
                pass  # If fails, will list all accessible schemas below

        tables = []

        if schema_filter:
            # Query specific schema - use TABLES view instead of M_TABLES to include virtual tables
            query = """
                SELECT SCHEMA_NAME, TABLE_NAME, TABLE_TYPE, 0 as RECORD_COUNT
                FROM SYS.TABLES
                WHERE SCHEMA_NAME = ?
                AND IS_USER_DEFINED_TYPE = 'FALSE'
                ORDER BY TABLE_NAME
            """
            print(f"[HANA] Executing query with schema_filter: {schema_filter}")
            print(f"[HANA] Using SYS.TABLES to include virtual tables")
            cursor.execute(query, (schema_filter,))

            rows = cursor.fetchall()
            print(f"[HANA] Query returned {len(rows)} rows")

            for row in rows:
                tables.append({
                    "schema_name": row[0],
                    "table_name": row[1],
                    "table_type": row[2],
                    "record_count": row[3] if len(row) > 3 else 0
                })

        # If no tables found or no schema specified, list all accessible tables
        if not tables:
            # List all tables from non-system schemas - use TABLES view to include virtual tables
            query = """
                SELECT SCHEMA_NAME, TABLE_NAME, TABLE_TYPE, 0 as RECORD_COUNT
                FROM SYS.TABLES
                WHERE SCHEMA_NAME NOT LIKE '_SYS%'
                AND SCHEMA_NAME NOT IN ('SYS', 'SYSTEM')
                AND IS_USER_DEFINED_TYPE = 'FALSE'
                ORDER BY SCHEMA_NAME, TABLE_NAME
                LIMIT 1000
            """
            print(f"[HANA] No tables found with schema filter, trying fallback query")
            print(f"[HANA] Using SYS.TABLES to include virtual tables")
            cursor.execute(query)

            rows = cursor.fetchall()
            print(f"[HANA] Fallback query returned {len(rows)} rows")

            for row in rows:
                tables.append({
                    "schema_name": row[0],
                    "table_name": row[1],
                    "table_type": row[2],
                    "record_count": row[3] if len(row) > 3 else 0
                })

        cursor.close()
        db_connection.close()

        print(f"[HANA] Found {len(tables)} tables for connection {connection_id}, schema_filter: {schema_filter}")

        # Return array format for consistency
        return tables

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tables: {str(e)}",
        )


@router.get("/{connection_id}/tables/{table_name}/columns", response_model=List[str])
async def list_table_columns(connection_id: str, table_name: str, schema: Optional[str] = None):
    """
    List columns in a specific table

    Returns column names.
    """
    try:
        # Get connection
        connection = await get_connection_by_id(connection_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection {connection_id} not found"
            )

        # Decrypt password
        password = decrypt_password(connection["password_encrypted"])

        # Connect and list columns
        from hdbcli import dbapi

        conn_params = {
            'address': connection["host"],
            'port': connection["port"],
            'user': connection["user"],
            'password': password,
            'encrypt': bool(connection["encrypt"]),
            'sslValidateCertificate': False
        }

        db_connection = dbapi.connect(**conn_params)
        cursor = db_connection.cursor()

        # Query columns
        schema_filter = schema or connection.get("schema") or connection["database"]
        cursor.execute("""
            SELECT COLUMN_NAME
            FROM SYS.TABLE_COLUMNS
            WHERE SCHEMA_NAME = ? AND TABLE_NAME = ?
            ORDER BY POSITION
        """, (schema_filter, table_name))

        columns = [row[0] for row in cursor.fetchall()]

        cursor.close()
        db_connection.close()

        return columns

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list columns: {str(e)}",
        )
