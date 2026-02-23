"""Orchestrator lifecycle and execution exceptions."""

from typing import Optional

from cadence.exception.base import CadenceException


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
    """Orchestrator instance is not ready to handle requests."""

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

    def __init__(self, instance_id: str, timeout_seconds: int, **kwargs):
        super().__init__(
            message=f"Orchestrator operation timed out after {timeout_seconds} seconds",
            code="ORCHESTRATOR_TIMEOUT",
            instance_id=instance_id,
            details={"timeout_seconds": timeout_seconds},
            **kwargs,
        )
