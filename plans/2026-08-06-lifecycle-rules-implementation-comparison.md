# Comparison: two implementations of Ceph Lifecycle Rules (Epic #608, Section 13)

**Date:** 2026-08-06
**Scope compared:** Epic [#608](https://github.com/cobaltcore-dev/aurora-dashboard/issues/608), Section 13 — "Lifecycle Rules (P3)": BFF `storage.ceph.lifecycle.{get,set,delete}` + a UI rule list with add/edit/delete.

| | Implementation A — "speckit" | Implementation B — "planner" |
|---|---|---|
| Branch | `kiryl-lifecycle-rules-speckit` | `kiryl-lifecycle-rules-planner` (current) |
| Planning artifacts | `specs/001-bucket-lifecycle-rules/{spec,plan,tasks,data-model,research,quickstart}.md`, `contracts/lifecycle-trpc-contract.md` | `DOCS/plans/2026-07-31-ceph-lifecycle-rules-crud.md` (single living document) |
| Methodology | GitHub spec-kit slash-command workflow (`/speckit-specify` → `/speckit-clarify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`) | Freehand plan doc, iteratively re-verified and updated in place (dated edits, decision log) |
| Base commit | Stale — missing several since-merged `main` features | 2 commits behind `main` (missing the presigned-URL feature) |

Both were reviewed by independently reading and executing the actual code (not just the planning docs) — see the per-branch review sections below for file:line citations.

---

## 1. The methodologies, compared

**Speckit** produced six structured artifacts before writing code: `spec.md` (user stories with priorities, functional requirements, a clarification Q&A session, edge cases, measurable success criteria), `research.md`, `data-model.md`, a tRPC contract doc, `quickstart.md`, and `tasks.md` (a dependency-ordered, per-user-story task breakdown with `[P]`arallel markers and an MVP-first incremental strategy). This is a genuinely rigorous *elicitation* process — the `spec.md` clarification session surfaced five real product questions up front (rule-name uniqueness, multipart-abort scoping, manual reordering, rule-limit UX, day-count bounds) and answered them before any code existed. The task breakdown is a good project-management artifact: it makes parallelizable and independently-demoable slices explicit.

Its weakness is that the artifacts are static snapshots frozen at creation time (2026-08-04) and are never revisited against the sibling CORS branch, `main`'s drift, or the implementation's own emerging discoveries — e.g. `data-model.md`/`contracts/lifecycle-trpc-contract.md` still say the input field is `bucket` while the actual code uses `bucketName`, a small but real planning/code drift that nothing caught. The spec also commits early to a product decision (transitions *are* authored in the UI, `spec.md` FR-006) without the deeper investigation into Ceph/RGW's storage-class-enumeration limits that the other plan did — `research.md` §4 acknowledges the limitation but the resulting design (an env-var-configured class list) is a workaround adopted without weighing the "just don't author it" alternative.

**The planner doc** is a single, continuously-updated markdown file with a visible decision log: it records *when* each open question was resolved and *why*, including reversals (e.g. Open Question 7, the rate-limiter decision, was explicitly flipped from "don't copy" to "adopt" on 2026-08-05 once a second sibling router established the pattern as a convention, not a one-off). It re-verifies its dependency on the CORS branch on a specific date, cataloguing exactly what in that sibling PR is settled vs. still in flux, and instructs the executor to re-diff before opening a PR. This produces less structured process visibility (no user-story slicing, no formal FR numbering) but a much higher-fidelity, continuously-corrected risk model: a 10-row risk table with severity ratings, each with a concrete mitigation, most of which (per the code review below) were actually implemented and tested, not just written down.

**Net assessment:** speckit is the better tool for *requirements elicitation and task decomposition*; the planner-doc approach was the better tool for *risk tracking and staying correct as reality (a sibling branch, `main`) moved under it*. Neither is strictly superior — a combination (speckit's user-story slicing and clarification session, feeding into a planner-style living risk log kept current through implementation) would likely beat either alone.

---

## 2. The scope divergence that matters most: are Transitions authored?

The single biggest design fork between the two implementations, and one neither branch's author seems to have cross-checked against the other:

- **Speckit decided transitions ARE a first-class authored action** (`spec.md` FR-006), and built a real storage-class picker sourced from a `CEPH_LIFECYCLE_STORAGE_CLASSES` deployment env var (`lifecycleRouter.ts`, `getAvailableStorageClasses()`) — an honest, non-fake solution to RGW's inability to enumerate storage classes via the S3 API, correctly disabling the control when the env var is unset.
- **The planner doc decided transitions are read-only, preserve-on-roundtrip, never authored** (`DOCS/plans/2026-07-31-ceph-lifecycle-rules-crud.md`, Open Question 1), reasoning that a storage-class picker would be guesswork against a given deployment and that building real enumeration support would reintroduce the RGW Admin Ops API dependency already ruled out elsewhere in the epic (Section 4, Usage & Quota).

Both are internally coherent, defensible positions — this is a genuine product decision, not a bug in either branch. It needs to be resolved once, deliberately, before either branch ships, because they produce different wire contracts (`transition: {days, storageClass}` as a writable schema field vs. `Transitions` as an opaque passthrough never touched by the schema).

---

## 3. Code-level review findings

### 3a. `kiryl-lifecycle-rules-speckit`

**Strengths**
- Clean, symmetric `toSdkLifecycleRule`/`fromSdkLifecycleRule` mapping, closely mirroring `bucketPolicyRouter`/`versioningRouter` conventions.
- The storage-class-picker workaround for transitions (above) is a genuinely well-reasoned answer to a real backend limitation, not a guess.
- `unsupportedFilter` passthrough mechanism (for `Tag`/`And`/object-size `Filter` fragments) is the right *idea* for FR-013 ("never silently drop unsupported config"), and is partially tested.
- Correct empty-state handling for `NoSuchLifecycleConfiguration` on both `get`/`delete` (checks both `err.name` and `err.Code`).
- Correct "delete last rule → call `lifecycle.delete`, not `set([])`" semantics (S3 rejects an empty `Rules` array).
- 24 test cases across schema/router/UI, all with meaningful, non-generic names.

**Confirmed bugs / gaps**
1. **Data loss**: `Expiration.Date` and `Expiration.ExpiredObjectDeleteMarker` are not modeled anywhere in the schema or mapper (`lifecycleRouter.ts:60` only reads `Expiration?.Days`). A rule authored externally with a date-based (rather than day-count) expiration silently loses that expiration the moment it round-trips through any unrelated edit — this directly contradicts the branch's own `spec.md` SC-003 ("100% of pre-existing lifecycle configurations ... never silently lost"), and is untested.
2. **Filter corruption**: `toSdkLifecycleRule` unconditionally injects `Filter: { ...unsupportedFilter, Prefix: rule.prefix ?? "" }` (`lifecycleRouter.ts:24-27`). A rule whose original `Filter` was a bare `Tag`/`ObjectSizeGreaterThan`/`And` with **no** `Prefix` (a normal, valid S3 shape) gets a synthetic `Prefix: ""` injected alongside it on save, producing an invalid two-predicate `Filter`. Untested.
3. **No rate limiting** on `lifecycle.set` (the closest real precedent, `bucketPolicyRouter`, has one; a `corsRouter` does not actually exist in this repo, contrary to what the planner doc's CORS-reference section assumes for that branch — worth noting the planner doc's CORS citations should be re-verified against reality too).
4. **No server-side rule-ID/name uniqueness check** — client-only, by explicit design choice (`research.md` §3), so any non-UI caller can create duplicates.
5. **No lost-update / concurrency protection** — two concurrent editors silently clobber each other via the blind full-array `PUT`.
6. **No whole-bucket-expiration warning**, and **no versioning-not-enabled warning** for noncurrent-version actions — the latter is explicitly named as required UX in the branch's own `spec.md` Edge Cases section, but `LifecycleRuleFormModal` never queries bucket versioning status at all.
7. New rules default to **Enabled** (less-safe default; an accidental empty-prefix + short expiration rule takes effect immediately with no extra confirmation).
8. Error-code fallback: unmapped codes (`MalformedXML`, rule-limit `InvalidRequest`) fall through to `INTERNAL_SERVER_ERROR` (HTTP 500) rather than `BAD_REQUEST` — message text still reaches the UI, but status semantics are wrong for what are really client-correctable validation failures.
9. No dedicated schema unit-test file (`types/lifecycle.test.ts` doesn't exist); schema behavior is only indirectly exercised via two router-level cases.
10. Minor: unused `ModalType` variants (`editLifecycleRule`/`deleteLifecycleRule`) declared but never referenced.
11. **Branch hygiene**: diff includes unrelated regressions — removal of the already-shipped `generatePresignedUrl` feature and its docs — indicating the branch predates several merged `main` commits and needs a rebase before it's mergeable as-is.

### 3b. `kiryl-lifecycle-rules-planner`

**Strengths**
- Every mitigation in the plan doc's risk table is genuinely implemented and covered by a passing test, not just described: lossless round-trip (including `Transitions`/`NoncurrentVersionTransitions`, verified against a real round-trip test), lost-update guard, whole-bucket-expiration warning, per-bucket rate limiting, midnight-UTC normalization for `Expiration.Date` (real `Date.UTC(y,m,d)` logic, not just a comment), `MalformedXML`/`InvalidArgument` error-code backstop.
- Read/write schema split (`lifecycleRuleReadSchema` vs. the strict write schema) correctly anticipated and avoided the exact validation bug the CORS sibling branch had.
- New rules default to **Disabled** (safer default), with explicit helptext.
- Substantially larger and non-redundant test suite: ~120 lifecycle-specific cases across schema (36), mapper (22), router (29), and UI (33) — all verified to actually pass (`pnpm --filter @cobaltcore-dev/aurora test`/`typecheck` both green). No other bucket-sub-resource feature in this repo (per the plan doc, CORS included) ships UI tests at all; this branch does.
- Concurrency check is a real deep-equality snapshot compare against a freshly-refetched `get`, not a superficial reference check.

**Confirmed bugs / gaps**
1. **Real bug, most significant finding**: `LifecycleRuleForm.tsx` re-attaches preserved object-size filter predicates (`ObjectSizeGreaterThan`/`ObjectSizeLessThan`) via `Object.assign(filter, unsupportedFilterPredicates)` on top of a freshly-`normalizeFilter`'d prefix/tags object. For a rule whose original filter was *only* an object-size predicate (no prefix/tags), or one nested inside `And`, this produces an invalid **two-top-level-predicate** `Filter` (e.g. `{ Prefix: "", ObjectSizeGreaterThan: X }`), which the strict write schema's own `superRefine` then rejects with `BAD_REQUEST` — meaning editing an unrelated field (even just `Status`) on such a rule and saving fails validation. This directly undermines the branch's own stated "never destroys config authored outside Aurora" goal, for exactly the class of externally-authored config it was trying to protect. Not covered by any of the 8 `LifecycleRuleForm.test.tsx` cases.
2. The lost-update/concurrency "reject on mismatch" branch is correctly implemented (`LifecycleModal.tsx::handleSaveConfiguration`) but has **zero test coverage** — none of the 12 `LifecycleModal.test.tsx` cases exercise the "changed since opened" path.
3. **Branch hygiene**: 2 commits behind `main` — diff shows the presigned-URL feature/docs as "removed," which is stale-branch noise, not an intentional deletion, but would revert that feature if merged as-is without a rebase.
4. Minor: `BucketModals.tsx`'s lifecycle `onSuccess`/`onError` wiring calls `onClose()` redundantly (already called inside `LifecycleModal.tsx`'s own `handleClose()`) — harmless, idempotent, but worth a cleanup pass.
5. Entry point is currently 2 header buttons (Policy + Lifecycle), not the plan's aspirational "3rd button" framing, since the sibling CORS branch (PR #1092) hasn't actually merged into this branch's base — expected given the plan's own documented conditional wording, not a defect.

### 3c. Head-to-head on the risks that matter most for a feature that can auto-delete data

| Risk | speckit | planner |
|---|---|---|
| Lossless round-trip of externally-authored config | ❌ Two confirmed data-loss/corruption bugs (Date-based expiration dropped; bare Tag/ObjectSize filter corrupted) | ⚠️ One confirmed corruption bug (object-size filter merge), narrower blast radius (only object-size filters, not Date-expiration) |
| Concurrent-edit protection | ❌ absent | ✅ implemented, untested branch |
| Rate limiting on `set` | ❌ absent | ✅ implemented and tested |
| Whole-bucket-expiration warning | ❌ absent | ✅ implemented and tested |
| Versioning-not-enabled warning (own spec requirement, speckit only) | ❌ absent despite being in its own spec | N/A (not in planner's spec) |
| New-rule default status | Enabled (less safe) | Disabled (safer) |
| Error status-code correctness for backend rejections | ⚠️ falls back to 500 for validation-shaped errors | ✅ correct 400s |
| Test coverage (lifecycle-specific) | ~24 cases | ~120 cases, verified passing |
| Transitions: authored vs. preserved | Authored (real feature, extra surface area) | Read-only preserved (smaller surface area, explicit scope cut) |
| Both need before merge | Rebase onto current `main` | Rebase onto current `main` |

---

## 4. Best-of-both: what a combined/cleaned-up implementation should take from each

**From planner, keep:**
- The dedicated `lifecycleMapper.ts` pure module with independent round-trip tests — this discipline is exactly why planner's Date-normalization and Transitions-preservation logic are actually correct and verified, vs. speckit's inline, untested equivalent logic.
- Rate limiting, lost-update guard, whole-bucket warning, Disabled-by-default — all directly reduce the odds of this feature auto-deleting data by accident, which is the dominant risk of "lifecycle rules" as a feature category.
- The UI test suite structure and volume.

**From speckit, keep:**
- The versioning-not-enabled warning requirement from its own spec (neither branch fully avoids gaps — planner doesn't have this requirement at all; it should be added regardless of which branch ships).
- The `spec.md` clarification-session pattern as a pre-implementation step — worth running against whichever branch is chosen, to settle the transitions-authored-or-not question explicitly rather than by default.
- Consider the storage-class-picker-via-env-var approach as a candidate resolution to the transitions question, if the product actually wants transitions authored — it's a reasonable design, just needs to sit in the mapper module and be tested at the level planner tests its equivalents.

**Both need fixed before merge regardless of which is chosen:**
- Rebase onto current `main` (both branches are stale relative to it in ways that would regress unrelated shipped features).
- The object-size-filter merge bug (planner) / bare-filter-Prefix-injection + Date-expiration-loss bugs (speckit) — these are the kind of silent-data-loss issues the risk tables in both plans explicitly called out as the top concern, and both branches still have a live instance of exactly that category of bug.
- Resolve the transitions-authored-or-not product question explicitly, in writing, rather than letting whichever branch merges first decide it by default.

---

## 5. Recommendation

**Use `kiryl-lifecycle-rules-planner` as the base to carry forward.** It implements more of its own stated risk mitigations correctly and verifiably (rate limiting, concurrency guard, whole-bucket warning, safer default, correct error-status mapping), has ~5x the test volume with no padding, and its one confirmed data-loss-adjacent bug (object-size filter merge) has a narrower blast radius than speckit's two (Date-based expiration is a common real-world pattern; the planner bug requires the more unusual case of object-size-only filters authored outside Aurora). Before opening a PR from this branch:

1. Fix the `LifecycleRuleForm.tsx` object-size-filter merge bug (§3b.1) and add a regression test.
2. Add a test for the concurrency-mismatch save-rejection branch (§3b.2).
3. Port over the versioning-not-enabled warning that speckit's spec correctly identified as required UX but neither branch actually built.
4. Rebase onto current `main`.
5. Get an explicit product decision on transitions (author vs. preserve-only) rather than defaulting to planner's choice by omission — if the decision reverses, speckit's env-var-driven storage-class picker is a reasonable pattern to port in, reimplemented inside `lifecycleMapper.ts` with the same test rigor as planner's other mapper functions.

If minimizing engineering time to close the epic section matters more than the above, speckit's spec.md/tasks.md are still worth keeping as reference documents (the clarification Q&A and edge-case list are genuinely useful and not duplicated in the planner doc) even though its code should not ship as-is without fixing findings 1–2 and 5–7 in §3a.
