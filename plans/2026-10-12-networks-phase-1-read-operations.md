---
type: plan
date: 2026-10-12
status: not-implemented
issue: [1019]
---
# Plan: Networks Management — Phase 1 (read operations)

**Date:** 2026-10-12 · **Status:** not implemented
**Base:** `main` @ `6a8dad69`

## Overview

Phase 1 of epic #1019 adds a read-only Networks feature for the project. On the BFF side it adds `network.networks.list` and `network.networks.getById`, typed with Zod. On the client it adds a Networks list page (search, sort, client-side pagination, and Status / Shared / External filters, all kept in the URL) and a Network detail page with basic info and copy-to-clipboard IDs. `signal-openstack` needs no change: `ctx.openstack.service("network")` is already a generic Neutron client (`packages/signal-openstack/src/service.ts:95`), and every Network router uses it through `getNetworkService` (`packages/aurora/src/server/Network/helpers/index.ts:24`). The "Create/Extend Neutron client wrapper" subtask is therefore dropped.

## Decisions

- **D1. Which networks the list shows** → **A**: own ∪ shared ∪ external, fetched with three Neutron requests (`project_id`+`shared=false`, `shared=true`, `router:external=true`), then merged and deduplicated in the BFF. Adds an External column and an External Yes/No filter.
- **D2. Where copy-to-clipboard for network IDs goes** → **B**: `ClipboardText` on the detail page (ID, Project ID) and on the ID line of each list row.
- **D3. Position of "Networks" in navigation** → **A**: first in the Network section of the side nav and of the project overview cards. The order assertions in tests are updated.

Choices I made myself, each following an existing pattern:
- The "Name" filter is the standard BFF-side search box over `name`/`id`/`description` (`filterBySearchParams`), as in Routers and Security Groups. Neutron's `name=` is an exact match and would be a poor fit.
- Sort options are Name and Status. Sorting happens in the BFF, because the result is a union of three requests.
- Pagination is client-side with `PAGE_SIZE = 50` and `page` in the URL, as in Routers (`routers/-components/RoutersList.tsx:14,84-86`).
- Data fetching uses `trpcReact…useQuery` with `placeholderData`, as Security Groups does (`securitygroups/-components/SecurityGroupsList.tsx:87-104`), because that list already has a filter toolbar.
- Status is shown as plain text, as in Routers (`RouterTableRow.tsx:80`).
- Phase 1 has no actions, so there is no `useNetworkPermissions` hook yet. A 403 from Neutron becomes an error state in the grid.
- Admin-only `provider:*` and other extension fields are in the schema as optional/nullish but are not shown in the UI.
- New `enabledServices` key `networks`. When `enabledServices` is omitted it is visible by default, as `routers` was.

## Architecture Analysis

**Current state:**

- `server/Network/routers/index.ts:9-18` mounts the network sub-routers under `network`. The closest read-only model is `routersRouter.ts` (`list`/`getById` at `:170-238`), built on `projectScopedProcedure`, `withErrorHandling`, `requestOrThrow`, `parseOrThrow` and `validateAndEncodeResourceId`.
- `requestOrThrow` (`Network/helpers/routerHelpers.ts:122-139`) exists because signal-openstack rejects every non-2xx response with `SignalOpenstackApiError`. A plain `if (!response.ok)` check (still present in `floatingIpRouter.ts:61`) never runs, and the error would surface as a 500. Today it is router-local.
- `ErrorHandler(resourceName, overrides)` (`Network/helpers/errorHandling.ts:57-74`) already accepts `"Network"` as a resource name.
- The union / admin-safe pattern comes from Security Groups (#1321/#1360): `securityGroupRouter.ts:76-95` plus the generic helpers `deduplicateSecurityGroupsById` (`securityGroupHelpers.ts:382`) and `sortSecurityGroups` (`:417`). Both are generic over `T`.
- Existing network schemas are narrow projections that serve other calls and are left unchanged: `ExternalNetworkSchema` (`types/floatingIp.ts:272`, `router:external=true` only) and `NetworkSummarySchema` (`types/router.ts:142`, `fields=id,name`).
- `NetworkPortStatusSchema` (`ACTIVE|DOWN|BUILD|ERROR`) lives in `types/index.ts:13`.
- Permissions: `network:networks:read|list` → `get_network` (`permissionRouter.ts:20-21`), defined in `apps/dashboard/src/policies/networking.json:68` (`rule:default_viewer`). No change is needed.
- Client:
  - Section guard: `network.tsx` (redirects when the catalog has no network service).
  - Layout route carrying the breadcrumb and `errorComponent`: `network/routers.tsx:1-37`.
  - List route with per-field `validateSearch` fallback: `routers/index.tsx:9-41` and `floatingips/index.tsx:8-38`.
  - Detail route: `routers/$routerId.tsx`. Its loader only resolves the title; the component's query renders errors, with a code-aware `RouterLoadError` (`:13-106`) and `useSetBreadcrumb` (`:149`).
  - Typed filter config: `securitygroups/filterConfig.ts`. URL helpers: `securitygroups/urlHelpers.ts`.
  - Grid with Pagination: `routers/-components/RouterListContainer.tsx`. Loading/error/empty states inside the grid: `SecurityGroupListContainer.tsx` (≈`:130-172`).
- Navigation: `projects/-components/buildNavSections.ts:58-95` and the overview cards in `$projectId/index.tsx:70-95`. The service keys are documented in `packages/aurora/README.md:183,210`, which is already missing `routers`.
- `routeTree.gen.ts` is committed and regenerated by `@tanstack/router-plugin` (`vite.config.mjs:8,62`) on dev/build.

**Proposed changes:**

- **BFF:**
  - New `types/network.ts` with tolerant Zod schemas.
  - New `helpers/networkHelpers.ts` with error handlers, the request-selection logic and BFF filters.
  - New `routers/networksRouter.ts`, mounted as `network.networks`.
  - `requestOrThrow` moves to `helpers/errorHandling.ts` and is re-exported from `routerHelpers.ts`, so router code and tests don't change.
- **Client:**
  - New routes `network/networks.tsx`, `network/networks/index.tsx` and `network/networks/$networkId.tsx`.
  - Route-local `filterConfig.ts` and `urlHelpers.ts`.
  - Components in `networks/-components/`: `NetworksList`, `NetworkListContainer`, `NetworkTableRow`, `NetworkDetailsView`.
  - Navigation entries and the README key list.
- This fits the architecture: everything goes through `projectScopedProcedure`, data uses tRPC + TanStack Query, list state lives in the URL, and the UI is built from the Juno components prescribed by `.github/copilot-instructions.md`.

## Potential Problems & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Admin tokens see other projects' private networks if `project_id` is dropped from the own-side request (#1321 class) | High | The own request always sends `project_id` + `shared=false`. The other two requests (`shared=true`, `router:external=true`) only return resources visible to everyone. A unit test asserts the exact query strings. On the mock, `third-project-net` must never appear. |
| `shared=true` on an admin token may also return networks shared via RBAC with *other specific* projects (Neutron computes `shared` per context) | Medium | Same behavior that Security Groups accepted. Listed under Live-environment checks. |
| One of the three requests fails (e.g. a 403 on the external query) and the whole list fails | Medium | Kept at Security Groups parity (`Promise.all`). The error is mapped via `NetworkErrorHandlers.list` into a readable message shown in the grid. Noted under Open Questions. |
| Neutron `pagination_max_limit` set in a deployment truncates unpaginated list responses silently | Medium | Same as Routers today. Listed under Live-environment checks. |
| An unknown status or missing extension fields (`mtu`, `router:external`, `port_security_enabled`, `availability_zones`) fail parsing for the whole list | Medium | `status: z.string()`; extension fields `optional()`/`nullish()`; `subnets` defaults to `[]`; `name`/`description` default to `""`. The schema test covers a minimal payload. |
| `[PERF]` Three Neutron calls per list load | Low | They run in parallel. Requests that the active Shared/External filters make unnecessary are skipped (see Step 2). |
| `[BREAKING]` (visual only) Nav and overview order changes and a new nav entry appears for consumers without `enabledServices` | Low | Decided in D3. Consumers that pass `enabledServices` are unaffected until they add `networks`. README updated. |
| Clickable rows contain the `ClipboardText` button | Low | `ClipboardText` already calls `preventDefault` + `stopPropagation` (`client/components/ClipboardText.tsx:29-31`). A row test asserts that clicking it does not navigate. |
| Moving `requestOrThrow` breaks imports | Low | It is re-exported from `routerHelpers.ts`. `routerHelpers.test.ts` keeps passing unchanged. |

## Prerequisites

- [ ] Extend the local mock (`/Users/kirylmishchuk/projects/SAP/local-mock-backend/fake-backend.js`, `networks` collection at `:525` / `seedNetwork` at `:699`) with the fixtures the manual check needs; today none are shared, DOWN/ERROR or admin-down:
  - a network from another project with `shared: true`;
  - an own network with `shared: true`;
  - an own network with `status: "DOWN"` and `admin_state_up: false`;
  - an own network with `status: "ERROR"`;
  - a network without `mtu` and without `port_security_enabled`.

  Check whether the mock's generic filter (`neutronApplyQuery`, `:1290`) handles `shared=false` / `router:external=true` as booleans. If not, add that there. The mock lives outside the repo; repo code must not depend on it.

## Implementation Steps

### Step 1: Add Network Zod schemas

**Files to modify/create:**

- `packages/aurora/src/server/Network/types/network.ts` (new)
- `packages/aurora/src/server/Network/types/network.test.ts` (new)

**What to do:**

1. Import `z`, `projectScopedInputSchema` from `../../trpc`, and `ISO8601TimestampSchema`, `NetworkPortStatusSchema`, `SortDirSchema` from `./index`. Follow the section layout of `types/router.ts`.
2. `NetworkSchema = z.object({...})` (default non-strict object, so unknown keys are stripped):
   - Required: `id: z.string()`, `admin_state_up: z.boolean()`, `shared: z.boolean()`, `project_id: z.string()`.
   - With defaults: `name: z.string().nullable().optional().transform(v => v ?? "")` (or `.default("")`, as in `RouterSchema`; Neutron can return `""`), `description: z.string().nullish().transform(v => v ?? "")`, `status: z.string()` (tolerant; comment that the known values are `NetworkPortStatusSchema`), `subnets: z.array(z.string()).optional().default([])`.
   - Optional: `tenant_id: z.string().optional()`, `"router:external": z.boolean().optional()`, `mtu: z.number().optional()`, `port_security_enabled: z.boolean().optional()`, `availability_zones: z.array(z.string()).optional()`, `availability_zone_hints: z.array(z.string()).optional()`, `revision_number: z.number().optional()`, `tags: z.array(z.string()).optional()`, `created_at: ISO8601TimestampSchema.optional()`, `updated_at: ISO8601TimestampSchema.optional()`, `dns_domain: z.string().nullish()`, `l2_adjacency: z.boolean().optional()`.
   - Nullish: `is_default: z.boolean().nullish()`, `ipv4_address_scope: z.string().nullish()`, `ipv6_address_scope: z.string().nullish()`, `qos_policy_id: z.string().nullish()`, `"provider:network_type": z.string().nullish()`, `"provider:physical_network": z.string().nullish()`, `"provider:segmentation_id": z.number().nullish()`.
   - Add a short comment: extension and admin-only fields vary per deployment.
3. Response envelopes: `NetworkListResponseSchema = z.object({ networks: z.array(NetworkSchema) })` and `NetworkResponseSchema = z.object({ network: NetworkSchema })`.
4. Input schemas:
   - `NetworkSortKeySchema = z.enum(["name", "status"])`.
   - `ListNetworksInputSchema = projectScopedInputSchema.extend({ sort_key: NetworkSortKeySchema.optional(), sort_dir: SortDirSchema.optional(), status: NetworkPortStatusSchema.optional(), shared: z.boolean().optional(), external: z.boolean().optional(), searchTerm: z.string().trim().optional() })`. Comment that every field except `project_id` is applied BFF-side.
   - `GetNetworkByIdInputSchema = projectScopedInputSchema.extend({ network_id: z.string().trim().min(1, "ID is required") })`.
5. Export types: `Network`, `NetworkListResponse`, `ListNetworksInput`, `GetNetworkByIdInput`, `NetworkSortKey`.

**Expected outcome:** schemas compile and are importable from client code as types (`import type`).

**Verification:** `network.test.ts` (mirror `types/routers.test.ts`) covers:
- a full payload;
- a minimal payload (only `id`, `admin_state_up`, `shared`, `project_id`, `status`), with `subnets` defaulting to `[]` and `name` to `""`;
- `provider:*` set to `null`;
- an unknown status `"UNKNOWN"` accepted;
- unknown keys stripped;
- input schema: an empty `network_id` rejected, a non-enum `sort_key` rejected, a non-enum `status` rejected.

Run `pnpm --filter @cobaltcore-dev/aurora test src/server/Network/types/network.test.ts`.

---

### Step 2: Add network helpers and move `requestOrThrow` `[SECURITY]`

**Files to modify/create:**

- `packages/aurora/src/server/Network/helpers/errorHandling.ts` - add `requestOrThrow`
- `packages/aurora/src/server/Network/helpers/routerHelpers.ts` - replace the definition with a re-export
- `packages/aurora/src/server/Network/helpers/networkHelpers.ts` (new)
- `packages/aurora/src/server/Network/helpers/networkHelpers.test.ts` (new)

**What to do:**

1. Move `requestOrThrow` with its JSDoc from `routerHelpers.ts:113-139` into `errorHandling.ts`. Type the handler parameter as `(response: ErrorResponse, resourceLabel?: string) => TRPCError` (export that type as `ResourceErrorHandler`). Import `SignalOpenstackApiError` there.
2. In `routerHelpers.ts`, delete the local definition and the now-unused `RouterErrorHandler` type and `SignalOpenstackApiError` import, if unused. Add `export { requestOrThrow } from "./errorHandling"`.
3. In `networkHelpers.ts`:
   - `NetworkErrorHandlers = { list: ErrorHandler("Network"), get: ErrorHandler("Network", { 404: (_r, id) => new TRPCError({ code: HTTP_STATUS_ERROR_MAP[404], message: \`Network ${id} was not found.\` }) }) }`. Follow `RouterErrorHandlers.get` at `routerHelpers.ts:53-55`.
   - `selectNetworkRequests({ shared, external }): { own: boolean; shared: boolean; external: boolean }`:
     - `own = shared !== true && external !== true`
     - `shared = shared !== false && external !== true`
     - `external = external !== false`

     Add a JSDoc table of the 9 combinations. The idea: every filtered view is a subset of "All", and each row reaches the result through at least one request.
   - `filterNetworksByBffParams(networks, { status, shared, external })`:
     - `status` is compared case-insensitively;
     - `shared` is compared with `network.shared`;
     - `external` is compared with `Boolean(network["router:external"])`.

     Follow `filterRoutersByBffParams` at `routerHelpers.ts:162-170`.

**Expected outcome:** routers code is unchanged in behavior; network helpers are ready.

**Verification:**
- `networkHelpers.test.ts` covers all 9 `selectNetworkRequests` combinations, each filter dimension and their combination, and the 404 handler message and code.
- `pnpm --filter @cobaltcore-dev/aurora test src/server/Network/helpers` (including the existing `routerHelpers.test.ts` `requestOrThrow` block at `:433`) is green.

---

### Step 3: Implement `networksRouter` and mount it `[SECURITY]` `[CAREFUL]`

**Files to modify/create:**

- `packages/aurora/src/server/Network/routers/networksRouter.ts` (new)
- `packages/aurora/src/server/Network/routers/networksRouter.test.ts` (new)
- `packages/aurora/src/server/Network/routers/index.ts` - add `networks: networksRouter`

**What to do:**

1. Constants: `NETWORKS_BASE_URL = "v2.0/networks"`, plus a local `withQuery` (copy from `routersRouter.ts:66-69`).
2. A fetch helper `fetchNetworks(network, params)`:
   - Builds the query with `appendQueryParamsFromObject(params)`.
   - Calls `requestOrThrow(() => network.get(withQuery(NETWORKS_BASE_URL, qp)), NetworkErrorHandlers.list)`.
   - Parses with `parseOrThrow(NetworkListResponseSchema, data, "networksRouter.list").networks`.
3. `list: projectScopedProcedure.input(ListNetworksInputSchema).query(async ({ input, ctx }): Promise<Network[]> => withErrorHandling(async () => {...}, "list networks"))`:
   - Destructure `{ project_id, searchTerm, status, shared, external, sort_key, sort_dir }`.
   - `const plan = selectNetworkRequests({ shared, external })`.
   - Requests:
     - own → `{ project_id, shared: false }`
     - shared → `{ shared: true }`
     - external → `{ "router:external": true }`

     Run them with `Promise.all`.
   - Pipeline: `deduplicateSecurityGroupsById` → `filterNetworksByBffParams` → `filterBySearchParams(result, searchTerm, ["name", "description", "id"])` → `sortSecurityGroups(result, sort_key ?? "name", sort_dir ?? "asc")`. Import the two SG helpers from `../helpers/securityGroupHelpers` and comment that they are generic.
   - Copy the #1321 comment (`securityGroupRouter.ts:80-82`) explaining why `project_id` must stay on the own request.
4. `getById: projectScopedProcedure.input(GetNetworkByIdInputSchema).query(...)`:
   - `validateAndEncodeResourceId(network_id, "Network")`.
   - `requestOrThrow(() => network.get(\`${NETWORKS_BASE_URL}/${encoded}\`), NetworkErrorHandlers.get, network_id)`.
   - `parseOrThrow(NetworkResponseSchema, data, "networksRouter.getById").network`.
   - `withErrorHandling(..., "show network details")`.
5. Add a JSDoc header listing the procedures, like `routersRouter.ts:148-167`.
6. In `routers/index.ts`, add `networks: networksRouter` to the `network` router object.

**Expected outcome:** `trpc.network.networks.list` / `getById` are callable. The client type `@/server/Network/types/network` is available.

**Verification:** `networksRouter.test.ts` mirrors the caller setup in `routersRouter.test.ts` (`createCallerFactory`, mocked `ctx.openstack.service("network").get`) and covers:
- No filters → exactly 3 GETs. Assert the URLs contain `project_id=proj-1&shared=false`, `shared=true`, and `router%3Aexternal=true`. The shared and external URLs contain no `project_id`.
- A network returned by two requests appears once.
- A foreign private network is never requested (no unscoped call).
- `shared: true` → only the `shared=true` call. `external: false` → no external call.
- Status, search and sort (name asc/desc, status) applied.
- `SignalOpenstackApiError(…, 403)` → `TRPCError` `FORBIDDEN`. 404 on `getById` → `NOT_FOUND` with "Network x was not found.".
- An invalid response shape → `PARSE_ERROR`.
- A path-traversal id (`"../x"`) rejected.

---

### Step 4: Add the Networks layout and list routes

**Files to modify/create:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks.tsx` (new)
- `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/index.tsx` (new)
- `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/filterConfig.ts` (+ `filterConfig.test.ts`) (new)
- `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/urlHelpers.ts` (+ `urlHelpers.test.ts`) (new)

**What to do:**

1. `networks.tsx`: copy `network/routers.tsx` 1:1 with `service: "networks"`, ``crumb: { text: msg`Networks` }``, `NetworksErrorComponent` with a "Back to Networks" button targeting `/projects/$projectId/network/networks`.
2. `networks/index.tsx`, following `routers/index.tsx:9-41`:
   - `networksSearchFields = { search: z.string().optional(), sortBy: NetworkSortKeySchema.optional(), sortDirection: z.enum(["asc","desc"]).optional(), page: z.number().int().positive().optional(), status: NetworkPortStatusSchema.optional(), shared: z.enum(["true","false"]).optional(), external: z.enum(["true","false"]).optional() }`.
   - `z.looseObject`, with per-field `safeParse` fallback for every field.
   - `staticData { section: "network", service: "networks", analytics: { name: "network.networks.list" } }`.
   - ``head: t`Networks` ``.
   - The component renders ``<ContentHeader title={t`Networks`} projectId={projectId} />`` and `<Networks key={projectId} projectId={projectId} />`.
   - Export `type NetworksSearchParams`.
3. `filterConfig.ts`, mirroring `securitygroups/filterConfig.ts`:
   - `NetworkFilterParams = Partial<Pick<ListNetworksInput, "status" | "shared" | "external">>`.
   - `buildNetworkFilters(labels: { status; shared; external; yes; no; active; down; build; error })` returns:
     - Status: values `ACTIVE/DOWN/BUILD/ERROR` with `valueLabels`, `supportsMultiValue: false`;
     - Shared and External: `"true"/"false"` with Yes/No labels.
   - `buildNetworkFilterParams(selected)` returns typed params; for `status`, validate with `NetworkPortStatusSchema.safeParse`.
   - `isKnownNetworkFilter(name, value)`.
4. `urlHelpers.ts`, mirroring `securitygroups/urlHelpers.ts`:
   - `parseFiltersFromUrl(params)` for `status`/`shared`/`external`, dropping unknown values via `isKnownNetworkFilter`;
   - `applyFilterSelection` (copy);
   - `buildUrlSearchParams(selected, filters, base)`, which keeps `search`/`sortBy`/`sortDirection` and **omits `page`**, so a filter change resets to page 1. Single-value filters only, so the `in:` branch is not needed.

**Expected outcome:** `/projects/$projectId/network/networks?status=DOWN&shared=false&page=2` parses. Invalid values fall back per field.

**Verification:**
- Unit tests for `filterConfig` (typed params, invalid status ignored, last-wins) and `urlHelpers` (parse, unknown values dropped, page removed on filter change).
- Route generation happens in Step 7.

---

### Step 5: Build the list components (DataGrid, toolbar, pagination, copyable IDs)

**Files to modify/create** (under `.../network/networks/-components/`):

- `NetworksList.tsx` (+ `.test.tsx`)
- `NetworkListContainer.tsx` (+ `.test.tsx`)
- `NetworkTableRow.tsx` (+ `.test.tsx`)

**What to do:**

1. `NetworksList.tsx` (`{ projectId: string }`) uses the toolbar and URL handling of `SecurityGroupsList.tsx:39-104,190-356`, without the create/update/delete parts:
   - Read `useSearch({ strict: false }) as NetworksSearchParams`. Defaults: `sortBy` "name", `sortDirection` "asc", `page` 1.
   - Query: `trpcReact.network.networks.list.useQuery({ project_id, sort_key, sort_dir, ...buildNetworkFilterParams(parseFiltersFromUrl(search)), ...(search ? { searchTerm } : {}) }, { refetchOnWindowFocus: false, placeholderData: (prev) => prev })`.
   - Error text: FORBIDDEN → ``t`You do not have permission to view networks` ``; otherwise `error.message || t`Failed to Load Networks``.
   - Non-blocking `<Message variant="error" className="mb-4">` when the refetch fails and cached rows exist (`:252-256`).
   - Layout `Stack direction="vertical" className="juno-pattern-datagrid-outer"`:
     - Zone 1: `Stack distribution="end" alignment="center" gap="2" className="pb-2"` with a `SortInput` (options Name / Status; no create button in Phase 1).
     - Zone 2: `DataGridToolbar` with `FiltersInput`, a debounced `SearchInput` (500 ms, ``placeholder={t`Search networks...`}``, `className="w-60 sm:w-68"`) and `SelectedFilters`.
   - Navigation: sort, filter and search changes use `replace: true` and set `page: undefined` (as `RoutersList.tsx:180-200`). The page change pushes (`:202-212`).
   - Client pagination: `PAGE_SIZE = 50`, `totalPages = max(1, ceil(n/50))`, `safePage = min(page, totalPages)`, slice. When not `isPlaceholderData` and `page > totalPages`, call `onPageChange(1)` (as `RoutersList.tsx:96-100`, using `isPlaceholderData` in place of `isStale`).
   - Debounce/URL sync of the input follows `SecurityGroupsList.tsx:67-85`.
2. `NetworkListContainer.tsx` (props `networks`, `isLoading`, `isError`, `error`, `hasActiveFilters`, `currentPage`, `totalPages`, `onPageChange`):
   - `DataGrid columns={7} minContentColumns={[6]}`, `data-testid="networks-table"`.
   - Head cells (title case): Name, Status, Admin State, Shared, External, MTU, and an empty action cell.
   - Loading, error and empty rows inside the grid, as in `SecurityGroupListContainer`: `Status progress` with ``t`Loading Networks...` ``; `Status error` with the message; `Status empty` with ``t`No Networks Found` ``. Empty-state body: with filters/search active, ``t`No networks match the current search or filters. Clear them to view all networks.` ``; otherwise ``t`There are no networks available in this project.` `` (B.6 distinguishes empty reasons).
   - The `Pagination variant="input"` block is copied from `RouterListContainer.tsx:96-118` (`Stack distribution="center" className="py-4"`), rendered only if `totalPages > 1`.
3. `NetworkTableRow.tsx`, following `RouterTableRow.tsx`:
   - The row is clickable to `/projects/$projectId/network/networks/$networkId`, `data-testid={\`network-row-${id}\`}`.
   - Name cell: a vertical `Stack gap="0.5"` with the name (or the id if the name is empty) and, below it, `<ClipboardText text={network.id} className="text-theme-light text-sm" />` (D2). When the name is empty, render only the `ClipboardText` id.
   - Status: plain `network.status`. Admin State: ``t`Up` ``/``t`Down` ``. Shared and External: ``t`Yes` ``/``t`No` ``. MTU: `network.mtu ?? "–"`.
   - Action cell: `onClick={(e) => e.stopPropagation()}`, a `PopupMenu` with ``PopupMenuItem label={t`Show Details`}`` (`RouterTableRow.tsx:81-87`).

**Expected outcome:** the list renders with filters, search, sort and pagination, all reflected in the URL; back/forward restores state.

**Verification** (component tests, using the render/router helpers of the routers/SG tests):
- Columns and values render; the empty MTU shows "–".
- Clicking the `ClipboardText` copies (mock `navigator.clipboard.writeText`) and does **not** navigate; clicking the row navigates.
- Pagination shows with 51+ rows and is hidden with 50.
- The filter pill updates the URL and resets the page.
- The empty-state wording differs with and without filters.
- FORBIDDEN error text.
- Loading state.

---

### Step 6: Add the Network detail route and view

**Files to modify/create:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId.tsx` (new)
- `.../network/networks/-components/NetworkDetailsView.tsx` (+ `.test.tsx`) (new)

**What to do:**

1. `$networkId.tsx`: copy the structure of `routers/$routerId.tsx`:
   - `ROUTE_ID`; `HTTP_STATUS_BY_TRPC_CODE`, `RETRYABLE_TRPC_CODES` and `getTrpcErrorCode` copied.
   - `NetworkLoadError` with network wording: ``t`This network does not exist or has been deleted.` ``, ``t`Access to this network is not permitted.` ``, ``t`Network Not Found` ``/``t`Error Loading Network` ``, "Back to Networks".
   - `errorComponent`.
   - A loader that only resolves `networkName` via `context.trpcClient?.network.networks.getById.query(...)` inside try/catch; `head` falls back to "Network Details".
   - `staticData { section: "network", service: "networks", analytics: { name: "network.networks.detail" } }`.
   - The component: `trpcReact.network.networks.getById.useQuery({ project_id, network_id })`, `useSetBreadcrumb(Route.id, network?.name || network?.id)`, ``Status progress t`Loading Network Details...` `` while pending, `ContentHeader title={network.name || network.id}` and `<NetworkDetailsView network={network} />`.
2. `NetworkDetailsView.tsx`: `Stack direction="vertical" gap="6" className="mt-6"` with a single `DescriptionList alignTerms="right"`, reusing the `DetailsList` helper pattern from `RouterDetailsView.tsx:24-36` (defined locally). Rows, with "—" for absent values:
   - Name;
   - ID → `<ClipboardText text={network.id} />`;
   - Project ID → `<ClipboardText text={network.project_id} />`;
   - Description;
   - Status;
   - Admin State (``t`Up` ``/``t`Down` ``);
   - Shared (Yes/No);
   - External (Yes/No);
   - MTU;
   - Port Security (``t`Enabled` ``/``t`Disabled` ``/—);
   - Availability Zones (comma-joined or —);
   - Subnets (count; the subnet list is Phase 2).

**Expected outcome:** the detail page shows basic info with copyable IDs; 404, 403 and 5xx render the scoped error with retry where relevant.

**Verification:** `NetworkDetailsView.test.tsx`: all labels/values; "—" for a missing `mtu`, `port_security_enabled` and `availability_zones`; both `ClipboardText` triggers present (`data-testid="clipboard-copy-trigger"`).

---

### Step 7: Register navigation, regenerate the route tree, update README `[BREAKING]` (visual order)

**Files to modify:**

- `packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.ts:58` - prepend a `networks` NavItem (``label: t`Networks` ``, navigates to `/projects/$projectId/network/networks`, guarded by `isEnabled("networks")`) as the first entry of `networkServices`.
- `packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.test.ts:40,64,118` (and any other `toEqual` on network order) - expect `["networks", "securitygroups", "floatingips", "routers"]`, etc. Add a test that `enabledServices: ["networks"]` shows only Networks and that `deniedServices: ["networks"]` hides it.
- `packages/aurora/src/client/routes/_auth/projects/$projectId/index.tsx:70` - inside `if (serviceIndex["network"])`, push the Networks card **first**: ``{ group: t`Network`, label: t`Networks`, to: `${base}/network/networks`, service: "networks" }``.
- `packages/aurora/README.md:183,210` - the service key lists become `"images"`, `"flavors"`, `"networks"`, `"securitygroups"`, `"floatingips"`, `"routers"`, `"containers"`, `"ceph-containers"`. Also drop the stale `"pca"`, which was removed in #1189, since these are the same lines.
- `packages/aurora/src/client/routeTree.gen.ts` - regenerated, not hand-edited.

**What to do:** apply the edits, then run `pnpm --filter @cobaltcore-dev/aurora build` (or start `pnpm dev` once) so the router plugin regenerates `routeTree.gen.ts` with `network/networks`, `network/networks/`, and `network/networks/$networkId`.

**Expected outcome:** the side nav and overview show "Networks" first in the Network group; routes resolve; typed `navigate({ to: "/projects/$projectId/network/networks/$networkId" })` compiles.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck` and `test src/client/routes/_auth/projects/-components` pass.

---

### Step 8: Extract i18n and run the CI checks

**Files to modify:** `packages/aurora/src/locales/{en,de}/messages.*` (generated by Lingui extraction).

**What to do:** run `pnpm check-i18n` (lingui extract + compile) and keep the generated catalog changes. Then run `pnpm --filter @cobaltcore-dev/aurora lint`, `typecheck`, `test`, plus `pnpm format:check` and `pnpm build`.

**Expected outcome:** all CI jobs that apply are green.

**Verification:** command exit codes; `git status` shows only the files listed in this plan plus the regenerated catalogs and `routeTree.gen.ts`.

## Testing Plan

**Unit tests** (vitest, colocated):

- [ ] `types/network.test.ts`: full and minimal payloads, nullable `provider:*`, unknown status, input validation.
- [ ] `helpers/networkHelpers.test.ts`: request-selection matrix (9 cases), BFF filters, 404 handler.
- [ ] `routers/networksRouter.test.ts`: the 3 request URLs (own carries `project_id`+`shared=false`, others don't); dedupe; no unscoped request; filter-driven request skipping; search, sort; 403/404/parse errors; id path validation.
- [ ] Existing `helpers/routerHelpers.test.ts` and `routers/routersRouter.test.ts` stay green after the `requestOrThrow` move.
- [ ] `networks/filterConfig.test.ts`, `networks/urlHelpers.test.ts`.
- [ ] `NetworksList.test.tsx`, `NetworkListContainer.test.tsx`, `NetworkTableRow.test.tsx` (copy does not navigate, pagination threshold, empty wording, FORBIDDEN).
- [ ] `NetworkDetailsView.test.tsx`.
- [ ] `buildNavSections.test.ts`: new order, enabled-only and denied cases.

**Manual check on the local mock** (`/Users/kirylmishchuk/projects/SAP/local-mock-backend/`, `./run-all.sh`; the mock token behaves like an admin token, so it reproduces the #1321 case):

1. Open the project overview for `demo-project`. "Networks" is the first card in Network and the first side-nav entry.
2. Networks list, no filters. It shows `demo-private`, `isolated-net`, the seeded `app-*`/`k8s-*`/`lab-*`/`bulk-net-01..52` networks and the two `FloatingIP-external-*` networks (External = Yes). `third-project-net` must **not** appear. With more than 50 rows, Pagination appears; `?page=2` deep-links.
3. Filters. Shared = Yes shows only the shared fixtures from the Prerequisites, including the other project's shared one. External = Yes shows only the two external networks. Status = DOWN shows the DOWN fixture with Admin State "Down". The URL updates and the page resets to 1; browser back/forward restores state.
4. Search "bulk-net-0" filters by substring. Sort by Status desc.
5. Click the ID copy icon in a row: the "Copied to clipboard" tooltip appears and the page does not navigate. Click the row: the detail page opens with the breadcrumb Home › … › Networks › `<name>`.
6. Detail of the fixture without `mtu`/`port_security_enabled` shows "—". `/network/networks/does-not-exist` shows "Network Not Found" with "Back to Networks".

**Live-environment checks** (real Neutron; the mock can't confirm these):

- [ ] As an admin user in a project: the list contains no private networks of other projects. If any appear, the own-request scoping is wrong.
- [ ] A network shared via RBAC to *this specific* project (not `*`) appears with Shared = Yes for a non-admin member. If it's missing, Neutron's `shared=true` filter doesn't cover targeted RBAC and the shared request needs rethinking. Also check whether admins see RBAC-targeted networks of unrelated projects.
- [ ] A user without `network_viewer`-type roles gets the "You do not have permission to view networks" grid error, not a crash.
- [ ] The list isn't silently capped: compare the count with `openstack network list` for a project with many networks (`pagination_max_limit`).

**E2E (Playwright):** none. Phase 4 per the epic.

## Acceptance Criteria

- [ ] `network.networks.list` and `network.networks.getById` exist, use `projectScopedProcedure`, and validate inputs and Neutron responses with Zod.
- [ ] The list never requests networks without `project_id` except the `shared=true` and `router:external=true` requests; no other project's private networks are shown (unit test + mock check).
- [ ] The list page shows Name (with copyable ID), Status, Admin State, Shared, External and MTU; supports search, sort (Name/Status), pagination (50/page) and Status/Shared/External filters; all of that state lives in the URL.
- [ ] The detail page shows Name, ID and Project ID (copyable), Description, Status, Admin State, Shared, External, MTU, Port Security, Availability Zones and Subnets count, with code-aware errors (404/403/retryable).
- [ ] Neutron errors surface as readable messages (`NetworkErrorHandlers`), not as generic 500s.
- [ ] "Networks" is the first entry in the Network section of the side nav and overview, gated by the `networks` service key; README lists the key.
- [ ] No regressions in Routers, Security Groups, Floating IPs or navigation tests.
- [ ] CI checks pass: `lint`, `typecheck`, `test`, `check-i18n`, `format:check`, `build` (scoped with `--filter @cobaltcore-dev/aurora` where possible).

## Open Questions

- Partial failure: if one of the three requests is denied in a real deployment (e.g. the external query), should the list degrade to the remaining requests instead of failing? Kept at Security Groups parity (fail the whole list) for now. The implementer can confirm during the live check whether this happens.
- Status display: plain text, matching Routers. If review asks for `Badge`/icons (copilot-instructions B.1), that is a styling change contained in `NetworkTableRow`/`NetworkDetailsView`.

## Follow-ups

- [FOLLOW-UPS.md → item 48](../FOLLOW-UPS.md) — Per-resource copies of the detail-route load-error component
- [FOLLOW-UPS.md → item 30](../FOLLOW-UPS.md) — `if (!response.ok)` branches are unreachable across the whole repository (covers the dead checks in `floatingIpRouter.ts` / `securityGroupRouter.ts`)

<!-- related:auto — generated from pr/issue properties by tools/update-related.py; do not edit by hand -->
## Related

- plan · 2026-10-12 · [2026-10-12-networks-epic-1019-analysis](2026-10-12-networks-epic-1019-analysis.md)
