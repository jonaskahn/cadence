from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select

if TYPE_CHECKING:
    from cadence.infrastructure.persistence.postgresql.client import PostgreSQLClient

from cadence.infrastructure.persistence.postgresql.models import SystemPlugin, utc_now


class SystemPluginRepository:
    """Repository for system-wide plugin catalog.

    Attributes:
        client: PostgreSQL client for database access
    """

    def __init__(self, client: PostgreSQLClient):
        self.client = client

    async def upload(
        self,
        *,
        pid: str,
        version: str,
        name: str,
        description: Optional[str] = None,
        tag: Optional[str] = None,
        s3_path: Optional[str] = None,
        default_settings: Optional[Dict[str, Any]] = None,
        capabilities: Optional[List[Any]] = None,
        agent_type: str = "specialized",
        stateless: bool = True,
        caller_id: Optional[str] = None,
    ) -> SystemPlugin:
        """Insert a new system plugin version, flipping is_latest atomically."""
        async with self.client.session() as session:
            prev_result = await session.execute(
                select(SystemPlugin).where(
                    SystemPlugin.pid == pid,
                    SystemPlugin.is_latest == True,  # noqa: E712
                )
            )
            for prev in prev_result.scalars().all():
                prev.is_latest = False
                prev.updated_at = utc_now()
                prev.updated_by = caller_id

            plugin = SystemPlugin(
                pid=pid,
                version=version,
                name=name,
                description=description,
                tag=tag,
                is_latest=True,
                s3_path=s3_path,
                default_settings=default_settings or {},
                capabilities=capabilities or [],
                agent_type=agent_type,
                stateless=stateless,
                created_by=caller_id,
            )
            session.add(plugin)
            await session.flush()
            return plugin

    async def get_latest(self, pid: str) -> Optional[SystemPlugin]:
        """Retrieve the latest active version of a system plugin."""
        try:
            async with self.client.session() as session:
                result = await session.execute(
                    select(SystemPlugin).where(
                        SystemPlugin.pid == pid,
                        SystemPlugin.is_latest == True,  # noqa: E712
                        SystemPlugin.is_active == True,  # noqa: E712
                    )
                )
                return result.scalar_one_or_none()
        except Exception:
            return None

    async def get_by_version(self, pid: str, version: str) -> Optional[SystemPlugin]:
        """Retrieve a specific version of a system plugin."""
        try:
            async with self.client.session() as session:
                result = await session.execute(
                    select(SystemPlugin).where(
                        SystemPlugin.pid == pid,
                        SystemPlugin.version == version,
                    )
                )
                return result.scalar_one_or_none()
        except Exception:
            return None

    async def get_by_id(self, plugin_id: UUID) -> Optional[SystemPlugin]:
        """Retrieve a system plugin by primary key."""
        if isinstance(plugin_id, str):
            plugin_id = UUID(plugin_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(SystemPlugin).where(SystemPlugin.id == plugin_id)
            )
            return result.scalar_one_or_none()

    async def list_all(self, tag: Optional[str] = None) -> List[SystemPlugin]:
        """List all active system plugins, optionally filtered by tag."""
        async with self.client.session() as session:
            query = select(SystemPlugin).where(
                SystemPlugin.is_active == True  # noqa: E712
            )
            if tag:
                query = query.where(SystemPlugin.tag == tag)
            query = query.order_by(SystemPlugin.pid, SystemPlugin.version)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def soft_delete(
        self, plugin_id: UUID, caller_id: Optional[str] = None
    ) -> bool:
        """Soft-delete a system plugin by setting is_active=False."""
        if isinstance(plugin_id, str):
            plugin_id = UUID(plugin_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(SystemPlugin).where(SystemPlugin.id == plugin_id)
            )
            plugin = result.scalar_one_or_none()
            if not plugin:
                return False
            plugin.is_active = False
            plugin.updated_at = utc_now()
            plugin.updated_by = caller_id
            if plugin.is_latest:
                plugin.is_latest = False
            await session.flush()
            return True
