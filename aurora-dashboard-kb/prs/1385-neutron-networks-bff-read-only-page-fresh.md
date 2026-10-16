---
type: pr-report
date: 2026-10-16
status: open
pr: [1385]
issue: []
author: mark-karnaukh-extern-sap
branch: mark-manage-networks-interface
commit: 9ed4250
---

# PR #1385: feat(network): add Neutron Networks BFF and read-only Networks page (list & details)

**Author:** mark-karnaukh-extern-sap · **State:** 🟡 Draft · **Base:** `main` ← `mark-manage-networks-interface`
**Size:** 41 files, +5106 / −211 · **Created:** 2026-10-13 · [View on GitHub](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1385)

---

## PR Review Report by [review-and-comment-pr](https://github.com/KirillMishchuk/aurora-dashboard-docs/blob/main/ToolDocs/claude-config/aurora-dashboard-config/.claude/skills/review-and-comment-pr/SKILL.md)

### ⚖️ &nbsp; Verdict

> Recommendation: **🔴 Request Changes** &nbsp;&nbsp;&nbsp;&nbsp; Confidence to Merge: **Medium**
>
> Solid, well-tested feature — two quick checklist violations (PopupMenu toggle, all-caps admin state), a real sort bug when null MTU values are sorted descending, and merge conflicts with the open Ports PR. Fix the three code issues and the conflicts, clear the process to-dos, and this is ready. CI is fully green on the head commit.

### 🔧 &nbsp; Required Changes

| #   | Severity    | Category      | Issue                                                                                                                                                    | Location                                                     |
| --- | ----------- | ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| CR1 | 🟡 Moderate | Accessibility | `PopupMenu` has no `PopupMenuToggle` — keyboard users cannot open the row actions menu.                                                                  | `NetworkTableRow.tsx:68`                                     |
| CR2 | 🟡 Moderate | UI/UX         | Admin State rendered as all-caps `UP`/`DOWN` — Quick Reject.                                                                                             | `NetworkTableRow.tsx:50`, `NetworkDetailsView.tsx:78`        |
| CR3 | 🟠 Major    | Bug           | Descending sort puts null-MTU networks first, contradicting the JSDoc contract "missing values sort last".                                               | `networkHelpers.ts:142`                                      |
| CR4 | 🟡 Moderate | Code Quality  | Real merge conflicts with open PR #1377 (Ports) in `routeTree.gen.ts`, locales, and `Network/routers/index.ts`.                                          | `routeTree.gen.ts`, `locales/**`, `Network/routers/index.ts` |
| P1  | —           | Process       | PR is still a draft — mark ready for review when all changes are addressed.                                                                              | PR state                                                     |
| P2  | —           | Process       | PR description bullet for the `$routerId.tsx` literal-route-id fix describes work on the Ports branch, not this diff.                                    | PR body                                                      |
| P3  | —           | Process       | All three issue links (`#<epic-number>`, `#<bff-issue-number>`, `#<ui-issue-number>`) are template placeholders. Acceptance criteria cannot be verified. | PR body                                                      |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**CR1 — PopupMenu has no keyboard trigger** · Accessibility · `NetworkTableRow.tsx:68`
`PopupMenu` renders directly with `PopupMenuOptions` but no `<PopupMenuToggle>`. The Quick Reject Checklist explicitly flags "`PopupMenu` without `PopupMenuToggle` as trigger", and B.14 mandates `<PopupMenuToggle as="div"><Button icon="moreVert" /></PopupMenuToggle>`. Without a toggle, keyboard users have no focusable element to open the three-dot menu. `RouterTableRow.tsx:82` has the same omission (pre-existing; scored 0) — this file is new code and the same project rule applies.
_Fix:_ Wrap `PopupMenuOptions` inside a `<PopupMenuToggle as="div"><Button icon="moreVert" size="small" /></PopupMenuToggle>`:

```tsx
<PopupMenu>
  <PopupMenuToggle as='div'>
    <Button
      icon='moreVert'
      size='small'
    />
  </PopupMenuToggle>
  <PopupMenuOptions>
    <PopupMenuItem
      label={t`Show Details`}
      onClick={navigateToDetailsPage}
    />
  </PopupMenuOptions>
</PopupMenu>
```

**CR2 — Admin State all-caps** · UI/UX · `NetworkTableRow.tsx:50`, `NetworkDetailsView.tsx:78`
Both files render `network.admin_state_up ? t\`UP\` : t\`DOWN\``. The Quick Reject Checklist flags "String using… all-caps" and B.19 says "Never all-caps, ever." `RouterTableRow.tsx:44`and`RouterDetailsView.tsx:63`have the same pattern (pre-existing), but the rule applies to new code.
_Fix:_ Sentence-case:`t\`Up\``/`t\`Down\``, or use the design-system state indicator if one exists for boolean states.

**CR3 — Descending sort puts null MTU first** · Bug · `networkHelpers.ts:142`
`sortNetworks` at line 142: `direction * compareValues(a[sortKey], b[sortKey])`. When `b` is null, `compareValues` returns `-1`; in descending mode `(-1) * (-1) = 1`, so the comparator puts null _before_ non-null values. The JSDoc at line 133 states "Missing values sort last" — violated for descending direction. `mtu` is the only nullable sort key (schema: `z.number().nullish()`), and no test covers the descending-null case (the test at line 179 only uses ascending).
_Fix:_ Guard nulls before applying direction so they always sort last:

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

Also add a descending-null test.

**CR4 — Merge conflicts with PR #1377 (Ports)** · Code Quality · multiple files
`git merge-tree --write-tree` against the Ports branch head (`512f01b1`) shows CONFLICT in 7 files: `routeTree.gen.ts`, `buildNavSections.test.ts`, `locales/de/messages.po`, `locales/de/messages.ts`, `locales/en/messages.po`, `locales/en/messages.ts`, `Network/routers/index.ts`. The PR description says the helper extraction "is the same commit as on the Ports branch, so the two branches don't conflict" — this is accurate for the helper files themselves (they are byte-identical), but generated files (`routeTree.gen.ts`) and locale catalogs diverged independently.
_Fix:_ Rebase onto the Ports branch (or onto `main` after Ports merges). The helper files will merge cleanly; `routeTree.gen.ts` and locales need a manual `pnpm check-i18n` + route-tree regeneration.

**P2 — Description references a Ports-branch fix** · Process · PR body
The bullet "Router details route: use a literal route id in `createFileRoute`…" describes a change in `$routerId.tsx` that is not in this PR's changed-file list. Leaving it conflates what this PR actually did.
_Fix:_ Remove the bullet from the PR description.

</details>

### 💡 &nbsp; Improvements

| #   | Severity   | Category     | Issue                                                                                                                                                                                                                       | Location                              |
| --- | ---------- | ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------- |
| I1  | 🟢 Low     | UI/UX        | Error state in Subnets table uses raw `error?.message` as title; may show API/exception text to users.                                                                                                                      | `NetworkSubnetsTable.tsx:35`          |
| I2  | ⚪ Trivial | Code Quality | Import order: `zod` appears after i18n imports (B.13 Group 1).                                                                                                                                                              | `networks/index.tsx:4`                |
| I3  | 🟢 Low     | Docs         | README service-key lists (`README.md:183`, `:210`) do not include `"networks"` — consumers using `enabledServices` won't know the key.                                                                                      | `packages/aurora/README.md:183, :210` |
| I4  | 🟢 Low     | Security     | Admin-only provider fields (`provider:network_type`, `provider:physical_network`, `provider:segmentation_id`) are included in `NetworkSchema` and travel in the JSON payload for admin sessions, though no UI renders them. | `types/network.ts:54–56`              |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**I1 — Raw `error?.message` as error title** · UI/UX · `NetworkSubnetsTable.tsx:35`
`<Status status="error" title={error?.message || t\`Failed to Load Subnets\`}>`passes the raw API/exception message as the title. B.6 recommends static, controlled copy for user-visible error titles. The fallback string is reasonable, but`error?.message`can expose Neutron internal messages. This pattern is pre-existing in`FloatingIpListContainer.tsx`and`RouterInterfacesTable.tsx`; the better pattern (static title, raw message in `body`) is used in storage components like `CorsRulesTab.tsx`.
_Fix:_ Use a static title and move the raw message to `body`: `title={t\`Failed to Load Subnets\`} body={error?.message}`.

**I2 — Import order** · Code Quality · `networks/index.tsx:4`
`zod` (B.13 Group 1 — "React / framework") is imported at line 4, after the i18n imports at lines 2–3. Move `z from "zod"` before the `@lingui` imports.

**I3 — README omits `"networks"` service key** · Docs · `packages/aurora/README.md:183, :210`
Two consumer-facing lists document available `enabledServices` keys and neither includes `"networks"` (or `"routers"`, which is also missing — pre-existing). Consumers reading the README to configure `enabledServices` won't find this key.
_Fix:_ Add `"networks"` to both lines 183 and 210. Consider also adding `"routers"`.

**I4 — Provider fields in NetworkSchema** · Security · `types/network.ts:54–56`
`NetworkSchema` includes `"provider:network_type"`, `"provider:physical_network"`, and `"provider:segmentation_id"` as `z.number().nullish()` / `z.string().nullish()`. Neutron only returns these for admin roles; for non-admin users they are absent. When an admin uses the dashboard, the raw VLAN segmentation ID and physical network name are visible in browser network logs even though no UI renders them. The BFF pattern elsewhere (e.g. Swift's TempURL key redaction) strips fields the UI doesn't need.
_Fix:_ Remove the three `provider:*` fields from `NetworkSchema` since neither the list nor the details view consumes them. If provider attributes need to be shown to admins in a future version, add an explicit admin-gated schema at that time.

</details>

---

## Solution Overview

<details>
<summary><strong>What was done</strong></summary>

The PR adds OpenStack Neutron **Networks (L2)** to `packages/aurora` in two parts.

**A `network.networks` tRPC BFF** with seven procedures — `list`, `getById`, `create`, `update`, `delete`, `setTags`, `listSubnets` — all `projectScopedProcedure`, mounted at `network.networks` in `Network/routers/index.ts`. Only the three read procedures (`list`, `getById`, `listSubnets`) are called from the client; the write procedures exist and are tested but are not reachable from the UI yet.

**A read-only Networks UI**: a list page with columns Name/ID, Status, Admin State, Subnets, Shared, External, MTU; search, Status and Shared filters, sort by Name/Status/MTU, and URL-state pagination (50 per page); a details page with copy-to-clipboard IDs and a Subnets tab; a "Networks" entry in the Network side-nav; and a card on the project overview. Both gated on the `"networks"` key in `enabledServices`.

**A helper extraction refactor**: `requestOrThrow`, `pickDefined`, `chunk`, and `withQuery` move from `routerHelpers.ts` to the new `helpers/requestHelpers.ts`; `fetchNetworkSummaries`, `fetchSubnetSummaries`, and the new `fetchSecurityGroupSummaries` move to `helpers/lookupHelpers.ts`; summary schemas (`SubnetSummary`, `NetworkSummary`, `SecurityGroupSummary`) move from `types/router.ts` to `types/index.ts`. All callers in `routersRouter.ts` were updated.

</details>

<details>
<summary><strong>How it is implemented</strong></summary>

**Own + shared networks, merged and re-sorted.** Neutron's `project_id` filter hides shared networks from other projects, so `list` sends up to two requests in parallel and merges by ID (first occurrence wins):

```typescript
// networksRouter.ts:74-79
const [ownNetworks, sharedNetworks] = await Promise.all([
  listNetworks(os, { project_id: input.project_id }),
  listNetworks(os, { shared: true }),
]);
const networks = mergeNetworks(...results);
```

`getNetworkListScopes` (`networkHelpers.ts:106-113`) decides which requests to send: `shared=true` → only the shared request; `shared=false` → only the own request; `shared=undefined` → both. After merging, the BFF re-sorts because each Neutron response is sorted individually but the concatenation isn't.

**Subnet name resolution.** After merging and filtering, subnet IDs are batch-resolved into names via `fetchSubnetSummaries` — one request per chunk of 50, best-effort (failures return `[]` so the list never breaks over a missing name). Resolved names are added to each network as `subnet_details` alongside the raw IDs.

**Error mapping.** Network-specific Neutron quirks get clear messages: quota errors arrive as 409 Conflict (not 413), so every conflict response checks for the word "quota" first (`networkHelpers.ts:26`). `create` strips `project_id` from the body — Neutron derives ownership from the rescoped token (`networksRouter.ts:121-122`).

**Client state.** All URL-driving state (search, filters, sort, page) lives in search params. The list uses `useDeferredValue` + `React.use()` + `Suspense` to keep the previous result on screen while a new query loads — consistent with the B.7 pattern for list pages. A `FORBIDDEN` on list is shown inline (not thrown) to let other parts of the page remain usable.

**Details route.** The loader calls `getById` silently (swallowing errors) for the page title; the component's `trpcReact.network.networks.getById.useQuery` call handles the actual data, errors, and retry. This matches the existing pattern in `$routerId.tsx`.

</details>

<details>
<summary><strong>What it affects (blast radius)</strong></summary>

**`network.networks.*` procedures — additive, no outside consumers.** `git grep 'network\.networks'` at `9ed42505` finds only the new route files, their tests, `docs/0017`, and the changeset. No existing code calls them.

**Refactored helpers — all callers updated.** `routersRouter.ts` now imports `requestOrThrow`, `pickDefined`, `chunk` from `requestHelpers.ts` and the lookup functions from `lookupHelpers.ts`. The helpers are byte-identical across both this PR and the Ports PR (`requestHelpers.ts` SHA matches exactly). Behavior is unchanged except that lookup requests are now chunked in batches of 50.

**`"networks"` service key — on by default.** Consumers with an explicit `enabledServices` allowlist must add `"networks"` to see the new nav entry and project card. `packages/aurora/README.md` does not yet document this key (I3).

**Overlap with PR #1377 (Ports).** `requestHelpers.ts` and `lookupHelpers.ts` are identical across both branches and will merge cleanly. However, `routeTree.gen.ts`, the locale catalogs, `buildNavSections.test.ts`, and `Network/routers/index.ts` have confirmed conflicts (CR4). Whichever branch merges second needs a rebase.

</details>

---

## QA Test Plan

<details>
<summary><strong>Core Path</strong></summary>

1. Open a project → Network → Networks. Confirm the list loads and shows both the project's own networks and networks shared from other projects (two parallel `GET /v2.0/networks` requests — verify in the browser network tab).
2. Apply **Shared: Yes** — only shared networks show; URL updates with `shared=true`. Apply **Shared: No** — only own networks show.
3. Type in the search box — list filters by name, ID, and description; URL updates with `search=`. Clear it — full list returns.
4. Click the **MTU** column header to sort ascending — networks with `mtu: null` should appear last. Sort descending — currently, null-MTU networks appear first (CR3, fixed by the bugfix).
5. Open a network — columns in the list (Status, Admin State, Shared, External, MTU) should match the property panel in the details view.
6. Open the **Subnets** tab — subnet names appear where known; IDs appear as fallback if name resolution failed. A network with no subnets shows an empty state.

</details>

<details>
<summary><strong>Edge Cases</strong></summary>

- **Network with no name** — row shows the ID as the primary value; `network.name || network.id` at `NetworkTableRow.tsx:47`.
- **Network with no subnets** — Subnets column shows "–"; Subnets tab shows empty state.
- **Network with no MTU** (`mtu: null`) — sorting by MTU descending should put it last. Currently puts it first until CR3 is fixed (`networkHelpers.ts:142`).
- **50+ networks with subnets** — if one lookup chunk fails, subnet names fall back to IDs; the list must not error (`lookupHelpers.ts:36` catch returns `[]`).
- **Actions menu via keyboard** — Tab to the actions cell, press Enter or Space to open the menu. Currently broken: no `PopupMenuToggle` means no focusable trigger (CR1, `NetworkTableRow.tsx:68`).
- **Open a non-existent network ID** — detail route shows "Network Not Found" with a "Back to Networks" button; tests `errorCode === "NOT_FOUND"` at `$networkId.tsx:83-85`.
- **FORBIDDEN on list** — renders inline error (`NetworksList.tsx:61-63`) rather than throwing; rest of project nav remains usable.
- **External networks** — filtering by **Shared: No** with **External: Yes** returns an empty list by design; the External column shows "–" for networks where `router:external` is absent (extension not enabled in deployment).
- **Project switch** — Networks component is keyed on `projectId` (`networks/index.tsx:73`) so a project change triggers a full remount, preventing stale data.

</details>

---

_Analyzed 2026-10-16 · commit `9ed4250` · read-only; no review threads on this PR; security-reviewer agent used · skill: review-and-comment_
