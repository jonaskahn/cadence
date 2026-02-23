"""Unit tests for SettingsService.

Verifies all three setting tiers: Global settings, Organization settings,
and Instance config. Also verifies hot-reload triggering on instance config
update, immutability enforcement for framework_type/mode, and soft-delete
behaviour.

Global settings change notifications are broadcast via RabbitMQ
(settings.global_changed) from the controller layer, not from the service.
"""

from unittest.mock import MagicMock

import pytest

from cadence.service.settings_service import SettingsService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def service(
    global_settings_repo: MagicMock,
    org_settings_repo: MagicMock,
    instance_repo: MagicMock,
    orchestrator_pool: MagicMock,
) -> SettingsService:
    """Provide a fully wired SettingsService with all dependencies mocked."""
    return SettingsService(
        global_settings_repo=global_settings_repo,
        org_settings_repo=org_settings_repo,
        instance_repo=instance_repo,
        pool=orchestrator_pool,
    )


@pytest.fixture
def service_minimal(
    global_settings_repo: MagicMock,
    org_settings_repo: MagicMock,
    instance_repo: MagicMock,
) -> SettingsService:
    """Provide a SettingsService without pool (minimal dependencies)."""
    return SettingsService(
        global_settings_repo=global_settings_repo,
        org_settings_repo=org_settings_repo,
        instance_repo=instance_repo,
    )


# ---------------------------------------------------------------------------
# Global Settings
# ---------------------------------------------------------------------------


class TestGetGlobalSetting:
    """Tests for SettingsService.get_global_setting (Global settings)."""

    async def test_returns_value_when_setting_exists(
        self, service: SettingsService, global_settings_repo: MagicMock
    ) -> None:
        """get_global_setting extracts the value field from the setting record."""
        setting = MagicMock()
        setting.value = 4096
        global_settings_repo.get_by_key.return_value = setting

        result = await service.get_global_setting("max_tokens")

        assert result == 4096

    async def test_returns_none_when_setting_absent(
        self, service: SettingsService, global_settings_repo: MagicMock
    ) -> None:
        """get_global_setting returns None when no record exists for the key."""
        global_settings_repo.get_by_key.return_value = None

        result = await service.get_global_setting("missing")

        assert result is None

    async def test_delegates_to_repository(
        self, service: SettingsService, global_settings_repo: MagicMock
    ) -> None:
        """get_global_setting passes the key to the repository lookup."""
        await service.get_global_setting("my_key")

        global_settings_repo.get_by_key.assert_awaited_once_with("my_key")


class TestSetGlobalSetting:
    """Tests for SettingsService.set_global_setting (Global settings)."""

    async def test_upserts_key_value_via_repository(
        self, service: SettingsService, global_settings_repo: MagicMock
    ) -> None:
        """set_global_setting stores the value using the repository upsert."""
        await service.set_global_setting("max_tokens", 8192, "Max tokens limit")

        global_settings_repo.upsert.assert_awaited_once_with(
            key="max_tokens",
            value=8192,
            description="Max tokens limit",
        )

    async def test_completes_without_redis(
        self, service: SettingsService, global_settings_repo: MagicMock
    ) -> None:
        """set_global_setting completes normally — no Redis dependency."""
        await service.set_global_setting("k", "v")

        global_settings_repo.upsert.assert_awaited_once()


class TestListGlobalSettings:
    """Tests for SettingsService.list_global_settings (Global settings)."""

    async def test_returns_all_settings_from_repository(
        self, service: SettingsService, global_settings_repo: MagicMock
    ) -> None:
        """list_global_settings returns every record from the repository."""

        def _make_setting(key, value):
            m = MagicMock()
            m.key = key
            m.value = value
            m.value_type = "number"
            m.description = ""
            return m

        global_settings_repo.get_all.return_value = [
            _make_setting("max_tokens", 4096),
            _make_setting("timeout", 30),
        ]

        result = await service.list_global_settings()

        assert len(result) == 2

    async def test_delegates_to_repository(
        self, service: SettingsService, global_settings_repo: MagicMock
    ) -> None:
        """list_global_settings retrieves all records via the repository."""
        await service.list_global_settings()

        global_settings_repo.get_all.assert_awaited_once()


class TestUpdateGlobalSetting:
    """Tests for SettingsService.update_global_setting (Global settings)."""

    async def test_returns_updated_setting_when_found(
        self, service: SettingsService, global_settings_repo: MagicMock
    ) -> None:
        """update_global_setting returns the updated record when the key exists."""
        existing = MagicMock()
        existing.description = "Max tokens"
        global_settings_repo.get_by_key.return_value = existing

        result = await service.update_global_setting("max_tokens", 8192)

        assert result is not None

    async def test_returns_none_when_setting_not_found(
        self, service: SettingsService, global_settings_repo: MagicMock
    ) -> None:
        """update_global_setting returns None when the key has no stored value."""
        global_settings_repo.get_by_key.return_value = None

        result = await service.update_global_setting("missing", 100)

        assert result is None

    async def test_skips_upsert_when_setting_not_found(
        self, service: SettingsService, global_settings_repo: MagicMock
    ) -> None:
        """update_global_setting does not write to the repository when the key is absent."""
        global_settings_repo.get_by_key.return_value = None

        await service.update_global_setting("missing", 100)

        global_settings_repo.upsert.assert_not_awaited()


class TestDeleteGlobalSetting:
    """Tests for SettingsService.delete_global_setting (Global settings)."""

    async def test_delegates_to_repository(
        self, service: SettingsService, global_settings_repo: MagicMock
    ) -> None:
        """delete_global_setting forwards the key to the repository delete."""
        await service.delete_global_setting("max_tokens")

        global_settings_repo.delete.assert_awaited_once_with("max_tokens")

    async def test_completes_without_error(
        self, service: SettingsService, global_settings_repo: MagicMock
    ) -> None:
        """delete_global_setting completes normally — no Redis dependency."""
        await service.delete_global_setting("max_tokens")

        global_settings_repo.delete.assert_awaited_once()


# ---------------------------------------------------------------------------
# Organization Settings
# ---------------------------------------------------------------------------


class TestGetTenantSetting:
    """Tests for SettingsService.get_tenant_setting (Organization settings)."""

    async def test_returns_value_when_setting_exists(
        self, service: SettingsService, org_settings_repo: MagicMock
    ) -> None:
        """get_tenant_setting extracts the value from the org-level setting record."""
        setting = MagicMock()
        setting.value = "dark"
        org_settings_repo.get_by_key.return_value = setting

        result = await service.get_tenant_setting("org_test", "theme")

        assert result == "dark"

    async def test_returns_none_when_setting_absent(
        self, service: SettingsService, org_settings_repo: MagicMock
    ) -> None:
        """get_tenant_setting returns None when the key has no value for that org."""
        org_settings_repo.get_by_key.return_value = None

        result = await service.get_tenant_setting("org_test", "missing")

        assert result is None

    async def test_passes_org_id_and_key_to_repository(
        self, service: SettingsService, org_settings_repo: MagicMock
    ) -> None:
        """get_tenant_setting forwards both org_id and key to the repository."""
        await service.get_tenant_setting("org_abc", "key_x")

        org_settings_repo.get_by_key.assert_awaited_once_with("org_abc", "key_x")


class TestSetTenantSetting:
    """Tests for SettingsService.set_tenant_setting (Organization settings)."""

    async def test_upserts_via_repository(
        self, service: SettingsService, org_settings_repo: MagicMock
    ) -> None:
        """set_tenant_setting persists the key-value pair via the repository."""
        await service.set_tenant_setting("org_test", "theme", "light")

        org_settings_repo.upsert.assert_awaited_once_with(
            org_id="org_test",
            key="theme",
            value="light",
        )

    async def test_completes_without_redis(
        self, service: SettingsService, org_settings_repo: MagicMock
    ) -> None:
        """set_tenant_setting completes normally — no Redis dependency."""
        await service.set_tenant_setting("org_test", "theme", "dark")

        org_settings_repo.upsert.assert_awaited_once()


class TestListTenantSettings:
    """Tests for SettingsService.list_tenant_settings (Organization settings)."""

    async def test_returns_key_value_dict_from_settings_list(
        self, service: SettingsService, org_settings_repo: MagicMock
    ) -> None:
        """list_tenant_settings converts the repository list of records to a dict."""

        def _make_setting(key, value):
            m = MagicMock()
            m.key = key
            m.value = value
            return m

        org_settings_repo.get_all_for_org.return_value = [
            _make_setting("theme", "dark"),
            _make_setting("language", "en"),
        ]

        result = await service.list_tenant_settings("org_test")

        assert result == {"theme": "dark", "language": "en"}

    async def test_returns_empty_dict_when_no_settings_stored(
        self, service: SettingsService, org_settings_repo: MagicMock
    ) -> None:
        """list_tenant_settings returns an empty dict when the org has no settings."""
        org_settings_repo.get_all_for_org.return_value = []

        result = await service.list_tenant_settings("org_test")

        assert result == {}


class TestDeleteTenantSetting:
    """Tests for SettingsService.delete_tenant_setting (Organization settings)."""

    async def test_delegates_to_repository(
        self, service: SettingsService, org_settings_repo: MagicMock
    ) -> None:
        """delete_tenant_setting forwards org_id and key to the repository."""
        await service.delete_tenant_setting("org_test", "theme")

        org_settings_repo.delete.assert_awaited_once_with("org_test", "theme")

    async def test_completes_without_redis(self, service: SettingsService) -> None:
        """delete_tenant_setting completes normally — no Redis dependency."""
        await service.delete_tenant_setting("org_test", "theme")


# ---------------------------------------------------------------------------
# Instance Config
# ---------------------------------------------------------------------------


class TestCreateInstance:
    """Tests for SettingsService.create_instance (Tier 4)."""

    async def test_passes_framework_type_and_mode_to_repo(
        self, service: SettingsService, instance_repo: MagicMock
    ) -> None:
        """create_instance forwards framework_type and mode as explicit column values."""
        await service.create_instance(
            org_id="org_test",
            framework_type="langgraph",
            mode="coordinator",
            instance_config={"name": "My Bot"},
        )

        call_kwargs = instance_repo.create.call_args.kwargs
        assert call_kwargs["framework_type"] == "langgraph"
        assert call_kwargs["mode"] == "coordinator"

    async def test_strips_immutable_fields_from_jsonb_config(
        self, service: SettingsService, instance_repo: MagicMock
    ) -> None:
        """create_instance removes framework_type, mode, instance_id, org_id, status from JSONB."""
        dirty_config = {
            "name": "My Bot",
            "framework_type": "langgraph",
            "mode": "supervisor",
            "instance_id": "inst_new",
            "org_id": "org_test",
            "status": "active",
            "temperature": 0.7,
        }

        await service.create_instance(
            org_id="org_test",
            framework_type="langgraph",
            mode="supervisor",
            instance_config=dirty_config,
        )

        stored_config = instance_repo.create.call_args.kwargs["config"]
        for forbidden in ("framework_type", "mode", "instance_id", "org_id", "status"):
            assert forbidden not in stored_config
        assert stored_config["temperature"] == 0.7

    async def test_defaults_name_to_empty_string_when_absent(
        self, service: SettingsService, instance_repo: MagicMock
    ) -> None:
        """create_instance uses empty string for name when config has no name key."""
        await service.create_instance("org_test", "langgraph", "supervisor", {})

        assert instance_repo.create.call_args.kwargs["name"] == ""

    async def test_passes_tier_to_repo(
        self, service: SettingsService, instance_repo: MagicMock
    ) -> None:
        """create_instance forwards the tier to the repository."""
        await service.create_instance(
            org_id="org_test",
            framework_type="langgraph",
            mode="supervisor",
            instance_config={"name": "My Bot"},
            tier="hot",
        )

        assert instance_repo.create.call_args.kwargs["tier"] == "hot"

    async def test_defaults_tier_to_cold(
        self, service: SettingsService, instance_repo: MagicMock
    ) -> None:
        """create_instance defaults tier to 'cold' when not specified."""
        await service.create_instance("org_test", "langgraph", "supervisor", {})

        assert instance_repo.create.call_args.kwargs["tier"] == "cold"

    async def test_passes_plugin_settings_and_config_hash(
        self, service: SettingsService, instance_repo: MagicMock
    ) -> None:
        """create_instance forwards plugin_settings and config_hash to the repository."""
        ps = {"com.example.search": {"api_key": "abc"}}
        ch = "deadbeef12345678"

        await service.create_instance(
            org_id="org_test",
            framework_type="langgraph",
            mode="supervisor",
            instance_config={"name": "Bot"},
            plugin_settings=ps,
            config_hash=ch,
        )

        call_kwargs = instance_repo.create.call_args.kwargs
        assert call_kwargs["plugin_settings"] == ps
        assert call_kwargs["config_hash"] == ch

    async def test_returns_created_instance(
        self, service: SettingsService, instance_repo: MagicMock
    ) -> None:
        """create_instance returns the record produced by the repository."""
        expected = {
            "instance_id": "inst_new",
            "org_id": "org_test",
            "framework_type": "langgraph",
            "mode": "supervisor",
            "tier": "cold",
            "plugin_settings": {},
            "config_hash": None,
        }
        instance_repo.create.return_value = expected

        result = await service.create_instance(
            "org_test", "langgraph", "supervisor", {}
        )

        assert result is expected


class TestListInstancesForOrg:
    """Tests for SettingsService.list_instances_for_org (Tier 4)."""

    async def test_delegates_to_repository(
        self, service: SettingsService, instance_repo: MagicMock
    ) -> None:
        """list_instances_for_org passes org_id to the repository list method."""
        await service.list_instances_for_org("org_test")

        instance_repo.list_for_org.assert_awaited_once_with("org_test")

    async def test_returns_repository_result(
        self, service: SettingsService, instance_repo: MagicMock
    ) -> None:
        """list_instances_for_org returns whatever the repository provides."""
        instance_repo.list_for_org.return_value = [
            {"instance_id": "i1"},
            {"instance_id": "i2"},
        ]

        result = await service.list_instances_for_org("org_test")

        assert len(result) == 2


class TestGetInstanceConfig:
    """Tests for SettingsService.get_instance_config (Tier 4)."""

    async def test_returns_instance_data_when_found(
        self, service: SettingsService, instance_repo: MagicMock
    ) -> None:
        """get_instance_config returns the instance record from the repository."""
        result = await service.get_instance_config("inst_test")

        assert result["instance_id"] == "inst_test"

    async def test_returns_none_when_instance_absent(
        self, service: SettingsService, instance_repo: MagicMock
    ) -> None:
        """get_instance_config returns None when the instance does not exist."""
        instance_repo.get_by_id.return_value = None

        result = await service.get_instance_config("missing_inst")

        assert result is None


class TestDeleteInstance:
    """Tests for SettingsService.delete_instance (Tier 4) — soft-delete."""

    async def test_soft_deletes_by_setting_status_to_deleted(
        self,
        service: SettingsService,
        instance_repo: MagicMock,
    ) -> None:
        """delete_instance calls update_status('deleted') — never hard-deletes."""
        await service.delete_instance("inst_test")

        instance_repo.update_status.assert_awaited_once_with(
            "inst_test", "is_deleted", caller_id=None
        )
        instance_repo.delete.assert_not_awaited()

    async def test_evicts_from_pool_when_pool_present(
        self,
        service: SettingsService,
        orchestrator_pool: MagicMock,
    ) -> None:
        """delete_instance evicts the instance from the pool before marking deleted."""
        await service.delete_instance("inst_test")

        orchestrator_pool.remove_instance.assert_awaited_once_with("inst_test")

    async def test_skips_pool_removal_when_pool_is_absent(
        self, service_minimal: SettingsService, instance_repo: MagicMock
    ) -> None:
        """delete_instance soft-deletes even when pool is not configured."""
        await service_minimal.delete_instance("inst_test")

        instance_repo.update_status.assert_awaited_once_with(
            "inst_test", "is_deleted", caller_id=None
        )


class TestUpdateInstanceStatus:
    """Tests for SettingsService.update_instance_status (Tier 4)."""

    async def test_updates_status_via_repository(
        self, service: SettingsService, instance_repo: MagicMock
    ) -> None:
        """update_instance_status writes the new status to the repository."""
        await service.update_instance_status("inst_test", "suspended")

        instance_repo.update_status.assert_awaited_once_with(
            "inst_test", "suspended", caller_id=None
        )

    async def test_returns_updated_instance_from_repository(
        self, service: SettingsService, instance_repo: MagicMock
    ) -> None:
        """update_instance_status returns the refreshed instance dict."""
        updated = {"instance_id": "inst_test", "status": "suspended"}
        instance_repo.get_by_id.return_value = updated

        result = await service.update_instance_status("inst_test", "suspended")

        assert result["status"] == "suspended"

    async def test_evicts_from_pool_on_soft_delete(
        self,
        service: SettingsService,
        orchestrator_pool: MagicMock,
    ) -> None:
        """update_instance_status evicts instance from pool when status='deleted'."""
        await service.update_instance_status("inst_test", "is_deleted")

        orchestrator_pool.remove_instance.assert_awaited_once_with("inst_test")

    async def test_does_not_evict_pool_for_non_delete_status(
        self,
        service: SettingsService,
        orchestrator_pool: MagicMock,
    ) -> None:
        """update_instance_status does NOT touch the pool for active/suspended transitions."""
        await service.update_instance_status("inst_test", "suspended")

        orchestrator_pool.remove_instance.assert_not_awaited()


class TestUpdateInstanceConfig:
    """Tests for SettingsService.update_instance_config (Tier 4)."""

    async def test_updates_config_in_repository(
        self, service: SettingsService, instance_repo: MagicMock
    ) -> None:
        """update_instance_config writes the new config to the repository."""
        await service.update_instance_config(
            "inst_test", {"temperature": 0.8}, trigger_reload=False
        )

        instance_repo.update_config.assert_awaited_once_with(
            "inst_test", {"temperature": 0.8}, caller_id=None
        )

    async def test_triggers_pool_reload_when_enabled(
        self,
        service: SettingsService,
        instance_repo: MagicMock,
        orchestrator_pool: MagicMock,
    ) -> None:
        """update_instance_config triggers a pool hot-reload when trigger_reload=True."""
        await service.update_instance_config(
            "inst_test", {"temperature": 0.8}, trigger_reload=True
        )

        orchestrator_pool.reload_instance.assert_awaited_once()

    async def test_skips_pool_reload_when_disabled(
        self,
        service: SettingsService,
        instance_repo: MagicMock,
        orchestrator_pool: MagicMock,
    ) -> None:
        """update_instance_config does not reload the pool when trigger_reload=False."""
        await service.update_instance_config("inst_test", {}, trigger_reload=False)

        orchestrator_pool.reload_instance.assert_not_awaited()

    async def test_returns_updated_instance_from_repository(
        self, service: SettingsService, instance_repo: MagicMock
    ) -> None:
        """update_instance_config returns the refreshed instance record after the update."""
        updated_instance = {"instance_id": "inst_test", "config": {"temperature": 0.9}}
        instance_repo.get_by_id.return_value = updated_instance

        result = await service.update_instance_config(
            "inst_test", {}, trigger_reload=False
        )

        assert result["config"]["temperature"] == 0.9

    async def test_raises_value_error_when_framework_type_in_new_config(
        self, service: SettingsService
    ) -> None:
        """update_instance_config raises ValueError when framework_type is in the update."""
        with pytest.raises(ValueError, match="framework_type"):
            await service.update_instance_config(
                "inst_test", {"framework_type": "openai_agents"}, trigger_reload=False
            )

    async def test_raises_value_error_when_mode_in_new_config(
        self, service: SettingsService
    ) -> None:
        """update_instance_config raises ValueError when mode is in the update."""
        with pytest.raises(ValueError, match="mode"):
            await service.update_instance_config(
                "inst_test", {"mode": "handoff"}, trigger_reload=False
            )

    async def test_allows_mutable_fields_through(
        self, service: SettingsService, instance_repo: MagicMock
    ) -> None:
        """update_instance_config accepts updates that do not contain immutable fields."""
        await service.update_instance_config(
            "inst_test", {"temperature": 0.5}, trigger_reload=False
        )

        instance_repo.update_config.assert_awaited_once_with(
            "inst_test", {"temperature": 0.5}, caller_id=None
        )
