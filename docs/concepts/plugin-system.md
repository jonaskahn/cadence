# Plugin System

Cadence plugins are self-contained packages discovered via the SDK registry. Each plugin exposes:

- **Metadata**: `name`, `version`, `description`, `capabilities`, `llm_requirements`, `dependencies`
- **Agent factory**: `create_agent() -> BaseAgent` (returns SDK BaseAgent instance)
- **Tools**: LangChain `Tool` functions used by the agent (decorated with `@tool`)
- **Validation**: `validate_dependencies() -> list[str]`
- **Health checks**: `health_check() -> dict`

## Plugin Bundle Lifecycle

The `SDKPluginManager` creates `SDKPluginBundle` objects that encapsulate complete plugin functionality:

1. **Discovery**: Multi-source discovery (pip packages, directories, uploaded plugins)
2. **Validation**: Structure validation, dependency installation, health checks
3. **Bundle Creation**:
    - Create agent instance from plugin contract
    - Create and bind LLM model to agent
    - Get tools from agent and create ToolNode with automatic "back" tool
    - Create agent node callable via `agent.create_agent_node()`
4. **Graph Integration**: Register nodes and edges with LangGraph orchestrator

## Workflow Implementation

### Plugin Bundle Structure

Each `SDKPluginBundle` contains:

```python
# Created by SDKPluginManager
bundle = SDKPluginBundle(
    contract=plugin_contract,  # BasePlugin instance
    agent=agent_instance,  # BaseAgent instance
    bound_model=llm_model,  # LLM with tools bound
    tools=agent_tools  # List[Tool] from agent.get_tools()
)

# Bundle creates:
# 1. ToolNode with agent tools + automatic "back" tool
# 2. Agent node callable from agent.create_agent_node()
```

### Agent Node Execution

When an agent node executes:

1. **Prompt Construction**: `[SystemMessage(agent.get_system_prompt())] + state["messages"]`
2. **LLM Invocation**: `bound_model.invoke(request_messages)`
3. **Context Updates**: Updates `plugin_context` with routing history
4. **State Return**: Returns new state with agent response

### Routing Decision Logic

The routing is controlled by `BaseAgent.should_continue(state)` static method:

```python
@staticmethod
def should_continue(state: Dict[str, Any]) -> str:
    """Simple routing logic"""
    last_msg = state.get("messages", [])[-1] if state.get("messages") else None
    if not last_msg:
        return "back"

    tool_calls = getattr(last_msg, "tool_calls", None)
    return "continue" if tool_calls else "back"
```

**Key Points:**

- **Simple implementation**: No complex tool call generation needed
- **Pure decision logic**: Checks if the agent's response has tool_calls
- **Consistent behavior**: All agents use the same standardized decision method

### Graph Integration

Each bundle provides nodes and edges:

```python
# Nodes with normalized naming
nodes = {
    f"{plugin_name}_agent": bundle.agent_node,  # Callable from create_agent_node()
    f"{plugin_name}_tools": bundle.tool_node  # ToolNode(tools + back_tool)
}

# Edges define routing logic
edges = {
    "conditional_edges": {
        f"{plugin_name}_agent": {
            "condition": agent.should_continue,  # Static method reference
            "mapping": {
                "continue": f"{plugin_name}_tools",  # Route to tools
                "back": "coordinator"  # Return to coordinator
            }
        }
    },
    "direct_edges": [(f"{plugin_name}_tools", "coordinator")]  # Tools always return
}
```

## Coordinator Safety Mechanisms

The coordinator implements several safety mechanisms to prevent infinite loops and unproductive routing:

### Hop Limit Protection

- **Agent Hops Counter**: Tracks total agent switches in conversation
- **Max Agent Hops**: Configurable limit (default: 25) via `CADENCE_MAX_AGENT_HOPS`
- **Hop Counting Logic**: Only agent routing increments counter (excludes `goto_finalize`)

### Consecutive Agent Routing Protection

- **Same Agent Counter**: Tracks consecutive routes to the same agent
- **Consecutive Limit**: Configurable via `CADENCE_COORDINATOR_CONSECUTIVE_AGENT_ROUTE_LIMIT` (default: 5)
- **Context Tracking**: Maintained in `plugin_context.same_agent_consecutive_routes`
- **Reset Conditions**: Counter resets on agent change or `goto_finalize`

### Suspend Node Behavior

When limits are reached, the coordinator routes to the suspend node which:

- Provides user-friendly explanations (no technical jargon)
- Synthesizes information gathered so far
- Respects user's requested tone preference
- Suggests how to continue the conversation

## Plugin Discovery and Configuration

### Discovery Sources

- **Pip Packages**: Automatically discovered when importing packages that depend on `cadence_sdk`
- **Directory Plugins**: Configured via `CADENCE_PLUGINS_DIR` (single path or JSON list)
- **Uploaded Plugins**: Dynamic uploads via UI/API stored in `CADENCE_STORE_PLUGIN`

### Model Configuration Priority

1. Plugin-specific `llm_requirements` in metadata
2. Core `Settings` default provider and model
3. Fallback to system defaults on model creation failure

### Plugin Registration

Ensure your plugin package calls the global SDK registry on import:

```python
# plugins/src/cadence_example_plugins/my_agent/__init__.py
from cadence_sdk import register_plugin
from .plugin import MyPlugin

register_plugin(MyPlugin)
```

### Key Configuration Settings

- `CADENCE_PLUGINS_DIR`: Plugin discovery directories
- `CADENCE_STORE_PLUGIN`: Uploaded plugin storage directory
- `CADENCE_MAX_AGENT_HOPS`: Maximum agent switches per conversation
- `CADENCE_COORDINATOR_CONSECUTIVE_AGENT_ROUTE_LIMIT`: Consecutive same-agent limit
