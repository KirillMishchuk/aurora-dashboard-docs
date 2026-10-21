---
type: pr-report
date: 2026-09-16
status: merged
pr: [1304]
author: vlad-schur-external-sap
branch: vlad-centralized-error-handling
---
# PR #1304: feat(dashboard): centralize client error handling

**Author:** vlad-schur-external-sap · **Status:** merged 2026-09-17 (created 2026-09-15)
**Branches:** `vlad-centralized-error-handling` → `main` · **Files:** 94 (+837/-527)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1304

## What was done

A large (94 files) refactoring of client-side error handling around Epic #1055, with no server changes. Three layers, per the PR description: **global** (expired token and the like — already existed), **service-level** (a non-existent route such as `netrowk/floatingips`) and **$id-level** (a non-existent specific resource: flavor/image/floating IP/security group/storage container).

**1. New shared components** (`client/components/Errors/`, renamed from the singular `Error/`):
- `RouteError` (renamed, no functional changes, only a doc comment added) — a full-screen error outside the layout (expired session, etc.); it already existed.
- `RouteIdLevelDefaultError` (new) — a resource error **inside** the layout (sidebar/header stay), a wrapper over `<Status code={404} status="error">`, with a default title/text/"Go to Project Home" button that can be overridden via props.
- `ServiceLevelDefaultError` (new) — the equivalent for an entirely non-existent route, registered as the router's `defaultNotFoundComponent` (`router.ts:14`).

**2. Five routes got their own `errorComponent`** (they had none before): `compute/flavors/$flavorId.tsx`, `compute/images/$imageId.tsx`, `network/floatingips.tsx`, `network/securitygroups.tsx`, `storage/$provider/$storageType/$containerName/objects/index.tsx` (here also a `notFoundComponent`; it used to be `<p>Storage container not found</p>`). All five are wrappers rendering `RouteIdLevelDefaultError` with a "Back to `<section>`" button. `images/$imageId.tsx` also manually uses `RouteIdLevelDefaultError`/its own `ImageErrorComponent` in the component's own `status === "error"` / `!image` branches (data from `useQuery`, separate from the router's `errorComponent`).

**3. Mechanical replacement of `Spinner`/`Message` with `<Status/>`** in ~50 modals (Delete/Empty/Move/Copy/Edit — Ceph Buckets/Objects, Swift Containers/Objects, Flavors, Images, Security Groups): `<Spinner/>` + text → `<Status status="progress" title=.../>`, `<Message variant="error">` → `<Status status="error" title=... body=.../>`, `variant="warning"` → `status="empty"`. The semantics are preserved 1:1 everywhere; along the way, a couple of places where the spinner and the error text could render at the same time were fixed (see "How it is implemented").

**4.** The `en`/`de` `messages.po` locales are synchronized (91/90 lines changed — new Status titles, removed inline spinner texts).

## How it is implemented

### New primitives (`client/components/Errors/`)

`RouteIdLevelDefaultError.tsx` (new file, 44 lines):

```tsx
export const RouteIdLevelDefaultError = ({ errorTitle, errorDescription, action }: RouteIdLevelDefaultErrorProps) => {
  const { t } = useLingui()
  const navigate = useNavigate()
  const { projectId } = useParams({ strict: false })
  ...
  return (
    <Status
      code={404}
      status="error"
      title={errorTitle || t`Resource Not Found`}
      body={errorDescription || t`The Resource you are looking for does not exist or is not accessible.`}
      action={action ?? (<Button variant="primary" onClick={navigateToProjectId}>{t`Go to Project Home`}</Button>)}
    />
  )
}
```

`code={404}` and both texts are hardcoded defaults, overridden only by explicitly passed `errorTitle`/`errorDescription`/`action`. This matters for "What it affects" below: wherever this wrapper is registered as a route's `errorComponent:` without passing these props, the component shows a static 404 regardless of the actual cause of failure.

### Five new `errorComponent`s

The pattern is the same in all five places — for example `compute/flavors/$flavorId.tsx:25-44`:

```tsx
function FlavorErrorComponent() {
  const { t } = useLingui()
  const navigate = useNavigate()
  const { projectId } = Route.useParams()

  return (
    <RouteIdLevelDefaultError
      action={
        <Button variant="primary" onClick={() => navigate({ to: "/projects/$projectId/compute/flavors", params: { projectId } })}>
          {t`Back to Flavors`}
        </Button>
      }
    />
  )
}
...
export const Route = createFileRoute(...)({
  ...
  errorComponent: FlavorErrorComponent,
})
```

Identical in `compute/images/$imageId.tsx:41-60` (`ImageErrorComponent`), `network/floatingips.tsx:6-23` (`FloatingIpsErrorComponent`), `network/securitygroups.tsx:6-23` (`SecurityGroupsErrorComponent`), `storage/.../objects/index.tsx:12-30` (`ObjectStorageErrorComponent`, assigned to both `errorComponent` and `notFoundComponent`).

In all five cases the function is declared **without parameters** — none of them accepts `error`. Separately, `images/$imageId.tsx:325-336` shows the correct pattern for a **different** error source — the component's own `useQuery` state (not the router's `errorComponent`):

```tsx
if (status === "error") {
  const errorMessage = error?.message || t`Unknown error`
  return (
    <RouteIdLevelDefaultError
      errorTitle={t`Error loading image`}
      errorDescription={errorMessage}
      action={<Button onClick={handleBack} variant="primary"><Trans>Back to Images</Trans></Button>}
    />
  )
}
```

Here the actual error text is passed explicitly — in contrast to `errorComponent: ImageErrorComponent`, which calls the same wrapper without passing a single prop. There is no test for this discrepancy — see "Review".

### Spinner/Message → Status (example)

`storage/-components/Swift/Objects/DeleteObjectModal.tsx:134-152` — this also fixes an ordering in which a metadata loading error could render at the same time as the `isLoading`/`isPending` state (an `if/else if metadataError` structure instead of a separate `{metadataError && (...)}` block before the main tree):

```tsx
{isPending ? (
  <Status status="progress" title={t`Deleting...`} className="mt-0" />
) : isLoading ? (
  <Status status="progress" title={t`Loading object info...`} className="mt-0" />
) : metadataError ? (
  <Status status="error" title={t`Failed to load object metadata`} body={metadataErrorMessage} className="mt-0" />
) : (
  ...
)}
```

The pattern is identical in all ~50 affected modals — a mechanical, consistent replacement, spot-checked (Ceph `DeleteBucketPolicyModal`, `DeleteCorsRuleModal`; Swift `DeleteObjectModal`, `CopyObjectModal`; Security Groups `AddRuleModal`, `CreateSecurityGroupModal`, `EditSecurityGroupModal`) — semantics carried over 1:1 everywhere, no findings.

## What it affects

**`errorComponent` ignores the passed `error` in all five new places — confirmed by the types.** `@tanstack/router-core@1.171.15` (pinned in the project, `node_modules/.pnpm/@tanstack+router-core@1.171.15/.../route.d.ts:432`) types the `errorComponent` props as `ErrorComponentProps<TError = Error> = { error: TError; info?; reset: () => void }` — i.e. the router really does pass `error` to the component. None of `FlavorErrorComponent`, `ImageErrorComponent`, `FloatingIpsErrorComponent`, `SecurityGroupsErrorComponent`, `ObjectStorageErrorComponent` declares parameters or reads `error` — the types allow this (structural compatibility with missing props), so `typecheck`/CI won't catch it. See "Review".

**The `Error/` → `Errors/` rename is clean in itself** (checked: across the whole tree at the PR's head commit no references to the singular `components/Error/` remain), **but it directly conflicts with the user's current uncommitted branch** `kiryl-storage-type-404-1081`: its working tree contains new files `packages/aurora/src/client/components/Error/RouteNotFound.tsx` and `RouteNotFound.test.tsx` — in the **same** directory that this PR renames. If #1304 is merged first, that branch will, on rebase/merge, end up with a non-existent (renamed) directory under its new files; if the other way round, the rename will have to be repeated manually for the files from #1081.

**The same file `storage/.../objects/index.tsx` is simultaneously being rewritten in the uncommitted branch `kiryl-storage-type-404-1081`** (issue #1081) — following a completely different scheme: there it is `notFound({ data: { reason } })` with different messages for `provider-not-found`/`storage-type-mismatch` (see the plan [`DOCS/plans/2026-09-14-storage-type-404-issue-1081.md`](../../plans/2026-09-14-storage-type-404-issue-1081.md)), whereas #1304 here simply puts the same `ObjectStorageErrorComponent` on both (`notFoundComponent`/`errorComponent`) without distinguishing the cause. Both PRs touch the same route with incompatible designs — whichever order they are merged in, a manual reconciliation will be needed.

**`errorComponent` coverage is uneven between Network and Compute.** For Network (`floatingips.tsx`, `securitygroups.tsx`) the new `errorComponent` is placed on the section's **parent layout route** — so it catches errors from both the list and the details page (`floatingips/$floatingIpId/index.tsx`, `securitygroups/$securityGroupId/index.tsx` via `Outlet`). For Compute, the equivalent layout routes (`compute/flavors.tsx`, `compute/images.tsx`) are not touched by this PR at all — `errorComponent` exists only on the details page itself (`$flavorId.tsx`/`$imageId.tsx`), and on a loading error the list (`flavors/index.tsx`/`images/index.tsx`) will still bubble up to the full-screen `ProjectErrorComponent` at the `$projectId.tsx` level. Not a bug (the same behaviour as everywhere before the PR), but the claimed coverage of "Compute, Network and Object Storage" is in fact incomplete and asymmetric between sections.

## Review

**[90]** All five new `errorComponent`s (`FlavorErrorComponent`, `ImageErrorComponent`, `FloatingIpsErrorComponent`, `SecurityGroupsErrorComponent`, `ObjectStorageErrorComponent`) discard the actual `error` passed by the router and render a hardcoded `RouteIdLevelDefaultError` without `errorTitle`/`errorDescription` — the 404 code and the text "Resource Not Found / ...does not exist or is not accessible" are shown **for any** thrown error, not only for a genuine "not found". A concrete reproducible case: `compute/images/$imageId.tsx` `beforeLoad` (not changed by this PR, but falling under the new `errorComponent: ImageErrorComponent`) calls `trpcClient?.auth.getAvailableServices.query()` without try/catch — a network failure or BFF error here will show the user "Resource Not Found" instead of the actual cause. The contrast in the same file: its own manual `status === "error"` branch (lines 325-336) correctly passes `errorMessage` via `errorTitle`/`errorDescription` — i.e. the authors knew about the component's parameters but forgot to pass them specifically in the router's `errorComponent`. None of the five wrapper components is covered by a test that throws an error through the route itself and checks the rendered text — only the primitives `RouteIdLevelDefaultError`/`ServiceLevelDefaultError` are tested directly, with hand-specified props; the "real error → `errorComponent` → screen" path is never reproduced in this PR's tests. This directly contradicts the PR's stated goal of "Improved error messages".

Below the threshold (not reported, but worth keeping in mind): uneven `errorComponent` coverage between Network (list+details) and Compute (details only) — an architectural decision, not a regression, but presented as a single policy for all three domains (70/100).

---
Analyzed: 2026-09-16 · commit `aac6f9ed9`
