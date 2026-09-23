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
