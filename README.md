# Cadence AI Framework

**Multi-Tenant, Multi-Orchestrator AI Agent Platform**

Cadence is a production-ready framework for deploying AI agent orchestrators at scale. It supports three orchestration
frameworks (LangGraph, Google ADK, OpenAI Agents SDK) across seven orchestration modes (Supervisor, Coordinator,
Handoff, Pipeline, Reflection, Ensemble, Hierarchical), giving you 21 orchestrator configurations out of the box.

---

![Dashboard](docs/images/dashboard.png)

## Features

### Multi-Backend Orchestration

- **LangGraph**: State graph-based orchestration with explicit control flow and built-in checkpointing
- **Google ADK**: Google's Agent Development Kit with native Gemini model support
- **OpenAI Agents SDK**: Function-calling agents with native OpenAI / LiteLLM integration

### Multi-Tenancy Built-In

- Complete tenant isolation (data, instances, plugins)
- Per-tenant LLM configurations (BYOK — Bring Your Own Key)
- Per-tenant plugin directories
- Role-based access control with multi-org membership (one user, many orgs)

### Seven Orchestration Modes

| Mode             | Control Flow                                                | Status      |
|------------------|-------------------------------------------------------------|-------------|
| **Supervisor**   | router → planner → executor → synthesizer (8-node pipeline) | Implemented |
| **Coordinator**  | router → agent_A \| agent_B → synthesizer                   | Placeholder |
| **Handoff**      | agent_A → agent_B → agent_C (peer chain)                    | Placeholder |
| **Pipeline**     | stage_1 → stage_2 → … → synthesizer                         | Placeholder |
| **Reflection**   | generator ↔ critic (loop, max N iterations)                 | Placeholder |
| **Ensemble**     | dispatcher → [agent_1 \|\| … \|\| agent_N] → merger         | Placeholder |
| **Hierarchical** | top_router → [team_A \| team_B] → top_synthesizer           | Placeholder |

Each node in Supervisor mode supports independent LLM config, model name, temperature, max tokens, and prompt override.
See [Orchestration Modes](#orchestration-modes-1) for details.

### Hot-Reload Everything

- Configuration changes without restart
- Plugin updates without downtime
- Atomic orchestrator rebuilds
- RabbitMQ event-driven loading across multiple nodes (dedup via config hash)

### Scalable Architecture

- Multi-tier orchestrator pool (Hot / Warm / Cold)
- Shared resource registries (models, plugin bundles, graph templates)
- LRU eviction and prewarming strategies
- Handles 1000+ orchestrator instances efficiently

### Plugin System

- Framework-agnostic plugin SDK (`cadence-sdk`)
- Two-table DB catalog: `system_plugins` (all orgs) + `org_plugins` (per-tenant)
- Version pinning (`pid@version`) with `is_latest` tracking
- Per-plugin `default_settings` stored at upload time
- Upload via API; S3/MinIO as source of truth for zip packages

### Security

- JWT authentication — `jti` is a ULID; session data stored in Redis
- Instant token revocation by deleting the Redis session key
- Multi-org membership: one user can belong to many orgs with per-org admin rights
- Rate limiting (per-tenant, Redis-backed)
- CORS support

### Infrastructure

- **PostgreSQL**: Organizations, orchestrator instances, settings, users, memberships, plugin catalog, LLM configs
- **MongoDB**: Per-tenant conversation storage (database-per-org)
- **Redis**: Session store (JWT sessions keyed by ULID jti) + caching + rate limiting
- **RabbitMQ**: Orchestrator load/reload/unload events (topic exchange, per-node queues)
- **S3 / MinIO**: Plugin zip storage

### Real-Time Streaming

- Server-Sent Events (SSE) for real-time responses
- Framework-agnostic event protocol
- Event types: `agent_start`, `agent_end`, `tool_start`, `tool_end`, `message`, `error`, `metadata`
- Token streaming from: synthesizer, clarifier, responder, error_handler nodes

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         FastAPI API                         │
│  ┌──────────────┬──────────────┬──────────────────────────┐ │
│  │ Multi-Tenant │ Rate Limiting│  JWT + Redis Session     │ │
│  │  Middleware  │  Middleware  │     Middleware           │ │
│  └──────────────┴──────────────┴──────────────────────────┘ │
│                                                             │
│  ┌───────────┬───────────────┬──────────────┬─────────────┐ │
│  │   Auth    │ Orchestrators │   Plugins    │   Tenants   │ │
│  │  Routers  │    Routers    │   Routers    │   Routers   │ │
│  └───────────┴───────────────┴──────────────┴─────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Service Layer                           │
│  ┌──────────────┬──────────────┬──────────────────────────┐ │
│  │ Orchestrator │ Conversation │   Tenant / Auth          │ │
│  │   Service    │   Service    │      Service             │ │
│  ├──────────────┴──────────────┴──────────────────────────┤ │
│  │  Settings Service (instance lifecycle + config hash)   │ │
│  │  Plugin Service   (catalog + upload + settings schema) │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator Pool                        │
│                                                             │
│  Hot Tier (200)     Warm Tier (300)      Cold Tier (500)    │
│  ┌─────────────┐   ┌─────────────┐      ┌─────────────┐     │
│  │ Orchestrator│   │   Config    │      │  Metadata   │     │
│  │   Instance  │   │   Cached    │      │    Only     │     │
│  └─────────────┘   └─────────────┘      └─────────────┘     │
│                                                             │
│  Shared Resources:                                          │
│  ┌──────────────┬─────────────────┬────────────────────┐    │
│  │  Model Pool  │  Bundle Cache   │  Template Cache    │    │
│  │ (ref counted)│ (ref counted)   │  (ref counted)     │    │
│  └──────────────┴─────────────────┴────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │  LangGraph   │ │ OpenAI Agents│ │  Google ADK  │
    │   Backend    │ │   Backend    │ │   Backend    │
    └──────────────┘ └──────────────┘ └──────────────┘
              │               │               │
    ┌─────────┼──────────┐ ┌─────┼──────┐ ┌──────┼──────┐
    ▼         ▼          ▼ ▼     ▼      ▼ ▼      ▼      ▼
Supervisor Coordinator Handoff Pipeline Reflection Ensemble Hierarchical
                              (7 modes × 3 backends = 21 types)
              │               │               │
              └───────────────┴───────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  Plugin Manager  │
                    │  (SDKPluginMgr)  │
                    │ ┌──────────────┐ │
                    │ │ Plugin Agent │ │
                    │ │   + UvTools  │ │
                    │ └──────────────┘ │
                    └──────────────────┘
```

---

## Installation

### Prerequisites

- Python 3.13+
- Poetry 2.0+
- Docker & Docker Compose (for local databases)
- Node.js 20+ and pnpm (for the UI)

### 1. Clone and Install

```bash
git clone https://github.com/jonaskahn/cadence.git
cd cadence

# Install core dependencies
poetry install

# Also install dev dependencies
poetry install --with dev
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Key variables:

```bash
# API
CADENCE_API_HOST=0.0.0.0
CADENCE_API_PORT=8000
CADENCE_ENVIRONMENT=development

# Security
CADENCE_SECRET_KEY=your-secret-key-here
CADENCE_JWT_ALGORITHM=HS256
CADENCE_ACCESS_TOKEN_EXPIRE_MINUTES=180

# Databases
CADENCE_POSTGRES_URL=postgresql+asyncpg://cadence:cadence_dev_password@localhost/cadence_dev
CADENCE_MONGO_URL=mongodb://cadence:cadence_dev_password@localhost:27017
CADENCE_REDIS_URL=redis://:cadence_dev_password@localhost:6379
CADENCE_RABBITMQ_URL=amqp://cadence:cadence_dev_password@localhost/

# Storage
CADENCE_STORAGE_ROOT=/var/cadence
CADENCE_SYSTEM_PLUGINS_DIR=/var/cadence/system_plugins
CADENCE_TENANT_PLUGINS_ROOT=/var/cadence/tenant_plugins

# Features
CADENCE_ENABLE_DIRECTORY_PLUGINS=true
CADENCE_API_ENABLED_PROTECT=true

# Logging
CADENCE_LOG_LEVEL=INFO
CADENCE_LOG_FORMAT=json
```

### 3. Start Infrastructure

```bash
# Start PostgreSQL, MongoDB, Redis, RabbitMQ, MinIO, LiteLLM via Docker Compose
make db-up

# Run Alembic migrations
make migrate
```

Local service URLs are printed after `make db-up`:

| Service             | URL                        |
|---------------------|----------------------------|
| Cadence API         | http://localhost:8000      |
| Cadence Docs        | http://localhost:8000/docs |
| pgAdmin             | http://localhost:5050      |
| Mongo Express       | http://localhost:8081      |
| Redis Commander     | http://localhost:8082      |
| RabbitMQ Management | http://localhost:15672     |
| MinIO Console       | http://localhost:9001      |
| LiteLLM             | http://localhost:4000      |

### 4. Bootstrap Admin

Creates a `sys_admin` user and issues a ready-to-use JWT:

```bash
make bootstrap

# Custom user:
poetry run python scripts/bootstrap.py --username alice --email alice@acme.com

# Specify a password:
poetry run python scripts/bootstrap.py --password mysecretpassword

# Add a second sys_admin (skips schema creation):
poetry run python scripts/bootstrap.py --add-sys-admin --username bob --email bob@example.com
```

Output:

```
╔──────────────────────────────────────────────────────────────────────────────────╗
║  Credentials                                                                     ║
╠──────────────────────────────────────────────────────────────────────────────────╣
║  User ID   : <uuid>                                                              ║
║  Username  : admin                                                               ║
║  Email     : admin@localhost                                                     ║
║  Role      : sys_admin                                                           ║
║  Password  : xK9mP2rLnQwYfZe8Rj                                                  ║
║  Bearer    : (Store credentials securely — they cannot be recovered after this)  ║
╚──────────────────────────────────────────────────────────────────────────────────╝
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9....
```

> **Note:** `sys_admin` has no org membership by default. Use `POST /api/admin/orgs` to create organizations, then add
> users.

---

## Running

### Development Server (auto-reload)

```bash
make dev
# → http://localhost:8000
```

### Production Server

```bash
make start
# → http://localhost:8000  (4 workers)
```

### One-Command Quick Start

```bash
# Databases + migrate + dev server in one step
make up
```

### Nuxt UI

```bash
cd ui
pnpm install
pnpm dev
# → http://localhost:3000
```

Pages:

| Page          | Covers                                                                    |
|---------------|---------------------------------------------------------------------------|
| Orchestrators | Create, view, edit, manage plugins, suspend/activate                      |
| Plugins       | List, inspect settings schema, activate versions                          |
| Settings      | LLM configurations (BYOK), org members                                    |
| Admin         | Organizations, users, system plugins, health, pool stats, global settings |

---

## Configuration

### Running Migrations

```bash
make migrate           # Apply all pending migrations
make migrate-down      # Rollback last migration
make migrate-create MSG="add new column"
make migrate-history   # Show migration history
make migrate-current   # Show current version
```

### Makefile Reference

```bash
make help              # Show all available commands
make up                # Quick start: db-up + migrate + dev server
make down              # Stop databases
make dev               # Development server (auto-reload)
make start             # Production server
make test              # Run all tests
make test-cov          # Tests with HTML coverage report
make format            # Format with Black + Ruff
make lint              # Lint with Ruff
make check             # format + lint + type-check
make bootstrap         # Create initial sys_admin user and issue a JWT
make openapi           # Export OpenAPI schema to scripts/openapi_schema.json
make health            # Quick health check (curl /health)
make stats             # Pool statistics (curl /api/admin/pool/stats)
make psql              # Connect to local PostgreSQL
make mongo             # Connect to local MongoDB
make redis             # Connect to local Redis CLI
make clean             # Remove __pycache__, .pytest_cache, etc.
make db-reset-full     # Full reset: wipe volumes → start → migrate
```

---

## Quick Start (curl)

### 1. Login

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "<password from bootstrap>"}' \
  | jq -r '.token')

export AUTH="Authorization: Bearer $TOKEN"
```

### 2. Create an Organization

```bash
curl -s -X POST http://localhost:8000/api/admin/orgs \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme Corporation"}' | jq .

export ORG_ID="<org_id from above>"
```

### 3. Add an LLM Configuration

```bash
curl -X POST http://localhost:8000/api/orgs/$ORG_ID/llm-configs \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "primary",
    "provider": "openai",
    "api_key": "sk-...",
    "base_url": null,
    "additional_config": {}
  }'
```

Supported providers: `openai`, `anthropic`, `google`, `azure`, `groq`, `litellm`, `tensorzero`

### 4. Create an Orchestrator

```bash
curl -X POST http://localhost:8000/api/orgs/$ORG_ID/orchestrators \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "customer-support",
    "framework_type": "langgraph",
    "mode": "supervisor",
    "active_plugin_ids": ["<plugin-uuid>"],
    "config": {
      "default_llm_config_id": 1,
      "mode_config": {
        "max_agent_hops": 10,
        "parallel_tool_calls": true,
        "invoke_timeout": 60,
        "use_llm_validation": false
      }
    }
  }'
```

### 5. Send a Chat Request (SSE Streaming)

```bash
curl -X POST http://localhost:8000/api/orgs/$ORG_ID/chat/completion \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "<instance_id>",
    "message": "What is the weather in San Francisco?",
    "conversation_id": "conv_abc123"
  }'
```

Response is a stream of SSE events: `agent_start`, `agent_end`, `tool_start`, `tool_end`, `message`, `error`,
`metadata`.

---

## API Reference

Full interactive API reference is available at `http://localhost:8000/docs` (Swagger UI) when the server is running.

Key resource groups: **auth** (`/api/auth/`), **orgs** (`/api/orgs/{org_id}/`), **orchestrators**, **llm-configs**, *
*plugins**, **chat**, **admin** (`/api/admin/`).

---

## Core Concepts

### Authentication & Sessions

Login returns a signed JWT. The JWT carries only `sub` (user_id) and `jti` (a ULID session key). Session data (org
memberships, roles) lives in Redis, keyed by the JWT's `jti`:

- **No org/role in the token** — stale tokens cannot escalate privileges
- **Instant revocation** — delete the Redis key to invalidate immediately
- **Multi-org support** — one user can belong to many orgs

### Roles

| Role        | Scope         | Permissions                                           |
|-------------|---------------|-------------------------------------------------------|
| `sys_admin` | Platform-wide | CRUD all orgs, create users, global settings          |
| `org_admin` | Per-org       | Manage LLM configs, orchestrators, add/remove members |
| `user`      | Per-org       | Send chat requests                                    |

A user can be `org_admin` in one org and `user` in another. `sys_admin` is a platform-level flag independent of org
membership.

### LLM Providers

| Provider     | Key          | LangGraph              | OpenAI Agents              | Google ADK          |
|--------------|--------------|------------------------|----------------------------|---------------------|
| OpenAI       | `openai`     | ChatOpenAI             | OpenAIChatCompletionsModel | —                   |
| Anthropic    | `anthropic`  | ChatAnthropic          | —                          | —                   |
| Google       | `google`     | ChatGoogleGenerativeAI | —                          | Native (model name) |
| Azure OpenAI | `azure`      | AzureChatOpenAI        | —                          | —                   |
| Groq         | `groq`       | ChatGroq               | —                          | —                   |
| LiteLLM      | `litellm`    | ChatOpenAI (base_url)  | LitellmModel               | LiteLlm             |
| TensorZero   | `tensorzero` | ChatOpenAI (base_url)  | LitellmModel               | LiteLlm             |

**Framework-aware filtering** — the UI automatically hides unsupported providers:

- **LangGraph**: all providers
- **Google ADK**: `google`, `litellm`, `anthropic`
- **OpenAI Agents**: `openai`, `litellm`

---

## Orchestration Modes

### Supervisor Mode

An 8-node pipeline: `router` → `planner` → `executor` → `validator` (optional) → `synthesizer`, with `clarifier`,
`responder`, and `error_handler` as alternate exits. Each node independently supports its own `llm_config_id`,
`model_name`, `prompt`, `temperature`, and `max_tokens`.

| Node            | Role                                      | Streams |
|-----------------|-------------------------------------------|---------|
| `router`        | Intent classification (structured output) | —       |
| `planner`       | Tool selection                            | —       |
| `executor`      | Tool invocation                           | —       |
| `validator`     | Optional LLM result validation            | —       |
| `synthesizer`   | Final response composition                | yes     |
| `clarifier`     | Asks clarifying questions                 | yes     |
| `responder`     | Conversational / meta-query replies       | yes     |
| `error_handler` | Graceful error recovery                   | yes     |

Retrieve default prompt templates: `GET /api/engine/supervisor/prompts`. See
the [docs](https://jonaskahn.github.io/cadence) for the full config schema.

### Other Modes

The remaining modes (Coordinator, Handoff, Pipeline, Reflection, Ensemble, Hierarchical) are placeholder
implementations. See the [full documentation](https://jonaskahn.github.io/cadence) for configuration details and
use-case guidance for each mode.

---

## Backend Frameworks

### LangGraph

- State graph with explicit control flow and conditional edges
- Built-in LangGraph checkpointing
- Excellent debugging and replay support
- **Models:** All providers (OpenAI, Anthropic, Google, Azure, Groq, LiteLLM, TensorZero)

### Google ADK

- Native Gemini model support via ADK session management
- Fresh ADK session per `astream()` call
- System prompt templating with instruction providers
- **Models:** `google`, `litellm`, `anthropic`

### OpenAI Agents SDK

- Native OpenAI function-calling agents
- LiteLLM-compatible models for non-OpenAI providers
- **Models:** `openai`, `litellm`

---

## Plugin Development

Plugins are developed against the `cadence-sdk`. See [sdk/README.md](./sdk/README.md) for the complete guide.

### SDK Overview

```python
from cadence_sdk import BasePlugin, BaseAgent, PluginMetadata, uvtool, plugin_settings, UvTool


class MyPlugin(BasePlugin):
    @staticmethod
    def get_metadata() -> PluginMetadata:
        return PluginMetadata(
            pid="com.example.my_plugin",
            name="My Plugin",
            version="1.0.0",
            description="Does something useful",
            stateless=True,
        )

    @staticmethod
    def create_agent() -> BaseAgent:
        return MyAgent()


@plugin_settings([
    {"key": "api_key", "type": "str", "description": "API key", "sensitive": True, "required": True},
    {"key": "timeout", "type": "int", "description": "Request timeout", "default": 30},
])
class MyAgent(BaseAgent):
    def get_system_prompt(self) -> str:
        return "You are a helpful assistant."

    def get_tools(self) -> list[UvTool]:
        return [self._search_tool]

    def initialize(self, config: dict):
        self.api_key = config["api_key"]

    @uvtool(description="Search for something")
    def search(self, query: str) -> str:
        ...
```

**Key SDK components:**

- `BasePlugin` / `BaseAgent` — core abstract classes
- `@uvtool` — wraps sync/async functions as framework-agnostic tools
- `@plugin_settings` — declares settings schema (key, type, description, default, sensitive, required)
- `CacheConfig` — semantic caching (TTL + cosine similarity threshold)
- `UvMessage` types — `UvHumanMessage`, `UvAIMessage`, `UvSystemMessage`, `UvToolMessage`

> **Auto-discovery**: Cadence scans configured plugin directories and auto-registers any `BasePlugin` subclass found in
> a `plugin.py` file. No manual registration needed — just place your plugin in a directory with a `plugin.py` entry
> point.

### Installing Plugins

Upload via API — the server extracts metadata from `plugin.py`, stores the zip in S3/MinIO, and writes to the catalog:

```bash
# System-wide (sys_admin)
curl -X POST http://localhost:8000/api/admin/plugins/upload \
  -H "Authorization: Bearer $TOKEN" -F "file=@my_plugin.zip"

# Tenant-specific (org_admin)
curl -X POST http://localhost:8000/api/orgs/$ORG_ID/plugins/upload \
  -H "Authorization: Bearer $TOKEN" -F "file=@my_plugin.zip"
```

Pin a specific version by passing its UUID in `active_plugin_ids` when creating/updating an orchestrator.

---

## Multi-Tier Pool

Instances live in three tiers: **Cold** (metadata only) → **Warm** (config cached) → **Hot** (fully built). Promoted on
demand, evicted by LRU. Shared resources (models, plugin bundles, graph templates) are ref-counted across instances.

Configure via `PATCH /api/admin/settings/{key}`: `max_hot_pool_size`, `prewarm_strategy` (`"recent"`, `"all"`,
`"none"`), `prewarm_count`, `warm_tier_ttl`. Monitor with `GET /api/admin/pool/stats`.

---

## Hot-Reload

`PATCH /api/orgs/{org_id}/orchestrators/{id}/config` writes the new config, recomputes a hash, publishes a reload event
to RabbitMQ, and atomically rebuilds the pool instance. No downtime — in-flight requests finish on the old instance.
Unchanged configs (same hash) are a no-op.

Manually promote or evict with `POST .../load` and `POST .../unload` (202 fire-and-forget).

---

## Performance Tips

- Prewarm frequent instances: `prewarm_strategy: "recent"`
- Use `stateless=True` in plugins for bundle sharing
- Reuse LLM configs — same API key shares a model instance
- Enable semantic caching on tools (TTL 3600s, threshold 0.85)

## Monitoring

```bash
GET /health                  # Basic liveness
GET /api/admin/health        # All orchestrators (sys_admin)
GET /api/admin/pool/stats    # Pool statistics (sys_admin)
```

Structured JSON logs via `CADENCE_LOG_FORMAT=json`.

## Deployment

Run via Docker or directly with Poetry. For HA: use shared S3/MinIO for plugins, a RabbitMQ cluster (per-node queues,
hash-based dedup), sticky-session load balancer for SSE, and PostgreSQL/MongoDB replicas.

---

## Troubleshooting

**Orchestrator build fails with "Plugin not found"**

```bash
GET /api/orgs/{org_id}/plugins   # Verify plugin is in catalog
```

**"No LLM config found" error**

```bash
GET /api/orgs/{org_id}/llm-configs   # Verify config exists
POST /api/orgs/{org_id}/llm-configs  # Add a config
```

**401 Unauthorized after login**

```bash
# Token session may have expired or Redis is down
POST /api/auth/login   # Re-authenticate
make redis             # Check Redis connectivity
```

**Hot-reload not triggering**

```bash
# Check RabbitMQ
open http://localhost:15672   # cadence / cadence_dev_password
# Verify exchange cadence.orchestrators exists with bindings

# Manually trigger
PATCH /api/orgs/{org_id}/orchestrators/{id}/config
# or
POST /api/orgs/{org_id}/orchestrators/{id}/load
```

**High memory usage**

```bash
GET /api/admin/pool/stats
PATCH /api/admin/settings/max_hot_pool_size  # {"value": 100}
```

---

## Security Best Practices

1. **Never commit API keys** — Use environment variables or encrypted secrets
2. **Rotate JWT secrets** — Change `CADENCE_SECRET_KEY` regularly
3. **Session TTL** — Configure `CADENCE_ACCESS_TOKEN_EXPIRE_MINUTES` appropriately
4. **Use HTTPS** — Deploy behind a reverse proxy (nginx, Caddy)
5. **Enable rate limiting** — Configure per-tenant limits
6. **Network isolation** — PostgreSQL, MongoDB, Redis should not be publicly exposed
7. **Principle of least privilege** — Grant minimal database permissions

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Write tests for new functionality
4. Ensure all tests pass: `poetry run pytest`
5. Follow code style: `poetry run black . && poetry run ruff check .`
6. Submit a pull request

---

## License

See [LICENSE](./LICENSE) file.

---

## Support

- **Issues**: [GitHub Issues](https://github.com/jonaskahn/cadence/issues)
- **Discussions**: [GitHub Discussions](https://github.com/jonaskahn/cadence/discussions)
- **Email**: me@ifelse.one

---

## Acknowledgments

Built with:

- [LangGraph](https://github.com/langchain-ai/langgraph)
- [Google ADK](https://google.github.io/adk-docs/)
- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Pydantic](https://docs.pydantic.dev/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [Redis](https://redis.io/)
- [PostgreSQL](https://www.postgresql.org/)
- [MongoDB](https://www.mongodb.com/)
- [RabbitMQ](https://www.rabbitmq.com/)

---

**Cadence AI Framework** — Production-ready multi-tenant AI orchestration at scale.
