"""Database Connection Management for Cadence Framework.

This module provides comprehensive database connection management for the Cadence multi-agent
AI framework, supporting multiple database backends with connection pooling, health monitoring,
and automatic failover capabilities.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import QueuePool

from ...config.settings import Settings

logger = logging.getLogger(__name__)


class DatabaseConnectionManager:
    """Multi-backend database connection manager with health monitoring and pooling.

    This class orchestrates connections to multiple database backends, providing
    a unified interface for connection management, health monitoring, and performance
    optimization across PostgreSQL and Redis backends.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.postgres_engine = None
        self.postgres_session_factory = None
        self.redis_client = None

    async def initialize_postgresql(self) -> None:
        """Initialize PostgreSQL connection with async SQLAlchemy."""
        if not self.settings.postgres_url:
            logger.warning("No PostgreSQL URL configured, skipping PostgreSQL initialization")
            return

        try:
            self.postgres_engine = create_async_engine(
                self.settings.postgres_url,
                poolclass=QueuePool,
                pool_size=20,
                max_overflow=30,
                pool_pre_ping=True,
                pool_recycle=3600,
                cadence=self.settings.debug,
            )

            self.postgres_session_factory = async_sessionmaker(
                self.postgres_engine, class_=AsyncSession, expire_on_commit=False
            )

            async with self.postgres_session_factory() as session:
                await session.execute("SELECT 1")

            logger.info("✅ PostgreSQL connection initialized successfully")

        except Exception as e:
            logger.error(f"❌ Failed to initialize PostgreSQL: {e}")
            raise

    async def initialize_redis(self) -> None:
        """Initialize Redis connection for session storage and caching."""
        if not self.settings.redis_url:
            logger.warning("No Redis URL configured, skipping Redis initialization")
            return

        try:
            self.redis_client = redis.from_url(
                self.settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=20,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={},
            )

            await self.redis_client.ping()

            logger.info("Redis connection initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
            raise

    @asynccontextmanager
    async def get_postgres_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get PostgreSQL session with automatic cleanup."""
        if not self.postgres_session_factory:
            raise RuntimeError("PostgreSQL not initialized")

        async with self.postgres_session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def get_redis_client(self) -> redis.Redis:
        """Get Redis client."""
        if not self.redis_client:
            raise RuntimeError("Redis not initialized")
        return self.redis_client

    async def close_connections(self) -> None:
        """Close all database connections."""
        try:
            if self.postgres_engine:
                await self.postgres_engine.dispose()
                logger.info("PostgreSQL connection closed")

            if self.redis_client:
                await self.redis_client.aclose()
                logger.info("Redis connection closed")

        except Exception as e:
            logger.error(f"Error closing database connections: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all database connections."""
        health = {
            "postgres": {"status": "not_configured", "error": None},
            "redis": {"status": "not_configured", "error": None},
        }

        if self.postgres_engine:
            try:
                async with self.get_postgres_session() as session:
                    await session.execute("SELECT 1")
                health["postgres"]["status"] = "healthy"
            except Exception as e:
                health["postgres"]["status"] = "unhealthy"
                health["postgres"]["error"] = str(e)

        if self.redis_client:
            try:
                await self.redis_client.ping()
                health["redis"]["status"] = "healthy"
            except Exception as e:
                health["redis"]["status"] = "unhealthy"
                health["redis"]["error"] = str(e)

        return health


connection_manager: Optional[DatabaseConnectionManager] = None


async def initialize_databases(settings: Settings) -> DatabaseConnectionManager:
    """Initialize database connections based on configured backends."""
    global connection_manager

    connection_manager = DatabaseConnectionManager(settings)

    conversation_backend = getattr(settings, "conversation_storage_backend", "memory").lower()

    if conversation_backend == "postgresql":
        await connection_manager.initialize_postgresql()
    elif conversation_backend == "redis":
        await connection_manager.initialize_redis()

    logger.info(f"Database connections initialized for backend: conversation={conversation_backend}")
    return connection_manager


async def get_connection_manager() -> DatabaseConnectionManager:
    """Get the global connection manager."""
    if not connection_manager:
        raise RuntimeError("Database connections not initialized")
    return connection_manager
