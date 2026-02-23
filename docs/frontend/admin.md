# Admin Panel

The admin panel is restricted to system administrators. It covers organisation management, user management, pool
statistics, system health, global settings, and LLM configuration (BYOK). All admin routes live under `/admin/*`.

## Route Guard

`ui/app/middleware/auth.global.ts` checks `auth.isSysAdmin.value` for any path starting with `/admin`. Non-admins are
redirected to `/dashboard` via `handleAdminRoute()` (`auth.global.ts:28–30`). The sidebar in `default.vue` conditionally
renders the System nav
group only when `auth.isSysAdmin` is true (`layouts/default.vue:74–75`).

## Organisations — `ui/app/pages/admin/orgs/index.vue`

Data is loaded with `useFetch<OrganizationResponse[]>('/api/admin/orgs')` at page load (`admin/orgs/index.vue:11`).

The `UTable` shows: Name, ID, Status badge, Created date, and an action column with a detail link to
`/admin/orgs/{org_id}`.

**Creating an org**: clicking "Create Org" opens a `UModal` containing a Zod-validated form (
`schema: z.object({ name: z.string().min(1) })`). On submit, `onCreate()` calls `POST /api/admin/orgs` and then
refreshes both the org table and the sidebar's own org list via `auth.loadOrgs()` in parallel (
`admin/orgs/index.vue:24`).

## Users — `ui/app/pages/admin/users/index.vue`

Data is loaded with `useFetch<UserMembershipResponse[]>('/api/admin/users')` (`admin/users/index.vue:9`).

The `UTable` shows: Username, Email, Role badge (`sys_admin` or `user`), Created date, and Edit/Delete actions.

Three modals are managed:

### Create User

Zod schema:

```ts
z.object({
    username: z.string().min(1),
    email: z.string().email().optional().or(z.literal('')),
    password: z.string().min(6).optional().or(z.literal(''))
})
```

Password is optional — the user can set it later. Calls `POST /api/admin/users`.

### Edit User

Schema includes `is_sys_admin: z.boolean()`, allowing the sys admin flag to be toggled. Calls
`PATCH /api/admin/users/{user_id}`. The edit modal opens via `openEdit(user)` which pre-populates `editState` from the
row data.

### Delete User

Confirmation modal with a warning that all org memberships will be removed. Calls `DELETE /api/admin/users/{user_id}`.

## Pool Statistics — `ui/app/pages/admin/pool/index.vue`

Fetches `GET /api/admin/pool/stats` via `useFetch` and then **auto-refreshes on a timer**:

```ts
// admin/pool/index.vue:15-21
onMounted(() => {
    timer.value = setInterval(() => refresh(), POOL_STATS_REFRESH_MS)
})
onUnmounted(() => {
    if (timer.value) clearInterval(timer.value)
})
```

`POOL_STATS_REFRESH_MS` is imported from `~/utils` and the page template notes it as "every 30 seconds" (
`admin/pool/index.vue:107`). A manual **Refresh** button is also available.

Stat cards displayed:

| Metric          | Icon                                    |
|-----------------|-----------------------------------------|
| Total Instances | `i-lucide-cpu`                          |
| Hot Tier        | `i-lucide-flame` (error colour)         |
| Warm Tier       | `i-lucide-thermometer` (warning colour) |
| Cold Tier       | `i-lucide-snowflake` (info colour)      |
| Shared Models   | `i-lucide-share-2`                      |
| Shared Bundles  | `i-lucide-package`                      |

A separate card shows `memory_estimate_mb` from `PoolStatsResponse`, formatted to one decimal place.

## Health — `ui/app/pages/admin/health/index.vue`

Loads two independent endpoints in parallel via `useFetch`:

- `GET /api/system-health` → `HealthResponse` — overall platform status
- `GET /api/admin/health` → `HealthCheckResponse[]` — per-instance readiness

**System status card**: shows overall `status` (`healthy` / other) with a check or X icon, then iterates over
`HEALTH_SERVICE_LABELS` (imported from `~/constants`) to display each service connection status as `connected` or an
error state. If `systemHealth.error` is set it is shown in an error-coloured paragraph.

**Orchestrator instance health table**: columns are Instance ID (monospace), Framework, Mode, Ready (green `ready` / red
`not ready` badge), Plugin Count. The table is populated from `instanceHealth`.

## Global Settings — `ui/app/pages/admin/settings/index.vue`

Fetches `GET /api/admin/settings` which returns a flat `GlobalSettingResponse[]`. Settings are grouped by
`SETTINGS_GROUPS` (a `Record<string, string[]>` from `~/constants`) that maps label strings to arrays of setting keys.
Any settings not matched by a named group fall into an "Other" category (`admin/settings/index.vue:52–53`).

Each setting renders as an inline edit row showing:

- Human-readable description
- Key name in monospace
- Value type badge
- A text input bound to `editValues[key]`
- A per-key **Save** button with its own `saving[key]` loading state

`saveSetting(key)` calls `PATCH /api/admin/settings/{key}` with `{ value: editValues[key] }` and refreshes the full
settings list on success (`admin/settings/index.vue:23–37`).

## LLM Configurations (BYOK) — `ui/app/pages/settings/llm-configs.vue`

This page lives under `/settings/llm-configs` (accessible to org admins via the sidebar's Settings > LLM Configs link)
rather than under `/admin`. It manages per-organisation BYOK LLM provider credentials.

Data is fetched with `useFetch` reactive on `orgId`:

```ts
// settings/llm-configs.vue:15-18
const {data: configs, refresh} = await useFetch<LLMConfigResponse[]>(
    () => `/api/orgs/${orgId.value}/llm-configs`,
    {watch: [orgId]}
)
```

The `UTable` shows: Name, Provider (via `providerLabel()`), Base URL, Created date, Edit and Delete actions.

**Delete** handles a `409 Conflict` response specifically to show a user-friendly message when the config is still
referenced by active orchestrators (`settings/llm-configs.vue:27–45`).

### LLMConfigModal — `ui/app/components/settings/LLMConfigModal.vue`

Used for both **create** and **edit** modes, distinguished by the presence of the `initialValue` prop.

The Zod schema is computed to adjust required fields by mode (`LLMConfigModal.vue:19–27`):

- `api_key` is required on create, optional on edit (leave blank to keep the existing key).
- `provider` is included in the schema only on create (provider cannot be changed after creation).

Provider is selected from `LLM_PROVIDERS` imported from `~/utils` (`LLMConfigModal.vue:4`).

Azure OpenAI requires an additional `api_version` field (e.g. `2024-02-01`), surfaced when `isAzure` is true (
`LLMConfigModal.vue:17`). On create the value is sent as `additional_config: { api_version }`.

API calls:

- Create: `POST /api/orgs/{orgId}/llm-configs`
- Edit: `PATCH /api/orgs/{orgId}/llm-configs/{name}` (uses the original config name from `initialValue`)

`onSubmit` delegates to `submitEdit(data)` for edit mode or `submitCreate(data)` for create mode, each building the
appropriate request body.

The `base_url` field is optional and noted as required for LiteLLM deployments.

## Related Pages

- [Frontend Overview](index.md)
- [Auth Flow](auth.md) — sys admin route guard details
- [Orchestrator Management](orchestrators.md) — LLM configs are consumed in `LangGraphSupervisorSettings`
