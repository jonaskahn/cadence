"""Database Repositories for Cadence Framework.

This module provides repository pattern implementations for data access in the Cadence
multi-agent AI framework. It supports multiple backend strategies with consistent
interfaces and optimized implementations for different deployment scenarios.
"""

from .conversation_repository import ConversationRepository, InMemoryConversationRepository
from .postgres import PostgreSQLConversationRepository, PostgreSQLThreadRepository
from .redis import RedisConversationRepository, RedisThreadRepository
from .thread_repository import InMemoryThreadRepository, ThreadRepository

__all__ = [
    "ThreadRepository",
    "ConversationRepository",
    "InMemoryThreadRepository",
    "InMemoryConversationRepository",
    "PostgreSQLThreadRepository",
    "PostgreSQLConversationRepository",
    "RedisThreadRepository",
    "RedisConversationRepository",
]
