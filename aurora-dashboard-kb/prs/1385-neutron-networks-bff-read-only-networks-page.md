---
type: pr-report
date: 2026-10-17
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

### ⚖️ &nbsp; Verdict

Recommendation: **🔴 Request Changes** &nbsp;&nbsp;&nbsp;&nbsp; Confidence to Merge: **Medium**

The PR is solid and well tested. The BFF is fully project-scoped, IDs are validated before they reach URLs, and the security review found nothing. CI is green. Two code issues need fixing before it merges. First, the description says the PR doesn't conflict with the Ports PR (#1377), but it does, in 7 generated and registry files. Second, the details page fetches the network twice on every visit. The other findings are small UI-convention and docs fixes. The process to-dos are leaving draft, correcting the description and linking the issues. Confidence is Medium because the PR links no issue: acceptance was graded against epic #1019, which the reviewer supplied. Against that epic, the Phase 1 read scope and the BFF write procedures are delivered. The write UI, permission-gated actions and E2E tests are listed as follow-ups.

### 🔧 &nbsp; Required Changes

| #   | Severity    | Category     | Issue                                                                                                  | Location                                                                         |
| --- | ----------- | ------------ | ------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------- |
| CR1 | 🟡 Moderate | Code Quality | The description says it doesn't conflict with the Ports PR (#1377); it conflicts in 7 files            | `packages/aurora/src/server/Network/routers/index.ts`, `routeTree.gen.ts`, `locales/**` |
| CR2 | 🟡 Moderate | Performance  | The details page sends two `getById` requests per visit (loader + component query)                     | `network/networks/$networkId.tsx:138`                                            |
| P1  | —           | Process      | The PR is still a draft                                                                                | PR state                                                                         |
| P2  | —           | Process      | The description lists a `$routerId` route fix that isn't in this diff                                  | PR body                                                                          |
| P3  | —           | Process      | No linked issue: all three links are template placeholders                                             | PR body                                                                          |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**CR1 — Merge conflict with the Ports PR that the description denies** · Code Quality · `packages/aurora/src/server/Network/routers/index.ts`
The description says the shared helpers are "the same commit as on the Ports branch, so the two branches don't conflict". The helper part is true: `requestHelpers.ts` and `lookupHelpers.ts` are identical on both heads, with the same patch-id. Running `git merge-tree --write-tree --name-only 9ed42505 512f01b1` against #1377's head still reports conflicts in 7 files: `routeTree.gen.ts`, `buildNavSections.test.ts`, the de/en `messages.po` and `messages.ts` catalogs, and `server/Network/routers/index.ts`. All seven are generated or registry files, so resolving them is easy, but whichever PR merges second has to rebase and regenerate them. Context: #1383 is a second, competing Networks implementation by another author, opened a day earlier. The team needs to decide which one goes ahead.
_Fix:_ Correct the claim in the description. Agree a merge order with #1377, then rebase, regenerate `routeTree.gen.ts`, re-run `pnpm check-i18n` and re-merge `routers/index.ts` after the first one lands.

**CR2 — The network is fetched twice on the details page** · Performance · `network/networks/$networkId.tsx:138`
The route `loader` (`:138-148`) calls `getById.query` only to get the page title and swallows every error. The component (`:175`) then calls `trpcReact.network.networks.getById.useQuery` again. That is two Neutron GETs on every navigation, and the loader's result never reaches the query cache. `copilot-instructions.md` Part A says that "Data critical for rendering a page must be fetched via the route's loader … rather than loading it inside the component body". Precedent: `routers/$routerId.tsx` and `floatingips/$floatingIpId/index.tsx` use the same loader-for-title plus `useQuery` pattern, so expect pushback.
_Fix:_ Fetch it once. Either prefetch the same tRPC query into the React Query cache in the loader, so `useQuery` reads it from there, or drop the loader call and set the title from the component's data.

**P1 — Still a draft** · Process · PR state
`isDraft: true` at head `9ed42505`.
_Fix:_ Mark it ready for review once CR1/CR2 are addressed.

**P2 — The description names a fix that isn't in the diff** · Process · PR body
The "**Fix**" bullet says the PR changes the Router details route to a literal `createFileRoute` id, "same fix as on the Ports branch". `routers/$routerId.tsx` isn't among the 41 changed files and still reads `createFileRoute(ROUTE_ID)` at head, the same as on `main`. The fix exists only on the Ports branch (#1377). The screenshot placeholders are also still empty.
_Fix:_ Remove the bullet, or include the fix in this PR. Add the list and details screenshots.

**P3 — No linked issue** · Process · PR body
`Part of #<epic-number>`, `Closes #<bff-issue-number>` and `Closes #<ui-issue-number>` are template placeholders, so GitHub links nothing and closes nothing. For this review, acceptance was graded against epic #1019 (Networks Management), which the reviewer supplied. This PR delivers its Phase 1 read scope (list with filters and pagination, details, copy IDs), the Phase 2 BFF procedures and the Phase 3 Subnets tab. The remaining epic criteria (write UI, delete pre-checks, Ports tab, tag editor, bulk delete, permission-gated actions, E2E tests) are explicitly deferred in the description.
_Fix:_ Replace the placeholders with `Part of #1019` and the real BFF/UI issue numbers.

</details>

### 💡 &nbsp; Improvements

| #   | Severity   | Category      | Issue                                                                                    | Location                                                    |
| --- | ---------- | ------------- | ---------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| I1  | 🟢 Low     | Bug           | Descending sort puts networks with no value (e.g. no MTU) first, against its JSDoc       | `packages/aurora/src/server/Network/helpers/networkHelpers.ts:142` |
| I2  | 🟢 Low     | Accessibility | `PopupMenu` without `PopupMenuToggle`; the default toggle has no accessible name        | `network/networks/-components/NetworkTableRow.tsx:68`       |
| I3  | 🟢 Low     | UI/UX         | Admin State shown as all-caps `UP` / `DOWN`                                              | `NetworkTableRow.tsx:50`, `NetworkDetailsView.tsx:78`       |
| I4  | 🟢 Low     | Code Quality  | Raw `<div>` wrappers where Juno layout components exist                                  | `NetworkDetailsView.tsx:45`, `NetworksList.tsx:312`         |
| I5  | 🟢 Low     | UI/UX         | `Stack gap="1"` is not in the approved spacing values                                    | `NetworkTableRow.tsx:53`                                    |
| I6  | 🟢 Low     | UI/UX         | Network status rendered as plain text, not a `Badge`                                     | `NetworkTableRow.tsx:49`, `NetworkDetailsView.tsx:77`       |
| I7  | 🟢 Low     | UI/UX         | A hand-typed `?shared=true` or numeric `?search=` is silently dropped                    | `network/networks/index.tsx:16`                             |
| I8  | 🟢 Low     | Docs          | README service-key lists don't mention the new `networks` key                            | `packages/aurora/README.md:183`, `:210`                     |
| I9  | ⚪ Trivial | UI/UX         | `...` (three dots) instead of the `…` glyph in loading and placeholder strings           | `$networkId.tsx:183`, `NetworksList.tsx:170`, `:331`, `NetworkSubnetsTable.tsx:28` |
| I10 | ⚪ Trivial | Code Quality  | Import order: `zod` after the i18n imports                                               | `network/networks/index.tsx:4`                              |
| I11 | ⚪ Trivial | Docs          | The Routers doc and a Routers comment describe the helpers' old location and behaviour   | `packages/aurora/docs/0010_routers_bff.md:571`, `routersRouter.ts:151` |
| I12 | ⚪ Trivial | Docs          | The new design doc says every Neutron request goes through `requestOrThrow`; lookups don't | `packages/aurora/docs/0017_networks_bff.md:401`             |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**I1 — Descending sort puts missing values first** · Bug · `packages/aurora/src/server/Network/helpers/networkHelpers.ts:142`
`compareValues` returns `1` for a null or undefined `a` (`:123`). `sortNetworks` multiplies the whole result by `direction` (`:141-142`), so with `sort_dir: "desc"` the missing values move to the top. This contradicts the JSDoc at `:133` and `docs/0017_networks_bff.md:82`, which both say "Missing values sort last". The UI offers MTU sorting, and `mtu` is nullish (`types/network.ts:38`). `compareValues(undefined, null)` and `compareValues(null, undefined)` also both return `1`, which makes the comparator inconsistent. The `sortNetworks` tests have no descending-with-null case. @guoda-puidokaite raised this in both review comments on 2026-10-16, with no reply or fix yet.
_Fix:_ Handle missing values before applying the direction, and add a desc-with-null test:

```ts
const aMissing = a[sortKey] == null, bMissing = b[sortKey] == null
if (aMissing || bMissing) return aMissing === bMissing ? 0 : aMissing ? 1 : -1
return direction * compareValues(a[sortKey], b[sortKey])
```

**I2 — Row actions menu without an explicit toggle** · Accessibility · `network/networks/-components/NetworkTableRow.tsx:68`
This is on the Quick Reject Checklist: "`PopupMenu` without `PopupMenuToggle` as trigger". B.14 says context menus must use `<PopupMenuToggle as="div"><Button icon="moreVert" /></PopupMenuToggle>`. Juno 9.4.0, the pinned version, renders a default focusable `moreVert` button when no toggle is passed, so keyboard users can open the menu. The earlier review comments call this a keyboard blocker, and that part isn't accurate. The default button does have no accessible name. Precedent: Copilot raised the same on #1355 (`RouterTableRow.tsx`) and it wasn't applied, and several existing rows omit the toggle.
_Fix:_ `` <PopupMenuToggle as="div"><Button icon="moreVert" aria-label={t`Network Actions`} /></PopupMenuToggle> ``.

**I3 — All-caps Admin State** · UI/UX · `NetworkTableRow.tsx:50`, `NetworkDetailsView.tsx:78`
Both render `` t`UP` `` / `` t`DOWN` ``. The Quick Reject Checklist bans all-caps strings, and B.19 says "Never all-caps (ever)". Other booleans in the same PR use Enabled/Disabled. Precedent: the merged `RouterTableRow` uses the same casing. Raised in both earlier review comments, with no fix yet.
_Fix:_ Use `` t`Up` `` / `` t`Down` ``, or Enabled/Disabled to match the rest of the details view.

**I4 — Raw `<div>` wrappers** · Code Quality · `NetworkDetailsView.tsx:45`, `NetworksList.tsx:312`
`<div className="break-all">{value}</div>` and `<div className="relative">` hit the Quick Reject item "Raw HTML element (`<div>`, `<table>`, `<button>`) where a Juno component exists". B.1 names `Stack` as the primary layout primitive.
_Fix:_ Use `Stack` with the same class, or drop the wrappers if they aren't needed.

**I5 — Unapproved Stack gap** · UI/UX · `NetworkTableRow.tsx:53`
`<Stack direction="vertical" gap="1">` isn't in B.3's approved gaps (0.5, 2, 4, 6). The Quick Reject Checklist covers "Ad-hoc spacing value not in the approved list (B.3)". Precedent: `RouterTableRow.tsx` uses `gap="1"` too.
_Fix:_ Use `gap="0.5"` or `gap="2"`.

**I6 — Status as plain text** · UI/UX · `NetworkTableRow.tsx:49`, `NetworkDetailsView.tsx:77`
The B.1 component table maps "Status indicators" to `Badge`, but `network.status` is rendered as plain text. Precedent: Routers and Floating IPs do the same.
_Fix:_ Render the status in a `Badge` with a variant per status (ACTIVE/DOWN/BUILD/ERROR).

**I7 — Hand-typed filter URLs are dropped** · UI/UX · `network/networks/index.tsx:16`
The router uses TanStack's default JSON search parsing (`router.ts`, no `parseSearch`). A hand-written `?shared=true` therefore arrives as a boolean and fails `z.enum(["true","false"])`, and `?search=123` arrives as a number and fails `z.string()`. `validOrUndefined` silently resets both. URLs the app generates are JSON-quoted strings and work.
_Fix:_ Accept both forms, e.g. `z.union([z.enum([...]), z.boolean().transform(String)])` for `shared` and `z.coerce.string()` for `search`.

**I8 — README doesn't list the new service key** · Docs · `packages/aurora/README.md:183`, `:210`
The PR adds the `networks` service key (nav entry and overview card). The changeset says both "require `networks` in `enabledServices`". The README's two service-key lists, the consumer-facing contract, don't mention it. The "require" wording is also loose: with no `enabledServices`, every service is visible. (`routers` is missing from the lists too, but that predates this PR.)
_Fix:_ Add `"networks"` to both README lists, and say "when `enabledServices` is set" in the changeset.

**I9 — Three dots instead of an ellipsis** · UI/UX · `$networkId.tsx:183`, `NetworksList.tsx:170`, `:331`, `NetworkSubnetsTable.tsx:28`
B.19: "**Never** … double/triple punctuation. An ellipsis (`…`) counts as a single glyph and is allowed." Precedent: existing pages and B.6's own sample use `Loading...`.
_Fix:_ Replace `...` with `…` and update the tests that assert the text.

**I10 — Import order** · Code Quality · `network/networks/index.tsx:4`
B.13 puts `zod` in group 1 (framework), before i18n, but here it comes after the two Lingui imports.
_Fix:_ Move `import { z } from "zod"` above the Lingui imports.

**I11 — Stale Routers docs after the helper move** · Docs · `packages/aurora/docs/0010_routers_bff.md:571`, `routersRouter.ts:151`
The PR moves `requestOrThrow`, `pickDefined` and `chunk` to `requestHelpers.ts`, and the name lookups to `lookupHelpers.ts`, which now chunk at 50 IDs. `0010_routers_bff.md` still lists these helpers under `routerHelpers.ts` (`:571`, `:584`, `:590`), still names `routerHelpers.test.ts` as covering `requestOrThrow` (`:628`), and still says names come from "one request". The comment at `routersRouter.ts:151` also still says "one networks request … and one subnets request".
_Fix:_ Point the doc at `requestHelpers.ts`/`lookupHelpers.ts`, and say "batched (chunks of 50)" in the doc and the comment.

**I12 — Design doc overstates `requestOrThrow`** · Docs · `packages/aurora/docs/0017_networks_bff.md:401`
"Every Neutron request goes through `requestOrThrow`" isn't true for the best-effort subnet-name lookups. `lookupHelpers.ts:41-45` calls `network.get` directly and returns `[]` on failure.
_Fix:_ Say "every main request", and mention that the name lookups are best-effort.

</details>

---

## Solution Overview

<details>
<summary><strong>What was done</strong></summary>

**BFF.** A new `network.networks` tRPC router with seven project-scoped procedures: `list`, `getById`, `create`, `update`, `delete`, `setTags` and `listSubnets`. Its Zod request and response schemas are in `types/network.ts`, and network-specific error mapping is in `networkHelpers.ts`: ports still in use on delete, unsharing a network other projects use, admin-only attributes, and quota exceeded (reported as 409). `list` handles one Neutron quirk: filtering by `project_id` hides networks that other projects share with this one. So it sends one request for the project's own networks and one with `shared=true`, merges them by ID and re-sorts the result. It then resolves subnet names with one batched, best-effort lookup. The write procedures exist only in the BFF. No UI calls them yet.

**Shared helpers refactor.** `requestOrThrow`, `pickDefined`, `chunk` and `withQuery` move from the Routers code into a new `requestHelpers.ts`. The name lookups (`fetchNetworkSummaries`, `fetchSubnetSummaries`, plus a new `fetchSecurityGroupSummaries`, which Ports will use and nothing in this PR uses) move into `lookupHelpers.ts`, and their summary schemas move to `types/index.ts`. `routersRouter.ts` now imports from the new files. One behaviour change: the lookups now de-duplicate IDs and split them into chunks of 50 instead of sending a single request. This is the same commit as on the Ports branch (#1377).

**UI.** A "Networks" entry under Network in the side navigation and a "Networks" card on the project overview, both shown when the `networks` service key is enabled. The list view shows Name / ID, Status, Admin State, Subnets, Shared, External and MTU. It has search, Status and Shared filters, sorting by name/status/MTU and client-side pagination (50 per page), all kept in URL search params. The details view shows an overview with copyable IDs and a Subnets tab whose `?tab=` lives in the URL. The list keeps showing the previous results while a new query loads, and errors render inside the project layout with retry.

**Other.** The design doc `docs/0017_networks_bff.md`, the regenerated route tree, the de/en catalogs, a `minor` changeset for `@cobaltcore-dev/aurora`, and tests across 13 files (+2526 lines). CI passes on `9ed42505`.

</details>

<details>
<summary><strong>How it is implemented</strong></summary>

**Own + shared list.** The `shared` input decides which requests go out (`networkHelpers.ts:106`):

```ts
export const getNetworkListScopes = (shared: boolean | undefined): Array<"own" | "shared"> => {
  if (shared === true) return ["shared"]
  if (shared === false) return ["own"]
  return ["own", "shared"]
}
```

Each scope becomes one Neutron request with its own filters. The results are merged by ID (first occurrence wins), re-sorted, filtered by the BFF-side search term and enriched with subnet names (`networksRouter.ts:74`):

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

        const networks = sortNetworks(mergeNetworks(...(await Promise.all(requests))), input.sort_key, input.sort_dir)
```

Neutron sorts each list, but not their concatenation, so `sortNetworks` re-sorts the merged list (`networkHelpers.ts:135-143`; see I1 for its null handling). Non-shared external networks owned by other projects, such as floating IP pools, deliberately aren't part of this list. The design doc points to `network.floatingIp.listExternalNetworks` for those.

**Safe resource URLs.** Every path-ID procedure builds its URL through `networkUrl`, which validates and encodes the ID with the shared signal-openstack helper (`networksRouter.ts:44`):

```ts
const networkUrl = (networkId: string, subresource?: "tags"): string => {
  const encodedId = validateAndEncodeResourceId(networkId, "Network")
  return subresource ? `${NETWORKS_BASE_URL}/${encodedId}/${subresource}` : `${NETWORKS_BASE_URL}/${encodedId}`
}
```

`listSubnets` validates the ID too, then sends it as a `network_id` query parameter (`networksRouter.ts:198-204`).

**Error mapping.** signal-openstack rejects every non-2xx response with `SignalOpenstackApiError`, so `requestOrThrow` catches it and passes Neutron's message to the operation's handler as `statusText` (`requestHelpers.ts:25`):

```ts
  try {
    response = await request()
  } catch (error) {
    if (error instanceof SignalOpenstackApiError) {
      throw handleError({ status: error.statusCode, statusText: error.message }, resourceLabel)
    }
    throw error
  }
```

Neutron reports OverQuota as 409, so every 409 override in `NetworkErrorHandlers` checks the message for "quota" first (`networkHelpers.ts:26-30`).

**Best-effort lookups.** `fetchSummaries` de-duplicates the IDs, sends one request per chunk of 50 and returns `[]` on any failure, so callers fall back to IDs (`lookupHelpers.ts:30`):

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

**List page state.** Search, sort, filters and page come from the URL. The query promise is memoized on those values plus a retry counter, and deferred so the previous list stays visible while the next one loads (`NetworksList.tsx:254`):

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

A FORBIDDEN list response becomes an inline error `Status` (`NetworksList.tsx:65-67`, `:141`). Other errors reach an `ErrorBoundary` with "Try Again", keyed on the deferred promise. Pagination happens client-side over the full BFF result (`PAGE_SIZE = 50`).

**Details page.** The loader only resolves the page title. The component's own query renders the page and the error state (code-specific messages, retry for transient codes). This is where the duplicate request in CR2 comes from (`$networkId.tsx:138`):

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

**Navigation.** The nav entry is gated like its siblings: the network service must be in the catalog, and `isEnabled("networks")` must hold (`buildNavSections.ts:60`):

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

</details>

<details>
<summary><strong>What it affects (blast radius)</strong></summary>

**Public contract.** The new tRPC surface is `network.networks.*` on the app router, which typed consumers of `AuroraRouter` will see. It is additive. The client uses only `list`, `getById` and `listSubnets`. No production code (UI or other routers) calls `create`, `update`, `delete` or `setTags` yet. Only `networksRouter.test.ts` does. The permission keys `network:networks:{read,list,create,update,delete}` already existed in `permissionRouter.ts:19-23` and are unchanged. The new page doesn't use them.

**New service key `networks`.** It is used by `buildNavSections.ts`, the project overview cards and the routes' `staticData.service`. When `enabledServices` is unset, every service shows, so existing hosts get the new nav entry and card automatically. Hosts that allowlist services must add `networks`. The README's service-key lists don't mention it (I8).

**Routers refactor (internal).** `routersRouter.ts` and `routerHelpers.ts` now import the moved helpers from `requestHelpers.ts` / `lookupHelpers.ts`. A search at the head commit finds no other importer of the old exports. `pickDefined`, `chunk` and `withQuery` moved unchanged. `requestOrThrow` only renames its handler type to `NetworkErrorHandler`. The name lookups were reworked: they now de-duplicate IDs, go out in chunks of 50 (several requests for very large lists), take an optional `context` argument (with new default log labels), and route the failure check through a `getJson` helper. On failure they still return `[]`. The Routers doc `0010_routers_bff.md` and one comment in `routersRouter.ts` weren't updated (I11).

**Generated files.** `routeTree.gen.ts` and the de/en catalogs are regenerated. Those files, `routers/index.ts` and `buildNavSections.test.ts` are exactly where the PR conflicts with Ports #1377 (CR1). They also overlap with #1383 (a competing Networks PR) and #1386 (marked "DO NOT MERGE").

</details>

---

## QA Test Plan

<details>
<summary><strong>Core Path</strong></summary>

1. Open a project whose catalog includes Neutron. Check the "Networks" entry under Network in the side nav and the "Networks" card on the overview. Both should open `/projects/<id>/network/networks`.
2. On the list, check that the columns read Name / ID, Status, Admin State, Subnets, Shared, External and MTU, and that the project's own networks and the networks shared with it are both listed, without duplicates.
3. Type a search term (part of a name, ID or description). The URL gets `?search=…` after a short pause, and the list narrows without falling back to a full loading state.
4. Apply the Status filter, then the Shared filter (Yes / No). Each adds a pill and a URL param, and the page resets to 1. Clear the filters and the full list returns.
5. Sort by Name, Status and MTU, both directions. The URL keeps `sortBy` / `sortDirection`.
6. With more than 50 networks, page through the list. Then use the browser back and forward buttons: the controls and the list follow the URL.
7. Click a row, and separately use the row menu's "Show Details". Both open the details page with the network's name in the header, breadcrumb and tab title.
8. On the details page, copy the ID and the Project ID. Check Description, Status, Admin State, MTU, Shared, External, Port Security, Availability Zones, Tags and Created/Updated.
9. Open the Subnets tab and check Name/ID, CIDR, IP version, gateway and DHCP. The URL keeps the default tab without `?tab=`. Switching tabs doesn't add history entries.

</details>

<details>
<summary><strong>Edge Cases</strong></summary>

- Sort by MTU descending while some networks have no MTU (net-mtu extension off): they appear at the top, not at the bottom. This is the I1 scenario, `networkHelpers.ts:123`, `:142`.
- A network shared with the project by another project: listed once, Shared = Yes. Filter Shared = No and it disappears, because only the own request is sent (`networkHelpers.ts:106-110`).
- A non-shared external network of another project (e.g. a floating IP pool exposed through RBAC): not listed, by design (`docs/0017_networks_bff.md`).
- A network with no name: the ID is shown as the primary text and in the header (`NetworkTableRow.tsx:47`, `$networkId.tsx:192`).
- A subnet whose name can't be resolved (lookup fails or isn't visible): the list shows its ID (`NetworkTableRow.tsx:56`, `lookupHelpers.ts:36-38`).
- More than 50 distinct subnets in the list: names come from several lookup requests, and if one of them fails, every subnet falls back to its ID (`lookupHelpers.ts:34`).
- External and MTU missing from the response (extension off): shown as "–" (`NetworkTableRow.tsx:65-66`).
- A project with no networks: "There are no networks in this project." With a search or filter applied and no matches: the "No networks match…" text (`NetworkListContainer.tsx:91-93`).
- A user whose list request returns 403: an inline "Failed to Load Networks" with the server's message, no retry (`NetworksList.tsx:65-67`, `:141`).
- A transient list failure (5xx): an error with "Try Again", which re-runs the same query (`NetworksList.tsx:318-329`).
- Opening a deleted or unknown network ID: "Network Not Found" with Back/Home and no retry. On a 5xx, "Error Loading Network" with "Try Again" (`$networkId.tsx:72-106`).
- Check the browser's network tab while opening a details page: `getById` is requested twice (the CR2 scenario, `$networkId.tsx:140`, `:175`).
- A hand-typed `?shared=true` or `?search=123` in the URL: the filter or search is ignored (the I7 scenario, `network/networks/index.tsx:11`, `:16`). The same URL produced by the UI works.
- An invalid `?tab=foo` on the details page: falls back to the Subnets tab (`$networkId.tsx:134`).
- Switching projects while on the list: the list remounts, and the previous project's networks aren't shown (`network/networks/index.tsx:62`).
- A host with `enabledServices` set but without `networks`: no nav entry and no overview card (`buildNavSections.ts:60`, `$projectId/index.tsx:73`).
- Keyboard: Tab to the row menu's default toggle and open it with Enter/Space. A screen reader announces it with no name (I2, `NetworkTableRow.tsx:68`).

</details>

---

_Analyzed 2026-10-17 · commit `9ed42505` · read-only; acceptance graded against epic #1019 supplied by the reviewer · skill: review-and-comment-pr_

<!-- related:auto — generated from pr/issue properties by tools/update-related.py; do not edit by hand -->
## Related

- plan · 2026-10-12 · [2026-10-12-networks-epic-1019-analysis](../../plans/2026-10-12-networks-epic-1019-analysis.md)
- plan · 2026-10-12 · [2026-10-12-networks-phase-1-read-operations](../../plans/2026-10-12-networks-phase-1-read-operations.md)
- pr-report · 2026-10-17 · [1386-network-and-verify-do-not-merge](1386-network-and-verify-do-not-merge.md)
- pr-report · 2026-10-21 · [1383-neutron-networks-bff-read-only-networks-page](1383-neutron-networks-bff-read-only-networks-page.md)
