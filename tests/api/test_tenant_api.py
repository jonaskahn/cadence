"""API tests for the tenant controller.

Verifies organization management endpoints (sys_admin-only) at /api/admin/orgs,
Tier 3 settings endpoints at /api/orgs/{org_id}/settings, BYOK LLM configuration
endpoints at /api/orgs/{org_id}/llm-configs, and user management at /api/orgs/{org_id}/users.

Authentication is bypassed via the conftest dependency override (sys_admin role by default).
"""

from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

ADMIN_TENANTS_URL = "/api/admin/orgs"
ADMIN_USERS_URL = "/api/admin/users"
TENANT_SETTINGS_URL = "/api/orgs/org_test/settings"
TENANT_LLM_CONFIGS_URL = "/api/orgs/org_test/llm-configs"
TENANT_USERS_URL = "/api/orgs/org_test/users"


# ---------------------------------------------------------------------------
# Organization management (admin-only)
# ---------------------------------------------------------------------------


class TestCreateOrgEndpoint:
    """Tests for POST /api/admin/orgs."""

    def test_returns_201_for_valid_payload(self, client: TestClient) -> None:
        """POST /api/admin/orgs returns HTTP 201 Created when name is provided."""
        response = client.post(ADMIN_TENANTS_URL, json={"name": "New Org"})

        assert response.status_code == 201

    def test_response_contains_org_id(self, client: TestClient) -> None:
        """POST /api/admin/orgs response body includes org_id of the created organization."""
        response = client.post(ADMIN_TENANTS_URL, json={"name": "New Org"})

        assert "org_id" in response.json()

    def test_response_does_not_contain_framework_type(self, client: TestClient) -> None:
        """POST /api/admin/orgs response body does not include framework_type."""
        response = client.post(ADMIN_TENANTS_URL, json={"name": "New Org"})

        assert "framework_type" not in response.json()

    def test_returns_422_when_name_is_empty_string(self, client: TestClient) -> None:
        """POST /api/admin/orgs returns HTTP 422 when name violates the min_length constraint."""
        response = client.post(ADMIN_TENANTS_URL, json={"name": ""})

        assert response.status_code == 422

    def test_delegates_to_tenant_service(
        self, client: TestClient, mock_tenant_service: MagicMock
    ) -> None:
        """POST /api/admin/orgs calls TenantService.create_org exactly once."""
        client.post(ADMIN_TENANTS_URL, json={"name": "Org"})

        mock_tenant_service.create_org.assert_awaited_once()


class TestListOrgsEndpoint:
    """Tests for GET /api/admin/orgs."""

    def test_returns_200(self, client: TestClient) -> None:
        """GET /api/admin/orgs returns HTTP 200."""
        response = client.get(ADMIN_TENANTS_URL)

        assert response.status_code == 200

    def test_response_is_a_list(self, client: TestClient) -> None:
        """GET /api/admin/orgs response body is a JSON array."""
        response = client.get(ADMIN_TENANTS_URL)

        assert isinstance(response.json(), list)

    def test_delegates_to_tenant_service(
        self, client: TestClient, mock_tenant_service: MagicMock
    ) -> None:
        """GET /api/admin/orgs calls TenantService.list_orgs exactly once."""
        client.get(ADMIN_TENANTS_URL)

        mock_tenant_service.list_orgs.assert_awaited_once()


class TestUpdateOrgEndpoint:
    """Tests for PATCH /api/admin/orgs/{org_id}."""

    def test_returns_200_with_valid_update(self, client: TestClient) -> None:
        """PATCH /api/admin/orgs/{org_id} returns HTTP 200 when the update is valid."""
        response = client.patch(
            f"{ADMIN_TENANTS_URL}/org_test", json={"name": "New Name"}
        )

        assert response.status_code == 200

    def test_response_contains_org_id(self, client: TestClient) -> None:
        """PATCH /api/admin/orgs/{org_id} response body includes the org_id field."""
        response = client.patch(f"{ADMIN_TENANTS_URL}/org_test", json={"name": "N"})

        assert "org_id" in response.json()

    def test_delegates_to_tenant_service(
        self, client: TestClient, mock_tenant_service: MagicMock
    ) -> None:
        """PATCH /api/admin/orgs/{org_id} calls TenantService.update_org exactly once."""
        client.patch(f"{ADMIN_TENANTS_URL}/org_test", json={"name": "N"})

        mock_tenant_service.update_org.assert_awaited_once()


# ---------------------------------------------------------------------------
# Tenant settings (Tier 3)
# ---------------------------------------------------------------------------


class TestTenantSettingsEndpoints:
    """Tests for tenant-level Tier 3 settings endpoints at /api/orgs/{org_id}/settings."""

    def test_set_tenant_setting_returns_201(self, client: TestClient) -> None:
        """POST /api/orgs/org_test/settings returns HTTP 201 Created on success."""
        payload = {"key": "theme", "value": "dark"}

        response = client.post(TENANT_SETTINGS_URL, json=payload)

        assert response.status_code == 201

    def test_set_tenant_setting_response_contains_key(self, client: TestClient) -> None:
        """POST /api/orgs/org_test/settings response body includes the setting key."""
        payload = {"key": "theme", "value": "dark"}

        response = client.post(TENANT_SETTINGS_URL, json=payload)

        assert "key" in response.json()

    def test_list_tenant_settings_returns_200(self, client: TestClient) -> None:
        """GET /api/orgs/org_test/settings returns HTTP 200."""
        response = client.get(TENANT_SETTINGS_URL)

        assert response.status_code == 200

    def test_list_tenant_settings_response_is_list(self, client: TestClient) -> None:
        """GET /api/orgs/org_test/settings response body is a JSON array."""
        response = client.get(TENANT_SETTINGS_URL)

        assert isinstance(response.json(), list)

    def test_list_tenant_settings_contains_settings(self, client: TestClient) -> None:
        """GET /api/orgs/org_test/settings returns at least one setting from the mock."""
        response = client.get(TENANT_SETTINGS_URL)

        assert len(response.json()) >= 1

    def test_set_setting_delegates_to_tenant_service(
        self, client: TestClient, mock_tenant_service: MagicMock
    ) -> None:
        """POST /api/orgs/org_test/settings calls TenantService.set_setting exactly once."""
        client.post(TENANT_SETTINGS_URL, json={"key": "theme", "value": "light"})

        mock_tenant_service.set_setting.assert_awaited_once()

    def test_list_settings_delegates_to_tenant_service(
        self, client: TestClient, mock_tenant_service: MagicMock
    ) -> None:
        """GET /api/orgs/org_test/settings calls TenantService.list_settings exactly once."""
        client.get(TENANT_SETTINGS_URL)

        mock_tenant_service.list_settings.assert_awaited_once()


# ---------------------------------------------------------------------------
# LLM configuration (BYOK)
# ---------------------------------------------------------------------------


class TestLLMConfigEndpoints:
    """Tests for BYOK LLM configuration endpoints at /api/orgs/{org_id}/llm-configs.

    All requests use org_admin_client because sys_admin is excluded from
    LLM config endpoints by design (require_org_admin_only).
    """

    def test_sys_admin_receives_403_on_llm_config_list(self, app: FastAPI) -> None:
        """GET /api/orgs/org_test/llm-configs returns 403 for sys_admin without org membership."""
        import cadence.middleware.authorization_middleware as perms
        from cadence.middleware.tenant_context_middleware import TenantContext

        sys_admin_no_org_ctx = TenantContext(
            user_id="sys_1",
            org_id="org_test",
            is_sys_admin=True,
            is_org_admin=False,
        )

        def override() -> TenantContext:
            return sys_admin_no_org_ctx

        app.dependency_overrides[perms.require_org_admin_access] = override
        sys_only_client = TestClient(app)

        response = sys_only_client.get(TENANT_LLM_CONFIGS_URL)

        assert response.status_code == 403

    def test_sys_admin_receives_403_on_add_llm_config(self, app: FastAPI) -> None:
        """POST /api/orgs/org_test/llm-configs returns 403 for sys_admin without org membership."""
        import cadence.middleware.authorization_middleware as perms
        from cadence.middleware.tenant_context_middleware import TenantContext

        sys_admin_no_org_ctx = TenantContext(
            user_id="sys_1",
            org_id="org_test",
            is_sys_admin=True,
            is_org_admin=False,
        )

        def override() -> TenantContext:
            return sys_admin_no_org_ctx

        app.dependency_overrides[perms.require_org_admin_access] = override
        sys_only_client = TestClient(app)

        payload = {"name": "p", "provider": "openai", "api_key": "sk-x"}
        response = sys_only_client.post(TENANT_LLM_CONFIGS_URL, json=payload)

        assert response.status_code == 403

    def test_add_llm_config_returns_201(self, org_admin_client: TestClient) -> None:
        """POST /api/orgs/org_test/llm-configs returns HTTP 201 for org_admin."""
        payload = {
            "name": "production",
            "provider": "openai",
            "api_key": "sk-secret",
            "base_url": None,
        }

        response = org_admin_client.post(TENANT_LLM_CONFIGS_URL, json=payload)

        assert response.status_code == 201

    def test_add_llm_config_response_contains_id(
        self, org_admin_client: TestClient
    ) -> None:
        """POST /api/orgs/org_test/llm-configs response body includes the config id."""
        payload = {"name": "p", "provider": "openai", "api_key": "sk-x"}

        response = org_admin_client.post(TENANT_LLM_CONFIGS_URL, json=payload)

        assert "id" in response.json()

    def test_add_llm_config_with_additional_config(
        self, org_admin_client: TestClient
    ) -> None:
        """POST /api/orgs/org_test/llm-configs accepts additional_config field."""
        payload = {
            "name": "azure_primary",
            "provider": "azure",
            "api_key": "sk-x",
            "additional_config": {"api_version": "2024-02-01", "deployment_id": "gpt4"},
        }

        response = org_admin_client.post(TENANT_LLM_CONFIGS_URL, json=payload)

        assert response.status_code == 201

    def test_list_llm_configs_returns_200(self, org_admin_client: TestClient) -> None:
        """GET /api/orgs/org_test/llm-configs returns HTTP 200 for org_admin."""
        response = org_admin_client.get(TENANT_LLM_CONFIGS_URL)

        assert response.status_code == 200

    def test_list_llm_configs_response_is_list(
        self, org_admin_client: TestClient
    ) -> None:
        """GET /api/orgs/org_test/llm-configs response body is a JSON array."""
        response = org_admin_client.get(TENANT_LLM_CONFIGS_URL)

        assert isinstance(response.json(), list)

    def test_delete_llm_config_returns_204(self, org_admin_client: TestClient) -> None:
        """DELETE /api/orgs/org_test/llm-configs/{name} returns HTTP 204 when deleted."""
        response = org_admin_client.delete(f"{TENANT_LLM_CONFIGS_URL}/production")

        assert response.status_code == 204

    def test_delete_llm_config_returns_404_when_not_found(
        self, org_admin_client: TestClient, mock_tenant_service: MagicMock
    ) -> None:
        """DELETE /api/orgs/org_test/llm-configs/{name} returns 404 when config does not exist."""
        mock_tenant_service.delete_llm_config.return_value = False

        response = org_admin_client.delete(f"{TENANT_LLM_CONFIGS_URL}/missing")

        assert response.status_code == 404

    def test_delete_llm_config_returns_409_when_in_use(
        self, org_admin_client: TestClient, mock_tenant_service: MagicMock
    ) -> None:
        """DELETE /api/orgs/org_test/llm-configs/{name} returns 409 when config is in use."""
        mock_tenant_service.delete_llm_config.side_effect = ValueError(
            "LLM config 'production' is still referenced by 1 active orchestrator instance(s)."
        )

        response = org_admin_client.delete(f"{TENANT_LLM_CONFIGS_URL}/production")

        assert response.status_code == 409

    def test_add_llm_config_delegates_to_tenant_service(
        self, org_admin_client: TestClient, mock_tenant_service: MagicMock
    ) -> None:
        """POST /api/orgs/org_test/llm-configs calls TenantService.add_llm_config exactly once."""
        payload = {"name": "p", "provider": "openai", "api_key": "sk-x"}

        org_admin_client.post(TENANT_LLM_CONFIGS_URL, json=payload)

        mock_tenant_service.add_llm_config.assert_awaited_once()


# ---------------------------------------------------------------------------
# Role-based access control for tenant endpoints
# ---------------------------------------------------------------------------


class TestTenantRoleEnforcement:
    """Tests that org-level endpoints reject users with 'user' role."""

    def test_user_role_receives_403_on_tenant_settings_get(self, app: FastAPI) -> None:
        """GET /api/orgs/org_test/settings returns HTTP 403 for a non-admin user."""
        from fastapi import HTTPException, status

        import cadence.middleware.authorization_middleware as perms

        def override_raises_403():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization admin access required",
            )

        app.dependency_overrides[perms.require_org_admin_access] = override_raises_403
        restricted_client = TestClient(app)

        response = restricted_client.get(TENANT_SETTINGS_URL)

        assert response.status_code == 403

    def test_user_role_receives_403_on_tenant_settings_post(self, app: FastAPI) -> None:
        """POST /api/orgs/org_test/settings returns HTTP 403 for a non-admin user."""
        from fastapi import HTTPException, status

        import cadence.middleware.authorization_middleware as perms

        def override_raises_403():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization admin access required",
            )

        app.dependency_overrides[perms.require_org_admin_access] = override_raises_403
        restricted_client = TestClient(app)

        response = restricted_client.post(
            TENANT_SETTINGS_URL, json={"key": "k", "value": "v"}
        )

        assert response.status_code == 403

    def test_org_admin_receives_200_on_tenant_settings_get(self, app: FastAPI) -> None:
        """GET /api/orgs/org_test/settings returns HTTP 200 for a user with is_org_admin."""
        import cadence.middleware.authorization_middleware as perms
        from cadence.middleware.tenant_context_middleware import TenantContext

        org_admin_ctx = TenantContext(
            user_id="admin_1",
            org_id="org_test",
            is_sys_admin=False,
            is_org_admin=True,
        )

        def override() -> TenantContext:
            return org_admin_ctx

        app.dependency_overrides[perms.require_org_admin_access] = override
        org_admin_client = TestClient(app)

        response = org_admin_client.get(TENANT_SETTINGS_URL)

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# User management endpoints
# ---------------------------------------------------------------------------


class TestUserManagementEndpoints:
    """Tests for /api/orgs/{org_id}/users CRUD endpoints."""

    def test_create_user_returns_201(self, client: TestClient) -> None:
        """POST /api/admin/users returns HTTP 201 on success (sys_admin only)."""
        payload = {"username": "newuser", "email": "new@example.com"}

        response = client.post(ADMIN_USERS_URL, json=payload)

        assert response.status_code == 201

    def test_create_user_response_contains_user_id(self, client: TestClient) -> None:
        """POST /api/admin/users response body includes user_id."""
        payload = {"username": "newuser", "email": "new@example.com"}

        response = client.post(ADMIN_USERS_URL, json=payload)

        assert "user_id" in response.json()

    def test_create_user_delegates_to_tenant_service(
        self, client: TestClient, mock_tenant_service: MagicMock
    ) -> None:
        """POST /api/admin/users calls TenantService.create_user exactly once."""
        payload = {"username": "newuser", "email": "new@example.com"}

        client.post(ADMIN_USERS_URL, json=payload)

        mock_tenant_service.create_user.assert_awaited_once()

    def test_list_users_returns_200(self, client: TestClient) -> None:
        """GET /api/orgs/org_test/users returns HTTP 200."""
        response = client.get(TENANT_USERS_URL)

        assert response.status_code == 200

    def test_list_users_response_is_list(self, client: TestClient) -> None:
        """GET /api/orgs/org_test/users response body is a JSON array."""
        response = client.get(TENANT_USERS_URL)

        assert isinstance(response.json(), list)

    def test_list_users_delegates_to_tenant_service(
        self, client: TestClient, mock_tenant_service: MagicMock
    ) -> None:
        """GET /api/orgs/org_test/users calls TenantService.list_org_members exactly once."""
        client.get(TENANT_USERS_URL)

        mock_tenant_service.list_org_members.assert_awaited_once()

    def test_update_user_membership_returns_200(self, client: TestClient) -> None:
        """PATCH /api/orgs/org_test/users/{user_id}/membership returns HTTP 200 on success."""
        response = client.patch(
            f"{TENANT_USERS_URL}/user_1/membership", json={"is_admin": True}
        )

        assert response.status_code == 200

    def test_update_user_membership_delegates_to_tenant_service(
        self, client: TestClient, mock_tenant_service: MagicMock
    ) -> None:
        """PATCH /api/orgs/org_test/users/{user_id}/membership calls TenantService.update_org_membership."""
        client.patch(f"{TENANT_USERS_URL}/user_1/membership", json={"is_admin": True})

        mock_tenant_service.update_org_membership.assert_awaited_once()

    def test_delete_user_returns_204(self, client: TestClient) -> None:
        """DELETE /api/orgs/org_test/users/{user_id} removes user from org and returns HTTP 204."""
        response = client.delete(f"{TENANT_USERS_URL}/user_1")

        assert response.status_code == 204

    def test_delete_user_delegates_to_tenant_service(
        self, client: TestClient, mock_tenant_service: MagicMock
    ) -> None:
        """DELETE /api/orgs/org_test/users/{user_id} calls TenantService.remove_user_from_org exactly once."""
        client.delete(f"{TENANT_USERS_URL}/user_1")

        mock_tenant_service.remove_user_from_org.assert_awaited_once()

    def test_delete_user_returns_404_when_not_found(
        self, client: TestClient, mock_tenant_service: MagicMock
    ) -> None:
        """DELETE /api/orgs/org_test/users/{user_id} returns 404 when user is not a member."""
        mock_tenant_service.remove_user_from_org.return_value = False

        response = client.delete(f"{TENANT_USERS_URL}/missing_user")

        assert response.status_code == 404

    def test_non_admin_cannot_update_membership(self, app: FastAPI) -> None:
        """PATCH /api/orgs/org_test/users/{user_id}/membership returns 403 for a non-admin user."""
        from fastapi import HTTPException, status

        import cadence.middleware.authorization_middleware as perms

        def override_raises_403():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization admin access required",
            )

        app.dependency_overrides[perms.require_org_admin_access] = override_raises_403
        restricted_client = TestClient(app)

        response = restricted_client.patch(
            f"{TENANT_USERS_URL}/user_1/membership", json={"is_admin": True}
        )

        assert response.status_code == 403

    def test_user_role_receives_403_on_list_users(self, app: FastAPI) -> None:
        """GET /api/orgs/org_test/users returns HTTP 403 for a non-admin user."""
        from fastapi import HTTPException, status

        import cadence.middleware.authorization_middleware as perms

        def override_raises_403():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization admin access required",
            )

        app.dependency_overrides[perms.require_org_admin_access] = override_raises_403
        restricted_client = TestClient(app)

        response = restricted_client.get(TENANT_USERS_URL)

        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Soft-deleted user masking
# ---------------------------------------------------------------------------


class TestDeletedUserMasking:
    """Tests for org member listing — deleted users are excluded entirely.

    Memberships are hard-deleted, so soft-deleted user accounts are filtered
    out by the service layer and never appear in the org member list.
    """

    def test_list_returns_only_active_members(
        self, client: TestClient, mock_tenant_service: MagicMock
    ) -> None:
        """list_org_members returns only active (non-deleted) users."""
        mock_tenant_service.list_org_members.return_value = [
            {
                "user_id": "u_active",
                "username": "activeuser",
                "email": "active@example.com",
                "is_sys_admin": False,
                "is_admin": False,
                "is_deleted": False,
                "created_at": "2026-01-01T00:00:00Z",
            }
        ]

        response = client.get(TENANT_USERS_URL)

        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["username"] == "activeuser"

    def test_empty_list_when_no_active_members(
        self, client: TestClient, mock_tenant_service: MagicMock
    ) -> None:
        """list_org_members returns empty list when no active members exist."""
        mock_tenant_service.list_org_members.return_value = []

        response = client.get(TENANT_USERS_URL)

        assert response.status_code == 200
        assert response.json() == []

    def test_active_user_never_masked(
        self, app: FastAPI, mock_tenant_service: MagicMock
    ) -> None:
        """Non-deleted users always appear with full data regardless of caller role."""
        import cadence.middleware.authorization_middleware as perms
        from cadence.middleware.tenant_context_middleware import TenantContext

        mock_tenant_service.list_org_members.return_value = [
            {
                "user_id": "u_active",
                "username": "activeuser",
                "email": "active@example.com",
                "is_sys_admin": False,
                "is_admin": False,
                "is_deleted": False,
                "created_at": "2026-01-01T00:00:00Z",
            }
        ]

        org_admin_ctx = TenantContext(
            user_id="admin_1",
            org_id="org_test",
            is_sys_admin=False,
            is_org_admin=True,
        )

        def override() -> TenantContext:
            return org_admin_ctx

        app.dependency_overrides[perms.require_org_admin_access] = override
        org_admin_client = TestClient(app)

        response = org_admin_client.get(TENANT_USERS_URL)

        assert response.status_code == 200
        body = response.json()[0]
        assert body["username"] == "activeuser"
        assert body["email"] == "active@example.com"
