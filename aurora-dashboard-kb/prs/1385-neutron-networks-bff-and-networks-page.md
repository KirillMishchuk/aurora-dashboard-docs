---
type: pr-report
date: 2026-10-13
status: open
pr: [1385]
author: mark-karnaukh-extern-sap
branch: mark-manage-networks-interface
---

# PR #1385: feat(network): add Neutron Networks BFF and read-only Networks page (list & details)

**Author:** mark-karnaukh-extern-sap · **Status:** open (draft as of 2026-10-13)
**Branches:** `mark-manage-networks-interface` → `main` · **Files:** 41 (+5106/-211)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1385

## What was done

The PR adds end-to-end Networks management to Aurora Dashboard: a tRPC BFF for Neutron Networks and a read-only UI with a list view and a network details view.

**BFF — `packages/aurora/src/server/Network/`**

A new `networksRouter` is mounted at `network.networks`. It exposes seven procedures: `list`, `getById`, `create`, `update`, `delete`, `setTags`, and `listSubnets`. Only `list`, `getById`, and `listSubnets` are wired to the UI in this PR; the write procedures (`create`, `update`, `delete`, `setTags`) are implemented in the BFF and tested but not yet exposed in the client. New Zod schemas land in `types/network.ts` and network-specific error handlers in `helpers/networkHelpers.ts`.

The `list` procedure solves a Neutron blind spot: Neutron's `project_id` filter hides networks shared with the project by other projects. The BFF therefore sends up to two parallel requests — own networks (`?project_id=X`) and shared networks (`?shared=true`) — merges the results by ID, and re-sorts the combined list. A `shared` filter in the input sends only one of the two requests.

Subnet names in the list are resolved in one batched, best-effort lookup: after filtering, the BFF collects all unique subnet IDs from the result and resolves them with a single chunked request (`GET /v2.0/subnets?id=a&id=b&fields=id,name`). A failed lookup degrades gracefully to showing IDs.

**Shared helper extraction — same commit as the Ports branch**

Two new shared helper modules are extracted from `routersRouter.ts` / `routerHelpers.ts` so the Networks BFF can use them without duplication:

- `helpers/requestHelpers.ts`: `requestOrThrow` (runs a Neutron request, maps `SignalOpenstackApiError` to `TRPCError` via an operation-specific handler), `pickDefined`, `chunk`, `withQuery`.
- `helpers/lookupHelpers.ts`: `fetchNetworkSummaries`, `fetchSubnetSummaries`, `fetchSecurityGroupSummaries` — batched, best-effort name lookups.

`routersRouter.ts` and `routerHelpers.ts` are updated to import from these new modules; their logic is unchanged.

**UI — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/`**

- A "Networks" nav entry is added to the Network section in `buildNavSections.ts`, gated behind `isEnabled("networks")`.
- A "Networks" card is added to the project overview, also gated.
- The list route (`networks/index.tsx`) renders the `Networks` component from `NetworksList.tsx`. It supports search, Status and Shared filters, column sorting (Name, Status, MTU), and URL-driven pagination. The component uses React 19's `use()` + `useDeferredValue` pattern (same as the Routers list) to keep the current list on screen while the next query loads.
- The details route (`networks/$networkId.tsx`) shows a description list of all network properties with copyable IDs and a Subnets tab. The loader fetches only the page title; all data, error handling, and retry are managed by a `useQuery` inside the component (same pattern as `$routerId.tsx`).

**i18n, docs, changeset**

German and English `.po` files are updated, the `@cobaltcore-dev/aurora: minor` changeset is included, and BFF documentation is added at `packages/aurora/docs/0017_networks_bff.md`.

## How it is implemented

### Dual-scope list with merge and sort

`networksRouter.list` builds one or two `requestOrThrow` calls depending on the `shared` filter, runs them with `Promise.all`, then merges and re-sorts:

```typescript
// packages/aurora/src/server/Network/routers/networksRouter.ts:74–99
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

const networks = sortNetworks(mergeNetworks(...(await Promise.all(requests))), input.sort_key, input.sort_dir)
```

`mergeNetworks` deduplicates by ID (first occurrence wins) and `sortNetworks` re-orders the combined list because each scope arrives already sorted by Neutron, but the concatenation is not:

```typescript
// packages/aurora/src/server/Network/helpers/networkHelpers.ts:112–143
export const mergeNetworks = (...lists: Network[][]): Network[] => {
  const byId = new Map<string, Network>()
  for (const network of lists.flat()) {
    if (!byId.has(network.id)) byId.set(network.id, network)
  }
  return [...byId.values()]
}

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

`compareValues` handles null/undefined (sorts last), booleans, numbers, arrays, and strings.

### Batched subnet name lookup

After filtering, the BFF collects all unique subnet IDs across the result set and resolves them in one call. The `fetchSummaries` core in `lookupHelpers.ts` chunks IDs at 50, sends one request per chunk in parallel, and swallows the entire result on any failure:

```typescript
// packages/aurora/src/server/Network/helpers/lookupHelpers.ts:30–39
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

`applySubnetNames` (networkHelpers.ts:151) then zips the resolved names back onto each network's `subnets` array as `subnet_details: NetworkSubnetReference[]`.

### Error mapping

`NetworkErrorHandlers` in `networkHelpers.ts` builds on the shared `ErrorHandler` factory with network-specific overrides. Notably, Neutron reports quota violations as 409 (not 413), so the 409 handler inspects `statusText` for a quota pattern before falling back to the operation-specific message:

```typescript
// packages/aurora/src/server/Network/helpers/networkHelpers.ts:27–33
const conflict = (message: string) => (response: ErrorResponse) =>
  new TRPCError({
    code: HTTP_STATUS_ERROR_MAP[409],
    message: /quota/i.test(response.statusText ?? "") ? QUOTA_EXCEEDED_MESSAGE : message,
  })
```

### UI: stale-content list with URL-driven state

`NetworksList.tsx` follows the same React 19 pattern as `RoutersList.tsx`. The tRPC query is issued as a Promise (`createNetworksPromise`) and deferred so the previous result stays on screen while the next query loads:

```typescript
// packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:254–266
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

### Details route: loader for title, component for data

The `$networkId` route loader fetches only the network name for the `<title>` tag and never throws. The component makes its own `trpcReact.network.networks.getById.useQuery` call, which carries retry logic and maps `TRPCError` codes to human-readable messages and retry-eligibility via `RETRYABLE_TRPC_CODES`. This matches the pattern of `$routerId.tsx`.

## What it affects

**`network.networks` tRPC key** — brand new, no existing callers. All seven procedures (`list`, `getById`, `create`, `update`, `delete`, `setTags`, `listSubnets`) are exclusively consumed by the new routes and components added in this PR. No stale callers elsewhere in the monorepo.

**`requestHelpers.ts` exports** (`requestOrThrow`, `pickDefined`, `chunk`, `withQuery`) — consumed by `routersRouter.ts`, `routerHelpers.ts`, `networkHelpers.ts`, and `networksRouter.ts`. All four are changed in this PR; no consumers outside the PR's changed files.

**`lookupHelpers.ts` exports** (`fetchNetworkSummaries`, `fetchSubnetSummaries`, `fetchSecurityGroupSummaries`) — consumed by `routersRouter.ts` and `networksRouter.ts`. Both updated in this PR; no outside consumers. `fetchSecurityGroupSummaries` is introduced here but not yet used (it existed in `routersRouter.ts` inline before extraction).

**Nav and project card** — both gated behind `enabledServices: ["networks"]`, so host apps not opting in see no change.

**`routersRouter.ts` and `routerHelpers.ts`** — their logic is unchanged; only import statements move from inlined definitions to the new shared modules.

## Review

No issues with confidence ≥80 found.

Two issues were identified and scored:

- **`networksRouter.ts:88` — `Promise.all` on dual-scope requests**: if the `?shared=true` Neutron request fails (e.g. FORBIDDEN under a non-default policy), the whole `list` procedure fails even if the project's own networks were retrieved successfully. Real UX break when triggered; requires a non-default Neutron policy. Confidence **50** — not commonly hit on standard deployments.

- **`lookupHelpers.ts:34` — `Promise.all` in chunk loop**: a single failed chunk discards results from all resolved chunks, returning `[]` rather than partial names. Confidence **50** — requires >50 distinct subnet IDs across the network list; the degradation is graceful (IDs shown instead of names). The pattern `Promise.allSettled` is used in comparable code in `imageHelpers.ts`, so the inconsistency is real but low-impact here.

---

Analyzed: 2026-10-13 · commit `9ed4250`

<!-- related:auto — generated from pr/issue properties by tools/update-related.py; do not edit by hand -->
## Related

- pr-report · 2026-10-13 · [1385-neutron-networks-bff-and-networks-page-v2](1385-neutron-networks-bff-and-networks-page-v2.md)
- pr-report · 2026-10-13 · [1385-neutron-networks-bff-and-networks-page-v3](1385-neutron-networks-bff-and-networks-page-v3.md)
- pr-report · 2026-10-14 · [1385-neutron-networks-bff-and-networks-page-mergeview-opus](1385-neutron-networks-bff-and-networks-page-mergeview-opus.md)
- pr-report · 2026-10-14 · [1385-neutron-networks-bff-and-networks-page-opus-2](1385-neutron-networks-bff-and-networks-page-opus-2.md)
- pr-report · 2026-10-14 · [1385-neutron-networks-bff-and-networks-page-opus](1385-neutron-networks-bff-and-networks-page-opus.md)
- pr-report · 2026-10-14 · [1385-neutron-networks-bff-read-only-page](1385-neutron-networks-bff-read-only-page.md)
- pr-report · 2026-10-15 · [1385-neutron-networks-bff-and-networks-page-review-opus](1385-neutron-networks-bff-and-networks-page-review-opus.md)
- pr-report · 2026-10-15 · [1385-neutron-networks-review-brief](1385-neutron-networks-review-brief.md)
