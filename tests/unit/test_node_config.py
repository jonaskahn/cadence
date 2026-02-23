"""Unit tests for SupervisorModeNodeConfig — shared node configuration model.

Covers:
- Default field values
- prompt_override alias populates prompt
- prompt_override is excluded from serialization
- Explicit prompt field takes priority over prompt_override
- All numeric overrides (temperature, max_tokens) round-trip correctly
"""

import pytest

from cadence.engine.base.supervisor_node_config import SupervisorModeNodeConfig

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


class TestSupervisorModeNodeConfigDefaults:
    def test_all_fields_default_to_none(self):
        config = SupervisorModeNodeConfig()
        assert config.llm_config_id is None
        assert config.model_name is None
        assert config.prompt is None
        assert config.temperature is None
        assert config.max_tokens is None

    def test_prompt_override_defaults_to_none(self):
        config = SupervisorModeNodeConfig()
        assert config.prompt_override is None


# ---------------------------------------------------------------------------
# prompt_override alias
# ---------------------------------------------------------------------------


class TestPromptOverrideAlias:
    def test_prompt_override_sets_prompt(self):
        config = SupervisorModeNodeConfig(prompt_override="My custom prompt")
        assert config.prompt == "My custom prompt"

    def test_prompt_override_via_model_validate(self):
        config = SupervisorModeNodeConfig.model_validate(
            {"prompt_override": "Override text"}
        )
        assert config.prompt == "Override text"

    def test_explicit_prompt_wins_over_prompt_override(self):
        """When both prompt and prompt_override are supplied, prompt wins."""
        config = SupervisorModeNodeConfig(
            prompt="Explicit prompt", prompt_override="Override"
        )
        assert config.prompt == "Explicit prompt"

    def test_prompt_override_excluded_from_serialization(self):
        config = SupervisorModeNodeConfig(prompt_override="hidden")
        serialized = config.model_dump()
        assert "prompt_override" not in serialized

    def test_prompt_present_in_serialization_when_set_via_override(self):
        config = SupervisorModeNodeConfig(prompt_override="visible")
        serialized = config.model_dump()
        assert serialized["prompt"] == "visible"

    def test_prompt_override_none_does_not_overwrite_existing_prompt(self):
        config = SupervisorModeNodeConfig(prompt="keep me", prompt_override=None)
        assert config.prompt == "keep me"


# ---------------------------------------------------------------------------
# Numeric overrides
# ---------------------------------------------------------------------------


class TestSupervisorModeNodeConfigNumericOverrides:
    def test_llm_config_id_stored(self):
        config = SupervisorModeNodeConfig(llm_config_id=42)
        assert config.llm_config_id == 42

    def test_temperature_stored(self):
        config = SupervisorModeNodeConfig(temperature=0.3)
        assert config.temperature == pytest.approx(0.3)

    def test_max_tokens_stored(self):
        config = SupervisorModeNodeConfig(max_tokens=512)
        assert config.max_tokens == 512

    def test_model_name_stored(self):
        config = SupervisorModeNodeConfig(model_name="gpt-4o")
        assert config.model_name == "gpt-4o"


# ---------------------------------------------------------------------------
# model_validate round-trips
# ---------------------------------------------------------------------------


class TestSupervisorModeNodeConfigModelValidate:
    def test_full_dict_round_trip(self):
        data = {
            "llm_config_id": 7,
            "model_name": "claude-3",
            "prompt": "Be concise.",
            "temperature": 0.5,
            "max_tokens": 1024,
        }
        config = SupervisorModeNodeConfig.model_validate(data)
        assert config.llm_config_id == 7
        assert config.model_name == "claude-3"
        assert config.prompt == "Be concise."
        assert config.temperature == pytest.approx(0.5)
        assert config.max_tokens == 1024

    def test_empty_dict_gives_all_none(self):
        config = SupervisorModeNodeConfig.model_validate({})
        assert config.llm_config_id is None
        assert config.prompt is None
