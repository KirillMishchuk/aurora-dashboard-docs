## Summary

User feedback from `dashboard-aurora.eu-de-1.cloud.sap`:

> The file overview for our bucket is briefly shown but then disappears. I can only see deleted files.

Reproduced by the reporter: three folders are visible in the Elektra Ceph UI, they are visible in the responses of Aurora's own API calls, and yet in Aurora's object browser they appear for a split second and are then replaced with "No objects found."

The whole report comes from one condition in the `All` tab's folder filter:

```ts
return !status.isFolderDeleted && status.folderMarkerVersionId !== undefined
```

`folderMarkerVersionId` is set by `versioning.checkDeletedContent` only when the bucket contains an object whose key is *exactly* the folder prefix — the zero-byte `folder/` placeholder. Nothing in S3 requires such an object to exist: a folder is a naming convention over keys. The only thing that writes one is Aurora's own "Create folder" button. Upload `folder/file.txt` with Elektra, `s3cmd`, `rclone` or any SDK and there is no placeholder, so `folderMarkerVersionId` comes back `undefined` and the client discards a folder that is fully alive.

**Why it flickers.** Two queries race. `objects.list` returns first and the folders render, because the filter is skipped while `checkDeletedContent` has no data yet. When the scan answers, the filter runs and removes them.

**Why the header disagrees with the table.** `totalItemCount` is computed from the unfiltered list, so the header keeps reporting the real number of items above an empty table — which is what "the file overview is briefly shown" describes from the other side.

**The filter was never needed.** The `All` tab is served by `ListObjectsV2`, which only ever returns current versions. A `CommonPrefix` coming back from it therefore already proves there is live content under that prefix, and a folder whose keys are all covered by delete markers never appears in the listing at all. Hiding deleted folders is the server's job and the server already does it; the client's second pass could only ever be wrong.

A second victim of the same condition: `!status.isFolderDeleted` hid a folder whose *placeholder object* carried a delete marker, even when live objects remained inside it. What happened to one bookkeeping key says nothing about the rest of the folder.

Regression introduced in `f66da80a` (#1121).

## Changes Made

**Client — `ObjectBrowserView.tsx`** (the only source file touched)

- `deletedFoldersList`, branch `tab !== "deleted"`, is now `return allFolders`. Gone with it: the `folderMarkerVersionId !== undefined` requirement, the `isFolderDeleted` check, the `isPartialScan` escape hatch, and the "show everything while loading" fallback that produced the flicker. A comment records *why* there is no filter, so it doesn't get reinstated as a bug fix later.
- `versioning.checkDeletedContent` gained `tab === "deleted"` in its `enabled` gate. Its result no longer has a reader on the `All` tab, so the query has no reason to run there. This removes up to `S3_MAX_SCAN_PAGES` (20) paginated `ListObjectVersions` requests over the whole prefix from every ordinary folder view.

**Tests — `ObjectBrowserView.test.tsx`** (40 → 43)

- `hides folders with no versions (permanently deleted) from All tab` asserted exactly the reported bug. Same fixture, inverted assertions, renamed to `All tab: shows every folder the listing returned, including folders with no folder-marker object`.
- `All tab: still hides a folder that is confirmed deleted by a complete scan` is inverted the same way, keeping its data untouched — see the note below.
- `All tab: shows a folder whose scan is partial...` keeps its assertion and is re-commented: it now guards against the Deleted tab's unresolved-scan handling being copied back into the `All` branch.
- New: a folder entirely covered by delete markers is absent because the listing never returns it (the removed client filter isn't missed); `enabled` is `false` for `checkDeletedContent` on `All`; `enabled` is `true` on `Deleted`.

**Changeset** — `patch`.

## Note for reviewers

**This is not a partial revert of #1331.** Everything #1331 did substantively survives: the bounded scan, the `prefix`-based input, the removal of the per-folder `try/catch`, the `isPartialScan` contract. What goes away is one two-line mitigation *inside a filter this PR deletes in full* — `if (status.isPartialScan) return true`, which made a partial scan stop hiding live folders. This PR removes the hiding altogether, so the mitigation has nothing left to mitigate. #1331's changeset stays true as written. Its test for the `All` branch is inverted rather than deleted, with its fixture (`confirmed-deleted/`, `dm-1`, `v-1`) preserved verbatim so the diff shows one assertion and one name changing.

**`checkDeletedContent.isPartialScan` keeps no client reader after this PR.** Do not drop the field — the remaining consumer is the Deleted tab's handling of partially scanned folders, which is deliberately still open (`FOLLOW-UPS.md` item 1) and needs a product decision, not a code change.

**Reproducing.** Any versioned bucket whose folders were created by something other than Aurora's "Create folder" button. Concretely: upload `docs/report.pdf` with `s3cmd` into a versioned bucket, delete every object in the bucket root, then open the `All` tab — before this change the tab is empty with the header still counting the folder.

## Not changed

- **No server changes.** `versioningRouter.checkDeletedContent` is untouched; it is simply no longer called from the `All` tab.
- **The Deleted tab is untouched.** Its own filtering, the `isDeleted`/`deleteMarkerVersionId` annotations and Restore Folder all behave exactly as before.
- **No new destructive surface.** `s3FolderPrefixSchema` carries no `isDeleted`, so the folders that become visible again render the ordinary `canDeleteFolder`-gated "Delete Folder" action. Restore and permanent-delete remain reachable only from the Deleted tab.
- **Swift is unaffected** — no versioning, no equivalent logic.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
