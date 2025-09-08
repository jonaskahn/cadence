"""Configuration settings for the Cadence Multi-Agent AI Framework."""

from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Basic application configuration settings."""

    app_name: str = Field(default="Cadence 🤖 Multi-agents AI Framework", description="Application name")
    debug: bool = Field(default=False, description="Enable debug mode")
    environment: str = Field(default="development", description="Environment name")


class APISettings(BaseSettings):
    """API and server configuration settings."""

    api_host: str = Field(default="0.0.0.0", description="API host to bind to")
    api_port: int = Field(default=8000, description="API port to bind to")
    cors_origins: List[str] = Field(default=["*"], description="CORS allowed origins")


class LLMSettings(BaseSettings):
    """LLM provider and model configuration settings."""

    default_llm_provider: str = Field(default="openai", description="Default LLM provider")
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key")
    google_api_key: Optional[str] = Field(default=None, description="Google AI API key")
    default_llm_temperature: float = Field(default=0.1, description="Default temperature for LLM models")
    default_llm_context_window: int = Field(default=32_000, description="Default context window size for LLM models")

    coordinator_llm_provider: Optional[str] = Field(
        default=None, description="LLM provider for the coordinator. Falls back to default if None"
    )
    coordinator_temperature: float = Field(default=0.1, description="Temperature for the coordinator LLM")
    coordinator_max_tokens: int = Field(default=32_000, description="Max tokens for the coordinator LLM")

    suspend_llm_provider: Optional[str] = Field(
        default=None, description="LLM provider for the suspend node. Falls back to default if None"
    )
    suspend_temperature: float = Field(default=0.7, description="Temperature for the suspend node LLM")
    suspend_max_tokens: int = Field(default=32_000, description="Max tokens for the suspend node LLM")

    synthesizer_llm_provider: Optional[str] = Field(
        default=None, description="LLM provider for the synthesizer. Falls back to default if None"
    )
    synthesizer_temperature: float = Field(default=0.7, description="Temperature for the synthesizer LLM")
    synthesizer_max_tokens: int = Field(default=32_000, description="Max tokens for the synthesizer LLM")


class DatabaseSettings(BaseSettings):
    """Database connection configuration settings."""

    postgres_url: Optional[str] = Field(
        default=None, description="PostgreSQL connection URL (e.g., postgresql+asyncpg://user:pass@localhost/cadence)"
    )
    redis_url: Optional[str] = Field(default="redis://localhost:6379", description="Redis connection URL")
    mongo_url: Optional[str] = Field(default=None, description="MongoDB connection URL")
    cassandra_hosts: Optional[List[str]] = Field(default=None, description="Cassandra cluster hosts")
    mariadb_url: Optional[str] = Field(default=None, description="MariaDB connection URL")


class PluginSettings(BaseSettings):
    """Plugin and storage configuration settings."""

    plugins_dir: List[str] = Field(
        default=["./plugins/src/cadence_example_plugins"], description="Directories to search for plugins"
    )
    storage_root: str = Field(default="./storage", description="Root directory for plugin storage")
    enable_directory_plugins: bool = Field(default=True, description="Enable directory-based plugin discovery")


class OrchestratorSettings(BaseSettings):
    """Orchestrator and conversation flow configuration settings."""

    conversation_storage_backend: str = Field(default="memory", description="Conversation storage backend")
    max_agent_hops: int = Field(default=25, description="Maximum agent hops per conversation")
    graph_recursion_limit: int = Field(default=50, description="Maximum graph recursion depth")

    coordinator_consecutive_agent_route_limit: int = Field(
        default=5,
        description="Max consecutive coordinator routes to agents (excluding synthesize) before suspend",
    )
    allowed_coordinator_terminate: bool = Field(
        default=False,
        description="Allow coordinator to terminate conversation directly without routing through synthesizer",
    )
    coordinator_parallel_tool_calls: bool = Field(
        default=False, description="Enable parallel tool calls in coordinator node"
    )

    coordinator_invoke_timeout: int = Field(
        default=3, description="Timeout in seconds for coordinator invoke when not allowed to terminate"
    )

    additional_coordinator_context: str = Field(
        default="You are a helpful Cadence chatbot - designed, trained, customized by JonasKahn",
        description="Additional coordinator context",
    )

    additional_synthesizer_context: str = Field(
        default="You are a helpful Cadence chatbot - designed, trained, customized by JonasKahn",
        description="Additional synthesizer context",
    )

    use_structured_synthesizer: Optional[str] = Field(
        default="model",
        description="Structured synthesizer mode: 'model' for native structured output, 'prompt' for JSON parsing with backoff (BETA), None to disable",
    )

    synthesizer_compact_messages: str = Field(
        default="system",
        description="Compact tool call/result chains before synthesizer to reduce confusion. Receive: system, tool, None",
    )

    synthesizer_compaction_max_chars: int = Field(
        default=6000, description="Max characters to include in compacted tool context"
    )

    synthesizer_compaction_header: str = Field(
        default="Context from tools and intermediate steps (compacted):",
        description="Header prefix for the compacted tool context block",
    )

    additional_suspend_context: str = Field(
        default="You are a helpful Cadence chatbot - designed, trained, customized by JonasKahn",
        description="Additional suspend context",
    )


class SecuritySettings(BaseSettings):
    """Authentication and security configuration settings."""

    secret_key: Optional[str] = Field(default=None, description="Secret key for JWT tokens")
    access_token_expire_minutes: int = Field(default=30, description="Access token expiration time")

    rate_limit_requests: int = Field(default=100, description="Rate limit requests per minute")
    rate_limit_window: int = Field(default=60, description="Rate limit window in seconds")


class LoggingSettings(BaseSettings):
    """Logging configuration settings."""

    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="Log message format"
    )


class MonitoringSettings(BaseSettings):
    """Metrics, tracing, and health check configuration settings."""

    health_check_interval: int = Field(default=30, description="Health check interval in seconds")
    health_check_timeout: int = Field(default=5, description="Health check timeout in seconds")

    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    enable_tracing: bool = Field(default=False, description="Enable distributed tracing")
    enable_profiling: bool = Field(default=False, description="Enable performance profiling")

    enable_prometheus: bool = Field(default=False, description="Enable Prometheus metrics")
    metrics_port: int = Field(default=9090, description="Metrics endpoint port")


class DevelopmentSettings(BaseSettings):
    """Development and testing configuration settings."""

    reload_on_change: bool = Field(default=False, description="Auto-reload on file changes")
    enable_hot_reload: bool = Field(default=False, description="Enable hot reload for development")

    test_mode: bool = Field(default=False, description="Enable test mode")
    mock_external_services: bool = Field(default=False, description="Mock external services in tests")


class Settings(
    AppSettings,
    APISettings,
    LLMSettings,
    DatabaseSettings,
    PluginSettings,
    OrchestratorSettings,
    SecuritySettings,
    LoggingSettings,
    MonitoringSettings,
    DevelopmentSettings,
):
    """Main application configuration settings with environment variable support."""

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
            return "gpt-4.1"
        elif provider == "anthropic":
            return "claude-3-5-sonnet-20241022"
        elif provider == "google":
            return "gemini-1.5-flash"
        else:
            return "gpt-4.1"

    def get_synthesizer_provider_llm_model(self, provider: str) -> str:
        """Get the model name for the synthesizer LLM provider."""
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

    @staticmethod
    def get_provider_extra_params(provider: str) -> dict:
        """Get additional parameters for the specified LLM provider."""
        return {}

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
