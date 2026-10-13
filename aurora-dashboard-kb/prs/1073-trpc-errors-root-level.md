---
type: pr-report
date: 2026-07-17
status: merged
pr: [1073]
author: vlad-schur-external-sap
branch: vlad-fix-default-msgs-at-global-error-route
---
# PR #1073: fix(aurora): trpc errors not used at root level errors

**Author:** vlad-schur-external-sap · **Status:** merged 2026-07-22 (`8944e742`; created 2026-07-15)
**Branches:** `vlad-fix-default-msgs-at-global-error-route` → `main` · **Files:** 6 (+22/-23)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1073

> The PR is not yet ready to merge: the description is an unfilled template (CodeRabbit explicitly flagged this as a fail in its pre-merge check), and the PR itself has 4 unresolved Copilot comments, three of which point to the same problem that the review below found independently (see the "Review" section). This report documents the PR as it is at the time of analysis — not as a merge-ready solution.

## What was done

The PR fixes a specific bug: several `errorComponent` components in the client router rendered `<RouteError error={error} />` **without** the `safeErrorMessage` prop, which caused `RouteError` (see `packages/aurora/src/client/components/Error/RouteError.tsx:19-30`) to deliberately hide the real error text and show a safe default ("Unable to Load Content" / "An unexpected error occurred") — even when the tRPC server returned a meaningful, specially crafted message (for example, "Access denied — your credentials are valid but lack permissions for this operation" from `s3ErrorMapper.ts`).

The fix is targeted — everywhere an `errorComponent` is created, `safeErrorMessage={error instanceof TRPCClientError ? error.message : undefined}` is now passed explicitly, so tRPC errors are shown to the user as is, while non-tRPC errors (not `instanceof TRPCClientError`) are still hidden behind the default text.

Along the way the PR removes two **unreachable** `errorComponent`s (dead code left over from earlier refactorings — see "What it affects") and one unused export, `invalidateCsrfToken`.

## How it is implemented

**The root error boundary** — `packages/aurora/src/client/routes/__root.tsx:63-68` — is the `errorComponent` for the *entire* application (it catches any error not caught by a more specific boundary further down the route tree):

```tsx
import { TRPCClientError } from "@trpc/client"
// ...
function RootErrorComponent({ error }: { error: Error }) {
  return (
    <AuroraLayout>
      <RouteError error={error} safeErrorMessage={error instanceof TRPCClientError ? error.message : undefined} />
    </AuroraLayout>
  )
}
```
Before this PR it was simply `<RouteError error={error} />` here — since this component first appeared (PR #850, "move aurora-portal to aurora package"), tRPC errors at the root level never showed their real text.

**The project details route** — `packages/aurora/src/client/routes/_auth/projects/$projectId.tsx:136` — the same fix, the same pattern:
```tsx
return <RouteError error={error} safeErrorMessage={error instanceof TRPCClientError ? error.message : undefined} />
```
This `ProjectErrorComponent` was added by PR #1035 ("improve project not found error handling") and has had the same gap ever since.

**Dead code removal**: `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images.tsx` lost its own `errorComponent: ({ error }) => <RouteError error={error} />` — this route has neither a `loader` nor any other point where an error could be thrown before render, so this boundary had been unreachable since it was added (PR #900). Errors now correctly bubble up to `$projectId.tsx`'s `ProjectErrorComponent` (verified: the neighboring routes `compute/index.tsx` and `compute/flavors.tsx` already relied on the same pattern without their own `errorComponent`).

**Removal of an unused export** — `packages/aurora/src/client/trpcClient.ts:58-63`:
```ts
-/**
- * Invalidate the cached CSRF token.
- * Call this when receiving a 403 response to trigger a fresh token fetch on the next request.
- */
-export const invalidateCsrfToken = () => csrfCache.invalidate()
```
The export had no call sites in the codebase either before or after the removal — but see "Review": this is not an entirely clear-cut cleanup.

## What it affects

**The blast radius of the fix itself is wide**: `__root.tsx`'s `errorComponent` is the top-level error boundary; it catches any unhandled error from any route of the application. Before this PR, tRPC messages were suppressed everywhere there was no more specific boundary with its own `safeErrorMessage` — now they are shown.

**Direct connection to PR #1067** (merged a day earlier, rewrote `projects/index.tsx` to use `Suspense`/`useSuspenseQuery`): that rework left `ProjectsOverviewNavBar` **outside** the `ErrorBoundary` it had itself added, and turned this file's route-level `errorComponent` into unreachable dead code (data is now loaded in the component, not in the `loader`, so the router-level `errorComponent` never fires). PR #1073 fixes exactly this — it moves `ProjectsOverviewNavBar` inside the `ErrorBoundary`:
```tsx
// packages/aurora/src/client/routes/_auth/projects/index.tsx:76-93 (after the PR)
<ErrorBoundary
  fallbackRender={({ error }) => (
    <RouteError error={error} safeErrorMessage={error instanceof TRPCClientError ? error.message : undefined} />
  )}
>
  <ProjectsOverviewNavBar searchTerm={search} onSearch={handleSearch} />
  <div className="pt-5">
    <Suspense fallback={...}><ProjectsContent search={search} /></Suspense>
  </div>
</ErrorBoundary>
```
and removes the dead `errorComponent` from the route config. A side effect of this move (not a bug, but a noticeable behavioral change): the search bar (`ProjectsOverviewNavBar`) now also disappears when loading the project cards fails, whereas previously it stayed visible — consistency matters more, but it's worth knowing.

**Consumer check**: a `git grep` for `safeErrorMessage`/`TRPCClientError` at the PR's head commit shows that after this fix ALL production (non-test) `errorComponent`/`RouteError` sites in the client either pass `safeErrorMessage` or have been removed as unreachable — no discrepancies remain. The test file `RouteError.test.tsx` still calls `<RouteError error={error} />` without the prop in several cases — this is intentional (it tests precisely the default hiding behavior), not a missed call site.

## Review

**Found (confidence ≥ 80):**

1. **`error instanceof TRPCClientError` is an insufficient safety condition; raw messages from the server can leak through the root error boundary.** (confidence 85)
   `RouteError.tsx:19-24` documents an invariant: "Do not expose raw Error.message by default as it may contain sensitive information" — only explicitly verified safe messages may be shown. But the server router (`packages/aurora/src/server/trpc.ts:5`, `initTRPC.context<AuroraPortalContext>().create()`) doesn't define a custom `errorFormatter`, so tRPC by default passes `error.message` through as is. Specifically, `packages/aurora/src/server/Storage/helpers/s3ErrorMapper.ts:80-81` does `parts.push(s3Error.message)` for unmapped S3/Ceph error codes — the raw AWS/Ceph SDK error text goes straight into `TRPCError.message` → `TRPCClientError.message` → and is now shown to the user via the root boundary (which catches errors from *any* route, not only storage). This is exactly the scenario the comment in `RouteError.tsx` warns against.
   This is not speculation on the review's part — PR #1073 itself already has **3 unresolved Copilot comments** (on `__root.tsx`, `$projectId.tsx` and `projects/index.tsx`) recommending verbatim: "Consider filtering out INTERNAL_SERVER_ERROR (or otherwise ensuring messages are sanitized)". None had been addressed at the time of analysis.
   Files: `packages/aurora/src/client/routes/__root.tsx:66`, `packages/aurora/src/client/routes/_auth/projects/$projectId.tsx:136`, `packages/aurora/src/client/routes/_auth/projects/index.tsx:75` (the last one — the pattern already existed before PR #1073; 2 more such places were simply added).

**Also noticed (confidence 50-79, confirmed but did not reach full confidence):** — no candidates qualified for this tier; the only other candidate (removing `invalidateCsrfToken` without replacing the recovery mechanism after CSRF token rotation, also flagged by a Copilot comment on the PR) got confidence 35 — a real architectural gap, but the export was dead code with no call sites even before the PR, so it doesn't break anything that worked; below the inclusion threshold.

## What was done well

Removing the unreachable `errorComponent`s (in `images.tsx` and `projects/index.tsx`) is not cosmetic but a correct response to the fact that the routing architecture changed in PR #1067 (data fetching moved from the `loader` into the component), and the old route-level boundaries stopped making sense. The PR author verified this rather than just patching in place.

---
Analyzed: 2026-07-17 · commit `0263a780e`
