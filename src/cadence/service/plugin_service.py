"""Plugin service for system and org plugin catalog management.

Handles upload, listing, schema extraction, and default settings building
for both system-wide and organization-specific plugins.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from cadence_sdk import Loggable

from cadence.repository.org_plugin_repository import OrgPluginRepository
from cadence.repository.system_plugin_repository import SystemPluginRepository
from cadence.service._plugin_helpers import (
    build_default_settings_lookup,
    build_plugin_names_lookup,
    extract_full_plugin_metadata,
    serialize_org_plugin,
    serialize_system_plugin,
    validate_plugin_id_matches_domain,
)

logger = logging.getLogger(__name__)


class PluginService(Loggable):
    """Service for managing the plugin catalog.

    Attributes:
        system_plugin_repo: SystemPluginRepository
        org_plugin_repo: OrgPluginRepository
        plugin_store: PluginStore (for S3 + local extraction)
    """

    def __init__(
        self,
        system_plugin_repo: SystemPluginRepository,
        org_plugin_repo: OrgPluginRepository,
        plugin_store: Optional[Any] = None,
    ):
        self.system_plugin_repo = system_plugin_repo
        self.org_plugin_repo = org_plugin_repo
        self.plugin_store = plugin_store

    async def get_latest_plugin_version(self, org_id: str, pid: str) -> Any:
        """Get the latest plugin version for a given org.

        Args:
            org_id: Organization identifier
            pid: Plugin identifier
        """
        latest_sys_plugin = self.system_plugin_repo.get_latest(pid)
        if latest_sys_plugin:
            return latest_sys_plugin.version
        latest_org_plugin = self.org_plugin_repo.get_latest(org_id, pid)
        if latest_org_plugin:
            return latest_org_plugin.version
        return None

    async def _upload_plugin_to_storage(
        self, pid: str, version: str, zip_bytes: bytes, org_id: Optional[str]
    ) -> str:
        """Upload plugin zip to object store and return the storage path."""
        if org_id is None:
            storage_path = f"plugins/system/{pid}/{version}/plugin.zip"
        else:
            storage_path = f"plugins/tenants/{org_id}/{pid}/{version}/plugin.zip"
        if self.plugin_store is not None:
            await self.plugin_store.upload(
                pid=pid, version=version, zip_bytes=zip_bytes, org_id=org_id
            )
        return storage_path

    async def upload_system_plugin(
        self, zip_bytes: bytes, caller_id: Optional[str] = None
    ) -> Any:
        """Upload a system plugin from a zip archive.

        Extracts metadata, uploads to S3 + local cache, writes to system_plugins.

        Args:
            zip_bytes: Raw zip archive bytes
            caller_id: User ID performing the upload

        Returns:
            Created SystemPlugin ORM instance
        """
        metadata = extract_full_plugin_metadata(zip_bytes)
        plugin_id = metadata["pid"]
        version = metadata["version"]

        storage_path = await self._upload_plugin_to_storage(
            plugin_id, version, zip_bytes, org_id=None
        )

        plugin = await self.system_plugin_repo.upload(
            pid=plugin_id,
            version=version,
            name=metadata["name"],
            description=metadata.get("description"),
            tag=metadata.get("tag"),
            s3_path=storage_path,
            default_settings=metadata.get("default_settings", {}),
            capabilities=metadata.get("capabilities", []),
            agent_type=metadata.get("agent_type", "specialized"),
            stateless=metadata.get("stateless", True),
            caller_id=caller_id,
        )

        self.logger.info(f"System plugin uploaded: {plugin_id} v{version}")
        return plugin

    async def upload_org_plugin(
        self,
        org_id: str,
        zip_bytes: bytes,
        caller_id: Optional[str] = None,
        org_domain: Optional[str] = None,
    ) -> Any:
        """Upload an org-specific plugin from a zip archive.

        The plugin pid must match the org's domain in reverse-domain notation
        (e.g. domain 'acme.com' → pid must start with 'com.acme').

        Args:
            org_id: Organization identifier
            zip_bytes: Raw zip archive bytes
            caller_id: User ID performing the upload
            org_domain: Organization domain used to validate the plugin pid

        Returns:
            Created OrgPlugin ORM instance

        Raises:
            ValueError: If the pid does not match the org domain
        """
        metadata = extract_full_plugin_metadata(zip_bytes)
        plugin_id = metadata["pid"]
        version = metadata["version"]

        if org_domain:
            validate_plugin_id_matches_domain(plugin_id, org_domain)

        storage_path = await self._upload_plugin_to_storage(
            plugin_id, version, zip_bytes, org_id=org_id
        )

        plugin = await self.org_plugin_repo.upload(
            org_id=org_id,
            pid=plugin_id,
            version=version,
            name=metadata["name"],
            description=metadata.get("description"),
            tag=metadata.get("tag"),
            s3_path=storage_path,
            default_settings=metadata.get("default_settings", {}),
            capabilities=metadata.get("capabilities", []),
            agent_type=metadata.get("agent_type", "specialized"),
            stateless=metadata.get("stateless", True),
            caller_id=caller_id,
        )

        self.logger.info(f"Org plugin uploaded: {org_id}/{plugin_id} v{version}")
        return plugin

    async def list_available(
        self, org_id: str, tag: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all plugins available to an org (system + org-specific).

        Args:
            org_id: Organization identifier
            tag: Optional tag filter

        Returns:
            Combined list of plugin dicts with source field
        """
        system_plugins = await self.system_plugin_repo.list_all(tag=tag)
        org_plugins = await self.org_plugin_repo.list_available(org_id, tag=tag)

        available_plugins = []
        for plugin in system_plugins:
            available_plugins.append(serialize_system_plugin(plugin))
        for plugin in org_plugins:
            available_plugins.append(serialize_org_plugin(plugin))

        return available_plugins

    @staticmethod
    def get_settings_schema(
        pid: str, org_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get settings schema for a plugin by pid.

        Looks up the plugin class from the SDK registry and extracts the schema.

        Args:
            pid: Plugin identifier
            org_id: Optional org for context

        Returns:
            List of setting definition dicts
        """
        from cadence_sdk.decorators.settings_decorators import (
            get_plugin_settings_schema as sdk_get_schema,
        )
        from cadence_sdk.registry.plugin_registry import PluginRegistry

        registry = PluginRegistry.instance()
        contract = registry.get_plugin(pid)
        if not contract:
            return []

        schema_definitions = sdk_get_schema(contract.plugin_class)
        return [
            {
                "key": schema_field["key"],
                "name": schema_field.get("name", schema_field["key"]),
                "type": schema_field["type"],
                "default": schema_field.get("default"),
                "description": schema_field.get("description", ""),
                "required": schema_field.get("required", False),
                "sensitive": schema_field.get("sensitive", False),
            }
            for schema_field in schema_definitions
        ]

    async def resolve_plugin_rows(
        self, active_plugins: List[str], org_id: str
    ) -> tuple[List, List]:
        """Fetch system and org plugin catalog rows for the given plugin refs.

        Args:
            active_plugins: List of 'pid' or 'pid@version' strings
            org_id: Organization identifier

        Returns:
            Tuple of (system_rows, org_rows)
        """
        plugin_ids = [
            ref.split("@")[0] if "@" in ref else ref for ref in active_plugins
        ]
        system_rows = []
        org_rows = []
        for plugin_id in plugin_ids:
            sys_row = await self.system_plugin_repo.get_latest(plugin_id)
            if sys_row:
                system_rows.append(sys_row)
            org_row = await self.org_plugin_repo.get_latest(org_id, plugin_id)
            if org_row:
                org_rows.append(org_row)
        return system_rows, org_rows

    @staticmethod
    def merge_plugin_settings(
        existing: Optional[Dict[str, Any]],
        overrides: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Merge plugin setting overrides into existing settings.

        Args:
            existing: Current plugin settings dict (pid@version -> {id, version, name, active, settings: [{key, value}]})
            overrides: Override settings to merge in (same key format)

        Returns:
            Merged settings dict
        """
        merged = dict(existing or {})
        for spec_key, spec_entry in overrides.items():
            if spec_key in merged:
                existing_settings = {
                    setting["key"]: setting
                    for setting in merged[spec_key].get("settings", [])
                }
                for setting in spec_entry.get("settings", []):
                    existing_settings[setting["key"]] = setting
                merged[spec_key] = {
                    **merged[spec_key],
                    **{k: v for k, v in spec_entry.items() if k != "settings"},
                    "settings": list(existing_settings.values()),
                }
            else:
                merged[spec_key] = spec_entry
        return merged

    async def get_schema_for_version(self, pid: str, version: str) -> Dict[str, Any]:
        """Get default settings schema for a specific plugin version.

        Args:
            pid: Plugin identifier
            version: Plugin version string

        Returns:
            Dict of {key: default_value} for all settings in that version
        """
        sys_row = await self.system_plugin_repo.get_by_version(pid, version)
        if sys_row:
            return dict(sys_row.default_settings or {})
        return {}

    async def delete_org_plugin(
        self, org_id: str, plugin_id: str, caller_id: str
    ) -> bool:
        """Soft-delete an org plugin.

        Args:
            org_id: Organization identifier
            plugin_id: Plugin database ID
            caller_id: User ID performing the operation

        Returns:
            True if deleted, False if not found
        """
        return await self.org_plugin_repo.soft_delete(
            plugin_id=UUID(plugin_id),
            org_id=org_id,
            caller_id=caller_id,
        )

    @staticmethod
    def build_initial_plugin_settings(
        active_plugins: List[str],
        system_repo_rows: List[Any],
        org_repo_rows: List[Any],
    ) -> Dict[str, Any]:
        """Build initial plugin_settings from catalog default_settings.

        Args:
            active_plugins: List of 'pid@version' strings
            system_repo_rows: SystemPlugin ORM rows
            org_repo_rows: OrgPlugin ORM rows

        Returns:
            Dict mapping 'pid@version' -> {id, version, name, active, settings} entries
        """
        plugin_defaults = build_default_settings_lookup(system_repo_rows, org_repo_rows)
        plugin_names = build_plugin_names_lookup(system_repo_rows, org_repo_rows)

        initial_settings: Dict[str, Any] = {}
        for plugin_ref in active_plugins:
            if "@" in plugin_ref:
                plugin_id, version = plugin_ref.split("@", 1)
            else:
                plugin_id, version = plugin_ref, ""
            settings_key = f"{plugin_id}@{version}" if version else plugin_id
            per_plugin_defaults = plugin_defaults.get(plugin_id, {})
            initial_settings[settings_key] = {
                "id": plugin_id,
                "version": version,
                "name": plugin_names.get(plugin_id, plugin_id),
                "active": True,
                "settings": [
                    {"key": k, "value": v} for k, v in per_plugin_defaults.items()
                ],
            }

        return initial_settings
