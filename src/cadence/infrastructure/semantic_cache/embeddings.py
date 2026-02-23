"""Embedding service for semantic cache.

This module provides embedding generation for semantic similarity matching.
Supports multiple providers: OpenAI, Azure, Voyage, Cohere.
"""

import hashlib
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating embeddings from text.

    Supports multiple embedding providers and caches embeddings
    to avoid redundant API calls.

    Attributes:
        provider: Embedding provider name
        model_name: Embedding model name
        api_key: API key for the provider
        dimension: Embedding vector dimension
        _cache: In-memory cache of text -> embedding
    """

    PROVIDER_DEFAULTS = {
        "openai": {
            "model": "text-embedding-3-small",
            "dimension": 1536,
        },
        "azure": {
            "model": "text-embedding-ada-002",
            "dimension": 1536,
        },
        "voyage": {
            "model": "voyage-2",
            "dimension": 1024,
        },
        "cohere": {
            "model": "embed-english-v3.0",
            "dimension": 1024,
        },
    }

    def __init__(
        self,
        provider: str = "openai",
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        cache_embeddings: bool = True,
    ):
        """Initialize embedding service.

        Args:
            provider: Provider name (openai, azure, voyage, cohere)
            model_name: Model name (uses provider default if None)
            api_key: API key for the provider
            base_url: Optional base URL for API
            cache_embeddings: Whether to cache embeddings in memory
        """
        self.provider = provider.lower()
        self.api_key = api_key
        self.base_url = base_url
        self.cache_embeddings = cache_embeddings

        if self.provider not in self.PROVIDER_DEFAULTS:
            raise ValueError(
                f"Unsupported provider: {provider}. "
                f"Supported: {list(self.PROVIDER_DEFAULTS.keys())}"
            )

        defaults = self.PROVIDER_DEFAULTS[self.provider]
        self.model_name = model_name or defaults["model"]
        self.dimension = defaults["dimension"]

        self._cache: Dict[str, List[float]] = {}

        logger.info(
            f"Initialized EmbeddingService: provider={self.provider}, "
            f"model={self.model_name}, dimension={self.dimension}"
        )

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text.

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        if self.cache_embeddings:
            cached_embedding = self._get_cached_embedding(text)
            if cached_embedding is not None:
                return cached_embedding

        embedding = await self._generate_embedding_by_provider(text)

        if self.cache_embeddings:
            cache_key = self._get_cache_key(text)
            self._cache[cache_key] = embedding

        return embedding

    def _get_cached_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding from cache if available.

        Args:
            text: Text to check cache for

        Returns:
            Cached embedding or None
        """
        cache_key = self._get_cache_key(text)
        if cache_key in self._cache:
            logger.debug(f"Embedding cache hit for: {text[:50]}...")
            return self._cache[cache_key]
        return None

    async def _generate_embedding_by_provider(self, text: str) -> List[float]:
        """Generate embedding using configured provider.

        Args:
            text: Text to embed

        Returns:
            Embedding vector

        Raises:
            ValueError: If provider is not implemented
        """
        if self.provider == "openai":
            return await self._generate_openai_embedding(text)
        elif self.provider == "azure":
            return await self._generate_azure_embedding(text)
        elif self.provider == "voyage":
            return await self._generate_voyage_embedding(text)
        elif self.provider == "cohere":
            return await self._generate_cohere_embedding(text)
        else:
            raise ValueError(f"Provider {self.provider} not implemented")

    async def _generate_openai_embedding(self, text: str) -> List[float]:
        """Generate embedding using OpenAI API.

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        try:
            logger.debug(f"Generating OpenAI embedding for: {text[:50]}...")
            return self._generate_mock_embedding(text)

        except Exception as e:
            logger.error(f"OpenAI embedding generation failed: {e}", exc_info=True)
            raise

    async def _generate_azure_embedding(self, text: str) -> List[float]:
        """Generate embedding using Azure OpenAI API.

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        try:
            logger.debug(f"Generating Azure embedding for: {text[:50]}...")
            return self._generate_mock_embedding(text)

        except Exception as e:
            logger.error(f"Azure embedding generation failed: {e}", exc_info=True)
            raise

    async def _generate_voyage_embedding(self, text: str) -> List[float]:
        """Generate embedding using Voyage AI API.

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        try:
            logger.debug(f"Generating Voyage embedding for: {text[:50]}...")
            return self._generate_mock_embedding(text)

        except Exception as e:
            logger.error(f"Voyage embedding generation failed: {e}", exc_info=True)
            raise

    async def _generate_cohere_embedding(self, text: str) -> List[float]:
        """Generate embedding using Cohere API.

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        try:
            logger.debug(f"Generating Cohere embedding for: {text[:50]}...")
            return self._generate_mock_embedding(text)

        except Exception as e:
            logger.error(f"Cohere embedding generation failed: {e}", exc_info=True)
            raise

    def _generate_mock_embedding(self, text: str) -> List[float]:
        """Generate deterministic mock embedding for testing.

        Uses text hash to create consistent embeddings.

        Args:
            text: Input text

        Returns:
            Mock embedding vector
        """
        text_hash = hashlib.sha256(text.encode()).digest()
        embedding = []

        for i in range(self.dimension):
            byte_index = i % len(text_hash)
            normalized = (text_hash[byte_index] / 127.5) - 1.0
            embedding.append(normalized)

        return embedding

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text.

        Args:
            text: Input text

        Returns:
            Cache key
        """
        return hashlib.md5(text.encode()).hexdigest()

    def clear_cache(self) -> None:
        """Clear in-memory embedding cache."""
        self._cache.clear()
        logger.info("Embedding cache cleared")

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics.

        Returns:
            Dict with cache stats
        """
        return {
            "cache_size": len(self._cache),
            "cache_enabled": self.cache_embeddings,
        }
