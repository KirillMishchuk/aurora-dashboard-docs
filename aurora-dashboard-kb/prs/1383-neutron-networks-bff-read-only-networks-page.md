---
type: pr-report
date: 2026-10-17
status: open
pr: [1383]
issue: [1019]
author: hodanoori
branch: hoda-aurora-network
---

# PR #1383: feat(aurora): add Neutron Networks BFF and read-only Networks page (list & details)

**Author:** hodanoori · **Status:** draft · **Base:** `main` ← `hoda-aurora-network`
**Size:** 17 files, +1344 / −2 · **Created:** 2026-10-12 · [View on GitHub](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1383)

---

## PR Review Report by [review-and-comment-pr](https://github.com/KirillMishchuk/aurora-dashboard-docs/blob/main/ToolDocs/claude-config/aurora-dashboard-config/.claude/skills/review-and-comment-pr/SKILL.md)

### ⚖️ &nbsp; Verdict

Recommendation: **🔴 Request Changes** &nbsp;&nbsp;&nbsp;&nbsp; Confidence to Merge: **Medium**

The BFF is cleanly project-scoped. IDs are validated before they reach Neutron, and the security review found nothing. The client follows the Routers pattern closely.

Two things block the merge:
- **CI is red.** The new nav entry breaks two `buildNavSections` tests, and those tests were not updated.
- **The list is never paginated.** It reads one Neutron page, so on deployments that cap list size, networks go missing without any warning.

The PR also duplicates #1385 and #1386, which implement the same `network.networks` feature, so the team has to pick one before either can merge.

Acceptance was graded against epic #1019, which the PR links as context. The read-only Phase 1 scope is mostly delivered. The Status and Shared list filters are still missing.

### 🔧 &nbsp; Required Changes

| #   | Severity    | Category      | Issue                                                                                   | Location                                                     |
| --- | ----------- | ------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| CR1 | 🟠 Major    | Bug           | Networks list reads a single Neutron page: no `limit`/`marker`, `networks_links` ignored | `packages/aurora/src/server/Network/routers/networksRouter.ts:43` |
| CR2 | 🟠 Major    | Test coverage | New nav item breaks `buildNavSections.test.ts`, so CI `test` fails                       | `packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.test.ts:40` |
| CR3 | 🟡 Moderate | UI/UX         | 401/403 rendered inline as error text instead of redirect / page-level info `Message`   | `.../network/networks/-components/NetworksList.tsx:42`       |
| CR4 | 🟡 Moderate | Performance   | Details page fetches the network twice (loader + `useQuery`)                            | `.../network/networks/$networkId.tsx:124`                    |
| CR5 | 🟡 Moderate | Code Quality  | Same feature implemented by open PRs #1385 and #1386; add/add conflicts                  | PR state                                                     |
| CR6 | 🟡 Moderate | Code Quality  | Conflicts with `main` (locale catalogs) and with Ports PR #1377 (`Network/routers/index.ts`) | `packages/aurora/src/server/Network/routers/index.ts:17`  |
| P1  | —           | Process       | PR is still a draft                                                                     | PR state                                                     |
| P2  | —           | Process       | No changeset, though `packages/aurora/src` changes                                      | `.changeset/`                                                |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**CR1 — List reads only the first Neutron page** · Bug · `packages/aurora/src/server/Network/routers/networksRouter.ts:43`
`list` issues one `GET v2.0/networks`. It parses the result with `NetworkListResponseSchema = z.object({ networks: z.array(NetworkSchema) })` (`types/network.ts:32`), and `NetworkQueryParametersSchema` (`types/network.ts:63`) has no `limit` or `marker`.

The Neutron API reference ([Pagination](https://docs.openstack.org/api-ref/network/v2/index.html)) says list operations "will return a maximum number of items at a time". It also says: "If the client requests a limit beyond the maximum limit configured by the deployment, the server returns the maximum limit number of items". Responses carry `next` links for the rest.

So on a deployment with a page cap, the BFF returns only the first page. The BFF-side `searchTerm`/`status` filters and the client-side 50-row pagination (`NetworksList.tsx:82`) then work on that partial set, and the user gets no sign that networks are missing. The existing `routersRouter` doesn't paginate either, so expect pushback.

@KirylSAP raised this in the earlier review comment on this PR (CR3); it is still unaddressed. That comment's fix was to add the params to the schema. That alone isn't enough, because BFF-side search over a paged fetch gives wrong pages.

_Fix:_ Follow `networks_links` `next` until it runs out, then filter and slice. The other option is server-side paging, with search pushed to Neutron's `name` filter. Add a test with a two-page Neutron response.

**CR2 — Nav tests not updated; CI `test` fails** · Test coverage · `packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.test.ts:40`
`buildNavSections.ts:60` now puts `networks` first in the Network section. The test file isn't in the PR, and two assertions still expect the old lists:
- line 40: `toEqual(["securitygroups", "floatingips", "routers"])`
- line 118: `toEqual(["securitygroups", "routers"])`

The `ci-checks` `test` job on `3e32ab04` fails on exactly these two tests: "includes the correct services in each built-in section" and "hides a service via deniedServices alone". @KirylSAP raised this in the earlier review comment (P1); it is still unaddressed.

_Fix:_ Prepend `"networks"` to both expected arrays, and add a case where `"networks"` is denied.

**CR3 — 401/403 handled inline** · UI/UX · `.../network/networks/-components/NetworksList.tsx:42`
On the list, `FORBIDDEN` is caught and turned into `listError: err.message`, which is rendered as `<Status status="error" … body={listError} />` (`NetworksList.tsx:101`). The details page maps `UNAUTHORIZED` and `FORBIDDEN` to inline error text (`$networkId.tsx:63`).

`copilot-instructions.md` B.6 says: "**Reject** … a 401/403 handled inline instead of via redirect / page-level info `Message`". Its table expects a redirect to sign-in for 401 and an info `Message` page for 403. The Routers details page (`$routerId.tsx:71`) does the same, so expect pushback.

_Fix:_ Let 401 go through the app's session-expiry redirect. Render 403 as the page-level info `Message` from B.6, with no raw upstream text.

**CR4 — Network fetched twice on the details page** · Performance · `.../network/networks/$networkId.tsx:124`
The route `loader` calls `context.trpcClient?.network.networks.getById.query(...)` only to get the page title. The component then calls `trpcReact.network.networks.getById.useQuery(...)` (`$networkId.tsx:149`). The vanilla client and the React Query cache are separate, so every visit sends two `GET /v2.0/networks/{id}` to Neutron. The Routers details route (`$routerId.tsx:129` / `:154`) has the same pattern.

_Fix:_ Prefetch into the query cache in the loader, using the tRPC utils' `ensureData`/`fetch`. The other option is to drop the loader and set the title from the query result.

**CR5 — Duplicate implementation in #1385 and #1386** · Code Quality · PR state
#1385 ("feat(network): add Neutron Networks BFF and read-only Networks page") and #1386 both register `networks: networksRouter` under `network` and add the same `network/networks/…` routes.

`git merge-tree` of this head against #1385 reports add/add conflicts in:
- `$networkId.tsx` and `networks/index.tsx`
- the four `-components` files
- `networkHelpers.ts`, `networksRouter.ts` and `types/network.ts`
- the locale catalogs

Only one of them can land without a rewrite. #1385 also ships router and schema tests. @KirylSAP raised this in the earlier review comment (P3); the PRs are still unreconciled.

_Fix:_ Agree with the #1385/#1386 authors which branch carries the feature. Close the others or rebase them onto it.

**CR6 — Conflicts with `main` and with Ports PR #1377** · Code Quality · `packages/aurora/src/server/Network/routers/index.ts:17`
Against current `main` (`a21ba3ec`), the head conflicts in `packages/aurora/src/locales/{de,en}/messages.{po,ts}`. Those are generated catalogs, regenerated by `pnpm check-i18n`. Against #1377 it conflicts in the same catalogs and in `Network/routers/index.ts`, where both PRs add an entry to the router map. That one needs a manual merge, though there is no semantic clash.

_Fix:_ Merge `main`, re-run the lingui extract/compile, and coordinate the `index.ts` entry order with #1377.

**P1 — Draft** · Process · PR state
The PR is still a draft, and the description's screenshots section is a TODO.
_Fix:_ Add the list and detail screenshots, then mark the PR ready for review.

**P2 — Missing changeset** · Process · `.changeset/`
The PR adds a feature to the published `@cobaltcore-dev/aurora` package (`packages/aurora/src/**`), but adds no `.changeset/*.md`. Releases are driven by changesets. @KirylSAP raised this in the earlier review comment (P2).
_Fix:_ `pnpm changeset` with a `minor` bump for `@cobaltcore-dev/aurora`.

</details>

### 💡 &nbsp; Improvements

| #   | Severity   | Category     | Issue                                                                       | Location                                                        |
| --- | ---------- | ------------ | --------------------------------------------------------------------------- | --------------------------------------------------------------- |
| I1  | 🟢 Low     | Code Quality | Raw `<button>` for the Subnets "Try Again" action                           | `.../networks/-components/NetworkDetailsView.tsx:69`            |
| I2  | 🟢 Low     | Code Quality | `PopupMenu` without `PopupMenuToggle`                                       | `.../networks/-components/NetworkTableRow.tsx:56`               |
| I3  | 🟢 Low     | Code Quality | Active details tab held in `useState`, not in the URL                       | `.../networks/-components/NetworkDetailsView.tsx:109`           |
| I4  | 🟢 Low     | UI/UX        | "Log in again to continue." — standards require "Sign in"                   | `.../network/networks/$networkId.tsx:66`                        |
| I5  | 🟢 Low     | UI/UX        | All-caps `UP` / `DOWN` admin-state values                                   | `.../networks/-components/NetworkTableRow.tsx:46`               |
| I6  | 🟢 Low     | Code Quality | `status` filtered BFF-side under a comment saying Neutron can't filter it   | `packages/aurora/src/server/Network/helpers/networkHelpers.ts:28` |
| I7  | 🟢 Low     | Code Quality | `shared` allowed as `sort_key` and commented as Neutron-supported; it isn't | `packages/aurora/src/server/Network/types/network.ts:61`        |
| I8  | 🟢 Low     | Docs         | New `"networks"` service key missing from the README key lists              | `packages/aurora/README.md:183`                                 |
| I9  | 🟢 Low     | UI/UX        | Epic #1019 Phase 1 asks for Status/Shared list filters; only search + sort  | `.../networks/-components/NetworksList.tsx:165`                 |
| I10 | ⚪ Trivial | Code Quality | Import order: `zod` after the lingui imports                                | `.../network/networks/index.tsx:2`                              |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**I1 — Raw `<button>`** · Code Quality · `.../networks/-components/NetworkDetailsView.tsx:69`
`action={<button onClick={() => refetch()}>{t`Try Again`}</button>}`. This is a Quick Reject item: "Raw HTML element (`<div>`, `<table>`, `<button>`) where a Juno component exists". The button is unstyled, and other files in this PR already use Juno `Button`. @KirylSAP raised this in the earlier review comment (CR1); it is still unaddressed.
_Fix:_ Import `Button` from Juno and use `<Button onClick={() => refetch()}>`.

**I2 — `PopupMenu` without `PopupMenuToggle`** · Code Quality · `.../networks/-components/NetworkTableRow.tsx:56`
This is a Quick Reject item: "`PopupMenu` without `PopupMenuToggle` as trigger". B.14 says context menus must use `<PopupMenuToggle as="div"><Button icon="moreVert" /></PopupMenuToggle>`. Juno 9.4.0 renders a default `moreVert` toggle, so the visible effect is small. The merged `RouterTableRow.tsx:82` does the same. @KirylSAP raised this in the earlier review comment (CR2).
_Fix:_ Wrap the trigger in `PopupMenuToggle` as B.14 shows.

**I3 — Tab state in `useState`** · Code Quality · `.../networks/-components/NetworkDetailsView.tsx:109`
`useState<NetworkDetailsTab>("overview")`. This is a Quick Reject item: "URL-worthy state held in `useState` instead of search params". B.9 lists "Active tab → `tab`". After a refresh or a shared link, the page opens on Overview instead of Subnets. `RouterDetailsView.tsx:45` does the same.
_Fix:_ Add `tab` to the details route's `validateSearch`, and drive `TabNavigation` from it.

**I4 — "Log in"** · UI/UX · `.../network/networks/$networkId.tsx:66`
This is a Quick Reject item: the checklist bans strings using "Sign In"/"Log in" and asks for "Sign in". B.19 repeats the rule. The same wording exists in `$routerId.tsx:71`.
_Fix:_ Change it to "Sign in again to continue." This line goes away if CR3 is fixed.

**I5 — All-caps values** · UI/UX · `.../networks/-components/NetworkTableRow.tsx:46`
`network.admin_state_up ? t`UP` : t`DOWN``, here and at `NetworkDetailsView.tsx:117`. This is a Quick Reject item: strings using all-caps. B.19 says: "Never all-caps (ever)". Routers uses the same strings.
_Fix:_ Use "Up" / "Down".

**I6 — Wrong comment about Neutron filtering** · Code Quality · `packages/aurora/src/server/Network/helpers/networkHelpers.ts:28`
The comment says "Filters Neutron doesn't support directly; applied BFF-side." The [List networks](https://docs.openstack.org/api-ref/network/v2/index.html#list-networks) reference documents a `status` query parameter: "Filter the network list result by network status. Values are `ACTIVE`, `DOWN`, `BUILD` or `ERROR`." The UI doesn't send `status` today. If it does later, filtering BFF-side makes CR1 worse.
_Fix:_ Forward `status` to Neutron (validated against the four values), and drop `filterNetworksByBffParams`.

**I7 — `shared` is not a documented sort key** · Code Quality · `packages/aurora/src/server/Network/types/network.ts:61`
The comment says "Sort keys supported by Neutron for GET /v2.0/networks", and the enum is `["name", "status", "admin_state_up", "shared"]`. The [List networks](https://docs.openstack.org/api-ref/network/v2/index.html#list-networks) `sort_key` values are `admin_state_up`, `availability_zone_hints`, `id`, `mtu`, `name`, `status`, `tenant_id`, `project_id`. The UI only offers name and status, so users can't hit this today.
_Fix:_ Remove `shared` from the enum, or replace it with a documented key.

**I8 — README service keys** · Docs · `packages/aurora/README.md:183`
"**Service key reference:**" (line 183) and "**Available service keys:**" (line 210) document the `enabledServices`/`deniedServices` keys. The PR adds `"networks"` but updates neither list. `"routers"` is already missing from both, which predates this PR.
_Fix:_ Add `"networks"` to both lists, and `"routers"` while there.

**I9 — Epic filters not delivered** · UI/UX · `.../networks/-components/NetworksList.tsx:165`
Epic #1019 Phase 1 asks for "Networks List View with DataGrid, pagination, and filters (Name, Status, Shared)". The list has search and Name/Status sort only. There is no Status or Shared filter, though the BFF already accepts `status` and `shared` (`types/network.ts:63`).
_Fix:_ Add the filters, or mark that subtask as a follow-up in the PR description or the epic.

**I10 — Import order** · Code Quality · `.../network/networks/index.tsx:2`
`@lingui/core/macro` and `@lingui/react/macro` come before `zod`. B.13 puts `zod` in group 1 (framework) and i18n in group 2.
_Fix:_ Move `import { z } from "zod"` above the lingui imports.

</details>

---

## Solution Overview

<details>
<summary><strong>What was done</strong></summary>

The PR adds a read-only **Networks** resource (Neutron L2 networks) under the Network section. It follows the existing Routers resource, file for file.

**BFF.** A new `network.networks` tRPC router has three project-scoped queries:
- `list` — `GET /v2.0/networks`, with Neutron-side sort plus BFF-side search and status filter.
- `getById` — `GET /v2.0/networks/{id}`.
- `listSubnets` — `GET /v2.0/subnets?network_id=…`, trimmed with `fields`.

Zod schemas model the Neutron network and subnet shapes. A mapper turns `router:external` into `external` and adds `subnet_count`, so the client never sees OpenStack-specific keys.

**Client.**
- A layout route under `/projects/$projectId/network/networks`.
- A list page with URL-driven search, sort (Name/Status) and client-side pagination of 50 rows.
- A details page with an Overview tab and a Subnets tab.
- A "Networks" entry first in the Network side-nav section, behind `isEnabled("networks")`.

The `network:networks:read`/`list` permission mappings already existed. Nothing in the PR uses them.

**State of the PR.** It is a draft, and it adds no tests and no changeset. The description ticks "My changes generate no new warnings or errors", but the `ci-checks` `test` job fails on `3e32ab04`, in the two `buildNavSections` tests (see CR2). All other CI jobs pass.

</details>

<details>
<summary><strong>How it is implemented</strong></summary>

**Router wiring.** `networksRouter` is added to the Network domain's `auroraRouter` map, so it is exposed as `network.networks.*`:

```ts
    routers: routersRouter,
    networks: networksRouter,
    ...buildNetworkPermissionRouter(policyDir),
```

`packages/aurora/src/server/Network/routers/index.ts:16`

**`list`.** It strips the BFF-only fields from the input and forwards the rest to Neutron as query parameters (`name`, `admin_state_up`, `shared`, `sort_key`, `sort_dir`, and `project_id` from `projectScopedInputSchema`). It then filters and maps the single response page:

```ts
        const { searchTerm, status, ...openstackFilters } = input
        const network = getNetworkService(ctx)

        const queryParams = appendQueryParamsFromObject(openstackFilters)
        const response = await requestOrThrow(
          () => network.get(withQuery(NETWORKS_BASE_URL, queryParams)),
          NetworkErrorHandlers.list
        )
```

`packages/aurora/src/server/Network/routers/networksRouter.ts:39`

`requestOrThrow` is reused from `routerHelpers.ts`. It routes `signal-openstack`'s non-2xx rejections through the network `ErrorHandler`, which a plain `!response.ok` check would miss. The search runs through `filterBySearchParams` over `id`, `name` and `description` (`networksRouter.ts:51`).

**`getById` / `listSubnets`.** `getById` validates and encodes the ID before putting it in the path (`networksRouter.ts:68`). `listSubnets` only validates the ID, then sends it as a query parameter together with a fixed `fields` list:

```ts
        const params = appendQueryParamsFromObject({
          network_id,
          fields: ["id", "name", "cidr", "ip_version", "gateway_ip", "enable_dhcp"],
        })
```

`packages/aurora/src/server/Network/routers/networksRouter.ts:91`

**UI-facing shape.** `toNetworkListItem` renames the colon key and derives the subnet count:

```ts
export const toNetworkListItem = (network: Network): NetworkListItem => {
  const { "router:external": external, subnets, ...rest } = network
  return {
    ...rest,
    subnets,
    external: external ?? false,
    subnet_count: subnets.length,
  }
}
```

`packages/aurora/src/server/Network/helpers/networkHelpers.ts:18`

**List page.** `Networks` reads `search`, `sortBy`, `sortDirection` and `page` from the URL, which is the single source of truth. It builds a promise per query and defers it with `useDeferredValue`, so the old rows stay visible while the next query loads. An `ErrorBoundary` keyed on the deferred promise provides "Try Again".

```ts
  const networksPromise = useMemo(
    () => createNetworksPromise(client, project, sortBy, sortDirection, searchTerm),
    // retryCount is not used in the factory, it only forces a new promise on "Try Again"
    [client, project, sortBy, sortDirection, searchTerm, retryCount]
  )
```

`.../network/networks/-components/NetworksList.tsx:177`

Pagination is a client-side slice of the full result (`NetworksList.tsx:82`). The table has 8 columns: Name/ID, Status, Shared, MTU, Admin State, Subnets, Port Security, and a row menu (`NetworkListContainer.tsx:15`).

**Details page.** The loader resolves only the page title and swallows errors. The component re-queries through React Query, and maps the tRPC error code to a status, a message and an optional retry in `NetworkLoadError`:

```ts
  loader: async ({ context, params }) => {
    try {
      const network = await context.trpcClient?.network.networks.getById.query({
        project_id: params.projectId,
        network_id: params.networkId,
      })
      return { networkName: network?.name || null }
    } catch {
      return { networkName: null }
    }
  },
```

`.../network/networks/$networkId.tsx:122`

`NetworkDetailsView` has an Overview `DescriptionList`, with `ClipboardText` for the network and project IDs. It also has a Subnets tab whose own `listSubnets` query renders loading, error, empty and `DataGrid` states (`NetworkDetailsView.tsx:47`).

</details>

<details>
<summary><strong>What it affects (blast radius)</strong></summary>

- **New tRPC surface.** `network.networks.{list,getById,listSubnets}` is new. Outside the PR's own files, nothing in the monorepo calls it. It sits under `packages/aurora/src/server/*/routers/`, so it becomes part of the published `AuroraRouter` type.
- **New service key `"networks"`.** It is used in `buildNavSections.ts` and the routes' `staticData`. Host apps can now hide the page via `enabledServices`/`deniedServices`/`appConfig`, but `packages/aurora/README.md` doesn't list the key (I8). The project overview page (`$projectId/index.tsx`) wasn't touched, so it has no Networks card. Networks is reachable from the side nav only.
- **Nav order.** Networks is inserted before Security Groups. That changes the Network section order and breaks the two `buildNavSections.test.ts` assertions that pin it (CR2).
- **Shared helpers.** `requestOrThrow` (`routerHelpers.ts`), `ErrorHandler`, `filterBySearchParams` and `appendQueryParamsFromObject` are reused unchanged, so other routers are not affected.
- **Permissions.** The `network:networks:*` mappings in `permissionRouter.ts:19` already existed. No policy files change, and nothing in the PR calls `canUser`.
- **Generated files.** `routeTree.gen.ts` and the de/en lingui catalogs are regenerated. The catalogs conflict with current `main` and with the other open network PRs (CR6).
- **Other open PRs.** #1385 and #1386 add the same router key and routes, and #1377 (Ports) touches the same router map (CR5, CR6).

</details>

---

## QA Test Plan

<details>
<summary><strong>Core Path</strong></summary>

1. Sign in and open a project whose catalog includes the `network` service.
2. In the side nav, under **Network**, check that **Networks** is the first entry, and open it.
3. Check that the list shows Name (with ID underneath when named), Status, Shared, MTU, Admin State, Subnets count, Port Security and a row menu. Compare the values against `openstack network list --long`.
4. Change the sort to Status, and then to descending. Check that the URL gets `sortBy`/`sortDirection` and that the order changes.
5. Type part of a network name, then part of an ID. After the 500 ms debounce, check that the URL gets `search` and the list filters. Clear the search and check that all networks return.
6. With more than 50 networks, page forward, then use browser back and forward. Check that the page and the controls follow the URL.
7. Click a row, or use row menu → Show Details. Check the details title and breadcrumb (name, or ID when unnamed). Check that the Overview shows ID and Project ID with copy, Description, Status, Admin State, Shared, External, MTU, Port Security, Subnets count, and Tags/Created/Updated when present.
8. Open the **Subnets** tab and check Name/ID, CIDR, IP version, Gateway IP and DHCP against `openstack subnet list --network <id>`.
9. Switch to another project. Check that the list remounts and doesn't flash the previous project's networks (`index.tsx:54`).

</details>

<details>
<summary><strong>Edge Cases</strong></summary>

- **More networks than the deployment's page cap** (CR1). Compare the row count with `openstack network list | wc -l`. Missing networks, or a search that misses a network known to exist, reproduces the bug (`networksRouter.ts:43`).
- **Empty project.** "No Networks Found" / "There are no networks in this project." (`NetworkListContainer.tsx:92`).
- **Search with no match.** "No networks match your search…" (`NetworkListContainer.tsx:91`).
- **Out-of-range `?page=99`.** After the query settles, the page resets to 1 (`NetworksList.tsx:97`). Invalid `sortBy`/`page` values in the URL are dropped by `validateSearch` (`index.tsx:28`).
- **Missing list permission.** A FORBIDDEN error shows "Failed to Load Networks" with the raw server message (`NetworksList.tsx:42`, CR3).
- **Network deleted or unknown ID in the URL.** "Network Not Found" with Back to Networks and Home buttons, and no retry (`$networkId.tsx:61`, `:76`).
- **Expired session on the details page.** The inline "The session has expired…" message (`$networkId.tsx:65`, CR3, I4).
- **Neutron 5xx or timeout on details.** The "Try Again" button appears and refetches (`$networkId.tsx:31`, `:89`).
- **Two Neutron requests per details visit.** Check the browser network tab or the BFF logs for two `getById` calls (`$networkId.tsx:124`, `:149`, CR4).
- **Network without subnets.** The Subnets tab shows "No Subnets" (`NetworkDetailsView.tsx:74`).
- **Subnets request fails.** The unstyled "Try Again" button appears (`NetworkDetailsView.tsx:69`, I1).
- **Null fields.**
  - Null `mtu` shows "–" in the list and "—" in the details (`NetworkTableRow.tsx:45`, `NetworkDetailsView.tsx:120`).
  - Missing `port_security_enabled` shows "–" or "—".
  - An unnamed network shows its ID as the title.
  - A subnet without a gateway shows "–" (`NetworkDetailsView.tsx:97`).
- **Refresh while on the Subnets tab.** It returns to Overview (`NetworkDetailsView.tsx:109`, I3).
- **`deniedServices: ["networks"]`.** The nav entry is hidden (`buildNavSections.ts:60`), but the route still loads by direct URL, which is the same as for the other services.
- **External or shared networks from other projects.** They appear in the list, as Neutron returns them, and External shows "Yes" in the details.

</details>

---

_Analyzed 2026-10-17 · commit `3e32ab04` · read-only, CI from PR API · skill: review-and-comment-pr_

<!-- related:auto — generated from pr/issue properties by tools/update-related.py; do not edit by hand -->
## Related

- plan · 2026-10-12 · [2026-10-12-networks-epic-1019-analysis](../../plans/2026-10-12-networks-epic-1019-analysis.md)
- plan · 2026-10-12 · [2026-10-12-networks-phase-1-read-operations](../../plans/2026-10-12-networks-phase-1-read-operations.md)
- pr-report · 2026-10-17 · [1385-neutron-networks-bff-read-only-networks-page](1385-neutron-networks-bff-read-only-networks-page.md)
- pr-report · 2026-10-17 · [1386-network-and-verify-do-not-merge](1386-network-and-verify-do-not-merge.md)
