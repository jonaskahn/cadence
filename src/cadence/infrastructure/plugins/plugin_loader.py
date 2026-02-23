"""Plugin filesystem discovery and module loading mixin."""

import logging
import types
from abc import ABC, abstractmethod
from pathlib import Path

from cadence_sdk.registry.contracts import PluginContract
from cadence_sdk.registry.plugin_registry import PluginRegistry
from cadence_sdk.utils.directory_discovery import DirectoryPluginDiscovery

logger = logging.getLogger(__name__)


class PluginLoaderMixin(ABC):
    """Mixin for plugin filesystem discovery, registry resolution, and module loading.

    Requires self.get_org_id(), self.get_tenant_plugins_root(), self.get_system_plugins_dir(),
    and self.get_plugin_store().
    """

    @abstractmethod
    def get_org_id(self):
        pass

    @abstractmethod
    def get_tenant_plugins_root(self):
        pass

    @abstractmethod
    def get_system_plugins_dir(self):
        pass

    @abstractmethod
    def get_plugin_store(self):
        pass

    def discover_plugins(self) -> list[str]:
        """Discover plugins from all sources.

        Discovery order (highest to lowest priority):
        1. Tenant directory
        2. System directory
        3. Environment (pip-installed packages)

        Returns:
            List of discovered plugin pids
        """
        registry = PluginRegistry.instance()
        discovered_plugin_ids: set[str] = set()

        tenant_dir = Path(self.get_tenant_plugins_root()) / self.get_org_id()
        if tenant_dir.exists():
            tenant_plugins = DirectoryPluginDiscovery(str(tenant_dir)).discover()
            discovered_plugin_ids.update(plugin.pid for plugin in tenant_plugins)
            logger.info(
                f"Discovered {len(tenant_plugins)} tenant plugins for {self.get_org_id()}"
            )

        if self.get_system_plugins_dir():
            system_dir = Path(self.get_system_plugins_dir())
            if system_dir.exists():
                system_plugins = DirectoryPluginDiscovery(str(system_dir)).discover()
                discovered_plugin_ids.update(plugin.pid for plugin in system_plugins)
                logger.info(f"Discovered {len(system_plugins)} system plugins")

        environment_plugins = registry.list_registered_plugins()
        discovered_plugin_ids.update(plugin.pid for plugin in environment_plugins)

        logger.info(f"Total unique plugins discovered: {len(discovered_plugin_ids)}")
        return list(discovered_plugin_ids)

    async def _resolve_contract(
        self,
        pid: str,
        requested_version: str | None,
        registry: PluginRegistry,
    ) -> PluginContract:
        """Resolve plugin contract from registry or filesystem.

        Raises:
            ValueError: If plugin or version not found
        """
        if requested_version:
            contract = registry.get_plugin_by_version(pid, requested_version)
            if not contract:
                logger.warning(
                    f"Plugin '{pid}' v{requested_version} not in registry, trying filesystem"
                )
                contract = await self._load_versioned_plugin_from_filesystem(
                    pid, requested_version
                )
            if not contract:
                raise ValueError(
                    f"Plugin '{pid}' version '{requested_version}' not found "
                    f"in registry or plugin store"
                )
            return contract

        contract = registry.get_plugin(pid)
        if not contract:
            logger.warning(
                f"Plugin '{pid}' not in registry, scanning filesystem for latest version"
            )
            latest = self._find_latest_version_on_filesystem(pid)
            if latest:
                contract = await self._load_versioned_plugin_from_filesystem(
                    pid, latest
                )
        if not contract:
            raise ValueError(f"Plugin '{pid}' not found in registry or filesystem")

        if self.get_plugin_store() and self.get_plugin_store().s3_enabled:
            try:
                await self.get_plugin_store().ensure_local(
                    pid=pid, version=contract.version, org_id=self.get_org_id()
                )
            except FileNotFoundError:
                logger.warning(
                    f"Plugin '{pid}' v{contract.version} not found in S3, "
                    f"using locally cached version"
                )

        return contract

    async def _load_versioned_plugin_from_filesystem(
        self, pid: str, version: str
    ) -> PluginContract | None:
        """Load a specific plugin version from the plugin store or local filesystem.

        Search order: tenant PluginStore → system PluginStore → tenant local dir
        → system local dir. Registers the loaded contract in the registry.
        """
        local_plugin_dir = await self._resolve_local_plugin_directory(pid, version)
        if local_plugin_dir is None:
            return None

        plugin_file_path = self._find_plugin_file(local_plugin_dir)
        if plugin_file_path is None:
            return None

        module = self._load_plugin_module(plugin_file_path, pid, version)
        if module is None:
            return None

        plugin_class = self._extract_plugin_class(module)
        if plugin_class is None:
            return None

        contract = PluginContract(plugin_class)
        PluginRegistry.instance().register(plugin_class, override=False)
        return contract

    async def _resolve_local_plugin_directory(
        self, pid: str, version: str
    ) -> Path | None:
        """Resolve the local directory for a versioned plugin."""
        if self.get_plugin_store():
            try:
                return await self.get_plugin_store().ensure_local(
                    pid, version, self.get_org_id()
                )
            except FileNotFoundError:
                try:
                    return await self.get_plugin_store().ensure_local(
                        pid, version, None
                    )
                except FileNotFoundError:
                    pass

        tenant_path = (
            Path(self.get_tenant_plugins_root()) / self.get_org_id() / pid / version
        )
        if tenant_path.exists() and any(tenant_path.iterdir()):
            return tenant_path

        if self.get_system_plugins_dir():
            system_path = Path(self.get_system_plugins_dir()) / pid / version
            if system_path.exists() and any(system_path.iterdir()):
                return system_path

        return None

    @staticmethod
    def _find_plugin_file(local_plugin_dir: Path) -> Path | None:
        """Find plugin.py in a directory or one level deep in subdirectories."""
        direct_path = Path(local_plugin_dir) / "plugin.py"
        if direct_path.exists():
            return direct_path

        for subdir in Path(local_plugin_dir).iterdir():
            if (
                subdir.is_dir()
                and not subdir.name.startswith(".")
                and subdir.name != "__pycache__"
            ):
                candidate = subdir / "plugin.py"
                if candidate.exists():
                    return candidate

        return None

    @staticmethod
    def _load_plugin_module(
        plugin_file_path: Path, pid: str, version: str
    ) -> types.ModuleType | None:
        """Load a Python module from a plugin file.

        Temporarily adds the file's parent directory to sys.path during loading.
        """
        import importlib.util
        import sys

        plugin_module_name = (
            f"_cadence_plugin_{pid.replace('.', '_')}_{version.replace('.', '_')}"
        )
        module_spec = importlib.util.spec_from_file_location(
            plugin_module_name, plugin_file_path
        )
        if module_spec is None or module_spec.loader is None:
            return None

        module = importlib.util.module_from_spec(module_spec)
        plugin_parent_dir = str(plugin_file_path.parent)
        sys.path.insert(0, plugin_parent_dir)
        try:
            module_spec.loader.exec_module(module)
        finally:
            if plugin_parent_dir in sys.path:
                sys.path.remove(plugin_parent_dir)

        return module

    @staticmethod
    def _extract_plugin_class(module: types.ModuleType) -> type | None:
        """Extract the first BasePlugin subclass from a loaded module."""
        from cadence_sdk.base import BasePlugin

        return next(
            (
                getattr(module, name)
                for name in dir(module)
                if isinstance(getattr(module, name), type)
                and issubclass(getattr(module, name), BasePlugin)
                and getattr(module, name) is not BasePlugin
            ),
            None,
        )

    def _find_latest_version_on_filesystem(self, pid: str) -> str | None:
        """Scan filesystem for latest available version directory of a plugin."""
        candidates: list[str] = []

        tenant_pid_dir = Path(self.get_tenant_plugins_root()) / self.get_org_id() / pid
        if tenant_pid_dir.exists():
            candidates.extend(
                d.name
                for d in tenant_pid_dir.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            )

        if not candidates and self.get_system_plugins_dir():
            system_pid_dir = Path(self.get_system_plugins_dir()) / pid
            if system_pid_dir.exists():
                candidates.extend(
                    d.name
                    for d in system_pid_dir.iterdir()
                    if d.is_dir() and not d.name.startswith(".")
                )

        if not candidates:
            return None

        try:
            return max(candidates, key=lambda v: [int(x) for x in v.split(".")])
        except ValueError:
            return sorted(candidates)[-1]
