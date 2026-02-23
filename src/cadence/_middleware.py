"""Middleware configuration for the Cadence application."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from cadence.config.app_settings import AppSettings
from cadence.constants import (
    DEFAULT_RATE_LIMIT_MAX_REQUESTS,
    DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
)
from cadence.middleware import ErrorHandlerMiddleware
from cadence.middleware.rate_limiting_middleware import RateLimitMiddleware
from cadence.middleware.tenant_context_middleware import TenantContextMiddleware

logger = logging.getLogger(__name__)


def configure_cors_middleware(application: FastAPI, allowed_origins: list[str]) -> None:
    """Configure CORS middleware with the specified allowed origins."""
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def configure_rate_limiting_middleware(application: FastAPI) -> None:
    """Configure rate limiting middleware using the application-bound Redis client."""

    async def provide_redis_client():
        if not hasattr(application.state, "redis_client"):
            return None
        return application.state.redis_client.get_client()

    application.add_middleware(
        RateLimitMiddleware,
        redis_client=provide_redis_client,
        window_seconds=DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
        max_requests=DEFAULT_RATE_LIMIT_MAX_REQUESTS,
        enabled=True,
    )


def configure_tenant_context_middleware(
    application: FastAPI, settings: AppSettings
) -> None:
    """Configure tenant context middleware for JWT-based session resolution."""
    application.add_middleware(
        TenantContextMiddleware,
        jwt_secret=settings.secret_key,
        jwt_algorithm=settings.jwt_algorithm,
    )


def configure_error_handlers_middleware(
    application: FastAPI, settings: AppSettings
) -> None:
    """Configure error handling middleware and expose debug mode to application state."""
    application.state.debug = settings.debug
    application.state.environment = settings.environment

    application.add_middleware(ErrorHandlerMiddleware)

    logger.info(
        "Error handling middleware configured",
        extra={
            "debug": application.state.debug,
            "environment": application.state.environment,
        },
    )
