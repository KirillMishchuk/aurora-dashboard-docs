# Summary

Fixes the object browser hiding live folders on the "All" tab of a versioned bucket. Reported from `dashboard-aurora.eu-de-1.cloud.sap`:

> The file overview for our bucket is briefly shown but then disappears. I can only see deleted files.

Three folders are visible in the Elektra Ceph UI and in the responses of Aurora's own API calls, but in Aurora they render for a split second and are replaced by "No objects found."

The "All" tab filtered the listing a second time, against `versioning.checkDeletedContent`, and required each folder to have a zero-byte placeholder object whose key equals the prefix (`folder/`). Nothing in S3 requires one to exist — a folder is a naming convention over keys — and the only thing that writes one is Aurora's own "Create folder" (`objectRouter.ts:1047`). Upload `folder/file.txt` with Elektra, `s3cmd`, `rclone` or any SDK and there is no placeholder, `folderMarkerVersionId` comes back `undefined` (`versioningRouter.ts:446-447`), and a fully alive folder is discarded.

**Why the second filter was never needed.** The "All" tab is served by `ListObjectsV2` (`objectRouter.ts:313`), which only ever returns current versions. A `CommonPrefix` coming back from it therefore already proves there is live content under that prefix, and a folder whose keys are all covered by delete markers never appears in the listing at all. Hiding deleted folders is the server's job and the server already does it; the client's second pass could only ever be wrong in one direction.

**Why it flickers.** Two queries race. `objects.list` returns first and the folders render, because the filter is skipped while `checkDeletedContent` has no data yet (`ObjectBrowserView.tsx:358` was the same fallback on the "All" branch). When the scan answers, the filter runs and removes them.

**Why the header disagrees with the table.** `totalItemCount` (`ObjectBrowserView.tsx:409`) is computed from the unfiltered list, so the header goes on reporting the real number of items above an empty table — which is "the file overview is briefly shown" seen from the other side.

**A second folder shape hit by the same condition.** `!status.isFolderDeleted` also hid a folder whose *placeholder object* carried a delete marker, while live objects remained inside it. What happened to one bookkeeping key says nothing about the rest of the folder.

Regression from `f66da80a` (#1121).

# Changes Made

## Client

- **`ObjectBrowserView.tsx`** — `deletedFoldersList`, branch `tab !== "deleted"`, is now `return allFolders` (`:345-355`). Gone with it: the `folderMarkerVersionId !== undefined` requirement, the `isFolderDeleted` check, the `isPartialScan` escape hatch, and the "show everything while loading" fallback that produced the flicker. The branch carries a comment recording why there is no filter, so it is not reinstated later as a bug fix.
- **`ObjectBrowserView.tsx`** — `versioning.checkDeletedContent` gains `tab === "deleted"` in its `enabled` gate (`:167`). Its result no longer has a reader on the "All" tab, so the query has no reason to run there: an ordinary folder view stops issuing up to `S3_MAX_SCAN_PAGES` (20) paginated `ListObjectVersions` requests over the whole prefix. The "Deleted" tab is unchanged — same input, same filtering, same `isDeleted` / `deleteMarkerVersionId` annotations, same Restore Folder.

`checkDeletedContent` keeps its `isPartialScan` field. After this PR the "All" tab is its only lost reader; the "Deleted" tab's handling of partially scanned folders is deliberately still open and needs a product decision, so the field stays.

## Tests

`ObjectBrowserView.test.tsx`, 40 → 43 cases.

- `hides folders with no versions (permanently deleted) from All tab` asserted exactly the reported bug. Same fixture, inverted assertions, renamed to `All tab: shows every folder the listing returned, including folders with no folder-marker object`.
- `All tab: still hides a folder that is confirmed deleted by a complete scan` is inverted the same way, with its fixture (`confirmed-deleted/`, `dm-1`, `v-1`) preserved verbatim so the diff shows one assertion and one name changing.
- `All tab: shows a folder whose scan is partial...` keeps its assertion and is re-commented: it now guards against the "Deleted" tab's unresolved-scan handling being copied back into the "All" branch.
- New: a folder entirely covered by delete markers is absent because the listing never returns it, not because of any client-side check; `enabled` is `false` for `checkDeletedContent` on "All"; `enabled` is `true` on "Deleted" (asserted on the last call — `allFolders` is still empty on first render, so the flag only flips once the accumulation effect has run).

Full suite green (236 files / 5749 tests in `@cobaltcore-dev/aurora`), plus `typecheck`, `lint`, `format:check` and `check-i18n`. Restoring the old filter turns exactly the two inverted cases red and nothing else.

# Note on #1331

This is not a partial revert of #1331. Everything it did substantively survives: the bounded scan, the `prefix`-based input, the removal of the per-folder `try/catch`, the `isPartialScan` contract. What goes away is one two-line mitigation *inside a filter this PR deletes in full* — `if (status.isPartialScan) return true`, which stopped a partial scan from hiding live folders. Removing the hiding altogether leaves it nothing to mitigate. Its test for the "All" branch is inverted rather than deleted.

# Testing Instructions

1. `pnpm i`
2. `pnpm run test`
3. Manual scenario — any versioned bucket whose folders were created by something other than Aurora's "Create folder":
   - upload `docs/report.pdf` with `s3cmd` (or any non-Aurora client) into a versioned bucket and delete every object in the bucket root;
   - open the "All" tab → the folder is listed and stays listed, with no flicker, and the header count matches the number of rows. Before this change the tab settles on "No objects found." while the header still counts the folder;
   - delete a folder's contents entirely → it disappears from "All" and appears under "Deleted", as before;
   - in the network panel, opening "All" issues no `versioning.checkDeletedContent`; switching to "Deleted" issues one.

# Checklist

- [x] I have performed a self-review of my code.
- [x] I have commented my code, particularly in hard-to-understand areas.
- [x] I have added tests that prove my fix is effective or that my feature works.
- [x] New and existing unit tests pass locally with my changes.
- [x] I have made corresponding changes to the documentation (if applicable).
- [x] My changes generate no new warnings or errors.
