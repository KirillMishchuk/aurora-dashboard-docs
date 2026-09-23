# Plan: Invalid storage provider/type must render a 404, not a list (issue #1081)

**Date:** 2026-09-14 · **Revised:** 2026-09-15 (scope expanded after resolving all open questions with the user) · **Revised again:** 2026-09-15 (plan audited against HEAD `6f4c35de`; D6–D13 added, several claims corrected, three silent test breakages caught) · **Status:** implemented 2026-09-15 on branch `kiryl-storage-type-404-1081` — all 10 steps done, 27 files, uncommitted per D5; typecheck/lint/format clean, 228 test files · 5671 tests green, build OK; security review clean (no Critical/High); 5 implementation-level deviations documented below; **Manual verification (Testing Plan items 1–10) not yet run** — needs a live dashboard.

### Deviations recorded at implementation time (2026-09-15)

1. `requireAvailableProvider` returns the narrowed `StorageProvider` instead of using an `asserts` signature — TS rejects assertion signatures on destructured parameters (`TS2775`). Same runtime behavior, same reason order.
2. Two type-only casts, both commented in-code: `notFoundComponent: StorageNotFound as NotFoundRouteComponent` (the router's `NotFoundRouteProps` doesn't model the `data`-spread documented in the Router facts) and `context as unknown as { availableServices: ServiceInfo[] }` in both loaders (this router version doesn't surface the `beforeLoad`→`loader` context merge in the inferred type). The runtime merge was re-verified against the installed router: `load-matches.js:268` stores the `beforeLoad` return as `__beforeLoadContext`, `buildMatchContext` (:34, `includeCurrentMatch = true`) merges it into the same match's context, and `getLoaderContext` (:335) passes that to the loader. **Residual risk:** because the cast is unchecked, deleting `return { availableServices }` from a `beforeLoad` would not fail typecheck and would surface only at runtime — the "Route lifecycle ordering" tests are the guard.
3. `ServiceInfo` exported from `serviceAvailability.ts` (was private) for the cast above.
4. Comments that would have contained the literal strings `cephFallbackEnabled`/`CEPH_FALLBACK_ENABLED` were reworded to "the removed Ceph availability fallback (D6)", so the acceptance-criterion grep returns genuinely nothing.
5. `BucketModalsProps.storageType` and `useBucketModals`'s `storageType` parameter left in place though now unused inside the component — Step 6 asked for the derivation invariant, not a signature change.

**Follow-ups surfaced by the security pass (both pre-existing, neither introduced here, neither blocking):**
- `getServiceIndex` (`server/Authentication/helpers/index.ts`, untouched) builds its index via `acc[service.type][service.name] = true` with no own-property guard, so a catalog entry typed `"__proto__"` would write onto `Object.prototype`. Source is the user's own Keystone catalog, so not cross-tenant injectable — but note that `hasServiceByName` reads `byName[name]` without `Object.hasOwn`, so a polluted prototype would make every provider look available. Cheap hardening, separate ticket.
- `setupRouterAnalytics` still forwards raw `metadata.pathname` / `metadata.search` (container names, base64 `prefix`, search terms) to the host app's `onTrackEvent`. Unchanged by this PR; worth a ticket if the host's analytics sink ever renders that as HTML.

## Overview

`/projects/$projectId/storage/$provider/$storageType` never validates the `$storageType` segment and treats any unknown/unavailable `$provider` as a redirect target. Result: `/storage/swift/lolnope` happily renders the Swift container list, and `/storage/garbage/garbage` silently bounces to a fallback provider. This change makes syntactically invalid or unavailable provider/storage-type URLs return a real in-shell 404, keeps the "project has no object store at all" case as a redirect to the project overview, and removes the last hardcoded `swift→containers` / `ceph→buckets` string pairs by centralizing them in one constant.

The audit pass added a second, independent fix in the same files: **the frontend looked Ceph up under the wrong service-catalog key**, which is the real reason the `CEPH_FALLBACK_ENABLED` workaround existed. Provider resolution now matches the backend (by service *name*, ignoring catalog *type*), the flag is deleted, and a Ceph-only project stops being bounced to the project overview (D6/D9).

Scope covers both storage routes (list + objects), a new shared 404 view with distinct copy per failure reason, a provider↔storage-type constant consumed by 5 additional call sites, a catalog-lookup helper consumed by the guards + nav + project overview, analytics hygiene on the 404 path, and rewrites of the existing assertions in both route test files.

This is sub-issue #1081 of epic #1246 "[EPIC](Ceph): Fix post go-live design and functionality issues". Sibling sub-issue #1119 (bucket name validation) is already handled on a separate branch/PR (#1288) — unrelated, out of scope here.

### Decisions this revision is built on (resolved with the user 2026-09-15, final)

- **D1 — 404 presentation:** in-shell `Status status="error" code={404}`, as a route-level `notFoundComponent` so it renders inside `AuroraLayout`/breadcrumbs (not the shell-less root `PageNotFound`).
- **D2 — Provider validation, applies to BOTH storage routes identically:** "no object-store service at all" stays a `redirect` to the project overview (in `beforeLoad`); "provider is not swift/ceph" and "provider is swift/ceph but unavailable for the project" both become `notFound()` (moved to `loader`).
- **D3 — ~~StorageType-vs-provider validation stays asymmetric~~ — REVERSED 2026-09-16 during manual verification.** Originally: list route 404s on a mismatch, while the deeper objects route keeps redirecting to the canonical path with the same `containerName` (it has a concrete container to land on; the list route doesn't). Reversed after seeing it live: it left the objects route as the sole exception to the 404 rule, and the compatibility argument does not hold — the app never generated a non-canonical objects URL (all five hardcoded pairings produced canonical paths, and before `7b3e4deb` the routes were splat-shaped entirely), so the redirect normalized nothing real. **Both routes now share one guard, `validateStorageAccess`, and a non-canonical `storageType` 404s everywhere.** See the Manual verification log for the full change list.
- **D4 — Shared constant:** `STORAGE_TYPE_BY_PROVIDER` (or equivalent), migrated into by all 5 additional hardcoded call sites, not just the two validators.
- **D5 — Delivery:** working tree modified, not committed, not pushed.

### Decisions added by the audit pass (2026-09-15, second revision)

- **D6 — Services are resolved by *name*, not by catalog *type*.** The guard's `serviceIndex["object-store"]["ceph"]` never matches: Ceph is in the Keystone catalog as `{ type: "object-store-ceph", name: "ceph" }` (see `buildNavSections.ts:93`, `buildNavSections.test.ts:16`). The backend has no such problem — it resolves both providers by name and ignores type (`cephProcedure.ts:23` → `ctx.openstack?.service("ceph")`; `swiftRouter.ts:99` etc. → `service("swift")`; `signal-openstack/src/session.ts:95` takes only a name). The frontend adopts the same rule via a shared `hasServiceByName(serviceIndex, name)` helper.

  **Consequence: `CEPH_FALLBACK_ENABLED` is deleted outright, not set to `false`.** History: the flag was introduced in `76146c28` (2026-05-15 12:54) because Ceph's endpoint then came from the `CEPH_S3_ENDPOINT` env var and genuinely worked without a catalog entry. `b9e51fc3` (same day, 13:19) removed that env path — "Endpoints now exclusively from OpenStack service catalog via `ctx.openstack.service("ceph")`". Since then the flag's stated premise has been dead: with no catalog entry the backend throws `Ceph service not found in OpenStack service catalog` on every request, so the flag only buys a page whose every call fails. What actually kept it load-bearing is the wrong-key bug above. Once D6 lands, the flag has nothing left to mask. Its comment (`// Set to false once Ceph is in catalog`) is misleading — Ceph has been in the catalog all along, just under a type the guard never looked at.

- **D7 — Component and constant placement.** The 404 view is split in two: a **generic** `client/components/Error/RouteNotFound.tsx` (sibling of `RouteError.tsx`, reusable — `services/$serviceType.tsx` should adopt it in a follow-up) and a thin `storage/-components/StorageNotFound.tsx` adapter that only maps `reason` → copy. Shared constants go to `client/utils/storageProviders.ts` and `client/utils/serviceCatalog.ts` (flat folder, alongside `formatBytes`/`buildFilterParams`) — **not** under `$projectId/storage/-components/utils/`, which would make `projects/-components/buildNavSections.ts` import upward out of a leaf route subtree.

- **D8 — The fetch-count claim is restated honestly.** `$projectId.tsx:79` already fetches `auth.getAvailableServices` in its own `loader`, so the real numbers are: **cold load 3 → 2**, **in-project navigation 2 → 1**. `$projectId.tsx` is not touched. The old "one query per navigation, not two" wording would make a DevTools check on a cold load look like a regression.

- **D9 — The nav and the project overview migrate to name lookup too**, not just the guards: `buildNavSections.ts:79,93` and `$projectId/index.tsx:84,91`. Fixing only the guard leaves the mirror hole (Ceph registered under `object-store` → reachable by URL, invisible in the nav). Verified safe: no existing test asserts the negative case, all nav tests mock `object-store-ceph`/`ceph` and keep passing.

- **D10 — Two distinct 404 messages**, driven by `notFound({ data: { reason } })`:
  - `provider-not-found` / `provider-unavailable` → "Object Storage Not Found" — the service does not exist or is not available for this project.
  - `storage-type-mismatch` (i.e. the actual subject of #1081) → "Page Not Found" — the address is not valid for this object storage service.
  A single shared message would be factually wrong for the mismatch case, where the service does exist and is available.

- **D11 — The 404 action button goes to the project overview** (`/projects/$projectId`) in every case. Deliberately *not* "take me to the canonical storage URL" — that would reintroduce, on click, exactly the redirect this change removes.

- **D12 — Analytics on the 404 path is fixed here, not deferred.** `setupRouterAnalytics.ts:54-57` interpolates the raw `provider` URL segment into the event name (`analytics.name.replace("objectstore", provider)`), so any visitor minting `/storage/<anything>/containers` mints a new action name `storage.<anything>.list` — unbounded cardinality in the `action` dimension, sourced entirely from user input, forwarded to the consumer's `onTrackEvent`. Guard it with `isStorageProvider(provider)` from step 1 (falls back to the literal `objectstore`). Event **names** are unchanged, so existing dashboards keep working.

  **Scope trimmed 2026-09-16.** D12 originally bundled a second change: `metadata.notFound = true` when `deepestMatch.status === "notFound"`, so a 404 stops being reported as a successful list view. Removed on review — #1081 does not require it, and its value is speculative in a way the guard's is not: `metadata` is forwarded to the host app's `onTrackEvent`, nothing in this repo reads the field, and `packages/aurora/README.md` does not document it, so it only helps if a consumer we neither control nor can inspect already knows to look for it. Adding a field to a public analytics payload on that basis is scope the ticket did not ask for. The guard half stays: it closes a hole this PR itself widens, since an invalid provider now stays on screen instead of redirecting away. (Mechanism, kept for the record: `onResolved` fires from `Transitioner.js:86` on any pending→idle transition regardless of match outcome, and `match.status` does carry `'notFound'` — `router-core/Matches.d.ts:49` — so the flag would have worked; it just isn't warranted.)

- **D13 — `head` loses its false fallback; no dependence on `match.status`.** Confirmed that `head` *does* run for the 404: `load-matches.js:573` sets `headMaxIndex = renderedBoundaryIndex` and the loop at :585 executes `executeHead` for every match up to and including the not-found boundary — which is the leaf storage route itself. So the tab currently reads "Object Storage (Swift)" on a `swift/buckets` 404 and "Storage Overview" on an unknown provider, the latter naming a page that does not exist (the route renders a `<div>Storage Overview Page</div>` placeholder). Fix: derive the title through `isStorageProvider`, with a neutral `Object Storage` fallback. Deliberately **not** reading `match.status` inside `head` — that would depend on the internal ordering of the status update vs. the head loop, an undocumented detail that can move between router versions. The breadcrumb in `$storageType.tsx` is left as-is behaviorally (its unknown-provider label is already a neutral "Storage"), but its provider ternary migrates to the shared constant so no sixth hardcoded mapping survives.

## Architecture Analysis

### Current state (verified against working tree at `bb6e7ccd`; all line numbers and test-case line references re-verified by the audit pass against HEAD `6f4c35de` — still accurate)

| File | Role today |
| --- | --- |
| `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/$provider/$storageType/index.tsx` | List route. Exports `checkServiceAvailability(availableServices, { projectId, provider })` (lines 28–103, no `storageType` param at all), called from `beforeLoad` (151–155). `loader` (142–150) makes a *second* `auth.getAvailableServices.query()` and returns `{ client, availableServices }` — read by nobody. Dead `notFoundComponent` at 139–141 (`<p>Storage service not found</p>`, not even wrapped in `Trans`). |
| `.../storage/-components/utils/serviceAvailability.ts` | Near-identical `checkServiceAvailability` (108 lines) used by the objects route's `beforeLoad`, plus a 4th block (94–107) that canonicalizes `storageType` by redirecting. Duplicates `cephFallbackEnabled = true` and its TODO. |
| `.../storage/$provider/$storageType/$containerName/objects/index.tsx` | Objects route. Same double-fetch pattern (`loader` 68–76 + `beforeLoad` 77–81), `notFoundComponent` at 61–67 (`<Trans>Storage container not found</Trans>`, currently dead). |
| `.../services/$serviceType.tsx` | Only `notFound()` precedent (line 14), with the load-bearing comment about throwing from a `loader`. **Audit correction:** the file is 17 lines and defines **no** `notFoundComponent` — its `notFound()` falls through to the shell-less root `PageNotFound`. So D1 is not "following the repo precedent", it establishes a new one; the precedent covers only *where* `notFound()` is thrown, not how it renders. D7's generic `RouteNotFound` exists so this route can be fixed the same way in a follow-up. |
| `client/routes/__root.tsx` | `PageNotFound` (78–96): `<Container className="py-8"><Status status="error" code={404} .../></Container>`, rendered **instead of** `RootComponent` — loses `AuroraLayout` entirely, which is exactly why D1 wants a route-level component. |
| `client/components/Error/RouteError.tsx` | The in-layout `Status` precedent (no `Container` wrapper) — model the new 404 view on this, with `code={404}` added. |

Router facts verified in the installed `@tanstack/router-core@1.168.15`:

- `notFound()` returns a plain object `{ isNotFound: true }` (`dist/esm/not-found.js`). Assert with `isNotFound()`, never `toThrow()`.
- `getNotFoundBoundaryIndex` walks up from the throwing match to the nearest route that defines a `notFoundComponent`. A `notFound()` thrown in the list route's own `loader` renders that route's `notFoundComponent` in that route's match position — inside `AuroraLayout` and the breadcrumb layout's `<Outlet/>`. No route defines it → falls through to the shell-less root fallback (no `defaultNotFoundComponent` configured in `router.ts`).
- `beforeLoad` is awaited for every match top-down *before* any `loader` runs — a `redirect` from `beforeLoad` always wins over a `notFound()` from a `loader`.
- `buildMatchContext` merges a match's `beforeLoad` return value into the context passed to that match's own `loader` — so `beforeLoad` can fetch `availableServices` once and hand it to `loader`, killing the existing duplicate tRPC call.
- This router version *does* also support `notFound()` thrown from `beforeLoad` (`beforeLoadNotFound`) — but the plan still puts every `notFound()` in a `loader` per D2, matching the repo's own `$serviceType.tsx` precedent/comment. It's the documented, version-proof contract.
- **`notFound({ data })` spreads `data` into the component's props — it is not passed as a `data` prop.** `react-router/dist/esm/renderRouteNotFound.js:21`: `jsx(route.options.notFoundComponent, { ...data })`. So `notFound({ data: { reason: "storage-type-mismatch" } })` renders `<StorageNotFound reason="storage-type-mismatch" />`. Writing the component as `({ data })` yields `undefined` and silently falls back to the default copy — a failure that neither a component test nor a guard test catches on its own. `NotFoundError` is typed `{ data?: any; routeId?; headers?; throw? }` (`router-core@1.168.15/dist/esm/not-found.d.ts`); `packages/aurora` resolves `@tanstack/react-router@1.168.22`.

### Proposed changes

1. New constant module `client/utils/storageProviders.ts` (D7) — single source of truth for `swift↔containers` / `ceph↔buckets`, plus `isStorageProvider`/`asStorageProvider` narrowing helpers.
2. New `client/utils/serviceCatalog.ts` (D6/D7) — `hasServiceByName(serviceIndex, name)`, the frontend's mirror of the backend's name-only service resolution.
3. `serviceAvailability.ts` becomes the **one** shared guard module for both routes, exposing three functions split along the `beforeLoad`/`loader` line:
   - `requireObjectStoreService(...)` → `redirect` only (beforeLoad-safe). Behavior changes per D6: "is there any object store at all" becomes `hasSwift || hasCeph` by name, instead of the presence of a literal `object-store` catalog type.
   - `validateStorageListAccess(...)` → `notFound()` for invalid provider, unavailable provider, and non-canonical storage type (list route), each carrying its `reason` per D10.
   - `validateObjectsAccess(...)` → `notFound()` for invalid/unavailable provider, then `redirect` for non-canonical storage type (objects route, D3 asymmetry preserved).
   The duplicate `checkServiceAvailability` in the list route file is deleted; ~80 lines of near-duplicate logic collapse into one place; `CEPH_FALLBACK_ENABLED` disappears entirely (D6).
4. New generic `client/components/Error/RouteNotFound.tsx` + thin `StorageNotFound.tsx` adapter, used by **both** routes' `notFoundComponent` (D7, D10).
5. Both routes: `beforeLoad` = fetch once + no-service redirect + return `{ availableServices }`; `loader` = pure validation from context, no tRPC call, no return value.
6. The 5 hardcoded-mapping call sites migrate to the constant; every object-storage catalog gate migrates to `hasServiceByName` — inside the guard module, plus `buildNavSections.ts` (2) and `$projectId/index.tsx` (2) (D6/D9).
7. `setupRouterAnalytics.ts` stops interpolating a raw URL segment into event names and flags not-found navigations (D12).

**Judgment call (flagged, not acted on):** the `beforeLoad` fetch + no-service redirect could move up into the shared layout route `$storageType.tsx` (ancestor of both leaf routes), removing even the remaining 4-line `beforeLoad` duplication. **Recommended against** for this change — that route exists purely for a breadcrumb (#1254), has no test file, and mixing in auth/availability gating makes the guarded context an implicit cross-route contract the two leaf routes' tests can no longer exercise in isolation. Worth a follow-up issue, not this PR.

## Potential Problems & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Any bookmark/deep link with a non-canonical storage type on the *list* route (e.g. `/storage/swift/buckets`) 404s instead of rendering | Medium (intended) | All in-app links are generated from the constant after step 6, so nothing in the app can produce such a URL. Call out in the PR description. |
| A bookmark to a provider that is valid but unavailable to the current project (e.g. `/storage/swift/containers` after switching to a Swift-less project) 404s instead of gracefully redirecting to the other provider | Medium (intended, not covered by the previous revision) | The nav never generates such a link, so exposure is bookmarks and browser history. D10's distinct copy keeps the 404 honest, and D11's button lands the user on the project overview where the available storage cards are listed. Call out in the PR description alongside the storage-type case. |
| `checkServiceAvailability` is removed from both modules | Low | Verified not in `client/index.ts` (not public API), no importers other than the two routes and their tests. |
| ~~Guard and nav disagree on the Ceph catalog key~~ | ~~Medium~~ | **Superseded by D6 — now fixed in this PR, not deferred.** The audit found the earlier framing wrong on two counts: (a) `CEPH_FALLBACK_ENABLED` does not mask it — the flag rescues `hasCeph`, but *not* the first gate `if (!serviceIndex["object-store"])`, so a Ceph-only project is bounced to the overview today while the nav happily shows the Ceph entry; (b) the flag's own premise died in `b9e51fc3`. Both ends now resolve by name (D6, D9). |
| Name-only lookup would match an unrelated service literally named `ceph`/`swift` under some other catalog type | Low | Accepted deliberately: the collision is hypothetical, the frontend/backend divergence is the bug actually being fixed, and narrowing to `object-store*` types would re-introduce a rule the backend does not apply. Revisit only if such a catalog entry ever appears. |
| `hasServiceByName` placed in `@/server/Authentication/helpers` would break both storage test files | Medium | Both tests do `vi.mock("@/server/Authentication/helpers", () => ({ getServiceIndex: vi.fn() }))` — a factory returning *only* `getServiceIndex`. Any new export from that module arrives as `undefined` inside the guard, failing with an opaque "is not a function". Hence D7: the helper lives in `client/utils/serviceCatalog.ts`. |
| `notFoundComponent` written as `({ data })` instead of `({ reason })` | Medium (silent) | `data` is spread into props (see router facts above). Covered by an explicit `StorageNotFound` prop test plus `expect(caught.data).toEqual({ reason: ... })` assertions in the guard tests. |
| Deleting `CEPH_FALLBACK_ENABLED` changes behavior for a deployment where Ceph really is absent from the catalog | Low | Such a deployment is already broken: `cephProcedure.ts:23` throws on every Ceph call. Before: a rendered page whose every request fails. After: an honest 404. Strictly an improvement, but call it out in the PR body. |
| Existing tests written around `cephFallbackEnabled` keep passing for the wrong reason, or break for the wrong reason | High (silent test rot) | Three distinct traps, all enumerated in steps 7/8: (a) cases missing `storageType` now hit the mismatch branch — `defaultParams` and every override gain one; (b) five cases asserting "ceph works without a catalog entry" (list ~114/~319, objects ~146/~222) must **flip to notFound**, and objects ~235 must flip from notFound to a project-overview **redirect**; (c) the objects file's "Canonical storageType enforcement" `beforeEach` relies on the flag to make Ceph available — its fixture must register Ceph in the catalog or the whole block stops testing canonicalization. |
| `"__proto__" in STORAGE_TYPE_BY_PROVIDER` evaluates `true` — a naive `in` check would let `/storage/__proto__/containers` pass provider validation | Medium | `isStorageProvider` uses `Object.hasOwn` (repo's existing guard style). Explicit `__proto__`/`constructor` test cases. |
| `notFound()` thrown from `beforeLoad` or during render doesn't reliably reach `notFoundComponent` | High if violated | All `notFound()` calls live in `loader`s only; repeat the `$serviceType.tsx`-style comment above each. |
| Dropping the list route's `loader` return value (`{ client, availableServices }`) | Low | Verified: no `useLoaderData({ from: ... })` anywhere for either storage route. |
| `availableServices!` non-null assertion turns a failed/undefined query into a `TypeError` → error boundary | Low | Replace with `?? []`, routing cleanly into the existing "no object store → project overview" redirect. |
| i18n catalog churn: `lingui extract --clean` drops "Storage container not found", adds new 404 strings across `en`/`de` | Low | Run `check-i18n`, commit regenerated `.po`+`.ts` for both locales. German `msgstr` stays empty — normal, CI-clean. |

**Positive side-effect (restated per D8):** each storage route currently issues `auth.getAvailableServices` twice on its own (`beforeLoad` + `loader`, no cache), and `$projectId.tsx:79` issues a third in its loader on a cold load. This change removes the leaf route's duplicate: **cold load 3 → 2, in-project navigation 2 → 1.** Guarded by a test asserting the leaf `beforeLoad` queries exactly once and the `loader` queries zero times. `$projectId.tsx` is out of scope — collapsing the last one would mean moving its loader fetch into a `beforeLoad`, far beyond #1081.

## Prerequisites

- [ ] Work from a branch dedicated to #1081 — do not mix with `kiryl-bucket-and-folder-validations`/PR #1288 (#1119, unrelated).
- [ ] Working tree clean before starting (`git status`).
- [ ] `pnpm install` already done.
- [ ] No decisions outstanding — D1–D13 are final.

## Implementation Steps

### Step 1: Create the shared constant + catalog modules (D4, D6, D7)

**Create:** `client/utils/storageProviders.ts` + `storageProviders.test.ts` (path per D7 — **not** under the storage route subtree)

```ts
export const STORAGE_TYPE_BY_PROVIDER = { swift: "containers", ceph: "buckets" } as const
export type StorageProvider = keyof typeof STORAGE_TYPE_BY_PROVIDER
export type StorageType = (typeof STORAGE_TYPE_BY_PROVIDER)[StorageProvider]

// Object.hasOwn, not `in` — "__proto__" in obj is true.
export const isStorageProvider = (value: unknown): value is StorageProvider =>
  typeof value === "string" && Object.hasOwn(STORAGE_TYPE_BY_PROVIDER, value)

export const asStorageProvider = (value: unknown, fallback: StorageProvider): StorageProvider =>
  isStorageProvider(value) ? value : fallback

export const storageTypeFor = (provider: StorageProvider): StorageType =>
  STORAGE_TYPE_BY_PROVIDER[provider]
```

Tests: `isStorageProvider` true for `"swift"`/`"ceph"`; false for `""`, `"containers"`, `"SWIFT"`, `"__proto__"`, `"constructor"`, `"toString"`, `undefined`, `null`, `123`. `asStorageProvider`/`storageTypeFor` round-trips.

**Also create:** `client/utils/serviceCatalog.ts` + `serviceCatalog.test.ts` (D6):

```ts
/**
 * Mirrors the backend's service resolution, which matches by NAME and ignores the
 * catalog type entirely (cephProcedure.ts:23 → ctx.openstack.service("ceph");
 * swiftRouter.ts → service("swift"); signal-openstack session.ts:95 takes only a name).
 * The old type-scoped lookups disagreed with it: Ceph lives in the catalog as
 * { type: "object-store-ceph", name: "ceph" }, so serviceIndex["object-store"]["ceph"]
 * never matched and CEPH_FALLBACK_ENABLED had to paper over it.
 */
export const hasServiceByName = (serviceIndex: Record<string, Record<string, boolean>>, name: string) =>
  Object.values(serviceIndex).some((byName) => byName[name])
```

Tests: finds `ceph` under `object-store-ceph`, under `object-store`, and under any other type; returns `false` for an empty index, for a missing name, and for a name present only as a *type* (`{"ceph": {...}}` must not count).

**Verify:** `pnpm --filter @cobaltcore-dev/aurora test storageProviders serviceCatalog`; `typecheck`.

### Step 2: Rework `serviceAvailability.ts` into three lifecycle-split guards (D2, D3, D6, D10)

**Modify:** `.../storage/-components/utils/serviceAvailability.ts` — full rewrite of its exported surface.

1. Imports: `redirect`, `notFound` from `@tanstack/react-router`; `getServiceIndex`; `hasServiceByName` from `@/client/utils/serviceCatalog`; `isStorageProvider`, `storageTypeFor`, `StorageProvider` from `@/client/utils/storageProviders`.
2. Keep `ServiceInfo` interface. Export the reason union used by D10: `type StorageNotFoundReason = "provider-not-found" | "provider-unavailable" | "storage-type-mismatch"`.
3. **Delete `CEPH_FALLBACK_ENABLED` entirely** (D6) — flag, comment and TODO. Private `getProviderAvailability(availableServices)` → `{ hasSwift, hasCeph }`, both computed with `hasServiceByName` over `getServiceIndex(availableServices)`.
4. Export `requireObjectStoreService(availableServices, { projectId })` — `redirect` to the project overview when `!hasSwift && !hasCeph`. Note the D6 change: the gate is no longer "is there a literal `object-store` catalog type", it is "is either provider resolvable by name". JSDoc: **beforeLoad-safe**, must run first in every storage route.
5. Export `validateStorageListAccess(availableServices, { provider, storageType })` — `notFound({ data: { reason } })` with `provider-not-found` if provider isn't swift/ceph, `provider-unavailable` if it is but is missing from the catalog, `storage-type-mismatch` if `storageType !== storageTypeFor(provider)`. JSDoc: **loader-only**, assumes `requireObjectStoreService` already ran.
6. Export `validateObjectsAccess(availableServices, { projectId, provider, storageType, containerName })` — same two provider `notFound()` checks (factor a private `requireAvailableProvider` shared by both composites), then `redirect` (not notFound) to the canonical path with the same `containerName` on a storageType mismatch — target/params unchanged from today. JSDoc explains the deliberate D3 asymmetry.
7. Delete old `checkServiceAvailability`, `RouteParams`, and the fallback-provider computation entirely.

**Resulting behavior, list route** (the whole PR in one table):

| provider / storageType | today | after |
| --- | --- | --- |
| neither provider resolvable by name | redirect → project overview | redirect → project overview (unchanged) |
| `ceph`, catalog has `object-store-ceph` only (no `object-store` at all) | **redirect → project overview — Ceph unreachable even though the nav links to it** | **renders** ✅ D6 |
| `nope`, `__proto__`, `Swift` | redirect → first available provider | `notFound` · `provider-not-found` |
| `swift`, no Swift in catalog | redirect → `ceph/buckets` | `notFound` · `provider-unavailable` |
| `ceph`, no Ceph anywhere in the catalog (but `object-store` exists) | **renders** — the flag forces availability, then every backend call fails with `Ceph service not found` | `notFound` · `provider-unavailable` |
| `swift/buckets`, `ceph/containers` | **renders the wrong list** ← #1081 | `notFound` · `storage-type-mismatch` |
| `swift/containers`, `ceph/buckets` | renders | renders |

**Verify:** `typecheck` (routes/tests will error until steps 4–8 — expected).

### Step 3: Create the in-shell 404 views — generic + storage adapter (D1, D7, D10, D11)

**Create A:** `client/components/Error/RouteNotFound.tsx` + test — generic, reusable, sibling of `RouteError.tsx`.

Modeled on `RouteError.tsx` (no `Container` wrapper — already inside `AuroraLayout`/the `$storageType` layout), with `code={404}`:

```tsx
export function RouteNotFound({ title, body, action }: { title?: string; body?: string; action?: ReactNode }) {
  const { t } = useLingui()
  const navigate = useNavigate()
  return (
    <Status
      status="error"
      code={404}
      title={title ?? t`Page Not Found`}
      body={body ?? t`The page you are looking for does not exist.`}
      action={
        action ?? (
          <Button variant="primary" onClick={() => navigate({ to: "/projects" })}>
            <Trans>Go to Projects</Trans>
          </Button>
        )
      }
    />
  )
}
```

**Create B:** `.../storage/-components/StorageNotFound.tsx` + test — the thin adapter that maps `reason` → copy (D10) and supplies the action (D11).

```tsx
// `notFound({ data: { reason } })` spreads `data` into props — this component receives
// `reason`, NOT `{ data }`. See renderRouteNotFound.js:21.
export function StorageNotFound({ reason }: { reason?: StorageNotFoundReason }) {
  const { t } = useLingui()
  const navigate = useNavigate()
  const { projectId } = useParams({ strict: false })

  const isBadUrl = reason === "storage-type-mismatch"

  return (
    <RouteNotFound
      title={isBadUrl ? t`Page Not Found` : t`Object Storage Not Found`}
      body={
        isBadUrl
          ? t`This address is not valid for this object storage service.`
          : t`This object storage service does not exist or is not available for this project.`
      }
      action={
        projectId ? (
          <Button variant="primary" onClick={() => navigate({ to: "/projects/$projectId", params: { projectId } })}>
            <Trans>Go to Project</Trans>
          </Button>
        ) : undefined /* falls back to RouteNotFound's "Go to Projects" */
      }
    />
  )
}
```

`useParams({ strict: false })` is required — a `notFoundComponent` renders for a match whose loader failed, so a typed `from:`-pinned accessor isn't safe.

Tests (wrap in `<I18nProvider i18n={i18n}>`):
- `RouteNotFound`: default title/body render, `404` renders, default action present, custom `action` overrides it.
- `StorageNotFound`: `reason="storage-type-mismatch"` renders the "address is not valid" copy; `reason="provider-not-found"` and `reason="provider-unavailable"` render the "not available for this project" copy; **`reason` undefined** falls back to the latter; the button targets the project overview.
- **Regression guard for the props-spread gotcha:** render `<StorageNotFound {...{ reason: "storage-type-mismatch" }} />` and assert the mismatch copy — i.e. that the component reads a flat `reason` prop, not `data.reason`.

**Verify:** `pnpm --filter @cobaltcore-dev/aurora test RouteNotFound StorageNotFound`.

### Step 4: Rewire the list route (D1, D2, D3, D13)

**Modify:** `.../storage/$provider/$storageType/index.tsx`

1. Delete `checkServiceAvailability` and its now-unused `redirect`/`getServiceIndex` imports.
2. Import `requireObjectStoreService`, `validateStorageListAccess` from `../../-components/utils/serviceAvailability`, `StorageNotFound` from `../../-components/StorageNotFound`.
3. `beforeLoad`:
   ```ts
   beforeLoad: async ({ context, params }) => {
     const availableServices = (await context.trpcClient?.auth.getAvailableServices.query()) ?? []
     requireObjectStoreService(availableServices, params)
     return { availableServices }
   },
   ```
4. `loader`:
   ```ts
   // notFound() must be thrown from a loader, not from beforeLoad or during render, for
   // TanStack Router to intercept it and show notFoundComponent instead of crashing the
   // error boundary. See services/$serviceType.tsx for the same constraint.
   loader: ({ context, params }) => {
     validateStorageListAccess(context.availableServices, params)
   },
   ```
5. `notFoundComponent: StorageNotFound`.
6. `head` — replace the nested provider ternary with `isStorageProvider(match.params.provider)`, falling back to a neutral `Object Storage` instead of `Storage Overview` (D13). `head` runs for the 404 page too, so the fallback must not name a page that does not exist.
7. Leave `validateSearch`, `staticData`, `StorageDashboard` untouched (their `default:` branches become unreachable but are harmless defense-in-depth).

**Verify:** `typecheck`; manual checks in Testing Plan.

### Step 5: Rewire the objects route (D2, D3)

**Modify:** `.../storage/$provider/$storageType/$containerName/objects/index.tsx`

1. Swap `checkServiceAvailability` for `requireObjectStoreService, validateObjectsAccess`; add `StorageNotFound`.
2. `beforeLoad` — same shape as step 4.3.
3. `loader` — `validateObjectsAccess(context.availableServices, params)`, same loader-only comment, no tRPC call, no return.
4. `notFoundComponent: StorageNotFound`. Drop the old "Storage container not found" copy — after this change the boundary fires only for an invalid/unavailable **provider** (storage-type mismatch redirects; a missing container is an API-level error, not a route notFound), so that wording would mislead.

**Verify:** `typecheck`.

### Step 6: Migrate the hardcoded call sites — mapping (D4) and catalog gating (D9)

1. `client/routes/_auth/projects/-components/buildNavSections.ts` (lines 87/89 Swift, 101/103 Ceph) — replace the four literals with `STORAGE_TYPE_BY_PROVIDER.swift`/`.ceph` (import via `@/client/utils/storageProviders`).
2. `$projectId/index.tsx` (lines 88, 95) — template strings: `` `${base}/storage/swift/${STORAGE_TYPE_BY_PROVIDER.swift}` `` / ceph equivalent.
3. `Ceph/Buckets/BucketTableView.tsx` (~182–183) — `provider`/`storageType` from `useParams({ strict: false })` are `string | undefined`; derive once: `const resolvedProvider = asStorageProvider(provider, "ceph")`, then `storageType: storageTypeFor(resolvedProvider)`. Hoist out of the row-render closure.
4. `Ceph/Buckets/BucketModals.tsx` (~67–68) — same derivation from the `provider?: string` prop.
5. `Ceph/Objects/ObjectBrowserView.tsx` (~981–982) — same derivation (the `?? "ceph"` here was already dead code; point is removing possible provider/storageType drift, not fixing a live bug).

**Invariant:** `storageType` is always derived from the resolved `provider`, never defaulted independently.

**Catalog gating (D9)** — the same two files, different lines:

6. `buildNavSections.ts:79` — `serviceIndex?.["object-store"]?.["swift"]` → `hasServiceByName(serviceIndex, "swift")`.
7. `buildNavSections.ts:93` — `serviceIndex?.["object-store-ceph"]?.["ceph"]` → `hasServiceByName(serviceIndex, "ceph")`.
8. `$projectId/index.tsx:84` and `:91` — same two substitutions.

The `isEnabled("containers")` / `isEnabled("ceph-containers")` whitelist checks and the `service:` identifiers on the nav items/cards are **untouched** — they are the consumer-facing `enabledServices` vocabulary, unrelated to catalog types.

**Invariant:** no file indexes the **object-storage** catalog entries by type any more. `grep -rn '\["object-store' packages/aurora/src/client --include='*.ts' --include='*.tsx'` should match only test fixtures. Scope note: other domains (`serviceIndex.image?.glance`, `serviceIndex.compute?.nova`, `serviceIndex.network` in `$projectId/index.tsx` and `buildNavSections.ts`) still gate by type and are deliberately **not** touched — their type and name do not disagree the way Ceph's do, and converting them is a separate change.

**Verify:** `grep -rn '?? "buckets"\|?? "containers"\|"swift" ? "containers"' packages/aurora/src/client` returns nothing outside `storageProviders.ts`; `typecheck`; `test buildNavSections BucketTableView SideNavBar` pass **unchanged** (verified during the audit: the existing fixtures use `{type:"object-store",name:"swift"}` + `{type:"object-store-ceph",name:"ceph"}`, and no test asserts a negative catalog-key case). **Add** one positive case to `buildNavSections.test.ts`: Ceph registered as `{type:"object-store",name:"ceph"}` still produces the Ceph nav item — otherwise the D6/D9 fix has no test anchoring it.

### Step 6b: Analytics and breadcrumb hygiene on the 404 path (D12, D13)

**Modify:** `client/analytics/setupRouterAnalytics.ts`

1. Lines 54–57 — wrap the provider interpolation in the narrowing guard:
   ```ts
   // `provider` is a raw URL segment. Without this guard any visitor can mint an
   // arbitrary analytics action name (`storage.<anything>.list`) just by editing the URL.
   if (isStorageProvider(provider)) action = analytics.name.replace("objectstore", provider)
   ```
2. ~~Mark not-found navigations so a 404 is not counted as a successful page view (`metadata.notFound = true` when `deepestMatch.status === "notFound"`).~~ **Dropped 2026-09-16 — see the scope note under D12.**

**Modify:** `.../storage/$provider/$storageType.tsx` — the layout route's provider ternary (line 18) moves to the shared constant/narrowing helper. Behavior unchanged: an unknown provider still yields the neutral `Storage` crumb above the 404.

**Tests:** `setupRouterAnalytics.test.ts` already covers the swift/ceph substitution (~318, ~352) — both keep passing. Add one case: an unknown provider leaves `action` as `storage.objectstore.list`. (The two `metadata.notFound` cases were added and then removed with the flag itself.)

**Verify:** `pnpm --filter @cobaltcore-dev/aurora test setupRouterAnalytics`; `typecheck`.

### Step 7: Rewrite the list route's test file

**Modify:** `.../storage/$provider/$storageType/index.test.tsx`

Setup: import `requireObjectStoreService, validateStorageListAccess` instead of `checkServiceAvailability`; keep the `redirect`-throwing mock, do NOT stub `notFound`/`isNotFound` (mock spreads `importActual`); add `isNotFound` import + an `expectNotFound(fn)` helper that asserts `isNotFound(caught)` and **returns the caught error**, so every call site can assert the D10 reason:

```ts
const caught = expectNotFound(() => validateStorageListAccess(services, params))
expect(caught.data).toEqual({ reason: "storage-type-mismatch" })
```

Add `storageType: "containers"` to `defaultParams`.

Note the mock interaction with D6/D7: the file's `vi.mock("@/server/Authentication/helpers", () => ({ getServiceIndex: vi.fn() }))` keeps working because `hasServiceByName` lives in `client/utils/serviceCatalog.ts`, a module this file does **not** mock — the helper runs for real over the mocked index, which is what we want to exercise.

**Change to notFound (4 existing cases):** "throws redirect when swift is not available but provider is 'swift'" (~102); "calls redirect with correct params when swift is unavailable" (~137); "redirects to ceph when object-store exists but swift is missing" (~176); "redirects swift provider to ceph when only ceph is available" (~338) — all become `notFound` assertions + `expect(redirect).not.toHaveBeenCalled()`.

**Stay redirect-shaped, retargeted to `requireObjectStoreService` (4):** "throws redirect when no object-store service is available" (~61), "calls redirect with correct params when no storage services available" (~73), "handles empty availableServices array" (~129), "redirects to project overview when no storage service is available" (~330).

**"Does not throw" cases retargeted, given a matching `storageType` (4):** ~49 (split into two assertions across both functions), ~90 (`storageType: "containers"`), ~163 (`"containers"`), ~309 (`"containers"`).

**Flip to notFound because `CEPH_FALLBACK_ENABLED` is gone (D6) — correction to the previous revision (2):** ~114 and ~319, both named "…cephFallbackEnabled is true", both mocking `{"object-store": {swift: true}}` with `provider: "ceph"`. With the flag deleted and lookup by name, Ceph is genuinely absent from that fixture → `notFound` with `reason: "provider-unavailable"`. Adding `storageType: "buckets"` does **not** rescue them, contrary to what the previous revision said. Rename both off the `cephFallbackEnabled` vocabulary (e.g. "throws notFound when ceph is in neither catalog type") and add the positive counterpart from the new "Catalog lookup by service name" describe.

**Unchanged (2):** both ErrorBoundary-reset (#875) tests and their explanatory comments. (4 + 4 + 4 + 2 + 2 = the file's 16 cases — use this as the checksum that no case was silently dropped.)

**New describes:** "Invalid provider (issue #1081)" — notFound for `"nope"`, `""`, `"__proto__"`, `"Swift"`, each with `reason: "provider-not-found"`; none call redirect. "Canonical storageType enforcement (issue #1081)" — notFound with `reason: "storage-type-mismatch"` for `swift+buckets`, `ceph+containers`, `swift+objects`; no-throw for both canonical pairs; redirect never called. "Route lifecycle ordering" — `beforeLoad` calls the query exactly once, returns `{ availableServices }`; `beforeLoad`'s redirect wins even when provider+storageType are both invalid; tolerates undefined query result; `loader` throws notFound for invalid provider and makes zero tRPC calls.

**New describe: "Catalog lookup by service name (D6)"** — this is the block that anchors the `CEPH_FALLBACK_ENABLED` removal, so it must not be skipped:
- `{"object-store-ceph": {ceph: true}}` + `provider: "ceph"` → does not throw (**this is the case that was broken before D6**; note the old code bounced it to the project overview).
- `{"object-store": {ceph: true}}` + `provider: "ceph"` → does not throw (either catalog type works).
- `{"object-store": {swift: true}}` + `provider: "ceph"` → `notFound` with `reason: "provider-unavailable"` — the case the deleted flag used to swallow. Comment it as the deliberate behavior change.
- `{"object-store-ceph": {ceph: true}}` + `provider: "swift"` → `notFound` / `provider-unavailable`, and `requireObjectStoreService` does **not** redirect (an object store exists, just not Swift).
- `{"ceph": {rgw: true}}` (name appearing only as a *type*) → `requireObjectStoreService` redirects to the project overview.

**Verify:** `pnpm --filter @cobaltcore-dev/aurora test 'storage/\$provider/\$storageType/index.test'`.

### Step 8: Rewrite the objects route's test file

**Modify:** `.../$containerName/objects/index.test.tsx`

Setup: swap import for `requireObjectStoreService, validateObjectsAccess`; add `isNotFound` + `expectNotFound`. `defaultParams` already has `storageType: "containers"`.

**Change to notFound (3):** ~134, ~169, ~210 — all mock `{"object-store": {ceph: true}}` with `provider: "swift"`, so Ceph is available and Swift is not → `reason: "provider-unavailable"`.

**Moves to the *redirect* group — correction to the previous revision (1):** ~235 mocks `{"object-store": {}}`. The old gate `!serviceIndex["object-store"]` read that empty object as truthy and fell through to the provider check, which is why the previous revision filed it under notFound. Under D6 the gate is `hasSwift || hasCeph` by name — both false — so `requireObjectStoreService` redirects to the **project overview**, neither to `ceph/buckets/my-container/objects` (today's behavior) nor to a notFound. Retarget the assertion accordingly.

**Stay redirect-shaped (3):** ~93, ~105, ~161.

**"Does not throw" retargeted, unchanged params (3):** ~81, ~122, ~197 — only the function name changes. (The previous revision listed five entries under a count of four; ~146 and ~222 belong in the next group instead.)

**Flip to notFound because `CEPH_FALLBACK_ENABLED` is gone (D6) (2):** ~146 and ~222, both mocking `{"object-store": {swift: true}}` with `provider: "ceph"` → `notFound` / `provider-unavailable`. Rename off the `cephFallbackEnabled` vocabulary.

**"Canonical storageType enforcement" block (~247–309) — the four tests keep their shape (D3), but the block's `beforeEach` fixture MUST change first.** It currently mocks `{"object-store": {swift: true}}` with the comment "ceph is available via fallback. This lets both providers pass availability so the canonical check is what's exercised" — and three of its four cases pass `provider: "ceph"`. With `CEPH_FALLBACK_ENABLED` deleted (D6) that fixture no longer makes Ceph available, so those three would throw `notFound`/`provider-unavailable` and never reach the canonicalization branch. Change the fixture to actually register Ceph:

```ts
vi.mocked(getServiceIndex).mockReturnValue({ "object-store": { swift: true }, "object-store-ceph": { ceph: true } })
```

and rewrite the comment to say Ceph is available *because it is in the catalog*, not because of a flag. Only then do the three redirect cases (~256, ~266, ~276) and the one no-throw case (~293 — note it is a `not.toThrow`, not a redirect assertion) keep their original meaning. Add a comment at the describe block explaining the deliberate asymmetry with the list route.

**Unchanged (7):** "View Parameter Handling" (5 tests), "Header rendering per provider" (2 tests). (Checksum: 3 + 1 + 3 + 3 + 2 + 4 = the file's 16 guard cases, plus these 7 render cases = 23 total.)

**New describes:** "Invalid provider (issue #1081)" — notFound for `"nope"`/`""`/`"__proto__"`, redirect never called; notFound takes precedence over the canonical-storageType redirect (`provider "nope" + storageType "buckets"` → notFound, not redirect). "Route lifecycle ordering" — same four checks as step 7, plus a regression guard that `ceph + "containers"` still throws the canonical redirect preserving `containerName`.

**Verify:** `pnpm --filter @cobaltcore-dev/aurora test objects/index.test`.

### Step 9: i18n catalogs, changeset, full verification

1. Run `pnpm --filter @cobaltcore-dev/aurora check-i18n`. Expect added to both locales: `Object Storage Not Found`, `This object storage service does not exist or is not available for this project.`, `This address is not valid for this object storage service.`, `Go to Project`, plus `Page Not Found` / `The page you are looking for does not exist.` / `Go to Projects` if not already present from `__root.tsx` (they are — expect reuse, not new entries). `Storage container not found` removed by `extract --clean`. German `msgstr` stays empty. Leave regenerated files in the working tree uncommitted (D5).
2. Create `.changeset/<name>.md`, `"@cobaltcore-dev/aurora": patch`, summary covering: 404 for invalid/unavailable provider or mismatched storage type (list route) rendered in-shell, with distinct copy for a bad URL vs an unavailable service; no-object-store still redirects; objects route still canonicalizes via redirect (intentional asymmetry); **Ceph is now found in the service catalog regardless of its catalog type, and the `CEPH_FALLBACK_ENABLED` workaround is removed**; mapping centralized in one constant now used by nav/overview/Ceph views; one fewer catalog fetch per storage navigation.
3. Run `pnpm --filter @cobaltcore-dev/aurora typecheck`, `lint`, `test`; `pnpm format:check`.
4. Leave working tree modified, uncommitted, unpushed (D5).

## Testing Plan

**Unit tests:**
- [ ] `storageProviders.test.ts` — narrowing + `__proto__`/`constructor` rejection + round-trips.
- [ ] `serviceCatalog.test.ts` — name found under any catalog type; not found when the name appears only as a type; empty index.
- [ ] `RouteNotFound.test.tsx` — 404 code, default title/body, default and overridden action.
- [ ] `StorageNotFound.test.tsx` — copy per `reason`, undefined-`reason` fallback, action targets the project overview, and the props-spread regression guard.
- [ ] Guard tests assert the `reason` carried by every `notFound()`, not just that one was thrown.
- [ ] `buildNavSections.test.ts` — new positive case: Ceph registered as `{type:"object-store",name:"ceph"}` still yields the Ceph nav item (D9 anchor).
- [ ] `setupRouterAnalytics.test.ts` — unknown provider does not leak into the action name; existing swift/ceph substitution tests pass unmodified (D12, scope trimmed — the `metadata.notFound` cases are gone with the flag).
- [ ] List route: notFound for invalid provider, unavailable provider, storageType mismatch; still redirects for no-object-store; redirect never called on notFound branches.
- [ ] Objects route: notFound for invalid/unavailable provider; still redirects for storageType mismatch (preserving `containerName`); still redirects for no-object-store.
- [ ] Both routes: `beforeLoad` issues exactly one query, returns `{ availableServices }`; redirect wins over notFound even when both conditions are invalid; `loader` issues zero tRPC queries.
- [ ] Pre-existing tests passing untouched: `BucketTableView.test.tsx`, `SideNavBar.test.tsx`, both ErrorBoundary-reset tests, both objects-route render describes. (`buildNavSections.test.ts` and `setupRouterAnalytics.test.ts` keep every existing case unmodified and only gain new ones.)
- [ ] ~~The objects route's "Canonical storageType enforcement" block still exercises canonicalization after its fixture is updated — i.e. its ceph cases throw a redirect, not a notFound.~~ **Superseded by the D3 reversal:** the block's ceph/swift mismatch cases now assert `notFound` with `reason: "storage-type-mismatch"` and that `redirect` was never called. The fixture change (registering Ceph in the catalog rather than relying on the deleted flag) still stands — without it those cases die at the availability check and never reach the storageType comparison.

**Integration:** `pnpm --filter @cobaltcore-dev/aurora test` fully green; `pnpm --filter @cobaltcore-dev/aurora build` succeeds. (The import-cycle worry from the previous revision is moot under D7 — the shared modules live in `client/utils/`, so nothing imports upward out of a route subtree any more.)

**Manual verification** (dashboard running, logged in, real project):
1. `/storage/swift/containers`, `/storage/ceph/buckets` — unchanged.
2. `/storage/swift/buckets`, `/storage/ceph/containers` — 404, **with header/side nav/footer/breadcrumb still visible** (compare against `/nonsense`, which shows the shell-less root 404).
3. `/storage/nonsense/containers`, `/storage/__proto__/containers` — 404, not a rendered list.
4. `/storage/ceph/containers/<bucket>/objects` — ~~**redirects** to `.../ceph/buckets/<bucket>/objects` (asymmetry intact)~~ → **404 in-shell**, same as the list route (D3 reversed 2026-09-16).
5. `/storage/nonsense/buckets/<bucket>/objects` — 404 in-shell.
6. "Go to Project" button on the 404 → lands on project overview.
7. Nav + project-overview cards + bucket-row/object-browser delete flows → all still land on canonical URLs.
8. DevTools Network: on an in-project storage navigation `auth.getAvailableServices` fires **once** (was twice); on a cold load / hard refresh it fires **twice** — the second one is `$projectId.tsx`'s own loader, out of scope (D8). Do not read the cold-load count as a regression.
9. On a 404 page: the browser tab does **not** read "Storage Overview", and with an `onTrackEvent` stub wired up, the emitted event's action is `storage.objectstore.list`, not `storage.lolnope.list`.
10. **D6 check, the one that matters for Ceph go-live:** in a project whose catalog carries Ceph as `object-store-ceph` and has no Swift at all, the Ceph nav entry now actually opens `/storage/ceph/buckets` instead of bouncing to the project overview. If no such project is reachable, fake it by trimming the `getAvailableServices` response in DevTools — this path is the reason `CEPH_FALLBACK_ENABLED` existed and must be seen working before the flag is deleted.

## Acceptance Criteria

- [ ] Unknown `$provider` on either storage route → 404 (no redirect, no list).
- [ ] `swift`/`ceph` provider unavailable for the project → 404 on either route.
- [ ] Services are resolved by name across all catalog types; Ceph registered as `object-store-ceph` is reachable from the guard, and Ceph registered as `object-store` appears in the nav (D6/D9).
- [ ] `CEPH_FALLBACK_ENABLED` is gone from the codebase — `grep -rn "cephFallbackEnabled\|CEPH_FALLBACK" packages/` returns nothing.
- [ ] No module outside `client/utils/serviceCatalog.ts` indexes the service catalog by type.
- [ ] Each `notFound()` carries a `reason`, and the 404 copy differs for `storage-type-mismatch` vs the two provider reasons (D10).
- [ ] No user-controlled URL segment reaches an analytics action name (D12). The analytics payload gains no new field.
- [ ] The 404 tab title never reads `Storage Overview` — a page that does not exist (D13).
- [ ] `$storageType` not canonical for the provider → 404 on the **list** route; **redirect** to canonical (same `containerName`) on the **objects** route.
- [ ] Neither `swift` nor `ceph` resolvable in the catalog by name → redirect to project overview from both routes, and this redirect wins over any 404 condition.
- [ ] 404 renders inside `AuroraLayout` + breadcrumbs, using Juno `Status status="error" code={404}`.
- [ ] `notFound()` thrown only from `loader`s; the no-service `redirect` thrown from `beforeLoad`.
- [ ] `STORAGE_TYPE_BY_PROVIDER` is the only place the mapping is written; all 5 previously-hardcoded call sites consume it.
- [ ] `checkServiceAvailability` no longer exists in either location.
- [ ] The leaf storage routes issue `auth.getAvailableServices` exactly once (in `beforeLoad`) and zero times in `loader`: cold load 3 → 2, in-project navigation 2 → 1 (D8).
- [ ] i18n catalogs regenerated for `en`/`de`, no drift.
- [ ] A `patch` changeset for `@cobaltcore-dev/aurora` present.
- [ ] No regressions: `BucketTableView.test.tsx`, `SideNavBar.test.tsx`, ErrorBoundary-reset tests and objects-route render tests pass **without modification**; `buildNavSections.test.ts` passes with its existing cases unmodified, gaining only the new D9 positive case.
- [ ] `typecheck`, `lint`, `test`, `format:check` all pass.
- [ ] Working tree modified and **uncommitted**; nothing pushed.
- [ ] PR description explicitly calls out (a) that the objects route no longer silently rewrites a mismatched `storageType` to the canonical path — it 404s like the list route (D3 reversed), so a hand-edited or stale `/storage/ceph/containers/<bucket>/objects` now errors instead of redirecting; (b) that provider lookup moved from catalog type to service name, matching the backend, which is what made `CEPH_FALLBACK_ENABLED` removable — including the note that a deployment with Ceph genuinely absent from the catalog now gets an honest 404 instead of a page whose every request fails; (c) that a bookmarked non-canonical list URL (`/storage/swift/buckets`) now 404s instead of rendering, and a bookmarked unavailable-provider URL 404s instead of redirecting to the other provider; and (d) the analytics change — an arbitrary URL segment can no longer become an analytics action name, which matters more now that such a URL stays on screen instead of redirecting away.

## Open Questions

None blocking — all prior open questions (404 UI, provider 404 scope for both routes, no-service edge case, constant rollout breadth, delivery) were resolved with the user on 2026-09-15. Two things surfaced during dev-planner's verification pass, resolved inline rather than escalated:

1. The objects route's `notFoundComponent` also needed upgrading (D1 named only the list route, but D2 gives the objects route `notFound()` branches too) — both routes now share `StorageNotFound`.
2. The installed router version does technically support `notFound()` from `beforeLoad` (`beforeLoadNotFound`) — the plan still keeps every `notFound()` in a `loader`, matching the repo's documented `$serviceType.tsx` contract and staying version-proof.

### Raised and resolved by the audit pass, block C (route wiring)

All three are now decided and have implementation steps — kept here for the PR description, since two are behavior changes a reviewer will not expect from an issue titled "invalid storage type should 404".

1. **Analytics fired on the 404, with a user-controlled event name.** Resolved by D12 / step 6b. The cardinality half is the part worth calling out in the PR: it predates this change (an invalid provider redirects only *after* the navigation resolves, so the event already escapes today), but this PR makes such URLs stay on screen, so it stops being theoretical.
2. **`head` title on the 404.** Resolved by D13 / step 4.6 — verified that `head` really does run for the not-found boundary (`load-matches.js:573,585`), so this was a real wrong title, not a hypothetical one.
3. **Breadcrumb on the 404.** Confirmed acceptable as-is; only the hardcoded provider ternary in `$storageType.tsx` moves to the shared constant (D13 / step 6b).

## Integration with PR #1304 (centralized error handling) — recorded 2026-09-16

PR [#1304](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1304) `feat(dashboard): centralize client error handling`
(author: vlad-schur-external-sap, branch `vlad-centralized-error-handling`, 94 files, +837/−527) was OPEN on 2026-09-16
and is expected to merge before this branch. It overlaps this plan directly. Everything below was verified against
`origin/vlad-centralized-error-handling` at `aac6f9ed`, which branches from the same base as this work (`6f4c35de`,
0 commits behind `main`).

**Decision: do NOT merge their branch into `kiryl-storage-type-404-1081`.** The repo uses squash merges
(`git log --merges origin/main` is empty; every PR lands as one commit tagged `(#NNNN)`), so their 7 commits will
reach `main` as a single new SHA. Merging their branch now would put commits into our history that never appear in
`main`, and the eventual rebase would then see the same content arriving from two unrelated ancestries —
duplicate-change conflicts across all 94 files instead of the 5 below. Wait for the squash, then
`git rebase origin/main` (or merge `main` in) once.

### Conflicts to expect (measured, not guessed)

Dry run via `git merge-tree --write-tree $(git stash create) origin/vlad-centralized-error-handling` — working tree
untouched. Exactly five:

| File | Kind |
| --- | --- |
| `…/storage/$provider/$storageType/$containerName/objects/index.tsx` | real, ~30 lines — see recipe |
| `locales/{en,de}/messages.po`, `locales/{en,de}/messages.ts` | generated — discard both sides, rerun `pnpm check-i18n` |

`…/storage/-components/Ceph/Objects/ObjectBrowserView.tsx` is touched by both sides but auto-merges (their edits at
lines 6 and ~592, ours at 59/76/983). `_auth/projects/$projectId.tsx` is theirs only (import path change).
`$projectId/index.tsx`, `BucketModals.tsx`, `BucketTableView.tsx` are ours only.

### What #1304 gives us for free

- **`defaultNotFoundComponent: ServiceLevelDefaultError` in `client/router.ts`.** This closes the unstyled
  `<p>Not Found</p>` fallthrough on unmatched in-project paths (`/projects/<id>/storag`) that this plan left as a
  known pre-existing gap. **Do not add `defaultNotFoundComponent` or `notFoundMode` here** — it arrives with #1304.
- **`components/Errors/RouteIdLevelDefaultError.tsx`** is functionally our `components/Error/RouteNotFound.tsx`:
  same `Status code={404}`, same optional title/body/action, same `useParams({ strict: false })` → project-home
  button. Prop names differ (`errorTitle`/`errorDescription` vs `title`/`body`).
- **Folder rename `components/Error/` → `components/Errors/`.** The old folder does not exist on their branch.

### Post-merge cleanup (do after #1304 is in `main`, in the same PR)

1. ~~Delete `client/components/Error/RouteNotFound.tsx` and `RouteNotFound.test.tsx`.~~ **Done ahead of the merge on
   2026-09-16** — see the log entry below. ~~`components/Error/` now holds only the pre-existing `RouteError`, which is
   #1304's to move.~~ **Superseded 2026-09-17**: the folder rename was done on this branch too (see the
   `ServiceLevelDefaultError` entry at the end), so `components/Error/` no longer exists here either.
2. Repoint `StorageNotFound.tsx` at `@/client/components/Errors/RouteIdLevelDefaultError`: replace its inlined
   `<Status status="error" code={404} title=… body=… action=… />` with
   `<RouteIdLevelDefaultError errorTitle=… errorDescription=… action=… />`, keeping the `reason` ternary and the
   `Go to Project` button exactly as they are. No behavior change — `StorageNotFound` overrides every default either
   component offers. D7 (a 404 rendered in-shell as a Juno `Status` with `code={404}`) survives; only the component
   supplying that markup moves upstream. The `renders the 404 status code` test then covers the shared component's
   output instead of our own.
3. Resolve `objects/index.tsx` as follows — their side and ours touch the same two regions:
   - **imports**: keep ours (`requireObjectStoreService`, `validateObjectsAccess`, `ServiceInfo`,
     `NotFoundRouteComponent`, `StorageNotFound`) and drop their `checkServiceAvailability` import — that helper no
     longer exists after this plan's Step 2. Their `RouteIdLevelDefaultError` import is only needed if their
     `ObjectStorageErrorComponent` is kept (see below).
   - **`beforeLoad`/`loader`**: keep ours verbatim. Their side still calls the deleted `checkServiceAvailability`,
     so a naive "take theirs" will not typecheck.
   - **`notFoundComponent`**: take *their* action semantics, our component. Their `ObjectStorageErrorComponent`
     navigates back to the container/bucket list ("Back to Buckets"/"Back to Containers"), which beats our
     "Go to Project" on this route. But it selects the label via a hardcoded `provider === "ceph"` — the exact
     sixth hardcoded pairing D6/D8 removed. Reimplement it over `isStorageProvider`/`storageTypeFor` from
     `@/client/utils/storageProviders`, keeping `StorageNotFound`'s `reason` plumbing.
   - **`errorComponent`**: theirs is new and unopposed — keep it.
4. Rerun `pnpm check-i18n`, then the full gate.

### Green baseline before the merge (2026-09-16, branch at 27 uncommitted files)

`pnpm typecheck` 7/7 · `pnpm lint` 4/4 · `pnpm format:check` clean · `pnpm --filter @cobaltcore-dev/aurora test`
**228 files / 5671 tests passed**. Any red after the rebase is therefore attributable to the merge, not to this work.

### Feedback worth leaving on #1304 while it is still open

- ~~`ServiceLevelDefaultError` renders `Status` with `code={404}` and an action but **no `title` and no `body`** — the
  user sees a bare number and a button.~~ **Wrong — corrected 2026-09-17**, see the last section: Juno's `Status`
  fills both from its own code table. The real objection is that those defaults are hardcoded English, outside
  Lingui, while every other 404 in the app goes through `t``.
- `ObjectStorageErrorComponent` hardcodes `provider === "ceph"` (see cleanup item 3).

## Manual verification log

Stand: `local-mock-backend` (127.0.0.1:8090) + dashboard on localhost:4500, project
`11111111111111111111111111111111`. A `MOCK_OBJECT_STORE` env switch was added to
`local-mock-backend/fake-backend.js` (`both` default / `ceph-only` / `swift-only` / `none`) so the
catalog shapes this plan depends on can be reproduced locally instead of hand-trimming responses in
DevTools. That file lives outside the repo and ships with nothing.

### 2026-09-16 — Testing Plan item 10 (D6 / Ceph go-live): **PASS**

Catalog served: `identity, compute, image, network, dns, pca, object-store-ceph:ceph` — Ceph present
only under type `object-store-ceph`, **Swift absent entirely** (verified by reading the token catalog
straight off the mock, not from the UI).

| Check | Result |
| --- | --- |
| Project overview shows the Object Storage (Ceph) card; no Swift card | PASS |
| Clicking it opens `/storage/ceph/buckets` with the bucket list (no bounce to project overview) | PASS |
| Cold direct URL to `/storage/ceph/buckets` opens the same list (`beforeLoad` without a warm router context) | PASS |
| `/storage/swift/containers` → in-shell 404, not a redirect | PASS |

What this proves that no unit test could: `hasServiceByName` resolves Ceph by **name** while
`serviceIndex["object-store"]["ceph"]` is empty, so `requireObjectStoreService` no longer throws the
redirect that `CEPH_FALLBACK_ENABLED` used to paper over. **Deleting the flag is justified against a
live stand**, which was the one item in this plan that unit tests could not cover.

It also closes the acceptance criterion "`swift`/`ceph` provider unavailable for the project → 404 on
either route" for the list route: with Swift out of the catalog, `/storage/swift/containers` renders
`StorageNotFound` with `reason: "provider-unavailable"` instead of redirecting.

### 2026-09-16 — no-object-store project (`MOCK_OBJECT_STORE=none`): **PASS**

Catalog served: `identity, compute, image, network, dns, pca` — no object-store service of any kind.

| Check | Result |
| --- | --- |
| Project overview shows no Object Storage card (neither provider); side nav likewise | PASS |
| `/storage/ceph/buckets` → redirect to project overview (not 404) | PASS |
| `/storage/swift/containers` → redirect to project overview (not 404) | PASS |
| `/storage/nonsense/containers` → redirect to project overview, **not** 404, though both conditions hold | PASS |

The last row is the one that matters: the `redirect` thrown from `beforeLoad` wins over the
`notFound()` the `loader` would have thrown for the invalid provider. Confirms the acceptance
criterion "neither swift nor ceph resolvable by name → redirect from both routes, and this redirect
wins over any 404 condition", and confirms the lifecycle split (redirect in `beforeLoad`, `notFound()`
in `loader`) holds at runtime, not just in the unit tests.

### 2026-09-16 — Testing Plan items 1–4 and the D3 reversal

Items 1 (canonical URLs unchanged), 2 (`swift/buckets` and `ceph/containers` → in-shell 404, visibly
different from the shell-less root 404 at `/nonsense`) and 3 (`nonsense`/`__proto__` providers → 404
with the *other* copy, proving `reason` reaches the component): **PASS**.

Item 4 behaved as planned — both `/storage/ceph/containers/<bucket>/objects` and
`/storage/swift/buckets/<container>/objects` redirected to the canonical path — and seeing it next to
item 2 is what killed D3. Every wrong storage noun 404s, except this one route, which silently rewrote
the URL. **D3 reversed the same day; see the entry at the top of the decisions list for the reasoning.**

Change list (all in the working tree, still uncommitted):

- `serviceAvailability.ts` — `validateStorageListAccess` and `validateObjectsAccess` collapsed into a
  single `validateStorageAccess(availableServices, { provider, storageType })`. `projectId` and
  `containerName` leave the signature; they existed only to build the redirect target. The file no
  longer has two near-identical exports whose only difference was the last branch.
- `$storageType/index.tsx`, `…/objects/index.tsx` — both call the shared guard. The comment above the
  objects route's `notFoundComponent` claimed "a storageType mismatch redirects instead (D3)" and now
  states the three reasons the boundary actually fires for.
- `objects/index.test.tsx` — the "Canonical storageType enforcement" block's two mismatch cases flip
  from `toThrow("Redirect to: …")` to `notFound` + `reason: "storage-type-mismatch"` + `redirect` never
  called; the loader-level case flips the same way; one case ("never redirects, whatever the
  containerName") was deleted rather than rewritten — `containerName` is no longer a parameter, so the
  signature itself is the proof, and TS rejected the literal. Test count 5671 → 5670.
- `$storageType/index.test.tsx` — rename only.
- `.changeset/storage-provider-404.md` and this plan's D3 / acceptance criteria / manual item 4.

Gate after the change: `typecheck` clean, `lint` 4/4, `format:check` clean,
**228 files / 5670 tests passed**.

### 2026-09-16 — D12 scope trimmed: `metadata.notFound` removed

Questioned during verification: why did the analytics file change at all, and was it required? Split
verdict, recorded because the answer was not the same for both halves of D12:

- **`isStorageProvider(provider)` guard — kept.** Required, and required *because of* this PR: the raw
  `$provider` segment is interpolated into the emitted action name, and before this change an invalid
  provider redirected away, so a junk name escaped only in passing. Now the 404 stays on that URL, so
  anyone editing the address bar mints `storage.<anything>.list` indefinitely — unbounded cardinality
  in the `action` dimension, user-controlled, forwarded to the host's `onTrackEvent`.
- **`metadata.notFound = true` — removed.** Not required by #1081. Its value depends entirely on a
  consumer outside this repo: `metadata` goes to the host app's `onTrackEvent`, nothing here reads the
  field, and `packages/aurora/README.md` does not document it. Adding a field to a public analytics
  payload on the assumption that some sink knows to look for it is scope the ticket did not ask for.

Removed with it: the two test cases (`sets metadata.notFound…`, `does not set… for a successful
match`) and the `status?: string` widening of the test's mock-router type, which existed only for them.
Test count 5670 → 5668. `typecheck` 7/7, `lint` 4/4, `format:check` clean, 228 files green.

Also updated: the changeset's analytics paragraph, D12 itself, step 6b, the unit-test checklist, manual
item 9, the acceptance criterion, and PR-description bullet (d).

### 2026-09-16 — `RouteNotFound` dropped, inlined into `StorageNotFound`

Questioned during verification: #1304 ships `components/Errors/RouteIdLevelDefaultError.tsx`, so is our
`components/Error/RouteNotFound.tsx` going to be replaced? It would have been duplicated, not replaced —
git deletes nothing on merge, so the branch would have left a stray one-file `Error/` folder beside the
new `Errors/`. Removed now instead of after the merge, because the component turned out not to earn its
place on its own terms:

- **One consumer** (`StorageNotFound.tsx`), which overrode `title`, `body` **and** `action`.
- Its only surviving default — the `Go to Projects` fallback when `projectId` is missing — is unreachable
  from the storage routes, since `projectId` is a segment of their own path. The component's five-case
  test file tested exactly those dead defaults.

So D7's generic component was a wrapper whose every default was dead, about to be duplicated by #1304.
`StorageNotFound` now renders the Juno `Status` directly (~15 lines, same markup, same copy, same
`code={404}`), keeping an unreachable `Go to Projects` branch only so the component can never render an
actionless 404 if it is ever mounted outside `/projects/$projectId`. D7's acceptance criterion is about
what renders — in-shell, Juno `Status status="error" code={404}` — not about where the JSX lives, so it
still holds.

`renders the 404 status code` was carried over from the deleted test file into `StorageNotFound.test.tsx`
so that coverage does not vanish with the component. Working tree 27 → **25 files**. Gate: `typecheck`
7/7, `lint` 4/4, `format:check` clean, `check-i18n` no drift (the four new strings are the only additions;
`Go to Projects` and `Page Not Found` already existed on `main` for the root `PageNotFound`),
**227 files / 5664 tests passed**.

### 2026-09-17 — provider/storage-type literals extracted into named constants

`storageProviders.ts` previously exported only the `STORAGE_TYPE_BY_PROVIDER` map; the words `"swift"`,
`"ceph"`, `"containers"` and `"buckets"` were still written out by hand at every comparison, switch case
and `hasServiceByName` call. Added two named constants and rebuilt the map from them:

```ts
export const STORAGE_PROVIDER = { SWIFT: "swift", CEPH: "ceph" } as const
export const STORAGE_TYPE = { CONTAINERS: "containers", BUCKETS: "buckets" } as const
export const STORAGE_TYPE_BY_PROVIDER = {
  [STORAGE_PROVIDER.SWIFT]: STORAGE_TYPE.CONTAINERS,
  [STORAGE_PROVIDER.CEPH]: STORAGE_TYPE.BUCKETS,
} as const
```

The computed keys keep their literal types under `as const`, so `StorageProvider` / `StorageType` are
derived unchanged and no call site's inference moved (`typecheck` green).

Call sites converted: `serviceAvailability.ts` (both `hasServiceByName` lookups, the `provider === "swift"`
availability pick), `buildNavSections.ts`, `$projectId/index.tsx`, `$storageType.tsx`, the list route and
the objects route (breadcrumb/title ternaries and both `switch (provider)` blocks), the three Ceph views'
`asStorageProvider(provider, "ceph")`, and `ContentHeader.tsx`.

**Deliberately left as literals** — they are not this vocabulary:

- Nav / `enabledServices` **service keys** `"containers"` and `"ceph-containers"` (`staticData.service`,
  `isEnabled(...)`, `SideNavBar`'s `activeService`). These only textually overlap: Ceph's nav key is
  `"ceph-containers"`, never `"buckets"`. Substituting `STORAGE_TYPE.CONTAINERS` there would read as if
  the two namespaces were one. Noted in a comment at each site and in `STORAGE_TYPE`'s own doc block.
- i18n copy (`<Plural other="buckets">`), CSS class names (`className="buckets"` / `"containers"`), and
  prose in comments.

`ContentHeader.tsx` was not otherwise touched by this branch — one line + one import, flagged as the only
file the refactor adds to the PR's diff.

Gate: `typecheck` green, `lint` clean, `format:check` clean, **227 files / 5664 tests passed**. Working
tree 25 → **26 files**. Changeset paragraph on the centralized mapping rewritten to name all three
constants and to record the nav-key carve-out.

**Follow-up deferred — `NAV_SERVICE` constants (out of scope for #1081).** Questioned during review: why
does `isEnabled("containers")` keep a literal? Because it belongs to the nav-service-key set, not to
`STORAGE_TYPE` — but that is a reason for it to get its **own** constant, not for it to stay a magic
string. The full set is documented public API — `packages/aurora/README.md:177` lists
`images · flavors · securitygroups · floatingips · containers · ceph-containers · pca` (seven keys,
not six: `pca` is a service extension and has no route of its own). 27 occurrences across 20 files (`staticData.service` on every route, `isEnabled(...)`, the overview cards'
`service:`, `SideNavBar`'s `activeService`), none of them constants today. It is also public API —
`AuroraApp` takes `enabledServices?: string[]` and `RouteInfo.service` is `z.string()`, so the natural
version of this change is a constant **plus** a union type, so a typo in `staticData` fails typecheck.

Must be done for all six keys at once — converting only the two storage keys leaves a set that is half
constants and half literals with no stated rule. That pulls in `compute/images`, `compute/flavors` and
`network/*`, which have nothing to do with #1081, so the diff would stop reading as "404 on an invalid
provider". Decision (2026-09-17): leave the literals, do `NAV_SERVICE` as its own refactor later.

### 2026-09-17 — Testing Plan item D re-check after the D3 reversal: **PASS**

The objects route previously redirected a non-canonical `storageType` to the canonical path; D3 was
reversed so it 404s like the list route. Re-ran all four URLs against the mock (`MOCK_OBJECT_STORE=both`,
project `11111111111111111111111111111111`), base
`http://localhost:4500/projects/<id>/storage`:

| URL tail | expected | result |
| --- | --- | --- |
| `/ceph/containers/demo-bucket-1/objects` | 404 "This address is not valid…" | PASS |
| `/swift/buckets/demo-container-1/objects` | 404 "This address is not valid…" | PASS |
| `/nonsense/buckets/demo-bucket-1/objects` | 404 "Object Storage Not Found" | PASS |
| `/ceph/buckets/demo-bucket-1/objects` | opens normally (control) | PASS |

The load-bearing observation was the **address bar**, not the copy: on the first two URLs it stays
unchanged. Under the pre-reversal behavior it silently rewrote itself to `/ceph/buckets/...`. Confirmed
no redirect on any of the four. Both 404s render in-shell (side nav + breadcrumbs), not as a full-page
takeover — D7 holds on the objects route too, which the unit tests cannot show.

Item D is now the same rule on both storage routes, with no route left as an exception.

**Correction (2026-09-17), same follow-up.** Two details found while explaining `ContentHeader`'s
`currentService` mapping, both affecting the deferred `NAV_SERVICE` work:

- The key set has **seven** members, not six — `README.md:177` and `:204` also list `"pca"`. Any constant
  or union type must cover it, and the README's two lists are a third and fourth place the set is written
  out by hand.
- The keys are **public API**, not an internal detail: hosts pass them in `enabledServices`, and the
  `serviceBadge` / `servicePageActions` / `serviceBanner` slots receive one as `auroraContext.currentService`.
  So the union type has to be exported, and renaming a key would be a breaking change.

Also worth recording, since it is the reason `ContentHeader` needs a mapping at all: all three storage
routes declare `service: "containers"` in `staticData`, because the `$provider/$storageType` tree is one
set of files serving both providers and cannot statically know which one is loaded. `ContentHeader`
repairs the Ceph case from the `$provider` URL segment. The 404 path does not need the repair —
`StorageNotFound` renders a bare `Status` and never mounts `ContentHeader`.

---

## 2026-09-17 — `beforeLoad` collapsed into `loader` on both storage routes

Triggered by the question "why is the same code in two files?". The answer turned out to be that it was
already in two files before #1081 — both routes had their own `notFoundComponent`, their own `beforeLoad`
calling `checkServiceAvailability`, and their own dead `loader` that re-queried `getAvailableServices` and
threw the result away. #1081 changed what the guard *does*, not where it lives. The two routes are
siblings under the `$storageType.tsx` layout (`routeTree.gen.ts:639-652` — both name `StorageTypeRoute`
as `parentRoute`), so neither can inherit the other's guard; the objects URL is independently typeable.

**What was wrong in our own comment.** `serviceAvailability.ts` claimed `requireObjectStoreService` was
"the only availability check safe to run from `beforeLoad` — a `redirect` thrown here always wins over a
`notFound()` thrown later from a `loader`". Under scrutiny that does not hold: two sequential calls in
one `loader` already give the redirect priority, because the second never runs.

**Verified on a live router** before changing anything — a throwaway probe built a real route tree with
`createRouter` + `createMemoryHistory` on the installed `@tanstack/react-router@1.168.22`, with no mocking
of `redirect`/`notFound` (the existing suites mock `redirect`, so they could not answer this):

| | scenario | result |
|---|---|---|
| A | `redirect` from `loader`, no object-store | navigated to the fallback route |
| B | `notFound` from `loader`, invalid provider | `notFoundComponent` rendered |
| C | both guards in one `loader`, both would fire | redirect won; 404 never rendered |
| D | happy path | component rendered |
| E | current `beforeLoad` + `loader` split, same input as C | identical to C |

The probe was deleted after reading the result.

**Change.** Both routes now have a single `loader`:

```ts
loader: async ({ context, params }) => {
  const { trpcClient } = context
  const availableServices = (await trpcClient?.auth.getAvailableServices.query()) ?? []
  requireObjectStoreService(availableServices, params)   // redirect
  validateStorageAccess(availableServices, params)       // notFound
},
```

`beforeLoad` is gone from both. Collapsing can only go this direction: `notFound()` thrown from
`beforeLoad` is not intercepted by `notFoundComponent`, so that half cannot move up.

Side effect worth noting: the `as unknown as { availableServices: ServiceInfo[] }` cast in both files is
gone. It existed *only* because this router version does not surface `beforeLoad`'s return value in
`loader`'s inferred context type. No `beforeLoad` → no cast → `ServiceInfo` no longer imported by either
route. Checked that nothing else read `availableServices` out of these routes' context (grep across
`client/`): both are leaves, nobody did.

**Divergence from the house pattern, recorded deliberately.** Six other routes
(`compute/flavors.tsx:40`, `compute/images.tsx`, `network.tsx`, the two `$…Id` detail routes) still do
availability-redirects from `beforeLoad`. They only ever throw `redirect`, never `notFound`, so they have
no reason to move; the storage routes are the only ones needing both. Not touched.

**Gates:** `pnpm typecheck` ✅ · `pnpm lint` ✅ · `pnpm format:check` ✅ · `pnpm test` ✅ (aurora
5664 / signal-openstack 177 / policy-engine 320, 0 failures).

**Tests rewritten.** The "Route lifecycle ordering" block in both route test files tested
`Route.options.beforeLoad` directly. Rewritten against the single loader, keeping every original
intent and adding an async `expectNotFoundAsync` helper (the loader is now async, so its throws arrive as
rejections). The one test that lost meaning was "loader … makes zero tRPC calls" — the loader is now the
thing that fetches; it became "throws notFound for an invalid provider once the project does have object
storage", and the once-per-navigation guarantee (D8) moved into its own explicit assertion.

**Manual verification item 8 is now redundant as written** — the D8 count is asserted in unit tests
against the real route object. Left in the plan for the record; not worth doing by hand in DevTools,
especially since `httpBatchLink` merges same-tick calls into one HTTP request and makes row-counting in
the Network panel misleading anyway.

### Follow-up, same day — `guardStorageRoute` composer

Removing `beforeLoad` left the two-function split without its reason: the split was made *because*
`notFound()` could not be thrown from `beforeLoad`, so the redirect half had to live in a different hook.
With both in one loader, the two functions had exactly two production call sites, both calling both, in
the same order, with the same arguments — and the required ordering was documented only in three prose
comments ("Must run before…", "Assumes … already ran", twice).

Not merged into one function: they answer genuinely different questions — `requireObjectStoreService` is
"does this project have object storage at all?" (a project-capability question → redirect to the
overview), `validateStorageAccess` is "is this URL a valid address?" (→ 404). Both names earn their keep.

Added a composer instead, `guardStorageRoute(availableServices, params)`, which both routes now call
instead of the pair. The ordering lives inside it, so a future third storage route cannot get it wrong;
the three prose warnings collapsed to one sentence. Also fixed a stale comment on
`requireAvailableProvider` that still referenced `validateStorageListAccess` / `validateObjectsAccess`,
functions this branch had already deleted.

Cost was as predicted: no existing test needed changing (they import the two halves directly and still
do). Added three tests on the composer itself, which are the ones that actually lock the ordering —
no-storage + invalid provider must redirect rather than 404, has-storage + wrong storageType must fall
through to the 404, and a canonical pairing must not throw.

**Gates:** `pnpm typecheck` ✅ · `pnpm lint` ✅ · `pnpm format:check` ✅ · `pnpm test` ✅
(aurora 5667 / signal-openstack 177 / policy-engine 320, 0 failures).

---

## 2026-09-17 — BUG FOUND IN THIS BRANCH: `StorageNotFound` never saw its `reason`

Found by the user in the browser, not by the suite: `/storage/swift/buckets` rendered "Object Storage Not
Found / This object storage service does not exist or is not available for this project." — the
`provider-unavailable` copy — when D10 says a non-canonical pairing must read "Page Not Found / This
address is not valid for this object storage service."

**Root cause.** `StorageNotFound` declared `reason?: StorageNotFoundReason` as a flat prop, on the
strength of a comment in this branch claiming `notFound({ data })` spreads `data` into the component's
props. It does not. Read from the installed `@tanstack/react-router@1.168.22`:

- `router-core/not-found.js` — `notFound(options)` tags `options` with `isNotFound` and returns *that
  object*; `data` stays a field on it.
- `react-router/Match.js:158` — `renderRouteNotFound(router, route, match.error)`, i.e. the whole error.
- `react-router/renderRouteNotFound.js` — `jsx(route.options.notFoundComponent, { ...data })` where its
  `data` parameter *is* the error object.

So the component received `{ data: { reason }, isNotFound: true }`. Its `reason` prop was always
`undefined`, `isBadUrl` was always `false`, and **all three notFound reasons collapsed into one message**.
The "Page Not Found" branch had never rendered.

**Why the suite missed it — the part worth remembering.** `StorageNotFound.test.tsx` rendered
`<StorageNotFound reason="storage-type-mismatch" />`, passing the prop by hand in a shape the router never
produces. It even carried a test named "reads a flat `reason` prop, not `data.reason` (props-spread
regression guard)", which asserted the bug and locked it in. A guard written from an assumption about a
dependency, instead of from the dependency, is worse than no guard.

**Fix.** Component now takes `data?: { reason?: StorageNotFoundReason }` and reads `data?.reason`; the
comment above it cites the three files above instead of asserting a contract. `StorageNotFound.test.tsx`
now builds its props with the real `notFound()` and spreads the resulting error exactly as
`renderRouteNotFound` does (helper `renderAsRouterWould`), so the prop shape cannot drift from the router
again; the mock of `@tanstack/react-router` keeps the real `notFound` via `importActual`. The inverted
guard is replaced by one asserting both directions — spread error honoured, flat `reason` ignored.

**Gates:** `pnpm typecheck` ✅ · `pnpm lint` ✅ · `pnpm format:check` ✅ · `pnpm test` ✅ (aurora 5667 /
signal-openstack 177 / policy-engine 320, 0 failures).

**Still to confirm in the browser** (the unit tests cannot): `/storage/swift/buckets` must now read "Page
Not Found", while `/storage/nonsense/containers` and an unavailable provider keep "Object Storage Not
Found".

---

## 2026-09-17 — `$containerName`: a missing resource stops being a banner

Scope extension, decided by the user ("допиливаем в текущую"): #1081 proper is about the two URL-shape
params, but the third dynamic segment was left behaving worse than either. Folded into this branch rather
than a separate issue.

### What it did before

`$provider` and `$storageType` can be judged from the URL alone. `$containerName` cannot — only the API
knows whether the container is there. Nothing asked it, so the detail page mounted anyway and every part
of it discovered the same 404 independently:

| Provider | Requests fired for a name that doesn't exist | What the user saw |
|---|---|---|
| Ceph | `containers.list`, `versioning.getStatus`, `bucketPolicy.get`, `cors.get`, `lifecycle.get`, `objects.list` (version check), `objects.list` (listing), `storage.canUser` | Header with the bucket name, tabs, and a full action menu (Empty, Delete, versioning) over an error banner printing the raw `Failed to list objects — bucket: … ` |
| Swift | `getContainerMetadata` (header), `listObjects` | Header banner with the raw `Resource not found container: …`, plus #1142's toast and a bounce back to the list |

Three behaviours for one situation, none of them a 404, two of them printing server error text.

### Decisions

- **D14 — the probe lives in the loader, and only a `NOT_FOUND` answer counts.** One request settles
  existence before anything renders. Anything that is *not* a NOT_FOUND — a permission denial, a 500, a
  dead network, and in particular Ceph's `NO_CEPH_CREDENTIALS` (which arrives as FORBIDDEN) — is
  deliberately let through so the page still renders and reports it. A 404 is a dead end; the credentials
  case has `CredentialPrompt` further down the page and would be unreachable behind one. The copy on the
  404 page still says "does not exist **or is not accessible**", so distinguishing the codes internally
  does not leak existence to the user, which was #1142's original concern.
  A non-tRPC throw (a broken procedure path, a bug in the probe) is rethrown rather than swallowed — an
  early version caught everything and silently rendered the page when the stub was wrong, which the route
  tests then failed to notice.
- **D15 — no redirect.** User's call, and consistent with the rest of this branch: a deep link that
  silently rewrites itself, plus a toast that vanishes in five seconds, is worse than a page that says
  what happened and offers the list. This retires #1142's toast-and-bounce for the "doesn't exist" case
  (it still covers a container that disappears while you are on the page).
- **D16 — a separate component, not a wider `StorageNotFound`.** User's call. Address errors and resource
  errors get different components because their exits differ: "this address is wrong" leads out of storage
  entirely, "this bucket is gone" leads back to the list, which is a page that still works. The route has
  one `notFoundComponent`, so `ObjectsNotFound` dispatches on the reason.
- **D17 — Ceph gets a `head` procedure.** `containers.list` would have answered without server changes,
  but ListBuckets only returns buckets the caller *owns* — a bucket reachable through a policy would have
  read as missing. `HeadBucket` asks about the bucket itself. Cost: `s3ErrorMapper` needed two new rows
  (`NotFound`, `Forbidden`) — a HEAD carries no XML body, so the SDK has no `Code` to read and raises a
  bare status-derived name; without them a missing bucket would have surfaced as a 500.

### Vendored from #1304

The component the user chose, `RouteIdLevelDefaultError`, lives only in PR #1304
(`vlad-centralized-error-handling`), which is still open. Its two files were copied **verbatim** from
`origin/vlad-centralized-error-handling` into `client/components/Errors/`, so when that PR lands the merge
sees identical content on both sides. One deliberate divergence: their
`RouteIdLevelDefaultError.test.tsx` asserts the button reads "Go to Project Home" when there is no
`projectId`, but the component renders "Go to Home" in that branch — the test is red as written. Corrected
here with a comment saying so; **worth reporting on #1304**. The post-merge recipe's item 2 (repoint
`StorageNotFound` at this component) is unaffected.

Note this branch temporarily carried both `components/Error/` (pre-existing `RouteError`) and
`components/Errors/`; resolved later the same day — see the last entry.

### Changes

| File | Change |
|---|---|
| `server/Storage/types/ceph.ts` | `headBucketInputSchema` (permissive name, like every other existing-bucket op) |
| `server/Storage/routers/ceph/containerRouter.ts` | `head` procedure — one `HeadBucketCommand` |
| `server/Storage/helpers/s3ErrorMapper.ts` | `NotFound` → NOT_FOUND, `Forbidden` → FORBIDDEN (bodiless HEAD errors) |
| `.../storage/-components/utils/containerExistence.ts` | **new** — `CONTAINER_NOT_FOUND` + `requireContainerExists` |
| `.../storage/-components/utils/serviceAvailability.ts` | `validateStorageAccess`/`guardStorageRoute` now return the resolved `StorageProvider`, so the loader doesn't re-narrow it for the probe |
| `.../$containerName/objects/index.tsx` | loader: guard → probe; `notFoundComponent` → `ObjectsNotFound` dispatcher |
| `client/components/Errors/RouteIdLevelDefaultError.{tsx,test.tsx}` | vendored (see above) |

Tests: `containerExistence.test.ts` (9, new), four `buckets.head` cases, two `s3ErrorMapper` cases, three
loader cases and four boundary-dispatch cases on the objects route.

**Gates:** `pnpm --filter @cobaltcore-dev/aurora typecheck` ✅ · `lint` ✅ · `pnpm format:check` ✅ ·
`check-i18n` ✅ (1365 messages) · `pnpm --filter @cobaltcore-dev/aurora test` **229 files / 5692 tests
passed**.

### Manual verification still owed

| URL | Expected |
|---|---|
| `/storage/ceph/buckets/no-such-bucket/objects` | "Bucket Not Found" + "Back to Buckets", **one** storage request in Network, no header, no action menu |
| `/storage/swift/containers/no-such/objects` | "Container Not Found" + "Back to Containers", no toast, no bounce |
| `/storage/ceph/buckets/demo-bucket-1/objects` | opens normally (control) |
| `/storage/nonsense/containers/x/objects` | still "Object Storage Not Found", and **no** storage request at all |

### Follow-up, same day — the probe's answer is reused instead of refetched

The first cut of the probe threw its response away, so on Swift the page made the same HEAD twice: once in
the loader (vanilla client) and once in `ContainerHeader` (React Query — separate caches, since
`queryClient` is created in `App.tsx:50` *after* the router and never reaches its context). Closed by
handing the answer down rather than by wiring the two caches together.

- `requireContainerExists` now returns `ContainerProbe { containerInfo?, fetchedAt }` — Swift's HEAD is
  exactly the summary the header needs; Ceph's HeadBucket has no body, so `containerInfo` stays undefined
  there and the request is a genuine (cheap, bodiless) extra one.
- The loader returns it; `ContainerHeader` seeds `getContainerMetadata` with
  `initialData` + `initialDataUpdatedAt`. The timestamp matters: the router can replay loader data it
  cached earlier, and without it React Query would treat a stale answer as freshly fetched and sit on it
  for a full `staleTime` (60s, set globally in `App.tsx`). The modals share that cache entry — the input
  shape is unchanged — so they are seeded too.
- `ContainerHeader` reads it with `useLoaderData({ strict: false })`, **not** `from: <route id>`: the
  component is imported *by* the route module, so naming the route makes the two files circular and
  TypeScript resolves the loader data as `undefined`. One cast, documented in place.

Net request count on opening a container: Swift unchanged from before this whole change (one HEAD, now
made earlier and reused), Ceph +1 HeadBucket and −7 that used to fire only to fail.

**Gates:** typecheck ✅ · lint ✅ · format:check ✅ · check-i18n ✅ · `pnpm --filter @cobaltcore-dev/aurora
test` **229 files / 5697 tests passed**.

### Follow-up — the rest of #1304's `Errors/` folder pulled forward

User's call: finish the folder rather than leave it half-vendored.

- **`ServiceLevelDefaultError.{tsx,test.tsx}`** vendored verbatim from
  `origin/vlad-centralized-error-handling`.
- **`components/Error/` → `components/Errors/`**: `RouteError.{tsx,test.tsx}` moved with `git mv` and given
  the five-line JSDoc #1304 adds, so both files are byte-identical to theirs. The old folder is gone.
- Three import sites updated: `routes/__root.tsx:9`, `routes/_auth/projects/$projectId.tsx:6`,
  `routes/_auth/projects/index.tsx:6`. (A first grep found only the third — it had been truncated by
  `head -20`. Worth remembering: verify a rename by re-grepping for the *old path*, not by trusting a
  capped listing.)
- `ServiceLevelDefaultError.test.tsx` carries the same corrected assertion as
  `RouteIdLevelDefaultError.test.tsx` — same bug, same one-line fix, same note. **Two red tests to report
  on #1304**, not one.

**Wired, same as #1304** (`defaultNotFoundComponent: ServiceLevelDefaultError` in `client/router.ts`;
our copy differs only by an explanatory comment). Note #1304 does **not** touch `__root.tsx`'s
`notFoundComponent: PageNotFound`, so nothing had to be decided about the app's global 404 after all.

I first described this wiring as inert. That was wrong in the part that matters. `renderRouteNotFound.js`
does prefer a route's own `notFoundComponent`, so the root's `PageNotFound` still owns the
matches-no-route case (`/storag/ceph/buckets` is unchanged) — but `defaultNotFoundComponent` is exactly
what covers a route that *throws* `notFound()` without declaring a boundary. There is one today:
`services/$serviceType.tsx:14` throws from its loader and has no `notFoundComponent`, so until now an
unknown service extension URL rendered TanStack's `DefaultGlobalNotFound` — a bare `<p>Not Found</p>` —
plus a dev-mode console warning. That is the concrete improvement this line buys.

Six files in `components/Errors/`, five byte-identical to #1304's, one (RouteIdLevelDefaultError's test)
differing only by the documented assertion fix.

**Gates:** typecheck ✅ · lint ✅ · format:check ✅ · check-i18n ✅ (still 1365 messages — the vendored
component's strings were already extracted) · `pnpm --filter @cobaltcore-dev/aurora test` **230 files /
5699 tests passed**.

### Follow-up — `errorComponent` on the objects route (the one idea worth taking from #1304)

Asked while diffing our objects route against theirs: is there anything in #1304's version of this file
worth adopting? One thing, and it is the idea rather than the code.

Their file wires `ObjectStorageErrorComponent` to **both** `notFoundComponent` and `errorComponent`, so a
failed request renders `RouteIdLevelDefaultError` — a 404 page titled "Resource Not Found". That is a lie
about a 500. Adopted the boundary, rejected the wiring: `errorComponent: ObjectsError`, a three-line
component over the existing `components/Errors/RouteError`, with the root boundary's `safeErrorMessage`
rule (show a `TRPCClientError`'s message, which is ours; hide anything else).

Without it the error reached `__root.tsx:72` (`RootErrorComponent` → `RouteError` inside `AuroraLayout`):
honest copy, but it replaces everything below the root, breadcrumb trail included. Caught at this route's
own match, the parent routes keep rendering and the boundary resets on navigation.

Everything else in their version is either already taken (`RouteIdLevelDefaultError` itself, and the
"Back to Buckets"/"Back to Containers" action, which beat our original "Go to Project" on this route) or
worse than ours (hardcoded `provider === "ceph"` in four places, `beforeLoad` + a dead `loader` that
fetches the catalog twice).

Tests: two on `Route.options.errorComponent` — a plain `Error` renders "Unable to Load Content" and no
404, and a `TRPCClientError` shows the server's own message (matched by regex: `RouteError` concatenates
message and help text into one body string).

**Gates:** typecheck ✅ · lint ✅ · format:check ✅ · check-i18n ✅ (1365, unchanged) ·
`pnpm --filter @cobaltcore-dev/aurora test` **230 files / 5701 tests passed**.

## 2026-09-17 — the partial-URL gap, found by poking the running app

Reported from the browser: `/storage/ceph/buckets/demo-bucket-1/object` (note the missing `s`) showed
"The requested URL does not exist or may have moved." with a button to the project overview.

**Where that text came from.** Not from us. `Status` in `juno-ui-components@9.4.0` carries a built-in copy
table keyed by HTTP code — for 404, `{ title: "Page Not Found", body: "The requested URL does not exist or
may have moved." }` — and fills it in when the caller passes `code` without `title`/`body`, which is
exactly what `ServiceLevelDefaultError` does. So the newly wired `defaultNotFoundComponent` was answering.

**This corrects the feedback note recorded for #1304 earlier in this file** ("renders `Status` with
`code={404}` and an action but no title and no body — the user sees a bare number and a button"). Juno
supplies both. What is genuinely wrong with relying on those defaults is that they are hardcoded English,
outside Lingui — every other 404 in the app goes through `t\`\``.

**The real problem, and D18.** The URL was one segment away from valid, against a bucket that exists, and
the only exit offered was the project overview. A *global* fallback cannot do better — it knows nothing
about storage. So the storage subtree gets its own boundary: `notFoundComponent` on the `$storageType`
layout, the deepest route that still matches such a URL. It also covers the more likely
`/storage/ceph/buckets/demo-bucket-1` — a truncated link, missing the `objects` tail entirely.

**One exit, after trying two.** First cut offered a button straight to the container the URL names plus the
list as a fallback. Confirmed working in the browser, then cut back to the list alone on review: at this
boundary the container name is *not* a route param — there is no `$containerName` route, only the
`$containerName/objects` leaf — so it had to be read back out of `useLocation().pathname`, which made the
button an informed guess that could land on a second 404. With the guess gone, the ~20-line
`containerSegmentFrom` helper and its six tests existed only to vary one sentence of copy, so they went
too. The list is one click from the container anyway. Copy goes through `t``, so unlike the Juno default
it translates.

Untouched by this: `/storage/swift/buckets` (index route, its own guard and boundary) and
`/storage/nonsense/containers/x/objects` (objects leaf, same). A child with its own `notFoundComponent`
still handles its own throws — the router only searches upward past routes that declare none.
~~`defaultNotFoundComponent` now covers just `services/$serviceType`.~~ **Wrong — corrected 2026-09-18,
see D22.** It covers the opposite set: unmatched URLs under a layout route with no boundary of its own,
never a `notFound()` thrown from a loader.

Tests: `$storageType.test.tsx` (new) — three on the boundary: renders as a 404 whose exit is the bucket
list, uses the containers list for Swift, and falls back to the shared component's own action when the
params aren't readable.

**Gates:** typecheck ✅ · lint ✅ · format:check ✅ · check-i18n ✅ (1365, unchanged — the boundary reuses
strings the other storage 404s already carry) · `pnpm --filter @cobaltcore-dev/aurora test` **231 files /
5704 tests passed**.

## Swift's duplicated `prefix` helpers, folded into the shared ones (D19)

Found while answering a question about `?prefix=aW1hZ2VzLw%3D%3D` (base64 of `images/` — the folder being
browsed inside the bucket; base64 only so the `/` chars survive as a search param, not as protection).

Both object browsers encode that param, from two copies of the same code: `-components/utils/
prefixEncoding.ts` (used only by Ceph, extracted in #992) and a private pair inside `-components/Swift/
Objects/index.tsx:54-68`, older — it arrived with the portal→package move in #850 and was never repointed
when the shared file appeared.

`encodePrefix` was byte-identical. `decodePrefix` differed by one argument: the shared one decodes with
`new TextDecoder("utf-8", { fatal: true })`, Swift's with a plain `new TextDecoder()`. Not cosmetic —
`fatal` makes invalid UTF-8 throw into the existing `catch` and fall back to `""`, the container root,
while the non-fatal decoder substitutes U+FFFD and hands the result on as a genuine prefix, so a
hand-edited URL listed a folder that cannot exist. Invalid *base64* behaved the same either way; `atob`
throws for both.

D19: Swift imports the shared helpers, its twelve local lines go. The shared file gained a line of JSDoc
saying why it is shared (one `prefix` spelling, so a link made by one browser must be readable by the
other), and its first test — five cases: round-trip, nested/non-ASCII paths, absent param → root, invalid
base64 → root, and valid-base64-but-invalid-UTF-8 → root, the case that documents the behaviour Swift just
gained. One changeset paragraph records the user-visible half.

Unrelated to #1081 and raised as such; the user asked for it to be folded in ("можешь перенести если это
не критично").

**Gates:** typecheck ✅ · lint ✅ · format ✅ · `pnpm --filter @cobaltcore-dev/aurora test` **232 files /
5709 tests passed**.

## Per-folder state outliving its folder in the Ceph browser (D20)

Came out of walking the hand-edited-`prefix` cases one by one. `navigateToPrefix` clears the browser's
per-folder state (accumulated pages, the three pagination cursors, `hasMore`, `selectedItems`) before it
navigates — but it is only reached by a click on a folder row. Browser back/forward, a deep link and an
edited `?prefix=` reach the component as nothing but a new prefix, and `ObjectBrowserView` had no effect on
`currentPrefix`; its only reset hung on `[tab]`. Swift already had the effect, for selection only, and its
comment names exactly these paths.

User-visible: select an object in `tmp/`, press Back, and the bulk Actions menu is still armed with
"Delete 1 Object" over `tmp/scratch.log` while the root listing is on screen. The confirmation modal does
show the full path (`key.replace(currentPrefix, "")` strips nothing when the prefix no longer matches), so
it is not silent, but it offers to delete something the user cannot see. The pagination half of it is real
too but hard to reach: `hasMore` needs `isTruncated`, and the listing asks for `maxKeys: 1000`.

D20: extract the eight setters into `resetFolderState` (used by `navigateToPrefix`, `navigateToBuckets`,
and the new effect) and add an effect on `currentPrefix`. Two details about *when* it runs, both of which
broke the browser before they were right:

- It must be declared **before** the accumulation effect. My first cut put it after, reasoning that its
  updates should queue last and win. That is exactly backwards whenever the new folder's listing is already
  in the query cache — stepping back out of a folder visited seconds ago — because then `data` is there in
  the same commit: accumulation stored the page and the reset wiped it, and the user got an empty list.
  Caught by the user in the browser, not by the suite, which is why the fourth test below exists.
- It must be guarded by a ref against firing on mount, or it clears the first page for the same reason.
  `ObjectBrowserView`'s existing "shows total item count" test caught that one immediately.

Tests: four in `ObjectBrowserView.test.tsx` — selection dropped when the prefix changes outside
`navigateToPrefix`; selection kept across a re-render that doesn't change the folder (the guard against an
over-eager reset); the listing still on screen after a folder change whose data is already cached (the
regression above); and the continuation token dropped so it isn't replayed against another prefix. Each
verified red against the version of the code it is meant to pin.

Not part of #1081; raised while answering a question about `prefix` and folded in on the user's go-ahead.
Its own changeset (`object-browser-folder-state.md`), which also carries the `prefixEncoding` dedupe from
D19 — that paragraph was moved out of the 404 changeset so the latter stays about 404s.

Noted, not fixed (no instruction yet): with a folder above 1000 objects, sort/search/count operate on the
loaded subset only, and any mutation in the folder invalidates `objects.list`, refetches the current page
and re-appends it to the accumulated list — duplicate rows. The local mock can't exercise either: it
answers `IsTruncated=false` unconditionally.

**Gates:** typecheck ✅ · lint ✅ · format ✅ · `pnpm --filter @cobaltcore-dev/aurora test` **232 files /
5713 tests passed**.

## A folder that doesn't exist stops being a writable empty folder (D21)

Case 2 of the `prefix` walk-through: a valid base64 value naming a folder that isn't in the bucket. Both
browsers rendered it as an ordinary empty folder — breadcrumbs drawing the invented segment, the empty-state
message, and a full toolbar. The user's objection was the toolbar, not the message: Upload writes
`currentPrefix + fileName` and Create Folder writes `currentPrefix + folderName`, so an invented path could
be made real from the address bar — including `a/b/c/` in one step, which the "no slashes in a folder name"
rule in `validateFolderName` otherwise prevents.

**The evidence is already on hand.** A prefix names a folder that exists iff some key starts with it, and
that is exactly what the listing request answers. No second request, no loader change — a loader would have
needed `loaderDeps` on the search params and would have duplicated the browse listing, the dubling we just
removed for Swift.

Two things the check must get right, both about what an empty folder really is:

- it is a stored object — a zero-byte key equal to the prefix in Ceph (`objectRouter.ts` `createFolder`
  writes it), an `application/directory` object in Swift. Both row builders filter that marker out of the
  table, so the check has to read the **raw** response, not the rows;
- the Deleted tab lists versions, and a live folder can have none, so only the All tab may judge. Ceph's
  check also skips a paginated or truncated response — an empty page is not an empty listing.

D21: an early return above the toolbar in both browsers, rendering `RouteIdLevelDefaultError` ("Folder Not
Found") whose action is the container/bucket root — the container itself is fine, so the exit stays inside
it. Returning above the toolbar is half the point: the message alone would still leave Upload reachable.

Deliberate consequence: a folder that exists only as an implicit prefix, with no marker and no objects, now
reads as missing. In S3/Swift terms it *is* missing, and the user accepted that when the trade was put to
them.

Tests: four in `ObjectBrowserView.test.tsx` and four in `Swift/Objects/index.test.tsx` — the missing-folder
message together with the absence of the table and Upload; an empty *root* left alone; a folder holding
only its own marker treated as real; and (Ceph) the Deleted tab not judging existence, (Swift) the exit
navigating within the container. Verified red with the guards disabled.

**Gates:** typecheck ✅ · lint ✅ · format ✅ · check-i18n ✅ (1371 messages, +6) · `pnpm --filter
@cobaltcore-dev/aurora test` **232 files / 5721 tests passed**.

## D22 — what `defaultNotFoundComponent` actually covers (corrects D18's closing line) — 2026-09-18

Surfaced by the code review of the working tree. The reviewer claimed `defaultNotFoundComponent` is dead
code, since `__root.tsx:29` declares `notFoundComponent: PageNotFound` and the boundary search always
reaches the root. That is true of one of the router's two not-found paths, and the wrong one was written
into `router.ts`'s comment and into the changeset.

**Path A — `notFound()` thrown from a loader.** `load-matches.js:547` → `getNotFoundBoundaryIndex`
(`:38`) walks *upward* from the throwing match and returns the first route declaring a
`notFoundComponent` (`:47`). The root declares one, so the guard at `:555`
(`if (!boundaryRoute.options.notFoundComponent && defaultNotFoundComponent)`) never fires.
`services/$serviceType` — the case D18 named — takes this path and renders the root's `PageNotFound`.
`defaultNotFoundComponent` has nothing to do with it.

**Path B — a URL matching no route at all.** Different machinery: `router.js:830-833` sets
`isGlobalNotFound` and `findGlobalNotFoundRouteId` (`:1142`) picks the boundary. Under the default
`notFoundMode` (anything but `"root"`, so `undefined` qualifies) it returns the deepest matched route
**having children**, without checking for a `notFoundComponent`. That match gets `globalNotFound: true`
(`load-matches.js:562`) and its `<Outlet/>` calls `renderRouteNotFound(router, route, void 0)`
(`Match.js:283`) with *that* route — not the root. No component there → `defaultNotFoundComponent`.

So the fallback covers exactly Path B, at any layout route without its own boundary: `$projectId` today
(`/projects/<id>/nonsense`), and `$storageType` until D18 gave it `StorageTypeNotFound`. The 2026-09-17
browser observation recorded above is the empirical proof — the Juno default copy plus a "Go to Project
Home" button is `ServiceLevelDefaultError`, which the root's `PageNotFound` (explicit `title`/`body`,
"Go to Home" → `/`) could not have produced.

Fixed: the comment in `client/router.ts` and paragraph 17 of `.changeset/storage-provider-404.md`, both of
which had the two paths swapped. The component and its wiring stay — they are a real improvement over the
shell-less `<p>Not Found</p>` that Path B produced before.

Left alone deliberately: `ServiceLevelDefaultError` passes `code` without `title`/`body`, so Juno fills in
hardcoded English outside Lingui. Now known to be on a reachable path rather than theoretical, but the file
is vendored byte-identical from #1304 and diverging is a separate decision — still on the list of feedback
to leave there.

## D23 — the folder reset moves off the effect queue (completes D20) — 2026-09-18

Also from the code review. D20 reset per-folder state in a `useEffect`, which is one step too late for
the cursor: `objects.list.useQuery` reads `continuationToken` *while rendering*, at a point where
`currentPrefix` is already the new folder and the cursor still belongs to the old one. React Query
subscribes and fetches at commit, so that render really did send
`{prefix: "tmp/", continuationToken: <from images/>}` before the effect cleared it.

Replaced with the documented "adjust state while rendering" pattern, placed above the query:

```tsx
const [lastPrefix, setLastPrefix] = useState(currentPrefix)
if (lastPrefix !== currentPrefix) {
  setLastPrefix(currentPrefix)
  resetFolderState()
}
```

React re-runs the component before committing, so the stale-cursor pass never reaches a commit — and
nothing fetches during render: `useBaseQuery` calls only `observer.getOptimisticResult`
(`queryObserver.js:120`, builds the cache entry, no request); the fetch hangs off `observer.subscribe`
via `useSyncExternalStore` and off the `observer.setOptions` effect, both commit-time.

Bonus: D20's load-bearing effect ordering is gone. The reset is no longer an effect, so it cannot race
the accumulation effect — which is the regression that emptied the browser on the way back out of a
folder. `navigateToPrefix` keeps its own `resetFolderState()` call: redundant now, but it runs before
`navigate`, so it costs one render and removes any doubt about the click path.

**Not unit-testable, and deliberately not faked.** The suite mocks `useQuery`, so `mock.calls` records
the discarded render's arguments exactly like a committed one — the very distinction that makes the fix
work is invisible at that level. An assertion like "no recorded call carried the old cursor" would be red
against correct code. The existing four tests still cover what is observable (selection dropped, cached
listing survives, cursor absent from the committed query), and the rest is argued from the two library
call sites above.

**Gates:** typecheck ✅ · lint ✅ · format:check ✅ · `pnpm --filter @cobaltcore-dev/aurora test`
**232 files / 5721 tests passed** (unchanged).

## D24 — the rest of the code-review findings, case by case — 2026-09-18

**"Folder Not Found" hides the Deleted tab (Ceph) — not taken.** The claim was a lockout: delete every
object under `tmp/` in a versioned bucket and the restorable versions become unreachable. It isn't one.
The tab switch resets the prefix to the bucket root **by design** (`ObjectBrowserView.tsx`, the All/Deleted
`onClick`s: `prefix: tab === "all" ? undefined : prev.prefix`), so even with the tab bar on screen, Deleted
would land at the root — the same place "Back to Bucket Root" goes. Cost of the missing tab bar: one extra
click. And the state barely occurs: a folder made by `CreateFolderModal` has a marker object whose key is
the prefix, the row builder hides it so no bulk delete can select it, and it keeps the raw listing
non-empty. Only an *implicit* prefix flips, and for one of those the message is true. Recorded in the
JSDoc over `folderIsMissing` so the next reader doesn't walk the same path.

**Same transition in Swift — not taken, same reasons plus two of its own.** `swiftRouter.ts:929` writes the
`application/directory` marker; `buildRows` classifies it as a folder row, so it is never among the objects
a delete can select. And the listing query passes `prefix` with **no delimiter**, so it is recursive —
anything nested keeps the folder alive too. `if (isLoading)` returns above the check, so there is no 404
flash on a cold navigation either. JSDoc updated to match.

**The boundary's exit could land on a second 404 — fixed.** `StorageTypeNotFound` built its list link out of
the raw `$provider`/`$storageType` params, and the layout route has no guard, so `/storage/garbage/garbage/x`
rendered a "Back to Containers" button pointing at `/storage/garbage/garbage`, which the list route's own
guard 404s (`provider-not-found`); `/storage/ceph/containers/b/oops` did the same via
`storage-type-mismatch`. Now the link is offered only when `isStorageProvider(provider)` holds, and the noun
comes from `storageTypeFor(provider)` instead of being echoed. An unknown provider falls through to
`RouteIdLevelDefaultError`'s own "Go to Project Home". Two tests added, both verified red first (against a
version with the narrowing removed, then against one echoing the raw noun).

**Dead `storageType` prop on `BucketModals` — next.**

**Gates:** typecheck ✅ · lint ✅ · format:check ✅ · check-i18n ✅ (1371, unchanged — the corrected link
reuses the labels it already had) · `pnpm --filter @cobaltcore-dev/aurora test` **232 files / 5723 tests**
(+2).

**Dead `storageType` prop — removed.** `BucketModals` stopped reading it when `resolvedStorageType` became
derived from the provider, but it stayed in `BucketModalsProps`, in the (unused, deprecated)
`useBucketModals` signature, and at the one real call site. `BucketHeader` was pulling `storageType` out of
`useParams` for nothing else, so that went too. A comment in the props interface says why there is no such
prop, so it doesn't get added back. Gates re-run: typecheck ✅ · lint ✅ · format:check ✅ ·
**232 files / 5723 tests** ✅.
