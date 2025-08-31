"""Cadence Framework Configuration Management System.

This module provides comprehensive configuration management for the Cadence multi-agent
AI framework using Pydantic settings with environment variable support and validation.
The configuration system supports multiple environments, provider-specific settings,
and extensive validation to ensure system reliability.

Configuration Features:
    - Environment variable support with CADENCE_ prefix
    - .env file loading with validation
    - Multi-provider LLM configuration (OpenAI, Anthropic, Google, Azure)
    - Database backend configuration (PostgreSQL, Redis)
    - Plugin system configuration with directory discovery
    - API server and middleware configuration
    - Session and conversation management settings
    - Comprehensive field validation with helpful error messages

Main Components:
    Settings: Complete application configuration with validation and helpers

Usage Patterns:
    Loading configuration from environment:

    ```python
    from cadence.config import Settings

    settings = Settings()

    api_port = settings.api_port
    llm_provider = settings.default_llm_provider
    ```

    Validating provider credentials:

    ```python
    settings = Settings()
    if not settings.validate_provider_credentials("openai"):
        raise ValueError("OpenAI credentials not configured")
    ```

    Getting provider-specific configurations:

    ```python
    openai_key = settings.get_api_key_for_provider("openai")
    azure_params = settings.get_provider_extra_params("azure")
    ```

Environment Configuration:
    All settings can be configured via environment variables with the CADENCE_ prefix:

    ```bash
    export CADENCE_API_PORT=8080
    export CADENCE_DEFAULT_LLM_PROVIDER=anthropic
    export CADENCE_ANTHROPIC_API_KEY=your-key-here
    export CADENCE_DEBUG=true
    ```

For detailed configuration options, see the Settings class documentation.
"""

from .settings import Settings

__all__ = ["Settings"]
