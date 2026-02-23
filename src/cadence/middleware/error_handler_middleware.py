"""Error handling middleware for Cadence API.

This middleware catches all exceptions and returns consistent error responses.
"""

import logging
import traceback
import uuid

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Receive, Scope, Send

from cadence.controller.schemas.responses import ErrorDetail, error_response
from cadence.exception.api_exceptions import CadenceException

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware:
    """Pure ASGI middleware to catch and format all exceptions."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        response_started = False

        async def send_with_request_id(message: dict) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                headers = MutableHeaders(scope=message)
                headers.append("X-Request-ID", request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception as exc:
            if response_started:
                raise
            response = await self.handle_exception(request, exc, request_id)
            await response(scope, receive, send)

    async def handle_exception(
        self, request: Request, exc: Exception, request_id: str
    ) -> JSONResponse:
        """Handle exception and return formatted error response.

        Args:
            request: Request that caused the exception
            exc: Exception that was raised
            request_id: Request ID for tracing

        Returns:
            JSONResponse with formatted error
        """
        debug_mode = getattr(request.app.state, "debug", False)
        environment = getattr(request.app.state, "environment", "production")
        show_stack_trace = debug_mode or environment == "development"

        path = request.url.path
        method = request.method

        logger.error(
            f"Error processing request: {method} {path}",
            extra={
                "request_id": request_id,
                "path": path,
                "method": method,
                "exception": str(exc),
                "exception_type": type(exc).__name__,
            },
            exc_info=True,
        )

        if isinstance(exc, CadenceException):
            return self._handle_cadence_exception(
                exc, request_id, path, method, show_stack_trace
            )

        elif isinstance(exc, RequestValidationError):
            return self._handle_validation_error(
                exc, request_id, path, method, show_stack_trace
            )

        elif isinstance(exc, PydanticValidationError):
            return self._handle_pydantic_validation_error(
                exc, request_id, path, method, show_stack_trace
            )

        elif isinstance(exc, StarletteHTTPException):
            return self._handle_http_exception(
                exc, request_id, path, method, show_stack_trace
            )

        else:
            return self._handle_generic_exception(
                exc, request_id, path, method, show_stack_trace
            )

    @staticmethod
    def _handle_cadence_exception(
        exc: CadenceException,
        request_id: str,
        path: str,
        method: str,
        show_stack_trace: bool,
    ) -> JSONResponse:
        """Handle Cadence custom exceptions."""
        response_data = error_response(
            code=exc.code,
            message=exc.message,
            field=exc.field,
            details=exc.details,
            request_id=request_id,
            path=path,
            method=method,
            stack_trace=traceback.format_exc() if show_stack_trace else None,
        )

        return JSONResponse(
            status_code=exc.status_code,
            content=response_data,
            headers={"X-Request-ID": request_id},
        )

    @staticmethod
    def _handle_validation_error(
        exc: RequestValidationError,
        request_id: str,
        path: str,
        method: str,
        show_stack_trace: bool,
    ) -> JSONResponse:
        """Handle FastAPI request validation errors."""
        error_details = []
        for error in exc.errors():
            field_path = " -> ".join(str(loc) for loc in error["loc"])
            error_details.append(
                ErrorDetail(
                    code="VALIDATION_ERROR",
                    message=error["msg"],
                    field=field_path,
                    details={"type": error["type"], "input": error.get("input")},
                )
            )

        response_data = error_response(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            errors=error_details,
            request_id=request_id,
            path=path,
            method=method,
            stack_trace=traceback.format_exc() if show_stack_trace else None,
            debug_info={"errors": exc.errors()} if show_stack_trace else None,
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=response_data,
            headers={"X-Request-ID": request_id},
        )

    @staticmethod
    def _handle_pydantic_validation_error(
        exc: PydanticValidationError,
        request_id: str,
        path: str,
        method: str,
        show_stack_trace: bool,
    ) -> JSONResponse:
        """Handle Pydantic validation errors."""
        error_details = []
        for error in exc.errors():
            field_path = " -> ".join(str(loc) for loc in error["loc"])
            error_details.append(
                ErrorDetail(
                    code="VALIDATION_ERROR",
                    message=error["msg"],
                    field=field_path,
                    details={"type": error["type"]},
                )
            )

        response_data = error_response(
            code="VALIDATION_ERROR",
            message="Data validation failed",
            errors=error_details,
            request_id=request_id,
            path=path,
            method=method,
            stack_trace=traceback.format_exc() if show_stack_trace else None,
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=response_data,
            headers={"X-Request-ID": request_id},
        )

    @staticmethod
    def _handle_http_exception(
        exc: StarletteHTTPException,
        request_id: str,
        path: str,
        method: str,
        show_stack_trace: bool,
    ) -> JSONResponse:
        """Handle Starlette HTTP exceptions."""
        status_code_map = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            409: "CONFLICT",
            422: "UNPROCESSABLE_ENTITY",
            429: "TOO_MANY_REQUESTS",
            500: "INTERNAL_SERVER_ERROR",
            502: "BAD_GATEWAY",
            503: "SERVICE_UNAVAILABLE",
            504: "GATEWAY_TIMEOUT",
        }

        code = status_code_map.get(exc.status_code, "HTTP_ERROR")

        response_data = error_response(
            code=code,
            message=exc.detail,
            request_id=request_id,
            path=path,
            method=method,
            details={"status_code": exc.status_code},
            stack_trace=traceback.format_exc() if show_stack_trace else None,
        )

        return JSONResponse(
            status_code=exc.status_code,
            content=response_data,
            headers={"X-Request-ID": request_id},
        )

    @staticmethod
    def _handle_generic_exception(
        exc: Exception,
        request_id: str,
        path: str,
        method: str,
        show_stack_trace: bool,
    ) -> JSONResponse:
        """Handle generic unhandled exceptions."""
        message = str(exc) if show_stack_trace else "An internal error occurred"

        response_data = error_response(
            code="INTERNAL_ERROR",
            message=message,
            request_id=request_id,
            path=path,
            method=method,
            details=(
                {"exception_type": type(exc).__name__} if show_stack_trace else None
            ),
            stack_trace=traceback.format_exc() if show_stack_trace else None,
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=response_data,
            headers={"X-Request-ID": request_id},
        )
