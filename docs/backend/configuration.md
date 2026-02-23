# Configuration Cascade

Cadence separates **infrastructure config** (loaded once from environment variables) from **operational settings** (
stored in PostgreSQL and runtime-mutable). Only the latter participates in the 3-tier cascade.

## Two Configuration Layers

```
AppSettings (env vars)          — immutable, loaded at module import
    ↓ read once at startup
3-tier settings cascade         — mutable, stored in PostgreSQL
    global_settings  (Tier 1: platform-wide defaults)
    organization_settings  (Tier 2: org overrides)
    orchestrator instance config  (Tier 3: instance overrides)
```

## AppSettings (`src/cadence/config/app_settings.py`)

`AppSettings` is a `pydantic_settings.BaseSettings` subclass with the `CADENCE_` prefix. It is instantiated once at
module level (`main.py`) and never written to at runtime.

Key fields:

| Field                         | Env var                               | Default                            | Notes                          |
|-------------------------------|---------------------------------------|------------------------------------|--------------------------------|
| `api_host`                    | `CADENCE_API_HOST`                    | `0.0.0.0`                          |                                |
| `api_port`                    | `CADENCE_API_PORT`                    | `8000`                             |                                |
| `postgres_url`                | `CADENCE_POSTGRES_URL`                | `postgresql+asyncpg://...`         |                                |
| `redis_url`                   | `CADENCE_REDIS_URL`                   | `redis://localhost:6379`           |                                |
| `redis_default_db`            | `CADENCE_REDIS_DEFAULT_DB`            | `0`                                | Sessions and cache             |
| `redis_ratelimit_db`          | `CADENCE_REDIS_RATELIMIT_DB`          | `1`                                | Rate-limit counters            |
| `rabbitmq_url`                | `CADENCE_RABBITMQ_URL`                | `amqp://cadence:...@localhost/`    |                                |
| `mongo_url`                   | `CADENCE_MONGO_URL`                   | `mongodb://localhost:27017`        |                                |
| `secret_key`                  | `CADENCE_SECRET_KEY`                  | dev placeholder                    | Must be changed in production  |
| `jwt_algorithm`               | `CADENCE_JWT_ALGORITHM`               | `HS256`                            |                                |
| `access_token_expire_minutes` | `CADENCE_ACCESS_TOKEN_EXPIRE_MINUTES` | `180`                              |                                |
| `storage_root`                | `CADENCE_STORAGE_ROOT`                | `/var/lib/cadence/storage`         |                                |
| `system_plugins_dir`          | `CADENCE_SYSTEM_PLUGINS_DIR`          | `/var/lib/cadence/plugins/system`  |                                |
| `tenant_plugins_root`         | `CADENCE_TENANT_PLUGINS_ROOT`         | `/var/lib/cadence/plugins/tenants` |                                |
| `plugin_s3_enabled`           | `CADENCE_PLUGIN_S3_ENABLED`           | `true`                             |                                |
| `s3_endpoint_url`             | `CADENCE_S3_ENDPOINT_URL`             | `None`                             | `None` = AWS S3; set for MinIO |
| `s3_bucket_name`              | `CADENCE_S3_BUCKET_NAME`              | `cadence-plugins`                  |                                |
| `cors_origins`                | `CADENCE_CORS_ORIGINS`                | `["http://localhost:3000", ...]`   |                                |

`AppSettings.validate_production_config()` returns a list of validation errors when checked
against production requirements (changed secret key, no localhost URLs, etc.):

```python
def validate_production_config(self) -> list[str]:
    """Validate configuration for production deployment.

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    if self.secret_key == DEV_SECRET_KEY_PLACEHOLDER:
        errors.append("SECRET_KEY must be changed in production")

    if self.debug:
        errors.append("DEBUG should be False in production")

    if LOCALHOST in self.postgres_url:
        errors.append("PostgreSQL URL should not use localhost in production")

    if LOCALHOST in self.redis_url:
        errors.append("Redis URL should not use localhost in production")

    if LOCALHOST in self.mongo_url:
        errors.append("MongoDB URL should not use localhost in production")

    return errors
```

`get_settings()` returns the singleton instance, creating it on first call:

```python
_app_settings: Optional[AppSettings] = None


def get_settings() -> AppSettings:
    """Get singleton instance of static settings.

    Settings are loaded once and cached for application lifetime.

    Returns:
        AppSettings instance
    """
    global _app_settings

    if _app_settings is None:
        _app_settings = AppSettings()

    return _app_settings
```

## 3-Tier Settings Cascade

```mermaid
flowchart LR
    G[global_settings\nPostgreSQL\nTier 1] -->|overridable=True| O[organization_settings\nPostgreSQL\nTier 2]
    O -->|overridable=True| I[instance config JSONB\nPostgreSQL\nTier 3]
    I --> R[resolved_config\npassed to Orchestrator]
```

**Resolution order (highest wins):** instance config > org settings > global settings — but only when each tier
explicitly permits it via `overridable=True`. When `overridable=False` at any tier, that tier's value is final and
lower tiers are silently skipped.

`SettingsService` (`src/cadence/service/settings_service.py`) provides the CRUD methods for Tiers 1 and 2. Tier 3 (
instance config) is managed via the orchestrator CRUD endpoints.

### Tier 1: Global Settings

Stored in `global_settings` table. Managed by `sys_admin` only.

```
GET  /api/admin/settings          → list all
PATCH /api/admin/settings/{key}   → update value + overridable flag
```

(`src/cadence/controller/admin_controller.py`)

Each row has an `overridable: bool` column (default `False`). When `overridable=False`, no org or instance can
override this key — the global value always wins at resolution time. When `overridable=True`, org-level settings for
this key become effective.

`SettingsService` methods: `get_global_setting(key)`, `set_global_setting(key, value, overridable)`,
`list_global_settings()`, `update_global_setting(key, value, overridable)`, `delete_global_setting(key)`.

### Tier 2: Organization Settings

Stored in `organization_settings` table. Managed by `org_admin`.

```
POST /api/orgs/{org_id}/settings        → create or update (includes overridable flag)
GET  /api/orgs/{org_id}/settings        → list all for org
```

(`src/cadence/controller/organization_controller.py`)

Each row has an `overridable: bool` column (default `False`). When `overridable=False`, instance config cannot
override this key. When `overridable=True`, the instance `config` JSONB value for this key takes precedence.

Write operations are always accepted and stored regardless of whether the parent tier permits overriding. Scope
enforcement happens only at resolution time via `resolve_effective_setting`.

`SettingsService` methods: `get_tenant_setting(org_id, key)`, `set_tenant_setting(org_id, key, value)`,
`list_tenant_settings(org_id)`, `delete_tenant_setting(org_id, key)`.

### Tier 3: Instance Config

Each `orchestrator_instances` row has a `config` JSONB column. This is the instance-level override. `framework_type` and
`mode` are stored as separate columns and are immutable.

```
PATCH /api/orgs/{org_id}/orchestrators/{instance_id}/config
```

When instance config changes, `settings_service.update_orchestrator_config` publishes an `orchestrator.reload` event so
the running orchestrator picks up the new values without restart.

## Settings → RabbitMQ Broadcasts

Two events propagate settings changes to all running nodes:

| Event                     | Trigger                            | Handler                                                                  |
|---------------------------|------------------------------------|--------------------------------------------------------------------------|
| `settings.global_changed` | `PATCH /api/admin/settings/{key}`  | `_handle_global_settings_changed` — reloads all hot-tier instances       |
| `settings.org_changed`    | `POST /api/orgs/{org_id}/settings` | `_handle_org_settings_changed` — reloads hot-tier instances for that org |

```python
await event_publisher.publish_global_settings_changed()
await event_publisher.publish_org_settings_changed(org_id=org_id)
```

Both handlers live in `orchestrator_events.py`. The global handler reloads every hot-tier instance; the org handler
filters to instances whose `org_id` matches the event payload. This ensures a setting change propagates to all
affected orchestrators on all nodes without a restart.

## SettingsService Constructor

```python
SettingsService(
    global_settings_repo: GlobalSettingsRepository,  # Tier 1 CRUD
org_settings_repo: OrganizationSettingsRepository,  # Tier 2 CRUD
instance_repo: OrchestratorInstanceRepository,  # Tier 3 CRUD + reload trigger
pool: OrchestratorPool | None = None,  # optional for in-process reloads
)
```

`SettingsService` extends `OrchestratorConfigMixin` which contributes the orchestrator CRUD methods (
`create_orchestrator_instance`, `update_orchestrator_config`, etc.).

## Cascade Resolution

`SettingsService.resolve_effective_setting(key, org_id, instance_config=None)` applies the full cascade with scope
enforcement:

```python
# Early-return cascade — flat logic, no nesting
global_setting = await self.global_settings_repo.get_by_key(key)
if global_setting is None:
    return None  # key unknown at platform level

if not global_setting.overridable:
    return global_setting.value  # global locked → always wins

org_setting = await self.org_settings_repo.get_by_key(org_id, key)
if org_setting is None:
    return global_setting.value  # org never set this key → use global

if not org_setting.overridable or instance_config is None:
    return org_setting.value  # org locked or no instance config → org wins

return instance_config.get(key, org_setting.value)  # instance wins (fallback: org)
```

| Scenario                                           | Result                                |
|----------------------------------------------------|---------------------------------------|
| Key not in `global_settings`                       | `None`                                |
| `global.overridable=False`                         | `global.value` (org/instance ignored) |
| `global.overridable=True`, no org row              | `global.value`                        |
| `global.overridable=True`, `org.overridable=False` | `org.value`                           |
| Both overridable, `instance_config` is `None`      | `org.value`                           |
| Both overridable, instance has the key             | `instance_config[key]`                |
| Both overridable, instance lacks the key           | `org.value`                           |

## Resolution at Runtime

`resolved_config` is assembled in the event consumer (`orchestrator_events.py`) and in the pool:

```python
instance_config = {
    **instance["config"],
    "plugin_settings": instance.get("plugin_settings", {}),
}
resolved_config = {**instance_config, "org_id": instance["org_id"]}
```

The `resolved_config` dict is passed to the orchestrator constructor. Per-key scope enforcement (global/org
`overridable` flags) is applied by `resolve_effective_setting` when individual keys are looked up, not at this
assembly step.
