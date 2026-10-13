---
type: pr-report
date: 2026-09-23
status: merged
pr: [1320]
author: TilmanHaupt
branch: til-all-search
---
# PR #1320: feat(portal): expand search to all visible columns including numeric

**Author:** TilmanHaupt · **Status:** merged 2026-09-23 (andypf; created 2026-09-23). The report was written while the PR was open.
**Branches:** `til-all-search` → `main` · **Files:** 20 (+195/-73)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1320
**Closes:** #1226 ("Ensure search placeholder instructs user what to search by")

## What was done

Issue #1226 proposed two options: either search across *all* displayed fields, or state in the placeholder which fields are searched. The PR takes the first option. The placeholders were not changed (for example, `Search...` in `ProjectOverviewNavBar.tsx:51`), and the issue's second point (a consistent placeholder style) is not addressed.

By area:

1. **The shared helper `filterBySearchParams`** now also searches numeric fields: the number is converted to a string and checked as a substring. Ceph, Swift, Images, Projects and Floating IPs depend on this.
2. **Compute.** Flavors are now also searched by `vcpus`/`ram`/`disk`/`swap` (flavors have their own regex helper rather than `filterBySearchParams`). Images are now also searched by `id`/`owner`/`size`, but only in two of the three procedures (see below).
3. **Storage (Ceph + Swift): name filtering moved from the client to the server.** `searchTerm` was added to the `listContainersInputSchema` input schemas (both). The routers filter via `filterBySearchParams` by name/count/bytes/last_modified (Ceph also by creationDate). The client passes `searchParam` to `useQuery` and no longer filters on its own. The "X of Y buckets/containers" counter was removed; what remains is just "N buckets". Two msgids were therefore removed from the `en`/`de` catalogs.
4. **Projects: a new procedure `project.listProjectsWithSearch`.** The `/projects` page used to load all projects via `getAuthProjects` and filter them on the client by name/description. Now `searchTerm` is sent to the server, and the search covers id/name/description/domain_name/domain_id.
5. **Network.** Floating IPs are now also searched by `id`. The PR description says "no changes", but the change is in the diff.
6. A `minor` changeset for `@cobaltcore-dev/aurora` and tests: numeric search in `filterBySearchParams.test.ts`; the tRPC mocks in the Ceph/Swift tests now return an already filtered list.

The changeset diverges from the code. It claims "Images: owner and size", while the PR description adds "excluded filter arrays (status, visibility, disk_format)". In the shared images branch (`listSharedImagesByMemberStatus`) the search still covers only `id`/`name`.

## How it is implemented

Code is quoted as of commit `e0737fe`.

### `filterBySearchParams`: the numeric branch

`packages/aurora/src/server/helpers/filterBySearchParams.ts:26-39`:

```ts
  return items.filter((item) =>
    searchFields.some((field) => {
      const value = item[field]
      // Handle strings
      if (typeof value === "string") {
        return value.toLowerCase().includes(searchLower)
      }
      // Handle numbers by converting to string
      if (typeof value === "number") {
        return value.toString().includes(searchLower)
      }
      return false
    })
  )
```

This is a substring search on the *raw* value. Searching for `"512"` finds both `512` and `5120`, and `"0"` finds almost everything. In the Ceph and Swift UI, `bytes` is shown in human-readable form and dates are formatted. So "search by visible columns" here actually means search by raw data: a query like "1.5 KB" or a date in the UI format will find nothing, while a year from the ISO string will.

In the tests (`filterBySearchParams.test.ts`) the expectations are computed correctly. Copilot wrote in its review that the `"1"` case should fail because `medium` (count=512) supposedly does not match. This is a false positive: `"512"` contains `"1"`.

### Flavors: a separate regex helper

`packages/aurora/src/server/Compute/helpers/flavorHelpers.ts:162-181`:

```ts
export function includesSearchTerm(flavor: Flavor, searchTerm: string): boolean {
  const regex = new RegExp(searchTerm, "i")

  // Search across all visible fields in the flavor list: id, name, description, vcpus, ram, disk, swap
  const searchableValues = [
    flavor.id,
    flavor.name,
    flavor.description,
    flavor.vcpus,
    flavor.ram,
    flavor.disk,
    flavor.swap,
  ]
```

Flavors were not moved to `filterBySearchParams`, even though the PR claims "unified search". `new RegExp(searchTerm)` without escaping was already there before: typing `(` will throw an exception. The PR did not change this line, but more fields now pass through it.

### Images

`packages/aurora/src/server/Compute/routers/imageRouter.ts:128` (`listImagesWithSearch`) and `:244` (`listImagesWithPagination`):

```ts
          filteredImages = filterBySearchParams(filteredImages, queryInput.name, ["id", "name", "owner", "size"])
```

`imageRouter.ts:1006` (`listSharedImagesByMemberStatus`):

```ts
          filteredImages = filterBySearchParams(filteredImages, name, ["id", "name"])
```

### Ceph: server-side filtering after the metadata fan-out

`packages/aurora/src/server/Storage/routers/ceph/containerRouter.ts:130-136`:

```ts
      return filterBySearchParams(bucketsWithMetadata, searchTerm, [
        "name",
        "count",
        "bytes",
        "last_modified",
        "creationDate",
      ])
```

The filter comes *after* the loop that runs `ListObjectsV2` for each bucket in batches of 5 (`containerRouter.ts:62-128`). So every new search query repeats the entire S3 fan-out. Previously the search was purely client-side and never hit the server. On the fast path without metadata (`:57`) the filter applies only to `name`.

Client, `Ceph/Buckets/index.tsx:153-163` and `:200-201`:

```tsx
  } = trpcReact.storage.ceph.containers.list.useQuery(
    {
      project_id: projectId,
      includeMetadata: true, // Fetch full metadata for table view with sorting
      searchTerm: searchParam, // Server-side filtering
    },
    {
      enabled: !!projectId,
      retry: false, // Don't retry on NO_CEPH_CREDENTIALS error
    }
  )
...
  // Buckets are already filtered server-side via searchTerm
  const filteredBuckets = buckets || []
```

`searchParam` gets into the URL via SearchInput with a 500 ms debounce (`index.tsx:330`), so a new query key appears after every pause in typing.

### Swift

`packages/aurora/src/server/Storage/routers/swift/swiftRouter.ts:134` pulls `searchTerm` out of the input so that it does not end up in the Swift API query string. The filter is applied on line `:168`:

```ts
        return filterBySearchParams(parsedData.data, searchTerm, ["name", "count", "bytes", "last_modified"])
```

The client (`Swift/Containers/index.tsx:169-173`) works the same way as Ceph's: it passes `searchTerm: searchParam`.

### Projects

`packages/aurora/src/client/routes/_auth/projects/index.tsx:36-42`:

```tsx
function ProjectsContent({ searchTerm }: ProjectsContentProps) {
  const [projects] = trpcReact.project.listProjectsWithSearch.useSuspenseQuery({
    searchTerm: searchTerm.trim() || undefined,
  })

  return <ProjectCardView projects={projects} />
}
```

`packages/aurora/src/server/Project/routers/projectRouter.ts:195` defines `listProjectsWithSearch`. The procedure body repeats `getAuthProjects` (`:89-129`) line for line: the same token checks, the same `Promise.all` on `auth/projects` and `auth/domains`, the same `domainMap`, the same `domain_name` enrichment (compare `:127` and `:239`). A filter is added at the end (`:243`):

```ts
      return filterBySearchParams(projectsWithDomain, input.searchTerm, [
        "id",
        "name",
        "description",
        "domain_name",
        "domain_id",
      ])
```

## What it affects

- **`storage.ceph.containers.list`.** An optional field was added to the input, so the contract is extended in a backward-compatible way. Other consumers (`Ceph/Objects/CopyObjectModal.tsx:72`, `MoveObjectModal.tsx:75`, `Ceph/hooks/useBucketInfo.ts:50`) do not pass `searchTerm` and their behavior does not change. All `invalidate()` calls in the modals (Create/Delete/Empty/DeleteVersions bucket, object operations) are made without input and still hit all key variants, including keys with `searchTerm`. The bucket list cache and `useBucketInfo` already lived under different keys before (`includeMetadata: true` versus the field being absent); nothing changed here.
- **`storage.swift.listContainers`.** The situation is the same. `EditContainerMetadataModal.tsx:88`, `Swift/Objects/CopyObjectModal.tsx:97` and `MoveRenameObjectModal.tsx:106` are unaffected; invalidations without input work.
- **`project.getAuthProjects`.** After the PR the procedure has no client consumers left (a grep across the monorepo finds only the definition and `projectRouter.test.ts`). The router now has three overlapping project-loading procedures: `getAuthProjects`, `searchProjects` (no domain enrichment, with sorting, also without client consumers) and the new `listProjectsWithSearch`. Copilot pointed out this duplication; it is not resolved in the PR. There are no router tests for the new procedure.
- **External consumers of `AuroraRouter`.** The new procedure in `project.*` and the new input fields are an additive extension of the router's public type; nothing breaks.
- **i18n.** Two msgids were removed ("X of Y container(s)", "X of Y bucket(s)"), the `messages.ts` catalogs were recompiled, and `check-i18n` should not fail.
- **The selection UX contract (bulk actions) in Storage** changed silently; details in the review.
- **The client tests** now mock an already filtered server response. They check rendering, but not that `searchTerm` is actually sent in the request.

## Review

The review was done in a single pass across the five directions from the skill (CLAUDE.md, bugs, history, previous PRs, code comments), followed by confidence scoring. Only findings with a score ≥80 are listed below.

**1. Every new search query in Ceph Buckets and Swift Containers replaces the whole page, including the search field, with a loading spinner (85/100).** *As of 2026-09-24 not fixed either in `main` or in [#1330](./1330-search-architecture-consistency-ux.md).*
`searchTerm` is part of the query key. Each debounced search commit creates a key with no cache, and in TanStack Query v5 (`^5.0.0`) `isLoading` becomes `true`. The component then does an early return: `Ceph/Buckets/index.tsx:231-233` (`if (isLoading) return <Status … Loading Buckets... />`) and `Swift/Containers/index.tsx:253-255`. The toolbar with `SearchInput` unmounts mid-typing: focus is lost and the whole interface flickers. `placeholderData`/`keepPreviousData` are not set. For Ceph, each such switch also repeats `ListObjectsV2` across all buckets (`containerRouter.ts:62-128`). Previously the search was instant and client-side. Copilot noted the cost side of the problem, but not the unmounting of the search field.

**2. After server-side filtering, a selection made before the search stops working. This directly contradicts a comment in the code (85/100).**
`Ceph/Buckets/index.tsx:269-272`:

```tsx
  // Resolve selected Bucket objects from the full unfiltered list so
  // the modal always operates on what was actually selected — not the filtered
  // subset currently visible in the table.
  const selectedBucketSummaries = (buckets || []).filter((c) => selectedBuckets.includes(c.name))
```

`buckets` is now the server-filtered list, not the "full unfiltered list". If the user selects bucket A and then searches for B, A stays in `selectedBuckets` but disappears from `selectedBucketSummaries`. `hasSelection` becomes `false`, and the counter and bulk actions do not see the selection. If the search is cleared, A is "selected" again. The same applies to `Swift/Containers/index.tsx:267-272`. Copilot flagged this for both files.

> **Update 2026-09-24. Partially fixed before merge.** The merged version (`6ce6aeac`) includes an effect that clears the selection on every `searchParam` change: `Ceph/Buckets/index.tsx:79-84`, `Swift/Containers/index.tsx:80-85`. Bulk actions no longer break, but the selection is now simply reset on search, i.e. the opposite behavior to the previous one was chosen. The comment "from the full unfiltered list" above `selectedBucketSummaries` / `selectedContainerSummaries` remains and is now wrong.

**3. Search on the Projects page now shows a Suspense fallback on every query and makes two requests to Keystone (80/100).** *As of 2026-09-24 not fixed either in `main` or in #1330.*
`projects/index.tsx:37` calls `useSuspenseQuery` with `searchTerm` in the key. `handleSearch` (`:50-52`) calls `navigate` without `startTransition`, so every new query (300 ms debounce, `ProjectOverviewNavBar.tsx:32-35`) suspends `ProjectsContent`, and "Loading..." (`:73`) appears instead of the cards. On top of that, two calls go out (`auth/projects` and `auth/domains`). Previously filtering ran over the already loaded list without network requests. The search bar stays in place (it is outside Suspense), but the list flickers on every keystroke.

Below the threshold. Not included in the report as review findings, but worth keeping in mind:

- `listSharedImagesByMemberStatus` searches only by `id`/`name`, while the changeset describes Images more broadly than what is implemented (70).
- `listProjectsWithSearch` duplicates `getAuthProjects`, and `getAuthProjects`/`searchProjects` were left without consumers. It would have been simpler to add an optional input to `getAuthProjects` (65).
- Numeric and date search runs over raw values, not over what is displayed (50).
- Copilot's remarks about `../../` imports are no longer relevant: at head, all new imports use `@/`.

---
Analyzed: 2026-09-23 · commit `e0737fe` · issue status updated 2026-09-24 against merged `6ce6aeac`
