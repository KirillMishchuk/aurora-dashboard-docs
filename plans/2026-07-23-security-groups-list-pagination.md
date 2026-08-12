# Plan: Security groups list pagination

**Date:** 2026-07-23 · **Status:** not implemented

## 📋 IMPLEMENTATION PLAN: Security Groups List Pagination

### Overview

The project-scoped Security Groups list view (`/projects/$projectId/network/securitygroups`) currently fetches and renders **every** security group (own + shared) for a project in one unpaginated `DataGrid`, with no client-side slicing. Each `SecurityGroup` record embeds its own `security_group_rules` array by default (Neutron's list response), so on projects with hundreds of rules spread across many groups the payload and the rendered row count both balloon, slowing the page down. This plan adds pagination to the list view, following the client-side pagination pattern already established and shipped for Compute Images and Flavors in this repo (`PAGE_SIZE` constant + URL `page` search param + array slicing + juno's `<Pagination>` control), rather than inventing a new approach.

### Architecture Analysis

**Current state:**

- **Server** — `packages/aurora/src/server/Network/routers/securityGroupRouter.ts`, `list` procedure (project-scoped, input `listSecurityGroupsInputSchema` in `packages/aurora/src/server/Network/types/securityGroup.ts:52`). It issues up to 2 parallel, unpaginated `GET v2.0/security-groups` calls (own + shared, via the `fetchSecurityGroupsWithParams` helper), then deduplicates, applies BFF-side search (`filterBySearchParams`), and sorts (`sortSecurityGroups`) in memory before returning a plain `SecurityGroup[]` — no pagination metadata, no page-size limiting.
- **Payload shape** — `SecurityGroup` (`securityGroup.ts:34`) has `security_group_rules: z.array(securityGroupRuleSchema).optional()`, and Neutron includes this by default on the list endpoint, i.e. rules are embedded per group in the same response the list view fetches. This is the concrete mechanism behind "some projects have hundreds of rules" making the list view heavy — it isn't only about the number of *groups*.
- **Client** — `-components/SecurityGroupsList.tsx` (exports `SecurityGroups`, the query-owning component) calls `trpcReact.network.securityGroup.list.useQuery(...)` with the full result set and passes it straight into `-components/SecurityGroupListContainer.tsx` (exports `SecurityGroupListContainer`, the presentational grid), which maps every item into a `<DataGridRow>` inside a single `<DataGrid>` (`SecurityGroupListContainer.tsx:141-169`) — no slicing, no page control.
- **Established pagination pattern elsewhere in the repo** (same shape of problem, already solved twice):
  - `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/-components/Images/List.tsx` — `const PAGE_SIZE = 50`; `totalPages = Math.ceil(images.length / PAGE_SIZE)`; `safePage = Math.min(currentPage, totalPages)`; `images.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)`; `currentPage` sourced from the route's URL search params (`searchParams.page ?? 1`); resets to page 1 via a `useEffect` guard when the current page falls out of range after filtering; renders `<Pagination variant="input" currentPage totalPages onPressPrevious onPressNext onSelectChange onInputChange onKeyDown />` from `@cloudoperators/juno-ui-components` only when `totalPages > 1`.
  - `.../compute/-components/Flavors/List.tsx` — identical `PAGE_SIZE = 50` + slicing pattern.
  - `.../services/pca/-components/-table/PcaListContainer.tsx` and `.../pca/$pcaId/-components/-table/PcaCertificatesListContainer.tsx` also render `<Pagination>`.
  - `Network/types/floatingIp.ts` separately defines Neutron `limit`/`marker`/pagination-direction schema fields (real upstream pagination), which is a *different* pattern from Images/Flavors and isn't wired to a client `<Pagination>` control today — it's not a precedent to imitate here, since the security-groups list endpoint itself is a single unpaginated call, just like Images was before its BFF added multi-page walking.
- **URL state helpers** — `urlHelpers.ts` in the security groups folder already round-trips `shared`/`search`/`sortBy`/`sortDirection` through `SecurityGroupsSearchParams` via `parseFiltersFromUrl` / `buildUrlSearchParams`, consumed by `SecurityGroupsList.tsx`'s `useSearch`/`navigate` calls — the natural place to add a `page` param.

**Proposed changes:**

- Keep `securityGroupRouter.list`'s return type unchanged (`SecurityGroup[]`, still the full merged/sorted/filtered set) — no server contract break, no new upstream pagination logic needed since Neutron's security-groups list is already a single call, not multi-page like Glance images were.
- Add **client-side** pagination to `SecurityGroupsList.tsx` / `SecurityGroupListContainer.tsx`, mirroring `Flavors/List.tsx` and `Images/List.tsx` exactly: a `PAGE_SIZE = 50` constant, a `page` URL search param, slicing after the full fetched array is available (i.e. after search/filter/sort have already been applied — order matters, see risks below), and the shared `<Pagination>` component.
- This fits the codebase's existing convention (2 other list views already do exactly this) better than introducing Neutron `limit`/`marker` pagination, which would require rewriting `fetchSecurityGroupsWithParams`'s own+shared merge logic and isn't necessary to solve the stated problem (rendering hundreds of rows).

### Potential Problems & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Client-side slicing doesn't shrink the network payload — every group's embedded `security_group_rules` is still fetched even for groups not on the visible page | ⚠️ Medium | Out of scope for "add pagination" per se; flagged under Open Questions as a fast-follow (`fields` query param to Neutron to omit `security_group_rules` from the list call). Document this limitation in the PR description so it isn't mistaken for a full fix of the payload-size problem. |
| Pagination must be applied strictly after the existing own+shared merge, dedup, BFF search filter, and sort — slicing before any of those would silently drop or misorder items across pages | 🔴 High if done wrong, otherwise N/A | Slice only in the client component, only after `securityGroupsData` from `useQuery` is available (same point `Images/List.tsx` and `Flavors/List.tsx` slice) — never slice server-side. |
| Page can go out of range after a filter/sort/search change shrinks the result set | ⚠️ Medium | Copy the `Images/List.tsx` guard: a `useEffect` that resets to page 1 (via `navigate`) whenever `currentPage > totalPages`, and also reset `page` to 1 whenever `search`/`shared` filter/`sortBy`/`sortDirection` change (the existing `useEffect` in `SecurityGroupsList.tsx` that syncs local state from `searchParams` is the natural place to add this). |
| `SecurityGroupListContainer` is also unit-tested in isolation (`SecurityGroupListContainer.test.tsx`) with a full array passed in — adding required `currentPage`/`totalPages`/`onPageChange` props (or defaults) will break existing tests if not handled | ⚠️ Medium | Give the new props sensible defaults (`currentPage = 1`, `totalPages = 1`) exactly like `ImageListView`'s props (`currentPage = 1`, `totalPages = 1`), so existing tests that don't pass them keep passing; add new test cases for the paginated behavior. |
| `hasAnyBulkAction`/row-selection props already exist on `SecurityGroupListContainer` but are unused today (`hasAnyBulkAction={false}` hardcoded, `isSelected={false}`, `onSelect={() => {}}` in `SecurityGroupsList.tsx`) | 🐛 Low | Not a blocker — no bulk-select feature to break yet — but note in code comments that if bulk-select is added later, "select all" must be scoped to the current page's rows only (as Images does), not the full fetched array. |
| No existing Playwright e2e spec for security groups (`apps/dashboard/e2e/` has none) | 🐛 Low | No e2e regression risk today; not adding a new e2e spec is acceptable for this change, but call it out as a testing gap in Open Questions. |

### Prerequisites

- [ ] None blocking — all groundwork (URL search-param plumbing, `<Pagination>` component, the reference pattern in Images/Flavors) already exists in the codebase.
- [ ] Confirm `PAGE_SIZE = 50` (matching Images/Flavors) is acceptable rather than a smaller value — security group rows are narrower than image rows, but 50 keeps the convention consistent across the app; see Open Questions.

### Implementation Steps

#### Step 1: Add paginated state to the query-owning component

**Files to modify:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/-components/SecurityGroupsList.tsx` — the `SecurityGroups` component.

**What to do:**

1. Add `const PAGE_SIZE = 50` near the top of the file.
2. Read `page` from `useSearch({ strict: false })` (extend the local `SecurityGroupsSearchParams` type with `page?: number`), defaulting to `1`.
3. After `securityGroupsData` resolves, compute `totalPages = Math.max(1, Math.ceil(securityGroups.length / PAGE_SIZE))`, `safePage = Math.min(currentPage, totalPages)`, and `paginatedSecurityGroups = securityGroups.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)`.
4. Add a `useEffect` that resets `page` to `1` via `navigate` (same `replace: true` pattern already used by `handleSortChange`/`handleFilterChange`) whenever `searchTerm`, `filterSettings.selectedFilters`, `sortSettings.sortBy`, or `sortSettings.sortDirection` change — mirroring the existing sync effect at the top of the component (lines 69-80) and the out-of-range guard in `Images/List.tsx`.
5. Add a `handlePageChange(newPage: number)` that calls `navigate({ search: (prev) => ({ ...prev, page: newPage }), replace: true })`.
6. Pass `paginatedSecurityGroups` (not the full `securityGroups`) plus `currentPage={safePage}`, `totalPages`, `onPageChange={handlePageChange}` into `<SecurityGroupListContainer />`.

**Expected outcome:**

- The list view only renders up to 50 rows per page; page state is reflected in the URL (`?page=2`).

**Verification:**

- `pnpm --filter @cobaltcore-dev/aurora typecheck`; manual check that `?page=` appears/updates in the URL when paging.

---

#### Step 2: Render the pagination control in the presentational grid

**Files to modify:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/-components/SecurityGroupListContainer.tsx`

**What to do:**

1. Import `Pagination` from `@cloudoperators/juno-ui-components` (already a dependency, used by Images/Flavors/PCA).
2. Add optional props `currentPage?: number` (default `1`), `totalPages?: number` (default `1`), `onPageChange?: (page: number) => void` to `SecurityGroupListContainerProps`.
3. After the closing `</DataGrid>` (around line 169), render `{totalPages > 1 && <div className="flex justify-center py-4"><Pagination variant="input" currentPage={currentPage} pages={totalPages} onPressPrevious={...} onPressNext={...} onSelectChange={...} onInputChange={...} onKeyDown={...} /></div>}`, following `Images/List.tsx`'s `Pagination` block (lines ~686-710) verbatim for prop wiring (local `inputPage` state for the free-text page input, clamped `Math.max`/`Math.min` on prev/next).

**Expected outcome:**

- A page-1/…/N control appears below the grid whenever there's more than one page; prev/next/direct-page-entry all call `onPageChange`.

**Verification:**

- Manual: with a project that has >50 security groups (or a mocked query in a test), confirm the control renders and navigating pages swaps the visible rows.

---

#### Step 3: Extend URL helpers and search-param typing

**Files to modify:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/urlHelpers.ts`

**What to do:**

1. Add `page?: number` to the local `SecurityGroupsSearchParams` type (kept in sync with the identically-named type duplicated in `SecurityGroupsList.tsx` — consider whether to de-duplicate into one shared type while touching this file, since both currently redeclare it).
2. No functional change to `buildUrlSearchParams`/`parseFiltersFromUrl` is required for `page` itself (it's not a `Filter`), but double-check `buildUrlSearchParams` doesn't accidentally strip an existing `page` param when filters/sort change — since `SecurityGroupsList.tsx` calls `navigate` separately for page changes (Step 1.5) rather than through `buildUrlSearchParams`, this should be a non-issue, but verify with a manual check that changing a filter doesn't leave a stale `page=3` in the URL pointing past the new, smaller result set (covered by the reset effect in Step 1.4 either way).

**Expected outcome:**

- `page` survives navigation and coexists correctly with `shared`/`search`/`sortBy`/`sortDirection`.

**Verification:**

- Unit test (see Step 4) asserting `page` resets to 1 when `search`/`shared`/`sortBy`/`sortDirection` change.

---

#### Step 4: Update and add tests

**Files to modify/create:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/-components/SecurityGroupListContainer.test.tsx` — update.
- New: a colocated test for `SecurityGroupsList.tsx` (none exists today) covering the pagination slicing/reset logic, e.g. `SecurityGroupsList.test.tsx` in the same `-components/` folder.

**What to do:**

1. In `SecurityGroupListContainer.test.tsx`: add cases for (a) `totalPages` omitted/`1` → no `<Pagination>` rendered (preserves existing test behavior via defaults), (b) `totalPages > 1` → `<Pagination>` renders and clicking prev/next/selecting a page calls `onPageChange` with the expected value.
2. In the new `SecurityGroupsList.test.tsx`: mock `trpcReact.network.securityGroup.list.useQuery` to return >50 groups, assert only `PAGE_SIZE` rows are passed down / rendered for page 1, assert navigating triggers the mocked `navigate` with the expected `page` search param, and assert changing `search`/`sortBy` resets `page` to 1.
3. Run `pnpm --filter @cobaltcore-dev/aurora test` scoped to the touched files first, then the full package suite.

**Expected outcome:**

- Test suite proves pagination math, prop wiring, and the page-reset-on-filter-change behavior.

**Verification:**

- `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/$projectId/network/securitygroups` passes.

---

### Testing Plan

**Unit tests:**

- [ ] `SecurityGroupListContainer` renders `<Pagination>` only when `totalPages > 1`, and wires prev/next/select/input callbacks to `onPageChange`.
- [ ] `SecurityGroupsList` slices the fetched array to `PAGE_SIZE` items for the current page.
- [ ] `SecurityGroupsList` resets `page` to `1` when `search`, `shared` filter, `sortBy`, or `sortDirection` change.
- [ ] `SecurityGroupsList` clamps `currentPage` to `totalPages` when the result set shrinks below the current page.

**Integration tests:**

- [ ] Full render of the security groups route with a mocked >50-item response confirms only one page of rows is in the DOM at a time and the URL `page` param updates on navigation.

**Manual verification:**

1. Run `pnpm dev`, open a project's Security Groups list with a data set (real or mocked) exceeding 50 groups.
2. Confirm only 50 rows render initially, with a pagination control below the grid.
3. Click "next", verify the next 50 (or remainder) render and the URL reflects `?page=2`.
4. Change the search box or the `shared` filter, verify the page resets to 1 and the pagination control's page count updates to match the filtered set.
5. Type a page number directly into the pagination input and press Enter, verify it navigates correctly and clamps to `[1, totalPages]`.

### Acceptance Criteria

- [ ] Security Groups list view renders at most `PAGE_SIZE` (50) rows per page regardless of the total number of groups/rules in the project.
- [ ] A `<Pagination>` control appears whenever there is more than one page, matching the visual/interaction pattern already used by Images and Flavors.
- [ ] Page state survives browser navigation (back/forward) and is reflected in the URL.
- [ ] Changing search/filter/sort resets the visible page to 1 and never leaves the user on an out-of-range page.
- [ ] No regressions to existing security-groups list behavior (search, `shared` filter, sort, create/edit/delete flows).
- [ ] `pnpm typecheck`, `pnpm lint`, `pnpm test` pass for `packages/aurora` (scope with `--filter @cobaltcore-dev/aurora`).

### Open Questions

1. **Payload size, not just row count** — client-side pagination (this plan) does not reduce the amount of data fetched from Neutron per request; every security group's embedded `security_group_rules` array is still transferred even for off-screen groups. If the "hundreds of rules" problem is primarily about *network/response-time* cost rather than *DOM rendering* cost, the team may also want a follow-up to strip `security_group_rules` from the LIST call via Neutron's `fields` query parameter (only fetch it on `getById`, which already exists and is used by the detail view). I did not include this in the plan since the task asked specifically for pagination, but flagging it since it's the more direct fix for "hundreds of rules" as opposed to "hundreds of groups."
2. **PAGE_SIZE value** — I defaulted to `50` to match the existing convention in `Images/List.tsx` and `Flavors/List.tsx`. If security-group rows are visually denser/lighter than image or flavor rows, a different value (e.g. 25) might read better; no strong signal either way from the codebase.
3. **Server-side vs. client-side pagination** — I chose client-side slicing (matching Images/Flavors) over real Neutron `limit`/`marker` pagination (which `Network/types/floatingIp.ts` has schema fields for but isn't wired to a UI control anywhere yet). If the team specifically wants true upstream pagination for security groups too, that's a materially larger change (rewriting the own+shared merge/sort logic to work across server-driven pages) and should be scoped separately.
