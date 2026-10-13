---
type: pr-report
date: 2026-07-28
status: merged
pr: [1099]
author: TilmanHaupt
branch: til-datahead
---
# PR #1099: feat(portal): use DataGrid Header, stop blocking search, extend searchfields

**Author:** TilmanHaupt · **Status:** merged 2026-07-28 (`e04eed17`)
**Branches:** `til-datahead` → `main` · **Files:** 11 (+244/-34)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1099

## What was done

The PR rewrites the toolbar of the Floating IPs list (`FloatingIpsList.tsx`), replacing the generic `<ListToolbar>` with a composition of `SortInput`/`FiltersInput`/`SelectedFilters`/`SearchInput`/`DataGridToolbar` — the same two-zone header pattern (sorting+action on top, filters+search below) already used in Images/Flavors (`compute/-components/Images`) and Security Groups (PR #952). The stated goal is to fix issue #1096 ("search blocks the entire UI with a full-screen Loading") and #1097 ("make IP and subnet searchable"), as well as #887 (use the DataGrid Header, as in Images).

Key changes:
1. **Local echo state for search** — `localSearchTerm` is synchronized with the committed `searchTerm` via `useEffect`; input is debounced for 500ms before `handleSearchChange` is called.
2. **`placeholderData: (prev) => prev`** is added to `trpcReact.network.floatingIp.list.useQuery` — the goal: not to lose the displayed data when refetching under a new query key.
3. **Permission-gated button** — `<Button>Allocate Floating IP</Button>` is now rendered only if `trpcReact.network.canUser.useQuery({ permission: ["network:floatingips:create"] })` returned `canCreate: true` (an existing procedure; the key `network:floatingips:create` is confirmed in `permissionRouter.ts:51`).
4. **Extended server-side search** — `floatingIpRouter.ts` now searches not only by `description` but also by `floating_ip_address`, `fixed_ip_address`, `floating_network_id`.
5. **A new file `floatingips/urlHelpers.ts`** with the function `applyFilterSelection` — the code is byte-for-byte identical to the already existing copies in `network/securitygroups/urlHelpers.ts` and `compute/-components/Images/urlHelpers.ts`.
6. Tests updated, a changeset added, i18n strings added (`en`/`de` `.po`/`.ts`).

## How it is implemented

Early exit on first load/error with no data:
```tsx
// FloatingIpsList.tsx:91-105
if (isLoading && !floatingIps.length) {
  return (
    <Stack className="py-8" distribution="center" alignment="center" direction="vertical">
      <Trans>Loading...</Trans>
    </Stack>
  )
}

if (isError && !floatingIps.length) {
  return (
    <Stack className="py-8" distribution="center" alignment="center" direction="vertical">
      {error?.message ?? t`Failed to load Floating IPs`}
    </Stack>
  )
}
```

The query with `placeholderData` and passing state to the table container:
```tsx
// FloatingIpsList.tsx:73-90, 190-196
} = trpcReact.network.floatingIp.list.useQuery(
  { project_id: projectId, sort_key: sortSettings.sortBy, sort_dir: sortSettings.sortDirection, ... },
  { placeholderData: (prev) => prev }
)
...
<FloatingIpListContainer
  floatingIps={floatingIps}
  isLoading={isLoading}
  isError={isError && !floatingIps.length}
  error={error}
/>
```

The new `urlHelpers.ts` (identical to the pattern from securitygroups/Images):
```ts
// floatingips/urlHelpers.ts:9-19
export const applyFilterSelection = (
  current: SelectedFilter[],
  selected: SelectedFilter,
  filterDefinitions: Filter[]
): SelectedFilter[] => {
  const alreadySelected = current.some((f) => f.name === selected.name && f.value === selected.value)
  if (alreadySelected) return current
  const supportsMulti = filterDefinitions.find((f) => f.filterName === selected.name)?.supportsMultiValue
  return supportsMulti ? [...current, selected] : [...current.filter((f) => f.name !== selected.name), selected]
}
```

## What it affects

- **Internal change, no external consumers**: `applyFilterSelection` from the new `urlHelpers.ts` is used only inside `FloatingIpsList.tsx`; nothing is exported outward. The shape of `FloatingIpListContainer`'s props (`floatingIps`/`isLoading`/`isError`/`error`) has not changed — only a local variable `columnCount` was added.
- **`floatingIpRouter.ts`**: the list of `filterBySearchParams` fields is extended — the only client consumer of `floatingIp.list` has not changed (the same `FloatingIpsList.tsx`); the existing server test `floatingIpRouter.test.ts` (not among the changed files) was not updated for the new search fields — there is no test coverage for the new search fields.
- **`network.canUser` is used inline**, unlike Security Groups, which has a dedicated hook for this, `useSecurityGroupPermissions` (PR #952) — a minor pattern inconsistency, not a bug.
- **An inaccuracy in the PR description**: the PR text claims *"Fixed import path: Corrected `urlHelpers` import from `./urlHelpers` to `../urlHelpers`... since the helper file is in the parent directory"*. Checked against the base commit (`8a56eef9d`) — in it, `FloatingIpsList.tsx` did not import `urlHelpers` at all (`<ListToolbar>` was used), and the file `floatingips/urlHelpers.ts` itself is new, added by this PR. There was nothing to fix: this is not a bug fix but entirely new code that the description mistakenly presents as a fix.
- **Issue #1097 is not fully closed**: the issue asks to make IP **and subnet** searchable. IP addresses are now searchable (`floating_ip_address`, `fixed_ip_address`, `floating_network_id`), but subnet is not: `FloatingIpSchema` (the schema that `list` actually returns) has no top-level `subnet_id` field; the closest equivalent is `port_details.fixed_ips[].subnet_id`, nested inside an optional/nullable field, and extracting it for search is separate work, not just adding a field name to an array. The PR is marked as closing #1097, but in fact closes only its IP part.
- **A positive point, confirmed via history**: the `localSearchTerm` re-synchronization (`useEffect(() => setLocalSearchTerm(searchTerm), [searchTerm])`) correctly eliminates the exact class of bug that CodeRabbit explicitly pointed out in the review of PR #952 for `SecurityGroupRulesTable.tsx` ("localSearchTerm is initialized from searchTerm once and is not re-synchronized") — but there the bug was never fixed. Here it is solved correctly.

## Review

Of the 6 hypotheses checked, only one passed the confidence ≥80 threshold (confidence scoring by Haiku-based agents, independently of each other; for the rejected ones the reason is given below):

**1. [100] The spinner completely covers the table on every search/filter/sort change — directly contradicting the PR's stated goal ("stop blocking search")**
- `FloatingIpsList.tsx:192` passes the raw `isLoading` into `<FloatingIpListContainer isLoading={isLoading} .../>`.
- `FloatingIpListContainer.tsx:27` — `if (isLoading) { return <Spinner/> }` — with no check on `floatingIps.length`, it replaces the table entirely with a spinner.
- Verified directly against the installed sources of `@tanstack/query-core@5.99.0` (`queryObserver.cjs`): `placeholderData` substitutes only `data` and does not touch `status`; `isLoading = isPending && isFetching`, and `isPending = status === "pending"` stays `true` for **any** new query key (that is, on every debounced search input, filter change or sort change) until the fetch completes — even when `floatingIps` is already showing the old data via the placeholder.
- Result: when typing into the search (after the 500ms debounce) or changing a filter/sort, the whole table disappears and only the spinner is shown — exactly the behavior (issue #1096) that the PR claims to have fixed.

Rejected below 80 (not formal issues; mentioned in "What it affects" as factual inaccuracies rather than behavioral bugs):
- [75] The `<Message variant="error">` banner for a "non-blocking refetch failure" is effectively unreachable for errors caused by search/filter input (same cause — `placeholderData` has no effect when `status === "error"`, `floatingIps` collapses to `[]`, and the earlier blocking `return` fires).
- [75] The inaccuracy in the PR description about the "fix" of the `urlHelpers` import (see "What it affects").
- [75] Issue #1097 is not fully closed — subnet search is not implemented (see "What it affects").
- [50] `FloatingIpListContainer.tsx:36` (`if (isError) {...}`) — unreachable code: the parent's early `return` on `isError && !floatingIps.length` guarantees that `isError` only ever reaches the container as `false`.
- [50] A race between `localSearchTerm` and the `startTransition`-wrapped `setSearchTerm` in `useListWithFiltering.ts` — the mechanism is confirmed, but the race window is narrow (the transition usually commits before the next keystroke arrives at normal typing speed).

---
Analyzed: 2026-07-28 · commit `233f2ac1d`
