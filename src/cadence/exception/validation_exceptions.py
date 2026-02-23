"""Input validation and data integrity exceptions."""

from typing import Optional

from cadence.exception.base import CadenceException


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
