from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional
from uuid import UUID

from sqlalchemy import delete, select

if TYPE_CHECKING:
    from cadence.infrastructure.persistence.postgresql.client import PostgreSQLClient

from cadence.infrastructure.persistence.postgresql.models import (
    OrganizationSettings,
    utc_now,
)


class OrganizationSettingsRepository:
    """Repository for organization settings operations (Tier 3).

    Attributes:
        client: PostgreSQL client for database access
    """

    def __init__(self, client: PostgreSQLClient):
        self.client = client

    async def get_all_for_org(self, org_id: str | UUID) -> List[OrganizationSettings]:
        """Retrieve all settings for an organization.

        Args:
            org_id: Organization identifier

        Returns:
            List of OrganizationSettings instances
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(OrganizationSettings).where(
                    OrganizationSettings.org_id == org_id
                )
            )
            return list(result.scalars().all())

    async def get_by_key(
        self, org_id: str | UUID, key: str
    ) -> Optional[OrganizationSettings]:
        """Retrieve setting by key for organization.

        Args:
            org_id: Organization identifier
            key: Setting key

        Returns:
            OrganizationSettings instance or None
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(OrganizationSettings).where(
                    OrganizationSettings.org_id == org_id,
                    OrganizationSettings.key == key,
                )
            )
            return result.scalar_one_or_none()

    async def upsert(
        self,
        org_id: str | UUID,
        key: str,
        value: Any,
        caller_id: Optional[str] = None,
    ) -> OrganizationSettings:
        """Create or update organization setting.

        Args:
            org_id: Organization identifier
            key: Setting key
            value: Setting value
            caller_id: User ID performing the operation

        Returns:
            Created or updated OrganizationSettings instance
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(OrganizationSettings).where(
                    OrganizationSettings.org_id == org_id,
                    OrganizationSettings.key == key,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.value = value
                existing.updated_at = utc_now()
                existing.updated_by = caller_id
                await session.flush()
                return existing

            setting = OrganizationSettings(
                org_id=org_id,
                key=key,
                value=value,
                created_by=caller_id,
            )
            session.add(setting)
            await session.flush()
            return setting

    async def delete(self, org_id: str | UUID, key: str) -> bool:
        """Delete organization setting.

        Args:
            org_id: Organization identifier
            key: Setting key

        Returns:
            True if deleted, False if not found
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            result = await session.execute(
                delete(OrganizationSettings).where(
                    OrganizationSettings.org_id == org_id,
                    OrganizationSettings.key == key,
                )
            )
            return result.rowcount > 0
