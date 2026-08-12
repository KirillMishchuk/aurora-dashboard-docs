# Phase 1 Data Model: Ceph Bucket Lifecycle Rules

Source: `spec.md` Key Entities, resolved against the AWS SDK `LifecycleRule` wire shape in `research.md` §2.
Schemas live in `packages/aurora/src/server/Storage/types/lifecycle.ts`, built with
`projectScopedInputSchema.extend({...})` for inputs (per `server/trpc.ts`), following
`types/versioning.ts`'s structure.

## LifecycleRule

The core entity. One bucket has zero or many, order not evaluation-significant (spec Key Entities /
Clarifications).

| Field | Type | Required | Validation | Notes |
|---|---|---|---|---|
| `id` | `string` | yes | 1–255 chars, unique within the bucket's rule set | Maps to SDK `ID`. Uniqueness enforced client-side only (research #3), before calling `set`. |
| `status` | `"Enabled" \| "Disabled"` | yes | enum | Maps to SDK `Status` (`ExpirationStatus`). FR-004. |
| `prefix` | `string` | no (optional; empty = whole bucket) | any string | Maps to SDK `Filter.Prefix`. FR-004. |
| `expiration` | `{ days: number }` \| `undefined` | no | `days` positive integer, no upper bound (FR-010) | Maps to SDK `Expiration.Days`. FR-005. |
| `transition` | `{ days: number; storageClass: string }` \| `undefined` | no | `days` positive integer; `storageClass` one of the server-configured available classes (research #4) | Maps to SDK `Transitions: [{ Days, StorageClass }]` (single entry per rule for this UI's scope — the SDK supports an array for multi-tier transitions, but the add/edit form manages one transition step per rule, consistent with "one or more actions" in FR-004 treating transition as a single action). FR-006. |
| `noncurrentVersionExpiration` | `{ days: number }` \| `undefined` | no | `days` positive integer | Maps to SDK `NoncurrentVersionExpiration.NoncurrentDays`. FR-007. Only meaningful when bucket versioning is enabled (Edge Cases — UI warns otherwise, does not block). |
| `noncurrentVersionTransition` | `{ days: number; storageClass: string }` \| `undefined` | no | same as `transition` | Maps to SDK `NoncurrentVersionTransitions: [{ NoncurrentDays, StorageClass }]`. FR-007. |
| `abortIncompleteMultipartUpload` | `{ daysAfterInitiation: number }` \| `undefined` | no | positive integer | Maps to SDK `AbortIncompleteMultipartUpload.DaysAfterInitiation`. Implicitly scoped by the rule's `prefix` since it's a sibling field on the same `LifecycleRule` (research #2). FR-008. |
| `unsupportedFilter` | passthrough raw SDK `Filter` fragment (e.g. `Tag`, `And`) \| `undefined` | no | none (opaque) | Not rendered as editable UI; preserved verbatim from `get` and echoed back unchanged on `set` so the edit form never drops externally-configured tag filters. FR-013. |

**Validation rule (cross-field)**: at least one of `expiration`, `transition`, `noncurrentVersionExpiration`,
`noncurrentVersionTransition`, `abortIncompleteMultipartUpload` must be present — FR-009 ("at least one
action is required"). Enforced by the client Zod `formSchema` (`.refine(...)`) before submission.

**State transitions**: `status` toggles `Enabled` ↔ `Disabled` via edit (Acceptance Scenario 3.1); no other
state machine — a rule is created, edited (any field), or deleted.

## LifecycleConfiguration (bucket-level)

Not a separate entity in the UI, but the shape actually sent to/received from the S3 API.

| Field | Type | Notes |
|---|---|---|
| `rules` | `LifecycleRule[]` | Full-replace semantics: `setLifecycle` always sends the complete desired rule set, mirroring `bucketPolicy.set`'s full-replace behavior. An empty array (or absent config) is the "no rules configured" empty state (FR-002, Edge Cases: deleting the last rule returns to this state). |

## Bucket (existing entity, referenced not modified)

No schema changes. Lifecycle rules are keyed by `(project_id, bucket)` exactly like `bucketPolicy`/
`versioning` inputs (`projectScopedInputSchema.extend({ bucket: z.string().min(1) })`).

## StorageClass (server-configured, not a persisted entity)

Not stored per-bucket or per-project — a single server-wide (or deployment-wide) list of available
transition target storage classes, sourced from server configuration per research #4. Each entry:

| Field | Type | Notes |
|---|---|---|
| `value` | `string` (subset of SDK `TransitionStorageClass`: `DEEP_ARCHIVE`, `GLACIER`, `GLACIER_IR`, `INTELLIGENT_TIERING`, `ONEZONE_IA`, `STANDARD_IA`) | Offered as `transition.storageClass` / `noncurrentVersionTransition.storageClass` options in the add/edit form. |

If the configured list is empty, the UI disables the transition action entirely and shows the
"transitions unavailable" messaging (FR-006).

## Zod schema sketch

```ts
// packages/aurora/src/server/Storage/types/lifecycle.ts
export const transitionActionSchema = z.object({
  days: z.number().int().positive(),
  storageClass: z.string().min(1),
})

export const dayCountActionSchema = z.object({
  days: z.number().int().positive(),
})

export const lifecycleRuleSchema = z.object({
  id: z.string().min(1).max(255),
  status: z.enum(["Enabled", "Disabled"]),
  prefix: z.string().optional(),
  expiration: dayCountActionSchema.optional(),
  transition: transitionActionSchema.optional(),
  noncurrentVersionExpiration: dayCountActionSchema.optional(),
  noncurrentVersionTransition: transitionActionSchema.optional(),
  abortIncompleteMultipartUpload: z.object({ daysAfterInitiation: z.number().int().positive() }).optional(),
  unsupportedFilter: z.unknown().optional(),
}).refine(
  (rule) =>
    rule.expiration ||
    rule.transition ||
    rule.noncurrentVersionExpiration ||
    rule.noncurrentVersionTransition ||
    rule.abortIncompleteMultipartUpload,
  { message: "At least one action is required" }
)

export const getLifecycleInputSchema = projectScopedInputSchema.extend({ bucket: z.string().min(1) })
export const setLifecycleInputSchema = projectScopedInputSchema.extend({
  bucket: z.string().min(1),
  rules: z.array(lifecycleRuleSchema),
})
export const deleteLifecycleInputSchema = projectScopedInputSchema.extend({ bucket: z.string().min(1) })
```

Server-side mapping functions (`toSdkLifecycleRule` / `fromSdkLifecycleRule`) translate between this schema
and the SDK's `LifecycleRule` shape inside `lifecycleRouter.ts`, analogous to how `versioningRouter.ts` maps
`ObjectVersion` to/from `_Object`/`DeleteMarkerEntry`.
