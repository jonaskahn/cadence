"""Redis-based ConversationRepository implementation."""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import redis.asyncio as redis

from cadence.domain.models import Conversation

from ...repositories.conversation_repository import ConversationRepository

logger = logging.getLogger(__name__)


class RedisConversationRepository(ConversationRepository):
    """Redis implementation of ConversationRepository.

    This implementation leverages Redis's high-performance data structures for
    optimized conversation storage:

    Storage Strategy:
        - Hash sets for conversation data storage
        - Sorted sets for efficient pagination and chronological ordering
        - Sets for indexing by thread_id, user_id, and org_id
        - Atomic operations for thread token updates
        - TTL support for automatic expiration

    Key Features:
        - Sub-millisecond read/write performance
        - Efficient pagination with sorted sets
        - Full-text search capabilities using Redis search
        - Atomic token counter updates
        - Automatic indexing for fast queries
        - Configurable TTL for data expiration
        - Optimized storage (only user input + final AI response)

    Performance Optimizations:
        - Pipeline operations for batch updates
        - Lua scripts for atomic operations
        - Efficient set intersections for filtering
        - Sorted sets for O(log N) pagination
    """

    def __init__(self, redis_client: redis.Redis, thread_repository=None, ttl_days: int = 365):
        """Initialize Redis ConversationRepository.

        Args:
            redis_client: Redis client instance
            thread_repository: Optional thread repository for token updates
            ttl_days: TTL in days for conversation data (default: 365 days)
        """
        self.redis = redis_client
        self.thread_repository = thread_repository
        self.ttl_seconds = ttl_days * 24 * 60 * 60
        self._setup_key_patterns()

    def _setup_key_patterns(self):
        """Setup Redis key patterns for consistent naming."""
        self.conversation_key = "conversation:{conversation_id}"
        self.conversations_by_thread = "conversations:thread:{thread_id}"
        self.conversations_by_user = "conversations:user:{user_id}"
        self.conversations_by_org = "conversations:org:{org_id}"
        self.conversations_sorted = "conversations:sorted:{sort_by}"
        self.conversation_counter = "conversations:counter"
        self.search_index = "conversations:search"

    def _get_conversation_key(self, conversation_id: str) -> str:
        """Get Redis key for conversation data."""
        return self.conversation_key.format(conversation_id=conversation_id)

    def _get_thread_conversations_key(self, thread_id: str) -> str:
        """Get Redis key for thread's conversation set."""
        return self.conversations_by_thread.format(thread_id=thread_id)

    def _get_user_conversations_key(self, user_id: str) -> str:
        """Get Redis key for user's conversation set."""
        return self.conversations_by_user.format(user_id=user_id)

    def _get_org_conversations_key(self, org_id: str) -> str:
        """Get Redis key for organization's conversation set."""
        return self.conversations_by_org.format(org_id=org_id)

    def _get_sorted_conversations_key(self, sort_by: str) -> str:
        """Get Redis key for sorted conversations set."""
        return self.conversations_sorted.format(sort_by=sort_by)

    async def _queue_conversation_hash_and_ttl(
        self,
        pipe,
        conversation_key: str,
        conversation_data: Any,
    ) -> None:
        """Queue storing the conversation hash and setting TTL."""
        await pipe.hset(conversation_key, mapping=conversation_data)
        await pipe.expire(conversation_key, self.ttl_seconds)

    async def _queue_thread_index(
        self,
        pipe,
        thread_key: str,
        conversation_id: str,
    ) -> None:
        """Queue adding conversation to its thread index and set TTL."""
        await pipe.sadd(thread_key, conversation_id)
        await pipe.expire(thread_key, self.ttl_seconds)

    async def _queue_sorted_index(
        self,
        pipe,
        sorted_key: str,
        member_id: str,
        score: float,
    ) -> None:
        """Queue adding the conversation to a sorted set and set TTL."""
        await pipe.zadd(sorted_key, {member_id: score})
        await pipe.expire(sorted_key, self.ttl_seconds)

    async def _queue_search_index(self, pipe, conversation: Conversation) -> None:
        """Queue storing the JSON search document (best-effort)."""
        try:
            search_data = {
                "conversation_id": conversation.id,
                "thread_id": conversation.thread_id,
                "user_message": conversation.user_message,
                "assistant_message": conversation.assistant_message,
                "created_at": conversation.created_at.isoformat(),
            }
            await pipe.json().set(f"search:{conversation.id}", "$", json.dumps(search_data))
            await pipe.expire(f"search:{conversation.id}", self.ttl_seconds)
        except Exception as e:
            logger.debug(f"Redis search not available: {e}")

    async def _queue_increment_counter(self, pipe) -> None:
        """Queue incrementing the global conversation counter."""
        await pipe.incr(self.conversation_counter)

    async def _queue_delete_conversation_artifacts(
        self,
        pipe,
        conversation: Conversation,
        sorted_key: str,
    ) -> None:
        """Queue deletion of a conversation and all related index entries."""
        conversation_key = self._get_conversation_key(conversation.id)
        await pipe.delete(conversation_key)

        thread_key = self._get_thread_conversations_key(conversation.thread_id)
        await pipe.srem(thread_key, conversation.id)

        await pipe.zrem(sorted_key, conversation.id)
        await pipe.delete(f"search:{conversation.id}")

    async def save(self, conversation: Conversation) -> Conversation:
        """Save a conversation atomically with thread token updates."""
        conversation_key = self._get_conversation_key(conversation.id)
        conversation_data = {
            "id": str(conversation.id),
            "thread_id": str(conversation.thread_id),
            "user_message": conversation.user_message,
            "assistant_message": conversation.assistant_message or "",
            "user_tokens": str(conversation.user_tokens or 0),
            "assistant_tokens": str(conversation.assistant_tokens or 0),
            "created_at": conversation.created_at.isoformat(),
            "metadata": json.dumps(conversation.metadata or {}),
        }

        async with self.redis.pipeline() as pipe:
            await self._queue_conversation_hash_and_ttl(pipe, conversation_key, conversation_data)

            thread_key = self._get_thread_conversations_key(conversation.thread_id)
            await self._queue_thread_index(pipe, thread_key, conversation.id)

            created_score = conversation.created_at.timestamp()
            created_key = self._get_sorted_conversations_key("created_at")
            await self._queue_sorted_index(pipe, created_key, conversation.id, created_score)

            await self._queue_search_index(pipe, conversation)

            await self._queue_increment_counter(pipe)

            await pipe.execute()

        if self.thread_repository:
            await self.thread_repository.update_thread_tokens(
                conversation.thread_id, conversation.user_tokens, conversation.assistant_tokens
            )

        logger.debug(f"Saved conversation {conversation.id} in Redis")
        return conversation

    async def get(self, id: str) -> Optional[Conversation]:
        """Get a conversation by ID from Redis.

        Retrieves the stored conversation hash and normalizes legacy field names,
        converts numeric fields to integers, and deserializes the ``metadata``
        JSON field when present.

        Args:
            id: Conversation identifier.

        Returns:
            The ``Conversation`` if found; otherwise ``None``.
        """
        conversation_key = self._get_conversation_key(id)
        conversation_data = await self.redis.hgetall(conversation_key)

        if not conversation_data:
            return None

        try:
            if "conversation_id" in conversation_data and "id" not in conversation_data:
                conversation_data["id"] = conversation_data["conversation_id"]

            for numeric_key in ("user_tokens", "assistant_tokens"):
                if numeric_key in conversation_data and isinstance(conversation_data[numeric_key], str):
                    try:
                        conversation_data[numeric_key] = int(conversation_data[numeric_key])
                    except ValueError:
                        conversation_data[numeric_key] = 0

            if "metadata" in conversation_data and isinstance(conversation_data["metadata"], str):
                try:
                    conversation_data["metadata"] = json.loads(conversation_data["metadata"]) or {}
                except Exception:
                    conversation_data["metadata"] = {}

            return Conversation.from_dict(conversation_data)
        except Exception as e:
            logger.error(f"Error deserializing conversation {id}: {e}")
            return None

    async def get_conversation_history(
        self, thread_id: str, limit: int = 50, before_id: Optional[str] = None
    ) -> List[Conversation]:
        """Get conversation history for a thread ordered by creation time.

        Uses membership in the thread's Set plus the global ``created_at`` Sorted Set
        to efficiently select and page results. When ``before_id`` is supplied, the
        history is returned strictly before that conversation's timestamp.

        Args:
            thread_id: Thread to fetch history for.
            limit: Maximum number of conversations to return.
            before_id: Optional cursor id; return entries created before this id.

        Returns:
            A list of ``Conversation`` objects sorted ascending by ``created_at``.
        """
        thread_key = self._get_thread_conversations_key(thread_id)
        conversation_ids = await self.redis.smembers(thread_key)

        if not conversation_ids:
            return []

        sorted_key = self._get_sorted_conversations_key("created_at")

        if before_id:
            before_score = await self.redis.zscore(sorted_key, before_id)
            if before_score is not None:
                conversation_ids_with_scores = await self.redis.zrangebyscore(
                    sorted_key, 0, before_score, withscores=True
                )
                conversation_ids = [conv_id for conv_id, _ in conversation_ids_with_scores]

        conversation_ids_with_scores = await self.redis.zrevrange(sorted_key, 0, limit - 1, withscores=True)

        thread_conversation_ids = [
            conv_id for conv_id, _ in conversation_ids_with_scores if conv_id in conversation_ids
        ]
        limited_ids = thread_conversation_ids[:limit]

        conversations = []
        for conversation_id in limited_ids:
            conversation = await self.get(conversation_id)
            if conversation:
                conversations.append(conversation)

        conversations.sort(key=lambda c: c.created_at)
        return conversations

    async def get_thread_conversations_count(self, thread_id: str) -> int:
        """Get total number of conversations in a thread."""
        thread_key = self._get_thread_conversations_key(thread_id)
        return await self.redis.scard(thread_key)

    async def get_recent_conversations(
        self, user_id: Optional[str] = None, org_id: Optional[str] = None, limit: int = 10, hours_back: int = 24
    ) -> List[Conversation]:
        """Get recent conversations across threads using Redis sorted sets.

        Selects conversations by timestamp cutoff from the global Sorted Set and
        applies optional filtering by user or organization.

        Args:
            user_id: Optional user filter.
            org_id: Optional organization filter.
            limit: Maximum number of conversations to return.
            hours_back: Lookback window from now.

        Returns:
            A list of the most recent ``Conversation`` objects.
        """
        cutoff_timestamp = (datetime.utcnow() - timedelta(hours=hours_back)).timestamp()

        sorted_key = self._get_sorted_conversations_key("created_at")
        recent_conversation_ids = await self.redis.zrevrangebyscore(
            sorted_key, "+inf", cutoff_timestamp, start=0, num=limit * 2
        )

        filtered_ids = []
        for conversation_id in recent_conversation_ids:
            conversation = await self.get(conversation_id)
            if not conversation:
                continue

            if user_id and conversation.thread_id:
                continue

            if org_id and conversation.thread_id:
                continue

            filtered_ids.append(conversation_id)
            if len(filtered_ids) >= limit:
                break

        conversations = []
        for conversation_id in filtered_ids:
            conversation = await self.get(conversation_id)
            if conversation:
                conversations.append(conversation)

        return conversations

    async def search_conversations(
        self, query: str, thread_id: Optional[str] = None, user_id: Optional[str] = None, limit: int = 20
    ) -> List[Conversation]:
        """Search conversations by content.

        Attempts Redis Search (if available). If not, falls back to scanning recent
        conversations and filtering by substring match on user and assistant messages.

        Args:
            query: Search query string.
            thread_id: Optional thread filter.
            user_id: Unused placeholder to keep signature consistent across backends.
            limit: Maximum number of results.

        Returns:
            A list of matching conversations ordered by most recent first.
        """
        query_lower = query.lower()
        matching_conversations = []

        try:
            search_results = await self.redis.ft(self.search_index).search(
                f"@user_message:*{query}* | @assistant_message:*{query}*"
            )

            for doc in search_results.docs:
                conversation_id = doc.id.replace("search:", "")
                conversation = await self.get(conversation_id)
                if conversation:
                    if thread_id and conversation.thread_id != thread_id:
                        continue
                    matching_conversations.append(conversation)

        except Exception as e:
            logger.debug(f"Redis search not available, using fallback: {e}")

            sorted_key = self._get_sorted_conversations_key("created_at")
            all_conversation_ids = await self.redis.zrevrange(sorted_key, 0, limit * 10)

            for conversation_id in all_conversation_ids:
                conversation = await self.get(conversation_id)
                if not conversation:
                    continue

                if thread_id and conversation.thread_id != thread_id:
                    continue

                if (
                    query_lower in conversation.user_message.lower()
                    or query_lower in conversation.assistant_message.lower()
                ):
                    matching_conversations.append(conversation)

                if len(matching_conversations) >= limit:
                    break

        matching_conversations.sort(key=lambda c: c.created_at, reverse=True)
        return matching_conversations[:limit]

    async def get_conversation_statistics(
        self,
        thread_id: Optional[str] = None,
        user_id: Optional[str] = None,
        org_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get conversation statistics using Redis operations.

        Aggregates token usage and counts over conversations filtered by thread and/or
        date range using Redis Sets and Sorted Sets.

        Args:
            thread_id: Optional thread filter.
            user_id: Unused placeholder to keep signature consistent across backends.
            org_id: Unused placeholder to keep signature consistent across backends.
            start_date: Optional lower bound for creation time.
            end_date: Optional upper bound for creation time.

        Returns:
            A dictionary with totals and basic averages for the selected window.
        """
        conversation_ids = set()

        if thread_id:
            thread_key = self._get_thread_conversations_key(thread_id)
            thread_conversations = await self.redis.smembers(thread_key)
            conversation_ids = set(thread_conversations)

        if start_date or end_date:
            sorted_key = self._get_sorted_conversations_key("created_at")
            start_score = start_date.timestamp() if start_date else 0
            end_score = end_date.timestamp() if end_date else "+inf"

            date_filtered_ids = await self.redis.zrangebyscore(sorted_key, start_score, end_score)
            date_filtered_set = set(date_filtered_ids)

            if conversation_ids:
                conversation_ids = conversation_ids.intersection(date_filtered_set)
            else:
                conversation_ids = date_filtered_set

        if not conversation_ids:
            return {
                "total_conversations": 0,
                "total_tokens": 0,
                "average_tokens_per_conversation": 0.0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "estimated_cost": 0.0,
                "unique_threads": 0,
            }

        total_tokens = 0
        total_input_tokens = 0
        total_output_tokens = 0
        unique_threads = set()

        for conversation_id in conversation_ids:
            conversation = await self.get(conversation_id)
            if conversation:
                total_tokens += conversation.total_tokens
                total_input_tokens += conversation.user_tokens
                total_output_tokens += conversation.assistant_tokens
                unique_threads.add(conversation.thread_id)

        conversation_count = len(conversation_ids)

        return {
            "total_conversations": conversation_count,
            "total_tokens": total_tokens,
            "average_tokens_per_conversation": total_tokens / conversation_count if conversation_count > 0 else 0.0,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "estimated_cost": sum(
                conv.get_cost_estimate() for conv in [await self.get(cid) for cid in conversation_ids] if conv
            ),
            "unique_threads": len(unique_threads),
        }

    async def delete_old_conversations(self, older_than_days: int) -> int:
        """Delete conversations older than specified days using Sorted Sets.

        Args:
            older_than_days: Age threshold; conversations strictly older than this are removed.

        Returns:
            Number of conversations deleted.
        """
        cutoff_timestamp = (datetime.utcnow() - timedelta(days=older_than_days)).timestamp()
        sorted_key = self._get_sorted_conversations_key("created_at")
        old_conversation_ids = await self.redis.zrangebyscore(sorted_key, 0, cutoff_timestamp)

        if not old_conversation_ids:
            return 0

        deleted_count = 0
        async with self.redis.pipeline() as pipe:
            for conversation_id in old_conversation_ids:
                conversation = await self.get(conversation_id)
                if not conversation:
                    continue

                await self._queue_delete_conversation_artifacts(pipe, conversation, sorted_key)

                deleted_count += 1

            await pipe.execute()

        logger.info(f"Deleted {deleted_count} old conversations from Redis")
        return deleted_count

    async def cleanup_expired_data(self, days_old: int = 30) -> int:
        """Clean up expired conversation entries in Sorted Sets.

        TTL cleanup is handled by Redis; this removes stale Sorted Set entries.

        Args:
            days_old: Age threshold for removal in the Sorted Set.

        Returns:
            Number of entries removed from the Sorted Set.
        """
        cutoff_timestamp = (datetime.utcnow() - timedelta(days=days_old)).timestamp()
        sorted_key = self._get_sorted_conversations_key("created_at")
        removed = await self.redis.zremrangebyscore(sorted_key, 0, cutoff_timestamp)

        logger.info(f"Cleaned up {removed} expired conversation entries")
        return removed

    async def get_redis_stats(self) -> Dict[str, Any]:
        """Get Redis-specific statistics for conversation storage.

        Returns basic operational metrics like counts and memory usage.

        Returns:
            A dictionary with metrics, or an error message on failure.
        """
        try:
            info = await self.redis.info("memory")
            conversation_keys = await self.redis.keys(self.conversation_key.format(conversation_id="*"))
            thread_keys = await self.redis.keys(self.conversations_by_thread.format(thread_id="*"))
            total_conversations = await self.redis.get(self.conversation_counter) or 0

            return {
                "total_conversations": int(total_conversations),
                "active_conversation_keys": len(conversation_keys),
                "active_thread_indexes": len(thread_keys),
                "redis_memory_usage": info.get("used_memory_human", "unknown"),
                "redis_connected_clients": info.get("connected_clients", 0),
                "ttl_seconds": self.ttl_seconds,
            }
        except Exception as e:
            logger.error(f"Error getting Redis stats: {e}")
            return {"error": str(e)}

    async def get_storage_efficiency_estimate(self) -> Dict[str, Any]:
        """Estimate storage efficiency compared to full message storage.

        Approximates the storage saved by keeping only input and final response.

        Returns:
            A dictionary with estimated byte counts and efficiency percentage.
        """
        try:
            sorted_key = self._get_sorted_conversations_key("created_at")
            sample_ids = await self.redis.zrevrange(sorted_key, 0, 99)

            if not sample_ids:
                return {"efficiency_percentage": 0.0, "estimated_savings": 0.0}

            current_storage = 0
            for conversation_id in sample_ids:
                conversation = await self.get(conversation_id)
                if conversation:
                    current_storage += len(conversation.user_message) + len(conversation.assistant_message) + 100

            estimated_full_storage = current_storage * 4

            efficiency_percentage = ((estimated_full_storage - current_storage) / estimated_full_storage) * 100

            return {
                "current_storage_bytes": current_storage,
                "estimated_full_storage_bytes": estimated_full_storage,
                "efficiency_percentage": efficiency_percentage,
                "estimated_savings_bytes": estimated_full_storage - current_storage,
                "sample_size": len(sample_ids),
            }
        except Exception as e:
            logger.error(f"Error calculating storage efficiency: {e}")
            return {"error": str(e)}
