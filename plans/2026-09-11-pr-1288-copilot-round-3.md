# Plan: PR #1288 round-3 Copilot review findings

**Date:** 2026-09-11 · **Status:** implemented 2026-09-11, plus a follow-up triple-review fix pass same day (all 5 steps done; one lint-driven deviation in Step 1 — `onError` kept in `CreateBucketModalProps` but not destructured, since Ceph has no post-close partial-success path unlike Swift; Step 2's row-menu `Button` uses only `title`, no extra `aria-label`, to match the reference files exactly. `swiftRouter.test.ts` 108/108, full storage suite 72 files/2066 tests, full package suite 224 files/5601 tests, typecheck/lint/format:check all green, i18n regenerated. Security review clean — no Critical/High/Medium findings; noted one pre-existing, out-of-scope gap: `mapErrorResponseToTRPCError`'s default/500 branch can embed raw upstream error text, unchanged by this round. Not committed, per delivery decision.)

**Follow-up (2026-09-11, same day):** user asked for an independent triple-review (security + performance + architecture) of the *entire* PR diff (all 3 rounds, not just this one) before merging, in response to repeated Copilot findings. Architecture review found 1 High + 6 Medium; performance found 1 Medium; security found nothing new. User approved fixing all 7: (1) Ceph `CreateFolderModal` had zero handling for the `CONFLICT` this same PR round introduced — added `onError` mirroring Swift (field error for CONFLICT, `Message` banner for everything else, raw catch-all `<p>` removed); (2) Swift's 412→CONFLICT mapping moved from an inline router branch into the shared `mapErrorResponseToTRPCError` (matching Ceph's `s3ErrorMapper` pattern), with a new `swiftHelpers.test.ts` case; (3) changeset bumped `minor` → `major` (the `createContainer`/`createFolder` contract changes are genuinely breaking) and its false "instead of a HEAD pre-check" history claim removed; (4) Ceph's `createFolder` idempotent→CONFLICT behavior change documented in the changeset and in `docs/009_ceph_s3_bff.md` (which also had a wrong documented return type, `{success: boolean}` vs actual `boolean`), Swift's `docs/006` folder section similarly noted; (5) Swift `createContainer` partial-success no longer fires a contradictory simultaneous "Created" + "Failed to Create" toast pair — replaced with a single `onPartialSuccess` callback and a new "Created with Warnings" toast, `getContainerCreateErrorToast` (now unreachable) removed in favor of `getContainerCreatedWithWarningToast`; (6) Swift's `CreateFolderModal` now disables Cancel/close while pending and guards Enter against `isPending`, matching the other 3 create modals; (7) `resetTracking()` now called in the `onError` path of all 3 modals that stay open on failure (Ceph bucket, Swift container, Ceph folder) so a subsequent Cancel is correctly tracked instead of silently swallowed by `useModalTracking`'s `hasSubmitted` guard. 4 Low findings (dead prop chain, type-only import written as value import, a11y nuance in the shared `PopupMenuToggle as="div"` pattern, misc hardcode notes) explicitly skipped by user decision. Full suite re-verified after these fixes: 224 files/5602 tests, typecheck/lint/format:check green, i18n regenerated. Not committed.

## ⚠️ Read this first — two verified facts that change the task

**1. Issue 2 is already fixed. Copilot's 08:51 comments are stale false positives.**
At the current PR head `0bb43420`, both modals already pass the props:
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/CreateBucketModal.tsx` lines 174–175
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Swift/Containers/CreateContainerModal.tsx` lines 124–125

Copilot's comments point at lines 172 / 122 (`size="small"`), i.e. it reviewed a snapshot two lines short of the actual code. **No production code change is needed for Issue 2** — only regression tests (Step 4) plus a reply on the threads.

**2. Git state (re-verified at end of planning session):** `HEAD == origin/kiryl-bucket-and-folder-validations == 0bb43420`, working tree clean. The local branch also contains the merge of `origin/main` (`a1051ee2`), so `.github/copilot-instructions.md` (the expanded review rulebook from #1290) is present locally — and it is binding for this work (see below).

**3. Baseline is green**: `swiftRouter.test.ts` 107/107 pass; all 70 storage component test files (2011 tests) pass.

## Overview

Four Copilot threads on PR #1288 collapse into: (1) non-CONFLICT create errors leave the modal open with no persistent explanation, (2) *already fixed*, (3) `swiftRouter.createContainer` throws a retryable-looking error after the container was genuinely created, (4) two row menus use a bare `Icon` trigger instead of the mandated `PopupMenuToggle as="div"` + `Button` pattern.

## Architecture Analysis

**The repo's own rulebook decides two of the four issues.** `.github/copilot-instructions.md` (merged into the branch via `b90c126c`) says:

- L181 (modal skeleton): `{error && <Message variant="error" text={error} className="mb-4" onDismiss={clearError} />}` inside the modal body
- L406: "Context menus **must** use `<PopupMenuToggle as="div"><Button icon="moreVert" /></PopupMenuToggle>` as the trigger" (+ L541 reject: "`PopupMenu` without `PopupMenuToggle` as trigger")
- L404 / L545: error elements must carry `role="alert"` and `aria-live="assertive"`; L407: icon-only buttons must carry `aria-label`
- **L448 / L535 (key rule): "Do not use `toast` for errors that require user action — they auto-dismiss… Use `<Message>` instead"; reject "`toast.error` used for a persistent/actionable error"**
- L551: no "Please"/"Thanks"/"We"/exclamation marks/all-caps in user strings

**Current state — the four touchpoints:**

| File | Relevant lines |
|---|---|
| `.../Ceph/Buckets/CreateBucketModal.tsx` | `onError` 50–59; `Modal` 165–176; body `Stack` 177–203 |
| `.../Swift/Containers/CreateContainerModal.tsx` | `onError` 45–54; `Modal` 115–126; body `Stack` 127–146 |
| `.../Ceph/Buckets/BucketTableView.tsx` | bare toggle 241–246; imports `Icon` L9, `PopupMenuToggle` L13; mounts `CreateBucketModal` at 277 |
| `.../Swift/Containers/ContainerTableView.tsx` | bare toggle 240–245; same import shape; mounts `CreateContainerModal` at 277 |
| `packages/aurora/src/server/Storage/routers/swift/swiftRouter.ts` | `createContainer` 320–360; follow-up POST 347–356 |

**Reference patterns confirmed by reading them:**
- Row-menu target pattern: `BucketHeaderActions.tsx:69–71` and `ContainerHeaderActions.tsx:24–26` — `<PopupMenuToggle as="div"><Button icon="moreVert" title={t\`Bucket actions\`} /></PopupMenuToggle>`, no custom `className`. Every other `PopupMenuToggle` in the client (16 sites: Compute images/flavors, Network floating IPs/security groups, Ceph CORS/Lifecycle tabs, Swift objects) uses `as="div"` + `Button`. The two row menus added by this PR are the only outliers in the codebase.
- Inline error banner pattern: `CreateSecurityGroupModal.tsx:130–134` (`<Message dismissible={false} variant="error" className="mb-4">{error}</Message>`), plus `DeleteRuleDialog.tsx:72`, `AllocateFloatingIpModal.tsx:148`. Note `SecurityGroupsList.tsx:139–140` — the **create** mutation's `onError` sets inline error state and does **not** toast, while delete/update (151–153, 164–166) do both. So the closest precedent for a *create* modal is Message-only.
- Partial-success precedent on the server: `objectRouter.ts:193–201` (bulk delete degrades to `{deleted, errors, deletedCount, errorCount}` once any work succeeded, only throwing when nothing succeeded) and `lifecycleRouter.ts:104–126` (`{rules, skippedRuleCount}`).

**Juno 9.4.0 `Message` facts verified in the built source** (`MessageProps extends HTMLAttributes<HTMLDivElement>`):
- `text` is **not** destructured — it is read from the rest object *and* spread onto the root `<div>`, so `text="…"` leaks as a DOM attribute. **Use children form**, not `text`.
- `role`, `aria-live`, `data-testid` spread onto the root div correctly.
- `Message` keeps internal `visible` state after dismissal, so a dismissed banner would never re-show if the element stayed mounted — conditional rendering (`{submitError && <Message …/>}`) plus `onDismiss={() => setSubmitError(null)}` avoids that trap.
- The root div has **no** `role` by default → must pass `role="alert" aria-live="assertive"` explicitly.

**Server contract facts:**
- `createContainer` returns `Promise<boolean>` (always `true`) and is exported through the published `@cobaltcore-dev/aurora` app router.
- Its **only** in-repo caller is `CreateContainerModal.tsx:100–103`, which sends `{project_id, container}` and **no** metadata/ACL/quota — so `optionHeaders` is empty and the follow-up POST never runs from the bundled UI today. Issue 3 is real but currently only reachable by external consumers of the package, and is documented as a supported call shape in `packages/aurora/docs/006_swift_object_storage_bff.md:184–194`.
- `withErrorHandling` (`swiftHelpers.ts:604`) is generic — returning an object instead of a boolean is fine.

## Potential Problems & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Issue 1 "coexist" choice keeps `toast.error` for an actionable error — directly on the repo's own reject-list (L448/L535) → likely re-flagged in round 4 | High | Default to **Message-only** for errors rendered in the open modal (Step 1). |
| Issue 3 Option A changes a published tRPC procedure's output type (`boolean` → object) | High | Only one in-repo consumer, which ignores the return value. Update the design doc and bump the changeset from `patch` to `minor` (Open Question 2). |
| Removing the create-error toast would ripple into 6 test files (`BucketToastNotifications.test.tsx`, `ContainerToastNotifications.test.tsx`, both `index.test.tsx`, both modal tests) | Medium | Step 1 keeps the `onError` prop and toast builders intact and only stops calling `onError` on the in-modal path; `onError` is still called by Step 3's partial-success branch (Swift). |
| Existing tests assert `onError` **is** called on non-CONFLICT failures (`CreateBucketModal.test.tsx:750–785`, Swift equivalent at ~323) | Medium | Rewrite in the same step. |
| Row-menu tests locate the toggle via `.querySelector("button")` (`BucketTableView.test.tsx:318`) | Low | `as="div"` + `Button` still renders exactly one `<button>` in that cell. |
| `Message` inside `<Stack gap="6">` + guideline's `className="mb-4"` would double-space | Low | Put it as first child of the Stack without `mb-4`; comment that Stack gap provides spacing. |
| Guideline L450 ("Message variant must align with the modal's primary button") conflicts with `variant="error"` in a blue-primary modal | Low | Follow Copilot's explicit request (matches L444 and every in-repo precedent); mention in the PR reply. |
| i18n: new strings must be extracted | Low | Run `pnpm check-i18n`, commit regenerated locale files. |

## Prerequisites

- [ ] Confirm Open Questions 1–3 with the user before starting Step 1 and Step 3 (Steps 2 and 4 are unconditional and can be done first).
- [ ] Branch `kiryl-bucket-and-folder-validations` at `0bb43420`, clean tree, in sync with origin (re-check with `git status -sb` in case it moved again).
- [ ] Baseline green: `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/routers/swift/swiftRouter.test.ts` and the storage component test tree.

## Implementation Steps

### Step 1 — Add a persistent inline error banner to both create modals (Issue 1)

Files: `Ceph/Buckets/CreateBucketModal.tsx`, `Swift/Containers/CreateContainerModal.tsx`. Apply the identical shape to both.

1. Add `Message` to the Juno import.
2. Add `const [submitError, setSubmitError] = useState<string | null>(null)` next to `nameError`.
3. Rewrite `onError`: `CONFLICT` → field error + `setSubmitError(null)` + return; everything else → `setSubmitError(error.message || t\`The bucket could not be created. Try again or choose a different name.\`)`, no `onError?.()` call (per Open Question 1 default).
4. Clear `submitError` in `handleClose`, `handleNameChange`, and at the top of `handleSubmit`.
5. Render as first child of the body `Stack`:
   ```tsx
   {submitError && (
     <Message variant="error" dismissible onDismiss={() => setSubmitError(null)}
       role="alert" aria-live="assertive" data-testid="create-bucket-error">
       {submitError}
     </Message>
   )}
   ```
   (children form, not `text` prop — Juno 9.4.0 leaks `text` onto the DOM node otherwise.)
6. Keep the `onError` prop on both components (Swift still uses it in Step 3); add a doc comment clarifying it now fires only for post-close failures.

### Step 2 — Fix the two row-menu triggers (Issue 4)

Files: `BucketTableView.tsx`, `ContainerTableView.tsx`.

Replace the bare-`Icon` trigger with `<PopupMenuToggle as="div"><Button icon="moreVert" title={t\`Bucket actions\`} aria-label={t\`Bucket actions\`} /></PopupMenuToggle>` (Swift: "Container actions"). Drop the custom hover/active className. Remove now-unused `Icon` import, add `Button`.

### Step 3 — `createContainer`: report partial success instead of a retryable failure (Issue 3)

Files: `types/swift.ts`, `swiftRouter.ts`, `swiftRouter.test.ts`, `CreateContainerModal.tsx`, `docs/006_swift_object_storage_bff.md`.

1. Add `createContainerResultSchema = z.object({ created: z.literal(true), optionsApplied: z.boolean(), optionsError: z.string().optional() })`.
2. Change `createContainer`'s return type to that schema. No options → `{created: true, optionsApplied: true}`. POST succeeds → same. POST throws → do not rethrow; return `{created: true, optionsApplied: false, optionsError: <message>}`. Keep the 202→CONFLICT throw untouched.
3. In `CreateContainerModal.tsx`'s `onSuccess(data)`: if `data.optionsApplied === false`, call `onError?.(name, data.optionsError ?? t\`The container was created, but its settings could not be applied.\`)` before `handleClose()` — this is the one place a toast survives Step 1, since the modal is closing.
4. Update changeset + design doc.

### Step 4 — Regression tests for the already-fixed Issue 2

Add pending-state tests to both modal test files: Cancel disabled while `isPending`, close (X) control disabled while `isPending`. Harness already supports `mockState.isPending`.

### Step 5 — Changeset, i18n, docs

Update `.changeset/full-maps-obey.md` (bump `patch` → `minor` if Step 3 lands), document the new `createContainer` return shape in `docs/006_swift_object_storage_bff.md`, run `pnpm check-i18n` and commit regenerated locales.

## Testing Plan

**`CreateBucketModal.test.tsx` / `CreateContainerModal.test.tsx`:**
- Rewrite existing non-CONFLICT-error tests to assert the banner renders (not `onError` called), modal stays open.
- New: banner `role="alert"`/`aria-live="assertive"`; clears on name edit; clears+re-shows correctly across dismiss/re-fail cycles; gone after Cancel→reopen.
- Keep CONFLICT test green; assert banner is NOT rendered for CONFLICT.
- New (Step 4): Cancel/close disabled while pending.

**`BucketTableView.test.tsx` / `ContainerTableView.test.tsx`:**
- Existing "Action menu" suites pass unchanged.
- New: row trigger is a `button` with accessible name "Bucket actions" / "Container actions".

**`swiftRouter.test.ts` `describe("createContainer")`:**
- New: PUT 201 + options + POST rejects → resolves with `{created: true, optionsApplied: false, optionsError: expect.any(String)}`.
- Update existing 201-path tests to expect the new object shape instead of `true`.
- Unchanged: both 202/CONFLICT tests still reject with CONFLICT, `post` never called.

**Manual verification** (needs a running dashboard): server-error create shows persistent banner + Cancel/X re-enable after settling; existing-name create shows field error only, no banner; row menus keyboard/screen-reader accessible; Cancel/X disabled mid-flight.

## Acceptance Criteria

- [ ] Both create modals render a persistent `Message variant="error"` for non-CONFLICT failures; CONFLICT still uses field-level `errortext`; both clear on name edit, submit, and close.
- [ ] No `toast.error` fires for an error displayed inside an open modal, unless Open Question 1 is answered "coexist".
- [ ] Both row menus use `PopupMenuToggle as="div"` + labeled `Button`; no `Icon` import remains in either table view.
- [ ] `swiftRouter.createContainer` never throws when the container was genuinely created; a failed options POST surfaces as `{created: true, optionsApplied: false, optionsError}`.
- [ ] Regression tests prove Cancel/close disabled while pending.
- [ ] Changeset + design doc updated; `pnpm check-i18n` run.
- [ ] `pnpm --filter @cobaltcore-dev/aurora typecheck`, `lint`, `test` pass; `pnpm format:check` clean.
- [ ] No changes to anything already resolved in `2fa7d63f` / `4677d6b5` / `0bb43420` beyond these four issues.

## Decisions (confirmed by user, 2026-09-11)

1. **Toast vs Message for non-CONFLICT create errors → Message-only**, as Step 1 specifies. User initially leaned toward toast-only, but on being shown that `.github/copilot-instructions.md` L448/L535 explicitly rejects `toast.error` for actionable errors, chose to follow the repo's own guideline instead. Proceed with Step 1 exactly as written.
2. **Issue 3 → Option A**, partial-success shape `{created, optionsApplied, optionsError}` (Step 3), changeset bump `patch` → `minor`.
3. **Delivery → working tree only, no commit.** Do not commit or push; leave the changes as uncommitted working-tree edits. No reply to Copilot threads as part of this work.
4. **Row-menu label → generic**, `"Bucket actions"` / `"Container actions"`, matching the header-action reference files exactly (Step 2 as written, no per-row uniqueness).
