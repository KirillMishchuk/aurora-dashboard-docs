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
