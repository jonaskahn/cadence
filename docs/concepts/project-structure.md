# Project Structure

This repository contains three main components:

- `src/cadence`: Cadence core (API, orchestrator, LLM factory, plugin manager)
- `sdk/src/cadence_sdk`: Cadence SDK for building plugins (interfaces, registry, utilities)
- `plugins/src/cadence_example_plugins`: Example plugins (math, search)

```
cadence/
├─ src/cadence/               # Cadence core application
│  ├─ api/                 # FastAPI routes, schemas, and DI container
│  │  ├─ routers/          # Chat, plugins, system endpoints
│  │  ├─ schemas.py        # Request/response models
│  │  └─ services.py       # Service initialization
│  ├─ core/                # Multi-agent orchestration
│  │  ├─ orchestrator/     # LangGraph coordinator and state
│  │  └─ services/         # Conversation and orchestrator services
│  ├─ domain/              # Business models and DTOs
│  │  ├─ models/           # Thread, Conversation, User, Organization
│  │  └─ dtos/             # Data transfer objects
│  ├─ infrastructure/      # External integrations
│  │  ├─ database/         # Multi-backend repositories (PostgreSQL, Redis, Memory)
│  │  ├─ llm/              # LLM factory and provider implementations
│  │  └─ plugins/          # SDK plugin manager integration
│  ├─ config/              # Settings and configuration (Pydantic)
│  ├─ ui/                  # Streamlit debug interface
│  │  ├─ app.py            # Main Streamlit application
│  │  └─ client.py         # Cadence API client wrapper
│  ├─ main.py              # Application factory and entry point
│  └─ __main__.py          # Module entry point (python -m cadence)
│
├─ sdk/src/cadence_sdk/       # Cadence Plugin SDK
│  ├─ base/                # BasePlugin, BasePluginAgent, PluginMetadata
│  ├─ registry/            # Plugin registry, contracts, discovery
│  ├─ tools/               # Tool decorators and registry
│  ├─ types/               # AgentState and message types
│  ├─ utils/               # Plugin discovery, validation, hybrid loading
│  └─ examples/            # Template plugin implementation
│
├─ plugins/src/cadence_example_plugins/ # Example plugin ecosystem
│  ├─ math_agent/          # Mathematical calculations plugin
│  ├─ search_agent/        # Web search capabilities plugin
│  └─ myinfo_agent/        # Chatbot information plugin
│
├─ docs/                   # Comprehensive documentation
│  ├─ concepts/            # Architecture and system concepts
│  ├─ getting-started/     # Installation and quick start guides
│  ├─ plugins/             # Plugin development documentation
│  ├─ deployment/          # Environment and production guides
│  └─ contributing/        # Development and contribution guidelines
├─ docker/                 # Docker compose configurations
├─ migrations/             # Database migration scripts (Alembic)
├─ tests/                  # Test suite and fixtures
├─ pyproject.toml          # Poetry project configuration
├─ mkdocs.yml              # Documentation site configuration
└─ README.md               # Project overview and quick start
```

## Core entry points

- Run server: `python -m cadence`
- Run debug UI: `streamlit run src/cadence/ui/app.py`
- SDK imports: `from cadence_sdk import BasePlugin, PluginMetadata, BaseAgent, tool`
- Plugins dir: configured via `CADENCE_PLUGINS_DIR` (default `./plugins/src/cadence_example_plugins`)

## How things connect

- Core loads plugins via `SDKPluginManager`, which discovers packages and registers them through the SDK registry.
- Each plugin implements `BasePlugin`, creates an `agent` (subclass of `BaseAgent`), and exposes tools.
- Orchestrator builds a graph with agent nodes and tool nodes for runtime execution.
- UI connects to core via REST API endpoints for chat, thread management, and plugin status.

## Key architectural patterns

- **Multi-Agent Orchestration**: LangGraph-based workflow coordination with plugin agents
- **Plugin Discovery**: Hybrid discovery supporting both pip-installed and directory-based plugins
- **Storage Strategy**: Optimized conversation storage with 75% reduction vs full message history
- **Multi-Backend Support**: PostgreSQL, Redis, and in-memory storage with automatic selection
- **LLM Provider Abstraction**: Unified interface for OpenAI, Anthropic, Google, and Azure models
- **State Management**: Comprehensive conversation state tracking across agent switches

## Development workflow

1. **Core Development**: Modify `src/cadence/` for framework features
2. **Plugin Development**: Create new agents in `plugins/src/cadence_example_plugins/`
3. **SDK Updates**: Update plugin interfaces in `sdk/src/cadence_sdk/`
4. **Testing**: Run tests with `poetry run pytest`
5. **Documentation**: Update docs in `docs/` directory
6. **UI Testing**: Use Streamlit debug interface for rapid iteration
