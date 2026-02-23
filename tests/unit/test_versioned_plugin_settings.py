"""Unit tests for versioned plugin settings (pid@version key scheme).

Covers:
  - PluginSettingsResolver: resolve() looks up pid@version key
  - OrchestratorConfigMixin.activate_plugin_version:
      * Entry already exists — only flips active flags and updates active_plugins
      * Entry absent — auto-migrates: copies matching keys, sets new keys to default,
        omits deleted keys
      * Reload event published only when tier == 'hot'
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

# Pre-load engine module first to avoid circular import:
# cadence.infrastructure.plugins → cadence.engine.base →
# cadence.engine.__init__ → cadence.engine.factory →
# cadence.infrastructure.plugins (partially initialized) → ImportError
import cadence.engine.factory  # noqa: F401
from cadence.infrastructure.plugins.plugin_settings_resolver import (
    PluginSettingsResolver,
)
from cadence.service.orchestrator_config_service import OrchestratorConfigMixin

# ---------------------------------------------------------------------------
# PluginSettingsResolver
# ---------------------------------------------------------------------------


class TestPluginSettingsResolverVersioned:
    """Tests for PluginSettingsResolver.resolve() with versioned keys."""

    def _make_agent(self, schema=None):
        agent = MagicMock()
        agent.get_settings_schema = MagicMock(return_value=schema or [])
        return agent

    def _make_resolver(self, plugin_settings: dict) -> PluginSettingsResolver:
        return PluginSettingsResolver(
            instance_config={"plugin_settings": plugin_settings}
        )

    def test_looks_up_by_pid_at_version_key(self) -> None:
        """resolve() reads overrides from the pid@version key."""
        resolver = self._make_resolver(
            {
                "com.example.search@1.0.0": {
                    "id": "com.example.search",
                    "version": "1.0.0",
                    "active": True,
                    "settings": [{"key": "api_key", "value": "sk-test"}],
                }
            }
        )
        agent = self._make_agent()

        result = resolver.resolve("com.example.search", "1.0.0", agent)

        assert result["api_key"] == "sk-test"

    def test_schema_defaults_applied_when_no_override(self) -> None:
        """resolve() falls back to schema defaults when pid@version entry is absent."""
        resolver = self._make_resolver({})
        agent = self._make_agent(
            schema=[{"key": "timeout", "default": 30, "required": False}]
        )

        result = resolver.resolve("com.example.search", "1.0.0", agent)

        assert result["timeout"] == 30

    def test_override_wins_over_schema_default(self) -> None:
        """resolve() user-override value beats schema default."""
        resolver = self._make_resolver(
            {
                "com.example.search@2.0.0": {
                    "settings": [{"key": "timeout", "value": 99}]
                }
            }
        )
        agent = self._make_agent(
            schema=[{"key": "timeout", "default": 30, "required": False}]
        )

        result = resolver.resolve("com.example.search", "2.0.0", agent)

        assert result["timeout"] == 99

    def test_wrong_version_not_found_falls_back_to_defaults(self) -> None:
        """resolve() uses schema defaults when the requested version key is missing."""
        resolver = self._make_resolver(
            {
                "com.example.search@1.0.0": {
                    "settings": [{"key": "api_key", "value": "old-key"}]
                }
            }
        )
        agent = self._make_agent(
            schema=[{"key": "api_key", "default": None, "required": False}]
        )

        result = resolver.resolve("com.example.search", "2.0.0", agent)

        assert result.get("api_key") is None

    def test_raises_when_required_setting_missing(self) -> None:
        """resolve() raises ValueError when a required setting has no value."""
        resolver = self._make_resolver({})
        agent = self._make_agent(
            schema=[{"key": "api_key", "default": None, "required": True}]
        )

        with pytest.raises(ValueError, match="api_key"):
            resolver.resolve("com.example.search", "1.0.0", agent)


# ---------------------------------------------------------------------------
# OrchestratorConfigMixin.activate_plugin_version
# ---------------------------------------------------------------------------


class _ConcreteConfigService(OrchestratorConfigMixin):
    """Minimal concrete subclass for testing activate_plugin_version."""

    def __init__(self, instance: dict):
        self._instance = dict(instance)

    async def get_instance_config(self, instance_id):
        return (
            self._instance if instance_id == self._instance.get("instance_id") else None
        )

    async def update_instance_config(
        self, instance_id, new_config, trigger_reload, caller_id=None
    ):
        self._instance["config"] = new_config
        return self._instance

    async def update_instance_plugin_settings(
        self, instance_id, plugin_settings, config_hash, caller_id=None
    ):
        self._instance["plugin_settings"] = plugin_settings
        self._instance["config_hash"] = config_hash
        return self._instance

    async def create_instance(self, **kwargs):
        pass


def _make_instance(
    instance_id="inst_1",
    org_id="org_test",
    tier="cold",
    active_plugins=None,
    plugin_settings=None,
):
    return {
        "instance_id": instance_id,
        "org_id": org_id,
        "tier": tier,
        "config": {"active_plugins": active_plugins or []},
        "plugin_settings": plugin_settings or {},
        "status": "active",
        "name": "Test",
        "framework_type": "langgraph",
        "mode": "supervisor",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }


def _make_plugin_service(schema: dict = None) -> MagicMock:
    """Mock PluginService that returns the given default_settings as schema."""
    svc = MagicMock()
    svc.get_schema_for_version = AsyncMock(return_value=schema or {})
    return svc


class TestActivatePluginVersionEntryExists:
    """activate_plugin_version when pid@version entry already exists."""

    async def test_sets_target_active_true(self) -> None:
        """When entry exists, target entry is marked active=True."""
        plugin_settings = {
            "com.example.search@1.0.0": {
                "id": "com.example.search",
                "version": "1.0.0",
                "active": True,
                "settings": [{"key": "api_key", "value": "old"}],
                "name": "Search",
            },
            "com.example.search@2.0.0": {
                "id": "com.example.search",
                "version": "2.0.0",
                "active": False,
                "settings": [{"key": "api_key", "value": "new"}],
                "name": "Search",
            },
        }
        instance = _make_instance(
            active_plugins=["com.example.search@1.0.0"],
            plugin_settings=plugin_settings,
        )
        service = _ConcreteConfigService(instance)

        await service.activate_plugin_version(
            instance_id="inst_1",
            org_id="org_test",
            pid="com.example.search",
            version="2.0.0",
            plugin_service=_make_plugin_service(),
        )

        ps = service._instance["plugin_settings"]
        assert ps["com.example.search@2.0.0"]["active"] is True

    async def test_sets_old_version_active_false(self) -> None:
        """When activating new version, old version entry is deactivated."""
        plugin_settings = {
            "com.example.search@1.0.0": {
                "id": "com.example.search",
                "version": "1.0.0",
                "active": True,
                "settings": [],
                "name": "Search",
            },
            "com.example.search@2.0.0": {
                "id": "com.example.search",
                "version": "2.0.0",
                "active": False,
                "settings": [],
                "name": "Search",
            },
        }
        instance = _make_instance(
            active_plugins=["com.example.search@1.0.0"],
            plugin_settings=plugin_settings,
        )
        service = _ConcreteConfigService(instance)

        await service.activate_plugin_version(
            instance_id="inst_1",
            org_id="org_test",
            pid="com.example.search",
            version="2.0.0",
            plugin_service=_make_plugin_service(),
        )

        ps = service._instance["plugin_settings"]
        assert ps["com.example.search@1.0.0"]["active"] is False

    async def test_updates_active_plugins_in_config(self) -> None:
        """activate_plugin_version replaces old pid@* in active_plugins."""
        plugin_settings = {
            "com.example.search@1.0.0": {
                "id": "com.example.search",
                "version": "1.0.0",
                "active": True,
                "settings": [],
                "name": "Search",
            },
            "com.example.search@2.0.0": {
                "id": "com.example.search",
                "version": "2.0.0",
                "active": False,
                "settings": [],
                "name": "Search",
            },
        }
        instance = _make_instance(
            active_plugins=["com.example.search@1.0.0"],
            plugin_settings=plugin_settings,
        )
        service = _ConcreteConfigService(instance)

        await service.activate_plugin_version(
            instance_id="inst_1",
            org_id="org_test",
            pid="com.example.search",
            version="2.0.0",
            plugin_service=_make_plugin_service(),
        )

        active = service._instance["config"]["active_plugins"]
        assert "com.example.search@2.0.0" in active
        assert "com.example.search@1.0.0" not in active

    async def test_does_not_publish_reload_for_cold_tier(self) -> None:
        """activate_plugin_version does NOT publish reload for cold instances."""
        plugin_settings = {
            "com.example.search@2.0.0": {
                "id": "com.example.search",
                "version": "2.0.0",
                "active": False,
                "settings": [],
                "name": "Search",
            },
        }
        instance = _make_instance(
            tier="cold",
            active_plugins=["com.example.search@1.0.0"],
            plugin_settings=plugin_settings,
        )
        service = _ConcreteConfigService(instance)
        event_publisher = MagicMock()
        event_publisher.publish_reload = AsyncMock()

        await service.activate_plugin_version(
            instance_id="inst_1",
            org_id="org_test",
            pid="com.example.search",
            version="2.0.0",
            plugin_service=_make_plugin_service(),
            event_publisher=event_publisher,
        )

        event_publisher.publish_reload.assert_not_awaited()

    async def test_publishes_reload_for_hot_tier(self) -> None:
        """activate_plugin_version publishes reload when tier is hot."""
        plugin_settings = {
            "com.example.search@2.0.0": {
                "id": "com.example.search",
                "version": "2.0.0",
                "active": False,
                "settings": [],
                "name": "Search",
            },
        }
        instance = _make_instance(
            tier="hot",
            active_plugins=["com.example.search@1.0.0"],
            plugin_settings=plugin_settings,
        )
        service = _ConcreteConfigService(instance)
        event_publisher = MagicMock()
        event_publisher.publish_reload = AsyncMock()

        await service.activate_plugin_version(
            instance_id="inst_1",
            org_id="org_test",
            pid="com.example.search",
            version="2.0.0",
            plugin_service=_make_plugin_service(),
            event_publisher=event_publisher,
        )

        event_publisher.publish_reload.assert_awaited_once()


class TestActivatePluginVersionAutoMigrate:
    """activate_plugin_version when pid@version entry does NOT exist (auto-migrate)."""

    async def test_creates_new_entry_with_matching_keys_copied(self) -> None:
        """Keys present in both old and new schema are copied from old values."""
        plugin_settings = {
            "com.example.search@1.0.0": {
                "id": "com.example.search",
                "version": "1.0.0",
                "active": True,
                "settings": [
                    {"key": "api_key", "value": "sk-old-key"},
                    {"key": "max_results", "value": 10},
                ],
                "name": "Search",
            },
        }
        instance = _make_instance(
            active_plugins=["com.example.search@1.0.0"],
            plugin_settings=plugin_settings,
        )
        service = _ConcreteConfigService(instance)
        plugin_service = _make_plugin_service(
            schema={"api_key": None, "max_results": 5, "new_setting": None}
        )

        await service.activate_plugin_version(
            instance_id="inst_1",
            org_id="org_test",
            pid="com.example.search",
            version="2.0.0",
            plugin_service=plugin_service,
        )

        ps = service._instance["plugin_settings"]
        new_entry = ps["com.example.search@2.0.0"]
        settings_map = {s["key"]: s["value"] for s in new_entry["settings"]}
        assert settings_map["api_key"] == "sk-old-key"
        assert settings_map["max_results"] == 10

    async def test_new_keys_get_catalog_defaults(self) -> None:
        """Keys only in new version schema receive catalog default values."""
        plugin_settings = {
            "com.example.search@1.0.0": {
                "id": "com.example.search",
                "version": "1.0.0",
                "active": True,
                "settings": [{"key": "api_key", "value": "sk-old"}],
                "name": "Search",
            },
        }
        instance = _make_instance(
            active_plugins=["com.example.search@1.0.0"],
            plugin_settings=plugin_settings,
        )
        service = _ConcreteConfigService(instance)
        plugin_service = _make_plugin_service(
            schema={"api_key": None, "new_setting": "default-val"}
        )

        await service.activate_plugin_version(
            instance_id="inst_1",
            org_id="org_test",
            pid="com.example.search",
            version="2.0.0",
            plugin_service=plugin_service,
        )

        ps = service._instance["plugin_settings"]
        new_entry = ps["com.example.search@2.0.0"]
        settings_map = {s["key"]: s["value"] for s in new_entry["settings"]}
        assert settings_map["new_setting"] == "default-val"

    async def test_removed_keys_are_omitted(self) -> None:
        """Keys only in old version (not in new schema) are not carried over."""
        plugin_settings = {
            "com.example.search@1.0.0": {
                "id": "com.example.search",
                "version": "1.0.0",
                "active": True,
                "settings": [
                    {"key": "api_key", "value": "sk-old"},
                    {"key": "deprecated_key", "value": "old-value"},
                ],
                "name": "Search",
            },
        }
        instance = _make_instance(
            active_plugins=["com.example.search@1.0.0"],
            plugin_settings=plugin_settings,
        )
        service = _ConcreteConfigService(instance)
        plugin_service = _make_plugin_service(schema={"api_key": None})

        await service.activate_plugin_version(
            instance_id="inst_1",
            org_id="org_test",
            pid="com.example.search",
            version="2.0.0",
            plugin_service=plugin_service,
        )

        ps = service._instance["plugin_settings"]
        new_entry = ps["com.example.search@2.0.0"]
        keys_in_new = {s["key"] for s in new_entry["settings"]}
        assert "deprecated_key" not in keys_in_new

    async def test_old_entry_is_preserved_with_active_false(self) -> None:
        """After auto-migrate, old version entry remains in plugin_settings with active=False."""
        plugin_settings = {
            "com.example.search@1.0.0": {
                "id": "com.example.search",
                "version": "1.0.0",
                "active": True,
                "settings": [{"key": "api_key", "value": "sk-old"}],
                "name": "Search",
            },
        }
        instance = _make_instance(
            active_plugins=["com.example.search@1.0.0"],
            plugin_settings=plugin_settings,
        )
        service = _ConcreteConfigService(instance)
        plugin_service = _make_plugin_service(schema={"api_key": None})

        await service.activate_plugin_version(
            instance_id="inst_1",
            org_id="org_test",
            pid="com.example.search",
            version="2.0.0",
            plugin_service=plugin_service,
        )

        ps = service._instance["plugin_settings"]
        assert "com.example.search@1.0.0" in ps
        assert ps["com.example.search@1.0.0"]["active"] is False

    async def test_raises_for_wrong_org(self) -> None:
        """activate_plugin_version raises ValueError when org_id doesn't match."""
        instance = _make_instance(org_id="org_test")
        service = _ConcreteConfigService(instance)

        with pytest.raises(ValueError, match="Access denied"):
            await service.activate_plugin_version(
                instance_id="inst_1",
                org_id="org_other",
                pid="com.example.search",
                version="2.0.0",
                plugin_service=_make_plugin_service(),
            )

    async def test_raises_when_instance_not_found(self) -> None:
        """activate_plugin_version raises ValueError when instance doesn't exist."""
        instance = _make_instance(instance_id="inst_1")
        service = _ConcreteConfigService(instance)

        with pytest.raises(ValueError, match="not found"):
            await service.activate_plugin_version(
                instance_id="inst_missing",
                org_id="org_test",
                pid="com.example.search",
                version="2.0.0",
                plugin_service=_make_plugin_service(),
            )
