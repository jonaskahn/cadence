"""Database and configuration infrastructure exceptions."""

from cadence.exception.base import CadenceException


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
