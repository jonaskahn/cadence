# Plugin System

Cadence plugins are self-contained packages discovered via the SDK registry. Each plugin exposes:

- Metadata: `name`, `version`, `description`, `capabilities`, `llm_requirements`, `dependencies`
- Agent factory: `create_agent() -> BasePluginAgent`
- Tools: LangChain `Tool` functions used by the agent
- Validation: `validate_dependencies() -> list[str]`
- Health checks: `health_check() -> dict`

## Lifecycle

1. Discovery: `SDKPluginManager` imports pip and directory plugins and calls `discover_plugins()`
2. Validation: structure and dependency checks
3. Agent & Model: `create_agent()`, `get_tools()`, `bind_model()`
4. Graph Wiring: `agent.create_agent_node()` and `ToolNode(tools)` registered with edges

## Routing

The coordinator offers `goto_{plugin}` tools generated from plugin metadata plus a `finalize` tool. After agents act:

- `should_continue(state)` returns `continue` to call tools or `back` to return to coordinator
- Hop limits: `max_agent_hops` and `max_tool_hops` enforce limits; a `suspend` node explains limits to users

## Configuration

- Plugins directory: `CADENCE_PLUGINS_DIR` (single path or JSON list)
- Default provider and model come from core `Settings` or plugin `llm_requirements`

See Plugin Development for how to build a plugin.

### Registering your plugin

Ensure your plugin package calls the global SDK registry on import:

```python
# plugins/src/cadence_example_plugins/my_agent/__init__.py
from cadence_sdk import register_plugin
from .plugin import MyPlugin

register_plugin(MyPlugin)
```
