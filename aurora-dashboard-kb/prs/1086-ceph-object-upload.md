---
type: pr-report
date: 2026-07-24
status: merged
pr: [1086]
author: mark-karnaukh-extern-sap
branch: mark-ceph-object-upload-setup
---
# PR #1086: feat(portal): add object upload for Ceph (S3) buckets

**Author:** mark-karnaukh-extern-sap · **Status:** merged 2026-07-24 (`1e9ba790`)
**Branches:** `mark-ceph-object-upload-setup` → `main` · **Files:** 12 (+1691/-10)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1086

Closes #1087.

## What was done

Before this PR, Ceph (S3) buckets could be browsed, and objects could be downloaded and managed, but new ones could not be uploaded — users had to turn to external S3 tools. The PR adds upload at parity with the existing Swift upload: a button in the object browser toolbar, a modal with drag-and-drop/file picker, live progress, cancellation, and success/cancellation/error toasts.

The implementation is literally a **port** of the existing Swift upload to S3: the server and client parts copy the structure of `swiftRouter.uploadObject`/`watchUploadProgress` and the client-side `Swift/Objects/UploadObjectModal.tsx` almost line by line, replacing the Swift specifics (the `x-upload-account` header, which Ceph does not have — this is explicitly checked by a separate test) with S3 (`PutObjectCommand`). The key architectural detail that pushed the logic into a separate procedure: `octetInputParser` (for receiving the file as a raw stream) cannot be attached to `cephProtectedProcedure`, because the latter is built on `projectScopedProcedure`, which already carries an object `project_id` input — and tRPC refuses to merge an object input with a raw-stream input ("All input parsers did not resolve to an object"). So the metadata (project id, bucket, object key, type, size, progress id) travels in `x-upload-*` headers rather than as tRPC input — the same technique the Swift upload already uses.

## How it is implemented

The new `cephUploadProcedure` (`packages/aurora/src/server/Storage/cephProcedure.ts:135-178`) is built on the base `protectedProcedure` (not `cephProtectedProcedure`) and manually rescopes the OpenStack session from the `x-upload-project-id` header:

```ts
// cephProcedure.ts:135-144
export const cephUploadProcedure = protectedProcedure.use(async function resolveCephForUpload(opts) {
  const { ctx, next } = opts
  const uploadProjectId = (ctx.req.headers["x-upload-project-id"] as string | undefined)?.trim()
  if (!uploadProjectId) {
    throw new TRPCError({ code: "BAD_REQUEST", message: "x-upload-project-id header is required for uploads" })
  }
```

The rescoped session (`scopedCtx`, not the original `ctx`) then goes both into the EC2-credentials resolution and into the returned context (`cephProcedure.ts:165-177`) — on the PR branch itself this was initially missed (the spread came from `ctx`, not `scopedCtx`); the Copilot reviewer caught the bug on the PR itself, and it was fixed in a separate commit `38bcf24` ("scope upload session to the rescoped project") before the current head — on the current code everything is correct.

`uploadObject` (`objectRouter.ts:1092-1216`) reads the metadata from the headers, validates it as non-empty strings after `trim()` (the same as, not stricter than, the `containerName`/`objectKey` Zod schemas for the other Ceph procedures in `types/ceph.ts` — not a weakening, but a match with the convention), then runs the file through a `Transform` stream that counts bytes and emits progress before handing it to `PutObjectCommand`:

```ts
// objectRouter.ts:1099-1117
const projectId = (headers["x-upload-project-id"] as string | undefined)?.trim()
const bucket = (headers["x-upload-container"] as string | undefined)?.trim()
const objectKey = (headers["x-upload-object"] as string | undefined)?.trim()
...
if (!projectId) { throw new TRPCError({ code: "BAD_REQUEST", message: "x-upload-project-id header is required" }) }
if (!bucket) { throw new TRPCError({ code: "BAD_REQUEST", message: "x-upload-container header is required" }) }
if (!objectKey) { throw new TRPCError({ code: "BAD_REQUEST", message: "x-upload-object header is required" }) }
```

`watchUploadProgress` (`objectRouter.ts:1227-...`) is an async-generator subscription; it yields a snapshot of the current progress immediately on subscription, then listens to an `EventEmitter` until completion/error or until a 30-second bounded wait (in case the upload already finished before the client managed to subscribe).

The client — `UploadObjectModal.tsx` (new file, 309 lines) — is a near-verbatim copy of `Swift/Objects/UploadObjectModal.tsx`, with `container`/`account` replaced by `bucketName` (no account — Ceph has no such concept), and calling `trpcClient.storage.ceph.objects.uploadObject.mutate` instead of `storage.swift.uploadObject`. It is wired into `ObjectBrowserView.tsx:612-631` via a new "Upload Object" toolbar button.

## What it affects

`uploadObject`/`watchUploadProgress` are correctly registered in the exported `objectRouter` (`routers/ceph/index.ts` → `routers/index.ts`) — the new procedures are actually reachable via `AuroraRouter`; nothing is missing. `cephUploadProcedure` is used only by this router — there are no external consumers. `UploadObjectModal` (Ceph) is a standalone component, not reused anywhere outside `ObjectBrowserView.tsx`; the Swift component of the same name (`Swift/Objects/UploadObjectModal.tsx`) is separate and does not conflict (different directories, different tRPC path).

Invalidating the list after upload (`utils.storage.ceph.objects.list.invalidate()`, without arguments — i.e. broadly, all list variants, not just the current bucket) is not a decision made by this PR: exactly the same pattern is used by all existing Ceph object modals (`CreateFolderModal`, `DeleteObjectModal`, `MoveObjectModal`, `EditMetadataModal`, etc.) — consistent, not a regression.

Access control: in this domain (Storage/Ceph+Swift), no object-mutation procedure performs a server-side `canUser` check internally — `canUser` (`routers/permissionRouter.ts`) exists only as a separate query for UI gating of buttons; actual authorization is fully delegated to the Keystone-scoped S3/Swift credentials at the Ceph RGW level. In this respect `uploadObject` is no different from `deleteObject`/`moveObject`/etc. — not a new gap, but the existing architecture of the domain.

## Review

The diff and history were run in parallel through bug-scan, comment-compliance, historical-context (a line-by-line comparison with the Swift original, which this PR explicitly states it copies) and prior-feedback (issue/PR comments). The following had already been found and closed on this same branch during the PR: the bug with the non-rescoped `ctx` (Copilot, fix `38bcf24`), overly narrow list invalidation (Copilot, fix `2171b5e3`), a timer leak in a test (Copilot, fix `b3bad147`), `setTimeout`→`setImmediate` (CodeRabbit, fix `4ed90c3`), and the button position (human reviewer, fix `4e80607d`, followed by approve). What follows is what that cycle did not catch.

**Found 2 issues with confidence ≥80:**

1. **Missing `error` handler on `progressTracker` — an unhandled exception crashes the entire BFF process, not just the current request.**
   `packages/aurora/src/server/Storage/routers/ceph/objectRouter.ts:1167-1172`. The error listener is attached only to `fileStream`:
   ```ts
   fileStream.on("error", (err) => {
     if (isAbortLike(err)) return
     progressTracker.destroy(err as Error)
   })
   const trackedStream = fileStream.pipe(progressTracker)
   ```
   `progressTracker.destroy(err)` emits `'error'` on `progressTracker` itself — and there is no listener on it. `trackedStream` (`=== progressTracker`) is passed directly into `PutObjectCommand({ Body: trackedStream })`; `@smithy/node-http-handler`'s `write-request-body.js` only does `body.pipe(httpRequest)` and adds no error listener there. In Node, `.pipe()` does NOT protect the source from its own unhandled `'error'`. The code comment claims: "Non-abort errors are re-emitted so they surface through PutObject and the catch block" — this is wrong: on a *non*-abort error on `fileStream` (e.g. `EPIPE`/`ETIMEDOUT`/a dropped connection on a large file — entirely realistic for gigabyte-sized uploads), the unhandled exception crashes the whole Node process instead of surfacing through `catch`. There is no global `uncaughtException` handler in `packages/aurora/src/server` — so this is a real process crash that kills the in-flight requests of all users, not just a failed upload. A live reproduction of exactly this chain (fileStream→Transform→pipe, an error without an abort code) confirms the crash.
   This exact listener is present in the Swift original that the PR states it copies (`packages/aurora/src/server/Storage/routers/swift/swiftRouter.ts:1426-1429`):
   ```ts
   progressTracker.on("error", (err) => {
     if (isAbortLike(err)) return
     trackedStream.destroy(err as Error)
   })
   ```
   In the Ceph port this block was simply not carried over.

2. **`watchUploadProgress` does not react to `ctx.req.signal` (client connection drop) — the subscription hangs for up to 30 seconds instead of terminating immediately, unlike Swift.**
   `packages/aurora/src/server/Storage/routers/ceph/objectRouter.ts:1227-1309`. For the Swift upload, this exact problem was a real bug fixed in a separate commit `665957d` ("cancellable file upload with AbortSignal propagation to Swift", #776) — before the fix the generator likewise hung on the 30-second timeout when the client dropped; after the fix the Swift version (`swiftRouter.ts:1557-1563,1597-1599`) registers `ctx.req.signal.addEventListener("abort", onAbort)` and terminates immediately. The Ceph port did not inherit this piece — `ctx.req` is available in the context (it is used right next door, in `uploadObject`), it is just not wired into `watchUploadProgress`. The PR explicitly claims the "same abort-signal wiring" as Swift — in fact it is not. (The same thing is also missing from the neighboring, already existing `watchDownloadProgress` — so this is not a new flaw specific to this PR, but a systemic gap in the Ceph module that this PR inherited instead of fixing along the way.)

**Considered but below the ≥80 threshold** (for completeness, so there is no need to search again):
- An unconditional `await setImmediate` on every chunk (`objectRouter.ts:1148-1151`) — real but small scheduling overhead (~900ms per GB in an isolated benchmark), growing with the number of concurrent uploads; not catastrophic compared to the real network transfer time of a gigabyte-sized file.
- A race between the `finally` removal of the entry from `uploadProgressMap` (`objectRouter.ts:1213-1215`) and the snapshot in `watchUploadProgress` for very fast/small uploads — real but harmless: `UploadObjectModal.tsx` relies on the resolution of `mutate()` itself, not on the subscription; at worst the progress bar will not show a percentage for a short-lived upload.
- `err.name === "AbortError"` in `UploadObjectModal.tsx:150-161` is dead code (`TRPCClientError` always has `name === "TRPCClientError"`), but actual cancellation detection currently works via the neighboring fallback on the substring `"aborted"` in the message, which empirically catches a real abort. Not broken right now, but fragile (it relies on the message text rather than the error structure).
- `x-upload-size` validation: `Number.isFinite(fileSize) && fileSize >= 0` lets fractional values through (`"1024.5"`), whereas Swift uses `Number.isInteger`. Low impact.

---
Analyzed: 2026-07-24 · commit `4e80607dacd`
