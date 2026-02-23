# Backend Overview

Cadence Multi-agents AI Framework is a multi-tenant AI agent orchestration platform built on **FastAPI**. Each HTTP
request runs in its own
async event loop task; long-running orchestration is handled by a pool of pre-built orchestrator objects kept in memory.

## Tech Stack

| Layer            | Technology           | Role                                                          |
|------------------|----------------------|---------------------------------------------------------------|
| API              | FastAPI (Python)     | HTTP + SSE endpoints                                          |
| Relational       | PostgreSQL (asyncpg) | Orgs, users, instances, settings, LLM configs, plugin catalog |
| Document         | MongoDB              | Conversation message history                                  |
| Cache / Sessions | Redis                | JWT session store, rate-limit counters, general cache         |
| Messaging        | RabbitMQ (aio-pika)  | Orchestrator lifecycle events broadcast across nodes          |
| Object storage   | S3 / MinIO           | Plugin zip source-of-truth                                    |
| Local filesystem | Host disk            | Extracted plugin cache (`/var/lib/cadence/plugins/`)          |

## Source Tree

```
src/cadence/
├── config/          AppSettings (env-var loaded infra config)
├── constants/       Shared constants and type aliases
├── controller/      FastAPI routers (HTTP boundary)
├── engine/          Orchestrator pool, factory, framework implementations
│   ├── base/        Abstract orchestrator and adapter interfaces
│   ├── impl/        Framework-specific implementations
│   │   ├── langgraph/
│   │   ├── google_adk/
│   │   └── openai_agents/
│   ├── modes/       Orchestration mode base classes
│   └── shared_resources/  Bundle cache, model pool, template cache
├── infrastructure/  External system clients and adapters
│   ├── llm/         LLM provider factory
│   ├── messaging/   RabbitMQ client and event publisher/consumer
│   ├── persistence/ PostgreSQL, MongoDB, Redis, S3 clients
│   ├── plugins/     Plugin loader, bundle builder, settings resolver
│   └── streaming/   StreamEvent (SSE format)
├── middleware/      TenantContextMiddleware, authorization dependencies, rate limiting
├── repository/      Data access objects (one per domain entity)
├── service/         Business logic layer
└── main.py          Application entry point and lifespan manager
```

## Key Architectural Decisions

**Multi-tenant isolation.** Every org-scoped endpoint carries `org_id` as a path parameter. The authorization middleware
verifies that the JWT session has the required membership in that org before any service code runs. LLM API keys (BYOK)
are stored per-org and are never accessible to `sys_admin` users through normal endpoints.

**3-tier settings cascade.** Operational defaults (LLM parameters, pool sizes, feature flags) live in the PostgreSQL
`global_settings` table and are managed via `PATCH /api/admin/settings`. An org can override any global key in
`organization_settings`. A specific orchestrator instance carries its own inline `config` JSONB. Resolution order:
instance config wins over org settings, which win over global settings. `AppSettings` is *not* part of this cascade — it
holds immutable infrastructure config loaded once from environment variables at startup.

**LRU orchestrator pool.** All active instances are kept fully-built in memory (hot tier). The `OrchestratorPool` holds
a `dict[instance_id, BaseOrchestrator]` plus a per-instance `asyncio.Lock` for safe concurrent access. On a cache miss
the pool falls back to the database. Future tiers (warm/cold) are defined as constants but not yet implemented.

**RabbitMQ for broadcast.** When a node creates or changes an orchestrator instance it publishes a lifecycle event to a
topic exchange (`cadence.orchestrators`). Every running node subscribes to its own per-hostname queue bound to
`orchestrator.*` and `settings.*`. This allows zero-downtime hot-reload across horizontally-scaled deployments.

## Section Pages

- [Application Startup](startup.md)
- [Authentication and Sessions](auth.md)
- [Chat and Streaming (SSE)](chat.md)
- [Orchestrator Lifecycle](orchestrator-lifecycle.md)
- [Plugin System](plugins.md)
- [Configuration Cascade](configuration.md)
- [Tenant and Admin Management](admin.md)
