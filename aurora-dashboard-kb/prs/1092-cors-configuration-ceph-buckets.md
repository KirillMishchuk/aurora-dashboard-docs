---
type: pr-report
date: 2026-08-11
status: merged
pr: [1092]
author: KirylSAP
branch: kiryl-ceph-cors
---
# PR #1092: feat(aurora): add CORS configuration management for Ceph/S3 buckets

**Author:** KirylSAP · **Status:** merged 2026-08-12 (commit `b7576db`)
**Branches:** `kiryl-ceph-cors` → `main` · **Files:** 35 (+4643/-45, after round 4)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1092

> This is the fourth version of the report. The first (2026-07-25, commit `1f7a0d9`) described the modal-oriented implementation (20 files, +2212/-6). The second (2026-08-11 morning, commit `834f993`) recorded the complete redesign into a tab-based UI (34 files, +4478/-45) and 3 findings ≥80. The third (2026-08-11 afternoon, commit `5d8fb2d`) recorded the first round of fixes — 1 of 3 findings closed, 2 still open, plus 2 new candidates at 75/70. This version reflects four targeted fix commits `4f16ad3`/`356618c`/`81598e1`/`8cbd4a5` (2026-08-11, 14:09), written from `dev-executor` prompts prepared based on the previous report. The branch is in sync with `main` (merge-base = current `origin/main`).

### Round 4 (commits `4f16ad3` → `8cbd4a5`, 13 files, +95/-49) — all 4 remaining findings closed

All four prompts were carried out and verified line by line against the code (not against the commit messages):

- **[Was #1, 100] Changeset — FIXED.** The text has been rewritten: it no longer claims that anything was removed from the header, and correctly describes the added «CORS Rules» tab and the added «Delete CORS Rules» item in the header menu.
- **[Was #2 (in the 3rd version), 95] Rule ID helptext — FIXED.** `placeholder`/`helptext` were replaced with text relevant to a CORS rule; the strings `"Access to admin area"` and `"Confirm that the Project ID is accurate."` disappeared entirely from `en/de messages.po` on `pnpm check-i18n` (meaning there were no other legitimate uses of these strings in the codebase — the earlier assumption that the second string was used for a real Project ID field was not confirmed, but it did not cause a problem either: a clean removal).
- **[F, 50] `isMutating={false}` — FIXED.** Implemented exactly as described in the prompt: `onMutatingChange` is threaded through `CorsRuleModal`, `DeleteCorsRulesModal`, `DeleteCorsRuleModal` (following the existing `onValidationChange` pattern), and `CorsRulesTab` and `CorsRulesTable` aggregate the state into `effectiveIsMutating`, which now actually disables Edit/Delete in the rows. The code was verified line by line — the implementation is correct.
- **[A, 50] Dead `DeleteCorsModal` in the tab — FIXED.** The `isDeleteModalOpen` state, the render block, the unused imports (`DeleteCorsModal`, `getCorsDeleteErrorToast`) and the mock in the test were removed completely and cleanly — the working path for deleting the whole configuration via the header (`BucketHeaderActions`/`BucketModals`) is untouched.

Two new observations from the same round, both **did not pass the ≥80 threshold** (independent confidence scoring):
- **[75] The new `isMutating` test does not check what it claims.** The restored test `CorsRulesTable.test.tsx` is called «renders without errors when isMutating is true», but it only checks the absence of a crash and the presence of the menu button — it does not open the menu and does not check that Edit/Delete are actually `disabled`. The implementation itself (`effectiveIsMutating`) is correct and I verified it directly in the code, but this test will not catch a regression (for example, an accidentally reintroduced hardcoded `isMutating={false}`).
- **[70] A narrow "blind window" in `onMutatingChange` during the freshness check.** In all three modals (`CorsRuleModal`, `DeleteCorsRuleModal`, `DeleteCorsRulesModal`) the mutation is preceded by `await ...cors.get.fetch(...)` (freshness check) — at that moment `setMutation.isPending`/`deleteMutation.isPending` is still `false`, so during this short interval (one network request) `onMutatingChange` reports "not mutating" even though the action has already started. `DeleteCorsRuleModal`/`DeleteCorsRulesModal` introduced a local `isVerifying` and use it to block their own confirm button, but did not include `isVerifying` in `onMutatingChange` itself — so the protection does not extend to NEIGHBOURING table rows during this window. `CorsRuleModal` did not introduce such a local flag for its edit branch at all. A narrow window that requires two users working on the same bucket simultaneously — according to both independent checks, this is a real but unlikely gap in practice.

### What changed since the previous version of the report (commit `5d8fb2d`, 16 files, +250/-131)

Commit `5d8fb2d` deliberately closes some of the findings from the previous report:

- **[Was #2, 100] Hardcoded non-localized toasts when deleting CORS from the header — FIXED.** `BucketModals.tsx` now uses `getCorsDeletedToast`/`getCorsDeleteErrorToast` instead of template strings — exactly what was suggested.
- **Stale `selectedIndices` index after single-rule deletion (below threshold, 75) — FIXED (crudely, but in a working way).** `CorsRulesTab` gained `handleDeleteRule`, which simply resets `selectedIndices` to `[]` on any single-rule deletion — not surgical (it doesn't shift the indices), but it fully removes the stale-index risk, at the cost of resetting all the user's other selections.
- **`setState` during render in `CorsRuleForm` (below threshold, 50) — FIXED.** `onValidationChange` was moved into a `useEffect`.
- **`as any` cast that came back after an earlier fix (below threshold, 75) — PARTIALLY FIXED.** A `toCorsRule()` helper was added in the new `utils/corsUtils.ts`, encapsulating the `AllowedMethods` type cast in a single explicit, documented place instead of `as any` on the whole object with `eslint-disable` — not perfect type safety, but clearly better, and it is reused in three places (`CorsRuleModal`, `DeleteCorsRuleModal`, `DeleteCorsRulesModal`).
- **Cross-tab index race without a freshness check (below threshold, 50) — FIXED for edit/delete, NOT for add** (see the new finding in «Review» below). In `CorsRuleModal`, `DeleteCorsRuleModal`, `DeleteCorsRulesModal` the mutation is now preceded by a repeat `fetch` + a `JSON.stringify` comparison of the specific rule against the original snapshot — if the rule has changed, an error is shown instead of a silent overwrite.
- Plus fixes unrelated to the previous report: tab title «Cors Rules» → «CORS Rules»; the row key in `CorsRulesTable` is always `originalIndex` (it was `rule.ID ?? originalIndex`, which could produce duplicate React keys when `ID` was missing/repeated); in `DeleteCorsRulesModal` the «Rule #N» numbering in the bulk-delete preview was fixed — previously the index within the truncated `visibleRules` was used instead of the rule's real index, so the wrong number was shown when non-adjacent rows were selected.

**Not closed:**

- **[Was #1, 100] The changeset claims the «Delete CORS Rules» item was removed from the header — untouched, the claim is still wrong.**
- **[Was #3, 95] Copied helptext «Confirm that the Project ID is accurate.» on the Rule ID field — untouched.**
- **[F, 50] `isMutating={false}` is still hardcoded** in `CorsRulesTab.tsx:298` when rendering `CorsRulesTable` — Edit/Delete in the rows are still not blocked during a mutation.
- **[A, 50] A second unreachable `DeleteCorsModal` instance inside `CorsRulesTab`** (gated by `isDeleteModalOpen`, `setIsDeleteModalOpen(true)` is never called anywhere) — untouched.

## What was done

The PR closes **Section 12: CORS Configuration** of epic #608 for Ceph (S3) buckets — the backend (`corsRouter.ts`: `get`/`set`/`delete`) has not changed conceptually since the July version, but the frontend has been completely reinvented: instead of a modal with two tabs (view/edit), there is now a separate **«Cors Rules»** tab on the bucket details page, next to the existing Overview tab — with full CRUD: a list of rules in a `DataGrid`, search/sort with state in the URL, single and bulk deletion.

The branch history (`git log`) shows three waves: (1) `fc5cf77` (08-04) — the first implementation, a modal with two tabs, as in the July version; (2) `bef794d` (08-10, "apply 6 critical fixes from code review") — fixes from the author's own review, including replacing the `as any` cast with proper client-side validation via a separate `corsValidation.ts` file; (3) `6025e09` (08-08) → a series of commits up to `834f993` (08-11) — the complete redesign into tabs, during which `corsValidation.ts` was deleted along with some of the fixes from (2) (see «Review» and the historical finding below).

Three new large visual blocks: the tab itself (`CorsRulesTab`/`CorsRulesTable`), the add/edit rule form (`CorsRuleForm` in the `CorsRuleModal` modal), and **three** delete modals with different scope — delete the whole configuration, a single rule, or a selected group of rules. Plus a new reusable `TagInput` for string-array fields (origins/headers).

## How it is implemented

### Backend — `corsRouter.ts` has not changed in substance, but gained a rate limit

Three procedures under `cephProtectedProcedure`, mounted as `storage.ceph.cors.{get,set,delete}`:

```typescript
// packages/aurora/src/server/Storage/routers/index.ts:34-36
      cors: auroraRouter({
        ...corsRouter,
      }),
```

`get`/`delete` treat `NoSuchCORSConfiguration` as a valid "no configuration" state rather than an error — the same pattern as in the July version:

```typescript
// packages/aurora/src/server/Storage/routers/ceph/corsRouter.ts:90-95
    } catch (error) {
      // NoSuchCORSConfiguration is not an error - it means no CORS config set
      const s3Error = error as { name?: string; Code?: string }
      if (s3Error.name === "NoSuchCORSConfiguration" || s3Error.Code === "NoSuchCORSConfiguration") {
        return { corsRules: null }
      }
```

New compared to the July version — two validation schemas instead of one: a strict `corsRuleSchema` (for `set`, 1-5 `AllowedMethods` without duplicates, ≥1 `AllowedOrigin` with a wildcard pattern check, `MaxAgeSeconds` with only `.min(0)` — there is no upper bound in the schema at all) and a lenient `corsRuleReadSchema` (for `get`, accepts arbitrary strings so as not to fail on rules created outside Aurora):

```typescript
// packages/aurora/src/server/Storage/routers/ceph/corsRouter.ts:85-89
      // Use lenient read schema to accept rules with values outside write-time constraints
      // (e.g., more than 5 AllowedMethods, though write schema now matches S3 limits)
      const corsRules = rawCorsRules.map((rule) => corsRuleReadSchema.parse(rule))
```

An in-process rate limiter was also added on `set` — no more than 10 changes per minute per `projectId:bucketName` pair, with state in a module-level `Map`:

```typescript
// packages/aurora/src/server/Storage/routers/ceph/corsRouter.ts:8-38 (abridged)
const corsSetRateLimits = new Map<string, { count: number; resetAt: number }>()
function checkCorsSetRateLimit(bucketName: string, projectId: string): void {
  // ...
  if (limit.count >= 10) {
    throw new TRPCError({ code: "TOO_MANY_REQUESTS", ... })
  }
  limit.count++
}
```

The limiter is per-process (not distributed) — with multiple BFF instances behind a load balancer, the effective threshold scales with the number of replicas. This limiter did not make it into the rewritten section of the design document (`009_ceph_s3_bff.md`) at all — neither a description nor a caveat about the per-process behaviour.

`s3ErrorMapper.ts` gained two new codes (`NoSuchCORSConfiguration`, `MalformedXML`) — this is a shared file for all Ceph routers, so everyone benefits, not just CORS; that said, `NoSuchCORSConfiguration` in the mapper is effectively unreachable, since `corsRouter.ts` catches this error earlier (see «Review», rejected finding scored 65).

`mockContext.ts` (a shared test helper for all Ceph routers) was extended with `res`/`signal` fields to match the real shape of `AuroraPortalContext` — this was needed for typing the new `corsRouter.test.ts`, but it also fixes the mock for 6 other Ceph router test files that import it.

### Tab architecture on the bucket page

The objects route (`.../$containerName/objects/index.tsx`) gained a URL parameter `view: "overview" | "cors-rules"` (default `"overview"`) and three CORS-specific parameters `corsSortBy`/`corsSortDirection`/`corsSearch`, independent of the object list parameters:

```typescript
// objects/index.tsx:27-33
  view: z.enum(["overview", "cors-rules"]).optional().default("overview"),
  corsSortBy: z
    .enum(["ID", "AllowedOrigins", "AllowedMethods", "AllowedHeaders", "ExposeHeaders", "MaxAgeSeconds"])
    .optional()
    .default("ID"),
  corsSortDirection: z.enum(["asc", "desc"]).optional().default("asc"),
  corsSearch: z.string().optional(),
```

Branching by provider and `view` happens directly in the route component:

```typescript
// objects/index.tsx:108-124 (abridged)
              switch (provider) {
                case "swift":
                  return <SwiftObjects provider={provider} containerName={containerName} />
                case "ceph":
                  if (view === "cors-rules") {
                    return <CephCorsRules bucketName={containerName} />
                  }
                  return <CephObjects bucketName={containerName} />
```

Swift explicitly ignores `view` (covered by the regression test `objects/index.test.tsx:344-360`). `CephCorsRules` is not a new component but `CorsRulesTab`, re-exported under this name from the barrel `Ceph/Buckets/index.tsx:44`.

The tab strip itself is rendered not in the route but in `BucketHeader` — above the content that the route selects:

```tsx
// .../Ceph/Buckets/BucketHeader.tsx:73-90 (abridged)
      <ContentHeader title={bucketName} projectId={projectId} badges={badges} actions={actions} />
      <div className="-mt-4 mb-8">
        <BucketDetailTabs />
        <Divider />
      </div>
      <BucketModals ... />
```

`BucketDetailTabs` is a thin wrapper over `TabNavigation` that reads/writes the same `view` parameter via the generated `Route` object of the same route. That is, the tab switcher and the content it switches are two independent readers/writers of one URL parameter, synchronized only by the fact that both import the same `Route`. It works, but it is structurally decoupled (the tab component does not wrap its content; it is a parallel consumer of the state).

`useBucketInfo` was extended with a `storage.ceph.cors.get` query; the result is used in `BucketHeader` for `hasCors` (visibility of the badge/menu item).

### CORS tab: container, table, form, TagInput

`CorsRulesTab` (353 lines) is the container: it owns the `cors.get` query, the sort/search state (in URL parameters), the row selection state (`selectedIndices`), and orchestrates three modals (add/edit, delete whole configuration, bulk delete).

`CorsRulesTable` (190 lines) is a presentational 8-column table driven by props; however, it **itself owns** the state for single-rule deletion (`deleteModalState` + its own `DeleteCorsRuleModal` instance) — this state is not lifted into `CorsRulesTab`, unlike bulk deletion. Rows are identified by `rule.ID ?? originalIndex`, since rules have no stable server-side identifier.

`CorsRuleModal` wraps `CorsRuleForm` in a `Modal`; on submit it builds the full updated array of rules and calls `cors.set` with the whole thing (add — append, edit — replace by index):

```typescript
// CorsRuleModal.tsx:88-101
  const handleSubmit = (rule: CorsRuleRead) => {
    markSubmitted()
    const currentRules = corsData?.corsRules ?? []
    let updatedRules: CorsRuleRead[]
    if (editingIndex === null) {
      updatedRules = [...currentRules, rule]
    } else {
      updatedRules = [...currentRules]
      updatedRules[editingIndex] = rule
    }
```

The Save button is in the modal footer rather than in the form, and triggers submission via `document.querySelector('#'+formId).requestSubmit()` — a DOM bridge between the footer and the form instead of a `ref`.

`CorsRuleForm` uses `@tanstack/react-form`. The helptext of the Rule ID field was clearly copied from another field and not edited:

```tsx
// CorsRuleForm.tsx:65-73
          <form.Field name="ID">
            {(field) => (
              <TextInput
                label={t`Rule ID`}
                ...
                placeholder={t`Access to admin area`}
                helptext={t`Confirm that the Project ID is accurate.`}
```

The string `"Confirm that the Project ID is accurate."` already exists in `de/messages.po:636` for another, non-CORS Project ID field — almost certainly a copy-paste. See «Review», item 3 (score 95).

`TagInput` (a new shared component, 165 lines) is a field for a string array with `urlValidator`/`headerValidator` validators. These validators duplicate (in different code, with the same rules) the `.refine()` logic in the server-side `corsRuleSchema` — client and server independently reinvent the same wildcard-origin check. The component has not a single string passed through Lingui (the "Add" button, validator error texts) — all the other new components in this PR correctly use `t`/`Trans`.

### Three delete modals — different scope, one not wired up

1. **`DeleteCorsModal`** — deletes **the whole CORS configuration** (`cors.delete`). It is wired up twice: (a) from the bucket header actions menu via `BucketHeaderActions.tsx:49` → `BucketModals.tsx:131-143` — this path actually works; (b) a separate instance inside `CorsRulesTab.tsx:296-309`, gated by the `isDeleteModalOpen` state (declared on line 78) — but `setIsDeleteModalOpen(true)` is not called anywhere in the file or in the repository (only `false` on lines 300/302). This second instance is unreachable dead code, apparently left over from a refactor in which «Delete All» was replaced with bulk deletion by selection.
2. **`DeleteCorsRuleModal`** — deletes a single rule by index, invoked from a table row (internal state of `CorsRulesTable`, not lifted into the tab).
3. **`DeleteCorsRulesModal`** — bulk deletion by selected indices, with a preview of the first `MAX_VISIBLE_RULES = 5` rules and a line «…and N more».

Both #2 and #3 are live and meaningfully different (one rule vs a selection). #1 in variant (a) is an intentional "global" shortcut from the header, but #1 in variant (b) is dead code that should either be wired to a UI trigger or removed together with `isDeleteModalOpen`.

All three delete modals independently make their own `cors.get.useQuery` instead of reusing the data already loaded in `CorsRulesTab`/`useBucketInfo`, relying on the React Query cache.

### Locales, design document, changeset

The changeset (`minor` for `@cobaltcore-dev/aurora`) claims: *«The Add CORS, Edit/View CORS buttons, and Delete CORS menu item have been removed in favor of full CRUD operations within the Cors Rules tab.»* This is **not true** — a comparison with the base commit (`c65b027a`) shows that before this PR the bucket header had neither CORS buttons nor a «Delete CORS Rules» item at all — this PR **adds** the «Delete CORS Rules» item to the header menu rather than removing anything. See «Review», item 1 (score 100).

The design document (`009_ceph_s3_bff.md`) gained a full section `### CORS Configuration (storage.ceph.cors)` — with a description of `get`/`set`/`delete`, examples, and a note on the peculiarities of testing CORS in Ceph RGW (RGW does not add CORS headers to HEAD requests, only to GET/POST/PUT/DELETE/OPTIONS). This note contains a link [`DOCS/plans/2026-07-25-cors-manual-testing-scenarios.md`](../../plans/2026-07-25-cors-manual-testing-scenarios.md), which points to the author's personal notes folder (not part of the repository); for upstream readers of this PR the path will not exist (see «Review», rejected finding scored 75). Also, the section on `MaxAgeSeconds` in the document (and one of the comments in `types/ceph.ts:581`) claims an upper bound of 86400, although the actual Zod schema has no maximum (see the rejected finding scored 75).

The `en`/`de` locales grew from 1255 to 1330 `msgid` lines (+75 for the new CORS UI); all 75 new German strings have an empty `msgstr ""` — none of them is translated, the catalog was only re-extracted. This is probably a separate translation process rather than an oversight of this PR.

## What it affects

The PR is fully self-contained within `packages/aurora` and does not change any contract consumed by `apps/dashboard` or other monorepo packages (`policy-engine`, `signal-openstack`, `config`). A search across the whole repository at the head commit (`git grep -n '<symbol>' HEAD`) for each new export/tRPC key/type showed:

- `storage.ceph.cors.{get,set,delete}` — there is only one consumer outside `Ceph/Buckets/*`: `useBucketInfo.ts:95`, which is itself part of the same feature and is updated by this same PR. There are no references to CORS in `apps/dashboard` or in `policies/storage.json` (just as with `bucketPolicy`/`versioning` — this is not a regression of the PR but an existing pattern: `permissionRouter.ts`'s `STORAGE_MAPPINGS` does not cover any of the "advanced" bucket-level features).
- All new React components/hooks (`BucketDetailTabs`, `CorsRuleForm`, `CorsRuleModal`, `CorsRulesTab`, `CorsRulesTable`, `TagInput`, the three Delete modals) — without a single consumer outside their directory. `CephCorsRules` (re-export of `CorsRulesTab`) is used exactly once, in `objects/index.tsx`.
- New types/schemas (`CorsRule`, `CorsRuleRead`, `CorsConfiguration`, `CorsAllowedMethod`, `GetCorsOutput`, Zod schemas) — consumed exclusively inside `corsRouter.ts` and the client code of the same feature; `CorsConfiguration`/`CorsAllowedMethod` are exported but not used anywhere yet (dead but harmless exports).
- The only cross-cutting dependency is `mockContext.ts`, shared by 7 Ceph router test files; the change is backward compatible (optional fields added to match the real context shape).

The old modal implementation (the July version — `CorsModal.tsx`, `CorsRulesViewer.tsx`) was removed completely and without a trace: `git grep -n '\bCorsModal\b' HEAD` (with a word boundary, excluding `DeleteCorsModal` matches) and `git grep -n 'CorsRulesViewer' HEAD` return **zero matches** — no references to the deleted files remain in the code, tests or docs. The only "leftover" of the move from modal to tab is not a dead reference but dead state: the second unreachable `DeleteCorsModal` instance inside `CorsRulesTab` (see above).

## Review

**Current status: 0 confirmed (≥80) findings open.** All 4 findings that reached this stage from previous versions of the report (changeset, Rule ID helptext, `isMutating`, dead `DeleteCorsModal` in the tab) were closed by commits `4f16ad3`/`356618c`/`81598e1`/`8cbd4a5` — each verified line by line against the current code, not against the commit messages; details in the «Round 4» block above. The remaining two observations of this round (the `isMutating` test that doesn't check what it claims; the narrow blind window in `onMutatingChange` during the freshness check) scored 75 and 70 in independent confidence scoring — below the threshold; they are listed in «Round 4» for completeness and are not counted as confirmed findings.

Also still below the threshold (unchanged since the previous version, the code was not touched, not in scope of the last round): the missing freshness check on the add-new-rule branch in `CorsRuleModal` (75, «What changed» above), the missing Lingui wrappers in `TagInput.tsx` (75), the dead `NoSuchCORSConfiguration` branch in the error mapper (65), and several more items scored 25-60 from the second version of the report — if the PR gets another round of review, they are worth keeping in view, but there is currently no reason to raise them as separate fix prompts (low practical significance by independent assessment).

---
Analyzed: 2026-08-11 · commit `8cbd4a5` (previous versions of the report — commits `1f7a0d9`, `834f993`, `5d8fb2d`)

<!-- related:auto — generated from pr/issue properties by tools/update-related.py; do not edit by hand -->
## Related

- plan · 2026-07-25 · [2026-07-25-cors-configuration-testing-plan](../../plans/2026-07-25-cors-configuration-testing-plan.md)
- plan · 2026-08-11 · [2026-08-11-fix-pr1092-cors-review-findings](../../plans/2026-08-11-fix-pr1092-cors-review-findings.md)
