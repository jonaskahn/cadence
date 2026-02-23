"""API tests for the health controller.

Verifies that the single health endpoint returns the expected HTTP status code
and response body shape, and that infrastructure dependency checks are
delegated to the mocked clients.
"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Tests for GET /health (liveness and readiness combined check)."""

    def test_returns_200_when_all_dependencies_healthy(
        self, client: TestClient
    ) -> None:
        """GET /health returns HTTP 200 when all infrastructure checks pass."""
        response = client.get("/health")

        assert response.status_code == 200

    def test_response_body_contains_status_key(self, client: TestClient) -> None:
        """GET /health response body includes a 'status' field."""
        response = client.get("/health")

        assert "status" in response.json()

    def test_status_value_is_healthy_on_success(self, client: TestClient) -> None:
        """GET /health reports status 'healthy' when all checks pass."""
        response = client.get("/health")

        assert response.json()["status"] == "healthy"

    def test_response_includes_postgres_field(self, client: TestClient) -> None:
        """GET /health response body includes a 'postgres' connectivity field."""
        response = client.get("/health")

        assert "postgres" in response.json()

    def test_response_includes_redis_field(self, client: TestClient) -> None:
        """GET /health response body includes a 'redis' connectivity field."""
        response = client.get("/health")

        assert "redis" in response.json()

    def test_response_includes_mongodb_field(self, client: TestClient) -> None:
        """GET /health response body includes a 'mongodb' connectivity field."""
        response = client.get("/health")

        assert "mongodb" in response.json()

    def test_checks_postgres_dependency(
        self,
        client: TestClient,
        mock_postgres_repo: MagicMock,
    ) -> None:
        """GET /health calls postgres_repo.health_check to verify connectivity."""
        client.get("/health")

        mock_postgres_repo.health_check.assert_awaited_once()

    def test_checks_redis_dependency(
        self,
        client: TestClient,
        mock_redis_client: MagicMock,
    ) -> None:
        """GET /health pings the Redis client to verify connectivity."""
        client.get("/health")

        mock_redis_client.get_client.return_value.ping.assert_awaited_once()

    def test_checks_mongodb_dependency(
        self,
        client: TestClient,
        mock_mongo_client: MagicMock,
    ) -> None:
        """GET /health issues a MongoDB admin ping command."""
        client.get("/health")

        mock_mongo_client.client.admin.command.assert_awaited_once_with("ping")

    def test_returns_200_with_unhealthy_status_when_postgres_fails(
        self,
        client: TestClient,
        mock_postgres_repo: MagicMock,
    ) -> None:
        """GET /health returns 200 with unhealthy status when PostgreSQL check fails."""
        mock_postgres_repo.health_check.side_effect = Exception("connection refused")

        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "unhealthy"

    def test_returns_200_with_unhealthy_status_when_redis_fails(
        self,
        client: TestClient,
        mock_redis_client: MagicMock,
    ) -> None:
        """GET /health returns 200 with unhealthy status when Redis ping fails."""
        mock_redis_client.get_client.return_value.ping.side_effect = Exception(
            "timeout"
        )

        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "unhealthy"

    def test_returns_200_with_unhealthy_status_when_mongodb_fails(
        self,
        client: TestClient,
        mock_mongo_client: MagicMock,
    ) -> None:
        """GET /health returns 200 with unhealthy status when MongoDB check fails."""
        mock_mongo_client.client.admin.command.side_effect = Exception("auth failed")

        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "unhealthy"
