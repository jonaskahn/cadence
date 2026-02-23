"""Plugin bundle creation and validation mixin."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

from cadence_sdk.registry.contracts import PluginContract
from cadence_sdk.utils.validation import validate_plugin_structure

from cadence.constants import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE
from cadence.infrastructure.plugins.plugin_settings_resolver import (
    PluginSettingsResolver,
)

if TYPE_CHECKING:
    from cadence.infrastructure.plugins.plugin_manager import SDKPluginBundle

logger = logging.getLogger(__name__)


class PluginBundleBuilderMixin(ABC):
    """Mixin for plugin bundle creation and validation.

    Requires self.get_adapter(), self.get_llm_factory(), self.get_bundle_cache(),
    and self.get_org_id().
    """

    @staticmethod
    def _validate_plugin(contract: PluginContract) -> None:
        """Validate plugin structure and custom dependencies.

        Raises:
            ValueError: If validation fails
        """
        is_valid, errors = validate_plugin_structure(contract.plugin_class)
        if not is_valid:
            raise ValueError(
                f"Plugin '{contract.pid}' validation failed: {'; '.join(errors)}"
            )

        if hasattr(contract.plugin_class, "validate_dependencies"):
            custom_errors = contract.plugin_class.validate_dependencies()
            if custom_errors:
                raise ValueError(
                    f"Plugin '{contract.pid}' dependency validation failed: "
                    f"{'; '.join(custom_errors)}"
                )

    @abstractmethod
    def get_bundle_cache(self):
        pass

    @abstractmethod
    def get_adapter(self):
        pass

    @abstractmethod
    def get_llm_factory(self):
        pass

    @abstractmethod
    def get_org_id(self) -> str:
        pass

    async def _create_bundle_with_cache(
        self,
        contract: PluginContract,
        settings_resolver: PluginSettingsResolver,
    ) -> SDKPluginBundle:
        """Create bundle, reusing SharedBundleCache for stateless plugins."""
        if not self.get_bundle_cache() or not contract.is_stateless:
            return await self._create_bundle(contract, settings_resolver)

        agent = contract.plugin_class.create_agent()
        resolved_settings = settings_resolver.resolve(
            contract.pid, contract.version, agent
        )
        adapter_type = getattr(
            self.get_adapter(), "framework_type", type(self.get_adapter()).__name__
        )

        async def bundle_factory():
            return await self._create_bundle(contract, settings_resolver)

        bundle, from_cache = await self.get_bundle_cache().get_or_create(
            plugin_pid=contract.pid,
            version=contract.version,
            settings=resolved_settings,
            adapter_type=adapter_type,
            is_stateless=contract.is_stateless,
            bundle_factory=bundle_factory,
        )
        if from_cache:
            logger.info(f"Reusing cached bundle: {contract.pid} v{contract.version}")
        return bundle

    async def _create_bundle(
        self, contract: PluginContract, settings_resolver: PluginSettingsResolver
    ) -> SDKPluginBundle:
        """Create a new plugin bundle with all resources."""
        from cadence.infrastructure.plugins.plugin_manager import SDKPluginBundle

        metadata = contract.plugin_class.get_metadata()
        agent = contract.plugin_class.create_agent()

        resolved_settings = settings_resolver.resolve(
            contract.pid, contract.version, agent
        )
        if hasattr(agent, "initialize"):
            agent.initialize(resolved_settings)

        uv_tools = agent.get_tools()
        orchestrator_tools = [
            self.get_adapter().uvtool_to_orchestrator(tool) for tool in uv_tools
        ]

        bound_model = await self._create_plugin_model(resolved_settings)

        bound_model = (
            self.get_adapter().bind_tools_to_model(bound_model, uv_tools)
            if bound_model is not None
            else None
        )

        tool_node = None
        if self.get_adapter().framework_type == "langgraph":
            tool_node = self.get_adapter().create_tool_node(uv_tools)

        return SDKPluginBundle(
            contract=contract,
            metadata=metadata,
            agent=agent,
            bound_model=bound_model,
            uv_tools=uv_tools,
            orchestrator_tools=orchestrator_tools,
            adapter=self.get_adapter(),
            tool_node=tool_node,
        )

    async def _create_plugin_model(self, resolved_settings: dict) -> Optional[object]:
        """Create a model for this plugin from its resolved settings.

        Returns None when no llm_config_id is available (e.g. supervisor mode
        where the supervisor model handles all tool dispatch).
        """
        llm_config_id = resolved_settings.get("llm_config_id")
        if not llm_config_id:
            return None
        return await self.get_llm_factory().create_model_by_id(
            org_id=self.get_org_id(),
            llm_config_id=llm_config_id,
            temperature=resolved_settings.get("temperature", DEFAULT_TEMPERATURE),
            max_tokens=resolved_settings.get("max_tokens", DEFAULT_MAX_TOKENS),
        )
