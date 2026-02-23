"""Application infrastructure configuration from environment variables.

This module provides the AppSettings class which loads immutable infrastructure
configuration from environment variables at startup (DB URLs, JWT secrets, ports,
plugin directories, etc.).

AppSettings is NOT part of the runtime settings cascade. Operational defaults
(LLM settings, pool sizes, rate limits, feature flags, etc.) live in the
global_settings database table and are managed via PATCH /api/admin/settings.
Changes to global settings are broadcast to all nodes via RabbitMQ.

For runtime setting resolution, use SettingsResolver which implements the
3-tier cascade: Global settings → Organization settings → Instance config.
"""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from cadence.constants import (
    DEV_SECRET_KEY_PLACEHOLDER,
    ENV_DEVELOPMENT,
    ENV_PRODUCTION,
    LOCALHOST,
)


class AppSettings(BaseSettings):
    """Static configuration loaded from environment variables.

    All settings can be overridden via environment variables with the
    CADENCE_ prefix. For example, api_host can be set via CADENCE_API_HOST.

    Attributes:
        api_host: API server bind address
        api_port: API server port
        postgres_url: PostgreSQL connection URL
        redis_url: Redis connection URL
        redis_default_db: Redis database for caching (default 0)
        redis_ratelimit_db: Redis database for rate limiting (default 1)
        mongo_url: MongoDB connection URL
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Log format (json or text)
        environment: Deployment environment (development, staging, production)
        debug: Enable debug mode
        secret_key: Secret key for JWT signing (must be set in production)
        jwt_algorithm: JWT signing algorithm
        third_party_jwt_secret_key: Secret for third-party JWT verification
        third_party_jwt_algorithm: Algorithm for third-party JWTs
        storage_root: Root directory for file storage
        system_plugins_dir: Directory for system-wide plugins
        tenant_plugins_root: Root directory for tenant-specific plugins
        s3_endpoint_url: S3/MinIO endpoint URL (None = AWS S3, set for MinIO)
        s3_access_key_id: S3 access key ID
        s3_secret_access_key: S3 secret access key
        s3_bucket_name: S3 bucket name for plugin storage
        s3_region: S3 region
        plugin_s3_enabled: Enable S3/MinIO as plugin source of truth
        enable_directory_plugins: Enable filesystem plugin discovery
        api_enabled_protect: Enable API protection (auth required)
        cors_origins: List of allowed CORS origins
        access_token_expire_minutes: JWT access token expiration time
    """

    model_config = SettingsConfigDict(
        env_prefix="CADENCE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    postgres_url: str = Field(
        default="postgresql+asyncpg://cadence:cadence@localhost:5432/cadence"
    )

    redis_url: str = Field(default="redis://localhost:6379")
    redis_default_db: int = Field(default=0)
    redis_ratelimit_db: int = Field(default=1)

    rabbitmq_url: str = Field(
        default="amqp://cadence:cadence_dev_password@localhost/",
        description="RabbitMQ AMQP connection URL",
    )

    mongo_url: str = Field(default="mongodb://localhost:27017")

    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")

    environment: str = Field(default="development")
    debug: bool = Field(default=False)

    secret_key: str = Field(
        default=DEV_SECRET_KEY_PLACEHOLDER,
        description="Secret key for JWT signing - MUST be changed in production",
    )
    jwt_algorithm: str = Field(default="HS256")

    third_party_jwt_secret_key: Optional[str] = Field(default=None)
    third_party_jwt_algorithm: str = Field(default="RS256")

    storage_root: Path = Field(default=Path("/var/lib/cadence/storage"))
    system_plugins_dir: Path = Field(default=Path("/var/lib/cadence/plugins/system"))
    tenant_plugins_root: Path = Field(default=Path("/var/lib/cadence/plugins/tenants"))

    s3_endpoint_url: Optional[str] = Field(default=None)
    s3_access_key_id: str = Field(default="")
    s3_secret_access_key: str = Field(default="")
    s3_bucket_name: str = Field(default="cadence-plugins")
    s3_region: str = Field(default="us-east-1")
    plugin_s3_enabled: bool = Field(default=False)

    enable_directory_plugins: bool = Field(default=True)
    api_enabled_protect: bool = Field(default=True)

    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"]
    )

    access_token_expire_minutes: int = Field(default=30)

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == ENV_PRODUCTION

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == ENV_DEVELOPMENT

    def validate_production_config(self) -> list[str]:
        """Validate configuration for production deployment.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if self.secret_key == DEV_SECRET_KEY_PLACEHOLDER:
            errors.append("SECRET_KEY must be changed in production")

        if self.debug:
            errors.append("DEBUG should be False in production")

        if LOCALHOST in self.postgres_url:
            errors.append("PostgreSQL URL should not use localhost in production")

        if LOCALHOST in self.redis_url:
            errors.append("Redis URL should not use localhost in production")

        if LOCALHOST in self.mongo_url:
            errors.append("MongoDB URL should not use localhost in production")

        return errors


_app_settings: Optional[AppSettings] = None


def get_settings() -> AppSettings:
    """Get singleton instance of static settings.

    Settings are loaded once and cached for application lifetime.

    Returns:
        AppSettings instance
    """
    global _app_settings

    if _app_settings is None:
        _app_settings = AppSettings()

    return _app_settings
