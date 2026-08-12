# Plan: Testing Plan — Section 12: CORS Configuration (PR #1092)

**Date:** 2026-07-25 · **Status:** not implemented

# TESTING PLAN: Section 12 — CORS Configuration (PR #1092, commit `1f7a0d9`)

## Overview

PR #1092 ships a full-stack CORS feature for Ceph/S3 buckets. It contains **512 lines of server tests and zero client tests**, while every sibling bucket modal already merged in `main` (`BucketPolicyModal`, `DeleteBucketPolicyModal`, `EnableVersioningModal`, `SuspendVersioningModal`, `DeleteVersionsModal`, `EmptyBucketModal`, ...) has a colocated `*.test.tsx`. It also adds ~110 lines of Zod schemas to `ceph.ts` with no matching cases in `ceph.test.ts` (the Bucket Policy schemas *do* have a `describe("Bucket Policy Schemas")` block there).

This plan therefore has three jobs: (1) close the automated-coverage gap to parity with Bucket Policy/Versioning, (2) pin the 7 known defects with red-first regression tests plus manual repro scripts, (3) run the CI gate checks (i18n in particular) that this feature is likely to fail.

## Architecture Analysis

**Code under test (all at commit `1f7a0d9a7a6c5d0a5b4b3743542cf92124605bec`):**

Server — `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/`
- `routers/ceph/corsRouter.ts` — `get` / `set` / `delete`, all `cephProtectedProcedure`, errors via `mapS3ErrorToTRPCError`, `NoSuchCORSConfiguration` treated as non-error in `get` and `delete`.
- `routers/ceph/corsRouter.test.ts` — 30 existing cases (exists on the branch only).
- `types/ceph.ts:519-579` — `corsAllowedMethodSchema`, `corsRuleSchema`, `corsConfigurationSchema`, `get/set/deleteCorsInputSchema`, `getCorsOutputSchema`.
- `helpers/s3ErrorMapper.ts:16` — new `NoSuchCORSConfiguration: "NOT_FOUND"` entry; `helpers/s3ErrorMapper.test.ts` was **not** touched.

Client — `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/`
- `CorsModal.tsx`, `CorsRuleForm.tsx`, `CorsRulesViewer.tsx`, `DeleteCorsModal.tsx`, `TagInput.tsx` — all new, all untested.
- `BucketModals.tsx`, `BucketToastNotifications.tsx`, `BucketHeader.tsx`, `BucketHeaderActions.tsx`, and `../hooks/useBucketInfo.ts` — modified wiring.

**Test patterns to copy (do not invent new ones):**
- Client: `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketPolicyModal.test.tsx` is the canonical template — module mocks for `@/client/hooks/useProjectId`, `@tanstack/react-router` (`useRouteContext` → `{ onTrackEvent }`), and `@/client/trpcClient` (hand-rolled `trpcReact` object with `useQuery`/`useMutation`/`useUtils`); a `renderModal` helper wrapping in `<I18nProvider i18n={i18n}><PortalProvider>`; `i18n.activate("en")` in `beforeEach`; and a trailing `describe("Analytics tracking")` block with the three canonical cases (`.open` on mount, `.close` on cancel, no `.close` after save).
- Server: `bucketPolicyRouter.test.ts` — `createMockContext()` from `./mockContext` (`hasCredentials: false` for the FORBIDDEN path), `vi.mock("../../clients/s3Client")` returning `{ send: mockSend }`.
- Test env: `packages/aurora/vitest.config.ts` → `jsdom`, `globals: true`, setup `vitest.setup.ts`, include `src/**/*.test.{ts,tsx}`.

**Non-goals (confirmed, do not test):** there are no `storage:*cors*` permission keys anywhere; CORS is gated purely by EC2-credential presence via `cephProtectedProcedure`, exactly like Policy/Versioning. No permission-matrix cases.

## Defect Inventory To Be Covered

The 5 from the KB report, plus 2 additional ones confirmed while reading the code for this plan:

| # | Defect | Where | Confidence |
| --- | --- | --- | --- |
| a | Stale `editingRuleIndex` after deleting an earlier rule silently overwrites the wrong rule | `CorsModal.tsx:106-111`, `:89-99`, `:232` | Confirmed |
| b | In-modal `<Message variant="error">` blocks are dead code — parent `onError` closes the modal on the same tick | `CorsModal.tsx:172-182` + `BucketModals.tsx:146-150` | Confirmed |
| c | "CORS Configuration Saved" toast shown when the config was actually **deleted** (empty-save and "Delete All Rules" both hit `deleteMutation`) | `CorsModal.tsx:117-131` + `BucketModals.tsx:141-145` | Confirmed |
| d | `hasChanges` uses raw `JSON.stringify`; server key order (`ID, AllowedHeaders, AllowedMethods, AllowedOrigins, ExposeHeaders, MaxAgeSeconds`) differs from `CorsRuleForm`'s submit order (`ID, AllowedOrigins, AllowedMethods, AllowedHeaders, ExposeHeaders, MaxAgeSeconds`) → false positive, spurious PUT | `CorsModal.tsx:133-136` vs `ceph.ts:519-534` / `CorsRuleForm.tsx:29-36` | Confirmed |
| e | `urlValidator` allegedly rejects `https://*.example.com` | `TagInput.tsx:97-110` | **DISPROVEN.** `new URL("https://*.example.com")` succeeds (hostname `*.example.com`, protocol `https:`), so wildcard-subdomain origins are accepted. The *real* looseness is the opposite: `https://example.com/some/path`, `https://user:pw@example.com`, and `https://example.com?q=1` all pass, though S3 origins must be scheme+host(+port) only. Keep as an exploratory item, re-scoped. |
| f (new) | "Cancel Edit" does not clear the form. `handleCancelEdit` only nulls `editingRuleIndex` while `activeTab` stays `ADD`, so `CorsRuleForm` is **not** remounted. `@tanstack/form-core@1.29.0` `FormApi.update()` only re-applies `defaultValues` when `!this.state.isTouched` (verified at `FormApi.js:92`), and `field.handleChange` sets `isTouched`. So after any edit, cancelling leaves the edited values in place, the button flips to "Add Rule", and submitting **appends a duplicate rule** instead of updating. | `CorsModal.tsx:113-115`, `:230-237`; `CorsRuleForm.tsx:19-41` | Confirmed |
| g (new) | Analytics `.open` stops firing after any save/delete error. `BucketModals` keeps `<CorsModal>` mounted permanently (`isOpen` prop, early `return null`), so `useModalTracking`'s `hasTrackedOpen` ref survives close. `CorsModal`'s error path calls only `onError` → parent `onClose()`; `handleClose()`/`resetTracking()` never run, so `hasTrackedOpen.current` stays `true` and every subsequent open is untracked. `DeleteCorsModal.tsx:57-62` has a `useEffect(() => { if (!isOpen) { ...resetTracking() } })` guard; `CorsModal` has none. `CorsModal` also never calls `markSubmitted()` (every sibling modal does). | `CorsModal.tsx:76-86` vs `DeleteCorsModal.tsx:57-62`, `hooks/useModalTracking.ts` | Confirmed |

## Existing Server Coverage — Gap Audit

`corsRouter.test.ts` already covers: `get` happy/complex/minimal/null-when-`NoSuchCORSConfiguration`/null-when-`CORSRules: undefined`/NOT_FOUND/FORBIDDEN(no creds)/FORBIDDEN(AccessDenied); `set` valid/multi/minimal/empty-array/empty-methods/empty-origins/MaxAge 86401/-1/ID 256 chars/MaxAge boundary 0 and 86400/NOT_FOUND/FORBIDDEN x2/MalformedXML; `delete` happy/idempotent/NOT_FOUND/FORBIDDEN x2.

Missing (Step 2 fills these):
1. **No assertion on what is actually sent to S3.** Every case ends at `expect(mockSend).toHaveBeenCalledOnce()`. Nothing proves `PutBucketCorsCommand` receives `{ Bucket, CORSConfiguration: { CORSRules } }`, or that `GetBucketCorsCommand`/`DeleteBucketCorsCommand` get the right bucket. A router that sent the wrong bucket name would pass today.
2. **No TRPC error-code assertions.** Every negative case is `rejects.toThrow(TRPCError)`, so a case named "should throw NOT_FOUND" passes when the code is `FORBIDDEN`. (Note: `bucketPolicyRouter.test.ts` is equally weak — this is house style, so treat tightening as an improvement, not a "fix the PR to match main" demand.)
3. **No malformed-S3-response test for `get`.** `corsRuleSchema.parse` runs *inside* the `try`, so a ZodError from a bad Ceph response is swallowed by the `catch` and fed to `mapS3ErrorToTRPCError` — which will not recognise it and will emit whatever its fallback is. Untested and likely a confusing 500.
4. No `AllowedMethods` upper-bound (`max(5)`), no invalid method value (`"PATCH"`), no `CORSRules.length > 100`, no invalid `bucketName` (empty / >255 via `existingBucketNameSchema`), no non-integer `MaxAgeSeconds` (e.g. `3600.5`).
5. `Code`-property variant of the S3 error is untested — the router checks both `s3Error.name` and `s3Error.Code`, only `name` is exercised.
6. `s3ErrorMapper.test.ts` was not updated for the new `NoSuchCORSConfiguration` → `NOT_FOUND` entry.

## Risks

| Risk | Severity | Mitigation |
| --- | --- | --- |
| [WATCH] Running the branch requires build/install in a tree you were told not to check out | Medium | Use a detached `git worktree` in the scratch dir (Step 0) — main working tree untouched |
| Red-first regression tests make the suite fail on the branch, blocking CI for the PR author | Medium | Land them behind `it.fails(...)` or as a separate commit paired with the fixes; see DECISION 3 |
| [SECURITY] Wildcard-origin CORS is a real data-exposure vector; the only guardrail is a warning `<Message>` | Medium | Explicit test that the warning appears for `*`, and a manual check that it survives translation (see i18n items) |
| Client accepts values the server rejects (`MaxAgeSeconds > 86400`, `ID > 255`) and defect (b) then discards all unsaved rules on the resulting error | High | Scenario M6 — this is the highest-user-impact combination of defects |
| Component tests on `@cloudoperators/juno-ui-components` `Modal`/`CheckboxGroup` may need `PortalProvider` and role-based queries | Low | Copy `BucketPolicyModal.test.tsx` verbatim for setup |
| `check-i18n` is a CI gate and the branch has untranslated literals | Medium | Step 11 runs it and diffs catalogs |
| No changeset for the feature — the PR's only `.changeset/fifty-icons-serve.md` is "Changed List styling to non-monospace", inherited from the `main` merge. Every feature PR in recent history adds one (`#952`, `#1062`, `#1067`, ...). Without it the feature ships with no version bump. | Medium | Flagged as a release-gate item in Step 11 |

## Prerequisites

- [ ] Node >= 24, pnpm >= 10 (per `.nvmrc` / `packageManager`).
- [ ] Network access to fetch the PR branch (`git fetch origin kiryl-ceph-cors`) — the commit is already present locally.
- [ ] For manual scenarios (Step 12): a running dashboard (`pnpm dev`, http://localhost:4005) with a valid Keystone `IDENTITY_ENDPOINT` in `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/apps/dashboard/.env`, a project with Ceph/S3 enabled, EC2 credentials created for that project, and at least one bucket.
- [ ] Decide DECISIONS 1-4 at the end of this document before starting Step 2.

---

## Test Groups

### Step 0: Set up an isolated worktree

**What to do:**
1. `git -C /Users/kirylmishchuk/projects/SAP/aurora-dashboard worktree add --detach <scratch-path>/cors-test 1f7a0d9a7a6c5d0a5b4b3743542cf92124605bec`
2. `pnpm install` inside that worktree.
3. Confirm the main working tree (`kirylDev`) is untouched: `git -C /Users/kirylmishchuk/projects/SAP/aurora-dashboard status`.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/routers/ceph/corsRouter.test.ts` runs in the worktree.

**Cleanup at the end:** `git worktree remove <path>` (or `--force` if new test files remain uncommitted and you have already copied them out).

---

### Step 1: Baseline — run everything as-is

**What to do:**
1. `pnpm --filter @cobaltcore-dev/aurora test` — record pass/fail and total count.
2. `pnpm --filter @cobaltcore-dev/aurora typecheck`
3. `pnpm --filter @cobaltcore-dev/aurora lint`
4. `pnpm format:check`
5. `pnpm --filter @cobaltcore-dev/aurora check-i18n` then `git status --porcelain packages/aurora/src/locales` — any diff means the committed catalogs are stale and CI will fail.

**Expected outcome:** a documented baseline. Anything failing here is pre-existing and must not be attributed to the new tests.

---

### Step 2: Server — harden `corsRouter.test.ts`

**File:** `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/corsRouter.test.ts`

**Cases to add** (each `it(...)` inside the existing `describe("get"|"set"|"delete")` blocks):

*Command-input assertions (all three procedures):*
1. `get` sends `GetBucketCorsCommand` with `{ Bucket: TEST_BUCKET_NAME }` — assert via `mockSend.mock.calls[0][0].input`.
2. `set` sends `PutBucketCorsCommand` with `{ Bucket, CORSConfiguration: { CORSRules: [VALID_CORS_RULE] } }`, and assert the rules array is passed through **unmodified** (no silent normalisation).
3. `delete` sends `DeleteBucketCorsCommand` with `{ Bucket: TEST_BUCKET_NAME }`.

*Error-code assertions (replace/augment `rejects.toThrow(TRPCError)`):*
4. `get`/`set`/`delete` with `NoSuchBucket` reject with `expect.objectContaining({ code: "NOT_FOUND" })`.
5. `AccessDenied` → `code: "FORBIDDEN"`; no-credentials context → `code: "FORBIDDEN"` (verify these two are actually distinguishable — if `cephProtectedProcedure` throws a different code for missing creds, document the real one).
6. `set` with `MalformedXML` → `code: "BAD_REQUEST"`.
7. Zod input failures → `code: "BAD_REQUEST"`.

*Uncovered schema branches on `set`:*
8. 6 `AllowedMethods` → BAD_REQUEST (`max(5)`).
9. `AllowedMethods: ["PATCH"]` → BAD_REQUEST (enum).
10. 101 rules → BAD_REQUEST; 100 rules → success (boundary).
11. `MaxAgeSeconds: 3600.5` → BAD_REQUEST (`.int()`).
12. `bucketName: ""` → BAD_REQUEST; `"a".repeat(256)` → BAD_REQUEST (`existingBucketNameSchema`).

*Response-validation branch on `get` (currently a blind spot):*
13. S3 returns `{ CORSRules: [{ AllowedOrigins: ["*"] }] }` (missing required `AllowedMethods`) → assert the actual thrown code/message. Document whether the ZodError leaks a confusing 500 through `mapS3ErrorToTRPCError`; if so, that's defect #8 and belongs in the report to the PR author.
14. S3 returns `{ CORSRules: [] }` (empty array) → current code returns `{ corsRules: [] }` (empty array is truthy), **not** `null`. Assert and document the difference from the "no config" case, because `BucketHeader.tsx` and `DeleteCorsModal.tsx` both branch on `corsRules.length > 0` while `CorsModal`'s `hasChanges` compares against `corsData?.corsRules || []`.

*Error-shape variant:*
15. `get` and `delete` with `{ Code: "NoSuchCORSConfiguration" }` (capital `Code`, no `name`) → treated as no-config / idempotent success.

**Expected outcome:** ~15 new server cases, all green (except possibly #13, which is diagnostic).

---

### Step 3: Server — CORS schema tests in `ceph.test.ts`

**File:** `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/types/ceph.test.ts`

Add a `describe("CORS Configuration Schemas")` block modelled on the existing `describe("Bucket Policy Schemas")` (line ~793), with sub-blocks for `corsAllowedMethodSchema`, `corsRuleSchema`, `corsConfigurationSchema`, `getCorsOutputSchema`.

**Cases:**
1. `corsAllowedMethodSchema` accepts each of GET/PUT/POST/DELETE/HEAD; rejects `PATCH`, `OPTIONS`, lowercase `get`.
2. `corsRuleSchema` — minimal valid rule (`AllowedMethods` + `AllowedOrigins` only) parses and leaves optional fields `undefined`.
3. `corsRuleSchema` rejects: missing `AllowedMethods`, empty `AllowedMethods`, 6 methods, missing/empty `AllowedOrigins`, `ID` 256 chars, `MaxAgeSeconds` -1 / 86401 / non-integer. Assert the custom messages ("At least one AllowedMethod is required", etc.) since they surface in tRPC BAD_REQUEST payloads.
4. `corsRuleSchema` accepts `ID` exactly 255 chars, `MaxAgeSeconds` 0 and 86400.
5. **Unknown-key behaviour**: parse a rule with an extra key (e.g. `{ ...VALID, Foo: "bar" }`). `z.object` strips by default — assert the stripped result explicitly, because `get` re-parses the live S3 response through this schema, so any future Ceph-side field is silently dropped.
6. `corsConfigurationSchema` — 1 rule ok, 100 rules ok, 0 rules rejected, 101 rejected.
7. `getCorsOutputSchema` — `{ corsRules: null }` valid, `{ corsRules: [] }` valid, `{ corsRules: [invalidRule] }` rejected.

---

### Step 4: Server — `s3ErrorMapper` mapping

**File:** `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/helpers/s3ErrorMapper.test.ts`

1. Add a case asserting `NoSuchCORSConfiguration` maps to `NOT_FOUND`, matching the existing `NoSuchBucketPolicy` case.
2. Add a case for a non-S3 error object (e.g. a `ZodError`) to document the fallback code — feeds Step 2 case #13.

---

### Step 5: Client — `TagInput.test.tsx` (new file)

**File to create:** `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/TagInput.test.tsx`

This is the only genuinely reusable new building block and needs the most thorough coverage. No tRPC mocks needed; wrap in `<I18nProvider>` only.

**Cases:**
1. Renders `label`, `placeholder`, `helptext`; renders one `Pill` per entry in `value`.
2. Typing + Enter calls `onChange` with `[...value, tag]` and clears the input.
3. Enter with whitespace-only input does nothing (`inputValue.trim()` guard).
4. Input is trimmed before being added (`" https://a.com "` → `"https://a.com"`).
5. **Blur adds the pending tag** (`onBlur` → `addTag`). This is unusual behaviour — verify it and check it does not fire twice when the user presses Enter and the field then blurs.
6. Duplicate entry → `onChange` NOT called, error text "This value already exists" shown, `invalid` prop set.
7. Failing `validate` → `onChange` NOT called, `result.error` rendered.
8. Typing after an error clears the error (`onChange` handler resets `setError(undefined)`).
9. Closing a Pill calls `onChange` with that value filtered out.
10. `disabled` disables the input.
11. **`urlValidator`** (pure-function `describe`): accepts `*`, `https://example.com`, `http://localhost:3000`, `https://example.com:8080`, and `https://*.example.com`. Rejects `example.com` (no scheme), `ftp://example.com`, `file:///x`, `""`. Then document (do not necessarily assert as a bug) that `https://example.com/path`, `https://a:b@example.com` and `https://example.com?q=1` are **accepted** although S3 origins are scheme+host+port only.
12. **`headerValidator`**: accepts `*`, `Content-Type`, `x_custom`, `X-Amz-Meta-1`; rejects `Content Type` (space), `Content:Type`, `""`, `héader`.
13. **i18n**: assert the four hard-coded English strings (`"This value already exists"`, `"URL must use http or https protocol"`, `"Invalid URL format. Expected: https://example.com"`, `"Header name can only contain letters, numbers, hyphens, and underscores"`) — confirmed none of them appear in `packages/aurora/src/locales/en/messages.po`, i.e. they are not Lingui-wrapped and will never translate. Write the test asserting the *English* text so it passes now, with a `// TODO: not Lingui-wrapped` comment, and report it (see Step 11).

---

### Step 6: Client — `CorsRuleForm.test.tsx` (new file)

**Cases:**
1. `editingRule: null` → heading "Add CORS Rule", submit button "Add Rule".
2. `editingRule: VALID_RULE` → heading "Edit CORS Rule", button "Update Rule", "Cancel Edit" button present, and every field pre-populated (ID text, origin pills, checked method checkboxes, header pills, `MaxAgeSeconds` as a string).
3. Submit button disabled when `AllowedOrigins` is empty; disabled when `AllowedMethods` is empty; enabled once both are non-empty (`canSubmit`).
4. Submit button disabled while `isSaving`, and all fields disabled while `isSaving`.
5. Checkbox toggling adds/removes the method from the array.
6. Valid submit calls `onSubmit` once with exactly `{ ID, AllowedOrigins, AllowedMethods, AllowedHeaders, ExposeHeaders, MaxAgeSeconds }` — assert empty ID becomes `undefined`, empty header arrays become `undefined`, and `MaxAgeSeconds` is parsed to a **number** not a string.
7. `MaxAgeSeconds: ""` → `undefined` in the payload (not `NaN`).
8. **Defect (d) probe:** assert `Object.keys(submittedRule)` order and compare with `Object.keys(corsRuleSchema.parse(serverShapedRule))`. This documents the key-order mismatch that makes `hasChanges` fire spuriously.
9. **[WATCH] Client-side range gap:** enter `MaxAgeSeconds: 999999` and an `ID` of 300 chars → assert `onSubmit` is still called (jsdom does not run native `min`/`max` constraint validation). This is the setup for manual scenario M6.
10. "Cancel Edit" calls `onCancel` (behaviour of what happens *after* is tested in Step 7, defect f).

---

### Step 7: Client — `CorsRulesViewer.test.tsx` (new file)

**Cases:**
1. Empty rules → "No CORS rules configured on this bucket" + "Add First Rule" button; no "Delete All Rules" button, no "Rules Details" section.
2. Non-empty → "N rules configured", one `RuleCard` per rule, both "Delete All Rules" and "Add Another Rule" visible.
3. Singular/plural: 1 rule renders "rule", 2 renders "rules".
4. `RuleCard` shows `ID` when present, "Rule {index+1}" when absent.
5. Optional sections (`AllowedHeaders`, `ExposeHeaders`, `MaxAgeSeconds`) hidden when absent, rendered when present.
6. `MaxAgeSeconds` formatting: 30 → no minutes suffix; 60 → "(1 minute)"; 3600 → "(60 minutes)".
7. Wildcard: a rule with `"*"` in `AllowedOrigins` renders the "Wildcard" badge on that card and the global "Security Warning" message; without it, neither.
8. `onAddRule` / `onEditRule(index)` / `onDeleteRule(index)` / `onDeleteAllRules` fire with the right index — critical, these indices feed defect (a).
9. **i18n:** assert `title="Security Warning"` here is the raw literal while `CorsModal.tsx` uses `t\`Security Warning\``. The `en` catalog has `msgid "Security Warning"` at line 2919 with `msgstr ""` in `de` — so in German the modal-level warning will be translated (once someone fills it in) but the viewer-level one never will. Test in `de` locale to demonstrate divergence if the German catalog has a value; otherwise assert-and-comment.

---

### Step 8: Client — `CorsModal.test.tsx` (new file) — the core suite

Copy the mocking scaffold from `BucketPolicyModal.test.tsx`, swapping `bucketPolicy` for `cors` (`trpcReact.storage.ceph.cors.get.useQuery`, `.set.useMutation`, `.delete.useMutation`, `useUtils().storage.ceph.cors.get.invalidate`).

**8.1 Rendering / loading (parity with siblings):**
1. `isOpen: false` → renders nothing.
2. `isLoading: true` → spinner; no tabs.
3. `error` → "Failed to load CORS configuration" + the error message; no tabs.
4. Loaded with `corsRules: null` → View tab active, "View Rules (0)".
5. Loaded with 2 rules → "View Rules (2)", both cards rendered.
6. Tab switching View ↔ Add Rule; the Add tab label reads "Edit Rule" while `editingRuleIndex !== null`.
7. Wildcard rule → modal-level "Security Warning".

**8.2 Save/delete wiring:**
8. Save is disabled when nothing changed (`hasChanges` false) and while `isPending`.
9. Adding a rule then Save calls `setMutation.mutate` with `{ project_id: "test-project-id", bucketName, corsConfiguration: { CORSRules: [...] } }`.
10. **Defect (c):** clearing all rules then Save calls `deleteMutation.mutate` (not `set`) — and, one level up in `BucketModals`, that surfaces the *"Saved"* toast. Assert the mutate call here; assert the wrong toast in Step 10.
11. "Delete All Rules" calls `deleteMutation.mutate` immediately with no confirmation step — verify and flag as a UX finding (the sibling `DeleteCorsModal` exists precisely to add confirmation, so a destructive unconfirmed button inside `CorsModal` is inconsistent).
12. Mutation `onSuccess` calls `utils...invalidate()`, then `onSuccess(bucketName)`, then resets local state.

**8.3 Regression tests for the defects (red-first, see DECISION 3):**
13. **Defect (a) — wrong-rule overwrite.** Render with rules `[A,B,C]`. Click Edit on B. Switch to View tab **without** cancelling. Delete A. Return to the Add/Edit tab. **Assert the form is pre-filled with B, not C** (fails today). Then submit and assert `currentRules` is `[B', C]` — today you get `[B, B']` with C destroyed. Verify via the payload passed to `setMutation.mutate` after Save.
14. **Defect (f) — Cancel Edit leaves stale data.** Edit rule B, change a field (this sets `isTouched`, which is what suppresses `FormApi.update`'s `defaultValues` re-apply at `form-core@1.29.0` `FormApi.js:92`), click "Cancel Edit". Assert the form fields are cleared and the heading returns to "Add CORS Rule" (fails today). Then click "Add Rule" and assert no duplicate rule is appended.
15. **Defect (b) — dead error UI.** Set `setMutation` mock to `{ error: { message: "Access Denied" }, isPending: false }` and assert "Failed to save CORS configuration" renders when the modal is still open — this passes at the unit level. Then in Step 10 (`BucketModals`) prove the parent unmounts it, which is the actual bug. Note explicitly in the test comment that unit-level pass + integration-level fail is the signature of this defect.
16. **Defect (d) — spurious `hasChanges`.** Load a rule in server key order, Edit it, submit the form with **zero** modifications, return to View. Assert Save is still disabled (fails today, because the resubmitted object has form key order).
17. **Defect (g) — analytics reset leak.** Render open → assert `.open` tracked once. Simulate the error path (invoke the `onError` captured from `useMutation` options, then rerender with `isOpen: false`), then rerender `isOpen: true`. Assert `storage.ceph.bucket.cors.open` is tracked **twice** total (fails today: only once, because `hasTrackedOpen` was never reset).
18. **Missing `markSubmitted`.** Click Save then click Cancel while `isPending`. Assert no `.close` event (fails today).

**8.4 Analytics tracking (the canonical sibling block):**
19. `.open` fired on mount with `action: "storage.ceph.bucket.cors.open"`.
20. `.close` fired on cancel-without-saving.
21. `.close` NOT fired after a successful save.

---

### Step 9: Client — `DeleteCorsModal.test.tsx` (new file)

Model on `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/DeleteBucketPolicyModal.test.tsx`.

**Cases:**
1. `isOpen: false` → nothing.
2. Loading → spinner, confirm button disabled.
3. Query error → error message, confirm disabled.
4. `corsRules: null` or `[]` → "No CORS configuration found" warning, confirm disabled (`!hasCors`).
5. With rules → bucket name in the confirmation text, rule-count sentence with correct singular/plural, confirm enabled.
6. Confirm calls `markSubmitted()` then `deleteMutation.mutate({ project_id, bucketName })`.
7. `onSuccess` → invalidate + `onSuccess(bucketName)` + `onClose`.
8. `deleteMutation.isError` → in-modal error message renders (note: same defect (b) applies here at integration level — parent closes on error).
9. Confirm disabled while `isPending`.
10. Analytics block: `.open` / `.close` on cancel / no `.close` after confirm — plus verify the `useEffect(!isOpen → resetTracking)` guard means a second open re-fires `.open` (the contrast case to `CorsModal` defect g).

---

### Step 10: Client — orchestration/wiring tests

**10.1 `BucketToastNotifications.test.tsx`** (existing file at the Buckets path — extend it):
1. `getCorsSavedToast("b")` → message "CORS Configuration Saved", description contains the bucket name.
2. `getCorsSaveErrorToast("b", "boom")` → contains bucket name and error message.
3. Same for `getCorsDeletedToast` / `getCorsDeleteErrorToast`.

**10.2 `BucketHeaderActions` / `BucketHeader`:**
4. `hasCors: false` → button reads "Add CORS"; `true` → "Edit/View CORS".
5. "Delete CORS" popup-menu item present only when `hasCors`.
6. Clicking the CORS button calls `onOpenModal("cors")`; the menu item calls `onOpenModal("deleteCors")`.
7. `BucketHeader` renders the "CORS Enabled" badge only when `corsData.corsRules.length > 0` — include the `corsRules: []` case (badge must be hidden), which pairs with Step 2 case #14.

**10.3 `BucketModals` integration — this is where defects (b) and (c) are proven:**
8. `activeModal: "cors"` renders `CorsModal` with `isOpen`, everything else closed.
9. **Defect (c):** drive `CorsModal`'s `onSuccess` after a *delete* path and assert `toast.success` received "CORS Configuration Saved". Assert the desired behaviour instead (deleted-toast) to make it a red test.
10. **Defect (b):** drive `onError` and assert `onClose()` is called synchronously in the same handler as `toast.error` — i.e. the modal is unmounted, so its in-modal `<Message>` can never be seen. Express as: after `onError`, `activeModal` is `null`.

---

### Step 11: CI gates, i18n and release hygiene

**What to do (all in the worktree):**
1. `pnpm --filter @cobaltcore-dev/aurora check-i18n`, then `git status --porcelain packages/aurora/src/locales` — must be clean. If `messages.po`/`.ts` change, the committed catalogs are stale → CI fails.
2. Grep for un-wrapped user-facing literals introduced by the PR and report them:
   - `TagInput.tsx` — 4 validator/error strings, confirmed absent from `packages/aurora/src/locales/en/messages.po`.
   - `CorsRulesViewer.tsx` — `title="Security Warning"` (raw), `"⚠️ Wildcard"`, `"seconds"`, `"minute"`/`"minutes"`, and the `"rule"`/`"rules"` ternary embedded inside `<Trans>` (which extracts as a placeholder, so the words themselves stay English).
3. Manually flip the app to German (`de`) and confirm which of the above render untranslated — the `de` catalog has `msgid "Security Warning"` with an empty `msgstr`, so also flag that the new CORS strings ship with no German translations at all (194 new lines in `de/messages.po`).
4. `pnpm --filter @cobaltcore-dev/aurora lint` — pay attention to `react-hooks/exhaustive-deps` on `DeleteCorsModal.tsx:57-62` (`useEffect` deps `[isOpen, bucketName]` while the body uses `deleteMutation` and `resetTracking`) and `CorsModal.tsx:55-58`.
5. `pnpm --filter @cobaltcore-dev/aurora typecheck`, `pnpm format:check`, `pnpm licenses:check`, `pnpm build`.
6. **Release gate:** confirm the PR has no changeset for the CORS feature (the only one present is `.changeset/fifty-icons-serve.md`, "Changed List styling to non-monospace", inherited from the `main` merge). Every recent feature PR adds one. Report as a blocker for merge.

---

### Step 12: Manual / exploratory scenarios

Run against a real Ceph-backed project (`pnpm dev`). Record pass/fail plus a screenshot per scenario.

- **M1 — Happy path.** Bucket with no CORS → "Add CORS" button → add a rule (origin `https://example.com`, methods GET+HEAD, MaxAge 3600) → Save → "CORS Configuration Saved" toast → "CORS Enabled" badge appears, button flips to "Edit/View CORS", "Delete CORS" menu item appears. Reopen → the rule is displayed. Verify against the actual bucket (e.g. `aws s3api get-bucket-cors`).
- **M2 — Defect (a), wrong-rule overwrite.** Create rules A, B, C (distinct IDs). Edit B → switch to View tab **without** clicking Cancel Edit → delete A → switch back to the Edit tab. **Expect (bug):** the form shows C's data. Change something, click Update Rule, Save. **Expect (bug):** B is untouched and C has been overwritten with the edited data. Confirm on the server.
- **M3 — Defect (f), Cancel Edit.** Edit rule B, change the ID field, click "Cancel Edit". **Expect (bug):** fields still hold B's edited data, heading now says "Add CORS Rule". Click "Add Rule" → a duplicate rule is appended.
- **M4 — Defect (c), misleading toast.** (i) Open CORS, delete every rule individually, Save. (ii) Open CORS, click "Delete All Rules". Both **expect (bug):** toast says "CORS Configuration Saved" although the config was deleted and the badge disappears. Compare with the "Delete CORS" menu item, which correctly says "Deleted".
- **M5 — Defect (b), lost work on error.** Revoke S3 permissions (or point at a bucket owned by another tenant / stop the RGW) so `set` returns 403. Add 3 rules, Save. **Expect (bug):** modal closes instantly, only a toast, all 3 unsaved rules are lost, and the in-modal "Failed to save CORS configuration" message is never visible.
- **M6 — Client/server validation gap + lost work (highest impact).** Enter `MaxAgeSeconds: 999999` (or an ID longer than 255 chars) — the form accepts it (the number input's `max` is advisory) — add several other valid rules, Save. **Expect:** a server BAD_REQUEST, the modal closes per M5, and everything is lost. Note whether the Zod message ("MaxAgeSeconds must be at most 86400 (24 hours)") is even legible in the toast.
- **M7 — Defect (d), spurious dirty state.** Open a bucket with an existing rule, click Edit, click "Update Rule" without changing anything, return to View. **Expect (bug):** "Save Configuration" is enabled; saving issues a needless PUT.
- **M8 — Defect (g), analytics.** With `onTrackEvent` logging to the console: open CORS → `.open`; trigger a save error (M5); reopen CORS. **Expect (bug):** no second `.open` event.
- **M9 — Origin validation (re-scoped from defect e).** Try `*` (accepted), `https://*.example.com` (accepted — the original report's claim that this is rejected is wrong), `example.com` (rejected), `ftp://x.com` (rejected), `https://example.com/path` and `https://example.com?q=1` (accepted, though S3 wants scheme+host+port only — check what Ceph does with them: silently store, normalise, or 400).
- **M10 — TagInput blur behaviour.** Type an origin and click straight on "Add Rule" without pressing Enter. Confirm the blur handler commits the tag before submit and no value is lost; also confirm a partially-typed invalid value on blur shows the error rather than being silently dropped.
- **M11 — Concurrency / cache.** Open the CORS modal, change the config from another tab/CLI, save from the modal. Confirm last-write-wins is acceptable and that `useBucketInfo`'s `staleTime: 5 * 60 * 1000` on the CORS query doesn't leave the header badge stale for 5 minutes after an external change (the mutation invalidates, but an external change won't).
- **M12 — DeleteCorsModal on a bucket with no CORS.** Only reachable when `hasCors` is true, but force it via cache staleness: delete CORS externally, then use the "Delete CORS" menu item. Expect the "No CORS configuration found" warning and a disabled confirm button.
- **M13 — Non-EC2-credentialed user.** Confirm the CORS button behaves like Policy/Versioning for a user without EC2 credentials (`CredentialPrompt` path), and that no CORS query storms the BFF with 403s.
- **M14 — Wildcard security warning.** Add a rule with origin `*`; confirm both the per-card "Wildcard" badge and the two "Security Warning" messages appear; switch the UI to German and note which stay English (Step 11.3).

---

### Step 13: E2E — scope decision, not a task

`/Users/kirylmishchuk/projects/SAP/aurora-dashboard/apps/dashboard/e2e/` contains only `smoke/authenticated.spec.ts`, `smoke/unauthenticated.spec.ts`, `ui/project-detail.spec.ts`, `ui/project-navigation.spec.ts`, `ui/projects-overview.spec.ts`. **There is no bucket-detail spec at all** — Policy and Versioning shipped without one too. Adding e2e for CORS would be new ground for the repo and requires real OpenStack + Ceph credentials in `.env`.

**Recommendation:** do **not** add e2e in this PR; record the missing bucket-detail e2e suite as a follow-up issue covering Policy + Versioning + CORS together, so the pattern is designed once. See DECISION 2.

---

## Testing Plan Summary

**New/extended automated tests:**
- [ ] `corsRouter.test.ts` — ~15 added cases (command inputs, error codes, schema boundaries, malformed responses)
- [ ] `ceph.test.ts` — new `describe("CORS Configuration Schemas")`, ~20 cases
- [ ] `s3ErrorMapper.test.ts` — 2 cases
- [ ] `TagInput.test.tsx` — new, ~20 cases including both validators
- [ ] `CorsRuleForm.test.tsx` — new, ~10 cases
- [ ] `CorsRulesViewer.test.tsx` — new, ~9 cases
- [ ] `CorsModal.test.tsx` — new, ~21 cases including 6 defect regressions
- [ ] `DeleteCorsModal.test.tsx` — new, ~10 cases
- [ ] `BucketToastNotifications.test.tsx` — 4 added cases
- [ ] `BucketHeader`/`BucketHeaderActions`/`BucketModals` — ~7 added cases

**Manual:** M1-M14 above, with a pass/fail record per scenario.

**CI gates:** `test`, `typecheck`, `lint`, `format:check`, `check-i18n` (+ catalog diff), `licenses:check`, `build`, and the missing-changeset check.

## Acceptance Criteria

- [ ] Every new/changed source file in PR #1092 has a colocated `*.test.ts(x)`, matching the Bucket Policy/Versioning convention.
- [ ] Server suite asserts what is sent to S3 and which TRPC error code comes back, not merely "some `TRPCError` was thrown".
- [ ] Each of the 7 defects has a named, executable regression test whose current status (red/green) is recorded, plus a written manual repro.
- [ ] The disproven finding (`urlValidator` and wildcard subdomains) is corrected in the KB report at `/Users/kirylmishchuk/projects/SAP/DOCS/aurora-dashboard-kb/prs/1092-cors-configuration-ceph-buckets.md`, with the re-scoped path/query looseness noted instead.
- [ ] `pnpm --filter @cobaltcore-dev/aurora test|typecheck|lint` and `pnpm format:check` + `check-i18n` results are recorded for the branch, with any failure attributed to either pre-existing baseline or the PR.
- [ ] i18n findings (4 unwrapped `TagInput` strings, raw `"Security Warning"` in `CorsRulesViewer`, untranslated units/badge in `RuleCard`, empty German translations) are reported with file:line.
- [ ] Missing changeset reported as a merge blocker.
- [ ] No regressions in the existing Ceph bucket suites (`BucketPolicyModal`, `EnableVersioningModal`, `BucketTableView`, `index.test.tsx`, ...).
- [ ] The worktree is removed and `/Users/kirylmishchuk/projects/SAP/aurora-dashboard` is left on `kirylDev` with its original working state.

## DECISIONS NEEDED (dev-planner could not prompt the user directly — these are the assumptions baked into the plan)

1. **Automated test scope.** Plan assumes: write *all* missing tests (server hardening + schema tests + 5 new client suites + wiring). Alternatives: regression-tests-for-the-7-defects only, or a manual-only pass. → **Assumed: write all.**
2. **E2E.** Plan assumes: no Playwright work now, file a follow-up issue for a bucket-detail e2e suite covering Policy + Versioning + CORS. Alternative: one minimal smoke spec. → **Assumed: defer + follow-up issue.**
3. **Red-first vs pin-current-behaviour.** Plan assumes red-first: defect tests assert the *correct* behaviour and therefore fail on `1f7a0d9`, doubling as the fix-verification checklist. That leaves the PR branch red until fixes land — if that's unacceptable, wrap them in `it.fails(...)` or keep them on a separate branch. → **Assumed: red-first, plus manual repro scripts.**
4. **Where tests run / what happens to them.** Plan assumes a detached `git worktree` in the scratch dir (working tree stays on `kirylDev`, branch never checked out). It does **not** assume the new tests get pushed to `kiryl-ceph-cors` — say so if you want them committed onto the PR. → **Assumed: worktree, deliverable is test files + a findings report, no push.**

## Open Questions

- Should the wildcard-origin security warning block saving (confirmation checkbox) rather than merely warn? Bucket Policy has the same class of exposure — check what it does before asking the PR author to change behaviour.
- Is `{ corsRules: [] }` (empty array from S3) a state Ceph can actually produce, or only `NoSuchCORSConfiguration`? It changes whether Step 2 case #14 is a real branch or defensive dead code.
- `useBucketInfo` caches the CORS query for 5 minutes while the two modals use the default `staleTime` — intentional, or should they share one query config?
- Should `CorsModal`'s unconfirmed "Delete All Rules" button route through `DeleteCorsModal` for consistency with the rest of the destructive-action UX?
