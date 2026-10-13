---
type: pr-report
date: 2026-08-20
status: merged
pr: [1189]
author: taymoor89 (Taimoor Aslam)
branch: 1102-support-custom-services
---
# PR #1189: feat(aurora): allow consumers to register custom srevices

**Author:** taymoor89 (Taimoor Aslam) · **Status:** merged 2026-08-24 (commit `a9c257a1`; created 2026-08-20)
**Branches:** `1102-support-custom-services` → `main` · **Files:** 61 (+840/-7582)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1189

> Closes issue #1102. The title commit contains a typo — "srevices" instead of "services"; this doesn't violate the `<type>(<scope>): <subject>` format for commitlint (only type/scope are checked, not spelling).

## What was done

The PR introduces a general extension mechanism for `AuroraApp` — a new `additionalProjectServices` prop that lets a consumer register their own project-scoped service (client-side routes + a nav item) without forking the package — and at the same time, in the same PR, completely removes the built-in PCA (Clavis) implementation from the OSS package: the server router, Zod schemas, the entire client UI and tests under `services/pca/**`, i18n strings. Wording from the changeset: "This replaces the previously hardcoded PCA (Clavis) integration. PCA and any other consumer-specific service should now be registered this way rather than living inside the OSS package."

The net result for the consumer: instead of a hardwired "PCA is always there", the package now knows nothing specific about PCA — if it's needed, the consumer app registers it itself via the new API, while getting the same UX (an item in the "Services" nav section, a card on the project page) that the built-in PCA used to provide.

## How it is implemented

### New public `AuroraApp` API

`AdditionalProjectService` is a new exported type (`packages/aurora/src/client/AuroraApp.tsx:64-78`):

```ts
export type AdditionalProjectService = {
  /** OpenStack catalog service type, e.g. `"pca"`. */
  serviceType: string
  /** OpenStack catalog service name, e.g. `"clavis"`. */
  serviceName: string
  /** Nav item and service card label. */
  label: string
  routes: AnyRoute
}
```

and a new prop on `AuroraAppProps` (`AuroraApp.tsx:115-116`): `additionalProjectServices?: AdditionalProjectService[]`. Service activation is tied to the same condition that `canAccessClavisPca` used to check for PCA — the presence of `serviceType`/`serviceName` in the project's OpenStack catalog plus (if set) `enabledServices`.

### Splicing routes into the TanStack Router tree

The most non-trivial part — `createAuroraRouter` (`packages/aurora/src/client/router.ts:12-45`) now takes a third parameter `additionalProjectServices` and, before creating the router, manually appends the passed routes to the tree:

```ts
const parent = parentFn() as unknown as RouteWithChildren
const existing = parent.children ?? {}
parent._addFileChildren({ ...existing, [`_extra_${i}`]: route })
```

(`router.ts:26-28`). Each element of `additionalProjectServices[].routes` must have `options.getParentRoute` (by convention pointing to the new `servicesRoute`), otherwise an `Error` is thrown (`router.ts:23-24`). The new file route `services.tsx` (`packages/aurora/src/client/routes/_auth/projects/$projectId/services.tsx`, created by this PR) is a minimal layout route that serves as the attachment point:

```tsx
export const Route = createFileRoute("/_auth/projects/$projectId/services")({
  component: () => <Outlet />,
})
export { Route as servicesRoute }
```

`servicesRoute` is exported from the public `packages/aurora/src/client/index.ts` together with `RouteInfo`/`Crumb`/`isRouteInfo` — the consumer needs all of these to build its own sub-route and pass it into `additionalProjectServices`.

### Navigation and cards on the project page

`buildNavSections.ts` (`packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.ts`) dropped the hardcoded `canAccessClavisPca`/`clavisServices` and introduced a `Map` of built-in sections (compute/network/storage/services), into which a loop (lines 117-128) mixes in the permitted additional services:

```ts
for (const module of additionalProjectServices ?? []) {
  if (!serviceIndex[module.serviceType]?.[module.serviceName]) continue
  if (enabledServices && !enabledServices.includes(module.serviceType)) continue
  sectionMap.get("services")?.services.push({ ... navigate: (nav) => nav({ to: module.routes.fullPath as never, params: { projectId } as never }) })
}
```

A similar loop in `$projectId/index.tsx:102-114` renders the service card on the project overview page, but builds the link differently — not via `nav({ to, params })` but by string substitution: `additionalService.routes.fullPath.replace("$projectId", projectId)` (`index.tsx:111`, more in the "Review" section).

### Server exports

`packages/aurora/src/server/index.ts` now additionally exports `validateOpenstackService` (a previously existing internal helper, since #850, made public for the first time) and `parseOrThrow` (previously an internal `Network/helpers` helper, used only by `pcaRouter.ts`/floating-ip routers) — both are needed by the consumer to write its own BFF router following the same conventions described in [`CLAUDE.md`](../../CLAUDE.md) ("routers must be built with the exported `auroraRouter`"). `routers.ts` removed `serviceRouters` (the former `Services/routers`, whose only content was PCA) from `buildBaseRouter` (`routers.ts:6,15`).

### Other

The `@peculiar/x509` and `reflect-metadata` dependencies were removed from `packages/aurora/package.json` (they were used only by PCA's CSR/certificate parsing) — `git grep` over `pr-1189-head` no longer finds a single import of either. `apps/dashboard/package.json` added `@tanstack/router-plugin` to devDependencies (apparently needed for regenerating `routeTree.gen.ts`). The changeset `move-pca-to-sci-scope-modules.md` is marked `minor`.

## What it affects

**The package's own design doc is outdated.** `packages/aurora/docs/0011_clavis.md` — a design doc describing the PCA/Clavis integration in full detail (routes, components, states) — is not touched by this PR at all (`git diff` on the file is empty), even though the functionality it describes has been removed entirely. It continues to claim "The active UI entry point is the project service route at `/projects/$projectId/services/pca/`" and so on — i.e. it now describes code that no longer exists, without an "outdated" marker and without a pointer to the new `additionalProjectServices`.

**Our own KB depends on this too.** [`DOCS/aurora-dashboard-kb/05-domain-map.md`](../05-domain-map.md) in this knowledge base references `0011_clavis.md` as the "living doc, current scope" for the Services — PCA/Clavis row. If this PR is merged as is, our domain map will also become inaccurate (it references a design doc describing removed functionality) — worth taking into account on the next `update-kb` run after the merge.

**Fresh PCA work is deleted the very next day.** This PR's merge base (`35095b4f`) is exactly the head of `main` right after PR #1177 was merged (2026-08-19, "different changes(api/ui-ux) with downloading functionality" — certificate download/import, refactoring of `parseCsrInfo`, etc.). PR #1189 deletes all of this code the next day (commits of 2026-08-20). Neither the commit messages nor the changeset mention #1177 or that functionality merged just the day before is being thrown out entirely — it's worth explicitly checking with the author of #1177 (or the PCA consumer) that this work has been carried over/accounted for on the side of the future external implementation, rather than lost.

**The public contract is extended without bloating server routing.** A grep for `pca`/`clavis` outside the deleted files shows that mentions remain only in `CHANGELOG.md` (a historical entry, as expected), `docs/0011_clavis.md` (see above) and — more importantly — twice in `README.md` (see "Review"). No other code/test outside the deleted files and this PR's edits references `pca`/`Clavis`, `serviceRouters` or `pcaRouter` itself — i.e. the removal of the server/client parts is internally self-contained and doesn't break anything else.

**Checked and not a problem:** the standalone path traversal security fix (#1153, `validateAndEncodeResourceId`) inside `pcaRouter.ts` was self-contained — the shared helper lives in `signal-openstack` and continues to be used by the other routers (`flavorRouter`, `floatingIpRouter`, `securityGroupRouter`, `projectRouter`); deleting `pcaRouter.ts` does not affect it.

## Review

**[100] `README.md` is not updated for the new public prop `additionalProjectServices` — the PR's only substantive feature.** `CLAUDE.md` explicitly names `packages/aurora/README.md` as the source of truth when changing `AuroraApp`'s public props: "treat that file as the source of truth when changing any of `AuroraApp`'s public props". The props table (`README.md:117-125`) ends at `enabledServices` and contains neither a row nor a usage example for `additionalProjectServices`/`AdditionalProjectService` — a consumer opening the README today won't learn that this mechanism exists at all.

**[100] `README.md` in two places continues to call `"pca"` a working built-in service key, even though this same PR removes the entire built-in PCA implementation.** `README.md:176` ("**Service key reference:** ... `"pca"`") and `README.md:203` ("**Available service keys:** ... `"pca"`") are not touched by this PR — yet after the merge `"pca"` exists nowhere in the package's built-in code. A consumer following these instructions will expect a working service key that won't be there.

**[80] `createAuroraRouter` mutates the shared module-singleton `routeTree` without resetting it between calls — routes may accumulate on repeated factory calls.** `router.ts:26-28` gets the parent route via `parentFn()`, which returns an object from the shared `routeTree` (imported once from `./routeTree.gen`), and calls `parent._addFileChildren({...existing, [`_extra_${i}`]: route})`. The `_addFileChildren` implementation in `@tanstack/router-core` mutates the route object itself (`this.children = ...; return this`) rather than cloning it; nothing in `createAuroraRouter` clears `parent.children` before mixing in. Since `AuroraApp` is a published library embedded by external consumers (not a single fixed page controlled by the maintainers), calling this factory again within one loaded module instance — an HMR remount in dev mode, a second mounted `<AuroraApp/>` on the same page, or simply a future test suite for `router.ts` (which doesn't exist now) — will append `_extra_i` on top of whatever has already accrued from previous calls, with no mechanism for removing the old ones. No test for `router.ts` was added in the PR, so CI won't catch this.

*Checked and not confirmed (below the ≥80 threshold, not reported separately):* orphaned files `PcaToastNotifications.tsx`/`.test.tsx` (not deleted along with the rest of the PCA UI, but they don't affect anything either — dead code); `additionalService.routes.fullPath.replace("$projectId", projectId)` in `index.tsx:111` — works under the documented "single `$projectId` segment" constraint, but is less robust than the neighboring `nav({ to, params })` approach in `buildNavSections.ts:125`; the typing of `RouteWithChildren.children` as `Record<string, AnyRoute>` in `router.ts:9` doesn't match the actual shape (an array) — a type-level discrepancy only, it doesn't affect behavior.

---
Analyzed: 2026-08-20 · commit `c086aa4`
