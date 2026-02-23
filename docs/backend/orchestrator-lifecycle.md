# Orchestrator Lifecycle

An orchestrator instance is a fully-built, in-memory AI agent graph scoped to one org. Its lifecycle — create, load,
reload, unload — is event-driven via RabbitMQ so that changes propagate to every horizontally-scaled node without
restart.

## Framework × Mode Matrix

`OrchestratorFactory` (`src/cadence/engine/factory.py`) maintains a registry keyed by `(framework_type, mode)`. All
combinations defined in `_BACKEND_CONFIGS` (`factory.py`):

| Framework       | Modes                                                                          |
|-----------------|--------------------------------------------------------------------------------|
| `langgraph`     | supervisor, coordinator, handoff, pipeline, reflection, ensemble, hierarchical |
| `openai_agents` | supervisor, coordinator, handoff, pipeline, reflection, ensemble, hierarchical |
| `google_adk`    | supervisor, coordinator, handoff, pipeline, reflection, ensemble, hierarchical |

> **Active modes** are further constrained by `FRAMEWORK_SUPPORTED_MODES` (`src/cadence/constants/framework.py`):
> `langgraph` and `google_adk` currently expose only `supervisor`; `openai_agents` has no active modes.
> The factory registry still contains skeleton entries for all combinations listed above.

Each entry maps to three classes: an **adapter**, an **orchestrator**, and a **streaming wrapper**. For example
`("langgraph", "supervisor")` maps to `LangChainAdapter`, `LangGraphSupervisor`, `LangGraphStreamingWrapper`.

`framework_type` and `mode` are immutable after instance creation — the `SettingsService` enforces this.

## CRUD Endpoints

**Prefix:** `POST/GET/PATCH/DELETE /api/orgs/{org_id}/orchestrators`
**Controller:** `src/cadence/controller/orchestrator_crud_controller.py`
**Auth:** `require_org_admin_access`

| Method   | Path                    | Action                                                         |
|----------|-------------------------|----------------------------------------------------------------|
| `POST`   | `/`                     | Create instance record in DB, then publish `orchestrator.load` |
| `GET`    | `/`                     | List all instances for org                                     |
| `GET`    | `/{instance_id}`        | Get instance config                                            |
| `PATCH`  | `/{instance_id}`        | Update name, tier, default LLM config                          |
| `PATCH`  | `/{instance_id}/config` | Update config JSONB (triggers reload via RabbitMQ)             |
| `PATCH`  | `/{instance_id}/status` | Set `active` or `suspended`                                    |
| `DELETE` | `/{instance_id}`        | Soft-delete (sets `status=is_deleted`)                         |
| `GET`    | `/{instance_id}/graph`  | Mermaid graph definition (if supported)                        |

## Lifecycle Endpoints

**Controller:** `src/cadence/controller/orchestrator_lifecycle_controller.py`

| Method | Path                    | Action                                             |
|--------|-------------------------|----------------------------------------------------|
| `POST` | `/{instance_id}/load`   | Publish `orchestrator.load` event (202 Accepted)   |
| `POST` | `/{instance_id}/unload` | Publish `orchestrator.unload` event (202 Accepted) |

Both endpoints are fire-and-forget — they return as soon as the RabbitMQ message is published.

## RabbitMQ Event System

**Exchange:** `cadence.orchestrators` (topic, durable)
**Source:** `src/cadence/infrastructure/messaging/orchestrator_events.py`

### Routing Keys

| Routing key               | Publisher method                                   | Consumer handler                  |
|---------------------------|----------------------------------------------------|-----------------------------------|
| `orchestrator.load`       | `publish_load(instance_id, org_id, tier)`          | `_handle_load`                    |
| `orchestrator.reload`     | `publish_reload(instance_id, org_id, config_hash)` | `_handle_reload`                  |
| `orchestrator.unload`     | `publish_unload(instance_id)`                      | `_handle_unload`                  |
| `settings.global_changed` | `publish_global_settings_changed()`                | `_handle_global_settings_changed` |
| `settings.org_changed`    | `publish_org_settings_changed(org_id)`             | `_handle_org_settings_changed`    |

### Per-node Queue

Each node subscribes to its own durable queue named `cadence.orchestrators.<hostname>`. The queue is bound to
`orchestrator.*` and `settings.*` patterns. This ensures every node receives every lifecycle event — not just one.

```python
node_name = socket.gethostname()
queue_name = _make_per_node_queue_name(node_name)  # "cadence.orchestrators.<host>"
await queue.bind(exchange, routing_key="orchestrator.*")
await queue.bind(exchange, routing_key="settings.*")
```

(`orchestrator_events.py`)

## Event Handlers

### `_handle_load`

```
1. Dedup check: if pool already has instance with matching config_hash, skip
2. Fetch instance config from DB
3. plugin_store.ensure_local() for each active_plugins ref
4. If instance already in hot_tier → pool.reload_instance(...)
   Else → pool.create_instance(...)
5. pool.set_hash(instance_id, config_hash)
```

### `_handle_reload`

Only acts if the instance is already in the hot tier. Compares incoming `config_hash` against stored hash — skips if
unchanged (dedup). Fetches fresh config from DB then calls `pool.reload_instance`.

### `_handle_unload`

```python
if instance_id in pool.hot_tier:
    await pool.remove_instance(instance_id)
```

### `_handle_global_settings_changed`

Iterates all hot-tier instances and calls `pool.reload_instance` on each, fetching fresh config from DB. This propagates
changes to `global_settings` across the entire pool without a restart.

## OrchestratorPool

```python
class OrchestratorPool:
    """Simple orchestrator pool for MVP.

    Manages multiple orchestrator instances with hot-reload support.
    All instances kept in Hot tier (fully built and ready).

    Attributes:
        factory: Orchestrator factory for creating instances
        db_repositories: Database repositories for loading instance config
        instances: Dict mapping instance_id to orchestrator
        locks: Per-instance locks for concurrency safety
    """

    def __init__(
            self,
            factory: OrchestratorFactory,
            db_repositories: dict[str, Any],
    ):
        self.factory = factory
        self.db_repositories = db_repositories
        self.instances: dict[str, BaseOrchestrator] = {}
        self.locks: dict[str, asyncio.Lock] = {}
        self._hashes: dict[str, str] = {}
```

Key methods:

| Method                 | Description                                    |
|------------------------|------------------------------------------------|
| `get(instance_id)`     | Return cached instance or load from DB         |
| `create_instance(...)` | Factory.create → store in `instances`          |
| `reload_instance(...)` | Atomic swap: build new → cleanup old → replace |
| `remove_instance(...)` | cleanup + delete from `instances`              |
| `cleanup_all()`        | Called at shutdown                             |

`reload_instance` acquires the per-instance lock, builds the new orchestrator, calls
`old_orchestrator.cleanup()`, then atomically replaces the reference. In-flight requests that already hold a reference
to the old object will complete normally.

```python
async def reload_instance(self, instance_id, org_id, framework_type, mode,
                          instance_config, resolved_config) -> None:
    """Hot-reload orchestrator instance with new configuration.

    Atomic swap procedure:
    1. Acquire lock for instance
    2. Build new orchestrator with updated config
    3. Cleanup old orchestrator
    4. Replace in registry atomically
    5. Release lock
    """
    if instance_id not in self.instances:
        raise ValueError(f"Instance '{instance_id}' not found")

    self._ensure_lock(instance_id)

    async with self.locks[instance_id]:
        old_orchestrator = self.instances[instance_id]

        try:
            new_orchestrator = await self.factory.create(
                framework_type=framework_type,
                mode=mode,
                org_id=org_id,
                instance_config=instance_config,
                resolved_config=resolved_config,
            )

            await old_orchestrator.cleanup()

            self.instances[instance_id] = new_orchestrator

        except Exception as e:
            logger.error(f"Failed to reload instance {instance_id}: {e}", exc_info=True)
            raise
```

The `hot_tier` property is an alias for `self.instances` — all instances are hot in the MVP:

## Factory Creation Pipeline

```
OrchestratorFactory.create(framework_type, mode, org_id, instance_config, resolved_config)
  1. registry_key = (framework_type, mode)
  2. adapter = adapter_class()
  3. plugin_manager = SDKPluginManager(adapter, llm_factory, org_id, ...)
  4. await plugin_manager.load_plugins(active_plugins, instance_config)
  5. streaming_wrapper = streaming_wrapper_class()
  6. orchestrator = orchestrator_class(plugin_manager, llm_factory, resolved_config, adapter, streaming_wrapper)
  7. await orchestrator.initialize()
  8. return orchestrator
```

`resolved_config` is the 3-tier merged config dict. `instance_config` is the raw instance JSONB. Both are passed to the
orchestrator constructor so it can access both the resolved defaults and the raw instance overrides.

## Pool Tier Constants (`src/cadence/engine/constants.py`)

```python
HOT_TIER = "hot"
WARM_TIER = "warm"  # defined, not yet implemented
COLD_TIER = "cold"  # defined, not yet implemented

DEFAULT_MAX_HOT_POOL_SIZE = 200
DEFAULT_WARM_TIER_TTL = 3600
DEFAULT_MAX_AGENT_HOPS = 15
DEFAULT_CONSECUTIVE_ROUTE_LIMIT = 3
DEFAULT_INVOKE_TIMEOUT = 120
DEFAULT_MAX_HANDOFFS = 10
```

All instances are currently hot-tier.

```python
@property
def hot_tier(self) -> dict[str, BaseOrchestrator]:
    """Alias for instances dict (all instances are hot-tier in MVP)."""
    return self.instances
```

## Supervisor Mode Configuration

When `mode="supervisor"`, the instance `config` JSONB is validated against `BaseSupervisorSettings` (
`src/cadence/engine/impl/langgraph/supervisor/settings.py`). `SupervisorMode` (
`src/cadence/engine/modes/supervisor/__init__.py`)
strips `None` values from the config before merging with defaults, so storing `null` for any field is safe.

### `BaseSupervisorSettings` Fields

| Field                         | Type   | Default | Description                                                         |
|-------------------------------|--------|---------|---------------------------------------------------------------------|
| `max_agent_hops`              | `int`  | `10`    | Max planner iterations before routing to synthesizer                |
| `enabled_parallel_tool_calls` | `bool` | `True`  | Allow parallel tool execution in a single planner step              |
| `node_execution_timeout`      | `int`  | `60`    | Default timeout in seconds for all node LLM/tool calls              |
| `enabled_llm_validation`      | `bool` | `False` | Add a validator node that reviews tool results before synthesizing  |
| `message_context_window`      | `int`  | `5`     | Last N messages passed to the router/planner                        |
| `max_context_window`          | `int`  | `16000` | Estimated token budget — triggers compaction or error when exceeded |
| `enabled_auto_compact`        | `bool` | `False` | Compact conversation history when either context limit is exceeded  |
| `autocompact`                 | node   | `{}`    | `SupervisorModeNodeConfig` for the summarization LLM                |

Each of the following keys accepts a `SupervisorModeNodeConfig` object (all fields optional):

`classifier_node`, `planner_node`, `synthesizer_node`, `validation_node`, `clarifier_node`, `responder_node`,
`error_handler_node`

### `SupervisorModeNodeConfig` Fields

| Field           | Type            | Description                                                                         |
|-----------------|-----------------|-------------------------------------------------------------------------------------|
| `llm_config_id` | `int \| null`   | Override LLM config for this node (falls back to `default_llm_config_id`)           |
| `model_name`    | `str \| null`   | Override model name                                                                 |
| `prompt`        | `str \| null`   | Replace the node's default prompt template (must preserve `{placeholder}` slots)    |
| `temperature`   | `float \| null` | Override temperature for this node (0.0–2.0)                                        |
| `max_tokens`    | `int \| null`   | Override max output tokens for this node                                            |
| `timeout`       | `int \| null`   | Per-node timeout in seconds (overrides `node_execution_timeout` for this node only) |

Answer nodes (`synthesizer`, `clarifier`, `responder`, `error_handler`) default to `node_execution_timeout × 2` when
no per-node `timeout` is set.

### Context Limit Enforcement

Both limits are checked in `OrchestratorService._prepare_context` **before** passing state to the orchestrator:

| Condition                               | `enabled_auto_compact=True`                           | `enabled_auto_compact=False` |
|-----------------------------------------|-------------------------------------------------------|------------------------------|
| `token_count > max_context_window`      | `compact_history` → `compact_conversation` → continue | `RuntimeError`               |
| `len(history) > message_context_window` | `compact_history` → `compact_conversation` → continue | `RuntimeError`               |

`compact_history` calls the `autocompact` node LLM with a summarization prompt and returns a summary string.
`compact_conversation` (`ConversationService`) marks all existing messages as `is_compacted=True` in MongoDB and inserts
2 synthetic replacement messages. See [Chat and Streaming](chat.md#autocompaction) for the full persistence details.
