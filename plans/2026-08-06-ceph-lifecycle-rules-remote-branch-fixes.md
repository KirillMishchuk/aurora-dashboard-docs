# Fix plan: `kiryl-ceph-lifecycle-rules` (remote-machine branch)

**Date:** 2026-08-06 (updated same day with manual QA findings)
**Status:** implemented 2026-08-07 (Round 2 complete)
**Branch this applies to:** `kiryl-ceph-lifecycle-rules` (built on a remote machine, from the same design doc as the local `kiryl-lifecycle-rules-planner` branch: [`2026-07-31-ceph-lifecycle-rules-crud.md`](./2026-07-31-ceph-lifecycle-rules-crud.md))
**Why this file exists:** the remote machine isn't reachable from this environment (no permissions) — this document is meant to be copied over and handed to a Claude Code session running on that machine to execute directly, without further investigation.

**Verified before writing this list** (not guessed): `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/routers/ceph/lifecycleRouter.test.ts src/server/Storage/types/ceph.test.ts` → 221/221 pass. `pnpm --filter @cobaltcore-dev/aurora typecheck` → clean. `pnpm --filter @cobaltcore-dev/aurora lint` → **fails, 13 errors**. No client-side test files exist for any of the 4 lifecycle UI components (confirmed via `find`, 0 results). Items 3, 5, and 6 below were added after manually clicking through the "Add Lifecycle Rule" popup and confirmed by reading `@cloudoperators/juno-ui-components`'s actual type definitions (not assumed).

---

## Round 2 status (2026-08-07) — verified after commit `1a7f0e4c "first fix"`

The remote machine applied a fix pass (commit `1a7f0e4c`) addressing this list. Re-verified by running the real test/lint/typecheck commands (not by reading diffstats) and by re-reading every changed file.

**Verified:** `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/routers/ceph/lifecycleRouter.test.ts src/server/Storage/types/ceph.test.ts src/server/Storage/helpers/lifecycleMapper.test.ts` → **253/253 pass**. `pnpm --filter @cobaltcore-dev/aurora typecheck` → **clean**. `pnpm --filter @cobaltcore-dev/aurora lint` → **0 errors** (the 13 `no-explicit-any` errors are gone).

| # | Item | Verdict |
|---|---|---|
| 1 | Data loss on edit (drops other action fields) | ✅ FIXED |
| 2 | Transitions authorable in UI | ✅ FIXED |
| 3 | Status `Select` onChange broken | ✅ FIXED |
| 4 | No concurrency guard | ✅ FIXED |
| 5 | Action-type not using Juno components | ✅ FIXED (Checkbox, correct native-event convention) |
| 6 | No tag-filter editor | ⚠️ PARTIAL — editor added, but hand-builds the filter instead of calling `lifecycleMapper.ts`'s `normalizeFilter` |
| 7 | No duplicate rule-ID check | ✅ FIXED |
| 8 | `And` allows <2 predicates | ✅ FIXED |
| 9 | No legacy top-level `Prefix` / no Filter-vs-Prefix exclusion | ⚠️ PARTIAL — schema now has the field + refine, but the **UI doesn't consume it correctly — see new critical items 23/24 below** |
| 10 | `ExpiredObjectDeleteMarker`+tag not rejected | ✅ FIXED |
| 11 | Rule cap 1000 instead of 100 | ✅ FIXED |
| 12 | No pure mapper module / inline date logic | ⚠️ PARTIAL — `lifecycleMapper.ts` + tests created correctly, **but `lifecycleRouter.ts` never imports or calls it** — router still runs its own separate inline copy of the same logic. The module exists unused. |
| 13 | `z.any()` read schema | ✅ FIXED |
| 14 | `pnpm lint` 13 errors | ✅ FIXED (consequence of #13) |
| 15 | New rules default `Enabled` | ✅ FIXED (now `Disabled`) |
| 16 | No whole-bucket warning | ✅ FIXED |
| 17 | Missing `MalformedXML`/`InvalidArgument` | ✅ FIXED |
| 18 | No schema-rejection/round-trip tests in router test | ⚠️ PARTIAL — all 8 requested `BAD_REQUEST`/`MalformedXML` cases added; the round-trip-fidelity case ("editing one rule leaves another rule's `Transitions` byte-identical") is still missing |
| 19 | Zero client-side tests for the 4 UI components | ❌ NOT FIXED — still 0 `.test.tsx` files |
| 20 | Duplicate changesets | ✅ FIXED |
| 21 | No docs section | ❌ NOT FIXED — file untouched |
| 22 | Cosmetic label drift | ❌ NOT FIXED — untouched (low priority, as noted originally) |

**Two new critical bugs were introduced by the fix pass itself** (both in the rewritten `LifecycleRuleForm.tsx`, both stemming from the same root cause: the rewrite only fully models the `Days`+`Filter` happy path, not every rule shape the schema/RGW can actually produce) — see items 23 and 24 below. These are more urgent than any of the partial/not-fixed items above, because they make **existing, previously-valid rules unsavable or corrupting**, which is a regression on the exact "never destroy config authored outside Aurora" guarantee this whole feature exists to provide.

---

## How this branch diverged from the plan

Same plan document, two independent Claude Code sessions (local machine vs. remote machine), materially different code. Three concrete, confirmed causes:

1. **A different `main` base at branch-creation time** — this branch forked from `03cde79a`, one commit later than the local branch's `7d9e6aa0`. Minor, mostly cosmetic drift (unrelated floating-IP files appear in diffs).
2. **The plan's Step 4 was skipped**: no `helpers/lifecycleMapper.ts` module was created. Date/filter conversion ended up inlined directly in `lifecycleRouter.ts`, with no independent unit tests — which is exactly why the critical bug below (#1) went undetected.
3. **Several explicit plan decisions were not carried through** to the implementation: transitions ended up authorable in the UI (the plan says read-only/preserve-only); the rule cap is 1000, not the plan's deliberately-chosen 100; new rules default to `Enabled`, not `Disabled`; and the form doesn't use this repo's Juno UI component conventions for `Select`/`Radio`, which is what caused the Status field to be unusable (see fix #3).

None of this means the remote session did something invalid — the plan didn't force determinism, and where it left room for judgment, this branch made different (mostly weaker) calls. But some of these are outright unimplemented plan requirements, not judgment calls, and some are real, user-facing bugs.

---

## Fix list (apply in this order — later fixes depend on earlier ones)

### 1. [CRITICAL] Editing a rule silently drops fields tied to any action type other than the one currently selected

**File:** `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRuleForm.tsx` (lines 76–116)

**What's wrong:** `onSubmit` builds `newRule` from only `ID`/`Status`/`Filter` plus whichever single `actionType` radio is selected. Every other field the original rule had — `Transitions`, `NoncurrentVersionTransitions`, `NoncurrentVersionExpiration`, `AbortIncompleteMultipartUpload`, or any `Expiration` not matching the selected radio — is discarded. Opening any existing rule for edit and saving (even changing only `Status`) permanently deletes the rest of its configuration. This is the exact risk the plan's mapper design and top risk-table row exist to prevent, and it is live in this branch.

**Fix:** Stop modeling actions as a mutually-exclusive radio group. Let `Expiration`, `NoncurrentVersionExpiration`, and `AbortIncompleteMultipartUpload` be independently toggled — use Juno's `Checkbox` component for each action's on/off toggle (see fix #5 below for why `Checkbox`, not hand-rolled `<input>`, and note its `onChange` signature is a **native event** (`ChangeEventHandler<HTMLInputElement>`, read `e.target.checked`) — the opposite convention from `Select`/`Radio`/`RadioGroup`, which pass the raw value directly (see fix #3). Don't mix these up when rewriting this section. When building `newRule`, start from `...editingRule` and only overwrite the fields the user actually changed — never drop `Transitions`/`NoncurrentVersionTransitions` or unrelated action fields. Add a colocated test: create a rule with `Transitions` set, edit only `Status`, assert `Transitions` is byte-identical in the submitted payload.

### 2. [CRITICAL] Transitions are authorable in the UI — contradicts the plan's explicit scope decision

**File:** `LifecycleRuleForm.tsx` (the "Transition to Storage Class" `ActionType` option, its `Select` of `STORAGE_CLASSES`, and `getInitialActionType`)

**What's wrong:** The plan decided (Open Question 1) that storage-class transitions are **read-only, preserved on round-trip, never authored** — RGW can't enumerate real storage classes via the S3 API, so any picker is guesswork against a specific deployment. This branch built a real transition-authoring control anyway.

**Fix:** Remove the "transition" action entirely from the authoring form (including the `transitionStorageClass` `Select`, which also carries the onChange bug from fix #3 — removing it fixes that instance for free). Render any `Transitions`/`NoncurrentVersionTransitions` already on the rule being edited as a **read-only** summary ("Storage-class transitions are managed outside Aurora and are preserved unchanged"), and make sure they pass through untouched on submit (this falls out of fix #1's `...editingRule` spread).

### 3. [CRITICAL] "Status" `Select` never registers a change — clicking an option does nothing

**File:** `LifecycleRuleForm.tsx` (lines 168-188, `onChange` at 175-179)

**Confirmed by manual QA**: clicking a Status option in the "Add Lifecycle Rule" popup has no visible effect; the field is stuck.

**Root cause, confirmed by reading `@cloudoperators/juno-ui-components`'s type definitions directly** (`node_modules/.../juno-ui-components/build/components/Select/Select.component.d.ts`): Juno's `Select` is **not** a native `<select>` — it's a custom listbox/dropdown component whose `onChange` signature is:
```ts
onChange?: (value?: string | number | string[]) => void
```
It hands the **selected value directly**, never a DOM event. The current code assumes a native-`<select>`-style event:
```tsx
onChange={(e) => {
  if (e && typeof e === "object" && "target" in e) {
    field.handleChange((e.target as HTMLSelectElement).value as "Enabled" | "Disabled")
  }
}}
```
`e` is actually a plain string (`"Enabled"`/`"Disabled"`). `typeof e === "object"` is `false` for a string, so the guard's body never runs and `field.handleChange` is never called — every click is silently swallowed.

**Fix:**
```tsx
onChange={(value) => field.handleChange(value as "Enabled" | "Disabled")}
```
The exact same bug exists a second time on the `transitionStorageClass` `Select` (lines 334-338) — moot once fix #2 removes that field entirely, but if fix #2 is applied first, this second instance disappears on its own.

**Systemic note for whoever fixes this:** this repo's Juno wrapper components are inconsistent on purpose — `Select`, `Radio`, and `RadioGroup` all pass the **raw value** to `onChange`; `Checkbox` passes a **native change event** (`e.target.checked`). Don't assume one convention applies to all of them; check each component's `.d.ts` (or an existing usage elsewhere in the codebase, e.g. `DirectionEthertypeSection.tsx` for `RadioGroup`/`Radio`) before wiring `onChange`.

### 4. [CRITICAL] No concurrency / lost-update guard before saving

**File:** `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleModal.tsx`

**What's wrong:** No snapshot of the rules loaded when the modal opened, and no refetch-and-compare before mutating. Two people (or two tabs) editing the same bucket's lifecycle config concurrently will silently clobber each other, since `set` always replaces the entire configuration.

**Fix:** On first successful load, store an immutable `loadedSnapshot` of `lifecycleData.rules`. In the save handler, refetch `lifecycle.get` first and deep-compare (e.g. `JSON.stringify`) the fresh result against `loadedSnapshot`; on mismatch, show an error message ("The lifecycle configuration changed since you opened this dialog. Close and reopen to reload.") and abort — do not call `set`/`delete`.

### 5. [HIGH] "Action Type" is hand-rolled raw HTML, not this repo's Juno UI components

**File:** `LifecycleRuleForm.tsx` (lines 205-286)

**Confirmed by manual QA and code reading**: the current implementation is bare `<input type="radio">` elements with Tailwind utility classes and manually built `<label>`/description `<div>`s (`className="flex items-start gap-2"`, `className="mt-1"`, etc.) — it doesn't import or use any Juno form component for this section at all, which is why it looks and behaves inconsistently with the rest of the app's forms (and every other Select/TextInput in this same file *does* use Juno).

**What to use instead** — this repo already has a working reference pattern for exactly this in `packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/$securityGroupId/-modals/AddRuleModal/sections/DirectionEthertypeSection.tsx`:
```tsx
import { RadioGroup, Radio } from "@cloudoperators/juno-ui-components"
// ...
<RadioGroup
  name="actionType"
  label={t`Action Type`}
  selected={field.state.value}
  onChange={(value) => field.handleChange(value as ActionType)}
  required
>
  <Radio value="expiration" label={t`Expire Objects`} helptext={t`Delete objects after a certain number of days`} />
  {/* ...one Radio per option, each with its own label + helptext, no manual <div> wrapper needed */}
</RadioGroup>
```
Note `RadioGroup`/`Radio.onChange` also pass the raw value directly (`(value: string) => void`), same convention as `Select` — see fix #3's systemic note.

**However**, per fix #1, action type should stop being a single mutually-exclusive choice at all (a rule commonly needs more than one action simultaneously). So the end state here should be **Juno `Checkbox` per action** (`Expiration`, `NoncurrentVersionExpiration`, `AbortIncompleteMultipartUpload` — not `RadioGroup`/`Radio`, since those are for single-choice, not independent toggles), each revealing its own fields (days, etc.) when checked. Do fix #1 and this fix together as one redesign of the action section, not as two separate passes — apply fix #1's "spread + toggle" logic using Juno `Checkbox` components as the toggle UI, and drop the current radio markup entirely (there's no scenario where the final version keeps `RadioGroup` for this specific field, since it's being turned into an independent-toggle section).

### 6. [MEDIUM] No tag-based filter authoring — only a `Prefix` text input exists

**File:** `LifecycleRuleForm.tsx` (filter section, lines 190-203)

**Confirmed by manual QA**: opening the Add/Edit Rule form shows only a "Prefix Filter" text input; there is no way to add a key/value tag as a filter condition, even though the schema (`lifecycleFilterSchema` in `ceph.ts`) supports `Filter.Tag` and `Filter.And.Tags`, and the plan requires it.

**Fix:** Add a tag key/value row editor below the Prefix field, modeled on the existing pattern in `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/EditMetadataModal.tsx` (add-row / remove-row key+value inputs, local `tags: LifecycleTag[]` state, "Add" button disabled until a key is entered). On submit, feed `prefix`+`tags` into the same filter-normalization logic used elsewhere (see fix #9 below — once `lifecycleMapper.ts`/`normalizeFilter` exists, call it here rather than hand-building `Filter` inline): no tags + prefix → `{ Prefix }`; one tag, no prefix → `{ Tag }`; prefix+tags or 2+ tags → `{ And: { Prefix?, Tags } }`; nothing → whole-bucket `{ Prefix: "" }`.

### 7. [HIGH] No duplicate rule-ID validation

**File:** `packages/aurora/src/server/Storage/types/ceph.ts`, `lifecycleConfigurationSchema` (~line 713)

**Fix:** Add a `superRefine` that collects non-empty `ID`s across `Rules` and raises an issue if any repeat. Add matching tests in `ceph.test.ts` (schema rejects duplicate IDs) and `lifecycleRouter.test.ts` (`set` returns `BAD_REQUEST` for duplicate IDs).

### 8. [HIGH] `And` filter accepts fewer than 2 predicates

**File:** `ceph.ts`, filter schema (~lines 603–643)

**What's wrong:** A single-tag (or single-anything) `And` block currently validates, even though S3's `And` combinator only makes sense for ≥2 predicates.

**Fix:** In the filter refine, count predicates inside `And` (`Prefix` present + `Tags.length` + `ObjectSizeGreaterThan` present + `ObjectSizeLessThan` present) and reject totals below 2. Add test cases (accept 2+ combos, reject a lone tag inside `And`).

### 9. [HIGH] No legacy top-level `Prefix` field, so `Filter`-vs-`Prefix` exclusion can't exist

**File:** `ceph.ts`, `lifecycleRuleSchema` (~lines 659–669)

**What's wrong:** RGW can return v1-style rules with a bare top-level `Prefix` instead of `Filter.Prefix`. This schema has no such field at all, so those legacy rules have no valid representation, and the plan's "reject Filter + top-level Prefix together" check can't be written.

**Fix:** Add `Prefix: z.string().optional()` to `lifecycleRuleSchema`; add a `superRefine` rejecting both `Filter` and `Prefix` set simultaneously; make sure the SDK-write path (see fix #12) never emits both at once (migrate legacy `Prefix` into `Filter.Prefix` on write, never both).

### 10. [HIGH] `ExpiredObjectDeleteMarker` + tag filter isn't rejected client-side

**File:** `ceph.ts`, `lifecycleRuleSchema`

**What's wrong:** S3/RGW rejects `Expiration.ExpiredObjectDeleteMarker: true` combined with a tag-based filter, but with an opaque `MalformedXML`— nothing catches this before the request leaves the BFF.

**Fix:** Add a `superRefine`: if `Expiration?.ExpiredObjectDeleteMarker` is true and (`Filter?.Tag` or `Filter?.And?.Tags?.length`) is set, raise a field-level validation error. Add tests for both the rejection and the still-valid prefix-only + `ExpiredObjectDeleteMarker` combination.

### 11. [HIGH] Rule-count cap is 1000, not the plan's deliberately-chosen 100

**File:** `ceph.ts:717`

**What's wrong:** `.max(1000, ...)` uses RGW's real technical ceiling. The plan explicitly caps at 100 (Open Question 5) as a *UI-sanity* limit for a manual, add-one-at-a-time rule editor — not a claim about the real backend limit, which stays enforced server-side regardless.

**Fix:** Change to `.max(100, "Maximum 100 lifecycle rules per bucket")`. Update the corresponding `ceph.test.ts` case (currently asserts rejection only above 1000 — change the fixture size and expected message to match 100).

### 12. [HIGH] Date/filter conversion is inlined with no UTC-midnight normalization, and no pure/tested mapper module exists

**Files:** `packages/aurora/src/server/Storage/routers/ceph/lifecycleRouter.ts` (~lines 141–155); new file `packages/aurora/src/server/Storage/helpers/lifecycleMapper.ts` (+ `.test.ts`)

**What's wrong:** `set` does `new Date(rule.Expiration.Date)` directly with no midnight-UTC normalization (AWS requires `Expiration.Date` to land on midnight UTC). All conversion logic lives inline in the router instead of an independently-tested pure module — this is precisely why bug #1 shipped undetected: there was never a place to write a round-trip unit test.

**Fix:** Create `helpers/lifecycleMapper.ts` per the plan's Step 4: `toWireLifecycleRules` (SDK → wire, `Date` → ISO string), `toSdkLifecycleRules` (wire → SDK, including a `toMidnightUTC` helper: `new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()))`, applied only to `Expiration.Date`, never to `Transitions[].Date`), and `normalizeFilter` (used by both the router and fix #6's tag editor). Move the router's inline conversion to call these functions. Add `lifecycleMapper.test.ts`: each filter-normalization branch, Date round-trip at midnight UTC, transitions preserved verbatim, and a full-fixture `toWire(toSdk(x)) === x` round-trip.

### 13. [HIGH] `lifecycleRuleReadSchema` uses `z.any()` everywhere, forcing `any`-casts in the UI and failing lint

**File:** `ceph.ts` (~lines 695–704)

**What's wrong:** `Filter`, `Expiration`, `Transitions`, `NoncurrentVersionExpiration`, `NoncurrentVersionTransitions`, `AbortIncompleteMultipartUpload` are all typed `z.any()`. Direct, confirmed consequence: `LifecycleRuleForm.tsx` (5 sites) and `LifecycleRulesViewer.tsx` (8 sites) cast to `any` to read these fields — which is also why `pnpm --filter @cobaltcore-dev/aurora lint` currently fails with 13 `@typescript-eslint/no-explicit-any` errors.

**Fix:** Replace each `z.any()` with a structured-but-lenient sub-schema (typed fields, loose/optional constraints — not full write-time strictness, but not `unknown` either). Then remove the `any` casts in both UI files and re-run lint to confirm it's clean. This directly resolves fix #14 below as well.

### 14. [HIGH] `pnpm --filter @cobaltcore-dev/aurora lint` currently fails (13 errors) — blocks merge as-is

**Files:** `LifecycleRuleForm.tsx` (5 sites), `LifecycleRulesViewer.tsx` (8 sites)

**Fix:** Falls out of fix #13 — once the read schema is properly typed, remove the `any` casts and type these locals against the real field types. Re-run `pnpm --filter @cobaltcore-dev/aurora lint` to confirm zero errors before proceeding.

### 15. [MEDIUM] New rules default to `Enabled` instead of `Disabled`

**File:** `LifecycleRuleForm.tsx` (initial-values default)

**Fix:** Default `Status` to `"Disabled"`. This is a deliberate safety choice in the plan — a misconfigured whole-bucket expiration rule that's Enabled by default can delete an entire bucket the moment it's saved. (Note: this default was previously untestable in practice because of fix #3 — the Status select couldn't be changed at all, so every rule saved so far was stuck at whatever the default was.)

### 16. [MEDIUM] No whole-bucket-expiration warning anywhere in the UI

**Files:** `LifecycleModal.tsx`, `LifecycleRulesViewer.tsx`

**Fix:** Add a helper (`isWholeBucketExpirationRule(rule)`): true when `Status === "Enabled"`, the filter matches everything (no `Prefix`/`Tag`/`And`, or an empty `Prefix`), and a current-version `Expiration` is set. Render a warning message per matching rule in the rule list, and/or an aggregate warning above the modal content.

### 17. [MEDIUM] Missing `MalformedXML`/`InvalidArgument` entries in the S3 error map

**File:** `packages/aurora/src/server/Storage/helpers/s3ErrorMapper.ts`

**Fix:** Add `MalformedXML: "BAD_REQUEST"` and `InvalidArgument: "BAD_REQUEST"` to `S3_ERROR_MAP` (check first whether a sibling router already added `MalformedXML` — skip re-adding if so). `NoSuchLifecycleConfiguration` is already present and correct.

### 18. [MEDIUM] `lifecycleRouter.test.ts` has no schema-rejection or round-trip-fidelity cases

**File:** `packages/aurora/src/server/Storage/routers/ceph/lifecycleRouter.test.ts`

**What's wrong:** The existing 17 cases cover happy paths and rate limiting only.

**Fix:** Add `BAD_REQUEST` cases for: empty `Rules`, zero-action rule, `Days`+`Date` together, duplicate IDs, `Filter`+`Prefix` together, `ID`>255, `And` with 1 predicate, `ExpiredObjectDeleteMarker`+tag filter. Add a `MalformedXML`-mapping case. Add a round-trip case: edit one rule in a multi-rule config, assert the *other*, untouched rule (including any `Transitions`) reaches `send()` byte-identical to what `get` returned.

### 19. [MEDIUM] Zero client-side tests exist for any of the 4 lifecycle UI components

**Missing files:** `.../Ceph/Buckets/LifecycleModal.test.tsx`, `LifecycleRuleForm.test.tsx`, `LifecycleRulesViewer.test.tsx`, `DeleteLifecycleModal.test.tsx`

**Fix:** Add all four, using the mocking harness pattern from `BucketPolicyModal.test.tsx` (mock `useProjectId`, `useRouteContext`, `trpcReact.storage.ceph.lifecycle.*`). Prioritize two cases that would have caught the bugs found manually: "a rule carrying `Transitions` survives an unrelated edit unchanged" (fix #1) and "selecting a Status option updates the field's value" (fix #3 — a test using RTL's `userEvent` against the rendered `Select` would have caught the broken `onChange` immediately, since reading-the-code review alone initially missed it).

### 20. [LOW] Two duplicate changesets describing the same feature

**Files:** `.changeset/nice-clouds-start.md`, `.changeset/proud-pumpkins-smile.md`

**Fix:** Keep one, delete the other (or merge). Whichever is kept, remove any claim about authoring storage-class transitions from its text once fix #2 removes that capability.

### 21. [LOW] No "Lifecycle Configuration" section in the BFF docs

**File:** `packages/aurora/docs/009_ceph_s3_bff.md`

**Fix:** Add a section documenting the three procedures, the wire schema, the transitions-preserve-not-author decision, and the async-processing caveat (RGW evaluates lifecycle rules on its own schedule, not immediately after save).

### 22. [LOW] Cosmetic label drift from the plan

**File:** `BucketHeaderActions.tsx`

**What's wrong:** Buttons read "Edit/View Lifecycle"/"Add Lifecycle"; the plan (and the "Delete Lifecycle Rules" wording already used elsewhere in the same menu) says "Edit/View Lifecycle Rules"/"Add Lifecycle Rules".

**Fix:** Optional, cosmetic only — align if consistency matters for the PR.

### 23. [CRITICAL — NEW, introduced by the "first fix" commit] Editing any rule when the bucket has a legacy top-level-`Prefix` rule makes the whole save fail

**File:** `LifecycleRuleForm.tsx` — `getInitialValues` and the submit handler's `Filter`-building block

**What's wrong:** Item 9's schema fix (§9 above) correctly added `Prefix?: string` to `lifecycleRuleSchema` plus a refine rejecting `Filter` and `Prefix` set together. But the form was never updated to match:
- `getInitialValues` reads prefix/tags **only from `editingRule.Filter`** — it never looks at `editingRule.Prefix` (the legacy field) at all.
- On submit, `newRule` is built by spreading `{ ...editingRule }` first (which carries the original `Prefix` forward untouched if it was set) and then **unconditionally** setting `newRule.Filter` from the form's prefix/tag state.
- Net result: a rule that originally had legacy top-level `Prefix` (e.g. authored via `aws-cli` years ago, never touched by Aurora) ends up with **both** `Prefix` and `Filter` set the moment *any* rule in that bucket's config is saved — not just the legacy rule itself. Since `set` always sends the *entire* `Rules` array, this one bad rule blocks saving the whole configuration with `BAD_REQUEST` from the new refine.
- Secondary symptom: `LifecycleRulesViewer.tsx`'s `RuleCard` also only reads `Filter`, never `Prefix`, so such a rule is mis-displayed as "All objects" (scope-blind) even before this save-blocking issue surfaces.

**Fix:**
1. In `getInitialValues`, fall back to `editingRule.Prefix` when `editingRule.Filter` is absent (i.e., treat legacy top-level `Prefix` as equivalent to `Filter.Prefix` for display/edit purposes — this matches the plan's original intent that legacy `Prefix` migrates into `Filter.Prefix` "only when the user edits that rule").
2. On submit, when building `newRule`, explicitly clear the legacy `Prefix` field (`newRule.Prefix = undefined`) whenever `newRule.Filter` is being set, so the two are never both present — the migration should be one-directional (legacy → `Filter`), never both.
3. Update `LifecycleRulesViewer.tsx`'s `RuleCard` to fall back to `rule.Prefix` when `rule.Filter` is absent, so legacy-scoped rules display their actual scope instead of "All objects".
4. Add a regression test: a rule with only legacy `Prefix` set, opened for edit (of an unrelated field or the same rule), submits with `Filter.Prefix` set and `Prefix` cleared — never both.

### 24. [CRITICAL — NEW, introduced by the "first fix" commit] Rules using `Expiration.Date` or `Expiration.ExpiredObjectDeleteMarker` become permanently unsavable once opened for edit

**File:** `LifecycleRuleForm.tsx` — `getInitialValues`'s expiration population and `canSubmit()`

**What's wrong:** `getInitialValues` only populates `expirationDays` from `Expiration.Days`. If the rule's `Expiration` actually uses `Date` or `ExpiredObjectDeleteMarker` instead (both valid per the plan's own schema — `lifecycleExpirationSchema` requires exactly one of the three, not specifically `Days`), the "has expiration" checkbox correctly shows as checked, but `expirationDays` stays `""`. `canSubmit()` then requires `expirationDaysValue.length > 0` whenever the expiration checkbox is on — so the Save button is **permanently disabled** the instant such a rule is opened, even if the user only wants to flip `Status` or edit an unrelated field. There is also no way to *author* `Date`/`ExpiredObjectDeleteMarker` in this form at all (only `Days` — a narrower gap than a bug on its own, but it's what makes the disabled-Save state a dead end rather than something the user can work around in the UI).

**Fix:**
1. Either (preferred, matches the plan's original scope): keep authoring limited to `Days`, but make the form **tolerate** a rule whose `Expiration` uses `Date`/`ExpiredObjectDeleteMarker` by preserving that sub-object untouched (like `Transitions` are already preserved per fix #1/#2) when the user hasn't touched the Expiration checkbox — i.e., don't force `expirationDays` to be populated/required for a rule that didn't use days in the first place; only require `expirationDays` when the user is defining a *new* days-based expiration (checkbox freshly checked with no pre-existing non-Days expiration).
2. Or (larger scope, only if product wants full authoring): add `Date` and `ExpiredObjectDeleteMarker` as alternate expiration modes in the form (radio/select under the Expiration checkbox), matching what the schema already accepts.
3. Whichever direction is chosen, add a regression test: a rule with `Expiration.ExpiredObjectDeleteMarker: true` (no `Days`), opened for edit and saved after only changing `Status`, submits successfully with the original expiration mode intact.

**Note:** fixes 23 and 24 share the same root cause — `LifecycleRuleForm.tsx`'s rewrite for fix #1 only fully modeled the `Days`+`Filter` happy path. Before considering the form "fixed," explicitly test it against every rule shape the schema allows: `Days`-expiration, `Date`-expiration, `ExpiredObjectDeleteMarker`-expiration, `Filter`-scoped, legacy-`Prefix`-scoped, and a rule carrying `Transitions`. A single property-style test fixture covering all these combinations (open for edit → change one unrelated field → submit → assert nothing else changed) would have caught both of these before this "first fix" commit shipped, and would catch any next-round regression too.

---

## What's already correct in this branch (don't touch)

- `get` null/empty semantics on `NoSuchLifecycleConfiguration` (checks both `err.name` and `err.Code`).
- Rate limiting on `set` (`checkLifecycleSetRateLimit`, per-bucket+per-project keyed, 10/min, tested).
- Empty-array semantics (deleting the last rule calls `delete`, not `set([])`).
- Entry-point UI wiring (header button, badge, `useBucketInfo.ts` integration) — functionally correct.
- No permission keys added (correctly matches the plan's explicit "skip for now" decision).
- Exactly-one-of `Days`/`Date`/`ExpiredObjectDeleteMarker`, zero-action rejection, and `ID` ≤255 validation all already work correctly.
- `Prefix` `TextInput` and the other plain `TextInput`/`Select`-for-storage-class fields in the form use Juno components correctly in isolation — the problems are specifically the `Select` `onChange` wiring (fix #3) and the hand-rolled radio section (fix #5), not Juno usage in general.

## Suggested execution order

**This is Round 2.** Items 1–5, 7, 8, 10, 11, 13–17, 20 from the original list are already done (see the Round 2 status table above) — do not redo them, just don't regress them.

**Do these next, in this order:**

1. **Items 23 and 24 first** — both are live, critical regressions from the "first fix" pass: they make existing valid rules unsavable or corrupt the saved config the moment *any* rule in the bucket is touched. Fix them together as one pass over `LifecycleRuleForm.tsx` (and `LifecycleRulesViewer.tsx`'s display fallback for item 23), per the note at the end of item 24 — test against every rule shape the schema allows, not just the one that was broken.
2. **Item 12** — wire `lifecycleRouter.ts`'s `get`/`set` to actually call `lifecycleMapper.ts`'s `toWireLifecycleRules`/`toSdkLifecycleRules` instead of running its own parallel inline logic. Low risk, high value: removes a duplicate-logic drift hazard and makes the mapper's tests actually mean something for production behavior.
3. **Item 6** — once #12 is done, make the tag editor call `normalizeFilter` from the mapper instead of hand-building the filter object.
4. **Item 19** — add the four missing `.test.tsx` files. Prioritize a case that would have caught items 23/24: open a rule for edit with each of (legacy `Prefix`, `Date`-expiration, `ExpiredObjectDeleteMarker`-expiration, `Transitions` present), change one unrelated field, save, assert the rest of the rule is unchanged.
5. **Item 18** — add the missing round-trip-fidelity case to `lifecycleRouter.test.ts`.
6. **Items 21, 22** — docs section and label wording, whenever convenient before the PR.

After applying, re-run: `pnpm --filter @cobaltcore-dev/aurora typecheck && pnpm --filter @cobaltcore-dev/aurora lint && pnpm --filter @cobaltcore-dev/aurora test` and confirm all three pass clean, then manually re-test the Add/Edit Lifecycle Rule popup — specifically including opening a *legacy-`Prefix`* rule and a *`Date`/`ExpiredObjectDeleteMarker`-expiration* rule for edit, not just a freshly-created one — before opening a PR.
