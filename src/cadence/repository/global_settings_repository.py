from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional

from sqlalchemy import delete, select

if TYPE_CHECKING:
    from cadence.infrastructure.persistence.postgresql.client import PostgreSQLClient

from cadence.infrastructure.persistence.postgresql.models import GlobalSettings, utc_now


class GlobalSettingsRepository:
    """Repository for global settings operations (Tier 2).

    Attributes:
        client: PostgreSQL client for database access
    """

    def __init__(self, client: PostgreSQLClient):
        self.client = client

    async def get_all(self) -> List[GlobalSettings]:
        """Retrieve all global settings.

        Returns:
            List of GlobalSettings instances
        """
        async with self.client.session() as session:
            result = await session.execute(select(GlobalSettings))
            return list(result.scalars().all())

    async def get_by_key(self, key: str) -> Optional[GlobalSettings]:
        """Retrieve setting by key.

        Args:
            key: Setting key

        Returns:
            GlobalSettings instance or None
        """
        async with self.client.session() as session:
            result = await session.execute(
                select(GlobalSettings).where(GlobalSettings.key == key)
            )
            return result.scalar_one_or_none()

    async def health_check(self) -> None:
        """Verify PostgreSQL connection is alive."""
        async with self.client.session() as session:
            await session.execute(select(GlobalSettings).limit(1))

    async def upsert(
        self,
        key: str,
        value: Any,
        value_type: str,
        description: Optional[str] = None,
        caller_id: Optional[str] = None,
    ) -> GlobalSettings:
        """Create or update global setting.

        Args:
            key: Setting key
            value: Setting value
            value_type: Type of the value
            description: Optional description
            caller_id: User ID performing the operation

        Returns:
            Created or updated GlobalSettings instance
        """
        async with self.client.session() as session:
            result = await session.execute(
                select(GlobalSettings).where(GlobalSettings.key == key)
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.value = value
                existing.value_type = value_type
                existing.updated_at = utc_now()
                existing.updated_by = caller_id
                if description:
                    existing.description = description
                await session.flush()
                return existing

            setting = GlobalSettings(
                key=key,
                value=value,
                value_type=value_type,
                description=description,
                created_by=caller_id,
            )
            session.add(setting)
            await session.flush()
            return setting

    async def delete(self, key: str) -> bool:
        """Delete global setting.

        Args:
            key: Setting key

        Returns:
            True if deleted, False if not found
        """
        async with self.client.session() as session:
            result = await session.execute(
                delete(GlobalSettings).where(GlobalSettings.key == key)
            )
            return result.rowcount > 0
