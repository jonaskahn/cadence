from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import delete, func, select

if TYPE_CHECKING:
    from cadence.infrastructure.persistence.postgresql.client import PostgreSQLClient

from cadence.infrastructure.persistence.postgresql.models import (
    OrchestratorInstance,
    utc_now,
)


class OrchestratorInstanceRepository:
    """Repository for orchestrator instance operations (Tier 4).

    Attributes:
        client: PostgreSQL client for database access
    """

    def __init__(self, client: PostgreSQLClient):
        self.client = client

    @staticmethod
    def _serialize(instance: OrchestratorInstance) -> Dict[str, Any]:
        """Serialize ORM instance to dict.

        Args:
            instance: OrchestratorInstance ORM object

        Returns:
            Instance data dictionary
        """
        return {
            "instance_id": str(instance.id),
            "org_id": str(instance.org_id),
            "name": instance.name,
            "framework_type": instance.framework_type,
            "mode": instance.mode,
            "status": instance.status,
            "config": instance.config,
            "tier": instance.tier,
            "plugin_settings": instance.plugin_settings or {},
            "config_hash": instance.config_hash,
            "last_accessed_at": (
                instance.last_accessed_at.isoformat()
                if instance.last_accessed_at
                else None
            ),
            "created_at": instance.created_at.isoformat(),
            "updated_at": instance.updated_at.isoformat(),
            "created_by": instance.created_by,
            "updated_by": instance.updated_by,
        }

    async def create(
        self,
        org_id: str | UUID,
        name: str,
        framework_type: str,
        mode: str,
        config: Dict[str, Any],
        tier: str = "cold",
        plugin_settings: Optional[Dict[str, Any]] = None,
        config_hash: Optional[str] = None,
        caller_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create new orchestrator instance.

        Args:
            org_id: Organization identifier
            name: Instance name
            framework_type: Orchestration framework (immutable after creation)
            mode: Orchestration mode (immutable after creation)
            config: Mutable instance configuration (must not include framework_type or mode)
            tier: Pool tier (hot/warm/cold)
            plugin_settings: Per-plugin default settings overrides
            config_hash: SHA-256 hash of config+plugin_settings
            caller_id: User ID performing the operation

        Returns:
            Created instance as dictionary
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            instance = OrchestratorInstance(
                org_id=org_id,
                name=name,
                framework_type=framework_type,
                mode=mode,
                status="active",
                config=config,
                tier=tier,
                plugin_settings=plugin_settings or {},
                config_hash=config_hash,
                created_by=caller_id,
            )
            session.add(instance)
            await session.flush()
            return self._serialize(instance)

    async def get_by_id(self, instance_id) -> Optional[Dict[str, Any]]:
        """Retrieve instance by ID.

        Args:
            instance_id: Instance identifier (UUID or str)

        Returns:
            Instance dictionary or None
        """
        if isinstance(instance_id, str):
            instance_id = UUID(instance_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(OrchestratorInstance).where(
                    OrchestratorInstance.id == instance_id
                )
            )
            instance = result.scalar_one_or_none()
            return self._serialize(instance) if instance else None

    async def list_for_org(
        self, org_id: str | UUID, include_deleted: bool = False
    ) -> List[Dict[str, Any]]:
        """Retrieve all instances for an organization.

        Args:
            org_id: Organization identifier
            include_deleted: If False (default), exclude status='deleted' instances

        Returns:
            List of instance dictionaries
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            query = select(OrchestratorInstance).where(
                OrchestratorInstance.org_id == org_id
            )

            if not include_deleted:
                query = query.where(OrchestratorInstance.status != "is_deleted")

            result = await session.execute(query)
            return [self._serialize(i) for i in result.scalars().all()]

    async def list_all(self) -> List[Dict[str, Any]]:
        """List all non-deleted instances (for pool loading).

        Returns:
            List of instance dictionaries
        """
        async with self.client.session() as session:
            result = await session.execute(
                select(OrchestratorInstance).where(
                    OrchestratorInstance.status != "is_deleted"
                )
            )
            return [self._serialize(i) for i in result.scalars().all()]

    async def list_by_tier(
        self, tier: str, status: str = "active"
    ) -> List[Dict[str, Any]]:
        """List instances by tier and status.

        Args:
            tier: Pool tier (hot/warm/cold)
            status: Instance status filter

        Returns:
            List of instance dictionaries
        """
        async with self.client.session() as session:
            result = await session.execute(
                select(OrchestratorInstance).where(
                    OrchestratorInstance.tier == tier,
                    OrchestratorInstance.status == status,
                    ~OrchestratorInstance.is_deleted,
                )
            )
            return [self._serialize(i) for i in result.scalars().all()]

    async def update_plugin_settings(
        self,
        instance_id,
        plugin_settings: Dict[str, Any],
        config_hash: Optional[str] = None,
        caller_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update plugin_settings and config_hash on an instance.

        Args:
            instance_id: Instance identifier (UUID or str)
            plugin_settings: New plugin settings dict
            config_hash: New config hash
            caller_id: User ID performing the operation

        Returns:
            Updated instance dict or None
        """
        if isinstance(instance_id, str):
            instance_id = UUID(instance_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(OrchestratorInstance).where(
                    OrchestratorInstance.id == instance_id
                )
            )
            instance = result.scalar_one_or_none()
            if instance:
                instance.plugin_settings = plugin_settings
                instance.config_hash = config_hash
                instance.updated_at = utc_now()
                instance.updated_by = caller_id
                await session.flush()
                return self._serialize(instance)
            return None

    async def update_config(
        self,
        instance_id,
        config: Dict[str, Any],
        caller_id: Optional[str] = None,
    ) -> Optional[OrchestratorInstance]:
        """Update instance configuration.

        Args:
            instance_id: Instance identifier (UUID or str)
            config: New configuration
            caller_id: User ID performing the operation

        Returns:
            Updated OrchestratorInstance or None
        """
        if isinstance(instance_id, str):
            instance_id = UUID(instance_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(OrchestratorInstance).where(
                    OrchestratorInstance.id == instance_id
                )
            )
            instance = result.scalar_one_or_none()

            if instance:
                instance.config = config
                instance.updated_at = utc_now()
                instance.updated_by = caller_id
                await session.flush()
            return instance

    async def update_status(
        self,
        instance_id,
        status: str,
        caller_id: Optional[str] = None,
    ) -> Optional[OrchestratorInstance]:
        """Update instance status.

        Args:
            instance_id: Instance identifier (UUID or str)
            status: New status
            caller_id: User ID performing the operation

        Returns:
            Updated OrchestratorInstance or None
        """
        if isinstance(instance_id, str):
            instance_id = UUID(instance_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(OrchestratorInstance).where(
                    OrchestratorInstance.id == instance_id
                )
            )
            instance = result.scalar_one_or_none()

            if instance:
                instance.status = status
                instance.updated_at = utc_now()
                instance.updated_by = caller_id
                await session.flush()
            return instance

    async def update_last_accessed(self, instance_id: UUID) -> bool:
        """Update last accessed timestamp (for LRU).

        Args:
            instance_id: Instance identifier

        Returns:
            True if updated, False if not found
        """
        if isinstance(instance_id, str):
            instance_id = UUID(instance_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(OrchestratorInstance).where(
                    OrchestratorInstance.id == instance_id
                )
            )
            instance = result.scalar_one_or_none()

            if instance:
                instance.last_accessed_at = utc_now()
                await session.flush()
                return True
            return False

    async def delete(self, instance_id: UUID) -> bool:
        """Delete orchestrator instance.

        Args:
            instance_id: Instance identifier

        Returns:
            True if deleted, False if not found
        """
        if isinstance(instance_id, str):
            instance_id = UUID(instance_id)
        async with self.client.session() as session:
            result = await session.execute(
                delete(OrchestratorInstance).where(
                    OrchestratorInstance.id == instance_id
                )
            )
            return result.rowcount > 0

    async def count_using_llm_config(self, org_id: str | UUID, config_name: str) -> int:
        """Count active instances in the org that reference an LLM config by name.

        Searches the config JSONB for references via primary_model.llm_config_name.
        Used to block deletion of an LLM config that is still in use.

        Args:
            org_id: Organization identifier
            config_name: LLM configuration name to search for

        Returns:
            Number of active (non-deleted, non-status-deleted) instances
            that reference this config
        """
        if isinstance(org_id, str):
            org_id = UUID(org_id)
        async with self.client.session() as session:
            result = await session.execute(
                select(func.count()).where(
                    OrchestratorInstance.org_id == org_id,
                    OrchestratorInstance.status != "is_deleted",
                    ~OrchestratorInstance.is_deleted,
                    OrchestratorInstance.config["primary_model"][
                        "llm_config_name"
                    ].astext
                    == config_name,
                )
            )
            return result.scalar() or 0
