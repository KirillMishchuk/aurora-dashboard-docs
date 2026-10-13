---
type: pr-report
date: 2026-08-03
status: merged
pr: [1121]
author: KirylSAP
branch: kiryl-ceph-bulk-objects-delete
---
# PR #1121: feat(aurora): add bulk delete for Ceph objects with performance and UX improvements

**Author:** KirylSAP · **Status:** merged 2026-08-07
**Branches:** `kiryl-ceph-bulk-objects-delete` → `main` · **Files:** 24 (+2937/-289)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1121

## What was done

Before this PR, objects in Ceph buckets could only be deleted one at a time — via `objects.delete` in a table row. The PR adds a full **bulk delete**: checkboxes in the table, "select all", an action bar when the selection is non-empty, and a modal with a two-step flow (confirmation → results with a per-object breakdown). It works both for current objects (the "All" tab) and for specific versions in recovery mode (the "Deleted" tab) — including full permanent deletion of all versions of a file or folder.

Besides the main feature, the PR also fixes two independent backend bugs in the existing `checkDeletedContent` pagination (risk of an infinite loop and data being skipped on later pages — see below), removes ~140 lines of duplication between the new `deleteBulk`/`deleteVersionsBulk` through a shared helper, and brings all three object delete/restore modals to a single style (the warning text goes under the title rather than into the field's `helptext`; confirmation uses lowercase `delete` rather than uppercase `DELETE`).

## How it is implemented

### Backend: `bulkDeleteItems` — shared chunking and aggregation logic

The new input schema (`packages/aurora/src/server/Storage/types/ceph.ts:210-227`) explicitly forbids passing folder keys (ending in `/`) — `DeleteObjects` would delete only the zero-byte marker, leaving the folder's contents orphaned:

```ts
// types/ceph.ts:210-219
export const deleteObjectsBulkInputSchema = projectScopedInputSchema.extend({
  containerName: z.string().min(1),
  objectKeys: z
    .array(z.string().min(1).max(1024)) // 1024 = S3 max key length
    .min(1)
    .max(10000)
    .refine((keys) => keys.every((key) => !key.endsWith("/")), {
      message: 'Folder keys (ending with "/") cannot be bulk-deleted. Use objects.delete, which deletes recursively.',
    }),
})
```

The output schema (`deleteObjectsBulkOutputSchema`, `types/ceph.ts:263-268`) reflects a key property of the S3 API: `DeleteObjectsCommand` returns a *mixed* result in a single HTTP 200 — some keys in `Deleted[]`, some in `Errors[]`, with no single success flag. All the server-side logic is built around this fact.

The shared helper `bulkDeleteItems` (`objectRouter.ts:143-208`) is reused by both new procedures — it removes the duplication that the PR explicitly mentions in its description (~140 lines):

```ts
// objectRouter.ts:187-201
} catch (error) {
  // If aborted, stop processing without recording errors
  if (abortSignal?.aborted) {
    break
  }
  // Nothing deleted yet → the failure is systemic (bad bucket, denied
  // credentials). Surface it as a normal tRPC error rather than as 1000
  // identical per-key errors.
  if (deleted.length === 0 && errors.length === 0) {
    throw mapS3ErrorToTRPCError(error, { operation, bucket: containerName })
  }
  // Otherwise degrade: earlier chunks really were deleted, so keep the
  // partial result and report this chunk's items as failures.
  const message = error instanceof Error ? error.message : String(error)
  for (const item of chunk) {
    errors.push({ key: item.key, versionId: item.versionId, code: "RequestFailed", message })
  }
}
```

The logic distinguishes two fundamentally different failure scenarios: if nothing has been deleted yet and there have been no errors yet, this is most likely a systemic problem (non-existent bucket, access denied), and it is rethrown as a regular tRPC error. If some chunks have already gone through successfully, the previous result is kept, and the failed chunk degrades into a set of per-key errors instead of losing the work already done. `deleteBulk` (`objectRouter.ts:702-714`) and `deleteVersionsBulk` (`objectRouter.ts:736-746`) are thin wrappers over this helper, each with its own de-duplication (by key for objects, by the key+versionId pair for versions) before the call.

### Backend: fix for the pagination bug in `checkDeletedContent`

Separately from bulk delete, the PR rewrites the pagination loop in `versioningRouter.checkDeletedContent` (`versioningRouter.ts:397-457`). Previously the loop was `while (!hasDeleteMarkers)` — that is, it stopped at the **very first** delete marker on any page, even if the folder had only been partially scanned and the folder's own marker (`folderMarkerVersionId`) had not yet been found on that page. Now it is `do...while(true)` with explicit exit conditions:

```ts
// versioningRouter.ts:445-457
// Early exit optimization: stop if we have all the information we need
if (hasDeletedNestedObjects && isFolderMarkerDeleted && folderMarkerVersionId) {
  break
}

// Continue to next page if truncated and has next marker
if (!response.IsTruncated || !response.NextKeyMarker) {
  break
}

keyMarker = response.NextKeyMarker
versionIdMarker = response.NextVersionIdMarker
} while (true) // eslint-disable-line no-constant-condition
```

The loop now exits correctly either when all three required facts have been collected (there are deleted nested objects, the folder marker is deleted, its versionId is known), or when the pages run out (`!response.IsTruncated`) — with additional protection against an infinite loop in case S3 reports `IsTruncated: true` but does not send `NextKeyMarker`. The result is also extended with two new fields (`folderDeleteMarkerVersionId`, `folderMarkerVersionId`), which the frontend needs to restore and permanently delete folders.

### Frontend: selection state in `ObjectBrowserView`

`selectedItems: { key: string; versionId?: string }[]` is the source of truth for the selection; it lives in `ObjectBrowserView`, not in the table. It is cleared on tab change, prefix navigation, bucket change, and after the bulk delete itself:

```ts
// ObjectBrowserView.tsx:522-535
const handleBulkDeleted = (deletedKeys: string[], errorCount: number) => {
  // The list accumulates pages; a plain invalidate would refetch only the last
  // page and append it. Drop the accumulator so the refetch rebuilds page 1.
  resetAccumulatedObjects()

  // In Deleted tab, clear all selection after bulk delete (list is being refetched anyway)
  // In All tab, only clear successfully deleted items
  if (tab === "deleted") {
    setSelectedItems([])
  } else {
    setSelectedItems((prev) => prev.filter((item) => !deletedKeys.includes(item.key)))
  }
  ...
```

There is a meaningful asymmetry between the tabs: in the "All" tab, after a partial failure the successfully deleted keys are removed from the selection while the undeleted ones stay selected (so the attempt can be retried right away); in the "Deleted" tab the selection is reset entirely regardless of the result, because the version list is refetched from scratch anyway.

The O(1) checks instead of O(n)/O(m), which the PR presents as a performance fix, are implemented via `useMemo` maps (`ObjectBrowserView.tsx:443,449`):

```ts
// ObjectBrowserView.tsx:443-451
const versionIdByKey = useMemo(() => {
  if (tab !== "deleted") return new Map<string, string>()
  return new Map(filteredDeletedFiles.map((v) => [v.key, v.versionId]))
}, [tab, filteredDeletedFiles])

const selectedItemsSet = useMemo(() => {
  return new Set(selectedItems.map((item) => makeItemKey(item.key, item.versionId)))
}, [selectedItems])
```

Permission for bulk actions is hardcoded for now:

```ts
// ObjectBrowserView.tsx:96-98
// TODO(perms): wire to storage.canUser({ permission: "storage:objects:delete" })
// instead of hardcoding — mirrors the Swift objects list.
const hasAnyBulkAction = true
```

The comment itself calls this a temporary solution and explicitly notes that the Swift object list is built the same way (without a server-side permission check) — so this is not a new gap but a match with the domain's existing architecture (see "Review" below).

### Frontend: `DeleteObjectsModal` — a new component, two steps

A new file (`DeleteObjectsModal.tsx`, 266 lines) implements the confirmation → results pair in a single component, switching on `result !== null`:

```tsx
// DeleteObjectsModal.tsx:32-57 (handleConfirm)
const handleConfirm = () => {
  if (!projectId) return

  if (result === null) {
    // Step A: Confirm
    markSubmitted()
    if (isVersionMode) {
      deleteVersionsBulkMutation.mutate({ project_id: projectId, containerName: bucketName, versions })
    } else {
      deleteBulkMutation.mutate({ project_id: projectId, containerName: bucketName, objectKeys })
    }
  } else {
    // Step B: Close results view
    handleClose()
  }
}
```

When `errorCount === 0` the modal closes itself; on a partial failure it switches to a results screen with a truncated error list (up to 100 entries, `MAX_ERROR_VISIBLE`) and a list of objects being deleted (up to 20, `MAX_VISIBLE`), both with an "and N more" counter.

### Frontend: permanent deletion of all versions/a folder via `deleteVersionsBulk`

`DeleteVersionModal` (single version deletion from history) and `RestoreVersionModal` (for folders, "restore" is implemented as deleting the delete marker) were moved from the previous `versioning.deleteVersion`/`versioning.restoreVersion` procedure paths to the shared `objects.deleteVersionsBulk` — so as not to duplicate the deletion logic and to handle the compound "delete the whole folder" case uniformly (the delete marker + the folder's marker object itself — two items in one call):

```ts
// DeleteVersionModal.tsx:52-59
const deleteMutation = trpcReact.storage.ceph.objects.deleteVersionsBulk.useMutation({
  onSuccess: () => {
    utils.storage.ceph.versioning.listObjectVersions.invalidate()
    utils.storage.ceph.versioning.checkDeletedContent.invalidate()
    utils.storage.ceph.objects.list.invalidate()
    utils.storage.ceph.containers.list.invalidate()
    onSuccess?.(objectKey, versionId)
  },
  ...
```

### Toasts: a single factory instead of duplication

`ObjectToastNotifications.tsx` gained `createBulkDeleteToasts(entityType)` (`ObjectToastNotifications.tsx:194-233`) — a factory parameterized by `"object" | "version"` that produces `success`/`partial`/`error` variants with correct plural forms via Lingui `<Plural>`, instead of six separate, nearly identical functions.

## What it affects

Both new procedures (`deleteBulk`, `deleteVersionsBulk`), the `bulkDeleteItems` helper and all the new Zod schemas (`deleteObjectsBulkInputSchema`, `deleteVersionsBulkInputSchema`, `deleteObjectsBulkOutputSchema`, `deletedObjectSchema`, `deleteObjectErrorSchema`) are used only within files changed by the PR itself — there are no outward-facing contract changes; it is a purely additive feature at the `AuroraRouter` level.

There is, however, a notable side effect: **`versioning.deleteVersion`** (the old single version-deletion procedure, `versioningRouter.ts:281`) remained in the router but lost all of its frontend consumers — `DeleteVersionModal` and `RestoreVersionModal` now use `objects.deleteVersionsBulk` instead. The only remaining references to `.deleteVersion` are in its own test `versioningRouter.test.ts:236,252`. This is not a bug (the procedure is still valid and tested), but the orphaned endpoint is a candidate for removal in a separate PR if it is definitely no longer needed.

The name `DeleteObjectsModal` is already taken — there is an unrelated component with the same name, `Swift/Objects/DeleteObjectsModal.tsx` (different directory, different tRPC path, a separate bulk-delete implementation for Swift). There is no conflict (different modules), but it is worth keeping in mind when searching by name.

`checkDeletedContent` is now also queried on the "All" tab (`enabled: !!projectId && versioningStatus?.status === "Enabled" && allFolders.length > 0`; previously only on the "deleted" tab) in order to hide deleted folders from the regular list — a new constant source of load on this query rather than a one-off for the "Deleted" tab.

## Review

CLAUDE.md-compliance, bug-scan, historical-context, prior-feedback and comment-compliance were run in parallel over the diff, history, comments and earlier review feedback; the candidates went through a separate confidence-scoring pass.

CLAUDE.md-compliance, comment-compliance and historical-context found nothing: the hardcoded `hasAnyBulkAction = true` (see above) matches the existing pattern of the Swift object list rather than being a new gap; all the checked comments in the new code (`bulkDeleteItems`, the schemas, `checkDeletedContent`, the selection handlers in `ObjectBrowserView`) accurately describe what the code does; the rewritten pagination loop in `checkDeletedContent` correctly fixes the bug from PR #1013 (see "What it affects" — the history of its origin is there too). Prior-feedback noted one open point unrelated to this PR: `checkDeletedContent` still has no hard limit on the number of pagination pages — this was flagged as Major back in the review of PR #992 and has not been fixed; PR #1121 does not regress this (it keeps the previous behavior), but does not fix it either.

**1 issue found with confidence ≥80** (originally two related findings with the same root cause went through confidence-scoring separately — `RestoreVersionModal` scored 100, `DeleteVersionModal` with the same code pattern scored 75, below the reporting threshold; below they are merged into a single defect, since the code is identical and differs only in how easily it reproduces):

1. **Mutations based on `deleteVersionsBulk` treat the operation as successful even if S3 deleted nothing.** After `RestoreVersionModal` and `DeleteVersionModal` were moved from single procedures to the shared `objects.deleteVersionsBulk`, both `onSuccess` handlers rely on the mere fact that the promise resolved and never check `res.errorCount`/`res.errors`. The `bulkDeleteItems` helper (`objectRouter.ts:143-209`) throws an exception only when the `catch` actually fired (a network/systemic error) **and** nothing has been deleted yet; a per-key S3 failure (for example, a versioning conflict on that particular key) is returned inside a normal HTTP 200 in `response.Errors` — there is no exception, and the promise resolves normally with `errorCount > 0`.

   The confirmed (confidence 100) path is `RestoreVersionModal.tsx:45-52,82-88`: restoring a folder deletes its delete marker via `deleteVersionsBulk` with **exactly one** item (`versions: [{ key: objectKey, versionId }]`). It was previously assumed that for a single item `bulkDeleteItems` either throws an exception or is guaranteed to return full success — this is wrong: a per-key failure on a single item does not throw an exception either. `handleRestoreSuccess` (`RestoreVersionModal.tsx:45-52`) is called unconditionally and reports "folder restored" even though the delete marker has not physically been removed — the path is guaranteed to be reachable on any per-key S3 failure on that key.

   The same code pattern (confidence 75, below the threshold as a standalone finding, but the root cause is identical) is in `DeleteVersionModal.tsx:52-59`: when permanently deleting all versions of a file (`allVersionIds`) or deleting a folder (delete marker + folder marker, two items), `onSuccess` likewise does not look at `errorCount`, but here triggering it requires a genuinely mixed S3 response for several items in a single request — a less guaranteed but realistically reachable scenario.

---
Analyzed: 2026-08-03 · commit `3775ab00`
