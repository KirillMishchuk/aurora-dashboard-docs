# Plan: PR #1178 code-review fixes (Ceph S3 lifecycle rules)

**Date:** 2026-08-20 · **Status:** partially implemented 2026-08-20 (Steps 1-5 done; 6-11 not started)

> Note: this plan fixes the 10 findings from the `code-review` skill's 2026-08-20 pass
> (saved at `../pr-reviews/pr-1178-review.md`), run against branch `kiryl-ceph-lifecycle-rules`
> head `eb82d69c` — which already includes an earlier, separate 15-fix round (commit `092fd7e3`,
> tracked by `2026-08-18-pr-1178-review-findings-fixes-implementation.md` in this folder, status
> implemented). These 10 findings are new/post that round, not a re-run of it. A third,
> unrelated CodeRabbit+Copilot-sourced 16-finding review (`2026-08-18-pr-1178-review-findings-fixes.md`,
> status not implemented) also exists for this PR — worth a quick diff-check against this plan's
> steps before implementing, in case of overlap.

I have full context on the PR. Here is the plan.

---

# 📋 IMPLEMENTATION PLAN: PR #1178 review-finding fixes (Ceph S3 bucket lifecycle rules)

## Overview

Fix all 10 verified review findings on branch `kiryl-ceph-lifecycle-rules` before merge: five correctness bugs (client-side Days validation, prefix trim inconsistency, a missing server constraint, a total-failure GET path, and a false-positive concurrency check), three duplication removals (rate limiter, delete modals, `normalizeFilter`), one dead-code/test-parity fix, and one render-efficiency fix. No backward-compat or migration concerns — this is pre-merge feature-branch work.

## Architecture Analysis

**Current state — files in scope** (all absolute):

Server:
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/lifecycleRouter.ts` — `get`/`set`/`delete` on `cephProtectedProcedure`; inline rate limiter at lines 20–51
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/helpers/lifecycleMapper.ts` — `normalizeFilter` (line 28, **no production caller**), `toSdkLifecycleRules` (line 72, used by `set`), `toWireLifecycleRules` (line 140, **no production caller**)
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/types/ceph.ts` — lifecycle Zod schemas, lines 770–1167; `lifecycleRuleSchema` refinements at 960–1001; `getLifecycleOutputSchema` at 1132
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/corsRouter.ts` (limiter lines 8–39) and `.../bucketPolicyRouter.ts` (limiter lines 16–47) — already shipped

Client (all under `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/`):
- `Buckets/LifecycleRuleForm.tsx` — TanStack Form; `canSubmit()` at 140–167; warning at 137–138; submit at 78–124
- `Buckets/utils/lifecycleUtils.ts` — `normalizeFilter` (29, client copy), `toLifecycleRule` (73), `validateLifecycleRules` (131), formatters
- `Buckets/LifecycleRuleModal.tsx` (freshness at 126), `Buckets/DeleteLifecycleRuleModal.tsx` (129), `Buckets/DeleteLifecycleRulesModal.tsx` (131)
- `Buckets/LifecycleRulesTab.tsx` — derivations at 151–194, uncached
- `Buckets/LifecycleRulesTable.tsx` — **no `React.memo` anywhere** (see risk table)
- `hooks/useBucketInfo.ts` — prefetches `lifecycle.get`

Existing tests to extend (do **not** create parallel files for these):
| Finding | Test file |
| --- | --- |
| 1, 2 | `Buckets/LifecycleRuleForm.test.tsx` (`describe("Form validation")`, line 405) |
| 1, 3, 5, 8 | `Buckets/utils/lifecycleUtils.test.ts` |
| 3 | `server/Storage/types/ceph.test.ts` → `describe("lifecycleRuleSchema")` at 1461, EODM cases at 1585–1615 |
| 4, 9 | `server/Storage/routers/ceph/lifecycleRouter.test.ts` (`describe("get")`, 65) + `server/Storage/helpers/lifecycleMapper.test.ts` |
| 6 | `lifecycleRouter.test.ts` (300, 336, 364), `corsRouter.test.ts` (447, 484), `bucketPolicyRouter.test.ts` (361, 403) — these must pass **unchanged** |

New test files needed (nothing exists today): `LifecycleRulesTab.test.tsx`, `useLifecycleRuleDeletion.test.tsx`, `helpers/rateLimiter.test.ts`. Use `Buckets/CorsRulesTab.test.tsx` as the harness template — it `vi.mock`s `trpcReact`, `@tanstack/react-router`, `useProjectId` and the `Route.useSearch` module.

**Proposed approach:** correctness first (steps 1–6), each independently landable; then the two isolated refactors (7, 8); then the two shared-infrastructure refactors (9, 10) last so they can be dropped without blocking the PR.

## Potential Problems & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| 🔴 **`get` silently dropping rules + `set` being a full replace = permanent data loss.** Finding #4's "skip the bad rule" fix, done naively, means the next save PUTs the array *without* the skipped rule — RGW deletes it. Index misalignment also breaks the freshness check. | **High** | Step 4 returns `skippedRuleCount` in the GET output; Step 5 makes the tab show a warning **and disable all mutating actions** when it is > 0. Non-negotiable pair. |
| ⚠️ New Abort+tags check in `validateLifecycleRules` narrows behavior on *existing* configs | Medium | `validateLifecycleRules` runs on the **remaining** rules during delete. A pre-existing externally-authored Abort+tags rule will now block deleting an unrelated rule. Same class as the already-shipped EODM check. Accepted; called out in Step 3. |
| 🔴 #6 and #9 touch already-shipped CORS + bucket-policy code | High blast radius | Do them last, in separate commits. Preserve the exact error-message strings (tests regex `/rate limit exceeded/i`, users see the text). Existing rate-limit tests are the regression gate. |
| Finding #10's premise is partly wrong: `LifecycleRulesTable.tsx` has **no `React.memo`** | Low | Verified by grep — the only `useMemo` in the whole `Buckets/` folder is in `BucketPolicyModal.tsx`. `useMemo`/`useCallback` alone buy the sort/filter savings; row-level bail-out requires *introducing* a memoized row (Step 8b, optional). |
| Finding #1's stated mechanism is partly wrong | Low | `e.preventDefault()` runs *after* the submit event, so it does not suppress constraint validation; `LifecycleRuleModal.tsx:175` uses `requestSubmit()`, which *does* validate, and Juno's `TextInput` extends `InputHTMLAttributes` and spreads `...props`, so `min="1"` reaches the DOM. The real gap is the enabled Save button + zero inline feedback + jsdom tests bypassing it. Fix is unchanged; don't chase `preventDefault`. |
| ⚠️ Trimming the Prefix silently discards legitimate S3 keys with leading/trailing spaces | Low–Medium | S3 keys *may* legitimately contain them. Step 2 normalizes the field on blur so the user sees exactly what will be saved. Listed in Open Questions. |
| New `t\`\`` strings require i18n extraction | Low | Run `pnpm --filter @cobaltcore-dev/aurora check-i18n`; commit regenerated `src/locales/{en,de}/messages.po`. CI runs `check-i18n`. |
| `@/server/Storage/types/ceph` imports `projectScopedInputSchema` from `../../trpc` | Info | Value imports from that module into the client would pull the tRPC server in. `lifecycleMapper.ts` has only `import type` imports, so its runtime graph is empty — relevant to Step 9. |

## Prerequisites

- [ ] On branch `kiryl-ceph-lifecycle-rules`, working tree clean, rebased on `main`
- [ ] Baseline green: `pnpm --filter @cobaltcore-dev/aurora test && pnpm --filter @cobaltcore-dev/aurora typecheck && pnpm --filter @cobaltcore-dev/aurora lint`
- [ ] Decide the two Open Questions below (Prefix trimming semantics; whether Step 8b lands now)

---

## Implementation Steps

### Step 1 — Validate Days fields as positive integers with inline errors (finding #1)

**Files:**
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/utils/lifecycleUtils.ts` — add helper
- `.../Buckets/LifecycleRuleForm.tsx` — use it
- `.../Buckets/utils/lifecycleUtils.test.ts`, `.../Buckets/LifecycleRuleForm.test.tsx` — extend

**What to do:**
1. In `lifecycleUtils.ts`, export:
   ```ts
   export type DaysParseResult = { ok: true; value: number } | { ok: false; reason: "empty" | "invalid" }
   export function parseDaysValue(raw: string): DaysParseResult
   ```
   Trim; `""` → `{ ok: false, reason: "empty" }`; accept only `/^\d+$/` with `Number(...) >= 1` and `Number.isSafeInteger` → `{ ok: true, value }`; everything else (`-5`, `1.5`, `1e3`, `0`, `abc`) → `{ ok: false, reason: "invalid" }`. Place it above `toLifecycleRule`, with a JSDoc noting it mirrors the server's `z.number().int().min(1)`.
2. In `LifecycleRuleForm.tsx`, after the `useStore` block (line 135), derive three error strings — only when the owning checkbox is checked, and only surface `"invalid"` (not `"empty"`) so a freshly-checked box doesn't flash an error:
   ```ts
   const daysError = (checked: boolean, raw: string) =>
     checked && parseDaysValue(raw).reason === "invalid"
       ? t`Enter a whole number of days greater than 0`
       : undefined
   const expirationDaysError = daysError(hasExpirationValue, expirationDaysValue)
   const noncurrentDaysError = daysError(hasNoncurrentExpirationValue, noncurrentDaysValue)
   const abortDaysError = daysError(hasAbortUploadValue, abortDaysValue)
   ```
3. Wire `invalid={!!<x>Error}` and `errortext={<x>Error}` onto the three `TextInput`s (lines ~287, ~329, ~372). Keep the existing `helptext`/`required`/`min` props.
4. In `canSubmit()` (140–167) replace the three emptiness checks:
   - Expiration (152–156): if `hasExpiration` — `const r = parseDaysValue(values.expirationDays)`; valid iff `r.ok`, **or** (`r.reason === "empty"` and `hasNonDaysExpiration`). Never valid when `r.reason === "invalid"`.
   - Noncurrent (159): `if (values.hasNoncurrentExpiration && !parseDaysValue(values.noncurrentDays).ok) return false`
   - Abort (162): same shape.
5. In `onSubmit` (89–121), use the parsed values instead of bare `parseInt`, e.g. `const exp = parseDaysValue(value.expirationDays); if (exp.ok) newRule.Expiration = { Days: exp.value }` — keeping the existing `else if (editingRule?.Expiration)` preservation branch. Same for noncurrent (103) and abort (117).

**Expected outcome:** Save stays disabled and an inline error appears for `-5`, `0`, `1.5`; unchanged for valid input and for the edit-a-Date-rule case.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets/LifecycleRuleForm.test.tsx`

**Tests to add** (in `describe("Form validation")` at line 405):
- typing `-5` into Expiration Days → `onValidationChange` last called with `false`, error text rendered
- typing `1.5` → invalid
- typing `0` → invalid
- typing `30` → valid (regression of existing test at 430)
- editing `mockRuleWithDateExpiration` with empty Days → still valid (regression of 132)
In `lifecycleUtils.test.ts`, a new `describe("parseDaysValue")` covering the table above.

---

### Step 2 — Make the whole-bucket warning agree with the submitted filter (finding #2)

**Files:** `.../Buckets/LifecycleRuleForm.tsx`, `.../Buckets/LifecycleRuleForm.test.tsx`

**What to do:**
1. In `onSubmit` (line 79), compute `const trimmedPrefix = value.Prefix.trim()` and pass `trimmedPrefix || undefined` to `normalizeFilter`. A whitespace-only Prefix now yields `{ Prefix: "" }` — exactly what the warning at line 137 promises.
2. Normalize the field on blur so the user sees the saved value. In the `Prefix` field (221–233), replace `onBlur={field.handleBlur}` with a handler that calls `field.handleChange(field.state.value.trim())` when it differs, then `field.handleBlur()`.
3. Leave `willExpireWholeBucket` (137–138) as-is — it is now the correct predicate.

**Expected outcome:** Prefix `"   "` → warning shown **and** a whole-bucket filter saved. Prefix `" logs/ "` → saved as `logs/`, no warning.

**Tests to add** (new `describe("Prefix trimming")`): whitespace-only prefix submits `Filter === { Prefix: "" }`; ` logs/ ` submits `Filter.Prefix === "logs/"`; the Prefix input's value is trimmed after blur.

---

### Step 3 — Enforce "Abort cannot combine with tag filters" server-side and in the shared validator (finding #3)

**Files:** `packages/aurora/src/server/Storage/types/ceph.ts`, `.../Buckets/utils/lifecycleUtils.ts`, plus `ceph.test.ts` and `lifecycleUtils.test.ts`

**What to do:**
1. In `ceph.ts`, append a fourth `.refine()` to `lifecycleRuleSchema` immediately after the `ExpiredObjectDeleteMarker` refine that ends at line 1001, copying its structure exactly:
   ```ts
   .refine(
     (val) => {
       if (val.AbortIncompleteMultipartUpload === undefined) return true
       const hasTagFilter =
         val.Filter?.Tag !== undefined || (val.Filter?.And?.Tags !== undefined && val.Filter.And.Tags.length > 0)
       return !hasTagFilter
     },
     { message: "AbortIncompleteMultipartUpload cannot be combined with tag-based filters" }
   )
   ```
2. In `validateLifecycleRules` (`lifecycleUtils.ts`), insert the mirrored check right after the EODM tag-filter block (ends line 194), same `errors.push(\`${ruleLabel}: …\`)` shape and same message text.
3. Leave `LifecycleRuleForm.tsx`'s existing gate (`canSubmit` line 164 + the disabled checkbox at 358) untouched — it is now the outermost of three consistent layers.

**Expected outcome:** the constraint holds at the API boundary, not just in the form.

**Tests to add:**
- `ceph.test.ts`, inside `describe("lifecycleRuleSchema")`, next to lines 1585–1615: reject Abort + `Filter.Tag`; reject Abort + `Filter.And.Tags`; **accept** Abort + prefix-only filter; accept Abort + no filter.
- `lifecycleUtils.test.ts`, inside `describe("validateLifecycleRules")` after the EODM test at 201: the same three cases against `validateLifecycleRules`.

**⚠️ Note in the commit body** that this can now block deleting an unrelated rule in a bucket whose *existing* config has an Abort+tags rule — same trade-off the EODM check already makes.

---

### Step 4 — Route `get` through `toWireLifecycleRules` with per-rule graceful degradation (findings #4 + #9, server half)

**Files:** `packages/aurora/src/server/Storage/helpers/lifecycleMapper.ts`, `.../routers/ceph/lifecycleRouter.ts`, `.../types/ceph.ts`, plus `lifecycleMapper.test.ts`, `lifecycleRouter.test.ts`, `ceph.test.ts`

**What to do:**
1. In `lifecycleMapper.ts`, extract the body of `toWireLifecycleRules` (140–194) into a new exported `toWireLifecycleRule(rule: AwsSdkLifecycleRule): LifecycleRuleRead`, and redefine `toWireLifecycleRules = (sdkRules) => sdkRules.map(toWireLifecycleRule)` so the existing round-trip tests at `lifecycleMapper.test.ts:136/162/179` keep passing verbatim.
2. Harden the date conversion inside `toWireLifecycleRule`. Lines 156 and 166 call `.toISOString()` unconditionally; if RGW/the SDK ever hands back a string this throws `TypeError`. Add a local
   ```ts
   const toIso = (d: Date | string | undefined) =>
     d === undefined ? undefined : d instanceof Date ? d.toISOString() : String(d)
   ```
   and use it in both places.
3. In `lifecycleRouter.ts` `get` (83–119), replace line 104 with a per-rule loop:
   ```ts
   const rules: LifecycleRuleRead[] = []
   let skippedRuleCount = 0
   for (const rawRule of rawRules) {
     try {
       const parsed = lifecycleRuleReadSchema.safeParse(toWireLifecycleRule(rawRule))
       if (parsed.success) { rules.push(parsed.data); continue }
       skippedRuleCount++
       logger.warn("Skipped unparseable S3 lifecycle rule", { bucket: bucketName, ruleId: rawRule.ID, issues: parsed.error.issues })
     } catch (mapError) {
       skippedRuleCount++
       logger.warn("Failed to map S3 lifecycle rule", { bucket: bucketName, ruleId: rawRule.ID, error: mapError })
     }
   }
   return { rules, skippedRuleCount }
   ```
   Import `logger` from `@cobaltcore-dev/signal-openstack` — the same import `helpers/s3ErrorMapper.ts:2` uses. Import `toWireLifecycleRule` and drop the now-unused `lifecycleRuleReadSchema.parse` path.
   **Do not** collapse an all-skipped config to `null`: return `{ rules: [], skippedRuleCount: n }` so the UI can distinguish "no lifecycle config" from "config exists but unreadable". The `!rawRules` early return at 99–101 still yields `{ rules: null, skippedRuleCount: 0 }`.
4. In `ceph.ts`, extend `getLifecycleOutputSchema` (1132–1134) with `skippedRuleCount: z.number().int().min(0)`, and return it from the two `rules: null` branches too.

**Expected outcome:** one aws-cli-authored rule that fails the lenient read schema no longer nukes the whole response; the tested Date-conversion path is now the real GET path.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage`

**Tests to add:**
- `lifecycleRouter.test.ts`, `describe("get")` (65): mock `Rules: [validRule, { Status: "Enabled", Transitions: [{ Days: 30 }] }]` (missing required `StorageClass`) → `rules` length 1, `skippedRuleCount` 1; all-malformed → `{ rules: [], skippedRuleCount: n }`; mock `Expiration: { Date: new Date("2026-12-31T12:00:00Z") }` → returned as an ISO string (proves `toWireLifecycleRule` is on the path); existing tests at 66/83/97 updated for the new field.
- `lifecycleMapper.test.ts`: `toWireLifecycleRule` singular; `Date` already-a-string does not throw.
- `ceph.test.ts` `describe("getLifecycleOutputSchema")` (1775): new field required/validated.

---

### Step 5 — Surface skipped rules in the UI and block mutations (finding #4, client half)

**Files:** `.../Buckets/LifecycleRulesTab.tsx`, new `.../Buckets/LifecycleRulesTab.test.tsx`

**What to do:**
1. Read `const skippedRuleCount = lifecycleData?.skippedRuleCount ?? 0`.
2. When `> 0`, render a `<Message variant="warning" title={t\`Some lifecycle rules could not be read\`}>` above the toolbar, explaining that N rules were configured outside Aurora, are not shown, and that saving would remove them — so editing is disabled until they are fixed with an external tool.
3. Gate mutations: disable the "Create Lifecycle Rule" button (228), and pass `isMutating` (or a new explicit `disableActions` prop) into `LifecycleRulesTable` so per-row Edit/Delete `PopupMenuItem`s (197–206) and the bulk-delete action are disabled.
4. Add `data-testid="lifecycle-skipped-rules-warning"` for the test.

**Expected outcome:** partially-readable configs are visible but read-only — no silent data loss through the full-replace `set`.

**Tests:** create `LifecycleRulesTab.test.tsx` modeled on `CorsRulesTab.test.tsx` (copy its `vi.mock` blocks for `trpcReact`, `@tanstack/react-router`, `useProjectId`, and the `Route` module, changing `cors*` search params to `lifecycle*`): warning renders when `skippedRuleCount > 0` and Create is disabled; no warning and Create enabled when `0`.

---

### Step 6 — Order-insensitive freshness comparison (finding #5)

**Files:** `.../Buckets/utils/lifecycleUtils.ts`, the three modals, `.../Buckets/utils/lifecycleUtils.test.ts`

**What to do:**
1. In `lifecycleUtils.ts` add and export:
   ```ts
   function stableStringify(value: unknown): string   // internal
   export function isSameLifecycleRule(a: LifecycleRuleRead | undefined, b: LifecycleRuleRead | undefined): boolean
   ```
   `stableStringify` recurses: `undefined`/primitives → `JSON.stringify`; arrays → canonicalize each element, **sort the resulting strings**, join; objects → sort keys, recurse. `isSameLifecycleRule` returns `a !== undefined && b !== undefined && stableStringify(a) === stableStringify(b)`.
   Document the assumption in JSDoc: every array in a lifecycle rule (`Filter.And.Tags`, `Transitions`, `NoncurrentVersionTransitions`) is semantically an unordered set — S3 evaluates transitions by Days, not array position — so blanket order-insensitivity is safe here.
2. Replace all three call sites, preserving the existing `!freshRule` guard (which `isSameLifecycleRule` also covers via the `undefined` check):
   - `DeleteLifecycleRuleModal.tsx:129` → `if (!isSameLifecycleRule(freshRule, cachedRule)) { … }`
   - `DeleteLifecycleRulesModal.tsx:131` → same inside the loop
   - `LifecycleRuleModal.tsx:126` → `if (!isSameLifecycleRule(freshRule, editingRule)) { … }`

**Expected outcome:** a reordered-but-equivalent `Filter.And.Tags` or `Transitions` array from RGW no longer blocks a valid delete/edit.

**Tests to add** — new `describe("isSameLifecycleRule")` in `lifecycleUtils.test.ts`: reordered `And.Tags` → equal; reordered `Transitions` → equal; different `Expiration.Days` → not equal; different object key order → equal; `undefined` vs a rule → not equal; both `undefined` → not equal.

---

### Step 7 — Extract a shared delete hook for the two lifecycle delete modals (finding #7)

**Files:**
- New: `.../storage/-components/Ceph/hooks/useLifecycleRuleDeletion.ts` (alongside the existing `hooks/useBucketInfo.ts`)
- New: `.../Ceph/hooks/useLifecycleRuleDeletion.test.tsx`
- Rewrite: `.../Buckets/DeleteLifecycleRuleModal.tsx`, `.../Buckets/DeleteLifecycleRulesModal.tsx`

**Scope decision:** lifecycle pair **only**. Do **not** touch `DeleteCorsRuleModal.tsx` / `DeleteCorsRulesModal.tsx` — note the identical CORS duplication as a follow-up issue in the PR description.

**What to do:**
1. The hook owns everything the two modals share: the `lifecycle.get` query (`enabled: isOpen && !!projectId, retry: false, staleTime: 5*60*1000`), both mutations, the `isMutating` + `onMutatingChange` effect, the `!isOpen` reset effect, `close()`, `useModalTracking`, and `confirm()` (refetch → per-index freshness via `isSameLifecycleRule` → `remaining.length === 0 ? delete : validate + set`).
   ```ts
   interface UseLifecycleRuleDeletionOptions {
     isOpen: boolean
     bucketName: string
     ruleIndices: number[]
     cachedRules?: LifecycleRuleRead[]   // bulk modal passes its `rules` prop; singular omits it
     actionPrefix: string
     cannotDeleteMessage: (errors: string[]) => string  // singular vs plural copy differs
     onClose: () => void
     onSuccess?: () => void
     onError?: (message: string) => void
     onMutatingChange?: (isMutating: boolean) => void
   }
   interface UseLifecycleRuleDeletionResult {
     isLoading: boolean
     queryError: { message: string } | null
     isMutating: boolean
     isVerifying: boolean
     confirm: () => Promise<void>
     close: () => void
   }
   ```
   **Preserve the existing behavioral difference:** the singular modal compares against `lifecycleData?.rules?.[ruleIndex]` from its own query, the bulk one against its `rules` prop. Model this as `const baseline = cachedRules ?? queryData?.rules ?? []`.
   The hook calls `useLingui()` itself for the shared stale message (`The lifecycle configuration has changed. Please refresh and try again.`); `cannotDeleteMessage` stays a caller-supplied formatter so `Cannot delete rule:` / `Cannot delete rules:` survive.
2. Rewrite both modals as presentation only, keeping **unchanged**: analytics prefixes (`storage.ceph.lifecycle.rule.delete` vs `storage.ceph.lifecycle.rules.bulk_delete`), callback signatures (`(ruleIndex)` vs `(bucketName, count)` — mapped at the call boundary), all `<Trans>`/`<Plural>` copy, the `MAX_VISIBLE_RULES = 5` list, and all `Modal` disable/`closeOnEsc` props.
3. Do not merge the two components into one — the copy, analytics identity, and callback contracts genuinely differ, and `LifecycleRulesTable.tsx` / `LifecycleRulesTab.tsx` keep their current props.

**Expected outcome:** roughly 200 duplicated lines collapse to one hook + two ~60-line presentational modals; no user-visible or analytics change.

**Verification:** Grep for `getLifecycleRuleDeletedToast` / `getLifecycleRulesDeletedToast` wiring in `LifecycleRulesTable.tsx:88–98` and `LifecycleRulesTab.tsx:306–316` — both must still receive the same argument shapes.

**Tests:** new `useLifecycleRuleDeletion.test.tsx` using `CorsRulesTab.test.tsx`'s `vi.mock("@/client/trpcClient", …)` pattern plus `renderHook`: last-rule path calls `lifecycle.delete`; multi-rule path calls `lifecycle.set` with `remaining`; stale rule → `onError` with the stale message and neither mutation fires; validation failure → `onError` with `cannotDeleteMessage`.

---

### Step 8 — Memoize rule-list derivations (finding #10)

**Files:** `.../Buckets/LifecycleRulesTab.tsx`, `.../Buckets/LifecycleRulesTable.tsx`, `LifecycleRulesTab.test.tsx`

**8a (required).** In `LifecycleRulesTab.tsx`:
1. Add a module-level `const EMPTY_RULES: LifecycleRuleRead[] = []` and change line 151 to `const rules = useMemo(() => lifecycleData?.rules ?? EMPTY_RULES, [lifecycleData])` — otherwise the fresh `[]` literal defeats every downstream memo.
2. Fold `sortRules` (159–179) and `rulesWithOriginalIndices` (181–184) and the filter (185–188) into **one** `useMemo` producing `filteredRulesWithIndices`, deps `[rules, lifecycleSortBy, lifecycleSortDirection, lifecycleSearch]`.
3. `const filteredIndices = useMemo(…, [filteredRulesWithIndices])`; `allFilteredSelected` / `someFilteredSelected` in a `useMemo` with deps `[filteredIndices, selectedIndices]`.
4. `useCallback` for `handleEditRule`, `handleToggleSelectRule`, `handleDeleteRule` (empty/stable deps) and `handleToggleSelectAll` (deps `[allFilteredSelected, filteredIndices]`).
5. ⚠️ All the `useMemo`s must sit **above** the `if (isLoading)` / `if (error)` early returns at 196–210 — they already are; keep it that way (Rules of Hooks).

**8b (optional, decide up front).** Row-level bail-out does not exist today. To make 8a's stable callbacks pay off, extract the body of the `rulesWithIndices.map` (135–213) in `LifecycleRulesTable.tsx` into `const LifecycleRuleRow = React.memo(function LifecycleRuleRow({ rule, originalIndex, isSelected, onToggleSelectRule, onEditRule, onOpenDeleteModal, isMutating }) { … })`, passing `isSelected={selectedIndices.includes(originalIndex)}` rather than the whole array.
Safe with Juno: its `DataGrid` computes `gridTemplateColumns` on the grid element and cells consume a React context (verified in `@cloudoperators/juno-ui-components@9.1.0` build output), so an extra component layer between `DataGrid` and `DataGridRow` does not break layout — but confirm visually in dev.

**Expected outcome:** typing in the search box no longer re-sorts and re-derives on every keystroke render; with 8b, unchanged rows skip re-render.

**Verification:** functional — extend `LifecycleRulesTab.test.tsx` with sort/filter/select-all behavior tests (before and after must match). Perf — React DevTools Profiler while typing in the search box: only the toolbar and matching rows should re-render.

---

### Step 9 — Delete the dead server-side `normalizeFilter` (finding #8)

**Files:** `packages/aurora/src/server/Storage/helpers/lifecycleMapper.ts`, `.../lifecycleMapper.test.ts`, `.../Buckets/utils/lifecycleUtils.ts`

**Investigation result (already done — record it in the commit body):** a repo-wide grep confirms the server `normalizeFilter` (lifecycleMapper.ts:28) has **zero** production callers; only `lifecycleMapper.test.ts` imports it. The only runtime caller of either copy is `LifecycleRuleForm.tsx:79` → the client copy.

**What to do:**
1. Delete `normalizeFilter` (lines 15–59) from `lifecycleMapper.ts` and the now-unused `LifecycleTag` type import on line 2. Keep `LifecycleFilter` (still used by `toSdkLifecycleRules`/`toWireLifecycleRule`).
2. Delete `describe("normalizeFilter")` (lines 7–49) from `lifecycleMapper.test.ts` and drop `normalizeFilter` from its import on line 2.
3. Update the JSDoc in `lifecycleUtils.ts` (lines 12–28): remove the "Intentional duplicate of `lifecycleMapper.normalizeFilter` … keep behaviourally identical" claim and the stale cross-reference to `lifecycleMapper.test.ts`'s filter cases. This is now the single implementation.

**Do not** extract a shared isomorphic module. It is not warranted: `packages/aurora/src/types` (the third `./types` entry point) is type-declaration-only, and there is no runtime-sharing convention. Worth knowing for the record: the client *already* value-imports from the server tree in several places (`getServiceIndex` from `@/server/Authentication/helpers`, `FloatingIpQueryParametersSchema` from `@/server/Network/types/floatingIp`), so cross-boundary sharing is not forbidden — but adding a shared module here would be pure overhead for a function with one caller.

**Expected outcome:** ~45 lines of untested-in-production code and a sync-by-comment convention removed.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck && pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/helpers`

---

### Step 10 — Extract a shared rate-limiter factory (finding #6) 🔴 broadest blast radius, do last

**Files:**
- New: `packages/aurora/src/server/Storage/helpers/rateLimiter.ts` + `rateLimiter.test.ts`
- Modify: `.../routers/ceph/lifecycleRouter.ts` (20–51), `.../corsRouter.ts` (8–39), `.../bucketPolicyRouter.ts` (16–47)

**What to do:**
1. Create `rateLimiter.ts`:
   ```ts
   import { TRPCError } from "@trpc/server"
   export function createRateLimiter(options: { windowMs: number; maxCount: number; message: string }): (bucketName: string, projectId: string) => void
   ```
   Body is the existing logic verbatim with `windowMs`/`10`/message text injected, including the `.unref()` and the stale-timer guard (`if (current && current.resetAt <= Date.now())`) with its explanatory comment. The `Map` lives in the closure, so each `createRateLimiter(...)` call gets independent state — same isolation the three module-level Maps have today.
2. Replace each router's inline function and Map with one call, **preserving the message strings byte-for-byte**:
   - `corsRouter.ts`: `{ windowMs: 60 * 1000, maxCount: 10, message: "CORS modification rate limit exceeded. Maximum 10 CORS changes per minute per bucket." }`
   - `bucketPolicyRouter.ts`: `{ windowMs: 5 * 60 * 1000, maxCount: 10, message: "Policy modification rate limit exceeded. Maximum 10 policy changes per 5 minutes per bucket." }`
   - `lifecycleRouter.ts`: `{ windowMs: 60 * 1000, maxCount: 10, message: "Lifecycle modification rate limit exceeded. Maximum 10 lifecycle changes per minute per bucket." }`
   Keep the local const names (`checkCorsSetRateLimit`, `checkPolicySetRateLimit`, `checkLifecycleSetRateLimit`) so the call sites in each `set` handler are unchanged.
3. Remove the now-unused `TRPCError` import from any router that no longer uses it directly — `bucketPolicyRouter.ts` still needs it (`validateResourceARNsMatchBucket`); check `corsRouter.ts` and `lifecycleRouter.ts` and let `pnpm lint` decide.

**Expected outcome:** ~90 duplicated lines → one ~30-line factory; identical runtime behavior and identical error messages.

**Verification (the regression gate — these tests must pass with *no edits*):**
```
pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/routers/ceph/corsRouter.test.ts
pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/routers/ceph/bucketPolicyRouter.test.ts
pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/routers/ceph/lifecycleRouter.test.ts
```
They drive the limiter only through `caller.set(...)` plus `vi.getTimerCount()` (corsRouter 447/484, bucketPolicy 361/403, lifecycle 300/336/364) — no internals are touched, so extraction should be transparent. If any needs editing, stop and re-examine the extraction.

**New `rateLimiter.test.ts`:** allows exactly `maxCount` calls; throws `TRPCError` with `code: "TOO_MANY_REQUESTS"` and the configured message on `maxCount + 1`; different `projectId:bucketName` keys are independent; two limiter instances are independent; with fake timers, the cleanup timer is scheduled and fires after `windowMs` leaving `vi.getTimerCount() === 0`; a stale timer does not delete a newer window for the same key.

---

### Step 11 — Docs, i18n, changeset, full CI

**Files:** `packages/aurora/docs/009_ceph_s3_bff.md`, `.changeset/nice-clouds-start.md`, `packages/aurora/src/locales/{en,de}/messages.po`

1. Update `009_ceph_s3_bff.md`'s lifecycle section (added by this PR): document the new `skippedRuleCount` field on `lifecycle.get`'s response and the read-only degradation behavior; note the Abort+tag-filter constraint alongside the existing rate-limiting note.
2. Amend `.changeset/nice-clouds-start.md`. Its "Additional improvements" bullet already claims the O(1) rate-limiter cleanup — extend it to mention the shared factory, and add bullets for the Abort+tags constraint and the partial-read degradation. Keep it `minor` for `@cobaltcore-dev/aurora`.
3. `pnpm --filter @cobaltcore-dev/aurora check-i18n` and commit regenerated `.po` files (Steps 1, 2, 5 add new `t`/`Trans` strings).
4. Full local CI parity: `pnpm lint && pnpm typecheck && pnpm format:check && pnpm test && pnpm build`.

---

## Testing Plan

**Unit — server**
- [ ] `ceph.test.ts`: Abort + `Filter.Tag` rejected; Abort + `And.Tags` rejected; Abort + prefix-only accepted; `getLifecycleOutputSchema` requires `skippedRuleCount`
- [ ] `lifecycleMapper.test.ts`: `toWireLifecycleRule` singular; string-valued `Date` doesn't throw; existing round-trip tests unchanged
- [ ] `lifecycleRouter.test.ts` `describe("get")`: valid+malformed mix; all-malformed; SDK `Date` → ISO on the real path; `rules: null` still returns `skippedRuleCount: 0`
- [ ] `rateLimiter.test.ts`: full factory behavior (Step 10)
- [ ] `corsRouter.test.ts`, `bucketPolicyRouter.test.ts` rate-limit tests pass **unedited**

**Unit — client**
- [ ] `lifecycleUtils.test.ts`: `parseDaysValue`; `isSameLifecycleRule`; Abort+tags in `validateLifecycleRules`
- [ ] `LifecycleRuleForm.test.tsx`: negative/decimal/zero Days blocked with inline error; valid Days still enables; Date-expiration edit still valid; whitespace-only Prefix → whole-bucket filter; Prefix trimmed on blur
- [ ] `LifecycleRulesTab.test.tsx` (new): skipped-rules warning + disabled actions; sort/filter/select-all unchanged after memoization
- [ ] `useLifecycleRuleDeletion.test.tsx` (new): last-rule → `delete`; partial → `set`; stale → error, no mutation; validation failure → error

**Integration / manual** (dev server against a real RGW, `pnpm dev`)
1. Bucket detail → `?view=lifecycle-rules`. Create a rule with Expiration Days `-5` → Save disabled + inline error. Change to `30` → saves.
2. Enter `"   "` (spaces only) as Prefix with expiration enabled and status Enabled → the whole-bucket warning shows; save; reopen → Scope column reads "All objects".
3. Try to enable Abort with a tag present → checkbox disabled. Craft the same combination via `aws s3api put-bucket-lifecycle-configuration` → the tab still loads, and any Aurora `set` is rejected with the new message.
4. Via aws-cli, add a rule the read schema can't parse (e.g. a `Transitions` entry with no `StorageClass`) → tab lists the valid rules, shows the warning banner, and Create/Edit/Delete are disabled.
5. Delete one rule of several → succeeds. Delete the last one → the whole config is removed (`lifecycle.delete`).
6. Bulk-select and delete two of three rules → succeeds; toast copy and plural forms unchanged.
7. Type in the search box with 50+ rules → no visible lag; Profiler shows only the toolbar + matching rows re-rendering.
8. `set` 11 times in a minute on one bucket → `TOO_MANY_REQUESTS`; smoke-test the CORS and bucket-policy tabs for the same limit (Step 10 regression).

## Acceptance Criteria

- [ ] All 10 findings closed; each in its own commit referencing the finding number
- [ ] Days fields reject non-positive/non-integer input client-side with inline feedback
- [ ] The whole-bucket warning and the submitted filter agree for every Prefix input, including whitespace-only
- [ ] Abort + tag-filter is rejected by `lifecycleRuleSchema` **and** `validateLifecycleRules`, mirroring the EODM refinement
- [ ] A single malformed external rule no longer fails `lifecycle.get`; valid rules are returned with `skippedRuleCount > 0`, the UI warns, and mutations are blocked so the full-replace `set` cannot delete the skipped rule
- [ ] Freshness checks in all three lifecycle modals are order-insensitive for `Filter.And.Tags`, `Transitions`, `NoncurrentVersionTransitions`
- [ ] One `createRateLimiter` factory backs cors, bucketPolicy and lifecycle; all three routers' pre-existing rate-limit tests pass **unmodified**; error messages byte-identical
- [ ] The two lifecycle delete modals share `useLifecycleRuleDeletion`; analytics prefixes, callback shapes and all user-facing copy unchanged; CORS modals untouched (follow-up noted)
- [ ] Server `normalizeFilter` and its tests deleted; the "intentional duplicate" comment in `lifecycleUtils.ts` removed
- [ ] `toWireLifecycleRule(s)` is on the real `get` code path
- [ ] Rule-list derivations in `LifecycleRulesTab.tsx` are memoized; behavior unchanged
- [ ] `pnpm lint`, `pnpm typecheck`, `pnpm format:check`, `pnpm test`, `pnpm build`, `pnpm check-i18n` all pass (scope with `--filter @cobaltcore-dev/aurora` while iterating)

## Open Questions

1. **Prefix trimming (Step 2).** S3 object keys may legitimately begin or end with a space. Step 2 trims and shows the trimmed value on blur. Acceptable, or should the warning instead be relaxed (`!prefixValue` rather than `!prefixValue.trim()`) so a whitespace prefix is saved verbatim and no warning shows?
2. **Blocking mutations on skipped rules (Step 5).** Recommended as required, because `lifecycle.set` is a full replace and dropped rules would be permanently deleted. The heavier alternative — retaining raw unparsed rules and re-sending them verbatim — preserves editability but adds a passthrough path through the whole client flow. Confirm the read-only approach.
3. **Step 8b (memoized row component).** In scope for this PR, or defer? 8a alone delivers the sort/filter savings; 8b is what actually makes row-level bail-out possible, but it restructures `LifecycleRulesTable.tsx`, which currently has no tests.
4. **CORS delete-modal duplication.** Confirm it stays out of scope and becomes a follow-up issue rather than being folded into Step 7.

## Incidental observations (not in the 10 findings, not planned)

- `LifecycleRuleModal.tsx:175` submits via `document.querySelector<HTMLFormElement>("#lifecycle-rule-form")?.requestSubmit()` — a document-global lookup against a hardcoded id. Harmless today (one modal at a time) but a footgun; a ref would be safer.
- `LifecycleRulesTable.tsx` casts through `as unknown as {…}` in five places (lines 143, 149, 162, 188) to feed the `lifecycleUtils` formatters. The formatters' parameter types could be widened to `LifecycleRuleRead["Expiration"]` etc. to delete the casts.
- The KB at `/Users/kirylmishchuk/projects/SAP/DOCS/aurora-dashboard-kb/` is pinned to `d00f84a`, ~27 commits / 2 days behind current `main` — recent enough that this plan's file/line references should still hold, but worth a `git status`/line-number sanity check against the branch before starting implementation.
