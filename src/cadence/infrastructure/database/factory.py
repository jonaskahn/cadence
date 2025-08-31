"""Database factory for repository and session store creation.

Implements factory pattern for creating database repositories and session stores
based on configuration, providing backend-agnostic access to storage.
"""

import logging
from typing import Any, Dict, Tuple

from ...config.settings import Settings
from .connection import DatabaseConnectionManager, initialize_databases
from .repositories import (
    ConversationRepository,
    InMemoryConversationRepository,
    InMemoryThreadRepository,
    PostgreSQLConversationRepository,
    PostgreSQLThreadRepository,
    RedisConversationRepository,
    RedisThreadRepository,
    ThreadRepository,
)

logger = logging.getLogger(__name__)


class DatabaseFactory:
    """Factory for creating database repositories and session stores.

    Implements factory pattern to provide backend-agnostic access to database
    repositories and session stores with automatic backend selection.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.connection_manager: DatabaseConnectionManager = None

    async def initialize(self) -> None:
        """Initialize database connections for configured backends."""
        self.connection_manager = await initialize_databases(self.settings)
        logger.info("Database factory initialized with configured backends only")

    async def create_repositories(self) -> Tuple[ThreadRepository, ConversationRepository]:
        """Create repository instances based on configuration."""
        backend = self.settings.conversation_storage_backend.lower()
        if backend == "postgresql":
            return await self._create_postgresql_repositories()
        elif backend == "redis":
            return await self._create_redis_repositories()
        else:
            return self._create_memory_repositories()

    @staticmethod
    def _create_memory_repositories() -> Tuple[ThreadRepository, ConversationRepository]:
        """Create in-memory repository implementations."""
        thread_repo = InMemoryThreadRepository()
        conversation_repo = InMemoryConversationRepository(thread_repo)

        logger.info("Created in-memory repositories")
        return thread_repo, conversation_repo

    async def _create_postgresql_repositories(self) -> Tuple[ThreadRepository, ConversationRepository]:
        """Create PostgreSQL repository implementations."""
        if not self.connection_manager:
            raise RuntimeError("Database connections not initialized")

        if not self.connection_manager.postgres_session_factory:
            raise RuntimeError("PostgreSQL not configured")

        thread_repo = PostgreSQLThreadRepository(self.connection_manager.postgres_session_factory)
        conversation_repo = PostgreSQLConversationRepository(
            self.connection_manager.postgres_session_factory, thread_repo
        )

        logger.info("Created PostgreSQL repositories with SQLAlchemy")
        return thread_repo, conversation_repo

    async def _create_redis_repositories(self) -> Tuple[ThreadRepository, ConversationRepository]:
        """Create Redis repository implementations."""
        if not self.connection_manager:
            raise RuntimeError("Database connections not initialized")

        if not self.connection_manager.redis_client:
            raise RuntimeError("Redis is not configured")

        thread_repo = RedisThreadRepository(self.connection_manager.redis_client)
        conversation_repo = RedisConversationRepository(self.connection_manager.redis_client, thread_repo)

        logger.info("Created Redis repositories with high-performance storage")
        return thread_repo, conversation_repo

    async def get_connection_manager(self) -> DatabaseConnectionManager:
        """Get database connection manager."""
        if not self.connection_manager:
            raise RuntimeError("Database factory not initialized")
        return self.connection_manager

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all database backends."""
        if not self.connection_manager:
            return {"status": "not_initialized"}
        db_health = await self.connection_manager.health_check()
        health_info = {
            "database_factory": {
                "status": "healthy",
                "conversation_backend": self.settings.conversation_storage_backend,
                "session_backend": self.settings.session_storage_backend,
                "backends": db_health,
            }
        }

        unhealthy_backends = [name for name, status in db_health.items() if status.get("status") == "unhealthy"]

        if unhealthy_backends:
            health_info["database_factory"]["status"] = "degraded"
            health_info["database_factory"]["unhealthy_backends"] = unhealthy_backends

        return health_info

    async def close(self):
        """Close database connections."""
        if self.connection_manager:
            await self.connection_manager.close_connections()
