---
type: pr-report
date: 2026-09-04
status: merged
pr: [1268]
author: taymoor89
branch: 1253-change-additional-services-integration
---
# PR #1268: feat(aurora): replace route-injection with standalone extension sub-app pattern

**Author:** taymoor89 · **Status:** 2026-09-03 → merged 2026-09-04 (approved andypf 2026-09-04)
**Branches:** `1253-change-additional-services-integration` → `main` · **Files:** 18 (+305/-87)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1268

## What was done

A change in how third-party (SCI) services integrate into Aurora. Before: the consumer handed ready-made TanStack routes to OSS, and they were **spliced into the OSS route tree** (`AdditionalProjectService.routes: AnyRoute` + an exported `servicesRoute` as the parent + a shared `ProjectId` context). Now: the consumer registers a **self-contained React component**, which OSS mounts under `/projects/$projectId/services/$serviceType/**`; the component spins up **its own** `RouterProvider` with a `basepath` and receives host data through an extensible `context` object rather than through a shared React context.

Along the way the vocabulary was unified: everything called an "additional project service" became a "service extension" (`AdditionalProjectService` → `ServiceExtension`, prop `additionalProjectServices` → `serviceExtensions`).

Key point about the history: the pattern being replaced lived for **11 days** — route-injection was introduced by the same author in `a9c257a1` (#1189, 2026-08-24), and its changeset explicitly sold the mechanism as "pass your service definitions via the `additionalProjectServices` prop… to plug in client-side routes". The trigger for the reversal was a comment in issue #1102 ("Reopening this task and converting this to an epic in order to change the approach how we handle breadcrumbs and additional services integration"), from which #1253 grew. This is not an external requirement but a quick internal reconsideration of a design that had just shipped — when reading the knowledge base it is worth remembering that the section on route-injection became outdated a week and a half after it appeared.

## How it is implemented

**Registration contract** (`packages/aurora/src/client/AuroraApp.tsx:61-100`). Three new types instead of one: `ServiceExtensionContext` (currently `{ projectId }`, but extensible — the whole point is that future fields like `domainId`/`scope` won't change the component's signature), `ServiceExtensionProps = { basePath, context }`, and `ServiceExtension` itself, where `routes` is now replaced by `component`:

```ts
export type ServiceExtension = {
  /** OpenStack catalog service type, e.g. `"pca"`. */
  serviceType: string
  /** OpenStack catalog service name, e.g. `"clavis"`. */
  serviceName: string
  /** Nav item and service card label. */
  label: string
  /**
   * The React component to render at `/projects/$projectId/services/$serviceType/**`.
   * Receives `basePath` (the URL prefix) and `context` (host data). Create your own RouterProvider
   * inside this component using `basePath` as the `basepath` prop and `context` as the router context.
   *
   * Note: this is a self-contained sub-app. Host slots (see `Slots`) are not injected into it, so the
   * extension owns its own header/actions (e.g. via the re-exported `PageContentHeader` `actions` prop).
   */
  component: FC<ServiceExtensionProps>
}
```
— `AuroraApp.tsx:84-100`

The stated "host slots are not injected into the sub-app" is not just a claim in the docs: `ServiceExtensionContext` has no `slots` field, and the mounting component passes out only `{ projectId }`, so structurally the extension has no path to the slots.

**Mounting.** The entire decoupling lives in a single 23-line component:

```tsx
export function ServiceExtensionMount() {
  const { projectId, serviceType } = useParams({ strict: false }) as { projectId: string; serviceType: string }
  const { serviceExtensions } = useRouteContext({ strict: false })
  const extension = serviceExtensions?.find((s) => s.serviceType === serviceType)

  // Memoize so the object reference stays stable across renders and the extension's own
  // createRouter (seeded with this context) is not recreated on every render.
  const context = useMemo<ServiceExtensionContext>(() => ({ projectId }), [projectId])

  if (!extension?.component) return null

  const basePath = `/projects/${projectId}/services/${serviceType}`
  const ServiceComponent = extension.component
  return <ServiceComponent basePath={basePath} context={context} />
}
```
— `.../services/$serviceType/-components/ServiceExtensionMount.tsx:9-23`

**Three new routes with separated roles.** Mounting lives on the **layout** route, while `index` and the splat exist only for URL matching — this is a deliberate decision, and it is documented in the code:

```tsx
// Render the extension mount at the layout level so it stays mounted across all
// /services/$serviceType/** navigation. The index and splat child routes exist only to
// match the URL (so deep links don't 404); if the mount rendered in those children instead,
// navigating between them would tear down and rebuild the extension's own RouterProvider,
// losing its state, scroll position, and in-flight fetches.
export const Route = createFileRoute("/_auth/projects/$projectId/services/$serviceType")({
  staticData: { section: "services" },
  component: ServiceExtensionMount,
})
```
— `.../services/$serviceType.tsx:4-12` (both children are `component: () => null`: `$serviceType/index.tsx:6`, `$serviceType/$.tsx:7`)

Verified separately (against `@tanstack/react-router@1.168.22`): the concern "extension A stays mounted while the URL already points to B" does not materialize — `ServiceExtensionMount` is not unmounted when `serviceType` changes, but it substitutes a different component function, and React correctly unmounts the old subtree based on the element type difference.

**Public surface** (`packages/aurora/src/client/index.ts`). Removed: `AdditionalProjectService`, `useProjectId`, `servicesRoute`. Added: `ServiceExtension`, `ServiceExtensionProps`, `ServiceExtensionContext`, and `PageContentHeader` (a renamed re-export of `ContentHeader`, so that an extension can render an OSS-styled header with its own actions). Renaming on export is already an established practice in the repo (cf. `ObjectBrowserView as CephObjects`).

**Navigation.** `buildNavSections` can no longer navigate via `module.routes.fullPath` (there are no routes anymore) and switches to a static path with params; active-item highlighting gained a fallback to the URL param, because the mount route has no static `service`:

```ts
const activeService = activeRouteInfo?.service ?? serviceType ?? null
```
— `packages/aurora/src/client/routes/_auth/projects/-components/SideNavBar.tsx:38`

**Breadcrumbs.** On `/services/$serviceType/**` OSS does not show a section breadcrumb (same as in compute/network/storage), and everything below the service level is published by the extension itself via `usePushBreadcrumbs`. This is a direct application of the mechanism built two days earlier in #1254 (`0cadedd9`), not a conflict with it: `useBreadcrumbs.ts` was already documented back then as suitable for embedded sub-apps, and `Breadcrumbs.tsx` as merging `BreadcrumbExtensionContext`.

**Minor hardening.** `EMPTY_SERVICE_EXTENSIONS` is declared at module level (`App.tsx:39`) and substituted when the prop is not passed (`App.tsx:108`), so as not to break `buildNavSections` memoization with a new `[]` on every render. Verified: the constant really is at module level, and the downstream memoization depends on the `serviceExtensions` reference itself, not on the wrapping context object, so the hardening works.

## What it affects

**Nothing breaks inside the monorepo — and this was verified.** `additionalProjectServices`, `AdditionalProjectService` and `ProjectIdContext` do not occur in any file at `4df9ccea`; `apps/dashboard` did not use these APIs at all, and its dependency is `workspace:*` (`apps/dashboard/package.json:20`), so the bump type is irrelevant to it. `useProjectId` remains alive and actively used **inside** the package (117 files) — it was removed from the public index but not deleted, so internal consumers are unaffected.

**The real risk is only for external consumers.** The package is published (`publishConfig.access: "public"`, version 1.1.0), and this is a classic breaking contract change: the SCI dashboard has to move in lockstep. Coordination of that move is **not tracked anywhere** — the only mention in the PR is the "Rebuild and install OSS into the SCI dashboard" step in the testing instructions; no linked issue, no checklist.

**The bump type — `minor` with six documented breaking changes — matches the project's practice rather than violating it.** This is worth recording, because it looks like a mistake but isn't one: in `packages/aurora/CHANGELOG.md:6-9` the removal of the public `getAuthToken` with a migration note shipped as minor (commit `8e99f074` explicitly says in its message "Upgraded to minor version due to breaking API change"); `.changeset/tempurl-restrictions.md` — minor for a breaking TempURL restriction; `.changeset/brave-weeks-warn.md` — even `patch` with a "Breaking change for API consumers" section. The only major in the history (1.0.0, `2c7bd0e7`) was a deliberate exception. `docs/semantic_release.md`, which talks about a major on `BREAKING CHANGE:`, is a dead document: there is neither `.releaserc.js` nor a semantic-release workflow in the repo; releases go through the changesets action.

**The tests were not rewritten for the new behavior — they were mechanically renamed.** `buildNavSections.test.ts` (+4/-5): only `AdditionalProjectService`→`ServiceExtension` and `routes: {} as unknown as AnyRoute`→`component: () => null`; the assertions themselves are untouched. `useBreadcrumbs.test.tsx` (+1/-1): a field rename in the `useRouteContext` mock, which the hook itself never calls (it works via `useMatches`/`DynamicBreadcrumbContext`) — a dead stub inherited from #1254. That is, the new behavior (mounting, splat, highlighting fallback, behavior for an unregistered type) is not covered by any test.

## Review

Five parallel agents (conventions/versioning, bug scan, history, past feedback, conformance to docs and comments) plus confidence scoring. One finding passed the ≥80 threshold; three scored 75 and are listed in a separate block, because in substance they are more useful than their score suggests.

### [100] The changeset publishes three nonexistent breaking changes

`.changeset/extension-sub-app-pattern.md` is not a PR description but consumer-facing release notes: the release action copies the changeset text verbatim into `packages/aurora/CHANGELOG.md`. Three of the six declared breaking changes do not match reality:

| Claim in the changeset | Fact |
| --- | --- |
| "`ProjectIdContext` export removed" (line 11) | No export, type or file with that name has **ever existed** in the repository history: `git log --all -S'ProjectIdContext'` returns no commits except on the PR's own branch |
| "`AuroraAppProps.router` prop removed" (line 13) | `AuroraAppProps` never had a `router` field in any commit, including the base `273aebbe` (it only has `theme`, `bffEndpoint`, `onThemeChange`, `slots`, `appName`, `onTrackEvent`, `enabledServices`, `additionalProjectServices`) |
| `usePushBreadcrumbs` in the "New exports" section (line 19) | Was already exported before this PR — `git show 273aebbe:packages/aurora/src/client/index.ts:25`, added in #1254 |

Plus a milder wording inaccuracy: "`ServiceExtensionProps` reshaped from `{ basePath, projectId }` to `{ basePath, context }`" (line 10) — no type with that name existed before this PR at all; it is introduced right here, so "reshaped" is misleading.

Practical harm: an external consumer reading the CHANGELOG will search their code for `ProjectIdContext` and a `router` prop that they don't have and never could have had, and will at the same time get a wrong picture of what is actually new. Confirmed independently by two agents and re-checked manually via `git log --all -S` and the base blobs. Fixable before merge — by editing the changeset file.

### Below threshold [75], but this is exactly what is worth fixing in the code

- **A blank page instead of a 404 for an unknown `serviceType`.** `$serviceType` + the `$` splat together match **any** URL under `/services/**`, and `ServiceExtensionMount.tsx:18` returns `null` on a lookup miss. Result: a stale link, a typo, or a service type that exists in the OpenStack catalog but is not registered as an extension yields a completely empty content area inside the normal project shell — no error, no redirect, no `notFoundComponent: PageNotFound` (`routes/__root.tsx:29`), which before this PR is exactly what fired, because an unregistered route simply wasn't in the tree. Cf. the analogous dynamic segment in storage: `storage/$provider/$storageType/index.tsx` validates it via `checkServiceAvailability` and always throws a `redirect()` to a meaningful fallback. **Copilot left this same comment on the PR itself, and it went unanswered and unfixed** — while its neighboring comment (about duplicate `serviceType`s) was deliberately rejected by the author with an explanation ("OSS `aurora` shouldn't second-guess consumers intent"), so the silence here looks like an oversight rather than a decision. The approve from andypf ("Looks good to me, no regressions so far") does not resolve this point.
- **"No user-visible change" in the PR description contradicts its own changeset.** The statement "N/A (no user-visible change; projectId resolves identically inside mounted extensions)" is true about `projectId`, but the changeset itself documents that the section breadcrumb disappears on `/services/**`, and that breadcrumbs of routes inside the extension's own router are no longer visible to OSS's `useMatches()`-based breadcrumb bar until the extension calls `usePushBreadcrumbs` at every level. A breadcrumb that used to render and now doesn't is a visible change.
- **A dead `servicesRoute` remains in the sources.** The public re-export was removed and route-injection deleted, but the file itself still exports the alias: `packages/aurora/src/client/routes/_auth/projects/$projectId/services.tsx:7` → `export { Route as servicesRoute }`. An artifact of exactly the mechanism the PR replaces.

### Below threshold [50], as context

- `$serviceType.tsx:10` writes `staticData: { section: "services" }` without `satisfies RouteInfo`, whereas comparable routes in the repo consistently include that assertion (`_auth.tsx:8-10`, `storage/$provider/$storageType.tsx:7-10`). It doesn't break typing.
- The new public export `PageContentHeader` is not mentioned even once in `packages/aurora/README.md`, even though the PR rewrites the "Service extensions" section of that README, and the export was added specifically for extension authors. The rest of the section was checked against the code at `4df9ccea` and matches exactly — names, props, type shapes, and both examples with `createRouter({ routeTree, context })`/`useRouteContext`.
- Going beyond the scope of issue #1253: the issue only asks to "render consumer supplied project services as isolated components"; removing `useProjectId`/`servicesRoute` from the public API is not there. As a consequence of the new pattern this is defensible, but formally it is a scope expansion, and the reviewers did not discuss it.

---
Analyzed: 2026-09-04 · commit `4df9ccea`
