# Global Orchestrator Settings Tab Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a "Orchestrators" tab to `/settings` where org admins configure default LLM settings (llm_config_id, model_name, max_tokens, timeout) inherited by all orchestrator instances in their org, with per-instance config still overriding.

**Architecture:** Org defaults stored as a single JSON blob in `organization_settings` table under key `"orchestrator_defaults"` (no migration needed). When any instance's `resolved_config` is assembled, org defaults are merged first so instance config wins. Two new REST endpoints expose GET/PUT for the defaults. A new frontend page at `/settings/orchestrators` provides the form UI.

**Tech Stack:** FastAPI + Pydantic (backend), SQLAlchemy async + PostgreSQL JSONB (storage), Nuxt 3 + Vue 3 + Nuxt UI (frontend), pytest-asyncio (tests).

---

## Task 1: Pydantic Schemas

**Files:**
- Modify: `src/cadence/controller/schemas/tenant_schemas.py`

**Step 1: Add the two new models at the bottom of the file**

```python
class OrchestratorDefaultsRequest(BaseModel):
    """PUT body for org-level orchestrator defaults."""

    default_llm_config_id: Optional[int] = None
    default_model_name: Optional[str] = None
    default_max_tokens: Optional[int] = None
    default_timeout: Optional[int] = None


class OrchestratorDefaultsResponse(BaseModel):
    """GET/PUT response for org-level orchestrator defaults."""

    default_llm_config_id: Optional[int] = None
    default_model_name: Optional[str] = None
    default_max_tokens: Optional[int] = None
    default_timeout: Optional[int] = None
```

**Step 2: Verify import (Optional is already imported at line 3)**

Confirm `from typing import Any, Dict, List, Optional` is present — it is, no change needed.

**Step 3: Run existing schema tests**

```bash
cd /Volumes/WS/Projects/Personal/cadence
python -m pytest tests/unit/ -k "tenant" -v 2>&1 | tail -20
```

Expected: all existing tests pass (or no tests match — that is also fine).

**Step 4: Commit**

```bash
git add src/cadence/controller/schemas/tenant_schemas.py
git commit -m "feat: add OrchestratorDefaultsRequest/Response schemas"
```

---

## Task 2: Backend API Endpoints

**Files:**
- Modify: `src/cadence/controller/organization_controller.py`

**Step 1: Add import for the two new schemas**

In the existing import block at the top, extend the import from `tenant_schemas`:

```python
from cadence.controller.schemas.tenant_schemas import (
    CreateOrganizationRequest,
    OrganizationResponse,
    OrgWithRoleResponse,
    OrchestratorDefaultsRequest,       # NEW
    OrchestratorDefaultsResponse,      # NEW
    SetTenantSettingRequest,
    TenantSettingResponse,
)
```

**Step 2: Add module-level constant after the `logger` line**

```python
_ORCHESTRATOR_DEFAULTS_KEY = "orchestrator_defaults"
```

**Step 3: Add GET endpoint — append after `list_tenant_settings`**

```python
@router.get(
    "/api/orgs/{org_id}/orchestrator-defaults",
    response_model=OrchestratorDefaultsResponse,
)
async def get_orchestrator_defaults(
    org_id: str,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Get org-level orchestrator defaults."""
    tenant_service = request.app.state.tenant_service
    try:
        raw = await tenant_service.get_setting(org_id, _ORCHESTRATOR_DEFAULTS_KEY)
        if not isinstance(raw, dict):
            return OrchestratorDefaultsResponse()
        return OrchestratorDefaultsResponse(
            **{k: raw.get(k) for k in OrchestratorDefaultsResponse.model_fields}
        )
    except Exception as e:
        logger.error(f"Failed to get orchestrator defaults: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get orchestrator defaults",
        )
```

**Step 4: Add PUT endpoint — append after GET endpoint**

```python
@router.put(
    "/api/orgs/{org_id}/orchestrator-defaults",
    response_model=OrchestratorDefaultsResponse,
)
async def set_orchestrator_defaults(
    org_id: str,
    body: OrchestratorDefaultsRequest,
    request: Request,
    context: TenantContext = Depends(require_org_admin_access),
):
    """Upsert org-level orchestrator defaults."""
    tenant_service = request.app.state.tenant_service
    try:
        payload = body.model_dump()
        await tenant_service.set_setting(
            org_id=org_id,
            key=_ORCHESTRATOR_DEFAULTS_KEY,
            value=payload,
            caller_id=context.user_id,
            overridable=True,
        )
        event_publisher = getattr(request.app.state, "event_publisher", None)
        if event_publisher is not None:
            try:
                await event_publisher.publish_org_settings_changed(org_id=org_id)
            except Exception as pub_err:
                logger.warning(
                    f"Failed to publish org settings changed event: {pub_err}"
                )
        return OrchestratorDefaultsResponse(**payload)
    except Exception as e:
        logger.error(f"Failed to set orchestrator defaults: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set orchestrator defaults",
        )
```

**Step 5: Smoke-test the import chain**

```bash
cd /Volumes/WS/Projects/Personal/cadence
python -c "from cadence.controller.organization_controller import router; print('OK')"
```

Expected: `OK`

**Step 6: Commit**

```bash
git add src/cadence/controller/organization_controller.py
git commit -m "feat: add GET/PUT /api/orgs/{org_id}/orchestrator-defaults endpoints"
```

---

## Task 3: orchestrator_events.py — Helper + Handler Updates

**Files:**
- Modify: `src/cadence/infrastructure/messaging/orchestrator_events.py`

**Step 1: Add `_fetch_org_defaults` helper after the `_parse_plugin_ref` function at the bottom**

```python
async def _fetch_org_defaults(org_settings_repo, org_id: str) -> dict:
    """Fetch orchestrator defaults for an org from the org_settings_repo.

    Returns empty dict if repo is None or key not set.
    """
    if not org_settings_repo:
        return {}
    setting = await org_settings_repo.get_by_key(org_id, "orchestrator_defaults")
    if setting and isinstance(setting.value, dict):
        return setting.value
    return {}
```

**Step 2: Update `OrchestratorEventConsumer.__init__` to accept `org_settings_repo`**

Current signature (line 133):
```python
def __init__(
    self,
    client: RabbitMQClient,
    pool: OrchestratorPool,
    instance_repo: OrchestratorInstanceRepository,
    plugin_store: PluginStoreRepository,
):
```

Replace with:
```python
def __init__(
    self,
    client: RabbitMQClient,
    pool: OrchestratorPool,
    instance_repo: OrchestratorInstanceRepository,
    plugin_store: PluginStoreRepository,
    org_settings_repo=None,
):
```

And add `self.org_settings_repo = org_settings_repo` in the `__init__` body after `self.plugin_store = plugin_store`.

**Step 3: Update `_dispatch` to pass `self.org_settings_repo` to all four handler calls**

Replace the four handler dispatches (lines 188–214):

```python
if routing_key == _RK_LOAD:
    await _handle_load(
        event,
        self.pool,
        self.instance_repo,
        self.plugin_store,
        self.org_settings_repo,        # NEW
    )
elif routing_key == _RK_RELOAD:
    await _handle_reload(
        event,
        self.pool,
        self.instance_repo,
        self.org_settings_repo,        # NEW
    )
elif routing_key == _RK_UNLOAD:
    await _handle_unload(event, self.pool)
elif routing_key == _RK_SETTINGS_GLOBAL_CHANGED:
    await _handle_global_settings_changed(
        event,
        self.pool,
        self.instance_repo,
        self.org_settings_repo,        # NEW
    )
elif routing_key == _RK_SETTINGS_ORG_CHANGED:
    await _handle_org_settings_changed(
        event,
        self.pool,
        self.instance_repo,
        self.org_settings_repo,        # NEW
    )
```

**Step 4: Update `_handle_load` signature and resolved_config assembly**

Add `org_settings_repo=None` parameter. Replace line 274:
```python
# before:
resolved_config = {**instance_config, "org_id": instance["org_id"]}

# after:
org_defaults = await _fetch_org_defaults(org_settings_repo, instance["org_id"])
resolved_config = {**org_defaults, **instance_config, "org_id": instance["org_id"]}
```

**Step 5: Update `_handle_reload` signature and resolved_config assembly**

Add `org_settings_repo=None` parameter. Replace line 341:
```python
# before:
resolved_config = {**instance_config, "org_id": instance["org_id"]}

# after:
org_defaults = await _fetch_org_defaults(org_settings_repo, instance["org_id"])
resolved_config = {**org_defaults, **instance_config, "org_id": instance["org_id"]}
```

**Step 6: Update `_handle_global_settings_changed` — cache by org_id to avoid redundant DB queries**

Add `org_settings_repo=None` parameter. Replace the `resolved_config` line inside the loop (line 393):

```python
# Add cache before the loop:
_org_defaults_cache: dict[str, dict] = {}

for instance_id in hot_instance_ids:
    try:
        instance = await instance_repo.get_by_id(instance_id)
        if not instance:
            continue

        oid = instance["org_id"]
        if oid not in _org_defaults_cache:
            _org_defaults_cache[oid] = await _fetch_org_defaults(org_settings_repo, oid)

        resolved_config = {
            **_org_defaults_cache[oid],
            **instance["config"],
            "org_id": oid,
        }

        await pool.reload_instance(...)
```

**Step 7: Update `_handle_org_settings_changed` — fetch once before the loop**

Add `org_settings_repo=None` parameter. Add one fetch before the loop, then use it inside:

```python
# Fetch org defaults once (org_id known from event payload):
org_defaults = await _fetch_org_defaults(org_settings_repo, org_id)

for instance_id in hot_instance_ids:
    try:
        instance = await instance_repo.get_by_id(instance_id)
        if not instance or instance.get("org_id") != org_id:
            continue

        resolved_config = {**org_defaults, **instance["config"], "org_id": instance["org_id"]}

        await pool.reload_instance(...)
```

**Step 8: Smoke-test import**

```bash
python -c "from cadence.infrastructure.messaging.orchestrator_events import OrchestratorEventConsumer, _fetch_org_defaults; print('OK')"
```

Expected: `OK`

**Step 9: Commit**

```bash
git add src/cadence/infrastructure/messaging/orchestrator_events.py
git commit -m "feat: inject org defaults into resolved_config in all event handlers"
```

---

## Task 4: pool.py — `_load_from_db`

**Files:**
- Modify: `src/cadence/engine/pool.py`

**Step 1: Add the inline helper at the top of the file (after imports)**

Do NOT import from `orchestrator_events` — that would create a circular dependency.
Instead, duplicate the 6-line helper inline at module level in `pool.py`:

```python
async def _fetch_org_defaults(org_settings_repo, org_id: str) -> dict:
    """Fetch orchestrator_defaults blob for an org. Returns {} if unavailable."""
    if not org_settings_repo:
        return {}
    setting = await org_settings_repo.get_by_key(org_id, "orchestrator_defaults")
    if setting and isinstance(setting.value, dict):
        return setting.value
    return {}
```

Place it right before `class OrchestratorPool`.

**Step 2: Update `_load_from_db` — replace line 104**

```python
# before (line 104):
resolved_config = {**instance_config, "org_id": instance["org_id"]}

# after:
org_settings_repo = self.db_repositories.get("org_settings_repo")
org_defaults = await _fetch_org_defaults(org_settings_repo, instance["org_id"])
resolved_config = {**org_defaults, **instance_config, "org_id": instance["org_id"]}
```

**Step 3: Smoke-test**

```bash
python -c "from cadence.engine.pool import OrchestratorPool; print('OK')"
```

Expected: `OK`

**Step 4: Commit**

```bash
git add src/cadence/engine/pool.py
git commit -m "feat: merge org defaults into resolved_config in pool._load_from_db"
```

---

## Task 5: settings_service.py — `update_instance_config`

**Files:**
- Modify: `src/cadence/service/settings_service.py`

**Step 1: Update `update_instance_config` — replace the resolved_config line (~line 353)**

```python
# before:
resolved_config = {**instance["config"], "org_id": instance["org_id"]}

# after:
org_defaults_setting = await self.org_settings_repo.get_by_key(
    instance["org_id"], "orchestrator_defaults"
)
org_defaults = {}
if org_defaults_setting and isinstance(org_defaults_setting.value, dict):
    org_defaults = org_defaults_setting.value
resolved_config = {**org_defaults, **instance["config"], "org_id": instance["org_id"]}
```

`self.org_settings_repo` is already set in `__init__` — no constructor change needed.

**Step 2: Smoke-test**

```bash
python -c "from cadence.service.settings_service import SettingsService; print('OK')"
```

Expected: `OK`

**Step 3: Run existing service tests**

```bash
python -m pytest tests/unit/test_orchestrator_service.py -v 2>&1 | tail -20
```

Expected: all pass.

**Step 4: Commit**

```bash
git add src/cadence/service/settings_service.py
git commit -m "feat: merge org defaults into resolved_config in update_instance_config"
```

---

## Task 6: main.py — Wire `org_settings_repo`

**Files:**
- Modify: `src/cadence/main.py`

**Step 1: Update `OrchestratorPool` constructor (~line 390)**

```python
orchestrator_pool = OrchestratorPool(
    factory=orchestrator_factory,
    db_repositories={
        "orchestrator_instance_repo": repositories["instance_repo"],
        "org_settings_repo": repositories["org_settings_repo"],   # NEW
    },
)
```

**Step 2: Update `OrchestratorEventConsumer` constructor (~line 406)**

```python
event_consumer = OrchestratorEventConsumer(
    client=rabbitmq_client,
    pool=orchestrator_pool,
    instance_repo=repositories["instance_repo"],
    plugin_store=plugin_store,
    org_settings_repo=repositories["org_settings_repo"],   # NEW
)
```

**Step 3: Update `load_hot_tier_instances` function signature (~line 249)**

```python
async def load_hot_tier_instances(
    orchestrator_pool: OrchestratorPool,
    instance_repo: OrchestratorInstanceRepository,
    plugin_store: Optional[PluginStoreRepository],
    org_settings_repo=None,   # NEW
) -> int:
```

**Step 4: Update `load_hot_tier_instances` body — replace the resolved_config line (~line 293)**

```python
# Existing:
instance_config = {
    **instance["config"],
    "plugin_settings": instance.get("plugin_settings", {}),
}
# NEW: merge org defaults
org_defaults = {}
if org_settings_repo:
    setting = await org_settings_repo.get_by_key(
        instance["org_id"], "orchestrator_defaults"
    )
    if setting and isinstance(setting.value, dict):
        org_defaults = setting.value
resolved_config = {**org_defaults, **instance_config, "org_id": instance["org_id"]}
```

**Step 5: Update the `load_hot_tier_instances` call site (~line 422)**

```python
await load_hot_tier_instances(
    orchestrator_pool,
    repositories["instance_repo"],
    plugin_store,
    repositories["org_settings_repo"],   # NEW
)
```

**Step 6: Smoke-test**

```bash
python -c "from cadence.main import load_hot_tier_instances; print('OK')"
```

Expected: `OK`

**Step 7: Run all unit tests**

```bash
python -m pytest tests/unit/ -v 2>&1 | tail -30
```

Expected: all pass.

**Step 8: Commit**

```bash
git add src/cadence/main.py
git commit -m "feat: wire org_settings_repo to pool, consumer, and hot-tier loader"
```

---

## Task 7: TypeScript Type

**Files:**
- Modify: `ui/app/types/api.ts`

**Step 1: Append at the end of the file**

```typescript
export interface OrchestratorDefaultsResponse {
  default_llm_config_id: number | null
  default_model_name: string | null
  default_max_tokens: number | null
  default_timeout: number | null
}
```

**Step 2: Commit**

```bash
git add ui/app/types/api.ts
git commit -m "feat: add OrchestratorDefaultsResponse TypeScript type"
```

---

## Task 8: Settings Nav Tab

**Files:**
- Modify: `ui/app/pages/settings.vue`

**Step 1: Add the "Orchestrators" nav item to `links` array (after LLM Configs)**

```typescript
const links = [
  [
    {
      label: 'General',
      icon: 'i-lucide-user',
      to: '/settings',
      exact: true
    },
    {
      label: 'Members',
      icon: 'i-lucide-users',
      to: '/settings/members'
    },
    {
      label: 'LLM Configs',
      icon: 'i-lucide-key',
      to: '/settings/llm-configs'
    },
    {
      label: 'Orchestrators',
      icon: 'i-lucide-cpu',
      to: '/settings/orchestrators'
    }
  ]
] satisfies NavigationMenuItem[][]
```

**Step 2: Commit**

```bash
git add ui/app/pages/settings.vue
git commit -m "feat: add Orchestrators nav tab to settings layout"
```

---

## Task 9: Orchestrators Settings Page

**Files:**
- Create: `ui/app/pages/settings/orchestrators.vue`

**Step 1: Create the file with full content**

```vue
<script lang="ts" setup>
import type {LLMConfigResponse, OrchestratorDefaultsResponse} from '~/types'

const auth = useAuth()
const toast = useToast()
const orgId = computed(() => auth.currentOrgId.value || '')

// Load org's LLM configs for the dropdown
const {data: llmConfigs} = await useFetch<LLMConfigResponse[]>(
  () => `/api/orgs/${orgId.value}/llm-configs`,
  {watch: [orgId]}
)

const llmConfigOptions = computed(() => [
  {label: 'None (use instance setting)', value: null},
  ...(llmConfigs.value || []).map(c => ({
    label: `${c.name} (${c.provider})`,
    value: Number(c.id)
  }))
])

// Form state
const form = reactive({
  default_llm_config_id: null as number | null,
  default_model_name: null as string | null,
  default_max_tokens: null as number | null,
  default_timeout: null as number | null,
})

// Load saved defaults
const {data: defaults, refresh} = await useFetch<OrchestratorDefaultsResponse>(
  () => `/api/orgs/${orgId.value}/orchestrator-defaults`,
  {watch: [orgId]}
)

watch(defaults, (val) => {
  if (val) {
    form.default_llm_config_id = val.default_llm_config_id
    form.default_model_name = val.default_model_name ?? null
    form.default_max_tokens = val.default_max_tokens
    form.default_timeout = val.default_timeout
  }
}, {immediate: true})

const saving = ref(false)

async function save() {
  saving.value = true
  try {
    await $fetch(`/api/orgs/${orgId.value}/orchestrator-defaults`, {
      method: 'PUT',
      body: {
        default_llm_config_id: form.default_llm_config_id || null,
        default_model_name: form.default_model_name || null,
        default_max_tokens: form.default_max_tokens || null,
        default_timeout: form.default_timeout || null,
      },
    })
    await refresh()
    toast.add({title: 'Orchestrator defaults saved', icon: 'i-lucide-check', color: 'success'})
  } catch {
    toast.add({title: 'Failed to save orchestrator defaults', color: 'error'})
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="flex flex-col gap-6">
    <UPageCard
      title="Global Orchestrator Settings"
      description="Default values inherited by all orchestrator instances in this organization. Each instance can override these in its own configuration."
      variant="naked"
      orientation="horizontal"
    />

    <UCard>
      <div class="flex flex-col gap-5">
        <UFormField
          label="Default LLM Config"
          description="Fallback LLM configuration used when an instance has no explicit llm_config_id."
        >
          <USelect
            v-model="form.default_llm_config_id"
            :items="llmConfigOptions"
            value-key="value"
            label-key="label"
            class="w-full"
          />
        </UFormField>

        <UFormField
          label="Default Model Name"
          description="Model identifier sent to the provider (e.g. gpt-4o, claude-3-5-sonnet-20241022)."
        >
          <UInput
            v-model="form.default_model_name"
            placeholder="e.g. gpt-4o"
            class="w-full"
          />
        </UFormField>

        <UFormField
          label="Default Max Tokens"
          description="Maximum tokens per LLM response. Leave blank to use the provider default."
        >
          <UInput
            v-model.number="form.default_max_tokens"
            type="number"
            placeholder="e.g. 4096"
            :min="1"
            class="w-full"
          />
        </UFormField>

        <UFormField
          label="Default Node Execution Timeout (seconds)"
          description="Per-node timeout in seconds. Overridden by instance-level or per-node timeout settings."
        >
          <UInput
            v-model.number="form.default_timeout"
            type="number"
            placeholder="e.g. 60"
            :min="1"
            class="w-full"
          />
        </UFormField>

        <div class="flex justify-end pt-2">
          <UButton
            :loading="saving"
            icon="i-lucide-save"
            label="Save Defaults"
            @click="save"
          />
        </div>
      </div>
    </UCard>
  </div>
</template>
```

**Step 2: Commit**

```bash
git add ui/app/pages/settings/orchestrators.vue
git commit -m "feat: add Global Orchestrator Settings page at /settings/orchestrators"
```

---

## Verification

**Run backend unit tests:**
```bash
cd /Volumes/WS/Projects/Personal/cadence
python -m pytest tests/unit/ -v 2>&1 | tail -30
```
Expected: all pass.

**Smoke-test the full import chain:**
```bash
python -c "
from cadence.controller.organization_controller import router
from cadence.infrastructure.messaging.orchestrator_events import OrchestratorEventConsumer, _fetch_org_defaults
from cadence.engine.pool import OrchestratorPool
from cadence.service.settings_service import SettingsService
print('All imports OK')
"
```
Expected: `All imports OK`

**Manual API test (with server running):**
```bash
# PUT defaults
curl -X PUT http://localhost:8000/api/orgs/{org_id}/orchestrator-defaults \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"default_model_name": "gpt-4o", "default_max_tokens": 4096, "default_timeout": 60}'

# GET defaults back
curl http://localhost:8000/api/orgs/{org_id}/orchestrator-defaults \
  -H "Authorization: Bearer {token}"
```
Expected: PUT returns saved values; GET returns same values.

**Check merge priority:**
Create an instance with `"default_model_name": "claude-3-5-sonnet-20241022"` in its config, with org default set to `"gpt-4o"`. The instance should use `claude-3-5-sonnet-20241022`.

**UI:**
Navigate to `/settings/orchestrators` — form should load, values should persist after save, toast appears on success.