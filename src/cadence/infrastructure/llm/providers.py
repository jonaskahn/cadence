"""LLM provider registry and configuration classes.

Defines provider-specific configuration and instantiation for
all supported LLM providers. Each provider class knows how to
create model instances for the target framework:
  - LangGraph/LangChain (BaseChatModel)
  - OpenAI Agents SDK (OpenAIChatCompletionsModel / LitellmModel)
  - Google ADK (Gemini string / LiteLlm)
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type

from langchain_core.language_models import BaseChatModel
from pydantic import SecretStr


class LLMProvider(ABC):
    """Base class for LLM provider configuration.

    Each provider implementation knows how to create models for one or
    more orchestration frameworks. Methods raise NotImplementedError by
    default; subclasses override what they support.
    """

    @staticmethod
    @abstractmethod
    def create_model(
        model_name: str,
        api_key: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> BaseChatModel:
        """Create a LangChain/LangGraph chat model instance."""
        pass

    @staticmethod
    def create_openai_agents_model(
        model_name: str,
        api_key: str,
        base_url: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """Create an OpenAI Agents SDK model instance.

        Raises:
            NotImplementedError: If the provider does not support OpenAI Agents SDK.
        """
        raise NotImplementedError(
            "This provider does not support the OpenAI Agents SDK."
        )

    @staticmethod
    def create_google_adk_model(
        model_name: str,
        api_key: str,
        **kwargs,
    ) -> Any:
        """Create a Google ADK model instance.

        Raises:
            NotImplementedError: If the provider does not support Google ADK.
        """
        raise NotImplementedError("This provider does not support the Google ADK.")


class OpenAIProvider(LLMProvider):
    """OpenAI provider (GPT-4, GPT-3.5, etc.).

    Framework support:
      - LangGraph  : ChatOpenAI
      - OpenAI Agents: OpenAIChatCompletionsModel
    """

    @staticmethod
    def create_model(
        model_name: str,
        api_key: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        base_url: Optional[str] = None,
        **kwargs,
    ) -> BaseChatModel:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model_name,
            api_key=SecretStr(api_key),
            temperature=temperature,
            max_tokens=max_tokens,
            base_url=base_url,
            **kwargs,
        )

    @staticmethod
    def create_openai_agents_model(
        model_name: str,
        api_key: str,
        base_url: Optional[str] = None,
        **kwargs,
    ) -> Any:
        from agents import OpenAIChatCompletionsModel
        from openai import AsyncOpenAI

        return OpenAIChatCompletionsModel(
            model=model_name,
            openai_client=AsyncOpenAI(api_key=api_key, base_url=base_url),
        )


class AnthropicProvider(LLMProvider):
    """Anthropic provider (Claude models).

    Framework support:
      - LangGraph: ChatAnthropic
    """

    @staticmethod
    def create_model(
        model_name: str,
        api_key: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> BaseChatModel:
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model_name,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )


class GoogleProvider(LLMProvider):
    """Google AI provider (Gemini models).

    Framework support:
      - LangGraph  : ChatGoogleGenerativeAI
      - Google ADK : native Gemini model name (ADK resolves it internally)
    """

    @staticmethod
    def create_model(
        model_name: str,
        api_key: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> BaseChatModel:
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=temperature,
            max_output_tokens=max_tokens,
            **kwargs,
        )

    @staticmethod
    def create_google_adk_model(
        model_name: str,
        api_key: str,
        **kwargs,
    ) -> Any:
        """Return the Gemini model name; Google ADK resolves it natively."""
        return model_name


class AzureProvider(LLMProvider):
    """Azure OpenAI provider.

    Framework support:
      - LangGraph: AzureChatOpenAI
    """

    @staticmethod
    def create_model(
        model_name: str,
        api_key: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        azure_endpoint: Optional[str] = None,
        deployment_name: Optional[str] = None,
        api_version: str = "2024-02-15-preview",
        **kwargs,
    ) -> BaseChatModel:
        from langchain_openai import AzureChatOpenAI

        return AzureChatOpenAI(
            azure_deployment=deployment_name or model_name,
            azure_endpoint=azure_endpoint,
            api_key=SecretStr(api_key),
            api_version=api_version,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )


class GroqProvider(LLMProvider):
    """Groq provider (fast inference).

    Framework support:
      - LangGraph: ChatGroq
    """

    @staticmethod
    def create_model(
        model_name: str,
        api_key: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> BaseChatModel:
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=model_name,
            api_key=SecretStr(api_key),
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI-compatible / LiteLLM provider (custom endpoints).

    Framework support:
      - LangGraph    : ChatOpenAI with custom base_url
      - OpenAI Agents: LitellmModel
      - Google ADK   : google.adk.models.lite_llm.LiteLlm
    """

    @staticmethod
    def create_model(
        model_name: str,
        api_key: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        base_url: Optional[str] = None,
        **kwargs,
    ) -> BaseChatModel:
        from langchain_openai import ChatOpenAI

        if not base_url:
            raise ValueError("base_url is required for OpenAI-compatible provider")

        return ChatOpenAI(
            model=model_name,
            api_key=SecretStr(api_key),
            temperature=temperature,
            max_tokens=max_tokens,
            base_url=base_url,
            **kwargs,
        )

    @staticmethod
    def create_openai_agents_model(
        model_name: str,
        api_key: str,
        base_url: Optional[str] = None,
        **kwargs,
    ) -> Any:
        from agents.extensions.models.litellm_model import LitellmModel

        return LitellmModel(model=model_name, api_key=api_key, base_url=base_url)

    @staticmethod
    def create_google_adk_model(
        model_name: str,
        api_key: str,
        base_url: Optional[str] = None,
        **kwargs,
    ) -> Any:
        from google.adk.models.lite_llm import LiteLlm

        return LiteLlm(model=model_name, api_key=api_key)


PROVIDER_REGISTRY: Dict[str, Type[LLMProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "google": GoogleProvider,
    "azure": AzureProvider,
    "groq": GroqProvider,
    "openai_compatible": OpenAICompatibleProvider,
}


def get_provider_class(provider_name: str) -> Type[LLMProvider]:
    """Get provider class by name.

    Args:
        provider_name: Provider identifier

    Returns:
        LLMProvider class

    Raises:
        ValueError: If provider not found
    """
    provider_class = PROVIDER_REGISTRY.get(provider_name.lower())

    if provider_class is None:
        available = ", ".join(PROVIDER_REGISTRY.keys())
        raise ValueError(
            f"Unknown provider: {provider_name}. Available providers: {available}"
        )

    return provider_class


def register_provider(name: str, provider_class: Type[LLMProvider]) -> None:
    """Register custom provider.

    Args:
        name: Provider identifier
        provider_class: LLMProvider implementation
    """
    PROVIDER_REGISTRY[name.lower()] = provider_class
