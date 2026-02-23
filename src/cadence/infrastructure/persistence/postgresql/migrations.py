"""Database migration utilities using Alembic.

Provides helper functions for initializing and running database migrations.
Actual migration files will be in the alembic/ directory at project root.
"""

from pathlib import Path
from typing import Optional

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncEngine

from .models import BaseModel


async def create_all_tables(engine: AsyncEngine) -> None:
    """Create all database tables.

    For development only. Production should use Alembic migrations.

    Args:
        engine: Async SQLAlchemy engine
    """
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.create_all)


async def drop_all_tables(engine: AsyncEngine) -> None:
    """Drop all database tables.

    WARNING: This deletes all data. Use with caution.

    Args:
        engine: Async SQLAlchemy engine
    """
    async with engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.drop_all)


def get_alembic_config(alembic_ini_path: Optional[Path] = None) -> Config:
    """Get Alembic configuration.

    Args:
        alembic_ini_path: Path to alembic.ini file

    Returns:
        Alembic Config instance
    """
    if alembic_ini_path is None:
        alembic_ini_path = (
            Path(__file__).parent.parent.parent.parent.parent / "alembic.ini"
        )

    config = Config(str(alembic_ini_path))
    return config


def run_migrations_upgrade(revision: str = "head") -> None:
    """Run database migrations upgrade.

    Args:
        revision: Target revision (default: head)
    """
    config = get_alembic_config()
    command.upgrade(config, revision)


def run_migrations_downgrade(revision: str) -> None:
    """Run database migrations downgrade.

    Args:
        revision: Target revision
    """
    config = get_alembic_config()
    command.downgrade(config, revision)


def generate_migration(message: str, autogenerate: bool = True) -> None:
    """Generate new migration file.

    Args:
        message: Migration message
        autogenerate: Whether to autogenerate from model changes
    """
    config = get_alembic_config()
    command.revision(config, message=message, autogenerate=autogenerate)
