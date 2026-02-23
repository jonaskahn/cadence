"""Custom exceptions for Cadence API.

All custom exceptions should inherit from CadenceException for consistent error handling.
"""

from typing import Any, Dict, Optional


class CadenceException(Exception):
    """Base exception for all Cadence errors."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Initialize Cadence exception.

        Args:
            message: Human-readable error message
            code: Error code for programmatic handling
            status_code: HTTP status code
            field: Field name if validation error
            details: Additional error context
        """
        self.message = message
        self.code = code
        self.status_code = status_code
        self.field = field
        self.details = details or {}
        super().__init__(message)


# Authentication & Authorization Errors (401, 403)
class AuthenticationError(CadenceException):
    """Authentication failed."""

    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(
            message=message,
            code=kwargs.pop("code", "AUTHENTICATION_FAILED"),
            status_code=401,
            **kwargs,
        )


class InvalidTokenError(AuthenticationError):
    """Invalid or expired token."""

    def __init__(self, message: str = "Invalid or expired token", **kwargs):
        super().__init__(message=message, code="INVALID_TOKEN", **kwargs)


class AuthorizationError(CadenceException):
    """Authorization failed - insufficient permissions."""

    def __init__(self, message: str = "Insufficient permissions", **kwargs):
        super().__init__(
            message=message,
            code=kwargs.pop("code", "AUTHORIZATION_FAILED"),
            status_code=403,
            **kwargs,
        )


class TenantIsolationError(AuthorizationError):
    """Tenant isolation violation."""

    def __init__(
        self,
        message: str = "Access denied: resource belongs to another tenant",
        **kwargs,
    ):
        super().__init__(message=message, code="TENANT_ISOLATION_VIOLATION", **kwargs)


# Resource Errors (404, 409)
class ResourceNotFoundError(CadenceException):
    """Requested resource not found."""

    def __init__(self, resource: str, resource_id: str, **kwargs):
        super().__init__(
            message=f"{resource} not found: {resource_id}",
            code="RESOURCE_NOT_FOUND",
            status_code=404,
            details={"resource": resource, "resource_id": resource_id},
            **kwargs,
        )


class ResourceAlreadyExistsError(CadenceException):
    """Resource already exists."""

    def __init__(self, resource: str, identifier: str, **kwargs):
        super().__init__(
            message=f"{resource} already exists: {identifier}",
            code="RESOURCE_ALREADY_EXISTS",
            status_code=409,
            details={"resource": resource, "identifier": identifier},
            **kwargs,
        )


class ResourceConflictError(CadenceException):
    """Resource conflict."""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message, code="RESOURCE_CONFLICT", status_code=409, **kwargs
        )


# Validation Errors (400, 422)
class ValidationError(CadenceException):
    """Validation error."""

    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            field=field,
            **kwargs,
        )


class InvalidInputError(ValidationError):
    """Invalid input provided."""

    def __init__(self, field: str, message: str, **kwargs):
        super().__init__(message=message, field=field, code="INVALID_INPUT", **kwargs)


class MissingRequiredFieldError(ValidationError):
    """Required field is missing."""

    def __init__(self, field: str, **kwargs):
        super().__init__(
            message=f"Required field missing: {field}",
            field=field,
            code="MISSING_REQUIRED_FIELD",
            **kwargs,
        )


# Rate Limiting (429)
class RateLimitExceededError(CadenceException):
    """Rate limit exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        details = kwargs.pop("details", {})
        if retry_after:
            details["retry_after"] = retry_after

        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details=details,
            **kwargs,
        )


# Orchestrator Errors (500, 503)
class OrchestratorError(CadenceException):
    """Orchestrator operation failed."""

    def __init__(self, message: str, instance_id: Optional[str] = None, **kwargs):
        details = kwargs.pop("details", {})
        if instance_id:
            details["instance_id"] = instance_id

        super().__init__(
            message=message,
            code=kwargs.pop("code", "ORCHESTRATOR_ERROR"),
            status_code=500,
            details=details,
            **kwargs,
        )


class OrchestratorNotReadyError(OrchestratorError):
    """Orchestrator instance is not ready."""

    def __init__(self, instance_id: str, **kwargs):
        super().__init__(
            message=f"Orchestrator instance not ready: {instance_id}",
            code="ORCHESTRATOR_NOT_READY",
            instance_id=instance_id,
            status_code=503,
            **kwargs,
        )


class OrchestratorTimeoutError(OrchestratorError):
    """Orchestrator operation timed out."""

    def __init__(self, instance_id: str, timeout: int, **kwargs):
        super().__init__(
            message=f"Orchestrator operation timed out after {timeout} seconds",
            code="ORCHESTRATOR_TIMEOUT",
            instance_id=instance_id,
            details={"timeout": timeout},
            **kwargs,
        )


# Plugin Errors
class PluginError(CadenceException):
    """Plugin operation failed."""

    def __init__(self, message: str, plugin_pid: Optional[str] = None, **kwargs):
        details = kwargs.pop("details", {})
        if plugin_pid:
            details["plugin_pid"] = plugin_pid

        super().__init__(
            message=message,
            code=kwargs.pop("code", "PLUGIN_ERROR"),
            status_code=500,
            details=details,
            **kwargs,
        )


class PluginNotFoundError(PluginError):
    """Plugin not found."""

    def __init__(self, plugin_pid: str, **kwargs):
        super().__init__(
            message=f"Plugin not found: {plugin_pid}",
            code="PLUGIN_NOT_FOUND",
            plugin_pid=plugin_pid,
            status_code=404,
            **kwargs,
        )


class PluginValidationError(PluginError):
    """Plugin validation failed."""

    def __init__(self, plugin_pid: str, errors: list, **kwargs):
        super().__init__(
            message=f"Plugin validation failed: {plugin_pid}",
            code="PLUGIN_VALIDATION_FAILED",
            plugin_pid=plugin_pid,
            details={"validation_errors": errors},
            **kwargs,
        )


# LLM Errors
class LLMError(CadenceException):
    """LLM operation failed."""

    def __init__(self, message: str, provider: Optional[str] = None, **kwargs):
        details = kwargs.pop("details", {})
        if provider:
            details["provider"] = provider

        super().__init__(
            message=message,
            code=kwargs.pop("code", "LLM_ERROR"),
            status_code=500,
            details=details,
            **kwargs,
        )


class LLMAPIKeyError(LLMError):
    """LLM API key is invalid or missing."""

    def __init__(self, provider: str, **kwargs):
        super().__init__(
            message=f"Invalid or missing API key for provider: {provider}",
            code="LLM_API_KEY_ERROR",
            provider=provider,
            status_code=401,
            **kwargs,
        )


class LLMRateLimitError(LLMError):
    """LLM rate limit exceeded."""

    def __init__(self, provider: str, **kwargs):
        super().__init__(
            message=f"LLM rate limit exceeded for provider: {provider}",
            code="LLM_RATE_LIMIT_EXCEEDED",
            provider=provider,
            status_code=429,
            **kwargs,
        )


# Database Errors
class DatabaseError(CadenceException):
    """Database operation failed."""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            code=kwargs.pop("code", "DATABASE_ERROR"),
            status_code=500,
            **kwargs,
        )


class DatabaseConnectionError(DatabaseError):
    """Database connection failed."""

    def __init__(self, database: str, **kwargs):
        super().__init__(
            message=f"Failed to connect to database: {database}",
            code="DATABASE_CONNECTION_ERROR",
            details={"database": database},
            status_code=503,
            **kwargs,
        )


# Configuration Errors
class ConfigurationError(CadenceException):
    """Configuration error."""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message, code="CONFIGURATION_ERROR", status_code=500, **kwargs
        )


class SettingsNotFoundError(ConfigurationError):
    """Required settings not found."""

    def __init__(self, key: str, **kwargs):
        super().__init__(
            message=f"Required setting not found: {key}",
            code="SETTINGS_NOT_FOUND",
            details={"key": key},
            **kwargs,
        )
