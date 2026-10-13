---
type: pr-report
date: 2026-09-02
status: merged
pr: [1250]
author: mark-karnaukh-extern-sap
branch: mark-fix-datagrid-virtualized-tables
---
# PR #1250: fix(aurora): incorrect DataGrid usage in virtualized tables (Swift, Ceph) (#1223)

**Author:** mark-karnaukh-extern-sap · **Status:** created 2026-09-01 → merged 2026-09-02
**Branches:** `mark-fix-datagrid-virtualized-tables` → `main` · **Files:** 9 (+79/-27)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1250

> Closes #1223.

## What was done

A fix for incorrect use of Juno `DataGrid` in the virtualized body of four Storage tables: Ceph `BucketTableView`/`ObjectsTableView` and Swift `ContainerTableView`/`ObjectsTableView`. Before the PR, every row of the virtualized body was wrapped in `<div className="juno-datagrid" ...>` — so in effect a list of N rows rendered N separate grid containers instead of one. The PR replaces this with a single `<DataGrid>` wrapper for the body with a child `<DataGridRow>` for each row — exactly the structure issue #1223 expects. The table headers (`<DataGrid>`/`<DataGridHeadCell>`) are not touched — the problem was only in the body.

A side effect, deliberate: rows get `role="row"` (via `<DataGridRow>`) instead of the previous `role="link"`; row click and keyboard navigation (Enter/Space) have not changed — the handlers and `tabIndex={0}` remain on the row.

## How it is implemented

The pattern is identical in all four files. Using `Ceph/Buckets/BucketTableView.tsx` as an example:

```tsx
// packages/aurora/src/client/routes/.../storage/-components/Ceph/Buckets/BucketTableView.tsx:166-206
<DataGrid
  style={{
    height: `${totalSize}px`,
    width: "100%",
    position: "relative",
  }}
>
  {virtualItems.map((virtualRow) => {
    ...
    return (
      <DataGridRow
        key={bucket.name}
        data-index={virtualRow.index}
        ref={measureElement}
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          transform: `translateY(${virtualRow.start}px)`,
          display: "grid",
          gridTemplateColumns: gridColumnTemplate,
          alignItems: "stretch",
        }}
        data-testid={`bucket-row-${bucket.name}`}
        tabIndex={0}
        onClick={handleRowNavigate}
        onKeyDown={...}
      >
```

Previously, in place of `<DataGrid>`/`<DataGridRow>` there were plain `<div>`s with manual classes `juno-datagrid` (body wrapper) and `juno-datagrid group hover:bg-theme-background-lvl-1 cursor-pointer` (row, only for Buckets/Containers — in the Objects tables the class was just `juno-datagrid`, without hover/cursor). The virtualizer positioning (`position: absolute`, `transform: translateY(...)`) and the row's own grid layout (`display: "grid"`, `gridTemplateColumns: gridColumnTemplate`) remain as inline `style` — unchanged, one to one.

An important detail for the correctness of this refactoring: Juno's `DataGridRow` (`packages/ui-components/src/components/DataGridRow/DataGridRow.component.tsx` @ juno-ui-components 9.4.0) has the CSS class `.datagrid-row { display: contents }` — the element itself does not generate a box. Each row's inline `style` in the PR explicitly sets `display: "grid"`, which as an inline style overrides `display: contents` from the external CSS class — so `position: absolute`/`transform` keep working the same as before. Verified for all 4 files — the style pattern is identical (see `CephObjectsTableView.tsx:470-479`, `SwiftContainerTableView.tsx:215-224`, `SwiftObjectsTableView.tsx:317-326`).

The test changes are mirrored across 4 files — a new regression test for "one grid, many rows":

```tsx
// packages/aurora/src/client/routes/.../Ceph/Buckets/BucketTableView.test.tsx:185-195
// #1223: the virtualized body must be a single grid wrapper with the rows as
// role="row" children — previously each row carried the grid itself (one grid
// per row), causing extra re-renders and broken grid semantics.
test("renders one grid wrapper with row children, not a grid per row", () => {
  renderTableView()
  const body = screen.getByTestId("buckets-table-body")
  const grids = within(body).getAllByRole("grid")
  expect(grids).toHaveLength(1)
  const rows = within(grids[0]).getAllByRole("row")
  expect(rows.length).toBeGreaterThan(1)
})
```

Plus a targeted update of the existing row-role assertion in Swift `ContainerTableView.test.tsx` (the only place in the diff where `role="link"` used to be checked):

```tsx
// packages/aurora/src/client/routes/.../Swift/Containers/ContainerTableView.test.tsx:383-392
test("container rows have tabIndex 0 and role row", () => {
  renderView()
  mockContainers.forEach((c) => {
    const row = screen.getByTestId(`container-row-${c.name}`)
    expect(row).toHaveAttribute("tabindex", "0")
    // Rows now render via Juno's <DataGridRow>, which sets role="row"
    // (previously the row div used role="link"). Row-click / keyboard
    // navigation is unchanged — see the navigation tests above.
    expect(row).toHaveAttribute("role", "row")
  })
})
```

`.changeset/sunny-geckos-read.md` adds a `patch` changeset for `@cobaltcore-dev/aurora`; its wording matches the essence of the change (performance/layout/accessibility).

## What it affects

The change is entirely internal — the components' public contract did not change, and no prop signature was touched:

- **Consumers of the four `*TableView` components.** Each is imported only from its own `index.tsx` in the same folder (`Ceph/Buckets/index.tsx`, `Ceph/Objects/ObjectBrowserView.tsx` and `Ceph/Objects/index.tsx` (re-export), `Swift/Containers/index.tsx`, `Swift/Objects/index.tsx`) — no other usages found in `origin/main` (`git grep` for the component names outside their own directories). Their `index.test.tsx`/`ObjectBrowserView.test.tsx` mock `TableView` entirely (`vi.mock(".../TableView", ...)`), so the internal DOM/role structure is not visible to those tests and is not affected by the diff.
- **The per-row `juno-datagrid` anti-pattern.** `git grep -n "juno-datagrid" origin/main` before the PR finds exactly 4 matches — all of them in the four files the PR fixes. The same goes for `useVirtualizedTableBody` — it is used only by these four files. So the PR closes the problem completely, with no missed virtualized tables with the same bug elsewhere in the monorepo.
- **Interaction with the recent PR #1216** ("optimize DataGrid Action column width", `fb23589e`, 2026-08-28) — that one added `minContentColumns={[columnCount - 1]}` to the **header** `<DataGrid>` of these same files. #1250 does not touch the header; the body `<DataGrid>` receives no `columns`/`gridColumnTemplate` props at all (the column layout is set per row via inline `gridTemplateColumns` on each `DataGridRow`, as before the PR) — no overlap/regression with #1216.
- **Hover/cursor on the row.** For Buckets/Containers the Tailwind class `group hover:bg-theme-background-lvl-1 cursor-pointer` was removed without an explicit replacement class — but `DataGridRow` itself adds `datagrid-row-hoverable` when `onClick` is present (which these rows have), and the CSS rule `.datagrid-row-hoverable:hover > * { cursor: pointer; background-color: ... }` (juno-ui-components 9.4.0) gives equivalent highlighting/cursor on the child cells. The Objects tables (Ceph/Swift) had no `onClick` on the row before and still have none — there was no hover highlighting there before either; the behavior has not changed. The `group` class was not used for `group-hover:` anywhere in these 4 files (checked with `grep`), so removing it affected nothing.

## Review

No issues with confidence ≥80 found.

The places where this kind of refactoring usually breaks were checked separately:
- Conflict between `display: contents` (the `DataGridRow` CSS class) and the inline `position: absolute`/`transform` the virtualizer needs — not a problem: each row's inline `style` explicitly overrides it with `display: "grid"` in all 4 files.
- Loss of the row hover/cursor style when the Tailwind class was removed — compensated by `DataGridRow`'s built-in behavior (`datagrid-row-hoverable` when `onClick` is present); the distinction between Buckets/Containers (have `onClick`) and Objects (no `onClick`, there was no hover before either) is preserved correctly.
- Completeness of the `role="link"` → `role="row"` test assertion updates — the only such assertion in the whole PR diff (in `ContainerTableView.test.tsx`) was updated; the other three test files had no assertion on a specific row `role` either before or after.
- Overlap with the recent PR #1216 (minimizing the Action column width via `minContentColumns` on the header `DataGrid`) — no overlap: the header is untouched, and the body column layout is per-row as before.
- Completeness of coverage: the `juno-datagrid` anti-pattern and the `useVirtualizedTableBody` hook occur in `origin/main` in exactly these 4 files — no other virtualized tables with the same bug left unfixed were found.
- Compliance with CLAUDE.md — the changes are localized to client components in `packages/aurora/src/client`, tests are colocated as `*.test.tsx` (per convention), a changeset was added; the diff does not touch any other applicable CLAUDE.md items (server architecture, permission keys, routing).

---
Analyzed: 2026-09-02 · commit `12f54f1e` (head, PR open/unmerged)
