# Cadence AI Framework

**Multi-Tenant, Multi-Orchestrator AI Agent Platform**

Cadence is a production-ready framework for deploying AI agent orchestrators at scale. It supports three major
orchestration frameworks (LangGraph, OpenAI Agents SDK, Google ADK) and three orchestration modes (supervisor,
coordinator, handoff), giving you 9 different orchestrator configurations to choose from.

---

![Dashboard](docs/images/dashboard.png)

## Features

### 🎯 Multi-Backend Orchestration

- **LangGraph**: State graph-based orchestration with explicit control flow
- **OpenAI Agents SDK**: Function calling agents with native OpenAI integration
- **Google ADK**: Agent development kit with Gemini models

### 🏢 Multi-Tenancy Built-In

- Complete tenant isolation (data, instances, plugins)
- Per-tenant LLM configurations (BYOK - Bring Your Own Key) with `model_name` tracking
- Per-tenant plugin directories
- Role-based access control with multi-org membership

### 🔄 Three Orchestration Modes

- **Supervisor**: 6-node workflow (Supervisor → Control Tools → Validation → Synthesizer / Facilitator /
  Conversational / Error Handler). Each node supports independent LLM config and prompt override.
- **Coordinator**: Routing agent delegates to specialized plugin agents
- **Handoff**: Peer-to-peer agent collaboration with explicit transfers

### 🔥 Hot-Reload Everything

- Configuration changes without restart
- Plugin updates without downtime
- Atomic orchestrator rebuilds
- RabbitMQ event-driven loading across multiple nodes (dedup via config_hash)

### 🚀 Scalable Architecture

- Multi-tier orchestrator pool (Hot/Warm/Cold)
- Shared resource registries (models, plugin bundles, graph templates)
- LRU eviction and prewarming strategies
- Handles 1000+ orchestrator instances efficiently

### 🛠️ Plugin System

- Framework-agnostic plugin SDK ([cadence-sdk](./sdk/README.md))
- Two-table DB catalog: `system_plugins` (all orgs) + `org_plugins` (per-tenant)
- Version pinning (`pid@version`) with `is_latest` tracking
- Per-plugin `default_settings` stored at upload time
- Upload via API; S3/MinIO as source of truth for zip packages

### 🔐 Security

- JWT authentication — `jti` is a ULID; session data (org memberships, roles) stored in Redis
- Instant token revocation by deleting the Redis session key
- Multi-org membership: one user can belong to many orgs with per-org admin rights
- Rate limiting (per-tenant, Redis-backed)
- CORS support

### 💾 Infrastructure

- **PostgreSQL**: Organizations, orchestrator instances, settings, users, org memberships, conversations, plugin catalog
- **MongoDB**: Per-tenant conversation storage (database-per-org)
- **Redis**: Session store (JWT sessions keyed by ULID jti) + caching + rate limiting
- **RabbitMQ**: Orchestrator load/reload/unload events (topic exchange, per-node queues)
- **S3 / MinIO**: Plugin zip storage (optional)

### 📡 Streaming

- Server-Sent Events (SSE) for real-time responses
- Framework-agnostic event protocol
- Event types: agent_start, agent_end, tool_start, tool_end, message, error, metadata

### 🧪 Advanced Features

- Semantic caching with vector similarity
- Message compaction for long conversations
- Health monitoring with auto-recovery
- Token usage tracking (extensible)
- OpenTelemetry support (extensible)

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
    ┌─────────┼───────┐ ┌─────┼──────┐ ┌──────┼──────┐
    ▼         ▼       ▼ ▼     ▼      ▼ ▼      ▼      ▼
Supervisor Coordinator Handoff (3 modes × 3 backends = 9 types)
              │               │               │
              └───────────────┴───────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  Plugin Manager  │
                    │                  │
                    │ ┌──────────────┐ │
                    │ │ Plugin Agent │ │
                    │ │   + Tools    │ │
                    │ └──────────────┘ │
                    └──────────────────┘
```

---

## Installation

### Prerequisites

- Python 3.13+
- Poetry 2.0+
- Docker & Docker Compose (for local databases)

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

Copy the example and fill in your values:

```bash
cp .env.example .env
```

```bash
# API
CADENCE_API_HOST=0.0.0.0
CADENCE_API_PORT=8000
CADENCE_ENVIRONMENT=development

# Security
CADENCE_SECRET_KEY=your-secret-key-here
CADENCE_JWT_ALGORITHM=HS256
CADENCE_ACCESS_TOKEN_EXPIRE_MINUTES=30

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

### 3. Start Databases

```bash
# Start PostgreSQL, MongoDB, Redis, RabbitMQ, MinIO via Docker Compose
make db-up

# Run Alembic migrations
make migrate
```

RabbitMQ management UI: http://localhost:15672 (cadence / cadence_dev_password)

### 4. Bootstrap Admin

Creates a `sys_admin` user (no default org) and issues a ready-to-use JWT:

```bash
make bootstrap

# Custom user:
poetry run python scripts/bootstrap.py --username alice --email alice@acme.com

# Specify a password instead of auto-generating one:
poetry run python scripts/bootstrap.py --password mysecretpassword

# Add a second sys_admin to an existing installation (skips schema creation):
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

The token is ready to use immediately. It expires after `CADENCE_ACCESS_TOKEN_EXPIRE_MINUTES`
(default 30 min); use `POST /api/auth/login` to get a fresh token after that.

> **Note:** `sys_admin` has no org membership by default. Use `POST /api/admin/orgs` to
> create organizations, then `POST /api/orgs/{org_id}/members` to add users.

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

### Vue / Nuxt UI

A full-featured browser UI for the platform located in the `ui/` directory.

```bash
cd ui
npm install
npm run dev
# → http://localhost:3000
```

Pages:

| Page          | Covers                                                                       |
|---------------|------------------------------------------------------------------------------|
| Orchestrators | Create (with supervisor settings), view details, settings, plugin management |
| Plugins       | List, inspect settings schema, activate versions                             |
| Settings      | LLM configurations (BYOK with model name), org settings                      |
| Admin         | Organizations, global settings, user management                              |

The supervisor orchestrator create modal supports a two-panel layout: basic fields on the left, per-node LLM config and
prompt overrides on the right. Each of the 6 supervisor nodes can override the default LLM config and system prompt
independently.

---

## Configuration

### Running Migrations

```bash
# Apply all pending migrations
make migrate

# Rollback last migration
make migrate-down

# Create a new migration
make migrate-create MSG="add new column"

# Show migration history
make migrate-history
```

### Makefile Reference

```bash
make help          # Show all available commands
make up            # Quick start: db-up + migrate + dev server
make down          # Stop databases
make dev           # Development server (auto-reload)
make start         # Production server
make test          # Run all tests
make test-cov      # Tests with HTML coverage report
make format        # Format with Black + Ruff
make lint          # Lint with Ruff
make check         # format + lint + type-check
make bootstrap     # Create initial sys_admin user and issue a JWT
make openapi       # Export OpenAPI schema to scripts/openapi_schema.json
make health        # Quick health check (curl /health)
make stats         # Pool statistics (curl /api/admin/pool/stats)
make psql          # Connect to local PostgreSQL
make mongo         # Connect to local MongoDB
make redis         # Connect to local Redis CLI
make clean         # Remove __pycache__, .pytest_cache, etc.
make db-reset-full # Full reset: wipe volumes → start → migrate
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

### 2. Create an Organization (sys_admin)

The bootstrapped `sys_admin` has no org membership. Create at least one org first:

```bash
curl -s -X POST http://localhost:8000/api/admin/orgs \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme Corporation"}' | jq .

# Example response:
# {"org_id": "<uuid>", "name": "Acme Corporation", "status": "active", "created_at": "..."}

export ORG_ID="<org_id from above>"
```

All subsequent org-scoped requests include `$ORG_ID` in the path.

### 3. List Accessible Organizations

```bash
# sys_admin: returns all orgs with role="sys_admin"
# org members: returns only their orgs with their actual role
curl -s http://localhost:8000/api/orgs \
  -H "$AUTH" | jq .

# Example response:
# [{"org_id": "<uuid>", "name": "Acme Corporation", "status": "active", "created_at": "...", "role": "sys_admin"}]
```

### 4. Add LLM Configuration

```bash
curl -X POST http://localhost:8000/api/orgs/$ORG_ID/llm-configs \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "primary",
    "provider": "openai",
    "api_key": "sk-...",
    "model_name": "gpt-4o"
  }'
```

`model_name` is optional but recommended — it is shown in the UI when selecting an LLM config for an orchestrator or
per-node override.

### 5. Create an Orchestrator Instance

```bash
# First get plugin IDs: GET /api/orgs/$ORG_ID/plugins  →  each item has an "id" (UUID)

curl -X POST http://localhost:8000/api/orgs/$ORG_ID/orchestrators \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "customer-support",
    "framework_type": "langgraph",
    "mode": "supervisor",
    "active_plugin_ids": ["<plugin-uuid-1>", "<plugin-uuid-2>"],
    "config": {
      "default_llm_config_id": 1,
      "mode_config": {
        "max_agent_hops": 10,
        "parallel_tool_calls": true,
        "invoke_timeout": 60,
        "supervisor_timeout": 60,
        "use_llm_validation": false
      }
    }
  }'
```

### 6. Send a Chat Request (SSE Streaming)

```bash
curl -X POST http://localhost:8000/api/orgs/$ORG_ID/completion/stream \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "<instance_id>",
    "message": "What is the weather in San Francisco?"
  }'
```

Response (SSE stream):

```
event: agent_start
data: {"agent": "supervisor", "timestamp": 1708234567.123}

event: tool_start
data: {"tool": "weather_plugin.get_weather", "args": {"location": "San Francisco"}}

event: tool_end
data: {"tool": "weather_plugin.get_weather", "result": "Sunny, 72°F"}

event: message
data: {"content": "The weather in San Francisco is sunny with a temperature of 72°F."}

event: agent_end
data: {"agent": "supervisor", "timestamp": 1708234568.456}
```

### 6b. Synchronous Chat

```bash
curl -X POST http://localhost:8000/api/orgs/$ORG_ID/completion/chat \
  -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "<instance_id>",
    "message": "What is the weather in San Francisco?",
    "conversation_id": "conv_abc123"
  }'
```

---

## Core Concepts

### Authentication & Sessions

Login returns a signed JWT. The JWT carries only `sub` (user_id) and `jti` (a ULID session key):

```
POST /api/auth/login  →  { "token": "<JWT>" }
```

Session data (org memberships, is_sys_admin) lives in Redis, keyed by the JWT's `jti`. This means:

- **No org/role in the token** — stale tokens can't escalate privileges
- **Instant revocation** — delete the Redis key to invalidate immediately
- **Multi-org support** — one user can belong to many orgs

```bash
# Logout (revoke current session)
DELETE /api/auth/logout

# List accessible orgs with your role in each (role-aware: sys_admin sees all)
GET /api/orgs

# List only orgs you have membership in (excludes sys_admin-only view)
GET /api/me/orgs

# Update your own password
PATCH /api/me/profile
```

### Roles

| Role        | Scope         | Can do                                               |
|-------------|---------------|------------------------------------------------------|
| `sys_admin` | Platform-wide | CRUD all orgs, create users, global settings         |
| `org_admin` | Per-org       | Manage org settings, LLM configs, add/remove members |
| `user`      | Per-org       | Access org resources, send chat requests             |

A user can be `org_admin` in one org and a regular `user` in another. `sys_admin` is a platform-level flag independent
of org membership.

### Organizations (Tenants)

Each organization is an isolated tenant with:

- Unique `org_id`
- Own LLM configurations (BYOK)
- Own plugin directory
- Own MongoDB database for conversations
- Own settings overrides

### Org Membership

Users are not tied to a single org. Membership is managed via the `user_org_memberships` table:

```bash
# sys_admin: create a user (no org)
POST /api/admin/users

# sys_admin: create user + immediately add to org
POST /api/admin/orgs/{org_id}/users

# org_admin or sys_admin: add existing user to org
POST /api/orgs/{org_id}/members  { "user_id": "...", "is_admin": false }

# Update a member's admin flag
PATCH /api/orgs/{org_id}/users/{user_id}/membership  { "is_admin": true }

# Remove member from org (hard-delete)
DELETE /api/orgs/{org_id}/users/{user_id}
```

### Orchestrator Instances

Each organization can have multiple orchestrator instances:

- Each instance has a unique `instance_id`
- Configured with `framework_type` (`langgraph`, `openai_agents`, `google_adk`) — immutable after creation
- Configured with `mode` (`supervisor`, `coordinator`, `handoff`) — immutable after creation
- Configured with active plugins
- Instance-specific settings (Tier 4)
- Independent lifecycle (create, update, delete)

### Hot-Reload

Configuration changes trigger automatic rebuilds:

```bash
# Update instance config via API
PATCH /api/orgs/{org_id}/orchestrators/{instance_id}/config

# Triggers:
# 1. Config written to orchestrator_instances
# 2. config_hash recomputed
# 3. orchestrator.reload published to RabbitMQ cadence.orchestrators exchange
# 4. Each node's consumer receives the event
# 5. Dedup: if config_hash unchanged, no-op
# 6. Orchestrator pool rebuilds instance atomically
# 7. Old instance cleanup (releases shared resources)
# 8. New instance ready for requests
```

No downtime. In-flight requests complete on old instance. New requests use new instance.

### Manual Load / Unload

```bash
# Load an instance into hot tier
POST /api/orgs/{org_id}/orchestrators/{id}/load
{"tier": "hot"}

# Unload from hot tier
POST /api/orgs/{org_id}/orchestrators/{id}/unload
```

Both are fire-and-forget (202 Accepted) — the RabbitMQ consumer handles the actual work.

---

## Orchestration Modes

### Supervisor Mode

**Architecture:** Central orchestrator with all plugin tools, structured as a 6-node workflow: Supervisor → Control
Tools → Validation → Synthesizer / Facilitator / Conversational / Error Handler.

**How it works:**

1. User message arrives at the Supervisor node
2. Supervisor LLM sees all plugin tools and decides which to call
3. Tools execute in the Control Tools node
4. Validation node checks results (optionally via LLM)
5. Synthesizer produces the final response
6. Facilitator handles unclear intent; Conversational handles context-only queries; Error Handler recovers from failures

**Best for:**

- Simple to moderately complex workflows
- Few to moderate plugins (< 15)
- Fast response time critical

**Configuration:**

```json
{
  "default_llm_config_id": 1,
  "mode_config": {
    "max_agent_hops": 10,
    "parallel_tool_calls": true,
    "invoke_timeout": 60,
    "supervisor_timeout": 60,
    "use_llm_validation": false,
    "supervisor_node": {
      "llm_config_id": null,
      "prompt_override": null
    },
    "synthesizer_node": {
      "llm_config_id": null,
      "prompt_override": null
    },
    "validation_node": {
      "llm_config_id": null,
      "prompt_override": null
    },
    "facilitator_node": {
      "llm_config_id": null,
      "prompt_override": null
    },
    "conversational_node": {
      "llm_config_id": null,
      "prompt_override": null
    },
    "error_handler_node": {
      "llm_config_id": null,
      "prompt_override": null
    }
  }
}
```

`default_llm_config_id` (required) — FK to an `OrganizationLLMConfig` in the same org. All 6 nodes use it unless
overridden.

Each node accepts:

- `llm_config_id` — override the LLM for that specific node (e.g. use a cheaper model for validation)
- `prompt_override` — replace the built-in system prompt; must contain the same `{placeholder}` slots

Retrieve default prompt templates: `GET /api/engine/supervisor/prompts`

### Coordinator Mode

**Architecture:** Central routing agent + specialized plugin agents.

**How it works:**

1. User message arrives at coordinator
2. Coordinator routes to appropriate plugin agent
3. Plugin agent executes with own tools
4. Plugin agent returns control to coordinator
5. Coordinator can route to another plugin or synthesize response

**Best for:**

- Many plugins (10+)
- Complex multi-step workflows
- Clear domain boundaries between plugins

**Configuration:**

```json
{
  "name": "my-coordinator",
  "framework_type": "langgraph",
  "mode": "coordinator",
  "active_plugin_ids": [
    "<plugin-uuid>"
  ],
  "config": {
    "max_agent_hops": 20,
    "consecutive_agent_route_limit": 5
  }
}
```

### Handoff Mode

**Architecture:** Peer-to-peer agent collaboration.

**How it works:**

1. User message arrives at entry agent
2. Entry agent processes, then transfers to peer if needed
3. Peer agent processes, can transfer to another peer
4. Final agent synthesizes response

**Best for:**

- Conversational workflows
- Sequential processing pipelines
- Explicit handoff points

**Configuration:**

```json
{
  "name": "my-handoff",
  "framework_type": "langgraph",
  "mode": "handoff",
  "active_plugin_ids": [
    "<plugin-uuid>"
  ],
  "config": {
    "entry_agent": "triage_plugin",
    "handoff_instructions": "Transfer to search_plugin for searches"
  }
}
```

---

## Backend Frameworks

### LangGraph

**Type:** State graph-based orchestration

**Pros:**

- Explicit control flow
- Built-in checkpointing
- Excellent debugging
- Cycles and conditional edges

**Use when:**

- Complex workflows with branching
- Need conversation replay/forking
- Require explicit control flow

**Models supported:** All (via LangChain wrappers)

### OpenAI Agents SDK

**Type:** Function calling agents

**Pros:**

- Native OpenAI integration
- Simple API
- Built-in streaming

**Use when:**

- Using OpenAI models
- Need simplicity
- Function calling is primary pattern

**Models supported:** OpenAI, OpenAI-compatible (Azure, vLLM, etc.)

### Google ADK

**Type:** Agent development kit

**Pros:**

- Native Gemini integration
- Session-based state management
- System prompt templating

**Use when:**

- Using Gemini models
- Need Google AI features
- Session management fits use case

**Models supported:** Gemini (all variants)

---

## Plugin Development

Plugins are developed against the [cadence-sdk](../cadence-sdk/README.md). See SDK README for complete guide.

### Installing Plugins

**System-wide (all tenants) — via API upload:**

```bash
curl -X POST http://localhost:8000/api/admin/plugins/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@my_plugin.zip"
# → writes row to system_plugins with is_latest=True
```

**Tenant-specific — via API upload:**

```bash
curl -X POST http://localhost:8000/api/orgs/$ORG_ID/plugins/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@my_plugin.zip"
# → writes row to org_plugins scoped to your org
```

Both endpoints extract metadata from the zip's `plugin.py`, upload to S3/MinIO, and write to the DB catalog. The
`is_latest` flag is flipped atomically for the same `pid`.

### Plugin Catalog

- `system_plugins`: Available to all tenants. Managed by sys_admin.
- `org_plugins`: Private to a single org. Managed by org_admin.
- `GET /api/orgs/{org_id}/plugins` returns both, combined in one list with `source: "system"` or `source: "org"`.
- Each row includes `default_settings` (key→default_value) extracted at upload time.

### Version Pinning

The `active_plugin_ids` field accepts plugin UUIDs from the catalog. Because each version is a separate row with its own
UUID, passing a specific version's UUID pins that version. The `is_latest` flag on the catalog row indicates the most
recent upload.

```bash
# List all versions of a plugin — each has a unique "id"
GET /api/orgs/{org_id}/plugins

# Pass the UUID of the exact version you want
{
  "active_plugin_ids": [
    "<uuid-of-search-plugin-latest>",
    "<uuid-of-math-plugin-v1.2.3>"
  ]
}
```

---

## Multi-Tier Pool

### Overview

The orchestrator pool manages instances across three tiers:

- **Cold Tier**: Minimal metadata (~100 bytes/instance)
- **Warm Tier**: Config cached in memory (~1-5 KB/instance)
- **Hot Tier**: Fully built orchestrators (~5-50 MB/instance)

### Tier Transitions

```
Cold ──────────> Warm ──────────> Hot
     (on boot)          (on request)

Hot ───────────> Warm ──────────> Cold
    (LRU evict)        (TTL expire)
```

### Configuration

```python
# Global settings (Tier 2)
{
    "max_hot_pool_size": 200,  # Max instances in Hot tier
    "prewarm_strategy": "recent",  # "recent", "all", or "none"
    "prewarm_count": 100,  # How many to prewarm
    "warm_tier_ttl": 3600,  # Warm → Cold after 1 hour
}
```

### Shared Resources

To optimize memory, instances share:

1. **Models**: Same (provider, model_name, api_key) → shared instance
2. **Plugin bundles**: Same (plugin, version, settings) for stateless plugins
3. **Graph templates**: Same (framework, mode, plugins) for LangGraph

Reference counting ensures resources are released when no instances use them.

### Monitoring

```bash
GET /api/admin/pool/stats

# Response:
{
  "cold_count": 500,
  "warm_count": 300,
  "hot_count": 200,
  "shared_models": 15,
  "shared_bundles": 42,
  "estimated_memory_mb": 1024
}
```

---

## Deployment

### Docker

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry install --no-dev

# Copy application
COPY . .

# Run migrations and start
CMD ["sh", "-c", "poetry run alembic upgrade head && poetry run uvicorn cadence.main:app --host 0.0.0.0 --port 8000"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  cadence:
    build: .
    ports:
      - "8000:8000"
    environment:
      CADENCE_POSTGRES_URL: postgresql+asyncpg://cadence:pass@postgres/cadence
      CADENCE_MONGO_URL: mongodb://mongo:27017
      CADENCE_REDIS_URL: redis://redis:6379
    depends_on:
      - postgres
      - mongo
      - redis
    volumes:
      - ./tenant_plugins:/var/cadence/tenant_plugins

  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: cadence
      POSTGRES_USER: cadence
      POSTGRES_PASSWORD: pass
    volumes:
      - postgres_data:/var/lib/postgresql/data

  mongo:
    image: mongo:7
    volumes:
      - mongo_data:/data/db

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  mongo_data:
  redis_data:
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cadence
spec:
  replicas: 3
  selector:
    matchLabels:
      app: cadence
  template:
    metadata:
      labels:
        app: cadence
    spec:
      containers:
        - name: cadence
          image: cadence:latest
          ports:
            - containerPort: 8000
          env:
            - name: CADENCE_POSTGRES_URL
              valueFrom:
                secretKeyRef:
                  name: cadence-secrets
                  key: postgres-url
            - name: CADENCE_MONGO_URL
              valueFrom:
                secretKeyRef:
                  name: cadence-secrets
                  key: mongo-url
            - name: CADENCE_REDIS_URL
              valueFrom:
                secretKeyRef:
                  name: cadence-secrets
                  key: redis-url
          volumeMounts:
            - name: tenant-plugins
              mountPath: /var/cadence/tenant_plugins
      volumes:
        - name: tenant-plugins
          persistentVolumeClaim:
            claimName: tenant-plugins-pvc
```

### High Availability

For production, deploy multiple replicas with:

1. **Shared storage**: S3 or MinIO for plugin zip packages (`CADENCE_PLUGIN_S3_ENABLED=true`)
2. **RabbitMQ cluster**: Orchestrator load/reload events across nodes — each node gets its own queue, hash-based dedup
   prevents redundant rebuilds
3. **Load balancer**: Distribute traffic (sticky sessions for SSE)
4. **PostgreSQL replica**: Read replicas for heavy reads
5. **MongoDB replica set**: High availability for conversation storage

---

## Performance

### Optimization Tips

1. **Prewarm frequently used instances**: Set `prewarm_strategy: "recent"`
2. **Use stateless plugins**: Enables bundle sharing across instances
3. **Reuse LLM configs**: Same API key → shared model instances
4. **Enable semantic cache**: Reduces redundant LLM calls
5. **Tune pool sizes**: Balance memory vs build latency

---

## Monitoring & Observability

### Health Checks

```bash
# Basic health
GET /health

# Detailed health (all orchestrators)
GET /api/admin/health

# Pool statistics
GET /api/admin/pool/stats
```

### Logging

Structured JSON logs (configurable via `CADENCE_LOG_FORMAT`):

```json
{
  "timestamp": "2026-02-18T00:00:00Z",
  "level": "INFO",
  "message": "Orchestrator instance created",
  "org_id": "acme-corp",
  "instance_id": "customer-support-123",
  "mode": "supervisor",
  "framework_type": "langgraph"
}
```

### Metrics (Extensible)

Integration points for Prometheus:

- Request counts by tenant
- Response times (p50, p95, p99)
- Pool tier distribution
- Shared resource utilization
- Error rates by orchestrator

---

## Troubleshooting

### Common Issues

**Issue:** Orchestrator build fails with "Plugin not found"

```bash
# Check plugin discovery
GET /api/orgs/{org_id}/plugins

# Verify plugin structure
python -c "from cadence_sdk import validate_plugin_structure; validate_plugin_structure(MyPlugin)"
```

**Issue:** "No LLM config found" error

```bash
# List tenant's LLM configs
GET /api/orgs/{org_id}/llm-configs

# Add config
POST /api/orgs/{org_id}/llm-configs
```

**Issue:** 401 Unauthorized after login

```bash
# Token session may have expired — log in again
POST /api/auth/login

# Or check Redis is running (sessions stored there)
make redis
```

**Issue:** Hot-reload not triggering

```bash
# Check RabbitMQ management UI
open http://localhost:15672  # cadence / cadence_dev_password

# Verify exchange cadence.orchestrators exists and has bindings

# Manually trigger reload via config update
PATCH /api/orgs/{org_id}/orchestrators/{id}/config

# Or fire-and-forget load event
POST /api/orgs/{org_id}/orchestrators/{id}/load
```

**Issue:** High memory usage

```bash
# Check pool stats
GET /api/admin/pool/stats

# Reduce hot pool size
PATCH /api/admin/settings/max_hot_pool_size
```

---

## Security Best Practices

1. **Never commit API keys**: Use environment variables or encrypted storage
2. **Rotate JWT secrets**: Change `CADENCE_SECRET_KEY` regularly
3. **Session TTL**: Configure `CADENCE_ACCESS_TOKEN_EXPIRE_MINUTES` appropriately for your security policy
4. **Use HTTPS**: Deploy behind reverse proxy (nginx, Caddy)
5. **Enable rate limiting**: Configure per-tenant limits
6. **Audit logs**: Enable detailed logging for production
7. **Network isolation**: PostgreSQL/MongoDB/Redis not exposed publicly
8. **Principle of least privilege**: Grant minimal permissions to database users

---

## Contributing

Contributions are welcome! Please:

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
- [FastAPI](https://fastapi.tiangolo.com/)
- [Pydantic](https://docs.pydantic.dev/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [Redis](https://redis.io/)
- [PostgreSQL](https://www.postgresql.org/)
- [MongoDB](https://www.mongodb.com/)

---

**Cadence AI Framework** - Production-ready multi-tenant AI orchestration at scale.
