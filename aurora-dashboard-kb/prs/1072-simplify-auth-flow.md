---
type: pr-report
date: 2026-07-17
status: merged
pr: [1072]
author: andypf
branch: andypf/auth
---
# PR #1072: refactor(aurora): simplify auth flow and improve session handling

**Author:** andypf · **Status:** merged 2026-07-15
**Branches:** `andypf/auth` → `main` · **Files:** 14 (+575/-727)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1072

## What was done

A complete refactoring of the client-side auth flow in the `aurora` package: the authorization logic moved out of the `/` route (the file route `routes/index.tsx`, which previously housed both the `beforeLoad` guard and the entire login form inline) into `AuthProvider` and a new dedicated `LoginForm` component. The goal is less state, fewer re-renders, and taking advantage of React 19 (dropping `useCallback`, since it is no longer needed for memoization).

The changes fall into four related pieces:

1. **`AuthProvider` became the source of truth for the session.** Previously `login`/`logout` were just setters of local state, while the tRPC calls themselves (`createUserSession`, `terminateUserSession`, `getCurrentUserSession`) were scattered across components (`routes/index.tsx`, `UserMenu.tsx`). Now all three calls are encapsulated inside `AuthProvider`, and it exposes a simple contract: `login(credentials) → {success}`, `logout()`, `isLoading`, `error`.
2. **Session restore on mount.** A new `useEffect` in `AuthProvider` calls `getCurrentUserSession` on mount and restores `user`/`expiresAt` if the session is alive — this replaces the previous check that was done in the router's `beforeLoad`.
3. **Session expiry timer.** A separate `useEffect` computes `timeUntilExpiry` and on expiry clears the local state itself and redirects to `/`, saving the current URL in `sessionStorage` (`redirect=...`) so that after logging in again the user is returned to where they were.
4. **New `LoginForm`.** An uncontrolled form based on `FormData` (without `onChange` state for each field) — no more extra re-renders on every typed character.

## How it is implemented

**`AuthProvider` — contract and session restore** (`packages/aurora/src/client/store/AuthProvider.tsx:19-116`):

```ts
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expiresAt, setExpiresAt] = useState<string | null>(null)

  useEffect(() => {
    trpcClient.auth.getCurrentUserSession
      .query()
      .then((session) => {
        if (session) {
          setUser(session.user)
          setExpiresAt(session.expires_at)
        }
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Could not load session")
      })
      .finally(() => setIsLoading(false))
  }, [])
```

`getCurrentUserSession` is a `publicProcedure` that resolves with `null` if there is no session (`packages/aurora/src/server/Authentication/routers/sessionRouter.ts:12-15`); it does not reject in the normal "guest visiting for the first time" case. A rejection here is specifically an infrastructure failure (network, CSRF), not an ordinary "not logged in".

`AuthProvider` no longer takes `router` as a prop (previously — `{ children, router }: { ...; router: RouterNavigation }`) — redirects now go through `window.location.href` rather than `router.navigate()`/`router.invalidate()` (`AuthProvider.tsx:23-30`, the `redirectToLogin` function). Accordingly, in `App.tsx:93` the call was simplified from `<AuthProvider router={router}>` to `<AuthProvider>`.

**`LandingPage`** (the new name of the `/` route component, `packages/aurora/src/client/routes/index.tsx:18-49`) became thin: it gates rendering on `isLoading` (spinner), then either renders `<LoginForm />` or (if already authenticated) renders nothing and leaves via a `useEffect` redirect:

```tsx
function LandingPage() {
  const { isLoading, isAuthenticated } = useAuth()
  const { redirect: searchRedirect } = Route.useSearch()
  const navigate = useNavigate()

  useEffect(() => {
    if (isAuthenticated && !isLoading) {
      const target = isSafeRedirect(searchRedirect) ? searchRedirect : "/projects"
      navigate({ to: target, replace: true })
    }
  }, [isAuthenticated, isLoading, navigate, searchRedirect])

  if (isLoading) {
    return (<Stack className="fixed inset-0" distribution="center" alignment="center">...<Spinner .../></Stack>)
  }
  if (!isAuthenticated) {
    return <LoginForm />
  }
  return null // Redirecting...
}
```

Previously this same logic (redirecting already authenticated users) lived in the router's `beforeLoad` — it ran before the component rendered, at the router level, rather than after mount. Now `isLoading` is initially `true` (the state default in `AuthProvider`), so there is no "flash" of the login form for already authenticated users — just a spinner instead of an instant router redirect.

**New `LoginForm`** (`packages/aurora/src/client/components/Auth/LoginForm.tsx:1-55`) — an uncontrolled form based on `FormData`:

```tsx
<form onSubmit={(e) => {
  e.preventDefault()
  const formData = new FormData(e.currentTarget)
  login({
    domain: String(formData.get("domain") ?? ""),
    user: String(formData.get("user") ?? ""),
    password: String(formData.get("password") ?? ""),
  })
}}>
```

**`UserMenu`** (`packages/aurora/src/client/components/navigation/UserMenu.tsx`) lost its own `handleLogout` wrapper (it was: a direct call to `trpcClient.auth.terminateUserSession.mutate()` + try/catch + its own `isLoading` state) — now it is simply `onClick={logout}`, and `isLoading`/`isAuthenticated`/`user`/`expiresAt` come directly from `useAuth()`.

## What it affects

`useAuth`/`AuthProvider` are exported from the package's public entry point (`packages/aurora/src/client/index.ts:19`), so they are part of the public API of `@cobaltcore-dev/aurora`, not just an internal detail. A check of consumers across the whole monorepo at commit `710e506` (`git grep -n "useAuth\|AuthProvider"`) showed:

- Inside `aurora`, the following depend on `useAuth()`: `App.tsx`, `LoginForm.tsx`, `UserMenu.tsx`, `hooks/useDomainId.ts`, `hooks/useScope.ts`, `routes/_auth.tsx`, `routes/_auth/aurora.tsx`, `routes/index.tsx` — all of them use only `isAuthenticated`/`user`/`isLoading`/`logout`; none called `login()` with the old `(user, expires_at)` signature, so changing the `login` signature to `(credentials) => {success}` left no broken calls.
- `routes/_auth.tsx` (the private route guard) reads only `context.auth?.isAuthenticated` — it is not affected by the contract.
- In `apps/` (the package's consumer applications) no direct references to `useAuth`/`AuthProvider`/`login(` were found — they get the auth functionality wholesale via the mounted `<App>` from the package, so the refactoring is transparent to them at the API level.
- The tests (`AuthProvider.test.tsx`, `MainNavigation.test.tsx`, `useScope.test.ts`, the new `LoginForm.test.tsx`) were updated consistently with the new shape of `AuthContext` (`isLoading`/`error` added to the mocks).

A more serious side effect — this PR silently removed the `slots.login` customization point (see the "Review" section below): the check `git grep -n "slots.*login" 710e506` across the whole repository at the PR's head commit finds nothing — the slot is declared in the `Slots` type (`AuroraApp.tsx`) but is not read anywhere. This is already documented in the knowledge base's main log: the slot was restored in PR #1079 (see the 2026-07-16 entry in the knowledge base's [`README.md`](../README.md#update-log) log; there is no separate report for #1079).

## Review

The pipeline (5 parallel agents: CLAUDE.md compliance, quick bug scan, historical context via git blame/log, previous PR comments on these files, compliance with code comments) plus independent confidence scoring of each finding produced one finding with confidence ≥80:

1. **The `slots.login` customization point was silently removed** (confidence 90) — `packages/aurora/src/client/routes/index.tsx`. The old code rendered a custom login component via `<Slot component={slots.login} .../>` if the package consumer had configured one (added deliberately in PR #970 — specifically for OIDC environments where a password form is not needed). The new `LandingPage` does not read `Route.useRouteContext().slots` at all and always renders a hardcoded `<LoginForm />`. The `Slots.login` prop remained in the type but became dead. The PR description does not mention this removal — it looks like an unintended side effect of rewriting the file rather than a deliberate decision. Already fixed in PR #1079.

Two more findings were confirmed independently by several agents and by git history (the PRs that originally introduced this behaviour), but scored 75 — just below the ≥80 inclusion threshold; I list them as "also noted", since this is documentation, not a merge gate:

- **Localization of the login error was lost** (confidence 75) — `AuthProvider.login()` now does `setError(err.message)` with the raw error text from tRPC, without an `isTRPCUnauthorized()` check and without translation via `useErrorTranslation`/`t`. The `isTRPCUnauthorized` utility (`packages/aurora/src/client/utils/trpcErrors.ts:4`) remains in the codebase but is unused. This is the same behaviour that was explicitly added in PR #972 after a CodeRabbit review comment that German users see raw English error text when entering invalid login credentials.
- **Invalid `autoComplete` tokens in `LoginForm`** (confidence 75) — the new form uses `autoComplete="domain"`, `autoComplete="user"`, `autoComplete="password"`, none of which is a valid WHATWG specification token (the valid ones are `"username"`, `"current-password"`). The old form used `autoComplete="username"` / `autoComplete="current-password"`, added deliberately in PR #1032 for autofill from password managers — this no longer works.

Also checked and rejected as false positive/intentional decision: changing the logout redirect from `router.navigate()`/`router.invalidate()` to `window.location.href` (confidence 30 — fits the PR's stated goal of "simpler and more reliable"; a full reload on logout is common practice for BFF applications); the hypothesis of a login form "flash" for authenticated users due to removing the router's `beforeLoad` guard (confidence 20 — not confirmed: `isLoading` gates rendering with a spinner before the `isAuthenticated` check).

**What was done well:** `SessionExpirationTimer` became a pure display component without the logout side effect — this eliminates the race that was pointed out earlier in the review of PR #1046 (a double session invalidation call from independent timers). The tests were rewritten consistently with the new `AuthContext` contract rather than just patched in spots.

---
Analyzed: 2026-07-17 · commit `710e506`
