---
type: pr-report
date: 2026-08-27
status: merged
pr: [1209]
author: andypf
branch: andypf/fix-multi-tab-auth-error-1128
---
# PR #1209: fix(aurora): improve multi-tab auth error handling (#1128)

**Author:** andypf · **Status:** created 2026-08-26, updated 2026-08-27, merged 2026-08-27 (commit `9796a71b`)
**Branches:** `andypf/fix-multi-tab-auth-error-1128` → `main` · **Files:** 18 (+434/-521)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1209

> Version 2 of the report. The author pushed fix commits in response to the findings of version 1 (all of which also surfaced independently in the automated Copilot/CodeRabbit review on this same PR). The head commit changed `c44278f3` → `6c2fedef`; the base (`main`) did not change. The comparison below is specifically between these two versions of the PR, not the PR as a whole.

## What changed since the first version

All 4 findings at the ≥80 level from version 1 of the report are closed by targeted fix commits; verified line by line against the actual code, not from the PR description (which was left untouched and still shows the old "Session Changed" text in the "User Experience" section — outdated).

1. **`sessionRouter.ts` — a `null` check was added.** The `domain`/`project` branches in `setCurrentScope` now throw `TRPCError({ code: "NOT_FOUND" })` if `token?.tokenData.domain`/`token?.tokenData.project` are not set after rescope:
   ```ts
   // packages/aurora/src/server/Authentication/routers/sessionRouter.ts:36-43
   if (!token?.tokenData.project) {
     throw new TRPCError({ code: "NOT_FOUND", message: "Failed to rescope to the requested project." })
   }
   ```
   `sessionRouter.test.ts` was updated in the same commit — the test "should handle null session from rescopeSession" now checks `rejects.toThrow(TRPCError)` instead of the previous `expect(result).toEqual({project: undefined, ...})`. Closes finding #1 (was 95/100).

2. **`context.ts` — `pendingRescopes` now stores the original (rejecting) promise, not a safe wrapper.** Instead of `rescopeTokenPromise.catch(() => null).finally(...)` being put into the map, it is now:
   ```ts
   // packages/aurora/src/server/context.ts:370-393
   const cleanupPromise = rescopeTokenPromise.finally(() => { /* cleanup of pendingRescopes/sessionRescopes, unchanged */ })
   pendingRescopes.set(scopeKey, rescopeTokenPromise)     // ← the original promise, not .catch(() => null)
   cleanupPromise.catch(() => {})                          // ← the unhandled rejection is swallowed on a SEPARATE derived promise
   ```
   Verified: the concurrent-request deduplication branch (`await cachedTokenPromise`, slightly above in the same function) still doesn't wrap the `await` in try/catch — i.e. on error it now honestly rejects and propagates `SignalOpenstackApiError` on to `openstackErrorMiddleware`, just like the initiating call. The comment "Prevent unhandled rejection on the cleanup promise" now correctly describes what exactly it swallows (in version 1 the comment pointed at the wrong promise). Closes finding #2 (was 90/100).

3. **`$projectId.tsx` — the message for `UNAUTHORIZED` was rewritten so it no longer implies the wrong recovery.** Instead of "Session Changed... Please select a project from your current domain" (with a "Go to Projects" button), it is now:
   ```tsx
   // packages/aurora/src/client/routes/_auth/projects/$projectId.tsx:106-119
   title={t`Session Expired`}
   body={t`Your session has expired. Please log in again. This may have occurred because you logged out or switched domains in another browser tab.`}
   action={<Button variant="primary" onClick={() => navigate({ to: "/" })}><Trans>Log In</Trans></Button>}
   ```
   The server still doesn't distinguish between "the session really expired" and "invalid because of a domain switch in another tab" (both cases are 401 → the same `UNAUTHORIZED`), but now the only action offered ("Log In" → `/`) works equally correctly for both scenarios — unlike the previous "select a project", which was useless when the session had actually expired. Closes finding #3 (was 85/100).

4. **`trpc.ts` — 400 is split into a separate `BAD_REQUEST` branch and no longer lumped together with 404/`NOT_FOUND`.**
   ```ts
   // packages/aurora/src/server/trpc.ts:34-43
   if (cause.statusCode === 400) {
     return { ...result, error: new TRPCError({ code: "BAD_REQUEST", message: "The OpenStack request was invalid.", cause }) }
   }
   if (cause.statusCode === 404) {
     return { ...result, error: new TRPCError({ code: "NOT_FOUND", message: "Resource not found or not accessible. This can happen if you switched domains in another tab.", cause }) }
   }
   ```
   Closes finding #4 (was 82/100).

**Untouched since version 1** (same files, same code): `__root.tsx`, `$flavorId.tsx`, `packages/signal-openstack/src/index.ts` — byte-for-byte identical to commit `c44278f3`.

## What was done (current for v2, unchanged in substance)

Closes #1128: if the user opens a second tab with a different domain/project, the first tab keeps working with the old session cookie, which on the next request no longer matches the current scope on the backend. The PR centralizes turning OpenStack API errors into meaningful tRPC codes on the server (`openstackErrorMiddleware` in `trpc.ts`, applied to `publicProcedure` and, transitively, to the whole API) and shows a friendly screen via Juno's `Status` on the client (`$projectId.tsx`) instead of crashing. Along the way it deletes `resolveProjectScope.ts` (which checked the rescope result against the actual project) and `StatusError.tsx` (a custom error screen component, replaced by `Status` from `@cloudoperators/juno-ui-components@9.4.0`).

## What it affects

Still current: `openstackErrorMiddleware` applies to the whole API repo-wide via `publicProcedure`, not only to the rescope flow. It was confirmed (see v1 of the report) that this doesn't lead to double error handling in `imageHelpers.ts`/`swiftHelpers.ts` — their `mapErrorResponseToTRPCError` doesn't set `cause`, so `cause instanceof SignalOpenstackApiError` is false for them. The `SignalOpenstackApiError` value export and the removal of `resolveProjectScope`/`StatusError` are unchanged; for details see v1 (preserved in the file history).

## Review

**Found in version 1 (confidence ≥ 80) — all 4 closed in this version:**

1. ~~`sessionRouter.ts:41` — no `null` check, a failed rescope is silently reported as success~~ (was 95/100) — **closed**, see "What changed" item 1.
2. ~~`context.ts` — concurrent requests lose the rescope error status~~ (was 90/100) — **closed**, see item 2.
3. ~~`$projectId.tsx` — `UNAUTHORIZED` always shows the domain-switch narrative, even when the session has actually expired~~ (was 85/100) — **closed**, see item 3.
4. ~~`trpc.ts` — 400 is blanket-mapped to `NOT_FOUND`~~ (was 82/100) — **closed**, see item 4.

**New in this version (confidence ≥ 80): none found.**

**Also noticed (confidence 50-79, below the inclusion threshold):**
- **[65]** `sessionRouter.ts` case `"unscoped"` (lines 76-81) still has no result check: `await ctx.rescopeSession({})` is called, but the return value isn't stored or checked anywhere — the mutation unconditionally returns `{project: null, domain: null}` regardless of whether the rescope succeeded. The same category of problem as the closed finding #1, but for the `unscoped` branch. Confidence is lowered relative to what was found earlier for `domain`/`project`, because `git grep` over the head commit finds no client call of `setCurrentScope` with `type: "unscoped"` — the path exists in the router but is currently unreachable from any known UI scenario, so there is no real user impact today.
- **[70]** The Copilot comment on `$projectId.tsx:63` about parallel execution of child route loaders in TanStack Router (the parent's friendly screen doesn't stop child scoped requests) — unchanged since version 1, not addressed in this update.
- **[55]** The missing "Back" button in `PageNotFound` (`__root.tsx`) and the 404 branch of `ProjectErrorComponent` (`$projectId.tsx`) after migrating to `Status`, even though `$flavorId.tsx` kept the button in the same PR — unchanged since version 1, not addressed.
- **[15, rejected]** The CodeRabbit comment on `trpc.ts:71` (current head commit `6c2fedef`), repeating the claim from version 1 about "raw cause.message reaches the UI" — re-checked against the current code: the `INTERNAL_SERVER_ERROR` fallback branch (`trpc.ts:64-71`) still uses the static string `"An unexpected OpenStack error occurred"`; `cause.message` is not used as the `message` value anywhere. This looks like a stuck/inaccurate templated bot comment not tied to the actual content of the line — the same conclusion as in version 1.

## What was done well

All 4 findings were fixed with targeted, minimal commits (not by rewriting from scratch), with the accompanying test updated where needed (`sessionRouter.test.ts`). The comment in `context.ts` about "Prevent unhandled rejection" became more precise rather than simply being deleted — the fix didn't just remove the outward symptoms but actually corrected the semantics of two different promises.

---
Analyzed: 2026-08-27 (v1: commit `c44278f3`, v2: commit `6c2fedef`)
