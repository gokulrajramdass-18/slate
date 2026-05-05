"""
Configuration management for Open Notebook

Handles database configuration, environment variables, and factory functions
for database instance creation.
"""

import os
from enum import Enum
from typing import Optional, Union
from dataclasses import dataclass

from open_notebook.database.interface import DatabaseInterface, ConnectionConfig
from open_notebook.database.sqlite_impl import SQLiteDatabase


class DatabaseType(str, Enum):
    """Supported database types"""
    SQLITE = "sqlite"
    HANA = "hana"


class DeploymentMode(str, Enum):
    """Deployment environment modes"""
    DEVELOPMENT = "development"
    PRODUCTION = "production"


@dataclass
class HostingConfig:
    """Configuration for microsite hosting server.

    In development mode, the hosting router is mounted within the main API.
    In production mode, a standalone hosting server runs on a separate port.
    """
    deployment_env: DeploymentMode = DeploymentMode.DEVELOPMENT
    hosting_port: int = 5056
    hosting_host: str = "127.0.0.1"
    hosting_base_url: str = ""
    enable_caching: bool = True
    cache_ttl: int = 300  # seconds (5 minutes)

    @classmethod
    def from_env(cls) -> "HostingConfig":
        """Load hosting configuration from environment variables"""
        host = os.getenv("HOSTING_HOST", "127.0.0.1")
        port = int(os.getenv("HOSTING_PORT", "5056"))

        env_value = os.getenv("DEPLOYMENT_ENV", "development").lower()
        try:
            deployment_env = DeploymentMode(env_value)
        except ValueError:
            deployment_env = DeploymentMode.DEVELOPMENT

        return cls(
            deployment_env=deployment_env,
            hosting_port=port,
            hosting_host=host,
            hosting_base_url=os.getenv(
                "HOSTING_BASE_URL",
                f"http://{host}:{port}"
            ),
            enable_caching=os.getenv("ENABLE_HOSTING_CACHE", "true").lower() == "true",
            cache_ttl=int(os.getenv("HOSTING_CACHE_TTL", "300")),
        )


@dataclass
class SQLiteConfig:
    """SQLite-specific configuration"""
    db_path: str = "./data/database.db"
    pool_size: int = 20
    max_overflow: int = 30  # busy_timeout prevents deadlocks; large pools are unnecessary
    pool_timeout: int = 30
    query_timeout: int = 30

    @classmethod
    def from_env(cls) -> "SQLiteConfig":
        """Load SQLite configuration from environment variables"""
        return cls(
            db_path=os.getenv("SQLITE_DB_PATH", "./data/database.db"),
            pool_size=int(os.getenv("SQLITE_POOL_SIZE", "20")),
            max_overflow=int(os.getenv("SQLITE_MAX_OVERFLOW", "30")),
            pool_timeout=int(os.getenv("SQLITE_POOL_TIMEOUT", "30")),
            query_timeout=int(os.getenv("SQLITE_QUERY_TIMEOUT", "30"))
        )

    def to_connection_config(self) -> ConnectionConfig:
        """Convert to ConnectionConfig"""
        return ConnectionConfig(
            db_type=DatabaseType.SQLITE.value,
            db_path=self.db_path,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            pool_timeout=self.pool_timeout
        )


@dataclass
class HANAConfig:
    """
    SAP HANA Cloud configuration

    Note: HANA implementation will be completed in Phase 8.
    This class defines the structure for future implementation.
    """
    host: str
    port: int = 443
    database: str = "SYSTEMDB"
    user: str = ""
    password: str = ""
    encrypt: bool = True
    ssl_validate_cert: bool = True
    pool_size: int = 30
    max_overflow: int = 40
    pool_timeout: int = 30
    query_timeout: int = 30

    @classmethod
    def from_env(cls) -> "HANAConfig":
        """Load HANA configuration from environment variables"""
        return cls(
            host=os.getenv("HANA_HOST", ""),
            port=int(os.getenv("HANA_PORT", "443")),
            database=os.getenv("HANA_DATABASE", "SYSTEMDB"),
            user=os.getenv("HANA_USER", ""),
            password=os.getenv("HANA_PASSWORD", ""),
            encrypt=os.getenv("HANA_ENCRYPT", "true").lower() == "true",
            ssl_validate_cert=os.getenv("HANA_SSL_VALIDATE_CERT", "true").lower() == "true",
            pool_size=int(os.getenv("HANA_POOL_SIZE", "30")),
            max_overflow=int(os.getenv("HANA_MAX_OVERFLOW", "40")),
            pool_timeout=int(os.getenv("HANA_POOL_TIMEOUT", "30")),
            query_timeout=int(os.getenv("HANA_QUERY_TIMEOUT", "30"))
        )

    def to_connection_config(self) -> ConnectionConfig:
        """Convert to ConnectionConfig"""
        return ConnectionConfig(
            db_type=DatabaseType.HANA.value,
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password,
            encrypt=self.encrypt,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            pool_timeout=self.pool_timeout
        )


@dataclass
class ToolFilteringConfig:
    """
    Tool filtering configuration for plan mode agents.

    Controls two-phase tool discovery system that reduces context window bloat
    by intelligently filtering tools before binding to LLM.
    """
    enabled: bool = True
    confidence_threshold: float = 0.85
    max_tools: int = 10
    filter_model: str = "claude-haiku-3-5-20241022"

    @classmethod
    def from_env(cls) -> "ToolFilteringConfig":
        """Load tool filtering configuration from environment variables"""
        return cls(
            enabled=os.getenv("PLAN_MODE_TOOL_FILTERING_ENABLED", "true").lower() == "true",
            confidence_threshold=float(
                os.getenv("PLAN_MODE_FILTER_CONFIDENCE_THRESHOLD", "0.85")
            ),
            max_tools=int(os.getenv("PLAN_MODE_MAX_TOOLS", "10")),
            filter_model=os.getenv(
                "PLAN_MODE_FILTER_MODEL",
                "claude-haiku-3-5-20241022"
            )
        )


class Config:
    """
    Application configuration

    Loads settings from environment variables and provides
    database factory functions.
    """

    def __init__(self):
        """Initialize configuration from environment"""
        # Database type selection
        self.database_type = DatabaseType(
            os.getenv("DATABASE_TYPE", DatabaseType.SQLITE.value)
        )

        # Encryption key for credentials
        self.encryption_key = os.getenv("OPEN_NOTEBOOK_ENCRYPTION_KEY", "")
        if not self.encryption_key:
            print("WARNING: OPEN_NOTEBOOK_ENCRYPTION_KEY not set. Credential encryption disabled.")

        # Load database-specific configs
        self.sqlite_config = SQLiteConfig.from_env()
        self.hana_config = HANAConfig.from_env()

        # API configuration
        self.api_host = os.getenv("API_HOST", "127.0.0.1")
        self.api_port = int(os.getenv("API_PORT", "5055"))
        self.api_reload = os.getenv("API_RELOAD", "true").lower() == "true"

        # Microsite hosting configuration
        self.hosting_config = HostingConfig.from_env()

        # Tool filtering configuration
        self.tool_filtering_config = ToolFilteringConfig.from_env()

        # Authentication
        self.basic_auth_password = os.getenv("BASIC_AUTH_PASSWORD", "")

    def get_database_config(self) -> Union[SQLiteConfig, HANAConfig]:
        """
        Get the current database configuration based on DATABASE_TYPE.

        Returns:
            SQLiteConfig or HANAConfig instance
        """
        if self.database_type == DatabaseType.SQLITE:
            return self.sqlite_config
        elif self.database_type == DatabaseType.HANA:
            return self.hana_config
        else:
            raise ValueError(f"Unsupported database type: {self.database_type}")

    def validate(self) -> None:
        """
        Validate configuration and raise errors for missing required settings.

        Raises:
            ValueError: If required configuration is missing or invalid
        """
        if self.database_type == DatabaseType.HANA:
            if not self.hana_config.host:
                raise ValueError("HANA_HOST is required when DATABASE_TYPE=hana")
            if not self.hana_config.user:
                raise ValueError("HANA_USER is required when DATABASE_TYPE=hana")
            if not self.hana_config.password:
                raise ValueError("HANA_PASSWORD is required when DATABASE_TYPE=hana")


# Global configuration instance
config = Config()


def get_encryption_key() -> str:
    """
    Get the encryption key for credential storage.

    Returns:
        Encryption key string, or empty string if not set
    """
    return config.encryption_key


def get_database() -> DatabaseInterface:
    """
    Factory function to get the appropriate database implementation.

    Returns the correct database instance based on DATABASE_TYPE environment variable.
    This enables runtime database switching without code changes.

    Returns:
        DatabaseInterface: SQLiteDatabase or HANADatabase instance

    Raises:
        ValueError: If DATABASE_TYPE is invalid or configuration is missing

    Example:
        ```python
        from open_notebook.config import get_database

        async with get_database() as db:
            await db.connect()
            results = await db.query("SELECT * FROM notebooks")
            await db.disconnect()
        ```
    """
    db_type = config.database_type

    if db_type == DatabaseType.SQLITE:
        connection_config = config.sqlite_config.to_connection_config()
        return SQLiteDatabase(connection_config)

    elif db_type == DatabaseType.HANA:
        # HANA implementation will be completed in Phase 8
        # For now, raise NotImplementedError
        try:
            from open_notebook.database.hana_impl import HANADatabase
            connection_config = config.hana_config.to_connection_config()
            return HANADatabase(connection_config)
        except ImportError:
            raise NotImplementedError(
                "HANA implementation not yet available. "
                "This will be completed in Phase 8 of the migration. "
                "For now, please use DATABASE_TYPE=sqlite"
            )

    else:
        raise ValueError(f"Unsupported database type: {db_type}")


async def test_database_connection() -> bool:
    """
    Test the current database connection.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        db = get_database()
        await db.connect()
        await db.disconnect()
        return True
    except Exception as e:
        print(f"Database connection test failed: {str(e)}")
        return False


def switch_database(new_type: DatabaseType) -> None:
    """
    Switch database type at runtime.

    This updates the DATABASE_TYPE environment variable and reloads configuration.
    Note: Existing database connections should be closed before switching.

    Args:
        new_type: DatabaseType.SQLITE or DatabaseType.HANA

    Example:
        ```python
        from open_notebook.config import switch_database, DatabaseType

        # Switch to HANA
        switch_database(DatabaseType.HANA)
        ```
    """
    os.environ["DATABASE_TYPE"] = new_type.value
    global config
    config = Config()
    config.validate()


def get_default_model():
    """
    Get the default LLM model for agent orchestration.

    Returns a LangChain chat model instance (ChatOpenAI or ChatAnthropic)
    based on the DEFAULT_CHAT_MODEL environment variable or falls back to gpt-4.

    Returns:
        BaseChatModel: LangChain chat model instance

    Example:
        ```python
        from open_notebook.config import get_default_model

        llm = get_default_model()
        response = await llm.ainvoke("Hello, world!")
        ```
    """
    from langchain_openai import ChatOpenAI
    from langchain_anthropic import ChatAnthropic

    # Get model name from environment or use default
    model_name = os.getenv("DEFAULT_CHAT_MODEL", "gpt-4")

    # Check if model is Anthropic Claude
    if "claude" in model_name.lower():
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is required for Claude models. "
                "Please set it or change DEFAULT_CHAT_MODEL to use a different provider."
            )
        return ChatAnthropic(
            model=model_name,
            api_key=api_key,
            temperature=0
        )

    # Default to OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")  # For LiteLLM proxy support

    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is required. "
            "Please set it or configure DEFAULT_CHAT_MODEL with ANTHROPIC_API_KEY for Claude."
        )

    kwargs = {
        "model": model_name,
        "api_key": api_key,
        "temperature": 0
    }

    if base_url:
        kwargs["base_url"] = base_url

    return ChatOpenAI(**kwargs)
