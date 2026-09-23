## What was implemented

Both halves described above are done, plus a third thing: a data-loss bug in "Delete Versions" that surfaced while reworking the gating around it. That one has its own comment below — this one covers the two halves of #1004.

### Backend — one bounded scan instead of a hundred unbounded ones

Rather than tightening the per-folder fan-out, `checkDeletedContent` now performs **one paginated, delimiter-less scan of the parent prefix** and attributes each key to its direct-child folder (`prefix + key.slice(prefix.length).split("/")[0] + "/"`).

The data is equivalent: the union of the per-folder scans is a subset of the parent-prefix scan, plus the loose objects at the prefix level, which have no remaining `/` and are ignored. All three computed values come from the same sets.

What this buys:

| | before | after |
|---|---|---|
| typical case (20 folders) | 20 requests minimum | **1** |
| 100 folders | 100 requests minimum | **1–2** |
| worst case | 100 × unbounded | page ceiling, once |

- Hard ceiling of `S3_MAX_SCAN_PAGES = 20` × `S3_MAX_KEYS_PER_REQUEST` (1000) = 20,000 versions, reported through a new **per-folder `isPartialScan`** flag. `hasDeletedContent` stays strictly factual — the "conservative fallback = true" idea was **not** implemented, for the reasons in the previous comment.
- `MaxKeys` now uses `S3_MAX_KEYS_PER_REQUEST` instead of the hard-coded 100.
- `ctx.req.signal` is honoured at the top of each iteration and passed as `abortSignal` to `s3.send`, matching `objectRouter.ts:156`.
- The empty `catch` is gone. Errors are logged and mapped through `mapS3ErrorToTRPCError`; only an actual abort stops the loop quietly, returning what was accumulated with `isPartialScan: true`.
- Input stays backward compatible: `prefix` added as optional, `folders` made optional and widened to `.max(1000)`. `folders` is now an output filter rather than a fan-out driver, so the cap no longer implies request cost. Two shapes are newly **rejected**, both of which used to be answered confidently and wrongly: a call giving neither `prefix` nor `folders` (nothing to scan, so it walked the whole bucket), and a `folders` entry that does not live under `prefix` (never visited, yet reported as clean — a completed scan marks every unseen folder covered). The flag `isPartialScan: false` means "this answer is reliable", so an input that cannot honour it is refused rather than served.
- Its input/output schemas moved out of the router into `types/versioning.ts` (`checkDeletedContentInputSchema` / `checkDeletedContentOutputSchema`, built on `projectScopedInputSchema` rather than a hand-rolled `project_id: z.string()`), matching every sibling procedure in that router.
- `S3_CONNECTION_TIMEOUT_MS` (5s) added to the shared S3 client. `requestTimeout` and `maxAttempts` were deliberately left alone — that client is shared with the streaming upload/download paths, so changing them needs its own investigation.

**Two bugs found and fixed along the way:**

- `folderMarkerVersionId` was only ever populated from the first page (`if (!folderMarkerVersionId && response.Versions)`), so a folder marker appearing later was lost. It is now accumulated by most recent `LastModified` across pages.
- The `folders`-without-`prefix` fallback scanned the folders' common prefix, which for a single folder *is* that folder — leaving no path segment for any key to be attributed by, so every such call returned `{hasDeletedContent: false, folderMarkerVersionId: undefined, isPartialScan: false}`. The All tab reads a missing marker version as "permanently deleted" and hides the folder, so the one input shape kept purely for backward compatibility answered confidently and wrongly. The fallback now climbs to the common **parent**, exactly when the shallowest folder is itself the common prefix: `["p/foo/"]` scans `p/`, while `["p/foo/", "p/bar/"]` still scans `p/` without climbing needlessly.

### Frontend — state computed once, on the server

The three duplicate client probes are replaced by a single `storage.ceph.containers.getState`,
returning `{ status, isVersioningEnabled, isEmpty, hasOnlyDeleteMarkers,
hasOldVersionsOrDeleteMarkers, isPartialScan }`.

The flags are established by different means, deliberately, because they are not equally
hard to answer:

- **`status` and `isEmpty` never involve the scan.** The raw three-way versioning status comes
  from the `GetBucketVersioning` the procedure has to issue anyway; emptiness from its own one-key
  `ListObjectsV2`, which lists current objects only and omits anything hidden behind a delete
  marker — so "no keys returned" *is* emptiness, exactly, in one request, on a bucket of any size.
  The two commands go out in parallel, since neither depends on the other.
- **An unversioned bucket stops there.** S3 cannot hold a non-current version or a delete marker
  for it, so both history flags are false by definition and there is nothing to scan. Two requests,
  whatever the bucket's size.
- **Only the history flags use the bounded scan**, which exits as soon as it has seen both an old
  version or delete marker (proving `hasOldVersionsOrDeleteMarkers`) and a real version
  (disproving `hasOnlyDeleteMarkers`). Two shapes satisfy neither and therefore scan to the end of
  the bucket or to the ceiling: a genuinely clean history, and a bucket left holding only delete
  markers after a `NoncurrentVersionExpiration` rule expired the real versions behind them. Both
  costs are inherent rather than wasteful — in each case the scan is still working towards an
  answer that only the last page can give.

`status` is returned raw alongside the collapsed `isVersioningEnabled` boolean for a specific
reason: the bucket header renders a different badge for "Suspended" than for "Unversioned", and
without it `useBucketInfo` and `EmptyBucketModal` each paid a second `GetBucketVersioning` through
`versioning.getStatus` beside this call — on the modal, with `staleTime: 0`, a guaranteed duplicate
round-trip on every open. Both now read it from here.

Deriving emptiness from the scan instead was the natural first design, and it was wrong in a way
worth naming: `DeleteBucketModal` blocks deletion on `isPartialScan`, so a bucket too large to scan
became **permanently undeletable**, told to "refresh and try again" by a check that could never
succeed. Splitting emptiness off removes that state entirely — an unconfirmed history can no longer
leave a bucket unactionable.

`hasOnlyDeleteMarkers` is forced to `false` whenever the scan was cut short, rather than reported
as seen. A truncated scan that happened to encounter only delete markers cannot tell "this bucket
holds nothing else" from "the real versions are on a page we never read", and `EmptyBucketModal`
reads that flag as "already emptied".

There is deliberately no `currentObjectCount` in that shape. The one-key probe has no count to
give, the scan's early exit could only ever produce a lower bound, and the sole consumer
immediately reduced it to `> 0` — so the count was dropped rather than shipped as a number nobody
could trust.

Knock-on cleanups this made possible:

- `useBucketInfo` no longer queries `containers.list` or `objects.list` at all, which removes the always-zero `bucketObjectCount` problem rather than papering over it.
- The dead `isBucketEmptyWithVersions` return value (read by no component) is gone.
- The client-side `bucketStateHelpers.ts` is deleted. Its logic lives in `getState`'s scan loop rather than in a separate pure helper: an intermediate `calculateBucketState` was written first, but since the loop has to decide per page in order to early-exit, the helper ended up never being called — a second definition of bucket state that could only drift. The rules are covered by `containerRouter` tests instead.
- **Cache coherence.** Moving state to the server introduced a regression the review round caught: the ten object modals invalidated `objects.list`, which `useBucketInfo` used to derive state from, but not the new `containers.getState`. Deleting the last object left the bucket menu showing pre-mutation state for up to 30s. All call sites now go through one `invalidateBucketQueries(utils, options)` helper, so the next query added to that set cannot be forgotten in nine places.

  Every bucket-wide query in it is invalidated unconditionally. That was not the first design, and
  the way the first design failed is the interesting part. Two of the queries are server-side
  scans, so both were put behind opt-in flags on the theory that the caller knows whether its
  mutation could have moved them.

  `containers.getState` lost its flag in the first review round: a reviewer proposed keeping it
  opt-in on the grounds that a metadata edit or a copy cannot change bucket state, and checking
  showed the opposite — `updateMetadata` and `copyObject` are both `CopyObjectCommand`s, and
  copying onto an existing key writes a new version, which turns the previous current version into
  an old one and flips `hasOldVersionsOrDeleteMarkers` from false to true.

  `checkDeletedContent` kept its flag one round longer, and by the next review four of thirteen
  call sites had it wrong — including `objects.delete` called from two different modals with two
  different answers. The premise behind the flag was that only deletions can change whether a
  folder holds deleted content. They are not the only ones: the query counts delete markers that
  are *currently latest*, and writing to a key whose current record is a delete marker makes that
  marker non-latest, so an upload, a copy or a folder creation onto a deleted key clears deleted
  content exactly as a delete creates it. Of the thirteen sites only `updateMetadata` genuinely
  could not move it, because it can only run against a key that is already visible. A flag that is
  right at one call site out of thirteen is not an optimisation, it is a trap — and
  `checkDeletedContent` is the *cheaper* of the two scans anyway, bounded to a single prefix where
  `getState` scans the whole bucket, so making it the opt-in one had it backwards twice over.

  What survives as a flag is `objectVersions`, which is genuinely narrow: it is keyed to one
  object, and only the two modals acting on a single version have anything to tell it. The
  reasoning for each unconditional query is recorded next to it so neither gets re-proposed.
- `folders` is no longer sent from `ObjectBrowserView` — the query key is now `{ project_id, bucket, prefix }`, which is stable across "Load more" and has no 100-folder limit. Both client-side defects from the previous comment disappear as a side effect.

### Fail-open vs fail-closed

Split by what a wrong guess costs:

- **Non-destructive gates fail open.** A folder whose scan was incomplete stays **visible** in the All tab — this is the mitigation for the "live folders disappear" risk. `Empty Bucket` is permission-gated only; its modal already has a live "already empty" branch.
- **Destructive gates fail closed.** `DeleteBucketModal` gained a third blocking reason for unverifiable contents and never enables deletion on incomplete data. `Delete Versions` stays gated on `hasOldVersionsOrDeleteMarkers` alone, because `false` there can mean either "none found" or "could not check", and only the first justifies offering an action that unrestorably deletes version history. `Empty Bucket` remains available whenever there is genuinely something to clean up, so this is not a dead end.

### Known limitations, stated up front

- Under the page ceiling, folders that sort lexicographically last may not be reached at all, where per-folder scanning guaranteed each folder its first page. This is reported via `isPartialScan` and rendered neutrally rather than guessed. Coverage is computable exactly: on stopping at `NextKeyMarker = X`, folder `F` is complete iff `F < X && !X.startsWith(F)`.
- A versioned bucket whose history is genuinely clean gives `getState` nothing to find and no way
  to know that early, so its scan runs to the end of the bucket or to the ceiling. The same holds
  for a bucket left holding only delete markers once a `NoncurrentVersionExpiration` rule has
  expired the versions behind them: `hasOldVersionsOrDeleteMarkers` is settled on page one, but
  `hasOnlyDeleteMarkers` cannot be, since any later page could still carry a real version. This is
  inherent — proving a negative about a whole bucket means looking at the whole bucket — and it is
  bounded, not unbounded. It no longer blocks anything, since emptiness is established separately
  and exactly. Both shapes are named in the procedure's own cost note rather than left for a reader
  to discover.

### Tests

There were **no tests at all** for `bucketStateHelpers.ts` or `useBucketInfo.ts`, and all six existing `checkDeletedContent` cases set `IsTruncated: false`, so the pagination loop, the early exit and the `catch` were entirely uncovered.

Added: pure-helper tests for key attribution, coverage and the parent-prefix rule;
`checkDeletedContent` rewritten for the new input, covering page breaks, the page ceiling, both
abort paths, `AccessDenied`/`SlowDown` no longer being swallowed, the byte-order guarantee that a
folder's marker opens its own range, the two rejected input shapes, and the bucket root as an
explicit empty prefix; `getState` covering the skipped scan on an unversioned bucket, exact
emptiness under a truncated scan, `hasOnlyDeleteMarkers` collapsing to false when unproven,
delete-markers-only, ceiling, abort, missing credentials, and the raw `status` reported for a
suspended bucket. On the client: `isPartialScan` in both tabs, query-key stability,
fail-open/fail-closed gating, the previously uncovered "Delete Versions" branch of
`EmptyBucketModal`, a first test file for `useBucketInfo` — including that it takes the versioning
status from `getState` and never queries `versioning.getStatus`, and that the object it hands the
header is reference-stable — the invalidation helper's contract, and that the object browser asks
for the root as `prefix: ""` rather than as no prefix at all. The dead `maxKeys === 1` branch in
`ObjectBrowserView.test.tsx` (a query that no longer exists in production) was removed.

### Review rounds

The branch was put through a parallel security / performance / architecture review three times —
when it was feature-complete, and again after each round of resulting fixes.

**No Critical findings, and no High security findings against the new code.** The new procedures
use the domain's existing `cephProtectedProcedure`, so the destructive one sits at the same
authorization bar as the `deleteAll` it replaces in this flow, and nothing new is exposed to the
client or the logs. One authorization finding is genuine but not this PR's to fix — see the
follow-up comment.

The first round produced four fixes: `getState`'s early exit could never fire for an **unversioned**
bucket, since it waited on a flag such a bucket never sets, so a large unversioned bucket ran the
full ceiling and came back `isPartialScan: true`, needlessly blocking "Delete Bucket"; the
cache-coherence gap described above; the dead `calculateBucketState`; and one in the new delete
path, covered in the next comment.

The second round found that the same class of mistake survived one level up — the early exit had
been fixed for unversioned buckets but not for versioned ones, and the guard against a malformed
RGW response had been placed on `VersionId` but not on `IsLatest`. Both are fixed here, along with
the emptiness split described above, the parent-prefix fallback, the input refinements, and the
`O(folders x statuses)` recomputation in `ObjectBrowserView`, which this branch had inadvertently
unbounded by removing the 100-folder cap that used to limit it. It also produced one finding that
was **not** acted on, because verifying it showed the proposed change would introduce a bug: the
`getState` invalidation flag discussed above.

The third round found no Critical or High security findings, and its most useful result was about
an abstraction rather than a bug: the surviving `deletedContent` invalidation flag was already
answered wrongly at four of thirteen call sites, two of them the same mutation. That flag is gone,
for the reasons set out above. The round also renamed `getState`'s input key to `bucketName` to
match every other `containers.*` procedure before this ships as public API, applied
`checkDeletedContentOutputSchema` to a return that had been declared with a contract and never
validated against it, folded the versioning status into `getState` so two call sites stop paying a
duplicate `GetBucketVersioning`, and completed the procedure's cost note with the
delete-markers-only shape it had omitted.

Every behavioural fix across the three rounds is pinned by a regression test that was verified to
fail against the pre-fix code, so none of them can pass for an unrelated reason.

All CI jobs green locally: `licenses:check`, `lint`, `check-i18n`, `typecheck`, `format:check`,
`test` (235 files / 5700 tests), `build`.
