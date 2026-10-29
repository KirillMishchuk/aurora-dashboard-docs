# PR #1393: feat(aurora): add Key Manager (Barbican) in-core plugin

Author: hodanoori · State: open · https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393
Code: `origin/pr/1393` (head `8763f93b`) — read it with `git show origin/pr/1393:<path>` and `git diff origin/main...origin/pr/1393`, not from the working tree.

## Description

# Summary

Adds a Key Manager (OpenStack Barbican) in-core plugin to the Aurora package, following
the documented `aurora-plugin` pattern and the conventions of the existing network
plugins. It surfaces three Barbican resources — Secrets, Containers, and Orders — under a
new Authorization nav section that appears only when the `key-manager` / `barbican`
service is present in the project catalog.

# Changes Made

- Add the server side under `packages/aurora/src/server/KeyManager/`: `keyManagerRouter`
  tRPC procedures for secrets (list/get/payload/create/update/delete), containers
  (list/get/create/delete, add/remove secret refs) and orders (list/get/create/delete),
  with Zod schemas, a permission router via the shared `createPermissionRouter`, policy
  mappings in `apps/dashboard/src/policies/key-manager.json`, and registration in
  `server/routers.ts`.
- Add the client side under `…/authorization/key-manager/`: layout plus per-resource list
  and detail routes with catalog-guarded navigation, Juno three-zone DataGrid lists
  (search, sort, pagination), detail views, create/delete modals, and a new Authorization
  nav section in `buildNavSections`.
- Align naming with the merged network plugins (`*ListContainer` singular, `*DetailsView`)
  and apply the Juno DataGridSpec (empty cells render as `- -`; the status column sits
  immediately after the primary column).
- Add unit tests mirroring the other plugins: router procedures, Zod schema validation,
  and client DataGrid components (TableRow + ListContainer) for all three resources.

# Related Issues

- Epic: #1133  

# Screenshots (if applicable)

<!-- If there are any visual changes, provide screenshots or GIFs. -->

# Testing Instructions

<!-- Describe the steps needed to test this pull request. -->

1. `pnpm i`
2. `pnpm run test`

# Checklist

<!-- Ensure that your pull request meets the following requirements. -->

- [x] I have performed a self-review of my code.
- [ ] I have commented my code, particularly in hard-to-understand areas.
- [ ] I have added tests that prove my fix is effective or that my feature works.
- [ ] New and existing unit tests pass locally with my changes.
- [ ] I have made corresponding changes to the documentation (if applicable).
- [ ] My changes generate no new warnings or errors.
