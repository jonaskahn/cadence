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

The new conditional routing system provides intelligent agent decision-making:

### Agent Decision Logic

Agents now implement a `should_continue` method that determines routing:

```python
@staticmethod
def should_continue(state: Dict[str, Any]) -> str:
    """Decide whether to call tools or return to the coordinator."""
    last_msg = state.get("messages", [])[-1] if state.get("messages") else None
    if not last_msg:
        return "back"

    tool_calls = getattr(last_msg, "tool_calls", None)
    return "continue" if tool_calls else "back"
```

**Routing Decisions:**

- `"continue"`: Agent has tool calls, route to tools
- `"back"`: Agent answered directly, return to coordinator

### Fake Tool Call Implementation

To ensure consistent routing flow, agents create fake tool calls when answering directly:

```python
if tool_calls:
    logger.debug(f"Agent {self.metadata.name} generated {len(tool_calls)} tool calls.")
else:
    # Create fake "back" tool call for consistent routing
    response.content = ""
    response.tool_calls = [ToolCall(
        id=str(uuid.uuid4()),
        name="back",
        args={}
    )]
```

### Plugin Bundle Edge Configuration

Plugin bundles now define their own routing logic:

```python
def get_graph_edges(self) -> Dict[str, Any]:
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
```

**Key Benefits:**

- **No Circular Routing**: Tools always route to coordinator, never back to agent
- **Consistent Flow**: All agent responses follow the same routing path
- **Better Debugging**: Clear routing decisions and edge creation logging
- **Predictable Behavior**: Eliminates infinite loops and routing confusion

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
