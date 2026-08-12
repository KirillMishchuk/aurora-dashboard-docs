# Plan: Restore a deleted Cinder volume from its most recent snapshot

**Date:** 2026-07-23 · **Status:** implemented 2026-07-23 (BFF-only, per Open Question 1 — no client UI shipped this iteration)

## 📋 IMPLEMENTATION PLAN: Cinder volume restore-from-snapshot

### Overview

Add a BFF capability that recreates a deleted Cinder (Block Storage) volume from
the most recent surviving snapshot taken of it. The caller supplies the id of
the volume that no longer exists; the server finds all snapshots whose
`volume_id` matches it, picks the newest by `created_at`, and issues a Cinder
"create volume from snapshot" call, returning the new volume.

### Architecture Analysis

**Current state:**

- 🔴 **Major finding**: this codebase has **no Cinder / Block Storage
  integration at all** — no server domain code, no client route, nothing
  under `packages/signal-openstack` or `packages/aurora/src/server` mentions
  "cinder"/"volume"/"block-storage" (confirmed via repo-wide grep). The
  `05-domain-map.md` KB table lists Compute, Network, Storage (Swift/Ceph),
  Services, Permissions — no Volumes/Cinder row. This plan introduces the
  domain from scratch rather than extending existing code.
- The `Storage` domain (`packages/aurora/src/server/Storage/`) currently only
  covers Swift and Ceph S3 object storage (`routers/swift/`, `routers/ceph/`).
  Block storage is conceptually part of "Storage" from a UI-vocabulary
  standpoint (see permission-key convention below), so this plan adds volumes
  as a third subtree there rather than creating a new top-level domain
  folder.
- Generic OpenStack access pattern (`packages/signal-openstack`):
  `ctx.openstack.service(<catalog type or name>)` resolves a Keystone catalog
  entry by `type === name || name === name` (`packages/signal-openstack/src/service.ts:73`)
  and returns a `{get,post,put,patch,del,...}` client scoped to that service's
  endpoint. Existing domains call this with the endpoint already
  version/tenant-templated by Keystone (e.g. `compute.get("os-keypairs")` in
  `Compute/routers/keypairRouter.ts` — no `/v2.1/{project_id}` prefix needed),
  which is how Nova and (per OpenStack conventions) Cinder register their
  catalog URLs — unlike Neutron, whose floating-IP router prefixes
  `v2.0/floatingips` manually because Neutron's endpoint is not
  tenant-templated. Volume calls in this plan follow the Nova/keypair style
  (relative paths, no manual `v3/{project_id}` prefix).
- Cinder's catalog service `type` has been `volumev3` historically and is
  being migrated to `block-storage` by some deployments (OpenStack service
  types authority). `floatingIpRouter.ts` already has a precedent for this
  exact ambiguity — `listDnsDomains` does
  `ctx.openstack?.service("dns") ?? ctx.openstack?.service("designate")`
  (`Network/routers/floatingIpRouter.ts:172`). This plan follows the same
  fallback pattern for the volume service.
- The most recently added, most idiomatic router in the codebase is
  `Network/routers/floatingIpRouter.ts` (merged with the security-group work,
  commit `cb548a4`): `projectScopedProcedure` + a small `getXService(ctx)`
  helper (`validateOpenstackService` + `ctx.openstack.service(...)`) +
  `parseOrThrow(schema, data, context)` + `withErrorHandling(fn, label)` from
  the generic `@/server/helpers/errorHandling.ts`, with a domain-local
  `XErrorHandlers` object mapping HTTP status → `TRPCError`. This plan follows
  that shape rather than Swift's older `mapErrorResponseToTRPCError`/manual
  style, since it is the newest precedent and keeps Storage internally
  consistent with Network on new work.
- Permissions: `Storage/routers/permissionRouter.ts` builds one `storage`
  policy engine off `apps/dashboard/src/policies/storage.json` via
  `createPermissionRouter`, with a flat `STORAGE_MAPPINGS` object
  (`"storage:resource:action": { engine: "storage", rule: "storage:xxx" }`).
  New volume permissions extend this same map/file rather than introducing a
  second engine — consistent with the "one BFF, one storage policy" model
  already used for Swift+Ceph.
- Router mounting: `Storage/routers/index.ts`'s `buildObjectStorageRouters`
  returns `{ storage: { swift: auroraRouter({...}), ceph: auroraRouter({...}),
  ...buildStoragePermissionRouter(policyDir) } }`. A `volumes:
  auroraRouter({...volumeRouter})` sibling slots in cleanly.
- Precedent for a BFF-only router with **no dedicated client route**:
  `Compute/routers/keypairRouter.ts` — domain map lists its client UI as "—".
  This plan follows that precedent (see Prerequisites/Open Questions).

**Proposed changes:**

- New Zod types: `Storage/types/volume.ts` (`VolumeSchema`,
  `VolumeSnapshotSchema`, list/single response wrappers, restore input
  schema).
- New helpers: `Storage/helpers/volumeHelpers.ts` (`getVolumeService(ctx)`
  with the `volumev3`/`block-storage` fallback, a local `parseOrThrow`, a
  `mostRecentSnapshot(snapshots)` picker, and `VolumeErrorHandlers` mapping
  HTTP status → `TRPCError`, mirroring `Network/helpers/index.ts` +
  `Network/helpers/errorHandling.ts`'s shape but kept local to Storage, same
  as Storage's existing `s3ErrorMapper.ts` is local to Ceph).
- New router: `Storage/routers/volumeRouter.ts` exposing a single
  project-scoped mutation, `restoreFromSnapshot`, that:
  1. Resolves the volume service.
  2. `GET snapshots/detail?volume_id={volume_id}` (Cinder's documented
     filterable list-snapshots-with-details call).
  3. Picks the newest snapshot by `created_at` via `mostRecentSnapshot`; if
     none exist, throws `NOT_FOUND` (Cinder doesn't expose deleted volumes to
     regular list calls, so a caller reaching this code path already has the
     deleted volume's id from elsewhere — e.g. an audit log or the id they
     just tried to delete — and the "not found" case genuinely means no
     surviving snapshot, not a wrong id).
  4. `POST volumes` with `{ volume: { snapshot_id, name, description?, size?
     } }` — Cinder defaults `size` to the snapshot's size when omitted, so
     `size` is optional input only used to grow the restored volume.
  5. Returns the parsed new `Volume`.
- Permission: `storage:volumes:restore` → `{ engine: "storage", rule:
  "storage:volume_restore" }` added to `STORAGE_MAPPINGS`; new rule
  `"storage:volume_restore": "rule:storage_admin"` added to
  `apps/dashboard/src/policies/storage.json` (restoring recreates billable
  infra, so it's gated at the same `storage_admin` level as
  container/object mutations, not `storage_viewer`).
- Mount `volumes: auroraRouter({ ...volumeRouter })` in
  `Storage/routers/index.ts`.

### Potential Problems & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| 🔴 Cinder's catalog service type is ambiguous (`volumev3` vs `block-storage` across deployments) | High | `getVolumeService` tries `volumev3` first, falls back to `block-storage`, matching the existing `dns`/`designate` fallback precedent in `floatingIpRouter.ts` |
| 🔒 A restore call could be used to read snapshot data across projects if `project_id` weren't enforced | Medium | Built on `projectScopedProcedure`, which rescopes the OpenStack token to `input.project_id` before any call — Cinder itself then scopes the snapshot/volume list to that token, so cross-project snapshots are never visible or restorable regardless of what `volume_id` is passed |
| ⚠️ No dedicated permission for *reading* snapshots (only for the combined restore action) | Low | Acceptable for this iteration since the only exposed operation is the combined restore; if a standalone snapshot-browsing UI is added later it needs its own `storage:volumes:read`/`list` key — noted as an Open Question |
| 🐛 Restoring picks the single newest snapshot; if the caller actually wants an older one there's no way to choose | Low (by design — task asks specifically for "most recent") | Out of scope; a future `listSnapshots` + explicit `snapshotId` input would generalize this, noted as an Open Question |
| ⚠️ No client UI is added, so the capability isn't reachable from the dashboard yet | Medium | Matches the existing `keypairRouter` precedent (BFF-only, no route); flagged explicitly below so the user can decide whether a follow-up UI plan is wanted |
| 🐛 Cinder snapshot `created_at` format/precision could tie or be missing | Low | `mostRecentSnapshot` treats a missing/unparseable timestamp as epoch 0 (sorts last) rather than throwing, so a malformed snapshot doesn't crash the whole restore path |

### Prerequisites

- [x] `projectScopedProcedure`, `withErrorHandling`, `validateOpenstackService`, `createPermissionRouter` already exist and need no changes.
- [ ] Decision (defaulted below, see Open Questions): ship BFF-only in this
      iteration, no client route/UI.

### Implementation Steps

#### Step 1: Add volume/snapshot Zod types

**Files to modify/create:**

- `packages/aurora/src/server/Storage/types/volume.ts` (new)
- `packages/aurora/src/server/Storage/types/volume.test.ts` (new)

**What to do:**

1. Define `VolumeSnapshotSchema` (`id`, `volume_id`, `status`, `name`
   nullable/optional, `description` nullable/optional, `size: z.number()`,
   `created_at` optional string, `updated_at` nullable/optional string,
   `metadata` optional `z.record(z.string())`).
2. Define `VolumeSnapshotListResponseSchema = z.object({ snapshots:
   z.array(VolumeSnapshotSchema) })`.
3. Define `VolumeSchema` (`id`, `status`, `name` nullable/optional,
   `description` nullable/optional, `size: z.number()`, `volume_type`
   nullable/optional, `snapshot_id` nullable/optional, `created_at` optional).
4. Define `VolumeResponseSchema = z.object({ volume: VolumeSchema })`.
5. Define `RestoreVolumeFromSnapshotInputSchema =
   projectScopedInputSchema.extend({ volume_id: z.string().trim().min(1,
   "volume_id must be a non-empty string"), name: z.string().trim().min(1)
   .optional(), description: z.string().trim().min(1).optional(), size:
   z.number().int().positive().optional() })` — import
   `projectScopedInputSchema` from `../../trpc` to extend it (matches
   `FloatingIpQueryParametersSchema`-style project scoping).
6. Export inferred TS types for all of the above.
7. Colocated test: valid/invalid parses for each schema (mirror
   `Network/types/floatingIp.test.ts` structure).

**Expected outcome:** typed, validated shapes for every Cinder payload the
router touches.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/types/volume.test.ts`

---

#### Step 2: Add volume helpers (service resolution, parsing, sorting, errors)

**Files to modify/create:**

- `packages/aurora/src/server/Storage/helpers/volumeHelpers.ts` (new)
- `packages/aurora/src/server/Storage/helpers/volumeHelpers.test.ts` (new)

**What to do:**

1. `getVolumeService(ctx: AuroraPortalContext)`: `const openstackSession =
   ctx.openstack; const volume = openstackSession?.service("volumev3") ??
   openstackSession?.service("block-storage"); validateOpenstackService(volume,
   "volumev3"); return volume` — reuse
   `@/server/helpers/validateOpenstackService`.
2. `parseOrThrow<S extends ZodTypeAny>(schema, data, context)`: same shape as
   `Network/helpers/index.ts`'s version (safeParse, console.error +
   `PARSE_ERROR` TRPCError on failure) — duplicated locally rather than
   imported cross-domain, matching how each domain keeps its own copy today.
3. `mostRecentSnapshot(snapshots: VolumeSnapshot[]): VolumeSnapshot |
   undefined`: return `undefined` for an empty array; otherwise sort a copy
   descending by `Date.parse(created_at ?? "") || 0` and return the first
   entry.
4. `VolumeErrorHandlers` object with `listSnapshots` and `restore` functions,
   each taking `(response: {status?, statusText?}, label?: string)` and
   mapping `400/401/403/404/409/412` to the matching `TRPCError` code (same
   map as `Network/helpers/errorHandling.ts`'s `HTTP_STATUS_ERROR_MAP`,
   defined locally here to avoid a cross-domain import) with a
   `INTERNAL_SERVER_ERROR` default.
5. Tests: `getVolumeService` prefers `volumev3`, falls back to
   `block-storage`, throws when neither exists; `mostRecentSnapshot` picks
   the newest, handles ties/missing timestamps, handles empty input;
   `VolumeErrorHandlers` map each status code correctly.

**Expected outcome:** all cross-cutting router logic (service lookup,
parsing, error mapping, "most recent" selection) is unit-tested in isolation.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/helpers/volumeHelpers.test.ts`

---

#### Step 3: Add the `restoreFromSnapshot` router

**Files to modify/create:**

- `packages/aurora/src/server/Storage/routers/volumeRouter.ts` (new)
- `packages/aurora/src/server/Storage/routers/volumeRouter.test.ts` (new)

**What to do:**

1. `projectScopedProcedure.input(RestoreVolumeFromSnapshotInputSchema).mutation(...)`
   named `restoreFromSnapshot`.
2. Wrap the whole body in `withErrorHandling(async () => {...}, "restore
   volume from snapshot")` (from `@/server/helpers/errorHandling`).
3. `const volumeService = getVolumeService(ctx)`.
4. `GET snapshots/detail?volume_id=${encodeURIComponent(input.volume_id)}` →
   on `!response.ok` throw `VolumeErrorHandlers.listSnapshots(response,
   input.volume_id)`; else `parseOrThrow(VolumeSnapshotListResponseSchema,
   await response.json(), "volumeRouter.restoreFromSnapshot (list
   snapshots)")`.
5. `mostRecentSnapshot(snapshots)`; if `undefined`, throw `new TRPCError({
   code: "NOT_FOUND", message: \`No snapshot found for volume
   ${input.volume_id}; it can't be restored\` })`.
6. `POST volumes` with body `{ volume: { snapshot_id: latest.id, name:
   input.name ?? (latest.name ? \`${latest.name}-restored\` :
   \`restored-${input.volume_id}\`), ...(input.description !== undefined &&
   { description: input.description }), ...(input.size !== undefined && {
   size: input.size }) } }` → on `!response.ok` throw
   `VolumeErrorHandlers.restore(response, input.volume_id)`; else
   `parseOrThrow(VolumeResponseSchema, await response.json(),
   "volumeRouter.restoreFromSnapshot (create)").volume`.
7. Return the parsed `Volume`.
8. Tests (mirror `floatingIpRouter.test.ts`'s mock-context style): happy
   path (snapshots present, picks newest, posts correct body, returns
   volume); no snapshots → `NOT_FOUND`; list-snapshots HTTP error → mapped
   `TRPCError`; create HTTP error → mapped `TRPCError`; malformed
   list/create response → `PARSE_ERROR`; missing volume service → error from
   `validateOpenstackService`.

**Expected outcome:** `storage.volumes.restoreFromSnapshot` is callable
end-to-end against a mocked Cinder API and returns the new volume, or a
correctly-typed `TRPCError` for every failure mode.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/routers/volumeRouter.test.ts`

---

#### Step 4: Wire permissions

**Files to modify/create:**

- `packages/aurora/src/server/Storage/routers/permissionRouter.ts`
- `apps/dashboard/src/policies/storage.json`

**What to do:**

1. In `STORAGE_MAPPINGS`, add a new `// Volume Operations (Cinder block
   storage)` section with `"storage:volumes:restore": { engine: "storage",
   rule: "storage:volume_restore" }`.
2. In `storage.json`, add `"storage:volume_restore": "rule:storage_admin"`
   (alongside the existing `container_create`/`object_delete`-style admin
   rules — keep valid JSON, no trailing comma).
3. No existing permission-router test should need changes since this only
   adds a mapping entry and a policy rule (the factory is generic); run the
   existing `Storage/routers/permissionRouter.test.ts` (if present) or the
   `policies/createPermissionRouter.test.ts` suite to confirm nothing broke.

**Expected outcome:** `storage.canUser.query({ project_id, permission:
"storage:volumes:restore" })` resolves against the real `storage_admin` rule.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/routers/permissionRouter.test.ts src/server/policies/createPermissionRouter.test.ts`

---

#### Step 5: Mount the router

**Files to modify/create:**

- `packages/aurora/src/server/Storage/routers/index.ts`

**What to do:**

1. `import { volumeRouter } from "./volumeRouter"`.
2. Add `volumes: auroraRouter({ ...volumeRouter }),` as a sibling of `swift`
   and `ceph` inside the `storage: {...}` object.

**Expected outcome:** `storage.volumes.restoreFromSnapshot` is reachable
through the app router (`packages/aurora/src/server/routers.ts` already
merges `buildObjectStorageRouters(...)`'s output, no change needed there).

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck` (confirms
the router tree still resolves) + `pnpm --filter @cobaltcore-dev/aurora test
src/server/routers.test.ts` if it snapshots the router shape.

---

### Testing Plan

**Unit tests:**

- [ ] `volume.test.ts` — schema parse success/failure for each new schema
- [ ] `volumeHelpers.test.ts` — service fallback, `mostRecentSnapshot`
      ordering/edge-cases, `VolumeErrorHandlers` status mapping
- [ ] `volumeRouter.test.ts` — happy path, no-snapshot 404, upstream HTTP
      errors, malformed-response parse errors, missing service

**Integration tests:**

- [ ] None required (no cross-router integration point beyond the app
      router merge, already covered by Step 5's verification)

**Manual verification:**

1. Not applicable this iteration — no client UI ships, so there's no page to
   click through. Manual verification is via a tRPC caller
   (`createCallerFactory`) test or a direct `curl` against a real/dev
   OpenStack with Cinder, if available.

### Acceptance Criteria

- [ ] `storage.volumes.restoreFromSnapshot` exists, is project-scoped, and
      restores from the newest snapshot of the given `volume_id`
- [ ] Returns `NOT_FOUND` when no snapshot exists for that volume
- [ ] Upstream Cinder HTTP errors are mapped to appropriately-coded
      `TRPCError`s, never leaked as raw fetch errors
- [ ] `storage:volumes:restore` permission key is enforceable via
      `storage.canUser`
- [ ] No regressions in existing Swift/Ceph storage routers or their tests
- [ ] `pnpm --filter @cobaltcore-dev/aurora typecheck`, `lint`, `test` pass

### Open Questions

1. **No client UI in this iteration** — defaulted to BFF-only (precedent:
   `keypairRouter`), since there's no existing Volumes/Snapshots
   list page to hook a "Restore" action into and building one is a
   materially larger, separate scope (list volumes, list snapshots, a
   route, i18n strings, a confirmation modal). If the dashboard should
   surface this to end users, a follow-up plan is recommended once this
   BFF capability lands. Proceeding without blocking, per this task's
   explicit "don't stop to confirm" pre-authorization.
2. **Cinder catalog service type** — defaulted to try `volumev3` then
   `block-storage`. If this deployment's catalog uses a different custom
   type name, `getVolumeService` will need a third fallback or a
   config option (like `cephRegion` is today) — not discoverable without a
   real OpenStack catalog to test against.
3. **`storage:volume_restore` policy rule** — defaulted to `rule:storage_admin`
   (same bar as other mutating storage actions). If restoring a deleted
   volume should be available to regular project members (not just
   admins), the rule should be `rule:storage_viewer` or a new named rule
   instead — this is a product decision, not an architectural one.
