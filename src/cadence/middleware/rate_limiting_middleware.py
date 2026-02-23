"""Rate limiting middleware using Redis sliding window algorithm.

This module provides rate limiting middleware for protecting API endpoints
from excessive requests using Redis-backed sliding window tracking.
"""

import logging
import time
from typing import Optional

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

from cadence.constants import (
    DEFAULT_RATE_LIMIT_MAX_REQUESTS,
    DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
)

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis sliding window.

    Tracks requests per tenant per endpoint using Redis sorted sets.
    Uses sliding window algorithm for accurate rate limiting.

    Attributes:
        redis_client: Async Redis client
        window_seconds: Time window for rate limit (default: 60)
        max_requests: Maximum requests per window (default: 100)
        enabled: Whether rate limiting is active
        exempt_paths: Paths exempt from rate limiting
    """

    def __init__(
        self,
        app,
        redis_client,
        window_seconds: int = DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
        max_requests: int = DEFAULT_RATE_LIMIT_MAX_REQUESTS,
        enabled: bool = True,
        exempt_paths: Optional[list] = None,
    ):
        """Initialize rate limiting middleware.

        Args:
            app: FastAPI application
            redis_client: Async Redis client
            window_seconds: Time window in seconds (default: 60)
            max_requests: Maximum requests per window (default: 100)
            enabled: Enable/disable rate limiting (default: True)
            exempt_paths: Paths to exempt (default: /health, /docs)
        """
        super().__init__(app)
        self.redis_client = redis_client
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self.enabled = enabled
        self.exempt_paths = exempt_paths or [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]

    async def _get_redis(self):
        """Resolve the Redis client, supporting lazy factory callables."""
        if callable(self.redis_client):
            return await self.redis_client()
        return self.redis_client

    async def dispatch(self, request: Request, call_next):
        """Process request and enforce rate limits.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response from downstream handlers

        Raises:
            HTTPException: If rate limit exceeded (429)
        """
        if not self.enabled or self._is_exempt_path(request.url.path):
            return await call_next(request)

        redis = await self._get_redis()
        if redis is None:
            return await call_next(request)

        tenant_context = getattr(request.state, "tenant_context", None)
        org_id = tenant_context.org_id if tenant_context else "anonymous"

        rate_limit_key = self._build_rate_limit_key(org_id, request.url.path)

        if await self._is_rate_limited(rate_limit_key, redis):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
                headers={"Retry-After": str(self.window_seconds)},
            )

        await self._track_request(rate_limit_key, redis)

        response = await call_next(request)
        return response

    def _is_exempt_path(self, path: str) -> bool:
        """Check if path is exempt from rate limiting.

        Args:
            path: Request path

        Returns:
            True if exempt
        """
        return any(path.startswith(exempt) for exempt in self.exempt_paths)

    def _build_rate_limit_key(self, org_id: str, endpoint: str) -> str:
        """Build Redis key for rate limit tracking.

        Args:
            org_id: Organization ID
            endpoint: API endpoint path

        Returns:
            Redis key string
        """
        normalized_endpoint = endpoint.replace("/", ":")
        return f"ratelimit:{org_id}:{normalized_endpoint}"

    async def _is_rate_limited(self, key: str, redis) -> bool:
        """Check if request should be rate limited.

        Uses Redis sorted set with timestamp scores for sliding window.

        Args:
            key: Redis key for this endpoint
            redis: Resolved Redis client

        Returns:
            True if rate limit exceeded
        """
        now = time.time()
        window_start = now - self.window_seconds

        await redis.zremrangebyscore(key, 0, window_start)

        request_count = await redis.zcard(key)

        return request_count >= self.max_requests

    async def _track_request(self, key: str, redis) -> None:
        """Track request in Redis sorted set.

        Args:
            key: Redis key for this endpoint
            redis: Resolved Redis client
        """
        now = time.time()
        unique_id = f"{now}:{id(self)}"

        await redis.zadd(key, {unique_id: now})

        await redis.expire(key, self.window_seconds * 2)
