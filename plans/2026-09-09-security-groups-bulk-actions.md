# Plan: Bulk Actions (multi-select + bulk delete) for Security Groups — list, Rules tab, RBAC Policies tab

**Date:** 2026-09-09 · **Status:** implemented 2026-09-09

# IMPLEMENTATION PLAN: Bulk Delete for Security Groups (list, Rules tab, RBAC tab)

*(Note on process: this plan was produced by `dev-planner`, which reported `AskUserQuestion` unavailable and therefore left six questions open at the end. All six were resolved with the user on 2026-09-09 — see the table immediately below. **The body of the plan has been updated in place to match**, so Steps 13 and 16 no longer describe what the original draft proposed.)*

## Decisions resolved after review (2026-09-09)

| # | Question | Decision |
| --- | --- | --- |
| 1 | Delivery | **Leave everything in the working tree, uncommitted**, as the current go-live work on this branch already is. Nothing is pushed to the remote. |
| 2 | 404 on a per-item DELETE | **Treated as success**, in the bulk processors only. The single-item procedures keep reporting `NOT_FOUND`. |
| 3 | Fan-out cap / concurrency | **Keep the guard rails** (`MAX_BULK_DELETE_ITEMS = 100`, `chunkSize: 5`) **and** batch client-side into ≤100-ID calls, merging results — see the new **Step 9a**. Necessary because the security groups list is *not* paginated (`securityGroup.list` returns everything; pagination is a separate unimplemented plan from 2026-07-23), so select-all can exceed the cap in a large project. |
| 4 | `canManageAccess` over-gating the RBAC bulk action | **Left as-is**, matching `RBACPolicyRow`'s existing gate. Splitting out a `canDeleteRBAC` flag is a possible follow-up, out of scope here. |
| 5 | Bulk gate vs single-item gate | **Revises fixed requirement #3 — all three bulk modals get a type-to-confirm gate.** Verified in the working tree that all three single-item dialogs already require typing: `DeleteSecurityGroupDialog` and `DeleteRuleDialog` want `delete`, `DeleteRBACPolicyDialog` wants **`remove`** (the original draft claimed `delete` for both — that was wrong). Without this change, deleting 20 rules at once would be *easier* than deleting one, and the Ceph `DeleteCorsRulesModal` precedent does not justify it: Ceph's *single* CORS delete has no typed gate either, so there bulk is simply not weaker than single. The invariant to preserve is **bulk gate ≥ single-item gate**. |
| 6 | Missing `DeleteCorsRulesModal.test.tsx` | Confirmed absent from the repo; the new modal tests template off `Ceph/Objects/DeleteObjectsModal.test.tsx` / `Swift/Containers/EmptyContainersModal.test.tsx` instead. |

## Overview

Add multi-select + server-side bulk delete to the three Security Groups surfaces: the group list ("Delete Selected Groups"), the detail page's Rules tab ("Delete Selected Rules"), and the RBAC Policies tab ("Remove Selected Policies"). Fan-out happens in the BFF via three new tRPC procedures returning a typed partial-result object, modelled on the Compute Images pattern but with a **Network-local** helper. No new permission keys are needed.

## Architecture Analysis

### Current state — the three surfaces (working tree, branch `kiryl-security-groups-go-live`)

| File | Role today |
| --- | --- |
| `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/-components/SecurityGroupsList.tsx` | Owns the `securityGroup.list` query (with `placeholderData: (prev) => prev`), URL-backed filter/sort/search, create/update/delete mutations + toasts. Passes `hasAnyBulkAction={false}` hardcoded at line 362. |
| `.../-components/SecurityGroupListContainer.tsx` | Renders the `DataGrid`. Already switches `columnCount` (6/5) and `minContentColumns` (`[5]`/`[4]`) on `hasAnyBulkAction`, already emits a leading empty `DataGridHeadCell`, already computes `isReadOnly` per row (line 144), and passes `isSelected={false} onSelect={() => {}}` (lines 156-157). |
| `.../-components/SecurityGroupTableRow.tsx` | Already accepts `showSelectColumn`/`isSelected`/`onSelect` and renders a Juno `Checkbox` in a `stopPropagation` cell (lines 63-67). |
| `.../$securityGroupId/-components/-details/SecurityGroupRulesTable.tsx` | Presentational. Receives already-filtered/sorted `rules`; `columnCount = canDeleteRule ? 6 : 5`; owns single-delete dialog state and the `formatPortRange` closure (lines 109-136). |
| `.../-details/SecurityGroupRBACPolicies.tsx` | Self-contained: owns its `rbacPolicy.list` query, delete mutation, toasts, client-side search, `RBAC_COLUMN_COUNT = 3`. |
| `.../-details/RBACPolicyRow.tsx` | Two data cells + action cell gated on `canDelete`; no select column, no `key`-relevant props. |
| `.../$securityGroupId/-components/SecurityGroupDetailsView.tsx` | Owns `activeTab` and **conditionally renders** each tab (`activeTab === "rules" && <SecurityGroupRulesTable …>`), i.e. tab content unmounts on switch. |
| `.../$securityGroupId/-hooks/useSecurityGroupDetails.ts` | Owns `securityGroup.getById`, client-side rule filter/sort (`filteredAndSortedRules`), and all rule/group mutations + invalidations + toasts. **Rules are not their own query.** |
| `.../-hooks/useSecurityGroupPermissions.ts` | One batched `network.canUser` with 9 keys; `canManageAccess = canCreateRBAC && canDeleteRBAC`; `staleTime`/`gcTime: Infinity`; fail-closed defaults. |
| `.../-components/SecurityGroupToastNotifications.tsx` | 14 single-item builders, `{ message, description }` shape, no `severity`, no bulk builders. |

### Current state — server

- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Network/routers/securityGroupRouter.ts` — `deleteById` = `projectScopedProcedure` + `withErrorHandling` + `validateAndEncodeResourceId(id, "Security group")` + `SecurityGroupErrorHandlers.delete(response, id)`.
- `.../securityGroupRuleRouter.ts` — `delete` same shape (the `validateAndEncodeResourceId` call is **new on this branch**, staged). No test file exists for this router.
- `.../rbacPolicyRouter.ts` — `delete` same shape (`validateAndEncodeResourceId` also **new on this branch**). `rbacPolicyRouter.test.ts` exists.
- All three are composed in `.../Network/routers/index.ts` under `network.{securityGroup,securityGroupRule,rbacPolicy}`.
- Error mapping layers, outermost first: `openstackErrorMiddleware` (`server/trpc.ts`, only sees errors that *escape* the procedure) → `withErrorHandling`/`wrapError` (`server/helpers/errorHandling.ts`, passes `TRPCError` through untouched, maps `SignalOpenstackError` → `BAD_REQUEST`) → per-domain `*ErrorHandlers`.

### Reference: Compute Images bulk (`server/Compute/helpers/imageHelpers.ts`)

`processBulkOperation<T extends {id:string}>(items, processor, {chunkSize?, delayBetweenChunks?, operation?})` → `Promise<BulkOperationResult>`. `formatBulkOperationError` returns `error.message` verbatim for a `TRPCError`, otherwise `` `Failed to ${operation} image: …` ``. Failures are pushed as **`{ imageId, error }`**. `bulkOperationResultSchema` lives in `Compute/types/image.ts`.

### Proposed changes — decisions and justifications

**D1. Network-local bulk helper, not a shared extraction.** Recommend option **(b)**: new `server/Network/helpers/bulkOperations.ts`. Reasons:

1. Blast radius. Renaming `failed[].imageId` → `id` touches `Compute/types/image.ts`, two push sites in `imageHelpers.ts`, ~4 assertions in `imageHelpers.test.ts`, ~6 in `Compute/types/image.test.ts`, and 2 in `imageRouter.test.ts` (`result.failed[0].imageId`). I verified the **images client never reads `result.failed`** — `DeleteImagesModal`'s `DeleteResult.errors[].imageId` is internal state that nothing ever sets (the results screen is unreachable, a known finding). So the rename is compile-safe but forces Compute test churn into a Security-Groups review.
2. The Compute helper is not actually generic: `formatBulkOperationError` hardcodes the word `image` in three of its four branches, so "extract as-is" would need a `resourceLabel` parameter anyway.
3. `chunkSize`/`delayBetweenChunks` are dead in all three Compute call sites (all call with `{ operation }` only) — promoting them into a shared module would enshrine unused complexity.
4. If a third domain needs it, promote then to `server/helpers/bulkOperations.ts` and migrate Compute in a dedicated PR.

**D2. `validateAndEncodeResourceId` runs once up-front, not per-item.** Whole-call `BAD_REQUEST` on any malformed ID. Rationale: the UI can only send IDs it read back from Neutron, so a malformed ID means a tampered/buggy client, and half-executing a batch built from tampered input is worse than rejecting it. This is a security boundary, so it should fail closed and fail early (`SignalOpenstackError` → `BAD_REQUEST` via `wrapError`). [SECURITY]

**D3. Whole-call failure vs per-item failure.**
- **Whole call throws** (client sees a rejected mutation, no partial result): rescope failure (handled by `projectScopedProcedure` before the handler body), missing/unavailable `network` service (`getNetworkService` → `validateOpenstackService`), empty ID array, array over the size cap, any malformed ID (D2). These are "the request is not executable" conditions; returning `{successful: [], failed: […]}` for them would make the UI render a per-item failure list for one systemic cause.
- **Per item**: everything the individual `DELETE` can produce. Inside the processor, on `!response.ok` throw the **existing** handler — `SecurityGroupErrorHandlers.delete(response, id)`, `SecurityGroupRuleErrorHandlers.delete(response, id)`, `RBACPolicyErrorHandlers.delete(response, id)` — and let `formatBulkItemError` pass a `TRPCError`'s `.message` through unchanged, so the per-row reason keeps its resource-specific wording ("in use by one or more ports", "not found: <id>", "precondition failed"). A transport-level rejection from `network.del` (including `SignalOpenstackApiError`) also lands in the per-item catch. **Note the middleware nuance:** because per-item errors are caught inside the handler, `openstackErrorMiddleware` never sees them — its 401/403/404 remapping does not apply per item, which is correct (we want the granular Neutron reason, not "Session expired").
- **404 counts as success** (resolved decision 2, bulk path only): check `response?.status === 404` *before* the `!ok` branch and return without throwing, so the item lands in `successful`. In a bulk flow a stale row is the ordinary case — the user selected 20 and someone else already removed 3 — and "not found" is not actionable when the user's intent (make it gone) is already satisfied. Precedent: `Storage/routers/ceph/ec2CredentialRouter.ts` `delete`, which carries the comment `// Idempotent delete: already gone is success` and also ignores a 404 on the DELETE response itself. This deliberately diverges from `compute.deleteImages`, which counts any non-`ok` as a failure. The single-item `deleteById`/`delete` procedures are **not** changed: there a `NOT_FOUND` is worth surfacing, because the user acted on exactly one resource.

**D4. Toast shape — Swift, not Images.** One builder per resource that returns its own `severity`. Nine (3 resources × 3 outcomes) success/partial/error dispatch decisions at the call sites is nine chances for a title/severity mismatch; `getContainersEmptyCompleteToast` (`ContainerToastNotifications.tsx:131`) makes that structurally impossible and is the newer precedent. Callers do `const { message, severity, ...options } = getX(...); toast[severity](message, options)`.

**D5. Zone 3 is permission-gated (Images), not always rendered (Swift), on all three surfaces.** Swift renders its bar unconditionally only because it also hosts the count + quota + limits tooltip, which must always be visible. Our Zone 3 would carry nothing but bulk controls — and the in-flight changeset on this branch deliberately **removed** the rule count and the RBAC project count. An always-rendered bar with a disabled checkbox and a disabled Actions button would be pure noise.

**D6. Zone 3 is a separate `DataGridToolbar` on all three surfaces**, not Ceph's `Divider`-inside-the-existing-toolbar. Ceph's variant is the alternative; rejected because the in-flight changeset explicitly aligned both detail tabs' layout to the list, so the three surfaces should share one structure. Stacked `DataGridToolbar`s have precedent (Swift Containers Zone 2 + Zone 3).

**D7. Selection state placement.**
- **List**: `useState<string[]>` in `SecurityGroupsList.tsx` (it owns the query, the mutations, the toasts and Zone 3). Passed down to `SecurityGroupListContainer` → `SecurityGroupTableRow`, replacing the no-op.
- **Rules tab**: `useState<string[]>` local to `SecurityGroupRulesTable`. Bulk mutation + invalidation + toast live in `useSecurityGroupDetails.ts` (where every other rule mutation lives) and the handler **returns the result** so the table can prune selection.
- **RBAC tab**: `useState<string[]>` local to `SecurityGroupRBACPolicies` (it already owns query + mutation + toasts).
- **Tab switching**: `SecurityGroupDetailsView` conditionally renders each tab, so tab content unmounts and local selection is discarded for free. This is the desired behaviour — state it in a comment so nobody "fixes" it by hoisting the state.

**D8. Selection pruning — derive, never store.** In all three surfaces compute `const validSelectedIds = selectedIds.filter((id) => displayedIds.has(id))` from the currently displayed (filtered+sorted+searched) rows on every render, exactly like `validSelectedImages` (`compute/images/-components/List.tsx:183`). Never `setState` in an effect to prune — on the list the `placeholderData: (prev) => prev` refetch would otherwise wipe selection against a transiently-stale array.

**D9. Selection after a bulk delete.** Full success → clear. Partial failure → keep **only the failed IDs** selected (Swift's `handleEmptyAllComplete`), so the user's next action lands on exactly the rows that need attention. Unlike Swift we don't need its `errors.map(e => e.split(": ")[0])` string-parsing hack — the server returns `failed[].id` directly.

**D10. Undeletable rows.**
- **List, shared-from-another-project**: detectable and reliable — `sg.project_id && sg.project_id !== currentProjectId`. This predicate is currently duplicated three times (`SecurityGroupListContainer.tsx:144`, `$securityGroupId/index.tsx` `isReadOnly`, and it will be needed a fourth time in `SecurityGroupsList.tsx` for the modal split). Extract it once.
- **Neutron's `default` group: NOT reliably detectable client-side, do not invent a check.** `securityGroupSchema` (`server/Network/types/securityGroup.ts:25-37`) has no `is_default` field because Neutron does not return one on the security-group resource; the only signal is `name === "default"`, which is a convention that a `PUT` can rename away. So a name check would produce both false positives (a user-created group literally named "default" in a project whose real default was renamed) and false negatives. Let it land in the partial-failure path (Neutron answers 409) and put the explanation in **UI copy**, not in the server message. [CAREFUL]
- **Known imprecision, accepted:** `SecurityGroupErrorHandlers.delete`'s 409 message says "in use by one or more ports", which is also what a default-group 409 will render. Reusing the handler as-is is required by the brief and is the zero-risk choice; mitigate in the modal/toast copy ("A group can also fail to delete if it is your project's default security group."). Optional follow-up (not in this plan): a `bulkDelete` 409 variant on the handler object.

**D11. Permissions — no new keys.** `network:security_groups:delete`, `network:security_group_rules:delete` and `network:rbac_policies:delete` are already in the batched `canUser` call, so `PERMISSION_KEY_PATTERN.md` needs **no edit** and `Network/routers/permissionRouter.ts` needs **no new mapping**. Gating: list Zone 3 on `permissions.canDelete`, Rules Zone 3 on `canDeleteRule`, RBAC Zone 3 on `canManageAccess`. `canManageAccess` being the AND of RBAC create+delete is over-strict for a delete-only action, but `RBACPolicyRow` already gates its row action on the same flag — a bulk bar visible where the row menu is hidden would be worse than the existing wart. Keep `canManageAccess`; note the option to split out `canDeleteRBAC` as a follow-up.

**D12. Cache invalidation** (mirroring the single-item mutations exactly):
- groups → `utils.network.securityGroup.list.invalidate()` + `utils.network.securityGroup.getById.invalidate()`
- rules → `utils.network.securityGroup.getById.invalidate({ project_id, securityGroupId })` + `utils.network.securityGroup.list.invalidate()` (the list payload embeds `security_group_rules`)
- policies → `utils.network.rbacPolicy.list.invalidate({ project_id, securityGroupId })` + `utils.network.securityGroup.getById.invalidate({ project_id, securityGroupId })`

Only invalidate when `result.successful.length > 0`.

## Potential Problems & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| **Conflict with the large staged diff on this branch.** Steps 6, 8, 10, 11, 12, 14, 15 all land in files that are already modified-and-staged (see "Branch-state overlap" below). | **High** | Write against the working tree, not `origin/main`. Re-read each target file immediately before editing. Do all client edits *after* the server steps so the server work can't be lost to a rebase of the UI half. |
| `[SECURITY]` A tampered client sends an ID containing `../` or `?`, reaching a Neutron path. | **High** | D2: `validateAndEncodeResourceId` over **every** ID up-front, before the first DELETE; whole call rejects with `BAD_REQUEST`. Covered by a router test asserting zero `del` calls. |
| `[SECURITY]` Bulk procedure could bypass project scoping. | **High** | Use `projectScopedProcedure` + `projectScopedInputSchema.extend(...)` — identical to the single-item procedures. Never accept a `project_id` per item. |
| `[PERF]` A large fan-out hammers Neutron with concurrent DELETEs — heavier than the Glance equivalent, since deleting a security group cascades to its rules and checks port bindings. | Medium | Cap input at `MAX_BULK_DELETE_ITEMS = 100` and run with `chunkSize: 5`, no inter-chunk delay (resolved decision 3). Deliberately unlike Images, whose unbounded fully-parallel fan-out is better read as a latent problem there than as a model to copy. |
| The server cap is reachable from the UI: the security groups list is **not paginated**, so select-all in a large project can exceed 100 and would reject the whole mutation with `BAD_REQUEST`. | Medium | Step 9a: a client-side batching helper splits the selection into ≤100-ID calls and merges the results, so the cap is invisible to the user. Its merge must be all-or-nothing per *item*, not per call — a rejected batch contributes every ID in it to `failed`, so one bad batch cannot make earlier successful batches look failed. |
| `[CAREFUL]` Bulk rules/RBAC modals have **no** typed-word gate while the *single*-item `DeleteRuleDialog` and `DeleteRBACPolicyDialog` **do** — bulk is a weaker gate than single. | Medium | This is the settled requirement; call it out explicitly in the PR/changeset description so a reviewer doesn't read it as an oversight. Compensate with a full itemised list of affected rows in the bulk modal body. Optional follow-up: drop the typed gate from the single dialogs for consistency. |
| Selection wiped by the list's `placeholderData: (prev) => prev` refetch on every URL change. | Medium | D8: derive `validSelectedIds` per render; never prune via effect/`setState`. |
| Stale-row deletion: user selects, someone else deletes the group, bulk returns 404 for that item. | Low (resolved) | Resolved decision 2: 404 is treated as success in the bulk path, so the row simply disappears and is not reported as a failure. See D3. |
| Rules have no name — the modal's "rules to delete" list could be unidentifiable. | Medium | Extract `formatPortRange` from `SecurityGroupRulesTable` into `-details/ruleFormatting.ts` and add `formatRuleLabel(rule)` (`direction · ethertype · protocol · range`), used by both table and modal so they can't drift. |
| `columnCount` / `colSpan` drift once a select column is added — the empty/loading/error `Status` row spans the wrong width. | Low | Every one of the three tables already derives `colSpan` from a single `columnCount` (RBAC's is a module const `RBAC_COLUMN_COUNT = 3` → must become a computed value). Assert in tests. |
| `[BREAKING]` Public-API surface change. | Low | None: nothing here is exported from `packages/aurora/src/client/index.ts` or the server public entry. The three new procedures are additive; the existing `deleteById`/`delete` procedures are untouched, so no consumer breaks. Changeset severity `minor` (new tRPC procedures) — see Step 18. |
| i18n: `plural()` labels and en/de catalogs drift. | Low | Use `i18n._(plural(n, { one: …, other: … }))` for PopupMenu labels (they take a string, not a node) and `<Plural>`/`<Trans>` inside modal bodies. Run `pnpm check-i18n`. |

## Prerequisites

- [ ] Working tree is on `kiryl-security-groups-go-live` with the described staged changes present (verify with `git status`); the plan assumes the working-tree state, **not** `origin/main`.
- [ ] `pnpm install` done; baseline green: `pnpm test --filter @cobaltcore-dev/aurora`, `pnpm typecheck --filter @cobaltcore-dev/aurora`, `pnpm lint --filter @cobaltcore-dev/aurora`.
- [ ] Read the **Decisions resolved after review** table above before starting — it revises fixed requirement #3 (type-to-confirm now applies to all three bulk modals) and adds Step 9a.
- [ ] Delivery is settled: the work stays as uncommitted changes in the working tree; nothing is committed or pushed.

### Branch-state overlap (read this before starting)

These plan steps edit files that are **already modified and staged** on this branch, so they risk conflicting with, or partly redoing, that in-flight work:

| Step | File already in the staged diff | Nature of overlap |
| --- | --- | --- |
| 6 | `SecurityGroupListContainer.tsx`, `$securityGroupId/index.tsx` | Both already touched; the ownership-helper refactor replaces inline `isReadOnly` expressions the staged diff itself introduced/moved. |
| 8, 10 | `SecurityGroupsList.tsx` (274 changed lines), `SecurityGroupListContainer.tsx`, `SecurityGroupTableRow.tsx` | Heaviest overlap. `hasAnyBulkAction={false}` and the `onSelect={() => {}}` no-op are both staged lines being replaced. |
| 11, 12, 14 | `SecurityGroupRulesTable.tsx` (291 changed lines), `useSecurityGroupDetails.ts`, `SecurityGroupDetailsView.tsx` | The Zone 1/Zone 2 layout being extended was just rewritten by the staged diff. |
| 15 | `SecurityGroupRBACPolicies.tsx` (181 changed lines), `RBACPolicyRow.tsx` | Same. |
| Tests | `SecurityGroupListContainer.test.tsx`, `SecurityGroupTableRow.test.tsx`, `SecurityGroupRulesTable.test.tsx`, `SecurityGroupRBACPolicies.test.tsx`, `SecurityGroupDetailsView.test.tsx`, `useSecurityGroupDetails.test.ts` | All staged; new bulk cases append to files in flux. |
| Server | `securityGroupRouter.ts`, `securityGroupRuleRouter.ts`, `rbacPolicyRouter.ts`, `types/securityGroup.ts`, `helpers/securityGroupHelpers.ts` | New procedures/schemas append to staged files. Low conflict risk (additive, different regions). |
| 18 | `.changeset/thirty-actors-relax.md` | Existing changeset — see Step 18 for the extend-vs-new decision. |

Steps 1-5 (server helper + schemas + procedures) touch **new files** or append to stable regions and are the safest place to start.

---

## Implementation Steps

### Step 1: Create the Network-local bulk-operation helper

**Files to create:**
- `packages/aurora/src/server/Network/helpers/bulkOperations.ts`
- `packages/aurora/src/server/Network/helpers/bulkOperations.test.ts`

**What to do:**
1. Export `const MAX_BULK_DELETE_ITEMS = 100`.
2. Export `formatBulkItemError(error: unknown, resourceLabel: string, operation: string): string` — mirror `formatBulkOperationError` (`Compute/helpers/imageHelpers.ts:573`) but parameterize the resource noun: `TRPCError` → `error.message` verbatim; `Error` → `` `Failed to ${operation} ${resourceLabel}: ${error.message}` ``; `string` → same with the string; else `` `Failed to ${operation} ${resourceLabel}: Unknown error` ``.
3. Export `validateBulkIds(ids: string[], operation: string): void` — throw `TRPCError({ code: "BAD_REQUEST", message: `Cannot ${operation} - at least one ID is required` })` when empty; throw `BAD_REQUEST` when `ids.length > MAX_BULK_DELETE_ITEMS`.
4. Export `chunkArray<T>(array: T[], size: number): T[][]` (copy of the Compute one — do **not** import across domain folders).
5. Export `processBulkDelete<T extends { id: string }>(items: T[], processor: (item: T) => Promise<void>, options: { resourceLabel: string; operation?: string; chunkSize?: number; delayBetweenChunks?: number }): Promise<BulkDeleteResult>`. Same control flow as `processBulkOperation` (chunked branch + all-parallel branch, `Promise.allSettled`), but push failures as **`{ id, error }`**, not `{ imageId, error }`.
6. Add a JSDoc header stating this is the Network-local twin of `Compute/helpers/imageHelpers.ts`'s `processBulkOperation`, why it is duplicated (field name + resource-agnostic messages), and that it should be promoted to `server/helpers/` if a third domain needs it.

**Expected outcome:** a reusable, resource-agnostic bulk-delete engine inside `Network`.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test -- src/server/Network/helpers/bulkOperations.test.ts`. Cover: all succeed; some fail (order-independent `successful`/`failed` contents); all fail; `TRPCError` message passthrough; non-Error thrown value; chunk boundary (7 items, `chunkSize: 3` → processor called 7 times); empty array throws; over-cap throws.

---

### Step 2: Add the shared result schema and the three bulk input schemas

**Files to modify:**
- `packages/aurora/src/server/Network/types/index.ts` — add `bulkDeleteResultSchema` + `export type BulkDeleteResult`
- `packages/aurora/src/server/Network/types/securityGroup.ts` — add two input schemas + inferred types
- `packages/aurora/src/server/Network/types/rbacPolicy.ts` — add one input schema + inferred type

**What to do:**
1. In `Network/types/index.ts` (already the home of shared Network types like `SortDirSchema`):
   ```ts
   export const bulkDeleteResultSchema = z.object({
     successful: z.array(z.string()),
     failed: z.array(z.object({ id: z.string(), error: z.string() })),
   })
   export type BulkDeleteResult = z.infer<typeof bulkDeleteResultSchema>
   ```
   Comment that this is the Network counterpart of `Compute/types/image.ts`'s `bulkOperationResultSchema`, keyed `id` rather than `imageId`.
2. In `types/securityGroup.ts`, after `deleteSecurityGroupInputSchema` / `deleteSecurityGroupRuleInputSchema`:
   ```ts
   export const deleteSecurityGroupsBulkInputSchema = projectScopedInputSchema.extend({
     securityGroupIds: z.array(z.string().min(1)).min(1).max(MAX_BULK_DELETE_ITEMS),
   })
   export const deleteSecurityGroupRulesBulkInputSchema = projectScopedInputSchema.extend({
     ruleIds: z.array(z.string().min(1)).min(1).max(MAX_BULK_DELETE_ITEMS),
   })
   ```
   plus `DeleteSecurityGroupsBulkInput` / `DeleteSecurityGroupRulesBulkInput` type exports next to the existing ones (~line 137).
3. In `types/rbacPolicy.ts`: `deleteRBACPoliciesBulkInputSchema` with `policyIds`, plus `DeleteRBACPoliciesBulkInput`.
4. Do **not** use `.uuid()` (the existing single-item schemas use plain `z.string()`; path safety comes from `validateAndEncodeResourceId`, not UUID shape).

**Expected outcome:** typed, capped inputs and one result shape for all three procedures.

**Verification:** `pnpm typecheck --filter @cobaltcore-dev/aurora`. Add parse cases to `Network/types/securityGroup.test.ts` and `rbacPolicy.test.ts`: valid array; empty array rejected; 101 items rejected; empty-string element rejected.

---

### Step 3: Add `securityGroup.deleteBulk`

**Files to modify:** `packages/aurora/src/server/Network/routers/securityGroupRouter.ts`, `securityGroupRouter.test.ts`

**What to do:**
1. Add `deleteBulk: projectScopedProcedure.input(deleteSecurityGroupsBulkInputSchema).mutation(async ({ input, ctx }): Promise<BulkDeleteResult> => …)`, placed directly after `deleteById`. Leave `deleteById` untouched.
2. Handler body, inside `withErrorHandling(async () => { … }, "bulk delete security groups")`:
   - `const network = getNetworkService(ctx)` (throws whole-call if the service is missing).
   - `validateBulkIds(input.securityGroupIds, "delete security groups")`.
   - **Up-front encode pass** (D2): `const items = input.securityGroupIds.map((id) => ({ id, encodedId: validateAndEncodeResourceId(id, "Security group") }))` — any rejection propagates out of the whole call as `BAD_REQUEST`.
   - `return processBulkDelete(items, async (item) => { const response = await network.del(`${SECURITY_GROUPS_BASE_URL}/${item.encodedId}`); if (!response?.ok) throw SecurityGroupErrorHandlers.delete(response, item.id) }, { resourceLabel: "security group", operation: "delete", chunkSize: 5 })`.
   - **404 = success** (resolved decision 2): `if (response?.status === 404) return` *before* the `!ok` check, with a comment naming `ec2CredentialRouter.delete` as the precedent and noting that the single-item `deleteById` deliberately still reports `NOT_FOUND`.
3. Extend the router's top-of-file JSDoc list with `deleteBulk`.
4. Update the type import list (`BulkDeleteResult` from `../types/index`).

**Expected outcome:** `network.securityGroup.deleteBulk` returns `{ successful, failed }` and never rejects on individual-item failure.

**Verification:** new `describe("deleteBulk")` in `securityGroupRouter.test.ts`, following the existing `createMockContext`/`createCaller` harness (lines 1-70) and the shape of `imageRouter.test.ts`'s `describe("deleteImages")` (lines 1193-1285):
- all three delete → `successful` equals input order-insensitively, `del` called 3× with the right paths;
- middle one returns `{ ok: false, status: 409 }` → `successful` has 2, `failed[0].id` is the middle ID, `failed[0].error` contains "in use by one or more ports";
- one `del` rejects with `new Error("Network error")` → that item in `failed` with the message included;
- empty array → rejects;
- 101 items → rejects;
- `securityGroupIds: ["../../etc/passwd"]` → rejects **and** `mockNetwork.del` was never called (D2 assertion);
- all fail → `successful: []`, `failed.length === n`;
- no network service → rejects.

---

### Step 4: Add `securityGroupRule.deleteBulk`

**Files to modify:** `packages/aurora/src/server/Network/routers/securityGroupRuleRouter.ts`
**Files to create:** `packages/aurora/src/server/Network/routers/securityGroupRuleRouter.test.ts` (**none exists today** — the plan adds the first one)

**What to do:**
1. Add `deleteBulk` after `delete`, same structure as Step 3 with `SECURITY_GROUP_RULES_BASE_URL`, `validateAndEncodeResourceId(id, "Security group rule")`, `SecurityGroupRuleErrorHandlers.delete(response, item.id)`, `resourceLabel: "security group rule"`.
2. Create the test file by copying the `createMockContext`/`createCaller` scaffolding from `securityGroupRouter.test.ts` and narrowing it to `network.del` on `v2.0/security-group-rules/*`. Cover the same eight cases as Step 3, plus a 412 case asserting the message contains "precondition failed".

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test -- src/server/Network/routers/securityGroupRuleRouter.test.ts`.

---

### Step 5: Add `rbacPolicy.deleteBulk`

**Files to modify:** `packages/aurora/src/server/Network/routers/rbacPolicyRouter.ts`, `rbacPolicyRouter.test.ts`

**What to do:** identical pattern with `RBAC_POLICIES_BASE_URL`, `validateAndEncodeResourceId(id, "RBAC policy")`, `RBACPolicyErrorHandlers.delete(response, item.id)`, `resourceLabel: "RBAC policy"`, `operation: "delete"`. Extend the router JSDoc. Add a `describe("deleteBulk")` block to the existing test file mirroring Step 3's cases (409 message: "in use").

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test -- src/server/Network/routers/rbacPolicyRouter.test.ts`.

**Checkpoint:** after Step 5 run the full server test subset plus `pnpm typecheck --filter @cobaltcore-dev/aurora`. All server work is now done and independent of the in-flight client diff.

---

### Step 6: Extract the shared ownership predicate

**Files to create:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/ownership.ts` (+ `ownership.test.ts`)
**Files to modify:** `-components/SecurityGroupListContainer.tsx`, `$securityGroupId/index.tsx`

**What to do:**
1. `export const isSharedFromAnotherProject = (sg: Pick<SecurityGroup, "project_id">, currentProjectId?: string): boolean => Boolean(currentProjectId && sg.project_id && sg.project_id !== currentProjectId)` — preserve the existing "only when the group has an explicit project owner" semantics verbatim. Sits next to `filterConfig.ts`/`urlHelpers.ts`, which set the precedent for plain `.ts` modules at this route level.
2. Replace the inline expression at `SecurityGroupListContainer.tsx:144` and the `isReadOnly` computation in `$securityGroupId/index.tsx` with calls to it.
3. Test: same project → false; different project → true; `project_id` null/undefined → false; `currentProjectId` undefined → false.

**Expected outcome:** one definition, ready for the modal split in Step 9.

**Verification:** existing `SecurityGroupListContainer.test.tsx` and the detail-route tests still pass unchanged (pure refactor).

---

### Step 7: Add the three bulk toast builders

**Files to modify:** `-components/SecurityGroupToastNotifications.tsx`, `SecurityGroupToastNotifications.test.tsx`

**What to do:**
1. Import `NotificationSeverity` alongside `NotificationOptions`, and `Plural` from `@lingui/react/macro`, and `Stack` from Juno (matching `ContainerToastNotifications.tsx`).
2. Add `type BulkToastReturnType = { message: ReactNode; severity: NotificationSeverity } & NotificationOptions`.
3. Add three builders with the identical signature `(successCount: number, failures: { id: string; error: string }[]) => BulkToastReturnType`:
   - `getSecurityGroupsBulkDeleteToast` — titles: `Security Groups Deleted` / `Security Groups Partially Deleted` / `Failed to Delete Security Groups`
   - `getSecurityGroupRulesBulkDeleteToast` — `Rules Deleted` / `Rules Partially Deleted` / `Failed to Delete Rules`
   - `getRBACPoliciesBulkDeleteToast` — `Access Revoked` / `Access Partially Revoked` / `Failed to Revoke Access`
4. In each: derive `severity` in the same expression block as the title (`isPartial ? "warning" : hasErrors ? "error" : "success"`) with the same "so the two never drift" comment as the Swift builder. Description = a vertical `Stack` with a `<Plural>` success line and, when there are failures, up to 5 `id: error` lines plus a `… and N more` line.
5. Add a comment noting this module now mixes two shapes on purpose: single-item builders return `{ message, … }` (caller picks severity), bulk builders also return `severity`.
6. Tests: for each builder assert `severity` and title for the three outcomes, and that the failure list truncates at 5.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test -- src/client/routes/_auth/projects/\$projectId/network/securitygroups/-components/SecurityGroupToastNotifications.test.tsx`

---

### Step 8: Wire selection into the list (adopt the dead scaffolding)

**Files to modify:** `-components/SecurityGroupsList.tsx`, `-components/SecurityGroupListContainer.tsx`

**What to do:**
1. In `SecurityGroupsList.tsx`:
   - `const [selectedGroupIds, setSelectedGroupIds] = useState<string[]>([])`
   - `const displayedIds = useMemo(() => new Set(securityGroups.map((sg) => sg.id)), [securityGroups])`
   - `const validSelectedIds = selectedGroupIds.filter((id) => displayedIds.has(id))` — derived, with the D8 comment explaining why no effect prunes it.
   - `const hasAnyBulkAction = permissions.canDelete` and change line 362 from `hasAnyBulkAction={false}` to `hasAnyBulkAction={hasAnyBulkAction}`.
   - `const handleToggleSelect = (sg: SecurityGroup) => setSelectedGroupIds((prev) => prev.includes(sg.id) ? prev.filter((id) => id !== sg.id) : [...prev, sg.id])`
   - `const handleToggleSelectAll = () => { const ids = securityGroups.map((sg) => sg.id); const allSelected = ids.length > 0 && ids.every((id) => validSelectedIds.includes(id)); setSelectedGroupIds(allSelected ? validSelectedIds.filter((id) => !ids.includes(id)) : [...new Set([...validSelectedIds, ...ids])]) }` (Swift's `handleToggleSelectAll`, scoped to displayed rows).
   - Pass `selectedGroupIds={validSelectedIds}` and `onSelectSecurityGroup={handleToggleSelect}` to `SecurityGroupListContainer`.
2. In `SecurityGroupListContainer.tsx`: add props `selectedGroupIds?: string[]` and `onSelectSecurityGroup?: (sg: SecurityGroup) => void`; in the row map replace `isSelected={false}` with `isSelected={(selectedGroupIds ?? []).includes(sg.id)}` and `onSelect={() => {}}` with `onSelect={onSelectSecurityGroup}`.
3. `SecurityGroupTableRow.tsx` needs **no change** — its `Checkbox` (lines 63-67) already does the right thing.

**Expected outcome:** checkboxes appear (when `canDelete`) and actually toggle.

**Verification:** extend `SecurityGroupListContainer.test.tsx` — with `hasAnyBulkAction` true a checkbox renders per row and `onSelectSecurityGroup` fires with the group; with it false no checkbox and `columnCount` stays 5. Extend `SecurityGroupTableRow.test.tsx` to assert the checkbox click does not trigger row navigation (the `stopPropagation` cell).

---

### Step 9: Create `BulkDeleteSecurityGroupsModal` (type-to-confirm)

**Files to create:** `-components/-modals/BulkDeleteSecurityGroupsModal.tsx` (+ `.test.tsx`)

**What to do:**
1. Base the structure on `compute/images/-components/DeleteImagesModal.tsx` (TanStack Form + Zod + `useModalTracking`), but **drop its unreachable Step-B results view** — outcomes are reported by the toast (Step 10).
2. Props: `{ isOpen: boolean; deletableGroups: SecurityGroup[]; undeletableGroups: SecurityGroup[]; isLoading: boolean; onClose: () => void; onDelete: (ids: string[]) => void }` — objects in, IDs out. Note that `DeleteImagesModal` has since been changed on disk to exactly this shape (it now takes `Array<GlanceImage>` rather than `Array<string>`, renders `image.name || t\`Unnamed\`` with the id in a muted span beside it, and puts the protected block *first*); mirror that current version, not the string-array one described in the original brief.
3. Type-to-confirm gate, following `EmptyContainersModal.tsx:16-20`:
   ```ts
   // The literal word the user must type. isConfirmed compares against this constant,
   // NOT the translated label, so a mistranslation can never weaken the gate.
   const CONFIRM_WORD = "delete"
   ```
   `z.string().transform((v) => v.trim()).refine((v) => v === CONFIRM_WORD, { message: t`Type "${CONFIRM_WORD}" to confirm` })`; `const canDelete = useStore(form.store, (s) => s.isSubmitting || s.values.confirm.trim() !== CONFIRM_WORD)`.
4. `useModalTracking({ isOpen, actionPrefix: "network.securitygroups.bulk_delete" })`.
5. Body:
   - `<Trans>The selected security groups will be permanently deleted. This action cannot be undone.</Trans>`
   - **"Groups to delete"** section: up to `MAX_VISIBLE = 20` `name || id` entries + `… and {n} more`.
   - **"Cannot be deleted"** section (only when `undeletableGroups.length > 0`), styled like `DeleteImagesModal`'s protected block (`bg-theme-warning/10`, yellow border), each entry `name || id` with the reason `<Trans>Shared from another project</Trans>`.
   - A closing note covering the undetectable case: `<Trans>A group can also fail to delete if it is in use by a port or is your project's default security group.</Trans>` (D10).
6. `title={<Plural value={deletableGroups.length} one="Delete # Security Group" other="Delete # Security Groups" />}`, `confirmButtonVariant="primary-danger"`, `confirmButtonLabel` = `isLoading ? t`Deleting...` : plural(...)`, `disableConfirmButton={canDelete || isLoading || deletableGroups.length === 0}`, `disableCancelButton`/`disableCloseButton` while loading.
7. `onSubmit` → `markSubmitted(); onDelete(deletableGroups.map((g) => g.id))` — **only the deletable IDs**.

**Verification:** new test modelled on `EmptyContainersModal.test.tsx` (same imports: `I18nProvider` + `PortalProvider`, `vi.mock` for `useProjectId`, a `renderModal` helper, `describe` blocks for Visibility / Content / Truncation / Type-to-confirm gating / Confirmation / Cancel-close). Assert: confirm disabled until exactly `delete` typed; `onDelete` receives **only** deletable IDs; the undeletable section renders with its reason; truncation at 20; nothing renders when `isOpen` is false; confirm disabled when `deletableGroups` is empty.

---

### Step 9a: Client-side batching helper (cap-aware bulk dispatch)

**Files to create:** `packages/aurora/src/client/utils/bulkDispatch.ts` (+ `bulkDispatch.test.ts`)

Added by resolved decision 3. The server caps a call at 100 IDs, but the security groups list is not paginated, so select-all can hand the UI more than that. Rather than disabling the action or asking the user to select less, the client splits and merges.

**What to do:**
1. `export const BULK_DISPATCH_BATCH_SIZE = 100` — keep it equal to the server's `MAX_BULK_DELETE_ITEMS` and add a comment on each pointing at the other, since a client value larger than the server's would produce a wholesale `BAD_REQUEST`.
2. ```ts
   export type BulkResult = { successful: string[]; failed: { id: string; error: string }[] }

   export async function dispatchInBatches(
     ids: string[],
     call: (batch: string[]) => Promise<BulkResult>,
     batchSize = BULK_DISPATCH_BATCH_SIZE
   ): Promise<BulkResult>
   ```
   Run the batches **sequentially** (not `Promise.all`) so the per-batch server-side concurrency guard is not multiplied by the number of batches. Merge by concatenation.
3. Per-batch rejection must not lose the other batches: wrap each `call` in `try/catch` and, on rejection, push **every ID of that batch** into `failed` with the rejection message, then continue with the remaining batches. This is what makes the helper safe to use for the whole-call `catch` the surfaces currently need — see Step 10, whose `catch` block collapses into `dispatchInBatches`'s own error handling.
4. Live in `client/utils/` (next to `useListWithFiltering.ts`, `buildFilterParams.ts`) rather than under the security-groups route, because all three surfaces use it and a future paginated list elsewhere will too.

**Expected outcome:** each surface calls `dispatchInBatches(ids, (batch) => mutateAsync({ project_id, <idsField>: batch }))` and gets one merged `{ successful, failed }` regardless of selection size.

**Verification:** `bulkDispatch.test.ts` — 250 IDs → 3 sequential calls of 100/100/50, batches in order; a middle batch rejecting → its 100 IDs in `failed`, the other 150 in `successful`, and the third batch still attempted; a batch returning partial failures → merged correctly; empty input → no call, empty result; exactly 100 → one call.

---

### Step 10: Add Zone 3 + the bulk mutation to the list

**Files to modify:** `-components/SecurityGroupsList.tsx`, `-components/SecurityGroupsList.test.tsx`

**What to do:**
1. Imports: `Checkbox`, `PopupMenu`, `PopupMenuToggle`, `PopupMenuItem`, `PopupMenuOptions` from Juno; `plural` from `@lingui/core/macro`; `i18n` from `@lingui/core`; the new modal; `getSecurityGroupsBulkDeleteToast`.
2. Derive the split with the Step-6 helper:
   ```ts
   const selectedGroups = securityGroups.filter((sg) => validSelectedIds.includes(sg.id))
   const deletableGroups = selectedGroups.filter((sg) => !isSharedFromAnotherProject(sg, projectId))
   const undeletableGroups = selectedGroups.filter((sg) => isSharedFromAnotherProject(sg, projectId))
   ```
3. Insert Zone 3 **between** the existing `DataGridToolbar` (ends line 346) and `<SecurityGroupListContainer …>`:
   ```tsx
   {permissions.canDelete && (
     <DataGridToolbar>
       <Stack gap="2" alignment="center">
         <Checkbox
           checked={securityGroups.length > 0 && securityGroups.every((sg) => validSelectedIds.includes(sg.id))}
           indeterminate={validSelectedIds.length > 0 && !securityGroups.every((sg) => validSelectedIds.includes(sg.id))}
           onChange={handleToggleSelectAll}
           disabled={securityGroups.length === 0}
           aria-label={t`Select all security groups`}
           data-testid="select-all-security-groups"
         />
         <PopupMenu className="flex items-center">
           <PopupMenuToggle as="div">
             <Button disabled={validSelectedIds.length === 0} size="small" icon="moreVert" label={t`Actions`} />
           </PopupMenuToggle>
           {validSelectedIds.length > 0 && (
             <PopupMenuOptions>
               <PopupMenuItem
                 label={i18n._(plural(validSelectedIds.length, { one: "Delete # Selected Group", other: "Delete # Selected Groups" }))}
                 onClick={() => setBulkDeleteModalOpen(true)}
                 data-testid="bulk-delete-groups-action"
               />
             </PopupMenuOptions>
           )}
         </PopupMenu>
       </Stack>
     </DataGridToolbar>
   )}
   ```
4. Add `const [bulkDeleteModalOpen, setBulkDeleteModalOpen] = useState(false)` and the mutation:
   ```ts
   const bulkDeleteMutation = trpcReact.network.securityGroup.deleteBulk.useMutation()
   ```
   and the handler:
   ```ts
   const handleBulkDelete = async (ids: string[]) => {
     setBulkDeleteModalOpen(false)
     try {
       const result = await bulkDeleteMutation.mutateAsync({ project_id: projectId, securityGroupIds: ids })
       if (result.successful.length > 0) {
         utils.network.securityGroup.list.invalidate()
         utils.network.securityGroup.getById.invalidate()
       }
       // Keep only the failures selected so the next action lands on exactly the rows that need attention.
       setSelectedGroupIds(result.failed.map((f) => f.id))
       const { message, severity, ...options } = getSecurityGroupsBulkDeleteToast(result.successful.length, result.failed)
       toast[severity](message, options)
     } catch (error) {
       const failures = ids.map((id) => ({ id, error: (error as { message?: string })?.message ?? "" }))
       const { message, severity, ...options } = getSecurityGroupsBulkDeleteToast(0, failures)
       toast[severity](message, options)
     }
   }
   ```
   Note the whole-call `catch` funnels through the same builder with `successCount: 0` (D3/D4), and selection is left intact so a retry is possible.
5. Render the modal at the bottom next to `CreateSecurityGroupModal`, with `deletableGroups`, `undeletableGroups`, `isLoading={bulkDeleteMutation.isPending}`, `onClose={() => setBulkDeleteModalOpen(false)}`, `onDelete={handleBulkDelete}`.

**Expected outcome:** end-to-end bulk delete on the list with success/partial/error toasts and correct post-delete selection.

**Verification:** extend `SecurityGroupsList.test.tsx` (156 lines, already mocks `trpcReact`) — add `deleteBulk.useMutation`. Cases: Zone 3 absent when `canDelete` false; select-all checks every row; Actions button disabled with no selection; item label pluralizes; partial result leaves only the failed row selected; full success clears selection; a rejected `mutateAsync` shows an error toast and keeps selection.

---

### Step 11: Extract rule formatting

**Files to create:** `$securityGroupId/-components/-details/ruleFormatting.ts` (+ `ruleFormatting.test.ts`)
**Files to modify:** `-details/SecurityGroupRulesTable.tsx`

**What to do:**
1. Move `ICMP_PROTOCOLS`, `isIcmpProtocol` and `formatPortRange` out of `SecurityGroupRulesTable.tsx` (lines 27-33, 109-136) into the new module. `formatPortRange` currently uses `t` from `useLingui`, so change its signature to `formatPortRange(rule: SecurityGroupRule, t: ReturnType<typeof useLingui>["t"]): string` and pass `t` from the caller — do **not** import `i18n` directly (that would freeze the locale). Preserve the existing behaviour exactly (`type without code`, loose `== null` checks) — the in-flight changeset lists three bug fixes here that must not regress. [CAREFUL]
2. Add `formatRuleLabel(rule: SecurityGroupRule, t): string` → `` `${rule.direction ?? "—"} · ${rule.ethertype ?? "—"} · ${rule.protocol ?? t`any`} · ${formatPortRange(rule, t)}` ``, plus `rule.description` in parentheses when present.
3. Update `SecurityGroupRulesTable.tsx` to import both.
4. Tests: port the ICMP/port-range cases already in `SecurityGroupRulesTable.test.tsx` (staged diff added 74 lines there, several about `Range`) into `ruleFormatting.test.ts` and keep the table test asserting the rendered cell.

**Verification:** `SecurityGroupRulesTable.test.tsx` passes unchanged for the Range column; new unit test green.

---

### Step 12: Add selection + Zone 3 + select column to the Rules tab

**Files to modify:** `-details/SecurityGroupRulesTable.tsx`

**What to do:**
1. New props: `onBulkDeleteRules?: (ruleIds: string[]) => Promise<{ successful: string[]; failed: { id: string; error: string }[] }>` and `isBulkDeletingRules?: boolean`.
2. `const [selectedRuleIds, setSelectedRuleIds] = useState<string[]>([])`; derive `displayedRuleIds` from the `rules` prop (already filtered+sorted by `useSecurityGroupDetails`) and `validSelectedRuleIds`. Add a comment stating that selection is intentionally component-local so that a tab switch (which unmounts this component) discards it (D7).
3. `const hasAnyBulkAction = canDeleteRule && !!onBulkDeleteRules`; `const columnCount = canDeleteRule ? 7 : 5` — 5 data columns + actions column (existing, `canDeleteRule`) + select column (new, `hasAnyBulkAction`). Compute it as `5 + (canDeleteRule ? 1 : 0) + (hasAnyBulkAction ? 1 : 0)` so the two gates stay independent. Add `minContentColumns={[columnCount - 1]}` only if it is already consistent with the other tables — currently the rules `DataGrid` has none, so **leave it out** (do not introduce the inconsistency #1256 created in storage).
4. Header row: prepend `{hasAnyBulkAction && <DataGridHeadCell />}` before `Direction`.
5. Row: prepend `{hasAnyBulkAction && (<DataGridCell onClick={(e) => e.stopPropagation()}><Checkbox checked={validSelectedRuleIds.includes(rule.id)} onChange={() => handleToggleSelectRule(rule.id)} /></DataGridCell>)}`.
6. Insert a Zone 3 `DataGridToolbar` after the Zone 2 block (ends line 229) and before the `DataGrid`, gated on `hasAnyBulkAction`, with the same select-all `Checkbox` (scoped to the displayed `rules`) + `moreVert` `PopupMenu` as Step 10, item label `plural(n, { one: "Delete # Selected Rule", other: "Delete # Selected Rules" })`, `data-testid="bulk-delete-rules-action"`.
7. Add `const [bulkDeleteModalOpen, setBulkDeleteModalOpen] = useState(false)`; on confirm call `onBulkDeleteRules(validSelectedRuleIds)` and set selection to `result.failed.map((f) => f.id)`.

**Verification:** extend `SecurityGroupRulesTable.test.tsx`: no select column / no Zone 3 when `canDeleteRule` false or `onBulkDeleteRules` absent; `colSpan` on the empty-state row equals the new `columnCount` in both modes; select-all covers only the rows currently passed in `rules`; toggling one row's checkbox does not affect others.

---

### Step 13: Create `BulkDeleteRulesModal` (type-to-confirm)

**Files to create:** `$securityGroupId/-modals/BulkDeleteRulesModal.tsx` (+ `.test.tsx`)

> **Revised by resolved decision 5.** The original draft specced a plain `primary-danger` confirm with no typed word, based on Ceph's `DeleteCorsRulesModal`. That is superseded: the existing single-rule `DeleteRuleDialog` requires typing `delete`, so a bulk modal without a gate would make deleting many rules easier than deleting one.

**What to do:**
1. Base on the same TanStack Form + Zod + `CONFIRM_WORD` structure as Step 9 (`DeleteRuleDialog` in the same folder is the closest in-domain example and already uses `delete`), plus the itemised list from Ceph's `DeleteCorsRulesModal`. Keep `useModalTracking({ isOpen, actionPrefix: "network.securitygroup.rules.bulk_delete" })`. `CONFIRM_WORD = "delete"`, compared against the untranslated literal exactly as in Step 9.
2. Props: `{ isOpen: boolean; rules: SecurityGroupRule[]; isLoading: boolean; onClose: () => void; onConfirm: () => void }` (parent already holds the selected IDs).
3. Body: `<Trans>Are you sure you want to delete <Plural value={n} one="# rule" other="# rules"/> from this security group?</Trans>`, then a `Rules to delete:` block listing `formatRuleLabel(rule, t)` for up to `MAX_VISIBLE_RULES = 5` (Ceph's cap) + `… and {n} more`, then `<Trans>This action cannot be undone.</Trans>`.
4. Title `<Plural value={n} one="Delete Rule" other="Delete Rules" />`, `size="small"`, confirm label `isLoading ? t`Deleting...` : plural(...)`, `disableConfirmButton={canDelete || isLoading}`, disable cancel/close while loading. The `Type "delete" to confirm` `TextInput` goes below the list, matching `DeleteRuleDialog`'s layout.
5. Because Neutron rules are immutable, there is no "cannot be deleted" split here — every visible rule is deletable. State that in a comment so the difference from the list modal is intentional and documented.

**Verification:** new test (no `DeleteCorsRulesModal.test.tsx` exists to copy from — **the original brief's reference was inaccurate**; use `Ceph/Objects/DeleteObjectsModal.test.tsx` or `EmptyContainersModal.test.tsx` as the harness template instead). Assert: confirm stays disabled until exactly `delete` is typed (reject `Delete` and `del`); title/labels pluralize at n=1 and n=3; the list truncates at 5; `onConfirm` fires once on confirm; buttons disabled while `isLoading`; renders nothing when closed.

---

### Step 14: Add the rules bulk mutation to `useSecurityGroupDetails` and wire it through

**Files to modify:** `$securityGroupId/-hooks/useSecurityGroupDetails.ts`, `-components/SecurityGroupDetailsView.tsx`, `-hooks/useSecurityGroupDetails.test.ts`, `-components/SecurityGroupDetailsView.test.tsx`

**What to do:**
1. In the hook, next to `deleteRuleMutation`:
   ```ts
   const bulkDeleteRulesMutation = trpcReact.network.securityGroupRule.deleteBulk.useMutation()

   const handleBulkDeleteRules = async (ruleIds: string[]) => {
     try {
       const result = await bulkDeleteRulesMutation.mutateAsync({ project_id: projectId, ruleIds })
       if (result.successful.length > 0) {
         utils.network.securityGroup.getById.invalidate({ project_id: projectId, securityGroupId })
         utils.network.securityGroup.list.invalidate()
       }
       const { message, severity, ...options } = getSecurityGroupRulesBulkDeleteToast(result.successful.length, result.failed)
       toast[severity](message, options)
       return result
     } catch (error) {
       const failures = ruleIds.map((id) => ({ id, error: (error as { message?: string })?.message ?? "" }))
       const { message, severity, ...options } = getSecurityGroupRulesBulkDeleteToast(0, failures)
       toast[severity](message, options)
       return { successful: [], failed: failures }
     }
   }
   ```
   Return `handleBulkDeleteRules` and `isBulkDeletingRules: bulkDeleteRulesMutation.isPending`. Toast dispatch lives here (consistent with every other mutation in this hook); the **result** is returned so the table can prune its own selection.
2. `SecurityGroupDetailsView.tsx`: add `onBulkDeleteRules`/`isBulkDeletingRules` props and forward them to `SecurityGroupRulesTable` (guarded by `permissions.canDeleteRule ? onBulkDeleteRules : undefined`, matching how `onCreateRule` is already guarded at line 84).
3. `$securityGroupId/index.tsx`: destructure the two new values from the hook and pass them to `SecurityGroupDetailsView`.

**Verification:** extend `useSecurityGroupDetails.test.ts` — mock `deleteBulk.useMutation`; assert invalidation happens only when `successful.length > 0`; assert the returned result is passed back; assert a rejected `mutateAsync` resolves to `{ successful: [], failed: [...] }` rather than throwing (the table must not crash). Extend `SecurityGroupDetailsView.test.tsx` for prop forwarding.

---

### Step 15: Add selection + Zone 3 + bulk mutation to the RBAC tab

**Files to modify:** `-details/SecurityGroupRBACPolicies.tsx`, `-details/RBACPolicyRow.tsx`, `SecurityGroupRBACPolicies.test.tsx`

**What to do:**
1. `RBACPolicyRow.tsx`: add props `showSelectColumn?: boolean`, `isSelected?: boolean`, `onSelect?: () => void`; prepend the same `stopPropagation` + `Checkbox` cell used by `SecurityGroupTableRow`. Keep the existing default-false props style so nothing else breaks.
2. `SecurityGroupRBACPolicies.tsx`:
   - Replace `const RBAC_COLUMN_COUNT = 3` with `const columnCount = hasAnyBulkAction ? 4 : 3` (module const → computed inside the component), where `const hasAnyBulkAction = canManageAccess`. Update **all three** `colSpan={RBAC_COLUMN_COUNT}` sites (loading/error/empty) and `<DataGrid columns={columnCount}>`.
   - Prepend `{hasAnyBulkAction && <DataGridHeadCell />}` to the header row.
   - `const [selectedPolicyIds, setSelectedPolicyIds] = useState<string[]>([])`; derive `displayedIds` from `filteredPolicies` and `validSelectedIds`. Add the same "local by design, discarded on tab switch" comment.
   - Zone 3 `DataGridToolbar` between the Zone 2 toolbar (ends line 154) and the `DataGrid`, gated on `hasAnyBulkAction`, item label `plural(n, { one: "Remove # Selected Policy", other: "Remove # Selected Policies" })`, `data-testid="bulk-delete-rbac-action"`.
   - `const bulkDeleteMutation = trpcReact.network.rbacPolicy.deleteBulk.useMutation()` and a `handleBulkDelete` identical in shape to Step 10's, using `getRBACPoliciesBulkDeleteToast` and invalidating `rbacPolicy.list({ project_id, securityGroupId })` + `securityGroup.getById({ project_id, securityGroupId })` (matching the existing single-delete at lines 63-64).
   - Pass select props into `RBACPolicyRow`.

**Verification:** extend `SecurityGroupRBACPolicies.test.tsx` (658 lines, already mocks the trpc surface — add `deleteBulk`): no select column and `columnCount === 3` when `canManageAccess` false; `colSpan` matches in loading/error/empty states in both modes; select-all is scoped to search-filtered policies (search "alpha" then select-all → only matching IDs selected); partial failure keeps only failed IDs selected.

---

### Step 16: Create `BulkDeleteRBACPoliciesModal`

**Files to create:** `$securityGroupId/-modals/BulkDeleteRBACPoliciesModal.tsx` (+ `.test.tsx`)

> **Revised by resolved decision 5**, same reasoning as Step 13 — and note the word differs here.

**What to do:** same type-to-confirm shape as Step 13, but with **`CONFIRM_WORD = "remove"`**, because the existing single-policy `DeleteRBACPolicyDialog` gates on `remove`, not `delete`. Label the input `Type "remove" to confirm`. Props `{ isOpen, policies: RBACPolicy[], isLoading, onClose, onConfirm }`. Title `<Plural value={n} one="Remove # Policy" other="Remove # Policies" />` and `t`Remove Policies`` for the confirm label, matching the row action's "Remove Policy" wording. Body lists `policy.target_tenant || policy.id` (up to 5 + `… and n more`) with an explanatory line: `<Trans>The listed projects will lose access to this security group.</Trans>` + `<Trans>This action cannot be undone.</Trans>`. `useModalTracking({ isOpen, actionPrefix: "network.securitygroup.rbac.bulk_delete" })`. Wire it into `SecurityGroupRBACPolicies.tsx`.

**Verification:** new colocated test, same assertions as Step 13 — with the gate asserted on `remove`, and an explicit case that typing `delete` does **not** enable the confirm button.

---

### Step 17: i18n catalogs

**Files to modify:** `packages/aurora/src/locales/en/messages.po`, `messages.ts`, `packages/aurora/src/locales/de/messages.po`, `messages.ts`

**What to do:**
1. Run `pnpm check-i18n` (root, turbo) or `pnpm --filter @cobaltcore-dev/aurora check-i18n` (= `lingui extract --clean && lingui compile --typescript --verbose`).
2. Translate every newly extracted German string — new titles/descriptions in `SecurityGroupToastNotifications.tsx`, the three modals, and the three plural action labels. Verify plural forms are `one`/`other` for both locales.
3. Confirm `CONFIRM_WORD = "delete"` remains an untranslated literal and that the *label* string `Type "delete" to confirm` is the only translated part (both `.po` files).
4. Re-run `pnpm check-i18n` and confirm the working tree is clean afterwards (no leftover extraction drift). Note that the four catalog files are **already in the staged diff**, so expect to merge additions rather than regenerate from scratch.

**Verification:** `pnpm check-i18n` exits 0 and produces no further diff on a second run.

---

### Step 18: Changeset

**Files to create:** a new `.changeset/<name>.md`

**What to do:**
1. **Add a new changeset rather than extending `thirty-actors-relax.md`.** Reasons: the existing one is `patch` and describes a large set of unrelated UI/consistency fixes; this work adds three new public tRPC procedures (`network.securityGroup.deleteBulk`, `network.securityGroupRule.deleteBulk`, `network.rbacPolicy.deleteBulk`), which is an **additive feature** and therefore `minor` for `@cobaltcore-dev/aurora`. Folding a `minor` feature into a `patch` prose blob is exactly the changeset/semver mismatch pattern the KB has flagged repeatedly (#1173/#1176/#1189/#1268).
2. Content: `"@cobaltcore-dev/aurora": minor`; describe the three new bulk-delete surfaces; state that each bulk modal requires typing a word (`delete` for groups and rules, `remove` for policies) so bulk is never a weaker gate than the single-item dialogs; state that undeletable rows can be selected and are split out in the modal with the reason; state that a per-item 404 is reported as success in bulk while single-item deletion still reports not-found; state that a selection over 100 is sent as several sequential calls; state that no new permission key was added; and note that the default security group cannot be detected client-side so it surfaces as a per-item failure.

**Verification:** `pnpm changeset status` (or just confirm the file parses) and that `.changeset/` now holds four `.md` files besides `README.md`/`config.json`.

---

## Testing Plan

### Unit tests (new files)
- [ ] `server/Network/helpers/bulkOperations.test.ts` — all-success, partial, all-fail, `TRPCError` passthrough, non-Error throw, chunk boundary, empty rejects, over-cap rejects.
- [ ] `server/Network/routers/securityGroupRuleRouter.test.ts` — first test for this router: `delete` (regression) + `deleteBulk` (8 cases from Step 3, plus 412).
- [ ] `.../securitygroups/ownership.test.ts` — 4 cases.
- [ ] `.../-details/ruleFormatting.test.ts` — ICMP name/alias/number, type-without-code, absent vs null port fields, equal min/max, range.
- [ ] `BulkDeleteSecurityGroupsModal.test.tsx` — type-to-confirm gate (including trimmed input and a wrong word), deletable-only payload, undeletable section + reason, 20-item truncation, disabled states.
- [ ] `BulkDeleteRulesModal.test.tsx`, `BulkDeleteRBACPoliciesModal.test.tsx` — type-to-confirm gate on `delete` and `remove` respectively (including that the *other* word does not unlock it), pluralized title/label, 5-item truncation, single `onConfirm`, disabled while loading.
- [ ] `client/utils/bulkDispatch.test.ts` — batch splitting and ordering, mid-batch rejection contributing only its own IDs, merged partial results, empty input, exact-boundary input.

### Unit tests (extended existing files)
- [ ] `securityGroupRouter.test.ts`, `rbacPolicyRouter.test.ts` — `describe("deleteBulk")`.
- [ ] `Network/types/securityGroup.test.ts`, `rbacPolicy.test.ts` — bulk input schema parse cases.
- [ ] `SecurityGroupToastNotifications.test.tsx` — severity + title per outcome per resource, failure-list truncation.
- [ ] `SecurityGroupListContainer.test.tsx`, `SecurityGroupTableRow.test.tsx` — select column presence/absence, `columnCount`, checkbox does not navigate.
- [ ] `SecurityGroupsList.test.tsx` — Zone 3 gating, select-all, disabled Actions, partial-failure selection retention.
- [ ] `SecurityGroupRulesTable.test.tsx` — Zone 3 gating, `columnCount`/`colSpan` in both modes, select-all scoped to displayed rules.
- [ ] `SecurityGroupRBACPolicies.test.tsx` — Zone 3 gating, `columnCount`/`colSpan` in all three status states, select-all scoped to search results.
- [ ] `useSecurityGroupDetails.test.ts` — conditional invalidation, result passthrough, non-throwing rejection path.
- [ ] `SecurityGroupDetailsView.test.tsx` — new prop forwarding.

### Integration scenarios (component-level, jsdom)
- [ ] Select 3 groups → 1 shared from another project → modal shows 2 deletable + 1 undeletable → confirm sends exactly 2 IDs.
- [ ] Bulk delete returns 2 successful / 1 failed → warning toast, only the failed row still checked, list invalidated once.
- [ ] `deleteBulk` rejects entirely → error toast, selection untouched, no invalidation.
- [ ] Change a filter while rows are selected → off-list selections vanish from the count without an extra render loop.
- [ ] Switch Rules → RBAC → Rules: selection is empty on return.

### Manual verification
1. `pnpm dev`, open `/projects/<id>/network/securitygroups`.
2. With delete permission: Zone 3 appears; without it (a viewer-role token), Zone 3 and all row checkboxes are absent.
3. Select several groups including one shared from another project; open the modal; confirm the two sections and their reasons; confirm the button stays disabled until `delete` is typed exactly (try `Delete`, ` delete `, `del`).
4. Confirm; watch the toast wording match the outcome; confirm the list refreshes and only failures stay selected.
5. Select the project's `default` group alone and delete → expect a per-item 409 failure with the "in use by one or more ports" message and the modal's closing note explaining the default-group case.
6. Detail page → Rules tab: select via header checkbox after applying a protocol filter → only filtered rows are selected; delete → the modal demands the word `delete`, the list of rules is identifiable via `formatRuleLabel`; toast fires; rules refresh.
7. RBAC tab: same, with search applied — the gate here demands `remove`, and typing `delete` must not enable the button; switch tabs and back to confirm selection resets.
8. Toggle locale to German and re-check every new string and both plural forms.
9. In a project with more than 100 security groups (or by temporarily lowering `BULK_DISPATCH_BATCH_SIZE` to 2), select all and delete → confirm the network tab shows several sequential `deleteBulk` calls and a single merged toast, with no `BAD_REQUEST`.

## Acceptance Criteria

- [ ] Three new procedures exist — `network.securityGroup.deleteBulk`, `network.securityGroupRule.deleteBulk`, `network.rbacPolicy.deleteBulk` — each `projectScopedProcedure` + `withErrorHandling`, each returning `{ successful: string[]; failed: { id: string; error: string }[] }`.
- [ ] `deleteById` (groups), `delete` (rules) and `delete` (RBAC) are byte-for-byte unchanged apart from the additive imports the new procedures need.
- [ ] No per-item client-side delete loop anywhere: each surface issues one `deleteBulk` call per ≤100-ID batch via `dispatchInBatches`, and one merged result reaches the toast.
- [ ] Every ID is passed through `validateAndEncodeResourceId` **before** the first DELETE; a malformed ID rejects the whole call and issues zero DELETEs (asserted by test).
- [ ] Per-item failures carry the domain `*ErrorHandlers` message verbatim; systemic failures reject the whole call.
- [ ] `Compute/types/image.ts`, `Compute/helpers/imageHelpers.ts` and all Compute tests are untouched.
- [ ] All three surfaces render Zone 3 only when the relevant delete permission is granted, as a separate `DataGridToolbar`, with a `checked`/`indeterminate` select-all scoped to the currently displayed rows and a `moreVert` `PopupMenu` whose button is disabled until something is selected.
- [ ] Action labels use `plural()`; every new user-visible string is Lingui-wrapped; `pnpm check-i18n` is clean and the de catalog has no untranslated new entries.
- [ ] **All three** bulk modals gate on a typed word compared against an untranslated `CONFIRM_WORD` constant — `delete` for groups and rules, `remove` for RBAC policies — so no bulk action is easier to trigger than its single-item equivalent. All three also show an itemised list of what will be affected.
- [ ] A per-item 404 inside a bulk call lands in `successful`, not `failed`; the single-item procedures still report `NOT_FOUND`.
- [ ] A selection larger than `MAX_BULK_DELETE_ITEMS` succeeds via sequential batching; a rejected batch contributes only its own IDs to `failed` and does not abort the remaining batches.
- [ ] Undeletable rows can be selected, appear in a separate "cannot be deleted" section with a reason, and are excluded from the submitted ID list.
- [ ] `columnCount`/`colSpan` are correct in loading, error and empty states on all three tables, in both bulk-enabled and bulk-disabled modes.
- [ ] Selection survives sort/filter/search/refetch (pruned by derivation, not by effect), resets on detail-tab switch, clears on full success, and retains only failed IDs on partial failure.
- [ ] No new permission key; `PERMISSION_KEY_PATTERN.md` and `Network/routers/permissionRouter.ts` are unmodified by this work.
- [ ] Colocated `*.test.ts(x)` coverage exists for the new helper, the three procedures, the three modals and the selection logic on all three surfaces.
- [ ] A new `.changeset/*.md` marks `@cobaltcore-dev/aurora` as `minor`.
- [ ] `pnpm typecheck --filter @cobaltcore-dev/aurora`, `pnpm lint --filter @cobaltcore-dev/aurora`, `pnpm test --filter @cobaltcore-dev/aurora` and `pnpm check-i18n` all pass; no regression in the pre-existing security-groups tests.

## Open Questions

**None outstanding.** All six questions from the original draft were resolved on 2026-09-09 — see **Decisions resolved after review** at the top of this file for each decision and its reasoning. The plan body has been updated to match, so no step still depends on an unanswered question.

Two things were consciously deferred rather than answered, and are *not* part of this work:

- **Split `canDeleteRBAC` out of `canManageAccess`.** The RBAC bulk gate stays on `canManageAccess` (the AND of the RBAC create+delete keys), matching `RBACPolicyRow`'s existing gate. A dedicated delete flag would touch `useSecurityGroupPermissions.ts` and both RBAC components; worth a follow-up, not worth widening this change.
- **A `bulkDelete`-specific 409 message on `SecurityGroupErrorHandlers`.** The reused handler says "in use by one or more ports", which is also what a default-security-group 409 renders (see D10). Mitigated in modal copy for now.

---

### Key file paths referenced

**Server (to modify / create)**
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Network/helpers/bulkOperations.ts` *(new)*
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Network/types/index.ts`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Network/types/securityGroup.ts`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Network/types/rbacPolicy.ts`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Network/routers/securityGroupRouter.ts`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Network/routers/securityGroupRuleRouter.ts`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Network/routers/rbacPolicyRouter.ts`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Network/helpers/securityGroupHelpers.ts` *(read-only reference: `SecurityGroupErrorHandlers`, `SecurityGroupRuleErrorHandlers`)*
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Network/helpers/rbacPolicyHelpers.ts` *(read-only reference)*

**Client (to modify / create)** — all under `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/`
- `ownership.ts` *(new)*, `-components/SecurityGroupsList.tsx`, `-components/SecurityGroupListContainer.tsx`, `-components/SecurityGroupTableRow.tsx`, `-components/SecurityGroupToastNotifications.tsx`, `-components/-modals/BulkDeleteSecurityGroupsModal.tsx` *(new)*
- `$securityGroupId/-components/SecurityGroupDetailsView.tsx`, `$securityGroupId/-components/-details/SecurityGroupRulesTable.tsx`, `$securityGroupId/-components/-details/ruleFormatting.ts` *(new)*, `$securityGroupId/-components/-details/SecurityGroupRBACPolicies.tsx`, `$securityGroupId/-components/-details/RBACPolicyRow.tsx`, `$securityGroupId/-hooks/useSecurityGroupDetails.ts`, `$securityGroupId/index.tsx`, `$securityGroupId/-modals/BulkDeleteRulesModal.tsx` *(new)*, `$securityGroupId/-modals/BulkDeleteRBACPoliciesModal.tsx` *(new)*

**Reference implementations (read-only)**
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Compute/helpers/imageHelpers.ts` (lines 566-712), `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Compute/routers/imageRouter.ts` (lines 842-869), `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Compute/types/image.ts` (lines 340-349)
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/{List.tsx,ImageListView.tsx,DeleteImagesModal.tsx,ImageToastNotifications.tsx}`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Swift/Containers/{index.tsx,EmptyContainersModal.tsx,ContainerToastNotifications.tsx}`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/{CorsRulesTab.tsx,DeleteCorsRulesModal.tsx}`
