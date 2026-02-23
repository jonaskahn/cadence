"""Orchestrator configuration management mixin.

Provides orchestrator config creation, update, and sync methods that build on
top of the base SettingsService CRUD operations.
"""

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class OrchestratorConfigMixin(ABC):
    """Mixin that adds orchestrator-specific config management to SettingsService.

    Requires self.instance_repo to be set by the inheriting class.
    """

    @staticmethod
    def compute_config_hash(
        config: Dict[str, Any], plugin_settings: Dict[str, Any]
    ) -> str:
        """Compute SHA-256[:16] hash of config + plugin_settings.

        Args:
            config: Instance mutable configuration
            plugin_settings: Per-plugin settings dict

        Returns:
            16-character hex hash string
        """
        payload = json.dumps(
            {"config": config, "plugin_settings": plugin_settings},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    async def create_orchestrator_instance(
        self,
        org_id: str,
        framework_type: str,
        mode: str,
        active_plugin_ids: List[str],
        tier: str,
        name: str,
        extra_config: Optional[Dict[str, Any]],
        plugin_service: Any,
        caller_id: Optional[str] = None,
        event_publisher: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Create an orchestrator instance with plugin settings and optional load event.

        Args:
            org_id: Organization identifier
            framework_type: Orchestration framework (immutable)
            mode: Orchestration mode (immutable)
            active_plugin_ids: List of plugin UUID strings
            tier: Pool tier (hot/warm/cold)
            name: Instance name
            extra_config: Additional mutable config fields
            plugin_service: PluginService instance for resolving plugin rows
            caller_id: User ID performing the operation
            event_publisher: Optional event publisher for hot-tier load events

        Returns:
            Created instance dict
        """
        all_plugins = await plugin_service.list_available(org_id)
        active_plugins = [
            f"{plugin['pid']}@{plugin['version']}"
            for plugin in all_plugins
            if plugin["id"] in active_plugin_ids
        ]

        mutable_config = {
            "name": name,
            "active_plugins": active_plugins,
            **(extra_config or {}),
        }
        mutable_config.pop("framework_type", None)
        mutable_config.pop("mode", None)

        system_rows, org_rows = await plugin_service.resolve_plugin_rows(
            active_plugins, org_id
        )
        plugin_settings = plugin_service.build_initial_plugin_settings(
            active_plugins=active_plugins,
            system_repo_rows=system_rows,
            org_repo_rows=org_rows,
        )

        config_hash = self.compute_config_hash(mutable_config, plugin_settings)

        created_instance = await self.create_instance(
            org_id=org_id,
            framework_type=framework_type,
            mode=mode,
            instance_config=mutable_config,
            tier=tier,
            plugin_settings=plugin_settings,
            config_hash=config_hash,
            caller_id=caller_id,
        )

        if tier == "hot" and event_publisher:
            try:
                await event_publisher.publish_load(
                    instance_id=created_instance["instance_id"],
                    org_id=org_id,
                    tier="hot",
                )
            except Exception as exc:
                logger.warning(f"Failed to publish load event: {exc}")

        return created_instance

    async def update_orchestrator_config(
        self,
        instance_id: str,
        org_id: str,
        new_config: dict[str, Any],
        caller_id: Optional[str] = None,
        event_publisher: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Update orchestrator config, recompute hash, and publish reload event.

        Args:
            instance_id: Instance identifier
            org_id: Expected organization owner (access control)
            new_config: Full new mutable configuration
            caller_id: User ID performing the operation
            event_publisher: Optional event publisher for reload events

        Returns:
            Updated instance dict

        Raises:
            ValueError: If instance not found, deleted, wrong org, or immutable fields present
        """
        instance = await self.get_instance_config(instance_id)
        if not instance:
            raise ValueError(f"Instance {instance_id} not found")
        if instance.get("status") == "is_deleted":
            raise ValueError(f"Instance {instance_id} has been deleted")
        if instance.get("org_id") != org_id:
            raise ValueError("Access denied to this instance")

        updated_instance = await self.update_instance_config(
            instance_id=instance_id,
            new_config=new_config,
            trigger_reload=False,
            caller_id=caller_id,
        )

        plugin_settings = updated_instance.get("plugin_settings", {})
        new_hash = self.compute_config_hash(new_config, plugin_settings)

        updated_instance = await self.update_instance_plugin_settings(
            instance_id=instance_id,
            plugin_settings=plugin_settings,
            config_hash=new_hash,
            caller_id=caller_id,
        )

        if event_publisher:
            try:
                await event_publisher.publish_reload(
                    instance_id=instance_id,
                    org_id=org_id,
                    config_hash=new_hash,
                )
            except Exception as exc:
                logger.warning(f"Failed to publish reload event: {exc}")

        return updated_instance

    async def update_orchestrator_plugin_settings(
        self,
        instance_id: str,
        org_id: str,
        plugin_settings_override: dict[str, Any],
        caller_id: Optional[str] = None,
        event_publisher: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Merge plugin setting overrides, recompute hash, and publish reload if hot.

        Args:
            instance_id: Instance identifier
            org_id: Expected organization owner (access control)
            plugin_settings_override: Map of pid -> {key: value} to merge
            caller_id: User ID performing the operation
            event_publisher: Optional event publisher for reload events

        Returns:
            Updated instance dict

        Raises:
            ValueError: If instance not found or access denied
        """
        instance = await self.get_instance_config(instance_id)
        if not instance:
            raise ValueError(f"Instance {instance_id} not found")
        if instance.get("org_id") != org_id:
            raise ValueError("Access denied to this instance")

        from cadence.service.plugin_service import PluginService

        fresh_settings = PluginService.merge_plugin_settings(
            instance.get("plugin_settings"), plugin_settings_override
        )

        updated = await self._internal_update_instance_plugin_settings(
            caller_id, event_publisher, fresh_settings, instance, instance_id, org_id
        )

        return updated

    async def activate_plugin_version(
        self,
        instance_id: str,
        org_id: str,
        pid: str,
        version: str,
        plugin_service: Any,
        caller_id: Optional[str] = None,
        event_publisher: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Activate a specific plugin version, auto-migrating settings if needed.

        If pid@version entry does not exist, settings are migrated from the
        currently active version: matching keys are copied, new keys set to
        their catalog default, removed keys are omitted.

        Args:
            instance_id: Instance identifier
            org_id: Expected organization owner (access control)
            pid: Plugin identifier
            version: Target plugin version to activate
            plugin_service: PluginService for schema lookup
            caller_id: User ID performing the operation
            event_publisher: Optional event publisher for reload events

        Returns:
            Updated instance dict

        Raises:
            ValueError: If instance not found, access denied, or plugin not active
        """
        instance = await self.get_instance_config(instance_id)
        if not instance:
            raise ValueError(f"Instance {instance_id} not found")
        if instance.get("org_id") != org_id:
            raise ValueError("Access denied to this instance")

        current_settings: Dict[str, Any] = dict(instance.get("plugin_settings") or {})
        target_key = f"{pid}@{version}"

        if target_key not in current_settings:
            old_entry = next(
                (
                    e
                    for e in current_settings.values()
                    if e.get("id") == pid and e.get("active")
                ),
                None,
            )
            new_schema = await plugin_service.get_schema_for_version(pid, version)
            old_values: Dict[str, Any] = {}
            if old_entry:
                old_values = {
                    s["key"]: s["value"]
                    for s in old_entry.get("settings", [])
                    if "key" in s
                }

            new_settings_list = [
                {"key": k, "value": old_values.get(k, v)} for k, v in new_schema.items()
            ]
            entry_name = old_entry["name"] if old_entry else pid
            current_settings[target_key] = {
                "id": pid,
                "version": version,
                "name": entry_name,
                "active": False,
                "settings": new_settings_list,
            }

        for key, entry in current_settings.items():
            if entry.get("id") == pid:
                entry["active"] = False
        current_settings[target_key]["active"] = True

        current_config = instance.get("config", {})
        active_plugins: List[str] = list(current_config.get("active_plugins", []))
        active_plugins = [
            ref for ref in active_plugins if not ref.startswith(f"{pid}@")
        ]
        active_plugins.append(target_key)
        new_config = {**current_config, "active_plugins": active_plugins}

        updated = await self.update_instance_config(
            instance_id=instance_id,
            new_config=new_config,
            trigger_reload=False,
            caller_id=caller_id,
        )
        new_hash = self.compute_config_hash(new_config, current_settings)

        updated = await self.update_instance_plugin_settings(
            instance_id=instance_id,
            plugin_settings=current_settings,
            config_hash=new_hash,
            caller_id=caller_id,
        )

        if event_publisher and instance.get("tier") == "hot":
            try:
                await event_publisher.publish_reload(
                    instance_id=instance_id,
                    org_id=org_id,
                    config_hash=new_hash,
                )
            except Exception as exc:
                logger.warning(f"Failed to publish reload event: {exc}")

        return updated

    async def sync_orchestrator_plugin_settings(
        self,
        instance_id: str,
        org_id: str,
        plugin_service: Any,
        caller_id: Optional[str] = None,
        event_publisher: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Add missing catalog keys to active plugin entries without overwriting user values.

        Preserves all existing user-customized values. Only adds keys from
        the catalog that are missing in the current active entry. Non-active
        version entries are left untouched.

        Args:
            instance_id: Instance identifier
            org_id: Expected organization owner (access control)
            plugin_service: PluginService instance for resolving plugin rows
            caller_id: User ID performing the operation
            event_publisher: Optional event publisher for reload events

        Returns:
            Updated instance dict

        Raises:
            ValueError: If instance not found or access denied
        """
        instance = await self.get_instance_config(instance_id)
        if not instance:
            raise ValueError(f"Instance {instance_id} not found")
        if instance.get("org_id") != org_id:
            raise ValueError("Access denied to this instance")

        current_settings: Dict[str, Any] = dict(instance.get("plugin_settings") or {})
        active_plugins = instance.get("config", {}).get("active_plugins", [])
        system_rows, org_rows = await plugin_service.resolve_plugin_rows(
            active_plugins, org_id
        )
        catalog_defaults = _build_default_settings_lookup_from_rows(
            system_rows, org_rows
        )

        for ref in active_plugins:
            if "@" in ref:
                pid, version = ref.split("@", 1)
            else:
                pid, version = ref, ""
            key = f"{pid}@{version}" if version else pid
            entry = current_settings.get(key)
            if not entry:
                continue
            existing_keys = {s["key"] for s in entry.get("settings", []) if "key" in s}
            pid_defaults = catalog_defaults.get(pid, {})
            for k, v in pid_defaults.items():
                if k not in existing_keys:
                    entry.setdefault("settings", []).append({"key": k, "value": v})

        updated = await self._internal_update_instance_plugin_settings(
            caller_id, event_publisher, current_settings, instance, instance_id, org_id
        )

        logger.info(f"Plugin settings synced for {instance_id}")
        return updated

    async def _internal_update_instance_plugin_settings(
        self,
        caller_id: str | None,
        event_publisher: Any | None,
        fresh_settings,
        instance,
        instance_id: str,
        org_id: str,
    ) -> Any:
        new_hash = self.compute_config_hash(instance["config"], fresh_settings)

        updated = await self.update_instance_plugin_settings(
            instance_id=instance_id,
            plugin_settings=fresh_settings,
            config_hash=new_hash,
            caller_id=caller_id,
        )

        if event_publisher and instance.get("tier") == "hot":
            try:
                await event_publisher.publish_reload(
                    instance_id=instance_id,
                    org_id=org_id,
                    config_hash=new_hash,
                )
            except Exception as exc:
                logger.warning(f"Failed to publish reload event: {exc}")
        return updated

    @abstractmethod
    async def get_instance_config(self, instance_id):
        pass

    @abstractmethod
    async def update_instance_config(
        self, instance_id, new_config, trigger_reload, caller_id
    ):
        pass

    @abstractmethod
    async def update_instance_plugin_settings(
        self, instance_id, plugin_settings, config_hash, caller_id
    ):
        pass

    @abstractmethod
    async def create_instance(
        self,
        org_id,
        framework_type,
        mode,
        instance_config,
        tier,
        plugin_settings,
        config_hash,
        caller_id,
    ):
        pass


def _build_default_settings_lookup_from_rows(
    system_rows: List[Any], org_rows: List[Any]
) -> Dict[str, Dict[str, Any]]:
    """Build pid -> default_settings lookup from repo rows; org overrides system."""
    defaults: Dict[str, Dict[str, Any]] = {}
    for row in system_rows:
        defaults[row.pid] = dict(row.default_settings or {})
    for row in org_rows:
        defaults[row.pid] = dict(row.default_settings or {})
    return defaults
