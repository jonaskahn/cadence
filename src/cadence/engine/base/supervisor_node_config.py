"""Shared node configuration model for supervisor orchestrators."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


class SupervisorModeNodeConfig(BaseModel):
    """Configuration for a single supervisor node.

    Attributes:
        llm_config_id: FK → OrganizationLLMConfig.id (must belong to same org).
            If None, falls back to the instance-level default_llm_config_id.
        model_name: Optional model name override for this node.
        prompt: Replaces the default prompt constant for this node.
            Must contain the same {placeholder} slots as the default prompt.
        prompt_override: Alias for prompt (accepted during deserialization).
        timeout: Per-node execution timeout in seconds. Overrides node_execution_timeout when set.
    """

    llm_config_id: Optional[int] = None
    model_name: Optional[str] = None
    prompt: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    timeout: Optional[int] = None
    prompt_override: Optional[str] = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def _apply_prompt_override(self) -> "SupervisorModeNodeConfig":
        if self.prompt_override is not None and self.prompt is None:
            self.prompt = self.prompt_override
        return self

    @classmethod
    def from_resolved_config(cls, config: Dict[str, Any]) -> "SupervisorModeNodeConfig":
        """Build a default node config from instance-level resolved config keys."""
        return cls(
            llm_config_id=config.get("default_llm_config_id"),
            model_name=config.get("default_model_name"),
            max_tokens=config.get("default_max_tokens"),
            temperature=config.get("default_temperature"),
            timeout=config.get("default_timeout"),
        )

    def merge(self, override: "SupervisorModeNodeConfig") -> "SupervisorModeNodeConfig":
        """Return a new config where non-None values in *override* win; self fills gaps."""
        result = SupervisorModeNodeConfig()
        result.llm_config_id = override.llm_config_id or self.llm_config_id
        result.model_name = override.model_name or self.model_name
        result.max_tokens = override.max_tokens or self.max_tokens
        result.temperature = override.temperature or self.temperature
        result.timeout = override.timeout or self.timeout
        result.prompt_override = override.prompt_override
        result.prompt = override.prompt
        return result
