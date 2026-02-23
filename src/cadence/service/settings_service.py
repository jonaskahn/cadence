"""Settings service for managing configuration across all tiers.

This module provides settings management for Global settings, Organization
settings, and Instance config, with hot-reload support for instance updates.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

from cadence.constants import SettingValue
from cadence.repository.global_settings_repository import GlobalSettingsRepository
from cadence.repository.orchestrator_instance_repository import (
    OrchestratorInstanceRepository,
)
from cadence.repository.organization_settings_repository import (
    OrganizationSettingsRepository,
)
from cadence.service.orchestrator_config_service import OrchestratorConfigMixin

if TYPE_CHECKING:
    from cadence.engine.pool import OrchestratorPool

logger = logging.getLogger(__name__)


class SettingsService(OrchestratorConfigMixin):
    """Service for managing settings across all tiers.

    Attributes:
        global_settings_repo: Global settings repository (Tier 2)
        org_settings_repo: Organization settings repository (Tier 3)
        instance_repo: Orchestrator instance repository (Instance config)
        pool: Orchestrator pool (for triggering reloads)
    """

    def __init__(
        self,
        global_settings_repo: GlobalSettingsRepository,
        org_settings_repo: OrganizationSettingsRepository,
        instance_repo: OrchestratorInstanceRepository,
        pool: OrchestratorPool | None = None,
    ):
        self.global_settings_repo = global_settings_repo
        self.org_settings_repo = org_settings_repo
        self.instance_repo = instance_repo
        self.pool = pool

    async def get_global_setting(self, key: str) -> SettingValue:
        """Get global setting value (Tier 2).

        Args:
            key: Setting key

        Returns:
            Setting value or None if not found
        """
        setting = await self.global_settings_repo.get_by_key(key)
        return setting.value if setting else None

    async def set_global_setting(
        self,
        key: str,
        value: SettingValue,
        description: Optional[str] = None,
    ) -> None:
        """Set global setting (Tier 2).

        Args:
            key: Setting key
            value: Setting value
            description: Optional description
        """
        logger.info(f"Setting global setting: {key}")
        await self.global_settings_repo.upsert(
            key=key, value=value, description=description
        )

    async def list_global_settings(self) -> list:
        """List all global settings (Tier 2).

        Returns:
            List of setting dictionaries
        """
        settings = await self.global_settings_repo.get_all()
        return [
            {
                "key": s.key,
                "value": s.value,
                "value_type": s.value_type,
                "description": s.description or "",
            }
            for s in settings
        ]

    async def update_global_setting(
        self, key: str, value: SettingValue
    ) -> Optional[dict[str, Any]]:
        """Update existing global setting (Tier 2).

        Args:
            key: Setting key
            value: New setting value

        Returns:
            Updated setting or None if not found
        """
        existing = await self.global_settings_repo.get_by_key(key)
        if not existing:
            return None
        await self.set_global_setting(key, value, existing.description)
        return await self.global_settings_repo.get_by_key(key)

    async def delete_global_setting(self, key: str) -> None:
        """Delete global setting (Tier 2).

        Args:
            key: Setting key
        """
        logger.info(f"Deleting global setting: {key}")
        await self.global_settings_repo.delete(key)

    async def get_tenant_setting(self, org_id: str, key: str) -> SettingValue:
        """Get tenant setting value (Tier 3).

        Args:
            org_id: Organization ID
            key: Setting key

        Returns:
            Setting value or None if not found
        """
        setting = await self.org_settings_repo.get_by_key(org_id, key)
        return setting.value if setting else None

    async def set_tenant_setting(
        self, org_id: str, key: str, value: SettingValue
    ) -> None:
        """Set tenant setting (Tier 3).

        Args:
            org_id: Organization ID
            key: Setting key
            value: Setting value
        """
        logger.info(f"Setting tenant setting: {org_id}/{key}")
        await self.org_settings_repo.upsert(org_id=org_id, key=key, value=value)

    async def list_tenant_settings(self, org_id: str) -> dict[str, Any]:
        """List all tenant settings (Tier 3).

        Args:
            org_id: Organization ID

        Returns:
            Dict mapping setting keys to values
        """
        settings = await self.org_settings_repo.get_all_for_org(org_id)
        return {s.key: s.value for s in settings}

    async def delete_tenant_setting(self, org_id: str, key: str) -> None:
        """Delete tenant setting (Tier 3).

        Args:
            org_id: Organization ID
            key: Setting key
        """
        logger.info(f"Deleting tenant setting: {org_id}/{key}")
        await self.org_settings_repo.delete(org_id, key)

    async def create_instance(
        self,
        org_id: str,
        framework_type: str,
        mode: str,
        instance_config: dict[str, Any],
        tier: str = "cold",
        plugin_settings: Optional[dict[str, Any]] = None,
        config_hash: Optional[str] = None,
        caller_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create new orchestrator instance.

        Args:
            org_id: Organization ID
            framework_type: Orchestration framework (immutable after creation)
            mode: Orchestration mode (immutable after creation)
            instance_config: Mutable instance configuration
            tier: Pool tier (hot/warm/cold)
            plugin_settings: Per-plugin default settings
            config_hash: SHA-256 hash of config+plugin_settings
            caller_id: User ID performing the operation

        Returns:
            Created instance data
        """
        logger.info(
            f"Creating instance for org {org_id} with framework={framework_type} mode={mode} tier={tier}"
        )

        clean_config = {
            k: v
            for k, v in instance_config.items()
            if k not in ("framework_type", "mode", "instance_id", "org_id", "status")
        }

        return await self.instance_repo.create(
            org_id=org_id,
            name=instance_config.get("name", ""),
            framework_type=framework_type,
            mode=mode,
            config=clean_config,
            tier=tier,
            plugin_settings=plugin_settings or {},
            config_hash=config_hash,
            caller_id=caller_id,
        )

    async def list_instances_for_org(self, org_id: str) -> list:
        """List all instances for organization.

        Args:
            org_id: Organization ID

        Returns:
            List of instance dictionaries
        """
        return await self.instance_repo.list_for_org(org_id)

    async def get_instance_config(self, instance_id: str) -> Optional[dict[str, Any]]:
        """Get instance configuration.

        Args:
            instance_id: Instance ID

        Returns:
            Instance data or None if not found
        """
        return await self.instance_repo.get_by_id(instance_id)

    async def delete_instance(self, instance_id: str) -> None:
        """Soft-delete orchestrator instance (sets status to 'deleted').

        Args:
            instance_id: Instance ID
        """
        logger.info(f"Soft-deleting instance: {instance_id}")
        await self.update_instance_status(instance_id, "is_deleted")

    async def update_instance_status(
        self,
        instance_id: str,
        status: str,
        caller_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Update instance status (active, suspended, deleted).

        Args:
            instance_id: Instance ID
            status: New status
            caller_id: User ID performing the operation

        Returns:
            Updated instance data
        """
        logger.info(f"Updating instance {instance_id} status to {status}")

        if status == "is_deleted" and self.pool:
            try:
                await self.pool.remove_instance(instance_id)
            except Exception:
                pass

        await self.instance_repo.update_status(instance_id, status, caller_id=caller_id)
        return await self.instance_repo.get_by_id(instance_id)

    async def update_instance_config(
        self,
        instance_id: str,
        new_config: dict[str, Any],
        trigger_reload: bool = True,
        caller_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Update instance configuration.

        framework_type and mode are immutable and cannot be changed via this method.
        Triggers orchestrator reload if pool is available.

        Args:
            instance_id: Instance ID
            new_config: New configuration
            trigger_reload: Whether to trigger pool reload (default: True)
            caller_id: User ID performing the operation

        Returns:
            Updated instance data

        Raises:
            ValueError: If new_config contains immutable fields (framework_type, mode)
        """
        immutable = {"framework_type", "mode"} & new_config.keys()
        if immutable:
            raise ValueError(f"Cannot modify immutable fields: {sorted(immutable)}")

        logger.info(f"Updating instance config: {instance_id}")

        await self.instance_repo.update_config(
            instance_id, new_config, caller_id=caller_id
        )

        if trigger_reload and self.pool:
            instance = await self.instance_repo.get_by_id(instance_id)

            if instance:
                resolved_config = {**instance["config"], "org_id": instance["org_id"]}

                await self.pool.reload_instance(
                    instance_id=instance_id,
                    org_id=instance["org_id"],
                    framework_type=instance["framework_type"],
                    mode=instance["mode"],
                    instance_config=instance["config"],
                    resolved_config=resolved_config,
                )

        return await self.instance_repo.get_by_id(instance_id)

    async def update_instance_plugin_settings(
        self,
        instance_id: str,
        plugin_settings: dict[str, Any],
        config_hash: str,
        caller_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Update plugin_settings and config_hash on an instance.

        Args:
            instance_id: Instance identifier
            plugin_settings: New plugin settings dict
            config_hash: New config hash
            caller_id: User ID performing the operation

        Returns:
            Updated instance dict
        """
        return await self.instance_repo.update_plugin_settings(
            instance_id=instance_id,
            plugin_settings=plugin_settings,
            config_hash=config_hash,
            caller_id=caller_id,
        )
