# Frontend Overview

The Cadence frontend is a Nuxt 4 application written in TypeScript. It uses Vue 3 with the Composition API throughout,
Nuxt UI for components, and Tailwind CSS 4 for styling.

## Tech Stack

| Layer              | Technology                            |
|--------------------|---------------------------------------|
| Framework          | Nuxt 4 (Vue 3, Composition API)       |
| Language           | TypeScript                            |
| Component library  | Nuxt UI (built on Radix Vue)          |
| Styling            | Tailwind CSS 4                        |
| Markdown rendering | `@nuxtjs/mdc` (MDC component)         |
| Graph rendering    | Mermaid (dynamically imported)        |
| Validation         | Zod (via `@nuxt/ui` form integration) |

The UI colour theme is defined in `ui/app/app.config.ts:1` — primary `amber`, neutral `stone`.

## Directory Structure

```
ui/app/
├── app.vue                  # Root component — sets <head>, wraps NuxtLayout / NuxtPage
├── app.config.ts            # UI theme tokens
├── layouts/
│   ├── default.vue          # Authenticated shell: collapsible sidebar + slot
│   └── auth.vue             # Centred card layout for login / org-select
├── pages/
│   ├── login.vue
│   ├── org-select.vue
│   ├── dashboard/
│   ├── chat.vue
│   ├── orchestrators/
│   │   ├── index.vue
│   │   └── [id].vue
│   ├── settings/
│   │   └── llm-configs.vue
│   └── admin/
│       ├── orgs/
│       ├── users/
│       ├── pool/
│       ├── health/
│       └── settings/
├── composables/
│   ├── useAuth.ts
│   ├── useChat.ts
│   └── useOrchestrators.ts
├── components/
│   ├── orchestrators/
│   └── settings/
└── middleware/
    └── auth.global.ts
```

## Application Shell

`ui/app/app.vue` is minimal — it sets document metadata via `useHead` / `useSeoMeta` and renders
`<UApp><NuxtLayout><NuxtPage /></NuxtLayout></UApp>`. The loading indicator is provided by `<NuxtLoadingIndicator />` at
`app.vue:31`.

The **default layout** (`ui/app/layouts/default.vue`) wraps every authenticated page with a `UDashboardGroup` containing
a collapsible, resizable `UDashboardSidebar`. Navigation links are assembled at runtime from three computed arrays:

- `baseLinks` — Dashboard, Chat, Orchestrators (visible when `auth.currentOrgId` is set)
- `orgAdminLinks` — Plugins, Settings sub-tree (visible when `auth.isOrgAdmin`)
- `systemLinks` — System sub-tree (visible when `auth.isSysAdmin`)

See `ui/app/layouts/default.vue:13–130`.

## Auth Cookie and SSR-Safe State

Authentication state is held in Nuxt's `useState` composable, which is SSR-safe and shared between server and client
renders. The three keys are:

| Key                 | Type                  | Description                                           |
|---------------------|-----------------------|-------------------------------------------------------|
| `auth:user`         | `AuthUser \| null`    | Populated after a successful login or session restore |
| `auth:orgs`         | `OrgAccessResponse[]` | Org list for the current user                         |
| `auth:is_sys_admin` | `boolean`             | Elevated privilege flag                               |

The active organisation is stored as a **cookie** (`cadence-org-id`) rather than in `useState`, so the server can read
it on SSR without a client round-trip. Cookie access uses `useCookie` from Nuxt, which is also SSR-safe. See
`ui/app/composables/useAuth.ts:15`.

The JWT itself is handled entirely server-side: the API proxy sets an `HttpOnly` cookie on login (`/api/auth/login`).
The frontend never reads the raw token — it only sees the sentinel value `[set]` that confirms the cookie was written (
`useAuth.ts:32`).

## Sub-pages in this Section

- [Auth Flow](auth.md) — login form, route guard, org selection, session restore
- [Chat Interface & SSE](chat.md) — orchestrator selection, message streaming, SSE parsing
- [Orchestrator Management](orchestrators.md) — CRUD table, detail page, plugin settings, graph rendering
- [Admin Panel](admin.md) — orgs, users, pool stats, health check, global settings, LLM configs
