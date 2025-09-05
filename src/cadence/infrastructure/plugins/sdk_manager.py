"""SDK plugin manager for dynamic agent discovery and lifecycle management.

Implements comprehensive SDK-based plugin discovery, validation, loading, and lifecycle
management with seamless LangGraph integration for the multi-agent system.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from langchain_core.tools import Tool, tool
from langgraph.prebuilt import ToolNode

from ...config.settings import settings
from ...core.schema import DynamicModelBinder

try:
    from cadence_sdk import BaseAgent, BasePlugin, ModelConfig, discover_plugins
    from cadence_sdk.utils import validate_plugin_structure

    try:
        from cadence_sdk.utils.validation import validate_plugin_structure_shallow as _sdk_validate_shallow
    except Exception:
        _sdk_validate_shallow = None
    from cadence_sdk.utils.directory_discovery import DirectoryPluginDiscovery

    SDK_AVAILABLE = True
except ImportError:
    discover_plugins = None
    BasePlugin = None
    BaseAgent = None
    validate_plugin_structure = None
    SDK_AVAILABLE = False

from cadence_sdk.base.loggable import Loggable

try:
    from cadence_sdk.utils.installers import install_packages as _sdk_install_packages
except Exception:
    _sdk_install_packages = None

from ..llm.factory import LLMModelFactory


class SDKPluginBundle(Loggable):
    """Container for a complete plugin with agent, model, tools, and LangGraph integration.

    This class encapsulates all components of a loaded plugin, providing a unified
    interface for plugin management and LangGraph integration. Each bundle contains
    the plugin contract, initialized agent, bound LLM model, and associated tools.
    """

    def __init__(
        self,
        contract: BasePlugin,
        agent,
        bound_model,
        tools: List[Tool],
    ):
        super().__init__()
        self.contract = contract
        self.metadata = contract.get_metadata()
        self.agent = agent
        self.bound_model = bound_model
        self.tools = tools

        @tool
        def back() -> str:
            """Return control back to the coordinator."""
            return "back"

        all_tools = tools + [back]
        self.tool_node = ToolNode(all_tools)
        self.agent_node = agent.create_agent_node()

    def get_graph_edges(self) -> Dict[str, Any]:
        """Generate LangGraph edge definitions for orchestrator routing"""
        normalized_agent_name = str.lower(self.metadata.name).replace(" ", "_")
        return {
            "conditional_edges": {
                f"{normalized_agent_name}_agent": {
                    "condition": self.agent.should_continue,
                    "mapping": {
                        "continue": f"{normalized_agent_name}_tools",
                        "back": "coordinator",
                    },
                }
            },
            "direct_edges": [(f"{normalized_agent_name}_tools", "coordinator")],
        }


class SDKPluginManager(Loggable):
    """Comprehensive plugin manager for Cadence's SDK-based multi-agent system"""

    def __init__(self, plugins_dirs: Union[str, List[str]], llm_factory: LLMModelFactory):
        super().__init__()
        self.plugins_dirs = self._normalize_plugin_directories(plugins_dirs)
        self.llm_factory = llm_factory

        if not SDK_AVAILABLE:
            raise RuntimeError("cadence_sdk is not available. Please install it: pip install cadence_sdk")

        self.plugin_bundles: Dict[str, SDKPluginBundle] = {}
        self.plugin_contracts: Dict[str, BasePlugin] = {}
        self.healthy_plugins: Set[str] = set()
        self.failed_plugins: Set[str] = set()
        self._dir_discovery = DirectoryPluginDiscovery()
        self._source_map: Dict[str, str] = {}
        self.model_binder = DynamicModelBinder()

    @staticmethod
    def _get_class_module_file(klass) -> Optional[Path]:
        """Best-effort resolve the filesystem path for a class' defining module."""
        try:
            import inspect

            file_path = inspect.getfile(klass)
            return Path(file_path).resolve() if file_path else None
        except Exception:
            pass
        try:
            import sys

            module_name = getattr(klass, "__module__", None)
            if module_name and module_name in sys.modules:
                module = sys.modules[module_name]
                module_file = getattr(module, "__file__", None)
                return Path(module_file).resolve() if module_file else None
        except Exception:
            pass
        return None

    @staticmethod
    def _normalize_plugin_directories(plugins_dirs: Union[str, List[str]]) -> List[Path]:
        """Convert plugins_dirs to a list of Path objects."""
        if isinstance(plugins_dirs, str):
            return [Path(plugins_dirs)]
        return [Path(dir_path) for dir_path in plugins_dirs]

    def load_directory_plugins(self) -> None:
        """Load directory-based plugin packages using DirectoryPluginDiscovery."""
        self._attach_uploaded_plugins_dir_to_directory_load()
        directories = [str(p) for p in self.plugins_dirs]
        try:
            count = self._dir_discovery.import_plugins_from_directories(directories)
            self.logger.debug(f"Directory discovery imported {count} plugin modules")
        except Exception as e:
            self.logger.error(f"Directory plugin discovery failed: {e}")

    def load_environment_plugins(self) -> int:
        """Discover and import pip-installed plugins first.

        Returns:
            int: Number of pip plugin packages imported
        """
        try:
            from cadence_sdk.utils import import_plugins_from_environment

            count = import_plugins_from_environment()
            self.logger.debug(f"Imported {count} pip plugin packages")
            return count
        except Exception as e:
            self.logger.warning(f"Pip plugin discovery unavailable or failed: {e}")
            return 0

    def discover_and_load_plugins(self) -> None:
        """Discover plugins from pip and local directories, then create bundles.

        Local directory plugins are loaded after pip-installed plugins so that
        if a plugin with the same metadata.name exists locally, it overrides
        the version provided by a pip-installed package (last registration wins).
        """
        self.load_environment_plugins()
        env_contracts_after_env_load = discover_plugins() or []
        env_plugin_names = {c.name for c in env_contracts_after_env_load}

        self.load_directory_plugins()
        contracts = discover_plugins()
        self.logger.debug(f"Discovered {len(contracts)} SDK-registered plugins")
        try:
            from ...config.settings import settings

            uploaded_root = (Path(settings.storage_root) / "uploaded").resolve()
            configured_dirs = [Path(p).resolve() for p in settings.plugins_dir]
        except Exception:
            uploaded_root = None
            configured_dirs = []
        self._source_map.clear()
        for contract in contracts:
            if contract.name in env_plugin_names:
                src = "environment"
                self._source_map[contract.name] = src
                self.logger.debug(f"Source map (env priority): {contract.name} src={src}")
                continue

            src = "environment"
            try:
                mod_path = self._get_class_module_file(contract.plugin_class)
                if mod_path:
                    if uploaded_root is not None:
                        try:
                            _ = mod_path.relative_to(uploaded_root)
                            src = "storage"
                        except Exception:
                            src = None
                    elif src is None:
                        is_dir = False
                        for d in configured_dirs:
                            try:
                                _ = mod_path.relative_to(d)
                                is_dir = True
                                break
                            except Exception:
                                continue
                        src = "directory" if is_dir else "environment"

                self.logger.debug(f"Source map: {contract.name} file={str(mod_path) if mod_path else 'N/A'} src={src}")
            except Exception as e:
                self.logger.debug(f"Source map detection failed for {contract.name}: {e}")
            self._source_map[contract.name] = src

        for contract in contracts:
            try:
                self._create_plugin_bundle(contract)
            except Exception as e:
                self.logger.error(f"Failed to create bundle for {contract.name}: {e}")
                self.failed_plugins.add(contract.name)

    def _attach_uploaded_plugins_dir_to_directory_load(self) -> None:
        """Load plugins from the uploaded plugins directory."""
        try:
            store_plugin_dir = Path(settings.storage_root) / "uploaded"

            if store_plugin_dir.exists():
                str_dirs = [str(p) for p in self.plugins_dirs]
                if str(store_plugin_dir) not in str_dirs:
                    self.plugins_dirs.insert(0, store_plugin_dir)
                    self.logger.debug(f"Added uploaded plugins directory with precedence: {store_plugin_dir}")
        except Exception as e:
            self.logger.warning(f"Failed to load uploaded plugins: {e}")

    def _create_plugin_bundle(self, contract: BasePlugin) -> bool:
        """Create a plugin bundle from an SDK contract."""
        try:
            metadata = contract.get_metadata()
            plugin_name = metadata.name

            self.logger.debug(f"Creating plugin bundle for: {plugin_name}")

            if not self._validate_plugin(contract, plugin_name):
                return False

            agent = contract.create_agent()
            model_config = self._create_model_config(metadata)
            try:
                base_model = self.llm_factory.create_base_model(model_config)
            except Exception as e:
                self.logger.warning(
                    f"Agent [ {agent.metadata.name} ] failed to create agent AI model. Due {e}. Falling back to default model"
                )
                base_model = self.llm_factory.create_base_model(self.llm_factory.get_default_model_config())

            tools = agent.get_tools()

            bound_model = agent.bind_model(base_model)
            agent.initialize()

            bundle = SDKPluginBundle(contract=contract, agent=agent, bound_model=bound_model, tools=tools)

            if hasattr(metadata, "response_schema") and metadata.response_schema:
                self.model_binder.register_plugin(plugin_name, metadata.response_schema)
                self.logger.debug(f"Registered response schema for plugin: {plugin_name}")

            self.plugin_bundles[plugin_name] = bundle
            self.plugin_contracts[plugin_name] = contract
            self.healthy_plugins.add(plugin_name)

            self._log_bundle_creation_success(plugin_name, agent, tools, metadata)
            return True

        except Exception as e:
            self.logger.error(f"Failed to create plugin bundle for {contract.name}: {e}")
            return False

    def _validate_plugin(self, contract: BasePlugin, plugin_name: str) -> bool:
        """Validate plugin by shape, install dependencies, then fully validate."""
        try:
            if _sdk_validate_shallow is not None:
                errors = _sdk_validate_shallow(contract.plugin_class)
                if errors:
                    self.logger.error(f"Plugin validation failed for {plugin_name}: {errors}")
                    return False
        except Exception as e:
            self.logger.error(f"Shallow validation failed for {plugin_name}: {e}")
            return False

        try:
            metadata = contract.get_metadata()
            deps = list(getattr(metadata, "dependencies", []) or [])
            if deps:
                self.logger.info(f"Installing declared dependencies for {plugin_name}: {', '.join(deps)}")
                is_debug = os.environ.get("CADENCE_DEBUG", "False") == "True"
                if _sdk_install_packages is None:
                    self.logger.warning(
                        "Dependency installer unavailable (cadence_sdk.utils.installers). Skipping runtime install;"
                        " ensure dependencies are pre-installed."
                    )
                else:
                    ok, log = _sdk_install_packages(
                        deps,
                        prefer_poetry=True,
                        verbose=is_debug,
                        on_output=(lambda line: self.logger.debug(f"[deps] {line}") if is_debug else None),
                    )
                    if not ok:
                        self.logger.error(f"Failed to install dependencies for {plugin_name}: {deps}\n{log}")
                        return False
                    if is_debug:
                        self.logger.debug(
                            f"Successfully installed dependencies for {plugin_name}: {', '.join(deps)}\n{log}"
                        )
                    else:
                        self.logger.info(f"Successfully installed dependencies for {plugin_name}: {', '.join(deps)}")
        except Exception as e:
            self.logger.error(f"Error installing dependencies for {plugin_name}: {e}")
            return False

        if validate_plugin_structure:
            errors = validate_plugin_structure(contract.plugin_class)
            if errors:
                self.logger.error(f"Plugin validation failed for {plugin_name}: {errors}")
                return False

        dep_errors = contract.validate_dependencies()
        if dep_errors:
            self.logger.error(f"Plugin dependencies failed for {plugin_name}: {dep_errors}")
            return False

        return True

    @staticmethod
    def _create_model_config(metadata):
        """Create a model configuration from plugin metadata."""
        from ..llm.providers import ModelConfig

        model_config = metadata.get_model_config()
        return ModelConfig(
            provider=model_config.provider,
            model_name=model_config.model_name,
            temperature=model_config.temperature,
            max_tokens=model_config.max_tokens,
            additional_params=model_config.additional_params,
        )

    def _log_bundle_creation_success(self, plugin_name: str, agent, tools: List[Tool], metadata):
        """Log successful plugin bundle creation."""
        self.logger.info(f"Successfully created plugin bundle: {plugin_name} v{metadata.version}")
        self.logger.debug(f"  - Agent: {type(agent).__name__}")
        self.logger.debug(f"  - Tools: {len(tools)} tools")
        self.logger.debug(f"  - Capabilities: {metadata.capabilities}")

    def get_plugin_bundle(self, name: str) -> Optional[SDKPluginBundle]:
        """Get a plugin bundle by name."""
        return self.plugin_bundles.get(name)

    def get_available_plugins(self) -> List[str]:
        """List names of successfully loaded plugin bundles."""
        return list(self.plugin_bundles.keys())

    def get_plugin_routing_info(self) -> Dict[str, str]:
        """Return short routing descriptions for coordinator prompts."""
        return {
            name: f"{bundle.metadata.description}. Capabilities only for: {', '.join(bundle.metadata.capabilities)}"
            for name, bundle in self.plugin_bundles.items()
        }

    def get_plugin_source(self, name: str) -> str:
        return self._source_map.get(name, "unknown")

    def perform_health_checks(self) -> Dict[str, bool]:
        """Perform health checks on all plugin bundles."""
        results = {}
        for plugin_name, contract in self.plugin_contracts.items():
            try:
                dep_errors = contract.validate_dependencies()
                deps_ok = len(dep_errors) == 0

                try:
                    health_status = contract.health_check()
                except Exception as e:
                    health_status = {
                        "healthy": False,
                        "details": f"Health check execution failed: {e}",
                        "error": str(e),
                    }

                checks = health_status.get("checks") or {}
                if not isinstance(checks, dict):
                    checks = {"_raw_checks": checks}
                checks["dependencies"] = "OK" if deps_ok else "; ".join(dep_errors)
                health_status["checks"] = checks

                if not deps_ok:
                    health_status["healthy"] = False

                is_healthy = health_status.get("healthy", False)
                results[plugin_name] = is_healthy

                if is_healthy:
                    self.healthy_plugins.add(plugin_name)
                    self.failed_plugins.discard(plugin_name)
                else:
                    self.failed_plugins.add(plugin_name)
                    self.healthy_plugins.discard(plugin_name)

                self.logger.debug(f"Health check for {plugin_name}: {health_status}")

            except Exception as e:
                self.logger.error(f"Health check failed for {plugin_name}: {e}")
                results[plugin_name] = False
                self.failed_plugins.add(plugin_name)

        return results

    def get_coordinator_tools(self) -> List[Tool]:
        """Create routing tools used by the coordinator for control flow.

        Returns proper callable tools with docstrings so they convert to
        `StructuredTool`s reliably across langchain versions.
        """
        control_tools: List[Tool] = []

        def _make_goto_tool(name: str, description: str) -> Tool:
            def _goto() -> str:
                """Route control to an agent by name."""
                return name

            _goto.__name__ = f"goto_{name}"
            _goto.__doc__ = f"{description or _goto.__doc__}. Args: No parameters"
            return tool(_goto)

        for plugin_name in self.get_available_plugins():
            bundle = self.plugin_bundles.get(plugin_name)
            capabilities = ", ".join(bundle.metadata.capabilities) if bundle else ""
            desc = f"{bundle.metadata.description}" + (
                f". The agent capabilities are only for: {capabilities}" if capabilities else ""
            )
            control_tools.append(_make_goto_tool(plugin_name, desc))

        def goto_synthesize() -> str:
            """Route to synthesizer for final response generation.

            Use when the conversation is complete and ready for synthesis:
            - User query is fully addressed with sufficient information
            - Simple queries requiring direct response (greetings, basic facts)
            - Translation or clarification requests
            - No specialized agent is needed or available
            - User must provide additional input (clarification, missing data, choices)
            """
            return "synthesize"

        control_tools.append(tool(goto_synthesize))
        return control_tools

    def reload_plugins(self) -> None:
        """Reload all plugins by clearing and rediscovering."""
        self.logger.info("Reloading all plugins...")

        try:
            from cadence_sdk import get_plugin_registry
            from cadence_sdk.utils import reset_environment_discovery

            reset_environment_discovery()

            if hasattr(self, "_dir_discovery") and self._dir_discovery:
                self._dir_discovery.reset()

            registry = get_plugin_registry()
            if registry:
                registry.clear_all()
        except Exception as e:
            self.logger.warning(f"Failed to reset discovery or registry state: {e}")
        self._clear_plugin_state()
        self.discover_and_load_plugins()
        self.perform_health_checks()

        self.logger.info(f"Plugin reload complete. Loaded {len(self.plugin_bundles)} plugins")

    def _clear_plugin_state(self):
        """Clear all plugin-related state."""
        self.plugin_bundles.clear()
        self.plugin_contracts.clear()
        self.healthy_plugins.clear()
        self.failed_plugins.clear()

        self.model_binder.clear_cache()

    def get_model_binder(self) -> DynamicModelBinder:
        """Get the dynamic model binder for structured output."""
        return self.model_binder
