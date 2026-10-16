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
**Related epics (pattern reference):** [#1381 — Ports BFF](https://github.com/cobaltcore-dev/aurora-dashboard/issues/1381) · [#1382 — Ports list and details view](https://github.com/cobaltcore-dev/aurora-dashboard/issues/1382)

---

## Enhanced PR Description

> The original PR description reproduced below with code-verified additions in `<mark>` tags.
> Plain text = author-written; highlighted text = added by code review.

### BFF — `packages/aurora/src/server/Network/`

A new `networksRouter` is mounted at `network.networks`. It exposes seven procedures: `list`, `getById`, `create`, `update`, `delete`, `setTags`, and `listSubnets`. Only `list`, `getById`, and `listSubnets` are wired to the UI in this PR; the write procedures (`create`, `update`, `delete`, `setTags`) are implemented in the BFF and tested but not yet exposed in the client.

The `list` procedure solves a Neutron limitation: Neutron's `project_id` filter hides networks shared with the project by other projects. The BFF fires up to two parallel requests — own networks (`?project_id=X`) and shared networks (`?shared=true`) — merges the results by ID, and re-sorts the combined list. <mark>Both requests are fired concurrently with `Promise.all` (`networksRouter.ts:88`). If the `?shared=true` request fails (e.g. under a Neutron policy that restricts shared-network access), the entire `list` procedure fails even though the own-networks request succeeded — there is no partial fallback in the current implementation.</mark> A `shared` filter in the input sends only one of the two requests.

Subnet names in the list are resolved in one batched, best-effort lookup: after filtering, the BFF collects all unique subnet IDs from the result and resolves them in one chunked request (`GET /v2.0/subnets?id=a&id=b&fields=id,name`). <mark>This lookup fires **after** `filterBySearchParams`, so it resolves names only for networks that survived the current search and filters — not all networks in the project. Applying a search term before opening the page reduces the number of subnet IDs looked up. The description refers to "one batched lookup" but does not mention this post-filter scoping.</mark> A failed lookup degrades gracefully to showing IDs.

Two new shared helper modules are extracted from `routersRouter.ts` / `routerHelpers.ts` so the Networks BFF can use them without duplication:

- `helpers/requestHelpers.ts`: `requestOrThrow`, `pickDefined`, `chunk`, `withQuery`.
- `helpers/lookupHelpers.ts`: `fetchNetworkSummaries`, `fetchSubnetSummaries`, `fetchSecurityGroupSummaries` — batched, best-effort name lookups.

`routersRouter.ts` and `routerHelpers.ts` are updated to import from these new modules; their logic is unchanged.

### UI — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/`

- A "Networks" nav entry is added to the Network section, gated behind `isEnabled("networks")`.
- A "Networks" card is added to the project overview, also gated.
- The list route renders the `Networks` component. It supports search, Status and Shared filters, column sorting (Name, Status, MTU), and URL-driven pagination. The component uses React 19's `use()` + `useDeferredValue` pattern (same as the Routers list) to keep the current list on screen while the next query loads. <mark>The `isStale` flag derived from `useDeferredValue` also guards the page-clamp effect — preventing the old result's page count from resetting the URL during a query in flight (`NetworksList.tsx:254–266`).</mark>
- The details route shows a description list of all network properties with copyable IDs and a Subnets tab (`?tab=subnets` in the URL). The loader fetches only the page title; all data, error handling, and retry are managed by a `useQuery` inside the component (same pattern as `$routerId.tsx`). <mark>The loader never throws — a title-fetch failure leaves the `<title>` empty without unmounting the component, which is required for the useQuery-inside-component retry pattern to work.</mark>

<mark>**Scope note:** external networks not shared with the project (such as floating IP pools) are **not** included in this list. They are served by a separate procedure, `network.floatingIp.listExternalNetworks`, implemented in an earlier PR. The Networks list covers only project-owned and project-shared networks.</mark>

### i18n, docs, changeset

German and English `.po` files are updated, the `@cobaltcore-dev/aurora: minor` changeset is included, and BFF documentation is added at `packages/aurora/docs/0017_networks_bff.md`.

**Closes:** <mark>[The PR body uses placeholder text — `#<epic-number>`, `#<bff-issue-number>`, `#<ui-issue-number>` — no real issue numbers are linked.]</mark>

---

## PR Description Accuracy

- ✅ **Confirmed**: `networksRouter.ts` exposes `list`, `getById`, `create`, `update`, `delete`, `setTags`, `listSubnets` mounted at `network.networks` — all seven procedures are present and tested.
- ✅ **Confirmed**: `requestHelpers.ts` and `lookupHelpers.ts` extracted from `routersRouter.ts`/`routerHelpers.ts`; `routersRouter.ts` updated to import from them.
- ✅ **Confirmed**: List shows Name/ID, Status, Admin State, Subnets, Shared, External, MTU (verified in `NetworkTableRow.tsx`); search, status/shared filters, sort, and pagination are all URL-driven.
- ✅ **Confirmed**: Details view has copyable IDs and a Subnets tab with `?tab=` in the URL.
- ✅ **Confirmed**: `createFileRoute` uses a literal string ID in both routes.
- ✅ **Confirmed**: `shared` filter sends only one of the two requests (`getNetworkListScopes` returns `["own"]` or `["shared"]` when filter is set).
- ➕ **Understated**: The subnet name batch lookup fires _after_ `filterBySearchParams`, so it only resolves names for the filtered result set — not all networks in the project. On a project with many networks, applying a search before opening the page means fewer subnet lookup requests. The description calls it "one batched lookup" without explaining this scope.
- ➕ **Understated**: The description doesn't mention that `Promise.all` is used for the dual own/shared requests. This means a failure on either request silently fails the entire list — a design choice with real consequences that is not surfaced anywhere in the description.
- ➕ **Understated**: External networks not shared with the project (e.g. floating IP pools) are excluded from this list. They are served by `network.floatingIp.listExternalNetworks`. Not obvious from the description.

## Does it deliver?

No direct ticket is linked. The PR body uses placeholder text (`#<epic-number>`, `#<bff-issue-number>`, `#<ui-issue-number>`). The user provided two related epics — **[#1381 Ports BFF](https://github.com/cobaltcore-dev/aurora-dashboard/issues/1381)** and **[#1382 Ports list and details](https://github.com/cobaltcore-dev/aurora-dashboard/issues/1382)** — as pattern reference. These are the parallel Ports feature; they establish what a complete BFF + UI feature looks like in this domain. The table below checks whether the Networks PR meets the same completeness bar.

**Pattern reference: BFF completeness (from #1381)**

| Requirement                                                | Status       | Notes                                                                                                                                                  |
| ---------------------------------------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Zod schemas for all procedures' input/output               | ✅ Delivered | `network.ts` has `NetworkSchema`, `NetworkListItem`, `NetworkQueryParameters`, `NetworkListResponse`, and all operation schemas                        |
| CRUD procedures (list, get, create, update, delete)        | ✅ Delivered | All seven procedures present; write procedures BFF-only in this PR                                                                                     |
| Supplementary UI data (name lookups for related resources) | ✅ Delivered | `fetchSubnetSummaries` resolves subnet names for the list                                                                                              |
| User-friendly Neutron error mapping                        | ✅ Delivered | `NetworkErrorHandlers` with quota/409 special handling; `requestOrThrow` maps `SignalOpenstackApiError` → `TRPCError`                                  |
| Router registration in the domain index                    | ✅ Delivered | `networksRouter` mounted at `network.networks` via `packages/aurora/src/server/Network/routers/index.ts`                                               |
| Unit test coverage (success + error scenarios)             | ⚠️ Partial   | `networksRouter.test.ts` covers success and uniform-failure cases; partial failure (own succeeds, shared fails) is untested — this is the PR's blocker |
| BFF documentation                                          | ✅ Delivered | `packages/aurora/docs/0017_networks_bff.md` added                                                                                                      |
| Lists restricted to current project                        | ✅ Delivered | `project_id` scoping via `projectScopedProcedure`; shared filter reduces to a single own-networks request when set to `false`                          |
| Missing lookups degrade gracefully (IDs returned)          | ✅ Delivered | `fetchSummaries` catches all chunk failures and returns `[]`; `applySubnetNames` falls back to IDs                                                     |

**Pattern reference: UI completeness (from #1382)**

| Requirement                                            | Status            | Notes                                                                                                             |
| ------------------------------------------------------ | ----------------- | ----------------------------------------------------------------------------------------------------------------- |
| Navigation access and project overview card            | ✅ Delivered      | Both in `buildNavSections.ts` and project overview, gated behind `enabledServices: ["networks"]`                  |
| Search, sorting, pagination with URL persistence       | ✅ Delivered      | All state in the URL; `useDeferredValue` keeps the list visible during transitions                                |
| Correct columns in the list                            | ✅ Delivered      | Name/ID, Status, Admin State, Subnets, Shared, External, MTU — all seven verified in `NetworkTableRow.tsx`        |
| Details with all expected fields and copy-to-clipboard | ✅ Delivered      | `NetworkDetailsView.tsx` covers all network properties; copyable IDs present                                      |
| Graceful handling of incomplete data                   | ✅ Delivered      | Empty name → ID fallback in table row; subnet lookup failure → IDs shown                                          |
| Design system compliance (juno-ui-components)          | ✅ Delivered      | Components use `DataGrid`, `ContentHeader`, `TwoColumnDescriptionList`, and other juno components throughout      |
| Reusable list component for network-scoped display     | ⚠️ Not applicable | #1382 requires this for a Ports-in-a-Network sub-list. Networks has no equivalent scoped view in this PR's scope. |

**Scope delta vs. sibling Ports feature**: the Networks PR covers the same completeness level as #1381/#1382 define for Ports. The one item marked Partial (unit test for partial failure) is the existing blocker.

## What was done

**BFF — `packages/aurora/src/server/Network/`**

A new `networksRouter` provides seven tRPC procedures. `list`, `getById`, and `listSubnets` are connected to the UI; `create`, `update`, `delete`, and `setTags` are implemented and tested in the BFF but intentionally left unconnected to the client in this PR.

The `list` procedure addresses a structural Neutron limitation: filtering by `project_id` hides networks shared with the project by other projects. The BFF fires up to two parallel requests — own networks (`?project_id=X`) and shared networks (`?shared=true`) — then deduplicates by ID (first occurrence wins) and re-sorts. A `shared` filter in the input reduces this to a single request.

After filtering the merged list, subnet names are resolved in one batched request scoped to the _filtered_ result — only subnet IDs referenced by the networks that survived search and filter are looked up. This is more efficient than resolving all subnets upfront, but it means navigating back to an unfiltered view after a filtered one may trigger a larger lookup. A failed lookup degrades to showing IDs.

Two new shared modules are extracted from existing BFF code: `requestHelpers.ts` (request execution, error mapping, utility functions) and `lookupHelpers.ts` (batched name lookups for networks, subnets, and security groups). Both `routersRouter.ts` and the new `networksRouter.ts` now import from these modules.

**UI — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/`**

The list uses React 19's `use()` + `useDeferredValue` pattern (established by the Routers list): the tRPC query is issued as a Promise and deferred so the previous result stays on screen while the next query loads. All state — search, filters, sort, page — lives in the URL.

The details route loads only the network name in the `loader` (for the `<title>` tag) and never throws; the component manages the full data query, error handling, and retry independently. This matches the established pattern in `$routerId.tsx`.

Both nav entry and project overview card require `networks` in `enabledServices`.

## How it is implemented

### Dual-scope list merge

`getNetworkListScopes` controls which requests are sent:

```typescript
// packages/aurora/src/server/Network/helpers/networkHelpers.ts:106–110
export const getNetworkListScopes = (
  shared: boolean | undefined
): Array<"own" | "shared"> => {
  if (shared === true) return ["shared"];
  if (shared === false) return ["own"];
  return ["own", "shared"];
};
```

Both requests run via `Promise.all` and are merged before sorting:

```typescript
// packages/aurora/src/server/Network/routers/networksRouter.ts:74–88
const requests = getNetworkListScopes(shared).map(async (scope) => {
  const scopeFilters =
    scope === "own"
      ? {
          ...openstackFilters,
          project_id,
          ...(shared === false && { shared: false }),
        }
      : { ...openstackFilters, shared: true };
  const queryParams = appendQueryParamsFromObject(scopeFilters, {
    keyMap: LIST_NETWORKS_QUERY_KEY_MAP,
  });
  const response = await requestOrThrow(
    () => network.get(withQuery(NETWORKS_BASE_URL, queryParams)),
    NetworkErrorHandlers.list
  );
  const data = await response.json();
  return parseOrThrow(NetworkListResponseSchema, data, "networksRouter.list")
    .networks;
});

const networks = sortNetworks(
  mergeNetworks(...(await Promise.all(requests))),
  input.sort_key,
  input.sort_dir
);
```

### Subnet name enrichment

The batch fires after filtering, scoped to the visible result:

```typescript
// packages/aurora/src/server/Network/routers/networksRouter.ts:89–99
const filteredNetworks = filterBySearchParams(networks, searchTerm, [
  "id",
  "name",
  "description",
]);

// Subnet names are resolved in one batched, best-effort lookup for the whole list
const subnets = await fetchSubnetSummaries(
  network,
  collectSubnetIds(filteredNetworks),
  ["id", "name"],
  "networksRouter.list.subnets"
);

return applySubnetNames(filteredNetworks, subnets);
```

### Error mapping: quota as 409

Neutron reports quota exceeded as 409, not 413. The conflict handler checks `statusText` before applying the operation-specific message:

```typescript
// packages/aurora/src/server/Network/helpers/networkHelpers.ts:27–33
const conflict = (message: string) => (response: ErrorResponse) =>
  new TRPCError({
    code: HTTP_STATUS_ERROR_MAP[409],
    message: /quota/i.test(response.statusText ?? "")
      ? QUOTA_EXCEEDED_MESSAGE
      : message,
  });
```

### List: stale content while refetching

```typescript
// packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:254–266
const networksPromise = useMemo(
  () =>
    createNetworksPromise(client, project, sortBy, sortDirection, searchTerm, {
      status: statusFilter,
      shared: sharedFilter,
    }),
  [
    client,
    project,
    sortBy,
    sortDirection,
    searchTerm,
    statusFilter,
    sharedFilter,
    retryCount,
  ]
);
const deferredNetworksPromise = useDeferredValue(networksPromise);
const isStale = deferredNetworksPromise !== networksPromise;
```

`isStale` guards the page-clamp effect so the old result's page count is not used to reset the URL while a new query is in flight.

### Name fallback in table row

The row shows the name with the ID below it; when name is empty, the ID takes the primary slot:

```typescript
// packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:46–49
<TwoLineCell
  primary={network.name || network.id}
  secondary={network.name ? network.id : undefined}
/>
```

## What it affects

**`network.networks`** — brand new tRPC key. No existing callers anywhere in the monorepo; no stale consumers.

**`requestHelpers.ts` and `lookupHelpers.ts`** — new shared modules consumed by `routersRouter.ts`, `routerHelpers.ts`, and `networksRouter.ts`. All are changed in this PR; no callers outside the PR's changed files.

**Nav and project card** — gated behind `enabledServices: ["networks"]`. Host apps not opting in are unaffected.

**`routersRouter.ts` and `routerHelpers.ts`** — logic unchanged; only imports updated to the extracted modules.

## Review

### Blockers

**[🟠 Medium] No test for partial dual-scope failure** · `packages/aurora/src/server/Network/routers/networksRouter.test.ts`
The `networksRouter.list` fires two parallel Neutron requests via `Promise.all` when `shared` is undefined. The test suite's 403 test applies the error to all mock responses uniformly — it does not cover the case where only the `?shared=true` request fails while the own-networks request succeeds. With `Promise.all`, this scenario silently kills the entire list and returns FORBIDDEN to a user who can see their own networks. There is no test documenting either the current behaviour (fail-all) or the intended behaviour (show own networks on partial failure). Without this test, a future fix for the `Promise.all` issue has no regression guard.

### Follow-ups

**[🟠 Medium] `Promise.all` on dual-scope requests** · `packages/aurora/src/server/Network/routers/networksRouter.ts:88`
If the `?shared=true` Neutron request fails — possible under a custom policy that restricts shared-network access but not project-owned networks — the whole `list` procedure fails even though the own-networks request succeeded. The user sees a full error page with no indication their own networks are available. Replace with `Promise.allSettled` and merge only the fulfilled results.

**[🟡 Low] `Promise.all` in subnet lookup chunk loop** · `packages/aurora/src/server/Network/helpers/lookupHelpers.ts:34`
A single failed chunk discards all successfully resolved names from other chunks. Only affects projects with >50 distinct subnet IDs. Degradation is graceful (IDs shown instead of names). `Promise.allSettled` with `filter(r => r.status === 'fulfilled')` is already the pattern in `imageHelpers.ts`.

**[🟡 Low] No test for sort change updating the URL** · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.test.tsx`
Search and filter changes both have tests verifying URL updates, refetches, and page resets. The SortInput widget has no equivalent test — only the initial URL-read path is covered. Medium risk if sort wiring is refactored.

### Suggested changes

- The `networksRouter.list` test should add one case: own-networks request succeeds, shared-networks request returns 403. Assert whether the procedure fails or returns own networks only. This documents the intended contract regardless of which behaviour is chosen.
- Consider adding a `// TODO: replace Promise.all with Promise.allSettled` comment at `networksRouter.ts:88` so the known limitation is visible in the code until fixed.

## QA

**Core path:**

1. Open a project → Network → Networks. Confirm both own networks and networks shared from other projects appear in the list.
2. Apply "Shared: Yes" filter — confirm only shared networks appear and the URL updates. Apply "Shared: No" — confirm only own networks appear.
3. Search by name — confirm the list filters and the URL updates. Clear the search — confirm the full list returns.
4. Change sort to Status and direction to Desc — confirm the list reorders and the URL updates.
5. Open a network → confirm all columns in the list (Name/ID, Status, Admin State, Subnets, Shared, External, MTU) match the details view.
6. Subnets tab — confirm subnet names appear where known, IDs as fallback.

**Edge cases the code reveals:**

- **Network with empty name** — the list row should show the ID as the primary value, not a blank cell (`NetworkTableRow.tsx:46`).
- **Network with no subnets** — Subnets column should show "–", Subnets tab should show an empty state.
- **50+ subnets across all networks** — if one lookup chunk fails, all subnet names silently drop to IDs. Verify the list doesn't error.
- **Navigate to a non-existent network ID** — should show "Network Not Found" with a Back button, not a blank page.
- **Browser back from details to list** — URL state (search, filters, sort, page) should be restored.
- **Restricted shared-network access** (if testable): filter to "Shared: No" to verify own networks load. The unfiltered list currently fails entirely if the shared-networks request is rejected.

---

## Summary

**🚫 DON'T MERGE** — one blocker: no test documenting the behaviour when only the shared-networks request fails, which currently means a silent full-list failure for users with restricted shared-network access.

### Blocking issues

| Severity  | Issue                                          | Location                 |
| --------- | ---------------------------------------------- | ------------------------ |
| 🟠 Medium | No test for partial dual-scope request failure | `networksRouter.test.ts` |

### What was checked

| Check                                                          | Result                                                                             |
| -------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| Acceptance criteria (related epics #1381/#1382 as pattern ref) | Met — Networks matches the BFF + UI completeness bar; unit test gap is the blocker |
| PR description accuracy                                        | Accurate — 3 understated behaviours noted; enhanced description written            |
| Bugs                                                           | 2 found (both follow-ups)                                                          |
| CLAUDE.md compliance                                           | Clean                                                                              |
| Code quality & unit tests                                      | 2 gaps found (1 blocker, 1 follow-up)                                              |
| Historical regressions                                         | Clean                                                                              |
| Prior PR feedback                                              | Clean                                                                              |
| Comment compliance                                             | Clean                                                                              |

Analyzed: 2026-10-13 · commit `9ed4250` · epics: [#1381](https://github.com/cobaltcore-dev/aurora-dashboard/issues/1381) · [#1382](https://github.com/cobaltcore-dev/aurora-dashboard/issues/1382)

<!-- related:auto — generated from pr/issue properties by tools/update-related.py; do not edit by hand -->
## Related

- pr-report · 2026-10-13 · [1385-neutron-networks-bff-and-networks-page-v2](1385-neutron-networks-bff-and-networks-page-v2.md)
- pr-report · 2026-10-13 · [1385-neutron-networks-bff-and-networks-page](1385-neutron-networks-bff-and-networks-page.md)
- pr-report · 2026-10-14 · [1385-neutron-networks-bff-and-networks-page-mergeview-opus](1385-neutron-networks-bff-and-networks-page-mergeview-opus.md)
- pr-report · 2026-10-14 · [1385-neutron-networks-bff-and-networks-page-opus-2](1385-neutron-networks-bff-and-networks-page-opus-2.md)
- pr-report · 2026-10-14 · [1385-neutron-networks-bff-and-networks-page-opus](1385-neutron-networks-bff-and-networks-page-opus.md)
- pr-report · 2026-10-14 · [1385-neutron-networks-bff-read-only-page](1385-neutron-networks-bff-read-only-page.md)
- pr-report · 2026-10-15 · [1385-neutron-networks-bff-and-networks-page-review-opus](1385-neutron-networks-bff-and-networks-page-review-opus.md)
- pr-report · 2026-10-15 · [1385-neutron-networks-review-brief](1385-neutron-networks-review-brief.md)
