"""Centralized registry for creating and managing LLM models across conversation roles.

Encapsulates all model creation logic with role-specific configurations.
Provides consistent model instantiation patterns and configuration management.
"""

from typing import Any

from cadence_sdk.base.loggable import Loggable

from ...config.settings import Settings
from ...infrastructure.llm.factory import LLMModelFactory
from ...infrastructure.plugins.sdk_manager import SDKPluginManager


class ConversationModelRegistry(Loggable):
    """Centralized registry for creating and managing LLM models across conversation roles.
    
    Encapsulates all model creation logic with role-specific configurations.
    Provides consistent model instantiation patterns and configuration management.
    
    Responsibilities:
    - Model instantiation for coordinator, suspend, and finalizer roles
    - Configuration application and validation
    - Model lifecycle management
    """

    def __init__(
        self,
        llm_factory: LLMModelFactory,
        settings: Settings,
        plugin_manager: SDKPluginManager
    ) -> None:
        super().__init__()
        self.llm_factory = llm_factory
        self.settings = settings
        self.plugin_manager = plugin_manager

    def create_coordinator_model(self) -> Any:
        """Create LLM model for coordinator with bound routing tools.
        
        The coordinator model is responsible for making routing decisions
        and needs access to all available plugin tools for coordination.
        
        Returns:
            Configured LLM model with bound coordinator tools
        """
        from ...infrastructure.llm.providers import ModelConfig

        control_tools = self.plugin_manager.get_coordinator_tools()

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
        coordinator_model = base_model.bind_tools(control_tools, parallel_tool_calls=False)
        
        self.logger.debug(f"Created coordinator model: {provider}/{model_name} with {len(control_tools)} tools")
        return coordinator_model

    def create_suspend_model(self) -> Any:
        """Create LLM model for suspend node with fallback to default.
        
        The suspend model handles graceful conversation termination when
        hop limits are exceeded or other suspension conditions are met.
        
        Returns:
            Configured LLM model for suspension handling
        """
        from ...infrastructure.llm.providers import ModelConfig

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

        suspend_model = self.llm_factory.create_base_model(model_config)
        
        self.logger.debug(f"Created suspend model: {provider}/{model_name}")
        return suspend_model

    def create_finalizer_model(self) -> Any:
        """Create LLM model for synthesizing final responses.
        
        The finalizer model is responsible for creating coherent final responses
        by synthesizing information gathered throughout the conversation.
        
        Returns:
            Configured LLM model for response finalization
        """
        from ...infrastructure.llm.providers import ModelConfig

        provider = self.settings.finalizer_llm_provider or self.settings.default_llm_provider
        model_name = self.settings.get_finalizer_provider_llm_model(provider)
        temperature = self.settings.finalizer_temperature
        max_tokens = self.settings.finalizer_max_tokens

        model_config = ModelConfig(
            provider=provider,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        finalizer_model = self.llm_factory.create_base_model(model_config)
        
        self.logger.debug(f"Created finalizer model: {provider}/{model_name}")
        return finalizer_model

    def recreate_all_models(self) -> dict:
        """Recreate all models with current configuration.
        
        Useful when plugin configuration changes or settings are updated.
        
        Returns:
            dict: Dictionary containing all recreated models
        """
        self.logger.debug("Recreating all conversation models...")
        
        models = {
            "coordinator": self.create_coordinator_model(),
            "suspend": self.create_suspend_model(),
            "finalizer": self.create_finalizer_model()
        }
        
        self.logger.info("All conversation models recreated successfully")
        return models

    def validate_model_configurations(self) -> dict:
        """Validate that all model configurations are properly set.
        
        Returns:
            dict: Validation results for each model type
        """
        validation_results = {
            "coordinator": {"valid": True, "issues": []},
            "suspend": {"valid": True, "issues": []},
            "finalizer": {"valid": True, "issues": []}
        }

        # Validate coordinator configuration
        coordinator_provider = self.settings.coordinator_llm_provider or self.settings.default_llm_provider
        if not self.settings.validate_llm_provider(coordinator_provider):
            validation_results["coordinator"]["valid"] = False
            validation_results["coordinator"]["issues"].append(f"Invalid provider: {coordinator_provider}")

        # Validate suspend configuration
        suspend_provider = self.settings.suspend_llm_provider or self.settings.default_llm_provider
        if not self.settings.validate_llm_provider(suspend_provider):
            validation_results["suspend"]["valid"] = False
            validation_results["suspend"]["issues"].append(f"Invalid provider: {suspend_provider}")

        # Validate finalizer configuration
        finalizer_provider = self.settings.finalizer_llm_provider or self.settings.default_llm_provider
        if not self.settings.validate_llm_provider(finalizer_provider):
            validation_results["finalizer"]["valid"] = False
            validation_results["finalizer"]["issues"].append(f"Invalid provider: {finalizer_provider}")

        return validation_results

    def get_model_info(self) -> dict:
        """Get information about current model configurations.
        
        Returns:
            dict: Information about each model type's configuration
        """
        return {
            "coordinator": {
                "provider": self.settings.coordinator_llm_provider or self.settings.default_llm_provider,
                "model": self.settings.get_default_provider_llm_model(
                    self.settings.coordinator_llm_provider or self.settings.default_llm_provider
                ),
                "temperature": self.settings.coordinator_temperature,
                "max_tokens": self.settings.coordinator_max_tokens,
                "tools_count": len(self.plugin_manager.get_coordinator_tools())
            },
            "suspend": {
                "provider": self.settings.suspend_llm_provider or self.settings.default_llm_provider,
                "model": self.settings.get_default_provider_llm_model(
                    self.settings.suspend_llm_provider or self.settings.default_llm_provider
                ),
                "temperature": self.settings.suspend_temperature,
                "max_tokens": self.settings.suspend_max_tokens
            },
            "finalizer": {
                "provider": self.settings.finalizer_llm_provider or self.settings.default_llm_provider,
                "model": self.settings.get_finalizer_provider_llm_model(
                    self.settings.finalizer_llm_provider or self.settings.default_llm_provider
                ),
                "temperature": self.settings.finalizer_temperature,
                "max_tokens": self.settings.finalizer_max_tokens
            }
        }
