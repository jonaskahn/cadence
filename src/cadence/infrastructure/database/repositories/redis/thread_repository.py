"""Redis-based ThreadRepository implementation."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import redis.asyncio as redis

from cadence.domain.models import Thread, ThreadStatus

from ...repositories.thread_repository import ThreadRepository

logger = logging.getLogger(__name__)


class RedisThreadRepository(ThreadRepository):
    """Redis implementation of ThreadRepository.

    This implementation leverages Redis's high-performance data structures:
    - Hash sets for thread data storage
    - Sorted sets for efficient pagination and sorting
    - Sets for indexing by user_id and org_id
    - Atomic operations for token updates
    - TTL support for automatic expiration

    Key Features:
        - Sub-millisecond read/write performance
        - Atomic token counter updates
        - Efficient pagination with sorted sets
        - Automatic indexing for fast queries
        - Configurable TTL for data expiration
    """

    def __init__(self, redis_client: redis.Redis, ttl_days: int = 365):
        """Initialize Redis ThreadRepository.

        Args:
            redis_client: Redis client instance
            ttl_days: TTL in days for thread data (default: 365 days)
        """
        self.redis = redis_client
        self.ttl_seconds = ttl_days * 24 * 60 * 60
        self._setup_key_patterns()

    def _setup_key_patterns(self):
        """Setup Redis key patterns for consistent naming."""
        self.thread_key = "thread:{thread_id}"
        self.threads_by_user = "threads:user:{user_id}"
        self.threads_by_org = "threads:org:{org_id}"
        self.threads_by_status = "threads:status:{status}"
        self.threads_sorted = "threads:sorted:{sort_by}"
        self.thread_counter = "threads:counter"

    def _get_thread_key(self, thread_id: str) -> str:
        """Get Redis key for thread data."""
        return self.thread_key.format(thread_id=thread_id)

    def _get_user_threads_key(self, user_id: str) -> str:
        """Get Redis key for user's thread set."""
        return self.threads_by_user.format(user_id=user_id)

    def _get_org_threads_key(self, org_id: str) -> str:
        """Get Redis key for organization's thread set."""
        return self.threads_by_org.format(org_id=org_id)

    def _get_status_threads_key(self, status: ThreadStatus) -> str:
        """Get Redis key for status-based thread set."""
        return self.threads_by_status.format(status=status.value)

    def _get_sorted_threads_key(self, sort_by: str) -> str:
        """Get Redis key for sorted threads set."""
        return self.threads_sorted.format(sort_by=sort_by)

    async def _queue_thread_hash_and_ttl(self, pipe, thread_key: str, thread_data: Dict[str, Any]) -> None:
        """Queue storing the thread hash and setting TTL."""
        await pipe.hset(thread_key, mapping=thread_data)
        await pipe.expire(thread_key, self.ttl_seconds)

    async def _queue_index_set_and_ttl(self, pipe, index_key: str, member_id: str) -> None:
        """Queue adding a member to a Set index and set TTL."""
        await pipe.sadd(index_key, member_id)
        await pipe.expire(index_key, self.ttl_seconds)

    async def _queue_sorted_set_and_ttl(self, pipe, sorted_key: str, member_id: str, score: float) -> None:
        """Queue adding a member to a Sorted Set and set TTL."""
        await pipe.zadd(sorted_key, {member_id: score})
        await pipe.expire(sorted_key, self.ttl_seconds)

    async def _queue_increment_thread_counter(self, pipe) -> None:
        """Queue incrementing the global thread counter."""
        await pipe.incr(self.thread_counter)

    async def create_thread(self, user_id: str, org_id: str) -> Thread:
        """Create a new thread with Redis storage.

        Persists the thread as a Hash, maintains Set indexes for user/org/status,
        and adds entries to Sorted Sets for ``created_at`` and ``updated_at``.

        Args:
            user_id: Owner of the thread.
            org_id: Organization associated with the thread.

        Returns:
            Newly created ``Thread`` instance.
        """
        thread = Thread(user_id=user_id, org_id=org_id)
        thread_key = self._get_thread_key(thread.thread_id)
        thread_data = thread.to_dict()
        async with self.redis.pipeline() as pipe:
            await self._queue_thread_hash_and_ttl(pipe, thread_key, thread_data)
            user_key = self._get_user_threads_key(user_id)
            await self._queue_index_set_and_ttl(pipe, user_key, thread.thread_id)
            org_key = self._get_org_threads_key(org_id)
            await self._queue_index_set_and_ttl(pipe, org_key, thread.thread_id)
            status_key = self._get_status_threads_key(thread.status)
            await self._queue_index_set_and_ttl(pipe, status_key, thread.thread_id)
            created_score = thread.created_at.timestamp()
            updated_score = thread.updated_at.timestamp()
            created_key = self._get_sorted_threads_key("created_at")
            updated_key = self._get_sorted_threads_key("updated_at")
            await self._queue_sorted_set_and_ttl(pipe, created_key, thread.thread_id, created_score)
            await self._queue_sorted_set_and_ttl(pipe, updated_key, thread.thread_id, updated_score)
            await self._queue_increment_thread_counter(pipe)
            await pipe.execute()

        logger.debug(f"Created thread {thread.thread_id} in Redis")
        return thread

    async def get_thread(self, thread_id: str) -> Optional[Thread]:
        """Get thread by ID from Redis."""
        thread_key = self._get_thread_key(thread_id)
        thread_data = await self.redis.hgetall(thread_key)

        if not thread_data:
            return None

        try:
            return Thread.from_dict(thread_data)
        except Exception as e:
            logger.error(f"Error deserializing thread {thread_id}: {e}")
            return None

    async def update_thread(self, thread: Thread) -> Thread:
        """Update an existing thread in Redis.

        Refreshes the Hash and updates the ``updated_at`` Sorted Set score. If the
        thread transitions to ARCHIVED, moves it from the ACTIVE Set to ARCHIVED.

        Args:
            thread: Thread with updated fields.

        Returns:
            The updated ``Thread`` instance.

        Raises:
            ValueError: If the thread does not exist.
        """
        thread_key = self._get_thread_key(thread.thread_id)
        if not await self.redis.exists(thread_key):
            raise ValueError(f"Thread {thread.thread_id} not found")
        thread.updated_at = datetime.now(timezone.utc)
        thread_data = thread.to_dict()

        async with self.redis.pipeline() as pipe:
            await self._queue_thread_hash_and_ttl(pipe, thread_key, thread_data)
            updated_score = thread.updated_at.timestamp()
            updated_key = self._get_sorted_threads_key("updated_at")
            await self._queue_sorted_set_and_ttl(pipe, updated_key, thread.thread_id, updated_score)

            if thread.status == ThreadStatus.ARCHIVED:
                active_key = self._get_status_threads_key(ThreadStatus.ACTIVE)
                archived_key = self._get_status_threads_key(ThreadStatus.ARCHIVED)
                await pipe.srem(active_key, thread.thread_id)
                await self._queue_index_set_and_ttl(pipe, archived_key, thread.thread_id)
            await pipe.execute()

        logger.debug(f"Updated thread {thread.thread_id} in Redis")
        return thread

    async def archive_thread(self, thread_id: str) -> bool:
        """Archive a thread using Redis operations."""
        thread = await self.get_thread(thread_id)
        if not thread:
            return False

        thread.archive()
        await self.update_thread(thread)
        logger.debug(f"Archived thread {thread_id} in Redis")
        return True

    async def list_threads(
        self,
        user_id: Optional[str] = None,
        org_id: Optional[str] = None,
        status: Optional[ThreadStatus] = None,
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> List[Thread]:
        """List threads with filtering and pagination using Redis sets.

        Applies optional filters via Set intersections and returns threads ordered
        by the specified Sorted Set and paginated via ``limit`` and ``offset``.

        Args:
            user_id: Optional user filter.
            org_id: Optional organization filter.
            status: Optional status filter.
            limit: Maximum number of threads to return.
            offset: Number of items to skip in the ordered list.
            sort_by: Field backing the Sorted Set used for ordering.
            sort_order: Either "desc" or "asc".

        Returns:
            A list of ``Thread`` objects.
        """
        thread_ids = set()
        if user_id:
            user_key = self._get_user_threads_key(user_id)
            user_threads = await self.redis.smembers(user_key)
            thread_ids = set(user_threads) if not thread_ids else thread_ids.intersection(set(user_threads))

        if org_id:
            org_key = self._get_org_threads_key(org_id)
            org_threads = await self.redis.smembers(org_key)
            thread_ids = set(org_threads) if not thread_ids else thread_ids.intersection(set(org_threads))

        if status:
            status_key = self._get_status_threads_key(status)
            status_threads = await self.redis.smembers(status_key)
            thread_ids = set(status_threads) if not thread_ids else thread_ids.intersection(set(status_threads))

        if not thread_ids:
            return []
        sorted_key = self._get_sorted_threads_key(sort_by)
        if sort_order.lower() == "desc":
            sorted_thread_ids = await self.redis.zrevrange(sorted_key, 0, -1)
        else:
            sorted_thread_ids = await self.redis.zrange(sorted_key, 0, -1)
        filtered_ids = [tid for tid in sorted_thread_ids if tid in thread_ids]
        paginated_ids = filtered_ids[offset : offset + limit]
        threads = []
        for thread_id in paginated_ids:
            thread = await self.get_thread(thread_id)
            if thread:
                threads.append(thread)

        return threads

    async def count_threads(
        self, user_id: Optional[str] = None, org_id: Optional[str] = None, status: Optional[ThreadStatus] = None
    ) -> int:
        """Count threads matching filters using Redis sets."""
        thread_ids = set()

        if user_id:
            user_key = self._get_user_threads_key(user_id)
            user_threads = await self.redis.smembers(user_key)
            thread_ids = set(user_threads) if not thread_ids else thread_ids.intersection(set(user_threads))

        if org_id:
            org_key = self._get_org_threads_key(org_id)
            org_threads = await self.redis.smembers(org_key)
            thread_ids = set(org_threads) if not thread_ids else thread_ids.intersection(set(org_threads))

        if status:
            status_key = self._get_status_threads_key(status)
            status_threads = await self.redis.smembers(status_key)
            thread_ids = set(status_threads) if not thread_ids else thread_ids.intersection(set(status_threads))

        return len(thread_ids)

    async def get_thread_stats(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive stats for a thread from Redis."""
        thread = await self.get_thread(thread_id)
        if not thread:
            return None

        return {
            "thread_id": thread.thread_id,
            "total_tokens": thread.total_tokens,
            "input_tokens": thread.input_tokens,
            "output_tokens": thread.output_tokens,
            "message_count": thread.message_count,
            "status": thread.status.value,
            "created_at": thread.created_at.isoformat(),
            "updated_at": thread.updated_at.isoformat(),
            "estimated_cost": thread.get_cost_estimate(),
        }

    async def update_thread_tokens(self, thread_id: str, user_tokens: int, assistant_tokens: int) -> bool:
        """Update thread token counters atomically using Redis."""
        thread_key = self._get_thread_key(thread_id)

        lua_script = """
        local thread_key = KEYS[1]
        local user_tokens = tonumber(ARGV[1])
        local assistant_tokens = tonumber(ARGV[2])
        
        if redis.call('EXISTS', thread_key) == 0 then
            return 0
        end
        
        local current_input = tonumber(redis.call('HGET', thread_key, 'input_tokens') or 0)
        local current_output = tonumber(redis.call('HGET', thread_key, 'output_tokens') or 0)
        local current_message_count = tonumber(redis.call('HGET', thread_key, 'message_count') or 0)
        
        local new_input = current_input + user_tokens
        local new_output = current_output + assistant_tokens
        local new_total = new_input + new_output
        local new_message_count = current_message_count + 1
        
        redis.call('HSET', thread_key, 'input_tokens', new_input)
        redis.call('HSET', thread_key, 'output_tokens', new_output)
        redis.call('HSET', thread_key, 'total_tokens', new_total)
        redis.call('HSET', thread_key, 'message_count', new_message_count)
        redis.call('HSET', thread_key, 'updated_at', ARGV[3])
        
        return 1
        """

        try:
            result = await self.redis.eval(
                lua_script, 1, thread_key, user_tokens, assistant_tokens, datetime.now(timezone.utc).isoformat()
            )

            if result:
                updated_key = self._get_sorted_threads_key("updated_at")
                await self.redis.zadd(updated_key, {thread_id: datetime.now(timezone.utc).timestamp()})
                logger.debug(f"Updated tokens for thread {thread_id}: +{user_tokens} input, +{assistant_tokens} output")
                return True
            else:
                logger.warning(f"Thread {thread_id} not found for token update")
                return False

        except Exception as e:
            logger.error(f"Error updating tokens for thread {thread_id}: {e}")
            return False

    async def cleanup_expired_data(self, days_old: int = 30) -> int:
        """Clean up expired thread entries in Sorted Sets.

        TTL cleanup is handled by Redis; this removes stale Sorted Set entries.

        Args:
            days_old: Age threshold for removal in Sorted Sets.

        Returns:
            Number of entries removed across ``created_at`` and ``updated_at`` Sorted Sets.
        """
        cutoff_timestamp = (datetime.now(timezone.utc) - timedelta(days=days_old)).timestamp()
        created_key = self._get_sorted_threads_key("created_at")
        updated_key = self._get_sorted_threads_key("updated_at")

        removed_created = await self.redis.zremrangebyscore(created_key, 0, cutoff_timestamp)
        removed_updated = await self.redis.zremrangebyscore(updated_key, 0, cutoff_timestamp)

        logger.info(f"Cleaned up {removed_created + removed_updated} expired thread entries")
        return removed_created + removed_updated

    async def get_redis_stats(self) -> Dict[str, Any]:
        """Get Redis-specific statistics for thread storage.

        Returns:
            A dictionary with counts and memory/connection info, or an error.
        """
        try:
            info = await self.redis.info("memory")
            thread_keys = await self.redis.keys(self.thread_key.format(thread_id="*"))
            user_keys = await self.redis.keys(self.threads_by_user.format(user_id="*"))
            org_keys = await self.redis.keys(self.threads_by_org.format(org_id="*"))

            return {
                "total_threads": len(thread_keys),
                "total_user_indexes": len(user_keys),
                "total_org_indexes": len(org_keys),
                "redis_memory_usage": info.get("used_memory_human", "unknown"),
                "redis_connected_clients": info.get("connected_clients", 0),
                "ttl_seconds": self.ttl_seconds,
            }
        except Exception as e:
            logger.error(f"Error getting Redis stats: {e}")
            return {"error": str(e)}
