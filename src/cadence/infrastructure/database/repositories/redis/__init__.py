"""Redis-based repository implementations for Cadence framework.

This module provides Redis implementations of the repository interfaces,
leveraging Redis's high-performance in-memory data structures for optimal
performance in session storage and caching scenarios.

Key Features:
    - High-performance in-memory storage with optional persistence
    - Automatic TTL support for data expiration
    - Atomic operations for thread token updates
    - Efficient indexing and querying using Redis data structures
    - Pub/sub capabilities for real-time updates

Usage:
    ```python
    from cadence.infrastructure.database.repositories.redis import (
        RedisThreadRepository,
        RedisConversationRepository
    )


    redis_client = await get_redis_client()
    thread_repo = RedisThreadRepository(redis_client)
    conversation_repo = RedisConversationRepository(redis_client)
    ```
"""

from .conversation_repository import RedisConversationRepository
from .thread_repository import RedisThreadRepository

__all__ = ["RedisThreadRepository", "RedisConversationRepository"]
