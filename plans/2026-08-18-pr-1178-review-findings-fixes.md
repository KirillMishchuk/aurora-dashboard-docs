# Plan: Fix PR #1178 review findings (CodeRabbit + Copilot)

**Date:** 2026-08-18 · **Status:** not implemented

## Overview

PR [#1178](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1178) ("feat(aurora): add Ceph S3 bucket lifecycle configuration management") received 11 review comments from CodeRabbit and 6 from Copilot (17 total, 16 unique — one duplicate finding between the two tools, one duplicate within Copilot itself).

This is a **live document**, built up incrementally as each finding was triaged one at a time in conversation. Each finding was verified against the actual PR code (fetched locally as git ref `pr-1178-review`, not checked out) before being added here.

**Triage complete: all 16 unique findings accounted for** — 15 confirmed below (`Подтверждённые находки к исправлению`, items 1–15, with item 5 split into 5a/accepted and 5b/rejected) and 1 rejected (`Рассмотрено и отклонено`, item 5b). Nothing has been implemented yet — this document is the fix plan, not a change log.

PR branch source is inspected via `git show pr-1178-review:<path>` / `git diff main...pr-1178-review` without switching the working branch (currently `kirylDev`).

---

## Подтверждённые находки к исправлению

### 1. Docs: `lifecycle.delete` output documented as `{ success: boolean }`, actual return is bare `boolean`

- **Source:** CodeRabbit (comment `3783805126`) + Copilot (comment `3802426864`) — same finding, found independently by both tools.
- **File:** `packages/aurora/docs/009_ceph_s3_bff.md`, lines 2399–2420 (`#### delete` block).
- **Problem:** the doc's `**Output:**` block shows:
  ```typescript
  {
    success: boolean
  }
  ```
  claiming the procedure returns an object with a `success` field.
- **Ground truth** (`packages/aurora/src/server/Storage/routers/ceph/lifecycleRouter.ts:186-220`):
  ```typescript
  /**
   * @returns boolean - true on success
   */
  delete: cephProtectedProcedure
    .input(deleteLifecycleInputSchema)
    .mutation(async ({ ctx, input }): Promise<boolean> => {
      try {
        await s3.send(new DeleteBucketLifecycleCommand({ Bucket: bucketName }))
        return true
      } catch (error) {
        if (s3Error.name === "NoSuchLifecycleConfiguration" ...) {
          return true // idempotent: no config also counts as success
        }
        throw mapS3ErrorToTRPCError(...)
      }
    }),
  ```
  Signature is `Promise<boolean>`, returns bare `true` — no object wrapper. The JSDoc above it (`@returns boolean - true on success`) already states the correct type, so the author knew the real contract; only the design doc drifted.
- **Established precedent in the same file:** `cors.delete` (lines 1640-1653) documents the identical bare-boolean pattern *correctly*:
  ```typescript
  boolean // true on success
  ```
  So this isn't a new documentation convention being invented — it's a copy-paste/drift mistake against an existing correct pattern in the same doc.
- **Real-world impact:** verified that neither `DeleteLifecycleRuleModal.tsx` nor `DeleteLifecycleRulesModal.tsx` (the only client consumers in this PR) read `.success` anywhere — they rely on tRPC's `onSuccess`/`onError` mutation callbacks. So this bug has **zero effect on the shipped code in this PR**; its blast radius is external API consumers (other teams/scripts) who'd code `const { success } = await trpc...lifecycle.delete.mutate(...)` and get `success === undefined` (silently falsy) instead of the real `true`/`false`.
- **Severity:** Minor (both tools agree) — doc-only, misleading external contract, no functional regression.
- **Fix:** replace the Output block with:
  ```typescript
  boolean
  ```
  No other part of the section needs to change (the Example doesn't read `.success`).
- **Risk:** none — doc-only, 3 lines → 1 line, no code/behavior change.
- **Verification:** re-read the edited block; confirm it matches `lifecycleRouter.ts`'s `Promise<boolean>` signature and the `cors.delete` doc convention; `pnpm format:check` on the doc file (Prettier-formatted).

### 2. Docs: `### Lifecycle Configuration` section wedged inside `## Troubleshooting`, splitting an existing entry and duplicating `## Error Handling`

- **Source:** CodeRabbit (comment `3783805162`) flagged this as Minor/markdownlint "duplicate heading `## Error Handling`, line 2431". Investigation shows the real defect is structural, not a lint nit — severity raised to **Major**.
- **File:** `packages/aurora/docs/009_ceph_s3_bff.md`, lines 2240–2444.
- **Root cause:** the PR's diff for this file is a single 203-line pure insertion (`git diff main...pr-1178-review` — 0 deletions, one hunk `@@ -2239,6 +2239,209 @@`). The insertion point lands **between** the existing heading `### Problem: \`All input parsers did not resolve to an object\` when wiring an upload` (line 2240) and its own body (`**Cause:** ...`), which previously sat directly beneath it. The inserted content is the new `### Lifecycle Configuration (storage.ceph.lifecycle)` API reference (~188 lines: `get`/`set`/`delete` docs), followed by a second copy of `## Error Handling` → `### S3 Error Mapper` → `#### Mapped Error Codes` (a **truncated** 1-row table — only `NoSuchBucket` — vs. the real table's 20 rows at line 1693), followed by a **re-inserted duplicate** of the `### Problem: ...` heading immediately before the original (now reattached) `**Cause:**` body.
- **Concrete damage (verified against `pr-1178-review`):**
  1. The first occurrence of `### Problem: All input parsers...` (line 2240) is now orphaned — immediately followed by unrelated Lifecycle Configuration content instead of its Cause/Solution body. Anyone navigating via this heading lands on the wrong content.
  2. The duplicated `## Error Handling` → `### S3 Error Mapper` → `#### Mapped Error Codes` block (lines 2431–2441) is a strict subset/duplicate of the pre-existing, complete section at line 1693 (20-row table vs. 1-row here) — adds no information, pure clutter.
  3. **Wrong section placement**: every other procedure's API reference in this doc (`### EC2 Credentials`, `### Containers`, `### Objects`, `### Versioning`, `### CORS Configuration`) lives as a `###` sibling under `## Available Procedures` (lines 195–1692, ending right before `## Error Handling` at 1693). `### Lifecycle Configuration` is the only procedure doc misplaced under `## Troubleshooting` instead of alongside its siblings.
- **Fix (structural, not cosmetic):**
  1. Cut the entire `### Lifecycle Configuration (storage.ceph.lifecycle)` block (current lines ~2242–2429, ends right before the spurious `## Error Handling`) out of its current location.
  2. Paste it into `## Available Procedures`, immediately after `### CORS Testing Notes` ends (right before `## Error Handling` at line 1693) — as the natural sibling of `### CORS Configuration`.
  3. Delete the spurious duplicate block entirely: `## Error Handling` / `### S3 Error Mapper` / `#### Mapped Error Codes` (the 1-row table) — lines ~2431–2441.
  4. Delete the re-inserted duplicate `### Problem: All input parsers...` heading (line ~2443) and its trailing blank line, so the original heading (line 2240) is once again immediately followed by its own `**Cause:**` body — restoring the pre-PR structure of that Troubleshooting entry.
- **Risk:** low — doc-only reorganization, no code change. Main risk is a careless cut/paste breaking Markdown table/code-fence formatting; mitigate by reviewing the moved block's rendering (fenced blocks balanced, no stray `---` separators lost/duplicated) after the edit.
- **Verification:**
  - `git show pr-1178-review:...009_ceph_s3_bff.md` heading list should show exactly ONE `## Error Handling` and exactly ONE `### Problem: All input parsers...`, with `### Lifecycle Configuration` appearing as a `###` under `## Available Procedures`, right after `### CORS Testing Notes`.
  - `markdownlint-cli2` (as run by CI) should no longer report MD024 duplicate-heading for this file.
  - `pnpm format:check` on the doc file.
  - Manually re-read the Troubleshooting section end-to-end to confirm the `### Problem: All input parsers...` entry reads coherently (heading directly followed by Cause/Solution, then `## References`).

### 3. Client: `DeleteLifecycleRuleModal.tsx` lacks dismissal guards during verify/mutate, and ESC bypasses guards in BOTH delete modals

- **Source:** CodeRabbit (comment `3783805166`), Major/Stability — flagged only the single-rule modal missing `disableCancelButton`/`disableCloseButton`. Investigation found a second, unreported gap affecting both modals (ESC key) — scope widened accordingly, per user decision.
- **Files:** `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/DeleteLifecycleRuleModal.tsx` (lines 169-178) and `.../DeleteLifecycleRulesModal.tsx` (lines 191-202).

**3a. `DeleteLifecycleRuleModal.tsx` missing button-level dismissal guards (CodeRabbit's original finding, confirmed)**

- **Problem:** the `<Modal>` JSX sets `disableConfirmButton={isMutating || isVerifying || isLoading || !!queryError}` but has no `disableCancelButton`/`disableCloseButton`, unlike the sibling bulk-delete modal which has both (`isMutating || isVerifying`). During `handleConfirm`'s in-flight `isVerifying` (refetch + freshness check) or `isMutating` (the actual `lifecycle.delete`/`lifecycle.set` mutation), Cancel and the X button stay clickable. Clicking either runs `handleClose()`, which calls `.reset()` on both mutations and `onClose()` — closing the modal **visually** — but does not abort the in-flight tRPC/S3 request. The delete/set call still completes server-side after the user believes they cancelled it.
- **Fix:** add to `DeleteLifecycleRuleModal.tsx`'s `<Modal>`:
  ```tsx
  disableCancelButton={isMutating || isVerifying}
  disableCloseButton={isMutating || isVerifying}
  ```

**3b. ESC key bypasses `disableCancelButton`/`disableCloseButton` in BOTH modals (new finding, not caught by either review tool)**

- **Verified directly against the compiled `@cloudoperators/juno-ui-components@9.1.0` `Modal` component** (`node_modules/.../juno-ui-components/build/index.js`):
  - The X button's `disabled` attribute is `disableCancelButton || disableCloseButton` — correctly gated.
  - The footer Cancel button's `disabled` is `disableCancelButton` — correctly gated.
  - The ESC-key handler, wired via `FocusTrap`'s `escapeDeactivates: (e) => (B(e), !1)`, only checks `closeable` (prop, default `true`) and `closeOnEsc` (prop, default `true`) — **`disableCancelButton`/`disableCloseButton` are never read by this path.**
- **Consequence:** pressing ESC while `isMutating`/`isVerifying` is `true` dismisses the modal (visually) exactly like an unguarded Cancel click would, in **both** `DeleteLifecycleRuleModal.tsx` and `DeleteLifecycleRulesModal.tsx` — neither passes `closeOnEsc`, so the default `true` applies unconditionally, request-in-flight or not. This means even the bulk modal, held up by CodeRabbit as the correct reference implementation, has the same underlying data-safety gap via ESC.
- **Existing correct precedent in the codebase:** `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/-components/Images/-components/CreateImageModal.tsx:367-368` already does this correctly:
  ```tsx
  closeable={!isLoading}
  closeOnEsc={!isLoading}
  ```
  (Not proposing `closeable={false}` here — it also hides the X button entirely rather than greying it out, which would diverge from the already-established `disableCloseButton` visual convention used by the bulk modal.)
- **Fix:** add `closeOnEsc={!(isMutating || isVerifying)}` to the `<Modal>` in **both** `DeleteLifecycleRuleModal.tsx` and `DeleteLifecycleRulesModal.tsx`.

- **Risk:** low — additive props on an existing, well-understood UI component; no logic/state changes. Slightly changes UX (ESC/Cancel/X become inert during an in-flight request) — intended behavior, matches `CreateImageModal.tsx` precedent.
- **Verification:**
  - Manual: open each modal, click Delete/Confirm, and while the request is in flight (throttle network in devtools if needed to widen the window) try Cancel click, X click, and ESC — all three must be inert until the mutation settles.
  - Confirm `disableConfirmButton`'s existing condition is untouched (only additive props).
  - `pnpm --filter @cobaltcore-dev/aurora typecheck` and `pnpm --filter @cobaltcore-dev/aurora test` for the storage/Ceph client tests.

### 4. Client: `LifecycleRuleForm.tsx` silently drops `NewerNoncurrentVersions` on any unrelated edit

- **Source:** CodeRabbit (comment `3783805174`), Major/Data Integrity.
- **File:** `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRuleForm.tsx`, lines 116-120 (`onSubmit`'s `NoncurrentVersionExpiration` rebuild) and 50/82-83 (`getInitialValues`).
- **Problem:** the form rebuilds `NoncurrentVersionExpiration` from scratch on submit using only the `NoncurrentDays` form field:
  ```tsx
  if (value.hasNoncurrentExpiration && value.noncurrentDays) {
    newRule.NoncurrentVersionExpiration = {
      NoncurrentDays: parseInt(value.noncurrentDays, 10),
    }
  }
  ```
  The form has no state, no field extraction in `getInitialValues()`, and no UI control anywhere for `NewerNoncurrentVersions` — verified across the full 468-line file. So editing *any* other field (e.g. just `Status`) on a rule that has `NewerNoncurrentVersions` set (e.g. authored via `aws-cli`) silently strips it on save.
- **Confirmed this field is real and displayed elsewhere:** server schema (`ceph.ts:828,840,1067,1077`) validates it; `lifecycleMapper.ts:108,116` round-trips it between SDK and wire shape; `LifecycleRulesTable.tsx:148,155` + `lifecycleUtils.ts:350-351` (`formatNoncurrentExpiration`) **display it in the rules table** (e.g. "keep 3 versions") — so a user can see the setting, open the rule for an unrelated edit, save, and have it vanish without any warning.
- **Existing precedent in the very same file:** the sibling "not editable via Aurora UI, must be preserved" fields `Transitions` (lines 111-113) and `NoncurrentVersionTransitions` (lines 122-124) are both explicitly carried through unchanged from `editingRule` on submit — `NewerNoncurrentVersions` is the one field of this kind that didn't get the same treatment.
- **Fix:** preserve it in the rebuild, following the exact same pattern as the sibling fields:
  ```tsx
  if (value.hasNoncurrentExpiration && value.noncurrentDays) {
    newRule.NoncurrentVersionExpiration = {
      NoncurrentDays: parseInt(value.noncurrentDays, 10),
      ...(editingRule?.NoncurrentVersionExpiration?.NewerNoncurrentVersions !== undefined && {
        NewerNoncurrentVersions: editingRule.NoncurrentVersionExpiration.NewerNoncurrentVersions,
      }),
    }
  }
  ```
  Scope note: this only fixes preservation on edit of an existing rule that already has the field (e.g. from `aws-cli`). It does not add UI to *set* `NewerNoncurrentVersions` on a new/existing rule from scratch — that's a separate feature gap, out of scope for this review-findings fix pass unless the user wants it folded in.
- **Test:** `LifecycleRuleForm.test.tsx` already has the exact template to copy — `describe("Item 1: Transitions preservation")` → `test("preserves Transitions when editing unrelated field", ...)` (lines 200-219): renders the form with `editingRule`, changes `Status`, submits, asserts the untouched field survived. Add an equivalent test asserting `submittedRule.NoncurrentVersionExpiration.NewerNoncurrentVersions` matches the original after an unrelated edit.
- **Risk:** low — additive object-spread in one rebuild block, mirrors an already-shipped pattern in the same file. No schema/type changes needed (`LifecycleRuleRead["NoncurrentVersionExpiration"]` already allows the field).
- **Verification:** new unit test above; `pnpm --filter @cobaltcore-dev/aurora test` for `LifecycleRuleForm.test.tsx`; manual check — edit a rule with `NewerNoncurrentVersions` set (seed via `aws-cli` or test fixture), change only `Status`, save, confirm the table still shows "keep N versions" after refresh.

### 5a. Client: `LifecycleRuleModal.tsx` "add new rule" path builds on stale cached rules instead of refetching

- **Source:** CodeRabbit (comment `3783805184`), one half of a Major/Heavy-lift finding — split from 5b below (see "Рассмотрено и отклонено" for the rejected half).
- **File:** `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRuleModal.tsx`, lines 100-108 (`handleSubmit`).
- **Problem:** the `editingIndex === null` (add) branch builds `updatedRules` from `lifecycleData?.rules` — the `useQuery` cache, with `staleTime: 5 * 60 * 1000` (5 min) — without refetching first:
  ```tsx
  const currentRules = lifecycleData?.rules ?? []
  if (editingIndex === null) {
    // Adding new rule - no freshness check needed (appending is safe)
    updatedRules = [...currentRules, rule]
  } else {
    // Editing existing rule - perform freshness check
    const freshData = await utils.storage.ceph.lifecycle.get.fetch({...})
    ...
  }
  ```
  The in-code comment "appending is safe" is incorrect: `lifecycle.set` is a full replace of the bucket's `Rules` array (`PutBucketLifecycleConfigurationCommand`), not an atomic append. If another writer (another tab, another user, `aws-cli`) changed a *different* rule between this modal's data load and submit, that change is silently discarded when the stale `currentRules` base gets overwritten wholesale. The `else` (edit) branch already refetches fresh data before building its base array — the `add` branch skips this for no valid reason.
- **Fix:** refetch before appending, mirroring the edit branch:
  ```tsx
  if (editingIndex === null) {
    const freshData = await utils.storage.ceph.lifecycle.get.fetch({
      project_id: projectId,
      bucketName,
    })
    updatedRules = [...(freshData?.rules ?? []), rule]
  } else {
    // unchanged
  }
  ```
- **Risk:** low — one extra `await` mirroring an existing, already-tested code path in the same function.
- **Verification:** manual — open two browser tabs on the same bucket, add a rule via `aws-cli`/another tab, then add a different rule via the modal in the first tab without refreshing; confirm both rules survive. Unit test: mock `utils.storage.ceph.lifecycle.get.fetch` to return different data than the initial `useQuery` cache and assert the submitted payload includes both.

### 6. Client: `LifecycleRulesTable.tsx` interpolates a member expression directly in a Lingui `t` macro

- **Source:** CodeRabbit (comment `3783805190`), Minor/Quick win.
- **File:** `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRulesTable.tsx`, line 168.
- **Problem:**
  ```tsx
  const abortText = rule.AbortIncompleteMultipartUpload
    ? t`After ${rule.AbortIncompleteMultipartUpload.DaysAfterInitiation} days`
    : "–"
  ```
  `${rule.AbortIncompleteMultipartUpload.DaysAfterInitiation}` is a member-expression chain interpolated directly inside the Lingui `t` macro.
- **Verified against the actual lint rule** (`node_modules/eslint-plugin-lingui`, rule `no-expression-in-message`): *"doesn't allow functions or member expressions in templates"*, message *"Should be `${variable}`, not `${object.property}` or `${myFunction()}`"* — matches this exact pattern. The rule is active via `packages/aurora/eslint.config.mjs` → `pluginLingui.configs["flat/recommended"]`, at severity `'warn'`.
- **Severity nuance:** since it's `warn` (not `error`) and `packages/aurora/package.json`'s `"lint": "eslint"` script has no `--max-warnings 0`, **this does not fail CI** — `pnpm lint` exits 0, just prints a warning. CodeRabbit's Minor tag is accurate.
- **Why fix it anyway:** Lingui's extractor (`pnpm check-i18n`) derives each message's placeholder name from the interpolated expression's source text. A member-expression placeholder is fragile — refactoring the accessed field/type later can shift the generated placeholder/message shape across all locale `.po` files, forcing needless re-translation with no actual copy change.
- **Fix:** extract to a local variable before the macro:
  ```tsx
  const abortDays = rule.AbortIncompleteMultipartUpload?.DaysAfterInitiation
  const abortText = abortDays !== undefined ? t`After ${abortDays} days` : "–"
  ```
- **Risk:** none — one-line refactor, no behavior change.
- **Verification:** `pnpm --filter @cobaltcore-dev/aurora lint` — the `no-expression-in-message` warning for this line should disappear; `pnpm check-i18n` to confirm extraction still succeeds cleanly.

### 7. Client: checkbox `aria-label` uses 0-based index, inconsistent with `DeleteLifecycleRuleModal`'s 1-based label — fix widened to include `CorsRulesTable.tsx`

- **Source:** CodeRabbit (comment `3783805193`), Minor/Maintainability. Scope widened beyond the PR's own diff per user decision (see below).
- **Files:** `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRulesTable.tsx` (line 181, in this PR's diff) **and** `.../CorsRulesTable.tsx` (line 140, pre-existing, untouched by this PR — added in PR #1172).
- **Problem:** `LifecycleRulesTable.tsx:181`:
  ```tsx
  aria-label={t`Select rule ${originalIndex}`}   // 0-based: "Select rule 0" for the first row
  ```
  while `DeleteLifecycleRuleModal.tsx` identifies the same row as:
  ```tsx
  const displayName = ruleId || t`Rule #${ruleIndex + 1}`   // 1-based, prefers rule.ID
  ```
  A screen-reader user hears "Select rule 0" in the table, opens the delete dialog for that same row, and hears "Rule #1" — two different identifiers for one entity. The table already displays `rule.ID` in its own cell (line 184), so the ID is readily available to use here too.
- **Widened scope — verified before deciding:** the identical 0-based pattern already exists, unrelated to this PR, at `CorsRulesTable.tsx:140` (confirmed via `git diff main...pr-1178-review -- .../CorsRulesTable.tsx` → empty; file untouched since PR #1172). `LifecycleRulesTable.tsx` simply copied this already-shipped convention. Fixing only the Lifecycle table would not eliminate the inconsistency CodeRabbit describes — it would relocate it: Lifecycle would say "Select rule my-id"/"Select rule 3" while the sibling CORS table right next to it in the same bucket-details UI would still say "Select rule 0". User chose to fix both files together for actual consistency, even though `CorsRulesTable.tsx` is outside this PR's diff.
- **Fix (both files, identical pattern):**
  ```tsx
  const ruleLabel = rule.ID || String(originalIndex + 1)
  ...
  aria-label={t`Select rule ${ruleLabel}`}
  ```
  (Single translated template, `ruleLabel` is a plain `Identifier` interpolation — stays clean under `lingui/no-expression-in-message` from Finding #6, no nested macros.)
- **Risk:** low. `LifecycleRulesTable.tsx` change is within this PR's own files. `CorsRulesTable.tsx` change touches a file merged separately on `main` (PR #1172) — verify no other open PR is concurrently touching that same line before pushing, and that its own tests (if any reference `data-testid="select-rule-N"` or the aria-label text) are updated alongside.
- **Verification:** re-check `git grep "Select rule"` shows both files using the same `ruleLabel` pattern; any tests asserting the literal "Select rule 0"/"Select rule 1" text in either file's test suite updated to match; manual screen-reader spot check (or DOM inspection) confirms the checkbox label and the delete-modal title now agree for the same row in both tables.

### 8. Test: `lifecycleUtils.test.ts` date-formatting assertions are locale/timezone-dependent

- **Source:** CodeRabbit (comment `3783805200`), Minor/Quick win.
- **File:** `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/utils/lifecycleUtils.test.ts`, lines 398-400 (`formatExpiration`'s "should format Date from string") and 418-421 (`formatTransitions`'s "should format transition with Date", flagged by CodeRabbit as "Also applies to").
- **Problem:** both tests hardcode an expected US-formatted date string:
  ```tsx
  const result = formatExpiration({ Date: "2026-12-31T00:00:00.000Z" })
  expect(result).toContain("12/31/2026")
  ```
  The implementation (`lifecycleUtils.ts:312`, `:331`) calls `date.toLocaleDateString()` with **no locale/timeZone arguments**, so the output depends on the test runner's environment (`Intl.DateTimeFormat().resolvedOptions()`).
- **Reproduced live on this machine:**
  ```
  $ node -e "console.log(Intl.DateTimeFormat().resolvedOptions())"
  { locale: 'en-US', timeZone: 'Europe/Berlin', ... }
  $ node -e "console.log(new Date('2026-12-31T00:00:00.000Z').toLocaleDateString())"
  12/31/2026   ← passes (Berlin = UTC+1, same calendar day)
  $ TZ="America/New_York" node -e "console.log(new Date('2026-12-31T00:00:00.000Z').toLocaleDateString())"
  12/30/2026   ← FAILS the .toContain("12/31/2026") assertion
  ```
  Non-`en-US` locales (e.g. `de-DE`, `ru-RU`) format as `31.12.2026`, also failing the substring check.
- **Confirmed neither `packages/aurora/vitest.config.ts` nor `.github/workflows/ci-checks.yaml` pin `TZ` or locale.** GitHub Actions' `ubuntu` runners default to UTC (so CI is currently green), but any contributor in a UTC-behind timezone (the Americas) gets a red test locally with zero code changes on their part.
- **Fix:** derive the expected value with the same non-deterministic call the implementation uses, instead of a hardcoded literal — makes the test environment-independent rather than trying to pin TZ/locale (which isn't fully controllable via env vars alone without a full-ICU Node build):
  ```tsx
  it("should format Date from string", () => {
    const inputDate = "2026-12-31T00:00:00.000Z"
    const expected = `On ${new Date(inputDate).toLocaleDateString()}`
    expect(formatExpiration({ Date: inputDate })).toBe(expected)
  })

  it("should format transition with Date", () => {
    const inputDate = "2026-12-31T00:00:00.000Z"
    const expectedDate = new Date(inputDate).toLocaleDateString()
    const result = formatTransitions([{ Date: inputDate, StorageClass: "GLACIER" }])
    expect(result).toBe(`GLACIER after ${expectedDate}`)
  })
  ```
- **Risk:** none — test-only change, no production code touched.
- **Verification:** run `TZ="America/New_York" pnpm --filter @cobaltcore-dev/aurora test lifecycleUtils.test.ts` before and after the fix to confirm it fails pre-fix and passes post-fix; also run with default TZ to confirm no regression.

### 9. Client: `validateLifecycleRules` missing two filter-structure checks present in the server schema

- **Source:** CodeRabbit (comment `3783805206`), Minor/Quick win.
- **File:** `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/utils/lifecycleUtils.ts`, `validateLifecycleRules` (lines 179-213).
- **Problem:** confirmed via `grep` across the whole file — the client validator has no check for either of these two server-side (`packages/aurora/src/server/Storage/types/ceph.ts`) Zod refinements:
  1. `lifecycleFilterAndSchema` (lines 870-893): `"And filter must contain at least 2 predicates"`.
  2. `lifecycleFilterSchema` (lines 895-926): `"Multiple filter conditions (Prefix, Tag, ObjectSize) must be wrapped in an And clause"` (also fires when `And` is combined with a top-level condition).
- **Confirmed reachable, not dead code:** the form's `normalizeFilter()` (lines 29-60) is a "smart constructor" that can never itself produce an invalid combination — so a rule authored *through Aurora's own form* can't trigger this gap. But `validateLifecycleRules` runs over the **entire** bucket rule array on every edit/delete (not just the touched rule) — so a bucket containing one externally-authored rule (`aws-cli` etc.) with a malformed filter will pass client-side validation when the user edits/deletes an unrelated rule, then get rejected wholesale by the server's Zod schema with a generic, unlabeled mutation error instead of Aurora's inline `setValidationErrors` UI pointing at the actual offending rule.
- **Fix:** mirror both server refinements in `validateLifecycleRules`:
  ```tsx
  // And filter must have ≥2 predicates (per-tag counting — see Finding #11's server fix, which this must match)
  if (rule.Filter?.And) {
    const predicateCount =
      (rule.Filter.And.Prefix !== undefined && rule.Filter.And.Prefix !== "" ? 1 : 0) +
      (rule.Filter.And.Tags?.length ?? 0) +
      (rule.Filter.And.ObjectSizeGreaterThan !== undefined ? 1 : 0) +
      (rule.Filter.And.ObjectSizeLessThan !== undefined ? 1 : 0)
    if (predicateCount < 2) {
      errors.push(`${ruleLabel}: And filter must contain at least 2 predicates`)
    }
  }

  // Top-level conditions must not combine with each other or with And
  if (rule.Filter) {
    const topLevelConditions = [
      rule.Filter.Prefix !== undefined,
      rule.Filter.Tag !== undefined,
      rule.Filter.ObjectSizeGreaterThan !== undefined,
      rule.Filter.ObjectSizeLessThan !== undefined,
    ].filter(Boolean).length
    if (topLevelConditions > 1 || (rule.Filter.And && topLevelConditions > 0)) {
      errors.push(`${ruleLabel}: Multiple filter conditions (Prefix, Tag, ObjectSize) must be wrapped in an And clause`)
    }
  }
  ```
- **Cross-dependency on Finding #11 — resolved:** the server's `And`-predicate counter used to treat `val.Tags !== undefined && val.Tags.length > 0` as **one** predicate regardless of tag count — a separate bug, fixed in Finding #11 below (server now counts each tag individually). The client snippet above already reflects the corrected per-tag counting so it stays in sync with the fixed server logic — implement Finding #11's server fix in the same pass as this one, not before/after separately.
- **Risk:** low — additive validation logic, purely rejects things the server would reject anyway (moves the error message earlier/friendlier, doesn't change what's ultimately accepted... except for the interaction with Finding #11 noted above).
- **Verification:** unit test — feed `validateLifecycleRules` a rule with `Filter: { And: { Prefix: "x" } }` (1 predicate) and assert it's rejected locally with the expected message; same for a rule with both top-level `Prefix` and `Tag` set without `And`. `pnpm --filter @cobaltcore-dev/aurora test`.

### 10. Server + Client: `ExpiredObjectDeleteMarker` not made mutually exclusive with `Days`/`Date`

- **Source:** CodeRabbit (comment `3783805211`), Minor/Quick win — server-only in the original comment; client half added by the same "mirror the gap" pattern as Finding #9, per user decision.
- **Files:** `packages/aurora/src/server/Storage/types/ceph.ts` (lines 783-796, `lifecycleExpirationSchema`) and `.../client/.../utils/lifecycleUtils.ts` (`validateLifecycleRules`, lines 184-190 area).
- **Problem:** the schema has two refinements — "at least one of Days/Date/ExpiredObjectDeleteMarker" and "not both Days and Date" — but nothing preventing `{ Days: 30, ExpiredObjectDeleteMarker: true }` or `{ Date: "...", ExpiredObjectDeleteMarker: true }` from passing. Per the S3 lifecycle API, `ExpiredObjectDeleteMarker` is a distinct, mutually-exclusive action (cleaning up orphaned delete markers in versioned buckets) from date/day-based expiration; RGW rejects the combination.
- **Confirmed untested:** `ceph.test.ts:1215-1217` only tests `ExpiredObjectDeleteMarker` alone and `{Days, Date}` rejection — no test exists for `{Days/Date} + ExpiredObjectDeleteMarker`, confirming this is an unintentional gap, not a deliberate allowance.
- **Confirmed not reachable via Aurora's own form** (same reachability pattern as Finding #9): `LifecycleRuleForm.tsx` has no UI for `ExpiredObjectDeleteMarker` (preserve-only field, like `NewerNoncurrentVersions` in Finding #4); when the user fills in `Days`, the whole `Expiration` object is replaced wholesale (not merged), so the form can never itself produce this combination. Real-world trigger is the same as Finding #9: an externally-authored rule with this combination sits in a bucket, and editing/deleting an *unrelated* rule pulls it through `validateLifecycleRules` on the full array, hitting a generic server rejection instead of a targeted inline message. `validateLifecycleRules` currently only checks "ExpiredObjectDeleteMarker cannot be combined with tag-based filters" (line ~184-190) — not this Days/Date case.
- **Fix — server**, add a third `.refine` to `lifecycleExpirationSchema`:
  ```tsx
  .refine((val) => !(val.ExpiredObjectDeleteMarker !== undefined && (val.Days !== undefined || val.Date !== undefined)),
    "ExpiredObjectDeleteMarker cannot be combined with Days or Date")
  ```
- **Fix — client**, mirror in `validateLifecycleRules`:
  ```tsx
  if (
    rule.Expiration?.ExpiredObjectDeleteMarker === true &&
    (rule.Expiration.Days !== undefined || rule.Expiration.Date !== undefined)
  ) {
    errors.push(`${ruleLabel}: ExpiredObjectDeleteMarker cannot be combined with Days or Date`)
  }
  ```
- **Tests to add** in `ceph.test.ts` next to the existing `lifecycleExpirationSchema` block (template: "should reject both Days and Date", line ~1224):
  ```tsx
  it("should reject Days with ExpiredObjectDeleteMarker", () => {
    expect(lifecycleExpirationSchema.safeParse({ Days: 30, ExpiredObjectDeleteMarker: true }).success).toBe(false)
  })
  it("should reject Date with ExpiredObjectDeleteMarker", () => {
    expect(lifecycleExpirationSchema.safeParse({ Date: "2024-12-31T00:00:00.000Z", ExpiredObjectDeleteMarker: true }).success).toBe(false)
  })
  ```
- **Risk:** low — additive refinement/check, only rejects a combination the server (RGW) would reject anyway.
- **Verification:** new unit tests above (server + client); `pnpm --filter @cobaltcore-dev/aurora test`.

### 11. Server: `And` filter with 2+ tags (no other condition) wrongly rejected — real bug, reachable via Aurora's own UI

- **Source:** CodeRabbit (comment `3783805217`), Major. Unlike Findings #9/#10, this is reachable through Aurora's own form, not only via externally-authored rules.
- **File:** `packages/aurora/src/server/Storage/types/ceph.ts`, lines 870-893 (`lifecycleFilterAndSchema`'s predicate-count `.refine`).
- **Problem:**
  ```tsx
  const predicateCount = [
    val.Prefix !== undefined && val.Prefix !== "",
    val.Tags !== undefined && val.Tags.length > 0,   // ← whole Tags array = ONE predicate, regardless of length
    val.ObjectSizeGreaterThan !== undefined,
    val.ObjectSizeLessThan !== undefined,
  ].filter(Boolean).length
  return predicateCount >= 2
  ```
  `val.Tags !== undefined && val.Tags.length > 0` is a single boolean — 1 tag or 10 tags both count as exactly 1 toward `predicateCount`. So `Filter.And = { Tags: [tag1, tag2] }` (2 tags, no Prefix/Size) computes `predicateCount = 1` → fails the `>= 2` check → rejected with "And filter must contain at least 2 predicates", even though 2 ANDed tags is a fully valid, common S3 lifecycle filter (S3 *requires* wrapping 2+ tags in `And` — a single top-level `Tag` only supports one condition).
- **Confirmed reachable via Aurora's own form (not just `aws-cli`), making this the most user-facing finding in this pass:**
  - `LifecycleRuleForm.tsx`'s "Scope" section lets a user add any number of tags with no cap and no required Prefix.
  - `normalizeFilter()` (`lifecycleUtils.ts:29-60`): `if ((hasPrefix && hasTags) || (hasTags && tags.length > 1)) return { And: { Prefix: hasPrefix ? prefix : undefined, Tags: hasTags ? tags : undefined } }` — a user adding 2 tags and leaving Prefix empty produces exactly `{ And: { Tags: [tag1, tag2] } }`, the shape this bug rejects.
  - **Concretely: create a rule, add two tags, no prefix, hit Save → validation error on a completely legitimate action.**
- **Confirmed via existing tests** (`ceph.test.ts:1372-1424`): `"should reject And with only 1 predicate"` (1 tag → correctly `false`) exists, but there is **no test for "2+ tags alone → should be `true`"** — the exact case that's currently broken; nobody wrote a test for it, so nobody caught the bug.
- **Fix:** count tags individually instead of as one flag:
  ```tsx
  const predicateCount =
    (val.Prefix !== undefined && val.Prefix !== "" ? 1 : 0) +
    (val.Tags?.length ?? 0) +
    (val.ObjectSizeGreaterThan !== undefined ? 1 : 0) +
    (val.ObjectSizeLessThan !== undefined ? 1 : 0)
  return predicateCount >= 2
  ```
  Manually checked against all 7 existing `lifecycleFilterSchema`/And tests in `ceph.test.ts:1362-1424` — every one produces the identical pass/fail result under the new formula (no regressions); only the missing "2+ tags alone" case changes from incorrectly-`false` to correctly-`true`.
- **No mapper changes needed:** confirmed CodeRabbit's own note is correct — `lifecycleMapper.ts#L46-54` and the client `normalizeFilter` (`lifecycleUtils.ts#L48-56`) already emit the correct `{ And: { Tags: [...] } }` shape; the bug is purely in the Zod predicate count, not in how the filter is constructed.
- **New test** (`ceph.test.ts`, next to the existing And-filter block):
  ```tsx
  it("should accept And with 2+ tags and nothing else", () => {
    const input = { And: { Tags: [{ Key: "Type", Value: "Archive" }, { Key: "Team", Value: "Platform" }] } }
    expect(lifecycleFilterSchema.safeParse(input).success).toBe(true)
  })
  ```
- **Coupled with Finding #9:** the client-side `predicateCount` mirror added in Finding #9 already uses this corrected per-tag counting — implement both fixes together so client and server never disagree on this shape.
- **Risk:** low — the fix only *loosens* an incorrectly-strict check to match actual S3 semantics; verified no existing accepted/rejected case flips.
- **Verification:** new unit test above; full `ceph.test.ts` suite run to confirm no regressions in the other 6 And/filter tests; manual — create a rule via the Aurora UI with 2 tags and no prefix, confirm it now saves successfully.

### 12. Server: `toSdkLifecycleRules` return type (`LifecycleRule[]`) lies about `Date` shape, forcing `any`/casts

- **Source:** Copilot (comment `3802426757`), type-safety, no severity tag from this tool — treated as Minor.
- **File:** `packages/aurora/src/server/Storage/helpers/lifecycleMapper.ts`, lines 71-127 (`toSdkLifecycleRules`); consumer at `packages/aurora/src/server/Storage/routers/ceph/lifecycleRouter.ts`, lines 149-159 (`set` procedure).
- **Problem:** `toSdkLifecycleRules` is declared `(wireRules: LifecycleRuleRead[]): LifecycleRule[]`, where `LifecycleRule = z.infer<typeof lifecycleRuleSchema>` (`ceph.ts:1161`) and that schema's `Expiration.Date`/`Transitions[].Date` are `z.string().datetime(...)` — i.e. the declared return type claims `Date` fields are `string`. But the function body actually populates them with real `Date` objects (via `toMidnightUTC(...)`), then does `const result: any = {...}` / `return result as LifecycleRule` to paper over the mismatch.
- **Confirmed this already costs real friction, not just theoretical risk:**
  1. Inside the function itself: `any` + a trust-me cast.
  2. At the only production caller (`lifecycleRouter.ts:149`): `const transformed: any = { ...rule }`, and later `{ Rules: transformedRules } as BucketLifecycleConfiguration`.
  3. Even in tests (`lifecycleMapper.test.ts:65-67`) a dead defensive branch is required purely because of the wrong static type:
     ```tsx
     const date = typeof expiration.Date === "string" ? new Date(expiration.Date) : expiration.Date
     ```
     The test *knows* (from reading the implementation) this is always a `Date`, but the incorrect declared type forces handling a `string` case that can never actually occur.
- **Real risk:** if a future refactor passes `toSdkLifecycleRules`'s output somewhere expecting the true wire-shaped `LifecycleRule` (e.g. re-validating via `lifecycleRuleSchema.parse()`, which expects strings), TypeScript won't catch it — the declared type matches even though the runtime shape doesn't.
- **Confirmed the right target type already exists** — `@aws-sdk/client-s3` exports its own `LifecycleRule` interface with `Date` correctly typed as `Date | undefined` and includes `Prefix?: string` — it fully covers what the mapper builds and what `BucketLifecycleConfiguration.Rules: LifecycleRule[]` (the SDK's own type) expects downstream.
- **Fix:**
  ```tsx
  import type { LifecycleRule as AwsSdkLifecycleRule } from "@aws-sdk/client-s3"

  export function toSdkLifecycleRules(wireRules: LifecycleRuleRead[]): AwsSdkLifecycleRule[] {
    return wireRules.map((rule): AwsSdkLifecycleRule => {
      // build directly against AwsSdkLifecycleRule's shape — no `const result: any` needed
      ...
    })
  }
  ```
  Follow-on in the only caller, `lifecycleRouter.ts:149`: replace `const transformed: any = { ...rule }` with a properly-typed `AwsSdkLifecycleRule`; the trailing `{ Rules: transformedRules } as BucketLifecycleConfiguration` cast likely becomes unnecessary once the types line up (`BucketLifecycleConfiguration.Rules` is `LifecycleRule[]` from the same SDK).
- **Risk/effort:** moderate — touches an exported function's signature plus its one production caller; behavior is unchanged (types only). Not a one-line fix; budget real review time, not a quick win.
- **Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck` (should reveal exactly where the old `any` was hiding real shape mismatches, if any); `pnpm --filter @cobaltcore-dev/aurora test` for `lifecycleMapper.test.ts` and `lifecycleRouter.test.ts`; optionally simplify the now-dead `typeof expiration.Date === "string"` branches in the test file.

### 13. Server: rate limiter is per-process/in-memory with O(n) cleanup on every `set` — narrow fix applied to all 3 copies (lifecycle, CORS, bucket-policy)

- **Source:** Copilot (comment `3802426811`), scalability. Scope widened to two files outside this PR's diff, per user decision (option B of three presented).
- **Files:** `packages/aurora/src/server/Storage/routers/ceph/lifecycleRouter.ts` (lines 19-49, this PR), `.../corsRouter.ts` (lines 9-35, pre-existing from PR #1092), `.../bucketPolicyRouter.ts` (lines 16-45, pre-existing) — all three contain a byte-for-byte identical rate-limiter template (only the `Map` variable name, error message, and `windowMs` differ).
- **Problem:** each `checkXSetRateLimit` function does a full `for...of` sweep over its entire module-level `Map` on **every single call** to purge expired entries:
  ```tsx
  for (const [k, v] of lifecycleSetRateLimits.entries()) {   // O(n) across ALL active keys server-wide, on every set call
    if (now > v.resetAt) lifecycleSetRateLimits.delete(k)
  }
  ```
  Also, being a plain in-process `Map`, the limiter doesn't coordinate across multiple server replicas and resets on every restart/deploy.
- **Scope decision — what's in, what's out:**
  - **Rejected (out of scope):** a "real" distributed rate limiter (e.g. Redis-backed) — this is an infrastructure/architecture addition affecting the whole project's rate-limiting convention, not a point fix for one PR's review comments. Revisit as its own initiative if multi-replica correctness becomes an actual requirement.
  - **In scope:** replacing the O(n) full-map sweep with O(1) per-key cleanup via `setTimeout`, applied identically to **all three** copies of this pattern — fixing only `lifecycleRouter.ts` (the one file actually in this PR's diff) would leave two other, pre-existing, byte-identical copies with the same inefficiency, recreating the exact "fixed in one place, still broken next door" inconsistency flagged repeatedly elsewhere in this review pass (Findings #3, #7).
- **Fix (applied to all three files, same shape each time — example using `lifecycleRouter.ts`):**
  ```tsx
  const lifecycleSetRateLimits = new Map<string, { count: number; resetAt: number }>()

  function checkLifecycleSetRateLimit(bucketName: string, projectId: string): void {
    const key = `${projectId}:${bucketName}`
    const now = Date.now()
    const windowMs = 60 * 1000 // 1 minute

    const limit = lifecycleSetRateLimits.get(key)

    if (!limit || now > limit.resetAt) {
      lifecycleSetRateLimits.set(key, { count: 1, resetAt: now + windowMs })
      // Self-clean this one key after its window closes — O(1) per key, no full-map scan.
      setTimeout(() => {
        const current = lifecycleSetRateLimits.get(key)
        // Guard: only delete if this timer's entry is still the current one (not a newer window
        // that started for the same key before this stale timer fired).
        if (current && current.resetAt <= Date.now()) {
          lifecycleSetRateLimits.delete(key)
        }
      }, windowMs).unref()
      return
    }

    if (limit.count >= 10) {
      throw new TRPCError({ code: "TOO_MANY_REQUESTS", message: "..." /* unchanged per-file message */ })
    }

    limit.count++
  }
  ```
  Apply the same transform (drop the `for...of` sweep, add the per-key `setTimeout` cleanup with the staleness guard) to `corsSetRateLimits`/`checkCorsSetRateLimit` in `corsRouter.ts` and `policySetRateLimits`/`checkPolicySetRateLimit` in `bucketPolicyRouter.ts`, each keeping its own `windowMs` (1 min for CORS/lifecycle, 5 min for policy) and error message unchanged.
  `.unref()` keeps the timer from blocking Node process shutdown/test teardown — worth keeping even though this is a minor addition beyond Copilot's literal ask.
- **Risk:** low — purely an internal cleanup-strategy swap; the actual rate-limiting decision (count/window/reject) logic is untouched, so external behavior (429s, thresholds) is identical. Slightly widens the change footprint to 2 files outside this PR's own diff — confirm no other in-flight PR is touching `corsRouter.ts`/`bucketPolicyRouter.ts` concurrently before pushing.
- **Verification:** existing rate-limit tests for all three routers (if present) continue to pass unchanged; add/confirm a test that after `windowMs` elapses (fake timers), the map no longer holds the expired key (proves the `setTimeout` cleanup actually fires) without needing a subsequent call to trigger cleanup. `pnpm --filter @cobaltcore-dev/aurora test`.

### 14. Client: `LifecycleRulesTab.tsx` derives row index via `rules.indexOf(rule)` — fragile-by-reference and O(n²)

- **Source:** Copilot (comment `3802426838`), correctness/efficiency. Confirmed as a robustness/best-practice fix rather than an actively-triggerable bug — see reachability analysis below.
- **File:** `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRulesTab.tsx`, lines 155-179 (`sortRules` + `filteredRulesWithIndices`).
- **Problem:**
  ```tsx
  const filteredRulesWithIndices = sortRules(rules)
    .map((rule) => ({ rule, originalIndex: rules.indexOf(rule) }))   // reference (===) lookup
    .filter(...)
  ```
  `sortRules` returns `[...rules].sort(...)` — a new array, same object references. `rules.indexOf(rule)` then finds each sorted rule's original position by reference equality; if the same object reference ever appeared twice in `rules`, `indexOf` would always resolve to the *first* occurrence for both, mislabeling one row's index.
- **Reachability, checked end-to-end (downgrades this from "live bug" to "robustness/best-practice fix"):** traced the full data path — `rules` comes from `lifecycleData?.rules` (React Query) ← the `get` tRPC procedure, which does `rawRules.map((rule) => lifecycleRuleReadSchema.parse(rule))` (`lifecycleRouter.ts`). Both the JSON deserialization and Zod's `.parse()` always produce a fresh, distinct object per array element — even two rules with byte-identical content get different object references. So duplicate references cannot currently arise through the normal `get` → React Query → render path; the "wrong index" scenario isn't reachable today. It remains a latent footgun if a future change anywhere in that pipeline introduces object reuse/memoization — the fix removes the reliance on reference identity entirely rather than depending on this implementation detail holding forever.
- **O(n²) claim, checked against the doc's own stated cap:** `009_ceph_s3_bff.md` documents "Maximum 100 rules per bucket (UI limit)" — at n=100 the `indexOf`-in-`map` gives ~10,000 comparisons, negligible in practice. Not a real performance concern at the enforced scale, but the fix removes it as a side effect anyway.
- **Confirmed `sortRules` has exactly one call site** (line 178) — safe to change its signature.
- **Fix:** attach the original index before sorting instead of recovering it afterward by reference lookup:
  ```tsx
  interface RuleWithOriginalIndex {
    rule: LifecycleRuleRead
    originalIndex: number
  }

  const sortRules = (items: RuleWithOriginalIndex[]): RuleWithOriginalIndex[] => {
    return [...items].sort((a, b) => {
      let comparison: number
      switch (lifecycleSortBy ?? "ID") {
        case "ID": comparison = (a.rule.ID || "").localeCompare(b.rule.ID || ""); break
        case "Status": comparison = a.rule.Status.localeCompare(b.rule.Status); break
        case "Expiration": comparison = (a.rule.Expiration?.Days ?? -1) - (b.rule.Expiration?.Days ?? -1); break
        default: comparison = (a.rule.ID || "").localeCompare(b.rule.ID || "")
      }
      return (lifecycleSortDirection ?? "asc") === "desc" ? -comparison : comparison
    })
  }

  const rulesWithOriginalIndices = rules.map((rule, originalIndex) => ({ rule, originalIndex }))
  const filteredRulesWithIndices = sortRules(rulesWithOriginalIndices).filter(({ rule }) => {
    if (!lifecycleSearch) return true
    return (rule.ID || "").toLowerCase().includes(lifecycleSearch.toLowerCase())
  })
  ```
  `indexOf` is removed entirely; index correctness now holds by construction, independent of object-reference behavior anywhere upstream.
- **Risk:** low — refactor of one function and its single call site; sort/filter output/ordering unchanged, only how `originalIndex` is derived changes.
- **Verification:** existing tests for `LifecycleRulesTab`/`LifecycleRulesTable` covering select/edit/delete-by-row continue to pass; `pnpm --filter @cobaltcore-dev/aurora typecheck` and `test`.

### 15. i18n: numeric-only placeholders wrapped in Lingui `t` macro, extracted as meaningless translatable strings

- **Source:** Copilot, posted twice with identical text (comments `3802426893` and `3802426937` — duplicate, counted as one finding).
- **File:** `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRuleForm.tsx`, lines 373, 415, 453.
- **Problem:**
  ```tsx
  placeholder={t`30`}   // line 373, Expiration Days
  placeholder={t`90`}   // line 415, NoncurrentVersionExpiration Days
  placeholder={t`7`}    // line 453, AbortIncompleteMultipartUpload Days
  ```
  All three are `type="number"` input placeholders used purely as numeric examples ("e.g. 30"), not user-facing prose — wrapping them in `t` sends them through Lingui extraction as if they were translatable copy.
- **Confirmed concrete effect in the actual `.po` catalogs:**
  ```
  # packages/aurora/src/locales/en/messages.po
  msgid "30"
  msgstr "30"

  # packages/aurora/src/locales/de/messages.po
  msgid "30"
  msgstr ""     ← empty/"missing" translation
  ```
  Same pattern for `"7"` and `"90"`. The project has 2 locales (`en`, `de`) — the German catalog now carries 3 meaningless "untranslated" entries (there's nothing to meaningfully translate about a bare digit placeholder).
- **Doesn't fail CI:** `check-i18n` runs `lingui extract --clean && lingui compile --typescript --verbose` with no `--strict` flag, so empty `msgstr`s don't break the build — this is pure noise/future translator busywork, not a blocker.
- **Fix:** drop the `t` macro, use plain string literals:
  ```tsx
  placeholder="30"
  placeholder="90"
  placeholder="7"
  ```
  Then re-run `pnpm check-i18n` — `lingui extract --clean` will remove the now-unused `msgid "30"`/`"7"`/`"90"` entries from both `.po` files automatically.
- **Risk:** none — placeholder text displayed to the user is identical; only stops being routed through the translation pipeline.
- **Verification:** `pnpm check-i18n`; confirm `msgid "30"`/`"7"`/`"90"` no longer appear in `en/messages.po` or `de/messages.po`; visually confirm the three placeholders still show in the form.

---

## Рассмотрено и отклонено

### 5b. "Add atomic precondition/revision-token to `get`/`set`/`delete`, enforce server-side" — отклонено

- **Source:** CodeRabbit (comment `3783805184`), the other half of the same Major/Heavy-lift finding as 5a above: *"Add an expected revision or configuration token to `get`, `set`, and `delete`. Enforce the comparison atomically on the server."*
- **Why rejected:** verified against the AWS SDK types actually used by this router (`@aws-sdk/client-s3@3.1100.0`):
  - `GetBucketLifecycleConfigurationOutput` (`dist-types/models/models_0.d.ts:7088`) has fields `Rules` and `TransitionDefaultMinimumObjectSize` only — **no ETag, no version, nothing usable as a revision token.**
  - `PutBucketLifecycleConfigurationRequest` (`dist-types/models/models_0.d.ts:14075`) has fields `Bucket`, `ChecksumAlgorithm`, `LifecycleConfiguration`, `ExpectedBucketOwner` — **no `IfMatch`/conditional-write parameter.**
  - This mirrors the real AWS S3 API: unlike object `PutObject` (which supports `IfMatch`/`IfNoneMatch`), the Bucket Lifecycle Configuration sub-resource has no conditional-write or versioning primitive at the protocol level, in AWS S3 or in Ceph RGW's S3-compatible implementation. Aurora cannot ask Ceph to do a conditional PUT here — the capability doesn't exist to ask for.
  - The only way to get "server-side atomic" semantics would be for Aurora to invent and maintain its **own** out-of-band revision store (Aurora currently has no persistence layer — it's a stateless BFF over OpenStack/Ceph), which is exactly the "Heavy lift" CodeRabbit itself flagged.
  - Even if built, an Aurora-only revision store would **only** catch races between Aurora sessions — it would not protect against concurrent writes from `aws-cli` or any other S3 client hitting Ceph RGW directly, which don't participate in Aurora's token scheme. That defeats the actual goal (protection against *any* concurrent modification), so the heavy investment wouldn't even fully solve the stated problem.
- **What's kept instead:** the existing client-side best-effort mitigation (refetch immediately before mutating, compare via `JSON.stringify`, reject on mismatch with a "configuration has changed" message) already present in the edit path here and in both delete modals, now also extended to the add path via 5a above. This narrows the race window to the time between refetch and mutate (sub-second in practice) without inventing new infrastructure that can't fully deliver on the ask anyway.
- **Status:** not fixed, by design — infeasible with the current Ceph RGW/S3 API surface; revisit only if RGW/S3 ever add a conditional-write primitive for bucket lifecycle configuration.
