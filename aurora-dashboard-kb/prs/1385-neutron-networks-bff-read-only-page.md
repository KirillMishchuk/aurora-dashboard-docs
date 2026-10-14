---
type: pr-report
date: 2026-10-14
status: open
pr: [1385]
author: mark-karnaukh-extern-sap
branch: mark-manage-networks-interface
---
# PR #1385: feat(network): add Neutron Networks BFF and read-only Networks page (list & details)

**Author:** mark-karnaukh-extern-sap · **Status:** draft · **Created:** 2026-10-13
**Branches:** `mark-manage-networks-interface` → `main` (base `a21ba3ec`) · **Files:** 41 (+5106/-211)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1385
**CI:** all green (at `9ed42505`)

## What was done

The PR adds Neutron **Networks** (L2 networks) to the dashboard in two layers, as 13 commits that build up the BFF, then the UI, then docs, translations and a changeset.

**BFF.** A new tRPC router `network.networks` with seven procedures, all `projectScopedProcedure`:
- `list`: own networks plus shared networks, merged, re-sorted and searched in the BFF, with subnet names resolved.
- `getById`.
- `create`, `update`, `delete` and `setTags`.
- `listSubnets`: subnets of one network, for the details view.

The write procedures exist only in the BFF; the PR adds no UI for them. Network-specific error handlers map Neutron's 403/404/409 to readable messages: admin-only attributes, a network still in use on delete, unsharing a network that is still in use, and quota. Zod schemas live in a new `types/network.ts`. Design notes are in `packages/aurora/docs/0017_networks_bff.md` (495 lines).

**Shared-helper refactor.** `requestOrThrow`, `pickDefined`, `chunk` and `withQuery` moved out of the Routers BFF (`routerHelpers.ts` / `routersRouter.ts`) into a new `Network/helpers/requestHelpers.ts`. The two best-effort name lookups (`fetchNetworkSummaries`, `fetchSubnetSummaries`) moved into a new `Network/helpers/lookupHelpers.ts`, along with a new `fetchSecurityGroupSummaries` that nothing calls yet; it is meant for the Ports branch. The summary schemas moved from `types/router.ts` to `types/index.ts`. The PR description says this is "the same commit as on the Ports branch".

**UI.** Changes under `client/routes/_auth/projects/$projectId/network/networks/`:
- A layout route with a subtree error component.
- A list page with these columns: Name / ID, Status, Admin State, Subnets, Shared, External, MTU. It has search, status and shared filters, sort by name/status/MTU, and client-side pagination of 50 rows; all of this state lives in the URL.
- A details page with an overview (copyable IDs) and a Subnets tab (tab state in `?tab=`).
- A "Networks" entry in the side navigation and a card on the project overview (service key `networks`).
- 28 new message entries per locale (de, en).

**Tests.** 13 test files changed: +2526/-87 lines, mostly new.

**Description vs. code.** The PR description lists a **Fix**: "Router details route: use a literal route id in `createFileRoute`". This PR does not contain that change. `network/routers/$routerId.tsx` is not in the diff and still reads `createFileRoute(ROUTE_ID)` at `$routerId.tsx:117` (see Review). The changeset says the nav entry and card "both require `networks` in `enabledServices`". That is only true when `enabledServices` is set: with no list, `isEnabled` returns true (see "What it affects").

CI is green at the head. The only PR comment is the preview-deploy bot; there are no reviews yet.

## How it is implemented

### `list`: own + shared, merged and re-sorted in the BFF

Neutron's `project_id` filter hides networks that other projects share with this one, so the router sends one or two requests, depending on the `shared` filter:

```ts
const requests = getNetworkListScopes(shared).map(async (scope) => {
  const scopeFilters =
    scope === "own"
      ? { ...openstackFilters, project_id, ...(shared === false && { shared: false }) }
      : { ...openstackFilters, shared: true }
  const queryParams = appendQueryParamsFromObject(scopeFilters, { keyMap: LIST_NETWORKS_QUERY_KEY_MAP })
  const response = await requestOrThrow(
    () => network.get(withQuery(NETWORKS_BASE_URL, queryParams)),
    NetworkErrorHandlers.list
  )
  const data = await response.json()
  return parseOrThrow(NetworkListResponseSchema, data, "networksRouter.list").networks
})
```
`packages/aurora/src/server/Network/routers/networksRouter.ts:74`

```ts
export const getNetworkListScopes = (shared: boolean | undefined): Array<"own" | "shared"> => {
  if (shared === true) return ["shared"]
  if (shared === false) return ["own"]
  return ["own", "shared"]
}
```
`packages/aurora/src/server/Network/helpers/networkHelpers.ts:106`

`mergeNetworks` deduplicates by ID, so the first occurrence wins and the "own" copy is kept. Because each Neutron response is sorted on its own but their concatenation isn't, the BFF re-sorts the merged list:

```ts
export const sortNetworks = (
  networks: Network[],
  sortKey: NetworkQueryParameters["sort_key"],
  sortDir: SortDir = "asc"
): Network[] => {
  if (!sortKey) return networks
  const direction = sortDir === "desc" ? -1 : 1
  return [...networks].sort((a, b) => direction * compareValues(a[sortKey], b[sortKey]))
}
```
`packages/aurora/src/server/Network/helpers/networkHelpers.ts:135`

`compareValues` puts `null`/`undefined` after any value. The direction multiplier applies to that branch too, so in `desc` order missing values come first, which contradicts the JSDoc's "Missing values sort last" (Review).

After sorting, the shared `filterBySearchParams` applies `searchTerm` on `id`, `name` and `description`. Then subnet IDs from all remaining networks are collected and resolved with `fetchSubnetSummaries`, and `applySubnetNames` attaches `subnet_details: { id, name? }[]` to each network (`networksRouter.ts:89–99`). The return type is `NetworkListItem` = `Network & { subnet_details }` (`types/network.ts:178`).

There is no pagination: each scope is a single GET without `limit`/`marker`, and the client paginates the full result in memory.

### Error mapping

All main requests go through `requestOrThrow`, moved from `routerHelpers.ts` with the body unchanged; the handler type was renamed (`RouterErrorHandler` → exported `NetworkErrorHandler`) and the JSDoc no longer says "router":

```ts
export const requestOrThrow = async <T extends { ok: boolean; status: number; statusText?: string }>(
  request: () => Promise<T>,
  handleError: NetworkErrorHandler,
  resourceLabel?: string
): Promise<T> => {
  let response: T
  try {
    response = await request()
  } catch (error) {
    if (error instanceof SignalOpenstackApiError) {
      throw handleError({ status: error.statusCode, statusText: error.message }, resourceLabel)
    }
    throw error
  }
```
`packages/aurora/src/server/Network/helpers/requestHelpers.ts:19`

`statusText` therefore carries Neutron's own error message, not the HTTP reason phrase. That is what lets the 409 overrides detect quota errors by text:

```ts
const conflict = (message: string) => (response: ErrorResponse) =>
  new TRPCError({
    code: HTTP_STATUS_ERROR_MAP[409],
    message: /quota/i.test(response.statusText ?? "") ? QUOTA_EXCEEDED_MESSAGE : message,
  })
```
`packages/aurora/src/server/Network/helpers/networkHelpers.ts:26`

`NetworkErrorHandlers` (`networkHelpers.ts:51`) adds overrides on top of the shared `ErrorHandler("Network")`:
- 403 on `create`/`update`: the admin-only message plus Neutron's text.
- 404: "Network … was not found."
- 409 on `create`, `update` and `delete`: the quota check first, then an operation-specific text.

### Writes

- `create` drops `project_id` from the body, so Neutron derives ownership from the rescoped token (`networksRouter.ts:121`).
- `update` sends only the fields that were provided (`buildNetworkBody` = `pickDefined`) and rejects an empty update with `BAD_REQUEST` (`networksRouter.ts:141–144`).
- `setTags` replaces all tags with a deduplicated list (`networksRouter.ts:178–181`). Tags are trimmed, limited to 255 characters and comma-free (`types/network.ts:15`).
- `shared` and `router:external` are accepted on create and update; Neutron's policy decides whether they're allowed.
- Every ID used in a URL path goes through `validateAndEncodeResourceId` (`networkUrl`, `networksRouter.ts:44`). `listSubnets` validates the ID and sends it only as a query parameter (`networksRouter.ts:199`).

### Batched lookups (`lookupHelpers.ts`)

The extraction changed the lookups from one request for all IDs to one request per 50 IDs:

```ts
const fetchSummaries = async <T>(ids: string[], fetchChunk: (chunkIds: string[]) => Promise<T[]>): Promise<T[]> => {
  const uniqueIds = [...new Set(ids)]
  if (uniqueIds.length === 0) return []
  try {
    const chunks = await Promise.all(chunk(uniqueIds, LOOKUP_CHUNK_SIZE).map(fetchChunk))
    return chunks.flat()
  } catch {
    return []
  }
}
```
`packages/aurora/src/server/Network/helpers/lookupHelpers.ts:30`

Failure behaviour is still all-or-nothing, as before: one failed chunk returns `[]` for all of them, and callers fall back to IDs. The Routers BFF now uses these shared versions (`routersRouter.ts:44–45`).

### Client: list page

`index.tsx` validates the search params (`search`, `sortBy`, `sortDirection`, `page`, `status`, `shared`) and drops only the invalid ones (`index.tsx:36`). It renders `<Networks key={projectId} …>`, so the list remounts on a project switch (`index.tsx:62`).

`NetworksList.tsx` builds a promise for each URL state and keeps the previous list on screen while the next one loads:

```tsx
  const networksPromise = useMemo(
    () =>
      createNetworksPromise(client, project, sortBy, sortDirection, searchTerm, {
        status: statusFilter,
        shared: sharedFilter,
      }),
    // retryCount is not used in the factory, it only forces a new promise on "Try Again"
    [client, project, sortBy, sortDirection, searchTerm, statusFilter, sharedFilter, retryCount]
  )
  // Keeps the current list (and the search input) on screen while the next query loads,
  // instead of falling back to the Suspense loading state on every search, filter or sort change
  const deferredNetworksPromise = useDeferredValue(networksPromise)
  const isStale = deferredNetworksPromise !== networksPromise
```
`packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:254`

- `FORBIDDEN` turns into an inline error `Status`. Other errors go to an `ErrorBoundary`, keyed on the deferred promise, with a "Try Again" button that bumps `retryCount` (`NetworksList.tsx:65`, `:313`).
- Search is debounced by 500 ms. A `submittedSearchTerm` ref makes sure only external URL changes overwrite the input.
- The out-of-range page reset waits for `!isStale` (`NetworksList.tsx:136`).
- `NetworkListContainer` shows different empty states for "filtered" and "no networks in this project".
- Each `NetworkTableRow` is clickable and its menu offers a single action, "Show Details".

### Client: details page

`$networkId.tsx` has a loader whose only job is the page title; it swallows errors:

```tsx
  loader: async ({ context, params }) => {
    try {
      const network = await context.trpcClient?.network.networks.getById.query({
        project_id: params.projectId,
        network_id: params.networkId,
      })
      return { networkName: network?.name || null }
    } catch {
      return { networkName: null }
    }
  },
```
`packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId.tsx:138`

The component fetches the same network again with `trpcReact.network.networks.getById.useQuery` (`$networkId.tsx:175`). It renders `NetworkLoadError`, which maps the tRPC code to a 404/403/401/retryable error. `NetworkDetailsView` shows a `DescriptionList` overview and a `TabNavigation` with a single tab, `subnets`, synced to `?tab=` with `replace: true`. `subnets` is the default tab, so the UI writes `tab: undefined` for it and never sets `?tab=subnets` itself (`$networkId.tsx:165`). The tab loads `listSubnets` through `useQuery`.

### Wiring

- The router is mounted at `network.networks` in `packages/aurora/src/server/Network/routers/index.ts:17`.
- The nav entry is at `buildNavSections.ts:60` and the overview card at `$projectId/index.tsx:73`. Both are gated on `serviceIndex["network"]` and `isEnabled("networks")`.
- `routeTree.gen.ts` is regenerated: +79 lines, three new routes.
- `.changeset/neutron-networks-management.md` is a `minor` bump of `@cobaltcore-dev/aurora`.

## What it affects

**New public surface (additive).** The new procedure keys `network.networks.{list,getById,create,update,delete,setTags,listSubnets}` become part of `AuroraRouter`. Nothing outside the PR calls them: `git grep 'network\.networks'` at the head finds only the new route files (including the analytics name `network.networks.detail`), their tests, `docs/0017` and the changeset. There are no changes to `packages/aurora/src/server/index.ts` exports.

**Moved internal helpers.** These were checked with `git grep` at the head.
- `requestOrThrow`, `pickDefined`, `chunk` and `withQuery` are now consumed only by `routersRouter.ts`, `routerHelpers.ts` (`pickDefined`) and the new networks code.
- `NetworkSummary`/`SubnetSummary` (schemas and types) moved from `types/router.ts` to `types/index.ts`; `routerHelpers.ts:14` imports them from there.
- All callers were updated, and the Routers tests were trimmed to match (`routerHelpers.test.ts` -84; the tests moved to `requestHelpers.test.ts` / `lookupHelpers.test.ts`).

These helpers aren't exported from the package, so there is no consumer impact.

**Behaviour change for Routers.** Router list/detail name lookups are now chunked by 50 IDs (previously a single request). Failure handling is unchanged: still `[]` with a fallback to IDs. The Zod context strings changed from `routersRouter.networks/subnets` to `networkLookups.*`, which only affects log output.

**Navigation / `enabledServices`.** A new service key, `networks`, controls the nav entry and the overview card. `isEnabled` is `(!enabledServices || enabledServices.includes(service)) && !deniedServices?.includes(service)` (`buildNavSections.ts:32`). So:
- Consumers that pass no allowlist see Networks automatically.
- Consumers that pass an `enabledServices` allowlist (or an appConfig allowlist) don't see it until they add `networks`.
- The changeset's "require `networks` in `enabledServices`" is accurate only for that second group.

**Stale documentation.**
- `packages/aurora/README.md:183` and `:210` list the available service keys without `networks`. `routers` was already missing.
- `packages/aurora/docs/0010_routers_bff.md:571–590` still describes `requestOrThrow`, `chunk` and `pickDefined` as router helpers.

**Overlap with the Ports branch.** The helper extraction and the nav/routeTree edits also exist on `mark-manage-ports-interface`, which is not merged. The router route-id fix the description mentions (`d47d57b2`) exists only there. Whichever PR merges second will conflict in `buildNavSections.ts`, `routeTree.gen.ts`, `$projectId/index.tsx` and possibly the helper files.

## Review

### Findings (confidence ≥75)

#### 1. Non-shared external networks are missing from the Networks list — confidence 75

`list` builds its result from two Neutron queries only: `project_id=<current project>` ("own") and `shared=true` ("shared"). The code is at `packages/aurora/src/server/Network/routers/networksRouter.ts:74`; the scopes come from `getNetworkListScopes` at `packages/aurora/src/server/Network/helpers/networkHelpers.ts:106`.

A typical public/provider network has `router:external=true` and `shared=false` and is owned by an admin project. Neutron makes it visible to every project through an `access_as_external` RBAC entry, not through `shared`. That network matches neither query, so it never appears in the list.

The Neutron API reference describes list as returning "networks to which the project has access" (https://docs.openstack.org/api-ref/network/v2/index.html, List networks). The repo already treats external networks as their own category: `floatingIpRouter.ts:44` lists them with `router:external=true`.

The PR adds an "External" column and passes a `router:external` filter through. On most deployments, though, the column will show "No" for every row, and filtering by `router:external=true` will return nothing, unless the external network also happens to be shared.

Related, unverified (scored 25, below): networks shared with this project through a project-targeted RBAC `access_as_shared` policy may also fall through the `shared=true` filter.

**Suggested fix:** Add a third scope, `router:external=true`, merged by ID, and skip it when the caller filters `router:external=false` or `shared=false`. Alternatively, for non-admin tokens, drop the `project_id`/`shared` split and rely on Neutron's own visibility.
**Why this score:** The scorer confirmed in the code that only the `project_id` and `shared=true` requests are sent (`networksRouter.ts:76–84`, the design comment at `networkHelpers.ts:102–104`) and that `floatingIpRouter.ts:44` lists external networks separately. A non-shared external network matches neither request, and with the PR's External column and filter this will be visible on common deployments. The scorer scored on the code plus the Neutron docs wording and did not re-check Neutron's RBAC source.
This was not raised in the review discussion (there are no reviews yet). Two agents found it independently: the bug scan and the API-contract check.

### Below the bar

| Score | Finding | Why this score |
| --- | --- | --- |
| 50 | `sortNetworks` puts missing values **first** in `desc` order, contradicting the JSDoc "Missing values sort last", `docs/0017_networks_bff.md:82` and the ascending-only test; `networkHelpers.ts:121` | Verified: `compareValues` returns 1 for null `a`, and the `direction` multiplier flips that for `desc`. Rarely visible, because Neutron almost always sets `mtu`. |
| 50 | Context menu without `PopupMenuToggle` trigger; `NetworkTableRow.tsx:68` | Verified violation of B.14 / quick-reject (`copilot-instructions.md:47`), but it mirrors `RouterTableRow`. The impact on Juno's default trigger (accessibility) wasn't checked. |
| 50 | Network status rendered as plain text, not `Badge`; `NetworkTableRow.tsx:49`, `NetworkDetailsView.tsx:77` | B.1 "Status indicators → Badge" (`copilot-instructions.md:117`). Low impact, mirrors the routers pages. |
| 50 | All-caps `UP`/`DOWN` for admin state; `NetworkTableRow.tsx:50`, `NetworkDetailsView.tsx:78` | B.19 "Never all-caps (ever)" (`copilot-instructions.md:557`) is literal. These are Neutron state values and mirror `RouterDetailsView`. |
| 50 | Details page fetches the network twice (loader `getById.query` for the title + component `useQuery`); `$networkId.tsx:138`, `:175` | Verified: the loader call doesn't fill the react-query cache, so every visit makes two identical requests. Minor; mirrors `$routerId.tsx`. |
| 50 | `docs/0010_routers_bff.md:571` (and `:584`, `:590`) still describes `requestOrThrow`/`chunk`/`pickDefined` as router helpers after the move to `requestHelpers.ts` | Verified stale; the file isn't in the diff. |
| 50 | `packages/aurora/README.md:183` / `:210` service-key lists don't include `networks` | Verified. The lists read as examples, and `routers` was already missing. |
| 25 | PR description claims the literal-route-id fix for the router details route, but `$routerId.tsx:117` is untouched (`createFileRoute(ROUTE_ID)`); the fix `d47d57b2` is only on the Ports branch | Verified (`merge-base --is-ancestor` fails). This is a description inaccuracy, not a code defect: `routeTree.gen.ts` regenerated fine and CI is green. |
| 25 | Helper extraction duplicated with the Ports branch; whichever merges second conflicts; `requestHelpers.ts:1` | `requestHelpers.ts`/`lookupHelpers.ts` are identical on both branches, so they merge cleanly. Only the shared nav/routeTree files can conflict; this is about merge order. |
| 25 | Networks shared with this project through project-targeted RBAC may be missed by `shared=true`; `networksRouter.ts:79` | Couldn't verify from the repo whether Neutron's `shared` filter covers project-targeted `access_as_shared`. |
| 25 | Changeset: nav entry and card "both require `networks` in `enabledServices`", but they're shown when `enabledServices` is unset (`buildNavSections.ts:32`) | Wording nit in the changelog. |
| 25 | "One batched lookup" is really one request per 50 IDs, and one failed chunk drops all subnet names; `lookupHelpers.ts:30` | Verified, but this is a best-effort path that falls back to IDs. |
| 25 | `docs/0017` error tables omit 400/404/409/412 and quote messages loosely | Docs-only. The default `ErrorHandler` does cover those codes. |
| 25 | Untranslated `"Network Details"` page-title fallback; `$networkId.tsx:150` | Real, but title-only, and mirrors `$routerId.tsx`. |
| 25 | No length cap on `searchTerm`/tag filter strings; `types/network.ts:124` | Same as `securityGroup.ts`/`router.ts`. Generic hardening, not required by the standards. |
| 25 | En dash vs em dash for empty values (list vs details); `NetworkTableRow.tsx:61` | Cosmetic nitpick; mirrors routers. |
| 25 | `TwoLineCell` copied from `RouterTableRow`; `NetworkTableRow.tsx:19` | Small presentational duplicate; no rule requires extracting it. |
| 0 | No Neutron pagination (`next`/`marker`) in `list`; `networksRouter.ts:76` | Established pattern: `routersRouter`/`floatingIpRouter` don't follow `next` links either. |
| 0 | `NetworkSchema` requires `status`/`admin_state_up`/`project_id`; `types/network.ts:31` | Neutron always returns them; no concrete failure path. |
| 0 | Neutron error text put into `TRPCError` messages; `networkHelpers.ts:32` | Pre-existing pattern across the Network routers. |
| 0 | Write procedures lack server-side `canUser` / permission mapping | False: `network:networks:*` keys are mapped in `permissionRouter.ts:19–23`. As in the other routers, Neutron enforces authorization. |
| 0 | Quota detection in `conflict()` never matches because `statusText` is the HTTP reason phrase; `networkHelpers.ts:29` | False: `requestOrThrow` passes `SignalOpenstackApiError.message`, built from Neutron's parsed error (`signal-openstack/src/client.ts:202`). |

Security pass (dedicated `security-reviewer`): no exploitable issues. Scoping, ID encoding, Zod stripping of unknown keys and admin-only attributes all hold up. Its two low observations are the error-text and length-cap rows above.

## Proposed follow-ups

- [ ] **Non-shared external networks are missing from the Networks list** — `packages/aurora/src/server/Network/routers/networksRouter.ts:74` → Review, finding 1

---
Analyzed: 2026-10-14 · commit `9ed42505`
