# Plan: Copilot round 2 — Swift `createContainer` metadata leak + `createFolder` server-side existence check

**Date:** 2026-09-10 · **Status:** implemented 2026-09-10

## Overview

Two independent server-side fixes in `packages/aurora/src/server/Storage/routers/swift/swiftRouter.ts` on branch `kiryl-bucket-and-folder-validations`:

1. `createContainer` currently sends the caller's metadata/ACL/quota headers on the very PUT it uses to detect 201-vs-202, so a duplicate create silently mutates the *existing* container before CONFLICT is thrown. Fix: probe-PUT with only the create-only header, apply the rest via a follow-up `POST` only on a genuine 201.
2. `createFolder` has no server-side existence check at all, so a folder that exists outside the client's (unpaginated, Swift-truncated) `listObjects` page is silently overwritten. Fix: make the marker PUT an atomic create-if-not-exists via `If-None-Match: *` and map 412 to CONFLICT — plus fix a real argument-order bug that currently prevents `createFolder` from sending *any* headers at all.

Nothing from `2fa7d63f` / `4677d6b5` is re-litigated: the 201/202 container branch stays, the client-side `existingContainers` / `existingRows` fast-path checks stay.

---

## Research result (settles the Finding 2 approach)

The question the task posed — does Swift/RGW **object-level** PUT support an atomic create-if-not-exists — is **yes**, for both backends. Verified against upstream source, not just docs:

| Source | Evidence |
| --- | --- |
| OpenStack Swift API ref, `api-ref/source/parameters.yaml` → `If-None-Match-put-request` | Documented request header on "Create or replace object": *"In combination with `Expect: 100-Continue`, specify an `If-None-Match: *` header to query whether the server already has a copy of the object before any data is sent."* |
| `swift/proxy/controllers/obj.py` (master) | `ObjectController.PUT`: `if req.if_none_match is not None and '*' not in req.if_none_match: return HTTPBadRequest(... 'If-None-Match only supports *')`; `_check_failure_put_connections` raises `HTTPPreconditionFailed` (412) if **any** backend node reported 412. `Expect: 100-Continue` is a proxy-internal optimisation, **not** a client requirement. |
| `swift/obj/server.py` (master) | `_pre_create_checks`: `if request.if_none_match is not None and orig_metadata: if '*' in request.if_none_match: raise HTTPPreconditionFailed(...)` — the object already exists → 412. |
| Ceph `src/rgw/rgw_rest_swift.cc` → `RGWPutObj_ObjStore_SWIFT::get_params` | Reads `if_nomatch = s->info.env->get("HTTP_IF_NONE_MATCH")` on the **Swift-API** object PUT (the same field the S3 `PutObj` uses). |
| Ceph `src/rgw/driver/rados/rgw_rados.cc` | `if (meta.if_nomatch != NULL) { if (strcmp(meta.if_nomatch, "*") == 0) { if (r == -EEXIST) r = -ERR_PRECONDITION_FAILED; ...` and `check_preconditions`: `if (if_nomatch == "*"sv) { if (current_state.exists) return -ERR_PRECONDITION_FAILED; }` → HTTP 412, enforced at the exclusive-create RADOS write. |

So **Option A (atomic `If-None-Match: *`) is the recommended implementation** — no HEAD-then-PUT half-measure needed for the marker object, matching the "properly fixed" bar already applied to the container race. (This is materially different from the container-level PUT question answered in prior work: there is no conditional-create at the *container* level, which is exactly why containers use the 201/202 signal instead.)

**Client-side error surfacing (verified):** `packages/signal-openstack/src/client.ts` (~lines 194-208) throws `SignalOpenstackApiError(message, response.status)` for any `response.ok === false`. A 412 therefore arrives as a **caught error with `.statusCode === 412`**, not a resolved `Response`. `SignalOpenstackApiError.statusCode?: number` (`packages/signal-openstack/src/error.ts`). Note that `mapErrorResponseToTRPCError` (`Storage/helpers/swiftHelpers.ts:498`) has **no 412 case** — it falls through to `INTERNAL_SERVER_ERROR` — so the 412 must be branched on *before* the mapper is called.

Sources:
- [Swift API reference — Object Storage API](https://docs.openstack.org/api-ref/object-store/?expanded=create-or-replace-object-detail)
- [openstack/swift api-ref/source/storage-object-services.inc](https://github.com/openstack/swift/blob/master/api-ref/source/storage-object-services.inc)
- [openstack/swift api-ref/source/parameters.yaml](https://github.com/openstack/swift/blob/master/api-ref/source/parameters.yaml)
- [openstack/swift swift/obj/server.py](https://github.com/openstack/swift/blob/master/swift/obj/server.py)
- [openstack/swift swift/proxy/controllers/obj.py](https://github.com/openstack/swift/blob/master/swift/proxy/controllers/obj.py)
- [openstack/swift swift/container/server.py](https://github.com/openstack/swift/blob/master/swift/container/server.py)
- [ceph/ceph src/rgw/rgw_rest_swift.cc](https://github.com/ceph/ceph/blob/main/src/rgw/rgw_rest_swift.cc)
- [ceph/ceph src/rgw/rgw_op.cc](https://github.com/ceph/ceph/blob/main/src/rgw/rgw_op.cc)
- [Ceph docs — Swift API object operations](https://docs.ceph.com/en/reef/radosgw/swift/objectops/)

---

## Architecture Analysis

**Current state**

- `packages/aurora/src/server/Storage/routers/swift/swiftRouter.ts`
  - `createContainer` (lines 320-348): `buildContainerMetadataHeaders(options)` → single `swift.put(url, undefined, { headers })` → `if (response.status === 202) throw CONFLICT`.
  - `updateContainerMetadata` (lines 390-411): **the reuse target** — `swift.post(url, undefined, { headers: buildContainerMetadataHeaders(options) })`. Swift container metadata/ACL/quota updates are POSTs to the container URL; this is the existing mechanism, no new one needed.
  - `listObjects` (lines 269-311): one GET, `applyObjectQueryParams` only, no `limit`/`marker` — truncation confirmed.
  - `createFolder` (lines 896-937): raw PUT, no existence check.
- `packages/aurora/src/server/Storage/helpers/swiftHelpers.ts`
  - `buildContainerMetadataHeaders` (line 337): maps `metadata/read/write/versionsLocation/historyLocation/quotaBytes/quotaCount/tempUrlKey/tempUrlKey2` → `X-Container-*`, and `storagePolicy` → `X-Storage-Policy` (line 406).
  - `mapErrorResponseToTRPCError` (line 498): status → TRPCError; handles 400/401/403/404/409/413/422, no 412.
- Client: `…/Swift/Containers/CreateContainerModal.tsx` is the reference pattern for the CONFLICT UX (`error.data?.code === "CONFLICT"` → inline `setNameError`, modal stays open). `…/Swift/Objects/CreateFolderModal.tsx` has no CONFLICT branch and closes unconditionally in `onSettled`.

**Two facts that shape the fix**

1. **`X-Storage-Policy` is create-only and must stay on the PUT.** Verified in `swift/container/server.py`: on a PUT to an existing, non-deleted container, `elif requested_policy_index is not None: if requested_policy_index != broker.storage_policy_index: raise HTTPConflict(...)` — Swift never mutates the policy of an existing container; it either 202s (same policy, no change) or 409s (different policy). So keeping `X-Storage-Policy` on the probe PUT is safe *and* required for correctness. Every other option header **is** applied by a PUT to an existing container (same metadata path as POST) — that's the actual bug.
2. **`createFolder`'s PUT call is currently mis-shaped.** `service.put(path, values, options)` (`packages/signal-openstack/src/service.ts:100` → `client.ts:283`) takes the **body as the 2nd argument**. Current code:

   ```ts
   await swift.put(url, { headers, body: new ArrayBuffer(0) })   // ← headers object IS the body
   ```

   `request()` (`client.ts:105-121`) JSON-stringifies a plain object body and sets `Content-Type: application/json`. So today the folder marker is created with a ~90-byte JSON body `{"headers":{...},"body":{}}` and content-type `application/json`, and **none** of `Content-Type: application/directory` / `Content-Length: 0` / `X-Object-Meta-*` are ever sent. Adding `If-None-Match: *` without fixing this would be a no-op on the wire. `copyObject` (line 773) shows the correct shape: `swift.put(destUrl, undefined, { headers })` with a manual `"Content-Length": "0"` — proof the manual Content-Length pattern works through undici in this codebase.

**Proposed changes** — server-only behavioural changes plus one small client UX change; no schema, no tRPC signature, no public `AuroraApp` prop changes.

---

## Decisions needed (flagging explicitly, per the "no half-measures" precedent)

**D1 — Folder create strategy.** Recommended: **atomic `If-None-Match: *`** (Option A), justified by the source evidence above. The HEAD-then-PUT fallback is *not* needed and should not be used. If the target deployment turns out to run an object-store frontend that ignores `If-None-Match` on PUT, behaviour degrades to exactly today's (silent overwrite) — no regression, but also no protection; that is the only residual risk and it is not detectable from this repo.

**D2 — What happens if the follow-up `POST` (options apply) fails after a successful 201 PUT?** The container now exists but is unconfigured.
- (a) **Recommended:** surface the mapped error to the caller with a message that says the container was created but its settings could not be applied (retry via Edit Container Metadata). No rollback.
- (b) Best-effort rollback: `swift.del(url)` then throw. Destructive-adjacent, racy (a concurrent upload makes the DELETE 409), and can lose a container the user actually wanted.
- Practical note lowering the stakes: `CreateContainerModal.tsx` sends only `{ project_id, container }` — no options — so the follow-up POST is skipped entirely for every UI-driven create today. It only matters for library consumers calling the tRPC procedure directly.

**D3 — Should `createFolder` also reject *implicit* folders (a prefix that exists only because objects live under it, with no marker object)?** `If-None-Match: *` protects the **marker object** only. The client's `buildRows` (`Objects/index.tsx:93-131`) shows a folder row for implicit prefixes too, so the two layers would disagree in that one case (client says "already exists", server would happily create the marker).
- (a) **Recommended:** accept it. Creating a marker for an already-visible implicit folder destroys nothing and surfaces nothing wrong to the user; the harm Copilot identified (silently replacing an existing marker + false "created" toast) is fully closed.
- (b) Add a `GET <container>?prefix=<folderPath>&limit=1` probe before the PUT and throw CONFLICT if non-empty. Catches implicit folders and is immune to listing truncation, but adds a round trip per create and is non-atomic (belt-and-braces on top of the atomic marker check, not a replacement).

**D4 — `listObjects` pagination truncation itself.** Recommended **out of scope** for this round: the authoritative server check removes the *consequence* of truncation for folder creation. Untouched truncation still affects the objects table (a container/prefix with more than Swift's `container_listing_limit`, default 10000 by upstream config, shows a partial listing with no indicator). This repo enforces no limit of its own. Flag as a separate follow-up issue rather than growing this PR.

**D5 — Delivery.** How should this land? Options: leave the working tree dirty for review; amend/extend the existing `.changeset/full-maps-obey.md`; or a new commit on `kiryl-bucket-and-folder-validations`. No commit is assumed by this plan.

---

## Potential Problems & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| `createFolder` PUT arg-order fix changes what is actually stored: markers become 0 bytes + `application/directory` instead of ~90 bytes JSON | Medium | This is a strict improvement and matches `isFolderMarker(name, bytes)` (`swiftHelpers.ts:669`, requires `bytes === 0`), which today never matches Aurora-created markers. Existing markers are unaffected (still render as folders via the `name.endsWith("/")` branch in `buildRows`). Call it out in the changeset. |
| Adding `If-None-Match: *` without fixing arg order = silent no-op | High | Steps ordered so the arg-order fix and the header land together; the server test asserts the exact 3-arg call shape including the header. |
| 412 mapped to `INTERNAL_SERVER_ERROR` by the shared mapper | Medium | Branch on `error.statusCode === 412` **before** calling `mapErrorResponseToTRPCError`, inside `createFolder` only. Do **not** add a global `case 412` to the shared mapper — other Swift ops (conditional copy/`If-Match`) would inherit a wrong CONFLICT semantic. |
| Container create with options is now 2 requests; a partial failure leaves an unconfigured container | Medium | See D2. UI never sends options today. |
| Sending `X-Storage-Policy` on the probe PUT could look like "mutating an existing container" | Low | It cannot: Swift 409s on policy mismatch and no-ops otherwise (`swift/container/server.py` lines ~427-435). The 409 is mapped to CONFLICT by the existing mapper, which reads correctly. |
| Existing tests encode the old call shapes | Medium | Known breakages, listed per-step: `swiftRouter.test.ts:1215` (folder PUT 2-arg assert) must change; container tests need added `post` assertions. Client test `"onSuccess receives correct name even when onSettled fires…"` must keep passing — see Step 5's ref-flag approach. |
| i18n gate (`pnpm check-i18n`) | Low | Reuse the already-extracted string `A folder with this name already exists` for the server-CONFLICT inline error → no new catalog entries. |
| Extra POST per container create | Low | Only when options are supplied; skipped when the built header map is empty. |

---

## Prerequisites

- [ ] D1–D4 confirmed (D1/D3/D4 recommendations are ready to accept as-is; D2 needs a pick).
- [ ] Branch `kiryl-bucket-and-folder-validations` checked out, working tree clean at `4677d6b5`.
- [ ] `pnpm install` up to date.

---

## Implementation Steps

### Step 1: Split `createContainer` into probe-PUT + conditional options-POST

**Files to modify**
- `packages/aurora/src/server/Storage/routers/swift/swiftRouter.ts` — `createContainer`, lines 320-348.

**What to do**

1. Destructure the create-only option out of the rest: after `const { account, container, ...options } = input`, add `const { storagePolicy, ...applyOptions } = options`.
2. Build the probe headers through the same helper so the header-name mapping stays in one place: `const probeHeaders = buildContainerMetadataHeaders({ storagePolicy })`. (With `storagePolicy === undefined` this yields `{}`.)
3. Keep the existing PUT + 202 branch exactly as-is, but pass `probeHeaders`:
   ```ts
   const response = await swift.put(url, undefined, { headers: probeHeaders }).catch((error) => {
     throw mapErrorResponseToTRPCError(error, { operation: "create container", container })
   })

   if (response.status === 202) {
     throw new TRPCError({
       code: "CONFLICT",
       message: `Conflict - create container - container already exists: ${container}`,
     })
   }
   ```
4. Only after the 201 branch is proven, apply the caller's options with a POST, mirroring `updateContainerMetadata` (line 405):
   ```ts
   const optionHeaders = buildContainerMetadataHeaders(applyOptions)
   if (Object.keys(optionHeaders).length > 0) {
     await swift.post(url, undefined, { headers: optionHeaders }).catch((error) => {
       throw mapErrorResponseToTRPCError(error, {
         operation: "apply container settings",
         container,
         additionalInfo: "container was created but its metadata/ACL/quota could not be applied",
       })
     })
   }
   ```
   (If D2 = (b), wrap this in a rollback `swift.del(url)` before rethrowing.)
5. Add a short comment above the probe PUT explaining *why* only `X-Storage-Policy` rides along: it is create-only (Swift 409s on mismatch, never mutates an existing container), while every other `X-Container-*` header would be applied to an already-existing container by an idempotent PUT — which is exactly the bug being fixed.

**Expected outcome** — a duplicate create with options throws CONFLICT having sent zero option headers; a genuine create applies them in a second POST.

**Verification** — `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/routers/swift/swiftRouter.test.ts` (existing container tests must still pass unchanged at this point).

---

### Step 2: Regression tests for `createContainer`

**Files to modify**
- `packages/aurora/src/server/Storage/routers/swift/swiftRouter.test.ts` — `describe("createContainer")`, lines 532-594.

Context you'll need: `buildContainerMetadataHeaders` is `vi.fn().mockReturnValue({})` (line 32 of the mock block) and `vi.clearAllMocks()` in `beforeEach` does *not* clear return values, so per-test overrides via `(swiftHelpers.buildContainerMetadataHeaders as Mock).mockReturnValue(...)` / `.mockImplementation(...)` are the way to make header content assertable (see the account-metadata test at line ~414 for the existing idiom).

**What to do**

1. **New — the Copilot regression test.** `it("does not apply metadata, ACL or quota to a container that already exists", …)`:
   - `mockCtx.mockSwift.put.mockResolvedValue({ ok: true, status: 202, headers: new Headers() })`
   - `(swiftHelpers.buildContainerMetadataHeaders as Mock).mockImplementation((opts) => (opts.metadata ? { "X-Container-Meta-project": "test" } : {}))`
   - call with `{ project_id, container: "existing-container", metadata: { project: "test" }, read: ".r:*", quotaBytes: 1024 }`
   - assert `rejects.toMatchObject({ code: "CONFLICT" })`
   - assert `expect(mockCtx.mockSwift.post).not.toHaveBeenCalled()` ← the core assertion
   - assert the probe PUT carried no option headers: `expect(mockCtx.mockSwift.put).toHaveBeenCalledWith("existing-container", undefined, { headers: {} })`
2. **New** — `it("applies caller options in a follow-up POST only after a 201", …)`: default 201 put mock, same option input, assert `post` called once with the container URL and the option headers, and assert `put` was called **before** `post` (`expect(mockCtx.mockSwift.put.mock.invocationCallOrder[0]).toBeLessThan(mockCtx.mockSwift.post.mock.invocationCallOrder[0])`).
3. **New** — `it("skips the follow-up POST when no options are supplied", …)`: input `{ project_id, container }` only → `expect(mockCtx.mockSwift.post).not.toHaveBeenCalled()`.
4. **Amend** the existing `"should throw CONFLICT when container already exists"` (line 581) with `expect(mockCtx.mockSwift.post).not.toHaveBeenCalled()`; leave its comment and `head` assertion intact.
5. Leave `"treats a 201 response as a successful create"` (line 545) and `"should handle metadata during creation"` (line 562) as they are — both still hold (the latter asserts *any* call to `buildContainerMetadataHeaders` with the metadata, which is now the second call).

**Verification** — the whole `createContainer` describe block green.

---

### Step 3: Make `createFolder` an atomic create-if-not-exists

**Files to modify**
- `packages/aurora/src/server/Storage/routers/swift/swiftRouter.ts` — `createFolder`, lines 896-937.

**What to do**

1. Add `"If-None-Match": "*"` to the `headers` object built at line 909 (keep `Content-Type: application/directory` and `Content-Length: "0"`, keep the `X-Object-Meta-*` loop).
2. **Fix the call shape** (load-bearing — without it no header is sent at all):
   ```ts
   await swift.put(url, new ArrayBuffer(0), { headers }).catch((error) => {
     if (error?.statusCode === 412) {
       throw new TRPCError({
         code: "CONFLICT",
         message: `Conflict - create folder - folder already exists: ${normalizedPath}`,
       })
     }
     throw mapErrorResponseToTRPCError(error, { operation: "create folder", container, object: normalizedPath })
   })
   ```
   Mirror `createContainer`'s CONFLICT message wording so both read consistently in logs.
3. Add a comment recording *why* `If-None-Match: *` is safe and authoritative here (Swift proxy/object-server returns 412; RGW `if_nomatch` → `ERR_PRECONDITION_FAILED`), and that the client-side `existingRows` check remains the fast path, not the guarantee.
4. Do **not** add a `case 412` to `mapErrorResponseToTRPCError`.
5. If D3 = (b), insert the `limit=1` prefix GET probe before the PUT, throwing the same CONFLICT.

**Expected outcome** — creating a folder whose marker already exists returns a CONFLICT `TRPCError` instead of silently overwriting, regardless of what the client's truncated listing showed.

---

### Step 4: Regression tests for `createFolder`

**Files to modify**
- `packages/aurora/src/server/Storage/routers/swift/swiftRouter.test.ts` — `describe("createFolder")`, lines 1204-1227.

**What to do**

1. **Update** the existing `"should successfully create folder"` assertion (line 1215) to the corrected 3-argument shape:
   ```ts
   expect(mockCtx.mockSwift.put).toHaveBeenCalledWith(
     expect.stringContaining("test-container"),
     expect.any(ArrayBuffer),
     expect.objectContaining({
       headers: expect.objectContaining({
         "Content-Type": "application/directory",
         "Content-Length": "0",
         "If-None-Match": "*",
       }),
     })
   )
   ```
2. **New — the Copilot regression test.** `it("throws CONFLICT instead of overwriting an existing folder marker", …)`:
   - `mockCtx.mockSwift.put.mockRejectedValue({ statusCode: 412, message: "Precondition Failed" })`
   - assert `rejects.toMatchObject({ code: "CONFLICT" })`
   - assert `expect(swiftHelpers.mapErrorResponseToTRPCError).not.toHaveBeenCalled()` (proves the 412 never falls through to `INTERNAL_SERVER_ERROR`)
3. **New** — `it("sends If-None-Match on the marker PUT so the check is server-authoritative", …)`: success path, assert the header explicitly (guards against a future refactor dropping it).
4. **New** — `it("passes non-412 errors through the shared error mapper", …)`: `put` rejects with `{ statusCode: 403 }`; set `(swiftHelpers.mapErrorResponseToTRPCError as Mock).mockReturnValue(new TRPCError({ code: "FORBIDDEN" }))`; assert `rejects.toMatchObject({ code: "FORBIDDEN" })`.

**Verification** — `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/routers/swift/swiftRouter.test.ts`.

---

### Step 5: Surface the folder CONFLICT inline in `CreateFolderModal`

**Files to modify**
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Swift/Objects/CreateFolderModal.tsx` (lines 41-59).

Today `onError` unconditionally calls `onError?.(...)` (generic red toast) and `onSettled` unconditionally closes the modal — so a server CONFLICT would flash a technical toast and lose the user's input. Mirror `CreateContainerModal.tsx` (lines 39-49).

**What to do**

1. Add a `const keepOpenRef = useRef(false)` next to `submittedNameRef`; reset it to `false` at the top of `handleSubmit` (before `mutate`).
2. In `onError`:
   ```ts
   onError: (error) => {
     if (error.data?.code === "CONFLICT") {
       keepOpenRef.current = true
       setNameError(t`A folder with this name already exists`)
       return
     }
     onError?.(submittedNameRef.current, error.message)
   },
   ```
   Reuse that **exact existing message string** (already used at line 78) — no new Lingui entry.
3. In `onSettled`, guard the close: `if (keepOpenRef.current) return; handleClose()`.
4. Keep everything else (the `submittedNameRef` comment at lines 37-38, `handleClose`, the client-side `existingRows` check) untouched — the ref-flag approach is chosen specifically so the existing `"onSuccess receives correct name even when onSettled fires and clears state first"` test keeps passing unmodified.

**Expected outcome** — server CONFLICT renders as an inline field error with the modal open and the name preserved, identical to the container flow; all other errors keep the existing toast-and-close behaviour.

---

### Step 6: Client tests for the CONFLICT branch

**Files to modify**
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Swift/Objects/CreateFolderModal.test.tsx` (the `describe("Error handling")` block, ~line 357).

The existing tRPC mock's `mockMutate` calls `capturedOptions.onError?.({ message })`. Widen the captured-options type and the mock error object to carry `data?: { code?: string }`, and add a `mutationErrorCode` alongside `mutationError` (reset in `beforeEach`).

**What to do**

1. `test("shows an inline error and keeps the modal open when the server reports CONFLICT")`: fire `onError({ message: "...", data: { code: "CONFLICT" } })` → assert `screen.getByText(/A folder with this name already exists/i)` is present, `onError` prop **not** called, `onClose` **not** called, and the folder-name input still holds the typed value.
2. `test("still toasts and closes for non-conflict errors")`: existing behaviour, error without `data.code` → `onError` prop called, `onClose` called.
3. Verify the pre-existing `"Submitted name snapshot"` test is untouched and green.

**Verification** — `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Swift/Objects/CreateFolderModal.test.tsx`

---

### Step 7: Changeset + full verification

**Files to modify**
- `.changeset/full-maps-obey.md` (extend the existing entry rather than adding a second one — same PR).

**What to do**

1. Append two sentences: (a) container creation no longer applies caller-supplied metadata/ACL/quota to an already-existing container before reporting the conflict — options are now applied in a follow-up POST only after a genuine 201; (b) folder creation is now server-authoritative via an atomic `If-None-Match: *` conditional PUT (412 → CONFLICT), which also fixes folder markers being written as a JSON blob instead of a zero-byte `application/directory` object. Keep it `patch`.
2. Run, in order:
   ```
   pnpm --filter @cobaltcore-dev/aurora typecheck
   pnpm --filter @cobaltcore-dev/aurora lint
   pnpm --filter @cobaltcore-dev/aurora test
   pnpm format:check
   pnpm check-i18n     # expect no catalog diff; if there is one, a new string slipped in
   ```

---

## Testing Plan

**Unit (server, `swiftRouter.test.ts`)**
- [ ] Existing container + options → CONFLICT **and** `swift.post` never called, probe PUT carries `{ headers: {} }`.
- [ ] 201 + options → POST issued once, after the PUT, with the option headers.
- [ ] 201 + no options → no POST.
- [ ] Existing `createContainer` 201/202/metadata tests unchanged and green.
- [ ] `createFolder` 412 → CONFLICT, shared mapper not consulted.
- [ ] `createFolder` success → PUT called as `(url, ArrayBuffer, { headers: { …, "If-None-Match": "*" } })`.
- [ ] `createFolder` 403 → mapper's error propagates.

**Unit (client, `CreateFolderModal.test.tsx`)**
- [ ] CONFLICT → inline error, modal open, input preserved, no toast callback.
- [ ] Non-conflict error → toast callback + close (unchanged).
- [ ] Client-side `existingRows` duplicate check still short-circuits before `mutate` (existing tests).

**Manual verification** (needs a reachable Swift/RGW — real backend or `../local-mock-backend` if it implements container/object PUT status codes; if it does not, note that and rely on the unit suites)
1. Create container `dup-test`; create it again from the modal → inline `"dup-test" is already taken.`, modal stays open. Then check `getContainerMetadata` for `dup-test` — no `X-Container-Meta-*`/ACL/quota changes (this is the Finding 1 regression, reproducible via a direct tRPC call with `metadata`/`read` since the modal sends no options).
2. In a container, create folder `docs` → succeeds; verify in the object listing that the marker is **0 bytes** (previously ~90 bytes) — this confirms the arg-order fix landed.
3. Create `docs` again → inline "A folder with this name already exists", modal open, no listing change, no duplicate/overwritten marker.
4. Simulate the pagination case: create a folder marker directly against Swift (bypassing the UI, e.g. `curl -X PUT`), keep the browser's cached listing stale (don't refresh), then try to create the same folder from the UI → the client fast path misses, the server CONFLICT catches it.

---

## Acceptance Criteria

- [ ] `createContainer` sends no caller-supplied `X-Container-Meta-*` / `X-Container-Read|Write` / quota / TempURL-key header on the request that detects 202, and issues no POST at all when the container already existed.
- [ ] `createContainer` still throws `CONFLICT` on 202 with the same message and no HEAD pre-check (prior commits' fix intact).
- [ ] `X-Storage-Policy` still reaches Swift on creation (create-only header not lost in the split).
- [ ] `createFolder` sends `If-None-Match: *` and the marker PUT uses the correct `(path, body, options)` signature.
- [ ] `createFolder` maps 412 to `TRPCError CONFLICT`, not `INTERNAL_SERVER_ERROR`.
- [ ] `CreateFolderModal` renders the CONFLICT inline and keeps the modal open; client-side `existingRows` check unchanged.
- [ ] Shared `mapErrorResponseToTRPCError` behaviour unchanged for all other call sites.
- [ ] No changes to Zod schemas, tRPC procedure signatures, or `AuroraApp` public props.
- [ ] `pnpm --filter @cobaltcore-dev/aurora typecheck`, `lint`, `test` pass; `pnpm format:check` and `pnpm check-i18n` clean.

---

## Open Questions — resolved 2026-09-10

1. **D2** — follow-up POST failure: **surface-and-keep, no rollback** (recommended option chosen).
2. **D3** — implicit-prefix probe: **accept the marker-only guarantee as-is** (recommended option chosen) — no `limit=1` prefix GET added.
3. **D4** — `listObjects` pagination truncation: **out of scope for this round**, tracked as a separate follow-up issue; not touched here.
4. **D5** — delivery: **leave uncommitted for review** — dev-executor should not create a commit; working tree stays dirty for manual review, as with the prior round.
5. Ceph `objectRouter.createFolder` parity (same missing check, S3-side): **out of scope**, separate follow-up — Copilot's finding is Swift-only and S3 conditional-write support is version-dependent on the RGW side.

All decisions resolved; plan is ready to implement as written (Step 1 uses D2's choice already; Step 3 skips D3's optional probe per the decision above).

---

### Key file paths

- `packages/aurora/src/server/Storage/routers/swift/swiftRouter.ts`
- `packages/aurora/src/server/Storage/routers/swift/swiftRouter.test.ts`
- `packages/aurora/src/server/Storage/helpers/swiftHelpers.ts`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Swift/Objects/CreateFolderModal.tsx`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Swift/Objects/CreateFolderModal.test.tsx`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Swift/Objects/index.tsx`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Swift/Containers/CreateContainerModal.tsx` (reference pattern)
- `packages/signal-openstack/src/client.ts`, `packages/signal-openstack/src/service.ts`, `packages/signal-openstack/src/error.ts`
- `.changeset/full-maps-obey.md`
