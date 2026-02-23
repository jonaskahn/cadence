"""Unit tests for the exception hierarchy in cadence.exception.api_exceptions.

Verifies that every exception class carries the correct HTTP status code,
error code, and message, and that the inheritance chain is intact.
Also verifies that exceptions can be used with Python's exception chaining.
"""

import pytest

from cadence.exception.api_exceptions import (
    AuthenticationError,
    AuthorizationError,
    CadenceException,
    InvalidTokenError,
    TenantIsolationError,
)

# ---------------------------------------------------------------------------
# CadenceException – base class contract
# ---------------------------------------------------------------------------


class TestCadenceException:
    """Tests for the CadenceException base class."""

    def test_stores_message(self) -> None:
        """CadenceException stores the provided message on the message attribute."""
        exception = CadenceException("something broke")

        assert exception.message == "something broke"

    def test_default_error_code_is_internal_error(self) -> None:
        """CadenceException defaults to 'INTERNAL_ERROR' when no code is given."""
        exception = CadenceException("error")

        assert exception.code == "INTERNAL_ERROR"

    def test_default_http_status_is_500(self) -> None:
        """CadenceException defaults to HTTP 500 when no status_code is provided."""
        exception = CadenceException("error")

        assert exception.status_code == 500

    def test_default_field_is_none(self) -> None:
        """CadenceException sets field to None by default."""
        exception = CadenceException("error")

        assert exception.field is None

    def test_default_details_is_empty_dict(self) -> None:
        """CadenceException initializes details to an empty dict by default."""
        exception = CadenceException("error")

        assert exception.details == {}

    def test_stores_custom_error_code(self) -> None:
        """CadenceException stores a caller-supplied error code."""
        exception = CadenceException("error", code="CUSTOM_CODE")

        assert exception.code == "CUSTOM_CODE"

    def test_stores_custom_http_status(self) -> None:
        """CadenceException stores a caller-supplied HTTP status code."""
        exception = CadenceException("error", status_code=400)

        assert exception.status_code == 400

    def test_stores_field_name(self) -> None:
        """CadenceException stores the field name associated with the error."""
        exception = CadenceException("error", field="email")

        assert exception.field == "email"

    def test_stores_extra_details(self) -> None:
        """CadenceException stores arbitrary key-value details."""
        exception = CadenceException("error", details={"reason": "too long"})

        assert exception.details["reason"] == "too long"

    def test_is_an_exception_instance(self) -> None:
        """CadenceException inherits from the built-in Exception class."""
        assert isinstance(CadenceException("error"), Exception)

    def test_str_representation_is_message(self) -> None:
        """str(CadenceException) returns the human-readable message."""
        exception = CadenceException("something went wrong")

        assert str(exception) == "something went wrong"


# ---------------------------------------------------------------------------
# AuthenticationError (401)
# ---------------------------------------------------------------------------


class TestAuthenticationError:
    """Tests for AuthenticationError (HTTP 401)."""

    def test_http_status_is_401(self) -> None:
        """AuthenticationError carries HTTP 401 Unauthorized status code."""
        assert AuthenticationError().status_code == 401

    def test_default_error_code(self) -> None:
        """AuthenticationError uses 'AUTHENTICATION_FAILED' as its error code."""
        assert AuthenticationError().code == "AUTHENTICATION_FAILED"

    def test_stores_custom_message(self) -> None:
        """AuthenticationError stores a caller-supplied message."""
        exception = AuthenticationError("Token expired")

        assert exception.message == "Token expired"

    def test_is_cadence_exception_subclass(self) -> None:
        """AuthenticationError inherits from CadenceException."""
        assert isinstance(AuthenticationError(), CadenceException)


class TestInvalidTokenError:
    """Tests for InvalidTokenError (HTTP 401, code INVALID_TOKEN)."""

    def test_http_status_is_401(self) -> None:
        """InvalidTokenError carries HTTP 401 status code."""
        assert InvalidTokenError().status_code == 401

    def test_error_code_is_invalid_token(self) -> None:
        """InvalidTokenError uses 'INVALID_TOKEN' as its error code."""
        assert InvalidTokenError().code == "INVALID_TOKEN"

    def test_is_authentication_error_subclass(self) -> None:
        """InvalidTokenError inherits from AuthenticationError."""
        assert isinstance(InvalidTokenError(), AuthenticationError)


# ---------------------------------------------------------------------------
# AuthorizationError (403)
# ---------------------------------------------------------------------------


class TestAuthorizationError:
    """Tests for AuthorizationError (HTTP 403)."""

    def test_http_status_is_403(self) -> None:
        """AuthorizationError carries HTTP 403 Forbidden status code."""
        assert AuthorizationError().status_code == 403

    def test_default_error_code(self) -> None:
        """AuthorizationError uses 'AUTHORIZATION_FAILED' as its error code."""
        assert AuthorizationError().code == "AUTHORIZATION_FAILED"

    def test_is_cadence_exception_subclass(self) -> None:
        """AuthorizationError inherits from CadenceException."""
        assert isinstance(AuthorizationError(), CadenceException)


class TestTenantIsolationError:
    """Tests for TenantIsolationError (HTTP 403, code TENANT_ISOLATION_VIOLATION)."""

    def test_http_status_is_403(self) -> None:
        """TenantIsolationError carries HTTP 403 Forbidden status code."""
        assert TenantIsolationError().status_code == 403

    def test_error_code_is_tenant_isolation_violation(self) -> None:
        """TenantIsolationError uses 'TENANT_ISOLATION_VIOLATION' as its error code."""
        assert TenantIsolationError().code == "TENANT_ISOLATION_VIOLATION"

    def test_is_authorization_error_subclass(self) -> None:
        """TenantIsolationError inherits from AuthorizationError."""
        assert isinstance(TenantIsolationError(), AuthorizationError)


# ---------------------------------------------------------------------------
# Resource exceptions
# ---------------------------------------------------------------------------


class TestResourceNotFoundError:
    """Tests for ResourceNotFoundError (HTTP 404)."""

    def test_http_status_is_404(self) -> None:
        """ResourceNotFoundError carries HTTP 404 Not Found status code."""
        from cadence.exception.api_exceptions import ResourceNotFoundError

        exception = ResourceNotFoundError(
            resource="Organization", resource_id="org_xyz"
        )

        assert exception.status_code == 404


class TestResourceAlreadyExistsError:
    """Tests for ResourceAlreadyExistsError (HTTP 409)."""

    def test_http_status_is_409(self) -> None:
        """ResourceAlreadyExistsError carries HTTP 409 Conflict status code."""
        from cadence.exception.api_exceptions import ResourceAlreadyExistsError

        exception = ResourceAlreadyExistsError(
            resource="Organization", identifier="org_xyz"
        )

        assert exception.status_code == 409


class TestValidationError:
    """Tests for ValidationError (HTTP 422)."""

    def test_http_status_is_422(self) -> None:
        """ValidationError carries HTTP 422 Unprocessable Entity status code."""
        from cadence.exception.api_exceptions import ValidationError

        exception = ValidationError(message="invalid format", field="email")

        assert exception.status_code == 422


class TestRateLimitExceededError:
    """Tests for RateLimitExceededError (HTTP 429)."""

    def test_http_status_is_429(self) -> None:
        """RateLimitExceededError carries HTTP 429 Too Many Requests status code."""
        from cadence.exception.api_exceptions import RateLimitExceededError

        assert RateLimitExceededError().status_code == 429


# ---------------------------------------------------------------------------
# Exception chaining
# ---------------------------------------------------------------------------


class TestExceptionChaining:
    """Tests for Python exception chaining with CadenceException."""

    def test_cadence_exception_can_be_caught_as_base_type(self) -> None:
        """Subclasses of CadenceException can be caught using the CadenceException type."""
        with pytest.raises(CadenceException) as exc_info:
            raise AuthenticationError("test")

        assert exc_info.value.status_code == 401

    def test_original_cause_is_preserved_when_chained(self) -> None:
        """CadenceException retains the original exception when raised with 'from'."""
        original_exception = ValueError("original error")

        try:
            try:
                raise original_exception
            except ValueError as caught:
                raise CadenceException("wrapped") from caught
        except CadenceException as wrapped:
            assert wrapped.__cause__ is original_exception
