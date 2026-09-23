# Plan: Address GitHub Copilot review findings on PR #1288

**Date:** 2026-09-10 · **Status:** implemented 2026-09-10

## Overview

Five verified Copilot findings on `kiryl-bucket-and-folder-validations`: one real TOCTOU race in the Swift `createContainer` mutation, one behaviour/description mismatch in two create modals (they close on non-CONFLICT errors), and two missing client-side duplicate-name tests. All fixes are additive on top of the existing branch commit.

**Correction to the task brief:** the branch's work **is** already committed — `2fa7d63f fix(aurora): add validation for bucket/container/folder names and improve modal UX` (17 files), working tree clean. This plan therefore produces a second commit's worth of changes on top of it.

---

## Architecture Analysis

**Current state:**

- `packages/aurora/src/server/Storage/routers/swift/swiftRouter.ts` — `createContainer` (lines 320–356) does HEAD → 404-check → PUT. Added by `2fa7d63f`.
- `swift` comes from `ctx.openstack.service("swift")` → `SignalOpenstackService` in `packages/signal-openstack/src/service.ts`, which delegates to `client.put(path, values, options)`. `client.ts` returns the **raw `fetch` `Response`** for any `response.ok`, and throws `SignalOpenstackApiError(message, status)` otherwise. So `response.status` is available on the resolved PUT — `swiftRouter.ts` already relies on this pattern at lines 157, 300, 526, 990, 1077, 1181 (`response.status === 204`).
- Client modals: `CreateBucketModal.tsx` (Ceph) and `CreateContainerModal.tsx` (Swift) share the same `onError` shape; `CreateFolderModal.tsx` (Swift) closes via `onSettled` instead.
- `existingContainers` / `existingBuckets` / `existingRows` are wired from the list views (`Swift/Containers/index.tsx:423`, `Ceph/Buckets/index.tsx:411`, `Swift/Objects/index.tsx:592`) through the table views into the modals.

**Verified API facts (Finding 1 research):**

- OpenStack Swift "Create container" (`PUT /v1/{account}/{container}`) has normal response codes **201 and 202**: 201 = newly created, 202 = the container already existed (idempotent no-op create). Ceph RGW's Swift API implements the same 202-on-existing behaviour (added by ceph/ceph#5214 / tracker #12299, long since shipped).
- Swift's **container** PUT has **no** conditional create primitive — `If-None-Match: *` is an object-level thing in S3 and is not honoured for Swift container creation. Do not use it.
- Therefore the honest fix is **(a) from the brief**: the PUT response itself distinguishes create from update, so the HEAD pre-check can be replaced by a single PUT plus a status branch — race-free and simpler.
- Residual caveat: `buildContainerMetadataHeaders(options)` produces `X-Container-Meta-*`, `X-Container-Read/Write`, quota, TempURL-key and `X-Storage-Policy` headers. On the 202 path those headers have **already been applied** to the pre-existing container before we can throw CONFLICT. Today no in-repo caller sends any of these (`CreateContainerModal` sends only `{ project_id, container }`), but `createContainer` is part of the published `@cobaltcore-dev/aurora` server surface.

**Proposed changes:** replace HEAD+PUT with PUT + `status === 202 → CONFLICT`; stop closing the two create modals on error; add the two missing duplicate-name tests; fix the now-wrong existing test that asserts close-on-error.

---

## Decision needed

Recommended: **Option A**. The plan below is written for it — override Step 1 if you prefer B or C.

| Option | Shape | Trade-off |
| --- | --- | --- |
| **A (recommended)** | Drop HEAD. Single `swift.put(url, undefined, { headers })`; `response.status === 202` → CONFLICT, else success. | Race-free, simplest, one fewer round trip. Caveat: caller-supplied metadata reaches the pre-existing container before CONFLICT on the losing-racer path. Zero impact today; documented as a comment. |
| **B** | Bare PUT (only create-only `X-Storage-Policy`), 202 → CONFLICT with no side effects, 201 → follow-up `swift.post` with remaining headers. | No metadata clobber, but create+metadata is no longer atomic (POST can fail after the container exists) and `X-Storage-Policy` must still ride the PUT, so the caveat isn't fully eliminated. Extra request whenever options are supplied. |
| **C** | Keep HEAD as fast path **and** add the 201/202 branch as the backstop. | Avoids clobber in the non-racy case, but costs an extra round trip on every create and leaves two code paths meaning "already exists". |

---

## Potential Problems & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Existing test `"closes modal on error"` (`CreateBucketModal.test.tsx:767`) asserts `onClose` **is** called on error — Finding 2's fix inverts this and the test will fail | High (guaranteed red CI if missed) | Step 3 rewrites it into `"keeps the modal open on a non-CONFLICT error"`. Single most likely thing to be forgotten. |
| Swift mock `put` in `swiftRouter.test.ts:110` resolves `{ ok: true, headers }` with **no `status`** → after Step 1, `undefined !== 202` so existing success tests still pass, but silently for the wrong reason | Medium | Step 2 adds `status: 201` to the default `put` mock so success tests assert the real contract, and the CONFLICT test overrides with `status: 202`. |
| Behaviour change: a caller that previously got CONFLICT from a stale-but-correct HEAD now depends on the backend returning 202 | Low | Verified against both OpenStack Swift and Ceph RGW docs. Very old RGW (pre-2015) returned 201 unconditionally; not a supported target. Branch on `=== 202` (precise, per the Swift api-ref's documented 201/202 set) rather than "not 201", so an unexpected code degrades to "created" rather than a false CONFLICT. |
| Metadata side effect on the 202 path (Option A caveat) | Low | Explicit code comment; no in-repo caller passes options. Flagged as an accepted limitation of Swift's container API. |
| `CreateContainerModal.test.tsx` mock error type is `{ message: string }` — no `data.code`, so the CONFLICT branch is unreachable in tests today | Medium | Step 4 widens the mock error to `{ message: string; data?: { code?: string } }`, mirroring `CreateBucketModal.test.tsx`'s already-correct `mockState.mutationErrorCode` pattern. |
| `renderModal` helpers in the two Swift test files don't accept the new props | Medium | Steps 4 and 5 extend them (`existingContainers`, `existingRows`), following `CreateBucketModal.test.tsx:88-113`'s `existingBucketNames` precedent. |
| `useModalTracking` leakage when the modal no longer closes on error | Low | Non-issue: `markSubmitted()` runs in `handleSubmit`, and `trackClose()` is a no-op once `hasSubmitted.current` is true. `resetTracking()` still runs on the eventual real close. |

---

## Prerequisites

- [ ] Pick option A / B / C for Step 1 (default: A).
- [ ] Decide on the CreateFolderModal question in "Optional / flagged, not planned" below.

---

## Implementation Steps

### Step 1: Replace the HEAD-then-PUT TOCTOU with a single PUT + 201/202 branch

**Files to modify:**

- `packages/aurora/src/server/Storage/routers/swift/swiftRouter.ts` — `createContainer` mutation, ~lines 320–356.

**What to do:**

1. Delete the entire `const exists = await swift.head(url)...` block and the `if (exists) { throw new TRPCError(...) }` block.
2. Keep `const headers = buildContainerMetadataHeaders(options)` where it now sits (after the `url` computation).
3. Capture the PUT response instead of discarding it:
   - `const response = await swift.put(url, undefined, { headers }).catch((error) => { throw mapErrorResponseToTRPCError(error, { operation: "create container", container }) })`
4. Immediately after, branch on the status and throw the same CONFLICT as before:
   - `if (response.status === 202) { throw new TRPCError({ code: "CONFLICT", message: \`Conflict - create container - container already exists: ${container}\` }) }`
   - Keep the message string byte-identical to the current one so nothing downstream that matches on it changes.
5. Add an explanatory comment above the branch covering the three load-bearing facts:
   - Swift/RGW container PUT is idempotent: **201** = created, **202** = already existed.
   - There is no conditional create-if-not-exists for container PUT (`If-None-Match` is object-level in S3, not honoured here), so branching on the PUT status is the only race-free way to detect a duplicate.
   - Accepted limitation: on the 202 path any caller-supplied metadata headers have already been applied to the pre-existing container. No in-repo caller passes options; `CreateContainerModal` sends only `{ project_id, container }`.
6. Leave `return true` and the `withErrorHandling(..., "create container")` wrapper untouched.
7. Confirm `TRPCError` is still imported and used (it is — the CONFLICT throw remains).

**Expected outcome:** one HTTP request per container create; a concurrent duplicate create reliably gets `CONFLICT` from whichever request the backend answers with 202.

**Verification:**

- `pnpm --filter @cobaltcore-dev/aurora typecheck` — `response.status` must resolve.
- Read the diff and confirm no `swift.head` call remains inside `createContainer`.

### Step 2: Update the server-side createContainer tests to the new contract

**Files to modify:**

- `packages/aurora/src/server/Storage/routers/swift/swiftRouter.test.ts`

**What to do:**

1. In `createMockContext` (~line 110), add `status: 201` to the default `put` mock so it reads `put: vi.fn().mockResolvedValue({ ok: true, status: 201, headers: new Headers() })`. This makes every existing success-path test assert the real "created" contract instead of passing on `undefined !== 202`. `put` is shared by other mutations (upload, copy, createFolder, etc.) — adding `status` is additive and must not break them; re-run the full file.
2. In `describe("createContainer")`:
   - Remove the two now-obsolete `mockCtx.mockSwift.head.mockRejectedValue({ statusCode: 404, ... })` lines (and their comments) at lines 534–535 and 548 — there is no HEAD in this path any more.
   - Rewrite the `"should throw CONFLICT when container already exists"` test (line 565): set `mockCtx.mockSwift.put.mockResolvedValue({ ok: true, status: 202, headers: new Headers() })` and assert `rejects.toMatchObject({ code: "CONFLICT" })`. Update the comment to explain Swift answers an idempotent container PUT with 202 when the container already exists.
   - Replace the old `expect(mockCtx.mockSwift.put).not.toHaveBeenCalled()` assertion with `expect(mockCtx.mockSwift.head).not.toHaveBeenCalled()` — pins the race fix: fails if anyone reintroduces a pre-check.
3. Add a new test in the same describe: `"treats a 201 response as a successful create"` — default mocks, assert the caller resolves `true` and `put` was called once with the encoded URL.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/routers/swift/swiftRouter.test.ts`

### Step 3: Stop closing CreateBucketModal on non-CONFLICT errors, and fix its stale test

**Files to modify:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/CreateBucketModal.tsx` (lines 50–60)
- `.../Ceph/Buckets/CreateBucketModal.test.tsx`

**What to do:**

1. In the mutation's `onError`, delete the `handleClose()` call on the last line. Keep `onError?.(trimmed, error.message)` — the host still gets its toast — and keep the early-returning CONFLICT branch exactly as-is.
2. Add a one-line comment stating the modal deliberately stays open on any error so the user can retry, and closes only on success or Cancel.
3. Confirm `handleClose` is still referenced (used by `onSuccess` line 48 and `<Modal onCancel={handleClose}>` line 169) — both intentional, must stay.
4. In the test file, rewrite the existing `"closes modal on error"` test (line 767) into `"keeps the modal open on a non-CONFLICT error and still fires onError"`: same setup (`mockState.mutationError = "Creation failed"`, no `mutationErrorCode`), but assert `expect(mockOnClose).not.toHaveBeenCalled()` and `expect(mockOnError).toHaveBeenCalledWith("my-bucket", "Creation failed")`. Also assert the dialog is still present (`expect(screen.getByRole("dialog")).toBeInTheDocument()`).
5. Leave the CONFLICT test at line 784 unchanged.
6. Check the `"resets mutation state on close"` test (line 733) and the analytics tests (lines 907–1023) still hold — they all go through the success or Cancel path.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets/CreateBucketModal.test.tsx`

### Step 4: Same fix for CreateContainerModal + add the missing duplicate-name test (Finding 3)

**Files to modify:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Swift/Containers/CreateContainerModal.tsx` (lines 39–49)
- `.../Swift/Containers/CreateContainerModal.test.tsx`

**What to do:**

1. Apply the identical change as Step 3.1–3.2: drop `handleClose()` from `onError`, keep `onError?.(trimmed, error.message)`, keep the CONFLICT early return, add the same explanatory comment. `handleClose` stays used by `onSuccess` (line 37) and `<Modal onCancel={handleClose}>` (line 110).
2. Widen the mock error type so the CONFLICT branch is reachable — mirror the Ceph file's pattern:
   - Change `capturedOptions.onError` signature at lines 28 and 57 to `(error: { message: string; data?: { code?: string } }) => void`.
   - Add a module-level `let mutationErrorCode: string | undefined` next to `mutationError` (line 23), reset it in `beforeEach` (line 107), have `mockMutate` pass `data: mutationErrorCode ? { code: mutationErrorCode } : undefined` alongside `message`.
3. Extend the `renderModal` helper (lines 75–100) with an `existingContainers?: ContainerSummary[]` option defaulting to `[]`, passed through to the component. Import `ContainerSummary` from `@/server/Storage/types/swift`, or accept `existingContainerNames?: string[]` and map to `{ name, count: 0, bytes: 0, last_modified: "2023-01-01T00:00:00Z" }` — matching the Ceph file's `existingBucketNames` precedent. Pick whichever satisfies `ContainerSummary` under typecheck.
4. **Finding 3 test** — add inside the existing `describe("Validation", ...)` block (after `"clears validation error..."`, line 220):
   - `test("rejects a name already present in existingContainers without calling the mutation")`: render with one existing container named `taken-container`, type exactly `taken-container`, submit, wait for `screen.getByText(/"taken-container" is already taken/i)`, then `expect(mockMutate).not.toHaveBeenCalled()`.
   - `test("accepts a name not present in existingContainers")`: render with `other-container`, type `new-container`, submit, `expect(mockMutate).toHaveBeenCalled()` — mirrors `CreateBucketModal.test.tsx:563`.
5. Add a `describe("Error handling")` test: `"keeps the modal open on a non-CONFLICT error and still fires onError"` — `mutationError = "Creation failed"`, no code, assert `onError` called and `onClose` **not** called.
6. Add a companion CONFLICT test: `mutationError = "Container already exists"`, `mutationErrorCode = "CONFLICT"` → inline `"<name>" is already taken.` shown, `onClose` not called, `onError` **not** called.
7. Re-check the existing `"calls onError with container name and error message on mutation failure"` test (line 277) — it only asserts `onError`, not `onClose`, so it keeps passing unchanged.

**Verification:**

- `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Swift/Containers/CreateContainerModal.test.tsx`
- Also run `.../Swift/Containers/index.test.tsx` — renders `CreateContainerModal` inside `ContainerListView`, has no close-on-error assertion, should stay green — confirm.

### Step 5: Add the missing duplicate-folder test for Swift CreateFolderModal (Finding 4)

**Files to modify:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Swift/Objects/CreateFolderModal.test.tsx`

**What to do:**

1. Extend the `renderModal` helper (lines 90–115) with `existingRows?: BrowserRow[]` defaulting to `[]`, passed through to `<CreateFolderModal existingRows={existingRows} />`. Import the type: `import type { BrowserRow } from "./"` (the modal itself imports `BrowserRow` from `"./"` at line 7). If importing from `"./"` drags in unwanted side effects under the existing `@tanstack/react-router` mock, fall back to inlining literal `{ kind: "folder", name, displayName }` objects with an explicit `BrowserRow[]` annotation.
2. Add inside the existing `describe("Validation", ...)` block (after `"clears validation error..."`, line 239):
   - `test("rejects a folder name that already exists at the root level without calling the mutation")`: `renderModal({ currentPrefix: "", existingRows: [{ kind: "folder", name: "reports/", displayName: "reports" }] })`, type `reports`, submit, wait for `screen.getByText(/A folder with this name already exists/i)`, then `expect(mockMutate).not.toHaveBeenCalled()`.
   - `test("rejects a duplicate folder name inside a subfolder")`: `currentPrefix: "documents/"` with an existing row named `documents/reports/`, type `reports` → same assertions. Pins the `currentPrefix + trimmed + "/"` path construction at `CreateFolderModal.tsx:76`.
   - `test("accepts a folder name that only collides with an object row")`: existing row `{ kind: "object", name: "reports/", displayName: "reports", bytes: 0, last_modified: undefined, content_type: undefined }`, type `reports` → `expect(mockMutate).toHaveBeenCalled()`. Covers the `row.kind === "folder"` half of the predicate.
3. Do not touch the `describe("Submitted name snapshot", ...)` test at line 319 — depends on the current `onSettled` close ordering.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Swift/Objects/CreateFolderModal.test.tsx`

### Step 6: Refresh the changeset text

**Files to modify:** `.changeset/full-maps-obey.md` (or whichever changeset file currently covers this branch — check current filename, may have been renamed since)

**What to do:**

1. Current text says container creation "adds a server-side existence check with a CONFLICT error" — after Step 1 that's no longer accurate. Reword: server-side duplicate detection now branches on Swift's idempotent container-PUT status (201 created vs 202 already existed) instead of a racy HEAD pre-check.
2. Add a sentence for the Step 3/4 UX change: create-bucket and create-container modals now stay open on any failure so the user can retry, closing only on success or Cancel.
3. Keep severity at `patch`; keep the existing `useModalTracking` sentence.

**Verification:** `pnpm format:check` (or `pnpm format`).

### Step 7: Full affected-package gate

1. `pnpm --filter @cobaltcore-dev/aurora typecheck`
2. `pnpm --filter @cobaltcore-dev/aurora lint`
3. `pnpm --filter @cobaltcore-dev/aurora test`
4. `pnpm format:check`
5. `pnpm check-i18n` — no new `t\`\`` / `<Trans>` strings introduced, should be a no-op; run to confirm catalogs don't drift.

---

## Testing Plan

**Unit tests (server):**

- [ ] `createContainer` resolves `true` when PUT returns 201
- [ ] `createContainer` throws `CONFLICT` when PUT returns 202
- [ ] `createContainer` never calls `swift.head` (race-fix regression guard)
- [ ] Existing metadata-during-creation test still asserts `buildContainerMetadataHeaders` output reaches the PUT

**Unit tests (client):**

- [ ] Swift `CreateContainerModal`: duplicate name in `existingContainers` → inline "is already taken", `mutate` not called
- [ ] Swift `CreateContainerModal`: non-duplicate name → `mutate` called
- [ ] Swift `CreateContainerModal`: non-CONFLICT error → modal stays open, `onError` fires, `onClose` not called
- [ ] Swift `CreateContainerModal`: CONFLICT error → inline error, modal stays open, `onError` not called
- [ ] Ceph `CreateBucketModal`: non-CONFLICT error → modal stays open (rewritten from `"closes modal on error"`)
- [ ] Swift `CreateFolderModal`: duplicate folder at root and inside a prefix → inline error, `mutate` not called
- [ ] Swift `CreateFolderModal`: same-named **object** row does not block folder creation

**Manual verification:**

1. Run the local mock backend + dashboard (`local-mock-backend/run-all.sh`) or a real Swift endpoint.
2. Swift → Containers → Create Container, enter the name of a container visible in the list → inline `"<name>" is already taken.`, modal stays open, no toast.
3. Create a container whose name is not in the loaded list but exists server-side (create it out-of-band first, or scroll past the loaded page) → server CONFLICT → same inline error, modal stays open.
4. Force a non-CONFLICT failure (stop the backend mid-request) → error toast fires and the modal stays open with the typed name still in the field. This is the Finding 2 acceptance check.
5. Repeat 2–4 on Ceph → Buckets → Create Bucket.
6. Swift → any container → Objects → Create Folder with an existing folder name, both at root and inside a subfolder → inline "A folder with this name already exists".

---

## Acceptance Criteria

- [ ] `createContainer` performs exactly one HTTP request in the happy path and contains no HEAD pre-check
- [ ] Two concurrent `createContainer` calls for the same name cannot both succeed silently — the 202 responder gets `CONFLICT`
- [ ] The accepted Swift-API limitation (metadata headers land on the 202 path) is documented as a code comment, not left implicit
- [ ] Neither `CreateBucketModal` nor `CreateContainerModal` calls `handleClose()` from `onError`; both still call it from `onSuccess` and `Modal onCancel`
- [ ] The PR description's claim ("stays open for other errors so user can retry") now matches the code
- [ ] `existingContainers.some(...)` and `existingRows.some(...)` branches each have passing tests in both directions
- [ ] No regressions: `Swift/Containers/index.test.tsx`, `Swift/Objects/index.test.tsx`, `Ceph/Buckets/*.test.tsx` all green
- [ ] `pnpm --filter @cobaltcore-dev/aurora typecheck`, `lint`, `test` pass; `pnpm format:check` and `pnpm check-i18n` pass

---

## Optional / flagged, not planned (do not silently expand scope)

1. **Ceph side of Findings 3 & 4 is already covered — nothing to do.** `CreateBucketModal.test.tsx:546-577` has a `describe("Invalid bucket names - Duplicate check against loaded list")` block testing both directions of `existingBuckets.some(...)`. Ceph's `CreateFolderModal` delegates duplicate detection to `validateFolderName` in `Ceph/Objects/utils/objectValidation.ts`, whose `objectValidation.test.ts` has a dedicated `describe("duplicate validation")` covering root-level and prefixed duplicates. Copilot was right not to flag either.
2. **`Swift/Objects/CreateFolderModal.tsx` has the same close-on-error behaviour** (`onSettled: () => handleClose()`, line 49) that Copilot flagged in the other two modals, and it was *not* flagged. Making it consistent means moving the close into `onSuccess` only, and reworking the `describe("Submitted name snapshot")` test at line 319, which is built specifically around the close-on-settled ordering (and around the `submittedNameRef` workaround, which may become unnecessary). Recommend deferring to a follow-up unless the whole family should be made consistent in this PR.
3. **`CreateContainerModal` does not use `useModalTracking`** while its Ceph twin does — so Swift container creation emits no `.open`/`.close` analytics. Unrelated to Copilot's findings; worth a separate issue.
4. **No commit step is planned.** Say the word if the work should be committed locally on `kiryl-bucket-and-folder-validations` (never pushed).

---

## Open Questions

1. Option A / B / C for Step 1 — plan assumes **A**.
2. Include `Swift/Objects/CreateFolderModal` in the Finding 2 fix, or defer? — plan assumes **defer**.
3. Should the PR description on GitHub also be corrected, or is fixing the code to match it sufficient? The plan makes the code match the description, so no description edit is strictly needed.

**Sources:** [OpenStack Object Storage API reference](https://docs.openstack.org/api-ref/object-store/), [Ceph Container Operations](https://docs.ceph.com/en/reef/radosgw/swift/containerops/), [ceph/ceph#5214 — 202 Accepted on container creation](https://github.com/ceph/ceph/pull/5214)
