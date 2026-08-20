# PR #1178 Code Review — Ceph Lifecycle Rules UI

Branch: `kiryl-ceph-lifecycle-rules` vs `main`
Reviewed: 2026-08-20

## Correctness

1. **Days fields accept non-numeric/invalid values client-side**
   `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRuleForm.tsx:153`
   `canSubmit()` only checks Days fields are non-empty strings, never that they parse to a positive integer, and `preventDefault()` runs before `handleSubmit` so HTML5 min/required validation never fires.
   *Failure:* User types "abc", "0", or "-5" into a Days field; Save stays enabled and NaN or a non-positive number is sent to the server, which only then rejects it via Zod — a late, unhelpful error instead of inline validation.

2. **Bucket-wide-expiry warning disagrees with actual submitted filter**
   `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRuleForm.tsx:79`
   `onSubmit` builds the filter from the untrimmed Prefix while the "will expire whole bucket" warning is computed from the trimmed value, so the two disagree on whitespace-only prefixes.
   *Failure:* User enters a Prefix of only spaces with Expiration checked and no tags: the UI warns "this will expire all objects in the bucket," but the rule actually submitted is scoped to the literal prefix `"   "` — the warning doesn't match what gets saved.

3. **Missing server-side check for Abort+tag-filter constraint**
   `packages/aurora/src/server/Storage/types/ceph.ts:985`
   The write schema enforces "ExpiredObjectDeleteMarker can't combine with tag filters" but has no equivalent refinement for AWS's real constraint that `AbortIncompleteMultipartUpload` can't combine with a tag Filter; only the form's inline `canSubmit()` gate enforces it.
   *Failure:* A direct tRPC `lifecycle.set` call, a future second UI entry point, or a bug in the form gate can submit `AbortIncompleteMultipartUpload` combined with a tag Filter; it passes both server Zod validation and the client's own `validateLifecycleRules`, then gets rejected by RGW/S3 with an opaque error instead of a structured validation message.

4. **One malformed external rule breaks `lifecycle.get` entirely**
   `packages/aurora/src/server/Storage/routers/ceph/lifecycleRouter.ts:104`
   The `get` procedure maps S3 rules through the throwing `lifecycleRuleReadSchema.parse(rule)` inside `Array.map`; the catch only special-cases `NoSuchLifecycleConfiguration`, so any `ZodError` from one malformed rule aborts the entire call.
   *Failure:* A bucket has a lifecycle rule authored outside Aurora (AWS CLI/console) that doesn't satisfy the read schema; `lifecycle.get` for that bucket fails entirely instead of showing the other valid rules.

5. **Freshness check false-positives on reordered-but-same arrays**
   `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/DeleteLifecycleRuleModal.tsx:129`
   The pre-delete freshness check compares `JSON.stringify(freshRule) !== JSON.stringify(cachedRule)`; Zod normalizes key order so that's safe, but nothing normalizes array element order (`Filter.And.Tags`, `Transitions`).
   *Failure:* RGW returns `Filter.And.Tags` or `Transitions` in a different element order across two GETs of the same logically-unchanged rule; the check false-positives as a concurrent modification and blocks a valid delete.

## Duplication / simplification

6. **Rate limiter duplicated a third time across routers**
   `packages/aurora/src/server/Storage/routers/ceph/lifecycleRouter.ts:22`
   `checkLifecycleSetRateLimit` is a third verbatim copy of the same Map-based self-cleaning rate limiter already duplicated in `corsRouter.ts` and `bucketPolicyRouter.ts`, differing only in constants and message text.
   *Risk:* This same PR had to independently apply the same self-cleaning-timer fix to two copies of this limiter already; any future correctness fix now requires finding and editing three near-identical implementations, risking fixing some but missing others.

7. **Singular/bulk delete modals duplicate ~90% of logic**
   `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/DeleteLifecycleRulesModal.tsx:1`
   `DeleteLifecycleRuleModal.tsx` and `DeleteLifecycleRulesModal.tsx` duplicate ~90% of their logic; the singular-rule modal is structurally the bulk modal called with `ruleIndices=[ruleIndex]` — a pattern already duplicated once for CORS and now repeated for lifecycle rules.
   *Risk:* A bug fix to the freshness-check logic or a UX change to the confirm flow must be manually replicated across four near-identical files (two for CORS, two for lifecycle) instead of one shared component/hook.

8. **`normalizeFilter` duplicated client/server, no parity check**
   `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/utils/lifecycleUtils.ts:29`
   `normalizeFilter` is hand-duplicated verbatim between client and server, kept in sync only by a comment convention — no shared isomorphic module, no test/lint enforcement of parity, and the server copy has no production caller.
   *Risk:* A future change to filter-normalization rules is made in one copy and forgotten in the other, silently diverging client-side validation from server-side mapping.

## Test coverage / dead code

9. **Tested Date-conversion function has no production caller**
   `packages/aurora/src/server/Storage/helpers/lifecycleMapper.ts:140`
   `toWireLifecycleRules` is exported and unit-tested but has no production caller — the router's `get` procedure parses raw SDK rules directly instead of routing through it, so this PR's Date-conversion logic is never exercised by the real GET path.
   *Risk:* The tested round-trip diverges from the real GET path's behavior, so a Date-handling bug in the actual path could go undetected since the test suite only validates the unused function.

## Efficiency

10. **Rule list derivations recomputed every render, no `useMemo`**
    `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRulesTab.tsx:181`
    `rulesWithOriginalIndices`, the sorted/filtered rule lists, and select-all derived booleans are recomputed inline on every render, despite depending only on `rules`/sort/search state.
    *Risk:* Any unrelated re-render (a modal callback firing, toggling one row's selection) re-runs a full map+sort+filter+scan over up to 100 rules, and the fresh references also prevent row-level memoization in `LifecycleRulesTable.tsx` from ever bailing out.

---

*Generated via the `code-review` skill against `kiryl-ceph-lifecycle-rules` vs `main`. All findings independently verified.*
