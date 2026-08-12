# Agent Patterns

Actionable patterns and anti-patterns for AI coding agents working in this repo.
For commands, procedure builders, and routing basics, see [CLAUDE.md](../CLAUDE.md).

## Where to look

| Task | Location |
|------|----------|
| Add a tRPC procedure | `packages/aurora/src/server/<Domain>/routers/` |
| Add Zod types for API responses | `packages/aurora/src/server/<Domain>/types/` |
| Register a domain router | `packages/aurora/src/server/<Domain>/routers/index.ts` → `packages/aurora/src/server/routers.ts` |
| Add permission checks | `<Domain>/routers/permissionRouter.ts` via `createPermissionRouter` — see [PERMISSION_KEY_PATTERN.md](../PERMISSION_KEY_PATTERN.md) |
| Add a UI page | `packages/aurora/src/client/routes/_auth/projects/$projectId/<section>/` |
| Shared route components | `.../-components/` (prefix `-` excludes from route tree) |
| Consumer app wiring only | `apps/dashboard/src/server/server.ts`, `apps/dashboard/src/client/App.tsx` |
| OpenStack HTTP client | `packages/signal-openstack/` |
| Policy evaluation | `packages/policy-engine/`, loaded via `packages/aurora/src/server/policies/` |
| Policy YAML/JSON files | `apps/dashboard/src/policies/` |
| Debug "why was this permission denied" | `packages/policy-engine/src/debugTrace.ts` — use `PolicyEngine.checkRuleWithDebug`/`checkRuleWithTrace` |
| Server router test fixtures | `<Domain>/routers/mockContext.ts` pattern, e.g. `Storage/routers/ceph/mockContext.ts` |
| Global test setup (mocks, i18n) | `packages/aurora/vitest.setup.ts` |
| E2E auth/session fixtures | `apps/dashboard/e2e/global-setup.ts`, `apps/dashboard/e2e/helpers/auth.ts` |
| Public `AuroraApp` / `createServer` API | [packages/aurora/README.md](../packages/aurora/README.md) |

## Dependency map

```
apps/dashboard
  → @cobaltcore-dev/aurora/server   (createServer, auroraRouter, procedure builders)
  → @cobaltcore-dev/aurora/client   (<AuroraApp />)

packages/aurora/server
  → signal-openstack   (OpenStack sessions, service catalog, HTTP)
  → policy-engine      (oslo.policy evaluation)

packages/aurora/client
  → TanStack Router    (file-based routes, loaders)
  → TanStack Query     (caching; tRPC React hooks)
  → tRPC client        (typed BFF calls)
  → Lingui             (i18n)
  → juno-ui-components (UI kit)
```

`signal-openstack` has no classes — sessions/services/tokens are factory functions returning closures. It calls global `fetch`, not undici directly; undici's `ProxyAgent` is only pulled in dynamically when a dev-mode `proxyUrl` is set (mitmproxy debugging).

## Server patterns

### Procedure builders (always use these, never raw `initTRPC`)

| Builder | When to use |
|---------|-------------|
| `publicProcedure` | Login, session introspection, no auth required |
| `protectedProcedure` | Authenticated; reads token metadata (e.g. service catalog) |
| `projectScopedProcedure` | Any project-level OpenStack resource; requires `project_id` in input |
| `domainScopedProcedure` | Domain-admin operations; requires `domain_id`, validates access via `/v3/auth/domains` |

Custom routers passed to `createServer({ routers })` **must** use exported `auroraRouter` — a different `initTRPC` instance breaks `ctx.openstack` at runtime.

### Request context (`context.ts`)

- **Token rescoping dedup**: a module-level `Map<authToken, Map<scopeKey, Promise<token>>>` caches only the resulting **token string**, never the session object, so concurrent requests don't share mutable state. First caller for a given `scopeKey` (`project:{id}` / `domain:{id}` / `unscoped`) stores the pending promise before awaiting; concurrent callers await the same promise and apply the result to their own session/cookie. A `finally` block deletes the entry and prunes empty maps. If Keystone's rescope response changes the auth token itself, the pending-rescope map is migrated to the new key.
- **`ctx.signal`**: an `AbortController` wired to both `res.raw` close (queries/mutations) and `req.raw` close/error (in-flight streaming uploads). Pass it into every long-running OpenStack call (e.g. `swift.get/put/del`) so client disconnect actually cancels the upstream request.
- **`getUserInfo`**: lazily fetches `/v3/auth/domains`, memoized per user id, invalidated after a rescope (role assignments can change). Only called by `domainScopedProcedure` — avoid triggering it from project-scoped or public code paths.

### Cookies & CSRF

- The session cookie (`dashboard-session-auth`, `HttpOnly`, `SameSite=strict`) stores only the raw OpenStack **auth token string** — never the scope. Scope lives server-side, inside the Keystone token itself.
- CSRF (`@fastify/csrf-protection`, registered as a non-encapsulated `fastify-plugin`) validates a custom `x-csrf-token` header against the `aurora-csrf-protection` cookie, only for POST/PUT/DELETE, with explicit path exclusions (e.g. `/extensions`). `GET /csrf-token` issues the token.

### Error handling — two styles currently coexist

- **Legacy** (e.g. `Compute/routers/serverRouter.ts`): try/catch around the whole handler, `schema.safeParse` with manual field-by-field error logging, and on *any* failure — missing service, parse failure, thrown error — silently `return undefined`, pushing failure handling onto the client.
- **Target pattern** (e.g. `Network/routers/floatingIpRouter.ts` and newer code): wrap the handler body in `withErrorHandling(fn, "operation label")`; after a fetch, check `response.ok` and throw a status-mapped `TRPCError` via a domain `ErrorHandler(resourceName)` (`HTTP_STATUS_ERROR_MAP`: 400/401/403/404/409/412 → tRPC codes); parse the success payload with `parseOrThrow(schema, data, context)`, which throws `PARSE_ERROR` instead of swallowing it.

**When adding or touching a router handler, use the target pattern** (`withErrorHandling` + `parseOrThrow` + a status-aware `ErrorHandler`), not the legacy `return undefined` style — the latter is being phased out domain by domain.

Note: `Compute/errorCodes.ts` is a narrow, Flavor-specific enum (`GET_FLAVOR_DETAILS_NOT_FOUND`, etc.) — it is not a global error-code registry; don't assume other domains use it.

### Adding a new domain procedure

1. Define Zod schemas in `<Domain>/types/`.
2. Add procedure in `<Domain>/routers/<resource>Router.ts` using the correct procedure builder, wrapped in `withErrorHandling` with `parseOrThrow` for the response (target pattern above).
3. Spread into `<Domain>/routers/index.ts`.
4. Add colocated `*.test.ts` for schema validation and router logic (see Testing patterns below for the mock-context approach).

## Client patterns

### Route conventions

- `$param.tsx` — dynamic segment
- `-folder/` — non-route files (components, helpers, tests)
- `_auth.tsx` — auth guard; its `beforeLoad` tries `auth.getCurrentUserSession.query()` and redirects on failure; no child renders without a valid session
- `routeTree.gen.ts` — generated; do not hand-edit

### Data loading

- The "loader fetches/rescopes, component renders" rule is **strict only at the scope-establishing route** (`projects/$projectId.tsx`, which calls `auth.setCurrentScope.mutate(...)` in its loader).
- Below that, most leaf list/detail routes have **no loader at all** — their `-components/` fetch directly via `trpcReact.<domain>.<resource>.useQuery(...)` and handle `isLoading`/`isError` manually inside the component. Don't assume a loader exists just because a route is under `_auth`.
- Route-level failures use `errorComponent` (e.g. `RouteError`); uncaught render errors fall back to the top-level `ErrorBoundary` in `App.tsx`.
- `beforeLoad` on service routes also checks `auth.getAvailableServices` and redirects if the service is unavailable; `staticData: RouteInfo` on leaf routes drives breadcrumbs/nav metadata and is what `setupRouterAnalytics.ts` reads for `section`/`service` in tracked events.

### tRPC client link strategy (`trpcClient.ts`)

| Input type | Link |
|------------|------|
| Subscriptions | `httpSubscriptionLink` |
| FormData / Blob / ArrayBuffer (non-JSON) | `httpLink` (no batching) |
| Streaming procedures (`STREAMING_PROCEDURES` set, currently only `storage.swift.downloadObject`) | `httpBatchStreamLink` |
| Everything else | `httpBatchLink` |

Do **not** enable `httpBatchStreamLink` globally — CSRF cookie rotation breaks long-lived streams; keep new streaming procedures explicitly allow-listed in `STREAMING_PROCEDURES` instead of switching the default link.

### Query cache isolation

`QueryClient`'s `queryKeyHashFn` (in `App.tsx`) reads `router.state.matches` directly (not React context) to find the deepest matched route carrying a `projectId` param, and prefixes that onto every query key before hashing. Switching projects never returns cached data from a previous project — but this only works for query keys that go through the shared `queryClient`; don't bypass it with ad-hoc caching.

### Auth state

- `AuthProvider` is a plain React Context holding `user`/`expiresAt`, independent of the router. It arms a timer to auto-`logout("expired")` at token expiry (shows an inactivity modal) and calls `router.invalidate()` on manual logout to force loaders/guards to rerun.
- `useDomainId()` reads the domain from the **session** (`useAuth().user.domain.id`) — throws if missing.
- `useProjectId()` reads the **URL** (`useParams({ strict: false })`) — throws if `projectId` isn't present, and works across both old (`/accounts/:accountId/projects/:projectId`) and new (`/projects/:projectId`) URL shapes.
- Don't conflate the two: domain scope is session-derived, project scope is URL-derived.

## Supporting packages

### signal-openstack request flow

```
SignalOpenstackSession(endpoint, authConfig{scope})
  → POST {endpoint}/v3/auth/tokens          (validates AuthSchema first)
  → X-Subject-Token header + body.token     → SignalOpenstackToken
session.service("compute")
  → token.serviceEndpoint("compute", {interfaceName: "public", region})   (reads Keystone catalog embedded in the token)
service.get("/servers")
  → fetch → non-2xx → parseErrorObject → throw SignalOpenstackApiError
```

`rescope()` re-POSTs `{auth:{identity:{methods:["token"],token:{id}}, scope}}` to swap scope without re-sending credentials.

### policy-engine

Rules are compiled up front (`PolicyEngine` constructor tokenizes/parses every rule, not lazily). `engine.policy(keystoneToken).check(ruleName, params)` builds a flattened `PolicyContext` (roles, project/domain/user ids, `is_admin`, system scope) from the token and evaluates the rule's AST against it — grammar supports `role:x`, `rule:other_rule` (recursive), `%(param)s` substitution from `params`, and `and`/`or`/`not`. For a "why was this denied" investigation, use `checkRuleWithDebug`/`checkRuleWithTrace` rather than re-deriving the logic by hand.

## Testing patterns

- Tests are colocated `*.test.ts(x)` next to source — no `__tests__` tree.
- `packages/aurora/vitest.setup.ts` globally mocks `@tanstack/react-router` (shared `mockRouter`) and `@/client/trpcClient` (components never hit a real client in unit tests), stubs SVG `?react` imports and `ResizeObserver`, and resets Lingui to `i18n.activate("en")` before each test.
- **Server router tests**: build a fake context with a local/nearby `mockContext.ts` (e.g. `Storage/routers/ceph/mockContext.ts`) exposing `vi.fn()`-based `validateSession`/`rescopeSession`/`openstack.service(name)`, then call the router via `createCallerFactory(auroraRouter(...))`. External SDK clients (e.g. the S3 client) are mocked separately with `vi.mock(...)` and asserted on both return value and call count.
- **React component tests**: wrap in `<I18nProvider i18n={i18n}>` explicitly only when the component actually uses Lingui — don't add it reflexively to every test.
- **signal-openstack tests**: stub `global.fetch` directly (a hand-built `Response`-shaped mock with `.clone()`) — this package does not use nock/msw.
- **policy-engine integration tests**: exercise the real lexer/parser/evaluator against inline or temp-file fixtures — no mocking of the engine itself; this is the pattern to follow when adding new rule-evaluation coverage.
- **Playwright** (`apps/dashboard`): there is no `webServer` config — tests expect a dev server already running at `PLAYWRIGHT_BASE_URL`/`BASE_URL`. `globalSetup` logs in once and persists `storageState.json`, reused by authenticated specs; the `chromium-unauthenticated` project explicitly clears `storageState` for logged-out flows.

## Permissions

- UI keys: `scope:resource:action` (domain vocabulary, not OpenStack service names).
- Each domain exposes `canUser` via `createPermissionRouter`.
- Bulk check: `permission: ["key1", "key2"]` → `[boolean, boolean]`.
- Full naming rules: [PERMISSION_KEY_PATTERN.md](../PERMISSION_KEY_PATTERN.md).

## Anti-patterns

| Don't | Do instead |
|-------|------------|
| Call `initTRPC` in custom routers | Use `auroraRouter` from `@cobaltcore-dev/aurora/server` |
| Rescope tokens in React components | Rescope in route `loader` via `auth.setCurrentScope` |
| Use OpenStack names in permission keys (`neutron`, `swift`) | Use domain keys (`network`, `storage`) |
| Hand-edit `routeTree.gen.ts` | Let TanStack Router codegen regenerate it |
| Set `proxyUrl` expecting it in production | Proxy is dev-only; ignored in production |
| Use `httpBatchStreamLink` for all procedures | Scope streaming link to `STREAMING_PROCEDURES` only |
| Put business logic in `apps/dashboard` | Put it in `packages/aurora` |
| Skip Zod validation on OpenStack responses | `safeParse`/`parseOrThrow` + log format errors |
| Return `undefined` on handler failure (legacy pattern) | `withErrorHandling` + `parseOrThrow` + a status-aware `ErrorHandler` → typed `TRPCError` |
| Assume every route under `_auth` has a `loader` | Leaf routes often fetch client-side via `useQuery` with manual loading/error state |
| Mock external HTTP with nock/msw in `signal-openstack` tests | Stub `global.fetch` directly |

## Related docs

- [CLAUDE.md](../CLAUDE.md) — commands, overview, commit conventions
- [PERMISSION_KEY_PATTERN.md](../PERMISSION_KEY_PATTERN.md) — permission key naming
- [PERMISSION_ROUTER_IMPLEMENTATION.md](../PERMISSION_ROUTER_IMPLEMENTATION.md) — `createPermissionRouter` factory contract
- [packages/aurora/README.md](../packages/aurora/README.md) — public consumer API (slots, config)
- [docs/aurora_architecture_overview.md](./aurora_architecture_overview.md) — high-level architecture (human-oriented)
