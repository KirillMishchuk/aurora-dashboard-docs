---
type: pr-report
date: 2026-09-24
status: open
pr: [1330]
author: TilmanHaupt
branch: til-search-robustness
---
# PR #1330: refactor(portal): improve search architecture consistency and UX

**Author:** TilmanHaupt · **Status:** open, out of draft; approved by vlad-schur-external-sap 2026-09-24 (created 2026-09-24)
**Branches:** `til-search-robustness` → `main` · **Files:** 15 (at head `b424b47`)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1330
**Base:** `6ce6aeac`, i.e. the merge commit of [#1320](./1320-search-all-visible-columns.md) (merged 2026-09-23). This PR is a continuation of #1320.

> **CI:** on the first head `2572b6f`, the `test` job failed in three tests, even though the PR description says "All existing tests pass". Commit `b424b47` (2026-09-24, "fix(aurora): resolve test failures from ARIA live regions") fixed this: all CI checks are green. Details — in "What it affects".

## What was done

This is follow-up work after #1320. The PR itself describes itself as a response to the review of commit `6ce6aeac`. There are four kinds of changes:

1. **Server, Projects.** The `project.searchProjects` procedure was removed (no client consumers, its own inline filter). `getAuthProjects`, however, **remains**: it has no client consumers, and it duplicates `listProjectsWithSearch` almost line for line. So the "After" table in the description ("Projects — 1 endpoint with shared helper") does not match the code: there are still two project-loading procedures.
2. **Server, Flavors.** The custom regex helper `includesSearchTerm` was replaced with the shared `filterBySearchParams` with the same seven fields. Its six tests were deleted.
3. **Client, Storage: accessibility.** A hidden `aria-live="polite"` region was added to the Ceph Buckets and Swift Containers toolbars, announcing "Found N buckets matching "…"" or "N buckets total".
4. **Client, Storage: empty states.** `BucketTableView` and `ContainerTableView` got a `hasActiveSearch` prop. With an active search, "No … matching search / … match your search criteria" is shown; without a search — "No … found / There are no … available in this project".

Plus a `patch` changeset and i18n catalogs. In `en`, 8 msgids were added and 2 renamed. In `de`, all 8 new strings have an empty `msgstr`, meaning the German UI will show English text. Only the two renamed strings about an empty project were translated.

## How it is implemented

Code is quoted as of commit `2572b6f`.

### Flavors on the shared helper

`packages/aurora/src/server/Compute/helpers/flavorHelpers.ts:163-193`:

```ts
export function filterAndSortFlavors(
  flavors: Flavor[],
  searchTerm: string,
  sortBy: keyof Flavor,
  sortDirection: string
): Flavor[] {
  // Use shared filterBySearchParams helper for consistent search behavior
  const filtered = filterBySearchParams(flavors, searchTerm, [
    "id",
    "name",
    "description",
    "vcpus",
    "ram",
    "disk",
    "swap",
  ])

  filtered.sort((a, b) => {
```

The description calls the replacement of regex with substring matching "functionally equivalent". In reality the behavior changes, and for the better:

- previously `new RegExp(searchTerm, "i")` crashed on input like `(` or `[`, and `.` matched anything;
- now the search is a literal substring match, and surrounding whitespace is trimmed (`filterBySearchParams` does `trim()`).

`swap` in the schema (`types/flavor.ts:17`) is `string | number`, and the helper handles both types. `sort` still mutates the array in place. Without a search, the helper returns the same array, so the input mutation stays as it was. The array comes fresh from the API (`flavorRouter.ts:105`), so this has no effect.

In `flavorHelpers.test.ts:74`, the `describe("fetchFlavors")` block was renamed to `describe("filterAndSortFlavors")`. It still contains the `fetchFlavors` HTTP tests, and the file now has two describes with the same name (`:74` and `:212`). Flavor search is covered only by the tests at `:219` and `:255`. Numeric fields are not checked in them.

### ARIA live region

`packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/index.tsx:389-403`:

```tsx
            <div className="text-theme-light flex items-center gap-1" data-testid="buckets-info-block">
              <Plural value={totalCount} one={`${totalCount} bucket`} other={`${totalCount} buckets`} />
            </div>
            {/* ARIA live region for screen readers */}
            <div className="sr-only" aria-live="polite" aria-atomic="true">
              {searchParam?.trim() ? (
                <Plural
                  value={totalCount}
                  one={`Found ${totalCount} bucket matching "${searchParam}"`}
                  other={`Found ${totalCount} buckets matching "${searchParam}"`}
                />
              ) : (
                <Plural value={totalCount} one={`${totalCount} bucket total`} other={`${totalCount} buckets total`} />
              )}
            </div>
```

In Swift, the equivalent is at `Swift/Containers/index.tsx:406`. The region sits inside the toolbar, and the toolbar is rendered only after the early return `if (isLoading)` (`Ceph/Buckets/index.tsx:238-240`, `Swift/Containers/index.tsx:260`). That return came from #1320, after `searchTerm` became part of the query key.

### Empty states

`Ceph/Buckets/BucketTableView.tsx:149-157`:

```tsx
                  <Status
                    status="empty"
                    title={hasActiveSearch ? t`No buckets matching search` : t`No buckets found`}
                    body={
                      hasActiveSearch
                        ? t`No buckets match your search criteria. Try adjusting your search term.`
                        : t`There are no buckets available in this project.`
                    }
                  />
```

The prop is passed as `hasActiveSearch={!!searchParam}` (`Ceph/Buckets/index.tsx:423`, `Swift/Containers/index.tsx:444`), without `trim()`. The live region, meanwhile, checks `searchParam?.trim()`, so for a whitespace-only search these two flags diverge. The server ignores such a search.

## What it affects

- **Three failing tests at `2572b6f` (CI `test`, verified via check run annotations); fixed in `b424b47`.** Initially the tests were not updated for the new strings:
  - `Swift/Containers/index.test.tsx:647` expects `/No containers found/i` with an active search, but the title is now "No containers matching search";
  - `Ceph/Buckets/index.test.tsx:374` and `:388`: `getByText(/3 buckets/i)` finds two elements — the visible "3 buckets" and the hidden "3 buckets total" from the live region.

  In `b424b47`, the Ceph tests look for the text inside `buckets-info-block` (`within(...)`), and the Swift test expects `/No containers matching search/i`. The component code was not changed by this commit.

  `ContainerTableView.test.tsx:216/221` pass: there is no `hasActiveSearch` prop there, and the no-search variant is shown by default. There is no separate test with `hasActiveSearch` for it; there is one only in `BucketTableView.test.tsx`.
- **`project.searchProjects` removed.** This is a contract change to `AuroraRouter`. Within the monorepo there are no consumers (grep at head), but an external application that imports the router type and calls this procedure will break at build time. The changeset, meanwhile, is `patch`.
- **`includesSearchTerm` removed** from the `flavorHelpers.ts` exports. Only the test file imported it.
- **`BucketTableView` / `ContainerTableView`**: a new optional prop defaulting to `false`, so other usage sites are not affected.
- **Issues from the #1320 report** (checked at `b424b47`):

  | #1320 issue | Status |
  | --- | --- |
  | Full-page spinner on every search (Ceph/Swift), repeated S3 polling | Not resolved: `searchTerm` in the query key (`Ceph/Buckets/index.tsx:164`, `Swift/Containers/index.tsx:179`), early `if (isLoading)` (`:238`, `:260`), no `placeholderData`. Now it also gets in the way of the new feature (see review). |
  | Selection is lost with server-side filtering | Partially resolved **already in #1320** before merge: the selection is cleared when the search changes (`Ceph/Buckets/index.tsx:79-84`, `Swift/Containers/index.tsx:80-85`). The comment "from the full unfiltered list" (`:276`, `:274`) is outdated. #1330 changes nothing here. |
  | Projects: Suspense and two Keystone requests per search | Not resolved: `useSuspenseQuery` with `searchTerm` (`projects/index.tsx:37`), `navigate` without `startTransition`. |

## Review

The review was done in a single pass along the skill's five directions, followed by confidence scoring. Findings caught by CI (failing tests) are not included in the review per the skill's rules: they are described above.

**1. The live region does not announce the main scenario — a new search query (80/100).**
The region is rendered inside the toolbar, and the whole component goes into the early return `if (isLoading)` (`Ceph/Buckets/index.tsx:238-240`, `Swift/Containers/index.tsx:260`). Every new search query is a new query key with no cache. `isLoading` becomes `true`, and the region unmounts, then after loading it mounts again with the text already in place. `aria-live` announces *changes* to the content of a region that is already in the DOM. A region inserted with its content already present is usually not announced by screen readers (NVDA, JAWS, VoiceOver). As a result, the announcement will fire only when returning to an already cached query, but not for a new search — the very thing the feature was added for. To fix it, the region needs to stay mounted outside the loading branch, or the early return should be removed, e.g. via `placeholderData: keepPreviousData`.

Below the threshold. Not part of the review, but worth keeping in mind:

- `getAuthProjects` remains a dead duplicate of `listProjectsWithSearch`, while the description claims otherwise (65).
- In `de`, the 8 new strings have an empty `msgstr` (50).
- Two identical `describe("filterAndSortFlavors")` in `flavorHelpers.test.ts` (40).
- `hasActiveSearch` without `trim()` diverges from the live region condition (35).

---
**Copilot review** (on the first commit `a6b093a`; commit `2572b6f` is titled "apply Copilot code review suggestions"):

| Copilot comment | Status at `b424b47` |
| --- | --- |
| Outdated empty-state test in `BucketTableView.test.tsx` | Fixed |
| Live region announces a whitespace-only search | Fixed in the live region (`searchParam?.trim()`), but `hasActiveSearch={!!searchParam}` remained without `trim()` |
| German translation of the no-search empty state lost | Fixed for the two renamed strings; the 8 new strings still have an empty `msgstr` in `de` |
| `describe("fetchFlavors")` renamed by mistake | Not fixed |

The PR description has not been updated: it still says "All existing tests pass" and "Projects — 1 endpoint".

---
Analyzed: 2026-09-24 · commit `2572b6f`, updated for `b424b47` (test fix; component code unchanged, review findings still stand)
