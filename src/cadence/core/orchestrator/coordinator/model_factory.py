"""Model factory for creating different LLM models for coordinator components."""

from ....infrastructure.llm.providers import ModelConfig


class CoordinatorModelFactory:
    """Factory for creating LLM models for different coordinator components."""

    def __init__(self, llm_factory, settings):
        """Initialize with LLM factory and settings."""
        self.llm_factory = llm_factory
        self.settings = settings

    def create_coordinator_model(self, plugin_manager):
        """Create LLM model for coordinator with bound routing tools."""
        control_tools = plugin_manager.get_coordinator_tools()

        provider = self.settings.coordinator_llm_provider or self.settings.default_llm_provider
        model_name = self.settings.get_default_provider_llm_model(provider)
        temperature = self.settings.coordinator_temperature
        max_tokens = self.settings.coordinator_max_tokens

        model_config = ModelConfig(
            provider=provider,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        base_model = self.llm_factory.create_base_model(model_config)
        return base_model.bind_tools(control_tools, parallel_tool_calls=self.settings.coordinator_parallel_tool_calls)

    def create_suspend_model(self):
        """Create LLM model for suspend node with fallback to default."""
        provider = self.settings.suspend_llm_provider or self.settings.default_llm_provider
        model_name = self.settings.get_default_provider_llm_model(provider)
        temperature = self.settings.suspend_temperature
        max_tokens = self.settings.suspend_max_tokens

        model_config = ModelConfig(
            provider=provider,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return self.llm_factory.create_base_model(model_config)

    def create_synthesizer_model(self):
        """Create LLM model for synthesizing final responses."""
        provider = self.settings.synthesizer_llm_provider or self.settings.default_llm_provider
        model_name = self.settings.get_synthesizer_provider_llm_model(provider)
        temperature = self.settings.synthesizer_temperature
        max_tokens = self.settings.synthesizer_max_tokens

        model_config = ModelConfig(
            provider=provider,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return self.llm_factory.create_base_model(model_config)
