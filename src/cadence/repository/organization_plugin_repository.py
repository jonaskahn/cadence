from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import delete, select

if TYPE_CHECKING:
    from cadence.infrastructure.persistence.postgresql.client import PostgreSQLClient

from cadence.infrastructure.persistence.postgresql.models import OrganizationPlugin


class OrganizationPluginRepository:
    """Repository for organization plugin operations.

    Attributes:
        client: PostgreSQL client for database access
    """

    def __init__(self, client: PostgreSQLClient):
        self.client = client

    async def list_all_for_org(self, org_id: str | UUID) -> List[OrganizationPlugin]:
        """Retrieve all plugins for an organization.

        Args:
            org_id: Organization identifier

        Returns:
            List of OrganizationPlugin instances
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(OrganizationPlugin).where(OrganizationPlugin.org_id == org_id)
            )
            return list(result.scalars().all())

    async def list_active_for_org(self, org_id: str | UUID) -> List[OrganizationPlugin]:
        """Retrieve only active plugins for an organization.

        Args:
            org_id: Organization identifier

        Returns:
            List of active OrganizationPlugin instances
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(OrganizationPlugin).where(
                    OrganizationPlugin.org_id == org_id,
                    OrganizationPlugin.status == "active",
                )
            )
            return list(result.scalars().all())

    async def get_by_pid(
        self, org_id: str | UUID, plugin_pid: str
    ) -> Optional[OrganizationPlugin]:
        """Retrieve plugin by PID.

        Args:
            org_id: Organization identifier
            plugin_pid: Plugin PID

        Returns:
            OrganizationPlugin instance or None
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(OrganizationPlugin).where(
                    OrganizationPlugin.org_id == org_id,
                    OrganizationPlugin.plugin_pid == plugin_pid,
                )
            )
            return result.scalar_one_or_none()

    async def create(
        self,
        org_id: str | UUID,
        plugin_pid: str,
        status: str = "active",
        config: Optional[Dict[str, Any]] = None,
        caller_id: Optional[str] = None,
    ) -> OrganizationPlugin:
        """Create new plugin activation.

        Args:
            org_id: Organization identifier
            plugin_pid: Plugin PID
            status: Plugin status (default: active)
            config: Plugin configuration
            caller_id: User ID performing the operation

        Returns:
            Created OrganizationPlugin instance
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            plugin = OrganizationPlugin(
                org_id=org_id,
                plugin_pid=plugin_pid,
                status=status,
                config=config or {},
                created_by=caller_id,
            )
            session.add(plugin)
            await session.flush()
            return plugin

    async def update_status(
        self,
        org_id: str | UUID,
        plugin_pid: str,
        status: str,
        caller_id: Optional[str] = None,
    ) -> Optional[OrganizationPlugin]:
        """Update plugin status.

        Args:
            org_id: Organization identifier
            plugin_pid: Plugin PID
            status: New status
            caller_id: User ID performing the operation

        Returns:
            Updated OrganizationPlugin instance or None
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(OrganizationPlugin).where(
                    OrganizationPlugin.org_id == org_id,
                    OrganizationPlugin.plugin_pid == plugin_pid,
                )
            )
            plugin = result.scalar_one_or_none()

            if plugin:
                plugin.status = status
                plugin.updated_by = caller_id
                await session.flush()
            return plugin

    async def update_config(
        self,
        org_id: str | UUID,
        plugin_pid: str,
        config: Dict[str, Any],
        caller_id: Optional[str] = None,
    ) -> Optional[OrganizationPlugin]:
        """Update plugin configuration.

        Args:
            org_id: Organization identifier
            plugin_pid: Plugin PID
            config: New configuration
            caller_id: User ID performing the operation

        Returns:
            Updated OrganizationPlugin instance or None
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(OrganizationPlugin).where(
                    OrganizationPlugin.org_id == org_id,
                    OrganizationPlugin.plugin_pid == plugin_pid,
                )
            )
            plugin = result.scalar_one_or_none()

            if plugin:
                plugin.config = config
                plugin.updated_by = caller_id
                await session.flush()
            return plugin

    async def delete(self, org_id: str | UUID, plugin_pid: str) -> bool:
        """Delete plugin activation.

        Args:
            org_id: Organization identifier
            plugin_pid: Plugin PID

        Returns:
            True if deleted, False if not found
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            result = await session.execute(
                delete(OrganizationPlugin).where(
                    OrganizationPlugin.org_id == org_id,
                    OrganizationPlugin.plugin_pid == plugin_pid,
                )
            )
            return result.rowcount > 0
