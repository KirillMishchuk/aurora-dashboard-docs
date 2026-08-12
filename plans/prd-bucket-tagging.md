# PRD: Bucket Tagging (Ceph S3)

> Источник: [Issue #608](https://github.com/cobaltcore-dev/aurora-dashboard/issues/608), Section 14 (P3).
> Сгенерировано `create-prd.md` из `DOCS/ai-dev-tasks/`.

## Introduction/Overview

Aurora Dashboard's Ceph/S3 bucket management (`packages/aurora/src/server/Storage/routers/ceph/`) already supports bucket-level policy (`bucketPolicyRouter`) and versioning (`versioningRouter`), each exposed through a header-action modal on the bucket detail view. Bucket Tagging extends this with key-value labels on Ceph S3 buckets, matching standard S3 tagging semantics (`GetBucketTagging`/`PutBucketTagging`/`DeleteBucketTagging`). Tags let operators organize, filter, and attribute cost/ownership to buckets — a capability currently missing from the dashboard even though the underlying `capabilities.bucketTagging` flag already exists in the BFF's capability schema (`types/ceph.ts`), unused until this feature ships.

**Goal:** let a project member with bucket-management permissions view, add, edit, and remove key-value tags on a Ceph S3 bucket, following the same BFF/UI patterns already established for bucket policies and versioning.

## Goals

1. Expose three tRPC procedures — `storage.ceph.bucketTagging.get`, `.set`, `.delete` — that wrap the AWS SDK v3 `GetBucketTaggingCommand`/`PutBucketTaggingCommand`/`DeleteBucketTaggingCommand` against the project's Ceph RGW endpoint.
2. Ship a "Manage Tags" entry in the bucket header actions menu that opens a key-value tag editor (add/edit/remove rows), consistent with the existing `BucketPolicyModal` interaction pattern.
3. Validate tags against S3's structural limits (see Functional Requirements) both client-side (immediate feedback) and server-side (defense in depth), the same way `bucketPolicyRouter.set` pre-validates size and structure before calling S3.
4. Gate the entire feature behind the existing `capabilities.bucketTagging` flag so it silently does not appear on RGW clusters that don't support tagging.
5. Reuse the existing `storage:containers:read`/`storage:containers:update` permission keys rather than introducing new ones, keeping this consistent with how Policy and Versioning are gated today.

## User Stories

- As a project member managing Ceph buckets, I want to add labels like `environment=prod` or `team=platform` to a bucket so I can identify its purpose and ownership at a glance.
- As a project member, I want to edit or remove an existing tag without having to retype every other tag on the bucket.
- As a project member without bucket-update permission, I want the tag editor to be read-only (or hidden entirely for add/edit/delete), consistent with how other bucket-management actions are already gated.
- As a project member on a Ceph cluster that doesn't support tagging, I want the tagging UI to simply not appear, rather than show me a feature that will fail when I use it.

## Functional Requirements

1. The BFF **must** implement `storage.ceph.bucketTagging.get` (query) — returns the current set of tags for a bucket as an array of `{ key: string, value: string }`, or an empty array if no tags are set (not an error, mirroring how `bucketPolicyRouter.get` treats "no policy set").
2. The BFF **must** implement `storage.ceph.bucketTagging.set` (mutation) — accepts the full desired tag set (array of `{ key, value }`) and replaces all tags on the bucket via `PutBucketTaggingCommand` (S3 tagging is whole-set-replace, not incremental — the client sends the complete list every time, same as how the tag editor state works).
3. The BFF **must** implement `storage.ceph.bucketTagging.delete` (mutation) — removes all tags from the bucket via `DeleteBucketTaggingCommand`. Idempotent: not an error if no tags were set (mirrors `bucketPolicyRouter.delete`'s handling of `NoSuchBucketPolicy`; the tagging equivalent is `NoSuchTagSet`/`NoSuchTagSetError`, filtered the same way).
4. All three procedures **must** be built on `cephProtectedProcedure` (requires resolved EC2 credentials, same as `bucketPolicyRouter`/`versioningRouter`) and registered under `storage.ceph.bucketTagging` in `packages/aurora/src/server/Storage/routers/index.ts`, following the existing `bucketPolicy`/`versioning` registration pattern.
5. `set` **must** validate, before calling S3:
   - Maximum 10 tags per bucket (S3/RGW hard limit).
   - Key: 1–128 characters, non-empty after trim.
   - Value: 0–256 characters.
   - No duplicate keys within the same request.
   - Reject keys starting with the reserved `aws:` prefix.
   On validation failure, throw `TRPCError({ code: "BAD_REQUEST", message: <specific, human-readable reason> })` — one error per violation, not a generic "invalid tags" message (mirrors the per-field error formatting in `bucketPolicyRouter.set`'s Zod-error handling).
6. All S3 errors from the AWS SDK calls **must** be mapped via the existing `mapS3ErrorToTRPCError` helper (`Storage/helpers/s3ErrorMapper.ts`), not surfaced raw.
7. The client-side tag editor **must** replicate the same validation rules as #5 inline, before the user can submit, so invalid input never reaches the server round-trip.
8. The bucket header actions menu (`BucketHeaderActions.tsx`) **must** gain a new action — "Manage Tags" (or "Add Tags" when the bucket currently has zero tags, mirroring the existing "Add Policy" vs. "Edit/View Policy" label toggle on the Policy button) — that opens a new `BucketTaggingModal` component.
9. `BucketTaggingModal` **must** let the user add a new key-value row, edit an existing row's key or value, and remove a row, then submit the full set via `bucketTagging.set` (or `bucketTagging.delete` if the user removes all rows and confirms).
10. The "Manage Tags" action **must only** appear when the current project/cluster's `capabilities.bucketTagging` is `true`; when `false` or absent, the action is omitted entirely from the menu (not shown-disabled).
11. Access to view/edit tags **must** be gated by the existing `storage:containers:read` (view) and `storage:containers:update` (add/edit/delete) permission keys via `trpc.storage.canUser`, consistent with how other bucket actions in `BucketHeaderActions` are gated.
12. i18n: all new user-facing strings **must** be wrapped with Lingui (`Trans`/`t`) and the en/de catalogs regenerated (`pnpm check-i18n`), consistent with the rest of the Buckets UI.
13. Colocated vitest tests **must** cover: the three new router procedures (success, validation-rejection, and S3-error-mapping cases — see `bucketPolicyRouter.test.ts` for the expected shape), and the new modal component (render, add/edit/remove row interactions, submit).

## Non-Goals (Out of Scope)

- **Object-level tagging.** Issue #608 Section 14 scopes this to bucket tagging only. The `capabilities.objectTagging` flag already exists in `types/ceph.ts` but implementing per-object tags is separate, future work.
- **Tag-based filtering or search** of buckets/objects by tag value anywhere in the UI (bucket list, search) — this PRD only covers reading and writing the tag set on a single bucket.
- **New dedicated permission keys** (`storage:containers:read_tags`/`update_tags`) — explicitly decided against for this iteration; reusing the existing container read/update keys.
- **Automated/system tags** (e.g., tags set by lifecycle rules or automation) — this is a manual, user-driven editor only.
- **Cost-allocation or billing integration** using tags — out of scope for the dashboard itself.

## Design Considerations

- New modal `BucketTaggingModal.tsx` in `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/`, structured like `BucketPolicyModal.tsx` (a `ModalType` case wired through `BucketModals.tsx`, triggered from `BucketHeaderActions.tsx`).
- Editor UX: a simple key/value row list with an "Add tag" affordance and a per-row remove (✕) button — no separate "edit mode", editing a key or value is just editing the row's inputs directly before Save, matching the "power-user-facing, junior-dev-implementable" simplicity of the existing Policy JSON editor's surrounding chrome (though tags are structured rows, not raw JSON).
- Show a live count against the 10-tag limit (e.g. "3 / 10 tags") so users see the ceiling before hitting a validation error.
- Follow the existing `BucketToastNotifications.tsx` pattern for success/error toasts after save/delete.
- The "Manage Tags" vs "Add Tags" button label toggle should reuse the same conditional pattern already used for the Policy button in `BucketHeaderActions.tsx` (`hasPolicy ? "Edit/View Policy" : "Add Policy"`).

## Technical Considerations

- AWS SDK v3 commands: `GetBucketTaggingCommand`, `PutBucketTaggingCommand`, `DeleteBucketTaggingCommand` from `@aws-sdk/client-s3` — same import source as the existing bucket policy/versioning commands.
- `GetBucketTaggingCommand` throws `NoSuchTagSet` (exact error name/code should be confirmed against Ceph RGW's actual response, since RGW's S3 error emulation occasionally differs subtly from AWS's) when no tags are set — this must be caught and treated as "empty tag set", not propagated as an error, mirroring the `NoSuchBucketPolicy` handling in `bucketPolicyRouter.get`.
- Router registration: add `bucketTagging: auroraRouter({ ...bucketTaggingRouter })` to the `ceph` object in `Storage/routers/index.ts`, alongside the existing `bucketPolicy`/`versioning` entries.
- Input/output Zod schemas belong in `Storage/types/ceph.ts` alongside the existing bucket policy schemas (`getBucketPolicyInputSchema` etc.) — add `getBucketTaggingInputSchema`, `setBucketTaggingInputSchema`, `deleteBucketTaggingInputSchema`, and a `bucketTagSchema` (`{ key: z.string().min(1).max(128), value: z.string().max(256) }`).
- The `capabilities.bucketTagging` flag already exists in the capabilities schema (`types/ceph.ts:324`) but check where/how capabilities are currently populated and surfaced to the client (query it before assuming the client already receives this value — if it isn't wired to the client yet, wiring it through is itself a prerequisite task, not just a read).
- No new permission mappings needed in `Storage/routers/permissionRouter.ts` — reuse `storage:containers:read`/`storage:containers:update`, per the scope decision above.
- Design doc `packages/aurora/docs/009_ceph_s3_bff.md` is the canonical Ceph BFF reference (status: "implemented, reference") — update it with the new tagging endpoints once shipped, per the KB's `05-domain-map.md` design-doc index.

## Success Metrics

- All three BFF procedures (`get`/`set`/`delete`) ship with passing colocated vitest tests covering success, validation-rejection, and S3-error-mapping paths.
- A user with `storage:containers:update` permission can add, edit, and remove tags on a bucket end-to-end through the UI without a page reload, and the change persists (visible on next `get`).
- The "Manage Tags" action is verifiably absent from the menu when `capabilities.bucketTagging` is `false` (covered by a modal/menu test with both capability states).
- Zero regressions in existing bucket-actions tests (`BucketHeaderActions`, `BucketModals`, `BucketTableView`).

## Open Questions

- Exact current wiring of `capabilities.*` from BFF to client is unconfirmed — needs a quick investigation spike before implementation starts (see Technical Considerations).
- Should the tag key/value inputs warn (not block) on likely-reserved or provider-specific prefixes beyond `aws:` (e.g. any SAP/Ceph-specific reserved prefixes), or is the plain `aws:` check sufficient? Left to the implementer's judgment unless product feedback says otherwise.
- No design mockup exists yet for `BucketTaggingModal` — implementer should follow `BucketPolicyModal.tsx`'s existing visual structure unless a mockup is provided before implementation begins.

---
PRD сгенерирован: 2026-08-04 · на основе кода на коммите `3635f111` (локальная ветка `kirylDev`, origin/main = `f367c07b`)
