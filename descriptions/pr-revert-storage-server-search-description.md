# Summary

Reverts the Storage half of #1320: Ceph Buckets and Swift Containers go back to filtering the loaded list on the client, as they did before that PR. Nothing else from #1320 is touched — Flavors, Images, Projects and Floating IPs keep their expanded search, and `filterBySearchParams` keeps its numeric branch.

Moving these two lists to server-side filtering made the search input itself unusable on every keystroke, and on Ceph it made each search re-run a full S3 fan-out.

**Why the search box unmounts.** `searchTerm` is part of the TanStack Query key, so every debounced search commit is a cache miss and `isLoading` goes back to `true`. Both pages return early on that flag — `Ceph/Buckets/index.tsx:231`, `Swift/Containers/index.tsx:253` — so the whole toolbar, including the `SearchInput` the user is typing into, is replaced by a loading `Status`. Focus is lost and the page flashes on every pause in typing. No `placeholderData`/`keepPreviousData` was set.

**Why it is expensive on Ceph.** The filter was applied *after* the metadata loop that issues a `ListObjectsV2` per bucket in batches of five (`containerRouter.ts:62-128`). Each new search term therefore repeated the entire fan-out across all buckets. Before #1320 a search issued no request at all.

**Why the selection behaviour got worse.** `selectedBucketSummaries` resolves the selection against `buckets`, which is documented in place as "the full unfiltered list". After #1320 that list is the server-filtered one, so a selection made before searching silently dropped out of bulk actions. The fix that landed with #1320 (`Ceph/Buckets/index.tsx:79-84`, `Swift/Containers/index.tsx:80-85`) clears the selection on every search change instead — the opposite of the behaviour the comment describes. Client-side filtering removes the conflict: the full list is in memory again, so a selection survives a search, and the comment is true again.

# Changes Made

## Server

- `Storage/types/ceph.ts`, `Storage/types/swift.ts` — drop `searchTerm` from both `listContainersInputSchema`s. Additive removal of an optional field; no other call site passed it (`CopyObjectModal`, `MoveObjectModal`, `useBucketInfo` never did).
- `Storage/routers/ceph/containerRouter.ts` — `containers.list` returns the bucket list unfiltered again, on both the fast path and the metadata path.
- `Storage/routers/swift/swiftRouter.ts` — `listContainers` returns the parsed container list unfiltered again.

`filterBySearchParams` itself is unchanged, including the numeric branch #1320 added: Images, Projects and Flavors still depend on it.

## Client

- `Ceph/Buckets/index.tsx`, `Swift/Containers/index.tsx` — stop sending `searchTerm` in the query, filter by name in the component again, drop the effect that cleared the selection on every search change, and restore the "X of Y buckets/containers" counter that reports how much of the loaded list the current search matches.

## i18n

- Restores the two msgids removed by #1320 (`{filteredCount} of {totalCount} container(s)`, `{filteredCount} of {totalCount} bucket(s)`) in `en` and `de`, both with their existing German translations, and recompiles the catalogs. `pnpm check-i18n` regenerates them byte-identically.

## Changesets

None. #1320 has not been released yet, so nothing that reaches a consumer changes here and there is no released behaviour to describe. Its two pending changesets are left exactly as they are.

## Tests

The two suites (`Ceph/Buckets/index.test.tsx`, `Swift/Containers/index.test.tsx`) go back to asserting client-side filtering: the mocked tRPC response carries the full list again and the tests assert the component narrows it, which is what they now exercise. Full suite green (232 files / 5618 tests in `@cobaltcore-dev/aurora`), plus `typecheck`, `lint`, `format:check` and `check-i18n`.

# Deliberately out of scope

- **Search coverage for these two lists goes back to name only.** #1320's extra columns for buckets/containers (`count`, `bytes`, `last_modified`, `creationDate`) matched raw values, not what the table renders: `bytes` is displayed human-readable and dates are formatted, so "1.5 KB" or a UI-formatted date matched nothing while "0" matched almost everything. If the expanded coverage is wanted back, it belongs in the client filter, against the rendered values.
- **Projects (`listProjectsWithSearch`)** keeps its server-side search, including the Suspense fallback on every keystroke. Same class of problem, different page, and reverting it would mean restoring a procedure #1330 is in the middle of removing.

# Note on #1330

#1330 (open) builds on the reverted code and will conflict with this PR in `Ceph/Buckets/index.tsx` and `Swift/Containers/index.tsx`. Two of its Storage changes are affected:

- the `aria-live` region was reported as not announcing anything for a new search precisely because the early `isLoading` return unmounts it. With client-side filtering there is no refetch and no unmount, so the region stays mounted and the announcement works — the reason for that finding disappears.
- the region and the `hasActiveSearch` empty states read `totalCount`, which is the full list again after this PR; they need `filteredCount` to keep saying what they mean.

Its Flavors and Projects changes are independent of this PR.
