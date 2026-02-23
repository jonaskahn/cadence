"""Unit tests for middleware components.

Verifies that authentication, tenant context, and rate limiting middleware
can be instantiated with correct dependencies and that the TenantContext
data-class stores all required fields.
"""

from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# TenantContext
# ---------------------------------------------------------------------------


class TestTenantContext:
    """Tests for the TenantContext dataclass."""

    def test_stores_org_id(self) -> None:
        """TenantContext stores the organization ID on the org_id attribute."""
        from cadence.middleware.tenant_context_middleware import TenantContext

        context = TenantContext(
            user_id="user_xyz",
            org_id="org_abc",
            is_sys_admin=False,
            is_org_admin=False,
        )

        assert context.org_id == "org_abc"

    def test_stores_user_id(self) -> None:
        """TenantContext stores the user identifier on the user_id attribute."""
        from cadence.middleware.tenant_context_middleware import TenantContext

        context = TenantContext(
            user_id="user_xyz",
            org_id="o",
            is_sys_admin=False,
            is_org_admin=False,
        )

        assert context.user_id == "user_xyz"

    def test_stores_is_sys_admin_false(self) -> None:
        """TenantContext stores is_sys_admin=False for regular users."""
        from cadence.middleware.tenant_context_middleware import TenantContext

        context = TenantContext(
            user_id="u", org_id="o", is_sys_admin=False, is_org_admin=False
        )

        assert context.is_sys_admin is False

    def test_stores_is_sys_admin_true(self) -> None:
        """TenantContext stores is_sys_admin=True for platform admins."""
        from cadence.middleware.tenant_context_middleware import TenantContext

        context = TenantContext(
            user_id="u", org_id="o", is_sys_admin=True, is_org_admin=True
        )

        assert context.is_sys_admin is True

    def test_stores_is_org_admin_false(self) -> None:
        """TenantContext stores is_org_admin=False for regular members."""
        from cadence.middleware.tenant_context_middleware import TenantContext

        context = TenantContext(
            user_id="u", org_id="o", is_sys_admin=False, is_org_admin=False
        )

        assert context.is_org_admin is False

    def test_stores_is_org_admin_true(self) -> None:
        """TenantContext stores is_org_admin=True for org admins."""
        from cadence.middleware.tenant_context_middleware import TenantContext

        context = TenantContext(
            user_id="u", org_id="o", is_sys_admin=False, is_org_admin=True
        )

        assert context.is_org_admin is True


# ---------------------------------------------------------------------------
# JWTAuth
# ---------------------------------------------------------------------------


class TestJWTAuth:
    """Tests for the JWTAuth configuration class."""

    def test_stores_internal_secret(self) -> None:
        """JWTAuth stores the internal JWT signing secret."""
        from cadence.middleware.authentication_middleware import JWTAuth

        auth = JWTAuth(
            internal_secret="my_secret",
            internal_algorithm="HS256",
            third_party_secret="public_key",
            third_party_algorithm="RS256",
        )

        assert auth.internal_secret == "my_secret"

    def test_stores_internal_algorithm(self) -> None:
        """JWTAuth stores the signing algorithm for internal tokens."""
        from cadence.middleware.authentication_middleware import JWTAuth

        auth = JWTAuth(
            internal_secret="s",
            internal_algorithm="HS256",
            third_party_secret="p",
            third_party_algorithm="RS256",
        )

        assert auth.internal_algorithm == "HS256"

    def test_stores_third_party_secret(self) -> None:
        """JWTAuth stores the public key for verifying third-party JWTs."""
        from cadence.middleware.authentication_middleware import JWTAuth

        auth = JWTAuth(
            internal_secret="s",
            internal_algorithm="HS256",
            third_party_secret="public_key",
            third_party_algorithm="RS256",
        )

        assert auth.third_party_secret == "public_key"

    def test_stores_third_party_algorithm(self) -> None:
        """JWTAuth stores the verification algorithm for third-party tokens."""
        from cadence.middleware.authentication_middleware import JWTAuth

        auth = JWTAuth(
            internal_secret="s",
            internal_algorithm="HS256",
            third_party_secret="p",
            third_party_algorithm="RS256",
        )

        assert auth.third_party_algorithm == "RS256"


# ---------------------------------------------------------------------------
# APIKeyAuth
# ---------------------------------------------------------------------------


class TestAPIKeyAuth:
    """Tests for the APIKeyAuth class."""

    def test_can_be_instantiated_with_repository(self) -> None:
        """APIKeyAuth accepts a key repository dependency at construction time."""
        from cadence.middleware.authentication_middleware import APIKeyAuth

        api_key_repository = MagicMock()
        auth = APIKeyAuth(api_key_repo=api_key_repository)

        assert auth is not None


# ---------------------------------------------------------------------------
# AuthenticationMiddleware
# ---------------------------------------------------------------------------


class TestAuthenticationMiddleware:
    """Tests for the AuthenticationMiddleware ASGI middleware."""

    def test_can_be_instantiated_with_app_and_jwt_auth(self) -> None:
        """AuthenticationMiddleware wraps an ASGI app with a JWTAuth configuration."""
        from cadence.middleware.authentication_middleware import (
            AuthenticationMiddleware,
            JWTAuth,
        )

        asgi_app = MagicMock()
        jwt_config = JWTAuth("s", "HS256", "p", "RS256")

        middleware = AuthenticationMiddleware(app=asgi_app, jwt_auth=jwt_config)

        assert middleware is not None

    def test_all_auth_classes_importable(self) -> None:
        """Authentication module exports JWTAuth, APIKeyAuth, and AuthenticationMiddleware."""
        from cadence.middleware.authentication_middleware import (
            APIKeyAuth,
            AuthenticationMiddleware,
            JWTAuth,
        )

        assert JWTAuth is not None
        assert APIKeyAuth is not None
        assert AuthenticationMiddleware is not None


# ---------------------------------------------------------------------------
# TenantContextMiddleware
# ---------------------------------------------------------------------------


class TestTenantContextMiddleware:
    """Tests for the TenantContextMiddleware ASGI middleware."""

    def test_all_tenant_context_symbols_importable(self) -> None:
        """Tenant context module exports TenantContext and TenantContextMiddleware."""
        from cadence.middleware.tenant_context_middleware import (
            TenantContext,
            TenantContextMiddleware,
        )

        assert TenantContext is not None
        assert TenantContextMiddleware is not None

    def test_can_be_instantiated_with_app_and_jwt_secret(self) -> None:
        """TenantContextMiddleware wraps an ASGI app and accepts a JWT secret."""
        from cadence.middleware.tenant_context_middleware import TenantContextMiddleware

        middleware = TenantContextMiddleware(app=MagicMock(), jwt_secret="test-secret")

        assert middleware is not None


# ---------------------------------------------------------------------------
# RateLimitMiddleware
# ---------------------------------------------------------------------------


class TestRateLimitMiddleware:
    """Tests for the RateLimitMiddleware ASGI middleware."""

    def test_importable(self) -> None:
        """Rate limiting module exports RateLimitMiddleware."""
        from cadence.middleware.rate_limiting_middleware import RateLimitMiddleware

        assert RateLimitMiddleware is not None

    def test_can_be_instantiated_with_app_and_redis(self) -> None:
        """RateLimitMiddleware wraps an ASGI app and accepts a Redis client."""
        from cadence.middleware.rate_limiting_middleware import RateLimitMiddleware

        middleware = RateLimitMiddleware(app=MagicMock(), redis_client=MagicMock())

        assert middleware is not None
