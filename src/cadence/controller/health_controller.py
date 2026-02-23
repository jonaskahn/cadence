"""Basic health check endpoint.

This module provides a simple health check endpoint for monitoring
system availability and database connectivity.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health check response model.

    Attributes:
        status: Overall system status (healthy/unhealthy)
        postgres: PostgreSQL connection status
        redis: Redis connection status
        mongodb: MongoDB connection status
        error: Error message if unhealthy
    """

    status: str = Field(..., description="Overall system status")
    postgres: Optional[str] = Field(None, description="PostgreSQL status")
    redis: Optional[str] = Field(None, description="Redis status")
    mongodb: Optional[str] = Field(None, description="MongoDB status")
    error: Optional[str] = Field(None, description="Error message if unhealthy")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "status": "healthy",
                    "postgres": "connected",
                    "redis": "connected",
                    "mongodb": "connected",
                },
                {"status": "unhealthy", "error": "PostgreSQL connection failed"},
            ]
        }


@router.get("/", include_in_schema=False)
async def root_redirect() -> RedirectResponse:
    """Redirect root path to /health."""
    return RedirectResponse(url="/health")


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    response_model=HealthResponse,
    summary="System Health Check",
    description="Verifies system availability and database connectivity. Returns status of PostgreSQL, MongoDB, and Redis connections.",
    responses={
        200: {
            "description": "System is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "postgres": "connected",
                        "redis": "connected",
                        "mongodb": "connected",
                    }
                }
            },
        },
        500: {
            "description": "System is unhealthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "unhealthy",
                        "error": "PostgreSQL connection failed",
                    }
                }
            },
        },
    },
)
async def health_check(request: Request) -> HealthResponse:
    """Basic health check endpoint.

    Verifies system availability and database connections.

    Args:
        request: FastAPI request

    Returns:
        Health status with connection details

    Raises:
        HTTPException: If system unhealthy (500)
    """
    try:
        postgres_repo = request.app.state.postgres_repo
        redis_client = request.app.state.redis_client
        mongo_client = request.app.state.mongo_client

        await _check_postgres(postgres_repo)
        await _check_redis(redis_client)
        await _check_mongo(mongo_client)

        return HealthResponse(
            status="healthy",
            postgres="connected",
            redis="connected",
            mongodb="connected",
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return HealthResponse(
            status="unhealthy",
            error=str(e),
        )


async def _check_postgres(postgres_repo) -> None:
    """Verify PostgreSQL connection.

    Args:
        postgres_repo: PostgreSQL repository

    Raises:
        Exception: If connection fails
    """
    await postgres_repo.health_check()


async def _check_redis(redis_client) -> None:
    """Verify Redis connection.

    Args:
        redis_client: RedisClient wrapper

    Raises:
        Exception: If connection fails
    """
    await redis_client.get_client().ping()


async def _check_mongo(mongo_client) -> None:
    """Verify MongoDB connection.

    Args:
        mongo_client: MongoDBClient wrapper

    Raises:
        Exception: If connection fails
    """
    await mongo_client.client.admin.command("ping")
