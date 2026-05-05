"""
Database management service

Handles:
- Testing database connections
- Switching between SQLite and HANA
- Database health monitoring
- Connection statistics
"""

import time
from typing import Dict, Any, Optional
from datetime import datetime

from open_notebook.database.interface import (
    ConnectionConfig,
    DatabaseInterface,
    DatabaseError,
    ConnectionError as DBConnectionError,
)
from api.models import (
    DatabaseConfig,
    DatabaseType,
    DatabaseStatus,
    DatabaseTestConnectionResponse,
    DatabaseSwitchResponse,
)


class DatabaseService:
    """Service for database management operations"""

    def __init__(self):
        self._current_db: Optional[DatabaseInterface] = None
        self._connection_start_time: Optional[datetime] = None
        self._stats_cache: Dict[str, Any] = {}
        self._cache_time: Optional[datetime] = None
        self._cache_ttl_seconds = 30  # Cache stats for 30 seconds

    def set_database(self, db: DatabaseInterface) -> None:
        """Set the current database instance"""
        self._current_db = db
        self._connection_start_time = datetime.utcnow()
        self._clear_cache()

    def _clear_cache(self) -> None:
        """Clear the stats cache"""
        self._stats_cache = {}
        self._cache_time = None

    async def test_hana_connection(
        self, config: DatabaseConfig
    ) -> DatabaseTestConnectionResponse:
        """
        Test HANA database connection

        Args:
            config: HANA database configuration

        Returns:
            Test result with connection details
        """
        if config.db_type != DatabaseType.HANA:
            return DatabaseTestConnectionResponse(
                success=False,
                message="Configuration is not for HANA database",
                db_type=config.db_type,
            )

        if not config.hana_config:
            return DatabaseTestConnectionResponse(
                success=False,
                message="HANA configuration is missing",
                db_type=DatabaseType.HANA,
            )

        hana_conf = config.hana_config
        conn_config = ConnectionConfig(
            db_type="hana",
            host=hana_conf.host,
            port=hana_conf.port,
            database=hana_conf.database,
            user=hana_conf.user,
            password=hana_conf.password,
            encrypt=hana_conf.encrypt,
            pool_size=hana_conf.pool_size,
            max_overflow=hana_conf.max_overflow,
            pool_timeout=hana_conf.pool_timeout,
        )

        try:
            # Import HANA implementation
            from open_notebook.database.hana_impl import HANADatabase

            # Create temporary connection
            db = HANADatabase(conn_config)

            # Measure connection time
            start_time = time.time()
            await db.connect()
            latency_ms = (time.time() - start_time) * 1000

            # Get server version
            result = await db.query("SELECT VERSION FROM SYS.M_DATABASE", fetch_one=True)
            server_version = result.get("VERSION") if result else None

            # Clean up
            await db.disconnect()

            return DatabaseTestConnectionResponse(
                success=True,
                message="Successfully connected to HANA database",
                db_type=DatabaseType.HANA,
                server_version=server_version,
                latency_ms=round(latency_ms, 2),
            )

        except DBConnectionError as e:
            return DatabaseTestConnectionResponse(
                success=False,
                message=f"Connection failed: {str(e)}",
                db_type=DatabaseType.HANA,
            )
        except Exception as e:
            return DatabaseTestConnectionResponse(
                success=False,
                message=f"Unexpected error: {str(e)}",
                db_type=DatabaseType.HANA,
            )

    async def test_sqlite_connection(
        self, config: DatabaseConfig
    ) -> DatabaseTestConnectionResponse:
        """
        Test SQLite database connection

        Args:
            config: SQLite database configuration

        Returns:
            Test result with connection details
        """
        if config.db_type != DatabaseType.SQLITE:
            return DatabaseTestConnectionResponse(
                success=False,
                message="Configuration is not for SQLite database",
                db_type=config.db_type,
            )

        if not config.sqlite_config:
            return DatabaseTestConnectionResponse(
                success=False,
                message="SQLite configuration is missing",
                db_type=DatabaseType.SQLITE,
            )

        sqlite_conf = config.sqlite_config
        conn_config = ConnectionConfig(
            db_type="sqlite",
            db_path=sqlite_conf.db_path,
            pool_size=sqlite_conf.pool_size,
            pool_timeout=sqlite_conf.timeout,
        )

        try:
            # Import SQLite implementation
            from open_notebook.database.sqlite_impl import SQLiteDatabase

            # Create temporary connection
            db = SQLiteDatabase(conn_config)

            # Measure connection time
            start_time = time.time()
            await db.connect()
            latency_ms = (time.time() - start_time) * 1000

            # Get SQLite version
            result = await db.query("SELECT sqlite_version() as version", fetch_one=True)
            server_version = f"SQLite {result.get('version')}" if result else None

            # Clean up
            await db.disconnect()

            return DatabaseTestConnectionResponse(
                success=True,
                message="Successfully connected to SQLite database",
                db_type=DatabaseType.SQLITE,
                server_version=server_version,
                latency_ms=round(latency_ms, 2),
            )

        except Exception as e:
            return DatabaseTestConnectionResponse(
                success=False,
                message=f"Connection failed: {str(e)}",
                db_type=DatabaseType.SQLITE,
            )

    async def test_connection(
        self, config: DatabaseConfig
    ) -> DatabaseTestConnectionResponse:
        """
        Test database connection (auto-detects type)

        Args:
            config: Database configuration

        Returns:
            Test result with connection details
        """
        if config.db_type == DatabaseType.HANA:
            return await self.test_hana_connection(config)
        else:
            return await self.test_sqlite_connection(config)

    async def switch_database(
        self,
        target_type: DatabaseType,
        config: DatabaseConfig,
        migrate_data: bool = False,
    ) -> DatabaseSwitchResponse:
        """
        Switch active database

        Args:
            target_type: Target database type
            config: Database configuration for target
            migrate_data: Whether to migrate data from current to target

        Returns:
            Switch operation result
        """
        if not self._current_db:
            return DatabaseSwitchResponse(
                success=False,
                message="No active database connection",
                previous_type=DatabaseType.SQLITE,  # Assume SQLite as default
                current_type=DatabaseType.SQLITE,
            )

        previous_type = (
            DatabaseType.HANA
            if self._current_db.db_type == "hana"
            else DatabaseType.SQLITE
        )

        # Test new connection first
        test_result = await self.test_connection(config)
        if not test_result.success:
            return DatabaseSwitchResponse(
                success=False,
                message=f"Cannot switch: {test_result.message}",
                previous_type=previous_type,
                current_type=previous_type,  # Stay on current
            )

        try:
            # Create new database instance
            if target_type == DatabaseType.HANA:
                from open_notebook.database.hana_impl import HANADatabase

                hana_conf = config.hana_config
                conn_config = ConnectionConfig(
                    db_type="hana",
                    host=hana_conf.host,
                    port=hana_conf.port,
                    database=hana_conf.database,
                    user=hana_conf.user,
                    password=hana_conf.password,
                    encrypt=hana_conf.encrypt,
                    pool_size=hana_conf.pool_size,
                    max_overflow=hana_conf.max_overflow,
                    pool_timeout=hana_conf.pool_timeout,
                )
                new_db = HANADatabase(conn_config)
            else:
                from open_notebook.database.sqlite_impl import SQLiteDatabase

                sqlite_conf = config.sqlite_config
                conn_config = ConnectionConfig(
                    db_type="sqlite",
                    db_path=sqlite_conf.db_path,
                    pool_size=sqlite_conf.pool_size,
                    pool_timeout=sqlite_conf.timeout,
                )
                new_db = SQLiteDatabase(conn_config)

            # Connect to new database
            await new_db.connect()

            # Handle data migration if requested
            migration_status = None
            if migrate_data:
                migration_status = await self._migrate_data(self._current_db, new_db)

            # Disconnect old database
            await self._current_db.disconnect()

            # Switch to new database
            self.set_database(new_db)

            return DatabaseSwitchResponse(
                success=True,
                message=f"Successfully switched to {target_type.value} database",
                previous_type=previous_type,
                current_type=target_type,
                migration_status=migration_status,
            )

        except Exception as e:
            return DatabaseSwitchResponse(
                success=False,
                message=f"Failed to switch database: {str(e)}",
                previous_type=previous_type,
                current_type=previous_type,  # Stay on current
            )

    async def _migrate_data(
        self, source_db: DatabaseInterface, target_db: DatabaseInterface
    ) -> str:
        """
        Migrate data from source to target database

        Args:
            source_db: Source database
            target_db: Target database

        Returns:
            Migration status message
        """
        # This is a placeholder for data migration logic
        # In a real implementation, this would:
        # 1. Read all tables from source
        # 2. Create tables in target if not exist
        # 3. Copy data in batches
        # 4. Verify data integrity
        # 5. Handle conflicts and errors

        try:
            # Count records in source
            tables = ["notebooks", "sources", "notes", "chat_sessions", "chat_messages"]
            total_migrated = 0

            for table in tables:
                try:
                    # Get all records from source
                    records = await source_db.query(f"SELECT * FROM {table}")

                    # Insert into target (batch operation)
                    for record in records:
                        await target_db.create(table, record)
                        total_migrated += 1

                except Exception as e:
                    # Continue with other tables even if one fails
                    continue

            return f"Migrated {total_migrated} records successfully"

        except Exception as e:
            return f"Migration failed: {str(e)}"

    async def get_database_stats(self) -> Dict[str, Any]:
        """
        Get database statistics

        Returns:
            Dictionary with database statistics
        """
        if not self._current_db or not self._current_db.is_connected:
            return {
                "connected": False,
                "error": "No active database connection",
            }

        # Check cache
        now = datetime.utcnow()
        if self._cache_time and (now - self._cache_time).total_seconds() < self._cache_ttl_seconds:
            return self._stats_cache

        try:
            # Get counts from database
            notebooks_result = await self._current_db.query(
                "SELECT COUNT(*) as count FROM notebooks"
            )
            sources_result = await self._current_db.query(
                "SELECT COUNT(*) as count FROM sources"
            )
            notes_result = await self._current_db.query(
                "SELECT COUNT(*) as count FROM notes"
            )

            notebooks_count = notebooks_result[0]["count"] if notebooks_result else 0
            sources_count = sources_result[0]["count"] if sources_result else 0
            notes_count = notes_result[0]["count"] if notes_result else 0

            stats = {
                "connected": True,
                "db_type": self._current_db.db_type,
                "notebooks_count": notebooks_count,
                "sources_count": sources_count,
                "notes_count": notes_count,
                "total_records": notebooks_count + sources_count + notes_count,
            }

            # Cache the results
            self._stats_cache = stats
            self._cache_time = now

            return stats

        except Exception as e:
            return {
                "connected": True,
                "db_type": self._current_db.db_type,
                "error": f"Failed to fetch stats: {str(e)}",
            }

    async def get_database_status(self) -> DatabaseStatus:
        """
        Get comprehensive database status

        Returns:
            DatabaseStatus object with current state
        """
        if not self._current_db:
            return DatabaseStatus(
                db_type=DatabaseType.SQLITE,
                connected=False,
            )

        stats = await self.get_database_stats()
        connected = stats.get("connected", False)

        uptime_seconds = None
        if self._connection_start_time:
            uptime_seconds = int((datetime.utcnow() - self._connection_start_time).total_seconds())

        return DatabaseStatus(
            db_type=(
                DatabaseType.HANA
                if self._current_db.db_type == "hana"
                else DatabaseType.SQLITE
            ),
            connected=connected,
            connection_pool_size=self._current_db.config.pool_size if connected else None,
            total_records=stats.get("total_records"),
            notebooks_count=stats.get("notebooks_count"),
            sources_count=stats.get("sources_count"),
            notes_count=stats.get("notes_count"),
            uptime_seconds=uptime_seconds,
        )


# Singleton instance
_database_service: Optional[DatabaseService] = None


def get_database_service() -> DatabaseService:
    """Get or create the database service singleton"""
    global _database_service
    if _database_service is None:
        _database_service = DatabaseService()
    return _database_service
