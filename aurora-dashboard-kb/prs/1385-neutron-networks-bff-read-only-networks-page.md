---
type: pr-report
date: 2026-10-30
status: open
pr: [1385]
issue: [1019]
author: mark-karnaukh-extern-sap
branch: mark-manage-networks-interface
---

# PR #1385: feat(network): add Neutron Networks BFF and read-only Networks page (list & details)

**Author:** mark-karnaukh-extern-sap · **Status:** draft · **Base:** `main` ← `mark-manage-networks-interface`
**Size:** 41 files, +5106 / −211 · **Created:** 2026-10-13 · [View on GitHub](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1385)

---

## PR Review Report by [review-and-comment-pr](https://github.com/KirillMishchuk/aurora-dashboard-docs/blob/main/ToolDocs/claude-config/aurora-dashboard-config/.claude/skills/review-and-comment-pr/SKILL.md)

_Reviewed at head [`9ed42505`](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1385/commits/9ed425055637c05119f3d7a7814c3af134b884cd) · base `main` at `a21ba3ec` · 2026-10-30 06:40 UTC_

### ⚖️ &nbsp; Verdict

Recommendation: **🔴 Request Changes** &nbsp;&nbsp;&nbsp;&nbsp; Confidence to Merge: **High**

- **Must fix before merge** (#1019 — read-only Networks scope, list and details with Subnets tab (MVP foundation + partial MVP)): CR2, CR3, CR4
- **Team call** (convention, existing pattern or deferred by a maintainer): CR1
- **Process:** P1

This PR adds a fully-featured Networks BFF (7 procedures) and a read-only Networks UI (list and details) as part of issue #1019. All four MVP acceptance criteria are met. The implementation follows established patterns well: projectScopedProcedure for auth, Zod schemas for validation, and error handlers for user-friendly messages. Several bugs and UI convention violations need attention: a sorting bug puts null-MTU networks first in descending order, missing pagination limits large deployments, the filter design hides external networks, and multiple B.* rule violations (PopupMenu toggle, all-caps text, plain-text status, minWidth). The PR description claims a router-details fix that was already merged separately.

### 🔧 &nbsp; Required Changes

| #   | Severity    | Category      | Precedent     | Issue                                                                                                     | Location                                                                                                          |
| --- | ----------- | ------------- | ------------- | --------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| CR1 | 🟡 Moderate | Accessibility | existing code | `PopupMenu` lacks required `PopupMenuToggle` wrapper, making action menu inaccessible                     | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:68` |
| CR2 | 🟡 Moderate | Bug           | —             | No pagination — users see only the first page when there are more networks than Neutron's page limit      | `packages/aurora/src/server/Network/routers/networksRouter.ts:65`                                                 |
| CR3 | 🟡 Moderate | Bug           | —             | External non-shared networks are hidden from the list — users cannot see floating-IP pools here           | `packages/aurora/src/server/Network/routers/networksRouter.ts:74-78`                                              |
| CR4 | 🟡 Moderate | Bug           | —             | Descending sort puts null-MTU networks first, contradicting the JSDoc contract "missing values sort last" | `packages/aurora/src/server/Network/helpers/networkHelpers.ts:142`                                                |
| P1  | —           | Process       | —             | The router details route file was not changed in this PR.                                                 | PR body                                                                                                           |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**CR1 — Network table row menu lacks `PopupMenuToggle` trigger** · Accessibility · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:68`
The action menu in `NetworkTableRow` uses `PopupMenu` directly without a `PopupMenuToggle` wrapper. Per B.14, context menus require `<PopupMenuToggle as="div"><Button icon="moreVert" /></PopupMenuToggle>` as the trigger for keyboard navigation and screen reader support. Currently the menu has no visible trigger button and cannot be activated via keyboard.

```tsx
<PopupMenu>
  <PopupMenuOptions>
    <PopupMenuItem label={t`Show Details`} onClick={navigateToDetailsPage} />
  </PopupMenuOptions>
</PopupMenu>
```
_Precedent:_ the same pattern is already in merged code — `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/flavors/-components/FlavorListContainer.tsx:147`.
_Fix:_ Wrap with `PopupMenuToggle` and add a `Button` trigger, following `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketTableView.tsx:241`.

**CR2 — Network list lacks pagination (limit/marker) support** · Bug · `packages/aurora/src/server/Network/routers/networksRouter.ts:65`
The `list` procedure does not implement Neutron's pagination parameters (`limit`, `marker`, `page_reverse`). When there are more networks than Neutron's configured page size, users see only the first page with no way to retrieve the rest. The `NetworkQueryParametersSchema` at `packages/aurora/src/server/Network/types/network.ts:106` lacks these fields.

The Neutron API documents pagination at https://docs.openstack.org/api-ref/network/v2/#list-networks — list operations return a maximum number of items and provide `next`/`previous` links for navigation. The current implementation also merges two parallel requests (own and shared networks), which further complicates adding pagination since each would need separate marker tracking.
_Fix:_ Add `limit`, `marker`, and `page_reverse` to `NetworkQueryParametersSchema`, pass them to both own/shared requests, and return the pagination links so the client can implement "Load more" or marker-based navigation.

**CR3 — Network list excludes external networks that aren't shared** · Bug · `packages/aurora/src/server/Network/routers/networksRouter.ts:74-78`
The list procedure filters by `project_id` (own) or `shared=true`, which excludes external networks (`router:external=True`) that are not marked as shared. Neutron's default policy (`rule:external` in `get_network`) allows users to see external networks, but this filter hides them.

```ts
const requests = getNetworkListScopes(shared).map(async (scope) => {
  const scopeFilters =
    scope === "own"
      ? { ...openstackFilters, project_id, ...(shared === false && { shared: false }) }
      : { ...openstackFilters, shared: true }
```

The BFF documentation at `packages/aurora/docs/0017_networks_bff.md` states this is intentional — external networks are served by `network.floatingIp.listExternalNetworks`. However, a user looking at the Networks page cannot discover external networks they could attach ports to.
_Fix:_ Document this limitation in the UI (e.g., a note in the empty state or filters) or add a third scope that fetches `router:external=true` networks. If the current design is intentional, consider whether the floating-IP external-networks endpoint should be linked from the Networks page.

**CR4 — Descending sort puts null MTU first** · Bug · `packages/aurora/src/server/Network/helpers/networkHelpers.ts:142`
`sortNetworks` at line 142 multiplies `compareValues` result by `direction`. When a value is null, `compareValues` returns `1` (sort after). In descending mode (`direction = -1`), the multiplication `(-1) * 1 = -1` puts null values _before_ non-null values. The JSDoc at line 133 states "Missing values sort last" — violated for descending direction. `mtu` is the only nullable sort key (schema: `z.number().nullish()`), and no test covers the descending-null case.

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
_Fix:_ Guard nulls before applying direction so they always sort last:

```typescript
return [...networks].sort((a, b) => {
  const av = a[sortKey], bv = b[sortKey];
  if (av == null && bv == null) return 0;
  if (av == null) return 1;
  if (bv == null) return -1;
  return direction * compareValues(av, bv);
});
```

Also add a descending-null test.

**P1 — The description claims what the code doesn't do** · Process · PR body
The PR description lists this as a fix under "Changes Made", but `packages/aurora/src/client/routes/_auth/projects/$projectId/network/routers/$routerId.tsx` was not modified between the base commit (a21ba3ec) and head commit (9ed42505). The file already has the fix at the base commit.
_Fix:_ Remove this item from the "Fix" section of the PR description, or clarify that this fix was already merged separately and mention it only for context (not as a change made by this PR).

</details>

### 💡 &nbsp; Improvements

| #   | Severity   | Category     | Precedent     | Issue                                                                                                       | Location                                                                                                              |
| --- | ---------- | ------------ | ------------- | ----------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| I1  | 🟢 Low     | UI/UX        | existing code | Admin state shown as all-caps `UP`/`DOWN`, violating UX writing standards                                   | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:50`     |
| I2  | 🟢 Low     | UI/UX        | existing code | Status rendered as plain text instead of `Badge` component                                                  | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:49`     |
| I3  | 🟢 Low     | UI/UX        | existing code | Action `DataGridCell` missing `style={{ minWidth }}` — B.15 CRITICAL                                        | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:67`     |
| I4  | 🟢 Low     | UI/UX        | existing code | Error state uses raw `error?.message` as title; may expose API/exception text to users                      | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkSubnetsTable.tsx:35` |
| I5  | 🟢 Low     | Docs         | —             | README service-key lists do not include `"networks"` — consumers using `enabledServices` won't know the key | `packages/aurora/README.md:205`                                                                                       |
| I6  | ⚪ Trivial | Code Quality | —             | Import order: `zod` appears after i18n imports (B.13 Group 1)                                               | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/index.tsx:4`                            |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**I1 — All-caps `UP`/`DOWN` for admin state in table** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:50`
The network table row displays admin state as `` t`UP` `` / `` t`DOWN` ``. B.19 UX Writing states "Never all-caps (ever)" — status values are not an exception.

```tsx
<DataGridCell>{network.admin_state_up ? t`UP` : t`DOWN`}</DataGridCell>
```
_Precedent:_ the same pattern is already in merged code — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/routers/-components/RouterDetailsView.tsx:63`.
_Fix:_ Use sentence-case labels like `Enabled` / `Disabled` or `Active` / `Inactive`, matching other status displays.

**I2 — Status column uses plain text instead of Badge** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:49`
The Status column renders `network.status` as plain text. B.1 requires status indicators to use the `Badge` component for visual consistency. The same pattern exists in `RouterTableRow.tsx:42` (pre-existing).

```tsx
<DataGridCell>{network.status}</DataGridCell>
```
_Precedent:_ the same pattern is already in merged code — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/routers/-components/RouterTableRow.tsx:42`.
_Fix:_ Render status through `Badge` with appropriate variant based on status value (e.g., `success` for ACTIVE, `warning` for BUILD, `danger` for ERROR).

**I3 — Action cell missing minWidth style** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:67`
The action cell does not have `style={{ minWidth }}`. B.15 (marked CRITICAL) requires an explicit minWidth on action cells to prevent layout shifts when content changes. The same pattern exists in `RouterTableRow.tsx:60` (pre-existing).

```tsx
<DataGridCell onClick={(e) => e.stopPropagation()}>
```
_Precedent:_ the same pattern is already in merged code — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/routers/-components/RouterTableRow.tsx:60`.
_Fix:_ Add `style={{ minWidth: 48 }}` or similar to the action `DataGridCell`.

**I4 — Raw error.message as error title** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkSubnetsTable.tsx:35`
The error handler passes the raw API/exception message as the title. B.6 recommends static, controlled copy for user-visible error titles. The fallback string is reasonable, but `error?.message` can expose Neutron internal messages. The better pattern (static title, raw message in `body`) is used in storage components like `CorsRulesTab.tsx`.

```tsx
return (
  <Status
    status="error"
    title={error?.message || t`Failed to Load Subnets`}
```
_Precedent:_ the same pattern is already in merged code — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/routers/-components/RouterInterfacesTable.tsx:41`.
_Fix:_ Use a static title and move the raw message to body.

**I5 — README omits networks service key** · Docs · `packages/aurora/README.md:205`
Two consumer-facing lists document available `enabledServices` keys (lines 132 and 205) but neither includes `"networks"` (or `"routers"`, which is also missing — pre-existing). Consumers reading the README to configure `enabledServices` won't find this key.
_Fix:_ Add `"networks"` to both lines 132 and 205. Consider also adding `"routers"`.

**I6 — Import order violation — zod after i18n** · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/index.tsx:4`
`zod` (B.13 Group 1 — React / framework) is imported at line 4, after the i18n imports at lines 2-3. B.13 specifies Group 1 packages should come before i18n imports.

```tsx
import { createFileRoute } from "@tanstack/react-router"
import { t } from "@lingui/core/macro"
import { useLingui } from "@lingui/react/macro"
import { z } from "zod"
```
_Fix:_ Move `z from "zod"` before the `@lingui` imports.

</details>

---

## Solution Overview

<details>
<summary><strong>What was done</strong></summary>

This PR adds a read-only Networks management UI to Aurora Dashboard, backed by a full-featured tRPC BFF for Neutron Networks (L2). The BFF exposes seven procedures covering the complete network lifecycle (list, show, create, update, delete, tag management, and subnet listing), though only the read operations (`list`, `getById`, `listSubnets`) are wired into the UI. The write procedures (`create`, `update`, `delete`, `setTags`) exist in the BFF but have no UI yet — they'll ship in a follow-up.

The PR also extracts three shared helper modules (`requestHelpers`, `lookupHelpers`, and summary types) from the existing Routers BFF, eliminating duplication and setting up infrastructure the upcoming Ports BFF will reuse. CI shows 18 passing jobs, with 4 skipping (expected); the head commit is clean.

</details>

<details>
<summary><strong>How it is implemented</strong></summary>

## Server: Network BFF (`packages/aurora/src/server/Network`)

**New router** — `routers/networksRouter.ts`, mounted as `network.networks`, defines seven procedures:

```ts
export const networksRouter = {
  list: projectScopedProcedure
    .input(NetworkQueryParametersSchema)
    .query(async ({ input, ctx }): Promise<NetworkListItem[]> => {
      return withErrorHandling(async () => {
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
          const response = await requestOrThrow(
            () => network.get(withQuery(NETWORKS_BASE_URL, queryParams)),
            NetworkErrorHandlers.list
          )
          const data = await response.json()
          return parseOrThrow(NetworkListResponseSchema, data, "networksRouter.list").networks
        })

        const networks = sortNetworks(mergeNetworks(...(await Promise.all(requests))), input.sort_key, input.sort_dir)
```

The `list` procedure merges two parallel requests (own networks filtered by `project_id`, and shared networks with `shared=true`) to surface both networks the project owns and networks other projects have shared with it, because Neutron's `project_id` filter hides shared networks. The helper `getNetworkListScopes` at `packages/aurora/src/server/Network/helpers/networkHelpers.ts:106` determines which requests to send based on the `shared` input filter. After merging by ID (first occurrence wins), the BFF re-sorts the list by the requested `sort_key` / `sort_dir`, since concatenation breaks Neutron's per-request sort order.

**Subnet name enrichment:** After filtering, `list` collects every subnet ID referenced by the returned networks and resolves their names with one batched lookup — `fetchSubnetSummaries` at `packages/aurora/src/server/Network/helpers/lookupHelpers.ts:60` sends `GET /v2.0/subnets?id=a&id=b&fields=id&fields=name` in 50-ID chunks. The lookup is best-effort: a failure returns `[]` so the UI falls back to showing IDs. Each network's `subnet_details` array matches the order and IDs of its `subnets` field, with `name` set to `undefined` when the lookup failed or returned an empty name.

```ts
const networks = sortNetworks(mergeNetworks(...(await Promise.all(requests))), input.sort_key, input.sort_dir)
const filteredNetworks = filterBySearchParams(networks, searchTerm, ["id", "name", "description"])

// Subnet names are resolved in one batched, best-effort lookup for the whole list
const subnets = await fetchSubnetSummaries(
  network,
  collectSubnetIds(filteredNetworks),
  ["id", "name"],
  "networksRouter.list.subnets"
)
```

**Schemas and validation** — `types/network.ts` defines Zod schemas for all request/response shapes: `Network` (185 lines), `NetworkListItem` (adds `subnet_details`), `NetworkSubnet`, and input schemas for create/update/delete/setTags. Tags are validated to exclude commas (Neutron's tag filters are comma-separated) and trimmed/deduplicated before sending.

**Error handling** — `helpers/networkHelpers.ts` builds operation-specific error handlers on the shared `ErrorHandler("Network", overrides)` factory:

```ts
type ErrorResponse = { status?: number; statusText?: string }

const QUOTA_EXCEEDED_MESSAGE =
  "Network quota exceeded. Delete unused resources or contact an administrator to increase the quota."

const ADMIN_ONLY_MESSAGE =
  "You are not allowed to perform this change. Shared and external networks, provider attributes and some MTU changes require admin rights."

/**
 * Neutron reports OverQuota as 409 Conflict (not 413), so every network 409 override
 * checks for a quota message first and only then falls back to the operation-specific text.
 */
const conflict = (message: string) => (response: ErrorResponse) =>
  new TRPCError({
    code: HTTP_STATUS_ERROR_MAP[409],
    message: /quota/i.test(response.statusText ?? "") ? QUOTA_EXCEEDED_MESSAGE : message,
  })

const forbidden = (message: string) => (response: ErrorResponse) =>
  new TRPCError({
    code: HTTP_STATUS_ERROR_MAP[403],
    message: `${message}${response.statusText ? ` (${response.statusText})` : ""}`,
  })

const notFound = (message: (resourceLabel?: string) => string) => (_response: ErrorResponse, resourceLabel?: string) =>
```

Overrides: 403 on create/update explains that `shared`, `router:external`, `provider:*` attributes and some MTU changes require admin rights (appends Neutron's message). 404 on get/update/delete/setTags interpolates the network ID. 409 checks Neutron's message for "quota" first (Neutron reports OverQuota as 409 Conflict), then returns operation-specific messages.

**Extracted shared helpers** — three modules now serve both the Networks and Routers BFFs, eliminating duplication:

1. `helpers/requestHelpers.ts` — `requestOrThrow` (maps `SignalOpenstackApiError` through an operation's error handler), `pickDefined` (strips `undefined` keys from request bodies), `chunk` (splits IDs for batched requests), `withQuery` (appends `URLSearchParams`).
2. `helpers/lookupHelpers.ts` — `fetchNetworkSummaries`, `fetchSubnetSummaries`, `fetchSecurityGroupSummaries` — best-effort batched name lookups for resources referenced by other resources. Each sends one request per 50-ID chunk and returns `[]` on any failure.
3. `types/index.ts` — `NetworkSummary`, `SubnetSummary`, `SecurityGroupSummary` schemas (moved from `types/router.ts` where they were Routers-only).

```ts
/**
 * Runs a Neutron request and maps any failure through the operation's error handler.
 *
 * signal-openstack rejects every non-2xx response with SignalOpenstackApiError, so a plain
 * `if (!response.ok)` check never runs and the error would reach `withErrorHandling` as INTERNAL_SERVER_ERROR.
 * The error's `message` is Neutron's own message parsed from the JSON body (e.g. NeutronError.message
 * "Quota exceeded for resources: ['router']."), so it is passed to the handler as `statusText`.
 * Network failures are wrapped by the client as SignalOpenstackApiError with status 500 and end up in the default handler.
 * The `!response.ok` branch only guards against clients that resolve with error responses.
 */
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

  if (!response.ok) throw handleError(response, resourceLabel)
  return response
}
```

The Routers BFF (`routers/routersRouter.ts`) now imports these instead of defining its own copies — `packages/aurora/src/server/Network/helpers/routerHelpers.ts` dropped ~90 lines (the old `requestOrThrow`, `pickDefined`, `chunk`, `fetchNetworkSummaries`, and the summary type imports).

**Registration** — `routers/index.ts:17` mounts the router at `network.networks`.

## Client: Networks UI (`packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks`)

**Routes:**

- `networks.tsx` — layout route, provides breadcrumb and error boundary.
- `networks/index.tsx` — list route. URL params: `search`, `sortBy` (name/status/mtu), `sortDirection`, `page`, `status` (ACTIVE/DOWN/BUILD/ERROR), `shared` (true/false). Validates search params with Zod; invalid params become `undefined` (graceful degradation).
- `networks/$networkId.tsx` — details route. Prefetches `network.networks.getById` in the loader via `context.trpcClient`, then re-fetches with `useQuery` for reactivity. Tab state in `?tab=` (default "subnets", the only tab).

```tsx
export const Route = createFileRoute("/_auth/projects/$projectId/network/networks/")({
  staticData: {
    section: "network",
    service: "networks",
    analytics: {
      name: "network.networks.list",
    },
  } satisfies RouteInfo,
  validateSearch: (search) => {
    const result = networksSearchSchema.safeParse(search)
    if (result.success) return result.data
    return {
      ...search,
      search: validOrUndefined(networksSearchFields.search, search.search),
      sortBy: validOrUndefined(networksSearchFields.sortBy, search.sortBy),
      sortDirection: validOrUndefined(networksSearchFields.sortDirection, search.sortDirection),
      page: validOrUndefined(networksSearchFields.page, search.page),
      status: validOrUndefined(networksSearchFields.status, search.status),
      shared: validOrUndefined(networksSearchFields.shared, search.shared),
    }
  },
  head: () => ({ meta: [{ title: t`Networks` }] }),
  component: RouteComponent,
})
```

**List view** (`-components/NetworksList.tsx`, `NetworkListContainer.tsx`, `NetworkTableRow.tsx`):

- Columns: Name (with ID below in muted text), Status, Admin State (UP/DOWN), Subnets (comma-separated names, falls back to IDs when `name` is `undefined`), Shared (Yes/No), External (Yes/No/—), MTU, Actions (Show Details button).
- Search and filters in `FilterToolbar`; sorting and pagination in `DataGrid`.
- Fetches via a `Promise` + `use()` inside `ErrorBoundary` + `Suspense` (React 19 pattern). A `FORBIDDEN` response renders an inline message, not an error boundary throw.

```tsx
    status,
    shared: shared === undefined ? undefined : shared === "true",
  }

  return client.network.networks.list
    .query(query)
    .then((networks) => ({ networks, listError: undefined }))
    .catch((err: unknown) => {
      if (err instanceof TRPCClientError && err.data?.code === "FORBIDDEN") {
        return { networks: [], listError: err.message }
      }
      throw err
    })
}

const isStatusFilter = (value: string): value is NetworkStatusFilter =>
  (NETWORK_STATUS_FILTER_VALUES as readonly string[]).includes(value)

const isSharedFilter = (value: string): value is NetworkSharedFilter =>
  (NETWORK_SHARED_FILTER_VALUES as readonly string[]).includes(value)

function NetworksContent({
  networksPromise,
  searchTerm,
  setSearchTerm,
  sortSettings,
  handleSortChange,
  filterDefinitions,
  selectedFilters,
```

**Details view** (`-components/NetworkDetailsView.tsx`, `NetworkSubnetsTable.tsx`):

- Overview section: `DescriptionList` with Name, ID (clipboard), Project ID (clipboard), Description, Status, Admin State, MTU, Shared, External, Port Security, Availability Zones, Tags, Created/Updated timestamps. Missing/null extension fields show "—".
- `TabNavigation` for the Subnets tab (more tabs — Ports, Segmentation — mentioned in issue #1019 but not in this PR).
- Subnets tab: `DataGrid` with Name, CIDR, IP Version, Gateway IP, DHCP (Enabled/Disabled). Fetches `network.networks.listSubnets`. Loading/error/empty states.

```tsx
export function NetworkDetailsView({ network, activeTab, onTabChange }: NetworkDetailsViewProps) {
  const { t } = useLingui()
  const projectId = useProjectId()

  const {
    data: subnets = [],
    isLoading: isLoadingSubnets,
    isError: isSubnetsError,
    error: subnetsError,
    refetch: refetchSubnets,
  } = trpcReact.network.networks.listSubnets.useQuery({ project_id: projectId, network_id: network.id })

  const yesNo = (value?: boolean | null): string =>
    value === undefined || value === null ? "—" : value ? t`Yes` : t`No`

  const enabledDisabled = (value?: boolean | null): string =>
    value === undefined || value === null ? "—" : value ? t`Enabled` : t`Disabled`

  const basicInfoItems: DetailItem[] = [
    { label: t`Name`, value: network.name || "—" },
    { label: t`ID`, value: <ClipboardText text={network.id} /> },
    { label: t`Project ID`, value: <ClipboardText text={network.project_id} /> },
    { label: t`Description`, value: network.description || "—" },
    { label: t`Status`, value: network.status },
    { label: t`Admin State`, value: network.admin_state_up ? t`UP` : t`DOWN` },
    { label: t`MTU`, value: network.mtu ?? "—" },
    { label: t`Shared`, value: yesNo(network.shared) },
```

**Navigation integration:**

- `buildNavSections.ts` adds a "Networks" entry as the first item in the Network section, shown when `isEnabled("networks")` and the network service is in the catalog.
- Project overview (`$projectId/index.tsx`) adds a "Networks" service card.

Both require `networks` in `enabledServices` to appear.

```ts
...(isEnabled("networks")
  ? [
      {
        service: "networks",
        label: t`Networks`,
        navigate: (nav: NavigateFn) =>
          nav({ to: "/projects/$projectId/network/networks", params: { projectId } }),
        params: { projectId },
      },
    ]
  : []),
```

## Shared packages, config, docs

- `.changeset/neutron-networks-management.md` — minor bump for `@cobaltcore-dev/aurora`.
- `packages/aurora/docs/0017_networks_bff.md` — 495-line BFF implementation guide: API contract, error handling, data types, frontend integration, testing notes.
- i18n: `packages/aurora/src/locales/{en,de}/messages.po` add 84 strings each ("Networks", "Subnets", "Admin State", column headers, form labels).

## Tests

- Server: `networksRouter.test.ts` (701 lines), `networkHelpers.test.ts` (236 lines), `network.test.ts` (246 lines), `lookupHelpers.test.ts` (150 lines), `requestHelpers.test.ts` (95 lines) — procedure logic, own/shared merge, re-sort, batched lookups, error mapping, schema validation.
- Client: `NetworksList.test.tsx` (436 lines), `NetworkListContainer.test.tsx` (149 lines), `NetworkTableRow.test.tsx` (154 lines), `NetworkDetailsView.test.tsx` (230 lines), `NetworkSubnetsTable.test.tsx` (112 lines), `buildNavSections.test.ts` updated (15 additions) — rendering, URL state, filters, pagination, tab switching, empty/error states.
- `routerHelpers.test.ts` updated (1 addition, 84 deletions) — old tests for extracted helpers removed.

All tests colocated with source as `*.test.ts(x)`.

</details>

<details>
<summary><strong>What it affects (blast radius)</strong></summary>

## Contract changes and consumers

**New tRPC procedures** (all under `network.networks`): `list`, `getById`, `create`, `update`, `delete`, `setTags`, `listSubnets`. Consumed only by this PR's own client routes — no external consumers found in the monorepo at the head commit.

**New shared types** exported from `packages/aurora/src/server/Network/types/index.ts`:

- `NetworkSummary`, `NetworkSummarySchema`, `NetworkSummaryListResponseSchema`
- `SubnetSummary`, `SubnetSummarySchema`, `SubnetSummaryListResponseSchema`
- `SecurityGroupSummary`, `SecurityGroupSummarySchema`, `SecurityGroupSummaryListResponseSchema`

These were moved from `types/router.ts` (where they were private to the Routers BFF) to the shared types index. **Existing consumer:** `packages/aurora/src/server/Network/helpers/routerHelpers.ts` now imports them from `types/index` instead of from `types/router`. The change is internal to the Network domain; no consumers outside `packages/aurora/src/server/Network` reference these types.

**New shared helpers** in `packages/aurora/src/server/Network/helpers`:

- `requestHelpers.ts`: `requestOrThrow`, `pickDefined`, `chunk`, `withQuery`, `NetworkErrorHandler` (type)
- `lookupHelpers.ts`: `fetchNetworkSummaries`, `fetchSubnetSummaries`, `fetchSecurityGroupSummaries`, `LOOKUP_CHUNK_SIZE`

These extracted functions are now imported by both `routers/networksRouter.ts` and `routers/routersRouter.ts`. No external packages import them.

**Permission keys** — `network:networks:read`, `network:networks:list`, `network:networks:create`, `network:networks:update`, `network:networks:delete` already exist in `packages/aurora/src/server/Network/routers/permissionRouter.ts` (added in a prior commit, unchanged by this PR). The keys map to Neutron rules `get_network`, `create_network`, `update_network`, `delete_network`.

**Service key** — `"networks"` is the new service key for `enabledServices`. It gates visibility of the nav entry and project overview card. Consumers (e.g. `apps/dashboard`) that restrict services with `enabledServices` must add `"networks"` to show this feature.

**Documentation gap:** `packages/aurora/README.md` line 210 lists available service keys ("images", "flavors", "securitygroups", ...) but does **not** include `"networks"`. Consumers reading the README won't know the key exists. The changeset and BFF doc mention it, but the public API contract (README) is stale.

## Blast radius summary

- **Low risk:** All new tRPC procedures and client routes are net-new — no existing routes or procedures were modified.
- **Refactoring risk (low):** The extracted helpers (`requestHelpers`, `lookupHelpers`, summary types) are consumed only within the Network domain. The Routers BFF was updated to use them, and its tests still pass (1 test updated, 84 obsolete lines removed). The extraction is a pure refactor — no behavior changes for routers.
- **Consumer impact:** Apps that use `enabledServices` and want to show Networks must add `"networks"` to the array. Apps that don't restrict services (or already allow all) will see the Networks UI automatically if the Neutron network service is in the OpenStack catalog.

</details>

---

## QA Test Plan

<details>
<summary><strong>Core Path</strong></summary>

1. Navigate to a project's overview page. Verify a "Networks" card appears in the Network section (requires `networks` in `enabledServices` or no service restriction).
2. Click the Networks card or the "Networks" entry in the side navigation. The list view loads, showing Name/ID, Status, Admin State, Subnets (names or IDs), Shared, External, MTU columns.
3. Type a search term (e.g. part of a network name or ID) in the search box. The list filters client-side to matching networks.
4. Select a Status filter (e.g. ACTIVE) from the dropdown. The list re-fetches from the BFF with `?status=ACTIVE`.
5. Select "Shared: Yes" from the Shared filter. The list re-fetches, showing only shared networks (BFF sends only `?shared=true`, not the own-networks request).
6. Click a column header (e.g. "Name" or "MTU") to sort. The URL updates with `?sortBy=...&sortDirection=...`, and the BFF re-sorts the merged list.
7. Click a network row or the "Show Details" button. The details route loads, showing the network's overview (Name, IDs with clipboard icons, Status, Admin State, MTU, Shared, External, Port Security, timestamps).
8. Check the Subnets tab (default). A table shows the network's subnets: Name, CIDR, IP Version, Gateway IP, DHCP state. If the network has no subnets, an empty state message appears.
9. Navigate back to the list. Change the page number in the URL or via pagination controls. The list paginates client-side (50 per page).

</details>

<details>
<summary><strong>Edge Cases</strong></summary>

- Network with no subnets: the list's Subnets column shows "—", and the details Subnets tab shows an empty state (`packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkSubnetsTable.tsx:74` renders `Status` with `status="empty"`).
- Subnet name lookup fails or returns empty name: the list and details Subnets tab fall back to showing the subnet ID (`packages/aurora/src/server/Network/helpers/networkHelpers.ts:151` — `applySubnetNames` sets `name: undefined` when not in the lookup result; UI checks `subnet.name` and renders the ID).
- User lacks permission to list networks: the BFF returns `FORBIDDEN`, and the list view renders an inline "Access forbidden" message inside the page, not an error boundary (`packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:85` checks `error.data?.code === 'FORBIDDEN'`).
- Network has extension fields (MTU, QoS Policy, DNS Domain) that are `null` or missing: the details view shows "—" for each (`packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkDetailsView.tsx:79-91` — every extension field uses `?? "—"` or a ternary).
- Admin-only attributes (e.g. `provider:network_type`) are not visible to non-admin users: the details view omits them (not in the `DetailItem[]` arrays), and the schema marks them as optional (`packages/aurora/src/server/Network/types/network.ts:52-54`).
- Shared filter set to "No": BFF sends only `?project_id={project_id}&shared=false`, skipping the shared-networks request (`packages/aurora/src/server/Network/helpers/networkHelpers.ts:11` — `getNetworkListScopes` returns `["own"]`).
- Network created_at/updated_at missing: details view shows "—" (`packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkDetailsView.tsx:52` — `formatDateTime` returns "—" when value is falsy).
- Subnets tab fetch fails: the tab shows an error state with a retry button (`packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkSubnetsTable.tsx:31-44` renders `Status` with `status="error"`).
- Empty network name: list shows the network ID as fallback (`packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:47` — `network.name || network.id`), details show "—" for the Name label (`NetworkDetailsView.tsx:73`).
- Invalid URL search params (e.g. `?sortBy=invalid`): route's `validateSearch` coerces them to `undefined`, so the UI ignores them and uses defaults (`packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/index.tsx:36-47`).
- Deployment has more networks than Neutron's page limit (typically 1000) — list shows only the first page with no indication more exist (CR2)
- User wants to attach a port to an external floating-IP pool network — it does not appear in the Networks list (CR3)

</details>

---

## Checked and dismissed

<details>
<summary><strong>Candidates scored below 50 (1)</strong></summary>

| Score | Candidate                                                                                                                            | Location                                                                                                        | Why             |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------- | --------------- |
| 0     | When a user is on page 3 of networks but the page parameter is updated by another navigation, safePage will clamp to totalPages but… | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:122` | False positive. |

</details>

---

_Analyzed 2026-10-30 · commit `9ed42505` · read-only · skill: review-and-comment-pr_

<!-- related:auto — generated from pr/issue properties by tools/update-related.py; do not edit by hand -->
## Related

- plan · 2026-10-12 · [2026-10-12-networks-epic-1019-analysis](../../plans/2026-10-12-networks-epic-1019-analysis.md)
- plan · 2026-10-12 · [2026-10-12-networks-phase-1-read-operations](../../plans/2026-10-12-networks-phase-1-read-operations.md)
- pr-report · 2026-10-17 · [1386-network-and-verify-do-not-merge](1386-network-and-verify-do-not-merge.md)
- pr-report · 2026-10-23 · [1383-neutron-networks-bff-read-only-networks-page](1383-neutron-networks-bff-read-only-networks-page.md)
