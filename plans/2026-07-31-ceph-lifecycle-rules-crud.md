# Plan: Ceph S3 lifecycle rules (epic #608, Section 13) — full CRUD + UI

**Date:** 2026-07-31 · **Last updated:** 2026-08-05 · **Status:** implemented 2026-08-06

> **Executor: read this before doing anything.** This plan was originally sequenced strictly after
> CORS (epic Section 12, issue #1066, PR #1092) merged to `main`. **That hard gate was lifted on
> 2026-08-05**: PR #1092 is still open/unmerged, but its UI and schema design have matured enough
> (a UX/validation refactor landed 2026-08-05) to build against directly as a reference — see "CORS
> reference status" below for exactly what's confirmed vs. still in flux. **Before opening a PR for
> this plan, diff the actual `main` state of the `Cors*` files against what's described here** — PR
> #1092 can still change before it merges, and this plan's concrete details (Steps 8–9) are frozen to
> the 2026-08-05 snapshot, not to whatever eventually lands.

**Note:** this is distinct from the existing 2026-07-23 plan
[`2026-07-23-ceph-lifecycle-policies-endpoint.md`](./2026-07-23-ceph-lifecycle-policies-endpoint.md)
(already implemented), which added a read-only `storage.ceph.lifecyclePolicy.list` endpoint
aggregating lifecycle configs across all buckets in a project for a table view. This plan covers
epic Section 13 itself: per-bucket `get`/`set`/`delete` on `storage.ceph.lifecycle` plus an
add/edit/delete rule-list UI, per the epic checklist.

# 📋 IMPLEMENTATION PLAN: Ceph S3 Lifecycle Rules (Epic #608, Section 13)

## Overview

Add bucket-level S3 Lifecycle configuration to the Ceph/S3 integration: a Zod-validated `storage.ceph.lifecycle.{get,set,delete}` tRPC namespace on the BFF, plus a rule-list UI (view / add / edit / delete) reachable from the bucket detail page. The implementation mirrors the two shipped bucket sub-resource features (`bucketPolicyRouter`, `versioningRouter`) and the CORS work on `origin/kiryl-ceph-cors` (PR #1092, issue #1066), used here as a **live reference, not a blocking prerequisite** (see below).

---

## CORS reference status (re-verified 2026-08-05, gate lifted)

Section 13 (this plan) and Section 12 (CORS, issue #1066 / PR #1092) are siblings that touch the same
files: `types/ceph.ts`, `s3ErrorMapper.ts`, `routers/ceph/index.ts`, `routers/index.ts`,
`BucketModals.tsx`, `BucketHeaderActions.tsx`, `BucketHeader.tsx`, `useBucketInfo.ts`,
`BucketToastNotifications.tsx`, both `messages.po` catalogs, and `mockContext.ts`. This plan was
originally blocked entirely on CORS merging first (decision of 2026-07-31). **That block was lifted
2026-08-05**: the branch has matured enough (a UX/validation refactor commit landed today) that its
patterns can be treated as a reliable reference for building lifecycle now, in parallel, rather than
waiting for the actual GitHub merge.

**State as re-verified 2026-08-05:**

- PR #1092 is `OPEN`, **no longer `draft`**, `mergedAt: null`, `reviewDecision: REVIEW_REQUIRED` — still not merged, no human approval yet, but active: today's commits are `feat(aurora): add Ceph bucket CORS configuration management` (2026-08-04), `refactor(aurora): improve CORS modal UX and form validation` (2026-08-05), and a CodeQL string-escaping fix (2026-08-05). A fresh full CodeRabbit review was triggered today and hadn't reported back at time of writing.
- **The primary-button design question (previously `TBC`) is resolved in code**: the modal footer's `Save` button is always `variant="primary"` (disabled until `hasChanges`); the empty-state and list-view "Add New Rule"/"Add Rule" buttons are *also* `variant="primary"` — i.e. each view has its own primary CTA, not one primary button shared across all states. Applied to lifecycle's `LifecycleModal`/`LifecycleRuleForm` in Step 8 below.
- **The CodeRabbit read/write schema-validation bug is fixed**: `corsRouter.get` now parses through a separate, more permissive `corsRuleReadSchema` (comment: *"accept rules with values outside write-time constraints"*), while `set` validates against the strict write schema (`CorsRule`/`corsRuleSchema`). This confirms the split already designed into this plan's `lifecycleMapper.ts` (Step 4) is the right call — apply the same read/write separation there, don't parse `get` output through the strict schema.
- **Entry-point placement is confirmed, not just precedent**: `BucketHeaderActions.tsx` still has `Policy` and `CORS` as two separate standalone header buttons (`variant="subdued"`, `Edit/View X` / `Add X`), with `Delete Policy`/`Delete CORS` in the "..." `PopupMenu`. This is no longer just "CORS's current WIP guess" — it survived today's UX refactor commit unchanged. Open Question 6 is resolved on this basis (see below, Step 9 updated accordingly).
- **`CorsRulesViewer.tsx` has no "Delete All Rules" button** — contrary to an earlier assumption in this plan's Step 8. Deleting the *entire* configuration is only reachable via the separate `DeleteCorsModal` (opened from the header's "..." menu → "Delete CORS"), which itself queries `get` first and shows a warning if nothing is configured. The in-modal rule list only supports per-rule edit/delete plus one "Add New Rule" button at the top; the whole array is written or wiped only via the modal's single "Save" (or the separate delete modal). **Step 8's `LifecycleRulesViewer` spec below is corrected to match — no footer "Delete All Rules" button.**
- **Still no UI tests** for any `Cors*` component — only `corsRouter.test.ts` (server-side, ~515 lines). This gap persisted through today's refactor. Lifecycle should still not repeat it (Step 11 stands as written).
- `mockContext.ts` (shared Ceph router test context) picked up two new fields (`res`, `signal`) in the CORS branch — `lifecycleRouter.test.ts` (Step 7) automatically inherits these by using the shared `createMockContext()` as-is; no separate action needed, just don't hand-roll a context object.

**What this means going forward:** proceed with implementation using the concrete details in Steps 1–12 below — they've been refreshed against the 2026-08-05 snapshot. The one remaining risk is that PR #1092 itself could still change again before *it* merges (no human review yet). **Before submitting lifecycle's own PR, re-diff `Cors*`/`BucketHeaderActions.tsx` against whatever is on `main` at that point** — if CORS merged with further changes, reconcile; if it still hasn't merged, lifecycle can ship independently since both branch off `main` and touch these shared files only in additive/append regions (conflicts resolve normally at whichever PR merges second).

---

## Architecture Analysis

### Current state (verified by reading, not inferred from the epic)

**Server**

- Procedure builder is `cephProtectedProcedure` from `packages/aurora/src/server/Storage/cephProcedure.ts`. It is `projectScopedProcedure` + a middleware that resolves EC2 credentials via `resolveEC2Credential(ctx)`, derives the RGW S3 endpoint from the OpenStack catalog (`ctx.openstack.service("ceph")`, stripping the `/swift/` suffix) and exposes `ctx.getCephClient(): S3Client`. There is **no** `CredentialService`/`credentialCache`/generic `protectedProcedure` as the epic body sketches — ignore those snippets.
- Bucket sub-resource routers are **plain objects** (not `auroraRouter(...)` calls); they are spread into namespaces in `packages/aurora/src/server/Storage/routers/index.ts` inside `buildObjectStorageRouters(policyDir)` → `storage.ceph.{containers,objects,versioning,bucketPolicy,ec2Credentials}`.
- Zod schemas for bucket policy live in `packages/aurora/src/server/Storage/types/ceph.ts` (versioning has its own `types/versioning.ts`). All input schemas extend `projectScopedInputSchema` and use `existingBucketNameSchema` (permissive, 1–255 chars) for existing buckets.
- Error convention: `mapS3ErrorToTRPCError(error, { operation, bucket, key? })` from `packages/aurora/src/server/Storage/helpers/s3ErrorMapper.ts`, with "absence is not an error" special-casing done **before** the mapper call (`NoSuchBucketPolicy` → `{policy: null}` on get, → `true` on delete).
- No tRPC data transformer is configured (checked `trpcClient.ts` / `server/trpc.ts`) — **`Date` cannot cross the wire**; existing code ships ISO strings (`v.LastModified!.toISOString()`).
- `@aws-sdk/client-s3@3.1042.0` provides `GetBucketLifecycleConfigurationCommand`, `PutBucketLifecycleConfigurationCommand`, `DeleteBucketLifecycleCommand`, and the `LifecycleRule` model (`Expiration`, `Filter`, `Status`, `Transitions`, `NoncurrentVersionTransitions`, `NoncurrentVersionExpiration`, `AbortIncompleteMultipartUpload`, deprecated top-level `Prefix`).

**Client**

- The epic's `/storage/s3/buckets/:name/lifecycle` route base is **stale**. The real tree is `/_auth/projects/$projectId/storage/$provider/$storageType` (bucket list) and `/_auth/projects/$projectId/storage/$provider/$storageType/$containerName/objects` (bucket detail / object browser). There is no per-bucket settings route — **bucket policy and versioning are modals** opened from `BucketHeader` → `BucketHeaderActions` → `BucketModals` (`ModalType` union), fed by the `useBucketInfo` hook.
- Modal conventions: Juno `Modal`, `useProjectId()`, `useModalTracking({ isOpen, actionPrefix })`, `trpcReact.*.useQuery/useMutation` + `utils.*.invalidate()`, toasts built by factory functions in `BucketToastNotifications.tsx` and fired by `BucketModals`, forms via `@tanstack/react-form` + `useStore`, all strings wrapped in Lingui `<Trans>`/`` t`` ``.
- A key/value row editor already exists to copy for tag filters: `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/EditMetadataModal.tsx`.

**CORS (Section 12, issue #1066) — PR #1092 on `origin/kiryl-ceph-cors`, live reference (not a blocker), see "CORS reference status" above**

4 commits + a main-sync merge + today's refactor, 17 files under Storage/storage-UI, still `OPEN`/unmerged as of 2026-08-05 but functionally mature — the design question and schema bug that made this plan wait are both resolved in the branch now (see above). Concrete pattern to copy:

- `corsRouter.ts` next to the other ceph routers; schemas appended to `types/ceph.ts`; mounted as `storage.ceph.cors`; `NoSuchCORSConfiguration`/`MalformedXML` added to `s3ErrorMapper.ts`; a `corsRuleReadSchema` (lenient) used only in `get`, distinct from the strict write schema used in `set`.
- Rate limiting reappeared: `checkCorsSetRateLimit` — an in-memory `Map<string, {count, resetAt}>` capping `set` at 10 calls/minute per bucket, same shape as `bucketPolicyRouter`'s `checkPolicySetRateLimit`. **This plan's Step 5 currently tells the executor not to copy that pattern — now that it appears in two sibling routers (policy, CORS), that guidance needs a decision; see the open follow-up question below, don't silently resolve it either way.**
- UI: `CorsModal.tsx` (state-machine `ViewState.EMPTY | LIST | FORM` rather than a tab enum, **local `currentRules` state**, footer "Save" always primary + "Cancel", PUTs the whole array or DELETEs when empty), `CorsRulesViewer.tsx` (top "Add New Rule" primary button + per-rule cards with edit/delete icon buttons only — **no "Delete All Rules" footer**, that's a separate top-level modal), `CorsRuleForm.tsx`, `DeleteCorsModal.tsx` (separate, queries `get` first, whole-config wipe only), `TagInput.tsx` (string-list pill input, survived to today), plus two standalone header buttons (Policy, CORS) + badge + `useBucketInfo.corsData`.
- Notably it still ships **server tests only** (`corsRouter.test.ts`, ~515 lines) and **no UI tests** — lifecycle should not repeat that gap (Step 11 stands).
- Note: a related testing plan already exists for CORS referencing PR #1092 — [`2026-07-25-cors-configuration-testing-plan.md`](./2026-07-25-cors-configuration-testing-plan.md).

**Permissions**

`buildStoragePermissionRouter` (`packages/aurora/src/server/Storage/routers/permissionRouter.ts`) maps only `storage:containers:*`, `storage:objects:*`, `storage:folders:*`. **There are no permission keys for bucket policy, versioning or CORS**, `apps/dashboard/src/policies/storage.json` has no lifecycle rules, and `storage.canUser` is not called anywhere in the client (grep: only `network.canUser` / `compute.canUser` are used). So epic §15 is *not* actually satisfied for bucket sub-resources today — **this is known, out of scope for the present task, and will be addressed by a separate dedicated task covering permissions for the entire Ceph/S3 storage surface at once (decided 2026-07-31; see Step 10).**

### Proposed changes

1. `types/ceph.ts`: lifecycle Zod schemas (rule, filter, expiration, noncurrent expiration, abort-MPU, read-only transitions) + config schema with cross-field `superRefine` validation.
2. New `helpers/lifecycleMapper.ts`: pure conversion between the wire shape (ISO date strings) and the AWS SDK shape (`Date` objects), plus filter normalization (`Prefix`/`Tag`/`And`). Unit-testable without S3.
3. New `routers/ceph/lifecycleRouter.ts` with `get`/`set`/`delete` on `cephProtectedProcedure`, mounted as `storage.ceph.lifecycle`.
4. Client: `LifecycleModal` / `LifecycleRulesViewer` / `LifecycleRuleForm` / `DeleteLifecycleModal` in the Ceph `Buckets/` folder, wired through `ModalType`, `BucketHeaderActions`, `BucketHeader` badge and `useBucketInfo`. **Entry point confirmed 2026-08-05: a third standalone header button** (`Edit/View Lifecycle Rules` / `Add Lifecycle Rules`), matching the surviving Policy/CORS pattern — see Step 9.
5. Transitions are **read-and-preserve only, never authored in the UI** (see Open Question 1).

---

## Potential Problems & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| 🔴 `PutBucketLifecycleConfiguration` **replaces the entire configuration**. If Aurora drops fields it doesn't model (transitions, object-size filters, legacy top-level `Prefix`), saving one edited rule silently destroys config authored via `aws-cli`/Terraform. | High | Schema models **every** RGW-relevant `LifecycleRule` field, including `Transitions`/`NoncurrentVersionTransitions`/`ObjectSize*`; the modal always writes back the full `currentRules` array derived from what `get` returned; viewer shows non-editable fields read-only with a "managed outside Aurora" note; a round-trip test (`get` output → `set` input) asserts no field loss. |
| 🔴 Lost update: two users editing lifecycle concurrently; S3 has no ETag/If-Match for lifecycle. | High | On submit, refetch `lifecycle.get` and compare against the snapshot captured on modal open; if changed, block save and show a "configuration changed, reload" `Message`. (Cheap; the CORS branch has no equivalent — this is a deliberate improvement.) |
| 🔒 Lifecycle rules are *automated deletion*. A rule with an empty prefix + `Expiration.Days: 1` silently destroys a whole bucket. | High | Viewer shows a prominent warning card for any Enabled rule whose filter matches the whole bucket **and** has a current-version `Expiration` (mirrors the CORS wildcard-origin warning); the rule form defaults `Status` to `Disabled`; `DeleteLifecycleModal` and the save path list the affected rules. |
| ⚠️ SDK v3 flexible checksums: `PutBucketLifecycleConfiguration` is a checksum-required op; SDK ≥3.729 sends `x-amz-checksum-crc32` instead of `Content-MD5`. Older RGW builds reject or require MD5. | Medium | Verify manually against the real RGW before merging. If it fails, pass `ChecksumAlgorithm: "CRC32"`/`"MD5"` on the *command* — do **not** change `requestChecksumCalculation` on the shared `createS3Client` (that would affect every S3 op including uploads). |
| ⚠️ RGW processes lifecycle asynchronously (typically once daily); nothing happens immediately after save. | Medium | Explicit help text in the viewer: "Rules are evaluated by the storage backend on its own schedule (typically once per day); expiration is not immediate." |
| ⚠️ Invalid combinations that S3/RGW reject with an opaque `MalformedXML`: `Days` + `Date` together, `ExpiredObjectDeleteMarker` + `Days`/`Date`, `ExpiredObjectDeleteMarker` + tag filter, `Filter` + top-level `Prefix`, rule with zero actions, duplicate rule IDs, `And` with fewer than 2 predicates. | Medium | Encode all of these as `superRefine` checks so the user gets a field-level BAD_REQUEST, not `MalformedXML`. Add `MalformedXML` and `InvalidArgument` to `s3ErrorMapper.ts` as a backstop. |
| 🟡 Building lifecycle before CORS's own PR #1092 merges means both branches touch `types/ceph.ts`, `s3ErrorMapper.ts`, `routers/ceph/index.ts`, `routers/index.ts`, `BucketModals.tsx`, `BucketHeaderActions.tsx`, `BucketHeader.tsx`, `useBucketInfo.ts`, `BucketToastNotifications.tsx`, both `messages.po` files, and `mockContext.ts` — and PR #1092 could still change again before it merges (no human review yet as of 2026-08-05). | Medium (downgraded from High 2026-08-05, once the design/schema questions that were the real risk got resolved in the branch) | Branch lifecycle off `main` now, following the 2026-08-05 CORS snapshot described above; append changes to shared files rather than restructuring them, so a conflict — if CORS merges first with further edits — resolves as a normal merge conflict, not a redesign. Before opening lifecycle's own PR, re-diff the `Cors*` components and `BucketHeaderActions.tsx` against current `main` and reconcile any drift. |
| ⚠️ `useBucketInfo` already issues 4 queries per bucket-detail load; lifecycle makes 5 (6 with CORS). | Low | `staleTime: 5 * 60 * 1000`, `retry: false`, matching the policy/CORS queries. Do not add it to the bucket **list** page. |
| ⚠️ `Expiration.Date` is a JS `Date` in the SDK but cannot cross tRPC (no transformer). | Medium | Wire type is an ISO-8601 string; `lifecycleMapper` converts both directions and normalizes to midnight UTC (AWS requires it; RGW tolerates but normalizing keeps parity). |
| ⚠️ Legacy v1 rules from RGW may come back with top-level `Prefix` and no `Filter`. | Low | Schema accepts top-level `Prefix`; mapper migrates it into `Filter.Prefix` **only when the user edits that rule**, and never emits both. |

---

## Prerequisites

- [x] **Decision: transitions in or out of scope** (was Open Question 1, decided 2026-07-31: **out** — read-only preservation, never authored in the UI. See Step 1's `lifecycleTransitionSchema` and Step 8's read-only rendering).
- [x] **CORS sequencing** (was Open Question 2, decided 2026-07-31: wait for CORS to merge; **revised 2026-08-05: gate lifted**, build now against the mature-but-unmerged CORS branch as a live reference — see "CORS reference status" above; re-diff before submitting lifecycle's own PR).
- [x] **Decision: permission keys** (was Open Question 3, decided 2026-07-31: **skip entirely** — a dedicated future task will retrofit permissions across all of Ceph/S3 storage at once; see Step 10, now marked SKIPPED).
- [ ] **New (2026-08-05): decide whether `lifecycleRouter`'s `set` gets a rate limiter** matching the pattern now used by both `bucketPolicyRouter` and (as of today) `corsRouter` — see the CORS reference status note above and Step 5. Not yet decided; do not silently pick either option.
- [ ] Access to a project with EC2 credentials and a real Ceph RGW bucket for manual verification (`pnpm dev`, `IDENTITY_ENDPOINT` + `CEPH_REGION` in `apps/dashboard/.env`).
- [ ] A GitHub sub-issue for Section 13 (none exists) — create it mirroring #1066's format so the PR can reference it.

---

## Implementation Steps

### Step 1: Define the lifecycle Zod schemas

**Files:**
- `packages/aurora/src/server/Storage/types/ceph.ts` — append a new `LIFECYCLE CONFIGURATION SCHEMAS` section at the end of the file (after the bucket-policy types), following the section-banner comment style already used there.

**What to do:**

1. Add leaf schemas:
   - `lifecycleRuleStatusSchema = z.enum(["Enabled", "Disabled"])`
   - `lifecycleTagSchema = z.object({ Key: z.string().min(1).max(128), Value: z.string().max(256) })`
   - `lifecycleExpirationSchema = z.object({ Days: z.number().int().positive().optional(), Date: z.string().datetime().optional(), ExpiredObjectDeleteMarker: z.boolean().optional() })` with a `superRefine` requiring **exactly one** of the three to be set.
   - `noncurrentVersionExpirationSchema = z.object({ NoncurrentDays: z.number().int().positive(), NewerNoncurrentVersions: z.number().int().positive().max(100).optional() })`
   - `abortIncompleteMultipartUploadSchema = z.object({ DaysAfterInitiation: z.number().int().positive() })`
   - `lifecycleTransitionSchema` / `noncurrentVersionTransitionSchema` — permissive (`Days`/`Date`/`NoncurrentDays`/`NewerNoncurrentVersions` optional, `StorageClass: z.string().optional()`); documented in a JSDoc block as **read-only passthrough, preserved on round-trip, not authored by the UI**.
2. Add `lifecycleFilterSchema`: `{ Prefix?, Tag?, ObjectSizeGreaterThan?, ObjectSizeLessThan?, And?: { Prefix?, Tags?: Tag[], ObjectSizeGreaterThan?, ObjectSizeLessThan? } }` with a `superRefine` enforcing exactly one top-level predicate group and `And` having ≥ 2 predicates.
3. Add `lifecycleRuleSchema` (`ID?` max 255, `Status` required, `Filter?`, `Prefix?` legacy, `Expiration?`, `NoncurrentVersionExpiration?`, `AbortIncompleteMultipartUpload?`, `Transitions?`, `NoncurrentVersionTransitions?`) with `superRefine` enforcing:
   - at least one action present;
   - not both `Filter` and top-level `Prefix`;
   - `Expiration.ExpiredObjectDeleteMarker` not combined with a `Tag`/`And.Tags` filter.
4. Add `lifecycleConfigurationSchema = z.object({ Rules: z.array(lifecycleRuleSchema).min(1, ...).max(100, ...) })` with a `superRefine` rejecting duplicate non-empty `ID`s. **Cap is 100, not the AWS/RGW technical maximum of 1000** (decided 2026-07-31, matching the CORS sibling's own rule-count cap) — this is a UI-sanity limit for a manual add-one-at-a-time rule editor, not the real enforceable backend limit. RGW's actual per-deployment cap is the cluster-configurable `rgw_lc_max_rules` (default 1000, admin-settable, not discoverable via S3 API), so this client-side `max()` cannot and does not guarantee the request will be accepted — a config with ≤100 rules can still be rejected by RGW if an admin lowered `rgw_lc_max_rules` further, and that case is handled like any other S3 error via the existing `mapS3ErrorToTRPCError` path, not by this schema.
5. Add IO schemas, matching the CORS/policy naming exactly:
   - `getLifecycleInputSchema` / `setLifecycleInputSchema` (`+ lifecycleConfiguration`) / `deleteLifecycleInputSchema`, all `projectScopedInputSchema.extend({ bucketName: existingBucketNameSchema, ... })`
   - `getLifecycleOutputSchema = z.object({ rules: z.array(lifecycleRuleSchema).nullable() })`
6. Export inferred types: `LifecycleRule`, `LifecycleFilter`, `LifecycleExpiration`, `LifecycleConfiguration`, `GetLifecycleOutput`, `LifecycleTag`.

> ⚠️ Name the exported type `LifecycleRule` carefully — `@aws-sdk/client-s3` exports a type with the same name. Do not import both into one module without aliasing.

**Expected outcome:** schemas compile; every invalid combination listed in the risk table is rejected with a readable message.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck`

---

### Step 2: Add schema unit tests

**Files:**
- `packages/aurora/src/server/Storage/types/ceph.test.ts` — append a `describe("lifecycle schemas")` block (this file already exists and covers the bucket-policy schemas; follow its structure).

**What to do:** cover accept/reject for: minimal expiration-by-days rule; expiration-by-date; `ExpiredObjectDeleteMarker`; `Days`+`Date` together (reject); zero-action rule (reject); duplicate IDs (reject); `Filter` + top-level `Prefix` (reject); `And` with a single predicate (reject); single-tag filter; prefix+tags via `And`; a rule carrying `Transitions` (accept, preserved); >100 rules (reject); `ID` at 255 and 256 chars.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/types/ceph.test.ts`

---

### Step 3: Extend the S3 error map

**Files:**
- `packages/aurora/src/server/Storage/helpers/s3ErrorMapper.ts`

**What to do:** add to `S3_ERROR_MAP`: `NoSuchLifecycleConfiguration: "NOT_FOUND"`, `MalformedXML: "BAD_REQUEST"` (skip if the CORS branch merged first — it adds the same line), `InvalidArgument: "BAD_REQUEST"`. Do not change the mapper's shape or add a new convention.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/helpers`

---

### Step 4: Create the wire ⇄ SDK mapper helper

**Files (new):**
- `packages/aurora/src/server/Storage/helpers/lifecycleMapper.ts`
- `packages/aurora/src/server/Storage/helpers/lifecycleMapper.test.ts`

**What to do:**

1. `toWireLifecycleRules(sdkRules: SdkLifecycleRule[]): LifecycleRule[]` — convert `Expiration.Date` / `Transitions[].Date` (`Date` → ISO string), drop `undefined` members, then `lifecycleRuleSchema.parse` each rule so malformed backend data surfaces early.
2. `toSdkLifecycleRules(rules: LifecycleRule[]): SdkLifecycleRule[]` — inverse: ISO string → `new Date(...)` normalized to midnight UTC for `Expiration.Date`; never emit both `Filter` and `Prefix`; omit empty optional objects/arrays entirely (RGW rejects empty XML elements).
3. `normalizeFilter(input): LifecycleFilter` — prefix only → `{ Prefix }`; one tag, no prefix → `{ Tag }`; prefix + ≥1 tag, or ≥2 tags → `{ And: { Prefix?, Tags } }`; nothing → `{ Prefix: "" }` (whole-bucket, the RGW-safe encoding).
4. Alias the SDK type on import (`import type { LifecycleRule as SdkLifecycleRule } from "@aws-sdk/client-s3"`).
5. Tests: each filter-normalization branch, `Date` round-trip preserving the instant, transitions preserved verbatim, `toWire(toSdk(x)) === x` for a fixture with every field populated.

**Expected outcome:** all date/filter/shape trickiness lives in one tested pure module; the router stays as thin as `bucketPolicyRouter`.

---

### Step 5: Implement `lifecycleRouter`

**Files (new):**
- `packages/aurora/src/server/Storage/routers/ceph/lifecycleRouter.ts`

**What to do:** export a plain object `lifecycleRouter` (not `auroraRouter(...)`) with three procedures on `cephProtectedProcedure`, copying the structure and JSDoc style of `bucketPolicyRouter.ts`:

1. `get` — `.input(getLifecycleInputSchema).query(): Promise<GetLifecycleOutput>`; `new GetBucketLifecycleConfigurationCommand({ Bucket: bucketName })`; `return { rules: toWireLifecycleRules(response.Rules ?? []) }`, or `{ rules: null }` when `Rules` is empty/undefined; catch `NoSuchLifecycleConfiguration` (check both `err.name` and `err.Code`, as the siblings do) → `{ rules: null }`; everything else → `mapS3ErrorToTRPCError(error, { operation: "get lifecycle configuration", bucket: bucketName })`.
2. `set` — `.input(setLifecycleInputSchema).mutation(): Promise<boolean>`; **check the rate limit first** (see below), then `new PutBucketLifecycleConfigurationCommand({ Bucket: bucketName, LifecycleConfiguration: { Rules: toSdkLifecycleRules(input.lifecycleConfiguration.Rules) } })`; return `true`. Keep validation in the Zod schema (the mutation body should not re-implement checks); map errors via the mapper.
3. `delete` — `.input(deleteLifecycleInputSchema).mutation(): Promise<boolean>`; `new DeleteBucketLifecycleCommand(...)`; treat `NoSuchLifecycleConfiguration` as idempotent success (`return true`).

**Rate limiter — decided 2026-08-05, reversing the original "don't copy" guidance:** add a `checkLifecycleSetRateLimit(bucketName, projectId)` on `set`, copying `corsRouter`'s `checkCorsSetRateLimit` shape verbatim (in-memory `Map<string, {count, resetAt}>`, 10 calls/minute/bucket, periodic cleanup of expired entries, `TRPCError({ code: "TOO_MANY_REQUESTS", ... })` when exceeded). This pattern now appears in both `bucketPolicyRouter` and `corsRouter` — treat it as an established convention for Ceph bucket sub-resource `set` procedures, not a one-off, and keep lifecycle consistent with it rather than being the odd one out. The known limitation still applies (a module-level `Map` isn't a real limit across multiple BFF instances) — if a proper distributed rate limit is ever introduced, it should replace this pattern in all three routers together, not just lifecycle.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck`

---

### Step 6: Mount the router

**Files:**
- `packages/aurora/src/server/Storage/routers/ceph/index.ts` — add `export { lifecycleRouter } from "./lifecycleRouter"`.
- `packages/aurora/src/server/Storage/routers/index.ts` — import `lifecycleRouter` and add `lifecycle: auroraRouter({ ...lifecycleRouter })` inside the `ceph:` namespace, after `bucketPolicy`.

**Expected outcome:** `trpcReact.storage.ceph.lifecycle.get/set/delete` is typed end-to-end on the client.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck` (client type inference is the real check here).

---

### Step 7: Router tests

**Files (new):**
- `packages/aurora/src/server/Storage/routers/ceph/lifecycleRouter.test.ts`

**What to do:** mirror `bucketPolicyRouter.test.ts` / the CORS branch's `corsRouter.test.ts` exactly:

```ts
const mockSend = vi.fn()
vi.mock("../../clients/s3Client", () => ({ createS3Client: vi.fn(() => ({ send: mockSend })) }))
// router = auroraRouter(lifecycleRouter); createCaller = createCallerFactory(router)
// ctx = createMockContext()   // from ./mockContext
```

Cases: **get** — rules returned and date-converted to ISO; `null` when no config; `null` on `NoSuchLifecycleConfiguration`; transitions preserved in output; `NOT_FOUND` on `NoSuchBucket`; `FORBIDDEN` with `createMockContext({ hasCredentials: false })`; `FORBIDDEN` on `AccessDenied`. **set** — days-based rule; date-based rule (assert the command received a real `Date`); noncurrent expiration; abort-MPU; prefix+tags `And` filter; whole-bucket filter; round-trip of a config containing transitions (assert `Transitions` reaches `send`); `BAD_REQUEST` for each superRefine violation (empty `Rules`, zero-action rule, `Days`+`Date`, duplicate IDs, `Filter`+`Prefix`, `ID` > 255); `BAD_REQUEST` on `MalformedXML`; `NOT_FOUND`/`FORBIDDEN` paths; **`TOO_MANY_REQUESTS` after 10 calls within a minute for the same bucket** (rate limiter, mirroring `corsRouter.test.ts`'s coverage), and confirm the counter is keyed per-bucket (a different bucket isn't limited by another's calls). **delete** — success; idempotent on `NoSuchLifecycleConfiguration`; `NOT_FOUND`; `FORBIDDEN`.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/routers/ceph/lifecycleRouter.test.ts`

---

### Step 8: Build the lifecycle UI components

**Files (all new, in `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/`):**

- `LifecycleModal.tsx`
- `LifecycleRulesViewer.tsx`
- `LifecycleRuleForm.tsx`
- `DeleteLifecycleModal.tsx`

**What to do:**

1. **`LifecycleModal.tsx`** — structure copied from the CORS branch's `CorsModal.tsx` (as it stands 2026-08-05, re-verify at implementation time):
   - Props `{ isOpen, bucketName, onClose, onSuccess?, onError? }`; `key={bucketName}` on `<Modal>`; `size="xl"` (matching `CorsModal`, not `"large"`); `useModalTracking({ isOpen, actionPrefix: "storage.ceph.bucket.lifecycle" })`.
   - A `ViewState = "empty" | "list" | "form"` state machine (matching `CorsModal`'s actual shape — not a `VIEW`/`ADD` tab pair as an earlier draft of this plan assumed): `empty` when no rules exist, `list` shows `LifecycleRulesViewer`, `form` shows `LifecycleRuleForm` (add or edit). Track `editingRuleIndex: number | null` for add-vs-edit.
   - `trpcReact.storage.ceph.lifecycle.get.useQuery({ project_id, bucketName }, { enabled: isOpen && !!projectId, retry: false })`; seed local `currentRules: LifecycleRule[]` state from the response (initialize on open / first load, matching `CorsModal`'s `hasInitialized`/`prevIsOpenRef` pattern); also store an immutable `loadedSnapshot` for the concurrency check (this is a deliberate lifecycle-only addition — CORS has no equivalent check).
   - `set` and `delete` mutations both `utils.storage.ceph.lifecycle.get.invalidate()` on success, then `onSuccess?.(bucketName, "save" | "delete")` + `handleClose()`.
   - Footer: `Cancel` (`variant="subdued"`) + `Save` (`variant="primary"`, **always shown**, disabled unless `hasChanges` — JSON comparison against `corsData`/loaded rules — and not saving). On confirm: if `currentRules.length === 0` → `delete.mutate(...)`, else → `set.mutate({ project_id, bucketName, lifecycleConfiguration: { Rules: currentRules } })`. In the `empty` and `list` views, "Add New Rule"/"Add Rule" is a separate `variant="primary"` button in the body (not the footer) — each view has its own primary CTA, matching CORS's resolved pattern, not one primary button reused everywhere.
   - ⚠️ Before mutating, refetch `get` and compare with `loadedSnapshot`; on mismatch show an error `Message` ("The lifecycle configuration changed since you opened this dialog. Close and reopen to reload.") and abort the save.
   - Error `Message` blocks for query error, set error, delete error (same three-block pattern as `CorsModal`/`BucketPolicyModal`).
   - Whole-bucket-expiration warning `Message` (see risk table) rendered the same way `CorsModal` renders its wildcard-origin warning — computed from `currentRules`, shown above the view content.
2. **`LifecycleRulesViewer.tsx`** — props `{ rules, onAddRule, onEditRule, onDeleteRule }` (**no `onDeleteAllRules`** — corrected 2026-08-05: `CorsRulesViewer` has no such button; deleting the whole configuration is `DeleteLifecycleModal`'s job only, see point 4). Short description text; one `variant="primary"` "Add New Rule"/"Add Rule" button above the list; per-rule `RuleCard` with edit/delete icon buttons (`size="small"`, `variant="subdued"`, matching `CorsRulesViewer`'s `RuleCard`) showing ID (or "Rule N"), a `Badge` for `Enabled`/`Disabled`, the filter in human terms ("All objects" / "Prefix: logs/" / "Tag env=prod"), and each action ("Expire current versions after 30 days", "Expire noncurrent versions after 7 days", "Abort incomplete multipart uploads after 3 days"); transitions rendered read-only with the note "Storage-class transitions are managed outside Aurora and are preserved unchanged." 🔒 A `Message variant="warning"` per rule when `Status === "Enabled"` and the filter matches the whole bucket and a current-version `Expiration` is set. No footer.
3. **`LifecycleRuleForm.tsx`** — `@tanstack/react-form` + `useStore`, props `{ editingRule, onSubmit, onCancel, isSaving }`:
   - `ID` (`TextInput`, optional, helptext "max 255 characters, must be unique"), `Status` (`Select`: Enabled/Disabled, **default `Disabled`**).
   - Filter section: `Prefix` `TextInput`; tag key/value rows with add/remove, modelled on `EditMetadataModal.tsx`'s row editor (do **not** reuse the CORS branch's `TagInput`, which is a flat string list).
   - Actions section (at least one required, enforced client-side before enabling submit and again server-side): expire current versions — radio `Days` (number) vs `Date` (date input) vs `ExpiredObjectDeleteMarker` (checkbox); `NoncurrentVersionExpiration.NoncurrentDays` (+ optional `NewerNoncurrentVersions`), with helptext noting it only applies to versioned buckets; `AbortIncompleteMultipartUpload.DaysAfterInitiation`.
   - Read-only summary of any `Transitions` carried by the rule being edited, with the preservation note; the form must pass them through untouched into the emitted rule.
   - Submit builds a `LifecycleRule` (dropping empty optionals) and calls `onSubmit`; "Cancel Edit" shown only in edit mode.
4. **`DeleteLifecycleModal.tsx`** — copy `DeleteBucketPolicyModal.tsx` verbatim in structure: query `lifecycle.get` to verify rules exist, `size="small"`, `confirmButtonVariant="primary-danger"`, disabled when loading/empty/errored, warning `Message` when nothing is configured, and a body listing how many rules will be removed.

**Expected outcome:** components render standalone; no route changes needed.

---

### Step 9: Wire lifecycle into the bucket detail header

**Files:**
- `.../Ceph/Buckets/BucketToastNotifications.tsx` — add `getLifecycleSavedToast`, `getLifecycleSaveErrorToast`, `getLifecycleDeletedToast`, `getLifecycleDeleteErrorToast`, matching the existing `{ message, description }` `<Trans>` factories.
- `.../Ceph/Buckets/BucketModals.tsx` — extend `ModalType` with `"lifecycle" | "deleteLifecycle"`; render `<LifecycleModal>` and `<DeleteLifecycleModal>` with the same `onSuccess`/`onError` → `toast.*` + `onClose()` wiring used for the policy modals.
- `.../Ceph/Buckets/BucketHeaderActions.tsx` — add a `hasLifecycleRules: boolean` prop and:
  - A **third standalone header button** `<Button variant="subdued" className="whitespace-nowrap" onClick={() => onOpenModal("lifecycle")}>` with label `Edit/View Lifecycle Rules` / `Add Lifecycle Rules` (mirroring `hasPolicy`/`hasCors` conditional labels), placed after the CORS button and before the "..." `PopupMenu` toggle.
  - `Delete Lifecycle Rules` wired into the `PopupMenu` (`onClick={() => onOpenModal("deleteLifecycle")}`, shown only when `hasLifecycleRules`), matching exactly how `Delete Policy`/`Delete CORS` are wired there.
  - **Confirmed 2026-08-05, not deferred**: `Policy` and `CORS` are both standalone header buttons today, and that pattern survived CORS's 2026-08-05 UX refactor commit unchanged — so lifecycle follows suit as a third button rather than a menu item. **Still re-verify against `main` at implementation time** in case CORS's own PR picks up a header redesign before it merges (three buttons + "..." is already visually dense; if a future redesign collapses them, match that instead of reintroducing individual buttons).
- `.../Ceph/Buckets/BucketHeader.tsx` — consume `lifecycleData` from `useBucketInfo`, pass `hasLifecycleRules`, and add a `<Badge variant="info"><Trans>Lifecycle Rules</Trans></Badge>` when `lifecycleData?.rules?.length`.
- `.../Ceph/hooks/useBucketInfo.ts` — add `lifecycleData` to the `BucketInfo` interface and a `trpcReact.storage.ceph.lifecycle.get.useQuery({ project_id, bucketName }, { enabled: !!projectId && enabled, staleTime: 5 * 60 * 1000, retry: false })`; include `isLoadingLifecycle` in the aggregate `isLoading`.

(All under `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/`.)

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck`, then manual check that the bucket detail page still renders when the bucket has no lifecycle config.

---

### Step 10: SKIPPED — permission keys are explicitly out of scope for this task

> **Executor: do not add permission keys or `canUser` gating for lifecycle in this task.**
> Decided 2026-07-31: no bucket sub-resource (policy, versioning, CORS) has permission keys today —
> `STORAGE_MAPPINGS` in `packages/aurora/src/server/Storage/routers/permissionRouter.ts` has no entries
> for any of them, and `trpcReact.storage.canUser` is not called anywhere in the client. This is not an
> oversight specific to lifecycle; it's simply work that hasn't started for Ceph object storage at all.
> A **separate, dedicated task will retrofit permissions across the entire Ceph/S3 storage surface**
> (bucket policy, versioning, CORS, lifecycle, and likely containers/objects gating gaps too) in one
> consistent pass — do not preempt that by wiring up lifecycle alone, since a single permission-gated
> action next to three ungated ones in the same menu would be an inconsistent, confusing partial state.
> If that dedicated task already exists by the time this plan is implemented, coordinate with it instead
> of duplicating the work here.

**What this means concretely:** skip entirely — do not touch `permissionRouter.ts`, do not add
`storage:containers:*_lifecycle` mappings, do not call `trpcReact.storage.canUser` from any lifecycle
component. The "Lifecycle Rules" / "Delete Lifecycle Rules" menu items (Step 9) are visible to anyone
who can open the bucket detail page, matching the current (ungated) behavior of Policy and Versioning.

---

### Step 11: Client tests

**Files (new, colocated):**
- `.../Ceph/Buckets/LifecycleModal.test.tsx`
- `.../Ceph/Buckets/LifecycleRuleForm.test.tsx`
- `.../Ceph/Buckets/LifecycleRulesViewer.test.tsx`
- `.../Ceph/Buckets/DeleteLifecycleModal.test.tsx`

**What to do:** copy the mocking harness from `BucketPolicyModal.test.tsx` (`vi.mock("@/client/hooks/useProjectId")`, `vi.mock("@tanstack/react-router")` for `useRouteContext`, `vi.mock("@/client/trpcClient")` with a hand-rolled `trpcReact.storage.ceph.lifecycle.{get.useQuery,set.useMutation,delete.useMutation}` + `useUtils`), render inside `<I18nProvider i18n={i18n}><PortalProvider>…`.

Cases: empty state ("no rules configured"); rules render with correct human-readable summaries; add-rule flow appends locally without calling `set` until Save; edit-rule flow replaces in place; delete-rule removes locally; Save with rules → `set.mutate` with the exact `lifecycleConfiguration` payload; Save with zero rules → `delete.mutate`; Save disabled when nothing changed; a rule carrying `Transitions` survives an unrelated edit (guards the 🔴 data-loss risk); whole-bucket + expiration warning appears; error `Message` rendered on query/mutation error.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets`

---

### Step 12: i18n, docs, changeset

**Files:**
- `packages/aurora/src/locales/{en,de}/messages.po` + `messages.ts` — regenerated, never hand-edited.
- `packages/aurora/docs/009_ceph_s3_bff.md` — add a "Lifecycle Configuration" section documenting the three procedures, the wire schema, the transitions-are-preserved-not-authored decision, and the async-processing caveat.
- `.changeset/<name>.md` — `@cobaltcore-dev/aurora: minor`.

**What to do:** run `pnpm check-i18n` (adds English + German entries; German strings need real translations, matching how the CORS branch added ~194 lines per catalog). Commit as `feat(aurora): ceph s3 bucket lifecycle rules` (scope `aurora` is allow-listed in `commitlint.config.mjs`); PR title must satisfy commitlint too. Optionally add a KB note by updating the Storage — Ceph S3 row in `../DOCS/aurora-dashboard-kb/05-domain-map.md`.

---

## Testing Plan

**Unit (server)**
- [ ] `ceph.test.ts`: all lifecycle schema accept/reject cases from Step 2.
- [ ] `lifecycleMapper.test.ts`: filter normalization branches, ISO ⇄ `Date`, midnight-UTC normalization, full-fidelity round-trip.
- [ ] `lifecycleRouter.test.ts`: the ~30 cases from Step 7 with a mocked `createS3Client`.

**Unit (client)**
- [ ] The four component test files from Step 11, notably the transitions-preservation case.

**Integration**
- [ ] `get` → edit one rule in the modal → `set`: assert (in the router test, via `mockSend` args) that untouched rules and their transitions are byte-identical to what `get` returned.
- [ ] Deleting the last rule in the UI issues `delete`, not `set` with an empty array (S3 rejects empty `Rules`).

**Manual (requires real RGW)**
1. `pnpm dev`; open a project with EC2 credentials → `Storage → Ceph → <bucket> → Objects`.
2. Actions menu → **Lifecycle Rules** → empty state renders, no console errors.
3. Add rule: ID `expire-logs`, Status `Enabled`, Prefix `logs/`, expire current versions after 30 days → Save → success toast, "Lifecycle Rules" badge appears, reopening shows the rule. ⚠️ Confirm the `PutBucketLifecycleConfiguration` request is accepted — this is where the checksum/`Content-MD5` risk would surface.
4. Verify out-of-band: `aws s3api get-bucket-lifecycle-configuration --bucket <b> --endpoint-url <rgw>`.
5. Set a config **with a transition** via `aws s3api put-bucket-lifecycle-configuration`, reopen the Aurora modal: the transition shows read-only; edit a *different* rule and save; re-run `get-bucket-lifecycle-configuration` and confirm the transition is intact.
6. Add a rule with a tag filter (`env=prod`) and one with prefix + 2 tags → confirm RGW accepts the `And` encoding.
7. Delete all rules → bucket returns `NoSuchLifecycleConfiguration`; delete again from the UI → still succeeds (idempotent).
8. Try to save an invalid rule (Days + Date) → field-level error, no request sent.
9. Revoke/blank EC2 credentials → modal surfaces the `NO_CEPH_CREDENTIALS` FORBIDDEN path like the other Ceph modals.

---

## Acceptance Criteria

- [ ] `storage.ceph.lifecycle.get` returns `{ rules: null }` (not an error) for a bucket with no lifecycle configuration, and typed rules otherwise, with all dates as ISO strings.
- [ ] `storage.ceph.lifecycle.set` accepts a full rule array, validates it before hitting S3, and returns `true`.
- [ ] `storage.ceph.lifecycle.delete` is idempotent and returns `true` when nothing was configured.
- [ ] All three procedures run on `cephProtectedProcedure` and map S3 errors through `mapS3ErrorToTRPCError` — no new error convention introduced.
- [ ] Zod schema rejects: zero-action rules, `Days`+`Date`, `ExpiredObjectDeleteMarker` with a tag filter, `Filter`+top-level `Prefix`, duplicate IDs, `And` with < 2 predicates, > 100 rules, `ID` > 255 chars.
- [ ] Storage-class transitions authored outside Aurora survive an unrelated edit-and-save round trip, and are never authored by the UI.
- [ ] Bucket detail page exposes "Lifecycle Rules" (and "Delete Lifecycle Rules" when present) in the actions menu, shows a badge when rules exist, and the modal supports view / add / edit / delete with a single explicit Save.
- [ ] A rule that expires current versions across the whole bucket triggers a visible warning before save; new rules default to `Disabled`.
- [ ] The rule form supports authoring `AbortIncompleteMultipartUpload` (`DaysAfterInitiation`) as a first-class action alongside `Expiration`/`NoncurrentVersionExpiration` — this is required, not a stretch/optional field (decided 2026-07-31: only per-bucket lever a project user has in Aurora to reclaim space from abandoned multipart uploads, since the cluster-level `rgw_abort_incomplete_multipart_upload_expiration` setting is admin-only and invisible to Aurora).
- [ ] No regression on the bucket detail page for buckets with no lifecycle config (no extra spinner, no error banner).
- [ ] Colocated vitest suites exist for the schemas, the mapper, the router, and all four UI components.
- [ ] `pnpm --filter @cobaltcore-dev/aurora typecheck`, `lint`, `test` pass; `pnpm check-i18n` and `pnpm format:check` clean; changeset present; commit/PR title passes commitlint.

---

## Open Questions

**Resolved (2026-07-31):**

1. ~~Storage-class transitions — in scope?~~ **Decided: out of scope for authoring.** RGW only supports `Transition`/`NoncurrentVersionTransition` when extra storage classes or cloud-tiering placement targets are configured in the zonegroup ([Ceph: Pool Placement and Storage Classes](https://docs.ceph.com/en/latest/radosgw/placement/), [Ceph: Cloud Transition](https://docs.ceph.com/en/reef/radosgw/cloud-transition/)), and the S3 API offers no way to enumerate them, so a storage-class picker would be guesswork against this deployment — and building one for real would require the same RGW Admin Ops API access that was already ruled out for epic Section 4 (Usage & Quota), reintroducing the exact dependency that section avoided. Read-and-preserve only, no authoring UI (Step 1's `lifecycleTransitionSchema`, Step 8's read-only rendering).
2. ~~Sequencing vs. the CORS branch (#1066).~~ **Decided: wait for CORS, do not parallelize.** See "Blocking dependency: CORS readiness gate" at the top of this document for the full rationale and the concrete gate conditions. Unlike the original three options considered (land-CORS-first / parallel-independent / single-combined-PR), the deciding factor wasn't just merge conflicts (those are now resolved — CORS synced with `main` on 2026-07-31) but that CORS's own UI design is still open (`TBC` primary-button question) and its `get` has an apparently-unfixed schema-validation bug worth avoiding in `lifecycleMapper.ts` from day one.
3. ~~Permission keys now, or in an epic-§15 backfill?~~ **Decided: skip entirely.** Permissions for Ceph/S3 bucket sub-resources (policy, versioning, CORS, lifecycle) have not been started at all — this isn't lifecycle-specific catch-up work, it's a whole unstarted surface that a separate dedicated task will cover in one consistent pass across all of Ceph/S3 storage. Step 10 is a documented no-op for this task; see the executor note there.

4. ~~`AbortIncompleteMultipartUpload` in the authoring UI?~~ **Decided: required, not optional.** Not mentioned in the epic checklist text, but RGW genuinely supports it (`rgw_abort_incomplete_multipart_upload_expiration` is a *cluster-level* admin-only config Aurora cannot see or influence — a per-bucket lifecycle rule via this UI is the only lever a project user has in Aurora itself to reclaim space from abandoned multipart uploads, which matters directly because Aurora already ships multipart object upload, #1086). Must ship in Step 1 (schema — already includes `abortIncompleteMultipartUploadSchema`) and Step 8 (form field — already listed as `AbortIncompleteMultipartUpload.DaysAfterInitiation`); do not drop it for scope-tightening.

5. ~~Rule-count cap.~~ **Decided: 100, matching the CORS sibling** (down from the technical AWS/RGW-default maximum of 1000) — see Step 1's `lifecycleConfigurationSchema` for the full rationale (it's a UI-sanity limit for a manual add-one-at-a-time editor, not the real backend-enforced cap; RGW's actual per-deployment limit is the cluster-configurable, S3-API-invisible `rgw_lc_max_rules`).

6. ~~Entry point placement.~~ **Decided 2026-08-05: third standalone header button**, matching Policy/CORS. Confirmed by re-reading the CORS branch as it stands today (survived a same-day UX refactor unchanged) rather than by inference — see "CORS reference status" above and Step 9.

7. ~~Rate limiter for `lifecycleRouter.set`?~~ **Decided 2026-08-05: adopt it.** `bucketPolicyRouter` and (as of today) `corsRouter` both rate-limit their `set` procedure with the same in-memory per-bucket pattern — this plan originally told the executor to skip it for lifecycle as a one-off judgment call, but with two independent precedents it's now a project convention. See Step 5 for the concrete instruction.

Sources: [Ceph Object Gateway S3 API](https://docs.ceph.com/en/latest/radosgw/s3/), [Pool Placement and Storage Classes](https://docs.ceph.com/en/latest/radosgw/placement/), [Cloud Transition](https://docs.ceph.com/en/reef/radosgw/cloud-transition/)
