# Plan: Ceph permission-gating review fixes

**Date:** 2026-08-26 · **Status:** implemented 2026-08-26 (Steps 1–10 done, Step 11 skipped by
decision — typecheck/lint/216 test files/5483 tests/i18n/format all green, security review clean)

> Fixes the findings from a `/triple-review` (security + performance + architecture, run in
> parallel) against the Ceph/S3 permission-gating work on branch `kiryl-ceph-permissions`
> (commits `4fa8b349`, `1999dc32`, `4e917e0b`). That work is otherwise done — typecheck/lint/test
> all green (213 files / 5441 tests) — this plan only addresses review findings before merge.
> All 11 findings below were re-verified against the current code by `dev-planner`, not taken on
> faith from the review report.

## Overview

Fix the review findings on the three-commit Ceph/S3 permission-gating work (`4fa8b349..4e917e0b`)
before it merges. Four Medium findings are must-fix (one UX flash, one naming-convention
violation, one layout regression, one undocumented policy decision); seven Low findings are
optional polish/test-coverage steps, grouped separately so a subset can be implemented without
re-planning.

## Architecture Analysis

**Current state (verified):**

- `packages/aurora/src/server/Storage/routers/permissionRouter.ts` — `STORAGE_MAPPINGS` maps UI
  keys → oslo.policy rules. Its own docblock states resources must be "backend-agnostic".
- `apps/dashboard/src/policies/storage.json` — the reference policy file operators fork. 11 new
  rules were added; 9 → `rule:storage_admin`, 2 → `rule:storage_viewer`.
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/hooks/useCephPermissions.ts`
  — one `storage.canUser` query with a 21-entry positional array, `staleTime/gcTime: Infinity`,
  defaults all-false.
- Consumers: `Buckets/index.tsx`, `BucketHeader.tsx` → `BucketHeaderActions.tsx`,
  `CorsRulesTab/Table`, `LifecycleRulesTab/Table`, `Objects/ObjectBrowserView.tsx`,
  `Objects/ObjectsTableView.tsx`, `Buckets/CredentialPrompt.tsx`.

**Critical constraint confirmed (affects Step 2 and Step 10):** `createPermissionRouter` validates
permission keys with `z.string().superRefine(...).transform(v => v as keyof TMappings)` — the tRPC
**input type is plain `string`**, not a literal union. So renaming a key in `STORAGE_MAPPINGS`
will **not** produce a typecheck error in `useCephPermissions.ts`; a missed rename surfaces only
as a runtime `BAD_REQUEST: Unknown permission`, which (because the whole batched query then fails)
makes **all 21 permissions fall back to `false`** — i.e. the entire Ceph UI silently goes
read-only. Likewise there is **no** compile-time or test-time link between a mapping's `rule:`
string and `storage.json`; a drifted rule name just returns `false` forever.

**Established patterns to follow:**

- Bulk-toolbar placeholder: `Buckets/index.tsx` (Zone 3 comment), `Objects/ObjectBrowserView.tsx`,
  `LifecycleRulesTab.tsx` all use `cond ? (<Stack>…</Stack>) : (<span />)`.
- Collapsible selection column: `BucketTableView.tsx` (`hasAnyBulkAction` → `columnCount`,
  `gridColumnTemplate`, `{hasAnyBulkAction && <DataGridHeadCell />}`).
- Permission-loading UI: `network/securitygroups/$securityGroupId/index.tsx` renders `<Spinner>` +
  "Loading Permissions..." while `isLoading`.
- Test mocking: `let mockCephPermissions = {…}` +
  `vi.mock("../hooks/useCephPermissions", () => ({ useCephPermissions: () => ({ permissions:
  mockCephPermissions, isLoading: false, isError: false }) }))` — used in `CorsRulesTab.test.tsx`
  and `CredentialPrompt.test.tsx`.

## Potential Problems & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Rename (Step 2) missed in one of the 5 files → runtime `BAD_REQUEST` kills the whole batched `canUser` query, silently blanking every Ceph mutation control | High | Single repo-wide grep before/after (`grep -rn "s3_credential" . --exclude-dir=node_modules --exclude-dir=.git`), must return zero. Typecheck will **not** catch this. Manual smoke test required. |
| Rule name in `STORAGE_MAPPINGS` drifting from `storage.json` (Steps 2, and 9 if taken) | High | Both files edited in the same commit; verify with the grep in each step's Verification block. |
| `minContentColumns` on `LifecycleRulesTable` is a zero-based column index array (`[0, 7]`) — dropping the select column shifts the actions column from 7 → 6 | Medium | Step 5 explicitly recomputes it as `canDeleteLifecycle ? [0, 7] : [6]`. Verified against juno-ui-components 9.3.0 `DataGrid` source. |
| Adding a `<Trans>` string in Step 1 forces a locale-catalog regeneration (`pnpm check-i18n` is a CI job) | Low | Step 1 uses a bare `<Spinner>` with no new translatable string — no `.po`/`.ts` churn. |
| `CredentialPrompt.test.tsx`'s `useCephPermissions` mock hardcodes `isLoading: false` | Low | Step 1 makes it a mutable `mockIsLoadingPermissions` let, same shape as `mockCanCreateCredential`. |
| Finding 1's flash is rarer than the report implies — `Buckets/index.tsx` calls `useCephPermissions` on the same query key, so it's usually warm before `CredentialPrompt` mounts | Info | Still worth fixing (the buckets query can error faster than the policy query resolves), but don't expect it to reproduce reliably by hand. |

## Prerequisites

- [x] Credential rename target decided (2026-08-26): `storage:credentials:create` /
      `storage:credential_create` (Step 2).
- [x] Step 11 (rule verb-order rename) decided (2026-08-26): **skip** — not part of this
      implementation pass.
- [ ] Confirm nothing has merged into `kiryl-ceph-permissions` since `4e917e0b` that touches these
      files.
- [ ] KB (`../DOCS/aurora-dashboard-kb/`) is pinned to `90be7d9a` (44 commits behind `packages/`/
      `apps/`, all from this same branch's own recent merges — not flagged as stale). Its
      `02-architecture.md` permission-key section will need a touch-up after Step 2 renames a key
      it doesn't currently mention by name — low priority, KB-only, not part of this PR.

---

## MUST-FIX STEPS (Medium findings 1–4)

### Step 1: Branch on `isLoading` in `CredentialPrompt`

**Finding — confirmed.** `CredentialPrompt` destructures only `{ permissions }`; `isLoading` is
discarded. `permissions.canCreateCredential` is `false` from `DEFAULT_PERMISSIONS` while loading,
so the denial `Message` renders first, even for a user who does have the permission.

**Files to modify:**
- `.../Ceph/Buckets/CredentialPrompt.tsx`
- `.../Ceph/Buckets/CredentialPrompt.test.tsx`

**What to do:**

1. Change the hook destructuring to
   `const { permissions, isLoading: isLoadingPermissions } = useCephPermissions(projectId)`.
2. Convert the existing two-way ternary at the bottom of the `<Stack>` into a three-way branch.
   Keep the heading and both `<p>` paragraphs unconditional; only the button/Message slot changes:
   - `isLoadingPermissions` → `<Spinner variant="primary" size="small" />` (import `Spinner` from
     `@cloudoperators/juno-ui-components`, already the import source in this file).
   - `permissions.canCreateCredential` → existing `<div><Button …/></div>`.
   - otherwise → existing `<Message variant="info" …>`.
3. **Do not** add a `<Trans>Loading permissions…</Trans>` label — a bare `Spinner` avoids a new
   catalog message and therefore any `messages.po`/`messages.ts` churn.
4. In `CredentialPrompt.test.tsx`, replace the hardcoded `isLoading: false` in the
   `vi.mock("../hooks/useCephPermissions", …)` factory with a hoisted mutable
   `let mockIsLoadingPermissions = false`, mirroring the existing `mockCanCreateCredential`
   pattern; reset it to `false` in the existing `beforeEach`.
5. Add a `describe("Permission gating")` block with three cases:
   - loading → neither the button nor the denial text is present; the heading is still there.
   - not loading, `canCreateCredential: false` → denial text present, button absent.
   - not loading, `canCreateCredential: true` → button present, denial text absent.

**Expected outcome:** a user with the permission never sees the denial message; a user without it
still does, only after the query settles.

**Verification:**
```bash
pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets/CredentialPrompt.test.tsx
pnpm --filter @cobaltcore-dev/aurora typecheck
```

---

### Step 2: Rename the S3-credential permission key and rule to a backend-neutral name

**Finding — confirmed.** `"storage:s3_credentials:create"` / `"storage:s3_credential_create"`
uses the protocol name, contradicting the docblock three lines above the mapping ("resources must
be backend-agnostic... never the OpenStack service name"). The underlying resource is a Keystone
EC2 credential.

**Decided (2026-08-26):** permission key `storage:credentials:create`, policy rule
`storage:credential_create`.

**Files to modify (exhaustive — verified by repo-wide grep; exactly 5 occurrences):**
- `packages/aurora/src/server/Storage/routers/permissionRouter.ts` — the `STORAGE_MAPPINGS` entry
  under `// Ceph/S3 Credential Operations`
- `apps/dashboard/src/policies/storage.json` — the `"storage:s3_credential_create"` key
- `.../Ceph/hooks/useCephPermissions.ts` — the **last** entry of the `permission` array (index 20)
- `PERMISSION_KEY_PATTERN.md` — the `"storage:s3_credentials:create"` example line
- `.changeset/better-cars-brake.md` — `storage:s3_credential_create` in the operator rule list

**What to do:**

1. `permissionRouter.ts`: rename both the key and the `rule:` value.
2. `storage.json`: rename the key. **Keep its position and keep the value
   `"rule:storage_viewer"`** (Step 4 explains why it's viewer-tier).
3. `useCephPermissions.ts`: rename the array entry **in place** — it must stay at index 20 to keep
   aligning with `canCreateCredential`, the last name in the `select` destructuring. Do not
   reorder.
4. `PERMISSION_KEY_PATTERN.md` and the changeset: rename the mentions.
5. Re-grep and confirm zero hits (exclude the gitignored `apps/dashboard/dist/` build artifact, or
   `rm -rf apps/dashboard/dist` first):
   ```bash
   grep -rn "s3_credential" . --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=dist
   ```
6. Verify the mapping's `rule:` value and the `storage.json` key match character-for-character:
   ```bash
   grep -n "credential" packages/aurora/src/server/Storage/routers/permissionRouter.ts apps/dashboard/src/policies/storage.json
   ```

**Expected outcome:** no `s3_` anywhere in the permission vocabulary; behavior identical.

**Verification:**
```bash
pnpm --filter @cobaltcore-dev/aurora typecheck   # will NOT catch a missed rename — see risk table
pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph
pnpm --filter @cobaltcore-dev/aurora lint
```

⚠️ **Manual smoke test is mandatory** (typecheck cannot cover this): `pnpm dev`, open a Ceph
bucket list, confirm in the network tab that `storage.canUser` returns a 21-element boolean array
rather than a `BAD_REQUEST`, and that create/delete controls still appear for an admin user.

---

### Step 3: Add the `<span />` placeholder to `CorsRulesTab`'s bulk toolbar

**Finding — confirmed.** `CorsRulesTab.tsx` uses `{permissions.canDeleteCors && (<Stack …>)}`
inside a `Stack distribution="between"`; `LifecycleRulesTab.tsx`, `Buckets/index.tsx` and
`Objects/ObjectBrowserView.tsx` all use the ternary + `<span />` form so the "N rules" counter
stays right-aligned.

**Files to modify:**
- `.../Ceph/Buckets/CorsRulesTab.tsx`
- `.../Ceph/Buckets/CorsRulesTab.test.tsx`

**What to do:**

1. In the Zone 2 bulk-actions-toolbar block, convert
   `{permissions.canDeleteCors && (<Stack gap="2" alignment="center">…</Stack>)}` into
   `{permissions.canDeleteCors ? (<Stack gap="2" alignment="center">…</Stack>) : (<span />)}` —
   byte-for-byte the same shape as `LifecycleRulesTab.tsx`. Don't touch the inner contents.
2. Extend the existing "hides the bulk selection/actions toolbar when canDeleteCors is false" test
   in `describe("Permission gating")` to also assert the placeholder keeps the counter
   right-aligned (query structurally — e.g. assert the counter's parent `Stack` still has 2
   children and the sibling before it is a `SPAN`).

**Expected outcome:** the "N rules" counter stays right-aligned for a read-only user, matching all
three sibling components.

**Verification:**
```bash
pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets/CorsRulesTab.test.tsx
```
Manual: with `canDeleteCors: false`, open a bucket's CORS tab and confirm the counter sits at the
right edge, level with the Lifecycle tab.

---

### Step 4: Document why two rules are `storage_viewer`, not `storage_admin`

**Finding — confirmed.** In `storage.json`, `storage:object_share` and (post-Step-2) the
credential-create rule are `rule:storage_viewer`; the other 9 new rules are `rule:storage_admin`.
Nothing anywhere explains the split.

**Files to modify:**
- `permissionRouter.ts` — the top docblock's `Ceph/S3-specific notes:` list
- `.changeset/better-cars-brake.md`

**What to do:**

1. Add a bullet to the `Ceph/S3-specific notes:` list (same style as the existing
   versioning-toggle bullet):
   - `storage:objects:share` is viewer-tier because a presigned GET URL grants exactly the access
     the viewer already has via `storage:objects:download` — it re-exports an existing capability,
     not a new one.
   - The credential-create rule is viewer-tier because it's a self-service prerequisite for *any*
     Ceph access at all, including read-only browsing; requiring admin would make a
     `storage_viewer` unable to list buckets.
   - Note explicitly: operators forking `storage.json` should keep these two at viewer tier unless
     they deliberately want to lock read-only users out of S3 entirely.
2. In the changeset body, after the sentence listing the 11 required rules, add one sentence
   naming the two viewer-tier rules and the reasoning above.
3. Do **not** add comments to `storage.json` itself — JSON has no comment syntax and
   `loadPolicyEngine` parses it strictly.

**Verification:**
```bash
pnpm --filter @cobaltcore-dev/aurora typecheck
pnpm format:check
```
Docs-only; no test change. Confirm both rule names match Step 2's post-rename names.

---

## OPTIONAL STEPS (Low findings 5–11)

Ordered by value-per-effort. Steps 5–8 are self-contained and can be taken individually. Step 9
must come after Step 2. Step 10 is the largest. Step 11 is recommended to skip.

### Step 5: Collapse the selection column in both rule tables — *recommended*

**Finding — confirmed.** `CorsRulesTable.tsx`/`LifecycleRulesTable.tsx` keep `columns={8}`, always
render the sr-only "Select" head cell, and render an empty `DataGridCell` when the delete
permission is false. `BucketTableView.tsx` does this correctly via `hasAnyBulkAction`.

**Files to modify:**
- `.../Ceph/Buckets/CorsRulesTable.tsx` (+ `.test.tsx`)
- `.../Ceph/Buckets/LifecycleRulesTable.tsx` (+ new `.test.tsx` if Step 8 also taken)

**What to do (CorsRulesTable):**

1. Add `const columnCount = canDeleteCors ? 8 : 7` next to `const isEmpty = …`.
2. `<DataGrid columns={8}>` → `<DataGrid columns={columnCount}>`.
3. Wrap the leading head cell in `{canDeleteCors && (<DataGridHeadCell>…</DataGridHeadCell>)}`.
4. Empty-state `colSpan={8}` → `colSpan={columnCount}`.
5. Wrap the whole leading row `DataGridCell` (not just the `Checkbox` inside it) in
   `{canDeleteCors && (…)}`.

**What to do (LifecycleRulesTable) — same, plus:**

6. ⚠️ `minContentColumns={[0, 7]}` is a zero-based column index array (verified against
   juno-ui-components 9.3.0's `DataGrid` source). Dropping column 0 shifts the actions column from
   index 7 to 6: `minContentColumns={canDeleteLifecycle ? [0, 7] : [6]}`. Getting this wrong
   silently makes the Rule ID column min-content-width.

**Verification:**
```bash
pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets/CorsRulesTable.test.tsx
```
Add: `canDeleteCors={false}` → "Select" label absent; `canDeleteCors={true}` → present. Manual:
inspect `gridTemplateColumns` for the lifecycle table in both permission states.

---

### Step 6: Comment and test the `canDeleteVersion` gate on deleted rows — *recommended*

**Finding — confirmed.** In `ObjectsTableView.tsx`, the deleted-folder and deleted-file branches
gate "Delete Folder"/"Delete Object" on `canDeleteVersion`, not `canDeleteFolder`/`canDeleteObject`
— correct (these permanently purge version/delete markers), but undocumented and untested.

**Files to modify:**
- `.../Ceph/Objects/ObjectsTableView.tsx` (+ `.test.tsx`)

**What to do:**

1. Add a one-line comment above each `{canDeleteVersion && (<PopupMenuItem label={t\`Delete
   Folder\`} …` / `t\`Delete Object\`` explaining the substitution (permanent version/delete-marker
   purge, not a soft delete).
2. Add test cases to the existing `describe("permission gating")` block:
   - Deleted folder, `canDeleteVersion: false, canDeleteFolder: true, canRestoreVersion: true` →
     `Restore` present, `Delete Folder` absent.
   - Deleted file, same shape → `Restore` present, `Delete Object` absent.
   - Optional third case: both `canDeleteVersion: false` and `canRestoreVersion: false` on a
     deleted row → no menu button at all (exercises the `hasAnyRowAction` early return).

**Verification:**
```bash
pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Objects/ObjectsTableView.test.tsx
```

---

### Step 7: Simplify `BucketHeaderActions` and add its test file — *recommended*

**Finding — confirmed.** `canToggleVersioning`'s `||` chain over `versioningStatus.status` covers
all three union members (reduces to `Boolean(versioningStatus)`); the JSX re-derives the condition
inline instead of reusing the computed value; a redundant `<>…</>` wraps a single `PopupMenu`; no
test file exists despite 6 new required boolean props.

⚠️ You cannot simply reuse a single `canToggleVersioning` boolean in the JSX — Enable vs. Suspend
need to be distinguished, and a boolean doesn't narrow `versioningStatus` for TypeScript. Derive
three values instead.

**Files to modify/create:**
- `.../Ceph/Buckets/BucketHeaderActions.tsx`
- **new** `.../Ceph/Buckets/BucketHeaderActions.test.tsx`

**What to do:**

1. Replace the `canToggleVersioning` block with:
   ```ts
   const versioningState = canUpdateVersioning ? versioningStatus?.status : undefined
   const canEnableVersioning = versioningState === "Unversioned" || versioningState === "Suspended"
   const canSuspendVersioning = versioningState === "Enabled"
   const canToggleVersioning = canEnableVersioning || canSuspendVersioning
   ```
2. Replace the two versioning `PopupMenuItem` guards with `{canEnableVersioning && (…)}` and
   `{canSuspendVersioning && (…)}`.
3. Remove the redundant `<>`/`</>` wrapping the single `PopupMenu`.
4. Create `BucketHeaderActions.test.tsx` (pure presentational component — only `I18nProvider` +
   `PortalProvider` needed, see `CredentialPrompt.test.tsx` for setup). Cases: all granted → every
   item visible; all six booleans false → empty render; one case per permission flipped to false;
   `versioningStatus: "Unversioned"` → Enable visible, Suspend absent; `versioningStatus:
   undefined` → neither versioning item renders; `hasPolicy: false` → Add Policy visible, Delete
   Policy absent; `isBucketEmpty: true` → Empty Bucket absent.

**Verification:**
```bash
pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets/BucketHeaderActions.test.tsx
pnpm --filter @cobaltcore-dev/aurora typecheck
```

---

### Step 8: Add Lifecycle gating tests and individual-item assertions for CORS

**Finding — confirmed.** No `LifecycleRulesTab.test.tsx`/`LifecycleRulesTable.test.tsx` exists.
`CorsRulesTable.test.tsx` never asserts `Edit`/`Delete CORS Rule` gate independently — the exact
behavior commit `4e917e0b` introduced.

**Files to create/modify:**
- **new** `.../Ceph/Buckets/LifecycleRulesTab.test.tsx`
- **new** `.../Ceph/Buckets/LifecycleRulesTable.test.tsx`
- `.../Ceph/Buckets/CorsRulesTable.test.tsx` (extend)

**What to do:**

1. `CorsRulesTable.test.tsx` — add `describe("Permission gating")`: `canUpdateCors: true,
   canDeleteCors: false` → Edit present, Delete absent; reverse case; both false → no `more`
   button on the row.
2. **new** `LifecycleRulesTable.test.tsx` — mirror `CorsRulesTable.test.tsx`'s structure/mocks,
   same three gating cases against `Edit Lifecycle Rule`/`Delete Lifecycle Rule`, plus a rendering
   smoke test for columns/empty state.
3. **new** `LifecycleRulesTab.test.tsx` — mirror `CorsRulesTab.test.tsx` for the lifecycle domain
   (mock `trpcReact.storage.ceph.lifecycle.*`, mock `./LifecycleRulesTable`, mutable
   `mockCephPermissions`). Cases: hides `Create Lifecycle Rule` when `canUpdateLifecycle` false;
   hides bulk toolbar when `canDeleteLifecycle` false.
4. One Lifecycle-specific case worth adding: `skippedRuleCount > 0` sets `mutationsBlocked`, which
   disables the Actions button independently of permissions — assert the checkbox is present but
   the Actions button is disabled when `canDeleteLifecycle: true` and a rule is skipped.

**Verification:**
```bash
pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets
```

---

### Step 9: Regroup `STORAGE_MAPPINGS` by resource, drop "Ceph/S3" from headings

**Finding — confirmed.** `"storage:objects:share"` sits under `// Ceph/S3 Object Version
Operations` (it's neither Ceph-specific nor a version op); `"storage:containers:update_versioning"`
has its own section instead of living with the other `containers:*` keys.

⚠️ Do this **after** Step 2 — both touch the same file.

**Files to modify:**
- `permissionRouter.ts`
- `PERMISSION_KEY_PATTERN.md` (mirrors the same section headings)

**What to do:**

1. Move `"storage:containers:update_versioning"` into `// Container Operations`, right after
   `"storage:containers:update_acls"`.
2. Move `"storage:objects:share"` into `// Object Operations`, after `"storage:objects:move"`.
3. Rename remaining section comments to resource-based, backend-neutral names: `// Object Version
   Operations`, `// Container Policy Operations`, `// CORS Operations`, `// Lifecycle Operations`,
   `// Credential Operations`.
4. Apply the same regrouping to `PERMISSION_KEY_PATTERN.md`'s `### Storage` code block.
5. Leave the `Ceph/S3-specific notes:` prose list where it is — that's the right home for
   backend-specific rationale.

**Verification:**
```bash
pnpm --filter @cobaltcore-dev/aurora typecheck
pnpm --filter @cobaltcore-dev/aurora test src/server/policies
pnpm format:check
```
Confirm entry count unchanged (30 keys before and after).

---

### Step 10: Derive the permission array and `select` from one `PERMISSION_MAP`

**Finding — confirmed.** `useCephPermissions.ts` holds a 21-entry `permission` array and a
21-name positional `select` destructuring, linked only by a comment. A reorder/insert in one list
without the other silently misattributes booleans.

⚠️ **Scope honesty:** because `canUser`'s tRPC input type is plain `string` (not a literal
union), this buys `CephPermissions`-key safety (a missing/renamed `canX` fails to compile), not
permission-string safety (a typo'd policy string still only fails at runtime). Still a real
improvement — the positional-shift bug class disappears entirely.

**Files to modify:**
- `.../Ceph/hooks/useCephPermissions.ts`

**What to do:**

1. Replace `DEFAULT_PERMISSIONS` and the two positional lists with one source of truth:
   ```ts
   const PERMISSION_MAP = {
     canCreateBucket: "storage:containers:create",
     // …all 21…
     canCreateCredential: "storage:credentials:create",
   } as const satisfies Record<keyof CephPermissions, string>
   ```
2. Derive the request array and key order once, at module scope (must be module-level constants,
   not computed in the hook body — the array is part of the tRPC query key, and a fresh identity
   each render would break the `staleTime: Infinity` cache):
   ```ts
   const PERMISSION_KEYS = Object.keys(PERMISSION_MAP) as (keyof CephPermissions)[]
   const PERMISSION_REQUEST = PERMISSION_KEYS.map((k) => PERMISSION_MAP[k])
   ```
3. Derive `DEFAULT_PERMISSIONS` the same way via `Object.fromEntries`.
4. Replace the destructuring `select` with an index-driven one over `PERMISSION_KEYS`, keeping
   `?? false` per entry to preserve fail-closed behavior on a short array.
5. Update the docblock comment accordingly. Keep the exported `CephPermissions` interface as-is —
   it's the contract every consumer's props are typed against.

**Verification:**
```bash
pnpm --filter @cobaltcore-dev/aurora typecheck
pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph
```
Temporarily delete one line from `PERMISSION_MAP` and confirm `typecheck` fails on the `satisfies`
clause; restore it. Manual: confirm `storage.canUser` still fires exactly once per project.

---

### Step 11: Rule-name verb placement — **decided: skip (2026-08-26)**

**Confirmed as described, but the finding is weak.** Claim: `storage:container_cors_delete`
should be `storage:container_delete_cors` to match `storage:container_update_access_control` /
`storage:folder_create_object`.

Why to leave it:
- The file already supports both readings — `storage:object_version_delete`/`_restore` (shipped in
  this same PR, not flagged by the finding) are also `<compound_resource>_<verb>`, identical shape
  to `container_cors_delete`.
- The verb-first precedents (`container_update_access_control`, `container_show_access_control`,
  `folder_create_object`, `object_create_copy`) read as verb-object phrases, not compound resource
  names.
- The finding's own count doesn't reconcile (claims "8 of 11"; the actual group is 7, and including
  the object-version rules for consistency would make 9).
- No compile-time or test-time link exists between `storage.json` and `permissionRouter.ts`'s
  `rule:` values (verified) — every rename here is a chance to silently disable a permission
  forever, for a stylistic tie-break.

**If taken anyway** — mechanical spec, do in one commit across both files:
`container_versioning_update` → `container_update_versioning`; `container_policy_update` →
`container_update_policy`; `container_policy_delete` → `container_delete_policy`;
`container_cors_update` → `container_update_cors`; `container_cors_delete` →
`container_delete_cors`; `container_lifecycle_update` → `container_update_lifecycle`;
`container_lifecycle_delete` → `container_delete_lifecycle`. Decide explicitly whether
`object_version_delete`/`_restore` are in scope too (the finding excludes them, which would leave
the file more mixed than before). Leave the *permission keys* alone. Update
`.changeset/better-cars-brake.md` and `PERMISSION_KEY_PATTERN.md`. Verify with a per-rule grep
count of 1 in both files for every renamed rule.

---

## Testing Plan

**Unit tests (new/extended):**
- [ ] `CredentialPrompt.test.tsx` — loading / denied / granted (Step 1)
- [ ] `CorsRulesTab.test.tsx` — placeholder keeps the counter right-aligned (Step 3)
- [ ] `CorsRulesTable.test.tsx` — select column absent when `canDeleteCors` false (Step 5);
      Edit/Delete gate individually (Step 8)
- [ ] `ObjectsTableView.test.tsx` — deleted-folder and deleted-file `canDeleteVersion` gating
      (Step 6)
- [ ] `BucketHeaderActions.test.tsx` — new file (Step 7)
- [ ] `LifecycleRulesTab.test.tsx` / `LifecycleRulesTable.test.tsx` — new files (Step 8)

**Manual verification (after Steps 1–4):**
1. `pnpm dev`, log in, open a project's Ceph/S3 storage.
2. Network tab: confirm `storage.canUser` returns a 21-element boolean array, not `BAD_REQUEST`
   (the real check on Step 2's rename).
3. As admin: confirm every gated control still appears (bucket create/delete/empty, versioning
   enable/suspend, policy add/edit/delete, CORS create/edit/delete, lifecycle create/edit/delete,
   object share/delete/copy/move, version restore/delete).
4. As a `storage_viewer` (or by temporarily flipping the relevant `storage.json` rules to `"!"`):
   CORS tab's "N rules" counter stays right-aligned; no controls appear that shouldn't; the
   credential prompt shows a spinner then the correct branch, never a denial flash for a permitted
   user.

## Acceptance Criteria

- [ ] `grep -rn "s3_credential" . --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=dist`
      returns nothing (Step 2)
- [ ] Every rule referenced by `STORAGE_MAPPINGS` exists verbatim as a key in
      `apps/dashboard/src/policies/storage.json`
- [ ] `CorsRulesTab`'s bulk-toolbar branch is structurally identical to `LifecycleRulesTab`'s
- [ ] The viewer-tier rationale appears in both `permissionRouter.ts`'s docblock and the changeset
- [ ] No regressions: all four Ceph tabs (Objects, CORS, Lifecycle, Policy) render for both admin
      and viewer
- [ ] `pnpm --filter @cobaltcore-dev/aurora typecheck`, `lint`, `test` pass; `pnpm format:check`
      passes at repo root
- [ ] `pnpm check-i18n` produces no diff (guaranteed if Step 1 uses a bare `<Spinner>` and no new
      `<Trans>` is introduced anywhere)

## Open Questions

Both resolved with the user on 2026-08-26 — kept here for the record:

1. ~~Step 2 — credential name.~~ **Decided:** `storage:credentials:create` /
   `storage:credential_create`.
2. ~~Step 11 — rule verb order.~~ **Decided: skip.**
3. **Optional-step scope.** Suggested value ordering if only a subset is wanted: **5 → 6 → 7 → 8**,
   then 9 (cosmetic), then 10 (largest). Steps 5–8 together are roughly one focused session and
   close the two genuine defects (a11y column, untested deleted-row gating) plus the two real
   coverage gaps.

## Commit / changeset notes

- Suggested split: one `fix(aurora):` commit for Steps 1 + 3 (UI behavior), one `refactor(aurora):`
  for Step 2 (rename), one `docs(aurora):` for Step 4. Optional steps: `test(aurora):` for 6/7/8,
  `refactor(aurora):` for 5/9/10.
- Steps 2 and 4 both edit `.changeset/better-cars-brake.md`; edit the **existing** changeset rather
  than adding a new one — this is all part of the same unreleased feature.
- `scope` must be allow-listed in `commitlint.config.mjs`; `aurora` is already used by all three
  existing commits on this branch.

## Relevant file paths

- `packages/aurora/src/server/Storage/routers/permissionRouter.ts`
- `packages/aurora/src/server/policies/createPermissionRouter.ts`
- `apps/dashboard/src/policies/storage.json`
- `PERMISSION_KEY_PATTERN.md`
- `.changeset/better-cars-brake.md`
- `.../Ceph/hooks/useCephPermissions.ts`
- `.../Ceph/Buckets/` — `CredentialPrompt.tsx`, `CorsRulesTab.tsx`, `CorsRulesTable.tsx`,
  `LifecycleRulesTab.tsx`, `LifecycleRulesTable.tsx`, `BucketHeaderActions.tsx`,
  `BucketTableView.tsx`, `index.tsx` (+ colocated `.test.tsx`)
- `.../Ceph/Objects/ObjectsTableView.tsx` (+ `.test.tsx`), `ObjectBrowserView.tsx`
- Reference pattern for permission-loading UI:
  `.../network/securitygroups/$securityGroupId/index.tsx`
