---
type: pr-report
date: 2026-10-14
status: open
pr: [1385]
author: mark-karnaukh-extern-sap
branch: mark-manage-networks-interface
---

# PR #1385: feat(network): add Neutron Networks BFF and read-only Networks page (list & details)

**Author:** mark-karnaukh-extern-sap · **Status:** open (draft)
**Branches:** `mark-manage-networks-interface` → `main` · **Files:** 41 (+5106/-211)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1385

> Independent re-analysis (model: Opus) of the same PR already covered by `-v2`/`-v3`. Draft PR against `main`.

## What was done

The PR adds OpenStack Neutron **Networks (L2)** support to `packages/aurora` in two halves:

1. **A `network.networks` tRPC BFF** (server) with seven procedures — `list`, `getById`, `create`, `update`, `delete`, `setTags`, `listSubnets` — mounted under the existing `network` router namespace. The full write surface (create/update/delete/tags) exists on the API but is **not yet wired into the UI**; the UI is read-only for now.
2. **A read-only Networks UI** (client): a list view (Name/ID, Status, Admin State, Subnets, Shared, External, MTU) with search, status/shared filters, sorting and pagination, plus a details view with a Subnets tab and copy-to-clipboard IDs. A "Networks" entry is added to the Network side-nav section and a "Networks" card to the project overview.

Alongside the feature, the PR performs a **refactor of the pre-existing Network server code**: shared request plumbing (`requestOrThrow`, `pickDefined`, `chunk`, `withQuery`) is extracted from `routerHelpers.ts`/`routersRouter.ts` into a new `helpers/requestHelpers.ts`; the batched name-lookup helpers (`fetchNetworkSummaries`, `fetchSubnetSummaries`, and a new `fetchSecurityGroupSummaries`) move into a new `helpers/lookupHelpers.ts`; and the shared summary schemas (`SubnetSummary`, `NetworkSummary`, `SecurityGroupSummary`) move from `types/router.ts` into `types/index.ts`. `routersRouter` is updated to consume the shared versions.

A design doc (`packages/aurora/docs/0017_networks_bff.md`), a `minor` changeset, and en/de i18n catalogs are included.

## How it is implemented

### List: own + shared networks, merged, re-sorted, search, subnet-name enrichment

The central procedure is `list`. Neutron's `project_id` filter hides shared networks owned by *other* projects (which the project may still attach ports to), so the BFF issues up to two parallel requests and merges them.

```ts
// packages/aurora/src/server/Network/routers/networksRouter.ts:69
const { searchTerm, shared, project_id, ...openstackFilters } = input
const network = getNetworkService(ctx)

// Own networks are filtered by project_id, so admin roles also only see the current project's networks here.
// Shared networks of other projects are requested separately, because the project can use them too.
const requests = getNetworkListScopes(shared).map(async (scope) => {
  const scopeFilters =
    scope === "own"
      ? { ...openstackFilters, project_id, ...(shared === false && { shared: false }) }
      : { ...openstackFilters, shared: true }
  const queryParams = appendQueryParamsFromObject(scopeFilters, { keyMap: LIST_NETWORKS_QUERY_KEY_MAP })
  const response = await requestOrThrow(() => network.get(withQuery(NETWORKS_BASE_URL, queryParams)), NetworkErrorHandlers.list)
  const data = await response.json()
  return parseOrThrow(NetworkListResponseSchema, data, "networksRouter.list").networks
})

const networks = sortNetworks(mergeNetworks(...(await Promise.all(requests))), input.sort_key, input.sort_dir)
const filteredNetworks = filterBySearchParams(networks, searchTerm, ["id", "name", "description"])
```

`getNetworkListScopes` (`networkHelpers.ts:106`) encodes the request matrix: `shared===true` → `["shared"]`, `shared===false` → `["own"]`, unset → `["own","shared"]`. `mergeNetworks` dedupes by `id`, first occurrence wins (own-first order preserved because `Promise.all` keeps array order). Because each Neutron response is sorted but their concatenation isn't, the merged list is re-sorted BFF-side.

Subnet names are then resolved in one batched, best-effort lookup:

```ts
// packages/aurora/src/server/Network/routers/networksRouter.ts:92
const subnets = await fetchSubnetSummaries(network, collectSubnetIds(filteredNetworks), ["id", "name"], "networksRouter.list.subnets")
return applySubnetNames(filteredNetworks, subnets)
```

`fetchSubnetSummaries` (now in `lookupHelpers.ts:60`) chunks IDs by 50 (`LOOKUP_CHUNK_SIZE`), runs chunks in parallel, and returns `[]` on any failure so the list never fails because a name couldn't be resolved (`applySubnetNames` falls back to the ID).

### Error mapping

`networkHelpers.ts` builds `NetworkErrorHandlers` on top of the shared `ErrorHandler`, overriding where Neutron's semantics need a clearer message — notably Neutron reports `OverQuota` as **409, not 413**, so every network 409 checks for a quota message first:

```ts
// packages/aurora/src/server/Network/helpers/networkHelpers.ts:26
const conflict = (message: string) => (response: ErrorResponse) =>
  new TRPCError({
    code: HTTP_STATUS_ERROR_MAP[409],
    message: /quota/i.test(response.statusText ?? "") ? QUOTA_EXCEEDED_MESSAGE : message,
  })
```

### Validation

`types/network.ts` holds the Neutron response schema (extension-dependent fields are `nullish`, so missing extensions don't break parsing) and the tRPC input schemas, all extending `projectScopedInputSchema`. Write schemas enforce name length (1–255), description ≤255, MTU ≥68, and reject commas in tags (tags are sent as comma-separated lists). `create` intentionally omits `project_id` from the body (`networksRouter.ts:122`) — Neutron derives ownership from the rescoped token.

### Client

The list page (`NetworksList.tsx`) uses the URL as the single source of truth for search/filters/sort/page, a React `use()`+`Suspense` promise with `useDeferredValue` to keep the previous list visible while refetching, debounced search, and `ErrorBoundary` keyed on the deferred promise. `FORBIDDEN` list errors are caught and shown inline rather than thrown. The details page (`$networkId.tsx`) resolves only the page title in its loader (swallowing errors) and lets the component's query own the real error state, with a tRPC-code → HTTP-status map and a retryable-codes set driving the error UI.

## What it affects

- **New tRPC surface `network.networks.*`** (7 procedures), mounted in `Network/routers/index.ts:17`. No consumers outside the PR's own client files — this is additive.
- **Shared-helper refactor touches the existing Routers BFF.** `routersRouter.ts` now imports `requestOrThrow`/`pickDefined`/`chunk`/`withQuery` from `requestHelpers.ts` and `fetchNetworkSummaries`/`fetchSubnetSummaries` from `lookupHelpers.ts`. Verified against git history: the moved functions are behavior-preserving. Two observable deltas in the lookup helpers — ID de-duplication (`new Set`) and 50-ID chunking — do not change any currently exercised router path (call sites already pass unique, small ID arrays); the chunking is a latent-bug fix for the >50-ID case the old single-request version could not handle. No other module imported the moved symbols from their old locations, so the move breaks no callers.
- **Summary schemas moved** `types/router.ts` → `types/index.ts` with no field-level changes; `SecurityGroupSummary` is now defined/exported but `fetchSecurityGroupSummaries` has **no consumer yet** (staged for upcoming ports work).
- **`networks` service key** is free-form (`ServiceFeatureMap = Record<string, FeatureBag>`, default-open), so the nav/card wiring needs no central registration — it mirrors how `securitygroups`/`flavors` gate via `isEnabled`.
- **Routers code gets a minor observability regression** from the refactor (see Review, note 2).

## Review

Five review passes (CLAUDE.md/convention compliance, bug scan, git-history/refactor, comment compliance, prior-PR patterns) were run and confidence-scored. Compliance was clean: every convention candidate (import order, spacing/color tokens, `PopupMenu` shape, `distribution="end"` zone-1, permission-key `scope:resource:action`, file naming, URL state, `projectScopedProcedure` usage) matched the pre-existing Routers/Floating-IP/Security-Group pages. Two findings cleared the confidence bar.

**1. Auto page-clamp pushes a history entry → Back-navigation trap (confidence ~80).**
The clamp effect reuses the user-pagination handler, which — unlike every other search-param update in this file — navigates *without* `replace: true`:

```ts
// packages/aurora/.../network/networks/-components/NetworksList.tsx:136
useEffect(() => {
  if (!isStale && currentPage > totalPages) onPageChange(1)
}, [isStale, totalPages, currentPage, onPageChange])
```
```ts
// NetworksList.tsx:299  — onPageChange is this; note: no `replace: true`
const handlePageChange = useCallback(
  (page: number) => {
    navigate({ search: ((prev) => ({ ...prev, page: page === 1 ? undefined : page })) as unknown as true })
  },
  [navigate]
)
```
`updateSearch` (filters/sort/search, `NetworksList.tsx:268`) correctly passes `replace: true`; only the clamp path pushes. Scenario: land on `/networks?page=5` (bookmark/shared link, or the project shrank below 5 pages). The list loads with `totalPages=1`, `currentPage=5`, `isStale=false` → effect fires → `onPageChange(1)` pushes a new entry. Pressing **Back** restores `?page=5`, which re-clamps and pushes again — the user is trapped and cannot navigate back past that point. Fix: give the clamp a navigation path that uses `replace: true` (e.g. a separate `onPageClamp`).

**2. `sortNetworks` puts missing values *first* in descending order, contradicting the stated "missing values sort last" (confidence ~80).**
The null/undefined branch in `compareValues` returns a fixed sign, which `sortNetworks` then multiplies by the direction, flipping it for `desc`:

```ts
// packages/aurora/src/server/Network/helpers/networkHelpers.ts:121
const compareValues = (a: unknown, b: unknown): number => {
  if (a === b) return 0
  if (a === undefined || a === null) return 1   // "a after b" — only true for asc
  if (b === undefined || b === null) return -1
  ...
}
// networkHelpers.ts:135 — comment on this fn says "Missing values sort last."
return [...networks].sort((a, b) => direction * compareValues(a[sortKey], b[sortKey]))
```
For `desc`, `direction = -1`, so `compareValues(null, 1500) = 1` becomes `-1` → the null-valued network sorts **before** the 1500 one. Reachable through the UI: `mtu` is the only exposed sort key that is nullable (`name` defaults to `""`, `status` is always a string), so "sort by MTU, descending" lists networks without an MTU at the top instead of the bottom. The code's own comment (`networkHelpers.ts:133`) and `0017_networks_bff.md` both promise the opposite. Impact is cosmetic ordering, but it is a verified contract violation. Fix: handle null/undefined independently of `direction`.

**Lower-confidence notes (did not clear ~80, recorded for context):**
- `sort_key`/`sort_dir` fall into `...openstackFilters` and are forwarded to Neutron on both requests even though `sortNetworks` re-sorts authoritatively BFF-side — redundant. A hypothetical `400` from Neutron on an unsupported `mtu` sort key (deployments without `net-mtu`) would then fail the whole list, but whether Neutron rejects vs. ignores an unknown sort key is deployment-dependent and unverified (~45).
- The refactor drops the caller-specific `parseOrThrow` context labels in `routersRouter.ts` (`"routersRouter.networks"`/`"routersRouter.subnets"` → the helper defaults `"networkLookups.*"`), so Zod parse errors in the *routers* path are now harder to trace. Log label only (~40).
- `fetchSecurityGroupSummaries` is added but unused — dead code until the ports feature lands (~30).

---

Analyzed: 2026-10-14 · commit `9ed42505`

<!-- related:auto — generated from pr/issue properties by tools/update-related.py; do not edit by hand -->
## Related

- pr-report · 2026-10-13 · [1385-neutron-networks-bff-and-networks-page-v2](1385-neutron-networks-bff-and-networks-page-v2.md)
- pr-report · 2026-10-13 · [1385-neutron-networks-bff-and-networks-page-v3](1385-neutron-networks-bff-and-networks-page-v3.md)
- pr-report · 2026-10-13 · [1385-neutron-networks-bff-and-networks-page](1385-neutron-networks-bff-and-networks-page.md)
- pr-report · 2026-10-14 · [1385-neutron-networks-bff-and-networks-page-mergeview-opus](1385-neutron-networks-bff-and-networks-page-mergeview-opus.md)
- pr-report · 2026-10-14 · [1385-neutron-networks-bff-and-networks-page-opus-2](1385-neutron-networks-bff-and-networks-page-opus-2.md)
- pr-report · 2026-10-14 · [1385-neutron-networks-bff-read-only-page](1385-neutron-networks-bff-read-only-page.md)
- pr-report · 2026-10-15 · [1385-neutron-networks-bff-and-networks-page-review-opus](1385-neutron-networks-bff-and-networks-page-review-opus.md)
- pr-report · 2026-10-15 · [1385-neutron-networks-review-brief](1385-neutron-networks-review-brief.md)
