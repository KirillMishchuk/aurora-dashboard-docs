# PR #1207 Code Review — Ceph Lifecycle Rules Management & Permission Controls

Repo: `cobaltcore-dev/aurora-dashboard`
Head SHA: `7edcce6754996071bed6f09f7789aa08a0ce78e4`
Reviewed: 2026-08-26
Posted to PR: https://github.com/cobaltcore-dev/aurora-dashboard/pull/1207#issuecomment-5424819707

Generated via the `code-review` plugin skill (5 parallel Sonnet reviewers — CLAUDE.md compliance, shallow bug scan, git-history context, prior-PR-comment carryover, code-comment compliance — followed by independent Haiku confidence scoring of every candidate finding; only findings scoring ≥80/100 were posted).

## Findings posted (2)

1. **Editing a lifecycle rule silently drops its object-size filter** (confidence 100/100)
   `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRuleForm.tsx:40-58`
   `getInitialValues()` only extracts `Prefix`/`Tag` from `editingRule.Filter` — never `ObjectSizeGreaterThan`/`ObjectSizeLessThan`, even though `normalizeFilter`'s own docblock (`utils/lifecycleUtils.ts:21`) says single-condition filters should include `ObjectSize*`. On submit (`LifecycleRuleForm.tsx:82`), `normalizeFilter(prefix, tags)` rebuilds the filter from only those two args — its signature has no size parameters at all.
   *Failure:* Editing any externally-authored (AWS CLI/console) rule that has a size-based filter and saving it through this UI silently removes the size restriction, widening what objects the rule expires/transitions.
   *Origin:* independently raised by the prior-PR-comment-history reviewer (carried over from unresolved CodeRabbit feedback on sibling PR #1178) and cross-verified fresh against PR #1207's current head.

2. **"Create Lifecycle Rule" can silently delete rules that failed to load** (confidence 100/100)
   `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRulesTab.tsx:233-241` (button gate) + `LifecycleRuleModal.tsx:104-114` (add path)
   `mutationsBlocked` (`skippedRuleCount > 0`, `LifecycleRulesTab.tsx:158-159`) correctly disables the bulk Actions button (`:274`) and row Edit/Delete (`isMutating` at `:314`), but the "Create Lifecycle Rule" button is gated only by `permissions.canUpdateLifecycle`. `lifecycle.get` silently drops unparseable rules (only counted via `skippedRuleCount`), and the modal's add-path builds its full-replace `lifecycle.set` payload from that already-filtered fetch (`freshData?.rules`).
   *Failure:* Creating a new rule while any existing rule is unreadable permanently deletes that unreadable rule from the bucket on save. `LifecycleRulesTab.test.tsx`'s "mutationsBlocked (skipped rules)" block only asserts the bulk Actions button is disabled — never the Create button — confirming this path was missed rather than intentionally exempted.
   *Origin:* independently raised by both the prior-PR-comment-history reviewer and the code-comment-compliance reviewer (the latter caught it via the `LifecycleRulesTab.tsx:155-159` comment describing the invariant `mutationsBlocked` is supposed to enforce).

## Findings raised but filtered out (score < 80)

| Finding | File | Score | Why filtered |
| --- | --- | --- | --- |
| Project-scoped tRPC calls (`storage.canUser`, `lifecycle.get`) invoked directly from components/hooks instead of route loaders, per CLAUDE.md | `useCephPermissions.ts`, `LifecycleRulesTab.tsx` | 0 | Pre-existing codebase convention (`CorsRulesTab.tsx` on `main`, `useSecurityGroupPermissions`) — PR extends it, doesn't introduce it |
| No server-side concurrency control (ETag/revision check) on `lifecycle.set`'s full-replace write | `lifecycleRouter.ts` | 0 | Pre-existing architectural tradeoff shared identically by `corsRouter.ts`/`bucketPolicyRouter.ts`/`versioningRouter.ts`; not introduced or worsened by this PR |
| Inconsistent `.max()` bound — `Expiration.Days` has `.max(3650)` but `NoncurrentDays`/`DaysAfterInitiation`/`Transition.Days` don't | `types/ceph.ts` | 50 | Real gap, but AWS S3 rejects out-of-range values anyway; UX nitpick, not a functional bug |
| Docblock claims "Transitions must be ordered by increasing days" but no `.refine()` enforces it | `types/ceph.ts:946` | 50 | Real doc/code mismatch, but the UI never lets users author `Transitions` (read-only, preserved verbatim) — unreachable in practice |
| `toWireLifecycleRules` docblock says "used before sending rules to S3 SDK" but the function does the opposite conversion and is dead code (test-only) | `lifecycleMapper.ts:207` | 75 | Verified backwards comment, but describes genuinely unused code — the production path (`toSdkLifecycleRules`) is correctly documented and used |

## Reviewers with no findings

- **Shallow bug scan** (large logic/mapping/race-condition bugs in the diff itself): none found — explicitly checked and ruled out index-desync in `useCephPermissions`, `STORAGE_MAPPINGS`↔`storage.json` key parity, `normalizeFilter` branch exhaustiveness, freshness-check-by-`originalIndex` correctness, `minContentColumns` index-shift math, and the rate-limiter self-cleaning-timer guard.
- **Git-history context**: none found — explicitly verified the PR doesn't revert prior design-review fixes (`0bfd055c`), doesn't interfere with the empty-bucket-list fix (`45e8c437`) or the Swift/Ceph terminology unification (`3536c95e`), and in two places actually *resolves* pre-existing `TODO(perms)` comments left on `main`.

---

*Generated via the `code-review` plugin skill against PR #1207 (`kiryl-ceph-permissions` branch vs `main`). All posted findings independently score-verified ≥80/100.*
