"""Plugin service for system and org plugin catalog management.

Handles upload, listing, schema extraction, and default settings building
for both system-wide and organization-specific plugins.
"""

import importlib.util
import io
import logging
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from cadence.repository.org_plugin_repository import OrgPluginRepository
from cadence.repository.system_plugin_repository import SystemPluginRepository

logger = logging.getLogger(__name__)


class PluginService:
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
        metadata = _extract_full_plugin_metadata(zip_bytes)
        pid = metadata["pid"]
        version = metadata["version"]

        s3_path = f"plugins/system/{pid}/{version}/plugin.zip"

        if self.plugin_store is not None:
            await self.plugin_store.upload(
                pid=pid,
                version=version,
                zip_bytes=zip_bytes,
                org_id=None,
            )

        plugin = await self.system_plugin_repo.upload(
            pid=pid,
            version=version,
            name=metadata["name"],
            description=metadata.get("description"),
            tag=metadata.get("tag"),
            s3_path=s3_path,
            default_settings=metadata.get("default_settings", {}),
            capabilities=metadata.get("capabilities", []),
            agent_type=metadata.get("agent_type", "specialized"),
            stateless=metadata.get("stateless", True),
            caller_id=caller_id,
        )

        logger.info(f"System plugin uploaded: {pid} v{version}")
        return plugin

    async def upload_org_plugin(
        self,
        org_id: str,
        zip_bytes: bytes,
        caller_id: Optional[str] = None,
    ) -> Any:
        """Upload an org-specific plugin from a zip archive.

        Args:
            org_id: Organization identifier
            zip_bytes: Raw zip archive bytes
            caller_id: User ID performing the upload

        Returns:
            Created OrgPlugin ORM instance
        """
        metadata = _extract_full_plugin_metadata(zip_bytes)
        pid = metadata["pid"]
        version = metadata["version"]

        s3_path = f"plugins/tenants/{org_id}/{pid}/{version}/plugin.zip"

        if self.plugin_store is not None:
            await self.plugin_store.upload(
                pid=pid,
                version=version,
                zip_bytes=zip_bytes,
                org_id=org_id,
            )

        plugin = await self.org_plugin_repo.upload(
            org_id=org_id,
            pid=pid,
            version=version,
            name=metadata["name"],
            description=metadata.get("description"),
            tag=metadata.get("tag"),
            s3_path=s3_path,
            default_settings=metadata.get("default_settings", {}),
            capabilities=metadata.get("capabilities", []),
            agent_type=metadata.get("agent_type", "specialized"),
            stateless=metadata.get("stateless", True),
            caller_id=caller_id,
        )

        logger.info(f"Org plugin uploaded: {org_id}/{pid} v{version}")
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

        result = []
        for p in system_plugins:
            result.append(_system_plugin_to_dict(p))
        for p in org_plugins:
            result.append(_org_plugin_to_dict(p))

        return result

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

        raw = sdk_get_schema(contract.plugin_class)
        return [
            {
                "key": s["key"],
                "name": s.get("name", s["key"]),
                "type": s["type"],
                "default": s.get("default"),
                "description": s.get("description", ""),
                "required": s.get("required", False),
                "sensitive": s.get("sensitive", False),
            }
            for s in raw
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
        pids = [ref.split("@")[0] if "@" in ref else ref for ref in active_plugins]
        system_rows = []
        org_rows = []
        for pid in pids:
            sys_row = await self.system_plugin_repo.get_latest(pid)
            if sys_row:
                system_rows.append(sys_row)
            org_row = await self.org_plugin_repo.get_latest(org_id, pid)
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
                    s["key"]: s for s in merged[spec_key].get("settings", [])
                }
                for s in spec_entry.get("settings", []):
                    existing_settings[s["key"]] = s
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
            plugin_id=plugin_id,
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
        defaults = _build_default_settings_lookup(system_repo_rows, org_repo_rows)
        names = _build_plugin_names_lookup(system_repo_rows, org_repo_rows)

        result: Dict[str, Any] = {}
        for plugin_ref in active_plugins:
            if "@" in plugin_ref:
                pid, version = plugin_ref.split("@", 1)
            else:
                pid, version = plugin_ref, ""
            key = f"{pid}@{version}" if version else pid
            pid_defaults = defaults.get(pid, {})
            result[key] = {
                "id": pid,
                "version": version,
                "name": names.get(pid, pid),
                "active": True,
                "settings": [{"key": k, "value": v} for k, v in pid_defaults.items()],
            }

        return result


def _build_default_settings_lookup(
    system_repo_rows: List[Any], org_repo_rows: List[Any]
) -> Dict[str, Dict[str, Any]]:
    """Build pid -> default_settings lookup; org overrides system."""
    defaults: Dict[str, Dict[str, Any]] = {}
    for row in system_repo_rows:
        defaults[row.pid] = dict(row.default_settings or {})
    for row in org_repo_rows:
        defaults[row.pid] = dict(row.default_settings or {})
    return defaults


def _build_plugin_names_lookup(
    system_repo_rows: List[Any], org_repo_rows: List[Any]
) -> Dict[str, str]:
    """Build pid -> name lookup; org overrides system."""
    names: Dict[str, str] = {}
    for row in system_repo_rows:
        names[row.pid] = row.name
    for row in org_repo_rows:
        names[row.pid] = row.name
    return names


def _extract_default_settings_from_schema(
    plugin_class: Any, pid: str
) -> Dict[str, Any]:
    """Extract default_settings from SDK plugin_settings decorator."""
    default_settings: Dict[str, Any] = {}
    try:
        from cadence_sdk.decorators.settings_decorators import (
            get_plugin_settings_schema as sdk_get_schema,
        )

        schema = sdk_get_schema(plugin_class)
        for field in schema:
            key = field.get("key")
            if key:
                default_settings[key] = field.get("default")
    except Exception as e:
        logger.warning(f"Could not extract default_settings for {pid}: {e}")
    return default_settings


def _extract_full_plugin_metadata(zip_bytes: bytes) -> Dict[str, Any]:
    """Extract full plugin metadata from a zip archive.

    Loads plugin.py, instantiates the BasePlugin subclass, extracts
    metadata and default_settings via the SDK.

    Args:
        zip_bytes: Raw zip archive bytes

    Returns:
        Dict with pid, version, name, description, capabilities,
        agent_type, stateless, default_settings, tag

    Raises:
        ValueError: If zip is invalid or metadata cannot be extracted
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as e:
        raise ValueError(f"Invalid zip archive: {e}") from e

    plugin_entries = [n for n in zf.namelist() if n.endswith("plugin.py")]
    if not plugin_entries:
        raise ValueError("No plugin.py found in zip archive")

    plugin_entry = plugin_entries[0]

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        zf.extractall(tmp_path)
        zf.close()

        plugin_file = tmp_path / plugin_entry
        module_name = "_cadence_upload_inspect"

        spec = importlib.util.spec_from_file_location(module_name, plugin_file)
        if spec is None or spec.loader is None:
            raise ValueError("Cannot load plugin.py from zip")

        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(plugin_file.parent))
        try:
            spec.loader.exec_module(module)
        finally:
            sys.path.remove(str(plugin_file.parent))

        from cadence_sdk.base import BasePlugin

        plugin_class = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BasePlugin)
                and attr is not BasePlugin
            ):
                plugin_class = attr
                break

        if plugin_class is None:
            raise ValueError("No BasePlugin subclass found in plugin.py")

        meta = plugin_class.get_metadata()
        default_settings = _extract_default_settings_from_schema(plugin_class, meta.pid)

        return {
            "pid": meta.pid,
            "version": meta.version,
            "name": meta.name,
            "description": getattr(meta, "description", None),
            "capabilities": list(meta.capabilities or []),
            "agent_type": getattr(meta, "agent_type", "specialized"),
            "stateless": getattr(meta, "stateless", True),
            "default_settings": default_settings,
            "tag": getattr(meta, "tag", None),
        }


def _system_plugin_to_dict(plugin: Any) -> Dict[str, Any]:
    """Convert SystemPlugin ORM object to API response dict."""
    return {
        "id": str(plugin.id),
        "pid": plugin.pid,
        "version": plugin.version,
        "name": plugin.name,
        "description": plugin.description or "",
        "tag": plugin.tag,
        "is_latest": plugin.is_latest,
        "s3_path": plugin.s3_path,
        "default_settings": plugin.default_settings or {},
        "capabilities": plugin.capabilities or [],
        "agent_type": plugin.agent_type,
        "stateless": plugin.stateless,
        "source": "system",
    }


def _org_plugin_to_dict(plugin: Any) -> Dict[str, Any]:
    """Convert OrgPlugin ORM object to API response dict."""
    return {
        "id": str(plugin.id),
        "pid": plugin.pid,
        "version": plugin.version,
        "name": plugin.name,
        "description": plugin.description or "",
        "tag": plugin.tag,
        "is_latest": plugin.is_latest,
        "s3_path": plugin.s3_path,
        "default_settings": plugin.default_settings or {},
        "capabilities": plugin.capabilities or [],
        "agent_type": plugin.agent_type,
        "stateless": plugin.stateless,
        "source": "org",
    }
