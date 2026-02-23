# Plugin Discovery & Bundling

The Cadence backend's `SDKPluginManager` uses the SDK's discovery utilities to find plugin packages on the filesystem,
validate them, and assemble a complete `SDKPluginBundle` for each active plugin.

Source files:

- `sdk/src/cadence_sdk/utils/directory_discovery.py`
- `sdk/src/cadence_sdk/utils/validation.py`
- `sdk/src/cadence_sdk/utils/installers.py`
- `src/cadence/infrastructure/plugins/plugin_manager.py`
- `src/cadence/infrastructure/plugins/plugin_bundle_builder.py`
- `src/cadence/infrastructure/plugins/plugin_loader.py`

---

## Discovery flow

```mermaid
flowchart TD
    A[SDKPluginManager.load_plugins] --> B[PluginLoaderMixin.discover_plugins]
    B --> C1[Tenant directory\n{root}/{org_id}/]
    B --> C2[System directory]
    B --> C3[Environment\npip-installed packages]
    C1 & C2 --> D[DirectoryPluginDiscovery.discover]
    D --> E[import plugin.py\nextract BasePlugin subclass]
    E --> F[register_plugin → PluginRegistry]
    F --> G[_validate_plugin]
    G --> H[_create_bundle_with_cache]
    H --> I[SDKPluginBundle]
```

---

## DirectoryPluginDiscovery

`sdk/src/cadence_sdk/utils/directory_discovery.py`

```python
from cadence_sdk import DirectoryPluginDiscovery, discover_plugins

# Instance API
discovery = DirectoryPluginDiscovery(
    search_paths=["/plugins/tenant", "/plugins/system"],
    auto_register=True,   # default; registers each found class with PluginRegistry
)
contracts = discovery.discover()

# Convenience function
contracts = discover_plugins("/plugins/tenant")
```

### Directory layouts

The scanner handles two layouts per search path:

**Flat (legacy):** `{search_path}/{plugin_name}/plugin.py`

**Versioned (current):** `{search_path}/{pid}/{version}/plugin.py`

Detection is automatic: if a top-level directory contains no `plugin.py` but does contain subdirectories, the scanner
treats it as a pid container and descends one more level to find version directories.

Source: `sdk/src/cadence_sdk/utils/directory_discovery.py`

Directories starting with `.` and `__pycache__` are skipped.

All versions found are registered; the `PluginRegistry` keeps only the highest semantic version per `pid` when the same
`pid` appears more than once.

### Module loading

Each `plugin.py` is loaded with `importlib.util.spec_from_file_location`. The package directory is temporarily prepended
to `sys.path` during exec so local imports inside the plugin work. It is removed from `sys.path` in a `finally` block.
Source: `sdk/src/cadence_sdk/utils/directory_discovery.py`

---

## Validation — shallow vs. deep

`sdk/src/cadence_sdk/utils/validation.py`

### `validate_plugin_structure_shallow(plugin_class)` — fast, no instantiation

`sdk/src/cadence_sdk/utils/validation.py`

Checks (in order):

1. `plugin_class` is a subclass of `BasePlugin`.
2. The class has `get_metadata` and `create_agent` methods.
3. `get_metadata()` returns a `PluginMetadata` instance.
4. `name`, `version`, and `description` fields are non-empty.
5. `version` is parseable by `packaging.version`.

Returns `(is_valid: bool, errors: List[str])`. Stops at the first category of failure (e.g., if the class is not a
`BasePlugin` subclass, later checks are skipped).

### `validate_plugin_structure(plugin_class)` — deep, instantiates agent

`sdk/src/cadence_sdk/utils/validation.py`

Performs all shallow checks, then additionally:

6. Calls `create_agent()` and verifies the result is a `BaseAgent`.
7. Verifies the agent has `get_tools()` and `get_system_prompt()`.
8. Calls `get_tools()` and verifies every item in the returned list is a `UvTool`.
9. Calls `get_system_prompt()` and verifies it returns a non-empty string.
10. Verifies `metadata.sdk_version` is set.
11. Calls `validate_dependencies()` and surfaces any errors.

```python
from cadence_sdk import validate_plugin_structure, validate_plugin_structure_shallow

is_valid, errors = validate_plugin_structure_shallow(MyPlugin)
# fast — use during directory scan

is_valid, errors = validate_plugin_structure(MyPlugin)
# thorough — use before bundle creation
```

---

## How SDKPluginManager uses discovery

`src/cadence/infrastructure/plugins/plugin_loader.py`

`SDKPluginManager` inherits from both `PluginLoaderMixin` and `PluginBundleBuilderMixin`. Its `discover_plugins()`
method scans three sources in priority order:

1. **Tenant directory** — `{tenant_plugins_root}/{org_id}/`
2. **System directory** — `system_plugins_dir` if configured
3. **Environment** — already-registered plugins in `PluginRegistry` (pip-installed packages that called
   `register_plugin()` at import time)

```python
manager = SDKPluginManager(
    adapter=langgraph_adapter,
    llm_factory=llm_factory,
    org_id="acme-corp",
    tenant_plugins_root="/data/plugins",
    system_plugins_dir="/app/system_plugins",
)

# Discover: scans filesystem and populates PluginRegistry
pids = manager.discover_plugins()

# Load specific plugins and build bundles
bundles = await manager.load_plugins(
    plugin_specs=["com.acme.search", "io.cadence.system.summarizer@1.2.0"],
    instance_config=orchestrator_instance_config,
)
```

`load_plugins` accepts specs in `pid` or `pid@version` form. If a requested version is not in the registry the loader
falls back to the filesystem and, if a `PluginStoreRepository` is configured, to S3.

Source: `src/cadence/infrastructure/plugins/plugin_manager.py`

---

## Dependency installation

`sdk/src/cadence_sdk/utils/installers.py`

```python
from cadence_sdk import install_dependencies, check_dependency_installed

# Check before use
if not check_dependency_installed("duckduckgo_search"):
    success, msg = install_dependencies(["duckduckgo-search>=3.0"])
    if not success:
        raise RuntimeError(f"Could not install dependency: {msg}")
```

`check_dependency_installed(package_name)` attempts `__import__(package_name)` and returns `True` if it succeeds.

`install_dependencies(packages, upgrade=False, quiet=True)` shells out to `sys.executable -m pip install`. Timeout is
300 seconds. Returns `(success: bool, message: str)`.

These functions are also exposed through the higher-level
`install_plugin_dependencies(dependencies, plugin_name, auto_install=True)` which handles the check-then-install loop
and returns `(all_satisfied: bool, missing: List[str])`.

The `validate_dependencies()` static method on `BasePlugin` is the right place to call `check_dependency_installed` —
the framework calls it during bundle validation and surfaces errors before attempting any tool invocations.

---

## SDKPluginBundle

`src/cadence/infrastructure/plugins/plugin_manager.py`

```python
@dataclass
class SDKPluginBundle:
    contract: PluginContract          # wrapper around the plugin class
    metadata: PluginMetadata          # plugin identity and capabilities
    agent: BaseAgent                  # initialized agent instance
    bound_model: BaseChatModel | None # LLM bound to this plugin's tools
    uv_tools: list[UvTool]            # raw SDK tools
    orchestrator_tools: list[Any]     # framework-native tool objects
    adapter: OrchestratorAdapter      # framework adapter used to build this bundle
    tool_node: Any | None             # LangGraph ToolNode (langgraph only)
    agent_node: Any | None            # reserved
```

A bundle is created by `PluginBundleBuilderMixin._create_bundle()`:

1. `create_agent()` is called.
2. `PluginSettingsResolver.resolve()` produces the flat config dict.
3. `agent.initialize(config)` is called.
4. `agent.get_tools()` retrieves the tool list.
5. `adapter.uvtool_to_orchestrator(tool)` converts each `UvTool` to a framework-native tool.
6. The LLM model (if an `llm_config_id` is present in resolved settings) is created and bound to the tools.
7. For LangGraph adapters, a `ToolNode` is created.

Source: `src/cadence/infrastructure/plugins/plugin_bundle_builder.py`

### Bundle caching for stateless plugins

When `contract.is_stateless` is `True` and a `SharedBundleCache` is available, `_create_bundle_with_cache()` checks
whether an identical bundle (same `pid`, `version`, resolved settings, and adapter type) was already created for another
orchestrator instance. If so it reuses the cached bundle, skipping agent construction and model binding.

Source: `src/cadence/infrastructure/plugins/plugin_bundle_builder.py`

---

See also:

- [Plugin Development](plugin-development.md) — implementing `validate_dependencies()`
- [Plugin Settings](settings.md) — how `PluginSettingsResolver` resolves `OrchestratorInstance.plugin_settings`
- [SDK Overview](index.md)
