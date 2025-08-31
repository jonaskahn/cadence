# Your First Plugin

This tutorial creates a minimal plugin that adds a greeting agent.

## 1. Create package structure

Under `plugins/src/cadence_plugins/` add a folder `greeter_agent/`:

```text
plugins/src/cadence_plugins/greeter_agent/
├─ __init__.py
├─ plugin.py
├─ agent.py
└─ tools.py
```

`__init__.py`:

```python
from cadence_sdk import register_plugin
from .plugin import GreeterPlugin


# Register on import
def _register():
    register_plugin(GreeterPlugin)


_register()
```

## 2. Define tools

`tools.py`:

```python
from cadence_sdk import tool


@tool
def greet(name: str) -> str:
    """Return a friendly greeting for a given name."""
    return f"Hello, {name}! 👋"


greeter_tools = [greet]
```

## 3. Implement agent

`agent.py`:

```python
from typing import List
from cadence_sdk import BaseAgent
from cadence_sdk.base.metadata import PluginMetadata


class GreeterAgent(BaseAgent):
    def __init__(self, metadata: PluginMetadata):
        super().__init__(metadata)

    def get_tools(self) -> List:
        from .tools import greeter_tools
        return greeter_tools

    def get_system_prompt(self) -> str:
        return "You are a friendly greeter agent. Use the `greet` tool to greet users by name."
```

## 4. Implement plugin class

`plugin.py`:

```python
from cadence_sdk import BasePlugin, PluginMetadata, BaseAgent


class GreeterPlugin(BasePlugin):
    @staticmethod
    def get_metadata() -> PluginMetadata:
        return PluginMetadata(
            name="greeter_agent",
            version="0.1.0",
            description="Greets users by name",
            capabilities=["greeting"],
            llm_requirements={
                "provider": "openai",
                "model": "gpt-4.1",
                "temperature": 0,
                "max_tokens": 256,
            },
            agent_type="specialized",
            dependencies=[],
        )

    @staticmethod
    def create_agent() -> BaseAgent:
        from .agent import GreeterAgent

        return GreeterAgent(GreeterPlugin.get_metadata())
```

## 5. Point Cadence to your plugins directory

Ensure `.env` contains:

```text
CADENCE_PLUGINS_DIR=./plugins/src/cadence_plugins
```

## 6. Run Cadence and verify

```bash
python -m cadence start all
# In another terminal
curl http://127.0.0.1:8000/api/v1/plugins
```

You should see `greeter_agent` in the list.

## 7. Try it

```bash
curl -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Use greeter_agent to greet Alice", "tone": "natural"}'
```

## Tips

- Keep `create_agent()` static
- Keep tools simple and well documented
- Add `health_check()` if your plugin uses external services
