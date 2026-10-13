---
type: pr-report
date: 2026-07-21
status: merged
pr: [952]
author: KirylSAP
branch: kiryl-security-group-refactor
---
# PR #952: feat(aurora): security group data grid, permissions

**Author:** KirylSAP · **Status:** merged 2026-07-23 (`cb548a4a`)
**Branches:** `kiryl-security-group-refactor` → `main` · **Files:** 25 (+939/-756)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/952

> The PR's `baseRefOid` (`fd1a2ba`) has fallen far behind the current `main` (more than 70 commits) — the report is built on `git diff <baseRefOid>..<headRefOid>`, which yields exactly the 25 files the PR itself changes.

## What was done

The PR closes two related bugs in the Security Groups UI (issue #835 "Edit on DataGrid and details" and issue #836 "error message stays visible when the modal is reopened") and along the way moves the security groups list onto the shared DataGrid toolbar pattern already used in Images/Flavors (issue #888). Three independent pieces:

1. **Real permissions instead of a stub.** Before the PR, `permissions` in `SecurityGroupsList.tsx` was hardcoded as a `TODO` object `{ canCreate: true, canUpdate: true, canDelete: true, canManageAccess: true }` — that is, Edit/Delete in the row menu were already formally "gated" by the `permissions.canUpdate`/`canDelete` prop (this check existed before the PR too), but the prop itself was always `true`, so the gate was decorative. This is the source of bug #835. The PR replaces the stub with a `useSecurityGroupPermissions` hook that actually calls `network.canUser` (a bulk request of 9 permission keys) and unpacks the result by array position.
2. **A three-zone DataGrid toolbar** for the security groups list (sort+Create, filter+search+chips, groundwork for bulk actions) and a nearly identical toolbar for the rules table (`SecurityGroupRulesTable`) and RBAC policies (`SecurityGroupRBACPolicies`) — with URL persistence via the new `urlHelpers.ts` (the same pattern Images/Swift already have).
3. **An attempt to fix #836** (modal error is not reset) — `handleClose`/`onClearUpdateError` were added in a couple of places. As shown in the "Review" section, this is only partially fixed.

## How it is implemented

**Permission hook — positional unpacking of the bulk `canUser` response** (`-hooks/useSecurityGroupPermissions.ts:29-66`):

```ts
} = trpcReact.network.canUser.useQuery(
  {
    project_id: projectId || "",
    permission: [
      "network:security_groups:read", "network:security_groups:create",
      "network:security_groups:update", "network:security_groups:delete",
      "network:security_group_rules:create", "network:security_group_rules:delete",
      "network:rbac_policies:create", "network:rbac_policies:delete", "network:rbac_policies:read",
    ],
  },
  {
    enabled: Boolean(projectId),
    select: ([canView, canCreate, canUpdate, canDelete, canCreateRule, canDeleteRule,
               canCreateRBAC, canDeleteRBAC, canViewRBAC]) => ({
      canView, canCreate, canUpdate, canDelete, canCreateRule, canDeleteRule,
      canManageAccess: canCreateRBAC && canDeleteRBAC,
      canViewRBAC,
    }),
    staleTime: Infinity,
    gcTime: Infinity,
  }
)
```

I checked the positional unpacking order line by line against the `permission` array and against `createPermissionRouter.ts:157-163` (`permissions.map(...)` preserves the input array order; it does not sort or group by engine) — a 1:1 match, everything is correct here. The default when `data === undefined` (first render and request error) is an all-`false` object (`useSecurityGroupPermissions.ts:24-32`), so on error or before loading the UI fails towards "nothing is allowed" rather than towards the old "everything is allowed" stub — this is a direct fix of exactly the hole that issue #835 describes.

**The actual permission check in the table row already existed** (`SecurityGroupTableRow.tsx:90-91`, not changed by this PR):

```tsx
{permissions.canUpdate && !isReadOnly && <PopupMenuItem label={t`Edit`} onClick={() => onEdit(sg)} />}
{permissions.canDelete && !isReadOnly && <PopupMenuItem label={t`Delete`} onClick={() => onDelete(sg)} />}
```

i.e. bug #835 was not a missing check, but the fact that the checked value was hardcoded to `true` one level up — worth knowing if someone goes looking for a regression in this component in the future: the component itself was never "to blame".

**`canManageAccess` — AND rather than separate permissions** (`useSecurityGroupPermissions.ts:63`) — see "Review".

**Zone toolbar and URL state** (`SecurityGroupsList.tsx:39-90`, `urlHelpers.ts`): `sortSettings`/`filterSettings`/`searchTerm` are local `useState`, initialized once from `useSearch({strict:false})`; the tRPC query itself (`SecurityGroupsList.tsx:74-90`) takes its values not from this state but freshly from `searchParams` via `urlFilters`/`urlSortBy`/`urlSortDirection`/`urlSearchTerm` (lines 69-72) — so the data always matches the URL, but the displayed state of the controls (what is highlighted in `SortInput`, which chips are shown in `SelectedFilters`, what is in the search field) can diverge from the URL on browser back/forward navigation, see "Review".

## What it affects

`useSecurityGroupPermissions`/`SecurityGroupPermissions` are not exported outside `network/securitygroups/` — `git grep` across the whole monorepo at `<headRefOid>` finds no consumers outside the feature itself (`grep -n "useSecurityGroupPermissions\|SecurityGroupPermissions"` outside `securitygroups/` — empty). The server files (`network.canUser`, `permissionRouter.ts`) are not touched by this PR at all — the whole diff is client-side. So the blast radius is limited to the Security Groups screen; no external contracts change.

Inside the feature: `SecurityGroupsList.test.tsx` (439 lines) was **deleted without replacement** — the file `SecurityGroupsList.tsx` (the top-level component itself, with the list, toolbar, Create modal and permission gating of the Create button) was left without any tests of its own after the PR. This directly explains why both findings below (the uncleared Create modal error and the desynchronization of UI controls from the URL) were not caught: the only code that could have caught them was deleted, and nothing was added in its place.

## Review

The pipeline (5 parallel agents: CLAUDE.md compliance, quick bug scan, historical context via git blame/log, previous CodeRabbit PR comments on this same PR, compliance with code comments) plus independent confidence scoring produced one finding with confidence ≥80, additionally confirmed (both parts) by an earlier, unaddressed CodeRabbit comment on this same PR:

1. **Bug #836 is not fixed the way the PR description claims** (confidence 90) — `SecurityGroupsList.tsx:290-312`, `SecurityGroupListContainer.tsx:58-65`. The PR description claims: *"CreateSecurityGroupModal: Now resets error state in `handleClose()` to prevent error persistence"* and the same for `EditSecurityGroupModal`. In fact:
   - **The Create modal is not wired to the mutation state at all.** `isLoading={false}` (`SecurityGroupsList.tsx:310`) is hardcoded, so the "creating..." spinner will never show, even though `createSecurityGroupMutation.isPending` exists and is used for other mutations nearby. `onClose={() => setCreateModalOpen(false)}` (line 308) does not reset `createError` — `handleClose()` inside `CreateSecurityGroupModal.tsx:97-101` clears only the local `properties`/`errors` (form validation), not the `error` prop. When the modal is reopened after a failed creation, the old error message will be visible immediately, before any input — exactly the behaviour described in issue #836.
   - **The Edit modal is only partially fixed.** `handleEdit` in `SecurityGroupListContainer.tsx:58-65` calls `onClearUpdateError` only when switching to a **different** security group (`selectedSecurityGroup.id !== sg.id`). If Edit is reopened for the same group after a failed update, `updateError` (state lifted into `SecurityGroupsList.tsx`) is not cleared anywhere, and the old error is shown again.
   
   Both facts are independently confirmed by a CodeRabbit comment on this same PR (on a commit range before the final `head`; still relevant): *"The CreateSecurityGroupModal usage in SecurityGroupsList is not wired to the mutation state and leaves stale errors behind... make the close handler clear createError... matching the behavior used for the Edit modal"* — that is, the comment describes exactly this finding and, as of the analysis (`head` = `0377fe6`), has not been addressed.

Two more findings were confirmed independently and (partially) by the same CodeRabbit review on this PR, but in terms of likelihood/severity they are at the "also noted" level:

- **Local UI controls (sort/filters/search) can diverge from the URL** (confidence 60) — `SecurityGroupsList.tsx:40-61`. `sortSettings`/`filterSettings`/`searchTerm` are `useState` initialized once with the value of `searchParams` at first render, with no effect that resyncs them on subsequent `searchParams` changes (back/forward navigation, programmatic navigation via a link with different query parameters). The data list itself does not break — the network request is built directly from `searchParams`, not from this state (see "How it is implemented"), but the values displayed in `SortInput`/`SelectedFilters`/`SearchInput` may temporarily show something other than what is actually applied. The same pattern repeats in `localSearchTerm` (`SecurityGroupRulesTable.tsx:72`, initialized from the `searchTerm` prop without resync). Noted in the same CodeRabbit comment on the PR.
- **`canManageAccess` requires BOTH permissions (`create` AND `delete`) via a single AND** (confidence 55) — `useSecurityGroupPermissions.ts:63`: `canManageAccess: canCreateRBAC && canDeleteRBAC`. For a user who has only `network:rbac_policies:delete` (without `:create`, or vice versa), `canManageAccess` will be `false` — they will see neither the "Share Security Group" button (expected, that's create) nor the ability to delete an existing RBAC policy in `RBACPolicyRow` (`canDelete={canManageAccess}` in `SecurityGroupRBACPolicies.tsx:191`) — even though they formally have a separate delete permission. In OpenStack Neutron these really are different policy rules; merging them into one flag reproduces exactly the class of bug (action visibility not matching the user's permissions) that the PR sets out to eliminate for the other fields.
- **The groundwork for bulk actions is entirely non-functional** (confidence 50) — `SecurityGroupsList.tsx:302` passes `hasAnyBulkAction={false}` hardcoded (the only call site is `SecurityGroupListContainer`, `git grep` confirms). The row selection checkboxes, the selection column and the whole "Zone 3: Bulk actions toolbar" branch mentioned in the PR description technically exist in the code (`SecurityGroupTableRow.tsx:63-67`, props `showSelectColumn`/`isSelected`/`onSelect`), but are unreachable in any application state — this entire path is dead code as of the PR.
- **Removing the Stateful field from the Edit modal has no visible explanation in the UI** (confidence 45, below the inclusion threshold, but I mention it as context) — the old info message about the `stateful` restriction was removed entirely and replaced with a JSX comment (`EditSecurityGroupModal.tsx:187`) that is never rendered. Technically safe (the field really does require the cloud-admin role), but the user now sees no explanation of why the checkbox disappeared. Noted by the same CodeRabbit review as a trivial nitpick.

**What was done well:** the permissions hook's default on error/loading is an all-`false` object rather than the old "everything is allowed" stub — this is the right failure direction for permission-driven UI; the RBAC tab (`SecurityGroupDetailsView.tsx:60`) correctly takes into account both `isOwner` and `canViewRBAC` at the same time, not just one of the two.

---
Analyzed: 2026-07-21 · commit `0377fe6`
