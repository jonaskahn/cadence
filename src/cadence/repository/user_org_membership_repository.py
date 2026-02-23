from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

from sqlalchemy import delete, select

if TYPE_CHECKING:
    from cadence.infrastructure.persistence.postgresql.client import PostgreSQLClient

from cadence.infrastructure.persistence.postgresql.models import (
    UserOrgMembership,
    utc_now,
)


class UserOrgMembershipRepository:
    """Repository for user-organization membership operations.

    Manages which organizations users belong to and their admin status
    within each organization.

    Attributes:
        client: PostgreSQL client for database access
    """

    def __init__(self, client: PostgreSQLClient):
        self.client = client

    async def create(
        self,
        user_id: str | UUID,
        org_id: str | UUID,
        is_admin: bool = False,
        caller_id: Optional[str] = None,
    ) -> UserOrgMembership:
        """Add a user to an organization.

        Args:
            user_id: User identifier
            org_id: Organization identifier
            is_admin: Whether the user is an admin of this org
            caller_id: User ID performing the operation

        Returns:
            Created UserOrgMembership instance
        """
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            membership = UserOrgMembership(
                user_id=user_id,
                org_id=org_id,
                is_admin=is_admin,
                created_by=caller_id,
            )
            session.add(membership)
            await session.flush()
            return membership

    async def get(
        self, user_id: str | UUID, org_id: str | UUID
    ) -> Optional[UserOrgMembership]:
        """Retrieve active membership for a user/org pair.

        Args:
            user_id: User identifier
            org_id: Organization identifier

        Returns:
            UserOrgMembership instance or None
        """
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(UserOrgMembership).where(
                    UserOrgMembership.user_id == user_id,
                    UserOrgMembership.org_id == org_id,
                )
            )
            return result.scalar_one_or_none()

    async def list_for_user(self, user_id: str | UUID) -> List[UserOrgMembership]:
        """List all org memberships for a user.

        Args:
            user_id: User identifier

        Returns:
            List of UserOrgMembership instances
        """
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(UserOrgMembership).where(UserOrgMembership.user_id == user_id)
            )
            return list(result.scalars().all())

    async def list_for_org(self, org_id: str | UUID) -> List[UserOrgMembership]:
        """List all user memberships in an organization.

        Args:
            org_id: Organization identifier

        Returns:
            List of UserOrgMembership instances
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(UserOrgMembership).where(UserOrgMembership.org_id == org_id)
            )
            return list(result.scalars().all())

    async def update_admin_flag(
        self,
        user_id: str | UUID,
        org_id: str | UUID,
        is_admin: bool,
        caller_id: Optional[str] = None,
    ) -> Optional[UserOrgMembership]:
        """Update the admin flag for an existing membership.

        Args:
            user_id: User identifier
            org_id: Organization identifier
            is_admin: New admin value
            caller_id: User ID performing the operation

        Returns:
            Updated UserOrgMembership or None if not found
        """
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(UserOrgMembership).where(
                    UserOrgMembership.user_id == user_id,
                    UserOrgMembership.org_id == org_id,
                )
            )
            membership = result.scalar_one_or_none()
            if membership:
                membership.is_admin = is_admin
                membership.updated_by = caller_id
                membership.updated_at = utc_now()
                await session.flush()
            return membership

    async def delete(self, user_id: str | UUID, org_id: str | UUID) -> bool:
        """Hard-delete a membership row (remove user from org).

        Args:
            user_id: User identifier
            org_id: Organization identifier

        Returns:
            True if a row was deleted, False if not found
        """
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            result = await session.execute(
                delete(UserOrgMembership).where(
                    UserOrgMembership.user_id == user_id,
                    UserOrgMembership.org_id == org_id,
                )
            )
            return result.rowcount > 0

    async def delete_all_for_user(self, user_id: str | UUID) -> int:
        """Hard-delete all memberships for a user.

        Called when a user account is soft-deleted so stale memberships
        are removed and the user loses all org access.

        Args:
            user_id: User identifier

        Returns:
            Number of rows deleted
        """
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        async with self.client.session() as session:
            result = await session.execute(
                delete(UserOrgMembership).where(UserOrgMembership.user_id == user_id)
            )
            return result.rowcount
