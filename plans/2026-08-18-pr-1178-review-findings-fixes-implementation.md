# Plan: Fix PR #1178 review findings (15 confirmed) — implementation

**Date:** 2026-08-18 · **Status:** implemented 2026-08-18

## Overview

Implement all 15 confirmed findings from the completed triage at `../DOCS/plans/2026-08-18-pr-1178-review-findings-fixes.md` against PR #1178 ("feat(aurora): add Ceph S3 bucket lifecycle configuration management"). The work spans two design-doc corrections, four server changes (Zod refinements, mapper typing, rate-limiter cleanup), eight client changes (validation mirrors, modal guards, form preservation, a11y labels, index derivation, i18n), and one test-determinism fix. Finding **5b is explicitly REJECTED** and must NOT be implemented — it stays documented as "not fixed, by design."

## Architecture Analysis

**Current state (verified on disk, 2026-08-18):**

- 🔴 **PR #1178's code is NOT in the working tree.** `kiryl-ceph-lifecycle-rules` (verified via `git ls-remote`). Its merge-base with `main` is `0bfd055c` (PR #1172), so the PR **already contains** the current `CorsRulesTable.tsx`, `corsRouter.ts`, `bucketPolicyRouter.ts` that findings #7/#13 widen into. The PR branch is exactly **1 commit behind main** (`d00f84a2`, Swift TempURL — no file overlap, no conflict risk).
- Server domain code: `packages/aurora/src/server/Storage/` split into `routers/ceph/`, `types/ceph.ts` (Zod), `helpers/lifecycleMapper.ts`. Procedures built from `cephProtectedProcedure`.
- Client: TanStack Query + tRPC utils; `-components/Ceph/Buckets/` holds the modals/tables; validation mirrored client-side in `utils/lifecycleUtils.ts`.
- Tests colocated as `*.test.ts(x)`, vitest, **`environment: "jsdom"` for every test in `packages/aurora`, server tests included** (`packages/aurora/vitest.config.ts`).
- CI (`.github/workflows/ci-checks.yaml`) runs: `licenses:check`, `lint`, `check-i18n`, `typecheck`, `format:check`, `test`, `build`. **There is no markdownlint job** — the triage doc's "markdownlint-cli2 (as run by CI)" verification step for finding #2 does not exist locally; markdownlint only runs inside CodeRabbit's review. Adjusted in the Testing Plan below.
- Prettier covers `**/*.{js,jsx,ts,tsx,md}` — the design doc edits (#1/#2) are format-checked.

**Proposed changes:**

Fix in dependency order — server schema/type changes first, then the client logic that mirrors them, then pure-client and doc/test changes, then a single i18n regeneration pass at the end (three findings alter Lingui message ids).

## Potential Problems & Mitigations

| Risk                                                                                                                                                                                                                                           | Severity               | Mitigation                                                                                                                                                                                                                                                                                                                                                                    |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| 🔴 PR code absent from `kirylDev` — implementer edits non-existent files                                                                                                                                                                       | High                   | Prerequisite step 0: check out the PR branch first. Every path below only exists after checkout.                                                                                                                                                                                                                                                                              |
| ⚠️ #12: `toWireLifecycleRules(sdkRules)` is fed `toSdkLifecycleRules(...)` output in `lifecycleMapper.test.ts:137-138,163-164`. Changing only `toSdkLifecycleRules`'s return type to the AWS SDK's `LifecycleRule` **breaks `pnpm typecheck`** | High                   | Change **both** signatures in the same step: `toWireLifecycleRules(sdkRules: AwsSdkLifecycleRule[]): LifecycleRuleRead[]`. Its body already handles `Date` objects.                                                                                                                                                                                                           |
| ⚠️ #12: SDK types are stricter than our Zod types — `Transition.StorageClass?: TransitionStorageClass` (string-literal union) vs our `z.string()`; `LifecycleRule.Status: ExpirationStatus \| undefined`                                       | Medium                 | `StorageClass` needs `as TransitionStorageClass` (import the type from `@aws-sdk/client-s3`); `Status` needs no cast (`ExpirationStatus` = `"Enabled" \| "Disabled"`, exactly our enum). Verified in `@aws-sdk/client-s3@3.1100.0` `dist-types/models/models_0.d.ts:6998` / `enums.d.ts:539,555`.                                                                             |
| ⚠️ #13: `setTimeout(...).unref()` in server code executed under vitest's **jsdom** environment                                                                                                                                                 | Medium — **de-risked** | Probed empirically in this repo: under vitest jsdom, `setTimeout` returns a Node `Timeout` **object** with a `unref` function, and `tsc --noEmit` accepts `.unref()` with the current tsconfig. Also verified under `vi.useFakeTimers()`: the faked handle still exposes `unref`, `vi.getTimerCount()` reports 1 → 0 across `advanceTimersByTime`. No defensive guard needed. |
| ⚠️ #5a: removing the add-branch's use of `currentRules` leaves `const currentRules = ...` (LifecycleRuleModal.tsx:104) unused → `@typescript-eslint/no-unused-vars` lint failure                                                               | Medium                 | Delete line 104 as part of the same edit.                                                                                                                                                                                                                                                                                                                                     |
| #6/#7/#15 change Lingui message ids (`After {0} days` → `After {abortDays} days`; `Select rule {originalIndex}` → `Select rule {ruleLabel}`; removal of `"30"`/`"7"`/`"90"`)                                                                   | Medium                 | One dedicated step runs `pnpm check-i18n` and commits regenerated `en                                                                                                                                                                                                                                                                                                         | de/messages.po`+`messages.ts`. Verified both German entries are currently **empty** (`msgstr ""`) — no translation work is lost. |
| #7/#13 widen the diff into 3 files owned by main (`CorsRulesTable.tsx`, `corsRouter.ts`, `bucketPolicyRouter.ts`)                                                                                                                              | Medium                 | Isolate them in their own commits (see Open Questions); before pushing, confirm no other in-flight PR is touching them.                                                                                                                                                                                                                                                       |
| #9/#10 client validation may start blocking edits on buckets containing externally-authored malformed rules                                                                                                                                    | Low                    | Intended: the server already rejects these; the client now names the offending rule instead of showing a generic mutation error.                                                                                                                                                                                                                                              |
| #11 loosens an over-strict check                                                                                                                                                                                                               | Low                    | All 7 existing `lifecycleFilterSchema`/And tests (`ceph.test.ts:1355-1425`) were re-checked against the new formula — every pass/fail verdict is unchanged; only the previously-untested "2+ tags alone" case flips to `true`.                                                                                                                                                |
| No test file exists for `LifecycleRulesTable.tsx` / `LifecycleRulesTab.tsx` (confirmed absent from the PR diff)                                                                                                                                | Low                    | #7/#14 verified by typecheck + manual DOM check; adding suites is optional scope (see Open Questions).                                                                                                                                                                                                                                                                        |

## Prerequisites

- [ ] **Stated assumption (case (b) applies):** PR #1178 is **open and unmerged**; its code is reachable only via the local branch `pr-1178-review` (= origin `kiryl-ceph-lifecycle-rules` @ `75bec562`). The implementer must work **on the PR branch**, not on `kirylDev`.
- [ ] Check out and refresh the branch from the repo root:
  ```bash
  cd /Users/kirylmishchuk/projects/SAP/aurora-dashboard
  git checkout -b kiryl-ceph-lifecycle-rules pr-1178-review   # local name matching origin, so plain `git push` works
  git merge main                                              # picks up d00f84a2; no overlapping files, expect a clean merge
  pnpm install
  ```
- [ ] Capture a green baseline **before** any edit (so later failures are attributable):
  ```bash
  pnpm --filter @cobaltcore-dev/aurora typecheck
  pnpm --filter @cobaltcore-dev/aurora test
  ```
- [ ] Read the triage doc once end-to-end; keep it open — every code snippet below is quoted from it and is treated as verified ground truth.
- [ ] Confirm no other in-flight PR is touching `CorsRulesTable.tsx`, `corsRouter.ts`, `bucketPolicyRouter.ts` (needed for #7/#13).

**Node note:** the local Node is `v24.5.0` while `engines` wants `>=24.15.0` — pnpm prints an "Unsupported engine" warning on every command. It is non-fatal (typecheck/tests pass), but bump via `nvm use` if convenient.

---

## Implementation Steps

### Step 1 — Fix the design doc (#1 + #2)

**File:** `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/docs/009_ceph_s3_bff.md`

All line numbers below are verified against `pr-1178-review`. Do the edits **bottom-up** so earlier line numbers stay valid.

**What to do:**

1. **(#1)** In the `#### delete` block (~lines 2399-2420), replace the `**Output:**` fenced block body `{\n  success: boolean\n}` with the single line `boolean`. Match the existing convention used by `cors.delete` at lines 1640-1653. Leave the `**Example:**` block untouched.
2. **(#2.4)** Delete the re-inserted duplicate heading `### Problem: \`All input parsers did not resolve to an object\` when wiring an upload`at **line 2443** plus its trailing blank line, so the`**Cause:**` body at ~2445 reattaches to the original heading at line 2240.
3. **(#2.3)** Delete the spurious duplicate block at **lines 2431-2441**: `## Error Handling` → `### S3 Error Mapper` → intro sentence → `#### Mapped Error Codes` → the 1-row `NoSuchBucket` table (the complete 20-row version already lives at line 1693+). Also remove the now-dangling `---` separator that preceded it at ~line 2429.
4. **(#2.1 + #2.2)** Cut lines **2242-2429** — the whole `### Lifecycle Configuration (\`storage.ceph.lifecycle\`)`section (from its heading through the end of the`#### delete`example, i.e. everything up to but excluding the`---`before the spurious`## Error Handling`) — and paste it into `## Available Procedures`, immediately **before** line 1693 (`## Error Handling`), i.e. right after the `### CORS Testing Notes`section ends at line 1691, preserving the`---` separator convention used between sibling sections.

**Expected outcome:** exactly one `## Error Handling` and one `### Problem: All input parsers...` heading; `### Lifecycle Configuration` sits as a `###` sibling of `### CORS Configuration` under `## Available Procedures`; `lifecycle.delete`'s documented output is `boolean`.

**Verification:**

```bash
grep -n "^## \|^### " packages/aurora/docs/009_ceph_s3_bff.md | grep -c "^.*## Error Handling"   # → 1
grep -n "### Problem: \`All input parsers" packages/aurora/docs/009_ceph_s3_bff.md               # → 1 hit
pnpm --filter @cobaltcore-dev/aurora exec prettier --check docs/009_ceph_s3_bff.md
```

Manually re-read the Troubleshooting section end-to-end: heading → Cause → Solution → `## References`. Confirm no code fence lost its closing ` ``` `.

---

### Step 2 — Server Zod refinements: And-predicate counting (#11) + ExpiredObjectDeleteMarker exclusivity (#10, server half)

**File:** `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/types/ceph.ts`

**What to do:**

1. **(#11)** In `lifecycleFilterAndSchema` (lines 871-894), replace the boolean-array `predicateCount` with per-tag counting:
   ```ts
   const predicateCount =
     (val.Prefix !== undefined && val.Prefix !== "" ? 1 : 0) +
     (val.Tags?.length ?? 0) +
     (val.ObjectSizeGreaterThan !== undefined ? 1 : 0) +
     (val.ObjectSizeLessThan !== undefined ? 1 : 0)
   return predicateCount >= 2
   ```
   Update the adjacent comment (`// Count predicates inside And`) to state that each tag counts individually.
2. **(#10 server)** Append a third `.refine` to `lifecycleExpirationSchema` (currently ends at line 796):
   ```ts
   .refine(
     (val) => !(val.ExpiredObjectDeleteMarker !== undefined && (val.Days !== undefined || val.Date !== undefined)),
     "ExpiredObjectDeleteMarker cannot be combined with Days or Date"
   )
   ```
   Also extend the JSDoc above the schema (lines 776-782) — it already claims "Only ONE of the following can be set per rule", which the code now actually enforces.

**File (tests):** `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/types/ceph.test.ts`

3. In `describe("lifecycleExpirationSchema")` (starts line 1204), after `it("should reject both Days and Date")` (line ~1225), add:
   ```ts
   it("should reject Days with ExpiredObjectDeleteMarker", () => {
     expect(
       lifecycleExpirationSchema.safeParse({
         Days: 30,
         ExpiredObjectDeleteMarker: true,
       }).success
     ).toBe(false)
   })
   it("should reject Date with ExpiredObjectDeleteMarker", () => {
     expect(
       lifecycleExpirationSchema.safeParse({
         Date: "2024-12-31T00:00:00.000Z",
         ExpiredObjectDeleteMarker: true,
       }).success
     ).toBe(false)
   })
   ```
4. In the `lifecycleFilterSchema` describe block, next to `it("should reject And with only 1 predicate")` (line ~1392), add:
   ```ts
   it("should accept And with 2+ tags and nothing else", () => {
     const input = {
       And: {
         Tags: [
           { Key: "Type", Value: "Archive" },
           { Key: "Team", Value: "Platform" },
         ],
       },
     }
     expect(lifecycleFilterSchema.safeParse(input).success).toBe(true)
   })
   ```

**Expected outcome:** `{ And: { Tags: [t1, t2] } }` is accepted; `{ Days, ExpiredObjectDeleteMarker }` and `{ Date, ExpiredObjectDeleteMarker }` are rejected.

**Verification:**

```bash
pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/types/ceph.test.ts
```

All pre-existing And/filter tests (including `"should reject And with empty Tags array"` and `"should reject And with only 1 predicate"`) must still pass unchanged.

---

### Step 3 — Client validation mirrors: filter-structure checks (#9) + ExpiredObjectDeleteMarker (#10, client half)

> ⚠️ Must land in the **same pass/commit as Step 2** — the per-tag counting below is only correct against Step 2's fixed server logic.

**File:** `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/utils/lifecycleUtils.ts`

**What to do:**

1. In `validateLifecycleRules` (starts line 128), inside the `for` loop (`ruleLabel` is already defined at line 147), insert after the existing "ExpiredObjectDeleteMarker cannot be combined with tag-based filters" block (lines 184-191):

   ```ts
   // ExpiredObjectDeleteMarker is a distinct action — mirrors lifecycleExpirationSchema (server)
   if (
     rule.Expiration?.ExpiredObjectDeleteMarker === true &&
     (rule.Expiration.Days !== undefined || rule.Expiration.Date !== undefined)
   ) {
     errors.push(
       `${ruleLabel}: ExpiredObjectDeleteMarker cannot be combined with Days or Date`
     )
   }

   // And filter must have ≥2 predicates — per-tag counting, mirrors lifecycleFilterAndSchema (server)
   if (rule.Filter?.And) {
     const predicateCount =
       (rule.Filter.And.Prefix !== undefined && rule.Filter.And.Prefix !== ""
         ? 1
         : 0) +
       (rule.Filter.And.Tags?.length ?? 0) +
       (rule.Filter.And.ObjectSizeGreaterThan !== undefined ? 1 : 0) +
       (rule.Filter.And.ObjectSizeLessThan !== undefined ? 1 : 0)
     if (predicateCount < 2) {
       errors.push(
         `${ruleLabel}: And filter must contain at least 2 predicates`
       )
     }
   }

   // Top-level conditions must not combine with each other or with And — mirrors lifecycleFilterSchema (server)
   if (rule.Filter) {
     const topLevelConditions = [
       rule.Filter.Prefix !== undefined,
       rule.Filter.Tag !== undefined,
       rule.Filter.ObjectSizeGreaterThan !== undefined,
       rule.Filter.ObjectSizeLessThan !== undefined,
     ].filter(Boolean).length
     if (
       topLevelConditions > 1 ||
       (rule.Filter.And && topLevelConditions > 0)
     ) {
       errors.push(
         `${ruleLabel}: Multiple filter conditions (Prefix, Tag, ObjectSize) must be wrapped in an And clause`
       )
     }
   }
   ```

   Types are fine: `lifecycleRuleReadSchema`'s `Filter` is a structured (`.passthrough()`) object with typed `And.Tags`, so no casts are needed.

2. Update the function's JSDoc validation-rules list (lines 113-123) with the three new checks.

**File (tests):** `.../utils/lifecycleUtils.test.ts`, inside `describe("validateLifecycleRules")` (line 115), after `it("should reject Transition with both Days and Date")` (line 244):

3. Add four cases:
   - `{ Filter: { And: { Prefix: "x" } } }` → rejected with `/And filter must contain at least 2 predicates/`.
   - `{ Filter: { And: { Tags: [t1, t2] } } }` → **accepted** (locks in the #11 alignment).
   - `{ Filter: { Prefix: "logs/", Tag: { Key: "env", Value: "prod" } } }` → rejected with `/must be wrapped in an And clause/`.
   - `{ Expiration: { Days: 30, ExpiredObjectDeleteMarker: true } }` → rejected with `/ExpiredObjectDeleteMarker cannot be combined with Days or Date/`.
     Each rule needs a valid `Status` and at least one action so the assertion targets the intended message.

**Expected outcome:** the client rejects the same filter/expiration shapes the server rejects, with a rule-labelled inline message.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets/utils/lifecycleUtils.test.ts`

---

### Step 4 — Type `toSdkLifecycleRules` against the AWS SDK shape (#12)

**Files:**

- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/helpers/lifecycleMapper.ts`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/lifecycleRouter.ts`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/helpers/lifecycleMapper.test.ts`

**What to do:**

1. In `lifecycleMapper.ts`, add:
   ```ts
   import type {
     LifecycleRule as AwsSdkLifecycleRule,
     TransitionStorageClass,
   } from "@aws-sdk/client-s3"
   ```
2. Change `toSdkLifecycleRules` (line 71) to `(wireRules: LifecycleRuleRead[]): AwsSdkLifecycleRule[]` and build the object directly as `AwsSdkLifecycleRule` — delete `const result: any`, the `eslint-disable @typescript-eslint/no-explicit-any`, and the trailing `return result as LifecycleRule`. Notes from the SDK type check:
   - `Status` needs no cast — SDK's `ExpirationStatus` is exactly `"Enabled" | "Disabled"`.
   - `Transitions[].StorageClass` and `NoncurrentVersionTransitions[].StorageClass` are `TransitionStorageClass` unions while our Zod type is `z.string()` → cast at those two assignments: `StorageClass: t.StorageClass as TransitionStorageClass`.
   - `Filter` maps onto SDK `LifecycleRuleFilter`; keep the existing `rule.Filter as LifecycleFilter | undefined` only if typecheck demands it — prefer no cast, add a narrowly-scoped one if the structural check fails.
3. Change `toWireLifecycleRules` (line 140) to accept `AwsSdkLifecycleRule[]` (**required** — `lifecycleMapper.test.ts:137-138,163-164` pipe `toSdkLifecycleRules`'s output straight into it, so leaving the old param type breaks `typecheck`). Its body already branches on `typeof date === "string"`; simplify to a plain `.toISOString()` where the SDK type guarantees `Date`, and drop the now-unneeded `as Date` casts and `any`.
4. In `lifecycleRouter.ts` `set` (lines 149-161), replace `const transformed: any = { ...rule }` (and its eslint-disable) with a typed `const transformed: AwsSdkLifecycleRule = { ...rule }`; keep the legacy-`Prefix` → `Filter.Prefix` migration and the `delete transformed.Prefix` behaviour identical. Then drop the `as BucketLifecycleConfiguration` cast at line 171 if typecheck allows (`BucketLifecycleConfiguration.Rules` is the same SDK `LifecycleRule[]`); if it still complains, keep the cast and leave a one-line comment saying why.
5. In `lifecycleMapper.test.ts`: simplify the now-dead defensive branches `typeof expiration.Date === "string" ? new Date(...) : ...` (lines 65-67 and the equivalent for transitions at ~95-97), and drop the `// eslint-disable-next-line @typescript-eslint/no-explicit-any` + `as any` in the `"should convert Date objects to ISO strings"` test (~line 173) by typing its fixture as `AwsSdkLifecycleRule[]`. Behaviour assertions stay identical.

**Expected outcome:** no `any` in the mapper or in `lifecycleRouter.set`; the declared return type matches the runtime shape.

**Verification:**

```bash
pnpm --filter @cobaltcore-dev/aurora typecheck
pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/helpers/lifecycleMapper.test.ts src/server/Storage/routers/ceph/lifecycleRouter.test.ts
```

---

### Step 5 — O(1) rate-limiter cleanup in all three ceph routers (#13)

**Files (all in `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/`):**

- `lifecycleRouter.ts` — `lifecycleSetRateLimits` / `checkLifecycleSetRateLimit`, lines 19-49 (in PR diff)
- `corsRouter.ts` — `corsSetRateLimits` / `checkCorsSetRateLimit`, lines 8-38 (pre-existing, outside PR diff)
- `bucketPolicyRouter.ts` — `policySetRateLimits` / `checkPolicySetRateLimit`, lines 15-45 (pre-existing, outside PR diff)

**What to do (identical transform per file):**

1. Delete the `for (const [k, v] of <map>.entries())` sweep and its "Clean up expired entries…" comment.
2. In the new-window branch, schedule a self-cleaning timer:
   ```ts
   if (!limit || now > limit.resetAt) {
     <map>.set(key, { count: 1, resetAt: now + windowMs })
     // Self-clean this one key after its window closes — O(1) per key, no full-map scan.
     setTimeout(() => {
       const current = <map>.get(key)
       // Only delete if this timer's entry is still the current one (a newer window may have
       // started for the same key before this stale timer fired).
       if (current && current.resetAt <= Date.now()) {
         <map>.delete(key)
       }
     }, windowMs).unref()
     return
   }
   ```
3. Leave everything else byte-identical: each file keeps its own `windowMs` (60 s for lifecycle/CORS, 5 min for policy), its `count >= 10` threshold, and its own `TRPCError` message.

`.unref()` was verified safe here: under this repo's vitest jsdom environment `setTimeout` returns a Node `Timeout` object exposing `unref`, and `tsc --noEmit` accepts the call with the current `packages/aurora/tsconfig.json`.

**File (test):** `lifecycleRouter.test.ts`, in the `set` describe next to the existing rate-limit tests (lines 300-360):

4. Add a fake-timer test proving the cleanup timer is scheduled **and fires without a subsequent call**:
   ```ts
   it("schedules per-key cleanup that fires when the window closes", async () => {
     vi.useFakeTimers()
     try {
       mockSend.mockResolvedValue({})
       const bucket = "rate-limit-cleanup-bucket-unique"
       await caller.set({
         project_id: TEST_PROJECT_ID,
         bucketName: bucket,
         lifecycleConfiguration: {
           Rules: [{ Status: "Enabled", Expiration: { Days: 30 } }],
         },
       })
       expect(vi.getTimerCount()).toBeGreaterThan(0) // cleanup timer scheduled
       vi.advanceTimersByTime(60 * 1000)
       expect(vi.getTimerCount()).toBe(0) // fired, nothing left pending
     } finally {
       vi.useRealTimers()
     }
   })
   ```
   Use a bucket name unique to this test — the rate-limit `Map` is module-level and shared across the file. The `Map` itself is module-private, so the timer lifecycle is the observable proxy; do **not** export the map just to assert on it.
5. `corsRouter.test.ts` and `bucketPolicyRouter.test.ts` currently have **no** rate-limit tests (verified). Adding equivalents is optional; if skipped, note it in the PR description.

**Expected outcome:** no full-map sweep on any `set`; external 429 behaviour, thresholds, and messages unchanged.

**Verification:**

```bash
pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/routers/ceph/
```

All existing rate-limit tests (`"should enforce rate limiting (10 changes per minute per bucket)"`, `"…different buckets have separate limits"`) must pass untouched.

---

### Step 6 — Remove `indexOf` reference lookup from `LifecycleRulesTab` (#14)

**File:** `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRulesTab.tsx` (lines 154-184)

**What to do:**

1. Add above `sortRules`:
   ```tsx
   interface RuleWithOriginalIndex {
     rule: LifecycleRuleRead
     originalIndex: number
   }
   ```
   (`LifecycleRuleRead` is already imported at line 35.)
2. Change `sortRules` to operate on `RuleWithOriginalIndex[]`, reading `a.rule.ID` / `a.rule.Status` / `a.rule.Expiration?.Days` — same three `switch` cases, same `lifecycleSortDirection` handling. Rename the parameter to `items` to stop shadowing the outer `rules`.
3. Replace lines 178-184 with:
   ```tsx
   const rulesWithOriginalIndices = rules.map((rule, originalIndex) => ({
     rule,
     originalIndex,
   }))
   const filteredRulesWithIndices = sortRules(rulesWithOriginalIndices).filter(
     ({ rule }) => {
       if (!lifecycleSearch) return true
       return (rule.ID || "")
         .toLowerCase()
         .includes(lifecycleSearch.toLowerCase())
     }
   )
   ```
   `rules.indexOf(rule)` disappears entirely. `filteredIndices` (line 187) and the `<LifecycleRulesTable rulesWithIndices={filteredRulesWithIndices} />` prop (line 299) need no changes — the shape `{ rule, originalIndex }` is preserved and already matches `LifecycleRulesTable`'s `LifecycleRuleWithIndex` prop type.

**Expected outcome:** identical ordering/filtering output; `originalIndex` correct by construction; `sortRules` has exactly one call site (verified).

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck`; manual — sort by ID/Status/Expiration in both directions, search, then edit and delete a row and confirm the correct rule is targeted.

---

### Step 7 — Table a11y labels + Lingui member-expression (#6, #7)

**Files:**

- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRulesTable.tsx` (lines 167-182)
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/CorsRulesTable.tsx` (line 140) — **outside PR #1178's diff**, from PR #1172

**What to do:**

1. **(#6, LifecycleRulesTable only)** Replace lines 167-169 with:
   ```tsx
   const abortDays = rule.AbortIncompleteMultipartUpload?.DaysAfterInitiation
   const abortText = abortDays !== undefined ? t`After ${abortDays} days` : "–"
   ```
2. **(#7, both files)** Inside the row-render callback, before the `<Checkbox>`, add:
   ```tsx
   const ruleLabel = rule.ID || String(originalIndex + 1)
   ```
   and change the checkbox to `` aria-label={t`Select rule ${ruleLabel}`} ``.
   In `CorsRulesTable.tsx` the local is already `rule` / `originalIndex` (line 128 destructure), so the same two lines apply verbatim.
   **Leave `` data-testid={`select-rule-${originalIndex}`} `` 0-based in both files** — it is a DOM-query contract, not user-facing.

**Expected outcome:** a screen reader announces the same identifier for a row in the table and in its delete modal (`rule.ID`, else 1-based position), consistently across the Lifecycle and CORS tables.

**Verification:**

```bash
git grep -n "Select rule" packages/aurora/src/client   # both files → `Select rule ${ruleLabel}`
pnpm --filter @cobaltcore-dev/aurora lint              # lingui/no-expression-in-message warning for LifecycleRulesTable:168 gone
```

No test file references the literal "Select rule 0"/`select-rule-N` strings (verified across the whole client tree), so no test updates are needed.

---

### Step 8 — `LifecycleRuleForm`: preserve `NewerNoncurrentVersions` (#4) + drop numeric `t` placeholders (#15)

**File:** `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRuleForm.tsx`

**What to do:**

1. **(#4)** In `onSubmit`, replace the `NoncurrentVersionExpiration` rebuild (lines 116-120) with:
   ```tsx
   if (value.hasNoncurrentExpiration && value.noncurrentDays) {
     newRule.NoncurrentVersionExpiration = {
       NoncurrentDays: parseInt(value.noncurrentDays, 10),
       ...(editingRule?.NoncurrentVersionExpiration?.NewerNoncurrentVersions !==
         undefined && {
         NewerNoncurrentVersions:
           editingRule.NoncurrentVersionExpiration.NewerNoncurrentVersions,
       }),
     }
   }
   ```
   Follows the same preserve-on-edit pattern already used for `Transitions` (lines 111-113) and `NoncurrentVersionTransitions` (lines 122-124). Do **not** add UI to set the field — explicitly out of scope.
2. **(#15)** Replace the three numeric macro placeholders with plain literals: line 373 `placeholder="30"`, line 415 `placeholder="90"`, line 453 `placeholder="7"`. Leave the prose placeholders at lines 226 (`my-lifecycle-rule`) and 268 (`logs/`) wrapped in `t`.

**File (test):** `LifecycleRuleForm.test.tsx`

3. Copy the template at `describe("Item 1: Transitions preservation")` → `test("preserves Transitions when editing unrelated field")` (lines 199-219). Add a fixture rule with `NoncurrentVersionExpiration: { NoncurrentDays: 30, NewerNoncurrentVersions: 3 }`, render with `editingRule`, change only `Status` to Disabled, submit, then assert:
   ```tsx
   expect(
     submittedRule.NoncurrentVersionExpiration.NewerNoncurrentVersions
   ).toBe(3)
   expect(submittedRule.NoncurrentVersionExpiration.NoncurrentDays).toBe(30)
   expect(submittedRule.Status).toBe("Disabled")
   ```

**Expected outcome:** editing an unrelated field no longer strips `NewerNoncurrentVersions` (which `LifecycleRulesTable` visibly renders as "keep N versions"); the three number inputs still show 30/90/7 but leave the translation pipeline.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/client/.../LifecycleRuleForm.test.tsx`

---

### Step 9 — Dismissal guards in both delete modals (#3a + #3b)

**Files:**

- `.../Ceph/Buckets/DeleteLifecycleRuleModal.tsx` (`<Modal>` at lines 172-179)
- `.../Ceph/Buckets/DeleteLifecycleRulesModal.tsx` (`<Modal>` at lines 191-202)

**What to do:**

1. **(#3a)** In `DeleteLifecycleRuleModal.tsx`, add below the existing `disableConfirmButton` (line 178):
   ```tsx
   disableCancelButton={isMutating || isVerifying}
   disableCloseButton={isMutating || isVerifying}
   ```
   `isMutating` (line 87) and `isVerifying` (line 39) already exist. Do not touch `disableConfirmButton`'s condition.
2. **(#3b)** Add to **both** modals:
   ```tsx
   closeOnEsc={!(isMutating || isVerifying)}
   ```
   Do **not** use `closeable={false}` — it hides the X entirely, diverging from the `disableCloseButton` greyed-out convention already used by the bulk modal. Precedent for the `closeOnEsc` prop: `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/-components/Images/-components/CreateImageModal.tsx:367-368`.

**Expected outcome:** while verify/mutate is in flight, Cancel, X, and ESC are all inert in both modals.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck`; manual — throttle the network in devtools, trigger delete, then try Cancel / X / ESC; all three must do nothing until the mutation settles.

---

### Step 10 — Refetch before appending a new rule (#5a)

**File:** `.../Ceph/Buckets/LifecycleRuleModal.tsx`, `handleSubmit` (lines 99-135)

**What to do:**

1. Delete line 104 (`const currentRules = lifecycleData?.rules ?? []`) — it becomes unused and would fail `no-unused-vars`.
2. Replace the add branch (lines 106-109) with:
   ```tsx
   if (editingIndex === null) {
     // lifecycle.set is a full replace, not an append — rebase on fresh server state
     // so a concurrent writer's rule isn't silently overwritten.
     const freshData = await utils.storage.ceph.lifecycle.get.fetch({
       project_id: projectId,
       bucketName,
     })
     updatedRules = [...(freshData?.rules ?? []), rule]
   } else {
     // unchanged — existing freshness check
   }
   ```
   Remove the now-false comment "Adding new rule - no freshness check needed (appending is safe)". `utils` (line 39) and `projectId` (line 38) are already in scope. Do **not** add a `JSON.stringify` equality check in the add branch — appending to fresh state is intended to succeed, not to fail on concurrent modification.
3. **Do NOT implement finding 5b** (server-side revision token / conditional write). It is REJECTED: `GetBucketLifecycleConfigurationOutput` has no ETag/revision and `PutBucketLifecycleConfigurationRequest` has no `IfMatch` in `@aws-sdk/client-s3@3.1100.0`. If it helps future readers, add a short code comment near the freshness check noting that S3/RGW offers no conditional-write primitive for bucket lifecycle, so this is best-effort by design.

**Test:** add a case to a `LifecycleRuleModal` test (create `LifecycleRuleModal.test.tsx` if none exists — the PR ships no test for this file) that mocks `utils.storage.ceph.lifecycle.get.fetch` to resolve rules **different** from the `useQuery` cache, submits a new rule, and asserts the `set` mutation payload contains both the freshly fetched rule and the new one.

**Verification:** unit test above; manual — with the bucket open in tab A, add a rule via `aws-cli` or tab B, then add a different rule from tab A's modal without refreshing; both rules must survive.

---

### Step 11 — Make date-formatting tests TZ/locale independent (#8)

**File:** `.../Ceph/Buckets/utils/lifecycleUtils.test.ts` (lines 398-401 and 418-421)

**What to do:**

1. Replace `it("should format Date from string")`:
   ```tsx
   it("should format Date from string", () => {
     const inputDate = "2026-12-31T00:00:00.000Z"
     const expected = `On ${new Date(inputDate).toLocaleDateString()}`
     expect(formatExpiration({ Date: inputDate })).toBe(expected)
   })
   ```
2. Replace `it("should format transition with Date")`:
   ```tsx
   it("should format transition with Date", () => {
     const inputDate = "2026-12-31T00:00:00.000Z"
     const expectedDate = new Date(inputDate).toLocaleDateString()
     const result = formatTransitions([
       { Date: inputDate, StorageClass: "GLACIER" },
     ])
     expect(result).toBe(`GLACIER after ${expectedDate}`)
   })
   ```
   Test-only change; `lifecycleUtils.ts:312,331` (`toLocaleDateString()` with no args) stays as is.

**Per-step verification (the doc calls this out explicitly):**

```bash
# Before the fix — must FAIL (US-behind timezone shifts the calendar day):
TZ="America/New_York" pnpm --filter @cobaltcore-dev/aurora test src/client/.../lifecycleUtils.test.ts
# After the fix — must PASS in both:
TZ="America/New_York" pnpm --filter @cobaltcore-dev/aurora test src/client/.../lifecycleUtils.test.ts
pnpm --filter @cobaltcore-dev/aurora test src/client/.../lifecycleUtils.test.ts
```

---

### Step 12 — Regenerate i18n catalogs

Run **after** Steps 7, 8 (message ids changed by #6, #7, #15):

```bash
pnpm check-i18n     # lingui extract --clean && lingui compile --typescript --verbose
```

**Expected diff in `packages/aurora/src/locales/{en,de}/messages.po` (+ generated `messages.ts`):**

- removed: `msgid "30"`, `msgid "7"`, `msgid "90"` (en:214-224)
- `msgid "After {0} days"` (en:353, with its `#. placeholder {0}: rule.AbortIncompleteMultipartUpload.DaysAfterInitiation` comment) → `msgid "After {abortDays} days"`
- `msgid "Select rule {originalIndex}"` (en:3228) → `msgid "Select rule {ruleLabel}"`, still shared by both tables

All four German entries are currently empty (`msgstr ""`), so **no translation is lost** — no manual carry-over needed. Commit the regenerated `.po` and `.ts` files.

**Verification:**

```bash
grep -n 'msgid "30"\|msgid "7"\|msgid "90"\|Select rule {originalIndex}\|After {0} days' packages/aurora/src/locales/en/messages.po packages/aurora/src/locales/de/messages.po   # → no hits
```

---

### Step 13 — Changeset, formatting, and full gate

1. Extend the PR's existing changeset `.changeset/nice-clouds-start.md` (currently `"@cobaltcore-dev/aurora": minor`) with a sentence covering the shipped-code fixes that reach beyond the new feature — the And-filter multi-tag acceptance (#11), the CORS-table aria-label (#7), and the rate-limiter cleanup in the CORS/policy routers (#13). If the out-of-diff work is split into its own PR (see Open Questions), give that PR its own `patch` changeset instead.
2. `pnpm format` then `pnpm format:check`.
3. Run the full local CI gate (below).

---

## Testing Plan

**Unit tests to add:**

- [ ] `ceph.test.ts` — reject `{ Days: 30, ExpiredObjectDeleteMarker: true }` (#10)
- [ ] `ceph.test.ts` — reject `{ Date: "…", ExpiredObjectDeleteMarker: true }` (#10)
- [ ] `ceph.test.ts` — accept `{ And: { Tags: [t1, t2] } }` (#11)
- [ ] `lifecycleUtils.test.ts` — reject `And` with 1 predicate; accept `And` with 2 tags; reject two top-level conditions without `And`; reject `ExpiredObjectDeleteMarker` + `Days` (#9, #10)
- [ ] `LifecycleRuleForm.test.tsx` — `NewerNoncurrentVersions` survives an unrelated `Status` edit (#4)
- [ ] `lifecycleRouter.test.ts` — per-key cleanup timer is scheduled and fires under fake timers (#13)
- [ ] `LifecycleRuleModal` test — add-path submits rules rebased on the refetched configuration (#5a)
- [ ] `lifecycleUtils.test.ts` — the two date assertions rewritten TZ-independently (#8)

**Tests that must keep passing unchanged (regression watch):**

- [ ] All 7 existing `lifecycleFilterSchema`/And cases in `ceph.test.ts:1355-1425` (#11 must not flip any)
- [ ] Both existing rate-limit tests in `lifecycleRouter.test.ts:300-360` (#13)
- [ ] `lifecycleMapper.test.ts` round-trip tests (#12 signature change)
- [ ] `BucketDetailTabs.test.tsx`, `CorsRulesTable.test.tsx`, `corsRouter.test.ts`, `bucketPolicyRouter.test.ts` (#7/#13 widened scope)

**Manual verification:**

1. **#11 (highest user impact):** create a lifecycle rule with **two tags and no prefix** → Save must now succeed (previously rejected with "And filter must contain at least 2 predicates").
2. **#3:** open both delete modals, confirm, and while in flight click Cancel, click X, press ESC → all inert.
3. **#4:** seed a rule with `NewerNoncurrentVersions` via `aws-cli`, edit only `Status` in Aurora, save, refresh → table still shows "keep N versions".
4. **#5a:** two tabs / `aws-cli` concurrent-add scenario → both rules survive.
5. **#7:** inspect the checkbox `aria-label` in both the Lifecycle and CORS tables → matches the delete-modal title for the same row (rule ID, else 1-based).
6. **#14:** sort + search + edit/delete a row → the correct rule is targeted.
7. **#15:** the three number inputs still display 30 / 90 / 7.
8. **#2:** read `009_ceph_s3_bff.md` Available Procedures and Troubleshooting sections end-to-end.

**Full gate (matches CI job-for-job):**

```bash
pnpm --filter @cobaltcore-dev/aurora typecheck
pnpm --filter @cobaltcore-dev/aurora lint
pnpm --filter @cobaltcore-dev/aurora test
pnpm check-i18n
pnpm format:check
pnpm build
pnpm licenses:check
TZ="America/New_York" pnpm --filter @cobaltcore-dev/aurora test   # #8 cross-check
```

## Acceptance Criteria

- [ ] All 15 confirmed findings implemented: #1, #2, #3a, #3b, #4, #5a, #6, #7 (both files), #8, #9, #10 (server + client), #11, #12, #13 (all three routers), #14, #15
- [ ] **#5b is NOT implemented**; the rejection stands, optionally captured as a code comment near the client freshness check
- [ ] `009_ceph_s3_bff.md` has exactly one `## Error Handling` and one `### Problem: All input parsers…`, with `### Lifecycle Configuration` under `## Available Procedures`, and `lifecycle.delete` documented as returning `boolean`
- [ ] `{ And: { Tags: [t1, t2] } }` is accepted server-side and client-side; `{ Days|Date } + ExpiredObjectDeleteMarker` is rejected on both sides with matching messages
- [ ] No `any` remains in `lifecycleMapper.ts` or in `lifecycleRouter.set`
- [ ] No `for…of` map sweep remains in any of the three `check*SetRateLimit` functions; 429 thresholds/messages unchanged
- [ ] `rules.indexOf(rule)` no longer appears in `LifecycleRulesTab.tsx`
- [ ] `msgid "30"` / `"7"` / `"90"` / `"Select rule {originalIndex}"` / `"After {0} days"` are gone from both catalogs; regenerated `.po`/`.ts` committed
- [ ] Date-formatting tests pass under `TZ=America/New_York` and under the default TZ
- [ ] No regressions in existing features
- [ ] `pnpm typecheck`, `pnpm lint`, `pnpm test`, `pnpm check-i18n`, `pnpm format:check`, `pnpm build` all pass (scoped with `--filter @cobaltcore-dev/aurora` where possible)

## Open Questions

The planning agent could not use `AskUserQuestion` (unavailable in that subagent), so these decisions are **stated assumptions** — confirm before implementing/pushing:

1. **Branch/PR target — assumed:** work on the PR branch (`git checkout -b kiryl-ceph-lifecycle-rules pr-1178-review && git merge main`) and push to update the open PR #1178. Alternative, if isolated review of the fix pass is preferred: a separate branch off `pr-1178-review` with a second PR targeting it.
2. **Packaging of the out-of-diff files** (`CorsRulesTable.tsx` from #7; `corsRouter.ts`, `bucketPolicyRouter.ts` from #13) — **assumed:** land them inside PR #1178 but in their **own clearly-labelled commits** (e.g. `fix(aurora): align CORS rules table checkbox label with delete modal`, `perf(aurora): replace O(n) rate-limit sweep with per-key cleanup`) so they can be cherry-picked or split out on request. Alternative: a standalone `fix(aurora)` PR off `main` with its own `patch` changeset.
3. **Changeset wording/bump** for the shipped-code fixes (#7, #11, #13) — currently assumed folded into the PR's existing `minor` changeset.
4. **Optional scope, not planned:** adding UI to _set_ `NewerNoncurrentVersions` (#4 covers preservation only); adding `LifecycleRulesTable.test.tsx` / `LifecycleRulesTab.test.tsx` (none exist, so #7/#14 rely on typecheck + manual QA); adding rate-limit tests to `corsRouter.test.ts` / `bucketPolicyRouter.test.ts` (none exist today).

---

### Key files (absolute paths)

**Triage source:** `/../DOCS/plans/2026-08-18-pr-1178-review-findings-fixes.md`

**Server:** `/aurora-dashboard/packages/aurora/src/server/Storage/types/ceph.ts` · `.../types/ceph.test.ts` · `.../helpers/lifecycleMapper.ts` · `.../helpers/lifecycleMapper.test.ts` · `.../routers/ceph/lifecycleRouter.ts` · `.../routers/ceph/lifecycleRouter.test.ts` · `.../routers/ceph/corsRouter.ts` · `.../routers/ceph/bucketPolicyRouter.ts`

**Client** (all under `/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/`): `LifecycleRulesTab.tsx` · `LifecycleRulesTable.tsx` · `LifecycleRuleForm.tsx` · `LifecycleRuleForm.test.tsx` · `LifecycleRuleModal.tsx` · `DeleteLifecycleRuleModal.tsx` · `DeleteLifecycleRulesModal.tsx` · `CorsRulesTable.tsx` · `utils/lifecycleUtils.ts` · `utils/lifecycleUtils.test.ts`

**Docs/i18n/changeset:** `aurora-dashboard/packages/aurora/docs/009_ceph_s3_bff.md` · `/aurora-dashboard/packages/aurora/src/locales/{en,de}/messages.po` · `/aurora-dashboard/.changeset/nice-clouds-start.md`
</content>
