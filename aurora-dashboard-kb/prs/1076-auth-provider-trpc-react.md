---
type: pr-report
date: 2026-07-20
status: open
pr: [1076]
author: andypf
branch: andypf/refactor-auth-provider-to-trpc-react
---
# PR #1076: refactor(aurora): migrate AuthProvider to tRPC React Query hooks

**Author:** andypf · **Status:** open, draft (not merged)
**Branches:** `andypf/refactor-auth-provider-to-trpc-react` → `main` · **Files:** 6 meaningful (+~230/-~380, excluding changesets/CHANGELOG/locale noise, see below)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1076

> ⚠️ The PR is open as a **draft** and not merged. The `baseRefOid` returned by `gh` points to commit `3e8f1bf` (#1074), which `main` has since moved past (`main` is now at `28cc3ff`, including #1079/#1080). Because of this, `gh pr diff` mixes in noisy reverts of `CHANGELOG.md`/`package.json`/locales — the report below is built on `git diff <baseRefOid>..<headRefOid>`, which gives a clean diff of only the files this PR actually touched.

## What was done

The PR continues the auth-flow refactoring started in PR #1072 (see [1072-simplify-auth-flow.md](./1072-simplify-auth-flow.md)): `AuthProvider` is moved from vanilla `trpcClient` calls + manual `useState`/`useEffect` to `trpcReact` hooks (`useQuery`/`useMutation`), i.e. to the same pattern already used in the rest of the package's client code. Besides `AuthProvider` itself, the PR includes two small layout fixes (centering `LoginForm` and the spinner on `/projects`) and correspondingly rewrites three test files for the new mocking pattern.

## How it is implemented

**The session as a React Query query** (`packages/aurora/src/client/store/AuthProvider.tsx:19-32`):

```tsx
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const trpcUtils = trpcReact.useUtils()

  const sessionQuery = trpcReact.auth.getCurrentUserSession.useQuery(undefined, {
    staleTime: Infinity, // Session only changes via login/logout
    retry: false,
  })

  const user = sessionQuery.data?.user ?? null
  const expiresAt = sessionQuery.data?.expires_at
  const isInitialLoading = sessionQuery.isLoading
  const isRefetching = sessionQuery.isRefetching
  const error = sessionQuery.error?.message ?? null
```

Previously the session lived in four `useState`s and was loaded manually in a `useEffect` (see #1072). Now the source of truth is the React Query cache; `staleTime: Infinity` deliberately disables time-based background refetches (the session changes only via explicit `login`/`logout`), and `retry: false` keeps the previous "don't retry" behavior.

**Login/logout are mutations; the cache is updated manually** (`AuthProvider.tsx:68-93`):

```tsx
const loginMutation = trpcReact.auth.createUserSession.useMutation()

const login = async ({ domain, user, password }: { domain: string; user: string; password: string }) => {
  try {
    const tokenData = await loginMutation.mutateAsync({ domainName: domain, user, password })
    trpcUtils.auth.getCurrentUserSession.setData(undefined, tokenData)
    return { success: true }
  } catch {
    return { success: false }
  }
}

const logoutMutation = trpcReact.auth.terminateUserSession.useMutation()

const logout = async () => {
  try {
    await logoutMutation.mutateAsync()
  } catch {
    // Server-side termination failed, but we still clear local state
  }
  redirectToLogin(false)
}
```

After a successful login, the `getCurrentUserSession` cache is populated directly with the mutation result (`trpcUtils...setData`), without another trip to the server — saving one round-trip compared to invalidate+refetch. `logout` intentionally always clears local state and redirects, even if the server-side `terminateUserSession` failed — this is the same behavior as before the PR (see #1072), just moved onto the mutation.

**`redirectToLogin` no longer checks the path before building `returnUrl`** (`AuthProvider.tsx:34-47`):

```tsx
const redirectToLogin = (saveReturnUrl: boolean = false) => {
  const returnUrl = saveReturnUrl
    ? `/?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`
    : "/"

  if (window.location.pathname === "/") {
    // Already on login page - just clear session query, no redirect needed
    trpcUtils.auth.getCurrentUserSession.setData(undefined, undefined)
  } else {
    // Redirect triggers page reload which clears cache
    window.location.href = returnUrl
  }
}
```

If already on `/`, instead of `window.location.href` (which previously did nothing at all), the session cache is now explicitly cleared via `setData(undefined, undefined)` — otherwise, with `staleTime: Infinity`, stale `user`/`expiresAt` would keep lingering in the cache without a full page reload.

**A combined `isLoading` that does not account for logout** (`AuthProvider.tsx:95-96`, analyzed in detail in the "Review" section):

```tsx
// Combined loading state (initial load, during login, or refetching after login)
const combinedLoading = isInitialLoading || loginMutation.isPending || isRefetching
```

**Layout fixes**: `LoginForm.tsx:9` — the container changed from `<div className="mt-8 flex justify-center">` to `<Stack className="fixed inset-0 overflow-auto px-4 py-8" distribution="center" alignment="center">` (the form is now centered in the whole viewport, not just horizontally from the top of the page); `routes/_auth/projects/index.tsx:85` — the same for the Suspense fallback spinner on the project list page.

**Tests** (`AuthProvider.test.tsx`, `LoginForm.test.tsx`, `MainNavigation.test.tsx`) were rewritten from mocks of `trpcClient.auth.X.query/mutate` to mocks of `trpcReact.auth.X.useQuery/useMutation` + a `QueryClientProvider` wrapper. Along the way some behavioral checks were weakened or removed (for example, the login test no longer checks `result.current.isAuthenticated`/`user` after a successful `login()` — with a static `useQuery` mock, calling `trpcUtils.setData` is not reflected in the hook's returned data, so this check either wouldn't have worked or was removed outright as incompatible with the new mocking approach). This doesn't qualify as a standalone finding under the review rules (general test coverage quality is not a bug), but it explains why the regression from the "Review" section below went unnoticed by unit tests.

## What it affects

`AuthProvider`/`useAuth` are part of the package's public API (exported from `packages/aurora/src/client/index.ts`, see #1072). The `AuthContext` contract (`isAuthenticated`, `isLoading`, `error`, `user`, `expiresAt`, `login`, `logout`) does not change in shape — only what lies behind `isLoading` internally changes. Checking `useAuth()` consumers at the head commit (`git grep -n "useAuth()" 15f8590`) showed the same list as in #1072:

- **`UserMenu.tsx:14`** — reads `isLoading` to show `"Signing out…"` and disable the logout button while signing out. This is the only consumer for which the change in the `isLoading` implementation actually changes behavior (see the finding below) — the others read `isLoading` only to gate the first render (`LoginForm.tsx`, `routes/index.tsx`) or don't read it at all (`useDomainId.ts`, `useScope.ts`, `routes/_auth.tsx`, `routes/_auth/aurora.tsx`).
- `App.tsx:130` mounts `AuthProvider` inside the already existing `<QueryClientProvider>` (added in #1072) — the new `useQuery`/`useMutation` inside `AuthProvider` require no changes to the app's provider tree; there is no runtime crash risk.
- There are no direct references to `useAuth`/`AuthProvider` in `apps/dashboard` — consumers get auth functionality through the mounted `<App>`, so for them the refactor is transparent at the API level.
- `UserMenu.tsx` has no test file of its own (`git grep -l "UserMenu" -- '*.test.tsx'` — empty) — the regression below is not covered by tests either before or after the PR.

## Review

The pipeline (5 parallel agents: CLAUDE.md compliance, a quick bug scan, historical context from git blame/log, prior CodeRabbit/Copilot PR comments on this PR, conformance to code comments) plus independent confidence scoring produced one finding with confidence ≥80:

1. **The logout indicator in `UserMenu` no longer shows** (confidence 90) — `AuthProvider.tsx:96`, `UserMenu.tsx:33-38`. The combined `isLoading` is now computed as `isInitialLoading || loginMutation.isPending || isRefetching` — `logoutMutation.isPending` is not part of the formula. `UserMenu` relies specifically on `isLoading` to show `label={isLoading ? "Signing out…" : "Log Out"}` during sign-out and to disable the button (`disabled={isLoading}`). After this PR, the "Log Out" button stays enabled and doesn't change its text during the actual `terminateUserSession` network request — the user can click again while the request is still in flight. The comment above the line (`// Combined loading state (initial load, during login, or refetching after login)`) itself doesn't mention logout — this looks like an unintentional omission when moving state over from manual `useState`s (in the old version, `logout()` explicitly did `setIsLoading(true)` for the duration of the call, see the history in #1072). The "Signing out…" functionality was deliberately added in this very file in PR #1072 literally the day before ([`0021456`](https://github.com/cobaltcore-dev/aurora-dashboard/commit/0021456)) — so this is a silent regression of recently added, specifically manually tested UX behavior. Not covered by unit tests (`UserMenu.tsx` has no test file at all), so the regression won't surface in any existing run.

One more finding was confirmed independently (by historical context — it had already been raised by CodeRabbit on this very PR and was not fixed by the final commit `15f8590`, which is the head at the time of analysis), but given the likelihood of it actually triggering in production it only qualifies as "also noticed":

- **`setTimeout` overflow for long-lived sessions** (confidence 55) — `AuthProvider.tsx:50-66`. `setTimeout(handleExpiry, timeUntilExpiry)` uses `timeUntilExpiry` without an upper bound; `setTimeout` in JS stores the delay as a 32-bit integer (limit ≈ 24.8 days, 2 147 483 647 ms) — if `expiresAt` is further in the future, the timer overflows and fires `handleExpiry` synchronously (i.e. an instant logout) right after login. CodeRabbit raised this on the commit range `9297de8..15f8590` (the very one that went into the final `head`) with a ready-made fix (a recursive `setTimeout` capped at `MAX_TIMEOUT`) — the fix did not make it into the code. I lower it from a potential 75+ to 55 because the real Keystone token TTL in this project is typically measured in hours, not weeks — the bug is real and confirmed line by line, but the chance that a session lifetime in production will ever exceed ~25 days is low.

Also checked and rejected as false positives/intentional behavior: two later CodeRabbit comments on the final commit (`setData(undefined, undefined)` instead of `null` on logout at `/`, and the suggestion not to redirect when `terminateUserSession` fails) — both reproduce behavior that already existed before this PR (see #1072: "local state is cleared even if the server call failed") and are explicitly tested by the new test `"should clear session immediately if already expired"` (`AuthProvider.test.tsx:479-551`), i.e. this is a deliberate design, not a side effect of the refactoring (confidence 20).

**What was done well:** populating the `getCurrentUserSession` cache with the login mutation result instead of invalidate+refetch (`trpcUtils.auth.getCurrentUserSession.setData(undefined, tokenData)`) removes an extra round-trip to the server right after a successful sign-in — the first version of the refactoring (before this PR) didn't have this optimism.

---
Analyzed: 2026-07-20 · commit `15f8590`
