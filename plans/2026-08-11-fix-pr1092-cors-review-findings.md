# PR #1092 — 4 fix prompts for `dev-executor`

Source: `document-pr` review of PR #1092 (`kiryl-ceph-cors`, head `5d8fb2d`), findings carried over unfixed from the 11.08.2026 report:
`[Было #1, 100]`, `[Было #3, 95]`, `[F, 50]`, `[A, 50]`.

Each section below is a **self-contained prompt** — copy just that section into a `dev-executor` session (or a fresh Claude Code turn) on the `kiryl-ceph-cors` branch. They touch overlapping files but not overlapping lines, so they can be run in any order or in parallel worktrees. Run each as its own commit (`fix(aurora): ...`), matching Conventional Commits.

All line numbers below are current as of commit `5d8fb2d8ffb132e1eaacfe093f44b5a70df71600` — re-read the file first in case something has moved since.

---

## Prompt 1 of 4 — Fix incorrect changeset description

**Context:** `.changeset/strong-years-drop.md` currently says the "Add CORS", "Edit/View CORS" buttons and the "Delete CORS" menu item were *removed* from the bucket header. That's factually backwards — none of those existed in the header before this PR (verified against the base commit `c65b027a`). This PR *adds* a "Delete CORS Rules" item to the header's actions menu (`BucketHeaderActions.tsx:49`, wired in `BucketModals.tsx`), in addition to the new "CORS Rules" tab with full CRUD. This changeset text ships as the package's public changelog entry and is currently wrong.

**File to modify:**
- `.changeset/strong-years-drop.md`

**What to do:**

1. Read the current file — it's 5 lines, a frontmatter block (`"@cobaltcore-dev/aurora": minor`) followed by one paragraph of prose.
2. Replace the prose paragraph. Do not touch the frontmatter (`---` / package / bump-type lines). The corrected text must accurately describe what changed:
   - The bucket details page now has a dedicated **CORS Rules** tab (alongside Overview) providing full CRUD (add/edit/delete single or multiple rules) for CORS configuration on Ceph/S3 buckets — this replaces the earlier modal-based CORS editing workflow from before this PR existed.
   - The bucket header's actions menu also gained a **"Delete CORS Rules"** item for clearing the entire CORS configuration in one step — this is new, not something that replaces a prior header control (there was no CORS-related control in the header before this PR).
3. Suggested replacement text (adjust wording if you find something more accurate while reading the current UI, but keep the "added" framing correct — do not say anything was "removed" from the header):
   ```
   Add CORS configuration management for Ceph/S3 buckets. The bucket details page
   now has a "CORS Rules" tab (alongside Overview) with full CRUD for CORS rules —
   add, edit, delete individual rules, or bulk-delete a selection. The bucket
   header's actions menu also gained a "Delete CORS Rules" item to clear the
   entire CORS configuration in one step.
   ```
4. Also fix the capitalization of "Cors Rules" → "CORS Rules" in this file if it appears, to match the tab label already corrected elsewhere in this branch (`BucketDetailTabs.tsx`).

**Expected outcome:** the changeset accurately describes the feature; nothing in it claims removal of header controls that this PR never removed.

**Verification:**
- `cat .changeset/strong-years-drop.md` — read it back, confirm it no longer contains the word "removed" in relation to header buttons/menu items.
- No code changes needed elsewhere; this is a docs-only fix. No test run required, but do run `pnpm --filter @cobaltcore-dev/aurora lint` if you're unsure the changeset frontmatter format is still valid (changesets has its own linting via `pnpm changeset status` if available).

**Acceptance criteria:**
- [ ] Changeset no longer claims "Delete CORS menu item... removed"
- [ ] Changeset accurately says a "Delete CORS Rules" header menu item was *added*
- [ ] Frontmatter (package name + `minor` bump) unchanged

---

## Prompt 2 of 4 — Fix copy-pasted help text on the Rule ID field

**Context:** In the "Add/Edit CORS Rule" form, the "Rule ID" text field has a placeholder and help text that were clearly copy-pasted from an unrelated "Project ID" field and never updated. A user filling in a CORS rule's optional ID sees guidance about a completely different concept.

**File to modify:**
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/CorsRuleForm.tsx`

**Current code (around lines 65–74, inside `<form.Field name="ID">`):**
```tsx
<TextInput
  label={t`Rule ID`}
  id={field.name}
  name={field.name}
  value={field.state.value}
  onChange={(e) => field.handleChange(e.target.value)}
  onBlur={field.handleBlur}
  placeholder={t`Access to admin area`}
  helptext={t`Confirm that the Project ID is accurate.`}
/>
```

**What to do:**

1. Open the file and find the `<form.Field name="ID">` block (search for `Confirm that the Project ID is accurate` to locate it exactly, since line numbers may have shifted).
2. Replace `placeholder={t\`Access to admin area\`}` with a placeholder that's an actual example of a CORS rule ID, e.g.:
   ```tsx
   placeholder={t`e.g. allow-frontend-app`}
   ```
3. Replace `helptext={t\`Confirm that the Project ID is accurate.\`}` with help text describing what the Rule ID field actually is. Base this on the field's real purpose (an optional, user-chosen label for the rule, max 255 characters per the server-side `corsRuleSchema` in `packages/aurora/src/server/Storage/types/ceph.ts`), e.g.:
   ```tsx
   helptext={t`Optional label to help you identify this rule later. Not sent to AWS/S3 — used only within this UI.`}
   ```
   (Adjust the exact wording if you find the server actually does send `ID` to S3 as part of the CORS rule struct — check `corsRouter.ts`'s `set` procedure and the AWS SDK's `CORSRule` type before finalizing the copy, since S3's CORS rules do support an `ID` field server-side. If it IS sent to S3, phrase it as: `t\`Optional identifier for this rule (max 255 characters).\`` instead — don't claim it stays local if it doesn't.)
4. Update the English and German locale catalogs: run `pnpm check-i18n` from the repo root (this runs `lingui extract --clean && lingui compile` for `packages/aurora`) so the new/changed strings land in `packages/aurora/src/locales/en/messages.po` and `de/messages.po`. The `en` entry should get the new source text automatically; the `de` entry will appear with an empty `msgstr` (consistent with how other new strings in this PR were handled) — don't hand-write a German translation unless you're fluent, leave it for the existing translation workflow.
5. Check `packages/aurora/src/locales/de/messages.po:636` (or wherever it now lives) still correctly has `"Confirm that the Project ID is accurate."` attached to the *actual* Project ID field elsewhere in the codebase — you're only removing this string's use on the Rule ID field, not deleting the string itself (it's still legitimately used elsewhere).

**Expected outcome:** the Rule ID field's placeholder and help text accurately describe a CORS rule ID, not a Project ID.

**Verification:**
- Manually check: `pnpm dev`, navigate to a Ceph bucket's "CORS Rules" tab, click "Create rule", inspect the Rule ID field's placeholder/help text.
- `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets/CorsRuleForm.test.tsx` if such a test file exists (check `CorsRuleModal.test.tsx` too, since it may render the form) — if any test asserts on the old placeholder/helptext string, update the assertion to match the new text.
- `pnpm check-i18n` completes without leaving the git tree dirty in a way `check-i18n` in CI would reject (i.e., commit the regenerated `.po`/`.ts` locale files alongside the code change).

**Acceptance criteria:**
- [ ] Rule ID field's placeholder and help text are about CORS rule IDs, not Project IDs
- [ ] `en`/`de` locale catalogs regenerated via `pnpm check-i18n` and committed
- [ ] Any test asserting the old text is updated
- [ ] The other, legitimate "Confirm that the Project ID is accurate." usage elsewhere in the app is untouched

---

## Prompt 3 of 4 — Wire up `isMutating` so row actions actually disable during in-flight mutations

**Context:** `CorsRulesTab.tsx` renders `<CorsRulesTable ... isMutating={false} .../>` — a hardcoded literal, never derived from any pending mutation. `CorsRulesTable.tsx` gates its per-row "Edit"/"Delete" `PopupMenuItem`s on `disabled={isMutating}` (lines ~160/165), so that guard never actually disables anything, and a user can trigger an overlapping mutation (edit one row while another row's delete, or the add/edit modal, or a bulk-delete, is still in flight) since every CORS mutation reads a snapshot of the rule list and PUTs the whole array back with no server-side concurrency check. Also relevant: a genuinely-real test for this (`CorsRulesTable.test.tsx`, "disables buttons when isMutating is true") was deleted in commit `5d8fb2d` with a comment claiming the table "doesn't have buttons that are disabled by isMutating anymore" — that claim is false (the `disabled={isMutating}` lines are still there); this fix must restore real test coverage for it.

There are three independent sources of "something is mutating" that need to feed into the one `isMutating` value the table receives:
1. The Add/Edit modal (`CorsRuleModal`, rendered by `CorsRulesTab`) — has its own `setMutation`.
2. The bulk-delete modal (`DeleteCorsRulesModal`, rendered by `CorsRulesTab`) — has its own `setMutation`/`deleteMutation`.
3. The per-row delete modal (`DeleteCorsRuleModal`, rendered *inside* `CorsRulesTable`, not by `CorsRulesTab`) — has its own `setMutation`/`deleteMutation`.

Use the same "bubble a boolean up via a callback prop" pattern already established in this codebase for `CorsRuleForm`'s `onValidationChange` — add an `onMutatingChange` callback prop to each of the three modals, called from a `useEffect` that watches the modal's own mutation-pending state.

**Files to modify:**
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/CorsRuleModal.tsx`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/DeleteCorsRulesModal.tsx`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/DeleteCorsRuleModal.tsx`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/CorsRulesTable.tsx`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/CorsRulesTab.tsx`
- Their `*.test.tsx` counterparts.

**What to do:**

1. **`CorsRuleModal.tsx`:**
   - Add `onMutatingChange?: (isMutating: boolean) => void` to `CorsRuleModalProps`.
   - Destructure it in the component.
   - Find where `setMutation` is created (`trpcReact.storage.ceph.cors.set.useMutation(...)`). Add:
     ```tsx
     useEffect(() => {
       onMutatingChange?.(setMutation.isPending)
     }, [setMutation.isPending, onMutatingChange])
     ```
   - Import `useEffect` from `"react"` if not already imported (it already is, from the earlier fix in this same file for the `onValidationChange` render-phase bug — reuse that import).

2. **`DeleteCorsRulesModal.tsx`:**
   - Add `onMutatingChange?: (isMutating: boolean) => void` to its props interface.
   - Add the same `useEffect` pattern, combining both of its mutations:
     ```tsx
     useEffect(() => {
       onMutatingChange?.(setMutation.isPending || deleteMutation.isPending)
     }, [setMutation.isPending, deleteMutation.isPending, onMutatingChange])
     ```
   - Import `useEffect` from `"react"` if not already imported.

3. **`DeleteCorsRuleModal.tsx`:**
   - Same as step 2, but this modal is rendered by `CorsRulesTable`, not `CorsRulesTab` — the callback goes to `CorsRulesTable`'s own local state (see step 4), not up to the tab.
   - Add `onMutatingChange?: (isMutating: boolean) => void` to its props interface and wire it identically:
     ```tsx
     useEffect(() => {
       onMutatingChange?.(setMutation.isPending || deleteMutation.isPending)
     }, [setMutation.isPending, deleteMutation.isPending, onMutatingChange])
     ```

4. **`CorsRulesTable.tsx`:**
   - Add local state: `const [isRowDeleteMutating, setIsRowDeleteMutating] = useState(false)`.
   - Pass `onMutatingChange={setIsRowDeleteMutating}` to the `<DeleteCorsRuleModal>` it renders.
   - Compute `const effectiveIsMutating = isMutating || isRowDeleteMutating` and use `effectiveIsMutating` (not the raw `isMutating` prop) for both `disabled={...}` occurrences on the Edit/Delete `PopupMenuItem`s.
   - Keep the `isMutating` prop itself as-is in the component's own interface/signature (it now represents "something outside this table — the add/edit modal or bulk-delete modal — is mutating"); just don't use it directly for the `disabled` props anymore, use `effectiveIsMutating`.

5. **`CorsRulesTab.tsx`:**
   - Add two pieces of local state: `const [isRuleModalMutating, setIsRuleModalMutating] = useState(false)` and `const [isBulkDeleteMutating, setIsBulkDeleteMutating] = useState(false)`.
   - Pass `onMutatingChange={setIsRuleModalMutating}` to the `<CorsRuleModal>` instance it renders.
   - Pass `onMutatingChange={setIsBulkDeleteMutating}` to the `<DeleteCorsRulesModal>` instance it renders.
   - Change the `<CorsRulesTable ... isMutating={false} .../>` line to `isMutating={isRuleModalMutating || isBulkDeleteMutating}`.

6. **Tests — restore and extend real coverage (this directly fixes the false-rationale test deletion from `5d8fb2d`):**
   - In `CorsRulesTable.test.tsx`, add back a real (non-placeholder) test: render `<CorsRulesTable isMutating={true} .../>` and assert the Edit/Delete `PopupMenuItem`s render with `disabled` (e.g. via `expect(screen.getByRole("menuitem", { name: /Edit/i })).toBeDisabled()`, adapting to however this component's existing tests query for `PopupMenuItem`s — check an existing passing test in the same file for the query pattern used for these menu items).
   - Add a test that opens the per-row delete modal (sets `deleteModalState.isOpen`) and, while `DeleteCorsRuleModal`'s mutation is mocked as `isPending: true`, asserts the table's Edit/Delete on OTHER rows are disabled too (proves `isRowDeleteMutating` is wired correctly).
   - In `CorsRuleModal.test.tsx`, add a test asserting `onMutatingChange` is called with `true` while `setMutation.isPending` is true and `false` once it resolves (mock the mutation hook to control `isPending`).
   - Do the same for `DeleteCorsRulesModal.test.tsx` and `DeleteCorsRuleModal.test.tsx` if those test files exist; create them following the existing test file conventions in this directory if they don't already cover mutation state.

**Expected outcome:** while any CORS mutation (add, edit, single delete, bulk delete) is in flight, every row's Edit/Delete menu item across the whole table is disabled — not just cosmetically, but backed by real pending-mutation state from all three modal sources.

**Verification:**
- `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets/CorsRulesTable.test.tsx src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets/CorsRuleModal.test.tsx src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets/DeleteCorsRuleModal.test.tsx src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets/DeleteCorsRulesModal.test.tsx`
- `pnpm --filter @cobaltcore-dev/aurora typecheck`
- Manual check: open the CORS Rules tab with 3+ rules, start editing one rule (open the modal, don't submit yet — mutation isn't pending until submit, so this step alone won't show disabled rows; actually submit an edit and, if your network is slow enough to observe it, or by adding a temporary artificial delay locally, confirm other rows' menu items grey out during the request), or more reliably: check via React DevTools / a temporary `console.log` that `isRuleModalMutating`/`isBulkDeleteMutating`/`isRowDeleteMutating` flip correctly, then remove the temporary logging before committing.

**Acceptance criteria:**
- [ ] `isMutating` passed to `CorsRulesTable` is no longer a hardcoded `false` — it reflects real pending state from `CorsRuleModal` and `DeleteCorsRulesModal`
- [ ] `CorsRulesTable`'s own per-row `DeleteCorsRuleModal` mutation state also disables row actions (via local `isRowDeleteMutating`, ORed with the prop)
- [ ] Real (non-placeholder) test coverage exists proving Edit/Delete are disabled while a mutation is pending, replacing the deleted no-op test
- [ ] No regressions: `pnpm --filter @cobaltcore-dev/aurora test`, `typecheck`, `lint` all pass

---

## Prompt 4 of 4 — Remove the unreachable `DeleteCorsModal` instance inside `CorsRulesTab`

**Context:** `CorsRulesTab.tsx` declares `isDeleteModalOpen`/`setIsDeleteModalOpen` state (line ~78) and renders a `<DeleteCorsModal>` instance gated by it (lines ~302–315), but `setIsDeleteModalOpen(true)` is never called anywhere — there is no button, menu item, or handler in this file (or anywhere else in the repo) that opens it. It's dead code left over from the modal→tab redesign. The bucket header already has a working, reachable "Delete CORS Rules" entry point for wiping the entire CORS config (`BucketHeaderActions.tsx` → `BucketModals.tsx` → its own separate `<DeleteCorsModal>` instance) — that one stays, this fix only removes the duplicate, unreachable instance inside the tab.

**Decision already made — do not re-litigate it or ask the user:** remove the dead code. Do not add a new "Delete All Rules" button to make it reachable — that would be a product decision outside this fix's scope, and the header already provides that exact capability via `BucketHeaderActions`.

**Files to modify:**
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/CorsRulesTab.tsx`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/CorsRulesTab.test.tsx`

**What to do:**

1. In `CorsRulesTab.tsx`:
   - Remove the state declaration `const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false)`.
   - Remove the entire `{/* Delete all CORS modal */}` JSX block that renders `<DeleteCorsModal isOpen={isDeleteModalOpen} ... />` (the whole block, including its `onClose`/`onSuccess`/`onError` handlers).
   - Remove the now-unused import `import { DeleteCorsModal } from "./DeleteCorsModal"`.
   - Check whether `getCorsDeleteErrorToast` (imported from `./BucketToastNotifications`) is used anywhere else in this file after removing the block above — search the file for other call sites. If it's not used anywhere else in `CorsRulesTab.tsx`, remove it from the import list too (keep `getCorsSavedToast`, `getCorsSaveErrorToast`, `getCorsRulesDeletedToast`, `getCorsRulesDeleteErrorToast` — verify each of those is still actually used before assuming so, don't blanket-trust this list).
   - Double check `utils.storage.ceph.cors.get.invalidate()` (called in the removed block's `onSuccess`) isn't needed for anything else that also needs it — it likely isn't, since other successful mutations already invalidate their own way; just confirm nothing else in this file relied on that specific call site.

2. In `CorsRulesTab.test.tsx`:
   - Remove the `vi.mock("./DeleteCorsModal", () => ({ DeleteCorsModal: () => null }))` block — it's now mocking a module that's no longer imported by the file under test, and having it around unused could mask a future accidental re-introduction.
   - Search the rest of the test file for any other reference to `DeleteCorsModal`, `isDeleteModalOpen`, or a test case that opens/closes this specific modal, and remove those too.
   - Do NOT touch anything related to `DeleteCorsRulesModal` (bulk delete, no "s" difference matters here) — that one is unrelated and stays.

3. Do NOT modify `DeleteCorsModal.tsx` itself, `BucketHeaderActions.tsx`, or `BucketModals.tsx` — the header's own instance of `DeleteCorsModal` is legitimate, reachable, and out of scope for this fix.

**Expected outcome:** `CorsRulesTab.tsx` no longer imports or renders `DeleteCorsModal`; the only remaining `DeleteCorsModal` usage in the codebase is the header's reachable one in `BucketModals.tsx`. No behavior change from a user's perspective (this code path was never reachable).

**Verification:**
- `git grep -n "DeleteCorsModal" packages/aurora/src` — confirm the only remaining non-definition reference is in `BucketModals.tsx` (plus the component's own file, `DeleteCorsModal.tsx`, and its own test file if one exists).
- `pnpm --filter @cobaltcore-dev/aurora typecheck` — confirms no dangling references.
- `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets/CorsRulesTab.test.tsx`
- `pnpm --filter @cobaltcore-dev/aurora lint` — catches the unused-import case if you missed cleaning one up.

**Acceptance criteria:**
- [ ] `isDeleteModalOpen` state and its `<DeleteCorsModal>` render block are gone from `CorsRulesTab.tsx`
- [ ] No unused imports left behind (`DeleteCorsModal`, and `getCorsDeleteErrorToast` if confirmed unused elsewhere in the file)
- [ ] `CorsRulesTab.test.tsx` no longer mocks a module it doesn't import
- [ ] The header's own "Delete CORS Rules" flow (`BucketHeaderActions.tsx` → `BucketModals.tsx`) is untouched and still works
- [ ] `pnpm --filter @cobaltcore-dev/aurora typecheck lint test` all pass

---

## After all 4 are done

Run the full local gate before pushing, per `CLAUDE.md`:
```bash
pnpm --filter @cobaltcore-dev/aurora typecheck
pnpm --filter @cobaltcore-dev/aurora lint
pnpm --filter @cobaltcore-dev/aurora test
pnpm check-i18n
```
Then `pnpm changeset status` (if available) to sanity-check Prompt 1's changeset edit didn't break the changeset tooling. Commit each prompt's changes separately with a Conventional Commit message (`fix(aurora): ...`), so the PR history stays reviewable — don't squash all 4 into one commit.
