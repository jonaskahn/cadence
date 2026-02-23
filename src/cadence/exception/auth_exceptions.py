"""Authentication and authorization exceptions."""

from cadence.exception.base import CadenceException


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
    """Authorization failed — insufficient permissions."""

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
