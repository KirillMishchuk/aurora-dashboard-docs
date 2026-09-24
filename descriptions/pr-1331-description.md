# Summary

Fixes the "Delete Versions" bucket action, which permanently deleted **every** object in the bucket instead of only its non-current versions and delete markers: it called the same full-wipe `emptyBucket` mutation as "Empty Bucket" with `includeVersionsAndDeleteMarkers: true`.

Replaces the unbounded server-side version scans behind the deleted-content indicators with a single bounded scan (20 pages × 1000 keys), and moves bucket-state detection ("is it empty", "does it have old versions") from three truncation-prone client-side probes into one authoritative server procedure. Where a scan cannot be completed, the result says so (`isPartialScan` / `isPartial`) instead of guessing a value.

# Changes Made

## Server Procedures

### New `storage.ceph.objects.deleteNonCurrentVersions`

Replaces the "Delete Versions" implementation that called the full-wipe `emptyBucket` mutation. Performs a single paginated scan of the bucket's version history and:

- keeps the current version of every key that is a real object;
- removes the whole key group, delete marker included, when the current record is a delete marker;
- defers the page's last key group until the key is fully read — S3 recomputes `IsLatest` per listing request, so a group split across pages cannot be judged from one page;
- caps how many records one key may buffer (`S3_MAX_BUFFERED_VERSIONS_PER_KEY`) so a heavily rewritten key cannot grow the BFF heap without bound;
- reports per-key failures instead of silently succeeding, returning `{ deletedCount, errorCount, errors, isPartial }`.

### New `storage.ceph.containers.getState`

Authoritative bucket state in one call, replacing three independent client-side probes:

- `status` — the raw three-way `"Enabled" | "Suspended" | "Unversioned"`, alongside the collapsed `isVersioningEnabled`, so the bucket header no longer needs a second `GetBucketVersioning`;
- `isEmpty` — from a dedicated one-key `ListObjectsV2`, exact on a bucket of any size and never affected by `isPartialScan`;
- `hasOldVersionsOrDeleteMarkers` / `hasOnlyDeleteMarkers` — from a bounded version scan, with an early return on unversioned buckets that skips the scan entirely;
- `isPartialScan` — set when the ceiling was reached, when the run was aborted, or when a truncated page carried no continuation marker (stopping is mandatory there, but it is a stop, not a completed scan); `hasOnlyDeleteMarkers` is forced to `false` under it, because a truncated scan cannot tell "no real versions exist" from "none seen yet".

### Updated `storage.ceph.versioning.checkDeletedContent`

- One paginated scan of the parent `prefix` instead of N unbounded per-folder scans running in parallel. The previous early-exit required the folder's own marker to be deleted, so for a live folder it never fired and a full scan of the prefix was the normal case, not the worst one.
- Accepts a new optional `prefix` input; `folders` stays optional and its cap is raised from 100 to 1000. The client now sends the prefix alone, which also keeps the query key stable across "Load more" — the old `folders`-keyed input restarted the whole scan on every page, and an uncut list of more than 100 folders was rejected outright, silently killing the indicators.
- Honours `ctx.req.signal` and pages at the standard `S3_MAX_KEYS_PER_REQUEST` instead of a hardcoded 100.
- Returns a per-folder `isPartialScan` instead of guessing completeness. A truncated page with no continuation marker reports the greatest key that page actually delivered as the stop point, rather than claiming the scan ran to the end — folders sorting entirely before it stay honestly covered, and the folder holding that key does not, since its range may continue on the page that never arrived.
- Surfaces S3 errors as tRPC errors; the previous empty `catch` swallowed `AccessDenied`, throttling and timeouts alike and reported "no deleted content".

## Core Infrastructure

- **`helpers/versionScan.ts`** (new) — pure helpers for attributing keys to child folders during a delimiter-less prefix scan: `folderPrefixOf`, `isFolderCovered`, `longestCommonPrefix`. The lexicographic-coverage guarantee they rest on is testable without mocks.
- **`hooks/invalidateBucketQueries.ts`** (new) — one place to refresh everything a mutation can move (`objects.list`, `containers.list`, `containers.getState`, `versioning.checkDeletedContent`), replacing the set that was copy-pasted across 13 modals and had already drifted out of sync at four of them.
- **`hooks/useBucketInfo.ts`** — now reads `containers.getState` instead of `containers.list` + a truncation-prone `objects.list` probe; the separate `versioning.getStatus` query is gone, since `getState` already has that value in hand.
- **`hooks/bucketStateHelpers.ts`** — deleted. Its `calculateBucketState` had no truncation parameter, and its `bucketObjectCount` guard never worked: `containers.list` was called without `includeMetadata`, whose default is `false`, so the count was hardcoded `0` on the server's fast path.
- **`constants.ts`** — adds `S3_MAX_SCAN_PAGES` (20), `S3_CONNECTION_TIMEOUT_MS` (5000), `S3_MAX_BUFFERED_VERSIONS_PER_KEY`, `MAX_REPORTED_DELETE_ERRORS`. The scan page size reuses the existing `S3_MAX_KEYS_PER_REQUEST`. `S3_MAX_BUFFERED_VERSIONS_PER_KEY` bounds the cross-page carry, not the peak: a key that finishes within one page is processed regardless of size, so the reachable peak for one key is the limit plus one page (21 000), a constant that does not grow with the bucket.
- **`clients/s3Client.ts`** — adds a 5 s `connectionTimeout` so an unreachable endpoint fails fast. `requestTimeout` and `maxAttempts` are deliberately left at SDK defaults; the file documents what that does and does not bound. The SDK resolves the `requestHandler` options object through `NodeHttpHandler.create()`, so the timeout does reach the handler; a regression test now resolves the handler and asserts it, so an SDK release that narrowed the accepted shapes would fail the suite instead of silently dropping the timeout.

## Component Updates

- **`DeleteVersionsModal`** — calls `deleteNonCurrentVersions` and splits the outcome three ways: a clean run reports success; a run that deleted nothing, hit per-key failures and did finish scanning is an error; anything else is a partial result. `errorCount` and `isPartial` are weighed independently rather than as alternatives — the server records an error and sets `isPartial` for the same skipped key, so the ordinary partial run carries both, and testing one before the other dropped whichever came second. A clean success closes the modal and confirms with a toast, same as before. A failure or a partial result now stays inside the still-open modal instead of closing and reporting through a toast: an inline `<Message variant="error">` at the top of the modal carries the same structured body the toast used to (it spells out the first few failures, counts the rest, and for a partial result adds that the scan did not finish and the action should be run again), and the retry is the same "Delete Versions" button, already enabled, in the same modal — no separate Retry control. Cancel, the close button and the Esc key are all blocked while the mutation is in flight, so a mid-flight close can no longer silently discard the only copy of the report — `disableCancelButton`/`disableCloseButton` only reach the rendered controls, and juno's `Modal` gates Esc on `closeOnEsc` alone.
- **`EmptyBucketModal`** — takes its version state from `containers.getState` instead of its own probe, and now treats a background refetch of that query (`isFetching`) the same as an initial load: the modal used to be able to render a "safe to delete" verdict off a stale cached answer while a fresher one was already in flight, and that stale answer is exactly the one that can force a full wipe. Its three hand-rolled error banners are now `Message`s with `role="alert"`/`aria-live="assertive"`, and a failed wipe no longer closes the modal and raises a transient toast: it stays open and reports inline, the same way "Delete Versions" does. That removed the modal's `onError` prop from all three places that render it and left `getBucketEmptyErrorToast` without consumers, so it is gone. The report survives the cache invalidation the failed run itself triggers, including the case where a partly-successful wipe leaves the bucket empty and moves the modal into its info-only branch with no checkbox. The three hand-rolled error banners are now `<Message variant="error" role="alert" aria-live="assertive">`, matching the pattern already used elsewhere in this folder.
- **`DeleteBucketModal`** — takes bucket contents from `containers.getState`, and the blocking checklist now has a third, independent reason: an incomplete scan blocks the delete (fail-closed) rather than letting an unverified bucket through. Also picks up the same background-refetch fix as `EmptyBucketModal`. It deliberately keeps the close-then-toast shape the other two dropped: `containers.delete` destroys nothing, since S3 refuses a non-empty bucket outright, so a failure is "nothing happened" rather than a partial result that has to be read.
- **`BucketHeaderActions` / `BucketHeader`** — "Empty Bucket" and "Delete Versions" visibility now follows the server's flags, so the actions no longer disappear on a bucket whose first 100 versions happened not to show any.
- **`ObjectBrowserView`** — a folder under `isPartialScan` renders neutrally: it is neither hidden from "All" nor flagged as holding deleted content in "Deleted". A positive result is always trustworthy; a negative one under a partial scan only means "not checked".
- **All object modals** (Copy / Move / Delete / DeleteObjects / Upload / EditMetadata / CreateFolder / RestoreVersion / DeleteVersion) and `EmptyBucketsModal` — switched to `invalidateBucketQueries`.

## Types

- **`types/ceph.ts`** — `bucketStateInputSchema`, `bucketStateOutputSchema` / `BucketState`, `deleteNonCurrentVersionsInputSchema` / `DeleteNonCurrentVersionsInput`, `deleteNonCurrentVersionsOutputSchema` / `DeleteNonCurrentVersionsOutput`.
- **`types/versioning.ts`** — `checkDeletedContentInputSchema` (optional `prefix`, `folders` capped at 1000), `checkDeletedContentOutputSchema` / `CheckDeletedContentOutput` with the per-folder `isPartialScan`.

## Tests

New suites for `versionScan`, `invalidateBucketQueries` and `useBucketInfo` — none of which had any coverage — plus new cases in `containerRouter`, `objectRouter`, `versioningRouter` and the six affected modal suites: truncation, the page ceiling, abort mid-scan, S3 errors, the lexicographic position of a folder's own marker, and more than 100 folders. `mockContext` now carries a real `signal`, without which an abort test passes for the wrong reason.

Also covered: a truncated page carrying no continuation marker in all three scan loops (`containers.getState`, `checkDeletedContent`, `deleteNonCurrentVersions`), including the counter-case that folders closed out before such a stop stay `isPartialScan: false` and that a first page truncating with no marker still credits the keys it delivered; an abort landing while the last page's `DeleteObjects` is in flight; the `connectionTimeout` actually reaching the resolved S3 request handler; the delete-versions modal's failure / partial / success split rendered inline, including a run that carries per-key failures and an unfinished scan at once, the retry surface staying live after a failure, the outcome `Message`'s `role`/`aria-live`, and Cancel, close and Esc all being blocked while the mutation is in flight (with the counter-case that Esc does close the modal when nothing is in flight); a key whose versions overflow the scan buffer only on its last page, which must still be processed whole rather than abandoned; and a background refetch of `containers.getState` (`isFetching` with a warm cache) in both `DeleteBucketModal` and `EmptyBucketModal` not being treated as a known answer.

# Behaviour and Contract Changes

Two of these narrow an existing contract. No in-repo caller is affected, but a consumer of the BFF outside this repo would be:

- `versioning.checkDeletedContent` now rejects a request that carries neither `prefix` nor `folders`, and rejects `folders` entries that fall outside `prefix`. The previously accepted `{ folders: [...] }` without `prefix` still works and is covered by a test, but degenerates: the scan scope collapses to the folders' longest common prefix, so nested content is not attributed.
- `versioning.checkDeletedContent` now surfaces S3 errors as tRPC errors. A caller that relied on the old silent `hasDeletedContent: false` will start seeing failures it was previously blind to.
- `isPartialScan` (`checkDeletedContent`, `containers.getState`) and `isPartial` (`objects.deleteNonCurrentVersions`) now also cover a truncated page that carried no continuation marker, and `isPartial` additionally covers an abort that lands while the last page is being deleted. External consumers will see `true` in situations that previously reported `false` — those answers were wrong before, not newly uncertain.

Not breaking, listed for the reviewer's benefit:

- `objects.deleteNonCurrentVersions` and `containers.getState` are new procedures; nothing called them before. No procedure was removed, and `versioning.getStatus` still exists — the client simply stopped calling it.
- UX-only, no BFF contract change: "Delete Versions" no longer closes on a failed or partial run, and "Empty Bucket" no longer closes on a failed one; both stay open and report themselves inline so the user can retry immediately. All three destructive bucket modals also block Cancel, the close button and Esc while their mutation is in flight.

# Related Issues

Fixes #1004.

# Testing Instructions

1. `pnpm i`
2. `pnpm run test`
3. Manual scenarios (verified against a real Ceph RGW):
   - versioned bucket, upload an object, delete it → "Delete Versions" appears in the bucket menu;
   - run "Delete Versions" on a bucket holding both current objects and old versions → current objects stay, old versions and delete markers go;
   - squash `S3_MAX_SCAN_PAGES` / `S3_MAX_KEYS_PER_REQUEST` to reproduce a partial scan without a 20 000-version bucket → the folder still renders in "All", is not flagged in "Deleted", and "Delete Bucket" blocks with the third reason;
   - empty a versioned bucket → version detection prevents the accidental full wipe;
   - bucket menu actions stay correct on a bucket whose first page of versions shows nothing interesting.

# Checklist

- [x] I have performed a self-review of my code.
- [x] I have commented my code, particularly in hard-to-understand areas.
- [x] I have added tests that prove my fix is effective or that my feature works.
- [x] New and existing unit tests pass locally with my changes.
- [x] I have made corresponding changes to the documentation (if applicable).
- [x] My changes generate no new warnings or errors.
