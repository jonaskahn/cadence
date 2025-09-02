# Cadence 🤖 Multi-agents AI Framework

A plugin-based multi-agent conversational AI framework built on FastAPI, designed for building intelligent chatbot
systems with extensible the plugin/modularization architecture.

![demo](https://github.com/user-attachments/assets/ba7ceb1d-3226-4634-8491-abf7fab04add)

## 🚀 Features

- **Multi-Agent Orchestration**: Intelligent routing and coordination between AI agents
- **Plugin System**: Extensible architecture for custom agents and tools
- **Parallel Tool Execution**: Concurrent tool calls for improved performance and efficiency
- **Multi-LLM Support**: OpenAI, Anthropic, Google AI, and more
- **Flexible Storage**: PostgreSQL, Redis, MongoDB, and in-memory backends
- **REST API**: FastAPI-based API with automatic documentation
- **Streamlit UI**: Built-in web interface for testing and management
- **Docker Support**: Containerized deployment with Docker Compose

## 📦 Installation & Usage

### 🎯 For End Users (Quick Start)

**Install the package:**

```bash
pip install cadence-py
```

**Verify installation:**

```bash
# Check if cadence is available
python -m cadence --help

# Should show available commands and options
```

**Run the application:**

```bash
# Start the API server
python -m cadence start api

# Start with custom host/port
python -m cadence start api --host 0.0.0.0 --port 8000

# Start the Streamlit UI
python -m cadence start ui

# Start both API and UI
python -m cadence start all
```

**Available commands:**

```bash
# Show help
python -m cadence --help

# Show status
python -m cadence status

# Manage plugins
python -m cadence plugins

# Show configuration
python -m cadence config

# Health check
python -m cadence health
```

### 🛠️ For Developers (Build from Source)

If you want to contribute, develop plugins, or customize the framework:

#### Prerequisites

- Python 3.13+
- Poetry (for dependency management)
- Docker (optional, for containerized deployment)

#### Development Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/jonaskahn/cadence.git
   cd cadence
   ```

2. **Install dependencies**

   ```bash
   poetry install
   poetry install --with local  # Include local SDK development
   ```

3. **Set up environment variables**

   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

4. **Run the application**

   ```bash
   poetry run python -m cadence start api
   ```

## ⚙️ Configuration

### Environment Variables

All configuration is done through environment variables with the `CADENCE_` prefix:

```bash
# LLM Provider Configuration
CADENCE_DEFAULT_LLM_PROVIDER=openai
CADENCE_OPENAI_API_KEY=your-openai-key
CADENCE_ANTHROPIC_API_KEY=your-claude-key
CADENCE_GOOGLE_API_KEY=your-gemini-key

# Storage Configuration
CADENCE_CONVERSATION_STORAGE_BACKEND=memory  # or postgresql
CADENCE_POSTGRES_URL=postgresql://user:pass@localhost/cadence

# Plugin Configuration
CADENCE_PLUGINS_DIR=["./plugins/src/cadence_plugins"]

# Server Configuration
CADENCE_API_HOST=0.0.0.0
CADENCE_API_PORT=8000
CADENCE_DEBUG=true

# Advanced Configuration
CADENCE_MAX_AGENT_HOPS=25
CADENCE_GRAPH_RECURSION_LIMIT=50

# Session Management
CADENCE_SESSION_TIMEOUT=3600
CADENCE_MAX_SESSION_HISTORY=100
```

### Configuration File

You can also use a `.env` file for local development:

```bash
# .env
CADENCE_DEFAULT_LLM_PROVIDER=openai
CADENCE_OPENAI_API_KEY=your_actual_openai_api_key_here
CADENCE_ANTHROPIC_API_KEY=your_actual_claude_api_key_here
CADENCE_GOOGLE_API_KEY=your_actual_gemini_api_key_here

CADENCE_APP_NAME="Cadence 🤖 Multi-agents AI Framework"
CADENCE_DEBUG=false

CADENCE_PLUGINS_DIR=./plugins/src/cadence_example_plugins

CADENCE_API_HOST=0.0.0.0
CADENCE_API_PORT=8000

# For production, you might want to use PostgreSQL
CADENCE_CONVERSATION_STORAGE_BACKEND=postgresql
CADENCE_POSTGRES_URL=postgresql://user:pass@localhost/cadence

# For development, you can use the built-in UI
CADENCE_UI_HOST=0.0.0.0
CADENCE_UI_PORT=8501

# Plugin Configuration
CADENCE_PLUGINS_DIR=./plugins/src/cadence_example_plugins
CADENCE_MAX_AGENT_HOPS=25
CADENCE_GRAPH_RECURSION_LIMIT=50

# Parallel Tool Calls Configuration
# Individual agents can control parallel tool execution in their constructor:
# super().__init__(metadata, parallel_tool_calls=True)  # Enable (default)
# super().__init__(metadata, parallel_tool_calls=False) # Disable
```

## 🚀 Usage

### Command Line Interface

Cadence provides a comprehensive CLI for management tasks:

```bash
# Start the server
python -m cadence start api --host 0.0.0.0 --port 8000

# Show status
python -m cadence status

# Manage plugins
python -m cadence plugins

# Show configuration
python -m cadence config

# Health check
python -m cadence health
```

### API Usage

The framework exposes a REST API for programmatic access:

```python
import requests

# Send a message
response = requests.post("http://localhost:8000/api/v1/chat", json={
    "message": "Hello, how are you?",
    "user_id": "user123",
    "org_id": "org456"
})

print(response.json())
```

### Plugin Development

Create custom agents and tools using the Cadence SDK with enhanced routing capabilities:

```python
from cadence_sdk import BaseAgent, BasePlugin, PluginMetadata, tool


class MyPlugin(BasePlugin):
    @staticmethod
    def get_metadata() -> PluginMetadata:
        return PluginMetadata(
            name="my_agent",
            version="1.0.0",
            description="My custom AI agent",
            capabilities=["custom_task"],
            agent_type="specialized",
            dependencies=["cadence_sdk>=1.0.2,<2.0.0"],
        )

    @staticmethod
    def create_agent() -> BaseAgent:
        return MyAgent(MyPlugin.get_metadata())


class MyAgent(BaseAgent):
    def __init__(self, metadata: PluginMetadata):
        super().__init__(metadata)

    def get_tools(self):
        from .tools import my_custom_tool
        return [my_custom_tool]

    def get_system_prompt(self) -> str:
        return "You are a helpful AI assistant."

    @staticmethod
    def should_continue(state: dict) -> str:
        """Enhanced routing decision - decide whether to continue or return to coordinator.

        This is the REAL implementation from the Cadence SDK - it's much simpler than you might expect!
        The method simply checks if the agent's response has tool calls and routes accordingly.
        """
        last_msg = state.get("messages", [])[-1] if state.get("messages") else None
        if not last_msg:
            return "back"

        tool_calls = getattr(last_msg, "tool_calls", None)
        return "continue" if tool_calls else "back"


# Parallel Tool Calls Support
# BaseAgent supports parallel tool execution for improved performance

class MyAgent(BaseAgent):
    def __init__(self, metadata: PluginMetadata):
        # Enable parallel tool calls (default: True)
        super().__init__(metadata, parallel_tool_calls=True)

    def get_tools(self):
        return [my_tool1, my_tool2, my_tool3]

    def get_system_prompt(self) -> str:
        return "You are an agent that can execute multiple tools in parallel."


@tool
def my_custom_tool(input_data: str) -> str:
    """A custom tool for specific operations."""
    return f"Processed: {input_data}"
```

**Enhanced Features:**

- **Intelligent Routing**: Agents automatically decide when to use tools or return to coordinator
- **Fake Tool Calls**: Consistent routing flow even when agents answer directly
- **No Circular Routing**: Eliminated infinite loops through proper edge configuration
- **Better Debugging**: Clear routing decisions and comprehensive logging

**Key Implementation Details:**

- **`should_continue` is a static method**: Uses `@staticmethod` decorator
- **Automatic fake tool calls**: The SDK automatically creates fake "back" tool calls when agents answer directly
- **Consistent routing**: All responses go through the same flow regardless of whether tools are used

## 🐳 Docker Deployment

### Quick Start with Docker Compose

```bash
# Start all services
docker-compose -f docker/compose.yaml up -d

# View logs
docker-compose -f docker/compose.yaml logs -f

# Stop services
docker-compose -f docker/compose.yaml down
```

### Custom Docker Build

```bash
# Build the image
./build.sh

# Run the container
docker run -p 8000:8000 ifelsedotone/cadence:latest
```

## 🧪 Testing

Run the test suite to ensure everything works correctly:

```bash
# Install test dependencies
poetry install --with dev

# Run tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=src/cadence

# Run specific test categories
poetry run pytest -m "unit"
poetry run pytest -m "integration"
```

## 📚 Documentation

- [Quick Start Guide](docs/getting-started/quick-start.md)
- [Architecture Overview](docs/concepts/architecture.md)
- [Plugin Development](docs/plugins/overview.md)
- [API Reference](docs/api/)
- [Deployment Guide](docs/deployment/)

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](docs/contributing/development.md) for details.

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built on [FastAPI](https://fastapi.tiangolo.com/) for high-performance APIs
- Powered by [LangChain](https://langchain.com/) and [LangGraph](https://langchain.com/langgraph) for AI orchestration
- UI built with [Streamlit](https://streamlit.io/) for rapid development
- Containerized with [Docker](https://www.docker.com/) for easy deployment

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/jonaskahn/cadence/issues)
- **Discussions**: [GitHub Discussions](https://github.com/jonaskahn/cadence/discussions)
- **Documentation**: [Read the Docs](https://cadence.readthedocs.io/)

---

**Made with ❤️ by the Cadence AI Team**
