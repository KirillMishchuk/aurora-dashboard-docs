---
type: plan
date: 2026-10-13
status: not-implemented
issue: [1024]
---
# Plan: Cinder Volumes page in Compute (list, details, create, edit, delete, extend, attach/detach)

**Date:** 2026-10-13 · **Status:** not implemented
**Base:** `main` @ `6a8dad69`
**Reviewed:** 5 findings, 5 fixed

## Overview

This plan adds a Block Storage (Cinder) **Volumes** page to the project's Compute section, per GitHub epic #1024. Users can list volumes (search, status filter, sort, pagination), open a details page with attachments, and create, edit (name/description), delete, extend (`available` only), attach and detach volumes. Attach and detach go through Nova.

The BFF lives in the Compute domain as `compute.volumes.*`. Actions are gated by new `compute:volumes:*` keys on the Compute `canUser` router. The Cinder rules come from a new **optional** `volume.json` policy file: if an operator doesn't have it, the server still starts and the Cinder-backed actions stay hidden.

## Decisions

- **D1 Placement → Compute section.** Routes `/projects/$projectId/compute/volumes` and `/projects/$projectId/compute/volumes/$volumeId`. BFF in `Compute/`, namespace `compute.volumes.*`, nav item "Volumes" under Compute. Keys `compute:volumes:{create,update,delete,extend,attach,detach}` on the Compute permission router.
- **D2 Policy file → optional `volume.json`.** New `optional: true` flag on `EngineDef`. A missing file logs a warning, the server starts, and that engine's keys resolve to `false`.
- **D3 Delivery shape → one plan**, verified once at the end. No phases.
- **D4 Edit volume (name/description) → included.**
- **D5 Extend → `available` only**, with no Cinder microversion header. In-use extend (Cinder 3.42) is listed under Proposed follow-ups.
- **Defaults the user accepted:**
  - List pagination follows the Routers pattern.
  - Server names are added best-effort.
  - The list and details refetch every 5 s while an actively-changing status is present.
  - The volume service is looked up as `volumev3`, then `block-storage`, both via `hasService`.
  - Nova detach is called with the `volume_id`; a server picker appears when a multiattach volume has several attachments.
  - "Attached Volumes" on Instance Details is a follow-up.

## Architecture Analysis

**Current state:**

- **No Cinder code exists anywhere, and there is no Instances UI.** `client/routes/_auth/projects/$projectId/compute/index.tsx` only redirects to the project overview. The Compute section has `images` and `flavors`. Each has a layout route (e.g. `compute/flavors.tsx`) whose `beforeLoad` redirects to `/projects/$projectId` when the catalog lacks the service.
- **Compute BFF mounting.** `server/Compute/routers/index.ts` builds `compute: auroraRouter({...serverRouter, ...flavorRouter, ...imageRouter, ...keypairRouter, ...serverGroupRouter, ...buildPermissionRouter(policyDir)})`. Network mounts sub-namespaces as properties (`routers: routersRouter` in `server/Network/routers/index.ts`). We'll mount `volumes: volumeRouter` the same way.
- **Compute permissions.** `server/Compute/routers/permissionRouter.ts` has two engines, `compute` (`compute.json`) and `image` (`image.json`). Its existing keys predate the naming convention (`servers:list`, `flavors:create`); the new keys follow `PERMISSION_KEY_PATTERN.md`. `compute.json:161-165` already defines `os_compute_api:os-volumes-attachments:{index,show,create,update,delete}`.
- **Policy loading is eager and throws.**
  - `createPermissionRouter.ts:90-92` calls `loadPolicyEngine` for every engine when the router is built.
  - `policyEngineLoader.ts` throws `Policy file "<name>" not found…` when the file is in neither `policyDir` nor the nonexistent `permission_custom_policies/`.
  - Missing *rules* already resolve to `false` per key (#1362, `MISSING_RULE_MESSAGE`).
- **signal-openstack behaviour.**
  - `session.service(name)` never returns null. It always returns a service object, and the endpoint is resolved lazily per request by catalog `type` OR `name` (`packages/signal-openstack/src/session.ts:95-98`, `token.ts:84`). `session.hasService(name)` is the only reliable existence check.
  - Relative paths are appended to the endpoint URL (`client.ts:61`); absolute URLs are fetched as-is (`client.ts:54`).
  - Non-2xx responses throw `SignalOpenstackApiError(message, statusCode)`, with the message parsed from the OpenStack error body (`client.ts:201`).
- **`openstackErrorMiddleware` (`trpc.ts`, around lines 20-55)** maps a `SignalOpenstackApiError` cause with status **401, 400, 403 or 404** to a `TRPCError` with a *generic* message. For 400 the message is "The OpenStack request was invalid." So a router must convert upstream errors to `TRPCError` **without `cause`** if Cinder's/Nova's own text should reach the client. Precedent: `mapScopeError` in the same file.
- **Nova microversion detection** already exists: `getMaxMicroversion(compute)` in `server/Compute/helpers/flavorHelpers.ts`. It is module-private today, reads the version document, and falls back to `"2.1"`. `supportsDescriptionField` shows how to compare `major.minor` numerically (handles `2.100`).
- **Patterns to copy:**
  - BFF: `server/Network/routers/routersRouter.ts` (best-effort enrichment, `validateAndEncodeResourceId`), `server/Network/helpers/routerHelpers.ts` (`requestOrThrow`), `server/Network/helpers/index.ts` (`parseOrThrow`), `server/helpers/errorHandling.ts` (`withErrorHandling`).
  - Client list: `network/floatingips/-components/FloatingIpsList.tsx` (`trpcReact` `useQuery`, `FiltersInput`/`SelectedFilters` status filter, URL state via `../urlHelpers.ts`). Pagination and page-in-URL from `network/routers/-components/RoutersList.tsx` + `RouterListContainer.tsx` (`PAGE_SIZE` 50, `Pagination variant="input"`).
  - Client details: `network/routers/$routerId.tsx` (title-only loader, query-driven error with `RouteIdLevelDefaultError`, `useSetBreadcrumb`).
  - Modals: `network/floatingips/-components/-modals/*`. `ReleaseFloatingIpModal` is the TanStack Form + type-to-confirm + `useModalTracking` pattern; also `EditFloatingIpModal`, `AssociateFloatingIpModal` (select fed by a query), `FloatingIpActionModals.tsx` (render-prop orchestrator), `FloatingIpToastNotifications.tsx`, `-hooks/useFloatingIpMutations.ts`.
  - Permissions hook: `useSecurityGroupPermissions` (bulk `canUser` + `select`, `staleTime/gcTime: Infinity`, fail-closed defaults).
  - Nav and overview: `client/routes/_auth/projects/-components/buildNavSections.ts` and `client/routes/_auth/projects/$projectId/index.tsx`. `isEnabled(serviceKey)` handles `enabledServices` + `deniedServices`; service keys are an open string set (`types/appConfig.ts`).
- **UI review rules:** `.github/copilot-instructions.md` Part B. Relevant here: B.2 list zones, B.5 modals, B.6 `Status`, B.8 `can<Verb><Noun>` + fail-closed, B.9 URL state, B.10 toast builders, B.11 TanStack Form + Zod.

**Verified OpenStack behaviour (sources):**

- **Cinder v3 API** (https://docs.openstack.org/api-ref/block-storage/v3/index.html):
  - `GET volumes/detail` accepts `limit`, `marker`, `sort`, `sort_key`/`sort_dir`, `offset`, `with_count`. It returns `volumes` + `volumes_links` (the next link).
  - `POST volumes` → **202**. Only `size` is required. Optional fields: `name`, `description`, `volume_type`, `availability_zone`. "Since the Train release, every volume must have a volume type"; the default type is applied when omitted.
  - `PUT volumes/{id}` (`name`, `description`, `metadata`) → **200**.
  - `DELETE volumes/{id}` → **202**.
    - Allowed statuses: `available`, `in-use`, `error`, `error_restoring`, `error_extending`, `error_managing`.
    - The volume must not be migrating, attached, awaiting transfer, in a group, or have snapshots. `cascade` would delete the snapshots; we don't send it.
  - `POST volumes/{id}/action {"os-extend":{"new_size":N}}` → **202**. "Prior to microversion 3.42 the volume status must be `available`"; `reserved` is not valid. The status becomes `extending` while it runs.
  - Statuses: `creating, available, reserved, attaching, detaching, in-use, maintenance, deleting, awaiting-transfer, error, error_deleting, backing-up, restoring-backup, error_backing-up, error_restoring, error_extending, downloading, uploading, retyping, extending`.
  - `attachments[]` entries carry `server_id, attachment_id, attached_at, host_name, volume_id, device, id`. `bootable` is a **string**. `GET types` returns `volume_types` including a `__DEFAULT__` placeholder that should not be offered.
- **Cinder microversion history** (https://docs.openstack.org/cinder/latest/contributor/api_microversion_history.html): 3.42 adds in-use extend. Not used here.
- **Cinder policy rule names** (https://docs.openstack.org/cinder/latest/configuration/block-storage/samples/policy.yaml.html): `volume:get_all`, `volume:get`, `volume:create`, `volume:update`, `volume:delete`, `volume:extend`, `volume:extend_attached_volume`, `volume_extension:type_get_all`.
- **Nova API** (https://docs.openstack.org/api-ref/compute/):
  - Attach: `POST /servers/{server_id}/os-volume_attachments {"volumeAttachment":{"volumeId":…}}` → **200** for microversions 2.0–2.100. The response body is `volumeAttachment` with `device`, `id` (until 2.88), `serverId`, `volumeId`. Attach is asynchronous ("callers should poll the status … of the volume"). The libvirt driver ignores `device`.
  - Shelved servers can be attached from 2.20. Multiattach volumes are supported "From v2.60". Below 2.60 Nova rejects **any** attach of a volume with `multiattach: true`, even the first one, with 400 "Multiattach volumes are only supported starting with compute API version 2.60" (`check_attach_and_reserve_volume` → `MultiattachNotSupportedOldMicroversion`).
  - Detach: `DELETE /servers/{server_id}/os-volume_attachments/{volume_id}` → **202**. The path parameter is the **volume ID**, not the Cinder attachment ID; the issue's blueprint is wrong here. Detach is asynchronous.

**Proposed changes:**

- **Server:**
  - `server/policies/createPermissionRouter.ts`: optional engines.
  - `apps/dashboard/src/policies/volume.json`: reference Cinder policy.
  - `server/Compute/routers/permissionRouter.ts`: add the optional `volume` engine and six `compute:volumes:*` keys.
  - New `server/Compute/types/volume.ts`, `server/Compute/helpers/volumeHelpers.ts`, `server/Compute/helpers/volumeStatus.ts`, `server/Compute/routers/volumeRouter.ts`, mounted as `compute.volumes`. Procedures: `list`, `getById`, `listVolumeTypes`, `listAttachableServers`, `create`, `update`, `delete`, `extend`, `attach`, `detach`.
  - `attach` sends `OpenStack-API-Version: compute 2.60` when Nova supports it, reusing `getMaxMicroversion`, which gets exported from `flavorHelpers.ts`.
- **Client:**
  - Catalog helper `hasVolumeService`, nav item and overview card with service key `volumes`.
  - Routes `compute/volumes.tsx` (layout, guard, crumb, error), `compute/volumes/index.tsx` (list), `compute/volumes/$volumeId.tsx` (details).
  - Components and modals under `compute/volumes/-components/`, hooks under `-hooks/`.
- **Docs and release:** `README.md` service keys, `PERMISSION_KEY_PATTERN.md`, `PERMISSION_ROUTER_IMPLEMENTATION.md`, design doc `packages/aurora/docs/0017_volumes_bff.md`, a changeset, and i18n catalogs.
- **Why this fits:** every piece mirrors an existing feature: Routers (list/detail BFF, pagination), Floating IPs (modals, mutations, toasts), Flavors (Compute layout guard, Nova microversion detection). The only cross-cutting change is the backwards-compatible `optional` engine flag.

## Potential Problems & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| A new required policy file would stop `createServer()` from starting for every consumer without `volume.json` | High | `optional: true` engine. A missing file logs one startup warning and its keys return `false` (Step 1). Unit-tested. |
| Nova rejects any attach of a `multiattach: true` volume below compute 2.60 (400), and we would otherwise send no header (= 2.1) | High | `attach` reads Nova's max microversion via `getMaxMicroversion` (exported from `flavorHelpers.ts`) and sends `OpenStack-API-Version: compute 2.60` when max ≥ 2.60. The response is still the 200 `volumeAttachment` body; `id` stays until 2.88. If Nova is older, no header is sent, and Attach is disabled in the UI for multiattach volumes via `attachMultiattachSupported` from `listAttachableServers` (Step 5). Tested. |
| The Cinder catalog entry can be `volumev3` (legacy) or `block-storage` (newer), and the endpoint path may be `…/v3/{project_id}` or `…/v3` | High | `getVolumeService` checks `hasService("volumev3")`, then `hasService("block-storage")`, and uses relative paths (`volumes/detail`). Endpoint shape is an assumption; see Live-environment checks. |
| `service()` never returns null, so `service(a) ?? service(b)` and `validateOpenstackService(service(...))` can't detect a missing service | Medium | Gate on `ctx.openstack?.hasService(...)` everywhere: `getVolumeService` throws "Volume service is not available"; `getComputeServiceOrNull` returns `null`, and attach/detach/listAttachableServers throw `INTERNAL_SERVER_ERROR` "Compute service is not available" on `null` (Steps 4 and 5). |
| `openstackErrorMiddleware` replaces Cinder/Nova 400 text with "The OpenStack request was invalid." (and generic 401/403/404 messages), hiding actionable errors such as dependent snapshots | Medium | `volumeRequestOrThrow` converts every `SignalOpenstackApiError` into a `TRPCError` carrying the upstream message and **no `cause`**, so the middleware leaves it alone. A test asserts a Cinder 400 dependent-snapshots message reaches the caller verbatim. |
| **[PERF]** The list walks every Cinder page and makes one Nova call for server names; with polling that repeats | Medium | `limit=1000` per page, cap `MAX_VOLUME_PAGES = 10`. Server names come from one best-effort `GET servers`. Polling only while a status in `POLLING_VOLUME_STATUSES` is present. That set leaves out long-lived states (`awaiting-transfer`, `reserved`, `maintenance`), so a volume parked for days doesn't poll forever. TanStack doesn't poll background tabs by default. |
| Following Cinder's absolute `volumes_links` `href` would let a compromised upstream redirect the BFF (SSRF; the signal client accepts absolute URLs) | Medium | **[SECURITY]** Never fetch the `href`. Extract only the `marker` (`new URL(href).searchParams.get("marker")`) and build our own relative path. |
| Attach, detach, extend, create and delete are asynchronous (202/200 before the work finishes) | Medium | Toasts say "requested"/"started". Invalidate on settle, then poll while a polling status is present. |
| Nova rejects attach for some server states (409) or across availability zones (`cross_az_attach=False` → 400) | Medium | The picker lists only `ACTIVE`, `SHUTOFF`, `PAUSED` servers (`SUSPENDED` is excluded: Nova's `attach_volume` state check doesn't allow it at any microversion; still verified live) and labels each with its AZ. Nova's message is shown inline in the still-open modal. |
| Cinder quota exceeded is 413 (`overLimit`), which no existing mapper handles | Low | `volumeRequestOrThrow` maps 413 → `CONFLICT` with Cinder's message, following the Routers quota → `CONFLICT` precedent. |
| The `volume.json` role names (`volume_admin`, `volume_viewer`) are a guess for the reference app | Low | The changeset tells operators to copy their Cinder rules. The mock token has `member`, so all keys are true locally. |
| The new nav item appears automatically under default-open `appConfig`/`enabledServices` | Low | Same as Routers (#1355). Documented in the changeset; consumers can deny `volumes`. |
| Snapshots block deletion (Cinder 400) while snapshots are out of scope | Low | Cinder's message is shown inline in `DeleteVolumeModal` (verbatim, see above). `cascade` is not sent. |
| A multiattach volume has several attachments, and detach must target one server | Low | `DetachVolumeModal` shows a server `Select` when `attachments.length > 1`. |
| Existing Compute keys (`servers:list`) don't follow the naming pattern while the new ones do | Low | Leave the existing keys alone. |

## Prerequisites

- [ ] **Extend the personal local mock** (`/Users/kirylmishchuk/projects/SAP/local-mock-backend/fake-backend.js`). It is outside the repo; no repo code changes for it.
  - **Catalog:** add a `volumev3` service in `catalogFor()` (around line 870), e.g. `{ type: "volumev3", name: "cinderv3", endpoints: [{ interface: "public", region: CATALOG_REGION, region_id: CATALOG_REGION, url: \`${BASE}/volume/v3/${PROJECT_ID}\` }] }`. Add a `MOCK_VOLUME=none` knob that omits it.
  - **Router:** route the first path segment `volume` → new `handleVolume`.
  - **`handleVolume` endpoints:**
    - `GET volumes/detail`: honour `limit`/`marker`; emit `volumes_links` with an absolute `href` containing `marker=`.
    - `GET volumes/{id}`.
    - `POST volumes`: 202, status `creating`, then `available` after about 3 s.
    - `PUT volumes/{id}`.
    - `DELETE volumes/{id}`: 202. Return 400 `{"badRequest":{"message":"Volume still has 1 dependent snapshots."}}` for a seeded volume flagged as having snapshots; 400 for attached volumes. Remove the volume after about 3 s.
    - `POST volumes/{id}/action` `os-extend`: 202, `extending`, then `available` with the new size. 400 when `new_size <= size` or the status isn't `available`.
    - `GET types`: include `__DEFAULT__`, `standard`, `premium`.
  - **Nova, in `handleCompute`** (around line 1246): `POST servers/{id}/os-volume_attachments` and `DELETE servers/{id}/os-volume_attachments/{volume_id}`.
    - Flip the volume through `attaching`→`in-use` and `detaching`→`available`, and maintain `attachments[]`.
    - The POST returns 400 "Multiattach volumes are only supported starting with compute API version 2.60" when the volume has `multiattach: true` and the request's `OpenStack-API-Version` is missing or below `compute 2.60`. The mock's version document already advertises `NOVA_MAX_MICROVERSION` (default 2.96).
  - **Seeds:**
    - `available` "data-vol-01" (10 GiB, `standard`)
    - `in-use` "db-vol-01" on `demo-db-01` at `/dev/vdb`
    - `error` "broken-vol"
    - "snap-vol" (`available`, flagged as having snapshots)
    - `available` multiattach "shared-vol-free" (no attachments)
    - multiattach "shared-vol" attached to both seeded servers
    - a bootable volume
    - an `awaiting-transfer` volume
    - a volume belonging to a foreign project
    - a knob or batch giving more than 50 volumes for pagination
  - Document the new fixtures in the mock's `README.md`.
- [ ] No dependency bumps or upstream releases are needed.

## Implementation Steps

### Step 1: Support optional policy engines in `createPermissionRouter` [CAREFUL]

**Files to modify/create:**

- `packages/aurora/src/server/policies/createPermissionRouter.ts`: optional engine handling
- `packages/aurora/src/server/policies/createPermissionRouter.test.ts`: tests
- `PERMISSION_ROUTER_IMPLEMENTATION.md` (repo root): document the flag

**What to do:**

1. Extend `EngineDef` to `{ fileName: string; optional?: boolean }`. JSDoc: "When true, a missing policy file is not fatal: the engine is skipped with a warning and every key mapped to it resolves to `false`."
2. Rewrite the `loadedEngines` construction to iterate `config.engines`:
   - Non-optional engines → `loadPolicyEngine` as today.
   - Optional engines → wrap the call in `try/catch`. If the caught `Error`'s message matches `/^Policy file ".*" not found/` (the loader's wording in `policyEngineLoader.ts`), log once with `console.warn(\`Optional policy file "${fileName}" not found in policyDir; permissions mapped to engine "${name}" will be denied.\`)` and skip the engine. Rethrow any other error, e.g. a malformed file.
3. Change the mapping-validation loop to check `Object.hasOwn(config.engines, mapping.engine)`, i.e. *configured* engines rather than loaded ones.
4. In `checkSinglePermission`, before the existing `if (!engine) throw …`: if the engine isn't loaded but `config.engines[mapping.engine]?.optional` is true, `return false`. Don't log per call. Keep the throw for non-optional engines.
5. In `PERMISSION_ROUTER_IMPLEMENTATION.md`, add a short "Optional engines" subsection with an example (`volume: { fileName: "volume.json", optional: true }`) and the semantics above.

**Expected outcome:**

- A router whose optional engine file is missing builds and answers `false` for that engine's keys.
- Other engines' keys behave as before.

**Verification:**

- `pnpm --filter @cobaltcore-dev/aurora test src/server/policies/createPermissionRouter.test.ts`. New cases:
  - (a) optional engine whose loader throws "not found" → the router builds, `console.warn` is called once, and in a single batch its key is `false` while another engine's key is `true`.
  - (b) optional engine whose loader throws a different error → router creation throws.
  - (c) a missing non-optional engine still throws.
  - (d) a mapping that references an unconfigured engine still throws "Configuration error".

---

### Step 2: Add the `volume.json` reference policy and the `compute:volumes:*` keys [SECURITY]

**Files to modify/create:**

- `apps/dashboard/src/policies/volume.json`: new file. `apps/dashboard/vite.config.mjs:44` already copies the whole directory.
- `packages/aurora/src/server/Compute/routers/permissionRouter.ts`: new engine and keys
- `packages/aurora/src/server/Compute/routers/permissionRouter.test.ts`: tests
- `PERMISSION_KEY_PATTERN.md`: add a "Compute (`compute:*`), Volumes" block

**What to do:**

1. Create `volume.json`, modelled on the header of `compute.json`:
   ```json
   {
     "context_is_admin": "role:volume_admin",
     "owner_or_no_project": "project_id:%(project_id)s",
     "member": "role:member and rule:owner_or_no_project",
     "viewer": "role:volume_viewer and rule:owner_or_no_project",
     "admin": "role:volume_admin and rule:owner_or_no_project",
     "context_is_volume_admin": "rule:context_is_admin or rule:admin",
     "context_is_editor": "rule:context_is_volume_admin or rule:member",
     "context_is_viewer": "rule:context_is_editor or rule:viewer",
     "volume:get_all": "rule:context_is_viewer",
     "volume:get": "rule:context_is_viewer",
     "volume:create": "rule:context_is_editor",
     "volume:update": "rule:context_is_editor",
     "volume:delete": "rule:context_is_editor",
     "volume:extend": "rule:context_is_editor",
     "volume_extension:type_get_all": "rule:context_is_viewer"
   }
   ```
2. In `permissionRouter.ts`, add `volume: { fileName: "volume.json", optional: true }` to `engines`.
3. Add these keys to `COMPUTE_IMAGE_MAPPINGS`, under a `// Volumes (Cinder; attach/detach go through Nova)` comment:
   - `"compute:volumes:create": { engine: "volume", rule: "volume:create" }`
   - `"compute:volumes:update": { engine: "volume", rule: "volume:update" }`
   - `"compute:volumes:delete": { engine: "volume", rule: "volume:delete" }`
   - `"compute:volumes:extend": { engine: "volume", rule: "volume:extend" }`
   - `"compute:volumes:attach": { engine: "compute", rule: "os_compute_api:os-volumes-attachments:create" }`
   - `"compute:volumes:detach": { engine: "compute", rule: "os_compute_api:os-volumes-attachments:delete" }`

   Update the docblock. Add no read/list keys: reads are never gated in this repo.
4. In `PERMISSION_KEY_PATTERN.md`, list the six keys with one-line comments, and note that attach/detach map to Nova rules because Nova performs the operation.

**Expected outcome:**

- `compute.canUser` accepts the six keys.
- Without `volume.json`, the four Cinder keys resolve `false`, and attach/detach still follow `compute.json`.

**Verification:**

- `pnpm --filter @cobaltcore-dev/aurora test src/server/Compute/routers/permissionRouter.test.ts`, with new cases for the keys, plus one where the mocked loader throws `Policy file "volume.json" not found` only for `volume.json`.

---

### Step 3: Add Zod schemas for volumes, volume types, attachments and procedure inputs

**Files to modify/create:**

- `packages/aurora/src/server/Compute/types/volume.ts`: new
- `packages/aurora/src/server/Compute/types/volume.test.ts`: new

**What to do:**

1. **Status constants.**
   - Export `VOLUME_STATUSES`: an `as const` array of the 20 statuses above.
   - Make `volumeStatusSchema = z.string()`, so an unknown future status still parses.
   - Status sets live in Step 4's `volumeStatus.ts`, not here.
2. **`volumeAttachmentSchema`:** `z.object({ id: z.string().optional(), attachment_id: z.string().optional(), server_id: z.string(), volume_id: z.string().optional(), device: z.string().nullish(), host_name: z.string().nullish(), attached_at: z.string().nullish() })`.
3. **`volumeSchema`:** `id: z.string()`, `name: z.string().nullish()`, `description: z.string().nullish()`, `status: volumeStatusSchema`, `size: z.number()`, `volume_type: z.string().nullish()`, `bootable: z.string().nullish()`, `attachments: z.array(volumeAttachmentSchema).default([])`, `availability_zone: z.string().nullish()`, `multiattach: z.boolean().nullish()`, `encrypted: z.boolean().nullish()`, `created_at: z.string().nullish()`, `updated_at: z.string().nullish()`, `snapshot_id: z.string().nullish()`, `source_volid: z.string().nullish()`, `metadata: z.record(z.string(), z.string()).nullish()`.
   - Wrappers: `volumeListResponseSchema = z.object({ volumes: z.array(volumeSchema), volumes_links: z.array(z.object({ href: z.string(), rel: z.string() })).optional() })` and `volumeResponseSchema = z.object({ volume: volumeSchema })`.
4. **`volumeListItemSchema`:** `volumeSchema.extend({ attachments: z.array(volumeAttachmentSchema.extend({ server_name: z.string().optional() })) })`. Export the type `VolumeListItem`; `getById` returns it too.
5. **Volume types:** `volumeTypeSchema = z.object({ id: z.string(), name: z.string(), description: z.string().nullish(), is_public: z.boolean().optional() })` and `volumeTypeListResponseSchema = z.object({ volume_types: z.array(volumeTypeSchema) })`.
6. **Attachable servers:**
   - `attachableServerSchema = z.object({ id: z.string(), name: z.string().nullish(), status: z.string().optional(), "OS-EXT-AZ:availability_zone": z.string().nullish() })` and `attachableServerListResponseSchema = z.object({ servers: z.array(attachableServerSchema) })`.
   - Output type `AttachableServersResult = { servers: { id: string; name: string; status?: string; availability_zone?: string | null }[]; attachMultiattachSupported: boolean }`.
7. **Nova attach response:** `volumeAttachmentResponseSchema = z.object({ volumeAttachment: z.object({ device: z.string().nullish(), id: z.string().optional(), serverId: z.string(), volumeId: z.string() }) })`.
8. **Inputs**, each a `projectScopedInputSchema.extend(...)` from `@/server/trpc`:
   - `VolumeListInputSchema`: `searchTerm?`, `status?`, `sort_key?` (enum `"name","status","size","created_at"`), `sort_dir?` (enum `"asc","desc"`).
   - `VolumeIdInputSchema`: `volume_id: z.string().min(1)`.
   - `VolumeCreateInputSchema`: `name?: z.string().trim().max(255)`, `description?: z.string().max(255)`, `size: z.number().int().min(1)`, `volume_type?: z.string().min(1)`.
   - `VolumeUpdateInputSchema`: `volume_id`, `name?: z.string().max(255)`, `description?: z.string().max(255)`.
   - `VolumeExtendInputSchema`: `volume_id`, `new_size: z.number().int().min(1)`.
   - `VolumeAttachInputSchema` and `VolumeDetachInputSchema`: `volume_id`, `server_id: z.string().min(1)`.
   - Export the inferred types.

**Expected outcome:**

- Real Cinder payloads parse: string `bootable`, empty `attachments`, null `name`.

**Verification:**

- `volume.test.ts`: a Cinder API-ref example parses; `attachments` defaults to `[]`; an unknown status is accepted; create rejects `size` 0 and 1.5; extend rejects a non-integer `new_size`; the attach response parses both with and without `id`.

---

### Step 4: Add the volume BFF helpers and status predicates [SECURITY]

**Files to modify/create:**

- `packages/aurora/src/server/Compute/helpers/volumeHelpers.ts`: new
- `packages/aurora/src/server/Compute/helpers/volumeHelpers.test.ts`: new
- `packages/aurora/src/server/Compute/helpers/volumeStatus.ts`: new. This is the **single location** for status sets and predicates; server and client both import from it.
- `packages/aurora/src/server/Compute/helpers/volumeStatus.test.ts`: new
- `packages/aurora/src/server/Compute/helpers/flavorHelpers.ts`: export the existing `getMaxMicroversion`. This is a visibility change only; the behaviour is unchanged.

**What to do:**

1. **`getVolumeService(ctx)`:**
   - `const s = ctx.openstack`.
   - If `s?.hasService("volumev3")`, return `s.service("volumev3")`.
   - Else if `s?.hasService("block-storage")`, return `s.service("block-storage")`.
   - Otherwise throw `new TRPCError({ code: "INTERNAL_SERVER_ERROR", message: "Volume service is not available" })`.
2. **`getComputeServiceOrNull(ctx)`:** `ctx.openstack?.hasService("compute") ? ctx.openstack.service("compute") : null`.
   - Also add `requireComputeService(ctx)`, which calls it and throws `new TRPCError({ code: "INTERNAL_SERVER_ERROR", message: "Compute service is not available" })` on `null`.
   - Do **not** use `validateOpenstackService(service(...))`: `service()` always returns an object, so that check never fires.
3. **`volumeRequestOrThrow<T>(request: () => Promise<T>)`:**
   - Await the request. Catch `SignalOpenstackApiError` and throw `new TRPCError({ code, message: error.message })` **without `cause`**, so `openstackErrorMiddleware` (`trpc.ts`) doesn't replace Cinder's/Nova's text with its generic 400/401/403/404 messages. Comment this, citing `mapScopeError`.
   - Code map: `{400: "BAD_REQUEST", 401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT", 413: "CONFLICT"}`; anything else → `INTERNAL_SERVER_ERROR`.
   - Rethrow other errors unchanged; `withErrorHandling` normalises them.
   - Model it on `requestOrThrow` in `Network/helpers/routerHelpers.ts`, but keep it self-contained in Compute.
4. **Path helpers.**
   - `volumePath(volumeId, suffix?: "action")`: `validateAndEncodeResourceId(volumeId, "Volume")` → `volumes/${id}` or `volumes/${id}/action`.
   - `serverAttachmentPath(serverId, volumeId?)`: `servers/${enc(serverId)}/os-volume_attachments[/${enc(volumeId)}]`, using `validateAndEncodeResourceId(…, "Server")` / `(…, "Volume")`.
5. **`extractNextMarker(links?)`:**
   - Find the entry with `rel === "next"`, then return `new URL(href).searchParams.get("marker") ?? undefined`.
   - Wrap in try/catch → `undefined`. **Never return or follow the `href`.**
6. **`filterAndSortVolumes(volumes, { searchTerm, status, sort_key = "name", sort_dir = "asc" })`:**
   - Case-insensitive substring match across `name`, `id`, `description`, `volume_type` and attachments' `server_name`/`server_id`.
   - Exact `status` match.
   - String sort via `localeCompare` (null → `""`); numeric sort for `size`.
7. **Server names.**
   - `applyServerNames(volumes, servers: {id, name}[])` adds `server_name` to attachments where it resolves.
   - `fetchServerNames(compute | null)`: `[]` when `null`. Otherwise best-effort `GET servers?limit=1000`, parsed with `z.object({ servers: z.array(z.object({ id: z.string(), name: z.string().nullish() })) })`; `[]` on any failure, as `fetchNetworkSummaries` in `routersRouter.ts` does.
8. **`NOVA_MULTIATTACH_MICROVERSION = "2.60"` and `isMicroversionAtLeast(version: string, min: string): boolean`:** a numeric `major.minor` comparison like `supportsDescriptionField` in `flavorHelpers.ts`, so `2.100` > `2.60`.
9. **`volumeStatus.ts`.** Pure code: no imports of `TRPCError` or signal-openstack, so the client can import it.
   - `BUSY_VOLUME_STATUSES`, used for the badge's `warning` variant: `creating, attaching, detaching, deleting, extending, reserved, maintenance, downloading, uploading, retyping, backing-up, restoring-backup, awaiting-transfer`.
   - `POLLING_VOLUME_STATUSES`, short-lived states only, which drive refetch: `creating, attaching, detaching, deleting, extending, downloading, uploading, retyping, backing-up, restoring-backup`. Deliberately leave out `awaiting-transfer`, `reserved` (also covers shelved servers) and `maintenance`, which can last for days.
   - `DELETABLE_VOLUME_STATUSES`: `available, error, error_restoring, error_extending, error_managing`.
   - Predicates, named to avoid clashing with the permission booleans:
     - `isBusyVolume(v)`
     - `isTransitionalVolume(v)` (status ∈ `POLLING_VOLUME_STATUSES`)
     - `isAttachable(v)` (status `available`)
     - `isDetachable(v)` (status `in-use` && `attachments.length > 0`)
     - `isExtendable(v)` (status `available`)
     - `isDeletable(v)` (status ∈ `DELETABLE_VOLUME_STATUSES` && no attachments)
     - `isEditable(v)` (status ≠ `deleting`)
   - `getVolumeRefetchInterval(volumes: { status: string }[] | undefined): number | false` → `5000` if any `isTransitionalVolume`, else `false`.

**Expected outcome:**

- Pure, tested helpers that the router and the client compose.

**Verification:**

- `volumeHelpers.test.ts`:
  - service fallback order (`volumev3`, then `block-storage`, else throw)
  - `getComputeServiceOrNull` → `null` when `hasService("compute")` is false, and `requireComputeService` throws "Compute service is not available"
  - error mapping (400/401/403/404/409/413), with the upstream message preserved and the `TRPCError` carrying no `cause`
  - `extractNextMarker` with an absolute href, no next link, a malformed href
  - path helpers reject `../x`
  - filter and sort combinations
  - `isMicroversionAtLeast("2.100","2.60") === true`, `("2.59","2.60") === false`
- `volumeStatus.test.ts`:
  - every predicate for `available`, `in-use`, `in-use` with no attachments, `error`, `creating`
  - `getVolumeRefetchInterval([{status:"creating"}]) === 5000`
  - `getVolumeRefetchInterval([{status:"awaiting-transfer"}]) === false`, and the same for `reserved` and `maintenance`
  - `getVolumeRefetchInterval([{status:"available"}]) === false`

---

### Step 5: Implement `volumeRouter` and mount it as `compute.volumes` [SECURITY] [PERF]

**Files to modify/create:**

- `packages/aurora/src/server/Compute/routers/volumeRouter.ts`: new
- `packages/aurora/src/server/Compute/routers/volumeRouter.test.ts`: new
- `packages/aurora/src/server/Compute/routers/index.ts`: add `volumes: volumeRouter`

**What to do:**

1. Export `volumeRouter = { list, getById, listVolumeTypes, listAttachableServers, create, update, delete, extend, attach, detach }`.
   - Each procedure is `projectScopedProcedure.input(<schema>)`, with its body inside `withErrorHandling(async () => …, "<operation>")`.
   - Parse responses with a Compute-local copy of `parseOrThrow` in `volumeHelpers.ts`, to avoid importing Compute→Network.
   - Wrap every OpenStack call in `volumeRequestOrThrow`.
2. **`list`:**
   - Loop: build `volumes/detail?` + `appendQueryParamsFromObject({ limit: 1000, marker })` (`@/server/helpers/queryParams`), then `GET`, parse, and accumulate.
   - `marker = extractNextMarker(...)`. Stop when there is no marker, or after `MAX_VOLUME_PAGES = 10`; at the cap, `console.warn("volumeRouter.list: page cap reached")`.
   - Then `applyServerNames(volumes, await fetchServerNames(getComputeServiceOrNull(ctx)))`, then `filterAndSortVolumes(...)`.
3. **`getById`:** `GET volumes/{id}` → `volumeResponseSchema` → the same best-effort name enrichment as `list`.
4. **`listVolumeTypes`:** `GET types` → drop `name === "__DEFAULT__"` → sort by name.
5. **`listAttachableServers`:**
   - `const compute = requireComputeService(ctx)`.
   - `GET servers/detail` → parse → map to `{ id, name: name ?? id, status, availability_zone }`.
   - Keep `status` ∈ `ATTACHABLE_SERVER_STATUSES = ["ACTIVE", "SHUTOFF", "PAUSED"]`. Add a comment citing the Nova API ref and noting that SHELVED/SHELVED_OFFLOADED need ≥ 2.20 and are left out for now, and that SUSPENDED is not attachable at any microversion (`nova/compute/api.py`, `attach_volume`: `@check_instance_state(vm_state=[ACTIVE, PAUSED, STOPPED, RESIZED, SOFT_DELETED, SHELVED, SHELVED_OFFLOADED])` has no `SUSPENDED`).
   - Sort by name.
   - Also return `attachMultiattachSupported: isMicroversionAtLeast(await getMaxMicroversion(compute), NOVA_MULTIATTACH_MICROVERSION)`. The client uses it to disable Attach for multiattach volumes on old Nova.
6. **`create`:**
   - Body: `{ volume: pickDefined({ size, name: name || undefined, description: description || undefined, volume_type }) }`. Copy `pickDefined` from `routerHelpers.ts` into `volumeHelpers.ts`.
   - `POST volumes` → parse `volumeResponseSchema` → return the volume. Never forward `project_id`; it is only for rescoping.
7. **`update`:** `PUT volumes/{id}` with `{ volume: { ...(name !== undefined && { name }), ...(description !== undefined && { description }) } }`. An empty description clears it. Return the parsed volume.
8. **`delete`:** `DELETE volumes/{id}`, with no `cascade` → `true`.
9. **`extend`:** `POST volumes/{id}/action` with `{ "os-extend": { new_size } }` → `true`. No microversion header (D5).
10. **`attach`:**
    - `const compute = requireComputeService(ctx)`; `const max = await getMaxMicroversion(compute)`.
    - `POST serverAttachmentPath(server_id)` with `{ volumeAttachment: { volumeId: volume_id } }`.
    - Options: `isMicroversionAtLeast(max, NOVA_MULTIATTACH_MICROVERSION) ? { headers: { "OpenStack-API-Version": "compute 2.60" } } : undefined`. Use the same `headers` option shape as `flavorHelpers.ts`. Pin exactly 2.60, not `max`, so the response contract stays the 200 `volumeAttachment` body.
    - Parse `volumeAttachmentResponseSchema` → return `{ device }`.
    - Comment: below 2.60 Nova rejects any attach of a multiattach volume (`MultiattachNotSupportedOldMicroversion`).
11. **`detach`:** `const compute = requireComputeService(ctx)`; `DELETE serverAttachmentPath(server_id, volume_id)`. The path takes the **volume ID** → `true`.
12. **Mount** in `Compute/routers/index.ts`: import `volumeRouter` and add `volumes: volumeRouter` inside `compute: auroraRouter({...})` next to the spreads.

**Expected outcome:**

- `trpcClient.compute.volumes.*` is typed end to end, and `AuroraRouter` still compiles.

**Verification:**

- `pnpm --filter @cobaltcore-dev/aurora test src/server/Compute/routers/volumeRouter.test.ts`, following the caller and mock-context setup of `routersRouter.test.ts`. Cases:
  - Multi-page walk using only `marker`: the second call's path is relative and contains `marker=`. Page cap.
  - Name enrichment, including Nova failure and `hasService("compute") === false` → no names and no error.
  - Search, status filter and sort. `__DEFAULT__` is excluded.
  - Create body omits empty fields. Extend body shape.
  - Attach sends `OpenStack-API-Version: compute 2.60` when the mocked version document reports `2.96`, and no header when it reports `2.59`.
  - Detach path uses `volume_id`.
  - Attach/detach/listAttachableServers throw "Compute service is not available" when `hasService("compute")` is false.
  - `listAttachableServers.attachMultiattachSupported` reflects the max microversion.
  - A Cinder 400 `SignalOpenstackApiError("Volume still has 1 dependent snapshots.", 400)` on `delete` reaches the caller as `BAD_REQUEST` **with that exact message**, not "The OpenStack request was invalid.". Run it through a caller built with `auroraRouter`, so the middleware is in the chain.
  - 413 → `CONFLICT` with Cinder's message.
  - An invalid `volume_id` (`"../x"`) → `BAD_REQUEST`.
  - `volumev3` missing but `block-storage` present → works.
- `pnpm --filter @cobaltcore-dev/aurora typecheck`; `src/server/routers.test.ts` still passes; `flavorHelpers.test.ts` still passes.

---

### Step 6: Add the catalog check, the nav item and the project-overview card

**Files to modify/create:**

- `packages/aurora/src/client/utils/serviceCatalog.ts` (+ a colocated test)
- `packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.ts`
- `packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.test.ts`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/index.tsx`

**What to do:**

1. In `serviceCatalog.ts`, add:
   - `export const VOLUME_SERVICE_TYPES = ["volumev3", "block-storage"] as const`
   - `export const hasVolumeService = (serviceIndex: Record<string, Record<string, boolean>>): boolean => VOLUME_SERVICE_TYPES.some((type) => Object.keys(serviceIndex[type] ?? {}).length > 0)`

   The lookup is by type, with any name; add a comment pointing at `getVolumeService`.
2. In `buildNavSections.ts`, append to `computeServices` after Flavors: `...(hasVolumeService(serviceIndex) && isEnabled("volumes") ? [{ service: "volumes", label: t\`Volumes\`, navigate: (nav: NavigateFn) => nav({ to: "/projects/$projectId/compute/volumes", params: { projectId } }), params: { projectId } }] : [])`. The `to` path only type-checks once Step 7's routes generate the route tree, so do Steps 6 and 7 together.
3. In `$projectId/index.tsx`, after the Flavors card: `if (hasVolumeService(serviceIndex) && isEnabled("volumes")) cards.push({ group: t\`Compute\`, label: t\`Volumes\`, to: \`${base}/compute/volumes\`, service: "volumes" })`.

**Expected outcome:**

- "Volumes" appears under Compute in the nav and on the overview only when the catalog has a volume service and `volumes` isn't excluded by `enabledServices` or `deniedServices`.

**Verification:**

- `buildNavSections.test.ts`: present with `volumev3`; present with `block-storage` only; absent without either; absent with `enabledServices: ["images"]`; absent with `deniedServices: ["volumes"]`.
- A `hasVolumeService` unit test.

---

### Step 7: Add the Volumes routes (layout guard, list, details) [CAREFUL]

**Files to modify/create:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/volumes.tsx`
- `.../compute/volumes/index.tsx`
- `.../compute/volumes/$volumeId.tsx`
- `.../compute/volumes/urlHelpers.ts`
- `.../compute/volumes/-hooks/useVolumePermissions.ts` (+ test)
- `.../compute/volumes/-components/`: `VolumesList.tsx`, `VolumeListContainer.tsx`, `VolumeTableRow.tsx`, `VolumeActionsMenu.tsx`, `VolumeStatusBadge.tsx`, `VolumeDetailsView.tsx`, `VolumeAttachmentsTable.tsx`, each with a `*.test.tsx`
- `packages/aurora/src/client/routeTree.gen.ts`: regenerated, never hand-edited

**What to do:**

1. **`volumes.tsx` (layout).** Shape it like `network/routers.tsx` + `compute/flavors.tsx`:
   - `staticData: { section: "compute", service: "volumes", crumb: { text: msg\`Volumes\` } }`.
   - `beforeLoad`: `getAvailableServices` → `getServiceIndex` → if `!hasVolumeService(serviceIndex)`, `throw redirect({ to: "/projects/$projectId", params: { projectId } })`.
   - `component: () => <Outlet />`.
   - `errorComponent` with a "Back to Volumes" button, as in `RoutersErrorComponent`.
2. **`index.tsx` (list).**
   - `staticData`: `{ section: "compute", service: "volumes", analytics: { name: "compute.volumes.list" } }`.
   - `validateSearch` with the per-field `safeParse` fallback from `network/routers/index.tsx` over `search`, `status` (`z.string()`), `sortBy` (`z.enum(["name","status","size","created_at"])`), `sortDirection`, `page`. Export the type `VolumesSearchParams`.
   - `head`: title `t\`Volumes\``.
   - Render `<ContentHeader title={t\`Volumes\`} projectId={projectId} />` + `<VolumesList key={projectId} />`.
3. **`useVolumePermissions(projectId)`:**
   - Query: `trpcReact.compute.canUser.useQuery({ project_id, permission: ["compute:volumes:create","compute:volumes:update","compute:volumes:delete","compute:volumes:extend","compute:volumes:attach","compute:volumes:detach"] }, { enabled: Boolean(projectId), select: ([a, b, c, d, e, f]) => ({ canCreateVolume: a, canUpdateVolume: b, canDeleteVolume: c, canExtendVolume: d, canAttachVolume: e, canDetachVolume: f }), staleTime: Infinity, gcTime: Infinity })`.
   - All values default to `false`. Return `{ permissions, isLoading, isError }`.
4. **`VolumesList.tsx`.** Data and filter wiring like `FloatingIpsList.tsx`; pagination math and URL page like `RoutersList.tsx`.
   - Query: `trpcReact.compute.volumes.list.useQuery({ project_id, searchTerm: search || undefined, status, sort_key: sortBy ?? "name", sort_dir: sortDirection ?? "asc" }, { placeholderData: keepPreviousData, refetchInterval: (query) => getVolumeRefetchInterval(query.state.data) })` **[PERF]**.
   - Zone 1 (`Stack distribution="between" className="pb-2"`): `SortInput` (Name / Status / Size (GiB) / Created; labels match the table headers) + a `Button variant="primary"` "Create Volume", only when `permissions.canCreateVolume`.
   - Zone 2 (`DataGridToolbar`): `FiltersInput` with one filter `{ displayName: t\`Status\`, filterName: "status", values: [...VOLUME_STATUSES] }`, a `SearchInput` (500 ms debounce, `replace` while typing), and `SelectedFilters`.
   - `urlHelpers.ts` handles the single-value `status` param, copying the status parts of `network/floatingips/urlHelpers.ts`. Every sort, filter or search navigation sets `page: undefined`.
   - Client-side `PAGE_SIZE = 50`, with `page` in the URL.
   - States:
     - First load: `<Status status="progress" title={t\`Loading Volumes...\`} />`.
     - Error with no cached rows: `<Status status="error" title={t\`Failed to Load Volumes\`} body={error.message} action={<Button onClick={() => refetch()}>Try Again</Button>} />`.
     - Refetch error with cached rows: a non-blocking `Message variant="error"`.
   - Hosts `CreateVolumeModal` (Step 8).
5. **`VolumeListContainer.tsx`:**
   - `DataGrid columns={6} minContentColumns={[5]} cellVerticalAlignment="top"`. Headers: Name, Size (GiB), Status, Volume Type, Attached To, and an empty actions column.
   - Empty row: `Status status="empty"`, title "No Volumes Found". Body depends on `hasSearchOrFilter`: "No volumes match your search or filter. Clear them to view all volumes." or "There are no volumes in this project."
   - `Pagination variant="input"` copied from `RouterListContainer`.
6. **`VolumeTableRow.tsx`:**
   - Clicking the row navigates to the details page.
   - Name cell: `name || id`, with the ID as secondary text when a name exists (two-line pattern from `RouterTableRow`).
   - Size: `{size}`. Status: `<VolumeStatusBadge />`. Volume Type: `volume_type ?? "–"`.
   - Attached To: one line per attachment, `server_name ?? server_id` with `device` as secondary text; `"–"` when there are none.
   - The actions cell uses `stopPropagation` and renders `<VolumeActionsMenu volume={volume} context="row" />`.
7. **`VolumeActionsMenu.tsx`:** `<VolumeActionModals volume>{(triggers) => <PopupMenu>…</PopupMenu>}</VolumeActionModals>`. It takes permissions from `useVolumePermissions` and predicates from `@/server/Compute/helpers/volumeStatus`.
   - Items, in alphabetical order with Delete last after a divider (#1302):
     - "Show Details": row context only.
     - "Attach Volume": rendered when `canAttachVolume && isAttachable(volume)`. `disabled` when `volume.multiattach && attachMultiattachSupported === false`. The flag comes from a `listAttachableServers` query that is only enabled once the menu is opened, or is read inside the modal (see Step 8.8).
     - "Detach Volume": rendered when `canDetachVolume && isDetachable(volume)`.
     - "Edit Volume": rendered when `canUpdateVolume`, `disabled={!isEditable(volume)}`. Details context: omit it here, because the header has it as the primary button.
     - "Extend Volume": rendered when `canExtendVolume`, `disabled={!isExtendable(volume)}`.
     - "Delete Volume": rendered when `canDeleteVolume`, `disabled={!isDeletable(volume)}`.
   - If no item would render, don't render the menu.
8. **`VolumeStatusBadge.tsx`:** `available` → `success`; `in-use` → `info`; status starts with `error` → `error`; `isBusyVolume` → `warning`; anything else → `default`. Text is the raw status.
9. **`$volumeId.tsx` (details).** Copy `network/routers/$routerId.tsx`:
   - `ROUTE_ID`, `HTTP_STATUS_BY_TRPC_CODE`, `RETRYABLE_TRPC_CODES`, and `VolumeLoadError` with "Back to Volumes" / "Home" / "Try Again".
   - The loader only resolves the title and swallows errors.
   - Analytics name `compute.volumes.detail`.
   - Query: `trpcReact.compute.volumes.getById.useQuery({ project_id, volume_id }, { refetchInterval: (q) => getVolumeRefetchInterval(q.state.data ? [q.state.data] : undefined) })`.
   - `useSetBreadcrumb(Route.id, volume?.name || volume?.id)`.
   - Header: `ContentHeader` titled with the volume name or ID. The primary "Edit Volume" button appears when `canUpdateVolume`, disabled when `!isEditable`. Next to it, `<VolumeActionsMenu context="details" />` as "More Actions" (#1278 pattern: one primary action).
10. **`VolumeDetailsView.tsx`:**
    - An `h2` "General Information", then `TwoColumnDescriptionList` with Name, ID (`ClipboardText`), Status (badge), Size (GiB), Volume Type, Bootable (`bootable === "true"` → Yes/No), Availability Zone, Multiattach (Yes/No), Encrypted (Yes/No), Created, Updated, Description (`"—"` when empty).
    - An `h2` "Attachments", then `VolumeAttachmentsTable`: a `DataGrid` with Server (name, ID secondary), Device, Attached At, Host. Empty → `Status status="empty" title={t\`No Attachments\`} body={t\`This volume is not attached to any server.\`}`.

**Expected outcome:**

- The list supports search, filter, sort and pagination, all in the URL.
- Details render, and both views poll only while a short-lived transitional status is present.
- A project without a volume service redirects to the overview. `compute/index.tsx` still redirects.

**Verification:**

- Component tests (provider and mocking setup from `RoutersList.test.tsx`, `RouterListContainer.test.tsx`, `FloatingIpsList.test.tsx`):
  - rows render name, size, badge, type, attached server and device
  - both empty-state texts
  - pagination appears above 50 rows
  - Create is hidden while permissions load or are `false`
  - the menu visibility/disabled matrix for `available`, `in-use`, `error`, and `available` + `multiattach` with `attachMultiattachSupported: false`
  - details shows the attachments table and the copyable ID
  - the badge variant mapping, including `awaiting-transfer` → `warning`
- `pnpm --filter @cobaltcore-dev/aurora typecheck`.

---

### Step 8: Add the modals, mutations hook and toasts for create, edit, delete, extend, attach and detach [CAREFUL]

**Files to modify/create** (under `.../compute/volumes/`, each with a test):

- `-hooks/useVolumeMutations.ts`
- `-components/-modals/VolumeActionModals.tsx`
- `-components/-modals/CreateVolumeModal.tsx`
- `-components/-modals/EditVolumeModal.tsx`
- `-components/-modals/DeleteVolumeModal.tsx`
- `-components/-modals/ExtendVolumeModal.tsx`
- `-components/-modals/AttachVolumeModal.tsx`
- `-components/-modals/DetachVolumeModal.tsx`
- `-components/-modals/VolumeToastNotifications.tsx`

**What to do:**

1. **`useVolumeMutations()`** (modelled on `useFloatingIpMutations`):
   - One `trpcReact.compute.volumes.<op>.useMutation` per operation.
   - `onSettled` invalidates `utils.compute.volumes.list` and `utils.compute.volumes.getById({ project_id, volume_id })`.
   - Exposes `handleX(...)` plus `isXPending`, `xError` (`mutation.error?.message ?? null`) and `resetXError`.
   - No optimistic updates: the operations are asynchronous upstream, and polling shows the real status.
2. **`VolumeToastNotifications.tsx`.** Builders return `{ message, ...NotificationOptions }`:
   - `getVolumeCreateRequestedToast(name)`: "Volume Creation Started" / `Volume "{name}" is being created.`
   - `getVolumeUpdatedToast(name)`
   - `getVolumeDeleteRequestedToast(name)`
   - `getVolumeExtendRequestedToast(name, newSize)`
   - `getVolumeAttachRequestedToast(name, serverName)`
   - `getVolumeDetachRequestedToast(name, serverName)`

   Call sites use `const { message, ...options } = getX(...); toast.success(message, options)`.
3. **`VolumeActionModals.tsx`** (shape of `FloatingIpActionModals.tsx`):
   - A render prop `children(triggers)` exposing `toggleEditModal`, `toggleDeleteModal`, `toggleExtendModal`, `toggleAttachModal`, `toggleDetachModal`. Each toggle resets its mutation's error.
   - After a delete succeeds on the details route (`matches.some(r => r.routeId === "/_auth/projects/$projectId/compute/volumes/$volumeId")`), navigate to the list.
   - The display name is `volume.name || volume.id`.
4. **`CreateVolumeModal`** (`size="large"`): TanStack Form + Zod `onSubmit`.
   - Fields:
     - Name: `TextInput`, optional, max 255, `autoFocus`.
     - Description: `Textarea`, optional, max 255.
     - Size (GiB): `TextInput type="number"`, coerced with `Number(...)`, required integer ≥ 1. Help text: "Size in GiB. Quota limits are enforced by the Block Storage service."
     - Volume Type: `Select` whose first option is "Default" (value `""`, meaning omit the field), then the `listVolumeTypes` results. Disabled while loading. If the list fails, show a `Message variant="error"`: "Volume types could not be loaded. The default type will be used."
   - Confirm button "Create Volume" (`primary`), disabled while the mutation is pending or the form is invalid.
   - Server errors appear in a `Message variant="error"` at the top, and the modal stays open.
   - `useModalTracking({ actionPrefix: "compute.volume.create" })`.
5. **`EditVolumeModal`** (`size="large"`, `key={volume.id}`): copy `EditFloatingIpModal`. Fields: Name (max 255) and Description (max 255, may be empty). "Save" is disabled unless the form is dirty. Send only changed fields. `actionPrefix: "compute.volume.update"`.
6. **`DeleteVolumeModal`** (`size="small"`): copy `ReleaseFloatingIpModal`. Type-to-confirm with `"delete"`. Body: `Volume "{name}" will be permanently deleted. This action cannot be undone.` Confirm button "Delete Volume" (`primary-danger`). Show Cinder's error text inline, e.g. dependent snapshots. `actionPrefix: "compute.volume.delete"`.
7. **`ExtendVolumeModal`** (`size="small"`): show "Current size: {size} GiB". Field "New Size (GiB)": required integer, and a `refine` for `> volume.size` with the message `New size must be greater than {size} GiB.` Confirm button "Extend Volume"; errors inline. `actionPrefix: "compute.volume.extend"`.
8. **`AttachVolumeModal`** (`size="small"`):
   - Data: `trpcReact.compute.volumes.listAttachableServers.useQuery({ project_id })`.
   - A required "Server" `Select`. Option label `{name} ({availability_zone})`, or just `{name}` without an AZ.
   - Show the volume's AZ in the body. Help text: "Only servers in a state that allows attaching are listed. The server and the volume usually need to be in the same availability zone."
   - If `volume.multiattach && data?.attachMultiattachSupported === false`, show `Message variant="error"`: "This multi-attach volume can't be attached: the Compute service is older than API version 2.60." Disable confirm.
   - Loading → `Status status="progress"`. No servers → `Status status="empty" title={t\`No Servers Available\`}`.
   - Confirm button "Attach Volume"; Nova's errors inline. `actionPrefix: "compute.volume.attach"`.
9. **`DetachVolumeModal`** (`size="small"`):
   - With one attachment, the body reads `Volume "{name}" will be detached from server "{server_name ?? server_id}" ({device}).`
   - With more than one, show a required "Server" `Select` listing each attachment.
   - Confirm button "Detach Volume" (`primary-danger`; button only, mid severity per B.5). Call `handleDetach(volume.id, serverId)`. `actionPrefix: "compute.volume.detach"`.
10. **All modals:** pass `disableCancelButton` and `disableCloseButton={isPending}`, and set inputs `disabled` while pending.

**Expected outcome:**

- All six operations work from both the list and the details page.
- Success closes the modal and shows a toast. Failure keeps the modal open with the upstream text.

**Verification:**

- Per-modal tests:
  - confirm stays disabled until the input is valid: `delete` typed; new size ≤ current rejected; size 0 rejected
  - correct handler arguments: Create omits empty fields; Detach passes the chosen `server_id` for multiattach
  - an error `Message` renders from the `error` prop
  - Attach is disabled with the explanation when `multiattach` is true and `attachMultiattachSupported` is `false`
- The mutations-hook test checks both invalidations. Toast builder text tests.

---

### Step 9: Update docs, add the design doc and the changeset

**Files to modify/create:**

- `packages/aurora/README.md`: add `"volumes"` to both "Service key reference" lists (around lines 183 and 210). Also add the missing `"routers"` while editing the same list.
- `packages/aurora/docs/0017_volumes_bff.md`: new. Cover:
  - procedures, Cinder/Nova endpoints with the docs URLs above, status rules
  - the polling set vs the busy set and why long-lived states don't poll
  - marker extraction and why the `href` isn't followed
  - `volumev3`/`block-storage` resolution and `hasService` gating
  - **the attach microversion:** `compute 2.60` is sent when Nova supports it, because Nova rejects any multiattach attach below 2.60; the response contract is unchanged up to 2.100
  - error-text preservation (no `cause`) against `openstackErrorMiddleware`
  - keys and the optional `volume.json`
  - limits: no in-use extend, no AZ selection, no snapshots
- `.changeset/<name>.md`: new, `"@cobaltcore-dev/aurora": minor`. Bullets:
  - new Volumes page under Compute (service key `volumes`, shown when the catalog has `volumev3`/`block-storage`)
  - new `compute.volumes.*` procedures
  - new keys `compute:volumes:{create,update,delete,extend,attach,detach}`
  - new optional policy file `volume.json`; without it the Cinder-backed actions are hidden, and operators should add their rules `volume:create`/`update`/`delete`/`extend`
  - `createPermissionRouter` engines accept `optional: true`

**What to do:**

1. Write the files above. Don't edit `routeTree.gen.ts`; it regenerates on dev/build.

**Expected outcome:**

- Consumer-facing docs match the code.

**Verification:**

- `pnpm format:check`.

---

### Step 10: Run i18n and the CI checks

**Files to modify/create:**

- `packages/aurora/src/locales/{en,de}/messages.po` and the compiled `messages.ts`, both generated. German `msgstr` stays empty, as for the existing Routers strings.

**What to do:**

1. Run `pnpm --filter @cobaltcore-dev/aurora check-i18n` and keep the catalog changes.
2. Run `pnpm --filter @cobaltcore-dev/aurora lint`, `typecheck`, `test` and `build`; `pnpm format:check`; and `pnpm --filter @cobaltcore-dev/dashboard build`, which confirms `volume.json` lands in `dist/policies`.

**Expected outcome:**

- All green, with the changes left uncommitted in the working tree.

**Verification:**

- Every command exits 0.

## Testing Plan

**Unit tests** (vitest, colocated `*.test.ts(x)`):

- [ ] `createPermissionRouter`: optional engine missing → one warning, its keys `false`; other load errors rethrown; a missing non-optional engine still throws; validation checks configured engines.
- [ ] Compute `permissionRouter`: the six keys are accepted. Without `volume.json`, the Cinder keys are `false` and attach/detach follow `compute.json`.
- [ ] `volume.ts`: Cinder sample payloads parse; `attachments` defaults; `bootable` is a string; input bounds; the attach response parses with and without `id`.
- [ ] `volumeHelpers`:
  - [ ] service fallback; `getComputeServiceOrNull`/`requireComputeService`
  - [ ] error mapping keeps the upstream message and sets no `cause`
  - [ ] `extractNextMarker` never yields the href; path validation
  - [ ] filter and sort; `isMicroversionAtLeast`
- [ ] `volumeStatus`: all predicates. `getVolumeRefetchInterval` gives `5000` for `creating` and `false` for `awaiting-transfer`, `reserved`, `maintenance` and `available`.
- [ ] `volumeRouter`:
  - [ ] marker pagination and the page cap
  - [ ] best-effort names
  - [ ] `__DEFAULT__` filtered
  - [ ] method, path and body for every mutation
  - [ ] attach sends `compute 2.60` only when max ≥ 2.60
  - [ ] detach uses `volume_id`
  - [ ] missing compute service → "Compute service is not available"
  - [ ] a Cinder 400 dependent-snapshots message reaches the client verbatim through the middleware chain
  - [ ] 413 → `CONFLICT`; invalid ID → `BAD_REQUEST`
- [ ] `buildNavSections` and `hasVolumeService` across catalog/enabled/denied combinations.
- [ ] Client:
  - [ ] list rows, empty states, pagination, Create gating
  - [ ] the menu matrix, including multiattach on old Nova
  - [ ] details view; badge mapping
  - [ ] each modal's validation and submit
  - [ ] `useVolumeMutations` invalidation; `useVolumePermissions` fail-closed
  - [ ] toast builders

**Manual check on the local mock** (`/Users/kirylmishchuk/projects/SAP/local-mock-backend/` with the Prerequisite extension; run `./run-all.sh`, log in, open `demo-project`):

1. **Nav and guard.** Compute → "Volumes" appears in the nav, and there is a Volumes card on the overview. Restart with `MOCK_VOLUME=none`: both disappear, and `/projects/<id>/compute/volumes` redirects to the overview.
2. **List.**
   - Seeded volumes show; "db-vol-01" is `in-use` with "demo-db-01 /dev/vdb"; the foreign volume is absent.
   - Search "db", the Status filter `error`, and sorting by Size all work, and the URL survives a reload. Pagination appears with more than 50 volumes.
   - With the `awaiting-transfer` volume visible and nothing else transitional, the mock log shows no repeated `GET volumes/detail` every 5 s.
3. **Create.** "test-vol" 2 GiB `premium` → toast, row shows `creating` (warning badge), then `available` within about 5 s with no reload. Size 0 keeps the confirm button disabled.
4. **Edit.** Changing test-vol's name and description updates the details page.
5. **Extend.** Extending to 1 GiB → validation error. Extending to 5 GiB → `extending`, then 5. Extend is disabled for `in-use` volumes.
6. **Attach and detach.**
   - Attach test-vol to demo-web-01 → `attaching` → `in-use`, and the device shows in the Attachments table. Detach → `available`.
   - Attach "shared-vol-free" (multiattach) → succeeds; the mock log shows `OpenStack-API-Version: compute 2.60` on the POST.
   - On "shared-vol", Detach shows the server picker.
   - Restart with `NOVA_MAX_MICROVERSION=2.59`: Attach on "shared-vol-free" is disabled with the explanation, and Attach on "test-vol" still works with no header.
7. **Delete.**
   - Delete is disabled for `in-use` volumes.
   - Deleting "snap-vol" shows "Volume still has 1 dependent snapshots." inline, not "The OpenStack request was invalid."
   - Deleting "broken-vol" after typing `delete` → toast, row disappears.
   - Deleting from the details page returns to the list.
8. **Missing policy file.** Temporarily rename `apps/dashboard/src/policies/volume.json` and restart. The server starts with a warning; Create/Edit/Extend/Delete are hidden while Attach/Detach remain. Restore the file afterwards.

**Live-environment checks:**

- [ ] **Cinder catalog type and endpoint shape** (`volumev3` vs `block-storage`; does the URL end in `/v3/{project_id}`?). Confirmed if `compute.volumes.list` returns data; a 404 on `volumes/detail` refutes it.
- [ ] **Pagination marker.** The `volumes_links` next `href` carries `marker`. Confirmed if a project with more than 1000 volumes (or a lowered `osapi_max_limit`) lists all of them.
- [ ] **Multiattach attach.** Attaching a `multiattach: true` volume succeeds with `compute 2.60`. A 400 "Multiattach volumes are only supported starting with compute API version 2.60" would mean the header wasn't applied.
- [ ] **Policy role names.** Confirmed if the expected roles see Create/Delete; otherwise adjust `volume.json` and the changeset guidance.
- [ ] **Server states and AZs.** Nova attach in `SHUTOFF`/`PAUSED` succeeds (no 409), attach to a `SUSPENDED` server gets 409 (confirms leaving it out), and cross-AZ attach gives a readable inline error.
- [ ] **Quota.** A quota-exceeded create (413 `overLimit`) shows Cinder's message inline.
- [ ] **Dependent snapshots.** Deleting a volume with snapshots shows Cinder's 400 text inline.

**E2E (Playwright):** not part of this change; see Proposed follow-ups.

## Acceptance Criteria

- [ ] "Volumes" appears under Compute (nav and overview) only when the catalog has `volumev3` or `block-storage`, and respects `enabledServices`/`deniedServices` key `volumes`. Otherwise the routes redirect to the overview.
- [ ] The list shows Name, Size (GiB), Status (badge), Volume Type and Attached To (server name and device), with search, status filter, sort and 50-per-page pagination in the URL, and proper loading, empty and error states.
- [ ] The details page shows general info (bootable, AZ, multiattach, encryption), a copyable ID, and an attachments table with device paths.
- [ ] All of these work against the mock, with upstream error text shown verbatim inline:
  - Create (size, name, description, type)
  - Edit (name, description)
  - Delete (type-to-confirm; disabled unless the status is deletable and the volume is unattached)
  - Extend (`available` only; new size > current)
  - Attach (`available`; multiattach volumes attach on Nova ≥ 2.60)
  - Detach (`in-use`; server picker when there are several attachments)
- [ ] The list and details refresh every 5 s only while a short-lived transitional status is present. Volumes in `awaiting-transfer`, `reserved` or `maintenance` don't cause polling.
- [ ] Actions are hidden unless `compute.canUser` grants the matching `compute:volumes:*` key, and permissions default to `false` while loading.
- [ ] A `policyDir` without `volume.json` starts the server, logs a warning and hides the Cinder-backed actions. Existing permission routers are unchanged.
- [ ] The BFF never follows Cinder's absolute pagination `href`, and every resource ID in a path goes through `validateAndEncodeResourceId`.
- [ ] No regressions in Images, Flavors (`getMaxMicroversion` is only exported, not changed), the Network and Storage pages, or existing `canUser` batches.
- [ ] These pass: `pnpm --filter @cobaltcore-dev/aurora lint`, `typecheck`, `test`, `check-i18n`, `build`; `pnpm format:check`; `pnpm --filter @cobaltcore-dev/dashboard build`. A minor changeset for `@cobaltcore-dev/aurora` is present.

## Open Questions

- Disabled `PopupMenuItem` entries in Juno 9.4.0 have no built-in explanation, and Copilot B.8 asks for one. If a reviewer raises it, a short hint in the details page body is enough, e.g. "Detach the volume before deleting it." for `in-use` volumes.
- Does Juno's `TextInput type="number"` return a string? The plan coerces with `Number(...)` either way; check while building the Create and Extend modals.
- Where should the row menu read `attachMultiattachSupported` from? A `listAttachableServers` query enabled only for multiattach rows, or only inside `AttachVolumeModal` (with the menu item always enabled and the modal explaining)? Pick whichever avoids an extra request per row. The modal-only variant is acceptable.

## Follow-ups

- [FOLLOW-UPS.md → item 48](../FOLLOW-UPS.md) — Extend attached (`in-use`) volumes (Cinder microversion 3.42)
- [FOLLOW-UPS.md → item 49](../FOLLOW-UPS.md) — "Attached Volumes" section on Instance Details
- [FOLLOW-UPS.md → item 50](../FOLLOW-UPS.md) — Availability-zone selection when creating a volume
- Not filed: Playwright E2E for the volume lifecycle

Sources:
- Cinder Block Storage API v3 reference: https://docs.openstack.org/api-ref/block-storage/v3/index.html
- Cinder REST API microversion history: https://docs.openstack.org/cinder/latest/contributor/api_microversion_history.html
- Cinder sample policy: https://docs.openstack.org/cinder/latest/configuration/block-storage/samples/policy.yaml.html
- Nova Compute API reference (os-volume_attachments): https://docs.openstack.org/api-ref/compute/

