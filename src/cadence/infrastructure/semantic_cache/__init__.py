"""Semantic cache infrastructure package.

This package provides semantic caching using embeddings and vector similarity
to cache and retrieve LLM responses based on query similarity.
"""

from cadence.infrastructure.semantic_cache.cache import SemanticCache
from cadence.infrastructure.semantic_cache.embeddings import EmbeddingService

__all__ = [
    "SemanticCache",
    "EmbeddingService",
]
