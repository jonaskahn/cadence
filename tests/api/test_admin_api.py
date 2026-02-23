"""API tests for the admin controller.

Verifies admin-only global settings endpoints at /api/admin/settings,
pool health check at /api/admin/health, and pool stats at /api/admin/pool/stats.
Includes role-based access control checks confirming non-admin users receive HTTP 403.

After a successful PATCH on a global setting, the controller publishes a
settings.global_changed event via the event_publisher (if one is present on
app.state) so all nodes reload their hot-tier instances via RabbitMQ.
"""

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

ADMIN_SETTINGS_URL = "/api/admin/settings"
POOL_HEALTH_URL = "/api/admin/health"
POOL_STATS_URL = "/api/admin/pool/stats"


# ---------------------------------------------------------------------------
# Admin role enforcement
# ---------------------------------------------------------------------------


class TestAdminRoleEnforcement:
    """Tests that sys_admin-only endpoints reject non-sys_admin users."""

    def test_non_admin_receives_403_on_global_settings_list(self, app: FastAPI) -> None:
        """GET /api/admin/settings returns HTTP 403 for a user without sys_admin."""
        from fastapi import HTTPException, status

        import cadence.middleware.authorization_middleware as perms

        def override_raises_403():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Platform admin access required",
            )

        app.dependency_overrides[perms.require_sys_admin] = override_raises_403
        non_admin_client = TestClient(app)

        response = non_admin_client.get(ADMIN_SETTINGS_URL)

        assert response.status_code == 403

    def test_org_admin_receives_403_on_global_settings_list(self, app: FastAPI) -> None:
        """GET /api/admin/settings returns HTTP 403 for a user with org_admin but not sys_admin."""
        from fastapi import HTTPException, status

        import cadence.middleware.authorization_middleware as perms

        def override_raises_403():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Platform admin access required",
            )

        app.dependency_overrides[perms.require_sys_admin] = override_raises_403
        org_admin_client = TestClient(app)

        response = org_admin_client.get(ADMIN_SETTINGS_URL)

        assert response.status_code == 403

    def test_sys_admin_receives_200_on_global_settings_list(
        self, client: TestClient
    ) -> None:
        """GET /api/admin/settings returns HTTP 200 for a user with role 'sys_admin'."""
        response = client.get(ADMIN_SETTINGS_URL)

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/admin/settings — Tier 2 global settings
# ---------------------------------------------------------------------------


class TestGlobalSettingsEndpoints:
    """Tests for GET and PATCH /api/admin/settings."""

    def test_get_settings_returns_list(self, client: TestClient) -> None:
        """GET /api/admin/settings response body is a JSON array."""
        response = client.get(ADMIN_SETTINGS_URL)

        assert isinstance(response.json(), list)

    def test_get_settings_delegates_to_settings_service(
        self, client: TestClient, mock_settings_service: MagicMock
    ) -> None:
        """GET /api/admin/settings calls SettingsService.list_global_settings exactly once."""
        client.get(ADMIN_SETTINGS_URL)

        mock_settings_service.list_global_settings.assert_awaited_once()

    def test_update_global_setting_returns_200(self, client: TestClient) -> None:
        """PATCH /api/admin/settings/{key} returns HTTP 200 when the key exists."""
        response = client.patch(
            f"{ADMIN_SETTINGS_URL}/max_tokens", json={"value": 8192}
        )

        assert response.status_code == 200

    def test_update_global_setting_delegates_to_settings_service(
        self, client: TestClient, mock_settings_service: MagicMock
    ) -> None:
        """PATCH /api/admin/settings/{key} calls SettingsService.update_global_setting."""
        client.patch(f"{ADMIN_SETTINGS_URL}/max_tokens", json={"value": 8192})

        mock_settings_service.update_global_setting.assert_awaited_once()

    def test_update_returns_404_when_setting_not_found(
        self, client: TestClient, mock_settings_service: MagicMock
    ) -> None:
        """PATCH /api/admin/settings/{key} returns 404 when the setting key does not exist."""
        mock_settings_service.update_global_setting.return_value = None

        response = client.patch(f"{ADMIN_SETTINGS_URL}/missing_key", json={"value": 0})

        assert response.status_code == 404

    def test_update_publishes_global_settings_changed_event(
        self, app: FastAPI, client: TestClient
    ) -> None:
        """PATCH /api/admin/settings/{key} publishes a settings.global_changed event when successful."""
        mock_publisher = MagicMock()
        mock_publisher.publish_global_settings_changed = AsyncMock(return_value=None)
        app.state.event_publisher = mock_publisher

        client.patch(f"{ADMIN_SETTINGS_URL}/max_tokens", json={"value": 8192})

        mock_publisher.publish_global_settings_changed.assert_awaited_once()

    def test_update_succeeds_without_event_publisher(
        self, app: FastAPI, client: TestClient
    ) -> None:
        """PATCH /api/admin/settings/{key} returns 200 even when no event_publisher is configured."""
        app.state.event_publisher = None

        response = client.patch(
            f"{ADMIN_SETTINGS_URL}/max_tokens", json={"value": 8192}
        )

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/admin/health — pool health check
# ---------------------------------------------------------------------------


class TestPoolHealthEndpoint:
    """Tests for GET /api/admin/health."""

    def test_returns_200(self, client: TestClient) -> None:
        """GET /api/admin/health returns HTTP 200."""
        response = client.get(POOL_HEALTH_URL)

        assert response.status_code == 200

    def test_response_is_a_list(self, client: TestClient) -> None:
        """GET /api/admin/health response body is a JSON array of health records."""
        response = client.get(POOL_HEALTH_URL)

        assert isinstance(response.json(), list)

    def test_delegates_to_orchestrator_pool(
        self, client: TestClient, mock_pool: MagicMock
    ) -> None:
        """GET /api/admin/health calls OrchestratorPool.health_check_all exactly once."""
        client.get(POOL_HEALTH_URL)

        mock_pool.health_check_all.assert_awaited_once()


# ---------------------------------------------------------------------------
# GET /api/admin/pool/stats — pool statistics
# ---------------------------------------------------------------------------


class TestPoolStatsEndpoint:
    """Tests for GET /api/admin/pool/stats."""

    def test_returns_200(self, client: TestClient) -> None:
        """GET /api/admin/pool/stats returns HTTP 200."""
        response = client.get(POOL_STATS_URL)

        assert response.status_code == 200

    def test_response_contains_total_instances(self, client: TestClient) -> None:
        """GET /api/admin/pool/stats response body contains total_instances count."""
        response = client.get(POOL_STATS_URL)

        assert "total_instances" in response.json()

    def test_delegates_to_orchestrator_pool(
        self, client: TestClient, mock_pool: MagicMock
    ) -> None:
        """GET /api/admin/pool/stats calls OrchestratorPool.get_stats exactly once."""
        client.get(POOL_STATS_URL)

        mock_pool.get_stats.assert_called_once()
