# Clean Code Guidelines — Nuxt UI / Vue Project

## Table of Contents

1. [Uncle Bob's Clean Code Principles](#uncle-bobs-clean-code-principles)
2. [Naming Conventions](#naming-conventions)
3. [Component Design](#component-design)
4. [Composables](#composables)
5. [TypeScript](#typescript)
6. [Nuxt UI Usage](#nuxt-ui-usage)
7. [State Management](#state-management)
8. [API & Data Fetching](#api--data-fetching)
9. [Performance](#performance)
10. [Testing](#testing)
11. [Git & Code Review](#git--code-review)

---

## Uncle Bob's Clean Code Principles

These principles from Robert C. Martin's *Clean Code* are applied throughout this project. They are not suggestions —
they are the baseline standard.

### Meaningful Names

Names should reveal intent. If a name requires a comment to explain it, rename it.

```ts
// ❌ Bad
const d = ref(0)
const lst = ref<any[]>([])
function calc(x: number, y: number) { return x * y }

// ✅ Good
const elapsedDays = ref(0)
const activeUsers = ref<User[]>([])
function calculateTotalPrice(quantity: number, unitPrice: number) {
  return quantity * unitPrice
}
```

Avoid encodings (`strName`, `iCount`), noise words (`data`, `info`, `manager`), and abbreviations that don't have a
universal meaning in the domain.

### Functions Do One Thing

> "Functions should do one thing. They should do it well. They should do it only."

A function that fetches data, transforms it, and updates the UI is three functions. Keep them separate.

```ts
// ❌ Bad — fetches, maps, and filters in one function
async function loadUserDropdown() {
  const res = await $fetch('/api/users')
  return res.filter(u => u.active).map(u => ({ label: u.name, value: u.id }))
}

// ✅ Good — each function has one job
const toDropdownOption = (user: User) => ({ label: user.name, value: user.id })
const isActive = (user: User) => user.active

async function fetchUsers(): Promise<User[]> {
  return $fetch('/api/users')
}

async function loadActiveUserOptions() {
  const users = await fetchUsers()
  return users.filter(isActive).map(toDropdownOption)
}
```

### Small Functions, Low Indentation

Functions should be short — ideally under 20 lines. Deeply nested logic is a sign the function is doing too much.
Extract guard clauses and inner logic into named functions.

```ts
// ❌ Bad — deep nesting, hard to follow
function processOrder(order: Order) {
  if (order) {
    if (order.items.length > 0) {
      if (order.status === 'pending') {
        // ... actual logic buried here
      }
    }
  }
}

// ✅ Good — early returns flatten the logic
function processOrder(order: Order) {
  if (!order) return
  if (order.items.length === 0) return
  if (order.status !== 'pending') return

  // actual logic at top level
}
```

### Function Arguments

Aim for 0–2 arguments. Three is acceptable. More than three is a smell — group them into an object.

```ts
// ❌ Bad
function createUser(name: string, email: string, role: string, teamId: string, sendWelcome: boolean) {}

// ✅ Good
interface CreateUserParams {
  name: string
  email: string
  role: UserRole
  teamId: string
  sendWelcomeEmail: boolean
}

function createUser(params: CreateUserParams) {}
```

### Don't Repeat Yourself (DRY)

Every piece of knowledge must have a single, authoritative representation. Duplication is the root of maintenance
problems.

```ts
// ❌ Bad — same formatting logic copy-pasted across 3 components
const formatted = `${user.firstName} ${user.lastName}`.trim()

// ✅ Good — single source of truth
// utils/formatters.ts
export const fullName = (user: Pick<User, 'firstName' | 'lastName'>) =>
  `${user.firstName} ${user.lastName}`.trim()
```

### No Comments Inside Functions — Code Must Explain Itself

**No inline comments inside function or method bodies.** If a block of code needs a comment to be understood, extract it
into a named function. The name *is* the comment.

```ts
// ❌ Bad — inline comments signal the code isn't self-explanatory
async function submitOrder(order: Order) {
  // validate the order first
  if (!order.items.length) return
  // calculate totals
  const total = order.items.reduce((sum, i) => sum + i.price * i.quantity, 0)
  // send to API
  await $fetch('/api/orders', { method: 'POST', body: { ...order, total } })
  // notify the user
  toast.add({ title: 'Order placed!' })
}

// ✅ Good — extracted names make comments unnecessary
async function submitOrder(order: Order) {
  if (!isValidOrder(order)) return
  const total = calculateOrderTotal(order.items)
  await placeOrder({ ...order, total })
  notifyOrderSuccess()
}

const isValidOrder = (order: Order) => order.items.length > 0
const calculateOrderTotal = (items: OrderItem[]) =>
  items.reduce((sum, item) => sum + item.price * item.quantity, 0)
const placeOrder = (order: Order) =>
  $fetch('/api/orders', { method: 'POST', body: order })
const notifyOrderSuccess = () =>
  toast.add({ title: 'Order placed!' })
```

The only acceptable comments are at the top level of a file — to explain *why* a non-obvious architectural or external
constraint exists, never *what* the code does.

```ts
// ✅ Acceptable — explains a constraint that can't be inferred from the code
// Polling every 3s instead of WebSocket — the current hosting plan doesn't support WS
const POLL_INTERVAL_MS = 3000
```

Never commit commented-out code. Use git history instead.

### Don't Return Null, Don't Pass Null

Returning `null` forces every caller to check for it, spreading defensive code throughout the codebase. Return empty
arrays, `Option` types, or throw intentional errors instead.

```ts
// ❌ Bad
function findUser(id: string): User | null {
  return users.find(u => u.id === id) ?? null
}

// ✅ Good — throw a domain error or return a typed result
function findUserOrThrow(id: string): User {
  const user = users.find(u => u.id === id)
  if (!user) throw new Error(`User not found: ${id}`)
  return user
}
```

### The Boy Scout Rule

> "Leave the code cleaner than you found it."

Every PR should include at least one small improvement to the surrounding code — a rename, an extracted function, a
removed comment — beyond the task at hand. Incremental improvement is how codebases stay healthy.

### SOLID in Vue/Nuxt Context

| Principle                 | Application                                                                         |
|---------------------------|-------------------------------------------------------------------------------------|
| **Single Responsibility** | One component = one concern. One composable = one behavior. One store = one domain. |
| **Open/Closed**           | Extend components via slots and props, not by modifying internals.                  |
| **Liskov Substitution**   | Components accepting a `user` prop should work with any valid `User` shape.         |
| **Interface Segregation** | Don't pass a full `User` object when only `{ id, name }` is needed. Use `Pick<>`.   |
| **Dependency Inversion**  | Components depend on composable interfaces, not on fetch implementation details.    |

---

## Naming Conventions

| Entity               | Convention                            | Example                              |
|----------------------|---------------------------------------|--------------------------------------|
| Components           | PascalCase                            | `UserProfileCard.vue`                |
| Pages                | kebab-case                            | `user-settings.vue`                  |
| Composables          | camelCase with `use` prefix           | `useAuthUser.ts`                     |
| Pinia stores         | camelCase with `use` + `Store` suffix | `useCartStore.ts`                    |
| Utilities            | camelCase                             | `formatCurrency.ts`                  |
| Types/Interfaces     | PascalCase                            | `UserProfile`, `ApiResponse<T>`      |
| Constants            | SCREAMING_SNAKE_CASE                  | `MAX_RETRY_COUNT`                    |
| CSS classes (custom) | kebab-case                            | `.user-card--active`                 |
| Events (emits)       | kebab-case                            | `update:modelValue`, `item-selected` |

**Component naming:**

- Always multi-word to avoid conflicts with HTML elements. `UserCard` not `Card`.
- Prefix base/generic components consistently: `Base`, `App`, or `The` for singletons.
  ```
  BaseButton.vue     # reusable primitive
  AppHeader.vue      # used once per layout
  TheNavbar.vue      # layout singleton
  ```

---

## Component Design

### Single Responsibility

Each component does one thing. If a component needs a long comment to explain what it does, split it.

```vue
<!-- ❌ Bad: One component doing too much -->
<script setup lang="ts">
const { data: user } = await useFetch('/api/user')
const { data: orders } = await useFetch('/api/orders')
// + form logic + modal logic + table logic
</script>

<!-- ✅ Good: Delegated to focused sub-components -->
<template>
  <UserProfileHeader :user="user" />
  <UserOrdersTable :orders="orders" />
</template>
```

### Props

- Always define props with types. Use `defineProps` with TypeScript generics.
- Prefer required props over defaults where intent must be explicit.
- Avoid prop drilling more than 2 levels — use composables or provide/inject instead.

```ts
// ✅ Good
const props = defineProps<{
  userId: string
  readonly?: boolean
  variant?: 'primary' | 'secondary' | 'ghost'
}>()

withDefaults(defineProps<{ variant?: 'primary' | 'secondary' | 'ghost' }>(), {
  variant: 'primary',
})
```

### Emits

Always declare emits explicitly. Use `defineEmits` with TypeScript.

```ts
// ✅ Good
const emit = defineEmits<{
  'update:modelValue': [value: string]
  'item-selected': [item: Product]
  'form-submit': [payload: CreateUserDto]
}>()
```

### Template Cleanliness

- Avoid logic in templates. Extract to computed properties or methods.
- Max 1 ternary in a binding. Use computed for anything more complex.
- Never use `v-if` and `v-for` on the same element — wrap with `<template>`.

```vue
<!-- ❌ Bad -->
<li v-for="item in items" v-if="item.active" :key="item.id">

<!-- ✅ Good -->
<template v-for="item in items" :key="item.id">
  <li v-if="item.active">{{ item.name }}</li>
</template>
```

### Slots

Prefer slots over prop-based content rendering for flexible components.

```vue
<!-- ✅ Good: slot-based flexibility -->
<BaseCard>
  <template #header>
    <h2>Title</h2>
  </template>
  <p>Body content</p>
  <template #footer>
    <BaseButton>Save</BaseButton>
  </template>
</BaseCard>
```

---

## Composables

Composables are the primary abstraction unit. Prefer them over mixins, helpers classes, or bloated components.

### Rules

- One concern per composable.
- Always return reactive refs/computed — not raw values.
- Clean up side effects with `onUnmounted` or `watchEffect` auto-cleanup.
- Prefix with `use`.

```ts
// ✅ Good — useDisclosure.ts
export function useDisclosure(initial = false) {
  const isOpen = ref(initial)

  const open = () => { isOpen.value = true }
  const close = () => { isOpen.value = false }
  const toggle = () => { isOpen.value = !isOpen.value }

  return { isOpen: readonly(isOpen), open, close, toggle }
}
```

### Async Composables

Use `useAsyncData` or `useFetch` in page/layout context. Wrap lower-level fetch logic in composables for reuse.

```ts
// ✅ composables/useUser.ts
export function useUser(id: MaybeRef<string>) {
  return useAsyncData(
    () => `user-${toValue(id)}`,
    () => $fetch<User>(`/api/users/${toValue(id)}`),
    { watch: [() => toValue(id)] }
  )
}
```

---

## TypeScript

- Enable strict mode in `tsconfig.json`. No exceptions.
- No `any`. Use `unknown` and narrow, or define a proper type.
- Define API response shapes as interfaces in `types/`.
- Use generics to avoid duplicating similar types.

```ts
// types/api.ts
export interface ApiResponse<T> {
  data: T
  meta: {
    total: number
    page: number
  }
}

export interface User {
  id: string
  name: string
  email: string
  role: 'admin' | 'member' | 'viewer'
}
```

**Avoid:**

```ts
// ❌ Bad
const user: any = await fetchUser()
const data = response as SomeType  // unsafe cast without validation
```

---

## Nuxt UI Usage

Nuxt UI components should be used as the first choice for standard UI patterns before building custom ones.

### Do

- Use `UButton`, `UInput`, `UModal`, `UTable`, `UNotification` etc. directly.
- Customize via the `ui` prop or `app.config.ts` theming — not by overriding internal CSS.
- Use `UForm` + `UFormGroup` for all forms. Bind Zod/Valibot schemas for validation.

```vue
<!-- ✅ Good: UForm with schema validation -->
<script setup lang="ts">
import { z } from 'zod'

const schema = z.object({
  email: z.string().email('Invalid email'),
  password: z.string().min(8, 'Min 8 characters'),
})

type FormData = z.output<typeof schema>

async function onSubmit(data: FormData) {
  await $fetch('/api/auth/login', { method: 'POST', body: data })
}
</script>

<template>
  <UForm :schema="schema" @submit="onSubmit">
    <UFormGroup label="Email" name="email">
      <UInput type="email" />
    </UFormGroup>
    <UFormGroup label="Password" name="password">
      <UInput type="password" />
    </UFormGroup>
    <UButton type="submit">Login</UButton>
  </UForm>
</template>
```

### Don't

- Don't recreate components that Nuxt UI already provides (modals, dropdowns, toasts).
- Don't use raw `<button>` or `<input>` tags where `UButton` / `UInput` apply.
- Don't hardcode colors — use the Nuxt UI color tokens (`primary`, `gray`, `red`, etc.).

### Theming

Configure globally in `app.config.ts`, not inline:

```ts
// app.config.ts
export default defineAppConfig({
  ui: {
    button: {
      rounded: 'rounded-lg',
      default: {
        size: 'md',
        color: 'primary',
      },
    },
    input: {
      rounded: 'rounded-lg',
    },
  },
})
```

---

## State Management

Use Pinia. Keep stores domain-scoped and thin.

### Store Rules

- One store per domain entity (e.g., `useUserStore`, `useCartStore`).
- Keep derived/computed data as `getters`, not duplicated state.
- Side effects (API calls) belong in `actions`.
- Do not import one store inside another — use composables to coordinate.

```ts
// stores/useCartStore.ts
export const useCartStore = defineStore('cart', () => {
  const items = ref<CartItem[]>([])

  const totalPrice = computed(() =>
    items.value.reduce((sum, item) => sum + item.price * item.quantity, 0)
  )

  async function addItem(product: Product) {
    const existing = items.value.find(i => i.id === product.id)
    if (existing) {
      existing.quantity++
    } else {
      items.value.push({ ...product, quantity: 1 })
    }
  }

  function clearCart() {
    items.value = []
  }

  return { items: readonly(items), totalPrice, addItem, clearCart }
})
```

---

## API & Data Fetching

### Rules

- Always use `useFetch` or `useAsyncData` in components/pages (SSR-aware).
- Use `$fetch` only inside server routes, actions, or event handlers (not during SSR).
- Define server routes in `server/api/` — don't expose raw DB queries to the client.
- Type server routes with `defineEventHandler` and return typed responses.

```ts
// server/api/users/[id].get.ts
export default defineEventHandler(async (event): Promise<User> => {
  const id = getRouterParam(event, 'id')
  const user = await db.user.findUniqueOrThrow({ where: { id } })
  return user
})
```

### Error Handling

Always handle loading and error states in components:

```vue
<script setup lang="ts">
const { data, status, error } = await useFetch<User[]>('/api/users')
</script>

<template>
  <div v-if="status === 'pending'">
    <USkeleton v-for="n in 5" :key="n" class="h-12 w-full" />
  </div>
  <UAlert v-else-if="error" color="red" :description="error.message" />
  <UserList v-else :users="data" />
</template>
```

---

## Performance

- Use `defineAsyncComponent` for heavy components not needed on initial render.
- Prefer `v-show` over `v-if` for frequently toggled elements.
- Use `shallowRef` for large non-reactive data structures.
- Avoid watchers on deeply nested objects — use targeted `watch` with `() => prop.value`.
- Lazy-load images with Nuxt's `<NuxtImg>` component.
- Use `useLazyFetch` for non-critical below-the-fold data.

```ts
// ✅ Lazy load a heavy chart component
const HeavyChart = defineAsyncComponent(() => import('~/components/HeavyChart.vue'))
```

---

## Testing

- Unit test composables and utilities with Vitest.
- Component test with `@nuxt/test-utils` or Vue Test Utils.
- E2E with Playwright for critical user flows.
- Aim for: 80%+ coverage on composables/utils, key component interactions, all API routes.

```ts
// composables/useDisclosure.test.ts
import { useDisclosure } from './useDisclosure'

describe('useDisclosure', () => {
  it('starts closed by default', () => {
    const { isOpen } = useDisclosure()
    expect(isOpen.value).toBe(false)
  })

  it('opens and closes correctly', () => {
    const { isOpen, open, close } = useDisclosure()
    open()
    expect(isOpen.value).toBe(true)
    close()
    expect(isOpen.value).toBe(false)
  })
})
```

---

## Git & Code Review

### Commit Messages

Follow Conventional Commits:

```
feat(auth): add OAuth2 Google login
fix(cart): prevent duplicate item entries
refactor(user): extract profile form to composable
chore(deps): upgrade nuxt-ui to v3.1
```

### Pull Request Checklist

Before opening a PR, confirm:

- [ ] No `any` types introduced
- [ ] New components have defined props and emits
- [ ] Composables are unit tested
- [ ] No hardcoded colors or magic strings
- [ ] `useFetch` / `useAsyncData` used for SSR-aware fetching
- [ ] Nuxt UI components used where applicable
- [ ] Loading and error states handled in UI
- [ ] No `console.log` left in production code
- [ ] `app.config.ts` updated if new UI defaults introduced

### Code Review Norms

- Review for correctness first, style second.
- Suggest, don't demand — use "Consider..." or "What do you think about...".
- Approve when it's good enough, not perfect.
- Keep PR scope small — one concern per PR.

---

> This document should evolve with the project. If a guideline causes more friction than value, open a discussion and
> update it.