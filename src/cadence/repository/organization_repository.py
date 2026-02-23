from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import delete, select

if TYPE_CHECKING:
    from cadence.infrastructure.persistence.postgresql.client import PostgreSQLClient

from cadence.infrastructure.persistence.postgresql.models import Organization, utc_now

_FIELD_MAP = {"tier": "subscription_tier"}

_ALLOWED_FIELDS = {
    "name",
    "status",
    "display_name",
    "domain",
    "subscription_tier",
    "description",
    "contact_email",
    "website",
    "logo_url",
    "country",
    "timezone",
}


class OrganizationRepository:
    """Repository for organization operations.

    Attributes:
        client: PostgreSQL client for database access
    """

    def __init__(self, client: PostgreSQLClient):
        self.client = client

    async def create(
        self,
        org_id: str | UUID,
        name: str,
        caller_id: Optional[str] = None,
        display_name: Optional[str] = None,
        domain: Optional[str] = None,
        tier: Optional[str] = None,
        description: Optional[str] = None,
        contact_email: Optional[str] = None,
        website: Optional[str] = None,
        logo_url: Optional[str] = None,
        country: Optional[str] = None,
        timezone: Optional[str] = None,
    ) -> Organization:
        """Create new organization.

        Args:
            org_id: Organization identifier (UUID or string)
            name: Organization name
            caller_id: User ID performing the operation
            display_name: Human-friendly display name
            domain: Organization domain
            tier: Subscription tier (default 'free')
            description: Optional description
            contact_email: Contact email address
            website: Website URL
            logo_url: Logo image URL
            country: Country code/name
            timezone: Timezone string

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
                display_name=display_name,
                domain=domain,
                subscription_tier=tier or "free",
                description=description,
                contact_email=contact_email,
                website=website,
                logo_url=logo_url,
                country=country,
                timezone=timezone,
            )
            session.add(org)
            await session.flush()
            return org

    async def update(
        self,
        org_id: str | UUID,
        updates: dict,
        caller_id: Optional[str] = None,
    ) -> Optional[Organization]:
        """Update organization fields.

        Maps the API key 'tier' to the model column 'subscription_tier'.
        Only fields present in updates are modified.

        Args:
            org_id: Organization identifier (UUID or string)
            updates: Dict of fields to update (using API key names)
            caller_id: User ID performing the operation

        Returns:
            Updated Organization instance or None if not found or soft-deleted
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(Organization).where(
                    Organization.id == org_id, ~Organization.is_deleted
                )
            )
            org = result.scalar_one_or_none()
            if not org:
                return None

            for field_name, value in updates.items():
                model_field_name = _FIELD_MAP.get(field_name, field_name)
                if model_field_name in _ALLOWED_FIELDS:
                    setattr(org, model_field_name, value)

            org.updated_at = utc_now()
            org.updated_by = caller_id
            await session.flush()
            return org

    async def get_by_id(self, org_id: str | UUID) -> Optional[Organization]:
        """Retrieve organization by ID (excludes soft-deleted).

        Args:
            org_id: Organization identifier (UUID or string)

        Returns:
            Organization instance or None
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(Organization).where(
                    Organization.id == org_id, ~Organization.is_deleted
                )
            )
            return result.scalar_one_or_none()

    async def get_all(self) -> List[Organization]:
        """Retrieve all non-deleted organizations.

        Returns:
            List of Organization instances
        """
        async with self.client.session() as session:
            result = await session.execute(
                select(Organization).where(~Organization.is_deleted)
            )
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
