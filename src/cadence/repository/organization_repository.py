from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import delete, select

if TYPE_CHECKING:
    from cadence.infrastructure.persistence.postgresql.client import PostgreSQLClient

from cadence.infrastructure.persistence.postgresql.models import Organization, utc_now


class OrganizationRepository:
    """Repository for organization operations.

    Attributes:
        client: PostgreSQL client for database access
    """

    def __init__(self, client: PostgreSQLClient):
        self.client = client

    async def create(
        self, org_id: str | UUID, name: str, caller_id: Optional[str] = None
    ) -> Organization:
        """Create new organization.

        Args:
            org_id: Organization identifier (UUID or string)
            name: Organization name
            caller_id: User ID performing the operation

        Returns:
            Created Organization instance
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            org = Organization(
                id=org_id,
                name=name,
                status="active",
                created_by=caller_id,
            )
            session.add(org)
            await session.flush()
            return org

    async def get_by_id(self, org_id: str | UUID) -> Optional[Organization]:
        """Retrieve organization by ID.

        Args:
            org_id: Organization identifier (UUID or string)

        Returns:
            Organization instance or None
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(Organization).where(Organization.id == org_id)
            )
            return result.scalar_one_or_none()

    async def get_all(self) -> List[Organization]:
        """Retrieve all organizations.

        Returns:
            List of Organization instances
        """
        async with self.client.session() as session:
            result = await session.execute(select(Organization))
            return list(result.scalars().all())

    async def update_status(
        self, org_id: str | UUID, status: str, caller_id: Optional[str] = None
    ) -> Optional[Organization]:
        """Update organization status.

        Args:
            org_id: Organization identifier (UUID or string)
            status: New status
            caller_id: User ID performing the operation

        Returns:
            Updated Organization instance or None
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(Organization).where(Organization.id == org_id)
            )
            org = result.scalar_one_or_none()

            if org:
                org.status = status
                org.updated_at = utc_now()
                org.updated_by = caller_id
                await session.flush()
            return org

    async def delete(self, org_id: str | UUID) -> bool:
        """Delete organization.

        Args:
            org_id: Organization identifier (UUID or string)

        Returns:
            True if deleted, False if not found
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            result = await session.execute(
                delete(Organization).where(Organization.id == org_id)
            )
            return result.rowcount > 0
