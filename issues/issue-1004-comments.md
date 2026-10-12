---
type: issue-comment
date: 2026-09-23
issue: [1004]
---
# Issue #1004 — comment drafts

Three separate comments on GitHub issue #1004 (the issue body itself is not edited). Post them one by one: each comment is the text between its `# Comment N` heading and the next one — the `# Comment N` headings themselves are not part of the comments.

# Comment 1 — description verified against the code

## Description verified against the code at `dc918d47`

*(Both halves are now implemented — see the two comments below. This one records what the code
actually looked like beforehand, because several excerpts in the description do not match it and
whoever revisits this issue should not start from them.)*

I went through this issue line by line against the current `main`. Most of the diagnosis holds, but several code excerpts above do not match what is in the repository, one conclusion is not reachable, and one of the proposed fixes would break the object browser. Details below, so that whoever picks this up works from the real code.

### Confirmed

- `hooks/useBucketInfo.ts:123-135` issues a single `objects.list` query with `maxKeys: 100`, `delimiter: ""`, `showVersions: true`, and never reads `isTruncated` / `nextKeyMarker` / `nextVersionIdMarker`.
- `hooks/bucketStateHelpers.ts:11-48` (`calculateBucketState`) has no truncation parameter and no truncation guard, so `hasOnlyDeleteMarkers` (`:23`) can be wrongly `true` on a truncated page.
- `versioningRouter.ts` `checkDeletedContent` paginates `ListObjectVersions` with **no page limit, no time limit and no abort signal**.
- `folders: z.array(z.string()).max(100)` and `MaxKeys: 100` are both as described.
- The intent is documented in the code: *"Paginate through all versions to find if ANY delete marker exists"*, and the procedure's own doc block already warns *"This can be expensive for many folders"*.

### Stale or non-existent in the repository

- **The quoted loop does not exist.** There is no `while (!hasDeleteMarkers)` and no variable by that name. The actual construct is `do { … } while (true)` with an `eslint-disable-line no-constant-condition`; the variables are `hasDeletedNestedObjects` and `isFolderMarkerDeleted`. Anyone grepping for the quoted condition will not find it.
- **Line numbers do not match.** `checkDeletedContent` lives at `versioningRouter.ts:359-488`, not `:358`/`:384-412`.
- **`EmptyBucketModal` already handles truncation.** Since #1249 (`2275f02c`, 2026-09-02) it computes `isVersionDataComplete = !versionCheckData?.isTruncated` (`:96`) and conjoins it into both `isBucketEmptyWithVersions` (`:98`) and `isTrulyEmpty` (`:102`). It also has a third mode this issue does not mention — the info-only "This bucket is already empty" branch (`:217`). The two-flag formula quoted above describes an older version of that file.
- **No backend change is needed for the frontend half.** `listObjectsInputSchema` (`types/ceph.ts:164-173`) already accepts `keyMarker`, `versionIdMarker` and `continuationToken`; the handler already forwards them (`objectRouter.ts:237-245`); the response already returns `isTruncated` / `nextKeyMarker` / `nextVersionIdMarker` (`:297-305`); and `maxKeys` is capped at `.max(1000)`, so 100 → 1000 needs no schema change. `ObjectBrowserView.tsx:175-262` is a working in-repo precedent for the full pagination loop.

### Not reachable as described

> Allows bucket deletion when 200 old versions exist!

This cannot happen. `DeleteBucketModal.tsx:121-134` computes `cannotDelete = hasCurrentObjects || hasVersionsInVersionedBucket`, and any non-empty first page sets at least one of them (`hasOldVersionsOrDeleteMarkers` uses `.some(...)`, so truncation can only make it *miss*, never invent). The real defect is milder but still bad: the **list of blocking reasons** (`:173-190`) can be incomplete, so the user clears what is listed, hits the block again, and is given no way to learn why. A loop with no exit.

### Cost figures

The AWS request pricing does not apply — this runs against self-hosted Ceph RGW, where LIST requests are not billed per call. The two figures in the description also contradict each other (`10,000 × $0.0004 = $4.00` in one place, `10,000 requests = $0.05` in another). The real cost is round-trips, latency, a blocked event loop and RGW load — those are the numbers worth quoting.

Scope note on the DoS framing: `checkDeletedContent` is a `cephProtectedProcedure`, so it requires a valid session, a role on the project, and the caller's own EC2 credentials, and the RGW requests are signed as the caller. It is a self-inflicted / insider resource-exhaustion problem, not an unauthenticated attack surface.

---

### Five defects the description missed

**1. The early exit never fires for a live folder — the worst case *is* the ordinary case.**

```ts
// Early exit optimization: stop if we have all the information we need
if (hasDeletedNestedObjects && isFolderMarkerDeleted && folderMarkerVersionId) {
  break
}
```

It requires **all three** conditions. For any folder that has not itself been deleted, `isFolderMarkerDeleted` is permanently `false`, so the loop always runs to the end of the prefix. A folder with no delete markers at all — the normal, healthy case — is scanned in full, every time. The assumption "in most cases we will find it quickly" is exactly inverted.

**2. The per-folder `catch` is empty and swallows everything.**

```ts
} catch {
  // If query fails for this folder, assume no deleted content
  return { prefix: folderPrefix, hasDeletedContent: false, isFolderDeleted: false }
}
```

`AccessDenied`, throttling (`SlowDown`/503) and timeouts are all silently rendered as "this folder is clean", with no logging. This makes the outer `mapS3ErrorToTRPCError` dead code for per-folder failures, and it hides the very throttling that this procedure provokes.

**3. `.max(100)` versus an unsliced client array.** `ObjectBrowserView.tsx:146-156` sends `folders: allFolders.map((f) => f.prefix)` with no `slice`, while `allFolders` accumulates across pages at `maxKeys: 1000`. On a prefix with more than 100 sub-folders, Zod rejects the whole request with `BAD_REQUEST` and the deleted-content indicators silently stop working — no error shown to the user.

**4. The query key is unstable.** That same `.map()` allocates a new array on every accumulation (`:205`/`:219`), producing a new query key, so the entire fan-out restarts on every "Load more". `staleTime: 30s` does not help.

**5. `bucketObjectCount` is always `0`.** `useBucketInfo.ts:48-62` calls `containers.list` **without `includeMetadata`**; the schema default is `false` (`types/ceph.ts:56`) and the fast path returns a hard-coded `count: 0` (`containerRouter.ts:46-54`). So the comment on `:49` ("to get accurate count (same as Buckets page)") is wrong, the `bucketObjectCount > 0` branch of `calculateBucketState` never executes, and `isBucketEmpty` rests entirely on the first 100 entries. The metadata safety net the formula was written around does not exist.

---

### The proposed backend fallback would break the object browser

> `hasDeletedContent: reachedLimit ? true : hasDeleteMarkers`

`ObjectBrowserView.tsx:317-353` consumes this result two different ways:

- the **All** tab *hides* a folder unless `!status.isFolderDeleted && status.folderMarkerVersionId !== undefined`;
- the **Deleted** tab *shows* a folder when `status?.hasDeletedContent` is true.

Two consequences:

1. Visibility in the **main** listing is driven by `isFolderDeleted` and `folderMarkerVersionId`, which the proposal does not touch at all. Any page bound that leaves `folderMarkerVersionId` undefined will **remove live folders from the main listing** — a far worse outcome than a missing indicator.
2. Returning `true` on limit would mark every large **healthy** folder as containing deleted content and pull it into the Deleted tab. The indicator loses its meaning precisely on the folders it exists for.

The absence of an entry is safer than a wrong entry: `:325` already shows the folder when no status is present. Uncertainty should travel as its own field, not as a guessed value.

One helpful property to build on: S3 returns keys in raw byte order, and `foo/` sorts before every
`foo/<anything>`, so a folder's own marker is the first key of its own range. Under the existing
per-folder scans that means it arrives on the folder's first page, and `isFolderDeleted` /
`folderMarkerVersionId` can be resolved from that page alone; only the search for nested delete
markers needs to go deeper, and only that needs bounding.

The same ordering is what makes a single parent-prefix scan bounded *honestly* rather than
approximately: if such a scan stops at key `X`, a folder `F` was fully covered exactly when
`F < X && !X.startsWith(F)` — everything in `F`'s range sorts before `X` and none of it is still
pending. Coverage becomes a computation instead of a guess.

# Comment 2 — what was implemented

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

# Comment 3 — second bug, follow-ups, out of scope

## A second bug found while working on this — fixed in the same PR

The bucket-state work above touched the gating of the `⋮` → **Delete Versions** action, which is how this surfaced.

### The bug

`DeleteVersionsModal.tsx` unconditionally called:

```ts
// Always delete all versions and delete markers (includeVersionsAndDeleteMarkers: true)
deleteVersionsMutation.mutate({ ..., includeVersionsAndDeleteMarkers: true })
```

and that branch of `objectRouter.ts` collected:

```ts
const versions = listResponse.Versions ?? []
const deleteMarkers = listResponse.DeleteMarkers ?? []
const allItems = [...versions, ...deleteMarkers]   // no IsLatest filter
```

`ListObjectVersions.Versions` includes current versions (`IsLatest: true`), and the loop re-scanned from the beginning until the bucket came back empty. **"Delete Versions" emptied the entire bucket, irreversibly.**

Reproduction — no edge case required:

1. Versioned bucket. Upload `a.txt` twice (now it has one old version). Upload `b.txt` once.
2. Bucket page → `⋮` → **Delete Versions** → type the bucket name → confirm.
3. Expected from the label: the old version of `a.txt` goes, both files stay.
4. Actual: the bucket is empty. `b.txt` is gone, despite having no versions to clean at all.

This was pre-existing and unrelated to pagination, but it is a data-loss defect on a path this PR already touches, so it is fixed here rather than deferred.

### The fix

A new `storage.ceph.objects.deleteNonCurrentVersions` procedure. `deleteAll` is left untouched, because "Empty Bucket" depends on it and its rescan loop is not worth destabilising for this.

The rule: **delete every record except `Version` entries with `IsLatest === true`.**

| Key state | Result |
|---|---|
| `V3` (latest), `V2`, `V1` | `V3` kept, `V2`/`V1` deleted |
| `DM` (latest), `V2`, `V1` | deleted entirely, marker included |
| non-latest delete markers | deleted |

So the bucket keeps exactly what the normal listing shows, each object with only its current version. Deleted objects are purged whole — leaving a marker whose underlying versions were removed would produce an object that reads as deleted but can never be restored. The modal copy now states this explicitly, including that the Deleted tab can no longer be restored from.

One pass is sufficient: deleting a specific version by `VersionId` does not create a new delete marker, which is the only reason `deleteAll` needs its rescan-until-empty loop. (That settles correctness, not wall-clock — see the follow-up note below on the missing page ceiling.)

### The subtle part, for reviewers

`IsLatest` is computed by S3 **per listing request**, not globally. If a key's records straddle a page boundary and we delete its delete marker right after page 1, the request for page 2 is served against a bucket where that marker is already gone — so S3 reports the newest surviving version as `IsLatest: true`, the rule keeps it, and **a deleted object comes back to life**.

The scan therefore defers the group that may continue, and only decides once the whole key has been read. The deferred group is identified by `NextKeyMarker` (on a truncated response S3 sets it to the last key returned), not by "whatever sorted last on our side" — the merged `Versions` + `DeleteMarkers` arrays are also re-sorted in byte order rather than with `localeCompare`, since locale collation orders `"a"` before `"A"` while S3 does the opposite.

Both are covered by regression tests, each verified to fail against the naive implementation:

- a key with `DM`(latest)/`V2` on page 1 and `V1` on page 2 — all three must go, nothing kept;
- a page holding both `"A"` and `"a"` where `"a"` is the continuing key — page 1 may only act on `"A"`.

Also hardened, all in the same direction — when the response cannot be read, touch nothing rather
than guess:

- An entry with no `VersionId` is skipped rather than sent, because a `DeleteObjects` entry without
  a version does not remove anything on a versioned bucket — it creates a new delete marker, hiding
  a live object.
- A **completed key group with no record flagged `IsLatest`** is skipped whole. The deferral above
  is precisely what makes a group complete, so this should be impossible; the reason it is guarded
  anyway is the failure direction. `find(item => item.IsLatest)` returning `undefined` used to read
  as "this key has no current version", which queued the entire group — the live object included —
  for deletion by explicit version id, leaving no delete marker to restore from. The safe reading
  of an unreadable group is to delete none of it.
- A key whose records **overflow the scan buffer** is abandoned rather than accumulated. Judging a
  group needs all of it in memory at once, so a key spanning pages is buffered until it ends; a key
  rewritten hundreds of thousands of times (a CI artifact, a rolling log) would otherwise let one
  tenant grow the shared BFF's heap without bound.

Each of those, and an aborted run, sets **`isPartial: true`** in the result, and the modal then
warns that versions may remain instead of reporting a clean success. The procedure returns its own
shape rather than the bulk-delete one — counts, a capped error sample and that flag, with no
per-key `deleted` array, since this mutation scans a whole bucket and that array would grow with
the bucket instead of with the caller's input.

### Incidental cleanups in the same area

- `ObjectBrowserView` rendered `DeleteVersionsModal` and held its open state, but `setIsDeleteVersionsModalOpen(true)` had **zero call sites** — the modal was unreachable from the object browser. Dead code removed; the bucket header was and remains the only entry point.
- A comment in `BucketModals.tsx` claimed the modal *"fetches real-time bucket state (versions, delete markers) via its own queries when opened"*. It makes no queries at all. Corrected.
- The mutation now surfaces `errorCount` instead of reporting success when S3 partially fails, and
  a run that did not reach the end of the bucket is reported as incomplete rather than as a count.

---

## Follow-up work this PR deliberately leaves alone

**Extract a shared `scanObjectVersions` paginator.** There are now six `ListObjectVersions` pagination loops in the Ceph routers, each with its own take on the page ceiling (20 / 20 / none / none / …), abort handling, and stalled-marker detection — only some have all three. Every future fix to S3 pagination semantics has to be applied in six places and will be applied in two.

The shape that fits is an async generator in `Storage/helpers/versionScan.ts` — `scanObjectVersions(s3, { bucket, prefix, maxPages, signal })` yielding pages and reporting `{ stoppedAtKey, isPartial }` — folding the ceiling, abort handling and stall detection into one place and reducing each handler to "accumulate and decide".

It is not done here on purpose. Five of those six loops predate this PR (three in `objectRouter`, two in `versioningRouter`); this branch added one and rewrote one. Extracting the common scanner therefore means rewriting `deleteAll` — shipped code that permanently deletes objects — in the same diff as a new procedure that permanently deletes versions. That would leave a reviewer unable to separate "new delete-versions logic" from "rewrote the existing delete-everything logic", on a branch that is already 44 files. It deserves its own PR and its own review pass.

One smaller item in the same bucket:

- **`deleteNonCurrentVersions` has no page ceiling.** Correctness does not need one (see above —
  deleting by `VersionId` creates no new markers, so there is no rescan), and a per-key buffer
  ceiling plus the `isPartial` flag now bound the two things that were actually dangerous: server
  memory, and reporting an incomplete wipe as a complete one. What remains is wall-clock — on a
  bucket with hundreds of thousands of non-current versions the mutation runs for minutes inside a
  single request and can hit a proxy timeout. `deleteAll` has exactly the same property and is
  already in production; giving only the new procedure a page ceiling would make it the only one
  that can stop half-done. The two should be decided together, along with whether this class of
  operation belongs behind the existing progress-subscription pattern.

### Raised by review, deliberately left for separate work

**Destructive Ceph mutations are not authorized server-side.** `storage:object_version_delete` maps
to `rule:storage_admin` in the policy file, but that rule is only ever consulted by the client to
decide what to render: `canUser` has no call sites anywhere under `server/Storage`. A project member
without the admin role gets the menu item hidden and can still call the procedure directly, with
`deleteAll`, `deleteVersionsBulk` and `containers.delete` in exactly the same position. Effective
enforcement therefore rests entirely on RGW's Keystone role mapping, which is a coarser gate than
the policy file describes.

This PR adds one more door to that room, so it is worth naming here — but it is not this PR's to
fix. Either RGW is the authorization boundary and oslo.policy is advisory UI metadata, in which
case that should be stated once on `cephProtectedProcedure` and stop being re-litigated, or the
domain needs a `requirePermission` middleware applied across every destructive mutation at once.
Both are decisions about the whole Ceph surface. Happy to open a separate issue.

Three smaller ones from the same round, all pre-existing:

- **Key ordering uses UTF-16 comparison for a UTF-8-ordered API.** JavaScript's `<` on strings
  compares UTF-16 code units; S3 orders keys by raw UTF-8 bytes. The two disagree only for
  astral-plane characters versus U+E000–U+FFFF — emoji or CJK Ext-B in key names. Where it matters
  is the deferral fallback and the folder-coverage check, so the fix is a `Buffer.compare`-based
  comparator shared between them. Left out of this diff on purpose: it touches the most delicate
  part of the new delete path, and mixing it with the data-loss fix would make a failure there
  ambiguous.
- **A new `S3Client` and keep-alive agent per procedure call.** `getCephClient()` constructs one per
  invocation and nothing ever destroys it, so there is no connection reuse across requests and idle
  sockets accumulate. Worth a small per-credential cache — and worth doing together with any future
  change to the SDK timeouts below, since a shared agent changes what `connectionTimeout` can hit.
- **The object browser's pagination accumulator can duplicate rows.** After loading several pages,
  invalidating `objects.list` refetches only the page the current token points at, and the
  accumulating effect appends it again. Structural sharing hides this until a mutation actually
  changes the data. The real fix is `useInfiniteQuery` rather than a hand-rolled accumulator, which
  is a rewrite of that component's data flow.

Also noted and not done: six modals besides `DeleteVersionsModal` are mounted in `ObjectBrowserView`
with no code path that opens them; the bucket header drives the live instances. This diff removed
the one it touched rather than all seven.

A later round added two more, both about this diff rather than the code around it:

- **`checkDeletedContent` bounded its request but not its response.** The input keeps a cap
  (`folders` at 1000), and the new `prefix` mode — now the only mode the client uses — returns one
  entry per direct-child folder the scan discovered, up to the ~20 000 records the page ceiling
  allows. The client looks up only the prefixes it has actually loaded, so the rest is payload it
  discards. It is the same "cost grows with the bucket, not with the question" shape this PR fixed
  on the scan side, surviving on the other side of the same procedure. The obvious cheap fix —
  omit entries in the all-default state, since the object browser already renders a folder with no
  status entry — is **not** equivalent and was rejected on inspection: an absent entry makes the
  All tab *show* a folder, while a present entry with no `folderMarkerVersionId` makes it *hide*
  one, and folders in exactly that state do occur (a folder holding a single non-latest delete
  marker and no folder-marker object). A real fix needs an explicit cap plus an explicit "unknown"
  for what it drops, which is a contract change worth doing deliberately rather than in this diff.
- **The page→key-group logic in `deleteNonCurrentVersions` belongs in a helper.** This is not the
  shared-paginator item above: combining a page, sorting it in byte order, grouping by key, merging
  the carried-over group and deciding keep/delete are pure functions of one `ListObjectVersionsOutput`
  plus the carry — no S3 client, no `ctx`. This branch already established that such logic belongs
  in `Storage/helpers/` when it extracted `folderPrefixOf` / `isFolderCovered` / `longestCommonPrefix`,
  and the cost of not doing it for the harder case is visible: a large share of the new tests in
  `objectRouter.test.ts` sequence `mockSend` responses to exercise decisions that need no S3 at
  all. Unlike the shared paginator, extracting it touches nothing that `deleteAll` depends on, so
  it is independently landable.

One smaller note, unchanged in this diff: the new `console.error` calls log the caught AWS SDK
error object whole rather than a picked subset. It is server-side only, never reaches the client,
and `mapS3ErrorToTRPCError` sanitises what does — but it is a new instance of a pattern that
already appears in half a dozen places under `server/Storage`, and the place to change it is all of
them at once.

---

## Genuinely out of scope — noted, not touched

**`nextContinuationToken` is conflated with `NextKeyMarker`.** In the `showVersions` branch, `objectRouter.ts` assigns `nextContinuationToken: response.NextKeyMarker` while also assigning the same value to `nextKeyMarker`. Related: when a `delimiter` is set, versions are filtered client-side *after* S3 has already cut the page at `MaxKeys`, so a page can come back visually empty with `isTruncated: true`. Neither is triggered by the call sites involved here (they use `delimiter: ""`), and the object browser's current tab-based branching stays consistent.

**No request timeout or retry tuning on the shared S3 client.** `s3Client.ts` sets no `requestTimeout` and leaves `maxAttempts` at the SDK default of 3, multiplying every listing loop by up to 3×. `connectionTimeout: 5000` was added here because it only bounds TCP connection establishment and is safe for streams. `requestTimeout` was deliberately not changed: in `@smithy/node-http-handler` it is a socket-inactivity timeout, and the same client is shared with the streaming upload/download paths. Narrowing `maxAttempts` globally would likewise make object transfers less resilient. Both deserve their own investigation against the installed SDK version rather than a drive-by change.

**Two more from the manual verification pass, both pre-existing on `dc918d47`.**

- **`DeleteVersionModal` is always titled "Delete Version", including for a delete marker.** The
  menu item that opens it gets this right — `ObjectVersionHistoryModal` renders
  ``label={isDeleteMarker ? t`Delete Marker` : t`Delete Version`}`` — and the modal does receive
  `isDeleteMarker`, using it to hide the Date and Size rows that a marker has no values for. It is
  simply never consulted for the wording: the title, the confirm button and the body text all
  branch on `isDeletingAllVersions` alone, so clicking "Delete Marker" opens a dialog offering to
  delete a "version" that does not exist. A ten-minute fix (the same ternary in three more places,
  plus `pnpm check-i18n` for the new strings), but this branch touched only the invalidation block
  in that file and the defect predates it.
- **`GetBucketVersioning` is still issued twice per bucket page load.** `containers.getState` needs
  it to decide whether there is any history worth scanning; `ObjectBrowserView` separately queries
  `versioning.getStatus` to decide whether to enable `checkDeletedContent`. The round-3 cleanup
  collapsed this for the bucket header and the empty-bucket modal, both of which went through
  `useBucketInfo` — the object browser holds its own `useQuery` and was not reached. `getState`
  already returns the three-way `status`, so the same substitution applies; it is just outside what
  #1004 asked for.
