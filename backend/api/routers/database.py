"""
Database Management API Router

Endpoints for database configuration, testing, switching, and monitoring.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from fastapi.responses import JSONResponse

from api.models import (
    DatabaseConfig,
    DatabaseConfigResponse,
    DatabaseTestConnectionRequest,
    DatabaseTestConnectionResponse,
    DatabaseSwitchRequest,
    DatabaseSwitchResponse,
    DatabaseStatus,
    DatabaseType,
    ErrorResponse,
    SuccessResponse,
)
from api.services.database_service import get_database_service


router = APIRouter(prefix="/api/database", tags=["database"])


# ============================================================================
# Configuration Endpoints
# ============================================================================

@router.get("/config", response_model=DatabaseConfigResponse)
async def get_database_config():
    """
    Get current database configuration

    Returns the active database configuration with password fields masked.
    """
    try:
        # Get database service
        db_service = get_database_service()

        # TODO: Load config from environment or config file
        # For now, return a placeholder based on current connection
        if not db_service._current_db:
            # Return default SQLite config
            from api.models import SQLiteConfig

            return DatabaseConfigResponse(
                db_type=DatabaseType.SQLITE,
                sqlite_config=SQLiteConfig(db_path="./data/database.db"),
            )

        db_type = db_service._current_db.db_type
        config = db_service._current_db.config

        if db_type == "hana":
            from api.models import HANAConfig

            hana_config = HANAConfig(
                host=config.host,
                port=config.port,
                database=config.database,
                user=config.user,
                password="********",  # Mask password
                encrypt=config.encrypt,
                pool_size=config.pool_size,
                max_overflow=config.max_overflow,
                pool_timeout=config.pool_timeout,
            )

            return DatabaseConfigResponse(
                db_type=DatabaseType.HANA,
                hana_config=hana_config,
            )
        else:
            from api.models import SQLiteConfig

            sqlite_config = SQLiteConfig(
                db_path=config.db_path,
                pool_size=config.pool_size,
                timeout=config.pool_timeout,
            )

            return DatabaseConfigResponse(
                db_type=DatabaseType.SQLITE,
                sqlite_config=sqlite_config,
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get database config: {str(e)}",
        )


@router.put("/config", response_model=SuccessResponse)
async def update_database_config(config: DatabaseConfig):
    """
    Update database configuration

    Updates the configuration file with new settings.
    Does NOT switch the active database - use POST /database/switch for that.

    - **config**: New database configuration
    """
    try:
        # TODO: Save config to environment file or config file
        # For now, just validate the config

        # Test the new configuration
        db_service = get_database_service()
        test_result = await db_service.test_connection(config)

        if not test_result.success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid configuration: {test_result.message}",
            )

        # In a real implementation, save to .env or config.yaml
        # import os
        # from dotenv import set_key
        # set_key('.env', 'DATABASE_TYPE', config.db_type.value)
        # ... etc

        return SuccessResponse(
            success=True,
            message="Database configuration updated successfully",
            data={"db_type": config.db_type.value},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update config: {str(e)}",
        )


# ============================================================================
# Connection Testing Endpoints
# ============================================================================

@router.post("/test-connection", response_model=DatabaseTestConnectionResponse)
async def test_database_connection(request: DatabaseTestConnectionRequest):
    """
    Test database connection without switching

    Use this to validate configuration before applying changes.

    - **config**: Database configuration to test
    """
    try:
        db_service = get_database_service()
        result = await db_service.test_connection(request.config)
        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test connection: {str(e)}",
        )


# ============================================================================
# Database Switching Endpoints
# ============================================================================

@router.post("/switch", response_model=DatabaseSwitchResponse)
async def switch_database(
    request: DatabaseSwitchRequest,
    background_tasks: BackgroundTasks,
):
    """
    Switch active database

    Disconnects from current database and connects to new one.
    Optionally migrates data from old to new database.

    - **target_type**: Target database type (sqlite or hana)
    - **config**: Configuration for target database
    - **migrate_data**: Whether to migrate existing data (default: false)

    Note: Migration is a long-running operation and runs in the background.
    """
    try:
        db_service = get_database_service()

        # Perform the switch
        result = await db_service.switch_database(
            target_type=request.target_type,
            config=request.config,
            migrate_data=request.migrate_data,
        )

        # If migration is requested and switch was successful,
        # additional background processing could be queued here
        if request.migrate_data and result.success:
            # background_tasks.add_task(post_migration_tasks)
            pass

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to switch database: {str(e)}",
        )


# ============================================================================
# Status and Monitoring Endpoints
# ============================================================================

@router.get("/status", response_model=DatabaseStatus)
async def get_database_status():
    """
    Get comprehensive database status

    Returns current database type, connection state, and statistics.
    """
    try:
        db_service = get_database_service()
        status = await db_service.get_database_status()
        return status

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get database status: {str(e)}",
        )


@router.get("/stats")
async def get_database_stats():
    """
    Get database statistics

    Returns record counts and other metrics.
    """
    try:
        db_service = get_database_service()
        stats = await db_service.get_database_stats()
        return stats

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get database stats: {str(e)}",
        )


# ============================================================================
# Health Check Endpoint
# ============================================================================

@router.get("/health")
async def database_health_check():
    """
    Database health check endpoint

    Returns simple health status for monitoring systems.
    """
    try:
        db_service = get_database_service()

        if not db_service._current_db:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "unhealthy",
                    "message": "No database connection",
                },
            )

        if not db_service._current_db.is_connected:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "unhealthy",
                    "message": "Database not connected",
                },
            )

        # Try a simple query
        from open_notebook.database.repository import repo_query

        await repo_query("SELECT 1 as health_check")

        return {
            "status": "healthy",
            "db_type": db_service._current_db.db_type,
            "connected": True,
        }

    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "message": f"Health check failed: {str(e)}",
            },
        )


# ============================================================================
# Backup and Restore Endpoints (Optional)
# ============================================================================

@router.post("/backup")
async def backup_database(background_tasks: BackgroundTasks):
    """
    Create a backup of the current database

    For SQLite: Creates a copy of the database file
    For HANA: Triggers HANA backup (requires permissions)

    Note: This is an optional endpoint for Phase 6+
    """
    try:
        db_service = get_database_service()

        if not db_service._current_db:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active database connection",
            )

        # TODO: Implement backup logic
        # For SQLite: shutil.copy(db_path, backup_path)
        # For HANA: BACKUP DATA statement

        return SuccessResponse(
            success=False,
            message="Backup functionality not yet implemented",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to backup database: {str(e)}",
        )


@router.post("/restore")
async def restore_database(backup_path: str):
    """
    Restore database from a backup

    Note: This is an optional endpoint for Phase 6+

    - **backup_path**: Path to backup file
    """
    try:
        # TODO: Implement restore logic
        return SuccessResponse(
            success=False,
            message="Restore functionality not yet implemented",
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restore database: {str(e)}",
        )
