"""Unit tests for AppSettings (infrastructure configuration).

Verifies that AppSettings can be instantiated, exposes the expected attributes
with correct types, respects CADENCE_* environment variable overrides, and
that the get_settings() singleton factory returns an AppSettings instance.

AppSettings is infrastructure-only config (DB URLs, JWT secrets, ports). It is
not part of the runtime settings cascade; operational defaults live in the
global_settings DB table.
"""

import os
from unittest.mock import patch

import pytest

from cadence.config.app_settings import AppSettings, get_settings

# ---------------------------------------------------------------------------
# AppSettings instantiation
# ---------------------------------------------------------------------------


class TestAppSettings:
    """Tests for AppSettings default values and environment overrides."""

    def test_can_instantiate_with_defaults(self) -> None:
        """AppSettings can be created without any environment variables set."""
        settings = AppSettings()

        assert settings is not None

    def test_exposes_api_host_attribute(self) -> None:
        """AppSettings provides an api_host attribute for server bind configuration."""
        settings = AppSettings()

        assert hasattr(settings, "api_host")

    def test_exposes_api_port_attribute(self) -> None:
        """AppSettings provides an api_port attribute for server port configuration."""
        settings = AppSettings()

        assert hasattr(settings, "api_port")

    def test_api_port_is_integer(self) -> None:
        """AppSettings converts the api_port value to an integer."""
        settings = AppSettings()

        assert isinstance(settings.api_port, int)

    def test_api_port_overridable_via_cadence_prefix_env_var(self) -> None:
        """AppSettings reads CADENCE_API_PORT to override the default api_port."""
        with patch.dict(os.environ, {"CADENCE_API_PORT": "9999"}):
            settings = AppSettings()

        assert settings.api_port == 9999

    def test_api_host_overridable_via_cadence_prefix_env_var(self) -> None:
        """AppSettings reads CADENCE_API_HOST to override the default api_host."""
        with patch.dict(os.environ, {"CADENCE_API_HOST": "127.0.0.1"}):
            settings = AppSettings()

        assert settings.api_host == "127.0.0.1"


# ---------------------------------------------------------------------------
# get_settings() singleton
# ---------------------------------------------------------------------------


class TestGetSettings:
    """Tests for the get_settings() singleton factory."""

    def test_returns_app_settings_instance(self) -> None:
        """get_settings returns an AppSettings object."""
        result = get_settings()

        assert isinstance(result, AppSettings)

    def test_is_callable(self) -> None:
        """get_settings is a callable function."""
        assert callable(get_settings)


# ---------------------------------------------------------------------------
# Expected attributes
# ---------------------------------------------------------------------------


class TestSettingsAttributes:
    """Parametrized checks that frequently-used attributes exist on AppSettings."""

    MINIMUM_REQUIRED_ATTRIBUTES = [
        "api_host",
        "api_port",
    ]

    @pytest.mark.parametrize("attribute_name", MINIMUM_REQUIRED_ATTRIBUTES)
    def test_attribute_exists(self, attribute_name: str) -> None:
        """AppSettings exposes every attribute required by the application layer."""
        settings = AppSettings()

        assert hasattr(
            settings, attribute_name
        ), f"AppSettings is missing required attribute: {attribute_name}"
