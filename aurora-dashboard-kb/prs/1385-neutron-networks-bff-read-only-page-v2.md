---
type: pr-report
date: 2026-10-15
status: open
pr: [1385]
issue: []
author: mark-karnaukh-extern-sap
branch: feat/neutron-networks-bff-and-client
commit: 9ed42505
---

# PR #1385: feat(network): add Neutron Networks BFF and read-only Networks page (list & details)

**Author:** mark-karnaukh-extern-sap · **State:** 🟡 Draft · **Base:** `main` ← `feat/neutron-networks-bff-and-client`
**Size:** 41 files, +5106 / −211 · **Created:** 2026-10-13 · [View on GitHub](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1385)

---

## PR Review Report

> **Recommendation: Request Changes.** Confidence to Merge: **Medium.**
>
> This is a solid feature. It follows the patterns the Network domain already uses, ships with extensive tests, and the refactor it does along the way does not change how the existing Routers code behaves. Nothing here is dangerous — no data loss, nothing security-related. One moderate finding blocks a clean merge: the row actions menu has no focusable trigger, so keyboard users cannot open it. The remaining items are improvements that mirror existing code and do not need to block the PR. Fix the accessibility blocker, work through the process items below, and this is good to merge.

### Before Merge

#### Changes Required

| #   | Description                                                                                             | Location                 | Severity    |
| --- | ------------------------------------------------------------------------------------------------------- | ------------------------ | ----------- |
| CR1 | `PopupMenu` has no `PopupMenuToggle`, so the row actions menu has no focusable trigger — keyboard users cannot open it. | `NetworkTableRow.tsx:68` | 🟡 Moderate |

#### Process To Dos

| #   | Description                                                                                             | Notes                                                                                                |
| --- | ------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| P1  | PR is still a draft.                                                                                     | Confirm it is ready and that CI and approvals are in order.                                          |
| P2  | PR description lists a fix ("Router details route: use a literal route id") that is not in this PR.      | That commit is on the Ports branch. Correct the description to avoid confusion in the merge history. |
| P3  | No issue linked — PR body still has the `#<epic-number>` placeholder.                                   | Link to the relevant epic or issue before merge.                                                     |

### Recommended Improvements

| #   | Description                                                                           | Location                                              | Severity   |
| --- | ------------------------------------------------------------------------------------- | ----------------------------------------------------- | ---------- |
| I1  | Status rendered as plain text, not `Badge`, in both list and detail.                  | `NetworkTableRow.tsx:49`, `NetworkDetailsView.tsx:77` | 🟢 Low     |
| I2  | Admin State rendered as all-caps `UP`/`DOWN` — Quick Reject.                          | `NetworkTableRow.tsx:50`, `NetworkDetailsView.tsx:78` | 🟢 Low     |
| I3  | Action `DataGridCell` missing `style={{ minWidth }}`.                                 | `NetworkTableRow.tsx:67`                              | 🟢 Low     |
| I4  | Error state title in the Subnets table uses raw `error?.message`.                     | `NetworkSubnetsTable.tsx:35`                          | 🟢 Low     |
| I5  | Descending sort puts rows with no MTU first, contradicting the JSDoc and design doc.  | `networkHelpers.ts:133–142`                           | ⚪ Trivial |
| I6  | Import order: `zod` after i18n imports.                                               | `networks/index.tsx:4`                                | ⚪ Trivial |
| I7  | Import order: `@trpc/client` after i18n imports.                                      | `NetworksList.tsx:5`                                  | ⚪ Trivial |

---

## What was done

The PR adds OpenStack Neutron **Networks (L2)** to `packages/aurora` in two parts:

**A `network.networks` tRPC BFF** with seven procedures — `list`, `getById`, `create`, `update`, `delete`, `setTags`, `listSubnets` — all `projectScopedProcedure`, mounted at `network.networks` via `Network/routers/index.ts`.

**A read-only Networks UI**: a list page (columns: Name/ID, Status, Admin State, Subnets, Shared, External, MTU) with search, Status/Shared filters, sort, and URL-state-driven pagination (50/page); a details page with a Subnets tab and copy-to-clipboard IDs; a "Networks" entry in the Network side-nav; and a card on the project overview.

**What the code wires up vs. what's just there:** only the three read procedures (`list`, `getById`, `listSubnets`) are called from the client — a grep at `9ed42505` finds no `create`/`update`/`delete`/`setTags` calls in the route files. The write procedures exist and are tested on the server but are intentionally not reachable from the UI. The design doc (`0017_networks_bff.md`) confirms this.

The PR also **refactors the shared Network server helpers**: `requestOrThrow`, `pickDefined`, `chunk`, `withQuery` move to `helpers/requestHelpers.ts`; `fetchNetworkSummaries`, `fetchSubnetSummaries` (plus a new `fetchSecurityGroupSummaries` for the forthcoming Ports feature) move to `helpers/lookupHelpers.ts`; and summary schemas (`SubnetSummary`, `NetworkSummary`, `SecurityGroupSummary`) move from `types/router.ts` to `types/index.ts`. All callers in `routersRouter` were updated.

## How it is implemented

**Own + shared networks, merged, re-sorted, searched, enriched.** Neutron's `project_id` filter hides networks that other projects share with this one, so `list` sends up to two requests in parallel:

```typescript
// packages/aurora/src/server/Network/routers/networksRouter.ts:74-79
const [ownNetworks, sharedNetworks] = await Promise.all([
  listNetworks(os, { project_id: input.project_id }),
  listNetworks(os, { shared: true }),
]);
const networks = mergeById([...ownNetworks, ...sharedNetworks]);
```

`getNetworkListScopes` (`networkHelpers.ts:106-113`) decides which requests to send based on the `shared` filter. `mergeById` deduplicates by ID (first one wins, so the "own" copy takes priority). The merged list is re-sorted by the BFF because each Neutron response is sorted on its own but their concatenation isn't. Subnet IDs are then batch-resolved via `fetchSubnetSummaries` (chunks of 50, best-effort — failures return `[]` so the list never breaks over a missing name).

**Non-shared external networks are intentionally excluded** — `docs/0017_networks_bff.md:84` documents that floating IP pools (`router:external=true, shared=false`) are served by `network.floatingIp.listExternalNetworks`, not this router. The External column and filter work for external networks that happen to also be shared.

**Error mapping** turns Neutron's quirks into clear messages. Notable: Neutron reports quota errors as **409, not 413**, so every conflict checks for a quota string first (`networkHelpers.ts:26`). `create` strips `project_id` from the body — Neutron derives ownership from the rescoped token (`networksRouter.ts:121-122`).

**On the client**, all state (search/filter/sort/page) lives in the URL. The list uses `useDeferredValue` + `React.use()` + `Suspense` to keep the old list on screen while a new one loads — the project's standard B.7 pattern. A `FORBIDDEN` on the list is shown as an inline error `Status` rather than thrown.

**Sort bug.** `sortNetworks` (`networkHelpers.ts:135`) multiplies the comparator result by a direction scalar. `compareValues` returns `1` when `a` is null, placing nulls last in ascending — correct. In descending mode, the multiplication flips the sign, placing nulls _first_. The only nullable sort key is `mtu`. See I5.

## What it affects (blast radius)

**New `network.networks.*` procedures — additive, no outside consumers.** `git grep 'network\.networks'` at `9ed42505` finds only the new route files, their tests, `docs/0017` and the changeset. Nothing outside this PR calls them.

**Refactored helpers — all callers updated.** `routersRouter` now imports from `requestHelpers.ts` and `lookupHelpers.ts`. The behavior is unchanged; the only observable differences are batching by 50 IDs (previously one request for all) and updated Zod context strings in log output.

**`networks` service key — on by default.** Consumers with an explicit `enabledServices` allowlist need to add `"networks"` to see the new nav entry and project card. Consumers with no allowlist see it automatically on update.

**Overlap with PR #1377 (Ports).** The same helper extraction exists on the Ports branch. Whichever merges second will need a rebase; the helper files are identical across both branches and will merge cleanly. Only `buildNavSections.ts`, `routeTree.gen.ts` and `$projectId/index.tsx` need conflict resolution.

## Tests

Extensive test coverage: `networksRouter.test.ts` covers the seven procedures including error paths; `networkHelpers.test.ts` covers sort and filter helpers; `requestHelpers.test.ts` and `lookupHelpers.test.ts` cover the moved utilities; and client component tests cover `NetworksList`, `NetworkListContainer`, `NetworkTableRow`, `NetworkSubnetsTable` and `NetworkDetailsView`.

**The gap:** no test covers descending sort with a null MTU (the I5 sort bug) — it would fail if added. All existing sort tests use ascending, or use fields that Neutron always populates.

## QA — manual test plan

Covers things unit tests can't easily check: real OpenStack data, filter interaction, URL persistence, and the fallback rendering the code reveals.

**Core path:**

1. Open a project → Network → Networks. Confirm the list loads and shows both your project's own networks and networks shared from other projects (these are the two `Promise.all` requests).
2. Apply **Shared: Yes** — only shared networks show; URL updates. Apply **Shared: No** — only own networks show.
3. Type in the search box — list filters on name, ID and description; URL updates. Clear it — full list returns.
4. Click the **MTU** column header to sort ascending, then descending.
5. Open a network — the columns in the list row (Status, Admin State, Shared, External, MTU) should match the property panel in the details view.
6. Open the **Subnets** tab — subnet names appear where known; IDs appear as fallback if name resolution failed.

**Edge cases the code reveals:**

- **Network with no name** — the row shows the ID as the primary value, not a blank (`NetworkTableRow.tsx:47`).
- **Network with no subnets** — the Subnets column shows "–"; the Subnets tab shows an empty state.
- **Network with no MTU** (mtu is `nullish`) — sorting by MTU descending should put it _last_ per the JSDoc. Currently puts it _first_ (I5, `networkHelpers.ts:135`).
- **50+ networks with subnets** — if one lookup chunk fails, subnet names fall back to IDs; the list must not error (`lookupHelpers.ts:36`).
- **Actions menu via keyboard** — Tab to the actions cell, press Enter or Space to open the menu. Currently broken: no `<PopupMenuToggle>` means no focusable trigger exists in the DOM (CR1, `NetworkTableRow.tsx:68`).
- **Open a non-existent network ID** — the detail route should show an error ("Network not found"), not a blank page.
- **External networks** (if your deployment has them) — filtering by **External: Yes** with **Shared: No** will return an empty list by design; the External column will show "No" for all rows in a typical project view.

## Does it deliver? (completeness vs. PR #1377 Ports pattern)

No issue is linked — the PR body still has the placeholder lines (`#<epic-number>`, `#<bff-issue-number>`). PR **#1377 (Ports BFF + list & details)** is used here as a **pattern reference** — it sets the bar for what a complete Network BFF + UI feature looks like, and the tables below check whether this Networks PR clears that same bar.

**BFF completeness**

| Requirement                                                  | Status     | Notes                                                                                                                           |
| ------------------------------------------------------------ | ---------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Zod schemas for every procedure's input/output               | ✅         | `types/network.ts`: `NetworkSchema`, `NetworkListItem`, `NetworkQueryParameters`, `NetworkListResponse`, plus operation schemas |
| CRUD procedures (list, get, create, update, delete, setTags) | ✅         | All seven present; write procedures are BFF-only in this PR                                                                     |
| Supplementary name lookups for related resources             | ✅         | `fetchSubnetSummaries` resolves subnet names for the list                                                                       |
| User-friendly Neutron error mapping                          | ✅         | `NetworkErrorHandlers` with quota/409/404/403 handling                                                                          |
| Router registered in domain index                            | ✅         | `networksRouter` mounted at `network.networks` (`Network/routers/index.ts`)                                                     |
| Unit tests (success + error paths)                           | ⚠️ partial | Success and uniform-failure paths covered; descending sort with null key is untested (I5)                                       |
| BFF documentation                                            | ✅         | `packages/aurora/docs/0017_networks_bff.md` (495 lines)                                                                         |
| Requests scoped to the current project                       | ✅         | `projectScopedProcedure` throughout; admin users get no unscoped view in the read-only tier                                     |
| Lookup failures degrade gracefully                           | ✅         | `fetchSummaries` catches chunk failures and returns `[]`; `applySubnetNames` falls back to IDs                                  |

**UI completeness**

| Requirement                                               | Status     | Notes                                                                                                                                                                                                                            |
| --------------------------------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Nav entry + project-overview card                         | ✅         | `buildNavSections.ts` and overview card, gated on `enabledServices: ["networks"]`                                                                                                                                                |
| Search, sort, pagination with URL persistence             | ✅         | All state in the URL; `useDeferredValue` keeps the list visible during transitions                                                                                                                                               |
| Correct list columns                                      | ✅         | Name/ID, Status, Admin State, Subnets, Shared, External, MTU                                                                                                                                                                     |
| Details view with all expected fields + copy-to-clipboard | ✅         | `NetworkDetailsView.tsx` covers network properties; IDs are copyable                                                                                                                                                             |
| Graceful handling of incomplete data                      | ✅         | Empty name → ID fallback; subnet lookup failure → IDs shown                                                                                                                                                                      |
| Design-system compliance (Juno components)                | ⚠️ partial | Uses `DataGrid`, `ContentHeader`, `TwoColumnDescriptionList` etc. throughout; but Status/AdminState use plain text and all-caps instead of `Badge` and sentence-case (I1, I2) — mirrors pre-existing pattern in `RouterTableRow` |
| Keyboard-accessible action menu                           | ❌         | `PopupMenu` has no `PopupMenuToggle` — no focusable trigger (CR1)                                                                                                                                                                |

## Review — The Findings in Detail

### Changes Required

**CR1 · `PopupMenu` without `PopupMenuToggle`** — 🟡 Moderate  
_Where:_ `NetworkTableRow.tsx:68`.  
_What's wrong:_ the actions cell renders `<PopupMenu>` directly around the menu items with no `<PopupMenuToggle>`. The toggle renders the visible three-dot button and is the only focusable trigger in the DOM. Without it, keyboard users have no way to open the menu; mouse users may still reach it depending on Juno's default rendering.  
_Pre-existing:_ `RouterTableRow.tsx` (unchanged) has the same omission. That is scored 0 as a pre-existing issue. This file is new code.  
_Fix:_ add `<PopupMenuToggle />` inside `<PopupMenu>`.

### Recommended Improvements

**I1 · Status as plain text, not `Badge`** — 🟢 Low  
_Where:_ `NetworkTableRow.tsx:49`, `NetworkDetailsView.tsx:77`.  
_Pre-existing:_ mirrors `RouterTableRow.tsx:42` and `RouterDetailsView.tsx:62`.

**I2 · Admin State renders as all-caps `UP`/`DOWN`** — 🟢 Low  
_Where:_ `NetworkTableRow.tsx:50`, `NetworkDetailsView.tsx:78`.  
B.19 ("Never all-caps (ever)") and the Quick Reject checklist. Pre-existing: mirrors `RouterTableRow.tsx:44` and `RouterDetailsView.tsx:63`.

**I3 · Action cell missing `minWidth`** — 🟢 Low  
_Where:_ `NetworkTableRow.tsx:67`.  
B.15 CRITICAL requires explicit `style={{ minWidth }}` on action cells. Pre-existing: mirrors `RouterTableRow.tsx:60`.

**I4 · Raw `error?.message` as error title in Subnets table** — 🟢 Low  
_Where:_ `NetworkSubnetsTable.tsx:35`.  
B.6: user-visible error titles should be static, controlled strings, not raw API/exception messages. No pre-existing parallel in this component tree.

**I5 · Descending sort puts null MTU first, contradicting the JSDoc** — ⚪ Trivial  
_Where:_ `networkHelpers.ts:133–142`.  
_What's wrong:_ `compareValues` returns `1` when `a` is null — null "loses" in a standard comparator and sorts last in ascending. `sortNetworks` multiplies the result by `direction`; in descending mode (`direction = -1`), `(-1) × 1 = -1`, so null sorts _before_ any defined value. The JSDoc on line 133 says "Missing values sort last" — violated in descending order. `mtu` (`z.number().nullish()`) is the only nullable sort key.  
_Fix:_ extract the null guard before applying direction:

```typescript
return [...networks].sort((a, b) => {
  const av = a[sortKey],
    bv = b[sortKey];
  if (av == null && bv == null) return 0;
  if (av == null) return 1;
  if (bv == null) return -1;
  return direction * compareValues(av, bv);
});
```

**I6 / I7 · Import order violations** — ⚪ Trivial  
_Where:_ `networks/index.tsx:4` (`zod` after i18n Group 2); `NetworksList.tsx:5` (`@trpc/client` after i18n). B.13 places `zod` and framework packages in Group 1, before i18n. Both files are new.

**Below the threshold — noted, not worth acting on:**

- External networks visibility gap (25): intentional per `docs/0017_networks_bff.md:84`
- Bare `<Button>` in error boundary fallback (25): mirrors `RoutersList.tsx`
- `distribution="end"` in pagination zone (25): read-only page, no create button
- Neutron policy rule names in 403 messages (25): pre-existing pattern across Network/Compute/Storage
- Double-fetch on details page (0): pre-existing pattern from `$routerId.tsx:127-129`
- `validateAndEncodeResourceId` return discarded in `listSubnets` (0): no exploit path, consistent with `routersRouter.ts`

---

## Method & limitations

- Read-only at head commit `9ed42505`; the branch was never checked out.
- `gh` CLI has only a stale enterprise host entry (`github.tools.sap`, expired). GitHub.com API was accessed via `curl` (unauthenticated, 60 req/hr). **CI status was confirmed from the PR API response; review threads and approvals were not read.**
- Diff fetched via `git fetch origin refs/pull/1385/head`; files read individually with `git show 9ed42505:<path>`. Seven parallel review agents ran (conventions, bug scan, historical context, discussion, comment compliance, API contract, security), followed by a scoring pass and a targeted fact-check on key claims.
- Completeness compared against PR #1377 (Ports BFF + UI) as a pattern reference — no issue is linked to this PR.
- Note: a separate Opus-model analysis of this PR (`1385-neutron-networks-bff-and-networks-page-mergeview-opus.md`) identified an additional blocker — `Promise.all` failing if the shared-networks request errors, blanking the whole list — that this analysis did not surface above the 75 threshold. That finding is worth verifying before merge.

_Analyzed 2026-10-15 · commit `9ed42505` · skill: document-pr_

<!-- related:auto — generated from pr/issue properties by tools/update-related.py; do not edit by hand -->

## Related

- pr-report · 2026-10-13 · [1385-neutron-networks-bff-and-networks-page-v2](1385-neutron-networks-bff-and-networks-page-v2.md)
- pr-report · 2026-10-13 · [1385-neutron-networks-bff-and-networks-page-v3](1385-neutron-networks-bff-and-networks-page-v3.md)
- pr-report · 2026-10-13 · [1385-neutron-networks-bff-and-networks-page](1385-neutron-networks-bff-and-networks-page.md)
- pr-report · 2026-10-14 · [1385-neutron-networks-bff-and-networks-page-mergeview-opus](1385-neutron-networks-bff-and-networks-page-mergeview-opus.md)
- pr-report · 2026-10-14 · [1385-neutron-networks-bff-and-networks-page-opus-2](1385-neutron-networks-bff-and-networks-page-opus-2.md)
- pr-report · 2026-10-14 · [1385-neutron-networks-bff-and-networks-page-opus](1385-neutron-networks-bff-and-networks-page-opus.md)
- pr-report · 2026-10-14 · [1385-neutron-networks-bff-read-only-page](1385-neutron-networks-bff-read-only-page.md)
- pr-report · 2026-10-15 · [1385-neutron-networks-bff-and-networks-page-review-opus](1385-neutron-networks-bff-and-networks-page-review-opus.md)
- pr-report · 2026-10-15 · [1385-neutron-networks-review-brief](1385-neutron-networks-review-brief.md)
