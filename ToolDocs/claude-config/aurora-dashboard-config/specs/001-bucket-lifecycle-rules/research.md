# Phase 0 Research: Ceph Bucket Lifecycle Rules

## 1. Transport & S3 API surface

**Decision**: Use `@aws-sdk/client-s3` (`^3.1042.0`, already a dependency, confirmed present in
`node_modules/.pnpm/@aws-sdk+client-s3@3.1042.0`) commands `GetBucketLifecycleConfigurationCommand`,
`PutBucketLifecycleConfigurationCommand`, `DeleteBucketLifecycleCommand`, called via the existing
`ctx.getCephClient()` (an authenticated `S3Client`, `forcePathStyle: true` for RGW compatibility) inside a
new `lifecycleRouter.ts`, exactly mirroring `bucketPolicyRouter.ts` / `versioningRouter.ts`.

**Rationale**: This is the identical pattern already used for the two closest analogues (bucket policy,
versioning) — same client, same error-mapping helper (`mapS3ErrorToTRPCError`), same procedure builder
(`cephProtectedProcedure`). Ceph RGW implements the S3 `BucketLifecycleConfiguration` API, so no new
transport is needed.

**Alternatives considered**: A dedicated RGW Admin Ops client — rejected, out of scope; the epic explicitly
scopes the BFF surface to `buckets.getLifecycle/setLifecycle/deleteLifecycle`, and the S3-compatible API is
sufficient for all of FR-001–FR-013.

## 2. Lifecycle rule wire shape (AWS SDK `LifecycleRule` model)

**Decision**: Map the spec's Key Entities 1:1 onto the SDK's `LifecycleRule` shape:

| Spec attribute | SDK field |
|---|---|
| name/identifier | `ID` (string, max 255 chars per SDK docs) |
| enabled/disabled | `Status: "Enabled" \| "Disabled"` (`ExpirationStatus` enum) |
| key-prefix scope | `Filter.Prefix` (preferred over the deprecated top-level `Prefix`) |
| expire current objects after N days | `Expiration.Days` (number) |
| transition current objects after N days | `Transitions: [{ Days, StorageClass }]` |
| expire noncurrent versions after N days | `NoncurrentVersionExpiration.NoncurrentDays` |
| transition noncurrent versions after N days | `NoncurrentVersionTransitions: [{ NoncurrentDays, StorageClass }]` |
| abort incomplete multipart uploads after N days | `AbortIncompleteMultipartUpload.DaysAfterInitiation` |

A bucket's full configuration is `GetBucketLifecycleConfigurationOutput.Rules: LifecycleRule[]`, sent back
via `PutBucketLifecycleConfigurationCommand({ Bucket, LifecycleConfiguration: { Rules } })` (full-replace
semantics, same as bucket policy's `set`).

**Rationale**: `AbortIncompleteMultipartUpload` lives as a sibling field on the same `LifecycleRule` object
as `Filter`, so it is inherently scoped by that rule's key-prefix filter — this directly satisfies the
clarified requirement ("multipart-abort action is scoped by the same key-prefix as the rest of the rule")
with no extra modeling needed.

**Alternatives considered**: Using the deprecated top-level `Prefix` field instead of `Filter.Prefix` —
rejected; the SDK marks `Prefix` `@deprecated` in favor of `Filter`.

## 3. Rule-name uniqueness (FR-004)

**Decision**: Client-side validation against the list already fetched by `getLifecycle` before calling
`setLifecycle` (compare the new/edited rule's `ID` against all other rules' `ID`s in the current
in-memory list). No server-side uniqueness check is added.

**Rationale**: The spec's clarification explicitly scopes this to "rejected client-side before save." The
S3 API itself does not enforce rule-ID uniqueness (it's just an array), so nothing prevents a duplicate at
the wire level — the UI is the sole enforcement point, consistent with the clarification.

**Alternatives considered**: Server-side rejection in `setLifecycle` — rejected as unnecessary duplication
of a check the spec already scopes to the client; server-side would also require fetching current state
before every `set`, adding a round trip the spec doesn't ask for.

## 4. Storage-class availability for the transition action (FR-006, Edge Cases)

**Decision**: There is no S3-API call to enumerate a Ceph cluster's configured storage classes/placement
targets (that's an RGW Admin Ops / zonegroup concept, not part of `@aws-sdk/client-s3`), and no such
enumeration exists anywhere in this codebase today (confirmed: `grep` for `StorageClass` outside
pass-through object/version metadata returns nothing). Since discovering this dynamically is out of scope
for this feature (the epic only asks for `getLifecycle`/`setLifecycle`/`deleteLifecycle`), the transition
action's available storage-class list is a **server-side configuration value** (e.g. an env var such as
`CEPH_LIFECYCLE_STORAGE_CLASSES`, comma-separated, surfaced through a small addition to `getLifecycle`'s
output or a separate lightweight config-read procedure) rather than something fetched live from Ceph. When
the configured list is empty/unset, the UI disables the transition action and shows the "transitions are
unavailable" messaging required by FR-006 and Acceptance Scenario 2.4.

**Rationale**: This keeps the feature self-contained within the epic's stated BFF surface while still
satisfying FR-006's requirement to "clearly indicate when no alternate storage class is available" — it
just resolves the *source* of that availability signal (config, not live discovery) which the spec leaves
open. `Transitions[].StorageClass` is typed to the SDK's `TransitionStorageClass` enum (`DEEP_ARCHIVE`,
`GLACIER`, `GLACIER_IR`, `INTELLIGENT_TIERING`, `ONEZONE_IA`, `STANDARD_IA`) at the schema level, but only
the operator-configured subset is actually offered in the UI.

**Alternatives considered**: Building an RGW Admin Ops client to query zonegroup placement targets live —
rejected as disproportionate scope for a P3 feature explicitly bounded to the S3-compatible API surface;
can be revisited later if product wants live discovery.

## 5. Permission keys (FR-014)

**Decision**: Reuse the existing `storage:containers:read` (for `getLifecycle`) and
`storage:containers:update` (for `setLifecycle`/`deleteLifecycle`) permission keys already defined in
`STORAGE_MAPPINGS` (`Storage/routers/permissionRouter.ts`) and backed by `storage_admin`/`storage_viewer` in
`apps/dashboard/src/policies/storage.json`. No new permission keys, no `storage.json` changes.

**Rationale**: Confirmed via research that neither bucket policy nor versioning — the two existing
bucket-configuration features closest to lifecycle rules — have dedicated permission keys; both are gated
purely by `cephProtectedProcedure` (EC2-credential + Ceph RGW IAM) and reuse the generic container
read/update keys. FR-014 asks for "the same permission level already required for other
bucket-configuration actions" — this *is* that existing convention.

**Alternatives considered**: A dedicated `storage:buckets:lifecycle_read`/`storage:buckets:lifecycle_update`
key pair — rejected to stay consistent with the established pattern; can be revisited if product wants
finer-grained control later (would be a non-breaking additive change to `STORAGE_MAPPINGS`).

## 6. Client UI pattern

**Decision**: Model the feature on the existing `Buckets/` component folder:

- Header trigger: add a "Lifecycle Rules" entry to `BucketHeaderActions.tsx`'s action menu, opening
  `activeModal: "lifecycle"` in `BucketModals.tsx` (same dispatch pattern as `"policy"`/`"enableVersioning"`).
- Rule list: `LifecycleRulesModal.tsx`, calling `trpcReact.storage.ceph.lifecycle.get.useQuery(...)` and
  rendering a `DataGrid` of rules with a per-row `PopupMenu` (`Edit`/`Delete`), modeled directly on
  `ObjectVersionHistoryModal.tsx`'s version-list table.
- Add/edit: `LifecycleRuleFormModal.tsx`, a single component handling both create and edit (pass an
  optional `existingRule` prop), using `@tanstack/react-form` + a Zod `formSchema` for client validation
  (uniqueness check from research #3, "at least one action" per FR-009, positive-integer day counts per
  FR-010), modeled on `BucketPolicyModal.tsx`'s form usage.
- Delete confirm: `DeleteLifecycleRuleModal.tsx`, modeled directly on `DeleteBucketPolicyModal.tsx` /
  `DeleteVersionModal.tsx` (dedicated per-action confirm modal on `juno-ui-components`' `Modal` with
  `confirmButtonVariant="primary-danger"` — there is no shared generic confirm-delete component in this
  codebase, so none is introduced here).
- On success, invalidate `utils.storage.ceph.lifecycle.get` (same cache-invalidation pattern as the other
  bucket-config mutations) and surface toasts via the existing `BucketToastNotifications.tsx` helpers.
- All UI strings via `<Trans>`/`t` macro (`@lingui/react/macro`), consistent with every other Storage
  component.

**Rationale**: Every piece of this has a direct, working precedent in the same folder; deviating would
introduce inconsistency without benefit. FR-013 ("must not silently discard unsupported filter
conditions like object-tag filters") is satisfied by round-tripping the full raw `LifecycleRule` object
fetched from `get` through to `set` for fields the edit form doesn't expose (e.g. `Filter.Tag`/`Filter.And`)
— the form only overwrites the fields it renders controls for.

**Alternatives considered**: A dedicated route (`.../lifecycle/index.tsx`) instead of a modal — rejected;
none of the other bucket-configuration features (policy, versioning) use a dedicated route, and SC-001
("within 2 clicks from the bucket detail view") is naturally satisfied by the existing header-action →
modal flow already used for those features.

## 7. Testing pattern

**Decision**: Server: `lifecycleRouter.test.ts` using `createCallerFactory(auroraRouter(lifecycleRouter))`,
`vi.mock("../../clients/s3Client", () => ({ createS3Client: vi.fn(() => ({ send: mockSend })) }))`, and the
shared `routers/ceph/mockContext.ts` (`createMockContext`, `TEST_PROJECT_ID`) — identical structure to
`bucketPolicyRouter.test.ts`/`versioningRouter.test.ts`. Client: RTL + `userEvent`, `trpcReact` namespace
mocked per-procedure, wrapped in `I18nProvider`/`PortalProvider`, identical structure to
`BucketPolicyModal.test.tsx`.

**Rationale**: Constitution Principle III requires colocated tests matching CI; reusing the established
mock infrastructure (`mockContext.ts`) avoids duplicating fake-credential/catalog setup.
