"""Semantic cache implementation using Redis.

This module provides semantic caching of LLM responses using embeddings
and cosine similarity matching.
"""

import json
import logging
import math
from typing import Any, Dict, List, Optional

from cadence.constants import (
    DEFAULT_SEMANTIC_CACHE_TTL,
    DEFAULT_SEMANTIC_SIMILARITY_THRESHOLD,
    REDIS_SCAN_BATCH_SIZE,
)

logger = logging.getLogger(__name__)


class SemanticCache:
    """Semantic cache for LLM responses.

    Stores query embeddings and responses in Redis, using cosine similarity
    to find and retrieve cached responses for semantically similar queries.

    Attributes:
        redis_client: Redis client instance
        embedding_service: Embedding service for generating query embeddings
        key_prefix: Prefix for Redis keys
        default_ttl: Default TTL for cache entries (seconds)
        default_threshold: Default similarity threshold for cache hits
    """

    def __init__(
        self,
        redis_client: Any,
        embedding_service: Any,
        key_prefix: str = "semantic_cache:",
        default_ttl: int = DEFAULT_SEMANTIC_CACHE_TTL,
        default_threshold: float = DEFAULT_SEMANTIC_SIMILARITY_THRESHOLD,
    ):
        """Initialize semantic cache.

        Args:
            redis_client: Redis client instance
            embedding_service: EmbeddingService instance
            key_prefix: Prefix for Redis keys
            default_ttl: Default TTL in seconds (default 1 hour)
            default_threshold: Default similarity threshold (0.0-1.0)
        """
        self.redis_client = redis_client
        self.embedding_service = embedding_service
        self.key_prefix = key_prefix
        self.default_ttl = default_ttl
        self.default_threshold = default_threshold

        logger.info(
            f"Initialized SemanticCache: ttl={default_ttl}s, "
            f"threshold={default_threshold}"
        )

    async def get(
        self,
        query: str,
        threshold: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve cached response for semantically similar query.

        Args:
            query: User query
            threshold: Similarity threshold (uses default if None)

        Returns:
            Cached response dict or None if no match
        """
        if not query or not query.strip():
            return None

        threshold = threshold or self.default_threshold

        try:
            query_embedding = await self.embedding_service.generate_embedding(query)
            cache_keys = await self._get_all_cache_keys()

            best_match, best_similarity = await self._find_best_semantic_match(
                query_embedding, cache_keys
            )

            if best_similarity >= threshold:
                logger.info(
                    f"Semantic cache HIT: similarity={best_similarity:.3f}, "
                    f"threshold={threshold:.3f}, query='{query[:50]}...'"
                )
                return {
                    "response": best_match.get("response"),
                    "metadata": best_match.get("metadata", {}),
                    "similarity": best_similarity,
                    "original_query": best_match.get("query"),
                }

            logger.debug(
                f"Semantic cache MISS: best_similarity={best_similarity:.3f}, "
                f"threshold={threshold:.3f}"
            )
            return None

        except Exception as e:
            logger.error(f"Semantic cache get failed: {e}", exc_info=True)
            return None

    async def _find_best_semantic_match(
        self, query_embedding: List[float], cache_keys: List[str]
    ) -> tuple[Optional[Dict[str, Any]], float]:
        """Find the best semantic match for query embedding.

        Args:
            query_embedding: Query embedding vector
            cache_keys: List of cache keys to search

        Returns:
            Tuple of (best_match_data, best_similarity_score)
        """
        best_match = None
        best_similarity = 0.0

        for cache_key in cache_keys:
            cached_data = await self._load_cache_entry(cache_key)
            if not cached_data:
                continue

            cached_embedding = cached_data.get("embedding")
            if not cached_embedding:
                continue

            similarity = self._cosine_similarity(query_embedding, cached_embedding)

            if similarity > best_similarity:
                best_similarity = similarity
                best_match = cached_data

        return best_match, best_similarity

    async def set(
        self,
        query: str,
        response: Any,
        ttl: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Store query and response in semantic cache.

        Args:
            query: User query
            response: LLM response to cache
            ttl: Time-to-live in seconds (uses default if None)
            metadata: Optional metadata to store with cache entry
        """
        if not query or not query.strip():
            return

        ttl = ttl or self.default_ttl

        try:
            query_embedding = await self.embedding_service.generate_embedding(query)

            cache_entry = {
                "query": query,
                "embedding": query_embedding,
                "response": response,
                "metadata": metadata or {},
            }

            cache_key = self._generate_cache_key(query)
            await self._save_cache_entry(cache_key, cache_entry, ttl)

            logger.info(f"Semantic cache SET: query='{query[:50]}...', ttl={ttl}s")

        except Exception as e:
            logger.error(f"Semantic cache set failed: {e}", exc_info=True)

    async def clear(self) -> int:
        """Clear all semantic cache entries.

        Returns:
            Number of entries cleared
        """
        try:
            cache_keys = await self._get_all_cache_keys()
            count = 0

            for cache_key in cache_keys:
                await self.redis_client.delete(cache_key)
                count += 1

            logger.info(f"Semantic cache cleared: {count} entries removed")
            return count

        except Exception as e:
            logger.error(f"Semantic cache clear failed: {e}", exc_info=True)
            return 0

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache stats
        """
        try:
            cache_keys = await self._get_all_cache_keys()

            return {
                "total_entries": len(cache_keys),
                "key_prefix": self.key_prefix,
                "default_ttl": self.default_ttl,
                "default_threshold": self.default_threshold,
                "embedding_dimension": self.embedding_service.dimension,
            }

        except Exception as e:
            logger.error(f"Get cache stats failed: {e}", exc_info=True)
            return {}

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity (0.0 to 1.0)
        """
        if len(vec1) != len(vec2):
            raise ValueError("Vectors must have same dimension")

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        similarity = dot_product / (magnitude1 * magnitude2)
        return max(0.0, min(1.0, similarity))

    def _generate_cache_key(self, query: str) -> str:
        """Generate Redis key for query.

        Args:
            query: User query

        Returns:
            Redis key
        """
        import hashlib

        query_hash = hashlib.md5(query.encode()).hexdigest()
        return f"{self.key_prefix}{query_hash}"

    async def _get_all_cache_keys(self) -> List[str]:
        """Get all cache keys from Redis.

        Returns:
            List of cache keys
        """
        try:
            pattern = f"{self.key_prefix}*"
            keys = []
            cursor = 0

            while True:
                cursor, batch = await self.redis_client.scan(
                    cursor=cursor,
                    match=pattern,
                    count=REDIS_SCAN_BATCH_SIZE,
                )
                keys.extend(batch)

                if cursor == 0:
                    break

            return keys

        except Exception as e:
            logger.error(f"Get cache keys failed: {e}", exc_info=True)
            return []

    async def _load_cache_entry(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Load cache entry from Redis.

        Args:
            cache_key: Redis key

        Returns:
            Cache entry dict or None
        """
        try:
            data = await self.redis_client.get(cache_key)
            if not data:
                return None

            return json.loads(data)

        except Exception as e:
            logger.error(f"Load cache entry failed: {e}", exc_info=True)
            return None

    async def _save_cache_entry(
        self,
        cache_key: str,
        cache_entry: Dict[str, Any],
        ttl: int,
    ) -> None:
        """Save cache entry to Redis.

        Args:
            cache_key: Redis key
            cache_entry: Cache entry data
            ttl: Time-to-live in seconds
        """
        try:
            data = json.dumps(cache_entry)
            await self.redis_client.setex(cache_key, ttl, data)

        except Exception as e:
            logger.error(f"Save cache entry failed: {e}", exc_info=True)
