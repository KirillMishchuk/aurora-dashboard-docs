# Contract: `storage.ceph.lifecycle` tRPC Router

New sub-router mounted at `trpc.storage.ceph.lifecycle` (alongside `trpc.storage.ceph.bucketPolicy` and
`trpc.storage.ceph.versioning`), built with `cephProtectedProcedure`. Schemas per `data-model.md`.

## `lifecycle.get`

**Type**: query
**Permission**: `storage:containers:read`

**Input** (`getLifecycleInputSchema`):
```ts
{ project_id: string; bucket: string }
```

**Output**:
```ts
{ rules: LifecycleRule[] }
```

**Behavior**:
- Calls `GetBucketLifecycleConfigurationCommand({ Bucket: bucket })` via `ctx.getCephClient()`.
- Maps each SDK `LifecycleRule` to the app's `LifecycleRule` shape (`fromSdkLifecycleRule`).
- If the bucket has no lifecycle configuration, S3/RGW returns an error named
  `NoSuchLifecycleConfiguration` — this is **not** an error; return `{ rules: [] }` (mirrors
  `bucketPolicy.get`'s `NoSuchBucketPolicy` handling).
- Any other S3 error → `mapS3ErrorToTRPCError(error, { operation: "get bucket lifecycle configuration", bucket })`.

**Errors**:
- `NOT_FOUND` — bucket does not exist.
- `FORBIDDEN` — no EC2 credentials / access denied (via `cephProtectedProcedure` / `mapS3ErrorToTRPCError`).

## `lifecycle.set`

**Type**: mutation
**Permission**: `storage:containers:update`

**Input** (`setLifecycleInputSchema`):
```ts
{ project_id: string; bucket: string; rules: LifecycleRule[] }
```

**Output**:
```ts
boolean // true on success
```

**Behavior**:
- Full-replace: maps every `rules[i]` to an SDK `LifecycleRule` (`toSdkLifecycleRule`), preserving
  `unsupportedFilter` passthrough fields verbatim (FR-013).
- Server-side re-validation before send (defense in depth, mirroring `bucketPolicy.set`'s pattern):
  - Reject if `rules.length` exceeds a sane hard cap (e.g. 1000, matching S3's documented limit) — actual
    enforcement of the *backend's real* max-rules-per-bucket limit is left to the S3 call itself per FR-015
    ("relies on the backend's rejection at save time").
  - Each rule must have at least one action (`lifecycleRuleSchema`'s `.refine`) — FR-009.
  - Day-count fields must be positive integers (schema-level `z.number().int().positive()`) — FR-010.
- Calls `PutBucketLifecycleConfigurationCommand({ Bucket: bucket, LifecycleConfiguration: { Rules } })`.
- On S3 rejection (e.g. rule-count limit, invalid storage class), the error is mapped via
  `mapS3ErrorToTRPCError` and surfaced to the UI verbatim — no rule is considered saved (FR-015, Edge Cases:
  "storage backend rejects a rule at save time").

**Errors**:
- `BAD_REQUEST` — schema validation failure (missing action, non-positive day count) or S3-side rejection of
  the rule set (e.g. unsupported storage class, malformed filter).
- `NOT_FOUND` — bucket does not exist.
- `FORBIDDEN` — no EC2 credentials / access denied.
- (Backend rule-count-limit rejection surfaces as whatever `mapS3ErrorToTRPCError` maps the RGW error to —
  typically `BAD_REQUEST`; the UI must display the message clearly per FR-015.)

## `lifecycle.delete`

**Type**: mutation
**Permission**: `storage:containers:update`

**Input** (`deleteLifecycleInputSchema`):
```ts
{ project_id: string; bucket: string }
```

**Output**:
```ts
boolean // true on success
```

**Behavior**:
- Calls `DeleteBucketLifecycleCommand({ Bucket: bucket })` — removes the **entire** lifecycle configuration
  (all rules) from the bucket, per the S3 API contract. This procedure is used internally when the last
  rule is deleted from the UI (Edge Cases: "deleting the last remaining rule... returns to the empty
  state") — the client computes the remaining rule list after a row-delete and calls either `set` (if rules
  remain) or `delete` (if none remain).
- Idempotent: `NoSuchLifecycleConfiguration` on delete is not an error, mirrors `bucketPolicy.delete`.

**Errors**:
- `NOT_FOUND` — bucket does not exist.
- `FORBIDDEN` — no EC2 credentials / access denied.

## Client consumption contract

Single-rule "delete" from the UI (Acceptance Scenario 3.3 confirm-before-delete) is implemented as:
compute `remainingRules = currentRules.filter(r => r.id !== targetId)`, then call `lifecycle.set` with
`remainingRules` if non-empty, else call `lifecycle.delete`. This keeps the delete-one-rule UX (FR-012)
correctly mapped onto the S3 API's whole-configuration set/delete semantics, exactly as `bucketPolicy` and
`versioning` already do for their own full-replace operations.

Single-rule "add"/"edit" similarly computes the full desired `rules` array client-side (from the list
already held in the `lifecycle.get` query cache) and calls `lifecycle.set` with it.
