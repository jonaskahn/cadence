"""Runtime schema collection and dynamic per-plugin mapping for plugin responses."""

from typing import Any, Dict, List, Optional, Type

from cadence_sdk.base.loggable import Loggable
from typing_extensions import Annotated, TypedDict


class RuntimeSchemaCollector(Loggable):
    """Collects plugin schemas at runtime and creates dynamic per-plugin mappings."""

    def __init__(self):
        super().__init__()
        self.plugin_schemas: Dict[str, Type[TypedDict]] = {}
        self._union_cache: Dict[str, Type] = {}

    def register_plugin_schema(self, plugin_name: str, schema: Type[TypedDict]) -> None:
        """Register a plugin's response schema at runtime."""
        self.plugin_schemas[plugin_name] = schema
        self._union_cache.clear()
        self.logger.debug(f"Registered schema for plugin: {plugin_name}")

    def unregister_plugin_schema(self, plugin_name: str) -> None:
        """Remove a plugin's schema for plugin unloading."""
        if plugin_name in self.plugin_schemas:
            del self.plugin_schemas[plugin_name]
            self._union_cache.clear()
            self.logger.debug(f"Unregistered schema for plugin: {plugin_name}")

    def _create_brief_data_mapping(self, relevant_schemas: Dict[str, Type[TypedDict]]) -> Type[TypedDict]:
        """Create a TypedDict where each key is a plugin name mapping to List[schema]."""
        if not relevant_schemas:

            class AdditionalData(TypedDict, total=False):
                pass

            return AdditionalData

        annotations: Dict[str, Any] = {}
        for plugin_name, schema in relevant_schemas.items():
            # Strict schema binding: value type is List[PluginSchema]
            annotations[plugin_name] = List[schema]  # type: ignore[valid-type]

        class AdditionalData(TypedDict, total=False):
            pass

        AdditionalData.__annotations__ = annotations
        return AdditionalData

    def extract_plugin_data(self, structured_response: Dict[str, Any], plugin_name: str) -> List[Dict[str, Any]]:
        """Return list of items for a specific plugin from brief_data mapping."""
        brief_data = structured_response.get("brief_data", {}) or {}
        if isinstance(brief_data, dict):
            items = brief_data.get(plugin_name, [])
            return items if isinstance(items, list) else []
        return []

    def create_brief_data_schema(self, active_plugins: Optional[List[str]] = None) -> Type[TypedDict]:
        """Create per-plugin mapping schema: { plugin_name: List[PluginSchema] }."""
        relevant_schemas = (
            {name: schema for name, schema in self.plugin_schemas.items() if name in active_plugins}
            if active_plugins
            else self.plugin_schemas
        )

        cache_key = "map_" + "_".join(sorted(relevant_schemas.keys())) if relevant_schemas else "map_empty"
        if cache_key in self._union_cache:
            return self._union_cache[cache_key]

        brief_data_td = self._create_brief_data_mapping(relevant_schemas)
        self._union_cache[cache_key] = brief_data_td
        return brief_data_td

    def create_response_schema(self, active_plugins: Optional[List[str]] = None) -> Type[TypedDict]:
        """Create final response schema with per-plugin brief_data mapping."""
        ADDITIONAL_RESPONSE_SCHEMA = self.create_brief_data_schema(active_plugins)

        class DefaultResponseSchema(TypedDict):
            response: Annotated[str, "Main response content in markdown format"]
            brief_data: ADDITIONAL_RESPONSE_SCHEMA

        return DefaultResponseSchema


class DynamicModelBinder(Loggable):
    """Binds dynamic schemas to LangChain models for structured output."""

    def __init__(self):
        super().__init__()
        self.collector = RuntimeSchemaCollector()
        self._bound_models: Dict[str, Any] = {}

    def register_plugin(self, plugin_name: str, schema: Type[TypedDict]) -> None:
        """Register plugin schema and invalidate cached models."""
        self.collector.register_plugin_schema(plugin_name, schema)
        self._bound_models.clear()

    def get_structured_model(self, llm, active_plugins: List[str]) -> tuple[Any, bool]:
        """Get LangChain model with dynamic schema bound for active plugins."""
        plugins_with_schemas = [p for p in active_plugins if p in self.collector.plugin_schemas]

        if not plugins_with_schemas:
            return llm, False

        plugin_key = "_".join(sorted(plugins_with_schemas))

        if plugin_key not in self._bound_models:
            final_schema = self.collector.create_response_schema(plugins_with_schemas)

            try:
                structured_llm = llm.with_structured_output(final_schema)
                self._bound_models[plugin_key] = structured_llm
                self.logger.debug(f"Created structured model for plugins: {plugins_with_schemas}")
            except Exception as e:
                self.logger.warning(f"Failed to bind structured output: {e}")
                self._bound_models[plugin_key] = llm
                return llm, False

        return self._bound_models[plugin_key], True

    def extract_plugin_data(self, structured_response: Dict[str, Any], plugin_name: str) -> List[Dict[str, Any]]:
        """Return list of items for a specific plugin from brief_data mapping."""
        return self.collector.extract_plugin_data(structured_response, plugin_name)

    def clear_cache(self) -> None:
        """Clear all cached bound models."""
        self._bound_models.clear()
        self.collector._union_cache.clear()
