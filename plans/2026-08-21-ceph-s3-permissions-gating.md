# Plan: Epic #608 Section 15 — Permission gating for Ceph/S3 Object Storage

**Date:** 2026-08-21 · **Revised:** 2026-08-24 (step-by-step review with user) · **Status:** implemented 2026-08-24 (security review clean, no findings)

> This plan was walked through step-by-step with the user after the initial draft. Several
> proposed mechanisms were rejected or trimmed during review — see **Decisions Made** at the
> end for the full record of what changed from the original draft and why. The step list below
> already reflects the final, agreed shape.

## Overview

Ceph/S3 UI actions are currently ungated: every bucket, object, policy, CORS, lifecycle,
versioning and EC2-credential **mutation** renders unconditionally. This plan adds the missing
Ceph-specific permission keys to the existing `storage:*` permission router, adds the backing
rules to `storage.json`, and wires the Ceph Buckets/Objects mutation surface to
`trpc.storage.canUser` — client-side only, matching how every other domain in the repo does it.

**Read/list/view actions are intentionally left ungated.** This was verified, not assumed: the
repo's own reference pattern (`useSecurityGroupPermissions` / `SecurityGroupTableRow.tsx`) fetches
a `canView` permission but never uses it to hide anything — "Show Details" always renders. The
established convention across this codebase is "gate mutations, not reads." This plan follows
that convention rather than introducing a new one.

## Architecture Analysis

**Current state (verified against the branch, not the stale root docs):**

- `packages/aurora/src/server/Storage/routers/permissionRouter.ts` — `STORAGE_MAPPINGS`, a single
  `storage` engine (`storage.json`), 22 keys covering `storage:containers:*`, `storage:objects:*`,
  `storage:folders:*`. Mounted as `trpc.storage.canUser`. No test file exists for it (Compute has
  one: `packages/aurora/src/server/Compute/routers/permissionRouter.test.ts`).
- `apps/dashboard/src/policies/storage.json` — JSON, 30 rules, two roles: `storage_admin`
  (`role:admin or role:objectstore_admin`), `storage_viewer` (`role:objectstore_viewer or
  rule:storage_admin`). No `_default` rule.
- **Permission checking in this entire codebase (Compute, Network, Swift, Ceph) is 100%
  client-side.** No domain does server-side enforcement inside tRPC procedures — confirmed by
  exhaustive grep for `assertPermission|requirePermission|enforcePermission|checkPermission` and
  for `canUser` usage inside server routers (zero hits outside the permission routers
  themselves). This plan does not change that.
- Ceph routers needing coverage (`packages/aurora/src/server/Storage/routers/ceph/`):
  `bucketPolicyRouter` (get/set/delete), `corsRouter` (get/set/delete), `lifecycleRouter`
  (get/set/delete), `versioningRouter` (getStatus/setStatus/listVersions/listObjectVersions/
  deleteVersion/restoreVersion/checkDeletedContent), `ec2CredentialRouter` (list/create/delete),
  `objectRouter.generatePresignedUrl`. All 11 proposed keys below were checked against these
  files line-by-line and correspond to real, currently-unguarded procedures — nothing was
  invented that isn't backed by actual code.
  - `versioningRouter.checkDeletedContent` needs **no dedicated key** — it's a read query (drives
    which icon a folder row shows) and reads aren't gated.
  - `ec2CredentialRouter.delete` exists on the backend but has **zero UI consumers** — grepped the
    entire client tree; only `list` and `create` are called (`CredentialPrompt.tsx`). A permission
    key for it is deferred to whichever future PR actually adds a "Delete Credential" UI.
  - `containerRouter` (list/create/delete) and `objectRouter`'s list/getDetails/download/upload/
    copy/move/updateMetadata/delete/deleteBulk/createFolder/deleteAll are already covered by the
    existing 22 generic keys — confirmed by reading the routers. Of those existing keys, the
    *read*-flavored ones (`storage:containers:read`, `storage:containers:list`,
    `storage:objects:read`, `storage:objects:list`, `storage:objects:download`,
    `storage:containers:read_acls`) are pre-existing and untouched by this plan, but this plan
    does **not** start consuming them for UI gating either — consistent with "reads stay
    ungated."
- Client pattern to mirror: `useSecurityGroupPermissions`
  (`.../network/securitygroups/-hooks/useSecurityGroupPermissions.ts`) — one bulk `canUser` query,
  `select` → named booleans, `staleTime: Infinity`, `gcTime: Infinity`, **all-false default while
  loading or on error** (query error and "no data yet" are the same client state, so this default
  also covers the case where an operator's `storage.json` is missing a rule — see Decisions Made
  §1). Consumers *hide* menu items and buttons; Compute Flavors/Images *disable* instead — this
  plan follows the hide convention (Decisions Made §3).
- Two `TODO(perms)` markers to close: `.../Ceph/Objects/ObjectBrowserView.tsx:96-98` and
  `.../Ceph/Buckets/index.tsx:57-60` (both `const hasAnyBulkAction = true`). The Swift ones at
  `.../Swift/Objects/index.tsx:162` and `.../Swift/Containers/index.tsx:55` are explicitly **out
  of scope**.
- Ungated *mutation* surfaces with no TODO marker at all (the actual scope of this plan):
  `BucketHeaderActions` (enable/suspend versioning, add/edit/delete policy, empty, delete
  versions, delete bucket), `CorsRulesTab`/`CorsRulesTable` (create/edit/delete), `LifecycleRulesTab`/
  `LifecycleRulesTable` (create/edit/delete), `ObjectsTableView` row menu (copy, move, edit
  metadata, share, delete, restore, delete version — download and view-versions stay ungated),
  `ObjectVersionHistoryModal` (restore/delete version), `CredentialPrompt` (create S3 credentials).

**Proposed changes:**

1. Add **11** Ceph-specific keys to `STORAGE_MAPPINGS` (mutations only — see Step 1).
2. Add the 11 new rules to `apps/dashboard/src/policies/storage.json`, reusing only
   `rule:storage_admin` / `rule:storage_viewer`.
3. Add a `useCephPermissions` hook exposing only mutation-flavored booleans; call it in container
   components; pass booleans as props into presentational leaves.
4. Read/list/view/download actions (bucket list, object list, download, view versions, view CORS/
   lifecycle/policy config) render unconditionally — no gating added for them, matching the rest
   of the repo.

## Potential Problems & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| An operator's custom `storage.json` lacks one of the 11 new rules → `canUser`'s batched query throws server-side for that whole request | Medium | No new server-side machinery needed (see Decisions Made §1): `useCephPermissions` already returns its all-false default when `data` is `undefined`, which is also true on a query error. Result is "new Ceph mutation controls stay hidden until the operator adds the rules" — fail-closed, not a crash, no toast (no global `onError` wired to the tRPC query client). Call this out explicitly in the changeset. |
| Gating `storage:s3_credentials:create` to `storage_admin` would lock read-only users out of S3 entirely (no EC2 credential ⇒ `NO_CEPH_CREDENTIALS` ⇒ `CredentialPrompt` ⇒ dead button ⇒ no bucket list ever) | High | Mapped to `rule:storage_viewer` instead. Documented explicitly in the mapping comment. |
| 28 Ceph test files mock `@/client/trpcClient` with a narrow object; a component calling `storage.canUser.useQuery` directly would crash them | Medium | Permission query lives **only** in `useCephPermissions`; container tests `vi.mock` that module (1 line), leaves take plain props |
| Fail-closed default hides all actions for one render while the query loads | Medium | `staleTime/gcTime: Infinity` + one shared query for all Ceph screens ⇒ one request per session; matches `useSecurityGroupPermissions`. Do **not** fail open |
| A `PopupMenu` whose every item is permission-hidden renders as an empty popup | Medium | Applies only where **every** item in that menu is a gated mutation with no always-visible read action: `BucketHeaderActions`, `CorsRulesTable`, `LifecycleRulesTable`, `ObjectVersionHistoryModal`, and the deleted-item branches of `ObjectsTableView`'s row menu. Compute a `hasAnyAction` and render nothing when false. (The Buckets row menu and the normal-object row menu always keep "Show Details" / "Download Object" visible, so they can never go empty — no check needed there.) |
| Keystone roles ≠ Ceph/S3 authorization | Low (document) | This gating is UX-only; Ceph still enforces via EC2 creds/bucket policy. State it in the mapping doc comment; existing `AccessDenied` handling in `Ceph/Buckets/index.tsx:259` stays |

## Prerequisites

- [x] All open questions resolved during step-by-step review (see Decisions Made).
- [x] No external dependency; branch `kiryl-ceph-lifecycle-rules` is clean and already contains
      `lifecycleRouter`.

---

## Implementation Steps

### Step 1: Add the Ceph/S3 permission keys to `STORAGE_MAPPINGS`

**Files to modify:**
- `packages/aurora/src/server/Storage/routers/permissionRouter.ts`

**What to do:** Append these 11 entries (keep the existing 22 untouched), grouped with comments
in the file's current style. Every entry uses `engine: "storage"`.

| Permission key | `rule` |
| --- | --- |
| `storage:objects:share` | `storage:object_share` |
| `storage:object_versions:delete` | `storage:object_version_delete` |
| `storage:object_versions:restore` | `storage:object_version_restore` |
| `storage:containers:update_versioning` | `storage:container_versioning_update` |
| `storage:container_policies:update` | `storage:container_policy_update` |
| `storage:container_policies:delete` | `storage:container_policy_delete` |
| `storage:container_cors_rules:update` | `storage:container_cors_update` |
| `storage:container_cors_rules:delete` | `storage:container_cors_delete` |
| `storage:container_lifecycle_rules:update` | `storage:container_lifecycle_update` |
| `storage:container_lifecycle_rules:delete` | `storage:container_lifecycle_delete` |
| `storage:s3_credentials:create` | `storage:s3_credential_create` |

Naming rationale to put in the file header comment: resources stay plural snake_case and
backend-agnostic (`container_policies`, not `bucket_policies`/`s3_bucket_policies` — "container"
is used everywhere, matching the Swift-derived `containers` resource, never "bucket"); the
bucket-level versioning
*toggle* has no Swift analogue and stays on the `containers` resource with a compound action
(`update_versioning`), mirroring the existing `update_acls`. Also add a short note that these
checks are UX-only and Ceph independently enforces via EC2 credentials + bucket policy, and that
**read/list/view actions are deliberately not gated** (matches the rest of the app — see
`useSecurityGroupPermissions`, whose `canView` is fetched but never consumed for hiding).

⚠️ `storage:s3_credentials:delete` and every *read*-flavored variant of these 11 keys
(`object_versions:list`, `containers:read_versioning`, `container_policies:read`,
`container_cors_rules:read`, `container_lifecycle_rules:read`, `s3_credentials:list`) were
considered and deliberately **not** added —
see Decisions Made §2 and §4.

**Expected outcome:** `trpc.storage.canUser` accepts all 11 new keys; unknown keys still
`BAD_REQUEST`.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck`

---

### Step 2: Add the backing rules to the reference policy file

**Files to modify:**
- `apps/dashboard/src/policies/storage.json`

**What to do:** Add the 11 new rule names from Step 1's `rule` column, using only the two
existing roles. Keep the file's flat alphabetical-ish grouping style (append after the
`storage:folder_*` block):

- `rule:storage_viewer` → `storage:object_share`, `storage:s3_credential_create`
- `rule:storage_admin` → `storage:object_version_delete`, `storage:object_version_restore`,
  `storage:container_versioning_update`, `storage:container_policy_update`,
  `storage:container_policy_delete`, `storage:container_cors_update`, `storage:container_cors_delete`,
  `storage:container_lifecycle_update`, `storage:container_lifecycle_delete`

Do **not** add a `_default` rule (it would silently change behavior for every unknown rule across
the file).

**Verification:** `node -e "JSON.parse(require('fs').readFileSync('<path>','utf8'))"` plus Step
3's test.

---

### Step 3: ~~Add server tests for the Storage permission router~~ (removed 2026-08-25)

This step originally added `packages/aurora/src/server/Storage/routers/permissionRouter.test.ts`
(key-acceptance tests plus a real-file guard test resolving every `STORAGE_MAPPINGS` entry against
`storage.json`) and exported `STORAGE_MAPPINGS` from `permissionRouter.ts` to make that guard test
possible. Removed at the user's explicit request post-implementation — see Decisions Made §9. The
`export` on `STORAGE_MAPPINGS` was reverted to a plain `const` at the same time, since the test was
its only consumer.

---

### Step 4: Create the `useCephPermissions` hook

**Files to create:**
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/hooks/useCephPermissions.ts`
- ~~`.../Ceph/hooks/useCephPermissions.test.ts`~~ (removed 2026-08-25, see Decisions Made §9)

**What to do:**

1. Mirror `useSecurityGroupPermissions` exactly in shape: single
   `trpcReact.storage.canUser.useQuery({ project_id, permission: [...] }, { enabled:
   Boolean(projectId), select: ([...]) => ({...}), staleTime: Infinity, gcTime: Infinity })`,
   returning `{ permissions, isLoading, isError }`, with an **all-false default object** so a
   loading/errored query hides actions.
2. Export `interface CephPermissions` with **mutation-only** fields (order of the `permission`
   array must match the `select` destructuring — keep the array and destructuring adjacent and
   commented):

   `canCreateBucket` (`storage:containers:create`), `canDeleteBucket` (`…:delete`),
   `canEmptyBucket` (`…:empty`), `canUpdateVersioning` (`storage:containers:update_versioning`),
   `canCreateObject` (`storage:objects:create`), `canUpdateObject` (`…:update`),
   `canDeleteObject` (`…:delete`), `canCopyObject` (`…:copy`), `canMoveObject` (`…:move`),
   `canShareObject` (`storage:objects:share`), `canCreateFolder` (`storage:folders:create`),
   `canDeleteFolder` (`storage:folders:delete`), `canDeleteVersion`
   (`storage:object_versions:delete`), `canRestoreVersion` (`storage:object_versions:restore`),
   `canUpdatePolicy` (`storage:container_policies:update`), `canDeletePolicy` (`…:delete`),
   `canUpdateCors` (`storage:container_cors_rules:update`), `canDeleteCors` (`…:delete`),
   `canUpdateLifecycle` (`storage:container_lifecycle_rules:update`), `canDeleteLifecycle` (`…:delete`),
   `canCreateCredential` (`storage:s3_credentials:create`).

   No read/list/view/download field exists on this interface — those actions are never gated, so
   there is nothing to query for them.
3. `useProjectId()` throws outside a project route, so call it inside the hook exactly like
   `useSecurityGroupPermissions(projectId)`'s callers do — take `projectId` as an argument, don't
   call `useProjectId` in the hook, to keep it testable.
4. ~~Test: mock `@/client/trpcClient`, assert (a) all-false defaults when `data` is `undefined`,
   (b) `select` maps positionally to the right names using a distinguishable pattern (e.g. only
   index 3 true), (c) query disabled when `projectId` is empty.~~ (removed 2026-08-25, see
   Decisions Made §9)

**Expected outcome:** One cached permission query serves every Ceph screen, covering mutations
only.

---

### Step 5: Gate the Ceph Buckets list

**Files to modify:**
- `.../Ceph/Buckets/index.tsx` and `.../Ceph/Buckets/index.test.tsx`
- `.../Ceph/Buckets/BucketTableView.tsx` and `BucketTableView.test.tsx`

**What to do:**

1. In `Buckets/index.tsx`: call `useCephPermissions(projectId)`. **Delete the `TODO(perms)` block
   at lines 57-60** and replace with `const hasAnyBulkAction = permissions.canEmptyBucket` (Empty
   Buckets is the only bulk action today).
2. Hide the `Create Bucket` button (line 321) behind `permissions.canCreateBucket`. The Zone-1
   `Stack` must still render for the SortInput — hide only the `<Button>`.
3. Pass `canEmptyBucket` / `canDeleteBucket` into `<BucketTableView>`.
4. In `BucketTableView.tsx`: add required props `canEmptyBucket: boolean`, `canDeleteBucket:
   boolean`. In the row `PopupMenu` (lines 235-253) render `Empty Bucket` / `Delete Bucket`
   conditionally. `Show Details` is pure navigation — keep it always. (The menu therefore never
   becomes empty; no `hasAnyRowAction` needed here.)
5. Tests: `index.test.tsx` — `vi.mock` the `useCephPermissions` module and add cases for "create
   button hidden without permission" and "selection column dropped when `canEmptyBucket` false"
   (the mock `BucketTableView` already exposes `hasAnyBulkAction` indirectly — extend the mock to
   surface it as a `data-*` attribute). `BucketTableView.test.tsx` — pass the new props
   explicitly; add a case asserting both destructive items disappear.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets`

---

### Step 6: Gate the bucket detail header and versioning/policy actions

**Files to modify:**
- `.../Ceph/Buckets/BucketHeader.tsx`
- `.../Ceph/Buckets/BucketHeaderActions.tsx`

**What to do:**

1. `BucketHeader.tsx`: call `useCephPermissions(projectId)` (it already has `projectId` from
   `useParams`) and pass a `permissions` object (or discrete booleans) into
   `<BucketHeaderActions>`.
2. `BucketHeaderActions.tsx`: add props `canUpdateVersioning`, `canUpdatePolicy`,
   `canDeletePolicy`, `canEmptyBucket`, `canDeleteBucket`, `canDeleteVersions` (use
   `canDeleteVersion` from the hook). Wrap each existing conditional with the matching permission
   (versioning items ← `canUpdateVersioning`; `Add/Edit Policy` ← `canUpdatePolicy`; `Delete
   Policy` ← `hasPolicy && canDeletePolicy`; `Empty Bucket` ← `!isBucketEmpty && canEmptyBucket`;
   `Delete Versions` ← `hasOldVersionsOrDeleteMarkers && canDeleteVersions`; `Delete Bucket` ←
   `canDeleteBucket`).
3. ⚠️ Compute `hasAnyAction` from the same booleans and return `null` instead of the `PopupMenu`
   when nothing is available — this menu has no always-visible read item, so it can go fully
   empty for a read-only user.

CORS/Lifecycle tabs and bucket-config prefetch queries (`useBucketInfo`) are **not** touched by
this plan — those stay always-visible/always-enabled, consistent with reads never being gated
(see Decisions Made §4).

---

### Step 7: Gate the CORS Rules tab

**Files to modify:**
- `.../Ceph/Buckets/CorsRulesTab.tsx` and `CorsRulesTab.test.tsx`
- `.../Ceph/Buckets/CorsRulesTable.tsx` and `CorsRulesTable.test.tsx`

**What to do:**

1. `CorsRulesTab.tsx`: call `useCephPermissions(projectId)` (`projectId` already available via
   `useProjectId()`). The tab and its table always render — no read-permission check, no deep-link
   special-casing.
2. Hide `Create CORS Rule` (line 236) behind `canUpdateCors`. Gate the bulk-actions `Stack`
   (checkbox + Actions menu) behind `canDeleteCors`, rendering `<span />` in its place like
   `Buckets/index.tsx` does, so the rule count stays right-aligned.
3. `CorsRulesTable.tsx`: add `canUpdateCors`/`canDeleteCors` props; conditionally render the
   `Edit` and `Delete CORS Rule` items; drop the whole `PopupMenu` when neither is allowed (no
   always-visible item exists in this menu). Also gate the per-row selection checkbox on
   `canDeleteCors` for consistency with the toolbar.

---

### Step 8: Gate the Lifecycle Rules tab

**Files to modify:**
- `.../Ceph/Buckets/LifecycleRulesTab.tsx` (~~+ new colocated test~~ — a `LifecycleRulesTab.test.tsx`
  was created and then deleted at the user's explicit request, 2026-08-25; see Decisions Made §9)
- `.../Ceph/Buckets/LifecycleRulesTable.tsx` (~~+ new test~~ — same for `LifecycleRulesTable.test.tsx`)

**What to do:** Identical shape to Step 7 with `canUpdateLifecycle` / `canDeleteLifecycle` (no
read gate, tab always renders). ⚠️ Preserve the existing `mutationsBlocked`
(`skippedRuleCount > 0`) logic — the new permission booleans must be **AND**ed with it, never
replace it: `disabled={selectedIndices.length === 0 || mutationsBlocked}` becomes `... ||
mutationsBlocked` plus a permission-based hide of the surrounding control.

---

### Step 9: Gate the object browser toolbar

**Files to modify:**
- `.../Ceph/Objects/ObjectBrowserView.tsx` and `ObjectBrowserView.test.tsx`

**What to do:**

1. Call `useCephPermissions(projectId)`.
2. **Delete the `TODO(perms)` block at lines 96-98.** Replace with a tab-aware value:
   `const hasAnyBulkAction = tab === "deleted" ? permissions.canDeleteVersion :
   permissions.canDeleteObject`
   (the bulk action in the `deleted` tab deletes *versions*, in `all` it deletes objects — the
   current single hardcoded `true` conflates them).
3. Hide `Upload Object` (line 655) behind `canCreateObject`; hide `Create Folder` (line 658)
   behind `canCreateFolder`.
4. Pass the object-level booleans down to `<ObjectsTableView>` (Step 10).
5. The `Deleted` tab itself stays visible unconditionally (list/view is not gated).
6. Tests: extend the existing trpc/permission mocks; add cases for both tabs' bulk gating and both
   toolbar buttons.

---

### Step 10: Gate the object table row menu and version-history modal

**Files to modify:**
- `.../Ceph/Objects/ObjectsTableView.tsx` and `ObjectsTableView.test.tsx`
- `.../Ceph/Objects/ObjectVersionHistoryModal.tsx` and `ObjectVersionHistoryModal.test.tsx`

**What to do:**

1. `ObjectsTableView.tsx`: add required props `canCopyObject`, `canMoveObject`,
   `canUpdateObject`, `canShareObject`, `canDeleteObject`, `canDeleteFolder`, `canDeleteVersion`,
   `canRestoreVersion`. **`Download Object` and `View Versions` are not gated** — they always
   render, matching the "reads stay visible" convention.
2. Apply per branch of the existing menu (lines 592-731):
   - regular folder → `Delete Folder` ← `canDeleteFolder`
   - deleted folder → `Restore` ← `canRestoreVersion`, `Delete Folder` ← `canDeleteVersion` (it
     permanently deletes markers/versions, not a plain folder delete)
   - deleted file → `Restore` ← `canRestoreVersion`, `Delete Object` ← `canDeleteVersion`
   - normal object → `Download Object` (always visible), `View Versions` (always visible), `Copy
     Object` ← `canCopyObject`, `Move/Rename Object` ← `canMoveObject`, `Edit Object Metadata` ←
     `canUpdateObject`, `Share Object URL` ← `canShareObject`, `Delete Object` ← `canDeleteObject`
3. ⚠️ Extend the existing `shouldShowFolderMenu` IIFE into a `hasAnyRowAction` computed per row,
   but note it's now only reachable for the **deleted** folder/file branches (Restore + Delete
   Version are the only actions there, both gated, no always-visible item) — the normal-object
   branch always has Download + View Versions, so it can never go empty. Render nothing only when
   the deleted-branch computation is false.
4. `ObjectVersionHistoryModal.tsx`: add `canRestoreVersion` / `canDeleteVersion` props (threaded
   from `ObjectsTableView`), gate the two `PopupMenuItem`s, and skip the `PopupMenu` when neither
   applies (no always-visible item here either).
5. Tests: both files already have large suites that construct props — add the new required props
   to their fixture builders (one place each) plus 2-3 focused cases (viewer sees only
   Download/View Versions on a normal row; `canShareObject: false` hides `share-url-action-*`;
   `canDeleteObject: false` hides delete but keeps download). ⚠️ For
   `ObjectVersionHistoryModal.test.tsx`, the required-prop fixture update (`defaultProps.canRestoreVersion`
   / `canDeleteVersion`) must stay — the component won't typecheck without it — but its dedicated
   `describe("Permission gating")` block (4 tests) was removed at the user's request, 2026-08-26;
   see Decisions Made §9.

---

### Step 11: Gate EC2 credential creation with explicit feedback

**Files to modify:**
- `.../Ceph/Buckets/CredentialPrompt.tsx` and `CredentialPrompt.test.tsx`

**What to do:**

1. Call `useCephPermissions(projectId)`.
2. When `permissions.canCreateCredential` is false, **replace the button** with a Juno `<Message
   variant="info">` telling the user they lack permission to create S3 credentials and should ask
   an administrator — this is the one screen where a bare hide leaves a dead end (no button, no
   explanation, no buckets). This satisfies the epic's "show insufficient permissions feedback"
   without inventing a new component for cases where the existing hide convention is enough.
3. Keep the existing `disabled={createMutation.isPending || !projectId}` behavior intact for the
   permitted case.

---

### Step 12: Docs, i18n, changeset, and final checks

**Files to modify:**
- `PERMISSION_KEY_PATTERN.md` — extend the "Storage (`storage:*`)" section with the 11 new keys,
  and add a one-line note that read/list/view actions are deliberately not gated in this domain
  (or anywhere else in the app). Do **not** attempt to fix the file's other stale claims (`.yaml`
  filenames, `swift:`/`ceph:` split) in this PR — out of scope, and mixing it in makes review
  harder.
- `.changeset/<new-file>.md` — `@cobaltcore-dev/aurora`: `minor`. Body must state: (a) which 11
  Ceph mutation actions are now gated; (b) that operators must add the corresponding rules to
  their `storage.json` (rule names listed) or those specific actions will render hidden — no
  crash, no server error, just conservative/fail-closed until the policy file is updated.

**What to do:** run `pnpm check-i18n` (new `Trans`/`t` strings in Steps 7, 8, 11),
`pnpm --filter @cobaltcore-dev/aurora typecheck`, `pnpm --filter @cobaltcore-dev/aurora lint`,
`pnpm --filter @cobaltcore-dev/aurora test`, `pnpm format:check`.

Commit style: `feat(aurora): gate Ceph S3 mutations behind storage permission checks` (`aurora` is
an allow-listed scope in `commitlint.config.mjs`).

---

## Testing Plan

**Unit tests (server):**

- [x] ~~`buildStoragePermissionRouter`: each of the 11 new keys accepted; unknown key ⇒
      `BAD_REQUEST`; `boolean[]` shape and length; empty array ⇒ `[]`~~ (removed 2026-08-25,
      see Step 3 / Decisions Made §9)
- [x] ~~Guard test: every mapping in `STORAGE_MAPPINGS` resolves against the real
      `apps/dashboard/src/policies/storage.json`~~ (removed 2026-08-25, see Step 3 / Decisions Made §9)

**Unit tests (client):**

- [x] ~~`useCephPermissions`: all-false default while loading/errored; positional `select` mapping
      correctness; query disabled without `projectId`~~ (removed 2026-08-25, see Decisions Made §9)
- [ ] Per component (mock `useCephPermissions`): admin sees every action; viewer sees only reads
      plus whatever mutations their role grants; no empty `PopupMenu` ever renders where every item
      in it is gated (assert the toggle itself is absent, not just the items)
- [ ] `ObjectBrowserView`: bulk gating differs between `tab="all"` (`canDeleteObject`) and
      `tab="deleted"` (`canDeleteVersion`)
- [ ] `ObjectsTableView`: a viewer with no mutation permissions still sees `Download Object` and
      `View Versions` on a normal row (proves reads are never accidentally gated)
- [ ] `CredentialPrompt`: create-denied renders the explanatory `Message` and no button

**Integration/regression:**

- [ ] Existing Ceph suites (28 files) still pass — in particular the ones whose
      `vi.mock("@/client/trpcClient")` is a narrow object; confirm no component reaches
      `storage.canUser` outside `useCephPermissions`

**Manual verification:**

1. `pnpm dev`, log in as a user with `objectstore_admin` (or `admin`) in the project → every Ceph
   mutation visible and functional.
2. Temporarily edit `apps/dashboard/src/policies/storage.json` so `storage_admin` is `!` (or log
   in as an `objectstore_viewer`-only user) → Buckets list still renders fully, `Create Bucket`
   gone, row menu shows only `Show Details`, object rows still show `Download`/`View Versions` but
   lose Copy/Move/Edit/Share/Delete, CORS + Lifecycle tabs still render (with only their tables
   visible, no Create/Edit/Delete), `CredentialPrompt` still works (viewer role).
3. Backward-compat check: temporarily remove the 11 new rules from `storage.json`, restart → **no
   500 on `storage.canUser`**, the 11 new mutation controls are hidden (fail-closed, no console
   spam, no toast), everything else behaves exactly as before this PR.

## Acceptance Criteria

- [ ] All Ceph S3 mutating actions in scope (buckets, objects, folders, versions, bucket policy,
      CORS, lifecycle, EC2 credential creation) are gated by a `storage.canUser` result; nothing
      renders a permanently-dead control
- [ ] Read/list/view/download actions are never gated, anywhere in this change
- [ ] Both Ceph `TODO(perms)` markers are removed and replaced by real permission sources; the two
      Swift markers are untouched
- [ ] No server-side enforcement middleware added to any Ceph procedure (client-side only,
      consistent with Compute/Network/Swift)
- [ ] EC2 credential creation remains available to read-only object-storage users
- [ ] No empty `PopupMenu` renders for any permission combination
- [ ] Insufficient-permission feedback exists on the one dead-end surface (credential creation
      denial); everywhere else follows the existing hide-the-action convention
- [ ] `pnpm --filter @cobaltcore-dev/aurora typecheck | lint | test` pass, plus `pnpm check-i18n`
      and `pnpm format:check`
- [ ] Changeset added (`minor`, `@cobaltcore-dev/aurora`) documenting the required `storage.json`
      additions and the fail-closed behavior for operators who haven't added them yet

---

## Decisions Made (step-by-step review, 2026-08-21 → 2026-08-24)

The plan was originally drafted with 18 new permission keys and a `fallbackRule` mechanism. Both
were substantially revised after review with the user. Recorded here for anyone reading this plan
later and wondering why it doesn't match a first-draft instinct:

1. **No `fallbackRule` mechanism.** The original draft proposed an optional `fallbackRule` field
   on `PolicyMapping` so operators with an out-of-date `storage.json` wouldn't get a crash. Checked
   git history for both `Compute` and `Network` permission routers — neither has ever needed
   anything like this when adding keys, and no `_default` rule convention exists anywhere in the
   policy files either. Rejected as a novel abstraction with no precedent. It turned out to be
   unnecessary anyway: `checkSinglePermission` throwing on a missing rule already degrades
   gracefully through `useCephPermissions`'s existing all-false default (query error ⇒ `data` is
   `undefined` ⇒ same code path as "still loading"), and there's no global `onError` toast wired to
   the tRPC query client. Zero new server code required.
2. **Reads/lists/views are never gated — only mutations.** Verified against the codebase's own
   reference pattern: `SecurityGroupTableRow.tsx` accepts a `canView` permission (from
   `network:security_groups:read`) but never uses it in any conditional — "Show Details" always
   renders. This is the established, if implicit, design convention: RBAC differentiates who can
   change things, not who can see things (Keystone project membership already gates access to the
   page at all). This dropped 7 of the original 18 keys entirely
   (`storage:object_versions:list`, `storage:containers:read_versioning`,
   `storage:container_policies:read`, `storage:container_cors_rules:read`,
   `storage:container_lifecycle_rules:read`,
   `storage:s3_credentials:list`) and removed all "hide tab / show insufficient-permissions
   message on read-denial" logic from Steps 6-8 and 10 of the original draft, including the
   `?view=cors-rules` deep-link mitigation (no longer applicable — there's nothing to bypass).
3. **Hide, not disable — confirmed, no change from original recommendation.** Matches
   `useSecurityGroupPermissions`'s consumers; Compute Flavors/Images disable instead, but making
   the whole repo consistent one way or the other is out of scope for this plan.
4. **`storage:s3_credentials:delete` deferred, not defined now.** Original draft defined it
   "for completeness" despite noting no UI consumer existed. On review: grepped the entire client
   tree and confirmed `ec2CredentialRouter.delete` has **zero** callers anywhere in the dashboard —
   there is currently no way to delete an S3 credential through the UI at all. Defining a
   permission key for an action nobody can trigger has nothing to gate, test, or document. Add it
   alongside whichever future PR actually builds that UI.
5. **`storage:objects:share` → `rule:storage_viewer`.** No behavior change versus today (currently
   fully ungated); capability-equivalent to a normal download, so restricting it to admin would be
   a real capability regression for viewers.
6. **Leaf-component permission props are required, not optional-with-default.** `pnpm typecheck`
   surfaces every call site that needs updating; the one-time cost is updating fixtures in ~8
   existing test files, in exchange for not silently failing open if a future caller forgets to
   pass a prop.
7. **`useCephPermissions`'s `CephPermissions` interface has no read fields.** Follows directly from
   §2 — there was never any existing gating to remove (the hook doesn't exist yet; this whole plan
   is what creates it for the first time), so the interface was simply never given fields for
   actions this plan doesn't gate.
8. KB (`../DOCS/aurora-dashboard-kb/`) was pinned at `35095b4` as of the original draft date; its
   permissions section will need an `update-kb` pass after this lands, same as noted originally.
9. **Both new test files removed post-implementation (2026-08-25), at the user's explicit
   request, after the plan had already been implemented and reviewed clean:**
   - `packages/aurora/src/server/Storage/routers/permissionRouter.test.ts` (Step 3) — including
     its highest-value real-file guard test, which resolved every `STORAGE_MAPPINGS` entry against
     the real `storage.json`. The `export` added to `STORAGE_MAPPINGS` solely to make that guard
     test possible was reverted to a plain `const` in the same pass, since nothing else in the
     codebase consumed the export.
   - `.../Ceph/hooks/useCephPermissions.test.ts` (Step 4, item 4) — the hook's own unit tests
     (all-false default, positional `select` mapping, `enabled: Boolean(projectId)`).
   - `.../Ceph/Buckets/LifecycleRulesTab.test.tsx` and `LifecycleRulesTable.test.tsx` (Step 8) —
     unlike the two files above, these covered more than just permission gating: loading spinner,
     error state, empty state, opening the add-rule modal, rendering multiple rules, table
     headers, row action-menu rendering, and `isMutating` behavior, in addition to their
     `describe("Permission gating")` blocks. Neither file existed before this plan created them
     (confirmed via `git log` — no history, `??` in `git status`); deleting them leaves
     `LifecycleRulesTab`/`LifecycleRulesTable` with **zero** automated test coverage of any kind,
     unlike `CorsRulesTab`/`CorsRulesTable`, whose pre-existing test files were only extended (and
     therefore retain their non-permission coverage).
   - `.../Ceph/Objects/ObjectVersionHistoryModal.test.tsx`'s `describe("Permission gating")` block
     (Step 10, item 5) — removed 2026-08-26, at the user's request, but narrower than the three
     items above: this file **already existed** before this plan and the diff was purely additive
     (+37 lines, 0 deletions), so only the 4 new tests were removed. The `canRestoreVersion: true,
     canDeleteVersion: true` added to `defaultProps` in the same original diff were **kept** —
     `ObjectVersionHistoryModal.tsx`'s props interface requires both as non-optional booleans, so
     removing them from the shared fixture would break every pre-existing test in the file at
     typecheck time, not just the permission-specific ones.

   Net effect: neither the server-side mapping-to-policy-file wiring nor the client-side hook's
   query/mapping logic has dedicated automated coverage anymore, the Lifecycle Rules tab has no
   test coverage at all, and the version-history modal's permission gating is untested (though its
   pre-existing non-permission tests are intact). These classes of regression (a `storage.json`
   rule renamed without updating `permissionRouter.ts` or vice versa; a broken positional `select`
   mapping silently shifting which boolean means what; a Lifecycle Rules UI regression of any kind;
   Restore/Delete showing for a version-history row that shouldn't have it) are now only caught by
   manual review or transitively by the ~40 Ceph component test files that mock
   `useCephPermissions` and therefore never exercise its real implementation.
