"""Plugin infrastructure for Cadence.

Provides plugin discovery, validation, bundle management, and settings resolution.
Exports SDKPluginManager, SDKPluginBundle, PluginStore, and PluginSettingsResolver
for loading and configuring plugins from tenant and system directories.
"""

from cadence.infrastructure.plugins.plugin_manager import (
    SDKPluginBundle,
    SDKPluginManager,
)
from cadence.infrastructure.plugins.plugin_settings_resolver import (
    PluginSettingsResolver,
    get_sensitive_keys,
    mask_sensitive_settings,
)
from cadence.repository.plugin_store_repository import PluginStoreRepository

__all__ = [
    "SDKPluginManager",
    "SDKPluginBundle",
    "PluginSettingsResolver",
    "get_sensitive_keys",
    "mask_sensitive_settings",
    "PluginStoreRepository",
]
