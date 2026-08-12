# Plan: Stop `deleteVersionsBulk` per-item failures from being reported as success in `RestoreVersionModal` / `DeleteVersionModal`

**Date:** 2026-08-03 · **Status:** not implemented

---

## 📋 IMPLEMENTATION PLAN: Stop `deleteVersionsBulk` per-item failures from being reported as success in `RestoreVersionModal` / `DeleteVersionModal`

### ⚠️ Important logistics note (read first)

The code containing this bug is **not in the current working tree**. The working tree is on `kirylDev` (clean, at `a99951a8`); `grep -r deleteVersionsBulk packages/aurora/src` returns nothing, and `DeleteObjectsModal.tsx` does not exist locally. PR #1121's code lives only on `origin/kiryl-ceph-bulk-objects-delete` (head `3775ab00`, merge-base with `origin/main` = `f367c07`, i.e. slightly behind current `origin/main` = `cf2e0ad0`).

**All work in this plan must be done on the PR branch**, e.g.:

```bash
git checkout -b kiryl-ceph-bulk-objects-delete origin/kiryl-ceph-bulk-objects-delete
```

Do **not** rebase/merge `main` into the branch as part of this fix.

---

### Overview

`storage.ceph.objects.deleteVersionsBulk` resolves successfully (HTTP 200) even when S3 refused some or all of the requested version deletions — those land in `result.errors` / `result.errorCount`, not in a thrown error (confirmed in `bulkDeleteItems`, `packages/aurora/src/server/Storage/routers/ceph/objectRouter.ts:143-209`; it only throws when `deleted.length === 0 && errors.length === 0` inside the `catch`). `RestoreVersionModal` and `DeleteVersionModal` both call `onSuccess?.(objectKey, versionId)` and close in their `onSuccess` handler without inspecting `errorCount`, so the UI reports "restored"/"deleted" for operations S3 rejected. We make both modals treat `errorCount > 0` as a failure: keep the modal open, render the S3 per-item error detail inline, and do not invoke the success callback.

### Architecture Analysis

**Current state (all paths relative to repo root `/Users/kirylmishchuk/projects/SAP/aurora-dashboard`, on branch `kiryl-ceph-bulk-objects-delete`):**

- `packages/aurora/src/server/Storage/routers/ceph/objectRouter.ts:143-209` — `bulkDeleteItems`. Returns `deleteObjectsBulkOutputSchema.parse({ deleted, errors, deletedCount: deleted.length, errorCount: errors.length })`. So `errorCount > 0` ⟺ `errors.length > 0`, always.
- `packages/aurora/src/server/Storage/types/ceph.ts:242-268, 345-347` — `DeletedObject`, `DeleteObjectError` (`{ key: string; versionId?: string; code?: string; message?: string }`), `DeleteObjectsBulkOutput`. Both types are exported and already imported client-side by `DeleteObjectsModal.tsx:7`.
- `.../Ceph/Objects/RestoreVersionModal.tsx:44-74` — a **single shared** `handleRestoreSuccess` is wired as `onSuccess` for *both* `versioning.restoreVersion` (file restore; output has no `errorCount`) and `objects.deleteVersionsBulk` (folder restore = delete the folder's delete-marker, always exactly 1 item). It invalidates 4 queries, calls `onSuccess?.(objectKey, versionId)`, then `handleClose()`. **The modal has no inline error UI at all** — its `onError` calls `onError?.(...)` then `handleClose()`.
- `.../Ceph/Objects/DeleteVersionModal.tsx:52-64` — `deleteMutation` (`deleteVersionsBulk`) `onSuccess` does the same 4 invalidations then `onSuccess?.(objectKey, versionId)` + `handleClose()`, unconditionally. Sends 1 item (single version), 2 items (folder delete-marker + folder-marker), or N items (`allVersionIds`). It **does** have an inline error paragraph at lines 192-196 bound to `deleteMutation.error`.
- **Reference pattern** `.../Ceph/Objects/DeleteObjectsModal.tsx:66-82` — `onSuccess: (res) => { invalidate…; onDeleted(keys, res.errorCount); if (res.errorCount === 0) handleClose(); else setResult(res) }`, plus a full "results" step-B view (lines 125-185) that formats each error as `` `${code}: ${message}` `` (line 163). We follow the *decision logic*, not the two-step UI.
- **Callers** — `ObjectsTableView.tsx:751-788` renders both modals; its `onError` handlers set the target to `null` (**which closes the modal**) and rely on a comment ("Error is shown in the modal itself") that is already inaccurate. `ObjectVersionHistoryModal.tsx:254-307` renders both modals; its `onError` handlers also clear the target (closing the modal) and set a `feedbackMessage`.
- **Toast layer is not involved for these two modals.** `getVersionRestoredToast` / `getVersionDeletedToast` / `getVersionRestoreErrorToast` / `getVersionDeleteErrorToast` in `ObjectToastNotifications.tsx:274-322` are referenced **only from `ObjectToastNotifications.test.tsx`** — no production caller. `getVersionsBulkDeletePartialToast` is used only by `ObjectBrowserView.tsx:541` for the `DeleteObjectsModal` bulk flow. `ObjectsTableView`'s `onRestoreVersion`/`onDeleteVersion` props are optional and `ObjectBrowserView` never passes them. **Conclusion: no toast changes are needed or wanted here.**

**Proposed changes (design decisions — do not deviate):**

1. On `errorCount > 0`: **do not** call `onSuccess`, **do not** call `handleClose()`, **do not** call `onError` either. Store a formatted failure string in local state and render it as an inline red paragraph. Rationale for not calling `onError`: both call sites close the modal from their `onError` handler, which would immediately discard the per-key detail we just rendered — the exact false-feedback class of bug we're fixing.
2. **Always keep the 4 query invalidations**, on both the success and the failure branch — in a partial failure some versions really were deleted, so cached lists are stale either way.
3. Reuse the already-translated string `Error:` (present in `packages/aurora/src/locales/{en,de}/messages.po:1267`) as the paragraph prefix in both modals, so **no new i18n messages are introduced**.
4. `RestoreVersionModal`'s shared `handleRestoreSuccess` must be **split**: `restoreVersion` keeps the current unconditional behavior (its output has no `errorCount`); only `deleteVersionsBulk` gets the new branching handler.

### Potential Problems & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Applying the fix to the wrong branch — the bug is not in the local working tree | High | Prerequisite step 1: check out `kiryl-ceph-bulk-objects-delete` and verify `DeleteObjectsModal.tsx` exists before editing anything |
| 🔴 Accidentally adding `errorCount` branching to `restoreMutation` (`versioning.restoreVersion`) in `RestoreVersionModal` — its output has no such field, so it would be a type error / always-falsy check | Medium | Step 2 explicitly keeps `handleRestoreSuccess` for `restoreMutation` and adds a *separate* `handleDeleteMarkerSuccess` for the bulk mutation |
| Dropping query invalidation on the failure branch would leave partially-deleted lists stale | Medium | Invalidations run before the `errorCount` branch in both modals |
| ⚠️ Modal stays open with `confirmText === "delete"` after a failed `DeleteVersionModal` submit → user can immediately re-submit and see a stale error | Low | `handleDelete` clears `failureMessage` before mutating; `handleClose` clears it too |
| `deletedCount === 0 && errorCount === 0` (request aborted mid-flight before any chunk — `objectRouter.ts:154`) is still reported as success | Low | Out of scope for this fix — the client-side mutation is aborted in that scenario too. **Do not** add a `deletedCount === 0` check; note it in Open Questions |
| Existing tests use a `vi.mock` factory whose `useMutation` ignores its options, so `onSuccess` can never fire — naively switching to the `DeleteObjectsModal.test.tsx` mocking style would break the existing `mockMutate`/`mockReset` assertions | Medium | Steps 4-5 keep the existing factory shape and only add option capture inside the existing `vi.fn((options) => …)` |
| 🔒 No security impact — no new data exposure; the S3 `code`/`message` shown are already surfaced verbatim by `DeleteObjectsModal` | Low | — |
| New changeset needed? | Low | No — PR #1121 already carries `.changeset/lucky-worms-scream.md`. Do not add another |

### Prerequisites

- [ ] `git checkout -b kiryl-ceph-bulk-objects-delete origin/kiryl-ceph-bulk-objects-delete` (working tree is currently on `kirylDev`, which does **not** contain this code)
- [ ] Confirm `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/DeleteObjectsModal.tsx` exists — if not, you are on the wrong branch, stop
- [ ] `pnpm install` if the branch's lockfile differs

> Note on paths: the directory segment is a literal `$projectId` — quote paths in shell commands (`'…/$projectId/…'`) so the shell doesn't expand it.

---

### Implementation Steps

#### Step 1: Add a shared formatter for S3 per-item delete errors

**Files to create/modify:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/utils/bulkDeleteErrors.ts` — **new**
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/utils/index.ts` — add one re-export line

**What to do:**

1. Create `utils/bulkDeleteErrors.ts` with exactly this content:

```ts
import type { DeleteObjectError } from "@/server/Storage/types/ceph"

/**
 * S3's DeleteObjects reports per-item failures inline in an otherwise successful
 * (HTTP 200) response, so a *resolved* deleteVersionsBulk mutation can still carry
 * failures. Flatten those entries into one human-readable line for the small
 * single/two-item version modals, which have no room for a per-key results table
 * (DeleteObjectsModal renders the full breakdown for large selections instead).
 */
export const formatBulkDeleteErrors = (errors: DeleteObjectError[]): string =>
  errors
    .map((error) => {
      const label = error.versionId ? `${error.key} (${error.versionId})` : error.key
      const detail = [error.code, error.message].filter(Boolean).join(": ")
      return detail ? `${label}: ${detail}` : label
    })
    .join("; ")
```

2. In `utils/index.ts`, append:

```ts
export { formatBulkDeleteErrors } from "./bulkDeleteErrors"
```

**Expected outcome:** a pure, testable formatter. Note the sibling modules are imported directly (`./utils/objectValidation`), not through the barrel — the modals below import from `./utils/bulkDeleteErrors`.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck`

---

#### Step 2: Fix `RestoreVersionModal.tsx`

**File to modify:** `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/RestoreVersionModal.tsx`

**What to do:**

1. Add imports at the top:
   - `import { useState } from "react"` (the file currently imports no React hooks)
   - `import type { DeleteObjectsBulkOutput } from "@/server/Storage/types/ceph"`
   - `import { formatBulkDeleteErrors } from "./utils/bulkDeleteErrors"`
2. Inside the component, after `const projectId = useProjectId()`, add:
   ```ts
   const [failureMessage, setFailureMessage] = useState<string | null>(null)
   ```
3. Replace the existing `handleRestoreSuccess` (current lines 44-52) with an invalidation helper plus **two** handlers:
   ```ts
   const invalidateAfterRestore = () => {
     utils.storage.ceph.versioning.listObjectVersions.invalidate()
     utils.storage.ceph.versioning.checkDeletedContent.invalidate()
     utils.storage.ceph.objects.list.invalidate()
     utils.storage.ceph.containers.list.invalidate()
   }

   // versioning.restoreVersion either succeeds or rejects — no per-item results.
   const handleRestoreSuccess = () => {
     invalidateAfterRestore()
     onSuccess?.(objectKey, versionId)
     handleClose()
   }

   // deleteVersionsBulk resolves even when S3 refused the delete marker: a per-item
   // failure comes back in `errors`, not as a thrown error. Treat it as a failure.
   const handleDeleteMarkerSuccess = (result: DeleteObjectsBulkOutput) => {
     invalidateAfterRestore()
     if (result.errorCount > 0) {
       setFailureMessage(formatBulkDeleteErrors(result.errors))
       return
     }
     onSuccess?.(objectKey, versionId)
     handleClose()
   }
   ```
4. Change `deleteVersionMutation`'s `onSuccess` from `handleRestoreSuccess` to `handleDeleteMarkerSuccess`. Leave `restoreMutation`'s `onSuccess: handleRestoreSuccess`, both `onError` handlers, and both `onSettled` handlers **unchanged**.
5. In `handleClose`, add `setFailureMessage(null)` as the first statement (before `resetTracking()`).
6. In `handleRestore`, add `setFailureMessage(null)` as the first statement (before `markSubmitted()`).
7. Add the inline failure paragraph as the **last child** inside the `<Stack direction="vertical" gap="4">` in the JSX (after the `isFolder ? … : …` block, still inside `Stack`):
   ```tsx
   {failureMessage && (
     <p className="text-juno-red text-sm">
       <Trans>Error:</Trans> {failureMessage}
     </p>
   )}
   ```

**Expected outcome:** restoring a folder whose delete-marker S3 refuses to remove keeps the modal open, shows `Error: <key> (<versionId>): <Code>: <Message>`, and never calls `onSuccess`/`onClose`. File restore (`restoreVersion`) is byte-for-byte unchanged in behaviour.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck`; no new Lingui messages (`Error:` already exists in both catalogs).

---

#### Step 3: Fix `DeleteVersionModal.tsx`

**File to modify:** `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/DeleteVersionModal.tsx`

**What to do:**

1. Add imports:
   - `import type { DeleteObjectsBulkOutput } from "@/server/Storage/types/ceph"`
   - `import { formatBulkDeleteErrors } from "./utils/bulkDeleteErrors"`
   (`useState` is already imported.)
2. Next to `const [confirmText, setConfirmText] = useState("")`, add:
   ```ts
   const [failureMessage, setFailureMessage] = useState<string | null>(null)
   ```
3. Replace the `deleteMutation`'s `onSuccess` body (current lines 53-60) with:
   ```ts
   onSuccess: (result: DeleteObjectsBulkOutput) => {
     // Invalidate regardless of outcome: on a partial failure some versions really
     // were deleted, so the cached lists are stale either way.
     utils.storage.ceph.versioning.listObjectVersions.invalidate()
     utils.storage.ceph.versioning.checkDeletedContent.invalidate()
     utils.storage.ceph.objects.list.invalidate()
     utils.storage.ceph.containers.list.invalidate()
     // deleteVersionsBulk resolves even when S3 refused individual versions: those
     // come back in `errors` on an HTTP 200, not as a thrown error.
     if (result.errorCount > 0) {
       setFailureMessage(formatBulkDeleteErrors(result.errors))
       return
     }
     onSuccess?.(objectKey, versionId)
     handleClose()
   },
   ```
   Leave `onError` unchanged.
4. In `handleClose`, add `setFailureMessage(null)` (e.g. right after `setConfirmText("")`).
5. In `handleDelete`, add `setFailureMessage(null)` immediately after the `if (confirmText !== "delete") return` guard and before `markSubmitted()`, so a retry doesn't show a stale error.
6. Extend the existing error block at the bottom of the `Stack` (current lines 192-196) — **keep** the `deleteMutation.error` paragraph as-is and add a second one directly beneath it:
   ```tsx
   {failureMessage && (
     <p className="text-juno-red text-sm">
       <Trans>Error:</Trans> {failureMessage}
     </p>
   )}
   ```

**Expected outcome:** deleting a version / all versions / a folder's markers where S3 rejects one or more items keeps the modal open, lists the failures inline, and never calls `onSuccess`/`onClose`. `errorCount === 0` behaves exactly as before.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck`

---

#### Step 4: Add unit tests for the formatter

**File to create:** `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/utils/bulkDeleteErrors.test.ts`

**What to do:** create a vitest suite (`describe("formatBulkDeleteErrors", …)`) with these cases:

1. `[{ key: "a.txt", versionId: "v1", code: "AccessDenied", message: "Access Denied" }]` → `"a.txt (v1): AccessDenied: Access Denied"`
2. `[{ key: "a.txt", code: "AccessDenied" }]` → `"a.txt: AccessDenied"` (no versionId, no message)
3. `[{ key: "a.txt", versionId: "v1" }]` → `"a.txt (v1)"` (neither code nor message)
4. two entries → joined with `"; "`
5. `[]` → `""`

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Objects/utils/bulkDeleteErrors.test.ts`

---

#### Step 5: Extend `RestoreVersionModal.test.tsx`

**File to modify:** `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/RestoreVersionModal.test.tsx`

**What to do:**

1. Add `act` to the `@testing-library/react` import.
2. Declare capture variables next to the existing `const mockMutate = vi.fn()` block (top-level `let`s — they are only *read/written* when `useMutation` is invoked during render, so hoisting of `vi.mock` is not an issue):
   ```ts
   // eslint-disable-next-line @typescript-eslint/no-explicit-any
   let capturedRestoreOptions: any
   // eslint-disable-next-line @typescript-eslint/no-explicit-any
   let capturedBulkOptions: any
   ```
3. Inside the existing `vi.mock("@/client/trpcClient", …)` factory, change the two `useMutation` mocks so they capture their options (keep the returned shape identical so all existing tests keep passing):
   ```ts
   restoreVersion: {
     useMutation: vi.fn((options) => {
       capturedRestoreOptions = options
       return { mutate: mockMutate, reset: mockReset, isPending: false, error: null }
     }),
   },
   ```
   ```ts
   deleteVersionsBulk: {
     useMutation: vi.fn((options) => {
       capturedBulkOptions = options
       return { mutate: mockDeleteMutate, reset: mockDeleteReset, isPending: false, error: null }
     }),
   },
   ```
4. In `beforeEach`, after `vi.clearAllMocks()`, add `capturedRestoreOptions = undefined; capturedBulkOptions = undefined`.
5. Add a new `describe("Bulk delete result handling", …)` block with three tests:

   **(a) "calls onSuccess and closes when restoring a file succeeds"**
   - `const onSuccess = vi.fn(); const onClose = vi.fn(); renderModal({ onSuccess, onClose })`
   - click `screen.getByRole("button", { name: "Restore Version" })`
   - `act(() => { capturedRestoreOptions.onSuccess() })`
   - expect `onSuccess` toHaveBeenCalledWith `"test-file.txt", "abc123def456"`; expect `onClose` toHaveBeenCalled

   **(b) "calls onSuccess and closes when the folder delete-marker removal reports no errors"**
   - `renderModal({ objectKey: "my-folder/", versionId: "dm-1", onSuccess, onClose })`
   - click `screen.getByRole("button", { name: "Restore Folder" })`
   - expect `mockDeleteMutate` toHaveBeenCalledWith `{ project_id: "test-project-id", containerName: "test-bucket", versions: [{ key: "my-folder/", versionId: "dm-1" }] }`
   - `act(() => { capturedBulkOptions.onSuccess({ deleted: [{ key: "my-folder/", versionId: "dm-1" }], errors: [], deletedCount: 1, errorCount: 1 - 1 }) })` — use literal `errorCount: 0`
   - expect `onSuccess` toHaveBeenCalledWith `"my-folder/", "dm-1"`; expect `onClose` toHaveBeenCalled

   **(c) "does not report success and shows the S3 error when the delete marker removal fails"**
   - `renderModal({ objectKey: "my-folder/", versionId: "dm-1", onSuccess, onClose })`
   - click `screen.getByRole("button", { name: "Restore Folder" })`
   - ```ts
     act(() => {
       capturedBulkOptions.onSuccess({
         deleted: [],
         errors: [{ key: "my-folder/", versionId: "dm-1", code: "AccessDenied", message: "Access Denied" }],
         deletedCount: 0,
         errorCount: 1,
       })
     })
     ```
   - expect `onSuccess` **not** toHaveBeenCalled
   - expect `onClose` **not** toHaveBeenCalled
   - expect `screen.getByText(/my-folder\/ \(dm-1\): AccessDenied: Access Denied/)` toBeInTheDocument
   - expect `screen.getByRole("heading", { name: "Restore Folder" })` toBeInTheDocument (modal still rendered)

**Expected outcome:** the three tests fail against the pre-fix code for case (c) and pass after Step 2. All 13 existing tests keep passing untouched.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Objects/RestoreVersionModal.test.tsx`

---

#### Step 6: Extend `DeleteVersionModal.test.tsx`

**File to modify:** `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/DeleteVersionModal.test.tsx`

**What to do:**

1. Add `act` to the `@testing-library/react` import.
2. Add a top-level `// eslint-disable-next-line @typescript-eslint/no-explicit-any` + `let capturedBulkOptions: any` next to `const mockMutate = vi.fn()`.
3. Change the `deleteVersionsBulk.useMutation` mock inside the existing factory to:
   ```ts
   useMutation: vi.fn((options) => {
     capturedBulkOptions = options
     return { mutate: mockMutate, reset: mockReset, isPending: false, error: null }
   }),
   ```
4. In `beforeEach`, add `capturedBulkOptions = undefined` after `vi.clearAllMocks()`.
5. Add a `describe("Bulk delete result handling", …)` block with a local helper that types "delete" into `screen.getByLabelText('Type "delete" to confirm')` and clicks `screen.getByRole("button", { name: "Delete" })`, then three tests:

   **(a) "calls onSuccess and closes when no versions failed"**
   - `renderModal({ onSuccess, onClose })`, submit
   - `act(() => { capturedBulkOptions.onSuccess({ deleted: [{ key: "test-file.txt", versionId: "abc123def456" }], errors: [], deletedCount: 1, errorCount: 0 }) })`
   - expect `onSuccess` toHaveBeenCalledWith `"test-file.txt", "abc123def456"`; `onClose` toHaveBeenCalled

   **(b) "does not report success and shows the S3 error when the single version fails"**
   - `renderModal({ onSuccess, onClose })`, submit
   - `act(() => { capturedBulkOptions.onSuccess({ deleted: [], errors: [{ key: "test-file.txt", versionId: "abc123def456", code: "AccessDenied", message: "Access Denied" }], deletedCount: 0, errorCount: 1 }) })`
   - expect `onSuccess` **not** toHaveBeenCalled; `onClose` **not** toHaveBeenCalled
   - expect `screen.getByText(/test-file\.txt \(abc123def456\): AccessDenied: Access Denied/)` toBeInTheDocument
   - expect `screen.getByText("Delete Version")` toBeInTheDocument (still open)

   **(c) "does not report success on a partial failure when deleting all versions"**
   - `renderModal({ allVersionIds: ["v1", "v2"], onSuccess, onClose })`, submit
   - expect `mockMutate` toHaveBeenCalledWith `versions: [{ key: "test-file.txt", versionId: "v1" }, { key: "test-file.txt", versionId: "v2" }]`
   - `act(() => { capturedBulkOptions.onSuccess({ deleted: [{ key: "test-file.txt", versionId: "v1" }], errors: [{ key: "test-file.txt", versionId: "v2", code: "ObjectLocked", message: "Object is WORM protected" }], deletedCount: 1, errorCount: 1 }) })`
   - expect `onSuccess` **not** toHaveBeenCalled; `onClose` **not** toHaveBeenCalled
   - expect `screen.getByText(/test-file\.txt \(v2\): ObjectLocked: Object is WORM protected/)` toBeInTheDocument
   - expect `mockInvalidate` toHaveBeenCalled (partial success still refreshes caches)

   Note: with `allVersionIds` set, the modal title becomes `"Delete All Versions"` and the confirm button label is still `"Delete"`.

**Expected outcome:** (b) and (c) fail before Step 3 and pass after. All 16 existing tests keep passing.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Objects/DeleteVersionModal.test.tsx`

---

#### Step 7: Full verification pass

**What to do:**

```bash
pnpm --filter @cobaltcore-dev/aurora typecheck
pnpm --filter @cobaltcore-dev/aurora lint
pnpm --filter @cobaltcore-dev/aurora test
pnpm check-i18n          # must produce no catalog diff — we reused "Error:"
pnpm format:check
```

If `check-i18n` produces a diff in `packages/aurora/src/locales/*/messages.po`, something introduced a new string — revisit Steps 2/3 and use the existing `Error:` message.

**Do not** commit unless explicitly asked. If asked, use a Conventional Commit such as `fix(aurora): treat per-item deleteVersionsBulk failures as failures in version modals`, and do **not** add a new changeset (PR #1121 already ships `.changeset/lucky-worms-scream.md`).

---

### Testing Plan

**Unit tests:**

- [ ] `formatBulkDeleteErrors`: code+message+versionId, code only, key only, multiple entries joined by `"; "`, empty array
- [ ] `RestoreVersionModal`: file restore success unchanged (`restoreVersion` path)
- [ ] `RestoreVersionModal`: folder restore with `errorCount: 0` → `onSuccess` + close
- [ ] `RestoreVersionModal`: folder restore with `errorCount: 1` → no `onSuccess`, no `onClose`, error text rendered, modal still open
- [ ] `DeleteVersionModal`: single version `errorCount: 0` → `onSuccess` + close
- [ ] `DeleteVersionModal`: single version `errorCount: 1` → no `onSuccess`, no `onClose`, error text rendered
- [ ] `DeleteVersionModal`: `allVersionIds` partial failure (`deletedCount: 1, errorCount: 1`) → no `onSuccess`, no `onClose`, failing version listed, invalidation still called

**Integration tests:** none required — no router, prop-signature, or caller changes. `ObjectsTableView.test.tsx`, `ObjectBrowserView.test.tsx`, `ObjectVersionHistoryModal.test.tsx` and `DeleteObjectsModal.test.tsx` must all still pass untouched (run the whole aurora suite in Step 7).

**Manual verification** (needs a Ceph/S3 backend where a version delete can be refused, e.g. an object-lock/WORM-protected version, or a bucket policy denying `s3:DeleteObjectVersion`):

1. Open a versioned bucket → "Deleted" tab → choose a deleted folder → "Restore". If S3 refuses the delete-marker removal, the modal must stay open showing `Error: …` and the folder must remain in the Deleted tab.
2. On a protected version, open Version History → "Delete" → type `delete` → confirm. The modal must stay open with the S3 code/message; no "deleted successfully" feedback must appear in the version-history modal.
3. Happy path regression: restore a normal file version and delete a normal version — both must close the modal and show the existing success feedback exactly as before.

### Acceptance Criteria

- [ ] `RestoreVersionModal` never calls `onSuccess`/`onClose` when the `deleteVersionsBulk` result has `errorCount > 0`
- [ ] `DeleteVersionModal` never calls `onSuccess`/`onClose` when the `deleteVersionsBulk` result has `errorCount > 0`
- [ ] Both modals render the per-item S3 `code`/`message` inline in that case and remain open
- [ ] `errorCount === 0` behaviour is byte-for-byte identical to today in both modals, including the `versioning.restoreVersion` (file restore) path
- [ ] Query invalidation still runs on both branches
- [ ] No changes to `deleteBulk`, `objectRouter.ts`, `ceph.ts` types, `DeleteObjectsModal.tsx`, `ObjectToastNotifications.tsx`, `ObjectsTableView.tsx`, `ObjectBrowserView.tsx`, `ObjectVersionHistoryModal.tsx`, or any modal prop signature
- [ ] No new Lingui messages (`pnpm check-i18n` yields no catalog diff)
- [ ] `pnpm --filter @cobaltcore-dev/aurora typecheck`, `lint`, `test` and `pnpm format:check` all pass

### Open Questions

1. **Branch target.** This plan assumes the fix is applied on `kiryl-ceph-bulk-objects-delete` (PR #1121, unmerged). If the intent was instead to fix this after the PR merges to `main`, the same steps apply verbatim — only the starting branch changes. Flag to the user if PR #1121 gets merged before implementation starts.
2. **Not notifying the parent on partial failure.** I deliberately do not call `onError` on the `errorCount > 0` path, because both call sites (`ObjectsTableView.tsx:763-766, 784-787` and `ObjectVersionHistoryModal.tsx:272-278, 300-306`) close the modal in their `onError` handlers, which would throw away the per-key detail. Consequence: `ObjectVersionHistoryModal`'s `setTimeout(() => refetch(), 100)` does not run on a partial failure — this is covered by the tRPC `listObjectVersions.invalidate()` we keep calling, but if a future requirement wants an explicit parent notification, the callback contract would need a third state (as `DeleteObjectsModal` did with `onDeleted(keys, errorCount)`) — deliberately out of scope here.
3. **`deletedCount === 0 && errorCount === 0`** (abort before the first chunk, `objectRouter.ts:154`) is still treated as success. Not fixed here — it requires an aborted in-flight request that would normally also abort the client mutation. Worth a separate look if the user wants total coverage of "resolved but nothing happened".
4. **`ObjectsTableView`'s stale comment** ("Error is shown in the modal itself via mutation error state") is inaccurate for `RestoreVersionModal`, which closes on error and has no inline error UI for the `restoreVersion` path. Left untouched as out of scope.

---

**Key files (absolute paths):**

- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/RestoreVersionModal.tsx`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/RestoreVersionModal.test.tsx`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/DeleteVersionModal.tsx`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/DeleteVersionModal.test.tsx`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/DeleteObjectsModal.tsx` (reference only)
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/utils/bulkDeleteErrors.ts` (new)
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/objectRouter.ts` (read-only, `bulkDeleteItems` lines 143-209)
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/types/ceph.ts` (read-only, lines 242-268)
