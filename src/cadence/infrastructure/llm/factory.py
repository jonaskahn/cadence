"""LLM model factory with BYOK (Bring Your Own Key).

Creates LLM model instances from tenant-provided OrganizationLLMConfig records.
The platform provides NO default API keys — tenants must provide their own.
All model creation is id-based: callers supply an OrganizationLLMConfig.id and
the factory enforces that the config belongs to the requesting org.

Supported frameworks:
  - Framework.LANGGRAPH     → LangChain BaseChatModel  (all providers)
  - Framework.OPENAI_AGENTS → OpenAI Agents SDK model  (openai, openai_compatible)
  - Framework.GOOGLE_ADK    → Google ADK model         (google, openai_compatible)
"""

from enum import Enum
from typing import Any

from cadence.constants import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE
from cadence.infrastructure.persistence.postgresql.models import OrganizationLLMConfig
from cadence.repository.organization_llm_config_repository import (
    OrganizationLLMConfigRepository,
)

from .providers import get_provider_class


class Framework(str, Enum):
    """Target orchestration framework for model creation."""

    LANGGRAPH = "langgraph"
    OPENAI_AGENTS = "openai_agents"
    GOOGLE_ADK = "google_adk"


class LLMModelFactory:
    """Factory for creating LLM model instances with BYOK.

    Resolves model configuration from OrganizationLLMConfig records by ID,
    enforces tenant isolation, and delegates model construction to the
    appropriate provider based on the requested framework.

    Attributes:
        llm_config_repo: Repository for LLM configurations
    """

    def __init__(self, llm_config_repo: OrganizationLLMConfigRepository):
        self.llm_config_repo = llm_config_repo

    async def create_model_by_id(
        self,
        org_id: str,
        llm_config_id: int,
        model_name: str,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        framework: Framework = Framework.LANGGRAPH,
    ) -> Any:
        """Create a model instance from an OrganizationLLMConfig record.

        Args:
            org_id: Organization identifier (enforces tenant isolation)
            llm_config_id: OrganizationLLMConfig primary key
            model_name: Model identifier to use (e.g. "gpt-4o")
            framework: Target orchestration framework
            temperature: Sampling temperature (LangGraph only)
            max_tokens: Maximum tokens in response (LangGraph only)

        Returns:
            Framework-specific model instance:
              - Framework.LANGGRAPH     → BaseChatModel
              - Framework.OPENAI_AGENTS → OpenAI Agents SDK model
              - Framework.GOOGLE_ADK    → Google ADK model

        Raises:
            ValueError: If config not found, deleted, or belongs to another org
            NotImplementedError: If the provider does not support the framework
        """
        config = await self._resolve_config(org_id, llm_config_id)
        provider_class = get_provider_class(config.provider)
        api_key = self._decrypt_api_key(config.api_key)
        extra = config.additional_config or {}

        if framework == Framework.LANGGRAPH:
            return provider_class.create_model(
                model_name=model_name,
                api_key=api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                base_url=config.base_url,
                **extra,
            )

        if framework == Framework.OPENAI_AGENTS:
            return provider_class.create_openai_agents_model(
                model_name=model_name,
                api_key=api_key,
                base_url=config.base_url,
                **extra,
            )

        if framework == Framework.GOOGLE_ADK:
            return provider_class.create_google_adk_model(
                model_name=model_name,
                api_key=api_key,
                base_url=config.base_url,
                **extra,
            )

        raise ValueError(f"Unknown framework: {framework}")

    async def _resolve_config(
        self, org_id: str, llm_config_id: int
    ) -> OrganizationLLMConfig:
        """Fetch and validate an LLM config, enforcing tenant isolation.

        Args:
            org_id: Requesting organization's ID
            llm_config_id: Config primary key

        Returns:
            OrganizationLLMConfig record

        Raises:
            ValueError: If config is missing, deleted, or owned by another org
        """
        config = await self.llm_config_repo.get_by_id(llm_config_id)
        if not config or str(config.org_id) != str(org_id) or config.is_deleted:
            raise ValueError(f"LLM config {llm_config_id} not found for org {org_id}")
        return config

    def _decrypt_api_key(self, encrypted_key: str) -> str:
        """Decrypt API key from storage.

        For MVP this is a pass-through. In production implement proper
        decryption using a key management service.
        """
        return encrypted_key
