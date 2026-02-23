"""Unit tests for cadence.infrastructure.plugins.plugin_settings_resolver.

Covers:
- PluginSettingsResolver.resolve: schema defaults, instance overrides, required validation
- _get_overrides: pid@version key lookup, fallback to pid-only, settings-list format
- _extract_defaults: extracts only keys with non-None defaults
- _validate_required: raises ValueError when required key is missing
- get_sensitive_keys: returns keys marked sensitive=True
- mask_sensitive_settings: masks sensitive values, leaves others intact
"""

from unittest.mock import MagicMock

import pytest

from cadence.infrastructure.plugins.plugin_settings_resolver import (
    PluginSettingsResolver,
    get_sensitive_keys,
    mask_sensitive_settings,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent(schema: list) -> MagicMock:
    agent = MagicMock()
    agent.get_settings_schema.return_value = schema
    return agent


def _make_agent_no_schema() -> MagicMock:
    agent = MagicMock(spec=[])  # no get_settings_schema attribute
    return agent


# ---------------------------------------------------------------------------
# resolve — defaults only
# ---------------------------------------------------------------------------


class TestResolveDefaults:
    def test_returns_schema_defaults_when_no_overrides(self):
        schema = [{"key": "api_key", "default": "default_key"}]
        agent = _make_agent(schema)
        resolver = PluginSettingsResolver(instance_config={})
        result = resolver.resolve("com.example.plugin", "1.0.0", agent)
        assert result["api_key"] == "default_key"

    def test_skips_key_with_none_default(self):
        schema = [{"key": "secret", "default": None}]
        agent = _make_agent(schema)
        resolver = PluginSettingsResolver(instance_config={})
        result = resolver.resolve("com.example.plugin", "1.0.0", agent)
        assert "secret" not in result

    def test_empty_schema_returns_empty_dict(self):
        agent = _make_agent([])
        resolver = PluginSettingsResolver(instance_config={})
        result = resolver.resolve("com.example.plugin", "1.0.0", agent)
        assert result == {}

    def test_agent_without_schema_method_returns_empty(self):
        agent = _make_agent_no_schema()
        resolver = PluginSettingsResolver(instance_config={})
        result = resolver.resolve("com.example.plugin", "1.0.0", agent)
        assert result == {}


# ---------------------------------------------------------------------------
# resolve — overrides
# ---------------------------------------------------------------------------


class TestResolveOverrides:
    def test_instance_override_wins_over_default(self):
        schema = [{"key": "timeout", "default": 30}]
        agent = _make_agent(schema)
        instance_config = {
            "plugin_settings": {"com.example.plugin@1.0.0": {"timeout": 60}}
        }
        resolver = PluginSettingsResolver(instance_config)
        result = resolver.resolve("com.example.plugin", "1.0.0", agent)
        assert result["timeout"] == 60

    def test_versioned_key_takes_precedence(self):
        schema = [{"key": "url", "default": "http://default"}]
        agent = _make_agent(schema)
        instance_config = {
            "plugin_settings": {
                "com.example.plugin@2.0.0": {"url": "http://v2"},
                "com.example.plugin": {"url": "http://plain"},
            }
        }
        resolver = PluginSettingsResolver(instance_config)
        result = resolver.resolve("com.example.plugin", "2.0.0", agent)
        assert result["url"] == "http://v2"

    def test_settings_list_format_is_parsed(self):
        """Supports {"settings": [{"key": k, "value": v}]} override format."""
        schema = [{"key": "model", "default": "gpt-3.5"}]
        agent = _make_agent(schema)
        instance_config = {
            "plugin_settings": {
                "com.example.plugin@1.0.0": {
                    "settings": [{"key": "model", "value": "gpt-4"}]
                }
            }
        }
        resolver = PluginSettingsResolver(instance_config)
        result = resolver.resolve("com.example.plugin", "1.0.0", agent)
        assert result["model"] == "gpt-4"

    def test_no_plugin_settings_key_returns_defaults(self):
        schema = [{"key": "rate_limit", "default": 10}]
        agent = _make_agent(schema)
        resolver = PluginSettingsResolver(instance_config={})
        result = resolver.resolve("com.example.plugin", "1.0.0", agent)
        assert result["rate_limit"] == 10

    def test_empty_version_uses_plain_pid_key(self):
        schema = [{"key": "endpoint", "default": "http://default"}]
        agent = _make_agent(schema)
        instance_config = {
            "plugin_settings": {"com.example.plugin": {"endpoint": "http://custom"}}
        }
        resolver = PluginSettingsResolver(instance_config)
        result = resolver.resolve("com.example.plugin", "", agent)
        assert result["endpoint"] == "http://custom"


# ---------------------------------------------------------------------------
# resolve — required validation
# ---------------------------------------------------------------------------


class TestResolveRequiredValidation:
    def test_raises_when_required_key_missing(self):
        schema = [{"key": "api_key", "required": True}]
        agent = _make_agent(schema)
        resolver = PluginSettingsResolver(instance_config={})
        with pytest.raises(ValueError, match="api_key"):
            resolver.resolve("com.example.plugin", "1.0.0", agent)

    def test_raises_when_required_key_is_none(self):
        schema = [{"key": "api_key", "required": True, "default": None}]
        agent = _make_agent(schema)
        resolver = PluginSettingsResolver(instance_config={})
        with pytest.raises(ValueError, match="api_key"):
            resolver.resolve("com.example.plugin", "1.0.0", agent)

    def test_no_error_when_required_key_provided_via_override(self):
        schema = [{"key": "api_key", "required": True}]
        agent = _make_agent(schema)
        instance_config = {
            "plugin_settings": {"com.example.plugin@1.0.0": {"api_key": "secret123"}}
        }
        resolver = PluginSettingsResolver(instance_config)
        result = resolver.resolve("com.example.plugin", "1.0.0", agent)
        assert result["api_key"] == "secret123"

    def test_no_error_when_no_required_fields(self):
        schema = [{"key": "optional_key", "required": False}]
        agent = _make_agent(schema)
        resolver = PluginSettingsResolver(instance_config={})
        # Should not raise
        resolver.resolve("com.example.plugin", "1.0.0", agent)

    def test_error_message_includes_plugin_pid(self):
        schema = [{"key": "secret", "required": True}]
        agent = _make_agent(schema)
        resolver = PluginSettingsResolver(instance_config={})
        with pytest.raises(ValueError, match="com.example.plugin"):
            resolver.resolve("com.example.plugin", "1.0.0", agent)


# ---------------------------------------------------------------------------
# get_sensitive_keys
# ---------------------------------------------------------------------------


class TestGetSensitiveKeys:
    def test_returns_keys_marked_sensitive(self):
        schema = [
            {"key": "api_key", "sensitive": True},
            {"key": "timeout", "sensitive": False},
            {"key": "endpoint"},
        ]
        result = get_sensitive_keys(schema)
        assert "api_key" in result
        assert "timeout" not in result
        assert "endpoint" not in result

    def test_empty_schema_returns_empty_list(self):
        assert get_sensitive_keys([]) == []

    def test_no_sensitive_fields_returns_empty_list(self):
        schema = [{"key": "host", "sensitive": False}]
        assert get_sensitive_keys(schema) == []

    def test_skips_entries_without_key(self):
        schema = [{"sensitive": True}]  # no "key" field
        result = get_sensitive_keys(schema)
        assert result == []


# ---------------------------------------------------------------------------
# mask_sensitive_settings
# ---------------------------------------------------------------------------


class TestMaskSensitiveSettings:
    def test_masks_sensitive_value(self):
        schema = [{"key": "api_key", "sensitive": True}]
        settings = {"api_key": "sk-secret", "timeout": 30}
        result = mask_sensitive_settings(settings, schema)
        assert result["api_key"] == "***MASKED***"
        assert result["timeout"] == 30

    def test_non_sensitive_values_unchanged(self):
        schema = [{"key": "api_key", "sensitive": True}]
        settings = {"api_key": "secret", "host": "localhost"}
        result = mask_sensitive_settings(settings, schema)
        assert result["host"] == "localhost"

    def test_does_not_mutate_original(self):
        schema = [{"key": "token", "sensitive": True}]
        settings = {"token": "abc123"}
        mask_sensitive_settings(settings, schema)
        assert settings["token"] == "abc123"

    def test_empty_schema_returns_copy_unchanged(self):
        settings = {"api_key": "secret"}
        result = mask_sensitive_settings(settings, [])
        assert result == settings

    def test_sensitive_key_absent_from_settings_is_ignored(self):
        schema = [{"key": "missing_key", "sensitive": True}]
        settings = {"other": "value"}
        result = mask_sensitive_settings(settings, schema)
        assert "missing_key" not in result
        assert result["other"] == "value"
