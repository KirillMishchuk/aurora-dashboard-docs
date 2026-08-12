# 02 — Architecture

## Big picture

```
Browser (React 19, TanStack Router)
   │  tRPC over HTTP (default prefix /polaris-bff)
   ▼
BFF: Fastify + tRPC  (packages/aurora/src/server)
   │  signal-openstack (undici)          │ AWS SDK v3 (S3)
   ▼                                     ▼
OpenStack APIs (Keystone, Nova, Neutron, Glance, Swift…)   Ceph RGW (S3)
```

- The client is stateless and does no direct OpenStack calls; all contracts are Zod-validated and typed end-to-end via tRPC.
- The BFF owns session cookies, token scoping/rescoping, policy evaluation, retries and API stitching.

## Server side (BFF)

### Entry point

`createServer(config)` in `packages/aurora/src/server` builds and returns a `FastifyInstance` (before `.listen()`), so consumers can register extra plugins/routes. Key config: `identityEndpoint` (required, Keystone v3), `policyDir` (required), `bffEndpoint` (default `/polaris-bff`), `viteRoot`, `defaultEndpointInterface`, `proxyUrl` (dev only), `cephRegion`, `imageMetadataExcludedProperties`, `cookieName`/`cookieDomain`/`crossDomainCookie`/`insecureCookies`, `routers` (custom tRPC routers).

Security middleware in the stack: `@fastify/helmet`, `@fastify/csrf-protection` (client caches CSRF token, see commit `4518889`), cookie-based session (`dashboard-session-auth` by default). Note: the global rate limit (`@fastify/rate-limit`, 200 req/min) was removed in #1075 — the BFF currently has no built-in rate limiting.

### Domain module convention

Each OpenStack domain lives in a PascalCase folder under `src/server/`:

```
Compute/
  routers/    # tRPC routers (one per resource: serverRouter, flavorRouter, keypairRouter, imageRouter, permissionRouter…)
  types/      # Zod schemas + inferred types
  helpers/    # pure helpers
  *.test.ts   # colocated vitest tests
```

Domains: `Authentication`, `Project`, `Compute`, `Network`, `Storage` (swift + ceph subtrees), `Services` (PCA/Clavis), plus `policies/` (permission router factory) and `aurora-fastify-plugins/`.

### Procedure builders (exported from `@cobaltcore-dev/aurora/server`)

`auroraRouter`, `publicProcedure`, `protectedProcedure`, `projectScopedProcedure`, `domainScopedProcedure`, `projectScopedInputSchema`, `domainScopedInputSchema`.

Rules:
- Custom/consumer routers **must** be created with `auroraRouter` (same initTRPC instance) or context types (`ctx.openstack`, `ctx.validateSession`, `ctx.rescopeSession`) break at runtime.
- Typical pattern: `protectedProcedure.input(zodSchema).query/mutation` → `ctx.rescopeSession({ projectId })` → `session.service("compute").get("os-keypairs")` → parse with Zod (`safeParse`) → return typed data.

### Error handling

Two styles coexist. **Legacy** (some handlers, e.g. parts of `Compute/routers/serverRouter.ts`): try/catch the whole handler body, `schema.safeParse` with manual field-by-field logging, and on any failure — missing service, parse failure, thrown error — silently `return undefined`, pushing failure handling onto the client. **Generic wrapper, broadly adopted**: `withErrorHandling(operation, operationName)` (`server/helpers/errorHandling.ts`) runs an async operation and normalizes any non-`TRPCError` into a `TRPCError` (`INTERNAL_SERVER_ERROR`) via `wrapError`, rethrowing an already-thrown `TRPCError` as-is — used across Compute (images), Network (floating IP, RBAC policy, security group + rules), Services (PCA), and Storage (Swift) routers. **Network adds a further, narrower layer on top**: `parseOrThrow(schema, data, context)` (`Network/helpers/index.ts`) throws a `PARSE_ERROR` `TRPCError` instead of swallowing a Zod parse failure, and a per-resource `ErrorHandler(resourceName)` factory (`Network/helpers/errorHandling.ts`) maps HTTP status codes (400/401/403/404/409/412) to typed `TRPCError`s with resource-specific messages — currently wired up for floating IPs, with `pcaRouter.ts` reusing `parseOrThrow` on its own. The file's own comment marks this status-mapping layer `WORK_IN_PROGRESS`/prototype ("only used for list procedures in Port and Network helpers... goal is to extend this... in the future") — treat `withErrorHandling` as the actually-established convention to follow, and `parseOrThrow`/`ErrorHandler` as a newer pattern still confined to Network, not yet a repo-wide standard.

### Auth and token scoping

- Login creates a Keystone session; the token is kept server-side, session tracked via cookie.
- OpenStack calls need project- or domain-scoped tokens → route loaders call scoping mutations (e.g. `auth.setCurrentScope` / `rescopeSession`) so components receive already-scoped data.
- A `useScope` hook (commit `c55b535`) combines URL params and auth context on the client.
- **Client auth state** lives in `src/client/store/AuthProvider.tsx` (refactored in #1072): tRPC auth calls are centralized here; `login({ domain, user, password })` and `logout()` come from the context, which also exposes `isLoading`/`error`. A session-expiry timer auto-logs-out and redirects to login with a return-URL param (redirect back after re-login); manual logout does not save a return URL. `LoginForm` uses Juno FormRow/TextInput with uncontrolled inputs.
- Projects list page uses optimistic rendering via Suspense + `useSuspenseQuery` (#1067).
- **Two hooks read scope from different sources, deliberately** — `useDomainId()` (`client/hooks/useDomainId.ts`) reads the domain from the **session** (`useAuth().user.domain.id`), throwing if the user has no domain; `useProjectId()` (`client/hooks/useProjectId.ts`) reads the **URL** (`useParams({ strict: false })`, compatible with both the legacy `/accounts/:accountId/projects/:projectId` and current `/projects/:projectId` shapes), throwing outside a project-scoped route. Don't conflate them: domain scope is session-derived, project scope is URL-derived.
- **Rescope deduplication** (`server/context.ts`): a module-level `Map<authToken, Map<scopeKey, Promise<string | null>>>` (`sessionRescopes`) coordinates concurrent requests from the same session so they don't each hit Keystone. `rescopeSession({ projectId, domainId })` first no-ops if the token is already scoped to the requested project/domain; otherwise it derives a `scopeKey` (`project:{id}` / `domain:{id}` / `unscoped`) and, if another request already has a rescope in flight for that exact key, awaits the same promise instead of re-rescoping — only the resulting **token string** is cached (never the session object), so each request still applies the result to its own `openstackSession`/cookie. If Keystone's rescope response changes the auth token itself, the pending-rescope map is migrated to the new token key (merged with any map already there) before the old key is dropped; a `finally` always removes the completed entry and prunes now-empty maps (both the original and, if migrated, the new key) to avoid a leak.

## Permissions & policy

Two layers, both driven by oslo.policy files from `policyDir` (JSON/YAML; the reference app ships `compute.json`, `networking.json`, `image.json`, `storage.json`):

1. **policy-engine** (`packages/policy-engine`): lexer → parser (AST) → evaluator; compatible with oslo.policy syntax (`role:admin`, `rule:x`, `user_id:%(target.user.id)s`, `and/or/not`, `@`/`!`, `is_admin:true`…). Works server-side and in-browser. `createPolicyEngine(config)` / `createPolicyEngineFromFile(path)` → `engine.policy(keystoneToken)` → `policy.check("rule", params)`. Debug tracing available.
2. **Permission routers** (see `PERMISSION_ROUTER_IMPLEMENTATION.md`): a generic factory `createPermissionRouter` (`src/server/policies/`) maps UI-facing permission keys to policy engines + rules, with single and bulk checks.

**Permission key convention** (see `PERMISSION_KEY_PATTERN.md`): `scope:resource:action`, e.g. `storage:containers:create`, `network:routers:attach_interface`. Scope is a service domain (`storage`, `network`, `compute` — never implementation names like swift/ceph/neutron); resource is plural snake_case; action is a CRUD verb or specific operation. UI checks these keys, never raw OpenStack rules.

## Client side

### File-based routing (TanStack Router v1)

- Route files live in `packages/aurora/src/client/routes/`; dynamic segments use `$` prefix (`$projectId`), non-route folders use `-` prefix (`-components/`, `-hooks/`, `-modals/`).
- `_auth.tsx` is the shared layout for authenticated views: `beforeLoad` checks/hydrates the session and redirects to `/auth/login` otherwise.
- Loaders (not components) fetch data and set token scope; components receive loader data. Subnavigation is declarative via `linkOptions` + `useParams`.
- Route tree (current): `/` , `/about`, `/auth/login`, `_auth/projects` → `$projectId` → `compute | network (securitygroups, floatingips) | storage ($provider/$storageType/$containerName/objects) | services/pca`. `_auth/accounts` also exists but is a redirect-only stub (`beforeLoad` sends authenticated users with a domain to `/projects`, everyone else to `/`) — no page renders there.
- **List state lives in the URL.** Toolbar state (filters, search, sort key/direction) for a list view is kept in search params, not component state, so a filtered list is shareable and browser back/forward restores it. The route declares a Zod `validateSearch`; the flavors/floating-IP pattern (#1129) `safeParse`s the whole object and, on failure, falls back **per field** — a bad `sortBy` drops only `sortBy` instead of resetting the toolbar, and the component supplies its own defaults for `undefined`. Navigation intent differs by trigger: sort/filter/immediate-search changes `push` a history entry, debounced search-as-you-type uses `replace` so typing doesn't fill the history stack. Route-specific parse/build helpers live in a route-local `urlHelpers.ts` (floating IPs, security groups), not in shared utils.

### AuroraApp component

`<AuroraApp />` props: `bffEndpoint`, `theme`/`onThemeChange`, `appName`, `slots`, `onTrackEvent`, `enabledServices` (whitelist of service keys: `images`, `flavors`, `securitygroups`, `floatingips`, `containers`, `ceph-containers`, `pca`).

- **Slots** — UI extension points without forking: `logo`, `sideNavBanner` (shadow DOM), `pageFooter`, `login` (for OIDC), `serviceBadge`, `servicePageActions`, `serviceBanner`, `projectsBanner`, `projectOverviewBanner`. Slots get `auroraContext` with a tRPC `client`; service-level slots also get `currentService`. Shadow-DOM slots must inline their styles. `slots.login` replaces the default `LoginForm` on the landing page (`/`) for unauthenticated users — it was silently dropped by the #1072 auth refactor and restored in #1079.
- **Analytics** — `onTrackEvent(payload: {source, action, metadata})`; router navigation is auto-tracked (`source: "router"`, action = route ID, metadata includes pathname/search/section/service from route `staticData`). Custom events go through `useRouteContext().onTrackEvent`. See `packages/aurora/docs/0013_analytics-tracking.md`.

### tRPC client link strategy (`client/trpcClient.ts`)

`getLinks()` is a `splitLink` chain evaluated in order: subscriptions → `httpSubscriptionLink`; non-JSON-serializable input (FormData/Blob/ArrayBuffer) → plain `httpLink` (no batching); JSON procedures listed in the `STREAMING_PROCEDURES` set (currently `storage.swift.downloadObject`, `storage.ceph.objects.downloadObject`) → `httpBatchStreamLink`; everything else → `httpBatchLink`. `httpBatchStreamLink` is deliberately not the default link — it's incompatible with `@fastify/csrf-protection`'s cookie rotation on long-lived connections — so a new streaming procedure must be added to the allow-list explicitly rather than switching the default. A module-level `csrfCache` dedupes concurrent CSRF-token fetches (one in-flight request shared by all callers) and exposes `getCsrfToken`/`setCsrfToken` so a separate JS context — a Web Worker gets its own module instance of `trpcClient.ts` — can share the main thread's cached token instead of re-fetching.

### Query cache isolation

`QueryClient`'s `queryKeyHashFn` (set in `App.tsx`) reads `router.state.matches` directly (not React context) to find the deepest matched route carrying a `projectId` param, and prefixes that project id onto every query key before hashing. Switching projects therefore never returns cached data from a previous project — but only for query keys that go through the shared `queryClient`; ad-hoc caching bypasses this isolation.

## Cross-cutting mechanisms

- **Request cancellation** (`docs/0010_abort_signal_propagation.md`): per-request `AbortController` in Fastify context tied to connection close events (`res.raw`/`req.raw "close"`); signal flows browser → tRPC → signal-openstack → native fetch, so cancelled uploads/queries abort the OpenStack call too.
- **SSE / subscriptions** (`docs/004_proposal_subscriptions.md`): proposed unified single-SSE-connection design (lightweight invalidation notifications + normal tRPC refetch), targeting ~2000 concurrent users; centralized polling worker. Status: proposal.
- **Extensions** (`docs/001_extensions.md`): Aurora Extensions export `./client` and/or `./server` (with `registerRouter`), built from an extension template, sharing tRPC versions via the aurora-sdk concept. The current shipped mechanism for consumers is `createServer({ routers })` + slots.
- **Ceph S3 BFF** (`docs/009_ceph_s3_bff.md`): EC2 credentials fetched via Keystone, AWS SDK v3 with path-style addressing, S3 errors mapped to tRPC error codes, project-scoped isolation; needs `cephRegion`. Object upload (`uploadObject`, #1086) streams the request body straight into a `PutObjectCommand` via `octetInputParser` (no multipart, no whole-file buffering) with per-chunk progress on a `watchUploadProgress` subscription; it runs on a dedicated `cephUploadProcedure` rather than the usual `cephProtectedProcedure`, because tRPC can't merge a raw-stream (`octetInputParser`) input with the object-shaped `project_id` input that `projectScopedProcedure`-based procedures bundle ("All input parsers did not resolve to an object"). So upload metadata (project id, bucket, object key, size, an `x-upload-id` correlating with the progress subscription) travels as `x-upload-*` request headers instead of a tRPC input, and `cephUploadProcedure` rescopes the session from the `x-upload-project-id` header itself. Sharing an object goes through `objects.generatePresignedUrl` (#1120, a normal `cephProtectedProcedure`): `getSignedUrl` from `@aws-sdk/s3-request-presigner` signs a `GetObjectCommand` with the request's EC2 credentials — the S3 answer to Swift temp URLs, but with no key to configure and no round-trip to Ceph, since signing is purely local. It returns `{ url, expiresAt }` (absolute unix seconds, so the UI shows a real expiry rather than a duration), and `expiresIn` is capped in the Zod input schema at `S3_PRESIGN_MAX_EXPIRY_SECONDS` (604800 = 7 days, `Storage/constants.ts`) because the SigV4 signer rejects anything longer.
- **Virtualized storage tables** (`client/hooks/useAvailableViewportHeight.ts`, `useVirtualizedTableBody.ts`, #1090 + #1123): shared hooks size Ceph/Swift bucket and object tables to the actual remaining viewport height instead of letting `max-height` follow content — the latter creates a feedback loop where measured rows resize the scroll container, which makes `@tanstack/react-virtual` recompute its range and re-measure. **Both** edges are measured, in document coordinates (`getBoundingClientRect().top + scrollY`, so the value doesn't drift with scroll): the top from the element itself, so a banner slot, wrapped toolbar or second breadcrumb line shrinks the table rather than growing the page; the bottom from the page footer's top edge, found by `document.querySelector(".app-page-footer")` — an app-owned wrapper added around the `pageFooter` slot in `__root.tsx` deliberately *not* a component-library class, so the measurement survives changes to the shell's internal markup. The footer is a sibling, not an ancestor, so it's explicitly added to the `ResizeObserver` alongside the element's ancestor chain; a custom footer of any height therefore re-triggers measurement instead of overlapping the last rows (short-footer gap / tall-footer overlap was the #1123 bug). With no footer at all (embedded mode, no footer slot) it falls back to viewport bottom minus a 52px constant. Clamped to a **150px** floor (was 200 before #1123) so a very short viewport falls back to page scroll rather than an unusably short table. The per-call `bottomGap` parameter of both hooks was removed in #1123 — the footer is measured, not configured. `useVirtualizedTableBody` withholds `virtualItems`/`totalSize` until the height is known, so the virtualizer never renders the whole unvirtualized list on first paint.
- **Ceph object downloads run in a Web Worker** (#1062, `client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/`): streaming, base64 decode, and Blob assembly for `storage.ceph.objects.downloadObject` happen off the main thread in `workers/objectDownload.worker.ts`, so a large object doesn't jank the UI. Transfer ownership lives in a module-scope store (`stores/objectDownloadStore.ts`, outside React, read via `useSyncExternalStore`) rather than in `ObjectsTableView` — a download survives the table unmounting on folder navigation or a spinner swap, matching what the "download started" toast already promises. Concurrent transfers share one persistent toast, dismissed when the last one ends (saved/failed/cancelled). Cancel is cooperative: the row clears immediately, the worker is told to abort its fetch (which tears down the BFF's S3 read via `ctx.req.signal`, no separate server-side cancel procedure), and is force-terminated after a 5s grace period if it never reports back.
  - The worker is bundled inline (Vite `?worker&inline`), not as a separate asset — a URL-referenced worker would be lost when a consuming app re-bundles the library. Inline means it runs from a `blob:` URL, which needs `worker-src 'self' blob:` in CSP; `createServer()`'s production Helmet config now sets this (`server.ts`) — a consumer running its own CSP needs the same directive.
  - A worker gets its own module instance of `trpcClient.ts`, so it never sees `App`'s `setBffEndpoint()` call or the main thread's CSRF token cache — `getBffEndpoint()`/`getCsrfToken()`/`setCsrfToken()` were added to hand both across explicitly (BFF endpoint must be absolute for the worker, since a `blob:` location can't resolve a root-relative path).
  - The library build's `vite.config.mjs` substitutes `process.env.NODE_ENV` via `define` — react-query (pulled in by `trpcClient`) reads it, and the inlined worker has no `process` to read it from at runtime.
- **Toasts go through `NotificationManager`, not the legacy `<Toast>`** (#1132 migrated the last holdout, Glance images; Swift/Ceph storage views already did): a view no longer holds toast state or renders a `<Toast>` element. Per-domain builder modules (e.g. `ImageToastNotifications.tsx`, `ObjectToastNotifications.tsx`) export `getXxxToast(...)` functions returning `{ message, ...NotificationOptions }`; the call site destructures and picks severity itself — `const { message, ...options } = getImageUpdatedToast(name); toast.success(message, options)`. Severity lives at the call site, not in the builder, and `setToastData`-style plumbing is gone. Error-path builders take an already-extracted message string, so callers must read `error.data?.path` / error messages null-safely — otherwise a failure throws inside its own `catch`. Note #1132 left `NotificationText.tsx` (+ its test) orphaned in the images folder — dead code, not a dependency.
- **Gardener**: mentioned as an integration direction (Kubernetes-native infra management) — branches exist upstream, not part of the current core routers.
- **Shared two-column detail view** (`client/components/TwoColumnDescriptionList.tsx`, #1111): data-driven replacement for hand-rolled `DescriptionList`/`DescriptionTerm`/`DescriptionDefinition` JSX pairs — takes `items: {id?, label: string | ReactNode, value: string | number | ReactNode | undefined}[]`, splits them into two `DescriptionList` columns. Used by Flavor, Image, Floating IP and Security Group detail views; moved from the floating-IP-only `-components/` folder up to the shared `client/components/` once other domains adopted it.
