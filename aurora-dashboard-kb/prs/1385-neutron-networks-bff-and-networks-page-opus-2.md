---
type: pr-report
date: 2026-10-14
status: open
pr: [1385]
issue: [1381, 1382]
author: mark-karnaukh-extern-sap
branch: mark-manage-networks-interface
commit: 9ed42505
---

# PR #1385: feat(network): add Neutron Networks BFF and read-only Networks page (list & details)

**Author:** mark-karnaukh-extern-sap · **State:** 🟡 Draft · **Base:** `main` ← `mark-manage-networks-interface`
**Size:** 41 files, +5106 / −211 · **Created:** 2026-10-13 · [View on GitHub](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1385)

---

## ⚖️ Verdict — how confident should you be to approve?

> **Recommendation: request changes.** Confidence to merge as-is: **low–medium.**
>
> This is a solid feature — it follows the patterns the rest of the Network code already uses, ships with a lot of tests, and the refactor it does along the way doesn't change how the existing Routers code behaves. Nothing here is dangerous (no data loss, nothing security-related). But it's still a draft, it isn't linked to an issue, and there's one real robustness problem (if one of the two list requests fails, the whole page goes blank) plus a smaller back-button bug. All of it is cheap to fix. Clear the blocker and it's good to go; the rest can be follow-ups.

**Blockers (fix before merge)**

| # | Blocker | Where | Severity | Confidence |
|---|---------|-------|----------|------------|
| B1 | If either the "own" or "shared" networks request fails, the whole list fails — so a hiccup fetching shared networks hides the project's own networks too. No test covers this. | `networksRouter.ts:88` | Major | 75 ⚠ verify |

**Gates (process / mergeability — not code defects)**

| # | Gate | Note |
|---|------|------|
| G1 | PR isn't linked to an issue/epic (the `Part of #` / `Closes #` lines are left blank). Link to #1381/#1382. | process |
| G2 | It's a draft — confirm it's meant to merge and that CI + approvals are green (couldn't check those here, see Method). | gate |

**Non-blocking (fix now or later)**

| # | Finding | Where | Severity | Confidence |
|---|---------|-------|----------|------------|
| N1 | The auto page-clamp pushes a browser-history entry, so Back gets stuck in a loop on a stale `?page=N` link. | `NetworksList.tsx:299` | Minor | 80 |
| N2 | Sorting by a column descending puts rows with no value *first*, even though the code's own comment says they should be last. | `networkHelpers.ts:135` | Trivial | 85 |
| N3 | Sort params are sent to Neutron even though the BFF re-sorts anyway; on a deployment that rejects `mtu` sorting this could fail the list. | `networksRouter.ts:69` | Minor | 45 |
| N4 | The refactor dropped the log labels on two lookups, so parse errors in the Routers code now show the wrong source name. | `routersRouter.ts:157` | Trivial | 60 |
| N5 | `fetchSecurityGroupSummaries` is added but nothing uses it yet. | `lookupHelpers.ts:73` | Trivial | 40 |

---

## What was done

The PR adds OpenStack Neutron **Networks (L2)** to `packages/aurora`, in two parts:

- **A `network.networks` tRPC BFF** with seven procedures — `list`, `getById`, `create`, `update`, `delete`, `setTags`, `listSubnets` — mounted under the `network` namespace.
- **A read-only Networks UI**: a list page (Name/ID, Status, Admin State, Subnets, Shared, External, MTU) with search, status/shared filters, sorting and pagination; and a details page with a Subnets tab and copy-to-clipboard IDs. There's also a "Networks" entry in the Network side-nav and a card on the project overview.

**What the code actually wires up vs. what's just there:** the UI only calls the three read procedures (`list`, `getById`, `listSubnets`) — a grep of the client finds no `create`/`update`/`delete`/`setTags` calls. The write procedures exist and are tested on the server but you can't reach them from the UI. The PR description/changeset say that's on purpose and the write UI comes later; the code itself only tells us those procedures are currently unused.

The PR also **refactors the existing Network server code**: shared request plumbing (`requestOrThrow`, `pickDefined`, `chunk`, `withQuery`) moves into `helpers/requestHelpers.ts`, the batched name-lookups move into `helpers/lookupHelpers.ts`, and the summary schemas (`SubnetSummary`, `NetworkSummary`, `SecurityGroupSummary`) move from `types/router.ts` into `types/index.ts`. `routersRouter` is updated to use them.

## How it is implemented

**Own + shared networks, merged, re-sorted, searched, enriched.** Neutron's `project_id` filter hides shared networks owned by other projects, so `list` fires up to two requests in parallel and merges them:

```ts
// packages/aurora/src/server/Network/routers/networksRouter.ts:88
const networks = sortNetworks(mergeNetworks(...(await Promise.all(requests))), input.sort_key, input.sort_dir)
const filteredNetworks = filterBySearchParams(networks, searchTerm, ["id", "name", "description"])
```

`getNetworkListScopes(shared)` decides which requests to send (`true`→shared only, `false`→own only, unset→both); `mergeNetworks` dedupes by id (first one wins, so "own" takes priority); and the merged list is re-sorted on the BFF side because each Neutron response is sorted on its own but the concatenation of the two isn't. Subnet names are then filled in by one batched, best-effort lookup (`fetchSubnetSummaries`, chunked 50 at a time, returns `[]` if it fails so the list never breaks over a missing name).

**Error mapping** turns Neutron's quirks into clear messages — e.g. Neutron reports "over quota" as a **409, not a 413**, so every network 409 checks for a quota message first (`networkHelpers.ts:26`). **Validation** (`types/network.ts`) keeps extension-only fields `nullish` so a deployment missing an extension doesn't break parsing, and `create` leaves `project_id` out of the body (Neutron takes ownership from the rescoped token).

**On the client**, the URL holds all the state (search/filter/sort/page), and it uses React `use()` + `Suspense` with `useDeferredValue` to keep the old list on screen while the next one loads. A `FORBIDDEN` on the list is shown inline instead of thrown.

## What it affects (blast radius)

- **The new `network.networks.*` procedures** are additive — nothing outside this PR's own client files calls them.
- **The refactor touches the existing Routers BFF.** `routersRouter` now imports the shared helpers/lookups. Checked against git history: it behaves the same as before. The two visible changes (deduping ids, chunking by 50) don't affect any path the routers actually hit today, and the chunking is really a latent bug-fix. Nothing else imported the moved symbols from their old spot, so the move breaks no callers.
- **The `networks` service key** is free-form and on by default, so the nav + card don't need registering anywhere central — same as `securitygroups`/`flavors`.

## Tests

Lots of tests ship with this: server tests for the router (`networksRouter.test.ts`, 701 lines), the schemas, the helpers, the lookups and the request helpers; client tests for every component (`NetworksList`, `NetworkListContainer`, `NetworkTableRow`, `NetworkSubnetsTable`, `NetworkDetailsView`). Breadth is good.

**The gap that matters for merge:** nothing tests what happens when **one of the two list requests fails and the other succeeds** (that's B1). Because of `Promise.all`, that case throws and blanks the whole list — exactly the kind of thing you'd want a test to pin down before trusting the two-request design. (I confirmed the tests exist and are broad, but didn't read every assertion — see Method.)

## QA — manual test plan

Covers the things unit tests can't easily check: real OpenStack data, navigation and URL state, values matching across views, and the fallback rendering.

**Core path:**

1. Open a project → Network → Networks. Confirm both your own networks and networks shared from other projects show up.
2. Apply "Shared: Yes" — only shared networks show and the URL updates. Apply "Shared: No" — only your own show.
3. Search by name — the list filters and the URL updates. Clear it — the full list comes back.
4. Change sort to Status, direction Desc — the list reorders and the URL updates.
5. Open a network — the list columns (Name/ID, Status, Admin State, Subnets, Shared, External, MTU) match the details view.
6. Subnets tab — subnet names show where known, IDs as the fallback.

**Edge cases the code reveals:**

- **Network with an empty name** — the row shows the ID as the main value, not a blank cell (`NetworkTableRow.tsx:47`).
- **Network with no subnets** — the Subnets column shows "–" (`NetworkTableRow.tsx:61`) and the Subnets tab shows an empty state (`NetworkSubnetsTable.tsx:74`).
- **50+ subnets across all networks** — if one lookup chunk fails, all subnet names quietly fall back to IDs; the list must not error (`lookupHelpers.ts:36` → `networkHelpers.ts:151`).
- **Open a non-existent network ID** — you get "Network Not Found" with a Back button, not a blank page (`$networkId.tsx:89`).
- **Back from details to the list** — search/filter/sort/page all come back (URL is the source of truth, `NetworksList.tsx:211`).
- **Restricted shared-network access** (if you can set it up) — filter to "Shared: No" and confirm your own networks still load; today the unfiltered list fails completely if the shared request is rejected (that's B1, `networksRouter.ts:88`).

## Does it deliver? (completeness vs #1381 / #1382)

No ticket is linked — the PR body still has the placeholders (`#<epic-number>`, `#<bff-issue-number>`, `#<ui-issue-number>`). The two epics given as the anchor, **#1381 (Ports BFF)** and **#1382 (Ports list & details)**, are the parallel *Ports* feature; they're used here as a **pattern reference** — they set the bar for what a complete BFF + UI feature looks like in this domain, and the tables below check whether this Networks PR clears that same bar.

**BFF completeness (pattern from #1381)**

| Requirement | Status | Notes |
|-------------|--------|-------|
| Zod schemas for every procedure's input/output | ✅ delivered | `network.ts` has `NetworkSchema`, `NetworkListItem`, `NetworkQueryParameters`, `NetworkListResponse` and all operation schemas |
| CRUD procedures (list, get, create, update, delete) | ✅ delivered | all seven present; the write ones are BFF-only in this PR |
| Supplementary UI data (name lookups for related resources) | ✅ delivered | `fetchSubnetSummaries` resolves subnet names for the list |
| User-friendly Neutron error mapping | ✅ delivered | `NetworkErrorHandlers` with quota/409 handling; `requestOrThrow` maps `SignalOpenstackApiError` → `TRPCError` |
| Router registered in the domain index | ✅ delivered | `networksRouter` mounted at `network.networks` (`Network/routers/index.ts`) |
| Unit tests (success + error paths) | ⚠️ partial | success and uniform-failure cases are covered; **partial failure (own succeeds, shared fails) is untested — this is B1** |
| BFF documentation | ✅ delivered | `packages/aurora/docs/0017_networks_bff.md` |
| Lists restricted to the current project | ✅ delivered | `project_id` scoping via `projectScopedProcedure`; `shared: false` collapses to a single own-networks request |
| Missing lookups degrade gracefully (fall back to IDs) | ✅ delivered | `fetchSummaries` catches chunk failures and returns `[]`; `applySubnetNames` falls back to IDs |

**UI completeness (pattern from #1382)**

| Requirement | Status | Notes |
|-------------|--------|-------|
| Nav access + project-overview card | ✅ delivered | `buildNavSections.ts` and the overview card, gated behind `enabledServices: ["networks"]` |
| Search, sorting, pagination with URL persistence | ✅ delivered | all state in the URL; `useDeferredValue` keeps the list visible during transitions |
| Correct list columns | ✅ delivered | Name/ID, Status, Admin State, Subnets, Shared, External, MTU — all in `NetworkTableRow.tsx` |
| Details with all expected fields + copy-to-clipboard | ✅ delivered | `NetworkDetailsView.tsx` covers the network properties; IDs are copyable |
| Graceful handling of incomplete data | ✅ delivered | empty name → ID fallback in the row; subnet-lookup failure → IDs shown |
| Design-system compliance (juno-ui-components) | ✅ delivered | uses `DataGrid`, `ContentHeader`, `TwoColumnDescriptionList` etc. throughout |
| Reusable list component for a resource-scoped sub-list | ⚠️ n/a | #1382 needs this for a Ports-in-a-Network sub-list; Networks has no equivalent scoped view in this PR's scope |

**Scope delta vs. the Ports feature:** the Networks PR hits the same completeness level that #1381/#1382 define for Ports. The one item marked partial (the partial-failure unit test) is the existing blocker, B1.

## Review — the findings in detail

Each one below says where to look, what's wrong, and what to do.

**B1 · The whole list fails if one of the two requests fails** — Major · confidence 75
*Where:* `networksRouter.ts:88`, in the `list` procedure — the `Promise.all(requests)` line.
*What's wrong:* `list` sends an "own networks" request and a "shared networks" request and awaits them with `Promise.all`. `Promise.all` rejects the moment *either* one rejects, and `requestOrThrow` turns any non-2xx into a thrown error. So if the shared-networks request has a transient 500, the whole query throws and the user sees an error — even though their own networks loaded fine. (The client special-cases a `FORBIDDEN` into an empty list, but nothing else.)
*Fix:* use `Promise.allSettled` and show whatever came back, and add a test for the own-ok / shared-fails case.

**N1 · Back-button gets stuck after an out-of-range page** — Minor · confidence 80
*Where:* the clamp effect at `NetworksList.tsx:136` calls `onPageChange`, which is `handlePageChange` at `NetworksList.tsx:299`.
*What's wrong:* `handlePageChange` is the only navigation in this file that doesn't pass `replace: true` (compare `updateSearch` at `:268`, which does). When you land on a page that no longer exists (e.g. a bookmarked `?page=5` after the list shrank), the clamp effect "fixes" the URL by pushing a new history entry. Press Back and you're on `?page=5` again, which re-clamps and pushes again — a loop.
*Fix:* give the clamp its own navigation that uses `replace: true`.

**N2 · Descending sort puts empty values on top instead of the bottom** — Trivial · confidence 85
*Where:* `compareValues` at `networkHelpers.ts:123` and `sortNetworks` at `networkHelpers.ts:135`; the comment that's wrong is at `:133`.
*What's wrong:* `compareValues` returns a fixed sign for null/undefined ("missing goes after"), but `sortNetworks` then multiplies the whole result by the direction, which flips that sign when sorting descending. So in descending order the missing values move to the top. The only sortable column that can be empty is MTU, so you see it when you sort by MTU, descending. The function's own comment and the design doc both say missing values sort last — so the code contradicts them.
*Fix:* handle null/undefined before applying the direction, so "missing last" holds both ways.

**N3 · Sort params are sent to Neutron for no reason (and might break the list)** — Minor · confidence 45
*Where:* `networksRouter.ts:69`, the destructuring `const { searchTerm, shared, project_id, ...openstackFilters } = input` — `sort_key`/`sort_dir` fall into `openstackFilters` and get forwarded to Neutron on both requests.
*What's wrong:* the BFF already re-sorts the merged list itself (`:88`), so asking Neutron to sort is wasted work. Worse, `mtu` is only a valid Neutron sort key when the `net-mtu` extension is on; on a deployment without it, some Neutron versions answer `400` and the whole list fails. I couldn't verify whether Neutron rejects or just ignores an unknown sort key — it's deployment-dependent — hence the low confidence.
*Fix:* pull `sort_key`/`sort_dir` out of `openstackFilters` so they're not sent to Neutron.

**N4 · Refactor lost the log labels on two lookups** — Trivial · confidence 60
*Where:* `routersRouter.ts:157-158`, `:183-184`, `:361-362` — the `fetchNetworkSummaries(...)` / `fetchSubnetSummaries(...)` calls.
*What's wrong:* before the refactor these passed a context string (`"routersRouter.networks"` / `"routersRouter.subnets"`) that showed up in Zod parse-error logs. They now rely on the helper's default (`"networkLookups.*"`), so a parse error in the Routers code gets logged under the wrong name and is a bit harder to trace. Behaviour is otherwise unchanged.
*Fix:* pass the `"routersRouter.*"` context string at those call sites.

**N5 · An unused helper was added** — Trivial · confidence 40
*Where:* `lookupHelpers.ts:73`, `fetchSecurityGroupSummaries`.
*What's wrong:* it's exported but nothing imports it (grep finds no callers). Almost certainly staged for the upcoming ports work rather than a mistake.
*Fix:* fine to leave if ports is coming soon; otherwise drop it to avoid dead code.

---

## Method & limitations

- Read-only, at head commit `9ed42505`; the branch was never checked out.
- `gh` is only logged in to a suspended enterprise host and github.com's API was rate-limited here, so metadata came from a web fetch of the PR page and the diff from `git fetch origin pull/1385/head`. **CI status, approvals, conflicts and review threads couldn't be read** — the gates that depend on those need a human or CI to confirm before you lean on this verdict.
- The review ran five passes (conventions, bug scan, git history / refactor, comments & doc, prior-PR patterns) with confidence scoring; severity added per finding. I confirmed the tests are broad but didn't read every assertion.
- Completeness is judged against #1381/#1382 as a *pattern reference* (the parallel Ports feature), not fetched acceptance criteria — no ticket is linked to this PR.

_Analyzed 2026-10-14 · commit `9ed42505` · model: Opus · skill: review-pr-opus_

<!-- related:auto — generated from pr/issue properties by tools/update-related.py; do not edit by hand -->
## Related

- pr-report · 2026-10-13 · [1385-neutron-networks-bff-and-networks-page-v2](1385-neutron-networks-bff-and-networks-page-v2.md)
- pr-report · 2026-10-13 · [1385-neutron-networks-bff-and-networks-page-v3](1385-neutron-networks-bff-and-networks-page-v3.md)
- pr-report · 2026-10-13 · [1385-neutron-networks-bff-and-networks-page](1385-neutron-networks-bff-and-networks-page.md)
- pr-report · 2026-10-14 · [1385-neutron-networks-bff-and-networks-page-mergeview-opus](1385-neutron-networks-bff-and-networks-page-mergeview-opus.md)
- pr-report · 2026-10-14 · [1385-neutron-networks-bff-and-networks-page-opus](1385-neutron-networks-bff-and-networks-page-opus.md)
- pr-report · 2026-10-14 · [1385-neutron-networks-bff-read-only-page](1385-neutron-networks-bff-read-only-page.md)
- pr-report · 2026-10-15 · [1385-neutron-networks-bff-and-networks-page-review-opus](1385-neutron-networks-bff-and-networks-page-review-opus.md)
- pr-report · 2026-10-15 · [1385-neutron-networks-review-brief](1385-neutron-networks-review-brief.md)
