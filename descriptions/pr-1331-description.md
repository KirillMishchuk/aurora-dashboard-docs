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
- `isPartialScan` — set when the ceiling was reached; `hasOnlyDeleteMarkers` is forced to `false` under it, because a truncated scan cannot tell "no real versions exist" from "none seen yet".

### Updated `storage.ceph.versioning.checkDeletedContent`

- One paginated scan of the parent `prefix` instead of N unbounded per-folder scans running in parallel. The previous early-exit required the folder's own marker to be deleted, so for a live folder it never fired and a full scan of the prefix was the normal case, not the worst one.
- Accepts a new optional `prefix` input; `folders` stays optional and its cap is raised from 100 to 1000. The client now sends the prefix alone, which also keeps the query key stable across "Load more" — the old `folders`-keyed input restarted the whole scan on every page, and an uncut list of more than 100 folders was rejected outright, silently killing the indicators.
- Honours `ctx.req.signal` and pages at the standard `S3_MAX_KEYS_PER_REQUEST` instead of a hardcoded 100.
- Returns a per-folder `isPartialScan` instead of guessing completeness.
- Surfaces S3 errors as tRPC errors; the previous empty `catch` swallowed `AccessDenied`, throttling and timeouts alike and reported "no deleted content".

## Core Infrastructure

- **`helpers/versionScan.ts`** (new) — pure helpers for attributing keys to child folders during a delimiter-less prefix scan: `folderPrefixOf`, `isFolderCovered`, `longestCommonPrefix`. The lexicographic-coverage guarantee they rest on is testable without mocks.
- **`hooks/invalidateBucketQueries.ts`** (new) — one place to refresh everything a mutation can move (`objects.list`, `containers.list`, `containers.getState`, `versioning.checkDeletedContent`), replacing the set that was copy-pasted across 13 modals and had already drifted out of sync at four of them.
- **`hooks/useBucketInfo.ts`** — now reads `containers.getState` instead of `containers.list` + a truncation-prone `objects.list` probe; the separate `versioning.getStatus` query is gone, since `getState` already has that value in hand.
- **`hooks/bucketStateHelpers.ts`** — deleted. Its `calculateBucketState` had no truncation parameter, and its `bucketObjectCount` guard never worked: `containers.list` was called without `includeMetadata`, whose default is `false`, so the count was hardcoded `0` on the server's fast path.
- **`constants.ts`** — adds `S3_MAX_SCAN_PAGES` (20), `S3_CONNECTION_TIMEOUT_MS` (5000), `S3_MAX_BUFFERED_VERSIONS_PER_KEY`, `MAX_REPORTED_DELETE_ERRORS`. The scan page size reuses the existing `S3_MAX_KEYS_PER_REQUEST`.
- **`clients/s3Client.ts`** — adds a 5 s `connectionTimeout` so an unreachable endpoint fails fast. `requestTimeout` and `maxAttempts` are deliberately left at SDK defaults; the file documents what that does and does not bound.

## Component Updates

- **`DeleteVersionsModal`** — calls `deleteNonCurrentVersions`, reports partial per-key failures as errors, and warns when `isPartial` says the bucket was not processed to the end.
- **`EmptyBucketModal`** — takes its version state from `containers.getState` instead of its own probe.
- **`DeleteBucketModal`** — takes bucket contents from `containers.getState`, and the blocking checklist now has a third, independent reason: an incomplete scan blocks the delete (fail-closed) rather than letting an unverified bucket through.
- **`BucketHeaderActions` / `BucketHeader`** — "Empty Bucket" and "Delete Versions" visibility now follows the server's flags, so the actions no longer disappear on a bucket whose first 100 versions happened not to show any.
- **`ObjectBrowserView`** — a folder under `isPartialScan` renders neutrally: it is neither hidden from "All" nor flagged as holding deleted content in "Deleted". A positive result is always trustworthy; a negative one under a partial scan only means "not checked".
- **All object modals** (Copy / Move / Delete / DeleteObjects / Upload / EditMetadata / CreateFolder / RestoreVersion / DeleteVersion) and `EmptyBucketsModal` — switched to `invalidateBucketQueries`.

## Types

- **`types/ceph.ts`** — `bucketStateInputSchema`, `bucketStateOutputSchema` / `BucketState`, `deleteNonCurrentVersionsInputSchema` / `DeleteNonCurrentVersionsInput`, `deleteNonCurrentVersionsOutputSchema` / `DeleteNonCurrentVersionsOutput`.
- **`types/versioning.ts`** — `checkDeletedContentInputSchema` (optional `prefix`, `folders` capped at 1000), `checkDeletedContentOutputSchema` / `CheckDeletedContentOutput` with the per-folder `isPartialScan`.

## Tests

New suites for `versionScan`, `invalidateBucketQueries` and `useBucketInfo` — none of which had any coverage — plus new cases in `containerRouter`, `objectRouter`, `versioningRouter` and the six affected modal suites: truncation, the page ceiling, abort mid-scan, S3 errors, the lexicographic position of a folder's own marker, and more than 100 folders. `mockContext` now carries a real `signal`, without which an abort test passes for the wrong reason.

# Behaviour and Contract Changes

Two of these narrow an existing contract. No in-repo caller is affected, but a consumer of the BFF outside this repo would be:

- `versioning.checkDeletedContent` now rejects a request that carries neither `prefix` nor `folders`, and rejects `folders` entries that fall outside `prefix`. The previously accepted `{ folders: [...] }` without `prefix` still works and is covered by a test, but degenerates: the scan scope collapses to the folders' longest common prefix, so nested content is not attributed.
- `versioning.checkDeletedContent` now surfaces S3 errors as tRPC errors. A caller that relied on the old silent `hasDeletedContent: false` will start seeing failures it was previously blind to.

Not breaking, listed for the reviewer's benefit:

- `objects.deleteNonCurrentVersions` and `containers.getState` are new procedures; nothing called them before. No procedure was removed, and `versioning.getStatus` still exists — the client simply stopped calling it.

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
