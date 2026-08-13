# Plan: Ceph/S3 action-naming consistency (specific nouns on destructive + upload actions)

**Date:** 2026-08-13 · **Status:** not implemented

## 📋 IMPLEMENTATION PLAN: Ceph/S3 action-naming consistency (specific nouns on destructive + upload actions)

**Target branch:** `kiryl-ceph-cors-review-findings` (currently at `cf8ec618`). All line numbers in this plan are verified directly against that branch (`git show kiryl-ceph-cors-review-findings:<path>`) — implement on `kiryl-ceph-cors-review-findings` as checked out on the remote machine.

**Root path** for all relative paths below:
`/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/`

### Overview

Continue the naming convention established by PR #1092's follow-up (`Create rule` → `Create CORS Rule`, plan at `/Users/kirylmishchuk/projects/SAP/DOCS/plans/2026-08-12-cors-rules-designer-fixes.md`): every destructive or upload action must name the *thing* it acts on, both in the row/kebab menu that triggers it and in the footer button of the modal that confirms it. Client-only, string-only work in two folders (`Ceph/Buckets/`, `Ceph/Objects/`) plus the test files that query those strings and the regenerated Lingui catalogs. No tRPC, router, schema, or behaviour change.

**Decisions confirmed by the user (2026-08-13):** Q1 resolved — only footer buttons are renamed, modal titles are left as-is. Q4 resolved — yes, the CORS Rules row action and modal footers are included in this same plan/PR (see Scope 4 and Step 8 below). Q5 resolved — no, this does not extend to the Swift storage UI; that stays fully out of scope (not even filed as a follow-up by this plan).

---

### Architecture Analysis

**Current state — verified by reading the files, not guessed.**

Scope 1 — bucket list row kebab (`Buckets/BucketTableView.tsx`, rendered by `Buckets/index.tsx` → `<BucketTableView>`):

| Line | Current | Opens |
| --- | --- | --- |
| 238 | `Show Details` | navigates (not in scope) |
| 243 | `` t`Empty` `` | `EmptyBucketModal` (`setEmptyModalBucket`, rendered L270–276) |
| 248 | `` t`Delete` `` | `DeleteBucketModal` (`setDeleteModalBucket`, rendered L278–284) |

Scope 2 — object browser. Two distinct surfaces:

- **Per-row kebab** — `Objects/ObjectsTableView.tsx`, one `<PopupMenu>` with a 4-way branch (L597–727): regular folder / deleted folder / deleted file / regular object.

| Line | Row type | Current label | Opens |
| --- | --- | --- | --- |
| 602 | deleted folder (tab `deleted`) | `` t`Restore` `` | `RestoreVersionModal` (already says "Restore Folder") |
| 616 | deleted folder | `` t`Delete` `` | `DeleteVersionModal` (`allVersionIds` = delete-marker + folder-marker) |
| 639 | **regular folder** | `` t`Delete` `` | `DeleteObjectModal` (`key: row.prefix`) |
| 647 | deleted file | `` t`Restore` `` | `RestoreVersionModal` |
| 660 | deleted file | `` t`Delete` `` | `DeleteVersionModal` (all versions) |
| 680–715 | regular object | `Download` / `View Versions` / `Copy` / `Move/Rename` / `Edit Metadata` / `Share URL` | — (already specific) |
| 716 | **regular object** | `` t`Delete` `` | `DeleteObjectModal` |

  Folders and objects therefore **share one component** (`ObjectsTableView`) and **share one modal** (`DeleteObjectModal`, which derives `isFolder = objectKey.endsWith("/")` at L74 and already branches its *title*).

- **Bulk / multi-select** — `Objects/ObjectBrowserView.tsx` L718–735. Already compliant: `i18n._(plural(selectedCount, { one: "Delete # Object", other: "Delete # Objects" }))` and the version-mode equivalent (this is the #1121 bulk-delete work). The toolbar upload trigger at L655–657 already reads `Upload Object`. **No changes needed in `ObjectBrowserView.tsx`** — only its modal (`DeleteObjectsModal`) footer.

Scope 3 — modal footers reachable from the above (full audit; `confirmButtonLabel` is typed `string`, so plural labels need `t` ternaries or `i18n._(plural(...))`, not `<Plural>` JSX):

| Modal | Title | Footer today | Verdict |
| --- | --- | --- | --- |
| `Buckets/EmptyBucketModal.tsx` | `Empty Bucket` (L197) | `Empty Bucket` (L203) | ✅ compliant |
| `Buckets/EmptyBucketModal.tsx` (versioned branch) | `Delete Versions` (L150) | `Delete Versions` (L156) | ✅ compliant |
| `Buckets/DeleteBucketModal.tsx` | `Delete Bucket` (L140) | `Delete Bucket` (L146) | ✅ compliant |
| `Buckets/DeleteVersionsModal.tsx` | `Delete Versions` (L91) | `Delete Versions` (L97) | ✅ compliant |
| `Buckets/EmptyBucketsModal.tsx` (bulk) | `<Plural one="Empty Bucket" other="Empty Buckets">` (L91) | **`` t`Empty` ``** (L97) | 🔧 fix |
| `Objects/DeleteObjectModal.tsx` | `Delete Folder "{name}"` / `Delete Object` (L85) | **`` t`Delete` ``** (L87) | 🔧 fix |
| `Objects/DeleteObjectsModal.tsx` (bulk) | `Delete # Object(s)` / `Delete # Version(s)` (L209) | **`` t`Delete` ``** (L217) | 🔧 fix |
| `Objects/DeleteVersionModal.tsx` | `Delete All Versions` / `Delete Version` (L120) | **`` t`Delete` ``** (L126) | 🔧 fix |
| `Objects/UploadObjectModal.tsx` | `Upload object to: <path>` (L182) | **`` t`Upload` ``** (L194) | 🔧 fix |
| `Objects/CreateFolderModal.tsx` | `Create New Folder` | `Create Folder` (L101) | ✅ compliant |
| `Objects/RestoreVersionModal.tsx` | `Restore Folder` / `Restore Version` (L127) | same (L133) | ✅ compliant, and it's the reference pattern for `isFolder` branching |

Scope 4 — CORS Rules row action + its two modal footers (Q4, confirmed in scope). Verified directly against `kiryl-ceph-cors-review-findings`.

| File | Line (on `kiryl-ceph-cors-review-findings`) | Current | Fix |
| --- | --- | --- | --- |
| `Buckets/CorsRulesTable.tsx` | 164 | row action `label={t\`Delete\`}` | → `label={t\`Delete CORS Rule\`}` |
| `Buckets/DeleteCorsRuleModal.tsx` | 158 (title, unchanged) / 164 (footer) | title `t\`Delete CORS Rule\`` / footer `confirmButtonLabel={t\`Delete Rule\`}` | footer → `confirmButtonLabel={t\`Delete CORS Rule\`}` |
| `Buckets/DeleteCorsRulesModal.tsx` (bulk) | title unchanged / footer ~179 | title `<Plural value={ruleCount} one="Delete CORS Rule" other="Delete CORS Rules" />` / footer `confirmLabel = ... ruleCount === 1 ? t\`Delete Rule\` : t\`Delete Rules\`` | footer → `ruleCount === 1 ? t\`Delete CORS Rule\` : t\`Delete CORS Rules\`` |

No dedicated test files exist for either modal (`DeleteCorsRuleModal.test.tsx` / `DeleteCorsRulesModal.test.tsx` do not exist on either branch), and `CorsRulesTable.test.tsx` (240 lines, identical on both branches) asserts nothing about the row's "Delete" text — grepped and confirmed empty. So, unlike Scopes 2–3, **this rename does not require any test file changes**. It does create the same title=footer text collision pattern flagged elsewhere in this plan (both modals will show "Delete CORS Rule"/"Delete CORS Rules" as both heading and button) — harmless today since nothing asserts on it, but if a test is ever added for these modals, use `getByRole("heading", { level: 4, name: … })` for the title per the pattern established in Step 6.

**Established precedent to copy for plural footers** — `Buckets/DeleteCorsRulesModal.tsx:179`:

```ts
const confirmLabel = isDeleting ? t`Deleting...` : ruleCount === 1 ? t`Delete Rule` : t`Delete Rules`
```
i.e. the title carries the count, the footer carries only the noun. Use this shape rather than `i18n._(plural(...))` in footers — it avoids new imports and keeps footer text distinct from title text (which matters for tests, see Risks).

**Juno `Modal` rendering (verified in `@cloudoperators/juno-ui-components@9.1.0` bundle):** a `string` title renders `<h4 class="juno-modal-title" id=…>`; a **ReactNode** title renders `<div class="juno-modal-title juno-h4" role="heading" aria-level="4" id=…>`. Both are reachable via `getByRole("heading", { level: 4, name: … })`, and `aria-labelledby` points only at the title — so `getByRole("dialog", { name })` is unaffected by footer-label changes.

**Proposed changes:** 7 label sites in 3 table components (Scopes 1, 2, 4) + 7 modal footer expressions (Scopes 3, 4), plus mechanical query updates in 6 test files (Scope 4/CORS needs zero test changes), plus regenerated `en`/`de` catalogs and one changeset.

---

### Potential Problems & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| ⚠️ **`DeleteObjectModal`: title and footer become the same string.** After the fix, the object case renders "Delete Object" as both `<h4>` and the button. `DeleteObjectModal.test.tsx:95` `getByText("Delete Object")` and `:230` `queryByText("Delete Object")` will match two nodes → `Found multiple elements`. | High (guaranteed break) | Convert L95 to `getByRole("heading", { level: 4, name: "Delete Object" })`. L230 asserts *absence* while closed, so `queryByText` still returns null — but convert it too (`queryByRole("heading", …)`) for symmetry. The folder test at L102 (`/Delete Folder "folder"/`) stays unique — the footer will be plain "Delete Folder", the title `Delete Folder "folder"`. |
| ⚠️ **`DeleteVersionModal`: same collision.** Footer mirrors the title exactly. `DeleteVersionModal.test.tsx:129` and `:401` use `getByText("Delete Version")`. | High | Convert both to `getByRole("heading", { level: 4, name: "Delete Version" })`. |
| ⚠️ **Button-name queries stop matching.** 6× `name: "Delete"` in `DeleteObjectModal.test.tsx`, 8× in `DeleteVersionModal.test.tsx`, 8× `name: /Delete/i` in `DeleteObjectsModal.test.tsx`, 17× `/^Upload$/i` in `UploadObjectModal.test.tsx`, 10× `/^Empty$/i` in `EmptyBucketsModal.test.tsx`, 1× `getByText("Delete")` in `ObjectsTableView.test.tsx:510`. Exact-string `name: "Delete"` fails; anchored `/^Empty$/i`, `/^Upload$/i` fail. `/Delete/i` (unanchored) keeps matching, but leave nothing to luck. | High (guaranteed break, 50 sites) | Step 6 updates each explicitly with the new expected string. Do **not** loosen to bare `/Delete/i` — anchor the new labels. |
| 🔴 **Don't touch `data-testid`s.** `empty-action-${bucket.name}` / `delete-action-${bucket.name}` (`BucketTableView.tsx:245,250`), `bulk-delete-action`, `download-action-…` etc. are queried by tests and are stable contracts. | Medium | Change only the `label=` prop; leave every `data-testid` byte-identical. |
| ⚠️ **`Objects/index.test.tsx`-style ancestors mock the modals.** `Buckets/index.test.tsx` mocks `./EmptyBucketsModal` (L89) and `./BucketTableView` (L65); `ObjectsTableView.test.tsx` mocks `DeleteObjectModal`/`DeleteVersionModal`/`RestoreVersionModal`. So parent-level tests are insulated — the only parent-level break is `ObjectsTableView.test.tsx:510`. | Low | Verified by grep; no other parent test asserts these labels. |
| ⚡ Longer labels ("Delete 3 Objects" would be longest) in a narrow Juno modal footer / a kebab menu. | Low (visual) | Recommendation keeps footers count-free ("Delete Objects"), matching `DeleteCorsRulesModal`. Kebab items are single-line and the menu is content-sized. |
| **i18n catalogs go stale.** New standalone msgids introduced: `Delete Folder`, `Empty Buckets`, `Delete Objects` (`Delete Bucket`, `Delete Object`, `Delete Version`, `Delete Versions`, `Empty Bucket`, `Upload Object` already exist in `src/locales/en/messages.po`); `Delete Rule`/`Delete Rules` become orphaned (Scope 4). | Low | Step 9 runs `check-i18n` and commits the 4 regenerated files. CI's `check-i18n` job only runs the command (no diff gate), so this is hygiene, not a blocker. |
| Generic `` t`Delete` `` remains in the Swift mirror (`Swift/Objects/ObjectsTableView.tsx:534`, `Swift/Containers/ContainerTableView.tsx:274,279`, 4 Swift modals) and in non-storage lists (security groups, images). Reviewers may ask "why only Ceph?". | Low | Deliberate scoping — see Open Question Q5. Say so in the PR description. |
| Stale remote branch `origin/vlad-delete-ceph-overflow-and-empty-bucket` touches Ceph "empty bucket" wording, but is based on a very old `main` (its diff vs. current main is ~13.7k deletions) and is not a live conflict. | Low | Ignore; mention in the PR if it ever gets rebased. |

---

### Prerequisites

- [ ] `git switch kiryl-ceph-cors-review-findings` (exists locally and on origin at `cf8ec618`); working tree clean.
- [ ] `pnpm install` current (Node ≥ 24, pnpm from `packageManager`).
- [ ] Q1, Q4, Q5, Q8 are resolved by explicit user decision (see Open Questions) and already reflected in the steps below. Q2 (deleted-tab rows), Q3 (`Restore`), Q6 (transient labels), Q7 (informational) were not asked separately — the steps below implement dev-planner's **recommended default** for each; each is a one-line back-out if you want something different before implementing.

---

### Implementation Steps

#### Step 1: Name the bucket-list row actions

**Files to modify:** `Buckets/BucketTableView.tsx`

**What to do:**
1. L243: `` label={t`Empty`} `` → `` label={t`Empty Bucket`} ``.
2. L248: `` label={t`Delete`} `` → `` label={t`Delete Bucket`} ``.
3. Leave L238 `Show Details`, and leave `data-testid="empty-action-…"` (L245) / `"delete-action-…"` (L250) untouched.

**Expected outcome:** the per-bucket kebab reads *Show Details / Empty Bucket / Delete Bucket*, matching the wording already used by the bucket **header** kebab (`Buckets/BucketHeaderActions.tsx:50,54`) and the bucket-list **bulk** menu (`Buckets/index.tsx:379–380`).

**Verification:** `` grep -n 'label={t`Empty`}\|label={t`Delete`}' `` in `Buckets/BucketTableView.tsx` returns nothing. `BucketTableView.test.tsx` asserts nothing about these labels, so it must pass unchanged.

> **Note:** a separate, not-yet-implemented plan (`2026-08-12-ceph-bucket-empty-action-consistency.md`) touches the same two labels on the way to a different fix (gating "Empty Bucket" on emptiness, issues #1107/#1109). Per explicit user decision (2026-08-13), this plan proceeds independently — the two are not being reconciled.

---

#### Step 2: Name the object-browser row actions

**Files to modify:** `Objects/ObjectsTableView.tsx`

**What to do:**
1. L639 (regular folder branch, `onClick={() => setDeleteTarget({ key: row.prefix })}`): `` t`Delete` `` → `` t`Delete Folder` ``.
2. L716 (regular object branch, last item before `</>`): `` t`Delete` `` → `` t`Delete Object` ``.
3. **Q2 default — deleted tab (`showingVersions`):** L616 (deleted *folder*) → `` t`Delete Folder` ``; L660 (deleted *file*) → `` t`Delete Object` ``. If Q2 is answered "leave the deleted tab alone", skip 3 and note it in the PR.
4. Do **not** touch L602 / L647 `` t`Restore` `` (Q3), nor `Download` / `View Versions` / `Copy` / `Move/Rename` / `Edit Metadata` / `Share URL`, nor any `data-testid`.

**Expected outcome:** no bare "Delete" remains in the object row menu; folder rows say *Delete Folder*, object/file rows say *Delete Object*.

**Verification:** `` grep -n 'label={t`Delete`}' Objects/ObjectsTableView.tsx `` → empty.

---

#### Step 3: Fix the single-item delete modal footer (`DeleteObjectModal`)

**Files to modify:** `Objects/DeleteObjectModal.tsx`

**What to do:**
1. L87 — replace
   `` confirmButtonLabel={deleteMutation.isPending ? t`Deleting...` : t`Delete`} ``
   with
   `` confirmButtonLabel={deleteMutation.isPending ? t`Deleting...` : isFolder ? t`Delete Folder` : t`Delete Object`} ``.
   `isFolder` is already in scope (L74). Keep `` t`Deleting...` `` (Q6).
2. Leave the title at L85 exactly as-is (`Delete Folder "{displayName}"` / `Delete Object`) — title changes are Q1.
3. Leave `confirmButtonVariant="primary-danger"` (L88) and the `Type "delete" to confirm` input (L159) untouched.

**Expected outcome:** deleting `photo.png` shows heading "Delete Object" + button "Delete Object"; deleting `docs/` shows heading `Delete Folder "docs"` + button "Delete Folder".

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/client/…/Ceph/Objects/DeleteObjectModal.test.tsx` will fail until Step 6 — that's expected and is the guard.

---

#### Step 4: Fix the bulk delete modal footer (`DeleteObjectsModal`)

**Files to modify:** `Objects/DeleteObjectsModal.tsx`

**What to do:**
1. Just above the `return (` of the confirm view (after L200, next to the other derived consts), add, following `DeleteCorsRulesModal.tsx:179`:
   ```ts
   const confirmLabel = isPending
     ? t`Deleting...`
     : isVersionMode
       ? count === 1
         ? t`Delete Version`
         : t`Delete Versions`
       : count === 1
         ? t`Delete Object`
         : t`Delete Objects`
   ```
2. L217: `` confirmButtonLabel={isPending ? t`Deleting...` : t`Delete`} `` → `confirmButtonLabel={confirmLabel}`.
3. Do **not** add `plural`/`i18n` imports and do **not** put the count in the button — the title (L209–215) already carries it, and keeping the strings distinct avoids new `getByText` ambiguity.
4. Leave the "Delete Results" step-B modal (L136–138, confirm label `Done`) untouched.

**Expected outcome:** heading "Delete 3 Objects" + button "Delete Objects"; heading "Delete 1 Version" + button "Delete Version".

---

#### Step 5: Fix the remaining footers (`DeleteVersionModal`, `EmptyBucketsModal`, `UploadObjectModal`)

**Files to modify:** `Objects/DeleteVersionModal.tsx`, `Buckets/EmptyBucketsModal.tsx`, `Objects/UploadObjectModal.tsx`

**What to do:**
1. `DeleteVersionModal.tsx` L126: `` confirmButtonLabel={t`Delete`} `` → `` confirmButtonLabel={isDeletingAllVersions ? t`Delete All Versions` : t`Delete Version`} `` — mirrors the title at L120 exactly. `isDeletingAllVersions` is computed at L87, before the `return`. Leave the title alone.
2. `EmptyBucketsModal.tsx` L97: `` confirmButtonLabel={isPending ? t`Emptying...` : t`Empty`} `` → `` confirmButtonLabel={isPending ? t`Emptying...` : totalCount === 1 ? t`Empty Bucket` : t`Empty Buckets`} ``. `totalCount` is defined at L81.
3. `UploadObjectModal.tsx` L194: `` confirmButtonLabel={isPending ? t`Uploading...` : t`Upload`} `` → `` confirmButtonLabel={isPending ? t`Uploading...` : t`Upload Object`} ``. Leave the title (L182–193, "Upload object to: <path>") and `` cancelButtonLabel={isPending ? t`Cancel upload` : t`Cancel`} `` (L196) untouched.

**Expected outcome:** no modal in the Ceph feature reaches a user with a bare `Delete` / `Empty` / `Upload` footer button.

**Verification (whole scope-3 sweep):**
```
grep -rn 'confirmButtonLabel={t`Delete`}\|: t`Delete`}\|: t`Empty`}\|: t`Upload`}' \
  "packages/aurora/src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/"
```
must return nothing.

---

#### Step 6: Update the tests broken by the renames

**Files to modify (6):**

- `Objects/ObjectsTableView.test.tsx` — L510: in the disabled-during-transfer loop, `["Copy", "Move/Rename", "Edit Metadata", "Delete"]` → `["Copy", "Move/Rename", "Edit Metadata", "Delete Object"]` (that test renders `folders={[]}` with a single object row, so only the object label applies).
- `Objects/DeleteObjectModal.test.tsx` —
  - L95 → `expect(screen.getByRole("heading", { level: 4, name: "Delete Object" })).toBeInTheDocument()`
  - L230 → `expect(screen.queryByRole("heading", { level: 4, name: "Delete Object" })).not.toBeInTheDocument()`
  - all **6** `screen.getByRole("button", { name: "Delete" })` (L147, 158, 169, 180, 248, 305) → `{ name: "Delete Object" }` (every one of these renders `defaultProps`, i.e. an object key, not a folder)
  - L102 (folder title) unchanged. **Add** one new test: render `{ ...defaultProps, objectKey: "folder/" }` and assert `getByRole("button", { name: "Delete Folder" })`.
- `Objects/DeleteVersionModal.test.tsx` —
  - L129, L401 → `getByRole("heading", { level: 4, name: "Delete Version" })`
  - all **8** `{ name: "Delete" }` (L170, 181, 209, 272, 295, 319, 341, 356) → `{ name: "Delete Version" }`, **except** any case rendered with `allVersionIds` of length > 1 — the "does not report success on a partial failure when deleting all versions" block (from ~L404) and any other `renderModal({ allVersionIds: [...] })` need `{ name: "Delete All Versions" }`. Check each call site's props before substituting; do not blind-replace.
- `Objects/DeleteObjectsModal.test.tsx` — all **8** `{ name: /Delete/i }` (L203, 233, 290, 344, 392, 529, 614, 672) → anchored `{ name: /^Delete Objects?$/ }` for object-mode tests and `{ name: /^Delete Versions?$/ }` for the version-mode ones (L489+ block). Title assertions at L119/138/489/509 (`"Delete 3 Objects"` etc.) stay as `getByText` — those strings include the count and remain unique.
- `Objects/UploadObjectModal.test.tsx` — all **17** `/^Upload$/i` → `/^Upload Object$/i`. Leave `/Uploading\.\.\./i` (L291, 380) and `getByText(/Upload object to:/i)` (L110, 115) alone — neither collides.
- `Buckets/EmptyBucketsModal.test.tsx` — all **10** `/^Empty$/i` (L186, 204, 238, 261, 282, 305, 330, 358, 379, 472) → `/^Empty Buckets$/i` for the multi-bucket fixtures and `/^Empty Bucket$/i` for any single-bucket one (check each `renderModal` fixture; the default fixture is 3 buckets, and L154 shows a single-bucket case exists). The `getByRole("dialog", { name: … })` assertions (L142, 149, 154) are unaffected.

**Expected outcome:** `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph` is green.

**Verification:**
```
pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph
```

---

#### Step 7 (optional, recommended): Add regression coverage for the row labels

**Files to modify:** `Buckets/BucketTableView.test.tsx`, `Objects/ObjectsTableView.test.tsx`

**What to do:**
1. In `BucketTableView.test.tsx`'s existing `describe("Action menu")` block (L284), add a test that opens the kebab of `bucket-row-bucket-1` and asserts `getByText("Empty Bucket")` and `getByText("Delete Bucket")` are present. Follow the popup-opening idiom already used in `ObjectsTableView.test.tsx:499–505` (`within(row).getByRole("button", { name: /more/i })`).
2. In `ObjectsTableView.test.tsx`, add a test that opens a **folder** row's kebab (`folder-row-documents/`) and asserts `Delete Folder`, and one on an object row asserting `Delete Object`.

**Expected outcome:** these labels can no longer regress silently — today `BucketTableView.test.tsx` asserts nothing about them.

---

#### Step 8: Name the CORS Rules row action and its modal footers (Q4 — confirmed in scope)

**Files to modify:** `Buckets/CorsRulesTable.tsx`, `Buckets/DeleteCorsRuleModal.tsx`, `Buckets/DeleteCorsRulesModal.tsx`.

**What to do:**
1. `CorsRulesTable.tsx` L164: `` label={t`Delete`} `` → `` label={t`Delete CORS Rule`} ``. Leave the neighboring `` label={t`Edit`} `` (L159) untouched — edit isn't in scope.
2. `DeleteCorsRuleModal.tsx` L164: `` confirmButtonLabel={t`Delete Rule`} `` → `` confirmButtonLabel={t`Delete CORS Rule`} ``. Leave the title at L158 (already `t\`Delete CORS Rule\``) untouched — it will now read the same as the footer button, which is expected and matches the pattern used elsewhere in this plan (e.g. `DeleteObjectModal`'s object case).
3. `DeleteCorsRulesModal.tsx` (bulk), the `confirmLabel` line (~L179): change
   `` ruleCount === 1 ? t`Delete Rule` : t`Delete Rules` `` → `` ruleCount === 1 ? t`Delete CORS Rule` : t`Delete CORS Rules` ``.
   Leave `` isDeleting ? t`Deleting...` : `` and the title (`<Plural value={ruleCount} one="Delete CORS Rule" other="Delete CORS Rules" />`) untouched.

**Expected outcome:** the CORS rules row kebab reads *Edit / Delete CORS Rule*; deleting a single rule shows heading and button both "Delete CORS Rule"; bulk-deleting shows heading and button both "Delete CORS Rule"/"Delete CORS Rules" depending on count.

**Verification:** no test files need updating for this step — confirmed no test asserts the row's "Delete" text or either modal's footer text (`DeleteCorsRuleModal.test.tsx`/`DeleteCorsRulesModal.test.tsx` don't exist; `CorsRulesTable.test.tsx` was grepped and has no matching assertions). Run `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets/CorsRulesTable.test.tsx` as a sanity check that it still passes unchanged.

---

#### Step 9: Regenerate i18n catalogs, add a changeset, run the gate

**Files to modify:** `packages/aurora/src/locales/{en,de}/messages.{po,ts}` (generated), `.changeset/<new-name>.md` (new)

**What to do:**
1. `pnpm --filter @cobaltcore-dev/aurora check-i18n`, then commit all four regenerated catalogs. Expect **new** msgids `Delete Folder`, `Empty Buckets`, `Delete Objects` (and `Delete Object`/`Delete Bucket`/`Delete Version`/`Delete Versions`/`Empty Bucket`/`Upload Object` gaining extra source references — they already exist at `en/messages.po` L1048, 1003, 1078, 1081, 1270, 3790). `Delete CORS Rule`/`Delete CORS Rules` already exist (used by the modal titles today) and simply gain a second source reference from the footer. `Delete Rule`/`Delete Rules` are used **only** in the two footer lines Step 8 changes (`DeleteCorsRuleModal.tsx:164`, `DeleteCorsRulesModal.tsx:179` — verified by repo-wide grep, no other callers), so `check-i18n` will drop both msgids from the catalog entirely; that's expected, not a bug. Don't hand-translate the German entries.
2. Add a changeset (`.changeset/ceph-action-naming.md`), tone matching `.changeset/cors-design-fixes.md`:
   ```
   ---
   "@cobaltcore-dev/aurora": patch
   ---

   Name Ceph/S3 storage actions after what they act on: the bucket row menu now
   offers "Empty Bucket"/"Delete Bucket", object rows offer "Delete Folder"/
   "Delete Object", the CORS rules row menu offers "Delete CORS Rule", and the
   confirmation modals' footer buttons match their action ("Delete Folder",
   "Delete Object", "Delete Objects", "Delete Version", "Empty Buckets",
   "Upload Object", "Delete CORS Rule"/"Delete CORS Rules") instead of a
   generic verb.
   ```
3. Full local gate:
   ```
   pnpm --filter @cobaltcore-dev/aurora typecheck
   pnpm --filter @cobaltcore-dev/aurora lint
   pnpm --filter @cobaltcore-dev/aurora test
   pnpm format:check
   ```
4. Commit: `fix(aurora): name ceph storage actions after their target object` (`aurora` is an allow-listed scope in `commitlint.config.mjs`; subject stays lower-case).

---

### Testing Plan

**Unit tests (must be updated — Step 6):**
- [ ] `DeleteObjectModal.test.tsx` — object title via `getByRole("heading", …)`; 6 button lookups on "Delete Object"; new folder-footer test on "Delete Folder"
- [ ] `DeleteVersionModal.test.tsx` — 2 title lookups via role; 8 button lookups split between "Delete Version" and "Delete All Versions" per fixture
- [ ] `DeleteObjectsModal.test.tsx` — 8 button lookups anchored to `Delete Objects?` / `Delete Versions?`; count-bearing title assertions unchanged
- [ ] `UploadObjectModal.test.tsx` — 17 lookups on `/^Upload Object$/i`; `Uploading...` assertions unchanged
- [ ] `EmptyBucketsModal.test.tsx` — 10 lookups split singular/plural per fixture; `dialog` name assertions unchanged
- [ ] `ObjectsTableView.test.tsx` — disabled-during-transfer label list uses "Delete Object"

**Unit tests (must pass unchanged — Step 8, no test edits needed):**
- [ ] `CorsRulesTable.test.tsx` — passes unchanged; no assertion on the row's "Delete" text today

**Unit tests (must pass unchanged — regression guard):**
- [ ] `Buckets/index.test.tsx` (mocks `EmptyBucketsModal` + `BucketTableView`), `BucketTableView.test.tsx`, `EmptyBucketModal.test.tsx`, `DeleteBucketModal.test.tsx`, `DeleteVersionsModal.test.tsx`, `CreateFolderModal.test.tsx`, `RestoreVersionModal.test.tsx`, `ObjectBrowserView.test.tsx`, `CorsRulesTab.test.tsx`, `CorsRuleModal.test.tsx`
- [ ] `pnpm --filter @cobaltcore-dev/aurora typecheck` / `lint` clean (catches an unused `isFolder`, a stray import, etc.)

**Manual verification** (`pnpm dev`, log in, project → Storage → Ceph):
1. Bucket list: kebab on a row → *Show Details / Empty Bucket / Delete Bucket*. Click **Empty Bucket** → heading + button both "Empty Bucket"; cancel. Click **Delete Bucket** → heading + button both "Delete Bucket".
2. Select 1 bucket → Actions → "Empty Bucket" → modal heading "Empty Bucket", **button "Empty Bucket"**. Select 3 → heading "Empty Buckets", button "Empty Buckets". Type `empty`, confirm, verify the bulk empty still runs and reports progress.
3. Open a bucket → **Upload Object** → footer button reads "Upload Object" (not "Upload"); pick a file, upload, confirm the button flips to "Uploading… n%" and the object appears.
4. Create a folder (button/label unchanged) → its row kebab reads **Delete Folder**; open it → heading `Delete Folder "<name>"`, button "Delete Folder". Type `delete`, confirm, folder disappears.
5. An object row kebab reads **Delete Object**; modal heading and button both "Delete Object".
6. Multi-select 2 objects → Actions → "Delete 2 Objects" → modal heading "Delete 2 Objects", button **"Delete Objects"**. Confirm; verify both the all-success path and (if reproducible) the partial-failure "Delete Results" screen, whose button still reads "Done".
7. On a versioning-enabled bucket, switch to the **deleted** tab: a deleted folder row → *Restore* + **Delete Folder**; a deleted file row → *Restore* + **Delete Object**; opening either shows "Delete All Versions" as heading **and** button. (Skip if Q2 is answered "out of scope".)
8. Object row → View Versions → per-version kebab still reads *Restore* / *Delete Version* / *Delete Marker*; the confirmation button now reads "Delete Version".
9. CORS Rules tab: a rule row's kebab reads *Edit / Delete CORS Rule*. Opening it: heading and button both "Delete CORS Rule". Multi-select rules and bulk-delete: heading and button both "Delete CORS Rule"/"Delete CORS Rules" depending on count.
10. Regression: bucket header kebab (Enable/Suspend Versioning, Add/Edit Policy, Delete Policy, Empty Bucket, Delete Versions, Delete Bucket) is visually and functionally unchanged; CORS Rules tab's create/edit flow and toolbar spacing (from the prior PR) are unaffected.

---

### Acceptance Criteria

- [ ] `` grep -rn 'label={t`Delete`}\|label={t`Empty`}' `` under `…/-components/Ceph/` (Buckets + Objects only, Swift excluded per Q5) returns nothing
- [ ] `` grep -rn ': t`Delete`}\|: t`Empty`}\|: t`Upload`}\|confirmButtonLabel={t`Delete`}\|t`Delete Rule`\|t`Delete Rules`' `` under `…/-components/Ceph/Buckets` and `.../Ceph/Objects` returns nothing
- [ ] Bucket row menu: *Empty Bucket*, *Delete Bucket*; object row menu: *Delete Folder* (folders), *Delete Object* (objects); CORS rules row menu: *Delete CORS Rule*
- [ ] Every modal reachable from those menus has a footer button naming its object: Empty Bucket · Empty Bucket(s) · Delete Bucket · Delete Folder · Delete Object · Delete Object(s)/Version(s) · Delete Version / Delete All Versions · Delete Versions · Upload Object · Delete CORS Rule · Delete CORS Rules
- [ ] All `data-testid` values unchanged (`empty-action-*`, `delete-action-*`, `bulk-delete-action`, `bulk-delete-versions-action`, `download-action-*`, `share-url-action-*`)
- [ ] No modal **title** changed (confirmed: footer buttons only, per Q1) and no non-destructive/non-upload label changed (unless Q3 says otherwise)
- [ ] Transient labels `Deleting...` / `Emptying...` / `Uploading...` unchanged (per Q6's recommended default — not separately confirmed with the user)
- [ ] Swift storage UI untouched (confirmed out of scope, per Q5)
- [ ] Regenerated `en`/`de` `messages.po` + `messages.ts` committed; one changeset added
- [ ] `pnpm --filter @cobaltcore-dev/aurora typecheck`, `lint`, `test` and root `pnpm format:check` all pass

---

### Open Questions

**Q1 — [RESOLVED 2026-08-13, user: "только кнопки в футере" (footer buttons only)]** Modal *titles* are not renamed — only footer buttons, per Steps 3–5 and 8. `UploadObjectModal`'s title (`Upload object to: <path>`) and `Objects/CreateFolderModal`'s title (`Create New Folder`) stay exactly as-is.

**Q2 — Do the "deleted" tab rows count as folder/object rows?** `ObjectsTableView.tsx:616` (deleted folder) and `:660` (deleted file) also say bare "Delete", but they open `DeleteVersionModal` whose heading is "Delete All Versions". Step 2.3 renames them to "Delete Folder"/"Delete Object" (recommended — otherwise a bare "Delete" survives in the very same menu), accepting that the row label and the modal heading use different vocabulary ("Delete Folder" → "Delete All Versions"). Alternative if you dislike that mismatch: leave both as "Delete", or give `DeleteVersionModal` an `isFolder` heading branch ("Delete Folder") mirroring `RestoreVersionModal:127` — that one *is* a title change, so it depends on Q1.

**Q3 — Extend the rule to non-destructive `Restore`?** `ObjectsTableView.tsx:602/647` and `ObjectVersionHistoryModal.tsx:221` say bare "Restore", while `RestoreVersionModal` already titles itself "Restore Folder"/"Restore Version". Renaming the three menu items would cost 3 lines and 0 test changes (grep found no test asserting "Restore" as a menu label). Out of the stated destructive/upload scope — **recommend including it** for menu-level consistency, but confirm first.

**Q4 — [RESOLVED 2026-08-13, user: "да" (yes, include)]** Extended to the CORS rules row action and both its modals' footers — see Scope 4 (Architecture Analysis) and Step 8. Checked (not just recommended): no test asserts the row's "Delete" text or either modal's footer text today, so this rename needs zero test-file changes, unlike Q2/Q3's siblings.

**Q5 — [RESOLVED 2026-08-13, user: "нет" (no)]** Does not extend to the Swift storage UI. The identical generic labels there (`Swift/Containers/ContainerTableView.tsx:274 "Empty"`, `:279 "Delete"`; `Swift/Objects/ObjectsTableView.tsx:534 "Delete"`; generic `Delete` footers in `Swift/Objects/DeleteObjectModal.tsx:113`, `DeleteFolderModal.tsx:93`, `DeleteObjectsModal.tsx:114`, `Containers/DeleteContainerModal.tsx:138`) are left untouched by this plan and are not being filed as a follow-up here.

**Q6 — Should transient labels get the noun too** ("Deleting Object…", "Uploading Object…", "Emptying Buckets…")? **Recommendation: no**, consistent with the resolution of Q2 in the CORS plan — the convention is about the action label, not the in-flight state.

**Q7 — Is "Empty" ever valid on something other than a bucket?** Answered by the code, not assumed: **no.** A repo-wide grep for `Empty`/`empty` as an *action* in the Ceph tree finds only bucket-level uses — `BucketTableView.tsx:243`, `BucketHeaderActions.tsx:50`, `Buckets/index.tsx:379–380` (bulk), `EmptyBucketModal`, `EmptyBucketsModal`, and the `storage:containers:empty` permission verb. There is **no** "Empty Folder" affordance and no S3/Ceph server procedure for one (a folder is just a key prefix; "emptying" it would be indistinguishable from the existing bulk delete). Swift has the same shape at container level (`ContainerTableView.tsx:274`, `EmptyContainerModal`). So "Empty" → "Empty Bucket" is unambiguous today; flagging only in case a future "Empty Folder" is planned, which would make the bucket-specific label load-bearing rather than merely clearer.

**Q8 — [RESOLVED 2026-08-13, user: "не обращай внимание на этот план" (disregard that plan)]** This plan proceeds independently of `2026-08-12-ceph-bucket-empty-action-consistency.md`, which touches the same two `BucketTableView.tsx` labels via a different fix (emptiness-gating, #1107/#1109). No reconciliation between the two plans is being done here — see the note under Step 1.

---

**Key files referenced (absolute):**
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketTableView.tsx`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/EmptyBucketsModal.tsx`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/ObjectsTableView.tsx`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/ObjectBrowserView.tsx` (bulk menu + upload trigger — already compliant, no edits)
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/DeleteObjectModal.tsx`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/DeleteObjectsModal.tsx`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/DeleteVersionModal.tsx`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/UploadObjectModal.tsx`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/CorsRulesTable.tsx` (Scope 4 / Q4)
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/DeleteCorsRuleModal.tsx` (Scope 4 / Q4)
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/DeleteCorsRulesModal.tsx` (Scope 4 / Q4, precedent for plural footer labels — L179)
- Prior plan / convention source: `/Users/kirylmishchuk/projects/SAP/DOCS/plans/2026-08-12-cors-rules-designer-fixes.md`
