# Plan: PR #1207 review-feedback & test fixes

**Date:** 2026-08-28 · **Status:** partially implemented 2026-08-28 (Steps 1-3, 5-10, 12, 14 done — typecheck/214 test files/5476 tests/lint/format/i18n/build all green, security review clean; Steps 4 & 11 deferred by design to a follow-up PR per Q1; Step 13 — GitHub thread replies, issue filing — not yet done, pending human review before posting)

> Fixes CodeRabbit/Copilot review findings and CI test failures on
> [PR #1207](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1207) (branch
> `kiryl-ceph-permissions`), already merged with `main`, working tree clean at `67b55149`.

## Overview

PR #1207 (`feat(aurora): add Ceph permission controls`) is green on every CI job except `test`, where 2 assertions in the new permission-gating suites are stale relative to UI changes that arrived via the main merge. On top of that there are 10 unresolved review comments (7 CodeRabbit, 3 Copilot) plus one unanswered user question. This plan unblocks CI first, then works through the review findings in risk order, and explicitly separates findings that are **inside this PR's diff** from findings on code that is **byte-identical to `origin/main`**.

## Architecture Analysis

**Current state (verified against `HEAD = 67b55149`, merge-base with `origin/main` = `70367891` = `origin/main` tip):**

The PR diff is 32 files. Files relevant here:

| File | In PR diff? |
| --- | --- |
| `.../Ceph/Buckets/CorsRulesTable.tsx` + `.test.tsx` | yes |
| `.../Ceph/Objects/ObjectBrowserView.tsx` + `.test.tsx` | yes |
| `.../Ceph/Buckets/BucketHeaderActions.tsx` | yes |
| `.../Ceph/Buckets/CredentialPrompt.tsx` | yes |
| `.../Ceph/Buckets/LifecycleRulesTab.tsx` | yes |
| `.../Ceph/Buckets/LifecycleRulesTab.test.tsx` | **new file** |
| `.../Ceph/Buckets/LifecycleRulesTable.test.tsx` | **new file** |
| `.../Ceph/hooks/useCephPermissions.ts` | **new file** |
| `src/locales/{de,en}/messages.po` | yes (+2 msgids each) |
| `.../Ceph/Buckets/LifecycleRuleForm.tsx` | **NO — identical to `origin/main`** |
| `.../Ceph/Buckets/utils/lifecycleUtils.ts` | **NO — identical to `origin/main`** |
| `src/server/Storage/routers/ceph/lifecycleRouter.ts` | **NO — identical to `origin/main`** |

Those last three arrived on the branch through the `main` merge that pulled in PR #1178 (Ceph lifecycle management); CodeRabbit's incremental review picked them up as "new" and commented on them. They are pre-existing `main` code, not part of this PR's actual diff.

Existing patterns the fixes must follow:

- Permission gating: `useCephPermissions(projectId)` returns `{ permissions, isLoading, isError }`, defaults all-false (fail-closed). Keys map to `storage:<resource>:<action>` in `PERMISSION_MAP`.
- Icon-only kebab a11y: `ObjectBrowserView.tsx:663` uses `<Button icon="moreVert" title={t\`More Actions\`} />`. Juno's `Button` (9.4.0, verified against tag `@cloudoperators/juno-ui-components@9.4.0` in `../juno`) computes `titleValue = title || label || ""` and puts it on both the `<button>` and the inner `<Icon>`; `label` also renders **visible text**, `title` does not. `{...props}` is spread, so `aria-label` also passes through.
- Table row actions: `PopupMenuItem label={t\`Edit <Resource>\`}` / `t\`Delete <Resource>\`` (CorsRulesTable and LifecycleRulesTable are structural twins).
- Table unit tests: `CorsRulesTable.test.tsx` is the model — renders the table component directly, mocks `@/client/trpcClient` + `@/client/hooks/useProjectId`, uses a `Wrapper` (I18nProvider) and a `PortalWrapper` (I18nProvider + PortalProvider) for popup-menu assertions.

**Proposed changes:** repair the two stale assertions, tighten one vacuous assertion, add regression coverage for the `mutationsBlocked` gate that the merge restored, replace the duplicated test file, and apply the three in-diff review fixes (a11y name, permission-error state, blocked-mutations explanation). The out-of-diff lifecycle findings are staged separately behind a scope decision (Q1).

### Verification results per review finding

| # | Source | File | Verdict |
| --- | --- | --- | --- |
| T1 | CI | `CorsRulesTable.test.tsx:322,342` | ✅ real, in diff. Component renders `t\`Edit CORS Rule\`` (`CorsRulesTable.tsx:172`), test asserts `"Edit"`. |
| T2 | CI | `ObjectBrowserView.test.tsx:773-783` | ✅ real, in diff. Create Folder is a `menuitem` inside the `More Actions` kebab (`ObjectBrowserView.tsx:660-673`), not a flat button. |
| 1 | CodeRabbit | `BucketHeaderActions.tsx:70` | ✅ real, in diff. `<Button icon="moreVert" />` → `titleValue === ""`, no accessible name. |
| 2 | CodeRabbit | `CredentialPrompt.tsx:14` | ✅ real, in diff. Destructures `{ permissions, isLoading }` only; `isError` ignored → query failure renders "Insufficient permissions". |
| 3 | CodeRabbit + repo owner | `LifecycleRuleForm.tsx:45-92` | ✅ real data-loss bug — **but out of PR diff** (identical to `origin/main`). |
| 4 | CodeRabbit | `LifecycleRulesTab.tsx:159` | ✅ real, in diff. `mutationsBlocked` disables controls with zero explanation. |
| 5 | CodeRabbit + repo owner | `LifecycleRulesTab.tsx:237` | ⚠️ **STALE — already fixed.** At the reviewed commit `7edcce67` the branch had dropped `disabled={mutationsBlocked}`; the later merge `67b55149` restored it. Line 237 today reads `<Button variant="primary" onClick={handleAddRule} disabled={mutationsBlocked}>`. Needs a regression test + a reply, not a code change. |
| 6 | CodeRabbit + Copilot | `LifecycleRulesTable.test.tsx` | ✅ real, in diff. Confirmed **byte-identical** to `LifecycleRulesTab.test.tsx` (same md5); imports and renders `LifecycleRulesTab`, mocks `./LifecycleRulesTable`. Both files are new in this PR. |
| 7 | CodeRabbit | `lifecycleUtils.ts:180-326` + `LifecycleRuleForm.tsx:283` | ✅ real — **out of PR diff**. |
| 8 | CodeRabbit | `lifecycleRouter.ts:29` | ✅ real (`now > limit.resetAt`) — **out of PR diff**. |
| 9 | Copilot ×1 (not CodeRabbit) | `de/messages.po:2057,4030` | ✅ real, in diff — but 408 of 1349 de `msgstr` are already empty (~30%), and CI's `check-i18n` job runs only `lingui extract --clean && lingui compile`; it does not fail on untranslated strings. Cosmetic, needs the user's judgment. |
| C2 | Copilot | `lifecycleUtils.ts:397` | ✅ real (`new Date(typeof t.Date === "string" ? t.Date : t.Date)`) — **out of PR diff**. |
| — | SuperSandro2000 | PR comment | Not a code change — needs a reply. Bucket policies **are** supported (`bucketPolicyRouter`, `BucketPolicyModal`, gated by `storage:container_policies:{update,delete}` in this PR). |

## Potential Problems & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Fixing findings 3/7/8/C2 modifies code that is identical to `origin/main`, turning a permissions PR into a lifecycle-bugfix PR — bloats the diff, invalidates the changeset text, and risks conflicts with any in-flight lifecycle work | High | **Open Question Q1.** Recommended default: fix only the two 1-line items (8, C2) inline as trivial drive-bys, and split findings 3 + 7 into a follow-up `fix(aurora)` PR + GitHub issue. |
| Finding 3's fix changes `normalizeFilter`'s signature, which exists **twice** (`lifecycleUtils.ts:29` client, `lifecycleMapper.ts:28` server) with a docblock contract that they stay "behaviourally identical", plus two mirrored test files | High | If taken: change both copies + both test files in the same commit; add mirrored cases to `lifecycleUtils.test.ts` and `lifecycleMapper.test.ts`. Only caller is `LifecycleRuleForm.tsx:92`. |
| Deleting `LifecycleRulesTable.test.tsx` drops 266 lines of (duplicated) coverage; the table component itself would then have **zero** direct tests, unlike its twin `CorsRulesTable` | Medium | **Open Question Q2.** Recommended: rewrite it against `CorsRulesTable.test.tsx` — the components are structural twins so it's mostly mechanical. |
| Every new user-facing string added by these fixes lands in `en`+`de` catalogs, adding *more* empty German `msgstr` — the exact thing finding 9 complains about | Medium | Batch all string additions, run `pnpm check-i18n` **once** at the end (Step 12), and hand the full list of new German strings to the user together with the two existing ones. |
| Using `label={...}` instead of `title`/`aria-label` on the `BucketHeaderActions` kebab would render visible text and change the header layout | Low | Verified in Juno 9.4.0 source: use `title` (matches `ObjectBrowserView.tsx:663`, and the passing test at `ObjectBrowserView.test.tsx:354` proves `title` yields a queryable accessible name in jsdom). |
| `BucketHeaderActions.test.tsx:39` uses a bare `screen.getByRole("button")` | Low | Adding `title` doesn't add a button; assertion stays valid. |
| Adding an `isError` branch to `CredentialPrompt` must not accidentally show the create button on error | Low | Order the branches `isLoading → isError → canCreateCredential → denial`; keep fail-closed. |

## Prerequisites

- [x] **Q1 answered (2026-08-28): split.** Steps 9 (rate-limit `>=`) and 10 (redundant ternary) are done in this PR. Step 4 (`ObjectSize*` filter preservation) and Step 11 (client-side value bounds) are **deferred to a follow-up issue + separate `fix(aurora)` PR** — do not implement them here.
- [x] **Q2 answered (2026-08-28): rewrite.** `LifecycleRulesTable.test.tsx` gets replaced with real table-focused tests (Option A in Step 5), not deleted.
- [x] **Q3 answered (2026-08-28): leave empty.** The two German `msgstr` in Step 12 stay untranslated, consistent with the 408 other empty entries. Reply to Copilot's comment on the PR explaining this is a deliberate choice, not an oversight.
- [ ] Branch `kiryl-ceph-permissions` at `67b55149`, working tree clean, `origin/main` = `70367891`.
- [ ] Note for the implementer: every path below contains a literal `$projectId` directory segment — **always single-quote paths in shell commands**, e.g. `pnpm --filter @cobaltcore-dev/aurora test 'src/client/routes/_auth/projects/$projectId/...'`.

---

## Phase A — Unblock CI

### Step 1: Fix the stale `Edit` assertions in `CorsRulesTable.test.tsx`

**Files to modify:**
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/CorsRulesTable.test.tsx`

**What to do:**
1. Line 322 — change `expect(screen.getByText("Edit")).toBeInTheDocument()` to assert the real menu-item label: `expect(screen.getByRole("menuitem", { name: "Edit CORS Rule" })).toBeInTheDocument()`.
2. Line 342 — change the mirrored negative check `expect(screen.queryByText("Edit")).not.toBeInTheDocument()` to `expect(screen.queryByRole("menuitem", { name: "Edit CORS Rule" })).not.toBeInTheDocument()`.
3. Leave the two `Delete CORS Rule` assertions on lines 323/343 alone (they already match `CorsRulesTable.tsx:179`) — or convert them to `getByRole("menuitem", …)` for symmetry, but do not change their expected text.
4. Do **not** touch `CorsRulesTable.tsx` — the `t\`Edit CORS Rule\`` label is intentional (it matches `Delete CORS Rule` and the same convention in `LifecycleRulesTable.tsx:214`).

**Expected outcome:** `CorsRulesTable > Permission gating - row actions` passes.

**Verification:**
```
pnpm --filter @cobaltcore-dev/aurora test 'src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/CorsRulesTable.test.tsx'
```
All 12 tests in the file green.

---

### Step 2: Fix the Create-Folder toolbar assertions in `ObjectBrowserView.test.tsx`

**Files to modify:**
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/ObjectBrowserView.test.tsx`

**Context:** `ObjectBrowserView.tsx:660-673` wraps the whole `PopupMenu` (toggle + `Create Folder` menu item) in `{permissions.canCreateFolder && …}`. The toggle is `<Button icon="moreVert" title={t\`More Actions\`} />`; the item is `<PopupMenuItem label={t\`Create Folder\`} data-testid="create-folder-action" />`. The module-level `render` helper (lines 12-20) already wraps in `PortalProvider`, so popup contents are queryable. The correct pattern already exists at lines 350-357 and 374-382.

**What to do:**
1. Test at line 773, `"hides the Create Folder button when canCreateFolder is false"` — rename to `"hides the More Actions menu when canCreateFolder is false"` and replace the vacuous body assertion with:
   - `expect(screen.queryByRole("button", { name: /more actions/i })).not.toBeInTheDocument()`
   - `expect(screen.queryByTestId("create-folder-action")).not.toBeInTheDocument()`
   (Safe: the only other kebab in the component, `ObjectBrowserView.tsx:735`, has accessible name `"Actions"`, which `/more actions/i` does not match.)
2. Test at line 779, `"shows both toolbar buttons when permitted"` — rename to `"shows the Upload button and the Create Folder menu item when permitted"`, make it `async`, and rewrite the body mirroring lines 374-382:
   ```tsx
   const user = userEvent.setup()
   render(<ObjectBrowserView bucketName="test-bucket" />)
   expect(screen.getByRole("button", { name: /upload object/i })).toBeInTheDocument()
   await user.click(screen.getByRole("button", { name: /more actions/i }))
   expect(screen.getByRole("menuitem", { name: /create folder/i })).toBeInTheDocument()
   ```
3. Leave the `canCreateObject` test at line 767 unchanged — Upload really is a flat `Button` (`ObjectBrowserView.tsx:674-678`).

**Expected outcome:** `ObjectBrowserView - Permission gating` passes; the "hides" test now actually fails if the gate is removed.

**Verification:**
```
pnpm --filter @cobaltcore-dev/aurora test 'src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/ObjectBrowserView.test.tsx'
```
Then sanity-check the tightened test is not vacuous: temporarily change `ObjectBrowserView.tsx:660` to `{true && (` and confirm the "hides" test fails; revert.

---

### Step 2b: Confirm the whole suite is green

```
pnpm --filter @cobaltcore-dev/aurora test
```
Expected: 5466 passed, 0 failed. **Commit here** (`fix(aurora): update Ceph permission-gating test assertions`) so CI turns green independently of the rest.

---

## Phase B — Major / data-loss findings

### Step 3: Close CodeRabbit finding #5 with a regression test (no production change)

**Files to modify:**
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRulesTab.test.tsx`

**What to do:**
1. First **verify** `LifecycleRulesTab.tsx:237` still reads `<Button variant="primary" onClick={handleAddRule} disabled={mutationsBlocked}>`. If yes, no production change is required.
2. In the existing `describe("mutationsBlocked (skipped rules)")` block (ends at file line ~265), add a test:
   - name: `"disables the Create Lifecycle Rule button when a rule was skipped on read"`
   - mock `trpcReact.storage.ceph.lifecycle.get.useQuery` to return `{ data: { rules: [mockRule], skippedRuleCount: 1 }, isLoading: false, error: null }` (same shape as the existing test at line ~245)
   - assert `expect(screen.getByRole("button", { name: /Create Lifecycle Rule/i })).toBeDisabled()`
3. Add the complementary positive case: with `skippedRuleCount: 0`, the button is `not.toBeDisabled()`.

**Expected outcome:** the data-loss path CodeRabbit and the repo owner both flagged is locked down by a test, so a future refactor can't silently drop it again (which is exactly what happened between `7edcce67` and the merge).

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test 'src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRulesTab.test.tsx'`

---

### Step 4: DEFERRED (Q1 = split) — Preserve `ObjectSize*` predicates when editing a lifecycle rule

🔴 **Not part of this PR.** Q1 was answered "split" on 2026-08-28: this file is identical to `origin/main`, and this fix (real data-loss bug, but touches a duplicated client/server `normalizeFilter` helper plus 3 test files) is scoped to a **follow-up GitHub issue + separate `fix(aurora)` PR**, filed as part of Step 13. Kept below for that follow-up's reference only — skip when implementing this plan.

**Files to modify:**
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/utils/lifecycleUtils.ts`
- `packages/aurora/src/server/Storage/helpers/lifecycleMapper.ts`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRuleForm.tsx`
- the two mirrored test files `utils/lifecycleUtils.test.ts` and `server/Storage/helpers/lifecycleMapper.test.ts`

**The bug:** `getInitialValues()` (lines 45-68) reads only `Filter.Prefix` / `Filter.Tag` / `Filter.And.Prefix` / `Filter.And.Tags`. `onSubmit` (line 92) rebuilds the filter as `normalizeFilter(trimmedPrefix, tags)`. Since `lifecycle.set` is a full replace, editing an externally-authored rule scoped by `ObjectSizeGreaterThan` / `ObjectSizeLessThan` silently widens it to every object.

**What to do:**
1. Extend both copies of `normalizeFilter` to `normalizeFilter(prefix?: string, tags?: LifecycleTag[], objectSizeGreaterThan?: number, objectSizeLessThan?: number)`. Keep the two implementations byte-identical (the docblock at `lifecycleUtils.ts:15-17` mandates it). Reimplement the body as a predicate count so it matches the server Zod refinements in `server/Storage/types/ceph.ts:899-932`:
   - `count = (hasPrefix ? 1 : 0) + (tags?.length ?? 0) + (hasGt ? 1 : 0) + (hasLt ? 1 : 0)` where `hasPrefix = prefix !== undefined && prefix !== ""`
   - `count === 0` → `{ Prefix: "" }` (preserve existing whole-bucket behavior)
   - `count === 1` → the single top-level form: `{ Prefix }` / `{ Tag: tags[0] }` / `{ ObjectSizeGreaterThan }` / `{ ObjectSizeLessThan }`
   - `count >= 2` → `{ And: { Prefix?, Tags?, ObjectSizeGreaterThan?, ObjectSizeLessThan? } }`
   All existing call sites pass only 2 args, so existing assertions keep passing.
2. In `getInitialValues`, capture the size predicates from **both** locations — top-level `filter.ObjectSizeGreaterThan/LessThan` and `filter.And.ObjectSizeGreaterThan/LessThan` — into non-form-field values (they are not user-editable; keep them out of `defaultValues` and read them from `editingRule` at submit time, mirroring how `Transitions` is handled at lines 114-117).
3. In `onSubmit` (line 92), pass them through: `normalizeFilter(trimmedPrefix || undefined, value.tags.length > 0 ? value.tags : undefined, sizeGt, sizeLt)`.
4. Add a read-only notice, following the exact existing pattern at `LifecycleRuleForm.tsx:378-400`: a `<Message variant="info" title={t\`Object Size Filter (read-only)\`}>` shown when either predicate is present, explaining the rule is scoped by object size and that the scope is preserved unchanged. Also add the condition to the `hasReadOnlyFields`-style expression at line ~178.
5. Add mirrored test cases to **both** test files: single size predicate → top-level; prefix + size → `And`; tag + two sizes → `And` with all three; and a `LifecycleRuleForm.test.tsx` case asserting that editing a size-scoped rule round-trips the predicate into the submitted rule.

**Expected outcome:** editing a size-scoped rule preserves `ObjectSizeGreaterThan`/`ObjectSizeLessThan` byte-identically, and the user sees that the scope exists.

**Verification:**
```
pnpm --filter @cobaltcore-dev/aurora test 'src/server/Storage/helpers/lifecycleMapper.test.ts' 'src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/utils/lifecycleUtils.test.ts' 'src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRuleForm.test.tsx'
```

---

## Phase C — Duplicate test file

### Step 5: (Q2 = rewrite) Replace `LifecycleRulesTable.test.tsx`

**Files to modify:**
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRulesTable.test.tsx`

**Confirmed:** md5-identical to `LifecycleRulesTab.test.tsx`; imports `LifecycleRulesTab` on line 4 and `vi.mock("./LifecycleRulesTable", …)` on line 84. Both files are new in this PR, so this is squarely in scope.

**Option A (recommended) — rewrite as real table tests.** Model: `CorsRulesTable.test.tsx` (its component `CorsRulesTable.tsx` is a structural twin of `LifecycleRulesTable.tsx`).

1. Replace the whole file. Imports: `LifecycleRulesTable` from `./LifecycleRulesTable`; `LifecycleRuleRead` from `@/server/Storage/types/ceph`; `PortalProvider` from Juno.
2. Copy the mock scaffolding from `CorsRulesTable.test.tsx:14-44`, retargeting `storage.ceph.cors.*` → `storage.ceph.lifecycle.*` (`get.useQuery`, `set.useMutation`, `delete.useMutation`, `useUtils`) — these are what the nested `DeleteLifecycleRuleModal` reaches for. Keep `vi.mock("@/client/hooks/useProjectId", …)` and both `Wrapper` / `PortalWrapper` helpers.
3. Cover, mirroring the Cors suite:
   - **Columns:** with `canDeleteLifecycle: true` the `Select` head cell (`sr-only`, line 119-121) renders; with `false` it doesn't. Assert the 7 visible head cells: `Rule ID`, `Status`, `Scope`, `Expiration`, `Noncurrent Versions`, `Other Actions`.
   - **Empty state:** `isFiltered: false` → `"There are no lifecycle rules for this bucket"`; `isFiltered: true` → `"No lifecycle rules matching the current search criteria."`
   - **Cell formatting:** a rule with `Filter: { Prefix: "logs/" }`, `Expiration: { Days: 30 }`, `AbortIncompleteMultipartUpload: { DaysAfterInitiation: 7 }` renders `Prefix: logs/`, `After 30 days`, and the abort text; a rule with no ID renders the `—` placeholder (line 197).
   - **Permission-gated row actions** (`PortalWrapper`, open the menu via `row.querySelector("button[aria-haspopup='menu']")` exactly as `CorsRulesTable.test.tsx:299-304` does): `canUpdate=true/canDelete=false` → `Edit Lifecycle Rule` present, `Delete Lifecycle Rule` absent; the inverse; both false → **no** row menu button rendered at all (`hasAnyRowAction`, line 183/208).
   - **`isMutating`:** with `isMutating: true`, both menu items are disabled (lines 216/223).
   - **Selection:** `selectedIndices` drives the row checkbox `checked` state; clicking `select-rule-<i>` calls `onToggleSelectRule` with the `originalIndex` (**not** the array position — pass `rulesWithIndices` with non-sequential `originalIndex` values, e.g. `[{rule, originalIndex: 3}]`, to prove the contract).
4. Do **not** duplicate anything already covered by `LifecycleRulesTab.test.tsx` (sort/search/toolbar/modal wiring).

**Option B — delete.** `git rm` the file, and instead add the table's permission-gating assertions to `LifecycleRulesTab.test.tsx` by expanding its `vi.mock("./LifecycleRulesTable")` stub (lines 84-104) to expose `data-can-update-lifecycle` / `data-can-delete-lifecycle` attributes, mirroring how `ObjectBrowserView.test.tsx` stubs `ObjectsTableView` (lines 32-40). Cheaper, but leaves the table component itself untested.

**Expected outcome:** exactly one suite per component; no suite runs twice.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test 'src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/'` — no duplicate test names across the two files.

---

## Phase D — Minor findings inside the PR diff

### Step 6: Give the bucket-actions kebab an accessible name

**Files to modify:**
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketHeaderActions.tsx`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketHeaderActions.test.tsx`

**What to do:**
1. Line 70: `<Button icon="moreVert" />` → `<Button icon="moreVert" title={t\`Bucket actions\`} />`. `t` is already in scope (line 45). Use `title`, **not** `label` — verified against Juno 9.4.0's `Button.component.tsx`: `label` renders visible text and would change the header layout, while `title` sets `titleValue` on both the `<button>` and inner `<Icon>` and is exactly the pattern `ObjectBrowserView.tsx:663` uses for its icon-only kebab. (`aria-label` is CodeRabbit's literal suggestion and also works via the `{...props}` spread — either satisfies the finding; `title` is more consistent with the sibling component and adds a tooltip.)
2. In `BucketHeaderActions.test.tsx`, add an assertion `expect(screen.getByRole("button", { name: "Bucket actions" })).toBeInTheDocument()` and optionally retarget the bare `screen.getByRole("button")` at line 39 to the named query.

**Expected outcome:** screen readers announce the menu's purpose; the button becomes queryable by role+name in tests.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test 'src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketHeaderActions.test.tsx'`

---

### Step 7: Distinguish permission-query failure from "no permission" in `CredentialPrompt`

**Files to modify:**
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/CredentialPrompt.tsx`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/CredentialPrompt.test.tsx`

**What to do:**
1. Line 14: destructure `isError` — `const { permissions, isLoading: isLoadingPermissions, isError: isPermissionsError } = useCephPermissions(projectId)`.
2. Rework the ternary chain at lines 44-62 into `isLoadingPermissions → isPermissionsError → permissions.canCreateCredential → denial`. Keep the fail-closed shape: the error branch must **not** render the create button.
3. The error branch: `<Message variant="error" title={t\`Could not check permissions\`}>` with a `<Trans>` body along the lines of *"We couldn't verify whether you can create S3 credentials. Please reload the page or try again later."* Do not surface the raw tRPC error string here — `useCephPermissions` doesn't expose it, and the existing denial `Message` sets the tone for this component.
4. In the test file, promote the hardcoded `isError: false` in the `vi.mock("../hooks/useCephPermissions", …)` factory (lines 40-46) to a mutable `let mockIsErrorPermissions = false`, reset it in `beforeEach` (alongside `mockCanCreateCredential`/`mockIsLoadingPermissions` at lines 114-115).
5. Add to the `describe("Permission gating")` block (line 261): with `isError: true` and `canCreateCredential: false`, the error message renders, the create button does **not**, and the `"You don't have permission to create S3 credentials"` denial text does **not** — proving the two states are now distinguishable.

**Expected outcome:** a failed `storage.canUser` query is reported as an error, not silently as a denial.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test 'src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/CredentialPrompt.test.tsx'`

---

### Step 8: Explain *why* lifecycle mutations are blocked

**Files to modify:**
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRulesTab.tsx`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRulesTab.test.tsx`

**What to do:**
1. In the returned fragment (starts line 220), immediately before the Zone-1 `<Stack>` at line 223, render:
   ```tsx
   {mutationsBlocked && (
     <Message variant="warning" title={t`Lifecycle rules cannot be modified`} className="mb-2">
       …
     </Message>
   )}
   ```
   `Message` is already imported (line 9) and `mutationsBlocked` is already computed (line 159).
2. Body copy must state (a) that `skippedRuleCount` rule(s) on this bucket could not be read, (b) that saving any change replaces the whole configuration and would delete them, and (c) that they must be fixed with an external S3 tool first. Use `plural()` from `@lingui/core/macro` for the count — it's already imported (line 3) and used at line 283.
3. Add a test in the existing `describe("mutationsBlocked (skipped rules)")` block asserting the message renders when `skippedRuleCount: 1` and is absent when `skippedRuleCount` is `0`/undefined.

**Expected outcome:** the user sees why every mutation control is disabled instead of an unexplained dead UI.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test 'src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRulesTab.test.tsx'`

---

## Phase E — Findings on code identical to `origin/main` (Q1 = split: Steps 9–10 in scope, Step 11 deferred)

### Step 9: Rate-limit window boundary (1 character)

- File: `packages/aurora/src/server/Storage/routers/ceph/lifecycleRouter.ts`
- Line 29: `if (!limit || now > limit.resetAt) {` → `if (!limit || now >= limit.resetAt) {`
- Confirmed still valid at HEAD. Note the self-clean `setTimeout` at lines 32-39 already uses `<=`, so `>=` makes the two consistent.
- Add a case to `lifecycleRouter.test.ts` that fakes `Date.now()` exactly at `resetAt` and asserts no `TOO_MANY_REQUESTS`.

### Step 10: Redundant ternary in `formatTransitions`

- File: `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/utils/lifecycleUtils.ts`
- Line 397: `new Date(typeof t.Date === "string" ? t.Date : t.Date).toLocaleDateString()` → `new Date(t.Date).toLocaleDateString()`.
- The parameter is locally typed as `{ StorageClass: string; Days?: number; Date?: string }` at the call site (`LifecycleRulesTable.tsx:172`), but check the declared `LifecycleTransition` type in this module — if `Date` is `string | Date`, confirm `pnpm --filter @cobaltcore-dev/aurora typecheck` still passes (the `DateConstructor` overload accepting `Date` exists in modern lib.d.ts, but verify rather than assume). If it doesn't typecheck, use `new Date(t.Date as string | number | Date)`.
- Do **not** touch the sibling at line 377 (`formatExpiration`) — that ternary is not redundant.

### Step 11: DEFERRED (Q1 = split) — Client-side value bounds mirroring the server schema

🔴 **Not part of this PR** — deferred to the same follow-up as Step 4. Kept for reference only.

- Files: `utils/lifecycleUtils.ts` (`validateLifecycleRules`, lines 180-326) and `LifecycleRuleForm.tsx` (`addTag`, lines ~283-298).
- Server bounds to mirror, verified in `packages/aurora/src/server/Storage/types/ceph.ts`: `lifecycleTagSchema` (line 870) — `Key: z.string().min(1).max(128)`, `Value: z.string().max(256)`; `Expiration.Days` — `min(1).max(3650)`.
- In `validateLifecycleRules`, add per-rule checks inside the existing `for` loop (after the ID-length check at line 202), covering tags in **both** `Filter.Tag` and `Filter.And.Tags`, and `Expiration.Days`. Push messages in the file's existing style: `` errors.push(`${ruleLabel}: …`) `` — note these strings are deliberately **not** i18n-wrapped in this function, so keep them plain English.
- In `addTag`, after the trim on lines ~285-286, reject `key.length > 128` / `value.length > 256` via `setTagError(t\`…\`)` before the duplicate-key check.
- Extend `utils/lifecycleUtils.test.ts` with boundary cases (128/129 key chars, 256/257 value chars, Days 0/1/3650/3651).

---

## Phase F — i18n

### Step 12: Regenerate catalogs and resolve German translations

**Files to modify:**
- `packages/aurora/src/locales/en/messages.po` + `messages.ts`
- `packages/aurora/src/locales/de/messages.po` + `messages.ts`

**What to do:**
1. Run `pnpm check-i18n` **once**, after all string-adding steps are done (`lingui extract --clean && lingui compile --typescript`). Commit the resulting `.po` and `.ts` changes.
2. Every string added by Steps 6/7/8 will appear as a new `msgid` with an empty German `msgstr` — that's expected, leave them empty (see point 3).
3. **Q3 answered (2026-08-28): leave empty.** The two pre-existing untranslated msgids Copilot flagged —
   - `de/messages.po:2057` — `msgid "Insufficient permissions"`
   - `de/messages.po:4030` — `msgid "You don't have permission to create S3 credentials. Please contact your administrator to request access to S3 Object Storage."`
   — stay untranslated, consistent with the 408 other empty entries in this catalog. Do not fill these in. In Step 13, reply to Copilot's comment stating this is a deliberate, consistent choice, not an oversight.
4. Context for the decision: 408 of 1349 German entries are already empty, CI's `check-i18n` job (`.github/workflows/ci-checks.yaml:59-71`) only extracts and compiles — it does **not** assert translation completeness. This is not merge-blocking.

**Verification:** `pnpm check-i18n` exits 0 and `git status` shows no unstaged catalog drift afterwards.

---

## Phase G — GitHub hygiene & final gate

### Step 13: Reply to and resolve the review threads

Not code work, but required for "all outstanding review feedback addressed":

1. **SuperSandro2000** ("Does this also support bucket policies?") — reply: yes. Bucket policies are implemented server-side in `packages/aurora/src/server/Storage/routers/ceph/bucketPolicyRouter.ts` with UI in `BucketPolicyModal.tsx` / `DeleteBucketPolicyModal.tsx`, and this PR adds the `storage:container_policies:update` / `:delete` gates (`useCephPermissions.ts:60-61`, `apps/dashboard/src/policies/storage.json`).
2. **CodeRabbit finding #5** (`LifecycleRulesTab.tsx:240`) — reply that it was valid against `7edcce67` but is already fixed at HEAD by the `main` merge; link the regression test from Step 3; resolve.
3. **CodeRabbit finding #3** (`LifecycleRuleForm.tsx`, `ObjectSize*` filter data loss) and **finding #7** (`lifecycleUtils.ts` value bounds) — file a GitHub issue describing both (they share root cause: client validation drift from server), reply on each thread linking the issue and noting the file is byte-identical to `origin/main` / out of this PR's diff, resolve. Open the follow-up `fix(aurora)` PR separately (not part of this plan).
4. **CodeRabbit finding #8** (`lifecycleRouter.ts` rate-limit boundary) and **Copilot C2** (redundant ternary) — these are fixed inline in this PR (Steps 9–10, per Q1); reply linking the commit, resolve.
5. **Copilot** (`de/messages.po` missing German translations) — reply that this is a deliberate choice (Q3), consistent with the 408 other empty entries in the catalog, not an oversight; resolve.
6. Resolve the remaining threads as their steps land.

### Step 14: Full validation gate

```
pnpm --filter @cobaltcore-dev/aurora typecheck
pnpm --filter @cobaltcore-dev/aurora test
pnpm lint
pnpm format:check
pnpm check-i18n
pnpm build
```
All must pass — this is the exact set `.github/workflows/ci-checks.yaml` runs (plus `licenses:check`, unaffected here).

**Changeset:** `.changeset/better-cars-brake.md` is `minor` and describes only the permission gating. If Q1 = "fix in this PR", add a **second** changeset (`patch`, `@cobaltcore-dev/aurora`) describing the lifecycle fixes separately — don't fold unrelated lifecycle bug fixes into the permissions changeset text.

**Commits:** Conventional Commits are enforced on PR titles and commits (`commitlint.config.mjs`). Suggested split — `fix(aurora): update Ceph permission-gating test assertions` (Steps 1-3), `test(aurora): replace duplicated LifecycleRulesTable suite` (Step 5), `fix(aurora): address Ceph permissions review feedback` (Steps 6-8), and if applicable `fix(aurora): preserve lifecycle object-size filters on edit` (Steps 4, 9-11).

---

## Testing Plan

**Unit tests (new/changed):**
- [ ] `CorsRulesTable` row menu shows `Edit CORS Rule` when `canUpdateCors` and hides it otherwise
- [ ] `ObjectBrowserView` hides the entire `More Actions` menu when `canCreateFolder` is false (non-vacuous — verified by temporarily removing the gate)
- [ ] `ObjectBrowserView` shows the `Upload Object` button and the `Create Folder` **menuitem** when both permissions are granted
- [ ] `LifecycleRulesTab` disables `Create Lifecycle Rule` when `skippedRuleCount > 0`, enables it at `0`
- [ ] `LifecycleRulesTab` renders the blocked-mutations `Message` only when `skippedRuleCount > 0`
- [ ] `BucketHeaderActions` kebab is reachable via `getByRole("button", { name: "Bucket actions" })`
- [ ] `CredentialPrompt` renders a distinct error state when `useCephPermissions` reports `isError`, and neither the create button nor the denial text
- [ ] `LifecycleRulesTable`: columns, empty/filtered-empty states, cell formatting, permission-gated row actions, `isMutating` disabling, selection by `originalIndex`
- [ ] `lifecycleRouter` rate limit resets at exactly `resetAt`
- [ ] ~~`normalizeFilter` size-predicate cases~~ — deferred to follow-up PR (Q1)
- [ ] ~~`validateLifecycleRules` boundary cases; `addTag` length rejection~~ — deferred to follow-up PR (Q1)

**Integration:**
- [ ] Full `pnpm --filter @cobaltcore-dev/aurora test` — 5466+ passing, 0 failing
- [ ] No duplicate test names between `LifecycleRulesTab.test.tsx` and `LifecycleRulesTable.test.tsx`

**Manual verification** (`pnpm dev`, project with Ceph/S3 configured):
1. As a user missing `storage:folders:create`: open a bucket's Objects tab — the kebab next to `Upload Object` must be gone entirely, not an empty popup.
2. Open a bucket detail page as a read-only user — the header kebab is absent (`hasAnyAction` false); as an admin, hover it and confirm the `Bucket actions` tooltip.
3. Temporarily point the client at a failing `storage.canUser` (e.g. throttle/500 it in devtools) on a project with no EC2 credential — `CredentialPrompt` must show the error state, not "Insufficient permissions".
4. On a bucket whose lifecycle config contains a rule the server can't parse (`skippedRuleCount > 0`): the warning `Message` appears, `Create Lifecycle Rule` is disabled, bulk `Actions` is disabled, row Edit/Delete are disabled.
5. ~~Create a size-scoped rule with an external S3 client... — the size predicate must survive~~ — deferred to follow-up PR (Q1), not in scope here.

## Acceptance Criteria

- [ ] `pnpm --filter @cobaltcore-dev/aurora test` passes with 0 failures; PR #1207's `test` check goes green
- [ ] No test assertion in the touched files passes vacuously (each verified to fail when its gate is removed)
- [ ] `LifecycleRulesTable.test.tsx` either tests `LifecycleRulesTable` or no longer exists
- [ ] The `BucketHeaderActions` kebab has a non-empty accessible name; header layout unchanged
- [ ] `CredentialPrompt` renders three distinguishable states: loading / query-error / permission-denied
- [ ] `LifecycleRulesTab` explains the blocked-mutations state in the UI
- [ ] Every CodeRabbit and Copilot thread on the PR is either fixed or answered with a documented reason, and resolved
- [ ] SuperSandro2000's question has a reply
- [ ] Changeset(s) accurately describe the shipped change set
- [ ] No regressions: `pnpm typecheck`, `pnpm lint`, `pnpm format:check`, `pnpm check-i18n`, `pnpm build`, `pnpm test` all pass

## Open Questions

**Q1 — Scope of the out-of-diff lifecycle findings. ANSWERED 2026-08-28: split.** `LifecycleRuleForm.tsx`, `utils/lifecycleUtils.ts`, and `server/.../lifecycleRouter.ts` are **byte-identical to `origin/main`** — CodeRabbit only saw them because they arrived through the `main` merge (PR #1178). Decision: take the two 1-line drive-bys inline (Step 9 `>=`, Step 10 redundant ternary — zero risk, obviously correct); file a follow-up issue + separate `fix(aurora)` PR for Step 4 (size-predicate data loss) and Step 11 (value bounds). Keeps #1207 a permissions PR.

**Q2 — `LifecycleRulesTable.test.tsx`. ANSWERED 2026-08-28: rewrite.** Rewrite as real table tests mirroring `CorsRulesTable.test.tsx` (the components are twins, so it's mostly mechanical, and it leaves the table with parity coverage) — not deleted.

**Q3 — German translations. ANSWERED 2026-08-28: leave empty.** The two `msgstr` values stay empty, consistent with the 408 existing empty entries (not CI-blocking); reply to Copilot's comment explaining this is deliberate.

**Q4 — Non-blocking, FYI.** The knowledge base at `../DOCS/aurora-dashboard-kb/` is pinned to `90be7d9a` (24.08.2026); `origin/main` is now at `70367891` and has since merged the entire Ceph lifecycle feature (#1178) — the `Storage — Ceph S3` row in `05-domain-map.md` doesn't mention `lifecycleRouter` at all. Worth an `update-kb` pass after this PR lands.
