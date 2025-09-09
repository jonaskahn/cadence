# Environment Configuration

Cadence uses environment variables for configuration, making it easy to deploy across different environments. This guide
covers all available configuration options and best practices aligned with the current codebase.

## Configuration Methods

Cadence supports multiple configuration methods:

1. **Environment Variables** (recommended for production)
2. **`.env` file** (convenient for development)
3. **Command line arguments** (for testing and debugging)

## Configuration Variables

### Application Settings

| Variable           | Default                             | Description                                |
|--------------------|-------------------------------------|--------------------------------------------|
| `CADENCE_APP_NAME` | "Cadence Multi-agents AI Framework" | Application name displayed in logs and API |
| `CADENCE_DEBUG`    | `false`                             | Enable debug mode                          |

### UI Configuration

| Variable                     | Default                                                                | Description            |
|------------------------------|------------------------------------------------------------------------|------------------------|
| `CADENCE_UI_TITLE`           | "Cadence AI"                                                           | Main application title |
| `CADENCE_UI_SUBTITLE`        | "Intelligent conversations powered by multi-agent AI"                  | Application subtitle   |
| `CADENCE_UI_WELCOME_TITLE`   | "Welcome to Cadence AI!"                                               | Welcome page title     |
| `CADENCE_UI_WELCOME_MESSAGE` | "Start a conversation by typing a message below."                      | Welcome message text   |
| `CADENCE_UI_WELCOME_HINT`    | "Choose your preferred response style in Settings and start chatting." | Welcome hint text      |
| `CADENCE_UI_FOOTER`          | "Powered by Cadence AI Framework"                                      | Footer text            |

### Bot Configuration

| Variable                     | Default                          | Description                    |
|------------------------------|----------------------------------|--------------------------------|
| `CADENCE_BOT_NAME`           | "Cadence AI"                     | Bot name for self-introduction |
| `CADENCE_BOT_DESCRIPTION`    | "Multiple Agents Chatbot System" | Bot description                |
| `CADENCE_BOT_CREATOR`        | "JonasKahn"                      | Bot creator name               |
| `CADENCE_BOT_SPECIALIZATION` | "Business"                       | Bot specialization area        |
| `CADENCE_BOT_VERSION`        | "1.3.0"                          | Bot version number             |

### LLM Provider Configuration

| Variable                             | Default                    | Description                                                                                      |
|--------------------------------------|----------------------------|--------------------------------------------------------------------------------------------------|
| `CADENCE_DEFAULT_LLM_PROVIDER`       | `openai`                   | Default LLM provider (`openai`, `azure-openai`/`azure`, `anthropic`/`claude`, `google`/`gemini`) |
| `CADENCE_OPENAI_DEFAULT_MODEL`       | `gpt-4.1`                  | Default model when provider is `openai` or `azure`/`azure-openai`                                |
| `CADENCE_ANTHROPIC_DEFAULT_MODEL`    | `claude-sonnet-4-20250514` | Default model when provider is `anthropic`/`claude`                                              |
| `CADENCE_GEMINI_DEFAULT_MODEL`       | `gemini-2.5-flash`         | Default model when provider is `google`/`gemini`                                                 |
| `CADENCE_DEFAULT_LLM_TEMPERATURE`    | `0.1`                      | Default sampling temperature for LLMs                                                            |
| `CADENCE_DEFAULT_LLM_CONTEXT_WINDOW` | `32000`                    | Default context window size                                                                      |

> Notes
>
> - `CADENCE_DEFAULT_LLM_MODEL` is not used.
> - For Azure OpenAI, default model resolution uses `CADENCE_OPENAI_DEFAULT_MODEL`. You can still set

    `CADENCE_AZURE_OPENAI_DEFAULT_MODEL`, but it is not used by the core default-model resolver.

### API Keys

| Variable                       | Required | Description                         |
|--------------------------------|----------|-------------------------------------|
| `CADENCE_OPENAI_API_KEY`       | Yes\*    | OpenAI API key for GPT models       |
| `CADENCE_AZURE_OPENAI_API_KEY` | Yes\*    | Azure OpenAI API key                |
| `CADENCE_ANTHROPIC_API_KEY`    | Yes\*    | Anthropic API key for Claude models |
| `CADENCE_GOOGLE_API_KEY`       | Yes\*    | Google API key for Gemini models    |

\*At least one API key is required based on your chosen provider.

### Azure OpenAI Settings

When using `azure-openai` (alias: `azure`) as the provider, configure the following:

| Variable                           | Default              | Description                          |
|------------------------------------|----------------------|--------------------------------------|
| `CADENCE_AZURE_OPENAI_ENDPOINT`    | —                    | Azure OpenAI endpoint URL            |
| `CADENCE_AZURE_OPENAI_API_VERSION` | `2024-02-15-preview` | Azure OpenAI API version             |
| `CADENCE_AZURE_OPENAI_DEPLOYMENT`  | —                    | Azure OpenAI deployment (model name) |

### Plugin Configuration

| Variable              | Default                                     | Description                                            |
|-----------------------|---------------------------------------------|--------------------------------------------------------|
| `CADENCE_PLUGINS_DIR` | `["./plugins/src/cadence_example_plugins"]` | Plugin directory path(s). Accepts a path or JSON list. |

Examples:

```bash
# Single directory
CADENCE_PLUGINS_DIR=./plugins/src/cadence_example_plugins

# JSON list of directories
CADENCE_PLUGINS_DIR=["/abs/path/one", "/abs/path/two"]
```

### API Server Configuration

| Variable               | Default   | Description             |
|------------------------|-----------|-------------------------|
| `CADENCE_API_HOST`     | `0.0.0.0` | API server host address |
| `CADENCE_API_PORT`     | `8000`    | API server port number  |
| `CADENCE_CORS_ORIGINS` | `["*"]`   | CORS allowed origins    |

### Session Configuration

| Variable                      | Default | Description                    |
|-------------------------------|---------|--------------------------------|
| `CADENCE_SESSION_TIMEOUT`     | `3600`  | Session timeout in seconds     |
| `CADENCE_MAX_SESSION_HISTORY` | `100`   | Maximum session history length |

### Processing Configuration

| Variable                        | Default | Description                                                                  |
|---------------------------------|---------|------------------------------------------------------------------------------|
| `CADENCE_MAX_AGENT_HOPS`        | `25`    | Maximum agent switches before suspend/finalization                           |
| `CADENCE_GRAPH_RECURSION_LIMIT` | `50`    | Maximum LangGraph steps per request (prevents graph recursion/infinite loop) |

### Conversation Storage Configuration

#### Backend Selection

| Variable                               | Default  | Description                                            |
|----------------------------------------|----------|--------------------------------------------------------|
| `CADENCE_CONVERSATION_STORAGE_BACKEND` | `memory` | Conversation backend (`memory`, `redis`, `postgresql`) |

#### PostgreSQL Configuration

| Variable                        | Default | Description                                |
|---------------------------------|---------|--------------------------------------------|
| `CADENCE_POSTGRES_URL`          | —       | PostgreSQL connection URL (asyncpg format) |
| `CADENCE_POSTGRES_POOL_SIZE`    | `20`    | PostgreSQL connection pool size            |
| `CADENCE_POSTGRES_MAX_OVERFLOW` | `30`    | PostgreSQL connection pool max overflow    |

#### Redis Configuration

| Variable                  | Default | Description                |
|---------------------------|---------|----------------------------|
| `CADENCE_REDIS_URL`       | `None`  | Redis connection URL       |
| `CADENCE_REDIS_POOL_SIZE` | `20`    | Redis connection pool size |

### Persistence Configuration (Chat Memory/Checkpoints)

| Variable                                               | Default      | Description                                                                           |
|--------------------------------------------------------|--------------|---------------------------------------------------------------------------------------|
| `CADENCE_PERSISTENCE_TYPE`                             | `checkpoint` | Persistence mode: `checkpoint` or `memory`                                            |
| `CADENCE_PERSISTENCE_CHECKPOINT_LAYER`                 | `redis`      | Backend for checkpoints: `redis`, `postgres`, or `sqlite` (falls back to in-memory)   |
| `CADENCE_PERSISTENCE_CHECKPOINT_REDIS_TTL_MINUTES`     | `1440`       | Default TTL for Redis checkpoints (minutes)                                           |
| `CADENCE_PERSISTENCE_CHECKPOINT_REDIS_REFRESH_ON_READ` | `true`       | Whether to refresh TTL on read for Redis checkpoints                                  |
| `CADENCE_PERSISTENCE_MEMORY_LAYER`                     | `redis`      | Backend for active memory: `redis`, `postgres`, or `sqlite` (falls back to in-memory) |

Aliases supported: `anthropic` ≡ `claude`, `google` ≡ `gemini`, `azure-openai` ≡ `azure`.

## Storage and Persistence Options

### Conversation Storage Options

#### 1. Memory (Development)

```bash
CADENCE_CONVERSATION_STORAGE_BACKEND=memory
# Fast development and testing
# No external dependencies
# Data lost on restart
```

#### 2. Redis (High-performance, ephemeral)

```bash
CADENCE_CONVERSATION_STORAGE_BACKEND=redis
CADENCE_REDIS_URL=redis://localhost:6379/0
# Sub-millisecond reads/writes
# Persistence depends on Redis configuration
```

#### 3. PostgreSQL (Production)

```bash
CADENCE_CONVERSATION_STORAGE_BACKEND=postgresql
CADENCE_POSTGRES_URL=postgresql+asyncpg://user:pass@host:port/database
CADENCE_POSTGRES_POOL_SIZE=20
CADENCE_POSTGRES_MAX_OVERFLOW=30
# ACID transactions, complex queries, backup/recovery
```

### Persistence Options (Chat Memory/Checkpoints)

#### 1. In-Memory (Zero dependencies)

```bash
CADENCE_PERSISTENCE_TYPE=memory
# No external services
# Memory lost on restart
```

#### 2. Redis (Recommended for production checkpoints)

```bash
CADENCE_PERSISTENCE_TYPE=checkpoint
CADENCE_PERSISTENCE_CHECKPOINT_LAYER=redis
CADENCE_PERSISTENCE_MEMORY_LAYER=redis
CADENCE_REDIS_URL=redis://localhost:6379/0
# Distributed, TTL support, high performance
```

#### 3. PostgreSQL/SQLite (Enterprise/Portable)

```bash
# PostgreSQL
CADENCE_PERSISTENCE_TYPE=checkpoint
CADENCE_PERSISTENCE_CHECKPOINT_LAYER=postgres
CADENCE_PERSISTENCE_MEMORY_LAYER=postgres
CADENCE_POSTGRES_URL=postgresql+asyncpg://user:pass@host:5432/cadence

# SQLite (portable, local testing)
CADENCE_PERSISTENCE_TYPE=checkpoint
CADENCE_PERSISTENCE_CHECKPOINT_LAYER=sqlite
CADENCE_PERSISTENCE_MEMORY_LAYER=sqlite
```

## Environment File Setup

### Development Environment (`.env`)

```bash
# Cadence Multi-agents AI Framework Environment Configuration
CADENCE_APP_NAME="Cadence Multi-agents AI Framework (Dev)"
CADENCE_DEBUG=true

# UI Configuration
CADENCE_UI_TITLE="Cadence AI (Dev)"
CADENCE_UI_SUBTITLE="Intelligent conversations powered by multi-agent AI"
CADENCE_UI_WELCOME_TITLE="Welcome to Cadence AI!"
CADENCE_UI_WELCOME_MESSAGE="Start a conversation by typing a message below."
CADENCE_UI_WELCOME_HINT="Choose your preferred response style in Settings and start chatting."
CADENCE_UI_FOOTER="Powered by Cadence AI Framework"

# Bot Configuration
CADENCE_BOT_NAME="Cadence AI"
CADENCE_BOT_DESCRIPTION="Multiple Agents Chatbot System"
CADENCE_BOT_CREATOR="JonasKahn"
CADENCE_BOT_SPECIALIZATION="Business"
CADENCE_BOT_VERSION="1.3.0"

# LLM Provider Configuration
CADENCE_DEFAULT_LLM_PROVIDER=openai
# Optionally pin the default model for the chosen provider
# CADENCE_OPENAI_DEFAULT_MODEL=gpt-4.1
# CADENCE_ANTHROPIC_DEFAULT_MODEL=claude-sonnet-4-20250514
# CADENCE_GEMINI_DEFAULT_MODEL=gemini-2.5-flash

# API Keys
CADENCE_OPENAI_API_KEY=sk-your-openai-key-here

# Conversation Storage (Development - No external dependencies)
CADENCE_CONVERSATION_STORAGE_BACKEND=memory

# Persistence (keep everything in-memory for zero-deps dev)
CADENCE_PERSISTENCE_TYPE=memory

# Plugin Configuration
CADENCE_PLUGINS_DIR=./plugins/src/cadence_example_plugins

# API Server Configuration
CADENCE_API_HOST=127.0.0.1
CADENCE_API_PORT=8000

# Session Configuration
CADENCE_SESSION_TIMEOUT=1800
CADENCE_MAX_SESSION_HISTORY=50

# Processing Configuration
CADENCE_MAX_AGENT_HOPS=25
CADENCE_GRAPH_RECURSION_LIMIT=50

# --- Azure OpenAI (alternative) ---
# CADENCE_DEFAULT_LLM_PROVIDER=azure-openai
# CADENCE_AZURE_OPENAI_API_KEY=your-azure-openai-key
# CADENCE_AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
# CADENCE_AZURE_OPENAI_API_VERSION=2024-02-15-preview
# CADENCE_AZURE_OPENAI_DEPLOYMENT=gpt-4o
```

### Production Environment

```bash
# Production Configuration
CADENCE_APP_NAME="Cadence Multi-agents AI Framework"
CADENCE_DEBUG=false

# UI Configuration
CADENCE_UI_TITLE="Cadence AI"
CADENCE_UI_SUBTITLE="Intelligent conversations powered by multi-agent AI"
CADENCE_UI_WELCOME_TITLE="Welcome to Cadence AI!"
CADENCE_UI_WELCOME_MESSAGE="Start a conversation by typing a message below."
CADENCE_UI_WELCOME_HINT="Choose your preferred response style in Settings and start chatting."
CADENCE_UI_FOOTER="Powered by Cadence AI Framework"

# Bot Configuration
CADENCE_BOT_NAME="Cadence AI"
CADENCE_BOT_DESCRIPTION="Multiple Agents Chatbot System"
CADENCE_BOT_CREATOR="JonasKahn"
CADENCE_BOT_SPECIALIZATION="Business"
CADENCE_BOT_VERSION="1.3.0"

# LLM Provider Configuration
CADENCE_DEFAULT_LLM_PROVIDER=openai
# Provider-specific default model (optional)
# CADENCE_OPENAI_DEFAULT_MODEL=${OPENAI_MODEL:-gpt-4.1}

# API Keys (use secure secret management)
CADENCE_OPENAI_API_KEY=${OPENAI_API_KEY}

# Conversation Storage (Production)
CADENCE_CONVERSATION_STORAGE_BACKEND=postgresql
CADENCE_POSTGRES_URL=postgresql+asyncpg://cadence:password@db.internal:5432/cadence_prod
CADENCE_POSTGRES_POOL_SIZE=20
CADENCE_POSTGRES_MAX_OVERFLOW=30

# Persistence (Recommended: Redis)
CADENCE_PERSISTENCE_TYPE=checkpoint
CADENCE_PERSISTENCE_CHECKPOINT_LAYER=redis
CADENCE_PERSISTENCE_MEMORY_LAYER=redis
CADENCE_REDIS_URL=redis://redis:6379/0

# Plugin Configuration
CADENCE_PLUGINS_DIR=/opt/cadence/plugins

# API Server Configuration
CADENCE_API_HOST=0.0.0.0
CADENCE_API_PORT=8000

# Session Configuration
CADENCE_SESSION_TIMEOUT=3600
CADENCE_MAX_SESSION_HISTORY=100

# Processing Configuration
CADENCE_MAX_AGENT_HOPS=25
CADENCE_GRAPH_RECURSION_LIMIT=50

# --- Azure OpenAI (alternative) ---
# CADENCE_DEFAULT_LLM_PROVIDER=azure-openai
# CADENCE_AZURE_OPENAI_API_KEY=${AZURE_OPENAI_API_KEY}
# CADENCE_AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT}
# CADENCE_AZURE_OPENAI_API_VERSION=2024-02-15-preview
# CADENCE_AZURE_OPENAI_DEPLOYMENT=${AZURE_OPENAI_DEPLOYMENT}
```

## Docker Environment

### Docker Compose Example

```yaml
version: "3.8"

services:
  cadence:
    build: .
    ports:
      - "8000:8000"
    environment:
      - CADENCE_APP_NAME=Cadence Multi-agents AI Framework
      - CADENCE_DEBUG=false
      # UI Configuration
      - CADENCE_UI_TITLE=Cadence AI
      - CADENCE_UI_SUBTITLE=Intelligent conversations powered by multi-agent AI
      - CADENCE_UI_WELCOME_TITLE=Welcome to Cadence AI!
      - CADENCE_UI_WELCOME_MESSAGE=Start a conversation by typing a message below.
      - CADENCE_UI_WELCOME_HINT=Choose your preferred response style in Settings and start chatting.
      - CADENCE_UI_FOOTER=Powered by Cadence AI Framework
      # Bot Configuration
      - CADENCE_BOT_NAME=Cadence AI
      - CADENCE_BOT_DESCRIPTION=Multiple Agents Chatbot System
      - CADENCE_BOT_CREATOR=JonasKahn
      - CADENCE_BOT_SPECIALIZATION=Business
      - CADENCE_BOT_VERSION=1.0.3
      # LLM Configuration
      - CADENCE_DEFAULT_LLM_PROVIDER=openai
      # Optionally pin default model for provider
      # - CADENCE_OPENAI_DEFAULT_MODEL=gpt-4.1
      - CADENCE_OPENAI_API_KEY=${OPENAI_API_KEY}
      - CADENCE_PLUGINS_DIR=/opt/cadence/plugins
      - CADENCE_API_HOST=0.0.0.0
      - CADENCE_API_PORT=8000
      # Conversation storage
      - CADENCE_CONVERSATION_STORAGE_BACKEND=postgresql
      - CADENCE_POSTGRES_URL=postgresql+asyncpg://cadence:password@postgres:5432/cadence
      # Persistence (Redis)
      - CADENCE_PERSISTENCE_TYPE=checkpoint
      - CADENCE_PERSISTENCE_CHECKPOINT_LAYER=redis
      - CADENCE_PERSISTENCE_MEMORY_LAYER=redis
      - CADENCE_REDIS_URL=redis://redis:6379/0
      - CADENCE_MAX_AGENT_HOPS=25
      - CADENCE_GRAPH_RECURSION_LIMIT=50
      # Azure OpenAI (alternative)
      # - CADENCE_DEFAULT_LLM_PROVIDER=azure-openai
      # - CADENCE_AZURE_OPENAI_API_KEY=${AZURE_OPENAI_API_KEY}
      # - CADENCE_AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT}
      # - CADENCE_AZURE_OPENAI_API_VERSION=2024-02-15-preview
      # - CADENCE_AZURE_OPENAI_DEPLOYMENT=${AZURE_OPENAI_DEPLOYMENT}
    volumes:
      - ./plugins:/opt/cadence/plugins
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=cadence
      - POSTGRES_USER=cadence
      - POSTGRES_PASSWORD=password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

## Database Setup Instructions

### PostgreSQL Setup

```bash
# 1. Install PostgreSQL
brew install postgresql  # macOS
sudo apt install postgresql  # Ubuntu

# 2. Create database and user
sudo -u postgres psql
CREATE DATABASE cadence_db;
CREATE USER cadence_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE cadence_db TO cadence_user;
\q

# 3. Set environment variable
export CADENCE_POSTGRES_URL="postgresql+asyncpg://cadence_user:secure_password@localhost:5432/cadence_db"

# 4. Run migrations
poetry run alembic upgrade head
```

### Redis Setup

```bash
# 1. Install Redis
brew install redis  # macOS
sudo apt install redis-server  # Ubuntu

# 2. Start Redis
redis-server

# 3. Set environment variable
export CADENCE_REDIS_URL="redis://localhost:6379/0"
```

## Performance Characteristics

### Conversation Storage Performance

| Backend        | Write Speed | Read Speed | Scale       | Consistency | Best For    |
|----------------|-------------|------------|-------------|-------------|-------------|
| **Memory**     | Fastest     | Fastest    | Single Node | Strong      | Development |
| **Redis**      | Fastest     | Fastest    | Horizontal  | Eventual    | Caching     |
| **PostgreSQL** | Fast        | Fast       | Vertical    | ACID        | Production  |

### Persistence Layer Performance

| Backend        | Latency | Distributed | TTL | Persistence | Best For       |
|----------------|---------|-------------|-----|-------------|----------------|
| **Memory**     | <1ms    | No          | N/A | No          | Local dev      |
| **Redis**      | ~1ms    | Yes         | Yes | Optional    | Production     |
| **PostgreSQL** | ~5ms    | Yes         | Yes | Yes         | Enterprise     |
| **SQLite**     | ~1-3ms  | No          | No  | Yes         | Portable/local |

### Dockerfile Environment

```dockerfile
FROM python:3.13-slim

# Set environment variables
ENV CADENCE_APP_NAME="Cadence Multi-agents AI Framework"
ENV CADENCE_DEBUG=false
ENV CADENCE_DEFAULT_LLM_PROVIDER=openai
ENV CADENCE_API_HOST=0.0.0.0
ENV CADENCE_API_PORT=8000

# ... rest of Dockerfile
```

## Cloud Deployment

### Kubernetes ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cadence-config
data:
  CADENCE_APP_NAME: "Cadence Multi-agents AI Framework"
  CADENCE_DEBUG: "false"
  # UI Configuration
  CADENCE_UI_TITLE: "Cadence AI"
  CADENCE_UI_SUBTITLE: "Intelligent conversations powered by multi-agent AI"
  CADENCE_UI_WELCOME_TITLE: "Welcome to Cadence AI!"
  CADENCE_UI_WELCOME_MESSAGE: "Start a conversation by typing a message below."
  CADENCE_UI_WELCOME_HINT: "Choose your preferred response style in Settings and start chatting."
  CADENCE_UI_FOOTER: "Powered by Cadence AI Framework"
  # Bot Configuration
  CADENCE_BOT_NAME: "Cadence AI"
  CADENCE_BOT_DESCRIPTION: "Multiple Agents Chatbot System"
  CADENCE_BOT_CREATOR: "JonasKahn"
  CADENCE_BOT_SPECIALIZATION: "Business"
  CADENCE_BOT_VERSION: "1.3.0"
  # LLM Configuration
  CADENCE_DEFAULT_LLM_PROVIDER: "openai"
  # CADENCE_OPENAI_DEFAULT_MODEL: "gpt-4.1"
  CADENCE_PLUGINS_DIR: "/opt/cadence/plugins"
  CADENCE_API_HOST: "0.0.0.0"
  CADENCE_API_PORT: "8000"
  CADENCE_SESSION_TIMEOUT: "3600"
  CADENCE_MAX_AGENT_HOPS: "25"
  CADENCE_GRAPH_RECURSION_LIMIT: "50"
  # Conversation Storage
  CADENCE_CONVERSATION_STORAGE_BACKEND: "postgresql"
  CADENCE_POSTGRES_URL: "postgresql+asyncpg://cadence:password@postgres:5432/cadence"
  # Persistence
  CADENCE_PERSISTENCE_TYPE: "checkpoint"
  CADENCE_PERSISTENCE_CHECKPOINT_LAYER: "redis"
  CADENCE_PERSISTENCE_MEMORY_LAYER: "redis"
  CADENCE_REDIS_URL: "redis://redis:6379/0"
# --- Azure OpenAI (alternative) ---
#  CADENCE_DEFAULT_LLM_PROVIDER: "azure-openai"
#  CADENCE_AZURE_OPENAI_ENDPOINT: "https://your-resource.openai.azure.com/"
#  CADENCE_AZURE_OPENAI_API_VERSION: "2024-02-15-preview"
#  CADENCE_AZURE_OPENAI_DEPLOYMENT: "gpt-4o"
---
apiVersion: v1
kind: Secret
metadata:
  name: cadence-secrets
type: Opaque
data:
  CADENCE_OPENAI_API_KEY: <base64-encoded-key>
  # CADENCE_AZURE_OPENAI_API_KEY: <base64-encoded-key>
```

### AWS ECS Task Definition

```json
{
  "family": "cadence",
  "containerDefinitions": [
    {
      "name": "cadence",
      "image": "cadence:latest",
      "environment": [
        {
          "name": "CADENCE_APP_NAME",
          "value": "Cadence Multi-agents AI Framework"
        },
        {
          "name": "CADENCE_DEBUG",
          "value": "false"
        },
        {
          "name": "CADENCE_UI_TITLE",
          "value": "Cadence AI"
        },
        {
          "name": "CADENCE_UI_SUBTITLE",
          "value": "Intelligent conversations powered by multi-agent AI"
        },
        {
          "name": "CADENCE_UI_WELCOME_TITLE",
          "value": "Welcome to Cadence AI!"
        },
        {
          "name": "CADENCE_UI_WELCOME_MESSAGE",
          "value": "Start a conversation by typing a message below."
        },
        {
          "name": "CADENCE_UI_WELCOME_HINT",
          "value": "Choose your preferred response style in Settings and start chatting."
        },
        {
          "name": "CADENCE_UI_FOOTER",
          "value": "Powered by Cadence AI Framework"
        },
        {
          "name": "CADENCE_BOT_NAME",
          "value": "Cadence AI"
        },
        {
          "name": "CADENCE_BOT_DESCRIPTION",
          "value": "Multiple Agents Chatbot System"
        },
        {
          "name": "CADENCE_BOT_CREATOR",
          "value": "JonasKahn"
        },
        {
          "name": "CADENCE_BOT_SPECIALIZATION",
          "value": "Business"
        },
        {
          "name": "CADENCE_BOT_VERSION",
          "value": "1.3.0"
        },
        {
          "name": "CADENCE_DEFAULT_LLM_PROVIDER",
          "value": "openai"
        },
        {
          "name": "CADENCE_CONVERSATION_STORAGE_BACKEND",
          "value": "postgresql"
        },
        {
          "name": "CADENCE_PERSISTENCE_TYPE",
          "value": "checkpoint"
        },
        {
          "name": "CADENCE_PERSISTENCE_CHECKPOINT_LAYER",
          "value": "redis"
        }
      ],
      "secrets": [
        {
          "name": "CADENCE_OPENAI_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:openai-api-key"
        }
        /* Azure OpenAI (alternative)
        ,{ "name": "CADENCE_DEFAULT_LLM_PROVIDER", "value": "azure-openai" },
        { "name": "CADENCE_AZURE_OPENAI_API_KEY", "valueFrom": "arn:aws:secretsmanager:region:account:secret:azure-openai-api-key" },
        { "name": "CADENCE_AZURE_OPENAI_ENDPOINT", "value": "https://your-resource.openai.azure.com/" },
        { "name": "CADENCE_AZURE_OPENAI_API_VERSION", "value": "2024-02-15-preview" },
        { "name": "CADENCE_AZURE_OPENAI_DEPLOYMENT", "value": "gpt-4o" }
        */
      ]
    }
  ]
}
```

## Security Best Practices

### API Key Management

1. **Never commit API keys to version control**
2. **Use environment variables or secret management systems**
3. **Rotate keys regularly**
4. **Use least-privilege access**

### Environment Separation

```bash
# Development
.env.development

# Staging
.env.staging

# Production
.env.production
```

### Secret Management

```bash
# Use external secret managers
export CADENCE_OPENAI_API_KEY=$(aws secretsmanager get-secret-value --secret-id openai-api-key --query SecretString --output text)

# Or use Docker secrets
cadence $OPENAI_API_KEY | docker secret create openai-api-key -
```

## Configuration Validation

### Validate Configuration on Startup

Cadence validates configuration on startup:

```python
from .config.settings import Settings

# This will validate all configuration
settings = Settings()

# Check if required settings are present
if not settings.validate_provider_credentials(settings.default_llm_provider):
    raise ValueError(f"Missing credentials for {settings.default_llm_provider}")
```

## Troubleshooting Configuration

### Common Issues

**Plugin directory not found:**

```bash
# Check if directory exists
ls -la $CADENCE_PLUGINS_DIR

# Verify path is correct
cadence $CADENCE_PLUGINS_DIR
```

**API key not working:**

```bash
# Test API key
curl -H "Authorization: Bearer $CADENCE_OPENAI_API_KEY" \
  https://api.openai.com/v1/models
```

**Database connection issues:**

```bash
# Test PostgreSQL connection
psql $CADENCE_POSTGRES_URL -c "SELECT 1;"

# Test Redis connection
redis-cli -u $CADENCE_REDIS_URL ping
```

**Port already in use:**

```bash
# Check what's using the port
lsof -i :8000

# Change port in configuration
export CADENCE_API_PORT=8001
```

### Debug Mode

Enable debug mode to see detailed configuration:

```bash
export CADENCE_DEBUG=true
python -m cadence.main
```

## Deployment Scenarios

### Development (No external dependencies)

```bash
# .env file
CADENCE_CONVERSATION_STORAGE_BACKEND=memory
CADENCE_PERSISTENCE_TYPE=memory
CADENCE_OPENAI_API_KEY=your_key_here

# Start immediately
python -m cadence start all
```

### Production (PostgreSQL + Redis)

```bash
# Setup steps:
# 1. Create PostgreSQL database
# 2. Run migrations: poetry run alembic upgrade head
# 3. Start Redis server
# 4. Start Cadence: python -m cadence start all
```

### Hybrid Testing (Mix backends)

```bash
# PostgreSQL for conversations, in-memory persistence
CADENCE_CONVERSATION_STORAGE_BACKEND=postgresql
CADENCE_POSTGRES_URL=postgresql+asyncpg://cadence:password@localhost:5432/cadence_test
CADENCE_PERSISTENCE_TYPE=memory

# Memory conversations, Redis persistence
CADENCE_CONVERSATION_STORAGE_BACKEND=memory
CADENCE_PERSISTENCE_TYPE=checkpoint
CADENCE_PERSISTENCE_CHECKPOINT_LAYER=redis
CADENCE_PERSISTENCE_MEMORY_LAYER=redis
CADENCE_REDIS_URL=redis://localhost:6379/1
```

## Customizing UI and Bot Configuration

### UI Customization Examples

**Custom Branding:**

```bash
export CADENCE_UI_TITLE="My Company AI Assistant"
export CADENCE_UI_SUBTITLE="Powered by advanced multi-agent technology"
export CADENCE_UI_WELCOME_TITLE="Welcome to My Company AI!"
export CADENCE_UI_WELCOME_MESSAGE="How can I assist you today?"
export CADENCE_UI_WELCOME_HINT="I'm here to help with your questions and tasks."
export CADENCE_UI_FOOTER="© 2024 My Company - AI Assistant"
```

**Multi-language Support:**

```bash
# Spanish
export CADENCE_UI_TITLE="Asistente IA"
export CADENCE_UI_SUBTITLE="Conversaciones inteligentes impulsadas por IA multi-agente"
export CADENCE_UI_WELCOME_TITLE="¡Bienvenido al Asistente IA!"
export CADENCE_UI_WELCOME_MESSAGE="Comience una conversación escribiendo un mensaje abajo."
export CADENCE_UI_WELCOME_HINT="Elija su estilo de respuesta preferido en Configuración y comience a chatear."
export CADENCE_UI_FOOTER="Desarrollado por Cadence AI Framework"
```

### Bot Customization Examples

**Company-specific Bot:**

```bash
export CADENCE_BOT_NAME="My Company Assistant"
export CADENCE_BOT_DESCRIPTION="Intelligent AI Assistant for My Company"
export CADENCE_BOT_CREATOR="My Company"
export CADENCE_BOT_SPECIALIZATION="Customer Support and Sales"
export CADENCE_BOT_VERSION="2.1.0"
```

**Specialized Bot:**

```bash
export CADENCE_BOT_NAME="Tech Support Bot"
export CADENCE_BOT_DESCRIPTION="Technical Support AI Assistant"
export CADENCE_BOT_CREATOR="IT Department"
export CADENCE_BOT_SPECIALIZATION="Technical Support"
export CADENCE_BOT_VERSION="1.5.2"
```

## Configuration Behavior

The system automatically:

1. Reads configuration from environment variables
2. Selects appropriate providers/backends based on your settings
3. Handles connection pooling and health monitoring
4. Falls back gracefully to in-memory if databases are unavailable
5. Applies UI and bot customizations dynamically

## Next Steps

- **[Production Setup](production.md)** - Production deployment guide
