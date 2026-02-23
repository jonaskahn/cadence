"""Custom exception hierarchy for Cadence domain errors.

All custom exceptions inherit from CadenceException for consistent error handling
and HTTP response mapping.
"""

from cadence.exception.auth_exceptions import (
    AuthenticationError,
    AuthorizationError,
    InvalidTokenError,
    TenantIsolationError,
)
from cadence.exception.base import CadenceException
from cadence.exception.infra_exceptions import (
    ConfigurationError,
    DatabaseConnectionError,
    DatabaseError,
    SettingsNotFoundError,
)
from cadence.exception.llm_exceptions import LLMAPIKeyError, LLMError, LLMRateLimitError
from cadence.exception.orchestrator_exceptions import (
    OrchestratorError,
    OrchestratorNotReadyError,
    OrchestratorTimeoutError,
)
from cadence.exception.plugin_exceptions import (
    PluginError,
    PluginNotFoundError,
    PluginValidationError,
)
from cadence.exception.rate_limit_exceptions import RateLimitExceededError
from cadence.exception.resource_exceptions import (
    ResourceAlreadyExistsError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from cadence.exception.validation_exceptions import (
    InvalidInputError,
    MissingRequiredFieldError,
    ValidationError,
)

__all__ = [
    "CadenceException",
    "AuthenticationError",
    "InvalidTokenError",
    "AuthorizationError",
    "TenantIsolationError",
    "ResourceNotFoundError",
    "ResourceAlreadyExistsError",
    "ResourceConflictError",
    "ValidationError",
    "InvalidInputError",
    "MissingRequiredFieldError",
    "RateLimitExceededError",
    "OrchestratorError",
    "OrchestratorNotReadyError",
    "OrchestratorTimeoutError",
    "PluginError",
    "PluginNotFoundError",
    "PluginValidationError",
    "LLMError",
    "LLMAPIKeyError",
    "LLMRateLimitError",
    "DatabaseError",
    "DatabaseConnectionError",
    "ConfigurationError",
    "SettingsNotFoundError",
]
