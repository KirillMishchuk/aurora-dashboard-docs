# Tasks: Bucket Tagging (Ceph S3)

> Источник: [`prd-bucket-tagging.md`](./prd-bucket-tagging.md) (Issue [#608](https://github.com/cobaltcore-dev/aurora-dashboard/issues/608), Section 14).
> Сгенерировано `generate-tasks.md` из `DOCS/ai-dev-tasks/`.

## Relevant Files

- `packages/aurora/src/server/Storage/types/ceph.ts` - Add `bucketTagSchema` + get/set/delete tagging input/output schemas, alongside the existing bucket policy schemas.
- `packages/aurora/src/server/Storage/types/ceph.test.ts` - Unit tests for the new tagging schemas (limits, duplicate keys, `aws:` prefix rejection).
- `packages/aurora/src/server/Storage/routers/ceph/bucketTaggingRouter.ts` - New router: `get`/`set`/`delete` procedures, modeled on `bucketPolicyRouter.ts`.
- `packages/aurora/src/server/Storage/routers/ceph/bucketTaggingRouter.test.ts` - Unit tests for the new router (success, validation-rejection, S3-error-mapping).
- `packages/aurora/src/server/Storage/routers/ceph/index.ts` - Export `bucketTaggingRouter`.
- `packages/aurora/src/server/Storage/routers/index.ts` - Register `bucketTagging` under `storage.ceph`.
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketTaggingModal.tsx` - New tag editor modal (add/edit/remove rows).
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketTaggingModal.test.tsx` - Tests for the new modal.
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketModals.tsx` - Wire the new `"tags"` modal type into the dispatcher.
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketHeaderActions.tsx` - Add "Manage Tags"/"Add Tags" menu action, gated by capability + permission.
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/index.test.tsx` - Existing integration-style test for the Buckets view; likely the right place to cover header-action gating (no dedicated `BucketHeaderActions.test.tsx`/`BucketModals.test.tsx` exist today).
- `packages/aurora/docs/009_ceph_s3_bff.md` - Update the Ceph BFF reference doc with the new tagging endpoints.

### Notes

- Unit tests are colocated with the code they test (`*.test.ts(x)` next to the source file) — no separate `__tests__` tree.
- Run `pnpm --filter @cobaltcore-dev/aurora test [path]` to run a single file, or without a path for the whole package.
- Task 3.0 starts with an investigation step — its exact sub-steps may need adjusting once the actual state of `capabilities` plumbing is known; treat 3.1's finding as the source of truth over this task list.

## Tasks

- [ ] 0.0 Create feature branch
  - [ ] 0.1 Create and checkout a new branch for this feature (e.g., `git checkout -b feature/bucket-tagging`)
- [ ] 1.0 Add tagging Zod schemas & types to `Storage/types/ceph.ts`
  - [ ] 1.1 Add `bucketTagSchema`: `{ key: z.string().min(1).max(128), value: z.string().max(256) }`, plus a refinement rejecting keys starting with `aws:`
  - [ ] 1.2 Add `getBucketTaggingInputSchema` (bucket name + `project_id`, mirroring `getBucketPolicyInputSchema`)
  - [ ] 1.3 Add `setBucketTaggingInputSchema` (bucket name + `project_id` + `tags: z.array(bucketTagSchema).max(10)`, plus a refinement rejecting duplicate keys within the array)
  - [ ] 1.4 Add `deleteBucketTaggingInputSchema` (bucket name + `project_id`)
  - [ ] 1.5 Add a `GetBucketTaggingOutput` type (`{ tags: BucketTag[] }`)
  - [ ] 1.6 Add unit tests in `types/ceph.test.ts` covering: valid tag set, >10 tags, key too long (>128), value too long (>256), empty key, duplicate keys, `aws:`-prefixed key
- [ ] 2.0 Implement `bucketTaggingRouter` (get/set/delete)
  - [ ] 2.1 Create `Storage/routers/ceph/bucketTaggingRouter.ts`, structured like `bucketPolicyRouter.ts` (JSDoc header, exported object with `get`/`set`/`delete`)
  - [ ] 2.2 Implement `get` using `GetBucketTaggingCommand` from `@aws-sdk/client-s3`; catch the "no tags set" error (confirm exact RGW error name — likely `NoSuchTagSet` or `NoSuchTagSetError`, verify empirically or against RGW docs) and return `{ tags: [] }` instead of throwing
  - [ ] 2.3 Implement `set` using `PutBucketTaggingCommand`; run the schema validation from 1.3 first, then call S3 with the full replacement tag set
  - [ ] 2.4 Implement `delete` using `DeleteBucketTaggingCommand`; treat the "no tags set" case as a successful no-op (idempotent), same pattern as `bucketPolicyRouter.delete`
  - [ ] 2.5 Route every S3 SDK error through the existing `mapS3ErrorToTRPCError` helper (`Storage/helpers/s3ErrorMapper.ts`)
  - [ ] 2.6 Export `bucketTaggingRouter` from `Storage/routers/ceph/index.ts`
  - [ ] 2.7 Register `bucketTagging: auroraRouter({ ...bucketTaggingRouter })` inside the `ceph` object in `Storage/routers/index.ts`, next to `bucketPolicy`/`versioning`
  - [ ] 2.8 Write `bucketTaggingRouter.test.ts`: success path for all three procedures, validation-rejection cases (>10 tags, bad key/value, duplicates, `aws:` prefix), and an S3-error-mapping case (mirror the structure of `bucketPolicyRouter.test.ts`)
- [ ] 3.0 Confirm/wire `capabilities.bucketTagging` from BFF to client
  - [ ] 3.1 Investigate: find where the `capabilities` object (`types/ceph.ts`) is currently populated server-side, and whether any existing tRPC query already exposes it to the client — record the finding before proceeding
  - [ ] 3.2 If not yet exposed, add the field to an existing capabilities-returning query (or add a minimal new one if none exists) so the client can read `capabilities.bucketTagging` for the current project
  - [ ] 3.3 Add or extend a client-side hook to surface the flag to components (follow existing hook conventions under the Ceph client route tree, e.g. alongside `hooks/` in the Storage route)
  - [ ] 3.4 Add test coverage for whatever was added in 3.2/3.3 (server test if a query changed, hook/component test if a hook was added)
- [ ] 4.0 Build `BucketTaggingModal` UI and wire it in
  - [ ] 4.1 Add a `"tags"` case to the `ModalType` union in `BucketModals.tsx`
  - [ ] 4.2 Create `BucketTaggingModal.tsx`: key/value row list, "Add tag" row, per-row remove, live "N / 10 tags" counter, inline validation matching the server rules from 1.1–1.3
  - [ ] 4.3 Wire `BucketTaggingModal` into `BucketModals.tsx`'s modal-type dispatcher
  - [ ] 4.4 Add "Manage Tags" / "Add Tags" action to `BucketHeaderActions.tsx` (label toggles the same way the Policy button does), visible only when `capabilities.bucketTagging` is `true` and gated by `storage:containers:read`/`storage:containers:update` via `trpc.storage.canUser`
  - [ ] 4.5 Wire the modal's submit to `bucketTagging.set` (or `.delete` when the user removes every row and confirms); invalidate/refetch the bucket's tag data on success so the UI reflects the new state
  - [ ] 4.6 Add success/error toasts via the existing `BucketToastNotifications.tsx` pattern
  - [ ] 4.7 Write `BucketTaggingModal.test.tsx` (render, add/edit/remove row, validation errors block submit, successful submit calls `set`); extend `index.test.tsx` (or add a dedicated test file if warranted) to cover the menu item appearing/hiding based on capability and permission state
- [ ] 5.0 i18n, quality gates, and docs
  - [ ] 5.1 Wrap all new user-facing strings with Lingui `Trans`/`t`
  - [ ] 5.2 Run `pnpm check-i18n` and confirm the en/de catalogs picked up the new strings
  - [ ] 5.3 Run `pnpm --filter @cobaltcore-dev/aurora test` and confirm all new/changed tests are green
  - [ ] 5.4 Run `pnpm --filter @cobaltcore-dev/aurora typecheck` and `pnpm lint`, fix any issues
  - [ ] 5.5 Update `packages/aurora/docs/009_ceph_s3_bff.md` with the new tagging endpoints (request/response shape, error cases, limits)
  - [ ] 5.6 Add a changeset (`pnpm changeset`) describing the bucket-tagging feature
