"""Plugin discovery, validation, and bundle management.

SDKPluginManager coordinates plugin lifecycle by composing PluginLoaderMixin
and PluginBundleBuilderMixin. SDKPluginBundle defines the complete set of
resources for an active plugin.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from cadence_sdk.base.agent import BaseAgent
from cadence_sdk.base.metadata import PluginMetadata
from cadence_sdk.registry.contracts import PluginContract
from cadence_sdk.types.sdk_tools import UvTool
from langchain_core.language_models import BaseChatModel

from cadence.engine.base import OrchestratorAdapter
from cadence.infrastructure.plugins.plugin_bundle_builder import (
    PluginBundleBuilderMixin,
)
from cadence.infrastructure.plugins.plugin_loader import PluginLoaderMixin
from cadence.infrastructure.plugins.plugin_settings_resolver import (
    PluginSettingsResolver,
)

if TYPE_CHECKING:
    from cadence.engine.shared_resources.bundle_cache import SharedBundleCache
    from cadence.infrastructure.llm.factory import LLMModelFactory
    from cadence.repository.plugin_store_repository import PluginStoreRepository

logger = logging.getLogger(__name__)


def _parse_plugin_spec(plugin_spec: str) -> tuple[str, str | None]:
    """Parse 'pid@version' or plain 'pid' plugin spec.

    Returns (pid, version) where version is None if not specified.
    """
    if "@" in plugin_spec:
        pid, version = plugin_spec.rsplit("@", 1)
        return pid.strip(), version.strip()
    return plugin_spec, None


@dataclass
class SDKPluginBundle:
    """Complete plugin bundle ready for orchestrator use.

    Contains all resolved resources for a plugin including agent, tools,
    bound model, and orchestrator-native tools.
    """

    contract: PluginContract
    metadata: PluginMetadata
    agent: BaseAgent
    bound_model: BaseChatModel | None
    uv_tools: list[UvTool]
    orchestrator_tools: list[Any]
    adapter: OrchestratorAdapter
    tool_node: Any | None = None
    agent_node: Any | None = None


class SDKPluginManager(PluginLoaderMixin, PluginBundleBuilderMixin):
    """Manager for plugin discovery, validation, and bundle creation.

    Handles complete plugin lifecycle:
    1. Discovery from environment, system, and tenant directories
    2. Validation (shallow, dependencies, deep, custom)
    3. Bundle creation with resolved settings and bound models

    Plugins are identified by their reverse-domain `pid`
    (e.g., `io.cadence.system.product_search`).
    """

    def get_org_id(self):
        return self.org_id

    def get_tenant_plugins_root(self):
        return self.tenant_plugins_root

    def get_system_plugins_dir(self):
        return self.system_plugins_dir

    def get_plugin_store(self):
        return self.plugin_store

    def get_bundle_cache(self):
        return self.bundle_cache

    def get_adapter(self):
        return self.adapter

    def get_llm_factory(self):
        return self.llm_factory

    def __init__(
        self,
        adapter: OrchestratorAdapter,
        llm_factory: LLMModelFactory,
        org_id: str,
        tenant_plugins_root: str,
        system_plugins_dir: str | None = None,
        plugin_store: PluginStoreRepository | None = None,
        bundle_cache: SharedBundleCache | None = None,
    ):
        self.adapter = adapter
        self.llm_factory = llm_factory
        self.org_id = org_id
        self.tenant_plugins_root = tenant_plugins_root
        self.system_plugins_dir = system_plugins_dir
        self.plugin_store = plugin_store
        self.bundle_cache = bundle_cache
        self._bundles: dict[tuple[str, str], SDKPluginBundle] = {}

    async def load_plugins(
        self,
        plugin_specs: list[str],
        instance_config: dict[str, Any],
    ) -> dict[str, SDKPluginBundle]:
        """Load and create bundles for specified plugins.

        Args:
            plugin_specs: List of plugin specs to load ('pid@version' or bare 'pid')
            instance_config: Instance configuration dictionary

        Returns:
            Dict mapping plugin pid to bundle

        Raises:
            ValueError: If plugin validation fails or pid not found in registry
        """
        from cadence_sdk.registry.plugin_registry import PluginRegistry

        registry = PluginRegistry.instance()
        settings_resolver = PluginSettingsResolver(instance_config)

        for plugin_spec in plugin_specs:
            pid, requested_version = _parse_plugin_spec(plugin_spec)

            contract = await self._resolve_contract(pid, requested_version, registry)

            if (pid, contract.version) in self._bundles:
                logger.debug(f"Plugin '{pid}' v{contract.version} already loaded")
                continue

            self._validate_plugin(contract)
            bundle = await self._create_bundle_with_cache(contract, settings_resolver)
            self._bundles[(pid, contract.version)] = bundle
            logger.info(f"Loaded plugin bundle: {pid} v{contract.version}")

        return self.bundles

    @property
    def bundles(self) -> dict[str, SDKPluginBundle]:
        """Return plugin bundles keyed by pid (latest version per pid)."""
        return {pid: bundle for (pid, _version), bundle in self._bundles.items()}

    def get_bundle(self, pid: str, version: str) -> SDKPluginBundle | None:
        """Get loaded plugin bundle by pid and version."""
        return self._bundles.get((pid, version))

    async def cleanup_all(self) -> None:
        """Cleanup all loaded plugins."""
        for (pid, _version), bundle in self._bundles.items():
            if hasattr(bundle.agent, "cleanup"):
                await bundle.agent.cleanup()
                logger.debug(f"Cleaned up plugin: {pid}")

        self._bundles.clear()
