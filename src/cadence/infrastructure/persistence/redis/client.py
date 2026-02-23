"""Redis async client management.

Provides Redis client for caching, rate limiting, and pub/sub.
Uses redis-py with hiredis parser for performance.
"""

from typing import Optional

from redis.asyncio import Redis


class RedisClient:
    """Redis client for async operations.

    Manages Redis connection.

    Attributes:
        url: Redis connection URL
        default_db: Default database number
        client: Redis async client
    """

    def __init__(self, url: str, default_db: int = 0):
        """Initialize Redis client.

        Args:
            url: Redis connection URL
            default_db: Default database number
        """
        self.url = url
        self.default_db = default_db
        self.client: Optional[Redis] = None

    async def connect(self) -> None:
        """Create Redis client connection."""
        if self.client is None:
            self.client = Redis.from_url(
                self.url,
                db=self.default_db,
                decode_responses=True,
                encoding="utf-8",
            )

    async def disconnect(self) -> None:
        """Close Redis client connection."""
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    def get_client(self) -> Redis:
        """Get the underlying Redis client.

        Returns:
            Redis client instance
        """
        if self.client is None:
            raise RuntimeError("Client not connected. Call connect() first.")

        return self.client
