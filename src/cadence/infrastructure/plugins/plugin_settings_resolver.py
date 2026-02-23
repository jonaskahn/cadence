"""Plugin settings resolution.

This module resolves plugin configuration by merging schema defaults with
instance-specific overrides keyed by plugin pid.
"""

from typing import Any, Dict, List

from cadence_sdk.base.agent import BaseAgent


class PluginSettingsResolver:
    """Resolver for plugin configuration settings.

    Merges declared settings schema (from @plugin_settings decorator or
    get_settings_schema method) with instance configuration overrides.
    Overrides are looked up by plugin pid in the instance config.

    Attributes:
        instance_config: Instance-specific configuration
    """

    def __init__(self, instance_config: Dict[str, Any]):
        """Initialize settings resolver.

        Args:
            instance_config: Instance configuration dictionary
        """
        self.instance_config = instance_config

    def resolve(
        self, plugin_pid: str, version: str, agent: BaseAgent
    ) -> Dict[str, Any]:
        """Resolve settings for a plugin.

        Resolution order:
        1. Load schema defaults from agent.get_settings_schema()
        2. Override with instance_config.plugin_settings.{plugin_pid@version}
        3. Validate required fields

        Args:
            plugin_pid: Reverse-domain plugin identifier (e.g., "com.example.search")
            version: Plugin version string (e.g., "1.0.0")
            agent: Plugin agent instance

        Returns:
            Resolved settings dictionary

        Raises:
            ValueError: If required settings are missing
        """
        settings_schema = self._get_schema(agent)
        defaults = self._extract_defaults(settings_schema)
        overrides = self._get_overrides(plugin_pid, version)

        resolved = {**defaults, **overrides}
        self._validate_required(plugin_pid, settings_schema, resolved)

        return resolved

    @staticmethod
    def _get_schema(agent: BaseAgent) -> List[Dict[str, Any]]:
        """Extract settings schema from agent.

        Args:
            agent: Plugin agent instance

        Returns:
            Settings schema list
        """
        if hasattr(agent, "get_settings_schema"):
            return agent.get_settings_schema()
        return []

    @staticmethod
    def _extract_defaults(schema: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract default values from schema.

        Args:
            schema: Settings schema

        Returns:
            Dictionary of default values
        """
        defaults = {}
        for setting in schema:
            key = setting.get("key")
            default = setting.get("default")
            if key and default is not None:
                defaults[key] = default
        return defaults

    def _get_overrides(self, plugin_pid: str, version: str) -> Dict[str, Any]:
        """Get instance-specific overrides for plugin by pid@version key.

        Args:
            plugin_pid: Reverse-domain plugin identifier
            version: Plugin version string

        Returns:
            Override settings dictionary as {key: value}
        """
        plugin_settings = self.instance_config.get("plugin_settings", {})
        lookup_key = f"{plugin_pid}@{version}" if version else plugin_pid
        entry = plugin_settings.get(lookup_key, {})
        if "settings" in entry:
            return {
                s["key"]: s["value"] for s in entry.get("settings", []) if "key" in s
            }
        return entry

    @staticmethod
    def _validate_required(
        plugin_pid: str,
        schema: List[Dict[str, Any]],
        resolved: Dict[str, Any],
    ) -> None:
        """Validate that all required settings are present.

        Args:
            plugin_pid: Reverse-domain plugin identifier
            schema: Settings schema
            resolved: Resolved settings

        Raises:
            ValueError: If required settings are missing
        """
        missing = []
        for setting in schema:
            if setting.get("required", False):
                key = setting.get("key")
                if key not in resolved or resolved[key] is None:
                    missing.append(key)

        if missing:
            raise ValueError(
                f"Plugin '{plugin_pid}' missing required settings: {', '.join(missing)}"
            )


def get_sensitive_keys(schema: List[Dict[str, Any]]) -> List[str]:
    """Extract keys marked as sensitive from schema.

    Sensitive settings should be masked in logs and API responses.

    Args:
        schema: Settings schema

    Returns:
        List of sensitive setting keys
    """
    return [
        setting.get("key")
        for setting in schema
        if setting.get("sensitive", False) and setting.get("key")
    ]


def mask_sensitive_settings(
    settings: Dict[str, Any],
    schema: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Mask sensitive values in settings dictionary.

    Args:
        settings: Settings dictionary
        schema: Settings schema

    Returns:
        Settings with masked sensitive values
    """
    sensitive_keys = get_sensitive_keys(schema)
    masked = settings.copy()

    for key in sensitive_keys:
        if key in masked:
            masked[key] = "***MASKED***"

    return masked
