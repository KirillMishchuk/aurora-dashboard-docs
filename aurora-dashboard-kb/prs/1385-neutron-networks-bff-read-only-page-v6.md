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

## PR Review Report by [document-pr](https://github.com/KirillMishchuk/aurora-dashboard-docs/blob/main/ToolDocs/claude-config/aurora-dashboard-config/.claude/skills/document-pr/SKILL.md)

### ⚖️ &nbsp; Verdict

Recommendation: **Request Changes** &nbsp;&nbsp; Confidence to Merge: **Medium**

Solid feature, well-tested, nothing dangerous. One accessibility blocker; the rest is cosmetic.

### 🔧 &nbsp; Required Changes

| #   | Severity    | Category      | Issue                                                                                                                                                                                                                                                                                                                                                                                                                                                      | Location                 |
| --- | ----------- | ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------ |
| CR1 | 🟡 Moderate | Accessibility | Row actions menu has no keyboard trigger (`PopupMenu` without `PopupMenuToggle`).                                                                                                                                                                                                                                                                                                                                                                          | `NetworkTableRow.tsx:68` |
| P1  | —           | Process       | Mark the PR ready for review; confirm CI and approvals are green.                                                                                                                                                                                                                                                                                                                                                                                          | PR state                 |
| P2  | —           | Process       | PR description lists a fix that is not in this PR (it's on the Ports branch).                                                                                                                                                                                                                                                                                                                                                                              | PR body                  |
| P3  | —           | Process       | Link the epic/issue — the body still has the `#<epic-number>` placeholder. ⚠️ Acceptance criteria could not be verified: with no issue linked there is nothing to grade against. Epics [#1381](https://github.com/cobaltcore-dev/aurora-dashboard/issues/1381) (Ports BFF) and [#1382](https://github.com/cobaltcore-dev/aurora-dashboard/issues/1382) (Ports list & details view) are related but are the Ports feature, not this PR's acceptance source. | PR body                  |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**CR1 — Row actions menu has no keyboard trigger** · Accessibility · `NetworkTableRow.tsx:68`
`PopupMenu` renders directly around the menu items with no `<PopupMenuToggle>`. The toggle is the visible three-dot button and the only focusable trigger in the DOM — without it, keyboard users have no way to open the menu (mouse users may still reach it, depending on Juno's default rendering). `RouterTableRow.tsx` (unchanged) has the same omission, scored 0 as pre-existing; this file is new code.
_Fix:_ add `<PopupMenuToggle />` inside `<PopupMenu>`.

**P2 — Description references a Ports-branch fix** · Process · PR body
The "Router details route: use a literal route id" bullet describes work on the Ports branch, not anything in this diff (`$routerId.tsx` is untouched here). Leaving it in makes the merged history misleading.
_Fix:_ edit the PR body to remove it.

</details>

### 💡 &nbsp; Improvements

| #   | Severity   | Category     | Issue                                                                                      | Location                                              |
| --- | ---------- | ------------ | ------------------------------------------------------------------------------------------ | ----------------------------------------------------- |
| I1  | 🟢 Low     | UI/UX        | Status rendered as plain text, not `Badge`.                                                | `NetworkTableRow.tsx:49`, `NetworkDetailsView.tsx:77` |
| I2  | 🟢 Low     | UI/UX        | Admin State rendered as all-caps `UP`/`DOWN` — Quick Reject.                               | `NetworkTableRow.tsx:50`, `NetworkDetailsView.tsx:78` |
| I3  | 🟢 Low     | UI/UX        | Action `DataGridCell` missing `style={{ minWidth }}`.                                      | `NetworkTableRow.tsx:67`                              |
| I4  | 🟢 Low     | UI/UX        | Error state title uses raw `error?.message`.                                               | `NetworkSubnetsTable.tsx:35`                          |
| I5  | ⚪ Trivial | Bug          | Descending sort puts rows with no MTU first (contradicts JSDoc); no test covers this path. | `networkHelpers.ts:133–142`                           |
| I6  | ⚪ Trivial | Code Quality | Import order: `zod` after i18n imports.                                                    | `networks/index.tsx:4`                                |
| I7  | ⚪ Trivial | Code Quality | Import order: `@trpc/client` after i18n imports.                                           | `NetworksList.tsx:5`                                  |
| I8  | ⚪ Trivial | Docs         | `README` service-key list omits `networks`.                                                | `packages/aurora/README.md:183`, `:210`               |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**I1 — Status as plain text, not `Badge`** · UI/UX · `NetworkTableRow.tsx:49`, `NetworkDetailsView.tsx:77`
B.1 wants a `Badge` for status indicators; here it's plain text. Mirrors `RouterTableRow.tsx:42` and `RouterDetailsView.tsx:62`.
_Fix:_ render status through `Badge`.

**I2 — Admin State all-caps `UP`/`DOWN`** · UI/UX · `NetworkTableRow.tsx:50`, `NetworkDetailsView.tsx:78`
`` t`UP` `` / `` t`DOWN` `` are all-caps — B.19 ("Never all-caps, ever") and the Quick Reject checklist. Mirrors `RouterTableRow.tsx:44` and `RouterDetailsView.tsx:63`.
_Fix:_ sentence-case ("Up"/"Down") or use the design-system state component.

**I3 — Action cell missing `minWidth`** · UI/UX · `NetworkTableRow.tsx:67`
B.15 (CRITICAL) requires an explicit `style={{ minWidth }}` on action cells so the column doesn't collapse. Mirrors `RouterTableRow.tsx:60`.
_Fix:_ add the min-width style to the action `DataGridCell`.

**I4 — Raw `error?.message` as error title** · UI/UX · `NetworkSubnetsTable.tsx:35`
B.6: user-visible error titles should be static, controlled strings, not raw API/exception text. `NetworkSubnetsTable.tsx:35` passes `error?.message` straight into the title. No pre-existing parallel in this component tree.
_Fix:_ use a fixed title and surface the raw message (if at all) as secondary text.

**I5 — Descending sort puts null MTU first** · Bug · `networkHelpers.ts:133–142`
`compareValues` returns `1` when `a` is null — nulls sort last in ascending, correct. `sortNetworks` multiplies by `direction`; in descending mode (`-1`), `(-1) × 1 = -1`, so nulls sort **first**. The JSDoc on line 133 says "Missing values sort last" — violated in descending order. `mtu` (`z.number().nullish()`) is the only nullable sort key, and no test exercises the descending-null case (it would fail if added).
_Fix:_ guard nulls before applying direction, and add a descending-null test:

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

**I6 / I7 — Import order** · Code Quality · `networks/index.tsx:4`, `NetworksList.tsx:5`
B.13 places `zod` and framework packages (`@trpc/client`) in import Group 1, before the i18n group. Both new files put them after.
_Fix:_ move the imports into Group 1.

**I8 — `README` service-key list omits `networks`** · Docs · `packages/aurora/README.md:183`, `:210`
The consumer-facing service-key list doesn't include `networks` (`routers` was already missing). Consumers reading the README won't know the key exists.
_Fix:_ add `networks` to the service-key list.

</details>

---

## Solution Overview

<details>
<summary><strong>What was done</strong></summary>

The PR adds OpenStack Neutron **Networks (L2)** to `packages/aurora` in two parts:

**A `network.networks` tRPC BFF** with seven procedures — `list`, `getById`, `create`, `update`, `delete`, `setTags`, `listSubnets` — all `projectScopedProcedure`, mounted at `network.networks` via `Network/routers/index.ts`.

**A read-only Networks UI**: a list page (columns: Name/ID, Status, Admin State, Subnets, Shared, External, MTU) with search, Status/Shared filters, sort, and URL-state-driven pagination (50/page); a details page with a Subnets tab and copy-to-clipboard IDs; a "Networks" entry in the Network side-nav; and a card on the project overview.

**What the code wires up vs. what's just there:** only the three read procedures (`list`, `getById`, `listSubnets`) are called from the client — a grep at `9ed42505` finds no `create`/`update`/`delete`/`setTags` calls in the route files. The write procedures exist and are tested on the server but are intentionally not reachable from the UI. The design doc (`0017_networks_bff.md`) confirms this.

The PR also **refactors the shared Network server helpers**: `requestOrThrow`, `pickDefined`, `chunk`, `withQuery` move to `helpers/requestHelpers.ts`; `fetchNetworkSummaries`, `fetchSubnetSummaries` (plus a new `fetchSecurityGroupSummaries` for the forthcoming Ports feature) move to `helpers/lookupHelpers.ts`; and summary schemas (`SubnetSummary`, `NetworkSummary`, `SecurityGroupSummary`) move from `types/router.ts` to `types/index.ts`. All callers in `routersRouter` were updated.

</details>

<details>
<summary><strong>How it was implemented</strong></summary>

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

</details>

<details>
<summary><strong>What it affects (blast radius)</strong></summary>

**New `network.networks.*` procedures — additive, no outside consumers.** `git grep 'network\.networks'` at `9ed42505` finds only the new route files, their tests, `docs/0017` and the changeset. Nothing outside this PR calls them.

**Refactored helpers — all callers updated.** `routersRouter` now imports from `requestHelpers.ts` and `lookupHelpers.ts`. The behavior is unchanged; the only observable differences are batching by 50 IDs (previously one request for all) and updated Zod context strings in log output.

**`networks` service key — on by default.** Consumers with an explicit `enabledServices` allowlist need to add `"networks"` to see the new nav entry and project card. Consumers with no allowlist see it automatically on update.

**Overlap with PR #1377 (Ports).** The same helper extraction exists on the Ports branch. Whichever merges second will need a rebase; the helper files are identical across both branches and will merge cleanly. Only `buildNavSections.ts`, `routeTree.gen.ts` and `$projectId/index.tsx` need conflict resolution.

</details>

---

## QA Test Plan

<details>
<summary><strong>Happy Paths</strong></summary>

1. Open a project → Network → Networks. Confirm the list loads and shows both your project's own networks and networks shared from other projects (these are the two `Promise.all` requests).
2. Apply **Shared: Yes** — only shared networks show; URL updates. Apply **Shared: No** — only own networks show.
3. Type in the search box — list filters on name, ID and description; URL updates. Clear it — full list returns.
4. Click the **MTU** column header to sort ascending, then descending.
5. Open a network — the columns in the list row (Status, Admin State, Shared, External, MTU) should match the property panel in the details view.
6. Open the **Subnets** tab — subnet names appear where known; IDs appear as fallback if name resolution failed.

</details>

<details>
<summary><strong>Edge Cases</strong></summary>

- **Network with no name** — the row shows the ID as the primary value, not a blank (`NetworkTableRow.tsx:47`).
- **Network with no subnets** — the Subnets column shows "–"; the Subnets tab shows an empty state.
- **Network with no MTU** (mtu is `nullish`) — sorting by MTU descending should put it _last_ per the JSDoc. Currently puts it _first_ (I5, `networkHelpers.ts:135`).
- **50+ networks with subnets** — if one lookup chunk fails, subnet names fall back to IDs; the list must not error (`lookupHelpers.ts:36`).
- **Actions menu via keyboard** — Tab to the actions cell, press Enter or Space to open the menu. Currently broken: no `<PopupMenuToggle>` means no focusable trigger exists in the DOM (CR1, `NetworkTableRow.tsx:68`).
- **Open a non-existent network ID** — the detail route should show an error ("Network not found"), not a blank page.
- **External networks** (if your deployment has them) — filtering by **External: Yes** with **Shared: No** will return an empty list by design; the External column will show "No" for all rows in a typical project view.

</details>
