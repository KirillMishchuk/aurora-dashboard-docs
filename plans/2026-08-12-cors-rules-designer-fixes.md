# Plan: CORS Rules UI — post-merge designer fixes

**Date:** 2026-08-12 · **Status:** not implemented

## 📋 IMPLEMENTATION PLAN: CORS Rules UI — post-merge designer fixes

### Overview

Six small, independent UI corrections to the Ceph/S3 CORS management feature (merged as PR #1092 / `b7576dbd`), driven by designer feedback: consistent create-action naming, correct button variants inside the modal, removal of the leftover bucket-level "Delete CORS Rules" action, default DataGrid layout, and two spacing fixes. No server, router, or schema changes — this is client-only work inside one folder plus one shared hook.

All files below are under:
`/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/`

---

### Architecture Analysis

**Current state (verified against working tree, branch `kirylDev`, clean):**

| File | Role | Verified line refs |
| --- | --- | --- |
| `Buckets/CorsRulesTab.tsx` | Tab container. Outer `<Stack direction="vertical" gap="4">` (L221) wraps Zone 1 (sort + create, L223–239), Zone 2 (`DataGridToolbar`, L242–288), `CorsRulesTable` (L291), and two modals | trigger button L236–238 |
| `Buckets/CorsRuleModal.tsx` | Add/Edit modal wrapper around `CorsRuleForm` | title L150, footer buttons L160–189 |
| `Buckets/CorsRuleForm.tsx` | TanStack Form; renders `TagInput` 3× (L80, L124, L139) | — |
| `Buckets/TagInput.tsx` | Text input + "Add" button + `Pill` list | Button L86–96, literal `Add` L95 |
| `Buckets/CorsRulesTable.tsx` | `DataGrid` of rules + per-row kebab (Edit/Delete) | `gridColumnTemplate` const L95–96, `<DataGrid>` L103 |
| `Buckets/BucketHeaderActions.tsx` | Bucket-header overflow menu | `hasCors` prop L10/L26, menu item L49 |
| `Buckets/BucketModals.tsx` | Unified modal switchboard | `DeleteCorsModal` import L9, `"deleteCors"` in `ModalType` L35, toast imports L20–21, render L133–147 |
| `Buckets/DeleteCorsModal.tsx` | Whole-config delete confirmation (148 lines) | to be deleted |
| `Buckets/BucketHeader.tsx` | Header + tabs + divider + modals | `corsData` destructure L32, `hasCors=` L66, tabs/divider block L77–80 |
| `hooks/useBucketInfo.ts` | Consolidated bucket queries | `corsData` in `BucketInfo` L21–25, `cors.get` query L94–105, return L144, `isLoadingCors` in `isLoading` L149 |
| `Buckets/BucketToastNotifications.tsx` | Toast factories | `getCorsDeletedToast` L204, `getCorsDeleteErrorToast` L209 |

**Findings that correct/extend the brief — read these before starting:**

1. 🟢 **Item 6 has a first-class API, no className hack needed.** Juno `Divider` (v9.1.0) exposes `spacing?: DividerSpacing` with `"0"` in the union and default `"1"` → `jn:py-1` (4px top + 4px bottom on the wrapper `<div>`; the `<hr>` itself is `jn:h-px`). `TabNavigation` renders `<ul class="juno-navigation jn:flex">` with **no** bottom margin/border, and `TabNavigationItem` is `jn:py-[0.875rem] … jn:border-b-[3px]`. So the entire visible gap is the Divider's own `py-1`. Fix = `<Divider spacing="0" />`. The designer's `className` suggestion would work too but fights the component; use the prop.
2. 🟢 **`CorsRulesTable.test.tsx` does NOT assert on layout.** It never references `gridColumnTemplate`, `cors-rules-table`, or column widths. Item 4 needs **zero** test changes.
3. 🟢 **There are no `BucketHeaderActions.test.tsx` / `BucketModals.test.tsx` / `DeleteCorsModal.test.tsx` files.** Item 3 needs zero test changes; nothing in `BucketToastNotifications.test.tsx` covers the two orphaned CORS toasts either (verified by grep).
4. 🟢 **`cors-rules-table` is genuinely dead** — the only occurrence repo-wide is the JSX itself; `client/theme.css` and `client/index.css` contain no `.cors-rules-table` rule.
5. 🟢 **`variant="default"` is valid and is already the codebase convention.** `ButtonVariant = "primary" | "primary-danger" | "default" | "subdued"`, and `variant` already **defaults** to `"default"` — so passing it explicitly is a readability choice consistent with `DeleteRuleDialog.tsx`, `AddRuleModal.tsx`, `CreateSecurityGroupModal.tsx`, `DeleteImageModal.tsx`, `EditObjectMetadataModal.tsx:603`, etc.
6. 🟢 **No latent submit bug in `TagInput`.** Juno `Button` defaults `type="button"`, so the Add button inside `<Form id="cors-rule-form">` never submits the CORS form. Don't "fix" this.
7. ⚠️ **Removing item 3 orphans a chain of code**, all confirmed by grep to have no other consumer: `BucketHeaderActions.hasCors` prop → `BucketHeader`'s `corsData` destructure → `useBucketInfo`'s `corsData` field/query → `getCorsDeletedToast` / `getCorsDeleteErrorToast`. `storage.ceph.cors.delete` on the **server stays** — `DeleteCorsRuleModal.tsx:69` and `DeleteCorsRulesModal.tsx:76` both still call it (they use `cors.delete` when the last rule is removed, `cors.set` otherwise).
8. 🟢 **Reference pattern for item 5** is `network/securitygroups/-components/SecurityGroupsList.tsx:231–299`: a fragment with Zone 1 as `<Stack … className="pb-2">` immediately followed by `<DataGridToolbar>` then the table — i.e. no `gap` between zones. `gap="0"` on the CORS tab's outer Stack lands in the same place. `StackGap` includes `"0"`.
9. 🟢 **`columns={8}` alone** yields `gridTemplateColumns: repeat(8, minmax(0px, auto))` (from `columnMinSize="0px"` / `columnMaxSize="auto"` defaults). Juno also offers `minContentColumns?: number[]` — used by `ImageListView.tsx:714` (`[0, 6]`) and `FlavorListContainer.tsx:142` (`[6]`) — which is the established escape hatch if the checkbox/kebab columns look too wide (see Mitigations).
10. 🟢 **Locale files are git-tracked** (`src/locales/{en,de}/messages.{po,ts}`) and tests import the compiled `messages.ts`. String changes must be followed by `check-i18n` + committing the regenerated catalogs.

**Proposed changes:** purely presentational edits in the files above plus deletion of one component and its orphaned support code. Nothing crosses the tRPC boundary, so no `packages/aurora/README.md` (public `AuroraApp` contract) impact.

---

### Potential Problems & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| ⚠️ After the rename, **modal title and submit button share the exact string** "Create CORS Rule". `screen.getByText(/Create CORS Rule/i)` in `CorsRuleModal.test.tsx:121` will match **two** nodes and throw `TestingLibraryElementError: Found multiple elements`. | High (guaranteed test break) | Query the title by role. Juno `Modal` renders a string `title` as `<h4 class="juno-modal-title" id=…>`, so use `screen.getByRole("heading", { level: 4, name: /Create CORS Rule/i })`; keep the button query as `getByRole("button", { name: /Create CORS Rule/i })`. |
| ⚠️ `CorsRulesTab.test.tsx:225` and `:284` use `getByRole("button", { name: /Create rule/i })` — that regex does **not** match "Create CORS Rule". | High (guaranteed test break) | Update both to `/Create CORS Rule/i`. |
| ⚠️ `CorsRuleModal.test.tsx:217`, `:271`, `:311` use `{ name: /Create Rule/i }` — same problem. | High | Update all three to `/Create CORS Rule/i`. |
| ⚡ Removing `gridColumnTemplate` drops the `40px` checkbox and `60px` action columns; with `repeat(8, minmax(0px, auto))` they become content-sized-but-flex-shared, and a very long `AllowedOrigins` value (cell has `break-all`, L148) contributes a large max-content width. Table may look lopsided or overflow horizontally. | Medium (visual only) | Verify manually with a rule containing a ~120-char origin and 5 methods. If the checkbox/kebab columns are visibly over-wide, add `minContentColumns={[0, 7]}` — the same escape hatch `ImageListView`/`FlavorListContainer` use — rather than reinstating a hardcoded template. Flag to the designer if it still looks wrong. |
| 🔴 Deleting `DeleteCorsModal.tsx` removes the only "wipe entire CORS config in one action" affordance. Users must now delete rules individually or via the batch flow. | Medium (deliberate product change) | This is the explicitly confirmed intent; batch delete via the Zone-2 bulk menu + `DeleteCorsRulesModal` covers the use case (and already calls `cors.delete` when all rules are selected). Do **not** touch `CorsRulesTable.tsx:159–172` (per-row Delete) or `CorsRulesTab.tsx:268–281` (bulk menu). |
| Analytics regression: `DeleteCorsModal` was the only emitter of the `storage.ceph.bucket.cors.delete.*` `useModalTracking` events. | Low | Expected consequence of removing the flow; note it in the PR description so dashboards owners aren't surprised. |
| Removing the `cors.get` query from `useBucketInfo` means the CORS tab no longer benefits from the Overview page's prefetch (both use a 5-min `staleTime` and the same query key — see the comment at `CorsRulesTab.tsx:68`), so switching to the tab shows a brief spinner. Keeping it means one unused `GetBucketCors` request on every bucket Overview load. | Low | See Open Questions Q1. Default recommendation: **keep the query, drop only the unused `corsData` from the public return + interface** — preserves the prefetch, removes the dead surface. |
| `pnpm check-i18n` runs `lingui extract --clean`, which deletes catalog entries for removed strings and adds new ones. Skipping it leaves `messages.po`/`messages.ts` stale relative to source. | Low | Step 8 regenerates and commits them. CI's `check-i18n` job only *runs* the command (no `git diff` gate), so this won't fail CI — it's a hygiene requirement, not a blocker. |
| German catalog `de/messages.po` will gain untranslated new strings and lose removed ones. | Low | Expected; `lingui extract` handles it. Don't hand-translate. |

---

### Prerequisites

- [ ] Branch off current `kirylDev` (or `main`) — working tree is clean at `fc5995f3`.
- [ ] `pnpm install` up to date (Node ≥ 24, pnpm from `packageManager`).
- [ ] Confirm with the designer/user the two defaults chosen in Open Questions (Q1, Q2) or accept the recommended defaults — neither blocks starting Steps 1–7.

---

### Implementation Steps

#### Step 1: Rename the create action to "Create CORS Rule" (create flow only)

**Files to modify:**

- `Buckets/CorsRulesTab.tsx` — trigger button label
- `Buckets/CorsRuleModal.tsx` — modal title (create branch) and submit button (create branch)

**What to do:**

1. `CorsRulesTab.tsx` L237: change `<Trans>Create rule</Trans>` → `<Trans>Create CORS Rule</Trans>`. Leave `variant="primary"` on L236 as-is (this is a page-level primary action, not one of the modal's buttons).
2. `CorsRuleModal.tsx` L150: change the create branch only —
   `title={editingRule ? t\`Edit CORS Rule\` : t\`Add CORS Rule\`}` → `title={editingRule ? t\`Edit CORS Rule\` : t\`Create CORS Rule\`}`.
   **Do not touch the `Edit CORS Rule` branch.**
3. `CorsRuleModal.tsx` L187: change `<Trans>Create Rule</Trans>` → `<Trans>Create CORS Rule</Trans>`.
4. `CorsRuleModal.tsx` L182: leave `<Trans>Creating...</Trans>` as-is (see Open Questions Q2 — it mirrors the edit branch's `Saving...` at L180).
5. Do not touch L184 `<Trans>Save Changes</Trans>` or L180 `<Trans>Saving...</Trans>`.

**Expected outcome:** the page button, the modal heading, and the modal's primary button all read "Create CORS Rule" in the create flow; the edit flow is byte-identical to before.

**Verification:** `grep -rn "Create rule\|Create Rule\|Add CORS Rule" packages/aurora/src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets/` returns only test files (fixed in Step 2).

---

#### Step 2: Update the tests broken by the rename

**Files to modify:**

- `Buckets/CorsRulesTab.test.tsx`
- `Buckets/CorsRuleModal.test.tsx`

**What to do:**

1. `CorsRulesTab.test.tsx` L225 and L284: `/Create rule/i` → `/Create CORS Rule/i`. Also update the comment on L283 and the test name on L258 ("opens add rule modal when clicking Create rule button" → "… when clicking Create CORS Rule button").
2. `CorsRuleModal.test.tsx` L108: rename the test to `"renders with 'Create CORS Rule' title when adding new rule"`.
3. `CorsRuleModal.test.tsx` L121: replace `expect(screen.getByText(/Add CORS Rule/i)).toBeInTheDocument()` with
   `expect(screen.getByRole("heading", { level: 4, name: /Create CORS Rule/i })).toBeInTheDocument()`.
   ⚠️ A plain `getByText` here now matches both the `<h4>` title and the footer button and will throw.
4. `CorsRuleModal.test.tsx` L145 (edit-title test): leave `getByText(/Edit CORS Rule/i)` alone — that string is unique (the edit submit button says "Save Changes"). Optionally harden it to the same `getByRole("heading", …)` form for symmetry.
5. `CorsRuleModal.test.tsx` L217, L271, L311: `{ name: /Create Rule/i }` → `{ name: /Create CORS Rule/i }`.

**Expected outcome:** all 8 `CorsRuleModal` tests and all 7 `CorsRulesTab` tests pass.

**Verification:**
```
pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets/CorsRuleModal.test.tsx
pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets/CorsRulesTab.test.tsx
```

---

#### Step 3: Demote the TagInput "Add" button to `variant="default"`

**Files to modify:** `Buckets/TagInput.tsx`

**What to do:**

1. L87: `variant="primary"` → `variant="default"`.
2. Optional (see Open Questions Q3) — L95: wrap the literal in the macro used everywhere else in this folder: `<Trans>Add</Trans>`, adding `import { Trans } from "@lingui/react/macro"` at the top. This file currently imports no i18n at all, and its validator error strings (L51, L120, L127, L135, L143, L147, L159) are also unlocalized — **leave those alone**, they're out of scope and would balloon the diff.
3. Change nothing else; the button keeps `disabled={disabled || !inputValue.trim()}` and its implicit `type="button"`.

**Expected outcome:** all three tag inputs (Allowed Origins, Allowed Headers, Expose Headers) render a neutral Add button; the modal footer's "Create CORS Rule" is the only primary-styled button in the dialog.

**Verification:** open the modal and confirm exactly one blue/primary button. `grep -n 'variant="primary"' Buckets/CorsRuleModal.tsx Buckets/CorsRuleForm.tsx Buckets/TagInput.tsx` → only `CorsRuleModal.tsx:171` (plus the `Spinner variant="primary"` at L196, which is unrelated).

---

#### Step 4: Remove the bucket-header "Delete CORS Rules" action and retire `DeleteCorsModal`

**Files to modify/delete:**

- `Buckets/BucketHeaderActions.tsx` — remove menu item + `hasCors` prop
- `Buckets/BucketModals.tsx` — remove import, `ModalType` member, render block, toast imports
- `Buckets/BucketHeader.tsx` — remove `corsData` destructure + `hasCors` pass-through
- `Buckets/BucketToastNotifications.tsx` — remove the two orphaned factories
- `hooks/useBucketInfo.ts` — remove the orphaned `corsData` surface
- **Delete** `Buckets/DeleteCorsModal.tsx`

**What to do:**

1. `BucketHeaderActions.tsx`: delete L49 entirely (`{hasCors && <PopupMenuItem label={t\`Delete CORS Rules\`} … />}`). Then delete `hasCors: boolean` from `BucketHeaderActionsProps` (L10) and `hasCors,` from the destructured params (L26). Keep every other menu item (`Enable/Suspend Versioning`, `Edit/Add Policy`, `Delete Policy`, `Empty Bucket`, `Delete Versions`, `Delete Bucket`).
2. `BucketModals.tsx`:
   - delete the `import { DeleteCorsModal } from "./DeleteCorsModal"` line (L9);
   - remove `getCorsDeletedToast,` and `getCorsDeleteErrorToast,` from the `BucketToastNotifications` import (L20–21);
   - remove `| "deleteCors"` from the `ModalType` union (L35);
   - delete the whole `<DeleteCorsModal … />` JSX block (L133–147).
3. `BucketHeader.tsx`: change the destructure at L32 to `const { versioningStatus, policyData, hasOldVersionsOrDeleteMarkers, isBucketEmpty } = useBucketInfo({…})` and delete the `hasCors={…}` prop at L66. Leave the badges block (L41–59) untouched — there is no CORS badge there today; the PR-history note about "keep badge" refers to badges that were never added.
4. `BucketToastNotifications.tsx`: delete `getCorsDeletedToast` (L204–207) and `getCorsDeleteErrorToast` (L209–219). **Keep** `getCorsSavedToast`, `getCorsSaveErrorToast`, `getCorsRuleDeletedToast`, `getCorsRuleDeleteErrorToast`, `getCorsRulesDeletedToast`, `getCorsRulesDeleteErrorToast` — all still in use by `CorsRulesTab`/`CorsRulesTable`.
5. `hooks/useBucketInfo.ts`: remove the now-unused `corsData` field from the `BucketInfo` interface (L21–25) and from the returned object (L144). Per the recommended default, **keep** the `cors.get` query (L94–105) and `isLoadingCors` in the `isLoading` expression (L149) so the CORS tab still gets a warm cache — add a one-line comment above the query: `// Prefetch only: warms the shared cors.get cache consumed by CorsRulesTab (5 min staleTime).` If Q1 is resolved the other way, delete the query, the `isLoadingCors` term, and the "CORS configuration query" bullet from the JSDoc at L41.
6. `rm packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/DeleteCorsModal.tsx`.
7. Do **not** touch `DeleteCorsRuleModal.tsx`, `DeleteCorsRulesModal.tsx`, `CorsRulesTable.tsx:159–172`, `CorsRulesTab.tsx:268–281`, or `server/Storage/routers/ceph/corsRouter.ts` (the `delete` procedure at L156 is still called by both surviving delete modals).

**Expected outcome:** the bucket-header kebab no longer offers any CORS action; single-rule and batch deletes are unchanged; no unused imports, props, or exports remain.

**Verification:**
```
grep -rn "DeleteCorsModal\|hasCors\|deleteCors\"\|getCorsDeletedToast\|getCorsDeleteErrorToast" packages/aurora/src | grep -v node_modules
```
Should return only `DeleteCorsModal.tsx`-free results: `deleteCorsInputSchema` (server, `types/ceph.ts:733` + `corsRouter.ts:5`) and the local `hasCors` const *inside the deleted file* should be gone entirely. Then `pnpm --filter @cobaltcore-dev/aurora typecheck` and `pnpm --filter @cobaltcore-dev/aurora lint` must be clean (this is what catches any missed unused import).

---

#### Step 5: Use the DataGrid default layout in `CorsRulesTable`

**Files to modify:** `Buckets/CorsRulesTable.tsx`

**What to do:**

1. Delete the `gridColumnTemplate` const at L95–96.
2. Change L103 from
   `<DataGrid columns={8} gridColumnTemplate={gridColumnTemplate} className="cors-rules-table">`
   to
   `<DataGrid columns={8}>`.
3. Leave everything else — the `colSpan={8}` empty-state row (L120), the `break-all` on the origins cell (L148), and the `justify-end pr-0` on the actions cell (L157) — untouched.

**Expected outcome:** the grid falls back to `repeat(8, minmax(0px, auto))`, matching the plain-`columns` convention used by `BucketTableView.tsx:107`, `SecurityGroupListContainer.tsx:143`, `ImageMembersTable.tsx:163`, etc.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/client/…/CorsRulesTable.test.tsx` (no assertions touch layout, so it should pass unchanged). Then the manual check in the Testing Plan — this is the one step with real visual-regression risk.

---

#### Step 6: Collapse the gap between the CORS toolbar zones

**Files to modify:** `Buckets/CorsRulesTab.tsx`

**What to do:**

1. L221: `<Stack direction="vertical" gap="4">` → `<Stack direction="vertical" gap="0">`.
2. Leave the inner Zone-1 `<Stack distribution="end" alignment="center" gap="2">` (L223) and the `gap="0.5"` sort wrapper (L224) exactly as they are — the designer's complaint is the inter-zone gap only.
3. Leave the `<Stack direction="vertical" gap="2">` inside `DataGridToolbar` (L243) and the `<Divider />` at L257 alone.
4. Note `CorsRulesTable` has its own `<Stack direction="vertical" gap="4">` wrapper (L101) with a single visible child — no change needed.

**Expected outcome:** Zone 1 (sort + create) sits directly on top of the `DataGridToolbar` block (which has its own `jn:py-2 jn:px-3` + `border-b`), which sits directly on top of the grid — one continuous header, matching `SecurityGroupsList.tsx:231–301`.

**Verification:** visual, per the Testing Plan. If the create button ends up visually touching the toolbar's top border, add `className="pb-2"` to the Zone-1 Stack (exactly what `SecurityGroupsList.tsx:232` does) rather than restoring a gap on the outer Stack.

---

#### Step 7: Remove the gap between the bucket tabs and the divider

**Files to modify:** `Buckets/BucketHeader.tsx`

**What to do:**

1. L79: `<Divider />` → `<Divider spacing="0" />`.
2. Leave the wrapper `<div className="-mt-4 mb-8">` (L77) untouched — the `mb-8` is the intended breathing room *below* the divider, and `-mt-4` pulls the tabs up under `ContentHeader`.
3. Do not add any class to `BucketDetailTabs` / `TabNavigation` — verified that `TabNavigation` contributes no margin (`juno-navigation` + `jn:flex` only).

**Expected outcome:** the active tab's 3px bottom border sits flush on the 1px divider line; 32px of space remains below the divider before the tab content.

**Verification:** visual. In devtools the `div.juno-divider-wrapper` should carry `jn:py-0` and have zero computed vertical padding.

---

#### Step 8: Regenerate i18n catalogs, add a changeset, run the full gate

**Files to modify:**

- `packages/aurora/src/locales/en/messages.{po,ts}`, `packages/aurora/src/locales/de/messages.{po,ts}` (generated)
- `.changeset/<new-name>.md` (new)

**What to do:**

1. `pnpm --filter @cobaltcore-dev/aurora check-i18n` — runs `lingui extract --clean && lingui compile --typescript --verbose`. Commit the four regenerated catalog files. Expect: `Create CORS Rule` added; `Create rule`, `Create Rule`, `Add CORS Rule`, `Delete CORS Rules`, `Delete CORS Configuration`, `Delete CORS`, `CORS Configuration Deleted`, `Failed to Delete CORS Configuration`, `No CORS configuration found`, and the `DeleteCorsModal` body strings removed; `Add` added only if Q3 is answered yes.
2. Add a changeset (repo requires one per user-facing change; see `.changeset/clear-bags-jam.md` for tone):
   ```
   ---
   "@cobaltcore-dev/aurora": patch
   ---

   Address design review on Ceph/S3 bucket CORS management: name the create
   action "Create CORS Rule" consistently across the trigger, modal title and
   submit button; demote the tag-input "Add" buttons so the modal has a single
   primary action; drop the redundant bucket-header "Delete CORS Rules" entry
   (per-rule and batch delete are unchanged); use the default DataGrid column
   layout; and tighten the spacing between the toolbar zones and between the
   bucket tabs and their divider.
   ```
3. Run the full local gate:
   ```
   pnpm --filter @cobaltcore-dev/aurora typecheck
   pnpm --filter @cobaltcore-dev/aurora lint
   pnpm --filter @cobaltcore-dev/aurora test
   pnpm format:check
   ```
4. Commit with a conventional message using an allow-listed scope, e.g.
   `fix(aurora): apply design review fixes to bucket CORS rules UI`
   (`aurora` is in `commitlint.config.mjs`'s `scopes`; subject must not be start-case/pascal-case/upper-case).

**Expected outcome:** clean CI-equivalent run locally.

---

### Testing Plan

**Unit tests (updates required):**

- [ ] `CorsRulesTab.test.tsx` — "renders empty state when corsRules is null" finds the button by `/Create CORS Rule/i`
- [ ] `CorsRulesTab.test.tsx` — "opens add rule modal when clicking Create CORS Rule button" still opens the mocked modal
- [ ] `CorsRuleModal.test.tsx` — create-mode title asserted via `getByRole("heading", { level: 4, name: /Create CORS Rule/i })`
- [ ] `CorsRuleModal.test.tsx` — edit-mode title still `Edit CORS Rule`
- [ ] `CorsRuleModal.test.tsx` — the three submit-button lookups use `/Create CORS Rule/i` and the mutation/`markSubmitted` assertions still pass

**Unit tests (must pass unchanged — regression guard):**

- [ ] `CorsRulesTable.test.tsx` (all 6) — headers, em-dash fallbacks, empty state, per-row kebab present, `isMutating` behaviour
- [ ] `BucketDetailTabs.test.tsx`
- [ ] `BucketToastNotifications.test.tsx` (confirms the two deleted factories were untested and the survivors still work)
- [ ] `index.test.tsx`, `BucketTableView.test.tsx`, `BucketPolicyModal.test.tsx`, `DeleteBucketModal.test.tsx`, `EmptyBucketModal.test.tsx` — the whole Ceph/Buckets suite

**Integration / typecheck as the real guard for Step 4:**

- [ ] `pnpm --filter @cobaltcore-dev/aurora typecheck` catches the removed `hasCors` prop and `corsData` field at every call site
- [ ] `pnpm --filter @cobaltcore-dev/aurora lint` catches unused imports left behind in `BucketModals.tsx` / `BucketHeader.tsx`

**Manual verification** (`pnpm dev`, log in, navigate to a project → Storage → Ceph → a bucket):

1. **Header menu (item 3):** open the bucket's `⋮` menu on a bucket that *has* CORS rules. Confirm there is **no** "Delete CORS Rules" entry, and that Enable/Suspend Versioning, Add/Edit Policy, Delete Policy, Empty Bucket, Delete Versions, Delete Bucket are all still present and functional.
2. **Tabs/divider (item 7):** with the header visible, confirm the Overview / CORS Rules tabs sit flush on the divider line, with no light strip between the active tab's underline and the rule. Compare against `main` side-by-side if possible.
3. Switch to the **CORS Rules** tab.
4. **Zone spacing (item 5):** confirm the sort control + "Create CORS Rule" button, the search/bulk-actions toolbar, and the grid form one continuous block with no vertical whitespace between them.
5. **Naming (item 1):** the button reads "Create CORS Rule". Click it — the modal heading reads "Create CORS Rule" and the footer's primary button reads "Create CORS Rule". Fill in an origin + a method and submit; the button flashes "Creating…" and the rule appears with a success toast.
6. **Button variants (item 2):** with the modal open, confirm the three "Add" buttons next to Allowed Origins / Allowed Headers / Expose Headers are neutral, and "Create CORS Rule" is the only primary-styled button. Click each Add and confirm the pill is added and the form is **not** submitted.
7. **Edit flow untouched:** kebab → Edit on a row. Heading must still read "Edit CORS Rule", primary button "Save Changes" / "Saving…".
8. **DataGrid layout (item 4) — the risk area:** create a rule with a long origin (e.g. `https://very-long-subdomain-name-for-testing.example-company-domain.com`), all five methods, 3+ allowed headers and 2 expose headers. Confirm no horizontal scrollbar, the checkbox and kebab columns aren't absurdly wide, and header/cell alignment holds. Repeat at a narrow window width (~1280px). If it fails, apply `minContentColumns={[0, 7]}` per Mitigations.
9. **Deletes preserved:** per-row kebab → Delete opens the single-rule confirmation and works; select 2+ rows → Actions → "Delete 2 Rules" opens the batch confirmation and works. Delete *all* rules via the batch flow and confirm the empty state ("There are no CORS rules for this bucket") renders and no error toast appears (this is the path that calls `cors.delete`).
10. **Empty-bucket path:** on a bucket with no CORS config, the tab shows the empty state and the header kebab is unchanged.

---

### Acceptance Criteria

- [ ] The create action reads exactly "Create CORS Rule" in all three places (tab trigger button, modal heading, modal primary button); the edit flow's "Edit CORS Rule" / "Save Changes" / "Saving…" strings are byte-identical to `main`
- [ ] `variant="primary"` appears exactly once inside the CORS rule modal subtree (the footer submit button); all three `TagInput` Add buttons are `variant="default"`
- [ ] The bucket-header overflow menu contains no CORS entry; `DeleteCorsModal.tsx` no longer exists; `grep -rn "DeleteCorsModal\|hasCors\|getCorsDeletedToast\|getCorsDeleteErrorToast" packages/aurora/src` returns nothing outside deleted code
- [ ] `"deleteCors"` is gone from `ModalType`, and `BucketModals.tsx` / `BucketHeader.tsx` have no unused imports or props
- [ ] Per-row delete (`DeleteCorsRuleModal`) and batch delete (`DeleteCorsRulesModal`) still work end-to-end, including the all-rules-deleted case that hits `cors.delete`
- [ ] `CorsRulesTable`'s `<DataGrid>` carries only `columns={8}`; no `gridColumnTemplate`, no `className="cors-rules-table"`
- [ ] No visible vertical gap between Zone 1, the `DataGridToolbar`, and the grid on the CORS Rules tab
- [ ] No visible gap between the bucket detail tabs and the divider (`Divider` has `spacing="0"`; no className hack, no wrapper margin change)
- [ ] Regenerated `en`/`de` `messages.po` + `messages.ts` committed; a changeset is present
- [ ] No regressions in the Ceph/Buckets suite or the bucket Overview tab
- [ ] `pnpm --filter @cobaltcore-dev/aurora typecheck`, `lint`, `test` and repo-root `pnpm format:check` all pass

---

### Open Questions

**Q1 — How deep should the `useBucketInfo` cleanup go?** Once `hasCors` is removed, `corsData` has no consumer. Two options: (a) *recommended* — drop `corsData` from the `BucketInfo` interface and the return object but keep the `cors.get` query as an explicit prefetch, so switching to the CORS Rules tab stays instant (the tab's own query at `CorsRulesTab.tsx:56–70` shares the key and the 5-min `staleTime`, per the comment on L68); (b) delete the query outright, saving one `GetBucketCors` call per bucket Overview load at the cost of a spinner on first tab switch. Step 4 assumes (a) and documents the query's purpose in a comment.

**Q2 — Should the create-mode loading label become "Creating CORS Rule…"?** The brief left this to judgement. Recommendation: keep `Creating...` — it mirrors the edit branch's `Saving...`, and the designer's "same name" rule is about the action label, not the transient state. Trivial to change if the designer disagrees.

**Q3 — Wrap `TagInput`'s `Add` in `<Trans>` while the file is open?** It is currently the only unlocalized user-facing label in the CORS UI. `eslint-plugin-lingui`'s `flat/recommended` (`packages/aurora/eslint.config.mjs:8`) does **not** enable `no-unlocalized-strings`, and `lingui extract` doesn't fail on it, so CI passes either way — this is a correctness/consistency call, not a blocker. Recommendation: yes, wrap it (one line + one import). Explicitly *not* proposing to localize `TagInput`'s validator error strings — that's a separate, larger change.

**Q4 — Is losing the "delete the whole CORS configuration in one click" affordance acceptable long-term?** Confirmed in-session as the designer's intent, but worth restating in the PR description: with `DeleteCorsModal` gone, wiping a 40-rule config requires select-all → batch delete. Also note that the `storage.ceph.bucket.cors.delete.*` analytics events disappear with the modal.
