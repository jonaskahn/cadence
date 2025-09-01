# Cadence 🤖 Multi-agents AI Framework

Welcome to Cadence — a powerful, open-source multi-agent orchestration system designed to simplify the development and
deployment of AI agent workflows.

- **Quick Start**: [Get up and running](getting-started/quick-start.md)
- **Core Concepts**:
    - [Understand the architecture](concepts/architecture.md)
    - [LangGraph Architecture](concepts/langgraph-architecture.md)
- **Plugin Development**: [Build custom agents](plugins/overview.md)
- **Deployment**: [Configure environments](deployment/environment.md)

---

## What is Cadence?

Cadence is a multi-agent orchestration framework built with modern Python technologies like LangChain and LangGraph. It
provides a robust foundation for creating intelligent, collaborative AI systems, and a clean plugin system that keeps
your core code decoupled from custom functionality.

## Quick Installation

**For end users:**

```bash
pip install cadence-py
python -m cadence start api
```

**For developers:**

```bash
git clone https://github.com/jonaskahn/cadence.git
cd cadence
poetry install
poetry run python -m cadence start api
```

## Philosophy

Cadence is built on three core principles:

### 1. Simplicity First

- Clean, intuitive APIs that get out of your way
- Minimal boilerplate code for maximum productivity
- Clear separation of concerns between core system and plugins

### 2. Plugin-Driven Architecture

- Everything is a plugin — from agents to tools
- Hot-reloadable plugins for rapid development
- True decoupling between core system and custom functionality

### 3. Production Ready

- Built for scale with enterprise-grade reliability
- Comprehensive monitoring and observability
- Docker support and cloud-native deployment

## Architecture Overview

```mermaid
flowchart TD
    U["Client Request (with tone)"] --> API["FastAPI API"]
    API --> COORD["Enhanced Coordinator (LangGraph)"]
    COORD --> PM["SDK Plugin Manager"]
    COORD --> F["Finalizer (Tone-aware)"]
    COORD --> SAFETY["Safety & Logging"]

    PM -->|discovers| B1["Plugin bundle: math_agent"]
    PM -->|discovers| B2["Plugin bundle: search_agent"]

    subgraph B1
      A1[[AgentNode]]
      T1[[ToolNode]]
      A1 --> T1
      T1 --> A1
    end

    subgraph B2
      A2[[AgentNode]]
      T2[[ToolNode]]
      A2 --> T2
      T2 --> A2
    end

    %% Agent returns control to coordinator when not calling tools
    A1 --> COORD
    A2 --> COORD

    %% LLM binding used inside AgentNode execution
    A1 --> LLM[("LLM Models")]
    A2 --> LLM

    %% Safety mechanisms
    SAFETY --> HOP["Hop Limits"]
    SAFETY --> FILTER["Message Filtering"]
    SAFETY --> LOG["Execution Logging"]

    %% Finalizer handles tone-adapted responses
    F --> COORD
    COORD --> API
    API --> U
```

## Key Features

- **Multi-Agent Orchestration**: Coordinate multiple AI agents in complex workflows with intelligent routing
- **Plugin System**: Extend functionality without touching core code with dynamic plugin discovery
- **Hot Reloading**: Update plugins without restarting the system with automatic graph rebuilding
- **LLM Agnostic**: Support for OpenAI, Anthropic, Google, and more with separate model configurations for coordinator,
  suspend, and finalizer
- **REST API**: Full HTTP API for integration with any system
- **Operational API**: Endpoints for chat, plugins, status, and health
- **Comprehensive Logging**: Built-in observability and debugging tools with detailed execution tracking
- **Tone Control**: Dynamic response style adaptation for personalized interactions (natural, formal, concise,
  explanatory, learning)
- **Safety Mechanisms**: Hop limits, message filtering, and error handling to prevent infinite loops
- **State Management**: Robust conversation state tracking with standardized updates

## Quick Example

```python
from cadence_sdk import BasePlugin, PluginMetadata, BaseAgent


class MyPlugin(BasePlugin):
    @staticmethod
    def get_metadata() -> PluginMetadata:
        return PluginMetadata(
            name="my_agent",
            version="0.1.0",
            description="My custom AI agent",
            capabilities=["custom_task"],
        )

    @staticmethod
    def create_agent() -> BaseAgent:
        return MyAgent(MyPlugin.get_metadata())


class MyAgent(BaseAgent):
    def get_tools(self):
        return [my_custom_tool]

    def get_system_prompt(self):
        return "You are a helpful AI assistant."
```

## What's Next?

- [Quick Start Guide](getting-started/quick-start.md) — Get Cadence running in 5 minutes
- [Plugin Development](plugins/overview.md) — Learn to build custom agents
- [Architecture](concepts/architecture.md) — Understand the system design
- [Environment](deployment/environment.md) — Configure your setup

## Contributing

Cadence is open source and welcomes contributions! Check out the [contributing guide](contributing/development.md) to
get
started.

## License

Cadence is licensed under the MIT License — see the [LICENSE](../LICENSE) file for details.

---

Made with Material for MkDocs
