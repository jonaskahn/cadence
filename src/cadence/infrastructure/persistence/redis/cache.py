"""Redis-based caching with namespacing.

Provides simple key-value caching with TTL support and namespace
prefixing for multi-tenant isolation.
"""

import json
from typing import Any, Optional

from redis.asyncio import Redis


class RedisCache:
    """Redis cache with namespace support.

    All keys are prefixed with namespace to prevent collisions.
    Supports JSON serialization for complex objects.

    Attributes:
        client: Async Redis client
        namespace: Key prefix for this cache instance
    """

    def __init__(self, client: Redis, namespace: str = "cadence"):
        self.client = client
        self.namespace = namespace

    def build_key(self, key: str) -> str:
        """Build namespaced key.

        Args:
            key: Original key

        Returns:
            Namespaced key
        """
        return f"{self.namespace}:{key}"

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        namespaced_key = self.build_key(key)
        value = await self.client.get(namespaced_key)

        if value is None:
            return None

        return self.deserialize_value(value)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Store value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Optional time-to-live in seconds

        Returns:
            True if successful
        """
        namespaced_key = self.build_key(key)
        serialized_value = self.serialize_value(value)

        if ttl:
            await self.client.setex(namespaced_key, ttl, serialized_value)
        else:
            await self.client.set(namespaced_key, serialized_value)

        return True

    async def delete(self, key: str) -> bool:
        """Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if key existed and was deleted
        """
        namespaced_key = self.build_key(key)
        result = await self.client.delete(namespaced_key)
        return result > 0

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists
        """
        namespaced_key = self.build_key(key)
        result = await self.client.exists(namespaced_key)
        return result > 0

    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment numeric value.

        Args:
            key: Cache key
            amount: Amount to increment by

        Returns:
            New value after increment
        """
        namespaced_key = self.build_key(key)
        return await self.client.incrby(namespaced_key, amount)

    async def expire(self, key: str, ttl: int) -> bool:
        """Set TTL on existing key.

        Args:
            key: Cache key
            ttl: Time-to-live in seconds

        Returns:
            True if TTL was set
        """
        namespaced_key = self.build_key(key)
        return await self.client.expire(namespaced_key, ttl)

    async def clear_namespace(self) -> int:
        """Clear all keys in this namespace.

        WARNING: This deletes all data in the namespace.

        Returns:
            Number of keys deleted
        """
        pattern = f"{self.namespace}:*"
        keys = await self.client.keys(pattern)

        if not keys:
            return 0

        return await self.client.delete(*keys)

    def serialize_value(self, value: Any) -> str:
        """Serialize value for storage.

        Args:
            value: Value to serialize

        Returns:
            JSON string
        """
        if isinstance(value, (str, int, float, bool)):
            return json.dumps(value)

        return json.dumps(value)

    def deserialize_value(self, value: str) -> Any:
        """Deserialize value from storage.

        Args:
            value: JSON string

        Returns:
            Deserialized value
        """
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
