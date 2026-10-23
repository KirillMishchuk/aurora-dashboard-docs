---
type: pr-report
date: 2026-10-23
status: open
pr: [1393]
issue: [1133]
author: hodanoori
branch: feat/key-manager-plugin
---

# PR #1393: feat(aurora): add Key Manager (Barbican) in-core plugin

**Author:** hodanoori · **Status:** open · **Base:** `main` ← `feat/key-manager-plugin`
**Size:** 48 files, +4439 / −3 · **Created:** 2026-10-23 · [View on GitHub](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393)

---

## PR Review Report by [review-and-comment-pr](https://github.com/KirillMishchuk/aurora-dashboard-docs/blob/main/ToolDocs/claude-config/aurora-dashboard-config/.claude/skills/review-and-comment-pr/SKILL.md)

_Reviewed at head [`fd248f08`](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393/commits/fd248f083f89fbe9caca6ad536106ffd08860159) · base `main` at `c65b36d0` · 2026-10-23 12:55 UTC_

### ⚖️ &nbsp; Verdict

Recommendation: **🔴 Request Changes** &nbsp;&nbsp;&nbsp;&nbsp; Confidence to Merge: **Medium**

- **Must fix before merge** (#1133 — full feature (Secrets, Containers, Orders CRUD)): CR2, CR3
- **Team call** (existing pattern or deferred by a maintainer): CR1, CR4, CR5
- **Process:** P1

New Key Manager (Barbican) plugin adds secrets, containers and orders management with comprehensive tRPC procedures and unit tests. Two bugs need fixing: a Lingui interpolation error in order delete modals and a missing `isEnabled` check that breaks service visibility configuration. The Reveal Payload button lacks the client-side permission gate required by issue acceptance criteria. Acceptance partly met: container secret association UI and E2E tests are missing.

### 🔧 &nbsp; Required Changes

| #   | Severity    | Category | Precedent     | Issue                                                                                                   | Location                                                                                                                                 |
| --- | ----------- | -------- | ------------- | ------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| CR1 | 🟠 Major    | Security | existing code | Reveal Payload button not gated by permission check, violating fail-closed UI principle                 | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretDetailsView.tsx:89`     |
| CR2 | 🟠 Major    | Bug      | —             | Lingui template uses `${orderTypeLabel}` instead of `{orderTypeLabel}`, displaying literal text         | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/OrderModals.tsx:137`           |
| CR3 | 🟡 Moderate | UI/UX    | —             | Modals missing `disableCloseButton` during async operations, allowing bypass via X button               | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainerModals.tsx:49-50` |
| CR4 | 🟡 Moderate | Bug      | existing code | Key Manager nav entry ignores `enabledServices`/`deniedServices`, breaking service visibility           | `packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.ts:154`                                                   |
| CR5 | 🟡 Moderate | UI/UX    | existing code | `usePermissions` doesn't expose `isError`, so query failures show misleading "insufficient permissions" | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/-components/usePermissions.ts:24`                 |
| P1  | —           | Process  | —             | Published package code changed without a `.changeset/*.md`                                              | PR files                                                                                                                                 |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**CR1 — Reveal Payload button shown unconditionally without permission check** · Security · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretDetailsView.tsx:89`
The Reveal Payload button at `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretDetailsView.tsx:89` is rendered for any user who can view the secret detail page. Issue #1133 acceptance criteria explicitly require gating this action via `canUser('key-manager:secrets:get')`, and the policy file defines the rule. The server enforces the permission through Barbican, but the UI doesn't follow the fail-closed pattern: users without `keymanager_viewer` role can attempt payload retrieval and receive an error instead of never seeing the button.
_Precedent:_ the same pattern is already in merged code — `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/index.tsx:330`.
_Fix:_ Import `usePermissions` and conditionally render the button only when `permissions['key-manager:secrets:payload']` or `permissions['key-manager:secrets:get']` is true, matching the pattern in SecretsList, ContainersList and OrdersList.

**CR2 — Wrong interpolation syntax in delete order confirmation message** · Bug · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/OrderModals.tsx:137`
The delete confirmation at `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/OrderModals.tsx:137` uses JavaScript template literal syntax `${orderTypeLabel}` inside a Lingui tagged template. Lingui expects `{orderTypeLabel}` without the dollar sign. At runtime, the message shows the literal text `${orderTypeLabel}` instead of the order type (key, asymmetric, certificate).
_Fix:_ Change `${orderTypeLabel}` to `{orderTypeLabel}` in the Lingui template string.

**CR3 — Close button not disabled during pending mutations in modals** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainerModals.tsx:49-50`
CreateContainerModal sets `disableConfirmButton` and `disableCancelButton` during the pending mutation at `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainerModals.tsx:50` but omits `disableCloseButton`. B.5 requires all three to be synchronized. Users can click the X to close the modal while a create/delete is in flight, which may lead to confusing state. The same issue appears in DeleteContainerModal, and all modals in OrderModals.tsx and SecretModals.tsx.
_Fix:_ Add `disableCloseButton={createMutation.isPending}` (or the relevant mutation's `isPending`) alongside the existing props in each modal.

**CR4 — Missing `isEnabled("key-manager")` check in navigation builder** · Bug · `packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.ts:154`
The Key Manager nav entry at [[at:packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.ts | serviceIndex["key-manager"]?.["barbican"]]] checks only the service catalog but omits the `isEnabled("key-manager")` call. All other services (images, flavors, containers, securitygroups, floatingips, routers) use both checks. Without it, consumers cannot hide Key Manager via `appConfig.enabledServices` or `deniedServices`, breaking the established service visibility contract.
_Precedent:_ the same pattern is already in merged code — `packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.ts:36`.
_Fix:_ Change the condition to `serviceIndex["key-manager"]?.["barbican"] && isEnabled("key-manager")`.

**CR5 — Permission hook hides query errors, causing misleading UI state** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/-components/usePermissions.ts:24`
The `usePermissions` hook at `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/-components/usePermissions.ts:24` returns only `permissions` and `isLoading` in its return type. When the tRPC query fails, `data` defaults to `[]` and all permissions map to `false`, so the three list components show "You do not have permission…" instead of an error state. The `useCephPermissions` hook exposes `isError` for this reason, and PR #1207's review flagged the same pattern.
_Precedent:_ the same pattern is already in merged code — `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/hooks/useCephPermissions.ts:115`.
_Fix:_ Expose `isError` from the query and handle it in ContainersList, OrdersList and SecretsList to show an error message instead of the permissions warning.

**P1 — No changeset** · Process · PR files
The PR changes published code under `packages/aurora/src` but adds no changeset, so the change gets no version bump or changelog entry.
_Fix:_ Run `pnpm changeset`, pick the bump type and commit the generated `.changeset/*.md`.

</details>

### 💡 &nbsp; Improvements

| #   | Severity | Category      | Precedent     | Issue                                                                                  | Location                                                                                                                                   |
| --- | -------- | ------------- | ------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| I1  | 🟢 Low   | Accessibility | existing code | PopupMenu used without PopupMenuToggle, missing keyboard accessibility                 | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainerTableRow.tsx:34`    |
| I2  | 🟢 Low   | UI/UX         | existing code | Sort controls use custom Select+SortButton instead of standard SortInput component     | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:83-94`          |
| I3  | 🟢 Low   | UI/UX         | —             | Single-entity menus missing divider before Delete action per B.18                      | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainerTableRow.tsx:35-37` |
| I4  | 🟢 Low   | UI/UX         | —             | Delete modal titles include entity name instead of putting it in the body per B.5      | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainerModals.tsx:109`     |
| I5  | 🟢 Low   | Bug           | —             | `listOrders` sends `sort_key`/`sort_dir` that Barbican silently ignores                | `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:269-273`                                                                |
| I6  | 🟢 Low   | Bug           | —             | `listContainers` doesn't support `type` filter even though Barbican accepts it         | `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:29-31`                                                                  |
| I7  | 🟢 Low   | UI/UX         | —             | Backend has update/manage procedures for secrets and containers but no UI exposes them | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager`                                                    |
| I8  | 🟢 Low   | Test coverage | —             | Strong unit test coverage but no E2E tests for the new Key Manager feature             | PR files                                                                                                                                   |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**I1 — Context menus lack PopupMenuToggle wrapper** · Accessibility · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainerTableRow.tsx:34`
ContainerTableRow, OrderTableRow and SecretTableRow use `<PopupMenu>` directly at `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainerTableRow.tsx:34` without a `<PopupMenuToggle as="div">` wrapper. B.14 requires the toggle for keyboard accessibility.
_Precedent:_ the same pattern is already in merged code — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/routers/-components/RouterTableRow.tsx:82`.
_Fix:_ Wrap the trigger button with `<PopupMenuToggle as="div">` in each table row component.

**I2 — Inconsistent sort control pattern in list toolbars** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:83-94`
SecretsList and OrdersList at `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:83` use a custom Select + SortButton combination for sorting instead of the `SortInput` component required by B.1. All other list pages (flavors, images, routers, security groups, storage) use SortInput.
_Precedent:_ the same pattern is already in merged code — `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/flavors/-components/List.tsx:145`.
_Fix:_ Replace the Select + SortButton combination with the `SortInput` component from `@/client/components/ListToolbar/SortInput`.

**I3 — No divider separating Delete from other menu items** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainerTableRow.tsx:35-37`
The popup menus in ContainerTableRow, OrderTableRow and SecretTableRow at `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainerTableRow.tsx:35` have Show Details and Delete without a divider between them. B.18 requires single-entity menus to separate the destructive action with a divider.
_Fix:_ Add a divider component before the Delete menu item in each table row's popup menu.

**I4 — Modal titles should be generic, entity name belongs in body** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainerModals.tsx:109`
DeleteContainerModal, DeleteOrderModal and DeleteSecretModal use titles like `` t`Delete Container "${containerName}"` `` at `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainerModals.tsx:109`. B.5 says to put the object name in the body, not the title.
_Fix:_ Use a generic title (e.g. `Delete Container`) and reference the entity by name in the confirmation body.

**I5 — Sort parameters not supported by Barbican orders API** · Bug · `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:269-273`
The `listOrders` procedure at `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:271` sends `sort_key` and `sort_dir` query params, but the Barbican orders API only accepts `offset`, `limit` and `meta`. It always sorts by `created_at`. The parameters are silently ignored, so the UI's sort controls don't actually change the order.
_Fix:_ Remove sort handling from `listOrders` input and implementation, and hide or disable the sort control in OrdersList since the API doesn't support it.

**I6 — Missing container type filter in list endpoint** · Bug · `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:29-31`
The `containersSearchInput` schema at `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:29` omits the `type` field, and `listContainers` doesn't send it. Barbican accepts `type` (generic, rsa, certificate) for filtering. This limits the feature but doesn't break existing functionality.
_Fix:_ Add `type: z.enum(['generic', 'rsa', 'certificate']).optional()` to `containersSearchInput` and pass it as a query parameter when present.

**I7 — Container secret management procedures not wired to UI** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager`
The server exposes `updateSecret`, `addContainerSecret` and `deleteContainerSecret` procedures, but the client has only Create and Delete modals. Phase 2 acceptance asks for container secret association management, which the backend supports but the UI doesn't surface.
_Fix:_ Consider adding a ManageContainerSecretsModal or noting this as follow-up work for Phase 2 completion.

**I8 — E2E test coverage missing** · Test coverage · PR files
Unit tests cover all 16 server procedures, schema validation and client components (~1400 lines total), but no Playwright tests were added under `apps/dashboard/e2e/`. The acceptance criterion asks for "complete testing coverage (unit, integration, E2E)".
_Fix:_ Add E2E tests covering the happy path for listing, creating and deleting secrets, containers and orders.

</details>

---

## Solution Overview

<details>
<summary><strong>What was done</strong></summary>

Adds a complete Key Manager (OpenStack Barbican) in-core plugin to the Aurora package, surfacing three Barbican resources — **Secrets** (sensitive data like keys, certificates, passphrases), **Containers** (logical groupings of secrets), and **Orders** (asynchronous provisioning requests) — under a new **Authorization** navigation section that appears only when the `key-manager`/`barbican` service exists in the project catalog.

**CI status:** 2 jobs pending (`test`, `preview`), 16 passing, 0 failing. The PR body does not claim all checks passed.

The PR delivers **full CRUD** for all three resources via tRPC procedures backed by Zod schemas, a permission router using the shared `createPermissionRouter` factory, and a policy file (`apps/dashboard/src/policies/key-manager.json`) matching the epic's specification. The client provides tabbed navigation (Secrets / Containers / Orders), DataGrid lists with search/sort/pagination, detail views, and create/delete modals, all gated by `canUser(...)` permission checks. The PR follows the merged network plugin conventions (`*ListContainer` singular, `*DetailsView`, status column after the primary column) and the Juno DataGrid spec (empty cells render as `- -`).

</details>

<details>
<summary><strong>How it is implemented</strong></summary>

**Server (packages/aurora/src/server/KeyManager/):**

Zod schemas define `SecretSchema`, `ContainerSchema`, `OrderSchema`, and their list responses, plus input schemas for create/update operations:

```ts
export const SecretSchema = z.object({
  secret_ref: z.string(),
  name: z.string().nullable(),
  status: z.string(),
  algorithm: z.string().nullable(),
  bit_length: z.number().nullable(),
  mode: z.string().nullable(),
  secret_type: z.string(),
  content_types: z.record(z.string(), z.string()).nullable().optional(),
  created: z.string(),
  updated: z.string(),
  expiration: z.string().nullable(),
  creator_id: z.string().nullable().optional(),
})
```

The keyManagerRouter exposes 16 procedures, all using `projectScopedProcedure` for automatic token rescoping: Secrets (list/get/payload/create/update/delete), Containers (list/get/create/delete/addSecret/deleteSecret), Orders (list/get/create/delete). Each procedure fetches from the `key-manager` service via `ctx.openstack.service("key-manager")`, validates responses with `parseOrThrow`, and maps HTTP errors to tRPC codes via `mapKmError`:

```ts
listSecrets: projectScopedProcedure
  .input(projectScopedInputSchema.extend({ ...paginationInput.shape, ...secretsSearchInput.shape }))
  .query(async ({ input, ctx }) => {
    const km = ctx.openstack?.service("key-manager")
    validateOpenstackService(km, "key-manager")
    const params = new URLSearchParams()
    params.set("offset", String(input.offset))
    params.set("limit", String(input.limit))
    if (input.name) params.set("name", input.name)
    if (input.sort) params.set("sort", input.sort)
    const res = await km.get(`v1/secrets?${params}`).catch((e: unknown) => {
      throw mapKmError(e, "list secrets")
    })
    if (!res.ok) throw mapKmError({ statusCode: res.status }, "list secrets")
    return parseOrThrow(SecretsListSchema, await res.json(), "keyManager.listSecrets")
  }),
```

The permission router uses `createPermissionRouter` to expose a `canUser` query, mapping 16 permission keys to the `keyManager` policy engine:

```ts
export const buildKeyManagerPermissionRouter = (policyDir: string) =>
  createPermissionRouter({
    policyDir,
    engines: {
      keyManager: { fileName: "key-manager.json" },
    },
    mappings: KEY_MANAGER_MAPPINGS,
  })
```

The policy file defines `context_is_keymanager_admin`, `context_is_keymanager_editor`, `context_is_keymanager_viewer` rules and maps them to 16 permission keys:

```json
"context_is_keymanager_editor": "(rule:context_is_keymanager_admin) and not project_id:nil",
"context_is_keymanager_viewer": "(rule:context_is_keymanager_editor or rule:keymanager_viewer) and not project_id:nil",

"key-manager:secrets:list": "rule:context_is_keymanager_viewer",
"key-manager:secrets:get": "rule:context_is_keymanager_viewer",
"key-manager:secrets:payload": "rule:context_is_keymanager_viewer",
"key-manager:secrets:create": "rule:context_is_keymanager_editor",
"key-manager:secrets:delete": "rule:context_is_keymanager_editor",
"key-manager:secrets:update": "rule:context_is_keymanager_editor",

"key-manager:containers:list": "rule:context_is_keymanager_viewer",
"key-manager:containers:get": "rule:context_is_keymanager_viewer",
"key-manager:containers:create": "rule:context_is_keymanager_editor",
"key-manager:containers:delete": "rule:context_is_keymanager_editor",
"key-manager:containers:update": "rule:context_is_keymanager_editor",

"key-manager:orders:list": "rule:context_is_keymanager_viewer",
"key-manager:orders:get": "rule:context_is_keymanager_viewer",
"key-manager:orders:create": "rule:context_is_keymanager_editor",
"key-manager:orders:delete": "rule:context_is_keymanager_editor",
"key-manager:orders:update": "rule:context_is_keymanager_editor"
```

Router registration wires `buildKeyManagerRouters(policyDir)` into the app router:

```ts
auroraRouter(buildKeyManagerRouters(policyDir))
```

**Client (packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/):**

The layout route guards access via `beforeLoad` — it checks `serviceIndex["key-manager"]?.["barbican"]` from `auth.getAvailableServices` and redirects to the project page if absent:

```tsx
const isContainersRoute = Boolean(containersIndexMatch ?? containersDetailMatch)
const isOrdersRoute = Boolean(ordersIndexMatch ?? ordersDetailMatch)
const activeTab = isContainersRoute ? "containers" : isOrdersRoute ? "orders" : "secrets"

const tabPaths = {
  secrets: "/projects/$projectId/authorization/key-manager/secrets",
  containers: "/projects/$projectId/authorization/key-manager/containers",
  orders: "/projects/$projectId/authorization/key-manager/orders",
} as const

return (
  <div>
    <ContentHeader title={t`Key Manager`} projectId={projectId} />
    <TabNavigation
      activeItem={activeTab}
```

The layout renders a `TabNavigation` with three tabs (Secrets / Containers / Orders), deriving the active tab from route matches:

```tsx
<TabNavigation
  activeItem={activeTab}
  onActiveItemChange={(value: unknown) => {
    const tab = String(value) as "secrets" | "containers" | "orders"
    void navigate({ to: tabPaths[tab], params: { projectId } })
  }}
>
  <TabNavigationItem label={t`Secrets`} value="secrets" />
  <TabNavigationItem label={t`Containers`} value="containers" />
  <TabNavigationItem label={t`Orders`} value="orders" />
</TabNavigation>
```

Per-resource routes handle URL search params (search, sort, page), call their respective `list*` tRPC queries, and pass results to `*List` components. Detail routes fetch a single resource and render `*DetailsView`.

The permissions hook batches permission checks via `trpcReact.keyManager.canUser.useQuery`, returning a map of permission keys to boolean values:

```ts
export function usePermissions(
  projectId: string,
  permissions: KeyManagerPermission[]
): { permissions: Record<KeyManagerPermission, boolean>; isLoading: boolean } {
  const { data = [], isLoading } = trpcReact.keyManager.canUser.useQuery(
    { project_id: projectId, permission: permissions },
    { enabled: Boolean(projectId), staleTime: Infinity }
  )

  return {
    isLoading,
    permissions: Object.fromEntries(permissions.map((p, i) => [p, data[i] ?? false])) as Record<
      KeyManagerPermission,
      boolean
    >,
```

List components provide search/sort/pagination controls, call the tRPC list query, check `canCreate` / `canDelete` permissions, and render a DataGrid via `*ListContainer` + `*TableRow`. Create/Delete buttons are conditionally rendered based on permissions.

Modals provide `Create*Modal` (form with name, type, and type-specific fields) and `Delete*Modal` (confirmation dialog). Mutations invalidate the list query on success.

Detail views fetch a single resource, display a `TwoColumnDescriptionList` of metadata, and (for Containers) a nested DataGrid of associated secrets. For Secrets, `SecretDetailsView` includes a Reveal Payload button that fetches the payload on demand via `getSecretPayload` (line 89 renders the button unconditionally without permission check; this is flagged as CR1).

Navigation adds a Key Manager entry to the Authorization section when the service exists:

```ts
...(serviceIndex["key-manager"]?.["barbican"]
  ? [
      {
        service: "key-manager",
        label: t`Key Manager`,
        navigate: (nav: NavigateFn) =>
          nav({
            to: "/projects/$projectId/authorization/key-manager/secrets",
            params: { projectId },
          }),
        params: { projectId },
      },
    ]
  : []),
```

</details>

<details>
<summary><strong>What it affects (blast radius)</strong></summary>

**Contract changes:**

- **New tRPC router:** `keyManager` with 15 procedures. All are internal to `packages/aurora`; no external consumers exist at `headRefOid`.
- **New route namespace:** `/_auth/projects/$projectId/authorization/key-manager/*` (8 routes: layout, 3 index routes, 3 detail routes, 1 redirect). Generated in `routeTree.gen.ts`.
- **Policy file:** `apps/dashboard/src/policies/key-manager.json` — the policy engine loads this file; no code outside the KeyManager domain references it directly.
- **Navigation:** `buildNavSections` (shared by all projects) now includes Authorization section logic checking for `key-manager` service.

**Blast radius:**

All KeyManager code is self-contained under `packages/aurora/src/server/KeyManager/` and `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/`. The only cross-domain touch is `buildNavSections.ts` (23 lines added for the Authorization section and Key Manager entry).

The Authorization section in `buildNavSections` is new — before this PR, `sectionMap` had no "authorization" key:

```ts
[
  "authorization",
  {
    section: "authorization",
    label: t`Authorization`,
    services: [
      ...(serviceIndex["key-manager"]?.["barbican"]
        ? [
            {
              service: "key-manager",
              label: t`Key Manager`,
              navigate: (nav: NavigateFn) =>
                nav({
                  to: "/projects/$projectId/authorization/key-manager/secrets",
                  params: { projectId },
                }),
              params: { projectId },
            },
          ]
        : []),
    ],
  },
],
```

This section is only rendered when `services.length > 0`, so it won't appear for projects without Barbican.

No stale callers: the router, routes, and types are all new.

**Documentation:** No changes to `packages/aurora/README.md` (the consumer-facing contract). The Key Manager feature is implicitly available once `packages/aurora` is updated (services are auto-discovered via the catalog), so no new consumer configuration is needed.

</details>

---

## QA Test Plan

<details>
<summary><strong>Core Path</strong></summary>

1. Navigate to a project that has Barbican (`key-manager`/`barbican`) in its service catalog. The Side Navigation should show an **Authorization** section with a **Key Manager** entry.
2. Click **Key Manager**. The page should load with three tabs: **Secrets**, **Containers**, **Orders**. The **Secrets** tab is active by default.
3. On the **Secrets** tab, the list should render with columns: **Name / ID**, **Status**, **Type**, **Content Types**. Search for a secret by name, sort by created/updated, and paginate through results.
4. Click **Create Secret**. Fill in the form (name, type, payload, content type), submit, and verify the new secret appears in the list.
5. Click the More menu on a secret row and select **Show Details**. The detail page should display metadata (ID, reference, status, type, algorithm, bit length, created, updated, expiration) and a **Reveal Payload** button (if permitted).
6. Click **Reveal Payload** (if the `key-manager:secrets:payload` permission is granted). The payload should appear in a code block. Click **Hide Payload** to mask it again.
7. Return to the list, click More > **Delete**, and confirm. The secret should be removed.
8. Switch to the **Containers** tab. The list should render with columns: **Name / ID**, **Status**, **Type**. Click **Create Container**, select a type (generic/rsa/certificate), optionally add a name, and submit. Verify the new container appears.
9. Click **Show Details** on a container row. The detail view should display container metadata and a nested DataGrid of associated secrets (if any).
10. Return to the list, delete the container (if permitted), and verify it's removed.
11. Switch to the **Orders** tab. The list should render with columns: **Name / ID**, **Status**, **Type**. Click **Create Order**, select an order type (key/asymmetric/certificate), fill in meta fields, and submit.
12. Click **Show Details** on an order row. The detail view should display order metadata (type, status, sub_status, meta, secret_ref, created, updated).
13. Delete the order (if permitted) and verify it's removed.

</details>

<details>
<summary><strong>Edge Cases</strong></summary>

- Navigate to a project **without** Barbican in the catalog. The Authorization section should not appear in the Side Navigation. `packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.ts:154` (the nav entry check) and `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager.tsx:46-47` (the beforeLoad redirect)
- Try to access `/projects/<projectId>/authorization/key-manager/secrets` directly when Barbican is unavailable. The `beforeLoad` guard should redirect to `/projects/<projectId>`. `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager.tsx:46-52`
- A secret with `name: null` should render as **unnamed** in the list. `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:24`
- A container with no associated secrets should display an empty state: No Secrets in This Container. `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainerDetailsView.tsx:87`
- An order with `sub_status: null` or `sub_status_message: null` should render those fields as `- -`. `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/OrderDetailsView.tsx:42-43`
- If `getSecretPayload` fails (403, 404, or network error), the error message should appear inline in the detail view. `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretDetailsView.tsx:96-97`
- If the user lacks `key-manager:secrets:create` permission, the **Create Secret** button should be hidden. `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:131`
- If the user lacks `key-manager:containers:delete` permission, the **Delete** action in the container row menu should not appear. `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainerTableRow.tsx:34-36`
- When creating a container with an invalid type (not `generic`/`rsa`/`certificate`), Zod validation should reject it before it reaches the server. `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:194`
- Empty lists (no secrets, no containers, no orders) should render an empty state with a helpful message (e.g., No Secrets Found). `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretListContainer.tsx:53-57`
- HTTP 404 from Barbican when fetching a missing resource should surface as a user-friendly Secret Not Found / Container Not Found / Order Not Found status. `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:47`
- Network or tRPC errors in `beforeLoad` (e.g., session expired) should redirect to the project page rather than showing the error component. `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager.tsx:89-92`
- Delete an order via the modal: the confirmation message displays literal `${orderTypeLabel}` instead of the order type. CR2
- Set `deniedServices: ['key-manager']` in appConfig: the Key Manager nav entry still appears because `isEnabled()` is not called. CR4
- Select a sort option in the Orders list: the list order doesn't change because Barbican ignores the sort parameters. I5
- Filter containers by type (generic/rsa/certificate): not possible because the filter isn't exposed. I6

</details>

---

## Checked and dismissed

<details>
<summary><strong>Candidates scored below 50 (2)</strong></summary>

| Score | Candidate                                                                                                                  | Location                                                                                                                       | Why                                                           |
| ----- | -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------- |
| 25    | The permission naming convention violates the B.8 RBAC standard — boolean props must be named can&lt;Verb&gt;&lt;Noun&gt;. | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/-components/usePermissions.ts:32`       | Checked at headRefOid usePermissions.ts:24-35.                |
| 25    | Zone structure does not follow B.2 standard: sort controls should use distribution="between" with the create button.       | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:81` | Checked at headRefOid line 81: Stack uses distribution="end". |

</details>

---

_Analyzed 2026-10-23 · commit `fd248f08` · read-only · skill: review-and-comment-pr_
