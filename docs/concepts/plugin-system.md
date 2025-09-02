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

## Enhanced Routing System

The enhanced conditional routing system provides intelligent agent decision-making:

### Agent Decision Logic

Agents implement a standardized decision method that determines routing:

**Routing Decisions:**

- `"continue"`: Agent has tool calls, route to tools
- `"back"`: Agent answered directly, return to coordinator

### Fake Tool Call Implementation

To ensure consistent routing flow, agents create fake tool calls when answering directly.

**Design Principles:**

- **Consistent Flow**: All agent responses follow the same routing path
- **Explicit Intent**: Fake tool calls make routing decisions explicit
- **No Direct Routing**: Agents never route directly to coordinator

### Plugin Bundle Edge Configuration

Plugin bundles define their own routing logic through a standardized interface.

**Edge Configuration Design:**

- **Conditional Edges**: Agent routing decisions based on standardized decision method
- **Direct Edges**: Tools always route to coordinator (prevents circular routing)
- **No More Loops**: Eliminated the `tools → agent` edge that caused infinite loops
- **Standardized Interface**: All plugins follow the same edge configuration pattern

## Plugin Context and Coordinator Guardrails

Plugins participate in a coordinated flow where the orchestrator tracks lightweight routing context to improve safety:

- `plugin_context.same_agent_consecutive_routes`: consecutive route counter for the same agent
- `plugin_context.last_routed_agent`: last agent chosen by the coordinator

The coordinator uses this context to enforce a consecutive same-agent routing limit (`coordinator_consecutive_agent_route_limit`). Once reached, execution is routed to the `suspend` node to prevent unproductive loops. The counters reset when the coordinator selects a different agent or decides to `goto_finalize`.

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
