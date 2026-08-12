# Plan: Ceph/S3 Section 8 — Bulk Object Delete (`objects.deleteBulk` + multi-select UI)

**Date:** 2026-07-27 · **Status:** not implemented

# 📋 IMPLEMENTATION PLAN: Ceph/S3 Section 8 — Bulk Object Delete (`objects.deleteBulk` + multi-select UI)

## Overview

Add multi-object deletion to the Ceph (S3) object browser: a BFF procedure `storage.ceph.objects.deleteBulk` backed by the AWS SDK `DeleteObjectsCommand`, and a multi-select UI (checkbox column + select-all + "Delete N Objects" action) with a confirmation modal that renders a **per-key results summary**, because S3 returns a mixed `Deleted[]`/`Errors[]` payload inside a single HTTP 200 response.

Verified against `origin/main` (`fa875c7`): `git grep -n "deleteBulk"` returns nothing; `DeleteObjectsCommand` appears only as an internal implementation detail of `objects.deleteAll` and the folder-recursion branch of `objects.delete`. No exposed bulk-delete procedure exists for Ceph.

⚠️ **Your working tree is not on main.** `HEAD` = `d4a076b` (branch `kirylDev`); `origin/main` = `fa875c7` and is **6 commits ahead**, including `#1086` (Ceph upload) and `#1090` (`useVirtualizedTableBody`/`useAvailableViewportHeight`). All line numbers below refer to **`origin/main`**. Rebase before starting (Prerequisites).

---

## Architecture Analysis

### Current state — BFF

| File                                                                                                                 | Role                                                                                                                                                                                                                                                                                           |
| -------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/objectRouter.ts` | All Ceph object procedures. On main: `list` (125), `getDetails` (258), `deleteAll` (298), `delete` (516), `createFolder` (601), `copy` (638), `move` (678), `updateMetadata` (739), `downloadObject` (833), `watchDownloadProgress` (971), `uploadObject` (1092), `watchUploadProgress` (1227) |
| `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/types/ceph.ts`                | Zod schemas. `deleteObjectInputSchema` at 197; "OBJECT OPERATION SCHEMAS" banner at 191; exported `z.infer` types block at 269–274                                                                                                                                                             |
| `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/cephProcedure.ts`             | `cephProtectedProcedure` = `projectScopedProcedure` + EC2-credential resolution + `ctx.getCephClient()`                                                                                                                                                                                        |
| `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/helpers/s3ErrorMapper.ts`     | `mapS3ErrorToTRPCError(error, { operation, bucket, key })` — every procedure's catch block                                                                                                                                                                                                     |
| `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/constants.ts`                 | `S3_MAX_KEYS_PER_REQUEST = 1000`                                                                                                                                                                                                                                                               |
| `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/index.ts`             | `objectRouter` is spread into `storage.ceph.objects` — **no router wiring change needed**, a new key in the exported object is enough                                                                                                                                                          |
| `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/permissionRouter.ts`  | `"storage:objects:delete" → { engine: "storage", rule: "storage:object_delete" }` (line 34) already exists                                                                                                                                                                                     |
| `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/apps/dashboard/src/policies/storage.json`                        | `storage:object_delete = rule:storage_admin` already defined                                                                                                                                                                                                                                   |

**Permission key: no new key needed.** Per `PERMISSION_KEY_PATTERN.md` the action vocabulary is `read/list/create/update/delete/...`; "bulk" is not an action, it's a batching detail of `delete`. Reuse `storage:objects:delete`.

### Current state — the reference implementation already in the repo (Swift)

Swift **already solved this whole pattern**; mirror it rather than inventing:

- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/swift/swiftRouter.ts` — `bulkDelete` at 822 (`?bulk-delete`, parses `Number Deleted` / `Errors:` into `{ numberDeleted, numberNotFound, errors[] }`)
- `.../types/swift.ts` — `bulkDeleteInputSchema` (300, `objects: z.array(z.string()).min(1).max(10000)`), `bulkDeleteResultSchema` (305)
- `.../Swift/Objects/DeleteObjectsModal.tsx` — type-to-confirm bulk modal, derives the deleted-vs-failed split client-side, calls `onSuccess(count)` / `onError(message, deletedKeys)`
- `.../Swift/Objects/ObjectsTableView.tsx` — `selectedObjects: string[]` / `setSelectedObjects` props, `hasAnyBulkAction` prop that adds/removes the leading `40px` checkbox track (`GRID_COLUMN_TEMPLATE_WITH_SELECT` at 74, checkbox cell at 394–421, folders get a **disabled** checkbox + `Tooltip`)
- `.../Swift/Objects/index.tsx` — selection state (170), reset-on-prefix-change effect (174), "Zone 3" toolbar with select-all `Checkbox` + `PopupMenu` → "Delete # Objects" (460–506), `handleToggleSelectAll` (394), bulk toasts (265–277)

### Current state — Ceph object browser UI

| File (all under `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/`) | Role                                                                                                                                                                                                                                                                                                                   |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ObjectBrowserView.tsx` (739 lines)                                                                                                                                 | Owns query + accumulation (`allObjects`/`allFolders`/`allVersions`, effect at 148–181), pagination (`continuationToken`, `keyMarker`), search/sort, tabs (`all` / `deleted`), and toolbar **Zones 1–4** (422, 482, 510, 520). Renders `<ObjectsTableView>` at 544 and raises all toasts. **No selection state today.** |
| `ObjectsTableView.tsx` (630 lines)                                                                                                                                  | Virtualized rows via `useVirtualizedTableBody({ count: rows.length })` (276–283). `GRID_COLUMN_TEMPLATE` = 4 columns (112). Row union `CephRow = FolderRow \| ObjectRow \| VersionRow` (90–109). Owns the per-row action menu + all row-level modals. **No checkboxes today.**                                         |
| `DeleteObjectModal.tsx`                                                                                                                                             | Single-object confirm: type `DELETE`, `useModalTracking({ actionPrefix: "storage.ceph.object.delete" })`, invalidates `objects.list` + `containers.list`                                                                                                                                                               |
| `ObjectToastNotifications.tsx`                                                                                                                                      | `get*Toast()` factories returning `{ message: ReactNode } & NotificationOptions`                                                                                                                                                                                                                                       |

Virtualization: `useVirtualizedTableBody` (`/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/hooks/useVirtualizedTableBody.ts`) withholds `virtualItems`/`totalSize` until `useAvailableViewportHeight` has measured. Measurement runs **synchronously** inside `useLayoutEffect` (`useAvailableViewportHeight.ts:82`), so jsdom tests render rows without extra flushing. A selection column is purely a grid-template/cell change — it does **not** interact with virtualization, provided selection state lives **above** the virtualizer (in `ObjectBrowserView`, keyed by object key, not by row index). Never key selection by `virtualRow.index`.

### Proposed changes (high level)

1. **BFF**: `deleteObjectsBulkInputSchema` / `deleteObjectsBulkOutputSchema` in `types/ceph.ts`; `deleteBulk` procedure in `objectRouter.ts` that chunks the key list into ≤1000-key `DeleteObjectsCommand` calls and aggregates S3's `Deleted[]`/`Errors[]` verbatim.
2. **UI**: selection state hoisted into `ObjectBrowserView`; a `selectable`/`selectedKeys`/`onToggleKey` prop trio on `ObjectsTableView` adding a leading checkbox column; a new Zone-4 bulk-action bar (select-all + Actions menu); a new `DeleteObjectsModal.tsx` with a **two-step** flow: confirm → results summary.

---

## DECISIONS (assumptions taken rather than blocking)

| # | Decision | Rationale |
| --- | --- | --- |
| **D1** | Output is **not** a boolean/count — it is `{ deleted: [{key, versionId?, deleteMarker?, deleteMarkerVersionId?}], errors: [{key, code, message, versionId?}], deletedCount, errorCount }` | S3 returns `Deleted[]` + `Errors[]` in one HTTP 200. A boolean would throw away exactly the information the results summary must render. |
| **D2** | Input cap `max(10000)`, chunked server-side into `S3_MAX_KEYS_PER_REQUEST` (1000) batches, results aggregated across chunks | Matches Swift's `bulkDelete` cap (`types/swift.ts:301`) for cross-backend consistency; chunk-looping over `DeleteObjectsCommand` is already the established pattern in this very file (`deleteAll`, 372–384). A hard cap of 1000 would dead-end the user after two "Load More" clicks + select-all. |
| **D3** | Chunk-level throw handling: if a chunk's `send()` rejects **and nothing has been deleted yet**, rethrow via `mapS3ErrorToTRPCError` (clean `NOT_FOUND`/`FORBIDDEN` path). If it rejects **after** earlier successes, record that chunk's keys as per-key `errors` and continue | Keeps the "bad bucket / bad credentials" case a normal tRPC error, while never silently losing already-completed deletions. |
| **D4** | ✅ **Confirmed by user (2026-07-27).** Folder keys (trailing `/`) are **rejected** by the schema, and folder rows get a disabled checkbox in the UI — exactly matching Swift, no recursive folder expansion | `DeleteObjects` on a folder marker deletes only the zero-byte marker and orphans everything under the prefix. Recursive bulk delete of a folder's contents is out of scope entirely (not just deferred) — do it the same way Swift does: disabled checkbox + tooltip, full stop. |
| **D5** | **New** `DeleteObjectsModal.tsx`; do **not** extend `DeleteObjectModal.tsx` | Single-delete modal is bound to one key + size + lastModified + the folder-recursion copy; bulk needs a key list, a count, and a second "results" step. Extending it would make both paths worse. |
| **D6** | Modal is two-step: **confirm** (type `DELETE`, list preview capped at 20 + "… and N more") → on partial/total failure, the same modal switches to a **results** step listing failed keys with their S3 error codes; full success closes the modal and fires a success toast | The issue explicitly requires "show results summary". Swift's toast-with-`\n` approach (`DeleteObjectsModal.tsx:57-62`) is the fallback if you want strict Swift parity, but it truncates badly for >3 failures. |
| **D7** | Confirm word is `DELETE` (uppercase), matching Ceph's `DeleteObjectModal.tsx:74`, not Swift's lowercase `delete` | Consistency within the Ceph surface the user is actually in. |
| **D8** | Bulk delete is **not** offered in the `deleted` (versions) tab, and version rows are never selectable | `deleteBulk` deletes current versions (no `VersionId`); deleting specific versions in bulk is a distinct feature — see **Follow-up A** below. |
| **D9** | ✅ **Confirmed by user (2026-07-27), scope deliberately frozen.** Permission gating mirrors Swift exactly: a `hasAnyBulkAction` boolean with a `TODO(perms)` comment, hardcoded `true` — **do not** add real permission checks in this plan | Real RBAC/policy-engine gating for Ceph object/bucket procedures is a separate, larger future feature ("Ceph-wide permissions") covering the whole domain (single delete, copy, move, bulk delete, bucket policy, versioning, CORS, etc. all at once), not just this one action — see the new "Follow-up Tasks" section below. Doing it piecemeal here would gate only the bulk path while single-object delete stays ungated, which is exactly the inconsistency this plan avoids by deferring. The key to wire later is the existing `storage:objects:delete`. |

---

## Potential Problems & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| 🐛 **Partial failure inside a 200 OK** — treating the mutation's `onSuccess` as "all deleted" | **High** | Output schema forces the caller to read `errors[]`. `onSuccess` handler in the modal branches on `result.errorCount > 0` before deciding toast vs results step. Server test asserts the mixed-response case. |
| 🐛 **Stale list after bulk delete** — `ObjectBrowserView` accumulates pages into `allObjects`; invalidating `objects.list` refetches only the *current* `continuationToken` page, and the effect at 148–181 **appends** when `continuationToken` is set → duplicates / ghost rows | **High** | On bulk-delete settle, reset pagination exactly as `navigateToPrefix` does (`ObjectBrowserView.tsx:183-198`): `setContinuationToken(undefined); setKeyMarker(undefined); setVersionIdMarker(undefined); setAllObjects([]); setAllFolders([]); setHasMore(false)` **before** invalidating. |
| 🐛 **Selection keyed by row index breaks under virtualization** | **High** | Selection is `string[]` of full object keys, held in `ObjectBrowserView`; `ObjectsTableView` only reads `selectedKeys.includes(row.key)`. Never touch `virtualRow.index`. |
| 🔴 **Grid/header misalignment** — adding a column to the body but not the header (or the empty state) | Medium | Single `gridColumnTemplate` + `columnCount` derived from one `selectable` boolean, applied to header `<DataGrid>`, body rows, **and** the empty-state `<DataGrid columns={…}>` at `ObjectsTableView.tsx:296`. |
| 🐛 **Stale selection after navigation / tab switch / search** | Medium | Clear selection in `navigateToPrefix`, `navigateToBuckets`, the tab-change effect (96–103), and after a successful bulk delete. On *partial* failure, prune only the successfully deleted keys (Swift pattern, `Swift/Objects/index.tsx:271-277`). Selection of rows filtered out by search is preserved but the count is shown, so the user is never surprised. |
| 🔒 **Unbounded input / payload DoS** | Medium | `z.array(...).min(1).max(10000)` plus `z.string().min(1).max(1024)` per key (S3 max key length). Procedure is `cephProtectedProcedure` → project-scoped session + EC2 creds, so keys can only reach the caller's own tenant. |
| ⚡ **10 sequential S3 round-trips for a 10 000-key selection** | Medium | Chunks are sequential (bounded memory, no thundering herd against RGW); pass `{ abortSignal: ctx.req.signal }` to each `send()` and check `ctx.req.signal?.aborted` between chunks, per `docs/0010_abort_signal_propagation.md` (`downloadObject` does this at `objectRouter.ts:857`). |
| 🐛 **Deleting an object that is mid-download** | Low | Disable the row checkbox while `activeTransfers.get(transferKey(bucketName, row.key))` is set (the table already computes `isStreaming`). |
| 🐛 **Versioned buckets**: "deleted" objects reappear as restorable versions | Low | Copy in the modal must say "marked as deleted, restorable from version history" when `versioningEnabled`, mirroring `DeleteObjectModal.tsx:106-113`. |
| 🔴 **`pnpm check-i18n` CI failure** from unwrapped strings / uncommitted catalogs | Medium | Every new string uses `<Trans>` / `t\`\`` / `<Plural>`; run `pnpm --filter @cobaltcore-dev/aurora check-i18n` and **commit** the regenerated `src/locales/{en,de}/messages.po` + compiled output. |

---

## Prerequisites

- [ ] **Rebase/branch off `origin/main` (`fa875c7`).** Current `HEAD` (`d4a076b`) lacks `#1086` and `#1090`; `ObjectsTableView.tsx` there still uses the old `calc(100vh - 500px)` virtualizer and would produce a conflicting diff. Verify after rebase: `git grep -l useVirtualizedTableBody -- 'packages/aurora/src/client/routes/**/Ceph/**'` returns `ObjectsTableView.tsx`.
- [ ] `pnpm install` (peer-dep reshuffle landed in `#1085`).
- [ ] Baseline green: `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/routers/ceph/objectRouter.test.ts`
- [ ] Read `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Swift/Objects/DeleteObjectsModal.tsx` and `Swift/Objects/index.tsx:380-506` — they are the reference for everything in Steps 5–7.

---

## Implementation Steps

### Step 1: Add the `deleteBulk` Zod schemas

**Files to modify:**
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/types/ceph.ts`

**What to do:**

1. Insert immediately after `deleteObjectInputSchema` (ends line 200), keeping the existing JSDoc comment style:

```ts
/**
 * Delete multiple objects from a bucket in one operation.
 *
 * S3's DeleteObjects accepts at most 1000 keys per request; larger selections are
 * chunked server-side (see objectRouter.deleteBulk). Folder markers (trailing "/")
 * are rejected: DeleteObjects removes only the zero-byte marker and would orphan
 * everything under the prefix. Folders go through objects.delete, which recurses.
 */
export const deleteObjectsBulkInputSchema = projectScopedInputSchema.extend({
  containerName: z.string().min(1),
  objectKeys: z
    .array(z.string().min(1).max(1024)) // 1024 = S3 max key length
    .min(1)
    .max(10000)
    .refine((keys) => keys.every((key) => !key.endsWith("/")), {
      message: "Folder keys (ending with \"/\") cannot be bulk-deleted. Use objects.delete, which deletes recursively.",
    }),
})

/** One key S3 reported as deleted. Mirrors the SDK's DeletedObject shape. */
export const deletedObjectSchema = z.object({
  key: z.string(),
  versionId: z.string().optional(),
  deleteMarker: z.boolean().optional(),
  deleteMarkerVersionId: z.string().optional(),
})

/** One key S3 refused to delete. Mirrors the SDK's Error shape. */
export const deleteObjectErrorSchema = z.object({
  key: z.string(),
  versionId: z.string().optional(),
  code: z.string().optional(),     // e.g. "AccessDenied", "InternalError"
  message: z.string().optional(),
})

/**
 * DeleteObjects returns a *mixed* result on an otherwise-successful (HTTP 200)
 * response: some keys land in Deleted, others in Errors. Both are surfaced so the
 * UI can render a per-key summary instead of a single success/failure flag.
 */
export const deleteObjectsBulkOutputSchema = z.object({
  deleted: z.array(deletedObjectSchema),
  errors: z.array(deleteObjectErrorSchema),
  deletedCount: z.number().int().nonnegative(),
  errorCount: z.number().int().nonnegative(),
})
```

2. Add to the exported-types block (after line 274):

```ts
export type DeleteObjectsBulkInput = z.infer<typeof deleteObjectsBulkInputSchema>
export type DeletedObject = z.infer<typeof deletedObjectSchema>
export type DeleteObjectError = z.infer<typeof deleteObjectErrorSchema>
export type DeleteObjectsBulkOutput = z.infer<typeof deleteObjectsBulkOutputSchema>
```

**Expected outcome:** Schemas compile; `DeleteObjectsBulkOutput` is importable by both server and client (the client imports server types directly — see `ObjectsTableView.tsx:21`).

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck`

---

### Step 2: Implement `objects.deleteBulk`

**Files to modify:**
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/objectRouter.ts`

**What to do:**

1. Extend the type import block (lines 14–33) with `deleteObjectsBulkInputSchema`, `deleteObjectsBulkOutputSchema`, `type DeleteObjectsBulkOutput`, `type DeletedObject`, `type DeleteObjectError`. `DeleteObjectsCommand` is already imported (line 5); `S3_MAX_KEYS_PER_REQUEST` already imported (line 34).

2. Insert a new `deleteBulk` procedure **after `delete`** (which ends at line 599) and **before `createFolder`** (line 601), with a JSDoc in the file's existing voice covering: chunking, the mixed Deleted/Errors semantics, folder rejection, and idempotency of missing keys.

3. Implementation shape:

```ts
deleteBulk: cephProtectedProcedure
  .input(deleteObjectsBulkInputSchema)
  .mutation(async ({ ctx, input }): Promise<DeleteObjectsBulkOutput> => {
    const s3 = ctx.getCephClient!()
    const { containerName, objectKeys } = input

    // De-duplicate: S3 tolerates repeats but would report the same key twice,
    // inflating deletedCount and confusing the UI summary.
    const uniqueKeys = [...new Set(objectKeys)]

    const deleted: DeletedObject[] = []
    const errors: DeleteObjectError[] = []

    for (let offset = 0; offset < uniqueKeys.length; offset += S3_MAX_KEYS_PER_REQUEST) {
      if (ctx.req.signal?.aborted) break        // client navigated away / cancelled
      const chunk = uniqueKeys.slice(offset, offset + S3_MAX_KEYS_PER_REQUEST)

      try {
        const response = await s3.send(
          new DeleteObjectsCommand({
            Bucket: containerName,
            Delete: { Objects: chunk.map((Key) => ({ Key })), Quiet: false },
          }),
          { abortSignal: ctx.req.signal }
        )

        for (const d of response.Deleted ?? []) {
          deleted.push({
            key: d.Key ?? "",
            versionId: d.VersionId,
            deleteMarker: d.DeleteMarker,
            deleteMarkerVersionId: d.DeleteMarkerVersionId,
          })
        }
        for (const e of response.Errors ?? []) {
          errors.push({ key: e.Key ?? "", versionId: e.VersionId, code: e.Code, message: e.Message })
        }
      } catch (error) {
        // Nothing deleted yet → the failure is systemic (bad bucket, denied
        // credentials). Surface it as a normal tRPC error rather than as 1000
        // identical per-key errors.
        if (deleted.length === 0 && errors.length === 0) {
          throw mapS3ErrorToTRPCError(error, { operation: "delete objects", bucket: containerName })
        }
        // Otherwise degrade: earlier chunks really were deleted, so keep the
        // partial result and report this chunk's keys as failures.
        const message = error instanceof Error ? error.message : String(error)
        for (const key of chunk) errors.push({ key, code: "RequestFailed", message })
      }
    }

    return deleteObjectsBulkOutputSchema.parse({
      deleted,
      errors,
      deletedCount: deleted.length,
      errorCount: errors.length,
    })
  }),
```

4. Do **not** add `console.log` noise (the surrounding `deleteAll` has plenty; don't copy that).

5. No change needed in `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/index.ts` — `objectRouter` is spread at line 19.

**Expected outcome:** `trpcReact.storage.ceph.objects.deleteBulk` is typed end-to-end on the client.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck`; the client's `trpcClient` autocompletes the new procedure.

---

### Step 3: Server tests for `deleteBulk`

**Files to modify:**
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/objectRouter.test.ts`

**What to do:** Add `describe("objects.deleteBulk", …)` after the `objects.delete` block (ends ~line 683), following the existing `mockSend` / `createCaller` / `createMockContext()` conventions (file header lines 1–30). Cases:

1. **All succeed** — `mockSend` resolves `{ Deleted: [{Key:"a.txt"},{Key:"b.txt"}], $metadata:{httpStatusCode:200} }`; assert `{ deletedCount: 2, errorCount: 0 }` and that `DeleteObjectsCommand` was built with `Bucket` + `Delete.Objects` in key order.
2. **⚠️ Partial failure in one 200 response** — resolves `{ Deleted:[{Key:"a.txt"}], Errors:[{Key:"b.txt", Code:"AccessDenied", Message:"Access Denied"}] }`; assert `deletedCount === 1`, `errorCount === 1`, `errors[0].code === "AccessDenied"`. **This is the core test.**
3. **Chunking** — 1500 keys → `mockSend` called twice, first with 1000 `Delete.Objects`, second with 500; results aggregated (`deletedCount === 1500`).
4. **Systemic failure on first chunk** — `mockSend` rejects with `{ Code: "NoSuchBucket" }` → `rejects.toMatchObject({ code: "NOT_FOUND" })`; and with `{ Code: "AccessDenied" }` → `FORBIDDEN`.
5. **Degraded failure on a later chunk** — first `send` resolves 1000 deletes, second rejects → resolves with `deletedCount === 1000`, `errorCount === 500`, all with `code === "RequestFailed"`.
6. **Duplicate keys de-duplicated** — `["a.txt","a.txt"]` → one entry in `Delete.Objects`.
7. **Schema rejections** — `objectKeys: []` rejects; `objectKeys: ["photos/"]` rejects with the folder message; 10001 keys rejects.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/routers/ceph/objectRouter.test.ts`

---

### Step 4: Add bulk-delete toasts

**Files to modify:**
- `.../Ceph/Objects/ObjectToastNotifications.tsx`
- `.../Ceph/Objects/ObjectToastNotifications.test.tsx`

(both under `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/`)

**What to do:** Add three factories in the file's existing style (`{ message: ReactNode } & NotificationOptions`, `<Trans>` for everything), under a new `// ── Bulk object delete ───` banner after the single-object delete section (ends ~line 49):

```tsx
export const getObjectsBulkDeletedToast = (deletedCount: number): { message: ReactNode } & NotificationOptions => ({
  message: <Trans>Objects Deleted</Trans>,
  description: <Plural value={deletedCount} one="# object was deleted." other="# objects were deleted." />,
})

export const getObjectsBulkDeletePartialToast = (
  deletedCount: number,
  errorCount: number
): { message: ReactNode } & NotificationOptions => ({
  message: <Trans>Some Objects Could Not Be Deleted</Trans>,
  description: <Trans>{deletedCount} deleted, {errorCount} failed. See the details in the dialog.</Trans>,
})

export const getObjectsBulkDeleteErrorToast = (errorMessage: string): { message: ReactNode } & NotificationOptions => ({
  message: <Trans>Failed to Delete Objects</Trans>,
  description: <Trans>No objects were deleted: {errorMessage}</Trans>,
})
```

Import `Plural` from `@lingui/react/macro` alongside the existing `Trans`.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Objects/ObjectToastNotifications.test.tsx`

---

### Step 5: Create `DeleteObjectsModal.tsx` (confirm + results summary)

**Files to create:**
- `.../Ceph/Objects/DeleteObjectsModal.tsx`
- `.../Ceph/Objects/DeleteObjectsModal.test.tsx`

**Props:**

```ts
interface DeleteObjectsModalProps {
  bucketName: string
  objectKeys: string[]        // full keys, e.g. "photos/2024/img.jpg"
  currentPrefix: string       // used to derive display names
  versioningEnabled?: boolean
  isOpen: boolean
  onClose: () => void
  /** Fired once the mutation settles, with the keys S3 confirmed deleted. */
  onDeleted: (deletedKeys: string[], errorCount: number) => void
  /** Fired when the whole call failed (tRPC error, nothing deleted). */
  onError: (errorMessage: string) => void
}
```

**What to do:**

1. Model the file on `DeleteObjectModal.tsx` (imports, `useProjectId`, `useModalTracking`, `<Modal>` props, `Stack direction="vertical" gap="4"`).
2. `useModalTracking({ isOpen, actionPrefix: "storage.ceph.objects.delete_bulk" })` (plural resource, matching `storage.ceph.buckets.empty`).
3. Local state: `const [confirmText, setConfirmText] = useState("")` and `const [result, setResult] = useState<DeleteObjectsBulkOutput | null>(null)`.
4. Mutation:

```ts
const deleteBulkMutation = trpcReact.storage.ceph.objects.deleteBulk.useMutation({
  onSuccess: (res) => {
    utils.storage.ceph.objects.list.invalidate()
    utils.storage.ceph.containers.list.invalidate()
    onDeleted(res.deleted.map((d) => d.key), res.errorCount)
    if (res.errorCount === 0) handleClose()   // full success: close, parent toasts
    else setResult(res)                        // partial: stay open, show summary
  },
  onError: (error) => onError(error.message),
})
```
Note the invalidations mirror `DeleteObjectModal.tsx:44-45` exactly.

5. **Step A — confirm view** (`result === null`):
   - `<Modal title={<Plural value={count} one="Delete # Object" other="Delete # Objects" />} size="large" confirmButtonVariant="primary-danger" …>`
   - `<Message variant="danger">` with versioning-aware copy: `versioningEnabled ? <Trans>The selected objects will be marked as deleted and can be restored from version history.</Trans> : <Trans>The selected objects will be permanently deleted. This cannot be undone.</Trans>`
   - Scrollable key list (`max-h-48 overflow-y-auto`), first **20** display names (`objectKey.replace(currentPrefix,"")`), then `<Trans>… and {hiddenCount} more</Trans>`.
   - `<TextInput label={t\`Type DELETE to confirm\`} … />`; confirm disabled unless `confirmText === "DELETE"` or `isPending`.
   - Confirm handler: `markSubmitted()`, then `mutate({ project_id: projectId, containerName: bucketName, objectKeys })`.
   - `disableCancelButton` / `disableCloseButton` while pending (mirrors `DeleteObjectModal.tsx:90-91`).

6. **Step B — results view** (`result !== null`):
   - Title `<Trans>Delete Results</Trans>`; hide the destructive confirm button, show a single close action (`confirmButtonLabel={t\`Done\`}`, `onConfirm={handleClose}`).
   - Summary line: `<Trans>{result.deletedCount} deleted, {result.errorCount} failed.</Trans>`
   - Failure table: for each `result.errors`, one row with the display name (`title` = full key, `[overflow-wrap:anywhere]` like `DeleteObjectModal.tsx:94`) and `{e.code}{e.message ? ": " + e.message : ""}`. Cap the rendered list at 100 with `<Trans>… and {n} more failures</Trans>` so a 10 000-key disaster doesn't lock the browser.
7. `handleClose()` resets `confirmText`, `result`, `deleteBulkMutation.reset()`, `resetTracking()`, then `onClose()`.
8. Guard: `if (!isOpen || objectKeys.length === 0) return null` (Swift does this at `DeleteObjectsModal.tsx:99`).

**Expected outcome:** Modal usable standalone; renders both steps; every string translated.

**Verification:** `DeleteObjectsModal.test.tsx` — see Testing Plan.

---

### Step 6: Add the selection column to `ObjectsTableView`

**Files to modify:**
- `.../Ceph/Objects/ObjectsTableView.tsx`
- `.../Ceph/Objects/ObjectsTableView.test.tsx`

**What to do:**

1. Replace the single template constant (line 112) with two, mirroring `Swift/Objects/ObjectsTableView.tsx:74-76`:

```ts
const GRID_COLUMN_TEMPLATE_WITH_SELECT = "40px minmax(200px, 3fr) minmax(100px, 1fr) minmax(180px, 2fr) 60px"
const GRID_COLUMN_TEMPLATE_NO_SELECT = "minmax(200px, 3fr) minmax(100px, 1fr) minmax(180px, 2fr) 60px"
```

2. Add props to `ObjectsTableViewProps` (after line 133):

```ts
  /** When false the checkbox column is dropped entirely (versions tab, no bulk perms). */
  selectable?: boolean
  selectedKeys?: string[]
  onToggleSelectKey?: (objectKey: string) => void
```
Default `selectable = false`, `selectedKeys = []` in the destructure so **no existing caller breaks** 🔴 (`ObjectBrowserView.tsx:544` is the only caller; tests construct props directly).

3. Derive once, next to `isAnyDownloading`-style locals:
```ts
const showSelection = selectable && !showingVersions
const gridColumnTemplate = showSelection ? GRID_COLUMN_TEMPLATE_WITH_SELECT : GRID_COLUMN_TEMPLATE_NO_SELECT
const columnCount = showSelection ? 5 : 4
```

4. Use `gridColumnTemplate` / `columnCount` in **three** places: the empty-state `<DataGrid columns={4}>` (line 296) and its `colSpan` (310), the header `<DataGrid …>` (338), and the row `<div style={{ gridTemplateColumns: … }}>` (395). When `showSelection`, add a leading `<DataGridHeadCell><span className="sr-only"><Trans>Select</Trans></span></DataGridHeadCell>` to the header row and a leading empty head cell in the empty state.

5. In the row body (inside `virtualItems.map`, before the Name cell at line ~400), add:

```tsx
{showSelection && (
  <DataGridCell onClick={(e) => e.stopPropagation()}>
    {row.kind === "object" ? (
      <Checkbox
        checked={selectedKeys.includes(row.key)}
        disabled={isStreaming}
        onChange={() => onToggleSelectKey?.(row.key)}
        aria-label={t`Select ${row.displayName}`}
        data-testid={`select-object-${row.key}`}
      />
    ) : (
      <Tooltip triggerEvent="hover" placement="right">
        <TooltipTrigger>
          <Checkbox disabled aria-label={t`Folders cannot be bulk-deleted. Use the row menu to delete a folder.`} data-testid={`select-folder-disabled-${row.kind === "folder" ? row.prefix : row.key}`} />
        </TooltipTrigger>
        <TooltipContent>
          <Trans>Folders cannot be bulk-deleted. Use the row menu to delete a folder.</Trans>
        </TooltipContent>
      </Tooltip>
    )}
  </DataGridCell>
)}
```
Add `Checkbox`, `Tooltip`, `TooltipTrigger`, `TooltipContent` to the `@cloudoperators/juno-ui-components` import (line 3–15).

6. ⚠️ Do **not** touch `useVirtualizedTableBody`, `measureElement`, or `key={…}` on the row div. Selection is a cell, nothing more.

**Expected outcome:** With `selectable={false}` (default) the table renders byte-identically to today.

**Verification:** existing `ObjectsTableView.test.tsx` (676 lines) passes untouched; new selection tests added in Step 9.

---

### Step 7: Wire selection + bulk action into `ObjectBrowserView`

**Files to modify:**
- `.../Ceph/Objects/ObjectBrowserView.tsx`
- `.../Ceph/Objects/ObjectBrowserView.test.tsx`

**What to do:**

1. Imports: add `Checkbox`, `PopupMenu`, `PopupMenuItem`, `PopupMenuOptions`, `PopupMenuToggle` to the juno import (lines 3–13); `import { plural } from "@lingui/core/macro"`; `import { DeleteObjectsModal } from "./DeleteObjectsModal"`; the three new toast factories; and pull `i18n` out of `useLingui()` (line 56 → `const { t, i18n } = useLingui()`).

2. State, next to the other modal flags (after line 78):
```ts
const [selectedKeys, setSelectedKeys] = useState<string[]>([])
const [isDeleteObjectsModalOpen, setIsDeleteObjectsModalOpen] = useState(false)

// TODO(perms): wire to storage.canUser({ permission: "storage:objects:delete" })
// instead of hardcoding — mirrors the Swift objects list.
const hasAnyBulkAction = true
```

3. Clear selection wherever the visible set changes:
   - inside the tab-reset effect (96–103): `setSelectedKeys([])`
   - inside `navigateToPrefix` (183) and `navigateToBuckets` (200)

4. Derived values, next to the other derived locals (after `sortedFolders`, line 372):
```ts
const showSelection = hasAnyBulkAction && tab !== "deleted"
const selectableKeys = sortedObjects.map((o) => o.key)          // folders excluded by construction
const allSelected = selectableKeys.length > 0 && selectableKeys.every((k) => selectedKeys.includes(k))
const someSelected = selectableKeys.some((k) => selectedKeys.includes(k))
const selectedCount = selectedKeys.length

const handleToggleSelectKey = (key: string) =>
  setSelectedKeys((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]))

const handleToggleSelectAll = () =>
  setSelectedKeys((prev) =>
    allSelected ? prev.filter((k) => !selectableKeys.includes(k)) : [...new Set([...prev, ...selectableKeys])]
  )
```
(Select-all operates on the **filtered+sorted** set, matching `Swift/Objects/index.tsx:388-400`.)

5. **Zone 4 toolbar** (`ObjectBrowserView.tsx:520-535`): the `<Stack distribution="between">` currently holds only the item count. Add the bulk-action group as the *first* child so it sits left of the count:

```tsx
{showSelection ? (
  <Stack gap="2" alignment="center">
    <Checkbox
      checked={allSelected}
      indeterminate={someSelected && !allSelected}
      onChange={handleToggleSelectAll}
      aria-label={t`Select all objects`}
      data-testid="select-all-objects"
    />
    <PopupMenu className="flex items-center">
      <PopupMenuToggle as="div">
        <Button disabled={selectedCount === 0} size="small" icon="moreVert" label={t`Actions`} />
      </PopupMenuToggle>
      {selectedCount > 0 && (
        <PopupMenuOptions>
          <PopupMenuItem
            label={i18n._(plural(selectedCount, { one: "Delete # Object", other: "Delete # Objects" }))}
            onClick={() => setIsDeleteObjectsModalOpen(true)}
            data-testid="bulk-delete-action"
          />
        </PopupMenuOptions>
      )}
    </PopupMenu>
  </Stack>
) : (
  <span />
)}
```

6. Pass the new props at the `<ObjectsTableView>` call site (544):
```tsx
selectable={showSelection}
selectedKeys={selectedKeys}
onToggleSelectKey={handleToggleSelectKey}
```

7. Render the modal alongside the other modals (after `<CreateFolderModal>` at 600). `versioningStatus` is **not** a new fetch — it's an existing local already declared at `ObjectBrowserView.tsx:106` (`trpcReact.storage.ceph.versioning.getStatus.useQuery(...)`), and `versioningEnabled={versioningStatus?.status === "Enabled"}` is the exact expression already passed to `<ObjectsTableView>` at line 551 today — reuse both as-is, don't refetch or redefine:
```tsx
<DeleteObjectsModal
  bucketName={bucketName}
  objectKeys={selectedKeys}
  currentPrefix={currentPrefix}
  versioningEnabled={versioningStatus?.status === "Enabled"}
  isOpen={isDeleteObjectsModalOpen}
  onClose={() => setIsDeleteObjectsModalOpen(false)}
  onDeleted={handleBulkDeleted}
  onError={handleBulkDeleteError}
/>
```

8. Handlers — **including the pagination reset** called out in the risk table:
```tsx
const resetAccumulatedObjects = () => {
  setContinuationToken(undefined)
  setKeyMarker(undefined)
  setVersionIdMarker(undefined)
  setAllObjects([])
  setAllFolders([])
  setHasMore(false)
}

const handleBulkDeleted = (deletedKeys: string[], errorCount: number) => {
  // The list accumulates pages; a plain invalidate would refetch only the last
  // page and append it. Drop the accumulator so the refetch rebuilds page 1.
  resetAccumulatedObjects()
  setSelectedKeys((prev) => prev.filter((k) => !deletedKeys.includes(k)))
  if (errorCount === 0) {
    const { message, ...options } = getObjectsBulkDeletedToast(deletedKeys.length)
    toast.success(message, options)
  } else {
    const { message, ...options } = getObjectsBulkDeletePartialToast(deletedKeys.length, errorCount)
    toast.warning(message, options)
  }
}

const handleBulkDeleteError = (errorMessage: string) => {
  const { message, ...options } = getObjectsBulkDeleteErrorToast(errorMessage)
  toast.error(message, options)
}
```

**Expected outcome:** Checkbox column appears on the "All" tab, select-all + Actions menu work, delete flow round-trips, list refreshes correctly, selection prunes on partial failure.

**Verification:** manual run (see Testing Plan) + Step 9 tests.

---

### Step 8: Client tests

**Files to modify/create:**
- `.../Ceph/Objects/ObjectsTableView.test.tsx` (extend)
- `.../Ceph/Objects/ObjectBrowserView.test.tsx` (extend)
- `.../Ceph/Objects/DeleteObjectsModal.test.tsx` (new)

**What to do:**

`ObjectsTableView.test.tsx` — add a `describe("selection")` block. The file already mocks `@tanstack/react-virtual` (lines 87–100), `useProjectId`, `trpcClient`, the download store, and each child modal; reuse them as-is.
- default (`selectable` omitted) renders no `select-object-*` checkbox and the header keeps 3 labelled columns
- `selectable` + object rows → `select-object-file1.txt` present and unchecked; `selectedKeys={["file1.txt"]}` → checked
- clicking a checkbox calls `onToggleSelectKey` with the **full key**, once
- folder rows render `select-folder-disabled-documents/` in the disabled state
- `showingVersions` forces the column off even with `selectable`
- a row with an active transfer (`setActiveTransfer(...)`, helper at test line ~137) has a disabled checkbox

`DeleteObjectsModal.test.tsx` — mock `trpcReact` with a controllable `useMutation` (copy the mocking style used in the sibling `DeleteObjectModal.test.tsx`).
- renders `Delete 3 Objects`, lists display names, truncates past 20 with "… and N more"
- confirm disabled until `DELETE` typed
- confirm calls `mutate` with `{ project_id, containerName, objectKeys }`
- **all-success** → `onDeleted(keys, 0)` and modal closes
- **partial** (`{ deleted:[a], errors:[{key:b, code:"AccessDenied"}], deletedCount:1, errorCount:1 }`) → modal stays open, shows `1 deleted, 1 failed`, shows `AccessDenied`, and `onDeleted([a], 1)` fired
- **tRPC error** → `onError(message)`
- versioning copy switches on `versioningEnabled`

`ObjectBrowserView.test.tsx`
- select-all checkbox toggles all object rows and goes indeterminate on a partial selection
- Actions button disabled with zero selection; label pluralizes ("Delete 1 Object" / "Delete 2 Objects")
- selection clears on prefix navigation and on tab switch
- select-all/Actions hidden when `tab === "deleted"`

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Objects`

---

### Step 9: i18n, changeset, full gate

**Files:** `packages/aurora/src/locales/{en,de}/messages.po` (regenerated), `.changeset/<name>.md` (new)

**What to do:**

1. `pnpm --filter @cobaltcore-dev/aurora check-i18n` → runs `lingui extract --clean && lingui compile`. **Commit the regenerated catalogs.** Note `--clean` prunes obsolete entries, so review the diff: only additions related to this feature plus removals from unrelated churn should appear (if unrelated removals show up, you're not rebased on main).
2. Sanity-grep for unwrapped copy in the new/changed files: every human-readable string must be inside `<Trans>`, `t\`\``, `<Plural>`, or `plural()`. `aria-label`/`title`/`placeholder`/`label` props included.
3. German catalog: new msgids land untranslated — that's the repo norm (CI only checks extract/compile), don't hand-translate.
4. Add a changeset (`.changeset/` already holds `cool-tools-tie.md` etc.): `@cobaltcore-dev/aurora` → **minor**, description e.g. "Add bulk object delete for Ceph (S3) buckets: `objects.deleteBulk` with per-key partial-failure reporting, plus multi-select and a results summary in the object browser."
5. Full local gate, matching `.github/workflows/ci-checks.yaml`:
```bash
pnpm --filter @cobaltcore-dev/aurora typecheck
pnpm --filter @cobaltcore-dev/aurora lint
pnpm --filter @cobaltcore-dev/aurora test
pnpm check-i18n
pnpm format:check
pnpm build
```
6. Commit style: `feat(portal): add bulk object delete for Ceph (S3) buckets` (`type(scope)` from `commitlint.config.mjs`; the Ceph object-browser commits on main use `portal`, e.g. `#1086`/`#1090`).

---

## Testing Plan

**Unit tests (server) — `objectRouter.test.ts`**
- [ ] all-success → correct counts + command shape
- [ ] **mixed `Deleted`/`Errors` in one 200 response** → both surfaced, counts correct
- [ ] 1500 keys → two `DeleteObjectsCommand` sends (1000 + 500), aggregated result
- [ ] first-chunk rejection → `NOT_FOUND` (NoSuchBucket) / `FORBIDDEN` (AccessDenied)
- [ ] later-chunk rejection → partial result preserved, chunk keys reported as `RequestFailed`
- [ ] duplicate keys collapsed
- [ ] schema: empty array, >10000 keys, and any trailing-`/` key all rejected

**Unit tests (client)**
- [ ] `ObjectsTableView`: column present/absent, checked state, toggle callback, folder disabled, versions-tab off, streaming-row disabled
- [ ] `DeleteObjectsModal`: type-to-confirm gate, mutate payload, success close, **partial → results summary rendered**, tRPC error path, versioning copy
- [ ] `ObjectBrowserView`: select-all/indeterminate, action label pluralization, selection cleared on navigation + tab switch, hidden on deleted tab
- [ ] `ObjectToastNotifications`: three new factories

**Integration / manual verification** (`pnpm dev`, real Ceph project, `/projects/<id>/storage/<provider>/<type>/<bucket>/objects`)
1. Select 2 objects → Actions → "Delete 2 Objects" → type `DELETE` → confirm. Both vanish; success toast reads "2 objects were deleted."
2. Select-all with folders present → folder checkboxes are disabled with a tooltip; only objects are counted.
3. Deep folder + "Load More" (>1000 objects), select-all, delete → verify **no duplicate/ghost rows** after the list refreshes (the pagination-reset fix) and that the BFF issues 2 `DeleteObjects` calls.
4. Partial failure: apply a bucket policy denying `s3:DeleteObject` on one prefix, select objects from both prefixes → modal switches to the results view showing the deleted count and the failed key with `AccessDenied`; the selection retains only the failed key.
5. Versioned bucket: delete selected, switch to the **Deleted** tab → objects appear as restorable; confirm the bulk toolbar is **not** shown on that tab.
6. Navigate into a folder mid-selection → selection clears.
7. Switch language to German (catalog untranslated) → no crashes, English fallback strings.

---

## Acceptance Criteria

- [ ] `storage.ceph.objects.deleteBulk` exists, is `cephProtectedProcedure`, accepts `{ project_id, containerName, objectKeys }` and returns `{ deleted, errors, deletedCount, errorCount }`
- [ ] A single S3 response containing both `Deleted` and `Errors` is reported faithfully — never collapsed into a boolean
- [ ] Selections >1000 keys work (server-side chunking); >10000 are rejected by the schema
- [ ] Folder keys are rejected server-side and unselectable client-side
- [ ] The object browser has a checkbox column, a select-all with indeterminate state, and a "Delete N Object(s)" action gated on a non-empty selection
- [ ] Partial failures render a per-key results summary inside the modal; full success closes the modal and toasts a count
- [ ] The list refreshes correctly after deletion, including after "Load More" (no duplicated or ghost rows)
- [ ] Selection clears on folder navigation, tab switch, and full-success delete; prunes to failures only on partial success
- [ ] Bulk UI is absent on the "Deleted" (versions) tab; version rows are never selectable
- [ ] Rendering with `selectable` unset is byte-identical to today — no regressions to single-object delete, copy/move, metadata, download/upload, or version restore
- [ ] Every new user-facing string is wrapped for Lingui; regenerated catalogs committed
- [ ] `pnpm --filter @cobaltcore-dev/aurora typecheck|lint|test`, `pnpm check-i18n`, `pnpm format:check`, `pnpm build` all pass
- [ ] A `@cobaltcore-dev/aurora` **minor** changeset is included

---

## Open Questions — resolved by user (2026-07-27)

All four items below were open questions in the original plan. The user has now decided all four; nothing in this section is still open. See "Follow-up Tasks" below for the two items that turned into deferred, separately-scoped work rather than being folded into Steps 1–9.

1. **Bulk delete of specific versions** — deliberately out of scope for Steps 1–9 (D8 unchanged). **Decision: build it, but only as a follow-up task after regular bulk object delete (this plan) ships.** Do not start it in parallel or fold it into Step 2/6/7 — it needs its own schema/UI design pass once the base feature is stable. See **Follow-up A** below.
2. **Recursive bulk delete of folders** — **Decision: do exactly what Swift does.** Swift's own `ObjectsTableView.tsx` already disables the checkbox on folder rows with a tooltip (see Architecture Analysis, "Current state — the reference implementation already in the repo (Swift)") — it does **not** recursively expand folders for bulk delete either. So D4 (folder keys rejected server-side, disabled checkbox client-side) already matches Swift exactly and needs no change. This is not deferred work, it's confirmed-as-is: there is no recursive-folder-bulk-delete feature to build, in Swift or in Ceph.
3. **Permission gating** — **Decision: no, out of scope entirely for now.** Do not add real `canUser`/permission-router checks for bulk delete (or single delete) in this plan. This will become its own separate future feature covering permissions for **all** of Ceph (not just bulk delete — single delete, copy, move, bucket policy, versioning, CORS, etc.), so gating just this one action here would pre-empt and conflict with that broader design. D9's `hasAnyBulkAction = true` + `TODO(perms)` placeholder stays exactly as written. See **Follow-up B** below.
4. **Progress feedback for very large selections** — **Decision: do exactly what Swift does.** Swift's `bulkDelete` (`swiftRouter.ts:822`) is a single request/response with no progress subscription — the client waits behind a spinner and only sees results once the whole call resolves. Do **not** build an `EventEmitter`/`watchXProgress`-style progress subscription for `deleteBulk` (unlike `downloadObject`/`uploadObject`, which do have one) — Step 2's sequential per-chunk loop with a plain pending/spinner state on the modal (as already written in Step 5) is the final design, not an interim one. This removes the `EventEmitter` consideration entirely from scope; no plan changes needed elsewhere since Steps 1–9 never assumed it.

## Follow-up Tasks (separate, after this plan ships — not part of Steps 1–9)

### Follow-up A: Bulk delete of specific object versions (Deleted/versions tab)

Scope this as its own task once `objects.deleteBulk` (Steps 1–9 above) is implemented, tested, and merged. Sketch, to save the next planning pass some groundwork:

- **BFF:** either a new `deleteVersionsBulk` procedure or an optional-`versionId` variant of `deleteBulk` — needs a decision at that time on whether to extend the existing schema (`objectKeys: {key, versionId?}[]` instead of `string[]`) or add a parallel procedure. `DeleteObjectsCommand` already supports `{Key, VersionId}` pairs, so the underlying S3 call is a small variation of Step 2's implementation, not a new mechanism.
- **UI:** the "Deleted" tab currently has no selection UI at all (D8/Step 7 explicitly keep `showSelection = hasAnyBulkAction && tab !== "deleted"`) — enabling it there means version rows become selectable and the toolbar/modal need to show version-aware copy ("this permanently deletes this specific version", not "moves to trash").
- Do not start this before the base feature (Steps 1–9) is done — it depends on the same schema/router/modal/table conventions being settled first, and doing both at once risks conflicting changes to the same files (`objectRouter.ts`, `ObjectsTableView.tsx`, `ObjectBrowserView.tsx`).

### Follow-up B: Ceph-wide permissions (RBAC gating for the whole Ceph object/bucket surface)

A separate future feature, out of scope for this plan and for Follow-up A. When it happens, it should cover permission gating for the whole Ceph surface in one pass rather than one action at a time — single `delete`, `copy`, `move`, `deleteBulk`, `bucketPolicy`, `versioning`, `cors`, etc. — using the existing `storage:objects:delete` key (already registered in `permissionRouter.ts`/`storage.json`) as the starting point for the delete-family actions, plus new keys for whichever of those procedures don't have one yet. Every `TODO(perms)` placeholder left by this plan (D9) and by Follow-up A should be resolved together when that feature is scoped.
