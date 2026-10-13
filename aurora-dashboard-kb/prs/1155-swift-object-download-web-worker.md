---
type: pr-report
date: 2026-08-11
status: merged
pr: [1155]
author: mark-karnaukh-extern-sap
branch: mark-swift-download-improvements
---
# PR #1155: feat(portal): offload Swift object downloads to a Web Worker

**Author:** mark-karnaukh-extern-sap · **Status:** created 2026-08-09 → merged 2026-08-13
**Branches:** `mark-swift-download-improvements` → `main` · **Files:** 15 (+1271/-548)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1155

> **Re-check 2026-08-13:** the PR head on GitHub has not moved — it is the same commit `97430ad` that was analyzed on 2026-08-11; there are no new commits. Only the discussion changed: CodeRabbit left an automated review, a Copilot review was requested (but not performed), and there are no live approvals yet; GitHub also shows "Out of Scope Changes" warnings (this concerns the changeset finding already covered below) and "Docstring Coverage 75% < 80%". CodeRabbit's points were checked against the code at `97430ad`: one was independently confirmed and added to "Review" as the first item; one (`rel="noopener,noreferrer"` with a comma) turned out to be pre-existing code inherited from Ceph and was rejected; the rest are stylistic nitpicks below the threshold (see the end of the "Review" section).

## What was done

Ports the Web Worker object download architecture, previously implemented only for Ceph (PR #1062), to Swift objects. The stated bug fix: `swift.downloadObject` never checked for request cancellation, so a download cancelled on the client kept reading the stream to the end and accumulating bytes in the worker's memory — on a large file this filled up the renderer's memory (the "STATUS_BREAKPOINT" crash mentioned in the PR description). The solution is the same one that already works for Ceph: base64→Blob decoding moves into a separate Web Worker (does not block the main thread), the state of active downloads lives in a module-level store outside React (survives the table unmounting during folder navigation), and on the server `downloadObject` now checks `ctx.req.signal.aborted` in the read loop and does not emit `:complete` for an aborted download.

In the course of implementation the PR corrected itself: commit `7ece064` ("keep Swift and Ceph download worker/store in parity") added two guards on `abortController.signal.aborted` to the already existing Ceph worker, which were missing there — i.e. the Swift version was originally written more strictly than the Ceph original, and this mismatch was resolved by back-porting into Ceph.

## How it is implemented

### Web Worker + module-scope store (new for Swift)

`.../Swift/Objects/workers/objectDownload.worker.ts` (129 lines, `?worker&inline`) — an almost exact copy of the Ceph worker; it decodes base64 chunks into `Uint8Array` off the main thread and assembles a `Blob` at the end:

```ts
// objectDownload.worker.ts:21-25
// Cancellation: a "cancel" message aborts the AbortController passed to the tRPC
// mutation, which aborts the underlying fetch. The BFF sees the client disconnect
// and stops reading the Swift stream on its next chunk (see swiftRouter's
// downloadObject). The store drops the transfer from its state right away, so the
// UI doesn't wait on this unwinding.
```

`.../Swift/Objects/stores/objectDownloadStore.ts` (246 lines) holds a `Map<transferKey, ActiveTransfer>` outside React via `useSyncExternalStore(subscribeTransfers, getTransfersSnapshot)` — the reason is in the file's comment:

```ts
// objectDownloadStore.ts:3-9
// Why this lives outside React: ObjectBrowserView swaps ObjectsTableView out for
// a <Spinner> whenever objects.list is loading (i.e. entering an uncached
// folder). That unmounts the table — and if the table owned the workers, its
// cleanup would abort them mid-stream ("stream closed prematurely") and lose the
// progress state. Owning transfers here means a download survives folder
// navigation, spinner swaps, and even leaving the container entirely...
```

The transfer key is `container:objectKey` (`objectDownloadStore.ts:74`), with a separate toast id `"swift-object-download"` (`objectDownloadStore.ts:38`, deliberately different from the Ceph store so that the persistent toasts of the two backends do not dismiss each other).

Cancellation — `cancelObjectDownload()` (`objectDownloadStore.ts:233-245`) removes the entry from the `Map` immediately (the UI clears without waiting for the worker) and sets a safety timer:

```ts
// objectDownloadStore.ts:65-72
// How long a cancelled worker gets to report back before it is forced down.
//
// Normally it replies almost immediately — the abort rejects its `for await`,
// and the reply path terminates it. But that reply isn't guaranteed: if the
// abort ever fails to unwind the stream, the worker would keep downloading and
// buffering a file nobody wants, with no entry left in `transfers` to clean it
// up. This bounds that window.
const CANCEL_TERMINATE_GRACE_MS = 5000
```
```ts
// objectDownloadStore.ts:238-244
transfer.worker.postMessage({ type: "cancel" } satisfies DownloadWorkerRequest)
setTimeout(() => transfer.worker.terminate(), CANCEL_TERMINATE_GRACE_MS)
transfers.delete(key)
emit()
```

### ObjectsTableView.tsx — switching to per-row progress

Previously there was a single shared "something is downloading" flag; now `ObjectsTableView.tsx:140` subscribes to the whole `Map` via `useSyncExternalStore`, and each row computes its own `isStreaming` (`ObjectsTableView.tsx:307`), which controls both the per-row disabled state of the action buttons and the display of a new subcomponent:

```tsx
// ObjectsTableView.tsx:51-56
function RowTransferProgress({ downloadId, isPreviewing }: { downloadId: string; isPreviewing: boolean }) {
  const { data: progress } = trpcReact.storage.swift.watchDownloadProgress.useSubscription(
    { downloadId },
    { enabled: !!downloadId }
  )
  const percent = progress?.percent
```

The list of previewable MIME types was expanded — it used to be its own narrow list; now it delegates to the shared `isPreviewableContentType` (the same one Ceph uses: `image/*`/`video/*`/`audio/*` + `application/pdf`/`text/plain`) — a behavioral change toward parity with Ceph, not a regression, but worth knowing that this PR expanded the set of previewable types for Swift.

### ObjectToastNotifications.tsx — file name derivation moved inside

`getObjectDownloadErrorToast`/`getObjectDownloadCancelledToast` used to accept a ready-made display name; now they accept the full `objectKey` and cut the basename themselves:

```ts
// ObjectToastNotifications.tsx:88-92
export const getObjectDownloadErrorToast = (
  objectKey: string,
  errorMessage: string
): { message: ReactNode } & NotificationOptions => {
  const displayName = objectKey.split("/").filter(Boolean).pop() ?? objectKey
```

Verified: the only external caller (`index.tsx:222-224`, untouched by this PR) already passes the full `objectKey` under the parameter name `objectName` — the output behavior does not change; the name derivation simply moved from the calling code into the toast function itself.

### swiftRouter.ts — server-side abort-awareness

`downloadObject` (`swiftRouter.ts:1642-1741`) now checks the signal on every iteration of the read loop and does not emit `:complete` for an aborted stream:

```ts
// swiftRouter.ts:1687-1695
// The download worker aborts its tRPC fetch on cancel, which surfaces
// here as ctx.req.signal. Check before each read so a cancelled transfer
// stops pulling from Swift promptly, instead of streaming the whole
// object into a worker the client has already discarded...
if (ctx.req?.signal?.aborted) {
  aborted = true
  break
}
```
```ts
// swiftRouter.ts:1721-1726
// Only signal completion for a stream that actually ran to the end — an
// aborted transfer stopped at a partial byte count, and emitting
// `complete` would make watchDownloadProgress report it as finished.
if (!aborted) {
  downloadProgressEmitter.emit(`progress:${scopedDownloadId}:complete`)
}
```

### Side fix: the Ceph worker got the same abort guards

Commit `7ece064` changes `.../Ceph/Objects/workers/objectDownload.worker.ts` — an existing file from another, already merged PR (#1062) — adding exactly what the Swift worker was written with from the start:

```diff
 for await (const { chunk, contentType: ct, filename: fn } of iterable) {
+      if (abortController.signal.aborted) break
       if (ct) contentType = ct
```
```diff
+    if (abortController.signal.aborted) {
+      chunks.length = 0
+      self.postMessage({ ok: false, cancelled: true, message: "cancelled" } satisfies DownloadWorkerResponse)
+      return
+    }
+
     const blob = new Blob(chunks, { type: contentType })
```

This is a real, user-visible fix for Ceph (without it, a Ceph download cancelled right on the verge of completion could still assemble and save a Blob from partially buffered chunks) — but it is not about Swift and is not mentioned in the changeset (see "Review").

## What it affects

The entire change is internal to Swift/Objects (and, in one spot, to one file in Ceph/Objects). The blast radius was checked for every changed public name:

- `cancelObjectDownload`/`subscribeTransfers`/`getTransfersSnapshot`/`startObjectDownload` from `objectDownloadStore.ts` — consumed only inside `Swift/Objects/ObjectsTableView.tsx` and tests in the same directory. The analogous Ceph exports (untouched by this PR) are used only inside `Ceph/Objects`. There are no cross-backend consumers.
- `storage.swift.downloadObject` — the only client caller (`Swift/Objects` via the worker) and the `swiftRouter.test.ts` tests; it is separately registered in `trpcClient.ts:125` as one of two `STREAMING_PROCEDURES` (alongside `storage.ceph.objects.downloadObject`) — this registration did not change; the procedure was already streaming before the PR.
- `getObjectDownloadErrorToast`/`getObjectDownloadCancelledToast` (changed signature) — the only caller (`index.tsx:222-224`) is untouched by the PR, but passes a compatible value (the full `objectKey`), so the call remains correct without changes on its side.
- The change in `Ceph/Objects/workers/objectDownload.worker.ts` — the file is used only by `Ceph/Objects/stores/objectDownloadStore.ts`; the worker has no exports (it is a `self.addEventListener` module), so the only effect is behavioral (described above) and does not affect the contract.

None of the changed exports leave `packages/aurora` — there are no changes to the package's public API, and no consumers were found in `apps/dashboard`.

## Review

**One finding scored ≥80 confidence.** It comes first below, followed by two findings that hit just under the threshold (75/75), and the rejected ones, for completeness.

- **[80/100] An object's selection checkbox is disabled while it is being downloaded/previewed — an already selected object cannot be deselected before a bulk action.** This PR added `disabled={isStreaming}` to the row checkbox (`ObjectsTableView.tsx:353`, next to `checked={isSelected}` at `ObjectsTableView.tsx:352`) — previously this checkbox had no `disabled` attribute at all. `selectedObjects` lives in the parent (`Swift/Objects/index.tsx:170`) and is passed to `DeleteObjectsModal` in full, without filtering by `isStreaming` (`objectKeys={selectedObjects}`, `index.tsx:533`). Scenario: the user ticks an object's checkbox for bulk deletion, then (before deleting) clicks "Preview"/"Download" on it — the row goes into `isStreaming`, the checkbox is disabled, and the object cannot be deselected until the transfer finishes; a bulk deletion started at that moment will include the object being downloaded. Symmetrically: if a download is already in progress and the object accidentally ends up in the selection (e.g. via "select all"), it also cannot be removed from the selection until the transfer finishes. Independent confirmation: CodeRabbit flagged the same pattern on the PR itself ("disabled checkboxes prevent deselection during transfers, risking bulk actions on downloading objects") — verified against the code, not taken at its word.
- **[75/100] An unclosed cancellation window before the first byte: `swift.get(url)` does not receive a `signal`.** In `swiftRouter.ts:1665` the call `const response = await swift.get(url).catch(...)` does not pass `{ signal: ctx.req.signal }`, even though the same file does so for `uploadObject` (`swiftRouter.ts:1471`: `signal: ctx.req.signal`), and the Ceph counterpart passes `abortSignal: ctx.req.signal` to `GetObjectCommand` (`objectRouter.ts:1059-1071`) with an explicit comment about clicking "Cancel". The `ctx.req?.signal?.aborted` check added by this PR (`swiftRouter.ts:1687`) only fires between reads of an already open stream — if the client cancels the download before the Swift backend responds with the first byte (slow backend, file under load), the outgoing GET request will keep running to completion. This directly contradicts the PR's stated goal — to eliminate exactly this category of "the abort does not reach Swift". It fell short of 100 in the independent assessment because there is no direct reproduction (verified from the code, not from logs/traces of a real race).
- **[75/100] The changeset does not mention the Ceph-side change.** `.changeset/tough-things-mix.md` describes only the Swift part; the change in `Ceph/Objects/workers/objectDownload.worker.ts` (commit `7ece064`, a real user-visible fix of cancellation behavior — see "How it is implemented") is not reflected in the changeset. CodeRabbit on the PR itself flagged this change as "out of scope" for a PR titled around Swift.
- **[50/100, rejected as a nitpick] The abort guard in the Ceph worker (`7ece064`) is not covered by tests.** The new tests (`swiftRouter.test.ts`, `objectDownloadStore.test.ts` +385 lines, `ObjectsTableView.test.tsx`, `ObjectToastNotifications.test.tsx`) mock the worker itself (`vi.mock(".../objectDownload.worker?worker&inline", ...)`) and do not test its code directly — `objectDownload.worker.test.ts` does not exist for either Ceph or Swift anywhere in the repository. The commit message `test(portal): cover Swift object-download worker, store, and router abort` claims worker coverage that in fact does not exist. Rejected per the skill's rule — this is a claim about test coverage, not an explicit CLAUDE.md requirement.
- **[0/100, rejected] No watchdog for a "silently hung" worker outside of explicit cancellation.** `CANCEL_TERMINATE_GRACE_MS` protects only an explicit user cancellation; a worker that stopped responding without an explicit cancel (a hung read, a crash without an error message) can remain in the `Map` indefinitely. Rejected — the pattern is inherited identically from the Ceph store (this PR explicitly brings Swift to parity with Ceph), so this is pre-existing behavior, not a new problem introduced by this PR.
- **[0/100, rejected] `rel="noopener,noreferrer"` with a comma instead of a space in `openBlobInNewTab` (`objectDownloadStore.ts:97`).** CodeRabbit flagged this as a security problem: the browser parses `rel` into space-separated tokens, so a comma-separated value is recognized as neither `noopener` nor `noreferrer` — an anchor with `target="_blank"` loses its protection against `window.opener`. This is indeed the case in the PR's code, but an identical line with the same comma already exists in the Ceph store (`Ceph/Objects/stores/objectDownloadStore.ts:101`) since the merged #1062 — this PR merely copied the existing pattern for parity with Ceph rather than introducing it. Rejected per the skill's rule (pre-existing issue), although the vulnerability itself is real and deserves a separate fix in both stores at once.

CodeRabbit's other nitpick remarks on this PR (extracting the repeated basename derivation into a shared helper, `key={activeTransfer.downloadId}` on `RowTransferProgress`, `role="progressbar"`/ARIA attributes on the progress bar, extending the test for the worker's error path, reusing the real `isPreviewableContentType` in mocks instead of duplicating the allow-list) are stylistic; an independent check did not confirm the 80 threshold, so they are not broken out into separate items.

---
Analyzed: 2026-08-11, re-checked 2026-08-13 (no new commits) · commit `97430ad`
