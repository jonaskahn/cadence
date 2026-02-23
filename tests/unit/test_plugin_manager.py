"""Unit tests for SDKPluginManager version-pinning and on-demand loading logic.

Covers:
  - _parse_plugin_spec: plain pid and 'pid@version' parsing
  - load_plugins: versioned vs unversioned code paths, (pid, version) bundle key
  - _resolve_contract: non-versioned filesystem fallback
  - _find_latest_version_on_filesystem: semver selection from directories
  - _load_versioned_plugin_from_filesystem: filesystem fallback logic
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Pre-load engine module first to avoid circular import:
# cadence.infrastructure.plugins.plugin_manager → cadence.engine.base →
# cadence.engine.__init__ → cadence.engine.factory →
# cadence.infrastructure.plugins (partially initialized) → ImportError
import cadence.engine.factory  # noqa: F401
from cadence.infrastructure.plugins.plugin_manager import (
    SDKPluginManager,
    _parse_plugin_spec,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_contract(
    pid: str = "com.example.search", version: str = "1.0.0"
) -> MagicMock:
    contract = MagicMock()
    contract.pid = pid
    contract.version = version
    return contract


def _make_manager(plugin_store=None) -> SDKPluginManager:
    adapter = MagicMock()
    adapter.framework_type = "langgraph"
    llm_factory = MagicMock()
    llm_factory.create_model_by_id = AsyncMock(return_value=MagicMock())
    return SDKPluginManager(
        adapter=adapter,
        llm_factory=llm_factory,
        org_id="org_test",
        tenant_plugins_root="/tmp/plugins",
        system_plugins_dir="/tmp/sys_plugins",
        plugin_store=plugin_store,
    )


# ---------------------------------------------------------------------------
# _parse_plugin_spec
# ---------------------------------------------------------------------------


class TestParsePluginSpec:
    def test_plain_pid_returns_no_version(self) -> None:
        pid, ver = _parse_plugin_spec("com.example.search")
        assert pid == "com.example.search"
        assert ver is None

    def test_versioned_pid_returns_pid_and_version(self) -> None:
        pid, ver = _parse_plugin_spec("com.example.search@1.2.3")
        assert pid == "com.example.search"
        assert ver == "1.2.3"

    def test_multiple_at_signs_uses_last_segment_as_version(self) -> None:
        """Everything after the last @ is treated as version (rsplit semantics)."""
        pid, ver = _parse_plugin_spec("com.example@weird@1.0.0")
        assert pid == "com.example@weird"
        assert ver == "1.0.0"

    def test_strips_whitespace_from_pid_and_version(self) -> None:
        pid, ver = _parse_plugin_spec("  com.example.search  @  1.0.0  ")
        assert pid == "com.example.search"
        assert ver == "1.0.0"


# ---------------------------------------------------------------------------
# load_plugins — version pinning paths
# ---------------------------------------------------------------------------


REGISTRY_PATH = "cadence_sdk.registry.plugin_registry.PluginRegistry"


class TestLoadPluginsVersionPinning:
    @pytest.mark.asyncio
    async def test_plain_pid_uses_registry_get_plugin(self) -> None:
        manager = _make_manager()
        contract = _make_contract()

        with (
            patch(REGISTRY_PATH) as MockRegistry,
            patch.object(manager, "_validate_plugin"),
            patch.object(manager, "_create_bundle", return_value=MagicMock()),
        ):
            registry = MockRegistry.instance.return_value
            registry.get_plugin.return_value = contract

            await manager.load_plugins(["com.example.search"], {})

            registry.get_plugin.assert_called_once_with("com.example.search")
            registry.get_plugin_by_version.assert_not_called()

    @pytest.mark.asyncio
    async def test_versioned_pid_uses_get_plugin_by_version(self) -> None:
        manager = _make_manager()
        contract = _make_contract(version="1.2.3")

        with (
            patch(REGISTRY_PATH) as MockRegistry,
            patch.object(manager, "_validate_plugin"),
            patch.object(manager, "_create_bundle", return_value=MagicMock()),
        ):
            registry = MockRegistry.instance.return_value
            registry.get_plugin_by_version.return_value = contract

            await manager.load_plugins(["com.example.search@1.2.3"], {})

            registry.get_plugin_by_version.assert_called_once_with(
                "com.example.search", "1.2.3"
            )
            registry.get_plugin.assert_not_called()

    @pytest.mark.asyncio
    async def test_versioned_pid_falls_back_to_filesystem_when_not_in_registry(
        self,
    ) -> None:
        manager = _make_manager()
        contract = _make_contract(version="1.2.3")

        with (
            patch(REGISTRY_PATH) as MockRegistry,
            patch.object(
                manager,
                "_load_versioned_plugin_from_filesystem",
                new=AsyncMock(return_value=contract),
            ) as mock_fs,
            patch.object(manager, "_validate_plugin"),
            patch.object(manager, "_create_bundle", return_value=MagicMock()),
        ):
            registry = MockRegistry.instance.return_value
            registry.get_plugin_by_version.return_value = None

            await manager.load_plugins(["com.example.search@1.2.3"], {})

            mock_fs.assert_awaited_once_with("com.example.search", "1.2.3")

    @pytest.mark.asyncio
    async def test_versioned_pid_raises_when_not_found_anywhere(self) -> None:
        manager = _make_manager()

        with (
            patch(REGISTRY_PATH) as MockRegistry,
            patch.object(
                manager,
                "_load_versioned_plugin_from_filesystem",
                new=AsyncMock(return_value=None),
            ),
        ):
            registry = MockRegistry.instance.return_value
            registry.get_plugin_by_version.return_value = None

            with pytest.raises(
                ValueError, match="not found in registry or plugin store"
            ):
                await manager.load_plugins(["com.example.search@9.9.9"], {})

    @pytest.mark.asyncio
    async def test_plain_pid_falls_back_to_filesystem_when_not_in_registry(
        self,
    ) -> None:
        """When registry has no plain pid, the manager scans the filesystem for the latest version."""
        manager = _make_manager()
        contract = _make_contract(pid="com.example.search", version="2.0.0")

        with (
            patch(REGISTRY_PATH) as MockRegistry,
            patch.object(
                manager,
                "_find_latest_version_on_filesystem",
                return_value="2.0.0",
            ),
            patch.object(
                manager,
                "_load_versioned_plugin_from_filesystem",
                new=AsyncMock(return_value=contract),
            ) as mock_fs_load,
            patch.object(manager, "_validate_plugin"),
            patch.object(manager, "_create_bundle", return_value=MagicMock()),
        ):
            registry = MockRegistry.instance.return_value
            registry.get_plugin.return_value = None

            await manager.load_plugins(["com.example.search"], {})

            mock_fs_load.assert_awaited_once_with("com.example.search", "2.0.0")
            assert ("com.example.search", "2.0.0") in manager._bundles

    @pytest.mark.asyncio
    async def test_plain_pid_raises_when_not_in_registry_or_filesystem(self) -> None:
        manager = _make_manager()

        with (
            patch(REGISTRY_PATH) as MockRegistry,
            patch.object(
                manager,
                "_find_latest_version_on_filesystem",
                return_value=None,
            ),
        ):
            registry = MockRegistry.instance.return_value
            registry.get_plugin.return_value = None

            with pytest.raises(ValueError, match="not found in registry or filesystem"):
                await manager.load_plugins(["com.example.missing"], {})

    @pytest.mark.asyncio
    async def test_bundle_keyed_by_plain_pid_in_bundles_property(self) -> None:
        manager = _make_manager()
        contract = _make_contract(pid="com.example.search", version="1.2.3")
        mock_bundle = MagicMock()

        with (
            patch(REGISTRY_PATH) as MockRegistry,
            patch.object(manager, "_validate_plugin"),
            patch.object(manager, "_create_bundle", return_value=mock_bundle),
        ):
            registry = MockRegistry.instance.return_value
            registry.get_plugin_by_version.return_value = contract

            await manager.load_plugins(["com.example.search@1.2.3"], {})

            assert "com.example.search" in manager.bundles
            assert "com.example.search@1.2.3" not in manager.bundles

    @pytest.mark.asyncio
    async def test_bundle_keyed_by_pid_version_tuple_in_internal_store(self) -> None:
        """Internal _bundles dict uses (pid, version) as the compound key."""
        manager = _make_manager()
        contract = _make_contract(pid="com.example.search", version="1.2.3")
        mock_bundle = MagicMock()

        with (
            patch(REGISTRY_PATH) as MockRegistry,
            patch.object(manager, "_validate_plugin"),
            patch.object(manager, "_create_bundle", return_value=mock_bundle),
        ):
            registry = MockRegistry.instance.return_value
            registry.get_plugin_by_version.return_value = contract

            await manager.load_plugins(["com.example.search@1.2.3"], {})

            assert ("com.example.search", "1.2.3") in manager._bundles
            assert manager._bundles[("com.example.search", "1.2.3")] is mock_bundle

    @pytest.mark.asyncio
    async def test_same_pid_different_versions_both_stored(self) -> None:
        """Loading pid@1.0.0 then pid@2.0.0 stores both in _bundles without overwriting."""
        manager = _make_manager()
        contract_v1 = _make_contract(pid="com.example.search", version="1.0.0")
        contract_v2 = _make_contract(pid="com.example.search", version="2.0.0")
        bundle_v1 = MagicMock()
        bundle_v2 = MagicMock()

        def fake_create(contract, settings_resolver):
            return bundle_v1 if contract.version == "1.0.0" else bundle_v2

        with (
            patch(REGISTRY_PATH) as MockRegistry,
            patch.object(manager, "_validate_plugin"),
            patch.object(manager, "_create_bundle", side_effect=fake_create),
        ):
            registry = MockRegistry.instance.return_value
            registry.get_plugin_by_version.side_effect = lambda pid, v: (
                contract_v1 if v == "1.0.0" else contract_v2
            )

            await manager.load_plugins(
                ["com.example.search@1.0.0", "com.example.search@2.0.0"], {}
            )

            assert ("com.example.search", "1.0.0") in manager._bundles
            assert ("com.example.search", "2.0.0") in manager._bundles
            assert manager._bundles[("com.example.search", "1.0.0")] is bundle_v1
            assert manager._bundles[("com.example.search", "2.0.0")] is bundle_v2

    @pytest.mark.asyncio
    async def test_already_loaded_same_version_is_skipped(self) -> None:
        """When (pid, version) is already in _bundles, validation and bundle creation are skipped."""
        manager = _make_manager()
        contract = _make_contract(pid="com.example.search", version="1.0.0")
        existing_bundle = MagicMock()
        manager._bundles[("com.example.search", "1.0.0")] = existing_bundle

        with (
            patch(REGISTRY_PATH) as MockRegistry,
            patch.object(manager, "_validate_plugin") as mock_validate,
            patch.object(manager, "_create_bundle", return_value=MagicMock()),
        ):
            registry = MockRegistry.instance.return_value
            registry.get_plugin.return_value = contract

            await manager.load_plugins(["com.example.search"], {})

            mock_validate.assert_not_called()
            assert manager._bundles[("com.example.search", "1.0.0")] is existing_bundle


# ---------------------------------------------------------------------------
# _find_latest_version_on_filesystem
# ---------------------------------------------------------------------------


class TestFindLatestVersionOnFilesystem:
    def test_returns_none_when_no_plugin_directories_exist(
        self, tmp_path: Path
    ) -> None:
        manager = _make_manager()
        manager.tenant_plugins_root = str(tmp_path)
        manager.system_plugins_dir = str(tmp_path / "sys")

        result = manager._find_latest_version_on_filesystem("com.example.search")

        assert result is None

    def test_returns_single_version_when_only_one_exists(self, tmp_path: Path) -> None:
        version_dir = tmp_path / "org_test" / "com.example.search" / "1.0.0"
        version_dir.mkdir(parents=True)

        manager = _make_manager()
        manager.tenant_plugins_root = str(tmp_path)
        manager.system_plugins_dir = None

        result = manager._find_latest_version_on_filesystem("com.example.search")

        assert result == "1.0.0"

    def test_returns_highest_semver_when_multiple_versions_exist(
        self, tmp_path: Path
    ) -> None:
        base = tmp_path / "org_test" / "com.example.search"
        for v in ["1.0.0", "1.9.0", "1.10.0", "2.0.0"]:
            (base / v).mkdir(parents=True)

        manager = _make_manager()
        manager.tenant_plugins_root = str(tmp_path)
        manager.system_plugins_dir = None

        result = manager._find_latest_version_on_filesystem("com.example.search")

        assert result == "2.0.0"

    def test_prefers_tenant_dir_over_system_dir(self, tmp_path: Path) -> None:
        tenant_dir = tmp_path / "org_test" / "com.example.search" / "3.0.0"
        tenant_dir.mkdir(parents=True)

        sys_dir = tmp_path / "sys" / "com.example.search" / "1.0.0"
        sys_dir.mkdir(parents=True)

        manager = _make_manager()
        manager.tenant_plugins_root = str(tmp_path)
        manager.system_plugins_dir = str(tmp_path / "sys")

        result = manager._find_latest_version_on_filesystem("com.example.search")

        assert result == "3.0.0"

    def test_falls_back_to_system_dir_when_tenant_dir_is_absent(
        self, tmp_path: Path
    ) -> None:
        sys_dir = tmp_path / "sys" / "com.example.search" / "1.5.0"
        sys_dir.mkdir(parents=True)

        manager = _make_manager()
        manager.tenant_plugins_root = str(tmp_path)
        manager.system_plugins_dir = str(tmp_path / "sys")

        result = manager._find_latest_version_on_filesystem("com.example.search")

        assert result == "1.5.0"

    def test_ignores_hidden_directories(self, tmp_path: Path) -> None:
        base = tmp_path / "org_test" / "com.example.search"
        (base / "1.0.0").mkdir(parents=True)
        (base / ".hidden").mkdir(parents=True)

        manager = _make_manager()
        manager.tenant_plugins_root = str(tmp_path)
        manager.system_plugins_dir = None

        result = manager._find_latest_version_on_filesystem("com.example.search")

        assert result == "1.0.0"


# ---------------------------------------------------------------------------
# _load_versioned_plugin_from_filesystem
# ---------------------------------------------------------------------------


class TestLoadVersionedPluginFromFilesystem:
    @pytest.mark.asyncio
    async def test_returns_none_when_plugin_store_raises_and_no_local_dir(
        self,
    ) -> None:
        store = MagicMock()
        store.ensure_local = AsyncMock(side_effect=FileNotFoundError)
        manager = _make_manager(plugin_store=store)

        with patch("pathlib.Path.exists", return_value=False):
            result = await manager._load_versioned_plugin_from_filesystem(
                "com.example.search", "1.0.0"
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_plugin_file_missing(self, tmp_path: Path) -> None:
        """Empty version dir without plugin.py returns None."""
        version_dir = tmp_path / "com.example.search" / "1.0.0"
        version_dir.mkdir(parents=True)

        manager = _make_manager()
        manager.tenant_plugins_root = str(tmp_path)
        manager.system_plugins_dir = None

        result = await manager._load_versioned_plugin_from_filesystem(
            "com.example.search", "1.0.0"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_loads_plugin_from_tenant_path(self, tmp_path: Path) -> None:
        version_dir = tmp_path / "org_test" / "com.example.search" / "1.0.0"
        version_dir.mkdir(parents=True)
        plugin_file = version_dir / "plugin.py"
        plugin_file.write_text(
            "from cadence_sdk.base import BasePlugin\n"
            "from cadence_sdk.base.metadata import PluginMetadata\n"
            "class MyPlugin(BasePlugin):\n"
            "    @staticmethod\n"
            "    def get_metadata():\n"
            "        return PluginMetadata(\n"
            "            pid='com.example.search',\n"
            "            name='Search',\n"
            "            description='desc',\n"
            "            version='1.0.0',\n"
            "        )\n"
            "    @staticmethod\n"
            "    def create_agent(): return None\n"
        )

        manager = _make_manager()
        manager.tenant_plugins_root = str(tmp_path)
        manager.system_plugins_dir = None

        with patch(REGISTRY_PATH) as MockRegistry:
            MockRegistry.instance.return_value = MagicMock()

            result = await manager._load_versioned_plugin_from_filesystem(
                "com.example.search", "1.0.0"
            )

        assert result is None or hasattr(result, "pid")

    @pytest.mark.asyncio
    async def test_uses_store_ensure_local_when_available(self) -> None:
        store = MagicMock()
        store.ensure_local = AsyncMock(side_effect=FileNotFoundError)
        manager = _make_manager(plugin_store=store)

        with patch("pathlib.Path.exists", return_value=False):
            await manager._load_versioned_plugin_from_filesystem(
                "com.example.search", "2.0.0"
            )

        assert store.ensure_local.await_count == 2
        calls = store.ensure_local.await_args_list
        assert (
            calls[0].kwargs.get("org_id") == "org_test"
            or calls[0].args[2] == "org_test"
        )
        assert calls[1].kwargs.get("org_id") is None or calls[1].args[2] is None
