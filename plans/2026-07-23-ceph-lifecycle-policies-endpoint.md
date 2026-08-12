# Plan: Ceph bucket lifecycle policies endpoint

**Date:** 2026-07-23 · **Status:** implemented 2026-07-23

## 📋 IMPLEMENTATION PLAN: List Ceph Bucket Lifecycle Policies (BFF endpoint + storage-page table)

### Overview

Add a read-only tRPC endpoint, `storage.ceph.lifecyclePolicy.list`, that returns the S3 lifecycle
configuration (expiration/transition rules) for every bucket in a project's Ceph object store, and
render it as a new table on the existing Ceph storage page (`/projects/$projectId/storage/ceph/buckets`),
alongside the current bucket list. This is a project-wide read view — Ceph's S3 API has no
"list lifecycle policies across buckets" call, so the BFF fans out one `GetBucketLifecycleConfiguration`
per bucket (bounded concurrency) and aggregates the results, the same shape `containerRouter.list`
already uses for per-bucket metadata.

### Architecture Analysis

**Current state:**

- `packages/aurora/src/server/Storage/routers/ceph/` holds one router file per S3 concern
  (`containerRouter.ts`, `objectRouter.ts`, `bucketPolicyRouter.ts`, `versioningRouter.ts`,
  `ec2CredentialRouter.ts`), each built on `cephProtectedProcedure` (`../../cephProcedure.ts`),
  which resolves EC2 credentials + a project-scoped `S3Client` and throws `FORBIDDEN`/`NO_CEPH_CREDENTIALS`
  if the project has none. All are mounted in `ceph/index.ts` → `routers/index.ts` under
  `storage.ceph.<name>`.
- `containerRouter.list` (`containerRouter.ts:36-130`) is the direct precedent for "iterate every
  bucket in the project and fetch a per-bucket detail": it calls `ListBucketsCommand` once, then —
  when `includeMetadata` is requested — fans out `ListObjectsV2Command` per bucket in batches of
  `CONCURRENCY_LIMIT = 5` via `Promise.all`, catching per-bucket failures individually so one bad
  bucket doesn't fail the whole list.
- `bucketPolicyRouter.get` (`bucketPolicyRouter.ts:130-167`) is the direct precedent for "a
  per-bucket S3 sub-resource that often doesn't exist": S3 throws `NoSuchBucketPolicy` when no
  policy is set, and the router explicitly treats that as `{ policy: null }`, not an error. The
  generic `mapS3ErrorToTRPCError` (`../../helpers/s3ErrorMapper.ts`) does **not** know this code —
  it falls through to `INTERNAL_SERVER_ERROR` — so callers special-case it before delegating to the
  mapper.
- `versioningRouter.ts` shows the convention for a domain that gets its own `types/<name>.ts` file
  (`types/versioning.ts`) rather than growing `types/ceph.ts` further, since `types/ceph.ts` is
  already ~800+ lines covering buckets/objects/policies.
- Input schemas extend `projectScopedInputSchema` (from `../../trpc`), which requires `project_id`
  and drives `projectScopedProcedure`'s token rescoping — every Ceph router input does this.
- `Storage/routers/permissionRouter.ts` maps UI permission keys (`storage:<resource>:<action>`) to
  oslo.policy rules in `storage.json`, shared by Swift and Ceph via Swift-flavored resource names
  (`containers`, `objects`, `folders`). There is **no** lifecycle-specific rule or resource name
  today — `capabilities.lifecycleRules` in `types/ceph.ts:309` is an unrelated boolean flag on the
  (currently unused) S3 service-info schema, not a real feature.
- Client: `CephBuckets` (`.../storage/-components/Ceph/Buckets/index.tsx`) is the top-level component
  rendered by the storage page (`storage/$provider/$storageType/index.tsx:199`) when
  `provider === "ceph"`. It fetches `storage.ceph.containers.list` via `trpcReact...useQuery`, handles
  the `NO_CEPH_CREDENTIALS` error specially (renders `<CredentialPrompt/>`), and renders
  `BucketTableView`, a virtualized (`@tanstack/react-virtual`) `DataGrid` from
  `@cloudoperators/juno-ui-components`. Loading/error/empty states, i18n (Lingui `Trans`/`t`), and
  toast notifications all follow the same recipe across these table components.
- `@aws-sdk/client-s3` (`^3.1042.0`, already a dependency) provides
  `GetBucketLifecycleConfigurationCommand` — standard S3 API, no new dependency needed.

**Proposed changes:**

- New `types/lifecyclePolicy.ts`: Zod schemas for the list input (`project_id` only — this is a
  project-wide view, not per-bucket) and the output shape (per-bucket array of simplified lifecycle
  rules: id, status, prefix/filter, expiration, transitions, noncurrent-version expiration).
- New `routers/ceph/lifecyclePolicyRouter.ts`: one `list` query on `cephProtectedProcedure`, following
  `containerRouter.list`'s "list buckets, then fan out with bounded concurrency" shape, and
  `bucketPolicyRouter.get`'s "S3 'not configured' error is not a tRPC error" shape (S3 throws
  `NoSuchLifecycleConfiguration` when a bucket has no lifecycle rules — the overwhelmingly common
  case — which must map to `{ bucket, rules: [] }`, not an error).
- Mount as `storage.ceph.lifecyclePolicy` in `ceph/index.ts` and `routers/index.ts`, matching the
  existing sibling routers exactly.
- Reuse the existing `storage:containers:read` permission key to gate the new table (see Open
  Questions — no lifecycle-specific policy rule exists yet, and inventing one requires an oslo.policy
  change in the consumer's `storage.json`, which is out of scope for a BFF-only endpoint).
- Client: a new `LifecyclePoliciesTableView` + a container component under
  `storage/-components/Ceph/LifecyclePolicies/`, fetching `storage.ceph.lifecyclePolicy.list` and
  rendering a `DataGrid` (non-virtualized — bucket counts are small, unlike object lists), following
  `BucketTableView`'s loading/error/empty conventions. Rendered inside `CephBuckets`, below the
  existing bucket table, as a second `DataGrid` section on the same page (see Open Questions for the
  tab-vs-inline-section alternative).

### Potential Problems & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| S3 returns `NoSuchLifecycleConfiguration` for any bucket with no lifecycle rules configured (the default/common state). The generic `mapS3ErrorToTRPCError` has no entry for this code and falls through to `INTERNAL_SERVER_ERROR` — if not special-cased, the endpoint throws a 500 for the normal case and the table never renders for most projects. | 🔴 High | Catch this specific error per-bucket (same pattern as `bucketPolicyRouter.get`'s `NoSuchBucketPolicy` handling) and map it to `{ bucket, rules: [] }`, not a thrown error. Add a regression test asserting a bucket with no lifecycle config returns an empty-rules row, not a query error. |
| ⚡ N+1 fan-out: one `GetBucketLifecycleConfiguration` call per bucket in the project. Large projects (dozens–hundreds of buckets) mean dozens–hundreds of sequential-if-unbounded S3 calls, slowing the page and risking S3 throttling. | Medium | Reuse `containerRouter.list`'s bounded-concurrency batching (`CONCURRENCY_LIMIT`, `Promise.all` per batch) instead of `Promise.all` over the whole bucket list. Per-bucket failures caught individually (as `containerRouter.list` already does) so one bucket's error doesn't blank the whole table. |
| 🔒 No existing permission key covers "read lifecycle policy" — reusing `storage:containers:read` is a judgment call, not a verified-correct mapping to an underlying oslo.policy rule for this specific capability. | Medium | Ship gated behind `storage:containers:read` (already required to see the bucket list this table sits next to) and flag as an Open Question below; a dedicated `storage:lifecycle_policies:read` key can be added later without a breaking change once product/security confirms the policy split is wanted. |
| Ceph/RGW may not implement the S3 Lifecycle API identically to AWS (older RGW versions, or lifecycle disabled cluster-side) — errors here won't match the `NoSuchLifecycleConfiguration` assumption and could surface as opaque `NotImplemented`/`MethodNotAllowed`. | Low | `mapS3ErrorToTRPCError` already has a generic unmapped-code fallback with logging (`s3ErrorMapper.ts:57-59`); rely on it for anything besides the two explicitly-handled codes (`NoSuchLifecycleConfiguration`, generic S3 errors) rather than trying to enumerate every RGW variant up front. Manual verification step below covers checking this against a real RGW backend. |
| UI placement on the storage page isn't specified by the task ("show them in a table on the storage page") — could mean inline on the existing Buckets view, a new tab/sub-route, or per-bucket detail. Guessing wrong means rework. | Low (process risk, not technical) | Plan defaults to an inline second table on the existing Ceph Buckets view (lowest-effort, no new route); flagged explicitly in Open Questions for confirmation before/at implementation time. |

### Prerequisites

- [ ] Confirm which permission key gates this table — reuse `storage:containers:read` (default in
      this plan) or introduce a new `storage:lifecycle_policies:read` key + oslo.policy rule in
      `apps/dashboard/src/policies/storage.json` (see Open Questions).
- [ ] Confirm UI placement — inline table below `BucketTableView` in `CephBuckets` (default in this
      plan) vs. a separate tab/section (see Open Questions).
- [ ] Verify `@aws-sdk/client-s3@^3.1042.0` (already installed) exports
      `GetBucketLifecycleConfigurationCommand` with the expected `Rules[]` shape — quick local check
      against the package's type declarations before writing the router.

### Implementation Steps

#### Step 1: Add lifecycle policy types

**Files to modify/create:**

- `packages/aurora/src/server/Storage/types/lifecyclePolicy.ts` (new)

**What to do:**

1. Import `z` and `projectScopedInputSchema` from `../../trpc`, following `types/versioning.ts`'s
   header pattern.
2. Define `lifecycleRuleSchema`: `id` (string), `status` (`z.enum(["Enabled", "Disabled"])`),
   `prefix` (string, optional — legacy top-level prefix), `filter` (optional object: `prefix`
   string optional, `tags` array of `{key, value}` optional — mirrors S3's `Filter.And` shape but
   simplified for display), `expiration` (optional object: `days` number optional, `date` ISO
   string optional, `expiredObjectDeleteMarker` boolean optional), `noncurrentVersionExpirationDays`
   (number, optional), `transitions` (array of `{days?: number, date?: string, storageClass: string}`,
   optional), `abortIncompleteMultipartUploadDaysAfterInitiation` (number, optional).
3. Define `bucketLifecyclePoliciesSchema`: `{ bucket: string, rules: lifecycleRuleSchema[] }`.
4. Define `listLifecyclePoliciesInputSchema = projectScopedInputSchema` (no extra fields — this is
   project-wide, unlike `getBucketPolicyInputSchema` which needs a `bucketName`).
5. Export inferred types: `LifecycleRule`, `BucketLifecyclePolicies`.

**Expected outcome:**

- A typed, Zod-validated contract for the new endpoint's output, independent of `types/ceph.ts`.

**Verification:**

- `pnpm --filter @cobaltcore-dev/aurora typecheck` passes with no consumers yet (dead code is fine
  at this point).

---

#### Step 2: Add `s3ErrorMapper` awareness of the lifecycle "not configured" code

**Files to modify/create:**

- `packages/aurora/src/server/Storage/helpers/s3ErrorMapper.ts`

**What to do:**

1. Add `NoSuchLifecycleConfiguration: "NOT_FOUND"` to `S3_ERROR_MAP` (`s3ErrorMapper.ts:10-35`) —
   consistent with the existing `NoSuchBucketPolicy: "NOT_FOUND"` entry, even though the router will
   intercept this code before it reaches the generic mapper (defense in depth: any code path that
   forgets the special case still gets a sane `NOT_FOUND` instead of `INTERNAL_SERVER_ERROR`).

**Expected outcome:**

- Any unmapped call site for this error code degrades gracefully instead of surfacing as a 500.

**Verification:**

- Existing `s3ErrorMapper.test.ts` continues to pass; optionally add one case asserting
  `NoSuchLifecycleConfiguration` → `NOT_FOUND`.

---

#### Step 3: Implement `lifecyclePolicyRouter`

**Files to modify/create:**

- `packages/aurora/src/server/Storage/routers/ceph/lifecyclePolicyRouter.ts` (new)

**What to do:**

1. Import `GetBucketLifecycleConfigurationCommand`, `ListBucketsCommand` from `@aws-sdk/client-s3`,
   `cephProtectedProcedure` from `../../cephProcedure`, `mapS3ErrorToTRPCError` from
   `../../helpers/s3ErrorMapper`, and the new schemas from `../../types/lifecyclePolicy`.
2. Implement `list: cephProtectedProcedure.input(listLifecyclePoliciesInputSchema).query(...)`:
   - Call `ListBucketsCommand({})` once (same as `containerRouter.list:40`) to get all bucket names
     for the project's credentials.
   - Fan out `GetBucketLifecycleConfigurationCommand({ Bucket })` per bucket in
     `CONCURRENCY_LIMIT`-sized batches (copy the batching loop from `containerRouter.list:61-124`,
     `CONCURRENCY_LIMIT = 5`).
   - Per bucket, inside a try/catch: on success, map `response.Rules` (AWS SDK shape) into
     `lifecycleRuleSchema` objects; on error, check `error.name`/`error.Code` for
     `NoSuchLifecycleConfiguration` and return `{ bucket, rules: [] }` (not a throw) — mirror
     `bucketPolicyRouter.get`'s `NoSuchBucketPolicy` special case exactly; any other per-bucket error
     is logged (`console.error`, matching `containerRouter.list:113`'s style) and that bucket
     contributes `{ bucket, rules: [] }` too, so one broken bucket doesn't fail the whole list.
   - Wrap the whole thing in a top-level try/catch around the `ListBucketsCommand` call, delegating
     to `mapS3ErrorToTRPCError(error, { operation: "list lifecycle policies" })` (matches
     `containerRouter.list:127-129`).
3. Add a file-level JSDoc block mirroring `versioningRouter.ts`'s style (purpose + throws).

**Expected outcome:**

- `lifecyclePolicyRouter.list` returns `BucketLifecyclePolicies[]`, one entry per bucket, empty
  `rules` for buckets with no configured lifecycle policy, without ever throwing for that case.

**Verification:**

- Unit tests (Step 5) cover: buckets with rules, buckets with no policy (empty array, no throw),
  a bucket that errors for an unrelated reason (excluded gracefully, doesn't fail the batch), and
  the `NO_CEPH_CREDENTIALS` path (inherited from `cephProtectedProcedure`, no new test needed beyond
  confirming the procedure guard is in place).

---

#### Step 4: Mount the router

**Files to modify/create:**

- `packages/aurora/src/server/Storage/routers/ceph/index.ts`
- `packages/aurora/src/server/Storage/routers/index.ts`

**What to do:**

1. In `ceph/index.ts`, add `export { lifecyclePolicyRouter } from "./lifecyclePolicyRouter"`.
2. In `routers/index.ts`, import `lifecyclePolicyRouter` alongside the other ceph router imports and
   add `lifecyclePolicy: auroraRouter({ ...lifecyclePolicyRouter })` inside the `ceph:
   auroraRouter({...})` block, in the same style as `bucketPolicy`/`versioning`.

**Expected outcome:**

- `storage.ceph.lifecyclePolicy.list` is reachable from the tRPC client (`trpcReact`) with full
  type inference end-to-end.

**Verification:**

- `pnpm --filter @cobaltcore-dev/aurora typecheck` — the client's generated `AppRouter` type picks
  up the new procedure; a throwaway `trpcReact.storage.ceph.lifecyclePolicy.list.useQuery(...)` call
  typechecks.

---

#### Step 5: Server-side tests

**Files to modify/create:**

- `packages/aurora/src/server/Storage/routers/ceph/lifecyclePolicyRouter.test.ts` (new)

**What to do:**

1. Follow `bucketPolicyRouter.test.ts`'s structure exactly: mock `../../clients/s3Client`'s
   `createS3Client` to return `{ send: mockSend }`, use `createMockContext`/`TEST_PROJECT_ID` from
   `./mockContext.ts`, build a caller via `createCallerFactory(auroraRouter({ ...lifecyclePolicyRouter }))`.
2. Test cases:
   - Project with buckets that each have lifecycle rules → returns rules parsed correctly (assert
     shape of `expiration`, `transitions`, etc.).
   - Project with a bucket that throws `NoSuchLifecycleConfiguration` → that bucket's entry is
     `{ bucket, rules: [] }`, and the call does **not** throw.
   - Mixed project (some buckets with rules, one with no policy, one with an unrelated S3 error) →
     all buckets appear in the result; the errored bucket degrades to `{ bucket, rules: [] }` rather
     than failing the whole request.
   - No credentials (`hasCredentials: false` in `createMockContext`) → `FORBIDDEN`/`NO_CEPH_CREDENTIALS`
     (inherited from `cephProtectedProcedure`, confirms the guard wasn't bypassed).

**Expected outcome:**

- Full coverage of the success path and both S3-error-handling branches.

**Verification:**

- `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/routers/ceph/lifecyclePolicyRouter.test.ts`

---

#### Step 6: Client — lifecycle policies table

**Files to modify/create:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/LifecyclePolicies/LifecyclePoliciesTableView.tsx` (new)
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/LifecyclePolicies/index.tsx` (new)

**What to do:**

1. `index.tsx`: a `LifecyclePolicies` component fetching
   `trpcReact.storage.ceph.lifecyclePolicy.list.useQuery({ project_id: projectId }, { enabled:
   !!projectId, retry: false })`, following `CephBuckets`' loading (`Spinner` + `Trans`)/error
   (check for `NO_CEPH_CREDENTIALS` and reuse `<CredentialPrompt/>`, same as `CephBuckets`)/empty
   conventions.
2. `LifecyclePoliciesTableView.tsx`: a plain (non-virtualized — bucket lists here are small) `DataGrid`
   with columns Bucket, Rule ID, Status, Prefix/Filter, Expiration, Transitions — one row per rule,
   flattening the per-bucket `rules[]`; buckets with zero rules render either no row or a single
   "No lifecycle rules configured" row per bucket (decide based on whether an empty-state-per-bucket
   or a fully-empty-table-only-when-zero-buckets reads better — default to the latter, matching
   `BucketTableView`'s single top-level empty state when `buckets.length === 0`, per-bucket empty
   rows shown otherwise).
3. Format dates/day counts with existing helpers where applicable (`formatBytesBinary` is
   bytes-specific and not reusable here; day counts can render as plain numbers, e.g. "30 days").
4. Wrap all user-facing strings in Lingui `<Trans>`/`t` per the rest of the storage components.

**Expected outcome:**

- A standalone, testable table component consuming the new endpoint.

**Verification:**

- Component test (Step 8) renders with mocked query data.

---

#### Step 7: Wire into the storage page

**Files to modify/create:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/index.tsx`

**What to do:**

1. Import `LifecyclePolicies` from `../LifecyclePolicies`.
2. Render it below the existing `<BucketTableView .../>` (and `<EmptyBucketsModal/>`), inside the
   same `<div className="relative">` returned by `CephBuckets`, as its own labeled section (e.g. a
   heading `<Trans>Lifecycle Policies</Trans>` above the new table) — see Open Questions if this
   default placement should instead be a separate tab/route.

**Expected outcome:**

- Visiting `/projects/$projectId/storage/ceph/buckets` shows the existing bucket table followed by
  the new lifecycle policies table.

**Verification:**

- Manual check (Testing Plan) + existing `CephBuckets`-adjacent tests still pass (no regression to
  the bucket table above it).

---

#### Step 8: Client-side tests

**Files to modify/create:**

- `.../Ceph/LifecyclePolicies/LifecyclePoliciesTableView.test.tsx` (new)
- `.../Ceph/LifecyclePolicies/index.test.tsx` (new)

**What to do:**

1. Follow `BucketTableView.test.tsx`/`Buckets/index.test.tsx`'s setup (mock `trpcReact`, assert
   loading/error/empty/populated render states).
2. Cover: populated table renders one row per rule; a bucket with zero rules doesn't crash the
   table; `NO_CEPH_CREDENTIALS` error renders `<CredentialPrompt/>` (shared behavior with the bucket
   table, but must be re-verified for this independent query).

**Expected outcome:**

- Component behavior is regression-covered without needing a running backend.

**Verification:**

- `pnpm --filter @cobaltcore-dev/aurora test` (scoped to the new test files, then the full package
  suite before commit).

### Testing Plan

**Unit tests:**

- [ ] `lifecyclePolicyRouter.test.ts` — success, no-policy-configured (no throw), per-bucket error
      isolation, missing-credentials guard (Step 5).
- [ ] `s3ErrorMapper.test.ts` — `NoSuchLifecycleConfiguration` → `NOT_FOUND` (Step 2, optional but
      cheap).
- [ ] `LifecyclePoliciesTableView.test.tsx`, `LifecyclePolicies/index.test.tsx` — render states
      (Step 8).

**Integration tests:**

- [ ] None planned — no Playwright e2e for this read-only view unless the team's e2e suite already
      exercises the Ceph buckets page end-to-end against a real/test RGW; if it does, extend it with
      an assertion that the lifecycle table renders (out of scope for this plan unless confirmed
      necessary).

**Manual verification:**

1. Against a real or test Ceph RGW: create a bucket, set a lifecycle rule (e.g., via `aws s3api
   put-bucket-lifecycle-configuration` or the AWS CLI against the RGW endpoint), and confirm it
   shows up in the new table.
2. Confirm a bucket with no lifecycle rule renders without error (this is the regression the High
   risk above is about — test this first).
3. Confirm the page still works with zero buckets, and with `NO_CEPH_CREDENTIALS` (no EC2
   credentials provisioned yet) — should show the existing `<CredentialPrompt/>`.
4. Confirm i18n: run `pnpm check-i18n` and verify new strings extract into `en`/`de` catalogs.

### Acceptance Criteria

- [ ] `storage.ceph.lifecyclePolicy.list` returns one entry per bucket in the project, with `rules:
      []` (not an error) for buckets with no lifecycle configuration.
- [ ] The Ceph storage page (`/projects/$projectId/storage/ceph/buckets`) shows a new lifecycle
      policies table reflecting the endpoint's data.
- [ ] No regressions to the existing bucket table, credential-prompt flow, or other Ceph storage
      routers.
- [ ] `pnpm typecheck`, `pnpm lint`, `pnpm test` pass for `@cobaltcore-dev/aurora`
      (`pnpm --filter @cobaltcore-dev/aurora <cmd>`).
- [ ] `pnpm check-i18n` run and catalogs updated for any new user-facing strings.

### Open Questions

1. **Permission gating** — reuse `storage:containers:read` (this plan's default) or add a dedicated
   `storage:lifecycle_policies:read` key + oslo.policy rule in `apps/dashboard/src/policies/storage.json`?
   The latter is more correct long-term but requires a policy-file change outside `packages/aurora`
   and coordination with whoever owns that consumer config.
2. **UI placement** — inline second table on the existing Ceph Buckets view (this plan's default,
   lowest effort) vs. a new tab/sub-route (e.g. `storage/ceph/lifecycle`) vs. per-bucket detail
   (expand a bucket row to see its rules)? The task only says "show them in a table on the storage
   page," which is compatible with all three; inline was chosen as the smallest, least speculative
   change.
3. **Scope: read-only vs. CRUD** — the task asks only for *listing* lifecycle policies. This plan
   deliberately does not add create/update/delete for lifecycle rules (`PutBucketLifecycleConfiguration`,
   `DeleteBucketLifecycleCommand`); confirm that's intended before treating this plan as "the
   lifecycle policy feature" rather than "the read half of it."
4. **RGW compatibility** — has the target Ceph/RGW cluster's S3 API been confirmed to implement
   `GetBucketLifecycleConfiguration` (and return `NoSuchLifecycleConfiguration` specifically, not
   some other error shape)? Not blocking (mitigated via the generic error-mapper fallback), but
   worth a quick confirmation before relying on the specific-error-code special case in Step 3.
