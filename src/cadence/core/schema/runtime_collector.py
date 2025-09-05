"""Runtime schema collection and dynamic Union binding for plugin responses."""

from typing import Any, Dict, List, Optional, Type, get_type_hints

from cadence_sdk.base.loggable import Loggable
from typing_extensions import Annotated, TypedDict


class RuntimeSchemaCollector(Loggable):
    """Collects plugin schemas at runtime and creates dynamic Union types."""

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

    def _create_prefixed_schema(self, plugin_name: str, schema: Type[TypedDict]) -> Dict[str, Any]:
        """Create a schema definition with plugin name prefixed fields, preserving Annotated descriptions."""
        # Use __annotations__ directly to preserve Annotated metadata
        original_annotations = schema.__annotations__
        prefixed_annotations = {}

        for field_name, field_type in original_annotations.items():
            prefixed_field_name = f"{plugin_name}_{field_name}"
            # Preserve the original field type (including Annotated metadata)
            prefixed_annotations[prefixed_field_name] = field_type

        return {
            "plugin_name": plugin_name,
            "original_schema": schema,
            "prefixed_annotations": prefixed_annotations,
            "class_name": f"{plugin_name.title()}Response",
        }

    def extract_plugin_data(self, structured_response: Dict[str, Any], plugin_name: str) -> Dict[str, Any]:
        """Extract original field values from prefixed structured response."""
        plugin_data = {}
        prefix = f"{plugin_name}_"

        for key, value in structured_response.items():
            if key.startswith(prefix):
                original_field_name = key[len(prefix) :]
                plugin_data[original_field_name] = value

        return plugin_data

    def create_dynamic_union(self, active_plugins: Optional[List[str]] = None) -> Type:
        """Create Union type from registered schemas with plugin name prefixed fields."""
        relevant_schemas = (
            {name: schema for name, schema in self.plugin_schemas.items() if name in active_plugins}
            if active_plugins
            else self.plugin_schemas
        )

        if not relevant_schemas:

            class TextResponse(TypedDict):
                text: str

            return TextResponse

        cache_key = "_".join(sorted(relevant_schemas.keys()))
        if cache_key in self._union_cache:
            return self._union_cache[cache_key]

        combined_annotations = {}
        for plugin_name, schema in relevant_schemas.items():
            prefixed_schema_info = self._create_prefixed_schema(plugin_name, schema)
            combined_annotations.update(prefixed_schema_info["prefixed_annotations"])

        class CombinedResponse(TypedDict, total=False):
            pass

        CombinedResponse.__annotations__ = combined_annotations
        self._union_cache[cache_key] = CombinedResponse
        return CombinedResponse

    def create_final_response_schema(self, active_plugins: Optional[List[str]] = None) -> Type[TypedDict]:
        """Create final response schema with dynamic Union."""
        additional_data_type = self.create_dynamic_union(active_plugins)

        class FinalResponse(TypedDict):
            response: Annotated[str, "Main response content in markdown format"]
            additional_data: List[additional_data_type]

        return FinalResponse


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
            final_schema = self.collector.create_final_response_schema(plugins_with_schemas)

            try:
                structured_llm = llm.with_structured_output(final_schema)
                self._bound_models[plugin_key] = structured_llm
                self.logger.debug(f"Created structured model for plugins: {plugins_with_schemas}")
            except Exception as e:
                self.logger.warning(f"Failed to bind structured output: {e}")
                self._bound_models[plugin_key] = llm
                return llm, False

        return self._bound_models[plugin_key], True

    def extract_plugin_data(self, structured_response: Dict[str, Any], plugin_name: str) -> Dict[str, Any]:
        """Extract original field values from prefixed structured response."""
        return self.collector.extract_plugin_data(structured_response, plugin_name)

    def clear_cache(self) -> None:
        """Clear all cached bound models."""
        self._bound_models.clear()
        self.collector._union_cache.clear()
