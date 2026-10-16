---
type: pr-report
date: 2026-10-16
status: open
pr: [1377]
issue: [1381, 1382]
author: mark-karnaukh-extern-sap
branch: mark-manage-ports-interface
---

# PR #1377: feat(aurora): add Neutron Ports BFF and read-only Ports page (list & details)

**Author:** mark-karnaukh-extern-sap · **Status:** draft · **Base:** `main` ← `mark-manage-ports-interface`
**Size:** 42 files, +5094 / −247 · **Created:** 2026-10-09 · [View on GitHub](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377)

---

## PR Review Report

### ⚖️ &nbsp; Verdict

> Recommendation: **🔴 Request Changes** &nbsp;&nbsp;&nbsp;&nbsp; Confidence to Merge: **Medium**
>
> A carefully built feature. It has a tidy BFF with batched best-effort name lookups, a shared-helper refactor that keeps Routers working, and a list and details UI that already avoids most of the review points raised on the Routers PR (#1355). All CI jobs are green, and the acceptance criteria of #1381 and #1382 are met on paper. The main blocker is that `network.ports.list` reads only the first page Neutron returns. On deployments that cap list size, ports and search results silently go missing. Three further 🟡 items need fixing:
>
> - 401 and 403 errors are rendered inline.
> - The details route fetches the port twice.
> - The PR conflicts with the open Networks PRs #1383 and #1385; with #1383 the combined code wouldn't typecheck.
>
> Confidence is Medium because the PR is still a draft and the pagination impact depends on the deployment's Neutron configuration.

### 🔧 &nbsp; Required Changes

| #   | Severity    | Category    | Issue                                                                                     | Location                                                                                    |
| --- | ----------- | ----------- | ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| CR1 | 🟠 Major    | Bug         | Ports list reads one Neutron page and ignores `ports_links`, so ports are silently truncated | `packages/aurora/src/server/Network/routers/portsRouter.ts:65`                              |
| CR2 | 🟡 Moderate | UI/UX       | 401/403 handled inline (details error view, list `FORBIDDEN` status) — B.6 Reject         | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:68`  |
| CR3 | 🟡 Moderate | Performance | Details route fetches `getById` twice (loader for the title + component query)            | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:127` |
| CR4 | 🟡 Moderate | Code Quality | Conflicts with open PRs #1385 / #1383; #1383 imports `requestOrThrow` this PR removes    | `packages/aurora/src/server/Network/helpers/routerHelpers.ts`                               |
| P1  | —           | Process     | PR is still a draft                                                                       | PR state                                                                                    |
| P2  | —           | Process     | Router details tab-in-URL change isn't in the description or changeset                    | PR body                                                                                     |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**CR1 — Ports list ignores Neutron pagination** · Bug · `packages/aurora/src/server/Network/routers/portsRouter.ts:65`
`list` sends a single `network.get(withQuery(PORTS_BASE_URL, queryParams))` and parses only `{ ports }`. `PortListResponseSchema` (`types/port.ts:77`) has no `ports_links`, and nothing follows the `next` link. The [Networking API reference](https://docs.openstack.org/api-ref/network/v2/index.html) (Pagination) says:

- "list operations will return a maximum number of items at a time"
- "If the client requests a limit beyond the maximum limit configured by the deployment, the server returns the maximum limit number of items"
- "list responses contain atom `next` links"

On a deployment with a max limit, the Ports page shows only the first page with no indication. The BFF-side `searchTerm` filter (`portHelpers.ts:148`) then searches only that page, so a port that exists returns "No ports match your search". This undermines #1382's "list view shows the agreed columns for the current project". No test covers a paginated response. Expect pushback: the routers, floating IP and security group lists have the same gap; only the Glance images router follows `next`.
_Fix:_ loop on the `next` link of `ports_links` (or `limit` + `marker`) until it is absent, as `imageRouter.ts` does for Glance (including `validateRelativeUrl`). Add `ports_links` to the schema and a test with a two-page response.

**CR2 — 401/403 handled inline** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:68`
`.github/copilot-instructions.md` B.6 says: "**Reject** … a 401/403 handled inline instead of via redirect / page-level info `Message`".

- `$portId.tsx:68-71` renders `FORBIDDEN` ("Access to this port is not permitted.") and `UNAUTHORIZED` as text inside `RouteIdLevelDefaultError`, with no redirect and no info `Message`.
- `PortsList.tsx:54-55` turns a `FORBIDDEN` list error into `listError`, rendered at `PortsList.tsx:115-117` as `<Status status="error" title={t`Failed to Load Ports`} … />`.

Copilot raised both on #1355 (`RoutersList.tsx:102`, `$routerId.tsx:71`), and the author declined for consistency with the other lists.
_Fix:_ redirect `UNAUTHORIZED` to sign-in, and render `FORBIDDEN` as a page-level info `Message`, as B.6 prescribes. If the team keeps the current pattern, record that as an explicit exception to B.6.

**CR3 — Duplicate `getById` on the details route** · Performance · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:127`
The loader calls `context.trpcClient?.network.ports.getById.query(...)` only to set the page title. The component then calls `trpcReact.network.ports.getById.useQuery` with the same input (`$portId.tsx:154`). The raw client doesn't share the React Query cache, so every details page open sends two BFF requests. Each one makes four Neutron calls: the port, plus network, subnet and security group lookups. Copilot raised this on #1355 (`$routerId.tsx:133`), and the author declined, citing the `$flavorId.tsx` pattern.
_Fix:_ prefetch into the query cache in the loader (`queryClient.ensureQueryData` via the tRPC utils) and read it in the component, or take the title from the component query (`useSetBreadcrumb` already does).

**CR4 — Conflicts with the open Networks PRs** · Code Quality · `packages/aurora/src/server/Network/helpers/routerHelpers.ts`
`git merge-tree` against **#1385** (`9ed42505`) reports conflicts in:

- `server/Network/routers/index.ts`
- `buildNavSections.test.ts`
- the locale catalogs

#1385 also carries an identical `requestHelpers.ts`/`lookupHelpers.ts` refactor.

Against **#1383** (`3e32ab04`), git reports conflicts only in `routers/index.ts` and the locale catalogs. The worse problem is that `networksRouter.ts:15` in #1383 does `import { requestOrThrow } from "../helpers/routerHelpers"`, which this PR removes (moved to `requestHelpers.ts`). The combined tree fails typecheck even where git merges cleanly.
_Fix:_ agree a merge order with the Networks PR. Land the shared-helper refactor once, in whichever PR merges first, and rebase the other onto it, switching its import to `../helpers/requestHelpers`.

**P1 — Draft** · Process · PR state
The PR is still marked as a draft.
_Fix:_ mark it ready for review once the items above are settled.

**P2 — Undescribed router details change** · Process · PR body
The head commit `512f01b1` ("fix(portal): keep router details tab in URL search params") changes Routers behaviour:

- `$routerId.tsx` gets a `validateSearch` for `?tab=` and navigates with `replace: true`.
- `RouterDetailsView` becomes controlled through new required props `activeTab` and `onTabChange`.

The description mentions only the literal-route-id fix in `$routerId.tsx`, and the changeset doesn't mention the change either.
_Fix:_ add the change to the description and the changeset, or move it to its own PR.

</details>

### 💡 &nbsp; Improvements

| #   | Severity   | Category     | Issue                                                                                  | Location                                                                                                         |
| --- | ---------- | ------------ | -------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| I1  | 🟢 Low     | UI/UX        | Out-of-range page reset pushes a history entry (Back-button loop)                      | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortsList.tsx:111`        |
| I2  | 🟢 Low     | Code Quality | "Log in again" wording — Quick Reject: use "Sign in"                                   | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:71`                       |
| I3  | 🟢 Low     | Code Quality | `PopupMenu` without `PopupMenuToggle` trigger — Quick Reject / B.14                    | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortTableRow.tsx:79`      |
| I4  | 🟢 Low     | UI/UX        | Port status rendered as plain text, not a `Badge` (B.1)                                | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortTableRow.tsx:77`      |
| I5  | 🟢 Low     | UI/UX        | `gap="1"` is not an approved Stack gap — Quick Reject / B.3                            | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortTableRow.tsx:57`      |
| I6  | 🟢 Low     | Code Quality | One failed lookup chunk discards the names from all chunks                             | `packages/aurora/src/server/Network/helpers/lookupHelpers.ts:34`                                                 |
| I7  | 🟢 Low     | Docs         | `ports` service key missing from the README's service key lists                        | `packages/aurora/README.md:183`                                                                                  |
| I8  | 🟢 Low     | Code Quality | Port-local tRPC error-code map/retry set duplicated from `$routerId.tsx`               | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:13`                       |
| I9  | 🟢 Low     | UI/UX        | `PortsErrorComponent` shows the default 404 "Resource Not Found" for any error         | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports.tsx:14`                               |
| I10 | 🟢 Low     | UI/UX        | Status is the second-to-last column (B.15: near the left)                              | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortListContainer.tsx:83`  |
| I11 | ⚪ Trivial | Code Quality | `zod` imported after the Lingui imports (B.13 order)                                   | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/index.tsx:4`                          |
| I12 | ⚪ Trivial | Code Quality | `../../trpc` traversal import instead of `@/` — Quick Reject                           | `packages/aurora/src/server/Network/types/port.ts:2`                                                             |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**I1 — Page reset adds a history entry** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortsList.tsx:111`
The effect calls `onPageChange(1)` when `currentPage > totalPages`. `handlePageChange` (`PortsList.tsx:226`) navigates without `replace: true`, while sort and search both use `replace: true`. Opening a stale `?page=9` on a two-page list pushes a new entry. Back then returns to `?page=9`, the effect fires again, and the user is bounced forward. This needs a hand-edited or outdated URL, so it is rare.
_Fix:_ pass `replace: true` for the automatic reset (for example, a `replace` flag on `onPageChange`).

**I2 — "Log in" wording** · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:71`
`t`The session has expired. Log in again to continue.`` breaks the Quick Reject item "String using … `"Sign In"`/`"Log in"` (use `"Sign in"`)". `routers/$routerId.tsx` contains the identical string.
_Fix:_ "The session has expired. Sign in again to continue."

**I3 — Row menu without `PopupMenuToggle`** · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortTableRow.tsx:79`
The Quick Reject item "`PopupMenu` without `PopupMenuToggle` as trigger" applies, as does B.14: "Context menus **must** use `<PopupMenuToggle as="div"><Button icon="moreVert" /></PopupMenuToggle>`". The row uses a bare `<PopupMenu><PopupMenuOptions>…`. Copilot raised this on #1355 (`RouterTableRow.tsx:82`), and the author declined because Juno's default toggle is a `moreVert` button. The Router and Floating IP rows do the same.
_Fix:_ add the explicit `PopupMenuToggle`/`Button icon="moreVert"` trigger with an `aria-label`.

**I4 — Status not a `Badge`** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortTableRow.tsx:77`
The B.1 component table maps "Status indicators" to `Badge`. The list renders `{port.status}` as plain text, and so does the details view (`PortDetailsView.tsx:70`). Copilot raised this on #1355, and the author deferred it to a change across all lists.
_Fix:_ render the status with a `Badge` (e.g. ACTIVE as success, DOWN/ERROR as warning/danger), or track it in that cross-list change.

**I5 — Unapproved Stack gap** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortTableRow.tsx:57`
B.3 allows Stack gaps `0.5`, `2`, `4` and `6`, with "Reject any … not listed above", and the Quick Reject list includes "Ad-hoc spacing value not in the approved list". `gap="1"` appears here and at `PortDetailsView.tsx:51`. `RouterTableRow.tsx` has the same precedent.
_Fix:_ use `gap="0.5"` or `gap="2"`.

**I6 — Lookup failure is all-or-nothing** · Code Quality · `packages/aurora/src/server/Network/helpers/lookupHelpers.ts:34`
`fetchSummaries` runs every chunk in one `Promise.all` inside `try { … } catch { return [] }`. With more than 50 unique IDs, one failed chunk throws away names from the chunks that succeeded, and every row falls back to IDs. Through the refactor this now also applies to the Routers list.
_Fix:_ use `Promise.allSettled` and keep the fulfilled chunks.

**I7 — README service keys** · Docs · `packages/aurora/README.md:183`
The changeset tells consumers to add `ports` to `enabledServices`. The README's "Service key reference" (`:183`) and "Available service keys" (`:210`) lists don't include it. Per `CLAUDE.md`, the README is the consumer contract. `routers` was already missing before this PR.
_Fix:_ add `"routers"` and `"ports"` to both lists.

**I8 — Duplicated error-code handling** · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:13`
`HTTP_STATUS_BY_TRPC_CODE`, `RETRYABLE_TRPC_CODES` and `getTrpcErrorCode` are copied from `routers/$routerId.tsx`. The comment at `:29-31` is accurate: `useErrorTranslation` only knows the `FLAVORS_*` codes, so this isn't a clean B.17 violation. A third copy will arrive with every new details page.
_Fix:_ extract a shared util, or extend `useErrorTranslation` to raw tRPC codes.

**I9 — Subtree error shown as 404** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports.tsx:14`
`PortsErrorComponent` renders `<RouteIdLevelDefaultError action={…} />` without `code`, `errorTitle` or `errorDescription`. The component defaults to 404 "Resource Not Found", so any render error that reaches it is reported as missing. Reach is narrow, because the list and `$portId` have their own boundaries. `$portId.tsx:79-80` already handles this with `code={statusCode ?? null}`. `routers.tsx` has the same pattern.
_Fix:_ pass `code={null}` and a generic title and description.

**I10 — Status column position** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortListContainer.tsx:83`
B.15 says "Status/state columns: near the left (users scan for status first)". Status is the sixth of seven columns here, but #1382 and epic #816 prescribe exactly this order.
_Fix:_ none required in code. Confirm with the product owner which rule wins, then either move the column or note the exception.

**I11 — Import order** · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/index.tsx:4`
B.13 puts `zod` in group 1 (framework), before Lingui. Here it comes after `@lingui/core/macro` and `@lingui/react/macro`.
_Fix:_ move `import { z } from "zod"` above the Lingui imports.

**I12 — Relative traversal import** · Code Quality · `packages/aurora/src/server/Network/types/port.ts:2`
`import { projectScopedInputSchema } from "../../trpc"` breaks the Quick Reject item "Import using `../../` traversal beyond one level instead of `@/`". Copilot raised the same in `router.ts` on #1355, and the author declined for folder consistency (`floatingIp.ts` and `securityGroup.ts` do the same).
_Fix:_ `import { projectScopedInputSchema } from "@/server/trpc"`.

</details>

---

## Solution Overview

<details>
<summary><strong>What was done</strong></summary>

**BFF.** A new `network.ports` tRPC router has five project-scoped procedures: `list`, `getById`, `create`, `update` and `delete`.

- `list` always filters by the current project, can be narrowed to one network, accepts Neutron filters and sorting, and adds a BFF-side search.
- `list` and `getById` enrich every port with names: the network name, plus the subnet name and IP version of each fixed IP. `getById` also resolves security group names.
- Name lookups are batched, in chunks of 50 IDs, and best-effort: when a lookup fails, the UI falls back to the ID.
- Writes go through Zod schemas that validate IPs, CIDRs and MAC addresses.
- Port-specific error messages are built on the shared network `ErrorHandler`: quota exceeded, IP/MAC in use, port owned by a router.

**Refactor.** The request helpers and name lookups that the Routers BFF used privately moved into shared modules, so Ports and Routers share them:

- `requestHelpers.ts`: `requestOrThrow`, `pickDefined`, `chunk`, `withQuery`
- `lookupHelpers.ts`: network, subnet and security group summaries
- `types/index.ts`: summary schemas

Routers now imports from these modules. One behavioural difference: its lookups are now chunked as well.

**UI.** Ports appears under Network in the side navigation and as a card on the project overview, both behind `isEnabled("ports")`. The list view has these columns: Name / ID, Description, Network, Fixed IPs / Subnet, Device Owner / ID, Status. Search, sort and page live in the URL, and pagination is client-side at 50 rows per page. The list component accepts an optional `networkId` that scopes the query and hides the Network column, ready for the "Ports" tab of #1019. The details view lists all fields from the epic, with copy-to-clipboard for IDs, IPs and the MAC address.

**Routers side changes.**

- `createFileRoute()` in `$routerId.tsx` now takes a string literal, so the route generator works again.
- The router details tab is now kept in the URL (`?tab=`). The description doesn't mention this (see P2).

**Docs and release.** `docs/0017_ports_bff.md` is new and `0010_routers_bff.md` points at the moved helpers. A `minor` changeset for `@cobaltcore-dev/aurora` is included.

**CI.** All checks pass on `512f01b1`: lint, type-check, format, check-i18n, test, build, licenses and CodeQL.

</details>

<details>
<summary><strong>How it is implemented</strong></summary>

**List: project filter, name enrichment, then search** (`packages/aurora/src/server/Network/routers/portsRouter.ts:60`)

```ts
        const { searchTerm, ...openstackFilters } = input
        const network = getNetworkService(ctx)

        // project_id is forwarded as a filter, so admin roles also only see the current project's ports here
        const queryParams = appendQueryParamsFromObject(openstackFilters, { keyMap: LIST_PORTS_QUERY_KEY_MAP })
        const response = await requestOrThrow(
          () => network.get(withQuery(PORTS_BASE_URL, queryParams)),
          PortErrorHandlers.list
        )
```

`project_id` comes from `projectScopedInputSchema`, so it stays in `openstackFilters` and reaches Neutron as a filter. Names are applied before `filterPortsBySearchTerm`, which lets the search match network and subnet names too (`portsRouter.ts:73-81`). The request is a single `GET`, with no pagination handling (CR1).

**Shared best-effort lookups** (`packages/aurora/src/server/Network/helpers/lookupHelpers.ts:30`)

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

Each lookup sends `?id=a&id=b&fields=id&fields=name` per chunk of 50 IDs. Any failure collapses the whole lookup to `[]` (I6). Routers used single, unchunked requests before; it now uses these helpers too.

**Error mapping with quota detection** (`packages/aurora/src/server/Network/helpers/portHelpers.ts:25`)

```ts
const conflict = (message: string) => (response: ErrorResponse) =>
  new TRPCError({
    code: HTTP_STATUS_ERROR_MAP[409],
    message: /quota/i.test(response.statusText ?? "") ? QUOTA_EXCEEDED_MESSAGE : message,
  })
```

`requestOrThrow` (`requestHelpers.ts:19`) catches the `SignalOpenstackApiError` that signal-openstack throws on non-2xx responses. It passes Neutron's message as `statusText`, so a 409 caused by `OverQuota` gets the quota text and any other 409 gets the operation-specific message.

**Writes** (`packages/aurora/src/server/Network/routers/portsRouter.ts:112`)

```ts
      // project_id is intentionally not sent: Neutron derives ownership from the (rescoped) token
      const requestBody = { port: buildPortBody(omit(input, "project_id")) }
```

`buildPortBody` (`portHelpers.ts:81`) is an allowlist over the Zod-validated fields. It drops `undefined` keys, including inside `fixed_ips` and `allowed_address_pairs`. `update` rejects an empty body with `BAD_REQUEST` (`portsRouter.ts:129`). No UI calls the write procedures yet.

**Reusable list, scoped by network** (`packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortsList.tsx:193`)

```tsx
  const portsPromise = useMemo(
    () => createPortsPromise(client, project, networkId, sortBy, sortDirection, searchTerm),
    // retryCount is not used in the factory, it only forces a new promise on "Try Again"
    [client, project, networkId, sortBy, sortDirection, searchTerm, retryCount]
  )
  // Keeps the current list (and the search input) on screen while the next query loads,
  // instead of falling back to the Suspense loading state on every search or sort change
  const deferredPortsPromise = useDeferredValue(portsPromise)
```

The URL is the single source of truth for search, sort and page (`PortsList.tsx:175-178`). The promise is rendered through `use()` under `Suspense` and an `ErrorBoundary` that resets on the deferred promise. When `networkId` is set, `PortListContainer` drops the Network column (`PortListContainer.tsx:48`, `:72`).

**Details route** (`packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:127`)

```tsx
  loader: async ({ context, params }) => {
    try {
      const port = await context.trpcClient?.network.ports.getById.query({
        project_id: params.projectId,
        port_id: params.portId,
      })
      return { portName: port?.name || null }
    } catch {
      return { portName: null }
    }
  },
```

The loader only supplies the tab title. The component runs its own `getById.useQuery` (`$portId.tsx:154`), which renders the loading state, the code-specific error view with optional retry, and `PortDetailsView`. This is the double fetch in CR3.

**Router details tab in the URL** (`packages/aurora/src/client/routes/_auth/projects/$projectId/network/routers/$routerId.tsx:136`)

```tsx
  validateSearch: (search: Record<string, unknown>): RouterDetailsSearchParams => ({
    tab: isRouterDetailsTab(search.tab) ? search.tab : undefined,
  }),
```

`RouterDetailsView` no longer holds the tab in `useState`. It receives `activeTab` and `onTabChange` from the route, which navigates with `replace: true`.

</details>

<details>
<summary><strong>What it affects (blast radius)</strong></summary>

- **New public tRPC surface:** the `network.ports.*` procedures, mounted in `server/Network/routers/index.ts:17`. They are additive, so no existing callers change.
- **Moved internal exports:**
  - `requestOrThrow`, `pickDefined` and `chunk` left `routerHelpers.ts`.
  - `NetworkSummary`, `SubnetSummary` and their list schemas left `types/router.ts`.
  - None of these are exported from the package's public `server/index.ts`.
  - At head, every in-repo consumer imports them from the new homes (`routersRouter.ts:44-45`, `routerHelpers.ts:4,14`), and typecheck is green.
  - Outside this PR, open PR #1383 still imports `requestOrThrow` from `routerHelpers` (CR4).
- **Routers behaviour:** the network and subnet name lookups in `routers.list`, `routers.getById` and the router interfaces are now chunked at 50 IDs, and fail as a whole on any failed chunk. The comment at `routersRouter.ts:151` and `0010_routers_bff.md` (lines 80 and 411) still say "one request".
- **Routers UI:** `RouterDetailsView` has new required props, `activeTab` and `onTabChange`. Its only consumer, `$routerId.tsx`, was updated.
- **Navigation and app config:**
  - A new service key `ports` is checked by `buildNavSections.ts:93` and the project overview (`$projectId/index.tsx:94`), inside the existing network-catalog check.
  - Hosts with an `enabledServices` allowlist must add `ports` to see the page.
  - The README's service key lists don't mention `ports` (I7).
- **Permissions:** the `network:ports:*` keys already existed (`permissionRouter.ts:71-75`). This PR doesn't use `canUser` anywhere, because the UI is read-only.
- **Generated and i18n files:** `routeTree.gen.ts` and the `de`/`en` catalogs gain the ports entries. These are the usual merge-conflict points with #1383 and #1385.

</details>

---

## QA Test Plan

<details>
<summary><strong>Core Path</strong></summary>

1. With `ports` enabled (or no `enabledServices` allowlist), open a project. Check that **Ports** appears under Network in the side nav and as a card on the project overview.
2. Open **Network → Ports**. Check the columns: Name / ID, Description, Network, Fixed IPs / Subnet, Device Owner / ID, Status. Check that network and subnet show names, and that a router interface or VM port shows its device owner with the device ID below it.
3. Search by port name, IP address, MAC, network name and subnet name. Check that results narrow, the URL gets `?search=` without adding history entries, and opening a link with a different `?search=` updates the input.
4. Change sort (Name / Status / Device Owner) and direction. Check that the URL updates without adding history entries.
5. In a project with more than 50 ports, page through. Check that `?page=` updates and that a page link opened in a new tab shows the same page.
6. Open a port via the row click and via **Show Details**. Check every field: ID, MAC, Network, IPs with IPv4/IPv6 and subnet, Description, Name, Device Owner, Device ID, Created/Updated at, Project ID, Status, Security Groups. Check that the copy buttons work.
7. Switch projects while on the Ports list. Check that the previous project's ports aren't shown.
8. Open a router, switch to **Internal Networks**, reload, and press Back. Check that the tab persists via `?tab=internal` and that Back returns to the routers list.

</details>

<details>
<summary><strong>Edge Cases</strong></summary>

- **Neutron pagination enabled**, with a max limit lower than the project's port count. The list stops at the first page, and searching for a port beyond it returns nothing (`portsRouter.ts:65`, CR1).
- **More than 50 distinct networks or subnets** on the listed ports, with one lookup chunk failing (e.g. a 403 on shared networks). Every row shows IDs instead of names (`lookupHelpers.ts:34`).
- **Shared or external networks the user can't read.** Network and subnet columns fall back to IDs (`PortTableRow.tsx:52`, `:62`).
- **Unnamed port.** The ID is the primary line with no secondary line (`PortTableRow.tsx:47`). The details page header and breadcrumb use the ID.
- **Port with no fixed IPs or no device.** "–" in the list (`PortTableRow.tsx:56-75`), "—" in details.
- **Unexpected status value** such as `N/A` from some backends. It must render instead of failing validation (`types/port.ts:51`).
- **User without `get_port` permission.** The list renders "Failed to Load Ports" with Neutron's message and no retry (`PortsList.tsx:54`, `:115`, CR2).
- **Deleted or unknown port ID in the URL.** "Port Not Found" (404) with Back to Ports / Home and no retry (`$portId.tsx:66-67`, `:81`).
- **BFF or Neutron 5xx on details.** "Error Loading Port" with **Try Again** (`$portId.tsx:32-40`, `:94`).
- **Expired session on details.** The text says "Log in again", but no sign-in action is offered (`$portId.tsx:70`, CR2/I2).
- **Stale `?page=9` link** to a two-page list. The view resets to page 1, then Back loops (`PortsList.tsx:111`, I1).
- **Invalid search params** (`?sortBy=foo&page=-1`). They fall back to defaults per field (`ports/index.tsx:28-40`).
- **Hit DevTools → Network on a details page.** Two `getById` requests per open (`$portId.tsx:127`, `:154`, CR3).
- **`?tab=garbage` on a router details page.** Falls back to the External Networks tab (`$routerId.tsx:136`).

</details>

---

_Analyzed 2026-10-16 · commit `512f01b1` · read-only · CI from PR API · skill: review-and-comment-pr_
