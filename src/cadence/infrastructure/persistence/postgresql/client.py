"""PostgreSQL async client using SQLAlchemy.

Provides connection management and async session creation.
"""

from contextlib import asynccontextmanager
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class PostgreSQLClient:
    """PostgreSQL client for async database operations.

    Manages database engine and session creation.

    Attributes:
        url: Database connection URL
        engine: SQLAlchemy async engine
        sessionmaker: Session factory
    """

    def __init__(self, url: str):
        """Initialize PostgreSQL client.

        Args:
            url: PostgreSQL connection URL (asyncpg format)
        """
        self.url = url
        self.engine: Optional[AsyncEngine] = None
        self.sessionmaker: Optional[async_sessionmaker] = None

    async def connect(self) -> None:
        """Create engine and session factory."""
        if self.engine is None:
            self.engine = create_async_engine(
                self.url,
                echo=False,
                pool_pre_ping=True,
                pool_size=20,
                max_overflow=10,
                pool_recycle=3600,
            )
            self.sessionmaker = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

    async def disconnect(self) -> None:
        """Dispose of engine and close all connections."""
        if self.engine is not None:
            await self.engine.dispose()
            self.engine = None
            self.sessionmaker = None

    @asynccontextmanager
    async def session(self):
        """Get async database session context manager.

        Yields:
            AsyncSession instance

        Example:
            async with client.session() as session:
                result = await session.execute(select(User))
        """
        if self.sessionmaker is None:
            raise RuntimeError("Client not connected. Call connect() first.")

        session = self.sessionmaker()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
