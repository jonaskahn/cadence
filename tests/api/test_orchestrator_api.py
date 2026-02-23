"""API tests for the orchestrator controller.

Verifies orchestrator instance CRUD endpoints:
  - POST   /api/orgs/{org_id}/orchestrators               — create instance
  - GET    /api/orgs/{org_id}/orchestrators               — list instances
  - GET    /api/orgs/{org_id}/orchestrators/{id}          — retrieve config
  - PATCH  /api/orgs/{org_id}/orchestrators/{id}/config   — update mutable config
  - PATCH  /api/orgs/{org_id}/orchestrators/{id}/status   — change status
  - DELETE /api/orgs/{org_id}/orchestrators/{id}          — soft-delete

Authentication and tenant context are bypassed via the conftest dependency override.
"""

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

ORCHESTRATORS_URL = "/api/orgs/org_test/orchestrators"

VALID_CREATE_PAYLOAD = {
    "name": "My Bot",
    "framework_type": "langgraph",
    "mode": "supervisor",
    "active_plugin_ids": ["00000000-0000-0000-0000-000000000001"],
}

VALID_UPDATE_PAYLOAD = {
    "config": {"temperature": 0.9},
}


# ---------------------------------------------------------------------------
# POST /api/orchestrators
# ---------------------------------------------------------------------------


class TestCreateOrchestratorEndpoint:
    """Tests for POST /api/orchestrators."""

    def test_returns_201_for_valid_payload(self, client: TestClient) -> None:
        """POST /api/orchestrators returns HTTP 201 Created when all required fields are given."""
        response = client.post(ORCHESTRATORS_URL, json=VALID_CREATE_PAYLOAD)

        assert response.status_code == 201

    def test_response_contains_instance_id(self, client: TestClient) -> None:
        """POST /api/orchestrators response body includes the instance_id."""
        response = client.post(ORCHESTRATORS_URL, json=VALID_CREATE_PAYLOAD)

        assert "instance_id" in response.json()

    def test_response_contains_framework_type_and_mode(
        self, client: TestClient
    ) -> None:
        """POST /api/orchestrators response body includes framework_type and mode."""
        response = client.post(ORCHESTRATORS_URL, json=VALID_CREATE_PAYLOAD)

        body = response.json()
        assert "framework_type" in body
        assert "mode" in body

    def test_delegates_to_settings_service(
        self, client: TestClient, mock_settings_service: MagicMock
    ) -> None:
        """POST /api/orchestrators calls SettingsService.create_orchestrator_instance exactly once."""
        client.post(ORCHESTRATORS_URL, json=VALID_CREATE_PAYLOAD)

        mock_settings_service.create_orchestrator_instance.assert_awaited_once()

    def test_returns_422_when_required_fields_missing(self, client: TestClient) -> None:
        """POST /api/orchestrators returns HTTP 422 when required fields are absent."""
        response = client.post(ORCHESTRATORS_URL, json={"name": "Incomplete"})

        assert response.status_code == 422

    def test_returns_422_when_framework_type_missing(self, client: TestClient) -> None:
        """POST /api/orchestrators returns 422 when framework_type is not provided."""
        payload = {
            k: v for k, v in VALID_CREATE_PAYLOAD.items() if k != "framework_type"
        }

        response = client.post(ORCHESTRATORS_URL, json=payload)

        assert response.status_code == 422

    def test_returns_422_for_invalid_framework_type(self, client: TestClient) -> None:
        """POST /api/orchestrators returns 422 when framework_type value is not in the allowed set."""
        payload = {**VALID_CREATE_PAYLOAD, "framework_type": "unknown_framework"}

        response = client.post(ORCHESTRATORS_URL, json=payload)

        assert response.status_code == 422

    def test_accepts_multiple_plugin_ids(self, client: TestClient) -> None:
        """POST /api/orchestrators accepts multiple plugin UUIDs in active_plugin_ids."""
        payload = {
            **VALID_CREATE_PAYLOAD,
            "active_plugin_ids": [
                "00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000002",
            ],
        }

        response = client.post(ORCHESTRATORS_URL, json=payload)

        assert response.status_code == 201


# ---------------------------------------------------------------------------
# GET /api/orchestrators
# ---------------------------------------------------------------------------


class TestListOrchestratorEndpoint:
    """Tests for GET /api/orchestrators."""

    def test_returns_200(self, client: TestClient) -> None:
        """GET /api/orchestrators returns HTTP 200."""
        response = client.get(ORCHESTRATORS_URL)

        assert response.status_code == 200

    def test_response_is_list(self, client: TestClient) -> None:
        """GET /api/orchestrators response body is a JSON array."""
        response = client.get(ORCHESTRATORS_URL)

        assert isinstance(response.json(), list)

    def test_delegates_to_settings_service(
        self, client: TestClient, mock_settings_service: MagicMock
    ) -> None:
        """GET /api/orchestrators calls SettingsService.list_instances_for_org exactly once."""
        client.get(ORCHESTRATORS_URL)

        mock_settings_service.list_instances_for_org.assert_awaited_once()


# ---------------------------------------------------------------------------
# GET /api/orchestrators/{instance_id}
# ---------------------------------------------------------------------------


class TestGetOrchestratorConfigEndpoint:
    """Tests for GET /api/orchestrators/{instance_id}."""

    def test_returns_200_for_known_instance(self, client: TestClient) -> None:
        """GET /api/orchestrators/{id} returns HTTP 200 when the instance exists."""
        response = client.get(f"{ORCHESTRATORS_URL}/inst_test")

        assert response.status_code == 200

    def test_response_contains_instance_id(self, client: TestClient) -> None:
        """GET /api/orchestrators/{id} response body includes instance_id."""
        response = client.get(f"{ORCHESTRATORS_URL}/inst_test")

        assert "instance_id" in response.json()

    def test_response_contains_framework_type_and_mode(
        self, client: TestClient
    ) -> None:
        """GET /api/orchestrators/{id} response includes framework_type and mode fields."""
        response = client.get(f"{ORCHESTRATORS_URL}/inst_test")

        body = response.json()
        assert "framework_type" in body
        assert "mode" in body

    def test_returns_404_when_instance_not_found(
        self, client: TestClient, mock_settings_service: MagicMock
    ) -> None:
        """GET /api/orchestrators/{id} returns HTTP 404 when the instance does not exist."""
        mock_settings_service.get_instance_config.return_value = None

        response = client.get(f"{ORCHESTRATORS_URL}/missing_inst")

        assert response.status_code == 404

    def test_returns_410_for_deleted_instance(
        self, client: TestClient, mock_settings_service: MagicMock
    ) -> None:
        """GET /api/orchestrators/{id} returns 410 Gone for a soft-deleted instance."""
        mock_settings_service.get_instance_config.return_value = {
            "instance_id": "inst_test",
            "org_id": "org_test",
            "name": "My Bot",
            "framework_type": "langgraph",
            "mode": "supervisor",
            "status": "is_deleted",
            "config": {},
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }

        response = client.get(f"{ORCHESTRATORS_URL}/inst_test")

        assert response.status_code == 410


# ---------------------------------------------------------------------------
# PATCH /api/orchestrators/{instance_id}/config
# ---------------------------------------------------------------------------


class TestUpdateOrchestratorConfigEndpoint:
    """Tests for PATCH /api/orchestrators/{instance_id}/config."""

    def test_returns_200_for_valid_update(self, client: TestClient) -> None:
        """PATCH /api/orchestrators/{id}/config returns HTTP 200 on a valid config update."""
        response = client.patch(
            f"{ORCHESTRATORS_URL}/inst_test/config", json=VALID_UPDATE_PAYLOAD
        )

        assert response.status_code == 200

    def test_response_contains_instance_id(self, client: TestClient) -> None:
        """PATCH /api/orchestrators/{id}/config response body includes instance_id."""
        response = client.patch(
            f"{ORCHESTRATORS_URL}/inst_test/config", json=VALID_UPDATE_PAYLOAD
        )

        assert "instance_id" in response.json()

    def test_returns_422_when_instance_not_found(
        self, client: TestClient, mock_settings_service: MagicMock
    ) -> None:
        """PATCH /api/orchestrators/{id}/config returns 422 when instance does not exist."""
        mock_settings_service.update_orchestrator_config = AsyncMock(
            side_effect=ValueError("Instance missing_inst not found")
        )

        response = client.patch(
            f"{ORCHESTRATORS_URL}/missing_inst/config", json=VALID_UPDATE_PAYLOAD
        )

        assert response.status_code == 422

    def test_delegates_to_settings_service(
        self, client: TestClient, mock_settings_service: MagicMock
    ) -> None:
        """PATCH /api/orchestrators/{id}/config calls SettingsService.update_orchestrator_config."""
        client.patch(f"{ORCHESTRATORS_URL}/inst_test/config", json=VALID_UPDATE_PAYLOAD)

        mock_settings_service.update_orchestrator_config.assert_awaited_once()

    def test_returns_422_when_framework_type_in_config_update(
        self, client: TestClient, mock_settings_service: MagicMock
    ) -> None:
        """PATCH /api/orchestrators/{id}/config returns 422 when framework_type is in the payload."""
        mock_settings_service.update_orchestrator_config = AsyncMock(
            side_effect=ValueError("Cannot modify immutable fields: ['framework_type']")
        )

        response = client.patch(
            f"{ORCHESTRATORS_URL}/inst_test/config",
            json={"config": {"framework_type": "openai_agents"}},
        )

        assert response.status_code == 422

    def test_returns_422_when_mode_in_config_update(
        self, client: TestClient, mock_settings_service: MagicMock
    ) -> None:
        """PATCH /api/orchestrators/{id}/config returns 422 when mode is in the payload."""
        mock_settings_service.update_orchestrator_config = AsyncMock(
            side_effect=ValueError("Cannot modify immutable fields: ['mode']")
        )

        response = client.patch(
            f"{ORCHESTRATORS_URL}/inst_test/config",
            json={"config": {"mode": "handoff"}},
        )

        assert response.status_code == 422

    def test_returns_422_for_deleted_instance(
        self, client: TestClient, mock_settings_service: MagicMock
    ) -> None:
        """PATCH /api/orchestrators/{id}/config returns 422 for a deleted instance."""
        mock_settings_service.update_orchestrator_config = AsyncMock(
            side_effect=ValueError("Instance inst_test has been deleted")
        )

        response = client.patch(
            f"{ORCHESTRATORS_URL}/inst_test/config", json=VALID_UPDATE_PAYLOAD
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /api/orchestrators/{instance_id}/status
# ---------------------------------------------------------------------------


class TestUpdateOrchestratorStatusEndpoint:
    """Tests for PATCH /api/orchestrators/{instance_id}/status."""

    def test_returns_200_on_suspend(self, client: TestClient) -> None:
        """PATCH /api/orchestrators/{id}/status returns 200 when suspending an active instance."""
        response = client.patch(
            f"{ORCHESTRATORS_URL}/inst_test/status", json={"status": "suspended"}
        )

        assert response.status_code == 200

    def test_returns_200_on_reactivate(self, client: TestClient) -> None:
        """PATCH /api/orchestrators/{id}/status returns 200 when re-enabling a suspended instance."""
        response = client.patch(
            f"{ORCHESTRATORS_URL}/inst_test/status", json={"status": "active"}
        )

        assert response.status_code == 200

    def test_response_contains_instance_id(self, client: TestClient) -> None:
        """PATCH /api/orchestrators/{id}/status response body includes instance_id."""
        response = client.patch(
            f"{ORCHESTRATORS_URL}/inst_test/status", json={"status": "suspended"}
        )

        assert "instance_id" in response.json()

    def test_returns_422_for_deleted_status(self, client: TestClient) -> None:
        """PATCH /api/orchestrators/{id}/status returns 422 when status='deleted' (use DELETE instead)."""
        response = client.patch(
            f"{ORCHESTRATORS_URL}/inst_test/status", json={"status": "is_deleted"}
        )

        assert response.status_code == 422

    def test_returns_404_when_instance_not_found(
        self, client: TestClient, mock_settings_service: MagicMock
    ) -> None:
        """PATCH /api/orchestrators/{id}/status returns 404 when instance does not exist."""
        mock_settings_service.get_instance_config.return_value = None

        response = client.patch(
            f"{ORCHESTRATORS_URL}/missing_inst/status", json={"status": "suspended"}
        )

        assert response.status_code == 404

    def test_returns_410_when_instance_already_deleted(
        self, client: TestClient, mock_settings_service: MagicMock
    ) -> None:
        """PATCH /api/orchestrators/{id}/status returns 410 when instance is already deleted."""
        mock_settings_service.get_instance_config.return_value = {
            "instance_id": "inst_test",
            "org_id": "org_test",
            "name": "My Bot",
            "framework_type": "langgraph",
            "mode": "supervisor",
            "status": "is_deleted",
            "config": {},
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }

        response = client.patch(
            f"{ORCHESTRATORS_URL}/inst_test/status", json={"status": "active"}
        )

        assert response.status_code == 410

    def test_delegates_to_settings_service(
        self, client: TestClient, mock_settings_service: MagicMock
    ) -> None:
        """PATCH /api/orchestrators/{id}/status calls SettingsService.update_instance_status."""
        client.patch(
            f"{ORCHESTRATORS_URL}/inst_test/status", json={"status": "suspended"}
        )

        mock_settings_service.update_instance_status.assert_awaited_once()


# ---------------------------------------------------------------------------
# DELETE /api/orchestrators/{instance_id}
# ---------------------------------------------------------------------------


class TestDeleteOrchestratorEndpoint:
    """Tests for DELETE /api/orchestrators/{instance_id}."""

    def test_returns_204_for_known_instance(self, client: TestClient) -> None:
        """DELETE /api/orchestrators/{id} returns HTTP 204 No Content on success."""
        response = client.delete(f"{ORCHESTRATORS_URL}/inst_test")

        assert response.status_code == 204

    def test_delegates_to_settings_service(
        self, client: TestClient, mock_settings_service: MagicMock
    ) -> None:
        """DELETE /api/orchestrators/{id} calls SettingsService.delete_instance exactly once."""
        client.delete(f"{ORCHESTRATORS_URL}/inst_test")

        mock_settings_service.delete_instance.assert_awaited_once()

    def test_returns_404_when_instance_not_found(
        self, client: TestClient, mock_settings_service: MagicMock
    ) -> None:
        """DELETE /api/orchestrators/{id} returns 404 when the instance does not exist."""
        mock_settings_service.get_instance_config.return_value = None

        response = client.delete(f"{ORCHESTRATORS_URL}/missing_inst")

        assert response.status_code == 404

    def test_returns_410_when_instance_already_deleted(
        self, client: TestClient, mock_settings_service: MagicMock
    ) -> None:
        """DELETE /api/orchestrators/{id} returns 410 when instance is already soft-deleted."""
        mock_settings_service.get_instance_config.return_value = {
            "instance_id": "inst_test",
            "org_id": "org_test",
            "name": "My Bot",
            "framework_type": "langgraph",
            "mode": "supervisor",
            "status": "is_deleted",
            "config": {},
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }

        response = client.delete(f"{ORCHESTRATORS_URL}/inst_test")

        assert response.status_code == 410


# ---------------------------------------------------------------------------
# Role-based access control
# ---------------------------------------------------------------------------


class TestOrchestratorRoleEnforcement:
    """Tests that orchestrator endpoints enforce org_admin or higher."""

    def test_user_role_receives_403_on_create_orchestrator(self, app: FastAPI) -> None:
        """POST /api/orgs/org_test/orchestrators returns HTTP 403 for a non-admin user."""
        from fastapi import HTTPException, status

        import cadence.middleware.authorization_middleware as perms

        def override_raises_403():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization admin access required",
            )

        app.dependency_overrides[perms.require_org_admin_access] = override_raises_403
        restricted_client = TestClient(app)

        response = restricted_client.post(ORCHESTRATORS_URL, json=VALID_CREATE_PAYLOAD)

        assert response.status_code == 403

    def test_user_role_receives_403_on_list_orchestrators(self, app: FastAPI) -> None:
        """GET /api/orgs/org_test/orchestrators returns HTTP 403 for a non-admin user."""
        from fastapi import HTTPException, status

        import cadence.middleware.authorization_middleware as perms

        def override_raises_403():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization admin access required",
            )

        app.dependency_overrides[perms.require_org_admin_access] = override_raises_403
        restricted_client = TestClient(app)

        response = restricted_client.get(ORCHESTRATORS_URL)

        assert response.status_code == 403

    def test_org_admin_receives_201_on_create_orchestrator(self, app: FastAPI) -> None:
        """POST /api/orgs/org_test/orchestrators returns HTTP 201 for a user with org_admin."""
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

        response = org_admin_client.post(ORCHESTRATORS_URL, json=VALID_CREATE_PAYLOAD)

        assert response.status_code == 201
