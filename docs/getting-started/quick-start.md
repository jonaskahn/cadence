# Quick Start Guide

Welcome to Cadence AI Framework! This guide will help you get up and running quickly.

## Prerequisites

- Python 3.13+ (required)
- API keys for your chosen LLM providers (OpenAI, Anthropic, Google AI, or Azure OpenAI)
- Poetry (for development) or pip (for installation)

## Installation Options

### 🎯 Option 1: For End Users (Quick Start)

**Install the package:**

```bash
pip install cadence-py
```

**Verify installation:**

```bash
python -m cadence --help
```

**Run immediately:**

```bash
python -m cadence start api
```

### 🛠️ Option 2: For Developers (Build from Source)

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
   # Edit .env with your configuration
   ```

## Configuration

### Environment Variables

Create a `.env` file with your configuration:

```bash
# Application Configuration
CADENCE_APP_NAME="Cadence 🤖 Multi-agents AI Framework"
CADENCE_DEBUG=false

# LLM Provider Configuration
CADENCE_DEFAULT_LLM_PROVIDER=openai
CADENCE_OPENAI_API_KEY=your_openai_api_key_here
CADENCE_ANTHROPIC_API_KEY=your_claude_api_key_here
CADENCE_GOOGLE_API_KEY=your_gemini_api_key_here

# Plugin Configuration
CADENCE_PLUGINS_DIR=./plugins/src/cadence_example_plugins
CADENCE_ENABLE_DIRECTORY_PLUGINS=true

# Server Configuration
CADENCE_API_HOST=0.0.0.0
CADENCE_API_PORT=8000

# For production, you might want to use PostgreSQL
CADENCE_CONVERSATION_STORAGE_BACKEND=postgresql
CADENCE_POSTGRES_URL=postgresql+asyncpg://user:pass@localhost/cadence

# For development, you can use the built-in UI
CADENCE_UI_HOST=0.0.0.0
CADENCE_UI_PORT=8501
```

### Configuration Options

- **LLM Providers**: OpenAI, Anthropic, Google AI, Azure OpenAI
- **Storage Backends**: Memory (default), PostgreSQL, Redis
- **Plugin Directories**: Custom paths for plugin discovery
- **Server Settings**: Host, port, debug mode, CORS configuration
- **Plugin Management**: Upload directory, archive directory, auto-discovery settings
- **Safety Settings**: Hop limits, consecutive routing limits, timeout settings

## Running the Application

### Start the API Server

**If installed via pip:**

```bash
python -m cadence start api
```

**If built from source:**

```bash
poetry run python -m cadence start api
```

The server will start on `http://localhost:8000` by default.

### Start the UI (Optional)

**If installed via pip:**

```bash
python -m cadence start ui
```

**If built from source:**

```bash
poetry run python -m cadence start ui
```

### Start Both API and UI

```bash
python -m cadence start all
```

## Testing the Installation

1. **Check the API**

   ```bash
   curl http://localhost:8000/health
   ```

2. **Check the UI**

    - Open `http://localhost:8501` in your browser
    - The UI uses `CADENCE_API_BASE_URL` (default `http://localhost:8000`)
    - Features: Plugin management, conversation interface, system monitoring

3. **API Documentation**
    - Swagger UI: `http://localhost:8000/docs`
    - ReDoc: `http://localhost:8000/redoc`

## First Steps

1. **Send a test message**

   ```bash
   curl -X POST "http://localhost:8000/conversation/chat" \
     -H "Content-Type: application/json" \
     -d '{
       "message": "Hello, Cadence!",
       "user_id": "test-user",
       "org_id": "test-org"
     }'
   ```

2. **Test advanced orchestrator features**

   **Try different response tones:**

   ```bash
   curl -X POST "http://localhost:8000/conversation/chat" \
     -H "Content-Type: application/json" \
     -d '{
       "message": "Explain quantum computing",
       "user_id": "test-user",
       "org_id": "test-org",
       "metadata": {"tone": "explanatory"}
     }'
   ```

   **Test structured responses:**

   ```bash
   curl -X POST "http://localhost:8000/conversation/chat" \
     -H "Content-Type: application/json" \
     -d '{
       "message": "Calculate 15 * 23 and explain the steps",
       "user_id": "test-user",
       "org_id": "test-org",
       "metadata": {"tone": "learning"}
     }'
   ```

3. **Check available plugins**

   ```bash
   curl http://localhost:8000/plugins/plugins
   ```

4. **Monitor system status**

   ```bash
   curl http://localhost:8000/system/status
   ```

## Development Mode

For development, enable debug mode:

```bash
export CADENCE_DEBUG=true
export CADENCE_API_PORT=8001
export CADENCE_PLUGINS_DIR=./plugins/src/cadence_example_plugins

# Verify your API keys are set
echo $CADENCE_OPENAI_API_KEY
```

## Troubleshooting

### Common Issues

1. **Port already in use**

    - Change the port in your `.env` file
    - Or kill the process using the port

2. **API keys not working**

    - Verify your API keys are set correctly
    - Check the API provider's status

3. **Plugins not loading**
    - Verify the plugin directory path
    - Check plugin dependencies

### Getting Help

- Check the logs for error messages
- Verify your configuration
- Check the [documentation](https://cadence.readthedocs.io/)
- Open an [issue](https://github.com/jonaskahn/cadence/issues)

## Next Steps

Now that you have Cadence running:

1. **Explore the API**: Check out the interactive documentation
2. **Create plugins**: Build custom agents and tools
3. **Customize configuration**: Adjust settings for your needs
4. **Deploy**: Set up for production use

Welcome to Cadence AI Framework! 🚀
