"""Plugin management and validation exceptions."""

from typing import Optional

from cadence.exception.base import CadenceException


class PluginError(CadenceException):
    """Plugin operation failed."""

    def __init__(self, message: str, plugin_id: Optional[str] = None, **kwargs):
        details = kwargs.pop("details", {})
        if plugin_id:
            details["plugin_id"] = plugin_id

        super().__init__(
            message=message,
            code=kwargs.pop("code", "PLUGIN_ERROR"),
            status_code=500,
            details=details,
            **kwargs,
        )


class PluginNotFoundError(PluginError):
    """Plugin not found."""

    def __init__(self, plugin_id: str, **kwargs):
        super().__init__(
            message=f"Plugin not found: {plugin_id}",
            code="PLUGIN_NOT_FOUND",
            plugin_id=plugin_id,
            status_code=404,
            **kwargs,
        )


class PluginValidationError(PluginError):
    """Plugin validation failed."""

    def __init__(self, plugin_id: str, validation_errors: list, **kwargs):
        super().__init__(
            message=f"Plugin validation failed: {plugin_id}",
            code="PLUGIN_VALIDATION_FAILED",
            plugin_id=plugin_id,
            details={"validation_errors": validation_errors},
            **kwargs,
        )
