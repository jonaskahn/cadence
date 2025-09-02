"""Cadence Framework Configuration Management System.

This module provides comprehensive configuration management for the Cadence multi-agent
AI framework using Pydantic settings with environment variable support and validation.
The configuration system supports multiple environments, provider-specific settings,
and extensive validation to ensure system reliability.

The Settings class provides a centralized configuration interface that automatically
loads from environment variables with the CADENCE_ prefix, .env files, and provides
validation for all configuration values.
"""

from .settings import Settings

__all__ = ["Settings"]
