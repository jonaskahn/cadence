"""Unit tests for TenantService.

Verifies organization CRUD, Tier 3 settings management, and LLM configuration
(BYOK) including API key masking. Organizations are framework-agnostic;
framework_type lives on orchestrator instances, not orgs.
Each test class maps to one public method of TenantService.
"""

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest

from cadence.service.tenant_service import TenantService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def service(
    org_repo: MagicMock,
    org_settings_repo: MagicMock,
    org_llm_config_repo: MagicMock,
) -> TenantService:
    """Provide a TenantService with all repositories mocked."""
    return TenantService(
        org_repo=org_repo,
        org_settings_repo=org_settings_repo,
        org_llm_config_repo=org_llm_config_repo,
    )


# ---------------------------------------------------------------------------
# Organization CRUD
# ---------------------------------------------------------------------------


class TestCreateOrg:
    """Tests for TenantService.create_org."""

    async def test_delegates_to_repo_with_org_id_and_name(
        self, service: TenantService, org_repo: MagicMock
    ) -> None:
        """create_org forwards org_id and name to the repository (no framework_type)."""
        await service.create_org(org_id="org_new", name="New Org")

        org_repo.create.assert_awaited_once_with(
            org_id="org_new", name="New Org", caller_id=None
        )

    async def test_does_not_pass_framework_type(
        self, service: TenantService, org_repo: MagicMock
    ) -> None:
        """create_org does not pass framework_type to the repository."""
        await service.create_org(org_id="org_x", name="Org X")

        call_kwargs = org_repo.create.call_args.kwargs
        assert "framework_type" not in call_kwargs

    async def test_returns_repository_result(
        self, service: TenantService, org_repo: MagicMock
    ) -> None:
        """create_org converts the ORM result to a dict and returns it."""
        from tests.conftest import make_mock_org

        org_mock = make_mock_org(org_id="new", name="My Org")
        org_repo.create.return_value = org_mock

        result = await service.create_org("new", "My Org")

        assert result["org_id"] == "new"
        assert result["name"] == "My Org"


class TestGetOrg:
    """Tests for TenantService.get_org."""

    async def test_returns_org_when_found(
        self, service: TenantService, org_repo: MagicMock
    ) -> None:
        """get_org returns the organization when it exists in the repository."""
        result = await service.get_org("org_test")

        org_repo.get_by_id.assert_awaited_once_with("org_test")
        assert result["org_id"] == "org_test"

    async def test_returns_none_when_org_not_found(
        self, service: TenantService, org_repo: MagicMock
    ) -> None:
        """get_org returns None for a non-existent organization ID."""
        org_repo.get_by_id.return_value = None

        result = await service.get_org("org_missing")

        assert result is None

    async def test_passes_org_id_to_repository(
        self, service: TenantService, org_repo: MagicMock
    ) -> None:
        """get_org forwards the provided org_id to the repository lookup."""
        await service.get_org("org_xyz")

        org_repo.get_by_id.assert_awaited_once_with("org_xyz")


class TestListOrgs:
    """Tests for TenantService.list_orgs."""

    async def test_returns_all_organizations(
        self, service: TenantService, org_repo: MagicMock
    ) -> None:
        """list_orgs returns every organization from the repository."""
        from tests.conftest import make_mock_org

        org_repo.get_all.return_value = [
            make_mock_org(org_id="org_1", name="Org 1"),
            make_mock_org(org_id="org_2", name="Org 2"),
        ]

        result = await service.list_orgs()

        assert len(result) == 2
        assert result[0]["org_id"] == "org_1"

    async def test_returns_empty_list_when_no_orgs_exist(
        self, service: TenantService, org_repo: MagicMock
    ) -> None:
        """list_orgs returns an empty list when no organizations are registered."""
        org_repo.get_all.return_value = []

        result = await service.list_orgs()

        assert result == []

    async def test_delegates_to_repository(
        self, service: TenantService, org_repo: MagicMock
    ) -> None:
        """list_orgs delegates to org_repo.get_all with no arguments."""
        await service.list_orgs()

        org_repo.get_all.assert_awaited_once()


class TestUpdateOrg:
    """Tests for TenantService.update_org."""

    async def test_delegates_to_repository(
        self, service: TenantService, org_repo: MagicMock
    ) -> None:
        """update_org forwards org_id and updates dict to the repository."""
        updates: Dict[str, Any] = {"name": "Updated", "status": "suspended"}

        await service.update_org("org_test", updates)

        org_repo.update.assert_awaited_once_with("org_test", updates)

    async def test_returns_updated_organization(
        self, service: TenantService, org_repo: MagicMock
    ) -> None:
        """update_org returns the updated organization converted to dict."""
        from tests.conftest import make_mock_org

        org_repo.update.return_value = make_mock_org(name="Updated")

        result = await service.update_org("org_test", {"name": "Updated"})

        assert result["name"] == "Updated"


class TestDeleteOrg:
    """Tests for TenantService.delete_org."""

    async def test_delegates_to_repository(
        self, service: TenantService, org_repo: MagicMock
    ) -> None:
        """delete_org forwards org_id to the repository delete method."""
        await service.delete_org("org_test")

        org_repo.delete.assert_awaited_once_with("org_test")

    async def test_returns_none(self, service: TenantService) -> None:
        """delete_org has no return value (void operation)."""
        result = await service.delete_org("org_test")

        assert result is None


# ---------------------------------------------------------------------------
# Organization Settings (Tier 3)
# ---------------------------------------------------------------------------


class TestGetSetting:
    """Tests for TenantService.get_setting."""

    async def test_returns_value_from_setting_record(
        self, service: TenantService, org_settings_repo: MagicMock
    ) -> None:
        """get_setting extracts the value field from the setting record."""
        org_settings_repo.get_by_key.return_value = {"key": "theme", "value": "dark"}

        result = await service.get_setting("org_test", "theme")

        assert result == "dark"

    async def test_returns_none_when_setting_absent(
        self, service: TenantService, org_settings_repo: MagicMock
    ) -> None:
        """get_setting returns None when the key has no stored value."""
        org_settings_repo.get_by_key.return_value = None

        result = await service.get_setting("org_test", "missing_key")

        assert result is None

    async def test_passes_org_id_and_key_to_repository(
        self, service: TenantService, org_settings_repo: MagicMock
    ) -> None:
        """get_setting forwards both org_id and key to the repository."""
        await service.get_setting("org_abc", "my_key")

        org_settings_repo.get_by_key.assert_awaited_once_with("org_abc", "my_key")


class TestSetSetting:
    """Tests for TenantService.set_setting."""

    async def test_calls_upsert_with_correct_args(
        self, service: TenantService, org_settings_repo: MagicMock
    ) -> None:
        """set_setting upserts the key-value pair via the repository."""
        mock_setting = MagicMock()
        mock_setting.key = "theme"
        mock_setting.value = "light"
        org_settings_repo.upsert.return_value = mock_setting

        await service.set_setting("org_test", "theme", "light")

        org_settings_repo.upsert.assert_awaited_once_with(
            org_id="org_test",
            key="theme",
            value="light",
            caller_id=None,
        )

    async def test_accepts_complex_value_types(
        self, service: TenantService, org_settings_repo: MagicMock
    ) -> None:
        """set_setting accepts dicts, lists, and other non-primitive values."""
        mock_setting = MagicMock()
        mock_setting.key = "feature_flags"
        mock_setting.value = {"flag_a": True}
        org_settings_repo.upsert.return_value = mock_setting

        result = await service.set_setting(
            "org_test", "feature_flags", {"flag_a": True}
        )

        call_kwargs = org_settings_repo.upsert.call_args.kwargs
        assert call_kwargs["value"] == {"flag_a": True}
        assert result["value_type"] == "object"

    async def test_returns_setting_response(
        self, service: TenantService, org_settings_repo: MagicMock
    ) -> None:
        """set_setting returns key, value, value_type for the created/updated setting."""
        mock_setting = MagicMock()
        mock_setting.key = "k"
        mock_setting.value = "v"
        org_settings_repo.upsert.return_value = mock_setting

        result = await service.set_setting("org_test", "k", "v")

        assert result == {"key": "k", "value": "v", "value_type": "string"}


class TestListSettings:
    """Tests for TenantService.list_settings."""

    async def test_returns_list_of_setting_responses(
        self, service: TenantService, org_settings_repo: MagicMock
    ) -> None:
        """list_settings converts repository records to list of key, value, value_type."""
        org_settings_repo.get_all_for_org.return_value = [
            MagicMock(key="theme", value="dark"),
            MagicMock(key="language", value="en"),
        ]

        result = await service.list_settings("org_test")

        assert result == [
            {"key": "theme", "value": "dark", "value_type": "string"},
            {"key": "language", "value": "en", "value_type": "string"},
        ]

    async def test_returns_empty_list_when_no_settings_stored(
        self, service: TenantService, org_settings_repo: MagicMock
    ) -> None:
        """list_settings returns an empty list when no settings exist for the org."""
        org_settings_repo.get_all_for_org.return_value = []

        result = await service.list_settings("org_test")

        assert result == []

    async def test_delegates_to_repository_with_org_id(
        self, service: TenantService, org_settings_repo: MagicMock
    ) -> None:
        """list_settings passes org_id to the repository."""
        await service.list_settings("org_xyz")

        org_settings_repo.get_all_for_org.assert_awaited_once_with("org_xyz")


class TestDeleteSetting:
    """Tests for TenantService.delete_setting."""

    async def test_delegates_to_repository(
        self, service: TenantService, org_settings_repo: MagicMock
    ) -> None:
        """delete_setting forwards org_id and key to the repository."""
        await service.delete_setting("org_test", "theme")

        org_settings_repo.delete.assert_awaited_once_with("org_test", "theme")

    async def test_returns_none(self, service: TenantService) -> None:
        """delete_setting has no return value (void operation)."""
        result = await service.delete_setting("org_test", "theme")

        assert result is None


# ---------------------------------------------------------------------------
# LLM Configuration (BYOK)
# ---------------------------------------------------------------------------


class TestAddLLMConfig:
    """Tests for TenantService.add_llm_config."""

    async def test_creates_config_with_all_provided_fields(
        self, service: TenantService, org_llm_config_repo: MagicMock
    ) -> None:
        """add_llm_config forwards every argument to the repository create method."""
        await service.add_llm_config(
            org_id="org_test",
            name="production",
            provider="openai",
            api_key="sk-secret",
            base_url="https://api.openai.com",
        )

        org_llm_config_repo.create.assert_awaited_once_with(
            org_id="org_test",
            name="production",
            provider="openai",
            api_key="sk-secret",
            base_url="https://api.openai.com",
            additional_config={},
            caller_id=None,
        )

    async def test_defaults_base_url_to_none(
        self, service: TenantService, org_llm_config_repo: MagicMock
    ) -> None:
        """add_llm_config sets base_url to None when not provided."""
        await service.add_llm_config(
            org_id="org_test", name="config", provider="anthropic", api_key="sk-ant-xxx"
        )

        call_kwargs = org_llm_config_repo.create.call_args.kwargs
        assert call_kwargs["base_url"] is None

    async def test_passes_additional_config(
        self, service: TenantService, org_llm_config_repo: MagicMock
    ) -> None:
        """add_llm_config forwards additional_config to the repository."""
        extra = {"api_version": "2024-02-01"}
        await service.add_llm_config(
            org_id="org_test",
            name="azure",
            provider="azure",
            api_key="sk-x",
            additional_config=extra,
        )

        call_kwargs = org_llm_config_repo.create.call_args.kwargs
        assert call_kwargs["additional_config"] == extra

    async def test_returns_created_config(
        self, service: TenantService, org_llm_config_repo: MagicMock
    ) -> None:
        """add_llm_config returns the record produced by the repository."""
        expected = {"id": "cfg_1", "name": "production", "provider": "openai"}
        org_llm_config_repo.create.return_value = expected

        result = await service.add_llm_config(
            "org_test", "production", "openai", "sk-test"
        )

        assert result is expected


class TestListLLMConfigs:
    """Tests for TenantService.list_llm_configs.

    API key masking is now the controller's responsibility (api_key is not in
    the LLMConfigResponse schema). The service returns raw ORM objects.
    """

    async def test_returns_all_configs_for_org(
        self, service: TenantService, org_llm_config_repo: MagicMock
    ) -> None:
        """list_llm_configs returns every non-deleted config from the repository."""
        org_llm_config_repo.get_all_for_org.return_value = ["cfg1", "cfg2"]

        result = await service.list_llm_configs("org_test")

        assert len(result) == 2

    async def test_delegates_to_repository_with_org_id(
        self, service: TenantService, org_llm_config_repo: MagicMock
    ) -> None:
        """list_llm_configs calls get_all_for_org with include_deleted=False."""
        await service.list_llm_configs("org_test")

        org_llm_config_repo.get_all_for_org.assert_awaited_once_with(
            "org_test", include_deleted=False
        )

    async def test_returns_empty_list_when_no_configs_exist(
        self, service: TenantService, org_llm_config_repo: MagicMock
    ) -> None:
        """list_llm_configs returns an empty list when the org has no LLM configs."""
        org_llm_config_repo.get_all_for_org.return_value = []

        result = await service.list_llm_configs("org_test")

        assert result == []


class TestDeleteLLMConfig:
    """Tests for TenantService.delete_llm_config."""

    async def test_soft_deletes_via_repository(
        self, service: TenantService, org_llm_config_repo: MagicMock
    ) -> None:
        """delete_llm_config calls soft_delete on the repository."""
        org_llm_config_repo.soft_delete = AsyncMock(return_value=True)

        await service.delete_llm_config("org_test", "production")

        org_llm_config_repo.soft_delete.assert_awaited_once_with(
            org_id="org_test", name="production", caller_id=None
        )

    async def test_returns_false_when_not_found(
        self, service: TenantService, org_llm_config_repo: MagicMock
    ) -> None:
        """delete_llm_config returns False when the config does not exist."""
        org_llm_config_repo.soft_delete = AsyncMock(return_value=False)

        result = await service.delete_llm_config("org_test", "missing")

        assert result is False
