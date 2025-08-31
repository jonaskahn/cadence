"""Cadence Framework Database Repositories - Repository Pattern Implementation.

This module provides comprehensive repository pattern implementations for data access
in the Cadence multi-agent AI framework. It supports multiple backend strategies with
consistent interfaces and optimized implementations for different deployment scenarios.

Repository Pattern Benefits:
    - Clean separation between business logic and data persistence
    - Testability through dependency injection and mock repositories
    - Backend flexibility with pluggable implementations
    - Consistent data access patterns across the application
    - Centralized query optimization and caching strategies

Architecture Overview:
    Abstract Interfaces:
        - ThreadRepository: Conversation thread management operations
        - ConversationRepository: Optimized conversation turn storage and retrieval

    Implementation Strategies:
        - InMemory: Fast development and testing with no persistence
        - Database: Production-ready with PostgreSQL/SQLAlchemy

        - (Future) Hybrid: Intelligent backend selection based on data patterns

Key Features:
    - Async/await patterns for non-blocking database operations
    - Batch operations for high-throughput scenarios
    - Optimized queries with proper indexing strategies
    - Connection pooling and transaction management
    - Comprehensive error handling and retry mechanisms

Storage Optimization:
    All repository implementations support Cadence's optimized storage strategy:
    - Significant storage reduction through conversation turn optimization
    - Efficient conversation context reconstruction for LangGraph
    - Token usage tracking and cost attribution
    - Intelligent query patterns for minimal database load

Example Usage:
    Using repositories with dependency injection:

    ```python
    from cadence.infrastructure.database.repositories import (
        ThreadRepository, ConversationRepository
    )
    from cadence.infrastructure.database import DatabaseFactory
    from cadence.domain.models import Thread, ConversationTurn

    db_factory = DatabaseFactory(settings)
    await db_factory.initialize()

    thread_repo: ThreadRepository
    conversation_repo: ConversationRepository
    thread_repo, conversation_repo = await db_factory.create_repositories()

    thread = Thread(user_id="user-123", org_id="acme-corp")
    created_thread = await thread_repo.create(thread)

    conversation = Conversation(
        thread_id=created_thread.thread_id,
        user_message="Hello, world!",
        assistant_message="Hi! How can I help you today?",
        user_tokens=10,
        assistant_tokens=25
    )
    await conversation_repo.create(conversation)

    history = await conversation_repo.get_conversation_history(
        thread_id=created_thread.thread_id,
        limit=50
    )

    thread.add_conversation_tokens(conversation.user_tokens, conversation.assistant_tokens)
    await thread_repo.update(thread)
    ```

    Testing with in-memory repositories:

    ```python
    from cadence.infrastructure.database.repositories import (
        InMemoryThreadRepository, InMemoryConversationRepository
    )

    thread_repo = InMemoryThreadRepository()
    conversation_repo = InMemoryConversationRepository()

    thread = Thread(user_id="test-user")
    await thread_repo.create(thread)
    ```

    Batch operations for high throughput:

    ```python
    conversations = [
        Conversation(...),
        Conversation(...),
    ]

    await conversation_repo.create_batch(conversations)
    ```

Performance Considerations:
    - Repository implementations use optimized queries with proper indexing
    - Connection pooling prevents connection exhaustion under load
    - Batch operations reduce database round trips
    - Intelligent caching for frequently accessed data
    - Async patterns prevent blocking on I/O operations

The repository layer provides a clean, testable, and performant foundation for all
data access operations in the Cadence framework.
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
