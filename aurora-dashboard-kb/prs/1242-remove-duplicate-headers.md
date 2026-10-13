---
type: pr-report
date: 2026-09-01
status: merged
pr: [1242]
author: vlad-schur-external-sap
branch: vlad-1134-issue
---
# PR #1242: refactor(dashboard): remove duplicate breadcrumbs and old headers

**Author:** vlad-schur-external-sap · **Status:** merged 2026-09-01 (created 2026-09-01)
**Branches:** `vlad-1134-issue` → `main` · **Files:** 16 (+151/-186)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1242

> Closes #1134.
>
> **Correction 2026-09-01:** the first version of this report mistakenly raised to confidence 85 a finding that the Security Group details page loses "back to list" navigation after the page-local `<Breadcrumb>` is removed. This is wrong — the author (Kiryl) pointed to the real persistent breadcrumb at the top of the page, the report was re-checked and the finding was withdrawn (see "What was done" below, which now describes the `ProjectInfoBox` mechanism that was missed in the first pass). The report below is the corrected version; the overall conclusion on the PR (2 findings → 1 remaining) has changed.

## What was done

Issue #1134 asked to unify the page headers of Floating IPs and Security Groups under the already existing shared `ContentHeader` component (`packages/aurora/src/client/components/ContentHeader/ContentHeader.tsx` — not new, not touched by this PR; introduced back in PR #999/#1006/#1009 for the other service pages). Before this PR, both pages used an outdated pattern: a bare `ContentHeading` at the route-file level plus (for Security Groups) a separate `SecurityGroupHeader` component with its own title and **one more, page-local `<Breadcrumb>`** inside `SecurityGroupDetailsView`/`$securityGroupId/index.tsx`.

Important context missed in the first version of this report: the application already has a separate, persistent breadcrumb — the `ProjectInfoBox` component (`packages/aurora/src/client/components/ProjectView/ProjectInfoBox.tsx`), mounted once in the layout file `packages/aurora/src/client/routes/_auth/projects/$projectId.tsx:193` directly above `<Outlet />`, i.e. present on **every** project page, including both pages this PR touches. It builds the chain "Home → Project → Network → Security Groups → <group name>" (with clickable items) from the `crumb`/`sectionCrumb`/`isDetail`/`intermediateCrumb` fields in the active route's `staticData` (`RouteInfo`, `routeInfo.ts`) — these fields were already declared in `$securityGroupId/index.tsx:17-26` (`crumb: { labelKey: "Security Groups", to: "/projects/$projectId/network/securitygroups" }`) and were not changed by this PR. That is, the page-local `<Breadcrumb>` that the PR removes from `SecurityGroupDetailsView` was a **duplicate** — a second, separate breadcrumb row on top of the already working global one. This is apparently exactly what the PR title means by "duplicate breadcrumbs".

With this in mind, the PR introduces the new shared `<ContentHeader title=... projectId=... description=... actions=...? />` at the very top level of four pages instead of two parallel, partially duplicating patterns (`ContentHeading` at the route level + local `Breadcrumb`/`SecurityGroupHeader` at the details level):
- **Floating IPs, list** (`floatingips/index.tsx` → `FloatingIpsList.tsx`): `ContentHeading` is removed from the route file, `ContentHeader` is now rendered by `FloatingIpsList` itself.
- **Floating IP, details** (`$floatingIpId/index.tsx` → `FloatingIpDetailsView.tsx`): likewise — `ContentHeading` in the route file is removed, `ContentHeader` is now in `FloatingIpDetailsView`, and the whole `actions` block (Edit/Attach/Detach/Release) is moved there too.
- **Security Groups, list** (`securitygroups/index.tsx` → `SecurityGroupsList.tsx`): the same scheme.
- **Security Group, details** (`$securityGroupId/index.tsx`): `ContentHeading` + page-local `Breadcrumb`/`BreadcrumbItem` are replaced with `ContentHeader`; the separate `SecurityGroupHeader.tsx` component is deleted entirely (it was the only consumer of `ContentHeading` inside `SecurityGroupDetailsView`). The global breadcrumb from `ProjectInfoBox` stays untouched and keeps working as before.

Three files (`compute/flavors.tsx`, `compute/images.tsx`, `network/floatingips/index.tsx`) incidentally migrate the search schema from the deprecated `z.object(...).passthrough()` to `z.looseObject(...)` — an equivalent replacement (zod v4), but `flavors.tsx`/`images.tsx` are not part of the headers task at all (see "Review"). One minor side fix: `.changeset/optimize-datagrid-action-columns.md` (a pending-release changeset from the already merged #1216) is corrected from the non-existent package name `@cloudoperators/aurora` to the real `@cobaltcore-dev/aurora` — without this fix the changeset would formally be "empty" for the Changesets tool.

## How it is implemented

### The global breadcrumb (`ProjectInfoBox`) is untouched and keeps providing back navigation

```tsx
// packages/aurora/src/client/routes/_auth/projects/$projectId.tsx:189-201 (not touched by this PR)
<div className="min-w-0 flex-1">
  <ProjectInfoBox projectInfo={{ id: projectId, name: crumbProject?.name || projectId, domain: crumbProject?.domain }} />
  <Outlet />
</div>
```
```tsx
// packages/aurora/src/client/components/ProjectView/ProjectInfoBox.tsx:73-109 (not touched by this PR)
if (info.crumb) {
  const { labelKey, label, to, useParamAsLabel } = info.crumb
  ...
  if (info.isDetail) {
    items.push({ label: resolvedLabel, onClick: () => navigate({ to: to as never, params }) })
    ...
    const title = deepest.meta?.find((m) => m != null && "title" in m)?.title as string | undefined
    if (title) items.push({ label: title, active: true })
  }
}
```
```tsx
// packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/$securityGroupId/index.tsx:17-26 (not touched by this PR)
staticData: {
  ...
  isDetail: true,
  sectionCrumb: { labelKey: "Network" },
  crumb: { labelKey: "Security Groups", to: "/projects/$projectId/network/securitygroups" },
} satisfies RouteInfo,
```
These three pieces (the layout component, the global breadcrumb component and the route `staticData`) are not changed by a single line in this diff — they already worked before the PR and keep working after. The resulting chain on the security group details page: Home → Project → Network → **Security Groups** (clickable, leads to the list) → group name (active item). The removed page-local `<Breadcrumb>` provided exactly the same — just duplicating it.

### `FloatingIpDetailsView` — the Floating IP address is now shown twice

```tsx
// FloatingIpDetailsView.tsx:27-28 (not touched by the diff)
const networkRoutingItems: DetailListItem[] = [
  { label: t`Floating IP Address`, value: floatingIp.floating_ip_address || `—` },
  ...
]
...
// FloatingIpDetailsView.tsx:49-52 (new)
<ContentHeader
  title={floatingIp.floating_ip_address ?? floatingIp.id}
  ...
```
Before the PR, the heading `<ContentHeading>{floatingIp.floating_ip_address}</ContentHeading>` was rendered in the parent route file (`$floatingIpId/index.tsx`), not inside `FloatingIpDetailsView` — so in the isolated unit test `FloatingIpDetailsView.test.tsx` the address appeared once (only in `networkRoutingItems`). Now the heading has moved inside the same component, and the address is displayed twice on the same page. The PR itself confirms this — 3 assertions in `FloatingIpDetailsView.test.tsx` were switched from `getByText(...)` (fails on >1 match) to `getAllByText(...).length > 0`, instead of removing the `Floating IP Address` row from `networkRoutingItems` as redundant. See "Review", finding #1. (There is no similar effect for Security Groups: `SecurityGroupBasicInfo` shows Name/ID in the table just as it did before, regardless of the heading — this pair was duplicated before the PR as well, and the PR does not change it.)

## What it affects

All four pages are leaf route components with exactly one consumer (`FloatingIpsList`, `FloatingIpDetailsView`, `SecurityGroups`/`SecurityGroupsList`, `SecurityGroupDetailsView` are not imported anywhere else). `ContentHeader` is a reusable component that was already used on other pages; this PR does not change the component itself, it only adds two new consumers and removes the old parallel pattern (a bare `ContentHeading` + for Security Groups also a duplicating page-local `Breadcrumb` next to the already working global `ProjectInfoBox`). The deleted `SecurityGroupHeader.tsx` had no other consumers (only `SecurityGroupDetailsView`, updated in the same PR) — a safe deletion; the barrel export (`-details/index.ts`) is adjusted accordingly.

Both list components (`FloatingIpsList`, `SecurityGroupsList`) now use `useRouteContext`/`useMatches`/`useParams` (via `ContentHeader`) — both unit tests received the necessary mocks (`FloatingIpsList.test.tsx` mocks `ContentHeader` itself entirely; `SecurityGroupsList.test.tsx` mocks three `@tanstack/react-router` hooks directly). There are no other consumers of these lists in the codebase that would also need such a mock (the only matches for `SecurityGroups`/`FloatingIpsList` outside their own files are the route files themselves, already updated in this PR).

## Review

**Found (confidence ≥ 80):**

1. **`FloatingIpDetailsView` now shows the Floating IP address twice on the same page.** (confidence 80)
   The page heading (`ContentHeader title={floatingIp.floating_ip_address ?? floatingIp.id}`, line 50) and the `Floating IP Address` field in the "Network & Routing" table (`networkRoutingItems`, line 28, not touched by this diff) show the same value. Before the PR this did not manifest as duplication at the component level, because the heading was rendered in the parent route file rather than inside `FloatingIpDetailsView` — moving the heading into the same component that already showed this field in the table is what created the duplication. The PR noticed this (otherwise it wouldn't have had to fix the tests), but adapted the tests to the new behavior (`getByText` → `getAllByText(...).length > 0`, 3 places in `FloatingIpDetailsView.test.tsx`) rather than removing the redundant row from the table — i.e. the tests now document the duplication as expected rather than as a temporary artifact. This partially contradicts the goal stated in the PR title, "remove duplicate ... headers" (although for breadcrumbs this goal is indeed achieved correctly — see "What was done").
   Files: `FloatingIpDetailsView.tsx:28,50`, `FloatingIpDetailsView.test.tsx` (4 applied `getAllByText`).

**Also noted (confidence 50-79, did not reach full confidence):**
- **[70]** `compute/flavors.tsx` and `compute/images.tsx` received the change `z.object(...).passthrough()` → `z.looseObject(...)` (an equivalent replacement for zod v4), while neither of these two files is related to the stated topic of the PR (breadcrumbs/headers) — in both files this is the only line of the diff. Neither the PR description nor this PR's existing changeset mentions the migration to `z.looseObject`. The change itself is harmless and apparently fully completed within the client route schemas (no other `.passthrough()` remains in `packages/aurora/src/client/routes/**` at the head commit), but for a reader of the PR history it remains unclear why two files with no other edits ended up in a diff about page headers.
- **[55]** `.changeset/optimize-datagrid-action-columns.md` (a pending-release changeset of the already merged #1216) is corrected from the non-existent package name `@cloudoperators/aurora` to the real `@cobaltcore-dev/aurora` — a legitimate and necessary fix (without it the changeset would not have been tied to any real package in Changesets), but it is also unrelated to the topic of this PR and not mentioned anywhere in its description.

---
Analyzed: 2026-09-01 · commit `e80ea3ea` · corrected 2026-09-01 (withdrew the mistaken finding about loss of breadcrumb navigation after the author's check)
