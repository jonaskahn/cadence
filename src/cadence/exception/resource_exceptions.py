"""Resource lifecycle exceptions (not found, conflict, duplicate)."""

from cadence.exception.base import CadenceException


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
