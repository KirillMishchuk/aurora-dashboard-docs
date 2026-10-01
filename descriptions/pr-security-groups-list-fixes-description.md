# Summary

Fixes three issues from epic #1327 in the Security Groups list.

The main one is #1321. As an admin, the `Shared = No` filter returned security groups from **every** project. In the reported case the filtered view showed four `default` groups and `manila-service`, while the unfiltered view showed only two rows, so a filter produced more rows than no filter at all. Once the server side is restructured, every filtered view is by construction a subset of the unfiltered one, whatever role the token carries.

The other two are markup changes. The list's DataGrid header now follows the Juno DataGrid pattern (#1323), and the Name cell drops a wrapper that had no effect (#1325).

**Why `Shared = No` showed other projects' groups.**
- `network.securityGroup.list` is a `projectScopedProcedure`, so the token is rescoped to the selected project. Neutron, however, does not limit an admin-role token to that project: without a `project_id` filter, `GET /v2.0/security-groups` returns the groups of every project in the cloud.
- The unfiltered path sent `project_id` on its own-groups request (`securityGroupRouter.ts:98-102` before this change). The explicit-filter branch (`securityGroupRouter.ts:79-91`) sent a single `{ ...queryInput, shared, sort_key, sort_dir }` request with no `project_id`, so `shared=false` became "every non-shared group in the cloud", one `default` per project. A non-admin token is filtered by Neutron itself, which is why the bug only showed for admins.

**Why the two paths also disagreed on sorting and duplicates.**
- The explicit-filter branch left sorting to Neutron and skipped deduplication.
- The unfiltered branch deduplicated and sorted in the BFF.
- So the same groups could come back in a different order depending on whether a filter was active, and the two views were not built from the same data at all.

**Why `tenant_id` was removed from the input.** `listSecurityGroupsInputSchema` accepted `tenant_id`, which Neutron treats as an alias of `project_id`. It was spread into the Neutron query along with the other filters, so a caller could send it next to the scoped `project_id` and widen or contradict the own-groups request. The scope now always comes from `project_id`.

# Changes Made

## Server

- **`securityGroupRouter.list`.** Every view is now built from the same two sources:
  - *own*: `project_id` = the scoped project, `shared=false`;
  - *shared*: `shared=true`.
- Without a `shared` filter, both requests run in parallel and are merged. An explicit `shared` runs only the matching side, so `Shared = Yes` and `Shared = No` partition the unfiltered list (`Yes ∪ No = All`, `Yes ∩ No = ∅`).
- All views go through one BFF pipeline: deduplicate by id → `stateful` filter → `searchTerm` → sort. `sort_key`/`sort_dir` are no longer forwarded to Neutron, so explicit-filter views are sorted by the same algorithm as the unfiltered one.
- The comment on the own-side request explains why `project_id` must stay there.

## Types

- **`listSecurityGroupsInputSchema`.** `tenant_id` removed. Zod strips unknown keys, so a value sent anyway never reaches Neutron.

## Client

- **`SecurityGroupsList`** (#1323). The header zones are wrapped per the Juno DataGrid pattern:
  - `Stack.juno-pattern-datagrid-outer` holds `Stack.juno-pattern-datagrid-header` (sort + Create, then `DataGridToolbar` with filters, search and pills), followed by the list container.
  - The `div.relative` wrapper is gone. Nothing inside it relied on it: every popup (`PopupMenu`, `Select`, `ComboBox`, `Modal`) portals.
  - The refetch-error `Message` sits above the outer Stack as page-level status, and `CreateSecurityGroupModal` follows it.
  - With Juno 9.4.0, a vertical `Stack` is `flex-col items-stretch gap-0`, so spacing and width are unchanged.
- **`SecurityGroupTableRow`** (#1325). The Name cell is `<DataGridCell>{sg.name}</DataGridCell>`. The old `<div><p className="text-md">` wrapper did nothing: `text-md` is not defined in aurora or Juno, and `DataGridCell` already lays out bare text.

## Docs

- **`docs/007_security_groups_bff.md`.**
  - New "List semantics (own ∪ shared)" section.
  - The `project_id` row now describes it as the required scope.
  - A `stateful` row is added.
  - The `tenant_id` row is removed.

## Tests

- **`securityGroupRouter.test.ts`.** New "Explicit shared filter (admin token)" block with a Neutron mock that routes by URL query and models an admin token: every project's groups come back without a `project_id` filter. It covers:
  - `shared=false` sends `project_id` and returns a single `default`, which reproduces #1321;
  - `shared=true` is one request without `project_id`;
  - for every `shared` × `stateful` combination, filtered ids are a subset of the unfiltered ids and `Yes`/`No` partition the list;
  - an own group shared to all projects appears once, under `Shared = Yes` only, and is deduplicated when Neutron returns it from both requests;
  - explicit-filter sorting runs in the BFF and `sort_*` is not forwarded;
  - explicit filter combined with `stateful` and with `searchTerm`;
  - a caller-supplied `tenant_id` never reaches Neutron.
- **`SecurityGroupsList.test.tsx`.** The header Stack is the first zone of the outer Stack and the list container is the last. No `div.relative` wrapper remains.
- **`SecurityGroupTableRow.test.tsx`.** The name text is rendered directly in the `DataGridCell`.
- **Results.** The aurora suite passes: 236 files, 5758 tests, of which 40 are in `securityGroupRouter.test.ts`. `typecheck`, `lint` and `prettier --check` are green.

# Behaviour and Contract Changes

- **`network.securityGroup.list` no longer accepts `tenant_id`.** There is no in-repo caller. An external consumer passing it gets a TypeScript error, and at runtime the key is silently stripped.
- **Explicit `Shared` filters are now sorted in the BFF instead of Neutron.** The order matches the unfiltered list but can differ slightly from what Neutron's database collation produced.
- **Admins see fewer rows under `Shared = No`.** Those rows belonged to other projects and should never have been shown.

# Related Issues

Fixes #1321
Fixes #1323
Fixes #1325

Part of #1327

# Testing Instructions

1. `pnpm i`
2. `pnpm run test`
3. Manual scenario (DevStack, admin user in project A, with projects B and C existing):
   - **Setup:**
     - make sure B and C each have a `default` group;
     - create `sg-b-wide` in B, shared to all projects (`openstack network rbac create --type security_group --action access_as_shared --target-all-projects sg-b-wide`);
     - create `sg-c-to-a` in C, shared to A only;
     - create `sg-c-to-b` in C, shared to B only;
     - create `sg-a-stateless` in A (`--stateless`).
   - **Unfiltered:** A's own groups plus `sg-b-wide` and `sg-c-to-a`. Exactly one `default`, and no `sg-c-to-b`.
   - **`Shared = No`:** only A's own groups, with one `default`. Before this change it listed one `default` per project.
   - **`Shared = Yes`:** `sg-b-wide` and `sg-c-to-a`, and **not** `sg-c-to-b`. The `No` and `Yes` counts add up to the unfiltered count, with no name in both.
   - **`Stateful = No` / `Yes`:** the counts add up to the unfiltered count, and `sg-a-stateless` appears only under `No`.
   - **Search and sort:**
     - searching `default` gives one row, with and without a filter;
     - sorting Name asc/desc gives the same relative order with and without a filter.
   - **Reload:** reload with `?shared=false&stateful=false&search=…&sortDirection=desc`. The results and filter pills are the same.
   - **Non-admin:** repeat the unfiltered and `Shared` checks as a non-admin member of A. The results match what the admin sees.
   - **Layout:** the list looks the same as on `main`. The kebab menu, the sort and filter dropdowns, and the modals all work. The refetch-error banner sits above the header, and the Name column is aligned as before.

# Checklist

- [x] I have performed a self-review of my code.
- [x] I have commented my code, particularly in hard-to-understand areas.
- [x] I have added tests that prove my fix is effective or that my feature works.
- [x] New and existing unit tests pass locally with my changes.
- [x] I have made corresponding changes to the documentation (if applicable).
- [x] My changes generate no new warnings or errors.
