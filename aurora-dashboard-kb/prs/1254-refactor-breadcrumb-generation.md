---
type: pr-report
date: 2026-09-02
status: merged
pr: [1254]
author: taymoor89
branch: 1252-refactor-breadcrumbs
---
# PR #1254: feat(aurora): refactor breadcrumb generation

**Author:** taymoor89 · **Status:** created 2026-09-02 → merged 2026-09-02
**Branches:** `1252-refactor-breadcrumbs` → `main` · **Files:** 35 (+1129/-727)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1254

## What was done

Closes issue #1252. The PR replaces the monolithic, router-specific hardcoded way of building breadcrumbs (`ProjectInfoBox`, `packages/aurora/src/client/components/ProjectView/ProjectInfoBox.tsx`, deleted by this PR) with a set of generic primitives published from the package — with the explicit goal of letting embedded sub-apps (SCI services with their own `RouterProvider`) take part in the OSS host's shared breadcrumb chain.

Previously, all of the breadcrumb-chain building logic lived in a single `ProjectInfoBox` component, which manually walked `useMatches()`, looked for the deepest match under `/_auth/projects/$projectId`, and assembled 1–3 breadcrumbs from a special mini-DSL in each route's `staticData` (`labelKey`/`label`/`useParamAsLabel`/`sectionCrumb`/`intermediateCrumb`/`isDetail`/`useParentTitleAsLabel` — seven different fields for a single scheme). The component was tightly bound to the specific `useMatches()`/`useParams()` of the OSS router and took `projectInfo` as a prop from outside — using it outside `$projectId.tsx` was impossible.

The new model has two independent breadcrumb sources per route match:

- **Static** — `staticData.crumb: { text, to?, icon? }` (typed via `satisfies RouteInfo`), for labels known at build time;
- **Dynamic** — `useSetBreadcrumb(routeId, text, { to? })`, called from the route component, for labels known only at runtime (a resource name from the API) — it registers the breadcrumb in `DynamicBreadcrumbContext` and removes it on unmount.

Both sources are read by a single `useBreadcrumbs()` — a generic hook not tied to a specific router instance, and therefore suitable for embedded sub-apps as well. `usePushBreadcrumbs(items)` is the reverse channel: a sub-app publishes its own list of breadcrumbs into `BreadcrumbExtensionContext`, and the OSS `Breadcrumbs` component (the renamed `ProjectInfoBox`, moved to `components/Breadcrumbs.tsx`) appends them after its own chain.

The old mini-DSL in `routeInfo.ts` (`CRUMB_LABEL_KEYS`/`labelKey`/`useParamAsLabel`/`sectionCrumb`/`intermediateCrumb`/`isDetail`/`useParentTitleAsLabel`) has been removed entirely; instead of enum labels, Lingui `msg` message descriptors are now used (`text: MessageDescriptor | string`), resolved in `useBreadcrumbs()` via `useLingui()`.

~18 route files under `compute/flavors*`, `compute/images*`, `network/floatingips*`, `network/securitygroups*`, `storage/**` have been migrated to the new scheme — mostly mechanically: `sectionCrumb`/`crumb: { labelKey }` → `` crumb: { text: msg`...` } `` in static routes, `useSetBreadcrumb(Route.id, ...)` in detail page components.

## How it is implemented

**The core — `useBreadcrumbs()`** (`packages/aurora/src/client/hooks/useBreadcrumbs.ts:25-77`) reads `useMatches()` and filters the matches that either have `staticData.crumb` set or have an entry in `DynamicBreadcrumbContext` by `routeId`:

```ts
const crumbMatches = matches.filter(
  (m) => (isRouteInfo(m.staticData) && (m.staticData as RouteInfo).crumb) || dynamicCrumbs.has(m.routeId)
)
```
(`useBreadcrumbs.ts:42-44`), and for each match resolves text/icon/`to` with the priority "the dynamic breadcrumb wins over the static one" (`useBreadcrumbs.ts:50-56`); the last breadcrumb is marked `active: true` without `onClick`, all others get `onClick: () => navigate({ to: crumbTo ?? match.pathname, ... })` (`useBreadcrumbs.ts:57-65`) — if no explicit `to` is given, `match.pathname` accumulated by TanStack Router for this match is used (see below about the `$projectId`/`$storageType` tail, where `to` is deliberately not passed).

Additionally, the hook can attach a "service" breadcrumb for a server-side extension service (SCI) if the current URL matches the `serviceType` param and it is found in `additionalProjectServices` from the route context (`useBreadcrumbs.ts:68-74`) — this item is marked `active: true` without its own `onClick`; making it clickable (when there are extensions) is the caller's job.

**`useSetBreadcrumb`** (`hooks/useSetBreadcrumb.ts:12-23`) registers/removes the breadcrumb in a `useLayoutEffect` with cleanup:

```ts
useLayoutEffect(() => {
  if (text) {
    setCrumb(routeId, { text, to })
  } else {
    setCrumb(routeId, null)
  }
  return () => setCrumb(routeId, null)
}, [routeId, text, to, setCrumb])
```

The deps array contains only primitives (`routeId`, `text`, the extracted `to`, a stable `setCrumb` from `useCallback`) — calling code can pass `{ to: "..." }` as an inline object on every render without risking an infinite loop (`options` itself does not participate in the deps).

**`usePushBreadcrumbs`** (`hooks/usePushBreadcrumbs.ts:13-23`) serializes the list into a string key (`label:icon:active`, comma-separated) and updates the context only when the key changes; a separate effect with empty deps clears the context when the host unmounts.

**Contexts.** `DynamicBreadcrumbContext`/`DynamicBreadcrumbProvider` (`context/DynamicBreadcrumbContext.tsx:5-26`) — a `Map<routeId, Crumb>`, mounted in `routes/_auth.tsx:28-30` (wraps `<Outlet/>` at the level of the entire authenticated tree — exactly where the comment in `useSetBreadcrumb.ts:9` requires). `BreadcrumbExtensionContext`/`BreadcrumbExtensionProvider` (`context/BreadcrumbExtensionContext.tsx:5-17`) — mounted one level lower, in `routes/_auth/projects/$projectId.tsx:199-202`, exactly where the comment in `usePushBreadcrumbs.ts:10` requires.

**`Breadcrumbs`** (`components/Breadcrumbs.tsx:8-53`, formerly `ProjectInfoBox`) merges the two streams: it takes `useBreadcrumbs()` and, if there is a non-empty `extensionCrumbs` from `BreadcrumbExtensionContext`, deactivates the last OSS breadcrumb (the service label), gives it an `onClick` to return to the service root, and appends `extensionCrumbs` after it (`Breadcrumbs.tsx:15-39`). Unlike the old `ProjectInfoBox`, the new `Breadcrumbs` takes no props — project data comes via `useSetBreadcrumb(Route.id, projectLabel)`, called directly in `$projectId.tsx:105-107` (the same "domain/project" logic that used to be assembled inside `ProjectInfoBox` simply moved to the caller).

**Public exports** (`packages/aurora/src/client/index.ts:25-28`, added by this PR):

```ts
export { usePushBreadcrumbs } from "./hooks/usePushBreadcrumbs"
export { useSetBreadcrumb } from "./hooks/useSetBreadcrumb"
export { useBreadcrumbs, type BreadcrumbItem } from "./hooks/useBreadcrumbs"
export { DynamicBreadcrumbContext, DynamicBreadcrumbProvider } from "./context/DynamicBreadcrumbContext"
```

The `Breadcrumbs` component itself (the OSS UI widget) is not exported from the barrel — and that makes sense: the contract for sub-apps is `useBreadcrumbs`/`useSetBreadcrumb`/`DynamicBreadcrumbProvider`/`usePushBreadcrumbs`; OSS always renders the breadcrumbs itself.

**Representative route conversion examples.** Static (`compute/flavors.tsx:18-26`): `sectionCrumb: { labelKey: "Compute" }, crumb: { labelKey: "Flavors" }` → simply `` crumb: { text: msg`Flavors` } ``. Dynamic (`compute/images/$imageId.tsx:43-50` + `:112`): `staticData` no longer contains `crumb` at all (`isDetail`/`sectionCrumb`/the old `crumb` with `useParamAsLabel` were removed), and `RouteComponent` calls `useSetBreadcrumb(Route.id, image?.name as string | undefined)` after the image name arrives from the tRPC query.

One place required a structural rather than mechanical change: `storage/$provider/$storageType.tsx` is a new file (a layout route, `21` lines), added specifically so that "Object Storage (Swift/Ceph)" gets its own match with its own dynamic breadcrumb (`useSetBreadcrumb` inside `StorageTypeLayout`, `$storageType.tsx:12-20`), and the bucket list moved to `$storageType/index.tsx`. Because of this shift, the `Route` import in `storage/-components/Ceph/Buckets/index.tsx` (and its test) changed from `.../$storageType` to `.../$storageType/index` — both places are updated in sync in the diff; no inconsistencies.

`routeTree.gen.ts` was regenerated automatically (not reviewed line by line) — the set of new/renamed routes in it (in particular the new `$storageType` layout route) matches the manual edits; no discrepancies with the hand-written routes were found.

## What it affects

**New public surface and consumers.** `client/index.ts` adds 6 new public symbols: `useBreadcrumbs`, `type BreadcrumbItem`, `useSetBreadcrumb`, `usePushBreadcrumbs`, `DynamicBreadcrumbContext`, `DynamicBreadcrumbProvider`. A `git grep` for each name on `origin/main` (outside the files this PR itself changes) finds no mentions at all — which confirms what the PR/changeset states: the symbols are entirely new, there are no consumers outside the package yet (in particular in `apps/dashboard`), and nothing can break.

**`ProjectInfoBox` → `Breadcrumbs`: the rename is safe.** On `origin/main`, `ProjectInfoBox` was not exported from `client/index.ts` and was used in only one place — `routes/_auth/projects/$projectId.tsx` (plus its colocated test). Both places are switched to the new `Breadcrumbs` in this same PR; no external imports via a direct path (`@cobaltcore-dev/aurora/client/components/ProjectView/ProjectInfoBox` and the like) were found in the rest of the codebase — the rename is not a breaking change for package consumers.

**The (package) README is not updated for the new public surface — see "Review", the only finding with confidence ≥80.**

**Not a regression but dead-code cleanup: the disappearance of the "Compute"/"Network"/"Storage" section breadcrumb.** At first glance the PR removes an intermediate level of the chain (it was `Home > Compute > Flavors`, now `Home > Flavors`) — none of the 18 converted routes carries the section label over to the new scheme. But `git show origin/main:.../ProjectInfoBox.tsx` shows that the old code added `sectionCrumb` to the chain only under the condition `if (info.sectionCrumb?.to)` (`ProjectInfoBox.tsx:67`) — and in all 12 usages of `sectionCrumb` on `origin/main` only `{ labelKey: "Compute" }` and the like were passed, without `to`. That is, the section breadcrumb was already not rendered on `main` before this PR — this path became dead back in `3e782219 feat(portal): simplify breadcrumb — omit section group label (#937)`, long before the current PR. The refactoring simply removed code that never executed anyway; user-facing behavior does not change.

**The breadcrumb E2E tests (`apps/dashboard/e2e/ui/project-detail.spec.ts`), which this PR does not touch, remain valid according to the code.** The test checks that the combined "Domain/Project" breadcrumb is inactive on the overview and becomes clickable on sub-routes, leading back to the overview. Under the new implementation: `useSetBreadcrumb(Route.id, projectLabel)` in `$projectId.tsx:107` without `to` → on a sub-route `crumbTo ?? match.pathname` resolves to the `match.pathname` of the `$projectId` match, which is exactly the path `/projects/$projectId` — matching the test's expectation. The label format (`domain/project`) is assembled by the same logic (`$projectId.tsx:105-106`) that used to live inside `ProjectInfoBox`. The test was not verified by running it (E2E requires a real environment), but tracing the code found no discrepancies with its expectations.

## Review

**[95] `packages/aurora/README.md` does not document any of the six new public exports, even though the PR introduces them directly and solely for that purpose.** [`CLAUDE.md`](../../CLAUDE.md) names `packages/aurora/README.md` as the source of truth for the package's consumer contract ("treat that file as the source of truth when changing any of `AuroraApp`'s public props"), and this PR's changeset itself states the goal as "for use in embedded sub-apps and standalone consumers" — i.e. the audience is precisely external README readers, not only maintainers. The PR diff does not touch `README.md` at all (`git grep README` over `/tmp/pr1254.diff` — empty), neither at the root nor in `packages/aurora/`. The README has not a word about `useBreadcrumbs`, `useSetBreadcrumb`, `usePushBreadcrumbs`, `DynamicBreadcrumbProvider`/`DynamicBreadcrumbContext`, nor an example of how a sub-app should connect these primitives to its own `RouterProvider`. This is exactly the same pattern that was already recorded as finding [100] in the review of PR #1189 ([`prs/1189-custom-project-services.md`](1189-custom-project-services.md)) for `additionalProjectServices` — and as of this PR it remains unfixed for the new batch of public API. A developer opening the README today will not learn that the breadcrumb primitives exist at all.

*Checked and not confirmed (below the ≥80 threshold, not reported separately):* the disappearance of the "Compute"/"Network"/"Storage" section breadcrumb — not a regression, see "What it affects" (the render condition had been dead since #937, long before this PR); an edge case in `Breadcrumbs.tsx:15-39` where, with `hasExtensionTrail === true` but the service not found in `additionalProjectServices`, the last OSS breadcrumb would wrongly get a "back to service button" — the branch is technically unreachable in the normal flow (a URL with a `serviceType` param exists only if the service is registered and will therefore be found); the types/deps arrays of `useSetBreadcrumb`/`usePushBreadcrumbs` (provider mount order, cleanup on unmount, stability of `setCrumb`/`setBreadcrumbs`) were checked line by line — the logic is correct and matches the comments in the files.

---
Analyzed: 2026-09-02 · commit `b70f667c` (head, PR open/unmerged)
