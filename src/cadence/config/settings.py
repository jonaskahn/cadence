"""Configuration settings for the Cadence Multi-Agent AI Framework.

This module provides comprehensive configuration management for the Cadence framework.
All configuration values can be set via environment variables with the CADENCE_ prefix
(case-insensitive), and field validation is handled by Pydantic.

The Settings class centralizes all application configuration including API settings,
LLM provider configurations, database connections, plugin management, and system
tuning parameters with automatic environment variable loading and validation.
"""

from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings with environment variable support.

    All settings can be configured via environment variables with the CADENCE_ prefix.
    The configuration automatically loads from .env files and provides comprehensive
    validation for all fields to ensure system reliability.
    """

    app_name: str = Field(default="Cadence 🤖 Multi-agents AI Framework", description="Application name")
    debug: bool = Field(default=False, description="Enable debug mode")

    api_host: str = Field(default="0.0.0.0", description="API host to bind to")
    api_port: int = Field(default=8000, description="API port to bind to")
    cors_origins: List[str] = Field(default=["*"], description="CORS allowed origins")

    default_llm_provider: str = Field(default="openai", description="Default LLM provider")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key")
    google_api_key: Optional[str] = Field(default=None, description="Google AI API key")

    plugins_dir: List[str] = Field(
        default=["./plugins/src/cadence_example_plugins"], description="Directories to search for plugins"
    )
    storage_root: str = Field(default="./storage", description="Root directory for plugin storage")
    enable_directory_plugins: bool = Field(default=True, description="Enable directory-based plugin discovery")

    postgres_url: Optional[str] = Field(
        default=None, description="PostgreSQL connection URL (e.g., postgresql+asyncpg://user:pass@localhost/cadence)"
    )
    redis_url: Optional[str] = Field(default="redis://localhost:6379", description="Redis connection URL")
    mongo_url: Optional[str] = Field(default=None, description="MongoDB connection URL")
    cassandra_hosts: Optional[List[str]] = Field(default=None, description="Cassandra cluster hosts")
    mariadb_url: Optional[str] = Field(default=None, description="MariaDB connection URL")

    conversation_storage_backend: str = Field(default="memory", description="Conversation storage backend")
    max_agent_hops: int = Field(default=25, description="Maximum agent hops per conversation")
    graph_recursion_limit: int = Field(default=50, description="Maximum graph recursion depth")
    coordinator_consecutive_agent_route_limit: int = Field(
        default=5,
        description="Max consecutive coordinator routes to agents (excluding finalize) before suspend",
    )

    session_timeout: int = Field(default=3600, description="Session timeout in seconds")
    max_session_history: int = Field(default=100, description="Maximum conversation history per session")

    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="Log message format"
    )

    secret_key: Optional[str] = Field(default=None, description="Secret key for JWT tokens")
    access_token_expire_minutes: int = Field(default=30, description="Access token expiration time")

    rate_limit_requests: int = Field(default=100, description="Rate limit requests per minute")
    rate_limit_window: int = Field(default=60, description="Rate limit window in seconds")

    health_check_interval: int = Field(default=30, description="Health check interval in seconds")
    health_check_timeout: int = Field(default=5, description="Health check timeout in seconds")

    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    enable_tracing: bool = Field(default=False, description="Enable distributed tracing")
    enable_profiling: bool = Field(default=False, description="Enable performance profiling")

    reload_on_change: bool = Field(default=False, description="Auto-reload on file changes")
    enable_hot_reload: bool = Field(default=False, description="Enable hot reload for development")

    test_mode: bool = Field(default=False, description="Enable test mode")
    mock_external_services: bool = Field(default=False, description="Mock external services in tests")

    worker_processes: int = Field(default=1, description="Number of worker processes")
    max_concurrent_requests: int = Field(default=1000, description="Maximum concurrent requests")
    request_timeout: int = Field(default=30, description="Request timeout in seconds")

    enable_prometheus: bool = Field(default=False, description="Enable Prometheus metrics")
    metrics_port: int = Field(default=9090, description="Metrics endpoint port")

    backup_enabled: bool = Field(default=False, description="Enable automatic backups")
    backup_interval: int = Field(default=86400, description="Backup interval in seconds")
    backup_retention_days: int = Field(default=30, description="Backup retention period")

    slack_bot_token: Optional[str] = Field(default=None, description="Slack bot token")
    discord_bot_token: Optional[str] = Field(default=None, description="Discord bot token")
    webhook_secret: Optional[str] = Field(default=None, description="Webhook verification secret")

    custom_middleware: List[str] = Field(default=[], description="Custom middleware modules")
    custom_routes: List[str] = Field(default=[], description="Custom route modules")
    environment: str = Field(default="development", description="Environment name")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, env_prefix="CADENCE_", extra="ignore"
    )

    def __post_init__(self):
        """Post-initialization validation and setup."""
        if self.debug:
            self.log_level = "DEBUG"
            self.enable_hot_reload = True
            self.enable_tracing = True

        if self.test_mode:
            self.mock_external_services = True
            self.enable_metrics = False
            self.enable_tracing = False

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"

    @property
    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.environment.lower() == "testing"

    def get_database_url(self, backend: str) -> Optional[str]:
        """Get database URL for specified backend."""
        backend_map = {
            "postgresql": self.postgres_url,
            "redis": self.redis_url,
            "mongodb": self.mongo_url,
            "cassandra": self.cassandra_hosts,
            "mariadb": self.mariadb_url,
        }
        return backend_map.get(backend.lower())

    def validate_llm_provider(self, provider: str) -> bool:
        """Validate if the specified LLM provider is configured."""
        if provider.lower() == "openai":
            return bool(self.openai_api_key)
        elif provider.lower() == "anthropic":
            return bool(self.anthropic_api_key)
        elif provider.lower() == "google":
            return bool(self.google_api_key)
        else:
            return False

    @staticmethod
    def get_default_provider_llm_model(provider: str) -> str:
        """Get the default model name for the configured LLM provider."""
        if provider == "openai":
            return "gpt-4o-mini"
        elif provider == "anthropic":
            return "claude-3-5-sonnet-20241022"
        elif provider == "google":
            return "gemini-1.5-flash"
        else:
            return "gpt-4o-mini"

    def get_finalizer_provider_llm_model(self, provider: str) -> str:
        """Get the model name for the finalizer LLM provider."""
        return self.get_default_provider_llm_model(provider)

    def get_api_key_for_provider(self, provider: str) -> Optional[str]:
        """Get the API key for a specific provider."""
        provider = provider.lower()
        if provider == "openai":
            return self.openai_api_key
        elif provider == "anthropic":
            return self.anthropic_api_key
        elif provider == "google":
            return self.google_api_key
        else:
            return None

    def get_provider_extra_params(self, provider: str) -> dict:
        """Get extra parameters for a specific provider."""
        return {}

    @property
    def default_llm_temperature(self) -> float:
        """Get the default temperature for LLM models."""
        return 0.7

    @property
    def default_llm_context_window(self) -> int:
        """Get the default context window size for LLM models."""
        return 4096

    @property
    def coordinator_llm_provider(self) -> Optional[str]:
        """Get the LLM provider for the coordinator. Falls back to default if None."""
        return None

    @property
    def coordinator_temperature(self) -> float:
        """Get the temperature for the coordinator LLM."""
        return 0.7

    @property
    def coordinator_max_tokens(self) -> int:
        """Get the max tokens for the coordinator LLM."""
        return 4096

    @property
    def suspend_llm_provider(self) -> Optional[str]:
        """Get the LLM provider for the suspend node. Falls back to default if None."""
        return None

    @property
    def suspend_temperature(self) -> float:
        """Get the temperature for the suspend node LLM."""
        return 0.5

    @property
    def suspend_max_tokens(self) -> int:
        """Get the max tokens for the suspend node LLM."""
        return 1024

    @property
    def finalizer_llm_provider(self) -> Optional[str]:
        """Get the LLM provider for the finalizer. Falls back to default if None."""
        return None

    @property
    def finalizer_temperature(self) -> float:
        """Get the temperature for the finalizer LLM."""
        return 0.3

    @property
    def finalizer_max_tokens(self) -> int:
        """Get the max tokens for the finalizer LLM."""
        return 1024

    # Derived storage directories (computed from storage_root)
    @property
    def storage_uploaded(self) -> str:
        return str((__import__("pathlib").Path(self.storage_root) / "uploaded").resolve())

    @property
    def storage_archived(self) -> str:
        return str((__import__("pathlib").Path(self.storage_root) / "archived").resolve())

    @property
    def storage_staging(self) -> str:
        return str((__import__("pathlib").Path(self.storage_root) / "staging").resolve())

    @property
    def storage_backup(self) -> str:
        return str((__import__("pathlib").Path(self.storage_root) / "backup").resolve())


settings = Settings()

__all__ = ["Settings", "settings"]
