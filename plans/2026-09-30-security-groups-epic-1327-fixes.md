# Plan: Security Groups epic #1327 fixes (#1321, #1323, #1325)

**Date:** 2026-09-30 · **Status:** implemented 2026-09-30 (uncommitted in worktree `sg-bugs-main`, branch `fix/security-groups-epic-1327`; DevStack M1–M12 and PR description pending) · **Revised:** 2026-09-30 after verification against `fe1fa280`. Follow-up renumbered 31 → 35 (31–34 are taken). Commit, push and PR-opening instructions removed; delivery is Open Question 8. One changeset instead of three. M5 is now a hard gate.

> **Addition after the security review (2026-10-01):** `tenant_id` removed from `listSecurityGroupsInputSchema` (no callers; a Neutron alias of `project_id` that could override the own-side scope), plus test "never forwards a caller-supplied tenant_id to Neutron" and a doc note in `007_security_groups_bff.md`.

## IMPLEMENTATION PLAN: Security Groups epic #1327 (#1321, #1323, #1325)

> Note on sources: the worktree `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/.claude/worktrees/sg-bugs-main` (detached `fe1fa280`) has no `.claude/` and no `CLAUDE.md`. Both are untracked, so they exist only in the main working copy. I read only those two config files there (`.claude/agents/dev-planner.md`, `CLAUDE.md`) and no code. All code findings below come from the worktree. The worktree also has **no `node_modules`**, so see Prerequisites. I left out the agent spec's emoji risk markers and used text tags instead: [BREAKING], [SECURITY], [PERF], [CAREFUL].

### Overview

This epic delivers three fixes to the Security Groups list in `packages/aurora`, as one change set destined for a single upstream PR (how it is delivered is Open Question 8):
- **#1321:** a BFF bug. With an admin token, the `Shared = No` filter returns security groups from every project.
- **#1323:** the list's DataGrid header composition is changed to the Juno `juno-pattern-datagrid-outer/-header` pattern.
- **#1325:** the `Name` cell drops its needless `<div><p>` wrapper.

The same header anti-pattern also appears in other lists. It gets recorded as a single new item (**35**) in `DOCS/FOLLOW-UPS.md` and is not fixed here.

### Architecture Analysis

**Current state:**

- `packages/aurora/src/server/Network/routers/securityGroupRouter.ts`, `list` (lines 70–121):
  - Line 74 destructures `searchTerm, project_id, shared, stateful, sort_key, sort_dir, ...queryInput`.
  - **Explicit-filter branch (lines 79–91)** runs when `shared !== undefined`. It sends one Neutron GET with `{...queryInput, shared, sort_key, sort_dir}` and **no `project_id`**. Sorting is left to Neutron and the result is not deduplicated.
  - **Default branch (lines 97–119)** runs two GETs in parallel. `own = {...queryInput, project_id, shared:false}` and `shared = {...queryInput, shared:true}`. It then dedups, applies the `stateful` and search filters, and sorts, all in the BFF.
  - **Root cause confirmed:** `ctx.openstack` is rescoped to the project, but Neutron does not limit an admin-role token to the scoped project. `GET /v2.0/security-groups?shared=false` therefore returns every non-shared security group in the cloud, which means one `default` per project. That matches the screenshot: 4× `default` + `manila-service`, where the unfiltered view shows 2.
- `packages/aurora/src/server/Network/helpers/securityGroupHelpers.ts` already has the pieces a single pipeline needs: `deduplicateSecurityGroupsById`, `filterSecurityGroupsByStateful` (a missing field counts as `true`), and `sortSecurityGroups` (nullish values sort last).
- `packages/aurora/src/server/helpers/queryParams.ts`: `appendQueryParamsFromObject` skips `undefined` and encodes booleans as `"true"`/`"false"`.
- `packages/aurora/src/server/Network/types/securityGroup.ts:52-74`: `listSecurityGroupsInputSchema` extends `projectScopedInputSchema`. `stateful` and `searchTerm` are filtered only in the BFF.
- `packages/aurora/src/server/Network/routers/securityGroupRouter.test.ts`:
  - There are **no tests at all for the `shared !== undefined` branch** or for `stateful`.
  - The "Dual-fetch mode" block (lines 318–504) uses a mock keyed on call order (`callCount`) that ignores the URL. The new tests need a mock that routes by URL query instead.
- Client, under `packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/-components/`:
  - `SecurityGroupsList.tsx:249-375` returns `<>` → `ContentHeader` + `<div className="relative">`. Inside that div, in order: the refetch-error `Message` (`mb-4`), Zone 1 `Stack` (`pb-2`, sort + Create), Zone 2 `DataGridToolbar` (filters/search/pills), `SecurityGroupListContainer`, and `CreateSecurityGroupModal`.
  - `SecurityGroupListContainer.tsx:119-203` returns `<>` → `<DataGrid>` plus, when a group is selected, `EditSecurityGroupModal` and `DeleteSecurityGroupDialog`.
  - `SecurityGroupTableRow.tsx:68-72` has the Name cell `<DataGridCell><div><p className="text-md">{sg.name}</p></div></DataGridCell>`. `text-md` is defined nowhere, in either aurora or juno, so it has no effect.
  - Parent layout (`routes/_auth/projects/$projectId.tsx:198`): the page fragment renders inside a plain block `div.min-w-0.flex-1`.
- Juno `@cloudoperators/juno-ui-components` is pinned at `9.4.0` (`packages/aurora/package.json:86`). I checked the tag `9fa9074f` read-only via `git show`:
  - `Stack` defaults are `direction="horizontal"`, `gap="0"` (→ `jn:gap-0`), and `alignment="stretch"`. So `<Stack direction="vertical">` is `flex flex-col items-stretch gap-0`: full-width children with no added spacing, the same as today's block flow.
  - `Modal` renders `{isOpen && createPortal(...)}`: nothing in-flow when closed, and a portal when open.
  - `PopupMenu` uses floating-ui with `PortalProvider.Portal`. `Select` and `ComboBox` portal too. `SearchInput` carries its own `jn:relative`. `Message` has no positioning.
  - **Result: nothing inside the SG list needs the `div.relative` positioning context.**
  - `DataGridHeader.stories.tsx` at 9.4.0 (FullyFeatured) uses the zone structure without the marker classes. `juno-pattern-datagrid-outer/-header` exist only on Juno `origin/main` (story lines 169–170) as marker class names. There is no CSS behind them and no aurora ESLint Tailwind class rule, so they are safe with 9.4.0.
  - `DataGridCell` is `flex flex-col justify-center` + padding, so bare text in a cell lays out correctly.
- Other consumers of `network.securityGroup.list`: `$securityGroupId/index.tsx:170` calls it with only `project_id` (unfiltered branch), so the fix doesn't affect it.
- Conventions:
  - `network` is an allowed commitlint scope. Subjects must not be start-, pascal- or upper-case.
  - Changesets are the release model. Past PRs add **one** `.changeset/*.md` per PR (e.g. `dedf5a8c`), so this PR adds a single one with `"@cobaltcore-dev/aurora": patch`.
  - Lingui uses `origins: false`, so moving JSX causes no `.po` churn.
  - Prettier runs `prettier-plugin-tailwindcss`, which reorders classes.
- The KB is pinned at `0169b4ad`, 12 commits behind `fe1fa280`. In the areas this plan touches, only one line differs (`floatingIpRouter.ts`), so the KB is adequate for this task.

**Proposed changes:**

- **#1321, option (b), recommended.** Restructure `list` so that every view is built from the same two sources:
  - `own = {project_id, shared:false}`
  - `shared = {shared:true}`

  Explicit `shared` picks one source, `undefined` takes both. One common pipeline follows: dedup → `stateful` → search → BFF sort. Filtered views are then subsets of "All = own ∪ shared" by construction, and `Shared=Yes` / `Shared=No` split All into two disjoint parts. Sort, `stateful` and search behave the same in every branch. As today's unfiltered path already does, `sort_key`/`sort_dir` are no longer forwarded to Neutron.
  - **Why not (a).** Adding `project_id` only when `shared === false` fixes the symptom. But it keeps two different code paths: Neutron sorting vs BFF sorting (ordering/collation can differ between filtered and unfiltered views), no dedup, and duplicated request shapes that can drift apart again. Option (b) is about the same size and removes that class of bug.
- **#1323.** Wrap the header zones in `Stack.juno-pattern-datagrid-header` inside `Stack.juno-pattern-datagrid-outer`. Render `SecurityGroupListContainer` unchanged as the outer Stack's second child. Its fragment flattens, so `<DataGrid>` becomes a direct DOM child next to the header Stack, and the Edit/Delete modals add no in-flow DOM.
  - The refetch-error `Message` moves directly **above** the outer Stack, since it is page-level status and not a header zone. `CreateSecurityGroupModal` moves **after** the outer Stack as a fragment sibling.
  - Remove `div.relative`. The visual result is the same: parent block flow, `mb-4` on Message, `pb-2` on Zone 1, and gap 0.
- **#1325.** Render `{sg.name}` directly in the Name cell.

### Potential Problems & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| [SECURITY] Scoping leak. Admins see other projects' SGs in a project-scoped view today (rows open as read-only via `isReadOnly`). The fix narrows what admins see. | Medium | Intended. Covered by the regression tests and the DevStack checklist. |
| `shared=true` without `project_id` might over-return for admins. My understanding of neutron-lib `model_query.apply_filters` is that `shared` is matched against RBAC `access_as_shared` entries whose `target_project` is `'*'` or the **requesting context's project**. If so, it is scoped correctly even for admins. **Not verified against the running DevStack version.** | Medium | Don't change it blindly. DevStack checklist item M5 is a **hard gate before merge** (an SG shared only with project C must NOT appear as admin in project A): the unit-test mock only assumes this behaviour. If it does appear, fall back per Open Question 2. |
| [CAREFUL] Ordering under explicit filters changes from Neutron DB collation to BFF `localeCompare`. | Low | Now matches the unfiltered view, which is the goal. Unit test the sort in the filtered branch. |
| Pre-existing Neutron semantics: an own SG shared via RBAC only to a *specific other* project reports `shared:false` to its owner, so it shows under `Shared=No`. | Low | Not a regression and out of scope. Record it under Open Questions (item 5). |
| Old dual-fetch tests depend on `Promise.all` call order (own first). | Low | Keep `[own, shared]` ordering in the default branch. New tests use a URL-routing mock. |
| #1323: flex-column vs block could change spacing or width. | Low | Juno 9.4.0 `Stack` gives `gap-0` + `items-stretch`. The Message sits outside the Stack, so margin behaviour is the same. Compare in the browser: before/after screenshot, DevTools spacing. |
| #1323: modal siblings inside a flex container. | Low | Juno `Modal` renders nothing in-flow (closed: no node, open: portal). Confirm in DevTools that no extra children sit under `.juno-pattern-datagrid-outer`. |
| #1323: popups mis-positioned after removing `relative`. | Low | All of them portal (PopupMenu, Select, ComboBox, Modal). Check the kebab menu, sort select and filter combobox by hand. |
| Worktree has no `node_modules`, so verification commands fail. | Low | `pnpm install --frozen-lockfile` once (Prerequisites). |
| [PERF] Request count | None | Explicit filter: 1 request (unchanged). Unfiltered: 2 (unchanged). |

### Prerequisites

- [ ] Work from the clean worktree. Create a branch from `origin/main` (`fe1fa280`), e.g. `git -C <worktree> switch -c fix/security-groups-epic-1327`. Do not touch the user's main working copy. Never push.
- [ ] `pnpm install --frozen-lockfile` at the worktree root (Node >= 24, pnpm >= 10). There is currently no `node_modules`.
- [ ] Baseline run to capture pre-existing failures: `pnpm --filter @cobaltcore-dev/aurora test`, `pnpm --filter @cobaltcore-dev/aurora typecheck`, `pnpm --filter @cobaltcore-dev/aurora lint`.
- [ ] DevStack access as admin, with at least 3 projects (A = admin, B, C) for the manual checklist.
- [ ] Decision (b) vs (a) for #1321. Default is (b). See Open Question 1.
- [ ] Decision on delivery (Open Question 8). Until it is answered, leave all changes uncommitted in the worktree.

### Implementation Steps

#### Step 1: Write failing regression tests for #1321 (test-first)

**Files to modify/create:**

- `packages/aurora/src/server/Network/routers/securityGroupRouter.test.ts`: add a new `describe("Explicit shared filter (admin token)")` inside `describe("securityGroupRouter.list")`.

**What to do:**

1. Add a URL-aware mock factory next to `createMockContextForDualFetch`, e.g. `createNeutronListMock({ requestingProjectId, groups })`:
   - Each fixture has `{ ...SecurityGroup, sharedWith: string[] }`, where `sharedWith` lists RBAC targets (`'*'` or project ids).
   - `get(url)` parses `new URL(url, "http://x").searchParams` and pushes `url` into an exposed `requestedUrls: string[]`.
   - Then it emulates the admin behaviour we observed. `project_id` filters by owner if present. `shared=true` keeps groups where `sharedWith` includes `'*'` or `requestingProjectId`. `shared=false` keeps the rest. Without `project_id`, groups from **all projects** are returned (the admin behaviour).
   - It returns `{ ok: true, json: async () => ({ security_groups: [...] }) }`, with the `sharedWith` helper field stripped.
   - Build the context the same way as the existing factory (`validateSession`, `rescopeSession` resolving the session).
2. Fixture that reproduces the bug:
   - `default` in proj-1, proj-2, proj-3 and proj-4 (all not shared).
   - `manila-service` in proj-1 (not shared).
   - `shared-wide` in proj-2, `sharedWith: ['*']`.
   - `shared-to-proj1` in proj-3, `sharedWith: ['proj-1']`.
   - `shared-to-proj9` in proj-4, `sharedWith: ['proj-9']` (must never appear).
   - `stateless-own` in proj-1, `stateful: false`.

   `requestingProjectId = "proj-1"`.
3. Tests:
   - `"shared=false sends project_id and returns only own groups"`:
     - Exactly one request is made.
     - Its query has `project_id=proj-1` and `shared=false`.
     - Result ids are exactly proj-1's non-shared groups (`default`, `manila-service`, `stateless-own`).
     - Assert `result.filter(g => g.name === "default").length === 1`. This is the #1321 regression.
   - `"shared=true sends a single shared=true request"`: one request, `shared=true`, no `project_id`. The result is `shared-wide` + `shared-to-proj1`, with no `shared-to-proj9`.
   - `"filtered results are subsets of the unfiltered list"`: loop over `shared ∈ {undefined, true, false}` × `stateful ∈ {undefined, true, false}`. Assert every filtered id ⊆ the unfiltered id set. Also assert that `ids(shared=true) ∪ ids(shared=false)` equals `ids(unfiltered)` and that the two are disjoint.
   - `"explicit filter sorts in the BFF"`: the mock returns names in reverse order. `list({ project_id, shared:false, sort_key:"name", sort_dir:"asc" })` comes back sorted. Also check `desc`. Assert that no requested URL contains `sort_key`, which matches the default branch.
   - `"explicit filter combines with stateful and searchTerm"`: `shared:false, stateful:false` → only `stateless-own`. `shared:false, searchTerm:"MANILA"` → only `manila-service`.
4. Run it. The `shared=false` test and the subset/partition test should **fail** on current code, and so should the BFF sort assertions.

**Expected outcome:**

- The new tests fail for the documented reason: 4 `default` rows and no `project_id` in the URL.

**Verification:**

- `pnpm --filter @cobaltcore-dev/aurora test src/server/Network/routers/securityGroupRouter.test.ts` shows the new failures. The existing tests stay green.

---

#### Step 2: Restructure `securityGroupRouter.list` (#1321, option b)

**Files to modify/create:**

- `packages/aurora/src/server/Network/routers/securityGroupRouter.ts`: rewrite the `list` handler body (lines 72–120) and update the router JSDoc (lines 57–68).

**What to do:**

1. Keep the destructuring on line 74 as it is.
2. Replace both branches with one pipeline:
   ```ts
   // "All" = own ∪ shared. An explicit `shared` filter selects one side, so every filtered view is a subset of "All".
   // project_id must stay on the own-side request: for admin tokens Neutron does not scope to the token's project
   // and would return every project's non-shared groups (#1321).
   const fetchOwn = () => fetchSecurityGroupsWithParams(network, { ...queryInput, project_id, shared: false })
   const fetchShared = () => fetchSecurityGroupsWithParams(network, { ...queryInput, shared: true })

   const requests = shared === undefined ? [fetchOwn(), fetchShared()] : [shared ? fetchShared() : fetchOwn()]
   const fetched = (await Promise.all(requests)).flat()

   let result = deduplicateSecurityGroupsById<SecurityGroup>(fetched)
   result = filterSecurityGroupsByStateful<SecurityGroup>(result, stateful)
   result = filterBySearchParams<SecurityGroup>(result, searchTerm, ["name", "description", "id"])
   return sortSecurityGroups<SecurityGroup>(result, sort_key, sort_dir)
   ```
   Keep the own request first in the array so the existing call-order dual-fetch tests still hold.
3. Update the JSDoc bullet for `list`. It should say that all views are built from own (project-scoped) ∪ shared, that explicit `shared` picks one side, and that filtering and sorting happen in the BFF.
4. Optional, see Open Question 6: add a short "List semantics" paragraph under "List Security Groups" in `packages/aurora/docs/007_security_groups_bff.md`.

**Expected outcome:**

- All Step 1 tests pass. Existing list tests (search, dual-fetch, sort) pass.

**Verification:**

- `pnpm --filter @cobaltcore-dev/aurora test src/server/Network/routers/securityGroupRouter.test.ts`
- `pnpm --filter @cobaltcore-dev/aurora typecheck`
- `pnpm --filter @cobaltcore-dev/aurora lint`

---

#### Step 3: Add the PR's single changeset

**Files to modify/create:**

- `.changeset/security-groups-list-fixes.md`, new file with `"@cobaltcore-dev/aurora": patch`. This is the only changeset in the PR and covers all three issues. Sample text: "Fixed the Security Groups `Shared` filter returning groups from all projects for admin users (e.g. several `default` groups). Filtered lists are now always a subset of the unfiltered list, and sorting/search behave the same with and without filters. Aligned the list's DataGrid header with the Juno pattern and simplified the Name cell markup."

**What to do:**

1. Create the file. Do not commit (see Open Question 8).
2. `pnpm format:check`. If it fails, run `pnpm format` and re-check.

**Expected outcome:**

- One changeset in the change set.

**Verification:**

- `ls .changeset/*.md` shows only `README.md` and the new file.

---

#### Step 4: Recompose the DataGrid header (#1323)

**Files to modify/create:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/-components/SecurityGroupsList.tsx`: rewrite the JSX `return` (lines 249–375).
- `packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/-components/SecurityGroupsList.test.tsx`: add a structure test.

**What to do:**

1. Target JSX (logic and props unchanged; only the wrapping and placement change):
   ```tsx
   <>
     <ContentHeader title={t`Security Groups`} projectId={projectId} />

     {/* Non-blocking error banner for refetch failures with cached data */}
     {isError && securityGroups.length > 0 && (
       <Message variant="error" className="mb-4">{listError}</Message>
     )}

     <Stack direction="vertical" className="juno-pattern-datagrid-outer">
       <Stack direction="vertical" className="juno-pattern-datagrid-header">
         {/* Zone 1: sort + primary action (bare Stack, no background) */}
         <Stack distribution="end" alignment="center" gap="2" className="pb-2">…unchanged…</Stack>
         {/* Zone 2: filters, search, active filter pills */}
         <DataGridToolbar>…unchanged…</DataGridToolbar>
       </Stack>

       {/* Renders <DataGrid> as a direct child; its Edit/Delete modals portal and add no in-flow DOM */}
       <SecurityGroupListContainer …unchanged props… />
     </Stack>

     <CreateSecurityGroupModal …unchanged props… />
   </>
   ```
2. Delete the `<div className="relative">` wrapper. Do not add `gap` to either new Stack: the 9.4.0 default `gap="0"` keeps today's spacing (Zone 1 `pb-2`, toolbar's own `py-2`).
3. Don't change `SecurityGroupListContainer.tsx`. Its root fragment is what makes `DataGrid` a direct child of the outer Stack.
4. Test in `SecurityGroupsList.test.tsx`:
   - Change the `SecurityGroupListContainer` mock's root to `<div data-testid="sg-list-container">…`. Keep the buttons so the existing tests still work.
   - Add `it("composes the DataGrid header per the Juno pattern")`:
     - `const outer = container.querySelector(".juno-pattern-datagrid-outer")`
     - `outer.children` has exactly two elements: `.juno-pattern-datagrid-header` first, then `getByTestId("sg-list-container")`.
     - The header contains `searchbar` and the `Create Security Group` button.
     - `container.querySelector("div.relative")` is `null`.
   - Take `container` from `render` and scope every query to it, not to `document`.

**Expected outcome:**

- The DOM matches the issue's target structure. There is no visual change.

**Verification:**

- `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/network/securitygroups` (quote or escape `$`).
- `pnpm --filter @cobaltcore-dev/aurora typecheck && pnpm --filter @cobaltcore-dev/aurora lint`
- Manual, `pnpm dev`: in DevTools, `.juno-pattern-datagrid-outer` has two element children (header Stack + `.juno-datagrid`). Compare spacing against a screenshot taken before the change. Open the row kebab, sort select, filter select/combobox, the Create/Edit/Delete modals, and force the refetch-error Message (e.g. stop the backend after the first load and refocus/refetch). All must render and position correctly.

---

#### Step 5: Record the follow-up for the other lists

**Files to modify/create:**

- `/Users/kirylmishchuk/projects/SAP/DOCS/FOLLOW-UPS.md`, outside the repo:
  - items 31–34 already exist, so the new item is **35**. Before writing, re-check with `grep -oE "^### [0-9]+" FOLLOW-UPS.md | sort -k2 -n | tail -1` and take max + 1 if it has moved;
  - add item **35** in section `## G. Списки и поиск`, after item 25;
  - add a summary table row after the row for 25;
  - the footer already reads `Обновлено: 30.09.2026`; bump it only if the date differs on the day of implementation.

**What to do:**

1. Summary row: `| 35 | Шапка DataGrid не по паттерну Juno в остальных списках | Списки | открыт |`
2. Item text in Russian, following the file's conventions (Где/Что/Почему не сделано сразу/Источник):
   ```md
   ### 35. Шапка DataGrid не по паттерну Juno в остальных списках

   **Где:** `network/floatingips/-components/FloatingIpsList.tsx` — `<div className="relative">`, зоны шапки
   не обёрнуты в `Stack` (ровно как было в Security Groups до #1323); `storage/-components/Ceph/Buckets/index.tsx`,
   `Ceph/Objects/ObjectBrowserView.tsx`, `Swift/Objects/index.tsx` — `<div className="relative">` и один
   `Stack direction="vertical"` без разделения на внешний Stack и Stack шапки. При разборе заодно проверить
   `Swift/Containers/index.tsx`, `compute/images/-components/List.tsx`, `compute/flavors/-components/List.tsx` —
   там тоже есть `div.relative`.

   **Что:** привести к структуре из #1323: `Stack direction="vertical" className="juno-pattern-datagrid-outer"` →
   `Stack direction="vertical" className="juno-pattern-datagrid-header"` (зоны 1–3) + `DataGrid` прямым соседом;
   `div.relative` убрать, если внутри ничто не позиционируется относительно него (в Juno 9.4.0 `Modal`, `PopupMenu`,
   `Select`, `ComboBox` порталятся, `SearchInput` сам `relative`). Классы-маркеры есть только в сторис Juno `main`,
   CSS за ними нет — с 9.4.0 безопасны.

   **Почему не сделано сразу:** по решению #1323 ограничен Security Groups; остальные списки — отдельный PR,
   чтобы не раздувать дифф эпика #1327 и проверять каждый список отдельно.

   **Источник:** план эпика #1327 (задача #1323), 30.09.2026.
   ```
3. `pnpm format:check`. The PR description (Step 7) references `FOLLOW-UPS.md` → item 35, without copying its text.

**Expected outcome:**

- The follow-up is recorded outside the repo. Nothing else in `FOLLOW-UPS.md` changes.

**Verification:**

- `grep -n "^### 35\." /Users/kirylmishchuk/projects/SAP/DOCS/FOLLOW-UPS.md` returns one hit, and `grep -c "^### 31\." …` still returns 1 (the existing `createPermissionRouter` item is untouched).
- `git -C <worktree> status` shows nothing under `DOCS` (it is outside the repo).

---

#### Step 6: Simplify the Name cell (#1325)

**Files to modify/create:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/-components/SecurityGroupTableRow.tsx`: lines 68–72.

**What to do:**

1. Replace the block with `<DataGridCell>{sg.name}</DataGridCell>`. Add no fallback (see Open Question 7).
2. Leave the Shared cell (`<BooleanValue/>` + `<p>Owner: …</p>`, lines 74–81) unchanged. It is noted only as an observation, since it is out of scope.
3. Optional one-line test in `SecurityGroupTableRow.test.tsx`: the name text's parent element is the cell. `expect(screen.getByText("web-servers").tagName).not.toBe("P")` or similar. The existing `getByText("web-servers")` (line 98) keeps working.
4. No separate changeset: the Step 3 changeset covers #1325.

**Expected outcome:**

- Same visual output: `text-md` is undefined, and Tailwind preflight already zeroes `<p>` margins. The markup is simpler.

**Verification:**

- `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/network/securitygroups/-components`. This covers `SecurityGroupTableRow.test.tsx`, `SecurityGroupListContainer.test.tsx` and `SecurityGroupsList.test.tsx`.

---

#### Step 7: Run the full gate and write the PR description

**What to do:**

1. Run the same jobs CI runs, from the worktree root:
   - `pnpm --filter @cobaltcore-dev/aurora test`
   - `pnpm --filter @cobaltcore-dev/aurora typecheck`
   - `pnpm --filter @cobaltcore-dev/aurora lint`
   - `pnpm format:check`
   - `pnpm check-i18n` (expect no `.po` diff: `origins: false`, no strings changed)
   - `pnpm build`
2. Run the manual DevStack checklist (Testing Plan below) with `pnpm dev`, pointed at DevStack. M5 must pass before the change set is handed over.
3. Deliver the change set as decided in Open Question 8. Do **not** push, and do not open the PR: the user does both.
4. Write the PR description to `DOCS/descriptions/` (the `temp-sync` skill does this), following `.github/pull_request_template.md` and the house style:
   - Suggested title: `fix(network): security groups list fixes (#1327)`. It must pass commitlint.
   - Body: summary per issue; `Closes #1321`, `Closes #1323`, `Closes #1325`; `Part of #1327`; the DevStack results table; a reference to `FOLLOW-UPS.md` item 35 (the number only; the file is outside the repo); the Network-routers observation (below).
   - No mention of Claude or AI generation, no `Not changed` section, and no mention of changesets.

**Verification:**

- All gate commands pass locally. The description file exists in `DOCS/descriptions/`.

### Testing Plan

**Unit tests:**

- [ ] `shared=false` issues one request with `project_id=<current>` and `shared=false`. Only own groups are returned, with a single `default`.
- [ ] `shared=true` issues one `shared=true` request without `project_id`. It never returns a group shared only with another project.
- [ ] For every `shared` × `stateful` combination, the filtered ids ⊆ the unfiltered ids. `Yes ∪ No = All`, and `Yes ∩ No = ∅`.
- [ ] The explicit filter sorts in the BFF (asc and desc). `sort_key`/`sort_dir` are not forwarded to Neutron.
- [ ] Explicit filter + `stateful` and explicit filter + `searchTerm` both combine correctly.
- [ ] Existing search, dual-fetch and sort tests stay green.
- [ ] `SecurityGroupsList`: the outer Stack has exactly the header Stack + the list container as children, and there is no `div.relative`.
- [ ] `SecurityGroupTableRow`: the name renders, and the existing assertions still pass.

**Integration tests:**

- [ ] None automated. E2E (`apps/dashboard/e2e`) needs real credentials. Optional: run the Playwright SG specs if the environment is available.

**Manual verification (DevStack, admin in project A = `admin`, with projects B and C existing):**

Setup:
- Make sure B and C each have a `default` SG, e.g. `openstack security group list --project B` or create one.
- Create `sg-b-wide` in B and run `openstack network rbac create --type security_group --action access_as_shared --target-all-projects sg-b-wide`.
- Create `sg-c-to-a` in C, shared to A (`--target-project <A id>`).
- Create `sg-c-to-b` in C, shared to B only.
- Create `sg-a-stateless` in A (`--stateless`).
- Create `sg-a-to-b` in A, shared to B only (`openstack network rbac create --type security_group --action access_as_shared --target-project <B id> sg-a-to-b`). Used by M12. If M12 confirms the expected semantics, it counts as one of A's own groups under `Shared = No` in M1/M2.
- Reference sets:
  - Own = `openstack security group list --project A`.
  - Shared-to-A = `curl -H "X-Auth-Token: $(openstack token issue -f value -c id)" "$NEUTRON/v2.0/security-groups?shared=true"`, with the token scoped to A.

1. **M1 Unfiltered:** record count N and names. Expected: A's own groups + `sg-b-wide` + `sg-c-to-a`. Exactly one `default`, and no `sg-c-to-b`.
2. **M2 Shared = No:** only A's own non-shared groups, **one `default`**, and count ≤ N. This is the #1321 reproduction, which previously gave 5 rows.
3. **M3 Shared = Yes:** `sg-b-wide` + `sg-c-to-a` (plus any of A's own groups shared to `*`), and count ≤ N. `M2 + M3 = N`, with no name in both.
4. **M4 Stateful = No / Yes:** each count ≤ N, and No + Yes = N. `sg-a-stateless` appears only under No.
5. **M5 (Neutron `shared` semantics for admin) — hard gate:** under Shared = Yes, `sg-c-to-b` must **not** appear. If it does, stop and go to Open Question 2. Do not hand the change set over until this passes.
6. **M6 Combinations:** (Shared=No, Stateful=No) = `sg-a-stateless` only. (Shared=Yes, Stateful=Yes). Each combination ≤ its single-filter counts.
7. **M7 Search:** `default` shows 1 row, with and without Shared=No. `sg-` gives the same set whether or not a filter is active, restricted to that filter. Search + Shared=Yes ≤ Search alone.
8. **M8 Sort:** Name asc/desc, both unfiltered and with each filter. The order is the same algorithm in both: a filtered list is an in-order subsequence of the unfiltered one.
9. **M9 URL round-trip:** reload with `?shared=false&stateful=false&search=…&sortDirection=desc`. Same results, and the pills reflect the URL.
10. **M10 Regression across roles:** repeat M1–M3 as a non-admin member of A. The results match what admin sees for A.
11. **M11 Layout (#1323/#1325):** visually the same as main. Kebab menu, sort/filter dropdowns and modals all work. The refetch-error banner appears above the header with the same spacing. The Name column text is aligned the same as before.
12. **M12 `shared` for an owner's RBAC grant to a specific project (verifies Open Question 5):** check the raw `shared` value of `sg-a-to-b` from both sides. Use `curl -H "X-Auth-Token: <token>" "$NEUTRON/v2.0/security-groups/<sg-a-to-b id>"`, once with a token scoped to A and once with a token scoped to B.
    - Expected: `shared: false` for A (the owner is not the RBAC target) and `shared: true` for B.
    - In the dashboard as A: `sg-a-to-b` appears unfiltered and under `Shared = No`, shows `Shared: No` with no "Owner:" line, and is absent under `Shared = Yes`.
    - As a member of B (project B selected): `sg-a-to-b` appears under `Shared = Yes`, read-only, with `Owner: <A id>`.
    - Informational, not a merge gate. If A sees `shared: true`, the Open Question 5 assumption is wrong. Record the actual behaviour in the PR description and revisit Open Question 5. The subset/partition guarantee (M2 + M3 = N) must hold either way.

### Acceptance Criteria

- [ ] With an admin token, `Shared = No` in project A shows only A's non-shared SGs. In the reported DevStack case that is `default` + `manila-service`.
- [ ] For every filter/search/sort combination, the row count never exceeds the unfiltered count, and filtered rows are a subset of unfiltered rows.
- [ ] `SecurityGroupsList.tsx` renders `Stack.juno-pattern-datagrid-outer` > [`Stack.juno-pattern-datagrid-header` (Zone 1, Zone 2), `DataGrid`]. There is no `div.relative`, and nothing changes visually.
- [ ] The Name cell is `<DataGridCell>{sg.name}</DataGridCell>`.
- [ ] `FOLLOW-UPS.md` has item 35 (status `открыт`) plus a summary row, and nothing else in that file changed.
- [ ] The change set contains exactly one `patch` changeset. It is delivered as decided in Open Question 8, and nothing is pushed.
- [ ] DevStack check M5 passed.
- [ ] A PR description exists in `DOCS/descriptions/` that follows the house style and has `Closes #1321`, `#1323`, `#1325`.
- [ ] No regressions in the SG detail page, which uses the unfiltered `list`.
- [ ] `pnpm --filter @cobaltcore-dev/aurora typecheck`, `pnpm --filter @cobaltcore-dev/aurora lint` and `pnpm --filter @cobaltcore-dev/aurora test` pass, and so do `pnpm format:check`, `pnpm check-i18n` and `pnpm build`.

### Observation (Network routers, missing-`project_id` pattern)

`floatingIpRouter.list` forwards `project_id`: `...openstackFilters` keeps it in `floatingIpRouter.ts:53-56`, so it is project-filtered. `listAvailablePorts` sets `tenant_id`/`project_id` (lines 97–98). `listExternalNetworks` deliberately omits `project_id`, because external networks are cross-project. `rbacPolicyRouter` and `securityGroupRuleRouter` work by id. So none of the Network routers shows the #1321 pattern, and no follow-up is needed. Other domains (Compute, Storage) were not audited. If the user wants a cloud-wide audit of admin-token over-return, that could become a follow-up candidate, but I don't recommend filing one without evidence.

### Open Questions

1. **(b) restructure vs (a) minimal for #1321?** Recommended default: **(b)**, for the reasons in Architecture Analysis. It is about the same size. It also makes sorting consistent and structurally guarantees filtered ⊆ unfiltered.
2. **If M5 fails** (i.e. `shared=true` as admin also returns groups shared only with other projects): default is to filter the shared-side results in the BFF. Keep only groups whose `project_id !== current` and that are accessible via RBAC. Or query `GET /v2.0/rbac-policies?object_type=security_group&target_tenant=<current>` plus `target_tenant=*`, and intersect. Either way it would be an extra step within #1321. I expect it to pass, based on neutron-lib's RBAC `shared` filter using the context's project, but I haven't verified it.
3. **Placement of the refetch-error `Message` and `CreateSecurityGroupModal`.** Default: Message directly above the outer Stack, as page-level status outside the DataGrid pattern, with no visual change. CreateSecurityGroupModal after the outer Stack. Alternative: Message as the first child of the header Stack.
4. **Changesets.** Resolved: a single `patch` changeset for the whole PR (Step 3), as in past PRs (e.g. `dedf5a8c`).
5. **"Shared" semantics for RBAC-to-specific-project.** Verified manually by M12. An own SG shared only to a specific other project shows `Shared: No` to its owner, because Neutron computes `shared` relative to the requester. Default: leave as-is. It is pre-existing and outside #1321. File a follow-up only if product wants "has RBAC grants" semantics.
6. **Design doc.** Should the #1321 change add a short "List semantics (own ∪ shared)" note to `packages/aurora/docs/007_security_groups_bff.md`? Default: yes, 3–5 lines. The doc's stale `limit`/`marker`/`page_reverse` parameter rows are left alone as out of scope.
7. **Name fallback.** `sg.name` may be `null`. Default: no fallback, matching the current behaviour and the issue's literal target. Using `t\`—\`` like Description would be a separate UX decision.
8. **Delivery.** Ask the user before implementing, and don't assume commits. Options: leave the changes uncommitted in the worktree; commit locally (one commit or one per issue); or export them through `temp-sync` (files + patch) for transfer to another machine. If commits are chosen: use `fix(network): …` subjects with `Closes #…` / `Part of #1327` footers. The author and `Signed-off-by` should match the identity on the user's upstream commits (`KirylSAP <kiryl.mishchuk@sap.com>`, not the local git user `KirillMishchuk`). Never push.

### Critical Files for Implementation
- /Users/kirylmishchuk/projects/SAP/aurora-dashboard/.claude/worktrees/sg-bugs-main/packages/aurora/src/server/Network/routers/securityGroupRouter.ts
- /Users/kirylmishchuk/projects/SAP/aurora-dashboard/.claude/worktrees/sg-bugs-main/packages/aurora/src/server/Network/routers/securityGroupRouter.test.ts
- /Users/kirylmishchuk/projects/SAP/aurora-dashboard/.claude/worktrees/sg-bugs-main/packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/-components/SecurityGroupsList.tsx
- /Users/kirylmishchuk/projects/SAP/aurora-dashboard/.claude/worktrees/sg-bugs-main/packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/-components/SecurityGroupTableRow.tsx
- /Users/kirylmishchuk/projects/SAP/DOCS/FOLLOW-UPS.md
